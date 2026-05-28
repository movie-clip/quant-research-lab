import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ImportedSnapshot, MultiBenchmarkCorrelationResult } from './types'
import { BenchmarkCorrelationTable } from './BenchmarkCorrelationTable'

// Mock the adapter so tests don't make real HTTP calls.
vi.mock('./portfolioAnalysisAdapter', () => ({
  runMultiBenchmarkCorrelation: vi.fn(),
}))

import { runMultiBenchmarkCorrelation } from './portfolioAnalysisAdapter'
const mockRun = vi.mocked(runMultiBenchmarkCorrelation)

afterEach(() => { cleanup() })

beforeEach(() => { mockRun.mockReset() })

const MINIMAL_SNAPSHOT: ImportedSnapshot = {
  statement: {
    importer: 'interactive_brokers',
    account_id: null,
    base_currency: 'USD',
    statement_period: '2025-01-01 - 2025-12-31',
    page_count: null,
  },
  statements: [],
  positions: [],
  instruments: [],
  cash_balances: [],
  ledger_entries: [],
}

function makeSyntheticRow(symbol: string, label: string, opts: Partial<{ correlation: number; beta: number; r_squared: number }> = {}) {
  return {
    symbol,
    label,
    correlation: opts.correlation ?? 0.85,
    beta: opts.beta ?? 1.1,
    r_squared: opts.r_squared ?? 0.72,
    trust: 'synthetic' as const,
  }
}

function makeFullResult(): MultiBenchmarkCorrelationResult {
  return {
    lookback_days: 252,
    benchmarks: [
      { symbol: 'SPY', label: 'S&P 500', correlation: 0.90, beta: 1.0, r_squared: 0.81, trust: 'synthetic' },
      { symbol: 'QQQ', label: 'Nasdaq-100', correlation: 0.82, beta: 1.3, r_squared: 0.67, trust: 'synthetic' },
      { symbol: 'GLD', label: 'Gold', correlation: -0.10, beta: -0.05, r_squared: 0.01, trust: 'synthetic' },
      { symbol: 'IEF', label: 'US 7-10yr Bonds', correlation: -0.35, beta: -0.20, r_squared: 0.12, trust: 'synthetic' },
      { symbol: 'VT', label: 'Global Equity', correlation: 0.88, beta: 0.95, r_squared: 0.77, trust: 'synthetic' },
    ],
  }
}

function makeAllUnavailableResult(): MultiBenchmarkCorrelationResult {
  return {
    lookback_days: 252,
    benchmarks: [
      { symbol: 'SPY', label: 'S&P 500', correlation: null, beta: null, r_squared: null, trust: 'unavailable' },
      { symbol: 'QQQ', label: 'Nasdaq-100', correlation: null, beta: null, r_squared: null, trust: 'unavailable' },
      { symbol: 'GLD', label: 'Gold', correlation: null, beta: null, r_squared: null, trust: 'unavailable' },
      { symbol: 'IEF', label: 'US 7-10yr Bonds', correlation: null, beta: null, r_squared: null, trust: 'unavailable' },
      { symbol: 'VT', label: 'Global Equity', correlation: null, beta: null, r_squared: null, trust: 'unavailable' },
    ],
  }
}

describe('BenchmarkCorrelationTable', () => {
  it('renders idle state when snapshot is null', () => {
    render(<BenchmarkCorrelationTable snapshot={null} />)
    expect(screen.getByText(/correlation unavailable/i)).toBeTruthy()
    expect(mockRun).not.toHaveBeenCalled()
  })

  it('renders five benchmark rows after successful fetch', async () => {
    mockRun.mockResolvedValue(makeFullResult())
    render(<BenchmarkCorrelationTable snapshot={MINIMAL_SNAPSHOT} />)
    await waitFor(() => {
      expect(screen.getByText('S&P 500')).toBeTruthy()
      expect(screen.getByText('Nasdaq-100')).toBeTruthy()
      expect(screen.getByText('Gold')).toBeTruthy()
      expect(screen.getByText('US 7-10yr Bonds')).toBeTruthy()
      expect(screen.getByText('Global Equity')).toBeTruthy()
    })
  })

  it('shows dashes for null values when trust is unavailable', async () => {
    mockRun.mockResolvedValue(makeAllUnavailableResult())
    render(<BenchmarkCorrelationTable snapshot={MINIMAL_SNAPSHOT} />)
    await waitFor(() => {
      const dashes = screen.getAllByText('—')
      // 5 rows × 3 null columns (ρ, β, R²) = 15 dashes
      expect(dashes.length).toBe(15)
    })
  })

  it('displays the lookback window in the header', async () => {
    mockRun.mockResolvedValue(makeFullResult())
    render(<BenchmarkCorrelationTable snapshot={MINIMAL_SNAPSHOT} />)
    await waitFor(() => {
      expect(screen.getByText(/252d lookback/i)).toBeTruthy()
    })
  })

  it('displays the Synthetic trust badge', () => {
    mockRun.mockResolvedValue(makeFullResult())
    render(<BenchmarkCorrelationTable snapshot={MINIMAL_SNAPSHOT} />)
    // Badge is in the header, visible immediately
    expect(screen.getByText('Synthetic')).toBeTruthy()
  })

  // ── Sort-order + trust-indicator contract tests (US-9.6) ─────────────────
  //
  // US-9.3 AC4 says the table renders rows in the order returned by the engine
  // and uses row opacity as a per-row trust indicator (no dedicated column).
  // These tests pin both contracts so a future client-side sort or column
  // refactor can't silently break them.

  it('renders rows in the order returned by the engine (preserves backend sort)', async () => {
    const intentionalOrder: MultiBenchmarkCorrelationResult = {
      lookback_days: 252,
      benchmarks: [
        makeSyntheticRow('GLD', 'Gold'),
        makeSyntheticRow('SPY', 'S&P 500'),
        makeSyntheticRow('VT', 'Global Equity'),
        makeSyntheticRow('QQQ', 'Nasdaq-100'),
        makeSyntheticRow('IEF', 'US 7-10yr Bonds'),
      ],
    }
    mockRun.mockResolvedValue(intentionalOrder)
    render(<BenchmarkCorrelationTable snapshot={MINIMAL_SNAPSHOT} />)
    await waitFor(() => {
      expect(screen.getByText('Gold')).toBeTruthy()
    })
    // Read body rows (slice off the thead row).
    const rows = screen.getAllByRole('row').slice(1)
    const renderedSymbols = rows.map((row) => {
      const firstCell = row.querySelector('td')
      const text = firstCell?.textContent ?? ''
      return text.match(/^(SPY|QQQ|GLD|IEF|VT)/)?.[1] ?? ''
    })
    expect(renderedSymbols).toEqual(['GLD', 'SPY', 'VT', 'QQQ', 'IEF'])
  })

  it('renders unavailable rows with dimmed opacity (per-row trust indicator)', async () => {
    const mixed: MultiBenchmarkCorrelationResult = {
      lookback_days: 252,
      benchmarks: [
        makeSyntheticRow('SPY', 'S&P 500'),
        makeSyntheticRow('QQQ', 'Nasdaq-100'),
        makeSyntheticRow('VT', 'Global Equity'),
        { symbol: 'GLD', label: 'Gold', correlation: null, beta: null, r_squared: null, trust: 'unavailable' },
        { symbol: 'IEF', label: 'US 7-10yr Bonds', correlation: null, beta: null, r_squared: null, trust: 'unavailable' },
      ],
    }
    mockRun.mockResolvedValue(mixed)
    render(<BenchmarkCorrelationTable snapshot={MINIMAL_SNAPSHOT} />)
    await waitFor(() => {
      expect(screen.getByText('Gold')).toBeTruthy()
    })
    // Unavailable rows: dimmed via opacity 0.55 (per-row trust indicator).
    // Literal value because JSDOM does not parse CSS var() in numeric props.
    const goldRow = screen.getByText('Gold').closest('tr') as HTMLElement
    const iefRow = screen.getByText('US 7-10yr Bonds').closest('tr') as HTMLElement
    expect(goldRow.style.opacity).toBe('0.55')
    expect(iefRow.style.opacity).toBe('0.55')
    // Synthetic rows: opacity 1 (full)
    const spyRow = screen.getByText('S&P 500').closest('tr') as HTMLElement
    expect(spyRow.style.opacity).toBe('1')
  })
})
