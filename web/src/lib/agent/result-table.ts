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

export interface ResultColumn {
  key: string;
  /** What the header reads. The key is a database identifier, not a header. */
  label: string;
}

export interface ResultTable {
  columns: ResultColumn[];
  /** One array of formatted cells per row, aligned to `columns`. */
  rows: string[][];
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
 * `phases`, `overall_status` and `lead_sponsor_class` are usually pruned before
 * they render: the uniform-column rule below removes them under exactly the
 * filtered queries this exists for (every row is PHASE1 when the question said
 * Phase 1). They are listed for the mixed-filter case, not as a bug.
 */
const LEAD_COLUMNS = [
  'nct_id',
  'generic_name',
  'arm_name',
  'treatment_name',
  'interventions',
  'phases',
  'overall_status',
  'lead_sponsor_class',
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
 * One cell, read with its row in hand - which `formatCell` cannot do, and which
 * the censoring markers require.
 */
export function formatRowCell(row: Record<string, unknown>, column: string): string {
  if (marks(row, 'is_nr', column)) return NOT_REACHED;
  const formatted = formatCell(row[column]);
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
};

export function humanizeColumn(key: string): string {
  const known = INITIALISMS[key];
  if (known) return known;
  const words = key.replace(/_/g, ' ').trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function formatCell(value: unknown): string {
  if (value === null || value === undefined || value === '') return ABSENT;
  if (Array.isArray(value)) {
    if (value.length === 0) return ABSENT;
    return value.map(formatEntry).join(', ');
  }
  return formatEntry(value);
}

/** One element of a cell: an intervention object, or a plain scalar. */
function formatEntry(value: unknown): string {
  if (value !== null && typeof value === 'object') {
    const { name, type } = value as { name?: unknown; type?: unknown };
    if (typeof name === 'string') {
      return typeof type === 'string' ? `${name} (${type})` : name;
    }
    return JSON.stringify(value);
  }
  return String(value);
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
