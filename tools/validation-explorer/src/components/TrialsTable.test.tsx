import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { TrialsTable } from './TrialsTable'
import type { TrialRow } from '@/lib/types'

const rows: TrialRow[] = [{
  nct: 'NCT01', decision: 'hitl', score: 0.5, isValid: true, failCount: 1, missedCount: 1, detViolationCount: 0,
  cancerType: ['Cutaneous Melanoma'],
  fields: [{ nct: 'NCT01', decision: 'hitl', fieldName: 'stage', status: 'FAIL', extracted: 'Stage II', corrected: 'Stage III', issue: 'wrong', justification: 'because', evidence: 'quote' }],
}]

describe('TrialsTable', () => {
  it('renders a trial row and expands to show field cards', () => {
    render(<TrialsTable rows={rows} />)
    expect(screen.getByText('NCT01')).toBeInTheDocument()
    fireEvent.click(screen.getByText('NCT01'))
    expect(screen.getByText('Stage III')).toBeInTheDocument()
    expect(screen.getByText(/because/)).toBeInTheDocument()
  })

  it('renders the empty state when there are no rows', () => {
    render(<TrialsTable rows={[]} />)
    expect(screen.getByText('No trials match the current filters.')).toBeInTheDocument()
  })
})
