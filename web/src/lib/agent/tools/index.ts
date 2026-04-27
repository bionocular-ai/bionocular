import { anthropic } from '@ai-sdk/anthropic';
import { searchPubmedTool } from './pubmed';
import { searchClinicalTrialsTool } from './clinical-trials';
import { searchChemblTool } from './chembl';
import { queryOpenTargetsTool } from './open-targets';
import { buildSupabaseTools } from './supabase';

const ONCOLOGY_NEWS_DOMAINS = [
  'onclive.com',
  'biospace.com',
  'targetedonc.com',
  'cancernetwork.com',
];

export function agentTools(userId: string) {
  return {
    search_pubmed:           searchPubmedTool,
    search_clinical_trials:  searchClinicalTrialsTool,
    search_chembl:           searchChemblTool,
    query_open_targets:      queryOpenTargetsTool,
    web_search: anthropic.tools.webSearch_20250305({
      maxUses: 3,
      allowedDomains: ONCOLOGY_NEWS_DOMAINS,
    }),
    ...buildSupabaseTools(userId),
  };
}

export type AgentTools = ReturnType<typeof agentTools>;
