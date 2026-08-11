import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDashboardHistoryRunMetadataFixture, createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedDashboardFixture } from '../../test/portfolioFixtures'
import type { DashboardAnalysis, DiagnosticsEngineResponse } from './types'
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

  // ─── US-25.2: Monthly Returns grid ──────────────────────────────────────────

  it('renders one cell per month with signed, 2-decimal formatting', () => {
    const fixture = createImportedDashboardFixture()
    const result = {
      ...fixture,
      range_metrics: {
        ...fixture.range_metrics,
        '1M': {
          ...fixture.range_metrics!['1M'],
          monthly_returns: [
            { month: '2025-01', return_pct: 3.456 },
            { month: '2025-02', return_pct: -1.2 },
          ],
        },
      },
    } as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    expect(screen.getByText('+3.46%')).toBeTruthy()
    expect(screen.getByText('−1.20%')).toBeTruthy()
  })

  it('hides the grid and shows an EmptyState when monthly_returns_reliable is false', () => {
    const fixture = createImportedDashboardFixture()
    const result = {
      ...fixture,
      range_metrics: {
        ...fixture.range_metrics,
        '1M': { ...fixture.range_metrics!['1M'], monthly_returns_reliable: false },
      },
    } as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    expect(screen.getByText('Monthly returns unavailable')).toBeTruthy()
    expect(screen.queryByText('2025-01')).toBeNull()
  })

  it('shows an EmptyState when range_metrics is absent', () => {
    const fixture = createImportedDashboardFixture()
    const result = { ...fixture, range_metrics: null } as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    const grid = screen.getByLabelText('Monthly Returns')
    expect(within(grid).getByText('Monthly returns unavailable')).toBeTruthy()
  })

  it('updates the grid when the shared range selector changes', () => {
    const fixture = createImportedDashboardFixture()
    const result = {
      ...fixture,
      range_metrics: {
        ...fixture.range_metrics,
        '1M': {
          ...fixture.range_metrics!['1M'],
          monthly_returns: [{ month: '2025-01', return_pct: 1 }],
        },
        '3M': {
          ...fixture.range_metrics!['3M'],
          monthly_returns: [{ month: '2025-03', return_pct: 2 }],
        },
      },
    } as unknown as DashboardAnalysis
    render(<DashboardPanel result={result} />)

    expect(screen.getByText('+1.00%')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '3M window' }))
    expect(screen.getByText('+2.00%')).toBeTruthy()
    expect(screen.queryByText('+1.00%')).toBeNull()
  })

  // ─── US-25.3: Risk Summary card ─────────────────────────────────────────────

  it('renders volatility and tracking-error fields, with n/a for null values', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.volatility_summary.benchmark_volatility_pct = null
    render(<DashboardPanel result={null} diagnosticsAnalysis={diagnostics} />)

    expect(screen.getByText('Portfolio Volatility')).toBeTruthy()
    expect(screen.getByText('18.20%')).toBeTruthy()
    expect(screen.getByText('7.20%')).toBeTruthy() // tracking error
    const benchmarkVolLabel = screen.getByText('Benchmark Volatility')
    const row = benchmarkVolLabel.closest('.benchmark-card-metric')
    expect(row ? within(row as HTMLElement).getByText('n/a') : null).toBeTruthy()
  })

  it('renders drawdown from the diagnostics path, not the withheld dashboard-history value', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.drawdown_summary.max_drawdown_pct = -8.9
    const dashboardResult = {
      ...createImportedDashboardFixture(),
      range_metrics: {
        ...createImportedDashboardFixture().range_metrics,
        '1M': { ...createImportedDashboardFixture().range_metrics!['1M'], max_drawdown_pct: null },
      },
    } as unknown as DashboardAnalysis
    render(<DashboardPanel result={dashboardResult} diagnosticsAnalysis={diagnostics} />)

    expect(screen.getByText('Max Drawdown')).toBeTruthy()
    expect(screen.getByText('-8.90%')).toBeTruthy()
  })

  it('renders HHI and risk-share fields from risk_concentration_summary', () => {
    // top_*_risk_share fields are 0-1 fractions (see _sum_top_risk_shares in
    // analytics/risk.py) — 0.425 means "42.50% of risk", not "0.43%".
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.risk_concentration_summary = {
      top_1_factor_risk_share: 0.425,
      top_3_factor_risk_share: 0.701,
      top_1_position_risk_share: 0.203,
      top_5_position_risk_share: 0.556,
      factor_hhi: 0.312,
      position_hhi: 0.145,
    }
    render(<DashboardPanel result={null} diagnosticsAnalysis={diagnostics} />)

    expect(screen.getByText('Factor HHI')).toBeTruthy()
    expect(screen.getByText('0.312')).toBeTruthy()
    expect(screen.getByText('0.145')).toBeTruthy()
    expect(screen.getByText('42.50%')).toBeTruthy()
  })

  it('trust label follows section_trust.risk_contribution_path across its three states', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.run_metadata.section_trust.risk_contribution_path = 'verified_adjusted_close'
    const { rerender } = render(<DashboardPanel result={null} diagnosticsAnalysis={diagnostics} />)
    expect(screen.getByText('Risk contribution basis: Verified')).toBeTruthy()

    const degraded = { ...diagnostics, run_metadata: { ...diagnostics.run_metadata, section_trust: { ...diagnostics.run_metadata.section_trust, risk_contribution_path: 'degraded_unverified_return_basis' as const } } }
    rerender(<DashboardPanel result={null} diagnosticsAnalysis={degraded} />)
    expect(screen.getByText('Risk contribution basis: Degraded')).toBeTruthy()

    const unavailableTrust = { ...diagnostics, run_metadata: { ...diagnostics.run_metadata, section_trust: { ...diagnostics.run_metadata.section_trust, risk_contribution_path: 'unavailable' as const } } }
    rerender(<DashboardPanel result={null} diagnosticsAnalysis={unavailableTrust} />)
    expect(screen.getByText('Risk contribution basis: Unavailable')).toBeTruthy()
  })

  it('shows a single EmptyState when diagnosticsAnalysis is absent or unavailable', () => {
    const { rerender } = render(<DashboardPanel result={null} diagnosticsAnalysis={null} />)
    expect(screen.getByText('Risk metrics unavailable')).toBeTruthy()

    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.availability.historical_sections_available = false
    rerender(<DashboardPanel result={null} diagnosticsAnalysis={diagnostics} />)
    expect(screen.getByText('Risk metrics unavailable')).toBeTruthy()
    expect(screen.queryByText('Portfolio Volatility')).toBeNull()
  })

  // ─── US-25.5: Information Ratio ─────────────────────────────────────────────

  it('renders Information Ratio and Active Return when relative_risk is populated', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.relative_risk = { ...diagnostics.relative_risk, information_ratio: 0.42, active_return_pct: 3.5 }
    render(<DashboardPanel result={null} diagnosticsAnalysis={diagnostics} />)

    expect(screen.getByText('Information Ratio')).toBeTruthy()
    expect(screen.getByText('0.420')).toBeTruthy()
    expect(screen.getByText('Active Return (vs benchmark)')).toBeTruthy()
    expect(screen.getByText('3.50%')).toBeTruthy()
  })

  it('renders n/a for Information Ratio and Active Return when each is individually null', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.relative_risk = { ...diagnostics.relative_risk, information_ratio: null, active_return_pct: null }
    render(<DashboardPanel result={null} diagnosticsAnalysis={diagnostics} />)

    const irLabel = screen.getByText('Information Ratio')
    const irRow = irLabel.closest('.benchmark-card-metric')
    expect(irRow ? within(irRow as HTMLElement).getByText('n/a') : null).toBeTruthy()
  })

  it('omits Information Ratio and Active Return (not a second unavailable state) when tracking_error_pct is null', () => {
    const diagnostics = createDiagnosticsEngineFixture()
    diagnostics.volatility_summary = { ...diagnostics.volatility_summary, tracking_error_pct: null }
    diagnostics.relative_risk = { ...diagnostics.relative_risk, information_ratio: 0.42, active_return_pct: 3.5 }
    render(<DashboardPanel result={null} diagnosticsAnalysis={diagnostics} />)

    // Card still renders normally (not the whole-card EmptyState) since
    // historical_sections_available stays true; the two dependent rows
    // are simply omitted rather than shown inconsistently.
    expect(screen.getByText('Risk Summary')).toBeTruthy()
    expect(screen.queryByText('Risk metrics unavailable')).toBeNull()
    expect(screen.queryByText('Information Ratio')).toBeNull()
    expect(screen.queryByText('Active Return (vs benchmark)')).toBeNull()
  })

  it('renders EmptyState instead of crashing when volatility_summary/drawdown_summary/risk_concentration_summary are absent', () => {
    const partialDiagnostics = {
      ...createDiagnosticsEngineFixture(),
      volatility_summary: undefined,
      drawdown_summary: undefined,
      risk_concentration_summary: undefined,
    } as unknown as DiagnosticsEngineResponse
    render(<DashboardPanel result={null} diagnosticsAnalysis={partialDiagnostics} />)
    expect(screen.getByText('Risk metrics unavailable')).toBeTruthy()
  })

  // ── US-24.11: replay disclosures reach the researcher ──────────────────────

  it('surfaces the replay disclosures on the Dashboard when the run was degraded', () => {
    const base = createImportedDashboardFixture()
    const result = {
      ...base,
      run_metadata: {
        ...createDashboardHistoryRunMetadataFixture(),
        unpriced_replay_symbols: ['NOPRICE'],
        withheld_return_dates: ['2026-06-30'],
        withheld_return_reason: 'Return withheld: the state was adjusted to match the statement.',
        replay_cash_anchor: {
          basis: 'statement_nav_date_mismatch' as const,
          nav_as_of: '2026-01-01',
          window_start: '2026-01-08',
          residual: -1196.61,
          trust: 'degraded' as const,
        },
      },
    } as DashboardAnalysis

    render(<DashboardPanel result={result} />)

    const card = screen.getByRole('region', { name: /replay disclosures/i })
    const text = card.textContent ?? ''
    expect(text).toContain('NOPRICE')
    expect(text).toContain('2026-06-30')
    expect(text).toContain('$1,196.61')
  })

  it('shows no replay-disclosure card when the run is clean', () => {
    const base = createImportedDashboardFixture()
    const result = {
      ...base,
      run_metadata: {
        ...createDashboardHistoryRunMetadataFixture(),
        fx_fallback_currencies: [],
        unpriced_replay_symbols: [],
        trade_price_anchored_symbols: [],
        withheld_return_dates: [],
        withheld_return_reason: null,
        replay_cash_anchor: {
          basis: 'statement_nav_at_window_start' as const,
          nav_as_of: '2026-01-08',
          window_start: '2026-01-08',
          residual: 0,
          trust: 'verified' as const,
        },
      },
    } as DashboardAnalysis

    render(<DashboardPanel result={result} />)

    expect(screen.queryByRole('region', { name: /replay disclosures/i })).toBeNull()
  })

})
