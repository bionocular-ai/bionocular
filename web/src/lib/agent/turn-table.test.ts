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
    expect(table?.columns.map((c) => c.key)).toEqual(['treatment_name', 'nct_id', 'setting', 'sponsor_type', 'line', 'biomarker', 'orr']);
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

  it('ignores a result with no trial key, which cannot be joined', () => {
    const news = { ok: true, table: 'news_feed', rows: [{ url: 'https://example.test', title: 'x' }] };

    expect(toTurnTable([trials, news])).toBeNull();
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

  it('gives an outcomes table its setting and the three trial facts every answer states', () => {
    const outcomes = {
      ok: true,
      table: 'trial_outcomes',
      rows: [{ nct_id: 'NCT1', arm_name: 'A', orr: 43 }],
    };

    const table = toTurnTable([outcomes], today);

    expect(table?.columns.map((c) => c.key)).toEqual(['treatment_name', 'nct_id', 'setting', 'sponsor_type', 'line', 'biomarker', 'orr']);
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

    expect(keys.slice(0, 8)).toEqual([
      'treatment_name', 'nct_id', 'setting', 'phases', 'num_patients', 'sponsor_type', 'line', 'biomarker',
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
      { key: 'median_pfs', label: 'Median PFS', family: 'efficacy', arms: 1 },
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

  it("states each arm's sponsor type, line and biomarker, the arm's own line first", () => {
    const table = toTurnTable([phase1Outcomes], today);

    expect(cell(table, 0, 'sponsor_type')).toBe('Non-industry');
    expect(cell(table, 0, 'line')).toBe('2L');
    expect(cell(table, 1, 'line')).toBe('1L; 2L; 3L; R/R');
    expect(cell(table, 2, 'sponsor_type')).toBe('Industry');
    expect(cell(table, 2, 'biomarker')).toBe('All comers');
    expect(cell(table, 3, 'biomarker')).toBe('—');
  });

  it('places each arm in a setting from its line, so the table groups the way a landscape does', () => {
    const table = toTurnTable([phase1Outcomes], today);

    expect(cell(table, 0, 'setting')).toBe('Advanced / metastatic');
    expect(cell(table, 3, 'setting')).toBe('Unclassified');
  });

  it('puts an adjuvant or neoadjuvant arm in peri-operative, whatever else its trial treats', () => {
    const periOp = {
      ok: true,
      table: 'trial_outcomes',
      rows: [{ nct_id: 'NCT1', arm_name: 'A', orr: 40, line_of_treatment: 'Neoadjuvant; R/R' }],
    };

    expect(cell(toTurnTable([periOp], today), 0, 'setting')).toBe('Peri-operative');
  });

  it('keeps the three trial facts even when every arm shares them', () => {
    // A column identical on every row is usually noise; these three are what
    // every answer states, so an all-industry result still says Industry.
    const oneTrial = { ...phase1Outcomes, rows: phase1Outcomes.rows.slice(0, 2) };

    const keys = toTurnTable([oneTrial], today)!.columns.map((c) => c.key);

    expect(keys).toEqual(expect.arrayContaining(['sponsor_type', 'line', 'biomarker']));
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

  it('leaves a landscape table without parameters', () => {
    expect(toTurnTable([landscapeTrials, landscapeCurated], today)?.parameters).toBeUndefined();
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
});
