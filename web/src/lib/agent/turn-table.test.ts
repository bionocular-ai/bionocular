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

  it('folds acronym and brief_title into the row rather than rendering either as a column', () => {
    // NCT is already the identity column and a title runs 116-272 characters -
    // long enough to make every row several lines tall. This is the one thing
    // that must not slip: both fields still arrive on every clinical_trials
    // row, and dropping out of the folded list turns them into two new columns.
    const table = toTurnTable([trials, landscape]);

    expect(table?.columns.map((c) => c.key)).not.toContain('acronym');
    expect(table?.columns.map((c) => c.key)).not.toContain('brief_title');
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

    // Sits where treatment_name would have, directly after the key - not at
    // the end, behind whatever other columns the turn happens to carry.
    expect(table?.columns.map((c) => c.key)).toEqual([
      'nct_id',
      'interventions',
      'overall_status',
    ]);
    expect(cell(table, 0, 'interventions')).toBe('Relatlimab (DRUG)');
    expect(cell(table, 1, 'interventions')).toBe('No re-excision (PROCEDURE)');
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

  it('treats a result with duplicate nct_ids as non-joinable, since folding it would keep only the last arm', () => {
    // trial_outcomes is one row per treatment arm, so two arms of the same
    // trial share an nct_id. Folding that into the spine would silently drop
    // every arm but the last, so the whole turn falls back to per-query tables.
    const outcomes = {
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT03470922', arm_name: 'Relatlimab + Nivolumab', orr: 0.43 },
        { nct_id: 'NCT03470922', arm_name: 'Nivolumab', orr: 0.34 },
      ],
    };

    expect(toTurnTable([trials, outcomes])).toBeNull();
  });

  it("keeps an earlier query's real value when a later query carries an explicit null for the same column", () => {
    // cancer_type is projected by more than one query; PostgREST returns it as
    // an explicit null rather than omitting it, and that null must not erase a
    // value a query earlier in the turn already supplied.
    const first = {
      ok: true,
      table: 'clinical_trials',
      rows: [{ nct_id: 'NCT03470922', brief_title: 'x', cancer_type: ['cutaneous melanoma'] }],
    };
    const second = {
      ok: true,
      table: 'trial_landscape',
      rows: [{ nct_id: 'NCT03470922', treatment_name: 'Relatlimab + Nivolumab', cancer_type: null }],
    };

    const table = toTurnTable([first, second]);

    expect(cell(table, 0, 'cancer_type')).toBe('cutaneous melanoma');
  });

  it('keeps the first query\'s order when a middle query introduces a new key, appending it once', () => {
    const middle = {
      ok: true,
      table: 'trial_landscape',
      rows: [
        { nct_id: 'NCT03470922', treatment_name: 'Relatlimab + Nivolumab' },
        { nct_id: 'NCT06112314', treatment_name: 'Brenetafusp + Nivolumab' },
      ],
    };
    const last = {
      ok: true,
      table: 'trial_outcomes_summary',
      rows: [
        { nct_id: 'NCT03470922', orr: 0.43 },
        { nct_id: 'NCT07530887', orr: 0.12 },
      ],
    };

    const table = toTurnTable([trials, middle, last]);

    expect(table?.rows.map((row) => row[0])).toEqual([
      'NCT03470922',
      'NCT07530887',
      'NCT06112314',
    ]);
  });

  it('carries every trial the tools returned, which is what the prose no longer has to', () => {
    const rows = Array.from({ length: 53 }, (_, i) => ({ nct_id: `NCT0000${1000 + i}` }));
    const enriched = rows
      .slice(0, 48)
      .map((row) => ({ ...row, treatment_name: `Drug ${row.nct_id}` }));

    const table = toTurnTable([
      { ok: true, table: 'clinical_trials', rows },
      { ok: true, table: 'trial_landscape', rows: enriched },
    ]);

    expect(table?.rows).toHaveLength(53);
    expect(new Set(table?.rows.map((row) => row[0])).size).toBe(53);
  });
});
