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

export interface ResultTable {
  columns: string[];
  /** One array of formatted cells per row, aligned to `columns`. */
  rows: string[][];
}

/** Absent values are shown, not skipped: an uncurated trial is a finding. */
const ABSENT = '—';

function formatCell(value: unknown): string {
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

  return {
    columns,
    rows: rows.map((row) =>
      columns.map((column) =>
        typeof row === 'object' && row !== null
          ? formatCell((row as Record<string, unknown>)[column])
          : ABSENT,
      ),
    ),
  };
}
