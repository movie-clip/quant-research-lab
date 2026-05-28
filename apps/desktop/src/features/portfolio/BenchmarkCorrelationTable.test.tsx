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
})
