import { useEffect, useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

import type { FactorAttributionResponse, ImportedSnapshot } from './types'
import { runAttributionEngine } from './portfolioAnalysisAdapter'

type AttributionWindow = 20 | 60 | 252

const WINDOW_OPTIONS: AttributionWindow[] = [20, 60, 252]
const WINDOW_LABELS: Record<AttributionWindow, string> = { 20: '20d', 60: '60d', 252: '252d' }

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

const UNEXPLAINED_COLOR = '#6b7280'
const PORTFOLIO_COLOR = '#ffffff'

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

function SyntheticBadge() {
  const [showTooltip, setShowTooltip] = useState(false)
  return (
    <span
      className="backtest-source-badge attribution-synthetic-badge"
      style={{ position: 'relative', cursor: 'help' }}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      Synthetic
      {showTooltip && (
        <span
          className="attribution-badge-tooltip"
          style={{
            position: 'absolute',
            bottom: '100%',
            left: 0,
            backgroundColor: '#1a1f2e',
            border: '1px solid #2d3448',
            borderRadius: '4px',
            padding: '6px 10px',
            fontSize: '12px',
            color: '#a0aec0',
            whiteSpace: 'nowrap',
            zIndex: 100,
            marginBottom: '4px',
            pointerEvents: 'none',
          }}
        >
          Returns are reconstructed from current holdings and historical factor proxy prices.
        </span>
      )}
    </span>
  )
}

function WindowSelector({
  value,
  onChange,
}: {
  value: AttributionWindow
  onChange: (w: AttributionWindow) => void
}) {
  return (
    <div className="rolling-window-selector" style={{ display: 'flex', gap: '4px' }}>
      {WINDOW_OPTIONS.map((w) => (
        <button
          key={w}
          type="button"
          className={`window-option-btn${value === w ? ' window-option-btn-active' : ''}`}
          onClick={() => onChange(w)}
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
        backgroundColor: '#1a1f2e',
        border: '1px solid #2d3448',
        borderRadius: '4px',
        padding: '8px 12px',
        fontSize: 12,
        minWidth: 200,
      }}
    >
      <p style={{ color: '#a0aec0', marginBottom: 6, marginTop: 0, fontWeight: 600 }}>
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
              gap: 16,
              marginBottom: isPortfolio ? 4 : 2,
              paddingBottom: isPortfolio ? 4 : 0,
              borderBottom: isPortfolio ? '1px solid #2d3448' : 'none',
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
  const [window, setWindow] = useState<AttributionWindow>(60)
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
    <section className="dashboard-bottom-grid exposure-primary-section exposure-shell-section">
      <div className="section-header-inline sector-list-header exposure-section-header">
        <div className="panel-section-title-block">
          <p className="panel-label">Factor Return Attribution</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <SyntheticBadge />
          <WindowSelector value={window} onChange={setWindow} />
        </div>
      </div>

      {loadState === 'loading' && (
        <div className="empty-state-panel compact-empty-state">
          <p className="helper">Computing attribution…</p>
        </div>
      )}

      {loadState === 'error' && (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Attribution unavailable</p>
          <p className="helper">{errorMsg ?? 'The attribution engine returned an error.'}</p>
        </div>
      )}

      {loadState === 'idle' && (
        <div className="empty-state-panel compact-empty-state">
          <p className="helper">Import a portfolio to view factor return attribution.</p>
        </div>
      )}

      {loadState === 'done' && attribution && (
        <>
          {attribution.attribution_status === 'unavailable' ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Not enough history</p>
              <p className="helper">
                Need at least {window + 1} trading days of common history between portfolio and factor proxies.
                Try a shorter window or import a longer statement.
              </p>
            </div>
          ) : (
            <>
              {/* Cumulative attribution line chart */}
              <div style={{ width: '100%', height: 280, marginBottom: '24px' }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#2d3448" />
                    <XAxis
                      dataKey="date"
                      tickFormatter={formatDateLabel}
                      tick={{ fontSize: 10, fill: '#6b7280' }}
                      tickLine={false}
                      minTickGap={40}
                    />
                    <YAxis
                      tickFormatter={(v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`}
                      tick={{ fontSize: 10, fill: '#6b7280' }}
                      tickLine={false}
                      width={56}
                    />
                    <ReferenceLine y={0} stroke="#4a5568" strokeWidth={1} />
                    <Tooltip content={<AttributionTooltip />} />

                    {/* Factor contribution lines */}
                    {activeFactorKeys.map((key) => (
                      <Line
                        key={key}
                        type="monotone"
                        dataKey={key}
                        stroke={FACTOR_LINE_COLORS[key] ?? '#888'}
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
                </ResponsiveContainer>
              </div>

              {/* Period attribution table — collapsible, scrollable body */}
              <div>
                <button
                  type="button"
                  onClick={() => setTableExpanded((prev) => !prev)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '6px',
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '0 0 8px 0',
                    color: '#6b7280',
                    fontSize: '11px',
                  }}
                >
                  <span
                    style={{
                      display: 'inline-block',
                      width: 0,
                      height: 0,
                      borderLeft: '4px solid transparent',
                      borderRight: '4px solid transparent',
                      borderTop: tableExpanded ? '5px solid #6b7280' : undefined,
                      borderBottom: tableExpanded ? undefined : '5px solid #6b7280',
                    }}
                  />
                  Period attribution — arithmetic (not compounded)
                </button>

                {tableExpanded && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                    {/* Header row — not scrollable */}
                    <div className="list-row" style={{ fontWeight: 600, fontSize: '11px', color: '#6b7280' }}>
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
                        gap: '14px',
                        overflowY: 'auto',
                        maxHeight: SCROLL_MAX_HEIGHT,
                        paddingRight: '4px',
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
                              fontSize: '12px',
                              cursor: 'default',
                              outline: isHovered ? `1px solid ${FACTOR_LINE_COLORS[row.factor_key] ?? '#888'}` : undefined,
                            }}
                            onMouseEnter={() => setHoveredKey(row.factor_key)}
                            onMouseLeave={() => setHoveredKey(null)}
                          >
                            <span style={{ flex: 2, display: 'flex', alignItems: 'center', gap: '6px' }}>
                              <span
                                style={{
                                  display: 'inline-block',
                                  width: '8px',
                                  height: '8px',
                                  borderRadius: '2px',
                                  backgroundColor: FACTOR_LINE_COLORS[row.factor_key] ?? '#888',
                                  flexShrink: 0,
                                }}
                              />
                              {row.factor_label}
                            </span>
                            <span style={{ flex: 1, textAlign: 'right', color: '#a0aec0' }}>
                              {formatBeta(row.avg_beta)}
                            </span>
                            <span style={{ flex: 1, textAlign: 'right', color: '#a0aec0' }}>
                              {formatPct(row.factor_return_pct)}
                            </span>
                            <span
                              style={{
                                flex: 1,
                                textAlign: 'right',
                                color: contrib >= 0 ? '#48bb78' : '#fc8181',
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
                            fontSize: '12px',
                            cursor: 'default',
                            outline: hoveredKey === 'unexplained' ? `1px solid ${UNEXPLAINED_COLOR}` : undefined,
                          }}
                          onMouseEnter={() => setHoveredKey('unexplained')}
                          onMouseLeave={() => setHoveredKey(null)}
                        >
                          <span style={{ flex: 2, display: 'flex', alignItems: 'center', gap: '6px' }}>
                            <span
                              style={{
                                display: 'inline-block',
                                width: '8px',
                                height: '8px',
                                borderRadius: '2px',
                                backgroundColor: UNEXPLAINED_COLOR,
                                flexShrink: 0,
                              }}
                            />
                            Unexplained / idiosyncratic
                          </span>
                          <span style={{ flex: 1, textAlign: 'right', color: '#6b7280' }}>—</span>
                          <span style={{ flex: 1, textAlign: 'right', color: '#6b7280' }}>—</span>
                          <span
                            style={{
                              flex: 1,
                              textAlign: 'right',
                              color: (attribution.total_unexplained_pct ?? 0) >= 0 ? '#48bb78' : '#fc8181',
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
                        fontSize: '12px',
                        fontWeight: 700,
                        borderTop: '1px solid #2d3448',
                        paddingTop: '4px',
                        cursor: 'default',
                        outline: hoveredKey === 'portfolio' ? `1px solid ${PORTFOLIO_COLOR}` : undefined,
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
                          color: (attribution.total_portfolio_return_pct ?? 0) >= 0 ? '#48bb78' : '#fc8181',
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
    </section>
  )
}
