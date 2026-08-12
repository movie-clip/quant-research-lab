/**
 * CurrencyRiskCard (US-26.2) — how much of the portfolio's return volatility
 * came from currency moves rather than from the securities themselves.
 *
 * US-26.1's card shows composition (how much is foreign); this shows
 * consequence (whether that exposure did anything).
 *
 * Self-fetching (the project pattern): takes a snapshot, owns its request and
 * its idle/loading/error/done state. Presentation only — every share is
 * computed by the engine (guardrail #5).
 *
 * Carries a `Synthetic` badge, unlike the US-26.1 composition card: this
 * applies current holdings to historical prices.
 *
 * A share MAY BE NEGATIVE and is rendered as such. A currency leg moving
 * against the local leg genuinely reduces portfolio variance; clamping it to
 * zero would fabricate a floor the data does not support.
 */
import { useEffect, useState } from 'react'

import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'
import { WindowSelector } from '../../app/primitives/WindowSelector'
import { runCurrencyRiskEngine } from './portfolioAnalysisAdapter'
import type { CurrencyRiskResult, ImportedSnapshot } from './types'

type Status = 'idle' | 'loading' | 'error' | 'done'
const WINDOWS: Array<60 | 252> = [60, 252]

function pct(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${(value * 100).toFixed(1)}%`
}

function volPct(value: number | null | undefined): string {
  if (value == null) return '—'
  return `${value.toFixed(2)}%`
}

function num(value: number | null | undefined): string {
  if (value == null) return '—'
  return value.toFixed(2)
}

export type CurrencyRiskCardProps = {
  snapshot: ImportedSnapshot | null
}

export function CurrencyRiskCard({ snapshot }: CurrencyRiskCardProps) {
  const [status, setStatus] = useState<Status>('idle')
  const [result, setResult] = useState<CurrencyRiskResult | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [window, setWindow] = useState<60 | 252>(60)

  useEffect(() => {
    if (!snapshot) {
      setStatus('idle')
      setResult(null)
      return
    }
    let cancelled = false
    setStatus('loading')
    setError(null)
    runCurrencyRiskEngine(snapshot, window)
      .then((payload) => {
        if (cancelled) return
        setResult(payload)
        setStatus('done')
      })
      .catch((cause: unknown) => {
        if (cancelled) return
        setError(cause instanceof Error ? cause.message : 'Currency risk run failed')
        setStatus('error')
      })
    return () => {
      cancelled = true
    }
  }, [snapshot, window])

  const shares =
    result && result.trust === 'synthetic'
      ? [
          { key: 'local', label: 'Securities', value: result.local_variance_share },
          { key: 'currency', label: 'Currency', value: result.currency_variance_share },
          { key: 'interaction', label: 'Interaction', value: result.interaction_variance_share },
        ]
      : []

  const hasNegative = shares.some((s) => (s.value ?? 0) < 0)

  return (
    <CardShell
      title="Currency Risk Contribution"
      badge={<TrustBadge type={result && result.trust === 'synthetic' ? 'synthetic' : 'unavailable'} />}
      actions={
        <WindowSelector
          options={WINDOWS}
          value={window}
          onChange={setWindow}
          labelFn={(option) => `${option}d`}
        />
      }
    >
      {status === 'loading' ? <LoadingState message="Decomposing currency risk…" /> : null}
      {status === 'error' ? <ErrorState detail={error ?? 'Currency risk run failed'} /> : null}
      {status === 'idle' ? <EmptyState title="Currency risk unavailable" detail="Import a portfolio to see how much of your volatility came from currency." /> : null}

      {status === 'done' && result && result.trust !== 'synthetic' ? (
        <EmptyState
          title="Currency risk unavailable"
          detail={result.note ?? 'Needs at least 20 overlapping days of price and FX history.'}
        />
      ) : null}

      {status === 'done' && result && result.trust === 'synthetic' ? (
        <>
          <div className="sector-list">
            {shares.map((share) => (
              <div className="sector-list-row" key={share.key}>
                <span>{share.label}</span>
                <span>{pct(share.value)}</span>
              </div>
            ))}
          </div>

          <div className="sector-list" style={{ marginTop: 'var(--space-md)' }}>
            <div className="sector-list-row">
              <span>Currency vol (ann.)</span>
              <span>{volPct(result.currency_standalone_vol_pct)}</span>
            </div>
            <div className="sector-list-row">
              <span>Securities vol (ann.)</span>
              <span>{volPct(result.local_standalone_vol_pct)}</span>
            </div>
            <div className="sector-list-row">
              <span>Securities / FX correlation</span>
              <span>{num(result.local_fx_correlation)}</span>
            </div>
          </div>

          <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
            Shares of return variance over {result.observations} overlapping days; they sum to 100%.
          </p>

          {hasNegative ? (
            <p className="helper" style={{ margin: 'var(--space-sm) 0 0 0' }}>
              {/* Never clamped — a negative share is a real finding, not an error. */}
              A negative share means that leg moved <em>against</em> the rest of the portfolio over
              this window, reducing total variance rather than adding to it.
            </p>
          ) : null}

          {result.per_currency.length > 0 ? (
            <div className="sector-list" style={{ marginTop: 'var(--space-md)' }}>
              {result.per_currency.map((row) => (
                <div className="sector-list-row" key={row.currency}>
                  <span>
                    {row.currency} · {pct(row.base_weight)} of portfolio
                  </span>
                  <span>{pct(row.contribution)}</span>
                </div>
              ))}
            </div>
          ) : null}

          {result.excluded_symbols.length > 0 ? (
            <p className="helper" style={{ margin: 'var(--space-sm) 0 0 0' }}>
              {/* Excluded and named — never assigned to the local leg at zero FX. */}
              Excluded for want of price or FX history: {result.excluded_symbols.join(', ')} (
              {pct(result.excluded_weight)} of the portfolio). Their currency risk is not
              represented above.
            </p>
          ) : null}
        </>
      ) : null}
    </CardShell>
  )
}
