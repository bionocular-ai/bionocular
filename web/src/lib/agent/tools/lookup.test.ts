import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeSupabase, type FakeSupabase, type TableFixture } from './fake-supabase';
import { NCT_ID_PATTERN } from '@/lib/constants';
import { createTurnState } from './turn';

let fake: FakeSupabase;

vi.mock('@/lib/supabase/service', () => ({
  createServiceClient: () => fake,
}));

const { buildLookupTool, fitLookupToBudget } = await import('./lookup');
const { projectionFor } = await import('./schema');

const REQUEST = {
  userId: 'user-1',
  cancerSlug: 'cutaneous-melanoma',
  traceId: 'trace-1',
};

/** A fresh turn per test: the duplicate-call guard is per turn. */
const CONTEXT = () => ({ ...REQUEST, turn: createTurnState() });

function toolsWith(fixtures: Record<string, TableFixture> = {}) {
  fake = createFakeSupabase(fixtures);
  return buildLookupTool(CONTEXT());
}

// The SDK passes execute a second argument none of these tools read.
const RUN_OPTIONS = { toolCallId: 'test-call', messages: [] };

describe('lookup_trial', () => {
  beforeEach(() => {
    vi.spyOn(console, 'info').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('rejects anything that is not an 8-digit NCT number', () => {
    // The pattern both tools' input schemas are built from - the gate that
    // stops a malformed identifier before any query is constructed.
    for (const bad of ['NCT123', 'nct00006368', '2013-002616-28', 'CA209-578', '']) {
      expect(NCT_ID_PATTERN.test(bad)).toBe(false);
    }
    expect(NCT_ID_PATTERN.test('NCT00006368')).toBe(true);
  });

  it('separates the tables that hold a trial from those that do not', async () => {
    const tools = toolsWith({
      clinical_trials: { rows: [{ nct_id: 'NCT00006368', brief_title: 'A trial' }] },
      trial_landscape: { rows: [{ nct_id: 'NCT00006368', treatment_name: 'Interferon' }] },
      trial_outcomes: { rows: [] },
      km_curves: { rows: [] },
      news_feed: { rows: [] },
    });

    const result = await tools.lookup_trial.execute!({ nctId: 'NCT00006368' }, RUN_OPTIONS);

    expect(result).toMatchObject({ found: true, nctId: 'NCT00006368' });
    const coverage = (result as { coverage: { presentIn: string[]; absentFrom: string[]; caveats: string[] } }).coverage;
    expect(coverage.presentIn).toEqual(['clinical_trials', 'trial_landscape']);
    expect(coverage.absentFrom).toEqual(['trial_outcomes', 'km_curves', 'news_feed']);
    // Absent from trial_outcomes, so the linkage caveat has to travel with the
    // answer - the absence may be the 44% blind spot rather than missing data.
    expect(coverage.caveats.some((c) => /no nct_id/i.test(c))).toBe(true);
  });

  it('drops null keys from a looked-up row, so a wide projection sends only what populated', async () => {
    // trial_outcomes' projection is up to 198 columns; without dropEmpty a
    // named-trial lookup would carry a null for every endpoint the row did not
    // report.
    const tools = toolsWith({
      clinical_trials: {
        rows: [{ nct_id: 'NCT00006368', brief_title: 'A trial', acronym: null, keywords: [] }],
      },
      trial_landscape: { rows: [] },
      trial_outcomes: { rows: [] },
      km_curves: { rows: [] },
      news_feed: { rows: [] },
    });

    const result = await tools.lookup_trial.execute!({ nctId: 'NCT00006368' }, RUN_OPTIONS);

    const row = (result as { tables: Record<string, { rows: Record<string, unknown>[] }> }).tables
      .clinical_trials.rows[0];
    expect(row).toEqual({ nct_id: 'NCT00006368', brief_title: 'A trial' });
    expect(row).not.toHaveProperty('acronym');
    expect(row).not.toHaveProperty('keywords');
  });

  it('calls a trial we have never seen not_in_bionocular', async () => {
    const tools = toolsWith({});

    const result = await tools.lookup_trial.execute!({ nctId: 'NCT99999999' }, RUN_OPTIONS);

    expect(result).toMatchObject({ found: false, reason: 'not_in_bionocular' });
  });

  it('distinguishes a trial tagged to another cancer type', async () => {
    // Scoped queries find nothing; the unscoped existence check finds the row.
    fake = createFakeSupabase({});
    const scopedFake = fake;
    let call = 0;
    const original = scopedFake.from;
    scopedFake.from = (table: string) => {
      call += 1;
      // The sixth query is the unscoped clinical_trials existence check.
      if (call === 6) return createFakeSupabase({ [table]: { rows: [], count: 1 } }).from(table);
      return original(table);
    };
    const tools = buildLookupTool(CONTEXT());

    const result = await tools.lookup_trial.execute!({ nctId: 'NCT00604890' }, RUN_OPTIONS);

    expect(result).toMatchObject({ found: false, reason: 'other_cancer_type' });
    expect((result as { hint: string }).hint).toMatch(/not tagged to Cutaneous Melanoma/);
  });
});

describe('lookup_trial projection and budget', () => {
  beforeEach(() => {
    vi.spyOn(console, 'info').mockImplementation(() => {});
  });

  it('reads the concise projection by default, not every column', async () => {
    const tools = toolsWith({});
    await tools.lookup_trial.execute!({ nctId: 'NCT00006368' }, RUN_OPTIONS);

    const outcomes = fake.queries.find((q) => q.table === 'trial_outcomes')!;
    expect(outcomes.projection).toBe(projectionFor('trial_outcomes', 'concise', 'both'));
    expect(outcomes.projection).not.toContain('grade_3_plus_trae_rash');
    // Order applies to lookups too: two lookups of a ten-arm trial show the
    // same ten arms.
    expect(outcomes.order.map((o) => o.column)).toEqual(['nct_id', 'id']);
  });

  it('widens to the full endpoint set, narrowed by family, when asked', async () => {
    const tools = toolsWith({});
    await tools.lookup_trial.execute!(
      { nctId: 'NCT00006368', detail: 'detailed', endpoints: 'safety' },
      RUN_OPTIONS,
    );

    const outcomes = fake.queries.find((q) => q.table === 'trial_outcomes')!;
    expect(outcomes.projection).toContain('grade_3_plus_trae_rash');
    expect(outcomes.projection).not.toContain('median_pfs');
    // The other tables have one projection either way.
    const trials = fake.queries.find((q) => q.table === 'clinical_trials')!;
    expect(trials.projection).toBe(projectionFor('clinical_trials', 'detailed', 'safety'));
  });

  it('trims the widest table one row at a time until the lookup fits, and says so', () => {
    const wide = (n: number) =>
      Array.from({ length: n }, (_, i) => ({ id: `r${i}`, pad: 'x'.repeat(400) }));
    const tables = {
      clinical_trials: { matched: 1, rows: wide(1) },
      trial_landscape: { matched: 1, rows: wide(1) },
      trial_outcomes: { matched: 10, rows: wide(10) },
      km_curves: { matched: 6, rows: wide(6) },
      news_feed: null,
    };
    const before = JSON.stringify(tables).length;

    const { tables: fitted, truncated } = fitLookupToBudget(tables, Math.floor(before / 2));

    expect(JSON.stringify(fitted).length).toBeLessThanOrEqual(Math.floor(before / 2));
    // Single-row tables are never emptied; the multi-row ones share the cut.
    expect(fitted.clinical_trials!.rows).toHaveLength(1);
    expect(fitted.trial_landscape!.rows).toHaveLength(1);
    expect(fitted.trial_outcomes!.rows.length).toBeLessThan(10);
    expect(truncated).toContain('trial_outcomes');
    // Prefix of the ordered rows, so the trim is deterministic.
    expect(fitted.trial_outcomes!.rows).toEqual(tables.trial_outcomes.rows.slice(0, fitted.trial_outcomes!.rows.length));
  });

  it('applies the turn budget, and records the trial as evidence', async () => {
    const turn = createTurnState({ limitChars: 3_000 });
    fake = createFakeSupabase({
      clinical_trials: { rows: [{ nct_id: 'NCT00006368', brief_title: 'A trial' }] },
      trial_outcomes: {
        rows: Array.from({ length: 10 }, (_, i) => ({ id: `o${i}`, nct_id: 'NCT00006368', arm_name: 'x'.repeat(300) })),
      },
    });
    const tools = buildLookupTool({ ...REQUEST, turn });

    const result = (await tools.lookup_trial.execute!({ nctId: 'NCT00006368' }, RUN_OPTIONS)) as {
      coverage: { truncated?: string[]; hint?: string };
      tables: Record<string, { rows: unknown[] } | null>;
    };

    expect(result.coverage.truncated).toEqual(['trial_outcomes']);
    expect(result.coverage.hint).toMatch(/subset/);
    expect(result.tables.trial_outcomes!.rows.length).toBeLessThan(10);
    expect(turn.evidence.has('NCT00006368')).toBe(true);
    expect(turn.remainingChars()).toBeLessThan(3_000);
  });
});
