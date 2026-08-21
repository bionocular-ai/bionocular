import type { UIMessage } from 'ai';
import { createServiceClient } from '@/lib/supabase/service';

export interface PersistArgs {
  userId: string;
  sessionId: string;
  traceId: string;
  messages: UIMessage[];
  usage: unknown;
  /** Per-step usage for this turn, oldest first. Omitted when nothing captured it. */
  steps?: readonly unknown[];
}

/**
 * Fold this turn's usage into the session's running total.
 *
 * Every numeric counter the provider reports is summed, so provider-specific
 * fields (cached input, reasoning) accumulate without being enumerated here.
 * `turns` is kept out of that loop because it counts calls, not tokens.
 */
function accumulateUsage(prior: unknown, current: unknown): Record<string, number> {
  const total: Record<string, number> = {};

  for (const source of [prior, current]) {
    if (!source || typeof source !== 'object') continue;
    for (const [key, value] of Object.entries(source)) {
      if (key === 'turns') continue;
      if (typeof value === 'number' && Number.isFinite(value)) {
        total[key] = (total[key] ?? 0) + value;
      }
    }
  }

  const priorTurns =
    prior && typeof prior === 'object' && typeof (prior as { turns?: unknown }).turns === 'number'
      ? (prior as { turns: number }).turns
      : 0;
  total.turns = priorTurns + 1;

  return total;
}

/**
 * Keep every step's usage, oldest first, across the whole session.
 *
 * A turn total says the turn cost 17k tokens; it cannot say that one unfiltered
 * sweep in step 1 was 12k of it. Without this, attributing a turn's cost meant
 * bisecting production rows by hand. Only finite numbers survive, so a provider
 * adding a nested object to its usage shape cannot bloat the row.
 */
function accumulateSteps(prior: unknown, current: readonly unknown[]): Record<string, number>[] {
  const earlier =
    prior && typeof prior === 'object' && Array.isArray((prior as { steps?: unknown }).steps)
      ? ((prior as { steps: unknown[] }).steps as unknown[])
      : [];

  const compact = (step: unknown): Record<string, number> => {
    const out: Record<string, number> = {};
    if (step && typeof step === 'object') {
      for (const [key, value] of Object.entries(step)) {
        if (typeof value === 'number' && Number.isFinite(value)) out[key] = value;
      }
    }
    return out;
  };

  return [...earlier.map(compact), ...current.map(compact)];
}

/**
 * Upsert the conversation on the client-supplied session ID.
 *
 * The ID is owned by the browser for the life of the chat, so a conversation
 * lands in one row that grows. Previously the client never sent one, so the
 * update branch was unreachable and every turn inserted a fresh row - and what
 * it stored was the request's message list, which stops before the answer the
 * user actually saw. The list saved here comes from the finished UI stream, so
 * it includes the assistant turn and its tool calls.
 */
export async function persistSession({ userId, sessionId, traceId, messages, usage, steps }: PersistArgs) {
  const supabase = createServiceClient();
  const firstUserMessage = messages.find((m) => m.role === 'user');
  const titleSource = firstUserMessage?.parts.find((p) => p.type === 'text');
  const title = titleSource && 'text' in titleSource
    ? String(titleSource.text).slice(0, 80)
    : 'Untitled chat';

  // The upsert replaces the whole row, so the total this turn adds to has to be
  // read back first. Without it a follow-up turn overwrites every earlier turn's
  // usage and the session's real cost is unrecoverable.
  const { data: prior, error: readError } = await supabase
    .from('chat_sessions')
    .select('token_usage')
    .eq('id', sessionId)
    .maybeSingle();

  if (readError) {
    throw new Error(`chat_sessions token_usage read failed: ${readError.message}`);
  }

  const { error } = await supabase
    .from('chat_sessions')
    .upsert(
      {
        id: sessionId,
        user_id: userId,
        title,
        messages,
        token_usage: (() => {
          const priorUsage = (prior as { token_usage?: unknown } | null)?.token_usage;
          const total = accumulateUsage(priorUsage, usage);
          // Absent when nothing captured per-step usage, so the field never
          // appears as an empty array on rows that have nothing to say.
          return steps?.length ? { ...total, steps: accumulateSteps(priorUsage, steps) } : total;
        })(),
        last_trace_id: traceId,
        updated_at: new Date().toISOString(),
      },
      { onConflict: 'id' },
    );

  if (error) throw new Error(`chat_sessions upsert failed: ${error.message}`);
}
