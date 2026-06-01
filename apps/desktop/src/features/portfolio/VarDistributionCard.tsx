/**
 * VarDistributionCard — Risk tab card, third slot (Epic 13 — US-13.3).
 *
 * Top half: daily return histogram (Recharts BarChart). Bars in the loss
 *           tail (center ≤ -var_95/100) are colored red; the rest muted.
 *           Vertical reference lines mark VaR 95 and Mean.
 * Bottom half: percentile + tail-risk + distribution-shape table.
 *
 * Methodology: see §Value-at-Risk and Distribution in
 * financial-methodology.md. Historical VaR; CVaR ≥ VaR by construction
 * (Acerbi & Tasche 2002 — coherent risk measure). VaR may be NEGATIVE
 * when the window has no loss days at the requested confidence — the UI
 * styles those cells muted, never clips to 0.
 *
 * Trust: synthetic when ≥ 20 daily returns available; unavailable
 * otherwise. Self-fetching with internal window selector.
 */
import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'

import { runDistributionEngine } from './portfolioAnalysisAdapter'
import type { DistributionEngineResponse, DistributionWindow, HistogramBin } from './types'
import { CardShell } from '../../app/primitives/CardShell'
import { ChartShell } from '../../app/primitives/ChartShell'
import {
  defaultAxisTickStyle,
  defaultChartGrid,
  defaultMinTickGap,
  defaultTooltipContentStyle,
} from '../../app/primitives/chartDefaults'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'
import { WindowSelector } from '../../app/primitives/WindowSelector'
import type { PortfolioSnapshot } from './workspaceTypes'


const WINDOW_OPTIONS: DistributionWindow[] = [60, 252, 504]
const DEFAULT_WINDOW: DistributionWindow = 252
const MIN_OBSERVATIONS = 20


function labelForWindow(w: DistributionWindow): string {
  return `${w}d`
}

function ariaForWindow(w: DistributionWindow): string {
  return `${w} trading day window`
}


type LoadState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; response: DistributionEngineResponse }


function formatPct(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value.toFixed(2)}%`
}

function formatPctSignedNoSuffix(value: number | null | undefined, digits = 2): string {
  if (value == null) return '—'
  return value.toFixed(digits)
}

function formatBucketCenter(center: number): string {
  // center is decimal (e.g. -0.025 → "-2.5%"). One decimal for axis ticks.
  const pct = center * 100
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(1)}%`
}

function bucketRangeLabel(bins: HistogramBin[], idx: number): string {
  // Reconstruct the bin half-width from neighbours when possible.
  if (bins.length < 2) {
    return formatBucketCenter(bins[idx]?.center ?? 0)
  }
  const halfWidth = Math.abs(bins[1]!.center - bins[0]!.center) / 2
  const center = bins[idx]?.center ?? 0
  return `${formatBucketCenter(center - halfWidth)} to ${formatBucketCenter(center + halfWidth)}`
}


// ── Histogram ─────────────────────────────────────────────────────────────────

type HistogramTooltipPayload = {
  payload: { centerLabel: string; rangeLabel: string; count: number }
}

function HistogramTooltip(props: { active?: boolean; payload?: HistogramTooltipPayload[] }) {
  if (!props.active || !props.payload || props.payload.length === 0) return null
  const row = props.payload[0]?.payload
  if (!row) return null
  return (
    <div style={{ ...defaultTooltipContentStyle, padding: 'var(--space-sm) var(--space-md)' }}>
      <p style={{ margin: 0, fontWeight: 600, fontSize: 'var(--font-caption)' }}>
        {row.rangeLabel}
      </p>
      <p style={{ margin: 'var(--space-xs) 0 0 0', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--font-caption)', color: 'var(--color-text-muted)' }}>
        {row.count} {row.count === 1 ? 'day' : 'days'}
      </p>
    </div>
  )
}

function DistributionHistogram({
  bins,
  var95,
  meanPct,
}: {
  bins: HistogramBin[]
  var95: number | null
  meanPct: number | null
}) {
  // Threshold for the loss tail (decimal). Bars with center ≤ this are
  // re-colored red. When var_95 is null OR negative (no real loss tail in
  // window), no bar gets the tail color.
  const tailThreshold = var95 != null && var95 > 0 ? -var95 / 100 : -Infinity

  const data = bins.map((b, idx) => ({
    centerLabel: formatBucketCenter(b.center),
    rangeLabel: bucketRangeLabel(bins, idx),
    center: b.center,
    count: b.count,
    inTail: b.center <= tailThreshold,
  }))

  const varRefX = var95 != null && var95 > 0 ? -var95 / 100 : null
  const meanRefX = meanPct != null ? meanPct / 100 : null

  return (
    <ChartShell ariaLabel="Daily return distribution histogram with VaR-95 threshold" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid {...defaultChartGrid} />
        <XAxis
          dataKey="centerLabel"
          tick={defaultAxisTickStyle}
          minTickGap={defaultMinTickGap}
        />
        <YAxis
          tick={defaultAxisTickStyle}
          allowDecimals={false}
          label={{
            value: 'Days',
            angle: -90,
            position: 'insideLeft',
            offset: 10,
            style: defaultAxisTickStyle,
          }}
          width={48}
        />
        {varRefX != null && (
          <ReferenceLine
            x={formatBucketCenter(varRefX)}
            stroke="var(--color-value-negative)"
            strokeDasharray="4 4"
            label={{ value: 'VaR 95', position: 'top', fill: 'var(--color-value-negative)', fontSize: 'var(--font-caption)' }}
          />
        )}
        {meanRefX != null && (
          <ReferenceLine
            x={formatBucketCenter(meanRefX)}
            stroke="var(--color-text-muted)"
            strokeDasharray="4 4"
            label={{ value: 'Mean', position: 'top', fill: 'var(--color-text-muted)', fontSize: 'var(--font-caption)' }}
          />
        )}
        <Tooltip content={<HistogramTooltip />} contentStyle={defaultTooltipContentStyle} />
        <Bar
          dataKey="count"
          isAnimationActive={false}
          // Recharts shapeable bar: we color via the data row's `inTail`
          // flag using a cell-style fill function. Simpler approach: just
          // use a constant fill and let users distinguish via tooltip.
          // For the tail-coloring requirement, we use the shape prop.
          shape={(props: unknown) => {
            const p = props as { x: number; y: number; width: number; height: number; payload?: { inTail?: boolean } }
            const color = p.payload?.inTail
              ? 'var(--color-value-negative)'
              : 'var(--color-text-muted)'
            return <rect x={p.x} y={p.y} width={p.width} height={p.height} fill={color} />
          }}
        />
      </BarChart>
    </ChartShell>
  )
}


// ── Stats table ───────────────────────────────────────────────────────────────

function StatRow({ label, value, danger = false }: { label: string; value: string; danger?: boolean }) {
  const isMissing = value === '—'
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        padding: 'var(--space-xs) 0',
      }}
    >
      <span style={{ fontSize: 'var(--font-body-sm)', color: 'var(--color-text-secondary)' }}>{label}</span>
      <span
        style={{
          fontSize: 'var(--font-body-sm)',
          fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
          color:
            isMissing
              ? 'var(--color-text-disabled)'
              : danger
                ? 'var(--color-value-negative)'
                : 'var(--color-text-secondary)',
        }}
      >
        {value}
      </span>
    </div>
  )
}

function SectionHeader({ title }: { title: string }) {
  return (
    <p
      style={{
        margin: 'var(--space-md) 0 var(--space-xs) 0',
        fontSize: 'var(--font-caption)',
        fontWeight: 600,
        color: 'var(--color-text-muted)',
        textTransform: 'uppercase',
        letterSpacing: '0.05em',
      }}
    >
      {title}
    </p>
  )
}

function StatsTable({ response }: { response: DistributionEngineResponse }) {
  // Tail-risk values: red ("danger") when value is a POSITIVE loss; muted
  // otherwise (null or negative = no real tail loss in window).
  const tailDanger = (v: number | null | undefined) => v != null && v > 0

  return (
    <div style={{ marginTop: 'var(--space-md)' }}>
      <SectionHeader title="Percentiles" />
      <StatRow label="5%" value={formatPct(response.percentile_5)} />
      <StatRow label="10%" value={formatPct(response.percentile_10)} />
      <StatRow label="50%" value={formatPct(response.percentile_50)} />
      <StatRow label="90%" value={formatPct(response.percentile_90)} />
      <StatRow label="95%" value={formatPct(response.percentile_95)} />

      <SectionHeader title="Tail Risk" />
      <StatRow label="VaR 95" value={formatPct(response.var_95)} danger={tailDanger(response.var_95)} />
      <StatRow label="CVaR 95" value={formatPct(response.cvar_95)} danger={tailDanger(response.cvar_95)} />
      <StatRow label="VaR 99" value={formatPct(response.var_99)} danger={tailDanger(response.var_99)} />

      <SectionHeader title="Distribution shape" />
      <StatRow label="Mean" value={formatPct(response.mean_pct)} />
      <StatRow label="Std" value={formatPct(response.std_pct)} />
      <StatRow label="Skew" value={formatPctSignedNoSuffix(response.skewness)} />
      <StatRow label="Kurtosis (excess)" value={formatPctSignedNoSuffix(response.kurtosis_excess)} />
    </div>
  )
}


// ── Main card ─────────────────────────────────────────────────────────────────

export type VarDistributionCardProps = {
  snapshot: PortfolioSnapshot | null
}

export function VarDistributionCard({ snapshot }: VarDistributionCardProps) {
  const [selectedWindow, setSelectedWindow] = useState<DistributionWindow>(DEFAULT_WINDOW)
  const [state, setState] = useState<LoadState>({ kind: 'idle' })

  useEffect(() => {
    if (!snapshot) {
      setState({ kind: 'idle' })
      return
    }
    let cancelled = false
    setState({ kind: 'loading' })
    runDistributionEngine(snapshot, selectedWindow)
      .then((response) => {
        if (!cancelled) setState({ kind: 'done', response })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Distribution engine failed'
        setState({ kind: 'error', message })
      })
    return () => {
      cancelled = true
    }
  }, [snapshot, selectedWindow])

  const trust = state.kind === 'done' ? state.response.trust : 'unavailable'

  return (
    <CardShell
      title="VaR & Distribution"
      badge={
        <TrustBadge
          type={trust}
          tooltip="Computed from synthetic daily portfolio returns (current holdings × historical prices). Historical-simulation VaR — backward-looking by construction."
        />
      }
      actions={
        <WindowSelector<DistributionWindow>
          options={WINDOW_OPTIONS}
          value={selectedWindow}
          onChange={setSelectedWindow}
          labelFn={labelForWindow}
          ariaLabelFn={ariaForWindow}
        />
      }
    >
      {state.kind === 'idle' && (
        <EmptyState
          title="Distribution analytics unavailable"
          detail="Import a portfolio to see the daily return distribution, percentiles, and Value-at-Risk."
        />
      )}

      {state.kind === 'loading' && (
        <LoadingState message="Computing return distribution…" />
      )}

      {state.kind === 'error' && (
        <ErrorState title="Distribution engine failed" detail={state.message} />
      )}

      {state.kind === 'done' && (
        state.response.trust === 'unavailable'
        || state.response.return_count < MIN_OBSERVATIONS ? (
          <EmptyState
            title="Distribution analytics unavailable"
            detail="At least 20 trading days of portfolio returns are required. The 252d window is recommended once available."
          />
        ) : (
          <>
            <p
              className="helper"
              style={{ margin: '0 0 var(--space-sm) 0' }}
            >
              Window: {state.response.window_trading_days}d • N = {state.response.return_count} obs
            </p>
            <DistributionHistogram
              bins={state.response.histogram_bins}
              var95={state.response.var_95}
              meanPct={state.response.mean_pct}
            />
            <StatsTable response={state.response} />
          </>
        )
      )}
    </CardShell>
  )
}
