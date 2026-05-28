import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { EmptyState } from './EmptyState'

afterEach(() => { cleanup() })

describe('EmptyState', () => {
  it('renders_title', () => {
    render(<EmptyState title="Correlation unavailable" />)
    expect(screen.getByText('Correlation unavailable')).toBeTruthy()
  })

  it('renders_detail_when_provided', () => {
    render(<EmptyState title="A" detail="Detail line." />)
    expect(screen.getByText('Detail line.')).toBeTruthy()
  })

  it('omits_detail_when_not_provided', () => {
    render(<EmptyState title="A" />)
    expect(screen.queryByText(/^.+$/, { selector: 'p.helper' })).toBeNull()
  })
})
