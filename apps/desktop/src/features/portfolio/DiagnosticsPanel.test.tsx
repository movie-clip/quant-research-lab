import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { createDiagnosticsFixture } from '../../test/portfolioFixtures'
import { DiagnosticsPanel } from './DiagnosticsPanel'

const mockDiagnostics = createDiagnosticsFixture()

afterEach(() => {
  cleanup()
})

describe('DiagnosticsPanel', () => {
  it('renders professional diagnostics sections in updated order', () => {
    render(<DiagnosticsPanel result={mockDiagnostics} />)

    const labels = screen.getAllByText(/Decision Readout|Risk Concentration|Model Reliability|Historical Summary|Risk Contribution|Factor Contributions|Position Contributions|Factor Change Monitor/).map((item) => item.textContent)
    expect(labels).toEqual(['Decision Readout', 'Risk Concentration', 'Model Reliability', 'Historical Summary', 'Risk Contribution', 'Factor Contributions', 'Position Contributions', 'Factor Change Monitor'])
    expect(screen.getAllByText(mockDiagnostics.provenance.note).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Review provenance and decision-grade signals before drilling into deeper factor and risk detail.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Synthetic snapshot-history').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Historical sections live').length).toBeGreaterThan(0)
    expect(screen.getByText('Top-line diagnostics surfaced directly from authoritative backend provenance and summary outputs.')).toBeTruthy()
    expect(screen.getByText('History-derived summary only; current-state holdings concentration is tracked separately.')).toBeTruthy()
    expect(screen.getAllByText('Current Drawdown').length).toBeGreaterThan(0)
    expect(screen.getAllByText('-4.20%').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Factor HHI').length).toBeGreaterThan(0)
    expect(screen.getByText('Factor Total Variance')).toBeTruthy()
    expect(screen.getByText('R-Squared')).toBeTruthy()
    expect(screen.queryByText('Largest Positive Shifts 20d')).toBeNull()
    expect(screen.queryByText('Largest Absolute Shifts 60d')).toBeNull()
  })

  it('supports diagnostics filtering and risk table sorting controls', () => {
    render(<DiagnosticsPanel result={mockDiagnostics} />)

    fireEvent.click(screen.getAllByText('Flagged only')[0])
    expect(screen.getAllByText('Market').length).toBeGreaterThan(0)

    fireEvent.click(screen.getAllByText('Variance')[0])
    fireEvent.click(screen.getAllByText('Component')[0])

    expect(screen.getAllByText('Risk Share').length).toBeGreaterThan(0)
    expect(screen.getAllByText('AAPL').length).toBeGreaterThan(0)
  })

  it('renders a six-card decision readout from existing backend values only', () => {
    render(<DiagnosticsPanel result={mockDiagnostics} />)

    const decisionReadout = screen.getByTestId('diagnostics-decision-readout')
    expect(decisionReadout).toBeTruthy()
    const section = within(decisionReadout)

    expect(section.getByText('History Basis')).toBeTruthy()
    expect(section.getByText('Historical Status')).toBeTruthy()
    expect(section.getByText('Model Confidence')).toBeTruthy()
    expect(section.getByText('Current Drawdown')).toBeTruthy()
    expect(section.getByText('Top 3 Factor Risk Share')).toBeTruthy()
    expect(section.getByText('Top 5 Position Risk Share')).toBeTruthy()
    expect(section.queryByText('Top 1 Factor Risk Share')).toBeNull()
    expect(decisionReadout.querySelectorAll('.summary-card')).toHaveLength(6)
  })

  it('keeps imported-history and synthetic-history provenance visibly distinct', () => {
    const { rerender } = render(
      <DiagnosticsPanel
        result={{
          ...mockDiagnostics,
          provenance: {
            ...mockDiagnostics.provenance,
            historical_basis: 'imported_portfolio_history',
            note: 'Historical diagnostics are sourced from imported portfolio history.',
          },
        }}
      />,
    )

    expect(screen.getAllByText('Imported portfolio history').length).toBeGreaterThan(0)
    expect(screen.queryByText('Synthetic snapshot-history')).toBeNull()

    rerender(<DiagnosticsPanel result={mockDiagnostics} />)

    expect(screen.getAllByText('Synthetic snapshot-history').length).toBeGreaterThan(0)
  })

  it('renders empty state without analysis', () => {
    render(<DiagnosticsPanel result={null} />)

    expect(screen.getAllByText('Factor and risk diagnostics').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Review provenance and decision-grade signals before drilling into deeper factor and risk detail.').length).toBeGreaterThan(0)
  })

  it('shows unavailable state when historical diagnostics are missing', () => {
    render(
      <DiagnosticsPanel
        result={{
          ...mockDiagnostics,
          provenance: {
            ...mockDiagnostics.provenance,
            historical_basis: 'unavailable',
            note: 'Historical diagnostics are unavailable because imported history context is missing.',
          },
          availability: {
            historical_sections_available: false,
            history_context_required: true,
            note: 'Historical diagnostics require imported history context.',
          },
        }}
      />,
    )

    expect(screen.getByText('Historical diagnostics unavailable for this snapshot.')).toBeTruthy()
    expect(screen.getByText('History unavailable')).toBeTruthy()
    expect(screen.getByText('Historical sections unavailable')).toBeTruthy()
    expect(screen.getByText('Historical diagnostics are unavailable because imported history context is missing.')).toBeTruthy()
    expect(screen.getByText('Historical diagnostics require imported history context.')).toBeTruthy()
    expect(screen.getByText('Historical diagnostics are not approximated when history context is missing.')).toBeTruthy()
  })
})
