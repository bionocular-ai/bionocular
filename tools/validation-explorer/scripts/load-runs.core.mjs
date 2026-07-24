// Cohort dir name -> human label. Extend as new cohorts appear.
const COHORT_LABELS = {
  trials_extraction_nonindustry: 'Non-industry',
  trials_extraction_industry: 'Industry',
}

export function cohortLabel(cohortDir) {
  return COHORT_LABELS[cohortDir] ?? cohortDir
}

export function buildManifestEntry(validationMeta, runId, cohortDir) {
  return {
    id: runId,
    label: `${cohortLabel(cohortDir)} - ${runId}`,
    cohort: cohortLabel(cohortDir),
    run_date: validationMeta.run_date ?? null,
    counts: {
      kept: validationMeta.kept ?? 0,
      fixed: validationMeta.fixed ?? 0,
      dropped: validationMeta.dropped ?? 0,
      hitl: validationMeta.hitl ?? 0,
      errored: validationMeta.errored ?? 0,
      total: validationMeta.total_trials ?? 0,
    },
  }
}
