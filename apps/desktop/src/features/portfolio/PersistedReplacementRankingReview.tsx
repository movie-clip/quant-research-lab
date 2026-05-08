import type {
  IntentBoundEtfReplacementRankingArtifact,
  IntentBoundEtfReplacementRankingSupportedOpenResponse,
  IntentBoundEtfReplacementRankingSupportedPreflightResponse,
} from './types'

function formatReviewValue(value: string | number | null | undefined) {
  if (value == null) return 'n/a'
  if (typeof value === 'string') return value.trim() ? value : 'n/a'
  return String(value)
}

function formatCompositeScore(value: number | null | undefined) {
  return value == null ? 'n/a' : value.toFixed(4)
}

function reviewStatus(artifact: IntentBoundEtfReplacementRankingArtifact) {
  if (artifact.status === 'unavailable' || artifact.run_metadata.confidence === 'low') return 'degraded'
  if (artifact.warnings.length || artifact.excluded_count > 0) return 'warning'
  return 'ok'
}

function eligibleCandidates(artifact: IntentBoundEtfReplacementRankingArtifact) {
  return [...artifact.ranked_candidates]
    .filter((candidate) => candidate.eligibility_status === 'eligible')
    .sort((left, right) => {
      if (left.rank == null && right.rank == null) return left.symbol.localeCompare(right.symbol)
      if (left.rank == null) return 1
      if (right.rank == null) return -1
      return left.rank - right.rank
    })
}

type Props = {
  preflight: IntentBoundEtfReplacementRankingSupportedPreflightResponse
  openResponse: IntentBoundEtfReplacementRankingSupportedOpenResponse
}

export function PersistedReplacementRankingReview({ preflight, openResponse }: Props) {
  const artifact = openResponse.review_payload.artifact
  const status = reviewStatus(artifact)
  const eligible = eligibleCandidates(artifact)
  const topCandidate = eligible[0] ?? null
  const runnerUpCandidate = eligible[1] ?? null
  const selectedCandidate = artifact.ranked_candidates.find((candidate) => candidate.symbol === artifact.lineage.candidate_symbol) ?? null

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Saved Replacement Ranking Review</p></div>
        <p className="helper">Authoritative persisted ranking artifact reopened read-only for selection review only. This does not create intent, mutate the workspace, or launch replay.</p>
      </div>
      <div className="tab-bar" style={{ justifyContent: 'flex-start', margin: '0 0 8px' }}>
        <span className="backtest-source-badge">Truth: {openResponse.review_payload.review_truth_basis}</span>
        <span className="backtest-source-badge">Scope: {openResponse.review_payload.review_scope}</span>
        <span className="backtest-source-badge">Source: persisted artifact</span>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Incumbent</p><p className="summary-value">{formatReviewValue(artifact.lineage.base_symbol)}</p><p className="helper">Explicit incumbent carried in the persisted replacement lineage.</p></div>
        <div className="summary-card"><p className="stat-label">Chosen Candidate</p><p className="summary-value">{formatReviewValue(artifact.lineage.candidate_symbol)}</p><p className="helper">Explicit ETF choice recovered from the persisted replacement artifact.</p></div>
        <div className="summary-card"><p className="stat-label">Selected Rank</p><p className="summary-value">{formatReviewValue(selectedCandidate?.rank ?? openResponse.consumer_handoff.selected_candidate.rank)}</p><p className="helper">Rank position saved for the explicit candidate choice.</p></div>
        <div className="summary-card"><p className="stat-label">Total Score</p><p className="summary-value">{formatCompositeScore(selectedCandidate?.composite_score ?? openResponse.consumer_handoff.selected_candidate.composite_score)}</p><p className="helper">Deterministic composite score recovered from the persisted ranking artifact.</p></div>
        <div className="summary-card"><p className="stat-label">Highest-Ranked Eligible</p><p className="summary-value">{formatReviewValue(topCandidate?.symbol)}</p><p className="helper">Top eligible candidate from the same persisted backend run.</p></div>
        <div className="summary-card"><p className="stat-label">Next Eligible</p><p className="summary-value">{formatReviewValue(runnerUpCandidate?.symbol)}</p><p className="helper">Next eligible candidate retained for read-only comparison context.</p></div>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Ranking Status</p><p className="summary-value">{status}</p><p className="helper">{status === 'degraded' ? 'Persisted ranking context is available but degraded. Treat this as review context only.' : status === 'warning' ? 'Persisted ranking completed with warnings or exclusions. Review the saved details before any later handoff.' : 'Persisted ranking context reopened cleanly for this explicit selection.'}</p></div>
        <div className="summary-card"><p className="stat-label">Artifact Status</p><p className="summary-value">{formatReviewValue(artifact.status)}</p><p className="helper">Status recorded on the authoritative persisted artifact body.</p></div>
        <div className="summary-card"><p className="stat-label">Confidence</p><p className="summary-value">{formatReviewValue(artifact.run_metadata.confidence)}</p><p className="helper">Confidence label saved with the backend ranking run metadata.</p></div>
        <div className="summary-card"><p className="stat-label">Peer Group</p><p className="summary-value">{formatReviewValue(artifact.lineage.peer_group)}</p><p className="helper">Mandate group preserved in persisted replacement lineage.</p></div>
        <div className="summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{formatReviewValue(artifact.lineage.benchmark_symbol)}</p><p className="helper">Benchmark carried with the persisted replacement lineage.</p></div>
        <div className="summary-card"><p className="stat-label">Lookback</p><p className="summary-value">{formatReviewValue(artifact.lineage.lookback_months)}</p><p className="helper">Ranking lookback window in months.</p></div>
        <div className="summary-card"><p className="stat-label">Backend Warnings</p><p className="summary-value">{artifact.warnings.length}</p><p className="helper">Warning count saved with the persisted artifact.</p></div>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Eligible Candidates</p><p className="summary-value">{formatReviewValue(artifact.eligible_count)}</p><p className="helper">Eligible candidate count retained for the persisted replacement run.</p></div>
        <div className="summary-card"><p className="stat-label">Excluded Candidates</p><p className="summary-value">{formatReviewValue(artifact.excluded_count)}</p><p className="helper">Excluded candidate count retained for the persisted replacement run.</p></div>
        <div className="summary-card"><p className="stat-label">Ranking Id</p><p className="summary-value">{formatReviewValue(artifact.ranking_id)}</p><p className="helper">Immutable ranking engine identifier on the persisted artifact.</p></div>
        <div className="summary-card"><p className="stat-label">Methodology Id</p><p className="summary-value">{formatReviewValue(artifact.methodology_id)}</p><p className="helper">Methodology identity saved with the ranking artifact.</p></div>
        <div className="summary-card"><p className="stat-label">Basis Date</p><p className="summary-value">{formatReviewValue(artifact.basis_date)}</p><p className="helper">Basis date saved on the persisted replacement artifact.</p></div>
        <div className="summary-card"><p className="stat-label">Artifact Id</p><p className="summary-value">{formatReviewValue(artifact.artifact_id)}</p><p className="helper">Authoritative persisted ranking artifact backing this review.</p></div>
        <div className="summary-card"><p className="stat-label">Open Handoff</p><p className="summary-value">{formatReviewValue(preflight.open_handoff.handoff_kind)}</p><p className="helper">Canonical backend handoff reused unchanged to reopen this read-only review.</p></div>
      </div>
      <div className="summary-card">
        <p className="stat-label">What This Review Means</p>
        <p className="helper">This is saved replacement ranking context only. No holdings change has been applied, no draft or intent was created here, and no hypothetical replay has been launched from this view.</p>
        <p className="helper">Use this surface to inspect the authoritative persisted choice and methodology context only.</p>
      </div>
      <div className="summary-card">
        <p className="panel-label">Backend Warnings</p>
        {artifact.warnings.length ? artifact.warnings.map((warning) => <p className="helper" key={warning}>{warning}</p>) : <p className="helper">No backend warnings were saved with this replacement review.</p>}
      </div>
      <div className="summary-card">
        <p className="panel-label">Excluded Candidates</p>
        {artifact.excluded_candidates.length ? (
          <div className="list-table">
            {artifact.excluded_candidates.map((item) => <div className="list-row list-row-wide" key={`${item.symbol}-${item.exclusion_reason ?? 'eligible'}`}><span>{item.symbol}</span><span>{item.exclusion_reason ?? 'eligible'}</span></div>)}
          </div>
        ) : <p className="helper">No candidates were excluded from the persisted replacement run.</p>}
      </div>
    </section>
  )
}
