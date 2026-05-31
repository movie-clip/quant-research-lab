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
import { StressScenariosCard } from './StressScenariosCard'
import type { StressEngineResponse } from './types'
import type { PortfolioSnapshot } from './workspaceTypes'


export type RiskPanelProps = {
  snapshot: PortfolioSnapshot | null
}

type StressState =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'error'; error: Error }
  | { kind: 'done'; response: StressEngineResponse }

export function RiskPanel({ snapshot }: RiskPanelProps) {
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
          <h2 className="panel-label">Risk</h2>
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
        <h2 className="panel-label">Risk Analytics</h2>
      </header>

      <div className="risk-shell-stack">
        <StressScenariosCard
          scenarios={scenarios}
          trust={trust}
          loading={loading}
          error={error}
        />
      </div>
    </main>
  )
}
