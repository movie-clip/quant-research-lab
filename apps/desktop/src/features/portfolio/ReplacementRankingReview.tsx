import type { IntentBoundSeededEtfReplacementRankingDraftArtifact } from './workspaceTypes'

function formatReviewValue(value: string | number | null | undefined) {
  if (value == null) return 'n/a'
  if (typeof value === 'string') return value.trim() ? value : 'n/a'
  return String(value)
}

function formatCompositeScore(value: number | null | undefined) {
  return value == null ? 'n/a' : value.toFixed(4)
}

function rankingReviewStatus(artifact: IntentBoundSeededEtfReplacementRankingDraftArtifact) {
  if (artifact.confidence === 'low' || artifact.holdingsSupport === 'unavailable') return 'degraded'
  if (artifact.warnings.length || artifact.excludedSymbols.length) return 'warning'
  return 'ok'
}

type Props = {
  artifact: IntentBoundSeededEtfReplacementRankingDraftArtifact
}

export function ReplacementRankingReview({ artifact }: Props) {
  const status = rankingReviewStatus(artifact)

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Ranked Review</p></div>
        <p className="helper">This review saves deterministic ranking context for the ETF you explicitly chose. It supports selection only; replay still validates whether that choice improves the portfolio.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Incumbent</p><p className="summary-value">{formatReviewValue(artifact.baseSymbol)}</p><p className="helper">Explicit incumbent selected from current draft holdings</p></div>
        <div className="summary-card"><p className="stat-label">Chosen Candidate</p><p className="summary-value">{formatReviewValue(artifact.selectedCandidate.symbol)}</p><p className="helper">ETF you explicitly selected from the ranked list</p></div>
        <div className="summary-card"><p className="stat-label">Selected Rank</p><p className="summary-value">{formatReviewValue(artifact.selectedCandidate.rank)}</p><p className="helper">Rank position at selection time</p></div>
        <div className="summary-card"><p className="stat-label">Total Score</p><p className="summary-value">{formatCompositeScore(artifact.selectedCandidate.compositeScore)}</p><p className="helper">Deterministic composite score saved for the chosen ETF</p></div>
        <div className="summary-card"><p className="stat-label">Highest-Ranked Eligible</p><p className="summary-value">{formatReviewValue(artifact.topCandidate?.symbol)}</p><p className="helper">Top-ranked eligible ETF from the same backend run</p></div>
        <div className="summary-card"><p className="stat-label">Next Eligible</p><p className="summary-value">{formatReviewValue(artifact.runnerUpCandidate?.symbol)}</p><p className="helper">Next ranked eligible ETF retained for comparison context</p></div>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Ranking Status</p><p className="summary-value">{status}</p><p className="helper">{status === 'degraded' ? 'Backend ranking context is available but degraded. Interpret this selection cautiously before creating replay intent.' : status === 'warning' ? 'Backend ranking completed with warnings or exclusions. Review the saved details before replay.' : 'Backend ranking context restored cleanly for this explicit selection.'}</p></div>
        <div className="summary-card"><p className="stat-label">Confidence</p><p className="summary-value">{formatReviewValue(artifact.confidence)}</p><p className="helper">Ranking trust level from backend run metadata</p></div>
        <div className="summary-card"><p className="stat-label">Holdings Support</p><p className="summary-value">{formatReviewValue(artifact.holdingsSupport)}</p><p className="helper">Implementation-fit support available in the ranking run</p></div>
        <div className="summary-card"><p className="stat-label">Peer Group</p><p className="summary-value">{formatReviewValue(artifact.peerGroup)}</p><p className="helper">Applied same-mandate group for the run</p></div>
        <div className="summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{formatReviewValue(artifact.benchmarkSymbol)}</p><p className="helper">Benchmark used in the selected ranking run</p></div>
        <div className="summary-card"><p className="stat-label">Lookback</p><p className="summary-value">{formatReviewValue(artifact.lookbackMonths)}</p><p className="helper">Ranking window in months</p></div>
        <div className="summary-card"><p className="stat-label">Backend Warnings</p><p className="summary-value">{artifact.warnings.length}</p><p className="helper">Saved warning count from the deterministic backend run</p></div>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Excluded from Ranking</p><p className="summary-value">{artifact.excludedSymbols.length}</p><p className="helper">Symbols rejected by deterministic eligibility checks in the saved run</p></div>
        <div className="summary-card"><p className="stat-label">Ranking Id</p><p className="summary-value">{formatReviewValue(artifact.rankingId)}</p><p className="helper">Immutable local reference to the backend run</p></div>
        <div className="summary-card"><p className="stat-label">Methodology Id</p><p className="summary-value">{formatReviewValue(artifact.methodologyId)}</p><p className="helper">Methodology identity saved with the ranking review</p></div>
        <div className="summary-card"><p className="stat-label">Basis Date</p><p className="summary-value">{formatReviewValue(artifact.rankingBasisDate)}</p><p className="helper">Ranking basis date saved from run metadata</p></div>
      </div>
      <div className="summary-card">
        <p className="stat-label">What This Review Means</p>
        <p className="helper">This is saved ranking review context only. No holdings change has been applied, no candidate is adopted automatically, and no hypothetical replay has been run from this artifact alone.</p>
        <p className="helper">If you still want to test this explicit user choice, create replacement intent first and use hypothetical replay as the validation step.</p>
      </div>
      <div className="summary-card">
        <p className="panel-label">Top Factor Contributions</p>
        <p className="helper">Factor-level contribution rows are not persisted in the local ranking review artifact.</p>
        <p className="helper">Reopen ETF Ranking if you need the deterministic component-by-component explanation for this saved selection.</p>
      </div>
      <div className="summary-card">
        <p className="panel-label">Backend Warnings</p>
        {artifact.warnings.length ? artifact.warnings.map((warning) => <p className="helper" key={warning}>{warning}</p>) : <p className="helper">No backend warnings were saved with this ranking review.</p>}
      </div>
      <div className="summary-card">
        <p className="panel-label">Excluded Symbols</p>
        {artifact.excludedSymbols.length ? (
          <div className="list-table">
            {artifact.excludedSymbols.map((item) => <div className="list-row list-row-wide" key={`${item.symbol}-${item.reason}`}><span>{item.symbol}</span><span>{item.reason}</span></div>)}
          </div>
        ) : <p className="helper">No symbols were excluded from the saved ranking run.</p>}
      </div>
    </section>
  )
}
