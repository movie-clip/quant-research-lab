import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { canUseImportedReplay, collapseToHistoryContextSource, resolveEffectiveHistorySource } from '../features/portfolio/historySource'
import { projectImportedBootstrap } from '../features/portfolio/importedBootstrapMapper'
import { buildExposureFactorModel, buildPortfolioBaselineView, combineImportedSnapshots, composeDashboardAnalysisFromEngines, composeDashboardAnalysisWithHistory, runDashboardHistoryEngine, runDiagnosticsEngine, runExposureEngine, composeExposureView, runImportedDashboardHistory, runImportedDiagnosticsEngine } from '../features/portfolio/portfolioAnalysisAdapter'
import { formatVariantNodeLabel, formatWorkingDraftLabel } from '../features/portfolio/variantLabels'
import { buildPortfolioSnapshotFromAnalysis, overlayImportedSnapshot } from '../features/portfolio/portfolioSnapshot'
import { composeDashboardSession, type DashboardSession } from './dashboardSession'
import { resolveImportedWorkspaceStartupTruth } from './startupSelectionValidation'
import type { ImportedBootstrapResponse, ImportedExposureOverride, ImportedSnapshot, ImportedStatementImporter, DashboardAnalysis, DashboardHistoryEngineResponse, DiagnosticsEngineResponse, ExposureAnalysis, ExposureFactorModelResponse } from '../features/portfolio/types'
import type { ImportedHistoryContext, ImportedHistorySource, PortfolioNode, PortfolioWorkspace, WorkingDraft, WorkspaceState } from '../features/portfolio/workspaceTypes'
import { clearPortfolioWorkspaceState, createWorkspaceFromImport, getDraft, getLastOpenedWorkspaceState, getNode, getWorkspace, getWorkspaceNodes, resetLocalPortfolioDatabase, saveImportedSnapshotNode, setSelectedExposureSnapshot } from './portfolioWorkspaceStorage'
import { DashboardPanel } from '../features/portfolio/DashboardPanel'
const ExposurePanel = lazy(async () => ({ default: (await import('../features/portfolio/ExposurePanel')).ExposurePanel }))
const RiskPanel = lazy(async () => ({ default: (await import('../features/portfolio/RiskPanel')).RiskPanel }))


const defaultSymbolOverrides = '{}'
type ImportMode = 'replace' | 'add_snapshot'
type AppTab = 'dashboard' | 'exposure' | 'risk'

const tauriAnalyzeUploadTimeoutMs = 30_000

const appTabs: Array<{ id: AppTab; label: string }> = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'exposure', label: 'Exposure' },
  { id: 'risk', label: 'Risk' },
]

function isImportedWorkspaceSource(source: PortfolioWorkspace['source'] | null | undefined): source is Extract<PortfolioWorkspace['source'], { importedFileNames: string[] }> {
  return Boolean(source && 'importedFileNames' in source)
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

function statementMimeType(fileName: string) {
  return fileName.toLowerCase().endsWith('.csv') ? 'text/csv' : 'application/pdf'
}

function buildImportFormData(files: File[]) {
  const formData = new FormData()
  for (const file of files) {
    const expectedType = statementMimeType(file.name)
    const normalizedFile = file.type === expectedType
      ? file
      : new File([file], file.name, { type: expectedType, lastModified: file.lastModified })
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
    return createTauriImportError('the local import service timed out while analyzing the selected statement files')
  }
  if (error instanceof DOMException && error.name === 'AbortError') {
    return createTauriImportError('the local import service stopped before the selected statement files could be analyzed')
  }
  if (error instanceof TypeError) {
    return createTauriImportError('unable to reach the local import service while analyzing the selected statement files')
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
    filters: [{ name: 'Broker Statements', extensions: ['pdf', 'csv'] }],
  }))
  const statementPaths = selection.filter((path) => {
    const lowered = path.toLowerCase()
    return lowered.endsWith('.pdf') || lowered.endsWith('.csv')
  })

  return Promise.all(statementPaths.map(async (path) => {
    const bytes = await readFile(path)
    const fileName = resolveFileNameFromPath(path)
    if (!bytes.length) {
      throw createTauriImportError(`could not read "${fileName}" because the selected statement was empty`)
    }
    return new File([bytes], fileName, { type: statementMimeType(fileName) })
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


export function App() {
  const [tab, setTab] = useState<AppTab>('dashboard')
  const [analysis, setAnalysis] = useState<DashboardAnalysis | null>(null)
  const [baselineAnalysis, setBaselineAnalysis] = useState<ReturnType<typeof buildPortfolioBaselineView> | null>(null)
  const [exposureAnalysis, setExposureAnalysis] = useState<ExposureAnalysis | null>(null)
  const [diagnosticsAnalysis, setDiagnosticsAnalysis] = useState<DiagnosticsEngineResponse | null>(null)
  const [exposureFactorModel, setExposureFactorModel] = useState<ExposureFactorModelResponse | null>(null)
  const [importingPortfolio, setImportingPortfolio] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [lastImportedFileNames, setLastImportedFileNames] = useState<string[]>([])
  const [activeWorkspace, setActiveWorkspace] = useState<PortfolioWorkspace | null>(null)
  const [activeNode, setActiveNode] = useState<PortfolioNode | null>(null)
  const [workingDraft, setWorkingDraft] = useState<WorkingDraft | null>(null)
  const [workspaceNodes, setWorkspaceNodes] = useState<PortfolioNode[]>([])
  const [selectedExposureSnapshotId, setSelectedExposureSnapshotId] = useState<string>('current')
  const [restoringPortfolio, setRestoringPortfolio] = useState(true)
  const [restoredSession, setRestoredSession] = useState(false)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const importModeRef = useRef<ImportMode>('replace')
  const userSelectedTabRef = useRef(false)
  const dashboardSnapshot = workingDraft?.portfolioSnapshot ?? activeNode?.portfolioSnapshot ?? null
  const importedExposureExitNode = resolveImportedExposureExitNode(
    selectedExposureSnapshotId,
    workspaceNodes,
    activeNode,
    workingDraft,
  )
  // Persisted Import Admission Review for the snapshot the Exposure tab is
  // showing (US-22.1). Read from the resolved import source's workspace state;
  // null when there is no imported source (e.g. an unsaved draft).
  const exposureAdmissionSummary =
    getEffectiveNodeImportSource(importedExposureExitNode ?? activeNode, workspaceNodes, activeWorkspace)
      ?.admissionSummary ?? null
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
  const workflowState = activeWorkspace ? 'Portfolio Loaded' : 'Workspace Empty'

  function applyDashboardSession(session: DashboardSession) {
    setAnalysis(session.result)
    setExposureAnalysis(session.exposureResult)
    setExposureFactorModel(session.factorModel)
    setLastImportedFileNames(session.lastImportedFileNames)
    setRestoredSession(session.restoredSession)
  }

  function handleTabChange(nextTab: AppTab) {
    userSelectedTabRef.current = true
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
        throw new Error('Unable to restore previous portfolio workspace: authoritative workspace nodes are unavailable on startup')
      })
      if (!authoritativeNodes.length) {
        throw new Error('Unable to restore previous portfolio workspace: authoritative workspace nodes are unavailable on startup')
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

    if (!isActive()) return

    setActiveWorkspace(workspace)
    setActiveNode(node)
    setWorkingDraft(draft)
    if (sessionRestored && isImportedWorkspaceSource(workspace.source) && !userSelectedTabRef.current) {
      setTab('dashboard')
    }

    if (!isActive()) return

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
      const importedExposureOverride = resolvedSnapshot.id !== 'draft' ? (selectedDirectSource?.importedExposureOverride ?? null) : null
      const restoredAnalytics = await analyzeRestoredSnapshot(
        resolvedSnapshot.snapshot,
        resolvedSnapshot.id,
        resolveEffectiveHistorySource(selectedSource, selectedDirectSource) ?? getWorkspaceHistorySource(workspace) ?? null,
        workspace.id,
        importedExposureOverride,
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

  async function analyzeExposureSnapshot(
    snapshot: WorkingDraft['portfolioSnapshot'],
    snapshotId: string,
    workspaceId?: string,
    options?: {
      preserveDashboardAnalysis?: boolean
      historySource?: ImportedHistorySource | null
      importedExposureOverride?: ImportedExposureOverride | null
    },
  ) {
    // Drift is self-fetched by DriftBenchmarkPanel from the workspace snapshot
    // (US-30.3 / F-4) — no App-level drift fetch here, so no analyze path can
    // forget it (the restore-path bug that showed a blank chart until the
    // benchmark dropdown was touched).
    const [rawExposure, diagnostics] = await Promise.all([
      runExposureEngine(snapshot),
      options?.historySource?.kind === 'imported_replay'
        ? runImportedDiagnosticsEngine(options.historySource.importedHistorySnapshot)
        : runDiagnosticsEngine(snapshot, options?.historySource?.historyContext ?? getWorkspaceHistorySource(activeWorkspace)?.historyContext ?? null),
    ])
    const exposure = options?.importedExposureOverride ? { ...rawExposure, ...options.importedExposureOverride } : rawExposure
    const exposureView = composeExposureView(exposure, diagnostics)
    let factorModel: ExposureFactorModelResponse | null
    try {
      factorModel = buildExposureFactorModel(exposureView)
    } catch {
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
        importedExposureOverride: null,
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
      importedExposureOverride: directNodeSource?.importedExposureOverride ?? null,
    })
  }

  async function analyzeRestoredSnapshot(
    snapshot: WorkingDraft['portfolioSnapshot'],
    snapshotId: string,
    historySource: ImportedHistorySource | null | undefined,
    _workspaceId: string | undefined,
    importedExposureOverride: ImportedExposureOverride | null,
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
      } catch {
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

    const rawExposure = await runExposureEngine(snapshot)
    const exposure = importedExposureOverride ? { ...rawExposure, ...importedExposureOverride } : rawExposure

    const exposureView = composeExposureView(exposure, diagnostics)
    let factorModel: ExposureFactorModelResponse | null
    try {
      factorModel = buildExposureFactorModel(exposureView)
    } catch {
      factorModel = null
    }
    const nextAnalysis = dashboardHistory
      ? composeDashboardAnalysisWithHistory(exposure, dashboardHistory)
      : composeDashboardAnalysisFromEngines(exposure, diagnostics)
    const baselineView = buildPortfolioBaselineView(exposure)

    // Drift is self-fetched by DriftBenchmarkPanel from `dashboardSnapshot`
    // (US-30.3 / F-4), so the restore path no longer needs to fetch it or
    // stash the snapshot — the panel renders on mount without interaction.

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

      if (!isImportedWorkspaceSource(workspace.source)) {
        // Non-imported workspace sources (construction artifact, optimizer handoff) are no longer supported.
        // Fall through without restoring to avoid corrupted state.
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
    setLastImportedFileNames([])
    setActiveWorkspace(null)
    setActiveNode(null)
    setWorkingDraft(null)
    setWorkspaceNodes([])
    setSelectedExposureSnapshotId('current')
    setImportError(null)
    setRestoredSession(false)
    setTab('dashboard')
    void clearPortfolioWorkspaceState()
  }

  async function handleResetLocalDatabase() {
    setAnalysis(null)
    setBaselineAnalysis(null)
    setExposureAnalysis(null)
    setDiagnosticsAnalysis(null)
    setExposureFactorModel(null)
    setLastImportedFileNames([])
    setActiveWorkspace(null)
    setActiveNode(null)
    setWorkingDraft(null)
    setWorkspaceNodes([])
    setSelectedExposureSnapshotId('current')
    setImportError(null)
    setRestoredSession(false)
    setTab('dashboard')
    await resetLocalPortfolioDatabase()
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

        const baseImportedHistorySnapshot = canUseImportedReplay(baseSource) ? (baseSource?.historySource.importedHistorySnapshot ?? null) : null
        // No prior replay data to combine with -> adopt the new statement's own
        // snapshot alone. Still strictly better than discarding it outright, and
        // honest: there is nothing to combine.
        let combinedHistorySnapshot: ImportedSnapshot | null = nextAnalysis.snapshot
        if (baseImportedHistorySnapshot) {
          try {
            combinedHistorySnapshot = await combineImportedSnapshots([baseImportedHistorySnapshot, nextAnalysis.snapshot])
          } catch {
            combinedHistorySnapshot = null
            setImportError('Added statement could not be combined with the existing imported history (for example, a differing base currency) — this snapshot keeps the merged positions but not full replay history.')
          }
        }

        const savedNode = await saveImportedSnapshotNode({
          workspaceId: activeWorkspace.id,
          parentNodeId: baseNode?.id ?? activeWorkspace.rootNodeId,
          portfolioSnapshot: overlaidSnapshot,
          importedFileNames,
          historyContext: mergedHistoryContext,
          importedHistorySnapshot: combinedHistorySnapshot,
          admissionSummary: nextAnalysis.admission_summary,
          name: buildImportedSnapshotName(nextAnalysis.snapshot),
        })
        await restoreImportedWorkspaceFromPersistedState(savedNode.workspaceState, { restoredSession: false })
        return
      }

      const workspaceResult = await createWorkspaceFromImport({
        analysis: importedViews.workspace,
        importedFileNames,
        historyContext: importedViews.historyContext,
        importedHistorySnapshot: nextAnalysis.snapshot,
      })
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

      <input ref={fileInputRef} type="file" accept="application/pdf,.pdf,text/csv,.csv" hidden multiple onChange={handleImportFileChange} />

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
            diagnosticsAnalysis={diagnosticsAnalysis}
            importing={dashboardSession.importing}
            importError={dashboardSession.importError}
            lastImportedFileNames={dashboardSession.lastImportedFileNames}
            restoredSession={dashboardSession.restoredSession}
            onImportPortfolio={() => openImportPicker('replace')}
            onAppendStatement={dashboardSnapshot && activeWorkspace ? () => openImportPicker('add_snapshot') : undefined}
            onClearImportedSession={activeWorkspace ? handleClearImportedSession : undefined}
            onResetLocalDatabase={handleResetLocalDatabase}
          />
        </section>
      ) : null}

      {tab === 'exposure' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Exposure</p><p className="helper">Loading exposure analytics...</p></section>}>
            <ExposurePanel
              result={exposureAnalysis}
              driftSnapshot={dashboardSnapshot}
              snapshotOptions={[
                ...(workingDraft ? [{ id: 'draft', label: formatWorkingDraftLabel(activeNode, workspaceNodes) }] : []),
                ...workspaceNodes.map((node) => ({ id: node.id, label: formatVariantNodeLabel(node, workspaceNodes) })),
              ]}
              admissionSummary={exposureAdmissionSummary}
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

      {tab === 'risk' ? (
        <section className="grid grid-single">
          <Suspense fallback={<section className="panel"><p className="panel-label">Risk</p><p className="helper">Loading risk analytics...</p></section>}>
            <RiskPanel snapshot={dashboardSnapshot} />
          </Suspense>
        </section>
      ) : null}


    </main>
  )
}
