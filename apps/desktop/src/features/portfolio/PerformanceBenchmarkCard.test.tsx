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
  benchmarkBasis?: string
  benchmarkReturn?: number | null
  excessReturn?: number | null
} = {}): DashboardAnalysis {
  const {
    portfolioBasis = 'replay_derived',
    trust = 'degraded',
    twr = 2.43,
    withheldDates = [],
    withheldImpact = null,
    reconciliationAdjustment = null,
    benchmarkBasis = 'price_return_only',
    benchmarkReturn = 11.75,
    excessReturn = -11.21,
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
          benchmark_return_pct: benchmarkReturn,
          excess_return_pct: excessReturn,
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
      return_basis_contract: { portfolio_path: portfolioBasis, benchmark_path: benchmarkBasis },
      reproducibility: { benchmark_symbol: 'SPY' },
      withheld_return_dates: withheldDates,
      withheld_return_impact_pct: withheldImpact,
    },
  } as unknown as DashboardAnalysis
}

/**
 * US-34.5 (Epic 34 F-10): the benchmark return and excess are published.
 *
 * They were null on every run before this story, so the card never rendered
 * them. Publishing a PRICE return where a reader expects a total return is the
 * risk this surface has to manage, so the basis marker and the direction of the
 * bias are both asserted here.
 */
describe('PerformanceBenchmarkCard benchmark leg', () => {
  it('renders the benchmark return and the excess', () => {
    render(<PerformanceBenchmarkCard result={analysis()} activeRange="All" />)

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).toContain('SPY Return')
    expect(text).toContain('11.75%')
    expect(text).toContain('Excess Return')
    expect(text).toContain('-11.21%')
  })

  it('marks a price-basis benchmark and says which way the excess is biased', () => {
    render(<PerformanceBenchmarkCard result={analysis()} activeRange="All" />)

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    // The marker is text, not colour alone (a11y baseline).
    expect(text.match(/Price-return only/g)?.length).toBeGreaterThan(1)
    // The caveat must name the direction, not merely hedge.
    expect(text).toMatch(/understates the benchmark/i)
    expect(text).toMatch(/flattered/i)
  })

  it('does not caveat a verified benchmark basis', () => {
    render(
      <PerformanceBenchmarkCard
        result={analysis({ benchmarkBasis: 'verified_total_return' })}
        activeRange="All"
      />,
    )

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).toContain('11.75%')
    expect(text).not.toMatch(/understates the benchmark/i)
  })

  // US-34.9 (Epic 34 F-9): once the benchmark is sourced from the
  // dividend-adjusted endpoint the basis becomes `verified_total_return`, and
  // the price-return caveat stops being true. It must disappear with it —
  // a stale caveat is its own kind of false claim.
  it('drops the price-return caveat on a verified total-return basis', () => {
    render(
      <PerformanceBenchmarkCard
        result={analysis({ benchmarkBasis: 'verified_total_return' })}
        activeRange="All"
      />,
    )

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    // The figures still render...
    expect(text).toContain('11.75%')
    expect(text).toContain('-11.21%')
    // ...without the price-basis marker or the dividend caveat.
    expect(text).not.toMatch(/Price-return only/)
    expect(text).not.toMatch(/understates the benchmark/i)
    expect(text).not.toMatch(/excludes the benchmark/i)
  })

  it('keeps the caveat while the basis is still a price return', () => {
    render(<PerformanceBenchmarkCard result={analysis()} activeRange="All" />)

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).toMatch(/Price-return only/)
    expect(text).toMatch(/understates the benchmark/i)
  })

  it('shows no number and no caveat when the benchmark leg is withheld', () => {
    render(
      <PerformanceBenchmarkCard
        result={analysis({
          benchmarkBasis: 'unverified_adjusted_proxy',
          benchmarkReturn: null,
          excessReturn: null,
        })}
        activeRange="All"
      />,
    )

    const text = screen.getByRole('region', { name: /performance & benchmark/i }).textContent ?? ''
    expect(text).toContain('SPY Return')
    // Never a fabricated 0% standing in for an absent measurement.
    expect(text).not.toContain('0.00%')
    expect(text).not.toMatch(/understates the benchmark/i)
  })
})

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
