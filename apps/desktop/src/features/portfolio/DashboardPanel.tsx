import { useState } from 'react'
import type { DashboardAnalysis, DashboardRangeMetrics, ExposureAnalysis, ExposureFactorModelResponse, ImportAdmissionReviewDispositionV1, ImportAdmissionSummaryV1, ImportedStatementImporter } from './types'
import { investorEconomicsBaseReason } from './investorEconomics'
import { clonePortfolioSnapshot } from './portfolioSnapshot'
import type { PortfolioSnapshot } from './workspaceTypes'
import type { PortfolioNodeKind } from './workspaceTypes'
import { RollingFactorLoadingsCard } from './RollingFactorLoadingsCard'

type RangeOption = '1M' | '3M' | 'YTD' | '1Y' | 'All'
type EditableHolding = { symbol: string; market_value: number; sector?: string | null }
type AdmissionFamily = 'cash' | 'identity' | 'positions' | 'nav'
type AdmissionDispositionChoice = ImportAdmissionReviewDispositionV1['disposition']

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

function formatAdmissionBadge(value: string | null | undefined) {
  return value ? value.replace(/_/g, ' ') : 'unavailable'
}

function formatAdmissionDispositionLabel(value: AdmissionDispositionChoice) {
  if (value === 'accepted_known_exception') return 'Accepted known exception'
  if (value === 'needs_source_correction') return 'Needs source correction'
  return 'Deferred'
}

function getAdmissionCheck(summary: ImportAdmissionSummaryV1 | null | undefined, family: AdmissionFamily) {
  const checkIds: Record<AdmissionFamily, string> = {
    cash: 'residual_cash_comparability',
    identity: 'symbol_security_identity_consistency',
    positions: 'parsed_position_market_value_comparability',
    nav: 'nav_market_value_comparability',
  }
  return summary?.checks.find((check) => check.check_id === checkIds[family]) ?? null
}

function buildAdmissionEvidenceSummary(check: NonNullable<ImportAdmissionSummaryV1['checks'][number]> & { status: Exclude<ImportAdmissionSummaryV1['checks'][number]['status'], 'pass'> }): ImportAdmissionReviewDispositionV1['evidence_summary'] {
  return {
    status: check.status,
    trust_impact: check.trust_impact,
    message: check.message,
    affected_fields: check.affected_fields ?? [],
    observed: check.observed ?? null,
    comparison: check.comparison ?? null,
    delta: check.delta ?? null,
    currency: check.currency ?? null,
  }
}

function isNonPassAdmissionCheck(check: NonNullable<ImportAdmissionSummaryV1['checks'][number]>): check is NonNullable<ImportAdmissionSummaryV1['checks'][number]> & { status: Exclude<ImportAdmissionSummaryV1['checks'][number]['status'], 'pass'> } {
  return check.status !== 'pass'
}

function renderAdmissionCheckRow(input: {
  summary: ImportAdmissionSummaryV1 | null | undefined
  family: AdmissionFamily
  label: string
  activeReviewCheckId: string | null
  reviewDraft: { disposition: AdmissionDispositionChoice; rationale: string }
  reviewError: string | null
  dispositions: Record<string, ImportAdmissionReviewDispositionV1>
  snapshotFingerprint: string
  admissionSummaryFingerprint: string
  onStartReview: (checkId: string) => void
  onCancelReview: () => void
  onDraftChange: (draft: { disposition: AdmissionDispositionChoice; rationale: string }) => void
  onSaveReview?: (disposition: ImportAdmissionReviewDispositionV1) => void | Promise<void>
}) {
  const { summary, family, label } = input
  const check = getAdmissionCheck(summary, family)
  const status = check?.status ?? 'unavailable'
  const trustImpact = check?.trust_impact ?? 'unavailable'
  const savedDisposition = check ? input.dispositions[check.check_id] : null
  const reviewable = Boolean(check && check.status !== 'pass')
  const isReviewing = Boolean(check && input.activeReviewCheckId === check.check_id)
  const stale = Boolean(savedDisposition && (savedDisposition.snapshot_fingerprint !== input.snapshotFingerprint || savedDisposition.admission_summary_fingerprint !== input.admissionSummaryFingerprint))
  const saveDisabled = !input.reviewDraft.rationale.trim()
  return (
    <div className="dashboard-admission-check-row" key={family}>
      <div>
        <p className="stat-label">{label}</p>
        <p className="helper">{check?.message ?? 'Evidence unavailable for this admission check.'}</p>
        {savedDisposition ? (
          <div className="dashboard-admission-review-metadata">
            <p className="helper">Review metadata: {formatAdmissionDispositionLabel(savedDisposition.disposition)} by {savedDisposition.reviewer_label} at {formatDateTimeLabel(savedDisposition.reviewed_at)}{stale ? ' (stale)' : ''}</p>
            <p className="helper">Rationale: {savedDisposition.rationale}</p>
          </div>
        ) : null}
        {isReviewing && check && isNonPassAdmissionCheck(check) ? (
          <form className="dashboard-admission-review-form" onSubmit={(event) => {
            event.preventDefault()
            const rationale = input.reviewDraft.rationale.trim()
            if (!rationale) return
            void input.onSaveReview?.({
              schema_version: 'import_admission_review_disposition_v1',
              check_id: check.check_id,
              disposition: input.reviewDraft.disposition,
              rationale,
              reviewed_at: new Date().toISOString(),
              reviewer_label: 'local reviewer',
              snapshot_fingerprint: input.snapshotFingerprint,
              admission_summary_fingerprint: input.admissionSummaryFingerprint,
              evidence_summary: buildAdmissionEvidenceSummary(check),
            })
          }}>
            <label>
              <span className="stat-label">Disposition</span>
              <select value={input.reviewDraft.disposition} onChange={(event) => input.onDraftChange({ ...input.reviewDraft, disposition: event.target.value as AdmissionDispositionChoice })}>
                <option value="accepted_known_exception">Accepted known exception</option>
                <option value="needs_source_correction">Needs source correction</option>
                <option value="deferred">Deferred</option>
              </select>
            </label>
            <label>
              <span className="stat-label">Rationale</span>
              <textarea value={input.reviewDraft.rationale} onChange={(event) => input.onDraftChange({ ...input.reviewDraft, rationale: event.target.value })} aria-label={`${label} review rationale`} />
            </label>
            {input.reviewError ? <p className="helper">{input.reviewError}</p> : null}
            <div className="dashboard-admission-review-actions">
              <button type="submit" className="secondary-button" disabled={saveDisabled}>Save review metadata</button>
              <button type="button" className="ghost-button" onClick={input.onCancelReview}>Cancel</button>
            </div>
          </form>
        ) : null}
      </div>
      <div className="dashboard-admission-check-status">
        <span className={`dashboard-snapshot-status dashboard-snapshot-status-${status === 'pass' ? 'success' : status === 'fail' ? 'error' : 'partial'}`}>{status}</span>
        <span className="helper">impact {formatAdmissionBadge(trustImpact)}</span>
        {reviewable && !isReviewing ? <button type="button" className="ghost-button" onClick={() => input.onStartReview(check!.check_id)}>Review exception</button> : null}
      </div>
    </div>
  )
}

function renderImportAdmissionCard(input: {
  summary: ImportAdmissionSummaryV1 | null | undefined
  dispositions: Record<string, ImportAdmissionReviewDispositionV1>
  snapshotFingerprint: string
  admissionSummaryFingerprint: string
  activeReviewCheckId: string | null
  reviewDraft: { disposition: AdmissionDispositionChoice; rationale: string }
  reviewError: string | null
  onStartReview: (checkId: string) => void
  onCancelReview: () => void
  onDraftChange: (draft: { disposition: AdmissionDispositionChoice; rationale: string }) => void
  onSaveReview?: (disposition: ImportAdmissionReviewDispositionV1) => void | Promise<void>
}) {
  const { summary } = input
  const tone = summary?.trust_level === 'verified'
    ? 'success'
    : summary?.trust_level === 'withheld'
      ? 'error'
      : 'partial'
  return (
    <section className="summary-card dashboard-admission-card dashboard-shell-section" aria-label="Import Admission">
      <div className="section-header-inline dashboard-snapshot-header dashboard-shell-section-header">
        <div className="dashboard-shell-title-block">
          <p className="panel-label">Import Admission</p>
          <h3>{formatAdmissionBadge(summary?.decision ?? 'unavailable')}</h3>
        </div>
        <span className={`dashboard-snapshot-status dashboard-snapshot-status-${tone}`}>{formatAdmissionBadge(summary?.trust_level)}</span>
      </div>
      <p className="helper">Read-only admission summary. Review metadata is local only and does not change admission, trust, or imported values.</p>
      <div className="dashboard-admission-check-list">
        {renderAdmissionCheckRow({ ...input, family: 'cash', label: 'Residual cash' })}
        {renderAdmissionCheckRow({ ...input, family: 'identity', label: 'Symbol identity' })}
        {renderAdmissionCheckRow({ ...input, family: 'positions', label: 'Position market value' })}
        {renderAdmissionCheckRow({ ...input, family: 'nav', label: 'NAV / market value' })}
      </div>
    </section>
  )
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
  activeNodeKind?: PortfolioNodeKind | null
  admissionSummary?: ImportAdmissionSummaryV1 | null
  admissionReviewDispositions?: Record<string, ImportAdmissionReviewDispositionV1>
  admissionSnapshotFingerprint?: string
  admissionSummaryFingerprint?: string
  importing?: boolean
  importError?: string | null
  lastImportedFileNames?: string[]
  restoredSession?: boolean
  onImportPortfolio?: () => void
  onAppendStatement?: () => void
  onClearImportedSession?: () => void
  onResetLocalDatabase?: () => void | Promise<void>
  onSaveAdmissionReviewDisposition?: (disposition: ImportAdmissionReviewDispositionV1) => void | Promise<void>
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

export function DashboardPanel({ result, exposureResult = null, factorModel = null, activeNodeKind = null, admissionSummary = null, admissionReviewDispositions = {}, admissionSnapshotFingerprint = 'import_snapshot:null', admissionSummaryFingerprint = 'import_admission_summary:null', importing = false, importError = null, lastImportedFileNames = [], restoredSession = false, onImportPortfolio, onAppendStatement, onClearImportedSession, onResetLocalDatabase, onSaveAdmissionReviewDisposition }: DashboardPanelProps) {
  const [activeReviewCheckId, setActiveReviewCheckId] = useState<string | null>(null)
  const [reviewDraft, setReviewDraft] = useState<{ disposition: AdmissionDispositionChoice; rationale: string }>({ disposition: 'accepted_known_exception', rationale: '' })
  const [reviewError, setReviewError] = useState<string | null>(null)
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
  const hasDashboardResult = Boolean(result && hasRichDashboardData(result))

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
        <RollingFactorLoadingsCard result={exposureResult} factorModel={factorModel} />

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

      </div>

      <div className="dashboard-shell-footer-notes">
        {loadedFilesLabel ? <p className="helper">{loadedFilesLabel}</p> : null}
        {restoredSession ? <p className="helper">Restored on launch</p> : null}
        {importError ? <p className="error">{importError}</p> : null}
      </div>
    </article>
  )
}
