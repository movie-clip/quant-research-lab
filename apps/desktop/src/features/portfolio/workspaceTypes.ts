import type { ImportedStatementImporter } from './types'
import type { ImportedSnapshot } from './types'

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
  metadata: {
    benchmarkSymbol?: string | null
    notes?: string | null
    tags?: string[]
  }
}

export type PortfolioWorkspace = {
  id: PortfolioWorkspaceId
  name: string
  createdAt: string
  updatedAt: string
  rootNodeId: PortfolioNodeId
  activeNodeId: PortfolioNodeId
  source: {
    importedFileNames: string[]
    importedAt: string
    importer: ImportedStatementImporter | null
    baseCurrency: string | null
    historyContext?: {
      benchmarkSymbol: string
      statementPeriod: string | null
      importedAt: string | null
      importer: ImportedStatementImporter | null
      sourceFileNames: string[]
      historyStartDate: string | null
      historyEndDate: string | null
    } | null
    importedHistorySnapshot?: ImportedSnapshot | null
  }
}

export type PortfolioNodeKind = 'imported_base' | 'variant'

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
  portfolioSnapshot: PortfolioSnapshot
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
