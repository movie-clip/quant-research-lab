import { useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TooltipContentProps } from 'recharts/types/component/Tooltip'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

import type { DiagnosticsEngineResponse } from './types'
import { formatHistoryTruthClassLabel, formatSnapshotBasisLabel, humanizeContractLabel } from './historyTruth'

type BehaviorWindow = 20 | 60 | 252

type DecisionCardTone = 'hot' | 'warm' | 'cool' | 'neutral'

type BehaviorLine = {
  key: string
  label: string
  color: string
  strokeWidth?: number
  axisId?: 'left' | 'right'
}

type ChartDomain = [number, number] | readonly ['auto', 'auto']

const BEHAVIOR_WINDOW_OPTIONS: BehaviorWindow[] = [20, 60, 252]

const FACTOR_LINE_COLORS: Record<string, string> = {
  market: '#5b87c5',
  growth: '#3cb79f',
  value: '#65c18c',
  small_cap: '#2aa07b',
  technology: '#3b82f6',
  financials: '#cf8a4a',
  health_care: '#d6a45e',
  energy: '#de7047',
  industrials: '#c99b5a',
  consumer_staples: '#8f9b4f',
  utilities: '#6aa3a1',
  consumer_discretionary: '#b86f9b',
  rates_ief: '#9aa7bf',
  rates_tlt: '#7a8da8',
  credit: '#b6a36a',
  commodities: '#d7bf5c',
}

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
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

function formatAxisRatio(value: number | string) {
  return Number(value).toFixed(1)
}

function formatTooltipValue(value: ValueType | undefined) {
  if (value == null) return 'n/a'
  return typeof value === 'number' ? value.toFixed(2) : String(value)
}

function hasSeriesValue(data: Array<Record<string, number | string | null | undefined>>, key: string) {
  return data.some((point) => typeof point[key] === 'number' && Number.isFinite(point[key] as number))
}

function trimLeadingNullPoints<T extends { date: string }>(data: T[], keys: string[]) {
  const firstIndex = data.findIndex((point) => keys.some((key) => point[key as keyof T] != null))
  if (firstIndex < 0) return []
  return firstIndex > 0 ? data.slice(firstIndex) : data
}

function getCoverage<T extends { date: string }>(data: T[]) {
  if (!data.length) return null
  return { observations: data.length, startDate: data[0].date, endDate: data[data.length - 1].date }
}

function formatCoverageLabel(coverage: { observations: number; startDate: string; endDate: string } | null) {
  if (!coverage) return 'Insufficient history for the selected window'
  return `${coverage.observations} observations · ${formatDateLabel(coverage.startDate)} to ${formatDateLabel(coverage.endDate)}`
}

function getRollingLoadingsSeries(result: DiagnosticsEngineResponse, window: BehaviorWindow) {
  if (window === 60) return result.statistical_factor_model.rolling_loadings_60d
  if (window === 252) return result.statistical_factor_model.rolling_loadings_252d
  return result.statistical_factor_model.rolling_loadings_20d
}

function getWindowSummary(result: DiagnosticsEngineResponse, window: BehaviorWindow) {
  return result.statistical_factor_model.windows.find((item) => item.window_days === window) ?? null
}

function computeSymmetricFactorDomain(
  data: Array<Record<string, number | string | null | undefined>>,
  keys: string[],
): ChartDomain {
  const values = data.flatMap((point) => keys.map((key) => point[key])).filter((value) => typeof value === 'number' && Number.isFinite(value)) as number[]
  if (!values.length) return ['auto', 'auto'] as const
  const bound = Math.max(...values.map((value) => Math.abs(value)), 0.2) * 1.08
  return [-bound, bound]
}

function NumericChartTooltip({ active, payload, label }: TooltipContentProps<ValueType, NameType>) {
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
            <span>{formatTooltipValue(item.value)}</span>
          </div>
        )
      })}
    </div>
  )
}

function DiagnosticsBehaviorChartCard({
  title,
  helper,
  helperRight,
  controls,
  chartClassName,
  data,
  lines,
  yAxisFormatter,
  rightAxisFormatter,
  showZeroReference = false,
  domain,
  emptyTitle,
  emptyDetail,
}: {
  title: string
  helper: string
  helperRight?: string
  controls?: ReactNode
  chartClassName: string
  data: Array<Record<string, number | string | null | undefined>>
  lines: BehaviorLine[]
  yAxisFormatter: (value: number | string) => string
  rightAxisFormatter?: (value: number | string) => string
  showZeroReference?: boolean
  domain?: [number, number] | readonly ['auto', 'auto']
  emptyTitle: string
  emptyDetail: string
}) {
  const renderableLines = lines.filter((line) => hasSeriesValue(data, line.key))
  const showRightAxis = !!rightAxisFormatter && renderableLines.some((line) => line.axisId === 'right')
  const hasRenderableSeries = data.length > 1 && renderableLines.length > 0

  return (
    <section className="exposure-chart-card">
      <div className="exposure-chart-topbar">
        <div className="section-header-inline sector-list-header exposure-chart-header">
          <div className="exposure-chart-title-block"><p className="panel-label">{title}</p></div>
          {controls ? <div className="exposure-chart-header-controls">{controls}</div> : <span className="exposure-chart-header-controls exposure-chart-header-controls-placeholder" aria-hidden="true" />}
          {helperRight ? <p className="helper exposure-chart-helper exposure-chart-helper-right">{helperRight}</p> : <span className="exposure-chart-helper exposure-chart-helper-right exposure-chart-helper-placeholder" aria-hidden="true" />}
        </div>
        <div className="exposure-chart-subhead">
          <p className="helper exposure-chart-helper">{helper}</p>
        </div>
      </div>
      <div className={`line-chart-panel compact-chart-panel ${chartClassName}`}>
        {hasRenderableSeries ? (
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <LineChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 12 }}>
              <CartesianGrid stroke="rgba(70, 82, 98, 0.18)" strokeDasharray="3 3" />
              {showZeroReference ? <ReferenceLine y={0} stroke="rgba(156, 169, 184, 0.34)" strokeDasharray="5 5" /> : null}
              <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" padding={{ left: 0, right: 0 }} tickFormatter={formatDateLabel} />
              <YAxis yAxisId="left" tick={{ fill: '#748295', fontSize: 10 }} width={48} tickFormatter={yAxisFormatter} domain={domain} />
              {showRightAxis ? <YAxis yAxisId="right" orientation="right" tick={{ fill: '#748295', fontSize: 10 }} width={40} tickFormatter={rightAxisFormatter} /> : null}
              <Tooltip content={(props) => <NumericChartTooltip {...props} />} />
              {renderableLines.map((line) => <Line key={line.key} yAxisId={line.axisId ?? 'left'} type="monotone" dataKey={line.key} name={line.label} stroke={line.color} dot={false} strokeWidth={line.strokeWidth ?? 1.9} isAnimationActive={false} />)}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state-panel chart-empty-state">
            <p className="empty-state-title">{emptyTitle}</p>
            <p className="helper">{emptyDetail}</p>
          </div>
        )}
      </div>
    </section>
  )
}

function diagnosticsHistoryBasisLabel(result: DiagnosticsEngineResponse) {
  return formatHistoryTruthClassLabel(result.provenance.history_truth_class)
}

function diagnosticsSnapshotBasisLabel(result: DiagnosticsEngineResponse) {
  return formatSnapshotBasisLabel(result.provenance.snapshot_basis)
}

function diagnosticsStatusLabel(result: DiagnosticsEngineResponse) {
  return result.availability.historical_sections_available ? 'Historical sections live' : 'Historical sections unavailable'
}

function diagnosticsLead() {
  return 'Review provenance and decision-grade signals before drilling into deeper factor and risk detail.'
}

function formatStatusLabel(value: string | null | undefined) {
  return humanizeContractLabel(value)
}

function decisionCardToneForDrawdown(value: number | null | undefined): DecisionCardTone {
  if (value == null) return 'neutral'
  if (value <= -8) return 'hot'
  if (value < 0) return 'warm'
  return 'cool'
}

function decisionCardToneForConfidence(
  confidence: DiagnosticsEngineResponse['model_reliability']['confidence'],
  status: DiagnosticsEngineResponse['model_reliability']['status'],
): DecisionCardTone {
  if (status !== 'ok') return 'warm'
  if (confidence === 'high') return 'cool'
  if (confidence === 'medium') return 'warm'
  return 'hot'
}

function decisionCardToneForShare(value: number | null | undefined): DecisionCardTone {
  if (value == null) return 'neutral'
  if (value >= 0.8) return 'hot'
  if (value >= 0.5) return 'warm'
  return 'cool'
}

function decisionCardToneForTrackingError(value: number | null | undefined): DecisionCardTone {
  if (value == null) return 'neutral'
  if (value >= 8) return 'hot'
  if (value >= 5) return 'warm'
  return 'cool'
}

function metricCardClassName(tone: DecisionCardTone) {
  return `summary-card metric-card metric-card-${tone}`
}

export function DiagnosticsPanel({ result }: { result: DiagnosticsEngineResponse | null }) {
  const [behaviorWindow, setBehaviorWindow] = useState<BehaviorWindow>(60)

  const riskPathSeries = useMemo(() => {
    if (!result) return []
    return trimLeadingNullPoints(result.volatility_regime.rolling_series, [`realized_vol_${behaviorWindow}d`, 'drawdown_pct'])
  }, [behaviorWindow, result])

  const benchmarkBehaviorSeries = useMemo(() => {
    if (!result) return []
    const rollingRiskByDate = new Map(result.rolling_risk.map((point) => [point.date, point]))
    return trimLeadingNullPoints(
      result.volatility_regime.rolling_series.map((point) => {
        const riskPoint = rollingRiskByDate.get(point.date)
        return {
          ...point,
          [`beta_${behaviorWindow}d`]: riskPoint?.[`beta_${behaviorWindow}d`] ?? null,
          [`correlation_${behaviorWindow}d`]: riskPoint?.[`correlation_${behaviorWindow}d`] ?? null,
        }
      }),
      [`tracking_error_${behaviorWindow}d`, `beta_${behaviorWindow}d`, `correlation_${behaviorWindow}d`],
    )
  }, [behaviorWindow, result])

  const supportedFactorKeys = useMemo(() => {
    if (!result) return []
    return result.statistical_factor_model.current_factor_snapshot
      .map((factor) => factor.key)
      .filter((key) => hasSeriesValue(getRollingLoadingsSeries(result, behaviorWindow) as Array<Record<string, number | string | null | undefined>>, key))
      .slice(0, 6)
  }, [behaviorWindow, result])

  const factorBehaviorSeries = useMemo(() => {
    if (!result) return []
    return trimLeadingNullPoints(getRollingLoadingsSeries(result, behaviorWindow), supportedFactorKeys)
  }, [behaviorWindow, result, supportedFactorKeys])

  if (!result) {
    return (
      <article className="panel">
        <p className="panel-label">Diagnostics</p>
        <h2>Factor and risk diagnostics</h2>
        <p className="lead compact-lead">{diagnosticsLead()}</p>
        <p className="lead compact-lead">Import a portfolio from the Dashboard to inspect current risk diagnostics.</p>
      </article>
    )
  }

  const historyBasisLabel = diagnosticsHistoryBasisLabel(result)
  const snapshotBasisLabel = diagnosticsSnapshotBasisLabel(result)
  const historyTruthClassLabel = formatHistoryTruthClassLabel(result.provenance.history_truth_class)
  const historicalStatusLabel = diagnosticsStatusLabel(result)
  const modelStatusLabel = formatStatusLabel(result.model_reliability.status)
  const selectedBehaviorWindowSummary = getWindowSummary(result, behaviorWindow)
  const supportsBehavior252 = (selectedBehaviorWindowSummary?.status === 'ok' || selectedBehaviorWindowSummary?.status === 'partial') && behaviorWindow === 252
  const behaviorWindowAvailable = behaviorWindow !== 252 || supportsBehavior252
  const riskPathCoverage = getCoverage(riskPathSeries)
  const benchmarkBehaviorCoverage = getCoverage(benchmarkBehaviorSeries)
  const factorBehaviorCoverage = getCoverage(factorBehaviorSeries)
  const factorBehaviorDomain = computeSymmetricFactorDomain(factorBehaviorSeries as Array<Record<string, number | string | null | undefined>>, supportedFactorKeys)
  const behaviorWindowStatusLabel = selectedBehaviorWindowSummary ? `Window ${behaviorWindow}d ${formatStatusLabel(selectedBehaviorWindowSummary.status)}` : `Window ${behaviorWindow}d unavailable`
  const drawdownTone = decisionCardToneForDrawdown(result.drawdown_summary.current_drawdown_pct)
  const maxDrawdownTone = decisionCardToneForDrawdown(result.drawdown_summary.max_drawdown_pct)
  const modelConfidenceTone = decisionCardToneForConfidence(result.model_reliability.confidence, result.model_reliability.status)
  const trackingErrorTone = decisionCardToneForTrackingError(result.volatility_summary.tracking_error_pct)
  const factorShareTone = decisionCardToneForShare(result.risk_concentration_summary.top_3_factor_risk_share)
  const positionShareTone = decisionCardToneForShare(result.risk_concentration_summary.top_5_position_risk_share)

  const behaviorWindowControls = (
    <div className="toggle-group risk-window-selector" aria-label="Behavior through time window selector">
      {BEHAVIOR_WINDOW_OPTIONS.map((window) => {
        const windowSummary = getWindowSummary(result, window)
        const supported = window !== 252 || windowSummary?.status === 'ok' || windowSummary?.status === 'partial'
        return (
          <button className={`toggle-chip${behaviorWindow === window ? ' active' : ''}`} key={window} onClick={() => setBehaviorWindow(window)} type="button">
            {window}d{supported ? '' : ' unavailable'}
          </button>
        )
      })}
    </div>
  )

  const diagnosticsShell = (
    <section className="dashboard-quant-header-shell diagnostics-quant-shell" data-testid="diagnostics-shell">
      <div className="section-header-inline dashboard-quant-header-row">
        <div className="dashboard-quant-header-copy">
          <p className="panel-label">Diagnostics Shell</p>
          <h3>Provenance and decision signals</h3>
          <p className="helper">Start with source truth and availability, then scan the compact readout before moving into the deeper diagnostics.</p>
        </div>
        <div className="tab-bar dashboard-meta-row-quant diagnostics-provenance-strip">
          <span className="backtest-source-badge">{snapshotBasisLabel}</span>
          <span className="backtest-source-badge">{historyTruthClassLabel}</span>
          <span className="backtest-source-badge">{historicalStatusLabel}</span>
          {result.availability.history_context_required ? <span className="backtest-source-badge">History context required</span> : null}
          <span className="backtest-source-badge">Model {modelStatusLabel}</span>
        </div>
      </div>

      <div className="dashboard-quant-context-grid diagnostics-provenance-grid">
        <div className="summary-card diagnostics-provenance-card">
          <p className="stat-label">Snapshot Basis</p>
          <p className="diagnostics-context-value">{snapshotBasisLabel}</p>
          <p className="diagnostics-context-note">Current diagnostics anchor to the latest portfolio snapshot only.</p>
        </div>
        <div className="summary-card diagnostics-provenance-card">
          <p className="stat-label">History Truth Class</p>
          <p className="diagnostics-context-value">{historyTruthClassLabel}</p>
          <p className="diagnostics-context-note">Historical sections are shown only when the backend marked them available.</p>
        </div>
        <div className="summary-card diagnostics-provenance-card">
          <p className="stat-label">Availability</p>
          <p className="diagnostics-context-value">{historicalStatusLabel}</p>
          <p className="diagnostics-context-note">
            {result.availability.history_context_required ? 'Imported history context is required for live historical diagnostics.' : 'Historical context is available for this diagnostics window.'}
          </p>
        </div>
      </div>

      <div className="diagnostics-note-stack">
        <p className="helper">{result.provenance.note}</p>
        {result.availability.note ? <p className="helper">{result.availability.note}</p> : null}
      </div>

      {result.availability.historical_sections_available ? (
        <>
          <section className="dashboard-quant-strip diagnostics-decision-strip" data-testid="diagnostics-decision-readout">
            <div className="section-header-inline diagnostics-strip-header">
              <div>
                <p className="panel-label">Decision Readout</p>
              </div>
              <p className="helper">Decision cards stay compact: every value is mapped directly from backend summary outputs.</p>
            </div>
            <div className="dashboard-summary compact-summary-grid diagnostics-decision-grid">
              <div className={metricCardClassName(drawdownTone)}>
                <p className="stat-label">Current Drawdown</p>
                <p className="summary-value">{formatPct(result.drawdown_summary.current_drawdown_pct)}</p>
                <p className="helper">Max drawdown {formatPct(result.drawdown_summary.max_drawdown_pct)}</p>
              </div>
              <div className={metricCardClassName(maxDrawdownTone)}>
                <p className="stat-label">Max Drawdown</p>
                <p className="summary-value">{formatPct(result.drawdown_summary.max_drawdown_pct)}</p>
                <p className="helper">Current drawdown {formatPct(result.drawdown_summary.current_drawdown_pct)}</p>
              </div>
              <div className={metricCardClassName(modelConfidenceTone)}>
                <p className="stat-label">Model Confidence</p>
                <p className="summary-value">{result.model_reliability.confidence}</p>
                <p className="helper">{modelStatusLabel} / R-squared {formatNumber(result.model_reliability.r_squared, 4)}</p>
              </div>
              <div className={metricCardClassName(trackingErrorTone)}>
                <p className="stat-label">Tracking Error</p>
                <p className="summary-value">{formatPct(result.volatility_summary.tracking_error_pct)}</p>
                <p className="helper">Benchmark {result.relative_risk.benchmark_symbol}</p>
              </div>
              <div className={metricCardClassName(factorShareTone)}>
                <p className="stat-label">Top 3 Factor Risk Share</p>
                <p className="summary-value">{formatPct(result.risk_concentration_summary.top_3_factor_risk_share != null ? result.risk_concentration_summary.top_3_factor_risk_share * 100 : null)}</p>
                <p className="helper">Factor HHI {formatNumber(result.risk_concentration_summary.factor_hhi, 4)}</p>
              </div>
              <div className={metricCardClassName(positionShareTone)}>
                <p className="stat-label">Top 5 Position Risk Share</p>
                <p className="summary-value">{formatPct(result.risk_concentration_summary.top_5_position_risk_share != null ? result.risk_concentration_summary.top_5_position_risk_share * 100 : null)}</p>
                <p className="helper">Position HHI {formatNumber(result.risk_concentration_summary.position_hhi, 4)}</p>
              </div>
            </div>
          </section>

          <div className="dashboard-quant-context-grid diagnostics-support-grid">
            <section className="summary-card diagnostics-support-card">
              <div>
                <p className="panel-label">Historical Context</p>
                <p className="helper">Drawdown and volatility context from the live historical diagnostics window.</p>
              </div>
              <div className="diagnostics-support-rows">
                <div className="diagnostics-support-row"><span>Portfolio Volatility</span><span>{formatPct(result.volatility_summary.portfolio_volatility_pct)}</span></div>
                <div className="diagnostics-support-row"><span>Benchmark Volatility</span><span>{formatPct(result.volatility_summary.benchmark_volatility_pct)}</span></div>
                <div className="diagnostics-support-row"><span>Downside Volatility</span><span>{formatPct(result.volatility_summary.downside_volatility_pct)}</span></div>
                <div className="diagnostics-support-row"><span>Tracking Error</span><span>{formatPct(result.volatility_summary.tracking_error_pct)}</span></div>
              </div>
            </section>

            <section className="summary-card diagnostics-support-card">
              <div>
                <p className="panel-label">Model Readiness</p>
                <p className="helper">Fit, stability, and coverage stay explicit before the deeper factor tables.</p>
              </div>
              <div className="diagnostics-support-rows">
                <div className="diagnostics-support-row"><span>Status</span><span>{modelStatusLabel}</span></div>
                <div className="diagnostics-support-row"><span>Residual Volatility</span><span>{formatPct(result.model_reliability.residual_volatility)}</span></div>
                <div className="diagnostics-support-row"><span>Stability Score</span><span>{formatNumber(result.model_reliability.stability_score, 4)}</span></div>
                <div className="diagnostics-support-row"><span>Factors Used / Missing</span><span>{formatNumber(result.model_reliability.factor_count_used, 0)} / {formatNumber(result.model_reliability.missing_factor_count, 0)}</span></div>
              </div>
            </section>

            <section className="summary-card diagnostics-support-card">
              <div>
                <p className="panel-label">Concentration Watch</p>
                <p className="helper">Concentration risk stays compact here and detailed breakdowns remain below.</p>
              </div>
              <div className="diagnostics-support-rows">
                <div className="diagnostics-support-row"><span>Top 1 Factor Risk Share</span><span>{formatPct(result.risk_concentration_summary.top_1_factor_risk_share != null ? result.risk_concentration_summary.top_1_factor_risk_share * 100 : null)}</span></div>
                <div className="diagnostics-support-row"><span>Top 1 Position Risk Share</span><span>{formatPct(result.risk_concentration_summary.top_1_position_risk_share != null ? result.risk_concentration_summary.top_1_position_risk_share * 100 : null)}</span></div>
                <div className="diagnostics-support-row"><span>Factor HHI</span><span>{formatNumber(result.risk_concentration_summary.factor_hhi, 4)}</span></div>
                <div className="diagnostics-support-row"><span>Position HHI</span><span>{formatNumber(result.risk_concentration_summary.position_hhi, 4)}</span></div>
              </div>
            </section>
          </div>
        </>
      ) : (
        <div className="empty-state-panel diagnostics-unavailable-state">
          <p className="empty-state-title">Historical diagnostics unavailable for this snapshot.</p>
          <p className="helper">{result.availability.note ?? 'This view requires imported portfolio history context and is not approximated from a snapshot alone.'}</p>
          <p className="helper">Historical diagnostics are not approximated when history context is missing.</p>
        </div>
      )}
    </section>
  )

  if (!result.availability.historical_sections_available) {
    return (
      <article className="panel">
        <p className="panel-label">Diagnostics</p>
        <h2>Factor and risk diagnostics</h2>
        <p className="lead compact-lead">{diagnosticsLead()}</p>
        {diagnosticsShell}
      </article>
    )
  }

  return (
    <article className="panel">
      <p className="panel-label">Diagnostics</p>
      <h2>Factor and risk diagnostics</h2>
      <p className="lead compact-lead">{diagnosticsLead()}</p>
      {diagnosticsShell}

      <section className="dashboard-bottom-grid exposure-primary-section diagnostics-behavior-section" data-testid="diagnostics-behavior-through-time">
        <div className="section-header-inline sector-list-header">
          <div>
            <p className="panel-label">Behavior Through Time</p>
          </div>
          <p className="helper">Use the selected window to review risk path, benchmark-relative behavior, and factor loadings without inventing unsupported history.</p>
          {behaviorWindowControls}
        </div>
        <div className="factor-snapshot-meta-row diagnostics-behavior-meta-row">
          <p className="helper">Provenance: {result.provenance.note}</p>
          <p className="helper">Availability: {result.availability.note ?? 'Historical diagnostics remain live for the supported windows shown here.'}</p>
          <p className="helper">Status: {historyTruthClassLabel} / {historicalStatusLabel} / {behaviorWindowStatusLabel}. Unsupported windows stay hidden instead of interpolated.</p>
        </div>

        {!behaviorWindowAvailable ? (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">Behavior-through-time charts are unavailable for {behaviorWindow}d.</p>
            <p className="helper">The backend marked this window as {formatStatusLabel(selectedBehaviorWindowSummary?.status ?? 'unavailable')}. The panel does not invent continuity across unsupported periods.</p>
          </div>
        ) : (
          <>
            <div className="split-grid diagnostics-behavior-chart-grid">
              <DiagnosticsBehaviorChartCard
                title="Risk Path"
                helper={`Drawdown and realized volatility through time. ${formatCoverageLabel(riskPathCoverage)}`}
                helperRight={`Window ${behaviorWindow}d`}
                chartClassName="risk-combined-chart-panel"
                data={riskPathSeries}
                yAxisFormatter={formatAxisPct}
                lines={[
                  { key: 'drawdown_pct', label: 'Drawdown', color: '#d85a51', strokeWidth: 2.1 },
                  { key: `realized_vol_${behaviorWindow}d`, label: `Realized Vol ${behaviorWindow}d`, color: '#5b87c5' },
                ]}
                emptyTitle={`Not enough history for ${behaviorWindow}d risk-path behavior.`}
                emptyDetail="This chart requires at least two backend observations with drawdown or realized volatility values."
              />

              <DiagnosticsBehaviorChartCard
                title="Benchmark-Relative Behavior"
                helper={`Tracking error plus beta/correlation where the backend supports them. ${formatCoverageLabel(benchmarkBehaviorCoverage)}`}
                helperRight={`${result.relative_risk.benchmark_symbol} relative`}
                chartClassName="risk-drawdown-chart-panel"
                data={benchmarkBehaviorSeries}
                yAxisFormatter={formatAxisPct}
                rightAxisFormatter={formatAxisRatio}
                lines={[
                  { key: `tracking_error_${behaviorWindow}d`, label: `Tracking Error ${behaviorWindow}d`, color: '#9aa7bf', strokeWidth: 2.1, axisId: 'left' },
                  { key: `beta_${behaviorWindow}d`, label: `Beta ${behaviorWindow}d`, color: '#cf8a4a', axisId: 'right' },
                  { key: `correlation_${behaviorWindow}d`, label: `Correlation ${behaviorWindow}d`, color: '#6c88a6', axisId: 'right' },
                ]}
                emptyTitle={`Benchmark-relative behavior is unavailable for ${behaviorWindow}d.`}
                emptyDetail="Tracking error, beta, and correlation are shown only where the historical engine returned real series values."
              />
            </div>

            <DiagnosticsBehaviorChartCard
              title="Factor Behavior"
              helper={`Bounded rolling loading paths from the existing factor model payload. ${formatCoverageLabel(factorBehaviorCoverage)}`}
              helperRight={`${supportedFactorKeys.length || 0} factors shown`}
              controls={<p className="helper diagnostics-behavior-inline-note">Top supported rolling factors only; unsupported windows stay hidden.</p>}
              chartClassName="factor-loading-chart-panel diagnostics-factor-behavior-chart"
              data={factorBehaviorSeries as Array<Record<string, number | string | null | undefined>>}
              yAxisFormatter={formatAxisRatio}
              showZeroReference
              domain={factorBehaviorDomain}
              lines={supportedFactorKeys.map((key) => {
                const factor = result.statistical_factor_model.current_factor_snapshot.find((item) => item.key === key)
                return {
                  key,
                  label: factor ? `${factor.label} (${factor.us_proxy})` : key,
                  color: FACTOR_LINE_COLORS[key] ?? '#748295',
                }
              })}
              emptyTitle={`Factor behavior is unavailable for ${behaviorWindow}d.`}
              emptyDetail="The chart starts only when the selected rolling window has actual factor-loading observations from the backend."
            />
          </>
        )}
      </section>
    </article>
  )
}
