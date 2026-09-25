/**
 * The record of one agent run: what model ran, how many steps, which tools,
 * what they returned, what it cost, and whether the answer grounded.
 *
 * Built once per turn from the step results and the turn state, logged as a
 * single line, and stored on the session row. It is deliberately compact: no
 * prompt text, no rows, no answer text - those are in the transcript and in
 * the OpenTelemetry spans when an exporter is configured.
 */

import type { GroundednessResult } from './groundedness';
import { estimateCostUsd, type AgentModelSpec } from './model';
import type { ModelCallRecord } from './model-calls';
import type { ToolCallRecord, TurnState } from './tools/turn';

export interface AgentRunRecord {
  traceId: string;
  sessionId?: string;
  cancerType: string;
  model: { name: string; provider: string; id: string };
  promptVersion: string;
  /** How the turn was routed: straight to a lookup, or the full loop. */
  fastPath: 'lookup_trial' | null;
  steps: number;
  /** Per-step token usage, oldest first. */
  stepUsage: Array<{ input?: number; output?: number }>;
  finishReason?: string;
  usage: { input?: number; output?: number; total?: number; cached?: number; reasoning?: number };
  costUsd?: number;
  latencyMs: number;
  firstTokenMs?: number;
  toolCalls: ToolCallRecord[];
  /** Every model call: the lane asked for and the lane Vertex used, retries, refusals. */
  modelCalls: ModelCallRecord[];
  skillsLoaded: string[];
  budget: { spentChars: number; limitChars: number; exhausted: boolean };
  grounding?: { cited: number; ungrounded: string[] };
  status: 'ok' | 'error';
  error?: string;
  startedAt: string;
}

/** The counters every provider reports; the rest of `LanguageModelUsage` is provider detail. */
export interface UsageCounts {
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  cachedInputTokens?: number;
  reasoningTokens?: number;
}

export interface BuildRunRecordArgs {
  traceId: string;
  sessionId?: string;
  cancerType: string;
  model: AgentModelSpec;
  promptVersion: string;
  fastPath: 'lookup_trial' | null;
  steps: ReadonlyArray<{ usage: UsageCounts }>;
  finishReason?: string;
  totalUsage?: UsageCounts;
  turn: TurnState;
  grounding?: GroundednessResult;
  startedAt: number;
  firstTokenAt?: number;
  finishedAt: number;
  modelCalls?: ModelCallRecord[];
  error?: unknown;
}

export function buildRunRecord({
  traceId,
  sessionId,
  cancerType,
  model,
  promptVersion,
  fastPath,
  steps,
  finishReason,
  totalUsage,
  turn,
  grounding,
  startedAt,
  firstTokenAt,
  finishedAt,
  modelCalls = [],
  error,
}: BuildRunRecordArgs): AgentRunRecord {
  const spent = turn.spentChars();
  return {
    traceId,
    sessionId,
    cancerType,
    model: { name: model.name, provider: model.provider, id: model.id },
    promptVersion,
    fastPath,
    steps: steps.length,
    stepUsage: steps.map((s) => ({ input: s.usage.inputTokens, output: s.usage.outputTokens })),
    finishReason,
    usage: {
      input: totalUsage?.inputTokens,
      output: totalUsage?.outputTokens,
      total: totalUsage?.totalTokens,
      cached: totalUsage?.cachedInputTokens,
      reasoning: totalUsage?.reasoningTokens,
    },
    costUsd: estimateCostUsd(totalUsage, model),
    latencyMs: finishedAt - startedAt,
    firstTokenMs: firstTokenAt === undefined ? undefined : firstTokenAt - startedAt,
    toolCalls: turn.toolCalls,
    modelCalls,
    skillsLoaded: [...turn.skillsLoaded],
    budget: {
      spentChars: spent,
      limitChars: turn.limitChars,
      exhausted: turn.toolCalls.some((c) => c.outcome === 'turn_budget_exhausted'),
    },
    grounding: grounding && { cited: grounding.cited.length, ungrounded: grounding.ungrounded },
    status: error === undefined ? 'ok' : 'error',
    error: error === undefined ? undefined : error instanceof Error ? error.message : String(error),
    startedAt: new Date(startedAt).toISOString(),
  };
}

/** One structured line per run; the same shape the session row stores. */
export function logRun(record: AgentRunRecord): void {
  console.info('agent run', record);
}
