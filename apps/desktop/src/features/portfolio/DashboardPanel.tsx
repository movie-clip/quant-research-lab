import { useState } from 'react'
import type { DashboardAnalysis, DiagnosticsEngineResponse, ExposureAnalysis, ExposureFactorModelResponse } from './types'
import { BenchmarkPositioningCard } from './BenchmarkPositioningCard'
import { MonthlyReturnsGrid } from './MonthlyReturnsGrid'
import { PerformanceBenchmarkCard } from './PerformanceBenchmarkCard'
import { ReplayDisclosuresCard } from './ReplayDisclosuresCard'
import { RiskSummaryCard } from './RiskSummaryCard'
import { RollingFactorLoadingsCard } from './RollingFactorLoadingsCard'
import { SectorPieCard } from './SectorPieCard'
import { WindowSelector } from '../../app/primitives/WindowSelector'

function formatLoadedFilesLabel(statementCount: number, loadedStatementsLabel: string | null) {
  if (!loadedStatementsLabel) return null
  return `${statementCount > 1 ? 'Loaded statements' : 'Loaded file'}: ${loadedStatementsLabel}`
}

function formatLoadedStatements(result: DashboardAnalysis | null, fallbackFileNames: string[]) {
  const statements = result?.snapshot?.statements ?? []
  if (!statements.length) {
    return fallbackFileNames.length ? fallbackFileNames.join(', ') : null
  }

  return statements
    .map((statement) => {
      const sourcePath = statement.source_path
      if (!sourcePath) {
        return statement.statement_period || 'Imported statement'
      }
      return sourcePath.split(/[/\\]/).pop() || sourcePath
    })
    .join(', ')
}

type DashboardPanelProps = {
  result: DashboardAnalysis | null
  exposureResult?: ExposureAnalysis | null
  factorModel?: ExposureFactorModelResponse | null
  diagnosticsAnalysis?: DiagnosticsEngineResponse | null
  importing?: boolean
  importError?: string | null
  lastImportedFileNames?: string[]
  restoredSession?: boolean
  onImportPortfolio?: () => void
  onAppendStatement?: () => void
  onClearImportedSession?: () => void
  onResetLocalDatabase?: () => void | Promise<void>
}

export function DashboardPanel({
  result,
  exposureResult = null,
  factorModel = null,
  diagnosticsAnalysis = null,
  importing = false,
  importError = null,
  lastImportedFileNames = [],
  restoredSession = false,
  onImportPortfolio,
  onAppendStatement,
  onClearImportedSession,
  onResetLocalDatabase,
}: DashboardPanelProps) {
  const statementCount = (result?.snapshot?.statements?.length ?? 0) || lastImportedFileNames.length
  const loadedStatementsLabel = formatLoadedStatements(result, lastImportedFileNames)
  const loadedFilesLabel = formatLoadedFilesLabel(statementCount, loadedStatementsLabel)

  // Shared range selection for PerformanceBenchmarkCard + MonthlyReturnsGrid (US-25.2):
  // both cards read the same selected range so switching it never desyncs the two views.
  const rangeKeys = result?.range_metrics ? Object.keys(result.range_metrics) : []
  const [selectedRange, setSelectedRange] = useState<string>(rangeKeys[0] ?? '')
  const activeRange = rangeKeys.includes(selectedRange) ? selectedRange : (rangeKeys[0] ?? null)

  // 2026-09-12-composition-card-row-fold: single fold governing both
  // sub-sections together, superseding the prior per-sub-section fold
  // (Benchmark Positioning folded independently, Sector Composition did
  // not). One-off toggle, same convention as RiskSummaryCard's US-45.1
  // fold — not a shared primitive.
  const [compositionExpanded, setCompositionExpanded] = useState(true)
  const compositionDetailId = 'dashboard-composition-detail'

  function renderHeaderActions() {
    if (!(onImportPortfolio || onAppendStatement || onClearImportedSession || onResetLocalDatabase)) return null

    return (
      <div className="dashboard-action-row">
        {onImportPortfolio ? (
          <button className="secondary-button" onClick={onImportPortfolio} type="button">
            {importing ? 'Importing...' : loadedStatementsLabel ? 'Replace Import' : 'Import Portfolio'}
          </button>
        ) : null}
        {onAppendStatement ? (
          <button className="secondary-button dashboard-append-button" onClick={onAppendStatement} type="button">
            {importing ? 'Importing...' : 'Add Statement'}
          </button>
        ) : null}
        {onClearImportedSession ? (
          <button className="secondary-button dashboard-clear-button" onClick={onClearImportedSession} type="button">
            Clear Imported Session
          </button>
        ) : null}
        {onResetLocalDatabase ? (
          <button
            className="secondary-button dashboard-clear-button"
            onClick={() => void onResetLocalDatabase()}
            type="button"
          >
            Reset Local DB
          </button>
        ) : null}
      </div>
    )
  }

  return (
    <article className="panel dashboard-panel dashboard-shell-frame">
      <header className="section-header-inline dashboard-header-actions dashboard-shell-header">
        <div className="dashboard-shell-heading">
          <p className="panel-label">Dashboard</p>
          <h2>Account overview</h2>
        </div>
        {renderHeaderActions()}
      </header>

      <div className="dashboard-shell-stack">
        {rangeKeys.length > 1 && (
          <WindowSelector options={rangeKeys} value={activeRange ?? rangeKeys[0]} onChange={setSelectedRange} />
        )}
        {/* US-24.11: the replay's own degradations, directly above the surfaces
            they affect. Renders nothing when the run is clean. */}
        <ReplayDisclosuresCard runMetadata={result?.run_metadata} />
        <PerformanceBenchmarkCard result={result} activeRange={activeRange} />
        <MonthlyReturnsGrid result={result} activeRange={activeRange} />
        <RiskSummaryCard diagnosticsAnalysis={diagnosticsAnalysis} />
        <RollingFactorLoadingsCard result={exposureResult} factorModel={factorModel} />
        {/* 2026-09-12-composition-card-row-fold: one card surface hosting
            both sub-sections side by side, with a single fold control for
            the shared card (superseding the prior per-sub-section fold). */}
        <section className="summary-card dashboard-composition-card" aria-label="Sector and Benchmark Composition">
          <div className="benchmark-card-header">
            <p className="panel-label">Sector &amp; Benchmark Composition</p>
            <button
              type="button"
              aria-expanded={compositionExpanded}
              aria-controls={compositionDetailId}
              aria-label={compositionExpanded ? 'Collapse Sector and Benchmark Composition' : 'Expand Sector and Benchmark Composition'}
              onClick={() => { setCompositionExpanded(!compositionExpanded) }}
              style={{
                background: 'transparent',
                border: 'none',
                padding: 'var(--space-xs)',
                cursor: 'pointer',
                color: 'var(--color-text-secondary)',
                fontSize: 'var(--font-body-sm)',
                fontFamily: 'inherit',
              }}
            >
              {compositionExpanded ? '▾' : '▸'}
            </button>
          </div>
          {compositionExpanded && (
            <div className="dashboard-composition-row" id={compositionDetailId}>
              <SectorPieCard result={result} exposureResult={exposureResult} />
              <div className="dashboard-composition-divider" role="presentation" />
              <BenchmarkPositioningCard exposureResult={exposureResult} />
            </div>
          )}
        </section>
      </div>

      <div className="dashboard-shell-footer-notes">
        {loadedFilesLabel ? <p className="helper">{loadedFilesLabel}</p> : null}
        {restoredSession ? <p className="helper">Restored on launch</p> : null}
        {importError ? <p className="error">{importError}</p> : null}
      </div>
    </article>
  )
}
