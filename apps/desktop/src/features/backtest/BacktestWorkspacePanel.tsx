import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'

import { PortfolioImprovementWorkspaceShell } from './PortfolioImprovementWorkspaceShell'
import { buildAuthoritativeCurrentPortfolio } from './currentPortfolio'
import type { HypotheticalReplayResponse, MonitoringResearchHandoff, MonitorDefinitionActiveAlertEpisodeInboxResponse, MonitorDefinitionActiveAlertEpisodeInboxRow, MonitorDefinitionAlertEpisodeHistoryResponse, MonitorDefinitionAlertEpisodeHistoryRow, MonitorDefinitionAlertReviewTimelineHistoryRow, MonitorDefinitionAlertReviewTimelineObservationRow, MonitorDefinitionRecoveredAlertReviewQueueRow, PortfolioAllocationBacktestResponse, PortfolioBaselineView, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { ActiveThesisArtifact, CandidateImprovementDraftArtifact, CandidateImprovementSeed, ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifact, IntentBoundSeededEtfReplacementRankingDraftArtifactInput, MonitorDefinitionAlertReviewSessionState, PersistedConstructionArtifactWorkspaceReview, PersistedOptimizerHandoffWorkspaceReview, PortfolioSnapshot, PortfolioWorkspaceSource, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'
import type { BacktestRunResponse } from '../portfolio/types'
import type { EtfRankingPanelState, SessionStateUpdate, StrategyBacktestPanelState, StrategyLabPanelState } from '../portfolio/workspaceResearchSessionState'
import { applySessionStateUpdate, createEtfRankingPanelState, createStrategyBacktestPanelState, createStrategyLabPanelState } from '../portfolio/workspaceResearchSessionState'
import { StrategyBacktestPanel } from './StrategyBacktestPanel'
import { StrategyLabPanel } from '../strategy-lab/StrategyLabPanel'
import { EtfRankingPanel } from '../strategy-lab/EtfRankingPanel'

export type WorkspaceResearchTool = 'backtest' | 'strategy_lab' | 'etf_ranking'

const researchToolSectionId = 'workspace-section-research-tools'

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
  activeAlertEpisodeInbox?: {
    status: 'idle' | 'loading' | 'ready' | 'error'
    response: MonitorDefinitionActiveAlertEpisodeInboxResponse | null
    error: string | null
  }
  alertEpisodeHistory?: {
    status: 'idle' | 'loading' | 'ready' | 'error'
    monitorDefinitionId: string | null
    response: MonitorDefinitionAlertEpisodeHistoryResponse | null
    error: string | null
  }
  onOpenLatestObservation?: (row: MonitorDefinitionAlertReviewTimelineObservationRow) => void | Promise<void>
  onOpenAlertHistoryReview?: (row: MonitorDefinitionAlertReviewTimelineHistoryRow) => void | Promise<void>
  onReopenRecoveredAlertReview?: (row: MonitorDefinitionRecoveredAlertReviewQueueRow) => void | Promise<void>
  onOpenActiveAlertEpisode?: (row: MonitorDefinitionActiveAlertEpisodeInboxRow) => void | Promise<void>
  onOpenAlertEpisodeHistory?: (row: MonitorDefinitionAlertEpisodeHistoryRow) => void | Promise<void>
  onLoadOlderAlertEpisodeHistory?: () => void | Promise<void>
  onCreateReplacementIntent?: () => void | Promise<void>
  onClearReplacementIntent?: () => void | Promise<void>
  monitoringResearchHandoff?: MonitoringResearchHandoff | null
  monitoringResearchHandoffDismissed?: boolean
  onDismissMonitoringResearchHandoff?: () => void
  onReviewInResearch?: (handoff: MonitoringResearchHandoff) => void
  workspaceId?: string | null
  requestedResearchTool?: WorkspaceResearchTool | null
  onConsumeRequestedResearchTool?: () => void
  workspaceShellActivationKey?: number
  embeddedBacktestResult?: BacktestRunResponse | null
  embeddedStrategyBacktestState?: StrategyBacktestPanelState
  onEmbeddedStrategyBacktestStateChange?: (update: SessionStateUpdate<StrategyBacktestPanelState>) => void
  onEmbeddedBacktestResult?: (result: BacktestRunResponse) => void
  embeddedStrategyLabState?: StrategyLabPanelState
  onEmbeddedStrategyLabStateChange?: (update: SessionStateUpdate<StrategyLabPanelState>) => void
  embeddedEtfRankingState?: EtfRankingPanelState
  onEmbeddedEtfRankingStateChange?: (update: SessionStateUpdate<EtfRankingPanelState>) => void
  onSeedCandidateDraft?: (input: { seed: CandidateImprovementSeed; rankingArtifact: IntentBoundSeededEtfReplacementRankingDraftArtifactInput | null }) => void
  onOpenPersistedConstructionArtifactReview?: (constructionArtifactId: string) => void | Promise<void>
}

function WorkspaceResearchSession({
  title,
  onExit,
  children,
}: {
  title: string
  onExit: () => void
  children: ReactNode
}) {
  return (
    <section className="workspace-section panel" data-testid="workspace-owned-research-session">
      <div className="section-header-inline sector-list-header">
        <div>
          <p className="panel-label">Workspace Research Session</p>
          <h2>{title}</h2>
        </div>
        <div className="actions dashboard-edit-actions dashboard-edit-actions-compact">
          <button className="secondary-button" type="button" onClick={onExit}>Back To Workspace</button>
        </div>
      </div>
      {children}
    </section>
  )
}

export function BacktestWorkspacePanel({ allocationBacktestResult, onAllocationBacktestResult, analysis, draftSnapshot, candidateImprovementDraft, intentBoundSeededEtfReplacementRankingDraft, replacementIntentDraft, formedCandidateArtifact, constructedCandidateArtifact, constructionConstraintValidationArtifact, selectedConstructionRuleId, hypotheticalReplayResult, workspaceSource, persistedConstructionArtifactReview, persistedOptimizerHandoffReview, savedProposals, activeThesis, onSaveProposal, onOpenSavedProposal, openedSavedProposalArtifactId, onPromoteProposalToThesis, onClearActiveThesis, onHypotheticalReplayResult, onFormedCandidateArtifact, onConstructedCandidateArtifact, onConstructionConstraintValidationArtifact, onSelectedConstructionRuleChange, monitorDefinitionAlertReviewSession, recoveredAlertReviewQueue, activeAlertEpisodeInbox, alertEpisodeHistory, onOpenLatestObservation, onOpenAlertHistoryReview, onReopenRecoveredAlertReview, onOpenActiveAlertEpisode, onOpenAlertEpisodeHistory, onLoadOlderAlertEpisodeHistory, onCreateReplacementIntent, onClearReplacementIntent, monitoringResearchHandoff, monitoringResearchHandoffDismissed, onDismissMonitoringResearchHandoff, onReviewInResearch, workspaceId, requestedResearchTool, onConsumeRequestedResearchTool, workspaceShellActivationKey, embeddedBacktestResult, embeddedStrategyBacktestState, onEmbeddedStrategyBacktestStateChange, onEmbeddedBacktestResult, embeddedStrategyLabState, onEmbeddedStrategyLabStateChange, embeddedEtfRankingState, onEmbeddedEtfRankingStateChange, onSeedCandidateDraft, onOpenPersistedConstructionArtifactReview }: Props) {
  const [activeResearchTool, setActiveResearchTool] = useState<WorkspaceResearchTool | null>(null)
  const [returnSectionId, setReturnSectionId] = useState<string>(researchToolSectionId)
  const [localEmbeddedBacktestResult, setLocalEmbeddedBacktestResult] = useState<BacktestRunResponse | null>(null)
  const [localEmbeddedStrategyBacktestState, setLocalEmbeddedStrategyBacktestState] = useState<StrategyBacktestPanelState>(() => createStrategyBacktestPanelState())
  const [localEmbeddedStrategyLabState, setLocalEmbeddedStrategyLabState] = useState<StrategyLabPanelState>(() => createStrategyLabPanelState())
  const [localEmbeddedEtfRankingState, setLocalEmbeddedEtfRankingState] = useState<EtfRankingPanelState>(() => createEtfRankingPanelState())
  const [requestedEtfRankingArtifactId, setRequestedEtfRankingArtifactId] = useState<string | null>(null)

  const resolvedEmbeddedBacktestResult = embeddedBacktestResult ?? localEmbeddedBacktestResult
  const resolvedEmbeddedStrategyBacktestState = embeddedStrategyBacktestState ?? localEmbeddedStrategyBacktestState
  const resolvedEmbeddedStrategyLabState = embeddedStrategyLabState ?? localEmbeddedStrategyLabState
  const resolvedEmbeddedEtfRankingState = embeddedEtfRankingState ?? localEmbeddedEtfRankingState
  const authoritativeCurrentPortfolio = buildAuthoritativeCurrentPortfolio(draftSnapshot)
  const useControlledEmbeddedBacktest = embeddedStrategyBacktestState !== undefined && !!onEmbeddedStrategyBacktestStateChange
  const useControlledEmbeddedStrategyLab = embeddedStrategyLabState !== undefined && !!onEmbeddedStrategyLabStateChange
  const useControlledEmbeddedEtfRanking = embeddedEtfRankingState !== undefined && !!onEmbeddedEtfRankingStateChange
  const hasSeenWorkspaceShellActivation = useRef(false)

  useEffect(() => {
    setActiveResearchTool(null)
    setReturnSectionId(researchToolSectionId)
    setLocalEmbeddedBacktestResult(null)
    setLocalEmbeddedStrategyBacktestState(createStrategyBacktestPanelState())
    setLocalEmbeddedStrategyLabState(createStrategyLabPanelState())
    setLocalEmbeddedEtfRankingState(createEtfRankingPanelState())
    setRequestedEtfRankingArtifactId(null)
  }, [workspaceId])

  useEffect(() => {
    if (!requestedResearchTool || !workspaceId) return
    setReturnSectionId(researchToolSectionId)
    setActiveResearchTool(requestedResearchTool)
    onConsumeRequestedResearchTool?.()
  }, [requestedResearchTool, workspaceId, onConsumeRequestedResearchTool])

  useEffect(() => {
    if (!workspaceId) return
    if (!hasSeenWorkspaceShellActivation.current) {
      hasSeenWorkspaceShellActivation.current = true
      return
    }
    setActiveResearchTool(null)
    setReturnSectionId(researchToolSectionId)
  }, [workspaceId, workspaceShellActivationKey])

  const requestedToolLabel = requestedResearchTool === 'backtest'
    ? 'Backtest'
    : requestedResearchTool === 'strategy_lab'
      ? 'Strategy Lab'
      : requestedResearchTool === 'etf_ranking'
        ? 'ETF Ranking'
        : null

  function openEmbeddedResearchTool(tool: WorkspaceResearchTool, sectionId = researchToolSectionId) {
    setReturnSectionId(sectionId)
    setActiveResearchTool(tool)
  }

  function exitEmbeddedResearchTool() {
    setActiveResearchTool(null)
    globalThis.setTimeout(() => {
      const target = document.getElementById(returnSectionId)
      if (target && 'scrollIntoView' in target && typeof target.scrollIntoView === 'function') {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
    }, 0)
  }

  return (
    <article className="panel">
      {activeResearchTool === 'backtest' ? (
        <WorkspaceResearchSession title="Embedded Backtest" onExit={exitEmbeddedResearchTool}>
          <StrategyBacktestPanel
            backtestResult={resolvedEmbeddedBacktestResult}
            onBacktestResult={(result) => {
              if (useControlledEmbeddedBacktest && onEmbeddedBacktestResult) {
                onEmbeddedBacktestResult(result)
                return
              }
              setLocalEmbeddedBacktestResult(result)
            }}
            sessionState={resolvedEmbeddedStrategyBacktestState}
            onSessionStateChange={(update) => {
              if (useControlledEmbeddedBacktest && onEmbeddedStrategyBacktestStateChange) {
                onEmbeddedStrategyBacktestStateChange(update)
                return
              }
              setLocalEmbeddedStrategyBacktestState((current) => applySessionStateUpdate(current, update))
            }}
          />
        </WorkspaceResearchSession>
      ) : null}
      {activeResearchTool === 'strategy_lab' ? (
        <WorkspaceResearchSession title="Embedded Strategy Lab" onExit={exitEmbeddedResearchTool}>
          <StrategyLabPanel
            sessionState={resolvedEmbeddedStrategyLabState}
            onSessionStateChange={(update) => {
              if (useControlledEmbeddedStrategyLab && onEmbeddedStrategyLabStateChange) {
                onEmbeddedStrategyLabStateChange(update)
                return
              }
              setLocalEmbeddedStrategyLabState((current) => applySessionStateUpdate(current, update))
            }}
          />
        </WorkspaceResearchSession>
      ) : null}
      {activeResearchTool === 'etf_ranking' ? (
        <WorkspaceResearchSession title="Embedded ETF Ranking" onExit={exitEmbeddedResearchTool}>
          <EtfRankingPanel
            draftSymbols={draftSnapshot?.positions.map((position) => position.symbol) ?? []}
            currentPortfolio={authoritativeCurrentPortfolio}
            onSeedCandidateDraft={onSeedCandidateDraft}
            onReviewInConstruction={async ({ run }) => {
              await onOpenPersistedConstructionArtifactReview?.(run.artifact_id)
            }}
            requestedRecentArtifactId={requestedEtfRankingArtifactId}
            onConsumeRequestedRecentArtifactId={() => setRequestedEtfRankingArtifactId(null)}
            sessionState={resolvedEmbeddedEtfRankingState}
            onSessionStateChange={(update) => {
              if (useControlledEmbeddedEtfRanking && onEmbeddedEtfRankingStateChange) {
                onEmbeddedEtfRankingStateChange(update)
                return
              }
              setLocalEmbeddedEtfRankingState((current) => applySessionStateUpdate(current, update))
            }}
          />
        </WorkspaceResearchSession>
      ) : null}
      {!activeResearchTool && workspaceId ? (
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
          activeAlertEpisodeInbox={activeAlertEpisodeInbox}
          alertEpisodeHistory={alertEpisodeHistory}
          onOpenLatestObservation={onOpenLatestObservation}
          onOpenAlertHistoryReview={onOpenAlertHistoryReview}
          onReopenRecoveredAlertReview={onReopenRecoveredAlertReview}
          onOpenActiveAlertEpisode={onOpenActiveAlertEpisode}
          onOpenAlertEpisodeHistory={onOpenAlertEpisodeHistory}
          onLoadOlderAlertEpisodeHistory={onLoadOlderAlertEpisodeHistory}
          monitoringResearchHandoff={monitoringResearchHandoff}
          monitoringResearchHandoffDismissed={monitoringResearchHandoffDismissed}
          onDismissMonitoringResearchHandoff={onDismissMonitoringResearchHandoff}
          onReviewInResearch={onReviewInResearch}
          onOpenGenericBacktests={(sectionId) => openEmbeddedResearchTool('backtest', sectionId)}
          onOpenStrategyLab={(sectionId) => openEmbeddedResearchTool('strategy_lab', sectionId)}
          onOpenEtfRanking={(sectionId) => openEmbeddedResearchTool('etf_ranking', sectionId)}
          onOpenPersistedConstructionArtifactReview={onOpenPersistedConstructionArtifactReview}
          onOpenPersistedEtfRankingReview={(artifactId) => {
            setRequestedEtfRankingArtifactId(artifactId)
            openEmbeddedResearchTool('etf_ranking', 'workflow-section-candidate-idea')
          }}
        />
      ) : null}
      {!workspaceId && requestedToolLabel ? (
        <section className="workspace-section panel" data-testid="workspace-research-intent-empty-state">
          <h2>Portfolio Research Workspace</h2>
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">No active workspace is open for {requestedToolLabel}.</p>
            <p className="helper">Open or import a portfolio workspace first, then launch {requestedToolLabel} from Workspace. This compatibility entry point only redirects your request and does not create a synthetic workspace or start tool requests.</p>
          </div>
        </section>
      ) : null}
      {!workspaceId && !requestedToolLabel ? (
        <section className="workspace-section panel" data-testid="workspace-empty-state">
          <h2>Portfolio Research Workspace</h2>
          <div className="empty-state-panel compact-empty-state">
            <p className="empty-state-title">No active workspace is open.</p>
            <p className="helper">Import a portfolio or reopen a saved workspace to continue workspace-owned research.</p>
          </div>
        </section>
      ) : null}
    </article>
  )
}
