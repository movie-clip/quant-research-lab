import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DriftResult } from './types'
import type { PortfolioSnapshot } from './workspaceTypes'
import { DriftBenchmarkPanel } from './DriftBenchmarkPanel'

// Self-fetching panel (US-30.3): mock the adapter so tests make no real calls.
vi.mock('./portfolioAnalysisAdapter', () => ({
  runDriftEngine: vi.fn(),
}))

import { runDriftEngine } from './portfolioAnalysisAdapter'
const mockRun = vi.mocked(runDriftEngine)

afterEach(() => { cleanup() })
beforeEach(() => { mockRun.mockReset() })

const SNAPSHOT: PortfolioSnapshot = {
  snapshotVersion: 1,
  baseCurrency: 'USD',
  importedMeta: {
    importer: 'interactive_brokers',
    statementPeriod: '2026-01-01 - 2026-06-30',
    importedAt: '2026-07-08T00:00:00Z',
    sourceFileNames: ['IB2026.csv'],
  },
  positions: [{ symbol: 'AAPL', marketValue: 1000, quantity: 10, currency: 'USD', sector: null, sourceType: 'equity' }],
  cashBalances: [{ currency: 'USD', amount: 500 }],
  metadata: { benchmarkSymbol: 'SPY' },
}

function makeResult(overrides: Partial<DriftResult> = {}): DriftResult {
  return {
    windows: [
      {
        label: '1M',
        start_date: '2026-06-01',
        end_date: '2026-06-30',
        portfolio_return_pct: 1.5,
        benchmark_return_pct: 1.0,
        spread_pct: 0.5,
        trust: 'synthetic',
        note: 'Synthetic: current holdings × historical prices (market-value chain)',
      },
    ],
    benchmark_symbol: 'SPY',
    daily_series: [],
    availability: 'partial',
    fx_fallback_currencies: [],
    ...overrides,
  }
}

describe('DriftBenchmarkPanel self-fetch (US-30.3 / F-4)', () => {
  it('fetches on mount from the snapshot prop and renders windows — no result prop needed', async () => {
    mockRun.mockResolvedValue(makeResult())
    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)

    await waitFor(() => expect(mockRun).toHaveBeenCalledWith(SNAPSHOT, 'SPY'))
    await waitFor(() => expect(screen.getByText('Portfolio')).toBeTruthy())
  })

  it('shows the idle empty state and does not fetch when there is no snapshot', () => {
    render(<DriftBenchmarkPanel snapshot={null} />)
    expect(mockRun).not.toHaveBeenCalled()
    expect(screen.getByText('No drift data')).toBeTruthy()
  })

  it('re-fetches with the new symbol when the benchmark dropdown changes', async () => {
    mockRun.mockResolvedValue(makeResult())
    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)
    await waitFor(() => expect(mockRun).toHaveBeenCalledWith(SNAPSHOT, 'SPY'))

    fireEvent.change(screen.getByLabelText('Benchmark'), { target: { value: 'QQQ' } })
    await waitFor(() => expect(mockRun).toHaveBeenCalledWith(SNAPSHOT, 'QQQ'))
  })

  it('shows a loading state while the fetch is in flight', async () => {
    let resolve!: (r: DriftResult) => void
    mockRun.mockReturnValue(new Promise<DriftResult>((r) => { resolve = r }))
    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)

    expect(screen.getByText(/Computing drift vs benchmark/)).toBeTruthy()
    resolve(makeResult())
    await waitFor(() => expect(screen.getByText('Portfolio')).toBeTruthy())
  })

  it('surfaces the backend error detail (never a silent "No drift data")', async () => {
    mockRun.mockRejectedValue(new Error('benchmark history unavailable'))
    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)

    await waitFor(() => expect(screen.getByText('Drift engine failed')).toBeTruthy())
    expect(screen.getByText(/benchmark history unavailable/)).toBeTruthy()
    expect(screen.queryByText('No drift data')).toBeNull()
  })

  it('discards a stale result when a newer selection resolves first', async () => {
    // First fetch (SPY) is slow; second (QQQ) resolves immediately. The slow
    // one must not overwrite the newer selection's data.
    let resolveSlow!: (r: DriftResult) => void
    mockRun
      .mockReturnValueOnce(new Promise<DriftResult>((r) => { resolveSlow = r }))
      .mockResolvedValueOnce(makeResult({ windows: [{ label: '1M', start_date: '2026-06-01', end_date: '2026-06-30', portfolio_return_pct: 9.9, benchmark_return_pct: 1.0, spread_pct: 8.9, trust: 'synthetic', note: null }] }))

    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)
    fireEvent.change(screen.getByLabelText('Benchmark'), { target: { value: 'QQQ' } })

    await waitFor(() => expect(screen.getByText('+9.90%')).toBeTruthy())
    // The superseded SPY fetch resolves late — it must be ignored.
    resolveSlow(makeResult({ windows: [{ label: '1M', start_date: '2026-06-01', end_date: '2026-06-30', portfolio_return_pct: 1.5, benchmark_return_pct: 1.0, spread_pct: 0.5, trust: 'synthetic', note: null }] }))
    await new Promise((r) => setTimeout(r, 0))
    expect(screen.getByText('+9.90%')).toBeTruthy()
    expect(screen.queryByText('+1.50%')).toBeNull()
  })
})

describe('DriftBenchmarkPanel disclosure notes (US-27.8 / 30.1 / 30.2)', () => {
  it('renders the FX-fallback disclosure when non-base currencies were unconverted', async () => {
    mockRun.mockResolvedValue(makeResult({ fx_fallback_currencies: ['EUR', 'GBP'] }))
    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)
    await waitFor(() => expect(screen.getByText(/FX conversion unavailable for EUR, GBP/)).toBeTruthy())
  })

  it('renders no FX note when every position converted (or is base currency)', async () => {
    mockRun.mockResolvedValue(makeResult())
    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)
    await waitFor(() => expect(screen.getByText('Portfolio')).toBeTruthy())
    expect(screen.queryByText(/FX conversion unavailable/)).toBeNull()
  })

  it('renders the statement-anchored and static-rate notes when non-empty (US-30.2)', async () => {
    mockRun.mockResolvedValue(makeResult({ statement_anchored_symbols: ['LQQ'], fx_static_rate_currencies: ['EUR', 'GBP'] }))
    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)
    await waitFor(() => expect(screen.getByText(/No market price history for LQQ/)).toBeTruthy())
    expect(screen.getByText(/EUR, GBP converted at the statement/)).toBeTruthy()
  })

  it('renders neither US-30.2 note when the disclosure lists are empty', async () => {
    mockRun.mockResolvedValue(makeResult({ statement_anchored_symbols: [], fx_static_rate_currencies: [] }))
    render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)
    await waitFor(() => expect(screen.getByText('Portfolio')).toBeTruthy())
    expect(screen.queryByText(/No market price history/)).toBeNull()
    expect(screen.queryByText(/converted at the statement/)).toBeNull()
  })

  it('repeats the engine basis note in the trust tooltip instead of a hardcoded claim (US-30.1)', async () => {
    mockRun.mockResolvedValue(makeResult())
    const { container } = render(<DriftBenchmarkPanel snapshot={SNAPSHOT} />)
    await waitFor(() => expect(screen.getByText('Portfolio')).toBeTruthy())
    const badge = container.querySelector('[title]')
    expect(badge?.getAttribute('title')).toContain('Synthetic: current holdings')
    expect(badge?.getAttribute('title')).not.toContain('Broker-ledger replay')
  })
})
