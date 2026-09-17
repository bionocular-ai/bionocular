/**
 * The provider/model boundary. Everything provider-specific lives here: which
 * SDK provider is constructed, the model id, its pricing, and the provider
 * options (thinking configuration) sent with every call. Nothing outside this
 * file names a provider or a model id.
 *
 * `MODELS` holds every model the agent can be run on, so the evals can pit
 * them against each other with the same tools, prompt and cases. The model
 * the route serves is `AGENT_MODEL_NAME`, overridable per deployment with the
 * `AGENT_MODEL` environment variable so a rollback is a config change.
 */

import { createAnthropic } from '@ai-sdk/anthropic';
import type { LanguageModel, ToolLoopAgentSettings } from 'ai';

export interface AgentModelSpec {
  /** Short name used in run records, eval reports and `AGENT_MODEL`. */
  name: string;
  provider: string;
  id: string;
  /** USD per million tokens, for the cost estimate on every run record. */
  pricing: { inputPer1M: number; outputPer1M: number };
  /** Sent with every call; the one place model-specific behaviour is set. */
  providerOptions?: ToolLoopAgentSettings['providerOptions'];
  create(): LanguageModel;
}

/**
 * Haiku 4.5 supports extended thinking but leaves it off unless asked, and
 * `@ai-sdk/anthropic` builds the `thinking` field only for `enabled` and
 * `adaptive`, dropping `disabled` on the floor. So "off" has to go on the wire
 * by hand: without it the request carries no `thinking` field at all, which is
 * model-default rather than a stated choice, and on Sonnet 5 that default ate
 * the whole output budget on a large tool result.
 */
const ANTHROPIC_THINKING = { type: 'disabled' } as const;

const anthropic = createAnthropic({
  fetch: async (input, init) => {
    if (typeof init?.body !== 'string') return fetch(input, init);
    const body = JSON.parse(init.body) as Record<string, unknown>;
    body.thinking = ANTHROPIC_THINKING;
    return fetch(input, { ...init, body: JSON.stringify(body) });
  },
});

export const MODELS: Record<string, AgentModelSpec> = {
  'haiku-4.5': {
    name: 'haiku-4.5',
    provider: 'anthropic',
    id: 'claude-haiku-4-5-20251001',
    pricing: { inputPer1M: 1, outputPer1M: 5 },
    create: () => anthropic('claude-haiku-4-5-20251001'),
  },
};

export const DEFAULT_MODEL_NAME = 'haiku-4.5';

export function resolveModel(name: string = process.env.AGENT_MODEL ?? DEFAULT_MODEL_NAME): AgentModelSpec {
  const spec = MODELS[name];
  if (!spec) throw new Error(`Unknown agent model ${JSON.stringify(name)}; known: ${Object.keys(MODELS).join(', ')}`);
  return spec;
}

/** USD for one run, from the provider's reported token counts. */
export function estimateCostUsd(
  usage: { inputTokens?: number; outputTokens?: number } | undefined,
  spec: AgentModelSpec,
): number | undefined {
  if (!usage) return undefined;
  const input = usage.inputTokens ?? 0;
  const output = usage.outputTokens ?? 0;
  return (input * spec.pricing.inputPer1M + output * spec.pricing.outputPer1M) / 1_000_000;
}
