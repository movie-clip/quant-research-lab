import type { DriftResult, ExposureAnalysis } from './types'
import { DriftBenchmarkPanel } from './DriftBenchmarkPanel'
import { FactorAttributionCard } from './FactorAttributionCard'

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

type ConcentrationAvailabilityTone = 'trusted' | 'partial' | 'unavailable'

type ConcentrationMetric = {
  label: string
  value: string
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
  if (!result) {
    return (
      <article className="panel exposure-panel exposure-shell-frame">
        <div className="exposure-shell-heading">
          <p className="panel-label">Exposure</p>
          <h2>Look-Through Exposure Core</h2>
        </div>
        <p className="lead compact-lead">Import a portfolio from the Dashboard to review current ownership, sector composition, concentration, and benchmark-relative positioning.</p>
      </article>
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
        <DriftBenchmarkPanel
          result={driftResult}
          benchmarkSymbol={driftBenchmark}
          onBenchmarkChange={(symbol) => { onDriftBenchmarkChange?.(symbol) }}
        />

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

        <FactorAttributionCard snapshot={result.snapshot ?? null} />
      </div>
    </article>
  )
}
