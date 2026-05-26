import type { DashboardAnalysis, ExposureAnalysis } from './types'

// ─── colour palette ─────────────────────────────────────────────────────────

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

// ─── data model ─────────────────────────────────────────────────────────────

type SectorSlice = { name: string; weight: number; color: string }

type SectorDonutState =
  | { kind: 'data'; slices: SectorSlice[]; basisNote: string }
  | { kind: 'unavailable' }

function buildState(
  result: DashboardAnalysis | null,
  exposureResult: ExposureAnalysis | null,
): SectorDonutState {
  // 1. Look-through sectors (best trust)
  if (exposureResult) {
    const status = exposureResult.exposure_availability?.lookthrough_status ?? 'unavailable'
    const ltSectors = (exposureResult.lookthrough_sector_exposure ?? []).filter((s) => s.weight > 0)
    if (status !== 'unavailable' && ltSectors.length) {
      return {
        kind: 'data',
        slices: ltSectors.slice(0, 10).map((s, i) => ({ name: s.sector, weight: s.weight, color: sectorColor(s.sector, i) })),
        basisNote: status === 'live' ? 'Look-through composition' : 'Look-through (partial)',
      }
    }
    // 2. Exposure snapshot truth
    const expSectors = (exposureResult.overview?.sector_allocation ?? []).filter((s) => s.weight > 0)
    if (expSectors.length) {
      return {
        kind: 'data',
        slices: expSectors.slice(0, 10).map((s, i) => ({ name: s.sector, weight: s.weight, color: sectorColor(s.sector, i) })),
        basisNote: 'Imported snapshot composition',
      }
    }
  }

  // 3. Dashboard snapshot truth
  const dashSectors = (result?.overview?.sector_allocation ?? []).filter((s) => s.weight > 0)
  if (dashSectors.length) {
    return {
      kind: 'data',
      slices: dashSectors.slice(0, 10).map((s, i) => ({ name: s.sector, weight: s.weight, color: sectorColor(s.sector, i) })),
      basisNote: 'Imported snapshot composition',
    }
  }

  return { kind: 'unavailable' }
}

// ─── donut SVG ───────────────────────────────────────────────────────────────

const CX = 50
const CY = 50
const R = 36
const STROKE = 16
const CIRCUMFERENCE = 2 * Math.PI * R
const GAP = 1.5 // px between segments

function DonutSvg({ slices }: { slices: SectorSlice[] }) {
  let cumulative = 0

  const segments = slices.map((slice) => {
    const arcLength = Math.max(0, slice.weight * CIRCUMFERENCE - GAP)
    const offset = -(cumulative * CIRCUMFERENCE)
    cumulative += slice.weight
    return { ...slice, arcLength, offset }
  })

  return (
    <svg
      viewBox="0 0 100 100"
      className="sector-donut-svg"
      aria-hidden="true"
      style={{ display: 'block', width: '100%', height: '100%' }}
    >
      {/* track */}
      <circle cx={CX} cy={CY} r={R} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth={STROKE} />
      {/* segments */}
      {segments.map((seg) => (
        <circle
          key={seg.name}
          cx={CX}
          cy={CY}
          r={R}
          fill="none"
          stroke={seg.color}
          strokeWidth={STROKE}
          strokeDasharray={`${seg.arcLength} ${CIRCUMFERENCE}`}
          strokeDashoffset={seg.offset}
          strokeLinecap="butt"
          transform={`rotate(-90 ${CX} ${CY})`}
        />
      ))}
    </svg>
  )
}

// ─── public component ────────────────────────────────────────────────────────

type SectorDonutCardProps = {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
}

export function SectorDonutCard({ result, exposureResult }: SectorDonutCardProps) {
  const state = buildState(result, exposureResult)

  if (state.kind === 'unavailable') {
    return (
      <section className="summary-card sector-donut-card" aria-label="Sector Composition">
        <p className="panel-label">Sector Composition</p>
        <p className="helper" style={{ marginTop: 4 }}>Unavailable — import a portfolio to see sector mix.</p>
      </section>
    )
  }

  return (
    <section className="summary-card sector-donut-card" aria-label="Sector Composition">
      <div className="sector-donut-header">
        <p className="panel-label">Sector Composition</p>
        <p className="helper">{state.basisNote}</p>
      </div>
      <div className="sector-donut-body">
        <div className="sector-donut-chart-wrap">
          <DonutSvg slices={state.slices} />
        </div>
        <ul className="sector-donut-legend" aria-label="Sector weights">
          {state.slices.map((slice) => (
            <li key={slice.name} className="sector-legend-row">
              <span className="sector-legend-dot" style={{ background: slice.color }} />
              <span className="sector-legend-name">{slice.name}</span>
              <span className="sector-legend-pct">{(slice.weight * 100).toFixed(1)}%</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  )
}
