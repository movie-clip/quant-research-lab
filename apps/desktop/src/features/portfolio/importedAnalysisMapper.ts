import type {
  ImportedBaselineSource,
  ImportedBootstrapResponse,
  ImportedPortfolioSnapshotSource,
  ImportedStatementImporter,
} from './types'

export type ImportedHistoryContextProjection = {
  benchmarkSymbol: string
  statementPeriod: string | null
  importedAt: string | null
  importer: ImportedStatementImporter | null
  sourceFileNames: string[]
  historyStartDate: string | null
  historyEndDate: string | null
}

export type ImportedBootstrapProjection = {
  workspace: ImportedPortfolioSnapshotSource
  historyContext: ImportedHistoryContextProjection | null
}

export function projectImportedBootstrap(bootstrap: ImportedBootstrapResponse): ImportedBootstrapProjection {
  return {
    workspace: {
      snapshot: bootstrap.snapshot,
      overview: bootstrap.overview,
      risk_summary: bootstrap.risk_summary,
      benchmark: null,
    },
    historyContext: bootstrap.history_context
      ? {
          benchmarkSymbol: bootstrap.history_context.benchmark_symbol,
          statementPeriod: bootstrap.history_context.statement_period,
          importedAt: bootstrap.history_context.imported_at,
          importer: bootstrap.history_context.importer,
          sourceFileNames: bootstrap.history_context.source_file_names,
          historyStartDate: bootstrap.history_context.history_start_date,
          historyEndDate: bootstrap.history_context.history_end_date,
        }
      : null,
  }
}
