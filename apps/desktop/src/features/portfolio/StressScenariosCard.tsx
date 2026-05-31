/**
 * StressScenariosCard — Risk tab, point-in-time card showing projected
 * portfolio impact for each predefined stress scenario.
 *
 * Methodology: see §Stress Scenarios in financial-methodology.md —
 *   estimated_scenario_return = sum(current_factor_loading_i * shock_i)
 *
 * Trust: synthetic (uses current factor loadings). When the engine cannot
 * fit the factor model (insufficient history), `trust='unavailable'` is
 * surfaced via EmptyState — never zeros.
 *
 * No window selector (point-in-time analytic).
 */
import type { StressScenarioResult, StressTrustLevel } from './types'
import { CardShell } from '../../app/primitives/CardShell'
import { EmptyState } from '../../app/primitives/EmptyState'
import { ErrorState } from '../../app/primitives/ErrorState'
import { LoadingState } from '../../app/primitives/LoadingState'
import { TrustBadge } from '../../app/primitives/TrustBadge'


export type StressScenariosCardProps = {
  scenarios: StressScenarioResult[]
  trust: StressTrustLevel
  loading?: boolean
  error?: Error | null
}

function pctColor(pct: number | null): string {
  if (pct == null) return 'var(--color-text-muted)'
  if (pct > 0) return 'var(--color-value-positive)'
  if (pct < 0) return 'var(--color-value-negative)'
  return 'var(--color-text-muted)'
}

function formatPct(pct: number | null): string {
  if (pct == null) return '—'
  const sign = pct > 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

/** Sort by |pct| descending. Null pcts sort last (treated as -Infinity). */
function sortByAbsMagnitudeDesc(scenarios: StressScenarioResult[]): StressScenarioResult[] {
  return [...scenarios].sort((a, b) => {
    const magA = a.estimated_return_pct == null ? -Infinity : Math.abs(a.estimated_return_pct)
    const magB = b.estimated_return_pct == null ? -Infinity : Math.abs(b.estimated_return_pct)
    return magB - magA
  })
}

function ScenarioRow({ scenario, maxAbsPct }: { scenario: StressScenarioResult; maxAbsPct: number }) {
  const pct = scenario.estimated_return_pct
  const color = pctColor(pct)
  // Width: relative to max abs pct across the scenario set. Null → 0 (bar
  // is rendered but invisible, preserving row alignment).
  const widthPct = pct == null || maxAbsPct === 0 ? 0 : (Math.abs(pct) / maxAbsPct) * 100

  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: '1fr auto',
        gap: 'var(--space-md)',
        padding: 'var(--space-md) 0',
        borderBottom: 'var(--border-thin) solid var(--color-border-subtle)',
        alignItems: 'baseline',
      }}
    >
      <div>
        <p
          style={{
            margin: 0,
            fontWeight: 600,
            fontSize: 'var(--font-body-sm)',
            color: 'var(--color-text-primary)',
          }}
        >
          {scenario.name}
        </p>
        <p className="helper" style={{ margin: 'var(--space-xs) 0 0 0' }}>
          {scenario.description}
        </p>
        {/* Magnitude bar — color matches the number; width proportional to |pct| */}
        <div
          aria-hidden="true"
          style={{
            marginTop: 'var(--space-sm)',
            height: 'var(--space-xs)',
            background: 'var(--color-border-subtle)',
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${widthPct}%`,
              height: '100%',
              background: color,
              transition: 'width 200ms ease',
            }}
          />
        </div>
      </div>
      <p
        style={{
          margin: 0,
          fontSize: 'var(--font-section-title)',
          fontWeight: 600,
          fontVariantNumeric: 'tabular-nums',
          color,
          textAlign: 'right',
          whiteSpace: 'nowrap',
        }}
      >
        {formatPct(pct)}
      </p>
    </div>
  )
}

export function StressScenariosCard({ scenarios, trust, loading, error }: StressScenariosCardProps) {
  const sorted = sortByAbsMagnitudeDesc(scenarios)
  const maxAbsPct = sorted.reduce((acc, s) => {
    if (s.estimated_return_pct == null) return acc
    return Math.max(acc, Math.abs(s.estimated_return_pct))
  }, 0)

  return (
    <CardShell
      title="Stress Scenarios"
      badge={
        <TrustBadge
          type={trust}
          tooltip="Computed from current factor loadings × hypothetical shock vector. Sensitive to factor stability."
        />
      }
    >
      {loading ? (
        <LoadingState message="Computing stress scenarios…" />
      ) : error ? (
        <ErrorState title="Stress engine failed" detail={error.message} />
      ) : trust === 'unavailable' ? (
        <EmptyState
          title="Stress scenarios unavailable"
          detail="The factor model has insufficient history. Try after the portfolio has at least 252 days of returns."
        />
      ) : (
        <div>
          {sorted.map((scenario) => (
            <ScenarioRow key={scenario.name} scenario={scenario} maxAbsPct={maxAbsPct} />
          ))}
        </div>
      )}
    </CardShell>
  )
}
