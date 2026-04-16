import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { createDiagnosticsFixture } from '../../test/portfolioFixtures'
import { DiagnosticsPanel } from './DiagnosticsPanel'

const mockDiagnostics = createDiagnosticsFixture()

afterEach(() => {
  cleanup()
})

describe('DiagnosticsPanel', () => {
  it('renders the diagnostics quant shell and behavior-through-time section only', () => {
    render(<DiagnosticsPanel result={mockDiagnostics} />)

    const labels = screen.getAllByText(/Decision Readout|Behavior Through Time/).map((item) => item.textContent)
    expect(labels).toEqual(['Decision Readout', 'Behavior Through Time'])
    expect(screen.getByTestId('diagnostics-shell')).toBeTruthy()
    expect(screen.getByTestId('diagnostics-behavior-through-time')).toBeTruthy()
    expect(screen.getByText('Provenance first, then decision signals')).toBeTruthy()
    expect(screen.getAllByText(mockDiagnostics.provenance.note).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Review provenance and decision-grade signals before drilling into deeper factor and risk detail.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Snapshot request').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Synthetic snapshot-history').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Historical sections live').length).toBeGreaterThan(0)
    expect(screen.getByText('History context required')).toBeTruthy()
    expect(screen.getByText('Decision cards stay thin: every value is mapped directly from backend summary outputs.')).toBeTruthy()
    expect(screen.getByText('Backend truth stays explicit while the top shell surfaces the first diagnostics to review.')).toBeTruthy()
    expect(screen.getByText(/Temporal behavior stays primary here:/)).toBeTruthy()
    expect(screen.getByText('Risk Path')).toBeTruthy()
    expect(screen.getByText('Benchmark-Relative Behavior')).toBeTruthy()
    expect(screen.getByText('Factor Behavior')).toBeTruthy()
    expect(screen.getAllByText('Current Drawdown').length).toBeGreaterThan(0)
    expect(screen.getAllByText('-4.20%').length).toBeGreaterThan(0)
    expect(screen.queryByText('Risk Concentration')).toBeNull()
    expect(screen.queryByText('Model Reliability')).toBeNull()
    expect(screen.queryByText('Historical Summary')).toBeNull()
    expect(screen.queryByText('Risk Contribution')).toBeNull()
    expect(screen.queryByText('Factor Contributions')).toBeNull()
    expect(screen.queryByText('Position Contributions')).toBeNull()
    expect(screen.queryByText('Factor Change Monitor')).toBeNull()
  })

  it('switches behavior-through-time windows and shows honest unavailable messaging for unsupported 252d paths', () => {
    render(<DiagnosticsPanel result={mockDiagnostics} />)

    fireEvent.click(screen.getByRole('button', { name: '252d unavailable' }))

    expect(screen.getByText('Behavior-through-time charts are unavailable for 252d.')).toBeTruthy()
    expect(screen.getByText(/The backend marked this window as unavailable/)).toBeTruthy()
    expect(screen.queryByText('Risk Contribution')).toBeNull()
  })

  it('renders a six-card decision readout from existing backend values only', () => {
    render(<DiagnosticsPanel result={mockDiagnostics} />)

    const decisionReadout = screen.getByTestId('diagnostics-decision-readout')
    expect(decisionReadout).toBeTruthy()
    const section = within(decisionReadout)

    expect(section.getByText('Current Drawdown')).toBeTruthy()
    expect(section.getByText('Max Drawdown')).toBeTruthy()
    expect(section.getByText('Model Confidence')).toBeTruthy()
    expect(section.getByText('Tracking Error')).toBeTruthy()
    expect(section.getByText('Top 3 Factor Risk Share')).toBeTruthy()
    expect(section.getByText('Top 5 Position Risk Share')).toBeTruthy()
    expect(section.queryByText('Top 1 Factor Risk Share')).toBeNull()
    expect(section.getByText('Benchmark SPY')).toBeTruthy()
    expect(decisionReadout.querySelectorAll('.summary-card')).toHaveLength(6)
  })

  it('keeps imported-history and synthetic-history provenance visibly distinct', () => {
    const { rerender } = render(
      <DiagnosticsPanel
        result={{
          ...mockDiagnostics,
          provenance: {
            ...mockDiagnostics.provenance,
            snapshot_basis: 'imported_snapshot',
            historical_basis: 'imported_portfolio_history',
            note: 'Historical diagnostics are sourced from imported portfolio history.',
          },
        }}
      />,
    )

    expect(screen.getAllByText('Imported snapshot').length).toBeGreaterThan(0)
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

    expect(screen.getByTestId('diagnostics-shell')).toBeTruthy()
    expect(screen.getByText('Historical diagnostics unavailable for this snapshot.')).toBeTruthy()
    expect(screen.getAllByText('History unavailable').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Historical sections unavailable').length).toBeGreaterThan(0)
    expect(screen.getByText('Historical diagnostics are unavailable because imported history context is missing.')).toBeTruthy()
    expect(screen.getAllByText('Historical diagnostics require imported history context.').length).toBeGreaterThan(0)
    expect(screen.getByText('Historical diagnostics are not approximated when history context is missing.')).toBeTruthy()
    expect(screen.queryByTestId('diagnostics-decision-readout')).toBeNull()
    expect(screen.queryByTestId('diagnostics-behavior-through-time')).toBeNull()
  })
})
