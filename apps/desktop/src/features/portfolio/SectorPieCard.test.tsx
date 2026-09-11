import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedDashboardFixture } from '../../test/portfolioFixtures'
import type { DashboardAnalysis } from './types'
import { composeExposureView } from './portfolioAnalysisAdapter'
import { SectorPieCard } from './SectorPieCard'

// 2026-09-12-combine-sector-benchmark-card (test lane, order 02): SectorPieCard
// now renders as a `role="group"` sub-section inside DashboardPanel's combined
// `dashboard-composition-card`, not its own top-level `<section
// className="summary-card">`. These tests exercise the component directly
// (rather than only through DashboardPanel.test.tsx) so the group role,
// content and unavailable-state contract are pinned independently of the
// surrounding card.

const mockExposureView = composeExposureView(createExposureEngineFixture(), createDiagnosticsEngineFixture())

afterEach(cleanup)

describe('SectorPieCard', () => {
  it('renders as an accessible group named "Sector Composition"', () => {
    render(<SectorPieCard result={null} exposureResult={mockExposureView} />)

    const group = screen.getByRole('group', { name: 'Sector Composition' })
    expect(group).toBeTruthy()
  })

  it('shows sector weights from exposureResult.overview.sector_allocation in the legend', () => {
    render(<SectorPieCard result={null} exposureResult={mockExposureView} />)

    const group = screen.getByRole('group', { name: 'Sector Composition' })
    const legend = within(group).getByLabelText('Sector weights')
    expect(within(legend).getByText('Technology')).toBeTruthy()
    expect(within(legend).getByText('Financials')).toBeTruthy()
    expect(within(legend).getByText('36.0%')).toBeTruthy()
    expect(within(legend).getByText('24.0%')).toBeTruthy()
  })

  it('falls back to the dashboard result sector_allocation when no exposureResult is available', () => {
    const dashboardResult = createImportedDashboardFixture() as unknown as DashboardAnalysis

    render(<SectorPieCard result={dashboardResult} exposureResult={null} />)

    const group = screen.getByRole('group', { name: 'Sector Composition' })
    const legend = within(group).getByLabelText('Sector weights')
    expect(within(legend).getByText('Technology')).toBeTruthy()
    expect(within(legend).getByText('36.0%')).toBeTruthy()
  })

  it('renders the unavailable state as a group, not a placeholder value, when no data exists anywhere', () => {
    render(<SectorPieCard result={null} exposureResult={null} />)

    const group = screen.getByRole('group', { name: 'Sector Composition' })
    expect(within(group).getByText(/Unavailable/i)).toBeTruthy()
    // No legend, no chart, no zero-filled placeholder rendered in its place.
    expect(within(group).queryByLabelText('Sector weights')).toBeNull()
  })

  it('shows holdings for the selected sector by default and updates them on legend click', () => {
    render(<SectorPieCard result={null} exposureResult={mockExposureView} />)

    const group = screen.getByRole('group', { name: 'Sector Composition' })
    // Default selection is the first sector slice (Technology).
    expect(within(group).getByText('AAPL')).toBeTruthy()
    expect(within(group).getByText('MSFT')).toBeTruthy()

    fireEvent.click(within(group).getByText('Financials'))

    // Financials breakdown in the shared fixture is JPM only.
    expect(within(group).getByText('JPM')).toBeTruthy()
  })
})
