import { describe, expect, it, vi } from 'vitest';
import { APICallError, RetryError, wrapLanguageModel } from 'ai';
import { MockLanguageModelV3 } from 'ai/test';
import { createAgent } from './agent';
import {
  backoffMs,
  isRateLimited,
  modelCallMiddleware,
  RateLimitBreaker,
  RateLimitBreakerOpenError,
  type ModelCallRecord,
} from './model-calls';
import type { AgentTools } from './tools';

const apiError = (statusCode: number) =>
  new APICallError({ message: `status ${statusCode}`, url: 'u', requestBodyValues: {}, statusCode });

const usage = {
  inputTokens: { total: 120, noCache: 120, cacheRead: 0, cacheWrite: 0 },
  outputTokens: { total: 30, text: 30, reasoning: 0 },
};

const answer = (trafficType = 'ON_DEMAND_FLEX') => ({
  content: [{ type: 'text' as const, text: 'An answer.' }],
  finishReason: { unified: 'stop' as const, raw: 'STOP' },
  usage,
  providerMetadata: { vertex: { usageMetadata: { trafficType } } },
  warnings: [],
});

/** A model whose calls fail with each status in turn, then answer. */
function scripted(statuses: number[]) {
  let call = 0;
  return new MockLanguageModelV3({
    doGenerate: async () => {
      const status = statuses[call++];
      if (status !== undefined) throw apiError(status);
      return answer();
    },
  });
}

const RETRY = { maxAttempts: 3, baseDelayMs: 100, maxDelayMs: 1_000 };

function wrapped(model: MockLanguageModelV3, breaker?: RateLimitBreaker) {
  const records: ModelCallRecord[] = [];
  const sleep = vi.fn(async () => {});
  const wrappedModel = wrapLanguageModel({
    model,
    middleware: modelCallMiddleware({
      model: 'gemini-test',
      requestedTrafficType: 'flex',
      retry: RETRY,
      breaker,
      onCall: (r) => records.push(r),
      sleep,
    }),
  });
  const generate = () => wrappedModel.doGenerate({ prompt: [] });
  return { generate, records, sleep };
}

describe('modelCallMiddleware', () => {
  it('retries a 429 in place and records the lane Vertex reports, not the one asked for', async () => {
    const model = scripted([429]);
    const { generate, records, sleep } = wrapped(model);

    await generate();

    expect(model.doGenerateCalls).toHaveLength(2);
    expect(sleep).toHaveBeenCalledTimes(1);
    expect(records).toEqual([
      expect.objectContaining({
        model: 'gemini-test',
        requestedTrafficType: 'flex',
        actualTrafficType: 'ON_DEMAND_FLEX',
        status: 'ok',
        retryCount: 1,
        inputTokens: 120,
        outputTokens: 30,
      }),
    ]);
  });

  it('gives up after the policy\'s attempts and reports the call rate-limited', async () => {
    const model = scripted([429, 429, 429, 429]);
    const { generate, records } = wrapped(model);

    await expect(generate()).rejects.toSatisfy(isRateLimited);

    expect(model.doGenerateCalls).toHaveLength(3);
    expect(records).toEqual([expect.objectContaining({ status: 'rate_limited', httpStatus: 429, retryCount: 2, actualTrafficType: null })]);
  });

  it('counts a Flex queue timeout (504) as a refusal', async () => {
    const breaker = new RateLimitBreaker(5);
    const { generate, records } = wrapped(scripted([504]), breaker);

    await generate();

    expect(records).toEqual([expect.objectContaining({ status: 'ok', retryCount: 1 })]);
    expect(breaker.consecutiveRefusals).toBe(0);
  });

  it('retries other retryable errors without charging the breaker, and never a 400', async () => {
    const breaker = new RateLimitBreaker(1);
    const flaky = scripted([503]);
    await wrapped(flaky, breaker).generate();
    expect(flaky.doGenerateCalls).toHaveLength(2);
    expect(breaker.open).toBe(false);

    const bad = scripted([400]);
    const { generate, records } = wrapped(bad);
    await expect(generate()).rejects.toThrow('status 400');
    expect(bad.doGenerateCalls).toHaveLength(1);
    expect(records).toEqual([expect.objectContaining({ status: 'error', httpStatus: 400, retryCount: 0 })]);
  });

  it('stops sending once the run-wide breaker opens, and a success resets it', async () => {
    const breaker = new RateLimitBreaker(3);
    const first = wrapped(scripted([429, 429]), breaker);
    await first.generate();
    expect(breaker.consecutiveRefusals).toBe(0);

    const refused = scripted([429, 429, 429]);
    await expect(wrapped(refused, breaker).generate()).rejects.toSatisfy(isRateLimited);
    expect(breaker.open).toBe(true);

    const next = scripted([]);
    const { generate, records } = wrapped(next, breaker);
    await expect(generate()).rejects.toBeInstanceOf(RateLimitBreakerOpenError);
    expect(next.doGenerateCalls).toHaveLength(0);
    expect(records).toEqual([expect.objectContaining({ status: 'rate_limited' })]);
  });

  it('records a streamed call from its finish chunk', async () => {
    const records: ModelCallRecord[] = [];
    const model = wrapLanguageModel({
      model: new MockLanguageModelV3({
        doStream: async () => ({
          stream: new ReadableStream({
            start(controller) {
              controller.enqueue({ type: 'text-start', id: 't' });
              controller.enqueue({ type: 'text-delta', id: 't', delta: 'Hi' });
              controller.enqueue({ type: 'text-end', id: 't' });
              controller.enqueue({
                type: 'finish',
                finishReason: { unified: 'stop', raw: 'STOP' },
                usage,
                providerMetadata: { vertex: { usageMetadata: { trafficType: 'ON_DEMAND' } } },
              });
              controller.close();
            },
          }),
        }),
      }),
      middleware: modelCallMiddleware({
        model: 'gemini-test',
        requestedTrafficType: 'priority',
        retry: RETRY,
        onCall: (r) => records.push(r),
      }),
    });

    const { stream } = await model.doStream({ prompt: [] });
    const reader = stream.getReader();
    while (!(await reader.read()).done);

    expect(records).toEqual([
      expect.objectContaining({ requestedTrafficType: 'priority', actualTrafficType: 'ON_DEMAND', status: 'ok', inputTokens: 120 }),
    ]);
  });
});

describe('createAgent', () => {
  const agentOn = (mock: MockLanguageModelV3, maxAttempts: number, records: ModelCallRecord[]) =>
    createAgent({
      instructions: 'x',
      tools: {} as AgentTools,
      model: { name: 'mock', provider: 'mock', id: 'mock', pricing: { inputPer1M: 0, outputPer1M: 0 }, create: () => mock },
      retry: { maxAttempts, baseDelayMs: 1, maxDelayMs: 1 },
      onModelCall: (r) => records.push(r),
    });

  it('has the SDK retry off: with no middleware retries, a 429 is final', async () => {
    const mock = scripted([429]);
    const records: ModelCallRecord[] = [];

    await expect(agentOn(mock, 1, records).generate({ prompt: 'q' })).rejects.toSatisfy(isRateLimited);

    expect(mock.doGenerateCalls).toHaveLength(1);
    expect(records).toEqual([expect.objectContaining({ requestedTrafficType: 'n/a', status: 'rate_limited' })]);
  });

  it('retries a 429 in the middleware, keeping the turn going', async () => {
    const mock = scripted([429]);
    const records: ModelCallRecord[] = [];

    const result = await agentOn(mock, 2, records).generate({ prompt: 'q' });

    expect(result.text).toBe('An answer.');
    expect(mock.doGenerateCalls).toHaveLength(2);
    expect(records).toEqual([expect.objectContaining({ retryCount: 1, status: 'ok' })]);
  });
});

describe('isRateLimited', () => {
  it('is true for a 429 or a Flex 504, including one the SDK wrapped, and nothing else', () => {
    const retried = (last: unknown) => new RetryError({ message: 'x', reason: 'maxRetriesExceeded', errors: [last] });
    expect(isRateLimited(apiError(429))).toBe(true);
    expect(isRateLimited(retried(apiError(429)))).toBe(true);
    expect(isRateLimited(apiError(504))).toBe(true);
    expect(isRateLimited(retried(apiError(500)))).toBe(false);
    expect(isRateLimited(new Error('boom'))).toBe(false);
  });
});

describe('backoffMs', () => {
  it('doubles from the base, keeps at least half the step, and never passes the cap', () => {
    const policy = { maxAttempts: 5, baseDelayMs: 1_000, maxDelayMs: 4_000 };
    expect(backoffMs(1, policy, () => 0)).toBe(500);
    expect(backoffMs(1, policy, () => 1)).toBe(1_000);
    expect(backoffMs(2, policy, () => 1)).toBe(2_000);
    expect(backoffMs(5, policy, () => 1)).toBe(4_000);
  });
});
