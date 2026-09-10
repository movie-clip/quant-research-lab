/**
 * RiskPanel — third top-level tab (Epic 13).
 *
 * Mirrors ExposurePanel's shell pattern (page header + .risk-shell-stack
 * flex-column wrapper of cards). v1 hosts a single card: StressScenariosCard.
 * Subsequent stories (US-13.2 Drawdown, US-13.3 VaR) add cards to this same
 * stack.
 *
 * Self-fetching: when `snapshot` is non-null, the panel fires
 * `runStressEngine(snapshot)` via useEffect and threads loading/error/data
 * into the card. No analytics math here — the engine owns it.
 */
import { useEffect, useState } from 'react'

import { runStressEngine } from './portfolioAnalysisAdapter'
import { AnnualizedVolatilityCard } from './AnnualizedVolatilityCard'
import { DrawdownAnalyticsCard } from './DrawdownAnalyticsCard'
import { StressScenariosCard } from './StressScenariosCard'
import { VarDistributionCard } from './VarDistributionCard'
import type { DiagnosticsEngineResponse, StressEngineResponse } from './types'
import type { PortfolioSnapshot } from './workspaceTypes'


export type RiskPanelProps = {
  snapshot: PortfolioSnapshot | null
  /** US-44.1: the already-fetched diagnostics response held in App state
   *  (`App.tsx`). Threaded in — not re-fetched — so the Risk tab can surface
   *  the publication-gated annualized volatility figure. `null` while the
   *  Dashboard's diagnostics fetch is still in flight. */
  diagnosticsAnalysis: DiagnosticsEngineResponse | null
}

type StressState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; error: Error }
  | { kind: 'done'; response: StressEngineResponse }

export function RiskPanel({ snapshot, diagnosticsAnalysis }: RiskPanelProps) {
  const [stress, setStress] = useState<StressState>({ kind: 'idle' })

  useEffect(() => {
    if (!snapshot) {
      setStress({ kind: 'idle' })
      return
    }
    let cancelled = false
    setStress({ kind: 'loading' })
    runStressEngine(snapshot)
      .then((response) => {
        if (!cancelled) setStress({ kind: 'done', response })
      })
      .catch((error: unknown) => {
        if (cancelled) return
        const err = error instanceof Error ? error : new Error(String(error))
        setStress({ kind: 'error', error: err })
      })
    return () => {
      cancelled = true
    }
  }, [snapshot])

  // When no snapshot is loaded yet, render a thin header + helper text — no
  // card. Matches the dashboard pre-import state.
  if (!snapshot) {
    return (
      <main className="exposure-shell">
        <header className="exposure-header">
          {/* Two-tier header (US-13.4): small `panel-label` eyebrow + plain h2
              subtitle. Mirrors ExposurePanel's pattern so the page header
              doesn't compete with the first card's title. */}
          <p className="panel-label">Risk</p>
          <h2>Stress, drawdown, and tail-risk views</h2>
          <p className="helper">Import a portfolio to see stress scenarios and other risk analytics.</p>
        </header>
      </main>
    )
  }

  const scenarios = stress.kind === 'done' ? stress.response.scenarios : []
  const trust = stress.kind === 'done' ? stress.response.trust : 'unavailable'
  const error = stress.kind === 'error' ? stress.error : null
  const loading = stress.kind === 'loading'

  return (
    <main className="exposure-shell">
      <header className="exposure-header">
        <p className="panel-label">Risk</p>
        <h2>Stress, drawdown, and tail-risk views</h2>
      </header>

      <div className="risk-shell-stack">
        <StressScenariosCard
          scenarios={scenarios}
          trust={trust}
          loading={loading}
          error={error}
          coverage={stress.kind === 'done' ? stress.response.coverage : null}
        />
        {/* DrawdownAnalyticsCard self-fetches via useEffect on [snapshot,
            selectedWindow]; RiskPanel does not own its state. */}
        <DrawdownAnalyticsCard snapshot={snapshot} />
        {/* VarDistributionCard (US-13.3) — same self-fetching pattern. */}
        <VarDistributionCard snapshot={snapshot} />
        {/* AnnualizedVolatilityCard (US-44.1) — prop-driven from the diagnostics
            response already in App state; no self-fetch. `null` prop = the
            diagnostics fetch is still in flight (card renders LoadingState). */}
        <AnnualizedVolatilityCard volatility={diagnosticsAnalysis?.risk_tab_volatility ?? null} />
      </div>
    </main>
  )
}
