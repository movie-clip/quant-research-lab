/**
 * CacheControlCard — Exposure tab (Epic 20 / US-20.1).
 *
 * Shows the local market-data cache footprint (FMP + Yahoo) and a button to
 * clear it. Self-fetching: loads stats on mount; clearing re-fetches stats.
 */
import { useCallback, useEffect, useState } from 'react'

import type { CacheStats } from './types'
import { clearCache, getCacheStats } from './portfolioAnalysisAdapter'

import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'

type LoadState = 'loading' | 'ready' | 'error'

export function CacheControlCard() {
  const [loadState, setLoadState] = useState<LoadState>('loading')
  const [stats, setStats] = useState<CacheStats | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [clearing, setClearing] = useState(false)
  const [confirmation, setConfirmation] = useState<string | null>(null)

  const loadStats = useCallback(async () => {
    setLoadState('loading')
    setErrorMsg(null)
    try {
      setStats(await getCacheStats())
      setLoadState('ready')
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Cache stats failed')
      setLoadState('error')
    }
  }, [])

  useEffect(() => { void loadStats() }, [loadStats])

  const onClear = useCallback(async () => {
    setClearing(true)
    setConfirmation(null)
    setErrorMsg(null)
    try {
      const result = await clearCache(null)
      setConfirmation(`Removed ${result.removed} cached file${result.removed === 1 ? '' : 's'}.`)
      await loadStats()
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : 'Cache clear failed')
      setLoadState('error')
    } finally {
      setClearing(false)
    }
  }, [loadStats])

  const clearButton = (
    <button
      type="button"
      className="window-selector-btn"
      aria-label="Clear market-data cache"
      disabled={clearing || loadState === 'loading'}
      onClick={() => { void onClear() }}
      style={{
        padding: 'var(--space-xs) var(--space-sm)',
        fontSize: 'var(--font-caption)',
        borderRadius: 'var(--radius-sm)',
        border: 'var(--border-thin) solid var(--color-border-strong)',
        backgroundColor: 'transparent',
        color: 'var(--color-text-primary)',
        cursor: clearing ? 'default' : 'pointer',
      }}
    >
      {clearing ? 'Clearing…' : 'Clear cache'}
    </button>
  )

  return (
    <CardShell title="Market-data cache" actions={clearButton}>
      {loadState === 'loading' && <LoadingState message="Reading cache…" />}
      {loadState === 'error' && <ErrorState title="Cache unavailable" detail={errorMsg ?? 'Engine error'} />}

      {loadState === 'ready' && stats && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-sm)' }}>
          {stats.total_entries === 0 ? (
            <EmptyState title="Cache is empty." />
          ) : (
            <>
              <p style={{ margin: 0, fontSize: 'var(--font-body-sm)', color: 'var(--color-text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                {`${stats.total_entries} cached entr${stats.total_entries === 1 ? 'y' : 'ies'}`}
              </p>
              <p className="helper" style={{ margin: 0, fontVariantNumeric: 'tabular-nums' }}>
                {stats.namespaces.map((n) => `${n.namespace}: ${n.entries}`).join(' · ')}
              </p>
            </>
          )}
          {confirmation && (
            <p className="helper" style={{ margin: 0, color: 'var(--color-value-positive)' }}>{confirmation}</p>
          )}
          {!stats.enabled && (
            <p className="helper" style={{ margin: 0, color: 'var(--color-text-disabled)' }}>Caching is disabled in settings.</p>
          )}
        </div>
      )}
    </CardShell>
  )
}
