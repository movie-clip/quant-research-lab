import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RiskPanel } from './RiskPanel'
import type { PortfolioSnapshot } from './workspaceTypes'
import type { DrawdownEngineResponse, StressEngineResponse } from './types'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
})

const snapshot: PortfolioSnapshot = {
  snapshotVersion: 1,
  baseCurrency: 'USD',
  importedMeta: {
    importer: 'interactive_brokers',
    statementPeriod: '2025-01-01 - 2025-12-31',
    importedAt: '2026-04-10T00:00:00Z',
    sourceFileNames: ['IB2025.pdf'],
  },
  positions: [
    { symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' },
  ],
  cashBalances: [{ currency: 'USD', amount: 1000 }],
  metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
}

const stressPayload: StressEngineResponse = {
  scenarios: [
    { name: 'Broad Market Selloff', estimated_return_pct: -8.5, description: 'risk-off', status: 'ok' },
    { name: 'Rates Down Risk-On', estimated_return_pct: 2.1, description: 'duration', status: 'ok' },
    { name: 'Inflation Reacceleration', estimated_return_pct: -3.2, description: 'sticky', status: 'ok' },
  ],
  trust: 'synthetic',
}

/** Default drawdown payload used by URL-routed mocks so DrawdownAnalyticsCard
 *  (which mounts as a sibling of StressScenariosCard) has a well-shaped
 *  response. Tests that care about stress can ignore this and still pass. */
const defaultDrawdownPayload: DrawdownEngineResponse = {
  window_trading_days: 1260,
  underwater_series: Array.from({ length: 25 }, (_, i) => ({
    date: `2025-01-${String(i + 1).padStart(2, '0')}`,
    drawdown_pct: i === 0 ? 0 : -i * 0.4,
  })),
  current_drawdown_pct: -9.6,
  max_drawdown_pct: -9.6,
  episodes: [],
  trust: 'synthetic',
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/** URL-routed fetch mock: stress payload for /engines/stress/run, drawdown
 *  payload for /engines/drawdown/run. The two cards mount in parallel and
 *  fetch independently — order-based mocks (mockResolvedValueOnce) are
 *  fragile here. */
function makeRoutedFetch(
  stressResponder: () => Response = () => jsonResponse(stressPayload),
  drawdownResponder: () => Response = () => jsonResponse(defaultDrawdownPayload),
) {
  return vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/engines/stress/run')) {
      return Promise.resolve(stressResponder())
    }
    if (url.includes('/engines/drawdown/run')) {
      return Promise.resolve(drawdownResponder())
    }
    throw new Error(`Unexpected fetch URL: ${url}`)
  })
}

describe('RiskPanel', () => {
  it('renders header with helper text and does NOT fetch when snapshot is null', () => {
    const fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)

    render(<RiskPanel snapshot={null} />)

    expect(screen.getByText(/import a portfolio/i)).toBeTruthy()
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('fetches the stress engine and renders the card when snapshot is provided', async () => {
    const fetchMock = makeRoutedFetch()
    vi.stubGlobal('fetch', fetchMock)

    render(<RiskPanel snapshot={snapshot} />)

    // Wait for the async fetch + render
    await waitFor(() => {
      expect(screen.getByText('Broad Market Selloff')).toBeTruthy()
    })

    // Stress route was hit at least once
    const urlsCalled = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(urlsCalled.some((u) => u.includes('/api/engines/stress/run'))).toBe(true)
    // Trust badge surfaced via card (both cards now show Synthetic, so query
    // all and assert at least one)
    expect(screen.getAllByText('Synthetic').length).toBeGreaterThan(0)
  })

  it('surfaces fetch errors via the card ErrorState', async () => {
    const fetchMock = makeRoutedFetch(
      () => jsonResponse({ detail: 'engine down' }, 500),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<RiskPanel snapshot={snapshot} />)

    await waitFor(() => {
      expect(screen.getByText('Stress engine failed')).toBeTruthy()
    })
    // Error detail from backend is preserved
    expect(screen.getByText(/engine down/i)).toBeTruthy()
  })

  it('renders both StressScenariosCard and DrawdownAnalyticsCard when snapshot present', async () => {
    const drawdownPayloadWithEpisode: DrawdownEngineResponse = {
      ...defaultDrawdownPayload,
      episodes: [
        { peak_date: '2025-01-01', trough_date: '2025-01-25', recovery_date: null, magnitude_pct: -9.6, duration_days: 24, underwater_days: 24 },
      ],
    }
    const fetchMock = makeRoutedFetch(
      () => jsonResponse(stressPayload),
      () => jsonResponse(drawdownPayloadWithEpisode),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<RiskPanel snapshot={snapshot} />)

    // Both cards' content eventually visible
    await waitFor(() => expect(screen.getByText('Stress Scenarios')).toBeTruthy())
    await waitFor(() => expect(screen.getByText('Drawdown Analytics')).toBeTruthy())
    // At least one scenario from stress payload + the peak_date of the drawdown
    // episode confirm both data sources rendered
    expect(screen.getByText('Broad Market Selloff')).toBeTruthy()
    expect(screen.getByText('2025-01-01')).toBeTruthy()

    // Both routes hit
    const urlsCalled = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(urlsCalled.some((u) => u.includes('/engines/stress/run'))).toBe(true)
    expect(urlsCalled.some((u) => u.includes('/engines/drawdown/run'))).toBe(true)
  })
})
