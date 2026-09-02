import { tool } from 'ai';
import { z } from 'zod';
import { createServiceClient } from '@/lib/supabase/service';
import { getDbCancerType } from '@/lib/api';
import { NCT_ID_PATTERN } from '@/lib/constants';
import { PHASE_MAP, STATUS_MAP } from '@/lib/clinical-trials-enums';
import { DATA_TOOL_NAMES } from './names';
import { runTool } from './logging';
import {
  AGENT_TABLES,
  AGENT_TABLE_NAMES,
  applyCancerScope,
  applyNamedFilter,
  applyTrialKeys,
  describeTables,
  embedFor,
  projectionColumns,
  projectionFor,
  supportedFilters,
  viaFilters,
  FUNDING_VALUES,
  type AgentColumn,
  type AgentTable,
  type FilterName,
} from './schema';

/** PostgREST code for "column does not exist". */
const UNDEFINED_COLUMN = '42703';

/**
 * A filtered sweep has to come back whole, or the model reports a sample as if
 * it were the population: 184 Phase 3 cutaneous melanoma trials read through a
 * 25-row window looked like 9 active ones when there are 53.
 *
 * Row count alone is the wrong guard, because a row costs anywhere from 370
 * bytes (`news_feed`) to 650 (`clinical_trials`, which carries free text). The
 * size budget is what actually bounds the tool result; the row cap only stops
 * an unfiltered table scan from starting.
 */
const MAX_ROWS = 500;
const DEFAULT_ROWS = 25;
/**
 * Bounds `nctIds`, not the rows a filtered query can return - 1,134 Phase 1
 * cutaneous melanoma trials measured against `clinical_trials` is exactly why
 * a phase-scoped question has to filter `trial_outcomes` directly instead of
 * handing this cap a trial set of that size.
 */
const MAX_TRIAL_KEYS = 100;
/**
 * ~48k tokens of JSON, measured. The Phase 1 cutaneous melanoma
 * `trial_outcomes` sweep this branch was built for - 189 rows through the
 * `!inner` join, `detailed`, after `dropEmpty` - measures 92,934 chars, 71%
 * of this budget. That is the headline case, not a worst case with room to
 * spare.
 */
export const MAX_RESULT_CHARS = 130_000;

/**
 * Reduce each intervention to the drug and what kind of thing it is.
 *
 * `clinical_trials.interventions` carries the sponsor's prose alongside the
 * name. Measured over the 53 Phase 3 active cutaneous melanoma trials, the
 * column is 15,718 tokens, of which 12,594 are `description`, `otherNames` and
 * `armGroupLabels`. Name and type are what answer "which treatments"; the prose
 * is read once and then re-sent on every later step of the turn. Rows from
 * tables that do not project the column pass through untouched.
 */
function compactInterventions(rows: unknown[]): unknown[] {
  return rows.map((row) => {
    if (typeof row !== 'object' || row === null) return row;
    const { interventions } = row as { interventions?: unknown };
    if (!Array.isArray(interventions)) return row;
    return {
      ...row,
      interventions: interventions.map((entry) => {
        const { name, type } = entry as { name?: unknown; type?: unknown };
        return { name, type };
      }),
    };
  });
}

/**
 * Lift a `via`-join embed onto the row itself.
 *
 * PostgREST returns an active via-filter's embed as a nested
 * `{ clinical_trials: { phases, overall_status } }`, which `result-table.ts`
 * would otherwise render as `JSON.stringify` output instead of cells. Rows
 * from a query with no embed (the common case) pass through untouched.
 */
function flattenViaEmbed(rows: unknown[]): unknown[] {
  return rows.map((row) => {
    if (typeof row !== 'object' || row === null) return row;
    const { clinical_trials, ...rest } = row as Record<string, unknown> & { clinical_trials?: unknown };
    if (typeof clinical_trials !== 'object' || clinical_trials === null) return row;
    return { ...rest, ...clinical_trials };
  });
}

/**
 * Drop keys that carry no information, so a wide projection sends only the
 * columns a row actually populated. `trial_outcomes`' 198-column `detailed`
 * projection measures ~15.7 populated keys per row once this runs - what
 * makes that width affordable within `MAX_RESULT_CHARS`.
 *
 * `0` and `false` are real findings, not absence, so only the loader's own
 * not-found spellings are treated as empty.
 *
 * A null named by the row's own `is_nr` is the exception: that column is not
 * empty, it is *not reached*, and the null is the only place the marker has to
 * land. Dropping it left both the model and the rendered table reading "no DoR
 * data" where the truth was "DoR not reached" - the opposite clinical claim.
 */
const EMPTY_STRINGS = new Set(['', 'N/A', 'Not found']);

/** Column names this row marks as censored rather than missing. */
function censoredColumns(row: Record<string, unknown>): readonly unknown[] {
  const notReached = row.is_nr;
  return Array.isArray(notReached) ? notReached : [];
}

export function dropEmpty(rows: unknown[]): unknown[] {
  return rows.map((row) => {
    if (typeof row !== 'object' || row === null) return row;
    const censored = censoredColumns(row as Record<string, unknown>);
    const out: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(row as Record<string, unknown>)) {
      if ((value === null || value === undefined) && censored.includes(key)) {
        out[key] = null;
        continue;
      }
      if (value === null || value === undefined) continue;
      if (typeof value === 'string' && EMPTY_STRINGS.has(value)) continue;
      if (Array.isArray(value) && value.length === 0) continue;
      out[key] = value;
    }
    return out;
  });
}

/**
 * Drop rows from the tail until the payload fits the budget. Returns the kept
 * rows and whether anything was dropped, so the caller can say so out loud.
 */
export function fitToBudget<T>(rows: T[]): { kept: T[]; droppedForSize: boolean } {
  if (JSON.stringify(rows).length <= MAX_RESULT_CHARS) {
    return { kept: rows, droppedForSize: false };
  }
  let kept = rows;
  while (kept.length > 1 && JSON.stringify(kept).length > MAX_RESULT_CHARS) {
    kept = kept.slice(0, Math.floor(kept.length * 0.8));
  }
  return { kept, droppedForSize: true };
}

/**
 * Which of the requested trials no row carried.
 *
 * `coverage` measured the table, not the request: 53 NCT numbers asked of
 * `trial_landscape` came back as 48 rows and `complete: true`, which is true of
 * the table and false of the question. The model then answered for 48 without
 * knowing five had been asked about. Since `trial_landscape` is curated by hand
 * and lags the daily trial sync, that gap widens on its own.
 *
 * The array-keyed table (`news_feed.nct_ids`) carries several trials per row,
 * so a key counts as present if any row's array holds it.
 */
export function missingTrialKeys(
  rows: readonly unknown[],
  key: AgentColumn,
  requested: readonly string[],
): string[] {
  const present = new Set<string>();
  for (const row of rows) {
    if (typeof row !== 'object' || row === null) continue;
    const value = (row as Record<string, unknown>)[key.column];
    if (key.kind === 'array') {
      if (Array.isArray(value)) for (const entry of value) if (typeof entry === 'string') present.add(entry);
    } else if (typeof value === 'string') {
      present.add(value);
    }
  }
  return requested.filter((id) => !present.has(id));
}

export interface AgentToolContext {
  userId: string;
  /** Dashboard slug, e.g. `cutaneous-melanoma`. Validated by the caller. */
  cancerSlug: string;
  /** Present only once a chat has been persisted. */
  sessionId?: string;
  /** Per-request ID tying every tool log line to one chat session row. */
  traceId: string;
}

const PHASE_VALUES = Object.keys(PHASE_MAP) as [string, ...string[]];
const STATUS_VALUES = Object.keys(STATUS_MAP) as [string, ...string[]];

export function buildSupabaseTools({ userId, cancerSlug, sessionId, traceId }: AgentToolContext) {
  const dbCancerType = getDbCancerType(cancerSlug);

  return {
    query_proprietary_data: tool({
      description:
        "Query Bionocular's own oncology database. This is the only source of data available - " +
        'there is no live registry or literature lookup. Every query is automatically restricted ' +
        `to the dashboard's cancer type, so do not ask for one.\n\nTables:\n${describeTables()}\n\n` +
        'Filters are named parameters, not column expressions; one marked "via clinical_trials" ' +
          'above joins through the trial registry instead of reading a column on that table, so it ' +
          'excludes rows with no nct_id - `coverage.viaJoin` reports how many that excluded.\n\n' +
        `Returns at most ${MAX_ROWS} rows, and every result carries a coverage report: ` +
        '`matched` is how many rows exist in total, `returned` is how many you got, and ' +
        '`complete` says whether you are looking at all of them. When `complete` is false, ' +
        'either re-run with a higher `limit` or narrow the filters - and never describe a ' +
        'partial result as if it were the full set. To sweep a whole filtered set in one ' +
        `call, ask for limit ${MAX_ROWS} - a limit above ${DEFAULT_ROWS} needs at least one ` +
        'filter, because unfiltered it reads the table end to end. Filter the table you need ' +
        'directly first - phase and status reach several tables through the registry join ' +
        'named above, not only clinical_trials. Only when the table you need has no filter ' +
        'for what was asked, query one that does, then pass the NCT numbers it returned as ' +
        '`nctIds` to the table holding the rest.',
      inputSchema: z.object({
        table: z.enum(AGENT_TABLE_NAMES),
        nctIds: z
          .array(z.string().regex(NCT_ID_PATTERN, 'must be an NCT number, e.g. NCT00006368'))
          .min(1)
          .max(MAX_TRIAL_KEYS)
          .optional()
          .describe(
            'Restrict to these trials. Pass the whole set at once - this is how you enrich a ' +
              'result from another table (e.g. the NCT numbers of every Phase 3 trial) without ' +
              'reading a table end to end.',
          ),
        sponsor: z.string().min(2).optional().describe('Substring match on the sponsor name.'),
        phase: z
          .enum(PHASE_VALUES)
          .optional()
          .describe('Direct on clinical_trials; resolved via the join named above on the other tables that support it.'),
        status: z
          .array(z.enum(STATUS_VALUES))
          .min(1)
          .optional()
          .describe(
            'Direct on clinical_trials; resolved via the join named above on the other tables ' +
              'that support it. Recruitment status; several values match any of them. Trials ' +
              'still under way are RECRUITING, ACTIVE_NOT_RECRUITING, NOT_YET_RECRUITING and ' +
              'ENROLLING_BY_INVITATION.',
          ),
        drug: z
          .string()
          .min(2)
          .optional()
          .describe('Substring match on the treatment or arm name for this table.'),
        funding: z
          .enum(FUNDING_VALUES)
          .optional()
          .describe(
            'Who sponsors the trial, as the registry classes it. Not the same as `sponsor`, ' +
              'which matches the sponsor\'s name as a substring - asking for sponsor "industry" ' +
              'matches nothing. `industry` is lead_sponsor_class INDUSTRY; `non-industry` is ' +
              'every other class (NIH, NETWORK, OTHER_GOV, FED, OTHER). Direct on ' +
              'clinical_trials; resolved via the join named above on the other tables.',
          ),
        detail: z
          .enum(['concise', 'detailed'])
          .optional()
          .describe(
            'How much of each row to return. `concise` carries the columns an answer is usually ' +
              "built from; `detailed` is the table's full column set, at roughly twice the tokens " +
              'per row. On `trial_outcomes` that full set is every efficacy and safety endpoint - ' +
              'PFS, OS, EFS, RFS, MFS, response and duration measures, and the adverse-event ' +
              'families - so a question naming specific endpoints wants `detailed`. On ' +
              '`clinical_trials` it is provenance and classification detail: how a trial was ' +
              'classified, its conditions, its keywords. Defaults to `concise`.',
          ),
        endpoints: z
          .enum(['efficacy', 'safety', 'both'])
          .optional()
          .describe(
            'Which half of `trial_outcomes` the question is about, so the answer is not padded ' +
              'with the other half. `efficacy` keeps survival, response and duration endpoints; ' +
              '`safety` keeps the adverse-event families and per-toxicity rates; `both` keeps ' +
              'everything. Arm, drug and patient counts are kept either way. Set it to what was ' +
              'asked - it also decides which hub the user can open the answer in. Defaults to ' +
              '`both`. No effect on the other tables.',
          ),
        limit: z
          .number()
          .int()
          .min(1)
          .max(MAX_ROWS)
          .default(DEFAULT_ROWS)
          .describe(`Raise toward ${MAX_ROWS} when the user asks for a complete set.`),
      }),
      execute: async (args) =>
        runTool('query_proprietary_data', traceId, args, async () => {
        const { table, nctIds, sponsor, phase, status, drug, funding, detail, endpoints, limit } = args;
        const spec = AGENT_TABLES[table];

        // Cancer scope is applied to every query, so on its own it narrows
        // nothing the caller chose. Without a second predicate a raised limit is
        // a table read: 500 unfiltered `trial_landscape` rows measured 48k
        // tokens and carried 3 that mattered. The default window still allows an
        // unfiltered browse, which is how "what exists here" gets answered.
        const narrowed = [nctIds, sponsor, phase, status, drug, funding].some((f) => f !== undefined);
        if (!narrowed && limit > DEFAULT_ROWS) {
          const filters = supportedFilters(table);
          return {
            ok: false as const,
            reason: 'unfiltered_sweep' as const,
            table,
            supportedFilters: filters,
            hint:
              `A limit above ${DEFAULT_ROWS} needs a filter - unfiltered, \`${table}\` is read ` +
              'end to end and most of what comes back is noise. ' +
              (filters.length
                ? `Narrow it with ${filters.join(', ')} - some of those may resolve through the ` +
                  'registry join rather than a column on this table - or find the trials you ' +
                  'want in another table first and pass their NCT numbers as `nctIds`.'
                : 'Narrow it, or find the trials you want in another table first and pass ' +
                  'their NCT numbers as `nctIds`.'),
          };
        }

        const supabase = createServiceClient();

        // Resolved before the select is built, not during the filter loop
        // below: the `!inner` embed lives in the select string, and by the
        // time the loop runs which filters are active it is already too late
        // to change what was asked for.
        const requested = (
          [
            ['sponsor', sponsor],
            ['phase', phase],
            ['status', status],
            ['drug', drug],
            ['funding', funding],
          ] as const
        )
          .filter(([, v]) => v !== undefined)
          .map(([name]) => name);
        const activeVia = viaFilters(table, requested);
        const select =
          projectionFor(table, detail ?? 'concise', endpoints ?? 'both') + embedFor(table, activeVia);

        let query = supabase.from(table).select(select, { count: 'exact' }).limit(limit);

        query = applyCancerScope(query, table, dbCancerType);
        if (nctIds) query = applyTrialKeys(query, table, nctIds);

        const named: Array<[FilterName, string | readonly string[] | undefined]> = [
          ['sponsor', sponsor],
          ['phase', phase],
          ['status', status],
          ['drug', drug],
          ['funding', funding],
        ];
        const applied: Record<string, string | readonly string[]> = {};
        for (const [name, value] of named) {
          if (value === undefined) continue;
          const next = applyNamedFilter(query, table, name, value);
          if (!next) {
            return {
              ok: false as const,
              reason: 'unsupported_filter' as const,
              table,
              filter: name,
              supportedFilters: supportedFilters(table),
              hint: `\`${table}\` has no ${name} column. Try a table that does, or drop the filter.`,
            };
          }
          query = next;
          applied[name] = value;
        }

        const { data, error, count } = await query;

        if (error) {
          console.error('query_proprietary_data failed', { table, code: error.code, message: error.message });
          return {
            ok: false as const,
            reason: error.code === UNDEFINED_COLUMN ? ('unknown_column' as const) : ('query_failed' as const),
            table,
            message: error.message,
            availableColumns: projectionColumns(table),
          };
        }

        // One extra HEAD request, issued only when a via-filter fired: how
        // many in-scope rows the `!inner` join above silently dropped for
        // having no nct_id, so the result can say so instead of reading as a
        // clean phase/status match. A failed count is logged and swallowed -
        // a missing caveat number is better than failing the whole call.
        let viaJoin: { table: 'clinical_trials'; unlinked?: number; hint: string } | undefined;
        if (activeVia.length > 0 && spec.trialKey) {
          const trialKeyColumn = spec.trialKey.column;
          let unlinkedQuery = supabase
            .from(table)
            .select(trialKeyColumn, { count: 'exact', head: true });
          unlinkedQuery = applyCancerScope(unlinkedQuery, table, dbCancerType);
          const { count: unlinkedCount, error: unlinkedError } = await unlinkedQuery.is(trialKeyColumn, null);
          if (unlinkedError) {
            console.error('query_proprietary_data via-join count failed', {
              table,
              code: unlinkedError.code,
              message: unlinkedError.message,
            });
          }
          const unlinked = unlinkedError ? undefined : (unlinkedCount ?? undefined);
          // Names the filters that actually fired rather than a fixed
          // "phase or status": a funding-scoped result would otherwise claim
          // the exclusion was about a filter the caller never asked for.
          const byName =
            activeVia.length === 1
              ? activeVia[0]
              : `${activeVia.slice(0, -1).join(', ')} or ${activeVia[activeVia.length - 1]}`;
          viaJoin = {
            table: 'clinical_trials',
            ...(unlinked !== undefined ? { unlinked } : {}),
            hint:
              'Every row returned here carries an nct_id - the registry join requires one. ' +
              'Separately, ' +
              (unlinked !== undefined ? `${unlinked} rows in scope` : 'other rows in scope') +
              ` have no nct_id at all and cannot be filtered by ${byName}, so they are ` +
              'excluded from this result: that is a linkage gap, not evidence that they fail the ' +
              'filter.',
          };
        }

        // Trimmed before the size budget runs, so the budget measures what the
        // model will actually be sent.
        const fetched = dropEmpty(compactInterventions(flattenViaEmbed(data ?? [])));
        const matched = count ?? fetched.length;
        const { kept: rows, droppedForSize } = fitToBudget(fetched);
        const complete = rows.length === matched;
        const coverage = {
          returned: rows.length,
          matched,
          complete,
          cancerType: dbCancerType,
          ...(viaJoin ? { viaJoin } : {}),
          ...(complete
            ? {}
            : {
                truncatedBy: droppedForSize ? ('size' as const) : ('limit' as const),
                hint: droppedForSize
                  ? `Only ${rows.length} of ${matched} rows fit in one result. Narrow the filters - do not present this as the full set.`
                  : `You asked for ${limit} of ${matched} matching rows. Re-run with a higher limit (up to ${MAX_ROWS}) if the user wants all of them, and until then say the result is a sample.`,
              }),
          ...(nctIds ? { trialKeyColumn: spec.trialKey?.column } : {}),
          // Only once the result is whole: under truncation "absent from the
          // table" and "not returned yet" are the same shape, so naming one as
          // missing would be a guess.
          ...(nctIds && complete && spec.trialKey
            ? (() => {
                const missing = missingTrialKeys(rows, spec.trialKey, nctIds);
                return {
                  requested: nctIds.length,
                  ...(missing.length
                    ? {
                        missing,
                        hint:
                          `${missing.length} of the ${nctIds.length} trials you asked about have no row in ` +
                          `\`${table}\`. Report them as present but uncovered by this table - do not drop ` +
                          'them from the answer, and do not fill the gap from memory.',
                      }
                    : {}),
                };
              })()
            : {}),
          // The static caveat describes an ordinary query, where a returned row
          // may itself lack an nct_id. Under an active via-join that is no
          // longer possible - every returned row passed the `!inner` join - so
          // the caveat would be false about this result set, not merely
          // redundant with `viaJoin.hint`. Suppressed here rather than merged.
          ...(spec.caveat && !viaJoin ? { caveat: spec.caveat } : {}),
        };

        if (rows.length === 0) {
          return {
            ok: false as const,
            reason: 'no_rows' as const,
            table,
            appliedFilters: { ...applied, ...(nctIds ? { nctIds } : {}) },
            coverage,
            hint: 'Report this absence to the user. Do not substitute knowledge from outside these results.',
          };
        }

        return { ok: true as const, table, coverage, rows };
        }),
    }),

    store_finding: tool({
      description:
        'Persist a research finding for the user. Call only when the user explicitly asks to ' +
        'save, bookmark, or remember something. Provide a concise title, a 1-3 sentence summary, ' +
        'the tool the finding came from, and the identifiers it rests on (NCT numbers, ' +
        'abstract or publication IDs) exactly as they appeared in that tool result.',
      inputSchema: z.object({
        findingType: z.enum(['trial', 'literature', 'compound', 'target', 'landscape', 'other']),
        title: z.string().min(3).max(200),
        summary: z.string().min(10).max(2000),
        sourceTool: z.enum(DATA_TOOL_NAMES),
        citations: z.array(z.string()).default([]),
      }),
      execute: async (args) =>
        runTool('store_finding', traceId, args, async () => {
        const { findingType, title, summary, sourceTool, citations } = args;
        const supabase = createServiceClient();
        const { data, error } = await supabase
          .from('agent_findings')
          .insert({
            user_id: userId,
            session_id: sessionId ?? null,
            finding_type: findingType,
            title,
            summary,
            source_tool: sourceTool,
            citations,
          })
          .select('id')
          .single();

        if (error) {
          console.error('store_finding failed', { code: error.code, message: error.message });
          return { ok: false as const, reason: 'insert_failed' as const, message: error.message };
        }
        return { ok: true as const, id: data.id };
        }),
    }),
  };
}

export type SupabaseAgentTools = ReturnType<typeof buildSupabaseTools>;
export type { AgentTable };
