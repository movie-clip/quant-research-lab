import { useEffect, useMemo, useState } from 'react'

import { PersistedReplacementRankingBrowser } from './PersistedReplacementRankingBrowser'
import { PersistedEtfRankingConstructionBrowser } from './PersistedEtfRankingConstructionBrowser'
import { PersistedGenericRankingConstructionBrowser } from './PersistedGenericRankingConstructionBrowser'
import { buildAuthoritativeCurrentPortfolio } from './currentPortfolio'
import { ReplacementRankingReview } from '../portfolio/ReplacementRankingReview'
import { isDataQualityMonitorIdentity } from '../portfolio/types'
import type { BenchmarkTrendOverlayMonitorDefinitionEvaluationHistoryEntryArtifact, BenchmarkTrendOverlayMonitorDefinitionObservationArtifact, DataQualityMonitorEvidenceSummary, DataQualityMonitorDefinitionEvaluationHistoryEntryArtifact, DataQualityMonitorDefinitionObservationArtifact, MonitoringResearchHandoff, MonitorDefinitionActiveAlertEpisodeInboxResponse, MonitorDefinitionActiveAlertEpisodeInboxRow, MonitorDefinitionAlertEpisodeHistoryResponse, MonitorDefinitionAlertEpisodeHistoryRow, MonitorDefinitionAlertReviewTimelineHistoryRow, MonitorDefinitionAlertReviewTimelineObservationRow, MonitorDefinitionAlertReviewTimelineResponse, MonitorDefinitionEvaluationHistoryEntryResponse, MonitorDefinitionObservationArtifact, MonitorDefinitionRecoveredAlertReviewQueueRow, PortfolioBaselineView, HypotheticalReplayResponse, PortfolioAllocationBacktestResponse, PortfolioDiagnosticsTopCallout, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { ActiveThesisArtifact, CandidateImprovementDraftArtifact, ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, MonitorDefinitionAlertReviewSessionState, PersistedConstructionArtifactWorkspaceReview, PersistedOptimizerHandoffWorkspaceReview, PortfolioSnapshot, PortfolioWorkspaceSource, ReviewSnapshotActiveThesisCrossFamilyQueueResponse, ReviewSnapshotComparisonArtifactRef, ReviewSnapshotFamilyInboxResponse, ReviewSnapshotOpenResponse, ReplacementIntentDraftArtifact, ReviewSnapshotComparisonResponse, ReviewSnapshotFamilyReviewResponse, VersionedProposalArtifact } from '../portfolio/workspaceTypes'
import { assertSavedProposalProposalCaptureIntegrity, assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope, assertValidReviewSnapshotComparisonResponseEnvelope, assertValidReviewSnapshotFamilyInboxResponseEnvelope, assertValidReviewSnapshotFamilyReviewResponseEnvelope, assertValidReviewSnapshotOpenResponseEnvelope, buildReviewSnapshotComparisonRefs, buildReviewSnapshotOpenHandoffFromProposal } from '../../app/portfolioWorkspaceStorage'
import { CandidateFormationSection, ConstructionRuleSection, DiagnosticsChangeSection, HypotheticalReplaySection, PortfolioAllocationBacktestPanel, SavedProposalReadoutSection } from './PortfolioAllocationBacktestPanel'
import { MonitoringPanel } from './MonitoringPanel'
import { MONITORING_RESEARCH_TARGET_IDS, monitoringResearchTargetLabel } from './monitoringResearchHandoff'

function formatReplayWindow(startDate: string | null | undefined, endDate: string | null | undefined) {
  if (!startDate || !endDate) return 'n/a'
  return `${startDate} -> ${endDate}`
}

function formatValue(value: string | number | null | undefined) {
  if (value == null) return 'n/a'
  if (typeof value === 'string') return value.trim() ? value : 'n/a'
  return String(value)
}

function isBenchmarkTrendObservationArtifact(value: MonitorDefinitionObservationArtifact): value is BenchmarkTrendOverlayMonitorDefinitionObservationArtifact {
  return value.monitor_id === 'benchmark_trend_overlay_v1'
}

function isBenchmarkTrendHistoryEntry(value: MonitorDefinitionEvaluationHistoryEntryResponse['item']): value is BenchmarkTrendOverlayMonitorDefinitionEvaluationHistoryEntryArtifact & { metadata: MonitorDefinitionEvaluationHistoryEntryResponse['item']['metadata'] } {
  return value.monitor_id === 'benchmark_trend_overlay_v1'
}

function isDataQualityObservationArtifact(value: MonitorDefinitionObservationArtifact): value is DataQualityMonitorDefinitionObservationArtifact {
  return value.monitor_id === 'data_quality_monitor_v1'
}

function isDataQualityHistoryEntry(value: MonitorDefinitionEvaluationHistoryEntryResponse['item']): value is DataQualityMonitorDefinitionEvaluationHistoryEntryArtifact & { metadata: MonitorDefinitionEvaluationHistoryEntryResponse['item']['metadata'] } {
  return value.monitor_id === 'data_quality_monitor_v1'
}

function formatMoney(value: number | null | undefined) {
  return value == null ? 'n/a' : `$${value.toFixed(2)}`
}

function formatProposalTimestamp(value: string) {
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) return value
  return parsed.toLocaleString('en-US', {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function formatSavedProposalContractErrorOutcome(error: unknown) {
  const message = error instanceof Error ? error.message : 'Saved proposal proposalCapture is missing'
  if (message.startsWith('Unable to reopen saved proposal:')) {
    return message
  }
  return `Unable to reopen saved proposal: ${message.charAt(0).toLowerCase()}${message.slice(1)}`
}

function assertSavedProposalCaptureForWorkspaceShell(
  proposal: VersionedProposalArtifact,
  _context: 'Saved proposal' | 'Saved proposal comparison left' | 'Saved proposal comparison right' | 'Active thesis saved proposal',
) {
  assertSavedProposalProposalCaptureIntegrity(proposal)
  return proposal.proposalCapture
}

function getProposalLabel(proposal: VersionedProposalArtifact) {
  const proposalCapture = assertSavedProposalCaptureForWorkspaceShell(proposal, 'Saved proposal')
  return `v${proposal.versionNumber} · ${proposalCapture.proposal.incumbent_symbol} -> ${proposalCapture.proposal.candidate_symbol}`
}

function formatPct(value: number | null | undefined) {
  return value == null ? 'n/a' : `${value.toFixed(2)}%`
}

function formatSignedPct(value: number | null | undefined) {
  if (value == null) return 'n/a'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatSignedNumber(value: number | null | undefined) {
  if (value == null) return 'n/a'
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}`
}

function diagnosticsValueLabel(row: PortfolioDiagnosticsTopCallout) {
  if (row.key.includes('hhi') || row.key.includes('beta') || row.key.includes('correlation')) {
    return formatSignedNumber(row.delta_value)
  }
  return formatSignedPct(row.delta_value)
}

type WorkflowSpineCard = {
  key: string
  title: string
  value: string
  detail: string
  sectionId: string | null
  status: WorkflowSectionStatus
}

function getActiveReplay(props: Props) {
  if (!props.hypotheticalReplayResult) return props.allocationBacktestResult
  return 'replay' in props.hypotheticalReplayResult ? props.hypotheticalReplayResult.replay : props.hypotheticalReplayResult.overlay_replay
}

function getActiveCandidatePair(props: Props) {
  if (props.replacementIntentDraft) {
    return {
      baseSymbol: props.replacementIntentDraft.baseSymbol,
      candidateSymbol: props.replacementIntentDraft.candidateSymbol,
      kind: 'replacement_intent' as const,
    }
  }
  if (props.candidateImprovementDraft) {
    return {
      baseSymbol: props.candidateImprovementDraft.seed.baseSymbol,
      candidateSymbol: props.candidateImprovementDraft.seed.candidateSymbol,
      kind: 'candidate_seed' as const,
    }
  }
  if (props.intentBoundSeededEtfReplacementRankingDraft) {
    return {
      baseSymbol: props.intentBoundSeededEtfReplacementRankingDraft.baseSymbol,
      candidateSymbol: props.intentBoundSeededEtfReplacementRankingDraft.candidateSymbol,
      kind: 'candidate_seed' as const,
    }
  }
  return null
}


function getProposalReplayType(proposal: VersionedProposalArtifact) {
  return 'replay' in proposal.reviewSnapshot ? 'Standard replay' : 'Overlay-aware replay'
}

function getProposalActiveReplay(proposal: VersionedProposalArtifact) {
  return 'replay' in proposal.reviewSnapshot ? proposal.reviewSnapshot.replay : proposal.reviewSnapshot.overlay_replay
}

function formatReplayStatusLabel(status: string | null | undefined) {
  if (!status) return 'n/a'
  if (status === 'ok') return 'Pass'
  return status
}

function replaceUnderscoresWithSpaces(value: string) {
  return value.replace(/_/g, ' ')
}

function formatProposalSourceKind(value: string | null | undefined) {
  if (!value) return 'n/a'
  return replaceUnderscoresWithSpaces(value)
}

function formatCompareReadinessLabel(ready: boolean) {
  return ready ? 'ready' : 'not ready'
}

function familyInboxRowLabel(row: NonNullable<ReviewSnapshotFamilyInboxResponse['rows']>[number]) {
  return `v${row.lineage.version_number} · ${row.proposal_capture.proposal.incumbent_symbol} -> ${row.proposal_capture.proposal.candidate_symbol}`
}

function formatReplayCandidateInputSourceLabel(value: HypotheticalReplayResponse['replay_provenance']['candidate_input_source']) {
  return value === 'constructed_candidate_payload' ? 'constructed candidate replay' : 'direct preview replay'
}

function formatReplayConstructionRuleLabel(value: HypotheticalReplayResponse['replay_provenance']['construction_rule_id']) {
  return value === 'fixed_split_50_50_substitution_v2' ? 'fixed split 50/50' : 'same-weight substitution'
}

function formatReplayConstraintValidationLabel(value: HypotheticalReplayResponse['replay_provenance']['constraint_validation']) {
  if (!value.supplied) return 'validation not supplied'
  if (value.validation_status === 'blocked') return 'validated blocked'
  if (value.validation_status === 'rejected') return 'validated rejected'
  return 'validated ok'
}

function formatReplayLineageHelper(result: HypotheticalReplayResponse | null) {
  if (!result) return null
  return `Replay lineage: ${formatReplayCandidateInputSourceLabel(result.replay_provenance.candidate_input_source)} · ${formatReplayConstructionRuleLabel(result.replay_provenance.construction_rule_id)} · ${formatReplayConstraintValidationLabel(result.replay_provenance.constraint_validation)}`
}

type ProposalComparisonMetric = {
  key: string
  label: string
  leftValue: string
  rightValue: string
  note: string
}

type SavedProposalComparisonState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  comparison: ReviewSnapshotComparisonResponse | null
  error: string | null
}

type SavedProposalFamilyReviewState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  review: ReviewSnapshotFamilyReviewResponse | null
  error: string | null
}

type SavedProposalFamilyInboxState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  inbox: ReviewSnapshotFamilyInboxResponse | null
  error: string | null
}

type ActiveThesisOpenState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  open: ReviewSnapshotOpenResponse | null
  error: string | null
}

type ActiveThesisDeltaState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  comparison: ReviewSnapshotComparisonResponse | null
  error: string | null
}

type ActiveThesisCrossFamilyQueueState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  queue: ReviewSnapshotActiveThesisCrossFamilyQueueResponse | null
  error: string | null
}

type ActiveAlertEpisodeInboxState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  response: MonitorDefinitionActiveAlertEpisodeInboxResponse | null
  error: string | null
}

type AlertEpisodeHistoryState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  monitorDefinitionId: string | null
  response: MonitorDefinitionAlertEpisodeHistoryResponse | null
  error: string | null
}

type LatestObservationOpenState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  row: MonitorDefinitionAlertReviewTimelineObservationRow | null
  observation: MonitorDefinitionObservationArtifact | null
  error: string | null
}

type AlertHistoryOpenState = {
  status: 'idle' | 'loading' | 'ready' | 'error'
  row: MonitorDefinitionAlertReviewTimelineHistoryRow | null
  entry: MonitorDefinitionEvaluationHistoryEntryResponse | null
  error: string | null
}

function formatObservationStatusLabel(value: MonitorDefinitionObservationArtifact['observation_status'] | MonitorDefinitionAlertReviewTimelineObservationRow['observation_status']) {
  if (value === 'threshold_breach') return 'alert'
  return replaceUnderscoresWithSpaces(value)
}

function formatObservationAlertClassificationLabel(value: MonitorDefinitionAlertReviewTimelineObservationRow['alert_classification']) {
  return replaceUnderscoresWithSpaces(value)
}

function formatObservationCauseCodeLabel(value: MonitorDefinitionAlertReviewTimelineObservationRow['cause_code']) {
  return value ? replaceUnderscoresWithSpaces(value) : 'none'
}

function formatAlertHistoryOutcomeLabel(value: MonitorDefinitionAlertReviewTimelineHistoryRow['outcome_status']) {
  if (value === 'threshold_breach') return 'alert'
  return replaceUnderscoresWithSpaces(value)
}

function formatAlertHistorySignificanceLabel(value: MonitorDefinitionAlertReviewTimelineHistoryRow['significance_status']) {
  return replaceUnderscoresWithSpaces(value)
}

function formatAlertHistoryReviewSupportLabel(value: MonitorDefinitionAlertReviewTimelineHistoryRow['review_support_status']) {
  return replaceUnderscoresWithSpaces(value)
}

function monitorFamilyLabel(value: { monitor_id: string; benchmark_symbol: string }) {
  return isDataQualityMonitorIdentity(value) ? 'Input reliability / data quality' : 'Benchmark trend'
}

function monitorDefinitionLabel(value: { monitor_definition_id: string; benchmark_symbol: string }) {
  return `${value.monitor_definition_id} · ${value.benchmark_symbol}`
}

function formatDataQualitySymbols(symbols: string[]) {
  return symbols.length ? symbols.join(', ') : 'none'
}

function DataQualityEvidenceReadback({ evidence }: { evidence: DataQualityMonitorEvidenceSummary }) {
  const trustStatuses = Object.entries(evidence.trust_statuses)
    .map(([source, status]) => `${source}: ${status}`)
    .join(', ')
  const lineage = evidence.source_lineage
    .map((item) => `${item.source_kind}/${item.source_id} observed ${item.observed_at}`)
    .join('; ')

  return (
    <div className="summary-card" data-testid="data-quality-evidence-readback">
      <p className="panel-label">Input Reliability Evidence</p>
      <p className="helper">Coverage {formatPct(evidence.coverage_ratio * 100)} · available {evidence.coverage_available_count} of {evidence.coverage_total_count} · missing {evidence.coverage_missing_count}</p>
      <p className="helper">Stale symbols: {formatDataQualitySymbols(evidence.stale_symbols)} · missing symbols: {formatDataQualitySymbols(evidence.missing_symbols)}</p>
      <p className="helper">Withheld inputs: {formatDataQualitySymbols(evidence.withheld_inputs)} · unavailable inputs: {formatDataQualitySymbols(evidence.unavailable_inputs)}</p>
      <p className="helper">Trust statuses: {trustStatuses || 'none reported'}</p>
      <p className="helper">Source lineage: {lineage || 'none reported'}</p>
    </div>
  )
}

function dataQualityReadbackLabel(evidence: DataQualityMonitorEvidenceSummary | null | undefined) {
  if (!evidence) return 'evidence unavailable'
  return `coverage ${formatPct(evidence.coverage_ratio * 100)} · missing ${evidence.coverage_missing_count} · stale ${evidence.stale_symbols.length}`
}

function buildReviewSnapshotComparisonRef(
  artifact: {
    artifact_id: string
    artifact_kind: 'portfolio_review_snapshot'
    schema_version: 'review_snapshot_artifact_v1'
    consumer_kind: 'saved_hypothetical_replay_proposal'
  },
  role: ReviewSnapshotComparisonArtifactRef['role'],
): ReviewSnapshotComparisonArtifactRef {
  return {
    role,
    artifact_id: artifact.artifact_id,
    artifact_kind: artifact.artifact_kind,
    schema_version: artifact.schema_version,
    consumer_kind: artifact.consumer_kind,
  }
}

function buildProposalComparisonMetrics(comparison: ReviewSnapshotComparisonResponse): ProposalComparisonMetric[] {
  const left = comparison.baseline_pm_summary
  const right = comparison.candidate_pm_summary

  return [
    {
      key: 'replay-status',
      label: 'Replay status',
      leftValue: formatReplayStatusLabel(left.replay_status),
      rightValue: formatReplayStatusLabel(right.replay_status),
      note: 'Candidate replay execution status only.',
    },
    {
      key: 'replay-window',
      label: 'Replay window',
      leftValue: `${left.review_basis.replay_window.start_date} -> ${left.review_basis.replay_window.end_date}`,
      rightValue: `${right.review_basis.replay_window.start_date} -> ${right.review_basis.replay_window.end_date}`,
      note: 'Window compatibility for saved replay review.',
    },
    {
      key: 'replay-setup',
      label: 'Replay setup',
      leftValue: `${left.review_basis.rebalance_frequency} · ${left.review_basis.commission_bps}/${left.review_basis.slippage_bps} bps`,
      rightValue: `${right.review_basis.rebalance_frequency} · ${right.review_basis.commission_bps}/${right.review_basis.slippage_bps} bps`,
      note: 'Rebalance and cost inputs captured with each artifact.',
    },
    {
      key: 'lineage',
      label: 'Replay lineage',
      leftValue: `${formatReplayCandidateInputSourceLabel(left.provenance.replay_provenance.candidate_input_source)} · ${formatReplayConstructionRuleLabel(left.provenance.replay_provenance.construction_rule_id)}`,
      rightValue: `${formatReplayCandidateInputSourceLabel(right.provenance.replay_provenance.candidate_input_source)} · ${formatReplayConstructionRuleLabel(right.provenance.replay_provenance.construction_rule_id)}`,
      note: 'Saved provenance and replay handoff only.',
    },
    {
      key: 'constraint-validation',
      label: 'Constraint validation',
      leftValue: formatReplayConstraintValidationLabel(left.provenance.replay_provenance.constraint_validation),
      rightValue: formatReplayConstraintValidationLabel(right.provenance.replay_provenance.constraint_validation),
      note: 'Saved validation handoff state only.',
    },
  ]
}

function SavedProposalComparisonView({
  leftProposal,
  rightProposal,
  comparisonState,
  onSwapSides,
  onOpenProposal,
  onClearComparison,
}: {
  leftProposal: VersionedProposalArtifact
  rightProposal: VersionedProposalArtifact
  comparisonState: SavedProposalComparisonState
  onSwapSides: () => void
  onOpenProposal: (proposalId: string) => void
  onClearComparison: () => void
}) {
  const leftProposalCapture = assertSavedProposalCaptureForWorkspaceShell(leftProposal, 'Saved proposal comparison left')
  const rightProposalCapture = assertSavedProposalCaptureForWorkspaceShell(rightProposal, 'Saved proposal comparison right')
  const comparisonMetrics = comparisonState.comparison ? buildProposalComparisonMetrics(comparisonState.comparison) : []
  const sameReplayType = comparisonState.comparison
    ? comparisonState.comparison.baseline_pm_summary.replay_type === comparisonState.comparison.candidate_pm_summary.replay_type
    : getProposalReplayType(leftProposal) === getProposalReplayType(rightProposal)
  const sameReplayWindow = comparisonState.comparison
    ? comparisonState.comparison.baseline_pm_summary.review_basis.replay_window.start_date === comparisonState.comparison.candidate_pm_summary.review_basis.replay_window.start_date
      && comparisonState.comparison.baseline_pm_summary.review_basis.replay_window.end_date === comparisonState.comparison.candidate_pm_summary.review_basis.replay_window.end_date
    : leftProposalCapture.review_basis.replay_window.start_date === rightProposalCapture.review_basis.replay_window.start_date
      && leftProposalCapture.review_basis.replay_window.end_date === rightProposalCapture.review_basis.replay_window.end_date
  const sameIntentPair = leftProposalCapture.proposal.incumbent_symbol === rightProposalCapture.proposal.incumbent_symbol
    && leftProposalCapture.proposal.candidate_symbol === rightProposalCapture.proposal.candidate_symbol
  const leftTakeaway = comparisonState.comparison?.baseline_pm_summary.diagnostics_summary.top_factor_exposure_change
    ?? comparisonState.comparison?.baseline_pm_summary.diagnostics_summary.top_volatility_change
    ?? comparisonState.comparison?.baseline_pm_summary.diagnostics_summary.top_risk_contribution_change
    ?? comparisonState.comparison?.baseline_pm_summary.diagnostics_summary.top_concentration_change
    ?? comparisonState.comparison?.baseline_pm_summary.diagnostics_summary.top_stress_scenario_change
    ?? null
  const rightTakeaway = comparisonState.comparison?.candidate_pm_summary.diagnostics_summary.top_factor_exposure_change
    ?? comparisonState.comparison?.candidate_pm_summary.diagnostics_summary.top_volatility_change
    ?? comparisonState.comparison?.candidate_pm_summary.diagnostics_summary.top_risk_contribution_change
    ?? comparisonState.comparison?.candidate_pm_summary.diagnostics_summary.top_concentration_change
    ?? comparisonState.comparison?.candidate_pm_summary.diagnostics_summary.top_stress_scenario_change
    ?? null
  const diagnosticsAvailable = Boolean(leftTakeaway || rightTakeaway)

  return (
    <section className="dashboard-bottom-grid" data-testid="saved-proposal-comparison-view">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Saved Proposal Comparison</p></div>
        <p className="helper">Read-only comparison for exactly two immutable saved proposal artifacts. This view uses only saved artifact data and does not mutate proposal, draft, or portfolio state.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Left proposal</p>
          <p className="summary-value">v{leftProposal.versionNumber} · {leftProposalCapture.proposal.incumbent_symbol} -&gt; {leftProposalCapture.proposal.candidate_symbol}</p>
          <p className="helper">{getProposalReplayType(leftProposal)} · {formatProposalTimestamp(leftProposal.createdAt)}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Right proposal</p>
          <p className="summary-value">v{rightProposal.versionNumber} · {rightProposalCapture.proposal.incumbent_symbol} -&gt; {rightProposalCapture.proposal.candidate_symbol}</p>
          <p className="helper">{getProposalReplayType(rightProposal)} · {formatProposalTimestamp(rightProposal.createdAt)}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Compatibility</p>
          <p className="summary-value">{comparisonState.status === 'ready' ? 'Compatible' : sameReplayType && sameReplayWindow ? 'Aligned' : 'Review carefully'}</p>
          <p className="helper">Replay type {sameReplayType ? 'matches' : 'differs'} · window {sameReplayWindow ? 'matches' : 'differs'} · intent pair {sameIntentPair ? 'matches' : 'differs'}.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Comparison state</p>
          <p className="summary-value">2 of 2 selected</p>
          <p className="helper">Use swap to reverse sides or open either artifact in the full saved-proposal view.</p>
        </div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Artifact-backed comparison</p>
        {comparisonState.status === 'loading' ? <p className="helper">Loading persisted review snapshot comparison.</p> : null}
        {comparisonState.status === 'error' ? <p className="helper">{comparisonState.error}</p> : null}
        {comparisonState.status === 'ready' && comparisonState.comparison ? (
          <>
            <p className="helper">Provenance: {comparisonState.comparison.provenance} · benchmark separation: {comparisonState.comparison.benchmark_separation}</p>
            <p className="helper">Methodology consistent: {comparisonState.comparison.methodology.methodology_consistent ? 'yes' : 'no'} · assumptions consistent: {comparisonState.comparison.assumptions.assumptions_consistent ? 'yes' : 'no'}</p>
          </>
        ) : null}
      </div>
      <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
        <button className="secondary-button" onClick={onSwapSides} type="button">Swap sides</button>
        <button className="secondary-button" onClick={() => onOpenProposal(leftProposal.id)} type="button">Open full proposal v{leftProposal.versionNumber}</button>
        <button className="secondary-button" onClick={() => onOpenProposal(rightProposal.id)} type="button">Open full proposal v{rightProposal.versionNumber}</button>
        <button className="secondary-button" onClick={onClearComparison} type="button">Clear comparison</button>
      </div>
      <div className="summary-card">
        <p className="panel-label">Comparison Checks</p>
        <div className="list-table">
          <div className="list-row list-row-wide">
            <span>Check</span>
            <span>Left</span>
            <span>Right</span>
            <span>Review note</span>
          </div>
          {comparisonMetrics.map((metric) => (
            <div className="list-row list-row-wide" key={metric.key}>
              <span>{metric.label}</span>
              <span>{metric.leftValue}</span>
              <span>{metric.rightValue}</span>
              <span>{metric.note}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Left replay status</p>
          <p className="summary-value">{comparisonState.comparison ? formatReplayStatusLabel(comparisonState.comparison.baseline_pm_summary.replay_status) : formatReplayStatusLabel(getProposalActiveReplay(leftProposal).candidate_result.status)}</p>
          <p className="helper">Window {comparisonState.comparison ? `${comparisonState.comparison.baseline_pm_summary.review_basis.replay_window.start_date} - ${comparisonState.comparison.baseline_pm_summary.review_basis.replay_window.end_date}` : `${leftProposalCapture.review_basis.replay_window.start_date} - ${leftProposalCapture.review_basis.replay_window.end_date}`}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Right replay status</p>
          <p className="summary-value">{comparisonState.comparison ? formatReplayStatusLabel(comparisonState.comparison.candidate_pm_summary.replay_status) : formatReplayStatusLabel(getProposalActiveReplay(rightProposal).candidate_result.status)}</p>
          <p className="helper">Window {comparisonState.comparison ? `${comparisonState.comparison.candidate_pm_summary.review_basis.replay_window.start_date} - ${comparisonState.comparison.candidate_pm_summary.review_basis.replay_window.end_date}` : `${rightProposalCapture.review_basis.replay_window.start_date} - ${rightProposalCapture.review_basis.replay_window.end_date}`}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Left diagnostics takeaway</p>
          <p className="summary-value">{leftTakeaway?.label ?? 'Unavailable'}</p>
          <p className="helper">{leftTakeaway ? `Saved PM summary diagnostic delta ${diagnosticsValueLabel(leftTakeaway)}` : 'No saved diagnostics takeaway is available for this artifact.'}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Right diagnostics takeaway</p>
          <p className="summary-value">{rightTakeaway?.label ?? 'Unavailable'}</p>
          <p className="helper">{rightTakeaway ? `Saved PM summary diagnostic delta ${diagnosticsValueLabel(rightTakeaway)}` : 'No saved diagnostics takeaway is available for this artifact.'}</p>
        </div>
      </div>
      {!diagnosticsAvailable ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Saved diagnostics takeaway is unavailable for both proposals.</p>
          <p className="helper">Comparison still shows saved replay status, setup, compatibility, and lineage from the immutable artifacts.</p>
        </div>
      ) : null}
      <div className="split-grid dashboard-bottom-grid">
        <section>
          <div className="summary-card">
            <p className="panel-label">Left proposal details</p>
            <p className="helper">Immutable artifact detail reopened in comparison mode only.</p>
          </div>
          <SavedProposalReadoutSection proposal={leftProposal} />
        </section>
        <section>
          <div className="summary-card">
            <p className="panel-label">Right proposal details</p>
            <p className="helper">Immutable artifact detail reopened in comparison mode only.</p>
          </div>
          <SavedProposalReadoutSection proposal={rightProposal} />
        </section>
      </div>
    </section>
  )
}

type Props = {
  analysis: PortfolioBaselineView | null
  draftSnapshot: PortfolioSnapshot | null
  workspaceSource?: PortfolioWorkspaceSource | null
  persistedConstructionArtifactReview?: PersistedConstructionArtifactWorkspaceReview | null
  persistedOptimizerHandoffReview?: PersistedOptimizerHandoffWorkspaceReview | null
  candidateImprovementDraft: CandidateImprovementDraftArtifact | null
  intentBoundSeededEtfReplacementRankingDraft: IntentBoundSeededEtfReplacementRankingDraftArtifact | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  formedCandidateArtifact: FormedCandidateArtifact | null
  constructedCandidateArtifact: ConstructedCandidateArtifact | null
  constructionConstraintValidationArtifact: ConstructionConstraintValidationArtifact | null
  selectedConstructionRuleId: SingleReplacementConstructionRuleId
  allocationBacktestResult: PortfolioAllocationBacktestResponse | null
  onAllocationBacktestResult?: (result: PortfolioAllocationBacktestResponse) => void
  hypotheticalReplayResult: HypotheticalReplayResponse | null
  savedProposals: VersionedProposalArtifact[]
  activeThesis: ActiveThesisArtifact | null
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
  onSaveProposal: () => void | Promise<void>
  onOpenSavedProposal?: (reviewSnapshotArtifactId: string) => void | Promise<void>
  openedSavedProposalArtifactId?: string | null
  onPromoteProposalToThesis: (proposalId: string) => void | Promise<void>
  onClearActiveThesis: () => void | Promise<void>
  onHypotheticalReplayResult: (result: HypotheticalReplayResponse) => void
  onFormedCandidateArtifact: (result: SingleReplacementCandidateFormationResponse) => void
  onConstructedCandidateArtifact: (result: SingleReplacementCandidateConstructionResponse) => void
  onConstructionConstraintValidationArtifact: (result: SingleReplacementConstructionConstraintValidationResponse) => void
  onSelectedConstructionRuleChange: (ruleId: SingleReplacementConstructionRuleId) => void
  monitorDefinitionAlertReviewSession?: MonitorDefinitionAlertReviewSessionState | null
  recoveredAlertReviewQueue?: MonitorDefinitionRecoveredAlertReviewQueueRow[] | null
  activeAlertEpisodeInbox?: ActiveAlertEpisodeInboxState | null
  alertEpisodeHistory?: AlertEpisodeHistoryState | null
  onOpenLatestObservation?: (row: MonitorDefinitionAlertReviewTimelineObservationRow) => void | Promise<void>
  onOpenAlertHistoryReview?: (row: MonitorDefinitionAlertReviewTimelineHistoryRow) => void | Promise<void>
  onReopenRecoveredAlertReview?: (row: MonitorDefinitionRecoveredAlertReviewQueueRow) => void | Promise<void>
  onOpenActiveAlertEpisode?: (row: MonitorDefinitionActiveAlertEpisodeInboxRow) => void | Promise<void>
  onOpenAlertEpisodeHistory?: (row: MonitorDefinitionAlertEpisodeHistoryRow) => void | Promise<void>
  onLoadOlderAlertEpisodeHistory?: () => void | Promise<void>
  monitoringResearchHandoff?: MonitoringResearchHandoff | null
  monitoringResearchHandoffDismissed?: boolean
  onDismissMonitoringResearchHandoff?: () => void
  onReviewInResearch?: (handoff: MonitoringResearchHandoff) => void
  onOpenGenericBacktests?: (sectionId?: string) => void
  onOpenStrategyLab?: (sectionId?: string) => void
  onOpenEtfRanking?: (sectionId?: string) => void
  onOpenPersistedConstructionArtifactReview?: (constructionArtifactId: string) => void | Promise<void>
  onOpenPersistedEtfRankingReview?: (artifactId: string) => void | Promise<void>
}

function ResearchToolsSection({
  onOpenGenericBacktests,
  onOpenStrategyLab,
  onOpenEtfRanking,
}: {
  onOpenGenericBacktests?: (sectionId?: string) => void
  onOpenStrategyLab?: (sectionId?: string) => void
  onOpenEtfRanking?: (sectionId?: string) => void
}) {
  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-research-tools" id="workspace-section-research-tools">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Research Tools</p></div>
        <p className="helper">Open deeper research surfaces from the workspace without promoting them to primary shell destinations.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Generic Backtests</p>
          <p className="summary-value">Strategy sandbox</p>
          <p className="helper">Run generic strategy backtests outside the portfolio-improvement workflow.</p>
          <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
            <button className="secondary-button" onClick={() => onOpenGenericBacktests?.('workspace-section-research-tools')} type="button">Open Backtest</button>
          </div>
        </div>
        <div className="summary-card">
          <p className="stat-label">Strategy Lab</p>
          <p className="summary-value">Cross-sectional research</p>
          <p className="helper">Inspect ETF cross-sectional research artifacts and prototype rotation work.</p>
          <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
            <button className="secondary-button" onClick={() => onOpenStrategyLab?.('workspace-section-research-tools')} type="button">Open Strategy Lab</button>
          </div>
        </div>
        <div className="summary-card">
          <p className="stat-label">ETF Ranking</p>
          <p className="summary-value">Replacement discovery</p>
          <p className="helper">Rank ETF substitutes and seed a candidate back into the workspace review flow.</p>
          <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
            <button className="secondary-button" onClick={() => onOpenEtfRanking?.('workspace-section-research-tools')} type="button">Open ETF Ranking</button>
          </div>
        </div>
      </div>
    </section>
  )
}

function RecoveredAlertReviewQueueSection({
  rows,
  onReopenRecoveredAlertReview,
}: {
  rows: MonitorDefinitionRecoveredAlertReviewQueueRow[]
  onReopenRecoveredAlertReview: ((row: MonitorDefinitionRecoveredAlertReviewQueueRow) => void | Promise<void>) | undefined
}) {
  return (
    <section className="dashboard-bottom-grid" data-testid="recovered-alert-review-queue">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Recovered Alert Review Queue</p></div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Recovered Alerts</p>
        <p className="helper">Rows: {rows.length}</p>
      </div>
      {rows.length ? (
        <div className="summary-card">
          <p className="panel-label">Recovered Discovery Rows</p>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Benchmark</span>
              <span>Recovered Latest</span>
              <span>Recovered From</span>
              <span>Review</span>
            </div>
            {rows.map((row) => (
              <div className="list-row list-row-wide" key={`${row.monitor_definition_id}-${row.observation_id}`} data-testid={`recovered-alert-row-${row.observation_id}`}>
                <span>{row.benchmark_symbol}</span>
                <span>{formatObservationStatusLabel(row.observation_status)} · {row.observation_id} · {row.recency_status}</span>
                <span>{formatAlertHistorySignificanceLabel(row.recovered_from.significance_status)} · {formatAlertHistoryOutcomeLabel(row.recovered_from.outcome_status)} · {row.recovered_from.history_entry_id}</span>
                <span>
                  <button className="secondary-button" onClick={() => { void onReopenRecoveredAlertReview?.(row) }} type="button">Reopen timeline review</button>
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  )
}

function ActiveAlertEpisodeInboxSection({
  inbox,
  onOpenActiveAlertEpisode,
}: {
  inbox: ActiveAlertEpisodeInboxState
  onOpenActiveAlertEpisode: ((row: MonitorDefinitionActiveAlertEpisodeInboxRow) => void | Promise<void>) | undefined
}) {
  const response = inbox.response
  const rows = response?.items ?? []
  const metadata = response?.metadata ?? null

  return (
    <section className="dashboard-bottom-grid" data-testid="active-alert-episode-inbox">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Active Alert Review Inbox</p></div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Open Episodes</p>
        {inbox.status === 'loading' ? <p className="helper">Loading active alert episodes…</p> : null}
        {inbox.status === 'error' ? <p className="helper">{inbox.error ?? 'Unable to load active alert review inbox'}</p> : null}
        {inbox.status === 'ready' && metadata ? <p className="helper">Rows: {rows.length} of {metadata.total_active_episodes}</p> : null}
        {inbox.status === 'ready' && !rows.length ? <p className="helper">No active alert episodes.</p> : null}
      </div>
      {inbox.status === 'ready' && rows.length ? (
        <div className="summary-card">
          <p className="panel-label">Active Episode Rows</p>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Family</span>
              <span>Definition</span>
              <span>Status / Cause</span>
              <span>Readback</span>
              <span>Review</span>
            </div>
            {rows.map((row) => {
              const episode = row.alert_episode
              const latest = episode.latest_contributing_observation
              const handoff = episode.timeline_handoff
              return (
                <div className="list-row list-row-wide" key={episode.episode_id} data-testid={`active-alert-episode-row-${episode.episode_id}`}>
                  <span>{monitorFamilyLabel(episode)}</span>
                  <span>{monitorDefinitionLabel(episode)}<br />{replaceUnderscoresWithSpaces(episode.lifecycle_status)} · episode {episode.episode_id}</span>
                  <span>{formatObservationStatusLabel(latest.observation_status)} · {formatObservationAlertClassificationLabel(latest.alert_classification)}<br />cause {formatObservationCauseCodeLabel(latest.cause_code)}</span>
                  <span>{isDataQualityMonitorIdentity(episode) ? 'Input reliability review from persisted data-quality episode.' : 'Benchmark trend alert from persisted threshold episode.'}<br />latest {latest.observation_id} · {latest.evaluated_at}</span>
                  <span>
                    <button className="secondary-button" onClick={() => { void onOpenActiveAlertEpisode?.(row) }} type="button">Open timeline review</button>
                    <span className="helper"> handoff {handoff.monitor_definition_id} · {handoff.observation_id}</span>
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}
    </section>
  )
}

function AlertEpisodeHistoryDrillInSection({
  history,
  onOpenAlertEpisodeHistory,
  onLoadOlderAlertEpisodeHistory,
}: {
  history: AlertEpisodeHistoryState
  onOpenAlertEpisodeHistory: ((row: MonitorDefinitionAlertEpisodeHistoryRow) => void | Promise<void>) | undefined
  onLoadOlderAlertEpisodeHistory: (() => void | Promise<void>) | undefined
}) {
  const response = history.response
  const rows = response?.items ?? []
  const metadata = response?.metadata ?? null

  return (
    <section className="dashboard-bottom-grid" data-testid="alert-episode-history-drill-in">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Alert Episode History</p></div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Episode Window</p>
        {history.status === 'idle' ? <p className="helper">Select a monitor definition to load episode history.</p> : null}
        {history.status === 'loading' ? <p className="helper">Loading episode history for {history.monitorDefinitionId ?? 'selected monitor definition'}…</p> : null}
        {history.status === 'error' ? <p className="helper">{history.error ?? 'Unable to load alert episode history'}</p> : null}
        {metadata ? (
          <p className="helper">{rows.length} of {metadata.total_episodes} episodes · {metadata.monitor_definition_id}</p>
        ) : null}
        {history.status === 'ready' && !rows.length ? <p className="helper">No episodes in this window.</p> : null}
      </div>
      {rows.length ? (
        <div className="summary-card">
          <p className="panel-label">Persisted Episode Rows</p>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Family</span>
              <span>Lifecycle</span>
              <span>Status / Cause</span>
              <span>Readback</span>
              <span>Review</span>
            </div>
            {rows.map((row) => {
              const latest = row.latest_contributing_observation
              return (
                <div className="list-row list-row-wide" key={row.episode_id} data-testid={`alert-episode-history-row-${row.episode_id}`}>
                  <span>{monitorFamilyLabel(row)}</span>
                  <span>{replaceUnderscoresWithSpaces(row.lifecycle_status)} · {row.latest_for_monitor_definition ? 'latest for definition' : 'historical'}<br />{row.episode_id}<br />{monitorDefinitionLabel(row)}</span>
                  <span>{formatObservationStatusLabel(latest.observation_status)} · {formatObservationAlertClassificationLabel(latest.alert_classification)}<br />cause {formatObservationCauseCodeLabel(latest.cause_code)}</span>
                  <span>{isDataQualityMonitorIdentity(row) ? 'Input reliability lifecycle; no benchmark threshold readback.' : 'Benchmark threshold lifecycle readback.'}<br />started {row.started_at} · ended {row.ended_at ?? 'open'} · latest {row.latest_event_at}</span>
                  <span>
                    <button className="secondary-button" onClick={() => { void onOpenAlertEpisodeHistory?.(row) }} type="button">Open timeline review</button>
                    <span className="helper"> {row.timeline_handoff.selected_event_kind === 'latest_observation_event' ? row.timeline_handoff.observation_id : row.timeline_handoff.history_entry_id}</span>
                  </span>
                </div>
              )
            })}
          </div>
          {metadata?.next_before_episode_id ? (
            <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
              <button className="secondary-button" onClick={() => { void onLoadOlderAlertEpisodeHistory?.() }} type="button">Load older</button>
            </div>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function isPersistedConstructionArtifactMode(props: Props) {
  return Boolean(props.workspaceSource && 'kind' in props.workspaceSource && props.workspaceSource.kind === 'persisted_construction_artifact')
}

function isPersistedOptimizerHandoffMode(props: Props) {
  return Boolean(props.workspaceSource && 'kind' in props.workspaceSource && props.workspaceSource.kind === 'persisted_optimizer_handoff')
}

function isArtifactReviewMode(props: Props) {
  return isPersistedConstructionArtifactMode(props) || isPersistedOptimizerHandoffMode(props)
}

function formatOverviewSource(analysis: PortfolioBaselineView | null, draftSnapshot: PortfolioSnapshot | null) {
  return draftSnapshot?.importedMeta.importer ?? analysis?.snapshot.statement.importer ?? null
}

function formatOverviewPeriod(analysis: PortfolioBaselineView | null, draftSnapshot: PortfolioSnapshot | null) {
  return draftSnapshot?.importedMeta.statementPeriod ?? analysis?.snapshot.statement.statement_period ?? null
}

function formatArtifactReviewBasisLabel(source: Extract<PortfolioWorkspaceSource, { kind: 'persisted_construction_artifact' }> | null | undefined) {
  return source?.reviewBasis?.basisKind === 'persisted_construction_artifact_review' ? 'Artifact review basis' : 'Artifact review'
}

function formatArtifactReviewBasisDetail(source: Extract<PortfolioWorkspaceSource, { kind: 'persisted_construction_artifact' }> | null | undefined) {
  return source?.reviewBasis?.constructionArtifactId ?? source?.constructionArtifactId ?? 'n/a'
}

function optimizerHandoffReviewBasisId(props: Props) {
  if (props.persistedOptimizerHandoffReview?.handoffReference.handoff_id) return props.persistedOptimizerHandoffReview.handoffReference.handoff_id
  if (props.workspaceSource && 'handoffReference' in props.workspaceSource) return props.workspaceSource.handoffReference.handoff_id
  return 'n/a'
}

function scrollToSection(sectionId: string) {
  const target = document.getElementById(sectionId)
  if (target && 'scrollIntoView' in target && typeof target.scrollIntoView === 'function') {
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

function OverviewSection(props: Props) {
  const artifactMode = isPersistedConstructionArtifactMode(props)
  const optimizerHandoffMode = isPersistedOptimizerHandoffMode(props)
  const positionsCount = props.draftSnapshot?.positions.length ?? props.analysis?.snapshot.positions.length ?? null
  const benchmarkSymbol = artifactMode
    ? props.persistedConstructionArtifactReview?.replay.replay.candidate_result?.benchmark_symbol ?? 'SPY'
    : optimizerHandoffMode
      ? props.persistedOptimizerHandoffReview?.replay.replay.candidate_result?.benchmark_symbol ?? 'SPY'
      : props.draftSnapshot?.metadata.benchmarkSymbol ?? 'SPY'

  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-overview">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Overview</p></div>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Portfolio Value</p>
          <p className="summary-value">{formatMoney(props.analysis?.overview?.total_market_value ?? null)}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Positions</p>
          <p className="summary-value">{formatValue(positionsCount)}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Benchmark</p>
          <p className="summary-value">{formatValue(benchmarkSymbol)}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Review Basis</p>
          <p className="summary-value">{artifactMode ? formatArtifactReviewBasisLabel((props.workspaceSource && 'kind' in props.workspaceSource && props.workspaceSource.kind === 'persisted_construction_artifact') ? props.workspaceSource : null) : optimizerHandoffMode ? 'Optimizer handoff reference review basis' : formatValue(formatOverviewSource(props.analysis, props.draftSnapshot))}</p>
          <p className="helper">{artifactMode ? formatArtifactReviewBasisDetail((props.workspaceSource && 'kind' in props.workspaceSource && props.workspaceSource.kind === 'persisted_construction_artifact') ? props.workspaceSource : null) : optimizerHandoffMode ? optimizerHandoffReviewBasisId(props) : formatValue(formatOverviewPeriod(props.analysis, props.draftSnapshot))}</p>
        </div>
      </div>
      <MonitoringPanel result={props.allocationBacktestResult} hypotheticalReplayResult={props.hypotheticalReplayResult} onReviewInResearch={props.onReviewInResearch} />
    </section>
  )
}

function CandidateWorkspaceSection(props: Props) {
  const [open, setOpen] = useState(true)
  if (isArtifactReviewMode(props)) {
    return null
  }
  const currentPortfolio = buildAuthoritativeCurrentPortfolio(props.draftSnapshot)
  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-candidate">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Candidate</p></div>
        <button className="workspace-collapse-btn" onClick={() => setOpen((o) => !o)} type="button" aria-label={open ? 'Collapse candidate section' : 'Expand candidate section'}>
          <span className={`workspace-collapsible-chevron${open ? ' open' : ''}`}>▾</span>
        </button>
      </div>
      {open ? (
        <>
          <CandidateIdeaSection
            candidateImprovementDraft={props.candidateImprovementDraft}
            intentBoundSeededEtfReplacementRankingDraft={props.intentBoundSeededEtfReplacementRankingDraft}
            replacementIntentDraft={props.replacementIntentDraft}
            currentPortfolio={currentPortfolio}
            onCreateReplacementIntent={props.onCreateReplacementIntent}
            onClearReplacementIntent={props.onClearReplacementIntent}
            onOpenPersistedConstructionArtifactReview={props.onOpenPersistedConstructionArtifactReview}
            onOpenEtfRanking={props.onOpenEtfRanking}
            onOpenPersistedEtfRankingReview={props.onOpenPersistedEtfRankingReview}
          />
          <div id={WORKFLOW_SECTION_IDS.candidateFormation}>
            <CandidateFormationSection
              draftSnapshot={props.draftSnapshot}
              replacementIntentDraft={props.replacementIntentDraft}
              formedCandidateArtifact={props.formedCandidateArtifact}
              onFormedCandidateArtifact={props.onFormedCandidateArtifact}
            />
          </div>
          <div id={WORKFLOW_SECTION_IDS.constructionRule}>
            <ConstructionRuleSection
              draftSnapshot={props.draftSnapshot}
              replacementIntentDraft={props.replacementIntentDraft}
              formedCandidateArtifact={props.formedCandidateArtifact}
              constructedCandidateArtifact={props.constructedCandidateArtifact}
              constructionConstraintValidationArtifact={props.constructionConstraintValidationArtifact}
              selectedConstructionRuleId={props.selectedConstructionRuleId}
              onConstructedCandidateArtifact={props.onConstructedCandidateArtifact}
              onConstructionConstraintValidationArtifact={props.onConstructionConstraintValidationArtifact}
              onSelectedConstructionRuleChange={props.onSelectedConstructionRuleChange}
            />
          </div>
        </>
      ) : null}
    </section>
  )
}

function LatestObservationAlertInboxSection({
  timeline,
  timelineStatus,
  timelineError,
  openState,
  onOpenLatestObservation,
}: {
  timeline: MonitorDefinitionAlertReviewTimelineResponse | null | undefined
  timelineStatus: MonitorDefinitionAlertReviewSessionState['timelineStatus'] | undefined
  timelineError: string | null | undefined
  openState: LatestObservationOpenState | null | undefined
  onOpenLatestObservation: ((row: MonitorDefinitionAlertReviewTimelineObservationRow) => void | Promise<void>) | undefined
}) {
  const timelineRows = timeline?.items ?? []
  const rows = timelineRows.filter((row): row is MonitorDefinitionAlertReviewTimelineObservationRow => row.event_kind === 'latest_observation_event')
  const timelineMetadata = timeline?.metadata ?? null
  const selectedObservation = openState?.observation ?? null
  const selectedRow = openState?.row ?? null

  return (
    <section className="dashboard-bottom-grid" data-testid="latest-observation-alert-inbox">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Latest Observation Alerts</p></div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Timeline Status</p>
        {timelineStatus === 'loading' ? <p className="helper">Loading alert review timeline…</p> : null}
        {timelineStatus === 'error' ? <p className="helper">{timelineError}</p> : null}
        {timelineStatus === 'ready' && timelineMetadata ? (
          <>
            {!rows.length ? <p className="helper">No observation alerts in this period.</p> : null}
          </>
        ) : null}
      </div>
      {timelineStatus === 'ready' && rows.length ? (
        <div className="summary-card">
          <p className="panel-label">Observation Events</p>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Family</span>
              <span>Definition</span>
              <span>Status</span>
              <span>Cause / Readback</span>
              <span>Review</span>
            </div>
            {rows.map((row) => (
              <div className="list-row list-row-wide" key={row.observation_id} data-testid={`latest-observation-row-${row.observation_id}`}>
                <span>{monitorFamilyLabel(row)}</span>
                <span>{monitorDefinitionLabel(row)}</span>
                <span>{formatObservationStatusLabel(row.observation_status)} · {row.recency_status}</span>
                <span>{formatObservationAlertClassificationLabel(row.alert_classification)} · cause {formatObservationCauseCodeLabel(row.cause_code)}<br />{isDataQualityMonitorIdentity(row) ? dataQualityReadbackLabel(row.data_quality_evidence) : 'benchmark threshold observation'}</span>
                <span>
                  <button className="secondary-button" onClick={() => { void onOpenLatestObservation?.(row) }} type="button">Open observation</button>
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      <div className="summary-card" data-testid="latest-observation-review-surface">
          <p className="panel-label">Observation Review</p>
          {openState?.status === 'loading' ? <p className="helper">Loading persisted observation artifact.</p> : null}
          {openState?.status === 'error' ? <p className="helper">{openState.error}</p> : null}
          {openState?.status === 'idle' ? <p className="helper">Select an observation event above to open the review.</p> : null}
          {openState?.status === 'ready' && selectedObservation && selectedRow ? (
            <>
            <p className="helper">Opened by timeline ids only: {selectedRow.monitor_definition_id} · {selectedRow.observation_id}</p>
            <div className="dashboard-summary compact-summary-grid">
              <div className="summary-card"><p className="stat-label">Observation Status</p><p className="summary-value">{formatObservationStatusLabel(selectedObservation.observation_status)}</p><p className="helper">Classification {formatObservationAlertClassificationLabel(selectedObservation.alert_classification)}</p></div>
              <div className="summary-card"><p className="stat-label">Family</p><p className="summary-value">{monitorFamilyLabel(selectedObservation)}</p><p className="helper">Definition {selectedObservation.monitor_definition_id}</p></div>
              <div className="summary-card"><p className="stat-label">Cause Code</p><p className="summary-value">{formatObservationCauseCodeLabel(selectedObservation.cause_code)}</p><p className="helper">Reason {formatValue(selectedObservation.reason)}</p></div>
              <div className="summary-card"><p className="stat-label">Readback</p><p className="summary-value">{isDataQualityObservationArtifact(selectedObservation) ? 'Input reliability observation' : 'Threshold observation'}</p><p className="helper">{isDataQualityObservationArtifact(selectedObservation) ? 'Read-only persisted data-quality evidence review.' : 'Read-only persisted monitor observation for benchmark-relative threshold drift review.'}</p></div>
            </div>
            {isBenchmarkTrendObservationArtifact(selectedObservation) ? (
              <div className="summary-card">
                <p className="panel-label">Persisted Threshold / Observation Detail</p>
                <p className="helper">Overlay status {selectedObservation.benchmark_observation.status} · confirmation count {selectedObservation.benchmark_observation.confirmation_count} · rule {selectedObservation.benchmark_observation.rule_version}</p>
                <p className="helper">Portfolio risky weight {formatValue(selectedObservation.portfolio_observation.risky_weight)} · cash weight {formatValue(selectedObservation.portfolio_observation.cash_weight)} · positions {selectedObservation.portfolio_observation.position_count}</p>
                <p className="helper">Threshold evaluation performed: {selectedObservation.active_observation.threshold_evaluation_performed ? 'yes' : 'no'} · triggered thresholds: {selectedObservation.active_observation.triggered_thresholds.length}</p>
              </div>
            ) : null}
            {isDataQualityObservationArtifact(selectedObservation) ? <DataQualityEvidenceReadback evidence={selectedObservation.data_quality_evidence} /> : null}
          </>
        ) : null}
      </div>
    </section>
  )
}

function AlertHistoryQueueSection({
  timeline,
  timelineStatus,
  timelineError,
  openState,
  onOpenAlertHistoryReview,
}: {
  timeline: MonitorDefinitionAlertReviewTimelineResponse | null | undefined
  timelineStatus: MonitorDefinitionAlertReviewSessionState['timelineStatus'] | undefined
  timelineError: string | null | undefined
  openState: AlertHistoryOpenState | null | undefined
  onOpenAlertHistoryReview: ((row: MonitorDefinitionAlertReviewTimelineHistoryRow) => void | Promise<void>) | undefined
}) {
  const timelineRows = timeline?.items ?? []
  const rows = timelineRows.filter((row): row is MonitorDefinitionAlertReviewTimelineHistoryRow => row.event_kind === 'evaluation_history_event')
  const timelineMetadata = timeline?.metadata ?? null
  const selectedRow = openState?.row ?? null
  const selectedEntry = openState?.entry?.item ?? null

  return (
    <section className="dashboard-bottom-grid" data-testid="alert-history-queue">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Alert History Queue</p></div>
      </div>
      <div className="summary-card">
        <p className="panel-label">Timeline Status</p>
        {timelineStatus === 'loading' ? <p className="helper">Loading alert review timeline…</p> : null}
        {timelineStatus === 'error' ? <p className="helper">{timelineError}</p> : null}
        {timelineStatus === 'ready' && timelineMetadata ? (
          <>
            {!rows.length ? <p className="helper">No alert history in this period.</p> : null}
          </>
        ) : null}
      </div>
      {timelineStatus === 'ready' && rows.length ? (
        <div className="summary-card">
          <p className="panel-label">History Events</p>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Family</span>
              <span>Definition</span>
              <span>Outcome</span>
              <span>Cause / Readback</span>
              <span>Review</span>
            </div>
            {rows.map((row) => (
              <div className="list-row list-row-wide" key={row.history_entry_id} data-testid={`alert-history-row-${row.history_entry_id}`}>
                <span>{monitorFamilyLabel(row)}</span>
                <span>{monitorDefinitionLabel(row)}</span>
                <span>{formatAlertHistoryOutcomeLabel(row.outcome_status)} · {formatAlertHistorySignificanceLabel(row.significance_status)} · {row.latest_for_monitor_definition ? 'latest' : 'historical'}</span>
                <span>{formatAlertHistoryReviewSupportLabel(row.review_support_status)} · cause {formatObservationCauseCodeLabel(row.cause_code)}<br />{isDataQualityMonitorIdentity(row) ? dataQualityReadbackLabel(row.data_quality_evidence) : 'benchmark threshold history'}</span>
                <span>
                  <button className="secondary-button" onClick={() => { void onOpenAlertHistoryReview?.(row) }} type="button">Open history review</button>
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}
      <div className="summary-card" data-testid="alert-history-review-surface">
        <p className="panel-label">History Review</p>
        {openState?.status === 'loading' ? <p className="helper">Loading persisted evaluation history entry.</p> : null}
        {openState?.status === 'error' ? <p className="helper">{openState.error}</p> : null}
        {openState?.status === 'idle' ? <p className="helper">Select a history event above to open the review.</p> : null}
        {openState?.status === 'ready' && selectedRow && selectedEntry ? (
          <>
            <p className="helper">Opened by timeline ids only: {selectedRow.monitor_definition_id} · {selectedRow.history_entry_id}</p>
            <div className="dashboard-summary compact-summary-grid">
              <div className="summary-card"><p className="stat-label">Outcome</p><p className="summary-value">{formatAlertHistoryOutcomeLabel(selectedEntry.observation_status)}</p><p className="helper">Significance {formatAlertHistorySignificanceLabel(selectedEntry.significance_status)}</p></div>
              <div className="summary-card"><p className="stat-label">Family</p><p className="summary-value">{monitorFamilyLabel(selectedEntry)}</p><p className="helper">Definition {selectedEntry.monitor_definition_id}</p></div>
              <div className="summary-card"><p className="stat-label">Cause Code</p><p className="summary-value">{formatObservationCauseCodeLabel(selectedEntry.cause_code)}</p><p className="helper">Reason {formatValue(selectedEntry.reason)}</p></div>
              <div className="summary-card"><p className="stat-label">Review Support</p><p className="summary-value">{formatAlertHistoryReviewSupportLabel(selectedRow.review_support_status)}</p><p className="helper">{selectedRow.latest_for_monitor_definition ? 'Latest persisted row for this monitor definition.' : 'Historical persisted row for this monitor definition.'}</p></div>
            </div>
            {isBenchmarkTrendHistoryEntry(selectedEntry) ? (
              <div className="summary-card">
                <p className="panel-label">Persisted Threshold / History Detail</p>
                <p className="helper">Overlay status {selectedEntry.benchmark_observation.status} · confirmation count {selectedEntry.benchmark_observation.confirmation_count} · rule {selectedEntry.benchmark_observation.rule_version}</p>
                <p className="helper">Portfolio risky weight {formatValue(selectedEntry.portfolio_observation.risky_weight)} · cash weight {formatValue(selectedEntry.portfolio_observation.cash_weight)} · positions {selectedEntry.portfolio_observation.position_count}</p>
                <p className="helper">Threshold evaluation performed: {selectedEntry.active_observation.threshold_evaluation_performed ? 'yes' : 'no'} · triggered thresholds: {selectedEntry.active_observation.triggered_thresholds.length}</p>
              </div>
            ) : null}
            {isDataQualityHistoryEntry(selectedEntry) ? <DataQualityEvidenceReadback evidence={selectedEntry.data_quality_evidence} /> : null}
          </>
        ) : null}
      </div>
    </section>
  )
}

function CompareWorkspaceSection(props: Props) {
  const [open, setOpen] = useState(true)
  const handleAllocationBacktestResult = props.onAllocationBacktestResult ?? (() => undefined)
  const replayLineageHelper = formatReplayLineageHelper(props.hypotheticalReplayResult)
  const artifactMode = isPersistedConstructionArtifactMode(props)
  const optimizerHandoffMode = isPersistedOptimizerHandoffMode(props)
  const monitorDefinitionAlertReviewSession = props.monitorDefinitionAlertReviewSession ?? null
  const recoveredAlertReviewQueue = props.recoveredAlertReviewQueue ?? []
  const activeAlertEpisodeInbox = props.activeAlertEpisodeInbox ?? { status: 'idle' as const, response: null, error: null }
  const alertEpisodeHistory = props.alertEpisodeHistory ?? { status: 'idle' as const, monitorDefinitionId: null, response: null, error: null }

  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-compare">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Compare</p></div>
        <button className="workspace-collapse-btn" onClick={() => setOpen((o) => !o)} type="button" aria-label={open ? 'Collapse compare section' : 'Expand compare section'}>
          <span className={`workspace-collapsible-chevron${open ? ' open' : ''}`}>▾</span>
        </button>
      </div>
      {open ? (<>
      <div id={WORKFLOW_SECTION_IDS.hypotheticalReplay}>
        <HypotheticalReplaySection
          result={props.allocationBacktestResult}
          draftSnapshot={props.draftSnapshot}
          replacementIntentDraft={props.replacementIntentDraft}
          formedCandidateArtifact={props.formedCandidateArtifact}
          constructedCandidateArtifact={props.constructedCandidateArtifact}
          constructionConstraintValidationArtifact={props.constructionConstraintValidationArtifact}
          selectedConstructionRuleId={props.selectedConstructionRuleId}
          hypotheticalReplayResult={props.hypotheticalReplayResult}
          workspaceSource={props.workspaceSource}
          persistedConstructionArtifactReview={props.persistedConstructionArtifactReview}
          persistedOptimizerHandoffReview={props.persistedOptimizerHandoffReview}
          savedProposalCount={props.savedProposals.length}
          onSaveProposal={props.onSaveProposal}
          onHypotheticalReplayResult={props.onHypotheticalReplayResult}
        />
      </div>
      <div id={WORKFLOW_SECTION_IDS.diagnosticsChange}>
        <section className="dashboard-bottom-grid">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Diagnostics Change</p></div>
          </div>
          {replayLineageHelper ? <p className="helper">{replayLineageHelper}</p> : null}
        </section>
        <DiagnosticsChangeSection result={props.allocationBacktestResult} hypotheticalReplayResult={props.hypotheticalReplayResult} />
      </div>
      {monitorDefinitionAlertReviewSession ? (
        <>
          <LatestObservationAlertInboxSection
            timeline={monitorDefinitionAlertReviewSession.timeline}
            timelineStatus={monitorDefinitionAlertReviewSession.timelineStatus}
            timelineError={monitorDefinitionAlertReviewSession.timelineError}
            openState={monitorDefinitionAlertReviewSession.latestObservation}
            onOpenLatestObservation={props.onOpenLatestObservation}
          />
          <AlertHistoryQueueSection
            timeline={monitorDefinitionAlertReviewSession.timeline}
            timelineStatus={monitorDefinitionAlertReviewSession.timelineStatus}
            timelineError={monitorDefinitionAlertReviewSession.timelineError}
            openState={monitorDefinitionAlertReviewSession.alertHistory}
            onOpenAlertHistoryReview={props.onOpenAlertHistoryReview}
          />
        </>
      ) : null}
      {recoveredAlertReviewQueue.length > 0 ? (
        <RecoveredAlertReviewQueueSection
          rows={recoveredAlertReviewQueue}
          onReopenRecoveredAlertReview={props.onReopenRecoveredAlertReview}
        />
      ) : null}
      <ActiveAlertEpisodeInboxSection
        inbox={activeAlertEpisodeInbox}
        onOpenActiveAlertEpisode={props.onOpenActiveAlertEpisode}
      />
      <AlertEpisodeHistoryDrillInSection
        history={alertEpisodeHistory}
        onOpenAlertEpisodeHistory={props.onOpenAlertEpisodeHistory}
        onLoadOlderAlertEpisodeHistory={props.onLoadOlderAlertEpisodeHistory}
      />
      {artifactMode || optimizerHandoffMode ? null : (
        <>
          <div className="summary-card">
            <p className="panel-label">Legacy Replay Builder</p>
          </div>
          <PortfolioAllocationBacktestPanel result={props.allocationBacktestResult} onResult={handleAllocationBacktestResult} analysis={props.analysis} />
        </>
      )}
      </> ) : null}
    </section>
  )
}

function ProposalWorkspaceSection(props: Props) {
  const [open, setOpen] = useState(true)
  if (isArtifactReviewMode(props)) {
    return null
  }
  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-proposal">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Proposal</p></div>
        <button className="workspace-collapse-btn" onClick={() => setOpen((o) => !o)} type="button" aria-label={open ? 'Collapse proposal section' : 'Expand proposal section'}>
          <span className={`workspace-collapsible-chevron${open ? ' open' : ''}`}>▾</span>
        </button>
      </div>
      {open ? (
        <div id={WORKFLOW_SECTION_IDS.savedProposal}>
          <SavedProposalSection proposals={props.savedProposals} activeThesis={props.activeThesis} openedSavedProposalArtifactId={props.openedSavedProposalArtifactId} onOpenSavedProposal={props.onOpenSavedProposal} onPromoteProposalToThesis={props.onPromoteProposalToThesis} onClearActiveThesis={props.onClearActiveThesis} />
        </div>
      ) : null}
    </section>
  )
}

function ActiveThesisArtifactReview({
  thesis,
  proposals,
  openedSavedProposalArtifactId,
  onOpenSavedProposal,
}: {
  thesis: ActiveThesisArtifact
  proposals: VersionedProposalArtifact[]
  openedSavedProposalArtifactId?: string | null
  onOpenSavedProposal?: (reviewSnapshotArtifactId: string) => void | Promise<void>
}) {
  const [openState, setOpenState] = useState<ActiveThesisOpenState>({ status: 'idle', open: null, error: null })
  const [crossFamilyQueueState, setCrossFamilyQueueState] = useState<ActiveThesisCrossFamilyQueueState>({ status: 'idle', queue: null, error: null })
  const [familyReviewState, setFamilyReviewState] = useState<SavedProposalFamilyReviewState>({ status: 'idle', review: null, error: null })
  const [deltaState, setDeltaState] = useState<ActiveThesisDeltaState>({ status: 'idle', comparison: null, error: null })

  useEffect(() => {
    let active = true
    setOpenState({ status: 'loading', open: null, error: null })
    void (async () => {
      try {
        const handoff = await buildReviewSnapshotOpenHandoffFromProposal(thesis.thesisProposal)
        const response = await fetch('/api/backtests/review-snapshots/open', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(handoff),
        })
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.detail ?? 'Unable to load active thesis PM summary')
        }
        if (!active) return
        const open = assertValidReviewSnapshotOpenResponseEnvelope(payload)
        if (open.pm_summary.role !== 'saved_proposal') {
          throw new Error('Unable to load active thesis PM summary: persisted pm_summary role is invalid for active thesis readout')
        }
        if (open.handoff.artifact_id !== thesis.thesisProposal.reviewSnapshotArtifactId) {
          throw new Error('Unable to load active thesis PM summary: persisted open response artifact does not match active thesis artifact')
        }
        if (open.pm_summary.provenance.lineage.proposal_id !== thesis.sourceProposalId) {
          throw new Error('Unable to load active thesis PM summary: persisted open response lineage does not match active thesis proposal id')
        }
        setOpenState({ status: 'ready', open, error: null })
      } catch (error) {
        if (!active) return
        setOpenState({ status: 'error', open: null, error: error instanceof Error ? error.message : 'Unable to load active thesis PM summary' })
      }
    })()
    return () => {
      active = false
    }
  }, [thesis])

  useEffect(() => {
    let active = true
    setCrossFamilyQueueState({ status: 'loading', queue: null, error: null })
    void (async () => {
      try {
        const handoff = await buildReviewSnapshotOpenHandoffFromProposal(thesis.thesisProposal)
        const response = await fetch('/api/backtests/review-snapshots/active-thesis-cross-family-queue', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            source_proposal_id: thesis.sourceProposalId,
            handoff,
          }),
        })
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.detail ?? 'Unable to load active thesis cross-family PM review queue')
        }
        if (!active) return
        const queue = assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(payload)
        if (queue.active_thesis.source_proposal_id !== thesis.sourceProposalId) {
          throw new Error('Unable to load active thesis cross-family PM review queue: active thesis proposal id does not match the workspace thesis')
        }
        if (queue.active_thesis.handoff.artifact_id !== thesis.thesisProposal.reviewSnapshotArtifactId) {
          throw new Error('Unable to load active thesis cross-family PM review queue: active thesis artifact does not match the workspace thesis')
        }
        if (queue.active_thesis.lineage.proposal_id !== thesis.sourceProposalId) {
          throw new Error('Unable to load active thesis cross-family PM review queue: active thesis lineage does not match the workspace thesis')
        }
        setCrossFamilyQueueState({ status: 'ready', queue, error: null })
      } catch (error) {
        if (!active) return
        setCrossFamilyQueueState({ status: 'error', queue: null, error: error instanceof Error ? error.message : 'Unable to load active thesis cross-family PM review queue' })
      }
    })()
    return () => {
      active = false
    }
  }, [thesis])

  useEffect(() => {
    if (!crossFamilyQueueState.queue) {
      return
    }
    const knownArtifactIds = new Set(proposals.map((proposal) => proposal.reviewSnapshotArtifactId))
    if (crossFamilyQueueState.queue.rows.some((row) => !knownArtifactIds.has(row.latest_identity.artifact_id))) {
      setCrossFamilyQueueState({
        status: 'error',
        queue: null,
        error: 'Active thesis cross-family PM review queue latest artifact is not indexed by any saved proposal',
      })
    }
  }, [crossFamilyQueueState.queue, proposals])

  useEffect(() => {
    let active = true
    if (openState.status !== 'ready' || !openState.open) {
      setFamilyReviewState({ status: 'idle', review: null, error: null })
      return () => {
        active = false
      }
    }
    const open = openState.open
    setFamilyReviewState({ status: 'loading', review: null, error: null })
    void (async () => {
      try {
        const response = await fetch('/api/backtests/review-snapshots/family-review', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ handoff: open.handoff }),
        })
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.detail ?? 'Unable to load active thesis same-family review')
        }
        if (!active) return
        const review = assertValidReviewSnapshotFamilyReviewResponseEnvelope(payload)
        if (review.anchor.identity.artifact_id !== open.handoff.artifact_id) {
          throw new Error('Unable to load active thesis same-family review: anchor artifact does not match active thesis artifact')
        }
        setFamilyReviewState({ status: 'ready', review, error: null })
      } catch (error) {
        if (!active) return
        setFamilyReviewState({ status: 'error', review: null, error: error instanceof Error ? error.message : 'Unable to load active thesis same-family review' })
      }
    })()
    return () => {
      active = false
    }
  }, [openState.open, openState.status])

  useEffect(() => {
    let active = true
    if (familyReviewState.status !== 'ready' || !familyReviewState.review || !openState.open) {
      setDeltaState({ status: 'idle', comparison: null, error: null })
      return () => {
        active = false
      }
    }

    const open = openState.open
    const compatibleSiblingIds = familyReviewState.review.anchor.comparison_eligibility.compatible_sibling_artifact_ids
    if (!compatibleSiblingIds.length) {
      setDeltaState({ status: 'idle', comparison: null, error: null })
      return () => {
        active = false
      }
    }
    if (compatibleSiblingIds.length !== 1) {
      setDeltaState({ status: 'error', comparison: null, error: 'Unable to load active thesis same-family delta: ambiguous sibling selection' })
      return () => {
        active = false
      }
    }

    const sibling = familyReviewState.review.siblings.find((item) => item.identity.artifact_id === compatibleSiblingIds[0]) ?? null
    if (!sibling) {
      setDeltaState({ status: 'error', comparison: null, error: 'Unable to load active thesis same-family delta: compatible sibling artifact is missing from family review' })
      return () => {
        active = false
      }
    }

    setDeltaState({ status: 'loading', comparison: null, error: null })
    void (async () => {
      try {
        const response = await fetch('/api/backtests/review-snapshots/compare', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            baseline: buildReviewSnapshotComparisonRef(sibling.identity, 'baseline'),
            candidate: buildReviewSnapshotComparisonRef(open.artifact.identity, 'candidate'),
          }),
        })
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.detail ?? 'Unable to load active thesis same-family delta')
        }
        if (!active) return
        const comparison = assertValidReviewSnapshotComparisonResponseEnvelope(payload)
        if (comparison.baseline_pm_summary.role !== 'baseline' || comparison.candidate_pm_summary.role !== 'candidate') {
          throw new Error('Unable to load active thesis same-family delta: persisted comparison roles are invalid')
        }
        if (comparison.candidate_pm_summary.provenance.lineage.proposal_id !== thesis.sourceProposalId) {
          throw new Error('Unable to load active thesis same-family delta: candidate lineage does not match active thesis proposal id')
        }
        setDeltaState({ status: 'ready', comparison, error: null })
      } catch (error) {
        if (!active) return
        setDeltaState({ status: 'error', comparison: null, error: error instanceof Error ? error.message : 'Unable to load active thesis same-family delta' })
      }
    })()
    return () => {
      active = false
    }
  }, [familyReviewState.review, familyReviewState.status, openState.open, thesis.sourceProposalId])

  const activeSummary = openState.open?.pm_summary ?? null
  const crossFamilyQueue = crossFamilyQueueState.queue
  const siblingCount = familyReviewState.review?.siblings.length ?? 0

  return (
    <section className="dashboard-bottom-grid" data-testid="active-thesis-artifact-review">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Active Thesis Artifact Review</p></div>
        <p className="helper">Artifact-backed only. PM summary and same-family delta readouts use the persisted review-snapshot open and compare routes, never draft reconstruction or local fallback state.</p>
      </div>
      <div className="summary-card" data-testid="active-thesis-pm-summary-status">
        <p className="panel-label">Canonical PM Summary</p>
        {openState.status === 'loading' ? <p className="helper">Loading active thesis PM summary from persisted review snapshot open.</p> : null}
        {openState.status === 'error' ? <p className="helper">{openState.error}</p> : null}
        {openState.status === 'ready' && activeSummary ? (
          <>
            <p className="helper">Role: {activeSummary.role} · provenance: {activeSummary.provenance.source} · artifact: {openState.open?.handoff.artifact_id}</p>
            <p className="helper">Family: {activeSummary.provenance.lineage.proposal_family_id} · proposal: {activeSummary.provenance.lineage.proposal_id} · version: v{activeSummary.provenance.lineage.version_number}</p>
            <p className="helper">Benchmark: {activeSummary.review_basis.benchmark_symbol} · window: {activeSummary.review_basis.replay_window.start_date} {'->'} {activeSummary.review_basis.replay_window.end_date}</p>
            <p className="helper">Methodology: {activeSummary.methodology.methodology} · replay type: {activeSummary.replay_type} · diagnostics available: {activeSummary.diagnostics_summary.diagnostics_available ? 'yes' : 'no'}</p>
          </>
        ) : null}
      </div>
      <div className="summary-card" data-testid="active-thesis-cross-family-queue-status">
        <p className="panel-label">Cross-Family PM Review Queue</p>
        {crossFamilyQueueState.status === 'loading' ? <p className="helper">Loading active thesis cross-family PM review queue from persisted discovery.</p> : null}
        {crossFamilyQueueState.status === 'error' ? <p className="helper">{crossFamilyQueueState.error}</p> : null}
        {crossFamilyQueueState.status === 'ready' && crossFamilyQueue ? (
          <>
            <p className="helper">Queued families: {crossFamilyQueue.rows.length} · provenance: {crossFamilyQueue.provenance}</p>
            <p className="helper">Active thesis family excluded: {crossFamilyQueue.active_thesis.family_key.proposal_family_id} · ordering: {crossFamilyQueue.queue_ordering}</p>
            {!crossFamilyQueue.rows.length ? <p className="helper">No persisted cross-family PM review rows are available for the active thesis lineage.</p> : null}
          </>
        ) : null}
      </div>
      {crossFamilyQueueState.status === 'ready' && crossFamilyQueue && crossFamilyQueue.rows.length ? (
        <div className="summary-card" data-testid="active-thesis-cross-family-queue">
          <p className="panel-label">Queued PM Review Rows</p>
          <p className="helper">Metadata-only discovery. Cross-family queue rows open the existing saved-proposal PM review flow without becoming same-family review or comparison implicitly.</p>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Family</span>
              <span>Latest artifact</span>
              <span>PM summary fields</span>
              <span>Review actions</span>
            </div>
            {crossFamilyQueue.rows.map((row) => {
              const isOpened = row.latest_identity.artifact_id === openedSavedProposalArtifactId
              return (
                <div className="list-row list-row-wide" data-testid={`active-thesis-cross-family-queue-row-${row.latest_identity.artifact_id}`} key={row.latest_identity.artifact_id}>
                  <span>
                    {row.family_key.proposal_family_id}
                    <br />
                    v{row.lineage.version_number} · proposal {row.lineage.proposal_id}
                  </span>
                  <span>
                    {row.latest_identity.artifact_id}
                    <br />
                    Saved {formatProposalTimestamp(row.latest_saved_at)}
                  </span>
                  <span>
                    {formatProposalSourceKind(row.proposal_source.proposal_source_kind)} · replay {formatReplayStatusLabel(row.pm_summary_fields.replay_status)}
                    <br />
                    {row.pm_summary_fields.review_basis.benchmark_symbol} · investor economics {row.trust_visibility.investor_economics_status.status}
                  </span>
                  <span>
                    {onOpenSavedProposal ? (
                      <button className={isOpened ? 'primary-button' : 'secondary-button'} type="button" onClick={() => void onOpenSavedProposal(row.latest_identity.artifact_id)}>
                        {isOpened ? 'Opened In PM Review' : 'Open PM Review'}
                      </button>
                    ) : <p className="helper">Open action unavailable.</p>}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}
      <div className="summary-card" data-testid="active-thesis-delta-status">
        <p className="panel-label">Same-Family Delta</p>
        {familyReviewState.status === 'loading' ? <p className="helper">Loading active thesis same-family siblings from persisted family review.</p> : null}
        {familyReviewState.status === 'error' ? <p className="helper">{familyReviewState.error}</p> : null}
        {familyReviewState.status === 'ready' && familyReviewState.review ? <p className="helper">Persisted same-family siblings: {siblingCount} · compare policy: {familyReviewState.review.compare_selection_policy}</p> : null}
        {deltaState.status === 'loading' ? <p className="helper">Loading artifact-backed same-family delta with explicit baseline and candidate roles.</p> : null}
        {deltaState.status === 'error' ? <p className="helper">{deltaState.error}</p> : null}
        {deltaState.status === 'idle' && familyReviewState.status === 'ready' && familyReviewState.review?.anchor.comparison_eligibility.reason === 'no_compatible_family_sibling' ? (
          <p className="helper">No compatible persisted same-family sibling is available for active thesis delta review.</p>
        ) : null}
      </div>
      {deltaState.status === 'ready' && deltaState.comparison ? (
        <div className="summary-card" data-testid="active-thesis-delta-readout">
          <p className="panel-label">Active Thesis Delta Readout</p>
          <p className="helper">Baseline: v{deltaState.comparison.baseline_pm_summary.provenance.lineage.version_number} · proposal {deltaState.comparison.baseline_pm_summary.provenance.lineage.proposal_id} · role {deltaState.comparison.baseline_pm_summary.role}</p>
          <p className="helper">Candidate: v{deltaState.comparison.candidate_pm_summary.provenance.lineage.version_number} · proposal {deltaState.comparison.candidate_pm_summary.provenance.lineage.proposal_id} · role {deltaState.comparison.candidate_pm_summary.role}</p>
          <p className="helper">Provenance: {deltaState.comparison.provenance} · benchmark separation: {deltaState.comparison.benchmark_separation}</p>
          <p className="helper">Methodology consistent: {deltaState.comparison.methodology.methodology_consistent ? 'yes' : 'no'} · assumptions consistent: {deltaState.comparison.assumptions.assumptions_consistent ? 'yes' : 'no'}</p>
        </div>
      ) : null}
    </section>
  )
}

const WORKFLOW_SECTION_IDS = {
  currentPortfolio: 'workflow-section-current-portfolio',
  candidateIdea: 'workflow-section-candidate-idea',
  candidateFormation: 'workflow-section-candidate-formation',
  constructionRule: 'workflow-section-construction-rule',
  constructionConstraints: 'workflow-section-construction-constraints',
  hypotheticalReplay: 'workflow-section-hypothetical-replay',
  diagnosticsChange: 'workflow-section-diagnostics-change',
  savedProposal: 'workflow-section-saved-proposal',
} as const

type WorkflowSectionStatus = 'ready' | 'in_progress' | 'blocked' | 'recorded'

function workflowStatusLabel(status: WorkflowSectionStatus) {
  if (status === 'in_progress') return 'In progress'
  if (status === 'blocked') return 'Blocked'
  if (status === 'recorded') return 'Recorded'
  return 'Ready'
}

function workflowStatusTextClass(status: WorkflowSectionStatus) {
  if (status === 'ready' || status === 'recorded') return 'positive-text'
  if (status === 'blocked') return 'negative-text'
  return 'neutral-text'
}

function workflowStatusCardClass(status: WorkflowSectionStatus) {
  if (status === 'ready' || status === 'recorded') return 'metric-card-cool'
  if (status === 'blocked') return 'metric-card-hot'
  return 'metric-card-neutral'
}

function formatWorkflowTaskGuidance({
  summary,
  missing,
  unlocksNext,
}: {
  summary: string
  missing: string
  unlocksNext: string
}) {
  if (missing.startsWith('nothing ')) {
    return `${summary} Nothing else is needed right now. Next up: ${unlocksNext}.`
  }
  if (missing === 'proposal recording is intentionally disabled in this read-only mode') {
    return `${summary} Proposal recording stays unavailable in this read-only review. Next up: ${unlocksNext}.`
  }
  if (missing.startsWith('no additional ')) {
    return `${summary} This read-only review already has what it needs. Next up: ${unlocksNext}.`
  }
  return `${summary} Missing now: ${missing}. Unlocks next: ${unlocksNext}.`
}

function buildWorkflowStatusCards(props: Props): WorkflowSpineCard[] {
  const hasCurrentPortfolio = Boolean(props.analysis || props.draftSnapshot)
  const artifactMode = isArtifactReviewMode(props)
  const hasCandidateSeed = Boolean(props.candidateImprovementDraft || props.intentBoundSeededEtfReplacementRankingDraft)
  const hasReplacementIntent = Boolean(props.replacementIntentDraft)
  const hasFormedCandidate = Boolean(
    props.replacementIntentDraft
    && props.formedCandidateArtifact
    && props.formedCandidateArtifact.replacementIntentCreatedAt === props.replacementIntentDraft.createdAt
    && props.formedCandidateArtifact.replacementIntentBaseSymbol === props.replacementIntentDraft.baseSymbol
    && props.formedCandidateArtifact.replacementIntentCandidateSymbol === props.replacementIntentDraft.candidateSymbol
    && props.formedCandidateArtifact.formation.formation.status === 'ok',
  )
  const hasRejectedFormation = Boolean(
    props.replacementIntentDraft
    && props.formedCandidateArtifact
    && props.formedCandidateArtifact.replacementIntentCreatedAt === props.replacementIntentDraft.createdAt
    && props.formedCandidateArtifact.replacementIntentBaseSymbol === props.replacementIntentDraft.baseSymbol
    && props.formedCandidateArtifact.replacementIntentCandidateSymbol === props.replacementIntentDraft.candidateSymbol
    && props.formedCandidateArtifact.formation.formation.status === 'rejected',
  )
  const hasConstructedCandidate = Boolean(
    props.replacementIntentDraft
    && props.constructedCandidateArtifact
    && props.constructedCandidateArtifact.replacementIntentCreatedAt === props.replacementIntentDraft.createdAt
    && props.constructedCandidateArtifact.replacementIntentBaseSymbol === props.replacementIntentDraft.baseSymbol
    && props.constructedCandidateArtifact.replacementIntentCandidateSymbol === props.replacementIntentDraft.candidateSymbol
    && props.constructedCandidateArtifact.constructionRuleId === props.selectedConstructionRuleId
    && props.constructedCandidateArtifact.construction.construction.status === 'ok',
  )
  const hasConstraintValidation = Boolean(
    props.replacementIntentDraft
    && props.constructionConstraintValidationArtifact
    && props.constructionConstraintValidationArtifact.replacementIntentCreatedAt === props.replacementIntentDraft.createdAt
    && props.constructionConstraintValidationArtifact.replacementIntentBaseSymbol === props.replacementIntentDraft.baseSymbol
    && props.constructionConstraintValidationArtifact.replacementIntentCandidateSymbol === props.replacementIntentDraft.candidateSymbol
    && props.constructionConstraintValidationArtifact.constructionRuleId === props.selectedConstructionRuleId,
  )
  const hasPassingConstraintValidation = Boolean(hasConstraintValidation && props.constructionConstraintValidationArtifact?.validation.validation.status === 'ok')
  const hasBlockedConstraintValidation = Boolean(hasConstraintValidation && props.constructionConstraintValidationArtifact?.validation.validation.status === 'blocked')
  const hasRejectedConstraintValidation = Boolean(hasConstraintValidation && props.constructionConstraintValidationArtifact?.validation.validation.status === 'rejected')
  const hasRejectedConstruction = Boolean(
    props.replacementIntentDraft
    && props.constructedCandidateArtifact
    && props.constructedCandidateArtifact.replacementIntentCreatedAt === props.replacementIntentDraft.createdAt
    && props.constructedCandidateArtifact.replacementIntentBaseSymbol === props.replacementIntentDraft.baseSymbol
    && props.constructedCandidateArtifact.replacementIntentCandidateSymbol === props.replacementIntentDraft.candidateSymbol
    && props.constructedCandidateArtifact.constructionRuleId === props.selectedConstructionRuleId
    && props.constructedCandidateArtifact.construction.construction.status === 'rejected',
  )
  const hasStaleConstruction = Boolean(
    props.replacementIntentDraft
    && props.constructedCandidateArtifact
    && (
      props.constructedCandidateArtifact.replacementIntentCreatedAt !== props.replacementIntentDraft.createdAt
      || props.constructedCandidateArtifact.replacementIntentBaseSymbol !== props.replacementIntentDraft.baseSymbol
      || props.constructedCandidateArtifact.replacementIntentCandidateSymbol !== props.replacementIntentDraft.candidateSymbol
      || props.constructedCandidateArtifact.constructionRuleId !== props.selectedConstructionRuleId
    ),
  )
  const activeReplay = getActiveReplay(props)
  const hasReplay = Boolean(activeReplay)
  const hasDiagnostics = Boolean(activeReplay?.diagnostics_comparison)
  const hasSavedProposal = props.savedProposals.length > 0
  const workflowStatusCard = (key: string, title: string, status: WorkflowSectionStatus, detail: string): WorkflowSpineCard => ({
    key,
    title,
    status,
    value: workflowStatusLabel(status),
    detail,
    sectionId: workflowSectionIdForCard(key, props),
  })

  return [
    workflowStatusCard(
      'current-portfolio-status',
      'Current Portfolio',
      hasCurrentPortfolio ? 'ready' : 'blocked',
      hasCurrentPortfolio
        ? formatWorkflowTaskGuidance({
          summary: artifactMode ? 'Artifact review basis is available.' : 'Portfolio basis is available.',
          missing: artifactMode ? 'no additional current-portfolio input for this reopened review basis' : 'nothing at the portfolio-basis step',
          unlocksNext: artifactMode ? 'review the candidate and replay evidence already attached to this artifact-backed path' : 'candidate selection and replacement-intent work',
        })
        : formatWorkflowTaskGuidance({
          summary: 'Portfolio basis is not loaded.',
          missing: 'an imported or restored portfolio basis',
          unlocksNext: 'candidate selection once current portfolio truth is available',
        }),
    ),
    workflowStatusCard(
      'candidate-idea-status',
      'Candidate Idea',
      artifactMode ? 'recorded' : hasReplacementIntent ? 'ready' : hasCandidateSeed ? 'in_progress' : 'blocked',
      artifactMode
         ? formatWorkflowTaskGuidance({
           summary: isPersistedOptimizerHandoffMode(props) ? 'Candidate review comes from the persisted optimizer handoff reopened by handoff reference.' : 'Candidate review comes from the persisted construction artifact payload.',
           missing: 'no additional candidate-selection input in this read-only mode',
           unlocksNext: 'review the formation and replay evidence already attached to the reopened artifact',
         })
        : hasReplacementIntent
        ? formatWorkflowTaskGuidance({
          summary: 'A replacement intent is attached and ready for replay review.',
          missing: 'nothing at the candidate-idea step',
          unlocksNext: 'candidate formation for the active hypothetical path',
        })
        : hasCandidateSeed
          ? formatWorkflowTaskGuidance({
            summary: 'A candidate seed exists for this workflow.',
            missing: 'an explicit replacement intent',
            unlocksNext: 'candidate formation after the seed is promoted',
          })
          : formatWorkflowTaskGuidance({
              summary: 'No seeded candidate is attached yet.',
              missing: 'a seeded candidate or explicit replacement intent',
              unlocksNext: 'the hypothetical path once ETF Ranking provides a candidate',
          }),
    ),
    workflowStatusCard(
      'candidate-formation-status',
      'Candidate Formation',
      artifactMode ? 'recorded' : hasFormedCandidate ? 'ready' : hasRejectedFormation ? 'blocked' : hasReplacementIntent ? 'in_progress' : 'blocked',
      artifactMode
         ? formatWorkflowTaskGuidance({
           summary: isPersistedOptimizerHandoffMode(props) ? 'Formation is already embedded in the persisted optimizer handoff review lineage reopened by handoff reference.' : 'Formation is already embedded in the persisted construction artifact review lineage.',
           missing: 'no additional formation task in this read-only mode',
           unlocksNext: 'review the construction and replay lineage already reopened in workspace',
         })
        : hasFormedCandidate
        ? formatWorkflowTaskGuidance({
          summary: 'A formed candidate artifact is available for review-only replay handoff.',
          missing: 'nothing at candidate formation',
          unlocksNext: 'construction for the active rule selection',
        })
        : hasRejectedFormation
          ? formatWorkflowTaskGuidance({
            summary: 'Candidate formation rejected the active replacement intent.',
            missing: 'a formable replacement intent',
            unlocksNext: 'construction after formation succeeds',
          })
          : hasReplacementIntent
            ? formatWorkflowTaskGuidance({
              summary: 'The workflow can form a review-only candidate now.',
              missing: 'a formed candidate artifact',
              unlocksNext: 'construction once formation completes',
            })
            : formatWorkflowTaskGuidance({
              summary: 'Candidate formation cannot run yet.',
              missing: 'an explicit replacement intent',
              unlocksNext: 'candidate formation once the intent is created',
            }),
    ),
    workflowStatusCard(
      'construction-rule-status',
      'Construction Rule',
      artifactMode ? 'recorded' : hasConstructedCandidate ? 'ready' : hasRejectedConstruction ? 'blocked' : hasFormedCandidate ? 'in_progress' : 'blocked',
      artifactMode
         ? formatWorkflowTaskGuidance({
           summary: isPersistedOptimizerHandoffMode(props) ? 'The persisted optimizer handoff reference is the replay handoff under review.' : 'The persisted construction artifact is the replay handoff under review.',
           missing: 'no additional construction rerun in this read-only mode',
           unlocksNext: 'review constraint, replay, and diagnostics evidence from the reopened artifact',
         })
        : hasConstructedCandidate
        ? formatWorkflowTaskGuidance({
          summary: `A construction artifact is available for review-only replay handoff under ${props.selectedConstructionRuleId}.`,
          missing: 'nothing at the construction step',
          unlocksNext: 'construction-constraint validation for this handoff',
        })
        : hasRejectedConstruction
          ? formatWorkflowTaskGuidance({
            summary: 'Construction rule rejected the active replacement intent.',
            missing: `a constructible candidate for ${props.selectedConstructionRuleId}`,
            unlocksNext: 'constraint validation after construction succeeds',
          })
          : hasStaleConstruction
            ? formatWorkflowTaskGuidance({
              summary: `The selected construction rule is ${props.selectedConstructionRuleId}, but the saved construction artifact is stale.`,
              missing: `a fresh construction artifact for ${props.selectedConstructionRuleId}`,
              unlocksNext: 'constraint validation for the current rule selection',
            })
          : hasFormedCandidate
            ? formatWorkflowTaskGuidance({
              summary: `The workflow can build review-only construction output now with ${props.selectedConstructionRuleId}.`,
              missing: `a construction artifact for ${props.selectedConstructionRuleId}`,
              unlocksNext: 'construction-constraint validation once construction completes',
            })
            : formatWorkflowTaskGuidance({
              summary: 'Construction cannot run yet.',
              missing: 'a valid formed candidate artifact',
              unlocksNext: 'construction once candidate formation succeeds',
            }),
    ),
    workflowStatusCard(
      'construction-constraints-status',
      'Construction Constraints',
      artifactMode ? 'recorded' : hasPassingConstraintValidation ? 'ready' : hasBlockedConstraintValidation || hasRejectedConstraintValidation ? 'blocked' : hasConstructedCandidate ? 'in_progress' : 'blocked',
      artifactMode
         ? formatWorkflowTaskGuidance({
           summary: 'Truth-separation and persisted replay provenance are available for review from the artifact payload.',
           missing: 'no additional constraint-validation task in this read-only mode',
           unlocksNext: 'review the reopened replay evidence already backed by the artifact lineage',
         })
        : hasPassingConstraintValidation
        ? formatWorkflowTaskGuidance({
          summary: 'Constraint validation passed for the current constructed candidate and replay can use that handoff.',
          missing: 'nothing at the constraint-validation step',
          unlocksNext: 'the hypothetical replay run',
        })
        : hasBlockedConstraintValidation
          ? formatWorkflowTaskGuidance({
            summary: 'Constraint validation blocked the current constructed candidate, so replay remains unavailable.',
            missing: 'a constraint-compliant construction handoff',
            unlocksNext: 'the hypothetical replay once constraints pass',
          })
          : hasRejectedConstraintValidation
            ? formatWorkflowTaskGuidance({
              summary: 'Constraint validation rejected the current constructed candidate and replay remains unavailable.',
              missing: 'a safe-to-evaluate construction handoff',
              unlocksNext: 'the hypothetical replay once validation succeeds',
            })
            : hasConstructedCandidate
              ? formatWorkflowTaskGuidance({
                summary: 'Construction output is ready for constraint validation.',
                missing: 'a constraint-validation result for the current constructed candidate',
                unlocksNext: 'the hypothetical replay handoff',
              })
              : formatWorkflowTaskGuidance({
                summary: 'Construction constraints cannot run yet.',
                missing: 'a current accepted construction artifact',
                unlocksNext: 'constraint validation once construction succeeds',
              }),
    ),
    workflowStatusCard(
      'hypothetical-replay-status',
      'Hypothetical Replay',
      (artifactMode || props.hypotheticalReplayResult) ? 'ready' : hasPassingConstraintValidation ? 'in_progress' : 'blocked',
      artifactMode
         ? formatWorkflowTaskGuidance({
           summary: 'Replay evidence is loaded from the artifact review basis.',
           missing: 'no additional replay run inside this read-only mode',
           unlocksNext: 'review diagnostics and artifact-backed replay evidence already in workspace',
         })
        : props.hypotheticalReplayResult
        ? formatWorkflowTaskGuidance({
          summary: 'A draft-only hypothetical replay is available for review.',
          missing: 'nothing at the replay step',
          unlocksNext: 'diagnostics review and saved-proposal recording',
        })
        : hasPassingConstraintValidation
          ? formatWorkflowTaskGuidance({
            summary: 'The workflow can run a hypothetical replay now from the validated construction handoff.',
            missing: 'replay evidence for the current validated handoff',
            unlocksNext: 'diagnostics review and proposal recording',
          })
          : formatWorkflowTaskGuidance({
             summary: 'Hypothetical replay cannot run yet.',
             missing: 'passed construction constraints',
             unlocksNext: 'the hypothetical replay once constraint validation passes',
          }),
    ),
    workflowStatusCard(
      'diagnostics-change-status',
      'Diagnostics Change',
      (artifactMode || hasDiagnostics) ? 'ready' : hasReplay ? 'in_progress' : 'blocked',
      artifactMode
         ? formatWorkflowTaskGuidance({
           summary: 'Diagnostics change comes from the replay attached to the artifact review basis.',
           missing: 'no additional diagnostics-generation task in this read-only mode',
           unlocksNext: 'artifact-backed diagnostics review from the loaded replay',
         })
        : hasDiagnostics
        ? formatWorkflowTaskGuidance({
          summary: 'Diagnostics delta review is available from the active replay.',
          missing: 'nothing at the diagnostics step',
          unlocksNext: 'proposal recording if you want an immutable review artifact',
        })
        : hasReplay
          ? formatWorkflowTaskGuidance({
            summary: 'Replay exists, but diagnostics comparison is not available yet.',
            missing: 'diagnostics comparison output from replay',
            unlocksNext: 'diagnostics review once the replay includes diagnostics deltas',
          })
          : formatWorkflowTaskGuidance({
             summary: 'Diagnostics change cannot be reviewed yet.',
             missing: 'hypothetical replay evidence',
             unlocksNext: 'diagnostics review after replay runs',
          }),
    ),
    workflowStatusCard(
      'saved-proposal-status',
      'Saved Proposal',
      artifactMode ? 'blocked' : hasSavedProposal ? 'recorded' : props.hypotheticalReplayResult ? 'in_progress' : 'blocked',
      artifactMode
         ? formatWorkflowTaskGuidance({
           summary: isPersistedOptimizerHandoffMode(props) ? 'Saved proposal flows are not exposed in persisted optimizer handoff review mode.' : 'Saved proposal flows are not exposed in persisted construction artifact review mode.',
           missing: 'proposal recording is intentionally disabled in this read-only mode',
           unlocksNext: 'open and review the existing artifact-backed evidence only',
         })
        : hasSavedProposal
        ? formatWorkflowTaskGuidance({
          summary: 'An immutable proposal artifact has been recorded for this workflow.',
          missing: 'nothing at the proposal-recording step',
          unlocksNext: 'saved-proposal reopen, comparison, or thesis-promotion review',
        })
        : props.hypotheticalReplayResult
          ? formatWorkflowTaskGuidance({
            summary: 'A replay review is available and can be saved as a proposal artifact.',
            missing: 'a saved proposal artifact',
            unlocksNext: 'saved-proposal reopen and comparison flows',
          })
          : formatWorkflowTaskGuidance({
              summary: 'No saved proposal exists yet.',
              missing: 'a completed hypothetical replay review',
              unlocksNext: 'proposal recording after replay review exists',
          }),
    ),
  ]
}

function workflowSectionIdForCard(cardKey: string, props: Props) {
  const artifactMode = isArtifactReviewMode(props)

  if (cardKey === 'current-portfolio-status') return WORKFLOW_SECTION_IDS.currentPortfolio
  if (cardKey === 'candidate-idea-status') return artifactMode ? null : WORKFLOW_SECTION_IDS.candidateIdea
  if (cardKey === 'candidate-formation-status') return artifactMode ? null : WORKFLOW_SECTION_IDS.candidateFormation
  if (cardKey === 'construction-rule-status') return artifactMode ? null : WORKFLOW_SECTION_IDS.constructionRule
  if (cardKey === 'construction-constraints-status') return artifactMode ? null : WORKFLOW_SECTION_IDS.constructionConstraints
  if (cardKey === 'hypothetical-replay-status') return WORKFLOW_SECTION_IDS.hypotheticalReplay
  if (cardKey === 'diagnostics-change-status') return WORKFLOW_SECTION_IDS.diagnosticsChange
  if (cardKey === 'saved-proposal-status') return artifactMode ? null : WORKFLOW_SECTION_IDS.savedProposal
  return null
}

function WorkflowSpineSection({ props }: { props: Props }) {
  const workflowCards = buildWorkflowStatusCards(props)

  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-workflow-spine">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Workflow Spine</p></div>
        <p className="helper">Authoritative workflow state for the active workspace. Research tools stay adjacent and are not workflow steps.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        {workflowCards.map((card) => (
          <div className={`summary-card metric-card ${workflowStatusCardClass(card.status)} backtest-summary-card`} data-testid={`workflow-spine-card-${card.key}`} key={card.key}>
            <p className="stat-label">{card.title}</p>
            <p className="summary-value">{card.value}</p>
            <p className="helper">{card.detail}</p>
            {card.sectionId ? (
              <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
                <button className="secondary-button" onClick={() => scrollToSection(card.sectionId!)} type="button">Open {card.title}</button>
              </div>
            ) : null}
          </div>
        ))}
      </div>
    </section>
  )
}

function CurrentPortfolioSection({ analysis, draftSnapshot, persistedConstructionArtifactReview = null, persistedOptimizerHandoffReview = null }: { analysis: PortfolioBaselineView | null; draftSnapshot: PortfolioSnapshot | null; persistedConstructionArtifactReview?: PersistedConstructionArtifactWorkspaceReview | null; persistedOptimizerHandoffReview?: PersistedOptimizerHandoffWorkspaceReview | null }) {
  const artifactReplay = persistedConstructionArtifactReview?.replay.replay ?? null
  const optimizerReplay = persistedOptimizerHandoffReview?.replay.replay ?? null
  const artifactMode = Boolean(persistedConstructionArtifactReview || persistedOptimizerHandoffReview)
  const basisLabel = draftSnapshot ? 'Draft snapshot' : analysis ? 'Imported snapshot' : null

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Current Portfolio</p></div>
        <p className="helper">Current portfolio truth.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Basis</p><p className="summary-value">{formatValue(artifactMode ? 'Artifact review basis' : basisLabel)}</p></div>
        <div className="summary-card"><p className="stat-label">Source</p><p className="summary-value">{formatValue(persistedOptimizerHandoffReview ? 'optimizer_handoff_review' : artifactMode ? 'construction_artifact_review' : draftSnapshot?.importedMeta.importer ?? analysis?.snapshot.statement.importer ?? null)}</p></div>
        <div className="summary-card"><p className="stat-label">Period</p><p className="summary-value">{formatValue(artifactMode ? formatReplayWindow((artifactReplay ?? optimizerReplay)?.candidate_result?.start_date, (artifactReplay ?? optimizerReplay)?.candidate_result?.end_date) : draftSnapshot?.importedMeta.statementPeriod ?? analysis?.snapshot.statement.statement_period ?? null)}</p></div>
        <div className="summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{formatValue(artifactMode ? (artifactReplay ?? optimizerReplay)?.candidate_result?.benchmark_symbol ?? null : draftSnapshot?.metadata.benchmarkSymbol ?? null)}</p></div>
      </div>
    </section>
  )
}

function CandidateIdeaSection({
  candidateImprovementDraft,
  intentBoundSeededEtfReplacementRankingDraft,
  replacementIntentDraft,
  currentPortfolio,
  onCreateReplacementIntent,
  onClearReplacementIntent,
  onOpenPersistedConstructionArtifactReview,
  onOpenEtfRanking,
  onOpenPersistedEtfRankingReview,
}: {
  candidateImprovementDraft: CandidateImprovementDraftArtifact | null
  intentBoundSeededEtfReplacementRankingDraft: IntentBoundSeededEtfReplacementRankingDraftArtifact | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  currentPortfolio: {
    artifact_id: string
    as_of_timestamp: string
    weights: Array<{ symbol: string; weight: number }>
  } | null
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
  onOpenPersistedConstructionArtifactReview?: (constructionArtifactId: string) => void | Promise<void>
  onOpenEtfRanking?: (sectionId?: string) => void
  onOpenPersistedEtfRankingReview?: (artifactId: string) => void | Promise<void>
}) {
  const [showReplacementIntentConfirmation, setShowReplacementIntentConfirmation] = useState(false)
  const hasLocalCandidateIdea = Boolean(candidateImprovementDraft || intentBoundSeededEtfReplacementRankingDraft || replacementIntentDraft)

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Candidate Idea</p></div>
        <p className="helper">Pick a saved ranking run to seed a candidate allocation — then choose &ldquo;Review In Construction&rdquo; to preview how it would be built.</p>
      </div>
      <div className="workspace-step-label">
        <span className="workspace-step-badge">1</span>
        ETF Rankings
      </div>
      <PersistedEtfRankingConstructionBrowser
        currentPortfolio={currentPortfolio}
        onOpenRankingReview={(artifactId) => onOpenPersistedEtfRankingReview?.(artifactId)}
        onOpenConstructionReview={(constructionArtifactId) => onOpenPersistedConstructionArtifactReview?.(constructionArtifactId)}
      />
      <div className="workspace-browser-divider" />
      <div className="workspace-step-label">
        <span className="workspace-step-badge">2</span>
        Replacement Rankings
      </div>
      <PersistedReplacementRankingBrowser
        currentPortfolio={currentPortfolio}
        onOpenConstructionReview={(constructionArtifactId) => onOpenPersistedConstructionArtifactReview?.(constructionArtifactId)}
      />
      <div className="workspace-browser-divider" />
      <div className="workspace-step-label">
        <span className="workspace-step-badge">3</span>
        Generic Rankings
      </div>
      <PersistedGenericRankingConstructionBrowser
        currentPortfolio={currentPortfolio}
        onOpenConstructionReview={(constructionArtifactId) => onOpenPersistedConstructionArtifactReview?.(constructionArtifactId)}
      />
      {!hasLocalCandidateIdea ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">No local candidate idea is attached to this draft yet.</p>
          <p className="helper">Open a saved replacement review or seed a candidate from ETF Ranking to continue.</p>
        </div>
      ) : null}
      {intentBoundSeededEtfReplacementRankingDraft ? <ReplacementRankingReview artifact={intentBoundSeededEtfReplacementRankingDraft} /> : null}
      {candidateImprovementDraft ? (
        <section className="dashboard-bottom-grid">
          <div className="summary-card">
            <p className="panel-label">Seeded Candidate Review</p>
            <p className="helper">Base: {candidateImprovementDraft.seed.baseSymbol} · Candidate: {candidateImprovementDraft.seed.candidateSymbol} · Rank #{candidateImprovementDraft.seed.candidateRank}</p>
            {!replacementIntentDraft ? <p className="helper">Promote it to a replacement intent before replay.</p> : null}
            {!replacementIntentDraft && onCreateReplacementIntent ? (
              <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
                <button className="secondary-button" onClick={() => setShowReplacementIntentConfirmation(true)} type="button">Promote to Replacement Intent</button>
              </div>
            ) : null}
          </div>
          <div className="dashboard-summary compact-summary-grid">
            <div className="summary-card"><p className="stat-label">Incumbent</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.baseSymbol)}</p></div>
            <div className="summary-card"><p className="stat-label">Candidate</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.candidateSymbol)}</p></div>
            <div className="summary-card"><p className="stat-label">Peer Group</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.peerGroup)}</p></div>
            <div className="summary-card"><p className="stat-label">Confidence</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.confidence)}</p></div>
          </div>
        </section>
      ) : null}
      {candidateImprovementDraft && showReplacementIntentConfirmation && !replacementIntentDraft ? (
        <section className="dashboard-bottom-grid">
          <div className="summary-card">
            <p className="panel-label">Create replacement intent</p>
            <p className="helper">Draft intent only. No holdings change is applied here.</p>
            <div className="dashboard-summary compact-summary-grid">
              <div className="summary-card"><p className="stat-label">From</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.baseSymbol)}</p></div>
              <div className="summary-card"><p className="stat-label">To</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.candidateSymbol)}</p></div>
              <div className="summary-card"><p className="stat-label">Truth Class</p><p className="summary-value">Draft intent</p></div>
            </div>
            <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
              {onCreateReplacementIntent ? <button className="primary-button" onClick={() => { void onCreateReplacementIntent(); setShowReplacementIntentConfirmation(false) }} type="button">Create Intent</button> : null}
              <button className="secondary-button" onClick={() => setShowReplacementIntentConfirmation(false)} type="button">Cancel</button>
            </div>
          </div>
        </section>
      ) : null}
      {replacementIntentDraft ? (
        <section className="dashboard-bottom-grid">
          <div className="summary-card">
            <p className="panel-label">Replacement Intent</p>
            <p className="helper">Draft intent only. This handoff does not change holdings.</p>
            <div className="dashboard-summary compact-summary-grid">
              <div className="summary-card"><p className="stat-label">From</p><p className="summary-value">{formatValue(replacementIntentDraft.baseSymbol)}</p></div>
              <div className="summary-card"><p className="stat-label">To</p><p className="summary-value">{formatValue(replacementIntentDraft.candidateSymbol)}</p></div>
              <div className="summary-card"><p className="stat-label">Status</p><p className="summary-value">Draft intent</p></div>
              <div className="summary-card"><p className="stat-label">Source</p><p className="summary-value">ETF Ranking seed</p></div>
            </div>
            {onClearReplacementIntent ? (
              <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
                <button className="secondary-button" onClick={() => void onClearReplacementIntent()} type="button">Clear Intent</button>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}
    </section>
  )
}

function SavedProposalSection({
  proposals,
  activeThesis,
  openedSavedProposalArtifactId,
  onOpenSavedProposal,
  onPromoteProposalToThesis,
  onClearActiveThesis,
}: {
  proposals: VersionedProposalArtifact[]
  activeThesis: ActiveThesisArtifact | null
  openedSavedProposalArtifactId?: string | null
  onOpenSavedProposal?: (reviewSnapshotArtifactId: string) => void | Promise<void>
  onPromoteProposalToThesis: (proposalId: string) => void | Promise<void>
  onClearActiveThesis: () => void | Promise<void>
}) {
  const sortedProposals = useMemo(
    () => [...proposals].sort((left, right) => {
      if (left.versionNumber !== right.versionNumber) return right.versionNumber - left.versionNumber
      return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
    }),
    [proposals],
  )
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(sortedProposals[0]?.id ?? null)
  const [comparisonSelection, setComparisonSelection] = useState<string[]>([])
  const [comparisonState, setComparisonState] = useState<SavedProposalComparisonState>({ status: 'idle', comparison: null, error: null })
  const [familyInboxState, setFamilyInboxState] = useState<SavedProposalFamilyInboxState>({ status: 'idle', inbox: null, error: null })
  const [familyReviewState, setFamilyReviewState] = useState<SavedProposalFamilyReviewState>({ status: 'idle', review: null, error: null })

  useEffect(() => {
    if (!sortedProposals.length) {
      setSelectedProposalId(null)
      return
    }

    if (openedSavedProposalArtifactId) {
      const authoritativeProposal = sortedProposals.find((proposal) => proposal.reviewSnapshotArtifactId === openedSavedProposalArtifactId) ?? null
      setSelectedProposalId(authoritativeProposal?.id ?? null)
      if (authoritativeProposal) {
        return
      }
    }

    setSelectedProposalId((current) => sortedProposals.some((proposal) => proposal.id === current) ? current : sortedProposals[0].id)
  }, [openedSavedProposalArtifactId, sortedProposals])

  useEffect(() => {
    setComparisonSelection((current) => current.filter((proposalId) => sortedProposals.some((proposal) => proposal.id === proposalId)).slice(0, 2))
  }, [sortedProposals])

  const selectedProposal = openedSavedProposalArtifactId
    ? (sortedProposals.find((proposal) => proposal.reviewSnapshotArtifactId === openedSavedProposalArtifactId) ?? null)
    : (sortedProposals.find((proposal) => proposal.id === selectedProposalId) ?? sortedProposals[0] ?? null)
  const latestProposal = sortedProposals[0] ?? null
  const latestProposalCapture = latestProposal ? assertSavedProposalCaptureForWorkspaceShell(latestProposal, 'Saved proposal') : null
  const activeThesisProposalId = activeThesis?.sourceProposalId ?? null
  const activeThesisProposal = activeThesis?.thesisProposal ?? null
  const activeThesisProposalCapture = activeThesisProposal ? assertSavedProposalCaptureForWorkspaceShell(activeThesisProposal, 'Active thesis saved proposal') : null
  const comparisonProposals = useMemo(
    () => comparisonSelection
      .map((proposalId) => sortedProposals.find((proposal) => proposal.id === proposalId) ?? null)
      .filter((proposal): proposal is VersionedProposalArtifact => proposal != null),
    [comparisonSelection, sortedProposals],
  )
  const comparisonReady = comparisonProposals.length === 2
  const selectedFamilyInboxRow = useMemo(
    () => familyInboxState.inbox?.rows.find((row) => row.latest_identity.artifact_id === selectedProposal?.reviewSnapshotArtifactId) ?? null,
    [familyInboxState.inbox, selectedProposal],
  )

  useEffect(() => {
    let active = true
    if (!proposals.length) {
      setFamilyInboxState({ status: 'idle', inbox: null, error: null })
      return () => {
        active = false
      }
    }
    const workspaceId = proposals[0]?.workspaceId ?? null
    if (!workspaceId) {
      setFamilyInboxState({ status: 'error', inbox: null, error: 'Saved proposal family inbox requires workspaceId' })
      return () => {
        active = false
      }
    }
    setFamilyInboxState({ status: 'loading', inbox: null, error: null })
    void (async () => {
      try {
        const response = await fetch('/api/backtests/review-snapshots/family-inbox', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ workspace_id: workspaceId }),
        })
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.detail ?? 'Unable to load saved proposal family inbox')
        }
        if (!active) return
        setFamilyInboxState({ status: 'ready', inbox: assertValidReviewSnapshotFamilyInboxResponseEnvelope(payload), error: null })
      } catch (error) {
        if (!active) return
        setFamilyInboxState({ status: 'error', inbox: null, error: error instanceof Error ? error.message : 'Unable to load saved proposal family inbox' })
      }
    })()
    return () => {
      active = false
    }
  }, [proposals])

  useEffect(() => {
    if (!familyInboxState.inbox) {
      return
    }
    const knownArtifactIds = new Set(sortedProposals.map((proposal) => proposal.reviewSnapshotArtifactId))
    if (familyInboxState.inbox.rows.some((row) => !knownArtifactIds.has(row.latest_identity.artifact_id))) {
      setFamilyInboxState({
        status: 'error',
        inbox: null,
        error: 'Saved proposal family inbox latest artifact is not indexed by any saved proposal',
      })
    }
  }, [familyInboxState.inbox, sortedProposals])

  useEffect(() => {
    let active = true
    if (!selectedProposal) {
      setFamilyReviewState({ status: 'idle', review: null, error: null })
      return () => {
        active = false
      }
    }
    setFamilyReviewState({ status: 'loading', review: null, error: null })
    void (async () => {
      try {
        const handoff = await buildReviewSnapshotOpenHandoffFromProposal(selectedProposal)
        const response = await fetch('/api/backtests/review-snapshots/family-review', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ handoff }),
        })
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.detail ?? 'Unable to load saved proposal family review')
        }
        if (!active) return
        setFamilyReviewState({ status: 'ready', review: assertValidReviewSnapshotFamilyReviewResponseEnvelope(payload), error: null })
      } catch (error) {
        if (!active) return
        setFamilyReviewState({ status: 'error', review: null, error: error instanceof Error ? error.message : 'Unable to load saved proposal family review' })
      }
    })()
    return () => {
      active = false
    }
  }, [selectedProposal])

  useEffect(() => {
    let active = true
    if (!comparisonReady) {
      setComparisonState({ status: 'idle', comparison: null, error: null })
      return () => {
        active = false
      }
    }
    setComparisonState({ status: 'loading', comparison: null, error: null })
    void (async () => {
      try {
        const [baselineRef, candidateRef] = await buildReviewSnapshotComparisonRefs([comparisonProposals[0], comparisonProposals[1]])
        const response = await fetch('/api/backtests/review-snapshots/compare', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ baseline: baselineRef, candidate: candidateRef }),
        })
        const payload = await response.json()
        if (!response.ok) {
          throw new Error(payload.detail ?? 'Unable to compare saved review snapshots')
        }
        if (!active) return
         setComparisonState({ status: 'ready', comparison: assertValidReviewSnapshotComparisonResponseEnvelope(payload), error: null })
      } catch (error) {
        if (!active) return
        setComparisonState({ status: 'error', comparison: null, error: error instanceof Error ? error.message : 'Unable to compare saved review snapshots' })
      }
    })()
    return () => {
      active = false
    }
  }, [comparisonReady, comparisonProposals])

  function toggleComparisonSelection(proposalId: string) {
    setComparisonSelection((current) => {
      if (current.includes(proposalId)) {
        return current.filter((item) => item !== proposalId)
      }
      if (current.length >= 2) {
        return [current[1], proposalId]
      }
      return [...current, proposalId]
    })
  }

  function clearComparisonSelection() {
    setComparisonSelection([])
  }

  function swapComparisonSides() {
    setComparisonSelection((current) => current.length === 2 ? [current[1], current[0]] : current)
  }

  function openProposalFromComparison(proposalId: string) {
    const proposal = sortedProposals.find((item) => item.id === proposalId) ?? null
    if (onOpenSavedProposal) {
      if (!proposal?.reviewSnapshotArtifactId) {
        throw new Error('Saved proposal is missing authoritative reviewSnapshotArtifactId')
      }
      void onOpenSavedProposal(proposal.reviewSnapshotArtifactId)
    } else {
      setSelectedProposalId(proposalId)
    }
    setComparisonSelection([])
  }

  const openedFamilyInboxArtifactId = selectedFamilyInboxRow?.latest_identity.artifact_id ?? openedSavedProposalArtifactId ?? selectedProposal?.reviewSnapshotArtifactId ?? null

  if (!sortedProposals.length) {
    return (
      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Saved Proposal</p></div>
          <p className="helper">Saved review artifacts only.</p>
        </div>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">No saved proposal artifact yet.</p>
          <p className="helper">Save a reviewed replay to reopen it later.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Saved Proposal</p></div>
        <p className="helper">Saved review artifacts only.</p>
      </div>
      {latestProposal ? (
        <div className="summary-card">
          <p className="stat-label">Latest Saved Artifact</p>
          <p className="summary-value">v{latestProposal.versionNumber} · {latestProposalCapture?.proposal.incumbent_symbol} -&gt; {latestProposalCapture?.proposal.candidate_symbol}</p>
          <p className="helper">Recorded {formatProposalTimestamp(latestProposal.createdAt)}</p>
        </div>
      ) : null}
      <div className="summary-card" data-testid="active-thesis-status">
        <p className="panel-label">Active Thesis</p>
        {!activeThesisProposal ? (
          <>
            <p className="summary-value">Not promoted</p>
            <p className="helper">Promote a saved proposal into an active thesis snapshot.</p>
          </>
        ) : (
          <>
            <p className="summary-value">{getProposalLabel(activeThesisProposal)}</p>
            <p className="helper">Promoted {formatProposalTimestamp(activeThesis?.promotedAt ?? activeThesisProposal.createdAt)} from {activeThesisProposal.id}</p>
            <p className="helper">Pair {activeThesisProposalCapture?.proposal.incumbent_symbol} -&gt; {activeThesisProposalCapture?.proposal.candidate_symbol}</p>
            <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
              <button className="secondary-button" data-testid="clear-active-thesis" type="button" onClick={() => void onClearActiveThesis()}>Clear active thesis</button>
            </div>
          </>
        )}
      </div>
      {activeThesis ? <ActiveThesisArtifactReview thesis={activeThesis} proposals={sortedProposals} openedSavedProposalArtifactId={openedSavedProposalArtifactId} onOpenSavedProposal={onOpenSavedProposal} /> : null}
      <div className="list-table">
        <div className="list-row list-row-wide">
          <span>Artifact</span>
          <span>Status</span>
          <span>Review Basis</span>
        </div>
        {sortedProposals.map((proposal, index) => {
          const proposalCapture = assertSavedProposalCaptureForWorkspaceShell(proposal, 'Saved proposal')
          const isSelected = proposal.id === selectedProposal?.id
          const isMarkedForComparison = comparisonSelection.includes(proposal.id)
          const isActiveThesis = proposal.id === activeThesisProposalId
          return (
            <div className="list-row list-row-wide" data-testid={`saved-proposal-row-${proposal.id}`} key={proposal.id}>
              <span>
                v{proposal.versionNumber} · {proposalCapture.proposal.incumbent_symbol} -&gt; {proposalCapture.proposal.candidate_symbol}
                <br />
                {index === 0 ? 'Latest' : 'Saved artifact'} · {formatProposalTimestamp(proposal.createdAt)}
                {isActiveThesis ? <><br />Active thesis</> : null}
              </span>
              <span className={workflowStatusTextClass('recorded')} data-testid={`saved-proposal-status-${proposal.id}`}>{isActiveThesis ? 'active thesis' : isMarkedForComparison ? `compare ${comparisonSelection.indexOf(proposal.id) + 1}` : isSelected ? 'reviewing' : 'recorded'}</span>
              <span>
                {proposalCapture.review_basis.derivation_basis} · {proposalCapture.review_basis.rebalance_frequency}
                <br />
                <button className={isSelected ? 'primary-button' : 'secondary-button'} type="button" onClick={() => {
                  if (onOpenSavedProposal) {
                    if (!proposal.reviewSnapshotArtifactId) {
                      throw new Error('Saved proposal is missing authoritative reviewSnapshotArtifactId')
                    }
                    void onOpenSavedProposal(proposal.reviewSnapshotArtifactId)
                    return
                  }
                  setSelectedProposalId(proposal.id)
                }}>
                  {isSelected ? 'Viewing For Review' : 'Reopen In Workspace'}
                </button>
                <button className="secondary-button" data-testid={`saved-proposal-compare-${proposal.id}`} type="button" onClick={() => toggleComparisonSelection(proposal.id)}>
                  {isMarkedForComparison ? 'Remove From Compare' : 'Compare'}
                </button>
                <button className="secondary-button" data-testid={`saved-proposal-promote-${proposal.id}`} type="button" onClick={() => void onPromoteProposalToThesis(proposal.id)}>
                  {isActiveThesis ? 'Replace Active Thesis' : activeThesisProposal ? 'Replace Active Thesis' : 'Promote To Active Thesis'}
                </button>
              </span>
            </div>
          )
        })}
      </div>
      <div className="summary-card" data-testid="saved-proposal-comparison-status">
        <p className="panel-label">Saved proposal comparison</p>
        <p className="helper">Selected: {comparisonSelection.length}/2</p>
        {familyInboxState.status === 'loading' ? <p className="helper">Loading saved proposal family inbox.</p> : null}
        {familyInboxState.status === 'error' ? <p className="helper">{familyInboxState.error}</p> : null}
        {familyInboxState.status === 'ready' && familyInboxState.inbox ? <p className="helper">Persisted families: {familyInboxState.inbox.rows.length} · provenance: {familyInboxState.inbox.provenance}</p> : null}
        {familyReviewState.status === 'loading' ? <p className="helper">Loading proposal family review artifacts.</p> : null}
        {familyReviewState.status === 'error' ? <p className="helper">{familyReviewState.error}</p> : null}
        {familyReviewState.status === 'ready' && familyReviewState.review ? (
          <>
            <p className="helper">Family: {familyReviewState.review.family_key.proposal_family_id}</p>
            <p className="helper">Persisted siblings: {familyReviewState.review.siblings.length} · compare policy: exactly two distinct family siblings</p>
          </>
        ) : null}
        {sortedProposals.length < 2 ? <p className="helper">Comparison is unavailable until at least two saved proposal artifacts exist.</p> : null}
        {sortedProposals.length >= 2 && !comparisonReady ? <p className="helper">Choose one more saved proposal to open the comparison surface.</p> : null}
      </div>
      {familyInboxState.status === 'ready' && familyInboxState.inbox ? (
        <div className="summary-card" data-testid="saved-proposal-family-inbox">
          <p className="panel-label">Saved Proposal Family Inbox</p>
          <p className="helper">Persisted review-snapshot families only. Rows open the existing PM review flow through the typed review-snapshot handoff boundary.</p>
          <div className="list-table">
            <div className="list-row list-row-wide">
              <span>Family</span>
              <span>Latest / Anchor</span>
              <span>PM summary</span>
              <span>Review actions</span>
            </div>
            {familyInboxState.inbox.rows.map((row) => {
              const isSelectedFamily = selectedFamilyInboxRow?.latest_identity.artifact_id === row.latest_identity.artifact_id
              return (
                <div className="list-row list-row-wide" data-testid={`saved-proposal-family-inbox-row-${row.latest_identity.artifact_id}`} key={row.latest_identity.artifact_id}>
                  <span>
                    {row.family_key.proposal_family_id}
                    <br />
                    {row.sibling_count} sibling{row.sibling_count === 1 ? '' : 's'} · compare {formatCompareReadinessLabel(row.compare_readiness.ready)}
                  </span>
                  <span>
                    {familyInboxRowLabel(row)}
                    <br />
                    {isSelectedFamily ? 'selected family' : 'family row'} · saved {formatProposalTimestamp(row.latest_saved_at)}
                  </span>
                  <span>
                    {formatProposalSourceKind(row.pm_summary.provenance.proposal_source.proposal_source_kind)} · {row.pm_summary.truth_labels.proposal_truth}
                    <br />
                    {row.pm_summary.review_basis.benchmark_symbol} · {row.pm_summary.review_basis.replay_window.start_date} {'->'} {row.pm_summary.review_basis.replay_window.end_date}
                  </span>
                  <span>
                    <button className={row.latest_identity.artifact_id === openedFamilyInboxArtifactId ? 'primary-button' : 'secondary-button'} type="button" onClick={() => {
                      if (onOpenSavedProposal) {
                        void onOpenSavedProposal(row.latest_identity.artifact_id)
                        return
                      }
                      const matchingProposal = sortedProposals.find((proposal) => proposal.reviewSnapshotArtifactId === row.latest_identity.artifact_id) ?? null
                      if (matchingProposal) {
                        setSelectedProposalId(matchingProposal.id)
                      }
                    }}>
                      {row.latest_identity.artifact_id === openedFamilyInboxArtifactId ? 'Opened In PM Review' : 'Open PM Review'}
                    </button>
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      ) : null}
      {familyReviewState.status === 'ready' && familyReviewState.review ? (
        <div className="summary-card" data-testid="saved-proposal-family-review">
          {(() => {
            const review = familyReviewState.review
            return (
              <>
                <p className="panel-label">Proposal Family PM Review</p>
                <p className="helper">Anchor artifact: {review.anchor.identity.artifact_id} · lineage family: {review.family_key.proposal_family_id}</p>
                <div className="list-table">
                  <div className="list-row list-row-wide">
                    <span>Artifact</span>
                    <span>Version</span>
                    <span>Proposal source / truth</span>
                    <span>Replay basis</span>
                  </div>
                  {review.siblings.map((sibling) => (
                    <div className="list-row list-row-wide" key={sibling.identity.artifact_id}>
                      <span>{sibling.identity.artifact_id}</span>
                      <span>v{sibling.lineage.version_number}{sibling.identity.artifact_id === review.anchor.identity.artifact_id ? ' · anchor' : ''}</span>
                      <span>{sibling.pm_summary.provenance.proposal_source.proposal_source_kind} · {sibling.pm_summary.truth_labels.proposal_truth}</span>
                      <span>{sibling.pm_summary.review_basis.benchmark_symbol} · {sibling.pm_summary.review_basis.replay_window.start_date} {'->'} {sibling.pm_summary.review_basis.replay_window.end_date}</span>
                    </div>
                  ))}
                </div>
              </>
            )
          })()}
        </div>
      ) : null}
      {comparisonReady ? (
        <SavedProposalComparisonView
          leftProposal={comparisonProposals[0]}
          rightProposal={comparisonProposals[1]}
          comparisonState={comparisonState}
          onSwapSides={swapComparisonSides}
          onOpenProposal={openProposalFromComparison}
          onClearComparison={clearComparisonSelection}
        />
      ) : null}
      {selectedProposal ? <SavedProposalReadoutSection proposal={selectedProposal} /> : null}
    </section>
  )
}

export function PortfolioImprovementWorkspaceShell(props: Props) {
  const artifactReviewMode = isArtifactReviewMode(props)
  const proposalScopedSavedProposals = artifactReviewMode ? [] : props.savedProposals
  const proposalScopedActiveThesis = artifactReviewMode ? null : props.activeThesis
  const savedProposalContractError = useMemo(() => {
    if (artifactReviewMode) {
      return null
    }
    try {
      proposalScopedSavedProposals.forEach((proposal) => {
        assertSavedProposalProposalCaptureIntegrity(proposal)
      })
      if (proposalScopedActiveThesis?.thesisProposal) {
        assertSavedProposalProposalCaptureIntegrity(proposalScopedActiveThesis.thesisProposal)
      }
      return null
    } catch (error) {
      return formatSavedProposalContractErrorOutcome(error)
    }
  }, [artifactReviewMode, proposalScopedActiveThesis, proposalScopedSavedProposals])
  const shellProps = savedProposalContractError
    ? {
        ...props,
        savedProposals: [],
        activeThesis: null,
      }
    : {
        ...props,
        savedProposals: proposalScopedSavedProposals,
        activeThesis: proposalScopedActiveThesis,
      }

  useEffect(() => {
    if (!shellProps.monitoringResearchHandoff || shellProps.monitoringResearchHandoffDismissed) return
    const targetId = MONITORING_RESEARCH_TARGET_IDS[shellProps.monitoringResearchHandoff.researchTarget]
    const timer = globalThis.setTimeout(() => {
      const target = document.getElementById(targetId)
      if (target && 'scrollIntoView' in target && typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 0)
    return () => globalThis.clearTimeout(timer)
  }, [shellProps.monitoringResearchHandoff, shellProps.monitoringResearchHandoffDismissed])

  return (
    <section className="workspace-section panel">
      <h2>Portfolio Research Workspace</h2>
      {savedProposalContractError ? <p className="error" data-testid="saved-proposal-contract-error">{savedProposalContractError}</p> : null}
      {shellProps.monitoringResearchHandoff && !shellProps.monitoringResearchHandoffDismissed ? (
        <section className="dashboard-bottom-grid" data-testid="monitoring-research-handoff-banner">
          <div className="summary-card">
            <p className="panel-label">Monitoring context</p>
            <p className="helper">
              {shellProps.monitoringResearchHandoff.monitorTitle} · {monitoringResearchTargetLabel(shellProps.monitoringResearchHandoff.researchTarget)}
              {shellProps.monitoringResearchHandoff.replayContext ? ` for ${shellProps.monitoringResearchHandoff.replayContext}` : ''}.
            </p>
            <p className="helper">Context: {shellProps.monitoringResearchHandoff.contextLabel}</p>
            <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
              {shellProps.onDismissMonitoringResearchHandoff ? <button className="secondary-button" onClick={shellProps.onDismissMonitoringResearchHandoff} type="button">Dismiss</button> : null}
            </div>
          </div>
        </section>
      ) : null}
      {isArtifactReviewMode(shellProps) ? (
        <section className="dashboard-bottom-grid" data-testid="persisted-construction-artifact-banner">
          <div className="summary-card">
            <p className="panel-label">{isPersistedOptimizerHandoffMode(shellProps) ? 'Artifact Review Mode' : 'Construction Review'}</p>
            <p className="helper">{isPersistedOptimizerHandoffMode(shellProps) ? 'This workspace reopens a hypothetical artifact-backed optimizer review by persisted handoff reference while keeping replay review surfaces intact.' : "You're now previewing a saved construction. Scroll down to see the allocation and replay details."}</p>
            <p className="helper">Review basis: {isPersistedOptimizerHandoffMode(shellProps) ? optimizerHandoffReviewBasisId(shellProps) : shellProps.persistedConstructionArtifactReview?.constructionArtifactId ?? ((shellProps.workspaceSource && 'constructionArtifactId' in shellProps.workspaceSource) ? shellProps.workspaceSource.constructionArtifactId : 'n/a')}</p>
          </div>
        </section>
      ) : null}
      <OverviewSection {...shellProps} />
      <WorkflowSpineSection props={shellProps} />
      <div id={WORKFLOW_SECTION_IDS.currentPortfolio} data-testid="workspace-section-current-portfolio">
        <CurrentPortfolioSection analysis={shellProps.analysis} draftSnapshot={shellProps.draftSnapshot} persistedConstructionArtifactReview={shellProps.persistedConstructionArtifactReview} persistedOptimizerHandoffReview={shellProps.persistedOptimizerHandoffReview} />
      </div>
      {isArtifactReviewMode(shellProps) ? null : (
        <div id={WORKFLOW_SECTION_IDS.candidateIdea}>
          <CandidateWorkspaceSection {...shellProps} />
        </div>
      )}
      {isArtifactReviewMode(shellProps) ? null : (
        <ResearchToolsSection
          onOpenGenericBacktests={shellProps.onOpenGenericBacktests}
          onOpenStrategyLab={shellProps.onOpenStrategyLab}
          onOpenEtfRanking={shellProps.onOpenEtfRanking}
        />
      )}
      <div id={WORKFLOW_SECTION_IDS.constructionConstraints} />
      <CompareWorkspaceSection {...shellProps} />
      <ProposalWorkspaceSection {...shellProps} />
    </section>
  )
}
