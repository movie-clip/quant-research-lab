import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { createDiagnosticsFixture } from '../../test/portfolioFixtures'
import { TrendRiskOverlaysPanel } from './TrendRiskOverlaysPanel'

afterEach(() => {
  cleanup()
})

describe('TrendRiskOverlaysPanel', () => {
  it('renders top-line regime, component states, explanation drivers, and recent context', () => {
    const result = createDiagnosticsFixture()

    render(<TrendRiskOverlaysPanel result={result} />)

    expect(screen.getByTestId('trend-risk-overlays-panel')).toBeTruthy()
    expect(screen.getByText('Overlay analysis')).toBeTruthy()
    expect(screen.getByText('Top-Line Regime')).toBeTruthy()
    expect(screen.getByText('Component Status')).toBeTruthy()
    expect(screen.getByText('Explanation Drivers')).toBeTruthy()
    expect(screen.getByText('Recent Context')).toBeTruthy()
    expect(screen.getByText('Metadata & Caveats')).toBeTruthy()
    expect(screen.getByText('Status Live')).toBeTruthy()
    expect(screen.getAllByText('Regime normal').length).toBeGreaterThan(0)
  })

  it('shows explicit unavailable state messaging when historical diagnostics are missing', () => {
    const result = {
      ...createDiagnosticsFixture(),
      availability: {
        historical_sections_available: false,
        history_context_required: true,
        note: 'Overlay analysis requires imported history context.',
      },
    }

    render(<TrendRiskOverlaysPanel result={result} />)

    expect(screen.getByText('Status Unavailable')).toBeTruthy()
    expect(screen.getByText('Overlay analysis requires imported history context.')).toBeTruthy()
    expect(screen.getByText('Recent overlay history is unavailable.')).toBeTruthy()
  })

  it('shows waiting state without diagnostics input', () => {
    render(<TrendRiskOverlaysPanel result={null} />)

    expect(screen.getByText('Overlay diagnostics are waiting for a portfolio.')).toBeTruthy()
    expect(screen.getByText('Import a portfolio from the Dashboard to inspect trend and risk overlays.')).toBeTruthy()
  })
})
