import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TooltipContentProps } from 'recharts/types/component/Tooltip'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

import type { ExposureAnalysis, ExposureFactorModelResponse } from './types'

const SNAPSHOT_POSITIVE_COLOR = '#5b87c5'
const SNAPSHOT_NEGATIVE_COLOR = '#cf8a4a'

function formatLoading(value: number | null | undefined) {
  return value == null ? 'n/a' : value.toFixed(2)
}

function SnapshotTooltip({ active, payload }: TooltipContentProps<ValueType, NameType>) {
  if (!active || !payload?.length) return null
  const point = payload[0]?.payload as {
    label: string
    usProxy: string
    loading: number
    category: string
    ucitsExamples: string[]
  } | undefined

  if (!point) return null

  return (
    <div className="chart-tooltip-card factor-tooltip-card">
      <div className="chart-tooltip-row">
        <span className="chart-tooltip-label">{point.label} ({point.usProxy})</span>
        <span>{formatLoading(point.loading)}</span>
      </div>
      <p className="chart-tooltip-meta">{point.category}{point.ucitsExamples.length ? ` · ${point.ucitsExamples.join(', ')}` : ''}</p>
    </div>
  )
}

export function CurrentFactorSnapshotCard({ result, factorModel }: { result: ExposureAnalysis | null; factorModel: ExposureFactorModelResponse | null }) {
  const snapshot = factorModel?.statistical_factor_model.current_factor_snapshot ?? []

  const chartData = [...snapshot]
    .sort((left, right) => Math.abs(right.latest_loading ?? 0) - Math.abs(left.latest_loading ?? 0))
    .map((factor) => ({
      key: factor.key,
      label: factor.label,
      usProxy: factor.us_proxy,
      loading: factor.latest_loading ?? 0,
      category: factor.category,
      ucitsExamples: factor.ucits_examples,
      fill: (factor.latest_loading ?? 0) >= 0 ? SNAPSHOT_POSITIVE_COLOR : SNAPSHOT_NEGATIVE_COLOR,
    }))

  if (!chartData.length) {
    return null
  }

  const chartHeight = Math.max(320, chartData.length * 34)

  return (
    <section className="dashboard-bottom-grid factor-master-detail-section">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Current Factor Snapshot</p></div>
        <p className="helper">Latest factor loadings from the current model snapshot. The historical rolling factor chart is restored on the Dashboard below, while detailed factor rows remain in Exposure.</p>
      </div>
      <div className="factor-snapshot-meta-row">
        <p className="helper">Methodology: {factorModel?.methodology ?? result?.factor_methodology ?? 'n/a'}</p>
        <p className="helper">Benchmark: {factorModel?.statistical_factor_model.benchmark_symbol ?? result?.benchmark?.symbol ?? 'SPY'}</p>
        <p className="helper">Factors: {chartData.length}</p>
      </div>
      <div className="line-chart-panel compact-chart-panel factor-loading-chart-panel" aria-label="Current factor snapshot chart" style={{ height: chartHeight }}>
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <BarChart data={chartData} layout="vertical" margin={{ top: 18, right: 18, left: 8, bottom: 18 }}>
            <CartesianGrid stroke="rgba(70, 82, 98, 0.18)" strokeDasharray="3 3" horizontal={false} />
            <ReferenceLine x={0} stroke="rgba(156, 169, 184, 0.34)" strokeDasharray="5 5" />
            <XAxis type="number" tick={{ fill: '#748295', fontSize: 10 }} tickFormatter={(value) => Number(value).toFixed(2)} axisLine={{ stroke: 'rgba(88, 101, 118, 0.42)' }} tickLine={{ stroke: 'rgba(88, 101, 118, 0.42)' }} />
            <YAxis type="category" dataKey="label" width={132} tick={{ fill: '#748295', fontSize: 10 }} axisLine={{ stroke: 'rgba(88, 101, 118, 0.42)' }} tickLine={{ stroke: 'rgba(88, 101, 118, 0.42)' }} />
            <Tooltip content={(props) => <SnapshotTooltip {...props} />} />
            <Bar dataKey="loading" isAnimationActive={false} radius={[4, 4, 4, 4]}>
              {chartData.map((entry) => <Cell key={entry.key} fill={entry.fill} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </section>
  )
}
