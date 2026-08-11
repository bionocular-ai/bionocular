import { describe, expect, it } from 'vitest';
import { generateText, stepCountIs } from 'ai';
import { anthropic } from '@ai-sdk/anthropic';
import { agentTools } from './tools';
import { ONCOLOGY_SYSTEM_PROMPT } from './prompts';
import { checkGroundedness } from './groundedness';

/**
 * Model-behaviour evals: real model, real database, real money.
 *
 * Skipped unless both keys are present, so `npm run test` stays deterministic
 * and offline. These assert on tool choice and identifier provenance - never on
 * recorded response text - so enabling thinking or changing the model does not
 * invalidate them.
 */
const CREDENTIALS_PRESENT =
  Boolean(process.env.ANTHROPIC_API_KEY) && Boolean(process.env.SUPABASE_SECRET_KEY);

const CONTEXT = {
  userId: '00000000-0000-0000-0000-000000000000',
  cancerSlug: 'cutaneous-melanoma',
  traceId: 'eval',
};

async function ask(question: string) {
  return generateText({
    model: anthropic('claude-sonnet-5'),
    system: ONCOLOGY_SYSTEM_PROMPT,
    tools: agentTools(CONTEXT),
    providerOptions: { anthropic: { thinking: { type: 'disabled' } } },
    stopWhen: stepCountIs(6),
    prompt: question,
  });
}

describe.skipIf(!CREDENTIALS_PRESENT)('agent behaviour', () => {
  it('queries the database rather than answering from memory', async () => {
    const { steps } = await ask('What trials do we have for BRAF-mutant melanoma?');

    const called = steps.flatMap((s) => s.toolCalls).map((c) => c.toolName);
    expect(called).toContain('query_proprietary_data');
  }, 120_000);

  it('cites only identifiers its own tool results returned', async () => {
    const { text, steps } = await ask('Tell me about NCT00006368.');

    const results = steps.flatMap((s) => s.toolResults).map((r) => r.output);
    expect(checkGroundedness(text, results).ungrounded).toEqual([]);
  }, 120_000);

  it('states an absence instead of filling it', async () => {
    const { text } = await ask('Tell me about NCT99999999.');

    expect(text).toMatch(/no record|not (in|found)|don't have|do not have/i);
  }, 120_000);

  it('declines a cancer type outside this dashboard', async () => {
    const { text } = await ask("What's new in pancreatic cancer?");

    expect(text).toMatch(/outside|not cover|only cover|dashboard/i);
  }, 120_000);
});
