import { createAnthropic } from '@ai-sdk/anthropic';
import {
  convertToModelMessages,
  stepCountIs,
  streamText,
  type ModelMessage,
  type UIMessage,
} from 'ai';
import { createClient } from '@/lib/supabase/server';
import { checkAgentRateLimit } from '@/lib/agent/rate-limit';
import { persistSession } from '@/lib/agent/persist-session';
import { agentTools } from '@/lib/agent/tools';
import { ONCOLOGY_SYSTEM_PROMPT } from '@/lib/agent/prompts';
import { DASHBOARD_CANCER_TYPES } from '@/lib/dashboard-constants';

export const runtime = 'nodejs';
export const maxDuration = 60;

/**
 * Thinking configuration lives here and nowhere else.
 *
 * Sonnet 5 runs adaptive thinking by default; Sonnet 4.6 ran thinking-off when
 * the field was omitted, so leaving it out would silently change behaviour.
 * Disabled deliberately for now: turning it on means sending `adaptive` here,
 * plus a bump to MAX_OUTPUT_TOKENS below and a check that answers are not being
 * truncated.
 *
 * It has to go on the wire by hand. `@ai-sdk/anthropic` builds the `thinking`
 * field only for `enabled` and `adaptive` and drops `disabled` on the floor, so
 * `providerOptions` cannot express "off" - the request went out with no
 * `thinking` field at all, which on Sonnet 5 means adaptive. That was invisible
 * until a tool result got big enough for the reasoning to eat the whole output
 * budget: 4096 output tokens, two empty reasoning blocks, no answer.
 */
const THINKING_CONFIG = { type: 'disabled' } as const;

const anthropic = createAnthropic({
  fetch: async (input, init) => {
    if (typeof init?.body !== 'string') return fetch(input, init);
    const body = JSON.parse(init.body) as Record<string, unknown>;
    body.thinking = THINKING_CONFIG;
    return fetch(input, { ...init, body: JSON.stringify(body) });
  },
});

/**
 * A cap on thinking *and* response text together, not on the answer alone -
 * so this has to grow if thinking is ever enabled above.
 */
const MAX_OUTPUT_TOKENS = 4096;

/**
 * Tool calls plus a final answer. The last step is forced to answer in text
 * (see `prepareStep`), so one of these is always spent on the reply.
 */
const MAX_STEPS = 8;

interface ChatRequestBody {
  messages: UIMessage[];
  sessionId?: string;
  /** Dashboard category slug the chat was opened under. */
  cancerType?: string;
}

const VALID_CANCER_SLUGS: ReadonlySet<string> = new Set(
  DASHBOARD_CANCER_TYPES.map((t) => t.value),
);

export async function POST(req: Request) {
  const supabase = await createClient();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    return new Response('Unauthorized', { status: 401 });
  }

  const allowed = await checkAgentRateLimit(user.id);
  if (!allowed) {
    return new Response('Rate limit exceeded — 20 requests per minute', { status: 429 });
  }

  const { messages, sessionId, cancerType }: ChatRequestBody = await req.json();

  // Client-supplied, so it is checked against the known slugs before it reaches
  // the query builder rather than passed through.
  if (!cancerType || !VALID_CANCER_SLUGS.has(cancerType)) {
    return new Response('Unknown cancer type', { status: 400 });
  }

  if (!sessionId) {
    return new Response('Missing sessionId', { status: 400 });
  }

  // Ties every tool log line from this request to the session row it belongs to.
  const traceId = crypto.randomUUID();
  const modelMessages: ModelMessage[] = await convertToModelMessages(messages);

  // The single cache breakpoint: it covers the tool definitions and the system
  // prompt, which render ahead of it. The prompt lives in the messages array
  // rather than in the top-level `system` string only because the AI SDK's
  // `system` accepts no providerOptions, and cacheControl is a providerOption.
  const systemMessage: ModelMessage = {
    role: 'system',
    content: ONCOLOGY_SYSTEM_PROMPT,
    providerOptions: {
      anthropic: { cacheControl: { type: 'ephemeral' } },
    },
  };

  // Captured from the model stream, written once the UI stream has the finished
  // message list.
  let finalUsage: unknown;

  const result = streamText({
    model: anthropic('claude-sonnet-5'),
    messages: [systemMessage, ...modelMessages],
    tools: agentTools({ userId: user.id, cancerSlug: cancerType, sessionId, traceId }),
    maxOutputTokens: MAX_OUTPUT_TOKENS,
    stopWhen: stepCountIs(MAX_STEPS),
    // Take the tools away for the last step so the turn cannot end on a tool
    // call the model never got to explain - tool cards and silence.
    prepareStep: ({ stepNumber }) =>
      stepNumber === MAX_STEPS - 1 ? { toolChoice: 'none' } : {},
    onFinish: ({ usage, warnings }) => {
      finalUsage = usage;
      // Provider warnings — unsupported settings, silently dropped options —
      // are otherwise invisible.
      if (warnings?.length) console.warn('agent model warnings', { traceId, warnings });
    },
  });

  return result.toUIMessageStreamResponse({
    // Turns on the SDK's persistence mode. Without it `onFinish` hands back only
    // the response message, so what got stored was a single assistant turn with
    // no question in front of it - and no user message meant no session title.
    originalMessages: messages,
    // Without this the SDK sends a bare "An error occurred." and the real cause
    // never reaches the server logs either.
    onError: (error) => {
      console.error('agent stream failed', { traceId, error });
      return 'The assistant hit an error answering that. Please try again.';
    },
    // Fires with the completed message list, assistant turn included — which is
    // why persistence lives here rather than in streamText's onFinish.
    onFinish: async ({ messages: finishedMessages }) => {
      try {
        await persistSession({
          userId: user.id,
          sessionId,
          traceId,
          messages: finishedMessages,
          usage: finalUsage,
        });
      } catch (err) {
        // Don't fail the response if persistence breaks — just log.
        console.error('persistSession failed', { traceId, err });
      }
    },
  });
}

