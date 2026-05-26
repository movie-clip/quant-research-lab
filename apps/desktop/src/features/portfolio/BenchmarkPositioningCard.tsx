import type { ExposureAnalysis } from './types'

// ─── types ────────────────────────────────────────────────────────────────────

type BenchmarkTrust = 'verified' | 'degraded' | 'partial' | 'unavailable'

type BenchmarkRow = {
  symbol: string
  portfolioWeight: number
  benchmarkWeight: number
  activeWeight: number
}

type BenchmarkState = {
  trust: BenchmarkTrust
  benchmarkSymbol: string
  portfolioInBenchmarkWeight: number | null
  activeShare: number | null
  overweights: BenchmarkRow[]
  underweights: BenchmarkRow[]
  coverageNote: string
}

// ─── helpers ──────────────────────────────────────────────────────────────────

function formatPct(value: number | null | undefined): string {
  return value == null ? '—' : `${(value * 100).toFixed(2)}%`
}

function formatActiveShort(value: number): string {
  const pct = (Math.abs(value) * 100).toFixed(1)
  return value >= 0 ? `+${pct}%` : `−${pct}%`
}

// ─── logic ────────────────────────────────────────────────────────────────────

function getBenchmarkTrust(result: ExposureAnalysis): BenchmarkTrust {
  const overlapStatus = result.exposure_availability?.benchmark_overlap_status ?? 'unavailable'
  if (overlapStatus === 'unavailable') return 'unavailable'
  if (overlapStatus === 'partial') return 'partial'
  const holdingsSupport = result.run_metadata?.source_status?.benchmark_holdings ?? 'unavailable'
  if (holdingsSupport === 'verified') return 'verified'
  if (holdingsSupport === 'degraded') return 'degraded'
  return 'unavailable'
}

function normalizeBenchmarkRows(
  rows:
    | ExposureAnalysis['market_overlap']['top_overweights']
    | ExposureAnalysis['market_overlap']['top_underweights']
    | undefined,
  direction: 'overweight' | 'underweight',
): BenchmarkRow[] {
  return (rows ?? [])
    .filter((row) => {
      if (row.portfolio_weight == null || row.benchmark_weight == null || row.active_weight == null) return false
      return direction === 'overweight' ? row.active_weight > 0 : row.active_weight < 0
    })
    .map((row) => ({
      symbol: row.symbol,
      portfolioWeight: row.portfolio_weight,
      benchmarkWeight: row.benchmark_weight,
      activeWeight: row.active_weight,
    }))
    .sort((a, b) => {
      const d = Math.abs(b.activeWeight) - Math.abs(a.activeWeight)
      if (d !== 0) return d
      const pd = b.portfolioWeight - a.portfolioWeight
      if (pd !== 0) return pd
      const bd = b.benchmarkWeight - a.benchmarkWeight
      if (bd !== 0) return bd
      return a.symbol.localeCompare(b.symbol)
    })
}

function buildBenchmarkState(result: ExposureAnalysis): BenchmarkState {
  const trust = getBenchmarkTrust(result)
  const benchmarkSymbol =
    result.market_overlap?.benchmark_symbol
    ?? result.run_metadata?.reproducibility?.benchmark_symbol
    ?? 'benchmark'

  const overweights = normalizeBenchmarkRows(result.market_overlap?.top_overweights, 'overweight')
  const underweights = normalizeBenchmarkRows(result.market_overlap?.top_underweights, 'underweight')

  let coverageNote = 'Benchmark-relative positioning unavailable for this snapshot.'
  if (trust === 'verified') {
    coverageNote = `Positioning available versus ${benchmarkSymbol}.`
  } else if (trust === 'degraded') {
    coverageNote = `Positioning degraded versus ${benchmarkSymbol}.`
  } else if (trust === 'partial') {
    coverageNote = `Positioning partial versus ${benchmarkSymbol}.`
  }

  return {
    trust,
    benchmarkSymbol,
    portfolioInBenchmarkWeight: result.market_overlap?.portfolio_in_benchmark_weight ?? null,
    activeShare: result.market_overlap?.active_share ?? null,
    overweights,
    underweights,
    coverageNote,
  }
}

// ─── badge ────────────────────────────────────────────────────────────────────

const TRUST_BADGE: Record<BenchmarkTrust, string> = {
  verified: 'dashboard-snapshot-status-trusted',
  degraded: 'dashboard-snapshot-status-degraded',
  partial: 'dashboard-snapshot-status-partial',
  unavailable: 'dashboard-snapshot-status-unavailable',
}

// ─── component ────────────────────────────────────────────────────────────────

type BenchmarkPositioningCardProps = {
  exposureResult: ExposureAnalysis | null
}

export function BenchmarkPositioningCard({ exposureResult }: BenchmarkPositioningCardProps) {
  if (!exposureResult) {
    return (
      <section className="summary-card benchmark-positioning-card" aria-label="Benchmark Positioning">
        <p className="panel-label">Benchmark Positioning</p>
        <p className="helper" style={{ marginTop: 4 }}>
          Unavailable — import a portfolio to see benchmark-relative positioning.
        </p>
      </section>
    )
  }

  const bm = buildBenchmarkState(exposureResult)
  const overweights = bm.overweights.slice(0, 5)
  const underweights = bm.underweights.slice(0, 5)
  const hasRows = overweights.length > 0 || underweights.length > 0

  return (
    <section className="summary-card benchmark-positioning-card" aria-label="Benchmark Positioning">
      <div className="benchmark-card-header">
        <p className="panel-label">Benchmark Positioning</p>
        <span className={`dashboard-snapshot-status ${TRUST_BADGE[bm.trust]}`}>{bm.trust}</span>
      </div>

      <p className="helper benchmark-card-note">{bm.coverageNote}</p>

      <div className="benchmark-card-summary">
        <div className="benchmark-card-metric">
          <span className="stat-label">In benchmark</span>
          <span className="benchmark-card-value">
            {bm.trust === 'unavailable' ? '—' : formatPct(bm.portfolioInBenchmarkWeight)}
          </span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Active share</span>
          <span className="benchmark-card-value">
            {bm.trust === 'unavailable' ? '—' : formatPct(bm.activeShare)}
          </span>
        </div>
      </div>

      {hasRows ? (
        <div className="benchmark-card-lists">
          <div className="benchmark-card-col">
            <p className="benchmark-card-col-label benchmark-card-col-over">↑ Over</p>
            <div className="benchmark-card-col-rows">
              {overweights.map((row) => (
                <div className="benchmark-card-row" key={`over-${row.symbol}`}>
                  <span className="benchmark-card-symbol">{row.symbol}</span>
                  <span className="benchmark-card-active benchmark-card-active-over">
                    {formatActiveShort(row.activeWeight)}
                  </span>
                </div>
              ))}
            </div>
          </div>
          <div className="benchmark-card-col">
            <p className="benchmark-card-col-label benchmark-card-col-under">↓ Under</p>
            <div className="benchmark-card-col-rows">
              {underweights.length ? (
                underweights.map((row) => (
                  <div className="benchmark-card-row" key={`under-${row.symbol}`}>
                    <span className="benchmark-card-symbol">{row.symbol}</span>
                    <span className="benchmark-card-active benchmark-card-active-under">
                      {formatActiveShort(row.activeWeight)}
                    </span>
                  </div>
                ))
              ) : (
                <p className="helper" style={{ fontSize: 11 }}>None</p>
              )}
            </div>
          </div>
        </div>
      ) : (
        <div className="benchmark-card-empty">
          <p className="empty-state-title">Benchmark-relative positioning unavailable</p>
          <p className="helper">No benchmark cues shown rather than implying neutral positioning.</p>
        </div>
      )}
    </section>
  )
}
