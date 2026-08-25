import { createAnthropic } from '@ai-sdk/anthropic';

/**
 * Thinking configuration lives here and nowhere else.
 *
 * Haiku 4.5 supports extended thinking but leaves it off unless asked. Kept
 * explicitly disabled: turning it on means sending `enabled` with a budget
 * here, plus a bump to MAX_OUTPUT_TOKENS in the route and a check that answers
 * are not being truncated.
 *
 * It has to go on the wire by hand. `@ai-sdk/anthropic` builds the `thinking`
 * field only for `enabled` and `adaptive` and drops `disabled` on the floor, so
 * `providerOptions` cannot express "off" - the request goes out with no
 * `thinking` field at all, which is model-default rather than a stated choice.
 * On Sonnet 5 that default was adaptive, and it stayed invisible until a tool
 * result got big enough for the reasoning to eat the whole output budget: 4096
 * output tokens, two empty reasoning blocks, no answer.
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
 * The model the agent and its evals both run on.
 *
 * One definition rather than two: the evals used to name the model and its
 * thinking config themselves, so they could drift from what the route actually
 * sent and still pass.
 */
export const agentModel = anthropic('claude-haiku-4-5-20251001');
