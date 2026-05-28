import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { LoadingState } from './LoadingState'

afterEach(() => { cleanup() })

describe('LoadingState', () => {
  it('renders_default_message_when_message_omitted', () => {
    render(<LoadingState />)
    expect(screen.getByText('Loading…')).toBeTruthy()
  })

  it('renders_custom_message', () => {
    render(<LoadingState message="Computing correlation…" />)
    expect(screen.getByText('Computing correlation…')).toBeTruthy()
  })
})
