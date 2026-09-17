import { describe, expect, it } from 'vitest';
import { buildRunRecord } from './run';
import { MODELS } from './model';
import { createTurnState } from './tools/turn';

describe('buildRunRecord', () => {
  it('summarises a turn: model, steps, tools, usage, cost, budget, grounding', () => {
    const turn = createTurnState({ limitChars: 1000 });
    turn.spend(400);
    turn.toolCalls.push({ tool: 'query_proprietary_data', outcome: 'ok', ms: 120, chars: 400, rows: 3, matched: 3 });
    turn.skillsLoaded.add('trial-outcomes');

    const record = buildRunRecord({
      traceId: 't',
      sessionId: 's',
      cancerType: 'cutaneous-melanoma',
      model: MODELS['haiku-4.5'],
      promptVersion: 'v',
      fastPath: null,
      steps: [
        { usage: { inputTokens: 1000, outputTokens: 50, totalTokens: 1050 } },
        { usage: { inputTokens: 2000, outputTokens: 300, totalTokens: 2300 } },
      ],
      finishReason: 'stop',
      totalUsage: { inputTokens: 3000, outputTokens: 350, totalTokens: 3350 },
      turn,
      grounding: { grounded: false, cited: ['NCT1', 'NCT2'], ungrounded: ['NCT2'] },
      startedAt: 1_000,
      firstTokenAt: 1_800,
      finishedAt: 3_000,
    });

    expect(record).toMatchObject({
      model: { name: 'haiku-4.5', provider: 'anthropic' },
      steps: 2,
      stepUsage: [{ input: 1000, output: 50 }, { input: 2000, output: 300 }],
      usage: { input: 3000, output: 350, total: 3350 },
      latencyMs: 2000,
      firstTokenMs: 800,
      skillsLoaded: ['trial-outcomes'],
      budget: { spentChars: 400, limitChars: 1000, exhausted: false },
      grounding: { cited: 2, ungrounded: ['NCT2'] },
      status: 'ok',
    });
    // 3000 in at $1/M + 350 out at $5/M.
    expect(record.costUsd).toBeCloseTo(0.00475, 6);
    expect(record.toolCalls[0]).toMatchObject({ tool: 'query_proprietary_data', rows: 3 });
  });

  it('records a failed turn with its error and no usage', () => {
    const record = buildRunRecord({
      traceId: 't',
      cancerType: 'c',
      model: MODELS['haiku-4.5'],
      promptVersion: 'v',
      fastPath: 'lookup_trial',
      steps: [],
      turn: createTurnState(),
      startedAt: 0,
      finishedAt: 10,
      error: new Error('boom'),
    });
    expect(record).toMatchObject({ status: 'error', error: 'boom', steps: 0, fastPath: 'lookup_trial' });
    expect(record.costUsd).toBeUndefined();
  });
});
