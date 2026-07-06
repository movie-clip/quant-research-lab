import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import { DriftBenchmarkPanel } from './DriftBenchmarkPanel'
import type { DriftResult } from './types'

afterEach(() => { cleanup() })

const baseResult: DriftResult = {
  windows: [
    {
      label: '1M',
      start_date: '2026-06-01',
      end_date: '2026-06-30',
      portfolio_return_pct: 1.5,
      benchmark_return_pct: 1.0,
      spread_pct: 0.5,
      trust: 'synthetic',
      note: 'Broker-ledger replay: compounded time-weighted return (cash-flow-neutral)',
    },
  ],
  benchmark_symbol: 'SPY',
  daily_series: [],
  availability: 'partial',
  fx_fallback_currencies: [],
}

describe('DriftBenchmarkPanel (US-27.8)', () => {
  it('renders the FX-fallback disclosure when non-base currencies were unconverted', () => {
    render(
      <DriftBenchmarkPanel
        result={{ ...baseResult, fx_fallback_currencies: ['EUR', 'GBP'] }}
        benchmarkSymbol="SPY"
        onBenchmarkChange={() => {}}
      />,
    )
    expect(screen.getByText(/FX conversion unavailable for EUR, GBP/)).toBeTruthy()
  })

  it('renders no FX note when every position converted (or is base currency)', () => {
    render(
      <DriftBenchmarkPanel
        result={baseResult}
        benchmarkSymbol="SPY"
        onBenchmarkChange={() => {}}
      />,
    )
    expect(screen.queryByText(/FX conversion unavailable/)).toBeNull()
  })
})
