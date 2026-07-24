export type Decision = 'kept' | 'fixed' | 'dropped' | 'hitl' | 'error'
export type FieldStatus = 'PASS' | 'FAIL'

export interface RawFieldEvaluation {
  field_name: string
  status: FieldStatus
  extracted_value: string | null
  corrected_value: string | null
  issue_description: string | null
  mapping_justification: string | null
  source_evidence_quote: string | null
}

export interface RawVerdict {
  is_valid: boolean
  validation_score: number
  missed_values: string[]
  field_evaluations: RawFieldEvaluation[]
}

export interface RawTrial {
  nct_number: string
  decision: Decision
  validation_score: number | null
  is_valid: boolean
  deterministic_violations: string[]
  applied_corrections: unknown[]
  verdict: RawVerdict | null
  error_message?: string | null
}

export interface RawValidation {
  metadata: Record<string, unknown>
  trials: RawTrial[]
}

export interface RawResultTrial {
  nct_number: string
  cancer_type?: string[]
}

export interface RawResults {
  metadata: Record<string, unknown>
  trials: RawResultTrial[]
}

export interface FieldEvalRow {
  nct: string
  decision: Decision
  fieldName: string
  status: FieldStatus
  extracted: string | null
  corrected: string | null
  issue: string | null
  justification: string | null
  evidence: string | null
}

export interface TrialRow {
  nct: string
  decision: Decision
  score: number | null
  isValid: boolean
  failCount: number
  missedCount: number
  detViolationCount: number
  cancerType: string[]
  fields: FieldEvalRow[]
}

export interface NormalizedRun {
  metadata: Record<string, unknown>
  trials: TrialRow[]
  fieldEvals: FieldEvalRow[]
}
