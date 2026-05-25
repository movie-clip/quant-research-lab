import type { DriftResult, DriftWindow } from './types'

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

function WindowCard({ window }: { window: DriftWindow }) {
  const unavailable = window.trust === 'unavailable'
  return (
    <div className={`drift-window-card ${unavailable ? 'drift-window-unavailable' : ''}`}>
      <p className="drift-window-label">{window.label}</p>
      {unavailable ? (
        <p className="drift-window-na">No data</p>
      ) : (
        <>
          <div className="drift-row">
            <span className="drift-row-label">Portfolio</span>
            <span className="drift-row-value">{formatReturn(window.portfolio_return_pct)}</span>
          </div>
          <div className="drift-row">
            <span className="drift-row-label">Benchmark</span>
            <span className="drift-row-value">{formatReturn(window.benchmark_return_pct)}</span>
          </div>
          <div className={`drift-row drift-alpha-row ${spreadTone(window.spread_pct)}`}>
            <span className="drift-row-label">Alpha</span>
            <span className="drift-row-value">{formatReturn(window.spread_pct)}</span>
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
  return (
    <section className="drift-panel panel">
      <header className="drift-panel-header">
        <p className="panel-label">vs Market</p>
        <div className="drift-panel-controls">
          <label htmlFor="drift-benchmark" className="drift-benchmark-label">Benchmark</label>
          <select
            id="drift-benchmark"
            className="drift-benchmark-select"
            value={benchmarkSymbol}
            onChange={(e) => { onBenchmarkChange(e.target.value) }}
          >
            {BENCHMARK_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>{opt.label}</option>
            ))}
          </select>
          <span className="drift-trust-badge">Synthetic</span>
        </div>
      </header>
      {result == null ? (
        <p className="helper">Import a portfolio to see drift vs benchmark.</p>
      ) : result.availability === 'unavailable' ? (
        <p className="helper">Market data unavailable — drift cannot be computed.</p>
      ) : (
        <div className="drift-windows-grid">
          {result.windows.map((w) => (
            <WindowCard key={w.label} window={w} />
          ))}
        </div>
      )}
    </section>
  )
}
