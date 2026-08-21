/**
 * A turn's queries, joined into the one table the answer is about.
 *
 * "Phase 3 active treatments in cutaneous melanoma" is two queries: the trials
 * matching phase and status, then the curated landscape rows for exactly those
 * NCT numbers. Rendered apart, the landscape rows carry no trial name or status
 * and the five trials with no landscape row read as unasked-for. The join is
 * mechanical - one key, one direction - so the app does it rather than the model.
 *
 * Two columns know about other columns, and both are declared here rather than
 * scattered: a trial's label, and the registry fallback for a treatment that has
 * not been curated. Everything else is derived from the rows.
 */

import { ABSENT, formatCell, humanizeColumn, type ResultColumn, type ResultTable } from './result-table';

const KEY = 'nct_id';

/** `acronym` is null on 30 of the 53 Phase 3 melanoma trials; the title always exists. */
const TRIAL = { target: 'trial', label: 'Trial', sources: ['acronym', 'brief_title'] } as const;

/**
 * `treatment_name` is one curated regimen per trial. `interventions` is every arm
 * the registry lists - comparators, procedures and placebo arms included, so
 * `No re-excision` appears as an intervention. The fallback is real data and the
 * marker is what keeps the two from reading as the same claim.
 */
const FALLBACK = { target: 'treatment_name', source: 'interventions', marker: 'registry' } as const;

type Row = Record<string, unknown>;

/**
 * A tool result usable as a join input: succeeded, has rows, every row keyed,
 * and one row per key. `trial_outcomes` is one row per treatment arm and
 * `km_curves` is one row per arm/endpoint - both keyed by nct_id, so a turn
 * that queries either alongside `clinical_trials` has duplicate keys. Folding
 * those into one spine would silently keep only the last arm of each trial,
 * exactly what this module exists to prevent, so such a result disqualifies
 * the whole turn instead.
 */
function asJoinable(output: unknown): Row[] | null {
  if (typeof output !== 'object' || output === null) return null;
  const { ok, rows } = output as { ok?: unknown; rows?: unknown };
  if (ok !== true || !Array.isArray(rows) || rows.length === 0) return null;

  const keyed = rows.filter(
    (row): row is Row =>
      typeof row === 'object' && row !== null && typeof (row as Row)[KEY] === 'string',
  );
  if (keyed.length !== rows.length) return null;

  const distinct = new Set(keyed.map((row) => row[KEY]));
  return distinct.size === keyed.length ? keyed : null;
}

function trialCell(row: Row): string {
  for (const source of TRIAL.sources) {
    const value = formatCell(row[source]);
    if (value !== ABSENT) return value;
  }
  return ABSENT;
}

function treatmentCell(row: Row): string {
  const curated = formatCell(row[FALLBACK.target]);
  if (curated !== ABSENT) return curated;
  const registry = formatCell(row[FALLBACK.source]);
  return registry === ABSENT ? ABSENT : `${registry} · ${FALLBACK.marker}`;
}

export function toTurnTable(outputs: unknown[]): ResultTable | null {
  const queries = outputs.map(asJoinable).filter((rows): rows is Row[] => rows !== null);
  if (queries.length < 2) return null;

  // Row order comes from the first query: it is the one that answered the
  // question, and the later ones were scoped to the keys it returned. A key only
  // a later query carries is appended, never dropped - this is a left join from
  // the first query outward, not an inner one. Column conflicts go the other
  // way: PostgREST projects every column including nulls, so a later query's
  // null must not clobber an earlier query's real value - first non-null wins.
  const merged = new Map<string, Row>();
  for (const rows of queries) {
    for (const row of rows) {
      const key = row[KEY] as string;
      const existing = merged.get(key) ?? {};
      const next: Row = { ...existing };
      for (const [column, value] of Object.entries(row)) {
        if (value === null || value === undefined) continue;
        next[column] = value;
      }
      merged.set(key, next);
    }
  }

  const folded: string[] = [KEY, ...TRIAL.sources, FALLBACK.source];
  const hasTreatmentName = queries.some((rows) => rows.some((row) => FALLBACK.target in row));
  const columns: string[] = [KEY, TRIAL.target];
  // Nothing curated joined it, so the registry list is the only treatment there
  // is. It stands as its own column where treatment_name would otherwise have
  // sat - directly after the trial - rather than trailing behind unrelated
  // columns like orr or median_pfs.
  if (!hasTreatmentName) columns.push(FALLBACK.source);
  for (const rows of queries) {
    for (const row of rows) {
      for (const column of Object.keys(row)) {
        if (folded.includes(column) || columns.includes(column)) continue;
        columns.push(column);
      }
    }
  }

  const cells = [...merged.values()].map((row) =>
    columns.map((column) => {
      if (column === TRIAL.target) return trialCell(row);
      if (column === FALLBACK.target) return treatmentCell(row);
      return formatCell(row[column]);
    }),
  );

  // Same rule as a single result: a column identical on every row distinguishes
  // nothing. `nct_id` is unique, so it always survives.
  const keep =
    cells.length > 1
      ? columns.map((_, i) => new Set(cells.map((row) => row[i])).size > 1)
      : columns.map(() => true);

  const kept: ResultColumn[] = columns
    .map((key, i) => ({ key, label: key === TRIAL.target ? TRIAL.label : humanizeColumn(key), i }))
    .filter(({ i }) => keep[i])
    .map(({ key, label }) => ({ key, label }));
  if (kept.length === 0) return null;

  return { columns: kept, rows: cells.map((row) => row.filter((_, i) => keep[i])) };
}
