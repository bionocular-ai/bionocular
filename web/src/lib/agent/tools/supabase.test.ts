import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeSupabase, type FakeSupabase, type TableFixture } from './fake-supabase';

let fake: FakeSupabase;

vi.mock('@/lib/supabase/service', () => ({
  createServiceClient: () => fake,
}));

const { buildSupabaseTools } = await import('./supabase');

const CONTEXT = {
  userId: 'user-1',
  cancerSlug: 'cutaneous-melanoma',
  traceId: 'trace-1',
};

function toolsWith(fixtures: Record<string, TableFixture> = {}) {
  fake = createFakeSupabase(fixtures);
  return buildSupabaseTools(CONTEXT);
}

// The SDK passes execute a second argument none of these tools read.
const RUN_OPTIONS = { toolCallId: 'test-call', messages: [] };

const TRIAL_ROW = { nct_id: 'NCT00006368', brief_title: 'A melanoma trial' };

describe('query_proprietary_data', () => {
  beforeEach(() => {
    vi.spyOn(console, 'info').mockImplementation(() => {});
    vi.spyOn(console, 'error').mockImplementation(() => {});
  });

  it('scopes array cancer_type columns with contains, never eq', async () => {
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW], count: 42 } });

    await tools.query_proprietary_data.execute!({ table: 'clinical_trials', limit: 10 }, RUN_OPTIONS);

    const [query] = fake.queries;
    expect(query.filters).toContainEqual({
      operator: 'contains',
      column: 'cancer_type',
      value: ['Cutaneous Melanoma'],
    });
    // The exact shape of the bug this replaces: `.eq()` on a text[] column,
    // which PostgREST answers with `malformed array literal`.
    expect(query.filters.some((f) => f.column === 'cancer_type' && f.operator === 'eq')).toBe(false);
  });

  it('scopes the one scalar cancer_type column with eq', async () => {
    const tools = toolsWith({ km_curves: { rows: [{ id: 'k1' }] } });

    await tools.query_proprietary_data.execute!({ table: 'km_curves', limit: 10 }, RUN_OPTIONS);

    expect(fake.queries[0].filters).toContainEqual({
      operator: 'eq',
      column: 'cancer_type',
      value: 'Cutaneous Melanoma',
    });
  });

  it('matches a trial through news_feed.nct_ids, which is an array', async () => {
    const tools = toolsWith({ news_feed: { rows: [{ url: 'https://example.test/a' }] } });

    await tools.query_proprietary_data.execute!(
      { table: 'news_feed', nctId: 'NCT00006368', limit: 10 },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].filters).toContainEqual({
      operator: 'contains',
      column: 'nct_ids',
      value: ['NCT00006368'],
    });
  });

  it('selects an explicit projection, never *', async () => {
    const tools = toolsWith({ trial_outcomes: { rows: [{ id: 'o1' }] } });

    await tools.query_proprietary_data.execute!({ table: 'trial_outcomes', limit: 10 }, RUN_OPTIONS);

    const { projection } = fake.queries[0];
    expect(projection).not.toBe('*');
    expect(projection).toContain('nct_id');
    expect(projection.split(',').length).toBeLessThan(40);
  });

  it('returns the condition strings each cancer_type bucket was derived from', async () => {
    // cancer_type is derived from the trial's own conditions, so the evidence is
    // the sponsor's wording. Without it the model can only assert our tag.
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW] } });

    await tools.query_proprietary_data.execute!({ table: 'clinical_trials', limit: 10 }, RUN_OPTIONS);

    expect(fake.queries[0].projection).toContain('cancer_type_evidence');
  });

  it('reports rows with a coverage count of everything that matched', async () => {
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW], count: 3701 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', limit: 10 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({
      ok: true,
      coverage: { returned: 1, matched: 3701, cancerType: 'Cutaneous Melanoma' },
    });
  });

  it('marks a result incomplete when the limit cut it short', async () => {
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW], count: 184 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', phase: 'PHASE3', limit: 1 },
      RUN_OPTIONS,
    );

    const { coverage } = result as { coverage: { complete: boolean; truncatedBy: string; hint: string } };
    expect(coverage.complete).toBe(false);
    expect(coverage.truncatedBy).toBe('limit');
    expect(coverage.hint).toMatch(/higher limit/i);
  });

  it('marks a result complete when every matching row came back', async () => {
    const rows = Array.from({ length: 53 }, (_, i) => ({ ...TRIAL_ROW, nct_id: `NCT0000000${i}` }));
    const tools = toolsWith({ clinical_trials: { rows, count: 53 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', phase: 'PHASE3', limit: 500 },
      RUN_OPTIONS,
    );

    const { coverage } = result as { coverage: { complete: boolean; truncatedBy?: string } };
    expect(coverage).toMatchObject({ returned: 53, matched: 53, complete: true });
    expect(coverage.truncatedBy).toBeUndefined();
  });

  it('drops rows that do not fit the size budget and says so', async () => {
    // Each row is ~2KB of free text, so 500 of them overrun the result budget.
    const rows = Array.from({ length: 500 }, (_, i) => ({
      nct_id: `NCT1000${String(i).padStart(4, '0')}`,
      brief_title: 'x'.repeat(2000),
    }));
    const tools = toolsWith({ clinical_trials: { rows, count: 500 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', limit: 500 },
      RUN_OPTIONS,
    );

    const { coverage, rows: kept } = result as {
      coverage: { returned: number; complete: boolean; truncatedBy: string };
      rows: unknown[];
    };
    expect(coverage.complete).toBe(false);
    expect(coverage.truncatedBy).toBe('size');
    expect(kept.length).toBeLessThan(500);
    expect(coverage.returned).toBe(kept.length);
  });

  it('matches several recruitment statuses in one query rather than one at a time', async () => {
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW], count: 53 } });

    await tools.query_proprietary_data.execute!(
      {
        table: 'clinical_trials',
        phase: 'PHASE3',
        status: ['RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING'],
        limit: 500,
      },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].filters).toContainEqual({
      operator: 'in',
      column: 'overall_status',
      value: ['RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING'],
    });
  });

  it('matches a single status with eq, so ACTIVE_NOT_RECRUITING cannot catch NOT_YET_RECRUITING', async () => {
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW], count: 27 } });

    await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', status: ['ACTIVE_NOT_RECRUITING'], limit: 500 },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].filters).toContainEqual({
      operator: 'eq',
      column: 'overall_status',
      value: 'ACTIVE_NOT_RECRUITING',
    });
    expect(fake.queries[0].filters.some((f) => f.operator === 'ilike')).toBe(false);
  });

  it('refuses a status filter on tables that have no recruitment status', async () => {
    const tools = toolsWith({ trial_landscape: { rows: [{ nct_id: 'NCT00006368' }] } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', status: ['RECRUITING'], limit: 10 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({ ok: false, reason: 'unsupported_filter', filter: 'status' });
  });

  it('carries the linkage caveat on trial_outcomes results', async () => {
    const tools = toolsWith({ trial_outcomes: { rows: [{ id: 'o1' }] } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_outcomes', limit: 10 },
      RUN_OPTIONS,
    );

    expect((result as { coverage: { caveat?: string } }).coverage.caveat).toMatch(/no nct_id/i);
  });

  it('reports an empty result as a fact rather than an empty success', async () => {
    const tools = toolsWith({ trial_landscape: { rows: [] } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', nctId: 'NCT99999999', limit: 10 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({
      ok: false,
      reason: 'no_rows',
      appliedFilters: { nctId: 'NCT99999999' },
    });
    // Observational trials are excluded from this table by design, so an
    // absence here is not an absence from the registry.
    expect((result as { coverage: { caveat?: string } }).coverage.caveat).toMatch(/observational/i);
  });

  it('refuses a filter the table does not have instead of ignoring it', async () => {
    const tools = toolsWith({ km_curves: { rows: [{ id: 'k1' }] } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'km_curves', phase: 'PHASE3', limit: 10 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({ ok: false, reason: 'unsupported_filter', filter: 'phase' });
    expect((result as { supportedFilters: string[] }).supportedFilters).toEqual(['drug']);
  });

  it('turns an unknown column into a structured outcome, not a throw', async () => {
    const tools = toolsWith({
      clinical_trials: { error: { code: '42703', message: 'column does not exist' } },
    });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', limit: 10 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({ ok: false, reason: 'unknown_column' });
  });

});
