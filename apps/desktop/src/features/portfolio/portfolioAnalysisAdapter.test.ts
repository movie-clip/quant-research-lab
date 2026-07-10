import { afterEach, describe, expect, it, vi } from 'vitest'

import { createDiagnosticsEngineFixture, createExposureEngineFixture, createImportedBootstrapResponseFixture, createImportedDashboardHistoryFixture } from '../../test/portfolioFixtures'
import type { ResolveDesktopApiUrlOptions } from '../../app/apiBase'
import { clearCache, runDashboardHistoryEngine, runDiagnosticsEngine, runDistributionEngine, runDrawdownEngine, runDriftEngine, runExposureEngine, runImportedDashboardHistory, runImportedDiagnosticsEngine, runIntraCorrelationEngine, runProvenanceEngine, runStressEngine } from './portfolioAnalysisAdapter'
import type { DistributionEngineResponse, DrawdownEngineResponse, StressEngineResponse } from './types'
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

describe('runIntraCorrelationEngine (Epic 17 — Exposure tab)', () => {
  it('throws an Error with backend detail on non-2xx response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'intra correlation unavailable' }, 500))
    vi.stubGlobal('fetch', fetchMock)

    await expect(runIntraCorrelationEngine(bootstrapPayload.snapshot, 60)).rejects.toThrowError(/intra correlation unavailable/)
  })
})

describe('clearCache (Epic 20 — cache control)', () => {
  it('throws an Error with backend detail on non-2xx response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'cache locked' }, 500))
    vi.stubGlobal('fetch', fetchMock)

    await expect(clearCache(null)).rejects.toThrowError(/cache locked/)
  })
})

describe('runProvenanceEngine (Epic 18 — Exposure tab)', () => {
  it('throws an Error with backend detail on non-2xx response', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'provenance unavailable' }, 500))
    vi.stubGlobal('fetch', fetchMock)

    await expect(runProvenanceEngine(bootstrapPayload.snapshot)).rejects.toThrowError(/provenance unavailable/)
  })
})

describe('runDrawdownEngine (Epic 13 — Risk tab)', () => {
  const drawdownPayload: DrawdownEngineResponse = {
    window_trading_days: 1260,
    underwater_series: [
      { date: '2024-01-02', drawdown_pct: 0 },
      { date: '2024-01-03', drawdown_pct: -2.4 },
    ],
    current_drawdown_pct: -2.4,
    max_drawdown_pct: -2.4,
    episodes: [
      {
        peak_date: '2024-01-02',
        trough_date: '2024-01-03',
        recovery_date: null,
        magnitude_pct: -2.4,
        duration_days: 1,
        underwater_days: 1,
      },
    ],
    trust: 'synthetic',
  }

  it('posts to /api/engines/drawdown/run without window_trading_days when window is null', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(drawdownPayload))
    vi.stubGlobal('fetch', fetchMock)

    await runDrawdownEngine(snapshot)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/engines/drawdown/run',
      expect.objectContaining({ method: 'POST' }),
    )
    const init = fetchMock.mock.calls[0]?.[1] as { body?: string } | undefined
    const body = JSON.parse(init!.body!) as Record<string, unknown>
    expect(body.window_trading_days).toBeUndefined()
  })

  it('posts window_trading_days in the request body when window is provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(drawdownPayload))
    vi.stubGlobal('fetch', fetchMock)

    await runDrawdownEngine(snapshot, 252)

    const init = fetchMock.mock.calls[0]?.[1] as { body?: string } | undefined
    const body = JSON.parse(init!.body!) as { window_trading_days: number }
    expect(body.window_trading_days).toBe(252)
  })
})

describe('runDistributionEngine (Epic 13 — Risk tab US-13.3)', () => {
  const distributionPayload: DistributionEngineResponse = {
    window_trading_days: 252,
    return_count: 247,
    var_95: 2.34,
    var_99: 4.51,
    cvar_95: 3.12,
    percentile_5: -1.84,
    percentile_10: -1.21,
    percentile_50: 0.08,
    percentile_90: 1.42,
    percentile_95: 1.91,
    mean_pct: 0.04,
    std_pct: 0.92,
    skewness: -0.31,
    kurtosis_excess: 2.84,
    histogram_bins: [
      { center: -0.025, count: 3 },
      { center: 0.0, count: 240 },
      { center: 0.025, count: 4 },
    ],
    trust: 'synthetic',
  }

  it('posts to /api/engines/distribution/run with default window_trading_days=252', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(distributionPayload))
    vi.stubGlobal('fetch', fetchMock)

    await runDistributionEngine(snapshot)

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/engines/distribution/run',
      expect.objectContaining({ method: 'POST' }),
    )
    const init = fetchMock.mock.calls[0]?.[1] as { body?: string } | undefined
    const body = JSON.parse(init!.body!) as { window_trading_days: number }
    expect(body.window_trading_days).toBe(252)
  })

  it('posts the supplied window when explicitly provided', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(distributionPayload))
    vi.stubGlobal('fetch', fetchMock)

    await runDistributionEngine(snapshot, 504)

    const init = fetchMock.mock.calls[0]?.[1] as { body?: string } | undefined
    const body = JSON.parse(init!.body!) as { window_trading_days: number }
    expect(body.window_trading_days).toBe(504)
  })
})

describe('runDriftEngine fx_rates plumbing (US-30.2)', () => {
  const driftPayload = {
    windows: [],
    benchmark_symbol: 'SPY',
    daily_series: [],
    availability: 'unavailable',
    fx_fallback_currencies: [],
  }

  it('posts fx_rates from snapshot.fxRates when present', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(driftPayload))
    vi.stubGlobal('fetch', fetchMock)

    await runDriftEngine({ ...snapshot, fxRates: { EURUSD: 1.1422, GBPUSD: 1.3261 } }, 'SPY')

    const init = fetchMock.mock.calls[0]?.[1] as { body?: string } | undefined
    const body = JSON.parse(init!.body!) as { fx_rates?: Record<string, number> }
    expect(body.fx_rates).toEqual({ EURUSD: 1.1422, GBPUSD: 1.3261 })
  })

  it('omits fx_rates when the snapshot has none (pre-US-30.2 persisted snapshots)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(driftPayload))
    vi.stubGlobal('fetch', fetchMock)

    await runDriftEngine(snapshot, 'SPY')

    const init = fetchMock.mock.calls[0]?.[1] as { body?: string } | undefined
    const body = JSON.parse(init!.body!) as { fx_rates?: Record<string, number> }
    expect(body.fx_rates).toBeUndefined()
  })
})

describe('runExposureEngine fx_rates plumbing (US-30.5a)', () => {
  it('posts fx_rates from snapshot.fxRates so weights sum in the base currency', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(createExposureEngineFixture()))
    vi.stubGlobal('fetch', fetchMock)

    await runExposureEngine({ ...snapshot, fxRates: { EURUSD: 1.1422, GBPUSD: 1.3261 } })

    const init = fetchMock.mock.calls[0]?.[1] as { body?: string } | undefined
    const body = JSON.parse(init!.body!) as { fx_rates?: Record<string, number> }
    expect(body.fx_rates).toEqual({ EURUSD: 1.1422, GBPUSD: 1.3261 })
  })

  it('omits fx_rates when the snapshot has none (pre-US-30.2 persisted snapshots)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(createExposureEngineFixture()))
    vi.stubGlobal('fetch', fetchMock)

    await runExposureEngine(snapshot)

    const init = fetchMock.mock.calls[0]?.[1] as { body?: string } | undefined
    const body = JSON.parse(init!.body!) as { fx_rates?: Record<string, number> }
    expect(body.fx_rates).toBeUndefined()
  })
})
