import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { TrustBadge } from './TrustBadge'

afterEach(() => { cleanup() })

describe('TrustBadge', () => {
  it('renders_synthetic_label', () => {
    render(<TrustBadge type="synthetic" />)
    expect(screen.getByText('Synthetic')).toBeTruthy()
  })

  it('renders_unavailable_label', () => {
    render(<TrustBadge type="unavailable" />)
    expect(screen.getByText('Unavailable')).toBeTruthy()
  })

  it('applies_tooltip_when_provided', () => {
    render(<TrustBadge type="synthetic" tooltip="Computed from current holdings." />)
    const el = screen.getByText('Synthetic')
    expect(el.getAttribute('title')).toBe('Computed from current holdings.')
  })

  it('uses_canonical_class', () => {
    render(<TrustBadge type="synthetic" />)
    const el = screen.getByText('Synthetic')
    expect(el.className).toBe('attribution-trust-badge')
  })
})
