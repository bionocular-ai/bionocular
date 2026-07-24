import { describe, it, expect } from 'vitest'
import { emptyFilter, filterTrials, filterFieldEvals } from './filters'
import type { TrialRow, FieldEvalRow } from './types'

const trials: TrialRow[] = [
  { nct: 'NCT01', decision: 'hitl', score: 0.5, isValid: true, failCount: 1, missedCount: 1, detViolationCount: 0, cancerType: ['Cutaneous Melanoma'], fields: [] },
  { nct: 'NCT02', decision: 'kept', score: 1.0, isValid: true, failCount: 0, missedCount: 0, detViolationCount: 0, cancerType: ['Uveal Melanoma'], fields: [] },
  {
    nct: 'NCT03',
    decision: 'kept',
    score: 0.95,
    isValid: true,
    failCount: 0,
    missedCount: 2,
    detViolationCount: 0,
    cancerType: ['Cutaneous Melanoma'],
    fields: [
      { nct: 'NCT03', decision: 'kept', fieldName: 'stage', status: 'FAIL', extracted: 'Stage I', corrected: 'Stage II', issue: null, justification: null, evidence: null },
      { nct: 'NCT03', decision: 'kept', fieldName: 'histology', status: 'PASS', extracted: 'Melanoma', corrected: null, issue: null, justification: null, evidence: null },
    ],
  },
]

const fields: FieldEvalRow[] = [
  { nct: 'NCT01', decision: 'hitl', fieldName: 'stage', status: 'FAIL', extracted: 'Stage II', corrected: 'Stage III', issue: null, justification: null, evidence: null },
  { nct: 'NCT02', decision: 'kept', fieldName: 'stage', status: 'PASS', extracted: 'Stage IV', corrected: null, issue: null, justification: null, evidence: null },
]

describe('filterTrials', () => {
  it('returns all rows for the empty filter', () => {
    expect(filterTrials(trials, emptyFilter())).toHaveLength(3)
  })
  it('filters by decision', () => {
    const f = { ...emptyFilter(), decisions: new Set(['hitl' as const]) }
    expect(filterTrials(trials, f).map((t) => t.nct)).toEqual(['NCT01'])
  })
  it('filters by score range and hasFail', () => {
    const f = { ...emptyFilter(), scoreMax: 0.9, hasFail: true }
    expect(filterTrials(trials, f).map((t) => t.nct)).toEqual(['NCT01'])
  })
  it('filters by cancerType and NCT search', () => {
    expect(filterTrials(trials, { ...emptyFilter(), cancerType: 'Uveal Melanoma' }).map((t) => t.nct)).toEqual(['NCT02'])
    expect(filterTrials(trials, { ...emptyFilter(), search: 'nct01' }).map((t) => t.nct)).toEqual(['NCT01'])
  })
  it('filters by fieldName + status FAIL', () => {
    const f = { ...emptyFilter(), fieldName: 'stage', status: 'FAIL' as const }
    expect(filterTrials(trials, f).map((t) => t.nct)).toEqual(['NCT03'])
  })
  it('filters by fieldName with any status', () => {
    const f = { ...emptyFilter(), fieldName: 'stage', status: null }
    expect(filterTrials(trials, f).map((t) => t.nct)).toEqual(['NCT03'])
  })
  it('filters by hasMissed', () => {
    const f = { ...emptyFilter(), hasMissed: true }
    expect(filterTrials(trials, f).map((t) => t.nct)).toEqual(['NCT01', 'NCT03'])
  })
})

describe('filterFieldEvals', () => {
  it('filters by fieldName + status', () => {
    const f = { ...emptyFilter(), fieldName: 'stage', status: 'FAIL' as const }
    expect(filterFieldEvals(fields, f).map((r) => r.nct)).toEqual(['NCT01'])
  })
  it('filters by parent decision', () => {
    const f = { ...emptyFilter(), decisions: new Set(['kept' as const]) }
    expect(filterFieldEvals(fields, f).map((r) => r.nct)).toEqual(['NCT02'])
  })
})
