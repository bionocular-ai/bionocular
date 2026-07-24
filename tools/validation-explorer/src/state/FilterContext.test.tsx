import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { FilterProvider, useFilter } from './FilterContext'

function Probe() {
  const { filter, setFilter, reset } = useFilter()
  return (
    <div>
      <span data-testid="has-fail">{String(filter.hasFail)}</span>
      <button onClick={() => setFilter((f) => ({ ...f, hasFail: true }))}>set</button>
      <button onClick={reset}>reset</button>
    </div>
  )
}

describe('FilterContext', () => {
  it('updates and resets filter state', () => {
    render(<FilterProvider><Probe /></FilterProvider>)
    expect(screen.getByTestId('has-fail').textContent).toBe('false')
    fireEvent.click(screen.getByText('set'))
    expect(screen.getByTestId('has-fail').textContent).toBe('true')
    fireEvent.click(screen.getByText('reset'))
    expect(screen.getByTestId('has-fail').textContent).toBe('false')
  })
})
