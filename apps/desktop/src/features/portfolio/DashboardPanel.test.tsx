import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture } from '../../test/portfolioFixtures'
import { DashboardPanel, normalizePerformanceSeries } from './DashboardPanel'
import { composeExposureView } from './portfolioAnalysisAdapter'

const mockExposureView = composeExposureView(createExposureEngineFixture(), createDiagnosticsEngineFixture())

afterEach(() => {
  cleanup()
})

describe('DashboardPanel', () => {
  it('renders the account overview shell and keeps removed sections absent', () => {
    render(<DashboardPanel result={null} />)

    expect(screen.getByText('Account overview').closest('article')?.className.includes('dashboard-panel')).toBe(true)
    expect(screen.queryByText('Trusted Portfolio Snapshot')).toBeNull()
    expect(screen.queryByText('Freshness And Coverage Readiness')).toBeNull()
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByText('Benchmark used')).toBeNull()
  })

  it('shows loaded file label and restored session note in the footer', () => {
    const onClear = vi.fn()

    const { rerender } = render(
      <DashboardPanel
        result={null}
        lastImportedFileNames={['IB2025.pdf']}
        restoredSession
        onClearImportedSession={onClear}
      />,
    )

    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()
    expect(screen.getByText('Restored on launch')).toBeTruthy()

    rerender(<DashboardPanel result={null} importError="Import failed: unreadable PDF" />)
    expect(screen.getByText('Import failed: unreadable PDF')).toBeTruthy()
  })

  it('renders sector donut with look-through sectors when exposure result is provided', () => {
    render(<DashboardPanel result={null} exposureResult={mockExposureView} />)

    expect(screen.getByLabelText('Sector Composition')).toBeTruthy()
    expect(screen.getByText('Look-through composition')).toBeTruthy()
    expect(screen.getByText('Technology')).toBeTruthy()
    expect(screen.getByText('Health Care')).toBeTruthy()
    // weights from fixture: Technology 0.4 → 40.0%, Health Care 0.2 → 20.0%
    expect(screen.getByText('40.0%')).toBeTruthy()
    expect(screen.getByText('20.0%')).toBeTruthy()
  })

  it('shows sector donut unavailable state when no data is available', () => {
    render(<DashboardPanel result={null} exposureResult={null} />)

    expect(screen.getByLabelText('Sector Composition')).toBeTruthy()
    expect(screen.getByText(/Unavailable/i)).toBeTruthy()
  })

  it('falls back to dashboard sector allocation when exposure look-through is unavailable', () => {
    render(
      <DashboardPanel
        result={null}
        exposureResult={{
          ...mockExposureView,
          lookthrough_sector_exposure: [],
          exposure_availability: {
            ...mockExposureView.exposure_availability!,
            lookthrough_status: 'unavailable',
          },
        }}
      />,
    )

    // Falls back to exposureResult.overview.sector_allocation from fixture
    expect(screen.getByText('Imported snapshot composition')).toBeTruthy()
    expect(screen.getByText('Technology')).toBeTruthy()
  })

  it('normalizes all-range performance from first non-zero portfolio point', () => {
    const normalized = normalizePerformanceSeries([
      { date: '2025-01-02', portfolio_value: 0, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
      { date: '2025-01-03', portfolio_value: 0, benchmark_price: 101, portfolio_return_pct: 0, benchmark_return_pct: 1 },
      { date: '2025-06-30', portfolio_value: 3139.15, benchmark_price: 110, portfolio_return_pct: 0, benchmark_return_pct: 10 },
      { date: '2026-04-10', portfolio_value: 64687.71, benchmark_price: 116, portfolio_return_pct: 871.82, benchmark_return_pct: 16.22 },
    ])

    expect(normalized[0].portfolio_index).toBeNull()
    expect(normalized[1].portfolio_index).toBeNull()
    expect(normalized[2].portfolio_index).toBe(100)
    expect(normalized[3].portfolio_index).toBeGreaterThan(100)
    expect(normalized[2].benchmark_index).toBe(100)
  })
})
