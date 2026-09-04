import { describe, expect, it } from 'vitest';
import { vi } from 'vitest';
import type { UIMessage } from 'ai';
import { createFakeSupabase, type FakeSupabase, type TableFixture } from './tools/fake-supabase';

let fake: FakeSupabase;

vi.mock('@/lib/supabase/service', () => ({
  createServiceClient: () => fake,
}));

const { persistSession } = await import('./persist-session');

const MESSAGES: UIMessage[] = [
  { id: 'm1', role: 'user', parts: [{ type: 'text', text: 'Which trials read out in 2026?' }] },
  { id: 'm2', role: 'assistant', parts: [{ type: 'text', text: 'Three did.' }] },
];

function persistWith(
  fixtures: Record<string, TableFixture> = {},
  usage: unknown = {},
  steps?: readonly unknown[],
) {
  fake = createFakeSupabase(fixtures);
  return persistSession({
    userId: 'user-1',
    sessionId: 'session-1',
    traceId: 'trace-1',
    cancerType: 'cutaneous-melanoma',
    messages: MESSAGES,
    usage,
    steps,
  });
}

/** The row a prior turn of the same session left behind. */
function priorRow(tokenUsage: unknown): TableFixture {
  return { rows: [{ token_usage: tokenUsage }] };
}

describe('persistSession', () => {
  it('stores the first turn as a running total of one turn', async () => {
    await persistWith({}, { inputTokens: 4210, outputTokens: 318, totalTokens: 4528 });

    expect(fake.upserts[0].values.token_usage).toEqual({
      inputTokens: 4210,
      outputTokens: 318,
      totalTokens: 4528,
      turns: 1,
    });
  });

  it('adds a follow-up turn to the running total instead of overwriting it', async () => {
    await persistWith(
      { chat_sessions: priorRow({ inputTokens: 4210, outputTokens: 318, totalTokens: 4528, turns: 1 }) },
      { inputTokens: 5104, outputTokens: 402, totalTokens: 5506 },
    );

    expect(fake.upserts[0].values.token_usage).toEqual({
      inputTokens: 9314,
      outputTokens: 720,
      totalTokens: 10034,
      turns: 2,
    });
  });

  it('records each step separately, so a turn\'s cost can be blamed on the step that caused it', async () => {
    // A turn total says 17k tokens; it cannot say that the sweep in step 1 was
    // 12k of it. Diagnosing one expensive turn meant bisecting production rows.
    await persistWith({}, { inputTokens: 30000, outputTokens: 700 }, [
      { inputTokens: 4000, outputTokens: 200 },
      { inputTokens: 26000, outputTokens: 500 },
    ]);

    expect(fake.upserts[0].values.token_usage).toMatchObject({
      inputTokens: 30000,
      steps: [
        { inputTokens: 4000, outputTokens: 200 },
        { inputTokens: 26000, outputTokens: 500 },
      ],
    });
  });

  it('appends this turn\'s steps to the ones earlier turns left behind', async () => {
    await persistWith(
      { chat_sessions: priorRow({ inputTokens: 100, turns: 1, steps: [{ inputTokens: 100 }] }) },
      { inputTokens: 300 },
      [{ inputTokens: 300 }],
    );

    expect(fake.upserts[0].values.token_usage).toMatchObject({
      steps: [{ inputTokens: 100 }, { inputTokens: 300 }],
    });
  });

  it('leaves the total free of a steps key when no per-step usage was captured', async () => {
    // `accumulateUsage` sums every numeric it finds; an array is not one, so a
    // steps key that leaked into the total would be dead weight on every row.
    await persistWith({}, { inputTokens: 4210 });

    expect(fake.upserts[0].values.token_usage).not.toHaveProperty('steps');
  });

  it('carries provider-specific counters through the total too', async () => {
    await persistWith(
      { chat_sessions: priorRow({ inputTokens: 100, cachedInputTokens: 3000, turns: 1 }) },
      { inputTokens: 120, cachedInputTokens: 3000, reasoningTokens: 40 },
    );

    expect(fake.upserts[0].values.token_usage).toEqual({
      inputTokens: 220,
      cachedInputTokens: 6000,
      reasoningTokens: 40,
      turns: 2,
    });
  });

  it('treats an unusable prior total as a fresh count rather than crashing', async () => {
    await persistWith({ chat_sessions: priorRow(null) }, { inputTokens: 90, outputTokens: 10 });

    expect(fake.upserts[0].values.token_usage).toEqual({
      inputTokens: 90,
      outputTokens: 10,
      turns: 1,
    });
  });

  it('reads the prior total from the row it is about to overwrite', async () => {
    await persistWith({ chat_sessions: priorRow({ turns: 1 }) });

    const [read] = fake.queries;
    expect(read.table).toBe('chat_sessions');
    expect(read.projection).toBe('token_usage');
    expect(read.filters).toContainEqual({ operator: 'eq', column: 'id', value: 'session-1' });
  });

  it('titles the session from the first user message', async () => {
    await persistWith();

    expect(fake.upserts[0]).toMatchObject({
      table: 'chat_sessions',
      onConflict: 'id',
      values: { id: 'session-1', user_id: 'user-1', title: 'Which trials read out in 2026?' },
    });
  });

  it('records the indication the chat ran under, so history stays scoped to it', async () => {
    await persistWith();

    expect(fake.upserts[0].values.cancer_type).toBe('cutaneous-melanoma');
  });

  it('throws when chat_sessions is unreachable, so the caller can log it', async () => {
    await expect(
      persistWith({ chat_sessions: { error: { code: '42501', message: 'permission denied' } } }),
    ).rejects.toThrow(/permission denied/);
  });
});
