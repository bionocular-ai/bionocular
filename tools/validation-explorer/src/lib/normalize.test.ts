import { describe, it, expect } from 'vitest'
import { normalizeRun } from './normalize'
import type { RawValidation, RawResults } from './types'

const validation: RawValidation = {
  metadata: { total_trials: 2, kept: 1, hitl: 1, dropped: 0, fixed: 0, errored: 0 },
  trials: [
    {
      nct_number: 'NCT01', decision: 'hitl', validation_score: 0.5, is_valid: true,
      deterministic_violations: [], applied_corrections: [],
      verdict: {
        is_valid: true, validation_score: 0.5, missed_values: ['x'],
        field_evaluations: [
          { field_name: 'stage', status: 'FAIL', extracted_value: 'Stage II',
            corrected_value: 'Stage III', issue_description: 'wrong',
            mapping_justification: 'because', source_evidence_quote: 'quote' },
          { field_name: 'modality', status: 'PASS', extracted_value: 'Vaccine',
            corrected_value: null, issue_description: null,
            mapping_justification: 'ok', source_evidence_quote: null },
        ],
      },
    },
    {
      nct_number: 'NCT02', decision: 'dropped', validation_score: 0.0, is_valid: false,
      deterministic_violations: ['empty treatment_name'], applied_corrections: [],
      verdict: null,
    },
  ],
}

const results: RawResults = {
  metadata: {},
  trials: [
    { nct_number: 'NCT01', cancer_type: ['Cutaneous Melanoma'] },
    { nct_number: 'NCT02', cancer_type: ['Uveal Melanoma'] },
  ],
}

describe('normalizeRun', () => {
  it('builds trial rows with derived counts and joined cancer_type', () => {
    const run = normalizeRun(validation, results)
    const t1 = run.trials.find((t) => t.nct === 'NCT01')!
    expect(t1.failCount).toBe(1)
    expect(t1.missedCount).toBe(1)
    expect(t1.cancerType).toEqual(['Cutaneous Melanoma'])
    expect(t1.fields).toHaveLength(2)
  })

  it('treats verdict:null (dropped) as zero field evals', () => {
    const run = normalizeRun(validation, results)
    const t2 = run.trials.find((t) => t.nct === 'NCT02')!
    expect(t2.failCount).toBe(0)
    expect(t2.fields).toHaveLength(0)
    expect(t2.detViolationCount).toBe(1)
  })

  it('flattens all field evals with parent nct + decision', () => {
    const run = normalizeRun(validation, results)
    expect(run.fieldEvals).toHaveLength(2)
    const fail = run.fieldEvals.find((f) => f.status === 'FAIL')!
    expect(fail.nct).toBe('NCT01')
    expect(fail.decision).toBe('hitl')
    expect(fail.corrected).toBe('Stage III')
  })

  it('defaults cancer_type to empty array when results is null', () => {
    const run = normalizeRun(validation, null)
    expect(run.trials[0].cancerType).toEqual([])
  })
})
