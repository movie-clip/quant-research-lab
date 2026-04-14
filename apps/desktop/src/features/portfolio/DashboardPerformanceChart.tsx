import { Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { TooltipContentProps } from 'recharts/types/component/Tooltip'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'


function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'n/a' : `$${value.toFixed(2)}`
}

function formatDateLabel(value: string | number | null | undefined) {
  if (typeof value !== 'string') {
    return ''
  }

  const [year, month, day] = value.split('-')
  if (!year || !month || !day) {
    return value
  }

  return `${month}/${day}/${year.slice(2)}`
}

function formatIndex(value: number | null | undefined) {
  return value == null ? 'n/a' : value.toFixed(2)
}

function formatTooltipValue(value: ValueType | undefined, mode: 'capital' | 'performance') {
  if (value == null || typeof value !== 'number') {
    return 'n/a'
  }

  return mode === 'capital' ? formatMoney(value) : formatIndex(value)
}

function PerformanceTooltip(
  {
    active,
    payload,
    label,
    mode,
    labels,
  }: TooltipContentProps<ValueType, NameType> & { mode: 'capital' | 'performance'; labels: Record<string, string> },
) {
  if (!active || !payload?.length) {
    return null
  }

  const rows = payload.filter((item) => item.value != null)
  if (!rows.length) {
    return null
  }

  return (
    <div className="chart-tooltip-card">
      <p className="chart-tooltip-date">{formatDateLabel(label)}</p>
      {rows.map((item) => {
        const key = typeof item.dataKey === 'string' ? item.dataKey : String(item.dataKey)
        return (
          <div className="chart-tooltip-row" key={key}>
            <span className="chart-tooltip-label">
              <span className="chart-tooltip-swatch" style={{ backgroundColor: item.color ?? '#748295' }} />
              {labels[key] ?? key}
            </span>
            <span>{formatTooltipValue(item.value, mode)}</span>
          </div>
        )
      })}
    </div>
  )
}

type CapitalPoint = {
  date: string
  portfolioValue: number
  contributionBase: number
}

type PerformancePoint = {
  date: string
  portfolioIndex: number | null
  benchmarkIndex: number | null
  portfolioReturnPct: number | null
  benchmarkReturnPct: number | null
  flow: number
}

type Props = {
  performanceView: 'twr' | 'mwr' | 'capital'
  capitalChartData: CapitalPoint[]
  performancePathData: PerformancePoint[]
  showPortfolio: boolean
  showBenchmark: boolean
}

export function DashboardPerformanceChart({ performanceView, capitalChartData, performancePathData, showPortfolio, showBenchmark }: Props) {
  return (
    <div className="line-chart-panel performance-chart-panel">
      <ResponsiveContainer width="100%" height="100%" minWidth={0} minHeight={240}>
        {performanceView === 'capital' ? (
          <LineChart data={capitalChartData} margin={{ top: 18, right: 16, left: 8, bottom: 8 }}>
            <CartesianGrid stroke="rgba(70, 82, 98, 0.16)" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" padding={{ left: 0, right: 0 }} tickFormatter={formatDateLabel} />
            <YAxis tick={{ fill: '#748295', fontSize: 10 }} width={56} tickFormatter={(value) => `$${Number(value).toFixed(0)}`} />
            <Tooltip content={(props) => <PerformanceTooltip {...props} mode="capital" labels={{ portfolioValue: 'Portfolio value', contributionBase: 'Contribution base' }} />} />
            <Line type="monotone" dataKey="portfolioValue" name="Portfolio value" stroke="#d85a51" dot={false} strokeWidth={2.4} isAnimationActive={false} />
            <Line type="monotone" dataKey="contributionBase" name="Contribution base" stroke="#e1bf67" dot={false} strokeWidth={2} isAnimationActive={false} />
          </LineChart>
        ) : (
          <AreaChart data={performancePathData} margin={{ top: 18, right: 16, left: 8, bottom: 8 }}>
            <defs>
              <linearGradient id="dashboardPortfolioFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#d85a51" stopOpacity={0.24} />
                <stop offset="100%" stopColor="#d85a51" stopOpacity={0.03} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="rgba(70, 82, 98, 0.16)" strokeDasharray="3 3" />
            <XAxis dataKey="date" tick={{ fill: '#748295', fontSize: 10 }} minTickGap={28} interval="preserveStartEnd" padding={{ left: 0, right: 0 }} tickFormatter={formatDateLabel} />
            <YAxis tick={{ fill: '#748295', fontSize: 10 }} width={48} domain={['dataMin - 2', 'dataMax + 2']} />
            <ReferenceLine y={100} stroke="rgba(156, 169, 184, 0.34)" strokeDasharray="5 5" ifOverflow="extendDomain" />
            <Tooltip content={(props) => <PerformanceTooltip {...props} mode="performance" labels={{ portfolioIndex: performanceView === 'mwr' ? 'Portfolio index (MWR view)' : 'Portfolio index', benchmarkIndex: 'SPY index' }} />} />
            {(performanceView === 'mwr' || showPortfolio) ? <Area type="monotone" dataKey="portfolioIndex" name={performanceView === 'mwr' ? 'Portfolio index (MWR view)' : 'Portfolio index'} stroke="#d85a51" fill="url(#dashboardPortfolioFill)" strokeWidth={2.4} dot={false} isAnimationActive={false} /> : null}
            {performanceView === 'twr' && showBenchmark ? <Line type="monotone" dataKey="benchmarkIndex" name="SPY index" stroke="#6c88a6" dot={false} strokeWidth={2} isAnimationActive={false} /> : null}
          </AreaChart>
        )}
      </ResponsiveContainer>
    </div>
  )
}
