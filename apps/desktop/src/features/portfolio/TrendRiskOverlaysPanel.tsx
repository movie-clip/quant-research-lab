import { useMemo } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TooltipContentProps } from 'recharts/types/component/Tooltip'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

import type { DiagnosticsEngineResponse } from './types'

type OverlayTone = 'hot' | 'warm' | 'cool' | 'neutral'

type OverlayDriver = {
  label: string
  value: string
  tone: OverlayTone
  detail: string
}

const RECENT_HISTORY_POINTS = 8

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatPercentile(value: number | null | undefined) {
  return value == null ? 'n/a' : `${(value * 100).toFixed(0)}%`
}

function formatDateLabel(value: string | number | null | undefined) {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return value
  return `${month}/${day}/${year.slice(2)}`
}

function formatAxisPct(value: number | string) {
  return `${Number(value).toFixed(0)}%`
}

function metricCardClass(tone: OverlayTone) {
  return `summary-card metric-card metric-card-${tone}`
}

function toneFromConfidence(value: string | null | undefined): OverlayTone {
  if (!value) return 'neutral'
  if (value === 'high') return 'cool'
  if (value === 'medium') return 'warm'
  return 'hot'
}

function toneFromDrawdown(value: number | null | undefined): OverlayTone {
  if (value == null) return 'neutral'
  if (value <= -10) return 'hot'
  if (value <= -4) return 'warm'
  return 'cool'
}

function toneFromTrackingError(value: number | null | undefined): OverlayTone {
  if (value == null) return 'neutral'
  if (value >= 10) return 'hot'
  if (value >= 5) return 'warm'
  return 'cool'
}

function toneFromVolPercentile(value: number | null | undefined): OverlayTone {
  if (value == null) return 'neutral'
  if (value >= 0.8) return 'hot'
  if (value >= 0.6) return 'warm'
  if (value <= 0.35) return 'cool'
  return 'neutral'
}

function hasSeriesValue(data: Array<Record<string, number | string | null | undefined>>, key: string) {
  return data.some((point) => typeof point[key] === 'number' && Number.isFinite(point[key] as number))
}

function overlayStatusLabel(result: DiagnosticsEngineResponse | null) {
  if (!result) return 'Waiting for diagnostics input'
  if (!result.availability.historical_sections_available) return 'Unavailable'
  if (result.model_reliability.status !== 'ok') return 'Partial'
  return 'Live'
}

function overlayStateNote(result: DiagnosticsEngineResponse | null) {
  if (!result) return 'Import a portfolio from the Dashboard to inspect trend and risk overlays.'
  if (!result.availability.historical_sections_available) {
    return result.availability.note ?? 'Overlay analysis requires historical diagnostics support and is not approximated from a snapshot alone.'
  }
  if (result.model_reliability.status !== 'ok') {
    return `Overlay interpretation is partial because model status is ${result.model_reliability.status}.`
  }
  return 'Overlay analysis is read-only and observational; no execution or workflow actions are attached.'
}

function OverlayTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null
  const rows = payload.filter((item) => item.value != null)
  if (!rows.length) return null

  return (
    <div className="chart-tooltip-card">
      <p className="chart-tooltip-date">{formatDateLabel(label)}</p>
      {rows.map((item) => {
        const key = typeof item.name === 'string' ? item.name : String(item.name)
        return (
          <div className="chart-tooltip-row" key={key}>
            <span className="chart-tooltip-label">
              <span className="chart-tooltip-swatch" style={{ backgroundColor: item.color ?? '#748295' }} />
              {key}
            </span>
            <span>{typeof item.value === 'number' ? item.value.toFixed(2) : String(item.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

export function TrendRiskOverlaysPanel({ result }: { result: DiagnosticsEngineResponse | null }) {
  const overlayStatus = overlayStatusLabel(result)
  const stateNote = overlayStateNote(result)

  const recentHistory = useMemo(() => {
    if (!result) return []
    return result.volatility_regime.rolling_series.slice(-RECENT_HISTORY_POINTS)
  }, [result])

  const explanationDrivers = useMemo<OverlayDriver[]>(() => {
    if (!result) return []

    return [
      {
        label: 'Regime Confidence',
        value: result.volatility_regime.regime.confidence,
        tone: toneFromConfidence(result.volatility_regime.regime.confidence),
        detail: `Regime ${result.volatility_regime.regime.label}`,
      },
      {
        label: 'Current Drawdown',
        value: formatPct(result.volatility_regime.snapshot.current_drawdown_pct),
        tone: toneFromDrawdown(result.volatility_regime.snapshot.current_drawdown_pct),
        detail: `Max drawdown ${formatPct(result.volatility_regime.snapshot.max_drawdown_pct)}`,
      },
      {
        label: 'Tracking Error',
        value: formatPct(result.volatility_regime.snapshot.tracking_error_20d),
        tone: toneFromTrackingError(result.volatility_regime.snapshot.tracking_error_20d),
        detail: `Benchmark ${result.relative_risk.benchmark_symbol}`,
      },
      {
        label: '20d Vol Percentile',
        value: formatPercentile(result.volatility_regime.snapshot.current_20d_vol_percentile),
        tone: toneFromVolPercentile(result.volatility_regime.snapshot.current_20d_vol_percentile),
        detail: `Vol ratio 20/60 ${formatNumber(result.volatility_regime.snapshot.vol_ratio_20_60, 2)}`,
      },
    ]
  }, [result])

  if (!result) {
    return (
      <article className="panel">
        <p className="panel-label">Trend / Risk Overlays</p>
        <h2>Overlay analysis</h2>
        <p className="lead compact-lead">Read-only regime and overlay diagnostics for the current portfolio state.</p>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Overlay diagnostics are waiting for a portfolio.</p>
          <p className="helper">{stateNote}</p>
        </div>
      </article>
    )
  }

  const historyRenderable = recentHistory.length > 1 && (hasSeriesValue(recentHistory, 'realized_vol_20d') || hasSeriesValue(recentHistory, 'drawdown_pct'))
  const hasPartialState = result.model_reliability.status !== 'ok'

  return (
    <article className="panel">
      <section className="dashboard-quant-header-shell overlay-panel-shell" data-testid="trend-risk-overlays-panel">
        <div className="section-header-inline dashboard-quant-header-row">
          <div className="dashboard-quant-header-copy">
            <p className="panel-label">Trend / Risk Overlays</p>
            <h2>Overlay analysis</h2>
            <p className="helper">Top-line regime, component states, explanation drivers, and recent context for the first overlay-analysis surface.</p>
          </div>
          <div className="tab-bar dashboard-meta-row-quant diagnostics-provenance-strip">
            <span className="backtest-source-badge">Status {overlayStatus}</span>
            <span className="backtest-source-badge">{result.provenance.historical_basis === 'imported_portfolio_history' ? 'Imported history' : 'Synthetic history'}</span>
            <span className="backtest-source-badge">Model {result.model_reliability.status}</span>
            <span className="backtest-source-badge">Regime {result.volatility_regime.regime.label}</span>
          </div>
        </div>

        <div className="dashboard-summary compact-summary-grid overlay-summary-grid">
          <div className={metricCardClass(toneFromConfidence(result.volatility_regime.regime.confidence))}>
            <p className="stat-label">Top-Line Regime</p>
            <p className="summary-value regime-value">{result.volatility_regime.regime.label}</p>
            <p className="helper">{result.volatility_regime.regime.confidence} confidence</p>
          </div>
          <div className={metricCardClass(toneFromVolPercentile(result.volatility_regime.snapshot.current_20d_vol_percentile))}>
            <p className="stat-label">Current Vol State</p>
            <p className="summary-value">{formatPct(result.volatility_regime.snapshot.realized_vol_20d)}</p>
            <p className="helper">20d percentile {formatPercentile(result.volatility_regime.snapshot.current_20d_vol_percentile)}</p>
          </div>
          <div className={metricCardClass(toneFromTrackingError(result.volatility_regime.snapshot.tracking_error_20d))}>
            <p className="stat-label">Risk Overlay State</p>
            <p className="summary-value">{formatPct(result.volatility_regime.snapshot.tracking_error_20d)}</p>
            <p className="helper">Tracking error 20d</p>
          </div>
        </div>

        <section className="overlay-component-block">
          <div className="section-header-inline overlay-section-header">
            <div><p className="panel-label">Component Status</p></div>
            <p className="helper">Analytical component states only; no execution guidance is attached.</p>
          </div>
          <div className="dashboard-summary compact-summary-grid overlay-component-grid">
            <div className="summary-card overlay-component-card"><p className="stat-label">Regime Engine</p><p className="summary-value">{result.volatility_regime.regime.label}</p><p className="helper">{result.volatility_regime.regime.confidence} confidence</p></div>
            <div className="summary-card overlay-component-card"><p className="stat-label">Benchmark Relative</p><p className="summary-value">{formatPct(result.relative_risk.tracking_error_pct)}</p><p className="helper">Beta {formatNumber(result.risk_summary.portfolio_beta, 2)} / Corr {formatNumber(result.risk_summary.portfolio_correlation, 2)}</p></div>
            <div className="summary-card overlay-component-card"><p className="stat-label">Factor Stability</p><p className="summary-value">{result.model_reliability.confidence}</p><p className="helper">Status {result.model_reliability.status}</p></div>
          </div>
        </section>

        <section className="overlay-component-block">
          <div className="section-header-inline overlay-section-header">
            <div><p className="panel-label">Explanation Drivers</p></div>
            <p className="helper">Primary explanation drivers are mapped directly from existing diagnostics outputs.</p>
          </div>
          <div className="dashboard-summary compact-summary-grid overlay-driver-grid">
            {explanationDrivers.map((driver) => (
              <div className={metricCardClass(driver.tone)} key={driver.label}>
                <p className="stat-label">{driver.label}</p>
                <p className="summary-value">{driver.value}</p>
                <p className="helper">{driver.detail}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="overlay-component-block">
          <div className="section-header-inline overlay-section-header">
            <div><p className="panel-label">Recent Context</p></div>
            <p className="helper">Compact recent-history context from the available risk path only when the data supports a clean read.</p>
          </div>
          <div className="exposure-chart-card overlay-history-card">
            <div className="exposure-chart-topbar">
              <div className="section-header-inline sector-list-header exposure-chart-header">
                <div className="exposure-chart-title-block"><p className="panel-label">Recent Overlay History</p></div>
                <p className="helper exposure-chart-helper exposure-chart-helper-right">Last {recentHistory.length} observations</p>
              </div>
              <div className="exposure-chart-subhead">
                <p className="helper exposure-chart-helper">Realized volatility and drawdown are shown as observational context only.</p>
              </div>
            </div>
            <div className="line-chart-panel compact-chart-panel risk-combined-chart-panel">
              {historyRenderable ? (
                <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                  <LineChart data={recentHistory} margin={{ top: 12, right: 12, left: 0, bottom: 12 }}>
                    <CartesianGrid stroke="rgba(70, 82, 98, 0.18)" strokeDasharray="3 3" />
                    <ReferenceLine y={0} stroke="rgba(156, 169, 184, 0.34)" strokeDasharray="5 5" />
                    <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" padding={{ left: 0, right: 0 }} tickFormatter={formatDateLabel} />
                    <YAxis tick={{ fill: '#748295', fontSize: 10 }} width={48} tickFormatter={formatAxisPct} />
                    <Tooltip content={(props) => <OverlayTooltip {...props} />} />
                    <Line type="monotone" dataKey="realized_vol_20d" name="Realized Vol 20d" stroke="#5b87c5" dot={false} strokeWidth={1.9} isAnimationActive={false} />
                    <Line type="monotone" dataKey="drawdown_pct" name="Drawdown" stroke="#d85a51" dot={false} strokeWidth={2.1} isAnimationActive={false} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="empty-state-panel chart-empty-state">
                  <p className="empty-state-title">Recent overlay history is unavailable.</p>
                  <p className="helper">This compact visualization appears only when the diagnostics payload contains enough recent risk observations.</p>
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="overlay-component-block">
          <div className="section-header-inline overlay-section-header">
            <div><p className="panel-label">Metadata & Caveats</p></div>
            <p className="helper">Truth, provenance, and freshness remain explicit.</p>
          </div>
          <div className="overlay-meta-grid">
            <div className="summary-card overlay-meta-card">
              <p className="stat-label">Methodology</p>
              <p className="helper">{result.volatility_regime.methodology}</p>
            </div>
            <div className="summary-card overlay-meta-card">
              <p className="stat-label">Provenance</p>
              <p className="helper">{result.provenance.note}</p>
            </div>
            <div className="summary-card overlay-meta-card">
              <p className="stat-label">State</p>
              <p className="helper">{stateNote}</p>
              {hasPartialState ? <p className="helper">Interpret component states as partial rather than fully resolved.</p> : null}
            </div>
          </div>
        </section>
      </section>
    </article>
  )
}
