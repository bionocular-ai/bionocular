import { buildLoadSkillTool } from './load-skill';
import { buildLookupTool } from './lookup';
import { buildSupabaseTools, type AgentToolContext } from './supabase';
import { createTurnState, type TurnStateOptions } from './turn';

/** Everything a request has to supply; the turn state is built here. */
export type AgentRequestContext = Omit<AgentToolContext, 'turn'> & TurnStateOptions;

export function agentTools({ limitChars, retainedEvidence, ...request }: AgentRequestContext) {
  const context: AgentToolContext = {
    ...request,
    turn: createTurnState({ limitChars, retainedEvidence }),
  };
  return {
    ...buildSupabaseTools(context),
    ...buildLookupTool(context),
    ...buildLoadSkillTool(context),
  };
}

export type AgentTools = ReturnType<typeof agentTools>;
export type { AgentToolContext };
