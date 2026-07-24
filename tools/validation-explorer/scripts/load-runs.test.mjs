import { describe, it, expect } from 'vitest'
import { buildManifestEntry } from './load-runs.core.mjs'

describe('buildManifestEntry', () => {
  it('derives id, cohort label, and counts from metadata', () => {
    const meta = {
      run_date: '2026-07-24T08:24:58',
      total_trials: 1771, kept: 1182, fixed: 0, dropped: 63, hitl: 526, errored: 0,
    }
    const entry = buildManifestEntry(meta, 'validation-rerun-2026-07-24', 'trials_extraction_nonindustry')
    expect(entry.id).toBe('validation-rerun-2026-07-24')
    expect(entry.cohort).toBe('Non-industry')
    expect(entry.run_date).toBe('2026-07-24T08:24:58')
    expect(entry.counts).toEqual({ kept: 1182, fixed: 0, dropped: 63, hitl: 526, errored: 0, total: 1771 })
  })
})
