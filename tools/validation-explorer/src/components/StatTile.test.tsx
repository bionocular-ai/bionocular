import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { StatTile } from './StatTile'

describe('StatTile', () => {
  it('renders the label and value', () => {
    render(<StatTile label="kept" value={42} />)
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.getByText('kept')).toBeInTheDocument()
  })

  it('renders an accent dot when accentClassName is given', () => {
    const { container } = render(<StatTile label="error" value={3} accentClassName="bg-rose-600" />)
    expect(container.querySelector('.bg-rose-600')).toBeInTheDocument()
  })
})
