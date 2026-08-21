import { describe, expect, it } from 'vitest';
import { toTurnTable } from './turn-table';

const trials = {
  ok: true,
  table: 'clinical_trials',
  coverage: { returned: 2, matched: 2, complete: true },
  rows: [
    {
      nct_id: 'NCT03470922',
      acronym: 'RELATIVITY-047',
      brief_title: 'A Study of Relatlimab Plus Nivolumab Versus Nivolumab Alone',
      overall_status: 'ACTIVE_NOT_RECRUITING',
      interventions: [{ name: 'Relatlimab', type: 'DRUG' }],
    },
    {
      nct_id: 'NCT07530887',
      acronym: null,
      brief_title: 'NO Re-excision MelanomA - NORMA 2',
      overall_status: 'RECRUITING',
      interventions: [{ name: 'No re-excision', type: 'PROCEDURE' }],
    },
  ],
};

const landscape = {
  ok: true,
  table: 'trial_landscape',
  coverage: { returned: 1, matched: 1, complete: true, requested: 2, missing: ['NCT07530887'] },
  rows: [
    { nct_id: 'NCT03470922', treatment_name: 'Relatlimab + Nivolumab', modality: 'Monoclonal Antibody' },
  ],
};

function cell(table: ReturnType<typeof toTurnTable>, rowIndex: number, key: string): string {
  const column = table!.columns.findIndex((c) => c.key === key);
  return table!.rows[rowIndex][column];
}

describe('toTurnTable', () => {
  it("joins a turn's queries on nct_id rather than stacking two tables", () => {
    const table = toTurnTable([trials, landscape]);

    expect(table?.rows).toHaveLength(2);
    expect(table?.columns.map((c) => c.key)).toEqual([
      'nct_id',
      'trial',
      'overall_status',
      'treatment_name',
      'modality',
    ]);
  });

  it('keeps every trial the first query returned, not only the enriched ones', () => {
    // 48 of the 53 had a curated landscape row. The 5 without one are a finding,
    // and the join must not quietly become an inner one.
    const table = toTurnTable([trials, landscape]);

    expect(table?.rows.map((row) => row[0])).toEqual(['NCT03470922', 'NCT07530887']);
  });

  it('names a trial by acronym, falling back to its title', () => {
    const table = toTurnTable([trials, landscape]);

    expect(cell(table, 0, 'trial')).toBe('RELATIVITY-047');
    expect(cell(table, 1, 'trial')).toBe('NO Re-excision MelanomA - NORMA 2');
  });

  it('fills an uncurated treatment from the registry, and says so', () => {
    // trial_landscape holds one curated regimen per trial; interventions holds
    // every arm the registry lists, comparators included. Same cell, different
    // kind of value, so the source rides on the cell.
    const table = toTurnTable([trials, landscape]);

    expect(cell(table, 0, 'treatment_name')).toBe('Relatlimab + Nivolumab');
    expect(cell(table, 1, 'treatment_name')).toBe('No re-excision (PROCEDURE) · registry');
  });

  it('keeps interventions as its own column when nothing curated joins it', () => {
    const table = toTurnTable([trials, { ...trials, table: 'clinical_trials' }]);

    expect(table?.columns.map((c) => c.key)).toContain('interventions');
  });

  it('appends a trial only a later query carried, rather than dropping it', () => {
    const extra = {
      ok: true,
      table: 'trial_landscape',
      rows: [
        { nct_id: 'NCT03470922', treatment_name: 'Relatlimab + Nivolumab', modality: 'Monoclonal Antibody' },
        { nct_id: 'NCT06112314', treatment_name: 'Brenetafusp + Nivolumab', modality: 'Bispecific' },
      ],
    };
    const table = toTurnTable([trials, extra]);

    expect(table?.rows.map((row) => row[0])).toEqual(['NCT03470922', 'NCT07530887', 'NCT06112314']);
  });

  it('returns null for a turn with one query, which ToolStep already renders', () => {
    expect(toTurnTable([trials])).toBeNull();
  });

  it('ignores a failed query rather than joining against nothing', () => {
    expect(toTurnTable([trials, { ok: false, reason: 'no_rows', table: 'trial_outcomes' }])).toBeNull();
  });

  it('ignores a result with no trial key, which cannot be joined', () => {
    const news = { ok: true, table: 'news_feed', rows: [{ url: 'https://example.test', title: 'x' }] };

    expect(toTurnTable([trials, news])).toBeNull();
  });
});
