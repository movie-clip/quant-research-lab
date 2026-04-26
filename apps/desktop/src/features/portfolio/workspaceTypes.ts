import type { ConstructionArtifactReplayResponse, HypotheticalReplayResponse, ImportedStatementImporter, ImportedSnapshot, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse, OptimizerPersistedArtifactReference, RankingArtifactKind, RankingArtifactOpenHandoff, RankingArtifactReviewPayloadKind, RankingArtifactSchemaVersion, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from './types'

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
  lastOpenedAt: string
}

export type PersistedConstructionArtifactWorkspaceReview = {
  workspaceId: PortfolioWorkspaceId
  constructionArtifactId: string
  openedAt: string
  replay: ConstructionArtifactReplayResponse
}

export type PersistedOptimizerHandoffWorkspaceReview = {
  workspaceId: PortfolioWorkspaceId
  handoffReference: OptimizerPersistedArtifactReference
  openedAt: string
  validation: OptimizerHandoffValidationResponse
  replay: OptimizerHandoffReplayResponse
}
