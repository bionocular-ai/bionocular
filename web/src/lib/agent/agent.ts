/**
 * The agent: a bounded tool loop over the retrieval tools.
 *
 * One definition serves the route and the evals, so the two cannot drift on
 * step count, output cap or the last-step rule the way they once did. The
 * model is a parameter for the same reason: the evals run the same agent on
 * several models.
 */

import { stepCountIs, ToolLoopAgent, type TelemetrySettings, type UIMessage } from 'ai';
import { NCT_ID_SOURCE } from './groundedness';
import { resolveModel, type AgentModelSpec } from './model';
import type { AgentTools } from './tools';

/**
 * A cap on thinking *and* response text together, not on the answer alone -
 * so this has to grow if a model's thinking is turned up in `model.ts`.
 */
export const MAX_OUTPUT_TOKENS = 4096;

/**
 * Tool calls plus a final answer. The last step is forced to answer in text
 * (see `prepareStep`), so one of these is always spent on the reply.
 */
export const MAX_STEPS = 8;

/** Appended as the final user turn when the step cap is reached. */
export const LAST_STEP_NOTICE =
  'No further tool calls are available this turn. Answer now from the results above: state what ' +
  'was found, what was not, and which questions remain unverified. Do not describe what you would query next.';

export interface CreateAgentOptions {
  instructions: string;
  tools: AgentTools;
  model?: AgentModelSpec;
  /**
   * The user named a trial: the first step is `lookup_trial` and nothing
   * else, so the turn does not spend a step deciding what the question
   * already said. Later steps are free.
   */
  forceLookupFirst?: boolean;
  telemetry?: TelemetrySettings;
}

export function createAgent({
  instructions,
  tools,
  model = resolveModel(),
  forceLookupFirst = false,
  telemetry,
}: CreateAgentOptions) {
  return new ToolLoopAgent({
    model: model.create(),
    instructions,
    tools,
    maxOutputTokens: MAX_OUTPUT_TOKENS,
    stopWhen: stepCountIs(MAX_STEPS),
    providerOptions: model.providerOptions,
    experimental_telemetry: telemetry,
    prepareStep: ({ stepNumber, messages }) => {
      // Take the tools away for the last step so the turn cannot end on a
      // tool call the model never got to explain - tool cards and silence.
      // Removing the tools is not enough on its own: with only the tool
      // choice withdrawn, Gemini returned an empty message on every run that
      // reached this step. Told in words that the loop is over, it answers.
      if (stepNumber === MAX_STEPS - 1) {
        return {
          toolChoice: 'none',
          messages: [...messages, { role: 'user', content: LAST_STEP_NOTICE }],
        };
      }
      if (stepNumber === 0 && forceLookupFirst) {
        return { toolChoice: { type: 'tool', toolName: 'lookup_trial' }, activeTools: ['lookup_trial'] };
      }
      return {};
    },
  });
}

export type BionocularAgent = ReturnType<typeof createAgent>;

/** Text of the last user message, which is what a fast path is decided on. */
export function lastUserText(messages: UIMessage[]): string {
  const last = [...messages].reverse().find((m) => m.role === 'user');
  if (!last) return '';
  return last.parts
    .filter((p): p is { type: 'text'; text: string } => p.type === 'text')
    .map((p) => p.text)
    .join('\n');
}

export function mentionsNct(text: string): boolean {
  return new RegExp(NCT_ID_SOURCE).test(text);
}
