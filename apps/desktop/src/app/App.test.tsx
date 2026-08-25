import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createFf2026DiagnosticsEngineFixture, createFf2026ExposureEngineFixture, createIb2026DiagnosticsEngineFixture, createIb2026ExposureEngineFixture, createImportedBootstrapResponseFixture, createImportedDashboardHistoryFixture } from '../test/portfolioFixtures'
import {
  ff2026DashboardGolden,
  ff2026ImportedDashboardGoldenFixture,
  ib2026DashboardGolden,
  ib2026ImportedDashboardGoldenFixture,
} from '../test/dashboardGoldens'
import { App } from './App'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import * as portfolioAnalysisAdapter from '../features/portfolio/portfolioAnalysisAdapter'
import { mapImportedHistoryContextToWorkspace } from '../features/portfolio/importedBootstrapMapper'
import type { ExposureEngineResponse, ImportedExposureOverride, ImportedSnapshot, PortfolioOverview } from '../features/portfolio/types'
import type { ImportedHistoryContext, ImportedNodeSource, PortfolioNode, PortfolioSnapshot, PortfolioWorkspace, WorkingDraft, WorkspaceState } from '../features/portfolio/workspaceTypes'

vi.mock('@tauri-apps/plugin-dialog', () => ({
  open: vi.fn(),
}))

vi.mock('@tauri-apps/plugin-fs', () => ({
  readFile: vi.fn(),
}))

async function importTauriPlugins() {
  const [{ open }, { readFile }] = await Promise.all([
    import('@tauri-apps/plugin-dialog'),
    import('@tauri-apps/plugin-fs'),
  ])

  return {
    open: vi.mocked(open),
    readFile: vi.mocked(readFile),
  }
}

function installTauriRuntime() {
  Object.defineProperty(window, '__TAURI_INTERNALS__', {
    value: {},
    configurable: true,
  })
}

const exposurePayload = createExposureEngineFixture()
const diagnosticsPayload = createDiagnosticsEngineFixture()
const bootstrapPayload = createImportedBootstrapResponseFixture()
const dashboardHistoryPayload = createImportedDashboardHistoryFixture()

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// Selecting an Exposure snapshot fires runDriftEngine; most App tests don't
// register that route, so it previously fell through and logged a noisy
// "[drift] FAILED: Unhandled fetch" (the app swallows the error, tests still
// pass). Serve a harmless unavailable DriftResult here so the stub honestly
// models what the app calls. Genuinely-unknown routes still throw (safety net).
const _driftFallbackPayload = {
  windows: [],
  benchmark_symbol: 'SPY',
  daily_series: [],
  availability: 'unavailable' as const,
}

function unhandledOrDrift(pathname: string, method: string): Response {
  if (pathname === '/api/engines/drift/run' && method === 'POST') {
    return jsonResponse(_driftFallbackPayload)
  }
  throw new Error(`Unhandled fetch: ${method} ${pathname}`)
}

function requestUrl(input: RequestInfo | URL) {
  const rawUrl = typeof input === 'string'
    ? input
    : input instanceof URL
      ? input.toString()
      : input.url
  return new URL(rawUrl, 'http://localhost')
}

function requestPathname(input: RequestInfo | URL) {
  return requestUrl(input).pathname
}

function requestSearchParam(input: RequestInfo | URL, key: string) {
  return requestUrl(input).searchParams.get(key)
}

function requestMethod(input: RequestInfo | URL, init?: RequestInit) {
  if (init?.method) return init.method.toUpperCase()
  if (typeof input !== 'string' && !(input instanceof URL) && input.method) return input.method.toUpperCase()
  return 'GET'
}

function requestJsonBody(init?: RequestInit) {
  return JSON.parse(typeof init?.body === 'string' ? init.body : String(init?.body ?? '{}'))
}

function matchingFetchCalls(fetchMock: { mock: { calls: ReadonlyArray<ReadonlyArray<unknown>> } }, pathname: string, method?: string) {
  return fetchMock.mock.calls.filter((call) => {
    const input = call[0] as RequestInfo | URL
    const init = call[1] as RequestInit | undefined
    return requestPathname(input) === pathname
      && (method == null || requestMethod(input, init) === method.toUpperCase())
  }) as Array<[RequestInfo | URL, RequestInit | undefined]>
}

function installFetchMock(handler: (input: RequestInfo | URL, init?: RequestInit) => Response | Promise<Response>) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    return await handler(input, init)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function cloneMutable<T>(value: unknown): T {
  return JSON.parse(JSON.stringify(value)) as T
}

const ib2026MutableSnapshot = cloneMutable<ImportedSnapshot>(ib2026ImportedDashboardGoldenFixture.snapshot)
const ff2026MutableSnapshot = cloneMutable<ImportedSnapshot>(ff2026ImportedDashboardGoldenFixture.snapshot)
const ib2026MutableOverview = cloneMutable<PortfolioOverview>(ib2026ImportedDashboardGoldenFixture.overview)
const ff2026MutableOverview = cloneMutable<PortfolioOverview>(ff2026ImportedDashboardGoldenFixture.overview)

const ib2026LoadedFiles = [...ib2026DashboardGolden.loadedFiles]
const ff2026LoadedFiles = [...ff2026DashboardGolden.loadedFiles]
const ib2026ImportedDailyStates = ib2026ImportedDashboardGoldenFixture.daily_states as Array<{ date: string }>
const ff2026ImportedDailyStates = ff2026ImportedDashboardGoldenFixture.daily_states as Array<{ date: string }>

const ib2026DashboardHistoryPayload = {
  performance_series: ib2026ImportedDashboardGoldenFixture.performance_series,
  daily_states: ib2026ImportedDashboardGoldenFixture.daily_states,
  source_status: ib2026ImportedDashboardGoldenFixture.source_status,
  benchmark: ib2026ImportedDashboardGoldenFixture.benchmark,
  range_metrics: ib2026ImportedDashboardGoldenFixture.range_metrics,
}
const ib2026ExposurePayload = createIb2026ExposureEngineFixture()
const ib2026DiagnosticsPayload = createIb2026DiagnosticsEngineFixture()
const ib2026BootstrapPayload = {
  snapshot: ib2026MutableSnapshot,
  overview: ib2026MutableOverview,
  risk_summary: ib2026ImportedDashboardGoldenFixture.risk_summary,
   history_context: {
     benchmark_symbol: 'SPY',
     statement_period: ib2026ImportedDashboardGoldenFixture.snapshot.statement.statement_period,
     imported_at: ib2026ImportedDashboardGoldenFixture.snapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
     importer: ib2026ImportedDashboardGoldenFixture.snapshot.statement.importer,
     source_file_names: ib2026LoadedFiles,
      history_start_date: ib2026ImportedDailyStates[0]?.date ?? null,
      history_end_date: ib2026ImportedDailyStates[ib2026ImportedDailyStates.length - 1]?.date ?? null,
   },
}
const ff2026DashboardHistoryPayload = {
  performance_series: ff2026ImportedDashboardGoldenFixture.performance_series,
  daily_states: ff2026ImportedDashboardGoldenFixture.daily_states,
  source_status: ff2026ImportedDashboardGoldenFixture.source_status,
  benchmark: ff2026ImportedDashboardGoldenFixture.benchmark,
  range_metrics: ff2026ImportedDashboardGoldenFixture.range_metrics,
}
const ff2026ExposurePayload = createFf2026ExposureEngineFixture()
const ff2026DiagnosticsPayload = createFf2026DiagnosticsEngineFixture()
const ff2026BootstrapPayload = {
  snapshot: ff2026MutableSnapshot,
  overview: ff2026MutableOverview,
  risk_summary: ff2026ImportedDashboardGoldenFixture.risk_summary,
   history_context: {
     benchmark_symbol: 'SPY',
     statement_period: ff2026ImportedDashboardGoldenFixture.snapshot.statement.statement_period,
     imported_at: ff2026ImportedDashboardGoldenFixture.snapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
     importer: ff2026ImportedDashboardGoldenFixture.snapshot.statement.importer,
     source_file_names: ff2026LoadedFiles,
      history_start_date: ff2026ImportedDailyStates[0]?.date ?? null,
      history_end_date: ff2026ImportedDailyStates[ff2026ImportedDailyStates.length - 1]?.date ?? null,
   },
}
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

const variantSnapshot: PortfolioSnapshot = {
  ...persistedSnapshot,
  importedMeta: {
    ...persistedSnapshot.importedMeta,
    statementPeriod: '2026-01-01 - 2026-04-10',
    sourceFileNames: ['IB2025.pdf', 'IB2026.pdf'],
  },
  positions: [{ symbol: 'AAPL', marketValue: 15000, quantity: 15, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
  cashBalances: [{ currency: 'USD', amount: 500 }],
}

const variantExposurePayload = {
  ...exposurePayload,
  snapshot: {
    ...exposurePayload.snapshot,
    statement: {
      ...exposurePayload.snapshot.statement,
      statement_period: '2026-01-01 - 2026-04-10',
    },
    statement_totals: {
      ...exposurePayload.snapshot.statement_totals,
      ending_nav: 15500,
      starting_nav: 14000,
    },
    positions: [{ symbol: 'AAPL', quantity: 15, market_value: 15000, currency: 'USD', as_of_date: '2026-04-10' }],
    cash_balances: [{ currency: 'USD', ending_cash: 500 }],
  },
  overview: {
    ...exposurePayload.overview,
    total_market_value: 15500,
  },
}

const variantDashboardHistoryPayload = {
  ...dashboardHistoryPayload,
  daily_states: [
    { ...dashboardHistoryPayload.daily_states[0], total_portfolio_value: 14000, external_cash_flow: 0 },
    { ...dashboardHistoryPayload.daily_states[dashboardHistoryPayload.daily_states.length - 1], total_portfolio_value: 15500, external_cash_flow: 0 },
  ],
  performance_series: [
    { ...dashboardHistoryPayload.performance_series[0], portfolio_value: 14000, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
    { ...dashboardHistoryPayload.performance_series[dashboardHistoryPayload.performance_series.length - 1], portfolio_value: 15500, benchmark_price: 105, portfolio_return_pct: 10.71, benchmark_return_pct: 5 },
  ],
}

function buildHistorySource(historyContext: ImportedHistoryContext | null, importedHistorySnapshot: ImportedSnapshot | null) {
  if (importedHistorySnapshot) {
    return {
      kind: 'imported_replay' as const,
      historyContext,
      importedHistorySnapshot,
    }
  }
  if (historyContext) {
    return {
      kind: 'history_context' as const,
      historyContext,
      importedHistorySnapshot: null,
    }
  }
  return {
    kind: 'none' as const,
    historyContext: null,
    importedHistorySnapshot: null,
  }
}

function buildImportedSource(input: {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedNodeSource['importer']
  baseCurrency: string | null
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
  admissionSummary?: ImportedNodeSource['admissionSummary']
  importedExposureOverride?: ImportedExposureOverride | null
}): ImportedNodeSource {
  const source: ImportedNodeSource = {
    importedFileNames: input.importedFileNames,
    importedAt: input.importedAt,
    importer: input.importer,
    baseCurrency: input.baseCurrency,
    historySource: buildHistorySource(input.historyContext ?? null, input.importedHistorySnapshot ?? null),
  }
  if (input.admissionSummary !== undefined) source.admissionSummary = input.admissionSummary
  if (input.importedExposureOverride !== undefined) source.importedExposureOverride = input.importedExposureOverride
  return source
}

// ─── SBIO-still-unclassified regression fixtures (2026-08-24-sbio-still-unclassified-bug/T2) ──
//
// `sbioCorrectExposureOverride` models the 6 fields analyze-upload computes
// once at import time, with SBIO correctly classified. `sbioLossyExposure`
// models runExposureEngine's second, lossy call — SBIO falls to asset_class
// 'other'/sector null (US-37.1's "Unclassified" bucket), with lookthrough,
// market_overlap, current_state_concentration and availability all
// correspondingly degraded. Every one of the 6 fields differs between the
// two so a test asserting the override "won" can't pass by accident.
function buildSbioCorrectExposureOverride(): ImportedExposureOverride {
  const base = createExposureEngineFixture()
  return {
    overview: {
      ...base.overview,
      sector_allocation: [...base.overview.sector_allocation, { sector: 'Health Care', market_value: 357.05, weight: 0.0055 }],
      sector_position_breakdown: {
        ...base.overview.sector_position_breakdown,
        'Health Care': [{ symbol: 'SBIO', market_value: 357.05, weight: 0.0055 }],
      },
    },
    lookthrough: {
      ...base.lookthrough,
      uncovered_positions: [],
      coverage_ratio: 1,
    },
    lookthrough_sector_exposure: [...base.lookthrough_sector_exposure, { sector: 'Health Care', market_value: 357.05, weight: 0.0055 }],
    market_overlap: {
      ...base.market_overlap,
      active_share: 0.62,
    },
    current_state_concentration: {
      ...base.current_state_concentration,
      top_sectors: [...base.current_state_concentration.top_sectors, { name: 'Health Care', market_value: 357.05, weight: 0.0055 }],
    },
    availability: {
      lookthrough_status: 'live',
      lookthrough_confidence: 'high',
      benchmark_overlap_status: 'live',
      benchmark_overlap_confidence: 'high',
      note: null,
    },
  }
}

function buildSbioLossyExposure(): ExposureEngineResponse {
  const base = createExposureEngineFixture()
  return {
    ...base,
    overview: {
      ...base.overview,
      sector_allocation: [...base.overview.sector_allocation, { sector: 'Unclassified', market_value: 357.05, weight: 0.0055 }],
      sector_position_breakdown: {
        ...base.overview.sector_position_breakdown,
        Unclassified: [{ symbol: 'SBIO', market_value: 357.05, weight: 0.0055 }],
      },
    },
    lookthrough: {
      ...base.lookthrough,
      uncovered_positions: ['SBIO'],
      coverage_ratio: 0.85,
    },
    lookthrough_sector_exposure: [...base.lookthrough_sector_exposure, { sector: 'Unclassified', market_value: 357.05, weight: 0.0055 }],
    market_overlap: {
      ...base.market_overlap,
      active_share: 0.7,
    },
    current_state_concentration: {
      ...base.current_state_concentration,
      top_sectors: [...base.current_state_concentration.top_sectors, { name: 'Unclassified', market_value: 357.05, weight: 0.0055 }],
    },
    availability: {
      lookthrough_status: 'partial',
      lookthrough_confidence: 'medium',
      benchmark_overlap_status: 'partial',
      benchmark_overlap_confidence: 'medium',
      note: 'SBIO could not be resolved to a sector.',
    },
  }
}
const ib2026HistoryContext = mapImportedHistoryContextToWorkspace(ib2026BootstrapPayload.history_context)
const ff2026HistoryContext = mapImportedHistoryContextToWorkspace(ff2026BootstrapPayload.history_context)

function mockImportedWorkspace(): { workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: WorkingDraft; workspaceState: WorkspaceState } {
  return {
    workspace: { id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) },
    rootNode: { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base' as const, name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
    draft: { id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean' as const, portfolioSnapshot: persistedSnapshot },
    workspaceState: { workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:00:00Z' },
  }
}

function mockImportedWorkspaceRestore(importedWorkspace: { workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: WorkingDraft }) {
  vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(importedWorkspace.workspace)
  vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(importedWorkspace.rootNode)
  vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(importedWorkspace.draft)
}

function setupAppendedImportedStartupRestoreCase(overrides?: {
  persistedActiveDraftId?: string
  restoredDraft?: WorkingDraft | null
}) {
  const importedWorkspace = mockImportedWorkspace()
  const restoredSnapshot: PortfolioSnapshot = {
    snapshotVersion: 1,
    baseCurrency: 'USD',
    importedMeta: {
      importer: 'interactive_brokers',
      statementPeriod: ib2026MutableSnapshot.statement.statement_period,
      importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
      sourceFileNames: ib2026LoadedFiles,
    },
    positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
      positions.map((position) => ({
        symbol: position.symbol,
        marketValue: position.market_value,
        quantity: null,
        currency: 'USD',
        sector,
        sourceType: 'equity' as const,
      })),
    ),
    cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
    metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
  }
  const restoredImportedSnapshotNode: PortfolioNode = {
    id: 'node-2',
    workspaceId: 'workspace-1',
    parentId: 'node-1',
    kind: 'imported_snapshot',
    name: 'IB 2026',
    createdAt: '2026-04-14T00:00:00Z',
    changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
    portfolioSnapshot: restoredSnapshot,
    source: buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
  }

  vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({
    workspaceId: 'workspace-1',
    activeNodeId: 'node-2',
    activeDraftId: overrides?.persistedActiveDraftId ?? 'draft-2',
    selectedExposureSnapshotId: 'draft',
    lastOpenedAt: '2026-04-14T00:00:00Z',
  })
  vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([importedWorkspace.rootNode, restoredImportedSnapshotNode])
  vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
    ...importedWorkspace.workspace,
    activeNodeId: 'node-2',
    updatedAt: '2026-04-14T00:00:00Z',
  })
  vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
    if (nodeId === 'node-2') return restoredImportedSnapshotNode
    if (nodeId === 'node-1') return importedWorkspace.rootNode
    return null
  })
  vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(overrides?.restoredDraft ?? null)

  installFetchMock(async (input, init) => {
    const pathname = requestPathname(input)
    const method = requestMethod(input, init)
    if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
    if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
    if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
    return unhandledOrDrift(pathname, method)
  })

  return { importedWorkspace, restoredImportedSnapshotNode, restoredSnapshot }
}
function sectorPositionsByName(overview: PortfolioOverview): Record<string, Array<{ symbol: string; market_value: number; weight: number }>> {
  return overview.sector_position_breakdown
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
    portfolioSnapshot: variantSnapshot,
  }
}

afterEach(() => {
  cleanup()
  delete (window as Window & { __TAURI_INTERNALS__?: unknown }).__TAURI_INTERNALS__
  delete (window as Window & { __TAURI__?: unknown }).__TAURI__
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

describe('App', () => {
  it('adds a new imported snapshot node from Dashboard Add Statement', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    mockImportedWorkspaceRestore(importedWorkspace)
    const importedSnapshotNode: PortfolioNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'IB 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 },
      portfolioSnapshot: persistedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ['IB2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
      },
    }
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, importedSnapshotNode])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    const saveImportedSnapshotNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: importedSnapshotNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        ...importedWorkspace.draft,
        baseNodeId: 'node-2',
        updatedAt: '2026-04-10T00:05:00Z',
      } satisfies WorkingDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const addSnapshotBootstrapPayload = {
      ...bootstrapPayload,
      snapshot: {
        ...bootstrapPayload.snapshot,
        statement: { ...bootstrapPayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...bootstrapPayload.snapshot.statements[0], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf', imported_at: '2026-04-10T00:05:00Z', page_count: 17 }],
        positions: bootstrapPayload.snapshot.positions.map((position) => ({ ...position, as_of_date: '2026-04-08' })),
      },
      history_context: { ...bootstrapPayload.history_context, statement_period: '2026-01-01 - 2026-04-08', source_file_names: ['IB2026.pdf'], history_end_date: '2026-04-08' },
    }

    const fetchMock = vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(addSnapshotBootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...appendedExposurePayload, snapshot: { ...appendedExposurePayload.snapshot, statement: { ...appendedExposurePayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' }, statements: [{ ...appendedExposurePayload.snapshot.statements[1], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf' }] } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...appendedDiagnosticsPayload, snapshot: { ...appendedDiagnosticsPayload.snapshot, statement: { ...appendedDiagnosticsPayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' }, statements: [{ ...appendedDiagnosticsPayload.snapshot.statements[1], statement_period: '2026-01-01 - 2026-04-08', source_path: 'C:\\docs\\IB2026.pdf' }] } }), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [file2026] } })

    // Wait for both analyze-upload calls (initial + Add Statement). Asserting
    // on total fetchMock.calls is brittle — drift / attribution / etc. fetches
    // shift the count; the meaningful contract is "two analyze-uploads happened".
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')).toHaveLength(2))

    const analyzeCalls = matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')
    const appendAnalyzeBody = analyzeCalls[1]?.[1]?.body as FormData
    const uploadedFiles = appendAnalyzeBody.getAll('statement_files') as File[]
    expect(uploadedFiles.map((file) => file.name)).toEqual(['IB2026.pdf'])
    expect(saveImportedSnapshotNodeSpy).toHaveBeenCalledWith(expect.objectContaining({ workspaceId: 'workspace-1', parentNodeId: 'node-1', importedFileNames: ['IB2026.pdf'], name: 'IB 2026-04-08' }))
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.portfolioSnapshot.importedMeta.sourceFileNames).toContain('IB2026.pdf')
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.portfolioSnapshot.positions.some((position: { symbol: string }) => position.symbol === 'AAPL')).toBe(true)
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.historyContext?.sourceFileNames).toEqual(['IB2025.pdf', 'IB2026.pdf'])
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.historyContext?.historyEndDate).toBe('2026-04-08')
    await waitFor(() => expect(saveImportedSnapshotNodeSpy).toHaveBeenCalled())
  })


  it('uses the Tauri picker path and preserves PDF multipart metadata', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    const createWorkspaceFromImportSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    const getWorkspaceSpy = vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(mockImportedWorkspace().workspace)
    const getNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(mockImportedWorkspace().rootNode)
    const getDraftSpy = vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(mockImportedWorkspace().draft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue('D:\\brokerage\\IB2026.pdf')
    readFile.mockResolvedValue(new Uint8Array([50, 48, 50, 54]))

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(createWorkspaceFromImportSpy).toHaveBeenCalledWith(expect.objectContaining({ importedFileNames: ['IB2026.pdf'] })))
    await waitFor(() => expect(getWorkspaceSpy).toHaveBeenCalledWith('workspace-1'))
    expect(getNodeSpy).toHaveBeenCalledWith('node-1')
    expect(getDraftSpy).toHaveBeenCalledWith('workspace-1')

    expect(open).toHaveBeenCalledWith({
      multiple: true,
      directory: false,
      filters: [{ name: 'Broker Statements', extensions: ['pdf', 'csv'] }],
    })
    expect(readFile).toHaveBeenCalledWith('D:\\brokerage\\IB2026.pdf')
    const analyzeBody = matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')[0]?.[1]?.body as FormData
    const uploadedFiles = analyzeBody.getAll('statement_files') as File[]
    expect(uploadedFiles).toHaveLength(1)
    expect(uploadedFiles[0]).toMatchObject({ name: 'IB2026.pdf', type: 'application/pdf' })
  })

  it('accepts csv statements in the file input and uploads them with text/csv metadata', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(mockImportedWorkspace().workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(mockImportedWorkspace().rootNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(mockImportedWorkspace().draft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input.getAttribute('accept')).toBe('application/pdf,.pdf,text/csv,.csv')

    const csvFile = new File(['Statement,Header'], 'IB2026.csv', { type: 'text/csv', lastModified: 1 })
    fireEvent.change(input, { target: { files: [csvFile] } })

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')).toHaveLength(1))
    const analyzeBody = matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')[0]?.[1]?.body as FormData
    const uploadedFiles = analyzeBody.getAll('statement_files') as File[]
    expect(uploadedFiles).toHaveLength(1)
    expect(uploadedFiles[0]).toMatchObject({ name: 'IB2026.csv', type: 'text/csv' })
  })

  it('keeps csv paths in the Tauri picker selection', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(mockImportedWorkspace().workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(mockImportedWorkspace().rootNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(mockImportedWorkspace().draft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(exposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(diagnosticsPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue(['D:\\brokerage\\IB2026.csv', 'D:\\brokerage\\notes.txt'])
    readFile.mockResolvedValue(new Uint8Array([50, 48, 50, 54]))

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')).toHaveLength(1))
    expect(readFile).toHaveBeenCalledWith('D:\\brokerage\\IB2026.csv')
    expect(readFile).not.toHaveBeenCalledWith('D:\\brokerage\\notes.txt')
    const analyzeBody = matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')[0]?.[1]?.body as FormData
    const uploadedFiles = analyzeBody.getAll('statement_files') as File[]
    expect(uploadedFiles.map((file) => ({ name: file.name, type: file.type }))).toEqual([{ name: 'IB2026.csv', type: 'text/csv' }])
  })

  it('fails closed when the Tauri file bridge reads an empty PDF', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const fetchMock = vi.spyOn(globalThis, 'fetch')

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue('D:\\brokerage\\IB2026.pdf')
    readFile.mockResolvedValue(new Uint8Array())

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(screen.getAllByText('Tauri import failed: could not read "IB2026.pdf" because the selected statement was empty').length).toBeGreaterThan(0))
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('maps Tauri analyze-upload network failures to a Tauri import error', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') {
        throw new TypeError('Failed to fetch')
      }
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue('D:\\brokerage\\IB2026.pdf')
    readFile.mockResolvedValue(new Uint8Array([50, 48, 50, 54]))

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(screen.getAllByText('Tauri import failed: unable to reach the local import service while analyzing the selected statement files').length).toBeGreaterThan(0))
    expect(matchingFetchCalls(fetchMock, '/api/portfolios/import/interactive-brokers/analyze-upload', 'POST')).toHaveLength(1)
  })

  it('times out Tauri analyze-upload requests with a Tauri import error', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const originalSetTimeout = window.setTimeout.bind(window)
    vi.spyOn(window, 'setTimeout').mockImplementation(((handler: TimerHandler, timeout?: number, ...args: unknown[]) => {
      const effectiveTimeout = timeout === 30_000 ? 0 : timeout
      return originalSetTimeout(handler, effectiveTimeout, ...args)
    }) as typeof window.setTimeout)

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') {
        if (init?.signal?.aborted) {
          throw new DOMException('Aborted', 'AbortError')
        }
        return await new Promise<Response>((_, reject) => {
          init?.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')), { once: true })
        })
      }
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Import Portfolio')).toBeTruthy())

    installTauriRuntime()
    const { open, readFile } = await importTauriPlugins()
    open.mockResolvedValue('D:\\brokerage\\IB2026.pdf')
    readFile.mockResolvedValue(new Uint8Array([50, 48, 50, 54]))

    fireEvent.click(screen.getByText('Import Portfolio'))

    await waitFor(() => expect(screen.getAllByText('Tauri import failed: the local import service timed out while analyzing the selected statement files').length).toBeGreaterThan(0))
  })



  it('refreshes dashboard allocation and cards after adding a statement snapshot', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    mockImportedWorkspaceRestore(importedWorkspace)
    const addedSnapshot = {
      ...persistedSnapshot,
      importedMeta: {
        ...persistedSnapshot.importedMeta,
        statementPeriod: '2026-01-01 - 2026-04-08',
        sourceFileNames: ['IB2025.pdf', 'FF2026.pdf'],
      },
      positions: [
        { symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' as const },
        { symbol: 'JPM', marketValue: 5000, quantity: 20, currency: 'USD', sector: 'Financials', sourceType: 'equity' as const },
      ],
      cashBalances: [{ currency: 'USD', amount: 1200 }],
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'FF 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'FF 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: addedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ['FF2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'freedom24', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'freedom24', sourceFileNames: ['IB2025.pdf', 'FF2026.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: null }),
      },
    }
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, importedSnapshotNode])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: importedSnapshotNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({
        ...importedWorkspace.draft,
        baseNodeId: 'node-2',
        portfolioSnapshot: addedSnapshot,
        updatedAt: '2026-04-10T00:05:00Z',
      })
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const ffBootstrapPayload = {
      ...bootstrapPayload,
      snapshot: {
        ...bootstrapPayload.snapshot,
        statement: { ...bootstrapPayload.snapshot.statement, importer: 'freedom24', statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...bootstrapPayload.snapshot.statements[0], importer: 'freedom24', source_path: 'C:\\docs\\FF2026.pdf', statement_period: '2026-01-01 - 2026-04-08', imported_at: '2026-04-10T00:05:00Z' }],
        positions: [
          { ...bootstrapPayload.snapshot.positions[0], symbol: 'JPM', market_value: 5000, quantity: 20, as_of_date: '2026-04-08' },
        ],
      },
      history_context: {
        ...bootstrapPayload.history_context,
        importer: 'freedom24',
        statement_period: '2026-01-01 - 2026-04-08',
        source_file_names: ['FF2026.pdf'],
        history_end_date: '2026-04-08',
      },
    }

    const ffExposurePayload = {
      ...exposurePayload,
      snapshot: {
        ...exposurePayload.snapshot,
        statement: { ...exposurePayload.snapshot.statement, importer: 'freedom24', statement_period: '2026-01-01 - 2026-04-08' },
        statements: [{ ...exposurePayload.snapshot.statements[0], importer: 'freedom24', source_path: 'C:\\docs\\FF2026.pdf', statement_period: '2026-01-01 - 2026-04-08' }],
        positions: [
          { ...exposurePayload.snapshot.positions[0], symbol: 'AAPL', market_value: 10000, quantity: 10 },
          { ...exposurePayload.snapshot.positions[0], symbol: 'JPM', market_value: 5000, quantity: 20 },
        ],
      },
      overview: {
        ...exposurePayload.overview,
        total_market_value: 15000,
        sector_allocation: [
          { sector: 'Technology', market_value: 10000, weight: 2 / 3 },
          { sector: 'Financials', market_value: 5000, weight: 1 / 3 },
        ],
        sector_position_breakdown: {
          Technology: [{ symbol: 'AAPL', market_value: 10000, weight: 2 / 3 }],
          Financials: [{ symbol: 'JPM', market_value: 5000, weight: 1 / 3 }],
        },
      },
    }

    const unavailableHistoryPayload = { performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null }

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ffBootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      // T-40.2.2b: add_snapshot's base source is `imported_replay`
      // (mockImportedWorkspace's root node carries `bootstrapPayload.snapshot`
      // as its importedHistorySnapshot), so `processImportedFiles` now calls
      // `combineImportedSnapshots` (POST /api/portfolios/import/combine-snapshots)
      // before saving the node — an extra fetch not present before T-40.2.2b.
      .mockResolvedValueOnce(new Response(JSON.stringify(ffBootstrapPayload.snapshot), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(unavailableHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ffExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const ibFile = new File(['ib'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    const ffFile = new File(['ff'], 'FF2026.pdf', { type: 'application/pdf', lastModified: 2 })

    fireEvent.change(input, { target: { files: [ibFile] } })
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [ffFile] } })

    await waitFor(() => expect(screen.getAllByText('Loaded file: FF2026.pdf').length).toBeGreaterThan(0))
    expect(screen.queryByText('$15000.00')).toBeNull()
  })

  // ─── US-40.2 / T-40.2.3 — add_snapshot preserves imported history ──────────
  //
  // `processImportedFiles`'s `add_snapshot` branch (App.tsx, per 05-technical-plan.md
  // § US-40.2 design) now combines the base node's already-frozen
  // `importedHistorySnapshot` with the newly-imported statement via the new
  // `POST /api/portfolios/import/combine-snapshots` route, instead of always
  // passing `importedHistorySnapshot: null` to `saveImportedSnapshotNode`.

  function installUS402FetchMock(handlers: {
    onCombineSnapshots?: (body: { snapshots: unknown[] }) => Response | Promise<Response>
    analyzeUploadResponses: unknown[]
  }) {
    let analyzeUploadCallCount = 0
    return installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') {
        const payload = handlers.analyzeUploadResponses[analyzeUploadCallCount] ?? handlers.analyzeUploadResponses[handlers.analyzeUploadResponses.length - 1]
        analyzeUploadCallCount += 1
        return jsonResponse(payload)
      }
      if (pathname === '/api/portfolios/import/combine-snapshots' && method === 'POST') {
        if (handlers.onCombineSnapshots) return handlers.onCombineSnapshots(requestJsonBody(init))
        return jsonResponse(requestJsonBody(init).snapshots[requestJsonBody(init).snapshots.length - 1])
      }
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })
  }

  it('add_snapshot combines the base imported_replay history with the new statement and saves it non-null (AC1, AC2)', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    mockImportedWorkspaceRestore(importedWorkspace)
    const addedSnapshot = { ...persistedSnapshot, positions: [{ symbol: 'JPM', marketValue: 5000, quantity: 20, currency: 'USD', sector: 'Financials', sourceType: 'equity' as const }] }
    const addedNode: PortfolioNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot',
      name: 'IB 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'IB 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: addedSnapshot,
      source: buildImportedSource({ importedFileNames: ['IB2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf', 'IB2026.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: appendedExposurePayload.snapshot }),
    }
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, addedNode])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    const saveImportedSnapshotNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: addedNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return addedNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({ ...importedWorkspace.draft, baseNodeId: 'node-2', portfolioSnapshot: addedSnapshot, updatedAt: '2026-04-10T00:05:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const ffBootstrapPayload = { ...bootstrapPayload, snapshot: { ...bootstrapPayload.snapshot, statement: { ...bootstrapPayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' } } }
    // The value the combine-snapshots route returns — must be distinct from
    // both inputs so the assertion below can't pass by the route being a
    // pass-through of either snapshot alone.
    const combinedSnapshotFromRoute = { ...appendedExposurePayload.snapshot, statements: [...appendedExposurePayload.snapshot.statements, { ...ffBootstrapPayload.snapshot.statements[0] }] }

    let combineSnapshotsRequestBody: { snapshots: unknown[] } | null = null
    installUS402FetchMock({
      analyzeUploadResponses: [bootstrapPayload, ffBootstrapPayload],
      onCombineSnapshots: (body) => {
        combineSnapshotsRequestBody = body
        return jsonResponse(combinedSnapshotFromRoute)
      },
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['ib'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })] } })
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [new File(['ib26'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })] } })

    await waitFor(() => expect(saveImportedSnapshotNodeSpy).toHaveBeenCalled())

    // AC1/AC2: the base's frozen importedHistorySnapshot (`bootstrapPayload.snapshot`,
    // set on the root node by `mockImportedWorkspace()`) and the newly-imported
    // statement's own snapshot are both sent to combine-snapshots ...
    expect(combineSnapshotsRequestBody).not.toBeNull()
    expect(combineSnapshotsRequestBody!.snapshots).toEqual([bootstrapPayload.snapshot, ffBootstrapPayload.snapshot])
    // ... and the route's own combined result — not `null`, not either input
    // alone — is what gets persisted, replacing today's literal `null`.
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.importedHistorySnapshot).toEqual(combinedSnapshotFromRoute)
  })

  it('add_snapshot discloses degradation and saves a null importedHistorySnapshot when combine-snapshots fails (AC3)', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    mockImportedWorkspaceRestore(importedWorkspace)
    const addedSnapshot = { ...persistedSnapshot, positions: [{ symbol: 'JPM', marketValue: 5000, quantity: 20, currency: 'USD', sector: 'Financials', sourceType: 'equity' as const }] }
    const addedNode: PortfolioNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot',
      name: 'IB 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'IB 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: addedSnapshot,
      source: buildImportedSource({ importedFileNames: ['IB2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf', 'IB2026.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: null }),
    }
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, addedNode])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    const saveImportedSnapshotNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: addedNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return addedNode
      if (nodeId === 'node-1') return importedWorkspace.rootNode
      return null
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce({ ...importedWorkspace.draft, baseNodeId: 'node-2', portfolioSnapshot: addedSnapshot, updatedAt: '2026-04-10T00:05:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const ffBootstrapPayload = { ...bootstrapPayload, snapshot: { ...bootstrapPayload.snapshot, statement: { ...bootstrapPayload.snapshot.statement, statement_period: '2026-01-01 - 2026-04-08' } } }

    installUS402FetchMock({
      analyzeUploadResponses: [bootstrapPayload, ffBootstrapPayload],
      onCombineSnapshots: () => jsonResponse({ detail: 'Cannot combine snapshots with differing base currencies' }, 400),
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['ib'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })] } })
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    fireEvent.change(input, { target: { files: [new File(['ib26'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })] } })

    await waitFor(() => expect(saveImportedSnapshotNodeSpy).toHaveBeenCalled())

    // AC3: degradation is disclosed, not silently dropped or fabricated —
    // the node is still saved (positions preserved), but with a null
    // importedHistorySnapshot rather than a fabricated/partial merge.
    expect(saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]?.importedHistorySnapshot).toBeNull()
    await waitFor(() => expect(screen.getAllByText(/could not be combined with the existing imported history/).length).toBeGreaterThan(0))
  })

  it('add_snapshot combines against the already-accumulated chain result, not just the immediate parent (sequential-add regression)', async () => {
    // The active node is itself a prior add_snapshot result — its own
    // `source.historySource.importedHistorySnapshot` already represents the
    // combination of every earlier statement in the chain (multiple
    // `statements` entries), not just the immediately-preceding statement.
    const chainAccumulatedSnapshot = { ...bootstrapPayload.snapshot, statements: [...bootstrapPayload.snapshot.statements, { ...bootstrapPayload.snapshot.statements[0] }] }
    const chainNode: PortfolioNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot',
      name: 'IB 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'IB 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: persistedSnapshot,
      source: buildImportedSource({ importedFileNames: ['IB2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-08', importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf', 'IB2026.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2026-04-08' }, importedHistorySnapshot: chainAccumulatedSnapshot }),
    }
    const rootNode: PortfolioNode = { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
    const workspace: PortfolioWorkspace = { id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:05:00Z', rootNodeId: 'node-1', activeNodeId: 'node-2', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) }
    const draft: WorkingDraft = { id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([rootNode, chainNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => (nodeId === 'node-2' ? chainNode : rootNode))
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(draft)
    const saveImportedSnapshotNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: { ...chainNode, id: 'node-3', parentId: 'node-2' },
      workspace: { ...workspace, activeNodeId: 'node-3', updatedAt: '2026-04-10T00:10:00Z' },
      workspaceState: { workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:10:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    const newStatementPayload = { ...bootstrapPayload, snapshot: { ...bootstrapPayload.snapshot, statement: { ...bootstrapPayload.snapshot.statement, statement_period: '2026-04-09 - 2026-04-20' } } }

    let combineSnapshotsRequestBody: { snapshots: unknown[] } | null = null
    installUS402FetchMock({
      analyzeUploadResponses: [newStatementPayload],
      onCombineSnapshots: (body) => {
        combineSnapshotsRequestBody = body
        return jsonResponse(newStatementPayload.snapshot)
      },
    })

    render(<App />)
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['ib3'], 'IB2026-2.pdf', { type: 'application/pdf', lastModified: 3 })] } })

    await waitFor(() => expect(saveImportedSnapshotNodeSpy).toHaveBeenCalled())

    // The FIRST element combine-snapshots is called with is the chain node's
    // own already-accumulated snapshot (multiple `statements` entries), not
    // the workspace root's raw single-statement snapshot — a chained
    // add_snapshot combines against the previous step's own combined result.
    expect(combineSnapshotsRequestBody).not.toBeNull()
    expect(combineSnapshotsRequestBody!.snapshots[0]).toEqual(chainAccumulatedSnapshot)
    expect(combineSnapshotsRequestBody!.snapshots[0]).not.toEqual(bootstrapPayload.snapshot)
  })

  it('replace-mode import is unaffected by US-40.2 — still passes the fresh analyze-upload snapshot directly, no combine-snapshots call (AC4)', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    const createWorkspaceFromImportSpy = vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(mockImportedWorkspace())
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(mockImportedWorkspace().workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(mockImportedWorkspace().rootNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(mockImportedWorkspace().draft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const fetchMock = installUS402FetchMock({ analyzeUploadResponses: [bootstrapPayload] })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(['ib'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })] } })

    await waitFor(() => expect(createWorkspaceFromImportSpy).toHaveBeenCalled())
    expect(createWorkspaceFromImportSpy.mock.calls[0]?.[0]?.importedHistorySnapshot).toEqual(bootstrapPayload.snapshot)
    expect(matchingFetchCalls(fetchMock, '/api/portfolios/import/combine-snapshots', 'POST')).toHaveLength(0)
  })


  it('restores IB2026 dashboard values consistently from persisted imported state', async () => {
    const snapshot = {
      snapshotVersion: 1 as const,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers' as const,
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: ib2026MutableOverview.sector_allocation.flatMap((sector) =>
        (sectorPositionsByName(ib2026MutableOverview)[sector.sector] ?? []).map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector: sector.sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'IB 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 }, portfolioSnapshot: snapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-14T00:00:00Z', updatedAt: '2026-04-14T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'IB 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 }, portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-14T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026DashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ib2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText(ib2026DashboardGolden.loadedFileLabel)).toBeTruthy())

    // US-34.5 (Epic 34 F-10): the benchmark return and the excess reach the
    // screen, measured from the real IB2026 statement. Both rendered "n/a" on
    // every range on every run before this story.
    //
    // The assertion is deliberately not pinned to one range's number — the
    // active range here is not the goldens' `range_key` — so it checks that
    // real percentages render, and the per-range values are checked against the
    // engine response itself below.
    const card = screen.getByRole('region', { name: /performance & benchmark/i })
    const cardText = card.textContent ?? ''
    expect(cardText).toMatch(/Benchmark Return-?\d+\.\d\d%/)
    expect(cardText).toMatch(/Excess Return-?\d+\.\d\d%/)
    expect(ib2026DashboardGolden.benchmarkReturn).not.toBe('n/a')
    expect(ib2026DashboardGolden.excessReturn).not.toBe('n/a')

    // Every range publishes both legs, and the excess is exactly the difference
    // of the two published figures — the same identity the engine asserts.
    for (const metrics of Object.values(ib2026ImportedDashboardGoldenFixture.range_metrics)) {
      const summary = metrics.summary
      expect(summary.benchmark_return_pct).not.toBeNull()
      expect(summary.excess_return_pct).not.toBeNull()
      expect(summary.excess_return_pct).toBeCloseTo(
        Number(summary.time_weighted_return_pct) - Number(summary.benchmark_return_pct),
        2,
      )
    }
  })



  it('restores FF2026 dashboard values consistently from persisted imported state', async () => {
    const snapshot = {
      snapshotVersion: 1 as const,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'freedom24' as const,
        statementPeriod: ff2026MutableSnapshot.statement.statement_period,
        importedAt: ff2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ff2026LoadedFiles,
      },
      positions: ff2026MutableOverview.sector_allocation.flatMap((sector) =>
        (sectorPositionsByName(ff2026MutableOverview)[sector.sector] ?? []).map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector: sector.sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ff2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'FF 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'FF 2026', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 3018.96, netCapitalDelta: 3018.96 }, portfolioSnapshot: snapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-14T00:00:00Z', updatedAt: '2026-04-14T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ff2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'freedom24', baseCurrency: 'USD', historyContext: ff2026HistoryContext, importedHistorySnapshot: ff2026BootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'FF 2026', createdAt: '2026-04-14T00:00:00Z', changeSummary: { label: 'FF 2026', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 3018.96, netCapitalDelta: 3018.96 }, portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-14T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: snapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-14T00:00:00Z' })

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026DiagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026DashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(ff2026ExposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText(ff2026DashboardGolden.loadedFileLabel)).toBeTruthy())
  })















































  it('resets the local workspace database from the dashboard', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({ id: 'workspace-1', name: 'Portfolio Workspace', createdAt: '2026-04-10T00:00:00Z', updatedAt: '2026-04-10T00:00:00Z', rootNodeId: 'node-1', activeNodeId: 'node-1', source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-03-03' }, importedHistorySnapshot: bootstrapPayload.snapshot }) })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([{ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue({ id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const resetSpy = vi.spyOn(portfolioWorkspaceStorage, 'resetLocalPortfolioDatabase').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Reset Local DB')).toBeTruthy())
    fireEvent.click(screen.getByText('Reset Local DB'))

    await waitFor(() => expect(resetSpy).toHaveBeenCalled())
    expect(screen.getByText('Import Portfolio')).toBeTruthy()
  })

  it('keeps the dashboard tab landing-only after importing a portfolio', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    const importedWorkspace = mockImportedWorkspace()
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()
    vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()

    vi.spyOn(globalThis, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify(bootstrapPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(diagnosticsPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(dashboardHistoryPayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))
      .mockResolvedValueOnce(new Response(JSON.stringify(exposurePayload), { status: 200, headers: { 'Content-Type': 'application/json' } }))

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })
    fireEvent.change(input, { target: { files: [file2026] } })

    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())
    expect(screen.queryByText('Project summary')).toBeNull()
    expect(screen.queryByText('Saved Variants')).toBeNull()
    expect(screen.queryByText(/^base · active$/)).toBeNull()
    expect(screen.queryByRole('button', { name: 'Open' })).toBeNull()
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByRole('button', { name: /support layer/i })).toBeNull()
    expect(screen.queryByRole('button', { name: /draft\/tool layer/i })).toBeNull()

    expect(screen.getByRole('button', { name: 'Replace Import' })).toBeTruthy()

    fireEvent.click(screen.getByText('Exposure'))
    // After the post-Epic-12 layout fix, the rolling correlation chart and
    // multi-benchmark correlation table share a combined "Benchmark Correlation"
    // card. Assert that combined card's title to confirm the Exposure tab loaded.
    await waitFor(() => expect(screen.getByText('Benchmark Correlation')).toBeTruthy())
    expect(screen.getByText('Concentration Pack')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())
    expect(screen.queryByText('Detailed review')).toBeNull()
    expect(screen.queryByText('Saved Variants')).toBeNull()
  })

  it('exposes a Risk tab in the nav that activates and renders the Risk panel on click', async () => {
    // Pre-import state: no workspace restored → RiskPanel renders the
    // "Import a portfolio to see…" placeholder. No fetch should fire from
    // the panel because snapshot is null.
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )

    render(<App />)

    // Wait for the initial render so the tab bar is present.
    await waitFor(() => expect(screen.getByRole('button', { name: 'Dashboard' })).toBeTruthy())

    const riskButton = screen.getByRole('button', { name: 'Risk' })
    expect(riskButton).toBeTruthy()

    fireEvent.click(riskButton)

    // RiskPanel is lazy-loaded; wait for its no-snapshot helper text to appear.
    await waitFor(() => expect(screen.getByText(/import a portfolio to see stress scenarios/i)).toBeTruthy())

    // Active state via the `active` CSS class (same convention as Dashboard/Exposure).
    expect(riskButton.className).toMatch(/\bactive\b/)
    expect(screen.getByRole('button', { name: 'Dashboard' }).className).not.toMatch(/\bactive\b/)
    expect(screen.getByRole('button', { name: 'Exposure' }).className).not.toMatch(/\bactive\b/)
  })





  it('shows base and child variant lineage in Exposure snapshot options', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-2'
      ? variantNode
      : { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
      .mockResolvedValueOnce({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const persistActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    // T-40.1.2: the picker's variant/base labels now carry the import/capture
    // date (`resolveNodeImportDate`), so option names gain a `(YYYY-MM-DD)`
    // suffix sourced from `persistedSnapshot.importedMeta.importedAt`
    // ('2026-04-10T00:00:00Z' -> '2026-04-10'), shared by the base node and
    // `variantSnapshot` (which spreads the same `importedAt` unchanged).
    expect(screen.getByRole('option', { name: 'Working Draft · base (2026-04-10)' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'base (2026-04-10)' })).toBeTruthy()
    expect(screen.getByRole('option', { name: 'base -> Raise MSFT (2026-04-10)' })).toBeTruthy()
  })

  it('reuses imported diagnostics when selecting the base snapshot in Exposure after reload', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-1'
      ? { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
      : variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
      .mockResolvedValueOnce({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-2' } })
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(1))
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-1' } })

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST').length).toBeGreaterThanOrEqual(2))
    expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(1)
  })

  it('shows an Exposure header exit CTA after selecting a draft and returns to the imported base snapshot', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-1'
      ? { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot }
      : variantNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    const setSelectedExposureSnapshotSpy = vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'draft' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Return to imported snapshot' })).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: 'Return to imported snapshot' }))

    await waitFor(() => expect(setSelectedExposureSnapshotSpy).toHaveBeenLastCalledWith({ workspaceId: 'workspace-1', snapshotId: 'node-1' }))
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST').length).toBeGreaterThanOrEqual(2))
  })

  it('uses history-aware snapshot diagnostics for saved variants in Exposure', async () => {
    const variantNode = mockSavedVariantNode()

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:12:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildImportedSource({ importedFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2026-01-01 - 2026-04-10', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['ESPP2026.pdf', 'FF2026.pdf', 'IB2026.pdf'], historyStartDate: '2026-01-02', historyEndDate: '2026-04-10' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([
      { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot },
      variantNode,
    ])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => nodeId === 'node-2'
      ? variantNode
      : { id: 'node-1', workspaceId: 'workspace-1', parentId: null, kind: 'imported_base', name: 'Base Import', createdAt: '2026-04-10T00:00:00Z', changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 }, portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce({ id: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', updatedAt: '2026-04-10T00:00:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
      .mockResolvedValueOnce({ id: 'draft-2', workspaceId: 'workspace-1', baseNodeId: 'node-2', updatedAt: '2026-04-10T00:12:00Z', name: 'Working Draft', status: 'clean', portfolioSnapshot: persistedSnapshot })
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-2', activeDraftId: 'draft-2', selectedExposureSnapshotId: 'node-2', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(exposurePayload)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-2' } })

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(1))
    expect(String(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')[0]?.[1]?.body)).toContain('history_context')
  })

  it('returns a saved variant selection to the nearest imported ancestor without changing active workspace state', async () => {
    const baseNode = {
      id: 'node-1',
      workspaceId: 'workspace-1',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Base Import',
      createdAt: '2026-04-10T00:00:00Z',
      changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 },
      portfolioSnapshot: persistedSnapshot,
    }
    const importedSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: importedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
      },
    }
    const importedVariantSnapshot: PortfolioSnapshot = {
      ...importedSnapshot,
      positions: importedSnapshot.positions.map((position, index) => index === 0 ? { ...position, marketValue: position.marketValue + 5000 } : position),
    }
    const importedVariantNode = {
      id: 'node-3',
      workspaceId: 'workspace-1',
      parentId: 'node-2',
      kind: 'variant' as const,
      name: 'Raise SXRV',
      createdAt: '2026-04-14T00:10:00Z',
      changeSummary: { label: 'Raise SXRV', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: importedVariantSnapshot,
    }
    const variantDraft = {
      id: 'draft-3',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-3',
      updatedAt: '2026-04-14T00:10:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: importedVariantSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-2', lastOpenedAt: '2026-04-14T00:10:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:10:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-3',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([baseNode, importedSnapshotNode, importedVariantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-3') return importedVariantNode
      return baseNode
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(variantDraft)
    const setActiveNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'setActiveNode').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-3', lastOpenedAt: '2026-04-14T00:10:00Z' })
    const setSelectedExposureSnapshotSpy = vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockImplementation(async ({ snapshotId }) => ({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: snapshotId, lastOpenedAt: '2026-04-14T00:10:00Z' }))

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(ib2026ExposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(ib2026DashboardHistoryPayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null })
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())

    const variantDiagnosticsCallsBeforeSelection = matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST').length
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-3' } })
    await waitFor(() => expect(screen.getByRole('button', { name: 'Return to imported snapshot' })).toBeTruthy())
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST').length).toBeGreaterThan(variantDiagnosticsCallsBeforeSelection))

    fireEvent.click(screen.getByRole('button', { name: 'Return to imported snapshot' }))

    await waitFor(() => expect(setSelectedExposureSnapshotSpy).toHaveBeenLastCalledWith({ workspaceId: 'workspace-1', snapshotId: 'node-2' }))
    await waitFor(() => expect((screen.getByLabelText('Snapshot') as HTMLSelectElement).value).toBe('node-2'))
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Return to imported snapshot' })).toBeNull())
    expect(setActiveNodeSpy).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Dashboard' }))
    await waitFor(() => expect(screen.getByText('Account overview')).toBeTruthy())
  })

  it('uses snapshot-history diagnostics instead of imported replay for a child variant under an imported snapshot', async () => {
    const baseNode = {
      id: 'node-1',
      workspaceId: 'workspace-1',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Base Import',
      createdAt: '2026-04-10T00:00:00Z',
      changeSummary: { label: 'Base Import', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 10000, netCapitalDelta: 10000 },
      portfolioSnapshot: persistedSnapshot,
    }
    const importedSnapshot: PortfolioSnapshot = {
      snapshotVersion: 1,
      baseCurrency: 'USD',
      importedMeta: {
        importer: 'interactive_brokers',
        statementPeriod: ib2026MutableSnapshot.statement.statement_period,
        importedAt: ib2026MutableSnapshot.statement.imported_at ?? '2026-04-14T00:00:00Z',
        sourceFileNames: ib2026LoadedFiles,
      },
      positions: Object.entries(ib2026MutableOverview.sector_position_breakdown).flatMap(([sector, positions]) =>
        positions.map((position) => ({
          symbol: position.symbol,
          marketValue: position.market_value,
          quantity: null,
          currency: 'USD',
          sector,
          sourceType: 'equity' as const,
        })),
      ),
      cashBalances: Object.entries(ib2026MutableOverview.cash_by_currency).map(([currency, amount]) => ({ currency, amount })),
      metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
    }
    const importedSnapshotNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026',
      createdAt: '2026-04-14T00:00:00Z',
      changeSummary: { label: 'IB 2026', changedPositionsCount: 22, changedSectorsCount: 10, grossExposureDelta: 50368.17, netCapitalDelta: 50368.17 },
      portfolioSnapshot: importedSnapshot,
      source: {
        ...buildImportedSource({ importedFileNames: ib2026LoadedFiles, importedAt: '2026-04-14T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: ib2026HistoryContext, importedHistorySnapshot: ib2026BootstrapPayload.snapshot }),
      },
    }
    const importedVariantSnapshot: PortfolioSnapshot = {
      ...importedSnapshot,
      positions: importedSnapshot.positions.map((position, index) => index === 0 ? { ...position, marketValue: position.marketValue + 5000 } : position),
    }
    const importedVariantNode = {
      id: 'node-3',
      workspaceId: 'workspace-1',
      parentId: 'node-2',
      kind: 'variant' as const,
      name: 'Raise SXRV',
      createdAt: '2026-04-14T00:10:00Z',
      changeSummary: { label: 'Raise SXRV', changedPositionsCount: 1, changedSectorsCount: 1, grossExposureDelta: 5000, netCapitalDelta: 5000 },
      portfolioSnapshot: importedVariantSnapshot,
    }
    const variantDraft = {
      id: 'draft-3',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-3',
      updatedAt: '2026-04-14T00:10:00Z',
      name: 'Working Draft',
      status: 'clean' as const,
      portfolioSnapshot: importedVariantSnapshot,
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-3', lastOpenedAt: '2026-04-14T00:10:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue({
      id: 'workspace-1',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-14T00:10:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-3',
      source: buildImportedSource({ importedFileNames: ['IB2025.pdf'], importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', baseCurrency: 'USD', historyContext: { benchmarkSymbol: 'SPY', statementPeriod: '2025-01-01 - 2025-12-31', importedAt: '2026-04-10T00:00:00Z', importer: 'interactive_brokers', sourceFileNames: ['IB2025.pdf'], historyStartDate: '2025-01-02', historyEndDate: '2025-12-31' }, importedHistorySnapshot: bootstrapPayload.snapshot }),
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([baseNode, importedSnapshotNode, importedVariantNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return importedSnapshotNode
      if (nodeId === 'node-3') return importedVariantNode
      return baseNode
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(variantDraft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-3', activeDraftId: 'draft-3', selectedExposureSnapshotId: 'node-3', lastOpenedAt: '2026-04-14T00:10:00Z' })

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(ib2026ExposurePayload)
      if (pathname === '/api/engines/diagnostics/run-imported' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run-imported' && method === 'POST') return jsonResponse(ib2026DashboardHistoryPayload)
      if (pathname === '/api/engines/diagnostics/run' && method === 'POST') return jsonResponse(ib2026DiagnosticsPayload)
      if (pathname === '/api/engines/dashboard-history/run' && method === 'POST') return jsonResponse({ performance_series: [], daily_states: [], source_status: { performance_history: 'unavailable', monthly_returns: 'unavailable' }, benchmark: null, range_metrics: null })
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-2' } })
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST')).toHaveLength(1))
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-3' } })

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run-imported', 'POST')).toHaveLength(1))
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')).toHaveLength(2))
    expect(String(matchingFetchCalls(fetchMock, '/api/engines/diagnostics/run', 'POST')[1]?.[1]?.body)).toContain('history_context')
  })

  // ─── SBIO-still-unclassified regression coverage (2026-08-24-sbio-still-unclassified-bug/T2) ──

  it('applies the persisted exposure override instead of runExposureEngine\'s lossy response immediately after a replace-mode import', async () => {
    const sbioOverride = buildSbioCorrectExposureOverride()
    const sbioLossy = buildSbioLossyExposure()
    const base = mockImportedWorkspace()
    const importedWorkspace = {
      ...base,
      workspace: { ...base.workspace, source: { ...base.workspace.source, importedExposureOverride: sbioOverride } },
      workspaceState: { ...base.workspaceState, selectedExposureSnapshotId: base.rootNode.id },
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(importedWorkspace.workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(importedWorkspace.rootNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(importedWorkspace.draft)
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const composeExposureViewSpy = vi.spyOn(portfolioAnalysisAdapter, 'composeExposureView')

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if (pathname === '/api/engines/exposure/run' && method === 'POST') return jsonResponse(sbioLossy)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file] } })

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/exposure/run', 'POST')).toHaveLength(1))
    await waitFor(() => expect(composeExposureViewSpy).toHaveBeenCalled())

    // The engine actually returned SBIO under 'Unclassified' (sbioLossy). Every
    // one of the 6 persisted fields must win over it in what gets rendered.
    const [exposureArg] = composeExposureViewSpy.mock.calls[composeExposureViewSpy.mock.calls.length - 1]
    expect(exposureArg.overview).toEqual(sbioOverride.overview)
    expect(exposureArg.lookthrough).toEqual(sbioOverride.lookthrough)
    expect(exposureArg.lookthrough_sector_exposure).toEqual(sbioOverride.lookthrough_sector_exposure)
    expect(exposureArg.market_overlap).toEqual(sbioOverride.market_overlap)
    expect(exposureArg.current_state_concentration).toEqual(sbioOverride.current_state_concentration)
    expect(exposureArg.availability).toEqual(sbioOverride.availability)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByRole('region', { name: 'Top Sectors' })).toBeTruthy())
    const topSectorsText = screen.getByRole('region', { name: 'Top Sectors' }).textContent ?? ''
    expect(topSectorsText).toContain('Health Care')
    expect(topSectorsText).not.toContain('Unclassified')
  })

  it('applies the persisted exposure override instead of runExposureEngine\'s lossy response after a session restore', async () => {
    const sbioOverride = buildSbioCorrectExposureOverride()
    const sbioLossy = buildSbioLossyExposure()
    const base = mockImportedWorkspace()
    const workspace = { ...base.workspace, source: { ...base.workspace.source, importedExposureOverride: sbioOverride } }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([base.rootNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(base.rootNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(base.draft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const composeExposureViewSpy = vi.spyOn(portfolioAnalysisAdapter, 'composeExposureView')

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(sbioLossy)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/exposure/run', 'POST')).toHaveLength(1))
    await waitFor(() => expect(composeExposureViewSpy).toHaveBeenCalled())

    const [exposureArg] = composeExposureViewSpy.mock.calls[composeExposureViewSpy.mock.calls.length - 1]
    expect(exposureArg.overview).toEqual(sbioOverride.overview)
    expect(exposureArg.lookthrough).toEqual(sbioOverride.lookthrough)
    expect(exposureArg.lookthrough_sector_exposure).toEqual(sbioOverride.lookthrough_sector_exposure)
    expect(exposureArg.market_overlap).toEqual(sbioOverride.market_overlap)
    expect(exposureArg.current_state_concentration).toEqual(sbioOverride.current_state_concentration)
    expect(exposureArg.availability).toEqual(sbioOverride.availability)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByRole('region', { name: 'Top Sectors' })).toBeTruthy())
    const topSectorsText = screen.getByRole('region', { name: 'Top Sectors' }).textContent ?? ''
    expect(topSectorsText).toContain('Health Care')
    expect(topSectorsText).not.toContain('Unclassified')
  })

  it('never applies the persisted exposure override on the draft branch, and reuses it when switching back to the imported snapshot', async () => {
    const sbioOverride = buildSbioCorrectExposureOverride()
    const sbioLossy = buildSbioLossyExposure()
    const base = mockImportedWorkspace()
    const workspace = { ...base.workspace, source: { ...base.workspace.source, importedExposureOverride: sbioOverride } }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'node-1', lastOpenedAt: '2026-04-10T00:00:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([base.rootNode])
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspace').mockResolvedValue(workspace)
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockResolvedValue(base.rootNode)
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft').mockResolvedValue(base.draft)
    vi.spyOn(portfolioWorkspaceStorage, 'setSelectedExposureSnapshot').mockResolvedValue({ workspaceId: 'workspace-1', activeNodeId: 'node-1', activeDraftId: 'draft-1', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:12:00Z' })

    const composeExposureViewSpy = vi.spyOn(portfolioAnalysisAdapter, 'composeExposureView')

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(sbioLossy)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    fireEvent.click(screen.getByText('Exposure'))
    await waitFor(() => expect(screen.getByLabelText('Snapshot')).toBeTruthy())
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/exposure/run', 'POST')).toHaveLength(1))

    // Startup restore landed on the imported base node ('node-1') — override applied.
    let [exposureArg] = composeExposureViewSpy.mock.calls[composeExposureViewSpy.mock.calls.length - 1]
    expect(exposureArg.overview).toEqual(sbioOverride.overview)

    // Coverage point 4: switching to the working draft forces
    // importedExposureOverride: null even though the base node carries one —
    // the merged view must fall back to runExposureEngine's lossy response.
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'draft' } })
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/exposure/run', 'POST')).toHaveLength(2))
    ;[exposureArg] = composeExposureViewSpy.mock.calls[composeExposureViewSpy.mock.calls.length - 1]
    expect(exposureArg.overview).toEqual(sbioLossy.overview)
    expect(exposureArg.overview.sector_allocation.some((sector) => sector.sector === 'Unclassified')).toBe(true)

    // Coverage point 5: switching back to the imported base snapshot via
    // handleExposureSnapshotChange reuses the override the same way restore
    // does — parity, not a separate mechanism.
    fireEvent.change(screen.getByLabelText('Snapshot'), { target: { value: 'node-1' } })
    await waitFor(() => expect(matchingFetchCalls(fetchMock, '/api/engines/exposure/run', 'POST')).toHaveLength(3))
    ;[exposureArg] = composeExposureViewSpy.mock.calls[composeExposureViewSpy.mock.calls.length - 1]
    expect(exposureArg.overview).toEqual(sbioOverride.overview)
  })

  it('leaves an add_snapshot node without an exposure override, so the merged view stays on runExposureEngine\'s lossy output', async () => {
    // Coverage point 3 (rendered half): documents the known, deliberately
    // unfixed gap — saveImportedSnapshotNode never receives
    // importedExposureOverride, so an add_snapshot node's merged view keeps
    // showing SBIO 'Unclassified' even though the parent workspace carries a
    // correct override for its own snapshot.
    const sbioOverride = buildSbioCorrectExposureOverride()
    const sbioLossy = buildSbioLossyExposure()
    const base = mockImportedWorkspace()
    const importedWorkspace = {
      ...base,
      workspace: { ...base.workspace, source: { ...base.workspace.source, importedExposureOverride: sbioOverride } },
    }
    mockImportedWorkspaceRestore(importedWorkspace)
    vi.spyOn(portfolioWorkspaceStorage, 'createWorkspaceFromImport').mockResolvedValue(importedWorkspace)

    const addSnapshotNode: PortfolioNode = {
      id: 'node-2',
      workspaceId: 'workspace-1',
      parentId: 'node-1',
      kind: 'imported_snapshot' as const,
      name: 'IB 2026-04-08',
      createdAt: '2026-04-10T00:05:00Z',
      changeSummary: { label: 'IB 2026-04-08', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: 0, netCapitalDelta: 0 },
      portfolioSnapshot: persistedSnapshot,
      source: buildImportedSource({ importedFileNames: ['IB2026.pdf'], importedAt: '2026-04-10T00:05:00Z', importer: 'interactive_brokers', baseCurrency: 'USD' }),
    }

    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes')
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([importedWorkspace.rootNode, addSnapshotNode])
    const saveImportedSnapshotNodeSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveImportedSnapshotNode').mockResolvedValue({
      node: addSnapshotNode,
      workspace: { ...importedWorkspace.workspace, activeNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' },
      workspaceState: { ...importedWorkspace.workspaceState, activeNodeId: 'node-2', selectedExposureSnapshotId: 'draft', lastOpenedAt: '2026-04-10T00:05:00Z' },
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getNode').mockImplementation(async (nodeId: string) => {
      if (nodeId === 'node-2') return addSnapshotNode
      return importedWorkspace.rootNode
    })
    vi.spyOn(portfolioWorkspaceStorage, 'getDraft')
      .mockResolvedValueOnce(importedWorkspace.draft)
      .mockResolvedValueOnce({ ...importedWorkspace.draft, baseNodeId: 'node-2', updatedAt: '2026-04-10T00:05:00Z' })
    vi.spyOn(portfolioWorkspaceStorage, 'saveDraft').mockResolvedValue()

    const composeExposureViewSpy = vi.spyOn(portfolioAnalysisAdapter, 'composeExposureView')

    const fetchMock = installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      if (pathname === '/api/backtests/monitor-definitions/recovered-alert-review-queue' && method === 'GET') return jsonResponse({ items: [] })
      if (pathname === '/api/portfolios/import/interactive-brokers/analyze-upload' && method === 'POST') return jsonResponse(bootstrapPayload)
      if ((pathname === '/api/engines/exposure/run' || pathname === '/api/engines/exposure/run-imported') && method === 'POST') return jsonResponse(sbioLossy)
      if ((pathname === '/api/engines/diagnostics/run' || pathname === '/api/engines/diagnostics/run-imported') && method === 'POST') return jsonResponse(diagnosticsPayload)
      if ((pathname === '/api/engines/dashboard-history/run' || pathname === '/api/engines/dashboard-history/run-imported') && method === 'POST') return jsonResponse(dashboardHistoryPayload)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    const file2025 = new File(['2025'], 'IB2025.pdf', { type: 'application/pdf', lastModified: 1 })
    fireEvent.change(input, { target: { files: [file2025] } })
    await waitFor(() => expect(screen.getByText('Clear Imported Session')).toBeTruthy())

    fireEvent.click(screen.getByText('Add Statement'))
    const file2026 = new File(['2026'], 'IB2026.pdf', { type: 'application/pdf', lastModified: 2 })
    fireEvent.change(input, { target: { files: [file2026] } })

    await waitFor(() => expect(saveImportedSnapshotNodeSpy).toHaveBeenCalled())
    const savedNodeInput = saveImportedSnapshotNodeSpy.mock.calls[0]?.[0]
    expect(savedNodeInput && 'importedExposureOverride' in savedNodeInput).toBe(false)

    await waitFor(() => expect(composeExposureViewSpy.mock.calls.length).toBeGreaterThanOrEqual(2))
    const [exposureArg] = composeExposureViewSpy.mock.calls[composeExposureViewSpy.mock.calls.length - 1]
    expect(exposureArg.overview).toEqual(sbioLossy.overview)
    expect(exposureArg.overview.sector_allocation.some((sector) => sector.sector === 'Unclassified')).toBe(true)
  })

  it('renders exactly Dashboard, Exposure, and Risk tabs', async () => {
    vi.spyOn(portfolioWorkspaceStorage, 'getLastOpenedWorkspaceState').mockResolvedValue(null)
    vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceNodes').mockResolvedValue([])
    installFetchMock(async (input, init) => {
      const pathname = requestPathname(input)
      const method = requestMethod(input, init)
      return unhandledOrDrift(pathname, method)
    })

    render(<App />)

    const tabs = within(screen.getByRole('navigation', { name: 'Main workspace tabs' })).getAllByRole('button').map((el) => el.textContent?.trim())
    expect(tabs).toEqual([
      'Dashboard',
      'Exposure',
      'Risk',
    ])
  })
})
