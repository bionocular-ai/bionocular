import { tool } from 'ai';
import { z } from 'zod';
import { createServiceClient } from '@/lib/supabase/service';
import { getDbCancerType } from '@/lib/api';
import { PHASE_MAP, STATUS_MAP } from '@/lib/clinical-trials-enums';
import { DATA_TOOL_NAMES } from './names';
import { runTool } from './logging';
import {
  AGENT_TABLES,
  AGENT_TABLE_NAMES,
  NCT_ID_PATTERN,
  applyCancerScope,
  applyNamedFilter,
  applyTrialKey,
  describeTables,
  projectionColumns,
  supportedFilters,
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
/** ~35k tokens of JSON. Every filtered sweep measured fits well under this. */
const MAX_RESULT_CHARS = 130_000;

/**
 * Drop rows from the tail until the payload fits the budget. Returns the kept
 * rows and whether anything was dropped, so the caller can say so out loud.
 */
function fitToBudget<T>(rows: T[]): { kept: T[]; droppedForSize: boolean } {
  if (JSON.stringify(rows).length <= MAX_RESULT_CHARS) {
    return { kept: rows, droppedForSize: false };
  }
  let kept = rows;
  while (kept.length > 1 && JSON.stringify(kept).length > MAX_RESULT_CHARS) {
    kept = kept.slice(0, Math.floor(kept.length * 0.8));
  }
  return { kept, droppedForSize: true };
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
        'Filters are named parameters, not column expressions.\n\n' +
        `Returns at most ${MAX_ROWS} rows, and every result carries a coverage report: ` +
        '`matched` is how many rows exist in total, `returned` is how many you got, and ' +
        '`complete` says whether you are looking at all of them. When `complete` is false, ' +
        'either re-run with a higher `limit` or narrow the filters - and never describe a ' +
        'partial result as if it were the full set. To sweep a whole filtered set in one ' +
        `call, ask for limit ${MAX_ROWS}.`,
      inputSchema: z.object({
        table: z.enum(AGENT_TABLE_NAMES),
        nctId: z
          .string()
          .regex(NCT_ID_PATTERN, 'must be an NCT number, e.g. NCT00006368')
          .optional()
          .describe('Restrict to one trial.'),
        sponsor: z.string().min(2).optional().describe('Substring match on the sponsor name.'),
        phase: z.enum(PHASE_VALUES).optional().describe('clinical_trials only.'),
        status: z
          .array(z.enum(STATUS_VALUES))
          .min(1)
          .optional()
          .describe(
            'clinical_trials only. Recruitment status; several values match any of them. ' +
              'Trials still under way are RECRUITING, ACTIVE_NOT_RECRUITING, ' +
              'NOT_YET_RECRUITING and ENROLLING_BY_INVITATION.',
          ),
        drug: z
          .string()
          .min(2)
          .optional()
          .describe('Substring match on the treatment or arm name for this table.'),
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
        const { table, nctId, sponsor, phase, status, drug, limit } = args;
        const spec = AGENT_TABLES[table];
        const supabase = createServiceClient();

        let query = supabase
          .from(table)
          .select(spec.projection, { count: 'exact' })
          .limit(limit);

        query = applyCancerScope(query, table, dbCancerType);
        if (nctId) query = applyTrialKey(query, table, nctId);

        const named: Array<[FilterName, string | readonly string[] | undefined]> = [
          ['sponsor', sponsor],
          ['phase', phase],
          ['status', status],
          ['drug', drug],
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

        const fetched = data ?? [];
        const matched = count ?? fetched.length;
        const { kept: rows, droppedForSize } = fitToBudget(fetched);
        const complete = rows.length === matched;
        const coverage = {
          returned: rows.length,
          matched,
          complete,
          cancerType: dbCancerType,
          ...(complete
            ? {}
            : {
                truncatedBy: droppedForSize ? ('size' as const) : ('limit' as const),
                hint: droppedForSize
                  ? `Only ${rows.length} of ${matched} rows fit in one result. Narrow the filters - do not present this as the full set.`
                  : `You asked for ${limit} of ${matched} matching rows. Re-run with a higher limit (up to ${MAX_ROWS}) if the user wants all of them, and until then say the result is a sample.`,
              }),
          ...(nctId ? { trialKeyColumn: spec.trialKey?.column } : {}),
          ...(spec.caveat ? { caveat: spec.caveat } : {}),
        };

        if (rows.length === 0) {
          return {
            ok: false as const,
            reason: 'no_rows' as const,
            table,
            appliedFilters: { ...applied, ...(nctId ? { nctId } : {}) },
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
