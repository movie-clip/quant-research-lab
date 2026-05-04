import type {
  BacktestRunResponse,
  CrossSectionalResearchArtifact,
  CrossSectionalResearchDiscoveryFilters,
  CrossSectionalResearchRecentResponse,
  EtfMomentumStrategyResponse,
  EtfRankingArtifact,
  EtfRankingArtifactRecentMetadata,
  EtfRankingArtifactRecentRow,
} from './types'

export type SessionStateUpdate<T> = T | ((current: T) => T)

export function applySessionStateUpdate<T>(current: T, update: SessionStateUpdate<T>) {
  return typeof update === 'function'
    ? (update as (value: T) => T)(current)
    : update
}

export type StrategyLabUniversePresetKey = 'sectors' | 'broad_rotation' | 'growth_vs_value' | 'risk_on_off'
export type StrategyLabLookbackUnit = 'months' | 'quarters'
export type StrategyLabConstituentHeatmapMetric = 'contribution' | 'return'
export type StrategyLabConstituentHistoryMode = 'selected_etf' | 'leaders_only'

export type StrategyBacktestPanelState = {
  benchmarkSymbol: string
  strategyId: string
  universe: string
  startDate: string
  endDate: string
  initialCapital: string
  backtestLoading: boolean
  backtestError: string | null
}

export function createStrategyBacktestPanelState(): StrategyBacktestPanelState {
  return {
    benchmarkSymbol: 'SPY',
    strategyId: 'book_trend_breakout',
    universe: 'ES,NQ,CL',
    startDate: '2024-01-01',
    endDate: '2024-12-31',
    initialCapital: '100000',
    backtestLoading: false,
    backtestError: null,
  }
}

export function createStrategyLabResearchFilters(): CrossSectionalResearchDiscoveryFilters {
  return {
    artifact_kind: null,
    schema_version: null,
    methodology_id: null,
    dataset_version: null,
    universe_definition: null,
    benchmark_symbol: null,
    rebalance_date: null,
    as_of_date: null,
    holdout_start_date: null,
    methodology_family_id: null,
    methodology_family_version: null,
    active_methodology_version: null,
    alpha_package_version: null,
    alpha_methodology_id: null,
    alpha_input_contract_id: null,
    score_basis: null,
    benchmark_role: null,
    partition_rule: null,
    output_shape: null,
    artifact_status: null,
    diagnostics_status: null,
    coverage_status: null,
    input_source_kind: null,
    replay_provenance_status: null,
    benchmark_source_kind: null,
    alpha_source_kind: null,
  }
}

export type StrategyLabPanelState = {
  selectedPresets: StrategyLabUniversePresetKey[]
  presetMenuOpen: boolean
  detailsOpen: boolean
  universe: string
  benchmarkSymbol: string
  signalLookbackValue: string
  lookbackUnit: StrategyLabLookbackUnit
  topN: string
  constituentHeatmapMetric: StrategyLabConstituentHeatmapMetric
  constituentHistoryMode: StrategyLabConstituentHistoryMode
  selectedLeaderDate: string | null
  loading: boolean
  refreshingHoldings: boolean
  error: string | null
  result: EtfMomentumStrategyResponse | null
  researchRecentLoading: boolean
  researchRecentError: string | null
  researchRecent: CrossSectionalResearchRecentResponse | null
  researchArtifactLoadingId: string | null
  researchArtifactError: string | null
  researchArtifact: CrossSectionalResearchArtifact | null
  researchFilters: CrossSectionalResearchDiscoveryFilters
}

export function createStrategyLabPanelState(): StrategyLabPanelState {
  return {
    selectedPresets: ['broad_rotation'],
    presetMenuOpen: false,
    detailsOpen: false,
    universe: 'XLK,XLF,XLV,XLE,XLI,QQQ,IWM',
    benchmarkSymbol: 'SPY',
    signalLookbackValue: '4',
    lookbackUnit: 'quarters',
    topN: '3',
    constituentHeatmapMetric: 'contribution',
    constituentHistoryMode: 'selected_etf',
    selectedLeaderDate: null,
    loading: false,
    refreshingHoldings: false,
    error: null,
    result: null,
    researchRecentLoading: false,
    researchRecentError: null,
    researchRecent: null,
    researchArtifactLoadingId: null,
    researchArtifactError: null,
    researchArtifact: null,
    researchFilters: createStrategyLabResearchFilters(),
  }
}

export type EtfRankingPanelState = {
  universe: string
  benchmarkSymbol: string
  lookbackMonths: string
  peerGroup: string
  runLoading: boolean
  runError: string | null
  result: EtfRankingArtifact | null
  resultSource: 'fresh' | 'recent' | null
  recentMetadataLoading: boolean
  recentMetadataError: string | null
  recentMetadata: EtfRankingArtifactRecentMetadata | null
  selectedRecentPeerGroup: string
  recentRunsLoading: boolean
  recentRunsError: string | null
  recentRuns: EtfRankingArtifactRecentRow[]
  artifactLoadingId: string | null
  artifactLoadError: string | null
  seedTarget: EtfRankingArtifact['ranked_universe'][number] | null
  selectedBaseSymbol: string
  seedSuccess: string | null
}

export function createEtfRankingPanelState(): EtfRankingPanelState {
  return {
    universe: 'IUFS,IUHC,VDST,VUAA',
    benchmarkSymbol: 'SPY',
    lookbackMonths: '6',
    peerGroup: 'Sector UCITS ETF',
    runLoading: false,
    runError: null,
    result: null,
    resultSource: null,
    recentMetadataLoading: false,
    recentMetadataError: null,
    recentMetadata: null,
    selectedRecentPeerGroup: '',
    recentRunsLoading: false,
    recentRunsError: null,
    recentRuns: [],
    artifactLoadingId: null,
    artifactLoadError: null,
    seedTarget: null,
    selectedBaseSymbol: '',
    seedSuccess: null,
  }
}
