import { useEffect, useState } from 'react'
import type { DriftResult, DriftWindow } from './types'
import type { PortfolioSnapshot } from './workspaceTypes'
import { runDriftEngine } from './portfolioAnalysisAdapter'
import { IndexedReturnChart } from './IndexedReturnChart'
import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'

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

type LoadState = 'idle' | 'loading' | 'error' | 'done'

type DriftBenchmarkPanelProps = {
  /** The workspace snapshot (carries US-30.2 fxRates). The panel self-fetches
   *  drift from it on mount and on benchmark change (US-30.3 / F-4) — no
   *  App-level result plumbing, so no analyze path can forget to fetch. */
  snapshot: PortfolioSnapshot | null
}

export function DriftBenchmarkPanel({ snapshot }: DriftBenchmarkPanelProps) {
  const [benchmarkSymbol, setBenchmarkSymbol] = useState('SPY')
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [result, setResult] = useState<DriftResult | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  useEffect(() => {
    if (!snapshot) {
      setResult(null)
      setLoadState('idle')
      return
    }

    let cancelled = false
    setLoadState('loading')
    setErrorMsg(null)

    runDriftEngine(snapshot, benchmarkSymbol)
      .then((driftResult) => {
        if (!cancelled) {
          setResult(driftResult)
          setLoadState('done')
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : 'Drift engine failed')
          setLoadState('error')
        }
      })

    return () => {
      cancelled = true
    }
  }, [snapshot, benchmarkSymbol])

  const hasSeries = Boolean(result && result.daily_series.length > 0)

  const benchmarkPicker = (
    <div className="drift-panel-controls">
      <label htmlFor="drift-benchmark" className="drift-benchmark-label field-label">Benchmark</label>
      <select
        id="drift-benchmark"
        className="path-input drift-benchmark-select"
        value={benchmarkSymbol}
        onChange={(e) => { setBenchmarkSymbol(e.target.value) }}
      >
        {BENCHMARK_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>{opt.label}</option>
        ))}
      </select>
    </div>
  )

  return (
    <CardShell
      title="vs Market"
      badge={
        <TrustBadge
          type="synthetic"
          tooltip={
            // US-30.1 (AC3): the tooltip repeats the engine's own basis note
            // (per-path truth) instead of a hardcoded claim; the fallback
            // (no window available yet) states the convention without
            // hand-rolling the badge label (design-system audit rule).
            (result?.windows.find((w) => w.note != null)?.note ??
              'Computed from current holdings × historical prices (market-value chain)') +
            '. Not verified broker return basis.'
          }
        />
      }
      actions={benchmarkPicker}
      className="drift-panel"
    >
      {loadState === 'error' ? (
        <ErrorState title="Drift engine failed" detail={errorMsg ?? 'Drift engine failed'} />
      ) : loadState === 'loading' ? (
        <LoadingState message="Computing drift vs benchmark…" />
      ) : result == null ? (
        <EmptyState title="No drift data" detail="Import a portfolio to see drift vs benchmark." />
      ) : result.availability === 'unavailable' ? (
        <EmptyState title="Drift unavailable" detail="Market data unavailable — drift cannot be computed." />
      ) : (
        <>
          <div className="drift-windows-grid">
            {result.windows.map((w) => (
              <WindowCard key={w.label} window={w} />
            ))}
          </div>
          {(result.fx_static_rate_currencies?.length ?? 0) > 0 ? (
            <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
              {/* US-30.2 (F-6): converted — but at ONE period-end rate, not a daily series. */}
              {result.fx_static_rate_currencies!.join(', ')} converted at the statement&apos;s
              implied period-end rate (static across the window) — levels are broker truth as of
              the statement date; FX return dynamics are not modeled.
            </p>
          ) : null}
          {(result.fx_fallback_currencies?.length ?? 0) > 0 ? (
            <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
              FX conversion unavailable for {result.fx_fallback_currencies!.join(', ')} — those
              positions are valued in their own currency (unconverted), so window returns and the
              chart are degraded for the non-USD sleeve.
            </p>
          ) : null}
          {(result.statement_anchored_symbols?.length ?? 0) > 0 ? (
            <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
              {/* US-30.2 (F-3): flat statement anchor — zero return contribution, disclosed. */}
              No market price history for {result.statement_anchored_symbols!.join(', ')} — valued
              flat at the statement close for the whole window (no return contribution), which
              dampens the portfolio line.
            </p>
          ) : null}
          {hasSeries && (
            <IndexedReturnChart
              series={result.daily_series}
              windows={result.windows}
              benchmarkSymbol={benchmarkSymbol}
            />
          )}
        </>
      )}
    </CardShell>
  )
}
