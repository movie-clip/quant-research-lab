import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { DashboardPanel } from '../features/portfolio/DashboardPanel'
import { buildExposureFactorModelResponse } from '../features/portfolio/exposureFactorModel'
import { canUseImportedReplay, collapseToHistoryContextSource, resolveEffectiveHistorySource } from '../features/portfolio/historySource'
import { projectImportedBootstrap } from '../features/portfolio/importedBootstrapMapper'
import { buildExposureFactorModel, buildPortfolioBaselineView, composeDashboardAnalysisFromEngines, composeDashboardAnalysisWithHistory, runDashboardHistoryEngine, runDiagnosticsEngine, runExposureEngine, composeExposureView, runImportedDashboardHistory, runImportedDiagnosticsEngine } from '../features/portfolio/portfolioAnalysisAdapter'
import { formatVariantNodeLabel, formatWorkingDraftLabel } from '../features/portfolio/variantLabels'
import { DiagnosticsPanel } from '../features/portfolio/DiagnosticsPanel'
import { VariantList } from '../features/portfolio/VariantList'
import { buildPortfolioSnapshotFromAnalysis, overlayImportedSnapshot } from '../features/portfolio/portfolioSnapshot'
import type { ImportedBootstrapResponse, ImportedSnapshot, ImportedStatementImporter, BacktestRunResponse, DashboardAnalysis, DiagnosticsEngineResponse, ExposureAnalysis, ExposureFactorModelResponse, HypotheticalReplacementReplayResponse, PortfolioAllocationBacktestResponse, PortfolioBaselineView } from '../features/portfolio/types'
import type { CandidateImprovementDraftArtifact, CandidateImprovementSeed, HypotheticalReplacementReplayDraftArtifact, ImportedHistoryContext, ImportedHistorySource, PortfolioNode, PortfolioWorkspace, ReplacementIntentDraftArtifact, VersionedProposalArtifact, WorkingDraft } from '../features/portfolio/workspaceTypes'
import { clearPortfolioWorkspaceState, createWorkspaceFromImport, deleteHypotheticalReplacementReplayDraft, deleteReplacementIntentDraft, getCandidateImprovementDraft, getDraft, getHypotheticalReplacementReplayDraft, getLastOpenedWorkspaceState, getNode, getReplacementIntentDraft, getWorkspace, getWorkspaceNodes, getWorkspaceProposalArtifacts, isDraftDirty, resetLocalPortfolioDatabase, saveCandidateImprovementDraft, saveDraft, saveHypotheticalReplacementReplayDraft, saveImportedSnapshotNode, saveProposalArtifact, saveReplacementIntentDraft, saveVariantFromDraft, setActiveNode as persistActiveNode, setSelectedExposureSnapshot } from './portfolioWorkspaceStorage'


const ExposurePanel = lazy(async () => ({ default: (await import('../features/portfolio/ExposurePanel')).ExposurePanel }))
const BacktestWorkspacePanel = lazy(async () => ({ default: (await import('../features/backtest/BacktestWorkspacePanel')).BacktestWorkspacePanel }))
const StrategyLabPanel = lazy(async () => ({ default: (await import('../features/strategy-lab/StrategyLabPanel')).StrategyLabPanel }))
const EtfRankingPanel = lazy(async () => ({ default: (await import('../features/strategy-lab/EtfRankingPanel')).EtfRankingPanel }))


const defaultSymbolOverrides = '{}'
type ImportMode = 'replace' | 'add_snapshot'

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
  if (node.kind === 'imported_snapshot') {
    return node.source ?? null
  }
  if (node.kind === 'imported_base') {
    return workspace?.source ?? null
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
    if (node) {
      return { id: node.id, snapshot: node.portfolioSnapshot }
    }
  }

  if (workingDraft) {
    return { id: 'draft', snapshot: workingDraft.portfolioSnapshot }
  }

  if (activeNode) {
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

async function loadHypotheticalReplacementReplayForCurrentDraft(
  draft: WorkingDraft | null,
  replacementIntentDraft: ReplacementIntentDraftArtifact | null,
  setHypotheticalReplacementReplay: (value: HypotheticalReplacementReplayResponse | null) => void,
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

async function loadWorkspaceProposalArtifacts(workspace: PortfolioWorkspace | null, setProposalArtifacts: (value: VersionedProposalArtifact[]) => void) {
  if (!workspace) {
    setProposalArtifacts([])
    return
  }
  try {
    setProposalArtifacts(await getWorkspaceProposalArtifacts(workspace.id))
  } catch {
    setProposalArtifacts([])
  }
}

export function App() {
  const [tab, setTab] = useState<'dashboard' | 'exposure' | 'diagnostics' | 'backtest' | 'strategy_lab' | 'etf_ranking'>('dashboard')
  const [analysis, setAnalysis] = useState<DashboardAnalysis | null>(null)
  const [baselineAnalysis, setBaselineAnalysis] = useState<PortfolioBaselineView | null>(null)
  const [exposureAnalysis, setExposureAnalysis] = useState<ExposureAnalysis | null>(null)
  const [diagnosticsAnalysis, setDiagnosticsAnalysis] = useState<DiagnosticsEngineResponse | null>(null)
  const [exposureFactorModel, setExposureFactorModel] = useState<ExposureFactorModelResponse | null>(null)
  const [backtestRun, setBacktestRun] = useState<BacktestRunResponse | null>(null)
  const [allocationBacktestRun, setAllocationBacktestRun] = useState<PortfolioAllocationBacktestResponse | null>(null)
  const [hypotheticalReplacementReplay, setHypotheticalReplacementReplay] = useState<HypotheticalReplacementReplayResponse | null>(null)
  const [importingPortfolio, setImportingPortfolio] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
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
  const [replacementIntentDraft, setReplacementIntentDraft] = useState<ReplacementIntentDraftArtifact | null>(null)
  const [proposalArtifacts, setProposalArtifacts] = useState<VersionedProposalArtifact[]>([])
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const importModeRef = useRef<ImportMode>('replace')
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
          : runDiagnosticsEngine(snapshot, options?.historySource?.historyContext ?? activeWorkspace?.source.historySource?.historyContext ?? null),
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

      const nodes = await getWorkspaceNodes(workspace.id)
      setActiveWorkspace(workspace)
      setActiveNode(node)
      setWorkingDraft(draft)
      await loadWorkspaceProposalArtifacts(workspace, setProposalArtifacts)
      await loadCandidateImprovementDraftForCurrentDraft(draft, setCandidateImprovementDraft)
      const restoredReplacementIntentDraft = draft ? await getReplacementIntentDraft(draft.id).catch(() => null) : null
      setReplacementIntentDraft(restoredReplacementIntentDraft)
      await loadHypotheticalReplacementReplayForCurrentDraft(draft, restoredReplacementIntentDraft, setHypotheticalReplacementReplay)
      setWorkspaceNodes(nodes)
      setLastImportedFileNames(getNodeImportSource(node, workspace)?.importedFileNames ?? workspace.source.importedFileNames)
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
            resolveEffectiveHistorySource(selectedSource, selectedDirectSource) ?? workspace.source.historySource ?? null,
            workspace.id,
          )
          if (!active) return
        }
      })()
      .catch(() => {
        if (active) {
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
    setReplacementIntentDraft(null)
    setHypotheticalReplacementReplay(null)
    setProposalArtifacts([])
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
    setReplacementIntentDraft(null)
    setHypotheticalReplacementReplay(null)
    setProposalArtifacts([])
    setTab('dashboard')
    await resetLocalPortfolioDatabase()
  }

  function handleSeedCandidateDraft(seed: CandidateImprovementSeed) {
    if (!activeWorkspace || !workingDraft) return
    const annotation = {
      workspaceId: activeWorkspace.id,
      draftId: workingDraft.id,
      baseNodeId: workingDraft.baseNodeId,
      seed,
    }
    setCandidateImprovementDraft(annotation)
    void saveCandidateImprovementDraft(annotation).catch(() => undefined)
    setTab('dashboard')
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
    setHypotheticalReplacementReplay(null)
    void saveReplacementIntentDraft(intent).catch(() => undefined)
    if (workingDraft) {
      void deleteHypotheticalReplacementReplayDraft(workingDraft.id).catch(() => undefined)
    }
  }

  function handleClearReplacementIntent() {
    if (!workingDraft) return
    setReplacementIntentDraft(null)
    setHypotheticalReplacementReplay(null)
    void deleteReplacementIntentDraft(workingDraft.id).catch(() => undefined)
    void deleteHypotheticalReplacementReplayDraft(workingDraft.id).catch(() => undefined)
  }

  function handlePreviewHypotheticalReplay() {
    setTab('backtest')
  }

  async function handleSaveProposal() {
    if (!activeWorkspace || !workingDraft || !replacementIntentDraft || !hypotheticalReplacementReplay) return
    const existingProposals = await getWorkspaceProposalArtifacts(activeWorkspace.id).catch(() => proposalArtifacts)
    const proposal: VersionedProposalArtifact = {
      id: `proposal_${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`,
      kind: 'single_replacement_hypothetical_replay_proposal',
      schemaVersion: 1,
      createdAt: new Date().toISOString(),
      workspaceId: activeWorkspace.id,
      sourceDraftId: workingDraft.id,
      sourceBaseNodeId: workingDraft.baseNodeId,
      proposalFamilyId: `${replacementIntentDraft.kind}:${replacementIntentDraft.baseSymbol}:${replacementIntentDraft.candidateSymbol}:${replacementIntentDraft.createdAt}`,
      versionNumber: existingProposals.length + 1,
      savedFrom: 'desktop_hypothetical_replay_review',
      reviewStatus: 'recorded',
      sourceIntent: replacementIntentDraft,
      replayBasis: {
        benchmarkSymbol: hypotheticalReplacementReplay.replay.candidate_result.benchmark_symbol ?? replacementIntentDraft.benchmarkSymbol,
        startDate: hypotheticalReplacementReplay.replay.candidate_result.start_date,
        endDate: hypotheticalReplacementReplay.replay.candidate_result.end_date,
        rebalanceFrequency: hypotheticalReplacementReplay.replay.candidate_result.rebalance_frequency,
        commissionBps: hypotheticalReplacementReplay.replay.candidate_result.commission_bps,
        slippageBps: hypotheticalReplacementReplay.replay.candidate_result.slippage_bps,
        derivationBasis: hypotheticalReplacementReplay.derivation.baseline_basis,
        candidateConstructionRule: hypotheticalReplacementReplay.derivation.candidate_construction_rule,
      },
      reviewSnapshot: hypotheticalReplacementReplay,
    }
    await saveProposalArtifact(proposal)
    setProposalArtifacts([proposal, ...existingProposals])
  }

  async function handlePreviewExposure(snapshot: WorkingDraft['portfolioSnapshot']) {
    if (!activeWorkspace) return
    await analyzeExposureSnapshot(snapshot, 'draft', activeWorkspace?.id)
    setTab('exposure')
  }

  async function handleDraftSnapshotChange(snapshot: WorkingDraft['portfolioSnapshot']) {
    if (!workingDraft || !activeNode) return
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
    setReplacementIntentDraft(null)
    setHypotheticalReplacementReplay(null)
  }

  async function handleSaveVariant(variantName: string) {
    if (!activeWorkspace || !workingDraft) return
    const saved = await saveVariantFromDraft({ workspaceId: activeWorkspace.id, draftId: workingDraft.id, variantName })
    const [nextNode, nextDraft] = await Promise.all([getNode(saved.node.id), getDraft(activeWorkspace.id)])
    setActiveWorkspace(saved.workspace)
    setActiveNode(nextNode)
    setWorkingDraft(nextDraft)
    await loadCandidateImprovementDraftForCurrentDraft(nextDraft, setCandidateImprovementDraft)
    const nextReplacementIntentDraft = nextDraft ? await getReplacementIntentDraft(nextDraft.id).catch(() => null) : null
    setReplacementIntentDraft(nextReplacementIntentDraft)
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
    await loadCandidateImprovementDraftForCurrentDraft(nextDraft, setCandidateImprovementDraft)
    const nextReplacementIntentDraft = nextDraft ? await getReplacementIntentDraft(nextDraft.id).catch(() => null) : null
    setReplacementIntentDraft(nextReplacementIntentDraft)
    await loadHypotheticalReplacementReplayForCurrentDraft(nextDraft, nextReplacementIntentDraft, setHypotheticalReplacementReplay)
    setLastImportedFileNames(getEffectiveNodeImportSource(nextNode, nextNodes, nextWorkspace ?? activeWorkspace)?.importedFileNames ?? activeWorkspace.source.importedFileNames)
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
      const analysisSnapshot = importModeRef.current === 'add_snapshot' && (workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot)
        ? overlayImportedSnapshot(workingDraft?.portfolioSnapshot ?? activeNode!.portfolioSnapshot, importedSnapshot)
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
        const mergedHistoryContext = mergeHistoryContext(baseSource?.historySource.historyContext ?? null, importedViews.historyContext)

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
        await loadCandidateImprovementDraftForCurrentDraft(nextDraft, setCandidateImprovementDraft)
        const nextReplacementIntentDraft = nextDraft ? await getReplacementIntentDraft(nextDraft.id).catch(() => null) : null
        setReplacementIntentDraft(nextReplacementIntentDraft)
        await loadHypotheticalReplacementReplayForCurrentDraft(nextDraft, nextReplacementIntentDraft, setHypotheticalReplacementReplay)
        await loadWorkspaceProposalArtifacts(savedNode.workspace, setProposalArtifacts)
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
            activeWorkspace.id,
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
      await loadCandidateImprovementDraftForCurrentDraft(normalizedDraft, setCandidateImprovementDraft)
      await loadReplacementIntentDraftForCurrentDraft(normalizedDraft, setReplacementIntentDraft)
      setHypotheticalReplacementReplay(null)
      setProposalArtifacts([])
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
          <DashboardPanel
            result={analysis}
            draftSnapshot={workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot ?? null}
            activeNodeName={activeNode?.name ?? null}
            draftStatus={workingDraft?.status ?? null}
            candidateImprovementDraft={candidateImprovementDraft}
            replacementIntentDraft={replacementIntentDraft}
            importing={importingPortfolio || restoringPortfolio}
            importError={importError}
            lastImportedFileNames={lastImportedFileNames}
            restoredSession={restoredSession}
            onImportPortfolio={() => openImportPicker('replace')}
            onAppendStatement={analysis && activeWorkspace ? () => openImportPicker('add_snapshot') : undefined}
            onClearImportedSession={activeWorkspace ? handleClearImportedSession : undefined}
            onResetLocalDatabase={handleResetLocalDatabase}
            onPreviewExposure={handlePreviewExposure}
            onDraftSnapshotChange={handleDraftSnapshotChange}
            onDiscardDraft={handleDiscardDraft}
            onSaveVariant={handleSaveVariant}
            onCreateReplacementIntent={handleCreateReplacementIntent}
            onClearReplacementIntent={handleClearReplacementIntent}
            onPreviewHypotheticalReplay={handlePreviewHypotheticalReplay}
          />
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
                        ? (selectedBaseDirectSource?.historySource ?? null)
                        : collapseToHistoryContextSource(selectedBaseSource),
                      preserveDashboardAnalysis: true,
                    })
                    return
                  }

                  const node = workspaceNodes.find((item) => item.id === snapshotId) ?? await getNode(snapshotId)
                  if (!node) return
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
          <DiagnosticsPanel result={diagnosticsAnalysis} />
        </section>
      ) : null}

      {tab === 'backtest' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Backtest</p><p className="helper">Loading strategy tools...</p></section>}>
            <BacktestWorkspacePanel
              backtestResult={backtestRun}
              onBacktestResult={setBacktestRun}
              allocationBacktestResult={allocationBacktestRun}
              onAllocationBacktestResult={setAllocationBacktestRun}
              analysis={baselineAnalysis}
              draftSnapshot={workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot ?? null}
              replacementIntentDraft={replacementIntentDraft}
              hypotheticalReplayResult={hypotheticalReplacementReplay}
              savedProposals={proposalArtifacts}
              onSaveProposal={handleSaveProposal}
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
