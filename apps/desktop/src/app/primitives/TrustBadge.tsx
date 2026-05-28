/**
 * Canonical trust-level badge for analytics surfaces.
 *
 * Renders a token-styled `<span className="attribution-trust-badge">` whose
 * label reflects the trust class. Used in the Exposure tab cards (drift,
 * rolling correlation, factor attribution, multi-benchmark correlation) to
 * make the synthetic-history boundary visible to the researcher.
 *
 * Style lives in apps/desktop/src/app/styles.css under `.attribution-trust-badge`
 * — uses tokens only. To extend with new types (`verified`, `degraded`,
 * `withheld`), update both the union here and add a label entry.
 */

type TrustType = 'synthetic' | 'unavailable'

const LABELS: Record<TrustType, string> = {
  synthetic: 'Synthetic',
  unavailable: 'Unavailable',
}

export type TrustBadgeProps = {
  type: TrustType
  tooltip?: string
}

export function TrustBadge({ type, tooltip }: TrustBadgeProps) {
  return (
    <span className="attribution-trust-badge" title={tooltip}>
      {LABELS[type]}
    </span>
  )
}
