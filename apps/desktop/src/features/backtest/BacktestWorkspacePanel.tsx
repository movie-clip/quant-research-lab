import { PortfolioAllocationBacktestPanel } from './PortfolioAllocationBacktestPanel'
import { MonitoringPanel } from './MonitoringPanel'
import { PortfolioImprovementWorkspaceShell } from './PortfolioImprovementWorkspaceShell'
import type { HypotheticalReplayResponse, PortfolioAllocationBacktestResponse, PortfolioBaselineView, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { CandidateImprovementDraftArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, PortfolioSnapshot, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'

type Props = {
  allocationBacktestResult: PortfolioAllocationBacktestResponse | null
  onAllocationBacktestResult: (result: PortfolioAllocationBacktestResponse) => void
  analysis: PortfolioBaselineView | null
  draftSnapshot: PortfolioSnapshot | null
  candidateImprovementDraft: CandidateImprovementDraftArtifact | null
  intentBoundSeededEtfReplacementRankingDraft: IntentBoundSeededEtfReplacementRankingDraftArtifact | null
  replacementIntentDraft: ReplacementIntentDraftArtifact | null
  formedCandidateArtifact: FormedCandidateArtifact | null
  constructedCandidateArtifact: ConstructedCandidateArtifact | null
  selectedConstructionRuleId: SingleReplacementConstructionRuleId
  hypotheticalReplayResult: HypotheticalReplayResponse | null
  savedProposals: VersionedProposalArtifact[]
  onSaveProposal: () => void | Promise<void>
  onHypotheticalReplayResult: (result: HypotheticalReplayResponse) => void
  onFormedCandidateArtifact: (result: SingleReplacementCandidateFormationResponse) => void
  onConstructedCandidateArtifact: (result: SingleReplacementCandidateConstructionResponse) => void
  onSelectedConstructionRuleChange: (ruleId: SingleReplacementConstructionRuleId) => void
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
}

export function BacktestWorkspacePanel({ allocationBacktestResult, onAllocationBacktestResult, analysis, draftSnapshot, candidateImprovementDraft, intentBoundSeededEtfReplacementRankingDraft, replacementIntentDraft, formedCandidateArtifact, constructedCandidateArtifact, selectedConstructionRuleId, hypotheticalReplayResult, savedProposals, onSaveProposal, onHypotheticalReplayResult, onFormedCandidateArtifact, onConstructedCandidateArtifact, onSelectedConstructionRuleChange, onCreateReplacementIntent, onClearReplacementIntent }: Props) {
  return (
    <article className="panel">
      <p className="panel-label">Research</p>
      <h2>Portfolio improvement research</h2>
      <p className="lead compact-lead">Use Research for workflow orientation, improvement review, replay diagnostics, overlays, and monitoring.</p>

      <PortfolioImprovementWorkspaceShell analysis={analysis} draftSnapshot={draftSnapshot} candidateImprovementDraft={candidateImprovementDraft} intentBoundSeededEtfReplacementRankingDraft={intentBoundSeededEtfReplacementRankingDraft} replacementIntentDraft={replacementIntentDraft} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} selectedConstructionRuleId={selectedConstructionRuleId} allocationBacktestResult={allocationBacktestResult} hypotheticalReplayResult={hypotheticalReplayResult} savedProposals={savedProposals} onCreateReplacementIntent={onCreateReplacementIntent} onClearReplacementIntent={onClearReplacementIntent} onSaveProposal={onSaveProposal} onHypotheticalReplayResult={onHypotheticalReplayResult} onFormedCandidateArtifact={onFormedCandidateArtifact} onConstructedCandidateArtifact={onConstructedCandidateArtifact} onSelectedConstructionRuleChange={onSelectedConstructionRuleChange} />

      <MonitoringPanel result={allocationBacktestResult} hypotheticalReplayResult={hypotheticalReplayResult} />

      <PortfolioAllocationBacktestPanel result={allocationBacktestResult} onResult={onAllocationBacktestResult} analysis={analysis} />
    </article>
  )
}
