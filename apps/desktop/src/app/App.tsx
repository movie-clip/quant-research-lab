import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { buildExposureFactorModelResponse } from '../features/portfolio/exposureFactorModel'
import { canUseImportedReplay, collapseToHistoryContextSource, resolveEffectiveHistorySource } from '../features/portfolio/historySource'
import { projectImportedBootstrap } from '../features/portfolio/importedBootstrapMapper'
import { buildExposureFactorModel, buildPortfolioBaselineView, composeDashboardAnalysisFromEngines, composeDashboardAnalysisWithHistory, runDashboardHistoryEngine, runDiagnosticsEngine, runExposureEngine, composeExposureView, runImportedDashboardHistory, runImportedDiagnosticsEngine } from '../features/portfolio/portfolioAnalysisAdapter'
import { formatVariantNodeLabel, formatWorkingDraftLabel } from '../features/portfolio/variantLabels'
import { buildPortfolioSnapshotFromAnalysis, overlayImportedSnapshot } from '../features/portfolio/portfolioSnapshot'
import { hasDataQualityEvidence, isBenchmarkTrendMonitorIdentity, isBenchmarkTrendTimelineHistoryRow, isBenchmarkTrendTimelineObservationRow, isDataQualityMonitorIdentity, isDataQualityObservationStatus, isDataQualitySignificanceStatus, isDataQualityTimelineHistoryRow, isDataQualityTimelineObservationRow } from '../features/portfolio/types'
import { composeDashboardSession, isDashboardDetailedReviewEligible, type DashboardSession } from './dashboardSession'
import { desktopFeatureFlags } from './featureFlags'
import { resolveImportedWorkspaceStartupTruth } from './startupSelectionValidation'
import type { ConstructionArtifactPreviewHandoff, ConstructionArtifactReplayResponse, ConstructionArtifactReplayValidationResponse, DataQualityMonitorEvidenceSummary, HypotheticalReplayResponse, ImportedBootstrapResponse, ImportedSnapshot, ImportedStatementImporter, BacktestRunResponse, DashboardAnalysis, DashboardHistoryEngineResponse, DiagnosticsEngineResponse, ExposureAnalysis, ExposureFactorModelResponse, MonitoringResearchHandoff, MonitorDefinitionActiveAlertEpisodeInboxResponse, MonitorDefinitionActiveAlertEpisodeInboxRow, MonitorDefinitionAlertEpisodeHistoryResponse, MonitorDefinitionAlertEpisodeHistoryRow, MonitorDefinitionAlertReviewTimelineHistoryRow, MonitorDefinitionAlertReviewTimelineObservationRow, MonitorDefinitionAlertReviewTimelineResponse, MonitorDefinitionEvaluationHistoryEntryResponse, MonitorDefinitionObservationArtifact, MonitorDefinitionRecoveredAlertReviewQueueResponse, MonitorDefinitionRecoveredAlertReviewQueueRow, OptimizerHandoffReplayHandoff, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse, OptimizerPersistedArtifactReference, PortfolioAllocationBacktestResponse, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from '../features/portfolio/types'
import type { ActiveThesisArtifact, CandidateImprovementDraftArtifact, CandidateImprovementSeed, ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, HypotheticalReplacementReplayDraftArtifact, ImportedHistoryContext, ImportedHistorySource, IntentBoundSeededEtfReplacementRankingDraftArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifactInput, MonitorDefinitionAlertReviewSessionState, MonitorDefinitionAlertReviewTimelineSelection, MonitorDefinitionAlertReviewWorkspaceState, PersistedConstructionArtifactWorkspaceReview, PersistedOptimizerHandoffWorkspaceReview, PortfolioNode, PortfolioWorkspace, ReplacementIntentDraftArtifact, ReviewSnapshotArtifact, ReviewSnapshotOpenHandoff, SelectedConstructionRuleArtifact, VersionedProposalArtifact, WorkingDraft, WorkspaceState } from '../features/portfolio/workspaceTypes'
import { assertValidReviewSnapshotOpenResponseEnvelope, assertValidSavedProposalReviewSnapshotPMSummaryMirror, buildImportAdmissionSummaryFingerprint, buildImportSnapshotFingerprint, buildReviewSnapshotOpenHandoffFromProposal, buildSavedProposalArtifact, clearPortfolioWorkspaceState, createWorkspaceFromImport, createWorkspaceFromPersistedConstructionArtifact, createWorkspaceFromPersistedOptimizerHandoff, deleteActiveThesis, deleteConstructionConstraintValidationArtifact, deleteConstructedCandidateArtifact, deleteFormedCandidateArtifact, deleteHypotheticalReplacementReplayDraft, deleteReplacementIntentDraft, getActiveThesis, getCandidateImprovementDraft, getConstructionConstraintValidationArtifact, getConstructedCandidateArtifact, getDraft, getFormedCandidateArtifact, getHypotheticalReplacementReplayDraft, getIntentBoundSeededEtfReplacementRankingDraft, getLastOpenedWorkspaceState, getNode, getPersistedConstructionArtifactWorkspaceReview, getPersistedOptimizerHandoffWorkspaceReview, getReplacementIntentDraft, getSelectedConstructionRule, getWorkspace, getWorkspaceNodes, getWorkspaceProposalArtifacts, isDraftDirty, normalizeLegacyPersistedConstructionArtifactWorkspaceCache, normalizeLegacyPersistedOptimizerHandoffWorkspaceCache, resetLocalPortfolioDatabase, saveActiveThesis, saveCandidateImprovementDraft, saveConstructionConstraintValidationArtifact, saveConstructedCandidateArtifact, saveDraft, saveFormedCandidateArtifact, saveHypotheticalReplacementReplayDraft, saveImportAdmissionReviewDisposition, saveImportedSnapshotNode, saveIntentBoundSeededEtfReplacementRankingDraft, saveMonitorDefinitionAlertReviewWorkspaceState, saveProposalArtifact, saveReplacementIntentDraft, saveReviewSnapshotArtifact, saveSelectedConstructionRule, saveVariantFromDraft, setActiveNode as persistActiveNode, setSelectedExposureSnapshot } from './portfolioWorkspaceStorage'
import { TrendRiskOverlaysPanel } from '../features/portfolio/TrendRiskOverlaysPanel'
import { DashboardPanel } from '../features/portfolio/DashboardPanel'
import type { WorkspaceResearchTool } from '../features/backtest/BacktestWorkspacePanel'
import {
  applySessionStateUpdate,
  createEtfRankingPanelState,
  createStrategyBacktestPanelState,
  createStrategyLabPanelState,
  type StrategyBacktestPanelState,
  type StrategyLabPanelState,
  type EtfRankingPanelState,
  type SessionStateUpdate,
} from '../features/portfolio/workspaceResearchSessionState'
const ExposurePanel = lazy(async () => ({ default: (await import('../features/portfolio/ExposurePanel')).ExposurePanel }))
const DiagnosticsPanel = lazy(async () => ({ default: (await import('../features/portfolio/DiagnosticsPanel')).DiagnosticsPanel }))
const BacktestWorkspacePanel = lazy(async () => ({ default: (await import('../features/backtest/BacktestWorkspacePanel')).BacktestWorkspacePanel }))
const GenericRankingView = lazy(async () => ({ default: (await import('../features/generic-ranking/GenericRankingView')).GenericRankingView }))


const defaultSymbolOverrides = '{}'
type ImportMode = 'replace' | 'add_snapshot'
type AppTab = 'dashboard' | 'exposure' | 'diagnostics' | 'workspace' | 'backtest' | 'strategy_lab' | 'etf_ranking' | 'generic_ranking'
type WorkspaceOwnedResearchSessions = Record<string, {
  backtest: {
    result: BacktestRunResponse | null
    panelState: StrategyBacktestPanelState
  }
  strategy_lab: StrategyLabPanelState
  etf_ranking: EtfRankingPanelState
}>

function createWorkspaceOwnedResearchSessionRecord() {
  return {
    backtest: {
      result: null,
      panelState: createStrategyBacktestPanelState(),
    },
    strategy_lab: createStrategyLabPanelState(),
    etf_ranking: createEtfRankingPanelState(),
  }
}

const defaultConstructionRuleId: SingleReplacementConstructionRuleId = 'same_weight_substitution_v1'
const tauriAnalyzeUploadTimeoutMs = 30_000
const persistedConstructionArtifactQueryKey = 'construction_artifact_id'
const persistedOptimizerHandoffReferenceQueryKey = 'optimizer_handoff_reference'
const missingPersistedConstructionArtifactReviewRestoreMessage = 'Unable to restore previous portfolio workspace: persisted construction artifact review is missing'
const missingPersistedOptimizerHandoffReviewRestoreMessage = 'Unable to restore previous portfolio workspace: persisted optimizer handoff review is missing'
const missingPersistedStartupNodeListRestoreMessage = 'Unable to restore previous portfolio workspace: authoritative workspace nodes are unavailable on startup'

const appTabs: Array<{ id: AppTab; label: string }> = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'workspace', label: 'Workspace' },
  { id: 'exposure', label: 'Exposure' },
  { id: 'diagnostics', label: 'Diagnostics' },
  { id: 'backtest', label: 'Backtest' },
  { id: 'strategy_lab', label: 'Strategy Lab' },
  { id: 'etf_ranking', label: 'ETF Ranking' },
  { id: 'generic_ranking', label: 'Generic Ranking' },
]

const workspaceOwnedResearchTabs: WorkspaceResearchTool[] = ['backtest', 'strategy_lab', 'etf_ranking']

const idleMonitorDefinitionAlertReviewSession: MonitorDefinitionAlertReviewSessionState = {
  navigation: null,
  timeline: null,
  timelineStatus: 'idle',
  timelineError: null,
  latestObservation: { status: 'idle', row: null, observation: null, error: null },
  alertHistory: { status: 'idle', row: null, entry: null, error: null },
}

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

function assertConstructionArtifactReplayMatchesValidation(
  replay: ConstructionArtifactReplayResponse,
  validation: ConstructionArtifactReplayValidationResponse,
  expectedArtifactId: string,
) {
  if (replay.construction_artifact_id !== expectedArtifactId) {
    throw new Error('Unable to open persisted construction artifact review: preview artifact mismatch')
  }
  if (!replay.review_basis) {
    throw new Error('Unable to open persisted construction artifact review: preview response missing canonical review basis')
  }
  if (replay.review_basis.construction_artifact_id !== expectedArtifactId) {
    throw new Error('Unable to open persisted construction artifact review: review basis artifact mismatch')
  }
  if (JSON.stringify(replay.review_basis.preview_handoff) !== JSON.stringify(validation.preview_handoff)) {
    throw new Error('Unable to open persisted construction artifact review: review basis preview handoff mismatch')
  }
  if (JSON.stringify(replay.effective_replay_params) !== JSON.stringify(validation.effective_replay_params)) {
    throw new Error('Unable to open persisted construction artifact review: preview effective replay params mismatch')
  }
  if (JSON.stringify(replay.review_basis.preview_handoff.effective_replay_params) !== JSON.stringify(validation.effective_replay_params)) {
    throw new Error('Unable to open persisted construction artifact review: review basis replay params mismatch')
  }
  const launchContext = replay.review_basis.launch_context
  const replayProvenance = replay.replay_provenance
  if (!launchContext || typeof launchContext !== 'object') {
    throw new Error('Unable to open persisted construction artifact review: review basis launch context is missing')
  }
  if (launchContext.construction_artifact_id !== expectedArtifactId) {
    throw new Error('Unable to open persisted construction artifact review: review basis launch context artifact mismatch')
  }
  if (replayProvenance.construction_artifact_id !== expectedArtifactId) {
    throw new Error('Unable to open persisted construction artifact review: replay provenance artifact mismatch')
  }
  if (JSON.stringify(launchContext) !== JSON.stringify({
    construction_artifact_id: replayProvenance.construction_artifact_id,
    ranked_universe_artifact_id: replayProvenance.ranked_universe_artifact_id,
    ranked_universe_artifact_schema_version: replayProvenance.ranked_universe_artifact_schema_version,
    ranking_id: replayProvenance.ranking_id,
    ranking_methodology_id: replayProvenance.ranking_methodology_id,
    ranking_as_of_date: replayProvenance.ranking_as_of_date,
    current_portfolio_artifact_id: replayProvenance.current_portfolio_artifact_id,
    current_portfolio_as_of_timestamp: replayProvenance.current_portfolio_as_of_timestamp,
    policy_id: replayProvenance.policy_id,
    policy_definition_id: replayProvenance.policy_definition_id,
    top_n: replayProvenance.top_n,
  })) {
    throw new Error('Unable to open persisted construction artifact review: launch lineage mismatch between review basis and replay provenance')
  }
}

async function openPersistedConstructionArtifactReviewById(
  constructionArtifactId: string,
  options: {
    setActiveWorkspace: (value: PortfolioWorkspace | null) => void
    ensureWorkspaceOwnedResearchSession: (workspaceId: string) => void
    setActiveNode: (value: PortfolioNode | null) => void
    setWorkingDraft: (value: WorkingDraft | null) => void
    setWorkspaceNodes: (value: PortfolioNode[]) => void
    setPersistedConstructionArtifactReview: (value: PersistedConstructionArtifactWorkspaceReview | null) => void
    setPersistedOptimizerHandoffReview: (value: PersistedOptimizerHandoffWorkspaceReview | null) => void
    setHypotheticalReplacementReplay: (value: HypotheticalReplayResponse | null) => void
    setProposalArtifacts: (value: VersionedProposalArtifact[]) => void
    setOpenedSavedProposalArtifactId: (value: string | null) => void
    setActiveThesis: (value: ActiveThesisArtifact | null) => void
    setMonitorDefinitionAlertReviewSession: (value: MonitorDefinitionAlertReviewSessionState) => void
    setCandidateImprovementDraft: (value: CandidateImprovementDraftArtifact | null) => void
    setIntentBoundSeededEtfReplacementRankingDraft: (value: IntentBoundSeededEtfReplacementRankingDraftArtifact | null) => void
    setReplacementIntentDraft: (value: ReplacementIntentDraftArtifact | null) => void
    setFormedCandidateArtifact: (value: FormedCandidateArtifact | null) => void
    setConstructedCandidateArtifact: (value: ConstructedCandidateArtifact | null) => void
    setConstructionConstraintValidationArtifact: (value: ConstructionConstraintValidationArtifact | null) => void
    setSelectedConstructionRuleId: (value: SingleReplacementConstructionRuleId) => void
    setAnalysis: (value: DashboardAnalysis | null) => void
    setBaselineAnalysis: (value: ReturnType<typeof buildPortfolioBaselineView> | null) => void
    setAllocationBacktestRun: (value: PortfolioAllocationBacktestResponse | null) => void
    setSelectedExposureSnapshotId: (value: string) => void
    setLastImportedFileNames: (value: string[]) => void
    setTab: (value: AppTab) => void
    setRestoredSession: (value: boolean) => void
  },
) {
  const validationResponse = await fetch('/api/backtests/portfolio-allocation/construction-artifact-validation', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ construction_artifact_id: constructionArtifactId }),
  })
  const validationPayload = await validationResponse.json()
  if (!validationResponse.ok) {
    throw new Error((validationPayload as { detail?: string }).detail ?? 'Unable to open persisted construction artifact review')
  }
  const validation = validationPayload as ConstructionArtifactReplayValidationResponse
  const previewHandoff = resolveConstructionArtifactPreviewHandoff(validation, constructionArtifactId)
  const previewResponse = await fetch('/api/backtests/portfolio-allocation/construction-artifact-preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(previewHandoff),
  })
  const previewPayload = await previewResponse.json()
  if (!previewResponse.ok) {
    throw new Error((previewPayload as { detail?: string }).detail ?? 'Unable to open persisted construction artifact review')
  }
  const artifactReplay = previewPayload as ConstructionArtifactReplayResponse
  assertConstructionArtifactReplayMatchesValidation(artifactReplay, validation, constructionArtifactId)
  const created = await createWorkspaceFromPersistedConstructionArtifact({ constructionArtifactId, replay: artifactReplay })
  options.setActiveWorkspace(created.workspace)
  options.ensureWorkspaceOwnedResearchSession(created.workspace.id)
  options.setActiveNode(created.rootNode)
  options.setWorkingDraft(null)
  options.setWorkspaceNodes([created.rootNode])
  options.setPersistedConstructionArtifactReview(created.review)
  options.setPersistedOptimizerHandoffReview(null)
  options.setHypotheticalReplacementReplay(null)
  options.setProposalArtifacts([])
  options.setOpenedSavedProposalArtifactId(null)
  options.setActiveThesis(null)
  options.setMonitorDefinitionAlertReviewSession(idleMonitorDefinitionAlertReviewSession)
  options.setCandidateImprovementDraft(null)
  options.setIntentBoundSeededEtfReplacementRankingDraft(null)
  options.setReplacementIntentDraft(null)
  options.setFormedCandidateArtifact(null)
  options.setConstructedCandidateArtifact(null)
  options.setConstructionConstraintValidationArtifact(null)
  options.setSelectedConstructionRuleId(defaultConstructionRuleId)
  options.setAnalysis(null)
  options.setBaselineAnalysis(null)
  options.setAllocationBacktestRun(artifactReplay.replay)
  options.setSelectedExposureSnapshotId(created.rootNode.id)
  options.setLastImportedFileNames([])
  options.setTab('workspace')
  options.setRestoredSession(true)
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
  if (!snapshot.statement) {
    return 'undated'
  }
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
  return `${formatShortBrokerName(snapshot.statement?.importer)} ${extractStatementEndDate(snapshot)}`
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

function getImportedSourceAnchorNode(node: PortfolioNode | null, nodes: PortfolioNode[], workspace: PortfolioWorkspace | null) {
  let current = node
  const nodeById = new Map(nodes.map((item) => [item.id, item]))

  while (current) {
    if (getNodeImportSource(current, workspace)) {
      return current
    }
    current = current.parentId ? (nodeById.get(current.parentId) ?? null) : null
  }

  return null
}

function getEffectiveNodeImportSource(node: PortfolioNode | null, nodes: PortfolioNode[], workspace: PortfolioWorkspace | null) {
  const sourceAnchorNode = getImportedSourceAnchorNode(node, nodes, workspace)
  return getNodeImportSource(sourceAnchorNode, workspace)
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
    const normalizedFile = file.type === 'application/pdf'
      ? file
      : new File([file], file.name, { type: 'application/pdf', lastModified: file.lastModified })
    formData.append('statement_files', normalizedFile, normalizedFile.name)
  }
  formData.append('benchmark_symbol', 'SPY')
  formData.append('symbol_overrides', defaultSymbolOverrides)
  return formData
}

function isTauriRuntime() {
  return typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)
}

function normalizeTauriDialogSelection(selection: string | string[] | null): string[] {
  if (!selection) return []
  return Array.isArray(selection) ? selection : [selection]
}

function resolveFileNameFromPath(path: string) {
  const normalizedPath = path.startsWith('file://')
    ? (() => {
        try {
          return decodeURIComponent(new URL(path).pathname)
        } catch {
          return path
        }
      })()
    : path
  const segments = normalizedPath.replace(/\\/g, '/').split('/')
  return segments[segments.length - 1] || 'statement.pdf'
}

function createTauriImportError(detail: string) {
  return new Error(`Tauri import failed: ${detail}`)
}

function mapTauriAnalyzeUploadError(error: unknown, timedOut: boolean) {
  if (timedOut) {
    return createTauriImportError('the local import service timed out while analyzing the selected PDF files')
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    return createTauriImportError('the local import service stopped before the selected PDF files could be analyzed')
  }
  if (error instanceof TypeError) {
    return createTauriImportError('unable to reach the local import service while analyzing the selected PDF files')
  }
  return error
}

async function resolveTauriImportFiles(): Promise<File[]> {
  const [{ open }, { readFile }] = await Promise.all([
    import('@tauri-apps/plugin-dialog'),
    import('@tauri-apps/plugin-fs'),
  ])
  const selection = normalizeTauriDialogSelection(await open({
    multiple: true,
    directory: false,
    filters: [{ name: 'PDF Statements', extensions: ['pdf'] }],
  }))
  const pdfPaths = selection.filter((path) => path.toLowerCase().endsWith('.pdf'))

  return Promise.all(pdfPaths.map(async (path) => {
    const bytes = await readFile(path)
    const fileName = resolveFileNameFromPath(path)
    if (!bytes.length) {
      throw createTauriImportError(`could not read "${fileName}" because the selected PDF was empty`)
    }
    return new File([bytes], fileName, { type: 'application/pdf' })
  }))
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

function resolveImportedExposureExitNode(
  selectedSnapshotId: string | null | undefined,
  nodes: PortfolioNode[],
  activeNode: PortfolioNode | null,
  workingDraft: WorkingDraft | null,
) {
  const resolvedSnapshot = resolveSelectedSnapshot(selectedSnapshotId, nodes, activeNode, workingDraft)
  if (!resolvedSnapshot || resolvedSnapshot.id === 'current') return null
  if (resolvedSnapshot.id !== 'draft') {
    const selectedNode = nodes.find((item) => item.id === resolvedSnapshot.id) ?? (activeNode?.id === resolvedSnapshot.id ? activeNode : null)
    if (!selectedNode || selectedNode.kind !== 'variant') {
      return null
    }
  }

  const preferredBaseId = resolvedSnapshot.id === 'draft'
    ? (workingDraft?.baseNodeId ?? activeNode?.id ?? null)
    : resolvedSnapshot.id
  if (!preferredBaseId) return null

  const nodeById = new Map(nodes.map((item) => [item.id, item]))
  let current = nodeById.get(preferredBaseId) ?? (activeNode?.id === preferredBaseId ? activeNode : null)

  while (current) {
    if (current.kind === 'imported_base' || current.kind === 'imported_snapshot') {
      return current
    }
    current = current.parentId ? (nodeById.get(current.parentId) ?? null) : null
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

function formatObservationOpenFailure(error: unknown) {
  const message = error instanceof Error ? error.message : 'Unable to open timeline observation review'
  if (message.startsWith('Unable to open timeline observation review:')) {
    return message
  }
  return `Unable to open timeline observation review: ${message.charAt(0).toLowerCase()}${message.slice(1)}`
}

function formatAlertHistoryOpenFailure(error: unknown) {
  const message = error instanceof Error ? error.message : 'Unable to open timeline history review'
  if (message.startsWith('Unable to open timeline history review:')) {
    return message
  }
  return `Unable to open timeline history review: ${message.charAt(0).toLowerCase()}${message.slice(1)}`
}

function formatDefinitionScopedAlertReviewAnalyticsRestoreFailure(reason: string) {
  return `Unable to restore previous portfolio workspace: ${reason}`
}

function assertMonitorDefinitionRowFamilyIdentity(
  row: { monitor_id: string; benchmark_symbol: string; monitor_definition_id: string },
  context: string,
) {
  if (isDataQualityMonitorIdentity(row)) return 'data_quality' as const
  if (isBenchmarkTrendMonitorIdentity(row)) return 'benchmark_trend' as const
  if (row.monitor_id === 'data_quality_monitor_v1') {
    throw new Error(`${context} data-quality row benchmark_symbol must be DATA_QUALITY`)
  }
  if (row.monitor_id === 'benchmark_trend_overlay_v1') {
    throw new Error(`${context} benchmark trend row benchmark_symbol must not be DATA_QUALITY`)
  }
  throw new Error(`${context} monitor_id is unsupported`)
}

function assertMonitorDefinitionHandoffFamilyIdentity(
  row: { monitor_definition_id: string; monitor_id: string; benchmark_symbol: string },
  handoff: { monitor_definition_id: string; monitor_id: string; benchmark_symbol: string },
  context: string,
) {
  if (handoff.monitor_definition_id !== row.monitor_definition_id || handoff.monitor_id !== row.monitor_id || handoff.benchmark_symbol !== row.benchmark_symbol) {
    throw new Error(`${context} handoff identity does not match row identity`)
  }
}

function assertDataQualityEventFields(
  row: { observation_status?: string; outcome_status?: string; alert_classification?: string; significance_status?: string; benchmark_observation?: unknown; portfolio_observation?: unknown; active_observation?: unknown; data_quality_evidence?: DataQualityMonitorEvidenceSummary | null },
  context: string,
) {
  const status = row.observation_status ?? row.outcome_status
  const significance = row.alert_classification ?? row.significance_status
  if (!isDataQualityObservationStatus(status)) {
    throw new Error(`${context} data-quality status is unsupported`)
  }
  if (!isDataQualitySignificanceStatus(significance)) {
    throw new Error(`${context} data-quality significance is unsupported`)
  }
  if (row.benchmark_observation != null || row.portfolio_observation != null || row.active_observation != null) {
    throw new Error(`${context} data-quality row must not include benchmark threshold observation fields`)
  }
  if (!hasDataQualityEvidence(row)) {
    throw new Error(`${context} data-quality evidence is required`)
  }
}

function assertAlertEpisodeFamilyFields(
  row: MonitorDefinitionAlertEpisodeHistoryRow,
  context: string,
) {
  const family = assertMonitorDefinitionRowFamilyIdentity(row, context)
  assertMonitorDefinitionHandoffFamilyIdentity(row, row.timeline_handoff, context)
  if (family === 'data_quality') {
    if (!isDataQualityObservationStatus(row.latest_contributing_observation.observation_status)) {
      throw new Error(`${context} data-quality latest observation status is unsupported`)
    }
    if (!isDataQualitySignificanceStatus(row.latest_contributing_observation.alert_classification)) {
      throw new Error(`${context} data-quality latest observation classification is unsupported`)
    }
    if (row.recovery_basis) {
      if (!isDataQualityObservationStatus(row.recovery_basis.recovered_from_outcome_status)) {
        throw new Error(`${context} data-quality recovery outcome is unsupported`)
      }
      if (!isDataQualitySignificanceStatus(row.recovery_basis.recovered_from_significance_status)) {
        throw new Error(`${context} data-quality recovery significance is unsupported`)
      }
    }
  }
}

function assertMonitorDefinitionAlertReviewTimelineResponse(
  payload: unknown,
  expectedMonitorDefinitionId: string,
): asserts payload is MonitorDefinitionAlertReviewTimelineResponse {
  if (!payload || typeof payload !== 'object') {
    throw new Error('alert review timeline payload is malformed')
  }

  const candidate = payload as Partial<MonitorDefinitionAlertReviewTimelineResponse>
  if (!Array.isArray(candidate.items) || !candidate.metadata || typeof candidate.metadata !== 'object') {
    throw new Error('alert review timeline payload is malformed')
  }
  if (candidate.metadata.contract_version !== 'monitor_definition_alert_review_timeline_v1') {
    throw new Error('alert review timeline contract_version is unsupported')
  }
  if (candidate.metadata.monitor_definition_id !== expectedMonitorDefinitionId) {
    throw new Error('alert review timeline monitor_definition_id does not match requested definition id')
  }
  if (candidate.metadata.monitor_definition_schema_version !== 'monitor_definition_artifact_v1') {
    throw new Error('alert review timeline monitor_definition_schema_version is unsupported')
  }
  if (candidate.metadata.provenance !== 'canonical_latest_observation_artifact_and_append_only_evaluation_history_entries') {
    throw new Error('alert review timeline provenance is unsupported')
  }
  if (candidate.metadata.source_precedence !== 'persisted_observation_artifact_then_persisted_evaluation_history_entries_then_persisted_latest_alert_episode_projection') {
    throw new Error('alert review timeline source_precedence is unsupported')
  }
  if ('latest_alert_episode' in candidate.metadata && candidate.metadata.latest_alert_episode != null) {
    const episode = candidate.metadata.latest_alert_episode
    if (episode.contract_version !== 'monitor_definition_alert_episode_v1') {
      throw new Error('alert review timeline latest_alert_episode contract_version is unsupported')
    }
    if (episode.monitor_definition_id !== expectedMonitorDefinitionId) {
      throw new Error('alert review timeline latest_alert_episode monitor_definition_id does not match requested definition id')
    }
    if (episode.episode_status !== 'active' && episode.episode_status !== 'recovered') {
      throw new Error('alert review timeline latest_alert_episode episode_status is unsupported')
    }
    if (episode.episode_status === 'active' && (episode.ended_at != null || episode.recovery_basis != null)) {
      throw new Error('alert review timeline latest_alert_episode active lifecycle is contradictory')
    }
    if (episode.episode_status === 'recovered' && (episode.ended_at == null || episode.recovery_basis == null)) {
      throw new Error('alert review timeline latest_alert_episode recovered lifecycle is contradictory')
    }
    if (episode.source_precedence !== 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation') {
      throw new Error('alert review timeline latest_alert_episode source_precedence is unsupported')
    }
  }
  if (typeof candidate.metadata.observation_rows !== 'number' || typeof candidate.metadata.history_rows !== 'number' || typeof candidate.metadata.total_rows !== 'number') {
    throw new Error('alert review timeline metadata counts are malformed')
  }
  if (candidate.metadata.observation_rows + candidate.metadata.history_rows !== candidate.metadata.total_rows) {
    throw new Error('alert review timeline metadata counts are contradictory')
  }

  let observationRows = 0
  let historyRows = 0
  for (const row of candidate.items) {
    if (!row || typeof row !== 'object' || !('event_kind' in row)) {
      throw new Error('alert review timeline row is malformed')
    }
    if (row.monitor_definition_id !== expectedMonitorDefinitionId) {
      throw new Error('alert review timeline row monitor_definition_id does not match requested definition id')
    }
    if (row.monitor_definition_schema_version !== 'monitor_definition_artifact_v1') {
      throw new Error('alert review timeline row monitor_definition_schema_version is unsupported')
    }
    assertMonitorDefinitionRowFamilyIdentity(row, 'alert review timeline row')
    if (row.event_kind === 'latest_observation_event') {
      observationRows += 1
      if (row.event_semantics !== 'observation_rooted') {
        throw new Error('alert review timeline latest observation event semantics are unsupported')
      }
      if (!row.open_handoff || row.open_handoff.handoff_kind !== 'monitor_definition_observation_open_handoff_v1') {
        throw new Error('alert review timeline latest observation handoff is malformed')
      }
      if (row.open_handoff.monitor_definition_id !== expectedMonitorDefinitionId || row.open_handoff.observation_id !== row.observation_id) {
        throw new Error('alert review timeline latest observation handoff does not match row identity')
      }
      assertMonitorDefinitionHandoffFamilyIdentity(row, row.open_handoff, 'alert review timeline latest observation')
      if (row.metadata.row_provenance !== 'persisted_monitor_definition_observation_artifact') {
        throw new Error('alert review timeline latest observation provenance is unsupported')
      }
      if (row.hysteresis_transition !== null && row.hysteresis_transition !== 'open' && row.hysteresis_transition !== 'remain_open' && row.hysteresis_transition !== 'recover' && row.hysteresis_transition !== 'no_op') {
        throw new Error('alert review timeline latest observation hysteresis_transition is unsupported')
      }
      if (row.monitor_id === 'data_quality_monitor_v1') {
        assertDataQualityEventFields(row, 'alert review timeline latest observation')
        if (!isDataQualityTimelineObservationRow(row)) {
          throw new Error('alert review timeline latest observation data-quality row fields are inconsistent')
        }
      } else if (!isBenchmarkTrendTimelineObservationRow(row)) {
        throw new Error('alert review timeline latest observation benchmark trend row fields are inconsistent')
      }
      continue
    }
    if (row.event_kind === 'evaluation_history_event') {
      historyRows += 1
      if (row.event_semantics !== 'history_entry_rooted') {
        throw new Error('alert review timeline history event semantics are unsupported')
      }
      if (!row.review_handoff || row.review_handoff.handoff_kind !== 'monitor_definition_evaluation_history_review_handoff_v1') {
        throw new Error('alert review timeline history handoff is malformed')
      }
      if (row.review_handoff.monitor_definition_id !== expectedMonitorDefinitionId || row.review_handoff.history_entry_id !== row.history_entry_id) {
        throw new Error('alert review timeline history handoff does not match row identity')
      }
      assertMonitorDefinitionHandoffFamilyIdentity(row, row.review_handoff, 'alert review timeline history')
      if (row.metadata.row_provenance !== 'persisted_monitor_definition_evaluation_history_entry') {
        throw new Error('alert review timeline history provenance is unsupported')
      }
      if (row.hysteresis_transition !== null && row.hysteresis_transition !== 'open' && row.hysteresis_transition !== 'remain_open' && row.hysteresis_transition !== 'recover' && row.hysteresis_transition !== 'no_op') {
        throw new Error('alert review timeline history hysteresis_transition is unsupported')
      }
      if (row.monitor_id === 'data_quality_monitor_v1') {
        assertDataQualityEventFields(row, 'alert review timeline history')
        if (!isDataQualityTimelineHistoryRow(row)) {
          throw new Error('alert review timeline history data-quality row fields are inconsistent')
        }
      } else if (!isBenchmarkTrendTimelineHistoryRow(row)) {
        throw new Error('alert review timeline history benchmark trend row fields are inconsistent')
      }
      continue
    }
    throw new Error('alert review timeline event_kind is unsupported')
  }

  if (observationRows !== candidate.metadata.observation_rows) {
    throw new Error('alert review timeline observation row count does not match metadata')
  }
  if (historyRows !== candidate.metadata.history_rows) {
    throw new Error('alert review timeline history row count does not match metadata')
  }
}

function assertMonitorDefinitionRecoveredAlertReviewQueueResponse(
  payload: unknown,
): asserts payload is MonitorDefinitionRecoveredAlertReviewQueueResponse {
  if (!payload || typeof payload !== 'object') {
    throw new Error('recovered alert review queue payload is malformed')
  }

  const candidate = payload as Partial<MonitorDefinitionRecoveredAlertReviewQueueResponse>
  if (!Array.isArray(candidate.items) || !candidate.metadata || typeof candidate.metadata !== 'object') {
    throw new Error('recovered alert review queue payload is malformed')
  }
  if (candidate.metadata.contract_version !== 'monitor_definition_recovered_alert_review_queue_v1') {
    throw new Error('recovered alert review queue contract_version is unsupported')
  }
  if (candidate.metadata.provenance !== 'persisted_latest_observation_with_latest_snapshot_and_prior_alert_history_lineage') {
    throw new Error('recovered alert review queue provenance is unsupported')
  }
  if (candidate.metadata.row_provenance !== 'persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage') {
    throw new Error('recovered alert review queue row provenance is unsupported')
  }
  if (candidate.metadata.source_precedence !== 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries') {
    throw new Error('recovered alert review queue source_precedence is unsupported')
  }
  if (candidate.metadata.ordering !== 'newest_first_evaluated_at_then_monitor_definition_id_then_observation_id') {
    throw new Error('recovered alert review queue ordering is unsupported')
  }
  if (typeof candidate.metadata.total_queue_rows !== 'number') {
    throw new Error('recovered alert review queue metadata counts are malformed')
  }
  if (candidate.metadata.total_queue_rows < candidate.items.length) {
    throw new Error('recovered alert review queue metadata counts are contradictory')
  }

  for (const row of candidate.items) {
    if (!row || typeof row !== 'object') {
      throw new Error('recovered alert review queue row is malformed')
    }
    if (row.monitor_definition_schema_version !== 'monitor_definition_artifact_v1') {
      throw new Error('recovered alert review queue row monitor_definition_schema_version is unsupported')
    }
    if (row.alert_classification !== 'informational') {
      throw new Error('recovered alert review queue row alert_classification is unsupported')
    }
    if (!row.alert_episode || typeof row.alert_episode !== 'object') {
      throw new Error('recovered alert review queue row alert_episode is malformed')
    }
    if (row.alert_episode.contract_version !== 'monitor_definition_alert_episode_v1') {
      throw new Error('recovered alert review queue row alert_episode contract_version is unsupported')
    }
    if (row.alert_episode.monitor_definition_id !== row.monitor_definition_id) {
      throw new Error('recovered alert review queue row alert_episode monitor_definition_id does not match row identity')
    }
    if (row.alert_episode.episode_status !== 'recovered') {
      throw new Error('recovered alert review queue row alert_episode episode_status is unsupported')
    }
    if (row.alert_episode.source_precedence !== 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation') {
      throw new Error('recovered alert review queue row alert_episode source_precedence is unsupported')
    }
    if (row.alert_episode.latest_contributing_observation.observation_id !== row.observation_id) {
      throw new Error('recovered alert review queue row alert_episode latest observation does not match row identity')
    }
    if (!row.alert_episode.recovery_basis || row.alert_episode.recovery_basis.recovered_from_history_entry_id !== row.recovered_from.history_entry_id) {
      throw new Error('recovered alert review queue row alert_episode recovery basis is malformed')
    }
    if (!row.timeline_handoff || row.timeline_handoff.handoff_kind !== 'monitor_definition_alert_review_timeline_open_handoff_v1') {
      throw new Error('recovered alert review queue row timeline handoff is malformed')
    }
    if (row.timeline_handoff.selected_event_kind !== 'latest_observation_event') {
      throw new Error('recovered alert review queue row timeline handoff selected_event_kind is unsupported')
    }
    if (row.timeline_handoff.monitor_definition_id !== row.monitor_definition_id || row.timeline_handoff.observation_id !== row.observation_id) {
      throw new Error('recovered alert review queue row timeline handoff does not match row identity')
    }
    if (!row.recovered_from || typeof row.recovered_from !== 'object') {
      throw new Error('recovered alert review queue row recovered_from lineage is malformed')
    }
    if (row.recovered_from.significance_status === 'informational') {
      throw new Error('recovered alert review queue row recovered_from significance_status is unsupported')
    }
    if (row.recovered_from.history_entry_id === row.latest_history_entry_id) {
      throw new Error('recovered alert review queue row recovered_from lineage is ambiguous')
    }
    if (row.hysteresis_transition !== null && row.hysteresis_transition !== 'recover' && row.hysteresis_transition !== 'no_op') {
      throw new Error('recovered alert review queue row hysteresis_transition is unsupported')
    }
    if (row.metadata.row_provenance !== 'persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage') {
      throw new Error('recovered alert review queue row provenance is unsupported')
    }
  }
}

export function assertMonitorDefinitionActiveAlertEpisodeInboxResponse(
  payload: unknown,
): asserts payload is MonitorDefinitionActiveAlertEpisodeInboxResponse {
  if (!payload || typeof payload !== 'object') {
    throw new Error('active alert episode inbox payload is malformed')
  }

  const candidate = payload as Partial<MonitorDefinitionActiveAlertEpisodeInboxResponse>
  if (!Array.isArray(candidate.items) || !candidate.metadata || typeof candidate.metadata !== 'object') {
    throw new Error('active alert episode inbox payload is malformed')
  }
  if (candidate.metadata.contract_version !== 'monitor_definition_active_alert_episode_inbox_v1') {
    throw new Error('active alert episode inbox contract_version is unsupported')
  }
  if (candidate.metadata.provenance !== 'authoritative_persisted_monitor_definition_alert_episode_records_only') {
    throw new Error('active alert episode inbox provenance is unsupported')
  }
  if (candidate.metadata.row_provenance !== 'persisted_monitor_definition_alert_episode_record') {
    throw new Error('active alert episode inbox row provenance is unsupported')
  }
  if (candidate.metadata.source_precedence !== 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation') {
    throw new Error('active alert episode inbox source_precedence is unsupported')
  }
  if (candidate.metadata.ordering !== 'newest_first_latest_event_at_then_monitor_definition_id_then_episode_id') {
    throw new Error('active alert episode inbox ordering is unsupported')
  }
  if (candidate.metadata.windowing !== 'before_episode_id_exclusive') {
    throw new Error('active alert episode inbox windowing is unsupported')
  }
  if (typeof candidate.metadata.total_active_episodes !== 'number') {
    throw new Error('active alert episode inbox metadata counts are malformed')
  }
  if (candidate.metadata.total_active_episodes < candidate.items.length) {
    throw new Error('active alert episode inbox metadata counts are contradictory')
  }

  for (const row of candidate.items) {
    if (!row || typeof row !== 'object') {
      throw new Error('active alert episode inbox row is malformed')
    }
    if (row.review_scope !== 'current_portfolio_truth_only') {
      throw new Error('active alert episode inbox row review_scope is unsupported')
    }
    if (row.evaluation_mode !== 'review_only_observation_evaluation') {
      throw new Error('active alert episode inbox row evaluation_mode is unsupported')
    }
    if (!row.alert_episode || typeof row.alert_episode !== 'object') {
      throw new Error('active alert episode inbox row alert_episode is malformed')
    }
    if (row.alert_episode.schema_version !== 'monitor_definition_alert_episode_record_v1') {
      throw new Error('active alert episode inbox row alert_episode schema_version is unsupported')
    }
    if (row.alert_episode.lifecycle_status !== 'open') {
      throw new Error('active alert episode inbox row alert_episode lifecycle_status is unsupported')
    }
    if (row.alert_episode.source_precedence !== 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation') {
      throw new Error('active alert episode inbox row alert_episode source_precedence is unsupported')
    }
    if (!row.alert_episode.latest_for_monitor_definition) {
      throw new Error('active alert episode inbox row alert_episode latest_for_monitor_definition is contradictory')
    }
    if (!row.alert_episode.timeline_handoff || row.alert_episode.timeline_handoff.handoff_kind !== 'monitor_definition_alert_episode_history_timeline_handoff_v1') {
      throw new Error('active alert episode inbox row alert_episode timeline_handoff is malformed')
    }
    assertAlertEpisodeFamilyFields(row.alert_episode, 'active alert episode inbox row')
    if (row.alert_episode.timeline_handoff.selected_event_kind !== 'latest_observation_event') {
      throw new Error('active alert episode inbox row alert_episode timeline_handoff selected_event_kind is unsupported')
    }
    if (row.alert_episode.timeline_handoff.observation_id !== row.alert_episode.latest_contributing_observation.observation_id) {
      throw new Error('active alert episode inbox row alert_episode timeline_handoff does not match latest observation identity')
    }
    if (row.metadata.row_provenance !== 'persisted_monitor_definition_alert_episode_record') {
      throw new Error('active alert episode inbox row metadata provenance is unsupported')
    }
  }
}

function isWorkspaceOwnedResearchTab(tab: AppTab): tab is WorkspaceResearchTool {
  return workspaceOwnedResearchTabs.includes(tab as WorkspaceResearchTool)
}

export function assertMonitorDefinitionAlertEpisodeHistoryResponse(
  payload: unknown,
  expectedMonitorDefinitionId: string,
): asserts payload is MonitorDefinitionAlertEpisodeHistoryResponse {
  if (!payload || typeof payload !== 'object') {
    throw new Error('alert episode history payload is malformed')
  }

  const candidate = payload as Partial<MonitorDefinitionAlertEpisodeHistoryResponse>
  if (!Array.isArray(candidate.items) || !candidate.metadata || typeof candidate.metadata !== 'object') {
    throw new Error('alert episode history payload is malformed')
  }
  if (candidate.metadata.contract_version !== 'monitor_definition_alert_episode_history_v1') {
    throw new Error('alert episode history contract_version is unsupported')
  }
  if (candidate.metadata.history_truth !== 'authoritative_persisted_monitor_definition_alert_episode_history') {
    throw new Error('alert episode history truth label is unsupported')
  }
  if (candidate.metadata.row_provenance !== 'persisted_monitor_definition_alert_episode_record') {
    throw new Error('alert episode history row provenance is unsupported')
  }
  if (candidate.metadata.source_precedence !== 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation') {
    throw new Error('alert episode history source_precedence is unsupported')
  }
  if (candidate.metadata.ordering !== 'newest_first_latest_event_at_then_episode_id') {
    throw new Error('alert episode history ordering is unsupported')
  }
  if (candidate.metadata.windowing !== 'before_episode_id_exclusive') {
    throw new Error('alert episode history windowing is unsupported')
  }
  if (candidate.metadata.monitor_definition_id !== expectedMonitorDefinitionId) {
    throw new Error('alert episode history monitor_definition_id does not match requested definition id')
  }
  if (candidate.metadata.monitor_definition_schema_version !== 'monitor_definition_artifact_v1') {
    throw new Error('alert episode history monitor_definition_schema_version is unsupported')
  }
  if (typeof candidate.metadata.total_episodes !== 'number') {
    throw new Error('alert episode history metadata counts are malformed')
  }
  if (candidate.metadata.total_episodes < candidate.items.length) {
    throw new Error('alert episode history metadata counts are contradictory')
  }

  let latestRows = 0
  for (const row of candidate.items) {
    if (!row || typeof row !== 'object') {
      throw new Error('alert episode history row is malformed')
    }
    if (row.schema_version !== 'monitor_definition_alert_episode_record_v1') {
      throw new Error('alert episode history row schema_version is unsupported')
    }
    if (row.monitor_definition_id !== expectedMonitorDefinitionId) {
      throw new Error('alert episode history row monitor_definition_id does not match requested definition id')
    }
    if (row.monitor_definition_schema_version !== 'monitor_definition_artifact_v1') {
      throw new Error('alert episode history row monitor_definition_schema_version is unsupported')
    }
    if (row.lifecycle_status !== 'open' && row.lifecycle_status !== 'recovered' && row.lifecycle_status !== 'closed') {
      throw new Error('alert episode history row lifecycle_status is unsupported')
    }
    if (row.latest_for_monitor_definition) {
      latestRows += 1
    }
    if (!row.timeline_handoff || row.timeline_handoff.handoff_kind !== 'monitor_definition_alert_episode_history_timeline_handoff_v1') {
      throw new Error('alert episode history row timeline_handoff is malformed')
    }
    assertAlertEpisodeFamilyFields(row, 'alert episode history row')
    if (row.timeline_handoff.monitor_definition_id !== row.monitor_definition_id) {
      throw new Error('alert episode history row timeline_handoff monitor_definition_id does not match row identity')
    }
    if (row.timeline_handoff.selected_event_kind === 'latest_observation_event') {
      if (row.timeline_handoff.observation_id !== row.latest_contributing_observation.observation_id || row.timeline_handoff.history_entry_id != null) {
        throw new Error('alert episode history row latest-observation handoff is contradictory')
      }
      if (row.lifecycle_status === 'closed') {
        throw new Error('alert episode history closed rows must not reopen by latest observation handoff')
      }
    } else if (row.timeline_handoff.selected_event_kind === 'evaluation_history_event') {
      if (row.timeline_handoff.history_entry_id !== row.terminal_history_entry_id || row.timeline_handoff.observation_id != null) {
        throw new Error('alert episode history row evaluation-history handoff is contradictory')
      }
      if (row.lifecycle_status !== 'closed') {
        throw new Error('alert episode history non-closed rows must not reopen by evaluation history handoff')
      }
    } else {
      throw new Error('alert episode history row timeline_handoff selected_event_kind is unsupported')
    }
    if (row.lifecycle_status === 'open' && (row.ended_at != null || row.recovery_basis != null || !row.latest_for_monitor_definition)) {
      throw new Error('alert episode history open lifecycle is contradictory')
    }
    if (row.lifecycle_status !== 'open' && (row.ended_at == null || row.recovery_basis == null)) {
      throw new Error('alert episode history recovered or closed lifecycle is contradictory')
    }
    if (row.metadata.row_provenance !== 'persisted_monitor_definition_alert_episode_record') {
      throw new Error('alert episode history row provenance is unsupported')
    }
    if (row.source_precedence !== 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation') {
      throw new Error('alert episode history row source_precedence is unsupported')
    }
  }

  if (latestRows > 1) {
    throw new Error('alert episode history latest row state is ambiguous')
  }
}

export async function loadMonitorDefinitionRecoveredAlertReviewQueue(): Promise<MonitorDefinitionRecoveredAlertReviewQueueResponse> {
  const response = await fetch('/api/backtests/monitor-definitions/recovered-alert-review-queue?limit=20')
  const payload = await response.json()
  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail ?? 'Unable to load recovered alert review queue')
  }
  assertMonitorDefinitionRecoveredAlertReviewQueueResponse(payload)
  return payload
}

export async function loadMonitorDefinitionActiveAlertEpisodeInbox(): Promise<MonitorDefinitionActiveAlertEpisodeInboxResponse> {
  const response = await fetch('/api/backtests/monitor-definitions/active-alert-episode-inbox?limit=20')
  const payload = await response.json()
  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail ?? 'Unable to load active alert episode inbox')
  }
  assertMonitorDefinitionActiveAlertEpisodeInboxResponse(payload)
  return payload
}

export async function loadMonitorDefinitionAlertEpisodeHistory(
  monitorDefinitionId: string,
  beforeEpisodeId?: string | null,
): Promise<MonitorDefinitionAlertEpisodeHistoryResponse> {
  const trimmedMonitorDefinitionId = monitorDefinitionId.trim()
  if (!trimmedMonitorDefinitionId) {
    throw new Error('Unable to load alert episode history: monitor definition id is required')
  }

  const params = new URLSearchParams({ limit: '20' })
  const trimmedBeforeEpisodeId = beforeEpisodeId?.trim() ?? ''
  if (trimmedBeforeEpisodeId) {
    params.set('before_episode_id', trimmedBeforeEpisodeId)
  }

  const response = await fetch(`/api/backtests/monitor-definitions/${encodeURIComponent(trimmedMonitorDefinitionId)}/alert-episode-history?${params.toString()}`)
  const payload = await response.json()
  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail ?? 'Unable to load alert episode history')
  }
  assertMonitorDefinitionAlertEpisodeHistoryResponse(payload, trimmedMonitorDefinitionId)
  return payload
}

export async function reopenRecoveredAlertReviewRow(
  row: MonitorDefinitionRecoveredAlertReviewQueueRow,
  beginNavigation: (input: { monitorDefinitionId: string; selectedEvent: MonitorDefinitionAlertReviewTimelineSelection | null }) => Promise<void>,
) {
  await beginNavigation({
    monitorDefinitionId: row.timeline_handoff.monitor_definition_id,
    selectedEvent: {
      eventKind: 'latest_observation_event',
      observationId: row.timeline_handoff.observation_id,
    },
  })
}

export async function openActiveAlertEpisodeInboxRow(
  row: MonitorDefinitionActiveAlertEpisodeInboxRow,
  beginNavigation: (input: { monitorDefinitionId: string; selectedEvent: MonitorDefinitionAlertReviewTimelineSelection | null }) => Promise<void>,
) {
  const handoff = row.alert_episode.timeline_handoff
  if (!handoff.observation_id) {
    throw new Error('Unable to open active alert episode timeline review: timeline handoff observation id is missing')
  }
  await beginNavigation({
    monitorDefinitionId: handoff.monitor_definition_id,
    selectedEvent: {
      eventKind: 'latest_observation_event',
      observationId: handoff.observation_id,
    },
  })
}

export async function openAlertEpisodeHistoryRow(
  row: MonitorDefinitionAlertEpisodeHistoryRow,
  beginNavigation: (input: { monitorDefinitionId: string; selectedEvent: MonitorDefinitionAlertReviewTimelineSelection | null }) => Promise<void>,
) {
  const handoff = row.timeline_handoff
  if (handoff.selected_event_kind === 'latest_observation_event') {
    if (!handoff.observation_id) {
      throw new Error('Unable to open alert episode history timeline review: timeline handoff observation id is missing')
    }
    await beginNavigation({
      monitorDefinitionId: handoff.monitor_definition_id,
      selectedEvent: {
        eventKind: 'latest_observation_event',
        observationId: handoff.observation_id,
      },
    })
    return
  }

  if (!handoff.history_entry_id) {
    throw new Error('Unable to open alert episode history timeline review: timeline handoff history entry id is missing')
  }
  await beginNavigation({
    monitorDefinitionId: handoff.monitor_definition_id,
    selectedEvent: {
      eventKind: 'evaluation_history_event',
      historyEntryId: handoff.history_entry_id,
    },
  })
}

export async function loadMonitorDefinitionAlertReviewTimeline(
  monitorDefinitionId: string,
): Promise<MonitorDefinitionAlertReviewTimelineResponse> {
  if (!monitorDefinitionId.trim()) {
    throw new Error('Unable to load alert review timeline: monitor definition id is required')
  }
  const response = await fetch(`/api/backtests/monitor-definitions/${encodeURIComponent(monitorDefinitionId)}/alert-review-timeline`)
  const payload = await response.json()
  if (!response.ok) {
    throw new Error((payload as { detail?: string }).detail ?? 'Unable to load alert review timeline')
  }
  assertMonitorDefinitionAlertReviewTimelineResponse(payload, monitorDefinitionId)
  return payload
}

export async function openLatestObservationFromTimelineRow(
  row: MonitorDefinitionAlertReviewTimelineObservationRow,
  setOpenState: Parameters<typeof openLatestObservationFromTimelineReviewRow>[1],
) {
  return openLatestObservationFromTimelineReviewRow(row, setOpenState)
}

export async function openAlertHistoryReviewFromTimelineRow(
  row: MonitorDefinitionAlertReviewTimelineHistoryRow,
  setOpenState: Parameters<typeof openAlertHistoryReviewFromTimelineReviewRow>[1],
) {
  return openAlertHistoryReviewFromTimelineReviewRow(row, setOpenState)
}

function buildMonitorDefinitionAlertReviewWorkspaceState(input: {
  monitorDefinitionId: string
  timeline: MonitorDefinitionAlertReviewTimelineResponse
  row: MonitorDefinitionAlertReviewTimelineObservationRow | MonitorDefinitionAlertReviewTimelineHistoryRow
}): MonitorDefinitionAlertReviewWorkspaceState {
  return {
    source: 'definition_scoped_alert_review_timeline',
    monitorDefinitionId: input.monitorDefinitionId,
    openedAt: new Date().toISOString(),
    selectedEvent: input.row.event_kind === 'latest_observation_event'
      ? {
          eventKind: 'latest_observation_event',
          observationId: input.row.observation_id,
        }
      : {
          eventKind: 'evaluation_history_event',
          historyEntryId: input.row.history_entry_id,
        },
    cachedTimeline: input.timeline,
  }
}

function resolveSelectedMonitorDefinitionTimelineRow(
  reviewState: MonitorDefinitionAlertReviewWorkspaceState,
  timeline: MonitorDefinitionAlertReviewTimelineResponse,
) {
  const selectedEvent = reviewState.selectedEvent
  if (selectedEvent.eventKind === 'latest_observation_event') {
    const row = timeline.items.find((item): item is MonitorDefinitionAlertReviewTimelineObservationRow => item.event_kind === 'latest_observation_event' && item.observation_id === selectedEvent.observationId)
    if (!row) {
      throw new Error('alert review timeline selected event is missing from the authoritative payload')
    }
    return row
  }

  const row = timeline.items.find((item): item is MonitorDefinitionAlertReviewTimelineHistoryRow => item.event_kind === 'evaluation_history_event' && item.history_entry_id === selectedEvent.historyEntryId)
  if (!row) {
    throw new Error('alert review timeline selected event is missing from the authoritative payload')
  }
  return row
}

function resolveMonitorDefinitionTimelineRowFromSelection(
  timeline: MonitorDefinitionAlertReviewTimelineResponse,
  selection: MonitorDefinitionAlertReviewTimelineSelection,
) {
   const selectedEvent = selection
   if (selectedEvent.eventKind === 'latest_observation_event') {
     const row = timeline.items.find((item): item is MonitorDefinitionAlertReviewTimelineObservationRow => item.event_kind === 'latest_observation_event' && item.observation_id === selectedEvent.observationId)
     if (!row) {
       throw new Error('selected event is missing from authoritative timeline payload')
     }
     return row
   }

   const row = timeline.items.find((item): item is MonitorDefinitionAlertReviewTimelineHistoryRow => item.event_kind === 'evaluation_history_event' && item.history_entry_id === selectedEvent.historyEntryId)
   if (!row) {
     throw new Error('selected event is missing from authoritative timeline payload')
   }
   return row
}

function resolveDefaultMonitorDefinitionTimelineObservationRow(
  timeline: MonitorDefinitionAlertReviewTimelineResponse,
) {
  return timeline.items.find(
    (item): item is MonitorDefinitionAlertReviewTimelineObservationRow => item.event_kind === 'latest_observation_event',
  ) ?? null
}

async function openLatestObservationFromTimelineReviewRow(
  row: MonitorDefinitionAlertReviewTimelineObservationRow,
  setOpenState: (value: {
    status: 'idle' | 'loading' | 'ready' | 'error'
    row: MonitorDefinitionAlertReviewTimelineObservationRow | null
    observation: MonitorDefinitionObservationArtifact | null
    error: string | null
  }) => void,
): Promise<boolean> {
  setOpenState({ status: 'loading', row, observation: null, error: null })
  try {
    const response = await fetch(`/api/backtests/monitor-definitions/${encodeURIComponent(row.monitor_definition_id)}/observation`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error((payload as { detail?: string }).detail ?? 'Unable to load persisted timeline observation artifact')
    }
    const observation = payload as MonitorDefinitionObservationArtifact
    if (observation.monitor_definition_id !== row.monitor_definition_id) {
      throw new Error('persisted observation monitor_definition_id does not match selected timeline observation event')
    }
    if (observation.observation_id !== row.open_handoff.observation_id) {
      throw new Error('persisted observation observation_id does not match selected timeline observation event')
    }
    if (observation.monitor_id !== row.monitor_id) {
      throw new Error('persisted observation monitor_id does not match selected timeline observation event')
    }
    if (observation.benchmark_symbol !== row.benchmark_symbol) {
      throw new Error('persisted observation benchmark_symbol does not match selected timeline observation event')
    }
    if (observation.monitor_definition_fingerprint !== row.monitor_definition_fingerprint) {
      throw new Error('persisted observation fingerprint does not match selected timeline row')
    }
    if (observation.monitor_id === 'data_quality_monitor_v1') {
      if (!isDataQualityObservationStatus(observation.observation_status) || !isDataQualitySignificanceStatus(observation.alert_classification) || !hasDataQualityEvidence(observation)) {
        throw new Error('persisted observation data-quality fields do not match selected timeline observation event')
      }
      if (observation.benchmark_observation != null || observation.portfolio_observation != null || observation.active_observation != null) {
        throw new Error('persisted observation data-quality artifact must not include benchmark threshold fields')
      }
    } else if (observation.monitor_id === 'benchmark_trend_overlay_v1') {
      if (observation.benchmark_symbol === 'DATA_QUALITY' || !observation.benchmark_observation || !observation.portfolio_observation || !observation.active_observation) {
        throw new Error('persisted observation benchmark trend fields do not match selected timeline observation event')
      }
    }
    setOpenState({ status: 'ready', row, observation, error: null })
    return true
  } catch (error) {
    setOpenState({ status: 'error', row, observation: null, error: formatObservationOpenFailure(error) })
    return false
  }
}

async function openAlertHistoryReviewFromTimelineReviewRow(
  row: MonitorDefinitionAlertReviewTimelineHistoryRow,
  setOpenState: (value: {
    status: 'idle' | 'loading' | 'ready' | 'error'
    row: MonitorDefinitionAlertReviewTimelineHistoryRow | null
    entry: MonitorDefinitionEvaluationHistoryEntryResponse | null
    error: string | null
  }) => void,
): Promise<boolean> {
  setOpenState({ status: 'loading', row, entry: null, error: null })
  try {
    const response = await fetch(`/api/backtests/monitor-definitions/${encodeURIComponent(row.monitor_definition_id)}/evaluation-history/${encodeURIComponent(row.history_entry_id)}`)
    const payload = await response.json()
    if (!response.ok) {
      throw new Error((payload as { detail?: string }).detail ?? 'Unable to load persisted timeline history entry')
    }
    const entryResponse = payload as MonitorDefinitionEvaluationHistoryEntryResponse
    const entry = entryResponse.item
    if (entryResponse.metadata.monitor_definition_id !== row.monitor_definition_id) {
      throw new Error('persisted history metadata monitor_definition_id does not match selected timeline history event')
    }
    if (entryResponse.metadata.retrieved_history_entry_id !== row.review_handoff.history_entry_id) {
      throw new Error('persisted history metadata retrieved_history_entry_id does not match selected timeline history event')
    }
    if (entry.monitor_definition_id !== row.monitor_definition_id) {
      throw new Error('persisted history entry monitor_definition_id does not match selected timeline history event')
    }
    if (entry.history_entry_id !== row.review_handoff.history_entry_id) {
      throw new Error('persisted history entry history_entry_id does not match selected timeline history event')
    }
    if (entry.monitor_id !== row.monitor_id) {
      throw new Error('persisted history entry monitor_id does not match selected timeline history event')
    }
    if (entry.benchmark_symbol !== row.benchmark_symbol) {
      throw new Error('persisted history entry benchmark_symbol does not match selected timeline history event')
    }
    if (entry.monitor_definition_fingerprint !== row.monitor_definition_fingerprint) {
      throw new Error('persisted history entry fingerprint does not match selected timeline row')
    }
    if (entry.monitor_id === 'data_quality_monitor_v1') {
      if (!isDataQualityObservationStatus(entry.observation_status) || !isDataQualitySignificanceStatus(entry.significance_status) || !hasDataQualityEvidence(entry)) {
        throw new Error('persisted history entry data-quality fields do not match selected timeline history event')
      }
      if (entry.benchmark_observation != null || entry.portfolio_observation != null || entry.active_observation != null) {
        throw new Error('persisted history entry data-quality artifact must not include benchmark threshold fields')
      }
    } else if (entry.monitor_id === 'benchmark_trend_overlay_v1') {
      if (entry.benchmark_symbol === 'DATA_QUALITY' || !entry.benchmark_observation || !entry.portfolio_observation || !entry.active_observation) {
        throw new Error('persisted history entry benchmark trend fields do not match selected timeline history event')
      }
    }
    setOpenState({ status: 'ready', row, entry: entryResponse, error: null })
    return true
  } catch (error) {
    setOpenState({ status: 'error', row, entry: null, error: formatAlertHistoryOpenFailure(error) })
    return false
  }
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
  const savedProposalPMSummary = assertValidSavedProposalReviewSnapshotPMSummaryMirror(
    openResponse.pm_summary,
    'Saved proposal open response pm_summary',
  )
  setWorkspaceError(null)
  setProposalArtifacts((current) => current.map((proposal) => proposal.reviewSnapshotArtifactId === openResponse.handoff.artifact_id
    ? {
        ...proposal,
        proposalCapture: openResponse.artifact.proposal_capture,
        reviewSnapshotPMSummary: savedProposalPMSummary,
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
  const [tab, setTab] = useState<AppTab>('dashboard')
  const [analysis, setAnalysis] = useState<DashboardAnalysis | null>(null)
  const [baselineAnalysis, setBaselineAnalysis] = useState<ReturnType<typeof buildPortfolioBaselineView> | null>(null)
  const [exposureAnalysis, setExposureAnalysis] = useState<ExposureAnalysis | null>(null)
  const [diagnosticsAnalysis, setDiagnosticsAnalysis] = useState<DiagnosticsEngineResponse | null>(null)
  const [exposureFactorModel, setExposureFactorModel] = useState<ExposureFactorModelResponse | null>(null)
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
  const [monitorDefinitionAlertReviewSession, setMonitorDefinitionAlertReviewSession] = useState<MonitorDefinitionAlertReviewSessionState>(idleMonitorDefinitionAlertReviewSession)
  const [recoveredAlertReviewQueue, setRecoveredAlertReviewQueue] = useState<MonitorDefinitionRecoveredAlertReviewQueueRow[]>([])
  const [activeAlertEpisodeInbox, setActiveAlertEpisodeInbox] = useState<{
    status: 'idle' | 'loading' | 'ready' | 'error'
    response: MonitorDefinitionActiveAlertEpisodeInboxResponse | null
    error: string | null
  }>({ status: 'idle', response: null, error: null })
  const [alertEpisodeHistory, setAlertEpisodeHistory] = useState<{
    status: 'idle' | 'loading' | 'ready' | 'error'
    monitorDefinitionId: string | null
    response: MonitorDefinitionAlertEpisodeHistoryResponse | null
    error: string | null
  }>({ status: 'idle', monitorDefinitionId: null, response: null, error: null })
  const [monitoringResearchHandoff, setMonitoringResearchHandoff] = useState<MonitoringResearchHandoff | null>(null)
  const [monitoringResearchHandoffDismissed, setMonitoringResearchHandoffDismissed] = useState(false)
  const [persistedConstructionArtifactReview, setPersistedConstructionArtifactReview] = useState<PersistedConstructionArtifactWorkspaceReview | null>(null)
  const [persistedOptimizerHandoffReview, setPersistedOptimizerHandoffReview] = useState<PersistedOptimizerHandoffWorkspaceReview | null>(null)
  const [workspaceOwnedResearchSessions, setWorkspaceOwnedResearchSessions] = useState<WorkspaceOwnedResearchSessions>({})
  const [workspaceResearchIntent, setWorkspaceResearchIntent] = useState<WorkspaceResearchTool | null>(null)
  const [workspaceShellActivationKey, setWorkspaceShellActivationKey] = useState(0)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const importModeRef = useRef<ImportMode>('replace')
  const userSelectedTabRef = useRef(false)
  const artifactReviewMode = isPersistedConstructionArtifactWorkspace(activeWorkspace) || isPersistedOptimizerHandoffWorkspace(activeWorkspace)
  const definitionScopedAlertReviewActive = monitorDefinitionAlertReviewSession.navigation !== null
  const dashboardSnapshot = workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot ?? null
  const importedExposureExitNode = resolveImportedExposureExitNode(
    selectedExposureSnapshotId,
    workspaceNodes,
    activeNode,
    workingDraft,
  )
  const dashboardSession = composeDashboardSession({
    result: analysis,
    exposureResult: exposureAnalysis,
    factorModel: exposureFactorModel,
    activeNode,
    workingDraft,
    lastImportedFileNames,
    restoredSession,
    importing: importingPortfolio || restoringPortfolio,
    importError,
  })
  const dashboardImportAnchorNode = getImportedSourceAnchorNode(activeNode, workspaceNodes, activeWorkspace)
  const dashboardImportSource = getNodeImportSource(dashboardImportAnchorNode, activeWorkspace)
  const dashboardAdmissionSummary = dashboardImportSource?.admissionSummary ?? dashboardSession.result?.admission_summary ?? dashboardSession.admissionSummary
  const dashboardAdmissionReviewDispositions = dashboardImportSource?.admissionReviewDispositions ?? {}
  const dashboardAdmissionSnapshotFingerprint = buildImportSnapshotFingerprint({
    portfolioSnapshot: dashboardImportAnchorNode?.portfolioSnapshot ?? null,
    importedSource: dashboardImportSource,
  })
  const dashboardAdmissionSummaryFingerprint = buildImportAdmissionSummaryFingerprint(dashboardAdmissionSummary)
  const workspaceOwnedResearchSession = activeWorkspace
    ? workspaceOwnedResearchSessions[activeWorkspace.id] ?? createWorkspaceOwnedResearchSessionRecord()
    : null
  const workflowState = activeWorkspace && workspaceOwnedResearchSession?.backtest.result ? 'Portfolio + Backtest Loaded' : activeWorkspace ? 'Portfolio Loaded' : 'Workspace Empty'

  function applyDashboardSession(session: DashboardSession) {
    setAnalysis(session.result)
    setExposureAnalysis(session.exposureResult)
    setExposureFactorModel(session.factorModel)
    setLastImportedFileNames(session.lastImportedFileNames)
    setRestoredSession(session.restoredSession)
  }

  function ensureWorkspaceOwnedResearchSession(workspaceId: string) {
    setWorkspaceOwnedResearchSessions((current) => {
      if (current[workspaceId]) return current
      return {
        ...current,
        [workspaceId]: createWorkspaceOwnedResearchSessionRecord(),
      }
    })
  }

  function updateWorkspaceOwnedResearchSession<K extends keyof WorkspaceOwnedResearchSessions[string]>(
    workspaceId: string,
    key: K,
    update: SessionStateUpdate<WorkspaceOwnedResearchSessions[string][K]>,
  ) {
    setWorkspaceOwnedResearchSessions((current) => {
      const existing = current[workspaceId] ?? createWorkspaceOwnedResearchSessionRecord()
      return {
        ...current,
        [workspaceId]: {
          ...existing,
          [key]: applySessionStateUpdate(existing[key], update),
        },
      }
    })
  }

  function routeIntoWorkspace(requestedResearchTool: WorkspaceResearchTool | null = null) {
    setWorkspaceResearchIntent(activeWorkspace ? requestedResearchTool : null)
    setTab('workspace')
  }

  function handleTabChange(nextTab: AppTab) {
    userSelectedTabRef.current = true
    if (isWorkspaceOwnedResearchTab(nextTab)) {
      routeIntoWorkspace(nextTab)
      return
    }
    if (nextTab === 'workspace') {
      setWorkspaceShellActivationKey((current) => current + 1)
    }
    if (nextTab !== 'workspace') {
      setWorkspaceResearchIntent(null)
    }
    setTab(nextTab)
  }

  async function restoreImportedWorkspaceFromPersistedState(
    restoredWorkspaceState: WorkspaceState,
    options?: {
      isActive?: () => boolean
      restoredSession?: boolean
    },
  ) {
    const isActive = options?.isActive ?? (() => true)
    const sessionRestored = options?.restoredSession ?? true
    const [workspace, node, persistedDraft] = await Promise.all([
      getWorkspace(restoredWorkspaceState.workspaceId),
      getNode(restoredWorkspaceState.activeNodeId),
      getDraft(restoredWorkspaceState.workspaceId),
    ])

    if (!isActive()) return
    if (!workspace || !node) {
      throw new Error('Unable to restore previous portfolio workspace')
    }

    let nodes: PortfolioNode[]
    if (sessionRestored) {
      const authoritativeNodes = await getWorkspaceNodes(workspace.id).catch(() => {
        throw new Error(missingPersistedStartupNodeListRestoreMessage)
      })
      if (!authoritativeNodes.length) {
        throw new Error(missingPersistedStartupNodeListRestoreMessage)
      }
      nodes = authoritativeNodes
    } else {
      const persistedNodes = await getWorkspaceNodes(workspace.id).catch(() => [node])
      nodes = persistedNodes.length ? persistedNodes : [node]
    }
    const startupTruth = resolveImportedWorkspaceStartupTruth({
      sessionRestored,
      isImportedWorkspace: isImportedWorkspaceSource(workspace.source),
      restoredWorkspaceState,
      authoritativeNodes: nodes,
      restoredDraft: persistedDraft,
      restoredActiveNode: node,
    })
    const draft = startupTruth.restoredDraft
    const restoredProposalArtifacts = await loadWorkspaceProposalArtifacts(workspace).catch((error) => {
      throw new Error(formatSavedProposalRestoreFailure(error))
    })

    if (!isActive()) return

    setActiveWorkspace(workspace)
    ensureWorkspaceOwnedResearchSession(workspace.id)
    setActiveNode(node)
    setWorkingDraft(draft)
    setPersistedConstructionArtifactReview(null)
    setPersistedOptimizerHandoffReview(null)
    setProposalArtifacts(restoredProposalArtifacts)
    setOpenedSavedProposalArtifactId(null)
    if (sessionRestored && isImportedWorkspaceSource(workspace.source) && !userSelectedTabRef.current) {
      setTab('dashboard')
    }
    if (restoredWorkspaceState.monitorDefinitionAlertReview) {
      const restoredReviewState = restoredWorkspaceState.monitorDefinitionAlertReview
      const restoredTimeline = restoredReviewState.cachedTimeline
      assertMonitorDefinitionAlertReviewTimelineResponse(restoredTimeline, restoredReviewState.monitorDefinitionId)
      const selectedTimelineRow = resolveSelectedMonitorDefinitionTimelineRow(restoredReviewState, restoredTimeline)
      setMonitorDefinitionAlertReviewSession({
        navigation: {
          monitorDefinitionId: restoredReviewState.monitorDefinitionId,
          selectedEvent: restoredReviewState.selectedEvent,
        },
        timeline: restoredTimeline,
        timelineStatus: 'ready',
        timelineError: null,
        latestObservation: idleMonitorDefinitionAlertReviewSession.latestObservation,
        alertHistory: idleMonitorDefinitionAlertReviewSession.alertHistory,
      })
      if (selectedTimelineRow.event_kind === 'latest_observation_event') {
        await openLatestObservationFromTimelineRow(selectedTimelineRow, (value) => {
          setMonitorDefinitionAlertReviewSession((current) => ({
            ...current,
            latestObservation: value,
            alertHistory: idleMonitorDefinitionAlertReviewSession.alertHistory,
          }))
        })
      } else {
        await openAlertHistoryReviewFromTimelineRow(selectedTimelineRow, (value) => {
          setMonitorDefinitionAlertReviewSession((current) => ({
            ...current,
            latestObservation: idleMonitorDefinitionAlertReviewSession.latestObservation,
            alertHistory: value,
          }))
        })
      }
    } else {
      setMonitorDefinitionAlertReviewSession(idleMonitorDefinitionAlertReviewSession)
    }

    if (!isActive()) return

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

    if (!isActive()) return

    const restoredImportedFileNames = getWorkspaceImportedFileNames(workspace, node)
    let restoredDashboardSession = composeDashboardSession({
      result: null,
      exposureResult: null,
      factorModel: null,
      activeNode: node,
      workingDraft: draft,
      lastImportedFileNames: restoredImportedFileNames,
      restoredSession: sessionRestored,
      importing: false,
      importError: null,
    })

    const resolvedSnapshot = resolveSelectedSnapshot(
      sessionRestored && isImportedWorkspaceSource(workspace.source)
        ? startupTruth.dashboardSelectedSnapshotId
        : restoredWorkspaceState.selectedExposureSnapshotId,
      nodes,
      node,
      draft,
    )
    if (!resolvedSnapshot) {
      applyDashboardSession(restoredDashboardSession)
      return
    }

    if (resolvedSnapshot.snapshot.positions.length || resolvedSnapshot.snapshot.cashBalances.length) {
      const selectedNode = resolvedSnapshot.id === 'draft'
        ? (draft ? nodes.find((item) => item.id === draft.baseNodeId) ?? node : node)
        : nodes.find((item) => item.id === resolvedSnapshot.id) ?? node
      const selectedSource = getEffectiveNodeImportSource(selectedNode, nodes, workspace)
      const selectedDirectSource = getDirectNodeImportSource(selectedNode, workspace)
      const restoredAnalytics = await analyzeRestoredSnapshot(
        resolvedSnapshot.snapshot,
        resolvedSnapshot.id,
        resolveEffectiveHistorySource(selectedSource, selectedDirectSource) ?? getWorkspaceHistorySource(workspace) ?? null,
        workspace.id,
        { strictDefinitionScopedAlertReview: Boolean(restoredWorkspaceState.monitorDefinitionAlertReview) },
      )

      if (!isActive()) return

      setDiagnosticsAnalysis(restoredAnalytics.diagnostics)
      setBaselineAnalysis(restoredAnalytics.baselineView)
      setSelectedExposureSnapshotId(restoredAnalytics.snapshotId)
      try {
        await setSelectedExposureSnapshot({ workspaceId: workspace.id, snapshotId: restoredAnalytics.snapshotId })
      } catch {
        // Keep analytics usable when local persistence is unavailable.
      }
      restoredDashboardSession = composeDashboardSession({
        result: restoredAnalytics.result,
        exposureResult: restoredAnalytics.exposureResult,
        factorModel: restoredAnalytics.factorModel,
        activeNode: node,
        workingDraft: draft,
        lastImportedFileNames: restoredImportedFileNames,
        restoredSession: sessionRestored,
        importing: false,
        importError: null,
      })
    } else {
      setSelectedExposureSnapshotId(resolvedSnapshot.id)
    }

    if (!isActive()) return
    applyDashboardSession(restoredDashboardSession)
  }

  async function beginMonitorDefinitionAlertReviewNavigation(input: {
    monitorDefinitionId: string
    selectedEvent: MonitorDefinitionAlertReviewTimelineSelection | null
  }) {
    const monitorDefinitionId = input.monitorDefinitionId.trim()
    if (!monitorDefinitionId) {
      const message = 'Unable to load alert review timeline: monitor definition id is required'
      setMonitorDefinitionAlertReviewSession({
        navigation: null,
        timeline: null,
        timelineStatus: 'error',
        timelineError: message,
        latestObservation: { status: 'idle', row: null, observation: null, error: null },
        alertHistory: { status: 'idle', row: null, entry: null, error: null },
      })
      return
    }

    setMonitorDefinitionAlertReviewSession((current) => ({
      navigation: {
        monitorDefinitionId,
        selectedEvent: input.selectedEvent,
      },
      timeline: current.timeline,
      timelineStatus: 'loading',
      timelineError: null,
      latestObservation: !input.selectedEvent || input.selectedEvent.eventKind === 'evaluation_history_event'
        ? { status: 'idle', row: null, observation: null, error: null }
        : current.latestObservation,
      alertHistory: !input.selectedEvent || input.selectedEvent.eventKind === 'latest_observation_event'
        ? { status: 'idle', row: null, entry: null, error: null }
        : current.alertHistory,
    }))

    try {
      const timeline = await loadMonitorDefinitionAlertReviewTimeline(monitorDefinitionId)
      setMonitorDefinitionAlertReviewSession((current) => ({
        ...current,
        timeline,
        timelineStatus: 'ready',
        timelineError: null,
      }))

      const selectedRow = input.selectedEvent
        ? resolveMonitorDefinitionTimelineRowFromSelection(timeline, input.selectedEvent)
        : resolveDefaultMonitorDefinitionTimelineObservationRow(timeline)
      if (!selectedRow) {
        return
      }

      const opened = selectedRow.event_kind === 'latest_observation_event'
        ? await openLatestObservationFromTimelineRow(selectedRow, (value) => {
          setMonitorDefinitionAlertReviewSession((current) => ({
            ...current,
            latestObservation: value,
          }))
        })
        : await openAlertHistoryReviewFromTimelineRow(selectedRow, (value) => {
          setMonitorDefinitionAlertReviewSession((current) => ({
            ...current,
            alertHistory: value,
          }))
        })

      if (opened && activeWorkspace) {
        const reviewState = buildMonitorDefinitionAlertReviewWorkspaceState({
          monitorDefinitionId,
          timeline,
          row: selectedRow,
        })
        void saveMonitorDefinitionAlertReviewWorkspaceState({
          workspaceId: activeWorkspace.id,
          reviewState,
        }).catch(() => undefined)
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to load alert review timeline'
      setMonitorDefinitionAlertReviewSession((current) => ({
        ...current,
        timeline: null,
        timelineStatus: 'error',
        timelineError: message,
        latestObservation: input.selectedEvent?.eventKind === 'latest_observation_event'
          ? { status: 'error', row: null, observation: null, error: formatObservationOpenFailure(error) }
          : current.latestObservation,
        alertHistory: input.selectedEvent?.eventKind === 'evaluation_history_event'
          ? { status: 'error', row: null, entry: null, error: formatAlertHistoryOpenFailure(error) }
          : current.alertHistory,
      }))
    }
  }

  async function handleOpenLatestObservation(row: MonitorDefinitionAlertReviewTimelineObservationRow) {
    await beginMonitorDefinitionAlertReviewNavigation({
      monitorDefinitionId: row.monitor_definition_id,
      selectedEvent: {
        eventKind: 'latest_observation_event',
        observationId: row.observation_id,
      },
    })
  }

  async function handleOpenAlertHistoryReview(row: MonitorDefinitionAlertReviewTimelineHistoryRow) {
    await beginMonitorDefinitionAlertReviewNavigation({
      monitorDefinitionId: row.monitor_definition_id,
      selectedEvent: {
        eventKind: 'evaluation_history_event',
        historyEntryId: row.history_entry_id,
      },
    })
  }

  async function handleReopenRecoveredAlertReview(row: MonitorDefinitionRecoveredAlertReviewQueueRow) {
    await reopenRecoveredAlertReviewRow(row, beginMonitorDefinitionAlertReviewNavigation)
  }

  async function handleOpenActiveAlertEpisode(row: MonitorDefinitionActiveAlertEpisodeInboxRow) {
    await openActiveAlertEpisodeInboxRow(row, beginMonitorDefinitionAlertReviewNavigation)
  }

  async function handleOpenAlertEpisodeHistory(row: MonitorDefinitionAlertEpisodeHistoryRow) {
    await openAlertEpisodeHistoryRow(row, beginMonitorDefinitionAlertReviewNavigation)
  }

  async function handleLoadOlderAlertEpisodeHistory() {
    const monitorDefinitionId = alertEpisodeHistory.monitorDefinitionId
    const beforeEpisodeId = alertEpisodeHistory.response?.metadata.next_before_episode_id ?? null
    if (!monitorDefinitionId || !beforeEpisodeId) return

    setAlertEpisodeHistory((current) => ({
      status: 'loading',
      monitorDefinitionId,
      response: current.response,
      error: null,
    }))
    try {
      const payload = await loadMonitorDefinitionAlertEpisodeHistory(monitorDefinitionId, beforeEpisodeId)
      setAlertEpisodeHistory((current) => {
        if (current.monitorDefinitionId !== monitorDefinitionId) return current
        return { status: 'ready', monitorDefinitionId, response: payload, error: null }
      })
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to load alert episode history'
      setAlertEpisodeHistory((current) => {
        if (current.monitorDefinitionId !== monitorDefinitionId) return current
        return { status: 'error', monitorDefinitionId, response: current.response, error: message }
      })
    }
  }

  async function analyzeExposureSnapshot(
    snapshot: WorkingDraft['portfolioSnapshot'],
    snapshotId: string,
    workspaceId?: string,
    options?: {
      preserveDashboardAnalysis?: boolean
      historySource?: ImportedHistorySource | null
      strictDefinitionScopedAlertReview?: boolean
    },
  ) {
    const [exposure, diagnostics] = await Promise.all([
      runExposureEngine(snapshot),
      options?.historySource?.kind === 'imported_replay'
        ? runImportedDiagnosticsEngine(options.historySource.importedHistorySnapshot)
        : runDiagnosticsEngine(snapshot, options?.historySource?.historyContext ?? getWorkspaceHistorySource(activeWorkspace)?.historyContext ?? null),
    ])
    const exposureView = composeExposureView(exposure, diagnostics)
    let factorModel: ExposureFactorModelResponse | null
    try {
      factorModel = buildExposureFactorModel(exposureView)
    } catch (error) {
      if (options?.strictDefinitionScopedAlertReview) {
        const message = error instanceof Error ? error.message : 'exposure factor model inputs are malformed'
        throw new Error(formatDefinitionScopedAlertReviewAnalyticsRestoreFailure(`definition-scoped alert review analytics require authoritative exposure inputs; ${message}`))
      }
      factorModel = null
    }
    setExposureAnalysis(exposureView)
    setDiagnosticsAnalysis(diagnostics)
    setExposureFactorModel(factorModel)
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

  async function handleExposureSnapshotChange(snapshotId: string) {
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
        strictDefinitionScopedAlertReview: definitionScopedAlertReviewActive,
      })
      return
    }

    const node = workspaceNodes.find((item) => item.id === snapshotId) ?? await getNode(snapshotId)
    if (!node?.portfolioSnapshot) return
    const nodeSource = getEffectiveNodeImportSource(node, workspaceNodes, activeWorkspace)
    const directNodeSource = getDirectNodeImportSource(node, activeWorkspace)
    await analyzeExposureSnapshot(node.portfolioSnapshot, snapshotId, activeWorkspace.id, {
      historySource: resolveEffectiveHistorySource(nodeSource, directNodeSource),
      preserveDashboardAnalysis: true,
      strictDefinitionScopedAlertReview: definitionScopedAlertReviewActive,
    })
  }

  async function analyzeRestoredSnapshot(
    snapshot: WorkingDraft['portfolioSnapshot'],
    snapshotId: string,
    historySource: ImportedHistorySource | null | undefined,
    _workspaceId?: string,
    options?: {
      strictDefinitionScopedAlertReview?: boolean
    },
  ) {
    let diagnosticsHistoryContext: ImportedHistoryContext | null = historySource?.historyContext ?? null
    let diagnostics: DiagnosticsEngineResponse
    let dashboardHistory: DashboardHistoryEngineResponse | null

    if (historySource?.kind === 'imported_replay') {
      try {
        [diagnostics, dashboardHistory] = await Promise.all([
          runImportedDiagnosticsEngine(historySource.importedHistorySnapshot),
          runImportedDashboardHistory(historySource.importedHistorySnapshot),
        ])
      } catch (error) {
        if (options?.strictDefinitionScopedAlertReview) {
          const message = error instanceof Error ? error.message : 'imported diagnostics or dashboard history inputs are invalid'
          throw new Error(formatDefinitionScopedAlertReviewAnalyticsRestoreFailure(`definition-scoped alert review analytics require authoritative imported diagnostics and dashboard history inputs; ${message}`))
        }
        diagnostics = await runDiagnosticsEngine(snapshot, diagnosticsHistoryContext)
        dashboardHistory = diagnosticsHistoryContext
          ? await runDashboardHistoryEngine(snapshot, diagnosticsHistoryContext)
          : null
      }
    } else {
      diagnostics = await runDiagnosticsEngine(snapshot, diagnosticsHistoryContext)
      dashboardHistory = diagnosticsHistoryContext
        ? await runDashboardHistoryEngine(snapshot, diagnosticsHistoryContext)
        : null
    }

    const exposure = await runExposureEngine(snapshot)

    const exposureView = composeExposureView(exposure, diagnostics)
    let factorModel: ExposureFactorModelResponse | null
    try {
      factorModel = buildExposureFactorModel(exposureView)
    } catch (error) {
      if (options?.strictDefinitionScopedAlertReview) {
        const message = error instanceof Error ? error.message : 'exposure factor model inputs are malformed'
        throw new Error(formatDefinitionScopedAlertReviewAnalyticsRestoreFailure(`definition-scoped alert review analytics require authoritative exposure inputs; ${message}`))
      }
      factorModel = null
    }
    const nextAnalysis = dashboardHistory
      ? composeDashboardAnalysisWithHistory(exposure, dashboardHistory)
      : composeDashboardAnalysisFromEngines(exposure, diagnostics)
    const baselineView = buildPortfolioBaselineView(exposure)

    return {
      diagnostics,
      baselineView,
      result: nextAnalysis,
      exposureResult: exposureView,
      factorModel,
      snapshotId,
    }
  }

  useEffect(() => {
    let active = true
    let startupWorkspaceState: WorkspaceState | null = null

    void (async () => {
      const search = globalThis.location?.search ?? ''
      const constructionArtifactId = new URLSearchParams(search).get(persistedConstructionArtifactQueryKey)
      if (constructionArtifactId) {
        try {
          await openPersistedConstructionArtifactReviewById(constructionArtifactId, {
            setActiveWorkspace,
            ensureWorkspaceOwnedResearchSession,
            setActiveNode,
            setWorkingDraft,
            setWorkspaceNodes,
            setPersistedConstructionArtifactReview,
            setPersistedOptimizerHandoffReview,
            setHypotheticalReplacementReplay,
            setProposalArtifacts,
            setOpenedSavedProposalArtifactId,
            setActiveThesis,
            setMonitorDefinitionAlertReviewSession,
            setCandidateImprovementDraft,
            setIntentBoundSeededEtfReplacementRankingDraft,
            setReplacementIntentDraft,
            setFormedCandidateArtifact,
            setConstructedCandidateArtifact,
            setConstructionConstraintValidationArtifact,
            setSelectedConstructionRuleId,
            setAnalysis,
            setBaselineAnalysis,
            setAllocationBacktestRun,
            setSelectedExposureSnapshotId,
            setLastImportedFileNames,
            setTab,
            setRestoredSession,
          })
          if (!active) return
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
          const validationPayload = await validationResponse.json()
          if (!validationResponse.ok) {
            throw new Error((validationPayload as { detail?: string }).detail ?? 'Unable to open persisted optimizer handoff review')
          }
          const validation = validationPayload as OptimizerHandoffValidationResponse
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
          const previewPayload = await previewResponse.json()
          if (!previewResponse.ok) {
            throw new Error((previewPayload as { detail?: string }).detail ?? 'Unable to open persisted optimizer handoff review')
          }
          const handoffReplay = previewPayload as OptimizerHandoffReplayResponse
          assertOptimizerHandoffReplayMatchesReference(handoffReplay, optimizerHandoffReference)
          const created = await createWorkspaceFromPersistedOptimizerHandoff({ handoffReference: optimizerHandoffReference, validation, replay: handoffReplay })
          if (!active) return
          setActiveWorkspace(created.workspace)
          ensureWorkspaceOwnedResearchSession(created.workspace.id)
          setActiveNode(created.rootNode)
          setWorkingDraft(null)
          setWorkspaceNodes([created.rootNode])
          setPersistedConstructionArtifactReview(null)
          setPersistedOptimizerHandoffReview(created.review)
          setHypotheticalReplacementReplay(null)
          setProposalArtifacts([])
          setOpenedSavedProposalArtifactId(null)
          setActiveThesis(null)
          setMonitorDefinitionAlertReviewSession(idleMonitorDefinitionAlertReviewSession)
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
      startupWorkspaceState = restoredWorkspaceState

      if (!active || !restoredWorkspaceState) {
        return
      }

      const [workspace, node] = await Promise.all([
        getWorkspace(restoredWorkspaceState.workspaceId),
        getNode(restoredWorkspaceState.activeNodeId),
      ])

      if (!active || !workspace || !node) {
        return
      }

      if (isPersistedConstructionArtifactWorkspaceSource(workspace.source)) {
        const review = await getPersistedConstructionArtifactWorkspaceReview(workspace.id)
        if (!active) {
          return
        }
        if (!review) {
          setImportError(missingPersistedConstructionArtifactReviewRestoreMessage)
          setRestoringPortfolio(false)
          return
        }
        const normalizedWorkspaceState = await normalizeLegacyPersistedConstructionArtifactWorkspaceCache({ workspace, node, review })
        if (!active) {
          return
        }
        const normalizedNodes = await getWorkspaceNodes(workspace.id).catch(() => [normalizedWorkspaceState.node])
        setActiveWorkspace(normalizedWorkspaceState.workspace)
        ensureWorkspaceOwnedResearchSession(normalizedWorkspaceState.workspace.id)
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
        setMonitorDefinitionAlertReviewSession(idleMonitorDefinitionAlertReviewSession)
        setCandidateImprovementDraft(null)
        setIntentBoundSeededEtfReplacementRankingDraft(null)
        setReplacementIntentDraft(null)
        setFormedCandidateArtifact(null)
        setConstructedCandidateArtifact(null)
        setConstructionConstraintValidationArtifact(null)
        setSelectedConstructionRuleId(defaultConstructionRuleId)
        setSelectedExposureSnapshotId(normalizedWorkspaceState.node.id)
        setTab('workspace')
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
        ensureWorkspaceOwnedResearchSession(normalizedWorkspaceState.workspace.id)
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
        setMonitorDefinitionAlertReviewSession(idleMonitorDefinitionAlertReviewSession)
        setCandidateImprovementDraft(null)
        setIntentBoundSeededEtfReplacementRankingDraft(null)
        setReplacementIntentDraft(null)
        setFormedCandidateArtifact(null)
        setConstructedCandidateArtifact(null)
        setConstructionConstraintValidationArtifact(null)
        setSelectedConstructionRuleId(defaultConstructionRuleId)
        setSelectedExposureSnapshotId(normalizedWorkspaceState.node.id)
        setTab('workspace')
        return
      }

      await restoreImportedWorkspaceFromPersistedState(restoredWorkspaceState, {
        isActive: () => active,
        restoredSession: true,
      })
      })()
      .catch((caughtError) => {
        if (active) {
          const message = caughtError instanceof Error ? caughtError.message : 'Unable to restore previous portfolio workspace'
          if (message.startsWith('Unable to reopen saved proposal:') || message.startsWith('Unable to restore previous portfolio workspace:')) {
            if (startupWorkspaceState) {
              void setSelectedExposureSnapshot({
                workspaceId: startupWorkspaceState.workspaceId,
                snapshotId: startupWorkspaceState.activeNodeId,
              }).catch(() => undefined)
            }
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

  async function openImportPicker(mode: ImportMode) {
    if (!isTauriRuntime()) {
      importModeRef.current = mode
      fileInputRef.current?.click()
      return
    }

    try {
      importModeRef.current = mode
      const files = await resolveTauriImportFiles()
      if (!files.length) {
        return
      }
      await processImportedFiles(files, mode)
    } catch (caughtError) {
      setImportError(caughtError instanceof Error ? caughtError.message : 'Import failed')
    }
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
    setMonitorDefinitionAlertReviewSession(idleMonitorDefinitionAlertReviewSession)
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
    setMonitorDefinitionAlertReviewSession(idleMonitorDefinitionAlertReviewSession)
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
    if (handoff.monitorDefinitionReview) {
      void beginMonitorDefinitionAlertReviewNavigation({
        monitorDefinitionId: handoff.monitorDefinitionReview.monitorDefinitionId,
        selectedEvent: null,
      })
    }
    setTab('workspace')
  }

  useEffect(() => {
    if (tab !== 'workspace' || !activeWorkspace || artifactReviewMode) {
      setRecoveredAlertReviewQueue([])
      setActiveAlertEpisodeInbox({ status: 'idle', response: null, error: null })
      return
    }

    let active = true
    setActiveAlertEpisodeInbox({ status: 'loading', response: null, error: null })
    void loadMonitorDefinitionRecoveredAlertReviewQueue()
      .then((payload) => {
        if (!active) return
        setRecoveredAlertReviewQueue(payload.items)
      })
      .catch(() => {
        if (!active) return
        setRecoveredAlertReviewQueue([])
      })
    void loadMonitorDefinitionActiveAlertEpisodeInbox()
      .then((payload) => {
        if (!active) return
        setActiveAlertEpisodeInbox({ status: 'ready', response: payload, error: null })
      })
      .catch((error) => {
        if (!active) return
        const message = error instanceof Error ? error.message : 'Unable to load active alert episode inbox'
        setActiveAlertEpisodeInbox({ status: 'error', response: null, error: message })
      })
    return () => {
      active = false
    }
  }, [activeWorkspace, artifactReviewMode, tab])

  useEffect(() => {
    const monitorDefinitionId = monitorDefinitionAlertReviewSession.navigation?.monitorDefinitionId ?? null
    if (!monitorDefinitionId || tab !== 'workspace' || !activeWorkspace || artifactReviewMode) {
      setAlertEpisodeHistory({ status: 'idle', monitorDefinitionId: null, response: null, error: null })
      return
    }

    let active = true
    setAlertEpisodeHistory({ status: 'loading', monitorDefinitionId, response: null, error: null })
    void loadMonitorDefinitionAlertEpisodeHistory(monitorDefinitionId)
      .then((payload) => {
        if (!active) return
        setAlertEpisodeHistory((current) => {
          if (current.monitorDefinitionId !== monitorDefinitionId) return current
          return { status: 'ready', monitorDefinitionId, response: payload, error: null }
        })
      })
      .catch((error) => {
        if (!active) return
        const message = error instanceof Error ? error.message : 'Unable to load alert episode history'
        setAlertEpisodeHistory((current) => {
          if (current.monitorDefinitionId !== monitorDefinitionId) return current
          return { status: 'error', monitorDefinitionId, response: null, error: message }
        })
      })
    return () => {
      active = false
    }
  }, [activeWorkspace, artifactReviewMode, monitorDefinitionAlertReviewSession.navigation?.monitorDefinitionId, tab])

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
        const reviewSnapshotPayload = await reviewSnapshotResponse.json()
        if (!reviewSnapshotResponse.ok) {
          throw new Error((reviewSnapshotPayload as { detail?: string }).detail ?? 'Failed to create review snapshot artifact')
        }
        const reviewSnapshotArtifact = assertReviewSnapshotCreateArtifact(reviewSnapshotPayload)
      const savedProposalPMSummary = assertValidSavedProposalReviewSnapshotPMSummaryMirror(
        reviewSnapshotArtifact.pm_summary,
        'Saved proposal review snapshot artifact pm_summary',
      )
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
        reviewSnapshotPMSummary: savedProposalPMSummary,
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
    await analyzeExposureSnapshot(snapshot, 'draft', activeWorkspace?.id, { strictDefinitionScopedAlertReview: definitionScopedAlertReviewActive })
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
      ensureWorkspaceOwnedResearchSession(nextWorkspace.id)
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
    ensureWorkspaceOwnedResearchSession(saved.workspace.id)
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
      await analyzeExposureSnapshot(nextDraft.portfolioSnapshot, 'draft', activeWorkspace.id, { strictDefinitionScopedAlertReview: definitionScopedAlertReviewActive })
    }
  }

  async function handleOpenNode(nodeId: string) {
    if (!activeWorkspace) return
    await persistActiveNode({ workspaceId: activeWorkspace.id, nodeId, createDraftFromNode: true })
    const [nextWorkspace, nextNodes, nextNode, nextDraft] = await Promise.all([getWorkspace(activeWorkspace.id), getWorkspaceNodes(activeWorkspace.id), getNode(nodeId), getDraft(activeWorkspace.id)])
    const resolvedWorkspace = nextWorkspace ?? activeWorkspace
    if (nextWorkspace) {
      setActiveWorkspace(nextWorkspace)
      ensureWorkspaceOwnedResearchSession(nextWorkspace.id)
    }
    setWorkspaceNodes(nextNodes)
    setActiveNode(nextNode)
    setWorkingDraft(nextDraft)
    await loadActiveThesisForWorkspace(resolvedWorkspace, setActiveThesis)
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
    const nextImportedFileNames = getWorkspaceImportedFileNames(resolvedWorkspace, nextNode)
    const dashboardSnapshot = nextDraft?.portfolioSnapshot ?? nextNode?.portfolioSnapshot ?? null
    const dashboardSnapshotId = nextDraft ? 'draft' : nextNode?.id ?? null
    if (dashboardSnapshot && dashboardSnapshotId) {
      const nodeSource = getEffectiveNodeImportSource(nextNode, nextNodes, resolvedWorkspace)
      const directNodeSource = getDirectNodeImportSource(nextNode, resolvedWorkspace)
      const nextDashboardAnalytics = await analyzeRestoredSnapshot(
        dashboardSnapshot,
        dashboardSnapshotId,
        resolveEffectiveHistorySource(nodeSource, directNodeSource),
        activeWorkspace.id,
        { strictDefinitionScopedAlertReview: definitionScopedAlertReviewActive },
      )
      setDiagnosticsAnalysis(nextDashboardAnalytics.diagnostics)
      setBaselineAnalysis(nextDashboardAnalytics.baselineView)
      setSelectedExposureSnapshotId(nextDashboardAnalytics.snapshotId)
      try {
        await setSelectedExposureSnapshot({ workspaceId: activeWorkspace.id, snapshotId: nextDashboardAnalytics.snapshotId })
      } catch {
        // Keep analytics usable when local persistence is unavailable.
      }
      applyDashboardSession(composeDashboardSession({
        result: nextDashboardAnalytics.result,
        exposureResult: nextDashboardAnalytics.exposureResult,
        factorModel: nextDashboardAnalytics.factorModel,
        activeNode: nextNode,
        workingDraft: nextDraft,
        lastImportedFileNames: nextImportedFileNames,
        restoredSession: false,
        importing: false,
        importError,
      }))
      return
    }

    applyDashboardSession(composeDashboardSession({
      result: analysis,
      exposureResult: exposureAnalysis,
      factorModel: exposureFactorModel,
      activeNode: nextNode,
      workingDraft: nextDraft,
      lastImportedFileNames: nextImportedFileNames,
      restoredSession: false,
      importing: false,
      importError,
    }))
  }

  async function processImportedFiles(files: File[], mode: ImportMode) {
    if (!files.length) {
      return
    }

    importModeRef.current = mode
    setImportingPortfolio(true)
    setImportError(null)
    setExposureAnalysis(null)
    setExposureFactorModel(null)
    setTab('dashboard')

    try {
      const requestBody = buildImportFormData(files)
      const response = await (async () => {
        if (!isTauriRuntime()) {
          return fetch('/api/portfolios/import/interactive-brokers/analyze-upload', {
            method: 'POST',
            body: requestBody,
          })
        }

        const abortController = new AbortController()
        let timedOut = false
        const timeoutHandle = window.setTimeout(() => {
          timedOut = true
          abortController.abort()
        }, tauriAnalyzeUploadTimeoutMs)

        try {
          return await fetch('/api/portfolios/import/interactive-brokers/analyze-upload', {
            method: 'POST',
            body: requestBody,
            signal: abortController.signal,
          })
        } catch (error) {
          throw mapTauriAnalyzeUploadError(error, timedOut)
        } finally {
          window.clearTimeout(timeoutHandle)
        }
      })()
      const responsePayload = await response.json()

      if (!response.ok) {
        throw new Error((responsePayload as { detail?: string }).detail ?? 'Import failed')
      }

      const nextAnalysis = responsePayload as ImportedBootstrapResponse
      const importedViews = projectImportedBootstrap(nextAnalysis)
      const importedFileNames = files.map((file) => file.name)
      const importedSnapshot = buildPortfolioSnapshotFromAnalysis(importedViews.workspace, importedFileNames)
      if (mode === 'add_snapshot') {
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
          admissionSummary: nextAnalysis.admission_summary,
          name: buildImportedSnapshotName(nextAnalysis.snapshot),
        })
        setLoadedStatementFiles(files)
        await restoreImportedWorkspaceFromPersistedState(savedNode.workspaceState, { restoredSession: false })
        return
      }

      const workspaceResult = await createWorkspaceFromImport({
        analysis: importedViews.workspace,
        importedFileNames,
        historyContext: importedViews.historyContext,
        importedHistorySnapshot: nextAnalysis.snapshot,
      })
      setLoadedStatementFiles(files)
      await restoreImportedWorkspaceFromPersistedState(workspaceResult.workspaceState, { restoredSession: false })
    } catch (caughtError) {
      setImportError(caughtError instanceof Error ? caughtError.message : 'Import failed')
    } finally {
      setImportingPortfolio(false)
    }
  }

  async function handleImportFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (!selectedFiles.length) {
      return
    }

    await processImportedFiles(selectedFiles, importModeRef.current)
  }

  return (
    <main className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Portfolio Workstation</p>
          <p className="helper workflow-status-text">{workflowState}</p>
        </div>

        <div className="topbar-meta">
          <span className="status-dot" />
          <span>Local Quant Engine</span>
        </div>
      </header>

      <input ref={fileInputRef} type="file" accept="application/pdf,.pdf" hidden multiple onChange={handleImportFileChange} />

      <nav className="tab-bar main-menu" aria-label="Main workspace tabs">
        {appTabs.map((appTab) => (
          <button
            key={appTab.id}
            className={`tab-button${tab === appTab.id ? ' active' : ''}`}
            aria-current={tab === appTab.id ? 'page' : undefined}
            onClick={() => handleTabChange(appTab.id)}
          >
            {appTab.label}
          </button>
        ))}
      </nav>

      {tab === 'dashboard' ? (
        <section className="grid grid-single">
          <DashboardPanel
            result={dashboardSession.result}
            exposureResult={dashboardSession.exposureResult}
            factorModel={dashboardSession.factorModel}
            activeNodeKind={dashboardSession.activeNodeKind}
            admissionSummary={dashboardAdmissionSummary}
            admissionReviewDispositions={dashboardAdmissionReviewDispositions}
            admissionSnapshotFingerprint={dashboardAdmissionSnapshotFingerprint}
            admissionSummaryFingerprint={dashboardAdmissionSummaryFingerprint}
            importing={dashboardSession.importing}
            importError={dashboardSession.importError}
            lastImportedFileNames={dashboardSession.lastImportedFileNames}
            restoredSession={dashboardSession.restoredSession}
            onImportPortfolio={artifactReviewMode ? undefined : () => openImportPicker('replace')}
            onAppendStatement={artifactReviewMode ? undefined : dashboardSnapshot && activeWorkspace ? () => openImportPicker('add_snapshot') : undefined}
            onClearImportedSession={artifactReviewMode ? undefined : activeWorkspace ? handleClearImportedSession : undefined}
            onResetLocalDatabase={handleResetLocalDatabase}
            detailEligible={dashboardSession.detailEligible}
            onOpenDetailedReview={() => {
              if (!isDashboardDetailedReviewEligible(dashboardSession.result, dashboardSession.activeNodeKind)) return
              routeIntoWorkspace()
            }}
            onSaveAdmissionReviewDisposition={async (disposition) => {
              if (!activeWorkspace) return
              const saved = await saveImportAdmissionReviewDisposition({
                workspaceId: activeWorkspace.id,
                nodeId: dashboardImportAnchorNode?.id ?? null,
                disposition,
              })
              setActiveWorkspace(saved.workspace)
              if (saved.node) {
                setWorkspaceNodes((nodes) => nodes.map((node) => node.id === saved.node?.id ? saved.node : node))
                if (saved.node.id === activeNode?.id) setActiveNode(saved.node)
              }
            }}
          />
        </section>
      ) : null}

      {tab === 'exposure' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Exposure</p><p className="helper">Loading exposure analytics...</p></section>}>
            <ExposurePanel
              result={exposureAnalysis}
              snapshotOptions={[
                ...(workingDraft ? [{ id: 'draft', label: formatWorkingDraftLabel(activeNode, workspaceNodes) }] : []),
                ...workspaceNodes.map((node) => ({ id: node.id, label: formatVariantNodeLabel(node, workspaceNodes) })),
              ]}
              selectedSnapshotId={selectedExposureSnapshotId}
              snapshotExitOption={importedExposureExitNode && importedExposureExitNode.id !== selectedExposureSnapshotId
                ? {
                    id: importedExposureExitNode.id,
                    label: 'Return to imported snapshot',
                  }
                : undefined}
              onSnapshotSelect={(snapshotId) => {
                void handleExposureSnapshotChange(snapshotId)
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
              workspaceId={activeWorkspace?.id ?? null}
              requestedResearchTool={workspaceResearchIntent}
              onConsumeRequestedResearchTool={() => setWorkspaceResearchIntent(null)}
              workspaceShellActivationKey={workspaceShellActivationKey}
              embeddedBacktestResult={workspaceOwnedResearchSession?.backtest.result ?? null}
              embeddedStrategyBacktestState={workspaceOwnedResearchSession?.backtest.panelState}
              onEmbeddedStrategyBacktestStateChange={(update) => {
                if (!activeWorkspace) return
                updateWorkspaceOwnedResearchSession(activeWorkspace.id, 'backtest', (current) => ({
                  ...current,
                  panelState: applySessionStateUpdate(current.panelState, update),
                }))
              }}
              onEmbeddedBacktestResult={(result) => {
                if (!activeWorkspace) return
                updateWorkspaceOwnedResearchSession(activeWorkspace.id, 'backtest', (current) => ({
                  ...current,
                  result,
                }))
              }}
              embeddedStrategyLabState={workspaceOwnedResearchSession?.strategy_lab}
              onEmbeddedStrategyLabStateChange={(update) => {
                if (!activeWorkspace) return
                updateWorkspaceOwnedResearchSession(activeWorkspace.id, 'strategy_lab', update)
              }}
              embeddedEtfRankingState={workspaceOwnedResearchSession?.etf_ranking}
              onEmbeddedEtfRankingStateChange={(update) => {
                if (!activeWorkspace) return
                updateWorkspaceOwnedResearchSession(activeWorkspace.id, 'etf_ranking', update)
              }}
              onSeedCandidateDraft={handleSeedCandidateDraft}
              onOpenPersistedConstructionArtifactReview={async (constructionArtifactId) => {
                try {
                  setWorkspaceError(null)
                  if (!activeWorkspace) {
                    throw new Error('Review In Construction requires an active workspace draft and current portfolio.')
                  }
                  await openPersistedConstructionArtifactReviewById(constructionArtifactId, {
                    setActiveWorkspace,
                    ensureWorkspaceOwnedResearchSession,
                    setActiveNode,
                    setWorkingDraft,
                    setWorkspaceNodes,
                    setPersistedConstructionArtifactReview,
                    setPersistedOptimizerHandoffReview,
                    setHypotheticalReplacementReplay,
                    setProposalArtifacts,
                    setOpenedSavedProposalArtifactId,
                    setActiveThesis,
                    setMonitorDefinitionAlertReviewSession,
                    setCandidateImprovementDraft,
                    setIntentBoundSeededEtfReplacementRankingDraft,
                    setReplacementIntentDraft,
                    setFormedCandidateArtifact,
                    setConstructedCandidateArtifact,
                    setConstructionConstraintValidationArtifact,
                    setSelectedConstructionRuleId,
                    setAnalysis,
                    setBaselineAnalysis,
                    setAllocationBacktestRun,
                    setSelectedExposureSnapshotId,
                    setLastImportedFileNames,
                    setTab,
                    setRestoredSession,
                  })
                } catch (error) {
                  setWorkspaceError(error instanceof Error ? error.message : 'Unable to open persisted construction artifact review')
                }
              }}
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
              monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
              recoveredAlertReviewQueue={recoveredAlertReviewQueue}
              activeAlertEpisodeInbox={activeAlertEpisodeInbox}
              alertEpisodeHistory={alertEpisodeHistory}
              onOpenLatestObservation={handleOpenLatestObservation}
              onOpenAlertHistoryReview={handleOpenAlertHistoryReview}
              onReopenRecoveredAlertReview={handleReopenRecoveredAlertReview}
              onOpenActiveAlertEpisode={handleOpenActiveAlertEpisode}
              onOpenAlertEpisodeHistory={handleOpenAlertEpisodeHistory}
              onLoadOlderAlertEpisodeHistory={handleLoadOlderAlertEpisodeHistory}
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

      {tab === 'generic_ranking' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Generic Ranking</p><p className="helper">Loading generic ranking workspace...</p></section>}>
            <GenericRankingView />
          </Suspense>
        </section>
      ) : null}
    </main>
  )
}
