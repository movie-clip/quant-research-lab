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
import { coverageNote } from './coverageNote'
import { Fragment, useEffect, useState } from 'react'
import { Area, AreaChart, CartesianGrid, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'

import { runDrawdownEngine } from './portfolioAnalysisAdapter'
import type { DrawdownEngineResponse, DrawdownEpisode, DrawdownWindow, EpisodeContributor } from './types'
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

function formatSignedPct(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function signedColor(value: number | null | undefined): string {
  if (value == null) return 'var(--color-text-muted)'
  if (value < 0) return 'var(--color-value-negative)'
  if (value > 0) return 'var(--color-value-positive)'
  return 'var(--color-text-muted)'
}

// US-15.2 visibility thresholds. Below these, the corresponding row is
// treated as floating-point noise / immaterial and hidden — the
// methodology Contract rule still requires `residual` is REPORTED in the
// schema, but the UI hides cells that would otherwise look like clutter
// from rounding artifacts.
const _OTHER_ROW_THRESHOLD_PCT = 0.01
const _RESIDUAL_ROW_THRESHOLD_PCT = 0.05

/** Renders the per-episode "Contributors" sub-table inside a drawer row.
 *  Pure rendering — no state, no side effects. */
function ContributorsDrawer({ episode }: { episode: DrawdownEpisode }) {
  const cellPadding = 'var(--space-xs) var(--space-md)'
  const topContributors: EpisodeContributor[] = episode.top_contributors ?? []
  const other = episode.other_contribution_pct
  const residual = episode.decomposition_residual_pct
  const showOther = other != null && Math.abs(other) >= _OTHER_ROW_THRESHOLD_PCT
  const showResidual = residual != null && Math.abs(residual) > _RESIDUAL_ROW_THRESHOLD_PCT

  return (
    <div style={{ padding: 'var(--space-md) var(--space-md) var(--space-md) var(--space-xl)' }}>
      {episode.decomposition_trust === 'partial' && residual != null && (
        <p
          style={{
            margin: '0 0 var(--space-sm) 0',
            fontSize: 'var(--font-caption)',
            color: 'var(--color-text-muted)',
          }}
        >
          Partial: {residual.toFixed(1)}% unexplained (some positions missing price history).
        </p>
      )}
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr style={{ borderBottom: 'var(--border-thin) solid var(--color-border-subtle)' }}>
            <th
              style={{
                padding: cellPadding,
                textAlign: 'left',
                fontSize: 'var(--font-caption)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
              }}
            >
              Symbol
            </th>
            <th
              className="drawdown-contributor-secondary"
              style={{
                padding: cellPadding,
                textAlign: 'right',
                fontSize: 'var(--font-caption)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
              }}
            >
              Weight @ Peak
            </th>
            <th
              className="drawdown-contributor-secondary"
              style={{
                padding: cellPadding,
                textAlign: 'right',
                fontSize: 'var(--font-caption)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
              }}
            >
              Return
            </th>
            <th
              style={{
                padding: cellPadding,
                textAlign: 'right',
                fontSize: 'var(--font-caption)',
                fontWeight: 600,
                color: 'var(--color-text-muted)',
              }}
            >
              Contribution
            </th>
          </tr>
        </thead>
        <tbody>
          {topContributors.map((c) => (
            <tr key={c.symbol} style={{ borderBottom: 'var(--border-thin) solid var(--color-border-subtle)' }}>
              <td
                style={{
                  padding: cellPadding,
                  fontSize: 'var(--font-body-sm)',
                  fontWeight: 500,
                  color: 'var(--color-text-secondary)',
                }}
              >
                {c.symbol}
              </td>
              <td
                className="drawdown-contributor-secondary"
                style={{
                  padding: cellPadding,
                  fontSize: 'var(--font-body-sm)',
                  fontVariantNumeric: 'tabular-nums',
                  color: 'var(--color-text-muted)',
                  textAlign: 'right',
                }}
              >
                {c.weight_at_peak_pct == null ? '—' : `${c.weight_at_peak_pct.toFixed(2)}%`}
              </td>
              <td
                className="drawdown-contributor-secondary"
                style={{
                  padding: cellPadding,
                  fontSize: 'var(--font-body-sm)',
                  fontVariantNumeric: 'tabular-nums',
                  color: signedColor(c.return_pct),
                  textAlign: 'right',
                }}
              >
                {formatSignedPct(c.return_pct)}
              </td>
              <td
                style={{
                  padding: cellPadding,
                  fontSize: 'var(--font-body-sm)',
                  fontWeight: 600,
                  fontVariantNumeric: 'tabular-nums',
                  color: signedColor(c.contribution_pct),
                  textAlign: 'right',
                }}
              >
                {formatSignedPct(c.contribution_pct)}
              </td>
            </tr>
          ))}
          {showOther && (
            <tr style={{ borderBottom: 'var(--border-thin) solid var(--color-border-subtle)' }}>
              <td
                style={{
                  padding: cellPadding,
                  fontSize: 'var(--font-body-sm)',
                  color: 'var(--color-text-muted)',
                }}
              >
                Other
              </td>
              <td
                className="drawdown-contributor-secondary"
                style={{ padding: cellPadding, color: 'var(--color-text-muted)', textAlign: 'right' }}
              >
                —
              </td>
              <td
                className="drawdown-contributor-secondary"
                style={{ padding: cellPadding, color: 'var(--color-text-muted)', textAlign: 'right' }}
              >
                —
              </td>
              <td
                style={{
                  padding: cellPadding,
                  fontSize: 'var(--font-body-sm)',
                  fontWeight: 600,
                  fontVariantNumeric: 'tabular-nums',
                  color: signedColor(other),
                  textAlign: 'right',
                }}
              >
                {formatSignedPct(other)}
              </td>
            </tr>
          )}
          {showResidual && (
            <tr>
              <td
                style={{
                  padding: cellPadding,
                  fontSize: 'var(--font-body-sm)',
                  fontStyle: 'italic',
                  color: 'var(--color-text-muted)',
                }}
              >
                Residual (unexplained)
              </td>
              <td
                className="drawdown-contributor-secondary"
                style={{ padding: cellPadding, color: 'var(--color-text-muted)', textAlign: 'right' }}
              >
                —
              </td>
              <td
                className="drawdown-contributor-secondary"
                style={{ padding: cellPadding, color: 'var(--color-text-muted)', textAlign: 'right' }}
              >
                —
              </td>
              <td
                style={{
                  padding: cellPadding,
                  fontSize: 'var(--font-body-sm)',
                  fontStyle: 'italic',
                  fontVariantNumeric: 'tabular-nums',
                  color: signedColor(residual),
                  textAlign: 'right',
                }}
              >
                {formatSignedPct(residual)}
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function EpisodesTable({ episodes }: { episodes: DrawdownEpisode[] }) {
  // Defensive sort: backend already sorts deepest-first, but the AC requires
  // the rendered table be deepest-first regardless of input order. magnitude_pct
  // is signed-negative, so ascending sort puts the most-negative first.
  const sorted = [...episodes].sort((a, b) => a.magnitude_pct - b.magnitude_pct)

  // US-15.2: single-open drawer state. Episode key = `${peak}-${trough}`.
  const [expandedKey, setExpandedKey] = useState<string | null>(null)

  if (sorted.length === 0) {
    return (
      <p className="helper" style={{ marginTop: 'var(--space-md)' }}>
        No drawdown episodes over the selected window.
      </p>
    )
  }

  const cellPadding = 'var(--space-sm) var(--space-md)'
  // Parent table has 7 columns now (toggle + 6 episode columns); drawer spans all.
  const drawerColSpan = 7

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: 'var(--space-md)' }}>
      <thead>
        <tr style={{ borderBottom: 'var(--border-thin) solid var(--color-border-card)' }}>
          {/* Expand toggle column — no header label */}
          <th
            style={{
              padding: cellPadding,
              width: 'var(--space-xl)',
              fontSize: 'var(--font-caption)',
              fontWeight: 600,
              color: 'var(--color-text-muted)',
            }}
            aria-hidden="true"
          />
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
        {sorted.map((episode) => {
          const key = `${episode.peak_date}-${episode.trough_date}`
          const isExpanded = expandedKey === key
          // US-15.2 AC9: toggle disabled when decomposition is unavailable
          // OR top_contributors is null/absent.
          const isDecomposed =
            episode.decomposition_trust !== 'unavailable'
            && episode.decomposition_trust !== undefined
            && episode.top_contributors != null
            && episode.top_contributors.length > 0
          const drawerId = `contributors-${key}`
          const toggleAriaLabel = !isDecomposed
            ? `Decomposition unavailable for ${episode.peak_date} episode`
            : isExpanded
              ? `Collapse contributors for ${episode.peak_date} episode`
              : `Expand contributors for ${episode.peak_date} episode`
          const toggleTitle = !isDecomposed
            ? "Position-level prices not available for this episode's date range."
            : undefined

          return (
            <Fragment key={key}>
              <tr style={{ borderBottom: 'var(--border-thin) solid var(--color-border-subtle)' }}>
                <td style={{ padding: cellPadding, verticalAlign: 'middle' }}>
                  <button
                    type="button"
                    aria-expanded={isExpanded}
                    aria-controls={drawerId}
                    aria-label={toggleAriaLabel}
                    title={toggleTitle}
                    disabled={!isDecomposed}
                    onClick={() => { setExpandedKey(isExpanded ? null : key) }}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      padding: 'var(--space-xs)',
                      cursor: isDecomposed ? 'pointer' : 'not-allowed',
                      color: isDecomposed ? 'var(--color-text-secondary)' : 'var(--color-text-disabled)',
                      fontSize: 'var(--font-body-sm)',
                      fontFamily: 'inherit',
                    }}
                  >
                    {isExpanded ? '▾' : '▸'}
                  </button>
                </td>
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
              {isExpanded && (
                <tr id={drawerId}>
                  <td colSpan={drawerColSpan} style={{ padding: 0 }}>
                    <ContributorsDrawer episode={episode} />
                  </td>
                </tr>
              )}
            </Fragment>
          )
        })}
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
  // US-14.2: tracks whether the user has manually clicked a WindowSelector
  // button for the current snapshot. Once true, the cascade is disabled and
  // we respect the user's explicit choice — even if it returns unavailable.
  // Resets on snapshot change (separate effect below).
  const [hasUserOverriddenWindow, setHasUserOverriddenWindow] = useState(false)

  // Reset the user-override flag whenever the snapshot reference changes, so
  // the cascade re-runs from window=1260 on the new portfolio.
  useEffect(() => {
    setHasUserOverriddenWindow(false)
  }, [snapshot])

  useEffect(() => {
    if (!snapshot) {
      setState({ kind: 'idle' })
      return
    }
    let cancelled = false
    setState({ kind: 'loading' })

    // US-14.2: when the user has manually overridden, fetch once with the
    // selected window and surface whatever the engine returns (even
    // unavailable). When the user has NOT overridden, run the cascade:
    // start at selectedWindow, fall back to next-shorter on unavailable,
    // stop on the first synthetic response OR when all 4 options are
    // exhausted.
    const runCascade = async () => {
      // Cascade order is explicit (longest → shortest → Max) to avoid
      // depending on the WINDOW_OPTIONS array's display order.
      const cascadeOrder: WindowOption[] = [1260, 756, 252, null]
      const startIdx = Math.max(0, cascadeOrder.indexOf(selectedWindow))
      const cascade = hasUserOverriddenWindow
        ? [selectedWindow]
        : cascadeOrder.slice(startIdx)

      let lastResponse: Awaited<ReturnType<typeof runDrawdownEngine>> | null = null
      for (const window of cascade) {
        if (cancelled) return
        try {
          const response = await runDrawdownEngine(snapshot, window)
          if (cancelled) return
          lastResponse = response
          if (response.trust === 'synthetic') {
            // Stop on first success. We do NOT update `selectedWindow`
            // here — that would re-trigger the effect and cause a
            // redundant 3rd fetch. The WindowSelector's active button
            // is derived from `state.response.window_trading_days` (see
            // `displayedWindow` in render), so the UI still reflects
            // the window that actually rendered.
            setState({ kind: 'done', response })
            return
          }
          // unavailable → continue to next window in cascade (if any)
        } catch (err: unknown) {
          if (cancelled) return
          // AC7: network error stops the cascade and surfaces the error.
          const message = err instanceof Error ? err.message : 'Drawdown engine failed'
          setState({ kind: 'error', message })
          return
        }
      }

      // All cascade attempts returned unavailable. Surface the last
      // response so the card renders its EmptyState. Display window
      // tracks the last response's window via `displayedWindow` below.
      if (cancelled || !lastResponse) return
      setState({ kind: 'done', response: lastResponse })
    }

    void runCascade()
    return () => {
      cancelled = true
    }
  }, [snapshot, selectedWindow, hasUserOverriddenWindow])

  const trust = state.kind === 'done' ? state.response.trust : 'unavailable'

  // US-14.2: wrap the WindowSelector onChange so clicking a window both
  // updates the selection AND disables the auto-fallback cascade. The
  // user's explicit intent always wins.
  const handleWindowChange = (next: WindowOption) => {
    setHasUserOverriddenWindow(true)
    setSelectedWindow(next)
  }

  // US-14.2: the WindowSelector active button reflects what's actually
  // RENDERING — which during/after a cascade may differ from
  // `selectedWindow`. When state.kind === 'done', derive the displayed
  // window from the response's `window_trading_days`. Otherwise (idle,
  // loading, error) fall through to `selectedWindow`.
  const displayedWindow: WindowOption =
    state.kind === 'done' && !hasUserOverriddenWindow
      ? ((state.response.window_trading_days as DrawdownWindow | null) ?? null)
      : selectedWindow

  return (
    <CardShell
      title="Drawdown Analytics"
      badge={
        <TrustBadge
          type={trust}
          tooltip="Synthetic: computed from current holdings × historical prices. Underwater curve and episodes derived from daily portfolio value series."
        />
      }
      actions={
        <WindowSelector<WindowOption>
          options={WINDOW_OPTIONS}
          value={displayedWindow}
          onChange={handleWindowChange}
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
            {coverageNote(state.response.coverage) ? (
              <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
                {coverageNote(state.response.coverage)}
              </p>
            ) : null}
          </>
        )
      )}
    </CardShell>
  )
}
