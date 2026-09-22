/**
 * Runs one golden case against one model and classifies what went wrong.
 *
 * The classification is the point: a failed case names which layer failed -
 * retrieval, tool selection, filter selection, evidence, reasoning,
 * grounding, presentation - because the fix for each is different, and "the
 * model was wrong" is not a diagnosis. Every check is a deterministic
 * assertion on tool calls, tool results or the answer; none compares text to
 * an expected answer.
 */

import { createAgent, mentionsNct } from '../agent';
import { checkGroundedness, NCT_ID_SOURCE } from '../groundedness';
import { estimateCostUsd, type AgentModelSpec } from '../model';
import { buildInstructions, PROMPT_VERSION } from '../prompts';
import { buildAgentTools } from '../tools';
import { getDbCancerType } from '@/lib/api';
import { ABSENCE, PARTIAL, type EvalCase, type ExpectedFilter } from './cases';

export type FailureKind =
  | 'retrieval'
  | 'tool-selection'
  | 'filter-selection'
  | 'incomplete-evidence'
  | 'reasoning'
  | 'grounding'
  | 'presentation';

export interface Failure {
  kind: FailureKind;
  detail: string;
}

export interface ToolCallSummary {
  tool: string;
  input: unknown;
  outcome: string;
  rows?: number;
  matched?: number;
  complete?: boolean;
}

export interface CaseResult {
  id: string;
  category: EvalCase['category'];
  model: string;
  promptVersion: string;
  passed: boolean;
  failures: Failure[];
  metrics: {
    steps: number;
    toolCalls: number;
    latencyMs: number;
    inputTokens?: number;
    outputTokens?: number;
    costUsd?: number;
  };
  toolCalls: ToolCallSummary[];
  skillsLoaded: string[];
  answer: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function summariseCall(tool: string, input: unknown, output: unknown): ToolCallSummary {
  const out = isRecord(output) ? output : {};
  const coverage = isRecord(out.coverage) ? out.coverage : {};
  const rows = Array.isArray(out.rows)
    ? out.rows.length
    : isRecord(out.tables)
      ? Object.values(out.tables).reduce<number>(
          (n, hit) => n + (isRecord(hit) && Array.isArray(hit.rows) ? hit.rows.length : 0),
          0,
        )
      : undefined;
  return {
    tool,
    input,
    outcome: out.ok === false || out.found === false ? String(out.reason ?? 'not_ok') : 'ok',
    rows,
    matched: typeof coverage.matched === 'number' ? coverage.matched : undefined,
    complete: typeof coverage.complete === 'boolean' ? coverage.complete : undefined,
  };
}

function argMatches(actual: unknown, expected: string | RegExp | string[]): boolean {
  if (Array.isArray(expected)) {
    return Array.isArray(actual) && expected.every((v) => actual.includes(v));
  }
  const values = Array.isArray(actual) ? actual : [actual];
  return values.some((v) =>
    typeof v === 'string' && (expected instanceof RegExp ? expected.test(v) : v === expected),
  );
}

export function callMatches(call: ToolCallSummary, filter: ExpectedFilter): boolean {
  if (call.tool !== 'query_proprietary_data') return false;
  const input = isRecord(call.input) ? call.input : {};
  if (filter.table && input.table !== filter.table) return false;
  for (const [key, expected] of Object.entries(filter.args ?? {})) {
    if (!argMatches(input[key], expected)) return false;
  }
  return true;
}

function describeFilter(filter: ExpectedFilter): string {
  return JSON.stringify({ ...filter, args: filter.args && Object.fromEntries(Object.entries(filter.args).map(([k, v]) => [k, String(v)])) });
}

/** Lines that are GFM table rows, minus the header separator. */
function tableRowCount(answer: string): number {
  return answer.split('\n').filter((line) => /^\s*\|.*\|\s*$/.test(line) && !/^\s*\|[\s:-]+\|/.test(line)).length;
}

/** Rows reproduced in prose defeats the app-drawn table; a short comparison does not. */
const MAX_TABLE_ROWS = 5;

export interface Observed {
  calls: ToolCallSummary[];
  /** Raw tool outputs, in call order. */
  outputs: unknown[];
  skillsLoaded: string[];
  answer: string;
  ungrounded: string[];
  fastPath: 'lookup_trial' | null;
}

/** Whether a lookup found the trial but no outcome rows for it. */
function lookupLacksOutcomes(output: unknown): boolean {
  if (!isRecord(output) || output.found !== true) return false;
  const coverage = isRecord(output.coverage) ? output.coverage : {};
  return Array.isArray(coverage.absentFrom) && coverage.absentFrom.includes('trial_outcomes');
}

export function classify(c: EvalCase, observed: Observed): Failure[] {
  const failures: Failure[] = [];
  const { calls, answer } = observed;
  const e = c.expect;
  const dataCalls = calls.filter((x) => x.tool === 'query_proprietary_data' || x.tool === 'lookup_trial');

  // 1. Retrieval: the tool layer itself failed.
  for (const call of dataCalls) {
    if (['query_failed', 'unknown_column', 'threw'].includes(call.outcome)) {
      failures.push({ kind: 'retrieval', detail: `${call.tool} returned ${call.outcome}` });
    }
  }

  // 2. Tool selection.
  const used = new Set(calls.map((x) => x.tool));
  for (const tool of e.tools ?? []) {
    if (!used.has(tool)) failures.push({ kind: 'tool-selection', detail: `expected ${tool} to be called` });
  }
  for (const tool of e.forbidTools ?? []) {
    if (used.has(tool)) failures.push({ kind: 'tool-selection', detail: `${tool} must not be called` });
  }
  if (e.fastPath && observed.fastPath !== e.fastPath) {
    failures.push({ kind: 'tool-selection', detail: `fast path ${e.fastPath} not taken` });
  }
  if (e.maxToolCalls !== undefined && calls.length > e.maxToolCalls) {
    failures.push({ kind: 'tool-selection', detail: `${calls.length} tool calls, max ${e.maxToolCalls}` });
  }
  const seen = new Set<string>();
  for (const call of calls) {
    const key = `${call.tool}:${JSON.stringify(call.input)}`;
    if (seen.has(key)) failures.push({ kind: 'tool-selection', detail: `repeated identical call ${key}` });
    seen.add(key);
  }
  for (const skill of e.skills ?? []) {
    if (!observed.skillsLoaded.includes(skill)) {
      failures.push({ kind: 'tool-selection', detail: `skill ${skill} not loaded` });
    }
  }

  // 3. Filter selection.
  if (e.filter && !calls.some((call) => callMatches(call, e.filter!))) {
    failures.push({ kind: 'filter-selection', detail: `no query matched ${describeFilter(e.filter)}` });
  }
  if (e.forbidFilter && calls.some((call) => callMatches(call, e.forbidFilter!))) {
    failures.push({ kind: 'filter-selection', detail: `a query matched forbidden ${describeFilter(e.forbidFilter)}` });
  }
  for (const call of dataCalls) {
    if (call.outcome === 'unsupported_filter' || call.outcome === 'unfiltered_sweep') {
      failures.push({ kind: 'filter-selection', detail: `${call.tool} refused: ${call.outcome}` });
    }
  }

  // 4. Incomplete evidence: a partial result presented as whole, or a count
  //    that does not match what the tool returned.
  const firstOk = calls.find((x) => x.tool === 'query_proprietary_data' && x.outcome === 'ok');
  if (e.countAwareness && firstOk) {
    // "1,056" and "1056" are the same claim - the group separator is
    // presentation, and every count over a thousand carries one.
    const statesMatched =
      firstOk.matched !== undefined &&
      new RegExp(`\\b${firstOk.matched}\\b`).test(answer.replace(/(\d),(?=\d{3}\b)/g, '$1'));
    // A truncated row set only misleads when the answer rests on the rows. An
    // answer that states the matched count has not passed a subset off as the
    // whole, and for a count question that number is the entire answer -
    // `complete` is `rows === matched`, so a 1,056-row match can never be true.
    if (firstOk.complete === false && !PARTIAL.test(answer) && !statesMatched) {
      failures.push({ kind: 'incomplete-evidence', detail: `result was partial (${firstOk.rows} of ${firstOk.matched}) and the answer does not say so` });
    }
    if (firstOk.complete === true && firstOk.matched !== undefined && !statesMatched) {
      failures.push({ kind: 'incomplete-evidence', detail: `answer never states the matched count ${firstOk.matched}` });
    }
  }
  if (e.absenceIfNoOutcomes && observed.outputs.some(lookupLacksOutcomes) && !ABSENCE.test(answer)) {
    failures.push({ kind: 'incomplete-evidence', detail: 'lookup found no outcome rows but the answer does not say so' });
  }

  // 5. Reasoning: what the answer says.
  if (e.answer && !e.answer.test(answer)) {
    failures.push({ kind: 'reasoning', detail: `answer does not match ${e.answer}` });
  }
  if (e.answerNot && e.answerNot.test(answer)) {
    failures.push({ kind: 'reasoning', detail: `answer matches forbidden ${e.answerNot}` });
  }
  if (e.minNctIds !== undefined) {
    const ids = new Set(answer.match(new RegExp(NCT_ID_SOURCE, 'g')) ?? []);
    if (ids.size < e.minNctIds) {
      failures.push({ kind: 'reasoning', detail: `answer names ${ids.size} NCT numbers, expected ${e.minNctIds}` });
    }
  }
  if (!answer.trim()) failures.push({ kind: 'reasoning', detail: 'empty answer' });

  // 6. Grounding.
  if (observed.ungrounded.length > 0) {
    failures.push({ kind: 'grounding', detail: `ungrounded identifiers: ${observed.ungrounded.join(', ')}` });
  }

  // 7. Presentation: rows reproduced as a table.
  const rows = tableRowCount(answer);
  if (rows > MAX_TABLE_ROWS) {
    failures.push({ kind: 'presentation', detail: `answer reproduces ${rows} table rows; the app draws the rows` });
  }

  return failures;
}

export async function runCase(c: EvalCase, model: AgentModelSpec, userId = '00000000-0000-0000-0000-000000000000'): Promise<CaseResult> {
  const { tools, turn } = buildAgentTools({ userId, cancerSlug: c.cancerSlug, traceId: `eval-${c.id}` });
  const fastPath = mentionsNct(c.question) ? ('lookup_trial' as const) : null;
  const agent = createAgent({
    instructions: buildInstructions({ cancerType: getDbCancerType(c.cancerSlug) }),
    tools,
    model,
    forceLookupFirst: fastPath === 'lookup_trial',
  });

  const startedAt = Date.now();
  const result = await agent.generate({ prompt: c.question });
  const latencyMs = Date.now() - startedAt;

  const calls: ToolCallSummary[] = [];
  const outputs: unknown[] = [];
  for (const step of result.steps) {
    for (const call of step.toolCalls) {
      const res = step.toolResults.find((r) => r.toolCallId === call.toolCallId);
      outputs.push(res?.output);
      calls.push(summariseCall(call.toolName, call.input, res?.output));
    }
  }
  const grounding = checkGroundedness(result.text, [outputs, [...turn.evidence]]);

  const observed: Observed = {
    calls,
    outputs,
    skillsLoaded: [...turn.skillsLoaded],
    answer: result.text,
    ungrounded: grounding.ungrounded,
    fastPath,
  };
  const failures = classify(c, observed);

  return {
    id: c.id,
    category: c.category,
    model: model.name,
    promptVersion: PROMPT_VERSION,
    passed: failures.length === 0,
    failures,
    metrics: {
      steps: result.steps.length,
      toolCalls: calls.length,
      latencyMs,
      inputTokens: result.totalUsage.inputTokens,
      outputTokens: result.totalUsage.outputTokens,
      costUsd: estimateCostUsd(result.totalUsage, model),
    },
    toolCalls: calls,
    skillsLoaded: observed.skillsLoaded,
    answer: result.text,
  };
}

export interface ModelSummary {
  model: string;
  promptVersion: string;
  cases: number;
  passed: number;
  failuresByKind: Record<FailureKind, number>;
  totals: { toolCalls: number; steps: number; latencyMs: number; inputTokens: number; outputTokens: number; costUsd: number };
  medianLatencyMs: number;
}

export function summarise(results: CaseResult[]): ModelSummary {
  const failuresByKind: Record<FailureKind, number> = {
    retrieval: 0,
    'tool-selection': 0,
    'filter-selection': 0,
    'incomplete-evidence': 0,
    reasoning: 0,
    grounding: 0,
    presentation: 0,
  };
  for (const r of results) for (const f of r.failures) failuresByKind[f.kind] += 1;
  const latencies = results.map((r) => r.metrics.latencyMs).sort((a, b) => a - b);
  return {
    model: results[0]?.model ?? '',
    promptVersion: results[0]?.promptVersion ?? '',
    cases: results.length,
    passed: results.filter((r) => r.passed).length,
    failuresByKind,
    totals: {
      toolCalls: results.reduce((n, r) => n + r.metrics.toolCalls, 0),
      steps: results.reduce((n, r) => n + r.metrics.steps, 0),
      latencyMs: results.reduce((n, r) => n + r.metrics.latencyMs, 0),
      inputTokens: results.reduce((n, r) => n + (r.metrics.inputTokens ?? 0), 0),
      outputTokens: results.reduce((n, r) => n + (r.metrics.outputTokens ?? 0), 0),
      costUsd: results.reduce((n, r) => n + (r.metrics.costUsd ?? 0), 0),
    },
    medianLatencyMs: latencies[Math.floor(latencies.length / 2)] ?? 0,
  };
}
