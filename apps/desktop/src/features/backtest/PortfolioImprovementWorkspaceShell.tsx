import { useEffect, useMemo, useState } from 'react'

import { ReplacementRankingReview } from '../portfolio/ReplacementRankingReview'
import type { PortfolioBaselineView, HypotheticalReplayResponse, PortfolioAllocationBacktestResponse, PortfolioDiagnosticsTopCallout, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { CandidateImprovementDraftArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, PortfolioSnapshot, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'
import { CandidateFormationSection, ConstructionRuleSection, DiagnosticsChangeSection, HypotheticalReplaySection, SavedProposalReadoutSection } from './PortfolioAllocationBacktestPanel'

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
        : constructionMatchesIntent && constructionMatchesRule && activeConstruction?.construction.status === 'ok'
          ? 'Not yet run'
          : props.replacementIntentDraft || activeCandidatePair
            ? 'Blocked'
            : 'Unavailable',
      detail: props.hypotheticalReplayResult && activeReplay
        ? activeReplay.comparison?.total_return_diff_pct != null
          ? `Total return delta ${formatSignedPct(activeReplay.comparison.total_return_diff_pct)} versus baseline under the shared replay window.`
          : `Candidate total return ${formatPct(activeReplay.candidate_result.metrics.total_return_pct)} under the shared replay window.`
        : constructionMatchesIntent && constructionMatchesRule && activeConstruction?.construction.status === 'ok'
          ? 'A construction artifact exists, but no hypothetical replay review has been run yet.'
          : props.replacementIntentDraft
            ? 'Hypothetical replay cannot run until construction produces a valid constructed candidate review artifact.'
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
  selectedConstructionRuleId: SingleReplacementConstructionRuleId
  allocationBacktestResult: PortfolioAllocationBacktestResponse | null
  hypotheticalReplayResult: HypotheticalReplayResponse | null
  savedProposals: VersionedProposalArtifact[]
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
  onSaveProposal: () => void | Promise<void>
  onHypotheticalReplayResult: (result: HypotheticalReplayResponse) => void
  onFormedCandidateArtifact: (result: SingleReplacementCandidateFormationResponse) => void
  onConstructedCandidateArtifact: (result: SingleReplacementCandidateConstructionResponse) => void
  onSelectedConstructionRuleChange: (ruleId: SingleReplacementConstructionRuleId) => void
}

const WORKFLOW_SECTION_IDS = {
  currentPortfolio: 'workflow-section-current-portfolio',
  candidateIdea: 'workflow-section-candidate-idea',
  candidateFormation: 'workflow-section-candidate-formation',
  constructionRule: 'workflow-section-construction-rule',
  hypotheticalReplay: 'workflow-section-hypothetical-replay',
  diagnosticsChange: 'workflow-section-diagnostics-change',
  savedProposal: 'workflow-section-saved-proposal',
} as const

type WorkflowSectionStatus = 'ready' | 'in_progress' | 'blocked' | 'recorded'

type WorkflowGuideItem = {
  key: string
  title: string
  status: WorkflowSectionStatus
  guidance: string
  targetId: (typeof WORKFLOW_SECTION_IDS)[keyof typeof WORKFLOW_SECTION_IDS]
}

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

function buildWorkflowGuideItems(props: Props): WorkflowGuideItem[] {
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
      key: 'current-portfolio',
      title: 'Current Portfolio',
      status: hasCurrentPortfolio ? 'ready' : 'blocked',
      guidance: hasCurrentPortfolio
        ? 'Portfolio basis is available for workflow review.'
        : 'Import or restore a portfolio basis before starting the workflow.',
      targetId: WORKFLOW_SECTION_IDS.currentPortfolio,
    },
    {
      key: 'candidate-idea',
      title: 'Candidate Idea',
      status: hasReplacementIntent ? 'ready' : hasCandidateSeed ? 'in_progress' : 'blocked',
      guidance: hasReplacementIntent
        ? 'A replacement intent is attached and ready for replay.'
        : hasCandidateSeed
          ? 'A candidate seed exists; promote it into an explicit replacement intent next.'
          : 'No seeded candidate is attached yet; use ETF Ranking to choose one.',
      targetId: WORKFLOW_SECTION_IDS.candidateIdea,
    },
    {
      key: 'candidate-formation',
      title: 'Candidate Formation',
      status: hasFormedCandidate ? 'ready' : hasRejectedFormation ? 'blocked' : hasReplacementIntent ? 'in_progress' : 'blocked',
      guidance: hasFormedCandidate
        ? 'A formed candidate artifact is available for review-only replay handoff.'
        : hasRejectedFormation
          ? 'Candidate formation rejected the active replacement intent.'
          : hasReplacementIntent
            ? 'The workflow can form a review-only candidate next.'
            : 'Create a replacement intent before candidate formation can run.',
      targetId: WORKFLOW_SECTION_IDS.candidateFormation,
    },
    {
      key: 'construction-rule',
      title: 'Construction Rule',
      status: hasConstructedCandidate ? 'ready' : hasRejectedConstruction ? 'blocked' : hasFormedCandidate ? 'in_progress' : 'blocked',
      guidance: hasConstructedCandidate
        ? `A construction artifact is available for review-only replay handoff under ${props.selectedConstructionRuleId}.`
        : hasRejectedConstruction
          ? 'Construction rule rejected the active replacement intent.'
          : hasStaleConstruction
            ? `The selected construction rule is ${props.selectedConstructionRuleId}; rerun construction because the saved artifact is stale.`
          : hasFormedCandidate
            ? `The workflow can build review-only construction output next with ${props.selectedConstructionRuleId}.`
            : 'Form a valid candidate before the construction rule can run.',
      targetId: WORKFLOW_SECTION_IDS.constructionRule,
    },
    {
      key: 'hypothetical-replay',
      title: 'Hypothetical Replay',
      status: props.hypotheticalReplayResult ? 'ready' : hasConstructedCandidate ? 'in_progress' : 'blocked',
      guidance: props.hypotheticalReplayResult
        ? 'A draft-only hypothetical replay is available for review.'
        : hasConstructedCandidate
          ? 'The workflow can run a hypothetical replay next from the construction artifact.'
          : 'Construct a valid review-only candidate before hypothetical replay can run.',
      targetId: WORKFLOW_SECTION_IDS.hypotheticalReplay,
    },
    {
      key: 'diagnostics-change',
      title: 'Diagnostics Change',
      status: hasDiagnostics ? 'ready' : hasReplay ? 'in_progress' : 'blocked',
      guidance: hasDiagnostics
        ? 'Diagnostics delta review is available from the active replay.'
        : hasReplay
          ? 'Replay exists, but diagnostics comparison is not available yet.'
          : 'Run a replay before diagnostics change can be reviewed.',
      targetId: WORKFLOW_SECTION_IDS.diagnosticsChange,
    },
    {
      key: 'saved-proposal',
      title: 'Saved Proposal',
      status: hasSavedProposal ? 'recorded' : props.hypotheticalReplayResult ? 'in_progress' : 'blocked',
      guidance: hasSavedProposal
        ? 'An immutable proposal artifact has been recorded for this workflow.'
        : props.hypotheticalReplayResult
          ? 'A replay review is available; save it to record a proposal artifact.'
          : 'No saved proposal exists yet; review a hypothetical replay first.',
      targetId: WORKFLOW_SECTION_IDS.savedProposal,
    },
  ]
}

function WorkflowAnalysisGuide({ items }: { items: WorkflowGuideItem[] }) {
  const blockedCount = items.filter((item) => item.status === 'blocked').length
  const readyCount = items.filter((item) => item.status === 'ready' || item.status === 'recorded').length

  const jumpToSection = (targetId: string) => {
    const target = document.getElementById(targetId)
    if (!target) return
    target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Workflow / Analysis Guide</p></div>
        <p className="helper">Shell-owned orientation for the current workspace state. Use it to see what is blocked, what is ready now, and where to review next.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card">
          <p className="stat-label">Guide Status</p>
          <p className="summary-value">{readyCount}/{items.length}</p>
          <p className="helper">Blocked sections: {blockedCount}</p>
        </div>
        {items.map((item) => (
          <div className={`summary-card metric-card backtest-summary-card ${workflowStatusCardClass(item.status)}`} key={item.key}>
            <p className="stat-label">{item.title}</p>
            <p className={`summary-value ${workflowStatusTextClass(item.status)}`}>{workflowStatusLabel(item.status)}</p>
            <p className="helper">{item.guidance}</p>
          </div>
        ))}
      </div>
      <div className="list-table">
        <div className="list-row list-row-wide">
          <span>Section</span>
          <span>Status</span>
          <span>Guidance</span>
          <span>Jump</span>
        </div>
        {items.map((item) => (
          <div className="list-row list-row-wide" key={`guide-${item.key}`}>
            <span>{item.title}</span>
            <span className={workflowStatusTextClass(item.status)}>{workflowStatusLabel(item.status)}</span>
            <span>{item.guidance}</span>
            <span>
              <button className="secondary-button" onClick={() => jumpToSection(item.targetId)} type="button">
                Jump to section
              </button>
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

function PortfolioImprovementDecisionSummary({ props }: { props: Props }) {
  const decisionSummaryCards = buildDecisionSummaryCards(props)

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Portfolio Improvement Decision Summary</p></div>
        <p className="helper">Shell-owned decision summary. This synthesizes current workflow review state only; it does not recommend, approve, or apply any portfolio change.</p>
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
  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Current Portfolio</p></div>
        <p className="helper">Truth class: current draft or imported portfolio truth. This section describes the before-state used for workflow review.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card"><p className="stat-label">Portfolio Value</p><p className="summary-value">{formatMoney(analysis?.overview.total_market_value ?? null)}</p><p className="helper">Current portfolio truth from the imported or draft basis</p></div>
        <div className="summary-card"><p className="stat-label">Positions</p><p className="summary-value">{formatValue(draftSnapshot?.positions.length ?? analysis?.snapshot.positions.length ?? null)}</p><p className="helper">Positive holdings available in the current basis</p></div>
        <div className="summary-card"><p className="stat-label">Benchmark</p><p className="summary-value">{formatValue(draftSnapshot?.metadata.benchmarkSymbol ?? null)}</p><p className="helper">Reference benchmark carried with the current portfolio basis</p></div>
        <div className="summary-card"><p className="stat-label">Source</p><p className="summary-value">{formatValue(draftSnapshot?.importedMeta.importer ?? analysis?.snapshot.statement.importer ?? null)}</p><p className="helper">Importer or draft lineage for the current portfolio truth</p></div>
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
          <p className="helper">Truth class: ranking-derived review metadata only. Seed a candidate from ETF Ranking before replay can validate anything.</p>
        </div>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">No candidate idea is attached to this draft yet.</p>
          <p className="helper">Use ETF Ranking to choose a candidate explicitly, then return here to continue the improvement workflow.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Candidate Idea</p></div>
        <p className="helper">Truth class: ranking-derived review metadata only. This section captures the explicit user choice before hypothetical replay validates it.</p>
      </div>
      {intentBoundSeededEtfReplacementRankingDraft ? <ReplacementRankingReview artifact={intentBoundSeededEtfReplacementRankingDraft} /> : null}
      {candidateImprovementDraft ? (
        <section className="dashboard-bottom-grid">
          <div className="summary-card">
            <p className="panel-label">Seeded Candidate Review</p>
            <p className="helper">This seed carries forward the explicit incumbent/candidate pair and source metadata only. It does not imply a holdings change.</p>
            <p className="helper">Base: {candidateImprovementDraft.seed.baseSymbol} · Candidate: {candidateImprovementDraft.seed.candidateSymbol} · Rank #{candidateImprovementDraft.seed.candidateRank}</p>
            {!replacementIntentDraft ? <p className="helper">Turn this seeded pair into an explicit replacement intent before replay. No candidate is adopted automatically.</p> : null}
            {!replacementIntentDraft && onCreateReplacementIntent ? (
              <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
                <button className="secondary-button" onClick={() => setShowReplacementIntentConfirmation(true)} type="button">Promote to Replacement Intent</button>
              </div>
            ) : null}
          </div>
          <div className="dashboard-summary compact-summary-grid">
            <div className="summary-card"><p className="stat-label">Incumbent</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.baseSymbol)}</p><p className="helper">ETF currently selected as the review base</p></div>
            <div className="summary-card"><p className="stat-label">Candidate</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.candidateSymbol)}</p><p className="helper">ETF carried forward from deterministic ranking</p></div>
            <div className="summary-card"><p className="stat-label">Peer Group</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.peerGroup)}</p><p className="helper">Same-mandate group used during ranking</p></div>
            <div className="summary-card"><p className="stat-label">Confidence</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.confidence)}</p><p className="helper">Trust level carried from the ranking source</p></div>
          </div>
        </section>
      ) : null}
      {candidateImprovementDraft && showReplacementIntentConfirmation && !replacementIntentDraft ? (
        <section className="dashboard-bottom-grid">
          <div className="summary-card">
            <p className="panel-label">Create replacement intent</p>
            <p className="helper">This records an explicit incumbent-to-candidate replacement intent inside the draft. It does not apply the change, endorse it, or run replay by itself.</p>
            <div className="dashboard-summary compact-summary-grid">
              <div className="summary-card"><p className="stat-label">From</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.baseSymbol)}</p></div>
              <div className="summary-card"><p className="stat-label">To</p><p className="summary-value">{formatValue(candidateImprovementDraft.seed.candidateSymbol)}</p></div>
              <div className="summary-card"><p className="stat-label">Truth Class</p><p className="summary-value">Draft intent</p><p className="helper">Review object only; not applied holdings</p></div>
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
            <p className="helper">Truth class: draft intent only. This explicit user-chosen pair is the handoff into hypothetical replay; it does not change holdings.</p>
            <div className="dashboard-summary compact-summary-grid">
              <div className="summary-card"><p className="stat-label">From</p><p className="summary-value">{formatValue(replacementIntentDraft.baseSymbol)}</p></div>
              <div className="summary-card"><p className="stat-label">To</p><p className="summary-value">{formatValue(replacementIntentDraft.candidateSymbol)}</p></div>
              <div className="summary-card"><p className="stat-label">Status</p><p className="summary-value">Draft intent</p><p className="helper">Recorded for review only; not applied to holdings</p></div>
              <div className="summary-card"><p className="stat-label">Source</p><p className="summary-value">ETF Ranking seed</p><p className="helper">Replacement intent remains draft-scoped until replayed and reviewed</p></div>
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

function SavedProposalSection({ proposals }: { proposals: VersionedProposalArtifact[] }) {
  const sortedProposals = useMemo(
    () => [...proposals].sort((left, right) => {
      if (left.versionNumber !== right.versionNumber) return right.versionNumber - left.versionNumber
      return new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()
    }),
    [proposals],
  )
  const [selectedProposalId, setSelectedProposalId] = useState<string | null>(sortedProposals[0]?.id ?? null)

  useEffect(() => {
    if (!sortedProposals.length) {
      setSelectedProposalId(null)
      return
    }

    setSelectedProposalId((current) => sortedProposals.some((proposal) => proposal.id === current) ? current : sortedProposals[0].id)
  }, [sortedProposals])

  const selectedProposal = sortedProposals.find((proposal) => proposal.id === selectedProposalId) ?? sortedProposals[0] ?? null
  const latestProposal = sortedProposals[0] ?? null

  if (!sortedProposals.length) {
    return (
      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Saved Proposal</p></div>
          <p className="helper">Truth class: saved review artifacts only. Saved proposals are immutable review records and do not change applied portfolio truth.</p>
        </div>
        <div className="empty-state-panel compact-empty-state">
          <p className="empty-state-title">No saved proposal artifact yet.</p>
          <p className="helper">Save a reviewed hypothetical replay to create an immutable artifact that can be reopened in review-only mode later.</p>
        </div>
      </section>
    )
  }

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Saved Proposal</p></div>
        <p className="helper">Truth class: saved review artifacts only. Reopening a saved proposal restores immutable review context inside the workspace shell and does not mutate applied portfolio truth.</p>
      </div>
      {latestProposal ? (
        <div className="summary-card">
          <p className="stat-label">Latest Saved Artifact</p>
          <p className="summary-value">v{latestProposal.versionNumber} · {latestProposal.sourceIntent.baseSymbol} -&gt; {latestProposal.sourceIntent.candidateSymbol}</p>
          <p className="helper">Recorded {formatProposalTimestamp(latestProposal.createdAt)}. This remains a review artifact only, not an applied holdings change.</p>
        </div>
      ) : null}
      <div className="list-table">
        <div className="list-row list-row-wide">
          <span>Artifact</span>
          <span>Status</span>
          <span>Review Basis</span>
        </div>
        {sortedProposals.map((proposal, index) => {
          const isSelected = proposal.id === selectedProposal?.id
          return (
            <div className="list-row list-row-wide" key={proposal.id}>
              <span>
                v{proposal.versionNumber} · {proposal.sourceIntent.baseSymbol} -&gt; {proposal.sourceIntent.candidateSymbol}
                <br />
                {index === 0 ? 'Latest' : 'Saved artifact'} · {formatProposalTimestamp(proposal.createdAt)}
              </span>
              <span className={workflowStatusTextClass('recorded')}>{isSelected ? 'reviewing' : 'recorded'}</span>
              <span>
                {proposal.replayBasis.derivationBasis} · {proposal.replayBasis.rebalanceFrequency}
                <br />
                <button className={isSelected ? 'primary-button' : 'secondary-button'} type="button" onClick={() => setSelectedProposalId(proposal.id)}>
                  {isSelected ? 'Viewing For Review' : 'Reopen In Workspace'}
                </button>
              </span>
            </div>
          )
        })}
      </div>
      {selectedProposal ? (
        <>
          <div className="summary-card">
            <p className="panel-label">Review-only proposal view</p>
            <p className="helper">You are reopening an immutable saved artifact for review inside the workspace shell. This does not apply, edit, approve, or otherwise mutate portfolio truth.</p>
          </div>
          <SavedProposalReadoutSection proposal={selectedProposal} />
        </>
      ) : null}
    </section>
  )
}

export function PortfolioImprovementWorkspaceShell(props: Props) {
  const workflowGuideItems = buildWorkflowGuideItems(props)

  return (
    <section className="workspace-section">
      <p className="panel-label">Portfolio Improvement Workspace</p>
      <WorkflowAnalysisGuide items={workflowGuideItems} />
      <PortfolioImprovementDecisionSummary props={props} />
      <div id={WORKFLOW_SECTION_IDS.currentPortfolio}>
        <CurrentPortfolioSection analysis={props.analysis} draftSnapshot={props.draftSnapshot} />
      </div>
      <div id={WORKFLOW_SECTION_IDS.candidateIdea}>
        <CandidateIdeaSection
          candidateImprovementDraft={props.candidateImprovementDraft}
          intentBoundSeededEtfReplacementRankingDraft={props.intentBoundSeededEtfReplacementRankingDraft}
          replacementIntentDraft={props.replacementIntentDraft}
          onCreateReplacementIntent={props.onCreateReplacementIntent}
          onClearReplacementIntent={props.onClearReplacementIntent}
        />
      </div>
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
          selectedConstructionRuleId={props.selectedConstructionRuleId}
          onConstructedCandidateArtifact={props.onConstructedCandidateArtifact}
          onSelectedConstructionRuleChange={props.onSelectedConstructionRuleChange}
        />
      </div>
      <div id={WORKFLOW_SECTION_IDS.hypotheticalReplay}>
        <HypotheticalReplaySection
          result={props.allocationBacktestResult}
          draftSnapshot={props.draftSnapshot}
          replacementIntentDraft={props.replacementIntentDraft}
          formedCandidateArtifact={props.formedCandidateArtifact}
          constructedCandidateArtifact={props.constructedCandidateArtifact}
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
            <p className="helper">Truth class: replay-derived hypothetical diagnostics only. This section isolates the before/after diagnostics change view from replay and saved proposal review.</p>
          </div>
        </section>
        <DiagnosticsChangeSection result={props.allocationBacktestResult} hypotheticalReplayResult={props.hypotheticalReplayResult} />
      </div>
      <div id={WORKFLOW_SECTION_IDS.savedProposal}>
        <SavedProposalSection proposals={props.savedProposals} />
      </div>
    </section>
  )
}
