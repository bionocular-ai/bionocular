import { describe, expect, it } from 'vitest';
import type { UIMessage } from 'ai';
import { pruneHistory, stubOutput } from './context';

const ROWS = [
  { nct_id: 'NCT00000001', brief_title: 'A' },
  { nct_id: 'NCT00000002', brief_title: 'B', abstract_id: 'ASCO_1' },
];

function queryPart(output: unknown, state = 'output-available') {
  return { type: 'tool-query_proprietary_data', toolCallId: 'c1', state, input: { table: 'clinical_trials' }, output };
}

const QUERY_OUTPUT = { ok: true, table: 'clinical_trials', coverage: { matched: 2, returned: 2, complete: true }, rows: ROWS };

function transcript(): UIMessage[] {
  return [
    { id: 'u1', role: 'user', parts: [{ type: 'text', text: 'Phase 3 trials?' }] },
    {
      id: 'a1',
      role: 'assistant',
      parts: [queryPart(QUERY_OUTPUT), { type: 'text', text: 'Two trials: NCT00000001 and NCT00000002.' }],
    } as UIMessage,
    { id: 'u2', role: 'user', parts: [{ type: 'text', text: 'And their outcomes?' }] },
  ];
}

describe('pruneHistory', () => {
  it('replaces an earlier turn\'s rows with a stub that keeps coverage and identifiers', () => {
    const { messages, retainedEvidence } = pruneHistory(transcript());

    const part = messages[1].parts[0] as { output: Record<string, unknown> };
    expect(part.output.rows).toBeUndefined();
    expect(part.output).toMatchObject({
      ok: true,
      table: 'clinical_trials',
      coverage: { matched: 2, returned: 2, complete: true },
      pruned: true,
      rowCount: 2,
      identifiers: ['NCT00000001', 'NCT00000002', 'ASCO_1'],
    });
    expect(retainedEvidence).toEqual(['NCT00000001', 'NCT00000002', 'ASCO_1']);
  });

  it('leaves user text, assistant text and tool inputs untouched', () => {
    const { messages } = pruneHistory(transcript());
    expect(messages[0]).toEqual(transcript()[0]);
    expect(messages[1].parts[1]).toEqual({ type: 'text', text: 'Two trials: NCT00000001 and NCT00000002.' });
    expect((messages[1].parts[0] as { input: unknown }).input).toEqual({ table: 'clinical_trials' });
  });

  it('never prunes the current turn', () => {
    const current: UIMessage[] = [
      ...transcript(),
      { id: 'a2', role: 'assistant', parts: [queryPart(QUERY_OUTPUT)] } as UIMessage,
    ];
    const { messages } = pruneHistory(current);
    expect((messages[3].parts[0] as { output: typeof QUERY_OUTPUT }).output.rows).toEqual(ROWS);
  });

  it('keeps load_skill output, refusals and misses as they were', () => {
    const skill = { type: 'tool-load_skill', toolCallId: 'c2', state: 'output-available', output: { ok: true, content: 'method' } };
    const miss = { type: 'tool-lookup_trial', toolCallId: 'c3', state: 'output-available', output: { found: false, nctId: 'NCT99999999' } };
    const refusal = queryPart({ ok: false, reason: 'no_rows', coverage: { matched: 0 } });
    const messages: UIMessage[] = [
      { id: 'u1', role: 'user', parts: [{ type: 'text', text: 'x' }] },
      { id: 'a1', role: 'assistant', parts: [skill, miss, refusal] } as UIMessage,
      { id: 'u2', role: 'user', parts: [{ type: 'text', text: 'y' }] },
    ];
    const { messages: pruned } = pruneHistory(messages);
    expect(pruned[1].parts).toEqual([skill, miss, refusal]);
  });

  it('stubs a lookup by table, keeping which tables held the trial', () => {
    const output = {
      found: true,
      nctId: 'NCT00000001',
      coverage: { presentIn: ['clinical_trials', 'trial_outcomes'], absentFrom: [] },
      tables: {
        clinical_trials: { matched: 1, rows: [{ nct_id: 'NCT00000001' }] },
        trial_outcomes: { matched: 2, rows: [{ id: 'o1', nct_id: 'NCT00000001' }, { id: 'o2', nct_id: 'NCT00000001' }] },
        news_feed: null,
      },
    };
    const stub = stubOutput(output) as Record<string, unknown>;
    expect(stub).toMatchObject({ found: true, nctId: 'NCT00000001', pruned: true, rowCount: 3 });
    expect((stub.tables as Record<string, { rowCount?: number; rows?: unknown }>).trial_outcomes).toMatchObject({ matched: 2, rowCount: 2 });
    expect((stub.tables as Record<string, { rows?: unknown }>).trial_outcomes.rows).toBeUndefined();
    expect(stub.identifiers).toEqual(['NCT00000001', 'o1', 'o2']);
  });
});
