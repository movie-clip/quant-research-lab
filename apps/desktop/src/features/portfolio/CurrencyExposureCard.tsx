/**
 * CurrencyExposureCard (US-26.1) — how much of the portfolio is denominated in
 * each currency, and how much is not in the base currency.
 *
 * `ImportedPosition.currency` has been imported on every statement since the
 * beginning and displayed nowhere: a researcher holding UCITS ETFs traded in
 * EUR/GBP could not see that exposure on any tab.
 *
 * Presentation only (guardrail #5): every weight is computed by the engine on
 * the base-currency-converted denominator the rest of the Exposure tab uses.
 * This component formats and explains.
 *
 * No TrustBadge: this is snapshot analytics over broker-truth composition, not
 * synthetic history — the same call US-30.6 made for the Concentration Pack.
 */
import { CardShell } from '../../app/primitives/CardShell'
import type { CurrencyExposureSummary } from './types'

function formatPct(weight: number): string {
  return `${(weight * 100).toFixed(2)}%`
}

function formatMoney(value: number, currency: string | null | undefined): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: currency || 'USD',
    maximumFractionDigits: 0,
  })
}

export type CurrencyExposureCardProps = {
  exposure?: CurrencyExposureSummary | null
  /** US-30.5a tiers, so the card can say which weights are degraded. */
  fxStaticRateCurrencies?: string[]
  fxFallbackCurrencies?: string[]
}

export function CurrencyExposureCard({
  exposure,
  fxStaticRateCurrencies = [],
  fxFallbackCurrencies = [],
}: CurrencyExposureCardProps) {
  if (!exposure || exposure.weights.length === 0) return null

  const base = exposure.base_currency ?? null
  const nonBase = exposure.non_base_weight

  return (
    <CardShell title="Currency Exposure">
      <div className="sector-list">
        {exposure.weights.map((row) => (
          <div className="sector-list-row" key={row.currency}>
            <span>
              {row.currency}
              {base && row.currency === base ? ' (base)' : ''}
            </span>
            <span>
              {formatMoney(row.market_value, base)} · {formatPct(row.weight)}
            </span>
          </div>
        ))}
      </div>

      <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
        {/* Null base currency: no baseline exists, so this is withheld rather
            than shown as 0 — which would read as "no currency risk". */}
        Not in {base ?? 'base currency'}:{' '}
        <strong>{nonBase == null ? '—' : formatPct(nonBase)}</strong>
        {nonBase == null
          ? ' — the statement carries no base currency, so there is no baseline to measure against.'
          : ''}
      </p>

      {fxStaticRateCurrencies.length > 0 ? (
        <p className="helper" style={{ margin: 'var(--space-sm) 0 0 0' }}>
          {fxStaticRateCurrencies.join(', ')} converted at the statement&apos;s implied period-end
          rate (static, not a daily series) — the weight is a point-in-time figure.
        </p>
      ) : null}

      {fxFallbackCurrencies.length > 0 ? (
        <p className="helper" style={{ margin: 'var(--space-sm) 0 0 0' }}>
          {/* Deliberately NOT a repeat of the tab-level FX note above: this one
              states what it means for THIS card's numbers specifically. */}
          {fxFallbackCurrencies.join(', ')} counted at unconverted values — those rows and the
          total above are the least reliable figures on this card.
        </p>
      ) : null}
    </CardShell>
  )
}
