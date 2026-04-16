import { useEffect, useMemo, useState } from 'react'

import { ReplacementRankingReview } from '../portfolio/ReplacementRankingReview'
import type { PortfolioBaselineView, HypotheticalReplacementReplayResponse, PortfolioAllocationBacktestResponse, PortfolioDiagnosticsTopCallout } from '../portfolio/types'
import type { CandidateImprovementDraftArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, PortfolioSnapshot, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'
import { DiagnosticsChangeSection, HypotheticalReplaySection, SavedProposalReadoutSection } from './PortfolioAllocationBacktestPanel'

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
  return props.hypotheticalReplayResult?.replay ?? props.allocationBacktestResult
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
      key: 'replay',
      title: 'Replay Status',
      value: props.hypotheticalReplayResult
        ? activeReplay?.candidate_result.status ?? 'n/a'
        : props.replacementIntentDraft
          ? 'Not yet run'
          : activeCandidatePair
            ? 'Blocked'
            : 'Unavailable',
      detail: props.hypotheticalReplayResult && activeReplay
        ? activeReplay.comparison?.total_return_diff_pct != null
          ? `Total return delta ${formatSignedPct(activeReplay.comparison.total_return_diff_pct)} versus baseline under the shared replay window.`
          : `Candidate total return ${formatPct(activeReplay.candidate_result.metrics.total_return_pct)} under the shared replay window.`
        : props.replacementIntentDraft
          ? 'An explicit replacement intent exists, but no hypothetical replay review has been run yet.'
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
  allocationBacktestResult: PortfolioAllocationBacktestResponse | null
  hypotheticalReplayResult: HypotheticalReplacementReplayResponse | null
  savedProposals: VersionedProposalArtifact[]
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
  onSaveProposal: () => void | Promise<void>
  onHypotheticalReplayResult: (result: HypotheticalReplacementReplayResponse) => void
}

type WorkflowSectionStatus = 'ready' | 'in_progress' | 'blocked' | 'recorded'

type WorkflowStatusCard = {
  key: string
  title: string
  status: WorkflowSectionStatus
  detail: string
}

function workflowStatusLabel(status: WorkflowSectionStatus) {
  if (status === 'in_progress') return 'in progress'
  return status
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

function buildWorkflowStatuses(props: Props): WorkflowStatusCard[] {
  const hasCurrentPortfolio = Boolean(props.analysis || props.draftSnapshot)
  const hasCandidateSeed = Boolean(props.candidateImprovementDraft || props.intentBoundSeededEtfReplacementRankingDraft)
  const hasReplacementIntent = Boolean(props.replacementIntentDraft)
  const activeReplay = props.hypotheticalReplayResult?.replay ?? props.allocationBacktestResult
  const hasReplay = Boolean(activeReplay)
  const hasDiagnostics = Boolean(activeReplay?.diagnostics_comparison)
  const hasSavedProposal = props.savedProposals.length > 0

  return [
    {
      key: 'current-portfolio',
      title: 'Current Portfolio',
      status: hasCurrentPortfolio ? 'ready' : 'blocked',
      detail: hasCurrentPortfolio
        ? 'Portfolio basis is available for workflow review.'
        : 'Import or restore a portfolio basis before starting the workflow.',
    },
    {
      key: 'candidate-idea',
      title: 'Candidate Idea',
      status: hasReplacementIntent ? 'ready' : hasCandidateSeed ? 'in_progress' : 'blocked',
      detail: hasReplacementIntent
        ? 'A replacement intent is attached and ready for replay.'
        : hasCandidateSeed
          ? 'A candidate seed exists; promote it into an explicit replacement intent next.'
          : 'No seeded candidate is attached yet; use ETF Ranking to choose one.',
    },
    {
      key: 'hypothetical-replay',
      title: 'Hypothetical Replay',
      status: props.hypotheticalReplayResult ? 'ready' : hasReplacementIntent ? 'in_progress' : 'blocked',
      detail: props.hypotheticalReplayResult
        ? 'A draft-only hypothetical replay is available for review.'
        : hasReplacementIntent
          ? 'The workflow can run a hypothetical replay next.'
          : 'Create a replacement intent before hypothetical replay can run.',
    },
    {
      key: 'diagnostics-change',
      title: 'Diagnostics Change',
      status: hasDiagnostics ? 'ready' : hasReplay ? 'in_progress' : 'blocked',
      detail: hasDiagnostics
        ? 'Diagnostics delta review is available from the active replay.'
        : hasReplay
          ? 'Replay exists, but diagnostics comparison is not available yet.'
          : 'Run a replay before diagnostics change can be reviewed.',
    },
    {
      key: 'saved-proposal',
      title: 'Saved Proposal',
      status: hasSavedProposal ? 'recorded' : props.hypotheticalReplayResult ? 'in_progress' : 'blocked',
      detail: hasSavedProposal
        ? 'An immutable proposal artifact has been recorded for this workflow.'
        : props.hypotheticalReplayResult
          ? 'A replay review is available; save it to record a proposal artifact.'
          : 'No saved proposal exists yet; review a hypothetical replay first.',
    },
  ]
}

function WorkflowReadinessStrip({ statuses }: { statuses: WorkflowStatusCard[] }) {
  const blockedCount = statuses.filter((status) => status.status === 'blocked').length
  const readyCount = statuses.filter((status) => status.status === 'ready' || status.status === 'recorded').length

  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Workflow Readiness</p></div>
        <p className="helper">Shell-owned workflow guidance. Use this strip to see what is ready now and which section needs attention next.</p>
      </div>
      <div className="dashboard-summary compact-summary-grid">
        <div className="summary-card metric-card metric-card-neutral backtest-summary-card">
          <p className="stat-label">Ready Sections</p>
          <p className="summary-value">{readyCount}/{statuses.length}</p>
          <p className="helper">Blocked sections: {blockedCount}</p>
        </div>
        {statuses.map((status) => (
          <div className={`summary-card metric-card backtest-summary-card ${workflowStatusCardClass(status.status)}`} key={status.key}>
            <p className="stat-label">{status.title}</p>
            <p className={`summary-value ${workflowStatusTextClass(status.status)}`}>{workflowStatusLabel(status.status)}</p>
            <p className="helper">{status.detail}</p>
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

function SectionStatusGuidance({ statuses }: { statuses: WorkflowStatusCard[] }) {
  return (
    <section className="dashboard-bottom-grid">
      <div className="section-header-inline sector-list-header">
        <div><p className="panel-label">Section Status Guidance</p></div>
        <p className="helper">Read the workflow top-to-bottom. Each section stays shell-owned and describes its current role in the improvement review.</p>
      </div>
      <div className="list-table">
        <div className="list-row list-row-wide">
          <span>Section</span>
          <span>Status</span>
          <span>Guidance</span>
        </div>
        {statuses.map((status) => (
          <div className="list-row list-row-wide" key={`guidance-${status.key}`}>
            <span>{status.title}</span>
            <span className={workflowStatusTextClass(status.status)}>{workflowStatusLabel(status.status)}</span>
            <span>{status.detail}</span>
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
  const workflowStatuses = buildWorkflowStatuses(props)

  return (
    <section className="workspace-section">
      <p className="panel-label">Portfolio Improvement Workspace</p>
      <PortfolioImprovementDecisionSummary props={props} />
      <WorkflowReadinessStrip statuses={workflowStatuses} />
      <SectionStatusGuidance statuses={workflowStatuses} />
      <CurrentPortfolioSection analysis={props.analysis} draftSnapshot={props.draftSnapshot} />
      <CandidateIdeaSection
        candidateImprovementDraft={props.candidateImprovementDraft}
        intentBoundSeededEtfReplacementRankingDraft={props.intentBoundSeededEtfReplacementRankingDraft}
        replacementIntentDraft={props.replacementIntentDraft}
        onCreateReplacementIntent={props.onCreateReplacementIntent}
        onClearReplacementIntent={props.onClearReplacementIntent}
      />
      <HypotheticalReplaySection
        result={props.allocationBacktestResult}
        draftSnapshot={props.draftSnapshot}
        replacementIntentDraft={props.replacementIntentDraft}
        hypotheticalReplayResult={props.hypotheticalReplayResult}
        savedProposalCount={props.savedProposals.length}
        onSaveProposal={props.onSaveProposal}
        onHypotheticalReplayResult={props.onHypotheticalReplayResult}
      />
      <section className="dashboard-bottom-grid">
        <div className="section-header-inline sector-list-header">
          <div><p className="panel-label">Diagnostics Change</p></div>
          <p className="helper">Truth class: replay-derived hypothetical diagnostics only. This section isolates the before/after diagnostics change view from replay and saved proposal review.</p>
        </div>
      </section>
      <DiagnosticsChangeSection result={props.allocationBacktestResult} hypotheticalReplayResult={props.hypotheticalReplayResult} />
      <SavedProposalSection proposals={props.savedProposals} />
    </section>
  )
}
