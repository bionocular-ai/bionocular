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

export const runtime = 'nodejs';
export const maxDuration = 60;

interface ChatRequestBody {
  messages: UIMessage[];
  sessionId?: string;
}

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

  const { messages, sessionId }: ChatRequestBody = await req.json();
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
    tools: agentTools(user.id),
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

  return result.toUIMessageStreamResponse();
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
