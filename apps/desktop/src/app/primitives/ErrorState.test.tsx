import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { ErrorState } from './ErrorState'

afterEach(() => { cleanup() })

describe('ErrorState', () => {
  it('renders_default_title', () => {
    render(<ErrorState />)
    expect(screen.getByText('Error')).toBeTruthy()
  })

  it('renders_custom_title', () => {
    render(<ErrorState title="Whoops" />)
    expect(screen.getByText('Whoops')).toBeTruthy()
  })

  it('renders_detail_when_provided', () => {
    render(<ErrorState title="Failed" detail="Backend returned 500." />)
    expect(screen.getByText('Backend returned 500.')).toBeTruthy()
  })
})
