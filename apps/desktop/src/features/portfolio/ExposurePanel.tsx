import type { DriftResult, ExposureAnalysis, ImportAdmissionSummaryV1 } from './types'
import { BenchmarkCorrelationTable } from './BenchmarkCorrelationTable'
import { CacheControlCard } from './CacheControlCard'
import { DataSourcesPanel } from './DataSourcesPanel'
import { ImportAdmissionReviewCard } from './ImportAdmissionReviewCard'
import { DriftBenchmarkPanel } from './DriftBenchmarkPanel'
import { FactorAttributionCard } from './FactorAttributionCard'
import { FactorDriftSummaryCard } from './FactorDriftSummaryCard'
import { IntraCorrelationHeatmap } from './IntraCorrelationHeatmap'
import { RollingCorrelationChart } from './RollingCorrelationChart'
import { CardShell } from '../../app/primitives/CardShell'
import { TrustBadge } from '../../app/primitives/TrustBadge'

type ExposurePanelProps = {
  result: ExposureAnalysis | null
  driftResult?: DriftResult | null
  driftError?: string | null
  driftBenchmark?: string
  onDriftBenchmarkChange?: (symbol: string) => void
  snapshotOptions?: Array<{ id: string; label: string }>
  selectedSnapshotId?: string
  snapshotExitOption?: { id: string; label: string }
  onSnapshotSelect?: (snapshotId: string) => void
  admissionSummary?: ImportAdmissionSummaryV1 | null
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
  driftError = null,
  driftBenchmark = 'SPY',
  onDriftBenchmarkChange,
  snapshotOptions = [],
  selectedSnapshotId = 'current',
  snapshotExitOption,
  onSnapshotSelect,
  admissionSummary = null,
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
        <DataSourcesPanel snapshot={result.snapshot ?? null} />

        <ImportAdmissionReviewCard summary={admissionSummary} />

        <CacheControlCard />

        <DriftBenchmarkPanel
          result={driftResult}
          error={driftError}
          benchmarkSymbol={driftBenchmark}
          onBenchmarkChange={(symbol) => { onDriftBenchmarkChange?.(symbol) }}
        />

        {/* Combined Benchmark Correlation card — rolling chart on top,
            multi-benchmark snapshot table below. Each child is rendered with
            noShell so they share a single outer CardShell. */}
        <CardShell
          title="Benchmark Correlation"
          badge={
            <TrustBadge
              type="synthetic"
              tooltip="Computed from current holdings applied to historical prices. Not verified broker return basis."
            />
          }
        >
          <RollingCorrelationChart rollingRisk={result.rolling_risk ?? []} noShell />
          <div
            style={{
              borderTop: 'var(--border-thin) solid var(--color-border-subtle)',
              margin: 'var(--space-xl) 0 var(--space-lg)',
            }}
          />
          <BenchmarkCorrelationTable snapshot={result.snapshot ?? null} noShell />
        </CardShell>

        <IntraCorrelationHeatmap snapshot={result.snapshot ?? null} />

        <FactorAttributionCard snapshot={result.snapshot ?? null} />

        <FactorDriftSummaryCard result={result} />

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
  )
}
