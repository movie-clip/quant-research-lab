import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { RiskPanel } from './RiskPanel'
import type { PortfolioSnapshot } from './workspaceTypes'
import type { StressEngineResponse } from './types'

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

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
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
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(stressPayload))
    vi.stubGlobal('fetch', fetchMock)

    render(<RiskPanel snapshot={snapshot} />)

    // Wait for the async fetch + render
    await waitFor(() => {
      expect(screen.getByText('Broad Market Selloff')).toBeTruthy()
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/engines/stress/run',
      expect.objectContaining({ method: 'POST' }),
    )
    // Trust badge surfaced via card
    expect(screen.getByText('Synthetic')).toBeTruthy()
  })

  it('surfaces fetch errors via the card ErrorState', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'engine down' }, 500))
    vi.stubGlobal('fetch', fetchMock)

    render(<RiskPanel snapshot={snapshot} />)

    await waitFor(() => {
      expect(screen.getByText('Stress engine failed')).toBeTruthy()
    })
    // Error detail from backend is preserved
    expect(screen.getByText(/engine down/i)).toBeTruthy()
  })
})
