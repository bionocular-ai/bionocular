/**
 * The one retry layer for model calls, and a record of every call.
 *
 * Vertex serves Gemini 3.x from a shared pool that refuses with a bare 429,
 * sometimes for many minutes. The retry lives here, per model call, so a
 * refusal mid-turn re-sends that one step and keeps the steps already done.
 * The SDK's own retry is off (`maxRetries: 0` in `agent.ts`) and nothing
 * above this re-runs a turn, so retries cannot stack.
 *
 * A refusal is a 429 on the Standard lane, and on the Flex lane a 504: Flex
 * queues a request rather than refusing it, and answers "Deadline expired"
 * when the queue does not reach it before the server timeout.
 *
 * Every call leaves a record naming the traffic lane asked for and the lane
 * Vertex reports it used. The lane header is a request, not a grant: Vertex
 * has been seen downgrading priority to `ON_DEMAND` without an error.
 */

import { APICallError, RetryError, type LanguageModelMiddleware } from 'ai';

export interface RetryPolicy {
  /** Tries per model call, the first included. */
  maxAttempts: number;
  baseDelayMs: number;
  maxDelayMs: number;
}

/**
 * The chat route has a 60s budget. Three tries in about 15s - the same count
 * the SDK default made, with jitter so concurrent turns do not retry in step.
 */
export const INTERACTIVE_RETRY: RetryPolicy = { maxAttempts: 3, baseDelayMs: 2_000, maxDelayMs: 8_000 };

export interface ModelCallRecord {
  model: string;
  /** The lane the request asked for; `n/a` for a provider without lanes. */
  requestedTrafficType: string;
  /** `usageMetadata.trafficType` from the response; null when none came back. */
  actualTrafficType: string | null;
  status: 'ok' | 'rate_limited' | 'error';
  /** The provider's HTTP status on failure; absent on success or a network error. */
  httpStatus?: number;
  retryCount: number;
  inputTokens?: number;
  outputTokens?: number;
  /** From the first try to the last byte, backoff included. */
  latencyMs: number;
  /** When the first try was sent. */
  timestamp: string;
}

function statusOf(error: unknown): number | undefined {
  const last = RetryError.isInstance(error) ? error.lastError : error;
  return APICallError.isInstance(last) ? last.statusCode : undefined;
}

/** The pool did not admit the call: a 429, or a Flex request that timed out in the queue. */
export function isRateLimited(error: unknown): boolean {
  const status = statusOf(error);
  return status === 429 || status === 504;
}

/**
 * Consecutive refusals across a whole run, any success resetting the count. Once
 * open, no further call is sent: a pool that refused this many times in a row
 * is not going to admit the next one, and every refused try is load on it.
 */
export class RateLimitBreaker {
  private consecutive = 0;

  constructor(readonly threshold: number) {}

  get open(): boolean {
    return this.consecutive >= this.threshold;
  }

  get consecutiveRefusals(): number {
    return this.consecutive;
  }

  succeeded(): void {
    this.consecutive = 0;
  }

  refused(): void {
    this.consecutive += 1;
  }
}

export class RateLimitBreakerOpenError extends Error {
  constructor(consecutive: number) {
    super(`Rate-limit breaker open after ${consecutive} consecutive refusals; not sending further model calls`);
    this.name = 'RateLimitBreakerOpenError';
  }
}

/** Exponential with equal jitter: half the step fixed, half random. */
export function backoffMs(retry: number, policy: RetryPolicy, random = Math.random): number {
  const step = Math.min(policy.maxDelayMs, policy.baseDelayMs * 2 ** (retry - 1));
  return step / 2 + random() * (step / 2);
}

function trafficTypeOf(providerMetadata: unknown): string | null {
  if (!providerMetadata || typeof providerMetadata !== 'object') return null;
  for (const provider of Object.values(providerMetadata)) {
    const usage = (provider as { usageMetadata?: { trafficType?: unknown } } | null)?.usageMetadata;
    if (typeof usage?.trafficType === 'string') return usage.trafficType;
  }
  return null;
}

interface Usage {
  inputTokens: { total: number | undefined };
  outputTokens: { total: number | undefined };
}

export interface ModelCallOptions {
  model: string;
  requestedTrafficType: string;
  retry: RetryPolicy;
  breaker?: RateLimitBreaker;
  onCall?: (record: ModelCallRecord) => void;
  sleep?: (ms: number) => Promise<void>;
}

export function modelCallMiddleware({
  model,
  requestedTrafficType,
  retry,
  breaker,
  onCall,
  sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
}: ModelCallOptions): LanguageModelMiddleware {
  /**
   * Sends `call` until it is admitted, a non-retryable error comes back, the
   * tries run out, or the breaker opens. Anything the SDK marks retryable
   * (408, 409, 5xx) is retried as it was before; only refusals count
   * toward the breaker. A call that fails reports its record here;
   * one that succeeds hands `record` to the caller, which reports it once the
   * usage is known.
   */
  async function admitted<T>(call: () => PromiseLike<T>) {
    const startedAt = Date.now();
    let retryCount = 0;
    const record = (
      status: ModelCallRecord['status'],
      usage?: Usage,
      providerMetadata?: unknown,
      error?: unknown,
    ): ModelCallRecord => ({
      model,
      requestedTrafficType,
      actualTrafficType: trafficTypeOf(providerMetadata),
      status,
      httpStatus: error === undefined ? undefined : statusOf(error),
      retryCount,
      inputTokens: usage?.inputTokens.total,
      outputTokens: usage?.outputTokens.total,
      latencyMs: Date.now() - startedAt,
      timestamp: new Date(startedAt).toISOString(),
    });

    for (;;) {
      if (breaker?.open) {
        onCall?.(record('rate_limited'));
        throw new RateLimitBreakerOpenError(breaker.consecutiveRefusals);
      }
      try {
        const result = await call();
        breaker?.succeeded();
        return { result, record };
      } catch (error) {
        const refused = isRateLimited(error);
        if (!refused && !(APICallError.isInstance(error) && error.isRetryable)) {
          onCall?.(record('error', undefined, undefined, error));
          throw error;
        }
        if (refused) breaker?.refused();
        if (retryCount + 1 >= retry.maxAttempts || breaker?.open) {
          onCall?.(record(refused ? 'rate_limited' : 'error', undefined, undefined, error));
          throw error;
        }
        retryCount += 1;
        await sleep(backoffMs(retryCount, retry));
      }
    }
  }

  return {
    specificationVersion: 'v3',
    wrapGenerate: async ({ doGenerate }) => {
      const { result, record } = await admitted(doGenerate);
      onCall?.(record('ok', result.usage, result.providerMetadata));
      return result;
    },
    // A refusal arrives as the response to the request, before any chunk, so
    // retrying `doStream` itself is enough. The record waits for the finish
    // chunk, which carries the usage and the traffic type.
    wrapStream: async ({ doStream }) => {
      const { result, record } = await admitted(doStream);
      let finished = false;
      return {
        ...result,
        stream: result.stream.pipeThrough(
          new TransformStream({
            transform(part, controller) {
              if (part.type === 'finish') {
                finished = true;
                onCall?.(record('ok', part.usage, part.providerMetadata));
              }
              controller.enqueue(part);
            },
            flush() {
              if (!finished) onCall?.(record('error'));
            },
          }),
        ),
      };
    },
  };
}
