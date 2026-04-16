import { Suspense, lazy, useEffect, useMemo, useState } from 'react'
import type { DashboardAnalysis, ExposureAnalysis, ExposureFactorModelResponse, ImportedStatementImporter } from './types'
import { RollingFactorLoadingsCard } from './RollingFactorLoadingsCard'
import { clonePortfolioSnapshot } from './portfolioSnapshot'
import type { CandidateImprovementDraftArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, PortfolioSnapshot, ReplacementIntentDraftArtifact } from './workspaceTypes'

type RangeOption = '1M' | '3M' | 'YTD' | '1Y' | 'All'
type PerformanceView = 'twr' | 'mwr' | 'capital'
type EditableHolding = { symbol: string; market_value: number; sector?: string | null }

type StatusTone = 'neutral' | 'positive' | 'negative'

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'n/a' : `$${value.toFixed(2)}`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatRangeLabel(range: RangeOption) {
  if (range === '1M') return '1M range'
  if (range === '3M') return '3M range'
  if (range === '1Y') return '1Y range'
  return range === 'All' ? 'Full history' : 'YTD range'
}

function formatHistoryWindowLabel(startDate: string | null | undefined, endDate: string | null | undefined) {
  if (!startDate || !endDate) return 'History window unavailable'
  return `${startDate} to ${endDate}`
}

function formatLoadedFilesLabel(statementCount: number, loadedStatementsLabel: string | null) {
  if (!loadedStatementsLabel) return null
  return `${statementCount > 1 ? 'Loaded statements' : 'Loaded file'}: ${loadedStatementsLabel}`
}

function valueToneClass(value: number | null | undefined) {
  if (value == null || value === 0) return ''
  return value > 0 ? 'positive-text' : 'negative-text'
}

function buildPerformanceEmptyState(status: string | null | undefined, range: RangeOption) {
  if (status === 'suppressed') {
    return {
      title: 'Performance history is suppressed for this import.',
      detail: `The ${formatRangeLabel(range)} chart stays hidden because the reconstructed series is unstable and should not be shown as a reliable path.`,
    }
  }
  if (status === 'unavailable') {
    return {
      title: 'Performance history is unavailable for this import.',
      detail: `The ${formatRangeLabel(range)} chart cannot render until daily portfolio history is available.`,
    }
  }
  return {
    title: 'No performance history available yet.',
    detail: 'Import analysis succeeded, but the dashboard does not have enough daily history to render performance charts for the selected range.',
  }
}

function buildMonthlyReturnsEmptyState(status: string | null | undefined) {
  if (status === 'suppressed') {
    return {
      title: 'Monthly returns are suppressed for this imported history.',
      detail: 'This synthetic multi-statement path includes unstable reconstruction effects, so monthly return cards stay hidden until the history is economically consistent.',
    }
  }
  if (status === 'unavailable') {
    return {
      title: 'Monthly returns are unavailable for this imported history.',
      detail: 'Monthly cards appear only when the import includes a reliable monthly performance chain.',
    }
  }
  return {
    title: 'Monthly returns are not reliable for this imported history.',
    detail: 'This synthetic multi-statement path includes unstable reconstruction effects, so monthly return cards are hidden until the history is economically consistent.',
  }
}

function formatBrokerLabel(importer: ImportedStatementImporter) {
  if (importer === 'multi_broker') return 'Multi-Broker'
  return importer === 'freedom24' ? 'Freedom24' : 'Interactive Brokers'
}

function dashboardSourceLabel(status: string | undefined) {
  if (status === 'live') return 'Live market history'
  if (status === 'suppressed') return 'Suppressed unstable series'
  return 'Sample or reconstructed history'
}

function hasRichDashboardData(result: DashboardAnalysis | null) {
  return Boolean(result && (result.performance_series.length || result.daily_states.length || result.source_status))
}

function buildUnavailableRangeSummary() {
  return {
    startValue: null,
    endValue: null,
    netContributions: null,
    investmentGain: null,
    timeWeightedReturnPct: null,
    moneyWeightedReturnPct: null,
    benchmarkReturnPct: null,
    excessReturnPct: null,
  }
}

function resolveDisplayedPortfolioValue(result: DashboardAnalysis | null, visibleSummaryEndValue: number | null, latestPerfValue: number | null) {
  if (!result) return visibleSummaryEndValue ?? latestPerfValue
  const statementEndingNav = result.snapshot.statement_totals?.ending_nav ?? null
  const latestStateValue = result.daily_states.length ? result.daily_states[result.daily_states.length - 1].total_portfolio_value : null
  const candidateEndValue = visibleSummaryEndValue ?? latestStateValue ?? latestPerfValue
  if (
    statementEndingNav != null
    && latestStateValue != null
    && Math.abs(latestStateValue - statementEndingNav) > 0.01
    && candidateEndValue === latestStateValue
  ) {
    return statementEndingNav
  }
  return candidateEndValue
}

export function normalizePerformanceSeries(perf: DashboardAnalysis['performance_series']) {
  const anchorPoint = perf.find((point) => point.portfolio_value > 0)
  const anchorPortfolioValue = anchorPoint?.portfolio_value ?? null
  const anchorBenchmarkPrice = anchorPoint?.benchmark_price ?? null

  return perf.map((point) => {
    const beforeAnchor = anchorPoint != null && point.date < anchorPoint.date
    return {
      ...point,
      portfolio_index: anchorPortfolioValue && anchorPortfolioValue > 0 && !beforeAnchor
        ? (point.portfolio_value / anchorPortfolioValue) * 100
        : null,
      benchmark_index: anchorBenchmarkPrice && anchorBenchmarkPrice > 0 && !beforeAnchor && point.benchmark_price
        ? (point.benchmark_price / anchorBenchmarkPrice) * 100
        : null,
    }
  })
}

function buildSectorAllocationFromSnapshot(snapshot: PortfolioSnapshot | null) {
  const palette = ['#d85a51', '#6c88a6', '#d6b35f', '#76d49d', '#b084f5', '#ef8a62', '#4dc2c8', '#9aa5b5']
  if (!snapshot) return []

  const totalMarketValue = snapshot.positions.reduce((total, position) => total + position.marketValue, 0)
  const sectorTotals = Object.entries(
    snapshot.positions.reduce<Record<string, number>>((accumulator, position) => {
      const sector = position.sector ?? 'Unassigned'
      accumulator[sector] = (accumulator[sector] ?? 0) + position.marketValue
      return accumulator
    }, {}),
  ).map(([sector, marketValue]) => ({
    sector,
    marketValue,
    weight: totalMarketValue > 0 ? marketValue / totalMarketValue : 0,
  }))
  const maxWeight = sectorTotals.length ? Math.max(...sectorTotals.map((item) => item.weight)) : 1

  return sectorTotals
    .sort((left, right) => right.marketValue - left.marketValue)
    .map((item, index) => ({
      sector: item.sector,
      marketValue: item.marketValue,
      weight: item.weight,
      color: palette[index % palette.length],
      intensity: maxWeight > 0 ? item.weight / maxWeight : 0,
    }))
}

function abbreviateSectorLabel(label: string) {
  const map: Record<string, string> = {
    Technology: 'IT',
    Financials: 'Fin',
    'Communication Services': 'Comm',
    'Consumer Discretionary': 'Cons',
    'Consumer Staples': 'Staples',
    'Health Care': 'Health',
    Industrials: 'Ind',
    Materials: 'Mat',
    Energy: 'Energy',
    'Equity ETF': 'ETF',
    'Commodity ETF': 'Gold',
  }

  return map[label] ?? label.slice(0, 6)
}

function buildEditableSectorDraftFromSnapshot(snapshot: PortfolioSnapshot | null) {
  if (!snapshot) return {} as Record<string, EditableHolding[]>
  const grouped = snapshot.positions.reduce<Record<string, EditableHolding[]>>((accumulator, position) => {
    const sector = position.sector ?? 'Unassigned'
    accumulator[sector] = [...(accumulator[sector] ?? []), {
      symbol: position.symbol,
      market_value: position.marketValue,
      sector,
    }]
    return accumulator
  }, {})

  return Object.fromEntries(
    Object.entries(grouped).map(([sector, positions]) => [
      sector,
      positions.sort((left, right) => right.market_value - left.market_value),
    ]),
  )
}

function buildSnapshotFromSectorDraft(snapshot: PortfolioSnapshot | null, draft: Record<string, EditableHolding[]>) {
  if (!snapshot) return null
  const next = clonePortfolioSnapshot(snapshot)
  next.positions = Object.entries(draft)
    .flatMap(([sector, positions]) => positions.map((position) => ({
      symbol: position.symbol.toUpperCase(),
      marketValue: Number.isFinite(position.market_value) ? position.market_value : 0,
      quantity: null,
      currency: next.baseCurrency,
      sector,
      sourceType: 'equity' as const,
    })))
    .filter((position) => position.symbol)
  return next
}

function normalizeSectorDraft(draft: Record<string, EditableHolding[]>) {
  return Object.fromEntries(
    Object.entries(draft)
      .map(([sector, positions]) => [
        sector,
        positions.filter((position) => position.symbol || position.market_value !== 0),
      ])
      .filter(([, positions]) => Array.isArray(positions) && positions.length > 0),
  ) as Record<string, EditableHolding[]>
}

function polarToCartesian(cx: number, cy: number, radius: number, angle: number) {
  return {
    x: cx + (radius * Math.cos(angle)),
    y: cy + (radius * Math.sin(angle)),
  }
}

function describePieSlice(startAngle: number, endAngle: number) {
  const cx = 110
  const cy = 110
  const radius = 94
  const start = polarToCartesian(cx, cy, radius, startAngle - (Math.PI / 2))
  const end = polarToCartesian(cx, cy, radius, endAngle - (Math.PI / 2))
  const largeArcFlag = endAngle - startAngle > Math.PI ? 1 : 0

  return `M ${cx} ${cy} L ${start.x} ${start.y} A ${radius} ${radius} 0 ${largeArcFlag} 1 ${end.x} ${end.y} Z`
}

type DashboardPanelProps = {
  result: DashboardAnalysis | null
  exposureResult?: ExposureAnalysis | null
  factorModel?: ExposureFactorModelResponse | null
  draftSnapshot?: PortfolioSnapshot | null
  activeNodeName?: string | null
  draftStatus?: 'clean' | 'dirty' | null
  candidateImprovementDraft?: CandidateImprovementDraftArtifact | null
  intentBoundSeededEtfReplacementRankingDraft?: IntentBoundSeededEtfReplacementRankingDraftArtifact | null
  replacementIntentDraft?: ReplacementIntentDraftArtifact | null
  importing?: boolean
  importError?: string | null
  lastImportedFileNames?: string[]
  restoredSession?: boolean
  onImportPortfolio?: () => void
  onAppendStatement?: () => void
  onClearImportedSession?: () => void
  onResetLocalDatabase?: () => void | Promise<void>
  onPreviewExposure?: (snapshot: PortfolioSnapshot) => void | Promise<void>
  onDraftSnapshotChange?: (snapshot: PortfolioSnapshot) => void | Promise<void>
  onDiscardDraft?: () => void | Promise<void>
  onSaveVariant?: (variantName: string) => void | Promise<void>
}

const DashboardPerformanceChart = lazy(async () => ({ default: (await import('./DashboardPerformanceChart')).DashboardPerformanceChart }))

function formatLoadedStatements(result: DashboardAnalysis | null, fallbackFileNames: string[]) {
  if (!result?.snapshot.statements?.length) {
    return fallbackFileNames.length ? fallbackFileNames.join(', ') : null
  }

  return result.snapshot.statements
    .map((statement) => {
      const sourcePath = statement.source_path
      if (!sourcePath) {
        return statement.statement_period || 'Imported statement'
      }
      return sourcePath.split(/[/\\]/).pop() || sourcePath
    })
    .join(', ')
}

function formatSeedDisplayValue(value: string | number | null | undefined) {
  if (value == null) return 'n/a'
  if (typeof value === 'string') return value.trim() ? value : 'n/a'
  return String(value)
}

export function DashboardPanel({ result, exposureResult = null, factorModel = null, draftSnapshot = null, activeNodeName = null, draftStatus = null, candidateImprovementDraft = null, intentBoundSeededEtfReplacementRankingDraft = null, replacementIntentDraft = null, importing = false, importError = null, lastImportedFileNames = [], restoredSession = false, onImportPortfolio, onAppendStatement, onClearImportedSession, onResetLocalDatabase, onPreviewExposure, onDraftSnapshotChange, onDiscardDraft, onSaveVariant }: DashboardPanelProps) {
  const [selectedRange, setSelectedRange] = useState<RangeOption>('3M')
  const [showPortfolio, setShowPortfolio] = useState(true)
  const [showBenchmark, setShowBenchmark] = useState(true)
  const [performanceView, setPerformanceView] = useState<PerformanceView>('twr')
  const [hoveredSector, setHoveredSector] = useState<string | null>(null)
  const [lockedSector, setLockedSector] = useState<string | null>(null)
  const [sectorDraft, setSectorDraft] = useState<Record<string, EditableHolding[]>>({})
  const [variantName, setVariantName] = useState('')
  useEffect(() => {
    setSectorDraft(buildEditableSectorDraftFromSnapshot(draftSnapshot))
  }, [draftSnapshot])

  const allPerf = result?.performance_series ?? []

  const perf = useMemo(() => {
    if (!allPerf.length) {
      return []
    }

    if (selectedRange === '1M') {
      return allPerf.slice(-21)
    }
    if (selectedRange === '3M') {
      return allPerf.slice(-63)
    }
    if (selectedRange === 'YTD') {
      const year = allPerf[allPerf.length - 1].date.slice(0, 4)
      return allPerf.filter((point) => point.date.startsWith(year))
    }
    if (selectedRange === '1Y') {
      return allPerf.slice(-252)
    }
    return allPerf
  }, [allPerf, selectedRange])

  const visibleStates = useMemo(() => {
    if (!result) {
      return []
    }
    const visibleDates = new Set(perf.map((point) => point.date))
    return result.daily_states.filter((state) => visibleDates.has(state.date))
  }, [perf, result])

  const selectedRangeMetrics = result?.range_metrics?.[selectedRange] ?? null

  const resolvedSummary = selectedRangeMetrics?.summary
    ? {
        startValue: selectedRangeMetrics.summary.start_value,
        endValue: selectedRangeMetrics.summary.end_value,
        netContributions: selectedRangeMetrics.summary.net_contributions,
        investmentGain: selectedRangeMetrics.summary.investment_gain,
        timeWeightedReturnPct: selectedRangeMetrics.summary.time_weighted_return_pct,
        moneyWeightedReturnPct: selectedRangeMetrics.summary.money_weighted_return_pct,
        benchmarkReturnPct: selectedRangeMetrics.summary.benchmark_return_pct,
        excessReturnPct: selectedRangeMetrics.summary.excess_return_pct,
      }
    : buildUnavailableRangeSummary()
  const latestPerf = perf.length ? perf[perf.length - 1] : null
  const displayedPortfolioValue = useMemo(
    () => resolveDisplayedPortfolioValue(result, resolvedSummary.endValue, latestPerf?.portfolio_value ?? null),
    [latestPerf?.portfolio_value, result, resolvedSummary.endValue],
  )

  const normalizedPerf = useMemo(() => normalizePerformanceSeries(perf), [perf])

  const hasPerformance = normalizedPerf.length > 0 && visibleStates.length > 0
  const maxIndex = hasPerformance
    ? Math.max(...normalizedPerf.map((point) => Math.max(point.portfolio_index ?? 100, point.benchmark_index ?? 100, 100)))
    : 100
  const minIndex = hasPerformance
    ? Math.min(...normalizedPerf.map((point) => Math.min(point.portfolio_index ?? 100, point.benchmark_index ?? 100, 100)))
    : 100
  const indexRange = Math.max(maxIndex - minIndex, 1)
  const maxDrawdown = selectedRangeMetrics?.max_drawdown_pct ?? null
  const monthlyReturns = useMemo(
    () => selectedRangeMetrics?.monthly_returns?.map((item) => ({ month: item.month, returnPct: item.return_pct })) ?? [],
    [selectedRangeMetrics?.monthly_returns],
  )
  const monthlyReturnsReliable = selectedRangeMetrics?.monthly_returns_reliable ?? false
  const nextDraftSnapshot = useMemo(() => buildSnapshotFromSectorDraft(draftSnapshot, sectorDraft), [draftSnapshot, sectorDraft])
  const sectorAllocation = useMemo(() => buildSectorAllocationFromSnapshot(nextDraftSnapshot), [nextDraftSnapshot])
  const activeSector = hoveredSector ?? lockedSector
  const selectedSector = activeSector ?? sectorAllocation[0]?.sector ?? null
  const selectedSectorPositions = selectedSector ? sectorDraft[selectedSector] ?? [] : []
  const baseCapital = draftSnapshot?.positions.reduce((total, position) => total + position.marketValue, 0) ?? result?.overview.total_market_value ?? 0
  const editedNetCapital = nextDraftSnapshot?.positions.reduce((total, position) => total + position.marketValue, 0) ?? 0
  const grossExposure = Object.values(sectorDraft).flat().reduce((total, position) => total + Math.abs(position.market_value), 0)
  const leverageRatio = baseCapital > 0 ? grossExposure / baseCapital : 0
  const remainingCapital = baseCapital - editedNetCapital
  const pieSegments = useMemo(() => {
    let cumulative = 0
    return sectorAllocation.map((item) => {
      const startAngle = cumulative * Math.PI * 2
      cumulative += item.weight
      return { ...item, startAngle, endAngle: cumulative * Math.PI * 2 }
    })
  }, [sectorAllocation])
  const contributionBaseSeries = visibleStates.map((state, index) => ({
    date: state.date,
    contributionBase:
      resolvedSummary.startValue != null
        ? resolvedSummary.startValue + visibleStates.slice(1, index + 1).reduce((total, item) => total + item.external_cash_flow, 0)
        : state.total_portfolio_value,
    portfolioValue: state.total_portfolio_value,
  }))
  const contributionMax = contributionBaseSeries.length
    ? Math.max(...contributionBaseSeries.map((point) => Math.max(point.contributionBase, point.portfolioValue)))
    : 0
  const contributionMin = contributionBaseSeries.length
    ? Math.min(...contributionBaseSeries.map((point) => Math.min(point.contributionBase, point.portfolioValue)))
    : 0
  const contributionRange = Math.max(contributionMax - contributionMin, 1)
  const capitalChartData = contributionBaseSeries.map((point) => ({
    date: point.date,
    portfolioValue: point.portfolioValue,
    contributionBase: point.contributionBase,
  }))
  const performancePathData = normalizedPerf.map((point) => ({
    date: point.date,
    portfolioIndex: point.portfolio_index,
    benchmarkIndex: point.benchmark_index,
    portfolioReturnPct: point.portfolio_return_pct,
    benchmarkReturnPct: point.benchmark_return_pct,
    flow: visibleStates.find((state) => state.date === point.date)?.external_cash_flow ?? 0,
  }))

  const contributionPortfolioLine = contributionBaseSeries
    .map((point, index) => {
      const x = contributionBaseSeries.length > 1 ? (index / (contributionBaseSeries.length - 1)) * 1000 : 1000
      const y = 300 - (((point.portfolioValue - contributionMin) / contributionRange) * 260)
      return `${x},${y}`
    })
    .join(' ')

  const contributionBaseLine = contributionBaseSeries
    .map((point, index) => {
      const x = contributionBaseSeries.length > 1 ? (index / (contributionBaseSeries.length - 1)) * 1000 : 1000
      const y = 300 - (((point.contributionBase - contributionMin) / contributionRange) * 260)
      return `${x},${y}`
    })
    .join(' ')

  const portfolioLine = normalizedPerf
    .map((point, index) => {
      const x = normalizedPerf.length > 1 ? (index / (normalizedPerf.length - 1)) * 1000 : 1000
      const y = 300 - (((point.portfolio_index ?? 100) - minIndex) / indexRange) * 260
      return `${x},${y}`
    })
    .join(' ')

  const benchmarkLine = normalizedPerf
    .map((point, index) => {
      const x = normalizedPerf.length > 1 ? (index / (normalizedPerf.length - 1)) * 1000 : 1000
      const y = 300 - (((point.benchmark_index ?? 100) - minIndex) / indexRange) * 260
      return `${x},${y}`
    })
    .join(' ')

  function handleSectorActivate(sector: string) {
    setLockedSector((current) => (current === sector ? null : sector))
  }

  function updateSelectedSectorHolding(index: number, field: 'symbol' | 'market_value', value: string) {
    if (!selectedSector) return
    const nextDraft = {
      ...sectorDraft,
      [selectedSector]: (sectorDraft[selectedSector] ?? []).map((position, positionIndex) => positionIndex === index
        ? {
          ...position,
          [field]: field === 'market_value' ? Number(value || '0') : value.toUpperCase(),
        }
        : position),
    }
    setSectorDraft(nextDraft)
    const nextSnapshot = buildSnapshotFromSectorDraft(draftSnapshot, nextDraft)
    if (nextSnapshot) void onDraftSnapshotChange?.(nextSnapshot)
  }

  function removeSelectedSectorHolding(index: number) {
    if (!selectedSector) return
    const nextDraft = normalizeSectorDraft({
      ...sectorDraft,
      [selectedSector]: (sectorDraft[selectedSector] ?? []).filter((_, positionIndex) => positionIndex !== index),
    })
    setSectorDraft(nextDraft)
    if (!nextDraft[selectedSector]) {
      setLockedSector(null)
      setHoveredSector(null)
    }
    const nextSnapshot = buildSnapshotFromSectorDraft(draftSnapshot, nextDraft)
    if (nextSnapshot) void onDraftSnapshotChange?.(nextSnapshot)
  }

  function addSelectedSectorHolding() {
    if (!selectedSector) return
    const nextDraft = {
      ...sectorDraft,
      [selectedSector]: [...(sectorDraft[selectedSector] ?? []), { symbol: '', market_value: 0, sector: selectedSector }],
    }
    setSectorDraft(nextDraft)
    const nextSnapshot = buildSnapshotFromSectorDraft(draftSnapshot, nextDraft)
    if (nextSnapshot) void onDraftSnapshotChange?.(nextSnapshot)
  }

  const loadedStatementsLabel = formatLoadedStatements(result, lastImportedFileNames)
  const statementCount = result?.snapshot.statements?.length ?? lastImportedFileNames.length
  const loadedFilesLabel = formatLoadedFilesLabel(statementCount, loadedStatementsLabel)
  const dashboardSourceSummary = result?.source_status?.performance_history ? dashboardSourceLabel(result.source_status.performance_history) : null

  if (!result || !hasRichDashboardData(result)) {
    return (
      <article className="panel dashboard-panel">
        <div className="section-header-inline dashboard-header-actions">
          <div>
            <p className="panel-label">Dashboard</p>
            <h2>Account overview</h2>
          </div>
          <div className="dashboard-action-row">
            {onImportPortfolio ? <button className="secondary-button" onClick={onImportPortfolio} type="button">{importing ? 'Importing...' : loadedStatementsLabel ? 'Replace Import' : 'Import Portfolio'}</button> : null}
            {onAppendStatement ? <button className="secondary-button dashboard-append-button" onClick={onAppendStatement} type="button">{importing ? 'Importing...' : 'Add Statement'}</button> : null}
            {onClearImportedSession ? <button className="secondary-button dashboard-clear-button" onClick={onClearImportedSession} type="button">Clear Imported Session</button> : null}
            {onResetLocalDatabase ? <button className="secondary-button dashboard-clear-button" onClick={() => void onResetLocalDatabase()} type="button">Reset Local DB</button> : null}
          </div>
        </div>
        <p className="lead compact-lead">Import an Interactive Brokers or Freedom24 statement to populate the dashboard with account summary, look-through exposure, and professional risk views.</p>
        {loadedStatementsLabel ? <p className="helper">Last import: {loadedStatementsLabel}</p> : null}
        {restoredSession ? <p className="helper">Restored on launch</p> : null}
        {importError ? <p className="error">{importError}</p> : null}
      </article>
    )
  }

  const performanceHistoryStatus = result.source_status?.performance_history ?? 'unavailable'
  const monthlyReturnsStatus = result.source_status?.monthly_returns ?? 'unavailable'
  const performanceEmptyState = buildPerformanceEmptyState(performanceHistoryStatus, selectedRange)
  const monthlyReturnsEmptyState = buildMonthlyReturnsEmptyState(monthlyReturnsStatus)
  const benchmarkLabel = result.performance_series.find((point) => point.benchmark_price != null) ? 'SPY' : 'Benchmark'
  const visibleHistoryWindow = perf.length ? formatHistoryWindowLabel(perf[0]?.date ?? null, perf[perf.length - 1]?.date ?? null) : 'History window unavailable'
  const rangeMetricsStatusLabel = selectedRangeMetrics ? 'Range metrics live' : 'Range metrics unavailable'
  const workspaceStateLabel = draftStatus ? `Working draft ${draftStatus}` : activeNodeName ? `Viewing ${activeNodeName}` : 'Imported snapshot view'
  const quantMetrics: Array<{ label: string; value: string; helper: string; detail: string; tone: StatusTone; badge: string }> = [
    {
      label: 'Portfolio Value',
      value: formatMoney(displayedPortfolioValue),
      helper: `Start value: ${formatMoney(resolvedSummary.startValue)}`,
      detail: 'Current portfolio truth',
      tone: 'neutral',
      badge: 'Current truth',
    },
    {
      label: 'Time-Weighted Return',
      value: formatPct(resolvedSummary.timeWeightedReturnPct),
      helper: 'Contribution-neutral return for the selected range',
      detail: formatRangeLabel(selectedRange),
      tone: resolvedSummary.timeWeightedReturnPct != null && resolvedSummary.timeWeightedReturnPct < 0 ? 'negative' : 'positive',
      badge: formatRangeLabel(selectedRange),
    },
    {
      label: 'Money-Weighted Return',
      value: formatPct(resolvedSummary.moneyWeightedReturnPct),
      helper: 'Modified Dietz style money-weighted return for the selected range.',
      detail: rangeMetricsStatusLabel,
      tone: resolvedSummary.moneyWeightedReturnPct != null && resolvedSummary.moneyWeightedReturnPct < 0 ? 'negative' : 'positive',
      badge: formatRangeLabel(selectedRange),
    },
    {
      label: `${benchmarkLabel} Excess Return`,
      value: formatPct(resolvedSummary.excessReturnPct),
      helper: `${benchmarkLabel} return: ${formatPct(resolvedSummary.benchmarkReturnPct)}`,
      detail: hasPerformance ? visibleHistoryWindow : rangeMetricsStatusLabel,
      tone: resolvedSummary.excessReturnPct != null && resolvedSummary.excessReturnPct < 0 ? 'negative' : 'positive',
      badge: dashboardSourceSummary ?? 'Performance source',
    },
    {
      label: 'Net Contributions',
      value: formatMoney(resolvedSummary.netContributions),
      helper: 'Deposits minus withdrawals in the selected range',
      detail: formatRangeLabel(selectedRange),
      tone: resolvedSummary.netContributions != null && resolvedSummary.netContributions < 0 ? 'negative' : 'neutral',
      badge: rangeMetricsStatusLabel,
    },
    {
      label: 'Max Drawdown',
      value: formatPct(maxDrawdown),
      helper: 'Maximum drawdown from the visible portfolio path.',
      detail: hasPerformance ? visibleHistoryWindow : dashboardSourceSummary ?? 'Performance source',
      tone: maxDrawdown != null ? 'negative' : 'neutral',
      badge: hasPerformance ? 'Visible path' : 'Unavailable',
    },
  ]

  return (
    <article className="panel dashboard-panel">
      <section className="dashboard-quant-header-shell">
        <div className="section-header-inline dashboard-header-actions dashboard-quant-header-row">
          <div className="dashboard-quant-header-copy">
            <p className="panel-label">Dashboard</p>
            <h2>Account and performance</h2>
            <p className="lead compact-lead">Quant view for current portfolio truth, selected-range performance, explicit provenance, and degraded-state handling.</p>
            <div className="dashboard-meta-row dashboard-meta-row-quant">
              <span className="broker-badge">{formatBrokerLabel(result.snapshot.statement.importer)}</span>
              <span className="backtest-source-badge">{rangeMetricsStatusLabel}</span>
              {dashboardSourceSummary ? <span className="backtest-source-badge">{dashboardSourceSummary}</span> : null}
              <span className="backtest-source-badge">Monthly returns: {dashboardSourceLabel(monthlyReturnsStatus)}</span>
              <span className="backtest-source-badge">{workspaceStateLabel}</span>
              {restoredSession ? <span className="backtest-source-badge">Restored on launch</span> : null}
            </div>
            {importError ? <p className="error">{importError}</p> : null}
          </div>
          <div className="dashboard-action-row">
            {onImportPortfolio ? <button className="secondary-button" onClick={onImportPortfolio} type="button">{importing ? 'Importing...' : 'Replace Import'}</button> : null}
            {onAppendStatement ? <button className="secondary-button dashboard-append-button" onClick={onAppendStatement} type="button">{importing ? 'Importing...' : 'Add Statement'}</button> : null}
            {onClearImportedSession ? <button className="secondary-button dashboard-clear-button" onClick={onClearImportedSession} type="button">Clear Imported Session</button> : null}
            {onResetLocalDatabase ? <button className="secondary-button dashboard-clear-button" onClick={() => void onResetLocalDatabase()} type="button">Reset Local DB</button> : null}
          </div>
        </div>
        <div className="dashboard-quant-context-grid">
          <div className="summary-card dashboard-quant-context-card">
            <p className="stat-label">Account Context</p>
            <p className="summary-value">{result.snapshot.statement.account_id ?? 'Unknown'}</p>
            <p className="helper">{formatBrokerLabel(result.snapshot.statement.importer)} · {result.snapshot.statement.statement_period ?? 'Statement period unavailable'}{statementCount > 1 ? ` · ${statementCount} statements combined` : ''}</p>
          </div>
          <div className="summary-card dashboard-quant-context-card">
            <p className="stat-label">Import Provenance</p>
            <p className="summary-value">{statementCount}</p>
            <p className="helper">{loadedFilesLabel ?? 'No loaded file metadata'}</p>
          </div>
          <div className="summary-card dashboard-quant-context-card">
            <p className="stat-label">Performance Provenance</p>
            <p className="summary-value">{dashboardSourceSummary ?? 'Unavailable'}</p>
            <p className="helper">Visible window: {hasPerformance ? visibleHistoryWindow : 'History window unavailable'}</p>
          </div>
        </div>
      </section>

      <section className="dashboard-quant-strip">
        <div className="section-header-inline sector-list-header dashboard-quant-strip-header">
          <div>
            <p className="panel-label">Selected Range Snapshot</p>
            <p className="helper">Current portfolio truth stays separate from selected-range performance calculations and their provenance.</p>
          </div>
          <div className="dashboard-meta-row dashboard-quant-range-badges">
            <span className="backtest-source-badge">{formatRangeLabel(selectedRange)}</span>
            <span className="backtest-source-badge">{hasPerformance ? `${visibleStates.length} daily observations` : 'No visible observations'}</span>
            <span className="backtest-source-badge">Monthly-return status: {dashboardSourceLabel(monthlyReturnsStatus)}</span>
          </div>
        </div>
        <div className="dashboard-summary dashboard-quant-metric-grid">
          {quantMetrics.map((metric) => (
            <div className="summary-card dashboard-quant-metric-card" key={metric.label}>
              <div className="dashboard-quant-metric-topline">
                <p className="stat-label">{metric.label}</p>
                <span className="backtest-source-badge dashboard-inline-badge">{metric.badge}</span>
              </div>
              <p className={`summary-value ${metric.tone === 'positive' ? 'positive-text' : metric.tone === 'negative' ? 'negative-text' : ''}`}>{metric.value}</p>
              <p className="helper">{metric.helper}</p>
              <p className="helper dashboard-quant-detail">{metric.detail}</p>
            </div>
          ))}
        </div>
      </section>

      {candidateImprovementDraft || intentBoundSeededEtfReplacementRankingDraft || replacementIntentDraft ? (
        <section className="dashboard-bottom-grid">
          <div className="summary-card">
            <p className="panel-label">Portfolio Improvement Workspace</p>
            <p className="helper">Improvement-lane review has moved out of the generic dashboard into the dedicated workflow shell in `Backtest`.</p>
            <p className="helper">Truth classes stay separated there: current portfolio truth, candidate idea metadata, hypothetical replay evidence, diagnostics change, and saved proposal artifacts.</p>
            {candidateImprovementDraft ? <p className="helper">Seed present: {candidateImprovementDraft.seed.baseSymbol} {'->'} {candidateImprovementDraft.seed.candidateSymbol}</p> : null}
            {replacementIntentDraft ? <p className="helper">Replacement intent present: {replacementIntentDraft.baseSymbol} {'->'} {replacementIntentDraft.candidateSymbol}</p> : null}
            {intentBoundSeededEtfReplacementRankingDraft ? <p className="helper">Saved ranked review is available in the workflow shell.</p> : null}
          </div>
        </section>
      ) : null}

      <section className="performance-section dashboard-performance-shell">
        <div className="performance-toolbar dashboard-performance-toolbar">
          <div className="section-header-inline performance-header-static dashboard-performance-header">
            <div className="dashboard-performance-copy">
              <p className="panel-label">Performance Workspace</p>
              <h3>{performanceView === 'capital' ? 'Portfolio value vs contribution base' : performanceView === 'mwr' ? 'Portfolio growth path for the selected range' : 'Portfolio vs SPY path for the selected range'}</h3>
              <p className="helper">Use TWR for manager skill, MWR for investor experience, and Capital Path for contributions versus ending capital.</p>
              <div className="dashboard-meta-row dashboard-performance-badges">
                <span className="backtest-source-badge">{dashboardSourceSummary ?? 'Performance source unavailable'}</span>
                <span className="backtest-source-badge">{rangeMetricsStatusLabel}</span>
                <span className="backtest-source-badge">Monthly-return status: {dashboardSourceLabel(monthlyReturnsStatus)}</span>
                <span className="backtest-source-badge">Visible window: {hasPerformance ? visibleHistoryWindow : 'Unavailable'}</span>
              </div>
            </div>
            <div className="chart-controls dashboard-performance-controls">
              <div className="toggle-group">
                <button className={`toggle-chip${performanceView === 'twr' ? ' active' : ''}`} onClick={() => setPerformanceView('twr')} type="button">TWR</button>
                <button className={`toggle-chip${performanceView === 'mwr' ? ' active' : ''}`} onClick={() => setPerformanceView('mwr')} type="button">MWR</button>
                <button className={`toggle-chip${performanceView === 'capital' ? ' active' : ''}`} onClick={() => setPerformanceView('capital')} type="button">Capital Path</button>
              </div>
              {performanceView === 'twr' ? (
                <div className="toggle-group">
                  <button className={`toggle-chip${showPortfolio ? ' active' : ''}`} onClick={() => setShowPortfolio((value) => !value)} type="button">Portfolio</button>
                  <button className={`toggle-chip${showBenchmark ? ' active' : ''}`} onClick={() => setShowBenchmark((value) => !value)} type="button">Benchmark</button>
                </div>
              ) : null}
              <div className="range-group">
                {(['1M', '3M', 'YTD', '1Y', 'All'] as RangeOption[]).map((range) => (
                  <button key={range} className={`range-chip${selectedRange === range ? ' active' : ''}`} onClick={() => setSelectedRange(range)} type="button">{range}</button>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="dashboard-performance-meta-grid">
          <div className="summary-card dashboard-performance-meta-card">
            <p className="stat-label">Visible Window</p>
            <p className="summary-value dashboard-performance-meta-value">{hasPerformance ? visibleHistoryWindow : 'Unavailable'}</p>
            <p className="helper">{visibleStates.length} daily observations in the selected chart range</p>
          </div>
          <div className="summary-card dashboard-performance-meta-card">
            <p className="stat-label">Investment Gain</p>
            <p className={`summary-value dashboard-performance-meta-value ${valueToneClass(resolvedSummary.investmentGain)}`}>{formatMoney(resolvedSummary.investmentGain)}</p>
            <p className="helper">Selected-range gain net of contributions</p>
          </div>
          <div className="summary-card dashboard-performance-meta-card">
            <p className="stat-label">Benchmark Return</p>
            <p className={`summary-value dashboard-performance-meta-value ${valueToneClass(resolvedSummary.benchmarkReturnPct)}`}>{formatPct(resolvedSummary.benchmarkReturnPct)}</p>
            <p className="helper">{benchmarkLabel} return over the selected range</p>
          </div>
        </div>

        {!hasPerformance ? (
          <div className="empty-state-panel dashboard-performance-empty-state">
            <p className="empty-state-title">{performanceEmptyState.title}</p>
            <p className="helper">{performanceEmptyState.detail}</p>
          </div>
        ) : (
          <>
            <Suspense fallback={<div className="line-chart-panel performance-chart-panel" />}>
              <DashboardPerformanceChart performanceView={performanceView} capitalChartData={capitalChartData} performancePathData={performancePathData} showPortfolio={showPortfolio} showBenchmark={showBenchmark} />
            </Suspense>

            <div className="chart-legend">
              {performanceView === 'capital' ? (
                <>
                  <span><i className="legend-swatch legend-swatch-portfolio" /> Portfolio Value</span>
                  <span><i className="legend-swatch legend-swatch-contribution" /> Contribution Base</span>
                </>
              ) : performanceView === 'twr' ? (
                <>
                  {showPortfolio ? <span><i className="legend-swatch legend-swatch-portfolio" /> Portfolio</span> : null}
                  {showBenchmark ? <span><i className="legend-swatch legend-swatch-benchmark" /> Benchmark</span> : null}
                </>
              ) : (
                <span><i className="legend-swatch legend-swatch-portfolio" /> Portfolio</span>
              )}
            </div>
          </>
        )}
      </section>

      <RollingFactorLoadingsCard result={exposureResult} factorModel={factorModel} />

      <section className="dashboard-bottom-grid unified-sector-section">
        <div className="section-header-inline sector-list-header dashboard-edit-toolbar">
          <div>
            <p className="panel-label">Allocation Overview</p>
          </div>
          <div className="actions dashboard-edit-actions dashboard-edit-actions-global dashboard-edit-actions-compact">
            <input className="path-input dashboard-variant-input" value={variantName} onChange={(event) => setVariantName(event.target.value)} placeholder="Variant name" />
            <button className="secondary-button" type="button" onClick={() => { setSectorDraft(buildEditableSectorDraftFromSnapshot(draftSnapshot)); void onDiscardDraft?.() }}>Discard draft</button>
            <button className="secondary-button" type="button" onClick={() => { if (variantName.trim()) void onSaveVariant?.(variantName.trim()) }} disabled={!variantName.trim()}>Save Variant</button>
            <button className="primary-button" type="button" onClick={() => nextDraftSnapshot && onPreviewExposure?.(nextDraftSnapshot)}>Preview in Exposure</button>
          </div>
        </div>

        <div className="sector-overview-grid unified-sector-grid">
          <div className="sector-pie-wrap sector-pie-panel">
            {sectorAllocation.length ? (
              <svg className="sector-pie" viewBox="0 0 220 220" role="img" aria-label="Sector allocation pie chart">
                {pieSegments.map((segment) => {
                  const isHovered = hoveredSector === segment.sector
                  const isLocked = lockedSector === segment.sector
                  const isActive = isHovered || isLocked
                  const isDimmed = activeSector != null && !isActive
                  const midAngle = (segment.startAngle + segment.endAngle) / 2
                  const labelRadius = 60
                  const labelX = 110 + (labelRadius * Math.cos(midAngle - (Math.PI / 2)))
                  const labelY = 110 + (labelRadius * Math.sin(midAngle - (Math.PI / 2)))

                  return (
                    <g key={segment.sector}>
                      <path
                        d={describePieSlice(segment.startAngle, segment.endAngle)}
                        fill={segment.color}
                        stroke="rgba(9, 13, 19, 0.88)"
                        strokeWidth={isActive ? '1.8' : '0.8'}
                        opacity={isDimmed ? 0.26 : 1}
                        className="sector-slice"
                        onMouseEnter={() => setHoveredSector(segment.sector)}
                        onMouseLeave={() => setHoveredSector(null)}
                        onClick={() => handleSectorActivate(segment.sector)}
                      />
                      {segment.weight >= 0.06 ? (
                        <text x={labelX} y={labelY} textAnchor="middle" dominantBaseline="middle" className="sector-pie-label" pointerEvents="none">
                          {abbreviateSectorLabel(segment.sector)}
                        </text>
                      ) : null}
                    </g>
                  )
                })}
              </svg>
            ) : (
              <div className="empty-state-panel compact-empty-state">
                <p className="empty-state-title">No positions available for sector breakdown.</p>
              </div>
            )}
          </div>

          <div>
            <div className="section-header-inline sector-list-header">
              <div>
                <p className="panel-label">Diversification by Sector</p>
              </div>
            </div>
            {sectorAllocation.length ? (
              <div className="sector-legend">
                {sectorAllocation.map((item) => (
                  <div
                    className={`sector-row${selectedSector === item.sector ? ' active' : ''}${lockedSector === item.sector ? ' locked' : ''}`}
                    key={item.sector}
                    onMouseEnter={() => setHoveredSector(item.sector)}
                    onMouseLeave={() => setHoveredSector(null)}
                    onClick={() => handleSectorActivate(item.sector)}
                  >
                    <span className="sector-name"><i className="legend-swatch" style={{ background: item.color }} /> {item.sector}</span>
                    <span
                      className="sector-badge"
                      style={{
                        color: `hsl(145 45% ${72 - (item.intensity * 18)}%)`,
                      }}
                    >
                      {(item.weight * 100).toFixed(1)}%
                    </span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>

          <div>
            <div className="section-header-inline sector-list-header">
              <div>
                <p className="panel-label">{selectedSector ? `${selectedSector} Holdings` : 'Sector Holdings'}</p>
              </div>
              {lockedSector ? <p className="helper">Locked on {lockedSector}</p> : <p className="helper">No sector locked</p>}
            </div>
            <div className="summary-card strategy-summary-card dashboard-edit-summary-card">
              <p className="stat-label">Draft Capital Check</p>
              <p className={`summary-value ${remainingCapital < 0 ? 'negative-text' : 'positive-text'}`}>{formatMoney(remainingCapital)}</p>
              <p className="helper">Remaining capital after edits · Leverage {formatNumber(leverageRatio, 2)}x</p>
            </div>
            {selectedSectorPositions.length ? (
              <div className="list-table">
                {selectedSectorPositions.map((position, index) => (
                  <div className="list-row dashboard-edit-row" key={`${selectedSector}-${position.symbol}-${index}`}>
                    <input className="path-input dashboard-edit-symbol" value={String(position.symbol)} onChange={(event) => updateSelectedSectorHolding(index, 'symbol', event.target.value)} placeholder="Ticker" />
                    <input className="path-input dashboard-edit-value" inputMode="decimal" value={String(position.market_value)} onChange={(event) => updateSelectedSectorHolding(index, 'market_value', event.target.value)} placeholder="Market value" />
                    <span>{formatPct(editedNetCapital > 0 ? (Number(position.market_value) / editedNetCapital) * 100 : 0)}</span>
                    <button className="secondary-button" type="button" onClick={() => removeSelectedSectorHolding(index)}>Remove</button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state-panel compact-empty-state">
                <p className="empty-state-title">Hover or click a sector to inspect its holdings.</p>
              </div>
            )}
            {selectedSector ? (
              <div className="actions dashboard-edit-actions">
                <button className="secondary-button" type="button" onClick={addSelectedSectorHolding}>Add holding</button>
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <div className="split-grid dashboard-bottom-grid">
        <section>
          <p className="panel-label">Drawdown</p>
          <div className="stat drawdown-card">
            <p className="summary-value negative-text">{formatPct(maxDrawdown)}</p>
            <p className="helper">Maximum drawdown from the visible portfolio path.</p>
          </div>
        </section>

        <section>
          <p className="panel-label">Money-Weighted Return</p>
          <div className="stat drawdown-card">
              <p className="summary-value">{formatPct(resolvedSummary.moneyWeightedReturnPct)}</p>
            <p className="helper">Modified Dietz style money-weighted return for the selected range.</p>
          </div>
        </section>
      </div>

      <section className="dashboard-bottom-grid">
        <p className="panel-label">Monthly Returns</p>
        {monthlyReturns.length && monthlyReturnsReliable ? (
          <div className="heatmap-grid">
            {monthlyReturns.map((item) => {
              const positive = item.returnPct >= 0
              return (
                <div className={`heatmap-cell ${positive ? 'heatmap-positive' : 'heatmap-negative'}`} key={item.month}>
                  <span>{item.month}</span>
                  <strong>{item.returnPct.toFixed(2)}%</strong>
                </div>
              )
            })}
          </div>
        ) : (
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">{monthlyReturnsEmptyState.title}</p>
            <p className="helper">{monthlyReturnsEmptyState.detail}</p>
          </div>
        )}
      </section>
    </article>
  )
}
