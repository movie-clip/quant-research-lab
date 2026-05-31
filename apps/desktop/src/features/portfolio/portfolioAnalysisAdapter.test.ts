import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedBootstrapResponseFixture, createImportedDashboardHistoryFixture } from '../../test/portfolioFixtures'
import type { ResolveDesktopApiUrlOptions } from '../../app/apiBase'
import { runDashboardHistoryEngine, runDiagnosticsEngine, runExposureEngine, runImportedDashboardHistory, runImportedDiagnosticsEngine, runStressEngine } from './portfolioAnalysisAdapter'
import type { StressEngineResponse } from './types'
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

describe('runStressEngine (Epic 13 — Risk tab)', () => {
  const stressPayload: StressEngineResponse = {
    scenarios: [
      { name: 'Broad Market Selloff', estimated_return_pct: -9.42, description: 'risk-off', status: 'ok' },
      { name: 'Rates Down Risk-On', estimated_return_pct: 3.1, description: 'duration', status: 'ok' },
      { name: 'Inflation Reacceleration', estimated_return_pct: -1.5, description: 'sticky inflation', status: 'ok' },
    ],
    trust: 'synthetic',
  }

  it('posts to /api/engines/stress/run with POST method', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(stressPayload))
    vi.stubGlobal('fetch', fetchMock)

    await runStressEngine(snapshot)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/engines/stress/run',
      expect.objectContaining({ method: 'POST' }),
    )
  })

  it('posts the snapshot fields (positions, imported_at) in the request body', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(stressPayload))
    vi.stubGlobal('fetch', fetchMock)

    await runStressEngine(snapshot)

    const callArgs = fetchMock.mock.calls[0]
    const init = callArgs?.[1] as { body?: string } | undefined
    expect(init?.body).toBeTypeOf('string')
    const body = JSON.parse(init!.body!) as { positions: unknown[]; imported_at: string }
    expect(body.imported_at).toBe(snapshot.importedMeta.importedAt)
    expect(body.positions).toHaveLength(snapshot.positions.length)
  })

  it('throws an Error with backend detail on non-2xx response', async () => {
    const errorBody = { detail: 'factor model unavailable' }
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(errorBody, 500))
    vi.stubGlobal('fetch', fetchMock)

    await expect(runStressEngine(snapshot)).rejects.toThrowError(/factor model unavailable/)
  })
})
