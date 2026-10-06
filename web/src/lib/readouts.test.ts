import { describe, expect, it } from 'vitest';
import {
  EMPTY_FILTERS,
  facetCounts,
  filterReadouts,
  groupReadouts,
  phaseLabel,
  sortReadouts,
  type OutcomeRow,
  type ReadoutFilters,
} from './readouts';

function row(over: Partial<OutcomeRow> = {}): OutcomeRow {
  return {
    id: 1,
    nct_id: 'NCT00000001',
    abstract_id: 'ASCO_2024_9500',
    publication_id: null,
    source_name: 'extraction_results_ASCO_2024',
    source_type: 'abstract',
    arm_name: 'Arm A',
    target_protein: 'PD-1',
    num_patients: 10,
    is_nr: null,
    is_lt: null,
    orr: null, cr: null, pcr: null, median_pfs: null, median_os: null,
    hr_pfs: null, ci_hr_pfs: null, hr_os: null, ci_hr_os: null,
    hr_efs: null, ci_hr_efs: null, hr_rfs: null, ci_hr_rfs: null,
    rfs: null, efs: null, grade_3_plus_trae_pct: null,
    clinical_trials: {
      acronym: 'TRIAL',
      brief_title: 'A trial',
      phases: ['PHASE3'],
      lead_sponsor_name: 'Sponsor Inc.',
      lead_sponsor_class: 'INDUSTRY',
      primary_completion_date: '2024-01-12',
      trial_landscape: { treatment_name: 'Drug A', modality: 'Monoclonal Antibody', line_of_therapy: '1L' },
    },
    ...over,
  };
}

const filters = (over: Partial<ReadoutFilters> = {}): ReadoutFilters => ({ ...EMPTY_FILTERS, ...over });

describe('groupReadouts', () => {
  it('makes one readout per trial and source, with one arm per row', () => {
    const readouts = groupReadouts([
      row({ id: 1, arm_name: 'A', num_patients: 16 }),
      row({ id: 2, arm_name: 'B', num_patients: 37 }),
      row({ id: 3, abstract_id: 'ESMO_2021_1093', arm_name: 'A' }),
    ]);
    expect(readouts).toHaveLength(2);
    expect(readouts[0].arms.map((a) => a.name)).toEqual(['A', 'B']);
    expect(readouts[0].analyzedN).toBe(53);
  });

  it('keys a publication readout on its citation', () => {
    const readouts = groupReadouts([
      row({ id: 1, abstract_id: null, publication_id: 'N Engl J Med 2015;373:23-34.', source_type: 'publication' }),
      row({ id: 2, abstract_id: null, publication_id: 'N Engl J Med 2019;381:1535-46.', source_type: 'publication' }),
    ]);
    expect(readouts).toHaveLength(2);
  });

  it('leaves arms with no N out of the analyzed total', () => {
    const [r] = groupReadouts([row({ id: 1, num_patients: 20 }), row({ id: 2, num_patients: null })]);
    expect(r.analyzedN).toBe(20);
  });
});

describe('hasResults', () => {
  it('is false for a readout that only reports N', () => {
    expect(groupReadouts([row()])[0].hasResults).toBe(false);
  });

  it('counts a median that was not reached as a result', () => {
    expect(groupReadouts([row({ is_nr: ['median_os'] })])[0].hasResults).toBe(true);
  });

  it('counts an ORR as a result', () => {
    expect(groupReadouts([row({ orr: 33.6 })])[0].hasResults).toBe(true);
  });
});

describe('source label', () => {
  it('reads conference, year and number from an abstract id', () => {
    const [r] = groupReadouts([row({ abstract_id: 'SITC_2025_600' })]);
    expect(r.source).toEqual({ label: 'SITC 2025', detail: 'Abstract 600', group: 'SITC', year: 2025 });
  });

  it('shows a publication citation as it is stored', () => {
    const [r] = groupReadouts([
      row({ abstract_id: null, publication_id: 'N Engl J Med 2022;386:24-34.', source_type: 'publication' }),
    ]);
    expect(r.source).toEqual({ label: 'N Engl J Med 2022;386:24-34.', detail: null, group: 'Journal publication', year: 2022 });
  });
});

describe('phaseLabel', () => {
  it.each([
    [['PHASE3'], 'Phase 3'],
    [['PHASE1', 'PHASE2'], 'Phase 1/2'],
    [['PHASE2', 'PHASE3'], 'Phase 2/3'],
    [['EARLY_PHASE1'], 'Early Phase 1'],
    [null, null],
  ])('%j -> %s', (phases, label) => {
    expect(phaseLabel(phases)).toBe(label);
  });
});

describe('endpoint columns', () => {
  it('walks the fixed order, keeps what an arm reports, and stops at 4', () => {
    const [r] = groupReadouts([
      row({ id: 1, grade_3_plus_trae_pct: 38.7, cr: 6.3, pcr: 47.2, orr: 35.8, median_os: 30, hr_efs: 0.32, ci_hr_efs: '0.15-0.66' }),
    ]);
    expect(r.endpoints.map((e) => e.key)).toEqual(['hr', 'median_os', 'orr', 'pcr']);
  });

  it('reads the HR and its CI from whichever HR the readout reports', () => {
    const [r] = groupReadouts([row({ hr_efs: 0.32, ci_hr_efs: '0.15-0.66' })]);
    expect(r.endpoints[0].label).toBe('EFS HR');
    expect(r.arms[0].values.hr).toEqual({ value: 0.32, lo: 0.15, hi: 0.66, nr: false, lt: false });
  });

  it('flags a median that was not reached', () => {
    const [r] = groupReadouts([row({ is_nr: ['median_os'] })]);
    expect(r.arms[0].values.median_os).toEqual({ value: null, nr: true, lt: false });
  });
});

describe('sortReadouts', () => {
  it('puts the newest primary completion first and missing dates last', () => {
    const rs = groupReadouts([
      row({ id: 1, nct_id: 'NCT1', clinical_trials: { ...row().clinical_trials, primary_completion_date: '2020-01-01' } }),
      row({ id: 2, nct_id: 'NCT2', clinical_trials: { ...row().clinical_trials, primary_completion_date: null } }),
      row({ id: 3, nct_id: 'NCT3', clinical_trials: { ...row().clinical_trials, primary_completion_date: '2024-01-01' } }),
    ]);
    expect(sortReadouts(rs).map((r) => r.nctId)).toEqual(['NCT3', 'NCT1', 'NCT2']);
  });

  it('breaks a tie between readouts of one trial by the readout year', () => {
    const rs = groupReadouts([
      row({ id: 1, abstract_id: null, publication_id: 'N Engl J Med 2015;373:23-34.', source_type: 'publication' }),
      row({ id: 2, abstract_id: null, publication_id: 'N Engl J Med 2019;381:1535-46.', source_type: 'publication' }),
    ]);
    expect(sortReadouts(rs).map((r) => r.source.year)).toEqual([2019, 2015]);
  });
});

describe('filter values', () => {
  it('maps the sponsor class to Industry or Non-industry', () => {
    const rs = groupReadouts([
      row({ id: 1, nct_id: 'NCT1' }),
      row({ id: 2, nct_id: 'NCT2', clinical_trials: { ...row().clinical_trials, lead_sponsor_class: 'NIH' } }),
    ]);
    expect(rs.map((r) => r.facets.sponsor)).toEqual([['Industry'], ['Non-industry']]);
  });

  it('splits targets on ";" only and drops N/A', () => {
    const [r] = groupReadouts([row({ target_protein: 'HSV-1/GM-CSF/GALV-GP-R-; PD-1' }), row({ id: 2, target_protein: 'N/A' })]);
    expect(r.facets.target).toEqual(['HSV-1/GM-CSF/GALV-GP-R-', 'PD-1']);
  });

  it('keeps only modalities the landscape knows', () => {
    const [r] = groupReadouts([
      row({ clinical_trials: { ...row().clinical_trials, trial_landscape: { treatment_name: 'x', modality: 'Monoclonal Antibody; Made Up', line_of_therapy: 'Adjuvant; Neoadjuvant' } } }),
    ]);
    expect(r.facets.modality).toEqual(['Monoclonal Antibody']);
    expect(r.facets.setting).toEqual(['Adjuvant', 'Neoadjuvant']);
  });
});

describe('filterReadouts and facetCounts', () => {
  const rs = groupReadouts([
    row({ id: 1, nct_id: 'NCT1', orr: 40 }),
    row({ id: 2, nct_id: 'NCT2', orr: 20, clinical_trials: { ...row().clinical_trials, acronym: 'NADINA', phases: ['PHASE2'] } }),
    row({ id: 3, nct_id: 'NCT3', clinical_trials: { ...row().clinical_trials, phases: ['PHASE2'], lead_sponsor_class: 'OTHER' } }),
  ]);

  it('hides readouts without results when the toggle is on', () => {
    expect(filterReadouts(rs, filters({ onlyResults: true })).map((r) => r.nctId)).toEqual(['NCT1', 'NCT2']);
  });

  it('ORs options inside a group and ANDs across groups', () => {
    const f = filters({ selected: { phase: ['Phase 2', 'Phase 3'], sponsor: ['Industry'] } });
    expect(filterReadouts(rs, f).map((r) => r.nctId)).toEqual(['NCT1', 'NCT2']);
  });

  it('counts a group with every other group applied but not its own', () => {
    const f = filters({ selected: { phase: ['Phase 3'], sponsor: ['Industry'] } });
    expect(facetCounts(rs, f, 'phase')).toEqual(new Map([['Phase 3', 1], ['Phase 2', 1]]));
    expect(facetCounts(rs, f, 'sponsor')).toEqual(new Map([['Industry', 1]]));
  });

  it('searches acronym, drug, arm and NCT number', () => {
    expect(filterReadouts(rs, filters({ search: 'nadina' })).map((r) => r.nctId)).toEqual(['NCT2']);
    expect(filterReadouts(rs, filters({ search: 'nct3' })).map((r) => r.nctId)).toEqual(['NCT3']);
  });
});
