import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Dashboard } from './Dashboard'
import type { TrialRow } from '@/lib/types'

// recharts' ResponsiveContainer needs ResizeObserver, which jsdom doesn't implement.
// A no-op stub is enough to let it mount (it renders at zero size, which is fine -
// this test only checks that the component renders without throwing).
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
const globalWithResizeObserver = globalThis as typeof globalThis & { ResizeObserver?: typeof ResizeObserverStub }
globalWithResizeObserver.ResizeObserver ??= ResizeObserverStub

const trials: TrialRow[] = [
  {
    nct: 'NCT01',
    decision: 'hitl',
    score: 0.5,
    isValid: true,
    failCount: 1,
    missedCount: 1,
    detViolationCount: 0,
    cancerType: [],
    fields: [
      { nct: 'NCT01', decision: 'hitl', fieldName: 'stage', status: 'FAIL', extracted: null, corrected: null, issue: null, justification: null, evidence: null },
    ],
  },
  {
    nct: 'NCT02',
    decision: 'kept',
    score: 1.0,
    isValid: true,
    failCount: 0,
    missedCount: 0,
    detViolationCount: 0,
    cancerType: [],
    fields: [
      { nct: 'NCT02', decision: 'kept', fieldName: 'stage', status: 'PASS', extracted: null, corrected: null, issue: null, justification: null, evidence: null },
    ],
  },
]

describe('Dashboard', () => {
  it('renders stat tiles without throwing', () => {
    render(<Dashboard trials={trials} metadata={{}} />)
    expect(screen.getByText('hitl')).toBeInTheDocument()
    expect(screen.getByText('kept')).toBeInTheDocument()
    expect(screen.getByText('trials w/ missed')).toBeInTheDocument()
  })

  it('renders empty-state copy when there is no data to chart', () => {
    render(<Dashboard trials={[]} metadata={{}} />)
    expect(screen.getAllByText('No data matches the current filters.')).toHaveLength(2)
  })
})
