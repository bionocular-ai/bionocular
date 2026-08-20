import { describe, expect, it } from 'vitest';
import { toResultTable } from './result-table';

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

    expect(table?.columns).toEqual(['nct_id', 'treatment_name', 'modality']);
  });

  it('covers a column that only later rows carry', () => {
    const table = toResultTable({
      ok: true,
      table: 'trial_landscape',
      rows: [{ nct_id: 'NCT00006368' }, { nct_id: 'NCT00084656', modality: 'Small Molecule' }],
    });

    expect(table?.columns).toEqual(['nct_id', 'modality']);
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
});
