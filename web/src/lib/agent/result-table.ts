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

export interface ResultTable {
  columns: ResultColumn[];
  /** One array of formatted cells per row, aligned to `columns`. */
  rows: string[][];
  /** Present only for a landscape turn - one whose rows carry a `setting`. */
  summary?: ResultSummary;
}

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
 * `phases`, `overall_status` and `lead_sponsor_class` are usually pruned before
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
  'phases',
  'overall_status',
  'follow_up_only',
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
 * Both render paths call this, so a lone query and a joined turn agree. Stable:
 * a column the lead list does not name keeps its position relative to the other
 * unnamed ones.
 */
export function orderColumns(keys: readonly string[]): string[] {
  return keys
    .map((key, index) => {
      const lead = LEAD_COLUMNS.indexOf(key);
      return { key, rank: lead === -1 ? LEAD_COLUMNS.length + index : lead };
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
};

/**
 * One cell, read with its row in hand - which `formatCell` cannot do, and which
 * the censoring markers require.
 */
export function formatRowCell(row: Record<string, unknown>, column: string): string {
  if (marks(row, 'is_nr', column)) return NOT_REACHED;
  const formatted = formatCell(row[column], ENUM_LABELS[column]);
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
  // The two safety endpoints the concise projection carries. Word-splitting
  // renders them "Grade 3 plus trae pct" and "Serious ae pct" - the wider
  // `detailed` safety columns are the same shape, and get the same treatment
  // if a question ever puts one on screen.
  grade_3_plus_trae_pct: 'Grade 3+ TRAE %',
  serious_ae_pct: 'Serious AE %',
};

export function humanizeColumn(key: string): string {
  const known = INITIALISMS[key];
  if (known) return known;
  const words = key.replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
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
  if (settingIndex === -1) return [{ label: null, rows }];

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
    .map(([label, group]) => ({ label, rows: group }));
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
  const columns = orderColumns(discovered.filter((key) => !MARKER_COLUMNS.includes(key)));
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
      ? columns.filter((column) => new Set(cells.get(column)).size > 1)
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

export function toFacets(table: ResultTable): Facet[] {
  if (table.rows.length < FILTER_MIN_ROWS) return [];
  return table.columns
    .map((column, index) => ({
      index,
      label: column.label,
      values: [...new Set(table.rows.map((row) => row[index]))].sort(),
    }))
    .filter(
      ({ values }) =>
        values.length > 1 &&
        values.length <= MAX_FACET_VALUES &&
        // A grouping, not a near-identifier: every value covers two rows on average.
        values.length * 2 <= table.rows.length &&
        values.every((value) => value.length <= MAX_VALUE_LENGTH)
    )
    .slice(0, MAX_FACETS);
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
