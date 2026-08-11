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

  // Cache the system prompt + tool definitions. Anthropic caches break on changes,
  // so the system prompt lives in the messages array with cacheControl rather than
  // as a top-level `system` string.
  const systemMessage: ModelMessage = {
    role: 'system',
    content: ONCOLOGY_SYSTEM_PROMPT,
    providerOptions: {
      anthropic: { cacheControl: { type: 'ephemeral' } },
    },
  };

  const result = streamText({
    model: anthropic('claude-sonnet-4-6'),
    messages: [systemMessage, ...modelMessages],
    tools: agentTools({ userId: user.id, cancerSlug: cancerType, sessionId }),
    stopWhen: stepCountIs(4), // raise to 8 after Render Pro upgrade
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
