import type { Decision, FieldEvalRow, TrialRow } from './types'

export function decisionBreakdown(trials: TrialRow[]): { decision: Decision; count: number }[] {
  const counts = new Map<Decision, number>()
  for (const t of trials) counts.set(t.decision, (counts.get(t.decision) ?? 0) + 1)
  return [...counts.entries()].map(([decision, count]) => ({ decision, count }))
}

export function failRateByField(fieldEvals: FieldEvalRow[]): { field: string; fail: number; total: number; rate: number }[] {
  const agg = new Map<string, { fail: number; total: number }>()
  for (const f of fieldEvals) {
    const a = agg.get(f.fieldName) ?? { fail: 0, total: 0 }
    a.total += 1
    if (f.status === 'FAIL') a.fail += 1
    agg.set(f.fieldName, a)
  }
  return [...agg.entries()]
    .map(([field, a]) => ({ field, fail: a.fail, total: a.total, rate: a.total ? a.fail / a.total : 0 }))
    .sort((x, y) => y.rate - x.rate)
}

export function scoreHistogram(trials: TrialRow[], bins = 10): { bucket: string; count: number }[] {
  const counts = new Array(bins).fill(0)
  for (const t of trials) {
    if (t.score === null) continue
    const idx = Math.max(0, Math.min(bins - 1, Math.ceil(t.score * bins) - 1))
    counts[idx] += 1
  }
  return counts.map((count, i) => ({
    bucket: `${(i / bins).toFixed(1)}-${((i + 1) / bins).toFixed(1)}`,
    count,
  }))
}

export function missedValuesCount(trials: TrialRow[]): number {
  return trials.filter((t) => t.missedCount > 0).length
}
