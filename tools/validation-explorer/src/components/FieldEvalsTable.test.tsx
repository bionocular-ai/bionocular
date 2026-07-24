import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { FieldEvalsTable } from './FieldEvalsTable'
import type { FieldEvalRow } from '@/lib/types'

// @tanstack/react-virtual measures the scroll element's size (offsetHeight)
// to decide which rows are "in view" and only mounts those into the DOM. In
// jsdom every element reports zero height by default, so getVirtualItems()
// would return an empty range and a naive "row renders" assertion would
// fail (or worse, pass/fail flakily depending on layout timing). Stub
// offsetHeight/offsetWidth on the element prototype to a realistic viewport
// size so the virtualizer computes a non-empty visible range.
beforeAll(() => {
  Object.defineProperty(HTMLElement.prototype, 'offsetHeight', { configurable: true, value: 800 })
  Object.defineProperty(HTMLElement.prototype, 'offsetWidth', { configurable: true, value: 1000 })
})

const rows: FieldEvalRow[] = [
  { nct: 'NCT01', decision: 'hitl', fieldName: 'stage', status: 'FAIL', extracted: 'Stage II', corrected: 'Stage III', issue: null, justification: null, evidence: null },
]

describe('FieldEvalsTable', () => {
  it('renders a field-eval row', () => {
    render(<FieldEvalsTable rows={rows} />)
    expect(screen.getByText('NCT01')).toBeInTheDocument()
    expect(screen.getByText('stage')).toBeInTheDocument()
    expect(screen.getByText('FAIL')).toBeInTheDocument()
  })
  it('shows empty state when no rows', () => {
    render(<FieldEvalsTable rows={[]} />)
    expect(screen.getByText(/No field evaluations match/)).toBeInTheDocument()
  })
})
