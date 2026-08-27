import { describe, expect, it } from 'vitest';
import { generateText, stepCountIs } from 'ai';
import { agentModel } from './model';
import { agentTools } from './tools';
import { ONCOLOGY_SYSTEM_PROMPT } from './prompts';
import { checkGroundedness } from './groundedness';

/**
 * Model-behaviour evals: real model, real database, real money.
 *
 * Skipped unless the credentials are present, so `npm run test` stays
 * deterministic and offline. These assert on tool choice and identifier
 * provenance - never on recorded response text - so enabling thinking or
 * changing the model does not invalidate them.
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
    model: agentModel,
    system: ONCOLOGY_SYSTEM_PROMPT,
    tools: agentTools(CONTEXT),
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

  it('filters trial_outcomes by phase directly, and reports the linkage gap', async () => {
    // Sourced from a real observed failure: asked to filter outcomes by phase,
    // the agent used to sweep clinical_trials for NCT numbers first rather than
    // filtering trial_outcomes directly via the registry join. This is that
    // question, run against the real model and the real database - one
    // generateText call, every assertion drawn from it.
    //
    // The route (src/app/api/agent/chat/route.ts) runs stepCountIs(8),
    // maxOutputTokens: 4096, and forces toolChoice: 'none' on the last step so
    // a turn cannot end on an unexplained tool call. `ask()` above diverges on
    // both step count and output cap, so this call mirrors the route directly
    // rather than reusing it.
    const question =
      'show me all published efficacy parameters (ORR, PFS and others) in cutaneous melanoma. ' +
      'strict rule: only drugs which are in phase 1 trial.';
    const MAX_STEPS = 8;
    const { text, steps } = await generateText({
      model: agentModel,
      system: ONCOLOGY_SYSTEM_PROMPT,
      tools: agentTools(CONTEXT),
      maxOutputTokens: 4096,
      stopWhen: stepCountIs(MAX_STEPS),
      prepareStep: ({ stepNumber }) =>
        stepNumber === MAX_STEPS - 1 ? { toolChoice: 'none' } : {},
      prompt: question,
    });

    const dataCalls = steps
      .flatMap((s) => s.toolCalls)
      .filter((c) => c.toolName === 'query_proprietary_data');

    expect(dataCalls).toHaveLength(1);
    expect(dataCalls[0].input).toMatchObject({ table: 'trial_outcomes', phase: 'PHASE1' });
    expect(dataCalls.some((c) => (c.input as { table?: string }).table === 'clinical_trials')).toBe(
      false,
    );

    const results = steps.flatMap((s) => s.toolResults).map((r) => r.output);
    const outcomeResult = results.find(
      (r) => (r as { table?: string })?.table === 'trial_outcomes',
    ) as { coverage?: Record<string, unknown> } | undefined;
    const coverage = outcomeResult?.coverage;

    expect(coverage?.complete).toBe(true);
    expect(coverage?.returned).toBe(coverage?.matched);
    const viaJoin = coverage?.viaJoin as { table?: string; unlinked?: number } | undefined;
    expect(viaJoin).toBeDefined();
    expect(viaJoin?.unlinked).toBeGreaterThan(0);

    // Meaning, not phrasing - the answer must not present the unlinked rows as
    // if the phase-1 set were complete without them. Observed wording calls
    // out rows that "lack NCT IDs" and trials "with no linked outcome data",
    // so this matches the ideas (no NCT id / not linked / excluded / linkage)
    // rather than one recorded sentence.
    expect(text).toMatch(/\bno nct\b|lacks? .*nct|not linked|no linked|unlinked|excluded|linkage/i);

    expect(checkGroundedness(text, results).ungrounded).toEqual([]);
  }, 180_000);

  it('does not claim a count larger than the trials its tools returned', async () => {
    // The old answer said "53 active/recruiting Phase 3 trials" above a table of
    // 45 rows. The number and the row set have to agree. The prose is no longer
    // the row set - the app draws it - so the count is checked against what the
    // tools returned, not against the identifiers the answer happens to name.
    const { text, steps } = await ask(
      'Show me all phase 3 active treatments or therapies in cutaneous melanoma.',
    );

    const results = JSON.stringify(steps.flatMap((s) => s.toolResults).map((r) => r.output));
    const returned = new Set(results.match(/\bNCT\d{8}\b/g) ?? []).size;
    const claimed = [...text.matchAll(/\b(\d{2,3})\s+(?:active|phase 3|Phase 3|trials)/g)].map((m) =>
      Number(m[1]),
    );

    // A sweep that returned nothing proves nothing, so say so rather than pass.
    expect(returned).toBeGreaterThan(20);
    for (const count of claimed) expect(count).toBeLessThanOrEqual(returned);
  }, 180_000);
});
