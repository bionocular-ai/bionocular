import { describe, expect, it } from 'vitest';
import { orderColumns, toResultTable } from './result-table';

describe('toResultTable', () => {
  it('lists every row the tool returned, never a sample', () => {
    // The whole point. A sweep of 53 trials was written up as 45 because the
    // model transcribed rows into prose and merged the ones sharing a drug.
    const rows = Array.from({ length: 53 }, (_, i) => ({ nct_id: `NCT0000${1000 + i}` }));

    const table = toResultTable({ ok: true, table: 'clinical_trials', rows });

    expect(table?.rows).toHaveLength(53);
  });

  it('takes its columns from the rows, so any table renders without a mapping', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_landscape',
      rows: [{ nct_id: 'NCT00006368', treatment_name: 'Pembrolizumab', modality: 'Monoclonal Antibody' }],
    });

    expect(table?.columns.map((c) => c.key)).toEqual(['nct_id', 'treatment_name', 'modality']);
  });

  it('covers a column that only later rows carry', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_landscape',
      rows: [{ nct_id: 'NCT00006368' }, { nct_id: 'NCT00084656', modality: 'Small Molecule' }],
    });

    expect(table?.columns.map((c) => c.key)).toEqual(['nct_id', 'modality']);
    expect(table?.rows[0]).toEqual(['NCT00006368', '—']);
  });

  it('marks an absent value rather than leaving the cell blank', () => {
    // A trial with no curated landscape row is a fact worth showing, and an
    // empty cell reads as a rendering bug instead.
    const table = toResultTable({
      ok: true,
      table: 'trial_landscape',
      rows: [{ nct_id: 'NCT05522660', modality: null }],
    });

    expect(table?.rows[0]).toEqual(['NCT05522660', '—']);
  });

  it('renders interventions as drug and type instead of raw JSON', () => {
    const table = toResultTable({
      ok: true,
      table: 'clinical_trials',
      rows: [
        {
          nct_id: 'NCT03470922',
          interventions: [
            { name: 'Relatlimab', type: 'BIOLOGICAL' },
            { name: 'Nivolumab', type: 'BIOLOGICAL' },
          ],
        },
      ],
    });

    expect(table?.rows[0][1]).toBe('Relatlimab (BIOLOGICAL), Nivolumab (BIOLOGICAL)');
  });

  it('joins a plain array cell', () => {
    const table = toResultTable({
      ok: true,
      table: 'clinical_trials',
      rows: [{ nct_id: 'NCT03470922', phases: ['PHASE2', 'PHASE3'] }],
    });

    expect(table?.rows[0][1]).toBe('PHASE2, PHASE3');
  });

  it('renders a false boolean as false, not as an absence', () => {
    const table = toResultTable({
      ok: true,
      table: 'clinical_trials',
      rows: [{ nct_id: 'NCT03470922', is_basket: false }],
    });

    expect(table?.rows[0][1]).toBe('false');
  });

  it('has nothing to draw for a failed result', () => {
    const table = toResultTable({ ok: false, reason: 'no_rows', table: 'clinical_trials' });

    expect(table).toBeNull();
  });

  it('has nothing to draw for a lookup_trial result, which is not a row set', () => {
    const table = toResultTable({ found: true, nctId: 'NCT00006368', tables: {} });

    expect(table).toBeNull();
  });

  it('drops a column whose value never changes, because it carries no information', () => {
    // cancer_type is pinned by applyCancerScope, so it repeats down every row of
    // every result. Derived, not named: study_type behaves the same way.
    const table = toResultTable({
      ok: true,
      table: 'trial_landscape',
      rows: [
        { nct_id: 'NCT00006368', cancer_type: ['Cutaneous Melanoma'], modality: 'Monoclonal Antibody' },
        { nct_id: 'NCT00084656', cancer_type: ['Cutaneous Melanoma'], modality: 'Small Molecule' },
      ],
    });

    expect(table?.columns.map((c) => c.key)).toEqual(['nct_id', 'modality']);
  });

  it('keeps a single-row result whole, where every column is trivially uniform', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_landscape',
      rows: [{ nct_id: 'NCT00006368', modality: 'Monoclonal Antibody' }],
    });

    expect(table?.columns.map((c) => c.key)).toEqual(['nct_id', 'modality']);
  });

  it('labels columns for a reader rather than for PostgREST', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_landscape',
      rows: [
        { nct_id: 'NCT00006368', line_of_therapy: '1L', orr: 42 },
        { nct_id: 'NCT00084656', line_of_therapy: 'Adjuvant', orr: 51 },
      ],
    });

    // Lead order puts orr ahead of the columns the lead list does not name.
    expect(table?.columns.map((c) => c.label)).toEqual(['NCT', 'ORR', 'Line of therapy']);
  });
});

describe('censored measurements', () => {
  // `is_nr` and `is_lt` hold column *names*, not values. A null median_dor whose
  // name appears in is_nr means "not reached" - the opposite clinical claim from
  // "no data" - and rendering it as ABSENT states the opposite of the truth.
  it('renders a not-reached measurement as NR rather than as an absence', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT03470922', median_dor: null, is_nr: ['median_dor'] },
        { nct_id: 'NCT07530887', median_dor: 14.2, is_nr: [] },
      ],
    });

    expect(table?.rows[0]).toEqual(['NCT03470922', 'NR']);
    expect(table?.rows[1]).toEqual(['NCT07530887', '14.2']);
  });

  it('renders a censored value as a bound, keeping the number it was stored as', () => {
    // "<1%" is loaded as the number 1 plus the column name in is_lt. Rendered
    // bare it reads as a measured 1%.
    const table = toResultTable({
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT03470922', orr: 1, is_lt: ['orr'] },
        { nct_id: 'NCT07530887', orr: 43, is_lt: [] },
      ],
    });

    expect(table?.rows[0]).toEqual(['NCT03470922', '<1']);
    expect(table?.rows[1]).toEqual(['NCT07530887', '43']);
  });

  it('never renders the marker columns themselves, which describe other cells', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT03470922', median_dor: null, orr: 1, is_nr: ['median_dor'], is_lt: ['orr'] },
        { nct_id: 'NCT07530887', median_dor: 14.2, orr: 43, is_nr: [], is_lt: [] },
      ],
    });

    // Lead order, not projection order: ORR is a headline response metric and
    // ranks ahead of duration of response.
    expect(table?.columns.map((c) => c.key)).toEqual(['nct_id', 'orr', 'median_dor']);
  });

  it('leaves a null alone when no marker names it', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT03470922', median_dor: null, is_nr: ['median_os'] },
        { nct_id: 'NCT07530887', median_dor: 14.2, is_nr: [] },
      ],
    });

    expect(table?.rows[0]).toEqual(['NCT03470922', '—']);
  });
});

describe('orderColumns', () => {
  it('leads with the identity and headline columns, sinking machine keys to the tail', () => {
    // The rendered order used to be whatever the projection listed: 98 columns
    // led by id/source_type/abstract_id, with nct_id 5th and median_pfs 16th.
    expect(
      orderColumns(['id', 'source_type', 'abstract_id', 'nct_id', 'median_pfs', 'generic_name']),
    ).toEqual(['nct_id', 'generic_name', 'median_pfs', 'id', 'source_type', 'abstract_id']);
  });

  it('keeps discovery order among columns it does not name, so an unknown table is untouched', () => {
    expect(orderColumns(['url', 'title', 'date'])).toEqual(['url', 'title', 'date']);
  });

  it('orders a result table, not just a bare key list', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { id: 'o1', source_name: 'ASCO', nct_id: 'NCT03470922', orr: 43 },
        { id: 'o2', source_name: 'ESMO', nct_id: 'NCT07530887', orr: 12 },
      ],
    });

    expect(table?.columns.map((c) => c.key)).toEqual(['nct_id', 'orr', 'id', 'source_name']);
  });
});
