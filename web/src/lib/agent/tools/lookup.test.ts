import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeSupabase, type FakeSupabase, type TableFixture } from './fake-supabase';
import { NCT_ID_PATTERN } from '@/lib/constants';

let fake: FakeSupabase;

vi.mock('@/lib/supabase/service', () => ({
  createServiceClient: () => fake,
}));

const { buildLookupTool } = await import('./lookup');

const CONTEXT = {
  userId: 'user-1',
  cancerSlug: 'cutaneous-melanoma',
  traceId: 'trace-1',
};

function toolsWith(fixtures: Record<string, TableFixture> = {}) {
  fake = createFakeSupabase(fixtures);
  return buildLookupTool(CONTEXT);
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
    const tools = buildLookupTool(CONTEXT);

    const result = await tools.lookup_trial.execute!({ nctId: 'NCT00604890' }, RUN_OPTIONS);

    expect(result).toMatchObject({ found: false, reason: 'other_cancer_type' });
    expect((result as { hint: string }).hint).toMatch(/not tagged to Cutaneous Melanoma/);
  });
});
