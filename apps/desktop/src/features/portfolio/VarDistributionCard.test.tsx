import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { VarDistributionCard } from './VarDistributionCard'
import type { DistributionEngineResponse } from './types'
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

function syntheticPayload(overrides: Partial<DistributionEngineResponse> = {}): DistributionEngineResponse {
  return {
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
    ...overrides,
  }
}

function unavailablePayload(): DistributionEngineResponse {
  return {
    window_trading_days: 252,
    return_count: 0,
    var_95: null,
    var_99: null,
    cvar_95: null,
    percentile_5: null,
    percentile_10: null,
    percentile_50: null,
    percentile_90: null,
    percentile_95: null,
    mean_pct: null,
    std_pct: null,
    skewness: null,
    kurtosis_excess: null,
    histogram_bins: [],
    trust: 'unavailable',
  }
}

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}


describe('VarDistributionCard', () => {
  it('renders the histogram chart with ariaLabel when fetch succeeds', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    await waitFor(() => {
      expect(screen.getByRole('img', { name: /daily return distribution histogram/i })).toBeTruthy()
    })
  })

  it('renders the Synthetic trust badge when response trust is synthetic', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('Synthetic')).toBeTruthy())
  })

  it('renders the empty state and no chart when trust is unavailable', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(unavailablePayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText(/distribution analytics unavailable/i)).toBeTruthy())
    expect(screen.queryByRole('img', { name: /daily return distribution histogram/i })).toBeNull()
    expect(screen.getByText('Unavailable')).toBeTruthy()
  })

  it('renders the error state on fetch failure with the backend detail', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ detail: 'engine boom' }, 500))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('Distribution engine failed')).toBeTruthy())
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

    render(<VarDistributionCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText(/computing return distribution/i)).toBeTruthy())

    if (resolveFn) (resolveFn as (value: Response) => void)(jsonResponse(syntheticPayload()))
  })

  it('renders percentile / tail / shape values formatted as percentages', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('2.34%')).toBeTruthy())
    expect(screen.getByText('3.12%')).toBeTruthy()  // CVaR 95
    expect(screen.getByText('4.51%')).toBeTruthy()  // VaR 99
    expect(screen.getByText('0.08%')).toBeTruthy()  // median
    expect(screen.getByText('-1.84%')).toBeTruthy() // p5
    // Skew / kurtosis: no % suffix
    expect(screen.getByText('-0.31')).toBeTruthy()
    expect(screen.getByText('2.84')).toBeTruthy()
  })

  it('renders an em-dash for null cells (e.g. CVaR null path)', async () => {
    const payload = syntheticPayload({ cvar_95: null })
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(payload))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    // CVaR cell now renders the dash. (Multiple dashes may appear in
    // other contexts; we assert at least one is in the DOM.)
    await waitFor(() => expect(screen.getAllByText('—').length).toBeGreaterThan(0))
    // The non-null VaR 95 should still render normally
    expect(screen.getByText('2.34%')).toBeTruthy()
  })

  it('renders the window selector with three options (60d, 252d, 504d)', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    await waitFor(() =>
      expect(screen.getByRole('button', { name: '60 trading day window' })).toBeTruthy(),
    )
    expect(screen.getByRole('button', { name: '252 trading day window' })).toBeTruthy()
    expect(screen.getByRole('button', { name: '504 trading day window' })).toBeTruthy()
  })

  it('section headers render compactly without uppercase or wide letter-spacing', async () => {
    // US-13.4 density polish: the prior SectionHeader used
    // textTransform: 'uppercase' + letterSpacing: '0.05em' + a wide top
    // margin, which made the three sections (Percentiles, Tail Risk,
    // Distribution shape) feel like loud chapter breaks. The polish
    // removes both anti-patterns so the table reads as one quiet group.
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    // Wait for the data-driven body to mount so section headers exist
    await waitFor(() => expect(screen.getByText('Percentiles')).toBeTruthy())

    for (const title of ['Percentiles', 'Tail Risk', 'Distribution shape']) {
      const el = screen.getByText(title) as HTMLElement
      // Inline-style invariants from the polish
      expect(el.style.textTransform).not.toBe('uppercase')
      expect(el.style.letterSpacing).not.toBe('0.05em')
    }
  })

  it('defaults to window_trading_days=252', async () => {
    // The one test that intentionally pins the default window. Other tests must
    // not re-assert it implicitly (US-21.5 assertion convention).
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const firstBody = JSON.parse((fetchMock.mock.calls[0]?.[1] as { body: string }).body) as {
      window_trading_days: number
    }
    expect(firstBody.window_trading_days).toBe(252)
  })

  it('refetches with window_trading_days=504 when the 504d button is clicked', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(syntheticPayload()))
    vi.stubGlobal('fetch', fetchMock)

    render(<VarDistributionCard snapshot={snapshot} />)

    // Don't pin the implicit default here (the dedicated test above does that);
    // capture it dynamically so a default change can't break this click test.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const firstBody = JSON.parse((fetchMock.mock.calls[0]?.[1] as { body: string }).body) as {
      window_trading_days: number
    }
    const defaultWindow = firstBody.window_trading_days

    fireEvent.click(screen.getByRole('button', { name: '504 trading day window' }))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const secondBody = JSON.parse((fetchMock.mock.calls[1]?.[1] as { body: string }).body) as {
      window_trading_days: number
    }
    expect(secondBody.window_trading_days).toBe(504)
    expect(secondBody.window_trading_days).not.toBe(defaultWindow)
  })
})
