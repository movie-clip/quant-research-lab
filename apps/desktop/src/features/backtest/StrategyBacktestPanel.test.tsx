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
  trades: [],
  positions: [],
  equity_curve: [],
  total_return_pct: 12.5,
  annualized_return_pct: 12.5,
  max_drawdown_pct: -6.2,
  sharpe_ratio: 1.14,
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
})
