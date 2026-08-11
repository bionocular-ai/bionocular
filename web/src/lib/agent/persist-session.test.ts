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

function persistWith(fixtures: Record<string, TableFixture> = {}, usage: unknown = {}) {
  fake = createFakeSupabase(fixtures);
  return persistSession({
    userId: 'user-1',
    sessionId: 'session-1',
    traceId: 'trace-1',
    messages: MESSAGES,
    usage,
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

  it('throws when chat_sessions is unreachable, so the caller can log it', async () => {
    await expect(
      persistWith({ chat_sessions: { error: { code: '42501', message: 'permission denied' } } }),
    ).rejects.toThrow(/permission denied/);
  });
});
