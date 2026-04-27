import { tool } from 'ai';
import { z } from 'zod';
import { createServiceClient } from '@/lib/supabase/service';

const ALLOWED_TABLES = ['clinical_trials', 'trial_outcomes', 'trial_landscape'] as const;
type AllowedTable = typeof ALLOWED_TABLES[number];

export function buildSupabaseTools(userId: string) {
  return {
    query_proprietary_data: tool({
      description:
        "Query Bionocular's proprietary trial database. ALWAYS try this first before public " +
        'sources. Tables: ' +
        '`clinical_trials` (live trial registry mirror with our enrichments), ' +
        '`trial_outcomes` (extracted efficacy/safety endpoints from abstracts and publications), ' +
        '`trial_landscape` (denormalized view joining trials, outcomes, cancer-type tags). ' +
        'Filter by NCT ID, cancer_type, sponsor, phase, or any column. Returns up to 25 rows.',
      inputSchema: z.object({
        table: z.enum(ALLOWED_TABLES),
        filters: z
          .record(z.string(), z.union([z.string(), z.number(), z.boolean()]))
          .optional()
          .describe('Equality filters keyed by column. e.g. { cancer_type: "Cutaneous Melanoma" }'),
        limit: z.number().int().min(1).max(25).default(10),
      }),
      providerOptions: {
        anthropic: { cacheControl: { type: 'ephemeral' } },
      },
      execute: async ({ table, filters, limit }) => {
        const supabase = createServiceClient();
        let q = supabase.from(table as AllowedTable).select('*').limit(limit);
        if (filters) {
          for (const [k, v] of Object.entries(filters)) {
            q = q.eq(k, v);
          }
        }
        const { data, error } = await q;
        if (error) throw new Error(`Supabase query failed: ${error.message}`);
        return { table, count: data?.length ?? 0, rows: data ?? [] };
      },
    }),

    store_finding: tool({
      description:
        'Persist a research finding for the user. Call only when the user explicitly asks to ' +
        'save, bookmark, or remember something. Provide a concise title, a 1-3 sentence summary, ' +
        'and the citations array (NCT IDs, PMIDs, ChEMBL IDs, etc).',
      inputSchema: z.object({
        findingType: z.enum(['trial', 'literature', 'compound', 'target', 'landscape', 'other']),
        title: z.string().min(3).max(200),
        summary: z.string().min(10).max(2000),
        sourceTool: z.string().describe('Which tool produced this (e.g. "search_clinical_trials")'),
        citations: z.array(z.string()).default([]),
      }),
      providerOptions: {
        anthropic: { cacheControl: { type: 'ephemeral' } },
      },
      execute: async ({ findingType, title, summary, sourceTool, citations }) => {
        const supabase = createServiceClient();
        const { data, error } = await supabase
          .from('agent_findings')
          .insert({
            user_id: userId,
            finding_type: findingType,
            title,
            summary,
            source_tool: sourceTool,
            citations,
          })
          .select('id')
          .single();
        if (error) throw new Error(`store_finding failed: ${error.message}`);
        return { ok: true, id: data.id };
      },
    }),
  };
}
