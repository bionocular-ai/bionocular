import { describe, it, expect } from 'vitest'
import { buildManifestEntry, runKey } from './load-runs.core.mjs'

describe('runKey', () => {
  it('qualifies a run id with its cohort dir so identically-named runs stay distinct', () => {
    expect(runKey('trials_extraction_industry', 'validation')).toBe(
      'trials_extraction_industry__validation',
    )
    expect(runKey('trials_extraction_nonindustry', 'validation')).not.toBe(
      runKey('trials_extraction_industry', 'validation'),
    )
  })
})

describe('buildManifestEntry', () => {
  it('derives a cohort-qualified id, human label, and counts from metadata', () => {
    const meta = {
      run_date: '2026-07-24T08:24:58',
      total_trials: 1771, kept: 1182, fixed: 0, dropped: 63, hitl: 526, errored: 0,
    }
    const entry = buildManifestEntry(meta, 'validation-rerun-2026-07-24', 'trials_extraction_nonindustry')
    expect(entry.id).toBe('trials_extraction_nonindustry__validation-rerun-2026-07-24')
    expect(entry.label).toBe('Non-industry - validation-rerun-2026-07-24')
    expect(entry.cohort).toBe('Non-industry')
    expect(entry.run_date).toBe('2026-07-24T08:24:58')
    expect(entry.counts).toEqual({ kept: 1182, fixed: 0, dropped: 63, hitl: 526, errored: 0, total: 1771 })
  })

  it('gives two cohorts that share a run id distinct manifest ids', () => {
    const meta = { total_trials: 0 }
    const industry = buildManifestEntry(meta, 'validation', 'trials_extraction_industry')
    const nonindustry = buildManifestEntry(meta, 'validation', 'trials_extraction_nonindustry')
    expect(industry.id).not.toBe(nonindustry.id)
  })
})
