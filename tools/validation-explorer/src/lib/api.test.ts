import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchRun } from './api'

const validation = {
  metadata: { total_trials: 1 },
  trials: [{
    nct_number: 'NCT01', decision: 'kept', validation_score: 1, is_valid: true,
    deterministic_violations: [], applied_corrections: [],
    verdict: { is_valid: true, validation_score: 1, missed_values: [], field_evaluations: [] },
  }],
}
const results = { metadata: {}, trials: [{ nct_number: 'NCT01', cancer_type: ['Cutaneous Melanoma'] }] }

describe('fetchRun', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
      ok: true,
      json: async () => (url.includes('results.json') ? results : validation),
    })))
  })
  it('fetches, joins, and normalizes a run', async () => {
    const run = await fetchRun('run-x')
    expect(run.trials).toHaveLength(1)
    expect(run.trials[0].cancerType).toEqual(['Cutaneous Melanoma'])
  })
  it('tolerates a missing results.json (cancerType empty)', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => ({
      ok: !url.includes('results.json'),
      json: async () => validation,
    })))
    const run = await fetchRun('run-x')
    expect(run.trials[0].cancerType).toEqual([])
  })
})
