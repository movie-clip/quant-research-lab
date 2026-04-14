import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { Brush, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TooltipContentProps } from 'recharts/types/component/Tooltip'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

import { DEFAULT_FACTOR_MODEL_METHODOLOGY } from './exposureFactorModel'
import type { ExposureAnalysis, ExposureFactorModelResponse } from './types'

type RollingWindow = 20 | 60 | 252
type FactorGroupFilter = 'all' | 'market_style' | 'sectors' | 'macro'
type SignalTone = 'hot' | 'warm' | 'cool' | 'neutral'
type RollingRiskPoint = ExposureAnalysis['rolling_risk'][number]
type VolatilityPoint = ExposureAnalysis['volatility_regime']['rolling_series'][number]
type RollingRiskMetricKey = keyof Pick<RollingRiskPoint, 'beta_20d' | 'beta_60d' | 'beta_252d' | 'correlation_20d' | 'correlation_60d' | 'correlation_252d'>
type PortfolioVolSeriesKey = 'realized_vol_20d' | 'realized_vol_60d' | 'realized_vol_252d' | 'benchmark_vol_20d' | 'benchmark_vol_60d' | 'benchmark_vol_252d'
type DownsideVolSeriesKey = 'downside_vol_20d' | 'downside_vol_60d' | 'downside_vol_252d'
type TrackingErrorSeriesKey = 'tracking_error_20d' | 'tracking_error_60d' | 'tracking_error_252d'

const ROLLING_WINDOW_OPTIONS: RollingWindow[] = [20, 60, 252]
const DEFAULT_VISIBLE_FACTORS = ['market', 'growth', 'value', 'small_cap', 'technology', 'financials']
const DEFAULT_PORTFOLIO_VOL_SERIES: PortfolioVolSeriesKey[] = ['realized_vol_20d', 'realized_vol_60d', 'benchmark_vol_20d']
const DEFAULT_DOWNSIDE_VOL_SERIES: DownsideVolSeriesKey[] = ['downside_vol_20d', 'downside_vol_60d']
const DEFAULT_TRACKING_ERROR_SERIES: TrackingErrorSeriesKey[] = ['tracking_error_20d', 'tracking_error_60d']

const PORTFOLIO_VOL_SERIES_LABELS: Record<PortfolioVolSeriesKey, string> = {
  realized_vol_20d: 'Realized Vol 20d',
  realized_vol_60d: 'Realized Vol 60d',
  realized_vol_252d: 'Realized Vol 252d',
  benchmark_vol_20d: 'Benchmark Vol 20d',
  benchmark_vol_60d: 'Benchmark Vol 60d',
  benchmark_vol_252d: 'Benchmark Vol 252d',
}

const DOWNSIDE_VOL_SERIES_LABELS: Record<DownsideVolSeriesKey, string> = {
  downside_vol_20d: 'Downside Vol 20d',
  downside_vol_60d: 'Downside Vol 60d',
  downside_vol_252d: 'Downside Vol 252d',
}

const TRACKING_ERROR_SERIES_LABELS: Record<TrackingErrorSeriesKey, string> = {
  tracking_error_20d: 'Tracking Error 20d',
  tracking_error_60d: 'Tracking Error 60d',
  tracking_error_252d: 'Tracking Error 252d',
}

const PORTFOLIO_VOL_SERIES_COLORS: Record<PortfolioVolSeriesKey, string> = {
  realized_vol_20d: '#5b87c5',
  realized_vol_60d: '#3cb79f',
  realized_vol_252d: '#7a8da8',
  benchmark_vol_20d: '#b4c2d9',
  benchmark_vol_60d: '#89a9d0',
  benchmark_vol_252d: '#6f84a5',
}

const DOWNSIDE_VOL_SERIES_COLORS: Record<DownsideVolSeriesKey, string> = {
  downside_vol_20d: '#cf8a4a',
  downside_vol_60d: '#d6a45e',
  downside_vol_252d: '#de7047',
}

const TRACKING_ERROR_SERIES_COLORS: Record<TrackingErrorSeriesKey, string> = {
  tracking_error_20d: '#9aa7bf',
  tracking_error_60d: '#b6a36a',
  tracking_error_252d: '#d7bf5c',
}

const FACTOR_CATEGORY_LABELS: Record<string, string> = {
  market: 'Market',
  style: 'Style',
  sector: 'Sector',
  macro: 'Macro',
}

const MAPPING_QUALITY_LABELS: Record<string, string> = {
  high: 'Exact-ish',
  'medium-high': 'Close proxy',
  medium: 'Loose proxy',
  low: 'Loose proxy',
}

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
  rates_ief: '#9aa7bf',
  rates_tlt: '#7a8da8',
  credit: '#b6a36a',
  commodities: '#d7bf5c',
}

function formatDateLabel(value: string | number | null | undefined) {
  if (typeof value !== 'string') {
    return ''
  }
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) {
    return value
  }
  return `${month}/${day}/${year.slice(2)}`
}

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'n/a' : `$${value.toFixed(2)}`
}

function formatCompactMoney(value: number | null | undefined) {
  if (value == null) return 'n/a'
  if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(2)}k`
  return formatMoney(value)
}

function formatRatio(value: number | null | undefined) {
  return value == null ? 'n/a' : value.toFixed(2)
}

function formatPercentile(value: number | null | undefined) {
  return value == null ? 'n/a' : `${(value * 100).toFixed(0)}%`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatSignedNumber(value: number | null | undefined, digits = 2) {
  if (value == null) return 'n/a'
  return `${value >= 0 ? '+' : ''}${value.toFixed(digits)}`
}

function formatSignedPct(value: number | null | undefined) {
  if (value == null) return 'n/a'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatLoading(value: number | null | undefined) {
  return value == null ? 'Insufficient data' : value.toFixed(2)
}

function formatMappingScore(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(0)}%`
}

function toneFromMappingMatch(score: number | null | undefined): SignalTone {
  if (score == null) return 'neutral'
  if (score >= 90) return 'cool'
  if (score >= 80) return 'cool'
  if (score >= 65) return 'warm'
  if (score >= 50) return 'warm'
  return 'hot'
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function signalToneClass(tone: SignalTone) {
  if (tone === 'hot') return 'risk-hot'
  if (tone === 'warm') return 'risk-warm'
  if (tone === 'cool') return 'risk-cool'
  return 'risk-neutral'
}

function metricCardClass(tone: SignalTone) {
  return `summary-card metric-card metric-card-${tone}`
}

type MetricRangeStats = {
  min: number
  max: number
  current: number
  position: number
}

function getSeriesStats(data: Array<Record<string, number | string | null>>, key: string): MetricRangeStats | null {
  const values = data
    .map((point) => point[key])
    .filter((value) => typeof value === 'number' && Number.isFinite(value)) as number[]

  if (!values.length) return null

  const min = Math.min(...values)
  const max = Math.max(...values)
  const current = [...data]
    .reverse()
    .map((point) => point[key])
    .find((value) => typeof value === 'number' && Number.isFinite(value)) as number | undefined

  if (current == null) return null

  const position = min === max ? 0.5 : clamp((current - min) / (max - min), 0, 1)

  return { min, max, current, position }
}

function toneFromRangePosition(position: number | null | undefined): SignalTone {
  if (position == null) return 'neutral'
  if (position >= 0.8) return 'hot'
  if (position >= 0.6) return 'warm'
  if (position <= 0.25) return 'cool'
  return 'neutral'
}

function toneFromBeta(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value >= 1.2 || value < 0) return 'hot'
  if (value >= 1.05) return 'warm'
  if (value <= 0.75) return 'cool'
  return 'neutral'
}

function toneFromCorrelation(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value >= 0.9) return 'hot'
  if (value >= 0.75) return 'warm'
  if (value <= 0.45) return 'cool'
  return 'neutral'
}

function toneFromTrackingError(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value >= 12) return 'hot'
  if (value >= 7) return 'warm'
  if (value <= 4) return 'cool'
  return 'neutral'
}

function toneFromInformationRatio(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value < 0) return 'hot'
  if (value < 0.35) return 'warm'
  if (value >= 0.75) return 'cool'
  return 'neutral'
}

function toneFromOverlap(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value >= 70) return 'hot'
  if (value >= 50) return 'warm'
  if (value <= 30) return 'cool'
  return 'neutral'
}

function toneFromActiveShare(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value <= 35) return 'hot'
  if (value <= 50) return 'warm'
  if (value >= 70) return 'cool'
  return 'neutral'
}

function toneFromDrawdown(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value <= -15) return 'hot'
  if (value <= -8) return 'warm'
  if (value >= -3) return 'cool'
  return 'neutral'
}

function toneFromVolPercentile(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value >= 0.85) return 'hot'
  if (value >= 0.65) return 'warm'
  if (value <= 0.35) return 'cool'
  return 'neutral'
}

function toneFromVolRatio(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  if (value >= 1.25) return 'hot'
  if (value >= 1.05) return 'warm'
  if (value <= 0.85) return 'cool'
  return 'neutral'
}

function toneFromConfidence(value: string | null | undefined): SignalTone {
  if (!value) return 'neutral'
  if (value === 'high') return 'cool'
  if (value === 'medium') return 'neutral'
  if (value === 'low') return 'warm'
  return 'neutral'
}

function toneFromFactorLoading(value: number | null | undefined): SignalTone {
  if (value == null) return 'neutral'
  const absolute = Math.abs(value)
  if (absolute >= 1) return 'hot'
  if (absolute >= 0.45) return 'warm'
  if (absolute <= 0.15) return 'cool'
  return 'neutral'
}

function mappingQualityBadge(value: string) {
  return MAPPING_QUALITY_LABELS[value] ?? value
}

function mappingMatchScore(
  factor: ExposureFactorModelResponse['statistical_factor_model']['current_factor_snapshot'][number],
  registry: Record<string, ExposureFactorModelResponse['factor_registry'][number]>,
) {
  return factor.primary_mapping?.match_summary?.score_pct ?? registry[factor.key]?.primary_mapping?.match_summary?.score_pct ?? null
}

function mappingMatchCaption(
  factor: ExposureFactorModelResponse['statistical_factor_model']['current_factor_snapshot'][number],
  registry: Record<string, ExposureFactorModelResponse['factor_registry'][number]>,
) {
  return factor.primary_mapping?.match_summary?.label ?? registry[factor.key]?.primary_mapping?.match_summary?.label ?? 'Match'
}

function trimLeadingNullPoints<T extends { date: string }>(data: T[], keys: string[]) {
  const firstIndex = data.findIndex((point) => keys.some((key) => point[key as keyof T] != null))
  if (firstIndex < 0) {
    return []
  }
  return firstIndex > 0 ? data.slice(firstIndex) : data
}

function resolveChartWindowIndices<T extends { date: string }>(data: T[], window: { startDate: string; endDate: string } | null) {
  if (!data.length) return null
  if (!window) return { startIndex: 0, endIndex: data.length - 1 }

  let startIndex = data.findIndex((point) => point.date >= window.startDate)
  if (startIndex < 0) startIndex = 0

  let endIndex = -1
  for (let index = data.length - 1; index >= 0; index -= 1) {
    if (data[index]?.date <= window.endDate) {
      endIndex = index
      break
    }
  }
  if (endIndex < 0) endIndex = data.length - 1
  if (endIndex < startIndex) endIndex = startIndex

  return { startIndex, endIndex }
}

function computeFactorChartDomain(
  data: Array<Record<string, number | string | null | undefined>>,
  keys: string[],
  selection: { startIndex: number; endIndex: number } | null,
) {
  const selected = selection ? data.slice(selection.startIndex, selection.endIndex + 1) : data
  const values = selected.flatMap((point) => keys.map((key) => point[key])).filter((value) => typeof value === 'number' && Number.isFinite(value)) as number[]

  if (!values.length) {
    return ['auto', 'auto'] as const
  }

  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = Math.max(max - min, 0.2)
  const padding = span * 0.08
  return [min - padding, max + padding] as const
}

function getRollingLoadingsSeries(result: ExposureFactorModelResponse, window: RollingWindow) {
  if (window === 60) return result.statistical_factor_model.rolling_loadings_60d
  if (window === 252) return result.statistical_factor_model.rolling_loadings_252d
  return result.statistical_factor_model.rolling_loadings_20d
}

function getWindowSummary(result: ExposureFactorModelResponse, window: RollingWindow) {
  return result.statistical_factor_model.windows.find((item) => item.window_days === window) ?? null
}

function getSelectedWindowFactorLoading(
  result: ExposureFactorModelResponse | null,
  window: RollingWindow,
  factorKey: string,
): number | null {
  if (!result) return null
  const series = getRollingLoadingsSeries(result, window)
  for (let index = series.length - 1; index >= 0; index -= 1) {
    const point = series[index]
    const value = point?.[factorKey]
    if (typeof value === 'number') {
      return value
    }
  }
  return null
}

function getCoverage<T extends { date: string }>(data: T[]) {
  if (!data.length) return null
  return { observations: data.length, startDate: data[0].date, endDate: data[data.length - 1].date }
}

function hasRenderableBrush(selection: { startIndex: number; endIndex: number } | null, data: Array<{ date: string }>) {
  if (!selection) return false
  if (data.length < 2) return false
  return Number.isFinite(selection.startIndex) && Number.isFinite(selection.endIndex) && selection.endIndex > selection.startIndex
}

function formatCoverageLabel(coverage: { observations: number; startDate: string; endDate: string } | null) {
  if (!coverage) return 'Insufficient history for the selected window'
  return `${coverage.observations} observations · ${formatDateLabel(coverage.startDate)} to ${formatDateLabel(coverage.endDate)}`
}

function formatTooltipValue(value: ValueType | undefined) {
  if (value == null) return 'n/a'
  return typeof value === 'number' ? value.toFixed(2) : String(value)
}

export function sortTooltipPayloadRows<T extends { dataKey?: unknown; value?: unknown }>(payload: T[], orderByKey: Record<string, number>) {
  return [...payload].sort((left, right) => {
    const leftValue = typeof left.value === 'number' ? left.value : Number.NEGATIVE_INFINITY
    const rightValue = typeof right.value === 'number' ? right.value : Number.NEGATIVE_INFINITY
    if (leftValue !== rightValue) {
      return rightValue - leftValue
    }

    const leftKey = typeof left.dataKey === 'string' ? left.dataKey : String(left.dataKey)
    const rightKey = typeof right.dataKey === 'string' ? right.dataKey : String(right.dataKey)
    const leftOrder = orderByKey[leftKey] ?? Number.MAX_SAFE_INTEGER
    const rightOrder = orderByKey[rightKey] ?? Number.MAX_SAFE_INTEGER
    if (leftOrder !== rightOrder) {
      return leftOrder - rightOrder
    }
    return leftKey.localeCompare(rightKey)
  })
}

function formatAxisPct(value: number | string) {
  return `${Number(value).toFixed(0)}%`
}

function getFactorGroupKey(category: string): FactorGroupFilter {
  if (category === 'macro') return 'macro'
  if (category === 'sector') return 'sectors'
  return 'market_style'
}

function ChartTooltip(
  {
    active,
    payload,
    label,
    registry,
    orderByKey,
  }: TooltipContentProps<ValueType, NameType> & {
    registry: Record<string, ExposureFactorModelResponse['factor_registry'][number]>
    orderByKey: Record<string, number>
  },
) {
  if (!active || !payload?.length) return null
  const rows = sortTooltipPayloadRows(payload.filter((item) => item.value != null), orderByKey)
  if (!rows.length) return null

  return (
    <div className="chart-tooltip-card factor-tooltip-card">
      <p className="chart-tooltip-date">{formatDateLabel(label)}</p>
      {rows.map((item) => {
        const key = typeof item.dataKey === 'string' ? item.dataKey : String(item.dataKey)
        const factor = registry[key]
        return (
          <div className="chart-tooltip-factor-block" key={key}>
            <div className="chart-tooltip-row">
              <span className="chart-tooltip-label">
                <span className="chart-tooltip-swatch" style={{ backgroundColor: item.color ?? '#748295' }} />
                {factor ? `${factor.label} (${factor.us_proxy})` : key}
              </span>
              <span>{formatTooltipValue(item.value)}</span>
            </div>
            {factor ? <p className="chart-tooltip-meta">{FACTOR_CATEGORY_LABELS[factor.category] ?? factor.category} · {factor.ucits_examples.length ? factor.ucits_examples.join(', ') : 'No mapped UCITS example yet'}</p> : null}
          </div>
        )
      })}
    </div>
  )
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

function ExposureChartCard({
  title,
  helper,
  helperRight,
  controls,
  chartClassName,
  data,
  yAxisFormatter,
  rightAxisFormatter,
  showZeroReference = false,
  lines,
}: {
  title: string
  helper?: string
  helperRight?: string
  controls?: ReactNode
  chartClassName: string
  data: Array<Record<string, number | string | null | undefined>>
  yAxisFormatter: (value: number | string) => string
  rightAxisFormatter?: (value: number | string) => string
  showZeroReference?: boolean
  lines: Array<{ key: string; label: string; color: string; strokeWidth?: number; axisId?: 'left' | 'right' }>
}) {
  const hasRenderableSeries = data.length > 1 && lines.some((line) => data.some((point) => typeof point[line.key] === 'number' && Number.isFinite(point[line.key] as number)))

  return (
    <section className="exposure-chart-card">
      <div className="exposure-chart-topbar">
        <div className="section-header-inline sector-list-header exposure-chart-header">
          <div className="exposure-chart-title-block"><p className="panel-label">{title}</p></div>
          {controls ? <div className="exposure-chart-header-controls">{controls}</div> : <span className="exposure-chart-header-controls exposure-chart-header-controls-placeholder" aria-hidden="true" />}
          {helperRight ? <p className="helper exposure-chart-helper exposure-chart-helper-right">{helperRight}</p> : <span className="exposure-chart-helper exposure-chart-helper-right exposure-chart-helper-placeholder" aria-hidden="true" />}
        </div>
        <div className="exposure-chart-subhead">
          {helper ? <p className="helper exposure-chart-helper">{helper}</p> : <span className="exposure-chart-helper exposure-chart-helper-placeholder" aria-hidden="true" />}
        </div>
      </div>
      <div className={`line-chart-panel compact-chart-panel ${chartClassName}`}>
        {hasRenderableSeries ? (
          <ResponsiveContainer width="100%" height="100%" minWidth={0}>
            <LineChart data={data} margin={{ top: 12, right: 12, left: 0, bottom: 12 }}>
              <CartesianGrid stroke="rgba(70, 82, 98, 0.18)" strokeDasharray="3 3" />
              {showZeroReference ? <ReferenceLine y={0} stroke="rgba(156, 169, 184, 0.34)" strokeDasharray="5 5" /> : null}
              <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" padding={{ left: 0, right: 0 }} tickFormatter={formatDateLabel} />
              <YAxis yAxisId="left" tick={{ fill: '#748295', fontSize: 10 }} width={48} tickFormatter={yAxisFormatter} />
              {rightAxisFormatter ? <YAxis yAxisId="right" orientation="right" tick={{ fill: '#748295', fontSize: 10 }} width={40} tickFormatter={rightAxisFormatter} /> : null}
              <Tooltip content={(props) => <NumericChartTooltip {...props} />} />
              {lines.map((line) => <Line key={line.key} yAxisId={line.axisId ?? 'left'} type="monotone" dataKey={line.key} name={line.label} stroke={line.color} dot={false} strokeWidth={line.strokeWidth ?? 1.9} isAnimationActive={false} />)}
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="empty-state-panel chart-empty-state">
            <p className="empty-state-title">Not enough history to render this chart.</p>
            <p className="helper">Load at least two valid observations for the selected series.</p>
          </div>
        )}
      </div>
    </section>
  )
}

function RangeContext({
  stats,
  formatter,
  tone,
}: {
  stats: MetricRangeStats | null
  formatter: (value: number | null | undefined) => string
  tone: SignalTone
}) {
  if (!stats) {
    return <p className="helper metric-range-empty">No trailing range yet.</p>
  }

  return (
    <div className="metric-range-block">
      <div className="metric-range-labels">
        <span>Min {formatter(stats.min)}</span>
        <span>Max {formatter(stats.max)}</span>
      </div>
      <div className="metric-range-track" aria-hidden="true">
        <span className={`metric-range-marker metric-range-marker-${tone}`} style={{ left: `${stats.position * 100}%` }} />
      </div>
      <p className="helper metric-range-current">Now {formatter(stats.current)}</p>
    </div>
  )
}

function MiniRangeContext({
  stats,
  formatter,
  tone,
}: {
  stats: MetricRangeStats | null
  formatter: (value: number | null | undefined) => string
  tone: SignalTone
}) {
  if (!stats) {
    return <span className="helper mini-range-empty">No range</span>
  }

  return (
    <span className="mini-range-block">
      <span className="mini-range-track" aria-hidden="true">
        <span className={`mini-range-marker mini-range-marker-${tone}`} style={{ left: `${stats.position * 100}%` }} />
      </span>
      <span className="mini-range-current">Now <span className={signalToneClass(tone)}>{formatter(stats.current)}</span></span>
      <span className="mini-range-labels">
        <span>{formatter(stats.min)}</span>
        <span>{formatter(stats.max)}</span>
      </span>
    </span>
  )
}

export function ExposurePanel({ result, factorModel, snapshotOptions = [], selectedSnapshotId = 'current', onSnapshotSelect }: { result: ExposureAnalysis | null; factorModel: ExposureFactorModelResponse | null; snapshotOptions?: Array<{ id: string; label: string }>; selectedSnapshotId?: string; onSnapshotSelect?: (snapshotId: string) => void }) {
  const [rollingWindow, setRollingWindow] = useState<RollingWindow>(60)
  const [factorFilter, setFactorFilter] = useState<FactorGroupFilter>('all')
  const [hiddenFactors, setHiddenFactors] = useState<Set<string>>(new Set())
  const [factorSnapshotCollapsed, setFactorSnapshotCollapsed] = useState(false)
  const [hoveredFactorKey, setHoveredFactorKey] = useState<string | null>(null)
  const [combinedRiskWindow, setCombinedRiskWindow] = useState<RollingWindow>(20)
  const [factorChartWindow, setFactorChartWindow] = useState<{ startDate: string; endDate: string } | null>(null)
  const resolvedFactorModel = factorModel

  const topLookthrough = result?.lookthrough.top_constituents.slice(0, 10) ?? []
  const topLookthroughSectors = result?.lookthrough_sector_exposure.slice(0, 8) ?? []
  const factorExposures = result?.factor_exposures.slice(0, 6) ?? []
  const scenarioPreview = result?.scenario_preview ?? null
  const sectorDrifts = scenarioPreview?.sector_drifts.slice(0, 5) ?? []
  const positionDrifts = scenarioPreview?.position_drifts.slice(0, 5) ?? []
  const factorDrifts = scenarioPreview?.factor_drifts.slice(0, 5) ?? []
  const scenarioStressScenarios = scenarioPreview?.scenario_stress_scenarios ?? null
  const scenarioRiskContribution = scenarioPreview?.scenario_risk_contribution ?? null
  const factorRegistry = resolvedFactorModel?.factor_registry ?? []
  const factorRegistryByKey = useMemo(() => Object.fromEntries(factorRegistry.map((factor) => [factor.key, factor])), [factorRegistry])
  const factorSnapshot = resolvedFactorModel?.statistical_factor_model.current_factor_snapshot ?? []
  const selectedWindowSummary = resolvedFactorModel ? getWindowSummary(resolvedFactorModel, rollingWindow) : null
  const selectedCollinearity = resolvedFactorModel?.statistical_factor_model.collinearity_diagnostics.find((item) => item.window_days === rollingWindow) ?? null

  const visibleFactorKeys = useMemo(() => {
    const base = factorFilter === 'all' ? DEFAULT_VISIBLE_FACTORS : factorRegistry.map((factor) => factor.key)
    return base.filter((key) => {
      if (hiddenFactors.has(key)) return false
      const factor = factorRegistryByKey[key]
      if (!factor) return false
      if (factorFilter === 'all') return true
      return getFactorGroupKey(factor.category) === factorFilter
    })
  }, [factorFilter, factorRegistry, factorRegistryByKey, hiddenFactors])
  const factorOrderByKey = useMemo(() => Object.fromEntries(visibleFactorKeys.map((key, index) => [key, index])), [visibleFactorKeys])

  const factorToggleKeys = useMemo(() => {
    const base = factorFilter === 'all' ? DEFAULT_VISIBLE_FACTORS : factorRegistry.map((factor) => factor.key)
    return base.filter((key) => {
      const factor = factorRegistryByKey[key]
      if (!factor) return false
      if (factorFilter === 'all') return true
      return getFactorGroupKey(factor.category) === factorFilter
    })
  }, [factorFilter, factorRegistry, factorRegistryByKey])

  const rollingFactorSeries = useMemo(() => {
    if (!resolvedFactorModel) return []
    return trimLeadingNullPoints(getRollingLoadingsSeries(resolvedFactorModel, rollingWindow), visibleFactorKeys)
  }, [resolvedFactorModel, rollingWindow, visibleFactorKeys])
  const factorChartSelection = useMemo(() => resolveChartWindowIndices(rollingFactorSeries, factorChartWindow), [factorChartWindow, rollingFactorSeries])
  const factorChartDomain = useMemo(() => computeFactorChartDomain(rollingFactorSeries, visibleFactorKeys, factorChartSelection), [factorChartSelection, rollingFactorSeries, visibleFactorKeys])

  const rollingRiskSeries = useMemo(() => {
    if (!result) return []
    return trimLeadingNullPoints(result.rolling_risk, [`beta_${rollingWindow}d`, `correlation_${rollingWindow}d`])
  }, [result, rollingWindow])

  const rollingFactorCoverage = useMemo(() => getCoverage(rollingFactorSeries), [rollingFactorSeries])
  const rollingRiskCoverage = useMemo(() => getCoverage(rollingRiskSeries), [rollingRiskSeries])
  const volatilityCoverage = useMemo(() => getCoverage(result?.volatility_regime.rolling_series ?? []), [result])
  const sortedSnapshotFactors = useMemo(() => [...factorSnapshot].sort((left, right) => Math.abs(right.latest_loading ?? 0) - Math.abs(left.latest_loading ?? 0)), [factorSnapshot])
  const factorLoadingSeries = useMemo(() => (resolvedFactorModel ? getRollingLoadingsSeries(resolvedFactorModel, rollingWindow) : []), [resolvedFactorModel, rollingWindow])
  const riskBetaStats = useMemo(() => getSeriesStats(result?.rolling_risk ?? [], `beta_${rollingWindow}d` as RollingRiskMetricKey), [result, rollingWindow])
  const riskCorrelationStats = useMemo(() => getSeriesStats(result?.rolling_risk ?? [], `correlation_${rollingWindow}d` as RollingRiskMetricKey), [result, rollingWindow])
  const volatilitySeries = result?.volatility_regime.rolling_series ?? []
  const drawdownRiskSeries = useMemo(() => {
    const rollingRiskByDate = new Map((result?.rolling_risk ?? []).map((point) => [point.date, point]))
    return volatilitySeries.map((point) => {
      const rollingRiskPoint = rollingRiskByDate.get(point.date)
      return {
        ...point,
        [`beta_${rollingWindow}d`]: rollingRiskPoint?.[`beta_${rollingWindow}d`] ?? null,
        [`correlation_${rollingWindow}d`]: rollingRiskPoint?.[`correlation_${rollingWindow}d`] ?? null,
      }
    })
  }, [result, rollingWindow, volatilitySeries])
  const combinedRiskLines = useMemo(() => {
    const suffix = `${combinedRiskWindow}d`
    return [
      {
        key: `realized_vol_${suffix}` as PortfolioVolSeriesKey,
        label: `Portfolio Volatility ${suffix}`,
        color: PORTFOLIO_VOL_SERIES_COLORS[`realized_vol_${suffix}` as PortfolioVolSeriesKey],
      },
      {
        key: `benchmark_vol_${suffix}` as PortfolioVolSeriesKey,
        label: `Benchmark Volatility ${suffix}`,
        color: PORTFOLIO_VOL_SERIES_COLORS[`benchmark_vol_${suffix}` as PortfolioVolSeriesKey],
      },
      {
        key: `downside_vol_${suffix}` as DownsideVolSeriesKey,
        label: `Downside Volatility ${suffix}`,
        color: DOWNSIDE_VOL_SERIES_COLORS[`downside_vol_${suffix}` as DownsideVolSeriesKey],
      },
      {
        key: `tracking_error_${suffix}` as TrackingErrorSeriesKey,
        label: `Tracking Error ${suffix}`,
        color: TRACKING_ERROR_SERIES_COLORS[`tracking_error_${suffix}` as TrackingErrorSeriesKey],
      },
    ]
  }, [combinedRiskWindow])
  const vol20Stats = useMemo(() => getSeriesStats(volatilitySeries, 'realized_vol_20d'), [volatilitySeries])
  const vol60Stats = useMemo(() => getSeriesStats(volatilitySeries, 'realized_vol_60d'), [volatilitySeries])
  const vol252Stats = useMemo(() => getSeriesStats(volatilitySeries, 'realized_vol_252d'), [volatilitySeries])
  const benchmarkVol20Stats = useMemo(() => getSeriesStats(volatilitySeries, 'benchmark_vol_20d'), [volatilitySeries])
  const benchmarkVol60Stats = useMemo(() => getSeriesStats(volatilitySeries, 'benchmark_vol_60d'), [volatilitySeries])
  const benchmarkVol252Stats = useMemo(() => getSeriesStats(volatilitySeries, 'benchmark_vol_252d'), [volatilitySeries])
  const downside20Stats = useMemo(() => getSeriesStats(volatilitySeries, 'downside_vol_20d'), [volatilitySeries])
  const downside60Stats = useMemo(() => getSeriesStats(volatilitySeries, 'downside_vol_60d'), [volatilitySeries])
  const downside252Stats = useMemo(() => getSeriesStats(volatilitySeries, 'downside_vol_252d'), [volatilitySeries])
  const tracking20Stats = useMemo(() => getSeriesStats(volatilitySeries, 'tracking_error_20d'), [volatilitySeries])
  const tracking60Stats = useMemo(() => getSeriesStats(volatilitySeries, 'tracking_error_60d'), [volatilitySeries])
  const tracking252Stats = useMemo(() => getSeriesStats(volatilitySeries, 'tracking_error_252d'), [volatilitySeries])
  const drawdownStats = useMemo(() => getSeriesStats(volatilitySeries, 'drawdown_pct'), [volatilitySeries])
  const betaTone = toneFromBeta(result?.risk_summary.portfolio_beta)
  const correlationTone = toneFromCorrelation(result?.risk_summary.portfolio_correlation)
  const overlapTone = toneFromOverlap(result ? result.market_overlap.portfolio_in_benchmark_weight * 100 : null)
  const activeShareTone = toneFromActiveShare(result ? result.market_overlap.active_share * 100 : null)
  const trackingErrorTone = toneFromTrackingError(result?.relative_risk.tracking_error_pct)
  const informationRatioTone = toneFromInformationRatio(result?.relative_risk.information_ratio)
  const realizedVol20Tone = toneFromRangePosition(vol20Stats?.position)
  const realizedVol60Tone = toneFromRangePosition(vol60Stats?.position)
  const realizedVol252Tone = toneFromRangePosition(vol252Stats?.position)
  const benchmarkVol20Tone = toneFromRangePosition(benchmarkVol20Stats?.position)
  const benchmarkVol60Tone = toneFromRangePosition(benchmarkVol60Stats?.position)
  const benchmarkVol252Tone = toneFromRangePosition(benchmarkVol252Stats?.position)
  const downsideVol20Tone = toneFromRangePosition(downside20Stats?.position)
  const downsideVol60Tone = toneFromRangePosition(downside60Stats?.position)
  const downsideVol252Tone = toneFromRangePosition(downside252Stats?.position)
  const tracking20Tone = toneFromRangePosition(tracking20Stats?.position)
  const tracking60Tone = toneFromRangePosition(tracking60Stats?.position)
  const tracking252Tone = toneFromRangePosition(tracking252Stats?.position)
  const currentDrawdownTone = toneFromDrawdown(result?.volatility_regime.snapshot.current_drawdown_pct)
  const maxDrawdownTone = toneFromDrawdown(result?.volatility_regime.snapshot.max_drawdown_pct)
  const volRatio2060Tone = toneFromVolRatio(result?.volatility_regime.snapshot.vol_ratio_20_60)
  const volRatio20252Tone = toneFromVolRatio(result?.volatility_regime.snapshot.vol_ratio_20_252)
  const volPercentileTone = toneFromVolPercentile(result?.volatility_regime.snapshot.current_20d_vol_percentile)
  const confidenceTone = toneFromConfidence(result?.volatility_regime.regime.confidence)
  const modelReliabilityTone = toneFromConfidence(result?.model_reliability.confidence)

  useEffect(() => {
    if (!rollingFactorSeries.length) {
      return
    }

    setFactorChartWindow((current) => {
      if (!current) {
        return { startDate: rollingFactorSeries[0]?.date ?? '', endDate: rollingFactorSeries[rollingFactorSeries.length - 1]?.date ?? '' }
      }

      return current
    })
  }, [rollingFactorSeries])

  if (!result) {
    return (
      <article className="panel">
        <p className="panel-label">Exposure</p>
        <h2>Core exposure and factor model</h2>
        <p className="lead compact-lead">Import a portfolio from the Dashboard to inspect benchmark risk, factor loadings, regime metrics, and look-through exposure.</p>
      </article>
    )
  }

  const diagnosticsUnavailable = result.availability?.historical_sections_available === false

  const topRiskPath = [
    {
      label: `Beta vs ${result.risk_summary.benchmark_symbol}`,
      value: formatNumber(result.risk_summary.portfolio_beta, 2),
      tone: betaTone,
      detail: riskBetaStats ? `${formatNumber(riskBetaStats.min, 2)} to ${formatNumber(riskBetaStats.max, 2)}` : `${result.risk_summary.observations} obs`,
    },
    {
      label: 'Tracking Error',
      value: formatPct(result.relative_risk.tracking_error_pct),
      tone: trackingErrorTone,
      detail: result.relative_risk.active_return_pct == null ? 'Active return n/a' : `Active return ${formatPct(result.relative_risk.active_return_pct)}`,
    },
    {
      label: '20d Realized Vol',
      value: formatPct(result.volatility_regime.snapshot.realized_vol_20d),
      tone: realizedVol20Tone,
      detail: vol20Stats ? `${formatPct(vol20Stats.min)} to ${formatPct(vol20Stats.max)}` : 'Range n/a',
    },
    {
      label: 'Regime',
      value: result.volatility_regime.regime.label,
      tone: confidenceTone,
      detail: `${result.volatility_regime.regime.confidence} confidence`,
    },
  ]

  return (
    <article className="panel">
      <div className="section-header-inline exposure-header-row">
        <div>
          <p className="panel-label">Exposure</p>
          <h2>Core exposure and factor model</h2>
        </div>
        {snapshotOptions.length ? (
          <label className="exposure-snapshot-picker">
            <span className="field-label">Snapshot</span>
            <select className="path-input exposure-snapshot-select" value={selectedSnapshotId} onChange={(event) => onSnapshotSelect?.(event.target.value)}>
              {snapshotOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
            </select>
          </label>
        ) : null}
      </div>
      {diagnosticsUnavailable ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Current exposure is available, but historical diagnostics are unavailable for this snapshot.</p>
          <p className="helper">{result.availability?.note ?? 'Current holdings, look-through exposure, and overlap are shown below. Historical factor and risk sections require persisted import history.'}</p>
        </div>
      ) : null}
      {scenarioPreview ? (
        <div className="summary-card strategy-summary-card dashboard-edit-summary-card">
          <p className="stat-label">Scenario Preview</p>
          <p className="summary-value">{formatRatio(scenarioPreview.leverage_ratio)}x leverage</p>
          <p className="helper">Net {formatMoney(scenarioPreview.net_capital)} vs base {formatMoney(scenarioPreview.base_capital)} · gross {formatMoney(scenarioPreview.gross_exposure)}</p>
          <p className="helper">{scenarioPreview.methodology}</p>
        </div>
      ) : null}

      {scenarioPreview ? (
        <section className="dashboard-bottom-grid exposure-primary-section exposure-top-path-section">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Scenario Drift</p></div>
            <p className="helper">Current-state sections update from draft holdings edits; historical sections remain baseline.</p>
          </div>
          <div className="split-grid">
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Sector Shift</p></div><p className="helper">Largest weight changes vs imported portfolio</p></div>
              <div className="list-table">
                {sectorDrifts.map((item) => (
                  <div className="list-row" key={`scenario-sector-${item.name}`}>
                    <span>{item.name}</span>
                    <span>{formatPct(item.scenario_weight * 100)} ({formatSignedPct(item.delta_weight * 100)})</span>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Position Shift</p></div><p className="helper">Largest size changes in the draft scenario</p></div>
              <div className="list-table">
                {positionDrifts.map((item) => (
                  <div className="list-row" key={`scenario-position-${item.symbol}`}>
                    <span>{item.symbol}</span>
                    <span>{formatMoney(item.scenario_market_value)} ({formatSignedNumber(item.delta_market_value)})</span>
                  </div>
                ))}
              </div>
            </section>
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Factor Shift</p></div><p className="helper">Current snapshot deltas from the baseline import</p></div>
              <div className="list-table">
                {factorDrifts.map((item) => (
                  <div className="list-row" key={`scenario-factor-${item.factor}`}>
                    <span>{item.factor}</span>
                    <span>{item.unit === 'ratio' ? `${formatNumber(item.scenario_exposure, 2)} (${formatSignedNumber(item.delta_exposure, 2)})` : `${formatPct(item.scenario_exposure * 100)} (${formatSignedPct(item.delta_exposure * 100)})`}</span>
                  </div>
                ))}
              </div>
            </section>
          </div>
        </section>
      ) : null}

      <section className="dashboard-bottom-grid exposure-primary-section exposure-top-path-section">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Risk Path</p></div>
          <p className="helper">Fast read of benchmark sensitivity, active risk, realized volatility, and current regime.{scenarioPreview ? ' Historical baseline from the imported analysis.' : ''}</p>
        </div>
        <div className="risk-path-grid">
          {topRiskPath.map((item) => (
            <div className={metricCardClass(item.tone)} key={item.label}>
              <p className="stat-label">{item.label}</p>
              <p className={`summary-value ${signalToneClass(item.tone)} regime-value`}>{item.value}</p>
              <p className="helper">{item.detail}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="dashboard-bottom-grid exposure-primary-section exposure-priority-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Broad Market Risk</p></div><p className="helper">{result.risk_summary.observations} obs · {result.risk_summary.start_date ?? 'n/a'} to {result.risk_summary.end_date ?? 'n/a'}{scenarioPreview ? ' · baseline historical model' : ''}</p></div>
        <div className="market-risk-layout">
          <div className="dashboard-summary market-risk-grid market-risk-grid-dense">
          <div className={metricCardClass(overlapTone)}>
            <p className="stat-label">Portfolio in {result.market_overlap.benchmark_symbol} Names</p>
            <p className={`summary-value ${signalToneClass(overlapTone)}`}>{formatPct(result.market_overlap.portfolio_in_benchmark_weight * 100)}</p>
            <p className="helper">Look-through overlap inside benchmark constituents</p>
          </div>
          <div className={metricCardClass(activeShareTone)}>
            <p className="stat-label">Active Share vs {result.market_overlap.benchmark_symbol}</p>
            <p className={`summary-value ${signalToneClass(activeShareTone)}`}>{formatPct(result.market_overlap.active_share * 100)}</p>
            <p className="helper">Lower reads closer to benchmark construction</p>
          </div>
          <div className={metricCardClass(trackingErrorTone)}>
            <p className="stat-label">Tracking Error</p>
            <p className={`summary-value ${signalToneClass(trackingErrorTone)}`}>{formatPct(result.relative_risk.tracking_error_pct)}</p>
            <p className="helper">Benchmark-relative daily active-risk estimate</p>
          </div>
          <div className={metricCardClass(informationRatioTone)}>
            <p className="stat-label">Information Ratio</p>
            <p className={`summary-value ${signalToneClass(informationRatioTone)}`}>{formatRatio(result.relative_risk.information_ratio)}</p>
            <p className="helper">Active return {formatPct(result.relative_risk.active_return_pct)}</p>
          </div>
          </div>
          <div className="summary-card market-risk-method-card">
            <p className="stat-label">Method</p>
            <p className="helper">{result.risk_summary.methodology}</p>
            <div className="market-risk-method-meta">
              <p className="helper">Volatility {formatPct(result.risk_summary.portfolio_volatility_pct)} vs {result.risk_summary.benchmark_symbol} {formatPct(result.risk_summary.benchmark_volatility_pct)}</p>
              <p className="helper">Window {result.risk_summary.start_date ?? 'n/a'} to {result.risk_summary.end_date ?? 'n/a'}</p>
            </div>
          </div>
        </div>
      </section>

      <div className="split-grid dashboard-bottom-grid volatility-chart-grid exposure-volatility-row">
        <ExposureChartCard
          title="Volatility"
          controls={<div className="toggle-group risk-window-selector" aria-label="Combined risk window selector">{ROLLING_WINDOW_OPTIONS.map((window) => <button className={`toggle-chip${combinedRiskWindow === window ? ' active' : ''}`} key={window} onClick={() => setCombinedRiskWindow(window)} type="button">{window}d</button>)}</div>}
          chartClassName="risk-combined-chart-panel"
          data={result.volatility_regime.rolling_series}
          yAxisFormatter={formatAxisPct}
          lines={combinedRiskLines}
        />

        <ExposureChartCard
          title="Drawdown"
          helperRight={`Wealth Index ${formatNumber(result.volatility_regime.rolling_series[result.volatility_regime.rolling_series.length - 1]?.wealth_index, 2)}`}
          chartClassName="risk-drawdown-chart-panel"
          data={drawdownRiskSeries}
          yAxisFormatter={formatAxisPct}
          rightAxisFormatter={(value) => formatNumber(Number(value), 2)}
          showZeroReference
          lines={[
            { key: 'drawdown_pct', label: 'Drawdown', color: '#d85a51', strokeWidth: 2.1, axisId: 'left' },
            { key: `beta_${rollingWindow}d`, label: `Beta ${rollingWindow}d`, color: '#cf8a4a', strokeWidth: 1.9, axisId: 'right' },
            { key: `correlation_${rollingWindow}d`, label: `Correlation ${rollingWindow}d`, color: '#6c88a6', strokeWidth: 1.8, axisId: 'right' },
          ]}
        />
      </div>

      <section className="dashboard-bottom-grid exposure-primary-section">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Benchmark Sensitivity</p></div><p className="helper">Current broad-market sensitivity aligned with the drawdown horizon. {formatCoverageLabel(rollingRiskCoverage)}{scenarioPreview ? ' Historical baseline only.' : ''}</p></div>
        <div className="dashboard-summary compact-summary-grid">
          <div className={metricCardClass(betaTone)}>
            <p className="stat-label">Beta vs {result.risk_summary.benchmark_symbol}</p>
            <p className={`summary-value ${signalToneClass(betaTone)}`}>{formatNumber(result.risk_summary.portfolio_beta, 2)}</p>
            <RangeContext stats={riskBetaStats} formatter={(value) => formatNumber(value, 2)} tone={betaTone} />
          </div>
          <div className={metricCardClass(correlationTone)}>
            <p className="stat-label">Correlation vs {result.risk_summary.benchmark_symbol}</p>
            <p className={`summary-value ${signalToneClass(correlationTone)}`}>{formatNumber(result.risk_summary.portfolio_correlation, 2)}</p>
            <p className="helper">R-squared {formatNumber(result.risk_summary.r_squared, 2)}</p>
            <RangeContext stats={riskCorrelationStats} formatter={(value) => formatNumber(value, 2)} tone={correlationTone} />
          </div>
        </div>
      </section>

      <section className="dashboard-bottom-grid factor-master-detail-section">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Rolling Factor Loadings</p></div>
          <p className="helper">{formatCoverageLabel(rollingFactorCoverage)}{selectedWindowSummary ? ` · status ${selectedWindowSummary.status}` : ''}{scenarioPreview ? ' · baseline historical loadings' : ''}</p>
        </div>
        <div className="dashboard-summary compact-summary-grid">
          <div className={metricCardClass(modelReliabilityTone)}>
            <p className="stat-label">Model Confidence</p>
            <p className={`summary-value ${signalToneClass(modelReliabilityTone)}`}>{result.model_reliability.confidence}</p>
            <p className="helper">{result.model_reliability.status} · {result.model_reliability.observation_count} obs</p>
          </div>
          <div className="summary-card metric-card metric-card-neutral">
            <p className="stat-label">R-Squared</p>
            <p className="summary-value">{formatNumber(result.model_reliability.r_squared, 2)}</p>
            <p className="helper">Current {result.model_reliability.window_days}d regression fit</p>
          </div>
          <div className="summary-card metric-card metric-card-neutral">
            <p className="stat-label">Residual Vol</p>
            <p className="summary-value">{formatPct(result.model_reliability.residual_volatility)}</p>
            <p className="helper">Unexplained volatility after factors</p>
          </div>
          <div className="summary-card metric-card metric-card-neutral">
            <p className="stat-label">Collinearity Pairs</p>
            <p className="summary-value">{result.model_reliability.collinearity_pair_count}</p>
            <p className="helper">High-overlap factor pairs in the active window</p>
          </div>
        </div>
        <div className="factor-chart-toolbar factor-chart-toolbar-inline">
          <div className="factor-chart-toolbar-group">
            <p className="stat-label">Window</p>
            <div className="toggle-group factor-toggle-group" aria-label="Rolling loading window selector">{ROLLING_WINDOW_OPTIONS.map((window) => <button className={`toggle-chip factor-toggle-chip${rollingWindow === window ? ' active' : ''}`} key={window} onClick={() => setRollingWindow(window)} type="button">{window}d</button>)}</div>
          </div>
          <div className="factor-chart-toolbar-group">
            <p className="stat-label">Group</p>
            <div className="toggle-group factor-toggle-group" aria-label="Factor group filter">
              <button className={`toggle-chip factor-toggle-chip${factorFilter === 'all' ? ' active' : ''}`} onClick={() => setFactorFilter('all')} type="button">All</button>
              <button className={`toggle-chip factor-toggle-chip${factorFilter === 'market_style' ? ' active' : ''}`} onClick={() => setFactorFilter('market_style')} type="button">Market/Style</button>
              <button className={`toggle-chip factor-toggle-chip${factorFilter === 'sectors' ? ' active' : ''}`} onClick={() => setFactorFilter('sectors')} type="button">Sectors</button>
              <button className={`toggle-chip factor-toggle-chip${factorFilter === 'macro' ? ' active' : ''}`} onClick={() => setFactorFilter('macro')} type="button">Macro</button>
            </div>
          </div>
        </div>
        <div className="line-chart-panel compact-chart-panel factor-loading-chart-panel">
            {rollingFactorSeries.length ? (
              <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                <LineChart data={rollingFactorSeries} margin={{ top: 18, right: 18, left: 8, bottom: 18 }}>
                  <CartesianGrid stroke="rgba(70, 82, 98, 0.18)" strokeDasharray="3 3" />
                  <ReferenceLine y={0} stroke="rgba(156, 169, 184, 0.34)" strokeDasharray="5 5" />
                  <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} tickMargin={10} minTickGap={28} interval="preserveStartEnd" padding={{ left: 18, right: 18 }} tickFormatter={formatDateLabel} axisLine={{ stroke: 'rgba(88, 101, 118, 0.42)' }} tickLine={{ stroke: 'rgba(88, 101, 118, 0.42)' }} />
                  <YAxis tick={{ fill: '#748295', fontSize: 10 }} tickMargin={8} width={52} domain={factorChartDomain} axisLine={{ stroke: 'rgba(88, 101, 118, 0.42)' }} tickLine={{ stroke: 'rgba(88, 101, 118, 0.42)' }} />
                  <Tooltip content={(props) => <ChartTooltip {...props} registry={factorRegistryByKey} orderByKey={factorOrderByKey} />} />
                  {visibleFactorKeys.map((key) => {
                    const factor = factorRegistryByKey[key]
                    if (!factor) return null
                    return <Line key={key} type="monotone" dataKey={key} name={`${factor.label} (${factor.us_proxy})`} stroke={FACTOR_LINE_COLORS[key] ?? '#748295'} dot={false} strokeWidth={hoveredFactorKey === key ? 2.6 : 1.8} opacity={hoveredFactorKey && hoveredFactorKey !== key ? 0.2 : 1} isAnimationActive={false} />
                  })}
                  {hasRenderableBrush(factorChartSelection, rollingFactorSeries) ? (
                    <Brush
                      dataKey="date"
                      height={24}
                      stroke="#6d8095"
                      fill="rgba(11, 16, 24, 0.94)"
                      travellerWidth={8}
                      startIndex={factorChartSelection?.startIndex ?? 0}
                      endIndex={factorChartSelection?.endIndex ?? rollingFactorSeries.length - 1}
                      tickFormatter={formatDateLabel}
                      onChange={(next) => {
                        if (next?.startIndex == null || next?.endIndex == null) return
                        const startDate = rollingFactorSeries[next.startIndex]?.date
                        const endDate = rollingFactorSeries[next.endIndex]?.date
                        if (!startDate || !endDate) return
                        setFactorChartWindow({ startDate, endDate })
                      }}
                    />
                  ) : null}
                </LineChart>
              </ResponsiveContainer>
            ) : (
              <div className="empty-state-panel chart-empty-state">
                <p className="empty-state-title">Not enough history for {rollingWindow}d rolling factor loadings.</p>
                <p className="helper">This view starts once the selected window has enough observations. Available observations: {selectedWindowSummary?.observations ?? 0}</p>
              </div>
            )}
        </div>
        <div className="factor-chart-toggle-row" aria-label="Visible factors on rolling factor chart">
          {factorToggleKeys.map((key) => {
            const factor = factorRegistryByKey[key]
            if (!factor) return null

            const hidden = hiddenFactors.has(key)
            return (
              <button
                className={`factor-chart-toggle-chip${hidden ? '' : ' active'}`}
                key={`chart-toggle-${key}`}
                onClick={() => setHiddenFactors((current) => {
                  const next = new Set(current)
                  if (next.has(key)) next.delete(key)
                  else next.add(key)
                  return next
                })}
                onMouseEnter={() => setHoveredFactorKey(key)}
                onMouseLeave={() => setHoveredFactorKey(null)}
                aria-pressed={!hidden}
                title={hidden ? 'Show factor on chart' : 'Hide factor from chart'}
                type="button"
              >
                <span className="factor-chart-toggle-dot" style={{ backgroundColor: FACTOR_LINE_COLORS[key] ?? '#748295' }} />
                <span>{factor.label}</span>
              </button>
            )
          })}
        </div>
        <div className="factor-master-detail-layout factor-master-detail-layout-full">
          <div>
            <div className="section-header-inline sector-list-header factor-detail-header">
              <div><p className="panel-label">Current Factor Snapshot</p></div>
              <button
                className="toggle-chip factor-toggle-chip factor-snapshot-collapse-chip"
                onClick={() => setFactorSnapshotCollapsed((value) => !value)}
                aria-expanded={!factorSnapshotCollapsed}
                type="button"
              >
                {factorSnapshotCollapsed ? 'Show details' : 'Hide details'}
              </button>
            </div>
            {!factorSnapshotCollapsed ? (
              <>
                <div className="factor-snapshot-meta-row">
                  <p className="helper">Methodology: {resolvedFactorModel?.methodology ?? result.factor_methodology ?? DEFAULT_FACTOR_MODEL_METHODOLOGY}</p>
                  <p className="helper">Window status: {selectedWindowSummary?.status ?? resolvedFactorModel?.statistical_factor_model.status ?? 'n/a'}</p>
                  <p className="helper">Observations: {selectedWindowSummary?.observations ?? 0}</p>
                  <p className="helper">Table shows current snapshot plus selected {rollingWindow}d window loadings.</p>
                  <p className="helper">Benchmark: {resolvedFactorModel?.statistical_factor_model.benchmark_symbol ?? result.benchmark?.symbol ?? 'SPY'}</p>
                  <p className="helper">Reliability: {result.model_reliability.confidence} confidence{scenarioPreview ? ' · current values in this table are scenario-aware, rolling ranges stay baseline' : ''}</p>
                </div>
                <div className="factor-snapshot-table-wrap">
              <div className="factor-snapshot-table-grid factor-snapshot-header-row">
                <span>Factor</span>
                <span>Proxy</span>
                <span>Current Loading</span>
                <span>{rollingWindow}d Loading</span>
                <span>Category</span>
                <span>UCITS Examples</span>
                <span>Mapping Match</span>
                <span>Description</span>
              </div>
                  {sortedSnapshotFactors.map((factor) => {
                    const loadingStats = getSeriesStats(factorLoadingSeries as Array<Record<string, number | string | null>>, factor.key)
                    const selectedWindowLoading = getSelectedWindowFactorLoading(resolvedFactorModel, rollingWindow, factor.key)
                    const loadingTone = toneFromFactorLoading(factor.latest_loading)
                    const selectedWindowTone = toneFromFactorLoading(selectedWindowLoading)
                    const matchScore = mappingMatchScore(factor, factorRegistryByKey)
                    const matchTone = toneFromMappingMatch(matchScore)
                    return (
                      <button
                        className={`factor-snapshot-table-grid factor-snapshot-data-row${hoveredFactorKey === factor.key ? ' active' : ''}${hiddenFactors.has(factor.key) ? ' muted' : ''}`}
                        key={factor.key}
                        onClick={() => setHiddenFactors((current) => {
                          const next = new Set(current)
                          if (next.has(factor.key)) next.delete(factor.key)
                          else next.add(factor.key)
                          return next
                        })}
                        onMouseEnter={() => setHoveredFactorKey(factor.key)}
                        onMouseLeave={() => setHoveredFactorKey(null)}
                        aria-pressed={!hiddenFactors.has(factor.key)}
                        title={hiddenFactors.has(factor.key) ? 'Show factor on chart' : 'Hide factor from chart'}
                        type="button"
                      >
                        <span className="factor-snapshot-primary-cell"><span className="factor-snapshot-primary">{factor.label}</span>{hiddenFactors.has(factor.key) ? <span className="factor-row-state-badge">Hidden</span> : null}</span>
                        <span className="factor-snapshot-proxy">{factor.us_proxy}</span>
                        <span className="factor-loading-cell"><span className={`factor-loading-value ${signalToneClass(loadingTone)}`}>{formatLoading(factor.latest_loading)}</span><MiniRangeContext stats={loadingStats} formatter={(value) => formatNumber(value, 2)} tone={loadingTone} /></span>
                        <span className={`factor-loading-value ${signalToneClass(selectedWindowTone)}`}>{formatLoading(selectedWindowLoading)}</span>
                        <span><span className="factor-category-badge">{FACTOR_CATEGORY_LABELS[factor.category] ?? factor.category}</span></span>
                        <span className={`factor-snapshot-ucits${factor.ucits_examples.length ? '' : ' factor-snapshot-ucits-empty'}`}>{factor.ucits_examples.length ? factor.ucits_examples.join(', ') : 'No mapped UCITS example yet'}</span>
                        <span className="mapping-cell">
                          <span className="mapping-score-stack">
                            <span className="mapping-score-caption">{mappingMatchCaption(factor, factorRegistryByKey)}</span>
                            <span className={`mapping-score-value ${signalToneClass(matchTone)}`}>{formatMappingScore(matchScore)}</span>
                          </span>
                          <span className={`mapping-badge mapping-${factor.mapping_quality}`}>{mappingQualityBadge(factor.mapping_quality)}</span>
                        </span>
                        <span className="factor-snapshot-description">{factor.description}</span>
                      </button>
                    )
                  })}
                </div>
              </>
            ) : null}
          </div>
        </div>
      </section>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Volatility & Regime</p></div><p className="helper">{formatCoverageLabel(volatilityCoverage)}{scenarioPreview ? ' · imported historical baseline' : ''}</p></div>
        <div className="factor-snapshot-meta-row">
          <p className="helper">Methodology: {result.volatility_regime.methodology}</p>
          <p className="helper">Return Basis: {result.volatility_regime.assumptions.return_basis}</p>
          <p className="helper">Drawdown Basis: {result.volatility_regime.assumptions.drawdown_basis}</p>
          <p className="helper">Benchmark Basis: {result.volatility_regime.assumptions.benchmark_basis}</p>
        </div>
        <div className="dashboard-summary volatility-summary-grid">
          <div className={metricCardClass(realizedVol20Tone)}><p className="stat-label">Realized Vol 20d</p><p className={`summary-value ${signalToneClass(realizedVol20Tone)}`}>{formatPct(result.volatility_regime.snapshot.realized_vol_20d)}</p><RangeContext stats={vol20Stats} formatter={formatPct} tone={realizedVol20Tone} /></div>
          <div className={metricCardClass(realizedVol60Tone)}><p className="stat-label">Realized Vol 60d</p><p className={`summary-value ${signalToneClass(realizedVol60Tone)}`}>{formatPct(result.volatility_regime.snapshot.realized_vol_60d)}</p><RangeContext stats={vol60Stats} formatter={formatPct} tone={realizedVol60Tone} /></div>
          <div className={metricCardClass(realizedVol252Tone)}><p className="stat-label">Realized Vol 252d</p><p className={`summary-value ${signalToneClass(realizedVol252Tone)}`}>{formatPct(result.volatility_regime.snapshot.realized_vol_252d)}</p><RangeContext stats={vol252Stats} formatter={formatPct} tone={realizedVol252Tone} /></div>
          <div className={metricCardClass(benchmarkVol20Tone)}><p className="stat-label">Benchmark Vol 20d</p><p className={`summary-value ${signalToneClass(benchmarkVol20Tone)}`}>{formatPct(result.volatility_regime.snapshot.benchmark_vol_20d)}</p><RangeContext stats={benchmarkVol20Stats} formatter={formatPct} tone={benchmarkVol20Tone} /></div>
          <div className={metricCardClass(benchmarkVol60Tone)}><p className="stat-label">Benchmark Vol 60d</p><p className={`summary-value ${signalToneClass(benchmarkVol60Tone)}`}>{formatPct(result.volatility_regime.snapshot.benchmark_vol_60d)}</p><RangeContext stats={benchmarkVol60Stats} formatter={formatPct} tone={benchmarkVol60Tone} /></div>
          <div className={metricCardClass(benchmarkVol252Tone)}><p className="stat-label">Benchmark Vol 252d</p><p className={`summary-value ${signalToneClass(benchmarkVol252Tone)}`}>{formatPct(result.volatility_regime.snapshot.benchmark_vol_252d)}</p><RangeContext stats={benchmarkVol252Stats} formatter={formatPct} tone={benchmarkVol252Tone} /></div>
          <div className={metricCardClass(downsideVol20Tone)}><p className="stat-label">Downside Vol 20d</p><p className={`summary-value ${signalToneClass(downsideVol20Tone)}`}>{formatPct(result.volatility_regime.snapshot.downside_vol_20d)}</p><RangeContext stats={downside20Stats} formatter={formatPct} tone={downsideVol20Tone} /></div>
          <div className={metricCardClass(downsideVol60Tone)}><p className="stat-label">Downside Vol 60d</p><p className={`summary-value ${signalToneClass(downsideVol60Tone)}`}>{formatPct(result.volatility_regime.snapshot.downside_vol_60d)}</p><RangeContext stats={downside60Stats} formatter={formatPct} tone={downsideVol60Tone} /></div>
          <div className={metricCardClass(downsideVol252Tone)}><p className="stat-label">Downside Vol 252d</p><p className={`summary-value ${signalToneClass(downsideVol252Tone)}`}>{formatPct(result.volatility_regime.snapshot.downside_vol_252d)}</p><RangeContext stats={downside252Stats} formatter={formatPct} tone={downsideVol252Tone} /></div>
          <div className={metricCardClass(tracking20Tone)}><p className="stat-label">Tracking Error 20d</p><p className={`summary-value ${signalToneClass(tracking20Tone)}`}>{formatPct(result.volatility_regime.snapshot.tracking_error_20d)}</p><RangeContext stats={tracking20Stats} formatter={formatPct} tone={tracking20Tone} /></div>
          <div className={metricCardClass(tracking60Tone)}><p className="stat-label">Tracking Error 60d</p><p className={`summary-value ${signalToneClass(tracking60Tone)}`}>{formatPct(result.volatility_regime.snapshot.tracking_error_60d)}</p><RangeContext stats={tracking60Stats} formatter={formatPct} tone={tracking60Tone} /></div>
          <div className={metricCardClass(tracking252Tone)}><p className="stat-label">Tracking Error 252d</p><p className={`summary-value ${signalToneClass(tracking252Tone)}`}>{formatPct(result.volatility_regime.snapshot.tracking_error_252d)}</p><RangeContext stats={tracking252Stats} formatter={formatPct} tone={tracking252Tone} /></div>
          <div className={metricCardClass(currentDrawdownTone)}><p className="stat-label">Current Drawdown</p><p className={`summary-value ${signalToneClass(currentDrawdownTone)}`}>{formatPct(result.volatility_regime.snapshot.current_drawdown_pct)}</p><RangeContext stats={drawdownStats} formatter={formatPct} tone={currentDrawdownTone} /></div>
          <div className={metricCardClass(maxDrawdownTone)}><p className={`stat-label ${signalToneClass(maxDrawdownTone)}`}>Max Drawdown</p><p className={`summary-value ${signalToneClass(maxDrawdownTone)}`}>{formatPct(result.volatility_regime.snapshot.max_drawdown_pct)}</p></div>
          <div className={metricCardClass(volRatio2060Tone)}><p className="stat-label">Vol Ratio 20/60</p><p className={`summary-value ${signalToneClass(volRatio2060Tone)}`}>{formatRatio(result.volatility_regime.snapshot.vol_ratio_20_60)}</p></div>
          <div className={metricCardClass(volRatio20252Tone)}><p className="stat-label">Vol Ratio 20/252</p><p className={`summary-value ${signalToneClass(volRatio20252Tone)}`}>{formatRatio(result.volatility_regime.snapshot.vol_ratio_20_252)}</p></div>
          <div className={metricCardClass(volPercentileTone)}><p className="stat-label">20d Vol Percentile</p><p className={`summary-value ${signalToneClass(volPercentileTone)}`}>{formatPercentile(result.volatility_regime.snapshot.current_20d_vol_percentile)}</p></div>
          <div className="summary-card metric-card metric-card-neutral"><p className="stat-label">Regime</p><p className="summary-value regime-value">{result.volatility_regime.regime.label}</p></div>
          <div className={metricCardClass(confidenceTone)}><p className="stat-label">Confidence</p><p className={`summary-value ${signalToneClass(confidenceTone)}`}>{result.volatility_regime.regime.confidence}</p></div>
        </div>
      </section>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Factor Tilts</p></div><p className="helper">Current benchmark, style, sector, and macro sleeves.{scenarioPreview ? ' Scenario-aware from edited holdings.' : ''}</p></div>
        <div className="dashboard-summary">
          {factorExposures.map((item) => (
            <div className="summary-card" key={`factor-${item.factor}`}>
              <p className="stat-label">{item.factor}</p>
              <p className="summary-value">{item.factor === 'Market' ? formatNumber(item.exposure, 2) : formatPct(item.exposure * 100)}</p>
              <p className="helper">{item.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">EU Execution Mapping</p></div><p className="helper">US ETF analytical proxies with UCITS execution examples.</p></div>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">{resolvedFactorModel?.methodology ?? result.factor_methodology ?? DEFAULT_FACTOR_MODEL_METHODOLOGY}</p>
        </div>
      </section>

      <div className="split-grid dashboard-bottom-grid">
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Factor Registry</p></div><p className="helper">US analytical proxies and EU execution context</p></div>
          <div className="factor-registry-grid">
            {Object.entries(FACTOR_CATEGORY_LABELS).map(([categoryKey, label]) => {
              const factors = factorRegistry.filter((factor) => factor.category === categoryKey)
              if (!factors.length) return null
              return (
                <div className="factor-registry-card" key={categoryKey}>
                  <p className="stat-label">{label}</p>
                  {factors.map((factor) => <div className="factor-registry-row" key={factor.key}><span>{factor.label} / {factor.us_proxy}</span><span>{factor.ucits_examples.length ? factor.ucits_examples.join(', ') : 'No mapped UCITS example yet'}</span></div>)}
                </div>
              )
            })}
          </div>
        </section>
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Collinearity Warning</p></div><p className="helper">Informational diagnostic for overlapping factors</p></div>
          <div className="list-table">
            {selectedCollinearity?.high_collinearity_pairs.length ? selectedCollinearity.high_collinearity_pairs.map((item) => <div className="list-row" key={`collinearity-${item.left_key}-${item.right_key}`}><span>{item.left_key} / {item.right_key}</span><span>{formatNumber(item.correlation, 2)}</span></div>) : <div className="list-row"><span>No major collinearity warnings</span><span>OK</span></div>}
            {selectedCollinearity?.note ? <p className="helper collinearity-note">{selectedCollinearity.note}</p> : null}
          </div>
        </section>
      </div>

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header"><div><p className="panel-label">Stress Scenarios</p></div><p className="helper">Factor-shock estimates based on the 12-factor model{scenarioPreview ? ' · scenario-aware current-state approximation' : ''}</p></div>
        <div className="list-table">
          {scenarioStressScenarios
            ? scenarioStressScenarios.map((item) => <div className="list-row" key={`stress-${item.name}`}><span>{item.name}</span><span>{formatPct(item.estimated_return_pct)} ({formatSignedPct(item.delta_return_pct)})</span></div>)
            : result.stress_scenarios.map((item) => <div className="list-row" key={`stress-${item.name}`}><span>{item.name}</span><span>{formatPct(item.estimated_return_pct)}</span></div>)}
        </div>
        {scenarioStressScenarios ? <p className="helper">Scenario stress estimates scale baseline shocks from edited holdings mix and current factor tilts; they do not rerun historical stress regressions.</p> : null}
      </section>

      {scenarioRiskContribution ? (
        <section className="dashboard-bottom-grid">
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Risk Contribution</p></div><p className="helper">{scenarioRiskContribution.window_days}d / {scenarioRiskContribution.observation_count} obs / {scenarioRiskContribution.status} · scenario-aware approximation</p></div>
          <div className="dashboard-summary compact-summary-grid">
            <div className="summary-card"><p className="stat-label">Factor Total Variance</p><p className="summary-value">{formatNumber(scenarioRiskContribution.factor_total_variance, 4)}</p></div>
            <div className="summary-card"><p className="stat-label">Specific Variance</p><p className="summary-value">{formatNumber(scenarioRiskContribution.specific_variance, 4)}</p></div>
            <div className="summary-card"><p className="stat-label">Total Variance</p><p className="summary-value">{formatNumber(scenarioRiskContribution.total_variance, 4)}</p></div>
            <div className="summary-card"><p className="stat-label">Factor Risk Share</p><p className="summary-value">{formatPct(scenarioRiskContribution.factor_risk_share_total != null ? scenarioRiskContribution.factor_risk_share_total * 100 : null)}</p></div>
            <div className="summary-card"><p className="stat-label">Specific Risk Share</p><p className="summary-value">{formatPct(scenarioRiskContribution.specific_risk_share != null ? scenarioRiskContribution.specific_risk_share * 100 : null)}</p></div>
            <div className="summary-card"><p className="stat-label">Residual Volatility</p><p className="summary-value">{formatPct(scenarioRiskContribution.residual_volatility)}</p></div>
          </div>
          <div className="split-grid dashboard-bottom-grid">
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Factor Contributions</p></div><p className="helper">Approximate current factor concentration from scenario weights</p></div>
              <div className="list-table">{scenarioRiskContribution.factor_contributions.slice(0, 6).map((item) => <div className="list-row" key={`scenario-factor-contrib-${item.key}`}><span>{item.label}</span><span>{formatPct(item.risk_share != null ? item.risk_share * 100 : null)}</span></div>)}</div>
            </section>
            <section>
              <div className="section-header-inline sector-list-header"><div><p className="panel-label">Position Contributions</p></div><p className="helper">Approximate current position concentration from scenario weights</p></div>
              <div className="list-table">{scenarioRiskContribution.position_contributions.slice(0, 6).map((item) => <div className="list-row" key={`scenario-position-contrib-${item.symbol}`}><span>{item.symbol}</span><span>{formatPct(item.risk_share != null ? item.risk_share * 100 : null)}</span></div>)}</div>
            </section>
          </div>
          <div className="dashboard-summary compact-summary-grid">
            <div className="summary-card"><p className="stat-label">Top 1 Factor Risk Share</p><p className="summary-value">{formatPct(scenarioRiskContribution.concentration.top_1_factor_risk_share != null ? scenarioRiskContribution.concentration.top_1_factor_risk_share * 100 : null)}</p></div>
            <div className="summary-card"><p className="stat-label">Top 3 Factor Risk Share</p><p className="summary-value">{formatPct(scenarioRiskContribution.concentration.top_3_factor_risk_share != null ? scenarioRiskContribution.concentration.top_3_factor_risk_share * 100 : null)}</p></div>
            <div className="summary-card"><p className="stat-label">Top 1 Position Risk Share</p><p className="summary-value">{formatPct(scenarioRiskContribution.concentration.top_1_position_risk_share != null ? scenarioRiskContribution.concentration.top_1_position_risk_share * 100 : null)}</p></div>
            <div className="summary-card"><p className="stat-label">Top 5 Position Risk Share</p><p className="summary-value">{formatPct(scenarioRiskContribution.concentration.top_5_position_risk_share != null ? scenarioRiskContribution.concentration.top_5_position_risk_share * 100 : null)}</p></div>
            <div className="summary-card"><p className="stat-label">Factor HHI</p><p className="summary-value">{formatNumber(scenarioRiskContribution.concentration.factor_hhi, 4)}</p></div>
            <div className="summary-card"><p className="stat-label">Position HHI</p><p className="summary-value">{formatNumber(scenarioRiskContribution.concentration.position_hhi, 4)}</p></div>
          </div>
          <p className="helper">Scenario risk contribution uses edited holdings weights and current snapshot loadings as a current-state proxy. It does not rerun the underlying historical covariance engine.</p>
        </section>
      ) : null}

      <div className="split-grid dashboard-bottom-grid">
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Actual Exposure</p></div><p className="helper">Top look-through constituents by snapshot market value{scenarioPreview ? ' in the draft scenario' : ''}</p></div>
          <div className="list-table">{topLookthrough.map((item) => <div className="list-row" key={`lookthrough-${item.symbol}`}><span>{item.symbol}</span><span>{formatCompactMoney(item.effective_market_value)} · {formatPct(item.portfolio_weight * 100)}</span></div>)}</div>
          <p className="helper">Coverage {formatPct(result.lookthrough.coverage_ratio * 100)}</p>
        </section>
        <section>
          <div className="section-header-inline sector-list-header"><div><p className="panel-label">Look-Through Sectors</p></div><p className="helper">Economic exposure after ETF unpacking{scenarioPreview ? ' for the draft scenario' : ''}</p></div>
          <div className="allocation-list">{topLookthroughSectors.map((item) => <div className="allocation-row" key={`lt-sector-${item.sector}`}><div className="allocation-head"><span>{item.sector}</span><span>{formatPct(item.weight * 100)}</span></div><div className="allocation-bar"><div className="allocation-fill" style={{ width: `${Math.max(item.weight * 100, 2)}%` }} /></div></div>)}</div>
        </section>
      </div>

    </article>
  )
}
