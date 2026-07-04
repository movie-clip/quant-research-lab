import type { DashboardAnalysis } from './types'
import { EmptyState } from '../../app/primitives/EmptyState'

function formatMonthLabel(month: string): string {
  const [year, monthNum] = month.split('-')
  if (!year || !monthNum) return month
  const date = new Date(Number(year), Number(monthNum) - 1, 1)
  return date.toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
}

function formatReturnPct(value: number): string {
  const pct = Math.abs(value).toFixed(2)
  return value >= 0 ? `+${pct}%` : `−${pct}%`
}

type MonthlyReturnsGridProps = {
  result: DashboardAnalysis | null
  activeRange: string | null
}

export function MonthlyReturnsGrid({ result, activeRange }: MonthlyReturnsGridProps) {
  const rangeMetrics = result?.range_metrics ?? null
  const metrics = activeRange && rangeMetrics ? rangeMetrics[activeRange] : null

  if (!result || !metrics || !metrics.monthly_returns_reliable) {
    return (
      <section className="summary-card monthly-returns-grid" aria-label="Monthly Returns">
        <p className="panel-label">Monthly Returns</p>
        <EmptyState
          title="Monthly returns unavailable"
          detail={
            metrics && !metrics.monthly_returns_reliable
              ? 'The reconstructed monthly series is unstable for this range and is hidden rather than shown as plausible-looking data.'
              : 'Import a portfolio with usable history to see monthly returns.'
          }
        />
      </section>
    )
  }

  return (
    <section className="summary-card monthly-returns-grid" aria-label="Monthly Returns">
      <p className="panel-label">Monthly Returns</p>
      <div className="monthly-returns-cells">
        {metrics.monthly_returns.map((row) => (
          <div className="monthly-returns-cell" key={row.month}>
            <span className="monthly-returns-month">{formatMonthLabel(row.month)}</span>
            <span
              className={
                row.return_pct >= 0
                  ? 'monthly-returns-value benchmark-card-active-over'
                  : 'monthly-returns-value benchmark-card-active-under'
              }
            >
              {formatReturnPct(row.return_pct)}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}
