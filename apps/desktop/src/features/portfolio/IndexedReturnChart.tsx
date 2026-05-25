import { useState } from 'react'
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { DriftDailyPoint, DriftWindow } from './types'

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
  // Build from DriftWindows; include all 5 in reverse order (largest first)
  // plus an "All" option that shows the full series
  const opts: WindowOption[] = windows.map((w) => ({ label: w.label, startDate: w.start_date }))
  return opts
}

function sliceAndRebase(
  series: DriftDailyPoint[],
  startDate: string | null,
): Array<{ date: string; portfolio: number | null; benchmark: number | null }> {
  const sliced = startDate ? series.filter((p) => p.date >= startDate) : series

  // Find first non-null values for rebasing
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

export function IndexedReturnChart({ series, windows, benchmarkSymbol }: IndexedReturnChartProps) {
  const windowOptions = buildWindowOptions(windows)
  const [selectedWindowLabel, setSelectedWindowLabel] = useState<string>(
    windowOptions[windowOptions.length - 1]?.label ?? '',
  )

  const selectedWindow = windowOptions.find((w) => w.label === selectedWindowLabel) ?? windowOptions[windowOptions.length - 1]
  const chartData = sliceAndRebase(series, selectedWindow?.startDate ?? null)
  const hasData = chartData.some((p) => p.portfolio != null || p.benchmark != null)

  return (
    <div className="drift-chart-shell">
      {windowOptions.length > 1 && (
        <div className="drift-chart-window-selector" role="group" aria-label="Chart window">
          {windowOptions.map((opt) => (
            <button
              key={opt.label}
              type="button"
              className={`drift-chart-window-btn${selectedWindowLabel === opt.label ? ' drift-chart-window-btn-active' : ''}`}
              onClick={() => { setSelectedWindowLabel(opt.label) }}
            >
              {opt.label}
            </button>
          ))}
        </div>
      )}
      {!hasData ? (
        <p className="helper drift-chart-empty">No data available for the selected window.</p>
      ) : (
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={chartData} margin={{ top: 4, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis dataKey="date" tickFormatter={formatDateLabel} tick={{ fontSize: 11 }} minTickGap={40} />
            <YAxis
              tickFormatter={(v: number) => v.toFixed(0)}
              tick={{ fontSize: 11 }}
              width={40}
              domain={['auto', 'auto']}
            />
            <ReferenceLine y={100} stroke="#94a3b8" strokeDasharray="2 2" />
            <Tooltip
              formatter={(value: unknown, name: unknown) => [
                typeof value === 'number' ? formatIndexValue(value) : 'n/a',
                typeof name === 'string' ? name : '',
              ]}
              labelFormatter={(label: unknown) => formatDateLabel(typeof label === 'string' || typeof label === 'number' ? label : undefined)}
            />
            <Line
              type="monotone"
              dataKey="portfolio"
              name="Portfolio"
              stroke="#4f8ef7"
              dot={false}
              connectNulls={false}
              strokeWidth={2}
            />
            <Line
              type="monotone"
              dataKey="benchmark"
              name={benchmarkSymbol}
              stroke="#94a3b8"
              strokeDasharray="5 5"
              dot={false}
              connectNulls={false}
              strokeWidth={1.5}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
