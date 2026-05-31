/**
 * DrawdownAnalyticsCard — Risk tab card, second slot (Epic 13 — US-13.2).
 *
 * Top half: underwater curve (Recharts AreaChart) — drawdown_pct vs date,
 *           filling downward from 0.
 * Bottom half: top-N drawdown episodes table — Peak | Trough | Recovery |
 *              Magnitude | Duration | Underwater, sorted deepest first.
 *
 * Trust: synthetic when factor model has history; unavailable when fewer than
 * 20 daily observations are available. Never fabricates a zero drawdown or
 * a synthetic episode — surfaces EmptyState on the unavailable path.
 *
 * Methodology: see §Wealth Index and Drawdown + §Drawdown episode
 * identification in financial-methodology.md.
 *
 * Self-fetching component — owns its window selector state and re-fetches
 * the engine on `[snapshot, selectedWindow]` change.
 */
import { useEffect, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'

import { runDrawdownEngine } from './portfolioAnalysisAdapter'
import type { DrawdownEngineResponse, DrawdownEpisode, DrawdownWindow } from './types'
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


// Window options: trading days, plus null = "Max" (engine-capped at ~8 years).
type WindowOption = DrawdownWindow | null
const WINDOW_OPTIONS: WindowOption[] = [252, 756, 1260, null]

function labelForWindow(w: WindowOption): string {
  return w === null ? 'Max' : `${w}d`
}

function ariaForWindow(w: WindowOption): string {
  return w === null ? 'Max window' : `${w} trading day window`
}

// Default window: longest with data wins. We pre-select 1260 (the broadest
// finite window) so the very first render has the longest meaningful history;
// the engine returns whatever it can fit.
const DEFAULT_WINDOW: WindowOption = 1260

// Minimum daily observations to render the chart. Mirror of the engine's
// _MIN_OBSERVATIONS constant — surfaced here only to render the same
// "unavailable" message when the engine returns shorter series than 20
// (which it doesn't today, but the defensive check protects against future
// engine behaviour drift).
const MIN_OBSERVATIONS = 20

// Top-N drawdown episode count shown in the table; mirrors backend.
const TOP_N = 5

type LoadState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; message: string }
  | { kind: 'done'; response: DrawdownEngineResponse }


function formatDateLabel(value: string | number | null | undefined): string {
  if (typeof value !== 'string') return ''
  const [year, month] = value.split('-')
  if (!year || !month) return value
  return `${month}/${year.slice(2)}`
}

function formatMagnitudePct(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value.toFixed(2)}%`
}

function formatDays(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value}d`
}

function daysBetween(startIso: string, endIso: string): number {
  const start = Date.parse(startIso)
  const end = Date.parse(endIso)
  if (Number.isNaN(start) || Number.isNaN(end)) return 0
  return Math.round((end - start) / (24 * 60 * 60 * 1000))
}


// ── Underwater curve ──────────────────────────────────────────────────────────

type UnderwaterTooltipPayload = {
  payload: { date: string; drawdown_pct: number | null; days_from_peak: number | null }
  value: number | null
}

function UnderwaterTooltip(props: { active?: boolean; payload?: UnderwaterTooltipPayload[] }) {
  if (!props.active || !props.payload || props.payload.length === 0) return null
  const row = props.payload[0]?.payload
  if (!row) return null
  return (
    <div style={{ ...defaultTooltipContentStyle, padding: 'var(--space-sm) var(--space-md)' }}>
      <p style={{ margin: 0, fontWeight: 600, fontSize: 'var(--font-caption)' }}>
        {row.date}
      </p>
      <p style={{ margin: 'var(--space-xs) 0 0 0', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--font-caption)' }}>
        Drawdown: <strong>{formatMagnitudePct(row.drawdown_pct)}</strong>
      </p>
      {row.days_from_peak != null && row.days_from_peak > 0 ? (
        <p style={{ margin: 'var(--space-xs) 0 0 0', fontSize: 'var(--font-caption)', color: 'var(--color-text-muted)' }}>
          {row.days_from_peak}d from peak
        </p>
      ) : null}
    </div>
  )
}

function UnderwaterChart({ series }: { series: DrawdownEngineResponse['underwater_series'] }) {
  // Decorate each point with days_from_peak (preceding date where drawdown_pct == 0
  // or first date of series). Pure data-shaping, no analytics math.
  let lastPeakDate = series[0]?.date ?? null
  const data = series.map((point) => {
    if (point.drawdown_pct === 0) lastPeakDate = point.date
    return {
      date: point.date,
      drawdown_pct: point.drawdown_pct,
      days_from_peak: lastPeakDate ? daysBetween(lastPeakDate, point.date) : null,
    }
  })

  const minDD = data.reduce((acc, p) => (p.drawdown_pct != null && p.drawdown_pct < acc ? p.drawdown_pct : acc), 0)
  const yMin = Math.floor(minDD * 1.05)

  return (
    <ChartShell ariaLabel="Underwater drawdown curve over selected window" height={240}>
      <AreaChart data={data} margin={{ top: 8, right: 16, bottom: 8, left: 0 }}>
        <CartesianGrid {...defaultChartGrid} />
        <XAxis
          dataKey="date"
          tickFormatter={formatDateLabel}
          tick={defaultAxisTickStyle}
          minTickGap={defaultMinTickGap}
        />
        <YAxis
          tick={defaultAxisTickStyle}
          tickFormatter={(v: number) => `${v.toFixed(0)}%`}
          domain={[yMin, 0]}
          label={{
            value: 'Drawdown %',
            angle: -90,
            position: 'insideLeft',
            offset: 10,
            style: defaultAxisTickStyle,
          }}
          width={56}
        />
        <ReferenceLine y={0} stroke="var(--color-text-muted)" strokeDasharray="2 2" />
        <Tooltip content={<UnderwaterTooltip />} contentStyle={defaultTooltipContentStyle} />
        <Area
          type="monotone"
          dataKey="drawdown_pct"
          stroke="var(--color-value-negative)"
          fill="var(--color-value-negative)"
          fillOpacity={0.3}
          connectNulls={false}
          isAnimationActive={false}
        />
      </AreaChart>
    </ChartShell>
  )
}


// ── Episodes table ────────────────────────────────────────────────────────────

function EpisodesTable({ episodes }: { episodes: DrawdownEpisode[] }) {
  // Defensive sort: backend already sorts deepest-first, but the AC requires
  // the rendered table be deepest-first regardless of input order. magnitude_pct
  // is signed-negative, so ascending sort puts the most-negative first.
  const sorted = [...episodes].sort((a, b) => a.magnitude_pct - b.magnitude_pct)

  if (sorted.length === 0) {
    return (
      <p className="helper" style={{ marginTop: 'var(--space-md)' }}>
        No drawdown episodes over the selected window.
      </p>
    )
  }

  const cellPadding = 'var(--space-sm) var(--space-md)'

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 'var(--space-md)' }}>
      <thead>
        <tr style={{ borderBottom: 'var(--border-thin) solid var(--color-border-card)' }}>
          {['Peak', 'Trough', 'Recovery', 'Magnitude', 'Duration', 'Underwater'].map((header, idx) => (
            <th
              key={header}
              style={{
                padding: cellPadding,
                textAlign: idx >= 3 ? 'right' : 'left',
                fontSize: 'var(--font-caption)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
                textTransform: 'uppercase',
                letterSpacing: '0.05em',
              }}
            >
              {header}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {sorted.map((episode) => (
          <tr
            key={`${episode.peak_date}-${episode.trough_date}`}
            style={{ borderBottom: 'var(--border-thin) solid var(--color-border-subtle)' }}
          >
            <td style={{ padding: cellPadding, fontSize: 'var(--font-body-sm)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-secondary)' }}>
              {episode.peak_date}
            </td>
            <td style={{ padding: cellPadding, fontSize: 'var(--font-body-sm)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-secondary)' }}>
              {episode.trough_date}
            </td>
            <td style={{ padding: cellPadding, fontSize: 'var(--font-body-sm)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-secondary)' }}>
              {episode.recovery_date == null ? (
                <span style={{ fontStyle: 'italic', color: 'var(--color-text-muted)' }}>Still underwater</span>
              ) : (
                episode.recovery_date
              )}
            </td>
            <td
              style={{
                padding: cellPadding,
                fontSize: 'var(--font-body-sm)',
                fontWeight: 600,
                fontVariantNumeric: 'tabular-nums',
                color: 'var(--color-value-negative)',
                textAlign: 'right',
              }}
            >
              {formatMagnitudePct(episode.magnitude_pct)}
            </td>
            <td style={{ padding: cellPadding, fontSize: 'var(--font-body-sm)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-muted)', textAlign: 'right' }}>
              {formatDays(episode.duration_days)}
            </td>
            <td style={{ padding: cellPadding, fontSize: 'var(--font-body-sm)', fontVariantNumeric: 'tabular-nums', color: 'var(--color-text-muted)', textAlign: 'right' }}>
              {formatDays(episode.underwater_days)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}


// ── Main card ─────────────────────────────────────────────────────────────────

export type DrawdownAnalyticsCardProps = {
  snapshot: PortfolioSnapshot | null
}

export function DrawdownAnalyticsCard({ snapshot }: DrawdownAnalyticsCardProps) {
  const [selectedWindow, setSelectedWindow] = useState<WindowOption>(DEFAULT_WINDOW)
  const [state, setState] = useState<LoadState>({ kind: 'idle' })

  useEffect(() => {
    if (!snapshot) {
      setState({ kind: 'idle' })
      return
    }
    let cancelled = false
    setState({ kind: 'loading' })
    runDrawdownEngine(snapshot, selectedWindow)
      .then((response) => {
        if (!cancelled) setState({ kind: 'done', response })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Drawdown engine failed'
        setState({ kind: 'error', message })
      })
    return () => {
      cancelled = true
    }
  }, [snapshot, selectedWindow])

  const trust = state.kind === 'done' ? state.response.trust : 'unavailable'

  return (
    <CardShell
      title="Drawdown Analytics"
      badge={
        <TrustBadge
          type={trust}
          tooltip="Computed from synthetic daily portfolio values (current holdings × historical prices)."
        />
      }
      actions={
        <WindowSelector<WindowOption>
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
          title="Drawdown analytics unavailable"
          detail="Import a portfolio to see the underwater curve and historical drawdown episodes."
        />
      )}

      {state.kind === 'loading' && (
        <LoadingState message="Computing drawdown analytics…" />
      )}

      {state.kind === 'error' && (
        <ErrorState title="Drawdown engine failed" detail={state.message} />
      )}

      {state.kind === 'done' && (
        state.response.trust === 'unavailable'
        || state.response.underwater_series.length < MIN_OBSERVATIONS ? (
          <EmptyState
            title="Drawdown analytics unavailable"
            detail="At least 20 trading days of portfolio history are required."
          />
        ) : (
          <>
            <UnderwaterChart series={state.response.underwater_series} />
            <EpisodesTable episodes={state.response.episodes.slice(0, TOP_N)} />
          </>
        )
      )}
    </CardShell>
  )
}
