import { tool } from 'ai';
import { z } from 'zod';
import { createServiceClient } from '@/lib/supabase/service';
import { getDbCancerType } from '@/lib/api';
import { PHASE_MAP } from '@/lib/clinical-trials-enums';
import { DATA_TOOL_NAMES } from './names';
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

const MAX_ROWS = 25;

export interface AgentToolContext {
  userId: string;
  /** Dashboard slug, e.g. `cutaneous-melanoma`. Validated by the caller. */
  cancerSlug: string;
  /** Present only once a chat has been persisted. */
  sessionId?: string;
}

const PHASE_VALUES = Object.keys(PHASE_MAP) as [string, ...string[]];

export function buildSupabaseTools({ userId, cancerSlug, sessionId }: AgentToolContext) {
  const dbCancerType = getDbCancerType(cancerSlug);

  return {
    query_proprietary_data: tool({
      description:
        "Query Bionocular's own oncology database. This is the only source of data available - " +
        'there is no live registry or literature lookup. Every query is automatically restricted ' +
        `to the dashboard's cancer type, so do not ask for one.\n\nTables:\n${describeTables()}\n\n` +
        'Filters are named parameters, not column expressions. Returns at most ' +
        `${MAX_ROWS} rows plus a coverage report of how many rows matched in total.`,
      inputSchema: z.object({
        table: z.enum(AGENT_TABLE_NAMES),
        nctId: z
          .string()
          .regex(NCT_ID_PATTERN, 'must be an NCT number, e.g. NCT00006368')
          .optional()
          .describe('Restrict to one trial.'),
        sponsor: z.string().min(2).optional().describe('Substring match on the sponsor name.'),
        phase: z.enum(PHASE_VALUES).optional().describe('clinical_trials only.'),
        drug: z
          .string()
          .min(2)
          .optional()
          .describe('Substring match on the treatment or arm name for this table.'),
        limit: z.number().int().min(1).max(MAX_ROWS).default(10),
      }),
      execute: async ({ table, nctId, sponsor, phase, drug, limit }) => {
        const spec = AGENT_TABLES[table];
        const supabase = createServiceClient();

        let query = supabase
          .from(table)
          .select(spec.projection, { count: 'exact' })
          .limit(limit);

        query = applyCancerScope(query, table, dbCancerType);
        if (nctId) query = applyTrialKey(query, table, nctId);

        const named: Array<[FilterName, string | undefined]> = [
          ['sponsor', sponsor],
          ['phase', phase],
          ['drug', drug],
        ];
        const applied: Record<string, string> = {};
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

        const rows = data ?? [];
        const coverage = {
          returned: rows.length,
          matched: count ?? rows.length,
          cancerType: dbCancerType,
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
      },
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
      execute: async ({ findingType, title, summary, sourceTool, citations }) => {
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
      },
    }),
  };
}

export type SupabaseAgentTools = ReturnType<typeof buildSupabaseTools>;
export type { AgentTable };
