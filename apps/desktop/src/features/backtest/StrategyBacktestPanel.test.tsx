import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { BacktestRunResponse } from '../portfolio/types'
import { StrategyBacktestPanel } from './StrategyBacktestPanel'

const backtestResult: BacktestRunResponse = {
  run_id: 'run-1:book_trend_breakout',
  config: {
    strategy: {
      strategy_id: 'book_trend_breakout',
      name: 'Book Trend Breakout',
      description: null,
      timeframe: 'daily',
      side: 'long_only',
      universe: ['ES', 'NQ'],
      parameters: [],
      tags: [],
    },
    benchmark_symbol: 'SPY',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    initial_capital: 100000,
    base_currency: 'USD',
    slippage_bps: 0,
    commission_per_contract: 0,
    rebalance_frequency: 'monthly',
    use_continuous_contracts: false,
    continuous_series: null,
  },
  dataset_info: {
    ES: { symbol: 'ES', timeframe: 'daily', source: 'fmp', continuous: false, ready: true },
    NQ: { symbol: 'NQ', timeframe: 'daily', source: 'local approximation', continuous: false, ready: true },
  },
  investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
  trades: [],
  positions: [],
  equity_curve: [{ date: '2024-01-02', equity: null, cash: 100000, gross_exposure: 50000, net_exposure: 50000, drawdown_pct: null }],
  total_return_pct: null,
  annualized_return_pct: null,
  max_drawdown_pct: null,
  sharpe_ratio: null,
  overlay_preview: null,
}

describe('StrategyBacktestPanel', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('keeps generic backtest content inside the dedicated tab', () => {
    render(<StrategyBacktestPanel backtestResult={backtestResult} onBacktestResult={() => {}} />)

    expect(screen.getByText('Backtest')).toBeTruthy()
    expect(screen.getByText('Generic strategy backtests')).toBeTruthy()
    expect(screen.getByText('Run generic strategy backtests here. Portfolio-improvement work stays in the Workspace.')).toBeTruthy()
    expect(screen.getByText('Strategy Backtest')).toBeTruthy()
    expect(screen.getByText('Latest Strategy Run')).toBeTruthy()
    expect(screen.queryByText('Portfolio Improvement Workspace')).toBeNull()
    expect(screen.queryByText('Monitoring')).toBeNull()
  })

  it('submits a generic strategy backtest request', async () => {
    const onBacktestResult = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => backtestResult })
    vi.stubGlobal('fetch', fetchMock)

    render(<StrategyBacktestPanel backtestResult={null} onBacktestResult={onBacktestResult} />)

    fireEvent.click(screen.getAllByText('Run Backtest')[0] as HTMLButtonElement)

    await waitFor(() => expect(onBacktestResult).toHaveBeenCalledWith(backtestResult))
    const body = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))
    expect(body.strategy_id).toBe('book_trend_breakout')
    expect(body.universe).toEqual(['ES', 'NQ', 'CL'])
  })

  it('reframes withheld runs around workflow metadata instead of investor-performance output', () => {
    render(<StrategyBacktestPanel backtestResult={backtestResult} onBacktestResult={() => {}} />)

    expect(screen.getByText('Investor-performance metrics are intentionally withheld until verified total-return equivalence is available. Treat this run as workflow and dataset evidence only.')).toBeTruthy()
    expect(screen.getByText('Return, benchmark-relative, drawdown, and Sharpe readouts stay suppressed on this surface while withholding is active.')).toBeTruthy()
    expect(screen.getByText('Withheld')).toBeTruthy()
    expect(screen.getByText('Run Window')).toBeTruthy()
    expect(screen.getByText('2024-01-01 - 2024-12-31')).toBeTruthy()
    expect(screen.getByText('Dataset Coverage')).toBeTruthy()
    expect(screen.getByText('2 symbols')).toBeTruthy()
    expect(screen.queryByText('Total Return')).toBeNull()
    expect(screen.queryByText('Max Drawdown')).toBeNull()
    expect(screen.queryByText('Sharpe')).toBeNull()
  })
})
