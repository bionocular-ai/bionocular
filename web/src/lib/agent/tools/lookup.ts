import { tool } from 'ai';
import { z } from 'zod';
import { createServiceClient } from '@/lib/supabase/service';
import { getDbCancerType } from '@/lib/api';
import { NCT_ID_PATTERN } from '@/lib/constants';
import {
  AGENT_TABLES,
  AGENT_TABLE_NAMES,
  applyCancerScope,
  applyOrder,
  applyTrialKeys,
  projectionFor,
  type AgentTable,
} from './schema';
import { runTool } from './logging';
import { dropEmpty, MAX_RESULT_CHARS, type AgentToolContext } from './supabase';

/** Enough to show every arm or curve for one trial without dumping the table. */
const LOOKUP_ROW_LIMIT = 10;

interface TableHit {
  matched: number;
  rows: unknown[];
  caveat?: string;
}

/**
 * Trim the multi-row tables until the whole lookup fits `limitChars`.
 *
 * One row at a time from whichever table currently has the most, so a trial
 * with ten outcome arms and ten curves loses them evenly rather than one table
 * vanishing first. Table order breaks ties, so the result is deterministic.
 */
export function fitLookupToBudget(
  tables: Record<AgentTable, TableHit | null>,
  limitChars: number,
): { tables: Record<AgentTable, TableHit | null>; truncated: AgentTable[] } {
  const out = { ...tables };
  const truncated = new Set<AgentTable>();
  while (JSON.stringify(out).length > limitChars) {
    let widest: AgentTable | null = null;
    for (const table of AGENT_TABLE_NAMES) {
      const rows = out[table]?.rows.length ?? 0;
      if (rows > 1 && rows > (out[widest!]?.rows.length ?? 0)) widest = table;
    }
    if (widest === null) break;
    const hit = out[widest]!;
    out[widest] = { ...hit, rows: hit.rows.slice(0, -1) };
    truncated.add(widest);
  }
  return { tables: out, truncated: [...truncated] };
}

/**
 * Look one trial up across every relation at once.
 *
 * The point of this tool is that "we have nothing on that trial" becomes a fact
 * the model is told, rather than a silence it fills. Three outcomes are
 * distinguishable: the trial is here, the trial is in the database but tagged to
 * a different cancer type, and the trial is not in the database at all.
 */
export function buildLookupTool({ cancerSlug, traceId, turn }: AgentToolContext) {
  const dbCancerType = getDbCancerType(cancerSlug);

  return {
    lookup_trial: tool({
      description:
        'Look up a single trial by NCT number across every table at once - registry record, ' +
        'treatment landscape, reported outcomes, survival curves and news coverage. Use this ' +
        'instead of querying each table separately when the user names a trial. The result ' +
        'says explicitly which tables hold the trial and which do not; report both. Call it ' +
        'once per trial to compare several.',
      inputSchema: z.object({
        nctId: z
          .string()
          .regex(NCT_ID_PATTERN, 'must be an NCT number, e.g. NCT00006368')
          .describe('An 8-digit NCT number. Other registry IDs are not supported.'),
        detail: z
          .enum(['concise', 'detailed'])
          .optional()
          .describe(
            '`concise` (default) carries the columns an answer is usually built from; ' +
              '`detailed` is every column, including every efficacy and safety endpoint on ' +
              'trial_outcomes. Ask for `detailed` when the question names specific endpoints.',
          ),
        endpoints: z
          .enum(['efficacy', 'safety', 'both'])
          .optional()
          .describe(
            'Which half of trial_outcomes the question is about. Defaults to `both`; no effect ' +
              'on the other tables.',
          ),
      }),
      execute: async (args) =>
        runTool('lookup_trial', traceId, args, async () => {
        const { nctId, detail = 'concise', endpoints = 'both' } = args;
        const supabase = createServiceClient();

        const results = await Promise.all(
          AGENT_TABLE_NAMES.map(async (table): Promise<[AgentTable, TableHit | null]> => {
            const spec = AGENT_TABLES[table];
            let query = supabase
              .from(table)
              .select(projectionFor(table, detail, endpoints), { count: 'exact' })
              .limit(LOOKUP_ROW_LIMIT);
            query = applyOrder(query, table);
            query = applyCancerScope(query, table, dbCancerType);
            query = applyTrialKeys(query, table, [nctId]);

            const { data, error, count } = await query;
            if (error) {
              console.error('lookup_trial table query failed', {
                table,
                code: error.code,
                message: error.message,
              });
              return [table, null];
            }
            // A `detailed` row skeleton carries up to 198 columns on
            // trial_outcomes; dropEmpty keeps a lookup down to the ones that
            // actually populated.
            const rows = dropEmpty(data ?? []);
            if (rows.length === 0) return [table, { matched: 0, rows: [] }];
            return [table, { matched: count ?? rows.length, rows, caveat: spec.caveat }];
          }),
        );

        const fetched = Object.fromEntries(results) as Record<AgentTable, TableHit | null>;
        const presentIn = AGENT_TABLE_NAMES.filter((t) => (fetched[t]?.matched ?? 0) > 0);
        const absentFrom = AGENT_TABLE_NAMES.filter((t) => fetched[t]?.matched === 0);

        if (presentIn.length === 0) {
          // Distinguish "we have never heard of this trial" from "we have it, but
          // it is tagged to another cancer type" - only the first justifies
          // telling the user the trial is unknown to Bionocular.
          const { count: unscoped } = await supabase
            .from('clinical_trials')
            .select('nct_id', { count: 'exact', head: true })
            .eq('nct_id', nctId);

          return {
            found: false as const,
            nctId,
            reason: unscoped ? ('other_cancer_type' as const) : ('not_in_bionocular' as const),
            cancerType: dbCancerType,
            hint: unscoped
              ? `${nctId} exists in the database but is not tagged to ${dbCancerType}. Say so; do not describe it from memory.`
              : `Bionocular holds no record of ${nctId}. Say so plainly; do not describe it from memory.`,
          };
        }

        // Same two ceilings as query_proprietary_data: one result, and what
        // is left of the turn.
        const limitChars = Math.min(MAX_RESULT_CHARS, turn.remainingChars());
        const { tables, truncated } = fitLookupToBudget(fetched, limitChars);

        const result = {
          found: true as const,
          nctId,
          cancerType: dbCancerType,
          coverage: {
            presentIn,
            absentFrom,
            caveats: absentFrom
              .map((t) => AGENT_TABLES[t].caveat)
              .filter((c): c is string => Boolean(c)),
            ...(truncated.length
              ? {
                  truncated,
                  hint:
                    `Not every row fit the result budget: ${truncated.join(', ')} ` +
                    'show a subset of this trial\'s rows. Say so rather than treating the subset as complete.',
                }
              : {}),
          },
          tables,
        };
        turn.spend(JSON.stringify(result).length);
        turn.recordEvidence(Object.values(tables).flatMap((hit) => hit?.rows ?? []));
        return result;
        }),
    }),
  };
}
