import { tool } from 'ai';
import { z } from 'zod';
import { createServiceClient } from '@/lib/supabase/service';
import { getDbCancerType } from '@/lib/api';
import { NCT_ID_PATTERN } from '@/lib/constants';
import {
  AGENT_TABLES,
  AGENT_TABLE_NAMES,
  applyCancerScope,
  applyTrialKeys,
  type AgentTable,
} from './schema';
import { runTool } from './logging';
import type { AgentToolContext } from './supabase';

/** Enough to show every arm or curve for one trial without dumping the table. */
const LOOKUP_ROW_LIMIT = 10;

interface TableHit {
  matched: number;
  rows: unknown[];
  caveat?: string;
}

/**
 * Look one trial up across every relation at once.
 *
 * The point of this tool is that "we have nothing on that trial" becomes a fact
 * the model is told, rather than a silence it fills. Three outcomes are
 * distinguishable: the trial is here, the trial is in the database but tagged to
 * a different cancer type, and the trial is not in the database at all.
 */
export function buildLookupTool({ cancerSlug, traceId }: AgentToolContext) {
  const dbCancerType = getDbCancerType(cancerSlug);

  return {
    lookup_trial: tool({
      description:
        'Look up a single trial by NCT number across every table at once - registry record, ' +
        'treatment landscape, reported outcomes, survival curves and news coverage. Use this ' +
        'instead of querying each table separately when the user names a trial. The result ' +
        'says explicitly which tables hold the trial and which do not; report both.',
      inputSchema: z.object({
        nctId: z
          .string()
          .regex(NCT_ID_PATTERN, 'must be an NCT number, e.g. NCT00006368')
          .describe('An 8-digit NCT number. Other registry IDs are not supported.'),
      }),
      execute: async (args) =>
        runTool('lookup_trial', traceId, args, async () => {
        const { nctId } = args;
        const supabase = createServiceClient();

        const results = await Promise.all(
          AGENT_TABLE_NAMES.map(async (table): Promise<[AgentTable, TableHit | null]> => {
            const spec = AGENT_TABLES[table];
            let query = supabase
              .from(table)
              .select(spec.projection, { count: 'exact' })
              .limit(LOOKUP_ROW_LIMIT);
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
            const rows = data ?? [];
            if (rows.length === 0) return [table, { matched: 0, rows: [] }];
            return [table, { matched: count ?? rows.length, rows, caveat: spec.caveat }];
          }),
        );

        const tables = Object.fromEntries(results) as Record<AgentTable, TableHit | null>;
        const presentIn = AGENT_TABLE_NAMES.filter((t) => (tables[t]?.matched ?? 0) > 0);
        const absentFrom = AGENT_TABLE_NAMES.filter((t) => tables[t]?.matched === 0);

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

        return {
          found: true as const,
          nctId,
          cancerType: dbCancerType,
          coverage: {
            presentIn,
            absentFrom,
            caveats: absentFrom
              .map((t) => AGENT_TABLES[t].caveat)
              .filter((c): c is string => Boolean(c)),
          },
          tables,
        };
        }),
    }),
  };
}
