import { useMemo, useState } from 'react'

import { investorEconomicsBaseReason } from '../portfolio/investorEconomics'
import type { BacktestRunResponse } from '../portfolio/types'

type Props = {
  backtestResult: BacktestRunResponse | null
  onBacktestResult: (result: BacktestRunResponse) => void
}

function parseUniverse(value: string) {
  return value
    .split(',')
    .map((item) => item.trim().toUpperCase())
    .filter(Boolean)
}

function investorEconomicsHelper(status: BacktestRunResponse['investor_economics_status']) {
  if (investorEconomicsBaseReason(status)) {
    return 'Investor-performance metrics are intentionally withheld until verified total-return equivalence is available. Treat this run as workflow and dataset evidence only.'
  }
  return 'Investor-performance metrics are available on this run.'
}

export function StrategyBacktestPanel({ backtestResult, onBacktestResult }: Props) {
  const apiBase = useMemo(() => '/api', [])
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [strategyId, setStrategyId] = useState('book_trend_breakout')
  const [universe, setUniverse] = useState('ES,NQ,CL')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [initialCapital, setInitialCapital] = useState('100000')
  const [backtestLoading, setBacktestLoading] = useState(false)
  const [backtestError, setBacktestError] = useState<string | null>(null)

  const sourceSummary = useMemo(() => {
    if (!backtestResult) return null
    const items = Object.values(backtestResult.dataset_info)
    if (!items.length) return null
    const allFmp = items.every((item) => item.source === 'fmp')
    const anyProxyApproximation = items.some((item) => item.source.includes('proxy approximation'))
    const anyLocalApproximation = items.some((item) => item.source === 'local approximation')
    const anyFallback = items.some((item) => item.source === 'local-sample')
    if (allFmp) return 'Live FMP'
    if ((anyProxyApproximation || anyLocalApproximation) && anyFallback) return 'Mixed proxy + fallback'
    if (anyProxyApproximation) return 'Proxy approximation'
    if (anyLocalApproximation) return 'Local approximation'
    if (anyFallback) return 'Mixed FMP + sample'
    return 'Mixed sources'
  }, [backtestResult])
  const investorEconomicsWithheld = investorEconomicsBaseReason(backtestResult?.investor_economics_status) != null

  async function runBacktest() {
    const parsedUniverse = parseUniverse(universe)
    const capital = Number(initialCapital)

    if (!parsedUniverse.length) {
      setBacktestError('Please enter at least one symbol in the backtest universe.')
      return
    }
    if (!startDate || !endDate) {
      setBacktestError('Please provide both a start date and an end date.')
      return
    }
    if (endDate < startDate) {
      setBacktestError('End date must be on or after start date.')
      return
    }
    if (!Number.isFinite(capital) || capital <= 0) {
      setBacktestError('Initial capital must be a positive number.')
      return
    }

    setBacktestLoading(true)
    setBacktestError(null)

    try {
      const response = await fetch(`${apiBase}/backtests/run`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          strategy_id: strategyId,
          universe: parsedUniverse,
          benchmark_symbol: benchmarkSymbol,
          start_date: startDate,
          end_date: endDate,
          initial_capital: capital,
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Backtest failed')
      }
      onBacktestResult((await response.json()) as BacktestRunResponse)
    } catch (caughtError) {
      setBacktestError(caughtError instanceof Error ? caughtError.message : 'Backtest failed')
    } finally {
      setBacktestLoading(false)
    }
  }

  return (
    <article className="panel">
      <p className="panel-label">Backtest</p>
      <h2>Generic strategy backtests</h2>
      <p className="lead compact-lead">Run generic strategy backtests here. Portfolio-improvement work stays in the Workspace.</p>

      <div className="backtest-builder">
        <p className="panel-label">Strategy Backtest</p>
        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Strategy Id</span>
            <select className="path-input" value={strategyId} onChange={(event) => setStrategyId(event.target.value)}>
              <option value="book_trend_breakout">Book Trend Breakout</option>
              <option value="book_ma_filter">Book Moving Average Filter</option>
            </select>
          </label>
          <label className="field-group">
            <span className="field-label">Benchmark Symbol</span>
            <input className="path-input" value={benchmarkSymbol} onChange={(event) => setBenchmarkSymbol(event.target.value.toUpperCase())} />
          </label>
        </div>

        <label className="field-group">
          <span className="field-label">Universe</span>
          <input className="path-input" value={universe} onChange={(event) => setUniverse(event.target.value)} placeholder="ES,NQ,CL" />
        </label>

        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Start Date</span>
            <input className="path-input" type="date" value={startDate} onChange={(event) => setStartDate(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">End Date</span>
            <input className="path-input" type="date" value={endDate} onChange={(event) => setEndDate(event.target.value)} />
          </label>
        </div>

        <label className="field-group">
          <span className="field-label">Initial Capital</span>
          <input className="path-input" inputMode="decimal" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} />
        </label>

        <div className="actions">
          <button className={`primary-button${backtestLoading ? ' button-loading' : ''}`} type="button" disabled={backtestLoading} onClick={runBacktest}>
            {backtestLoading ? 'Running Backtest...' : 'Run Backtest'}
          </button>
        </div>
        {backtestError ? <p className="error">{backtestError}</p> : null}
      </div>

      {backtestResult ? (
        <section className="workspace-section">
          <div className="section-header-inline sector-list-header">
            <div>
              <p className="panel-label">Latest Strategy Run</p>
            </div>
            {sourceSummary ? <span className="backtest-source-badge">{sourceSummary}</span> : null}
          </div>
          <div className="stats">
            <div className="stat">
              <p className="stat-label">Run Id</p>
              <p className="stat-value">{backtestResult.run_id.split(':')[0]}</p>
            </div>
            <div className="stat">
              <p className="stat-label">Investor Economics</p>
              <p className="stat-value">{investorEconomicsWithheld ? 'Withheld' : 'Available'}</p>
            </div>
            <div className="stat">
              <p className="stat-label">Run Window</p>
              <p className="stat-value">{backtestResult.config.start_date} - {backtestResult.config.end_date}</p>
            </div>
            <div className="stat">
              <p className="stat-label">Benchmark</p>
              <p className="stat-value">{backtestResult.config.benchmark_symbol}</p>
            </div>
            <div className="stat">
              <p className="stat-label">Dataset Coverage</p>
              <p className="stat-value">{Object.keys(backtestResult.dataset_info).length} symbols</p>
            </div>
          </div>
          <p className="helper">{investorEconomicsHelper(backtestResult.investor_economics_status)}</p>
          {investorEconomicsWithheld ? (
            <p className="helper">Return, benchmark-relative, drawdown, and Sharpe readouts stay suppressed on this surface while withholding is active.</p>
          ) : null}
          <div className="factor-snapshot-table-wrap">
                    <div className="section-header-inline sector-list-header strategy-detail-subheader">
                      <div>
                        <p className="panel-label">Dataset Sources</p>
                        <p className="helper">Spot symbols prefer live FMP history; futures roots remain proxy or approximation paths.</p>
                      </div>
                    </div>
            <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-history-grid">
              <span>Symbol</span>
              <span>Timeframe</span>
              <span>Source</span>
              <span>Continuous</span>
              <span>Ready</span>
            </div>
            {Object.values(backtestResult.dataset_info).map((item) => (
              <div className="risk-contrib-table-grid factor-shift-data-row strategy-lab-history-grid" key={`dataset-${item.symbol}`}>
                <span className="factor-snapshot-primary">{item.symbol}</span>
                <span>{item.timeframe}</span>
                <span>{item.source}</span>
                <span>{item.continuous ? 'yes' : 'no'}</span>
                <span>{item.ready ? 'ready' : 'missing'}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </article>
  )
}
