/**
 * IntraCorrelationHeatmap — Exposure tab (Epic 17 / US-17.1).
 *
 * Holdings × holdings pairwise Pearson correlation heatmap over a selectable
 * lookback window, plus a diversification summary (average pairwise correlation,
 * most/least-correlated pair). Answers "what is actually diversifying me?".
 *
 * Methodology: see §Intra-Portfolio Correlation in financial-methodology.md.
 * Trust: synthetic (current holdings × historical prices) — never verified.
 *
 * Self-fetching: takes a `snapshot` prop, fetches on [snapshot, window].
 *
 * Accessibility (Epic 12 baseline): every cell prints the numeric ρ + a sign
 * glyph (▲▲/▲/•/▼/▼▼) so color (the --color-corr-* palette) is never the sole
 * encoder. The diagonal is muted; sub-threshold pairs render "n/a", never 0.
 */
import { useEffect, useState } from 'react'

import type { ImportedSnapshot, IntraCorrelationResult } from './types'
import { runIntraCorrelationEngine } from './portfolioAnalysisAdapter'

import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'
import { WindowSelector } from '../../app/primitives/WindowSelector'

type CorrWindow = 20 | 60 | 252
const WINDOW_OPTIONS: CorrWindow[] = [20, 60, 252]
type LoadState = 'idle' | 'loading' | 'error' | 'done'

const SYNTHETIC_TOOLTIP =
  'Pairwise correlations are computed from current holdings applied to historical prices. Not verified broker return basis.'

/** 5-level palette background by correlation sign/magnitude (tokens in styles.css). */
function correlationColor(value: number | null): string {
  if (value == null) return 'var(--color-border-subtle)'
  if (value >= 0.7) return 'var(--color-corr-strong-positive)'
  if (value >= 0.3) return 'var(--color-corr-positive)'
  if (value > -0.3) return 'var(--color-corr-neutral)'
  if (value > -0.7) return 'var(--color-corr-negative)'
  return 'var(--color-corr-strong-negative)'
}

/** Sign glyph for the same 5 bands — color is not the sole encoder (a11y). */
function correlationSymbol(value: number | null): string {
  if (value == null) return ''
  if (value >= 0.7) return '▲▲'
  if (value >= 0.3) return '▲'
  if (value > -0.3) return '•'
  if (value > -0.7) return '▼'
  return '▼▼'
}

function formatRho(value: number | null): string {
  return value == null ? '—' : value.toFixed(2)
}

function HeatmapGrid({ result }: { result: IntraCorrelationResult }) {
  const { symbols, matrix } = result
  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{ borderCollapse: 'collapse', fontSize: 'var(--font-chart-tick)', fontVariantNumeric: 'tabular-nums' }}
        aria-label="Holdings pairwise correlation heatmap"
      >
        <thead>
          <tr>
            <th style={{ padding: 'var(--space-xs)' }} aria-label="Holding" />
            {symbols.map((sym) => (
              <th
                key={`col-${sym}`}
                scope="col"
                style={{ padding: 'var(--space-xs) var(--space-sm)', color: 'var(--color-text-muted)', fontWeight: 500, textAlign: 'center' }}
              >
                {sym}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {symbols.map((rowSym, i) => (
            <tr key={`row-${rowSym}`}>
              <th
                scope="row"
                style={{ padding: 'var(--space-xs) var(--space-sm)', color: 'var(--color-text-secondary)', fontWeight: 500, textAlign: 'right', whiteSpace: 'nowrap' }}
              >
                {rowSym}
              </th>
              {symbols.map((colSym, j) => {
                const isDiagonal = i === j
                const value = matrix[i]?.[j] ?? null
                const isNull = !isDiagonal && value == null

                const background = isDiagonal
                  ? 'var(--color-surface-overlay)'
                  : isNull
                    ? 'var(--color-border-subtle)'
                    : correlationColor(value)
                const color = isDiagonal || isNull
                  ? 'var(--color-text-disabled)'
                  : 'var(--color-text-on-accent)'

                const label = isDiagonal
                  ? '1.00'
                  : isNull
                    ? 'n/a'
                    : `${correlationSymbol(value)} ${formatRho(value)}`

                return (
                  <td
                    key={`cell-${rowSym}-${colSym}`}
                    title={`${rowSym} · ${colSym}: ${isNull ? 'unavailable (insufficient overlapping history)' : formatRho(isDiagonal ? 1.0 : value)}`}
                    style={{
                      padding: 'var(--space-xs) var(--space-sm)',
                      textAlign: 'center',
                      whiteSpace: 'nowrap',
                      background,
                      color,
                      border: 'var(--border-thin) solid var(--color-surface-panel)',
                      fontWeight: 600,
                    }}
                  >
                    {label}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SummaryStrip({ result }: { result: IntraCorrelationResult }) {
  const avg = result.average_pairwise_correlation
  const most = result.most_correlated_pair
  const least = result.least_correlated_pair

  const pairLabel = (pair: typeof most): string =>
    pair == null ? 'Unavailable' : `${pair.symbol_a} · ${pair.symbol_b}  ${formatRho(pair.correlation)}`

  const dr = result.diversification_ratio
  const enb = result.effective_number_of_bets

  const items: Array<{ label: string; value: string }> = [
    { label: 'Avg pairwise ρ', value: avg == null ? 'Unavailable' : formatRho(avg) },
    { label: 'Diversification Ratio', value: dr == null ? 'Unavailable' : dr.toFixed(2) },
    { label: 'Effective number of bets', value: enb == null ? 'Unavailable' : enb.toFixed(1) },
    { label: 'Most correlated', value: pairLabel(most) },
    { label: 'Least correlated', value: pairLabel(least) },
  ]

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-xl)', marginBottom: 'var(--space-md)' }}>
      {items.map((item) => (
        <div key={item.label}>
          <p className="helper" style={{ margin: 0 }}>{item.label}</p>
          <p style={{ margin: 'var(--space-xxs) 0 0 0', fontSize: 'var(--font-body-sm)', fontWeight: 600, color: 'var(--color-text-primary)', fontVariantNumeric: 'tabular-nums' }}>
            {item.value}
          </p>
        </div>
      ))}
    </div>
  )
}

export function IntraCorrelationHeatmap({ snapshot }: { snapshot: ImportedSnapshot | null }) {
  const [window, setWindow] = useState<CorrWindow>(60)
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [result, setResult] = useState<IntraCorrelationResult | null>(null)
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
    runIntraCorrelationEngine(snapshot, window)
      .then((data) => {
        if (!cancelled) {
          setResult(data)
          setLoadState('done')
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : 'Intra-correlation engine failed')
          setLoadState('error')
        }
      })
    return () => { cancelled = true }
  }, [snapshot, window])

  const hasMatrix = loadState === 'done' && result != null && result.trust !== 'unavailable' && result.symbols.length >= 2

  return (
    <CardShell
      title="Intra-Portfolio Correlation"
      badge={<TrustBadge type="synthetic" tooltip={SYNTHETIC_TOOLTIP} />}
      actions={
        <WindowSelector<CorrWindow>
          options={WINDOW_OPTIONS}
          value={window}
          onChange={setWindow}
          labelFn={(w) => `${w}d`}
        />
      }
    >
      {loadState === 'idle' && <EmptyState title="Import a portfolio to view holding correlations." />}
      {loadState === 'loading' && <LoadingState message="Computing correlations…" />}
      {loadState === 'error' && <ErrorState title="Correlation unavailable" detail={errorMsg ?? 'Engine error'} />}

      {loadState === 'done' && !hasMatrix && (
        <EmptyState
          title="Not enough priceable holdings for a correlation matrix."
          detail="Needs at least 2 holdings with sufficient overlapping price history."
        />
      )}

      {hasMatrix && result && (
        <div>
          <SummaryStrip result={result} />
          <HeatmapGrid result={result} />
          {result.excluded_symbols.length > 0 && (
            <p className="helper" style={{ margin: 'var(--space-sm) 0 0 0' }}>
              {`${result.excluded_symbols.length} holding${result.excluded_symbols.length === 1 ? '' : 's'} excluded: insufficient history (${result.excluded_symbols.join(', ')})`}
            </p>
          )}
        </div>
      )}
    </CardShell>
  )
}
