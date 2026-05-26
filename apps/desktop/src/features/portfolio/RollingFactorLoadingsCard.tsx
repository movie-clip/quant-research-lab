import { useEffect, useMemo, useState } from 'react'
import { Brush, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TooltipContentProps } from 'recharts/types/component/Tooltip'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

import type { ExposureAnalysis, ExposureFactorModelResponse } from './types'

type RollingWindow = 20 | 60 | 252
type FactorGroupFilter = 'all' | 'market_style' | 'sectors' | 'macro'

const ROLLING_WINDOW_OPTIONS: RollingWindow[] = [20, 60, 252]
const DEFAULT_VISIBLE_FACTORS = ['market', 'growth', 'value', 'small_cap', 'technology', 'financials']

const FACTOR_CATEGORY_LABELS: Record<string, string> = {
  market: 'Market',
  style: 'Style',
  sector: 'Sector',
  macro: 'Macro',
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
  consumer_staples: '#8f9b4f',
  utilities: '#6aa3a1',
  consumer_discretionary: '#b86f9b',
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
  if (window === 60) return result.statistical_factor_model.rolling_loadings_60d ?? []
  if (window === 252) return result.statistical_factor_model.rolling_loadings_252d ?? []
  return result.statistical_factor_model.rolling_loadings_20d ?? []
}

function getWindowSummary(result: ExposureFactorModelResponse, window: RollingWindow) {
  return (result.statistical_factor_model.windows ?? []).find((item) => item.window_days === window) ?? null
}

function getCoverage<T extends { date: string }>(data: T[]) {
  if (!data.length) return null
  return { observations: data.length, startDate: data[0].date, endDate: data[data.length - 1].date }
}

function formatCoverageLabel(coverage: { observations: number; startDate: string; endDate: string } | null) {
  if (!coverage) return 'Insufficient history for the selected window'
  return `${coverage.observations} observations · ${formatDateLabel(coverage.startDate)} to ${formatDateLabel(coverage.endDate)}`
}

function hasRenderableBrush(selection: { startIndex: number; endIndex: number } | null, data: Array<{ date: string }>) {
  if (!selection) return false
  if (data.length < 2) return false
  return Number.isFinite(selection.startIndex) && Number.isFinite(selection.endIndex) && selection.endIndex > selection.startIndex
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

export function RollingFactorLoadingsCard({ result, factorModel }: { result: ExposureAnalysis | null; factorModel: ExposureFactorModelResponse | null }) {
  const [rollingWindow, setRollingWindow] = useState<RollingWindow>(60)
  const [factorFilter, setFactorFilter] = useState<FactorGroupFilter>('all')
  const [hiddenFactors, setHiddenFactors] = useState<Set<string>>(new Set())
  const [hoveredFactorKey, setHoveredFactorKey] = useState<string | null>(null)
  const [factorChartWindow, setFactorChartWindow] = useState<{ startDate: string; endDate: string } | null>(null)

  const resolvedFactorModel = factorModel
  const factorRegistry = resolvedFactorModel?.factor_registry ?? []
  const factorRegistryByKey = useMemo(() => Object.fromEntries(factorRegistry.map((factor) => [factor.key, factor])), [factorRegistry])
  const selectedWindowSummary = resolvedFactorModel ? getWindowSummary(resolvedFactorModel, rollingWindow) : null

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
  const rollingFactorCoverage = useMemo(() => getCoverage(rollingFactorSeries), [rollingFactorSeries])
  const scenarioPreview = result?.scenario_preview ?? null

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

  if (!result || !resolvedFactorModel || !factorRegistry.length) {
    return null
  }

  return (
    <section className="dashboard-bottom-grid factor-master-detail-section">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Rolling Factor Analysis</p></div>
        <p className="helper">{formatCoverageLabel(rollingFactorCoverage)}{scenarioPreview ? ' · scenario edits do not rerun these loadings.' : ''}</p>
      </div>
      <div className="factor-chart-toolbar factor-chart-toolbar-inline">
        <div className="factor-chart-toolbar-group">
          <div className="toggle-group factor-toggle-group" aria-label="Rolling loading window selector">
            {ROLLING_WINDOW_OPTIONS.map((window) => <button className={`toggle-chip factor-toggle-chip${rollingWindow === window ? ' active' : ''}`} key={window} onClick={() => setRollingWindow(window)} type="button">{window}d</button>)}
          </div>
        </div>
        <div className="factor-chart-toolbar-group">
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
    </section>
  )
}
