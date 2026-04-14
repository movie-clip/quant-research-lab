import { Suspense, lazy, useEffect, useRef, useState } from 'react'
import type { ChangeEvent } from 'react'

import { DashboardPanel } from '../features/portfolio/DashboardPanel'
import { buildExposureFactorModelResponse } from '../features/portfolio/exposureFactorModel'
import { projectImportedBootstrap } from '../features/portfolio/importedAnalysisMapper'
import { buildExposureFactorModel, buildPortfolioBaselineAnalysis, composeDashboardAnalysisFromEngines, composeDashboardAnalysisWithHistory, runDashboardHistoryEngine, runDiagnosticsEngine, runExposureEngine, composeExposureView, runImportedDashboardHistory, runImportedDiagnosticsEngine } from '../features/portfolio/portfolioAnalysisAdapter'
import { formatVariantNodeLabel, formatWorkingDraftLabel } from '../features/portfolio/variantLabels'
import { DiagnosticsPanel } from '../features/portfolio/DiagnosticsPanel'
import { VariantList } from '../features/portfolio/VariantList'
import { buildPortfolioSnapshotFromAnalysis } from '../features/portfolio/portfolioSnapshot'
import type { ImportedBootstrapResponse, BacktestRunResponse, DashboardAnalysis, DiagnosticsEngineResponse, ExposureAnalysis, ExposureFactorModelResponse, PortfolioAllocationBacktestResponse, PortfolioBaselineAnalysis } from '../features/portfolio/types'
import type { PortfolioNode, PortfolioWorkspace, WorkingDraft } from '../features/portfolio/workspaceTypes'
import { clearPortfolioWorkspaceState, createWorkspaceFromImport, getDraft, getLastOpenedWorkspaceState, getNode, getWorkspace, getWorkspaceNodes, isDraftDirty, migrateLegacyImportSession, resetLocalPortfolioDatabase, saveDraft, saveVariantFromDraft, setActiveNode as persistActiveNode, setSelectedExposureSnapshot } from './portfolioWorkspaceStorage'


const ExposurePanel = lazy(async () => ({ default: (await import('../features/portfolio/ExposurePanel')).ExposurePanel }))
const BacktestWorkspacePanel = lazy(async () => ({ default: (await import('../features/backtest/BacktestWorkspacePanel')).BacktestWorkspacePanel }))
const StrategyLabPanel = lazy(async () => ({ default: (await import('../features/strategy-lab/StrategyLabPanel')).StrategyLabPanel }))


const defaultSymbolOverrides = '{}'
type ImportMode = 'replace' | 'append'

function buildImportFormData(files: File[]) {
  const formData = new FormData()
  for (const file of files) {
    formData.append('statement_files', file)
  }
  formData.append('benchmark_symbol', 'SPY')
  formData.append('symbol_overrides', defaultSymbolOverrides)
  return formData
}

function buildFileSignature(file: File) {
  return `${file.name}:${file.size}:${file.lastModified}`
}

function mergeImportedFiles(existingFiles: File[], nextFiles: File[]) {
  const mergedFiles: File[] = []
  const seen = new Set<string>()

  for (const file of [...existingFiles, ...nextFiles]) {
    const signature = buildFileSignature(file)
    if (seen.has(signature)) {
      continue
    }

    seen.add(signature)
    mergedFiles.push(file)
  }

  return mergedFiles
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

export function App() {
  const [tab, setTab] = useState<'dashboard' | 'exposure' | 'diagnostics' | 'backtest' | 'strategy_lab'>('dashboard')
  const [analysis, setAnalysis] = useState<DashboardAnalysis | null>(null)
  const [baselineAnalysis, setBaselineAnalysis] = useState<PortfolioBaselineAnalysis | null>(null)
  const [exposureAnalysis, setExposureAnalysis] = useState<ExposureAnalysis | null>(null)
  const [diagnosticsAnalysis, setDiagnosticsAnalysis] = useState<DiagnosticsEngineResponse | null>(null)
  const [exposureFactorModel, setExposureFactorModel] = useState<ExposureFactorModelResponse | null>(null)
  const [backtestRun, setBacktestRun] = useState<BacktestRunResponse | null>(null)
  const [allocationBacktestRun, setAllocationBacktestRun] = useState<PortfolioAllocationBacktestResponse | null>(null)
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
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const importModeRef = useRef<ImportMode>('replace')
  const workflowState = activeWorkspace && backtestRun ? 'Portfolio + Backtest Loaded' : activeWorkspace ? 'Portfolio Loaded' : backtestRun ? 'Backtest Loaded' : 'Workspace Empty'

  async function analyzeExposureSnapshot(
    snapshot: WorkingDraft['portfolioSnapshot'],
    snapshotId: string,
    workspaceId?: string,
    options?: {
      importedHistorySnapshot?: PortfolioWorkspace['source']['importedHistorySnapshot'] | null
      useImportedDiagnostics?: boolean
      preserveDashboardAnalysis?: boolean
    },
  ) {
    const [exposure, diagnostics] = await Promise.all([
      runExposureEngine(snapshot),
      options?.useImportedDiagnostics && options.importedHistorySnapshot
        ? runImportedDiagnosticsEngine(options.importedHistorySnapshot)
        : runDiagnosticsEngine(snapshot, activeWorkspace?.source.historyContext ?? null),
    ])
    const exposureView = composeExposureView(exposure, diagnostics)
    setExposureAnalysis(exposureView)
    setDiagnosticsAnalysis(diagnostics)
    setExposureFactorModel(buildExposureFactorModel(exposureView))
    if (!options?.preserveDashboardAnalysis) {
      setAnalysis(composeDashboardAnalysisFromEngines(exposure, diagnostics))
    }
    setBaselineAnalysis(buildPortfolioBaselineAnalysis(exposure))
    setSelectedExposureSnapshotId(snapshotId)
    if (workspaceId) {
      await setSelectedExposureSnapshot({ workspaceId, snapshotId })
    }
    return diagnostics
  }

  async function analyzeRestoredSnapshot(
    snapshot: WorkingDraft['portfolioSnapshot'],
    snapshotId: string,
    historyContext: PortfolioWorkspace['source']['historyContext'] | null | undefined,
    importedHistorySnapshot: PortfolioWorkspace['source']['importedHistorySnapshot'] | null | undefined,
    workspaceId?: string,
  ) {
    const [exposure, diagnostics, dashboardHistory] = await Promise.all([
      runExposureEngine(snapshot),
      importedHistorySnapshot
        ? runImportedDiagnosticsEngine(importedHistorySnapshot)
        : runDiagnosticsEngine(snapshot, historyContext ?? null),
      importedHistorySnapshot
        ? runImportedDashboardHistory(importedHistorySnapshot)
        : historyContext
        ? runDashboardHistoryEngine(snapshot, historyContext)
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
    setBaselineAnalysis(buildPortfolioBaselineAnalysis(exposure))
    setSelectedExposureSnapshotId(snapshotId)
    if (workspaceId) {
      await setSelectedExposureSnapshot({ workspaceId, snapshotId })
    }
    return diagnostics
  }

  useEffect(() => {
    let active = true

    void (async () => {
      let restoredWorkspaceState = await getLastOpenedWorkspaceState()
      if (!restoredWorkspaceState) {
        const migrated = await migrateLegacyImportSession()
        restoredWorkspaceState = migrated?.workspaceState ?? null
      }

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
      setWorkspaceNodes(nodes)
      setLastImportedFileNames(workspace.source.importedFileNames)
      setRestoredSession(true)

      const resolvedSnapshot = resolveSelectedSnapshot(restoredWorkspaceState.selectedExposureSnapshotId, nodes, node, draft)
      if (!resolvedSnapshot) return

      setSelectedExposureSnapshotId(resolvedSnapshot.id)

        if (resolvedSnapshot.snapshot.positions.length || resolvedSnapshot.snapshot.cashBalances.length) {
          await analyzeRestoredSnapshot(resolvedSnapshot.snapshot, resolvedSnapshot.id, workspace.source.historyContext, workspace.source.importedHistorySnapshot, workspace.id)
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
    setTab('dashboard')
    await resetLocalPortfolioDatabase()
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
    const draft = await getDraft(activeWorkspace.id)
    if (draft && activeNode) {
      const cleanDraft: WorkingDraft = {
        ...draft,
        baseNodeId: activeNode.id,
        updatedAt: new Date().toISOString(),
        status: 'clean',
        portfolioSnapshot: JSON.parse(JSON.stringify(activeNode.portfolioSnapshot)),
      }
      setWorkingDraft(cleanDraft)
      await saveDraft(cleanDraft)
    }
  }

  async function handleSaveVariant(variantName: string) {
    if (!activeWorkspace || !workingDraft) return
    const saved = await saveVariantFromDraft({ workspaceId: activeWorkspace.id, draftId: workingDraft.id, variantName })
    const [nextNode, nextDraft] = await Promise.all([getNode(saved.node.id), getDraft(activeWorkspace.id)])
    setActiveWorkspace(saved.workspace)
    setActiveNode(nextNode)
    setWorkingDraft(nextDraft)
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
    if (nextDraft) {
      await analyzeExposureSnapshot(nextDraft.portfolioSnapshot, 'draft', activeWorkspace.id, {
        importedHistorySnapshot: nextNode?.kind === 'imported_base' ? (nextWorkspace?.source.importedHistorySnapshot ?? null) : null,
        useImportedDiagnostics: nextNode?.kind === 'imported_base',
        preserveDashboardAnalysis: true,
      })
    }
  }

  async function handleImportFileChange(event: ChangeEvent<HTMLInputElement>) {
    const selectedFiles = Array.from(event.target.files ?? [])
    if (!selectedFiles.length) {
      return
    }

    const files = importModeRef.current === 'append'
      ? mergeImportedFiles(loadedStatementFiles, selectedFiles)
      : selectedFiles

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
      const workspaceResult = await createWorkspaceFromImport({
        analysis: importedViews.workspace,
        importedFileNames: files.map((file) => file.name),
        historyContext: importedViews.historyContext,
        importedHistorySnapshot: nextAnalysis.snapshot,
      })
      const normalizedDraft = {
        ...workspaceResult.draft,
        portfolioSnapshot: buildPortfolioSnapshotFromAnalysis(importedViews.workspace, files.map((file) => file.name)),
      }
      const dashboardHistory = await runImportedDashboardHistory(nextAnalysis.snapshot)
      const [exposure, diagnostics] = await Promise.all([
        runExposureEngine(normalizedDraft.portfolioSnapshot),
        runImportedDiagnosticsEngine(nextAnalysis.snapshot),
      ])
      const exposureView = composeExposureView(exposure, diagnostics)

      setAnalysis(
        dashboardHistory
          ? composeDashboardAnalysisWithHistory(
              exposure,
              dashboardHistory,
            )
          : composeDashboardAnalysisFromEngines(exposure, diagnostics),
      )
      setBaselineAnalysis(buildPortfolioBaselineAnalysis(exposure))
      setExposureAnalysis(exposureView)
      setDiagnosticsAnalysis(diagnostics)
      setExposureFactorModel(buildExposureFactorModel(exposureView))
      setLoadedStatementFiles(files)
      setLastImportedFileNames(files.map((file) => file.name))
      setActiveWorkspace(workspaceResult.workspace)
      setActiveNode(workspaceResult.rootNode)
      setWorkingDraft(normalizedDraft)
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
            importing={importingPortfolio || restoringPortfolio}
            importError={importError}
            lastImportedFileNames={lastImportedFileNames}
            restoredSession={restoredSession}
            onImportPortfolio={() => openImportPicker('replace')}
            onAppendStatement={analysis && loadedStatementFiles.length ? () => openImportPicker('append') : undefined}
            onClearImportedSession={activeWorkspace ? handleClearImportedSession : undefined}
            onResetLocalDatabase={handleResetLocalDatabase}
            onPreviewExposure={handlePreviewExposure}
            onDraftSnapshotChange={handleDraftSnapshotChange}
            onDiscardDraft={handleDiscardDraft}
            onSaveVariant={handleSaveVariant}
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
                    await analyzeExposureSnapshot(workingDraft.portfolioSnapshot, 'draft', activeWorkspace.id, {
                      importedHistorySnapshot: selectedBaseNode?.kind === 'imported_base' && workingDraft.status === 'clean'
                        ? (activeWorkspace.source.importedHistorySnapshot ?? null)
                        : null,
                      useImportedDiagnostics: selectedBaseNode?.kind === 'imported_base' && workingDraft.status === 'clean',
                      preserveDashboardAnalysis: true,
                    })
                    return
                  }

                  const node = workspaceNodes.find((item) => item.id === snapshotId) ?? await getNode(snapshotId)
                  if (!node) return
                  await analyzeExposureSnapshot(node.portfolioSnapshot, snapshotId, activeWorkspace.id, {
                    importedHistorySnapshot: node.kind === 'imported_base' ? (activeWorkspace.source.importedHistorySnapshot ?? null) : null,
                    useImportedDiagnostics: node.kind === 'imported_base',
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
    </main>
  )
}
