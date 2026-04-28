import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { buildExposureFactorModelResponse } from '../features/portfolio/exposureFactorModel'
import { canUseImportedReplay, collapseToHistoryContextSource, resolveEffectiveHistorySource } from '../features/portfolio/historySource'
import { projectImportedBootstrap } from '../features/portfolio/importedBootstrapMapper'
import { buildExposureFactorModel, buildPortfolioBaselineView, composeDashboardAnalysisFromEngines, composeDashboardAnalysisWithHistory, runDashboardHistoryEngine, runDiagnosticsEngine, runExposureEngine, composeExposureView, runImportedDashboardHistory, runImportedDiagnosticsEngine } from '../features/portfolio/portfolioAnalysisAdapter'
import { formatVariantNodeLabel, formatWorkingDraftLabel } from '../features/portfolio/variantLabels'
import { VariantList } from '../features/portfolio/VariantList'
import { buildPortfolioSnapshotFromAnalysis, overlayImportedSnapshot } from '../features/portfolio/portfolioSnapshot'
import { desktopFeatureFlags } from './featureFlags'
import type { ConstructionArtifactPreviewHandoff, ConstructionArtifactReplayResponse, ConstructionArtifactReplayValidationResponse, HypotheticalReplayResponse, ImportedBootstrapResponse, ImportedSnapshot, ImportedStatementImporter, BacktestRunResponse, DashboardAnalysis, DiagnosticsEngineResponse, ExposureAnalysis, ExposureFactorModelResponse, MonitoringResearchHandoff, OptimizerHandoffReplayHandoff, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse, OptimizerPersistedArtifactReference, PortfolioAllocationBacktestResponse, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from '../features/portfolio/types'
import type { ActiveThesisArtifact, CandidateImprovementDraftArtifact, CandidateImprovementSeed, ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, HypotheticalReplacementReplayDraftArtifact, ImportedHistoryContext, ImportedHistorySource, IntentBoundSeededEtfReplacementRankingDraftArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifactInput, PersistedConstructionArtifactWorkspaceReview, PersistedOptimizerHandoffWorkspaceReview, PortfolioNode, PortfolioWorkspace, ReplacementIntentDraftArtifact, ReviewSnapshotArtifact, ReviewSnapshotOpenHandoff, SelectedConstructionRuleArtifact, VersionedProposalArtifact, WorkingDraft } from '../features/portfolio/workspaceTypes'
import { assertValidReviewSnapshotOpenResponseEnvelope, buildReviewSnapshotOpenHandoffFromProposal, buildSavedProposalArtifact, clearPortfolioWorkspaceState, createWorkspaceFromImport, createWorkspaceFromPersistedConstructionArtifact, createWorkspaceFromPersistedOptimizerHandoff, deleteActiveThesis, deleteConstructionConstraintValidationArtifact, deleteConstructedCandidateArtifact, deleteFormedCandidateArtifact, deleteHypotheticalReplacementReplayDraft, deleteReplacementIntentDraft, getActiveThesis, getCandidateImprovementDraft, getConstructionConstraintValidationArtifact, getConstructedCandidateArtifact, getDraft, getFormedCandidateArtifact, getHypotheticalReplacementReplayDraft, getIntentBoundSeededEtfReplacementRankingDraft, getLastOpenedWorkspaceState, getNode, getPersistedConstructionArtifactWorkspaceReview, getPersistedOptimizerHandoffWorkspaceReview, getReplacementIntentDraft, getSelectedConstructionRule, getWorkspace, getWorkspaceNodes, getWorkspaceProposalArtifacts, isDraftDirty, normalizeLegacyPersistedConstructionArtifactWorkspaceCache, normalizeLegacyPersistedOptimizerHandoffWorkspaceCache, resetLocalPortfolioDatabase, saveActiveThesis, saveCandidateImprovementDraft, saveConstructionConstraintValidationArtifact, saveConstructedCandidateArtifact, saveDraft, saveFormedCandidateArtifact, saveHypotheticalReplacementReplayDraft, saveImportedSnapshotNode, saveIntentBoundSeededEtfReplacementRankingDraft, saveProposalArtifact, saveReplacementIntentDraft, saveReviewSnapshotArtifact, saveSelectedConstructionRule, saveVariantFromDraft, setActiveNode as persistActiveNode, setSelectedExposureSnapshot } from './portfolioWorkspaceStorage'
import { TrendRiskOverlaysPanel } from '../features/portfolio/TrendRiskOverlaysPanel'


const ExposurePanel = lazy(async () => ({ default: (await import('../features/portfolio/ExposurePanel')).ExposurePanel }))
const DashboardPanel = lazy(async () => ({ default: (await import('../features/portfolio/DashboardPanel')).DashboardPanel }))
const DiagnosticsPanel = lazy(async () => ({ default: (await import('../features/portfolio/DiagnosticsPanel')).DiagnosticsPanel }))
const BacktestWorkspacePanel = lazy(async () => ({ default: (await import('../features/backtest/BacktestWorkspacePanel')).BacktestWorkspacePanel }))
const StrategyBacktestPanel = lazy(async () => ({ default: (await import('../features/backtest/StrategyBacktestPanel')).StrategyBacktestPanel }))
const StrategyLabPanel = lazy(async () => ({ default: (await import('../features/strategy-lab/StrategyLabPanel')).StrategyLabPanel }))
const EtfRankingPanel = lazy(async () => ({ default: (await import('../features/strategy-lab/EtfRankingPanel')).EtfRankingPanel }))


const defaultSymbolOverrides = '{}'
type ImportMode = 'replace' | 'add_snapshot'
const defaultConstructionRuleId: SingleReplacementConstructionRuleId = 'same_weight_substitution_v1'
const persistedConstructionArtifactQueryKey = 'construction_artifact_id'
const persistedOptimizerHandoffReferenceQueryKey = 'optimizer_handoff_reference'
const missingPersistedOptimizerHandoffReviewRestoreMessage = 'Unable to restore previous portfolio workspace: persisted optimizer handoff review is missing'

function isImportedWorkspaceSource(source: PortfolioWorkspace['source'] | null | undefined): source is Extract<PortfolioWorkspace['source'], { importedFileNames: string[] }> {
  return Boolean(source && 'importedFileNames' in source)
}

function isPersistedConstructionArtifactWorkspaceSource(
  source: PortfolioWorkspace['source'] | null | undefined,
): source is Extract<PortfolioWorkspace['source'], { kind: 'persisted_construction_artifact' }> {
  return Boolean(source && 'kind' in source && source.kind === 'persisted_construction_artifact')
}

function isPersistedOptimizerHandoffWorkspaceSource(
  source: PortfolioWorkspace['source'] | null | undefined,
): source is Extract<PortfolioWorkspace['source'], { kind: 'persisted_optimizer_handoff' }> {
  return Boolean(source && 'kind' in source && source.kind === 'persisted_optimizer_handoff')
}

function resolveConstructionArtifactPreviewHandoff(
  validation: ConstructionArtifactReplayValidationResponse,
  expectedArtifactId: string,
): ConstructionArtifactPreviewHandoff {
  if (!validation.preview_handoff) {
    throw new Error('Unable to open persisted construction artifact review: validation response missing preview handoff')
  }
  if (validation.preview_handoff.handoff_kind !== 'construction_artifact_preview_handoff_v1') {
    throw new Error('Unable to open persisted construction artifact review: unsupported preview handoff kind')
  }
  if (validation.preview_handoff.construction_artifact_id !== expectedArtifactId) {
    throw new Error('Unable to open persisted construction artifact review: preview handoff artifact mismatch')
  }
  return validation.preview_handoff
}

function parseOptimizerHandoffReferenceParam(search: string): OptimizerPersistedArtifactReference | null {
  const raw = new URLSearchParams(search).get(persistedOptimizerHandoffReferenceQueryKey)
  if (!raw) return null

  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error('Unable to open persisted optimizer handoff review: invalid handoff reference query payload')
  }

  if (!parsed || typeof parsed !== 'object') {
    throw new Error('Unable to open persisted optimizer handoff review: invalid handoff reference query payload')
  }

  const reference = parsed as Partial<OptimizerPersistedArtifactReference>
  if (
    reference.reference_kind !== 'optimizer_handoff_reference_v1'
    || !reference.handoff_id
    || !reference.artifact_id
    || !reference.manifest_path
    || !reference.artifact_path
  ) {
    throw new Error('Unable to open persisted optimizer handoff review: incomplete handoff reference query payload')
  }

  return {
    reference_kind: 'optimizer_handoff_reference_v1',
    handoff_id: reference.handoff_id,
    artifact_id: reference.artifact_id,
    manifest_path: reference.manifest_path,
    artifact_path: reference.artifact_path,
  }
}

function assertOptimizerHandoffValidationMatchesReference(
  validation: OptimizerHandoffValidationResponse,
  handoffReference: OptimizerPersistedArtifactReference,
) {
  if (!validation.handoff_id || validation.handoff_id !== handoffReference.handoff_id) {
    throw new Error('Unable to open persisted optimizer handoff review: validation handoff mismatch')
  }
  if (validation.artifact_id && validation.artifact_id !== handoffReference.artifact_id) {
    throw new Error('Unable to open persisted optimizer handoff review: validation artifact mismatch')
  }
}

function assertOptimizerHandoffReplayMatchesReference(
  replay: OptimizerHandoffReplayResponse,
  handoffReference: OptimizerPersistedArtifactReference,
) {
  if (replay.handoff_id !== handoffReference.handoff_id) {
    throw new Error('Unable to open persisted optimizer handoff review: replay handoff mismatch')
  }
  if (replay.artifact_id !== handoffReference.artifact_id) {
    throw new Error('Unable to open persisted optimizer handoff review: replay artifact mismatch')
  }
  if (!replay.optimizer_context) {
    throw new Error('Unable to open persisted optimizer handoff review: replay optimizer context missing')
  }
  if (!replay.optimizer_context.objective) {
    throw new Error('Unable to open persisted optimizer handoff review: replay optimizer objective missing')
  }
}

function getWorkspaceImportedFileNames(workspace: PortfolioWorkspace | null, node: PortfolioNode | null) {
  if (!workspace) return []
  const nodeSource = getNodeImportSource(node, workspace)
  if (nodeSource) return nodeSource.importedFileNames
  return isImportedWorkspaceSource(workspace.source) ? workspace.source.importedFileNames : []
}

function getWorkspaceHistorySource(workspace: PortfolioWorkspace | null) {
  return workspace && isImportedWorkspaceSource(workspace.source) ? workspace.source.historySource : null
}

function getNodeHistorySource(source: Extract<PortfolioWorkspace['source'], { importedFileNames: string[] }> | null | undefined) {
  return source?.historySource ?? null
}

function isPersistedConstructionArtifactWorkspace(workspace: PortfolioWorkspace | null | undefined) {
  return isPersistedConstructionArtifactWorkspaceSource(workspace?.source)
}

function isPersistedOptimizerHandoffWorkspace(workspace: PortfolioWorkspace | null | undefined) {
  return isPersistedOptimizerHandoffWorkspaceSource(workspace?.source)
}

function formatShortBrokerName(importer: ImportedStatementImporter | null | undefined) {
  if (importer === 'freedom24') return 'FF'
  if (importer === 'espp') return 'ESPP'
  if (importer === 'multi_broker') return 'MULTI'
  return 'IB'
}

function extractStatementEndDate(snapshot: ImportedSnapshot) {
  const sortedAsOfDates = snapshot.positions
    .map((position) => position.as_of_date)
    .filter((value): value is string => Boolean(value))
    .sort()
  const explicitAsOf = sortedAsOfDates[sortedAsOfDates.length - 1]
  if (explicitAsOf) {
    return explicitAsOf
  }

  const lastStatement = snapshot.statements[snapshot.statements.length - 1] ?? null
  const period = snapshot.statement.statement_period ?? lastStatement?.statement_period ?? null
  if (period?.includes(' - ')) {
    const parts = period.split(' - ')
    return parts[parts.length - 1] ?? period
  }

  const importedAt = lastStatement?.imported_at ?? null
  return importedAt ? importedAt.slice(0, 10) : 'undated'
}

function buildImportedSnapshotName(snapshot: ImportedSnapshot) {
  return `${formatShortBrokerName(snapshot.statement.importer)} ${extractStatementEndDate(snapshot)}`
}

function getNodeImportSource(node: PortfolioNode | null, workspace: PortfolioWorkspace | null) {
  if (!node) return null
  if (isPersistedConstructionArtifactWorkspace(workspace) || isPersistedOptimizerHandoffWorkspace(workspace)) {
    return null
  }
  if (node.kind === 'imported_snapshot') {
    return node.source ?? null
  }
  if (node.kind === 'imported_base') {
    return isImportedWorkspaceSource(workspace?.source) ? workspace.source : null
  }
  return null
}

function getEffectiveNodeImportSource(node: PortfolioNode | null, nodes: PortfolioNode[], workspace: PortfolioWorkspace | null) {
  let current = node
  const nodeById = new Map(nodes.map((item) => [item.id, item]))

  while (current) {
    const directSource = getNodeImportSource(current, workspace)
    if (directSource) {
      return directSource
    }
    current = current.parentId ? (nodeById.get(current.parentId) ?? null) : null
  }

  return null
}

function getDirectNodeImportSource(node: PortfolioNode | null, workspace: PortfolioWorkspace | null) {
  return getNodeImportSource(node, workspace)
}

function mergeHistoryContext(
  baseHistoryContext: ImportedHistoryContext | null | undefined,
  importedHistoryContext: ImportedHistoryContext | null | undefined,
) {
  if (!baseHistoryContext) return importedHistoryContext ?? null
  if (!importedHistoryContext) return baseHistoryContext

  return {
    benchmarkSymbol: importedHistoryContext.benchmarkSymbol || baseHistoryContext.benchmarkSymbol,
    statementPeriod: `${baseHistoryContext.historyStartDate ?? importedHistoryContext.historyStartDate ?? ''} - ${importedHistoryContext.historyEndDate ?? baseHistoryContext.historyEndDate ?? ''}`.trim(),
    importedAt: importedHistoryContext.importedAt ?? baseHistoryContext.importedAt,
    importer: importedHistoryContext.importer ?? baseHistoryContext.importer,
    sourceFileNames: Array.from(new Set([...baseHistoryContext.sourceFileNames, ...importedHistoryContext.sourceFileNames])),
    historyStartDate: baseHistoryContext.historyStartDate ?? importedHistoryContext.historyStartDate,
    historyEndDate: importedHistoryContext.historyEndDate ?? baseHistoryContext.historyEndDate,
  }
}

function buildImportFormData(files: File[]) {
  const formData = new FormData()
  for (const file of files) {
    formData.append('statement_files', file)
  }
  formData.append('benchmark_symbol', 'SPY')
  formData.append('symbol_overrides', defaultSymbolOverrides)
  return formData
}

function resolveSelectedSnapshot(
  selectedSnapshotId: string | null | undefined,
  nodes: PortfolioNode[],
  activeNode: PortfolioNode | null,
  workingDraft: WorkingDraft | null,
) {
  if (selectedSnapshotId === 'draft' && workingDraft) {
    return { id: 'draft', snapshot: workingDraft.portfolioSnapshot }
  }

  if (selectedSnapshotId) {
    const node = nodes.find((item) => item.id === selectedSnapshotId) ?? (activeNode?.id === selectedSnapshotId ? activeNode : null)
    if (node?.portfolioSnapshot) {
      return { id: node.id, snapshot: node.portfolioSnapshot }
    }
  }

  if (workingDraft) {
    return { id: 'draft', snapshot: workingDraft.portfolioSnapshot }
  }

  if (activeNode?.portfolioSnapshot) {
    return { id: activeNode.id, snapshot: activeNode.portfolioSnapshot }
  }

  return null
}

async function loadCandidateImprovementDraftForCurrentDraft(draft: WorkingDraft | null, setCandidateImprovementDraft: (value: CandidateImprovementDraftArtifact | null) => void) {
  if (!draft) {
    setCandidateImprovementDraft(null)
    return
  }
  try {
    const annotation = await getCandidateImprovementDraft(draft.id)
    setCandidateImprovementDraft(annotation)
  } catch {
    setCandidateImprovementDraft(null)
  }
}

async function loadReplacementIntentDraftForCurrentDraft(draft: WorkingDraft | null, setReplacementIntentDraft: (value: ReplacementIntentDraftArtifact | null) => void) {
  if (!draft) {
    setReplacementIntentDraft(null)
    return
  }
  try {
    const annotation = await getReplacementIntentDraft(draft.id)
    setReplacementIntentDraft(annotation)
  } catch {
    setReplacementIntentDraft(null)
  }
}

async function loadIntentBoundSeededEtfReplacementRankingDraftForCurrentDraft(
  draft: WorkingDraft | null,
  setIntentBoundSeededEtfReplacementRankingDraft: (value: IntentBoundSeededEtfReplacementRankingDraftArtifact | null) => void,
  options?: {
    failClosed?: boolean
  },
) {
  if (!desktopFeatureFlags.intentBoundSeededEtfReplacementRanking || !draft) {
    setIntentBoundSeededEtfReplacementRankingDraft(null)
    return
  }
  try {
    const annotation = await getIntentBoundSeededEtfReplacementRankingDraft(draft.id)
    setIntentBoundSeededEtfReplacementRankingDraft(annotation)
  } catch (error) {
    const message = error instanceof Error ? error.message : ''
    const isPersistedSeededRankingValidationError = message.startsWith('Persisted seeded ranking review cache ')
    if (options?.failClosed && isPersistedSeededRankingValidationError) {
      throw error
    }
    setIntentBoundSeededEtfReplacementRankingDraft(null)
  }
}

function resolveOptimizerHandoffReplayHandoff(
  validation: OptimizerHandoffValidationResponse,
  handoffReference: OptimizerPersistedArtifactReference,
): OptimizerHandoffReplayHandoff {
  if (!validation.replay_handoff) {
    throw new Error('Unable to open persisted optimizer handoff review: validation response missing replay handoff')
  }
  if (validation.replay_handoff.handoff_kind !== 'optimizer_handoff_replay_handoff_v1') {
    throw new Error('Unable to open persisted optimizer handoff review: unsupported replay handoff kind')
  }
  const replayHandoffReference = validation.replay_handoff.handoff_reference
  if (JSON.stringify(replayHandoffReference) !== JSON.stringify(handoffReference)) {
    throw new Error('Unable to open persisted optimizer handoff review: replay handoff reference mismatch')
  }
  return validation.replay_handoff
}

function assertReviewSnapshotCreateArtifact(value: unknown): ReviewSnapshotArtifact {
  if (!value || typeof value !== 'object') {
    throw new Error('Failed to create review snapshot artifact')
  }
  const candidate = value as Partial<ReviewSnapshotArtifact>
  if (!candidate.identity || typeof candidate.identity !== 'object') {
    throw new Error('Failed to create review snapshot artifact: identity is missing')
  }
  if (candidate.identity.artifact_kind !== 'portfolio_review_snapshot') {
    throw new Error('Failed to create review snapshot artifact: unsupported artifact kind')
  }
  if (candidate.identity.schema_version !== 'review_snapshot_artifact_v1') {
    throw new Error('Failed to create review snapshot artifact: unsupported schema version')
  }
  if (candidate.identity.consumer_kind !== 'saved_hypothetical_replay_proposal') {
    throw new Error('Failed to create review snapshot artifact: unsupported consumer kind')
  }
  if (!candidate.lineage || typeof candidate.lineage !== 'object') {
    throw new Error('Failed to create review snapshot artifact: lineage is missing')
  }
  if (!candidate.source_payload || typeof candidate.source_payload !== 'object') {
    throw new Error('Failed to create review snapshot artifact: source_payload is missing')
  }
  return candidate as ReviewSnapshotArtifact
}

function assertReviewSnapshotOpenHandoffRequest(value: unknown): ReviewSnapshotOpenHandoff {
  if (!value || typeof value !== 'object') {
    throw new Error('Unable to reopen saved proposal: review snapshot open handoff is invalid')
  }
  const candidate = value as Partial<ReviewSnapshotOpenHandoff>
  if (candidate.handoff_kind !== 'review_snapshot_open_handoff_v1') {
    throw new Error('Unable to reopen saved proposal: unsupported review snapshot open handoff kind')
  }
  if (candidate.artifact_kind !== 'portfolio_review_snapshot') {
    throw new Error('Unable to reopen saved proposal: unsupported review snapshot artifact kind')
  }
  if (candidate.schema_version !== 'review_snapshot_artifact_v1') {
    throw new Error('Unable to reopen saved proposal: unsupported review snapshot schema version')
  }
  if (candidate.consumer_kind !== 'saved_hypothetical_replay_proposal') {
    throw new Error('Unable to reopen saved proposal: unsupported review snapshot consumer kind')
  }
  if (!candidate.artifact_id) {
    throw new Error('Unable to reopen saved proposal: review snapshot open handoff is missing artifact_id')
  }
  return candidate as ReviewSnapshotOpenHandoff
}

function assertReviewSnapshotOpenHandoffMatchesArtifact(handoff: ReviewSnapshotOpenHandoff, artifact: ReviewSnapshotArtifact) {
  if (handoff.artifact_id !== artifact.identity.artifact_id) {
    throw new Error('Unable to reopen saved proposal: handoff artifact_id does not match persisted artifact identity')
  }
  if (handoff.artifact_kind !== artifact.identity.artifact_kind) {
    throw new Error('Unable to reopen saved proposal: handoff artifact_kind does not match persisted artifact identity')
  }
  if (handoff.schema_version !== artifact.identity.schema_version) {
    throw new Error('Unable to reopen saved proposal: handoff schema_version does not match persisted artifact identity')
  }
  if (handoff.consumer_kind !== artifact.identity.consumer_kind) {
    throw new Error('Unable to reopen saved proposal: handoff consumer_kind does not match persisted artifact identity')
  }
}

async function loadHypotheticalReplacementReplayForCurrentDraft(
  draft: WorkingDraft | null,
  replacementIntentDraft: ReplacementIntentDraftArtifact | null,
  setHypotheticalReplacementReplay: (value: HypotheticalReplayResponse | null) => void,
) {
  if (!draft || !replacementIntentDraft) {
    setHypotheticalReplacementReplay(null)
    return
  }
  try {
    const annotation = await getHypotheticalReplacementReplayDraft(draft.id)
    if (!annotation) {
      setHypotheticalReplacementReplay(null)
      return
    }
    const sameIntent = annotation.replacementIntentCreatedAt === replacementIntentDraft.createdAt
      && annotation.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
      && annotation.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol
    setHypotheticalReplacementReplay(sameIntent ? annotation.replay : null)
  } catch {
    setHypotheticalReplacementReplay(null)
  }
}

async function loadFormedCandidateArtifactForCurrentDraft(
  draft: WorkingDraft | null,
  replacementIntentDraft: ReplacementIntentDraftArtifact | null,
  setFormedCandidateArtifact: (value: FormedCandidateArtifact | null) => void,
) {
  if (!draft || !replacementIntentDraft) {
    setFormedCandidateArtifact(null)
    return
  }
  try {
    const annotation = await getFormedCandidateArtifact(draft.id)
    if (!annotation) {
      setFormedCandidateArtifact(null)
      return
    }
    const sameIntent = annotation.replacementIntentCreatedAt === replacementIntentDraft.createdAt
      && annotation.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
      && annotation.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol
    setFormedCandidateArtifact(sameIntent ? annotation : null)
  } catch {
    setFormedCandidateArtifact(null)
  }
}

async function loadConstructedCandidateArtifactForCurrentDraft(
  draft: WorkingDraft | null,
  replacementIntentDraft: ReplacementIntentDraftArtifact | null,
  setConstructedCandidateArtifact: (value: ConstructedCandidateArtifact | null) => void,
) {
  if (!draft || !replacementIntentDraft) {
    setConstructedCandidateArtifact(null)
    return
  }
  try {
    const annotation = await getConstructedCandidateArtifact(draft.id)
    if (!annotation) {
      setConstructedCandidateArtifact(null)
      return
    }
    const sameIntent = annotation.replacementIntentCreatedAt === replacementIntentDraft.createdAt
      && annotation.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
      && annotation.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol
    setConstructedCandidateArtifact(sameIntent ? annotation : null)
  } catch {
    setConstructedCandidateArtifact(null)
  }
}

async function loadConstructionConstraintValidationArtifactForCurrentDraft(
  draft: WorkingDraft | null,
  replacementIntentDraft: ReplacementIntentDraftArtifact | null,
  selectedConstructionRuleId: SingleReplacementConstructionRuleId,
  setConstructionConstraintValidationArtifact: (value: ConstructionConstraintValidationArtifact | null) => void,
) {
  if (!draft || !replacementIntentDraft) {
    setConstructionConstraintValidationArtifact(null)
    return
  }
  try {
    const annotation = await getConstructionConstraintValidationArtifact(draft.id)
    if (!annotation) {
      setConstructionConstraintValidationArtifact(null)
      return
    }
    const sameIntent = annotation.replacementIntentCreatedAt === replacementIntentDraft.createdAt
      && annotation.replacementIntentBaseSymbol === replacementIntentDraft.baseSymbol
      && annotation.replacementIntentCandidateSymbol === replacementIntentDraft.candidateSymbol
    const sameRule = annotation.constructionRuleId === selectedConstructionRuleId
    setConstructionConstraintValidationArtifact(sameIntent && sameRule ? annotation : null)
  } catch {
    setConstructionConstraintValidationArtifact(null)
  }
}

async function loadSelectedConstructionRuleForCurrentDraft(
  draft: WorkingDraft | null,
  setSelectedConstructionRuleId: (value: SingleReplacementConstructionRuleId) => void,
) {
  if (!draft) {
    setSelectedConstructionRuleId(defaultConstructionRuleId)
    return defaultConstructionRuleId
  }
  try {
    const annotation = await getSelectedConstructionRule(draft.id)
    const resolvedRule = annotation?.selectedRuleId ?? defaultConstructionRuleId
    setSelectedConstructionRuleId(resolvedRule)
    return resolvedRule
  } catch {
    setSelectedConstructionRuleId(defaultConstructionRuleId)
    return defaultConstructionRuleId
  }
}

async function loadWorkspaceProposalArtifacts(workspace: PortfolioWorkspace | null): Promise<VersionedProposalArtifact[]> {
  if (!workspace) {
    return []
  }
  return getWorkspaceProposalArtifacts(workspace.id)
}

function formatSavedProposalRestoreFailure(error: unknown) {
  const message = error instanceof Error ? error.message : 'Unable to reopen saved proposal'
  if (message.startsWith('Unable to reopen saved proposal:')) {
    return message
  }
  return `Unable to reopen saved proposal: ${message.charAt(0).toLowerCase()}${message.slice(1)}`
}

async function reopenSavedProposalFromArtifact(
  reviewSnapshotArtifactId: string,
  proposalArtifacts: VersionedProposalArtifact[],
  setProposalArtifacts: (value: VersionedProposalArtifact[] | ((current: VersionedProposalArtifact[]) => VersionedProposalArtifact[])) => void,
  setHypotheticalReplacementReplay: (value: HypotheticalReplayResponse | null) => void,
  setWorkspaceError: (value: string | null) => void,
  setOpenedSavedProposalArtifactId: (value: string | null) => void,
) {
  if (!reviewSnapshotArtifactId) {
    throw new Error('Unable to reopen saved proposal: missing authoritative reviewSnapshotArtifactId')
  }
  const proposal = proposalArtifacts.find((item) => item.reviewSnapshotArtifactId === reviewSnapshotArtifactId) ?? null
  if (!proposal) {
    throw new Error('Unable to reopen saved proposal: persisted review snapshot artifact is not indexed by any saved proposal')
  }
  const handoff = assertReviewSnapshotOpenHandoffRequest(await buildReviewSnapshotOpenHandoffFromProposal(proposal))
  const response = await fetch('/api/backtests/review-snapshots/open', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(handoff),
  })
  const payload = await response.json()
  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail ?? 'Unable to reopen saved proposal')
  }
  const openResponse = assertValidReviewSnapshotOpenResponseEnvelope(payload)
  assertReviewSnapshotOpenHandoffMatchesArtifact(handoff, openResponse.artifact)
  if (openResponse.handoff.artifact_id !== reviewSnapshotArtifactId) {
    throw new Error('Unable to reopen saved proposal: open response artifact_id does not match requested reviewSnapshotArtifactId')
  }
  const persistedProposal = proposalArtifacts.find((item) => item.reviewSnapshotArtifactId === openResponse.handoff.artifact_id) ?? null
  if (!persistedProposal) {
    throw new Error('Unable to reopen saved proposal: persisted review snapshot artifact is not indexed by any saved proposal')
  }
  if (persistedProposal.reviewSnapshotArtifactId !== openResponse.artifact.identity.artifact_id) {
    throw new Error('Unable to reopen saved proposal: saved proposal artifact identity does not match open response artifact identity')
  }
  if (persistedProposal.id !== openResponse.artifact.lineage.proposal_id) {
    throw new Error('Unable to reopen saved proposal: saved proposal id contradicts review snapshot lineage proposal_id')
  }
  if (persistedProposal.workspaceId !== openResponse.artifact.lineage.workspace_id) {
    throw new Error('Unable to reopen saved proposal: saved proposal workspaceId contradicts review snapshot lineage workspace_id')
  }
  if (persistedProposal.sourceDraftId !== openResponse.artifact.lineage.source_draft_id) {
    throw new Error('Unable to reopen saved proposal: saved proposal sourceDraftId contradicts review snapshot lineage source_draft_id')
  }
  if (persistedProposal.sourceBaseNodeId !== openResponse.artifact.lineage.source_base_node_id) {
    throw new Error('Unable to reopen saved proposal: saved proposal sourceBaseNodeId contradicts review snapshot lineage source_base_node_id')
  }
  if (persistedProposal.proposalFamilyId !== openResponse.artifact.lineage.proposal_family_id) {
    throw new Error('Unable to reopen saved proposal: saved proposal proposalFamilyId contradicts review snapshot lineage proposal_family_id')
  }
  if (persistedProposal.versionNumber !== openResponse.artifact.lineage.version_number) {
    throw new Error('Unable to reopen saved proposal: saved proposal versionNumber contradicts review snapshot lineage version_number')
  }
  if (JSON.stringify(openResponse.handoff) !== JSON.stringify(openResponse.artifact.proposal_capture.open_handoff)) {
    throw new Error('Unable to reopen saved proposal: open response handoff contradicts review snapshot proposal_capture open_handoff')
  }
  if (JSON.stringify(persistedProposal.proposalCapture.open_handoff) !== JSON.stringify(openResponse.handoff)) {
    throw new Error('Unable to reopen saved proposal: saved proposal proposalCapture open_handoff contradicts review snapshot open handoff')
  }
  if (persistedProposal.proposalCapture.lineage.proposal_id !== openResponse.artifact.proposal_capture.lineage.proposal_id) {
    throw new Error('Unable to reopen saved proposal: saved proposal proposalCapture lineage proposal_id contradicts review snapshot proposal_capture lineage')
  }
  const authoritativeReplay = openResponse.replay_payload.overlay_replay ?? openResponse.replay_payload.replay
  if (!authoritativeReplay) {
    throw new Error('Unable to reopen saved proposal: persisted review snapshot open payload is missing authoritative replay payload')
  }
  if (JSON.stringify(authoritativeReplay) !== JSON.stringify(persistedProposal.reviewSnapshot)) {
    throw new Error('Unable to reopen saved proposal: persisted review snapshot open payload contradicts saved proposal reviewSnapshot')
  }
  setWorkspaceError(null)
  setProposalArtifacts((current) => current.map((proposal) => proposal.reviewSnapshotArtifactId === openResponse.handoff.artifact_id
    ? {
        ...proposal,
        proposalCapture: openResponse.artifact.proposal_capture,
        reviewSnapshotPMSummary: openResponse.pm_summary,
      }
    : proposal))
  setOpenedSavedProposalArtifactId(reviewSnapshotArtifactId)
  setHypotheticalReplacementReplay(authoritativeReplay)
}

async function loadActiveThesisForWorkspace(workspace: PortfolioWorkspace | null, setActiveThesis: (value: ActiveThesisArtifact | null) => void) {
  if (!workspace) {
    setActiveThesis(null)
    return
  }
  try {
    setActiveThesis(await getActiveThesis(workspace.id))
  } catch {
    setActiveThesis(null)
  }
}

export function App() {
  const [tab, setTab] = useState<'dashboard' | 'exposure' | 'diagnostics' | 'workspace' | 'backtest' | 'strategy_lab' | 'etf_ranking'>('workspace')
  const [analysis, setAnalysis] = useState<DashboardAnalysis | null>(null)
  const [baselineAnalysis, setBaselineAnalysis] = useState<ReturnType<typeof buildPortfolioBaselineView> | null>(null)
  const [exposureAnalysis, setExposureAnalysis] = useState<ExposureAnalysis | null>(null)
  const [diagnosticsAnalysis, setDiagnosticsAnalysis] = useState<DiagnosticsEngineResponse | null>(null)
  const [exposureFactorModel, setExposureFactorModel] = useState<ExposureFactorModelResponse | null>(null)
  const [backtestRun, setBacktestRun] = useState<BacktestRunResponse | null>(null)
  const [allocationBacktestRun, setAllocationBacktestRun] = useState<PortfolioAllocationBacktestResponse | null>(null)
  const [hypotheticalReplacementReplay, setHypotheticalReplacementReplay] = useState<HypotheticalReplayResponse | null>(null)
  const [importingPortfolio, setImportingPortfolio] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [workspaceError, setWorkspaceError] = useState<string | null>(null)
  const [loadedStatementFiles, setLoadedStatementFiles] = useState<File[]>([])
  const [lastImportedFileNames, setLastImportedFileNames] = useState<string[]>([])
  const [activeWorkspace, setActiveWorkspace] = useState<PortfolioWorkspace | null>(null)
  const [activeNode, setActiveNode] = useState<PortfolioNode | null>(null)
  const [workingDraft, setWorkingDraft] = useState<WorkingDraft | null>(null)
  const [workspaceNodes, setWorkspaceNodes] = useState<PortfolioNode[]>([])
  const [selectedExposureSnapshotId, setSelectedExposureSnapshotId] = useState<string>('current')
  const [restoringPortfolio, setRestoringPortfolio] = useState(true)
  const [restoredSession, setRestoredSession] = useState(false)
  const [candidateImprovementDraft, setCandidateImprovementDraft] = useState<CandidateImprovementDraftArtifact | null>(null)
  const [intentBoundSeededEtfReplacementRankingDraft, setIntentBoundSeededEtfReplacementRankingDraft] = useState<IntentBoundSeededEtfReplacementRankingDraftArtifact | null>(null)
  const [replacementIntentDraft, setReplacementIntentDraft] = useState<ReplacementIntentDraftArtifact | null>(null)
  const [formedCandidateArtifact, setFormedCandidateArtifact] = useState<FormedCandidateArtifact | null>(null)
  const [constructedCandidateArtifact, setConstructedCandidateArtifact] = useState<ConstructedCandidateArtifact | null>(null)
  const [constructionConstraintValidationArtifact, setConstructionConstraintValidationArtifact] = useState<ConstructionConstraintValidationArtifact | null>(null)
  const [selectedConstructionRuleId, setSelectedConstructionRuleId] = useState<SingleReplacementConstructionRuleId>(defaultConstructionRuleId)
  const [proposalArtifacts, setProposalArtifacts] = useState<VersionedProposalArtifact[]>([])
  const [openedSavedProposalArtifactId, setOpenedSavedProposalArtifactId] = useState<string | null>(null)
  const [activeThesis, setActiveThesis] = useState<ActiveThesisArtifact | null>(null)
  const [monitoringResearchHandoff, setMonitoringResearchHandoff] = useState<MonitoringResearchHandoff | null>(null)
  const [monitoringResearchHandoffDismissed, setMonitoringResearchHandoffDismissed] = useState(false)
  const [persistedConstructionArtifactReview, setPersistedConstructionArtifactReview] = useState<PersistedConstructionArtifactWorkspaceReview | null>(null)
  const [persistedOptimizerHandoffReview, setPersistedOptimizerHandoffReview] = useState<PersistedOptimizerHandoffWorkspaceReview | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const importModeRef = useRef<ImportMode>('replace')
  const artifactReviewMode = isPersistedConstructionArtifactWorkspace(activeWorkspace) || isPersistedOptimizerHandoffWorkspace(activeWorkspace)
  const dashboardSnapshot = workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot ?? null
  const workflowState = activeWorkspace && backtestRun ? 'Portfolio + Backtest Loaded' : activeWorkspace ? 'Portfolio Loaded' : backtestRun ? 'Backtest Loaded' : 'Workspace Empty'

  async function analyzeExposureSnapshot(
    snapshot: WorkingDraft['portfolioSnapshot'],
    snapshotId: string,
    workspaceId?: string,
    options?: {
      preserveDashboardAnalysis?: boolean
      historySource?: ImportedHistorySource | null
    },
  ) {
    const [exposure, diagnostics] = await Promise.all([
      runExposureEngine(snapshot),
      options?.historySource?.kind === 'imported_replay'
        ? runImportedDiagnosticsEngine(options.historySource.importedHistorySnapshot)
        : runDiagnosticsEngine(snapshot, options?.historySource?.historyContext ?? getWorkspaceHistorySource(activeWorkspace)?.historyContext ?? null),
    ])
    const exposureView = composeExposureView(exposure, diagnostics)
    setExposureAnalysis(exposureView)
    setDiagnosticsAnalysis(diagnostics)
    setExposureFactorModel(buildExposureFactorModel(exposureView))
    if (!options?.preserveDashboardAnalysis) {
      setAnalysis(composeDashboardAnalysisFromEngines(exposure, diagnostics))
    }
    setBaselineAnalysis(buildPortfolioBaselineView(exposure))
    setSelectedExposureSnapshotId(snapshotId)
    if (workspaceId) {
      try {
        await setSelectedExposureSnapshot({ workspaceId, snapshotId })
      } catch {
        // Keep analytics usable when local persistence is unavailable.
      }
    }
    return diagnostics
  }

  async function analyzeRestoredSnapshot(
    snapshot: WorkingDraft['portfolioSnapshot'],
    snapshotId: string,
    historySource: ImportedHistorySource | null | undefined,
    workspaceId?: string,
  ) {
    const [exposure, diagnostics, dashboardHistory] = await Promise.all([
      runExposureEngine(snapshot),
      historySource?.kind === 'imported_replay'
        ? runImportedDiagnosticsEngine(historySource.importedHistorySnapshot)
        : runDiagnosticsEngine(snapshot, historySource?.historyContext ?? null),
      historySource?.kind === 'imported_replay'
        ? runImportedDashboardHistory(historySource.importedHistorySnapshot)
        : historySource?.historyContext
        ? runDashboardHistoryEngine(snapshot, historySource.historyContext)
        : Promise.resolve(null),
    ])

    const exposureView = composeExposureView(exposure, diagnostics)
    setExposureAnalysis(exposureView)
    setDiagnosticsAnalysis(diagnostics)
    setExposureFactorModel(buildExposureFactorModel(exposureView))
    setAnalysis(
      dashboardHistory
        ? composeDashboardAnalysisWithHistory(exposure, dashboardHistory)
        : composeDashboardAnalysisFromEngines(exposure, diagnostics),
    )
    setBaselineAnalysis(buildPortfolioBaselineView(exposure))
    setSelectedExposureSnapshotId(snapshotId)
    if (workspaceId) {
      try {
        await setSelectedExposureSnapshot({ workspaceId, snapshotId })
      } catch {
        // Keep analytics usable when local persistence is unavailable.
      }
    }
    return diagnostics
  }

  useEffect(() => {
    let active = true

    void (async () => {
      const search = globalThis.location?.search ?? ''
      const constructionArtifactId = new URLSearchParams(search).get(persistedConstructionArtifactQueryKey)
      if (constructionArtifactId) {
        try {
          const validationResponse = await fetch('/api/backtests/portfolio-allocation/construction-artifact-validation', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              construction_artifact_id: constructionArtifactId,
            }),
          })
          if (!validationResponse.ok) {
            const payload = (await validationResponse.json()) as { detail?: string }
            throw new Error(payload.detail ?? 'Unable to open persisted construction artifact review')
          }
          const validation = (await validationResponse.json()) as ConstructionArtifactReplayValidationResponse
          const previewHandoff = resolveConstructionArtifactPreviewHandoff(validation, constructionArtifactId)
          const previewResponse = await fetch('/api/backtests/portfolio-allocation/construction-artifact-preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(previewHandoff),
          })
          if (!previewResponse.ok) {
            const payload = (await previewResponse.json()) as { detail?: string }
            throw new Error(payload.detail ?? 'Unable to open persisted construction artifact review')
          }
          const artifactReplay = (await previewResponse.json()) as ConstructionArtifactReplayResponse
          const created = await createWorkspaceFromPersistedConstructionArtifact({ constructionArtifactId, replay: artifactReplay })
          if (!active) return
          setActiveWorkspace(created.workspace)
          setActiveNode(created.rootNode)
          setWorkingDraft(null)
          setWorkspaceNodes([created.rootNode])
          setPersistedConstructionArtifactReview(created.review)
          setHypotheticalReplacementReplay(null)
          setProposalArtifacts([])
          setOpenedSavedProposalArtifactId(null)
          setActiveThesis(null)
          setCandidateImprovementDraft(null)
          setIntentBoundSeededEtfReplacementRankingDraft(null)
          setReplacementIntentDraft(null)
          setFormedCandidateArtifact(null)
          setConstructedCandidateArtifact(null)
          setConstructionConstraintValidationArtifact(null)
          setSelectedConstructionRuleId(defaultConstructionRuleId)
          setAnalysis(null)
          setBaselineAnalysis(null)
          setAllocationBacktestRun(artifactReplay.replay)
          setSelectedExposureSnapshotId(created.rootNode.id)
          setLastImportedFileNames([])
          setTab('workspace')
          setRestoredSession(true)
          setRestoringPortfolio(false)
          return
        } catch (caughtError) {
          if (active) {
            setImportError(caughtError instanceof Error ? caughtError.message : 'Unable to open persisted construction artifact review')
          }
          setRestoringPortfolio(false)
          return
        }
      }

      const optimizerHandoffReference = parseOptimizerHandoffReferenceParam(search)
      if (optimizerHandoffReference) {
        try {
          const validationResponse = await fetch('/api/backtests/portfolio-allocation/optimizer-handoff/constraints', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              handoff_reference: optimizerHandoffReference,
            }),
          })
          if (!validationResponse.ok) {
            const payload = (await validationResponse.json()) as { detail?: string }
            throw new Error(payload.detail ?? 'Unable to open persisted optimizer handoff review')
          }
          const validation = (await validationResponse.json()) as OptimizerHandoffValidationResponse
          if (validation.validation_status !== 'ok') {
            throw new Error(`Unable to open persisted optimizer handoff review: validation ${validation.validation_status}`)
          }
          assertOptimizerHandoffValidationMatchesReference(validation, optimizerHandoffReference)
          const replayHandoff = resolveOptimizerHandoffReplayHandoff(validation, optimizerHandoffReference)
          const previewResponse = await fetch('/api/backtests/portfolio-allocation/optimizer-handoff-preview', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(replayHandoff),
          })
          if (!previewResponse.ok) {
            const payload = (await previewResponse.json()) as { detail?: string }
            throw new Error(payload.detail ?? 'Unable to open persisted optimizer handoff review')
          }
          const handoffReplay = (await previewResponse.json()) as OptimizerHandoffReplayResponse
          assertOptimizerHandoffReplayMatchesReference(handoffReplay, optimizerHandoffReference)
          const created = await createWorkspaceFromPersistedOptimizerHandoff({ handoffReference: optimizerHandoffReference, validation, replay: handoffReplay })
          if (!active) return
          setActiveWorkspace(created.workspace)
          setActiveNode(created.rootNode)
          setWorkingDraft(null)
          setWorkspaceNodes([created.rootNode])
          setPersistedConstructionArtifactReview(null)
          setPersistedOptimizerHandoffReview(created.review)
          setHypotheticalReplacementReplay(null)
          setProposalArtifacts([])
          setOpenedSavedProposalArtifactId(null)
          setActiveThesis(null)
          setCandidateImprovementDraft(null)
          setIntentBoundSeededEtfReplacementRankingDraft(null)
          setReplacementIntentDraft(null)
          setFormedCandidateArtifact(null)
          setConstructedCandidateArtifact(null)
          setConstructionConstraintValidationArtifact(null)
          setSelectedConstructionRuleId(defaultConstructionRuleId)
          setAnalysis(null)
          setBaselineAnalysis(null)
          setAllocationBacktestRun(handoffReplay.replay)
          setSelectedExposureSnapshotId(created.rootNode.id)
          setLastImportedFileNames([])
          setTab('workspace')
          setRestoredSession(true)
          setRestoringPortfolio(false)
          return
        } catch (caughtError) {
          if (active) {
            setImportError(caughtError instanceof Error ? caughtError.message : 'Unable to open persisted optimizer handoff review')
          }
          setRestoringPortfolio(false)
          return
        }
      }

      const restoredWorkspaceState = await getLastOpenedWorkspaceState()

      if (!active || !restoredWorkspaceState) {
        return
      }

      const [workspace, node, draft] = await Promise.all([
        getWorkspace(restoredWorkspaceState.workspaceId),
        getNode(restoredWorkspaceState.activeNodeId),
        getDraft(restoredWorkspaceState.workspaceId),
      ])

      if (!active || !workspace || !node) {
        return
      }

      if (isPersistedConstructionArtifactWorkspaceSource(workspace.source)) {
        const review = await getPersistedConstructionArtifactWorkspaceReview(workspace.id)
        if (!active || !review) {
          return
        }
        const normalizedWorkspaceState = await normalizeLegacyPersistedConstructionArtifactWorkspaceCache({ workspace, node, review })
        if (!active) {
          return
        }
        const normalizedNodes = await getWorkspaceNodes(workspace.id).catch(() => [normalizedWorkspaceState.node])
        setActiveWorkspace(normalizedWorkspaceState.workspace)
        setActiveNode(normalizedWorkspaceState.node)
        setWorkingDraft(null)
        setWorkspaceNodes(normalizedNodes)
        setPersistedConstructionArtifactReview(normalizedWorkspaceState.review)
        setLastImportedFileNames([])
        setRestoredSession(true)
        setRestoringPortfolio(false)
        setAnalysis(null)
        setBaselineAnalysis(null)
        setAllocationBacktestRun(normalizedWorkspaceState.review.replay.replay)
        setHypotheticalReplacementReplay(null)
        setProposalArtifacts([])
        setOpenedSavedProposalArtifactId(null)
        setActiveThesis(null)
        setCandidateImprovementDraft(null)
        setIntentBoundSeededEtfReplacementRankingDraft(null)
        setReplacementIntentDraft(null)
        setFormedCandidateArtifact(null)
        setConstructedCandidateArtifact(null)
        setConstructionConstraintValidationArtifact(null)
        setSelectedConstructionRuleId(defaultConstructionRuleId)
        setSelectedExposureSnapshotId(normalizedWorkspaceState.node.id)
        return
      }

      if (isPersistedOptimizerHandoffWorkspaceSource(workspace.source)) {
        const review = await getPersistedOptimizerHandoffWorkspaceReview(workspace.id)
        if (!active) {
          return
        }
        if (!review) {
          setImportError(missingPersistedOptimizerHandoffReviewRestoreMessage)
          setRestoringPortfolio(false)
          return
        }
        const normalizedWorkspaceState = await normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({ workspace, node, review })
        if (!active) {
          return
        }
        const normalizedNodes = await getWorkspaceNodes(workspace.id).catch(() => [normalizedWorkspaceState.node])
        setActiveWorkspace(normalizedWorkspaceState.workspace)
        setActiveNode(normalizedWorkspaceState.node)
        setWorkingDraft(null)
        setWorkspaceNodes(normalizedNodes)
        setPersistedConstructionArtifactReview(null)
        setPersistedOptimizerHandoffReview(normalizedWorkspaceState.review)
        setLastImportedFileNames([])
        setRestoredSession(true)
        setRestoringPortfolio(false)
        setAnalysis(null)
        setBaselineAnalysis(null)
        setAllocationBacktestRun(normalizedWorkspaceState.review.replay.replay)
        setHypotheticalReplacementReplay(null)
        setProposalArtifacts([])
        setOpenedSavedProposalArtifactId(null)
        setActiveThesis(null)
        setCandidateImprovementDraft(null)
        setIntentBoundSeededEtfReplacementRankingDraft(null)
        setReplacementIntentDraft(null)
        setFormedCandidateArtifact(null)
        setConstructedCandidateArtifact(null)
        setConstructionConstraintValidationArtifact(null)
        setSelectedConstructionRuleId(defaultConstructionRuleId)
        setSelectedExposureSnapshotId(normalizedWorkspaceState.node.id)
        return
      }

      const nodes = await getWorkspaceNodes(workspace.id)
      const restoredProposalArtifacts = await loadWorkspaceProposalArtifacts(workspace).catch((error) => {
        throw new Error(formatSavedProposalRestoreFailure(error))
      })
      setActiveWorkspace(workspace)
      setActiveNode(node)
      setWorkingDraft(draft)
      setPersistedConstructionArtifactReview(null)
      setPersistedOptimizerHandoffReview(null)
      setProposalArtifacts(restoredProposalArtifacts)
      setOpenedSavedProposalArtifactId(null)
      await loadActiveThesisForWorkspace(workspace, setActiveThesis)
      await loadCandidateImprovementDraftForCurrentDraft(draft, setCandidateImprovementDraft)
      await loadIntentBoundSeededEtfReplacementRankingDraftForCurrentDraft(draft, setIntentBoundSeededEtfReplacementRankingDraft, { failClosed: true })
      const restoredSelectedConstructionRuleId = await loadSelectedConstructionRuleForCurrentDraft(draft, setSelectedConstructionRuleId)
      const restoredReplacementIntentDraft = draft ? await getReplacementIntentDraft(draft.id).catch(() => null) : null
      setReplacementIntentDraft(restoredReplacementIntentDraft)
      await loadFormedCandidateArtifactForCurrentDraft(draft, restoredReplacementIntentDraft, setFormedCandidateArtifact)
      await loadConstructedCandidateArtifactForCurrentDraft(draft, restoredReplacementIntentDraft, setConstructedCandidateArtifact)
      await loadConstructionConstraintValidationArtifactForCurrentDraft(draft, restoredReplacementIntentDraft, restoredSelectedConstructionRuleId, setConstructionConstraintValidationArtifact)
      await loadHypotheticalReplacementReplayForCurrentDraft(draft, restoredReplacementIntentDraft, setHypotheticalReplacementReplay)
      setWorkspaceNodes(nodes)
      setLastImportedFileNames(getWorkspaceImportedFileNames(workspace, node))
      setRestoredSession(true)

      const resolvedSnapshot = resolveSelectedSnapshot(restoredWorkspaceState.selectedExposureSnapshotId, nodes, node, draft)
      if (!resolvedSnapshot) return

      setSelectedExposureSnapshotId(resolvedSnapshot.id)

        if (resolvedSnapshot.snapshot.positions.length || resolvedSnapshot.snapshot.cashBalances.length) {
          const selectedNode = resolvedSnapshot.id === 'draft'
            ? (draft ? nodes.find((item) => item.id === draft.baseNodeId) ?? node : node)
            : nodes.find((item) => item.id === resolvedSnapshot.id) ?? node
          const selectedSource = getEffectiveNodeImportSource(selectedNode, nodes, workspace)
          const selectedDirectSource = getDirectNodeImportSource(selectedNode, workspace)
          await analyzeRestoredSnapshot(
            resolvedSnapshot.snapshot,
            resolvedSnapshot.id,
            resolveEffectiveHistorySource(selectedSource, selectedDirectSource) ?? getWorkspaceHistorySource(workspace) ?? null,
            workspace.id,
          )
          if (!active) return
        }
      })()
      .catch((caughtError) => {
        if (active) {
          const message = caughtError instanceof Error ? caughtError.message : 'Unable to restore previous portfolio workspace'
          if (message.startsWith('Unable to reopen saved proposal:')) {
            setImportError(message)
            setTab('dashboard')
            return
          }
          setImportError('Unable to restore previous portfolio workspace')
        }
      })
      .finally(() => {
        if (active) {
          setRestoringPortfolio(false)
        }
      })

    return () => {
      active = false
    }
  }, [])

  function openImportPicker(mode: ImportMode) {
    importModeRef.current = mode
    fileInputRef.current?.click()
  }

  function handleClearImportedSession() {
    setAnalysis(null)
    setBaselineAnalysis(null)
    setExposureAnalysis(null)
    setDiagnosticsAnalysis(null)
    setExposureFactorModel(null)
    setLoadedStatementFiles([])
    setLastImportedFileNames([])
    setActiveWorkspace(null)
    setActiveNode(null)
    setWorkingDraft(null)
    setWorkspaceNodes([])
    setSelectedExposureSnapshotId('current')
    setImportError(null)
    setRestoredSession(false)
    setCandidateImprovementDraft(null)
    setIntentBoundSeededEtfReplacementRankingDraft(null)
    setReplacementIntentDraft(null)
    setFormedCandidateArtifact(null)
    setConstructedCandidateArtifact(null)
    setConstructionConstraintValidationArtifact(null)
    setSelectedConstructionRuleId(defaultConstructionRuleId)
    setHypotheticalReplacementReplay(null)
    setProposalArtifacts([])
    setActiveThesis(null)
    setMonitoringResearchHandoff(null)
    setMonitoringResearchHandoffDismissed(false)
    setPersistedConstructionArtifactReview(null)
    setPersistedOptimizerHandoffReview(null)
    setTab('dashboard')
    void clearPortfolioWorkspaceState()
  }

  async function handleResetLocalDatabase() {
    setAnalysis(null)
    setBaselineAnalysis(null)
    setExposureAnalysis(null)
    setDiagnosticsAnalysis(null)
    setExposureFactorModel(null)
    setLoadedStatementFiles([])
    setLastImportedFileNames([])
    setActiveWorkspace(null)
    setActiveNode(null)
    setWorkingDraft(null)
    setWorkspaceNodes([])
    setSelectedExposureSnapshotId('current')
    setImportError(null)
    setRestoredSession(false)
    setCandidateImprovementDraft(null)
    setIntentBoundSeededEtfReplacementRankingDraft(null)
    setReplacementIntentDraft(null)
    setFormedCandidateArtifact(null)
    setConstructedCandidateArtifact(null)
    setConstructionConstraintValidationArtifact(null)
    setSelectedConstructionRuleId(defaultConstructionRuleId)
    setHypotheticalReplacementReplay(null)
    setProposalArtifacts([])
    setActiveThesis(null)
    setMonitoringResearchHandoff(null)
    setMonitoringResearchHandoffDismissed(false)
    setPersistedConstructionArtifactReview(null)
    setPersistedOptimizerHandoffReview(null)
    setTab('dashboard')
    await resetLocalPortfolioDatabase()
  }

  function handleSeedCandidateDraft(input: { seed: CandidateImprovementSeed; rankingArtifact: IntentBoundSeededEtfReplacementRankingDraftArtifactInput | null }) {
    if (!activeWorkspace || !workingDraft) return
    const annotation = {
      workspaceId: activeWorkspace.id,
      draftId: workingDraft.id,
      baseNodeId: workingDraft.baseNodeId,
      seed: input.seed,
    }
    setCandidateImprovementDraft(annotation)
    void saveCandidateImprovementDraft(annotation).catch(() => undefined)
    if (desktopFeatureFlags.intentBoundSeededEtfReplacementRanking && input.rankingArtifact) {
      const rankingArtifact: IntentBoundSeededEtfReplacementRankingDraftArtifact = {
        ...input.rankingArtifact,
        workspaceId: activeWorkspace.id,
        draftId: workingDraft.id,
        baseNodeId: workingDraft.baseNodeId,
      }
      setIntentBoundSeededEtfReplacementRankingDraft(rankingArtifact)
      void saveIntentBoundSeededEtfReplacementRankingDraft(rankingArtifact).catch(() => undefined)
    }
    setTab('workspace')
  }

  function handleCreateReplacementIntent() {
    if (!activeWorkspace || !workingDraft || !candidateImprovementDraft) return
    const intent: ReplacementIntentDraftArtifact = {
      kind: 'etf_replacement_intent',
      source: 'candidate_seed',
      createdAt: new Date().toISOString(),
      draftId: workingDraft.id,
      workspaceId: activeWorkspace.id,
      baseNodeId: workingDraft.baseNodeId,
      baseSymbol: candidateImprovementDraft.seed.baseSymbol,
      candidateSymbol: candidateImprovementDraft.seed.candidateSymbol,
      seededFromDraftId: candidateImprovementDraft.draftId,
      seedRankingId: candidateImprovementDraft.seed.rankingId,
      seedMethodologyId: candidateImprovementDraft.seed.methodologyId,
      seedRankingBasisDate: candidateImprovementDraft.seed.rankingBasisDate,
      peerGroup: candidateImprovementDraft.seed.peerGroup,
      benchmarkSymbol: candidateImprovementDraft.seed.benchmarkSymbol,
      lookbackMonths: candidateImprovementDraft.seed.lookbackMonths,
      confidence: candidateImprovementDraft.seed.confidence,
      holdingsSupport: candidateImprovementDraft.seed.holdingsSupport,
      warningCount: candidateImprovementDraft.seed.warningCount,
    }
    setReplacementIntentDraft(intent)
    setFormedCandidateArtifact(null)
    setConstructedCandidateArtifact(null)
    setConstructionConstraintValidationArtifact(null)
    setHypotheticalReplacementReplay(null)
    void saveReplacementIntentDraft(intent).catch(() => undefined)
    void deleteFormedCandidateArtifact(workingDraft.id).catch(() => undefined)
    void deleteConstructedCandidateArtifact(workingDraft.id).catch(() => undefined)
    void deleteConstructionConstraintValidationArtifact(workingDraft.id).catch(() => undefined)
    if (workingDraft) {
      void deleteHypotheticalReplacementReplayDraft(workingDraft.id).catch(() => undefined)
    }
  }

  function handleClearReplacementIntent() {
    if (!workingDraft) return
    setReplacementIntentDraft(null)
    setFormedCandidateArtifact(null)
    setConstructedCandidateArtifact(null)
    setConstructionConstraintValidationArtifact(null)
    setHypotheticalReplacementReplay(null)
    void deleteReplacementIntentDraft(workingDraft.id).catch(() => undefined)
    void deleteFormedCandidateArtifact(workingDraft.id).catch(() => undefined)
    void deleteConstructedCandidateArtifact(workingDraft.id).catch(() => undefined)
    void deleteConstructionConstraintValidationArtifact(workingDraft.id).catch(() => undefined)
    void deleteHypotheticalReplacementReplayDraft(workingDraft.id).catch(() => undefined)
  }

  function handlePreviewHypotheticalReplay() {
    setTab('workspace')
  }

  function handleReviewMonitoringInResearch(handoff: MonitoringResearchHandoff) {
    setMonitoringResearchHandoff(handoff)
    setMonitoringResearchHandoffDismissed(false)
    setTab('workspace')
  }

  function handleDismissMonitoringResearchHandoff() {
    setMonitoringResearchHandoffDismissed(true)
  }

  async function handleSaveProposal() {
    if (!activeWorkspace || !workingDraft || !replacementIntentDraft || !hypotheticalReplacementReplay) return
    setWorkspaceError(null)
    const existingProposals = await getWorkspaceProposalArtifacts(activeWorkspace.id).catch(() => proposalArtifacts)
    try {
      const reviewSnapshotResponse = await fetch('/api/backtests/review-snapshots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          proposal_id: `proposal_${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`,
          workspace_id: activeWorkspace.id,
          source_draft_id: workingDraft.id,
          source_base_node_id: workingDraft.baseNodeId,
          proposal_family_id: `${replacementIntentDraft.kind}:${replacementIntentDraft.baseSymbol}:${replacementIntentDraft.candidateSymbol}:${replacementIntentDraft.createdAt}`,
          version_number: existingProposals.length + 1,
          review_payload: hypotheticalReplacementReplay,
        }),
      })
      if (!reviewSnapshotResponse.ok) {
        const payload = (await reviewSnapshotResponse.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Failed to create review snapshot artifact')
      }
      const reviewSnapshotArtifact = assertReviewSnapshotCreateArtifact(await reviewSnapshotResponse.json())
      const proposal = buildSavedProposalArtifact({
        id: reviewSnapshotArtifact.lineage.proposal_id,
        createdAt: new Date().toISOString(),
        workspaceId: activeWorkspace.id,
        sourceDraftId: workingDraft.id,
        sourceBaseNodeId: workingDraft.baseNodeId,
        proposalFamilyId: reviewSnapshotArtifact.lineage.proposal_family_id,
        versionNumber: reviewSnapshotArtifact.lineage.version_number,
        sourceIntent: replacementIntentDraft,
        proposalCapture: reviewSnapshotArtifact.proposal_capture,
        reviewSnapshotArtifactId: reviewSnapshotArtifact.identity.artifact_id,
        reviewSnapshotPMSummary: reviewSnapshotArtifact.pm_summary,
        hypotheticalReplay: hypotheticalReplacementReplay,
      })
      await saveReviewSnapshotArtifact({
        id: proposal.id,
        workspaceId: activeWorkspace.id,
        reviewSnapshotArtifactId: reviewSnapshotArtifact.identity.artifact_id,
        artifact: reviewSnapshotArtifact,
      })
      await saveProposalArtifact(proposal)
      setProposalArtifacts([proposal, ...existingProposals])
      setOpenedSavedProposalArtifactId(reviewSnapshotArtifact.identity.artifact_id)
    } catch (caughtError) {
      setWorkspaceError(caughtError instanceof Error ? caughtError.message : 'Failed to save proposal artifact')
    }
  }

  async function handleOpenSavedProposal(reviewSnapshotArtifactId: string) {
    try {
      await reopenSavedProposalFromArtifact(
        reviewSnapshotArtifactId,
        proposalArtifacts,
        setProposalArtifacts,
        setHypotheticalReplacementReplay,
        setWorkspaceError,
        setOpenedSavedProposalArtifactId,
      )
      setTab('workspace')
    } catch (caughtError) {
      setWorkspaceError(caughtError instanceof Error ? caughtError.message : 'Unable to reopen saved proposal')
    }
  }

  async function handlePromoteProposalToThesis(proposalId: string) {
    if (!activeWorkspace) return
    const proposal = proposalArtifacts.find((item) => item.id === proposalId)
    if (!proposal) return
    const thesis: ActiveThesisArtifact = {
      workspaceId: activeWorkspace.id,
      promotedAt: new Date().toISOString(),
      sourceProposalId: proposal.id,
      thesisProposal: proposal,
    }
    setActiveThesis(thesis)
    await saveActiveThesis(thesis).catch(() => {
      setActiveThesis(null)
    })
  }

  async function handleClearActiveThesis() {
    if (!activeWorkspace) return
    setActiveThesis(null)
    await deleteActiveThesis(activeWorkspace.id).catch(() => undefined)
  }

  async function handlePreviewExposure(snapshot: WorkingDraft['portfolioSnapshot']) {
    if (!activeWorkspace) return
    await analyzeExposureSnapshot(snapshot, 'draft', activeWorkspace?.id)
    setTab('exposure')
  }

  async function handleDraftSnapshotChange(snapshot: WorkingDraft['portfolioSnapshot']) {
    if (!workingDraft || !activeNode) return
    if (!activeNode.portfolioSnapshot) return
    const nextDraft: WorkingDraft = {
      ...workingDraft,
      updatedAt: new Date().toISOString(),
      portfolioSnapshot: snapshot,
      status: isDraftDirty(activeNode.portfolioSnapshot, snapshot) ? 'dirty' : 'clean',
    }
    setWorkingDraft(nextDraft)
    await saveDraft(nextDraft)
  }

  async function handleDiscardDraft() {
    if (!activeWorkspace) return
    if (!activeNode) return
    await persistActiveNode({ workspaceId: activeWorkspace.id, nodeId: activeNode.id, createDraftFromNode: true })
    const [nextWorkspace, nextNodes, nextDraft] = await Promise.all([
      getWorkspace(activeWorkspace.id),
      getWorkspaceNodes(activeWorkspace.id),
      getDraft(activeWorkspace.id),
    ])
    if (nextWorkspace) {
      setActiveWorkspace(nextWorkspace)
    }
    setWorkspaceNodes(nextNodes)
    setWorkingDraft(nextDraft)
    setCandidateImprovementDraft(null)
    setIntentBoundSeededEtfReplacementRankingDraft(null)
    setReplacementIntentDraft(null)
    setFormedCandidateArtifact(null)
    setConstructedCandidateArtifact(null)
    setConstructionConstraintValidationArtifact(null)
    setSelectedConstructionRuleId(defaultConstructionRuleId)
    setHypotheticalReplacementReplay(null)
    await loadActiveThesisForWorkspace(nextWorkspace, setActiveThesis)
  }

  async function handleSaveVariant(variantName: string) {
    if (!activeWorkspace || !workingDraft) return
    const saved = await saveVariantFromDraft({ workspaceId: activeWorkspace.id, draftId: workingDraft.id, variantName })
    const [nextNode, nextDraft] = await Promise.all([getNode(saved.node.id), getDraft(activeWorkspace.id)])
    setActiveWorkspace(saved.workspace)
    setActiveNode(nextNode)
    setWorkingDraft(nextDraft)
    await loadActiveThesisForWorkspace(saved.workspace, setActiveThesis)
    await loadCandidateImprovementDraftForCurrentDraft(nextDraft, setCandidateImprovementDraft)
    await loadIntentBoundSeededEtfReplacementRankingDraftForCurrentDraft(nextDraft, setIntentBoundSeededEtfReplacementRankingDraft)
    const nextSelectedConstructionRuleId = await loadSelectedConstructionRuleForCurrentDraft(nextDraft, setSelectedConstructionRuleId)
    const nextReplacementIntentDraft = nextDraft ? await getReplacementIntentDraft(nextDraft.id).catch(() => null) : null
    setReplacementIntentDraft(nextReplacementIntentDraft)
    await loadFormedCandidateArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, setFormedCandidateArtifact)
    await loadConstructedCandidateArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, setConstructedCandidateArtifact)
    await loadConstructionConstraintValidationArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, nextSelectedConstructionRuleId, setConstructionConstraintValidationArtifact)
    await loadHypotheticalReplacementReplayForCurrentDraft(nextDraft, nextReplacementIntentDraft, setHypotheticalReplacementReplay)
    setWorkspaceNodes(await getWorkspaceNodes(activeWorkspace.id))
    if (nextDraft) {
      await analyzeExposureSnapshot(nextDraft.portfolioSnapshot, 'draft', activeWorkspace.id)
    }
  }

  async function handleOpenNode(nodeId: string) {
    if (!activeWorkspace) return
    await persistActiveNode({ workspaceId: activeWorkspace.id, nodeId, createDraftFromNode: true })
    const [nextWorkspace, nextNodes, nextNode, nextDraft] = await Promise.all([getWorkspace(activeWorkspace.id), getWorkspaceNodes(activeWorkspace.id), getNode(nodeId), getDraft(activeWorkspace.id)])
    if (nextWorkspace) {
      setActiveWorkspace(nextWorkspace)
    }
    setWorkspaceNodes(nextNodes)
    setActiveNode(nextNode)
    setWorkingDraft(nextDraft)
    await loadActiveThesisForWorkspace(nextWorkspace ?? activeWorkspace, setActiveThesis)
    await loadCandidateImprovementDraftForCurrentDraft(nextDraft, setCandidateImprovementDraft)
    await loadIntentBoundSeededEtfReplacementRankingDraftForCurrentDraft(nextDraft, setIntentBoundSeededEtfReplacementRankingDraft)
    const nextSelectedConstructionRuleId = await loadSelectedConstructionRuleForCurrentDraft(nextDraft, setSelectedConstructionRuleId)
    const nextReplacementIntentDraft = nextDraft ? await getReplacementIntentDraft(nextDraft.id).catch(() => null) : null
    setReplacementIntentDraft(nextReplacementIntentDraft)
    await loadFormedCandidateArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, setFormedCandidateArtifact)
    await loadConstructedCandidateArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, setConstructedCandidateArtifact)
    await loadConstructionConstraintValidationArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, nextSelectedConstructionRuleId, setConstructionConstraintValidationArtifact)
    await loadHypotheticalReplacementReplayForCurrentDraft(nextDraft, nextReplacementIntentDraft, setHypotheticalReplacementReplay)
    setPersistedConstructionArtifactReview(null)
    setPersistedOptimizerHandoffReview(null)
    setLastImportedFileNames(getWorkspaceImportedFileNames(nextWorkspace ?? activeWorkspace, nextNode))
    const dashboardSnapshot = nextDraft?.portfolioSnapshot ?? nextNode?.portfolioSnapshot ?? null
    const dashboardSnapshotId = nextDraft ? 'draft' : nextNode?.id ?? null
    if (dashboardSnapshot && dashboardSnapshotId) {
      const nodeSource = getEffectiveNodeImportSource(nextNode, nextNodes, nextWorkspace ?? activeWorkspace)
      const directNodeSource = getDirectNodeImportSource(nextNode, nextWorkspace ?? activeWorkspace)
      await analyzeRestoredSnapshot(
        dashboardSnapshot,
        dashboardSnapshotId,
        resolveEffectiveHistorySource(nodeSource, directNodeSource),
        activeWorkspace.id,
      )
    }
  }

  async function handleImportFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.target.files ?? [])
    if (!selectedFiles.length) {
      return
    }

    const files = selectedFiles

    setImportingPortfolio(true)
    setImportError(null)
    setExposureAnalysis(null)
    setExposureFactorModel(null)
    setTab('dashboard')

    try {
      const response = await fetch('/api/portfolios/import/interactive-brokers/analyze-upload', {
        method: 'POST',
        body: buildImportFormData(files),
      })

      if (!response.ok) {
        const payload = (await response.json()) as { detail?: string }
        throw new Error(payload.detail ?? 'Import failed')
      }

      const nextAnalysis = (await response.json()) as ImportedBootstrapResponse
      const importedViews = projectImportedBootstrap(nextAnalysis)
      const importedFileNames = files.map((file) => file.name)
      const importedSnapshot = buildPortfolioSnapshotFromAnalysis(importedViews.workspace, importedFileNames)
      const activeSnapshot = workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot ?? null
      const analysisSnapshot = importModeRef.current === 'add_snapshot' && activeSnapshot
        ? overlayImportedSnapshot(activeSnapshot, importedSnapshot)
        : importedSnapshot
      if (importModeRef.current === 'add_snapshot') {
        if (!activeWorkspace) {
          throw new Error('No active workspace available for adding a statement')
        }

        const baseSnapshot = workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot
        if (!baseSnapshot) {
          throw new Error('No active snapshot available for adding a statement')
        }
        const overlaidSnapshot = overlayImportedSnapshot(baseSnapshot, importedSnapshot)
        const baseNode = workingDraft
          ? (workspaceNodes.find((item) => item.id === workingDraft.baseNodeId) ?? activeNode)
          : activeNode
        const baseSource = getEffectiveNodeImportSource(baseNode, workspaceNodes, activeWorkspace)
        const mergedHistoryContext = mergeHistoryContext(getNodeHistorySource(baseSource)?.historyContext ?? null, importedViews.historyContext)

        const savedNode = await saveImportedSnapshotNode({
          workspaceId: activeWorkspace.id,
          parentNodeId: baseNode?.id ?? activeWorkspace.rootNodeId,
          portfolioSnapshot: overlaidSnapshot,
          importedFileNames,
          historyContext: mergedHistoryContext,
          importedHistorySnapshot: null,
          name: buildImportedSnapshotName(nextAnalysis.snapshot),
        })
        const [nextNode, nextDraft, nextNodes] = await Promise.all([
          getNode(savedNode.node.id),
          getDraft(activeWorkspace.id),
          getWorkspaceNodes(activeWorkspace.id),
        ])

        setLoadedStatementFiles(files)
        setLastImportedFileNames(importedFileNames)
        setActiveWorkspace(savedNode.workspace)
        setActiveNode(nextNode ?? savedNode.node)
        setWorkingDraft(nextDraft)
        setPersistedConstructionArtifactReview(null)
        setPersistedOptimizerHandoffReview(null)
        await loadCandidateImprovementDraftForCurrentDraft(nextDraft, setCandidateImprovementDraft)
        await loadIntentBoundSeededEtfReplacementRankingDraftForCurrentDraft(nextDraft, setIntentBoundSeededEtfReplacementRankingDraft)
        const nextSelectedConstructionRuleId = await loadSelectedConstructionRuleForCurrentDraft(nextDraft, setSelectedConstructionRuleId)
        const nextReplacementIntentDraft = nextDraft ? await getReplacementIntentDraft(nextDraft.id).catch(() => null) : null
        setReplacementIntentDraft(nextReplacementIntentDraft)
        await loadFormedCandidateArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, setFormedCandidateArtifact)
        await loadConstructedCandidateArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, setConstructedCandidateArtifact)
        await loadConstructionConstraintValidationArtifactForCurrentDraft(nextDraft, nextReplacementIntentDraft, nextSelectedConstructionRuleId, setConstructionConstraintValidationArtifact)
        await loadHypotheticalReplacementReplayForCurrentDraft(nextDraft, nextReplacementIntentDraft, setHypotheticalReplacementReplay)
        await loadWorkspaceProposalArtifacts(savedNode.workspace, setProposalArtifacts)
        await loadActiveThesisForWorkspace(savedNode.workspace, setActiveThesis)
        setWorkspaceNodes(nextNodes)
        setRestoredSession(false)
        const dashboardNode = nextNode ?? savedNode.node
        const dashboardSnapshot = nextDraft?.portfolioSnapshot ?? dashboardNode.portfolioSnapshot
        const dashboardSnapshotId = nextDraft ? 'draft' : dashboardNode.id
        if (dashboardSnapshot) {
          await analyzeRestoredSnapshot(
            dashboardSnapshot,
            dashboardSnapshotId,
            mergedHistoryContext
              ? {
                  kind: 'history_context',
                  historyContext: mergedHistoryContext,
                  importedHistorySnapshot: null,
                }
              : null,
            savedNode.workspace.id,
          )
        } else {
          setSelectedExposureSnapshotId(dashboardSnapshotId)
        }
        return
      }

      const dashboardHistory = await runImportedDashboardHistory(nextAnalysis.snapshot)
      const [exposure, diagnostics] = await Promise.all([
        runExposureEngine(analysisSnapshot),
        runImportedDiagnosticsEngine(nextAnalysis.snapshot),
      ])
      const exposureView = composeExposureView(exposure, diagnostics)

      const workspaceResult = await createWorkspaceFromImport({
        analysis: importedViews.workspace,
        importedFileNames,
        historyContext: importedViews.historyContext,
        importedHistorySnapshot: nextAnalysis.snapshot,
      })
      const normalizedDraft = {
        ...workspaceResult.draft,
        portfolioSnapshot: importedSnapshot,
      }

      setAnalysis(
        dashboardHistory
          ? composeDashboardAnalysisWithHistory(
              exposure,
              dashboardHistory,
            )
          : composeDashboardAnalysisFromEngines(exposure, diagnostics),
      )
      setBaselineAnalysis(buildPortfolioBaselineView(exposure))
      setExposureAnalysis(exposureView)
      setDiagnosticsAnalysis(diagnostics)
      setExposureFactorModel(buildExposureFactorModel(exposureView))
      setLoadedStatementFiles(files)
      setLastImportedFileNames(importedFileNames)
      setActiveWorkspace(workspaceResult.workspace)
      setActiveNode(workspaceResult.rootNode)
      setWorkingDraft(normalizedDraft)
      setPersistedConstructionArtifactReview(null)
      setPersistedOptimizerHandoffReview(null)
      await loadCandidateImprovementDraftForCurrentDraft(normalizedDraft, setCandidateImprovementDraft)
      await loadIntentBoundSeededEtfReplacementRankingDraftForCurrentDraft(normalizedDraft, setIntentBoundSeededEtfReplacementRankingDraft)
      await loadSelectedConstructionRuleForCurrentDraft(normalizedDraft, setSelectedConstructionRuleId)
      await loadReplacementIntentDraftForCurrentDraft(normalizedDraft, setReplacementIntentDraft)
      setFormedCandidateArtifact(null)
      setConstructedCandidateArtifact(null)
      setConstructionConstraintValidationArtifact(null)
      setHypotheticalReplacementReplay(null)
      setProposalArtifacts([])
      setActiveThesis(null)
      setWorkspaceNodes([workspaceResult.rootNode])
      setSelectedExposureSnapshotId('draft')
      setRestoredSession(false)
      try {
        await saveDraft(normalizedDraft)
        await setSelectedExposureSnapshot({ workspaceId: workspaceResult.workspace.id, snapshotId: 'draft' })
      } catch {
        // Keep the imported workspace usable even if local persistence is unavailable.
      }
    } catch (caughtError) {
      setImportError(caughtError instanceof Error ? caughtError.message : 'Import failed')
    } finally {
      setImportingPortfolio(false)
      event.target.value = ''
    }
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Portfolio Workstation</p>
          <p className="helper workflow-status-text">{workflowState}</p>
        </div>
        <nav className="tab-bar header-tab-bar" aria-label="Main workspace tabs">
          <button className={`tab-button${tab === 'workspace' ? ' active' : ''}`} onClick={() => setTab('workspace')}>Workspace</button>
          <button className={`tab-button${tab === 'dashboard' ? ' active' : ''}`} onClick={() => setTab('dashboard')}>Dashboard</button>
          <button className={`tab-button${tab === 'exposure' ? ' active' : ''}`} onClick={() => setTab('exposure')}>Exposure</button>
          <button className={`tab-button${tab === 'diagnostics' ? ' active' : ''}`} onClick={() => setTab('diagnostics')}>Diagnostics</button>
          <button className={`tab-button${tab === 'backtest' ? ' active' : ''}`} onClick={() => setTab('backtest')}>Backtest</button>
          <button className={`tab-button${tab === 'strategy_lab' ? ' active' : ''}`} onClick={() => setTab('strategy_lab')}>Strategy Lab</button>
          <button className={`tab-button${tab === 'etf_ranking' ? ' active' : ''}`} onClick={() => setTab('etf_ranking')}>ETF Ranking</button>
        </nav>
        <div className="topbar-meta">
          <span className="status-dot" />
          <span>Local Quant Engine</span>
        </div>
      </header>

      <input ref={fileInputRef} type="file" accept="application/pdf,.pdf" hidden multiple onChange={handleImportFileChange} />

      {tab === 'dashboard' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Dashboard</p><p className="helper">Loading dashboard...</p></section>}>
            <DashboardPanel
              result={analysis}
              exposureResult={exposureAnalysis}
              factorModel={exposureFactorModel}
              draftSnapshot={dashboardSnapshot}
              activeNodeName={activeNode?.name ?? null}
              draftStatus={workingDraft?.status ?? null}
              importing={importingPortfolio || restoringPortfolio}
              importError={importError}
              lastImportedFileNames={lastImportedFileNames}
              restoredSession={restoredSession}
              onImportPortfolio={artifactReviewMode ? undefined : () => openImportPicker('replace')}
              onAppendStatement={artifactReviewMode ? undefined : dashboardSnapshot && activeWorkspace ? () => openImportPicker('add_snapshot') : undefined}
              onClearImportedSession={artifactReviewMode ? undefined : activeWorkspace ? handleClearImportedSession : undefined}
              onResetLocalDatabase={handleResetLocalDatabase}
              onPreviewExposure={artifactReviewMode ? undefined : handlePreviewExposure}
              onDraftSnapshotChange={artifactReviewMode ? undefined : handleDraftSnapshotChange}
              onDiscardDraft={artifactReviewMode ? undefined : handleDiscardDraft}
              onSaveVariant={artifactReviewMode ? undefined : handleSaveVariant}
            />
          </Suspense>
          <VariantList nodes={workspaceNodes} activeNodeId={activeNode?.id ?? null} onOpenNode={handleOpenNode} />
        </section>
      ) : null}

      {tab === 'exposure' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Exposure</p><p className="helper">Loading exposure analytics...</p></section>}>
            <ExposurePanel
              result={exposureAnalysis}
              factorModel={exposureFactorModel}
              snapshotOptions={[
                ...(workingDraft ? [{ id: 'draft', label: formatWorkingDraftLabel(activeNode, workspaceNodes) }] : []),
                ...workspaceNodes.map((node) => ({ id: node.id, label: formatVariantNodeLabel(node, workspaceNodes) })),
              ]}
              selectedSnapshotId={selectedExposureSnapshotId}
              onSnapshotSelect={(snapshotId) => {
                void (async () => {
                  if (!activeWorkspace) return
                  if (snapshotId === 'draft' && workingDraft) {
                    const selectedBaseNode = workspaceNodes.find((item) => item.id === workingDraft.baseNodeId) ?? activeNode
                    const selectedBaseSource = getEffectiveNodeImportSource(selectedBaseNode, workspaceNodes, activeWorkspace)
                    const selectedBaseDirectSource = getDirectNodeImportSource(selectedBaseNode, activeWorkspace)
                    await analyzeExposureSnapshot(workingDraft.portfolioSnapshot, 'draft', activeWorkspace.id, {
                      historySource: canUseImportedReplay(selectedBaseDirectSource) && workingDraft.status === 'clean'
                        ? (getNodeHistorySource(selectedBaseDirectSource) ?? null)
                        : collapseToHistoryContextSource(selectedBaseSource),
                      preserveDashboardAnalysis: true,
                    })
                    return
                  }

                  const node = workspaceNodes.find((item) => item.id === snapshotId) ?? await getNode(snapshotId)
                  if (!node) return
                  if (!node.portfolioSnapshot) return
                  const nodeSource = getEffectiveNodeImportSource(node, workspaceNodes, activeWorkspace)
                  const directNodeSource = getDirectNodeImportSource(node, activeWorkspace)
                  await analyzeExposureSnapshot(node.portfolioSnapshot, snapshotId, activeWorkspace.id, {
                    historySource: resolveEffectiveHistorySource(nodeSource, directNodeSource),
                    preserveDashboardAnalysis: true,
                  })
                })()
              }}
            />
          </Suspense>
        </section>
      ) : null}

        {tab === 'diagnostics' ? (
          <section className="grid grid-single">
            <TrendRiskOverlaysPanel result={diagnosticsAnalysis} />
            <Suspense fallback={<section className="panel"><p className="panel-label">Diagnostics</p><p className="helper">Loading diagnostics...</p></section>}>
              <DiagnosticsPanel result={diagnosticsAnalysis} />
            </Suspense>
          </section>
        ) : null}

      {tab === 'workspace' ? (
        <section className="grid grid-single">
          {workspaceError ? <p className="error">{workspaceError}</p> : null}
          <Suspense fallback={<section className="panel"><p className="panel-label">Workspace</p><p className="helper">Loading portfolio research workspace...</p></section>}>
            <BacktestWorkspacePanel
              allocationBacktestResult={allocationBacktestRun}
              onAllocationBacktestResult={setAllocationBacktestRun}
              analysis={baselineAnalysis}
              draftSnapshot={workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot ?? null}
              workspaceSource={activeWorkspace?.source ?? null}
              persistedConstructionArtifactReview={persistedConstructionArtifactReview}
              persistedOptimizerHandoffReview={persistedOptimizerHandoffReview}
              candidateImprovementDraft={candidateImprovementDraft}
              intentBoundSeededEtfReplacementRankingDraft={desktopFeatureFlags.intentBoundSeededEtfReplacementRanking ? intentBoundSeededEtfReplacementRankingDraft : null}
              replacementIntentDraft={replacementIntentDraft}
              formedCandidateArtifact={formedCandidateArtifact}
              constructedCandidateArtifact={constructedCandidateArtifact}
              constructionConstraintValidationArtifact={constructionConstraintValidationArtifact}
              selectedConstructionRuleId={selectedConstructionRuleId}
              hypotheticalReplayResult={hypotheticalReplacementReplay}
              savedProposals={proposalArtifacts}
              activeThesis={activeThesis}
              onOpenSavedProposal={handleOpenSavedProposal}
              openedSavedProposalArtifactId={openedSavedProposalArtifactId}
              monitoringResearchHandoff={monitoringResearchHandoff}
              monitoringResearchHandoffDismissed={monitoringResearchHandoffDismissed}
              onDismissMonitoringResearchHandoff={handleDismissMonitoringResearchHandoff}
              onReviewInResearch={handleReviewMonitoringInResearch}
              onSaveProposal={handleSaveProposal}
              onPromoteProposalToThesis={handlePromoteProposalToThesis}
              onClearActiveThesis={handleClearActiveThesis}
              onCreateReplacementIntent={handleCreateReplacementIntent}
              onClearReplacementIntent={handleClearReplacementIntent}
              onFormedCandidateArtifact={(result) => {
                if (!activeWorkspace || !workingDraft || !replacementIntentDraft) return
                const artifact: FormedCandidateArtifact = {
                  workspaceId: activeWorkspace.id,
                  draftId: workingDraft.id,
                  baseNodeId: workingDraft.baseNodeId,
                  replacementIntentCreatedAt: replacementIntentDraft.createdAt,
                  replacementIntentBaseSymbol: replacementIntentDraft.baseSymbol,
                  replacementIntentCandidateSymbol: replacementIntentDraft.candidateSymbol,
                  formation: result,
                }
                setFormedCandidateArtifact(artifact)
                setConstructedCandidateArtifact(null)
                setConstructionConstraintValidationArtifact(null)
                setHypotheticalReplacementReplay(null)
                void saveFormedCandidateArtifact(artifact).catch(() => undefined)
                void deleteConstructedCandidateArtifact(workingDraft.id).catch(() => undefined)
                void deleteConstructionConstraintValidationArtifact(workingDraft.id).catch(() => undefined)
                void deleteHypotheticalReplacementReplayDraft(workingDraft.id).catch(() => undefined)
              }}
              onConstructedCandidateArtifact={(result) => {
                if (!activeWorkspace || !workingDraft || !replacementIntentDraft) return
                const artifact: ConstructedCandidateArtifact = {
                  workspaceId: activeWorkspace.id,
                  draftId: workingDraft.id,
                  baseNodeId: workingDraft.baseNodeId,
                  replacementIntentCreatedAt: replacementIntentDraft.createdAt,
                  replacementIntentBaseSymbol: replacementIntentDraft.baseSymbol,
                  replacementIntentCandidateSymbol: replacementIntentDraft.candidateSymbol,
                  constructionRuleId: selectedConstructionRuleId,
                  construction: result,
                }
                setConstructedCandidateArtifact(artifact)
                setConstructionConstraintValidationArtifact(null)
                setHypotheticalReplacementReplay(null)
                void saveConstructedCandidateArtifact(artifact).catch(() => undefined)
                void deleteConstructionConstraintValidationArtifact(workingDraft.id).catch(() => undefined)
                void deleteHypotheticalReplacementReplayDraft(workingDraft.id).catch(() => undefined)
              }}
              onConstructionConstraintValidationArtifact={(result) => {
                if (!activeWorkspace || !workingDraft || !replacementIntentDraft) return
                const artifact: ConstructionConstraintValidationArtifact = {
                  workspaceId: activeWorkspace.id,
                  draftId: workingDraft.id,
                  baseNodeId: workingDraft.baseNodeId,
                  replacementIntentCreatedAt: replacementIntentDraft.createdAt,
                  replacementIntentBaseSymbol: replacementIntentDraft.baseSymbol,
                  replacementIntentCandidateSymbol: replacementIntentDraft.candidateSymbol,
                  constructionRuleId: selectedConstructionRuleId,
                  validation: result,
                }
                setConstructionConstraintValidationArtifact(artifact)
                setHypotheticalReplacementReplay(null)
                void saveConstructionConstraintValidationArtifact(artifact).catch(() => undefined)
                void deleteHypotheticalReplacementReplayDraft(workingDraft.id).catch(() => undefined)
              }}
              onSelectedConstructionRuleChange={(ruleId) => {
                if (!activeWorkspace || !workingDraft) {
                  setSelectedConstructionRuleId(ruleId)
                  return
                }
                setSelectedConstructionRuleId(ruleId)
                setConstructionConstraintValidationArtifact(null)
                setHypotheticalReplacementReplay(null)
                const annotation: SelectedConstructionRuleArtifact = {
                  workspaceId: activeWorkspace.id,
                  draftId: workingDraft.id,
                  baseNodeId: workingDraft.baseNodeId,
                  selectedRuleId: ruleId,
                }
                void saveSelectedConstructionRule(annotation).catch(() => undefined)
                void deleteConstructionConstraintValidationArtifact(workingDraft.id).catch(() => undefined)
                void deleteHypotheticalReplacementReplayDraft(workingDraft.id).catch(() => undefined)
              }}
              onHypotheticalReplayResult={(result) => {
                setHypotheticalReplacementReplay(result)
                if (!activeWorkspace || !workingDraft || !replacementIntentDraft) return
                const artifact: HypotheticalReplacementReplayDraftArtifact = {
                  workspaceId: activeWorkspace.id,
                  draftId: workingDraft.id,
                  baseNodeId: workingDraft.baseNodeId,
                  replacementIntentCreatedAt: replacementIntentDraft.createdAt,
                  replacementIntentBaseSymbol: replacementIntentDraft.baseSymbol,
                  replacementIntentCandidateSymbol: replacementIntentDraft.candidateSymbol,
                  replay: result,
                }
                void saveHypotheticalReplacementReplayDraft(artifact).catch(() => undefined)
              }}
            />
          </Suspense>
        </section>
      ) : null}

      {tab === 'backtest' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Backtest</p><p className="helper">Loading generic backtest workspace...</p></section>}>
            <StrategyBacktestPanel backtestResult={backtestRun} onBacktestResult={setBacktestRun} />
          </Suspense>
        </section>
      ) : null}

      {tab === 'strategy_lab' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Strategy Lab</p><p className="helper">Loading prototype research workspace...</p></section>}>
            <StrategyLabPanel />
          </Suspense>
        </section>
      ) : null}

      {tab === 'etf_ranking' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">ETF Ranking</p><p className="helper">Loading ETF ranking workspace...</p></section>}>
            <EtfRankingPanel draftSymbols={workingDraft?.portfolioSnapshot.positions.map((position) => position.symbol) ?? []} onSeedCandidateDraft={handleSeedCandidateDraft} />
          </Suspense>
        </section>
      ) : null}
    </main>
  )
}
