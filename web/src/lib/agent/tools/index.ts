import { buildLoadSkillTool } from './load-skill';
import { buildLookupTool } from './lookup';
import { buildSupabaseTools, type AgentToolContext } from './supabase';
import { createTurnState, type TurnState, type TurnStateOptions } from './turn';

/** Everything a request has to supply; the turn state is built here. */
export type AgentRequestContext = Omit<AgentToolContext, 'turn'> & TurnStateOptions;

/**
 * The tool set for one turn, and the state its tools share. The state comes
 * back to the caller because the run record is built from it once the turn
 * is over.
 */
export function buildAgentTools({ limitChars, retainedEvidence, ...request }: AgentRequestContext): {
  tools: AgentTools;
  turn: TurnState;
} {
  const turn = createTurnState({ limitChars, retainedEvidence });
  const context: AgentToolContext = { ...request, turn };
  return {
    tools: {
      ...buildSupabaseTools(context),
      ...buildLookupTool(context),
      ...buildLoadSkillTool(context),
    },
    turn,
  };
}

export type AgentTools = ReturnType<typeof buildSupabaseTools> &
  ReturnType<typeof buildLookupTool> &
  ReturnType<typeof buildLoadSkillTool>;
export type { AgentToolContext };
