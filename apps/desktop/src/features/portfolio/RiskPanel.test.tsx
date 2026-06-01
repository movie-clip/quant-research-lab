import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RiskPanel } from './RiskPanel'
import type { PortfolioSnapshot } from './workspaceTypes'
import type { DistributionEngineResponse, DrawdownEngineResponse, StressEngineResponse } from './types'

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

/** Default distribution payload — same role as defaultDrawdownPayload. */
const defaultDistributionPayload: DistributionEngineResponse = {
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
  distributionResponder: () => Response = () => jsonResponse(defaultDistributionPayload),
) {
  return vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = String(input)
    if (url.includes('/engines/stress/run')) {
      return Promise.resolve(stressResponder())
    }
    if (url.includes('/engines/drawdown/run')) {
      return Promise.resolve(drawdownResponder())
    }
    if (url.includes('/engines/distribution/run')) {
      return Promise.resolve(distributionResponder())
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

  it('renders the page header in a two-tier hierarchy without a bulky h2.panel-label', () => {
    // US-13.4 density polish: the prior implementation rendered
    // <h2 className="panel-label">Risk Analytics</h2>, which made the
    // page header visually compete with the first card's title. The
    // polish replaces it with ExposurePanel's pattern: small
    // panel-label eyebrow + plain <h2> subtitle.
    vi.stubGlobal('fetch', vi.fn())
    const { container } = render(<RiskPanel snapshot={null} />)

    // The bulky pattern (h2 with panel-label class) MUST NOT appear.
    const bulkyHeader = container.querySelector('h2.panel-label')
    expect(bulkyHeader).toBeNull()

    // The two-tier pattern: an eyebrow element with class `panel-label`
    // AND a plain <h2> (without the panel-label class) both exist.
    const eyebrow = container.querySelector('.panel-label')
    expect(eyebrow).not.toBeNull()
    const h2 = container.querySelector('h2')
    expect(h2).not.toBeNull()
    expect(h2?.classList.contains('panel-label')).toBe(false)
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

  it('renders all three cards (Stress, Drawdown, VaR & Distribution) when snapshot present', async () => {
    const fetchMock = makeRoutedFetch()
    vi.stubGlobal('fetch', fetchMock)

    render(<RiskPanel snapshot={snapshot} />)

    // All three card titles must render
    await waitFor(() => expect(screen.getByText('Stress Scenarios')).toBeTruthy())
    await waitFor(() => expect(screen.getByText('Drawdown Analytics')).toBeTruthy())
    await waitFor(() => expect(screen.getByText('VaR & Distribution')).toBeTruthy())

    // All three engine routes were hit
    const urlsCalled = fetchMock.mock.calls.map((c) => String(c[0]))
    expect(urlsCalled.some((u) => u.includes('/engines/stress/run'))).toBe(true)
    expect(urlsCalled.some((u) => u.includes('/engines/drawdown/run'))).toBe(true)
    expect(urlsCalled.some((u) => u.includes('/engines/distribution/run'))).toBe(true)
  })
})
