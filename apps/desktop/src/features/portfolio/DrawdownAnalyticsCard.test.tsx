import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { DrawdownAnalyticsCard } from './DrawdownAnalyticsCard'
import type { DrawdownEngineResponse } from './types'
import type { PortfolioSnapshot } from './workspaceTypes'

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

/** Build a synthetic underwater series of ≥ 20 points so the card clears
 *  the MIN_OBSERVATIONS gate when the response is "synthetic". */
function syntheticSeries(): DrawdownEngineResponse['underwater_series'] {
  const result: DrawdownEngineResponse['underwater_series'] = []
  for (let i = 0; i < 25; i++) {
    const day = String(i + 1).padStart(2, '0')
    result.push({ date: `2025-01-${day}`, drawdown_pct: i === 0 ? 0 : -i * 0.5 })
  }
  return result
}

function syntheticPayload(overrides: Partial<DrawdownEngineResponse> = {}): DrawdownEngineResponse {
  return {
    window_trading_days: 1260,
    underwater_series: syntheticSeries(),
    current_drawdown_pct: -12.0,
    max_drawdown_pct: -12.0,
    episodes: [
      { peak_date: '2025-01-01', trough_date: '2025-01-25', recovery_date: null, magnitude_pct: -12.0, duration_days: 24, underwater_days: 24 },
    ],
    trust: 'synthetic',
    ...overrides,
  }
}

function unavailablePayload(): DrawdownEngineResponse {
  return {
    window_trading_days: 1260,
    underwater_series: [],
    current_drawdown_pct: null,
    max_drawdown_pct: null,
    episodes: [],
    trust: 'unavailable',
  }
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

describe('DrawdownAnalyticsCard', () => {
  it('renders the underwater chart wrapper with ariaLabel when fetch succeeds', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => {
      expect(screen.getByRole('img', { name: /underwater drawdown curve/i })).toBeTruthy()
    })
  })

  it('renders the synthetic trust badge when response trust is synthetic', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('Synthetic')).toBeTruthy())
  })

  it('renders the empty-state and no chart when trust is unavailable', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(unavailablePayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText(/drawdown analytics unavailable/i)).toBeTruthy())
    // No chart should be present
    expect(screen.queryByRole('img', { name: /underwater drawdown curve/i })).toBeNull()
    // Badge reflects unavailable
    expect(screen.getByText('Unavailable')).toBeTruthy()
  })

  it('renders the error state on fetch failure with the backend detail', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'engine boom' }, 500))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('Drawdown engine failed')).toBeTruthy())
    expect(screen.getByText(/engine boom/i)).toBeTruthy()
  })

  it('renders the loading state while the fetch is in flight', async () => {
    let resolveFn: ((value: Response) => void) | null = null
    const fetchMock = vi.fn().mockReturnValue(
      new Promise<Response>((resolve) => {
        resolveFn = resolve
      }),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    // While fetch hasn't resolved, the loading message is visible
    await waitFor(() => expect(screen.getByText(/computing drawdown analytics/i)).toBeTruthy())

    // Cleanup: resolve so the unmount doesn't leave dangling promises
    if (resolveFn) (resolveFn as (value: Response) => void)(jsonResponse(syntheticPayload()))
  })

  it('renders episode rows sorted by magnitude descending (deepest first)', async () => {
    const payload = syntheticPayload({
      episodes: [
        { peak_date: '2025-01-01', trough_date: '2025-01-05', recovery_date: '2025-01-10', magnitude_pct: -5.0, duration_days: 4, underwater_days: 9 },
        { peak_date: '2025-02-01', trough_date: '2025-02-12', recovery_date: '2025-03-01', magnitude_pct: -12.0, duration_days: 11, underwater_days: 28 },
        { peak_date: '2025-04-01', trough_date: '2025-04-15', recovery_date: '2025-04-30', magnitude_pct: -8.0, duration_days: 14, underwater_days: 29 },
      ],
    })
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('-12.00%')).toBeTruthy())

    // Read magnitude cells in DOM order; component renders episodes verbatim
    // from the response (backend sorted them deepest-first). Confirm the
    // order we passed: -12, -8, -5.
    const magnitudes = screen.getAllByText(/^-\d+\.\d{2}%$/).map((el) => el.textContent)
    expect(magnitudes).toEqual(['-12.00%', '-8.00%', '-5.00%'])
  })

  it('renders "Still underwater" for episodes with null recovery_date', async () => {
    const payload = syntheticPayload({
      episodes: [
        { peak_date: '2025-01-01', trough_date: '2025-01-15', recovery_date: null, magnitude_pct: -10.0, duration_days: 14, underwater_days: 25 },
      ],
    })
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText(/still underwater/i)).toBeTruthy())
  })

  it('renders the window selector with the four canonical labels', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    // Wait for the card to mount; the WindowSelector is rendered eagerly in the
    // CardShell actions slot even before the fetch resolves.
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '1260 trading day window' })).toBeTruthy(),
    )
    expect(screen.getByRole('button', { name: '756 trading day window' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '252 trading day window' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Max window' })).toBeTruthy()
  })

  it('refetches with window_trading_days=252 when the 252d button is clicked', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    // First call: default window (1260)
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const firstBody = JSON.parse((fetchMock.mock.calls[0]?.[1] as { body: string }).body) as {
      window_trading_days?: number
    }
    expect(firstBody.window_trading_days).toBe(1260)

    fireEvent.click(screen.getByRole('button', { name: '252 trading day window' }))

    // Second call: window=252
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const secondBody = JSON.parse((fetchMock.mock.calls[1]?.[1] as { body: string }).body) as {
      window_trading_days?: number
    }
    expect(secondBody.window_trading_days).toBe(252)
  })
})
