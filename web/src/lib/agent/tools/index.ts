import { buildSupabaseTools } from './supabase';

export function agentTools(userId: string) {
  return {
    ...buildSupabaseTools(userId),
  };
}

export type AgentTools = ReturnType<typeof agentTools>;
