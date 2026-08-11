import { buildLookupTool } from './lookup';
import { buildSupabaseTools, type AgentToolContext } from './supabase';

export function agentTools(context: AgentToolContext) {
  return {
    ...buildSupabaseTools(context),
    ...buildLookupTool(context),
  };
}

export type AgentTools = ReturnType<typeof agentTools>;
export type { AgentToolContext };
