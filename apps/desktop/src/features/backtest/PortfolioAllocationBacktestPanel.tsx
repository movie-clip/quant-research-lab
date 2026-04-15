import { FormEvent, useEffect, useMemo, useState } from 'react'
import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { PortfolioAllocationBacktestResponse, PortfolioBaselineView, PortfolioDiagnosticsComparisonRow } from '../portfolio/types'

type AllocationWeightRow = {
  symbol: string
  target_weight: string
}

type Props = {
  result: PortfolioAllocationBacktestResponse | null
  onResult: (result: PortfolioAllocationBacktestResponse) => void
  analysis: PortfolioBaselineView | null
}

type ComparisonMetricRow = {
  key: string
  label: string
  baseline: number | null
  candidate: number | null
  delta: number | null
  format: 'pct' | 'number' | 'money'
}

type DeltaTone = 'positive' | 'negative' | 'neutral'

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'n/a' : `$${value.toFixed(2)}`
}

function formatDateLabel(value: string | number | null | undefined) {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return value
  return `${month}/${day}/${year.slice(2)}`
}

function formatTooltipLabel(label: unknown) {
  return typeof label === 'string' || typeof label === 'number' ? formatDateLabel(label) : ''
}

function parseWeightRows(rows: AllocationWeightRow[]) {
  return rows
    .map((row) => ({ symbol: row.symbol.trim().toUpperCase(), target_weight: Number(row.target_weight) }))
    .filter((row) => row.symbol.length > 0)
}

function totalWeight(rows: AllocationWeightRow[]) {
  return parseWeightRows(rows).reduce((sum, row) => sum + row.target_weight, 0)
}

function formatComparisonValue(value: number | null, kind: ComparisonMetricRow['format']) {
  if (kind === 'money') return formatMoney(value)
  if (kind === 'pct') return formatPct(value)
  return formatNumber(value, 2)
}

function formatSignedComparisonValue(value: number | null, kind: ComparisonMetricRow['format']) {
  if (value == null) return 'n/a'
  if (kind === 'money') return `${value > 0 ? '+' : ''}${formatMoney(value)}`
  if (kind === 'pct') return `${value > 0 ? '+' : ''}${formatPct(value)}`
  return `${value > 0 ? '+' : ''}${formatNumber(value, 2)}`
}

function metricDeltaTone(row: ComparisonMetricRow): DeltaTone {
  if (row.delta == null || row.delta === 0) return 'neutral'
  const betterWhenHigher = new Set(['total_return', 'annualized_return', 'max_drawdown', 'sharpe', 'sortino', 'excess_return', 'information_ratio'])
  const betterWhenLower = new Set(['annualized_volatility', 'downside_volatility', 'tracking_error', 'turnover', 'cost'])
  if (betterWhenHigher.has(row.key)) return row.delta > 0 ? 'positive' : 'negative'
  if (betterWhenLower.has(row.key)) return row.delta < 0 ? 'positive' : 'negative'
  return row.delta > 0 ? 'positive' : 'negative'
}

function deltaToneClass(tone: DeltaTone) {
  if (tone === 'positive') return 'positive-text'
  if (tone === 'negative') return 'negative-text'
  return 'neutral-text'
}

function totalTone(total: number, enabled = true): DeltaTone {
  if (!enabled) return 'neutral'
  if (Math.abs(total - 1) <= 0.01) return 'positive'
  if (Math.abs(total - 1) <= 0.03) return 'neutral'
  return 'negative'
}

function sectionCardClass(kind: 'baseline' | 'candidate') {
  return `backtest-allocation-card ${kind === 'baseline' ? 'backtest-allocation-card-baseline' : 'backtest-allocation-card-candidate'}`
}

function diagnosticsValueKind(key: string): ComparisonMetricRow['format'] {
  if (key.includes('hhi') || key.includes('beta') || key.includes('correlation')) return 'number'
  return 'pct'
}

function normalizeRows(rows: AllocationWeightRow[]) {
  const parsed = parseWeightRows(rows)
  const total = parsed.reduce((sum, row) => sum + row.target_weight, 0)
  if (!parsed.length || total === 0) return rows
  return parsed.map((row) => ({ symbol: row.symbol, target_weight: (row.target_weight / total).toFixed(4) }))
}

function deriveBaselineRows(analysis: PortfolioBaselineView | null): AllocationWeightRow[] {
  if (!analysis?.snapshot.positions?.length) return []
  const total = analysis.snapshot.positions.reduce((sum, position) => sum + position.market_value, 0)
  if (!total) return []
  return analysis.snapshot.positions
    .map((position) => ({ symbol: position.symbol, target_weight: (position.market_value / total).toFixed(4), market_value: position.market_value }))
    .sort((left, right) => right.market_value - left.market_value)
    .map(({ symbol, target_weight }) => ({ symbol, target_weight }))
}

function BacktestCurve({ result }: { result: PortfolioAllocationBacktestResponse }) {
  const chartData = useMemo(() => {
    const referenceByDate = new Map((result.reference_result?.equity_curve ?? []).map((point) => [point.date, point]))
    return result.candidate_result.equity_curve.map((point) => ({
      date: point.date,
      candidateEquity: point.equity,
      referenceEquity: referenceByDate.get(point.date)?.equity ?? null,
      candidateDrawdown: point.drawdown_pct,
      referenceDrawdown: referenceByDate.get(point.date)?.drawdown_pct ?? null,
    }))
  }, [result])

  return (
    <div className="split-grid dashboard-bottom-grid">
      <section>
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Equity</p></div></div>
        <div className="line-chart-panel compact-chart-panel">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={220}>
            <AreaChart data={chartData} margin={{ top: 18, right: 16, left: 8, bottom: 8 }}>
              <defs>
                <linearGradient id="allocationCandidateFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#d85a51" stopOpacity={0.24} />
                  <stop offset="100%" stopColor="#d85a51" stopOpacity={0.03} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="rgba(70, 82, 98, 0.16)" strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" tickFormatter={formatDateLabel} />
              <YAxis tick={{ fill: '#748295', fontSize: 10 }} width={56} tickFormatter={(value) => `$${Number(value).toFixed(0)}`} />
              <Tooltip formatter={(value) => formatMoney(typeof value === 'number' ? value : null)} labelFormatter={formatTooltipLabel} />
              {result.reference_result ? <Line type="monotone" dataKey="referenceEquity" name="Baseline" stroke="#6c88a6" strokeWidth={1.8} dot={false} isAnimationActive={false} /> : null}
              <Area type="monotone" dataKey="candidateEquity" name="Candidate" stroke="#d85a51" fill="url(#allocationCandidateFill)" strokeWidth={2.2} dot={false} isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </section>
      <section>
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Drawdown</p></div></div>
        <div className="line-chart-panel compact-chart-panel">
          <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={220}>
            <LineChart data={chartData} margin={{ top: 18, right: 16, left: 8, bottom: 8 }}>
              <CartesianGrid stroke="rgba(70, 82, 98, 0.16)" strokeDasharray="3 3" />
              <ReferenceLine y={0} stroke="rgba(156, 169, 184, 0.34)" strokeDasharray="5 5" />
              <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" tickFormatter={formatDateLabel} />
              <YAxis tick={{ fill: '#748295', fontSize: 10 }} width={48} />
              <Tooltip formatter={(value) => formatPct(typeof value === 'number' ? value : null)} labelFormatter={formatTooltipLabel} />
              {result.reference_result ? <Line type="monotone" dataKey="referenceDrawdown" name="Baseline" stroke="#6c88a6" strokeWidth={1.8} dot={false} isAnimationActive={false} /> : null}
              <Line type="monotone" dataKey="candidateDrawdown" name="Candidate" stroke="#d85a51" strokeWidth={2.0} dot={false} isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
    </div>
  )
}

function ComparisonTable({ rows }: { rows: ComparisonMetricRow[] }) {
  return (
    <div className="factor-snapshot-table-wrap">
      <div className="risk-contrib-table-grid factor-snapshot-header-row">
        <span>Metric</span>
        <span>Baseline</span>
        <span>Candidate</span>
        <span>Delta</span>
      </div>
      {rows.map((row) => (
        <div className={`risk-contrib-table-grid factor-shift-data-row comparison-data-row comparison-tone-${metricDeltaTone(row)}`} key={row.key}>
          <span className="factor-snapshot-primary">{row.label}</span>
          <span>{formatComparisonValue(row.baseline, row.format)}</span>
          <span>{formatComparisonValue(row.candidate, row.format)}</span>
          <span className={deltaToneClass(metricDeltaTone(row))}>{formatSignedComparisonValue(row.delta, row.format)}</span>
        </div>
      ))}
    </div>
  )
}

function DiagnosticsComparisonTable({ title, rows }: { title: string; rows: PortfolioDiagnosticsComparisonRow[] }) {
  return (
    <section>
      <div className="section-header-inline sector-list-header"><div><p className="panel-label">{title}</p></div></div>
      <ComparisonTable rows={rows.map((row) => ({
        key: row.key,
        label: row.label,
        baseline: row.baseline_value,
        candidate: row.candidate_value,
        delta: row.delta_value,
        format: diagnosticsValueKind(row.key),
      }))} />
    </section>
  )
}

export function PortfolioAllocationBacktestPanel({ result, onResult, analysis }: Props) {
  const apiBase = useMemo(() => '/api', [])
  const [portfolioName, setPortfolioName] = useState('Candidate')
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [startDate, setStartDate] = useState('2024-01-01')
  const [endDate, setEndDate] = useState('2024-12-31')
  const [initialCapital, setInitialCapital] = useState('100000')
  const [rebalanceFrequency, setRebalanceFrequency] = useState<'none' | 'monthly' | 'quarterly'>('monthly')
  const [commissionBps, setCommissionBps] = useState('0')
  const [slippageBps, setSlippageBps] = useState('0')
  const [driftTolerancePct, setDriftTolerancePct] = useState('')
  const [candidateWeights, setCandidateWeights] = useState<AllocationWeightRow[]>([{ symbol: 'SPY', target_weight: '0.60' }, { symbol: 'TLT', target_weight: '0.40' }])
  const [referenceWeights, setReferenceWeights] = useState<AllocationWeightRow[]>([{ symbol: 'SPY', target_weight: '1.00' }])
  const [includeReference, setIncludeReference] = useState(true)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const candidateWeightTotal = totalWeight(candidateWeights)
  const referenceWeightTotal = totalWeight(referenceWeights)
  const baselineRows = useMemo(() => deriveBaselineRows(analysis), [analysis])
  const importedPortfolioValue = analysis?.overview.total_market_value ?? null
  const importedPositionsCount = analysis?.snapshot.positions.length ?? 0

  useEffect(() => {
    if (!baselineRows.length) return
    setReferenceWeights((current) => (current.length === 1 && current[0]?.symbol === 'SPY' && current[0]?.target_weight === '1.00') ? baselineRows : current)
  }, [baselineRows])

  function updateWeightRow(kind: 'candidate' | 'reference', index: number, key: keyof AllocationWeightRow, value: string) {
    const setter = kind === 'candidate' ? setCandidateWeights : setReferenceWeights
    setter((current) => current.map((row, rowIndex) => rowIndex === index ? { ...row, [key]: value } : row))
  }

  function addWeightRow(kind: 'candidate' | 'reference') {
    const setter = kind === 'candidate' ? setCandidateWeights : setReferenceWeights
    setter((current) => [...current, { symbol: '', target_weight: '' }])
  }

  function removeWeightRow(kind: 'candidate' | 'reference', index: number) {
    const setter = kind === 'candidate' ? setCandidateWeights : setReferenceWeights
    setter((current) => current.filter((_, rowIndex) => rowIndex !== index))
  }

  async function runAllocationBacktest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const capital = Number(initialCapital)
    const candidate = parseWeightRows(candidateWeights)
    const reference = parseWeightRows(referenceWeights)
    if (!candidate.length) {
      setError('Enter at least one candidate weight.')
      return
    }
    if (candidate.some((row) => !Number.isFinite(row.target_weight) || row.target_weight < 0)) {
      setError('Candidate weights must be non-negative numbers.')
      return
    }
    if (Math.abs(candidateWeightTotal - 1) > 0.01) {
      setError('Candidate weights must sum to approximately 1.0.')
      return
    }
    if (includeReference) {
      if (!reference.length) {
        setError('Enter at least one baseline weight or disable comparison.')
        return
      }
      if (reference.some((row) => !Number.isFinite(row.target_weight) || row.target_weight < 0)) {
        setError('Baseline weights must be non-negative numbers.')
        return
      }
      if (Math.abs(referenceWeightTotal - 1) > 0.01) {
        setError('Baseline weights must sum to approximately 1.0.')
        return
      }
    }
    if (endDate < startDate) {
      setError('End date must be on or after start date.')
      return
    }
    if (!Number.isFinite(capital) || capital <= 0) {
      setError('Initial capital must be a positive number.')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await fetch(`${apiBase}/backtests/portfolio-allocation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          portfolio_name: portfolioName,
          weights: candidate,
          reference_weights: includeReference ? reference : null,
          benchmark_symbol: benchmarkSymbol,
          start_date: startDate,
          end_date: endDate,
          initial_capital: capital,
          rebalance_frequency: rebalanceFrequency,
          commission_bps: Number(commissionBps) || 0,
          slippage_bps: Number(slippageBps) || 0,
          drift_tolerance_pct: driftTolerancePct ? Number(driftTolerancePct) : null,
          price_basis: 'adjusted_close',
          execution_price_field: 'close',
          execution_lag_days: 1,
          base_currency: 'USD',
        }),
      })
      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Portfolio improvement replay failed')
      }
      onResult((await response.json()) as PortfolioAllocationBacktestResponse)
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Portfolio improvement replay failed')
    } finally {
      setLoading(false)
    }
  }

  const summaryRows: ComparisonMetricRow[] = result?.reference_result ? [
    { key: 'total_return', label: 'Total Return', baseline: result.reference_result.metrics.total_return_pct, candidate: result.candidate_result.metrics.total_return_pct, delta: result.comparison?.total_return_diff_pct ?? null, format: 'pct' },
    { key: 'annualized_return', label: 'Annualized Return', baseline: result.reference_result.metrics.annualized_return_pct, candidate: result.candidate_result.metrics.annualized_return_pct, delta: result.comparison?.annualized_return_diff_pct ?? null, format: 'pct' },
    { key: 'annualized_volatility', label: 'Annualized Volatility', baseline: result.reference_result.metrics.annualized_volatility_pct, candidate: result.candidate_result.metrics.annualized_volatility_pct, delta: result.comparison?.annualized_volatility_diff_pct ?? null, format: 'pct' },
    { key: 'downside_volatility', label: 'Downside Volatility', baseline: result.reference_result.metrics.downside_volatility_pct, candidate: result.candidate_result.metrics.downside_volatility_pct, delta: result.comparison?.downside_volatility_diff_pct ?? null, format: 'pct' },
    { key: 'max_drawdown', label: 'Max Drawdown', baseline: result.reference_result.metrics.max_drawdown_pct, candidate: result.candidate_result.metrics.max_drawdown_pct, delta: result.comparison?.max_drawdown_diff_pct ?? null, format: 'pct' },
    { key: 'sharpe', label: 'Sharpe Ratio', baseline: result.reference_result.metrics.sharpe_ratio, candidate: result.candidate_result.metrics.sharpe_ratio, delta: result.comparison?.sharpe_diff ?? null, format: 'number' },
    { key: 'sortino', label: 'Sortino Ratio', baseline: result.reference_result.metrics.sortino_ratio, candidate: result.candidate_result.metrics.sortino_ratio, delta: result.comparison?.sortino_diff ?? null, format: 'number' },
    { key: 'benchmark_return', label: 'Benchmark Return', baseline: result.reference_result.metrics.benchmark_return_pct, candidate: result.candidate_result.metrics.benchmark_return_pct, delta: 0, format: 'pct' },
    { key: 'excess_return', label: 'Excess Return', baseline: result.reference_result.metrics.excess_return_pct, candidate: result.candidate_result.metrics.excess_return_pct, delta: result.comparison?.excess_return_diff_pct ?? null, format: 'pct' },
    { key: 'tracking_error', label: 'Tracking Error', baseline: result.reference_result.metrics.tracking_error_pct, candidate: result.candidate_result.metrics.tracking_error_pct, delta: result.comparison?.tracking_error_diff_pct ?? null, format: 'pct' },
    { key: 'information_ratio', label: 'Information Ratio', baseline: result.reference_result.metrics.information_ratio, candidate: result.candidate_result.metrics.information_ratio, delta: result.comparison?.information_ratio_diff ?? null, format: 'number' },
    { key: 'beta', label: 'Beta vs Benchmark', baseline: result.reference_result.metrics.beta_vs_benchmark, candidate: result.candidate_result.metrics.beta_vs_benchmark, delta: result.comparison?.beta_diff ?? null, format: 'number' },
    { key: 'correlation', label: 'Correlation vs Benchmark', baseline: result.reference_result.metrics.correlation_vs_benchmark, candidate: result.candidate_result.metrics.correlation_vs_benchmark, delta: result.comparison?.correlation_diff ?? null, format: 'number' },
    { key: 'turnover', label: 'Total Turnover', baseline: result.reference_result.metrics.total_turnover_pct, candidate: result.candidate_result.metrics.total_turnover_pct, delta: result.comparison?.total_turnover_diff_pct ?? null, format: 'pct' },
    { key: 'cost', label: 'Total Cost Paid', baseline: result.reference_result.metrics.total_cost_paid, candidate: result.candidate_result.metrics.total_cost_paid, delta: result.comparison?.total_cost_diff ?? null, format: 'money' },
  ] : []

  return (
    <section className="workspace-section">
      <p className="panel-label">Portfolio Improvement Workspace</p>
      <div className="dashboard-summary compact-summary-grid backtest-workspace-summary">
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card">
          <p className="stat-label">Current Import</p>
          <p className="summary-value">{formatMoney(importedPortfolioValue)}</p>
          <p className="helper">{analysis ? `${importedPositionsCount} imported holdings ready for baseline seeding` : 'Import a portfolio to seed the baseline automatically'}</p>
        </div>
        <div className={`summary-card metric-card backtest-summary-card ${totalTone(referenceWeightTotal, includeReference) === 'positive' ? 'metric-card-cool' : totalTone(referenceWeightTotal, includeReference) === 'negative' ? 'metric-card-hot' : 'metric-card-neutral'}`}>
          <p className="stat-label">Baseline Total</p>
          <p className={`summary-value ${deltaToneClass(totalTone(referenceWeightTotal, includeReference))}`}>{formatNumber(referenceWeightTotal, 2)}</p>
          <p className="helper">{includeReference ? `${referenceWeights.length} rows / comparison enabled` : 'Comparison disabled'}</p>
        </div>
        <div className={`summary-card metric-card backtest-summary-card ${totalTone(candidateWeightTotal) === 'positive' ? 'metric-card-cool' : totalTone(candidateWeightTotal) === 'negative' ? 'metric-card-hot' : 'metric-card-neutral'}`}>
          <p className="stat-label">Candidate Total</p>
          <p className={`summary-value ${deltaToneClass(totalTone(candidateWeightTotal))}`}>{formatNumber(candidateWeightTotal, 2)}</p>
          <p className="helper">{candidateWeights.length} rows / target should be 1.00</p>
        </div>
        <div className="summary-card metric-card metric-card-warm backtest-summary-card">
          <p className="stat-label">Replay Setup</p>
          <p className="summary-value">{rebalanceFrequency}</p>
          <p className="helper">{benchmarkSymbol} benchmark / {formatMoney(Number(initialCapital) || null)} initial capital</p>
        </div>
      </div>

      <form className="import-form" onSubmit={runAllocationBacktest}>
        <div className="split-grid compact-split-grid backtest-config-grid">
          <label className="field-group">
            <span className="field-label">Portfolio Name</span>
            <input className="path-input" value={portfolioName} onChange={(event) => setPortfolioName(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Benchmark Symbol</span>
            <input className="path-input" value={benchmarkSymbol} onChange={(event) => setBenchmarkSymbol(event.target.value.toUpperCase())} />
          </label>
        </div>
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
        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Initial Capital</span>
            <input className="path-input" inputMode="decimal" value={initialCapital} onChange={(event) => setInitialCapital(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Rebalance Frequency</span>
            <select className="path-input" value={rebalanceFrequency} onChange={(event) => setRebalanceFrequency(event.target.value as 'none' | 'monthly' | 'quarterly')}>
              <option value="none">None</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
            </select>
          </label>
        </div>
        <div className="split-grid compact-split-grid">
          <label className="field-group">
            <span className="field-label">Commission Bps</span>
            <input className="path-input" inputMode="decimal" value={commissionBps} onChange={(event) => setCommissionBps(event.target.value)} />
          </label>
          <label className="field-group">
            <span className="field-label">Slippage Bps</span>
            <input className="path-input" inputMode="decimal" value={slippageBps} onChange={(event) => setSlippageBps(event.target.value)} />
          </label>
        </div>
        <label className="field-group">
          <span className="field-label">Drift Tolerance Pct</span>
          <input className="path-input" inputMode="decimal" value={driftTolerancePct} onChange={(event) => setDriftTolerancePct(event.target.value)} placeholder="Optional" />
        </label>

        <div className="split-grid dashboard-bottom-grid">
          <section className={sectionCardClass('baseline')}>
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Baseline Portfolio</p></div><div className="toggle-group"><p className={`helper ${deltaToneClass(totalTone(referenceWeightTotal, includeReference))}`}>Total {formatNumber(referenceWeightTotal, 2)}</p><button className={`toggle-chip${includeReference ? ' active' : ''}`} onClick={() => setIncludeReference((value) => !value)} type="button">Compare</button><button className="toggle-chip" onClick={() => setReferenceWeights(baselineRows)} type="button">Use Current Portfolio</button><button className="toggle-chip" disabled={!includeReference} onClick={() => addWeightRow('reference')} type="button">Add Row</button></div></div>
            <p className="helper backtest-section-helper">Use the imported book as the before-state or define a custom baseline sleeve.</p>
            <div className="factor-snapshot-table-wrap">
              {referenceWeights.map((row, index) => (
                <div className="allocation-weight-row" key={`reference-${index}`}>
                  <input aria-label={`reference-symbol-${index}`} className="path-input" disabled={!includeReference} value={row.symbol} onChange={(event) => updateWeightRow('reference', index, 'symbol', event.target.value)} placeholder="Symbol" />
                  <input aria-label={`reference-weight-${index}`} className="path-input" disabled={!includeReference} value={row.target_weight} onChange={(event) => updateWeightRow('reference', index, 'target_weight', event.target.value)} placeholder="1.00" />
                  <span className={`allocation-weight-badge ${deltaToneClass(totalTone(Number(row.target_weight) || 0, includeReference))}`}>{formatPct((Number(row.target_weight) || 0) * 100)}</span>
                  <button className="toggle-chip" disabled={!includeReference} onClick={() => removeWeightRow('reference', index)} type="button">Remove</button>
                </div>
              ))}
            </div>
          </section>
          <section className={sectionCardClass('candidate')}>
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Candidate Portfolio Builder</p></div><div className="toggle-group"><p className={`helper ${deltaToneClass(totalTone(candidateWeightTotal))}`}>Total {formatNumber(candidateWeightTotal, 2)}</p><button className="toggle-chip" onClick={() => setCandidateWeights(referenceWeights)} type="button">Copy Baseline to Candidate</button><button className="toggle-chip" onClick={() => setCandidateWeights(normalizeRows(candidateWeights))} type="button">Normalize</button><button className="toggle-chip" onClick={() => setCandidateWeights([])} type="button">Clear</button><button className="toggle-chip" onClick={() => addWeightRow('candidate')} type="button">Add Row</button></div></div>
            <p className="helper backtest-section-helper">Build the after-state and keep the total close to 1.00 before running the replay.</p>
            <div className="factor-snapshot-table-wrap">
              {candidateWeights.map((row, index) => (
                <div className="allocation-weight-row" key={`candidate-${index}`}>
                  <input aria-label={`candidate-symbol-${index}`} className="path-input" value={row.symbol} onChange={(event) => updateWeightRow('candidate', index, 'symbol', event.target.value)} placeholder="Symbol" />
                  <input aria-label={`candidate-weight-${index}`} className="path-input" value={row.target_weight} onChange={(event) => updateWeightRow('candidate', index, 'target_weight', event.target.value)} placeholder="0.50" />
                  <span className={`allocation-weight-badge ${deltaToneClass(totalTone(Number(row.target_weight) || 0))}`}>{formatPct((Number(row.target_weight) || 0) * 100)}</span>
                  <button className="toggle-chip" onClick={() => removeWeightRow('candidate', index)} type="button">Remove</button>
                </div>
              ))}
            </div>
          </section>
        </div>

        <div className="actions backtest-actions">
          <button className="primary-button" disabled={loading} type="submit">{loading ? 'Running Portfolio Improvement Replay...' : 'Run Portfolio Improvement Replay'}</button>
          <p className="helper">Baseline and candidate weights should each sum to 1.00 when comparison is enabled.</p>
        </div>
        {error ? <p className="error">{error}</p> : null}
      </form>

      {result ? (
        <>
          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Replay Summary</p></div><p className="helper">Baseline / candidate / delta</p></div>
            {summaryRows.length ? <ComparisonTable rows={summaryRows} /> : <div className="empty-state-panel compact-empty-state"><p className="empty-state-title">Run with baseline comparison enabled to view before/after replay metrics.</p></div>}
          </section>

          <BacktestCurve result={result} />

          {result.diagnostics_comparison ? (
            <section className="dashboard-bottom-grid">
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Before / After Diagnostics</p></div><p className="helper">{result.candidate_diagnostics?.provenance.note ?? 'Diagnostics compare synthetic replay snapshots against historical market-data inputs.'}</p></div>
              <div className="split-grid dashboard-bottom-grid">
                <DiagnosticsComparisonTable title="Factor Exposure Change" rows={result.diagnostics_comparison.factor_exposure_changes} />
                <DiagnosticsComparisonTable title="Volatility / Drawdown Change" rows={result.diagnostics_comparison.volatility_changes} />
              </div>
              <div className="split-grid dashboard-bottom-grid">
                <DiagnosticsComparisonTable title="Risk Contribution Change" rows={result.diagnostics_comparison.risk_contribution_changes} />
                <DiagnosticsComparisonTable title="Concentration Change" rows={result.diagnostics_comparison.concentration_changes} />
              </div>
              <DiagnosticsComparisonTable title="Stress Scenario Change" rows={result.diagnostics_comparison.stress_scenario_changes} />
            </section>
          ) : null}

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Implementation Details</p></div><p className="helper">{result.candidate_result.status} / {result.candidate_result.assumptions.calendar_policy}</p></div>
            <div className="dashboard-summary compact-summary-grid">
              <div className="summary-card"><p className="stat-label">Price Basis</p><p className="summary-value">{result.candidate_result.assumptions.price_basis}</p></div>
              <div className="summary-card"><p className="stat-label">Execution Field</p><p className="summary-value">{result.candidate_result.assumptions.execution_price_field}</p></div>
              <div className="summary-card"><p className="stat-label">Execution Lag</p><p className="summary-value">{formatNumber(result.candidate_result.assumptions.execution_lag_days, 0)}</p></div>
              <div className="summary-card"><p className="stat-label">Tax Treatment</p><p className="summary-value">{result.candidate_result.assumptions.tax_treatment}</p></div>
              <div className="summary-card"><p className="stat-label">Fractional Shares</p><p className="summary-value">{result.candidate_result.assumptions.fractional_shares ? 'true' : 'false'}</p></div>
              <div className="summary-card"><p className="stat-label">Base Currency</p><p className="summary-value">{result.candidate_result.assumptions.investor_base_currency ?? 'n/a'}</p></div>
            </div>
          </section>

          <div className="split-grid dashboard-bottom-grid">
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Starting Weights</p></div></div>
              <div className="list-table">{result.candidate_result.starting_weights.map((row) => <div className="list-row" key={`starting-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
            </section>
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Ending Weights</p></div></div>
              <div className="list-table">{result.candidate_result.ending_weights.map((row) => <div className="list-row" key={`ending-${row.symbol}`}><span>{row.symbol}</span><span>{formatPct(row.target_weight * 100)}</span></div>)}</div>
            </section>
          </div>

          <div className="split-grid dashboard-bottom-grid">
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Instrument Metadata</p></div></div>
              <div className="list-table">{result.candidate_result.instrument_metadata.map((item) => <div className="list-row list-row-wide" key={`meta-${item.symbol}`}><span>{item.symbol}</span><span>{item.trading_currency ?? 'n/a'}</span><span>{item.instrument_base_currency ?? 'n/a'}</span><span>{item.currency_hedged == null ? 'n/a' : String(item.currency_hedged)}</span><span>{item.distribution_policy}</span></div>)}</div>
            </section>
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Rebalance Events</p></div></div>
              <div className="list-table">{result.candidate_result.rebalance_events.length ? result.candidate_result.rebalance_events.map((row) => <div className="list-row list-row-wide" key={`rebalance-${row.execution_date}`}><span>{row.decision_date}</span><span>{row.execution_date}</span><span>{formatPct(row.turnover_pct)}</span><span>{formatMoney(row.total_cost)}</span></div>) : <div className="list-row"><span>No rebalances</span><span>n/a</span></div>}</div>
            </section>
          </div>

          <section className="dashboard-bottom-grid">
            <div className="section-header-inline sector-list-header"><div><p className="panel-label">Trade Log</p></div><p className="helper">Showing first 12 candidate trades.</p></div>
            <div className="list-table">{result.candidate_result.trades.slice(0, 12).map((trade, index) => <div className="list-row list-row-wide" key={`${trade.symbol}-${trade.date}-${index}`}><span>{trade.date}</span><span>{trade.action}</span><span>{trade.symbol}</span><span>{formatNumber(trade.quantity, 4)}</span><span>{formatMoney(trade.traded_notional)}</span><span>{formatMoney(trade.total_cost)}</span></div>)}</div>
          </section>
        </>
      ) : null}
    </section>
  )
}
