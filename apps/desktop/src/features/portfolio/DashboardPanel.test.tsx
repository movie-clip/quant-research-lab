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

  it('renders sector pie with look-through sectors when exposure result is provided', () => {
    render(<DashboardPanel result={null} exposureResult={mockExposureView} />)

    expect(screen.getByLabelText('Sector Composition')).toBeTruthy()
    expect(screen.getByText('Look-through composition')).toBeTruthy()
    expect(screen.getByText('Technology')).toBeTruthy()
    expect(screen.getByText('Health Care')).toBeTruthy()
    // weights from fixture: Technology 0.4 → 40.0%, Health Care 0.2 → 20.0%
    expect(screen.getByText('40.0%')).toBeTruthy()
    expect(screen.getByText('20.0%')).toBeTruthy()
  })

  it('shows sector pie unavailable state when no data is available', () => {
    render(<DashboardPanel result={null} exposureResult={null} />)

    expect(screen.getByLabelText('Sector Composition')).toBeTruthy()
    expect(screen.getAllByText(/Unavailable/i).length).toBeGreaterThan(0)
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

  it('renders benchmark positioning card with trust badge and compact active rows', () => {
    render(<DashboardPanel result={null} exposureResult={mockExposureView} />)

    expect(screen.getByLabelText('Benchmark Positioning')).toBeTruthy()
    // Trust badge from fixture (verified benchmark holdings)
    expect(screen.getByText('verified')).toBeTruthy()
    // Summary metrics present
    expect(screen.getByText('In benchmark')).toBeTruthy()
    expect(screen.getByText('Active share')).toBeTruthy()
    // Compact active weight format — fixture top overweight: AAPL +17%
    expect(screen.getByText('AAPL')).toBeTruthy()
    expect(screen.getByText('+17.0%')).toBeTruthy()
  })

  it('shows benchmark positioning unavailable when benchmark overlap is unavailable', () => {
    render(
      <DashboardPanel
        result={null}
        exposureResult={{
          ...mockExposureView,
          market_overlap: {
            ...mockExposureView.market_overlap,
            active_share: null,
            portfolio_in_benchmark_weight: null,
            top_overweights: [],
            top_underweights: [],
          },
          exposure_availability: {
            ...mockExposureView.exposure_availability!,
            benchmark_overlap_status: 'unavailable',
            benchmark_overlap_confidence: 'low',
          },
        }}
      />,
    )

    expect(screen.getByText('Benchmark-relative positioning unavailable')).toBeTruthy()
    expect(screen.getByText('unavailable')).toBeTruthy()
  })

  it('shows degraded trust badge when benchmark holdings support is degraded', () => {
    render(
      <DashboardPanel
        result={null}
        exposureResult={{
          ...mockExposureView,
          run_metadata: {
            ...mockExposureView.run_metadata!,
            source_status: {
              ...mockExposureView.run_metadata!.source_status,
              benchmark_holdings: 'degraded',
            },
          },
        }}
      />,
    )

    expect(screen.getByText('degraded')).toBeTruthy()
    expect(screen.getByText(/Positioning degraded versus SPY/)).toBeTruthy()
  })

  it('orders benchmark overweights by descending active weight and suppresses invalid rows', () => {
    render(
      <DashboardPanel
        result={null}
        exposureResult={{
          ...mockExposureView,
          market_overlap: {
            ...mockExposureView.market_overlap,
            top_overweights: [
              { symbol: 'MSFT', name: 'Microsoft', portfolio_weight: 0.18, benchmark_weight: 0.06, active_weight: 0.12 },
              { symbol: 'AAPL', name: 'Apple', portfolio_weight: 0.24, benchmark_weight: 0.07, active_weight: 0.17 },
              { symbol: 'NVDA', name: 'NVIDIA', portfolio_weight: null as unknown as number, benchmark_weight: 0.05, active_weight: 0.11 },
            ],
            top_underweights: [],
          },
        }}
      />,
    )

    const activeLabels = screen.getAllByText(/^[+−]\d+\.\d+%$/)
    expect(activeLabels[0].textContent).toBe('+17.0%')
    expect(activeLabels[1].textContent).toBe('+12.0%')
    // Row with null portfolio_weight is suppressed
    expect(screen.queryByText('NVDA')).toBeNull()
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
