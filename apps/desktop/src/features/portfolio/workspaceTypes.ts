import type { ImportAdmissionSummaryV1, ImportedStatementImporter, ImportedSnapshot } from './types'

export type PortfolioWorkspaceId = string
export type PortfolioNodeId = string
export type PortfolioDraftId = string

export type PortfolioPositionSnapshot = {
  symbol: string
  marketValue: number
  quantity?: number | null
  currency?: string | null
  sector?: string | null
  name?: string | null
  sourceType?: 'equity' | 'etf' | 'cash_equivalent' | 'other'
}

export type CashBalanceSnapshot = {
  currency: string
  amount: number
}

export type PortfolioSnapshot = {
  snapshotVersion: 1
  baseCurrency: string | null
  importedMeta: {
    importer: ImportedStatementImporter | null
    statementPeriod: string | null
    importedAt: string
    sourceFileNames: string[]
  }
  positions: PortfolioPositionSnapshot[]
  cashBalances: CashBalanceSnapshot[]
  /** US-30.2 (audit F-6): statement-implied FX rates ("EURUSD" → rate) copied
   *  from the imported snapshot's statement_totals.fx_rates (broker truth as
   *  of the statement period end, US-28.1). Optional — absent on snapshots
   *  persisted before this field existed (no migration, no fabrication). */
  fxRates?: Record<string, number>
  metadata: {
    benchmarkSymbol?: string | null
    notes?: string | null
    tags?: string[]
  }
}

export type ImportedHistoryContext = {
  benchmarkSymbol: string
  statementPeriod: string | null
  importedAt: string | null
  importer: ImportedStatementImporter | null
  sourceFileNames: string[]
  historyStartDate: string | null
  historyEndDate: string | null
}

export type ImportedHistorySource =
  | {
      kind: 'imported_replay'
      historyContext: ImportedHistoryContext | null
      importedHistorySnapshot: ImportedSnapshot
    }
  | {
      kind: 'history_context'
      historyContext: ImportedHistoryContext
      importedHistorySnapshot: null
    }
  | {
      kind: 'none'
      historyContext: null
      importedHistorySnapshot: null
    }

export type ImportedNodeSource = {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedStatementImporter | null
  baseCurrency: string | null
  historySource: ImportedHistorySource
  admissionSummary?: ImportAdmissionSummaryV1 | null
}

export type PortfolioWorkspaceSource = ImportedNodeSource

export type PortfolioWorkspace = {
  id: PortfolioWorkspaceId
  name: string
  createdAt: string
  updatedAt: string
  rootNodeId: PortfolioNodeId
  activeNodeId: PortfolioNodeId
  source: PortfolioWorkspaceSource
}

export type PortfolioNodeKind = 'imported_base' | 'imported_snapshot' | 'variant'

export type PortfolioNode = {
  id: PortfolioNodeId
  workspaceId: PortfolioWorkspaceId
  parentId: PortfolioNodeId | null
  kind: PortfolioNodeKind
  name: string
  createdAt: string
  changeSummary: {
    label: string
    notes?: string | null
    changedPositionsCount: number
    changedSectorsCount: number
    grossExposureDelta?: number | null
    netCapitalDelta?: number | null
  }
  portfolioSnapshot: PortfolioSnapshot | null
  source?: ImportedNodeSource | null
}

export type WorkingDraft = {
  id: PortfolioDraftId
  workspaceId: PortfolioWorkspaceId
  baseNodeId: PortfolioNodeId
  updatedAt: string
  name: string
  status: 'clean' | 'dirty'
  portfolioSnapshot: PortfolioSnapshot
}

export type WorkspaceState = {
  workspaceId: PortfolioWorkspaceId
  activeNodeId: PortfolioNodeId
  activeDraftId: PortfolioDraftId | null
  selectedExposureSnapshotId?: string | null
  lastOpenedAt: string
}
