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
    // US-14.2: with the cascade fallback, an unavailable response triggers
    // 4 sequential fetch calls (1260 → 756 → 252 → null). Use
    // mockImplementation so each call gets a FRESH Response (Web Response
    // bodies are single-use — mockResolvedValue would return the same
    // already-consumed Response on the second call, throwing on .json()).
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(unavailablePayload())))
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

    // First call: whatever the default window is (don't pin the implicit
    // default here — that's the dedicated cascade tests' job; this test is about
    // the click). Capture it dynamically so a future default change can't break
    // this test for an unrelated reason.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const firstBody = JSON.parse((fetchMock.mock.calls[0]?.[1] as { body: string }).body) as {
      window_trading_days?: number
    }
    const defaultWindow = firstBody.window_trading_days

    fireEvent.click(screen.getByRole('button', { name: '252 trading day window' }))

    // Second call: window=252 (and it actually changed from the default).
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2))
    const secondBody = JSON.parse((fetchMock.mock.calls[1]?.[1] as { body: string }).body) as {
      window_trading_days?: number
    }
    expect(secondBody.window_trading_days).toBe(252)
    expect(secondBody.window_trading_days).not.toBe(defaultWindow)
  })

  // ── US-14.2: smart-default window cascade fallback ──────────────────────────

  /** Extract the window_trading_days from a fetch mock call's body. Returns
   *  `undefined` when omitted (i.e. the Max window, where the adapter doesn't
   *  send the field). */
  function windowFromCall(call: unknown): number | undefined {
    const init = (call as [string, { body: string }])[1]
    const body = JSON.parse(init.body) as { window_trading_days?: number }
    return body.window_trading_days
  }

  it('auto_falls_back_from_1260_to_756_when_1260_returns_unavailable', async () => {
    // First call (1260) → unavailable. Second call (756) → synthetic with
    // an episode. Cascade should stop at the 756 call and render the data.
    const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const body = init?.body ? JSON.parse(init.body as string) as { window_trading_days?: number } : {}
      if (body.window_trading_days === 1260) {
        return Promise.resolve(jsonResponse(unavailablePayload()))
      }
      // 756 (or anything else) → synthetic with an episode
      return Promise.resolve(jsonResponse(syntheticPayload({
        episodes: [
          { peak_date: '2025-03-01', trough_date: '2025-04-01', recovery_date: null, magnitude_pct: -7.5, duration_days: 31, underwater_days: 60 },
        ],
      })))
    })
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    // Wait for the cascade to land on the synthetic payload from the 2nd call
    await waitFor(() => expect(screen.getByText(/still underwater/i)).toBeTruthy())

    // Exactly 2 fetch calls: cascade stopped at the first success.
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(windowFromCall(fetchMock.mock.calls[0])).toBe(1260)
    expect(windowFromCall(fetchMock.mock.calls[1])).toBe(756)
  })

  it('auto_falls_back_through_all_four_windows_until_exhausted', async () => {
    // Every window returns unavailable. Cascade walks 1260 → 756 → 252 →
    // null(Max). Final state: EmptyState.
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(unavailablePayload())))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText(/drawdown analytics unavailable/i)).toBeTruthy())

    // Exactly 4 fetch calls in cascade order: 1260, 756, 252, undefined (Max).
    expect(fetchMock).toHaveBeenCalledTimes(4)
    const windows = fetchMock.mock.calls.map((c) => windowFromCall(c))
    expect(windows).toEqual([1260, 756, 252, undefined])

    // Chart is not rendered on the unavailable path.
    expect(screen.queryByRole('img', { name: /underwater drawdown curve/i })).toBeNull()
  })

  it('user_window_click_disables_auto_fallback', async () => {
    // Every call returns unavailable. Initial render runs the cascade (4
    // calls). Then user clicks 252d — the click disables auto-fallback,
    // so the subsequent fetch is exactly ONE call (window=252) regardless
    // of its result.
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(unavailablePayload())))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    // Wait for the initial cascade (4 calls) to complete and land on
    // EmptyState.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(4))
    expect(screen.getByText(/drawdown analytics unavailable/i)).toBeTruthy()

    // User clicks 252d explicitly — sets hasUserOverriddenWindow=true.
    fireEvent.click(screen.getByRole('button', { name: '252 trading day window' }))

    // Exactly ONE more fetch call (the 252 call), no cascade after override.
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(5))
    expect(windowFromCall(fetchMock.mock.calls[4])).toBe(252)

    // No further fetches happen — give the event loop a tick to confirm.
    await new Promise((resolve) => setTimeout(resolve, 50))
    expect(fetchMock).toHaveBeenCalledTimes(5)
  })

  it('auto_fallback_does_not_run_when_first_window_succeeds', async () => {
    // Happy-path sanity: when window=1260 succeeds immediately, the cascade
    // does NOT over-fetch the shorter windows.
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(syntheticPayload())))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    // Wait for the synthetic data to render
    await waitFor(() => expect(screen.getByRole('img', { name: /underwater drawdown curve/i })).toBeTruthy())

    // Exactly 1 fetch call — no fallback attempted.
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(windowFromCall(fetchMock.mock.calls[0])).toBe(1260)
  })

  // ── US-15.2: Contributors drawer ────────────────────────────────────────────

  /** Build a synthetic payload with 2 episodes, each carrying decomposition
   *  fields populated per the schema landed in US-15.1. */
  function decomposedPayload(): DrawdownEngineResponse {
    const series = syntheticSeries()
    return {
      window_trading_days: 1260,
      underwater_series: series,
      current_drawdown_pct: -12.0,
      max_drawdown_pct: -12.0,
      episodes: [
        {
          peak_date: '2025-01-01',
          trough_date: '2025-01-15',
          recovery_date: null,
          magnitude_pct: -10.0,
          duration_days: 14,
          underwater_days: 25,
          top_contributors: [
            { symbol: 'AAPL', weight_at_peak_pct: 60.0, return_pct: -10.0, contribution_pct: -6.0, trust: 'synthetic' as const },
            { symbol: 'MSFT', weight_at_peak_pct: 40.0, return_pct: -10.0, contribution_pct: -4.0, trust: 'synthetic' as const },
          ],
          other_contribution_pct: null,
          decomposition_residual_pct: 0.0,
          decomposition_trust: 'synthetic' as const,
        },
        {
          peak_date: '2025-02-01',
          trough_date: '2025-02-20',
          recovery_date: '2025-03-15',
          magnitude_pct: -5.0,
          duration_days: 19,
          underwater_days: 42,
          top_contributors: [
            { symbol: 'NVDA', weight_at_peak_pct: 30.0, return_pct: -16.67, contribution_pct: -5.0, trust: 'synthetic' as const },
          ],
          other_contribution_pct: null,
          decomposition_residual_pct: 0.0,
          decomposition_trust: 'synthetic' as const,
        },
      ],
      trust: 'synthetic' as const,
    }
  }

  it('renders_expand_toggle_per_episode_row', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(decomposedPayload())))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('2025-01-01')).toBeTruthy())

    const toggles = screen.getAllByRole('button', { name: /expand contributors for/i })
    expect(toggles).toHaveLength(2)
    toggles.forEach((toggle) => {
      expect(toggle.getAttribute('aria-expanded')).toBe('false')
    })
  })

  it('clicking_expand_toggle_reveals_contributors_table_with_top_contributors_rendered', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(decomposedPayload())))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('2025-01-01')).toBeTruthy())

    // Before click, AAPL (episode 1's top contributor) is not in the DOM.
    expect(screen.queryByText('AAPL')).toBeNull()

    const firstToggle = screen.getAllByRole('button', { name: /expand contributors for/i })[0]!
    fireEvent.click(firstToggle)

    // After click, AAPL appears and toggle is expanded.
    expect(screen.getByText('AAPL')).toBeTruthy()
    // After expansion, the toggle's accessible name flips to "Collapse..."
    const collapseToggle = screen.getByRole('button', { name: /collapse contributors for 2025-01-01/i })
    expect(collapseToggle.getAttribute('aria-expanded')).toBe('true')
  })

  it('clicking_another_episode_toggle_swaps_focus_and_collapses_first', async () => {
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(decomposedPayload())))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)

    await waitFor(() => expect(screen.getByText('2025-01-01')).toBeTruthy())

    // Open episode 1 (the bigger -10% magnitude, sorted first).
    const ep1Toggle = screen.getByRole('button', { name: /expand contributors for 2025-01-01/i })
    fireEvent.click(ep1Toggle)
    expect(screen.getByText('AAPL')).toBeTruthy()

    // Click episode 2's toggle.
    const ep2Toggle = screen.getByRole('button', { name: /expand contributors for 2025-02-01/i })
    fireEvent.click(ep2Toggle)

    // Episode 2's NVDA is now visible; episode 1's AAPL is gone (single-open).
    expect(screen.getByText('NVDA')).toBeTruthy()
    expect(screen.queryByText('AAPL')).toBeNull()
  })

  it('renders_partial_trust_caption_with_residual_value_when_decomposition_trust_is_partial', async () => {
    const partial = decomposedPayload()
    partial.episodes[0]!.decomposition_trust = 'partial' as const
    partial.episodes[0]!.decomposition_residual_pct = -3.45
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(partial)))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)
    await waitFor(() => expect(screen.getByText('2025-01-01')).toBeTruthy())

    fireEvent.click(screen.getByRole('button', { name: /expand contributors for 2025-01-01/i }))
    // -3.45.toFixed(1) rounds to -3.5 in V8 (half-up away from zero).
    expect(screen.getByText(/partial: -3\.[45]% unexplained/i)).toBeTruthy()
  })

  it('expand_toggle_is_disabled_when_decomposition_trust_is_unavailable', async () => {
    const unavail = decomposedPayload()
    unavail.episodes[0]!.decomposition_trust = 'unavailable' as const
    unavail.episodes[0]!.top_contributors = null
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(unavail)))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)
    await waitFor(() => expect(screen.getByText('2025-01-01')).toBeTruthy())

    const disabledToggle = screen.getByRole('button', { name: /decomposition unavailable for 2025-01-01/i })
    expect((disabledToggle as HTMLButtonElement).disabled).toBe(true)
  })

  it('renders_other_and_residual_rows_when_applicable_and_skips_residual_when_near_zero', async () => {
    const payload = decomposedPayload()
    // Episode 1: has Other + material Residual → both rows should render
    payload.episodes[0]!.other_contribution_pct = -1.5
    payload.episodes[0]!.decomposition_residual_pct = -3.45
    payload.episodes[0]!.decomposition_trust = 'partial' as const
    // Episode 2: no Other (null) + negligible Residual (0.001) → neither row
    payload.episodes[1]!.other_contribution_pct = null
    payload.episodes[1]!.decomposition_residual_pct = 0.001
    const fetchMock = vi.fn().mockImplementation(() => Promise.resolve(jsonResponse(payload)))
    vi.stubGlobal('fetch', fetchMock)

    render(<DrawdownAnalyticsCard snapshot={snapshot} />)
    await waitFor(() => expect(screen.getByText('2025-01-01')).toBeTruthy())

    // Open episode 1: both rows visible.
    fireEvent.click(screen.getByRole('button', { name: /expand contributors for 2025-01-01/i }))
    expect(screen.getByText('Other')).toBeTruthy()
    expect(screen.getByText(/residual \(unexplained\)/i)).toBeTruthy()

    // Open episode 2 (single-open closes episode 1): neither row visible.
    fireEvent.click(screen.getByRole('button', { name: /expand contributors for 2025-02-01/i }))
    expect(screen.queryByText('Other')).toBeNull()
    expect(screen.queryByText(/residual \(unexplained\)/i)).toBeNull()
  })
})
