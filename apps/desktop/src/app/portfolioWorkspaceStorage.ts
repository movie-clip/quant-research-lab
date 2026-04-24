import { activeThesisStoreName, appStateStoreName, candidateImprovementDraftStoreName, constructedCandidateStoreName, constructionConstraintValidationStoreName, deletePortfolioDatabase, formedCandidateStoreName, hypotheticalReplacementReplayDraftStoreName, intentBoundSeededEtfReplacementRankingDraftStoreName, persistedConstructionArtifactReviewStoreName, persistedOptimizerHandoffReviewStoreName, portfolioNodeStoreName, replacementIntentDraftStoreName, selectedConstructionRuleStoreName, versionedProposalStoreName, withStore, withStores, workingDraftStoreName, workspaceStateStoreName, workspaceStoreName } from './portfolioDb'
import { buildImportedHistorySource } from '../features/portfolio/historySource'
import { buildPortfolioSnapshotFromAnalysis, clonePortfolioSnapshot, getPortfolioSnapshotGrossExposure, getPortfolioSnapshotNetCapital, getPortfolioSnapshotSectorCount, hashPortfolioSnapshot } from '../features/portfolio/portfolioSnapshot'
import type { ConstructionArtifactReplayResponse, ImportedPortfolioSnapshotSource, ImportedSnapshot, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse } from '../features/portfolio/types'
import type { ActiveThesisArtifact, CandidateImprovementDraftArtifact, DesktopArtifactReviewBasis, FormedCandidateArtifact, HypotheticalReplacementReplayDraftArtifact, ImportedHistoryContext, ImportedNodeSource, IntentBoundSeededEtfReplacementRankingDraftArtifact, PersistedConstructionArtifactReviewBasis, PersistedConstructionArtifactWorkspaceReview, PersistedOptimizerHandoffReviewBasis, PersistedOptimizerHandoffWorkspaceReview, PortfolioNode, PortfolioSnapshot, PortfolioWorkspace, ReplacementIntentDraftArtifact, SelectedConstructionRuleArtifact, VersionedProposalArtifact, WorkingDraft, WorkspaceState, ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact } from '../features/portfolio/workspaceTypes'

const activeWorkspacePointerKey = 'active-workspace-pointer'

function normalizeConstructionArtifactReplayResponse(replay: ConstructionArtifactReplayResponse): ConstructionArtifactReplayResponse {
  if (replay.effective_replay_params) {
    return replay
  }

  return {
    ...replay,
    effective_replay_params: {
      benchmark_symbol: replay.replay.candidate_result.benchmark_symbol ?? 'SPY',
      start_date: replay.replay.candidate_result.start_date,
      end_date: replay.replay.candidate_result.end_date,
      initial_capital: replay.replay.candidate_result.equity_curve[0]?.equity ?? 100000,
      rebalance_frequency: replay.replay.candidate_result.rebalance_frequency,
      base_currency: replay.replay.candidate_result.assumptions.investor_base_currency ?? 'USD',
      commission_bps: replay.replay.candidate_result.commission_bps,
      slippage_bps: replay.replay.candidate_result.slippage_bps,
      drift_tolerance_pct: replay.replay.candidate_result.drift_tolerance_pct,
      price_basis: 'adjusted_close',
      execution_price_field: 'close',
      execution_lag_days: replay.replay.candidate_result.assumptions.execution_lag_days,
      symbol_overrides: {},
    },
  }
}

export function buildPersistedImportedSource(input: {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedNodeSource['importer']
  baseCurrency: string | null
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): ImportedNodeSource {
  return {
    importedFileNames: input.importedFileNames,
    importedAt: input.importedAt,
    importer: input.importer,
    baseCurrency: input.baseCurrency,
    historySource: buildImportedHistorySource({
      historyContext: input.historyContext ?? null,
      importedHistorySnapshot: input.importedHistorySnapshot ?? null,
    }),
  }
}

function createId(prefix: string) {
  return `${prefix}_${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`
}

function buildDesktopArtifactReviewBasis(input: {
  constructionArtifactId: string
  openedAt: string
  replay: ConstructionArtifactReplayResponse
}): PersistedConstructionArtifactReviewBasis {
  return {
    basisVersion: 1,
    basisKind: 'persisted_construction_artifact_review',
    constructionArtifactId: input.constructionArtifactId,
    openedAt: input.openedAt,
    benchmarkSymbol: input.replay.replay.candidate_result.benchmark_symbol ?? null,
    baseCurrency: input.replay.replay.candidate_result.assumptions.investor_base_currency ?? input.replay.replay.reference_result?.assumptions.investor_base_currency ?? input.replay.effective_replay_params?.base_currency ?? null,
    replayWindow: {
      startDate: input.replay.replay.candidate_result.start_date ?? null,
      endDate: input.replay.replay.candidate_result.end_date ?? null,
    },
    baselineWeights: input.replay.baseline_weights,
    candidateWeights: input.replay.candidate_weights,
  }
}

function buildOptimizerHandoffReviewBasis(input: {
  handoffReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference']
  openedAt: string
  replay: OptimizerHandoffReplayResponse
}): PersistedOptimizerHandoffReviewBasis {
  return {
    basisVersion: 1,
    basisKind: 'persisted_optimizer_handoff_review',
    handoffReference: input.handoffReference,
    openedAt: input.openedAt,
    benchmarkSymbol: input.replay.replay.candidate_result.benchmark_symbol ?? input.replay.replay_provenance.benchmark_symbol ?? null,
    baseCurrency: input.replay.replay.candidate_result.assumptions.investor_base_currency ?? input.replay.replay.reference_result?.assumptions.investor_base_currency ?? null,
    replayWindow: {
      startDate: input.replay.replay.candidate_result.start_date ?? null,
      endDate: input.replay.replay.candidate_result.end_date ?? null,
    },
    baselineWeights: input.replay.baseline_weights,
    candidateWeights: input.replay.candidate_weights,
  }
}

type LegacyOptimizerIdentityFields = {
  handoffId?: string
  artifactId?: string | null
}

type LegacyOptimizerIdentityFieldPresence = LegacyOptimizerIdentityFields & {
  hasHandoffId: boolean
  hasArtifactId: boolean
}

function inspectLegacyOptimizerIdentityFields(value: unknown): LegacyOptimizerIdentityFieldPresence {
  if (!value || typeof value !== 'object') {
    return {
      hasHandoffId: false,
      hasArtifactId: false,
    }
  }

  const candidate = value as { handoffId?: unknown; artifactId?: unknown }
  return {
    hasHandoffId: 'handoffId' in candidate,
    handoffId: typeof candidate.handoffId === 'string' ? candidate.handoffId : undefined,
    hasArtifactId: 'artifactId' in candidate,
    artifactId: candidate.artifactId === null || typeof candidate.artifactId === 'string' ? candidate.artifactId : undefined,
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function assertValidOptimizerHandoffReference(
  value: unknown,
  label: string,
): asserts value is PersistedOptimizerHandoffWorkspaceReview['handoffReference'] {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is missing or invalid handoff reference`)
  }

  const candidate = value as Partial<PersistedOptimizerHandoffWorkspaceReview['handoffReference']>
  if (
    candidate.reference_kind !== 'optimizer_handoff_reference_v1'
    || !isNonEmptyString(candidate.handoff_id)
    || !isNonEmptyString(candidate.artifact_id)
    || !isNonEmptyString(candidate.manifest_path)
    || !isNonEmptyString(candidate.artifact_path)
  ) {
    throw new Error(`${label} is missing or invalid handoff reference`)
  }
}

function assertOptimizerHandoffReferenceMatchesCanonical(
  value: unknown,
  canonicalReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference'],
  label: string,
) {
  assertValidOptimizerHandoffReference(value, label)

  if (
    value.reference_kind !== canonicalReference.reference_kind
    || value.handoff_id !== canonicalReference.handoff_id
    || value.artifact_id !== canonicalReference.artifact_id
    || value.manifest_path !== canonicalReference.manifest_path
    || value.artifact_path !== canonicalReference.artifact_path
  ) {
    throw new Error(`${label} conflicts with canonical persisted review`)
  }
}

function canonicalizeOptimizerReviewBasisForComparison(basis: PersistedOptimizerHandoffReviewBasis) {
  return {
    basisVersion: basis.basisVersion,
    basisKind: basis.basisKind,
    handoffReference: basis.handoffReference,
    openedAt: basis.openedAt,
    benchmarkSymbol: basis.benchmarkSymbol,
    baseCurrency: basis.baseCurrency,
    replayWindow: basis.replayWindow,
    baselineWeights: basis.baselineWeights,
    candidateWeights: basis.candidateWeights,
  }
}

function assertCachedOptimizerReviewBasisMatchesCanonical(
  value: unknown,
  canonicalReviewBasis: PersistedOptimizerHandoffReviewBasis,
  label: string,
) {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is malformed`)
  }

  const candidate = value as Partial<PersistedOptimizerHandoffReviewBasis>
  if (candidate.basisKind !== 'persisted_optimizer_handoff_review') {
    throw new Error(`${label} has unsupported basis kind`)
  }
  if (candidate.basisVersion !== 1) {
    throw new Error(`${label} has unsupported basis version`)
  }

  assertOptimizerHandoffReferenceMatchesCanonical(candidate.handoffReference, canonicalReviewBasis.handoffReference, label)
  assertLegacyOptimizerIdentityMatchesReference(candidate, canonicalReviewBasis.handoffReference, label)

  if (
    JSON.stringify(canonicalizeOptimizerReviewBasisForComparison(candidate as PersistedOptimizerHandoffReviewBasis))
    !== JSON.stringify(canonicalizeOptimizerReviewBasisForComparison(canonicalReviewBasis))
  ) {
    throw new Error(`${label} conflicts with canonical persisted review`)
  }
}

function getLegacyOptimizerIdentityFields(value: unknown): LegacyOptimizerIdentityFields {
  const { handoffId, artifactId } = inspectLegacyOptimizerIdentityFields(value)
  return { handoffId, artifactId }
}

function hasLegacyOptimizerIdentityFields(value: unknown) {
  const legacyIdentity = inspectLegacyOptimizerIdentityFields(value)
  return legacyIdentity.hasHandoffId || legacyIdentity.hasArtifactId
}

function assertLegacyOptimizerIdentityMatchesReference(value: unknown, handoffReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference'], label: string) {
  const legacyIdentity = inspectLegacyOptimizerIdentityFields(value)

  if (legacyIdentity.hasHandoffId !== legacyIdentity.hasArtifactId) {
    throw new Error(`${label} has partial legacy identity fields`)
  }
  if (!legacyIdentity.hasHandoffId) {
    return
  }
  if (legacyIdentity.handoffId == null) {
    throw new Error(`${label} has invalid legacy handoff identity`)
  }
  if (!isNonEmptyString(legacyIdentity.artifactId)) {
    throw new Error(`${label} has invalid legacy artifact identity`)
  }

  if (legacyIdentity.handoffId !== handoffReference.handoff_id) {
    throw new Error(`${label} is inconsistent with handoff reference identity`)
  }
  if (legacyIdentity.artifactId !== handoffReference.artifact_id) {
    throw new Error(`${label} is inconsistent with artifact reference identity`)
  }
}

function toCanonicalPersistedOptimizerHandoffReview(review: PersistedOptimizerHandoffWorkspaceReview): PersistedOptimizerHandoffWorkspaceReview {
  assertValidOptimizerHandoffReference(review.handoffReference, 'Persisted optimizer handoff review cache')
  const replayHandoffId = review.replay.handoff_id
  const replayArtifactId = review.replay.artifact_id
  const validationHandoffId = review.validation.handoff_id ?? null
  const validationArtifactId = review.validation.artifact_id ?? null
  const referenceHandoffId = review.handoffReference.handoff_id
  const referenceArtifactId = review.handoffReference.artifact_id

  assertLegacyOptimizerIdentityMatchesReference(review, review.handoffReference, 'Persisted optimizer handoff review cache')

  if (replayHandoffId !== referenceHandoffId || replayArtifactId !== referenceArtifactId) {
    throw new Error('Persisted optimizer handoff review cache is inconsistent with replay identity')
  }
  if (validationHandoffId != null && validationHandoffId !== referenceHandoffId) {
    throw new Error('Persisted optimizer handoff review cache is inconsistent with validation handoff identity')
  }
  if (validationArtifactId != null && validationArtifactId !== referenceArtifactId) {
    throw new Error('Persisted optimizer handoff review cache is inconsistent with validation artifact identity')
  }
  if (review.replay.optimizer_context == null) {
    throw new Error('Persisted optimizer handoff review cache is missing replay optimizer context')
  }
  if (review.replay.optimizer_context.objective == null) {
    throw new Error('Persisted optimizer handoff review cache is missing replay optimizer objective')
  }

  return {
    workspaceId: review.workspaceId,
    handoffReference: review.handoffReference,
    openedAt: review.openedAt,
    validation: review.validation,
    replay: review.replay,
  }
}

function canonicalizePersistedOptimizerHandoffReviewForWrite(review: PersistedOptimizerHandoffWorkspaceReview): PersistedOptimizerHandoffWorkspaceReview {
  return toCanonicalPersistedOptimizerHandoffReview(review)
}

function buildPersistedOptimizerHandoffWorkspaceRecords(input: {
  workspaceId: string
  rootNodeId: string
  handoffReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference']
  openedAt: string
  validation: OptimizerHandoffValidationResponse
  replay: OptimizerHandoffReplayResponse
}): {
  workspace: PortfolioWorkspace
  rootNode: PortfolioNode
  workspaceState: WorkspaceState
  review: PersistedOptimizerHandoffWorkspaceReview
} {
  const review = canonicalizePersistedOptimizerHandoffReviewForWrite({
    workspaceId: input.workspaceId,
    handoffReference: input.handoffReference,
    openedAt: input.openedAt,
    validation: input.validation,
    replay: input.replay,
  })
  const reviewBasis = buildOptimizerHandoffReviewBasis({
    handoffReference: review.handoffReference,
    openedAt: review.openedAt,
    replay: review.replay,
  })

  return {
    workspace: {
      id: input.workspaceId,
      name: `Optimizer Handoff ${review.handoffReference.handoff_id}`,
      createdAt: review.openedAt,
      updatedAt: review.openedAt,
      rootNodeId: input.rootNodeId,
      activeNodeId: input.rootNodeId,
      source: {
        kind: 'persisted_optimizer_handoff',
        handoffReference: review.handoffReference,
        openedAt: review.openedAt,
        reviewBasis,
      },
    },
    rootNode: {
      id: input.rootNodeId,
      workspaceId: input.workspaceId,
      parentId: null,
      kind: 'artifact_review_basis',
      name: 'Artifact Review Basis',
      createdAt: review.openedAt,
      changeSummary: {
        label: 'Artifact Review Basis',
        changedPositionsCount: review.replay.candidate_weights.length,
        changedSectorsCount: 0,
        grossExposureDelta: null,
        netCapitalDelta: null,
      },
      portfolioSnapshot: null,
      artifactReviewBasis: reviewBasis,
    },
    workspaceState: {
      workspaceId: input.workspaceId,
      activeNodeId: input.rootNodeId,
      activeDraftId: null,
      selectedExposureSnapshotId: input.rootNodeId,
      lastOpenedAt: review.openedAt,
    },
    review,
  }
}

function buildLegacyArtifactReviewSnapshot(input: {
  constructionArtifactId: string
  openedAt: string
  replay: ConstructionArtifactReplayResponse
}): PortfolioSnapshot {
  return {
    snapshotVersion: 1,
    baseCurrency: input.replay.replay.candidate_result.assumptions.investor_base_currency ?? input.replay.replay.reference_result?.assumptions.investor_base_currency ?? 'USD',
    importedMeta: {
      importer: null,
      statementPeriod: `${input.replay.replay.candidate_result.start_date} - ${input.replay.replay.candidate_result.end_date}`,
      importedAt: input.openedAt,
      sourceFileNames: [input.constructionArtifactId],
    },
    positions: input.replay.baseline_weights.map((row) => ({
      symbol: row.symbol,
      marketValue: row.target_weight,
      quantity: null,
      currency: null,
      sector: null,
      name: null,
      sourceType: 'other' as const,
    })),
    cashBalances: [],
    metadata: {
      benchmarkSymbol: input.replay.replay.candidate_result.benchmark_symbol,
      notes: `Persisted construction artifact review: ${input.constructionArtifactId}`,
      tags: ['persisted_construction_artifact_review'],
    },
  }
}

function normalizePersistedConstructionArtifactWorkspace(input: {
  workspace: PortfolioWorkspace
  node: PortfolioNode
  review: PersistedConstructionArtifactWorkspaceReview
}) {
  const reviewBasis = buildDesktopArtifactReviewBasis({
    constructionArtifactId: input.review.constructionArtifactId,
    openedAt: input.review.openedAt,
    replay: input.review.replay,
  })

  const workspaceSource = input.workspace.source
  if (!('kind' in workspaceSource) || workspaceSource.kind !== 'persisted_construction_artifact') {
    throw new Error('Persisted construction artifact workspace normalization requires a persisted construction artifact source')
  }

  const normalizedWorkspace: PortfolioWorkspace = workspaceSource.reviewBasis
    ? input.workspace
    : {
        ...input.workspace,
        source: {
          ...workspaceSource,
          reviewBasis,
        },
      }

  const normalizedNode: PortfolioNode = input.node.kind === 'artifact_review_basis' && input.node.artifactReviewBasis
    ? { ...input.node, portfolioSnapshot: null }
    : {
        ...input.node,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        changeSummary: {
          ...input.node.changeSummary,
          label: 'Artifact Review Basis',
        },
        portfolioSnapshot: null,
        artifactReviewBasis: reviewBasis,
      }

  return {
    workspace: normalizedWorkspace,
    node: normalizedNode,
    review: {
      ...input.review,
      replay: normalizeConstructionArtifactReplayResponse(input.review.replay),
    },
  }
}

export async function normalizeLegacyPersistedConstructionArtifactWorkspaceCache(input: {
  workspace: PortfolioWorkspace
  node: PortfolioNode
  review: PersistedConstructionArtifactWorkspaceReview
}) {
  const normalized = normalizePersistedConstructionArtifactWorkspace(input)
  const workspaceSource = input.workspace.source
  const workspaceAlreadyNormalized = 'kind' in workspaceSource && workspaceSource.kind === 'persisted_construction_artifact' && workspaceSource.reviewBasis != null
  const nodeAlreadyNormalized = input.node.kind === 'artifact_review_basis' && input.node.artifactReviewBasis != null && input.node.portfolioSnapshot == null

  if (workspaceAlreadyNormalized && nodeAlreadyNormalized) {
    return normalized
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(normalized.workspace)
    const nodeRequest = transaction.objectStore(portfolioNodeStoreName).put(normalized.node)
    nodeRequest.onsuccess = () => resolve(normalized)
    nodeRequest.onerror = () => reject(nodeRequest.error ?? new Error('Failed to normalize persisted construction artifact workspace cache'))
  })

  return normalized
}

function normalizePersistedOptimizerHandoffWorkspace(input: {
  workspace: PortfolioWorkspace
  node: PortfolioNode
  review: PersistedOptimizerHandoffWorkspaceReview
}) {
  const canonicalReview = toCanonicalPersistedOptimizerHandoffReview(input.review)
  const reviewBasis = buildOptimizerHandoffReviewBasis({
    handoffReference: canonicalReview.handoffReference,
    openedAt: canonicalReview.openedAt,
    replay: canonicalReview.replay,
  })

  const workspaceSource = input.workspace.source
  if (!('kind' in workspaceSource) || workspaceSource.kind !== 'persisted_optimizer_handoff') {
    throw new Error('Persisted optimizer handoff workspace normalization requires a persisted optimizer handoff source')
  }

  assertOptimizerHandoffReferenceMatchesCanonical(workspaceSource.handoffReference, canonicalReview.handoffReference, 'Persisted optimizer handoff workspace source')
  assertLegacyOptimizerIdentityMatchesReference(workspaceSource, canonicalReview.handoffReference, 'Persisted optimizer handoff workspace source')

  if (workspaceSource.reviewBasis != null) {
    assertCachedOptimizerReviewBasisMatchesCanonical(workspaceSource.reviewBasis, reviewBasis, 'Persisted optimizer handoff workspace review basis')
  }

  const workspaceNeedsRepair = workspaceSource.reviewBasis == null
    || hasLegacyOptimizerIdentityFields(workspaceSource)
    || hasLegacyOptimizerIdentityFields(workspaceSource.reviewBasis)
  const normalizedWorkspace: PortfolioWorkspace = !workspaceNeedsRepair
    ? input.workspace
    : {
        ...input.workspace,
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: canonicalReview.handoffReference,
          openedAt: workspaceSource.openedAt,
          reviewBasis,
        },
      }

  if (input.node.artifactReviewBasis != null) {
    assertCachedOptimizerReviewBasisMatchesCanonical(input.node.artifactReviewBasis, reviewBasis, 'Persisted optimizer handoff node review basis')
  }

  const nodeNeedsRepair = input.node.artifactReviewBasis != null && hasLegacyOptimizerIdentityFields(input.node.artifactReviewBasis)
  const normalizedNode: PortfolioNode = input.node.kind === 'artifact_review_basis' && input.node.artifactReviewBasis && !nodeNeedsRepair
    ? { ...input.node, portfolioSnapshot: null }
    : {
        ...input.node,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        changeSummary: {
          ...input.node.changeSummary,
          label: 'Artifact Review Basis',
        },
        portfolioSnapshot: null,
        artifactReviewBasis: reviewBasis,
      }

  return {
    workspace: normalizedWorkspace,
    node: normalizedNode,
    review: canonicalReview,
  }
}

export async function normalizeLegacyPersistedOptimizerHandoffWorkspaceCache(input: {
  workspace: PortfolioWorkspace
  node: PortfolioNode
  review: PersistedOptimizerHandoffWorkspaceReview
}) {
  const normalized = normalizePersistedOptimizerHandoffWorkspace(input)
  const workspaceSource = input.workspace.source
  const workspaceAlreadyNormalized = 'kind' in workspaceSource
    && workspaceSource.kind === 'persisted_optimizer_handoff'
    && workspaceSource.reviewBasis != null
    && !hasLegacyOptimizerIdentityFields(workspaceSource)
    && !hasLegacyOptimizerIdentityFields(workspaceSource.reviewBasis)
  const nodeAlreadyNormalized = input.node.kind === 'artifact_review_basis'
    && input.node.artifactReviewBasis != null
    && input.node.portfolioSnapshot == null
    && (input.node.artifactReviewBasis.basisKind !== 'persisted_optimizer_handoff_review' || !hasLegacyOptimizerIdentityFields(input.node.artifactReviewBasis))

  if (workspaceAlreadyNormalized && nodeAlreadyNormalized) {
    return normalized
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(normalized.workspace)
    const nodeRequest = transaction.objectStore(portfolioNodeStoreName).put(normalized.node)
    nodeRequest.onsuccess = () => resolve(normalized)
    nodeRequest.onerror = () => reject(nodeRequest.error ?? new Error('Failed to normalize persisted optimizer handoff workspace cache'))
  })

  return normalized
}

function createChangeSummary(baseSnapshot: PortfolioSnapshot, nextSnapshot: PortfolioSnapshot, label: string) {
  const baseMap = new Map(baseSnapshot.positions.map((position) => [position.symbol, position.marketValue]))
  const nextMap = new Map(nextSnapshot.positions.map((position) => [position.symbol, position.marketValue]))
  const symbols = new Set([...baseMap.keys(), ...nextMap.keys()])
  const changedPositionsCount = Array.from(symbols).filter((symbol) => (baseMap.get(symbol) ?? 0) !== (nextMap.get(symbol) ?? 0)).length

  return {
    label,
    changedPositionsCount,
    changedSectorsCount: Math.abs(getPortfolioSnapshotSectorCount(nextSnapshot) - getPortfolioSnapshotSectorCount(baseSnapshot)),
    grossExposureDelta: getPortfolioSnapshotGrossExposure(nextSnapshot) - getPortfolioSnapshotGrossExposure(baseSnapshot),
    netCapitalDelta: getPortfolioSnapshotNetCapital(nextSnapshot) - getPortfolioSnapshotNetCapital(baseSnapshot),
  }
}

export function assertSavedProposalArtifactIntegrity(proposal: VersionedProposalArtifact): VersionedProposalArtifact {
  const replayBasis = proposal.replayBasis
  const reviewSnapshot = proposal.reviewSnapshot
  const replayProvenance = replayBasis.replayProvenance
  const snapshotProvenance = reviewSnapshot.replay_provenance

  if (replayBasis.candidateConstructionRule !== reviewSnapshot.derivation.candidate_construction_rule) {
    throw new Error('Saved proposal candidateConstructionRule does not match reviewSnapshot derivation')
  }
  if (replayProvenance.construction_rule_id !== snapshotProvenance.construction_rule_id) {
    throw new Error('Saved proposal replayProvenance construction_rule_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.candidate_input_source !== snapshotProvenance.candidate_input_source) {
    throw new Error('Saved proposal replayProvenance candidate_input_source does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.upstream_ids.draft_id !== snapshotProvenance.upstream_ids.draft_id) {
    throw new Error('Saved proposal replayProvenance upstream draft_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.upstream_ids.workspace_id !== snapshotProvenance.upstream_ids.workspace_id) {
    throw new Error('Saved proposal replayProvenance upstream workspace_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.upstream_ids.base_node_id !== snapshotProvenance.upstream_ids.base_node_id) {
    throw new Error('Saved proposal replayProvenance upstream base_node_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.seed_ranking_id !== snapshotProvenance.seed_ranking_id) {
    throw new Error('Saved proposal replayProvenance seed_ranking_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.seed_methodology_id !== snapshotProvenance.seed_methodology_id) {
    throw new Error('Saved proposal replayProvenance seed_methodology_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.constraint_validation.supplied !== snapshotProvenance.constraint_validation.supplied) {
    throw new Error('Saved proposal replayProvenance constraint_validation.supplied does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.constraint_validation.validation_status !== snapshotProvenance.constraint_validation.validation_status) {
    throw new Error('Saved proposal replayProvenance constraint_validation.validation_status does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.constraint_validation.constraint_set_id !== snapshotProvenance.constraint_validation.constraint_set_id) {
    throw new Error('Saved proposal replayProvenance constraint_validation.constraint_set_id does not match reviewSnapshot replay_provenance')
  }

  return proposal
}


export function buildSavedProposalArtifact(input: {
  id: string
  createdAt: string
  workspaceId: string
  sourceDraftId: string
  sourceBaseNodeId: string
  proposalFamilyId: string
  versionNumber: number
  sourceIntent: ReplacementIntentDraftArtifact
  hypotheticalReplay: VersionedProposalArtifact['reviewSnapshot']
}): VersionedProposalArtifact {
  const activeReplay = 'replay' in input.hypotheticalReplay ? input.hypotheticalReplay.replay : input.hypotheticalReplay.overlay_replay
  return assertSavedProposalArtifactIntegrity({
    id: input.id,
    kind: 'single_replacement_hypothetical_replay_proposal',
    schemaVersion: 1,
    createdAt: input.createdAt,
    workspaceId: input.workspaceId,
    sourceDraftId: input.sourceDraftId,
    sourceBaseNodeId: input.sourceBaseNodeId,
    proposalFamilyId: input.proposalFamilyId,
    versionNumber: input.versionNumber,
    savedFrom: 'desktop_hypothetical_replay_review',
    reviewStatus: 'recorded',
    sourceIntent: input.sourceIntent,
    replayBasis: {
      benchmarkSymbol: activeReplay.candidate_result.benchmark_symbol ?? input.sourceIntent.benchmarkSymbol,
      startDate: activeReplay.candidate_result.start_date,
      endDate: activeReplay.candidate_result.end_date,
      rebalanceFrequency: activeReplay.candidate_result.rebalance_frequency,
      commissionBps: activeReplay.candidate_result.commission_bps,
      slippageBps: activeReplay.candidate_result.slippage_bps,
      derivationBasis: input.hypotheticalReplay.derivation.baseline_basis,
      candidateConstructionRule: input.hypotheticalReplay.derivation.candidate_construction_rule,
      replayProvenance: input.hypotheticalReplay.replay_provenance,
    },
    reviewSnapshot: input.hypotheticalReplay,
  })
}

export function isDraftDirty(baseSnapshot: PortfolioSnapshot, draftSnapshot: PortfolioSnapshot) {
  return hashPortfolioSnapshot(baseSnapshot) !== hashPortfolioSnapshot(draftSnapshot)
}

export async function createWorkspaceFromImport(input: {
  name?: string
  analysis: ImportedPortfolioSnapshotSource
  importedFileNames: string[]
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): Promise<{ workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: WorkingDraft; workspaceState: WorkspaceState }> {
  const portfolioSnapshot = buildPortfolioSnapshotFromAnalysis(input.analysis, input.importedFileNames)
  const importedAt = portfolioSnapshot.importedMeta.importedAt
  const workspaceId = createId('workspace')
  const rootNodeId = createId('node')
  const draftId = createId('draft')
  const workspace: PortfolioWorkspace = {
    id: workspaceId,
    name: input.name ?? portfolioSnapshot.importedMeta.statementPeriod ?? 'Portfolio Workspace',
    createdAt: importedAt,
    updatedAt: importedAt,
    rootNodeId,
    activeNodeId: rootNodeId,
    source: buildPersistedImportedSource({
      importedFileNames: input.importedFileNames,
      importedAt,
      importer: portfolioSnapshot.importedMeta.importer,
      baseCurrency: portfolioSnapshot.baseCurrency,
      historyContext: input.historyContext ?? null,
      importedHistorySnapshot: input.importedHistorySnapshot ?? null,
    }),
  }
  const rootNode: PortfolioNode = {
    id: rootNodeId,
    workspaceId,
    parentId: null,
    kind: 'imported_base',
    name: 'Base Import',
    createdAt: importedAt,
    changeSummary: {
      label: 'Base Import',
      changedPositionsCount: portfolioSnapshot.positions.length,
      changedSectorsCount: getPortfolioSnapshotSectorCount(portfolioSnapshot),
      grossExposureDelta: getPortfolioSnapshotGrossExposure(portfolioSnapshot),
      netCapitalDelta: getPortfolioSnapshotNetCapital(portfolioSnapshot),
    },
    portfolioSnapshot,
  }
  const draft: WorkingDraft = {
    id: draftId,
    workspaceId,
    baseNodeId: rootNodeId,
    updatedAt: importedAt,
    name: 'Working Draft',
    status: 'clean',
    portfolioSnapshot: clonePortfolioSnapshot(portfolioSnapshot),
  }
  const workspaceState: WorkspaceState = {
    workspaceId,
    activeNodeId: rootNodeId,
    activeDraftId: draftId,
    selectedExposureSnapshotId: 'draft',
    lastOpenedAt: importedAt,
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName, workingDraftStoreName, workspaceStateStoreName, appStateStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(workspace)
    transaction.objectStore(portfolioNodeStoreName).put(rootNode)
    transaction.objectStore(workingDraftStoreName).put(draft)
    transaction.objectStore(workspaceStateStoreName).put(workspaceState)
    const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId })
    pointerRequest.onsuccess = () => resolve({ workspace, rootNode, draft, workspaceState })
    pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to save workspace pointer'))
  })

  return { workspace, rootNode, draft, workspaceState }
}

export async function savePersistedConstructionArtifactWorkspaceReview(review: PersistedConstructionArtifactWorkspaceReview) {
  const normalizedReview = {
    ...review,
    replay: normalizeConstructionArtifactReplayResponse(review.replay),
  }
  await withStore<void>(persistedConstructionArtifactReviewStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(normalizedReview)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save persisted construction artifact review'))
  })
}

export async function getPersistedConstructionArtifactWorkspaceReview(workspaceId: string) {
  return withStore<PersistedConstructionArtifactWorkspaceReview | null>(persistedConstructionArtifactReviewStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => {
      const review = (request.result as PersistedConstructionArtifactWorkspaceReview | undefined) ?? null
      resolve(review ? { ...review, replay: normalizeConstructionArtifactReplayResponse(review.replay) } : null)
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load persisted construction artifact review'))
  })
}

export async function savePersistedOptimizerHandoffWorkspaceReview(review: PersistedOptimizerHandoffWorkspaceReview) {
  const canonicalReview = canonicalizePersistedOptimizerHandoffReviewForWrite(review)
  await withStore<void>(persistedOptimizerHandoffReviewStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(canonicalReview)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save persisted optimizer handoff review'))
  })
}

export async function getPersistedOptimizerHandoffWorkspaceReview(workspaceId: string) {
  return withStore<PersistedOptimizerHandoffWorkspaceReview | null>(persistedOptimizerHandoffReviewStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => {
      try {
        const review = (request.result as PersistedOptimizerHandoffWorkspaceReview | undefined) ?? null
        resolve(review ? toCanonicalPersistedOptimizerHandoffReview(review) : null)
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load persisted optimizer handoff review'))
  })
}

export async function createWorkspaceFromPersistedConstructionArtifact(input: {
  constructionArtifactId: string
  openedAt?: string
  replay: ConstructionArtifactReplayResponse
}): Promise<{ workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: null; workspaceState: WorkspaceState; review: PersistedConstructionArtifactWorkspaceReview }> {
  const openedAt = input.openedAt ?? new Date().toISOString()
  const replay = normalizeConstructionArtifactReplayResponse(input.replay)
  const workspaceId = createId('workspace')
  const rootNodeId = createId('node')
  const reviewBasis = buildDesktopArtifactReviewBasis({
    constructionArtifactId: input.constructionArtifactId,
    openedAt,
    replay,
  })
  const workspace: PortfolioWorkspace = {
    id: workspaceId,
    name: `Construction Artifact ${input.constructionArtifactId}`,
    createdAt: openedAt,
    updatedAt: openedAt,
    rootNodeId,
    activeNodeId: rootNodeId,
    source: {
      kind: 'persisted_construction_artifact',
      constructionArtifactId: input.constructionArtifactId,
      openedAt,
      reviewBasis,
    },
  }
  const rootNode: PortfolioNode = {
    id: rootNodeId,
    workspaceId,
    parentId: null,
    kind: 'artifact_review_basis',
    name: 'Artifact Review Basis',
    createdAt: openedAt,
    changeSummary: {
      label: 'Artifact Review Basis',
      changedPositionsCount: replay.candidate_weights.length,
      changedSectorsCount: 0,
      grossExposureDelta: null,
      netCapitalDelta: null,
    },
    portfolioSnapshot: null,
    artifactReviewBasis: reviewBasis,
  }
  const workspaceState: WorkspaceState = {
    workspaceId,
    activeNodeId: rootNodeId,
    activeDraftId: null,
    selectedExposureSnapshotId: rootNodeId,
    lastOpenedAt: openedAt,
  }
  const review: PersistedConstructionArtifactWorkspaceReview = {
    workspaceId,
    constructionArtifactId: input.constructionArtifactId,
    openedAt,
    replay,
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName, workspaceStateStoreName, appStateStoreName, persistedConstructionArtifactReviewStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(workspace)
    transaction.objectStore(portfolioNodeStoreName).put(rootNode)
    transaction.objectStore(workspaceStateStoreName).put(workspaceState)
    transaction.objectStore(persistedConstructionArtifactReviewStoreName).put(review)
    const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId })
    pointerRequest.onsuccess = () => resolve({ workspace, rootNode, draft: null, workspaceState, review })
    pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to save workspace pointer'))
  })

  return { workspace, rootNode, draft: null, workspaceState, review }
}

export async function createWorkspaceFromPersistedOptimizerHandoff(input: {
  handoffReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference']
  openedAt?: string
  validation: OptimizerHandoffValidationResponse
  replay: OptimizerHandoffReplayResponse
}): Promise<{ workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: null; workspaceState: WorkspaceState; review: PersistedOptimizerHandoffWorkspaceReview }> {
  const openedAt = input.openedAt ?? new Date().toISOString()
  const workspaceId = createId('workspace')
  const rootNodeId = createId('node')
  const { workspace, rootNode, workspaceState, review } = buildPersistedOptimizerHandoffWorkspaceRecords({
    workspaceId,
    rootNodeId,
    handoffReference: input.handoffReference,
    openedAt,
    validation: input.validation,
    replay: input.replay,
  })

  await withStores([workspaceStoreName, portfolioNodeStoreName, workspaceStateStoreName, appStateStoreName, persistedOptimizerHandoffReviewStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(workspace)
    transaction.objectStore(portfolioNodeStoreName).put(rootNode)
    transaction.objectStore(workspaceStateStoreName).put(workspaceState)
    transaction.objectStore(persistedOptimizerHandoffReviewStoreName).put(review)
    const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId })
    pointerRequest.onsuccess = () => resolve({ workspace, rootNode, draft: null, workspaceState, review })
    pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to save workspace pointer'))
  })

  return { workspace, rootNode, draft: null, workspaceState, review }
}

export async function getWorkspace(workspaceId: string) {
  return withStore<PortfolioWorkspace | null>(workspaceStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => resolve((request.result as PortfolioWorkspace | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace'))
  })
}

export async function getNode(nodeId: string) {
  return withStore<PortfolioNode | null>(portfolioNodeStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(nodeId)
    request.onsuccess = () => resolve((request.result as PortfolioNode | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load node'))
  })
}

export async function getWorkspaceNodes(workspaceId: string) {
  return withStore<PortfolioNode[]>(portfolioNodeStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => resolve((request.result as PortfolioNode[]) ?? [])
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace nodes'))
  })
}

export async function getDraft(workspaceId: string) {
  return withStore<WorkingDraft | null>(workingDraftStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => resolve(((request.result as WorkingDraft[] | undefined) ?? [])[0] ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load draft'))
  })
}

export async function saveDraft(draft: WorkingDraft) {
  await withStore<void>(workingDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(draft)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save draft'))
  })
}

export async function getCandidateImprovementDraft(draftId: string) {
  return withStore<CandidateImprovementDraftArtifact | null>(candidateImprovementDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as CandidateImprovementDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load candidate improvement draft'))
  })
}

export async function saveCandidateImprovementDraft(annotation: CandidateImprovementDraftArtifact) {
  await withStore<void>(candidateImprovementDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save candidate improvement draft'))
  })
}

export async function deleteCandidateImprovementDraft(draftId: string) {
  await withStore<void>(candidateImprovementDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete candidate improvement draft'))
  })
}

export async function getIntentBoundSeededEtfReplacementRankingDraft(draftId: string) {
  return withStore<IntentBoundSeededEtfReplacementRankingDraftArtifact | null>(intentBoundSeededEtfReplacementRankingDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as IntentBoundSeededEtfReplacementRankingDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load intent-bound seeded ETF replacement ranking draft'))
  })
}

export async function saveIntentBoundSeededEtfReplacementRankingDraft(annotation: IntentBoundSeededEtfReplacementRankingDraftArtifact) {
  await withStore<void>(intentBoundSeededEtfReplacementRankingDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save intent-bound seeded ETF replacement ranking draft'))
  })
}

export async function deleteIntentBoundSeededEtfReplacementRankingDraft(draftId: string) {
  await withStore<void>(intentBoundSeededEtfReplacementRankingDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete intent-bound seeded ETF replacement ranking draft'))
  })
}

export async function getReplacementIntentDraft(draftId: string) {
  return withStore<ReplacementIntentDraftArtifact | null>(replacementIntentDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as ReplacementIntentDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load replacement intent draft'))
  })
}

export async function getFormedCandidateArtifact(draftId: string) {
  return withStore<FormedCandidateArtifact | null>(formedCandidateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as FormedCandidateArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load formed candidate artifact'))
  })
}

export async function saveFormedCandidateArtifact(annotation: FormedCandidateArtifact) {
  await withStore<void>(formedCandidateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save formed candidate artifact'))
  })
}

export async function deleteFormedCandidateArtifact(draftId: string) {
  await withStore<void>(formedCandidateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete formed candidate artifact'))
  })
}

export async function getConstructedCandidateArtifact(draftId: string) {
  return withStore<ConstructedCandidateArtifact | null>(constructedCandidateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as ConstructedCandidateArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load constructed candidate artifact'))
  })
}

export async function saveConstructedCandidateArtifact(annotation: ConstructedCandidateArtifact) {
  await withStore<void>(constructedCandidateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save constructed candidate artifact'))
  })
}

export async function getConstructionConstraintValidationArtifact(draftId: string) {
  return withStore<ConstructionConstraintValidationArtifact | null>(constructionConstraintValidationStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as ConstructionConstraintValidationArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load construction constraint validation artifact'))
  })
}

export async function saveConstructionConstraintValidationArtifact(annotation: ConstructionConstraintValidationArtifact) {
  await withStore<void>(constructionConstraintValidationStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save construction constraint validation artifact'))
  })
}

export async function deleteConstructionConstraintValidationArtifact(draftId: string) {
  await withStore<void>(constructionConstraintValidationStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete construction constraint validation artifact'))
  })
}

export async function deleteConstructedCandidateArtifact(draftId: string) {
  await withStore<void>(constructedCandidateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete constructed candidate artifact'))
  })
}

export async function getSelectedConstructionRule(draftId: string) {
  return withStore<SelectedConstructionRuleArtifact | null>(selectedConstructionRuleStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as SelectedConstructionRuleArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load selected construction rule'))
  })
}

export async function saveSelectedConstructionRule(annotation: SelectedConstructionRuleArtifact) {
  await withStore<void>(selectedConstructionRuleStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save selected construction rule'))
  })
}

export async function deleteSelectedConstructionRule(draftId: string) {
  await withStore<void>(selectedConstructionRuleStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete selected construction rule'))
  })
}

export async function saveReplacementIntentDraft(annotation: ReplacementIntentDraftArtifact) {
  await withStore<void>(replacementIntentDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save replacement intent draft'))
  })
}

export async function deleteReplacementIntentDraft(draftId: string) {
  await withStore<void>(replacementIntentDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete replacement intent draft'))
  })
}

export async function getHypotheticalReplacementReplayDraft(draftId: string) {
  return withStore<HypotheticalReplacementReplayDraftArtifact | null>(hypotheticalReplacementReplayDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as HypotheticalReplacementReplayDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load hypothetical replay draft'))
  })
}

export async function saveHypotheticalReplacementReplayDraft(annotation: HypotheticalReplacementReplayDraftArtifact) {
  await withStore<void>(hypotheticalReplacementReplayDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save hypothetical replay draft'))
  })
}

export async function deleteHypotheticalReplacementReplayDraft(draftId: string) {
  await withStore<void>(hypotheticalReplacementReplayDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete hypothetical replay draft'))
  })
}

export async function getWorkspaceProposalArtifacts(workspaceId: string) {
  return withStore<VersionedProposalArtifact[]>(versionedProposalStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => {
      try {
        resolve((((request.result as VersionedProposalArtifact[] | undefined) ?? []).map(assertSavedProposalArtifactIntegrity)).sort((left, right) => right.versionNumber - left.versionNumber || right.createdAt.localeCompare(left.createdAt)))
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load proposal artifacts'))
  })
}

export async function saveProposalArtifact(proposal: VersionedProposalArtifact) {
  assertSavedProposalArtifactIntegrity(proposal)
  await withStore<void>(versionedProposalStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(proposal)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save proposal artifact'))
  })
}

export async function getActiveThesis(workspaceId: string) {
  return withStore<ActiveThesisArtifact | null>(activeThesisStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => {
      try {
        const thesis = (request.result as ActiveThesisArtifact | undefined) ?? null
        if (!thesis) {
          resolve(null)
          return
        }
        thesis.thesisProposal = assertSavedProposalArtifactIntegrity(thesis.thesisProposal)
        resolve(thesis)
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load active thesis'))
  })
}

export async function saveActiveThesis(thesis: ActiveThesisArtifact) {
  thesis.thesisProposal = assertSavedProposalArtifactIntegrity(thesis.thesisProposal)
  await withStore<void>(activeThesisStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(thesis)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save active thesis'))
  })
}

export async function deleteActiveThesis(workspaceId: string) {
  await withStore<void>(activeThesisStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(workspaceId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete active thesis'))
  })
}

export async function createDraftFromNode(input: { workspaceId: string; baseNodeId: string; name?: string }) {
  const node = await getNode(input.baseNodeId)
  if (!node) throw new Error('Base node not found')
  if (!node.portfolioSnapshot) throw new Error('Base node does not contain a portfolio snapshot')
  const existingDraft = await getDraft(input.workspaceId)
  const draft: WorkingDraft = {
    id: existingDraft?.id ?? createId('draft'),
    workspaceId: input.workspaceId,
    baseNodeId: input.baseNodeId,
    updatedAt: new Date().toISOString(),
    name: input.name ?? 'Working Draft',
    status: 'clean',
    portfolioSnapshot: clonePortfolioSnapshot(node.portfolioSnapshot),
  }
  await saveDraft(draft)
  await deleteCandidateImprovementDraft(draft.id)
  await deleteIntentBoundSeededEtfReplacementRankingDraft(draft.id)
  await deleteReplacementIntentDraft(draft.id)
  await deleteFormedCandidateArtifact(draft.id)
  await deleteConstructedCandidateArtifact(draft.id)
  await deleteConstructionConstraintValidationArtifact(draft.id)
  await deleteSelectedConstructionRule(draft.id)
  await deleteHypotheticalReplacementReplayDraft(draft.id)
  return draft
}

export async function discardDraft(workspaceId: string) {
  const state = await getWorkspaceState(workspaceId)
  if (!state) return null
  return createDraftFromNode({ workspaceId, baseNodeId: state.activeNodeId })
}

export async function getWorkspaceState(workspaceId: string) {
  return withStore<WorkspaceState | null>(workspaceStateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => resolve((request.result as WorkspaceState | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace state'))
  })
}

export async function setActiveNode(input: { workspaceId: string; nodeId: string; createDraftFromNode?: boolean }) {
  const state = (await getWorkspaceState(input.workspaceId)) ?? {
    workspaceId: input.workspaceId,
    activeNodeId: input.nodeId,
    activeDraftId: null,
    lastOpenedAt: new Date().toISOString(),
  }
  const draft = input.createDraftFromNode === false ? null : await createDraftFromNode({ workspaceId: input.workspaceId, baseNodeId: input.nodeId })
  const nextState: WorkspaceState = {
    ...state,
    activeNodeId: input.nodeId,
    activeDraftId: draft?.id ?? null,
    selectedExposureSnapshotId: draft ? 'draft' : input.nodeId,
    lastOpenedAt: new Date().toISOString(),
  }

  await withStores([workspaceStateStoreName, workspaceStoreName, appStateStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStateStoreName).put(nextState)

    const workspaceStore = transaction.objectStore(workspaceStoreName)
    const workspaceRequest = workspaceStore.get(input.workspaceId)
    workspaceRequest.onsuccess = () => {
      const workspace = workspaceRequest.result as PortfolioWorkspace | undefined
      if (workspace) {
        workspaceStore.put({ ...workspace, activeNodeId: input.nodeId, updatedAt: nextState.lastOpenedAt })
      }
      const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId: input.workspaceId })
      pointerRequest.onsuccess = () => resolve(nextState)
      pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to update active workspace pointer'))
    }
    workspaceRequest.onerror = () => reject(workspaceRequest.error ?? new Error('Failed to load workspace for active node update'))
  })

  return nextState
}

export async function setSelectedExposureSnapshot(input: { workspaceId: string; snapshotId: string }) {
  const state = await getWorkspaceState(input.workspaceId)
  if (!state) return null

  const nextState: WorkspaceState = {
    ...state,
    selectedExposureSnapshotId: input.snapshotId,
    lastOpenedAt: new Date().toISOString(),
  }

  await withStore<void>(workspaceStateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(nextState)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to persist selected exposure snapshot'))
  })

  return nextState
}

export async function saveVariantFromDraft(input: { workspaceId: string; draftId: string; variantName: string }) {
  const draft = await getDraft(input.workspaceId)
  if (!draft || draft.id !== input.draftId) throw new Error('Draft not found')
  const baseNode = await getNode(draft.baseNodeId)
  if (!baseNode) throw new Error('Base node not found')
  if (!baseNode.portfolioSnapshot) throw new Error('Base node snapshot not found')

  const node: PortfolioNode = {
    id: createId('node'),
    workspaceId: input.workspaceId,
    parentId: draft.baseNodeId,
    kind: 'variant',
    name: input.variantName,
    createdAt: new Date().toISOString(),
    changeSummary: createChangeSummary(baseNode.portfolioSnapshot, draft.portfolioSnapshot, input.variantName),
    portfolioSnapshot: clonePortfolioSnapshot(draft.portfolioSnapshot),
  }

  await withStore<void>(portfolioNodeStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(node)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save portfolio node'))
  })

  const workspaceState = await setActiveNode({ workspaceId: input.workspaceId, nodeId: node.id, createDraftFromNode: true })
  const workspace = await getWorkspace(input.workspaceId)
  if (!workspace) throw new Error('Workspace not found after saving variant')
  return { node, workspace, workspaceState }
}

export async function saveImportedSnapshotNode(input: {
  workspaceId: string
  parentNodeId: string
  portfolioSnapshot: PortfolioSnapshot
  importedFileNames: string[]
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
  name: string
}) {
  const workspace = await getWorkspace(input.workspaceId)
  if (!workspace) throw new Error('Workspace not found')

  const parentNode = await getNode(input.parentNodeId)
  if (!parentNode) throw new Error('Parent node not found')
  if (!parentNode.portfolioSnapshot) throw new Error('Parent node snapshot not found')

  const source: ImportedNodeSource = buildPersistedImportedSource({
    importedFileNames: input.importedFileNames,
    importedAt: input.portfolioSnapshot.importedMeta.importedAt,
    importer: input.portfolioSnapshot.importedMeta.importer,
    baseCurrency: input.portfolioSnapshot.baseCurrency,
    historyContext: input.historyContext ?? null,
    importedHistorySnapshot: input.importedHistorySnapshot ?? null,
  })

  const node: PortfolioNode = {
    id: createId('node'),
    workspaceId: input.workspaceId,
    parentId: input.parentNodeId,
    kind: 'imported_snapshot',
    name: input.name,
    createdAt: input.portfolioSnapshot.importedMeta.importedAt,
    changeSummary: createChangeSummary(parentNode.portfolioSnapshot, input.portfolioSnapshot, input.name),
    portfolioSnapshot: input.portfolioSnapshot,
    source,
  }

  await withStore<void>(portfolioNodeStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(node)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save imported snapshot node'))
  })

  const workspaceState = await setActiveNode({ workspaceId: input.workspaceId, nodeId: node.id, createDraftFromNode: true })
  const nextWorkspace = await getWorkspace(input.workspaceId)
  if (!nextWorkspace) throw new Error('Workspace not found after saving imported snapshot node')
  return { node, workspace: nextWorkspace, workspaceState }
}

export async function clearPortfolioWorkspaceState() {
  await withStores([workspaceStoreName, portfolioNodeStoreName, workingDraftStoreName, workspaceStateStoreName, appStateStoreName, candidateImprovementDraftStoreName, intentBoundSeededEtfReplacementRankingDraftStoreName, replacementIntentDraftStoreName, formedCandidateStoreName, constructedCandidateStoreName, constructionConstraintValidationStoreName, selectedConstructionRuleStoreName, hypotheticalReplacementReplayDraftStoreName, versionedProposalStoreName, activeThesisStoreName, persistedConstructionArtifactReviewStoreName, persistedOptimizerHandoffReviewStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).clear()
    transaction.objectStore(portfolioNodeStoreName).clear()
    transaction.objectStore(workingDraftStoreName).clear()
    transaction.objectStore(workspaceStateStoreName).clear()
    transaction.objectStore(candidateImprovementDraftStoreName).clear()
    transaction.objectStore(intentBoundSeededEtfReplacementRankingDraftStoreName).clear()
    transaction.objectStore(replacementIntentDraftStoreName).clear()
    transaction.objectStore(formedCandidateStoreName).clear()
    transaction.objectStore(constructedCandidateStoreName).clear()
    transaction.objectStore(constructionConstraintValidationStoreName).clear()
    transaction.objectStore(selectedConstructionRuleStoreName).clear()
    transaction.objectStore(hypotheticalReplacementReplayDraftStoreName).clear()
    transaction.objectStore(versionedProposalStoreName).clear()
    transaction.objectStore(activeThesisStoreName).clear()
    transaction.objectStore(persistedConstructionArtifactReviewStoreName).clear()
    transaction.objectStore(persistedOptimizerHandoffReviewStoreName).clear()
    const request = transaction.objectStore(appStateStoreName).delete(activeWorkspacePointerKey)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to clear workspace state'))
  })
}

export async function resetLocalPortfolioDatabase() {
  await deletePortfolioDatabase()
}

export async function getLastOpenedWorkspaceState() {
  const pointer = await withStore<{ id: string; workspaceId: string } | null>(appStateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(activeWorkspacePointerKey)
    request.onsuccess = () => resolve((request.result as { id: string; workspaceId: string } | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load active workspace pointer'))
  })
  if (!pointer) return null
  return getWorkspaceState(pointer.workspaceId)
}
