import type {
  ImportedBaselineSource,
  ImportedBootstrapResponse,
  ImportedPortfolioSnapshotSource,
  ImportedStatementImporter,
} from './types'
import type { ImportedHistoryContext as WorkspaceImportedHistoryContext } from './workspaceTypes'

export type ImportedHistoryContextProjection = WorkspaceImportedHistoryContext

export type ImportedBootstrapProjection = {
  workspace: ImportedPortfolioSnapshotSource
  historyContext: ImportedHistoryContextProjection | null
}

export function mapImportedHistoryContextToWorkspace(
  historyContext: ImportedBootstrapResponse['history_context'],
): ImportedHistoryContextProjection | null {
  if (!historyContext) {
    return null
  }

  return {
    benchmarkSymbol: historyContext.benchmark_symbol,
    statementPeriod: historyContext.statement_period,
    importedAt: historyContext.imported_at,
    importer: historyContext.importer as ImportedStatementImporter | null,
    sourceFileNames: historyContext.source_file_names,
    historyStartDate: historyContext.history_start_date,
    historyEndDate: historyContext.history_end_date,
  }
}

export function projectImportedBootstrap(bootstrap: ImportedBootstrapResponse): ImportedBootstrapProjection {
  return {
    workspace: {
      snapshot: bootstrap.snapshot,
      overview: bootstrap.overview,
      risk_summary: bootstrap.risk_summary,
      benchmark: null,
    },
    historyContext: mapImportedHistoryContextToWorkspace(bootstrap.history_context ?? null),
  }
}
