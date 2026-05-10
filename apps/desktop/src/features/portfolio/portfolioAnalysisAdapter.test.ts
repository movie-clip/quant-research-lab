import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedBootstrapResponseFixture, createImportedDashboardHistoryFixture } from '../../test/portfolioFixtures'
import type { ResolveDesktopApiUrlOptions } from '../../app/apiBase'
import { runDashboardHistoryEngine, runDiagnosticsEngine, runExposureEngine, runImportedDashboardHistory, runImportedDiagnosticsEngine } from './portfolioAnalysisAdapter'
import type { ImportedHistoryContext, PortfolioSnapshot } from './workspaceTypes'

const exposurePayload = createExposureEngineFixture()
const diagnosticsPayload = createDiagnosticsEngineFixture()
const bootstrapPayload = createImportedBootstrapResponseFixture()
const dashboardHistoryPayload = createImportedDashboardHistoryFixture()

const snapshot: PortfolioSnapshot = {
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

const historyContext: ImportedHistoryContext = {
  benchmarkSymbol: 'SPY',
  statementPeriod: '2025-01-01 - 2025-12-31',
  importedAt: '2026-04-10T00:00:00Z',
  importer: 'interactive_brokers',
  sourceFileNames: ['IB2025.pdf'],
  historyStartDate: '2025-01-02',
  historyEndDate: '2025-03-03',
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

afterEach(() => {
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const packagedApiOptions: ResolveDesktopApiUrlOptions = {
  isDev: false,
  desktopApiOrigin: 'https://desktop-backend.example',
}

describe('portfolioAnalysisAdapter API base resolution', () => {
  it('keeps relative engine URLs in a dev-like runtime', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(exposurePayload))
    vi.stubGlobal('fetch', fetchMock)

    await runExposureEngine(snapshot, { isDev: true, desktopApiOrigin: 'https://desktop-backend.example' })

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/engines/exposure/run',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it.each([
    ['exposure', () => runExposureEngine(snapshot, packagedApiOptions), 'https://desktop-backend.example/api/engines/exposure/run', exposurePayload],
    ['diagnostics', () => runDiagnosticsEngine(snapshot, historyContext, packagedApiOptions), 'https://desktop-backend.example/api/engines/diagnostics/run', diagnosticsPayload],
    ['imported diagnostics', () => runImportedDiagnosticsEngine(bootstrapPayload.snapshot, packagedApiOptions), 'https://desktop-backend.example/api/engines/diagnostics/run-imported', diagnosticsPayload],
    ['dashboard-history', () => runDashboardHistoryEngine(snapshot, historyContext, packagedApiOptions), 'https://desktop-backend.example/api/engines/dashboard-history/run', dashboardHistoryPayload],
    ['imported dashboard-history', () => runImportedDashboardHistory(bootstrapPayload.snapshot, packagedApiOptions), 'https://desktop-backend.example/api/engines/dashboard-history/run-imported', dashboardHistoryPayload],
  ])('uses the backend absolute URL for %s in a packaged-like runtime', async (_label, runRequest, expectedUrl, payload) => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload))
    vi.stubGlobal('fetch', fetchMock)

    await runRequest()

    expect(fetchMock).toHaveBeenCalledWith(
      expectedUrl,
      expect.objectContaining({ method: 'POST' }),
    )
  })
})
