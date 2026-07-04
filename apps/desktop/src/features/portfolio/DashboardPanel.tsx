import { useState } from 'react'
import type { DashboardAnalysis, ExposureAnalysis, ExposureFactorModelResponse } from './types'
import { BenchmarkPositioningCard } from './BenchmarkPositioningCard'
import { MonthlyReturnsGrid } from './MonthlyReturnsGrid'
import { PerformanceBenchmarkCard } from './PerformanceBenchmarkCard'
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

export function normalizePerformanceSeries(perf: DashboardAnalysis['performance_series']) {
  const anchorPoint = perf.find((point) => point.portfolio_value > 0)
  const anchorPortfolioValue = anchorPoint?.portfolio_value ?? null
  const anchorBenchmarkPrice = anchorPoint?.benchmark_price ?? null

  return perf.map((point) => {
    const beforeAnchor = anchorPoint != null && point.date < anchorPoint.date
    return {
      ...point,
      portfolio_index: anchorPortfolioValue && anchorPortfolioValue > 0 && !beforeAnchor
        ? (point.portfolio_value / anchorPortfolioValue) * 100
        : null,
      benchmark_index: anchorBenchmarkPrice && anchorBenchmarkPrice > 0 && !beforeAnchor && point.benchmark_price
        ? (point.benchmark_price / anchorBenchmarkPrice) * 100
        : null,
    }
  })
}

type DashboardPanelProps = {
  result: DashboardAnalysis | null
  exposureResult?: ExposureAnalysis | null
  factorModel?: ExposureFactorModelResponse | null
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
        <PerformanceBenchmarkCard result={result} activeRange={activeRange} />
        <MonthlyReturnsGrid result={result} activeRange={activeRange} />
        <RollingFactorLoadingsCard result={exposureResult} factorModel={factorModel} />
        <div className="dashboard-composition-row">
          <SectorPieCard result={result} exposureResult={exposureResult} />
          <BenchmarkPositioningCard exposureResult={exposureResult} />
        </div>
      </div>

      <div className="dashboard-shell-footer-notes">
        {loadedFilesLabel ? <p className="helper">{loadedFilesLabel}</p> : null}
        {restoredSession ? <p className="helper">Restored on launch</p> : null}
        {importError ? <p className="error">{importError}</p> : null}
      </div>
    </article>
  )
}
