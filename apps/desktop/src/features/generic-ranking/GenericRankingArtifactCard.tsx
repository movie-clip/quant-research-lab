import type { GenericRankingArtifactRecentRow, RankingConfidence } from './types'

function ConfidenceBadge({ confidence }: { confidence: RankingConfidence }) {
  return (
    <span
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

type GenericRankingArtifactCardProps = {
  row: GenericRankingArtifactRecentRow
  isLoaded: boolean
  isLoading: boolean
  onLoad: () => void
}

export function GenericRankingArtifactCard({ row, isLoaded, isLoading, onLoad }: GenericRankingArtifactCardProps) {
  return (
    <div className={`risk-contrib-table-grid factor-shift-data-row strategy-lab-rank-grid-wide${isLoaded ? ' strategy-ranking-row-top' : ''}`}>
      <span>{row.as_of_date}</span>
      <span>{row.universe_id}</span>
      <span>{row.universe_kind}</span>
      <span>{row.score_config_id}</span>
      <span>{row.benchmark_symbol}</span>
      <span>{row.lookback_months}</span>
      <span>{row.evaluated_universe_size}</span>
      <span><ConfidenceBadge confidence={row.confidence} /></span>
      <span>
        <button
          className={`secondary-button${isLoading ? ' button-loading' : ''}`}
          type="button"
          onClick={onLoad}
          disabled={isLoading}
        >
          {isLoading ? 'Loading...' : isLoaded ? 'Loaded' : 'Load Run'}
        </button>
        <small>Load persisted artifact.</small>
      </span>
    </div>
  )
}
