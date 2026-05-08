import type { GenericRankingArtifact, GenericRankingRow, RankingConfidence } from './types'

function formatNumber(value: number | null | undefined, digits = 4) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function confidenceBadgeClass(confidence: RankingConfidence): string {
  if (confidence === 'full') return 'confidence-badge confidence-badge-full'
  if (confidence === 'partial') return 'confidence-badge confidence-badge-partial'
  return 'confidence-badge confidence-badge-degraded'
}

type ConfidenceBadgeProps = { confidence: RankingConfidence }

function ConfidenceBadge({ confidence }: ConfidenceBadgeProps) {
  return (
    <span
      className={confidenceBadgeClass(confidence)}
      style={{
        padding: '2px 8px',
        borderRadius: 4,
        fontWeight: 600,
        fontSize: '0.8em',
        background: confidence === 'full' ? '#1a7c40' : confidence === 'partial' ? '#a06a00' : '#b01c1c',
        color: '#fff',
      }}
    >
      {confidence}
    </span>
  )
}

type GenericRankingResultsTableProps = {
  artifact: GenericRankingArtifact
}

export function GenericRankingResultsTable({ artifact }: GenericRankingResultsTableProps) {
  const { ranked_universe, excluded_instruments, warnings, run_metadata } = artifact

  // Collect all factor_ids in stable order from the first ranked row
  const factorIds: string[] = ranked_universe.length > 0
    ? Object.keys(ranked_universe[0]?.component_scores ?? {})
    : []

  return (
    <>
      <div className="tab-bar" style={{ justifyContent: 'flex-start', margin: '8px 0 0' }}>
        <span className="backtest-source-badge">Artifact: {artifact.artifact_id}</span>
        <span className="backtest-source-badge">As of: {artifact.as_of_date}</span>
        <span className="backtest-source-badge">Benchmark: {artifact.benchmark_symbol}</span>
        <span className="backtest-source-badge">Lookback: {artifact.lookback_months}m</span>
        <span className="backtest-source-badge" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          Confidence: <ConfidenceBadge confidence={run_metadata.confidence} />
        </span>
      </div>

      {warnings.length > 0 ? (
        <section className="dashboard-bottom-grid">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Warnings ({warnings.length})</p></div>
            <p className="helper">Review warnings before treating this ranking as decision-grade.</p>
          </div>
          <div className="list-table">
            {warnings.map((warning) => (
              <div className="list-row list-row-wide" key={warning}><span>{warning}</span></div>
            ))}
          </div>
        </section>
      ) : null}

      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Ranked Universe ({ranked_universe.length})</p></div>
          <p className="helper">Eligible instruments ranked by composite score after normalization and weighting.</p>
        </div>
        {ranked_universe.length ? (
          <div className="factor-snapshot-table-wrap">
            <div
              className="risk-contrib-table-grid factor-snapshot-header-row"
              style={{ gridTemplateColumns: `auto auto auto ${factorIds.map(() => 'auto').join(' ')}` }}
            >
              <span>Rank</span>
              <span>Symbol</span>
              <span>Composite</span>
              {factorIds.map((fid) => <span key={fid}>{fid}</span>)}
            </div>
            {ranked_universe.map((row: GenericRankingRow) => (
              <div
                key={row.symbol}
                className={`risk-contrib-table-grid factor-shift-data-row${row.rank === 1 ? ' strategy-ranking-row-top' : ''}`}
                style={{ gridTemplateColumns: `auto auto auto ${factorIds.map(() => 'auto').join(' ')}` }}
              >
                <span>{row.rank}</span>
                <span><strong>{row.symbol}</strong></span>
                <span><strong>{formatNumber(row.composite_score, 4)}</strong></span>
                {factorIds.map((fid) => {
                  const score = row.component_scores[fid]
                  return (
                    <span key={fid} className="strategy-ranking-metric-cell">
                      <strong>{score?.normalized_score != null ? formatNumber(score.normalized_score, 3) : 'n/a'}</strong>
                      <small>{score?.direction === 'lower_is_better' ? 'lower better' : 'higher better'}</small>
                    </span>
                  )
                })}
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">No eligible instruments were ranked.</p>
            <p className="helper">All instruments may have been excluded by the universe filters.</p>
          </div>
        )}
      </section>

      {excluded_instruments.length > 0 ? (
        <section className="dashboard-bottom-grid">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Excluded Instruments ({excluded_instruments.length})</p></div>
            <p className="helper">Exclusions are explicit and never silent.</p>
          </div>
          <div className="list-table">
            {excluded_instruments.map((item) => (
              <div className="list-row list-row-wide" key={item.symbol}>
                <span><strong>{item.symbol}</strong></span>
                <span>{item.eligibility.hard_filter_failures.join(', ') || 'No failure detail available'}</span>
              </div>
            ))}
          </div>
        </section>
      ) : null}
    </>
  )
}
