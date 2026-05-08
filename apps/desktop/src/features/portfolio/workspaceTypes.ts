import type { ConstructionArtifactReplayResponse, HypotheticalReplayResponse, ImportedStatementImporter, ImportedSnapshot, MonitorDefinitionAlertReviewTimelineHistoryRow, MonitorDefinitionAlertReviewTimelineObservationRow, MonitorDefinitionAlertReviewTimelineResponse, MonitorDefinitionEvaluationHistoryEntryResponse, MonitorDefinitionObservationArtifact, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse, OptimizerPersistedArtifactReference, RankingArtifactKind, RankingArtifactOpenHandoff, RankingArtifactReviewPayloadKind, RankingArtifactSchemaVersion, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from './types'

export type PortfolioWorkspaceId = string
export type PortfolioNodeId = string
export type PortfolioDraftId = string

export type PortfolioPositionSnapshot = {
  symbol: string
  marketValue: number
  quantity?: number | null
  currency?: string | null
  sector?: string | null
  name?: string | null
  sourceType?: 'equity' | 'etf' | 'cash_equivalent' | 'other'
}

export type CashBalanceSnapshot = {
  currency: string
  amount: number
}

export type PortfolioSnapshot = {
  snapshotVersion: 1
  baseCurrency: string | null
  importedMeta: {
    importer: ImportedStatementImporter | null
    statementPeriod: string | null
    importedAt: string
    sourceFileNames: string[]
  }
  positions: PortfolioPositionSnapshot[]
  cashBalances: CashBalanceSnapshot[]
  metadata: {
    benchmarkSymbol?: string | null
    notes?: string | null
    tags?: string[]
  }
}

export type ImportedHistoryContext = {
  benchmarkSymbol: string
  statementPeriod: string | null
  importedAt: string | null
  importer: ImportedStatementImporter | null
  sourceFileNames: string[]
  historyStartDate: string | null
  historyEndDate: string | null
}

export type ImportedHistorySource =
  | {
      kind: 'imported_replay'
      historyContext: ImportedHistoryContext | null
      importedHistorySnapshot: ImportedSnapshot
    }
  | {
      kind: 'history_context'
      historyContext: ImportedHistoryContext
      importedHistorySnapshot: null
    }
  | {
      kind: 'none'
      historyContext: null
      importedHistorySnapshot: null
    }

export type ImportedNodeSource = {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedStatementImporter | null
  baseCurrency: string | null
  historySource: ImportedHistorySource
}

export type DesktopArtifactReviewBasis = {
  basisVersion: 1
  basisKind: 'persisted_construction_artifact_review' | 'persisted_optimizer_handoff_review'
  reviewScope?: 'workspace_review_only'
  canonicalSource?: 'typed_preview_handoff' | 'persisted_handoff_reference'
  basisProvenanceLabel?: 'artifact_backed_review_basis'
  portfolioTruth?: 'imported_portfolio_snapshot'
  candidateTruth?: 'hypothetical_construction_artifact' | 'hypothetical_optimizer_handoff'
  openedAt: string
  benchmarkSymbol: string | null
  baseCurrency: string | null
  replayWindow: {
    startDate: string | null
    endDate: string | null
  }
  baselineWeights: ConstructionArtifactReplayResponse['baseline_weights'] | OptimizerHandoffReplayResponse['baseline_weights']
  candidateWeights: ConstructionArtifactReplayResponse['candidate_weights'] | OptimizerHandoffReplayResponse['candidate_weights']
}

export type PersistedConstructionArtifactReviewBasis = DesktopArtifactReviewBasis & {
  basisKind: 'persisted_construction_artifact_review'
  constructionArtifactId: string
  previewHandoff: NonNullable<ConstructionArtifactReplayResponse['review_basis']> extends { preview_handoff: infer T } ? T : never
  launchContext: NonNullable<ConstructionArtifactReplayResponse['review_basis']> extends { launch_context: infer T } ? T : never
}

export type PersistedOptimizerHandoffReviewBasis = DesktopArtifactReviewBasis & {
  basisKind: 'persisted_optimizer_handoff_review'
  handoffReference: OptimizerPersistedArtifactReference
}

export type PersistedConstructionArtifactWorkspaceSource = {
  kind: 'persisted_construction_artifact'
  constructionArtifactId: string
  openedAt: string
  reviewBasis?: PersistedConstructionArtifactReviewBasis
}

export type PersistedOptimizerHandoffWorkspaceSource = {
  kind: 'persisted_optimizer_handoff'
  handoffReference: OptimizerPersistedArtifactReference
  openedAt: string
  reviewBasis?: PersistedOptimizerHandoffReviewBasis
}

export type PortfolioWorkspaceSource = ImportedNodeSource | PersistedConstructionArtifactWorkspaceSource | PersistedOptimizerHandoffWorkspaceSource

export type PortfolioWorkspace = {
  id: PortfolioWorkspaceId
  name: string
  createdAt: string
  updatedAt: string
  rootNodeId: PortfolioNodeId
  activeNodeId: PortfolioNodeId
  source: PortfolioWorkspaceSource
}

export type PortfolioNodeKind = 'imported_base' | 'imported_snapshot' | 'variant' | 'artifact_review_basis'

export type PortfolioNode = {
  id: PortfolioNodeId
  workspaceId: PortfolioWorkspaceId
  parentId: PortfolioNodeId | null
  kind: PortfolioNodeKind
  name: string
  createdAt: string
  changeSummary: {
    label: string
    notes?: string | null
    changedPositionsCount: number
    changedSectorsCount: number
    grossExposureDelta?: number | null
    netCapitalDelta?: number | null
  }
  portfolioSnapshot: PortfolioSnapshot | null
  artifactReviewBasis?: PersistedConstructionArtifactReviewBasis | PersistedOptimizerHandoffReviewBasis | null
  source?: ImportedNodeSource | null
}

export type WorkingDraft = {
  id: PortfolioDraftId
  workspaceId: PortfolioWorkspaceId
  baseNodeId: PortfolioNodeId
  updatedAt: string
  name: string
  status: 'clean' | 'dirty'
  portfolioSnapshot: PortfolioSnapshot
}

export type CandidateImprovementSeed = {
  kind: 'etf_replacement_candidate'
  source: 'etf_ranking'
  seededAt: string
  baseSymbol: string
  candidateSymbol: string
  candidateRank: number
  peerGroup: string | null
  benchmarkSymbol: string
  lookbackMonths: number
  rankingId: string
  methodologyId: string
  rankingBasisDate: string
  confidence: 'high' | 'medium' | 'low'
  holdingsSupport: 'sample' | 'mixed' | 'unavailable'
  requestUniverse: string[]
  evaluatedUniverse: string[]
  warningCount: number
  excludedSymbolsCount: number
}

export type CandidateImprovementDraftArtifact = {
  workspaceId: PortfolioWorkspaceId
  draftId: PortfolioDraftId
  baseNodeId: PortfolioNodeId
  seed: CandidateImprovementSeed
}

export type IntentBoundSeededEtfReplacementRankingCandidateSnapshot = {
  symbol: string
  rank: number
  compositeScore: number
  instrument: {
    name: string | null
    assetClass: string | null
    sector: string | null
    category: string | null
    currency: string | null
  }
}

export type IntentBoundSeededEtfReplacementRankingDraftArtifact = {
  kind: 'intent_bound_seeded_etf_replacement_ranking'
  source: 'etf_ranking'
  workspaceId: PortfolioWorkspaceId
  draftId: PortfolioDraftId
  baseNodeId: PortfolioNodeId
  selectedAt: string
  baseSymbol: string
  candidateSymbol: string
  candidateRank: number
  rankingId: string
  methodologyId: string
  rankingBasisDate: string
  openHandoff: RankingArtifactOpenHandoff
  benchmarkSymbol: string
  lookbackMonths: number
  peerGroup: string | null
  confidence: 'high' | 'medium' | 'low'
  holdingsSupport: 'sample' | 'mixed' | 'unavailable'
  requestUniverse: string[]
  evaluatedUniverse: string[]
  warnings: string[]
  excludedSymbols: Array<{
    symbol: string
    reason: string
  }>
  selectedCandidate: IntentBoundSeededEtfReplacementRankingCandidateSnapshot
  topCandidate: IntentBoundSeededEtfReplacementRankingCandidateSnapshot | null
  runnerUpCandidate: IntentBoundSeededEtfReplacementRankingCandidateSnapshot | null
}

export type LegacyIntentBoundSeededEtfReplacementRankingDraftArtifact = IntentBoundSeededEtfReplacementRankingDraftArtifact & {
  artifactId?: string
  artifactKind?: RankingArtifactKind
  schemaVersion?: RankingArtifactSchemaVersion
  reviewPayloadKind?: RankingArtifactReviewPayloadKind
  consumerHandoff?: unknown
}

export type IntentBoundSeededEtfReplacementRankingDraftArtifactInput = Omit<
  IntentBoundSeededEtfReplacementRankingDraftArtifact,
  'workspaceId' | 'draftId' | 'baseNodeId'
>

export type ReplacementIntentDraftArtifact = {
  kind: 'etf_replacement_intent'
  source: 'candidate_seed'
  createdAt: string
  draftId: PortfolioDraftId
  workspaceId: PortfolioWorkspaceId
  baseNodeId: PortfolioNodeId
  baseSymbol: string
  candidateSymbol: string
  seededFromDraftId: PortfolioDraftId
  seedRankingId: string
  seedMethodologyId: string
  seedRankingBasisDate: string
  peerGroup: string | null
  benchmarkSymbol: string
  lookbackMonths: number
  confidence: 'high' | 'medium' | 'low'
  holdingsSupport: 'sample' | 'mixed' | 'unavailable'
  warningCount: number
}

export type HypotheticalReplacementReplayDraftArtifact = {
  workspaceId: PortfolioWorkspaceId
  draftId: PortfolioDraftId
  baseNodeId: PortfolioNodeId
  replacementIntentCreatedAt: string
  replacementIntentBaseSymbol: string
  replacementIntentCandidateSymbol: string
  replay: HypotheticalReplayResponse
}

export type FormedCandidateArtifact = {
  workspaceId: PortfolioWorkspaceId
  draftId: PortfolioDraftId
  baseNodeId: PortfolioNodeId
  replacementIntentCreatedAt: string
  replacementIntentBaseSymbol: string
  replacementIntentCandidateSymbol: string
  formation: SingleReplacementCandidateFormationResponse
}

export type ConstructedCandidateArtifact = {
  workspaceId: PortfolioWorkspaceId
  draftId: PortfolioDraftId
  baseNodeId: PortfolioNodeId
  replacementIntentCreatedAt: string
  replacementIntentBaseSymbol: string
  replacementIntentCandidateSymbol: string
  constructionRuleId: SingleReplacementConstructionRuleId
  construction: SingleReplacementCandidateConstructionResponse
}

export type ConstructionConstraintValidationArtifact = {
  workspaceId: PortfolioWorkspaceId
  draftId: PortfolioDraftId
  baseNodeId: PortfolioNodeId
  replacementIntentCreatedAt: string
  replacementIntentBaseSymbol: string
  replacementIntentCandidateSymbol: string
  constructionRuleId: SingleReplacementConstructionRuleId
  validation: SingleReplacementConstructionConstraintValidationResponse
}

export type SelectedConstructionRuleArtifact = {
  workspaceId: PortfolioWorkspaceId
  draftId: PortfolioDraftId
  baseNodeId: PortfolioNodeId
  selectedRuleId: SingleReplacementConstructionRuleId
}

export type VersionedProposalArtifact = {
  id: string
  kind: 'single_replacement_hypothetical_replay_proposal'
  schemaVersion: 1
  createdAt: string
  workspaceId: PortfolioWorkspaceId
  sourceDraftId: PortfolioDraftId
  sourceBaseNodeId: PortfolioNodeId
  proposalFamilyId: string
  versionNumber: number
  savedFrom: 'desktop_hypothetical_replay_review'
  reviewStatus: 'recorded'
  sourceIntent: ReplacementIntentDraftArtifact
  proposalCapture: ReviewSnapshotProposalCapture
  proposalSource: ProposalSourceLabel
  reviewSnapshotArtifactId: string
  reviewSnapshotPMSummary: SavedProposalReviewSnapshotPMSummaryMirror
  replayBasis: {
    benchmarkSymbol: string
    startDate: string
    endDate: string
    rebalanceFrequency: string
    commissionBps: number
    slippageBps: number
    derivationBasis: HypotheticalReplayResponse['derivation']['baseline_basis']
    candidateConstructionRule: HypotheticalReplayResponse['derivation']['candidate_construction_rule']
    replayProvenance: HypotheticalReplayResponse['replay_provenance']
  }
  reviewSnapshot: HypotheticalReplayResponse
}

export type RawPersistedVersionedProposalArtifact = VersionedProposalArtifact

export type ReviewSnapshotArtifactIdentity = {
  artifact_id: string
  artifact_kind: 'portfolio_review_snapshot'
  schema_version: 'review_snapshot_artifact_v1'
  fingerprint: string
  consumer_kind: 'saved_hypothetical_replay_proposal'
}

export type ReviewSnapshotArtifactLineage = {
  workspace_id: string
  source_draft_id: string
  source_base_node_id: string
  proposal_family_id: string
  proposal_id: string
  version_number: number
  source_kind: 'hypothetical_replacement_replay'
}

export type ReviewSnapshotTruthLabels = {
  proposal_truth: 'review_only_hypothetical_proposal'
  portfolio_truth: 'draft_snapshot_not_applied'
  analytics_truth: 'hypothetical_replay_analytics_only'
  review_scope: 'proposal_review_context_only'
}

export type ReviewSnapshotArtifactAnalyticsSummary = {
  methodology: string
  methodology_provenance: NonNullable<ConstructionArtifactReplayResponse['replay']['methodology_provenance']>
  assumptions: ConstructionArtifactReplayResponse['replay']['candidate_result']['assumptions']
  benchmark_symbol: string | null
  benchmark_return_pct: number | null
  total_return_pct: number | null
  annualized_return_pct: number | null
  annualized_volatility_pct: number | null
  downside_volatility_pct: number | null
  max_drawdown_pct: number | null
  sharpe_ratio: number | null
  sortino_ratio: number | null
  excess_return_pct: number | null
  tracking_error_pct: number | null
  information_ratio: number | null
  beta_vs_benchmark: number | null
  correlation_vs_benchmark: number | null
  total_turnover_pct: number | null
  total_cost_paid: number | null
}

type NonNullDiagnosticsComparison = NonNullable<
  ConstructionArtifactReplayResponse['replay']['diagnostics_comparison']
>

export type ReviewSnapshotArtifactDiagnosticsSummary = {
  diagnostics_available: boolean
  top_factor_exposure_change: NonNullDiagnosticsComparison['top_factor_exposure_change'] | null
  top_volatility_change: NonNullDiagnosticsComparison['top_volatility_change'] | null
  top_risk_contribution_change: NonNullDiagnosticsComparison['top_risk_contribution_change'] | null
  top_concentration_change: NonNullDiagnosticsComparison['top_concentration_change'] | null
  top_stress_scenario_change: NonNullDiagnosticsComparison['top_stress_scenario_change'] | null
}

export type ReviewSnapshotOpenHandoff = {
  handoff_kind: 'review_snapshot_open_handoff_v1'
  artifact_id: string
  artifact_kind: 'portfolio_review_snapshot'
  schema_version: 'review_snapshot_artifact_v1'
  consumer_kind: 'saved_hypothetical_replay_proposal'
}

export type ReviewSnapshotProposalCapture = {
  capture_version: 1
  capture_kind: 'workspace_review_saved_proposal'
  open_handoff: ReviewSnapshotOpenHandoff
  lineage: ReviewSnapshotArtifactLineage
  proposal: {
    source: 'draft_replacement_intent'
    proposal_source: NonNullable<HypotheticalReplayResponse['proposal']['proposal_source']>
    incumbent_symbol: string
    candidate_symbol: string
  }
  replay_type: 'standard' | 'overlay_aware'
  replay_provenance: HypotheticalReplayResponse['replay_provenance']
  review_basis: {
    benchmark_separation: 'explicit_per_snapshot_benchmark_fields'
    benchmark_symbol: string
    replay_window: {
      start_date: string
      end_date: string
    }
    rebalance_frequency: string
    commission_bps: number
    slippage_bps: number
    derivation_basis: HypotheticalReplayResponse['derivation']['baseline_basis']
    candidate_construction_rule: HypotheticalReplayResponse['derivation']['candidate_construction_rule']
  }
}

export type ReviewSnapshotPMSummaryEnvelope = {
  pm_summary_version: 1
  role: 'saved_proposal' | 'baseline' | 'candidate'
  provenance: {
    source: 'persisted_review_snapshot_artifact'
    artifact_kind: 'portfolio_review_snapshot'
    schema_version: 'review_snapshot_artifact_v1'
    consumer_kind: 'saved_hypothetical_replay_proposal'
    lineage: ReviewSnapshotArtifactLineage
    proposal_source: NonNullable<VersionedProposalArtifact['reviewSnapshot']['proposal']['proposal_source']>
    replay_provenance: HypotheticalReplayResponse['replay_provenance']
  }
  truth_labels: ReviewSnapshotTruthLabels
  replay_type: 'standard' | 'overlay_aware'
  replay_status: ConstructionArtifactReplayResponse['replay']['candidate_result']['status']
  investor_economics_status: ConstructionArtifactReplayResponse['replay']['investor_economics_status']
  review_basis: {
    benchmark_separation: 'explicit_per_snapshot_benchmark_fields'
    benchmark_symbol: string
    replay_window: {
      start_date: string
      end_date: string
    }
    rebalance_frequency: string
    commission_bps: number
    slippage_bps: number
    derivation_basis: HypotheticalReplayResponse['derivation']['baseline_basis']
    candidate_construction_rule: HypotheticalReplayResponse['derivation']['candidate_construction_rule']
  }
  methodology: {
    methodology: string
    methodology_provenance: NonNullable<ConstructionArtifactReplayResponse['replay']['methodology_provenance']>
  }
  assumptions: ConstructionArtifactReplayResponse['replay']['candidate_result']['assumptions']
  analytics_summary: {
    candidate_analytics: ReviewSnapshotArtifactAnalyticsSummary
    baseline_analytics: ReviewSnapshotArtifactAnalyticsSummary | null
    analytics_comparison: ConstructionArtifactReplayResponse['replay']['comparison']
  }
  diagnostics_summary: ReviewSnapshotArtifactDiagnosticsSummary
}

export type SavedProposalReviewSnapshotPMSummaryMirror = Omit<ReviewSnapshotPMSummaryEnvelope, 'role' | 'methodology' | 'analytics_summary'> & {
  role: 'saved_proposal'
  methodology: Omit<ReviewSnapshotPMSummaryEnvelope['methodology'], 'methodology_provenance'> & {
    methodology_provenance?: NonNullable<ConstructionArtifactReplayResponse['replay']['methodology_provenance']>
  }
  analytics_summary: Omit<ReviewSnapshotPMSummaryEnvelope['analytics_summary'], 'candidate_analytics'> & {
    candidate_analytics: Omit<ReviewSnapshotArtifactAnalyticsSummary, 'methodology_provenance'> & {
      methodology_provenance?: NonNullable<ConstructionArtifactReplayResponse['replay']['methodology_provenance']>
    }
    baseline_analytics: ReviewSnapshotPMSummaryEnvelope['analytics_summary']['baseline_analytics']
  }
}

export type ReviewSnapshotArtifact = {
  identity: ReviewSnapshotArtifactIdentity
  lineage: ReviewSnapshotArtifactLineage
  review_basis: {
    benchmark_symbol: string
    start_date: string
    end_date: string
    rebalance_frequency: string
    commission_bps: number
    slippage_bps: number
    derivation_basis: HypotheticalReplayResponse['derivation']['baseline_basis']
    candidate_construction_rule: HypotheticalReplayResponse['derivation']['candidate_construction_rule']
    replay_provenance: HypotheticalReplayResponse['replay_provenance']
  }
  truth_labels: ReviewSnapshotTruthLabels
  compact_summary: {
    replay_type: 'standard' | 'overlay_aware'
    replay_status: ConstructionArtifactReplayResponse['replay']['candidate_result']['status']
    investor_economics_status: ConstructionArtifactReplayResponse['replay']['investor_economics_status']
    candidate_analytics: ReviewSnapshotArtifactAnalyticsSummary
    baseline_analytics: ReviewSnapshotArtifactAnalyticsSummary | null
    analytics_comparison: ConstructionArtifactReplayResponse['replay']['comparison']
    diagnostics_summary: ReviewSnapshotArtifactDiagnosticsSummary
  }
  proposal_capture: ReviewSnapshotProposalCapture
  pm_summary: ReviewSnapshotPMSummaryEnvelope
  source_payload: {
    replay_type: 'standard' | 'overlay_aware'
    replay: Extract<HypotheticalReplayResponse, { replay: unknown }> | null
    overlay_replay: Extract<HypotheticalReplayResponse, { overlay_replay: unknown }> | null
  }
}

export type ReviewSnapshotOpenResponse = {
  handoff: ReviewSnapshotOpenHandoff
  artifact: ReviewSnapshotArtifact
  pm_summary: ReviewSnapshotPMSummaryEnvelope
  replay_payload: ReviewSnapshotArtifact['source_payload']
}

export type ReviewSnapshotComparisonArtifactRef = {
  role: 'baseline' | 'candidate'
  artifact_id: string
  artifact_kind: 'portfolio_review_snapshot'
  schema_version: 'review_snapshot_artifact_v1'
  consumer_kind: 'saved_hypothetical_replay_proposal'
}

export type ReviewSnapshotFamilyKey = {
  workspace_id: string
  source_draft_id: string
  source_base_node_id: string
  proposal_family_id: string
  source_kind: 'hypothetical_replacement_replay'
}

export type ReviewSnapshotSiblingComparisonEligibility = {
  eligible: boolean
  reason: 'compatible_family_sibling_available' | 'no_compatible_family_sibling'
  compatible_sibling_artifact_ids: string[]
}

export type ReviewSnapshotFamilySiblingSummary = {
  identity: ReviewSnapshotArtifactIdentity
  open_handoff: ReviewSnapshotOpenHandoff
  lineage: ReviewSnapshotArtifactLineage
  pm_summary: ReviewSnapshotPMSummaryEnvelope
  comparison_eligibility: ReviewSnapshotSiblingComparisonEligibility
}

export type ReviewSnapshotFamilyCompareReadiness = {
  ready: boolean
  reason: 'compatible_family_pair_available' | 'no_compatible_family_pair'
  compatible_pair_count: number
}

export type ReviewSnapshotFamilyInboxRow = {
  family_key: ReviewSnapshotFamilyKey
  latest_identity: ReviewSnapshotArtifactIdentity
  lineage: ReviewSnapshotArtifactLineage
  proposal_capture: ReviewSnapshotProposalCapture
  pm_summary: ReviewSnapshotPMSummaryEnvelope
  sibling_count: number
  compare_readiness: ReviewSnapshotFamilyCompareReadiness
  latest_saved_at: string
  latest_order_provenance: 'persisted_artifact_file_mtime'
}

export type ReviewSnapshotFamilyInboxResponse = {
  inbox_kind: 'review_snapshot_family_inbox'
  workspace_id: string
  provenance: 'persisted_review_snapshot_artifacts_only'
  rows: ReviewSnapshotFamilyInboxRow[]
}

export type ReviewSnapshotFamilyReviewResponse = {
  review_kind: 'review_snapshot_family_review'
  family_key: ReviewSnapshotFamilyKey
  provenance: 'persisted_review_snapshot_artifacts_only'
  compare_selection_policy: 'exactly_two_distinct_family_siblings'
  anchor: ReviewSnapshotFamilySiblingSummary
  siblings: ReviewSnapshotFamilySiblingSummary[]
}

export type ReviewSnapshotActiveThesisCrossFamilyQueueRow = {
  latest_identity: ReviewSnapshotArtifactIdentity
  lineage: ReviewSnapshotArtifactLineage
  family_key: ReviewSnapshotFamilyKey
  family_separation: {
    separation_kind: 'distinct_proposal_family_id'
    active_thesis_proposal_family_id: string
    queue_proposal_family_id: string
  }
  proposal_source: NonNullable<VersionedProposalArtifact['reviewSnapshot']['proposal']['proposal_source']>
  truth_labels: ReviewSnapshotTruthLabels
  trust_visibility: {
    investor_economics_status: ConstructionArtifactReplayResponse['replay']['investor_economics_status']
    benchmark_separation: 'explicit_per_snapshot_benchmark_fields'
  }
  pm_summary_fields: {
    replay_type: 'standard' | 'overlay_aware'
    replay_status: ConstructionArtifactReplayResponse['replay']['candidate_result']['status']
    review_basis: ReviewSnapshotPMSummaryEnvelope['review_basis']
    methodology: ReviewSnapshotPMSummaryEnvelope['methodology']
    assumptions: ReviewSnapshotPMSummaryEnvelope['assumptions']
    analytics_summary: ReviewSnapshotPMSummaryEnvelope['analytics_summary']
    diagnostics_summary: ReviewSnapshotPMSummaryEnvelope['diagnostics_summary']
  }
  latest_saved_at: string
  queue_order_provenance: 'persisted_artifact_file_mtime_desc_then_artifact_id_desc'
}

export type ReviewSnapshotActiveThesisCrossFamilyQueueResponse = {
  queue_kind: 'review_snapshot_active_thesis_cross_family_queue'
  provenance: 'persisted_review_snapshot_artifacts_and_active_thesis_reference_only'
  queue_ordering: 'latest_saved_at_desc_then_artifact_id_desc'
  active_thesis: {
    source_proposal_id: string
    handoff: ReviewSnapshotOpenHandoff
    identity: ReviewSnapshotArtifactIdentity
    lineage: ReviewSnapshotArtifactLineage
    family_key: ReviewSnapshotFamilyKey
  }
  rows: ReviewSnapshotActiveThesisCrossFamilyQueueRow[]
}

export type ReviewSnapshotComparisonResponse = {
  comparison_kind: 'review_snapshot_comparison'
  family_key: ReviewSnapshotFamilyKey
  baseline: {
    benchmark_symbol: string
    replay_window: { start_date: string; end_date: string }
    replay_type: 'standard' | 'overlay_aware'
    candidate_construction_rule: HypotheticalReplayResponse['derivation']['candidate_construction_rule']
    derivation_basis: HypotheticalReplayResponse['derivation']['baseline_basis']
    source_pair: string
    replay_status: ConstructionArtifactReplayResponse['replay']['candidate_result']['status']
    investor_economics_status: ConstructionArtifactReplayResponse['replay']['investor_economics_status']
    methodology: {
      methodology: string
      methodology_provenance: NonNullable<ConstructionArtifactReplayResponse['replay']['methodology_provenance']>
      assumptions: ConstructionArtifactReplayResponse['replay']['candidate_result']['assumptions']
    }
    analytics: ReviewSnapshotArtifactAnalyticsSummary
    diagnostics_summary: ReviewSnapshotArtifactDiagnosticsSummary
  }
  candidate: {
    benchmark_symbol: string
    replay_window: { start_date: string; end_date: string }
    replay_type: 'standard' | 'overlay_aware'
    candidate_construction_rule: HypotheticalReplayResponse['derivation']['candidate_construction_rule']
    derivation_basis: HypotheticalReplayResponse['derivation']['baseline_basis']
    source_pair: string
    replay_status: ConstructionArtifactReplayResponse['replay']['candidate_result']['status']
    investor_economics_status: ConstructionArtifactReplayResponse['replay']['investor_economics_status']
    methodology: {
      methodology: string
      methodology_provenance: NonNullable<ConstructionArtifactReplayResponse['replay']['methodology_provenance']>
      assumptions: ConstructionArtifactReplayResponse['replay']['candidate_result']['assumptions']
    }
    analytics: ReviewSnapshotArtifactAnalyticsSummary
    diagnostics_summary: ReviewSnapshotArtifactDiagnosticsSummary
  }
  provenance: 'persisted_review_snapshot_artifacts_only'
  benchmark_separation: 'explicit_per_snapshot_benchmark_fields'
  baseline_pm_summary: ReviewSnapshotPMSummaryEnvelope
  candidate_pm_summary: ReviewSnapshotPMSummaryEnvelope
  analytics_comparison: ConstructionArtifactReplayResponse['replay']['comparison']
  methodology: {
    baseline_methodology: {
      methodology: string
      methodology_provenance: NonNullable<ConstructionArtifactReplayResponse['replay']['methodology_provenance']>
      assumptions: ConstructionArtifactReplayResponse['replay']['candidate_result']['assumptions']
    }
    candidate_methodology: {
      methodology: string
      methodology_provenance: NonNullable<ConstructionArtifactReplayResponse['replay']['methodology_provenance']>
      assumptions: ConstructionArtifactReplayResponse['replay']['candidate_result']['assumptions']
    }
    assumptions_consistent: boolean
    methodology_consistent: boolean
  }
  assumptions: {
    baseline_assumptions: ConstructionArtifactReplayResponse['replay']['candidate_result']['assumptions']
    candidate_assumptions: ConstructionArtifactReplayResponse['replay']['candidate_result']['assumptions']
    assumptions_consistent: boolean
  }
}

export type ActiveThesisArtifact = {
  workspaceId: PortfolioWorkspaceId
  promotedAt: string
  sourceProposalId: VersionedProposalArtifact['id']
  thesisProposal: VersionedProposalArtifact
}

export type WorkspaceState = {
  workspaceId: PortfolioWorkspaceId
  activeNodeId: PortfolioNodeId
  activeDraftId: PortfolioDraftId | null
  selectedExposureSnapshotId?: string | null
  monitorDefinitionAlertReview?: MonitorDefinitionAlertReviewWorkspaceState | null
  lastOpenedAt: string
}

export type MonitorDefinitionAlertReviewTimelineSelection =
  | {
      eventKind: 'latest_observation_event'
      observationId: string
    }
  | {
      eventKind: 'evaluation_history_event'
      historyEntryId: string
    }

export type MonitorDefinitionAlertReviewWorkspaceState = {
  source: 'definition_scoped_alert_review_timeline'
  monitorDefinitionId: string
  openedAt: string
  selectedEvent: MonitorDefinitionAlertReviewTimelineSelection
  cachedTimeline: MonitorDefinitionAlertReviewTimelineResponse
}

export type MonitorDefinitionAlertReviewLatestObservationOpenState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  row: MonitorDefinitionAlertReviewTimelineObservationRow | null
  observation: MonitorDefinitionObservationArtifact | null
  error: string | null
}

export type MonitorDefinitionAlertReviewAlertHistoryOpenState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  row: MonitorDefinitionAlertReviewTimelineHistoryRow | null
  entry: MonitorDefinitionEvaluationHistoryEntryResponse | null
  error: string | null
}

export type MonitorDefinitionAlertReviewSessionState = {
  navigation: {
    monitorDefinitionId: string
    selectedEvent: MonitorDefinitionAlertReviewTimelineSelection | null
  } | null
  timeline: MonitorDefinitionAlertReviewTimelineResponse | null
  timelineStatus: 'idle' | 'loading' | 'ready' | 'error'
  timelineError: string | null
  latestObservation: MonitorDefinitionAlertReviewLatestObservationOpenState
  alertHistory: MonitorDefinitionAlertReviewAlertHistoryOpenState
}

export type PersistedConstructionArtifactWorkspaceReview = {
  workspaceId: PortfolioWorkspaceId
  constructionArtifactId: string
  openedAt: string
  reviewBasisSource?: ConstructionArtifactReplayResponse['review_basis']
  replay: ConstructionArtifactReplayResponse
}

export type PersistedOptimizerHandoffWorkspaceReview = {
  workspaceId: PortfolioWorkspaceId
  handoffReference: OptimizerPersistedArtifactReference
  openedAt: string
  validation: OptimizerHandoffValidationResponse
  reviewBasisSource?: OptimizerHandoffReplayResponse['review_basis']
  replay: OptimizerHandoffReplayResponse
}

export type ProposalSourceLabel = {
  proposalSourceVersion: 1
  proposalSourceKind: 'draft_replacement_intent_review_only'
  proposalTruth: 'review_only_hypothetical_proposal'
  portfolioTruth: 'draft_snapshot_not_applied'
  reviewScope: 'proposal_review_context_only'
}
