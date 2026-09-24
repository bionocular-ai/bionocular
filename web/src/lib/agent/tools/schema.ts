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

/**
 * `partition` has one implementation on purpose. `funding` is not a value to
 * match but a two-way split of one, and the alternative - `exact` over the
 * eight non-INDUSTRY enum values - would silently exclude a row whose
 * `lead_sponsor_class` is null. Measured 2026-08-31 there are none, in
 * cutaneous melanoma or across all 4,350 registry rows, but `.in()` would make
 * the first one that appears vanish from both halves rather than one.
 */
export type ColumnKind = 'array' | 'scalar' | 'exact' | 'partition';

export interface AgentColumn {
  readonly column: string;
  readonly kind: ColumnKind;
}

/** One `ORDER BY` term. Nulls always sort last so a missing date never leads. */
export interface AgentOrder {
  readonly column: string;
  readonly ascending: boolean;
}

export interface AgentTableSpec {
  /** One line describing the table, used to generate the tool description. */
  readonly summary: string;
  readonly cancerType: AgentColumn;
  /** Absent where a table has no trial identifier at all. */
  readonly trialKey: AgentColumn | null;
  /**
   * Applied to every bounded read of this table. Without it Postgres returns
   * heap order, so a 25-row window was a different sample on two identical
   * calls and `fitToBudget` trimmed an arbitrary tail. The last term is always
   * a unique key, so the order is total and a window is reproducible.
   */
  readonly order: readonly AgentOrder[];
  /**
   * Explicit column list. Never `*` - `trial_outcomes` alone has 205 columns,
   * and `select=*` on it measured 4.5 MB / 3.5s against 1.04 MB / 1.9s for the
   * explicit list on the same result set. The invariant holds on wire cost
   * even though the wide `detailed` projection below approaches `*` in width -
   * `all_attributes`, `created_at`, `confidence`, and the cancer-scope-pinned
   * `cancer_type` stay excluded regardless.
   */
  readonly projection: string;
  /**
   * Named filters this table supports, mapped to their real columns. The kind
   * decides the operator the same way it does for cancer scope: `array` means
   * `.contains()`, `scalar` means a case-insensitive substring match.
   */
  readonly filters: Partial<Record<FilterName, AgentColumn>>;
  /**
   * The columns an answer is actually built from. Falls back to `projection`
   * where a table has no leaner form worth the split.
   */
  readonly conciseProjection?: string;
  /** Surfaced with every result for this table so the model can qualify it. */
  readonly caveat?: string;
  /**
   * Filters this table does not hold, resolved through a foreign key. PostgREST
   * evaluates them server-side via an embedded `!inner` join, so a phase-scoped
   * outcomes query is one request rather than a 1,134-key handoff no cap admits.
   */
  readonly via?: {
    readonly table: 'clinical_trials';
    readonly filters: Partial<Record<FilterName, AgentColumn>>;
  };
  /**
   * Trial-level facts every answer states - sponsor class, biomarker, line of
   * therapy - fetched from whichever table holds them rather than this one.
   * `embed` is the relation they are read through. On a table with a `via`, it
   * is the same `clinical_trials` relation, so its columns join the via-filter
   * columns in one embed; see `embedFor`.
   */
  readonly facts?: { readonly embed: string; readonly columns: readonly string[] };
}

/** Where the curated biomarker and line of therapy live, embedded from `clinical_trials`. */
const LANDSCAPE_FACTS = 'trial_landscape(biomarker,line_of_therapy)';
/** Sponsor class from the registry, then the curated landscape through it. */
const REGISTRY_FACTS = { embed: 'clinical_trials', columns: ['lead_sponsor_class', LANDSCAPE_FACTS] } as const;

// The month timepoints both PFS and OS carry a `_rate_{n}m` column for.
const RATE_MONTHS = [6, 9, 12, 18, 24, 36, 48] as const;

// Per-toxicity grade-3+ terms. Identical across the ae/trae/teae families, so
// this list is written once and expanded three ways below.
const GRADE_3_PLUS_TERMS = [
  'ir_ae', 'crs', 'thrombocytopenia', 'neutropenia', 'leukopenia', 'nausea',
  'anemia', 'diarrhea', 'colitis', 'hyperglycemia', 'neutrophil_count_decreased',
  'dyspnea', 'pyrexia', 'bleeding', 'pruritus', 'rash', 'pneumonia',
  'thyroiditis', 'hypophysitis', 'hepatitis', 'pneumonitis', 'alt_increased',
  'wbc_decreased', 'ast_increased', 'fatigue', 'hyperthyroidism',
  'hypothyroidism', 'irr', 'vomiting',
] as const;

// Safety-aggregate `_pct` columns, one list per family. Not symmetric:
// `immune_related_ae_pct` and `serious_ir_ae_pct` exist only on the any-cause
// `ae` family, and its discontinuation column is spelled differently from
// trae/teae's - these are typed out rather than derived because there is no
// naming rule that produces them.
const AE_AGGREGATE_PCT = [
  'ae_pct', 'grade_3_plus_ae_pct', 'ae_leading_to_discontinuation_pct',
  'serious_ae_pct', 'immune_related_ae_pct', 'serious_ir_ae_pct', 'ae_death_pct',
  'ae_dose_interruption_pct', 'ae_dose_reduction_pct', 'ae_hospitalization_pct',
];
const TRAE_AGGREGATE_PCT = [
  'trae_pct', 'grade_3_plus_trae_pct', 'grade_3_trae_pct', 'grade_4_trae_pct',
  'grade_5_trae_pct', 'trae_discontinuation_pct', 'trae_death_pct',
  'trae_ir_ae_pct', 'serious_trae_pct', 'trae_dose_interruption_pct',
  'trae_dose_reduction_pct', 'trae_hospitalization_pct',
];
const TEAE_AGGREGATE_PCT = [
  'teae_pct', 'grade_3_plus_teae_pct', 'grade_3_teae_pct', 'grade_4_teae_pct',
  'grade_5_teae_pct', 'teae_discontinuation_pct', 'teae_death_pct',
  'teae_ir_ae_pct', 'serious_teae_pct', 'teae_dose_interruption_pct',
  'teae_dose_reduction_pct', 'teae_hospitalization_pct',
];

const rateColumns = (endpoint: 'pfs' | 'os'): string[] =>
  RATE_MONTHS.map((m) => `${endpoint}_rate_${m}m`);

const grade3PlusColumns = (family: 'ae' | 'trae' | 'teae'): string[] =>
  GRADE_3_PLUS_TERMS.map((term) => `grade_3_plus_${family}_${term}`);

/**
 * Who the arm is and where the numbers came from. Neither an efficacy nor a
 * safety endpoint, so an `endpoints`-narrowed query keeps all of it - a table
 * of adverse-event rates with no arm name is not an answer.
 */
const TRIAL_OUTCOMES_IDENTITY = [
  'id', 'source_type', 'source_name', 'abstract_id', 'publication_id',
  // The only reference a web-scraped readout has - no abstract or publication
  // ID - so without it the arm cites nothing. Null, and dropped, everywhere else.
  'source_url', 'nct_id',
  'arm_id', 'arm_name', 'sponsors', 'line_of_treatment', 'generic_name',
  'brand_name', 'dosage', 'type_of_dosing', 'mechanism_of_action',
  'target_protein', 'type_of_therapy', 'sub_therapy', 'modality', 'median_age',
  'num_patients',
  // Column names that hold a censored measurement, not the measurement itself
  // - see the `is_nr`/`is_lt` note on `conciseProjection` below.
  'is_nr', 'is_lt',
];

/** Did it work: survival, response, and duration of response. */
export const TRIAL_OUTCOMES_EFFICACY = [
  // PFS / OS
  'median_pfs', 'pfs_followup_months', 'p_value_pfs', 'hr_pfs', 'ci_hr_pfs',
  ...rateColumns('pfs'),
  'median_os', 'os_followup_months', 'p_value_os', 'hr_os', 'ci_hr_os',
  ...rateColumns('os'),
  // other survival
  'efs', 'p_value_efs', 'hr_efs', 'ci_hr_efs',
  'rfs', 'p_value_rfs', 'rfs_followup_months', 'hr_rfs', 'ci_hr_rfs',
  'mfs', 'mfs_followup_months', 'hr_mfs', 'ci_hr_mfs',
  // response
  'orr', 'cr', 'pcr', 'cmr', 'dcr', 'cbr', 'median_dor', 'dor_rate', 'ttr',
  'ttp', 'hr_ttp', 'ci_hr_ttp', 'ttnt', 'ttf',
];

/** What it cost: the adverse-event families and the standalone toxicities. */
export const TRIAL_OUTCOMES_SAFETY = [
  // safety aggregates
  ...AE_AGGREGATE_PCT, ...TRAE_AGGREGATE_PCT, ...TEAE_AGGREGATE_PCT,
  // per-toxicity grade 3+
  ...grade3PlusColumns('ae'), ...grade3PlusColumns('trae'), ...grade3PlusColumns('teae'),
  // standalone
  'crs_pct', 'wbc_decreased_pct', 'irr_pct',
];

/**
 * Every extracted efficacy and safety endpoint `trial_outcomes` carries, built
 * from families rather than typed out by hand so a new column from the loader
 * is one array entry, not a search-and-add across a 198-name string.
 *
 * Excludes exactly six columns from the table's 205: `all_attributes` (the
 * LLM-extraction shadow copy - 3.5 MB of `"Not found"` on the target result
 * set), `created_at`, `cancer_type` (pinned to one value by
 * `applyCancerScope`, so it can tell the model nothing), `confidence`,
 * `validation_status`, and `validated_at`.
 *
 * `is_lt` postdates the CSV backup this list is checked against in
 * supabase.test.ts (added by migration 20260805000000_trial_outcomes_
 * validation_columns.sql), so it is appended by hand rather than falling out
 * of the CSV header like everything else here.
 */
const TRIAL_OUTCOMES_PROJECTION = [
  ...TRIAL_OUTCOMES_IDENTITY,
  ...TRIAL_OUTCOMES_EFFICACY,
  ...TRIAL_OUTCOMES_SAFETY,
].join(', ');

const TABLE_DEFINITIONS = {
  clinical_trials: {
    summary: 'trial registry mirror - one row per trial, with our cancer-type tagging',
    cancerType: { column: 'cancer_type', kind: 'array' },
    trialKey: { column: 'nct_id', kind: 'scalar' },
    // Most recently changed on the registry first - the same order the
    // dashboard's recent-updates feed uses (`lib/api.ts`).
    order: [
      { column: 'last_update_posted_date', ascending: false },
      { column: 'nct_id', ascending: true },
    ],
    projection:
      'nct_id, acronym, brief_title, overall_status, phases, enrollment_count, ' +
      'lead_sponsor_name, lead_sponsor_class, cancer_type, cancer_type_evidence, ' +
      'conditions, keywords, study_type, last_update_posted_date, is_basket, ' +
      'primary_completion_date, primary_purpose, ' +
      // The registry's own intervention list - drug names and types, straight
      // from the sponsor. Without it "which treatments" had no answer in the
      // one table that can filter by phase and status, so the model reached for
      // `trial_landscape`, which can do neither, and read 500 rows to find 3.
      'interventions',
    // Measured via `count_tokens` (compact JSON, interventions trimmed) over 53
    // Phase 3 trials: the full projection is 15,492 tokens, these seven are 7,743.
    // The difference is re-sent on every later step of the turn, so it is paid
    // more than once.
    //
    // `phases` and `overall_status` stay even though both are filters, because
    // neither predicate is an equality - 10 of the 53 are PHASE2/PHASE3, and the
    // status filter admits four values. `cancer_type` is pinned to one value by
    // `applyCancerScope` and `study_type` was one value on all 53 rows, so
    // neither can tell the model anything it does not already know.
    //
    // `acronym` is sparse (populated on 23 of 53) but brief, so it stays beside
    // `nct_id` rather than adding rows.
    //
    // The five short scalars after `lead_sponsor_name` are what a landscape is
    // read by - sponsor split, size, whether "active" still means enrolling,
    // treatment versus procedure, pan-tumour platform - and none was in the
    // rows of session 809e7692, so its answer could state none of them.
    // Measured 2026-09-22 on the 55 Phase 3 active trials: +141 characters a
    // row, about 2,150 tokens on the set.
    conciseProjection:
      'nct_id, acronym, brief_title, overall_status, phases, lead_sponsor_name, ' +
      'lead_sponsor_class, enrollment_count, primary_completion_date, primary_purpose, is_basket, ' +
      'interventions',
    filters: {
      sponsor: { column: 'lead_sponsor_name', kind: 'scalar' },
      phase: { column: 'phases', kind: 'array' },
      // Exact enum value, so `exact` rather than the default substring match:
      // `ACTIVE_NOT_RECRUITING` must not also match on `NOT_YET_RECRUITING`.
      status: { column: 'overall_status', kind: 'exact' },
      // Distinct from `sponsor`, which is a substring on the sponsor's *name*.
      // This one splits the registry's sponsor *class* the way the product
      // does, and the way the Efficacy Hub's FUNDING chip already labels it.
      funding: { column: 'lead_sponsor_class', kind: 'partition' },
    },
    facts: { embed: 'trial_landscape', columns: ['biomarker', 'line_of_therapy'] },
  },

  trial_landscape: {
    summary:
      'curated treatment landscape - interventional trials only, one row per trial, ' +
      'with treatment, modality, biomarker, stage and line of therapy',
    cancerType: { column: 'cancer_type', kind: 'array' },
    trialKey: { column: 'nct_id', kind: 'scalar' },
    // One row per trial and no date column, so the key alone is total.
    order: [{ column: 'nct_id', ascending: true }],
    projection:
      'nct_id, treatment_name, modality, biomarker, stage, line_of_therapy, ' +
      'previous_treatment_criteria, cancer_type',
    // `previous_treatment_criteria` is paragraph prose, populated on 23% of rows,
    // and is re-sent on every later step of the turn once it is in context.
    // `cancer_type` is pinned to one value by `applyCancerScope`, so it cannot
    // tell the model anything it does not already know. Dropping both leaves
    // the six columns an answer is actually built from.
    conciseProjection:
      'nct_id, treatment_name, modality, biomarker, stage, line_of_therapy',
    filters: {
      drug: { column: 'treatment_name', kind: 'scalar' },
      // "Every BRAF trial" has no other way in: without this the model swept
      // the table phase by phase, 500 rows at a time, to find them.
      biomarker: { column: 'biomarker', kind: 'scalar' },
    },
    caveat:
      'Observational studies are excluded from this table by design. A trial missing here ' +
      'may still exist in clinical_trials.',
    via: {
      table: 'clinical_trials',
      filters: {
        phase: { column: 'phases', kind: 'array' },
        status: { column: 'overall_status', kind: 'exact' },
        funding: { column: 'lead_sponsor_class', kind: 'partition' },
      },
    },
    facts: { embed: 'clinical_trials', columns: ['lead_sponsor_class'] },
  },

  trial_outcomes: {
    summary:
      'extracted efficacy and safety endpoints, one row per treatment arm, from ' +
      'conference abstracts and publications',
    cancerType: { column: 'cancer_type', kind: 'array' },
    trialKey: { column: 'nct_id', kind: 'scalar' },
    // Arms of the same trial sit together; the 44% with no nct_id sort last
    // rather than first, so a trial-keyed window is not filled with them.
    order: [
      { column: 'nct_id', ascending: true },
      { column: 'id', ascending: true },
    ],
    // The full endpoint set - see TRIAL_OUTCOMES_PROJECTION above for how it is
    // built and what it excludes.
    projection: TRIAL_OUTCOMES_PROJECTION,
    // The browse-level 19 columns this table's `projection` used to be, plus
    // `is_nr`/`is_lt`.
    //
    // `is_nr text[]` and `is_lt text[]` hold column names, not values: a
    // not-reached median stores NULL in e.g. `median_os` and the string
    // `'median_os'` in `is_nr` (melanoma/scripts/upload_to_supabase.py:~545);
    // `is_lt` does the same for a censored value like "<1%", stored as the
    // number 1 (melanoma/scripts/apply_publications_validation.py). Neither
    // column was in any projection before this change, so the agent saw
    // `median_dor: null` and reported "no DoR data" when the truth was "DoR
    // not reached" - the opposite clinical claim. On the 189-row target result
    // set, 33 rows carry `is_nr` and `median_dor` is the marked column on 16.
    conciseProjection:
      'id, source_type, source_name, abstract_id, publication_id, source_url, nct_id, arm_name, ' +
      'generic_name, line_of_treatment, num_patients, median_pfs, hr_pfs, median_os, ' +
      'hr_os, orr, dcr, median_dor, grade_3_plus_trae_pct, serious_ae_pct, is_nr, is_lt',
    filters: {
      sponsor: { column: 'sponsors', kind: 'scalar' },
      drug: { column: 'generic_name', kind: 'scalar' },
    },
    caveat:
      'Roughly 44% of rows in this table have no nct_id - they are conference abstracts ' +
      'identified by abstract_id instead. A trial-ID filter cannot see them, so absence ' +
      'from an NCT-filtered result here is not evidence that no outcome data exists.',
    via: {
      table: 'clinical_trials',
      filters: {
        phase: { column: 'phases', kind: 'array' },
        status: { column: 'overall_status', kind: 'exact' },
        funding: { column: 'lead_sponsor_class', kind: 'partition' },
      },
    },
    facts: REGISTRY_FACTS,
  },

  km_curves: {
    summary:
      'digitised Kaplan-Meier survival curves reconstructed from published figures',
    // The one scalar cancer_type in the set. Do not "fix" this to an array.
    cancerType: { column: 'cancer_type', kind: 'scalar' },
    trialKey: { column: 'nct_id', kind: 'scalar' },
    order: [
      { column: 'nct_id', ascending: true },
      { column: 'id', ascending: true },
    ],
    projection:
      'id, nct_id, publication_id, cancer_type, comparison_label, arm_name, endpoint, ' +
      'published_median, twin_median, rate_timepoint, published_rate, twin_rate, ' +
      'median_follow_up, match_pct, n_points, reference',
    filters: { drug: { column: 'arm_name', kind: 'scalar' } },
    // Nullable FK: km_curves rows without a matching clinical_trials row simply
    // never satisfy the `!inner` join, same as any other via-table.
    via: {
      table: 'clinical_trials',
      filters: {
        phase: { column: 'phases', kind: 'array' },
        status: { column: 'overall_status', kind: 'exact' },
        funding: { column: 'lead_sponsor_class', kind: 'partition' },
      },
    },
    facts: REGISTRY_FACTS,
  },

  news_feed: {
    summary: 'scraped oncology news and conference coverage',
    cancerType: { column: 'cancer_type', kind: 'array' },
    // No nct_id column - an article can reference several trials.
    trialKey: { column: 'nct_ids', kind: 'array' },
    // Newest coverage first; `url` is the row's identity.
    order: [
      { column: 'date', ascending: false },
      { column: 'url', ascending: true },
    ],
    projection: 'url, title, date, nct_ids, cancer_type, has_efficacy, has_safety',
    // A headline is the only text the row carries, so "news about nivolumab"
    // is a substring on it; the models asked for exactly this filter and were
    // refused.
    filters: { drug: { column: 'title', kind: 'scalar' } },
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
  neq(column: string, value: unknown): Q;
  in(column: string, values: readonly unknown[]): Q;
  contains(column: string, value: unknown): Q;
  overlaps(column: string, values: readonly unknown[]): Q;
  ilike(column: string, pattern: string): Q;
  order(column: string, options: { ascending: boolean; nullsFirst: boolean }): Q;
}

/**
 * Apply the table's total order. Every bounded read goes through here, so no
 * query in this directory relies on heap order.
 */
export function applyOrder<Q extends FilterableQuery<Q>>(query: Q, table: AgentTable): Q {
  let ordered = query;
  for (const { column, ascending } of AGENT_TABLES[table].order) {
    ordered = ordered.order(column, { ascending, nullsFirst: false });
  }
  return ordered;
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

/**
 * Match one or more trials by whichever key the table actually uses.
 *
 * Taking a list is what makes a trial-set enrichment pass expressible: find the
 * 53 Phase 3 trials in `clinical_trials`, then ask `trial_landscape` for those
 * 53 rows. One NCT at a time, that pass costs one model round trip per trial
 * and runs out of steps; unexpressible, it costs a whole-table read.
 *
 * `.in()` on a `text[]` column compares whole arrays rather than testing
 * membership, so the array-keyed table (`news_feed.nct_ids`) needs `overlaps` -
 * the many-valued form of the `contains` used for cancer scope.
 */
export function applyTrialKeys<Q extends FilterableQuery<Q>>(
  query: Q,
  table: AgentTable,
  nctIds: readonly string[],
): Q {
  const key = AGENT_TABLES[table].trialKey;
  if (!key) return query;
  if (key.kind === 'array') return query.overlaps(key.column, nctIds);
  return nctIds.length === 1 ? query.eq(key.column, nctIds[0]) : query.in(key.column, nctIds);
}

export type FilterName = 'sponsor' | 'phase' | 'status' | 'drug' | 'funding' | 'biomarker';

/** The two halves the product - and the Efficacy Hub's chip - divides sponsors into. */
export const FUNDING_VALUES = ['industry', 'non-industry'] as const;
export type FundingValue = (typeof FUNDING_VALUES)[number];

/** The one `lead_sponsor_class` value that counts as industry; everything else is not. */
const INDUSTRY_CLASS = 'INDUSTRY';

/**
 * Apply one named filter, or return null if this table does not support it -
 * `phase` and `status` exist only on `clinical_trials`, `drug` means a
 * different column on every table that has one. The caller turns null into a
 * structured refusal rather than a silently unfiltered query.
 *
 * `exact` filters take a list, because "active trials" is three separate
 * `overall_status` enum values and asking for them one query at a time makes
 * the row cap bite three times over. The other kinds stay single-valued:
 * `.in()` on a `text[]` column compares whole arrays, not membership.
 */
export function applyNamedFilter<Q extends FilterableQuery<Q>>(
  query: Q,
  table: AgentTable,
  name: FilterName,
  value: string | readonly string[],
): Q | null {
  const direct = AGENT_TABLES[table].filters[name];
  const viaColumn = AGENT_TABLES[table].via?.filters[name];
  // `via` filters live on the joined `clinical_trials` row, so the dotted path
  // is what PostgREST needs to filter on the embed rather than this table.
  const spec = direct ?? (viaColumn && { column: `clinical_trials.${viaColumn.column}`, kind: viaColumn.kind });
  if (!spec) return null;
  if (spec.kind === 'exact') {
    const values = typeof value === 'string' ? [value] : value;
    return values.length === 1 ? query.eq(spec.column, values[0]) : query.in(spec.column, values);
  }
  const single = typeof value === 'string' ? value : value[0];
  // `neq` rather than the hub's `or(...neq..., ...is.null)`: that null branch
  // exists for the hub's `!left` join, where null means "no joined trial row".
  // A via-filter is always `!inner`, so such a row is already gone, and the
  // column itself is never null (measured). Same partition, different join.
  if (spec.kind === 'partition') {
    return single === 'industry'
      ? query.eq(spec.column, INDUSTRY_CLASS)
      : query.neq(spec.column, INDUSTRY_CLASS);
  }
  return spec.kind === 'array'
    ? query.contains(spec.column, [single])
    : query.ilike(spec.column, `%${single}%`);
}

/** The only filters a table's `via` join can resolve - `clinical_trials` is the only via-table. */
export type ViaFilterName = Extract<FilterName, 'phase' | 'status' | 'funding'>;

/**
 * Which of the requested filters resolve through this table's `via` join.
 *
 * Excludes a name the table also holds directly: `applyNamedFilter` always
 * prefers the direct column (`direct ?? viaColumn`), so if a table ever
 * declared both, treating the name as "via" here would embed the `!inner`
 * join while the predicate actually landed on the direct column - an embed
 * with no dotted predicate to justify it, silently dropping every row with a
 * null `nct_id`. No table declares both today, but the check costs nothing.
 */
export function viaFilters(table: AgentTable, requested: readonly FilterName[]): FilterName[] {
  const { via, filters } = AGENT_TABLES[table];
  if (!via) return [];
  return requested.filter((name) => filters[name] === undefined && via.filters[name] !== undefined);
}

/**
 * The embed to append to the select string, or '' when a table has none.
 *
 * `!inner` only when a via-filter fired: an inner join drops every row with no
 * match on the joined side, and 44% of `trial_outcomes` rows have no `nct_id`
 * at all. The trial facts alone ride a left join, so those rows keep their
 * place and simply carry no facts.
 */
export function embedFor(table: AgentTable, activeVia: readonly FilterName[]): string {
  const { via, facts } = AGENT_TABLES[table];
  // Derived from the filters that actually fired, not a fixed column list: a
  // funding-only query has no business embedding `phases`, which
  // `flattenEmbeds` would lift onto every row and turn into a table column.
  const filterColumns = via
    ? activeVia
        .map((name) => via.filters[name as ViaFilterName]?.column)
        .filter((column): column is string => column !== undefined)
    : [];
  const relation = via?.table ?? facts?.embed;
  if (!relation) return '';
  const factColumns = facts?.embed === relation ? facts.columns : [];
  const columns = [...new Set([...filterColumns, ...factColumns])];
  if (columns.length === 0) return '';
  return `,${relation}${filterColumns.length > 0 ? '!inner' : ''}(${columns.join(',')})`;
}

/** Columns a caller may ask for by name, for error messages and descriptions. */
/** Which half of `trial_outcomes` a question is about. `both` narrows nothing. */
export type EndpointFamily = 'efficacy' | 'safety' | 'both';

/** The endpoints to leave out when a question is about only one family. */
const OTHER_FAMILY: Record<Exclude<EndpointFamily, 'both'>, Set<string>> = {
  efficacy: new Set(TRIAL_OUTCOMES_SAFETY),
  safety: new Set(TRIAL_OUTCOMES_EFFICACY),
};

/**
 * The columns to select for this table at the requested level of detail.
 *
 * `endpoints` drops the family the question is not about, so "what are the
 * grade 3+ rates" comes back - and renders - as adverse-event columns rather
 * than as those buried among every survival and response endpoint. Only
 * `trial_outcomes` carries either family, so it is a no-op on the other four.
 */
export function projectionFor(
  table: AgentTable,
  detail: 'concise' | 'detailed',
  endpoints: EndpointFamily = 'both',
): string {
  const spec = AGENT_TABLES[table];
  const selected = detail === 'concise' ? (spec.conciseProjection ?? spec.projection) : spec.projection;
  if (endpoints === 'both') return selected;
  const dropped = OTHER_FAMILY[endpoints];
  return selected
    .split(',')
    .map((column) => column.trim())
    .filter((column) => !dropped.has(column))
    .join(', ');
}

export function projectionColumns(table: AgentTable): string[] {
  return AGENT_TABLES[table].projection.split(',').map((c) => c.trim());
}

/**
 * Every filter name a table answers, whether the column lives on the table
 * itself or is resolved through its `via` join. A refusal that reported only
 * the direct names would hide `phase`/`status` on a via-enabled table and
 * point the caller at the NCT handoff those joins exist to replace.
 */
export function supportedFilters(table: AgentTable): FilterName[] {
  const { filters, via } = AGENT_TABLES[table];
  const direct = Object.keys(filters) as FilterName[];
  if (!via) return direct;
  const viaNames = (Object.keys(via.filters) as FilterName[]).filter((name) => !direct.includes(name));
  return [...direct, ...viaNames];
}

/**
 * Build the tool description from the map, so it can never again advertise
 * filters or tables that do not exist.
 */
export function describeTables(): string {
  return AGENT_TABLE_NAMES.map((name) => {
    const spec = AGENT_TABLES[name];
    const direct = Object.keys(spec.filters).join(', ');
    const viaNames = spec.via ? Object.keys(spec.via.filters).join(', ') : '';
    const via = viaNames ? `${viaNames} via ${spec.via!.table}` : '';
    const filterText =
      direct && via
        ? `filters: ${direct} (${via})`
        : direct || via
          ? `filters: ${direct || via}`
          : 'no extra filters';
    const trialText = spec.trialKey ? `trial key: ${spec.trialKey.column}` : 'no trial key';
    return `- \`${name}\`: ${spec.summary} (${trialText}; ${filterText})`;
  }).join('\n');
}
