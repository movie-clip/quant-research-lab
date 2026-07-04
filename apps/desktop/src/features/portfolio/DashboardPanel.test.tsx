import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDashboardHistoryRunMetadataFixture, createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedDashboardFixture } from '../../test/portfolioFixtures'
import type { DashboardAnalysis } from './types'
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

  it('renders sector pie with direct portfolio composition when exposure result is provided', () => {
    render(<DashboardPanel result={null} exposureResult={mockExposureView} />)

    const pieCard = screen.getByLabelText('Sector Composition')
    expect(pieCard).toBeTruthy()
    // legend contains both sectors (Technology appears in legend + holdings header, use legend scope)
    const legend = within(pieCard).getByLabelText('Sector weights')
    expect(within(legend).getByText('Technology')).toBeTruthy()
    expect(within(legend).getByText('Financials')).toBeTruthy()
    // weights from fixture overview.sector_allocation: Technology 0.36 → 36.0%, Financials 0.24 → 24.0%
    expect(within(legend).getByText('36.0%')).toBeTruthy()
    expect(within(legend).getByText('24.0%')).toBeTruthy()
  })

  it('shows sector pie unavailable state when no data is available', () => {
    render(<DashboardPanel result={null} exposureResult={null} />)

    expect(screen.getByLabelText('Sector Composition')).toBeTruthy()
    expect(screen.getAllByText(/Unavailable/i).length).toBeGreaterThan(0)
  })

  it('uses overview.sector_allocation regardless of look-through status', () => {
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

    // Always uses direct ETF-level allocation from overview.sector_allocation
    const pieCard = screen.getByLabelText('Sector Composition')
    expect(within(within(pieCard).getByLabelText('Sector weights')).getByText('Technology')).toBeTruthy()
  })

  it('renders benchmark positioning card with summary metrics and compact active rows', () => {
    render(<DashboardPanel result={null} exposureResult={mockExposureView} />)

    expect(screen.getByLabelText('Benchmark Positioning')).toBeTruthy()
    // Summary metrics present
    expect(screen.getByText('In benchmark')).toBeTruthy()
    expect(screen.getByText('Active share')).toBeTruthy()
    // Compact active weight format — fixture top overweight: AAPL +17%
    const bmCard = screen.getByLabelText('Benchmark Positioning')
    expect(within(bmCard).getByText('AAPL')).toBeTruthy()
    expect(within(bmCard).getByText('+17.0%')).toBeTruthy()
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
  })

  it('shows degraded coverage note when benchmark holdings support is degraded', () => {
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

  // ─── US-25.1: Performance & Benchmark card ──────────────────────────────────

  it('renders the performance chart and summary strip when range_metrics/performance_series are present', () => {
    const result = createImportedDashboardFixture() as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    expect(screen.getByText('Performance & Benchmark')).toBeTruthy()
    expect(screen.getByRole('img', { name: 'Indexed portfolio return vs benchmark' })).toBeTruthy()
    expect(screen.getByText('Time-Weighted Return')).toBeTruthy()
    expect(screen.getByText('20.00%')).toBeTruthy() // time_weighted_return_pct
    expect(screen.getByText('9.52%')).toBeTruthy() // money_weighted_return_pct
  })

  it('renders n/a for a null summary field', () => {
    const fixture = createImportedDashboardFixture()
    const result = {
      ...fixture,
      range_metrics: {
        ...fixture.range_metrics,
        '1M': {
          ...fixture.range_metrics!['1M'],
          summary: { ...fixture.range_metrics!['1M'].summary, money_weighted_return_pct: null },
        },
      },
    } as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    const moneyWeightedLabel = screen.getByText('Money-Weighted Return')
    const metricRow = moneyWeightedLabel.closest('.benchmark-card-metric')
    expect(metricRow ? within(metricRow as HTMLElement).getByText('n/a') : null).toBeTruthy()
  })

  it('renders a single EmptyState when range_metrics is absent', () => {
    const fixture = createImportedDashboardFixture()
    const result = { ...fixture, range_metrics: null } as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    expect(screen.getByText('Performance unavailable')).toBeTruthy()
    expect(screen.queryByText('Time-Weighted Return')).toBeNull()
  })

  it('shows the return-basis label reflecting the run-metadata contract', () => {
    const fixture = createImportedDashboardFixture()
    const result = {
      ...fixture,
      run_metadata: {
        ...createDashboardHistoryRunMetadataFixture(),
        return_basis_contract: { portfolio_path: 'verified_total_return', benchmark_path: 'unverified_adjusted_proxy' },
      },
    } as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    expect(screen.getByText('Portfolio: Verified · SPY: Unverified proxy')).toBeTruthy()
  })

  it('switches the summary strip when the range selector changes without any network fetch', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
    const result = createImportedDashboardFixture() as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    expect(screen.getByText('20.00%')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '3M window' }))
    // Fixture uses identical values across ranges; assert selector is now active and no fetch occurred.
    expect(screen.getByRole('button', { name: '3M window' }).getAttribute('aria-pressed')).toBe('true')
    expect(fetchSpy).not.toHaveBeenCalled()
    fetchSpy.mockRestore()
  })

  it('still shows the allowlisted TWR/MWR scalars and omits max_drawdown_pct when investor economics is withheld', () => {
    const fixture = createImportedDashboardFixture()
    const result = fixture as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    // run_metadata.investor_economics_status is 'withheld' by default in the fixture.
    expect(result.run_metadata?.investor_economics_status.status).toBe('withheld')
    expect(screen.getByText('Time-Weighted Return')).toBeTruthy()
    expect(screen.getByText('20.00%')).toBeTruthy()
    expect(screen.queryByText(/Drawdown/)).toBeNull()
  })
})
