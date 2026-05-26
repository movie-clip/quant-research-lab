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

type SectorPieState =
  | { kind: 'data'; slices: SectorSlice[]; basisNote: string }
  | { kind: 'unavailable' }

function buildState(
  result: DashboardAnalysis | null,
  exposureResult: ExposureAnalysis | null,
): SectorPieState {
  if (exposureResult) {
    const status = exposureResult.exposure_availability?.lookthrough_status ?? 'unavailable'
    const ltSectors = (exposureResult.lookthrough_sector_exposure ?? []).filter((s) => s.weight > 0)
    if (status !== 'unavailable' && ltSectors.length) {
      return {
        kind: 'data',
        slices: ltSectors.map((s, i) => ({ name: s.sector, weight: s.weight, color: sectorColor(s.sector, i) })),
        basisNote: status === 'live' ? 'Look-through composition' : 'Look-through (partial)',
      }
    }
    const expSectors = (exposureResult.overview?.sector_allocation ?? []).filter((s) => s.weight > 0)
    if (expSectors.length) {
      return {
        kind: 'data',
        slices: expSectors.map((s, i) => ({ name: s.sector, weight: s.weight, color: sectorColor(s.sector, i) })),
        basisNote: 'Imported snapshot composition',
      }
    }
  }

  const dashSectors = (result?.overview?.sector_allocation ?? []).filter((s) => s.weight > 0)
  if (dashSectors.length) {
    return {
      kind: 'data',
      slices: dashSectors.map((s, i) => ({ name: s.sector, weight: s.weight, color: sectorColor(s.sector, i) })),
      basisNote: 'Imported snapshot composition',
    }
  }

  return { kind: 'unavailable' }
}

// ─── SVG pie geometry ─────────────────────────────────────────────────────────

const CX = 80
const CY = 80
const R = 72
const GAP_RAD = 0.03 // gap between slices in radians

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
    if (a1 <= a0) continue // slice too small after gap

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
  activeIndex,
  onHover,
}: {
  sliceGeometry: SliceGeometry[]
  activeIndex: number | null
  onHover: (i: number | null) => void
}) {
  return (
    <svg
      viewBox="0 0 160 160"
      className="sector-pie-svg"
      aria-hidden="true"
      style={{ display: 'block', width: '100%', height: '100%' }}
    >
      {sliceGeometry.map(({ slice, d }, i) => {
        const isActive = activeIndex === i
        const isOther = activeIndex != null && !isActive
        return (
          <path
            key={slice.name}
            d={d}
            fill={slice.color}
            style={{
              opacity: isOther ? 0.3 : 1,
              transition: 'opacity 0.15s ease',
              cursor: 'default',
              filter: isActive ? `drop-shadow(0 0 3px ${slice.color}88)` : undefined,
            }}
            onMouseEnter={() => onHover(i)}
            onMouseLeave={() => onHover(null)}
          />
        )
      })}
    </svg>
  )
}

// ─── public component ─────────────────────────────────────────────────────────

export type SectorPieCardProps = {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
}

export function SectorPieCard({ result, exposureResult }: SectorPieCardProps) {
  const [activeIndex, setActiveIndex] = useState<number | null>(null)
  const state = buildState(result, exposureResult)

  if (state.kind === 'unavailable') {
    return (
      <section className="summary-card sector-pie-card" aria-label="Sector Composition">
        <div className="sector-pie-header">
          <p className="panel-label">Sector Composition</p>
        </div>
        <p className="helper" style={{ marginTop: 4 }}>
          Unavailable — import a portfolio to see sector mix.
        </p>
      </section>
    )
  }

  const sliceGeometry = buildSliceGeometry(state.slices)
  const activeSlice = activeIndex != null ? state.slices[activeIndex] : null

  return (
    <section className="summary-card sector-pie-card" aria-label="Sector Composition">
      <div className="sector-pie-header">
        <p className="panel-label">Sector Composition</p>
        <p className="helper">{state.basisNote}</p>
      </div>
      <div className="sector-pie-body">
        <div className="sector-pie-chart-wrap">
          <PieSvg sliceGeometry={sliceGeometry} activeIndex={activeIndex} onHover={setActiveIndex} />
        </div>
        <ul className="sector-pie-legend" aria-label="Sector weights">
          {state.slices.map((slice, index) => (
            <li
              key={slice.name}
              className={`sector-legend-row${activeIndex === index ? ' sector-legend-row-active' : ''}`}
              onMouseEnter={() => setActiveIndex(index)}
              onMouseLeave={() => setActiveIndex(null)}
            >
              <span className="sector-legend-dot" style={{ background: slice.color }} />
              <span className="sector-legend-name">{slice.name}</span>
              <span className="sector-legend-pct">{(slice.weight * 100).toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>
      <div
        className="sector-pie-tooltip-bar"
        style={activeSlice ? { borderLeftColor: activeSlice.color } : undefined}
        aria-live="polite"
      >
        {activeSlice ? (
          <>
            <span className="sector-pie-tooltip-name">{activeSlice.name}</span>
            <span className="sector-pie-tooltip-pct">{(activeSlice.weight * 100).toFixed(1)}%</span>
          </>
        ) : (
          <span className="sector-pie-tooltip-hint">Hover a slice for details</span>
        )}
      </div>
    </section>
  )
}
