import type {
  NormalizedRun, RawResults, RawTrial, RawValidation, FieldEvalRow, TrialRow,
} from './types'

function fieldRows(trial: RawTrial): FieldEvalRow[] {
  const evals = trial.verdict?.field_evaluations ?? []
  return evals.map((f) => ({
    nct: trial.nct_number,
    decision: trial.decision,
    fieldName: f.field_name,
    status: f.status,
    extracted: f.extracted_value,
    corrected: f.corrected_value,
    issue: f.issue_description,
    justification: f.mapping_justification,
    evidence: f.source_evidence_quote,
  }))
}

export function normalizeRun(
  validation: RawValidation,
  results: RawResults | null,
): NormalizedRun {
  const cancerByNct = new Map<string, string[]>()
  for (const r of results?.trials ?? []) {
    cancerByNct.set(r.nct_number, r.cancer_type ?? [])
  }

  const trials: TrialRow[] = []
  const fieldEvals: FieldEvalRow[] = []

  for (const t of validation.trials) {
    const fields = fieldRows(t)
    fieldEvals.push(...fields)
    trials.push({
      nct: t.nct_number,
      decision: t.decision,
      score: t.validation_score,
      isValid: t.is_valid,
      failCount: fields.filter((f) => f.status === 'FAIL').length,
      missedCount: t.verdict?.missed_values.length ?? 0,
      detViolationCount: t.deterministic_violations.length,
      cancerType: cancerByNct.get(t.nct_number) ?? [],
      fields,
    })
  }

  return { metadata: validation.metadata, trials, fieldEvals }
}
