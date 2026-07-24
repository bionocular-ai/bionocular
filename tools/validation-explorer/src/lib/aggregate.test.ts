import { describe, it, expect } from 'vitest'
import { decisionBreakdown, failRateByField, scoreHistogram, missedValuesCount } from './aggregate'
import type { TrialRow, FieldEvalRow } from './types'

const trials: TrialRow[] = [
  { nct: 'A', decision: 'hitl', score: 0.5, isValid: true, failCount: 1, missedCount: 1, detViolationCount: 0, cancerType: [], fields: [] },
  { nct: 'B', decision: 'kept', score: 1.0, isValid: true, failCount: 0, missedCount: 0, detViolationCount: 0, cancerType: [], fields: [] },
  { nct: 'C', decision: 'kept', score: 0.95, isValid: true, failCount: 0, missedCount: 0, detViolationCount: 0, cancerType: [], fields: [] },
]

const fields: FieldEvalRow[] = [
  { nct: 'A', decision: 'hitl', fieldName: 'stage', status: 'FAIL', extracted: null, corrected: null, issue: null, justification: null, evidence: null },
  { nct: 'B', decision: 'kept', fieldName: 'stage', status: 'PASS', extracted: null, corrected: null, issue: null, justification: null, evidence: null },
  { nct: 'C', decision: 'kept', fieldName: 'modality', status: 'PASS', extracted: null, corrected: null, issue: null, justification: null, evidence: null },
]

describe('aggregations', () => {
  it('decisionBreakdown counts by decision', () => {
    const b = decisionBreakdown(trials)
    expect(b.find((x) => x.decision === 'kept')!.count).toBe(2)
    expect(b.find((x) => x.decision === 'hitl')!.count).toBe(1)
  })
  it('failRateByField computes rate sorted desc', () => {
    const r = failRateByField(fields)
    expect(r[0]).toEqual({ field: 'stage', fail: 1, total: 2, rate: 0.5 })
    expect(r.find((x) => x.field === 'modality')!.rate).toBe(0)
  })
  it('scoreHistogram buckets scores into bins', () => {
    const h = scoreHistogram(trials, 2)
    expect(h).toHaveLength(2)
    expect(h[0].count).toBe(1) // 0.5 in [0,0.5)
    expect(h[1].count).toBe(2) // 0.95, 1.0 in [0.5,1]
  })
  it('missedValuesCount counts trials with missed values', () => {
    expect(missedValuesCount(trials)).toBe(1)
  })
})
