import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedAnalysisFixture, createImportedBootstrapResponseFixture } from '../test/portfolioFixtures'
import { App } from './App'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import type { PortfolioSnapshot } from '../features/portfolio/workspaceTypes'

const exposurePayload = createExposureEngineFixture()
const diagnosticsPayload = createDiagnosticsEngineFixture()
const bootstrapPayload = createImportedBootstrapResponseFixture()
const dashboardHistoryPayload = (() => {
  const fixture = createImportedAnalysisFixture()
  return {
    performance_series: fixture.performance_series,
    daily_states: fixture.daily_states,
    source_status: fixture.source_status,
    benchmark: fixture.benchmark,
  }
})()
const appendedExposurePayload = {
  ...exposurePayload,
  snapshot: {
    ...exposurePayload.snapshot,
    statement: {
      ...exposurePayload.snapshot.statement,
      statement_period: '2025-01-01 - 2026-04-08',
    },
    statements: [
      ...exposurePayload.snapshot.statements,
      {
        ...exposurePayload.snapshot.statements[0],
        statement_period: '2026-01-01 - 2026-04-08',
        source_path: 'C:\\docs\\IB2026.pdf',
        imported_at: '2026-04-10T00:05:00Z',
        page_count: 17,
      },
    ],
  },
}
const appendedDiagnosticsPayload = {
  ...diagnosticsPayload,
  snapshot: {
    ...diagnosticsPayload.snapshot,
    statement: {
      ...diagnosticsPayload.snapshot.statement,
      statement_period: '2025-01-01 - 2026-04-08',
    },
    statements: [
      ...diagnosticsPayload.snapshot.statements,
      {
        ...diagnosticsPayload.snapshot.statements[0],
        statement_period: '2026-01-01 - 2026-04-08',
        source_path: 'C:\\docs\\IB2026.pdf',
        imported_at: '2026-04-10T00:05:00Z',
        page_count: 17,
      },
    ],
  },
}

const allocationBacktestPayload = {
  methodology: 'm',
  reference_result: null,
  candidate_result: {
    portfolio_name: 'Candidate',
    benchmark_symbol: 'SPY',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    observation_count: 2,
    rebalance_frequency: 'monthly',
    commission_bps: 0,
    slippage_bps: 0,
    drift_tolerance_pct: null,
    assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
    status: 'ok',
    instrument_metadata: [],
    starting_weights: [],
    ending_weights: [],
    metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
    equity_curve: [{ date: '2024-01-02', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-12-31', equity: 101000, cash: 0, gross_exposure: 101000, drawdown_pct: -1 }],
    rebalance_events: [],
    trades: [],
  },
  comparison: null,
  reference_diagnostics: null,
  candidate_diagnostics: null,
  diagnostics_comparison: null,
}

const persistedSnapshot: PortfolioSnapshot = {
  snapshotVersion: 1,
  baseCurrency: 'USD',
  importedMeta: {
    importer: 'interactive_brokers',
    statementPeriod: '2025-01-01 - 2025-12-31',
    importedAt: '2026-04-10T00:00:00Z',
    sourceFileNames: ['IB2025.pdf'],
  },
  positions: [{ symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
  cashBalances: [{ currency: 'USD', amount: 1000 }],
  metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
}

function mockImportedWorkspace() {
  return {
    workspace: { id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: { importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot } },
    rootNode: { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base' as const, name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 0, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 }, portfolioSnapshot: { snapshotVersion: 1, baseCurrency: 'USD', importedMeta: { importer: 'interactive_brokers', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', sourceFileNames: ['IB2025.pdf'] }, positions: [], cashBalances: [], metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] } } },
    draft: { id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: { snapshotVersion: 1, baseCurrency: 'USD', importedMeta: { importer: 'interactive_brokers', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', sourceFileNames: ['IB2025.pdf'] }, positions: [], cashBalances: [], metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] } } },
    workspaceState: { workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', lastOpenedAt: '2026-04-10T00:00:00Z' },
  }
}

function mockSavedVariantNode() {
  return {
    id: 'node-2',
    workspaceId: 'workspace-1',
    parentId: 'node-1',
    kind: 'variant' as const,
    name: 'Raise MSFT',
    createdAt: '2026-04-10T00:10:00Z',
    changeSummary: { label: 'Raise MSFT', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 },
    portfolioSnapshot: persistedSnapshot,
  }
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('App', () => {
  it('appends new statement files onto the existing imported set', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...bootstrapPayload, snapshot: { ...bootstrapPayload.snapshot, statement: { ...bootstrapPayload.snapshot.statement, statement_period: '2025-01-01 - 2026-04-08' }, statements: [...bootstrapPayload.snapshot.statements, { ...bootstrapPayload.snapshot.statements[0], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf', imported_at: '2026-04-10T00:05:00Z', page_count: 17 }] }, history_context: { ...bootstrapPayload.history_context, statement_period: '2025-01-01 - 2026-04-08', source_file_names: ['IB2025.pdf', 'IB2026.pdf'] } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(appendedExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(appendedDiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [file2026] } })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(8))

    const appendAnalyzeBody = fetchMock.mock.calls[4]?.[1]?.body as FormData
    const uploadedFiles = appendAnalyzeBody.getAll('statement_files') as File[]
    expect(uploadedFiles.map((file) => file.name)).toEqual(['IB2025.pdf', 'IB2026.pdf'])
  })

  it('restores persisted import state on startup', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: { importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot } })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByText('Restored on launch')).toBeTruthy())
    expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy()
  })

  it('clears restored import state and persisted session', async () => {
    const clearSpy = vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: { importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot } })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())
    fireEvent.click(screen.getByText('Clear Imported Session'))

    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())
    expect(clearSpy).toHaveBeenCalled()
    expect(screen.queryByText('Clear Imported Session')).toBeNull()
  })

  it('passes imported analysis into the backtest workspace', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(allocationBacktestPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Loaded file: IB2025.pdf')).toBeTruthy())
    fireEvent.click(screen.getByText('Backtest'))

    await waitFor(() => expect(screen.getByText('Current Import')).toBeTruthy())
    expect(screen.getByText('$50000.00')).toBeTruthy()

    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
  })

  it('resets the local workspace database from the dashboard', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: { importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot } })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const resetSpy = vi.spyOn(portfolioWorkspaceStorage, 'resetLocalPortfolioDatabase').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByText('Portfolio Value')).toBeTruthy())
    fireEvent.click(screen.getByText('Reset Local DB'))

    await waitFor(() => expect(resetSpy).toHaveBeenCalled())
    expect(screen.getByText('Import Portfolio')).toBeTruthy()
  })

  it('keeps exposure and dashboard views usable after importing a portfolio', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })
    fireEvent.change(input, { target: { files: [file2026] } })

    await waitFor(() => expect(screen.getByText('Portfolio Value')).toBeTruthy())
    expect(screen.getByLabelText('Sector allocation pie chart')).toBeTruthy()
    expect(screen.getByText('Saved Variants')).toBeTruthy()
    expect(screen.getByText(/^base · active$/)).toBeTruthy()

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByText('Broad Market Risk')).toBeTruthy())
    expect(screen.getByText('Actual Exposure')).toBeTruthy()

    fireEvent.click(screen.getByText('Dashboard'))
    await waitFor(() => expect(screen.getByLabelText('Sector allocation pie chart')).toBeTruthy())
  })

  it('saves a draft as a child variant and shows it in the variant list', async () => {
    const importedWorkspace = mockImportedWorkspace()
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'saveVariantFromDraft').mockResolvedValue({
      node: variantNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({
      ...importedWorkspace.draft,
      baseNodeId: 'node-2',
      status: 'clean',
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockImplementation(async () => [importedWorkspace.rootNode, variantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:10:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })

    await waitFor(() => expect(screen.getByText('Portfolio Value')).toBeTruthy())

    const variantNameInput = screen.getByPlaceholderText('Variant name')
    fireEvent.change(variantNameInput, { target: { value: 'Raise MSFT' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save Variant' }))

    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    const variantRow = screen.getByText((content) => content.includes('Raise MSFT') && content.includes('active'))
    expect(variantRow).toBeTruthy()
  })

  it('opens a saved variant by creating a clean working draft from that node', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)

    const variantNode = mockSavedVariantNode()
    const cleanVariantDraft = {
      id: 'draft-2',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-2',
      updatedAt: '2026-04-10T00:12:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: persistedSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: {
        importedFileNames: ['IB2025.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' },
        importedHistorySnapshot: bootstrapPayload.snapshot,
      },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return variantNode
      return { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(cleanVariantDraft)
    const persistActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getAllByRole('button', { name: 'Open' }).find((button) => !button.hasAttribute('disabled')) as HTMLButtonElement)

    await waitFor(() => expect(persistActiveNodeSpy).toHaveBeenCalledWith({ workspaceId: 'workspace-1', nodeId: 'node-2', createDraftFromNode: true }))
    expect(screen.getByLabelText('Sector allocation pie chart')).toBeTruthy()
    expect(screen.getByText('Portfolio Value')).toBeTruthy()
  })

  it('shows base and child variant lineage consistently after reload', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: {
        importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' },
        importedHistorySnapshot: bootstrapPayload.snapshot,
      },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    expect(screen.getByText(/^base$/)).toBeTruthy()
    expect(screen.getByText(/base -> Raise MSFT/)).toBeTruthy()

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    expect(screen.getByText('Working Draft · base -> Raise MSFT')).toBeTruthy()
  })

  it('reuses imported diagnostics when selecting the base snapshot in Exposure after reload', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: {
        importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' },
        importedHistorySnapshot: bootstrapPayload.snapshot,
      },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-1'
      ? { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
      : variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-1' } })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
    expect(fetchMock.mock.calls[4]?.[0]).toBe('/api/engines/diagnostics/run-imported')
  })

  it('uses history-aware snapshot diagnostics for saved variants in Exposure', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'migrateLegacyImportSession').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-2',
      source: {
        importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' },
        importedHistorySnapshot: bootstrapPayload.snapshot,
      },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-2', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    await waitFor(() => expect(screen.getByText('Saved Variants')).toBeTruthy())
    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-2' } })

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
    expect(fetchMock.mock.calls[4]?.[0]).toBe('/api/engines/diagnostics/run')
    expect(String(fetchMock.mock.calls[4]?.[1]?.body)).toContain('history_context')
  })
})
