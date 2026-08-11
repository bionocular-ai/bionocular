/**
 * The five relations the agent may read, and how to query each one.
 *
 * This map is measured against the live database, not inferred from the app
 * code, because the tables disagree with each other: `cancer_type` is `text[]`
 * on four of them but a plain `text` scalar on `km_curves`, and `news_feed` has
 * no `nct_id` at all - it carries `nct_ids` `text[]`. PostgREST throws
 * `malformed array literal` when `.eq()` hits a `text[]` column, so the
 * operator has to be derived from the column's kind here rather than guessed at
 * a call site. Adding a table means adding an entry, not a branch.
 *
 * `clinical_trials_cache` (raw CT.gov jsonb) and `v_clinical_trials_with_results`
 * are deliberately absent: the first is unparsed source data, and the second's
 * `has_outcomes` flag inherits the `trial_outcomes` linkage gap described below.
 */

/** Anchored on purpose - PostgREST takes whatever string it is handed. */
export const NCT_ID_PATTERN = /^NCT\d{8}$/;

export type ColumnKind = 'array' | 'scalar';

export interface AgentColumn {
  readonly column: string;
  readonly kind: ColumnKind;
}

export interface AgentTableSpec {
  /** One line describing the table, used to generate the tool description. */
  readonly summary: string;
  readonly cancerType: AgentColumn;
  /** Absent where a table has no trial identifier at all. */
  readonly trialKey: AgentColumn | null;
  /** Explicit column list. Never `*` - `trial_outcomes` alone has 205 columns. */
  readonly projection: string;
  /**
   * Named filters this table supports, mapped to their real columns. The kind
   * decides the operator the same way it does for cancer scope: `array` means
   * `.contains()`, `scalar` means a case-insensitive substring match.
   */
  readonly filters: {
    readonly sponsor?: AgentColumn;
    readonly phase?: AgentColumn;
    readonly drug?: AgentColumn;
  };
  /** Surfaced with every result for this table so the model can qualify it. */
  readonly caveat?: string;
}

const TABLE_DEFINITIONS = {
  clinical_trials: {
    summary: 'trial registry mirror - one row per trial, with our cancer-type tagging',
    cancerType: { column: 'cancer_type', kind: 'array' },
    trialKey: { column: 'nct_id', kind: 'scalar' },
    projection:
      'nct_id, brief_title, overall_status, phases, enrollment_count, ' +
      'lead_sponsor_name, lead_sponsor_class, conditions, study_type',
    filters: {
      sponsor: { column: 'lead_sponsor_name', kind: 'scalar' },
      phase: { column: 'phases', kind: 'array' },
    },
  },

  trial_landscape: {
    summary:
      'curated treatment landscape - interventional trials only, one row per trial, ' +
      'with treatment, modality, biomarker, stage and line of therapy',
    cancerType: { column: 'cancer_type', kind: 'array' },
    trialKey: { column: 'nct_id', kind: 'scalar' },
    projection:
      'nct_id, treatment_name, modality, biomarker, stage, line_of_therapy, ' +
      'previous_treatment_criteria, cancer_type',
    filters: { drug: { column: 'treatment_name', kind: 'scalar' } },
    caveat:
      'Observational studies are excluded from this table by design. A trial missing here ' +
      'may still exist in clinical_trials.',
  },

  trial_outcomes: {
    summary:
      'extracted efficacy and safety endpoints, one row per treatment arm, from ' +
      'conference abstracts and publications',
    cancerType: { column: 'cancer_type', kind: 'array' },
    trialKey: { column: 'nct_id', kind: 'scalar' },
    projection:
      'id, source_type, source_name, abstract_id, publication_id, nct_id, arm_name, ' +
      'generic_name, line_of_treatment, num_patients, median_pfs, hr_pfs, median_os, ' +
      'hr_os, orr, dcr, median_dor, grade_3_plus_trae_pct, serious_ae_pct',
    filters: {
      sponsor: { column: 'sponsors', kind: 'scalar' },
      drug: { column: 'generic_name', kind: 'scalar' },
    },
    caveat:
      'Roughly 44% of rows in this table have no nct_id - they are conference abstracts ' +
      'identified by abstract_id instead. A trial-ID filter cannot see them, so absence ' +
      'from an NCT-filtered result here is not evidence that no outcome data exists.',
  },

  km_curves: {
    summary:
      'digitised Kaplan-Meier survival curves reconstructed from published figures',
    // The one scalar cancer_type in the set. Do not "fix" this to an array.
    cancerType: { column: 'cancer_type', kind: 'scalar' },
    trialKey: { column: 'nct_id', kind: 'scalar' },
    projection:
      'id, nct_id, publication_id, cancer_type, comparison_label, arm_name, endpoint, ' +
      'published_median, twin_median, rate_timepoint, published_rate, twin_rate, ' +
      'median_follow_up, match_pct, n_points, reference',
    filters: { drug: { column: 'arm_name', kind: 'scalar' } },
  },

  news_feed: {
    summary: 'scraped oncology news and conference coverage',
    cancerType: { column: 'cancer_type', kind: 'array' },
    // No nct_id column - an article can reference several trials.
    trialKey: { column: 'nct_ids', kind: 'array' },
    projection: 'url, title, date, nct_ids, cancer_type, has_efficacy, has_safety',
    filters: {},
  },
} as const satisfies Record<string, AgentTableSpec>;

export type AgentTable = keyof typeof TABLE_DEFINITIONS;

/**
 * Same object, widened to the interface: `as const` alone would make `caveat`
 * and each `filters` key absent from the tables that omit them, which no caller
 * can index generically.
 */
export const AGENT_TABLES: Record<AgentTable, AgentTableSpec> = TABLE_DEFINITIONS;

export const AGENT_TABLE_NAMES = Object.keys(AGENT_TABLES) as [AgentTable, ...AgentTable[]];

/**
 * Minimal shape of a PostgREST query builder. Structural so the helpers below
 * work against any stage of the chain without importing supabase-js generics.
 */
export interface FilterableQuery<Q> {
  eq(column: string, value: unknown): Q;
  contains(column: string, value: unknown): Q;
  ilike(column: string, pattern: string): Q;
}

/**
 * Restrict a query to one cancer type. Always applied - `cancer_type` is
 * non-null in all five tables, so this predicate can never silently drop rows
 * that should have been in scope.
 */
export function applyCancerScope<Q extends FilterableQuery<Q>>(
  query: Q,
  table: AgentTable,
  dbCancerType: string,
): Q {
  const { column, kind } = AGENT_TABLES[table].cancerType;
  return kind === 'array' ? query.contains(column, [dbCancerType]) : query.eq(column, dbCancerType);
}

/** Match a single trial by whichever key the table actually uses. */
export function applyTrialKey<Q extends FilterableQuery<Q>>(
  query: Q,
  table: AgentTable,
  nctId: string,
): Q {
  const key = AGENT_TABLES[table].trialKey;
  if (!key) return query;
  return key.kind === 'array' ? query.contains(key.column, [nctId]) : query.eq(key.column, nctId);
}

export type FilterName = 'sponsor' | 'phase' | 'drug';

/**
 * Apply one named filter, or return null if this table does not support it -
 * `phase` exists only on `clinical_trials`, `drug` means a different column on
 * every table that has one. The caller turns null into a structured refusal
 * rather than a silently unfiltered query.
 */
export function applyNamedFilter<Q extends FilterableQuery<Q>>(
  query: Q,
  table: AgentTable,
  name: FilterName,
  value: string,
): Q | null {
  const spec = AGENT_TABLES[table].filters[name];
  if (!spec) return null;
  return spec.kind === 'array'
    ? query.contains(spec.column, [value])
    : query.ilike(spec.column, `%${value}%`);
}

/** Columns a caller may ask for by name, for error messages and descriptions. */
export function projectionColumns(table: AgentTable): string[] {
  return AGENT_TABLES[table].projection.split(',').map((c) => c.trim());
}

export function supportedFilters(table: AgentTable): FilterName[] {
  return Object.keys(AGENT_TABLES[table].filters) as FilterName[];
}

/**
 * Build the tool description from the map, so it can never again advertise
 * filters or tables that do not exist.
 */
export function describeTables(): string {
  return AGENT_TABLE_NAMES.map((name) => {
    const spec = AGENT_TABLES[name];
    const filters = supportedFilters(name);
    const filterText = filters.length ? `filters: ${filters.join(', ')}` : 'no extra filters';
    const trialText = spec.trialKey ? `trial key: ${spec.trialKey.column}` : 'no trial key';
    return `- \`${name}\`: ${spec.summary} (${trialText}; ${filterText})`;
  }).join('\n');
}
