import { PortfolioAllocationBacktestPanel } from './PortfolioAllocationBacktestPanel'
import { MonitoringPanel } from './MonitoringPanel'
import { PortfolioImprovementWorkspaceShell } from './PortfolioImprovementWorkspaceShell'
import type { ConstructionArtifactReplayResponse, HypotheticalReplayResponse, MonitoringResearchHandoff, MonitorDefinitionAlertReviewTimelineHistoryRow, MonitorDefinitionAlertReviewTimelineObservationRow, MonitorDefinitionRecoveredAlertReviewQueueRow, PortfolioAllocationBacktestResponse, PortfolioBaselineView, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { ActiveThesisArtifact, CandidateImprovementDraftArtifact, ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, MonitorDefinitionAlertReviewSessionState, PersistedConstructionArtifactWorkspaceReview, PersistedOptimizerHandoffWorkspaceReview, PortfolioSnapshot, PortfolioWorkspaceSource, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'

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
  constructionConstraintValidationArtifact: ConstructionConstraintValidationArtifact | null
  selectedConstructionRuleId: SingleReplacementConstructionRuleId
  hypotheticalReplayResult: HypotheticalReplayResponse | null
  workspaceSource: PortfolioWorkspaceSource | null
  persistedConstructionArtifactReview: PersistedConstructionArtifactWorkspaceReview | null
  persistedOptimizerHandoffReview: PersistedOptimizerHandoffWorkspaceReview | null
  savedProposals: VersionedProposalArtifact[]
  activeThesis: ActiveThesisArtifact | null
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
  onOpenLatestObservation?: (row: MonitorDefinitionAlertReviewTimelineObservationRow) => void | Promise<void>
  onOpenAlertHistoryReview?: (row: MonitorDefinitionAlertReviewTimelineHistoryRow) => void | Promise<void>
  onReopenRecoveredAlertReview?: (row: MonitorDefinitionRecoveredAlertReviewQueueRow) => void | Promise<void>
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
  monitoringResearchHandoff?: MonitoringResearchHandoff | null
  monitoringResearchHandoffDismissed?: boolean
  onDismissMonitoringResearchHandoff?: () => void
  onReviewInResearch?: (handoff: MonitoringResearchHandoff) => void
}

export function BacktestWorkspacePanel({ allocationBacktestResult, onAllocationBacktestResult, analysis, draftSnapshot, candidateImprovementDraft, intentBoundSeededEtfReplacementRankingDraft, replacementIntentDraft, formedCandidateArtifact, constructedCandidateArtifact, constructionConstraintValidationArtifact, selectedConstructionRuleId, hypotheticalReplayResult, workspaceSource, persistedConstructionArtifactReview, persistedOptimizerHandoffReview, savedProposals, activeThesis, onSaveProposal, onOpenSavedProposal, openedSavedProposalArtifactId, onPromoteProposalToThesis, onClearActiveThesis, onHypotheticalReplayResult, onFormedCandidateArtifact, onConstructedCandidateArtifact, onConstructionConstraintValidationArtifact, onSelectedConstructionRuleChange, monitorDefinitionAlertReviewSession, recoveredAlertReviewQueue, onOpenLatestObservation, onOpenAlertHistoryReview, onReopenRecoveredAlertReview, onCreateReplacementIntent, onClearReplacementIntent, monitoringResearchHandoff, monitoringResearchHandoffDismissed, onDismissMonitoringResearchHandoff, onReviewInResearch }: Props) {
  return (
    <article className="panel">
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={candidateImprovementDraft}
        intentBoundSeededEtfReplacementRankingDraft={intentBoundSeededEtfReplacementRankingDraft}
        replacementIntentDraft={replacementIntentDraft}
        formedCandidateArtifact={formedCandidateArtifact}
        constructedCandidateArtifact={constructedCandidateArtifact}
        constructionConstraintValidationArtifact={constructionConstraintValidationArtifact}
        selectedConstructionRuleId={selectedConstructionRuleId}
        allocationBacktestResult={allocationBacktestResult}
        onAllocationBacktestResult={onAllocationBacktestResult}
        hypotheticalReplayResult={hypotheticalReplayResult}
        workspaceSource={workspaceSource}
        persistedConstructionArtifactReview={persistedConstructionArtifactReview}
        persistedOptimizerHandoffReview={persistedOptimizerHandoffReview}
        savedProposals={savedProposals}
        activeThesis={activeThesis}
        onCreateReplacementIntent={onCreateReplacementIntent}
        onClearReplacementIntent={onClearReplacementIntent}
        onSaveProposal={onSaveProposal}
        onOpenSavedProposal={onOpenSavedProposal}
        openedSavedProposalArtifactId={openedSavedProposalArtifactId}
        onPromoteProposalToThesis={onPromoteProposalToThesis}
        onClearActiveThesis={onClearActiveThesis}
        onHypotheticalReplayResult={onHypotheticalReplayResult}
        onFormedCandidateArtifact={onFormedCandidateArtifact}
        onConstructedCandidateArtifact={onConstructedCandidateArtifact}
        onConstructionConstraintValidationArtifact={onConstructionConstraintValidationArtifact}
        onSelectedConstructionRuleChange={onSelectedConstructionRuleChange}
        monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
        recoveredAlertReviewQueue={recoveredAlertReviewQueue}
        onOpenLatestObservation={onOpenLatestObservation}
        onOpenAlertHistoryReview={onOpenAlertHistoryReview}
        onReopenRecoveredAlertReview={onReopenRecoveredAlertReview}
        monitoringResearchHandoff={monitoringResearchHandoff}
        monitoringResearchHandoffDismissed={monitoringResearchHandoffDismissed}
        onDismissMonitoringResearchHandoff={onDismissMonitoringResearchHandoff}
        onReviewInResearch={onReviewInResearch}
      />
    </article>
  )
}
