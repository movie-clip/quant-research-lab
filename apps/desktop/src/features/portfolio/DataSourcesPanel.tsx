/**
 * DataSourcesPanel — Exposure tab (Epic 18 / US-18.2).
 *
 * One portfolio-level indicator of market-data provenance: which holdings are
 * priced by the secondary provider (Yahoo Finance) vs the primary (FMP), and
 * which are unpriced. Source label only — NOT a return-basis trust claim (the
 * synthetic-history trust badges remain on the individual analytic cards).
 *
 * Self-fetching: takes a `snapshot` prop, fetches on mount/snapshot change.
 */
import { useEffect, useState } from 'react'

import type { ImportedSnapshot, ProvenanceResult } from './types'
import { runProvenanceEngine } from './portfolioAnalysisAdapter'

import { CardShell } from '../../app/primitives/CardShell'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'

type LoadState = 'idle' | 'loading' | 'error' | 'done'

function countLabel(n: number): string {
  return `${n} holding${n === 1 ? '' : 's'}`
}

export function DataSourcesPanel({ snapshot }: { snapshot: ImportedSnapshot | null }) {
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [result, setResult] = useState<ProvenanceResult | null>(null)
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
    runProvenanceEngine(snapshot)
      .then((data) => {
        if (!cancelled) {
          setResult(data)
          setLoadState('done')
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : 'Provenance engine failed')
          setLoadState('error')
        }
      })
    return () => { cancelled = true }
  }, [snapshot])

  // Nothing to show before a portfolio is loaded.
  if (loadState === 'idle') return null

  const yahoo = result?.yahoo_sourced_symbols ?? []
  const fmp = result?.fmp_symbols ?? []
  const unavailable = result?.unavailable_symbols ?? []
  const allFmp = loadState === 'done' && yahoo.length === 0 && unavailable.length === 0 && fmp.length > 0

  return (
    <CardShell title="Data sources">
      {loadState === 'loading' && <LoadingState message="Checking data sources…" />}
      {loadState === 'error' && <ErrorState title="Data sources unavailable" detail={errorMsg ?? 'Engine error'} />}

      {loadState === 'done' && result && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {allFmp && (
            <p className="helper" style={{ margin: 0 }}>
              {`All ${countLabel(fmp.length)} priced via FMP (primary).`}
            </p>
          )}

          {yahoo.length > 0 && (
            <p style={{ margin: 0, fontSize: 'var(--font-body-sm)', color: 'var(--color-text-primary)' }}>
              <span style={{ color: 'var(--color-text-secondary)' }}>◆ </span>
              {`${countLabel(yahoo.length)} via Yahoo Finance (secondary source): `}
              <span style={{ color: 'var(--color-text-secondary)', fontVariantNumeric: 'tabular-nums' }}>{yahoo.join(', ')}</span>
            </p>
          )}

          {yahoo.length > 0 && fmp.length > 0 && (
            <p className="helper" style={{ margin: 0 }}>
              {`${countLabel(fmp.length)} via FMP (primary).`}
            </p>
          )}

          {unavailable.length > 0 && (
            <p style={{ margin: 0, fontSize: 'var(--font-body-sm)', color: 'var(--color-text-disabled)' }}>
              {`${countLabel(unavailable.length)} with no price history: ${unavailable.join(', ')}`}
            </p>
          )}

          {(result.identity_warnings ?? []).map((w) => (
            <p
              key={`identity-${w.symbol}`}
              style={{ margin: 0, fontSize: 'var(--font-body-sm)', color: 'var(--color-value-negative)' }}
            >
              {`⚠ Possible identity mismatch: ${w.symbol} — statement says "${w.statement_description}", registry says "${w.registry_name}"`}
            </p>
          ))}
        </div>
      )}
    </CardShell>
  )
}
