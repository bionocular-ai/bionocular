import { describe, expect, it, vi } from 'vitest';
import { GOLDEN_CASES, type EvalCase } from './cases';

// The classifier is pure, but the module also exports the runner, whose
// imports reach the service client and its env check.
vi.mock('@/lib/supabase/service', () => ({ createServiceClient: () => ({}) }));
const { classify, summarise } = await import('./harness');
type Observed = import('./harness').Observed;
type CaseResult = import('./harness').CaseResult;
type ModelCallRecord = import('../model-calls').ModelCallRecord;

const byId = (id: string): EvalCase => GOLDEN_CASES.find((c) => c.id === id)!;

function observed(over: Partial<Observed> = {}): Observed {
  return { calls: [], outputs: [], skillsLoaded: [], answer: 'An answer.', ungrounded: [], fastPath: null, ...over };
}

const okQuery = (input: Record<string, unknown>, matched = 3, complete = true) => ({
  tool: 'query_proprietary_data',
  input,
  outcome: 'ok',
  rows: complete ? matched : 1,
  matched,
  complete,
});

describe('classify', () => {
  it('passes a clean run', () => {
    const c = byId('phase-filter');
    const failures = classify(
      c,
      observed({ calls: [okQuery({ table: 'clinical_trials', phase: 'PHASE3', limit: 500 }, 184)], answer: '184 Phase 3 trials ...' }),
    );
    expect(failures).toEqual([]);
  });

  it('names a tool failure as retrieval, not reasoning', () => {
    const failures = classify(
      byId('phase-filter'),
      observed({ calls: [{ tool: 'query_proprietary_data', input: { table: 'clinical_trials', phase: 'PHASE3' }, outcome: 'query_failed' }] }),
    );
    expect(failures.map((f) => f.kind)).toContain('retrieval');
  });

  it('names a wrong filter as filter-selection', () => {
    const failures = classify(
      byId('funding-not-sponsor'),
      observed({ calls: [okQuery({ table: 'clinical_trials', sponsor: 'industry' })], answer: '3 trials' }),
    );
    expect(failures.map((f) => f.kind)).toEqual(['filter-selection', 'filter-selection']);
  });

  it('names a partial result presented as whole as incomplete-evidence', () => {
    const failures = classify(
      byId('phase-filter'),
      observed({ calls: [okQuery({ table: 'clinical_trials', phase: 'PHASE3' }, 184, false)], answer: 'Here are the Phase 3 trials.' }),
    );
    expect(failures).toEqual([{ kind: 'incomplete-evidence', detail: expect.stringMatching(/partial/) }]);
  });

  it('accepts a truncated result whose answer states the matched count', () => {
    // A count question: the rows were never the evidence, so "1,056 matched"
    // is the whole answer and nothing about it is partial.
    const failures = classify(
      byId('funding-not-sponsor'),
      observed({
        calls: [okQuery({ table: 'clinical_trials', funding: 'industry' }, 1056, false)],
        answer: 'There are **1,056** industry-sponsored trials.',
      }),
    );
    expect(failures).toEqual([]);
  });

  it('reads a thousands separator in a stated count', () => {
    const failures = classify(
      byId('phase-filter'),
      observed({ calls: [okQuery({ table: 'clinical_trials', phase: 'PHASE3' }, 1184)], answer: 'There are 1,184 Phase 3 trials.' }),
    );
    expect(failures).toEqual([]);
  });

  it('names a stated count that disagrees with the tool as incomplete-evidence', () => {
    const failures = classify(
      byId('phase-filter'),
      observed({ calls: [okQuery({ table: 'clinical_trials', phase: 'PHASE3' }, 184)], answer: 'There are 53 Phase 3 trials.' }),
    );
    expect(failures.map((f) => f.kind)).toEqual(['incomplete-evidence']);
  });

  it('names a missing refusal as reasoning', () => {
    const failures = classify(byId('out-of-scope-cancer'), observed({ answer: 'Pancreatic cancer trials include ...' }));
    expect(failures.map((f) => f.kind)).toEqual(['reasoning']);
  });

  it('names an unsupported identifier as grounding', () => {
    const failures = classify(
      byId('nct-lookup'),
      observed({ calls: [{ tool: 'lookup_trial', input: { nctId: 'NCT00006368' }, outcome: 'ok' }], fastPath: 'lookup_trial', ungrounded: ['NCT11111111'] }),
    );
    expect(failures).toEqual([{ kind: 'grounding', detail: 'ungrounded identifiers: NCT11111111' }]);
  });

  it('names a reproduced row table as presentation', () => {
    const table = ['| NCT | Title |', '|---|---|', ...Array.from({ length: 8 }, (_, i) => `| NCT0000000${i} | t |`)].join('\n');
    const failures = classify(
      byId('phase-filter'),
      observed({ calls: [okQuery({ table: 'clinical_trials', phase: 'PHASE3' }, 8)], answer: `8 trials:\n${table}` }),
    );
    expect(failures.map((f) => f.kind)).toEqual(['presentation']);
  });

  it('flags a repeated identical call, a skipped fast path, and a missing skill as tool-selection', () => {
    const call = { tool: 'query_proprietary_data', input: { table: 'trial_outcomes', drug: 'relatlimab' }, outcome: 'ok' as const };
    const failures = classify(byId('efficacy-endpoints'), observed({ calls: [call, { ...call }] }));
    expect(failures.map((f) => f.detail)).toEqual([
      expect.stringMatching(/repeated identical call/),
      'skill trial-outcomes not loaded',
    ]);
    const skipped = classify(byId('nct-lookup'), observed({ calls: [{ tool: 'lookup_trial', input: {}, outcome: 'ok' }] }));
    expect(skipped.map((f) => f.detail)).toEqual(['fast path lookup_trial not taken']);
  });

  it('requires the answer to admit a lookup found no outcomes', () => {
    const output = { found: true, nctId: 'NCT00006368', coverage: { presentIn: ['clinical_trials'], absentFrom: ['trial_outcomes'] } };
    const base = { calls: [{ tool: 'lookup_trial', input: { nctId: 'NCT00006368' }, outcome: 'ok' }], outputs: [output], fastPath: 'lookup_trial' as const };
    expect(classify(byId('missing-evidence'), observed({ ...base, answer: 'Median OS was 14 months.' })).map((f) => f.kind)).toEqual(['incomplete-evidence']);
    expect(classify(byId('missing-evidence'), observed({ ...base, answer: 'No outcome data is reported for NCT00006368.' }))).toEqual([]);
  });
});

describe('summarise', () => {
  const call = (over: Partial<ModelCallRecord> = {}): ModelCallRecord => ({
    model: 'm',
    requestedTrafficType: 'flex',
    actualTrafficType: 'ON_DEMAND_FLEX',
    status: 'ok',
    retryCount: 0,
    latencyMs: 1,
    timestamp: '2026-09-25T00:00:00.000Z',
    ...over,
  });
  const result = (over: Partial<CaseResult>): CaseResult => ({
    id: 'x', category: 'retrieval', model: 'm', promptVersion: 'v', status: 'completed', passed: true, failures: [],
    metrics: { steps: 0, toolCalls: 0, latencyMs: 0 }, toolCalls: [], skillsLoaded: [], answer: '', modelCalls: [], ...over,
  });

  it('counts passes and failures by kind and totals the metrics', () => {
    const results: CaseResult[] = [
      result({ id: 'a', metrics: { steps: 2, toolCalls: 1, latencyMs: 100, inputTokens: 10, outputTokens: 5, costUsd: 0.01 } }),
      result({ id: 'b', category: 'grounding', passed: false, failures: [{ kind: 'grounding', detail: 'x' }], metrics: { steps: 3, toolCalls: 2, latencyMs: 300, inputTokens: 20, outputTokens: 5, costUsd: 0.02 } }),
    ];
    const s = summarise(results);
    expect(s).toMatchObject({ cases: 2, passed: 1, rateLimited: 0, medianLatencyMs: 300, totals: { toolCalls: 3, steps: 5, latencyMs: 400, inputTokens: 30, outputTokens: 10 } });
    expect(s.failuresByKind.grounding).toBe(1);
    expect(s.totals.costUsd).toBeCloseTo(0.03);
  });

  it('keeps rate-limited cases out of the pass rate and counts calls by lane asked and lane served', () => {
    const s = summarise([
      result({ id: 'a', modelCalls: [call(), call({ retryCount: 1 })] }),
      result({
        id: 'b',
        status: 'rate_limited',
        passed: false,
        modelCalls: [call({ actualTrafficType: null, status: 'rate_limited', retryCount: 2 })],
      }),
    ]);
    expect(s).toMatchObject({ cases: 1, passed: 1, rateLimited: 1 });
    expect(s.modelCalls).toEqual({
      total: 3,
      retries: 3,
      rateLimited: 1,
      trafficTypes: { 'flex -> ON_DEMAND_FLEX': 2, 'flex -> rate_limited': 1 },
    });
  });
});
