// Cohort dir name -> human label. Extend as new cohorts appear.
const COHORT_LABELS = {
  trials_extraction_nonindustry: 'Non-industry',
  trials_extraction_industry: 'Industry',
}

export function cohortLabel(cohortDir) {
  return COHORT_LABELS[cohortDir] ?? cohortDir
}

// Cohort-qualified run id. Two cohorts can each hold a subdir named
// `validation`; keying only on the subdir name collides, so both the copied
// output dir and the manifest id must fold in the cohort dir.
export function runKey(cohortDir, runId) {
  return `${cohortDir}__${runId}`
}

export function buildManifestEntry(validationMeta, runId, cohortDir) {
  return {
    id: runKey(cohortDir, runId),
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
