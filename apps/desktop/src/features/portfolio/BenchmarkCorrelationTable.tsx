import { useEffect, useState } from 'react'
import type { BenchmarkStats, ImportedSnapshot, MultiBenchmarkCorrelationResult } from './types'
import { runMultiBenchmarkCorrelation } from './portfolioAnalysisAdapter'

// ── Formatters ────────────────────────────────────────────────────────────────

function formatValue(value: number | null | undefined): string {
  return value == null ? '—' : value.toFixed(2)
}

// Return a CSS color based on correlation sign and magnitude.
function correlationColor(value: number | null): string {
  if (value == null) return '#6b7280'          // muted / unavailable
  if (value >= 0.7) return '#3cb79f'           // strong positive → teal
  if (value >= 0.3) return '#6ec98f'           // moderate positive → soft green
  if (value > -0.3) return '#94a3b8'           // near-zero → neutral
  if (value > -0.7) return '#e08f5a'           // moderate negative → orange
  return '#e06a5a'                             // strong negative → red
}

// ── Row component ─────────────────────────────────────────────────────────────

function BenchmarkRow({ row }: { row: BenchmarkStats }) {
  const isUnavailable = row.trust === 'unavailable'
  const corrColor = correlationColor(row.correlation)

  return (
    <tr
      style={{
        borderBottom: '1px solid rgba(255,255,255,0.06)',
        opacity: isUnavailable ? 0.55 : 1,
      }}
    >
      <td style={{ padding: '7px 12px', color: '#cbd5e1', fontWeight: 500, fontSize: 13 }}>
        <span style={{ marginRight: 6, color: '#94a3b8', fontVariantNumeric: 'tabular-nums', fontSize: 11 }}>
          {row.symbol}
        </span>
        {row.label}
      </td>
      <td
        style={{
          padding: '7px 12px',
          color: isUnavailable ? '#6b7280' : corrColor,
          fontWeight: 600,
          fontSize: 13,
          fontVariantNumeric: 'tabular-nums',
          textAlign: 'right',
        }}
      >
        {formatValue(row.correlation)}
      </td>
      <td
        style={{
          padding: '7px 12px',
          color: isUnavailable ? '#6b7280' : '#94a3b8',
          fontSize: 13,
          fontVariantNumeric: 'tabular-nums',
          textAlign: 'right',
        }}
      >
        {formatValue(row.beta)}
      </td>
      <td
        style={{
          padding: '7px 12px',
          color: isUnavailable ? '#6b7280' : '#94a3b8',
          fontSize: 13,
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
        style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}
        aria-label="Multi-benchmark correlation statistics"
      >
        <thead>
          <tr style={{ borderBottom: '1px solid rgba(255,255,255,0.12)' }}>
            {(['Benchmark', 'ρ (Correlation)', 'β (Beta)', 'R²'] as const).map((col, i) => (
              <th
                key={col}
                style={{
                  padding: '6px 12px',
                  textAlign: i === 0 ? 'left' : 'right',
                  fontSize: 11,
                  color: '#94a3b8',
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
}

export function BenchmarkCorrelationTable({ snapshot }: BenchmarkCorrelationTableProps) {
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

  return (
    <section className="compact-chart-panel">
      {/* Header */}
      <div
        className="section-header-inline sector-list-header exposure-section-header"
        style={{ marginBottom: 12 }}
      >
        <div className="panel-section-title-block">
          <p className="panel-label" style={{ display: 'inline' }}>
            Multi-Benchmark Correlation
          </p>
          <span
            className="attribution-trust-badge"
            title="Computed from current holdings applied to historical prices. Not verified broker return basis."
            style={{ marginLeft: 8 }}
          >
            Synthetic
          </span>
        </div>
        <p className="helper" style={{ margin: 0 }}>
          {result ? `${result.lookback_days}d lookback` : '252d lookback'}
        </p>
      </div>

      {/* States */}
      {loadState === 'idle' && (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Correlation unavailable</p>
          <p className="helper">Import a portfolio to compute multi-benchmark correlation.</p>
        </div>
      )}

      {loadState === 'loading' && (
        <p className="helper" style={{ textAlign: 'center', padding: '24px 0' }}>
          Computing correlation…
        </p>
      )}

      {loadState === 'error' && (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Correlation unavailable</p>
          <p className="helper">{errorMsg ?? 'Engine error'}</p>
        </div>
      )}

      {loadState === 'done' && result && result.benchmarks.length > 0 && (
        <CorrelationDataTable result={result} />
      )}

      {loadState === 'done' && (!result || result.benchmarks.length === 0) && (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Correlation unavailable</p>
          <p className="helper">
            Multi-benchmark correlation requires at least 20 overlapping trading days of
            synthetic portfolio history.
          </p>
        </div>
      )}
    </section>
  )
}
