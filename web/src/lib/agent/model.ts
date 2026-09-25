/**
 * The provider/model boundary. Everything provider-specific lives here: which
 * SDK provider is constructed, the model id, its pricing, and the provider
 * options (thinking configuration) sent with every call. Nothing outside this
 * file names a provider or a model id.
 *
 * `MODELS` holds every model the agent can be run on, so the evals can pit
 * them against each other with the same tools, prompt and cases. The model
 * the route serves is `DEFAULT_MODEL_NAME`, overridable per deployment with
 * the `AGENT_MODEL` environment variable so a rollback is a config change.
 */

import { createAnthropic } from '@ai-sdk/anthropic';
import { createVertex } from '@ai-sdk/google-vertex';
import type { ToolLoopAgentSettings, wrapLanguageModel } from 'ai';

/** A provider's model object, as `wrapLanguageModel` takes it. */
export type ProviderModel = Parameters<typeof wrapLanguageModel>[0]['model'];

export interface AgentModelSpec {
  /** Short name used in run records, eval reports and `AGENT_MODEL`. */
  name: string;
  provider: string;
  id: string;
  /** USD per million tokens, for the cost estimate on every run record. */
  pricing: { inputPer1M: number; outputPer1M: number };
  /** Sent with every call; the one place model-specific behaviour is set. */
  providerOptions?: ToolLoopAgentSettings['providerOptions'];
  /**
   * The Vertex shared-pool lane this spec asks for; absent for a provider
   * without lanes. Asked, not granted - each model-call record carries the
   * lane Vertex reports it used.
   */
  trafficType?: 'standard' | 'flex' | 'priority';
  create(): ProviderModel;
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

/**
 * Gemini on Vertex AI, the same endpoint the extraction pipeline uses:
 * Application Default Credentials locally, a service-account key in
 * `GOOGLE_VERTEX_CREDENTIALS_JSON` where there is no gcloud login (Render).
 * `GOOGLE_VERTEX_PROJECT` names the project; the location is `global`.
 */
function vertex(headers?: Record<string, string>) {
  const credentials = process.env.GOOGLE_VERTEX_CREDENTIALS_JSON;
  return createVertex({
    location: process.env.GOOGLE_VERTEX_LOCATION ?? 'global',
    headers,
    ...(credentials ? { googleAuthOptions: { credentials: JSON.parse(credentials) } } : {}),
  });
}

export const MODELS: Record<string, AgentModelSpec> = {
  'gemini-3.8-flash': {
    name: 'gemini-3.8-flash',
    provider: 'google-vertex',
    id: 'gemini-3.8-flash',
    pricing: { inputPer1M: 0.75, outputPer1M: 3.75 },
    // Gemini 3 models take a thinking level rather than a token budget. `low`
    // is enough for choosing a filter and reading a coverage report, and it
    // keeps thinking from eating the shared output cap the way an unstated
    // default once did. Thoughts are not returned: nothing renders them.
    providerOptions: {
      google: { thinkingConfig: { thinkingLevel: 'low', includeThoughts: false } },
    },
    trafficType: 'standard',
    create: () => vertex()('gemini-3.8-flash'),
  },
  'haiku-4.5': {
    name: 'haiku-4.5',
    provider: 'anthropic',
    id: 'claude-haiku-4-5-20251001',
    pricing: { inputPer1M: 1, outputPer1M: 5 },
    create: () => anthropic('claude-haiku-4-5-20251001'),
  },
};

/**
 * How long Vertex may hold a Flex request in its queue before answering 504.
 * Its default is about ten minutes, but Node's fetch gives up waiting for
 * response headers at five, and a client-side timeout cannot be told apart
 * from a network fault. Under five, the refusal comes back as a 504 the
 * retry layer recognises.
 */
const FLEX_SERVER_TIMEOUT_S = 240;

/**
 * The same model on Vertex's Flex lane: half the price, queued rather than
 * refused when the shared pool is contended, and slower - seconds to minutes
 * per call. For latency-tolerant work only (the evals), never the chat route.
 * `requestType: 'shared'` keeps it off Provisioned Throughput, which this
 * project does not have. A provider without lanes comes back unchanged.
 */
export function onFlexLane(spec: AgentModelSpec): AgentModelSpec {
  if (spec.provider !== 'google-vertex') return spec;
  return {
    ...spec,
    pricing: { inputPer1M: spec.pricing.inputPer1M / 2, outputPer1M: spec.pricing.outputPer1M / 2 },
    trafficType: 'flex',
    providerOptions: {
      ...spec.providerOptions,
      google: { ...spec.providerOptions?.google, requestType: 'shared', sharedRequestType: 'flex' },
    },
    create: () => vertex({ 'X-Server-Timeout': String(FLEX_SERVER_TIMEOUT_S) })(spec.id),
  };
}

export const DEFAULT_MODEL_NAME = 'gemini-3.8-flash';

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
