/**
 * A turn's queries, joined into the one table the answer is about.
 *
 * "Phase 3 active treatments in cutaneous melanoma" is two queries: the trials
 * matching phase and status, then the curated landscape rows for exactly those
 * NCT numbers. Rendered apart, the landscape rows carry no trial name or status
 * and the five trials with no landscape row read as unasked-for. The join is
 * mechanical - one key, one direction - so the app does it rather than the model.
 *
 * A turn with exactly one successful query has nothing to join, so it renders
 * that query's own table (`toResultTable`) instead: the trial_outcomes shape -
 * one row per treatment arm, duplicate nct_ids by design - is a single query as
 * often as it is the second half of a pair, and the duplicate-key rule below
 * exists to protect a join spine, not to gate a query that never joins anything.
 *
 * One column knows about other columns, and it is declared here rather than
 * scattered: the registry fallback for a treatment that has not been curated.
 * Everything else is derived from the rows.
 */

import {
  ABSENT,
  ALWAYS_SHOWN,
  MARKER_COLUMNS,
  formatCell,
  formatRowCell,
  humanizeColumn,
  orderColumns,
  toResultTable,
  type ResultColumn,
  type ResultParameter,
  type ResultSummary,
  type ResultTable,
} from './result-table';
import { TRIAL_OUTCOMES_EFFICACY, TRIAL_OUTCOMES_SAFETY } from './tools/schema';

const KEY = 'nct_id';

/**
 * `acronym` and `brief_title` arrive on every `clinical_trials` row but neither
 * is rendered: NCT is already the identity column, and a title long enough to
 * identify a trial runs 116-272 characters - one column of those makes every
 * row in the table multiple lines tall. The model still receives both in the
 * row regardless, so a trial's name is not lost, only not tabled.
 *
 * The rest are read by `derive` or the model but not worth a column: purpose
 * and primary completion already surface as `setting` and "follow-up only".
 * Stripped after `derive` runs, so the facts built from them survive.
 */
const FOLDED_TRIAL_FIELDS = [
  'acronym',
  'brief_title',
  'enrollment_count',
  'primary_purpose',
  'stage',
  'primary_completion_date',
] as const;

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

function treatmentCell(row: Row): string {
  const curated = formatCell(row[FALLBACK.target]);
  if (curated !== ABSENT) return curated;
  const registry = formatCell(row[FALLBACK.source]);
  return registry === ABSENT ? ABSENT : `${registry} · ${FALLBACK.marker}`;
}

/** Same success check `asJoinable` starts with, minus the join-spine rules. */
function isSuccessful(output: unknown): boolean {
  if (typeof output !== 'object' || output === null) return false;
  const { ok, rows } = output as { ok?: unknown; rows?: unknown };
  return ok === true && Array.isArray(rows) && rows.length > 0;
}

/**
 * Strip the folded fields from a single query's rows before it reaches
 * `toResultTable`, so a lone `clinical_trials` query agrees with the join
 * path above: `acronym`/`brief_title` still arrive in the row the model
 * reads, they are just never a column here either.
 */
/**
 * Three facts a landscape reader wants first, none of which any row states
 * outright: which setting a trial belongs to, whether its sponsor is industry,
 * and whether "active" still means enrolling. Each is a rule over columns the
 * row already carries, so the app derives them here - deterministically, and
 * the same way on the joined path and the single-query one. A row that
 * carries none of a rule's inputs gets no column from it, so an outcomes
 * table does not grow three empty columns.
 *
 * Setting precedence: a trial with a resectable cohort is designed around
 * surgery, so peri-operative wins over advanced when both tokens appear
 * ("1L; Adjuvant"). The line-of-therapy column still shows every token.
 */
const PROCEDURAL_MODALITIES = ['Radiotherapy', 'Surgery/Procedure', 'Imaging/Diagnostic Agent', 'Device'];

/** The setting a line of therapy puts a trial or arm in, when it names one. */
function lineSetting(line: unknown): string | null {
  const lot = typeof line === 'string' ? line : '';
  if (/Adjuvant|Neoadjuvant/.test(lot)) return 'Peri-operative';
  if (/\b(1L|2L|3L|R\/R)\b/.test(lot)) return 'Advanced / metastatic';
  return null;
}

function derive(row: Row, today: string): Row {
  const next = { ...row };
  const modality = typeof row.modality === 'string' ? row.modality : '';

  // Modality alone does not open the rule: it only decides the procedural
  // branch, and a row with a modality but no line or purpose would otherwise
  // read "Unclassified" for want of columns the turn never asked for.
  if ('line_of_therapy' in row || 'primary_purpose' in row) {
    const setting = lineSetting(row.line_of_therapy);
    if (setting) next.setting = setting;
    else if (
      ('primary_purpose' in row && row.primary_purpose !== 'TREATMENT') ||
      PROCEDURAL_MODALITIES.some((m) => modality.includes(m))
    ) next.setting = 'Procedural / supportive';
    else next.setting = 'Unclassified';
  }

  const sponsor = sponsorType(row.lead_sponsor_class);
  if (sponsor) next.sponsor_type = sponsor;

  if ('overall_status' in row && 'primary_completion_date' in row) {
    const date = typeof row.primary_completion_date === 'string' ? row.primary_completion_date : null;
    // A month-precision date means "sometime that month"; compared as a string,
    // '2026-09' sorts before '2026-09-22' and would read as already past.
    const end = date && date.length === 7 ? `${date}-31` : date;
    next.follow_up_only =
      row.overall_status === 'ACTIVE_NOT_RECRUITING' && end !== null && end < today ? 'yes' : null;
  }

  return next;
}

function sponsorType(sponsorClass: unknown): string | null {
  if (typeof sponsorClass !== 'string') return null;
  return sponsorClass === 'INDUSTRY' ? 'Industry' : 'Non-industry';
}

/**
 * One row per treatment arm, so a trial's key repeats by design. The arms are
 * the answer: a turn that queried one of these draws it, and the registry or
 * landscape queries beside it were the model looking around, not the answer.
 * Joining them instead once drew a 616-trial landscape under a Phase 1
 * efficacy question (session b38c68c7).
 */
const PER_ARM_TABLES = ['trial_outcomes', 'km_curves'];

function isPerArm(output: unknown): boolean {
  const table = (output as { table?: unknown }).table;
  return typeof table === 'string' && PER_ARM_TABLES.includes(table);
}

const ENDPOINT_FAMILY = new Map<string, ResultParameter['family']>([
  ...TRIAL_OUTCOMES_EFFICACY.map((key) => [key, 'efficacy'] as const),
  ...TRIAL_OUTCOMES_SAFETY.map((key) => [key, 'safety'] as const),
]);

/** A p-value, CI or follow-up qualifies an endpoint; alone it is not one. */
const isQualifier = (key: string) => /^(p_value|ci)_|_followup_months$/.test(key);

/**
 * Who the arm is, then the facts every answer states about its trial.
 * `setting` is drawn as the section headings, not as a column.
 */
const OUTCOME_CONTEXT = [
  'treatment_name', 'nct_id', 'setting', 'phases', 'num_patients', 'sponsor_type', 'line', 'biomarker',
];
const OUTCOME_FACTS = ['setting', 'sponsor_type', 'line', 'biomarker'];
const OUTCOME_TRAIL = ['source', 'overall_status'];
const OUTCOME_LABELS: Record<string, string> = {
  treatment_name: 'Treatment',
  num_patients: 'N',
  sponsor_type: 'Sponsor',
};

/**
 * The key must be in the row: `is_nr` names every censored column the arm has,
 * including the other family's, which a safety query never projected. Without
 * this a not-reached median PFS offered itself as a safety parameter.
 */
function reports(row: Row, key: string): boolean {
  if (!(key in row)) return false;
  const notReached = row.is_nr;
  return row[key] != null || (Array.isArray(notReached) && notReached.includes(key));
}

/**
 * An outcomes result as the reader scans it: the arm, its trial and the three
 * trial facts, the endpoints, then where the numbers came from. Loader
 * bookkeeping (`id`, `arm_id`, `source_type`...) never becomes a column.
 *
 * Every endpoint any arm reports is a column, ranked by how many arms report
 * it; `TurnTable` draws the reader's pick of them. The arm's own line of
 * treatment wins over the trial's line of therapy - it is the more specific.
 */
function toOutcomesTable(output: unknown): ResultTable | null {
  const rows: Row[] = rowsOf(output)
    .filter((row): row is Row => typeof row === 'object' && row !== null)
    .map((row) => {
      const line = row.line_of_treatment ?? row.line_of_therapy ?? null;
      return {
        ...row,
        treatment_name: row.arm_name ?? row.generic_name ?? null,
        // `source_name` is a loader batch label, never a reference; a web-scraped
        // readout's page is.
        source: row.abstract_id ?? row.publication_id ?? row.source_url ?? null,
        line,
        // Grouped like a landscape. The arm's line decides, so a trial with an
        // adjuvant arm and a metastatic arm puts each in its own section.
        setting: lineSetting(line) ?? 'Unclassified',
        sponsor_type: sponsorType(row.lead_sponsor_class),
      };
    });
  if (rows.length === 0) return null;

  const endpoints = orderColumns([...ENDPOINT_FAMILY.keys()].filter((key) => !isQualifier(key)))
    .map((key) => ({ key, arms: rows.filter((row) => reports(row, key)).length }))
    .filter(({ arms }) => arms > 0)
    // Stable, so arms tied on a count keep the clinical order `orderColumns` gave them.
    .sort((a, b) => b.arms - a.arms);
  const parameters: ResultParameter[] = endpoints.map(({ key, arms }) => ({
    key,
    label: humanizeColumn(key),
    family: ENDPOINT_FAMILY.get(key)!,
    arms,
  }));

  const columns = [...OUTCOME_CONTEXT, ...parameters.map((p) => p.key), ...OUTCOME_TRAIL].filter(
    (key) => OUTCOME_FACTS.includes(key) || rows.some((row) => reports(row, key)),
  );

  return {
    columns: columns.map((key) => ({ key, label: OUTCOME_LABELS[key] ?? humanizeColumn(key) })),
    rows: rows.map((row) => columns.map((column) => formatRowCell(row, column))),
    parameters,
  };
}

function stripFolded(output: unknown, today: string): unknown {
  if (typeof output !== 'object' || output === null) return output;
  const { rows, ...rest } = output as { rows?: unknown };
  if (!Array.isArray(rows)) return output;
  return {
    ...rest,
    rows: rows.map((row) => {
      if (typeof row !== 'object' || row === null) return row;
      const next = derive(row as Row, today);
      for (const field of FOLDED_TRIAL_FIELDS) delete next[field];
      return next;
    }),
  };
}

export function toTurnTable(outputs: unknown[], now: Date = new Date()): ResultTable | null {
  const today = now.toISOString().slice(0, 10);
  const successful = outputs.filter(isSuccessful);
  if (successful.length === 0) return null;

  const perArm = successful.filter(isPerArm);
  const answer = perArm[perArm.length - 1];
  if (answer && (answer as { table?: unknown }).table === 'trial_outcomes') return toOutcomesTable(answer);
  if (answer || successful.length === 1) {
    const only = answer ?? successful[0];
    const stripped = stripFolded(only, today);
    const table = toResultTable(stripped);
    return table && withSummary(table, rowsOf(stripped));
  }
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
  for (const [key, row] of merged) merged.set(key, derive(row, today));

  const folded: string[] = [KEY, ...FOLDED_TRIAL_FIELDS, FALLBACK.source, ...MARKER_COLUMNS];
  const hasTreatmentName = queries.some((rows) => rows.some((row) => FALLBACK.target in row));
  const discovered: string[] = [KEY];
  // Nothing curated joined it, so the registry list is the only treatment there
  // is. It stands as its own column where treatment_name would otherwise have
  // sat - first, ahead of the key - rather than trailing behind unrelated
  // columns like orr or median_pfs. `orderColumns` ranks `interventions` among
  // the treatment names, so that placement survives the sort below.
  if (!hasTreatmentName) discovered.push(FALLBACK.source);
  for (const rows of queries) {
    for (const row of rows) {
      for (const column of Object.keys(row)) {
        if (folded.includes(column) || discovered.includes(column)) continue;
        discovered.push(column);
      }
    }
  }
  // Derived columns exist only on the merged rows, so they are discovered last.
  for (const row of merged.values()) {
    for (const column of Object.keys(row)) {
      if (folded.includes(column) || discovered.includes(column)) continue;
      discovered.push(column);
    }
  }
  const columns = orderColumns(discovered);

  const cells = [...merged.values()].map((row) =>
    columns.map((column) => {
      if (column === FALLBACK.target) return treatmentCell(row);
      return formatRowCell(row, column);
    }),
  );

  // Same rule as a single result: a column identical on every row distinguishes
  // nothing. `nct_id` is unique, so it always survives.
  const keep =
    cells.length > 1
      ? columns.map(
          (column, i) => ALWAYS_SHOWN.includes(column) || new Set(cells.map((row) => row[i])).size > 1,
        )
      : columns.map(() => true);

  const kept: ResultColumn[] = columns
    .map((key, i) => ({ key, label: humanizeColumn(key), i }))
    .filter(({ i }) => keep[i])
    .map(({ key, label }) => ({ key, label }));
  if (kept.length === 0) return null;

  return withSummary(
    { columns: kept, rows: cells.map((row) => row.filter((_, i) => keep[i])) },
    [...merged.values()],
  );
}

/**
 * The question already said which phase, so a column of it only repeats that
 * back - "Phase 2/Phase 3" beside "Phase 3" is a registry detail the reader did
 * not ask to see. Read from the tool inputs because the rows cannot say what
 * was filtered on. A turn that never passed `phase` keeps the column.
 */
export function withoutAskedPhase(table: ResultTable, inputs: unknown[]): ResultTable {
  const asked = inputs.some(
    (input) => typeof input === 'object' && input !== null && (input as Row).phase !== undefined,
  );
  const index = table.columns.findIndex((column) => column.key === 'phases');
  if (!asked || index === -1) return table;
  return {
    ...table,
    columns: table.columns.filter((_, i) => i !== index),
    rows: table.rows.map((row) => row.filter((_, i) => i !== index)),
  };
}

function rowsOf(output: unknown): Row[] {
  const rows = (output as { rows?: unknown })?.rows;
  return Array.isArray(rows) ? (rows as Row[]) : [];
}

/**
 * The strip's counts, from the rows rather than the rendered cells.
 *
 * Only a landscape turn gets one: `derive` writes `setting` exactly when the
 * row carries a line of therapy or a primary purpose, which is also the
 * condition for the table to have sections to put a strip above. An outcomes
 * table gets no strip instead of a strip of zeroes.
 */
function summarise(rows: Row[]): ResultSummary | undefined {
  if (!rows.some((row) => 'setting' in row)) return undefined;
  let curated = 0;
  let setAside = 0;
  let industry = 0;
  let nonIndustry = 0;
  for (const row of rows) {
    if (row[FALLBACK.target] != null) curated += 1;
    if (row.is_basket === true) setAside += 1;
    // Counted rather than subtracted from the total: a row whose query never
    // projected `lead_sponsor_class` belongs to neither side, and inferring one
    // from `trials - industry` would invent a non-industry trial.
    if (row.sponsor_type === 'Industry') industry += 1;
    else if (row.sponsor_type === 'Non-industry') nonIndustry += 1;
  }
  return { trials: rows.length, curated, setAside, industry, nonIndustry };
}

function withSummary(table: ResultTable, rows: Row[]): ResultTable {
  const summary = summarise(rows);
  return summary ? { ...table, summary } : table;
}
