import { anthropic } from '@ai-sdk/anthropic';
import {
  convertToModelMessages,
  stepCountIs,
  streamText,
  type ModelMessage,
  type UIMessage,
} from 'ai';
import { createClient } from '@/lib/supabase/server';
import { createServiceClient } from '@/lib/supabase/service';
import { checkAgentRateLimit } from '@/lib/agent/rate-limit';
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
 * Disabled deliberately for now: turning it on is a change to `{ type:
 * 'adaptive' }` here, plus a bump to MAX_OUTPUT_TOKENS below and a check that
 * answers are not being truncated.
 */
const AGENT_MODEL_OPTIONS = {
  anthropic: { thinking: { type: 'disabled' } },
} as const;

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

  const result = streamText({
    model: anthropic('claude-sonnet-5'),
    messages: [systemMessage, ...modelMessages],
    tools: agentTools({ userId: user.id, cancerSlug: cancerType, sessionId }),
    providerOptions: AGENT_MODEL_OPTIONS,
    maxOutputTokens: MAX_OUTPUT_TOKENS,
    stopWhen: stepCountIs(MAX_STEPS),
    // Take the tools away for the last step so the turn cannot end on a tool
    // call the model never got to explain - tool cards and silence.
    prepareStep: ({ stepNumber }) =>
      stepNumber === MAX_STEPS - 1 ? { toolChoice: 'none' } : {},
    onFinish: async ({ usage }) => {
      try {
        await persistSession({
          userId: user.id,
          sessionId,
          messages,
          usage,
        });
      } catch (err) {
        // Don't fail the response if persistence breaks — just log.
        console.error('persistSession failed', err);
      }
    },
  });

  return result.toUIMessageStreamResponse({
    // Without this the SDK sends a bare "An error occurred." and the real cause
    // never reaches the server logs either.
    onError: (error) => {
      console.error('agent stream failed', error);
      return 'The assistant hit an error answering that. Please try again.';
    },
  });
}

interface PersistArgs {
  userId: string;
  sessionId: string | undefined;
  messages: UIMessage[];
  usage: unknown;
}

async function persistSession({ userId, sessionId, messages, usage }: PersistArgs) {
  const supabase = createServiceClient();
  const firstUserMessage = messages.find((m) => m.role === 'user');
  const titleSource = firstUserMessage?.parts.find((p) => p.type === 'text');
  const title = titleSource && 'text' in titleSource
    ? String(titleSource.text).slice(0, 80)
    : 'Untitled chat';

  if (sessionId) {
    await supabase
      .from('chat_sessions')
      .update({
        messages,
        token_usage: usage,
        updated_at: new Date().toISOString(),
      })
      .eq('id', sessionId)
      .eq('user_id', userId);
  } else {
    await supabase.from('chat_sessions').insert({
      user_id: userId,
      title,
      messages,
      token_usage: usage,
    });
  }
}
