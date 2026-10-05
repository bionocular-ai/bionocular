import { describe, expect, it } from 'vitest';
import { toTurnTable, withoutAskedPhase } from './turn-table';

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
      'treatment_name',
      'nct_id',
      'modality',
      'overall_status',
    ]);
  });

  it('keeps every trial the first query returned, not only the enriched ones', () => {
    // 48 of the 53 had a curated landscape row. The 5 without one are a finding,
    // and the join must not quietly become an inner one.
    const table = toTurnTable([trials, landscape]);

    expect(table!.rows.map((_, i) => cell(table, i, 'nct_id'))).toEqual(['NCT03470922', 'NCT07530887']);
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
      'interventions',
      'nct_id',
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

    expect(table!.rows.map((_, i) => cell(table, i, 'nct_id'))).toEqual(['NCT03470922', 'NCT07530887', 'NCT06112314']);
  });

  it("renders a turn's only query, since there is nothing to join and it is the answer", () => {
    const table = toTurnTable([trials]);

    expect(table?.rows).toHaveLength(2);
    expect(table!.rows.map((_, i) => cell(table, i, 'nct_id'))).toEqual(['NCT03470922', 'NCT07530887']);
  });

  it('folds acronym and brief_title on a single-query turn too, not only the joined path', () => {
    // clinical_trials.conciseProjection carries both on every row; a single
    // Phase 3 sweep with nothing to join used to render them as columns -
    // 116-272 characters wide, several lines tall - even though the join path
    // already folds them.
    const table = toTurnTable([trials]);

    expect(table?.columns.map((c) => c.key)).not.toContain('acronym');
    expect(table?.columns.map((c) => c.key)).not.toContain('brief_title');
  });

  it('renders a lone query with duplicate nct_ids, since there is no join spine to corrupt', () => {
    // trial_outcomes is one row per treatment arm; two arms of the same trial
    // share an nct_id. That rule protects a *join*, and a single query never
    // joins anything.
    const outcomes = {
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT03470922', arm_name: 'Relatlimab + Nivolumab', orr: 0.43 },
        { nct_id: 'NCT03470922', arm_name: 'Nivolumab', orr: 0.34 },
      ],
    };

    const table = toTurnTable([outcomes]);

    expect(table?.rows).toHaveLength(2);
    expect(table?.columns.map((c) => c.key)).toEqual(['treatment_name', 'nct_id', 'setting', 'sponsor_type', 'biomarker', 'orr']);
  });

  it('renders a lone query with no nct_id column at all', () => {
    const news = { ok: true, table: 'news_feed', rows: [{ url: 'https://example.test', title: 'x' }] };

    const table = toTurnTable([news]);

    expect(table?.rows).toHaveLength(1);
    expect(table?.columns.map((c) => c.key)).toEqual(['url', 'title']);
  });

  it('renders the one successful query when the other query in the turn failed', () => {
    // A failed query is not a second query - the turn still has exactly one
    // answer to draw.
    const table = toTurnTable([trials, { ok: false, reason: 'no_rows', table: 'trial_outcomes' }]);

    expect(table?.rows).toHaveLength(2);
    expect(table!.rows.map((_, i) => cell(table, i, 'nct_id'))).toEqual(['NCT03470922', 'NCT07530887']);
  });

  it('returns null for a turn where every query failed', () => {
    expect(toTurnTable([{ ok: false, reason: 'no_rows', table: 'trial_outcomes' }])).toBeNull();
  });

  it('draws the last result when a result with no trial key leaves nothing to join', () => {
    const news = { ok: true, table: 'news_feed', rows: [{ url: 'https://example.test', title: 'x' }] };

    expect(toTurnTable([trials, news])?.columns.map((c) => c.key)).toEqual(['url', 'title']);
  });

  it('never leaves an approvals turn tableless: beside the landscape, or re-read by drug', () => {
    // The standard-of-care skill reads approvals together with the landscape,
    // and a drug question re-reads approvals filtered. Neither joins on nct_id.
    const approvals = {
      ok: true,
      table: 'approved_therapies',
      rows: [
        { treatment_name: 'Nivolumab', setting: 'Adjuvant', us_status: 'Off label', sheet_row: 9 },
        { treatment_name: 'Ipilimumab + Nivolumab', setting: '1L+ Advanced', us_status: 'On-label (generic)', sheet_row: 17 },
      ],
    };
    const nivolumabOnly = { ...approvals, rows: [approvals.rows[0]] };

    expect(toTurnTable([landscape, approvals])?.columns.map((c) => c.key)).toEqual(['treatment_name', 'setting', 'us_status']);
    expect(toTurnTable([approvals, nivolumabOnly])?.rows).toHaveLength(1);
  });

  it('draws the outcomes result rather than folding its arms into the registry join', () => {
    // trial_outcomes is one row per treatment arm, so two arms of the same
    // trial share an nct_id. Folding that into the spine would silently drop
    // every arm but the last; the arms are the answer, so they are the table.
    const outcomes = {
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT03470922', arm_name: 'Relatlimab + Nivolumab', orr: 0.43 },
        { nct_id: 'NCT03470922', arm_name: 'Nivolumab', orr: 0.34 },
      ],
    };

    const table = toTurnTable([trials, outcomes]);

    expect(table?.rows).toHaveLength(2);
    expect(cell(table, 1, 'treatment_name')).toBe('Nivolumab');
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

    expect(table!.rows.map((_, i) => cell(table, i, 'nct_id'))).toEqual([
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
    expect(new Set(table!.rows.map((_, i) => cell(table, i, 'nct_id'))).size).toBe(53);
  });

  it('renders a censored measurement when the registry was queried beside the outcomes', () => {
    const outcomes = {
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT03470922', median_dor: null, is_nr: ['median_dor'] },
        { nct_id: 'NCT07530887', median_dor: 14.2, is_nr: [] },
      ],
    };

    const table = toTurnTable([trials, outcomes]);

    expect(cell(table, 0, 'median_dor')).toBe('NR');
    expect(cell(table, 1, 'median_dor')).toBe('14.2');
    expect(table?.columns.map((c) => c.key)).not.toContain('is_nr');
  });
});

describe('derived columns', () => {
  // The three facts the landscape artifact led with and the recorded answer
  // could not state: which setting a trial belongs to, whether its sponsor is
  // industry, and whether "active" still means enrolling. Each is a rule over
  // columns the rows already carry, so the app derives them - the same way
  // every time, with no model in the loop.
  const today = new Date('2026-09-22');

  function registry(rows: Record<string, unknown>[]) {
    return { ok: true, table: 'clinical_trials', rows };
  }

  it('places a trial by setting: peri-operative beats advanced, advanced beats the procedural rule', () => {
    const curated = {
      ok: true,
      table: 'trial_landscape',
      rows: [
        { nct_id: 'NCT1', line_of_therapy: '1L; Adjuvant', modality: 'Monoclonal Antibody' },
        { nct_id: 'NCT2', line_of_therapy: 'R/R', modality: 'Radiotherapy' },
        { nct_id: 'NCT3', line_of_therapy: null, modality: 'Surgery/Procedure' },
        { nct_id: 'NCT4', line_of_therapy: null, modality: 'Monoclonal Antibody' },
      ],
    };
    const trials = registry([
      { nct_id: 'NCT1', primary_purpose: 'TREATMENT' },
      { nct_id: 'NCT2', primary_purpose: 'TREATMENT' },
      { nct_id: 'NCT3', primary_purpose: 'TREATMENT' },
      { nct_id: 'NCT4', primary_purpose: 'TREATMENT' },
    ]);

    const table = toTurnTable([trials, curated], today);

    expect([0, 1, 2, 3].map((i) => cell(table, i, 'setting'))).toEqual([
      'Peri-operative',
      'Advanced / metastatic',
      'Procedural / supportive',
      'Unclassified',
    ]);
  });

  it('places an uncurated diagnostic trial by its registry purpose, since it has no modality to go on', () => {
    const trials = registry([
      { nct_id: 'NCT1', primary_purpose: 'DIAGNOSTIC' },
      { nct_id: 'NCT2', primary_purpose: 'TREATMENT' },
    ]);

    const table = toTurnTable([trials], today);

    expect(cell(table, 0, 'setting')).toBe('Procedural / supportive');
    expect(cell(table, 1, 'setting')).toBe('Unclassified');
  });

  it('splits sponsors into industry and non-industry, which is the registry partition the product uses', () => {
    const trials = registry([
      { nct_id: 'NCT1', lead_sponsor_class: 'INDUSTRY' },
      { nct_id: 'NCT2', lead_sponsor_class: 'NIH' },
      { nct_id: 'NCT3', lead_sponsor_class: 'OTHER' },
    ]);

    const table = toTurnTable([trials], today);

    expect([0, 1, 2].map((i) => cell(table, i, 'sponsor_type'))).toEqual(['Industry', 'Non-industry', 'Non-industry']);
  });

  it('flags an active-not-recruiting trial as follow-up only once its primary completion date has passed', () => {
    const trials = registry([
      { nct_id: 'NCT1', overall_status: 'ACTIVE_NOT_RECRUITING', primary_completion_date: '2021-06-21' },
      { nct_id: 'NCT2', overall_status: 'ACTIVE_NOT_RECRUITING', primary_completion_date: '2027-03-31' },
      { nct_id: 'NCT3', overall_status: 'RECRUITING', primary_completion_date: '2021-06-21' },
      { nct_id: 'NCT4', overall_status: 'ACTIVE_NOT_RECRUITING', primary_completion_date: null },
    ]);

    const table = toTurnTable([trials], today);

    expect([0, 1, 2, 3].map((i) => cell(table, i, 'follow_up_only'))).toEqual(['yes', '—', '—', '—']);
  });

  it('treats a month-precision completion date as the end of that month, not its first day', () => {
    const trials = registry([
      { nct_id: 'NCT1', overall_status: 'ACTIVE_NOT_RECRUITING', primary_completion_date: '2026-09' },
      { nct_id: 'NCT2', overall_status: 'ACTIVE_NOT_RECRUITING', primary_completion_date: '2026-08' },
    ]);

    const table = toTurnTable([trials], today);

    expect(cell(table, 0, 'follow_up_only')).toBe('—');
    expect(cell(table, 1, 'follow_up_only')).toBe('yes');
  });

  it('gives an outcomes table its line section and the two trial facts every answer states', () => {
    const outcomes = {
      ok: true,
      table: 'trial_outcomes',
      rows: [{ nct_id: 'NCT1', arm_name: 'A', orr: 43 }],
    };

    const table = toTurnTable([outcomes], today);

    expect(table?.columns.map((c) => c.key)).toEqual(['treatment_name', 'nct_id', 'setting', 'sponsor_type', 'biomarker', 'orr']);
  });
});

// Session b38c68c7: "efficacy in active Phase 1 trials". The model queried
// outcomes, then the landscape and the registry, then outcomes again with the
// status filter. Every table drawn along the way must be an outcomes table.
const phase1Outcomes = {
  ok: true,
  table: 'trial_outcomes',
  rows: [
    {
      id: 1, arm_id: 'a1', source_type: 'abstract', abstract_id: 'ASCO_2023_9511', nct_id: 'NCT01989585',
      arm_name: 'Dabrafenib + Trametinib', num_patients: 25, orr: 80, cr: 15,
      os_followup_months: 25.9, p_value_os: 0.07, phases: ['PHASE1', 'PHASE2'],
      overall_status: 'ACTIVE_NOT_RECRUITING', lead_sponsor_class: 'NIH',
      biomarker: 'BRAF (V600)', line_of_therapy: '1L; 2L; 3L; R/R', line_of_treatment: '2L',
    },
    {
      id: 2, arm_id: 'a2', source_type: 'abstract', abstract_id: 'ASCO_2023_9511', nct_id: 'NCT01989585',
      arm_name: 'Dabrafenib + Trametinib + Navitoclax', num_patients: 25, orr: 84, cr: 20,
      phases: ['PHASE1', 'PHASE2'], overall_status: 'ACTIVE_NOT_RECRUITING', lead_sponsor_class: 'NIH',
      biomarker: 'BRAF (V600)', line_of_therapy: '1L; 2L; 3L; R/R',
    },
    {
      id: 3, arm_id: 'b1', source_type: 'publication', publication_id: 'J Clin Oncol 2024', nct_id: 'NCT05086692',
      generic_name: 'MDNA11', arm_name: 'MDNA11', num_patients: 8, orr: 38, dcr: 75, median_pfs: null, is_nr: ['median_pfs'],
      phases: ['PHASE1'], overall_status: 'RECRUITING', lead_sponsor_class: 'INDUSTRY', biomarker: 'All comers',
    },
    {
      id: 4, arm_id: 'c1', source_type: 'abstract', abstract_id: 'ESMO_2025_1641P', nct_id: 'NCT03454035',
      arm_name: 'Ulixertinib + Palbociclib', num_patients: 9, phases: ['PHASE1'], overall_status: 'RECRUITING',
    },
  ],
};

const activeOutcomes = { ...phase1Outcomes, rows: phase1Outcomes.rows.slice(1) };

// RELATIVITY-047, KEYNOTE-716 and NADINA as production carries them on
// 2026-09-30, plus two abstracts with no nct_id.
const readouts = {
  ok: true,
  table: 'trial_outcomes',
  askedColumns: ['median_pfs', 'grade_3_plus_teae_pct', 'ae_leading_to_discontinuation_pct'],
  rows: [
    {
      nct_id: 'NCT03470922', arm_name: 'Relatlimab + Nivolumab', num_patients: 355, abstract_id: 'ASCO_2021_9503',
      median_pfs: 10.1, pfs_followup_months: 13.2, p_value_pfs: 0.0055, grade_3_plus_trae_pct: 18.9, orr: 43,
      line_of_therapy: '1L',
    },
    {
      nct_id: 'NCT03470922', arm_name: 'Relatlimab-Nivolumab', num_patients: 355,
      publication_id: 'N Engl J Med 2022;386:24-34.', median_pfs: 10.1, p_value_pfs: 0.006, grade_3_plus_ae_pct: 40.3,
      grade_3_plus_trae_pct: 18.9, trae_discontinuation_pct: 14.6, line_of_therapy: '1L', line_of_treatment: '1L (First Line)',
    },
    {
      nct_id: 'NCT03470922', arm_name: 'NIVO + RELA', num_patients: 355, abstract_id: 'ASCO_2026_9532',
      median_pfs: 10.2, grade_3_plus_trae_pct: 23, trae_discontinuation_pct: 17, line_of_therapy: '1L',
    },
    // Newer than NEJM 2022, but reports nothing asked: never the main row.
    {
      nct_id: 'NCT03470922', arm_name: 'Nivolumab + Relatlimab', num_patients: 355, abstract_id: 'ESMO_2025_1619P',
      line_of_therapy: '1L',
    },
    {
      nct_id: 'NCT03470922', arm_name: 'NIVO', num_patients: 359, abstract_id: 'ASCO_2026_9532',
      median_pfs: 4.6, grade_3_plus_trae_pct: 12, trae_discontinuation_pct: 10, line_of_therapy: '1L',
    },
    {
      nct_id: 'NCT03553836', arm_name: 'Placebo', num_patients: 489, abstract_id: 'ESMO_2025_1611P',
      grade_3_plus_trae_pct: 5.1, line_of_therapy: 'Adjuvant',
    },
    {
      nct_id: 'NCT03553836', arm_name: 'Pembrolizumab', num_patients: 487, abstract_id: 'ESMO_2025_1611P',
      grade_3_plus_trae_pct: 17.4, line_of_therapy: 'Adjuvant',
    },
    {
      nct_id: 'NCT04949113', arm_name: 'Neoadjuvant ipilimumab plus nivolumab', num_patients: 212,
      publication_id: 'N Engl J Med 2024;391:1696-708.', grade_3_plus_ae_pct: 47.2, grade_3_plus_trae_pct: 38.7,
      ae_leading_to_discontinuation_pct: 9, line_of_therapy: 'Adjuvant; Neoadjuvant', line_of_treatment: 'Neoadjuvant',
    },
    {
      nct_id: 'NCT04949113', arm_name: 'Adjuvant nivolumab', num_patients: 211,
      publication_id: 'N Engl J Med 2024;391:1696-708.', grade_3_plus_ae_pct: 34.1, grade_3_plus_trae_pct: 24,
      ae_leading_to_discontinuation_pct: 14.4, line_of_therapy: 'Adjuvant; Neoadjuvant', line_of_treatment: 'Adjuvant',
    },
    { abstract_id: 'ASCO_2024_9999', arm_name: 'Nivolumab', num_patients: 40, median_pfs: 5, line_of_treatment: '2L' },
    { abstract_id: 'ASCO_2025_9998', arm_name: 'Nivolumab', num_patients: 41, median_pfs: 6 },
  ],
};

describe('outcomes turns', () => {
  const today = new Date('2026-09-22');

  it('keeps drawing outcomes when the model also queries the landscape and the registry', () => {
    const outputs = [phase1Outcomes, landscapeCurated, landscapeTrials, activeOutcomes];

    for (let n = 1; n <= outputs.length; n++) {
      const table = toTurnTable(outputs.slice(0, n), today);
      expect(table?.columns.map((c) => c.key)).toContain('orr');
      expect(table?.summary).toBeUndefined();
    }
  });

  it('draws the last outcomes query, since a re-query is the model narrowing its answer', () => {
    const table = toTurnTable([phase1Outcomes, landscapeTrials, activeOutcomes], today);

    expect(table?.rows).toHaveLength(3);
  });

  it('draws outcomes even when each trial has one arm and the keys would join', () => {
    const oneArmEach = { ...phase1Outcomes, rows: [phase1Outcomes.rows[0], phase1Outcomes.rows[2]] };

    const table = toTurnTable([landscapeTrials, oneArmEach], today);

    expect(table?.rows).toHaveLength(2);
    expect(table?.summary).toBeUndefined();
  });

  it('shows the arm, its trial, its size and its source, and none of the loader bookkeeping', () => {
    const table = toTurnTable([phase1Outcomes], today);
    const keys = table!.columns.map((c) => c.key);

    expect(keys.slice(0, 7)).toEqual([
      'treatment_name', 'nct_id', 'setting', 'phases', 'num_patients', 'sponsor_type', 'biomarker',
    ]);
    expect(keys).toEqual(expect.arrayContaining(['source', 'overall_status', 'orr', 'cr', 'dcr', 'median_pfs']));
    for (const gone of ['id', 'arm_id', 'arm_name', 'generic_name', 'abstract_id', 'publication_id', 'source_type', 'p_value_os', 'os_followup_months']) {
      expect(keys).not.toContain(gone);
    }
    expect(cell(table, 0, 'source')).toBe('ASCO_2023_9511');
    expect(cell(table, 2, 'source')).toBe('J Clin Oncol 2024');
    expect(cell(table, 2, 'median_pfs')).toBe('NR');
  });

  it('offers every reported endpoint as a parameter, most-reported first, with its family', () => {
    const table = toTurnTable([phase1Outcomes], today);

    expect(table?.parameters).toEqual([
      { key: 'orr', label: 'ORR', family: 'efficacy', arms: 3 },
      { key: 'cr', label: 'CR', family: 'efficacy', arms: 2 },
      { key: 'dcr', label: 'DCR', family: 'efficacy', arms: 1 },
      { key: 'median_pfs', label: 'Median PFS (mo)', family: 'efficacy', arms: 1 },
    ]);
  });

  it('tags safety endpoints as safety', () => {
    const safety = {
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT1', arm_name: 'A', grade_3_plus_trae_pct: 12 },
        { nct_id: 'NCT1', arm_name: 'B', grade_3_plus_trae_pct: 20, serious_ae_pct: 4 },
      ],
    };

    expect(toTurnTable([safety], today)?.parameters?.map((p) => [p.key, p.family])).toEqual([
      ['grade_3_plus_trae_pct', 'safety'],
      ['serious_ae_pct', 'safety'],
    ]);
  });

  it("states each arm's sponsor type and biomarker, and sections it by its trial's line", () => {
    const table = toTurnTable([phase1Outcomes], today);

    expect(cell(table, 0, 'sponsor_type')).toBe('Non-industry');
    // The trial's line beats the arm's own '2L', so the trial's arms share a section.
    expect(cell(table, 0, 'setting')).toBe('1L; 2L; 3L; R/R');
    expect(cell(table, 2, 'sponsor_type')).toBe('Industry');
    expect(cell(table, 2, 'biomarker')).toBe('All comers');
    expect(cell(table, 3, 'biomarker')).toBe('—');
  });

  it('puts an arm with no line under "Line not reported", last', () => {
    const table = toTurnTable([phase1Outcomes], today);

    expect(cell(table, 3, 'setting')).toBe('Line not reported');
  });

  it('keeps the trial facts even when every arm shares them', () => {
    // A column identical on every row is usually noise; these are what every
    // answer states, so an all-industry result still says Industry.
    const oneTrial = { ...phase1Outcomes, rows: phase1Outcomes.rows.slice(0, 2) };

    const keys = toTurnTable([oneTrial], today)!.columns.map((c) => c.key);

    expect(keys).toEqual(expect.arrayContaining(['sponsor_type', 'biomarker', 'setting']));
  });

  it("cites a web-scraped readout by its page, since it has no abstract or publication ID", () => {
    const scraped = {
      ok: true,
      table: 'trial_outcomes',
      rows: [
        {
          nct_id: 'NCT05086692', arm_name: 'MDNA11', orr: 38, source_type: 'webscrape', source_name: 'web_scrape',
          source_url: 'https://ir.medicenna.com/news-releases/mdna11',
        },
      ],
    };

    expect(cell(toTurnTable([scraped], today), 0, 'source')).toBe('https://ir.medicenna.com/news-releases/mdna11');
  });

  it("never offers the other family's censored endpoint on a safety table", () => {
    // `is_nr` names median_pfs, but a safety query never projected it.
    const safety = {
      ok: true,
      table: 'trial_outcomes',
      rows: [{ nct_id: 'NCT1', arm_name: 'A', trae_pct: 40, is_nr: ['median_pfs'] }],
    };

    expect(toTurnTable([safety], today)?.parameters?.map((p) => p.key)).toEqual(['trae_pct']);
  });

  // The Q3 baseline: median PFS vs grade 3+ TEAE vs discontinuation due to
  // AEs. No source labels a rate TEAE, so the asked table is empty on safety
  // and the answer lives under AE and TRAE.
  const q3 = {
    ok: true,
    table: 'trial_outcomes',
    askedColumns: ['median_pfs', 'grade_3_plus_teae_pct', 'ae_leading_to_discontinuation_pct'],
    rows: [
      {
        nct_id: 'NCT05732805', arm_name: 'Nurulimab + prolgolimab', num_patients: 135, abstract_id: 'ASCO_2026_9544',
        median_pfs: 15.4, grade_3_plus_trae_pct: 17.8, ae_leading_to_discontinuation_pct: 11.1, orr: 40, dcr: 60,
      },
      {
        nct_id: 'NCT03470922', arm_name: 'Nivolumab + relatlimab', num_patients: 355, publication_id: 'NEJM 2022',
        median_pfs: 10.1, grade_3_plus_ae_pct: 40.3, grade_3_plus_trae_pct: 18.9, trae_discontinuation_pct: 14.6,
        orr: 43, dcr: 60,
      },
      {
        nct_id: 'NCT02224781', arm_name: 'Nivolumab + ipilimumab first', num_patients: 135,
        abstract_id: 'ASCO_2025_9506', median_pfs: 26.7, orr: 46,
      },
    ],
  };

  it('shows the class most treatments report in place of an empty asked one, first, and keeps the asked column', () => {
    const table = toTurnTable([q3], today);

    expect(table?.asked).toEqual(['median_pfs', 'grade_3_plus_trae_pct', 'ae_leading_to_discontinuation_pct']);
    // Picked field by field: Task 4 adds `companions` to median PFS.
    const ranked = table?.parameters?.slice(0, 4).map(({ key, label, family, arms }) => ({ key, label, family, arms }));
    expect(ranked).toEqual([
      { key: 'median_pfs', label: 'Median PFS (mo)', family: 'efficacy', arms: 3 },
      { key: 'grade_3_plus_trae_pct', label: 'G3+ TRAE %', family: 'safety', arms: 2 },
      { key: 'ae_leading_to_discontinuation_pct', label: 'AE Disc %', family: 'safety', arms: 1 },
      { key: 'grade_3_plus_teae_pct', label: 'G3+ TEAE %', family: 'safety', arms: 0 },
    ]);
    expect(cell(table, 1, 'grade_3_plus_teae_pct')).toBe('—');
  });

  it('says above the table which class stands in, and which treatments report only another', () => {
    expect(toTurnTable([q3], today)?.caveat).toBe(
      'No treatment reports Grade 3+ TEAE; showing Grade 3+ TRAE (2 treatments), the class most treatments report. ' +
        'AE leading to discontinuation: 1 treatment; 1 more reports it only as TRAE discontinuation.',
    );
  });

  it('counts a treatment reporting more than one other class once, not once per class', () => {
    // Repro: a treatment reports TEAE disc and TRAE disc but not AE disc
    // (shown). The old code counted it under both classes for one treatment.
    const doubleCount = {
      ok: true,
      table: 'trial_outcomes',
      askedColumns: ['ae_leading_to_discontinuation_pct'],
      rows: [
        { nct_id: 'NCT1', arm_name: 'A', ae_leading_to_discontinuation_pct: 12 },
        { nct_id: 'NCT2', arm_name: 'B', teae_discontinuation_pct: 8, trae_discontinuation_pct: 9 },
      ],
    };

    expect(toTurnTable([doubleCount], today)?.caveat).toBe(
      'AE leading to discontinuation: 1 treatment; 1 more reports it only as TEAE discontinuation or TRAE discontinuation.',
    );
  });

  it('keeps the asked class on a tie, and otherwise breaks a tie by the class precedence', () => {
    const tied = {
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT1', arm_name: 'A', grade_3_plus_ae_pct: 30, trae_discontinuation_pct: 5 },
        { nct_id: 'NCT2', arm_name: 'B', grade_3_plus_trae_pct: 20, ae_leading_to_discontinuation_pct: 8 },
      ],
    };

    // TEAE is empty: grade 3+ goes to AE (TEAE > AE > TRAE), discontinuation to AE (AE > TEAE > TRAE).
    expect(toTurnTable([{ ...tied, askedColumns: ['grade_3_plus_teae_pct', 'teae_discontinuation_pct'] }], today)?.asked)
      .toEqual(['grade_3_plus_ae_pct', 'ae_leading_to_discontinuation_pct']);
    // TRAE ties AE and was asked, so it stays.
    expect(toTurnTable([{ ...tied, askedColumns: ['grade_3_plus_trae_pct', 'trae_discontinuation_pct'] }], today)?.asked)
      .toEqual(['grade_3_plus_trae_pct', 'trae_discontinuation_pct']);
  });

  it('draws no caveat when the asked class is shown and no treatment reports only another', () => {
    const reported = { ...q3, askedColumns: ['median_pfs', 'grade_3_plus_trae_pct'] };

    expect(toTurnTable([reported], today)?.caveat).toBeUndefined();
  });

  it('keeps both asked classes when one is the other one\'s own sibling, rather than standing in for both', () => {
    // Repro: TEAE reported on 1 treatment, TRAE on 3 - without the fix,
    // standIn picks TRAE for both asked keys and the TEAE column disappears.
    const bothClasses = {
      ok: true,
      table: 'trial_outcomes',
      askedColumns: ['grade_3_plus_teae_pct', 'grade_3_plus_trae_pct'],
      rows: [
        { nct_id: 'NCT1', arm_name: 'A', grade_3_plus_teae_pct: 40 },
        { nct_id: 'NCT2', arm_name: 'B', grade_3_plus_trae_pct: 20 },
        { nct_id: 'NCT3', arm_name: 'C', grade_3_plus_trae_pct: 25 },
        { nct_id: 'NCT4', arm_name: 'D', grade_3_plus_trae_pct: 30 },
      ],
    };

    const table = toTurnTable([bothClasses], today);

    expect(table?.asked).toEqual(['grade_3_plus_teae_pct', 'grade_3_plus_trae_pct']);
    expect(table?.caveat).not.toMatch(/the class most treatments report/);
  });

  it('draws no caveat, and no unreported class column, when the question named no endpoints', () => {
    const table = toTurnTable([{ ...q3, askedColumns: undefined }], today);

    expect(table?.asked).toBeUndefined();
    expect(table?.caveat).toBeUndefined();
    expect(table?.columns.map((c) => c.key)).not.toContain('grade_3_plus_teae_pct');
  });

  it('adds no companion column for an asked median when the rows never carried the key', () => {
    // An old persisted session's query never selected pfs_followup_months or
    // p_value_pfs, so no empty "PFS follow-up (mo)" column should appear.
    const noCompanions = {
      ok: true,
      table: 'trial_outcomes',
      askedColumns: ['median_pfs'],
      rows: [{ nct_id: 'NCT1', arm_name: 'A', median_pfs: 10 }],
    };

    const keys = toTurnTable([noCompanions], today)?.columns.map((c) => c.key);

    expect(keys).not.toContain('pfs_followup_months');
    expect(keys).not.toContain('p_value_pfs');
  });

  it('keeps the companion columns for an asked median when the rows carry the keys as null', () => {
    const nullCompanions = {
      ok: true,
      table: 'trial_outcomes',
      askedColumns: ['median_pfs'],
      rows: [{ nct_id: 'NCT1', arm_name: 'A', median_pfs: 10, pfs_followup_months: null, p_value_pfs: null }],
    };

    const keys = toTurnTable([nullCompanions], today)?.columns.map((c) => c.key);

    expect(keys).toEqual(expect.arrayContaining(['pfs_followup_months', 'p_value_pfs']));
  });

  it('shows the expert verdict beside the source, only once some arm was reviewed', () => {
    const reviewed = {
      ...phase1Outcomes,
      rows: phase1Outcomes.rows.map((row, i) => (i < 2 ? { ...row, expert_review: 'good' } : row)),
    };

    const table = toTurnTable([reviewed], today);
    const keys = table!.columns.map((c) => c.key);

    expect(keys.slice(-3)).toEqual(['expert_review', 'source', 'overall_status']);
    expect(table!.columns.find((c) => c.key === 'expert_review')?.label).toBe('Expert review');
    expect([0, 1, 2].map((i) => cell(table, i, 'expert_review'))).toEqual(['Good', 'Good', '—']);
    expect(toTurnTable([phase1Outcomes], today)!.columns.map((c) => c.key)).not.toContain('expert_review');
  });

  it('leaves a landscape table without parameters', () => {
    expect(toTurnTable([landscapeTrials, landscapeCurated], today)?.parameters).toBeUndefined();
  });
});

describe('one row per treatment', () => {
  const today = new Date('2026-09-30');
  const column = (table: ReturnType<typeof toTurnTable>, key: string) =>
    table!.columns.findIndex((c) => c.key === key);

  it('draws each treatment once, from its newest readout, under its longest name', () => {
    const table = toTurnTable([readouts], today);

    expect(table?.rows).toHaveLength(8);
    expect(cell(table, 0, 'treatment_name')).toBe('Relatlimab + Nivolumab');
    expect(cell(table, 0, 'source')).toBe('ASCO_2026_9532');
    expect(cell(table, 0, 'num_patients')).toBe('355');
    expect(cell(table, 0, 'median_pfs')).toBe('10.2');
  });

  it('folds the earlier readouts beneath it, newest first, and drops the ones that report nothing asked', () => {
    const table = toTurnTable([readouts], today);
    const source = column(table, 'source');

    // ESMO_2025_1619P reports nothing asked, so it is not a readout of this answer.
    expect(table?.readouts?.[0].map((row) => row[source])).toEqual([
      'N Engl J Med 2022;386:24-34.',
      'ASCO_2021_9503',
    ]);
    expect(table?.readouts?.[1]).toEqual([]);
  });

  it('keeps a placebo arm apart from the drug it is compared with', () => {
    const table = toTurnTable([readouts], today);
    const names = table!.rows.map((_, i) => cell(table, i, 'treatment_name'));

    expect(names).toEqual(expect.arrayContaining(['Placebo', 'Pembrolizumab']));
  });

  it('never folds two arms of one readout into one treatment, even sharing a name', () => {
    // E1609: ipi 3 mg/kg vs ipi 10 mg/kg, both just "Ipilimumab" - the dose
    // lives in `dosage`, not `arm_name`. Folding these would silently keep
    // one arm and hide the other under "1 earlier readout".
    const e1609 = {
      ok: true,
      table: 'trial_outcomes',
      askedColumns: ['grade_3_plus_trae_pct'],
      rows: [
        {
          nct_id: 'NCT01274338', arm_name: 'Ipilimumab', num_patients: 523, abstract_id: 'ASCO_2021_9582',
          grade_3_plus_trae_pct: 24.9,
        },
        {
          nct_id: 'NCT01274338', arm_name: 'Ipilimumab', num_patients: 511, abstract_id: 'ASCO_2021_9582',
          grade_3_plus_trae_pct: 17.5,
        },
      ],
    };

    const table = toTurnTable([e1609], today);

    expect(table?.rows).toHaveLength(2);
    expect(table?.readouts).toBeUndefined();
  });

  it('never folds two arms of one publication into one treatment, even sharing a drug key', () => {
    // S1801-style: neoadjuvant and adjuvant pembrolizumab are two randomised
    // arms of one trial, reported in one publication; both key to `pembrolizumab`.
    const s1801 = {
      ok: true,
      table: 'trial_outcomes',
      askedColumns: ['median_pfs'],
      rows: [
        {
          nct_id: 'NCT03698019', arm_name: 'Neoadjuvant pembrolizumab', num_patients: 154,
          publication_id: 'N Engl J Med 2023;388:813-23.', median_pfs: 72,
        },
        {
          nct_id: 'NCT03698019', arm_name: 'Adjuvant pembrolizumab', num_patients: 159,
          publication_id: 'N Engl J Med 2023;388:813-23.', median_pfs: 49.4,
        },
      ],
    };

    const table = toTurnTable([s1801], today);

    expect(table?.rows).toHaveLength(2);
  });

  it('never merges rows that carry no nct_id, or no arm name', () => {
    const nameless = {
      ok: true,
      table: 'trial_outcomes',
      rows: [
        { nct_id: 'NCT1', abstract_id: 'ASCO_2024_1', orr: 30 },
        { nct_id: 'NCT1', abstract_id: 'ASCO_2025_2', orr: 40 },
      ],
    };

    expect(toTurnTable([nameless], today)?.rows).toHaveLength(2);
    const table = toTurnTable([readouts], today);
    expect(table!.rows.filter((_, i) => cell(table, i, 'nct_id') === '—')).toHaveLength(2);
  });

  it('keeps a treatment whose readouts report nothing asked, as one empty row the table counts', () => {
    const tps = {
      ok: true,
      table: 'trial_outcomes',
      askedColumns: ['median_pfs'],
      rows: [
        { nct_id: 'NCT05155254', arm_name: 'IO102-IO103 + Pembrolizumab', abstract_id: 'ASCO_2022_TPS9589' },
        { nct_id: 'NCT05155254', arm_name: 'IO102-IO103 + Pembrolizumab', abstract_id: 'ASCO_2022_9589' },
      ],
    };

    const table = toTurnTable([tps], today);

    expect(table?.rows).toHaveLength(1);
    expect(cell(table, 0, 'median_pfs')).toBe('—');
    expect(table?.readouts).toBeUndefined();
  });

  it('counts treatments, not readouts, and still offers an endpoint only an earlier readout reports', () => {
    const parameters = toTurnTable([readouts], today)!.parameters!;

    // NADINA's two arms; RELATIVITY-047's 40.3 is in NEJM 2022, an earlier readout.
    expect(parameters.find((p) => p.key === 'grade_3_plus_ae_pct')?.arms).toBe(2);
    expect(parameters.find((p) => p.key === 'orr')).toMatchObject({ arms: 0 });
  });

  it('puts the PFS follow-up and p-value right after median PFS, and hides them with it', () => {
    const table = toTurnTable([readouts], today);
    const keys = table!.columns.map((c) => c.key);
    const at = keys.indexOf('median_pfs');

    expect(keys.slice(at, at + 3)).toEqual(['median_pfs', 'pfs_followup_months', 'p_value_pfs']);
    expect(table!.columns.slice(at + 1, at + 3).map((c) => c.label)).toEqual(['PFS follow-up (mo)', 'PFS p-value']);
    expect(table!.parameters!.find((p) => p.key === 'median_pfs')?.companions).toEqual(['pfs_followup_months', 'p_value_pfs']);
    expect(keys).not.toContain('os_followup_months');
  });

  it("sections treatments by their trial's line, so a trial's randomised arms stay together", () => {
    const table = toTurnTable([readouts], today);

    expect(table!.rows.map((_, i) => cell(table, i, 'setting'))).toEqual([
      '1L', '1L', '2L',
      'Adjuvant; Neoadjuvant', 'Adjuvant; Neoadjuvant',
      'Adjuvant', 'Adjuvant',
      'Line not reported',
    ]);
    expect(table!.columns.map((c) => c.key)).not.toContain('line');
  });

  it("falls back to the arm's line without its gloss when the trial has none", () => {
    const armOnly = {
      ok: true,
      table: 'trial_outcomes',
      rows: [{ nct_id: 'NCT1', arm_name: 'A', orr: 40, line_of_treatment: '1L (First Line)' }],
    };

    expect(cell(toTurnTable([armOnly], today), 0, 'setting')).toBe('1L');
  });
});

// A landscape turn: the registry rows carry what `derive` needs to place a
// trial in a setting, name its sponsor class and spot a pan-tumour platform.
const landscapeTrials = {
  ok: true,
  table: 'clinical_trials',
  coverage: { returned: 4, matched: 4, complete: true },
  rows: [
    {
      nct_id: 'NCT03470922',
      overall_status: 'RECRUITING',
      primary_purpose: 'TREATMENT',
      lead_sponsor_class: 'INDUSTRY',
      is_basket: false,
      interventions: [{ name: 'Relatlimab', type: 'DRUG' }],
    },
    {
      nct_id: 'NCT01274338',
      overall_status: 'RECRUITING',
      primary_purpose: 'TREATMENT',
      lead_sponsor_class: 'NETWORK',
      is_basket: false,
      interventions: [{ name: 'Pembrolizumab', type: 'DRUG' }],
    },
    {
      nct_id: 'NCT05078047',
      overall_status: 'RECRUITING',
      primary_purpose: 'TREATMENT',
      lead_sponsor_class: 'OTHER',
      is_basket: true,
      interventions: [{ name: 'Platform arm', type: 'DRUG' }],
    },
    {
      nct_id: 'NCT07530887',
      overall_status: 'RECRUITING',
      primary_purpose: 'OTHER',
      lead_sponsor_class: 'INDUSTRY',
      is_basket: false,
      interventions: [{ name: 'No re-excision', type: 'PROCEDURE' }],
    },
  ],
};

const landscapeCurated = {
  ok: true,
  table: 'trial_landscape',
  coverage: { returned: 2, matched: 2, complete: true, requested: 4, missing: ['NCT05078047', 'NCT07530887'] },
  rows: [
    { nct_id: 'NCT03470922', treatment_name: 'Relatlimab + Nivolumab', modality: 'Monoclonal Antibody', line_of_therapy: '1L' },
    { nct_id: 'NCT01274338', treatment_name: 'Pembrolizumab', modality: 'Monoclonal Antibody', line_of_therapy: 'Adjuvant' },
  ],
};

describe('toTurnTable summary', () => {
  it('counts the trials, the curated ones, the set-aside baskets and the sponsor split', () => {
    const table = toTurnTable([landscapeTrials, landscapeCurated]);

    expect(table?.summary).toEqual({
      trials: 4,
      curated: 2,
      setAside: 1,
      industry: 2,
      nonIndustry: 2,
    });
  });

  it('counts set-aside trials the column rule would have deleted', () => {
    // Every row a basket makes `is_basket` uniform, and a uniform column is
    // dropped as distinguishing nothing. The count is taken before that, or a
    // result that is entirely off-indication would report none set aside.
    const allBaskets = {
      ...landscapeTrials,
      rows: landscapeTrials.rows.map((row) => ({ ...row, is_basket: true })),
    };
    const table = toTurnTable([allBaskets, landscapeCurated]);

    expect(table?.columns.map((c) => c.key)).not.toContain('is_basket');
    expect(table?.summary?.setAside).toBe(4);
  });

  it('summarises a single-query turn too, not only the joined path', () => {
    const table = toTurnTable([landscapeTrials]);

    expect(table?.summary).toMatchObject({ trials: 4, curated: 0, setAside: 1, industry: 2 });
  });

  it('leaves a turn that is not a landscape without a summary', () => {
    // No line_of_therapy and no primary_purpose, so `derive` never places a
    // setting and there are no sections for a strip to sit above.
    const table = toTurnTable([trials, landscape]);

    expect(table?.summary).toBeUndefined();
  });

  it('gives approval rows no landscape strip: they are regimens, not trials', () => {
    const approvals = {
      ok: true,
      table: 'approved_therapies',
      rows: [
        { treatment_name: 'Nivolumab', setting: 'Adjuvant', us_status: 'Off label', sheet_row: 9 },
        { treatment_name: 'Ipilimumab + Nivolumab', setting: '1L+ Advanced', us_status: 'On-label (generic)', sheet_row: 17 },
      ],
    };

    const table = toTurnTable([approvals]);

    expect(table?.summary).toBeUndefined();
    expect(table?.columns.map((c) => c.key)).toEqual(['treatment_name', 'setting', 'us_status']);
  });
});

describe('withoutAskedPhase', () => {
  const table = {
    columns: [
      { key: 'nct_id', label: 'NCT' },
      { key: 'phases', label: 'Phases' },
    ],
    rows: [
      ['NCT1', 'Phase 3'],
      ['NCT2', 'Phase 2/Phase 3'],
    ],
  };

  it('drops the phase column when a query filtered on phase', () => {
    const result = withoutAskedPhase(table, [{ table: 'clinical_trials', phase: 'PHASE3' }]);
    expect(result.columns.map((c) => c.key)).toEqual(['nct_id']);
    expect(result.rows).toEqual([['NCT1'], ['NCT2']]);
  });

  it('keeps it when no query did', () => {
    expect(withoutAskedPhase(table, [{ table: 'clinical_trials' }, undefined])).toBe(table);
  });

  it('drops the phase column from the folded readouts too, so no sub-row shifts left', () => {
    const table = {
      columns: [{ key: 'treatment_name', label: 'Treatment' }, { key: 'phases', label: 'Phases' }, { key: 'orr', label: 'ORR' }],
      rows: [['A', 'Phase 3', '40']],
      readouts: [[['A', 'Phase 3', '38']]],
    };

    const next = withoutAskedPhase(table, [{ phase: 'PHASE3' }]);

    expect(next.rows).toEqual([['A', '40']]);
    expect(next.readouts).toEqual([[['A', '38']]]);
  });
});
