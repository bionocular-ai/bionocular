import { normalizeRun } from './normalize'
import type { NormalizedRun, RawResults, RawValidation } from './types'

export interface ManifestEntry {
  id: string
  label: string
  cohort: string
  run_date: string | null
  counts: { kept: number; fixed: number; dropped: number; hitl: number; errored: number; total: number }
}

export async function fetchRuns(): Promise<ManifestEntry[]> {
  const res = await fetch('/runs.json')
  if (!res.ok) throw new Error('no-manifest')
  return res.json()
}

export async function fetchRun(id: string): Promise<NormalizedRun> {
  const vRes = await fetch(`/runs/${id}/validation.json`)
  if (!vRes.ok) throw new Error(`Failed to load validation.json for ${id}`)
  const validation: RawValidation = await vRes.json()

  // results.json is optional (cancer_type enrichment only) - a transport
  // failure (rejected fetch) must degrade the same way a non-ok response
  // does, not force the whole run into the error state.
  let results: RawResults | null = null
  try {
    const rRes = await fetch(`/runs/${id}/results.json`)
    if (rRes.ok) results = await rRes.json()
  } catch {
    results = null
  }

  return normalizeRun(validation, results)
}
