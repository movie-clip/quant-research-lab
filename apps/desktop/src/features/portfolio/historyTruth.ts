export function humanizeContractLabel(value: string | null | undefined) {
  if (!value) return 'n/a'
  if (value === 'live_market_data_verified_adjusted_close') return 'live market data (adjusted-close verified)'
  if (value === 'live_market_data_unverified_return_basis') return 'live market data (return basis unverified)'
  return value.replace(/_/g, ' ')
}

export function formatSnapshotBasisLabel(snapshotBasis: string | null | undefined) {
  if (snapshotBasis === 'imported_snapshot') return 'Imported snapshot'
  if (snapshotBasis === 'snapshot_request') return 'Snapshot request'
  if (snapshotBasis === 'synthetic_replay_snapshot') return 'Synthetic replay snapshot'
  return humanizeContractLabel(snapshotBasis)
}

export function formatHistoryTruthClassLabel(historyTruthClass: string | null | undefined) {
  if (historyTruthClass === 'imported_history_equivalent') return 'Imported portfolio history'
  if (historyTruthClass === 'synthetic_history_derived') return 'Synthetic snapshot-history'
  if (historyTruthClass === 'unavailable') return 'History unavailable'

  return humanizeContractLabel(historyTruthClass)
}

export function formatReplayHistoricalBasisLabel(historicalBasis: string | null | undefined) {
  if (historicalBasis === 'market_data_history') return 'Replay-derived market history'
  return humanizeContractLabel(historicalBasis)
}
