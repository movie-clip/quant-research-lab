import { useState } from 'react'
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { RollingRiskPoint } from './types'

// ── Types ────────────────────────────────────────────────────────────────────

type CorrelationWindow = 20 | 60 | 252

const WINDOW_OPTIONS: CorrelationWindow[] = [20, 60, 252]
const WINDOW_LABELS: Record<CorrelationWindow, string> = { 20: '20d', 60: '60d', 252: '252d' }

type ChartPoint = {
  date: string
  correlation: number | null
  beta: number | null
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function formatDateLabel(value: string | number | null | undefined): string {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return String(value)
  return `${month}/${day}/${year.slice(2)}`
}

function formatVal(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2)
}

function buildChartData(points: RollingRiskPoint[], window: CorrelationWindow): ChartPoint[] {
  const corrKey = `correlation_${window}d` as keyof RollingRiskPoint
  const betaKey = `beta_${window}d` as keyof RollingRiskPoint
  return points.map((p) => ({
    date: p.date,
    correlation: (p[corrKey] as number | null) ?? null,
    beta: (p[betaKey] as number | null) ?? null,
  }))
}

function hasAnyData(data: ChartPoint[]): boolean {
  return data.some((p) => p.correlation != null || p.beta != null)
}

// ── Custom tooltip ────────────────────────────────────────────────────────────

type TooltipProps = {
  active?: boolean
  payload?: Array<{ dataKey: string; value: number | null | undefined; color: string }>
  label?: string
}

function CorrelationTooltip({ active, payload, label }: TooltipProps) {
  if (!active || !payload || payload.length === 0) return null
  const corrEntry = payload.find((p) => p.dataKey === 'correlation')
  const betaEntry = payload.find((p) => p.dataKey === 'beta')
  return (
    <div style={{ background: '#1a212b', border: '1px solid #2d3748', borderRadius: 8, padding: '8px 12px', fontSize: 12, lineHeight: 1.6 }}>
      <p style={{ margin: '0 0 4px', color: '#94a3b8', fontSize: 11 }}>{formatDateLabel(label)}</p>
      <p style={{ margin: 0, color: corrEntry?.color ?? '#5b87c5' }}>
        Correlation (ρ): <strong>{formatVal(corrEntry?.value)}</strong>
      </p>
      <p style={{ margin: 0, color: betaEntry?.color ?? '#3cb79f' }}>
        Beta (β): <strong>{formatVal(betaEntry?.value)}</strong>
      </p>
    </div>
  )
}

// ── Window selector ───────────────────────────────────────────────────────────

function WindowSelector({ value, onChange }: { value: CorrelationWindow; onChange: (w: CorrelationWindow) => void }) {
  return (
    <div style={{ display: 'flex', gap: '4px' }}>
      {WINDOW_OPTIONS.map((w) => (
        <button
          key={w}
          type="button"
          aria-label={`${WINDOW_LABELS[w]} window`}
          onClick={() => { onChange(w) }}
          style={{
            padding: '2px 8px',
            fontSize: '12px',
            borderRadius: '3px',
            border: '1px solid',
            borderColor: value === w ? '#5b87c5' : '#2d3448',
            backgroundColor: value === w ? '#1d3350' : 'transparent',
            color: value === w ? '#5b87c5' : '#6b7280',
            cursor: 'pointer',
          }}
        >
          {WINDOW_LABELS[w]}
        </button>
      ))}
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

type RollingCorrelationChartProps = {
  rollingRisk: RollingRiskPoint[]
}

export function RollingCorrelationChart({ rollingRisk }: RollingCorrelationChartProps) {
  const [window, setWindow] = useState<CorrelationWindow>(60)

  const chartData = buildChartData(rollingRisk, window)
  const hasData = hasAnyData(chartData)

  return (
    <section className="compact-chart-panel">
      {/* Header */}
      <div className="section-header-inline sector-list-header exposure-section-header" style={{ marginBottom: 12 }}>
        <div className="panel-section-title-block">
          <p className="panel-label" style={{ display: 'inline' }}>Rolling Correlation &amp; Beta</p>
          <span
            className="attribution-trust-badge"
            title="Computed from current holdings applied to historical prices. Not verified broker return basis."
            style={{ marginLeft: 8 }}
          >
            Synthetic
          </span>
        </div>
        <WindowSelector value={window} onChange={setWindow} />
      </div>

      {/* Chart or empty state */}
      {!hasData ? (
        <p className="helper" style={{ textAlign: 'center', padding: '32px 0' }}>
          Insufficient history for {window}d rolling window.
        </p>
      ) : (
        <div style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 4, right: 56, bottom: 4, left: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDateLabel}
                tick={{ fontSize: 11, fill: '#94a3b8' }}
                minTickGap={40}
              />
              {/* Left axis: Correlation */}
              <YAxis
                yAxisId="correlation"
                orientation="left"
                domain={[-1, 1]}
                ticks={[-1, -0.5, 0, 0.5, 1]}
                tickFormatter={(v: number) => v.toFixed(1)}
                tick={{ fontSize: 11, fill: '#5b87c5' }}
                width={44}
                label={{ value: 'Correlation (ρ)', angle: -90, position: 'insideLeft', offset: 12, style: { fontSize: 10, fill: '#5b87c5' } }}
              />
              {/* Right axis: Beta */}
              <YAxis
                yAxisId="beta"
                orientation="right"
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => v.toFixed(1)}
                tick={{ fontSize: 11, fill: '#3cb79f' }}
                width={44}
                label={{ value: 'Beta (β)', angle: 90, position: 'insideRight', offset: 12, style: { fontSize: 10, fill: '#3cb79f' } }}
              />
              <ReferenceLine yAxisId="correlation" y={0} stroke="#5b87c5" strokeDasharray="3 3" strokeOpacity={0.5} />
              <ReferenceLine yAxisId="beta" y={1} stroke="#3cb79f" strokeDasharray="3 3" strokeOpacity={0.5} />
              <Tooltip content={<CorrelationTooltip />} />
              <Line
                yAxisId="correlation"
                type="monotone"
                dataKey="correlation"
                name="Correlation (ρ)"
                stroke="#5b87c5"
                dot={false}
                connectNulls={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
              <Line
                yAxisId="beta"
                type="monotone"
                dataKey="beta"
                name="Beta (β)"
                stroke="#3cb79f"
                dot={false}
                connectNulls={false}
                strokeWidth={2}
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  )
}
