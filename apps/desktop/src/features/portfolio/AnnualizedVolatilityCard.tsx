/**
 * AnnualizedVolatilityCard — Risk tab card (US-44.1).
 *
 * Publication-gated view of the portfolio's annualized realized volatility.
 * The SAME scalar the Dashboard shows as
 * `volatility_summary.portfolio_volatility_pct`, but the Risk-tab surface only
 * publishes it once the portfolio has at least `minimum_observations` (60)
 * paired portfolio + benchmark daily returns. Below that the figure is
 * `withheld` (1..59 observations) or `unavailable` (0) — never a fabricated
 * zero, never the Dashboard's unfloored estimate passed through.
 *
 * Prop-driven, like StressScenariosCard: RiskPanel threads the already-fetched
 * `diagnosticsAnalysis.risk_tab_volatility`. No self-fetch, no window selector
 * (the figure uses the full available paired history). The server decides the
 * trust rung; this card only renders what arrives.
 *
 * Methodology: see §"Annualized realized volatility" in
 * financial-methodology.md — sample (N-1) standard deviation of daily returns,
 * annualized by √252. The 60-paired-observation publication floor is
 * `RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS`; the card reads the value off the
 * payload (`minimum_observations`) rather than mirroring the constant.
 */
import type { RiskTabAnnualizedVolatility } from './types'
import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'


export type AnnualizedVolatilityCardProps = {
  /** `risk_tab_volatility` off the diagnostics response. `null` = the
   *  diagnostics fetch is still in flight (a snapshot is loaded but App state
   *  has no diagnostics yet). */
  volatility: RiskTabAnnualizedVolatility | null
}

function formatPct(value: number | null): string {
  if (value == null) return '—'
  return `${value.toFixed(2)}%`
}

export function AnnualizedVolatilityCard({ volatility }: AnnualizedVolatilityCardProps) {
  if (volatility == null) {
    return (
      <CardShell title="Annualized Volatility">
        <LoadingState message="Computing annualized volatility…" />
      </CardShell>
    )
  }

  const { trust, annualized_volatility_pct, observations, minimum_observations } = volatility

  const badge =
    trust === 'synthetic' ? (
      <TrustBadge
        type="synthetic"
        tooltip="Computed from current holdings applied to historical prices. Sample (N-1) standard deviation of daily returns, annualized by √252."
      />
    ) : undefined

  return (
    <CardShell title="Annualized Volatility" badge={badge}>
      {trust === 'synthetic' ? (
        <>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'baseline',
              padding: 'var(--space-xs) 0',
            }}
          >
            <span style={{ fontSize: 'var(--font-body-sm)', color: 'var(--color-text-secondary)' }}>
              Portfolio volatility (annualized)
            </span>
            <span
              style={{
                fontSize: 'var(--font-heading-sm)',
                fontWeight: 600,
                fontVariantNumeric: 'tabular-nums',
                color: 'var(--color-text-primary)',
              }}
            >
              {formatPct(annualized_volatility_pct)}
            </span>
          </div>
          <p className="helper" style={{ margin: 'var(--space-sm) 0 0 0' }}>
            Sample (N-1) standard deviation of daily returns × √252, over {observations} paired
            portfolio and benchmark trading days. Published once at least {minimum_observations}{' '}
            paired trading days are available. See §"Annualized realized volatility" in the
            methodology.
          </p>
        </>
      ) : trust === 'withheld' ? (
        <EmptyState
          title="Annualized volatility withheld"
          detail={
            `${observations} of ${minimum_observations} paired portfolio and benchmark trading days available. ` +
            `An annualized volatility projected from fewer than ${minimum_observations} paired trading days is not published here. ` +
            `The Dashboard shows an unfloored estimate for the same portfolio.`
          }
        />
      ) : (
        <EmptyState
          title="Annualized volatility unavailable"
          detail="No paired portfolio and benchmark return history is available for this portfolio yet."
        />
      )}
    </CardShell>
  )
}
