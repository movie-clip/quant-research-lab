import React from 'react'
import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { DashboardAnalysis, PerformanceSeriesPoint } from './types'
import { PerformanceBenchmarkCard } from './PerformanceBenchmarkCard'

// CR-1 (2026-08-26-performance-benchmark-chart-audit, FINDING 1/2): the card's
// `buildIndexedSeries` is not exported, so the only way to assert the exact
// portfolio/benchmark index values it computes — without reading SVG path
// geometry, which write-tests/SKILL.md's Recharts section explicitly warns
// off — is to intercept the `data` array Recharts' `LineChart` receives. This
// mirrors src/test/setup.tsx's ResponsiveContainer shim locally (that global
// mock does not carry into this file's own `vi.mock('recharts', ...)`).
vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts')
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => {
      if (!React.isValidElement(children)) {
        return <>{children}</>
      }
      return React.cloneElement(children as React.ReactElement<{ width?: number; height?: number }>, {
        width: 960,
        height: 320,
      })
    },
    LineChart: ({ data }: { data: Array<{ date: string; portfolio: number | null; benchmark: number | null }> }) => (
      <div data-testid="indexed-chart-data">{JSON.stringify(data)}</div>
    ),
  }
})

afterEach(cleanup)

/** Reads the exact indexed series `buildIndexedSeries` computed, via the
 *  `LineChart` mock above. Waits for `ChartShell`'s one-tick deferred mount. */
async function getChartData(): Promise<Array<{ date: string; portfolio: number | null; benchmark: number | null }>> {
  const el = await screen.findByTestId('indexed-chart-data')
  return JSON.parse(el.textContent ?? '[]')
}

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
 * CR-1 (2026-08-26-performance-benchmark-chart-audit, FINDING 1/2): the
 * portfolio line must be a TWR-indexed chain built from `portfolio_return_pct`
 * (`indexed_t = 100 * (1 + portfolio_return_pct_t / 100)`), never a raw
 * `portfolio_value` ratio — a deposit/withdrawal is not performance. This is
 * the regression guard 02-quant-audit.md's FINDING 1 says would have caught
 * the original CRITICAL bug (a $50k mid-period deposit on a flat market
 * previously drew the chart's final point to 150, i.e. a fabricated +50pp
 * "gain" from pure cash).
 */
describe('PerformanceBenchmarkCard portfolio line (buildIndexedSeries)', () => {
  it('tracks portfolio_return_pct-derived values across a mid-period deposit, not raw portfolio_value', async () => {
    const result = analysis()
    result.performance_series = [
      { date: '2026-01-08', portfolio_value: 100000, benchmark_price: 500, portfolio_return_pct: 0, benchmark_return_pct: null },
      // $50k deposit, flat market: true TWR stays 0% even though NAV jumps 50%.
      { date: '2026-03-01', portfolio_value: 150000, benchmark_price: 500, portfolio_return_pct: 0, benchmark_return_pct: null },
      { date: '2026-08-10', portfolio_value: 153000, benchmark_price: 550, portfolio_return_pct: 2.0, benchmark_return_pct: null },
    ] satisfies PerformanceSeriesPoint[]

    render(<PerformanceBenchmarkCard result={result} activeRange="All" />)
    const data = await getChartData()

    // Old (buggy) formula would give 150000 / 100000 * 100 = 150 here.
    expect(data[1].portfolio).toBe(100)
    expect(data[0].portfolio).toBe(100)
    expect(data[2].portfolio).toBe(102)
  })

  it('still indexes the benchmark leg from raw benchmark_price, unaffected by the portfolio-side fix', async () => {
    const result = analysis()
    result.performance_series = [
      { date: '2026-01-08', portfolio_value: 100000, benchmark_price: 500, portfolio_return_pct: 0, benchmark_return_pct: null },
      { date: '2026-03-01', portfolio_value: 150000, benchmark_price: 500, portfolio_return_pct: 0, benchmark_return_pct: null },
      { date: '2026-08-10', portfolio_value: 153000, benchmark_price: 550, portfolio_return_pct: 2.0, benchmark_return_pct: null },
    ] satisfies PerformanceSeriesPoint[]

    render(<PerformanceBenchmarkCard result={result} activeRange="All" />)
    const data = await getChartData()

    expect(data[0].benchmark).toBe(100)
    expect(data[1].benchmark).toBe(100)
    expect(data[2].benchmark).toBeCloseTo(110, 5) // 550 / 500 * 100, deposit has no effect
  })

  it('anchors the first indexed portfolio point at 100 from the always-zero first-point return, not from portfolio_value', async () => {
    // 03-frontend.md risks: portfolio_return_pct is always 0.0 on the engine's
    // very first daily_state regardless of that state's own portfolio_value —
    // a subtly different anchor rule than the old (now-deleted)
    // DashboardPanel.normalizePerformanceSeries, which anchored on the first
    // date with portfolio_value > 0 and left everything before it null.
    const result = analysis()
    result.performance_series = [
      { date: '2026-01-08', portfolio_value: 0, benchmark_price: 500, portfolio_return_pct: 0, benchmark_return_pct: null },
      { date: '2026-01-09', portfolio_value: 100000, benchmark_price: 501, portfolio_return_pct: 1.5, benchmark_return_pct: null },
    ] satisfies PerformanceSeriesPoint[]

    render(<PerformanceBenchmarkCard result={result} activeRange="All" />)
    const data = await getChartData()

    expect(data[0].portfolio).toBe(100)
    expect(data[1].portfolio).toBeCloseTo(101.5, 5)
  })
})

/**
 * CR-2 #1 (2026-08-26-performance-benchmark-chart-audit, FINDING 1): the
 * range selector must re-anchor the CHART, not just the summary strip below
 * it. Before this fix `buildIndexedSeries` always consumed the top-level,
 * never-sliced `performance_series` regardless of `activeRange`, so every
 * range rendered an identical chart. `window_start_date`
 * (`DashboardRangeMetrics.window_start_date`, backend dispatch 07) is the
 * per-range anchor that makes this test possible: two ranges with distinct
 * non-null `window_start_date` values must produce chart data that differs
 * both in which dates are plotted AND in the re-based trajectory, while both
 * still open at the base-100 reference point.
 */
describe('PerformanceBenchmarkCard range-switch chart re-anchoring (CR-2 #1)', () => {
  const multiRangeResult = {
    performance_series: [
      { date: '2026-01-08', portfolio_value: 100000, benchmark_price: 500, portfolio_return_pct: 0, benchmark_return_pct: null },
      { date: '2026-03-01', portfolio_value: 101000, benchmark_price: 505, portfolio_return_pct: 1.0, benchmark_return_pct: null },
      { date: '2026-06-01', portfolio_value: 103000, benchmark_price: 520, portfolio_return_pct: 3.0, benchmark_return_pct: null },
      { date: '2026-07-15', portfolio_value: 104000, benchmark_price: 530, portfolio_return_pct: 4.0, benchmark_return_pct: null },
      { date: '2026-08-10', portfolio_value: 105000, benchmark_price: 540, portfolio_return_pct: 5.0, benchmark_return_pct: null },
    ] satisfies PerformanceSeriesPoint[],
    range_metrics: {
      '1M': {
        summary: {
          start_value: 104000,
          end_value: 105000,
          net_contributions: 0,
          investment_gain: 1000,
          time_weighted_return_pct: 0.96,
          money_weighted_return_pct: 0.96,
          benchmark_return_pct: null,
          excess_return_pct: null,
        },
        max_drawdown_pct: null,
        monthly_returns: [],
        monthly_returns_reliable: true,
        portfolio_return_trust: 'degraded',
        window_start_date: '2026-07-15',
      },
      '3M': {
        summary: {
          start_value: 103000,
          end_value: 105000,
          net_contributions: 0,
          investment_gain: 2000,
          time_weighted_return_pct: 1.94,
          money_weighted_return_pct: 1.94,
          benchmark_return_pct: null,
          excess_return_pct: null,
        },
        max_drawdown_pct: null,
        monthly_returns: [],
        monthly_returns_reliable: true,
        portfolio_return_trust: 'degraded',
        window_start_date: '2026-06-01',
      },
    },
    daily_states: [],
    run_metadata: {
      return_basis_contract: { portfolio_path: 'replay_derived', benchmark_path: 'price_return_only' },
      reproducibility: { benchmark_symbol: 'SPY' },
      withheld_return_dates: [],
      withheld_return_impact_pct: null,
    },
  } as unknown as DashboardAnalysis

  it('plots a different date window per range, each re-based to 100 at its own window start', async () => {
    const { rerender } = render(<PerformanceBenchmarkCard result={multiRangeResult} activeRange="1M" />)
    const oneMonth = await getChartData()

    // 1M's window starts 2026-07-15 — two points, re-based to 100 there.
    expect(oneMonth.map((p) => p.date)).toEqual(['2026-07-15', '2026-08-10'])
    expect(oneMonth[0].portfolio).toBe(100)
    expect(oneMonth[1].portfolio).toBeCloseTo((100 * 1.05) / 1.04, 5)

    rerender(<PerformanceBenchmarkCard result={multiRangeResult} activeRange="3M" />)
    const threeMonth = await getChartData()

    // 3M's window starts 2026-06-01 — three points, re-based to 100 there.
    expect(threeMonth.map((p) => p.date)).toEqual(['2026-06-01', '2026-07-15', '2026-08-10'])
    expect(threeMonth[0].portfolio).toBe(100)
    expect(threeMonth[2].portfolio).toBeCloseTo((100 * 1.05) / 1.03, 5)

    // The chart genuinely changed: different plotted range AND a different
    // re-based trajectory for the same underlying date/return, not merely a
    // longer prefix of the same series. Both ranges share the 2026-07-15 date,
    // but its indexed value differs because each range re-bases to its own
    // window start (1.04 pivot vs 1.03 pivot).
    expect(oneMonth).not.toEqual(threeMonth)
    expect(oneMonth[0].portfolio).not.toBeCloseTo(threeMonth[1].portfolio ?? NaN, 5)
  })

  it('leaves the chart unsliced (full history, day-one anchor) when window_start_date is null, e.g. "All"', async () => {
    const allResult = {
      ...multiRangeResult,
      range_metrics: {
        ...multiRangeResult.range_metrics,
        All: {
          ...multiRangeResult.range_metrics!['1M'],
          window_start_date: null,
        },
      },
    } as unknown as DashboardAnalysis

    render(<PerformanceBenchmarkCard result={allResult} activeRange="All" />)
    const data = await getChartData()

    expect(data.map((p) => p.date)).toEqual(['2026-01-08', '2026-03-01', '2026-06-01', '2026-07-15', '2026-08-10'])
    expect(data[0].portfolio).toBe(100)
    expect(data[data.length - 1].portfolio).toBeCloseTo(105, 5)
  })
})

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
