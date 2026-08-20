import { describe, expect, it } from 'vitest';
import { generateText, stepCountIs } from 'ai';
import { anthropic } from '@ai-sdk/anthropic';
import { agentTools } from './tools';
import { ONCOLOGY_SYSTEM_PROMPT } from './prompts';
import { checkCompleteness, checkGroundedness } from './groundedness';

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
    model: anthropic('claude-haiku-4-5-20251001'),
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

  // Sourced from a real failure, not from imagination: this exact question
  // returned all 53 trials to the model and enumerated 45 of them, while
  // claiming 53. Every grounding assertion above passed on that answer - they
  // police `cited - returned` and this failure is `returned - cited`. Anthropic
  // names the trap: one-sided evals create one-sided optimization.
  it('accounts for every trial its own tools returned', async () => {
    const { text, steps } = await ask(
      'Show me all phase 3 active treatments or therapies in cutaneous melanoma.',
    );

    const results = steps.flatMap((s) => s.toolResults).map((r) => r.output);
    const { complete, uncited, returned } = checkCompleteness(text, results);

    // A sweep that returned nothing proves nothing, so say so rather than pass.
    expect(returned.length).toBeGreaterThan(20);
    expect({ complete, uncited: uncited.slice(0, 10), returned: returned.length }).toMatchObject({
      complete: true,
    });
  }, 180_000);

  it('does not claim a count larger than the trials it lists', async () => {
    // The old answer said "53 active/recruiting Phase 3 trials" above a table of
    // 45 rows. The number and the list have to agree.
    const { text } = await ask(
      'Show me all phase 3 active treatments or therapies in cutaneous melanoma.',
    );

    const listed = new Set(text.match(/\bNCT\d{8}\b/g) ?? []).size;
    const claimed = [...text.matchAll(/\b(\d{2,3})\s+(?:active|phase 3|Phase 3|trials)/g)].map((m) =>
      Number(m[1]),
    );

    for (const count of claimed) expect(count).toBeLessThanOrEqual(listed);
  }, 180_000);
});
