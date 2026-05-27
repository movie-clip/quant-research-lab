import { useState } from 'react'

import type { DashboardAnalysis, ExposureAnalysis } from './types'

// ─── colour palette ──────────────────────────────────────────────────────────

const NAMED_COLORS: Record<string, string> = {
  'Technology': '#4a8fe8',
  'Financials': '#7b68ee',
  'Health Care': '#3ec878',
  'Consumer Discretionary': '#ff8c42',
  'Communication Services': '#e06b6b',
  'Industrials': '#20b2aa',
  'Energy': '#e8c040',
  'Materials': '#7bbf7b',
  'Utilities': '#b09ac0',
  'Consumer Staples': '#c8a050',
  'Real Estate': '#c08060',
  'Equity ETF': '#60a8c8',
  'Commodity ETF': '#d4a060',
}

const FALLBACK_COLORS = [
  '#4a8fe8', '#7b68ee', '#3ec878', '#ff8c42',
  '#e06b6b', '#20b2aa', '#e8c040', '#b084f5',
]

function sectorColor(name: string, index: number): string {
  return NAMED_COLORS[name] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length]
}

// ─── data model ──────────────────────────────────────────────────────────────

type SectorSlice = { name: string; weight: number; color: string }
type HoldingRow = { symbol: string; weight: number }

type SectorPieState =
  | { kind: 'data'; slices: SectorSlice[]; breakdown: Record<string, HoldingRow[]> }
  | { kind: 'unavailable' }

const MIN_SLICE_WEIGHT = 0.0005

function buildState(
  result: DashboardAnalysis | null,
  exposureResult: ExposureAnalysis | null,
): SectorPieState {
  const rawBreakdown = exposureResult?.overview?.sector_position_breakdown ?? {}
  const breakdown: Record<string, HoldingRow[]> = {}
  for (const [sector, rows] of Object.entries(rawBreakdown)) {
    breakdown[sector] = [...rows].sort((a, b) => b.weight - a.weight)
  }

  const expSectors = (exposureResult?.overview?.sector_allocation ?? []).filter((s) => s.weight >= MIN_SLICE_WEIGHT)
  if (expSectors.length) {
    return {
      kind: 'data',
      slices: expSectors.map((s, i) => ({ name: s.sector, weight: s.weight, color: sectorColor(s.sector, i) })),
      breakdown,
    }
  }

  const dashSectors = (result?.overview?.sector_allocation ?? []).filter((s) => s.weight >= MIN_SLICE_WEIGHT)
  if (dashSectors.length) {
    return {
      kind: 'data',
      slices: dashSectors.map((s, i) => ({ name: s.sector, weight: s.weight, color: sectorColor(s.sector, i) })),
      breakdown,
    }
  }

  return { kind: 'unavailable' }
}

// ─── SVG pie geometry ─────────────────────────────────────────────────────────

const CX = 80
const CY = 80
const R = 72
const GAP_RAD = 0.03

interface SliceGeometry {
  slice: SectorSlice
  d: string
  midAngle: number
}

function buildSliceGeometry(slices: SectorSlice[]): SliceGeometry[] {
  const result: SliceGeometry[] = []
  let cum = 0
  for (const slice of slices) {
    const a0 = cum * 2 * Math.PI - Math.PI / 2 + GAP_RAD / 2
    const a1 = (cum + slice.weight) * 2 * Math.PI - Math.PI / 2 - GAP_RAD / 2
    cum += slice.weight
    if (a1 <= a0) continue

    const x0 = (CX + R * Math.cos(a0)).toFixed(3)
    const y0 = (CY + R * Math.sin(a0)).toFixed(3)
    const x1 = (CX + R * Math.cos(a1)).toFixed(3)
    const y1 = (CY + R * Math.sin(a1)).toFixed(3)
    const large = a1 - a0 > Math.PI ? 1 : 0
    const d = `M ${CX} ${CY} L ${x0} ${y0} A ${R} ${R} 0 ${large} 1 ${x1} ${y1} Z`

    result.push({ slice, d, midAngle: (a0 + a1) / 2 })
  }
  return result
}

// ─── SVG component ───────────────────────────────────────────────────────────

function PieSvg({
  sliceGeometry,
  hoverIndex,
  selectedIndex,
  onHover,
  onSelect,
}: {
  sliceGeometry: SliceGeometry[]
  hoverIndex: number | null
  selectedIndex: number
  onHover: (i: number | null) => void
  onSelect: (i: number) => void
}) {
  return (
    <svg
      viewBox="0 0 160 160"
      className="sector-pie-svg"
      aria-hidden="true"
      style={{ display: 'block', width: '100%', height: 'auto' }}
    >
      {sliceGeometry.map(({ slice, d }, i) => {
        const isHovered = hoverIndex === i
        const isSelected = selectedIndex === i
        const isDimmed = hoverIndex != null && !isHovered
        return (
          <path
            key={slice.name}
            d={d}
            fill={slice.color}
            style={{
              opacity: isDimmed ? 0.25 : 1,
              transition: 'opacity 0.15s ease, filter 0.15s ease',
              cursor: 'pointer',
              filter: isHovered
                ? `drop-shadow(0 0 4px ${slice.color}bb)`
                : isSelected && hoverIndex == null
                  ? `drop-shadow(0 0 3px ${slice.color}66)`
                  : undefined,
            }}
            onMouseEnter={() => onHover(i)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onSelect(i)}
          />
        )
      })}
    </svg>
  )
}

// ─── holdings panel ───────────────────────────────────────────────────────────

function HoldingsPanel({
  slice,
  holdings,
}: {
  slice: SectorSlice
  holdings: HoldingRow[]
}) {
  return (
    <div className="sector-holdings-panel">
      <p className="sector-holdings-cap" style={{ color: slice.color }}>Holdings</p>
      {holdings.length > 0 ? (
        <ul className="sector-holdings-list" aria-label={`Holdings in ${slice.name}`}>
          {holdings.map((h) => (
            <li key={h.symbol} className="sector-holdings-row">
              <span className="sector-holdings-symbol">{h.symbol}</span>
              <span className="sector-holdings-weight">{(h.weight * 100).toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="sector-holdings-empty">No detail available</p>
      )}
    </div>
  )
}

// ─── public component ─────────────────────────────────────────────────────────

export type SectorPieCardProps = {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
}

export function SectorPieCard({ result, exposureResult }: SectorPieCardProps) {
  const [selectedIndex, setSelectedIndex] = useState<number>(0)
  const [hoverIndex, setHoverIndex] = useState<number | null>(null)

  const state = buildState(result, exposureResult)

  if (state.kind === 'unavailable') {
    return (
      <section className="summary-card sector-pie-card" aria-label="Sector Composition">
        <p className="panel-label">Sector Composition</p>
        <p className="helper" style={{ marginTop: 4 }}>
          Unavailable — import a portfolio to see sector mix.
        </p>
      </section>
    )
  }

  const displayIndex = hoverIndex ?? selectedIndex
  const sliceGeometry = buildSliceGeometry(state.slices)
  const displaySlice = state.slices[displayIndex]
  const displayHoldings = state.breakdown[displaySlice?.name] ?? []

  return (
    <section className="summary-card sector-pie-card" aria-label="Sector Composition">
      <p className="panel-label">Sector Composition</p>
      <div className="sector-pie-body">
        <div className="sector-pie-chart-wrap">
          <PieSvg
            sliceGeometry={sliceGeometry}
            hoverIndex={hoverIndex}
            selectedIndex={selectedIndex}
            onHover={setHoverIndex}
            onSelect={setSelectedIndex}
          />
        </div>
        <div className="sector-legend-column">
          <p className="sector-holdings-cap" style={{ color: 'rgba(248,251,254,0.28)' }}>Sectors</p>
          <ul className="sector-pie-legend" aria-label="Sector weights">
            {state.slices.map((slice, index) => {
              const isSelected = selectedIndex === index
              const isHovered = hoverIndex === index
              return (
                <li
                  key={slice.name}
                  className={[
                    'sector-legend-row',
                    isSelected ? 'sector-legend-row-selected' : '',
                    isHovered ? 'sector-legend-row-active' : '',
                  ].filter(Boolean).join(' ')}
                  style={isSelected ? { borderLeftColor: slice.color } : undefined}
                  onMouseEnter={() => setHoverIndex(index)}
                  onMouseLeave={() => setHoverIndex(null)}
                  onClick={() => setSelectedIndex(index)}
                >
                  <span className="sector-legend-dot" style={{ background: slice.color }} />
                  <span className="sector-legend-name">{slice.name}</span>
                  <span className="sector-legend-pct">{(slice.weight * 100).toFixed(1)}%</span>
                </li>
              )
            })}
          </ul>
        </div>
        {displaySlice && (
          <HoldingsPanel
            slice={displaySlice}
            holdings={displayHoldings}
          />
        )}
      </div>
    </section>
  )
}
