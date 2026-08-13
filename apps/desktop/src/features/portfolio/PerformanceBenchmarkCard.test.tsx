import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import type { DashboardAnalysis } from './types'
import { PerformanceBenchmarkCard } from './PerformanceBenchmarkCard'

afterEach(cleanup)

/**
 * US-34.2 (Epic 34 F-1): the Dashboard publishes a `replay_derived` return.
 *
 * The rung is only safe if it READS as weaker than a verified total return.
 * These tests are the check on that: the marker is text (not colour alone), it
 * is absent when the basis is verified, and an unavailable basis still shows no
 * number rather than a zero.
 */
function analysis(overrides: {
  portfolioBasis?: string
  trust?: 'verified' | 'degraded' | 'unavailable'
  twr?: number | null
  withheldDates?: string[]
  withheldImpact?: number | null
  reconciliationAdjustment?: number | null
} = {}): DashboardAnalysis {
  const {
    portfolioBasis = 'replay_derived',
    trust = 'degraded',
    twr = 2.43,
    withheldDates = [],
    withheldImpact = null,
    reconciliationAdjustment = null,
  } = overrides
  return {
    performance_series: [
      { date: '2026-01-08', portfolio_value: 52386.1, benchmark_price: 689.51, portfolio_return_pct: 0, benchmark_return_pct: null },
      { date: '2026-08-10', portfolio_value: 65168.77, benchmark_price: 773.03, portfolio_return_pct: twr, benchmark_return_pct: null },
    ],
    range_metrics: {
      All: {
        summary: {
          start_value: 52386.1,
          end_value: 65429.98,
          net_contributions: 9963,
          investment_gain: 3080.88,
          time_weighted_return_pct: twr,
          money_weighted_return_pct: 5.3,
          benchmark_return_pct: null,
          excess_return_pct: null,
        },
        max_drawdown_pct: null,
        monthly_returns: [],
        monthly_returns_reliable: true,
        portfolio_return_trust: trust,
      },
    },
    daily_states: [
      { date: '2026-08-11', reconciliation_adjustment: reconciliationAdjustment },
    ],
    run_metadata: {
      return_basis_contract: { portfolio_path: portfolioBasis, benchmark_path: 'price_return_only' },
      reproducibility: { benchmark_symbol: 'SPY' },
      withheld_return_dates: withheldDates,
      withheld_return_impact_pct: withheldImpact,
    },
  } as unknown as DashboardAnalysis
}

describe('PerformanceBenchmarkCard', () => {
  it('renders a replay-derived return with a visible basis marker', () => {
    render(<PerformanceBenchmarkCard result={analysis()} activeRange="All" />)

    const card = screen.getByRole('region', { name: /performance & benchmark/i })
    const text = card.textContent ?? ''
    expect(text).toContain('2.43%')
    // The marker is text, not colour alone (a11y baseline), and it appears
    // beside the metric — not only in the card-level basis line.
    expect(text.match(/Replay-derived/g)?.length).toBeGreaterThan(1)
  })

  it('does not mark a verified return', () => {
    render(
      <PerformanceBenchmarkCard
        result={analysis({ portfolioBasis: 'verified_total_return', trust: 'verified' })}
        activeRange="All"
      />,
    )

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).toContain('2.43%')
    expect(text).not.toContain('Replay-derived')
  })

  it('shows no number, and no zero, when the return is unavailable', () => {
    render(
      <PerformanceBenchmarkCard
        result={analysis({ portfolioBasis: 'unavailable', trust: 'unavailable', twr: null })}
        activeRange="All"
      />,
    )

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).toContain('n/a')
    expect(text).not.toContain('0.00%')
  })

  it('states what the withheld days cost the published return', () => {
    render(
      <PerformanceBenchmarkCard
        result={analysis({ withheldDates: ['2026-04-17', '2026-08-11'], withheldImpact: 1.8 })}
        activeRange="All"
      />,
    )

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).toMatch(/2 days are excluded/i)
    expect(text).toContain('1.80 percentage points')
    expect(text).toMatch(/understates/i)
  })

  it('says nothing about withheld days when none were withheld', () => {
    render(<PerformanceBenchmarkCard result={analysis()} activeRange="All" />)

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).not.toMatch(/excluded from this return/i)
  })

  it('explains why the gain and returns do not reconcile against portfolio value', () => {
    render(
      <PerformanceBenchmarkCard
        result={analysis({ reconciliationAdjustment: 1366.17 })}
        activeRange="All"
      />,
    )

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    // US-34.6: the value keeps the entry, the performance figures do not — a
    // researcher who spots that and is not told why trusts the card less.
    expect(text).toMatch(/accounting entry rather than a market move/i)
    expect(text).toMatch(/excluded from the returns and the gain/i)
    expect(text).toContain('1,366')
  })

  it('says nothing about a reconciliation when there was none', () => {
    render(<PerformanceBenchmarkCard result={analysis()} activeRange="All" />)

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).not.toMatch(/reconciliation/i)
  })
})
