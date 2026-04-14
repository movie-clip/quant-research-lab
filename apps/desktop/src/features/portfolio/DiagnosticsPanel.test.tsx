import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { createDiagnosticsFixture } from '../../test/portfolioFixtures'
import { DiagnosticsPanel } from './DiagnosticsPanel'

const mockDiagnostics = createDiagnosticsFixture()

describe('DiagnosticsPanel', () => {
  it('renders professional diagnostics sections in updated order', () => {
    render(<DiagnosticsPanel result={mockDiagnostics} />)

    const labels = screen.getAllByText(/Risk Contribution|Risk Concentration|Model Reliability|Factor Change Monitor/).map((item) => item.textContent)
    expect(labels).toEqual(['Risk Contribution', 'Risk Concentration', 'Model Reliability', 'Factor Change Monitor'])
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

  it('renders empty state without analysis', () => {
    render(<DiagnosticsPanel result={null} />)

    expect(screen.getAllByText('Factor and risk diagnostics').length).toBeGreaterThan(0)
  })

  it('shows unavailable state when historical diagnostics are missing', () => {
    render(
      <DiagnosticsPanel
        result={{
          ...mockDiagnostics,
          availability: {
            historical_sections_available: false,
            history_context_required: true,
            note: 'Historical diagnostics require imported history context.',
          },
        }}
      />,
    )

    expect(screen.getByText('Historical diagnostics unavailable for this snapshot.')).toBeTruthy()
    expect(screen.getByText('Historical diagnostics require imported history context.')).toBeTruthy()
  })
})
