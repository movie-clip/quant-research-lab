import { cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ff2026DashboardGolden, ib2026DashboardGolden } from '../../test/dashboardGoldens'
import {
  createDashboardHistoryRunMetadataFixture,
  createDiagnosticsEngineFixture,
  createExposureEngineFixture,
  createFf2026ImportedDashboardFixture,
  createIb2026ImportedDashboardFixture,
  createImportedDashboardFixture,
} from '../../test/portfolioFixtures'
import { DashboardPanel, normalizePerformanceSeries } from './DashboardPanel'
import { buildExposureFactorModel, buildImportedDashboardView, composeExposureView } from './portfolioAnalysisAdapter'
import { buildPortfolioSnapshotFromAnalysis } from './portfolioSnapshot'
import type { DashboardAnalysis, ImportedDashboardSource } from './types'

const mockAnalysis: ImportedDashboardSource = createImportedDashboardFixture()
const mockDashboardView: DashboardAnalysis = buildImportedDashboardView(mockAnalysis)
const mockRunMetadata = createDashboardHistoryRunMetadataFixture()
const ib2026Analysis: ImportedDashboardSource = createIb2026ImportedDashboardFixture()
const ib2026DashboardView: DashboardAnalysis = buildImportedDashboardView(ib2026Analysis)
const ff2026Analysis: ImportedDashboardSource = createFf2026ImportedDashboardFixture()
const ff2026DashboardView: DashboardAnalysis = buildImportedDashboardView(ff2026Analysis)
const dashboardExposureView = composeExposureView(createExposureEngineFixture(), createDiagnosticsEngineFixture())
const dashboardFactorModel = buildExposureFactorModel(dashboardExposureView)

afterEach(() => {
  cleanup()
})

function parseCurrencyLabel(value: string) {
  return Number(value.replace(/[$,]/g, ''))
}

function parsePercentLabel(value: string) {
  if (value === 'n/a') {
    return null
  }
  return Number(value.replace('%', ''))
}

describe('DashboardPanel', () => {
  it('renders the constrained dashboard surfaces only', () => {
    render(<DashboardPanel result={mockDashboardView} exposureResult={dashboardExposureView} factorModel={dashboardFactorModel} />)

    expect(screen.getByText('U8516450')).toBeTruthy()
    expect(screen.getByText('Project summary')).toBeTruthy()
    expect(screen.getByText('Portfolio vs SPY path for the selected range')).toBeTruthy()
    expect(screen.getByText('Rolling Factor Analysis')).toBeTruthy()
    expect(screen.getByText('Allocation Overview')).toBeTruthy()
    expect(screen.getByText('Interactive Brokers')).toBeTruthy()
    expect(screen.getAllByText('Live market history').length).toBeGreaterThan(0)
    expect(screen.queryByText('Monthly Returns')).toBeNull()
    expect(screen.queryByText('Selected Range Snapshot')).toBeNull()
    expect(screen.queryByText('Performance Workspace')).toBeNull()
    expect(screen.queryByText('Portfolio Improvement Workspace')).toBeNull()
  })

  it('renders project summary provenance and workspace state', () => {
    render(<DashboardPanel result={mockDashboardView} />)

    expect(screen.getByText('Dashboard stays focused on current portfolio truth, the selected-range portfolio path, rolling factor analysis, and allocation overview.')).toBeTruthy()
    expect(screen.getAllByText('Range metrics live').length).toBeGreaterThan(0)
    expect(screen.getByText(/Audit: SPY · live_market_data_unverified_return_basis · portfolio imported_replay · benchmark degraded_unverified_return_basis · monthly imported_replay · 01\/02\/25 to 03\/03\/25 · dataset market_data_service_v1/)).toBeTruthy()
    expect(screen.getByText('Refusals: benchmark return, excess return, and drawdown stay withheld outside the narrow allowlisted exact-slice contract. Investor-economics outputs are withheld because total-return equivalence is unverified. Dashboard policy remains partial-unlock only: exact-slice benchmark return may appear only for the identical admitted slice with independently verified benchmark total-return proof, and excess return still requires the same identical admitted slice pair plus a future server-side runtime enablement. Clients must not treat daily-series subtraction or local derivation as an equivalent path.')).toBeTruthy()
    expect(screen.getByText('Workspace State')).toBeTruthy()
    expect(screen.getByText('Current imported view and editable draft status.')).toBeTruthy()
  })

  it('keeps the refusal copy visible even when an exact-slice scalar is present', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          range_metrics: {
            ...mockAnalysis.range_metrics,
            All: {
              ...mockAnalysis.range_metrics!.All,
              summary: {
                ...mockAnalysis.range_metrics!.All.summary,
                time_weighted_return_pct: 3,
                benchmark_return_pct: 1,
                excess_return_pct: null,
              },
              max_drawdown_pct: null,
            },
          },
          run_metadata: {
            ...mockRunMetadata,
            investor_economics_status: {
              status: 'withheld',
              reason: 'withheld_unverified_total_return_equivalence',
            },
          },
        })}
      />,
    )

    expect(screen.getByText('Refusals: benchmark return, excess return, and drawdown stay withheld outside the narrow allowlisted exact-slice contract. Investor-economics outputs are withheld because total-return equivalence is unverified. Dashboard policy remains partial-unlock only: exact-slice benchmark return may appear only for the identical admitted slice with independently verified benchmark total-return proof, and excess return still requires the same identical admitted slice pair plus a future server-side runtime enablement. Clients must not treat daily-series subtraction or local derivation as an equivalent path.')).toBeTruthy()
    expect(screen.queryByText('Drawdown')).toBeNull()
  })

  it('uses explicit partial-unlock metadata for dashboard refusal wording', () => {
    render(<DashboardPanel result={mockDashboardView} />)

    expect(mockDashboardView.run_metadata?.investor_economics_partial_unlock.mode).toBe('allowlisted_exact_slice_scalars_only')
    expect(mockDashboardView.run_metadata?.investor_economics_partial_unlock.client_derivation_rule).toBe('server_side_scalar_only_no_daily_series_subtraction_equivalence')
    expect(mockDashboardView.run_metadata?.investor_economics_partial_unlock.exact_slice_scalar_allowlist).toEqual([
      {
        field: 'range_metrics[*].summary.time_weighted_return_pct',
        unlock_condition: 'identical_admitted_exact_slice_only',
        runtime_enabled: true,
      },
      {
        field: 'range_metrics[*].summary.benchmark_return_pct',
        unlock_condition: 'identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only',
        runtime_enabled: true,
      },
      {
        field: 'range_metrics[*].summary.excess_return_pct',
        unlock_condition: 'identical_admitted_exact_slice_pair_only',
        runtime_enabled: false,
      },
    ])
    expect(mockDashboardView.run_metadata?.investor_economics_partial_unlock.withheld_families).toContain('benchmark_relative_path_derived_outputs')
    expect(mockDashboardView.run_metadata?.investor_economics_partial_unlock.withheld_families).toContain('drawdown_family')
  })

  it('renders the rolling factor chart on dashboard when exposure context is available', () => {
    render(<DashboardPanel result={mockDashboardView} exposureResult={dashboardExposureView} factorModel={dashboardFactorModel} />)

    expect(screen.getByText('Rolling Factor Analysis')).toBeTruthy()
    expect(screen.getByLabelText('Visible factors on rolling factor chart')).toBeTruthy()
    expect(screen.getAllByText('Market').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Growth').length).toBeGreaterThan(0)
  })

  it('does not render the dashboard rolling factor chart when factor model data is unavailable', () => {
    render(
      <DashboardPanel
        result={mockDashboardView}
        exposureResult={dashboardExposureView}
        factorModel={null}
      />,
    )

    expect(screen.queryByLabelText('Visible factors on rolling factor chart')).toBeNull()
  })

  it('renders key IB2026 dashboard values from the imported bootstrap and history chain', () => {
    expect(ib2026DashboardView.snapshot.statement.statement_period).toBe(ib2026DashboardGolden.statementPeriod)
    expect(ib2026DashboardView.performance_series[ib2026DashboardView.performance_series.length - 1].portfolio_value).toBe(parseCurrencyLabel(ib2026DashboardGolden.portfolioValue))
    const draftSnapshot = buildPortfolioSnapshotFromAnalysis(ib2026Analysis, ['IB2026.pdf'])

    const view = render(<DashboardPanel result={ib2026DashboardView} draftSnapshot={draftSnapshot} />)
    const scoped = within(view.container)

    expect(ib2026DashboardView.daily_states.length).toBeGreaterThan(10)
    expect(ib2026DashboardView.performance_series.length).toBeGreaterThan(10)

    expect(scoped.getAllByText(ib2026DashboardGolden.accountId).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ib2026DashboardGolden.brokerLabel).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ib2026DashboardGolden.sourceLabel).length).toBeGreaterThan(0)
    expect(scoped.getByText('Project summary')).toBeTruthy()
    expect(scoped.getByText((content) => content.includes(ib2026DashboardGolden.statementPeriod))).toBeTruthy()
    expect(scoped.getAllByText(ib2026DashboardGolden.performanceTitle).length).toBeGreaterThan(0)
    expect(scoped.getByText(ib2026DashboardGolden.loadedFileLabel)).toBeTruthy()

    expect(scoped.getByText(`Portfolio value: ${ib2026DashboardGolden.portfolioValue}`)).toBeTruthy()

    expect(scoped.getByText('Technology')).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.sectors.Technology)).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.sectors['Broad Market'])).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.sectors.Commodities)).toBeTruthy()
    expect(scoped.getByText('Draft Capital Check')).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.draftCapitalHelper)).toBeTruthy()
    expect(scoped.getByText('No sector locked')).toBeTruthy()

    fireEvent.click(scoped.getAllByText('Technology')[0])
    for (const symbol of ib2026DashboardGolden.technologyHoldings) {
      expect(screen.getByDisplayValue(symbol)).toBeTruthy()
      expect(screen.getByText(ib2026DashboardGolden.technologyHoldingWeights[symbol])).toBeTruthy()
    }
    expect(screen.getByText('Locked on Technology')).toBeTruthy()
    expect(screen.getByDisplayValue(ib2026DashboardGolden.sxrvValue)).toBeTruthy()
  })

  it('keeps generated IB2026 backend range metrics aligned with visible dashboard output', () => {
    const view = render(<DashboardPanel result={ib2026DashboardView} draftSnapshot={buildPortfolioSnapshotFromAnalysis(ib2026Analysis, ['IB2026.pdf'])} />)
    const scoped = within(view.container)

    expect(ib2026DashboardView.range_metrics?.['3M']?.summary.start_value).toBeCloseTo(parseCurrencyLabel(ib2026DashboardGolden.startValue), 2)
    expect(ib2026DashboardView.range_metrics?.['3M']?.max_drawdown_pct).toBe(parsePercentLabel(ib2026DashboardGolden.drawdown))
    expect(ib2026DashboardView.range_metrics?.['3M']?.summary.money_weighted_return_pct).toBeCloseTo(parsePercentLabel(ib2026DashboardGolden.moneyWeightedReturn) ?? 0, 2)
    expect(scoped.getAllByText('Range metrics live').length).toBeGreaterThan(0)
    expect(scoped.getByText(`Portfolio value: ${ib2026DashboardGolden.portfolioValue}`)).toBeTruthy()
    expect(scoped.queryByText('Drawdown')).toBeNull()
    expect(scoped.queryByText('Money-Weighted Return')).toBeNull()
  })

  it('renders Freedom24 FF2026 dashboard values from the imported bootstrap and history chain', () => {
    expect(ff2026DashboardView.snapshot.statement.importer).toBe('freedom24')
    expect(ff2026DashboardView.performance_series[ff2026DashboardView.performance_series.length - 1].portfolio_value).toBe(3071)
    const draftSnapshot = buildPortfolioSnapshotFromAnalysis(ff2026Analysis, ['FF2026.pdf'])

    const view = render(<DashboardPanel result={ff2026DashboardView} draftSnapshot={draftSnapshot} />)
    const scoped = within(view.container)

    expect(ff2026DashboardView.daily_states.length).toBeGreaterThan(10)
    expect(ff2026DashboardView.performance_series.length).toBeGreaterThan(10)

    expect(scoped.getAllByText(ff2026DashboardGolden.accountId).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ff2026DashboardGolden.brokerLabel).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ff2026DashboardGolden.sourceLabel).length).toBeGreaterThan(0)
    expect(scoped.getByText('Project summary')).toBeTruthy()
    expect(scoped.getByText((content) => content.includes(ff2026DashboardGolden.statementPeriod))).toBeTruthy()
    expect(scoped.getAllByText(ff2026DashboardGolden.performanceTitle).length).toBeGreaterThan(0)
    expect(scoped.getByText(ff2026DashboardGolden.loadedFileLabel)).toBeTruthy()

    expect(scoped.getByText(`Portfolio value: ${ff2026DashboardGolden.portfolioValue}`)).toBeTruthy()

    expect(scoped.getByText('Broad Market')).toBeTruthy()
    expect(scoped.getByText(ff2026DashboardGolden.sectors['Broad Market'])).toBeTruthy()
    expect(scoped.getAllByText(ff2026DashboardGolden.draftCapitalCheck).length).toBeGreaterThan(0)
    expect(scoped.getByText(ff2026DashboardGolden.draftCapitalHelper)).toBeTruthy()
    expect(scoped.getByText('No sector locked')).toBeTruthy()

    fireEvent.click(scoped.getAllByText('Broad Market')[0])
    for (const symbol of ff2026DashboardGolden.broadMarketHoldings) {
      expect(screen.getByDisplayValue(symbol)).toBeTruthy()
      expect(screen.getByText(ff2026DashboardGolden.broadMarketHoldingWeights[symbol])).toBeTruthy()
    }
    expect(screen.getByText('Locked on Broad Market')).toBeTruthy()
    expect(screen.getByDisplayValue(ff2026DashboardGolden.vtiValue)).toBeTruthy()
  })

  it('shows combined statement metadata when multiple statements are loaded', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          snapshot: {
            ...mockAnalysis.snapshot,
            statement: {
              ...mockAnalysis.snapshot.statement,
              statement_period: '2025-01-02 - 2026-04-08',
            },
            statements: [
              mockAnalysis.snapshot.statements[0],
              {
                importer: 'interactive_brokers',
                account_id: 'U8516450',
                base_currency: 'USD',
                statement_period: '2026-01-01 - 2026-04-08',
                page_count: 17,
                source_path: 'C:\\docs\\IB2026.pdf',
                detected_format: 'pdf',
                imported_at: '2026-04-10T00:05:00Z',
              },
            ],
          },
        })}
      />,
    )

    expect(screen.getAllByText(/Loaded statements: .*IB2025\.pdf.*IB2026\.pdf/).length).toBeGreaterThan(0)
    expect(screen.getByText(/2 statements combined/)).toBeTruthy()
  })

  it('shows multi-broker label for mixed statement imports', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          snapshot: {
            ...mockAnalysis.snapshot,
            statement: {
              ...mockAnalysis.snapshot.statement,
              importer: 'multi_broker',
              account_id: 'U8516450 + 185960',
            },
            statements: [
              {
                importer: 'interactive_brokers',
                account_id: 'U8516450',
                base_currency: 'USD',
                statement_period: '2026-01-01 - 2026-04-08',
                page_count: 17,
                source_path: 'C:\\docs\\U8516450_20260101_20260408.pdf',
                detected_format: 'pdf',
                imported_at: '2026-04-10T00:00:00Z',
              },
              {
                importer: 'freedom24',
                account_id: '185960',
                base_currency: 'USD',
                statement_period: '2025-12-31 - 2026-04-09',
                page_count: 8,
                source_path: 'C:\\docs\\FF2026.pdf',
                detected_format: 'pdf',
                imported_at: '2026-04-10T00:05:00Z',
              },
            ],
          },
        })}
      />,
    )

    expect(screen.getByText('Multi-Broker')).toBeTruthy()
    expect(screen.getByText(/U8516450 \+ 185960/)).toBeTruthy()
  })

  it('renders append action when provided and triggers handlers', () => {
    const onImportPortfolio = vi.fn()
    const onAppendStatement = vi.fn()
    const onClearImportedSession = vi.fn()

    render(
      <DashboardPanel
        result={mockDashboardView}
        onImportPortfolio={onImportPortfolio}
        onAppendStatement={onAppendStatement}
        onClearImportedSession={onClearImportedSession}
      />,
    )

    fireEvent.click(screen.getByText('Replace Import'))
    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.click(screen.getByText('Clear Imported Session'))

    expect(onImportPortfolio).toHaveBeenCalledTimes(1)
    expect(onAppendStatement).toHaveBeenCalledTimes(1)
    expect(onClearImportedSession).toHaveBeenCalledTimes(1)
  })

  it('shows restored-session badges when session was recovered on launch', () => {
    render(<DashboardPanel result={mockDashboardView} restoredSession />)

    expect(screen.getAllByText('Restored on launch').length).toBeGreaterThan(0)
  })

  it('renders account metadata fallbacks when statement fields are missing', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          snapshot: {
            ...mockAnalysis.snapshot,
            statement: {
              ...mockAnalysis.snapshot.statement,
              account_id: null,
              statement_period: null,
            },
          },
        })}
      />,
    )

    expect(screen.getByText('Unknown')).toBeTruthy()
    expect(screen.getByText(/Statement period unavailable/)).toBeTruthy()
  })

  it('shows empty draft allocation states when no editable snapshot is available', () => {
    const emptyDraftSnapshot = {
      ...buildPortfolioSnapshotFromAnalysis(mockAnalysis, ['IB2025.pdf']),
      positions: [],
      cashBalances: [],
    }

    render(<DashboardPanel result={mockDashboardView} draftSnapshot={emptyDraftSnapshot} />)

    expect(screen.getAllByText('No positions available for sector breakdown.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No sector locked').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Hover or click a sector to inspect its holdings.').length).toBeGreaterThan(0)
  })

  it('clears the locked sector and keeps draft capital check stable when the last holding in a sector is removed', () => {
    const draftSnapshot = buildPortfolioSnapshotFromAnalysis(ff2026Analysis, ['FF2026.pdf'])

    render(<DashboardPanel result={ff2026DashboardView} draftSnapshot={draftSnapshot} />)

    fireEvent.click(screen.getAllByText('Broad Market')[0])
    expect(screen.getByText('Locked on Broad Market')).toBeTruthy()

    const removeButtons = screen.getAllByText('Remove')
    for (const button of [...removeButtons]) {
      fireEvent.click(button)
    }

    expect(screen.getByText('No sector locked')).toBeTruthy()
    expect(screen.getAllByText('Hover or click a sector to inspect its holdings.').length).toBeGreaterThan(0)
    expect(screen.getByText('Draft Capital Check')).toBeTruthy()
  })

  it('keeps the chart surface but drops metric cards when range metrics are absent', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          range_metrics: null,
          performance_series: [
            { date: '2022-01-03', portfolio_value: 0, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
            { date: '2022-04-12', portfolio_value: 5378.38, benchmark_price: 102, portfolio_return_pct: 0, benchmark_return_pct: 2 },
            { date: '2026-04-08', portfolio_value: 64272.07, benchmark_price: 141.51, portfolio_return_pct: 2891.15, benchmark_return_pct: 41.51 },
          ],
          daily_states: [
            { date: '2022-01-03', total_market_value: 0, total_portfolio_value: 0, external_cash_flow: 0, cash: { USD: 0 }, positions: [] },
            { date: '2022-04-12', total_market_value: 6906.16, total_portfolio_value: 5378.38, external_cash_flow: 7910.75, cash: { USD: -1527.78 }, positions: [] },
            { date: '2026-04-08', total_market_value: 65000, total_portfolio_value: 64272.07, external_cash_flow: 0, cash: { USD: -727.93 }, positions: [] },
          ],
        })}
      />,
    )

    fireEvent.click(screen.getAllByText('All')[0])
    expect(screen.getAllByText('Portfolio vs SPY path for the selected range').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Range metrics unavailable').length).toBeGreaterThan(0)
    expect(screen.queryByText('Selected Range Snapshot')).toBeNull()
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

  it('prefers statement ending value when reconstructed history overstates final nav', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          range_metrics: null,
          snapshot: {
            ...mockAnalysis.snapshot,
            statement_totals: {
              stock_total: 50634.03,
              cash_total: 10982.68,
              dividends_total: null,
              withholding_tax_total: null,
              interest_total: null,
              other_fees_total: null,
              deposits_total: null,
              starting_nav: 52381.12,
              ending_nav: 61623.07,
              fx_rates: {},
            },
          },
          performance_series: [
            { date: '2026-01-02', portfolio_value: 52381.12, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
            { date: '2026-04-10', portfolio_value: 83502.27, benchmark_price: 101, portfolio_return_pct: 59.4, benchmark_return_pct: 1 },
          ],
          daily_states: [
            { date: '2026-01-02', total_market_value: 25693.53, total_portfolio_value: 52381.12, external_cash_flow: 0, cash: { USD: 26687.59 }, positions: [] },
            { date: '2026-04-10', total_market_value: 50630.38, total_portfolio_value: 83502.27, external_cash_flow: 9963, cash: { USD: 32871.89 }, positions: [] },
          ],
        })}
      />,
    )

    expect(screen.getByText('Portfolio value: $61623.07')).toBeTruthy()
  })

  it('does not restore removed dashboard metric cards when backend range metrics are absent', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          range_metrics: null,
          performance_series: [
            { date: '2025-01-02', portfolio_value: 0, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
            { date: '2025-06-30', portfolio_value: 3139.15, benchmark_price: 110, portfolio_return_pct: 0, benchmark_return_pct: 10 },
            { date: '2026-04-10', portfolio_value: 64687.71, benchmark_price: 116, portfolio_return_pct: 871.82, benchmark_return_pct: 16.22 },
          ],
          daily_states: [
            { date: '2025-01-02', total_market_value: 0, total_portfolio_value: 0, external_cash_flow: 0, cash: { USD: 0 }, positions: [] },
            { date: '2025-06-30', total_market_value: 3139.15, total_portfolio_value: 3139.15, external_cash_flow: 3139.15, cash: { USD: 0 }, positions: [] },
            { date: '2026-04-10', total_market_value: 64687.71, total_portfolio_value: 64687.71, external_cash_flow: 0, cash: { USD: 0 }, positions: [] },
          ],
        })}
      />,
    )

    fireEvent.click(screen.getAllByText('All')[0])
    expect(screen.queryByText('Time-Weighted Return')).toBeNull()
    expect(screen.queryByText('Money-Weighted Return')).toBeNull()
    expect(screen.queryByText('Drawdown')).toBeNull()
  })

  it('keeps monthly-return-specific dashboard content removed for unstable reconstructed history', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          range_metrics: null,
          source_status: {
            performance_history: 'sample',
            monthly_returns: 'suppressed',
          },
          daily_states: [
            { date: '2025-01-02', total_market_value: 0, total_portfolio_value: 0, external_cash_flow: 0, cash: { USD: 0 }, positions: [] },
            { date: '2025-06-30', total_market_value: 3139.15, total_portfolio_value: 3139.15, external_cash_flow: 3139.15, cash: { USD: 0 }, positions: [] },
            { date: '2025-07-31', total_market_value: -250, total_portfolio_value: -250, external_cash_flow: 0, cash: { USD: 0 }, positions: [] },
            { date: '2025-08-29', total_market_value: 64687.71, total_portfolio_value: 64687.71, external_cash_flow: 0, cash: { USD: 0 }, positions: [] },
          ],
        })}
      />,
    )

    expect(screen.getAllByText('Sample or reconstructed history').length).toBeGreaterThan(0)
    expect(screen.queryByText('Monthly Returns')).toBeNull()
  })

  it('renders unavailable performance copy when history is unavailable', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          performance_series: [],
          daily_states: [],
          range_metrics: null,
          source_status: {
            performance_history: 'unavailable',
            monthly_returns: 'unavailable',
          },
          run_metadata: {
            ...createDashboardHistoryRunMetadataFixture('unavailable'),
          },
        })}
      />,
    )

    expect(screen.getByText('Performance history is unavailable for this import.')).toBeTruthy()
    expect(screen.getByText(/Audit: SPY · unavailable · portfolio unavailable · benchmark unavailable · monthly unavailable · History window unavailable · dataset market_data_service_v1/)).toBeTruthy()
    expect(screen.queryByText('Monthly Returns')).toBeNull()
  })

  it('keeps removed dashboard metric cards hidden when performance history is unavailable', () => {
    const view = render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
          performance_series: [],
          daily_states: [],
          range_metrics: null,
          source_status: {
            performance_history: 'unavailable',
            monthly_returns: 'unavailable',
          },
        })}
      />,
    )
    const scoped = within(view.container)

    expect(scoped.getByText('Performance history is unavailable for this import.')).toBeTruthy()
    expect(scoped.queryByText('Drawdown')).toBeNull()
    expect(scoped.queryByText('Money-Weighted Return')).toBeNull()
  })

  it('builds a scenario preview for exposure from size-only sector edits', () => {
    const previewSpy = vi.fn()
    const saveVariantSpy = vi.fn()
    const draftChangeSpy = vi.fn()
    const draftSnapshot = buildPortfolioSnapshotFromAnalysis(mockAnalysis, ['IB2025.pdf'])

    render(
      <DashboardPanel
        result={mockDashboardView}
        draftSnapshot={draftSnapshot}
        activeNodeName="Base Import"
        draftStatus="dirty"
        onPreviewExposure={previewSpy}
        onDraftSnapshotChange={draftChangeSpy}
        onSaveVariant={saveVariantSpy}
      />,
    )

    const technologyButtons = screen.getAllByText('Technology')
    const marketValueInputs = screen.getAllByPlaceholderText('Market value')
    const previewButtons = screen.getAllByText('Preview in Exposure')

    fireEvent.click(technologyButtons[technologyButtons.length - 1])
    fireEvent.change(marketValueInputs[marketValueInputs.length - 1], { target: { value: '15000' } })
    fireEvent.click(previewButtons[previewButtons.length - 1])

    const previewSnapshot = previewSpy.mock.calls[0]?.[0]
    expect(previewSnapshot.positions.find((position: { symbol: string; marketValue: number }) => position.symbol === 'MSFT')?.marketValue).toBe(15000)
    expect(draftChangeSpy).toHaveBeenCalled()

    const variantInput = screen.getAllByPlaceholderText('Variant name')[0]
    fireEvent.change(variantInput, { target: { value: 'Raise MSFT' } })
    expect(screen.getAllByRole('button', { name: 'Save Variant' }).some((button) => !button.hasAttribute('disabled'))).toBe(true)
    expect(screen.queryByText('Working Draft')).toBeNull()
  })

  it('shows restore shell when only narrow restore data is available', () => {
    const clearSpy = vi.fn()

    render(<DashboardPanel result={null} lastImportedFileNames={['IB2025.pdf']} restoredSession onClearImportedSession={clearSpy} />)

    expect(screen.getAllByText('Restored on launch').length).toBeGreaterThan(0)
    expect(screen.getByText('Last import: IB2025.pdf')).toBeTruthy()
    expect(screen.getAllByText('Clear Imported Session').length).toBeGreaterThan(0)
  })
})
