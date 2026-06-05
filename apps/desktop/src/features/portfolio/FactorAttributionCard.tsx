import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'

import type { FactorAttributionResponse, ImportedSnapshot } from './types'
import { runAttributionEngine } from './portfolioAnalysisAdapter'
import { CardShell } from '../../app/primitives/CardShell'
import { ChartShell } from '../../app/primitives/ChartShell'
import { defaultAxisTickStyle, defaultChartGrid, defaultMinTickGap } from '../../app/primitives/chartDefaults'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'
import { WindowSelector } from '../../app/primitives/WindowSelector'

type AttributionWindow = 20 | 60 | 252

const WINDOW_OPTIONS: AttributionWindow[] = [20, 60, 252]
const WINDOW_LABELS: Record<AttributionWindow, string> = { 20: '20d', 60: '60d', 252: '252d' }

// Maps factor_key → CSS variable. Tokens live in apps/desktop/src/app/styles.css
// (`--color-factor-*`). Adding a new factor: add a token there, then a row here.
const FACTOR_LINE_COLORS: Record<string, string> = {
  market: 'var(--color-factor-market)',
  growth: 'var(--color-factor-growth)',
  value: 'var(--color-factor-value)',
  small_cap: 'var(--color-factor-small-cap)',
  technology: 'var(--color-factor-technology)',
  financials: 'var(--color-factor-financials)',
  health_care: 'var(--color-factor-health-care)',
  energy: 'var(--color-factor-energy)',
  industrials: 'var(--color-factor-industrials)',
  consumer_staples: 'var(--color-factor-consumer-staples)',
  utilities: 'var(--color-factor-utilities)',
  consumer_discretionary: 'var(--color-factor-consumer-discretionary)',
  rates_ief: 'var(--color-factor-rates-ief)',
  rates_tlt: 'var(--color-factor-rates-tlt)',
  credit: 'var(--color-factor-credit)',
  commodities: 'var(--color-factor-commodities)',
}

const FACTOR_DEFAULT_COLOR = 'var(--color-factor-default)'
const UNEXPLAINED_COLOR = 'var(--color-unexplained)'
const PORTFOLIO_COLOR = 'var(--color-portfolio-total)'

// Each exposed-panel list-row: padding 9+9px + ~17px line-height + 1px border ≈ 36px.
// Exposure-panel list-table gap: 14px. Six rows visible:
//   6 × 36 + 5 × 14 = 286px.
const SCROLL_MAX_HEIGHT = 286

type ChartPoint = {
  date: string
  unexplained: number | null
  portfolio: number | null
} & Record<string, number | null | string>

function formatDateLabel(value: string | number | null | undefined) {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return value
  return `${month}/${day}/${year.slice(2)}`
}

function formatPct(value: number | null | undefined, digits = 2) {
  if (value == null) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(digits)}%`
}

function formatBeta(value: number | null | undefined) {
  if (value == null) return '—'
  return value.toFixed(3)
}

function buildChartData(attribution: FactorAttributionResponse): ChartPoint[] {
  return attribution.cumulative_series.map((entry) => {
    const point: ChartPoint = {
      date: entry.date,
      unexplained: entry.cumul_unexplained != null ? entry.cumul_unexplained * 100 : null,
      portfolio: entry.cumul_portfolio_return != null ? entry.cumul_portfolio_return * 100 : null,
    }
    for (const cp of entry.contributions) {
      point[cp.factor_key] = cp.cumul_contribution != null ? cp.cumul_contribution * 100 : null
    }
    return point
  })
}

// ── Line opacity / width helpers ───────────────────────────────────────────────

function lineOpacity(key: string, hovered: string | null): number {
  if (!hovered) return 1
  return hovered === key ? 1 : 0.15
}

function lineWidth(key: string, hovered: string | null, defaultWidth: number, hoveredWidth: number): number {
  if (!hovered) return defaultWidth
  return hovered === key ? hoveredWidth : defaultWidth
}

// ── Subcomponents ──────────────────────────────────────────────────────────────

// ── Custom tooltip ─────────────────────────────────────────────────────────────

type TooltipPayloadEntry = {
  dataKey: string
  name: string
  value: number | null | undefined
  color: string
}

type CustomTooltipProps = {
  active?: boolean
  payload?: TooltipPayloadEntry[]
  label?: string
}

function AttributionTooltip({ active, payload, label }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null

  const portfolioEntry = payload.find((p) => p.dataKey === 'portfolio')
  const unexplainedEntry = payload.find((p) => p.dataKey === 'unexplained')
  const factorEntries = payload
    .filter((p) => p.dataKey !== 'portfolio' && p.dataKey !== 'unexplained')
    .sort((a, b) => Math.abs(b.value ?? 0) - Math.abs(a.value ?? 0))

  const orderedItems: TooltipPayloadEntry[] = [
    ...(portfolioEntry ? [portfolioEntry] : []),
    ...factorEntries,
    ...(unexplainedEntry ? [unexplainedEntry] : []),
  ]

  return (
    <div
      style={{
        backgroundColor: 'var(--color-surface-elevated)',
        border: 'var(--border-thin) solid var(--color-border-strong)',
        borderRadius: 'var(--radius-sm)',
        padding: 'var(--space-sm) var(--space-md)',
        fontSize: 'var(--font-caption)',
        minWidth: 200,
      }}
    >
      <p style={{ color: 'var(--color-text-muted)', marginBottom: 'var(--space-xs)', marginTop: 0, fontWeight: 600 }}>
        {typeof label === 'string' ? formatDateLabel(label) : label}
      </p>
      {orderedItems.map((entry) => {
        const v = typeof entry.value === 'number' ? entry.value : null
        const formatted = formatPct(v)
        const isPortfolio = entry.dataKey === 'portfolio'
        return (
          <div
            key={entry.dataKey}
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 'var(--space-lg)',
              marginBottom: isPortfolio ? 'var(--space-xs)' : 'var(--space-xxs)',
              paddingBottom: isPortfolio ? 'var(--space-xs)' : 0,
              borderBottom: isPortfolio ? 'var(--border-thin) solid var(--color-border-strong)' : 'none',
              fontWeight: isPortfolio ? 600 : 400,
            }}
          >
            <span style={{ color: entry.color }}>{entry.name}</span>
            <span style={{ color: entry.color, fontVariantNumeric: 'tabular-nums' }}>{formatted}</span>
          </div>
        )
      })}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

type FactorAttributionCardProps = {
  snapshot: ImportedSnapshot | null
}

type LoadState = 'idle' | 'loading' | 'error' | 'done'

export function FactorAttributionCard({ snapshot }: FactorAttributionCardProps) {
  const [window, setWindow] = useState<AttributionWindow>(20)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [attribution, setAttribution] = useState<FactorAttributionResponse | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [tableExpanded, setTableExpanded] = useState(true)
  const [hoveredKey, setHoveredKey] = useState<string | null>(null)

  useEffect(() => {
    if (!snapshot) {
      setAttribution(null)
      setLoadState('idle')
      return
    }

    let cancelled = false
    setLoadState('loading')
    setErrorMsg(null)

    runAttributionEngine(snapshot, window)
      .then((result) => {
        if (!cancelled) {
          setAttribution(result)
          setLoadState('done')
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : 'Attribution engine failed')
          setLoadState('error')
        }
      })

    return () => {
      cancelled = true
    }
  }, [snapshot, window])

  const activeFactorKeys =
    attribution?.period_attribution.map((row) => row.factor_key) ?? []

  const chartData = attribution ? buildChartData(attribution) : []

  return (
    <CardShell
      title="Factor Return Attribution"
      badge={
        <TrustBadge
          type="synthetic"
          tooltip="Returns are reconstructed from current holdings and historical factor proxy prices."
        />
      }
      actions={
        <WindowSelector<AttributionWindow>
          options={WINDOW_OPTIONS}
          value={window}
          onChange={setWindow}
          labelFn={(w) => WINDOW_LABELS[w]}
        />
      }
      className="dashboard-bottom-grid exposure-primary-section exposure-shell-section"
    >
      {loadState === 'loading' && <LoadingState message="Computing attribution…" />}

      {loadState === 'error' && (
        <ErrorState title="Attribution unavailable" detail={errorMsg ?? 'The attribution engine returned an error.'} />
      )}

      {loadState === 'idle' && (
        <EmptyState title="Import a portfolio to view factor return attribution." />
      )}

      {loadState === 'done' && attribution && (
        <>
          {attribution.attribution_status === 'unavailable' ? (
            <EmptyState
              title="Not enough history"
              detail={`Need at least ${window + 1} trading days of common history between portfolio and factor proxies. Try a shorter window or import a longer statement.`}
            />
          ) : (
            <>
              {/* Cumulative attribution line chart */}
              <div style={{ width: '100%', marginBottom: 'var(--space-xl)' }}>
                <ChartShell ariaLabel="Cumulative factor return attribution line chart" height={280}>
                  <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                    <CartesianGrid {...defaultChartGrid} />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatDateLabel}
                      tick={defaultAxisTickStyle}
                      tickLine={false}
                      minTickGap={defaultMinTickGap}
                    />
                    <YAxis
                      tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      tick={defaultAxisTickStyle}
                      tickLine={false}
                      width={56}
                    />
                    <ReferenceLine y={0} stroke="var(--color-axis-reference)" strokeWidth={1} />
                    <Tooltip content={<AttributionTooltip />} />

                    {/* Factor contribution lines */}
                    {activeFactorKeys.map((key) => (
                      <Line
                        key={key}
                        type="monotone"
                        dataKey={key}
                        stroke={FACTOR_LINE_COLORS[key] ?? FACTOR_DEFAULT_COLOR}
                        strokeWidth={lineWidth(key, hoveredKey, 1.5, 2.8)}
                        opacity={lineOpacity(key, hoveredKey)}
                        dot={false}
                        connectNulls
                        isAnimationActive={false}
                        name={attribution.period_attribution.find((r) => r.factor_key === key)?.factor_label ?? key}
                      />
                    ))}

                    {/* Unexplained line */}
                    <Line
                      type="monotone"
                      dataKey="unexplained"
                      stroke={UNEXPLAINED_COLOR}
                      strokeWidth={lineWidth('unexplained', hoveredKey, 1.5, 2.8)}
                      opacity={lineOpacity('unexplained', hoveredKey)}
                      strokeDasharray="4 2"
                      dot={false}
                      connectNulls
                      isAnimationActive={false}
                      name="Unexplained"
                    />

                    {/* Total Portfolio line — rendered last so it draws on top */}
                    <Line
                      type="monotone"
                      dataKey="portfolio"
                      stroke={PORTFOLIO_COLOR}
                      strokeWidth={lineWidth('portfolio', hoveredKey, 2.5, 4)}
                      opacity={lineOpacity('portfolio', hoveredKey)}
                      dot={false}
                      connectNulls
                      isAnimationActive={false}
                      name="Total Portfolio (arithmetic)"
                    />
                  </LineChart>
                </ChartShell>
              </div>

              {/* Period attribution table — collapsible, scrollable body */}
              <div>
                <button
                  type="button"
                  onClick={() => setTableExpanded((prev) => !prev)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 'var(--space-xs)',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '0 0 var(--space-sm) 0',
                    color: 'var(--color-text-disabled)',
                    fontSize: 'var(--font-chart-tick)',
                  }}
                >
                  <span
                    style={{
                      display: 'inline-block',
                      width: 0,
                      height: 0,
                      borderLeft: 'var(--space-xs) solid transparent',
                      borderRight: 'var(--space-xs) solid transparent',
                      // design-system: escape-hatch: CSS triangle pointer (vertex height = 5px, by convention 1px taller than base width 4px)
                      borderTop: tableExpanded ? '5px solid var(--color-text-disabled)' : undefined,
                      // design-system: escape-hatch: CSS triangle pointer (vertex height = 5px, by convention 1px taller than base width 4px)
                      borderBottom: tableExpanded ? undefined : '5px solid var(--color-text-disabled)',
                    }}
                  />
                  Period attribution — arithmetic (not compounded)
                </button>

                {tableExpanded && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-md)' }}>
                    {/* Header row — not scrollable */}
                    <div className="list-row" style={{ fontWeight: 600, fontSize: 'var(--font-chart-tick)', color: 'var(--color-text-disabled)' }}>
                      <span style={{ flex: 2 }}>Factor</span>
                      <span style={{ flex: 1, textAlign: 'right' }}>Avg β</span>
                      <span style={{ flex: 1, textAlign: 'right' }}>Factor Rtn %</span>
                      <span style={{ flex: 1, textAlign: 'right' }}>Contribution %</span>
                    </div>

                    {/* Scrollable data body — shows 6 rows at a time */}
                    <div
                      style={{
                        display: 'flex',
                        flexDirection: 'column',
                        gap: 'var(--space-md)',
                        overflowY: 'auto',
                        maxHeight: SCROLL_MAX_HEIGHT,
                        paddingRight: 'var(--space-xs)',
                      }}
                    >
                      {/* Factor data rows */}
                      {attribution.period_attribution.map((row) => {
                        const contrib = row.contribution_pct ?? 0
                        const isHovered = hoveredKey === row.factor_key
                        return (
                          <div
                            className="list-row"
                            key={row.factor_key}
                            style={{
                              fontSize: 'var(--font-caption)',
                              cursor: 'default',
                              outline: isHovered ? `var(--border-thin) solid ${FACTOR_LINE_COLORS[row.factor_key] ?? FACTOR_DEFAULT_COLOR}` : undefined,
                            }}
                            onMouseEnter={() => setHoveredKey(row.factor_key)}
                            onMouseLeave={() => setHoveredKey(null)}
                          >
                            <span style={{ flex: 2, display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                              <span
                                style={{
                                  display: 'inline-block',
                                  width: 'var(--space-sm)',
                                  height: 'var(--space-sm)',
                                  borderRadius: 'var(--space-xxs)',
                                  backgroundColor: FACTOR_LINE_COLORS[row.factor_key] ?? FACTOR_DEFAULT_COLOR,
                                  flexShrink: 0,
                                }}
                              />
                              {row.factor_label}
                            </span>
                            <span style={{ flex: 1, textAlign: 'right', color: 'var(--color-text-muted)' }}>
                              {formatBeta(row.avg_beta)}
                            </span>
                            <span style={{ flex: 1, textAlign: 'right', color: 'var(--color-text-muted)' }}>
                              {formatPct(row.factor_return_pct)}
                            </span>
                            <span
                              style={{
                                flex: 1,
                                textAlign: 'right',
                                color: contrib >= 0 ? 'var(--color-value-positive)' : 'var(--color-value-negative)',
                                fontWeight: 500,
                              }}
                            >
                              {formatPct(row.contribution_pct)}
                            </span>
                          </div>
                        )
                      })}

                      {/* Unexplained row */}
                      {attribution.total_unexplained_pct != null && (
                        <div
                          className="list-row"
                          style={{
                            fontSize: 'var(--font-caption)',
                            cursor: 'default',
                            outline: hoveredKey === 'unexplained' ? `var(--border-thin) solid ${UNEXPLAINED_COLOR}` : undefined,
                          }}
                          onMouseEnter={() => setHoveredKey('unexplained')}
                          onMouseLeave={() => setHoveredKey(null)}
                        >
                          <span style={{ flex: 2, display: 'flex', alignItems: 'center', gap: 'var(--space-xs)' }}>
                            <span
                              style={{
                                display: 'inline-block',
                                width: 'var(--space-sm)',
                                height: 'var(--space-sm)',
                                borderRadius: 'var(--space-xxs)',
                                backgroundColor: UNEXPLAINED_COLOR,
                                flexShrink: 0,
                              }}
                            />
                            Unexplained / idiosyncratic
                          </span>
                          <span style={{ flex: 1, textAlign: 'right', color: 'var(--color-text-disabled)' }}>—</span>
                          <span style={{ flex: 1, textAlign: 'right', color: 'var(--color-text-disabled)' }}>—</span>
                          <span
                            style={{
                              flex: 1,
                              textAlign: 'right',
                              color: (attribution.total_unexplained_pct ?? 0) >= 0 ? 'var(--color-value-positive)' : 'var(--color-value-negative)',
                              fontWeight: 500,
                            }}
                          >
                            {formatPct(attribution.total_unexplained_pct)}
                          </span>
                        </div>
                      )}
                    </div>

                    {/* Total footer — not scrollable */}
                    <div
                      className="list-row"
                      style={{
                        fontSize: 'var(--font-caption)',
                        fontWeight: 700,
                        borderTop: 'var(--border-thin) solid var(--color-border-strong)',
                        paddingTop: 'var(--space-xs)',
                        cursor: 'default',
                        outline: hoveredKey === 'portfolio' ? `var(--border-thin) solid ${PORTFOLIO_COLOR}` : undefined,
                      }}
                      onMouseEnter={() => setHoveredKey('portfolio')}
                      onMouseLeave={() => setHoveredKey(null)}
                    >
                      <span style={{ flex: 2 }}>Total Portfolio (arithmetic)</span>
                      <span style={{ flex: 1, textAlign: 'right' }} />
                      <span style={{ flex: 1, textAlign: 'right' }} />
                      <span
                        style={{
                          flex: 1,
                          textAlign: 'right',
                          color: (attribution.total_portfolio_return_pct ?? 0) >= 0 ? 'var(--color-value-positive)' : 'var(--color-value-negative)',
                        }}
                      >
                        {formatPct(attribution.total_portfolio_return_pct)}
                      </span>
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </>
      )}
    </CardShell>
  )
}
