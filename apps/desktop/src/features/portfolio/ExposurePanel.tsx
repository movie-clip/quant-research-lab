import { useMemo } from 'react'

import { DenseInsightStrip, type DenseInsightStripItem, type DenseInsightMarker } from './DenseInsightStrip'
import { DriftBenchmarkPanel } from './DriftBenchmarkPanel'
import type { DriftResult, ExposureAnalysis } from './types'

type ExposurePanelProps = {
  result: ExposureAnalysis | null
  driftResult?: DriftResult | null
  driftBenchmark?: string
  onDriftBenchmarkChange?: (symbol: string) => void
  snapshotOptions?: Array<{ id: string; label: string }>
  selectedSnapshotId?: string
  snapshotExitOption?: { id: string; label: string }
  onSnapshotSelect?: (snapshotId: string) => void
}

type SectorModuleState = {
  title: string
  items: Array<{ name: string; marketValue: number; weight: number }>
  basisNote: string
  coverageNote: string
  limitationNote: string | null
}

type BenchmarkPositioningTrust = 'verified' | 'degraded' | 'partial' | 'unavailable'

type BenchmarkPositioningRow = {
  symbol: string
  name: string
  portfolioWeight: number
  benchmarkWeight: number
  activeWeight: number
}

type BenchmarkPositioningModuleState = {
  trust: BenchmarkPositioningTrust
  benchmarkSymbol: string
  portfolioInBenchmarkWeight: number | null
  activeShare: number | null
  overweights: BenchmarkPositioningRow[]
  underweights: BenchmarkPositioningRow[]
  basisNote: string
  coverageNote: string
  limitationNote: string | null
}

type ConcentrationAvailabilityTone = 'trusted' | 'partial' | 'unavailable'

type ConcentrationMetric = {
  label: string
  value: string
}

function normalizeExposureMarker(marker: string): DenseInsightMarker {
  if (marker === 'trusted' || marker === 'partial' || marker === 'degraded' || marker === 'stale' || marker === 'withheld' || marker === 'unavailable') return marker
  return marker === 'verified' ? 'trusted' : 'unavailable'
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'Unavailable' : `$${value.toFixed(2)}`
}

function formatCompactMoney(value: number | null | undefined) {
  if (value == null) return 'Unavailable'
  if (Math.abs(value) >= 1000) return `$${(value / 1000).toFixed(2)}k`
  return formatMoney(value)
}

function formatPct(value: number | null | undefined) {
  return value == null ? 'Unavailable' : `${value.toFixed(2)}%`
}

function formatWeightPct(value: number | null | undefined) {
  return value == null ? 'Unavailable' : formatPct(value * 100)
}

function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? 'Unavailable' : value.toFixed(digits)
}

function buildConcentrationAvailabilityState(concentration: ExposureAnalysis['current_state_concentration'] | null | undefined): {
  label: 'available' | 'partial' | 'withheld'
  tone: ConcentrationAvailabilityTone
} {
  const summaryMetricCount = [
    concentration?.top_1_position_weight,
    concentration?.top_3_position_weight,
    concentration?.top_5_position_weight,
    concentration?.top_sector_weight,
    concentration?.top_3_sector_weight,
    concentration?.position_hhi,
    concentration?.sector_hhi,
    concentration?.effective_holdings,
  ].filter((value) => value != null).length
  const hasTopPositions = Boolean(concentration?.top_positions?.length)
  const hasTopSectors = Boolean(concentration?.top_sectors?.length)

  if (!summaryMetricCount && !hasTopPositions && !hasTopSectors) {
    return { label: 'withheld', tone: 'unavailable' }
  }

  if (summaryMetricCount === 8 && hasTopPositions && hasTopSectors) {
    return { label: 'available', tone: 'trusted' }
  }

  return { label: 'partial', tone: 'partial' }
}

function buildConcentrationSummaryMetrics(concentration: ExposureAnalysis['current_state_concentration'] | null | undefined): ConcentrationMetric[] {
  return [
    concentration?.top_1_position_weight != null ? { label: 'Top 1 position', value: formatWeightPct(concentration.top_1_position_weight) } : null,
    concentration?.top_3_position_weight != null ? { label: 'Top 3 positions', value: formatWeightPct(concentration.top_3_position_weight) } : null,
    concentration?.top_5_position_weight != null ? { label: 'Top 5 positions', value: formatWeightPct(concentration.top_5_position_weight) } : null,
    concentration?.top_sector_weight != null ? { label: 'Top sector', value: formatWeightPct(concentration.top_sector_weight) } : null,
    concentration?.top_3_sector_weight != null ? { label: 'Top 3 sectors', value: formatWeightPct(concentration.top_3_sector_weight) } : null,
    concentration?.position_hhi != null ? { label: 'Position HHI', value: formatNumber(concentration.position_hhi, 3) } : null,
    concentration?.sector_hhi != null ? { label: 'Sector HHI', value: formatNumber(concentration.sector_hhi, 3) } : null,
    concentration?.effective_holdings != null ? { label: 'Effective holdings', value: formatNumber(concentration.effective_holdings, 2) } : null,
  ].filter((metric): metric is ConcentrationMetric => metric != null)
}

function formatCoverageState(status: ExposureAnalysis['exposure_availability']) {
  const state = status?.lookthrough_status ?? 'unavailable'
  if (state === 'live') return 'live'
  if (state === 'partial') return 'partial'
  return 'unavailable'
}

function buildLookthroughBasisNote(result: ExposureAnalysis) {
  const status = result.exposure_availability?.lookthrough_status ?? 'unavailable'
  if (status === 'live') return 'Basis: imported snapshot truth plus resolved ETF constituents.'
  if (status === 'partial') return 'Basis: imported snapshot truth plus resolved ETF constituents; unresolved ETFs stay partial.'
  return 'Basis: imported snapshot truth only; constituent look-through unavailable.'
}

function buildLookthroughCoverageNote(result: ExposureAnalysis) {
  const lookthrough = result.lookthrough
  const status = result.exposure_availability?.lookthrough_status ?? 'unavailable'
  if (status === 'unavailable') return 'Look-through coverage unavailable for this snapshot.'
  return `Look-through coverage ${formatWeightPct(lookthrough.coverage_ratio)} (${formatMoney(lookthrough.covered_market_value)} of ${formatMoney(lookthrough.portfolio_market_value)}).`
}

function buildLookthroughLimitationNote(result: ExposureAnalysis) {
  const status = result.exposure_availability?.lookthrough_status ?? 'unavailable'
  if (status === 'live') return null
  if (status === 'partial') {
    const uncovered = result.lookthrough.uncovered_positions
    return uncovered.length
      ? `Limitation: partial look-through leaves ${uncovered.join(', ')} unresolved.`
      : 'Limitation: partial look-through leaves constituent and sector reads incomplete.'
  }
  return 'Limitation: constituent ownership is withheld because look-through is unavailable.'
}

function buildSectorModuleState(result: ExposureAnalysis): SectorModuleState | null {
  const availability = result.exposure_availability
  const lookthroughStatus = availability?.lookthrough_status ?? 'unavailable'
  const lookthroughSectors = (result.lookthrough_sector_exposure ?? []).filter((item) => item.weight > 0)
  const holdingsSectors = (result.overview.sector_allocation ?? []).filter((item) => item.weight > 0)

  if (lookthroughStatus !== 'unavailable' && lookthroughSectors.length) {
    return {
      title: 'Sector Composition',
      items: lookthroughSectors.slice(0, 8).map((item) => ({ name: item.sector, marketValue: item.market_value, weight: item.weight })),
      basisNote: lookthroughStatus === 'live'
        ? 'Basis: sector mix uses look-through composition.'
        : 'Basis: sector mix uses look-through where resolved and imported snapshot truth elsewhere.',
      coverageNote: `Look-through coverage ${formatWeightPct(result.lookthrough.coverage_ratio)} (${lookthroughStatus}).`,
      limitationNote: lookthroughStatus === 'partial'
        ? 'Limitation: partial look-through can still shift sector mix.'
        : null,
    }
  }

  if (holdingsSectors.length) {
    return {
      title: 'Sector Composition',
      items: holdingsSectors.slice(0, 8).map((item) => ({ name: item.sector, marketValue: item.market_value, weight: item.weight })),
      basisNote: 'Basis: sector mix uses imported snapshot truth only.',
      coverageNote: 'Look-through coverage unavailable for sector mix.',
      limitationNote: lookthroughStatus === 'partial'
        ? 'Limitation: sector mix falls back to imported snapshot truth despite partial look-through elsewhere.'
        : 'Limitation: sector mix does not include constituent ETF unpacking.',
    }
  }

  return null
}

function getBenchmarkPositioningTrust(result: ExposureAnalysis): BenchmarkPositioningTrust {
  const availability = result.exposure_availability
  const overlapStatus = availability?.benchmark_overlap_status ?? 'unavailable'
  if (overlapStatus === 'unavailable') return 'unavailable'
  if (overlapStatus === 'partial') return 'partial'

  const holdingsSupport = result.run_metadata?.source_status?.benchmark_holdings ?? 'unavailable'
  if (holdingsSupport === 'verified') return 'verified'
  if (holdingsSupport === 'degraded') return 'degraded'
  return 'unavailable'
}

function normalizeBenchmarkPositioningRows(
  rows: ExposureAnalysis['market_overlap']['top_overweights'] | ExposureAnalysis['market_overlap']['top_underweights'] | undefined,
  direction: 'overweight' | 'underweight',
): BenchmarkPositioningRow[] {
  const filtered = (rows ?? []).filter((row) => {
    if (row.portfolio_weight == null || row.benchmark_weight == null || row.active_weight == null) return false
    if (direction === 'overweight') return row.active_weight > 0
    return row.active_weight < 0
  })

  return filtered
    .map((row) => ({
      symbol: row.symbol,
      name: row.name,
      portfolioWeight: row.portfolio_weight,
      benchmarkWeight: row.benchmark_weight,
      activeWeight: row.active_weight,
    }))
    .sort((left, right) => {
      const activeDelta = Math.abs(right.activeWeight) - Math.abs(left.activeWeight)
      if (activeDelta !== 0) return activeDelta
      const portfolioDelta = right.portfolioWeight - left.portfolioWeight
      if (portfolioDelta !== 0) return portfolioDelta
      const benchmarkDelta = right.benchmarkWeight - left.benchmarkWeight
      if (benchmarkDelta !== 0) return benchmarkDelta
      return left.symbol.localeCompare(right.symbol)
    })
}

function buildBenchmarkPositioningModuleState(result: ExposureAnalysis): BenchmarkPositioningModuleState {
  const trust = getBenchmarkPositioningTrust(result)
  const benchmarkSymbol = result.market_overlap?.benchmark_symbol ?? result.run_metadata?.reproducibility?.benchmark_symbol ?? 'benchmark'
  const overweights = normalizeBenchmarkPositioningRows(result.market_overlap?.top_overweights, 'overweight')
  const underweights = normalizeBenchmarkPositioningRows(result.market_overlap?.top_underweights, 'underweight')

  let basisNote = 'Basis: benchmark-relative positioning compares current composition with the selected benchmark composition.'
  let coverageNote = 'Benchmark-relative positioning unavailable for this snapshot.'
  let limitationNote: string | null = 'Limitation: no benchmark-relative cues are shown rather than implying neutral benchmark positioning.'

  if (trust === 'verified') {
    coverageNote = `Benchmark-relative positioning is available versus ${benchmarkSymbol}.`
    limitationNote = 'Limitation: current active bets only.'
  } else if (trust === 'degraded') {
    coverageNote = `Benchmark-relative positioning is degraded versus ${benchmarkSymbol}.`
    limitationNote = 'Limitation: incomplete benchmark composition can omit active bets.'
  } else if (trust === 'partial') {
    coverageNote = `Benchmark-relative positioning is partial versus ${benchmarkSymbol}.`
    limitationNote = result.lookthrough.uncovered_positions.length
      ? `Limitation: unresolved holdings (${result.lookthrough.uncovered_positions.join(', ')}) leave some active bets only partially mapped.`
      : 'Limitation: partial look-through leaves some active bets only partially mapped.'
  }

  return {
    trust,
    benchmarkSymbol,
    portfolioInBenchmarkWeight: result.market_overlap?.portfolio_in_benchmark_weight ?? null,
    activeShare: result.market_overlap?.active_share ?? null,
    overweights,
    underweights,
    basisNote,
    coverageNote,
    limitationNote,
  }
}

function buildExposureDenseInsightItems(
  result: ExposureAnalysis,
  sectorModule: SectorModuleState | null,
  benchmarkPositioningModule: BenchmarkPositioningModuleState | null,
): DenseInsightStripItem[] {
  const lookthroughStatus = result.exposure_availability?.lookthrough_status ?? 'unavailable'
  const items: DenseInsightStripItem[] = []

    items.push({
      title: 'Look-Through Coverage',
      headline: lookthroughStatus === 'live'
        ? `Look-through coverage is ${formatWeightPct(result.lookthrough.coverage_ratio)} of the portfolio.`
      : lookthroughStatus === 'partial'
        ? `Look-through coverage is ${formatWeightPct(result.lookthrough.coverage_ratio)} (partial).`
        : 'Look-through coverage unavailable.',
    facts: [
      `Covered market value ${formatMoney(result.lookthrough.covered_market_value)}.`,
      result.lookthrough.top_constituents[0]
        ? `${result.lookthrough.top_constituents[0].symbol} is the largest resolved constituent at ${formatWeightPct(result.lookthrough.top_constituents[0].portfolio_weight)}.`
        : 'Top constituent unavailable.',
    ],
    marker: lookthroughStatus === 'live' ? 'trusted' : lookthroughStatus === 'partial' ? 'partial' : 'unavailable',
  })

    items.push({
      title: 'Sector Composition',
      headline: sectorModule?.items[0]
        ? `${sectorModule.items[0].name} leads sector mix at ${formatWeightPct(sectorModule.items[0].weight)}.`
        : 'Sector composition unavailable.',
    facts: [
      sectorModule?.items[1] ? `${sectorModule.items[1].name} is next at ${formatWeightPct(sectorModule.items[1].weight)}.` : 'Second sector unavailable.',
      sectorModule?.basisNote ?? 'Sector basis unavailable.',
    ],
    marker: lookthroughStatus === 'live' && result.lookthrough_sector_exposure?.length ? 'trusted' : sectorModule ? 'partial' : 'unavailable',
  })

  if (benchmarkPositioningModule) {
    items.push({
      title: 'Benchmark Positioning',
      headline: benchmarkPositioningModule.activeShare != null
        ? `Active share is ${formatWeightPct(benchmarkPositioningModule.activeShare)} versus ${benchmarkPositioningModule.benchmarkSymbol}.`
        : 'Benchmark positioning is unavailable.',
      facts: [
        benchmarkPositioningModule.portfolioInBenchmarkWeight != null
          ? `Portfolio in benchmark ${formatWeightPct(benchmarkPositioningModule.portfolioInBenchmarkWeight)}.`
          : 'Portfolio in benchmark unavailable.',
        benchmarkPositioningModule.overweights[0]
          ? `${benchmarkPositioningModule.overweights[0].symbol} is the largest overweight at ${formatWeightPct(benchmarkPositioningModule.overweights[0].activeWeight)} active.`
          : 'Largest overweight unavailable.',
      ],
      marker: normalizeExposureMarker(benchmarkPositioningModule.trust),
    })
  }

  return items
}

function SummaryMetric({ label, value, detail }: { label: string; value: string; detail?: string }) {
  return (
    <div className="summary-card metric-card metric-card-neutral">
      <p className="stat-label">{label}</p>
      <p className="summary-value">{value}</p>
      {detail ? <p className="helper">{detail}</p> : null}
    </div>
  )
}

function UnavailablePanel({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="empty-state-panel compact-empty-state">
      <p className="empty-state-title">{title}</p>
      <p className="helper">{detail}</p>
    </div>
  )
}

export function ExposurePanel({
  result,
  driftResult = null,
  driftBenchmark = 'SPY',
  onDriftBenchmarkChange,
  snapshotOptions = [],
  selectedSnapshotId = 'current',
  snapshotExitOption,
  onSnapshotSelect,
}: ExposurePanelProps) {
  const sectorModule = useMemo(() => (result ? buildSectorModuleState(result) : null), [result])
  const benchmarkPositioningModule = useMemo(() => (result ? buildBenchmarkPositioningModuleState(result) : null), [result])
  const denseInsightItems = useMemo(
    () => (result ? buildExposureDenseInsightItems(result, sectorModule, benchmarkPositioningModule) : []),
    [benchmarkPositioningModule, result, sectorModule],
  )

  if (!result) {
    return (
      <>
        <DriftBenchmarkPanel
          result={driftResult}
          benchmarkSymbol={driftBenchmark}
          onBenchmarkChange={onDriftBenchmarkChange ?? (() => {})}
        />
        <article className="panel exposure-panel exposure-shell-frame">
          <div className="exposure-shell-heading">
            <p className="panel-label">Exposure</p>
            <h2>Look-Through Exposure Core</h2>
          </div>
          <p className="lead compact-lead">Import a portfolio from the Dashboard to review current ownership, sector composition, concentration, and benchmark-relative positioning.</p>
        </article>
      </>
    )
  }

  const lookthroughState = formatCoverageState(result.exposure_availability)
  const limitationNote = buildLookthroughLimitationNote(result)
  const topConstituents = (result.lookthrough.top_constituents ?? []).slice(0, 8)
  const concentration = result.current_state_concentration
  const concentrationAvailability = buildConcentrationAvailabilityState(concentration)
  const concentrationSummaryMetrics = buildConcentrationSummaryMetrics(concentration)
  const topPositions = (concentration?.top_positions ?? []).slice(0, 5)
  const topSectors = (concentration?.top_sectors ?? []).slice(0, 5)
  const hasBenchmarkPositioningRows = Boolean(
    benchmarkPositioningModule
    && (benchmarkPositioningModule.overweights.length || benchmarkPositioningModule.underweights.length),
  )
  const hasConcentrationFacts = Boolean(
    concentrationSummaryMetrics.length
    || topPositions.length
    || topSectors.length
    || concentration?.top_1_position_weight != null
    || concentration?.top_3_position_weight != null
    || concentration?.top_5_position_weight != null
    || concentration?.top_sector_weight != null
    || concentration?.top_3_sector_weight != null
    || concentration?.position_hhi != null
    || concentration?.sector_hhi != null
    || concentration?.effective_holdings != null,
  )

  return (
    <>
      <DriftBenchmarkPanel
        result={driftResult}
        benchmarkSymbol={driftBenchmark}
        onBenchmarkChange={onDriftBenchmarkChange ?? (() => {})}
      />
    <article className="panel exposure-panel exposure-shell-frame">
      <header className="section-header-inline exposure-header-row exposure-shell-header">
        <div className="exposure-shell-heading">
          <p className="panel-label">Exposure</p>
          <h2>Look-Through Exposure Core</h2>
        </div>
        <div className="exposure-shell-picker">
          {snapshotExitOption ? (
            <button className="secondary-button" type="button" onClick={() => onSnapshotSelect?.(snapshotExitOption.id)}>
              {snapshotExitOption.label}
            </button>
          ) : null}
          {snapshotOptions.length ? (
            <label className="exposure-snapshot-picker">
              <span className="field-label">Snapshot</span>
              <select className="path-input exposure-snapshot-select" value={selectedSnapshotId} onChange={(event) => onSnapshotSelect?.(event.target.value)}>
                {snapshotOptions.map((option) => <option key={option.id} value={option.id}>{option.label}</option>)}
              </select>
            </label>
          ) : null}
        </div>
      </header>

      <div className="exposure-shell-stack">
        {denseInsightItems.length ? (
          <DenseInsightStrip
            ariaLabel="Exposure Dense Insight Strip"
            heading="Dense Insight Strip"
            subheading="Current-state composition"
            className="exposure-dense-insight-strip exposure-shell-section"
            items={denseInsightItems}
          />
        ) : null}

        <section className="dashboard-bottom-grid exposure-primary-section exposure-shell-section exposure-top-path-section">
          <div className="section-header-inline sector-list-header exposure-section-header">
            <div className="panel-section-title-block"><p className="panel-label">Look-Through Summary</p></div>
            <p className="helper">Current-state composition only.</p>
          </div>
        <div className="dashboard-summary compact-summary-grid">
          <SummaryMetric label="Coverage state" value={lookthroughState} detail="Explicit look-through state." />
          <SummaryMetric label="Covered market value" value={formatMoney(result.lookthrough.covered_market_value)} detail="Imported market value resolved through look-through." />
          <SummaryMetric label="Coverage ratio" value={lookthroughState === 'unavailable' ? 'Unavailable' : formatWeightPct(result.lookthrough.coverage_ratio)} detail="Actual look-through coverage only." />
          <SummaryMetric label="Resolved constituents shown" value={String(topConstituents.length)} detail="Top resolved constituents shown." />
        </div>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">{buildLookthroughBasisNote(result)}</p>
          <p className="helper">{buildLookthroughCoverageNote(result)}</p>
          {limitationNote ? <p className="helper">{limitationNote}</p> : null}
        </div>
        {topConstituents.length ? (
          <section>
            <div className="section-header-inline sector-list-header exposure-section-header exposure-subsection-header">
              <div className="panel-section-title-block"><p className="panel-label">Top Constituents</p></div>
              <p className="helper">Current-state look-through only.</p>
            </div>
            <div className="list-table">
              {topConstituents.map((item) => (
                <div className="list-row" key={`lookthrough-${item.symbol}`}>
                  <span>{item.symbol}</span>
                  <span>{formatCompactMoney(item.effective_market_value)} · {formatWeightPct(item.portfolio_weight)}</span>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <UnavailablePanel title="Top constituents unavailable" detail="No defensible constituent list is shown because current look-through inputs did not resolve one." />
        )}
        </section>

        <section className="dashboard-bottom-grid exposure-primary-section exposure-shell-section">
          <div className="section-header-inline sector-list-header exposure-section-header">
            <div className="panel-section-title-block"><p className="panel-label">Sector Composition</p></div>
            <p className="helper">Look-through when available; otherwise imported snapshot truth.</p>
          </div>
        {sectorModule ? (
          <>
            <div className="empty-state-panel compact-empty-state">
              <p className="empty-state-title">{sectorModule.basisNote}</p>
              <p className="helper">{sectorModule.coverageNote}</p>
              {sectorModule.limitationNote ? <p className="helper">{sectorModule.limitationNote}</p> : null}
            </div>
            <div className="allocation-list">
              {sectorModule.items.map((item) => (
                <div className="allocation-row" key={`sector-${item.name}`}>
                  <div className="allocation-head">
                    <span>{item.name}</span>
                    <span>{formatWeightPct(item.weight)}</span>
                  </div>
                  <div className="allocation-bar">
                    <div className="allocation-fill" style={{ width: `${Math.max(item.weight * 100, 2)}%` }} />
                  </div>
                  <p className="helper">{formatCompactMoney(item.marketValue)}</p>
                </div>
              ))}
            </div>
          </>
        ) : (
          <UnavailablePanel title="Sector composition unavailable" detail="Sector output is withheld because neither defensible look-through sector composition nor holdings-level sector truth is available." />
        )}
        </section>

        <section className="dashboard-bottom-grid exposure-primary-section exposure-shell-section">
          <div className="section-header-inline sector-list-header exposure-section-header">
            <div className="panel-section-title-block"><p className="panel-label">Benchmark-Relative Positioning</p></div>
            <p className="helper">Current-state active bets only.</p>
          </div>
        {benchmarkPositioningModule ? (
          <>
            <div className="empty-state-panel compact-empty-state">
              <div className="benchmark-positioning-header-row">
                <p className="empty-state-title">{benchmarkPositioningModule.basisNote}</p>
                <span className={`dashboard-snapshot-status dashboard-snapshot-status-${benchmarkPositioningModule.trust === 'verified' ? 'trusted' : benchmarkPositioningModule.trust}`}>
                  {benchmarkPositioningModule.trust}
                </span>
              </div>
              <p className="helper">{benchmarkPositioningModule.coverageNote}</p>
              {benchmarkPositioningModule.limitationNote ? <p className="helper">{benchmarkPositioningModule.limitationNote}</p> : null}
            </div>
            <div className="dashboard-summary compact-summary-grid">
              <SummaryMetric label="Portfolio in benchmark" value={formatWeightPct(benchmarkPositioningModule.portfolioInBenchmarkWeight)} detail="Current portfolio weight mapped to benchmark constituents only." />
              <SummaryMetric label="Active share" value={formatWeightPct(benchmarkPositioningModule.activeShare)} detail="Current composition difference versus the selected benchmark." />
              <SummaryMetric label="Largest overweight" value={benchmarkPositioningModule.overweights[0] ? `${benchmarkPositioningModule.overweights[0].symbol} ${formatWeightPct(benchmarkPositioningModule.overweights[0].activeWeight)}` : 'Unavailable'} detail="Largest composition-based overweight with valid inputs." />
              <SummaryMetric label="Largest underweight" value={benchmarkPositioningModule.underweights[0] ? `${benchmarkPositioningModule.underweights[0].symbol} ${formatWeightPct(Math.abs(benchmarkPositioningModule.underweights[0].activeWeight))}` : 'Unavailable'} detail="Largest composition-based underweight with valid inputs." />
            </div>
            {hasBenchmarkPositioningRows ? (
              <div className="split-grid dashboard-bottom-grid">
                <section>
                  <div className="section-header-inline sector-list-header exposure-section-header exposure-subsection-header">
                    <div className="panel-section-title-block"><p className="panel-label">Top Overweights</p></div>
                    <p className="helper">Current-state composition deltas only.</p>
                  </div>
                  <div className="list-table">
                    {benchmarkPositioningModule.overweights.map((item) => (
                      <div className="list-row list-row-wide comparison-data-row comparison-tone-positive benchmark-positioning-row" key={`benchmark-overweight-${item.symbol}`}>
                        <span>{item.symbol}</span>
                        <span>{formatWeightPct(item.activeWeight)} active</span>
                        <span>{formatWeightPct(item.portfolioWeight)} portfolio vs {formatWeightPct(item.benchmarkWeight)} benchmark</span>
                      </div>
                    ))}
                  </div>
                </section>
                <section>
                  <div className="section-header-inline sector-list-header exposure-section-header exposure-subsection-header">
                    <div className="panel-section-title-block"><p className="panel-label">Top Underweights</p></div>
                    <p className="helper">Rows without complete inputs stay suppressed.</p>
                  </div>
                  {benchmarkPositioningModule.underweights.length ? (
                    <div className="list-table">
                      {benchmarkPositioningModule.underweights.map((item) => (
                        <div className="list-row list-row-wide comparison-data-row comparison-tone-negative benchmark-positioning-row" key={`benchmark-underweight-${item.symbol}`}>
                          <span>{item.symbol}</span>
                          <span>{formatWeightPct(Math.abs(item.activeWeight))} active</span>
                          <span>{formatWeightPct(item.portfolioWeight)} portfolio vs {formatWeightPct(item.benchmarkWeight)} benchmark</span>
                        </div>
                      ))}
                    </div>
                  ) : <UnavailablePanel title="Top underweights unavailable" detail="No benchmark constituents with valid underweight inputs are available for this snapshot." />}
                </section>
              </div>
            ) : (
              <UnavailablePanel title="Benchmark-relative positioning unavailable" detail="Current-state benchmark-relative cues are withheld until benchmark composition and mapped portfolio weights are defensible." />
            )}
          </>
        ) : null}
        </section>

        <section className="dashboard-bottom-grid exposure-primary-section exposure-shell-section">
          <div className="section-header-inline sector-list-header exposure-section-header">
            <div className="panel-section-title-block"><p className="panel-label">Concentration Pack</p></div>
            <p className="helper">Current-state composition only.</p>
          </div>
        {hasConcentrationFacts ? (
          <>
            <div className="concentration-pack-status-strip">
              <span className="backtest-source-badge concentration-pack-badge"><span className="concentration-pack-badge-label">Basis</span><span>Current-state concentration</span></span>
              <span className="backtest-source-badge concentration-pack-badge"><span className="concentration-pack-badge-label">Scope</span><span>Composition only</span></span>
              <span className={`dashboard-snapshot-status dashboard-snapshot-status-${concentrationAvailability.tone}`}><span className="concentration-pack-badge-label">Availability</span><span>{concentrationAvailability.label}</span></span>
            </div>
            {concentrationSummaryMetrics.length ? (
              <div className="dashboard-summary compact-summary-grid concentration-pack-summary-grid">
                {concentrationSummaryMetrics.map((metric) => (
                  <SummaryMetric key={metric.label} label={metric.label} value={metric.value} />
                ))}
              </div>
            ) : (
              <UnavailablePanel title="Concentration summary unavailable" detail="Current-state concentration metrics are withheld for this snapshot." />
            )}
            <div className="split-grid dashboard-bottom-grid concentration-pack-grid">
              <section>
                <div className="section-header-inline sector-list-header exposure-section-header exposure-subsection-header">
                  <div className="panel-section-title-block"><p className="panel-label">Top Positions</p></div>
                  <p className="helper">Top 5 current holdings.</p>
                </div>
                {topPositions.length ? (
                  <div className="list-table">
                    {topPositions.map((item, index) => (
                      <div className="list-row concentration-pack-row" key={`concentration-position-${item.name}`}>
                        <span className="concentration-pack-rank">{index + 1}</span>
                        <span className="concentration-pack-name">{item.name}</span>
                        <span className="concentration-pack-weight">{formatWeightPct(item.weight)}</span>
                        <span className="concentration-pack-value">{formatCompactMoney(item.market_value)}</span>
                      </div>
                    ))}
                  </div>
                ) : <UnavailablePanel title="Top positions unavailable" detail="No imported holdings concentration list is available for this snapshot." />}
              </section>
              <section>
                <div className="section-header-inline sector-list-header exposure-section-header exposure-subsection-header">
                  <div className="panel-section-title-block"><p className="panel-label">Top Sectors</p></div>
                  <p className="helper">Top 5 current sectors.</p>
                </div>
                {topSectors.length ? (
                  <div className="list-table">
                    {topSectors.map((item, index) => (
                      <div className="list-row concentration-pack-row" key={`concentration-sector-${item.name}`}>
                        <span className="concentration-pack-rank">{index + 1}</span>
                        <span className="concentration-pack-name">{item.name}</span>
                        <span className="concentration-pack-weight">{formatWeightPct(item.weight)}</span>
                        <span className="concentration-pack-value">{formatCompactMoney(item.market_value)}</span>
                      </div>
                    ))}
                  </div>
                ) : <UnavailablePanel title="Top sectors unavailable" detail="No current-state sector concentration list is available for this snapshot." />}
              </section>
            </div>
          </>
        ) : (
          <UnavailablePanel title="Concentration read unavailable" detail="Current-state concentration facts are unavailable for this snapshot, so the module is withheld rather than filled with estimates." />
        )}
        </section>
      </div>
    </article>
    </>
  )
}
