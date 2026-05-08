import { useGenericRanking } from './useGenericRanking'
import { GenericRankingRequestForm } from './GenericRankingRequestForm'
import { GenericRankingResultsTable } from './GenericRankingResultsTable'
import { GenericRankingArtifactCard } from './GenericRankingArtifactCard'
import type { GenericRankingRequest } from './types'

export function GenericRankingView() {
  const {
    runLoading,
    runError,
    result,
    resultSource,
    recentRunsLoading,
    recentRunsError,
    recentRuns,
    artifactLoadingId,
    artifactLoadError,
    runRanking,
    loadRecentRuns,
    loadRecentArtifact,
  } = useGenericRanking()

  function handleSubmit(request: GenericRankingRequest) {
    runRanking(request)
  }

  return (
    <article className="panel strategy-lab-panel">
      <p className="panel-label">Generic Ranking</p>
      <h2>Generic ranking workspace</h2>
      <p className="lead compact-lead">
        Rank any universe of instruments using configurable factor score configs. Supports custom lists, ETF peer groups, and broad equity screens.
      </p>

      <GenericRankingRequestForm onSubmit={handleSubmit} loading={runLoading} />

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Recent Runs</p></div>
          <p className="helper">Load a persisted ranking artifact to review a previous run.</p>
        </div>
        <div className="summary-card">
          <div className="dashboard-edit-actions dashboard-edit-actions-compact">
            <button
              className="secondary-button"
              type="button"
              onClick={loadRecentRuns}
              disabled={recentRunsLoading}
            >
              Refresh Recent Runs
            </button>
          </div>

          {recentRunsLoading ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Loading recent ranking runs.</p>
              <p className="helper">Reading persisted artifact summaries from the backend discovery route.</p>
            </div>
          ) : null}

          {!recentRunsLoading && recentRunsError ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Recent ranking runs are unavailable.</p>
              <p className="helper">The recent artifacts list could not be loaded.</p>
              <p className="helper">{recentRunsError}</p>
            </div>
          ) : null}

          {artifactLoadError ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">Recent artifact load failed.</p>
              <p className="helper">The selected persisted ranking artifact could not be loaded.</p>
              <p className="helper">{artifactLoadError}</p>
            </div>
          ) : null}

          {!recentRunsLoading && !recentRunsError && !recentRuns.length ? (
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">No recent ranking runs found.</p>
              <p className="helper">Run a ranking pass to persist an artifact.</p>
            </div>
          ) : null}

          {!recentRunsLoading && !recentRunsError && recentRuns.length ? (
            <div className="factor-snapshot-table-wrap">
              <div className="risk-contrib-table-grid factor-snapshot-header-row strategy-lab-rank-grid-wide">
                <span>As Of</span>
                <span>Universe ID</span>
                <span>Kind</span>
                <span>Score Config</span>
                <span>Benchmark</span>
                <span>Lookback</span>
                <span>Evaluated</span>
                <span>Confidence</span>
                <span>Action</span>
              </div>
              {recentRuns.map((row) => (
                <GenericRankingArtifactCard
                  key={row.artifact_id}
                  row={row}
                  isLoaded={resultSource === 'recent' && result?.artifact_id === row.artifact_id}
                  isLoading={artifactLoadingId === row.artifact_id}
                  onLoad={() => loadRecentArtifact(row.artifact_id)}
                />
              ))}
            </div>
          ) : null}
        </div>
      </section>

      {runLoading ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Running generic ranking.</p>
          <p className="helper">Applying universe filters, computing factor scores, and ranking instruments.</p>
        </div>
      ) : null}

      {!runLoading && !result && !runError ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Run a ranking pass to see results.</p>
          <p className="helper">Configure your universe and score config above, then click Run Ranking.</p>
        </div>
      ) : null}

      {runError ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Generic ranking failed.</p>
          <p className="helper">The request did not return a usable ranking payload.</p>
          <p className="helper">{runError}</p>
        </div>
      ) : null}

      {result && !runLoading ? (
        <GenericRankingResultsTable artifact={result} />
      ) : null}
    </article>
  )
}
