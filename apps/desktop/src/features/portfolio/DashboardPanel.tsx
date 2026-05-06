import type { ReactNode } from 'react'
import type { DashboardAnalysis, DashboardRangeMetrics, ExposureAnalysis, ExposureFactorModelResponse, ImportedStatementImporter } from './types'
import { DenseInsightStrip, type DenseInsightMarker, type DenseInsightStripItem } from './DenseInsightStrip'
import { investorEconomicsBaseReason } from './investorEconomics'
import { clonePortfolioSnapshot } from './portfolioSnapshot'
import type { PortfolioSnapshot } from './workspaceTypes'
import type { PortfolioNodeKind } from './workspaceTypes'

type RangeOption = '1M' | '3M' | 'YTD' | '1Y' | 'All'
type EditableHolding = { symbol: string; market_value: number; sector?: string | null }
type DashboardTrustTone = DenseInsightMarker
type DashboardHighlightModule = DenseInsightStripItem
type TrustPathKey = 'benchmark_relative_path' | 'factor_model_path' | 'benchmark_path'
type ExplicitTrustPathValue = 'verified_adjusted_close' | 'degraded_unverified_return_basis' | 'unavailable'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function readExplicitTrustPath(sectionTrust: unknown, key: TrustPathKey): ExplicitTrustPathValue | null {
  if (!isRecord(sectionTrust) || !(key in sectionTrust)) return null
  const value = sectionTrust[key]
  if (value === 'verified_adjusted_close' || value === 'degraded_unverified_return_basis' || value === 'unavailable') return value
  return null
}

function readDiagnosticsTrustPath(exposureResult: ExposureAnalysis, key: 'benchmark_relative_path' | 'factor_model_path'): ExplicitTrustPathValue | null {
  return readExplicitTrustPath(exposureResult.diagnostics_run_metadata?.section_trust, key)
}

function readDashboardTrustPath(result: DashboardAnalysis | null, key: 'benchmark_path'): ExplicitTrustPathValue | null {
  return readExplicitTrustPath(result?.run_metadata?.section_trust, key)
}

function trustToneFromPath(path: ExplicitTrustPathValue | null): DashboardTrustTone {
  if (path === 'verified_adjusted_close') return 'trusted'
  if (path === 'degraded_unverified_return_basis') return 'degraded'
  return 'unavailable'
}

function readStatisticalFactorModel(source: unknown) {
  return isRecord(source) ? source : null
}

function readFactorSnapshot(source: unknown) {
  const model = readStatisticalFactorModel(source)
  return Array.isArray(model?.current_factor_snapshot) ? model.current_factor_snapshot : []
}

function readFactorStatus(source: unknown) {
  const model = readStatisticalFactorModel(source)
  return typeof model?.status === 'string' && model.status.trim() ? model.status : null
}

function readFactorExposures(exposureResult: ExposureAnalysis) {
  return Array.isArray(exposureResult.factor_exposures) ? exposureResult.factor_exposures : []
}

function readStressScenarios(exposureResult: ExposureAnalysis) {
  return Array.isArray(exposureResult.stress_scenarios) ? exposureResult.stress_scenarios : []
}

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'n/a' : `$${value.toFixed(2)}`
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'n/a' : value.toFixed(digits)
}

function formatWholePct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${Math.round(value)}%`
}

function formatWeightPct(value: number | null | undefined) {
  return value == null ? 'n/a' : formatWholePct(value * 100)
}

function formatSignedLoading(value: number | null | undefined) {
  if (value == null) return 'n/a'
  return `${value >= 0 ? '+' : ''}${value.toFixed(2)}`
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

function formatDateLabel(value: string | null | undefined) {
  if (!value) return null
  const [year, month, day] = value.split('-')
  if (!year || !month || !day) return value
  return `${month}/${day}/${year.slice(2)}`
}

function formatLoadedFilesLabel(statementCount: number, loadedStatementsLabel: string | null) {
  if (!loadedStatementsLabel) return null
  return `${statementCount > 1 ? 'Loaded statements' : 'Loaded file'}: ${loadedStatementsLabel}`
}

function formatDateTimeLabel(value: string | null | undefined) {
  if (!value) return 'Unavailable'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'UTC',
    timeZoneName: 'short',
  }).format(date)
}

function formatAsOfLabel(value: string | null | undefined) {
  const label = formatDateLabel(value)
  return label ?? 'Unavailable'
}

function formatCountLabel(value: number | null | undefined) {
  return value == null ? 'Unavailable' : String(value)
}

function formatUnavailableMoney(value: number | null | undefined) {
  return value == null ? 'Unavailable' : formatMoney(value)
}

function formatUnavailableText(value: string | null | undefined) {
  if (!value) return 'Unavailable'
  const trimmed = value.trim()
  return trimmed ? trimmed : 'Unavailable'
}

function formatSnapshotFreshnessLabel(importedAt: string | null | undefined) {
  if (!importedAt) return 'Imported timestamp unavailable'
  const importedMs = Date.parse(importedAt)
  if (Number.isNaN(importedMs)) return 'Imported timestamp unavailable'
  const ageMs = Date.now() - importedMs
  const staleThresholdMs = 1000 * 60 * 60 * 24 * 30
  return ageMs > staleThresholdMs ? 'Timestamp suggests stale import' : 'Timestamp within freshness window'
}

function buildSnapshotState(input: {
  result: DashboardAnalysis | null
  importing: boolean
  importError: string | null
  activeNodeKind: PortfolioNodeKind | null
  hasFieldGaps: boolean
}) {
  if (input.importing) {
    return {
      tone: 'loading' as const,
      title: 'Loading imported snapshot',
      detail: 'Imported snapshot truth appears when the active import finishes loading.',
    }
  }
  if (input.importError) {
    return {
      tone: 'error' as const,
      title: 'Import failed',
      detail: input.importError,
    }
  }
  if (!input.result) {
    return {
      tone: 'empty' as const,
      title: 'No imported snapshot loaded',
      detail: 'Import a broker statement to populate imported snapshot truth.',
    }
  }
  if (input.activeNodeKind && input.activeNodeKind !== 'imported_base' && input.activeNodeKind !== 'imported_snapshot') {
    return {
      tone: 'partial' as const,
      title: 'Imported snapshot not active here',
      detail: 'Imported snapshot truth stays tied to the imported snapshot. Open it to restore trusted orientation fields.',
    }
  }
  const importedAt = input.result.snapshot?.statements?.[0]?.imported_at ?? null
  const importedMs = importedAt ? Date.parse(importedAt) : Number.NaN
  const isStale = !Number.isNaN(importedMs) && (Date.now() - importedMs) > (1000 * 60 * 60 * 24 * 30)
  if (isStale) {
    return {
      tone: 'stale' as const,
      title: 'Imported snapshot may be stale',
      detail: 'Imported snapshot truth is still shown, but the timestamp is stale. Refresh before relying on orientation.',
    }
  }
  if (input.hasFieldGaps) {
    return {
      tone: 'partial' as const,
      title: 'Imported snapshot has partial anchors',
      detail: 'Imported snapshot truth is shown, and unsupported orientation fields stay explicitly unavailable.',
    }
  }
  return {
    tone: 'success' as const,
    title: 'Imported snapshot loaded',
    detail: 'Summary orientation reflects imported snapshot truth only.',
  }
}

function sumImportedCashBalances(cashBalances: PortfolioSnapshot['cashBalances'] | DashboardAnalysis['snapshot']['cash_balances'] | null | undefined) {
  if (!cashBalances) return null
  let hasValue = false
  const total = cashBalances.reduce((runningTotal, balance) => {
    const amount = 'amount' in balance
      ? balance.amount
      : balance.ending_cash
    if (amount == null || !Number.isFinite(amount)) return runningTotal
    hasValue = true
    return runningTotal + amount
  }, 0)
  return hasValue ? total : null
}

function buildTopHoldingLabel(snapshot: DashboardAnalysis['snapshot'] | null, overview: DashboardAnalysis['overview'] | null | undefined) {
  const sortedPositions = [...(snapshot?.positions ?? [])]
    .filter((position) => Number.isFinite(position.market_value))
    .sort((left, right) => right.market_value - left.market_value)
  return sortedPositions[0]?.symbol ?? overview?.top_positions?.[0]?.symbol ?? null
}

function buildBenchmarkUsedLabel(
  result: DashboardAnalysis | null,
  exposureResult: ExposureAnalysis | null,
  factorModel: ExposureFactorModelResponse | null,
) {
  void exposureResult
  void factorModel
  const dashboardBenchmark = result?.run_metadata?.reproducibility.benchmark_symbol?.trim()
  return dashboardBenchmark ? dashboardBenchmark : null
}

function buildReadinessState(input: {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
  importing: boolean
  importError: string | null
  activeNodeKind: PortfolioNodeKind | null
  snapshotTone: 'success' | 'loading' | 'empty' | 'partial' | 'stale' | 'error'
  snapshotImportedAt: string | null
  benchmarkUsed: string | null
}) {
  if (input.importing) {
    return {
      tone: 'loading' as const,
      freshness: { value: 'Loading freshness status', detail: 'Import timestamp is still loading.' },
      coverage: { value: 'Loading coverage status', detail: 'Look-through coverage will appear when exposure context loads.' },
      benchmark: { value: 'Loading benchmark status', detail: 'Benchmark-relative support will appear when dashboard history loads.' },
      overall: { value: 'Readiness pending', detail: 'Wait for imported snapshot truth and support states before relying on orientation.' },
    }
  }

  if (input.importError) {
    return {
      tone: 'error' as const,
      freshness: { value: 'Import failed', detail: 'Freshness cannot be established after a failed import.' },
      coverage: { value: 'Coverage unavailable', detail: 'Look-through coverage is unavailable until a valid import succeeds.' },
      benchmark: { value: 'Benchmark unavailable', detail: 'Benchmark-relative support is unavailable until a valid import succeeds.' },
      overall: { value: 'Readiness unavailable', detail: 'Dashboard readiness is unavailable because the import failed.' },
    }
  }

  if (!input.result) {
    return {
      tone: 'empty' as const,
      freshness: { value: 'No snapshot loaded', detail: 'Import a statement to establish freshness.' },
      coverage: { value: 'Coverage unavailable', detail: 'Look-through coverage appears only after an imported portfolio loads.' },
      benchmark: { value: 'Benchmark unavailable', detail: 'Benchmark-relative support appears only after imported history loads.' },
      overall: { value: 'Not ready', detail: 'Load an imported portfolio before relying on dashboard orientation.' },
    }
  }

  const lookthroughStatus = input.exposureResult?.exposure_availability?.lookthrough_status ?? 'unavailable'
  const benchmarkHistory = input.result.run_metadata?.source_status.benchmark_history ?? 'unavailable'
  const freshnessTone = input.snapshotTone === 'stale'
    ? 'stale'
    : input.snapshotImportedAt && formatSnapshotFreshnessLabel(input.snapshotImportedAt) === 'Timestamp within freshness window'
      ? 'success'
      : 'partial'

  const freshness = freshnessTone === 'success'
    ? { value: 'Fresh import timestamp', detail: 'Import timestamp is within the dashboard freshness window.' }
    : freshnessTone === 'stale'
      ? { value: 'Stale import timestamp', detail: 'Refresh before relying on dashboard interpretation.' }
      : { value: 'Freshness unavailable', detail: 'Imported timestamp is unavailable, so freshness cannot be confirmed.' }

  const coverage = lookthroughStatus === 'live'
    ? { value: 'Look-through coverage ready', detail: 'Look-through coverage is available for this imported snapshot.' }
    : lookthroughStatus === 'partial'
      ? { value: 'Look-through coverage partial', detail: 'Look-through coverage is partial for this imported snapshot.' }
      : { value: 'Look-through coverage unavailable', detail: 'Look-through coverage is unavailable; rely on imported snapshot truth only.' }

  const benchmark = benchmarkHistory === 'live_market_data_verified_adjusted_close'
    ? { value: 'Benchmark available', detail: `Benchmark-relative support is available for ${input.benchmarkUsed ?? 'this path'}.` }
    : benchmarkHistory === 'live_market_data_unverified_return_basis'
      ? { value: 'Benchmark degraded', detail: `Benchmark-relative support is degraded for ${input.benchmarkUsed ?? 'this path'}.` }
      : { value: 'Benchmark unavailable', detail: 'Benchmark-relative support is unavailable on the current path.' }

  if (input.activeNodeKind && input.activeNodeKind !== 'imported_base' && input.activeNodeKind !== 'imported_snapshot') {
    return {
      tone: 'partial' as const,
      freshness,
      coverage,
      benchmark,
      overall: { value: 'Trusted orientation paused', detail: 'Return to the imported snapshot to restore trusted orientation.' },
    }
  }

  if (input.snapshotTone === 'stale') {
    return {
      tone: 'stale' as const,
      freshness,
      coverage,
      benchmark,
      overall: { value: 'Refresh before confident analysis', detail: 'Imported snapshot truth is still visible, but the stale timestamp should be refreshed first.' },
    }
  }

  if (
    input.snapshotTone === 'partial'
    || lookthroughStatus !== 'live'
    || benchmarkHistory !== 'live_market_data_verified_adjusted_close'
  ) {
    return {
      tone: 'partial' as const,
      freshness,
      coverage,
      benchmark,
      overall: { value: 'Partially ready', detail: 'Use imported snapshot truth first; look-through or benchmark support is still partial, degraded, or unavailable.' },
    }
  }

  return {
    tone: 'success' as const,
    freshness,
    coverage,
    benchmark,
    overall: { value: 'Ready for a first pass', detail: 'Imported snapshot truth, freshness, look-through coverage, and benchmark support are aligned.' },
  }
}

function isDesktopSafeMode() {
  return typeof window !== 'undefined' && ('__TAURI_INTERNALS__' in window || '__TAURI__' in window)
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

function formatBrokerLabel(importer: ImportedStatementImporter) {
  if (importer === 'multi_broker') return 'Multi-Broker'
  return importer === 'freedom24' ? 'Freedom24' : 'Interactive Brokers'
}

function isImportedAnalysisContextActive(activeNodeKind: PortfolioNodeKind | null | undefined) {
  return !activeNodeKind || activeNodeKind === 'imported_base' || activeNodeKind === 'imported_snapshot'
}

function buildUnavailableHighlightsModule(title: string, detail: string, trust: DashboardTrustTone = 'unavailable'): DashboardHighlightModule {
  return {
    title,
    marker: trust,
    headline: trust === 'partial' ? 'Limited' : 'Unavailable',
    facts: [detail],
  }
}

function aggregateHighlightTrust(trusts: DashboardTrustTone[]) {
  const availableTrusts = trusts.filter(Boolean)
  if (!availableTrusts.length) return 'unavailable'
  if (availableTrusts.every((trust) => trust === 'unavailable')) return 'unavailable'
  if (availableTrusts.includes('withheld')) return 'withheld'
  if (availableTrusts.includes('stale')) return 'stale'
  if (availableTrusts.includes('degraded')) return 'degraded'
  if (availableTrusts.includes('partial')) return 'partial'
  if (availableTrusts.includes('unavailable')) return 'partial'
  return 'trusted'
}

function buildExposureHighlightsModule(input: {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
  importing: boolean
  importError: string | null
  activeNodeKind: PortfolioNodeKind | null
  snapshotTone: 'success' | 'loading' | 'empty' | 'partial' | 'stale' | 'error'
}): DashboardHighlightModule {
  if (input.importing) {
    return buildUnavailableHighlightsModule('Exposure Highlights', 'Exposure highlights appear when the imported analysis context finishes loading.')
  }
  if (input.importError) {
    return buildUnavailableHighlightsModule('Exposure Highlights', 'Exposure highlights are unavailable after a failed import.')
  }
  if (!input.result || !input.exposureResult) {
    return buildUnavailableHighlightsModule('Exposure Highlights', 'Exposure highlights require the current imported analysis context.')
  }
  if (!isImportedAnalysisContextActive(input.activeNodeKind)) {
    return buildUnavailableHighlightsModule('Exposure Highlights', 'Exposure highlights stay tied to the imported analysis context only. Return to the imported snapshot to restore them.', 'partial')
  }

  const lookthroughStatus = input.exposureResult.exposure_availability?.lookthrough_status ?? 'unavailable'
  const lookthroughCoverage = input.exposureResult.lookthrough?.coverage_ratio ?? null
  const lookthroughTopSector = input.exposureResult.lookthrough_sector_exposure?.[0] ?? null
  const snapshotTopSector = input.result.overview?.sector_allocation?.[0] ?? null
  const facts: string[] = []
  let headline: string | null = null

  if (lookthroughTopSector && lookthroughStatus !== 'unavailable') {
    headline = `${lookthroughTopSector.sector} leads at ${formatWeightPct(lookthroughTopSector.weight)}.`
    facts.push(
      lookthroughStatus === 'partial'
        ? `Look-through coverage ${formatWeightPct(lookthroughCoverage)} (partial).`
        : `Look-through coverage ${formatWeightPct(lookthroughCoverage)}.`,
    )
  } else if (snapshotTopSector) {
    headline = `${snapshotTopSector.sector} leads at ${formatWeightPct(snapshotTopSector.weight)}.`
    facts.push('Imported snapshot truth only; look-through coverage unavailable.')
  }

  if (!headline) {
    return buildUnavailableHighlightsModule('Exposure Highlights', 'Exposure highlights stay unavailable until explicit sector or look-through fields are present.')
  }

  const trust: DashboardTrustTone = input.snapshotTone === 'stale'
    ? 'stale'
    : lookthroughStatus === 'live'
      ? 'trusted'
      : lookthroughStatus === 'partial'
        ? 'partial'
        : 'partial'

  return {
    title: 'Exposure Highlights',
    marker: trust,
    headline,
    facts,
  }
}

function buildConcentrationHighlightsModule(input: {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
  importing: boolean
  importError: string | null
  activeNodeKind: PortfolioNodeKind | null
  snapshotTone: 'success' | 'loading' | 'empty' | 'partial' | 'stale' | 'error'
}): DashboardHighlightModule {
  if (input.importing) {
    return buildUnavailableHighlightsModule('Concentration Highlights', 'Concentration highlights appear when the imported analysis context finishes loading.')
  }
  if (input.importError) {
    return buildUnavailableHighlightsModule('Concentration Highlights', 'Concentration highlights are unavailable after a failed import.')
  }
  if (!input.result || !input.exposureResult) {
    return buildUnavailableHighlightsModule('Concentration Highlights', 'Concentration highlights require the current imported analysis context.')
  }
  if (!isImportedAnalysisContextActive(input.activeNodeKind)) {
    return buildUnavailableHighlightsModule('Concentration Highlights', 'Concentration highlights stay tied to the imported analysis context only. Return to the imported snapshot to restore them.', 'partial')
  }

  const concentration = input.exposureResult.current_state_concentration
  const topPosition = concentration?.top_positions?.[0] ?? null
  const topPositionWeight = concentration?.top_1_position_weight ?? topPosition?.weight ?? null
  const topThreeWeight = concentration?.top_3_position_weight ?? null
  const topFiveWeight = concentration?.top_5_position_weight ?? null
  const topSectorWeight = concentration?.top_sector_weight ?? null
  const topThreeSectorWeight = concentration?.top_3_sector_weight ?? null
  const positionHhi = concentration?.position_hhi ?? null
  const sectorHhi = concentration?.sector_hhi ?? null
  const effectiveHoldings = concentration?.effective_holdings ?? null
  let headline: string | null = null
  const facts: string[] = []

  if (topPosition && topPositionWeight != null) {
    headline = `${topPosition.name} is ${formatWeightPct(topPositionWeight)} of the book.`
    const topPositionFact = [
      topThreeWeight != null ? `Top 3 ${formatWeightPct(topThreeWeight)}` : null,
      topFiveWeight != null ? `Top 5 ${formatWeightPct(topFiveWeight)}` : null,
      topSectorWeight != null ? `top sector ${formatWeightPct(topSectorWeight)}` : null,
    ].filter(Boolean).join('; ')
    if (topPositionFact) facts.push(topPositionFact)
  }

  if (!headline && (topSectorWeight != null || topThreeSectorWeight != null)) {
    headline = topSectorWeight != null ? `Top sector is ${formatWeightPct(topSectorWeight)} of the book.` : `Top 3 sectors are ${formatWeightPct(topThreeSectorWeight)} of the book.`
  } else if (!headline && (positionHhi != null || sectorHhi != null)) {
    headline = positionHhi != null ? `Position HHI is ${formatNumber(positionHhi, 3)}.` : `Sector HHI is ${formatNumber(sectorHhi, 3)}.`
  }

  if (!facts.length) {
    const secondaryFact = [
      topThreeSectorWeight != null ? `Top 3 sectors ${formatWeightPct(topThreeSectorWeight)}` : null,
      positionHhi != null ? `position HHI ${formatNumber(positionHhi, 3)}` : null,
      sectorHhi != null ? `sector HHI ${formatNumber(sectorHhi, 3)}` : null,
      effectiveHoldings != null ? `effective holdings ${formatNumber(effectiveHoldings)}` : null,
    ].filter(Boolean).join('; ')
    if (secondaryFact) facts.push(`${secondaryFact}.`)
  }

  if (!headline) {
    return buildUnavailableHighlightsModule('Concentration Highlights', 'Concentration inputs are not defensible on the current imported-analysis path.')
  }

  const trust: DashboardTrustTone = input.snapshotTone === 'stale'
    ? 'stale'
    : topPositionWeight != null && effectiveHoldings != null
      ? 'trusted'
      : 'partial'

  return {
    title: 'Concentration Highlights',
    marker: trust,
    headline,
    facts,
  }
}

function buildBenchmarkRelativeTrust(input: {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis
}) {
  const overlapStatus = input.exposureResult.exposure_availability?.benchmark_overlap_status ?? 'unavailable'
  if (overlapStatus === 'unavailable') return 'unavailable' as const
  if (overlapStatus === 'partial') return 'partial' as const

  const diagnosticsPath = readDiagnosticsTrustPath(input.exposureResult, 'benchmark_relative_path')
  const dashboardPath = readDashboardTrustPath(input.result, 'benchmark_path')

  if (!diagnosticsPath || !dashboardPath || diagnosticsPath === 'unavailable' || dashboardPath === 'unavailable') return 'unavailable' as const
  if (diagnosticsPath === 'degraded_unverified_return_basis' || dashboardPath === 'degraded_unverified_return_basis') return 'degraded' as const
  if (diagnosticsPath === 'verified_adjusted_close' && dashboardPath === 'verified_adjusted_close') return 'trusted' as const
  return 'unavailable' as const
}

function buildBenchmarkInterpretation(symbol: string, overlapWeight: number | null, activeShare: number | null) {
  if (activeShare != null && overlapWeight != null) {
    if (activeShare >= 0.6 && overlapWeight <= 0.35) return `Mostly differentiated from ${symbol}.`
    if (activeShare <= 0.4) return `Portfolio stays fairly close to ${symbol}.`
    return `Portfolio is partly aligned with ${symbol}, but still meaningfully different.`
  }
  if (activeShare != null) {
    return activeShare >= 0.6 ? `Portfolio is meaningfully differentiated from ${symbol}.` : `Portfolio still behaves fairly close to ${symbol}.`
  }
  if (overlapWeight != null) {
    return overlapWeight >= 0.5 ? `A large share of holdings overlaps ${symbol}.` : `Only part of the portfolio overlaps ${symbol}.`
  }
  return 'Benchmark-relative interpretation is unavailable.'
}

function buildBenchmarkRelativeHighlightsModule(input: {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
  importing: boolean
  importError: string | null
  activeNodeKind: PortfolioNodeKind | null
  snapshotTone: 'success' | 'loading' | 'empty' | 'partial' | 'stale' | 'error'
}): DashboardHighlightModule {
  if (input.importing) {
    return buildUnavailableHighlightsModule('Benchmark-Relative Highlights', 'Benchmark-relative highlights appear when the imported analysis context finishes loading.')
  }
  if (input.importError) {
    return buildUnavailableHighlightsModule('Benchmark-Relative Highlights', 'Benchmark-relative highlights are unavailable after a failed import.')
  }
  if (!input.result || !input.exposureResult) {
    return buildUnavailableHighlightsModule('Benchmark-Relative Highlights', 'Benchmark-relative highlights require imported benchmark support.')
  }
  if (!isImportedAnalysisContextActive(input.activeNodeKind)) {
    return buildUnavailableHighlightsModule('Benchmark-Relative Highlights', 'Benchmark-relative highlights stay tied to the imported analysis context only. Return to the imported snapshot to restore them.', 'partial')
  }

  const trust = input.snapshotTone === 'stale' ? 'stale' : buildBenchmarkRelativeTrust({ result: input.result, exposureResult: input.exposureResult })
  const overlap = input.exposureResult.market_overlap
  const symbol = overlap?.benchmark_symbol ?? buildBenchmarkUsedLabel(input.result, input.exposureResult, null) ?? 'benchmark'

  if (trust === 'unavailable' || (!overlap?.overlap_weight && !overlap?.active_share && overlap?.overlap_weight !== 0 && overlap?.active_share !== 0)) {
    return buildUnavailableHighlightsModule('Benchmark-Relative Highlights', 'Benchmark-relative support is unavailable on the current imported-analysis path.')
  }

  return {
    title: 'Benchmark-Relative Highlights',
    marker: trust,
    headline: buildBenchmarkInterpretation(symbol, overlap?.overlap_weight ?? null, overlap?.active_share ?? null),
    facts: [
      `${[
        overlap?.overlap_weight != null ? `Overlap with ${symbol} ${formatWeightPct(overlap.overlap_weight)}` : null,
        overlap?.active_share != null ? `active share ${formatWeightPct(overlap.active_share)}` : null,
      ].filter(Boolean).join('; ')}.`,
    ],
  }
}

type DashboardHeadline = { headline: string; facts: string[] }

function buildRiskHeadline(input: { exposureResult: ExposureAnalysis; benchmarkUsed: string | null }): { trust: DashboardTrustTone; item: DashboardHeadline } {
  const benchmarkPath = readDiagnosticsTrustPath(input.exposureResult, 'benchmark_relative_path')
  const trackingError = input.exposureResult.relative_risk?.tracking_error_pct ?? null
  const drawdown = input.exposureResult.volatility_regime?.snapshot?.current_drawdown_pct ?? null
  const riskSummary = input.exposureResult.risk_summary
  const symbol = riskSummary?.benchmark_symbol ?? input.benchmarkUsed ?? 'benchmark'

  const trust = trustToneFromPath(benchmarkPath)
  if (trust === 'unavailable') {
    return {
      trust,
      item: {
        headline: 'Risk headline unavailable.',
        facts: ['No defensible imported-analysis risk headline is available here.'],
      },
    }
  }

  if (drawdown != null && trackingError != null) {
    return {
      trust,
      item: {
        headline: `Current drawdown is ${formatPct(drawdown)} and tracking error is ${formatPct(trackingError)} versus ${symbol}.`,
        facts: ['Historical risk path follows the current imported-analysis diagnostics context.'],
      },
    }
  }
  if (riskSummary?.portfolio_beta != null) {
    return {
      trust,
      item: {
        headline: `Portfolio beta is ${formatNumber(riskSummary.portfolio_beta)} versus ${symbol}.`,
        facts: riskSummary.portfolio_volatility_pct != null ? [`Portfolio volatility ${formatPct(riskSummary.portfolio_volatility_pct)}.`] : [],
      },
    }
  }
  if (trackingError != null) {
    return {
      trust,
      item: {
        headline: `Tracking error is ${formatPct(trackingError)} versus ${symbol}.`,
        facts: [],
      },
    }
  }

  return {
    trust: 'unavailable',
    item: {
      headline: 'Risk headline unavailable.',
      facts: ['No defensible imported-analysis risk headline is available here.'],
    },
  }
}

function buildFactorHeadline(input: { exposureResult: ExposureAnalysis; factorModel: ExposureFactorModelResponse | null }): { trust: DashboardTrustTone; item: DashboardHeadline } {
  const factorPath = readDiagnosticsTrustPath(input.exposureResult, 'factor_model_path')
  const resolvedFactorSnapshot = readFactorSnapshot(input.factorModel?.statistical_factor_model)
  const factorSnapshot = resolvedFactorSnapshot.length
    ? resolvedFactorSnapshot
    : readFactorSnapshot(input.exposureResult.statistical_factor_model)
  const factorStatus = readFactorStatus(input.factorModel?.statistical_factor_model)
    ?? readFactorStatus(input.exposureResult.statistical_factor_model)
  const preferredSnapshots = factorSnapshot.filter((item) => item.latest_loading != null)
  const nonMarketSnapshots = preferredSnapshots.filter((item) => item.category !== 'market')
  const selectedSnapshot = [...(nonMarketSnapshots.length ? nonMarketSnapshots : preferredSnapshots)]
    .sort((left, right) => Math.abs((right.latest_loading ?? 0)) - Math.abs((left.latest_loading ?? 0)))[0] ?? null

  let trust = trustToneFromPath(factorPath)
  if (trust === 'trusted' && factorStatus && factorStatus !== 'ok') trust = 'partial'
  if (trust === 'unavailable') {
    return {
      trust,
      item: {
        headline: 'Factor headline unavailable.',
        facts: ['No defensible imported-analysis factor headline is available here.'],
      },
    }
  }

  if (selectedSnapshot?.latest_loading != null) {
    return {
      trust,
      item: {
        headline: `${selectedSnapshot.label} is the strongest modeled tilt at ${formatSignedLoading(selectedSnapshot.latest_loading)} loading.`,
        facts: selectedSnapshot.description ? [selectedSnapshot.description] : [],
      },
    }
  }

  const factorExposures = readFactorExposures(input.exposureResult).filter((item) => item.exposure != null)
  const currentStateFactors = factorExposures.filter((item) => item.basis === 'current_state')
  const selectedFactor = [...(currentStateFactors.length ? currentStateFactors : factorExposures)]
    .sort((left, right) => Math.abs((right.exposure ?? 0)) - Math.abs((left.exposure ?? 0)))[0] ?? null

  if (selectedFactor?.exposure != null) {
    return {
      trust,
      item: {
        headline: `${selectedFactor.factor} is the strongest available tilt at ${formatSignedLoading(selectedFactor.exposure)}.`,
        facts: selectedFactor.description ? [selectedFactor.description] : [],
      },
    }
  }

  return {
    trust: 'unavailable',
    item: {
      headline: 'Factor headline unavailable.',
      facts: ['No defensible imported-analysis factor headline is available here.'],
    },
  }
}

function buildStressHeadline(exposureResult: ExposureAnalysis): { trust: DashboardTrustTone; item: DashboardHeadline } {
  const diagnosticsStatus = exposureResult.availability?.status ?? 'unavailable'
  const factorPath = readDiagnosticsTrustPath(exposureResult, 'factor_model_path')
  const scenarios = [...readStressScenarios(exposureResult)].filter((scenario) => scenario.estimated_return_pct != null)
    .sort((left, right) => Math.abs((right.estimated_return_pct ?? 0)) - Math.abs((left.estimated_return_pct ?? 0)))
  const selectedScenario = scenarios[0] ?? null

  const trust: DashboardTrustTone = diagnosticsStatus !== 'ok' ? 'unavailable' : trustToneFromPath(factorPath)

  if (selectedScenario?.estimated_return_pct != null) {
    return {
      trust,
      item: {
        headline: `${selectedScenario.name} is the clearest modeled stress at ${formatPct(selectedScenario.estimated_return_pct)}.`,
        facts: selectedScenario.description ? [selectedScenario.description] : [],
      },
    }
  }

  return {
    trust: diagnosticsStatus === 'ok' && factorPath === 'degraded_unverified_return_basis' ? 'degraded' : 'unavailable',
    item: {
      headline: 'Stress headline unavailable.',
      facts: ['No imported-analysis stress scenario is available on this path.'],
    },
  }
}

function buildWhatMattersHeadline(input: {
  risk: DashboardHeadline
  factor: DashboardHeadline
  stress: DashboardHeadline
  trust: DashboardTrustTone
  activeNodeKind: PortfolioNodeKind | null
}): DashboardHeadline {
  if (!isImportedAnalysisContextActive(input.activeNodeKind)) {
    return {
      headline: 'Imported diagnostics stay paused until the imported snapshot is active again.',
      facts: [],
    }
  }
  if (input.trust === 'unavailable') {
    return {
      headline: 'Imported diagnostics are still too limited for a defensible headline set.',
      facts: [],
    }
  }
  if (input.trust === 'degraded') {
    return {
      headline: 'The signal set is useful for orientation, but the current diagnostics path remains degraded.',
      facts: [],
    }
  }
  return {
    headline: `${input.risk.headline} ${input.factor.headline} ${input.stress.headline}`,
    facts: [],
  }
}

function buildRiskFactorStressHeadlinesModule(input: {
  result: DashboardAnalysis | null
  exposureResult: ExposureAnalysis | null
  factorModel: ExposureFactorModelResponse | null
  importing: boolean
  importError: string | null
  activeNodeKind: PortfolioNodeKind | null
  snapshotTone: 'success' | 'loading' | 'empty' | 'partial' | 'stale' | 'error'
  benchmarkUsed: string | null
}): DashboardHighlightModule {
  if (input.importing) {
    return buildUnavailableHighlightsModule('Risk / Factor / Stress Headlines', 'Risk, factor, and stress headlines appear when imported diagnostics finish loading.')
  }
  if (input.importError) {
    return buildUnavailableHighlightsModule('Risk / Factor / Stress Headlines', 'Risk, factor, and stress headlines are unavailable after a failed import.')
  }
  if (!input.result || !input.exposureResult) {
    return buildUnavailableHighlightsModule('Risk / Factor / Stress Headlines', 'Risk, factor, and stress headlines require the current imported analysis context.')
  }
  if (!isImportedAnalysisContextActive(input.activeNodeKind)) {
    return buildUnavailableHighlightsModule('Risk / Factor / Stress Headlines', 'Risk, factor, and stress headlines stay tied to the imported analysis context only. Return to the imported snapshot to restore them.', 'partial')
  }

  const riskHeadline = buildRiskHeadline({ exposureResult: input.exposureResult, benchmarkUsed: input.benchmarkUsed })
  const factorHeadline = buildFactorHeadline({ exposureResult: input.exposureResult, factorModel: input.factorModel })
  const stressHeadline = buildStressHeadline(input.exposureResult)
  const trust = input.snapshotTone === 'stale'
    ? 'stale'
    : aggregateHighlightTrust([riskHeadline.trust, factorHeadline.trust, stressHeadline.trust])

  return {
    title: 'Risk / Factor / Stress Headlines',
    marker: trust,
    headline: buildWhatMattersHeadline({
      risk: riskHeadline.item,
      factor: factorHeadline.item,
      stress: stressHeadline.item,
      trust,
      activeNodeKind: input.activeNodeKind,
    }).headline,
    facts: [riskHeadline.item.headline, factorHeadline.item.headline],
  }
}


function sumCashBalances(cashByCurrency: Record<string, number> | null | undefined) {
  if (!cashByCurrency) return 0
  return Object.values(cashByCurrency).reduce((total, amount) => total + (Number.isFinite(amount) ? amount : 0), 0)
}


function dashboardSourceLabel(status: string | undefined) {
  if (status === 'live') return 'Live market history'
  if (status === 'suppressed') return 'Suppressed unstable series'
  return 'Sample or reconstructed history'
}

function formatDashboardAuditLine(result: DashboardAnalysis | null) {
  const runMetadata = result?.run_metadata
  if (!runMetadata) return null

  const reproducibility = runMetadata.reproducibility
  const sectionTrust = runMetadata.section_trust ?? {
    portfolio_path: 'unavailable',
    benchmark_path: 'unavailable',
    monthly_returns_path: 'unavailable',
  }
  const effectiveWindow = reproducibility.history_start_date && reproducibility.history_end_date
    ? `${formatDateLabel(reproducibility.history_start_date)} to ${formatDateLabel(reproducibility.history_end_date)}`
    : 'History window unavailable'

  return `Audit: ${reproducibility.benchmark_symbol} · ${runMetadata.source_status.benchmark_history} · portfolio ${sectionTrust.portfolio_path} · benchmark ${sectionTrust.benchmark_path} · monthly ${sectionTrust.monthly_returns_path} · ${effectiveWindow} · dataset ${reproducibility.dataset_version}`
}

function formatDashboardReturnBasisRefusalLine(result: DashboardAnalysis | null, selectedRangeMetrics: DashboardRangeMetrics | null) {
  const runMetadata = result?.run_metadata
  if (!runMetadata || !selectedRangeMetrics) return null

  const benchmarkReturnRefused = selectedRangeMetrics.summary.benchmark_return_pct == null
  const excessReturnRefused = selectedRangeMetrics.summary.excess_return_pct == null
  const drawdownRefused = selectedRangeMetrics.max_drawdown_pct == null

  if (runMetadata.investor_economics_status.status !== 'withheld') return null
  if (!benchmarkReturnRefused && !excessReturnRefused && !drawdownRefused) return null

  const baseReason = investorEconomicsBaseReason(runMetadata.investor_economics_status)
  if (!baseReason) return null

  const partialUnlock = runMetadata.investor_economics_partial_unlock
  const exactSliceScalarAllowlist = partialUnlock?.exact_slice_scalar_allowlist ?? []
  const excessReturnPolicy = exactSliceScalarAllowlist.find(
    (item) => item.field === 'range_metrics[*].summary.excess_return_pct',
  )
  const benchmarkPolicy = exactSliceScalarAllowlist.find(
    (item) => item.field === 'range_metrics[*].summary.benchmark_return_pct',
  )
  const policyDetail = benchmarkPolicy?.runtime_enabled && excessReturnPolicy?.runtime_enabled === false
    ? ' Dashboard policy remains partial-unlock only: exact-slice benchmark return may appear only for the identical admitted slice with independently verified benchmark total-return proof, and excess return still requires the same identical admitted slice pair plus a future server-side runtime enablement.'
    : ''
  const derivationDetail = partialUnlock?.client_derivation_rule === 'server_side_scalar_only_no_daily_series_subtraction_equivalence'
    ? ' Clients must not treat daily-series subtraction or local derivation as an equivalent path.'
    : ''

  return `Refusals: benchmark return, excess return, and drawdown stay withheld outside the narrow allowlisted exact-slice contract. ${baseReason}${policyDetail}${derivationDetail}`
}

function hasRichDashboardData(result: DashboardAnalysis | null) {
  const performanceSeries = result?.performance_series ?? []
  const dailyStates = result?.daily_states ?? []
  return Boolean(result && (performanceSeries.length || dailyStates.length || result.source_status))
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
  const statementEndingNav = result.snapshot?.statement_totals?.ending_nav ?? null
  const dailyStates = result.daily_states ?? []
  const latestStateValue = dailyStates.length ? dailyStates[dailyStates.length - 1].total_portfolio_value : null
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
  detailEligible?: boolean
  activeNodeKind?: PortfolioNodeKind | null
  importing?: boolean
  importError?: string | null
  lastImportedFileNames?: string[]
  restoredSession?: boolean
  onImportPortfolio?: () => void
  onAppendStatement?: () => void
  onClearImportedSession?: () => void
  onResetLocalDatabase?: () => void | Promise<void>
  onOpenDetailedReview?: () => void
}

function formatLoadedStatements(result: DashboardAnalysis | null, fallbackFileNames: string[]) {
  const statements = result?.snapshot?.statements ?? []
  if (!statements.length) {
    return fallbackFileNames.length ? fallbackFileNames.join(', ') : null
  }

  return statements
    .map((statement) => {
      const sourcePath = statement.source_path
      if (!sourcePath) {
        return statement.statement_period || 'Imported statement'
      }
      return sourcePath.split(/[/\\]/).pop() || sourcePath
    })
    .join(', ')
}

function renderTrustedSnapshotCards(input: {
  snapshotBrokerLabel: string | null
  snapshotAccountId: string | null
  snapshotStatementPeriod: string | null
  snapshotAsOf: string
  snapshotImportedDetail?: string | null
  snapshotLoadedFilesLabel?: string | null
  snapshotPortfolioValue: number | null
  snapshotCashTotal: number | null
  snapshotImportedAt: string | null
  snapshotPositionsCount: number | null
  snapshotTopHolding: string | null
  snapshotTopSector: string | null
  benchmarkUsed: string | null
  snapshotImportedLabel: string
  snapshotFieldAvailable: boolean
}) {
  return (
    <div className="dashboard-snapshot-grid">
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Broker / importer</p>
        <p className="summary-value">{formatUnavailableText(input.snapshotBrokerLabel)}</p>
        <p className="helper">Account ID {formatUnavailableText(input.snapshotAccountId)}</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Statement period</p>
        <p className="summary-value">{formatUnavailableText(input.snapshotStatementPeriod)}</p>
        <p className="helper">As of {input.snapshotAsOf}</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Portfolio value / NAV</p>
        <p className="summary-value">{formatUnavailableMoney(input.snapshotPortfolioValue)}</p>
        <p className="helper">Imported snapshot truth</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Cash total</p>
        <p className="summary-value">{formatUnavailableMoney(input.snapshotCashTotal)}</p>
        <p className="helper">{formatSnapshotFreshnessLabel(input.snapshotImportedAt)}</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Positions count</p>
        <p className="summary-value">{formatCountLabel(input.snapshotPositionsCount)}</p>
        <p className="helper">Top holding {formatUnavailableText(input.snapshotTopHolding)}</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Top sector</p>
        <p className="summary-value">{formatUnavailableText(input.snapshotTopSector)}</p>
        <p className="helper">Imported snapshot truth only</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Benchmark used</p>
        <p className="summary-value">{formatUnavailableText(input.snapshotFieldAvailable ? input.benchmarkUsed : null)}</p>
        <p className="helper">Imported snapshot benchmark context</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Import / as-of timestamp</p>
        <p className="summary-value">{input.snapshotImportedLabel}</p>
        <p className="helper">As of {input.snapshotAsOf}</p>
      </div>
    </div>
  )
}

function renderReadinessCards(readinessStatus: ReturnType<typeof buildReadinessState>) {
  return (
    <div className="dashboard-readiness-grid">
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Freshness status</p>
        <p className="summary-value">{readinessStatus.freshness.value}</p>
        <p className="helper">{readinessStatus.freshness.detail}</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Look-through coverage status</p>
        <p className="summary-value">{readinessStatus.coverage.value}</p>
        <p className="helper">{readinessStatus.coverage.detail}</p>
      </div>
      <div className="summary-card dashboard-snapshot-card">
        <p className="stat-label">Benchmark availability status</p>
        <p className="summary-value">{readinessStatus.benchmark.value}</p>
        <p className="helper">{readinessStatus.benchmark.detail}</p>
      </div>
    </div>
  )
}

function renderDashboardHighlightsModule(module: DashboardHighlightModule) {
  return <DenseInsightStrip ariaLabel={module.title} items={[module]} className="dashboard-summary-highlight-strip" />
}

export function DashboardPanel({ result, exposureResult = null, factorModel = null, detailEligible = true, activeNodeKind = null, importing = false, importError = null, lastImportedFileNames = [], restoredSession = false, onImportPortfolio, onAppendStatement, onClearImportedSession, onResetLocalDatabase, onOpenDetailedReview }: DashboardPanelProps) {
  const snapshot = result?.snapshot ?? null
  const statement = snapshot?.statement ?? null
  const statements = snapshot?.statements ?? []

  const loadedStatementsLabel = formatLoadedStatements(result, lastImportedFileNames)
  const statementCount = statements.length || lastImportedFileNames.length
  const loadedFilesLabel = formatLoadedFilesLabel(statementCount, loadedStatementsLabel)
  const snapshotImportedAt = statement?.imported_at ?? statements[0]?.imported_at ?? null
  const snapshotAsOfDate = result?.run_metadata?.reproducibility.snapshot_as_of_date ?? statements[0]?.statement_period?.split(' - ')[1] ?? null
  const benchmarkUsed = buildBenchmarkUsedLabel(result, exposureResult, factorModel)
  const statementTotals = result?.snapshot?.statement_totals ?? null
  const snapshotPortfolioValueCandidate = statementTotals?.ending_nav
    ?? (statementTotals?.stock_total != null && statementTotals?.cash_total != null ? statementTotals.stock_total + statementTotals.cash_total : null)
    ?? null
  const snapshotCashTotalCandidate = statementTotals?.cash_total
    ?? sumImportedCashBalances(snapshot?.cash_balances)
    ?? sumCashBalances(result?.overview?.cash_by_currency)
    ?? null
  const snapshotPositionsCountCandidate = result?.overview?.positions_count ?? (snapshot?.positions?.length ?? null)
  const snapshotTopHoldingCandidate = buildTopHoldingLabel(snapshot, result?.overview)
  const snapshotTopSectorCandidate = result?.overview?.sector_allocation?.[0]?.sector ?? null
  const snapshotHasFieldGaps = Boolean(result) && [
    statement?.importer ?? null,
    statement?.account_id ?? null,
    snapshotPortfolioValueCandidate,
    snapshotCashTotalCandidate,
    snapshotPositionsCountCandidate,
    snapshotTopHoldingCandidate,
    snapshotTopSectorCandidate,
    benchmarkUsed,
    snapshotAsOfDate,
    snapshotImportedAt,
  ].some((value) => value == null || value === '')
  const snapshotStatus = buildSnapshotState({
    result,
    importing,
    importError,
    activeNodeKind,
    hasFieldGaps: snapshotHasFieldGaps,
  })
  const readinessStatus = buildReadinessState({
    result,
    exposureResult,
    importing,
    importError,
    activeNodeKind,
    snapshotTone: snapshotStatus.tone,
    snapshotImportedAt,
    benchmarkUsed,
  })
  const landingSnapshotDetail = activeNodeKind && activeNodeKind !== 'imported_base' && activeNodeKind !== 'imported_snapshot'
    ? 'Imported snapshot truth stays tied to the imported snapshot only.'
    : snapshotStatus.detail
  const snapshotFieldAvailable = snapshotStatus.tone !== 'empty' && snapshotStatus.tone !== 'error' && snapshotStatus.tone !== 'loading' && !(activeNodeKind && activeNodeKind !== 'imported_base' && activeNodeKind !== 'imported_snapshot')
  const snapshotPortfolioValue = snapshotFieldAvailable
    ? snapshotPortfolioValueCandidate
    : null
  const snapshotCashTotal = snapshotFieldAvailable ? snapshotCashTotalCandidate : null
  const snapshotPositionsCount = snapshotFieldAvailable ? snapshotPositionsCountCandidate : null
  const snapshotTopHolding = snapshotFieldAvailable ? snapshotTopHoldingCandidate : null
  const snapshotTopSector = snapshotFieldAvailable ? snapshotTopSectorCandidate : null
  const snapshotBrokerLabel = snapshotFieldAvailable && statement?.importer ? formatBrokerLabel(statement.importer) : null
  const snapshotAccountId = snapshotFieldAvailable ? statement?.account_id ?? null : null
  const snapshotStatementPeriod = snapshotFieldAvailable ? statement?.statement_period ?? null : null
  const snapshotImportedLabel = snapshotFieldAvailable ? formatDateTimeLabel(snapshotImportedAt) : 'Unavailable'
  const snapshotAsOf = snapshotFieldAvailable ? formatAsOfLabel(snapshotAsOfDate) : 'Unavailable'
  const snapshotLoadedFilesLabel = snapshotFieldAvailable ? loadedFilesLabel : null
  const snapshotImportedDetail = snapshotFieldAvailable
    ? `Imported ${snapshotImportedLabel}${statementCount > 1 ? ` · ${statementCount} statements combined` : ''}`
    : null
  const exposureHighlights = buildExposureHighlightsModule({
    result,
    exposureResult,
    importing,
    importError,
    activeNodeKind,
    snapshotTone: snapshotStatus.tone,
  })
  const concentrationHighlights = buildConcentrationHighlightsModule({
    result,
    exposureResult,
    importing,
    importError,
    activeNodeKind,
    snapshotTone: snapshotStatus.tone,
  })
  const benchmarkRelativeHighlights = buildBenchmarkRelativeHighlightsModule({
    result,
    exposureResult,
    importing,
    importError,
    activeNodeKind,
    snapshotTone: snapshotStatus.tone,
  })
  const riskFactorStressHeadlines = buildRiskFactorStressHeadlinesModule({
    result,
    exposureResult,
    factorModel,
    importing,
    importError,
    activeNodeKind,
    snapshotTone: snapshotStatus.tone,
    benchmarkUsed,
  })

  const hasDashboardResult = Boolean(result && hasRichDashboardData(result))
  const showHandoffButton = hasDashboardResult && detailEligible

  function handleOpenDetailedReview() {
    if (!showHandoffButton) return
    onOpenDetailedReview?.()
  }

  function renderHeaderActions() {
    if (!(onImportPortfolio || onAppendStatement || onClearImportedSession || onResetLocalDatabase)) return null

    return (
      <div className="dashboard-action-row">
        {onImportPortfolio ? <button className="secondary-button" onClick={onImportPortfolio} type="button">{importing ? 'Importing...' : loadedStatementsLabel ? 'Replace Import' : 'Import Portfolio'}</button> : null}
        {onAppendStatement ? <button className="secondary-button dashboard-append-button" onClick={onAppendStatement} type="button">{importing ? 'Importing...' : 'Add Statement'}</button> : null}
        {onClearImportedSession ? <button className="secondary-button dashboard-clear-button" onClick={onClearImportedSession} type="button">Clear Imported Session</button> : null}
        {onResetLocalDatabase ? <button className="secondary-button dashboard-clear-button" onClick={() => void onResetLocalDatabase()} type="button">Reset Local DB</button> : null}
      </div>
    )
  }

  function renderHandoffCard(): ReactNode {
    return (
      <section className="summary-card dashboard-guidance-card dashboard-guidance-card-accent dashboard-shell-section" aria-label="Next step">
        <p className="stat-label">Next step</p>
        <p className="summary-value dashboard-guidance-value">{showHandoffButton ? 'Continue in detailed review' : 'Detailed review unavailable here'}</p>
        <p className="helper">{showHandoffButton ? 'This shell stays summary-first. Use the handoff when you need deeper review.' : 'This shell stays summary-first, and detailed review is unavailable on this path.'}</p>
        {showHandoffButton ? (
          <div className="dashboard-health-handoff-row">
            <button className="primary-button" type="button" onClick={handleOpenDetailedReview}>Open detailed review</button>
          </div>
        ) : null}
      </section>
    )
  }

  return (
    <article className="panel dashboard-panel dashboard-shell-frame">
      <header className="section-header-inline dashboard-header-actions dashboard-shell-header">
        <div className="dashboard-shell-heading">
          <p className="panel-label">Dashboard</p>
          <h2>Account overview</h2>
        </div>
        {renderHeaderActions()}
      </header>

      <div className="dashboard-shell-stack">
        <section className="dashboard-snapshot-shell dashboard-shell-section" aria-label="Trusted Portfolio Snapshot">
          <div className="section-header-inline dashboard-snapshot-header dashboard-shell-section-header">
            <div className="dashboard-shell-title-block">
              <p className="panel-label">Trusted Portfolio Snapshot</p>
              <h3>{snapshotStatus.title}</h3>
            </div>
            <span className={`dashboard-snapshot-status dashboard-snapshot-status-${snapshotStatus.tone}`}>{snapshotStatus.tone}</span>
          </div>
          <p className="helper">{landingSnapshotDetail}</p>
          {renderTrustedSnapshotCards({
            snapshotBrokerLabel: hasDashboardResult ? snapshotBrokerLabel : null,
            snapshotAccountId: hasDashboardResult ? snapshotAccountId : null,
            snapshotStatementPeriod: hasDashboardResult ? snapshotStatementPeriod : null,
            snapshotAsOf: hasDashboardResult ? snapshotAsOf : 'Unavailable',
            snapshotImportedDetail: hasDashboardResult ? snapshotImportedDetail : null,
            snapshotLoadedFilesLabel: hasDashboardResult ? snapshotLoadedFilesLabel : null,
            snapshotPortfolioValue: hasDashboardResult ? snapshotPortfolioValue : null,
            snapshotCashTotal: hasDashboardResult ? snapshotCashTotal : null,
            snapshotImportedAt: hasDashboardResult ? snapshotImportedAt : null,
            snapshotPositionsCount: hasDashboardResult ? snapshotPositionsCount : null,
            snapshotTopHolding: hasDashboardResult ? snapshotTopHolding : null,
            snapshotTopSector: hasDashboardResult ? snapshotTopSector : null,
            benchmarkUsed: hasDashboardResult ? benchmarkUsed : null,
            snapshotImportedLabel: hasDashboardResult ? snapshotImportedLabel : 'Unavailable',
            snapshotFieldAvailable: hasDashboardResult && snapshotFieldAvailable,
          })}
        </section>

        <section className="summary-card dashboard-readiness-shell dashboard-shell-section" aria-label="Freshness And Coverage Readiness">
          <div className="section-header-inline dashboard-snapshot-header dashboard-shell-section-header">
            <div className="dashboard-shell-title-block">
              <p className="panel-label">Freshness And Coverage Readiness</p>
              <h3>{readinessStatus.overall.value}</h3>
            </div>
            <span className={`dashboard-snapshot-status dashboard-snapshot-status-${readinessStatus.tone}`}>{readinessStatus.tone}</span>
          </div>
          <p className="helper">{readinessStatus.overall.detail}</p>
          {renderReadinessCards(readinessStatus)}
        </section>

        <section className="dashboard-dense-insight-shell dashboard-shell-section" aria-label="Dense Insight Strip">
          <div className="section-header-inline dashboard-snapshot-header dashboard-shell-section-header">
            <div className="dashboard-shell-title-block">
              <p className="panel-label">Dense Insight Strip</p>
              <h3>Scan-first portfolio cues</h3>
            </div>
          </div>
          <div className="dashboard-summary-highlights-grid">
            {renderDashboardHighlightsModule(exposureHighlights)}
            {renderDashboardHighlightsModule(concentrationHighlights)}
            {renderDashboardHighlightsModule(benchmarkRelativeHighlights)}
            {renderDashboardHighlightsModule(riskFactorStressHeadlines)}
          </div>
        </section>

        {renderHandoffCard()}
      </div>

      <div className="dashboard-shell-footer-notes">
        {loadedFilesLabel ? <p className="helper">{loadedFilesLabel}</p> : null}
        {restoredSession ? <p className="helper">Restored on launch</p> : null}
        {importError ? <p className="error">{importError}</p> : null}
      </div>
    </article>
  )
}
