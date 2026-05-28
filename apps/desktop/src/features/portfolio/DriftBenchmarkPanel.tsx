import type { DriftResult, DriftWindow } from './types'
import { IndexedReturnChart } from './IndexedReturnChart'

const BENCHMARK_OPTIONS = [
  { value: 'SPY', label: 'S&P 500 (SPY)' },
  { value: 'QQQ', label: 'Nasdaq 100 (QQQ)' },
  { value: 'IEF', label: '7-10yr Treasury (IEF)' },
  { value: 'VT', label: 'Total World (VT)' },
]

function formatReturn(value: number | null | undefined): string {
  if (value == null) return '—'
  const sign = value >= 0 ? '+' : ''
  return `${sign}${value.toFixed(2)}%`
}

function spreadTone(spread: number | null | undefined): string {
  if (spread == null) return 'drift-spread-neutral'
  if (spread > 0) return 'drift-spread-positive'
  if (spread < 0) return 'drift-spread-negative'
  return 'drift-spread-neutral'
}

function WindowCard({ window: w }: { window: DriftWindow }) {
  const unavailable = w.trust === 'unavailable'
  return (
    <div className={`drift-window-card${unavailable ? ' drift-window-unavailable' : ''}`}>
      <p className="drift-window-label">{w.label}</p>
      {unavailable ? (
        <p className="drift-window-na">No data</p>
      ) : (
        <>
          <div className="drift-row">
            <span className="drift-row-label">Portfolio</span>
            <span className="drift-row-value">{formatReturn(w.portfolio_return_pct)}</span>
          </div>
          <div className="drift-row">
            <span className="drift-row-label">Benchmark</span>
            <span className="drift-row-value">{formatReturn(w.benchmark_return_pct)}</span>
          </div>
          <div className={`drift-row drift-alpha-row ${spreadTone(w.spread_pct)}`}>
            <span className="drift-row-label">Spread</span>
            <span className="drift-row-value">{formatReturn(w.spread_pct)}</span>
          </div>
        </>
      )}
    </div>
  )
}

type DriftBenchmarkPanelProps = {
  result: DriftResult | null
  benchmarkSymbol: string
  onBenchmarkChange: (symbol: string) => void
}

export function DriftBenchmarkPanel({ result, benchmarkSymbol, onBenchmarkChange }: DriftBenchmarkPanelProps) {
  const hasSeries = Boolean(result && result.daily_series.length > 0)

  return (
    <section className="drift-panel">
      <header className="drift-panel-header">
        <div className="drift-panel-title-block">
          <p className="panel-label">vs Market</p>
          <span
            className="attribution-trust-badge"
            title="Computed from current holdings applied to historical prices. Not verified broker return basis."
          >
            Synthetic
          </span>
        </div>
        <div className="drift-panel-controls">
          <label htmlFor="drift-benchmark" className="drift-benchmark-label field-label">Benchmark</label>
          <select
            id="drift-benchmark"
            className="path-input drift-benchmark-select"
            value={benchmarkSymbol}
            onChange={(e) => { onBenchmarkChange(e.target.value) }}
          >
            {BENCHMARK_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
        </div>
      </header>

      {result == null ? (
        <p className="helper">Import a portfolio to see drift vs benchmark.</p>
      ) : result.availability === 'unavailable' ? (
        <p className="helper">Market data unavailable — drift cannot be computed.</p>
      ) : (
        <>
          <div className="drift-windows-grid">
            {result.windows.map((w) => (
              <WindowCard key={w.label} window={w} />
            ))}
          </div>
          {hasSeries && (
            <IndexedReturnChart
              series={result.daily_series}
              windows={result.windows}
              benchmarkSymbol={benchmarkSymbol}
            />
          )}
        </>
      )}
    </section>
  )
}
