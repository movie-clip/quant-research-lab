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
    <div style={{ background: 'var(--color-surface-elevated)', border: 'var(--border-thin) solid var(--color-border-card)', borderRadius: 'var(--radius-md)', padding: 'var(--space-sm) var(--space-md)', fontSize: 'var(--font-caption)', lineHeight: 1.6 }}>
      <p style={{ margin: '0 0 var(--space-xs)', color: 'var(--color-text-muted)', fontSize: 'var(--font-chart-tick)' }}>{formatDateLabel(label)}</p>
      <p style={{ margin: 0, color: corrEntry?.color ?? 'var(--color-line-correlation)' }}>
        Correlation (ρ): <strong>{formatVal(corrEntry?.value)}</strong>
      </p>
      <p style={{ margin: 0, color: betaEntry?.color ?? 'var(--color-line-beta)' }}>
        Beta (β): <strong>{formatVal(betaEntry?.value)}</strong>
      </p>
    </div>
  )
}

// ── Window selector ───────────────────────────────────────────────────────────

function WindowSelector({ value, onChange }: { value: CorrelationWindow; onChange: (w: CorrelationWindow) => void }) {
  return (
    <div style={{ display: 'flex', gap: 'var(--space-xs)' }}>
      {WINDOW_OPTIONS.map((w) => (
        <button
          key={w}
          type="button"
          aria-label={`${WINDOW_LABELS[w]} window`}
          onClick={() => { onChange(w) }}
          style={{
            padding: 'var(--space-xs) var(--space-sm)',
            fontSize: 'var(--font-caption)',
            borderRadius: 'var(--radius-sm)',
            border: 'var(--border-thin) solid',
            borderColor: value === w ? 'var(--color-line-correlation)' : 'var(--color-border-strong)',
            backgroundColor: value === w ? 'var(--color-surface-overlay)' : 'transparent',
            color: value === w ? 'var(--color-line-correlation)' : 'var(--color-text-disabled)',
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
      <div className="section-header-inline sector-list-header exposure-section-header" style={{ marginBottom: 'var(--space-md)' }}>
        <div className="panel-section-title-block">
          <p className="panel-label" style={{ display: 'inline' }}>Rolling Correlation &amp; Beta</p>
          <span
            className="attribution-trust-badge"
            title="Computed from current holdings applied to historical prices. Not verified broker return basis."
            style={{ marginLeft: 'var(--space-sm)' }}
          >
            Synthetic
          </span>
        </div>
        <WindowSelector value={window} onChange={setWindow} />
      </div>

      {/* Chart or empty state */}
      {!hasData ? (
        <p className="helper" style={{ textAlign: 'center', padding: 'var(--space-2xl) 0' }}>
          Insufficient history for {window}d rolling window.
        </p>
      ) : (
        <div style={{ height: 260 }}>
          <ResponsiveContainer width="100%" height="100%">
            {/* Axis-overlap fix (US-12.1 T-12.1.3): widened both YAxis widths
                from 44→64 and bumped right margin 56→72 so the rotated
                axis-name labels render outside the plot area and don't
                collide with tick labels at narrow widths. */}
            <ComposedChart data={chartData} margin={{ top: 8, right: 72, bottom: 8, left: 8 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border-subtle)" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDateLabel}
                tick={{ fontSize: 'var(--font-chart-tick)', fill: 'var(--color-text-muted)' }}
                minTickGap={40}
              />
              {/* Left axis: Correlation */}
              <YAxis
                yAxisId="correlation"
                orientation="left"
                domain={[-1, 1]}
                ticks={[-1, -0.5, 0, 0.5, 1]}
                tickFormatter={(v: number) => v.toFixed(1)}
                tick={{ fontSize: 'var(--font-chart-tick)', fill: 'var(--color-line-correlation)' }}
                width={64}
                label={{ value: 'Correlation (ρ)', angle: -90, position: 'insideLeft', offset: 18, style: { fontSize: 'var(--font-chart-tick)', fill: 'var(--color-line-correlation)' } }}
              />
              {/* Right axis: Beta */}
              <YAxis
                yAxisId="beta"
                orientation="right"
                domain={['auto', 'auto']}
                tickFormatter={(v: number) => v.toFixed(1)}
                tick={{ fontSize: 'var(--font-chart-tick)', fill: 'var(--color-line-beta)' }}
                width={64}
                label={{ value: 'Beta (β)', angle: 90, position: 'insideRight', offset: 18, style: { fontSize: 'var(--font-chart-tick)', fill: 'var(--color-line-beta)' } }}
              />
              <ReferenceLine yAxisId="correlation" y={0} stroke="var(--color-line-correlation)" strokeDasharray="3 3" strokeOpacity={0.5} />
              <ReferenceLine yAxisId="beta" y={1} stroke="var(--color-line-beta)" strokeDasharray="3 3" strokeOpacity={0.5} />
              <Tooltip content={<CorrelationTooltip />} />
              <Line
                yAxisId="correlation"
                type="monotone"
                dataKey="correlation"
                name="Correlation (ρ)"
                stroke="var(--color-line-correlation)"
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
                stroke="var(--color-line-beta)"
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
