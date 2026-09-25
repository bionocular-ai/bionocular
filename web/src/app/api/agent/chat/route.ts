import {
  convertToModelMessages,
  createUIMessageStream,
  createUIMessageStreamResponse,
  type UIMessage,
  type UIMessageChunk,
} from 'ai';
import { createClient } from '@/lib/supabase/server';
import { checkAgentRateLimit } from '@/lib/agent/rate-limit';
import { persistSession } from '@/lib/agent/persist-session';
import { resolveModel } from '@/lib/agent/model';
import { buildAgentTools } from '@/lib/agent/tools';
import { createAgent, lastUserText, mentionsNct } from '@/lib/agent/agent';
import type { ModelCallRecord } from '@/lib/agent/model-calls';
import { buildInstructions, PROMPT_VERSION } from '@/lib/agent/prompts';
import { pruneHistory } from '@/lib/agent/context';
import { checkGroundedness } from '@/lib/agent/groundedness';
import { buildRunRecord, logRun } from '@/lib/agent/run';
import { getDbCancerType } from '@/lib/api';
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
    return new Response('Rate limit exceeded - 20 requests per minute', { status: 429 });
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

  // Ties every tool log line and span from this request to the session row.
  const traceId = crypto.randomUUID();
  const startedAt = Date.now();
  const model = resolveModel();
  const dbCancerType = getDbCancerType(cancerType);

  // Earlier turns' rows leave the model context here; their identifiers stay
  // as evidence so a citation of an earlier result still grounds. The client
  // and the session row keep the full transcript.
  const { messages: prunedMessages, retainedEvidence } = pruneHistory(messages);
  const modelMessages = await convertToModelMessages(prunedMessages);

  // The turn state the tools close over comes back too: the run record is
  // built from it once the turn is over.
  const { tools, turn } = buildAgentTools({
    userId: user.id,
    cancerSlug: cancerType,
    sessionId,
    traceId,
    retainedEvidence,
  });

  const fastPath = mentionsNct(lastUserText(messages)) ? ('lookup_trial' as const) : null;
  const modelCalls: ModelCallRecord[] = [];

  const agent = createAgent({
    instructions: buildInstructions({ cancerType: dbCancerType }),
    tools,
    model,
    forceLookupFirst: fastPath === 'lookup_trial',
    onModelCall: (record) => modelCalls.push(record),
    telemetry: {
      isEnabled: true,
      functionId: 'agent.chat',
      // Prompts, tool arguments and answers stay out of the spans; the run
      // record and the transcript hold what is needed to debug a turn.
      recordInputs: false,
      recordOutputs: false,
      metadata: {
        traceId,
        sessionId,
        userId: user.id,
        cancerType,
        promptVersion: PROMPT_VERSION,
        modelName: model.name,
        modelId: model.id,
        fastPath: fastPath ?? 'none',
      },
    },
  });

  let firstTokenAt: number | undefined;
  let runRecord: ReturnType<typeof buildRunRecord> | undefined;

  const stream = createUIMessageStream({
    // Turns on the SDK's persistence mode. Without it `onFinish` hands back only
    // the response message, so what got stored was a single assistant turn with
    // no question in front of it - and no user message meant no session title.
    originalMessages: messages,
    execute: async ({ writer }) => {
      const result = await agent.stream({ messages: modelMessages });

      writer.merge(
        result.toUIMessageStream().pipeThrough(
          new TransformStream<UIMessageChunk, UIMessageChunk>({
            transform(chunk, controller) {
              if (firstTokenAt === undefined && chunk.type === 'text-delta') firstTokenAt = Date.now();
              controller.enqueue(chunk);
            },
          }),
        ),
      );

      const [text, steps, finishReason, totalUsage] = await Promise.all([
        result.text,
        result.steps,
        result.finishReason,
        result.totalUsage,
      ]);

      // Every identifier the answer names has to have come from a tool result
      // this turn or from retained evidence. An answer is already on screen by
      // now, so an unsupported identifier is flagged beside it rather than
      // silently rendered as fact.
      const outputs = steps.flatMap((s) => s.toolResults).map((r) => r.output);
      const grounding = checkGroundedness(text, [outputs, [...turn.evidence]]);
      if (grounding.ungrounded.length > 0) {
        writer.write({ type: 'data-grounding', data: { ungrounded: grounding.ungrounded } });
      }

      const warnings = steps.flatMap((s) => s.warnings ?? []);
      if (warnings.length) console.warn('agent model warnings', { traceId, warnings });

      runRecord = buildRunRecord({
        traceId,
        sessionId,
        cancerType,
        model,
        promptVersion: PROMPT_VERSION,
        fastPath,
        steps,
        finishReason,
        totalUsage,
        turn,
        grounding,
        startedAt,
        firstTokenAt,
        finishedAt: Date.now(),
        modelCalls,
      });
      logRun(runRecord);
    },
    // Without this the SDK sends a bare "An error occurred." and the real cause
    // never reaches the server logs either.
    onError: (error) => {
      console.error('agent stream failed', { traceId, error });
      runRecord ??= buildRunRecord({
        traceId,
        sessionId,
        cancerType,
        model,
        promptVersion: PROMPT_VERSION,
        fastPath,
        steps: [],
        turn,
        startedAt,
        firstTokenAt,
        finishedAt: Date.now(),
        modelCalls,
        error,
      });
      logRun(runRecord);
      return 'The assistant hit an error answering that. Please try again.';
    },
    // Fires with the completed message list, assistant turn included - which is
    // why persistence lives here rather than on the model result.
    onFinish: async ({ messages: finishedMessages }) => {
      try {
        await persistSession({
          userId: user.id,
          sessionId,
          traceId,
          cancerType,
          messages: finishedMessages,
          usage: runRecord && {
            inputTokens: runRecord.usage.input,
            outputTokens: runRecord.usage.output,
            totalTokens: runRecord.usage.total,
            cachedInputTokens: runRecord.usage.cached,
            reasoningTokens: runRecord.usage.reasoning,
          },
          steps: runRecord?.stepUsage.map((s) => ({ inputTokens: s.input, outputTokens: s.output })),
          run: runRecord,
        });
      } catch (err) {
        // Don't fail the response if persistence breaks - just log.
        console.error('persistSession failed', { traceId, err });
      }
    },
  });

  return createUIMessageStreamResponse({ stream });
}
