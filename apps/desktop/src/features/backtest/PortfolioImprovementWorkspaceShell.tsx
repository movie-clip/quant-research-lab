import { useEffect, useMemo, useState } from 'react'

import { ReplacementRankingReview } from '../portfolio/ReplacementRankingReview'
import type { MonitoringResearchHandoff, PortfolioBaselineView, HypotheticalReplayResponse, PortfolioAllocationBacktestResponse, PortfolioDiagnosticsTopCallout, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { ActiveThesisArtifact, CandidateImprovementDraftArtifact, ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, PortfolioSnapshot, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'
import { CandidateFormationSection, ConstructionRuleSection, DiagnosticsChangeSection, HypotheticalReplaySection, PortfolioAllocationBacktestPanel, SavedProposalReadoutSection } from './PortfolioAllocationBacktestPanel'
import { MonitoringPanel } from './MonitoringPanel'
import { MONITORING_RESEARCH_TARGET_IDS, monitoringResearchTargetLabel } from './monitoringResearchHandoff'

function formatValue(value: string | number | null | undefined) {
  if (value == null) return 'n/a'
  if (typeof value === 'string') return value.trim() ? value : 'n/a'
  return String(value)
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

function getProposalLabel(proposal: VersionedProposalArtifact) {
  return `v${proposal.versionNumber} · ${proposal.sourceIntent.baseSymbol} -> ${proposal.sourceIntent.candidateSymbol}`
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

function formatCandidateFormationStatus(status: 'ok' | 'rejected' | null | undefined) {
  if (status === 'ok') return 'Formed'
  if (status === 'rejected') return 'Rejected'
  return 'Not yet formed'
}

function formatConstructionStatus(status: 'ok' | 'rejected' | null | undefined) {
  if (status === 'ok') return 'Constructed'
  if (status === 'rejected') return 'Rejected'
  return 'Not yet constructed'
}

function diagnosticsValueLabel(row: PortfolioDiagnosticsTopCallout) {
  if (row.key.includes('hhi') || row.key.includes('beta') || row.key.includes('correlation')) {
    return formatSignedNumber(row.delta_value)
  }
  return formatSignedPct(row.delta_value)
}

type DecisionSummaryCard = {
  key: string
  title: string
  value: string
  detail: string
}

type DiagnosticsTakeaway = {
  group: string
  callout: PortfolioDiagnosticsTopCallout
}

function getLatestProposal(proposals: VersionedProposalArtifact[]) {
  return [...proposals].sort((left, right) => {
    if (left.versionNumber !== right.versionNumber) return right.versionNumber - left.versionNumber
    return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
  })[0] ?? null
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

function getTopDiagnosticsTakeaway(activeReplay: PortfolioAllocationBacktestResponse | null): DiagnosticsTakeaway | null {
  if (!activeReplay?.diagnostics_comparison) return null

  const candidates: DiagnosticsTakeaway[] = [
    activeReplay.diagnostics_comparison.top_concentration_change ? { group: 'Concentration', callout: activeReplay.diagnostics_comparison.top_concentration_change } : null,
    activeReplay.diagnostics_comparison.top_factor_exposure_change ? { group: 'Factor Exposure', callout: activeReplay.diagnostics_comparison.top_factor_exposure_change } : null,
    activeReplay.diagnostics_comparison.top_volatility_change ? { group: 'Volatility & Drawdown', callout: activeReplay.diagnostics_comparison.top_volatility_change } : null,
    activeReplay.diagnostics_comparison.top_risk_contribution_change ? { group: 'Risk Contribution', callout: activeReplay.diagnostics_comparison.top_risk_contribution_change } : null,
    activeReplay.diagnostics_comparison.top_stress_scenario_change ? { group: 'Stress / Scenario', callout: activeReplay.diagnostics_comparison.top_stress_scenario_change } : null,
  ].filter((candidate): candidate is DiagnosticsTakeaway => candidate != null)

  return candidates[0] ?? null
}

function getProposalReplayType(proposal: VersionedProposalArtifact) {
  return 'replay' in proposal.reviewSnapshot ? 'Standard replay' : 'Overlay-aware replay'
}

function getProposalActiveReplay(proposal: VersionedProposalArtifact) {
  return 'replay' in proposal.reviewSnapshot ? proposal.reviewSnapshot.replay : proposal.reviewSnapshot.overlay_replay
}

function formatComparisonDelta(value: number | null | undefined, kind: 'pct' | 'number' | 'money' = 'pct') {
  if (value == null) return 'n/a'
  if (kind === 'money') return `${value > 0 ? '+' : ''}${formatMoney(value)}`
  if (kind === 'number') return `${value > 0 ? '+' : ''}${value.toFixed(2)}`
  return `${value > 0 ? '+' : ''}${value.toFixed(2)}%`
}

function formatReplayStatusLabel(status: string | null | undefined) {
  if (!status) return 'n/a'
  if (status === 'ok') return 'Pass'
  return status
}

type ProposalComparisonMetric = {
  key: string
  label: string
  leftValue: string
  rightValue: string
  delta: string
}

function buildProposalComparisonMetrics(left: VersionedProposalArtifact, right: VersionedProposalArtifact): ProposalComparisonMetric[] {
  const leftReplay = getProposalActiveReplay(left)
  const rightReplay = getProposalActiveReplay(right)

  return [
    {
      key: 'total-return',
      label: 'Candidate total return',
      leftValue: formatPct(leftReplay.candidate_result.metrics.total_return_pct),
      rightValue: formatPct(rightReplay.candidate_result.metrics.total_return_pct),
      delta: formatComparisonDelta((rightReplay.candidate_result.metrics.total_return_pct ?? 0) - (leftReplay.candidate_result.metrics.total_return_pct ?? 0)),
    },
    {
      key: 'volatility',
      label: 'Annualized volatility',
      leftValue: formatPct(leftReplay.candidate_result.metrics.annualized_volatility_pct),
      rightValue: formatPct(rightReplay.candidate_result.metrics.annualized_volatility_pct),
      delta: formatComparisonDelta((rightReplay.candidate_result.metrics.annualized_volatility_pct ?? 0) - (leftReplay.candidate_result.metrics.annualized_volatility_pct ?? 0)),
    },
    {
      key: 'drawdown',
      label: 'Max drawdown',
      leftValue: formatPct(leftReplay.candidate_result.metrics.max_drawdown_pct),
      rightValue: formatPct(rightReplay.candidate_result.metrics.max_drawdown_pct),
      delta: formatComparisonDelta((rightReplay.candidate_result.metrics.max_drawdown_pct ?? 0) - (leftReplay.candidate_result.metrics.max_drawdown_pct ?? 0)),
    },
    {
      key: 'sharpe',
      label: 'Sharpe ratio',
      leftValue: formatValue(leftReplay.candidate_result.metrics.sharpe_ratio),
      rightValue: formatValue(rightReplay.candidate_result.metrics.sharpe_ratio),
      delta: formatComparisonDelta((rightReplay.candidate_result.metrics.sharpe_ratio ?? 0) - (leftReplay.candidate_result.metrics.sharpe_ratio ?? 0), 'number'),
    },
  ]
}

function SavedProposalComparisonView({
  leftProposal,
  rightProposal,
  onSwapSides,
  onOpenProposal,
  onClearComparison,
}: {
  leftProposal: VersionedProposalArtifact
  rightProposal: VersionedProposalArtifact
  onSwapSides: () => void
  onOpenProposal: (proposalId: string) => void
  onClearComparison: () => void
}) {
  const leftReplay = getProposalActiveReplay(leftProposal)
  const rightReplay = getProposalActiveReplay(rightProposal)
  const leftTakeaway = getTopDiagnosticsTakeaway(leftReplay)
  const rightTakeaway = getTopDiagnosticsTakeaway(rightReplay)
  const comparisonMetrics = buildProposalComparisonMetrics(leftProposal, rightProposal)
  const sameReplayType = getProposalReplayType(leftProposal) === getProposalReplayType(rightProposal)
  const sameReplayWindow = leftProposal.replayBasis.startDate === rightProposal.replayBasis.startDate
    && leftProposal.replayBasis.endDate === rightProposal.replayBasis.endDate
  const sameIntentPair = leftProposal.sourceIntent.baseSymbol === rightProposal.sourceIntent.baseSymbol
    && leftProposal.sourceIntent.candidateSymbol === rightProposal.sourceIntent.candidateSymbol
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
          <p className="summary-value">v{leftProposal.versionNumber} · {leftProposal.sourceIntent.baseSymbol} -&gt; {leftProposal.sourceIntent.candidateSymbol}</p>
          <p className="helper">{getProposalReplayType(leftProposal)} · {formatProposalTimestamp(leftProposal.createdAt)}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Right proposal</p>
          <p className="summary-value">v{rightProposal.versionNumber} · {rightProposal.sourceIntent.baseSymbol} -&gt; {rightProposal.sourceIntent.candidateSymbol}</p>
          <p className="helper">{getProposalReplayType(rightProposal)} · {formatProposalTimestamp(rightProposal.createdAt)}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Compatibility</p>
          <p className="summary-value">{sameReplayType && sameReplayWindow ? 'Aligned' : 'Review carefully'}</p>
          <p className="helper">Replay type {sameReplayType ? 'matches' : 'differs'} · window {sameReplayWindow ? 'matches' : 'differs'} · intent pair {sameIntentPair ? 'matches' : 'differs'}.</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Comparison state</p>
          <p className="summary-value">2 of 2 selected</p>
          <p className="helper">Use swap to reverse sides or open either artifact in the full saved-proposal view.</p>
        </div>
      </div>
      <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
        <button className="secondary-button" onClick={onSwapSides} type="button">Swap sides</button>
        <button className="secondary-button" onClick={() => onOpenProposal(leftProposal.id)} type="button">Open full proposal v{leftProposal.versionNumber}</button>
        <button className="secondary-button" onClick={() => onOpenProposal(rightProposal.id)} type="button">Open full proposal v{rightProposal.versionNumber}</button>
        <button className="secondary-button" onClick={onClearComparison} type="button">Clear comparison</button>
      </div>
      <div className="summary-card">
        <p className="panel-label">Key Differences</p>
        <div className="list-table">
          <div className="list-row list-row-wide">
            <span>Metric</span>
            <span>Left</span>
            <span>Right</span>
            <span>Right - left</span>
          </div>
          {comparisonMetrics.map((metric) => (
            <div className="list-row list-row-wide" key={metric.key}>
              <span>{metric.label}</span>
              <span>{metric.leftValue}</span>
              <span>{metric.rightValue}</span>
              <span>{metric.delta}</span>
            </div>
          ))}
        </div>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Left replay status</p>
          <p className="summary-value">{formatReplayStatusLabel(leftReplay.candidate_result.status)}</p>
          <p className="helper">Window {leftProposal.replayBasis.startDate} - {leftProposal.replayBasis.endDate}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Right replay status</p>
          <p className="summary-value">{formatReplayStatusLabel(rightReplay.candidate_result.status)}</p>
          <p className="helper">Window {rightProposal.replayBasis.startDate} - {rightProposal.replayBasis.endDate}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Left diagnostics takeaway</p>
          <p className="summary-value">{leftTakeaway?.callout.label ?? 'Unavailable'}</p>
          <p className="helper">{leftTakeaway ? `${leftTakeaway.group} · ${diagnosticsValueLabel(leftTakeaway.callout)}` : 'No saved diagnostics takeaway is available for this artifact.'}</p>
        </div>
        <div className="summary-card">
          <p className="stat-label">Right diagnostics takeaway</p>
          <p className="summary-value">{rightTakeaway?.callout.label ?? 'Unavailable'}</p>
          <p className="helper">{rightTakeaway ? `${rightTakeaway.group} · ${diagnosticsValueLabel(rightTakeaway.callout)}` : 'No saved diagnostics takeaway is available for this artifact.'}</p>
        </div>
      </div>
      {!diagnosticsAvailable ? (
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">Saved diagnostics takeaway is unavailable for both proposals.</p>
          <p className="helper">Comparison still shows shared replay metrics and saved proposal lineage from the immutable artifacts.</p>
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

function buildDecisionSummaryCards(props: Props): DecisionSummaryCard[] {
  const baselinePositions = props.draftSnapshot?.positions.length ?? props.analysis?.snapshot.positions.length ?? null
  const baselineBenchmark = props.draftSnapshot?.metadata.benchmarkSymbol ?? null
  const activeCandidatePair = getActiveCandidatePair(props)
  const activeFormation = props.formedCandidateArtifact?.formation ?? null
  const activeConstruction = props.constructedCandidateArtifact?.construction ?? null
  const formationMatchesIntent = Boolean(
    props.replacementIntentDraft
    && props.formedCandidateArtifact
    && props.formedCandidateArtifact.replacementIntentCreatedAt === props.replacementIntentDraft.createdAt
    && props.formedCandidateArtifact.replacementIntentBaseSymbol === props.replacementIntentDraft.baseSymbol
    && props.formedCandidateArtifact.replacementIntentCandidateSymbol === props.replacementIntentDraft.candidateSymbol,
  )
  const constructionMatchesIntent = Boolean(
    props.replacementIntentDraft
    && props.constructedCandidateArtifact
    && props.constructedCandidateArtifact.replacementIntentCreatedAt === props.replacementIntentDraft.createdAt
      && props.constructedCandidateArtifact.replacementIntentBaseSymbol === props.replacementIntentDraft.baseSymbol
      && props.constructedCandidateArtifact.replacementIntentCandidateSymbol === props.replacementIntentDraft.candidateSymbol,
  )
  const constructionMatchesRule = Boolean(
    props.constructedCandidateArtifact
    && props.constructedCandidateArtifact.constructionRuleId === props.selectedConstructionRuleId
    && props.constructedCandidateArtifact.construction.construction.rule_id === props.selectedConstructionRuleId,
  )
  const activeConstraintValidation = props.constructionConstraintValidationArtifact?.validation ?? null
  const constraintValidationMatchesIntent = Boolean(
    props.replacementIntentDraft
    && props.constructionConstraintValidationArtifact
    && props.constructionConstraintValidationArtifact.replacementIntentCreatedAt === props.replacementIntentDraft.createdAt
    && props.constructionConstraintValidationArtifact.replacementIntentBaseSymbol === props.replacementIntentDraft.baseSymbol
    && props.constructionConstraintValidationArtifact.replacementIntentCandidateSymbol === props.replacementIntentDraft.candidateSymbol,
  )
  const constraintValidationMatchesRule = Boolean(
    props.constructionConstraintValidationArtifact
    && props.constructionConstraintValidationArtifact.constructionRuleId === props.selectedConstructionRuleId,
  )
  const hasPassingConstraintValidation = Boolean(
    constraintValidationMatchesIntent
    && constraintValidationMatchesRule
    && activeConstraintValidation?.validation.status === 'ok',
  )
  const hasBlockedConstraintValidation = Boolean(
    constraintValidationMatchesIntent
    && constraintValidationMatchesRule
    && activeConstraintValidation?.validation.status === 'blocked',
  )
  const hasRejectedConstraintValidation = Boolean(
    constraintValidationMatchesIntent
    && constraintValidationMatchesRule
    && activeConstraintValidation?.validation.status === 'rejected',
  )
  const activeReplay = getActiveReplay(props)
  const diagnosticsTakeaway = getTopDiagnosticsTakeaway(activeReplay)
  const latestProposal = getLatestProposal(props.savedProposals)

  return [
    {
      key: 'baseline',
      title: 'Baseline',
      value: baselinePositions != null || baselineBenchmark
        ? `${formatValue(baselinePositions)} positions · ${formatValue(baselineBenchmark)} benchmark`
        : 'Not loaded',
      detail: baselinePositions != null || baselineBenchmark
        ? 'Current portfolio basis is available from imported or draft portfolio truth.'
        : 'No current portfolio basis is loaded yet, so the workflow remains review-incomplete.',
    },
    {
      key: 'candidate',
      title: 'Active Candidate',
      value: activeCandidatePair
        ? `${activeCandidatePair.baseSymbol} -> ${activeCandidatePair.candidateSymbol}`
        : 'Not selected',
      detail: props.replacementIntentDraft
        ? 'An explicit replacement intent is attached for draft-only replay review. It is not an applied holdings change.'
        : activeCandidatePair
          ? 'A candidate has been selected, but it has not yet been promoted into an explicit replacement intent.'
          : 'No active candidate or replacement intent exists yet for this workflow.',
    },
    {
      key: 'formation',
      title: 'Candidate Formation',
      value: !props.replacementIntentDraft
        ? 'Blocked'
        : !props.formedCandidateArtifact
          ? formatCandidateFormationStatus(null)
          : !formationMatchesIntent
            ? 'Stale'
            : formatCandidateFormationStatus(activeFormation?.formation.status),
      detail: !props.replacementIntentDraft
        ? 'Candidate formation remains unavailable until an explicit replacement intent exists.'
        : !props.formedCandidateArtifact
          ? 'An explicit replacement intent exists, but no formed candidate review artifact has been created yet.'
        : !formationMatchesIntent
          ? 'The existing formed candidate artifact no longer matches the active replacement intent and cannot be used for replay.'
          : activeFormation?.rejection_reason
              ? `Formation rejected: ${activeFormation.rejection_reason}`
              : 'A formed candidate artifact is available as review-only replay input.',
    },
    {
      key: 'construction',
      title: 'Construction Rule',
      value: !props.replacementIntentDraft
        ? 'Blocked'
        : !formationMatchesIntent || activeFormation?.formation.status !== 'ok'
          ? 'Blocked'
          : !props.constructedCandidateArtifact
            ? `${props.selectedConstructionRuleId} selected`
            : !constructionMatchesIntent || !constructionMatchesRule
              ? 'Stale'
            : formatConstructionStatus(activeConstruction?.construction.status),
      detail: !props.replacementIntentDraft
        ? 'Construction remains blocked until an explicit replacement intent exists.'
        : !formationMatchesIntent || activeFormation?.formation.status !== 'ok'
          ? 'Construction requires a valid formed candidate artifact first.'
        : !props.constructedCandidateArtifact
            ? `Selected rule ${props.selectedConstructionRuleId} is ready to construct, but no construction review artifact has been created yet.`
            : !constructionMatchesIntent
              ? 'The existing construction artifact no longer matches the active replacement intent and cannot be used for replay.'
              : !constructionMatchesRule
                ? `The existing construction artifact was built with ${props.constructedCandidateArtifact.constructionRuleId} and must be rerun for ${props.selectedConstructionRuleId}.`
              : activeConstruction?.rejection_reason
                ? `Construction rejected: ${activeConstruction.rejection_reason}`
                : `A construction artifact is available as review-only replay input for ${props.selectedConstructionRuleId}.`,
    },
    {
      key: 'constraints',
      title: 'Construction Constraints',
      value: !props.replacementIntentDraft
        ? 'Blocked'
        : !constructionMatchesIntent || !constructionMatchesRule || activeConstruction?.construction.status !== 'ok'
          ? 'Blocked'
          : !activeConstraintValidation
            ? 'Not yet validated'
            : !constraintValidationMatchesIntent || !constraintValidationMatchesRule
              ? 'Stale'
              : activeConstraintValidation.validation.status === 'ok'
                ? 'Pass'
                : activeConstraintValidation.validation.status === 'blocked'
                  ? 'Blocked'
                  : 'Rejected',
      detail: !props.replacementIntentDraft
        ? 'Constraint validation remains unavailable until an explicit replacement intent exists.'
        : !constructionMatchesIntent || !constructionMatchesRule || activeConstruction?.construction.status !== 'ok'
          ? 'Constraint validation requires a current accepted construction artifact first.'
          : !activeConstraintValidation
            ? 'The constructed candidate is ready for backend constraint validation before replay.'
            : !constraintValidationMatchesIntent || !constraintValidationMatchesRule
              ? 'The saved constraint validation no longer matches the active replacement intent or selected rule.'
              : activeConstraintValidation.validation.status === 'ok'
                ? 'The constructed candidate passed the locked backend constraint set and can be handed into replay review.'
                : activeConstraintValidation.validation.status === 'blocked'
                  ? `Constraint validation blocked replay with ${activeConstraintValidation.blocking_constraint_ids.length} hard-block result${activeConstraintValidation.blocking_constraint_ids.length === 1 ? '' : 's'}.`
                  : `Constraint validation rejected replay input: ${activeConstraintValidation.rejection_reason ?? 'constructed candidate could not be evaluated safely'}`,
    },
    {
      key: 'selected-rule',
      title: 'Selected Rule',
      value: props.selectedConstructionRuleId,
      detail: props.constructedCandidateArtifact && constructionMatchesIntent && constructionMatchesRule
        ? 'The saved construction artifact matches the active selected rule.'
        : 'Rule selection is shell state only until construction is rerun and a matching review artifact is saved.',
    },
    {
      key: 'replay',
      title: 'Replay Status',
      value: props.hypotheticalReplayResult
        ? activeReplay?.candidate_result.status ?? 'n/a'
        : constructionMatchesIntent && constructionMatchesRule && activeConstruction?.construction.status === 'ok' && hasPassingConstraintValidation
          ? 'Not yet run'
          : props.replacementIntentDraft || activeCandidatePair
            ? 'Blocked'
            : 'Unavailable',
      detail: props.hypotheticalReplayResult && activeReplay
        ? activeReplay.comparison?.total_return_diff_pct != null
          ? `Total return delta ${formatSignedPct(activeReplay.comparison.total_return_diff_pct)} versus baseline under the shared replay window.`
          : `Candidate total return ${formatPct(activeReplay.candidate_result.metrics.total_return_pct)} under the shared replay window.`
        : constructionMatchesIntent && constructionMatchesRule && activeConstruction?.construction.status === 'ok' && hasPassingConstraintValidation
          ? 'A validated construction artifact exists, but no hypothetical replay review has been run yet.'
          : hasBlockedConstraintValidation
            ? 'Hypothetical replay remains unavailable until the current constructed candidate passes construction constraints.'
            : hasRejectedConstraintValidation
              ? 'Hypothetical replay remains unavailable because the current constructed candidate could not be evaluated safely by construction constraints.'
          : props.replacementIntentDraft
            ? 'Hypothetical replay cannot run until construction and constraint validation produce a valid replay handoff.'
            : activeCandidatePair
              ? 'Hypothetical replay cannot run until the selected candidate is promoted into an explicit replacement intent.'
            : 'No replay state exists yet for this workflow.',
    },
    {
      key: 'diagnostics',
      title: 'Diagnostics Takeaway',
      value: diagnosticsTakeaway
        ? diagnosticsTakeaway.callout.label
        : activeReplay
          ? 'Not available'
          : 'Not yet run',
      detail: diagnosticsTakeaway
        ? `${diagnosticsTakeaway.group} shows ${diagnosticsValueLabel(diagnosticsTakeaway.callout)}. ${diagnosticsTakeaway.callout.rationale}`
        : activeReplay
          ? 'Replay state exists, but no diagnostics-change takeaway is available for review yet.'
          : 'Diagnostics change is not available until replay evidence exists.',
    },
    {
      key: 'proposal',
      title: 'Proposal State',
      value: latestProposal
        ? `Recorded v${latestProposal.versionNumber}`
        : props.hypotheticalReplayResult
          ? 'Not yet saved'
          : 'No artifact',
      detail: latestProposal
        ? `Latest immutable artifact captures ${latestProposal.sourceIntent.baseSymbol} -> ${latestProposal.sourceIntent.candidateSymbol} for review only.`
        : props.hypotheticalReplayResult
          ? 'A replay review exists, but no immutable proposal artifact has been recorded yet.'
          : 'No saved proposal artifact exists yet for this workflow.',
    },
  ]
}

type Props = {
  analysis: PortfolioBaselineView | null
  draftSnapshot: PortfolioSnapshot | null
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
  onPromoteProposalToThesis: (proposalId: string) => void | Promise<void>
  onClearActiveThesis: () => void | Promise<void>
  onHypotheticalReplayResult: (result: HypotheticalReplayResponse) => void
  onFormedCandidateArtifact: (result: SingleReplacementCandidateFormationResponse) => void
  onConstructedCandidateArtifact: (result: SingleReplacementCandidateConstructionResponse) => void
  onConstructionConstraintValidationArtifact: (result: SingleReplacementConstructionConstraintValidationResponse) => void
  onSelectedConstructionRuleChange: (ruleId: SingleReplacementConstructionRuleId) => void
  monitoringResearchHandoff?: MonitoringResearchHandoff | null
  monitoringResearchHandoffDismissed?: boolean
  onDismissMonitoringResearchHandoff?: () => void
  onReviewInResearch?: (handoff: MonitoringResearchHandoff) => void
}

function formatOverviewSource(analysis: PortfolioBaselineView | null, draftSnapshot: PortfolioSnapshot | null) {
  return draftSnapshot?.importedMeta.importer ?? analysis?.snapshot.statement.importer ?? null
}

function formatOverviewPeriod(analysis: PortfolioBaselineView | null, draftSnapshot: PortfolioSnapshot | null) {
  return draftSnapshot?.importedMeta.statementPeriod ?? analysis?.snapshot.statement.statement_period ?? null
}

function OverviewSection(props: Props) {
  const positionsCount = props.draftSnapshot?.positions.length ?? props.analysis?.snapshot.positions.length ?? null
  const benchmarkSymbol = props.draftSnapshot?.metadata.benchmarkSymbol ?? 'SPY'

  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-overview">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Overview</p></div>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card">
          <p className="stat-label">Portfolio Value</p>
          <p className="summary-value">{formatMoney(props.analysis?.overview.total_market_value ?? null)}</p>
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
          <p className="stat-label">Imported Basis</p>
          <p className="summary-value">{formatValue(formatOverviewSource(props.analysis, props.draftSnapshot))}</p>
          <p className="helper">{formatValue(formatOverviewPeriod(props.analysis, props.draftSnapshot))}</p>
        </div>
      </div>
      <MonitoringPanel result={props.allocationBacktestResult} hypotheticalReplayResult={props.hypotheticalReplayResult} onReviewInResearch={props.onReviewInResearch} />
      <PortfolioImprovementDecisionSummary props={props} />
    </section>
  )
}

function CandidateWorkspaceSection(props: Props) {
  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-candidate">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Candidate</p></div>
      </div>
      <CandidateIdeaSection
        candidateImprovementDraft={props.candidateImprovementDraft}
        intentBoundSeededEtfReplacementRankingDraft={props.intentBoundSeededEtfReplacementRankingDraft}
        replacementIntentDraft={props.replacementIntentDraft}
        onCreateReplacementIntent={props.onCreateReplacementIntent}
        onClearReplacementIntent={props.onClearReplacementIntent}
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
    </section>
  )
}

function CompareWorkspaceSection(props: Props) {
  const handleAllocationBacktestResult = props.onAllocationBacktestResult ?? (() => undefined)

  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-compare">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Compare</p></div>
      </div>
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
          savedProposalCount={props.savedProposals.length}
          onSaveProposal={props.onSaveProposal}
          onHypotheticalReplayResult={props.onHypotheticalReplayResult}
        />
      </div>
      <div id={WORKFLOW_SECTION_IDS.diagnosticsChange}>
        <section className="dashboard-bottom-grid">
          <div className="section-header-inline sector-list-header">
            <div><p className="panel-label">Diagnostics Change</p></div>
            <p className="helper">Replay-derived diagnostics only.</p>
          </div>
        </section>
        <DiagnosticsChangeSection result={props.allocationBacktestResult} hypotheticalReplayResult={props.hypotheticalReplayResult} />
      </div>
      <div className="summary-card">
        <p className="panel-label">Legacy Replay Builder</p>
        <p className="helper">Temporary bridge while replay work finishes moving into the workspace.</p>
      </div>
      <PortfolioAllocationBacktestPanel result={props.allocationBacktestResult} onResult={handleAllocationBacktestResult} analysis={props.analysis} />
    </section>
  )
}

function ProposalWorkspaceSection(props: Props) {
  return (
    <section className="dashboard-bottom-grid" data-testid="workspace-section-proposal">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Proposal</p></div>
        <p className="helper">Saved proposals stay review-only.</p>
      </div>
      <div id={WORKFLOW_SECTION_IDS.savedProposal}>
        <SavedProposalSection proposals={props.savedProposals} activeThesis={props.activeThesis} onPromoteProposalToThesis={props.onPromoteProposalToThesis} onClearActiveThesis={props.onClearActiveThesis} />
      </div>
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

function buildWorkflowStatusCards(props: Props): DecisionSummaryCard[] {
  const hasCurrentPortfolio = Boolean(props.analysis || props.draftSnapshot)
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

  return [
    {
      key: 'current-portfolio-status',
      title: 'Current Portfolio',
      value: workflowStatusLabel(hasCurrentPortfolio ? 'ready' : 'blocked'),
      detail: hasCurrentPortfolio
        ? 'Portfolio basis is available.'
        : 'Import or restore a portfolio basis.',
    },
    {
      key: 'candidate-idea-status',
      title: 'Candidate Idea',
      value: workflowStatusLabel(hasReplacementIntent ? 'ready' : hasCandidateSeed ? 'in_progress' : 'blocked'),
      detail: hasReplacementIntent
        ? 'A replacement intent is attached and ready for replay.'
        : hasCandidateSeed
          ? 'A candidate seed exists; promote it into an explicit replacement intent next.'
          : 'No seeded candidate is attached yet; use ETF Ranking to choose one.',
    },
    {
      key: 'candidate-formation-status',
      title: 'Candidate Formation',
      value: workflowStatusLabel(hasFormedCandidate ? 'ready' : hasRejectedFormation ? 'blocked' : hasReplacementIntent ? 'in_progress' : 'blocked'),
      detail: hasFormedCandidate
        ? 'A formed candidate artifact is available for review-only replay handoff.'
        : hasRejectedFormation
          ? 'Candidate formation rejected the active replacement intent.'
          : hasReplacementIntent
            ? 'The workflow can form a review-only candidate next.'
            : 'Create a replacement intent before candidate formation can run.',
    },
    {
      key: 'construction-rule-status',
      title: 'Construction Rule',
      value: workflowStatusLabel(hasConstructedCandidate ? 'ready' : hasRejectedConstruction ? 'blocked' : hasFormedCandidate ? 'in_progress' : 'blocked'),
      detail: hasConstructedCandidate
        ? `A construction artifact is available for review-only replay handoff under ${props.selectedConstructionRuleId}.`
        : hasRejectedConstruction
          ? 'Construction rule rejected the active replacement intent.'
          : hasStaleConstruction
            ? `The selected construction rule is ${props.selectedConstructionRuleId}; rerun construction because the saved artifact is stale.`
          : hasFormedCandidate
            ? `The workflow can build review-only construction output next with ${props.selectedConstructionRuleId}.`
            : 'Form a valid candidate before the construction rule can run.',
      },
    {
      key: 'construction-constraints-status',
      title: 'Construction Constraints',
      value: workflowStatusLabel(hasPassingConstraintValidation ? 'ready' : hasBlockedConstraintValidation || hasRejectedConstraintValidation ? 'blocked' : hasConstructedCandidate ? 'in_progress' : 'blocked'),
      detail: hasPassingConstraintValidation
        ? 'Constraint validation passed for the current constructed candidate and replay can use that handoff.'
        : hasBlockedConstraintValidation
          ? 'Constraint validation blocked the current constructed candidate, so replay remains unavailable.'
          : hasRejectedConstraintValidation
            ? 'Constraint validation rejected the current constructed candidate and replay remains unavailable.'
            : hasConstructedCandidate
              ? 'Run construction constraints next to validate the current constructed candidate before replay.'
              : 'Build a valid constructed candidate before construction constraints can run.',
    },
    {
      key: 'hypothetical-replay-status',
      title: 'Hypothetical Replay',
      value: workflowStatusLabel(props.hypotheticalReplayResult ? 'ready' : hasPassingConstraintValidation ? 'in_progress' : 'blocked'),
      detail: props.hypotheticalReplayResult
        ? 'A draft-only hypothetical replay is available for review.'
        : hasPassingConstraintValidation
          ? 'The workflow can run a hypothetical replay next from the validated construction handoff.'
          : 'Construction constraints must pass before hypothetical replay can run.',
    },
    {
      key: 'diagnostics-change-status',
      title: 'Diagnostics Change',
      value: workflowStatusLabel(hasDiagnostics ? 'ready' : hasReplay ? 'in_progress' : 'blocked'),
      detail: hasDiagnostics
        ? 'Diagnostics delta review is available from the active replay.'
        : hasReplay
          ? 'Replay exists, but diagnostics comparison is not available yet.'
          : 'Run a replay before diagnostics change can be reviewed.',
    },
    {
      key: 'saved-proposal-status',
      title: 'Saved Proposal',
      value: workflowStatusLabel(hasSavedProposal ? 'recorded' : props.hypotheticalReplayResult ? 'in_progress' : 'blocked'),
      detail: hasSavedProposal
        ? 'An immutable proposal artifact has been recorded for this workflow.'
        : props.hypotheticalReplayResult
          ? 'A replay review is available; save it to record a proposal artifact.'
          : 'No saved proposal exists yet; review a hypothetical replay first.',
    },
  ]
}

function PortfolioImprovementDecisionSummary({ props }: { props: Props }) {
  const decisionSummaryCards = [...buildDecisionSummaryCards(props), ...buildWorkflowStatusCards(props)]

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Portfolio Improvement Decision Summary</p></div>
        <p className="helper">Current review state only.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        {decisionSummaryCards.map((card) => (
          <div className="summary-card metric-card metric-card-neutral backtest-summary-card" key={card.key}>
            <p className="stat-label">{card.title}</p>
            <p className="summary-value">{card.value}</p>
            <p className="helper">{card.detail}</p>
          </div>
        ))}
      </div>
    </section>
  )
}

function CurrentPortfolioSection({ analysis, draftSnapshot }: { analysis: PortfolioBaselineView | null; draftSnapshot: PortfolioSnapshot | null }) {
  const basisLabel = draftSnapshot ? 'Draft snapshot' : analysis ? 'Imported snapshot' : null

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Current Portfolio</p></div>
        <p className="helper">Current portfolio truth.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Basis</p><p className="summary-value">{formatValue(basisLabel)}</p></div>
        <div className="summary-card"><p className="stat-label">Source</p><p className="summary-value">{formatValue(draftSnapshot?.importedMeta.importer ?? analysis?.snapshot.statement.importer ?? null)}</p></div>
        <div className="summary-card"><p className="stat-label">Period</p><p className="summary-value">{formatValue(draftSnapshot?.importedMeta.statementPeriod ?? analysis?.snapshot.statement.statement_period ?? null)}</p></div>
        <div className="summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{formatValue(draftSnapshot?.metadata.benchmarkSymbol ?? null)}</p></div>
      </div>
    </section>
  )
}

function CandidateIdeaSection({
  candidateImprovementDraft,
  intentBoundSeededEtfReplacementRankingDraft,
  replacementIntentDraft,
  onCreateReplacementIntent,
  onClearReplacementIntent,
}: {
  candidateImprovementDraft: CandidateImprovementDraftArtifact | null
  intentBoundSeededEtfReplacementRankingDraft: IntentBoundSeededEtfReplacementRankingDraftArtifact | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
}) {
  const [showReplacementIntentConfirmation, setShowReplacementIntentConfirmation] = useState(false)

  if (!candidateImprovementDraft && !intentBoundSeededEtfReplacementRankingDraft && !replacementIntentDraft) {
    return (
      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Candidate Idea</p></div>
          <p className="helper">Ranking-derived review metadata only.</p>
        </div>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">No candidate idea is attached to this draft yet.</p>
          <p className="helper">Seed a candidate from ETF Ranking to continue.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Candidate Idea</p></div>
        <p className="helper">Ranking-derived review metadata only.</p>
      </div>
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
  onPromoteProposalToThesis,
  onClearActiveThesis,
}: {
  proposals: VersionedProposalArtifact[]
  activeThesis: ActiveThesisArtifact | null
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

  useEffect(() => {
    if (!sortedProposals.length) {
      setSelectedProposalId(null)
      return
    }

    setSelectedProposalId((current) => sortedProposals.some((proposal) => proposal.id === current) ? current : sortedProposals[0].id)
  }, [sortedProposals])

  useEffect(() => {
    setComparisonSelection((current) => current.filter((proposalId) => sortedProposals.some((proposal) => proposal.id === proposalId)).slice(0, 2))
  }, [sortedProposals])

  const selectedProposal = sortedProposals.find((proposal) => proposal.id === selectedProposalId) ?? sortedProposals[0] ?? null
  const latestProposal = sortedProposals[0] ?? null
  const activeThesisProposalId = activeThesis?.sourceProposalId ?? null
  const activeThesisProposal = activeThesis?.thesisProposal ?? null
  const comparisonProposals = comparisonSelection
    .map((proposalId) => sortedProposals.find((proposal) => proposal.id === proposalId) ?? null)
    .filter((proposal): proposal is VersionedProposalArtifact => proposal != null)
  const comparisonReady = comparisonProposals.length === 2

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
    setSelectedProposalId(proposalId)
    setComparisonSelection([])
  }

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
          <p className="summary-value">v{latestProposal.versionNumber} · {latestProposal.sourceIntent.baseSymbol} -&gt; {latestProposal.sourceIntent.candidateSymbol}</p>
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
            <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
              <button className="secondary-button" data-testid="clear-active-thesis" type="button" onClick={() => void onClearActiveThesis()}>Clear active thesis</button>
            </div>
          </>
        )}
      </div>
      <div className="list-table">
        <div className="list-row list-row-wide">
          <span>Artifact</span>
          <span>Status</span>
          <span>Review Basis</span>
        </div>
        {sortedProposals.map((proposal, index) => {
          const isSelected = proposal.id === selectedProposal?.id
          const isMarkedForComparison = comparisonSelection.includes(proposal.id)
          const isActiveThesis = proposal.id === activeThesisProposalId
          return (
            <div className="list-row list-row-wide" data-testid={`saved-proposal-row-${proposal.id}`} key={proposal.id}>
              <span>
                v{proposal.versionNumber} · {proposal.sourceIntent.baseSymbol} -&gt; {proposal.sourceIntent.candidateSymbol}
                <br />
                {index === 0 ? 'Latest' : 'Saved artifact'} · {formatProposalTimestamp(proposal.createdAt)}
                {isActiveThesis ? <><br />Active thesis</> : null}
              </span>
              <span className={workflowStatusTextClass('recorded')} data-testid={`saved-proposal-status-${proposal.id}`}>{isActiveThesis ? 'active thesis' : isMarkedForComparison ? `compare ${comparisonSelection.indexOf(proposal.id) + 1}` : isSelected ? 'reviewing' : 'recorded'}</span>
              <span>
                {proposal.replayBasis.derivationBasis} · {proposal.replayBasis.rebalanceFrequency}
                <br />
                <button className={isSelected ? 'primary-button' : 'secondary-button'} type="button" onClick={() => setSelectedProposalId(proposal.id)}>
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
        {sortedProposals.length < 2 ? <p className="helper">Comparison is unavailable until at least two saved proposal artifacts exist.</p> : null}
        {sortedProposals.length >= 2 && !comparisonReady ? <p className="helper">Choose one more saved proposal to open the comparison surface.</p> : null}
      </div>
      {comparisonReady ? (
        <SavedProposalComparisonView
          leftProposal={comparisonProposals[0]}
          rightProposal={comparisonProposals[1]}
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
  useEffect(() => {
    if (!props.monitoringResearchHandoff || props.monitoringResearchHandoffDismissed) return
    const targetId = MONITORING_RESEARCH_TARGET_IDS[props.monitoringResearchHandoff.researchTarget]
    const timer = globalThis.setTimeout(() => {
      const target = document.getElementById(targetId)
      if (target && 'scrollIntoView' in target && typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 0)
    return () => globalThis.clearTimeout(timer)
  }, [props.monitoringResearchHandoff, props.monitoringResearchHandoffDismissed])

  return (
    <section className="workspace-section">
      <h2>Portfolio Research Workspace</h2>
      {props.monitoringResearchHandoff && !props.monitoringResearchHandoffDismissed ? (
        <section className="dashboard-bottom-grid" data-testid="monitoring-research-handoff-banner">
          <div className="summary-card">
            <p className="panel-label">Monitoring context</p>
            <p className="helper">
              {props.monitoringResearchHandoff.monitorTitle} · {monitoringResearchTargetLabel(props.monitoringResearchHandoff.researchTarget)}
              {props.monitoringResearchHandoff.replayContext ? ` for ${props.monitoringResearchHandoff.replayContext}` : ''}.
            </p>
            <p className="helper">Context: {props.monitoringResearchHandoff.contextLabel}</p>
            <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
              {props.onDismissMonitoringResearchHandoff ? <button className="secondary-button" onClick={props.onDismissMonitoringResearchHandoff} type="button">Dismiss</button> : null}
            </div>
          </div>
        </section>
      ) : null}
      <OverviewSection {...props} />
      <div id={WORKFLOW_SECTION_IDS.currentPortfolio} data-testid="workspace-section-current-portfolio">
        <CurrentPortfolioSection analysis={props.analysis} draftSnapshot={props.draftSnapshot} />
      </div>
      <div id={WORKFLOW_SECTION_IDS.candidateIdea}>
        <CandidateWorkspaceSection {...props} />
      </div>
      <div id={WORKFLOW_SECTION_IDS.constructionConstraints} />
      <CompareWorkspaceSection {...props} />
      <ProposalWorkspaceSection {...props} />
    </section>
  )
}
