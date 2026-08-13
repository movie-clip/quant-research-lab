/**
 * ReplayDisclosuresCard (US-24.11) — makes the imported ledger replay's own
 * degradations visible to the researcher.
 *
 * The engine has computed five disclosures on `DashboardHistoryRunMetadata`
 * since US-27.8 / US-31.2 / US-31.3 / US-24.10, but nothing rendered them, so
 * the Dashboard could present a performance chart, a TWR, monthly returns and a
 * max drawdown built on a `degraded` cash anchor with a withheld return day and
 * flat-anchored holdings — with no indication on screen. CLAUDE.md is explicit
 * that trust levels are rendered visibly and `withheld` is never silently
 * collapsed; this card is that rendering.
 *
 * Deliberately renders NO TrustBadge. The imported replay is broker truth that
 * has been degraded — not synthetic history — and `TrustBadge` only speaks
 * `Synthetic`/`Unavailable`, so using it here would assert a truth class that
 * does not apply (guardrail #2). The nuance lives in the prose instead.
 *
 * Presentation only (guardrail #5): every value shown is produced by the
 * engine; this component formats and explains, it never computes.
 */
import { CardShell } from '../../app/primitives/CardShell'
import type {
  DashboardHistoryRunMetadata,
  ReplayCashAnchor,
  ReplayQuantityWithholding,
} from './types'

const CASH_ANCHOR_BASIS_LABEL: Record<ReplayCashAnchor['basis'], string> = {
  // US-34.3: only shown when the anchor is NOT verified, so this label describes
  // an observed opening cash that the ledger nonetheless fails to reconcile.
  statement_starting_cash: "the statement's own reported starting cash",
  statement_nav_at_window_start: "the statement's starting NAV, dated at the replay window start",
  statement_nav_date_mismatch:
    "the statement's starting NAV, but dated BEFORE the replay window starts",
  snapshot_cash_balances: "the snapshot's own cash balances",
  unavailable: 'no trustworthy basis',
}

function formatUsd(value: number): string {
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 2,
  })
}

function CashAnchorNote({ anchor }: { anchor: ReplayCashAnchor }) {
  // US-31.3: a `verified` anchor needs no warning — only surface a degraded or
  // unavailable one, so the card never cries wolf on a clean run.
  const dateSpan =
    anchor.nav_as_of && anchor.window_start
      ? ` The NAV is as of ${anchor.nav_as_of} while the replay window starts ${anchor.window_start}, so market movement between those dates is absorbed into cash rather than measured.`
      : ''
  const residual =
    anchor.residual != null
      ? ` Measured residual against the statement-implied opening cash: ${formatUsd(anchor.residual)}.`
      : ''
  return (
    <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
      Opening cash is {anchor.trust === 'unavailable' ? 'unavailable' : 'degraded'} — derived from{' '}
      {CASH_ANCHOR_BASIS_LABEL[anchor.basis]}.{dateSpan}
      {residual} Every daily portfolio value carries this offset, so levels are affected while
      day-to-day returns are not.
    </p>
  )
}

function QuantityWithholdingNote({ withholdings }: { withholdings: ReplayQuantityWithholding[] }) {
  // US-33.2: the strongest disclosure on this card — the position is absent
  // from the replay entirely, so say what was dropped and on what evidence.
  // The evidence is the point: without the price range and ratio the researcher
  // cannot judge the call, and a withholding they cannot judge reads as a bug.
  return (
    <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
      Quantities withheld for{' '}
      {withholdings
        .map(
          (item) =>
            `${item.symbol} (traded between ${item.price_low.toLocaleString('en-US', {
              maximumFractionDigits: 3,
            })} and ${item.price_high.toLocaleString('en-US', {
              maximumFractionDigits: 2,
            })} ${item.currency} — a ${item.price_ratio.toLocaleString('en-US', {
              maximumFractionDigits: 1,
            })}× range)`,
        )
        .join('; ')}
      . A price range that wide means the broker's own quantities are denominated in more than one
      share unit — a split — so the reconstructed opening position cannot be trusted. It is left out
      of the replayed market value entirely rather than valued at a size that was never held. Cash
      movements from those trades are unaffected.
    </p>
  )
}

export type ReplayDisclosuresCardProps = {
  runMetadata?: DashboardHistoryRunMetadata | null
}

export function ReplayDisclosuresCard({ runMetadata }: ReplayDisclosuresCardProps) {
  if (!runMetadata) return null

  const fxFallback = runMetadata.fx_fallback_currencies ?? []
  const unpriced = runMetadata.unpriced_replay_symbols ?? []
  const tradeAnchored = runMetadata.trade_price_anchored_symbols ?? []
  const withheldDates = runMetadata.withheld_return_dates ?? []
  const quantityWithheld = runMetadata.quantity_withheld_symbols ?? []
  const anchor = runMetadata.replay_cash_anchor ?? null
  const anchorIsDegraded = anchor != null && anchor.trust !== 'verified'

  const hasAnything =
    fxFallback.length > 0 ||
    unpriced.length > 0 ||
    tradeAnchored.length > 0 ||
    withheldDates.length > 0 ||
    quantityWithheld.length > 0 ||
    anchorIsDegraded

  // A clean run renders nothing at all: an empty card, or worse an "all good"
  // banner, would be a reassurance the engine never made.
  if (!hasAnything) return null

  return (
    <CardShell title="Replay Disclosures">
      <p className="helper" style={{ margin: 0 }}>
        These affect the imported replay behind the performance surfaces on this tab.
      </p>

      {/* US-33.2 first: a withheld POSITION outranks a degraded valuation. */}
      {quantityWithheld.length > 0 ? (
        <QuantityWithholdingNote withholdings={quantityWithheld} />
      ) : null}

      {anchorIsDegraded && anchor ? <CashAnchorNote anchor={anchor} /> : null}

      {withheldDates.length > 0 ? (
        <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
          {/* US-31.3 (F-3): withheld, never collapsed into "unavailable". */}
          No return is published for {withheldDates.join(', ')} —{' '}
          {runMetadata.withheld_return_reason ??
            'the state was adjusted to match the statement, which is an accounting entry rather than a market move.'}{' '}
          The day is excluded from the return series and every statistic derived from it.
        </p>
      ) : null}

      {unpriced.length > 0 ? (
        <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
          {/* US-31.2 (F-1): the weakest tier — contributed 0, disclosed not hidden. */}
          No price of any kind for {unpriced.join(', ')} on days they were held — they contributed
          nothing to market value, so the replayed portfolio value is understated while they were
          in the book.
        </p>
      ) : null}

      {tradeAnchored.length > 0 ? (
        <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
          {/* US-24.10: broker truth, but a flat segment between trades. */}
          No market price history for {tradeAnchored.join(', ')} — valued at the broker&apos;s own
          trade price, carried flat until the next trade, so they show no market movement between
          trades.
        </p>
      ) : null}

      {fxFallback.length > 0 ? (
        <p className="helper" style={{ margin: 'var(--space-md) 0 0 0' }}>
          {/* US-27.8 (F9): carried unconverted, never a silent 1:1 claim. */}
          No FX rate available for {fxFallback.join(', ')} — those values are carried in their own
          currency rather than converted, so the non-base sleeve is degraded.
        </p>
      ) : null}
    </CardShell>
  )
}
