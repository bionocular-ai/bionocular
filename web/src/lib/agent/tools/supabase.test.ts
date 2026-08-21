import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeSupabase, type FakeSupabase, type TableFixture } from './fake-supabase';
import { projectionFor } from './schema';

let fake: FakeSupabase;

vi.mock('@/lib/supabase/service', () => ({
  createServiceClient: () => fake,
}));

const { buildSupabaseTools, fitToBudget, MAX_RESULT_CHARS } = await import('./supabase');

/** Rows whose JSON serialises to exactly `chars` characters. */
function rowsOfSize(chars: number, count = 1) {
  const rows = Array.from({ length: count }, () => ({ t: '' }));
  const each = Math.floor((chars - JSON.stringify(rows).length) / count);
  for (const row of rows) row.t = 'x'.repeat(each);
  // Integer division leaves a remainder; put it on the first row so the total
  // lands on `chars` exactly, which is what makes the boundary test meaningful.
  rows[0].t += 'x'.repeat(chars - JSON.stringify(rows).length);
  return rows;
}

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
      { table: 'news_feed', nctIds: ['NCT00006368'], limit: 10 },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].filters).toContainEqual({
      operator: 'overlaps',
      column: 'nct_ids',
      value: ['NCT00006368'],
    });
  });

  it('projects the interventions column, so treatments need no second table', async () => {
    // The whole reason a phase-3 "which treatments" question used to fan out
    // into an unfiltered trial_landscape scan: this table could filter by phase
    // and status but its projection carried no treatment names.
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW] } });

    await tools.query_proprietary_data.execute!({ table: 'clinical_trials', limit: 10 }, RUN_OPTIONS);

    expect(fake.queries[0].projection).toContain('interventions');
  });

  it('keeps intervention names and types but drops the prose around them', async () => {
    // Measured over the 53 Phase 3 active cutaneous melanoma trials: the column
    // as stored is 15,718 tokens, of which 12,594 are `description` and
    // `otherNames`. "Which treatments" is answered by name and type alone.
    const tools = toolsWith({
      clinical_trials: {
        rows: [
          {
            nct_id: 'NCT03470922',
            interventions: [
              {
                name: 'Relatlimab',
                type: 'BIOLOGICAL',
                description: 'Specified dose on specified day',
                otherNames: ['BMS-986016'],
                armGroupLabels: ['Arm A: Relatlimab + Nivolumab'],
              },
            ],
          },
        ],
      },
    });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', phase: 'PHASE3', limit: 500 },
      RUN_OPTIONS,
    );

    const [row] = (result as { rows: Array<{ interventions: unknown[] }> }).rows;
    expect(row.interventions).toEqual([{ name: 'Relatlimab', type: 'BIOLOGICAL' }]);
  });

  it('leaves rows from other tables untouched', async () => {
    const tools = toolsWith({
      trial_landscape: { rows: [{ nct_id: 'NCT03470922', treatment_name: 'Relatlimab + Nivolumab' }] },
    });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', nctIds: ['NCT03470922'], limit: 10 },
      RUN_OPTIONS,
    );

    expect((result as { rows: unknown[] }).rows).toEqual([
      { nct_id: 'NCT03470922', treatment_name: 'Relatlimab + Nivolumab' },
    ]);
  });

  it('matches several trials in one query rather than one call per NCT', async () => {
    const tools = toolsWith({ trial_landscape: { rows: [{ nct_id: 'NCT00006368' }], count: 2 } });

    await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', nctIds: ['NCT00006368', 'NCT00084656'], limit: 500 },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].filters).toContainEqual({
      operator: 'in',
      column: 'nct_id',
      value: ['NCT00006368', 'NCT00084656'],
    });
  });

  it('matches several trials on news_feed, whose trial key is an array column', async () => {
    // `.in()` on a text[] column compares whole arrays; membership needs overlaps.
    const tools = toolsWith({ news_feed: { rows: [{ url: 'https://example.test/a' }] } });

    await tools.query_proprietary_data.execute!(
      { table: 'news_feed', nctIds: ['NCT00006368', 'NCT00084656'], limit: 500 },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].filters).toContainEqual({
      operator: 'overlaps',
      column: 'nct_ids',
      value: ['NCT00006368', 'NCT00084656'],
    });
  });

  it('refuses a large limit when nothing but cancer scope narrows the query', async () => {
    // 500 unfiltered trial_landscape rows measured 48k tokens, of which 3 rows
    // were relevant. The row cap alone never stopped this.
    const tools = toolsWith({ trial_landscape: { rows: [{ nct_id: 'NCT00006368' }], count: 2163 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', limit: 500 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({ ok: false, reason: 'unfiltered_sweep', table: 'trial_landscape' });
    expect(fake.queries).toHaveLength(0);
  });

  it('allows a large limit once a filter narrows the query', async () => {
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW], count: 53 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', phase: 'PHASE3', limit: 500 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({ ok: true });
  });

  it('allows an unfiltered browse at the default limit, so "what exists" still works', async () => {
    const tools = toolsWith({ trial_landscape: { rows: [{ nct_id: 'NCT00006368' }], count: 2163 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', limit: 25 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({ ok: true });
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
    // the sponsor's wording. Without it the model can only assert our tag. It
    // costs 8.3% of a 53-row sweep, so it moved behind `detailed` rather than
    // being dropped - a question about our tagging asks for it explicitly.
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW] } });

    await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', detail: 'detailed', limit: 10 },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].projection).toContain('cancer_type_evidence');
  });

  it('projects only the columns an answer is built from unless asked for more', async () => {
    // 16 columns on every call measured 24,137 tokens over 53 trials through
    // `count_tokens`; the seven an answer is actually made of measure 11,982. The
    // difference was re-sent on every later step of the turn.
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW] } });

    await tools.query_proprietary_data.execute!({ table: 'clinical_trials', limit: 10 }, RUN_OPTIONS);

    const columns = fake.queries[0].projection.split(',').map((c) => c.trim());
    expect(columns).toEqual([
      'nct_id',
      'acronym',
      'brief_title',
      'overall_status',
      'phases',
      'lead_sponsor_name',
      'interventions',
    ]);
  });

  it('keeps the filter columns that still vary in the result', async () => {
    // `phases` and `overall_status` are filters, but neither predicate is an
    // equality: 10 of 53 Phase 3 trials are PHASE2/PHASE3, and the status filter
    // admits four values. `cancer_type` is pinned to one value, so it goes.
    const tools = toolsWith({ clinical_trials: { rows: [TRIAL_ROW] } });

    await tools.query_proprietary_data.execute!({ table: 'clinical_trials', limit: 10 }, RUN_OPTIONS);

    const { projection } = fake.queries[0];
    expect(projection).toContain('phases');
    expect(projection).toContain('overall_status');
    expect(projection).not.toContain('cancer_type');
    expect(projection).not.toContain('study_type');
  });

  it('falls back to the full projection for a table with no concise form', async () => {
    const tools = toolsWith({ trial_outcomes: { rows: [{ id: 'o1' }] } });

    await tools.query_proprietary_data.execute!({ table: 'trial_outcomes', limit: 10 }, RUN_OPTIONS);
    await tools.query_proprietary_data.execute!(
      { table: 'trial_outcomes', detail: 'detailed', limit: 10 },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].projection).toBe(fake.queries[1].projection);
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

  it('reports which requested trials had no row, so an absence is not read as completeness', async () => {
    // 53 Phase 3 trials asked of `trial_landscape` came back as 48 rows and
    // `complete: true` - true of the table, false of the question. The five
    // uncurated trials were silently dropped from the answer.
    const tools = toolsWith({
      trial_landscape: { rows: [{ nct_id: 'NCT00006368' }, { nct_id: 'NCT00084656' }], count: 2 },
    });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', nctIds: ['NCT00006368', 'NCT00084656', 'NCT00096083'], limit: 500 },
      RUN_OPTIONS,
    );

    const { coverage } = result as {
      coverage: { complete: boolean; requested: number; missing: string[]; hint: string };
    };
    expect(coverage.complete).toBe(true);
    expect(coverage.requested).toBe(3);
    expect(coverage.missing).toEqual(['NCT00096083']);
    expect(coverage.hint).toMatch(/no row/i);
  });

  it('says nothing about missing trials when the result was cut short', async () => {
    // Under truncation "absent from the table" and "not returned yet" are the
    // same shape, so naming one as missing would be a guess.
    const tools = toolsWith({ trial_landscape: { rows: [{ nct_id: 'NCT00006368' }], count: 2 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', nctIds: ['NCT00006368', 'NCT00084656'], limit: 1 },
      RUN_OPTIONS,
    );

    const { coverage } = result as { coverage: { complete: boolean; missing?: string[] } };
    expect(coverage.complete).toBe(false);
    expect(coverage.missing).toBeUndefined();
  });

  it('finds requested trials inside an array trial key', async () => {
    // `news_feed.nct_ids` holds several trials per row, so a key is present if
    // any row's array contains it.
    const tools = toolsWith({
      news_feed: { rows: [{ nct_ids: ['NCT00006368', 'NCT00084656'] }], count: 1 },
    });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'news_feed', nctIds: ['NCT00006368', 'NCT00084656', 'NCT00096083'], limit: 500 },
      RUN_OPTIONS,
    );

    const { coverage } = result as { coverage: { missing: string[] } };
    expect(coverage.missing).toEqual(['NCT00096083']);
  });

  it('blames the size budget, not the limit, when a result is trimmed for size', async () => {
    // The trimming itself belongs to `fitToBudget` below. What only the tool can
    // get wrong is the story it tells about the trim: a result cut for size but
    // reported as cut by `limit` sends the model back for a higher limit that
    // cannot help. `phase` is here only to clear the unfiltered-sweep guard -
    // the fake drives row count from its fixture, not from `limit`.
    const rows = Array.from({ length: 500 }, (_, i) => ({
      nct_id: `NCT1000${String(i).padStart(4, '0')}`,
      brief_title: 'x'.repeat(2000),
    }));
    const tools = toolsWith({ clinical_trials: { rows, count: 500 } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'clinical_trials', phase: 'PHASE3', limit: 500 },
      RUN_OPTIONS,
    );

    const { coverage, rows: kept } = result as {
      coverage: { returned: number; complete: boolean; truncatedBy: string; hint: string };
      rows: unknown[];
    };
    expect(coverage.complete).toBe(false);
    expect(coverage.truncatedBy).toBe('size');
    expect(coverage.hint).toMatch(/narrow the filters/i);
    // The coverage report must describe the payload actually sent, not the
    // row set before trimming.
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
      { table: 'trial_landscape', nctIds: ['NCT99999999'], limit: 10 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({
      ok: false,
      reason: 'no_rows',
      appliedFilters: { nctIds: ['NCT99999999'] },
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

describe('clinical_trials projection', () => {
  it('carries the acronym, so a trial has a label shorter than its title', () => {
    // brief_title runs to a median of 116 characters and a max of 272 across
    // the Phase 3 melanoma set. acronym is null on 30 of those 53, so it is a
    // second label rather than a replacement.
    expect(projectionFor('clinical_trials', 'concise')).toContain('acronym');
    expect(projectionFor('clinical_trials', 'detailed')).toContain('acronym');
  });
});

describe('fitToBudget', () => {
  it('passes a payload under the budget through untouched', () => {
    const rows = rowsOfSize(MAX_RESULT_CHARS - 1_000, 10);

    expect(fitToBudget(rows)).toEqual({ kept: rows, droppedForSize: false });
  });

  it('keeps a payload sitting exactly on the budget', () => {
    // The boundary is `<=`. One character either side of it decides whether a
    // whole result gets trimmed, and nothing else pins which way it falls.
    const rows = rowsOfSize(MAX_RESULT_CHARS, 4);
    expect(JSON.stringify(rows)).toHaveLength(MAX_RESULT_CHARS);

    expect(fitToBudget(rows)).toEqual({ kept: rows, droppedForSize: false });
  });

  it('trims from the tail until the payload fits, and says it did', () => {
    const rows = rowsOfSize(MAX_RESULT_CHARS * 3, 60);

    const { kept, droppedForSize } = fitToBudget(rows);

    expect(droppedForSize).toBe(true);
    expect(JSON.stringify(kept).length).toBeLessThanOrEqual(MAX_RESULT_CHARS);
    expect(kept.length).toBeLessThan(rows.length);
    // Tail-trimmed, so what survives is a prefix of the original order.
    expect(kept).toEqual(rows.slice(0, kept.length));
  });

  it('never trims below one row, even when that row alone is over budget', () => {
    // An empty result would read as "no rows matched" - a factual claim about
    // the database rather than about the size of one row.
    const rows = rowsOfSize(MAX_RESULT_CHARS * 2, 1);

    expect(fitToBudget(rows).kept).toEqual(rows);
  });
});
