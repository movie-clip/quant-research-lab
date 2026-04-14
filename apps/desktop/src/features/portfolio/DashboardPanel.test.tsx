import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { createImportedDashboardFixture } from '../../test/portfolioFixtures'
import { DashboardPanel, normalizePerformanceSeries } from './DashboardPanel'
import { buildImportedDashboardView } from './portfolioAnalysisAdapter'
import { buildPortfolioSnapshotFromAnalysis } from './portfolioSnapshot'
import type { DashboardAnalysis, ImportedDashboardSource, ImportedPortfolioSnapshotSource } from './types'

const mockAnalysis: ImportedDashboardSource & ImportedPortfolioSnapshotSource = createImportedDashboardFixture()
const mockDashboardView: DashboardAnalysis = buildImportedDashboardView(mockAnalysis)

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

  it('keeps rendering account summary when early portfolio history starts at zero', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
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
    expect(screen.getByText('Start value: $5378.38')).toBeTruthy()
    expect(screen.getAllByText('Portfolio vs SPY path for the selected range').length).toBeGreaterThan(0)
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

  it('anchors visible performance summary to the first non-zero portfolio value', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
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
    expect(screen.getByText('871.82%')).toBeTruthy()
    expect(screen.getByText('Start value: $3139.15')).toBeTruthy()
  })

  it('hides monthly returns when reconstructed history is economically unstable', () => {
    render(
      <DashboardPanel
        result={buildImportedDashboardView({
          ...mockAnalysis,
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

    expect(screen.getByText('Monthly returns are not reliable for this imported history.')).toBeTruthy()
    expect(screen.getAllByText('Sample or reconstructed history').length).toBeGreaterThan(0)
    expect(screen.queryByText('2025-07')).toBeNull()
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
