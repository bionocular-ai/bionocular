import type { Decision, FieldEvalRow, FieldStatus, TrialRow } from './types'

export interface FilterState {
  decisions: Set<Decision>
  scoreMin: number
  scoreMax: number
  hasFail: boolean
  hasMissed: boolean
  fieldName: string | null
  status: FieldStatus | null
  cancerType: string | null
  search: string
}

export function emptyFilter(): FilterState {
  return {
    decisions: new Set(),
    scoreMin: 0,
    scoreMax: 1,
    hasFail: false,
    hasMissed: false,
    fieldName: null,
    status: null,
    cancerType: null,
    search: '',
  }
}

export function filterTrials(rows: TrialRow[], f: FilterState): TrialRow[] {
  const q = f.search.trim().toLowerCase()
  return rows.filter((t) => {
    if (f.decisions.size > 0 && !f.decisions.has(t.decision)) return false
    if (t.score !== null && (t.score < f.scoreMin || t.score > f.scoreMax)) return false
    if (f.hasFail && t.failCount === 0) return false
    if (f.hasMissed && t.missedCount === 0) return false
    if (f.cancerType && !t.cancerType.includes(f.cancerType)) return false
    if (f.fieldName && !t.fields.some((x) => x.fieldName === f.fieldName && (!f.status || x.status === f.status))) return false
    if (q && !t.nct.toLowerCase().includes(q)) return false
    return true
  })
}

export function filterFieldEvals(rows: FieldEvalRow[], f: FilterState): FieldEvalRow[] {
  const q = f.search.trim().toLowerCase()
  return rows.filter((r) => {
    if (f.decisions.size > 0 && !f.decisions.has(r.decision)) return false
    if (f.fieldName && r.fieldName !== f.fieldName) return false
    if (f.status && r.status !== f.status) return false
    if (q && !(r.nct.toLowerCase().includes(q) ||
      (r.extracted ?? '').toLowerCase().includes(q) ||
      (r.corrected ?? '').toLowerCase().includes(q))) return false
    return true
  })
}
