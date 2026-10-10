/**
 * A tool result's rows, as a table the app draws itself.
 *
 * The model is good at deciding what to query and at reading what came back. It
 * is unreliable at the step in between: copying rows into prose. Asked for the
 * 53 active Phase 3 cutaneous melanoma trials it received all 53, pivoted from
 * one row per trial to one row per treatment, packed NCT numbers into cells, and
 * 8 trials were merged away - while the summary still said 53. Nothing in the
 * code dropped them and every grounding check passed.
 *
 * Transcription is the one part of a turn whose correct output is known in
 * advance, so it is the one part that should never be sampled. Columns come from
 * the rows rather than a per-table mapping, so a new table renders with no
 * change here.
 */

import { normalizePhase, normalizePurpose, normalizeStatus } from '@/lib/clinical-trials-enums';
import { regimenKey } from './regimen';
import { TRIAL_OUTCOMES_ENDPOINTS } from './tools/schema';

export interface ResultColumn {
  key: string;
  /** What the header reads. The key is a database identifier, not a header. */
  label: string;
}

/**
 * The counts a landscape is read by, above the sections.
 *
 * Taken from the rows before the uniform-column rule runs: `is_basket` is
 * exactly the column that rule deletes when every trial in a result is a
 * pan-tumour platform, and a result that is entirely off-indication is the one
 * that most needs to say so.
 */
export interface ResultSummary {
  trials: number;
  /** Trials with a curated `treatment_name`; the rest are registry-only. */
  curated: number;
  /** Pan-tumour platforms, set aside from the landscape rather than counted in. */
  setAside: number;
  industry: number;
  nonIndustry: number;
}

/** An endpoint the reader can put on screen, and how many treatments report it. */
export interface ResultParameter {
  key: string;
  label: string;
  family: 'efficacy' | 'safety';
  arms: number;
  /** Columns drawn beside this endpoint and hidden with it: its follow-up and p-value. */
  companions?: string[];
}

export interface ResultTable {
  columns: ResultColumn[];
  /** One array of formatted cells per row, aligned to `columns`. */
  rows: string[][];
  /** Present only for a landscape turn - one whose rows carry a `setting`. */
  summary?: ResultSummary;
  /**
   * Present only for an outcomes turn: the endpoint columns, most-reported
   * first. Each is also in `columns`; which ones are drawn is the reader's pick.
   */
  parameters?: ResultParameter[];
  /** The endpoints the question named, in its order: drawn before the reader picks. */
  asked?: string[];
  /**
   * Present only for an outcomes turn with a treatment reported more than
   * once: aligned with `rows`, each treatment's earlier readouts as cells in
   * `columns` order, newest first.
   */
  readouts?: string[][][];
  /**
   * Present when an asked adverse-event class had to stand in for another, or
   * some treatments report the measure only under a class not shown. Drawn
   * above the table.
   */
  caveat?: string;
}

/**
 * What every answer states about a trial: who pays for it, which line it
 * treats, and which biomarker it selects for. A column identical on every row
 * is otherwise dropped as noise; these stay, so an all-industry result still
 * says Industry rather than leaving the reader to wonder.
 */
export const ALWAYS_SHOWN = ['sponsor_type', 'line_of_therapy', 'line', 'biomarker'];

/** Absent values are shown, not skipped: an uncurated trial is a finding. */
export const ABSENT = '—';

/** A measurement the study reached the end of follow-up without observing. */
export const NOT_REACHED = 'NR';

/**
 * Columns that name other columns instead of carrying a measurement.
 *
 * `is_nr text[]` and `is_lt text[]` each hold column names: a not-reached
 * median stores NULL in e.g. `median_os` and the string `'median_os'` in
 * `is_nr`; `is_lt` does the same for a censored value like "<1%", stored as
 * the number 1. Rendering the null as ABSENT says "no data" where the truth is
 * "not reached", and rendering the 1 bare says a measured 1%.
 *
 * They are metadata about neighbouring cells, so they are never columns of
 * their own - and once the rule below has fired they carry nothing the reader
 * still needs.
 */
export const MARKER_COLUMNS = ['is_nr', 'is_lt'];

/**
 * Columns selected only so a query's ORDER BY names a column it selects (the
 * ordering test requires it). A sheet row number tells a reader nothing.
 */
export const ORDER_ONLY_COLUMNS = ['sheet_row'];

/**
 * Columns worth seeing first, in this order; everything else keeps the order it
 * was discovered in, behind them.
 *
 * `trial_outcomes` at `detailed` is a 198-column projection listed loader-first,
 * so the rendered table opened on `id`, `source_type`, `source_name`,
 * `abstract_id` and `publication_id`, with `nct_id` 5th and `median_pfs` 16th -
 * every column a reader wants was past the right edge.
 *
 * The treatment leads, not the identifier. The question is always about a drug
 * or a regimen; `nct_id` is how a reader follows one up, which is the second
 * thing they do, not the first. Whichever of the four treatment columns a
 * table carries takes the first position, so a curated regimen, an arm and a
 * raw registry list all land in the same place.
 *
 * `phases` and `lead_sponsor_class` are usually pruned before
 * they render: the uniform-column rule below removes them under exactly the
 * filtered queries this exists for (every row is PHASE1 when the question said
 * Phase 1). They are listed for the mixed-filter case, not as a bug.
 */
const LEAD_COLUMNS = [
  'treatment_name',
  'generic_name',
  'arm_name',
  'interventions',
  'nct_id',
  'setting',
  'us_status',
  'phases',
  'follow_up_only',
  'lead_sponsor_name',
  'lead_sponsor_class',
  'sponsor_type',
  'num_patients',
  'orr',
  'dcr',
  'median_pfs',
  'median_os',
  'median_dor',
  'hr_pfs',
  'hr_os',
  'grade_3_plus_trae_pct',
];

/**
 * Status closes the row: it is what a reader checks last, once the treatment and
 * the numbers have made a trial worth pursuing.
 */
const TRAIL_COLUMNS = ['overall_status'];

/**
 * Both render paths call this, so a lone query and a joined turn agree. Stable:
 * a column the lead list does not name keeps its position relative to the other
 * unnamed ones.
 */
export function orderColumns(keys: readonly string[]): string[] {
  return keys
    .map((key, index) => {
      const lead = LEAD_COLUMNS.indexOf(key);
      const trail = TRAIL_COLUMNS.indexOf(key);
      const rank =
        trail !== -1
          ? LEAD_COLUMNS.length + keys.length + trail
          : lead === -1
            ? LEAD_COLUMNS.length + index
            : lead;
      return { key, rank };
    })
    .sort((a, b) => a.rank - b.rank)
    .map(({ key }) => key);
}

/** Whether this row's `marker` column names `column` as censored. */
function marks(row: Record<string, unknown>, marker: string, column: string): boolean {
  const named = row[marker];
  return Array.isArray(named) && named.includes(column);
}

/**
 * Columns whose values are ClinicalTrials.gov enums rather than prose.
 *
 * `humanizeColumn` has always titled the header while the cells under it read
 * `ACTIVE_NOT_RECRUITING` and `PHASE3` - a registry identifier shown to a
 * clinician. The labels are keyed by column rather than matched on the string,
 * because a screaming-case value is not reliably an enum: `NRAS`, `TMB` and
 * `BRAF` are gene symbols and stay exactly as they are.
 */
const ENUM_LABELS: Record<string, (raw: string) => string> = {
  overall_status: normalizeStatus,
  phases: normalizePhase,
  primary_purpose: normalizePurpose,
  expert_review: (raw) => (raw === 'good' ? 'Good' : raw === 'issues' ? 'Issues found' : raw),
};

/** Durations in months: the medians of time-to-event endpoints, and follow-up. */
const MONTHS = /^median_(pfs|os|dor)$|_followup_months$/;

/**
 * One cell, read with its row in hand - which `formatCell` cannot do, and which
 * the censoring markers require.
 */
export function formatRowCell(row: Record<string, unknown>, column: string): string {
  if (marks(row, 'is_nr', column)) return NOT_REACHED;
  const value = row[column];
  // Months are reported to a decimal ("11.0 months"), and the float column
  // drops a trailing zero, so 11.0 would read as a rounded 11 beside 19.4.
  const formatted =
    MONTHS.test(column) && typeof value === 'number' && Number.isInteger(value)
      ? value.toFixed(1)
      : formatCell(value, ENUM_LABELS[column]);
  if (formatted !== ABSENT && marks(row, 'is_lt', column)) return `<${formatted}`;
  return formatted;
}

/** Initialisms a title-cased key would otherwise mangle into "Nct" or "Orr". */
const INITIALISMS: Record<string, string> = {
  nct_id: 'NCT',
  orr: 'ORR',
  dcr: 'DCR',
  median_pfs: 'Median PFS',
  median_os: 'Median OS',
  hr_pfs: 'HR PFS',
  hr_os: 'HR OS',
  median_dor: 'Median DoR',
  lead_sponsor_name: 'Sponsor',
  overall_status: 'Status',
  sponsor_type: 'Type',
  expert_review: 'Expert review',
  us_status: 'US status',
  nccn_tier: 'NCCN tier',
  nccn_category: 'NCCN category',
  // The setting is the section heading above it; the column carries the line.
  line_of_therapy: 'Line',
};

/**
 * Endpoint abbreviations as a clinician writes them. Matched per word, so the
 * hundred-odd endpoint columns read "OS rate 18m" and "G3+ TRAE %" without
 * each being listed.
 */
const ENDPOINT_WORDS: Record<string, string> = {
  os: 'OS', pfs: 'PFS', efs: 'EFS', rfs: 'RFS', mfs: 'MFS', orr: 'ORR', dcr: 'DCR', cr: 'CR',
  pcr: 'pCR', cmr: 'CMR', cbr: 'CBR', dor: 'DoR', ttr: 'TTR', ttp: 'TTP', ttnt: 'TTNT', ttf: 'TTF',
  hr: 'HR', ci: 'CI', ae: 'AE', trae: 'TRAE', teae: 'TEAE', crs: 'CRS', irr: 'IRR',
  wbc: 'WBC', alt: 'ALT', ast: 'AST', pct: '%',
};

/** The columns spell it two ways, and word-splitting the short one reads "IR AE". */
const IR_AE = /(^|_)(immune_related|ir)_ae(?=_|$)/;

/**
 * Phrases rewritten on the key before it is split into words. The short forms
 * are the ones the hubs' labels use (`src/types/analytics.ts`), so a header
 * fits a heatmap column - "AE Disc %", not "AE leading to discontinuation %" -
 * but every safety header still names its AE class. The long forms are the
 * header's tooltip.
 */
const SHORT_PHRASES: [RegExp, string][] = [
  [/^grade_3_plus_/, 'G3+_'],
  [/^grade_(\d)_/, 'G$1_'],
  [/^serious_ae_pct$/, 'SAE_pct'],
  [IR_AE, '$1irAE'],
  [/(leading_to_)?discontinuation/, 'Disc'],
  [/neutrophil_count_decreased/, 'neutrophil↓'],
  [/dose_interruption/, 'dose int.'],
  [/dose_reduction/, 'dose red.'],
  [/hospitalization/, 'hosp.'],
];
const LONG_PHRASES: [RegExp, string][] = [
  [/^grade_3_plus_/, 'grade 3+_'],
  [IR_AE, '$1immune-related AE'],
];

/** Abbreviations whose lower-case first letter is the spelling, not a slip. */
const MIXED_CASE = new Set(['pCR', 'irAE']);

/** Time-to-event endpoints a source reports in months, beyond the `median_*` ones. */
export const MONTH_ENDPOINTS = /^median_|^(efs|rfs|mfs|ttr|ttp|ttnt|ttf)$|_followup_months$/;

/**
 * A column's header; `short = false` spells the endpoint out, for its tooltip.
 * A duration carries its unit, so "19.4" under Median PFS reads as months.
 */
export function humanizeColumn(key: string, short = true): string {
  const label = spellColumn(key, short);
  return MONTH_ENDPOINTS.test(key) && !key.endsWith('_followup_months') ? `${label} (mo)` : label;
}

function spellColumn(key: string, short: boolean): string {
  const known = INITIALISMS[key];
  if (known) return known;
  const words = (short ? SHORT_PHRASES : LONG_PHRASES)
    .reduce((phrase, [pattern, replacement]) => phrase.replace(pattern, replacement), key)
    .split('_')
    .map((word) => ENDPOINT_WORDS[word] ?? word)
    .join(' ')
    .trim();
  if (MIXED_CASE.has(words.split(' ')[0])) return words;
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The spelled-out header, when the shown one abbreviates it. */
export function columnTooltip(key: string): string | undefined {
  const long = humanizeColumn(key, false);
  return long !== humanizeColumn(key) ? long : undefined;
}

/**
 * How a landscape reads: one group per clinical setting, then the trials that
 * are not a therapy for this indication at all.
 *
 * `SET_ASIDE` is last and never merged into a setting. A pan-tumour platform
 * has a line of therapy like any other trial, so it would otherwise sit among
 * the options a reader is weighing - which is the thing the summary strip has
 * just said it is not.
 */
export const SETTING_ORDER = [
  'Advanced / metastatic',
  'Peri-operative',
  'Procedural / supportive',
  'Unclassified',
] as const;

export const SET_ASIDE = 'Set aside · pan-tumour';

export interface Section {
  /** Null when the rows carry no setting and the table renders flat. */
  label: string | null;
  rows: string[][];
  /** Rows the section holds before `capSections` cut it; the heading's count. */
  total: number;
}

/**
 * Rows grouped for display: by `setting`, in `SETTING_ORDER`, with baskets
 * pulled out last and empty groups dropped.
 *
 * A setting `SETTING_ORDER` does not list still renders, appended in the order
 * it was met - an unrecognised value costs the reader its position, never its
 * rows.
 */
export function toSections(
  rows: string[][],
  settingIndex: number,
  basketIndex = -1,
): Section[] {
  if (settingIndex === -1) return [{ label: null, rows, total: rows.length }];

  const groups = new Map<string, string[][]>();
  for (const label of SETTING_ORDER) groups.set(label, []);
  const setAside: string[][] = [];
  for (const row of rows) {
    if (basketIndex !== -1 && row[basketIndex] === 'true') {
      setAside.push(row);
      continue;
    }
    const group = groups.get(row[settingIndex]);
    if (group) group.push(row);
    else groups.set(row[settingIndex], [row]);
  }
  if (setAside.length > 0) groups.set(SET_ASIDE, setAside);
  return [...groups]
    .filter(([, group]) => group.length > 0)
    .map(([label, group]) => ({ label, rows: group, total: group.length }));
}

/**
 * The first `limit` rows in reading order - section by section - so "show 20
 * more" continues where the reader stopped instead of topping up every section
 * at once. A section cut to nothing is dropped; its heading keeps its total.
 */
export function capSections(sections: Section[], limit: number): Section[] {
  let left = limit;
  const kept: Section[] = [];
  for (const section of sections) {
    if (left <= 0) break;
    kept.push({ ...section, rows: section.rows.slice(0, left) });
    left -= section.rows.length;
  }
  return kept;
}

/**
 * `label` maps one registry enum to its reading. It applies per element rather
 * than to the joined string, so `["PHASE2","PHASE3"]` reads "Phase 2, Phase 3".
 */
export function formatCell(value: unknown, label?: (raw: string) => string): string {
  if (value === null || value === undefined || value === '') return ABSENT;
  if (Array.isArray(value)) {
    if (value.length === 0) return ABSENT;
    return value.map((entry) => formatEntry(entry, label)).join(', ');
  }
  return formatEntry(value, label);
}

/** One element of a cell: an intervention object, or a plain scalar. */
function formatEntry(value: unknown, label?: (raw: string) => string): string {
  if (value !== null && typeof value === 'object') {
    const { name, type } = value as { name?: unknown; type?: unknown };
    if (typeof name === 'string') {
      return typeof type === 'string' ? `${name} (${type})` : name;
    }
    return JSON.stringify(value);
  }
  return label && typeof value === 'string' ? label(value) : String(value);
}

export function toResultTable(output: unknown): ResultTable | null {
  if (typeof output !== 'object' || output === null) return null;
  const { ok, rows } = output as { ok?: unknown; rows?: unknown };
  if (ok !== true || !Array.isArray(rows) || rows.length === 0) return null;

  // Union rather than the first row's keys: PostgREST omits nothing, but a
  // joined or partial row would otherwise lose a column silently.
  const discovered: string[] = [];
  for (const row of rows) {
    if (typeof row !== 'object' || row === null) continue;
    for (const key of Object.keys(row)) if (!discovered.includes(key)) discovered.push(key);
  }
  const columns = orderColumns(
    discovered.filter((key) => !MARKER_COLUMNS.includes(key) && !ORDER_ONLY_COLUMNS.includes(key)),
  );
  if (columns.length === 0) return null;

  const cells = new Map<string, string[]>();
  for (const column of columns) {
    cells.set(
      column,
      rows.map((row) =>
        typeof row === 'object' && row !== null
          ? formatRowCell(row as Record<string, unknown>, column)
          : ABSENT,
      ),
    );
  }

  // A value that is identical on every row distinguishes nothing: cancer_type is
  // pinned by applyCancerScope, study_type was one value on all 53 rows of the
  // Phase 3 sweep. Derived rather than named, so a new such column needs no edit.
  const kept =
    rows.length > 1
      ? columns.filter(
          (column) => ALWAYS_SHOWN.includes(column) || new Set(cells.get(column)).size > 1,
        )
      : columns;
  if (kept.length === 0) return null;

  return {
    columns: kept.map((key) => ({ key, label: humanizeColumn(key) })),
    rows: rows.map((_, rowIndex) => kept.map((column) => cells.get(column)![rowIndex])),
  };
}

/**
 * A column the reader can narrow the table by.
 *
 * Derived from the rendered cells rather than named: the agent chooses its own
 * projection, so a fixed list of filterable columns would be wrong on the next
 * question. A column qualifies when its values form a closed set the reader can
 * recognise - few of them, short, and each shared by several rows. That rules
 * out identifiers (one value per row), measurements (all distinct) and prose.
 *
 * Hidden columns count: `setting` is drawn as section headings and `sponsor_type`
 * as a pill, and both are exactly what a landscape is narrowed by.
 */
export interface Facet {
  /** Index into `columns`, so a hidden column filters as well as a drawn one. */
  index: number;
  label: string;
  values: string[];
}

/** Below this, the whole table is read at a glance and a filter bar is furniture. */
const FILTER_MIN_ROWS = 8;
const MAX_FACET_VALUES = 6;
/** Three chip rows is what fits above the table without becoming the page. */
const MAX_FACETS = 3;
/** Longer than this is a sentence, not a category. */
const MAX_VALUE_LENGTH = 28;

/**
 * A filter has no column beside it to lend context, so "Type" alone would not
 * say whose type. "Sponsor: Industry" does, and is how a reader says it.
 */
const FACET_LABELS: Record<string, string> = { sponsor_type: 'Sponsor' };

export function toFacets(table: ResultTable): Facet[] {
  if (table.rows.length < FILTER_MIN_ROWS) return [];
  // `sponsor_type` is `lead_sponsor_class` collapsed to industry or not, so the
  // raw registry class (INDUSTRY, OTHER, NIH...) would only be the same filter
  // spelled worse, and would spend a facet slot doing it.
  const hasSponsorType = table.columns.some((column) => column.key === 'sponsor_type');
  // Both are already drawn - `follow_up_only` as a note under the status,
  // `is_basket` as the "Set aside" section - and as filters they read "yes" or
  // "None" and took the slot Status needed.
  const notFacets = [
    // Filtered by its own toggle, which says "reviewed by an expert (MD or PhD)" in words.
    'expert_review',
    'follow_up_only',
    'is_basket',
    ...(hasSponsorType ? ['lead_sponsor_class'] : []),
    // An outcomes question already asked for active trials, so Status only
    // split that set by recruiting or not.
    ...(table.parameters ? ['overall_status'] : []),
  ];
  return table.columns
    .map((column, index) => ({
      key: column.key,
      index,
      label: FACET_LABELS[column.key] ?? column.label,
      values: [...new Set(table.rows.map((row) => row[index]))].sort(),
    }))
    .filter(
      ({ key, values }) =>
        !notFacets.includes(key) &&
        // Measurements, not groupings: CR reported as 15 or 20 on a few arms
        // reads as a closed set of values, and is not one. Every endpoint, not
        // only the parameters: companion columns are endpoints that are not
        // parameters.
        !TRIAL_OUTCOMES_ENDPOINTS.has(key) &&
        values.length > 1 &&
        values.length <= MAX_FACET_VALUES &&
        // A grouping, not a near-identifier: every value covers two rows on average.
        values.length * 2 <= table.rows.length &&
        values.every((value) => value.length <= MAX_VALUE_LENGTH)
    )
    .slice(0, MAX_FACETS)
    .map(({ index, label, values }) => ({ index, label, values }));
}

/**
 * The rows still standing: every chosen facet value matched, and `query` found
 * somewhere in the row.
 *
 * `selected` is keyed by column index and holds one value per facet - chips are
 * a choice, not a multi-select, so the counts a reader sees always add up to
 * one column's worth. Search runs over the whole row rather than a named column
 * because the reader is looking for a drug, a sponsor or an NCT number without
 * caring which cell holds it.
 */
export function filterRows(
  rows: string[][],
  selected: Record<number, string>,
  query: string
): string[][] {
  const needle = query.trim().toLowerCase();
  const chosen = Object.entries(selected);
  if (chosen.length === 0 && needle === '') return rows;
  return rows.filter(
    (row) =>
      chosen.every(([index, value]) => row[Number(index)] === value) &&
      (needle === '' || row.join(' ').toLowerCase().includes(needle))
  );
}

/**
 * Endpoints drawn before the reader picks: the ones the question named, else
 * the most-reported. `parameters` is ranked by how many arms report each, so
 * these are the three the most arms can be compared on - ORR, DCR and CR for
 * the active Phase 1 set, PFS and OS where trials mature.
 */
export const DEFAULT_PARAMETERS = 3;

export function defaultPicks(table: ResultTable): string[] {
  const parameters = table.parameters ?? [];
  const asked = (table.asked ?? []).filter((key) => parameters.some((p) => p.key === key));
  return asked.length > 0 ? asked : parameters.slice(0, DEFAULT_PARAMETERS).map((p) => p.key);
}

/**
 * Whether a treatment answers the picked columns: its own cells, or any earlier
 * readout's - RELATIVITY-047's any-cause rate sits in NEJM 2022, not the newest
 * readout, and the treatment must not read as silent for that.
 */
export function reportsAny(readouts: string[][], indices: number[]): boolean {
  return readouts.some((cells) => indices.some((index) => cells[index] !== ABSENT));
}

interface Counted {
  /** Table rows: one per treatment arm or cohort of a trial, earlier readouts folded in. */
  arms: number;
  /**
   * Distinct regimens per trial, by `regimenKey`: three cohorts of one combination
   * in one trial are one treatment, the same combination in two trials is two.
   */
  treatments: number;
  trials: number;
}

export interface AnswerCounts extends Counted {
  /** The endpoints counted: the ones the table draws before the reader picks. */
  columns: string[];
  reporting: Counted;
  /**
   * What reports none of `columns`: arms, the treatments with no reporting arm
   * anywhere, and the trials those arms belong to - read as "36 arms across
   * 22 trials", which a trial that also has a reporting arm is part of.
   */
  none: Counted;
}

/**
 * The count an outcomes answer opens with, taken from the table the app draws
 * rather than left to the model. Counting the rows itself, the model wrote
 * "16 arms across 9 trials" and, from the same 72 rows, "17 across 8", beside a
 * table of 19 arms - 16 treatments - across 12 trials.
 */
export function answerCounts(table: ResultTable): AnswerCounts | null {
  const columns = defaultPicks(table);
  if (columns.length === 0) return null;
  const index = (key: string) => table.columns.findIndex((column) => column.key === key);
  const indices = columns.map(index);
  const [nct, name] = [index('nct_id'), index('treatment_name')];
  const present = (cell: string | undefined): cell is string => cell !== undefined && cell !== ABSENT;
  const distinct = (rows: string[][], at: number) => new Set(rows.map((row) => row[at]).filter(present));
  const regimens = (rows: string[][]) =>
    new Set(rows.filter((row) => present(row[name])).map((row) => `${row[nct]} ${regimenKey(row[name])}`));
  const count = (rows: string[][], treatments = regimens(rows).size): Counted => ({
    arms: rows.length,
    treatments,
    trials: distinct(rows, nct).size,
  });
  const reports = (row: string[], i: number) => reportsAny([row, ...(table.readouts?.[i] ?? [])], indices);
  const reporting = table.rows.filter(reports);
  const silent = table.rows.filter((row, i) => !reports(row, i));
  const answered = regimens(reporting);
  return {
    columns,
    ...count(table.rows),
    reporting: count(reporting),
    none: count(silent, [...regimens(silent)].filter((key) => !answered.has(key)).length),
  };
}
