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
  const columns: string[] = [];
  for (const row of rows) {
    if (typeof row !== 'object' || row === null) continue;
    for (const key of Object.keys(row)) if (!columns.includes(key)) columns.push(key);
  }
  if (columns.length === 0) return null;

  const cells = new Map<string, string[]>();
  for (const column of columns) {
    cells.set(
      column,
      rows.map((row) =>
        typeof row === 'object' && row !== null
          ? formatCell((row as Record<string, unknown>)[column])
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
