import type { DiagnosticsEngineResponse } from './types'
import { EmptyState } from '../../app/primitives/EmptyState'

function formatPct(value: number | null | undefined): string {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatRatio(value: number | null | undefined): string {
  return value == null ? 'n/a' : value.toFixed(3)
}

/** `top_*_risk_share` fields are 0-1 fractions (see `_sum_top_risk_shares` in
 *  `analytics/risk.py`), unlike the `*_pct` volatility/drawdown fields which
 *  are already percentage-scaled. Multiply by 100 here, not in the backend. */
function formatShareAsPct(value: number | null | undefined): string {
  return value == null ? 'n/a' : `${(value * 100).toFixed(2)}%`
}

/** Distinct vocabulary from the Exposure-tab `TrustBadge` (synthetic/unavailable) —
 *  diagnostics reports its own per-section verification ladder. */
function sectionTrustLabel(trust: string | undefined): string {
  switch (trust) {
    case 'verified_adjusted_close':
      return 'Verified'
    case 'degraded_unverified_return_basis':
      return 'Degraded'
    default:
      return 'Unavailable'
  }
}

type RiskSummaryCardProps = {
  diagnosticsAnalysis: DiagnosticsEngineResponse | null
}

export function RiskSummaryCard({ diagnosticsAnalysis }: RiskSummaryCardProps) {
  const unavailable =
    !diagnosticsAnalysis
    || diagnosticsAnalysis.availability?.historical_sections_available === false
    || !diagnosticsAnalysis.volatility_summary
    || !diagnosticsAnalysis.drawdown_summary
    || !diagnosticsAnalysis.risk_concentration_summary

  if (unavailable) {
    return (
      <section className="summary-card risk-summary-card" aria-label="Risk Summary">
        <p className="panel-label">Risk Summary</p>
        <EmptyState
          title="Risk metrics unavailable"
          detail="Import a portfolio with usable history to see volatility, drawdown, and concentration."
        />
      </section>
    )
  }

  const { volatility_summary: vol, drawdown_summary: dd, risk_concentration_summary: conc, relative_risk: rel } = diagnosticsAnalysis
  const trust = sectionTrustLabel(diagnosticsAnalysis.run_metadata?.section_trust?.risk_contribution_path)
  // Information Ratio / Active Return are mathematically dependent on tracking
  // error (US-25.5 AC4) — only show them when tracking error itself is present,
  // rather than rendering a coherence-breaking "n/a beside a real number" pair.
  const showRelativeRisk = vol.tracking_error_pct != null

  return (
    <section className="summary-card risk-summary-card" aria-label="Risk Summary">
      <div className="benchmark-card-header">
        <p className="panel-label">Risk Summary</p>
      </div>
      <p className="helper" style={{ marginTop: 'var(--space-xs)' }}>Risk contribution basis: {trust}</p>

      <div className="benchmark-card-summary">
        <div className="benchmark-card-metric">
          <span className="stat-label">Portfolio Volatility</span>
          <span className="benchmark-card-value">{formatPct(vol.portfolio_volatility_pct)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Tracking Error</span>
          <span className="benchmark-card-value">{formatPct(vol.tracking_error_pct)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Downside Volatility</span>
          <span className="benchmark-card-value">{formatPct(vol.downside_volatility_pct)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Benchmark Volatility</span>
          <span className="benchmark-card-value">{formatPct(vol.benchmark_volatility_pct)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Current Drawdown</span>
          <span className="benchmark-card-value">{formatPct(dd.current_drawdown_pct)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Max Drawdown</span>
          <span className="benchmark-card-value">{formatPct(dd.max_drawdown_pct)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Factor HHI</span>
          <span className="benchmark-card-value">{formatRatio(conc.factor_hhi)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Position HHI</span>
          <span className="benchmark-card-value">{formatRatio(conc.position_hhi)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Top-1 Factor Risk Share</span>
          <span className="benchmark-card-value">{formatShareAsPct(conc.top_1_factor_risk_share)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Top-3 Factor Risk Share</span>
          <span className="benchmark-card-value">{formatShareAsPct(conc.top_3_factor_risk_share)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Top-1 Position Risk Share</span>
          <span className="benchmark-card-value">{formatShareAsPct(conc.top_1_position_risk_share)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Top-5 Position Risk Share</span>
          <span className="benchmark-card-value">{formatShareAsPct(conc.top_5_position_risk_share)}</span>
        </div>
        {showRelativeRisk && (
          <>
            <div className="benchmark-card-metric">
              <span className="stat-label">Information Ratio</span>
              <span className="benchmark-card-value">{formatRatio(rel.information_ratio)}</span>
            </div>
            <div className="benchmark-card-metric">
              <span className="stat-label">Active Return (vs benchmark)</span>
              <span className="benchmark-card-value">{formatPct(rel.active_return_pct)}</span>
            </div>
          </>
        )}
      </div>
    </section>
  )
}
