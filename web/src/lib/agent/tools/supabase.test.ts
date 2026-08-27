import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createFakeSupabase, type FakeSupabase, type TableFixture } from './fake-supabase';
import { applyNamedFilter, describeTables, embedFor, projectionFor, viaFilters } from './schema';

let fake: FakeSupabase;

vi.mock('@/lib/supabase/service', () => ({
  createServiceClient: () => fake,
}));

const { buildSupabaseTools, dropEmpty, fitToBudget, MAX_RESULT_CHARS, missingTrialKeys } =
  await import('./supabase');

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
    // 16 columns on every call measured 15,492 tokens over 53 trials via
    // `count_tokens` (compact JSON, interventions trimmed); the seven an answer is
    // actually made of measure 7,743. The difference was re-sent on every later
    // step of the turn.
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
    const tools = toolsWith({ km_curves: { rows: [{ id: 'k1' }] } });

    await tools.query_proprietary_data.execute!({ table: 'km_curves', limit: 10 }, RUN_OPTIONS);
    await tools.query_proprietary_data.execute!(
      { table: 'km_curves', detail: 'detailed', limit: 10 },
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

  it('refuses a status filter on tables with no status, direct or via a join', async () => {
    // trial_landscape resolves status through clinical_trials now; news_feed has
    // no nct_id at all, so it gets no `via` and still refuses outright.
    const tools = toolsWith({ news_feed: { rows: [{ url: 'https://example.test/a' }] } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'news_feed', status: ['RECRUITING'], limit: 10 },
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

  it('refuses a filter the table does not have, directly or via a join, instead of ignoring it', async () => {
    // news_feed has no nct_id column at all, so it gets no `via` and stays the
    // one table that still refuses phase outright.
    const tools = toolsWith({ news_feed: { rows: [{ url: 'https://example.test/a' }] } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'news_feed', phase: 'PHASE3', limit: 10 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({ ok: false, reason: 'unsupported_filter', filter: 'phase' });
    expect((result as { supportedFilters: string[] }).supportedFilters).toEqual([]);
  });

  it('reports a via-resolved filter as supported in a refusal, not just the columns this table owns', async () => {
    // trial_landscape has no `sponsor` column, direct or via - a genuine
    // refusal - but it does resolve phase/status through the registry join. A
    // refusal that named only `drug` here would hide the one path that
    // actually answers a phase- or status-scoped question and point the model
    // at the NCT handoff this branch exists to replace.
    const tools = toolsWith({ trial_landscape: { rows: [{ nct_id: 'NCT00006368' }] } });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_landscape', sponsor: 'Bristol', limit: 10 },
      RUN_OPTIONS,
    );

    expect(result).toMatchObject({ ok: false, reason: 'unsupported_filter', filter: 'sponsor' });
    expect((result as { supportedFilters: string[] }).supportedFilters).toEqual(
      expect.arrayContaining(['drug', 'phase', 'status']),
    );
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

describe('trial_outcomes projection', () => {
  // The 202 columns melanoma/data/backups/trial_outcomes_rows.csv carries as of
  // 2026-08-27 - the authoritative source the wide `detailed` projection is
  // built against. That backup is gitignored (melanoma/.gitignore excludes
  // data/backups/), so CI has no copy to read live; the header is pinned here
  // instead. `is_lt` postdates this backup (added by migration
  // 20260805000000_trial_outcomes_validation_columns.sql) and is added to the
  // known set by hand below rather than appearing in this list.
  const CSV_HEADER_COLUMNS = [
    'id', 'source_type', 'source_name', 'abstract_id', 'publication_id', 'source_url',
    'nct_id', 'arm_id', 'arm_name', 'cancer_type', 'sponsors', 'line_of_treatment',
    'generic_name', 'brand_name', 'dosage', 'type_of_dosing', 'mechanism_of_action',
    'target_protein', 'type_of_therapy', 'sub_therapy', 'median_age', 'num_patients',
    'median_pfs', 'pfs_followup_months', 'p_value_pfs', 'hr_pfs', 'pfs_rate_6m',
    'pfs_rate_9m', 'pfs_rate_12m', 'pfs_rate_18m', 'pfs_rate_24m', 'pfs_rate_36m',
    'pfs_rate_48m', 'median_os', 'os_followup_months', 'p_value_os', 'hr_os', 'os_rate_6m',
    'os_rate_9m', 'os_rate_12m', 'os_rate_18m', 'os_rate_24m', 'os_rate_36m', 'os_rate_48m',
    'efs', 'p_value_efs', 'hr_efs', 'rfs', 'p_value_rfs', 'rfs_followup_months', 'hr_rfs',
    'mfs', 'mfs_followup_months', 'hr_mfs', 'orr', 'cr', 'pcr', 'cmr', 'dcr', 'cbr',
    'median_dor', 'dor_rate', 'ttr', 'ttp', 'ttnt', 'ttf', 'ae_pct', 'grade_3_plus_ae_pct',
    'ae_leading_to_discontinuation_pct', 'serious_ae_pct', 'immune_related_ae_pct',
    'serious_ir_ae_pct', 'ae_death_pct', 'trae_pct', 'grade_3_plus_trae_pct',
    'grade_3_trae_pct', 'grade_4_trae_pct', 'grade_5_trae_pct', 'trae_discontinuation_pct',
    'trae_death_pct', 'trae_ir_ae_pct', 'serious_trae_pct', 'teae_pct',
    'grade_3_plus_teae_pct', 'grade_3_teae_pct', 'grade_4_teae_pct', 'grade_5_teae_pct',
    'teae_discontinuation_pct', 'teae_death_pct', 'teae_ir_ae_pct', 'serious_teae_pct',
    'crs_pct', 'wbc_decreased_pct', 'grade_3_plus_ae_ir_ae', 'grade_3_plus_ae_crs',
    'grade_3_plus_ae_thrombocytopenia', 'grade_3_plus_ae_neutropenia',
    'grade_3_plus_ae_leukopenia', 'grade_3_plus_ae_nausea', 'grade_3_plus_ae_anemia',
    'grade_3_plus_ae_diarrhea', 'grade_3_plus_ae_colitis', 'grade_3_plus_ae_hyperglycemia',
    'grade_3_plus_ae_neutrophil_count_decreased', 'grade_3_plus_ae_dyspnea',
    'grade_3_plus_ae_pyrexia', 'grade_3_plus_ae_bleeding', 'grade_3_plus_ae_pruritus',
    'grade_3_plus_ae_rash', 'grade_3_plus_ae_pneumonia', 'grade_3_plus_ae_thyroiditis',
    'grade_3_plus_ae_hypophysitis', 'grade_3_plus_ae_hepatitis',
    'grade_3_plus_ae_pneumonitis', 'grade_3_plus_ae_alt_increased',
    'grade_3_plus_ae_wbc_decreased', 'grade_3_plus_trae_ir_ae', 'grade_3_plus_trae_crs',
    'grade_3_plus_trae_thrombocytopenia', 'grade_3_plus_trae_neutropenia',
    'grade_3_plus_trae_leukopenia', 'grade_3_plus_trae_nausea', 'grade_3_plus_trae_anemia',
    'grade_3_plus_trae_diarrhea', 'grade_3_plus_trae_colitis',
    'grade_3_plus_trae_hyperglycemia', 'grade_3_plus_trae_neutrophil_count_decreased',
    'grade_3_plus_trae_dyspnea', 'grade_3_plus_trae_pyrexia', 'grade_3_plus_trae_bleeding',
    'grade_3_plus_trae_pruritus', 'grade_3_plus_trae_rash', 'grade_3_plus_trae_pneumonia',
    'grade_3_plus_trae_thyroiditis', 'grade_3_plus_trae_hypophysitis',
    'grade_3_plus_trae_hepatitis', 'grade_3_plus_trae_pneumonitis',
    'grade_3_plus_trae_alt_increased', 'grade_3_plus_trae_wbc_decreased',
    'grade_3_plus_teae_ir_ae', 'grade_3_plus_teae_crs', 'grade_3_plus_teae_thrombocytopenia',
    'grade_3_plus_teae_neutropenia', 'grade_3_plus_teae_leukopenia',
    'grade_3_plus_teae_nausea', 'grade_3_plus_teae_anemia', 'grade_3_plus_teae_diarrhea',
    'grade_3_plus_teae_colitis', 'grade_3_plus_teae_hyperglycemia',
    'grade_3_plus_teae_neutrophil_count_decreased', 'grade_3_plus_teae_dyspnea',
    'grade_3_plus_teae_pyrexia', 'grade_3_plus_teae_bleeding', 'grade_3_plus_teae_pruritus',
    'grade_3_plus_teae_rash', 'grade_3_plus_teae_pneumonia', 'grade_3_plus_teae_thyroiditis',
    'grade_3_plus_teae_hypophysitis', 'grade_3_plus_teae_hepatitis',
    'grade_3_plus_teae_pneumonitis', 'grade_3_plus_teae_alt_increased',
    'grade_3_plus_teae_wbc_decreased', 'confidence', 'is_nr', 'all_attributes', 'created_at',
    'ci_hr_pfs', 'ci_hr_os', 'ci_hr_efs', 'ci_hr_rfs', 'ci_hr_mfs', 'ci_hr_ttp', 'hr_ttp',
    'ae_dose_interruption_pct', 'ae_dose_reduction_pct', 'ae_hospitalization_pct',
    'teae_dose_interruption_pct', 'teae_dose_reduction_pct', 'teae_hospitalization_pct',
    'trae_dose_interruption_pct', 'trae_dose_reduction_pct', 'trae_hospitalization_pct',
    'irr_pct', 'grade_3_plus_ae_ast_increased', 'grade_3_plus_ae_fatigue',
    'grade_3_plus_ae_hyperthyroidism', 'grade_3_plus_ae_hypothyroidism',
    'grade_3_plus_ae_irr', 'grade_3_plus_ae_vomiting', 'grade_3_plus_teae_ast_increased',
    'grade_3_plus_teae_fatigue', 'grade_3_plus_teae_hyperthyroidism',
    'grade_3_plus_teae_hypothyroidism', 'grade_3_plus_teae_irr', 'grade_3_plus_teae_vomiting',
    'grade_3_plus_trae_ast_increased', 'grade_3_plus_trae_fatigue',
    'grade_3_plus_trae_hyperthyroidism', 'grade_3_plus_trae_hypothyroidism',
    'grade_3_plus_trae_irr', 'grade_3_plus_trae_vomiting', 'modality',
  ];

  const KNOWN_COLUMNS = new Set([...CSV_HEADER_COLUMNS, 'is_lt']);
  const EXCLUDED_COLUMNS = ['all_attributes', 'created_at', 'cancer_type', 'source_url', 'confidence'];

  function columns(detail: 'concise' | 'detailed'): string[] {
    return projectionFor('trial_outcomes', detail)
      .split(',')
      .map((c) => c.trim());
  }

  it('widens the detailed projection well past the concise browse level', () => {
    const concise = columns('concise');
    const detailed = columns('detailed');

    expect(detailed.length).toBeGreaterThan(concise.length * 5);
    expect(concise).toContain('is_nr');
    expect(concise).toContain('is_lt');
    expect(detailed).toContain('is_nr');
    expect(detailed).toContain('is_lt');
  });

  it('never selects a column absent from the loader\'s own column list', () => {
    for (const column of columns('detailed')) {
      expect(KNOWN_COLUMNS.has(column)).toBe(true);
    }
  });

  it('excludes the shadow copy, scope-pinned, and metadata columns', () => {
    const detailed = columns('detailed');
    for (const excluded of EXCLUDED_COLUMNS) {
      expect(detailed).not.toContain(excluded);
    }
  });
});

describe('tool description text', () => {
  it('tells the model a via-filter joins through the registry and what that excludes', () => {
    const tools = toolsWith();

    expect(tools.query_proprietary_data.description).toMatch(/via clinical_trials/);
    expect(tools.query_proprietary_data.description).toMatch(/excludes rows with no nct_id/);
    expect(tools.query_proprietary_data.description).toMatch(/coverage\.viaJoin/);
  });

  it('describes `detailed` as the full endpoint set on trial_outcomes, not a clinical_trials-only column list', () => {
    const tools = toolsWith();
    // The SDK types `inputSchema` as its own `FlexibleSchema`, which erases the
    // zod object's `.shape` - the schema passed in is still a real ZodObject at
    // runtime, so this reaches back through that type to read field descriptions.
    const { detail, phase, status } = (
      tools.query_proprietary_data.inputSchema as unknown as { shape: Record<string, { description?: string }> }
    ).shape;

    expect(detail.description).toMatch(/trial_outcomes/);
    expect(detail.description).toMatch(/efficacy and safety endpoint/);
    // The old wording justified `detailed` only in clinical_trials terms, which
    // steered the model away from the one table where `detailed` holds the
    // endpoints the reference question asks for.
    expect(detail.description).not.toMatch(/only when the question is about those columns/);

    // phase/status used to claim "clinical_trials only", which is now false:
    // both are resolved through the via-join on the other four tables.
    expect(phase.description).not.toMatch(/clinical_trials only\.?$/);
    expect(status.description).not.toMatch(/^clinical_trials only\./);
    expect(phase.description).toMatch(/via the join/);
    expect(status.description).toMatch(/via the join/);
  });
});

describe('via joins', () => {
  it('resolves phase and status through the via table, and nothing else requested', () => {
    expect(viaFilters('trial_outcomes', ['sponsor', 'phase', 'status', 'drug'])).toEqual([
      'phase',
      'status',
    ]);
    expect(viaFilters('trial_landscape', ['phase'])).toEqual(['phase']);
    expect(viaFilters('km_curves', ['status'])).toEqual(['status']);
  });

  it('resolves nothing for a table with no via', () => {
    expect(viaFilters('news_feed', ['phase', 'status'])).toEqual([]);
    // clinical_trials holds phase/status directly, not through a join.
    expect(viaFilters('clinical_trials', ['phase', 'status'])).toEqual([]);
  });

  it('embeds the join only when a via-filter is active', () => {
    expect(embedFor('trial_outcomes', ['phase'])).toBe(',clinical_trials!inner(phases,overall_status)');
  });

  it('never embeds when no via-filter is active - an `!inner` join would drop unlinked rows', () => {
    expect(embedFor('trial_outcomes', [])).toBe('');
  });

  it('never embeds for a table with no via, even if asked', () => {
    expect(embedFor('news_feed', ['phase'])).toBe('');
    expect(embedFor('clinical_trials', ['phase'])).toBe('');
  });

  it('applies a via array filter to the dotted clinical_trials path', () => {
    const fake = createFakeSupabase();
    const query = fake.from('trial_outcomes').select('id');

    applyNamedFilter(query, 'trial_outcomes', 'phase', 'PHASE1');

    expect(fake.queries[0].filters).toContainEqual({
      operator: 'contains',
      column: 'clinical_trials.phases',
      value: ['PHASE1'],
    });
  });

  it('applies a via exact filter with eq for one value, in for several', () => {
    const fake = createFakeSupabase();
    const single = fake.from('km_curves').select('id');
    applyNamedFilter(single, 'km_curves', 'status', ['ACTIVE_NOT_RECRUITING']);
    expect(fake.queries[0].filters).toContainEqual({
      operator: 'eq',
      column: 'clinical_trials.overall_status',
      value: 'ACTIVE_NOT_RECRUITING',
    });

    const several = fake.from('km_curves').select('id');
    applyNamedFilter(several, 'km_curves', 'status', ['RECRUITING', 'ACTIVE_NOT_RECRUITING']);
    expect(fake.queries[1].filters).toContainEqual({
      operator: 'in',
      column: 'clinical_trials.overall_status',
      value: ['RECRUITING', 'ACTIVE_NOT_RECRUITING'],
    });
  });

  it('still returns null when neither the table nor its via-table has the filter', () => {
    const fake = createFakeSupabase();
    const query = fake.from('trial_landscape').select('id');

    expect(applyNamedFilter(query, 'trial_landscape', 'sponsor', 'Bristol')).toBeNull();
  });

  it('names via-filters distinctly from a table\'s own filters in the tool description', () => {
    const text = describeTables();

    expect(text).toContain('filters: sponsor, drug (phase, status via clinical_trials)');
    expect(text).toContain('filters: drug (phase, status via clinical_trials)');
    // news_feed has no via at all - the description must not invent one.
    expect(text).not.toMatch(/news_feed.*via clinical_trials/);
  });
});

describe('via joins through the real tool entry point', () => {
  // Task 1's review flagged that the via accept-path was tested only by
  // calling schema.ts's exports directly, never through
  // tools.query_proprietary_data.execute - the crux of this task is the
  // ordering trap where the select has to be built before the filter loop
  // runs, and only a call through the real tool can catch a regression there.

  it('embeds the join and filters on it when a via-filter is active', async () => {
    const tools = toolsWith({ trial_outcomes: { rows: [{ id: 'o1', nct_id: 'NCT00006368' }] } });

    await tools.query_proprietary_data.execute!(
      { table: 'trial_outcomes', phase: 'PHASE1', limit: 10 },
      RUN_OPTIONS,
    );

    expect(fake.queries[0].projection).toContain('clinical_trials!inner(');
    expect(fake.queries[0].filters).toContainEqual({
      operator: 'contains',
      column: 'clinical_trials.phases',
      value: ['PHASE1'],
    });
  });

  it('never embeds the join without an active via-filter, or 44% of the table silently vanishes', async () => {
    const tools = toolsWith({ trial_outcomes: { rows: [{ id: 'o1', nct_id: 'NCT00006368' }] } });

    await tools.query_proprietary_data.execute!({ table: 'trial_outcomes', limit: 10 }, RUN_OPTIONS);

    expect(fake.queries[0].projection).not.toContain('!inner');
  });

  it('flattens the clinical_trials embed onto the row', async () => {
    const tools = toolsWith({
      trial_outcomes: {
        rows: [
          {
            id: 'o1',
            nct_id: 'NCT00006368',
            clinical_trials: { phases: ['PHASE1'], overall_status: 'RECRUITING' },
          },
        ],
      },
    });

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_outcomes', phase: 'PHASE1', limit: 10 },
      RUN_OPTIONS,
    );

    const [row] = (result as { rows: Array<Record<string, unknown>> }).rows;
    expect(row).toMatchObject({ phases: ['PHASE1'], overall_status: 'RECRUITING' });
    expect(row).not.toHaveProperty('clinical_trials');
  });

  it('adds coverage.viaJoin with the unlinked count only when a via-filter fired', async () => {
    const tools = toolsWith({
      trial_outcomes: {
        rows: [{ id: 'o1', nct_id: 'NCT00006368' }],
        count: 189,
        unlinkedCount: 713,
      },
    });

    const withVia = await tools.query_proprietary_data.execute!(
      { table: 'trial_outcomes', phase: 'PHASE1', limit: 10 },
      RUN_OPTIONS,
    );
    const { coverage: viaCoverage } = withVia as {
      coverage: { viaJoin?: { table: string; unlinked?: number; hint: string } };
    };
    expect(viaCoverage.viaJoin).toMatchObject({ table: 'clinical_trials', unlinked: 713 });
    expect(viaCoverage.viaJoin?.hint).toMatch(/no nct_id/i);
    // The count-only check runs against the same table, scoped the same way,
    // filtering for a null trial key - not a second read of clinical_trials.
    const countQuery = fake.queries[1];
    expect(countQuery.table).toBe('trial_outcomes');
    expect(countQuery.head).toBe(true);
    expect(countQuery.filters).toContainEqual({ operator: 'is', column: 'nct_id', value: null });

    const withoutVia = await tools.query_proprietary_data.execute!(
      { table: 'trial_outcomes', limit: 10 },
      RUN_OPTIONS,
    );
    const { coverage: plainCoverage } = withoutVia as { coverage: { viaJoin?: unknown } };
    expect(plainCoverage.viaJoin).toBeUndefined();
  });

  it('omits the unlinked number, but keeps the caveat, when the count query fails', async () => {
    const fake1 = createFakeSupabase({ trial_outcomes: { rows: [{ id: 'o1', nct_id: 'NCT00006368' }] } });
    let call = 0;
    const original = fake1.from;
    fake1.from = (table: string) => {
      call += 1;
      if (call === 2) {
        return createFakeSupabase({
          [table]: { error: { code: '500', message: 'boom' } },
        }).from(table);
      }
      return original(table);
    };
    fake = fake1;
    const tools = buildSupabaseTools(CONTEXT);

    const result = await tools.query_proprietary_data.execute!(
      { table: 'trial_outcomes', phase: 'PHASE1', limit: 10 },
      RUN_OPTIONS,
    );

    const { coverage } = result as { coverage: { viaJoin?: { unlinked?: number; hint: string } } };
    expect(coverage.viaJoin?.unlinked).toBeUndefined();
    expect(coverage.viaJoin?.hint).toMatch(/no nct_id/i);
  });
});

describe('dropEmpty', () => {
  it('removes null, empty-string, N/A, Not found and empty-array values', () => {
    const rows = [
      {
        a: null,
        b: undefined,
        c: '',
        d: 'N/A',
        e: 'Not found',
        f: [],
        g: 'kept',
        h: ['kept'],
      },
    ];

    expect(dropEmpty(rows)).toEqual([{ g: 'kept', h: ['kept'] }]);
  });

  it('keeps 0 and false - a real measurement, not an absence', () => {
    const rows = [{ pct: 0, flag: false }];

    expect(dropEmpty(rows)).toEqual([{ pct: 0, flag: false }]);
  });

  it('leaves non-object rows untouched', () => {
    expect(dropEmpty(['x', 1, null])).toEqual(['x', 1, null]);
  });
});

describe('missingTrialKeys after dropEmpty removes a null key entirely', () => {
  it('still treats the trial as absent when its nct_id key is gone rather than null', () => {
    // dropEmpty strips a null nct_id from the row instead of leaving it null,
    // so row[key.column] reads as `undefined`. missingTrialKeys must treat
    // that the same as an explicit null - both mean "not a string", so the
    // trial counts as not covered by this row.
    const rows = dropEmpty([{ id: 'o1', nct_id: null, abstract_id: 'A1' }]);
    expect(rows[0]).not.toHaveProperty('nct_id');

    const key = { column: 'nct_id', kind: 'scalar' as const };
    expect(missingTrialKeys(rows, key, ['NCT00006368'])).toEqual(['NCT00006368']);
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
