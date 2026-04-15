import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { ff2026DashboardGolden } from '../../test/ff2026DashboardGolden'
import { ib2026DashboardGolden } from '../../test/ib2026DashboardGolden'
import { createFf2026ImportedDashboardFixture, createIb2026ImportedDashboardFixture, createImportedDashboardFixture } from '../../test/portfolioFixtures'
import { DashboardPanel, normalizePerformanceSeries } from './DashboardPanel'
import { buildImportedDashboardView } from './portfolioAnalysisAdapter'
import { buildPortfolioSnapshotFromAnalysis } from './portfolioSnapshot'
import type { DashboardAnalysis, ImportedDashboardSource, ImportedPortfolioSnapshotSource } from './types'

const mockAnalysis: ImportedDashboardSource & ImportedPortfolioSnapshotSource = createImportedDashboardFixture()
const mockDashboardView: DashboardAnalysis = buildImportedDashboardView(mockAnalysis)
const ib2026Analysis: ImportedDashboardSource & ImportedPortfolioSnapshotSource = createIb2026ImportedDashboardFixture()
const ib2026DashboardView: DashboardAnalysis = buildImportedDashboardView(ib2026Analysis)
const ff2026Analysis: ImportedDashboardSource & ImportedPortfolioSnapshotSource = createFf2026ImportedDashboardFixture()
const ff2026DashboardView: DashboardAnalysis = buildImportedDashboardView(ff2026Analysis)

describe('DashboardPanel', () => {
  it('renders account summary and monthly returns', () => {
    render(<DashboardPanel result={mockDashboardView} />)

    expect(screen.getByText('U8516450')).toBeTruthy()
    expect(screen.getByText('Portfolio vs SPY path for the selected range')).toBeTruthy()
    expect(screen.getByText('Diversification by Sector')).toBeTruthy()
    expect(screen.getByText('Account and performance')).toBeTruthy()
    expect(screen.getByText('Monthly Returns')).toBeTruthy()
    expect(screen.getByText('Interactive Brokers')).toBeTruthy()
    expect(screen.getByText('Live market history')).toBeTruthy()
  })

  it('renders key IB2026 dashboard values from the imported bootstrap and history chain', () => {
    expect(ib2026DashboardView.snapshot.statement.statement_period).toBe('January 1, 2026 - April 13, 2026')
    expect(ib2026DashboardView.performance_series[ib2026DashboardView.performance_series.length - 1].portfolio_value).toBe(62023.98)
    const draftSnapshot = buildPortfolioSnapshotFromAnalysis(ib2026Analysis, ['IB2026.pdf'])

    const view = render(<DashboardPanel result={ib2026DashboardView} draftSnapshot={draftSnapshot} />)
    const scoped = within(view.container)

    expect(ib2026DashboardView.daily_states.length).toBeGreaterThan(10)
    expect(ib2026DashboardView.performance_series.length).toBeGreaterThan(10)

    expect(scoped.getAllByText(ib2026DashboardGolden.accountId).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ib2026DashboardGolden.brokerLabel).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ib2026DashboardGolden.sourceLabel).length).toBeGreaterThan(0)
    expect(scoped.getByText(ib2026DashboardGolden.accountSummary)).toBeTruthy()
    expect(scoped.getByText((content) => content.includes(ib2026DashboardGolden.statementPeriod))).toBeTruthy()
    expect(scoped.getAllByText(ib2026DashboardGolden.performanceTitle).length).toBeGreaterThan(0)
    expect(scoped.getByText(ib2026DashboardGolden.loadedFileLabel)).toBeTruthy()
    expect(scoped.getAllByText(ib2026DashboardGolden.monthlyStatusLabel).length).toBeGreaterThan(0)

    expect(scoped.getByText(ib2026DashboardGolden.portfolioValue)).toBeTruthy()
    expect(scoped.getByText(`Start value: ${ib2026DashboardGolden.startValue}`)).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.timeWeightedReturn)).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.netContributions)).toBeTruthy()
    expect(scoped.getByText('Drawdown')).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.drawdown)).toBeTruthy()
    expect(scoped.getAllByText('Money-Weighted Return').length).toBeGreaterThan(0)
    expect(scoped.getByText(ib2026DashboardGolden.moneyWeightedReturn)).toBeTruthy()

    for (const monthly of ib2026DashboardGolden.monthlyReturns) {
      expect(scoped.getByText(monthly.month)).toBeTruthy()
      expect(scoped.getByText(monthly.returnPct)).toBeTruthy()
    }

    expect(scoped.getByText('Technology')).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.sectors.Technology)).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.sectors['Broad Market'])).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.sectors.Commodities)).toBeTruthy()
    expect(scoped.getByText('Draft Capital Check')).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.draftCapitalCheck)).toBeTruthy()
    expect(scoped.getByText(ib2026DashboardGolden.draftCapitalHelper)).toBeTruthy()
    expect(scoped.getByText('No sector locked')).toBeTruthy()

    fireEvent.click(screen.getByText('Technology'))
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

    expect(ib2026DashboardView.range_metrics?.['3M']?.summary.start_value).toBe(52386.1)
    expect(ib2026DashboardView.range_metrics?.['3M']?.max_drawdown_pct).toBeCloseTo(-28.3981, 3)
    expect(ib2026DashboardView.range_metrics?.['3M']?.summary.money_weighted_return_pct).toBeCloseTo(-0.6188, 3)
    expect(scoped.getAllByText(`Start value: ${ib2026DashboardGolden.startValue}`).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ib2026DashboardGolden.drawdown).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ib2026DashboardGolden.moneyWeightedReturn).length).toBeGreaterThan(0)

    for (const monthly of ib2026DashboardGolden.monthlyReturns) {
      expect(scoped.getByText(monthly.month)).toBeTruthy()
      expect(scoped.getByText(monthly.returnPct)).toBeTruthy()
    }
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
    expect(scoped.getByText(ff2026DashboardGolden.accountSummary)).toBeTruthy()
    expect(scoped.getByText((content) => content.includes(ff2026DashboardGolden.statementPeriod))).toBeTruthy()
    expect(scoped.getAllByText(ff2026DashboardGolden.performanceTitle).length).toBeGreaterThan(0)
    expect(scoped.getByText(ff2026DashboardGolden.loadedFileLabel)).toBeTruthy()
    expect(scoped.getAllByText(ff2026DashboardGolden.monthlyStatusLabel).length).toBeGreaterThan(0)

    expect(scoped.getByText(ff2026DashboardGolden.portfolioValue)).toBeTruthy()
    expect(scoped.getByText(`Start value: ${ff2026DashboardGolden.startValue}`)).toBeTruthy()
    expect(scoped.getAllByText(ff2026DashboardGolden.timeWeightedReturn).length).toBeGreaterThan(0)
    expect(scoped.getAllByText(ff2026DashboardGolden.netContributions).length).toBeGreaterThan(0)
    expect(scoped.getByText(ff2026DashboardGolden.drawdown)).toBeTruthy()
    expect(scoped.getAllByText(ff2026DashboardGolden.moneyWeightedReturn).length).toBeGreaterThan(0)

    for (const monthly of ff2026DashboardGolden.monthlyReturns) {
      expect(scoped.getByText(monthly.month)).toBeTruthy()
      expect(scoped.getByText(monthly.returnPct)).toBeTruthy()
    }

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

    expect(screen.getByText(/Loaded statements: .*IB2025\.pdf.*IB2026\.pdf/)).toBeTruthy()
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

  it('renders n/a summary values when range metrics are absent even if history exists', () => {
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
    expect(screen.getAllByText('Start value: n/a').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Portfolio vs SPY path for the selected range').length).toBeGreaterThan(0)
    expect(screen.getAllByText('n/a').length).toBeGreaterThan(0)
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

    expect(screen.getByText('$61623.07')).toBeTruthy()
  })

  it('does not recompute visible summary locally when backend range metrics are absent', () => {
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
    expect(screen.getAllByText('Time-Weighted Return').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Start value: n/a').length).toBeGreaterThan(0)
    expect(screen.getAllByText('n/a').length).toBeGreaterThan(0)
  })

  it('hides monthly returns when reconstructed history is economically unstable', () => {
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

    expect(screen.getAllByText('Monthly returns are not reliable for this imported history.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Sample or reconstructed history').length).toBeGreaterThan(0)
    expect(screen.queryByText('2025-07')).toBeNull()
  })

  it('renders n/a for drawdown and money-weighted return when performance history is unavailable', () => {
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

    expect(scoped.getByText('No performance history available yet.')).toBeTruthy()
    expect(scoped.getAllByText('Drawdown').length).toBeGreaterThan(0)
    expect(scoped.getAllByText('Money-Weighted Return').length).toBeGreaterThan(0)
    expect(scoped.getAllByText('n/a').length).toBeGreaterThan(0)
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
