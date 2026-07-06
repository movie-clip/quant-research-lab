import { coverageNote } from './coverageNote'
import { useEffect, useState } from 'react'
import type { BenchmarkStats, ImportedSnapshot, MultiBenchmarkCorrelationResult } from './types'
import { runMultiBenchmarkCorrelation } from './portfolioAnalysisAdapter'
import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'

// ── Formatters ────────────────────────────────────────────────────────────────

function formatValue(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2)
}

// Return a token-backed CSS color based on correlation sign and magnitude.
// 5-level palette defined in styles.css under :root --color-corr-*.
function correlationColor(value: number | null): string {
  if (value == null) return 'var(--color-text-disabled)'     // muted / unavailable
  if (value >= 0.7) return 'var(--color-corr-strong-positive)'
  if (value >= 0.3) return 'var(--color-corr-positive)'
  if (value > -0.3) return 'var(--color-corr-neutral)'
  if (value > -0.7) return 'var(--color-corr-negative)'
  return 'var(--color-corr-strong-negative)'
}

// Sign-encoded symbol for the same 5 magnitude bands (US-12.3 a11y: color
// is not the sole encoder). Unicode geometric shapes — render reliably
// across OS/themes; no emoji. `▲ U+25B2`, `▼ U+25BC`, `• U+2022`.
function correlationSymbol(value: number | null): string {
  if (value == null) return ''
  if (value >= 0.7) return '▲▲'
  if (value >= 0.3) return '▲'
  if (value > -0.3) return '•'
  if (value > -0.7) return '▼'
  return '▼▼'
}

// ── Row component ─────────────────────────────────────────────────────────────

function BenchmarkRow({ row }: { row: BenchmarkStats }) {
  const isUnavailable = row.trust === 'unavailable'
  const corrColor = correlationColor(row.correlation)

  // Standardised once: cell padding 8/12 (was 7/12), cell font from --font-body-sm,
  // unavailable text from --color-text-disabled. The 7px → 8px change rounds to
  // the spacing scale; visual delta is sub-pixel at typical row heights.
  const cellPadding = 'var(--space-sm) var(--space-md)'
  return (
    <tr
      style={{
        borderBottom: 'var(--border-thin) solid var(--color-border-subtle)',
        // Literal 0.55 not tokenized: React inline-style opacity is numeric;
        // JSDOM rejects var() values in numeric CSS props (returns NaN).
        // The token --opacity-unavailable still exists in styles.css for any
        // future CSS-class-based rendering.
        opacity: isUnavailable ? 0.55 : 1,
      }}
    >
      <td style={{ padding: cellPadding, color: 'var(--color-text-secondary)', fontWeight: 500, fontSize: 'var(--font-body-sm)' }}>
        <span style={{ marginRight: 'var(--space-xs)', color: 'var(--color-text-muted)', fontVariantNumeric: 'tabular-nums', fontSize: 'var(--font-chart-tick)' }}>
          {row.symbol}
        </span>
        {row.label}
      </td>
      <td
        style={{
          padding: cellPadding,
          color: isUnavailable ? 'var(--color-text-disabled)' : corrColor,
          fontWeight: 600,
          fontSize: 'var(--font-body-sm)',
          fontVariantNumeric: 'tabular-nums',
          textAlign: 'right',
        }}
      >
        {/* a11y: sign symbol prefix means color is not the sole encoder (US-12.3) */}
        {row.correlation == null
          ? formatValue(row.correlation)
          : `${correlationSymbol(row.correlation)} ${formatValue(row.correlation)}`}
      </td>
      <td
        style={{
          padding: cellPadding,
          color: isUnavailable ? 'var(--color-text-disabled)' : 'var(--color-text-muted)',
          fontSize: 'var(--font-body-sm)',
          fontVariantNumeric: 'tabular-nums',
          textAlign: 'right',
        }}
      >
        {formatValue(row.beta)}
      </td>
      <td
        style={{
          padding: cellPadding,
          color: isUnavailable ? 'var(--color-text-disabled)' : 'var(--color-text-muted)',
          fontSize: 'var(--font-body-sm)',
          fontVariantNumeric: 'tabular-nums',
          textAlign: 'right',
        }}
      >
        {formatValue(row.r_squared)}
      </td>
    </tr>
  )
}

// ── Table component ───────────────────────────────────────────────────────────

function CorrelationDataTable({ result }: { result: MultiBenchmarkCorrelationResult }) {
  return (
    <div style={{ overflowX: 'auto' }}>
      <table
        style={{ width: '100%', borderCollapse: 'collapse', fontSize: 'var(--font-body-sm)' }}
        aria-label="Multi-benchmark correlation statistics"
      >
        <thead>
          <tr style={{ borderBottom: 'var(--border-thin) solid var(--color-border-default)' }}>
            {(['Benchmark', 'ρ (Correlation)', 'β (Beta)', 'R²'] as const).map((col, i) => (
              <th
                key={col}
                style={{
                  padding: 'var(--space-sm) var(--space-md)',
                  textAlign: i === 0 ? 'left' : 'right',
                  fontSize: 'var(--font-chart-tick)',
                  color: 'var(--color-text-muted)',
                  fontWeight: 500,
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                }}
              >
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {result.benchmarks.map((row) => (
            <BenchmarkRow key={row.symbol} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Main component ────────────────────────────────────────────────────────────

type LoadState = 'idle' | 'loading' | 'error' | 'done'

type BenchmarkCorrelationTableProps = {
  snapshot: ImportedSnapshot | null
  /** When true, render only the inner content (lookback header + table or
   *  state primitive) without the outer <CardShell>. For composition inside
   *  a combined card shared with RollingCorrelationChart. Defaults to false. */
  noShell?: boolean
}

export function BenchmarkCorrelationTable({ snapshot, noShell = false }: BenchmarkCorrelationTableProps) {
  const [loadState, setLoadState] = useState<LoadState>('idle')
  const [result, setResult] = useState<MultiBenchmarkCorrelationResult | null>(null)
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

    runMultiBenchmarkCorrelation(snapshot)
      .then((data) => {
        if (!cancelled) {
          setResult(data)
          setLoadState('done')
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setErrorMsg(err instanceof Error ? err.message : 'Correlation engine failed')
          setLoadState('error')
        }
      })

    return () => {
      cancelled = true
    }
  }, [snapshot])

  const lookbackHeader = (
    <p className="helper" style={{ margin: 0 }}>
      {result ? `${result.lookback_days}d lookback` : '252d lookback'}
    </p>
  )

  const body = (
    <>
      {/* In noShell mode we still want to show the lookback context — render
          it inline above the table since the outer CardShell's actions slot
          is owned by the parent. */}
      {noShell && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--space-sm)' }}>
          {lookbackHeader}
        </div>
      )}
      {loadState === 'idle' && (
        <EmptyState
          title="Correlation unavailable"
          detail="Import a portfolio to compute multi-benchmark correlation."
        />
      )}

      {loadState === 'loading' && <LoadingState message="Computing correlation…" />}

      {loadState === 'error' && (
        <ErrorState title="Correlation unavailable" detail={errorMsg ?? 'Engine error'} />
      )}

      {loadState === 'done' && result && result.benchmarks.length > 0 && (
        <>
          <CorrelationDataTable result={result} />
          {coverageNote(result.coverage) ? (
            <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
              {coverageNote(result.coverage)}
            </p>
          ) : null}
        </>
      )}

      {loadState === 'done' && (!result || result.benchmarks.length === 0) && (
        <EmptyState
          title="Correlation unavailable"
          detail="Multi-benchmark correlation requires at least 20 overlapping trading days of synthetic portfolio history."
        />
      )}
    </>
  )

  if (noShell) return body

  return (
    <CardShell
      title="Multi-Benchmark Correlation"
      badge={
        <TrustBadge
          type="synthetic"
          tooltip="Computed from current holdings applied to historical prices. Not verified broker return basis."
        />
      }
      actions={lookbackHeader}
    >
      {body}
    </CardShell>
  )
}
