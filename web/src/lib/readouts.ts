import { PHASE_MAP } from './clinical-trials-enums';
import { MODALITY_VALUES } from './dashboard-constants';

/**
 * Readouts for the Outcome Intelligence Hub. A readout is one abstract or publication
 * reporting a trial's results; each `trial_outcomes` row is one of its arms.
 * The whole indication is small enough (827 rows for Cutaneous Melanoma) to
 * group, filter and count in the browser.
 */

/** One `trial_outcomes` row with the registry and landscape fields it joins to. */
export interface OutcomeRow {
  id: number;
  nct_id: string;
  abstract_id: string | null;
  publication_id: string | null;
  source_name: string | null;
  source_type: string | null;
  arm_name: string | null;
  target_protein: string | null;
  num_patients: number | null;
  /** Columns whose median was not reached; the column itself is null. */
  is_nr: string[] | null;
  /** Columns reported as "<value". */
  is_lt: string[] | null;
  orr: number | null;
  cr: number | null;
  pcr: number | null;
  median_pfs: number | null;
  median_os: number | null;
  hr_pfs: number | null;
  ci_hr_pfs: string | null;
  hr_os: number | null;
  ci_hr_os: string | null;
  hr_efs: number | null;
  ci_hr_efs: string | null;
  hr_rfs: number | null;
  ci_hr_rfs: string | null;
  rfs: number | null;
  efs: number | null;
  grade_3_plus_trae_pct: number | null;
  clinical_trials: {
    acronym: string | null;
    brief_title: string | null;
    phases: string[] | null;
    lead_sponsor_name: string | null;
    lead_sponsor_class: string | null;
    primary_completion_date: string | null;
    trial_landscape: {
      treatment_name: string | null;
      modality: string | null;
      line_of_therapy: string | null;
    };
  };
}

/** Columns the readout query selects, in the shape `OutcomeRow` describes. */
export const OUTCOME_SELECT = [
  'id, nct_id, abstract_id, publication_id, source_name, source_type, arm_name, target_protein, num_patients, is_nr, is_lt',
  'orr, cr, pcr, median_pfs, median_os, hr_pfs, ci_hr_pfs, hr_os, ci_hr_os, hr_efs, ci_hr_efs, hr_rfs, ci_hr_rfs, rfs, efs, grade_3_plus_trae_pct',
  'clinical_trials!inner(acronym, brief_title, phases, lead_sponsor_name, lead_sponsor_class, primary_completion_date,' +
    ' trial_landscape!inner(treatment_name, modality, line_of_therapy))',
].join(', ');

export type EndpointKey = 'hr' | 'median_pfs' | 'median_os' | 'orr' | 'pcr' | 'cr' | 'grade_3_plus_trae_pct';

export interface Endpoint {
  key: EndpointKey;
  label: string;
  unit: 'mo' | '%' | null;
}

export interface Cell {
  value: number | null;
  /** Median not reached. */
  nr: boolean;
  /** Reported as "<value". */
  lt: boolean;
  lo?: number;
  hi?: number;
}

export interface Arm {
  name: string;
  n: number | null;
  values: Partial<Record<EndpointKey, Cell>>;
}

export interface ReadoutSource {
  label: string;
  detail: string | null;
  /** Filter option: the conference, or "Journal publication". */
  group: string;
  year: number | null;
}

export const FILTER_GROUPS = ['phase', 'setting', 'endpoint', 'target', 'modality', 'sponsor', 'source'] as const;
export type FilterGroup = (typeof FILTER_GROUPS)[number];

export interface Readout {
  key: string;
  nctId: string;
  acronym: string | null;
  title: string | null;
  drug: string | null;
  phase: string | null;
  sponsor: string | null;
  completion: string | null;
  source: ReadoutSource;
  arms: Arm[];
  /** Sum of the arms' N; null when no arm reports one. */
  analyzedN: number | null;
  /** The card's columns: up to 4, in the fixed order. */
  endpoints: Endpoint[];
  hasResults: boolean;
  facets: Record<FilterGroup, string[]>;
  searchText: string;
}

export interface ReadoutFilters {
  search: string;
  onlyResults: boolean;
  selected: Partial<Record<FilterGroup, string[]>>;
}

export const EMPTY_FILTERS: ReadoutFilters = { search: '', onlyResults: false, selected: {} };

const MAX_ENDPOINTS = 4;

/** HR kinds, in the order the HR column prefers them. */
const HR_KINDS = [
  { col: 'hr_pfs', ci: 'ci_hr_pfs', label: 'PFS HR' },
  { col: 'hr_os', ci: 'ci_hr_os', label: 'OS HR' },
  { col: 'hr_efs', ci: 'ci_hr_efs', label: 'EFS HR' },
  { col: 'hr_rfs', ci: 'ci_hr_rfs', label: 'RFS HR' },
] as const;

/** Non-HR card columns, in display order after the HR. */
const VALUE_ENDPOINTS: Endpoint[] = [
  { key: 'median_pfs', label: 'Median PFS', unit: 'mo' },
  { key: 'median_os', label: 'Median OS', unit: 'mo' },
  { key: 'orr', label: 'ORR', unit: '%' },
  { key: 'pcr', label: 'Pathologic CR', unit: '%' },
  { key: 'cr', label: 'Complete response', unit: '%' },
  { key: 'grade_3_plus_trae_pct', label: 'Grade 3+ TRAE', unit: '%' },
];

/** "Endpoint reported" filter options, by card column. */
const ENDPOINT_FACET: Partial<Record<EndpointKey, string>> = {
  hr: 'Hazard ratio',
  median_pfs: 'Median PFS',
  median_os: 'Median OS',
  orr: 'ORR',
  pcr: 'pCR',
};

/** What makes a readout count as "with results". */
const RESULT_COLUMNS = ['orr', 'median_pfs', 'median_os', 'pcr', 'hr_pfs', 'hr_os', 'hr_efs', 'hr_rfs', 'rfs', 'efs'] as const;

const MODALITIES = new Set<string>(MODALITY_VALUES);

/** ['PHASE1', 'PHASE2'] -> "Phase 1/2"; a single phase uses the registry label. */
export function phaseLabel(phases: string[] | null): string | null {
  if (!phases?.length) return null;
  if (phases.length === 1) return PHASE_MAP[phases[0]] ?? phases[0];
  return `Phase ${phases.map((p) => p.replace('PHASE', '')).join('/')}`;
}

function sourceOf(row: OutcomeRow): ReadoutSource {
  const abstract = row.abstract_id?.match(/^([A-Za-z]+)_(\d{4})_(.+)$/);
  if (abstract) {
    const [, conference, year, number] = abstract;
    return { label: `${conference} ${year}`, detail: `Abstract ${number}`, group: conference, year: Number(year) };
  }
  if (row.publication_id) {
    const year = row.publication_id.match(/\b(19|20)\d\d\b/);
    return { label: row.publication_id, detail: null, group: 'Journal publication', year: year ? Number(year[0]) : null };
  }
  return { label: 'Web', detail: null, group: 'Web', year: null };
}

function parseCi(ci: string | null): { lo: number; hi: number } | null {
  const m = ci?.match(/^\s*([\d.]+)\s*[-–]\s*([\d.]+)\s*$/);
  return m ? { lo: Number(m[1]), hi: Number(m[2]) } : null;
}

const split = (s: string | null) => (s ?? '').split(';').map((x) => x.trim()).filter(Boolean);

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

function cellFor(row: OutcomeRow, col: keyof OutcomeRow): Cell | undefined {
  const value = row[col] as number | null;
  const nr = row.is_nr?.includes(col) ?? false;
  if (value == null && !nr) return undefined;
  return { value, nr, lt: row.is_lt?.includes(col) ?? false };
}

function buildReadout(key: string, rows: OutcomeRow[]): Readout {
  const first = rows[0];
  const trial = first.clinical_trials;
  // One HR column per card: the first kind any arm reports.
  const hrKind = HR_KINDS.find((k) => rows.some((r) => r[k.col] != null));

  const arms: Arm[] = rows.map((r) => {
    const values: Arm['values'] = {};
    if (hrKind && r[hrKind.col] != null) {
      values.hr = { value: r[hrKind.col], nr: false, lt: false, ...parseCi(r[hrKind.ci]) };
    }
    for (const e of VALUE_ENDPOINTS) {
      const cell = cellFor(r, e.key as keyof OutcomeRow);
      if (cell) values[e.key] = cell;
    }
    return { name: r.arm_name ?? 'Unnamed group', n: r.num_patients, values };
  });

  const reported = (k: EndpointKey) => arms.some((a) => a.values[k]);
  const allEndpoints: Endpoint[] = [
    ...(hrKind ? [{ key: 'hr' as const, label: hrKind.label, unit: null }] : []),
    ...VALUE_ENDPOINTS,
  ].filter((e) => reported(e.key));

  const ns = arms.map((a) => a.n).filter((n): n is number => n != null);
  const source = sourceOf(first);
  const phase = phaseLabel(trial.phases);

  return {
    key,
    nctId: first.nct_id,
    acronym: trial.acronym,
    title: trial.brief_title,
    drug: trial.trial_landscape.treatment_name,
    phase,
    sponsor: trial.lead_sponsor_name,
    completion: trial.primary_completion_date,
    source,
    arms,
    analyzedN: ns.length ? ns.reduce((a, b) => a + b, 0) : null,
    endpoints: allEndpoints.slice(0, MAX_ENDPOINTS),
    hasResults: rows.some((r) => RESULT_COLUMNS.some((c) => r[c] != null) || (r.is_nr?.some((c) => c === 'median_pfs' || c === 'median_os') ?? false)),
    facets: {
      phase: phase ? [phase] : [],
      setting: unique(split(trial.trial_landscape.line_of_therapy)),
      endpoint: allEndpoints.flatMap((e) => ENDPOINT_FACET[e.key] ?? []),
      target: unique(rows.flatMap((r) => split(r.target_protein)).filter((t) => t !== 'N/A')),
      modality: unique(split(trial.trial_landscape.modality).filter((m) => MODALITIES.has(m))),
      sponsor: [trial.lead_sponsor_class === 'INDUSTRY' ? 'Industry' : 'Non-industry'],
      source: [source.group],
    },
    searchText: [trial.acronym, trial.trial_landscape.treatment_name, first.nct_id, ...arms.map((a) => a.name)]
      .filter(Boolean)
      .join(' ')
      .toLowerCase(),
  };
}

/** Group outcome rows into readouts: one per trial and source, one arm per row. */
export function groupReadouts(rows: OutcomeRow[]): Readout[] {
  const groups = new Map<string, OutcomeRow[]>();
  for (const r of rows) {
    const key = `${r.nct_id}|${r.abstract_id ?? r.publication_id ?? r.source_name ?? ''}`;
    const group = groups.get(key);
    if (group) group.push(r);
    else groups.set(key, [r]);
  }
  return [...groups].map(([key, group]) => buildReadout(key, group));
}

/**
 * Newest primary completion first, missing dates last. Readouts of one trial
 * share its date, so ties go to the readout's own year.
 */
export function sortReadouts(readouts: Readout[]): Readout[] {
  const desc = (a: string | number | null, b: string | number | null) =>
    a === b ? 0 : a == null ? 1 : b == null ? -1 : a < b ? 1 : -1;
  return [...readouts].sort(
    (a, b) => desc(a.completion, b.completion) || desc(a.source.year, b.source.year) || a.key.localeCompare(b.key),
  );
}

/**
 * Readouts passing every filter. `except` skips one group's selection, which
 * is how that group's own counts are taken.
 */
export function filterReadouts(readouts: Readout[], filters: ReadoutFilters, except?: FilterGroup): Readout[] {
  const q = filters.search.trim().toLowerCase();
  return readouts.filter(
    (r) =>
      (!filters.onlyResults || r.hasResults) &&
      (!q || r.searchText.includes(q)) &&
      FILTER_GROUPS.every((g) => {
        const picked = filters.selected[g];
        return g === except || !picked?.length || picked.some((v) => r.facets[g].includes(v));
      }),
  );
}

/** Option counts for one group, with every other group's selection applied. Largest first. */
export function facetCounts(readouts: Readout[], filters: ReadoutFilters, group: FilterGroup): Map<string, number> {
  const counts = new Map<string, number>();
  for (const r of filterReadouts(readouts, filters, group)) {
    for (const v of r.facets[group]) counts.set(v, (counts.get(v) ?? 0) + 1);
  }
  return new Map([...counts].sort((a, b) => b[1] - a[1]));
}

/** Readouts that can go to the agent at once: enough to compare, and each costs it a trial lookup. */
export const MAX_SELECTED = 5;

/**
 * The selection as it goes to the agent, in front of the user's question. Any
 * NCT number in a message makes the agent look the trial up first, and the
 * source tells it which of a trial's readouts was picked.
 */
export function describeSelection(readouts: Readout[]): string {
  const items = readouts.map((r) => {
    const source = [r.source.label, r.source.detail].filter(Boolean).join(' ');
    return `${r.acronym ?? r.drug ?? r.nctId} (${r.nctId}, ${source})`;
  });
  return `About ${items.length === 1 ? 'this readout' : 'these readouts'}: ${items.join('; ')}.`;
}
