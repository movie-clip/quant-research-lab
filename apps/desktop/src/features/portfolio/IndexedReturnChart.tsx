import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'
import type { DriftDailyPoint, DriftWindow } from './types'
import { ChartShell } from '../../app/primitives/ChartShell'
import { defaultAxisTickStyle, defaultChartGrid, defaultMinTickGap, defaultTooltipContentStyle } from '../../app/primitives/chartDefaults'
import { EmptyState } from '../../app/primitives/EmptyState'
import { WindowSelector } from '../../app/primitives/WindowSelector'

function formatDateLabel(value: string | number | null | undefined): string {
  if (typeof value !== 'string') return ''
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return String(value)
  return `${month}/${day}/${year.slice(2)}`
}

function formatIndexValue(value: number | null | undefined): string {
  return value == null ? 'n/a' : value.toFixed(2)
}

type WindowOption = { label: string; startDate: string | null }

function buildWindowOptions(windows: DriftWindow[]): WindowOption[] {
  return windows.map((w) => ({ label: w.label, startDate: w.start_date }))
}

function sliceAndRebase(
  series: DriftDailyPoint[],
  startDate: string | null,
): Array<{ date: string; portfolio: number | null; benchmark: number | null }> {
  const sliced = startDate ? series.filter((p) => p.date >= startDate) : series

  // Rebase to 100 at first non-null value for each series, independently.
  // This matches §Indexed Return Series in financial-methodology.md:
  //   indexed_t = (value_t / value_0) * 100
  // The backend already provides indexed values; slicing to a sub-window
  // requires a second rebasing pass to set the sub-window start to 100.
  const firstPortfolio = sliced.find((p) => p.portfolio_indexed != null)?.portfolio_indexed ?? null
  const firstBenchmark = sliced.find((p) => p.benchmark_indexed != null)?.benchmark_indexed ?? null

  return sliced.map((p) => ({
    date: p.date,
    portfolio:
      firstPortfolio != null && p.portfolio_indexed != null
        ? (p.portfolio_indexed / firstPortfolio) * 100
        : null,
    benchmark:
      firstBenchmark != null && p.benchmark_indexed != null
        ? (p.benchmark_indexed / firstBenchmark) * 100
        : null,
  }))
}

type IndexedReturnChartProps = {
  series: DriftDailyPoint[]
  windows: DriftWindow[]
  benchmarkSymbol: string
}

/** Filter the series for a given window start and check it has at least one
 *  non-null portfolio data point. Used to pick the default selected window
 *  (avoid defaulting to a window with zero data — e.g. "Since Import" when
 *  the user imported today). */
function windowHasData(series: DriftDailyPoint[], startDate: string | null): boolean {
  const sliced = startDate ? series.filter((p) => p.date >= startDate) : series
  return sliced.some((p) => p.portfolio_indexed != null)
}

export function IndexedReturnChart({ series, windows, benchmarkSymbol }: IndexedReturnChartProps) {
  const windowOptions = buildWindowOptions(windows)
  // Pick the LONGEST window (last in the list = "Since Import" usually) whose
  // filter actually returns data. If "Since Import" is empty because the user
  // imported recently and daily_series doesn't yet cover that range, fall back
  // to the next shorter window (12M, 6M, ...). Prevents the "blank chart on
  // first open" experience.
  const defaultWindowLabel =
    [...windowOptions].reverse().find((opt) => windowHasData(series, opt.startDate))?.label
    ?? windowOptions[windowOptions.length - 1]?.label
    ?? ''
  const [selectedWindowLabel, setSelectedWindowLabel] = useState<string>(defaultWindowLabel)

  const selectedWindow = windowOptions.find((w) => w.label === selectedWindowLabel) ?? windowOptions[windowOptions.length - 1]
  const chartData = sliceAndRebase(series, selectedWindow?.startDate ?? null)
  const hasData = chartData.some((p) => p.portfolio != null || p.benchmark != null)

  return (
    <div className="drift-chart-shell">
      {windowOptions.length > 1 && (
        <WindowSelector
          options={windowOptions.map((o) => o.label)}
          value={selectedWindowLabel}
          onChange={(label) => { setSelectedWindowLabel(label) }}
        />
      )}
      {!hasData ? (
        <EmptyState
          title={`No data for ${selectedWindowLabel}.`}
          detail={
            selectedWindowLabel === 'Since Import'
              ? 'Your portfolio was imported too recently to plot post-import returns. Try a longer window (12M, 6M, ...) for visible history.'
              : 'Insufficient history for this window. Try a longer or shorter range.'
          }
        />
      ) : (
        <ChartShell ariaLabel="Indexed return time series for portfolio and benchmark" height={220}>
          <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid {...defaultChartGrid} />
            <XAxis
              dataKey="date"
              tickFormatter={formatDateLabel}
              tick={defaultAxisTickStyle}
              minTickGap={defaultMinTickGap}
            />
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
                typeof value === 'number' ? formatIndexValue(value) : 'n/a',
                typeof name === 'string' ? name : '',
              ]}
              labelFormatter={(label: unknown) =>
                formatDateLabel(typeof label === 'string' || typeof label === 'number' ? label : undefined)
              }
              contentStyle={defaultTooltipContentStyle}
            />
            <Line
              type="monotone"
              dataKey="portfolio"
              name="Portfolio"
              stroke="var(--color-line-portfolio)"
              dot={false}
              connectNulls={false}
              strokeWidth={2}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="benchmark"
              name={benchmarkSymbol}
              stroke="var(--color-text-muted)"
              strokeDasharray="5 5"
              dot={false}
              connectNulls={false}
              strokeWidth={1.5}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartShell>
      )}
    </div>
  )
}
