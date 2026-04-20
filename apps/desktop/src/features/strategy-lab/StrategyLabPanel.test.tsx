import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { StrategyLabPanel } from './StrategyLabPanel'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('StrategyLabPanel', () => {
  it('combines ETF universe presets like a mask', () => {
    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByRole('button', { name: /Broad ETF Rotation/i }))
    fireEvent.click(screen.getByText('Growth vs Value'))

    expect(screen.getByDisplayValue('XLK,XLF,XLV,XLE,XLI,QQQ,IWM,SPY')).toBeTruthy()
  })

  it('renders the strategy result after running the ETF rotation prototype', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK', 'XLF', 'XLV', 'XLE', 'XLI', 'QQQ', 'IWM'],
        start_date: '2020-01-02',
        end_date: '2024-12-02',
        rebalance_frequency: 'monthly',
        lookback_months: 3,
        top_n: 3,
        methodology: 'm',
        source_status: {
          price_history: 'live',
          leader_internals: 'mixed',
          holdings_snapshot_counts: { XLK: 2 },
          dated_holdings_symbols: ['XLK'],
          sample_fallback_symbols: ['XLF'],
        },
        current_rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [
          { date: '2024-03-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
          { date: '2024-06-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
          { date: '2024-09-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
          { date: '2024-12-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] },
        ],
        etf_internals_history: {
          XLK: [
            { date: '2024-03-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
            { date: '2024-06-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
            { date: '2024-09-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
            { date: '2024-12-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] },
          ],
        },
        observations: [
          { date: '2024-03-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-04-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-06-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-09-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-12-02', rankings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 0.3333, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
        ],
        equity_curve: [{ date: '2024-12-02', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 28.4, average_volume_participation_ratio: 1.12 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))

    await waitFor(() => expect(screen.getByText('Leadership Heatmap')).toBeTruthy())
    const payload = JSON.parse(String(fetchSpy.mock.calls[0]?.[1]?.body)) as { lookback_months: number; prefer_live_data?: boolean }
    const heatmap = screen.getByTestId('strategy-heatmap')
    const leaderHeatmap = screen.getByTestId('strategy-leader-heatmap')
    expect(payload.lookback_months).toBe(12)
    expect(payload.prefer_live_data).toBe(true)
    expect(screen.queryByText('Prototype the book-faithful ETF rotation workflow: rank ETFs by trailing momentum, hold the top sleeves equally, and replay multi-year trend leadership for slower-moving investors and big-trend traders.')).toBeNull()
    expect(within(heatmap).getAllByText('Q1 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q2 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q3 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q4 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).queryByText('04/24')).toBeNull()
    expect(screen.queryByText('2024-04-02')).toBeNull()
    expect(screen.getByText('Investor Economics')).toBeTruthy()
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0)
    expect(screen.getByText('Volume Participation')).toBeTruthy()
    expect(screen.getByText('Price History')).toBeTruthy()
    expect(screen.getAllByText('Leader Internals').length).toBeGreaterThan(0)
    expect(screen.getByText('Live FMP')).toBeTruthy()
    expect(screen.getByText('Mixed live + sample')).toBeTruthy()
    expect(screen.getByText('XLK 2')).toBeTruthy()
    expect(screen.getByText('Sample fallback: XLF')).toBeTruthy()
    expect(screen.getByText('Leader Relative Heatmap')).toBeTruthy()
    expect(within(leaderHeatmap).getAllByText('XLK').length).toBeGreaterThan(0)
    expect(within(leaderHeatmap).getAllByText('0.0').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Leader Internals').length).toBeGreaterThan(0)
    expect(screen.getByText('Constituent Mini Heatmap')).toBeTruthy()
    expect(screen.getByText('Selected ETF history: XLK')).toBeTruthy()
    expect(screen.getByText('Selected ETF history')).toBeTruthy()
    expect(screen.getByText('Actual leaders only')).toBeTruthy()
    expect(screen.queryByText('Top Contributors')).toBeNull()
    expect(screen.queryByText('Lagging Contributors')).toBeNull()
    const constituentHeatmap = screen.getByTestId('strategy-constituent-heatmap')
    expect(screen.getByText('Contribution')).toBeTruthy()
    expect(screen.getByText('Lookback Price Change')).toBeTruthy()
    fireEvent.mouseEnter(screen.getByRole('button', { name: /Q3 2024/i }))
    expect(within(constituentHeatmap).getAllByText('Q3 2024').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('7.9').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/snapshot/i).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('Lookback Price Change'))
    expect(within(constituentHeatmap).getAllByText('33.1').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('Contribution'))
    expect(within(constituentHeatmap).getAllByText('7.9').length).toBeGreaterThan(0)
    expect(screen.getByText('Show details')).toBeTruthy()
    fireEvent.click(screen.getByText('Show details'))
    expect(screen.getByText('XLK Constituents')).toBeTruthy()
    expect(screen.getByText('Top Contributors')).toBeTruthy()
    expect(screen.getByText('Lagging Contributors')).toBeTruthy()
    expect(screen.getByText('Current Rankings')).toBeTruthy()
    expect(screen.getByText('Rebalance History')).toBeTruthy()
    expect(screen.getByText('Checkpoint investor-performance fields are intentionally withheld until Strategy Lab meets the verified investor total-return equivalence contract.')).toBeTruthy()
    expect(screen.getByText('2024-03-02')).toBeTruthy()
    expect(screen.getByText('2024-06-02')).toBeTruthy()
    expect(screen.getAllByText('XLK').length).toBeGreaterThan(0)
    expect(screen.queryByText('Rotation Equity')).toBeNull()
    expect(screen.queryByText('Rotation Drawdown')).toBeNull()
  })

  it('uses signal lookback as the visible quarterly range', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK'],
        start_date: '2020-01-02',
        end_date: '2024-12-02',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        source_status: {
          price_history: 'live',
          leader_internals: 'live-dated',
          holdings_snapshot_counts: { XLK: 3 },
          dated_holdings_symbols: ['XLK'],
          sample_fallback_symbols: [],
        },
        current_rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [
          { date: '2023-03-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
          { date: '2023-06-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
          { date: '2023-09-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-09-02', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
          { date: '2023-12-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-12-02', constituents: [{ symbol: 'AVGO', name: 'Broadcom', weight: 0.23, trailing_return_pct: 19.4, weighted_contribution_pct: 4.46 }] },
          { date: '2024-03-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
          { date: '2024-06-02', leader_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
          { date: '2024-09-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
          { date: '2024-12-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] },
        ],
        etf_internals_history: {
          XLK: [
            { date: '2023-03-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
            { date: '2023-06-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
            { date: '2023-09-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-09-02', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
            { date: '2023-12-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2023-12-02', constituents: [{ symbol: 'AVGO', name: 'Broadcom', weight: 0.23, trailing_return_pct: 19.4, weighted_contribution_pct: 4.46 }] },
            { date: '2024-03-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-03-02', constituents: [{ symbol: 'AAPL', name: 'Apple', weight: 0.31, trailing_return_pct: 18.2, weighted_contribution_pct: 5.64 }] },
            { date: '2024-06-02', etf_symbol: 'XLK', source_mode: 'sample', snapshot_date: '2024-06-02', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 20.5, weighted_contribution_pct: 5.95 }] },
            { date: '2024-09-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.24, trailing_return_pct: 33.1, weighted_contribution_pct: 7.94 }] },
            { date: '2024-12-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] },
          ],
        },
        observations: [
          { date: '2023-03-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2023-06-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2023-09-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2023-12-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-03-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-06-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-09-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
          { date: '2024-12-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 },
        ],
        equity_curve: [{ date: '2024-12-02', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 28.4, average_volume_participation_ratio: 1.12 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.change(screen.getByLabelText('Signal Lookback'), { target: { value: '16' } })
    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))

    await waitFor(() => expect(screen.getByText('Leadership Heatmap')).toBeTruthy())

    const heatmap = screen.getByTestId('strategy-heatmap')
    expect(within(heatmap).getAllByText('Q1 2023').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q2 2023').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q3 2023').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q4 2023').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q1 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q2 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q3 2024').length).toBeGreaterThan(0)
    expect(within(heatmap).getAllByText('Q4 2024').length).toBeGreaterThan(0)
  })

  it('shows selected ETF constituent history across all visible quarters even when it only leads at the selected checkpoint', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLF', 'XLE', 'XLK', 'XLI'],
        start_date: '2025-03-31',
        end_date: '2026-03-31',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        source_status: { price_history: 'live', leader_internals: 'live-dated', holdings_snapshot_counts: { XLE: 1 }, dated_holdings_symbols: ['XLE'], sample_fallback_symbols: [] },
        current_rankings: [{ symbol: 'XLE', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLE', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [{ date: '2026-03-31', leader_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 33.0, weighted_contribution_pct: 9.9 }] }],
        etf_internals_history: {
          XLE: [
            { date: '2025-06-30', etf_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 10.0, weighted_contribution_pct: 3.0 }] },
            { date: '2025-09-30', etf_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 12.0, weighted_contribution_pct: 3.6 }] },
            { date: '2025-12-31', etf_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 18.0, weighted_contribution_pct: 5.4 }] },
            { date: '2026-03-31', etf_symbol: 'XLE', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'XOM', name: 'Exxon', weight: 0.3, trailing_return_pct: 33.0, weighted_contribution_pct: 9.9 }] },
          ],
        },
        observations: [
          { date: '2025-06-30', rankings: [{ symbol: 'XLF', target_weight: 1, score: 0.2, trailing_return_pct: 20, average_volume: 1000000 }, { symbol: 'XLE', target_weight: 0, score: 0.1, trailing_return_pct: 10, average_volume: 1000000 }], holdings: [{ symbol: 'XLF', target_weight: 1, score: 0.2, trailing_return_pct: 20, average_volume: 1000000 }], leader: 'XLF', leader_score: 0.2, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-09-30', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.21, trailing_return_pct: 21, average_volume: 1000000 }, { symbol: 'XLE', target_weight: 0, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.21, trailing_return_pct: 21, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.21, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-12-31', rankings: [{ symbol: 'XLI', target_weight: 1, score: 0.22, trailing_return_pct: 22, average_volume: 1000000 }, { symbol: 'XLE', target_weight: 0, score: 0.18, trailing_return_pct: 18, average_volume: 1000000 }], holdings: [{ symbol: 'XLI', target_weight: 1, score: 0.22, trailing_return_pct: 22, average_volume: 1000000 }], leader: 'XLI', leader_score: 0.22, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2026-03-31', rankings: [{ symbol: 'XLE', target_weight: 1, score: 0.33, trailing_return_pct: 33, average_volume: 1000000 }, { symbol: 'XLI', target_weight: 0, score: 0.25, trailing_return_pct: 25, average_volume: 1000000 }], holdings: [{ symbol: 'XLE', target_weight: 1, score: 0.33, trailing_return_pct: 33, average_volume: 1000000 }], leader: 'XLE', leader_score: 0.33, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
        ],
        equity_curve: [{ date: '2026-03-31', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 20, average_volume_participation_ratio: 1.1 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))
    await waitFor(() => expect(screen.getByText('Leadership Heatmap')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: /Q1 2026/i }))

    const constituentHeatmap = screen.getByTestId('strategy-constituent-heatmap')
    expect(within(constituentHeatmap).getAllByText('XOM').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('3.0').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('3.6').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('5.4').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).getAllByText('9.9').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByText('Actual leaders only'))
    expect(within(constituentHeatmap).queryByText('3.0')).toBeNull()
    expect(within(constituentHeatmap).queryByText('3.6')).toBeNull()
    expect(within(constituentHeatmap).queryByText('5.4')).toBeNull()
    expect(within(constituentHeatmap).getAllByText('9.9').length).toBeGreaterThan(0)
  })

  it('keeps quarterly trailing-return cells aligned with the selected ETF history', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK', 'XLF', 'XLE', 'XLI'],
        start_date: '2025-03-31',
        end_date: '2025-12-31',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        source_status: { price_history: 'live', leader_internals: 'live-dated', holdings_snapshot_counts: { XLK: 1 }, dated_holdings_symbols: ['XLK'], sample_fallback_symbols: [] },
        current_rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [
          { date: '2025-06-30', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 27.89, weighted_contribution_pct: 4.27 }] },
        ],
        etf_internals_history: {
          XLK: [
            { date: '2025-03-31', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 19.94, weighted_contribution_pct: 3.05 }] },
            { date: '2025-06-30', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 27.89, weighted_contribution_pct: 4.27 }] },
            { date: '2025-09-30', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 53.64, weighted_contribution_pct: 8.21 }] },
            { date: '2025-12-31', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-11', constituents: [{ symbol: 'NVDA', name: 'NVIDIA', weight: 0.15, trailing_return_pct: 38.88, weighted_contribution_pct: 5.95 }] },
          ],
        },
        observations: [
          { date: '2025-03-31', rankings: [{ symbol: 'XLF', target_weight: 1, score: 0.2, trailing_return_pct: 20, average_volume: 1000000 }, { symbol: 'XLK', target_weight: 0, score: 0.19, trailing_return_pct: 19, average_volume: 1000000 }], holdings: [{ symbol: 'XLF', target_weight: 1, score: 0.2, trailing_return_pct: 20, average_volume: 1000000 }], leader: 'XLF', leader_score: 0.2, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-06-30', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.28, trailing_return_pct: 28, average_volume: 1000000 }, { symbol: 'XLF', target_weight: 0, score: 0.22, trailing_return_pct: 22, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.28, trailing_return_pct: 28, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.28, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-09-30', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.54, trailing_return_pct: 54, average_volume: 1000000 }, { symbol: 'XLI', target_weight: 0, score: 0.3, trailing_return_pct: 30, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.54, trailing_return_pct: 54, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.54, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
          { date: '2025-12-31', rankings: [{ symbol: 'XLE', target_weight: 1, score: 0.4, trailing_return_pct: 40, average_volume: 1000000 }, { symbol: 'XLK', target_weight: 0, score: 0.39, trailing_return_pct: 39, average_volume: 1000000 }], holdings: [{ symbol: 'XLE', target_weight: 1, score: 0.4, trailing_return_pct: 40, average_volume: 1000000 }], leader: 'XLE', leader_score: 0.4, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.1 },
        ],
        equity_curve: [{ date: '2025-12-31', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 20, average_volume_participation_ratio: 1.1 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))
    await waitFor(() => expect(screen.getByText('Leadership Heatmap')).toBeTruthy())

    fireEvent.mouseEnter(screen.getByRole('button', { name: /Q2 2025/i }))
    fireEvent.click(screen.getByText('Lookback Price Change'))

    const constituentHeatmap = screen.getByTestId('strategy-constituent-heatmap')
    expect(within(constituentHeatmap).getAllByText('27.9').length).toBeGreaterThan(0)
    expect(within(constituentHeatmap).queryByText('942.1')).toBeNull()
  })

  it('refreshes holdings snapshots and reruns the strategy', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK'],
        start_date: '2020-01-02',
        end_date: '2024-12-02',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        source_status: { price_history: 'live', leader_internals: 'live-dated', holdings_snapshot_counts: { XLK: 1 }, dated_holdings_symbols: ['XLK'], sample_fallback_symbols: [] },
        current_rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [{ date: '2024-12-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] }],
        etf_internals_history: { XLK: [{ date: '2024-12-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] }] },
        observations: [{ date: '2024-12-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 }],
        equity_curve: [{ date: '2024-12-02', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 28.4, average_volume_participation_ratio: 1.12 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ refreshed: [{ symbol: 'XLK', resolved_symbol: 'XLK', rows: 76, snapshots: 1 }] }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        strategy_id: 'book_etf_cross_sectional_momentum',
        title: 'ETF Cross-Sectional Momentum',
        benchmark_symbol: 'SPY',
        universe: ['XLK'],
        start_date: '2020-01-02',
        end_date: '2024-12-02',
        rebalance_frequency: 'monthly',
        lookback_months: 12,
        top_n: 1,
        methodology: 'm',
        source_status: { price_history: 'live', leader_internals: 'live-dated', holdings_snapshot_counts: { XLK: 2 }, dated_holdings_symbols: ['XLK'], sample_fallback_symbols: [] },
        current_rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        latest_holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }],
        leader_internals: [{ date: '2024-12-02', leader_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] }],
        etf_internals_history: { XLK: [{ date: '2024-12-02', etf_symbol: 'XLK', source_mode: 'live-dated', snapshot_date: '2026-04-12', constituents: [{ symbol: 'MSFT', name: 'Microsoft', weight: 0.29, trailing_return_pct: 24.5, weighted_contribution_pct: 7.11 }] }] },
        observations: [{ date: '2024-12-02', rankings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], holdings: [{ symbol: 'XLK', target_weight: 1, score: 0.12, trailing_return_pct: 12, average_volume: 1000000 }], leader: 'XLK', leader_score: 0.12, benchmark_return_pct: null, strategy_return_pct: null, average_volume_ratio: 1.18 }],
        equity_curve: [{ date: '2024-12-02', strategy_equity: null, benchmark_equity: null, strategy_drawdown_pct: null, benchmark_drawdown_pct: null }],
        metrics: { total_return_pct: null, benchmark_return_pct: null, excess_return_pct: null, annualized_return_pct: null, max_drawdown_pct: null, benchmark_max_drawdown_pct: null, win_rate_pct: null, average_turnover_pct: 28.4, average_volume_participation_ratio: 1.12 },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<StrategyLabPanel />)

    fireEvent.click(screen.getByText('Run ETF Rotation Prototype'))
    await waitFor(() => expect(screen.getByText('Refresh holdings snapshots')).toBeTruthy())
    fireEvent.click(screen.getByText('Refresh holdings snapshots'))

    await waitFor(() => expect(screen.getByText('XLK 2')).toBeTruthy())
    expect(fetchSpy).toHaveBeenCalledTimes(3)
  })
})
