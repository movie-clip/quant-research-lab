import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'
import type { DashboardAnalysis, DashboardRangeMetrics } from './types'
import { ChartShell } from '../../app/primitives/ChartShell'
import { defaultAxisTickStyle, defaultChartGrid, defaultMinTickGap, defaultTooltipContentStyle } from '../../app/primitives/chartDefaults'
import { EmptyState } from '../../app/primitives/EmptyState'

// ─── helpers ──────────────────────────────────────────────────────────────────

function formatDateLabel(value: string | number | null | undefined): string {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return String(value)
  return `${month}/${day}/${year.slice(2)}`
}

function formatPct(value: number | null | undefined): string {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatCurrency(value: number | null | undefined): string {
  return value == null ? 'n/a' : value.toLocaleString(undefined, { maximumFractionDigits: 0 })
}

/** Human label for the dashboard-history return-basis contract states.
 *  Distinct vocabulary from the Exposure-tab `TrustBadge` (synthetic/unavailable) —
 *  dashboard-history reports a broker-truth-adjacent verification ladder instead. */
function returnBasisLabel(basis: string | undefined): string {
  switch (basis) {
    case 'verified_total_return':
      return 'Verified'
    // US-34.2 (Epic 34 F-1): a real measurement on the replay's RECONSTRUCTED
    // inputs — one rung below verified, and it must read that way.
    case 'replay_derived':
      return 'Replay-derived'
    case 'price_return_only':
      return 'Price-return only'
    case 'unverified_adjusted_proxy':
      return 'Unverified proxy'
    default:
      return 'Unavailable'
  }
}

// ─── indexed-series construction (base 100, matches §Indexed Return Series) ────

type IndexedPoint = { date: string; portfolio: number | null; benchmark: number | null }

function buildIndexedSeries(perf: DashboardAnalysis['performance_series']): IndexedPoint[] {
  const anchor = perf.find((p) => p.portfolio_value > 0)
  const anchorPortfolio = anchor?.portfolio_value ?? null
  const anchorBenchmark = anchor?.benchmark_price ?? null

  return perf.map((p) => {
    const beforeAnchor = anchor != null && p.date < anchor.date
    return {
      date: p.date,
      portfolio:
        anchorPortfolio && anchorPortfolio > 0 && !beforeAnchor
          ? (p.portfolio_value / anchorPortfolio) * 100
          : null,
      benchmark:
        anchorBenchmark && anchorBenchmark > 0 && !beforeAnchor && p.benchmark_price
          ? (p.benchmark_price / anchorBenchmark) * 100
          : null,
    }
  })
}

// ─── component ────────────────────────────────────────────────────────────────

type PerformanceBenchmarkCardProps = {
  result: DashboardAnalysis | null
  /** Range key selected by the shared selector in `DashboardPanel` (e.g. '1M', 'YTD').
   *  Owned by the parent so this card and `MonthlyReturnsGrid` stay in sync (US-25.2). */
  activeRange: string | null
}

export function PerformanceBenchmarkCard({ result, activeRange }: PerformanceBenchmarkCardProps) {
  const rangeMetrics = result?.range_metrics ?? null

  if (!result || !rangeMetrics || !activeRange || !rangeMetrics[activeRange]) {
    return (
      <section className="summary-card performance-benchmark-card" aria-label="Performance & Benchmark">
        <p className="panel-label">Performance & Benchmark</p>
        <EmptyState
          title="Performance unavailable"
          detail="Import a portfolio with usable history to see performance vs benchmark."
        />
      </section>
    )
  }

  const metrics: DashboardRangeMetrics = rangeMetrics[activeRange]
  const chartData = buildIndexedSeries(result.performance_series)
  const hasChartData = chartData.some((p) => p.portfolio != null || p.benchmark != null)
  const benchmarkSymbol = result.run_metadata?.reproducibility?.benchmark_symbol ?? 'Benchmark'
  const portfolioBasis = result.run_metadata?.return_basis_contract?.portfolio_path
  const benchmarkBasis = result.run_metadata?.return_basis_contract?.benchmark_path
  const returnTrust = metrics.portfolio_return_trust ?? 'unavailable'
  const withheldDates = result.run_metadata?.withheld_return_dates ?? []
  const withheldImpact = result.run_metadata?.withheld_return_impact_pct ?? null
  // US-34.6: the terminal state's reconciliation is excluded from the gain and
  // the returns but included in the displayed portfolio value, so the three
  // numbers no longer reconcile by subtraction. Say so, or it reads as a bug.
  const reconciliationAdjustment =
    result.daily_states?.[result.daily_states.length - 1]?.reconciliation_adjustment ?? null

  return (
    <section className="summary-card performance-benchmark-card" aria-label="Performance & Benchmark">
      <div className="benchmark-card-header">
        <p className="panel-label">Performance & Benchmark</p>
      </div>

      <p className="helper" style={{ marginTop: 'var(--space-xs)' }}>
        Portfolio: {returnBasisLabel(portfolioBasis)} · {benchmarkSymbol}: {returnBasisLabel(benchmarkBasis)}
      </p>

      {hasChartData ? (
        <ChartShell ariaLabel="Indexed portfolio return vs benchmark" height={220}>
          <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid {...defaultChartGrid} />
            <XAxis dataKey="date" tickFormatter={formatDateLabel} tick={defaultAxisTickStyle} minTickGap={defaultMinTickGap} />
            <YAxis
              label={{ value: 'Indexed value (base = 100)', angle: -90, position: 'insideLeft', offset: 10, style: defaultAxisTickStyle }}
              tickFormatter={(v: number) => v.toFixed(0)}
              tick={defaultAxisTickStyle}
              width={48}
              domain={['auto', 'auto']}
            />
            <ReferenceLine y={100} stroke="var(--color-text-muted)" strokeDasharray="2 2" strokeOpacity={0.5} />
            <Tooltip
              formatter={(value: unknown, name: unknown) => [
                typeof value === 'number' ? value.toFixed(2) : 'n/a',
                typeof name === 'string' ? name : '',
              ]}
              labelFormatter={(label: unknown) =>
                formatDateLabel(typeof label === 'string' || typeof label === 'number' ? label : undefined)
              }
              contentStyle={defaultTooltipContentStyle}
            />
            <Line type="monotone" dataKey="portfolio" name="Portfolio" stroke="var(--color-line-portfolio)" dot={false} connectNulls={false} strokeWidth={2} isAnimationActive={false} />
            <Line type="monotone" dataKey="benchmark" name={benchmarkSymbol} stroke="var(--color-text-muted)" strokeDasharray="5 5" dot={false} connectNulls={false} strokeWidth={1.5} isAnimationActive={false} />
          </LineChart>
        </ChartShell>
      ) : (
        <EmptyState title="No performance history for this window." />
      )}

      <div className="benchmark-card-summary">
        <div className="benchmark-card-metric">
          <span className="stat-label">Portfolio Value</span>
          <span className="benchmark-card-value">{formatCurrency(metrics.summary.end_value)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">
            Time-Weighted Return
            {/* US-34.2: a degraded return must never read as a verified one.
                The marker is text, not colour alone (a11y baseline). */}
            {returnTrust === 'degraded' ? (
              <span className="helper"> · {returnBasisLabel(portfolioBasis)}</span>
            ) : null}
          </span>
          <span className="benchmark-card-value">{formatPct(metrics.summary.time_weighted_return_pct)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Money-Weighted Return</span>
          <span className="benchmark-card-value">{formatPct(metrics.summary.money_weighted_return_pct)}</span>
        </div>
        <div className="benchmark-card-metric">
          <span className="stat-label">Net Contributions</span>
          <span className="benchmark-card-value">{formatCurrency(metrics.summary.net_contributions)}</span>
        </div>
      </div>

      {reconciliationAdjustment != null && Math.abs(reconciliationAdjustment) > 1 ? (
        <p className="helper" style={{ marginTop: 'var(--space-md)' }}>
          Portfolio Value is the statement&apos;s own ending NAV, which includes a{' '}
          {formatCurrency(reconciliationAdjustment)} reconciliation on the final day. That is an
          accounting entry rather than a market move, so it is excluded from the returns and the
          gain above — which is why those figures do not reconcile against the value by
          subtraction.
        </p>
      ) : null}

      {/* US-34.2: publishing a return that omits days without saying what the
          omission is worth misleads more than publishing nothing. The engine
          measures the impact; this states it. */}
      {withheldImpact != null && withheldDates.length > 0 ? (
        <p className="helper" style={{ marginTop: 'var(--space-md)' }}>
          {withheldDates.length} {withheldDates.length === 1 ? 'day is' : 'days are'} excluded from
          this return because their portfolio value moved for a reason that was not a market move.
          Including them would change the full-period figure by about{' '}
          {withheldImpact > 0 ? '+' : ''}
          {withheldImpact.toFixed(2)} percentage points, so the number above understates by roughly
          that much. See Replay Disclosures for which days and why.
        </p>
      ) : null}
    </section>
  )
}
