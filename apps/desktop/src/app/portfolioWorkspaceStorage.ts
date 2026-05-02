import { activeThesisStoreName, appStateStoreName, candidateImprovementDraftStoreName, constructedCandidateStoreName, constructionConstraintValidationStoreName, deletePortfolioDatabase, formedCandidateStoreName, hypotheticalReplacementReplayDraftStoreName, intentBoundSeededEtfReplacementRankingDraftStoreName, persistedConstructionArtifactReviewStoreName, persistedOptimizerHandoffReviewStoreName, portfolioNodeStoreName, replacementIntentDraftStoreName, reviewSnapshotArtifactStoreName, selectedConstructionRuleStoreName, versionedProposalStoreName, withStore, withStores, workingDraftStoreName, workspaceStateStoreName, workspaceStoreName } from './portfolioDb'
import { buildImportedHistorySource } from '../features/portfolio/historySource'
import { buildPortfolioSnapshotFromAnalysis, clonePortfolioSnapshot, getPortfolioSnapshotGrossExposure, getPortfolioSnapshotNetCapital, getPortfolioSnapshotSectorCount, hashPortfolioSnapshot } from '../features/portfolio/portfolioSnapshot'
import type { ConstructionArtifactReplayResponse, ImportedPortfolioSnapshotSource, ImportedSnapshot, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse } from '../features/portfolio/types'
import type { ActiveThesisArtifact, CandidateImprovementDraftArtifact, DesktopArtifactReviewBasis, FormedCandidateArtifact, HypotheticalReplacementReplayDraftArtifact, ImportedHistoryContext, ImportedNodeSource, IntentBoundSeededEtfReplacementRankingDraftArtifact, LegacyIntentBoundSeededEtfReplacementRankingDraftArtifact, MonitorDefinitionAlertReviewWorkspaceState, PersistedConstructionArtifactReviewBasis, PersistedConstructionArtifactWorkspaceReview, PersistedOptimizerHandoffReviewBasis, PersistedOptimizerHandoffWorkspaceReview, PortfolioNode, PortfolioSnapshot, PortfolioWorkspace, ProposalSourceLabel, ReplacementIntentDraftArtifact, ReviewSnapshotActiveThesisCrossFamilyQueueResponse, ReviewSnapshotArtifact, ReviewSnapshotComparisonArtifactRef, ReviewSnapshotComparisonResponse, ReviewSnapshotFamilyInboxResponse, ReviewSnapshotFamilyKey, ReviewSnapshotFamilyReviewResponse, ReviewSnapshotOpenHandoff, ReviewSnapshotOpenResponse, SelectedConstructionRuleArtifact, VersionedProposalArtifact, WorkingDraft, WorkspaceState, ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact } from '../features/portfolio/workspaceTypes'

const activeWorkspacePointerKey = 'active-workspace-pointer'

function normalizeConstructionArtifactReplayResponse(replay: ConstructionArtifactReplayResponse): ConstructionArtifactReplayResponse {
  if (replay.effective_replay_params) {
    return replay
  }

  return {
    ...replay,
    effective_replay_params: {
      benchmark_symbol: replay.replay.candidate_result.benchmark_symbol ?? 'SPY',
      start_date: replay.replay.candidate_result.start_date,
      end_date: replay.replay.candidate_result.end_date,
      initial_capital: replay.replay.candidate_result.equity_curve[0]?.equity ?? 100000,
      rebalance_frequency: replay.replay.candidate_result.rebalance_frequency,
      base_currency: replay.replay.candidate_result.assumptions.investor_base_currency ?? 'USD',
      commission_bps: replay.replay.candidate_result.commission_bps,
      slippage_bps: replay.replay.candidate_result.slippage_bps,
      drift_tolerance_pct: replay.replay.candidate_result.drift_tolerance_pct,
      price_basis: 'adjusted_close',
      execution_price_field: 'close',
      execution_lag_days: replay.replay.candidate_result.assumptions.execution_lag_days,
      symbol_overrides: {},
    },
  }
}

export function buildPersistedImportedSource(input: {
  importedFileNames: string[]
  importedAt: string
  importer: ImportedNodeSource['importer']
  baseCurrency: string | null
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): ImportedNodeSource {
  return {
    importedFileNames: input.importedFileNames,
    importedAt: input.importedAt,
    importer: input.importer,
    baseCurrency: input.baseCurrency,
    historySource: buildImportedHistorySource({
      historyContext: input.historyContext ?? null,
      importedHistorySnapshot: input.importedHistorySnapshot ?? null,
    }),
  }
}

function createId(prefix: string) {
  return `${prefix}_${globalThis.crypto?.randomUUID?.() ?? Math.random().toString(36).slice(2)}`
}

const canonicalReviewOnlyProposalSourceLabel = Object.freeze({
  proposalSourceVersion: 1 as const,
  proposalSourceKind: 'draft_replacement_intent_review_only' as const,
  proposalTruth: 'review_only_hypothetical_proposal' as const,
  portfolioTruth: 'draft_snapshot_not_applied' as const,
  reviewScope: 'proposal_review_context_only' as const,
})

function buildCanonicalReviewOnlyProposalSourceLabel(): ProposalSourceLabel {
  return { ...canonicalReviewOnlyProposalSourceLabel }
}

function buildSnapshotProposalSourceLabel(value: ProposalSourceLabel): NonNullable<VersionedProposalArtifact['reviewSnapshot']['proposal']['proposal_source']> {
  return {
    proposal_source_version: value.proposalSourceVersion,
    proposal_source_kind: value.proposalSourceKind,
    proposal_truth: value.proposalTruth,
    portfolio_truth: value.portfolioTruth,
    review_scope: value.reviewScope,
  }
}

function assertProposalSourceLabelShape(value: unknown, label: string): asserts value is ProposalSourceLabel {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }

  const candidate = value as Partial<ProposalSourceLabel>
  if (
    typeof candidate.proposalSourceVersion !== 'number'
    || typeof candidate.proposalSourceKind !== 'string'
    || typeof candidate.proposalTruth !== 'string'
    || typeof candidate.portfolioTruth !== 'string'
    || typeof candidate.reviewScope !== 'string'
  ) {
    throw new Error(`${label} is invalid`)
  }
}

function isCanonicalProposalSourceLabel(value: ProposalSourceLabel) {
  return value.proposalSourceVersion === canonicalReviewOnlyProposalSourceLabel.proposalSourceVersion
    && value.proposalSourceKind === canonicalReviewOnlyProposalSourceLabel.proposalSourceKind
    && value.proposalTruth === canonicalReviewOnlyProposalSourceLabel.proposalTruth
    && value.portfolioTruth === canonicalReviewOnlyProposalSourceLabel.portfolioTruth
    && value.reviewScope === canonicalReviewOnlyProposalSourceLabel.reviewScope
}

function assertValidProposalSourceLabel(value: unknown, label: string): asserts value is ProposalSourceLabel {
  assertProposalSourceLabelShape(value, label)

  if (!isCanonicalProposalSourceLabel(value)) {
    throw new Error(`${label} is invalid`)
  }
}

function proposalSourceLabelsMatch(
  topLevel: ProposalSourceLabel,
  snapshot: NonNullable<VersionedProposalArtifact['reviewSnapshot']['proposal']['proposal_source']>,
) {
  return topLevel.proposalSourceVersion === snapshot.proposal_source_version
    && topLevel.proposalSourceKind === snapshot.proposal_source_kind
    && topLevel.proposalTruth === snapshot.proposal_truth
    && topLevel.portfolioTruth === snapshot.portfolio_truth
    && topLevel.reviewScope === snapshot.review_scope
}

function assertSnapshotProposalSourceLabelShape(
  value: unknown,
  label: string,
): asserts value is NonNullable<VersionedProposalArtifact['reviewSnapshot']['proposal']['proposal_source']> {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }

  const candidate = value as Partial<NonNullable<VersionedProposalArtifact['reviewSnapshot']['proposal']['proposal_source']>>
  if (
    typeof candidate.proposal_source_version !== 'number'
    || typeof candidate.proposal_source_kind !== 'string'
    || typeof candidate.proposal_truth !== 'string'
    || typeof candidate.portfolio_truth !== 'string'
    || typeof candidate.review_scope !== 'string'
  ) {
    throw new Error(`${label} is invalid`)
  }
}

function isCanonicalSnapshotProposalSourceLabel(
  value: NonNullable<VersionedProposalArtifact['reviewSnapshot']['proposal']['proposal_source']>,
) {
  return value.proposal_source_version === canonicalReviewOnlyProposalSourceLabel.proposalSourceVersion
    && value.proposal_source_kind === canonicalReviewOnlyProposalSourceLabel.proposalSourceKind
    && value.proposal_truth === canonicalReviewOnlyProposalSourceLabel.proposalTruth
    && value.portfolio_truth === canonicalReviewOnlyProposalSourceLabel.portfolioTruth
    && value.review_scope === canonicalReviewOnlyProposalSourceLabel.reviewScope
}

function assertValidSnapshotProposalSourceLabel(
  value: unknown,
  label: string,
): asserts value is NonNullable<VersionedProposalArtifact['reviewSnapshot']['proposal']['proposal_source']> {
  assertSnapshotProposalSourceLabelShape(value, label)

  if (!isCanonicalSnapshotProposalSourceLabel(value)) {
    throw new Error(`${label} is invalid`)
  }
}

function isRecognizedLegacySavedProposalProposalSourceOmission(proposal: VersionedProposalArtifact) {
  const snapshotProposal = proposal.reviewSnapshot.proposal
  const sourceIntent = proposal.sourceIntent
  const upstreamIds = proposal.replayBasis.replayProvenance.upstream_ids

  return proposal.kind === 'single_replacement_hypothetical_replay_proposal'
    && proposal.savedFrom === 'desktop_hypothetical_replay_review'
    && proposal.reviewStatus === 'recorded'
    && sourceIntent.kind === 'etf_replacement_intent'
    && snapshotProposal.source === 'draft_replacement_intent'
    && sourceIntent.draftId === proposal.sourceDraftId
    && sourceIntent.baseNodeId === proposal.sourceBaseNodeId
    && sourceIntent.workspaceId === proposal.workspaceId
    && sourceIntent.baseSymbol === snapshotProposal.incumbent_symbol
    && sourceIntent.candidateSymbol === snapshotProposal.candidate_symbol
    && snapshotProposal.draft_id === proposal.sourceDraftId
    && snapshotProposal.base_node_id === proposal.sourceBaseNodeId
    && upstreamIds.draft_id === proposal.sourceDraftId
    && upstreamIds.workspace_id === proposal.workspaceId
    && upstreamIds.base_node_id === proposal.sourceBaseNodeId
}

export function assertSavedProposalArtifactProposalSourceIntegrity(proposal: VersionedProposalArtifact): VersionedProposalArtifact {
  const topLevelProposalSource = proposal.proposalSource ?? null
  const snapshotProposalSource = proposal.reviewSnapshot.proposal.proposal_source ?? null

  if (topLevelProposalSource == null) {
    throw new Error('Saved proposal is missing authoritative proposalSource')
  }

  assertProposalSourceLabelShape(topLevelProposalSource, 'Saved proposal proposalSource')

  if (snapshotProposalSource == null) {
    assertValidProposalSourceLabel(topLevelProposalSource, 'Saved proposal proposalSource')
    return proposal
  }

  assertSnapshotProposalSourceLabelShape(snapshotProposalSource, 'Saved proposal reviewSnapshot proposal.proposal_source')

  if (!isCanonicalSnapshotProposalSourceLabel(snapshotProposalSource)) {
    throw new Error('Saved proposal reviewSnapshot proposal.proposal_source is invalid')
  }

  if (!proposalSourceLabelsMatch(topLevelProposalSource, snapshotProposalSource)) {
    throw new Error('Saved proposal proposalSource conflicts with reviewSnapshot proposal.proposal_source')
  }

  assertValidProposalSourceLabel(topLevelProposalSource, 'Saved proposal proposalSource')

  return proposal
}

function buildSavedProposalReviewSnapshotPMSummary(proposal: VersionedProposalArtifact) {
  const proposalReplay = 'replay' in proposal.reviewSnapshot ? proposal.reviewSnapshot.replay : proposal.reviewSnapshot.overlay_replay
  const proposalSource = proposal.reviewSnapshot.proposal.proposal_source ?? {
    proposal_source_version: proposal.proposalSource.proposalSourceVersion,
    proposal_source_kind: proposal.proposalSource.proposalSourceKind,
    proposal_truth: proposal.proposalSource.proposalTruth,
    portfolio_truth: proposal.proposalSource.portfolioTruth,
    review_scope: proposal.proposalSource.reviewScope,
  }
  return {
    pm_summary_version: 1 as const,
    role: 'saved_proposal' as const,
    provenance: {
      source: 'persisted_review_snapshot_artifact' as const,
      artifact_kind: 'portfolio_review_snapshot' as const,
      schema_version: 'review_snapshot_artifact_v1' as const,
      consumer_kind: 'saved_hypothetical_replay_proposal' as const,
      lineage: {
        workspace_id: proposal.workspaceId,
        source_draft_id: proposal.sourceDraftId,
        source_base_node_id: proposal.sourceBaseNodeId,
        proposal_family_id: proposal.proposalFamilyId,
        proposal_id: proposal.id,
        version_number: proposal.versionNumber,
        source_kind: 'hypothetical_replacement_replay' as const,
      },
      proposal_source: proposalSource,
      replay_provenance: proposal.reviewSnapshot.replay_provenance,
    },
    truth_labels: {
      proposal_truth: 'review_only_hypothetical_proposal' as const,
      portfolio_truth: 'draft_snapshot_not_applied' as const,
      analytics_truth: 'hypothetical_replay_analytics_only' as const,
      review_scope: 'proposal_review_context_only' as const,
    },
    replay_type: 'replay' in proposal.reviewSnapshot ? 'standard' as const : 'overlay_aware' as const,
    replay_status: proposalReplay.candidate_result.status,
    investor_economics_status: proposalReplay.investor_economics_status,
    review_basis: {
      benchmark_separation: 'explicit_per_snapshot_benchmark_fields' as const,
      benchmark_symbol: proposal.replayBasis.benchmarkSymbol,
      replay_window: {
        start_date: proposal.replayBasis.startDate,
        end_date: proposal.replayBasis.endDate,
      },
      rebalance_frequency: proposal.replayBasis.rebalanceFrequency,
      commission_bps: proposal.replayBasis.commissionBps,
      slippage_bps: proposal.replayBasis.slippageBps,
      derivation_basis: proposal.replayBasis.derivationBasis,
      candidate_construction_rule: proposal.replayBasis.candidateConstructionRule,
    },
    methodology: {
      methodology: proposalReplay.methodology,
      methodology_provenance: proposalReplay.methodology_provenance,
    },
    assumptions: proposalReplay.candidate_result.assumptions,
    analytics_summary: {
      candidate_analytics: {
        methodology: proposalReplay.methodology,
        methodology_provenance: proposalReplay.methodology_provenance,
        assumptions: proposalReplay.candidate_result.assumptions,
        benchmark_symbol: proposalReplay.candidate_result.benchmark_symbol,
        benchmark_return_pct: proposalReplay.candidate_result.metrics.benchmark_return_pct,
        total_return_pct: proposalReplay.candidate_result.metrics.total_return_pct,
        annualized_return_pct: proposalReplay.candidate_result.metrics.annualized_return_pct,
        annualized_volatility_pct: proposalReplay.candidate_result.metrics.annualized_volatility_pct,
        downside_volatility_pct: proposalReplay.candidate_result.metrics.downside_volatility_pct,
        max_drawdown_pct: proposalReplay.candidate_result.metrics.max_drawdown_pct,
        sharpe_ratio: proposalReplay.candidate_result.metrics.sharpe_ratio,
        sortino_ratio: proposalReplay.candidate_result.metrics.sortino_ratio,
        excess_return_pct: proposalReplay.candidate_result.metrics.excess_return_pct,
        tracking_error_pct: proposalReplay.candidate_result.metrics.tracking_error_pct,
        information_ratio: proposalReplay.candidate_result.metrics.information_ratio,
        beta_vs_benchmark: proposalReplay.candidate_result.metrics.beta_vs_benchmark,
        correlation_vs_benchmark: proposalReplay.candidate_result.metrics.correlation_vs_benchmark,
        total_turnover_pct: proposalReplay.candidate_result.metrics.total_turnover_pct,
        total_cost_paid: proposalReplay.candidate_result.metrics.total_cost_paid,
      },
      baseline_analytics: proposalReplay.reference_result ? {
        methodology: proposalReplay.methodology,
        methodology_provenance: proposalReplay.methodology_provenance,
        assumptions: proposalReplay.reference_result.assumptions,
        benchmark_symbol: proposalReplay.reference_result.benchmark_symbol,
        benchmark_return_pct: proposalReplay.reference_result.metrics.benchmark_return_pct,
        total_return_pct: proposalReplay.reference_result.metrics.total_return_pct,
        annualized_return_pct: proposalReplay.reference_result.metrics.annualized_return_pct,
        annualized_volatility_pct: proposalReplay.reference_result.metrics.annualized_volatility_pct,
        downside_volatility_pct: proposalReplay.reference_result.metrics.downside_volatility_pct,
        max_drawdown_pct: proposalReplay.reference_result.metrics.max_drawdown_pct,
        sharpe_ratio: proposalReplay.reference_result.metrics.sharpe_ratio,
        sortino_ratio: proposalReplay.reference_result.metrics.sortino_ratio,
        excess_return_pct: proposalReplay.reference_result.metrics.excess_return_pct,
        tracking_error_pct: proposalReplay.reference_result.metrics.tracking_error_pct,
        information_ratio: proposalReplay.reference_result.metrics.information_ratio,
        beta_vs_benchmark: proposalReplay.reference_result.metrics.beta_vs_benchmark,
        correlation_vs_benchmark: proposalReplay.reference_result.metrics.correlation_vs_benchmark,
        total_turnover_pct: proposalReplay.reference_result.metrics.total_turnover_pct,
        total_cost_paid: proposalReplay.reference_result.metrics.total_cost_paid,
      } : null,
      analytics_comparison: proposalReplay.comparison,
    },
    diagnostics_summary: {
      diagnostics_available: proposalReplay.diagnostics_comparison != null,
      top_factor_exposure_change: proposalReplay.diagnostics_comparison?.top_factor_exposure_change ?? null,
      top_volatility_change: proposalReplay.diagnostics_comparison?.top_volatility_change ?? null,
      top_risk_contribution_change: proposalReplay.diagnostics_comparison?.top_risk_contribution_change ?? null,
      top_concentration_change: proposalReplay.diagnostics_comparison?.top_concentration_change ?? null,
      top_stress_scenario_change: proposalReplay.diagnostics_comparison?.top_stress_scenario_change ?? null,
    },
  }
}

function assertValidReviewSnapshotPMSummaryEnvelope(
  value: unknown,
  label: string,
  allowedRoles: ReadonlyArray<'saved_proposal' | 'baseline' | 'candidate'> = ['saved_proposal', 'baseline', 'candidate'],
): asserts value is ReviewSnapshotArtifact['pm_summary'] {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }

  const candidate = value as Partial<ReviewSnapshotArtifact['pm_summary']>
  if (candidate.pm_summary_version !== 1) {
    throw new Error(`${label} has unsupported pm_summary_version`)
  }
  if (!candidate.role || !allowedRoles.includes(candidate.role)) {
    throw new Error(`${label} role is invalid`)
  }
  if (!candidate.provenance || typeof candidate.provenance !== 'object') {
    throw new Error(`${label} provenance is invalid`)
  }
  if (
    candidate.provenance.source !== 'persisted_review_snapshot_artifact'
    || candidate.provenance.artifact_kind !== 'portfolio_review_snapshot'
    || candidate.provenance.schema_version !== 'review_snapshot_artifact_v1'
    || candidate.provenance.consumer_kind !== 'saved_hypothetical_replay_proposal'
  ) {
    throw new Error(`${label} provenance is invalid`)
  }
  if (!candidate.provenance.lineage || typeof candidate.provenance.lineage !== 'object') {
    throw new Error(`${label} provenance lineage is invalid`)
  }
  if (
    !isNonEmptyString(candidate.provenance.lineage.workspace_id)
    || !isNonEmptyString(candidate.provenance.lineage.source_draft_id)
    || !isNonEmptyString(candidate.provenance.lineage.source_base_node_id)
    || !isNonEmptyString(candidate.provenance.lineage.proposal_family_id)
    || !isNonEmptyString(candidate.provenance.lineage.proposal_id)
    || typeof candidate.provenance.lineage.version_number !== 'number'
    || candidate.provenance.lineage.source_kind !== 'hypothetical_replacement_replay'
  ) {
    throw new Error(`${label} provenance lineage is invalid`)
  }
  assertSnapshotProposalSourceLabelShape(candidate.provenance.proposal_source, `${label} provenance proposal_source`)
  if (!candidate.truth_labels || typeof candidate.truth_labels !== 'object') {
    throw new Error(`${label} truth_labels are invalid`)
  }
  if (
    candidate.truth_labels.proposal_truth !== 'review_only_hypothetical_proposal'
    || candidate.truth_labels.portfolio_truth !== 'draft_snapshot_not_applied'
    || candidate.truth_labels.analytics_truth !== 'hypothetical_replay_analytics_only'
    || candidate.truth_labels.review_scope !== 'proposal_review_context_only'
  ) {
    throw new Error(`${label} truth_labels are invalid`)
  }
  if (candidate.replay_type !== 'standard' && candidate.replay_type !== 'overlay_aware') {
    throw new Error(`${label} replay_type is invalid`)
  }
  if (!candidate.review_basis || typeof candidate.review_basis !== 'object') {
    throw new Error(`${label} review_basis is invalid`)
  }
  if (
    candidate.review_basis.benchmark_separation !== 'explicit_per_snapshot_benchmark_fields'
    || !isNonEmptyString(candidate.review_basis.benchmark_symbol)
    || !candidate.review_basis.replay_window
    || !isNonEmptyString(candidate.review_basis.replay_window.start_date)
    || !isNonEmptyString(candidate.review_basis.replay_window.end_date)
    || !isNonEmptyString(candidate.review_basis.rebalance_frequency)
    || typeof candidate.review_basis.commission_bps !== 'number'
    || typeof candidate.review_basis.slippage_bps !== 'number'
    || !isNonEmptyString(candidate.review_basis.derivation_basis)
    || !isNonEmptyString(candidate.review_basis.candidate_construction_rule)
  ) {
    throw new Error(`${label} review_basis is invalid`)
  }
  if (!candidate.methodology || typeof candidate.methodology !== 'object') {
    throw new Error(`${label} methodology is invalid`)
  }
  if (!isNonEmptyString(candidate.methodology.methodology) || !candidate.methodology.methodology_provenance || typeof candidate.methodology.methodology_provenance !== 'object') {
    throw new Error(`${label} methodology is invalid`)
  }
  if (!candidate.analytics_summary || typeof candidate.analytics_summary !== 'object') {
    throw new Error(`${label} analytics_summary is invalid`)
  }
  if (!candidate.analytics_summary.candidate_analytics || typeof candidate.analytics_summary.candidate_analytics !== 'object') {
    throw new Error(`${label} analytics_summary candidate_analytics is invalid`)
  }
  if (!candidate.diagnostics_summary || typeof candidate.diagnostics_summary !== 'object') {
    throw new Error(`${label} diagnostics_summary is invalid`)
  }
  if (typeof candidate.diagnostics_summary.diagnostics_available !== 'boolean') {
    throw new Error(`${label} diagnostics_summary is invalid`)
  }
}

function assertCachedSavedProposalPMSummaryMatchesPersisted(
  proposal: VersionedProposalArtifact,
  reviewSnapshotArtifact: ReviewSnapshotArtifact,
) {
  if (!proposal.reviewSnapshotPMSummary) {
    throw new Error('Saved proposal cached reviewSnapshotPMSummary is missing while persisted review snapshot artifact pm_summary exists')
  }
  assertValidReviewSnapshotPMSummaryEnvelope(
    proposal.reviewSnapshotPMSummary,
    'Saved proposal cached reviewSnapshotPMSummary',
    ['saved_proposal'],
  )
  if (JSON.stringify(proposal.reviewSnapshotPMSummary) !== JSON.stringify(reviewSnapshotArtifact.pm_summary)) {
    throw new Error('Saved proposal cached reviewSnapshotPMSummary does not match persisted review snapshot artifact pm_summary')
  }
}

function isRecognizedLegacySavedProposalPMSummaryOmission(proposal: VersionedProposalArtifact) {
  return proposal.reviewSnapshotPMSummary == null && isRecognizedLegacySavedProposalProposalSourceOmission(proposal)
}

function hydrateLoadedSavedProposalArtifact(proposal: VersionedProposalArtifact): VersionedProposalArtifact {
  const canonicalProposal = assertSavedProposalArtifactLineageIntegrity(proposal)
  const topLevelProposalSource = canonicalProposal.proposalSource ?? null
  const snapshotProposalSource = canonicalProposal.reviewSnapshot.proposal.proposal_source ?? null
  const effectivePMSummary = canonicalProposal.reviewSnapshotPMSummary ?? null

  const hydrateProposalSource = (effectiveProposalSource: ProposalSourceLabel) => ({
    ...canonicalProposal,
    proposalSource: effectiveProposalSource,
    proposalCapture: {
      ...canonicalProposal.proposalCapture,
      proposal: {
        ...canonicalProposal.proposalCapture.proposal,
        proposal_source: buildSnapshotProposalSourceLabel(effectiveProposalSource),
      },
    },
  })

  if (topLevelProposalSource != null) {
    const hydratedProposal = snapshotProposalSource == null
      ? hydrateProposalSource(topLevelProposalSource)
      : canonicalProposal

    return {
      ...assertSavedProposalArtifactProposalSourceIntegrity(hydratedProposal),
      ...(effectivePMSummary ? { reviewSnapshotPMSummary: effectivePMSummary } : {}),
    }
  }

  const effectiveProposalSource = snapshotProposalSource == null && isRecognizedLegacySavedProposalProposalSourceOmission(canonicalProposal)
    ? buildCanonicalReviewOnlyProposalSourceLabel()
    : null

  if (!effectiveProposalSource) {
    throw new Error('Saved proposal is missing authoritative proposalSource')
  }

  return {
    ...hydrateProposalSource(effectiveProposalSource),
    ...(isRecognizedLegacySavedProposalPMSummaryOmission(canonicalProposal) ? {
      reviewSnapshotPMSummary: buildSavedProposalReviewSnapshotPMSummary({
        ...hydrateProposalSource(effectiveProposalSource),
      }),
    } : {}),
  }
}

function canonicalizeRestoredSavedProposalArtifact(proposal: VersionedProposalArtifact): VersionedProposalArtifact {
  if (proposal.reviewSnapshot.proposal.proposal_source != null) {
    return proposal
  }

  return {
    ...proposal,
    reviewSnapshot: {
      ...proposal.reviewSnapshot,
      proposal: {
        ...proposal.reviewSnapshot.proposal,
        proposal_source: buildSnapshotProposalSourceLabel(proposal.proposalSource),
      },
    },
  }
}

function assertValidReviewSnapshotArtifactIdentity(value: unknown, label: string): asserts value is ReviewSnapshotArtifact['identity'] {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }
  const candidate = value as Partial<ReviewSnapshotArtifact['identity']>
  if (
    candidate.artifact_kind !== 'portfolio_review_snapshot'
    || candidate.schema_version !== 'review_snapshot_artifact_v1'
    || candidate.consumer_kind !== 'saved_hypothetical_replay_proposal'
    || !isNonEmptyString(candidate.artifact_id)
    || !isNonEmptyString(candidate.fingerprint)
  ) {
    throw new Error(`${label} is invalid`)
  }
}

function assertValidReviewSnapshotArtifact(value: unknown, label: string): asserts value is ReviewSnapshotArtifact {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }
  const candidate = value as Partial<ReviewSnapshotArtifact>
  assertValidReviewSnapshotArtifactIdentity(candidate.identity, `${label} identity`)
  if (!candidate.lineage || typeof candidate.lineage !== 'object') {
    throw new Error(`${label} lineage is invalid`)
  }
  if (!candidate.review_basis || typeof candidate.review_basis !== 'object') {
    throw new Error(`${label} review_basis is invalid`)
  }
  if (!candidate.truth_labels || typeof candidate.truth_labels !== 'object') {
    throw new Error(`${label} truth_labels are invalid`)
  }
  if (!candidate.compact_summary || typeof candidate.compact_summary !== 'object') {
    throw new Error(`${label} compact_summary is invalid`)
  }
  assertValidReviewSnapshotProposalCapture(candidate.proposal_capture, `${label} proposal_capture`)
  assertValidReviewSnapshotPMSummaryEnvelope(candidate.pm_summary, `${label} pm_summary`, ['saved_proposal'])
  if (!candidate.source_payload || typeof candidate.source_payload !== 'object') {
    throw new Error(`${label} source_payload is invalid`)
  }
}

function assertValidReviewSnapshotOpenHandoff(value: unknown, label: string): asserts value is ReviewSnapshotOpenHandoff {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }
  const candidate = value as Partial<ReviewSnapshotOpenHandoff>
  if (candidate.handoff_kind !== 'review_snapshot_open_handoff_v1') {
    throw new Error(`${label} has unsupported handoff kind`)
  }
  if (
    candidate.artifact_kind !== 'portfolio_review_snapshot'
    || candidate.schema_version !== 'review_snapshot_artifact_v1'
    || candidate.consumer_kind !== 'saved_hypothetical_replay_proposal'
    || !isNonEmptyString(candidate.artifact_id)
  ) {
    throw new Error(`${label} is invalid`)
  }
}

function assertValidReviewSnapshotProposalCapture(value: unknown, label: string): asserts value is ReviewSnapshotArtifact['proposal_capture'] {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }
  const candidate = value as Partial<ReviewSnapshotArtifact['proposal_capture']>
  if (candidate.capture_version !== 1) {
    throw new Error(`${label} has unsupported capture_version`)
  }
  if (candidate.capture_kind !== 'workspace_review_saved_proposal') {
    throw new Error(`${label} capture_kind is invalid`)
  }
  assertValidReviewSnapshotOpenHandoff(candidate.open_handoff, `${label} open_handoff`)
  if (!candidate.lineage || typeof candidate.lineage !== 'object') {
    throw new Error(`${label} lineage is invalid`)
  }
  if (!candidate.proposal || typeof candidate.proposal !== 'object') {
    throw new Error(`${label} proposal is invalid`)
  }
  if (
    candidate.proposal.source !== 'draft_replacement_intent'
    || !isNonEmptyString(candidate.proposal.incumbent_symbol)
    || !isNonEmptyString(candidate.proposal.candidate_symbol)
  ) {
    throw new Error(`${label} proposal is invalid`)
  }
  assertValidSnapshotProposalSourceLabel(candidate.proposal.proposal_source, `${label} proposal proposal_source`)
  if (candidate.replay_type !== 'standard' && candidate.replay_type !== 'overlay_aware') {
    throw new Error(`${label} replay_type is invalid`)
  }
  if (!candidate.replay_provenance || typeof candidate.replay_provenance !== 'object') {
    throw new Error(`${label} replay_provenance is invalid`)
  }
  if (!candidate.review_basis || typeof candidate.review_basis !== 'object') {
    throw new Error(`${label} review_basis is invalid`)
  }
  if (
    candidate.review_basis.benchmark_separation !== 'explicit_per_snapshot_benchmark_fields'
    || !isNonEmptyString(candidate.review_basis.benchmark_symbol)
    || !candidate.review_basis.replay_window
    || !isNonEmptyString(candidate.review_basis.replay_window.start_date)
    || !isNonEmptyString(candidate.review_basis.replay_window.end_date)
    || !isNonEmptyString(candidate.review_basis.rebalance_frequency)
    || typeof candidate.review_basis.commission_bps !== 'number'
    || typeof candidate.review_basis.slippage_bps !== 'number'
    || !isNonEmptyString(candidate.review_basis.derivation_basis)
    || !isNonEmptyString(candidate.review_basis.candidate_construction_rule)
  ) {
    throw new Error(`${label} review_basis is invalid`)
  }
}

function assertValidReviewSnapshotOpenResponse(value: unknown, label: string): asserts value is ReviewSnapshotOpenResponse {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }
  const candidate = value as Partial<ReviewSnapshotOpenResponse>
  assertValidReviewSnapshotOpenHandoff(candidate.handoff, `${label} handoff`)
  assertValidReviewSnapshotArtifact(candidate.artifact, `${label} artifact`)
  assertValidReviewSnapshotPMSummaryEnvelope(candidate.pm_summary, `${label} pm_summary`, ['saved_proposal'])
  if (!candidate.replay_payload || typeof candidate.replay_payload !== 'object') {
    throw new Error(`${label} replay_payload is invalid`)
  }
  if (candidate.handoff.artifact_id !== candidate.artifact.identity.artifact_id) {
    throw new Error(`${label} handoff artifact_id does not match persisted artifact identity`)
  }
  if (candidate.handoff.artifact_kind !== candidate.artifact.identity.artifact_kind) {
    throw new Error(`${label} handoff artifact_kind does not match persisted artifact identity`)
  }
  if (candidate.handoff.schema_version !== candidate.artifact.identity.schema_version) {
    throw new Error(`${label} handoff schema_version does not match persisted artifact identity`)
  }
  if (candidate.handoff.consumer_kind !== candidate.artifact.identity.consumer_kind) {
    throw new Error(`${label} handoff consumer_kind does not match persisted artifact identity`)
  }
  if (JSON.stringify(candidate.handoff) !== JSON.stringify(candidate.artifact.proposal_capture.open_handoff)) {
    throw new Error(`${label} handoff does not match persisted artifact proposal_capture open_handoff`)
  }
  if (JSON.stringify(candidate.pm_summary) !== JSON.stringify(candidate.artifact.pm_summary)) {
    throw new Error(`${label} pm_summary does not match persisted artifact pm_summary`)
  }
  if (JSON.stringify(candidate.replay_payload) !== JSON.stringify(candidate.artifact.source_payload)) {
    throw new Error(`${label} replay_payload does not match persisted artifact source_payload`)
  }
}

export function assertValidReviewSnapshotComparisonResponseEnvelope(response: unknown): ReviewSnapshotComparisonResponse {
  if (!response || typeof response !== 'object') {
    throw new Error('Review snapshot comparison response is invalid')
  }
  const candidate = response as Partial<ReviewSnapshotComparisonResponse>
  if (candidate.provenance !== 'persisted_review_snapshot_artifacts_only') {
    throw new Error('Review snapshot comparison response provenance is invalid')
  }
  if (!candidate.family_key || typeof candidate.family_key !== 'object') {
    throw new Error('Review snapshot comparison response family_key is invalid')
  }
  if (
    !isNonEmptyString(candidate.family_key.workspace_id)
    || !isNonEmptyString(candidate.family_key.source_draft_id)
    || !isNonEmptyString(candidate.family_key.source_base_node_id)
    || !isNonEmptyString(candidate.family_key.proposal_family_id)
    || candidate.family_key.source_kind !== 'hypothetical_replacement_replay'
  ) {
    throw new Error('Review snapshot comparison response family_key is invalid')
  }
  if (candidate.benchmark_separation !== 'explicit_per_snapshot_benchmark_fields') {
    throw new Error('Review snapshot comparison response benchmark_separation is invalid')
  }
  if (!candidate.baseline_pm_summary || typeof candidate.baseline_pm_summary !== 'object') {
    throw new Error('Review snapshot comparison response baseline_pm_summary is invalid')
  }
  if (!candidate.candidate_pm_summary || typeof candidate.candidate_pm_summary !== 'object') {
    throw new Error('Review snapshot comparison response candidate_pm_summary is invalid')
  }
  if ((candidate.baseline_pm_summary as { role?: unknown }).role !== 'baseline') {
    throw new Error('Review snapshot comparison response baseline_pm_summary role is invalid')
  }
  if ((candidate.candidate_pm_summary as { role?: unknown }).role !== 'candidate') {
    throw new Error('Review snapshot comparison response candidate_pm_summary role is invalid')
  }
  assertValidReviewSnapshotPMSummaryEnvelope(
    candidate.baseline_pm_summary,
    'Review snapshot comparison response baseline_pm_summary',
    ['baseline'],
  )
  assertValidReviewSnapshotPMSummaryEnvelope(
    candidate.candidate_pm_summary,
    'Review snapshot comparison response candidate_pm_summary',
    ['candidate'],
  )
  assertReviewSnapshotFamilyKeyMatchesLineage(
    candidate.family_key,
    candidate.baseline_pm_summary.provenance.lineage,
    'Review snapshot comparison response baseline_pm_summary provenance lineage',
  )
  assertReviewSnapshotFamilyKeyMatchesLineage(
    candidate.family_key,
    candidate.candidate_pm_summary.provenance.lineage,
    'Review snapshot comparison response candidate_pm_summary provenance lineage',
  )
  return response as ReviewSnapshotComparisonResponse
}

function assertValidReviewSnapshotFamilyKey(value: unknown, label: string, expectedWorkspaceId?: string): asserts value is ReviewSnapshotFamilyKey {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }
  const candidate = value as Partial<ReviewSnapshotFamilyKey>
  if (
    !isNonEmptyString(candidate.workspace_id)
    || !isNonEmptyString(candidate.source_draft_id)
    || !isNonEmptyString(candidate.source_base_node_id)
    || !isNonEmptyString(candidate.proposal_family_id)
    || candidate.source_kind !== 'hypothetical_replacement_replay'
    || (expectedWorkspaceId !== undefined && candidate.workspace_id !== expectedWorkspaceId)
  ) {
    throw new Error(`${label} is invalid`)
  }
}

function assertReviewSnapshotFamilyKeyMatchesLineage(
  familyKey: ReviewSnapshotFamilyKey,
  lineage: unknown,
  label: string,
) {
  if (!lineage || typeof lineage !== 'object') {
    throw new Error(`${label} is invalid`)
  }
  const candidate = lineage as Partial<ReviewSnapshotArtifact['lineage']>
  if (candidate.workspace_id !== familyKey.workspace_id) {
    throw new Error(`${label} workspace_id is invalid`)
  }
  if (candidate.source_draft_id !== familyKey.source_draft_id) {
    throw new Error(`${label} source_draft_id is invalid`)
  }
  if (candidate.source_base_node_id !== familyKey.source_base_node_id) {
    throw new Error(`${label} source_base_node_id is invalid`)
  }
  if (candidate.proposal_family_id !== familyKey.proposal_family_id) {
    throw new Error(`${label} proposal_family_id is invalid`)
  }
  if (candidate.source_kind !== familyKey.source_kind) {
    throw new Error(`${label} source_kind is invalid`)
  }
}

export function assertValidReviewSnapshotFamilyReviewResponseEnvelope(response: unknown): ReviewSnapshotFamilyReviewResponse {
  if (!response || typeof response !== 'object') {
    throw new Error('Review snapshot family review response is invalid')
  }
  const candidate = response as Partial<ReviewSnapshotFamilyReviewResponse>
  if (candidate.review_kind !== 'review_snapshot_family_review') {
    throw new Error('Review snapshot family review response review_kind is invalid')
  }
  if (candidate.provenance !== 'persisted_review_snapshot_artifacts_only') {
    throw new Error('Review snapshot family review response provenance is invalid')
  }
  if (candidate.compare_selection_policy !== 'exactly_two_distinct_family_siblings') {
    throw new Error('Review snapshot family review response compare_selection_policy is invalid')
  }
  assertValidReviewSnapshotFamilyKey(candidate.family_key, 'Review snapshot family review response family_key')
  if (!candidate.anchor || typeof candidate.anchor !== 'object') {
    throw new Error('Review snapshot family review response anchor is invalid')
  }
  if (!Array.isArray(candidate.siblings) || candidate.siblings.length < 1) {
    throw new Error('Review snapshot family review response siblings are invalid')
  }
  const validateSibling = (sibling: unknown, label: string) => {
    if (!sibling || typeof sibling !== 'object') {
      throw new Error(`${label} is invalid`)
    }
    const summary = sibling as NonNullable<ReviewSnapshotFamilyReviewResponse['siblings']>[number]
    assertValidReviewSnapshotArtifactIdentity(summary.identity, `${label} identity`)
    assertValidReviewSnapshotOpenHandoff(summary.open_handoff, `${label} open_handoff`)
    assertValidReviewSnapshotPMSummaryEnvelope(summary.pm_summary, `${label} pm_summary`, ['saved_proposal'])
    if (!summary.lineage || typeof summary.lineage !== 'object') {
      throw new Error(`${label} lineage is invalid`)
    }
    if (!summary.comparison_eligibility || typeof summary.comparison_eligibility !== 'object') {
      throw new Error(`${label} comparison_eligibility is invalid`)
    }
    if (typeof summary.comparison_eligibility.eligible !== 'boolean') {
      throw new Error(`${label} comparison_eligibility is invalid`)
    }
    if (!['compatible_family_sibling_available', 'no_compatible_family_sibling'].includes(summary.comparison_eligibility.reason)) {
      throw new Error(`${label} comparison_eligibility is invalid`)
    }
    if (!Array.isArray(summary.comparison_eligibility.compatible_sibling_artifact_ids)) {
      throw new Error(`${label} comparison_eligibility is invalid`)
    }
    assertReviewSnapshotFamilyKeyMatchesLineage(candidate.family_key, summary.lineage, `${label} lineage`)
    assertReviewSnapshotFamilyKeyMatchesLineage(candidate.family_key, summary.pm_summary.provenance.lineage, `${label} pm_summary provenance lineage`)
    if (JSON.stringify(summary.lineage) !== JSON.stringify(summary.pm_summary.provenance.lineage)) {
      throw new Error(`${label} lineage does not match pm_summary provenance lineage`)
    }
  }
  validateSibling(candidate.anchor, 'Review snapshot family review response anchor')
  candidate.siblings.forEach((sibling, index) => validateSibling(sibling, `Review snapshot family review response sibling ${index + 1}`))
  if (!candidate.siblings.some((sibling) => sibling.identity.artifact_id === candidate.anchor?.identity.artifact_id)) {
    throw new Error('Review snapshot family review response anchor is missing from siblings')
  }
  return response as ReviewSnapshotFamilyReviewResponse
}

export function assertValidReviewSnapshotFamilyInboxResponseEnvelope(response: unknown): ReviewSnapshotFamilyInboxResponse {
  if (!response || typeof response !== 'object') {
    throw new Error('Review snapshot family inbox response is invalid')
  }
  const candidate = response as Partial<ReviewSnapshotFamilyInboxResponse>
  if (candidate.inbox_kind !== 'review_snapshot_family_inbox') {
    throw new Error('Review snapshot family inbox response inbox_kind is invalid')
  }
  if (!isNonEmptyString(candidate.workspace_id)) {
    throw new Error('Review snapshot family inbox response workspace_id is invalid')
  }
  if (candidate.provenance !== 'persisted_review_snapshot_artifacts_only') {
    throw new Error('Review snapshot family inbox response provenance is invalid')
  }
  if (!Array.isArray(candidate.rows)) {
    throw new Error('Review snapshot family inbox response rows are invalid')
  }
  const seenFamilyKeys = new Set<string>()
  candidate.rows.forEach((row, index) => {
    const label = `Review snapshot family inbox response row ${index + 1}`
    if (!row || typeof row !== 'object') {
      throw new Error(`${label} is invalid`)
    }
    assertValidReviewSnapshotFamilyKey(row.family_key, `${label} family_key`, candidate.workspace_id)
    const familyKeyKey = JSON.stringify(row.family_key)
    if (seenFamilyKeys.has(familyKeyKey)) {
      throw new Error('Review snapshot family inbox response contains duplicate family_key rows')
    }
    seenFamilyKeys.add(familyKeyKey)
    assertValidReviewSnapshotArtifactIdentity(row.latest_identity, `${label} latest_identity`)
    assertValidReviewSnapshotPMSummaryEnvelope(row.pm_summary, `${label} pm_summary`, ['saved_proposal'])
    assertValidReviewSnapshotProposalCapture(row.proposal_capture, `${label} proposal_capture`)
    assertReviewSnapshotFamilyKeyMatchesLineage(row.family_key, row.lineage, `${label} lineage`)
    assertReviewSnapshotFamilyKeyMatchesLineage(row.family_key, row.pm_summary.provenance.lineage, `${label} pm_summary provenance lineage`)
    assertReviewSnapshotFamilyKeyMatchesLineage(row.family_key, row.proposal_capture.lineage, `${label} proposal_capture lineage`)
    if (row.lineage.proposal_id !== row.pm_summary.provenance.lineage.proposal_id) {
      throw new Error(`${label} lineage proposal_id is invalid`)
    }
    if (JSON.stringify(row.lineage) !== JSON.stringify(row.pm_summary.provenance.lineage)) {
      throw new Error(`${label} lineage does not match pm_summary provenance lineage`)
    }
    if (JSON.stringify(row.lineage) !== JSON.stringify(row.proposal_capture.lineage)) {
      throw new Error(`${label} lineage does not match proposal_capture lineage`)
    }
    if (row.proposal_capture.open_handoff.artifact_id !== row.latest_identity.artifact_id) {
      throw new Error(`${label} latest_identity artifact_id is invalid`)
    }
    if (JSON.stringify(row.pm_summary.provenance.proposal_source) !== JSON.stringify(row.proposal_capture.proposal.proposal_source)) {
      throw new Error(`${label} proposal_source is invalid`)
    }
    if (typeof row.sibling_count !== 'number' || row.sibling_count < 1) {
      throw new Error(`${label} sibling_count is invalid`)
    }
    if (!row.compare_readiness || typeof row.compare_readiness !== 'object') {
      throw new Error(`${label} compare_readiness is invalid`)
    }
    if (typeof row.compare_readiness.ready !== 'boolean') {
      throw new Error(`${label} compare_readiness is invalid`)
    }
    if (!['compatible_family_pair_available', 'no_compatible_family_pair'].includes(row.compare_readiness.reason)) {
      throw new Error(`${label} compare_readiness is invalid`)
    }
    if (typeof row.compare_readiness.compatible_pair_count !== 'number' || row.compare_readiness.compatible_pair_count < 0) {
      throw new Error(`${label} compare_readiness is invalid`)
    }
    if (row.compare_readiness.ready && row.compare_readiness.compatible_pair_count < 1) {
      throw new Error(`${label} compare_readiness is invalid`)
    }
    if (!row.compare_readiness.ready && row.compare_readiness.compatible_pair_count !== 0) {
      throw new Error(`${label} compare_readiness is invalid`)
    }
    if (!isNonEmptyString(row.latest_saved_at)) {
      throw new Error(`${label} latest_saved_at is invalid`)
    }
    if (row.latest_order_provenance !== 'persisted_artifact_file_mtime') {
      throw new Error(`${label} latest_order_provenance is invalid`)
    }
  })
  return response as ReviewSnapshotFamilyInboxResponse
}

export function assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(response: unknown): ReviewSnapshotActiveThesisCrossFamilyQueueResponse {
  if (!response || typeof response !== 'object') {
    throw new Error('Review snapshot active thesis cross-family queue response is invalid')
  }
  const candidate = response as Partial<ReviewSnapshotActiveThesisCrossFamilyQueueResponse>
  if (candidate.queue_kind !== 'review_snapshot_active_thesis_cross_family_queue') {
    throw new Error('Review snapshot active thesis cross-family queue response queue_kind is invalid')
  }
  if (candidate.provenance !== 'persisted_review_snapshot_artifacts_and_active_thesis_reference_only') {
    throw new Error('Review snapshot active thesis cross-family queue response provenance is invalid')
  }
  if (candidate.queue_ordering !== 'latest_saved_at_desc_then_artifact_id_desc') {
    throw new Error('Review snapshot active thesis cross-family queue response queue_ordering is invalid')
  }
  if (!candidate.active_thesis || typeof candidate.active_thesis !== 'object') {
    throw new Error('Review snapshot active thesis cross-family queue response active_thesis is invalid')
  }
  if (!isNonEmptyString(candidate.active_thesis.source_proposal_id)) {
    throw new Error('Review snapshot active thesis cross-family queue response active_thesis source_proposal_id is invalid')
  }
  assertValidReviewSnapshotOpenHandoff(candidate.active_thesis.handoff, 'Review snapshot active thesis cross-family queue response active_thesis handoff')
  assertValidReviewSnapshotArtifactIdentity(candidate.active_thesis.identity, 'Review snapshot active thesis cross-family queue response active_thesis identity')
  assertValidReviewSnapshotFamilyKey(candidate.active_thesis.family_key, 'Review snapshot active thesis cross-family queue response active_thesis family_key')
  assertReviewSnapshotFamilyKeyMatchesLineage(
    candidate.active_thesis.family_key,
    candidate.active_thesis.lineage,
    'Review snapshot active thesis cross-family queue response active_thesis lineage',
  )
  if (candidate.active_thesis.source_proposal_id !== candidate.active_thesis.lineage.proposal_id) {
    throw new Error('Review snapshot active thesis cross-family queue response active_thesis source_proposal_id is invalid')
  }
  if (!Array.isArray(candidate.rows)) {
    throw new Error('Review snapshot active thesis cross-family queue response rows are invalid')
  }
  const seenFamilyKeys = new Set<string>()
  const seenArtifactIds = new Set<string>()
  let previousOrder: string | null = null
  candidate.rows.forEach((row, index) => {
    const label = `Review snapshot active thesis cross-family queue response row ${index + 1}`
    if (!row || typeof row !== 'object') {
      throw new Error(`${label} is invalid`)
    }
    assertValidReviewSnapshotFamilyKey(row.family_key, `${label} family_key`, candidate.active_thesis!.family_key.workspace_id)
    assertValidReviewSnapshotArtifactIdentity(row.latest_identity, `${label} latest_identity`)
    assertReviewSnapshotFamilyKeyMatchesLineage(row.family_key, row.lineage, `${label} lineage`)
    const familyKeyKey = JSON.stringify(row.family_key)
    if (seenFamilyKeys.has(familyKeyKey)) {
      throw new Error('Review snapshot active thesis cross-family queue response contains duplicate family_key rows')
    }
    seenFamilyKeys.add(familyKeyKey)
    if (seenArtifactIds.has(row.latest_identity.artifact_id)) {
      throw new Error('Review snapshot active thesis cross-family queue response contains duplicate canonical row identities')
    }
    seenArtifactIds.add(row.latest_identity.artifact_id)
    if (row.family_key.source_draft_id !== candidate.active_thesis!.family_key.source_draft_id) {
      throw new Error(`${label} family_key source_draft_id is invalid`)
    }
    if (row.family_key.source_base_node_id !== candidate.active_thesis!.family_key.source_base_node_id) {
      throw new Error(`${label} family_key source_base_node_id is invalid`)
    }
    if (row.family_key.source_kind !== candidate.active_thesis!.family_key.source_kind) {
      throw new Error(`${label} family_key source_kind is invalid`)
    }
    if (row.family_key.proposal_family_id === candidate.active_thesis!.family_key.proposal_family_id) {
      throw new Error(`${label} family_key proposal_family_id is invalid`)
    }
    if (!row.family_separation || typeof row.family_separation !== 'object') {
      throw new Error(`${label} family_separation is invalid`)
    }
    if (
      row.family_separation.separation_kind !== 'distinct_proposal_family_id'
      || row.family_separation.active_thesis_proposal_family_id !== candidate.active_thesis!.family_key.proposal_family_id
      || row.family_separation.queue_proposal_family_id !== row.family_key.proposal_family_id
      || row.family_separation.active_thesis_proposal_family_id === row.family_separation.queue_proposal_family_id
    ) {
      throw new Error(`${label} family_separation is invalid`)
    }
    assertSnapshotProposalSourceLabelShape(row.proposal_source, `${label} proposal_source`)
    if (!row.truth_labels || typeof row.truth_labels !== 'object') {
      throw new Error(`${label} truth_labels are invalid`)
    }
    if (
      row.truth_labels.proposal_truth !== 'review_only_hypothetical_proposal'
      || row.truth_labels.portfolio_truth !== 'draft_snapshot_not_applied'
      || row.truth_labels.analytics_truth !== 'hypothetical_replay_analytics_only'
      || row.truth_labels.review_scope !== 'proposal_review_context_only'
    ) {
      throw new Error(`${label} truth_labels are invalid`)
    }
    if (!row.trust_visibility || typeof row.trust_visibility !== 'object') {
      throw new Error(`${label} trust_visibility is invalid`)
    }
    if (row.trust_visibility.benchmark_separation !== 'explicit_per_snapshot_benchmark_fields') {
      throw new Error(`${label} trust_visibility is invalid`)
    }
    if (!row.pm_summary_fields || typeof row.pm_summary_fields !== 'object') {
      throw new Error(`${label} pm_summary_fields are invalid`)
    }
    if (row.pm_summary_fields.review_basis.benchmark_separation !== 'explicit_per_snapshot_benchmark_fields') {
      throw new Error(`${label} pm_summary_fields are invalid`)
    }
    if (row.trust_visibility.benchmark_separation !== row.pm_summary_fields.review_basis.benchmark_separation) {
      throw new Error(`${label} benchmark_separation is invalid`)
    }
    if (!isNonEmptyString(row.latest_saved_at)) {
      throw new Error(`${label} latest_saved_at is invalid`)
    }
    if (row.queue_order_provenance !== 'persisted_artifact_file_mtime_desc_then_artifact_id_desc') {
      throw new Error(`${label} queue_order_provenance is invalid`)
    }
    const currentOrder = `${row.latest_saved_at}::${row.latest_identity.artifact_id}`
    if (previousOrder !== null && currentOrder > previousOrder) {
      throw new Error('Review snapshot active thesis cross-family queue response ordering is invalid')
    }
    previousOrder = currentOrder
  })
  return response as ReviewSnapshotActiveThesisCrossFamilyQueueResponse
}

function assertSavedProposalArtifactReviewSnapshotIdentity(proposal: VersionedProposalArtifact, reviewSnapshotArtifact: ReviewSnapshotArtifact | null) {
  if (!proposal.reviewSnapshotArtifactId) {
    throw new Error('Saved proposal is missing authoritative reviewSnapshotArtifactId')
  }
  if (!reviewSnapshotArtifact) {
    throw new Error('Saved proposal review snapshot artifact is missing')
  }
  assertValidReviewSnapshotArtifact(reviewSnapshotArtifact, 'Saved proposal review snapshot artifact')
  if (reviewSnapshotArtifact.identity.artifact_id !== proposal.reviewSnapshotArtifactId) {
    throw new Error('Saved proposal reviewSnapshotArtifactId does not match persisted review snapshot artifact identity')
  }
  if (reviewSnapshotArtifact.lineage.proposal_id !== proposal.id) {
    throw new Error('Saved proposal review snapshot lineage proposal_id does not match saved proposal id')
  }
  if (reviewSnapshotArtifact.lineage.workspace_id !== proposal.workspaceId) {
    throw new Error('Saved proposal review snapshot lineage workspace_id does not match saved proposal workspaceId')
  }
  if (reviewSnapshotArtifact.lineage.source_draft_id !== proposal.sourceDraftId) {
    throw new Error('Saved proposal review snapshot lineage source_draft_id does not match saved proposal sourceDraftId')
  }
  if (reviewSnapshotArtifact.lineage.source_base_node_id !== proposal.sourceBaseNodeId) {
    throw new Error('Saved proposal review snapshot lineage source_base_node_id does not match saved proposal sourceBaseNodeId')
  }
  if (reviewSnapshotArtifact.lineage.proposal_family_id !== proposal.proposalFamilyId) {
    throw new Error('Saved proposal review snapshot lineage proposal_family_id does not match saved proposal proposalFamilyId')
  }
  if (reviewSnapshotArtifact.lineage.version_number !== proposal.versionNumber) {
    throw new Error('Saved proposal review snapshot lineage version_number does not match saved proposal versionNumber')
  }
  const payload = reviewSnapshotArtifact.source_payload.overlay_replay ?? reviewSnapshotArtifact.source_payload.replay
  if (!payload) {
    throw new Error('Saved proposal review snapshot artifact is missing authoritative replay payload')
  }
  if (JSON.stringify(payload) !== JSON.stringify(proposal.reviewSnapshot)) {
    throw new Error('Saved proposal review snapshot artifact payload does not match saved proposal reviewSnapshot')
  }
  if (!reviewSnapshotArtifact.proposal_capture || typeof reviewSnapshotArtifact.proposal_capture !== 'object') {
    throw new Error('Saved proposal review snapshot artifact is missing authoritative proposal_capture')
  }
  if (reviewSnapshotArtifact.proposal_capture.open_handoff.artifact_id !== proposal.reviewSnapshotArtifactId) {
    throw new Error('Saved proposal review snapshot proposal_capture open_handoff artifact_id does not match saved proposal reviewSnapshotArtifactId')
  }
  if (reviewSnapshotArtifact.proposal_capture.lineage.proposal_id !== proposal.id) {
    throw new Error('Saved proposal review snapshot proposal_capture lineage proposal_id does not match saved proposal id')
  }
  if (reviewSnapshotArtifact.proposal_capture.lineage.workspace_id !== proposal.workspaceId) {
    throw new Error('Saved proposal review snapshot proposal_capture lineage workspace_id does not match saved proposal workspaceId')
  }
}

export function assertSavedProposalProposalCaptureIntegrity(
  proposal: VersionedProposalArtifact,
  label = 'Saved proposal proposalCapture',
  options: { allowMissingReviewSnapshotProposalSource?: boolean } = {},
) {
  const capture = proposal.proposalCapture
  if (!capture || typeof capture !== 'object') {
    throw new Error(`${label} is missing`)
  }
  if (capture.capture_version !== 1) {
    throw new Error(`${label} has unsupported capture_version`)
  }
  if (capture.capture_kind !== 'workspace_review_saved_proposal') {
    throw new Error(`${label} capture_kind is invalid`)
  }
  assertValidReviewSnapshotOpenHandoff(capture.open_handoff, `${label} open_handoff`)
  if (capture.open_handoff.artifact_id !== proposal.reviewSnapshotArtifactId) {
    throw new Error(`${label} open_handoff artifact_id does not match saved proposal reviewSnapshotArtifactId`)
  }
  if (capture.lineage.workspace_id !== proposal.workspaceId) {
    throw new Error(`${label} lineage workspace_id does not match saved proposal workspaceId`)
  }
  if (capture.lineage.source_draft_id !== proposal.sourceDraftId) {
    throw new Error(`${label} lineage source_draft_id does not match saved proposal sourceDraftId`)
  }
  if (capture.lineage.source_base_node_id !== proposal.sourceBaseNodeId) {
    throw new Error(`${label} lineage source_base_node_id does not match saved proposal sourceBaseNodeId`)
  }
  if (capture.lineage.proposal_family_id !== proposal.proposalFamilyId) {
    throw new Error(`${label} lineage proposal_family_id does not match saved proposal proposalFamilyId`)
  }
  if (capture.lineage.proposal_id !== proposal.id) {
    throw new Error(`${label} lineage proposal_id does not match saved proposal id`)
  }
  if (capture.lineage.version_number !== proposal.versionNumber) {
    throw new Error(`${label} lineage version_number does not match saved proposal versionNumber`)
  }
  if (capture.proposal.source !== proposal.reviewSnapshot.proposal.source) {
    throw new Error(`${label} proposal source does not match saved proposal reviewSnapshot`)
  }
  assertValidSnapshotProposalSourceLabel(capture.proposal.proposal_source, `${label} proposal proposal_source`)
  if (
    proposal.reviewSnapshot.proposal.proposal_source == null
    && options.allowMissingReviewSnapshotProposalSource !== true
  ) {
    throw new Error(`${label} proposal proposal_source does not match saved proposal reviewSnapshot`)
  }
  if (
    proposal.reviewSnapshot.proposal.proposal_source != null
    && JSON.stringify(capture.proposal.proposal_source) !== JSON.stringify(proposal.reviewSnapshot.proposal.proposal_source)
  ) {
    throw new Error(`${label} proposal proposal_source does not match saved proposal reviewSnapshot`)
  }
  if (JSON.stringify(capture.proposal.proposal_source) !== JSON.stringify(buildSnapshotProposalSourceLabel(proposal.proposalSource))) {
    throw new Error(`${label} proposal proposal_source does not match saved proposal proposalSource`)
  }
  if (capture.proposal.incumbent_symbol !== proposal.reviewSnapshot.proposal.incumbent_symbol) {
    throw new Error(`${label} incumbent_symbol does not match saved proposal reviewSnapshot`)
  }
  if (capture.proposal.candidate_symbol !== proposal.reviewSnapshot.proposal.candidate_symbol) {
    throw new Error(`${label} candidate_symbol does not match saved proposal reviewSnapshot`)
  }
  const expectedReplayType = 'replay' in proposal.reviewSnapshot ? 'standard' : 'overlay_aware'
  if (capture.replay_type !== expectedReplayType) {
    throw new Error(`${label} replay_type does not match saved proposal reviewSnapshot`)
  }
  if (JSON.stringify(capture.replay_provenance) !== JSON.stringify(proposal.reviewSnapshot.replay_provenance)) {
    throw new Error(`${label} replay_provenance does not match saved proposal reviewSnapshot`)
  }
  if (capture.review_basis.benchmark_separation !== 'explicit_per_snapshot_benchmark_fields') {
    throw new Error(`${label} review_basis benchmark_separation is invalid`)
  }
  if (capture.review_basis.benchmark_symbol !== proposal.replayBasis.benchmarkSymbol) {
    throw new Error(`${label} review_basis benchmark_symbol does not match saved proposal replayBasis`)
  }
  if (capture.review_basis.replay_window.start_date !== proposal.replayBasis.startDate || capture.review_basis.replay_window.end_date !== proposal.replayBasis.endDate) {
    throw new Error(`${label} review_basis replay_window does not match saved proposal replayBasis`)
  }
  if (capture.review_basis.rebalance_frequency !== proposal.replayBasis.rebalanceFrequency) {
    throw new Error(`${label} review_basis rebalance_frequency does not match saved proposal replayBasis`)
  }
  if (capture.review_basis.commission_bps !== proposal.replayBasis.commissionBps) {
    throw new Error(`${label} review_basis commission_bps does not match saved proposal replayBasis`)
  }
  if (capture.review_basis.slippage_bps !== proposal.replayBasis.slippageBps) {
    throw new Error(`${label} review_basis slippage_bps does not match saved proposal replayBasis`)
  }
  if (capture.review_basis.derivation_basis !== proposal.replayBasis.derivationBasis) {
    throw new Error(`${label} review_basis derivation_basis does not match saved proposal replayBasis`)
  }
  if (capture.review_basis.candidate_construction_rule !== proposal.replayBasis.candidateConstructionRule) {
    throw new Error(`${label} review_basis candidate_construction_rule does not match saved proposal replayBasis`)
  }
}

function buildDesktopArtifactReviewBasis(input: {
  constructionArtifactId: string
  openedAt: string
  replay: ConstructionArtifactReplayResponse
}): PersistedConstructionArtifactReviewBasis {
  const reviewBasisSource = input.replay.review_basis
  if (!reviewBasisSource) {
    throw new Error('Persisted construction artifact review payload is missing canonical review_basis')
  }
  if (reviewBasisSource.construction_artifact_id !== input.constructionArtifactId) {
    throw new Error('Persisted construction artifact review payload review_basis conflicts with requested artifact identity')
  }
  if (!reviewBasisSource.preview_handoff || typeof reviewBasisSource.preview_handoff !== 'object') {
    throw new Error('Persisted construction artifact review payload review_basis is missing canonical preview handoff')
  }
  if (reviewBasisSource.preview_handoff.handoff_kind !== 'construction_artifact_preview_handoff_v1') {
    throw new Error('Persisted construction artifact review payload review_basis has unsupported preview handoff kind')
  }
  if (reviewBasisSource.preview_handoff.construction_artifact_id !== input.constructionArtifactId) {
    throw new Error('Persisted construction artifact review payload review_basis preview handoff conflicts with requested artifact identity')
  }
  if (JSON.stringify(reviewBasisSource.preview_handoff.effective_replay_params) !== JSON.stringify(input.replay.effective_replay_params)) {
    throw new Error('Persisted construction artifact review payload review_basis preview handoff conflicts with canonical replay params')
  }
  return {
    basisVersion: reviewBasisSource.basis_version,
    basisKind: 'persisted_construction_artifact_review',
    reviewScope: reviewBasisSource.review_scope,
    canonicalSource: reviewBasisSource.canonical_source,
    basisProvenanceLabel: reviewBasisSource.basis_provenance_label,
    portfolioTruth: reviewBasisSource.portfolio_truth,
    candidateTruth: reviewBasisSource.candidate_truth,
    constructionArtifactId: input.constructionArtifactId,
    previewHandoff: reviewBasisSource.preview_handoff,
    openedAt: input.openedAt,
    benchmarkSymbol: reviewBasisSource.benchmark_symbol ?? null,
    baseCurrency: reviewBasisSource.base_currency ?? null,
    replayWindow: {
      startDate: reviewBasisSource.replay_window.start_date ?? null,
      endDate: reviewBasisSource.replay_window.end_date ?? null,
    },
    baselineWeights: reviewBasisSource.baseline_weights,
    candidateWeights: reviewBasisSource.candidate_weights,
  }
}

function buildOptimizerHandoffReviewBasis(input: {
  handoffReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference']
  openedAt: string
  replay: OptimizerHandoffReplayResponse
}): PersistedOptimizerHandoffReviewBasis {
  const reviewBasisSource = input.replay.review_basis
  if (!reviewBasisSource) {
    throw new Error('Persisted optimizer handoff review payload is missing canonical review_basis')
  }
  assertValidOptimizerHandoffReference(reviewBasisSource.handoff_reference, 'Persisted optimizer handoff review payload review_basis')
  assertOptimizerHandoffReferenceMatchesCanonical(reviewBasisSource.handoff_reference, input.handoffReference, 'Persisted optimizer handoff review payload review_basis')
  return {
    basisVersion: reviewBasisSource.basis_version,
    basisKind: 'persisted_optimizer_handoff_review',
    reviewScope: reviewBasisSource.review_scope,
    canonicalSource: reviewBasisSource.canonical_source,
    basisProvenanceLabel: reviewBasisSource.basis_provenance_label,
    portfolioTruth: reviewBasisSource.portfolio_truth,
    candidateTruth: reviewBasisSource.candidate_truth,
    handoffReference: reviewBasisSource.handoff_reference,
    openedAt: input.openedAt,
    benchmarkSymbol: reviewBasisSource.benchmark_symbol ?? null,
    baseCurrency: reviewBasisSource.base_currency ?? null,
    replayWindow: {
      startDate: reviewBasisSource.replay_window.start_date ?? null,
      endDate: reviewBasisSource.replay_window.end_date ?? null,
    },
    baselineWeights: reviewBasisSource.baseline_weights,
    candidateWeights: reviewBasisSource.candidate_weights,
  }
}

type LegacyOptimizerIdentityFields = {
  handoffId?: string
  artifactId?: string | null
}

type LegacyOptimizerIdentityFieldPresence = LegacyOptimizerIdentityFields & {
  hasHandoffId: boolean
  hasArtifactId: boolean
}

function inspectLegacyOptimizerIdentityFields(value: unknown): LegacyOptimizerIdentityFieldPresence {
  if (!value || typeof value !== 'object') {
    return {
      hasHandoffId: false,
      hasArtifactId: false,
    }
  }

  const candidate = value as { handoffId?: unknown; artifactId?: unknown }
  return {
    hasHandoffId: 'handoffId' in candidate,
    handoffId: typeof candidate.handoffId === 'string' ? candidate.handoffId : undefined,
    hasArtifactId: 'artifactId' in candidate,
    artifactId: candidate.artifactId === null || typeof candidate.artifactId === 'string' ? candidate.artifactId : undefined,
  }
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

function assertValidMonitorDefinitionAlertReviewWorkspaceState(
  value: unknown,
  label: string,
): asserts value is MonitorDefinitionAlertReviewWorkspaceState {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is invalid`)
  }

  const candidate = value as Partial<MonitorDefinitionAlertReviewWorkspaceState>
  if (candidate.source !== 'definition_scoped_alert_review_timeline') {
    throw new Error(`${label} source is invalid`)
  }
  if (!isNonEmptyString(candidate.monitorDefinitionId)) {
    throw new Error(`${label} monitorDefinitionId is invalid`)
  }
  if (!isNonEmptyString(candidate.openedAt)) {
    throw new Error(`${label} openedAt is invalid`)
  }
  if (!candidate.selectedEvent || typeof candidate.selectedEvent !== 'object') {
    throw new Error(`${label} selectedEvent is invalid`)
  }
  if (candidate.selectedEvent.eventKind === 'latest_observation_event') {
    if (!isNonEmptyString(candidate.selectedEvent.observationId)) {
      throw new Error(`${label} selectedEvent observationId is invalid`)
    }
  } else if (candidate.selectedEvent.eventKind === 'evaluation_history_event') {
    if (!isNonEmptyString(candidate.selectedEvent.historyEntryId)) {
      throw new Error(`${label} selectedEvent historyEntryId is invalid`)
    }
  } else {
    throw new Error(`${label} selectedEvent eventKind is invalid`)
  }
  if (!candidate.cachedTimeline || typeof candidate.cachedTimeline !== 'object') {
    throw new Error(`${label} cachedTimeline is invalid`)
  }
}

function assertValidSeededRankingOpenHandoff(
  value: unknown,
  label: string,
): asserts value is IntentBoundSeededEtfReplacementRankingDraftArtifact['openHandoff'] {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is missing or invalid open handoff`)
  }

  const candidate = value as Partial<IntentBoundSeededEtfReplacementRankingDraftArtifact['openHandoff']>
  if (candidate.handoff_kind !== 'ranking_artifact_open_handoff_v1') {
    throw new Error(`${label} has unsupported open handoff kind`)
  }
  if (candidate.artifact_kind !== 'etf_ranking') {
    throw new Error(`${label} has unsupported open handoff artifact kind`)
  }
  if (!isNonEmptyString(candidate.artifact_id)) {
    throw new Error(`${label} is missing canonical artifact identity in open handoff`)
  }
  if (candidate.schema_version !== 'etf_ranking_artifact_v1') {
    throw new Error(`${label} has unsupported open handoff schema version`)
  }
}

function toCanonicalIntentBoundSeededEtfReplacementRankingDraft(
  draft: LegacyIntentBoundSeededEtfReplacementRankingDraftArtifact,
): IntentBoundSeededEtfReplacementRankingDraftArtifact {
  const candidate = draft as Partial<LegacyIntentBoundSeededEtfReplacementRankingDraftArtifact>
  const {
    artifactId: _artifactId,
    artifactKind: _artifactKind,
    schemaVersion: _schemaVersion,
    reviewPayloadKind: _reviewPayloadKind,
    consumerHandoff: _consumerHandoff,
    ...canonicalDraft
  } = draft

  assertValidSeededRankingOpenHandoff(candidate.openHandoff, 'Persisted seeded ranking review cache')

  if (candidate.artifactId != null && !isNonEmptyString(candidate.artifactId)) {
    throw new Error('Persisted seeded ranking review cache is missing canonical artifact identity')
  }
  if (candidate.artifactId != null && candidate.artifactId !== candidate.openHandoff.artifact_id) {
    throw new Error('Persisted seeded ranking review cache conflicts with open handoff artifact identity')
  }
  if (candidate.artifactKind != null && candidate.artifactKind !== candidate.openHandoff.artifact_kind) {
    throw new Error('Persisted seeded ranking review cache conflicts with open handoff artifact kind')
  }
  if (candidate.schemaVersion != null && candidate.schemaVersion !== candidate.openHandoff.schema_version) {
    throw new Error('Persisted seeded ranking review cache conflicts with open handoff schema version')
  }
  if (candidate.reviewPayloadKind != null && candidate.reviewPayloadKind !== 'etf_ranking_review_payload_v1') {
    throw new Error('Persisted seeded ranking review cache has unsupported review payload kind')
  }
  if ('consumerHandoff' in candidate) {
    throw new Error('Persisted seeded ranking review cache has unsupported consumer handoff state')
  }

  return {
    ...canonicalDraft,
    openHandoff: candidate.openHandoff,
  }
}

function canonicalizeIntentBoundSeededEtfReplacementRankingDraftForWrite(
  draft: IntentBoundSeededEtfReplacementRankingDraftArtifact,
): IntentBoundSeededEtfReplacementRankingDraftArtifact {
  return toCanonicalIntentBoundSeededEtfReplacementRankingDraft(draft)
}

function assertValidOptimizerHandoffReference(
  value: unknown,
  label: string,
): asserts value is PersistedOptimizerHandoffWorkspaceReview['handoffReference'] {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is missing or invalid handoff reference`)
  }

  const candidate = value as Partial<PersistedOptimizerHandoffWorkspaceReview['handoffReference']>
  if (
    candidate.reference_kind !== 'optimizer_handoff_reference_v1'
    || !isNonEmptyString(candidate.handoff_id)
    || !isNonEmptyString(candidate.artifact_id)
    || !isNonEmptyString(candidate.manifest_path)
    || !isNonEmptyString(candidate.artifact_path)
  ) {
    throw new Error(`${label} is missing or invalid handoff reference`)
  }
}

function assertOptimizerHandoffReferenceMatchesCanonical(
  value: unknown,
  canonicalReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference'],
  label: string,
) {
  assertValidOptimizerHandoffReference(value, label)

  if (
    value.reference_kind !== canonicalReference.reference_kind
    || value.handoff_id !== canonicalReference.handoff_id
    || value.artifact_id !== canonicalReference.artifact_id
    || value.manifest_path !== canonicalReference.manifest_path
    || value.artifact_path !== canonicalReference.artifact_path
  ) {
    throw new Error(`${label} conflicts with canonical persisted review`)
  }
}

function canonicalizeOptimizerReviewBasisForComparison(basis: PersistedOptimizerHandoffReviewBasis) {
  return {
    basisVersion: basis.basisVersion,
    basisKind: basis.basisKind,
    reviewScope: basis.reviewScope,
    canonicalSource: basis.canonicalSource,
    basisProvenanceLabel: basis.basisProvenanceLabel,
    portfolioTruth: basis.portfolioTruth,
    candidateTruth: basis.candidateTruth,
    handoffReference: basis.handoffReference,
    openedAt: basis.openedAt,
    benchmarkSymbol: basis.benchmarkSymbol,
    baseCurrency: basis.baseCurrency,
    replayWindow: basis.replayWindow,
    baselineWeights: basis.baselineWeights,
    candidateWeights: basis.candidateWeights,
  }
}

function assertCachedOptimizerReviewBasisMatchesCanonical(
  value: unknown,
  canonicalReviewBasis: PersistedOptimizerHandoffReviewBasis,
  label: string,
) {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is malformed`)
  }

  const candidate = value as Partial<PersistedOptimizerHandoffReviewBasis>
  if (candidate.basisKind !== 'persisted_optimizer_handoff_review') {
    throw new Error(`${label} has unsupported basis kind`)
  }
  if (candidate.basisVersion !== 1) {
    throw new Error(`${label} has unsupported basis version`)
  }

  assertOptimizerHandoffReferenceMatchesCanonical(candidate.handoffReference, canonicalReviewBasis.handoffReference, label)
  assertLegacyOptimizerIdentityMatchesReference(candidate, canonicalReviewBasis.handoffReference, label)

  if (
    JSON.stringify(canonicalizeOptimizerReviewBasisForComparison(candidate as PersistedOptimizerHandoffReviewBasis))
    !== JSON.stringify(canonicalizeOptimizerReviewBasisForComparison(canonicalReviewBasis))
  ) {
    throw new Error(`${label} conflicts with canonical persisted review`)
  }
}

function getLegacyOptimizerIdentityFields(value: unknown): LegacyOptimizerIdentityFields {
  const { handoffId, artifactId } = inspectLegacyOptimizerIdentityFields(value)
  return { handoffId, artifactId }
}

function hasLegacyOptimizerIdentityFields(value: unknown) {
  const legacyIdentity = inspectLegacyOptimizerIdentityFields(value)
  return legacyIdentity.hasHandoffId || legacyIdentity.hasArtifactId
}

function assertLegacyOptimizerIdentityMatchesReference(value: unknown, handoffReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference'], label: string) {
  const legacyIdentity = inspectLegacyOptimizerIdentityFields(value)

  if (legacyIdentity.hasHandoffId !== legacyIdentity.hasArtifactId) {
    throw new Error(`${label} has partial legacy identity fields`)
  }
  if (!legacyIdentity.hasHandoffId) {
    return
  }
  if (legacyIdentity.handoffId == null) {
    throw new Error(`${label} has invalid legacy handoff identity`)
  }
  if (!isNonEmptyString(legacyIdentity.artifactId)) {
    throw new Error(`${label} has invalid legacy artifact identity`)
  }

  if (legacyIdentity.handoffId !== handoffReference.handoff_id) {
    throw new Error(`${label} is inconsistent with handoff reference identity`)
  }
  if (legacyIdentity.artifactId !== handoffReference.artifact_id) {
    throw new Error(`${label} is inconsistent with artifact reference identity`)
  }
}

function toCanonicalPersistedOptimizerHandoffReview(review: PersistedOptimizerHandoffWorkspaceReview): PersistedOptimizerHandoffWorkspaceReview {
  assertValidOptimizerHandoffReference(review.handoffReference, 'Persisted optimizer handoff review cache')
  const replayHandoffId = review.replay.handoff_id
  const replayArtifactId = review.replay.artifact_id
  const validationHandoffId = review.validation.handoff_id ?? null
  const validationArtifactId = review.validation.artifact_id ?? null
  const referenceHandoffId = review.handoffReference.handoff_id
  const referenceArtifactId = review.handoffReference.artifact_id

  assertLegacyOptimizerIdentityMatchesReference(review, review.handoffReference, 'Persisted optimizer handoff review cache')

  if (replayHandoffId !== referenceHandoffId || replayArtifactId !== referenceArtifactId) {
    throw new Error('Persisted optimizer handoff review cache is inconsistent with replay identity')
  }
  if (validationHandoffId != null && validationHandoffId !== referenceHandoffId) {
    throw new Error('Persisted optimizer handoff review cache is inconsistent with validation handoff identity')
  }
  if (validationArtifactId != null && validationArtifactId !== referenceArtifactId) {
    throw new Error('Persisted optimizer handoff review cache is inconsistent with validation artifact identity')
  }
  if (review.replay.optimizer_context == null) {
    throw new Error('Persisted optimizer handoff review cache is missing replay optimizer context')
  }
  if (review.replay.optimizer_context.objective == null) {
    throw new Error('Persisted optimizer handoff review cache is missing replay optimizer objective')
  }

  return {
    workspaceId: review.workspaceId,
    handoffReference: review.handoffReference,
    openedAt: review.openedAt,
    validation: review.validation,
    reviewBasisSource: review.reviewBasisSource ?? review.replay.review_basis,
    replay: review.replay,
  }
}

function canonicalizeConstructionReviewBasisForComparison(basis: PersistedConstructionArtifactReviewBasis) {
  return {
    basisVersion: basis.basisVersion,
    basisKind: basis.basisKind,
    reviewScope: basis.reviewScope,
    canonicalSource: basis.canonicalSource,
    basisProvenanceLabel: basis.basisProvenanceLabel,
    portfolioTruth: basis.portfolioTruth,
    candidateTruth: basis.candidateTruth,
    constructionArtifactId: basis.constructionArtifactId,
    previewHandoff: basis.previewHandoff,
    openedAt: basis.openedAt,
    benchmarkSymbol: basis.benchmarkSymbol,
    baseCurrency: basis.baseCurrency,
    replayWindow: basis.replayWindow,
    baselineWeights: basis.baselineWeights,
    candidateWeights: basis.candidateWeights,
  }
}

function assertCachedConstructionReviewBasisMatchesCanonical(
  value: unknown,
  canonicalReviewBasis: PersistedConstructionArtifactReviewBasis,
  label: string,
) {
  if (!value || typeof value !== 'object') {
    throw new Error(`${label} is malformed`)
  }

  const candidate = value as Partial<PersistedConstructionArtifactReviewBasis>
  if (candidate.basisKind !== 'persisted_construction_artifact_review') {
    throw new Error(`${label} has unsupported basis kind`)
  }
  if (candidate.basisVersion !== 1) {
    throw new Error(`${label} has unsupported basis version`)
  }
  if (candidate.constructionArtifactId !== canonicalReviewBasis.constructionArtifactId) {
    throw new Error(`${label} conflicts with canonical persisted review`)
  }
  if (!candidate.previewHandoff || typeof candidate.previewHandoff !== 'object') {
    throw new Error(`${label} is missing canonical preview handoff`)
  }
  if (candidate.previewHandoff.handoff_kind !== 'construction_artifact_preview_handoff_v1') {
    throw new Error(`${label} has unsupported preview handoff kind`)
  }
  if (candidate.previewHandoff.construction_artifact_id !== canonicalReviewBasis.constructionArtifactId) {
    throw new Error(`${label} preview handoff conflicts with canonical persisted review identity`)
  }
  if (
    JSON.stringify(canonicalizeConstructionReviewBasisForComparison(candidate as PersistedConstructionArtifactReviewBasis))
    !== JSON.stringify(canonicalizeConstructionReviewBasisForComparison(canonicalReviewBasis))
  ) {
    throw new Error(`${label} conflicts with canonical persisted review`)
  }
}

function canonicalizePersistedOptimizerHandoffReviewForWrite(review: PersistedOptimizerHandoffWorkspaceReview): PersistedOptimizerHandoffWorkspaceReview {
  return toCanonicalPersistedOptimizerHandoffReview(review)
}

function buildPersistedOptimizerHandoffWorkspaceRecords(input: {
  workspaceId: string
  rootNodeId: string
  handoffReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference']
  openedAt: string
  validation: OptimizerHandoffValidationResponse
  replay: OptimizerHandoffReplayResponse
}): {
  workspace: PortfolioWorkspace
  rootNode: PortfolioNode
  workspaceState: WorkspaceState
  review: PersistedOptimizerHandoffWorkspaceReview
} {
  const review = canonicalizePersistedOptimizerHandoffReviewForWrite({
    workspaceId: input.workspaceId,
    handoffReference: input.handoffReference,
    openedAt: input.openedAt,
    validation: input.validation,
    replay: input.replay,
  })
  const reviewBasis = buildOptimizerHandoffReviewBasis({
    handoffReference: review.handoffReference,
    openedAt: review.openedAt,
    replay: review.replay,
  })

  return {
    workspace: {
      id: input.workspaceId,
      name: `Optimizer Handoff ${review.handoffReference.handoff_id}`,
      createdAt: review.openedAt,
      updatedAt: review.openedAt,
      rootNodeId: input.rootNodeId,
      activeNodeId: input.rootNodeId,
      source: {
        kind: 'persisted_optimizer_handoff',
        handoffReference: review.handoffReference,
        openedAt: review.openedAt,
        reviewBasis,
      },
    },
    rootNode: {
      id: input.rootNodeId,
      workspaceId: input.workspaceId,
      parentId: null,
      kind: 'artifact_review_basis',
      name: 'Artifact Review Basis',
      createdAt: review.openedAt,
      changeSummary: {
        label: 'Artifact Review Basis',
        changedPositionsCount: review.replay.candidate_weights.length,
        changedSectorsCount: 0,
        grossExposureDelta: null,
        netCapitalDelta: null,
      },
      portfolioSnapshot: null,
      artifactReviewBasis: reviewBasis,
    },
    workspaceState: {
      workspaceId: input.workspaceId,
      activeNodeId: input.rootNodeId,
      activeDraftId: null,
      selectedExposureSnapshotId: input.rootNodeId,
      lastOpenedAt: review.openedAt,
    },
    review,
  }
}

function buildLegacyArtifactReviewSnapshot(input: {
  constructionArtifactId: string
  openedAt: string
  replay: ConstructionArtifactReplayResponse
}): PortfolioSnapshot {
  return {
    snapshotVersion: 1,
    baseCurrency: input.replay.replay.candidate_result.assumptions.investor_base_currency ?? input.replay.replay.reference_result?.assumptions.investor_base_currency ?? 'USD',
    importedMeta: {
      importer: null,
      statementPeriod: `${input.replay.replay.candidate_result.start_date} - ${input.replay.replay.candidate_result.end_date}`,
      importedAt: input.openedAt,
      sourceFileNames: [input.constructionArtifactId],
    },
    positions: input.replay.baseline_weights.map((row) => ({
      symbol: row.symbol,
      marketValue: row.target_weight,
      quantity: null,
      currency: null,
      sector: null,
      name: null,
      sourceType: 'other' as const,
    })),
    cashBalances: [],
    metadata: {
      benchmarkSymbol: input.replay.replay.candidate_result.benchmark_symbol,
      notes: `Persisted construction artifact review: ${input.constructionArtifactId}`,
      tags: ['persisted_construction_artifact_review'],
    },
  }
}

function normalizePersistedConstructionArtifactWorkspace(input: {
  workspace: PortfolioWorkspace
  node: PortfolioNode
  review: PersistedConstructionArtifactWorkspaceReview
}) {
  const reviewBasis = buildDesktopArtifactReviewBasis({
    constructionArtifactId: input.review.constructionArtifactId,
    openedAt: input.review.openedAt,
    replay: input.review.replay,
  })

  const workspaceSource = input.workspace.source
  if (!('kind' in workspaceSource) || workspaceSource.kind !== 'persisted_construction_artifact') {
    throw new Error('Persisted construction artifact workspace normalization requires a persisted construction artifact source')
  }
  if (workspaceSource.constructionArtifactId !== input.review.constructionArtifactId) {
    throw new Error('Persisted construction artifact workspace source conflicts with canonical persisted review identity')
  }

  if (workspaceSource.reviewBasis != null) {
    assertCachedConstructionReviewBasisMatchesCanonical(workspaceSource.reviewBasis, reviewBasis, 'Persisted construction artifact workspace review basis')
  }

  const normalizedWorkspace: PortfolioWorkspace = workspaceSource.reviewBasis
    ? input.workspace
    : {
        ...input.workspace,
        source: {
          ...workspaceSource,
          reviewBasis,
        },
      }

  if (input.node.artifactReviewBasis != null) {
    assertCachedConstructionReviewBasisMatchesCanonical(input.node.artifactReviewBasis, reviewBasis, 'Persisted construction artifact node review basis')
  }

  const normalizedNode: PortfolioNode = input.node.kind === 'artifact_review_basis' && input.node.artifactReviewBasis
    ? { ...input.node, portfolioSnapshot: null }
    : {
        ...input.node,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        changeSummary: {
          ...input.node.changeSummary,
          label: 'Artifact Review Basis',
        },
        portfolioSnapshot: null,
        artifactReviewBasis: reviewBasis,
      }

  return {
    workspace: normalizedWorkspace,
    node: normalizedNode,
    review: {
      ...input.review,
      replay: normalizeConstructionArtifactReplayResponse(input.review.replay),
    },
  }
}

export async function normalizeLegacyPersistedConstructionArtifactWorkspaceCache(input: {
  workspace: PortfolioWorkspace
  node: PortfolioNode
  review: PersistedConstructionArtifactWorkspaceReview
}) {
  const normalized = normalizePersistedConstructionArtifactWorkspace(input)
  const workspaceSource = input.workspace.source
  const workspaceAlreadyNormalized = 'kind' in workspaceSource && workspaceSource.kind === 'persisted_construction_artifact' && workspaceSource.reviewBasis != null
  const nodeAlreadyNormalized = input.node.kind === 'artifact_review_basis' && input.node.artifactReviewBasis != null && input.node.portfolioSnapshot == null

  if (workspaceAlreadyNormalized && nodeAlreadyNormalized) {
    return normalized
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(normalized.workspace)
    const nodeRequest = transaction.objectStore(portfolioNodeStoreName).put(normalized.node)
    nodeRequest.onsuccess = () => resolve(normalized)
    nodeRequest.onerror = () => reject(nodeRequest.error ?? new Error('Failed to normalize persisted construction artifact workspace cache'))
  })

  return normalized
}

function normalizePersistedOptimizerHandoffWorkspace(input: {
  workspace: PortfolioWorkspace
  node: PortfolioNode
  review: PersistedOptimizerHandoffWorkspaceReview
}) {
  const canonicalReview = toCanonicalPersistedOptimizerHandoffReview(input.review)
  const reviewBasis = buildOptimizerHandoffReviewBasis({
    handoffReference: canonicalReview.handoffReference,
    openedAt: canonicalReview.openedAt,
    replay: canonicalReview.replay,
  })

  const workspaceSource = input.workspace.source
  if (!('kind' in workspaceSource) || workspaceSource.kind !== 'persisted_optimizer_handoff') {
    throw new Error('Persisted optimizer handoff workspace normalization requires a persisted optimizer handoff source')
  }

  assertOptimizerHandoffReferenceMatchesCanonical(workspaceSource.handoffReference, canonicalReview.handoffReference, 'Persisted optimizer handoff workspace source')
  assertLegacyOptimizerIdentityMatchesReference(workspaceSource, canonicalReview.handoffReference, 'Persisted optimizer handoff workspace source')

  if (workspaceSource.reviewBasis != null) {
    assertCachedOptimizerReviewBasisMatchesCanonical(workspaceSource.reviewBasis, reviewBasis, 'Persisted optimizer handoff workspace review basis')
  }

  const workspaceNeedsRepair = workspaceSource.reviewBasis == null
    || hasLegacyOptimizerIdentityFields(workspaceSource)
    || hasLegacyOptimizerIdentityFields(workspaceSource.reviewBasis)
  const normalizedWorkspace: PortfolioWorkspace = !workspaceNeedsRepair
    ? input.workspace
    : {
        ...input.workspace,
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: canonicalReview.handoffReference,
          openedAt: workspaceSource.openedAt,
          reviewBasis,
        },
      }

  if (input.node.artifactReviewBasis != null) {
    assertCachedOptimizerReviewBasisMatchesCanonical(input.node.artifactReviewBasis, reviewBasis, 'Persisted optimizer handoff node review basis')
  }

  const nodeNeedsRepair = input.node.artifactReviewBasis != null && hasLegacyOptimizerIdentityFields(input.node.artifactReviewBasis)
  const normalizedNode: PortfolioNode = input.node.kind === 'artifact_review_basis' && input.node.artifactReviewBasis && !nodeNeedsRepair
    ? { ...input.node, portfolioSnapshot: null }
    : {
        ...input.node,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        changeSummary: {
          ...input.node.changeSummary,
          label: 'Artifact Review Basis',
        },
        portfolioSnapshot: null,
        artifactReviewBasis: reviewBasis,
      }

  return {
    workspace: normalizedWorkspace,
    node: normalizedNode,
    review: canonicalReview,
  }
}

export async function normalizeLegacyPersistedOptimizerHandoffWorkspaceCache(input: {
  workspace: PortfolioWorkspace
  node: PortfolioNode
  review: PersistedOptimizerHandoffWorkspaceReview
}) {
  const normalized = normalizePersistedOptimizerHandoffWorkspace(input)
  const workspaceSource = input.workspace.source
  const workspaceAlreadyNormalized = 'kind' in workspaceSource
    && workspaceSource.kind === 'persisted_optimizer_handoff'
    && workspaceSource.reviewBasis != null
    && !hasLegacyOptimizerIdentityFields(workspaceSource)
    && !hasLegacyOptimizerIdentityFields(workspaceSource.reviewBasis)
  const nodeAlreadyNormalized = input.node.kind === 'artifact_review_basis'
    && input.node.artifactReviewBasis != null
    && input.node.portfolioSnapshot == null
    && (input.node.artifactReviewBasis.basisKind !== 'persisted_optimizer_handoff_review' || !hasLegacyOptimizerIdentityFields(input.node.artifactReviewBasis))

  if (workspaceAlreadyNormalized && nodeAlreadyNormalized) {
    return normalized
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(normalized.workspace)
    const nodeRequest = transaction.objectStore(portfolioNodeStoreName).put(normalized.node)
    nodeRequest.onsuccess = () => resolve(normalized)
    nodeRequest.onerror = () => reject(nodeRequest.error ?? new Error('Failed to normalize persisted optimizer handoff workspace cache'))
  })

  return normalized
}

function createChangeSummary(baseSnapshot: PortfolioSnapshot, nextSnapshot: PortfolioSnapshot, label: string) {
  const baseMap = new Map(baseSnapshot.positions.map((position) => [position.symbol, position.marketValue]))
  const nextMap = new Map(nextSnapshot.positions.map((position) => [position.symbol, position.marketValue]))
  const symbols = new Set([...baseMap.keys(), ...nextMap.keys()])
  const changedPositionsCount = Array.from(symbols).filter((symbol) => (baseMap.get(symbol) ?? 0) !== (nextMap.get(symbol) ?? 0)).length

  return {
    label,
    changedPositionsCount,
    changedSectorsCount: Math.abs(getPortfolioSnapshotSectorCount(nextSnapshot) - getPortfolioSnapshotSectorCount(baseSnapshot)),
    grossExposureDelta: getPortfolioSnapshotGrossExposure(nextSnapshot) - getPortfolioSnapshotGrossExposure(baseSnapshot),
    netCapitalDelta: getPortfolioSnapshotNetCapital(nextSnapshot) - getPortfolioSnapshotNetCapital(baseSnapshot),
  }
}

function assertSavedProposalArtifactLineageIntegrity(proposal: VersionedProposalArtifact): VersionedProposalArtifact {
  const replayBasis = proposal.replayBasis
  const reviewSnapshot = proposal.reviewSnapshot
  const replayProvenance = replayBasis.replayProvenance
  const snapshotProvenance = reviewSnapshot.replay_provenance

  if (replayBasis.candidateConstructionRule !== reviewSnapshot.derivation.candidate_construction_rule) {
    throw new Error('Saved proposal candidateConstructionRule does not match reviewSnapshot derivation')
  }
  if (replayProvenance.construction_rule_id !== snapshotProvenance.construction_rule_id) {
    throw new Error('Saved proposal replayProvenance construction_rule_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.candidate_input_source !== snapshotProvenance.candidate_input_source) {
    throw new Error('Saved proposal replayProvenance candidate_input_source does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.upstream_ids.draft_id !== snapshotProvenance.upstream_ids.draft_id) {
    throw new Error('Saved proposal replayProvenance upstream draft_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.upstream_ids.workspace_id !== snapshotProvenance.upstream_ids.workspace_id) {
    throw new Error('Saved proposal replayProvenance upstream workspace_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.upstream_ids.base_node_id !== snapshotProvenance.upstream_ids.base_node_id) {
    throw new Error('Saved proposal replayProvenance upstream base_node_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.seed_ranking_id !== snapshotProvenance.seed_ranking_id) {
    throw new Error('Saved proposal replayProvenance seed_ranking_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.seed_methodology_id !== snapshotProvenance.seed_methodology_id) {
    throw new Error('Saved proposal replayProvenance seed_methodology_id does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.constraint_validation.supplied !== snapshotProvenance.constraint_validation.supplied) {
    throw new Error('Saved proposal replayProvenance constraint_validation.supplied does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.constraint_validation.validation_status !== snapshotProvenance.constraint_validation.validation_status) {
    throw new Error('Saved proposal replayProvenance constraint_validation.validation_status does not match reviewSnapshot replay_provenance')
  }
  if (replayProvenance.constraint_validation.constraint_set_id !== snapshotProvenance.constraint_validation.constraint_set_id) {
    throw new Error('Saved proposal replayProvenance constraint_validation.constraint_set_id does not match reviewSnapshot replay_provenance')
  }

  return proposal
}

export function assertSavedProposalArtifactIntegrity(proposal: VersionedProposalArtifact): VersionedProposalArtifact {
  const canonicalProposal = assertSavedProposalArtifactProposalSourceIntegrity(assertSavedProposalArtifactLineageIntegrity(proposal))
  assertSavedProposalProposalCaptureIntegrity(canonicalProposal)
  if (canonicalProposal.reviewSnapshotPMSummary != null) {
    assertValidReviewSnapshotPMSummaryEnvelope(
      canonicalProposal.reviewSnapshotPMSummary,
      'Saved proposal reviewSnapshotPMSummary',
      ['saved_proposal'],
    )
  }
  return canonicalProposal
}


export function assertSavedProposalArtifactRestoreIntegrity(
  proposal: VersionedProposalArtifact,
  reviewSnapshotArtifact: ReviewSnapshotArtifact | null,
): VersionedProposalArtifact {
  const canonicalProposal = assertSavedProposalArtifactProposalSourceIntegrity(assertSavedProposalArtifactLineageIntegrity(proposal))
  assertSavedProposalProposalCaptureIntegrity(canonicalProposal, 'Saved proposal proposalCapture', { allowMissingReviewSnapshotProposalSource: true })
  assertSavedProposalArtifactReviewSnapshotIdentity(canonicalProposal, reviewSnapshotArtifact)
  if (canonicalProposal.reviewSnapshotPMSummary == null) {
    throw new Error('Saved proposal cached reviewSnapshotPMSummary is missing while persisted review snapshot artifact pm_summary exists')
  }
  assertCachedSavedProposalPMSummaryMatchesPersisted(canonicalProposal, reviewSnapshotArtifact)
  return canonicalizeRestoredSavedProposalArtifact(canonicalProposal)
}


export function buildSavedProposalArtifact(input: {
  id: string
  createdAt: string
  workspaceId: string
  sourceDraftId: string
  sourceBaseNodeId: string
  proposalFamilyId: string
  versionNumber: number
  sourceIntent: ReplacementIntentDraftArtifact
  proposalCapture: VersionedProposalArtifact['proposalCapture']
  reviewSnapshotArtifactId: string
  reviewSnapshotPMSummary: ReviewSnapshotPMSummaryEnvelope
  hypotheticalReplay: VersionedProposalArtifact['reviewSnapshot']
}): VersionedProposalArtifact {
  const activeReplay = 'replay' in input.hypotheticalReplay ? input.hypotheticalReplay.replay : input.hypotheticalReplay.overlay_replay
  const proposalSource = input.proposalCapture.proposal.proposal_source
  return assertSavedProposalArtifactIntegrity({
    id: input.id,
    kind: 'single_replacement_hypothetical_replay_proposal',
    schemaVersion: 1,
    createdAt: input.createdAt,
    workspaceId: input.workspaceId,
    sourceDraftId: input.sourceDraftId,
    sourceBaseNodeId: input.sourceBaseNodeId,
    proposalFamilyId: input.proposalFamilyId,
    versionNumber: input.versionNumber,
    savedFrom: 'desktop_hypothetical_replay_review',
    reviewStatus: 'recorded',
    sourceIntent: input.sourceIntent,
    proposalCapture: input.proposalCapture,
    proposalSource: {
      proposalSourceVersion: proposalSource.proposal_source_version,
      proposalSourceKind: proposalSource.proposal_source_kind,
      proposalTruth: proposalSource.proposal_truth,
      portfolioTruth: proposalSource.portfolio_truth,
      reviewScope: proposalSource.review_scope,
    },
    reviewSnapshotArtifactId: input.reviewSnapshotArtifactId,
    reviewSnapshotPMSummary: input.reviewSnapshotPMSummary,
    replayBasis: {
      benchmarkSymbol: input.proposalCapture.review_basis.benchmark_symbol,
      startDate: input.proposalCapture.review_basis.replay_window.start_date,
      endDate: input.proposalCapture.review_basis.replay_window.end_date,
      rebalanceFrequency: input.proposalCapture.review_basis.rebalance_frequency,
      commissionBps: input.proposalCapture.review_basis.commission_bps,
      slippageBps: input.proposalCapture.review_basis.slippage_bps,
      derivationBasis: input.proposalCapture.review_basis.derivation_basis,
      candidateConstructionRule: input.proposalCapture.review_basis.candidate_construction_rule,
      replayProvenance: input.proposalCapture.replay_provenance,
    },
    reviewSnapshot: input.hypotheticalReplay,
  })
}

export function isDraftDirty(baseSnapshot: PortfolioSnapshot, draftSnapshot: PortfolioSnapshot) {
  return hashPortfolioSnapshot(baseSnapshot) !== hashPortfolioSnapshot(draftSnapshot)
}

export async function createWorkspaceFromImport(input: {
  name?: string
  analysis: ImportedPortfolioSnapshotSource
  importedFileNames: string[]
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
}): Promise<{ workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: WorkingDraft; workspaceState: WorkspaceState }> {
  const portfolioSnapshot = buildPortfolioSnapshotFromAnalysis(input.analysis, input.importedFileNames)
  const importedAt = portfolioSnapshot.importedMeta.importedAt
  const workspaceId = createId('workspace')
  const rootNodeId = createId('node')
  const draftId = createId('draft')
  const workspace: PortfolioWorkspace = {
    id: workspaceId,
    name: input.name ?? portfolioSnapshot.importedMeta.statementPeriod ?? 'Portfolio Workspace',
    createdAt: importedAt,
    updatedAt: importedAt,
    rootNodeId,
    activeNodeId: rootNodeId,
    source: buildPersistedImportedSource({
      importedFileNames: input.importedFileNames,
      importedAt,
      importer: portfolioSnapshot.importedMeta.importer,
      baseCurrency: portfolioSnapshot.baseCurrency,
      historyContext: input.historyContext ?? null,
      importedHistorySnapshot: input.importedHistorySnapshot ?? null,
    }),
  }
  const rootNode: PortfolioNode = {
    id: rootNodeId,
    workspaceId,
    parentId: null,
    kind: 'imported_base',
    name: 'Base Import',
    createdAt: importedAt,
    changeSummary: {
      label: 'Base Import',
      changedPositionsCount: portfolioSnapshot.positions.length,
      changedSectorsCount: getPortfolioSnapshotSectorCount(portfolioSnapshot),
      grossExposureDelta: getPortfolioSnapshotGrossExposure(portfolioSnapshot),
      netCapitalDelta: getPortfolioSnapshotNetCapital(portfolioSnapshot),
    },
    portfolioSnapshot,
  }
  const draft: WorkingDraft = {
    id: draftId,
    workspaceId,
    baseNodeId: rootNodeId,
    updatedAt: importedAt,
    name: 'Working Draft',
    status: 'clean',
    portfolioSnapshot: clonePortfolioSnapshot(portfolioSnapshot),
  }
  const workspaceState: WorkspaceState = {
    workspaceId,
    activeNodeId: rootNodeId,
    activeDraftId: draftId,
    selectedExposureSnapshotId: 'draft',
    lastOpenedAt: importedAt,
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName, workingDraftStoreName, workspaceStateStoreName, appStateStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(workspace)
    transaction.objectStore(portfolioNodeStoreName).put(rootNode)
    transaction.objectStore(workingDraftStoreName).put(draft)
    transaction.objectStore(workspaceStateStoreName).put(workspaceState)
    const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId })
    pointerRequest.onsuccess = () => resolve({ workspace, rootNode, draft, workspaceState })
    pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to save workspace pointer'))
  })

  return { workspace, rootNode, draft, workspaceState }
}

export async function savePersistedConstructionArtifactWorkspaceReview(review: PersistedConstructionArtifactWorkspaceReview) {
  const normalizedReview = {
    ...review,
    replay: normalizeConstructionArtifactReplayResponse(review.replay),
  }
  await withStore<void>(persistedConstructionArtifactReviewStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(normalizedReview)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save persisted construction artifact review'))
  })
}

export async function getPersistedConstructionArtifactWorkspaceReview(workspaceId: string) {
  return withStore<PersistedConstructionArtifactWorkspaceReview | null>(persistedConstructionArtifactReviewStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => {
      try {
        const review = (request.result as PersistedConstructionArtifactWorkspaceReview | undefined) ?? null
        if (!review) {
          resolve(null)
          return
        }
        const normalizedReplay = normalizeConstructionArtifactReplayResponse(review.replay)
        resolve({
          ...review,
          reviewBasisSource: review.reviewBasisSource ?? normalizedReplay.review_basis,
          replay: normalizedReplay,
        })
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load persisted construction artifact review'))
  })
}

export async function savePersistedOptimizerHandoffWorkspaceReview(review: PersistedOptimizerHandoffWorkspaceReview) {
  const canonicalReview = canonicalizePersistedOptimizerHandoffReviewForWrite(review)
  await withStore<void>(persistedOptimizerHandoffReviewStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(canonicalReview)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save persisted optimizer handoff review'))
  })
}

export async function getPersistedOptimizerHandoffWorkspaceReview(workspaceId: string) {
  return withStore<PersistedOptimizerHandoffWorkspaceReview | null>(persistedOptimizerHandoffReviewStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => {
      try {
        const review = (request.result as PersistedOptimizerHandoffWorkspaceReview | undefined) ?? null
        resolve(review ? toCanonicalPersistedOptimizerHandoffReview(review) : null)
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load persisted optimizer handoff review'))
  })
}

export async function createWorkspaceFromPersistedConstructionArtifact(input: {
  constructionArtifactId: string
  openedAt?: string
  replay: ConstructionArtifactReplayResponse
}): Promise<{ workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: null; workspaceState: WorkspaceState; review: PersistedConstructionArtifactWorkspaceReview }> {
  const openedAt = input.openedAt ?? new Date().toISOString()
  const replay = normalizeConstructionArtifactReplayResponse(input.replay)
  const workspaceId = createId('workspace')
  const rootNodeId = createId('node')
  const reviewBasis = buildDesktopArtifactReviewBasis({
    constructionArtifactId: input.constructionArtifactId,
    openedAt,
    replay,
  })
  const workspace: PortfolioWorkspace = {
    id: workspaceId,
    name: `Construction Artifact ${input.constructionArtifactId}`,
    createdAt: openedAt,
    updatedAt: openedAt,
    rootNodeId,
    activeNodeId: rootNodeId,
    source: {
      kind: 'persisted_construction_artifact',
      constructionArtifactId: input.constructionArtifactId,
      openedAt,
      reviewBasis,
    },
  }
  const rootNode: PortfolioNode = {
    id: rootNodeId,
    workspaceId,
    parentId: null,
    kind: 'artifact_review_basis',
    name: 'Artifact Review Basis',
    createdAt: openedAt,
    changeSummary: {
      label: 'Artifact Review Basis',
      changedPositionsCount: replay.candidate_weights.length,
      changedSectorsCount: 0,
      grossExposureDelta: null,
      netCapitalDelta: null,
    },
    portfolioSnapshot: null,
    artifactReviewBasis: reviewBasis,
  }
  const workspaceState: WorkspaceState = {
    workspaceId,
    activeNodeId: rootNodeId,
    activeDraftId: null,
    selectedExposureSnapshotId: rootNodeId,
    lastOpenedAt: openedAt,
  }
  const review: PersistedConstructionArtifactWorkspaceReview = {
    workspaceId,
    constructionArtifactId: input.constructionArtifactId,
    openedAt,
    reviewBasisSource: replay.review_basis,
    replay,
  }

  await withStores([workspaceStoreName, portfolioNodeStoreName, workspaceStateStoreName, appStateStoreName, persistedConstructionArtifactReviewStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(workspace)
    transaction.objectStore(portfolioNodeStoreName).put(rootNode)
    transaction.objectStore(workspaceStateStoreName).put(workspaceState)
    transaction.objectStore(persistedConstructionArtifactReviewStoreName).put(review)
    const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId })
    pointerRequest.onsuccess = () => resolve({ workspace, rootNode, draft: null, workspaceState, review })
    pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to save workspace pointer'))
  })

  return { workspace, rootNode, draft: null, workspaceState, review }
}

export async function createWorkspaceFromPersistedOptimizerHandoff(input: {
  handoffReference: PersistedOptimizerHandoffWorkspaceReview['handoffReference']
  openedAt?: string
  validation: OptimizerHandoffValidationResponse
  replay: OptimizerHandoffReplayResponse
}): Promise<{ workspace: PortfolioWorkspace; rootNode: PortfolioNode; draft: null; workspaceState: WorkspaceState; review: PersistedOptimizerHandoffWorkspaceReview }> {
  const openedAt = input.openedAt ?? new Date().toISOString()
  const workspaceId = createId('workspace')
  const rootNodeId = createId('node')
  const { workspace, rootNode, workspaceState, review } = buildPersistedOptimizerHandoffWorkspaceRecords({
    workspaceId,
    rootNodeId,
    handoffReference: input.handoffReference,
    openedAt,
    validation: input.validation,
    replay: input.replay,
  })

  await withStores([workspaceStoreName, portfolioNodeStoreName, workspaceStateStoreName, appStateStoreName, persistedOptimizerHandoffReviewStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).put(workspace)
    transaction.objectStore(portfolioNodeStoreName).put(rootNode)
    transaction.objectStore(workspaceStateStoreName).put(workspaceState)
    transaction.objectStore(persistedOptimizerHandoffReviewStoreName).put(review)
    const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId })
    pointerRequest.onsuccess = () => resolve({ workspace, rootNode, draft: null, workspaceState, review })
    pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to save workspace pointer'))
  })

  return { workspace, rootNode, draft: null, workspaceState, review }
}

export async function getWorkspace(workspaceId: string) {
  return withStore<PortfolioWorkspace | null>(workspaceStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => resolve((request.result as PortfolioWorkspace | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace'))
  })
}

export async function getNode(nodeId: string) {
  return withStore<PortfolioNode | null>(portfolioNodeStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(nodeId)
    request.onsuccess = () => resolve((request.result as PortfolioNode | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load node'))
  })
}

export async function getWorkspaceNodes(workspaceId: string) {
  return withStore<PortfolioNode[]>(portfolioNodeStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => resolve((request.result as PortfolioNode[]) ?? [])
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace nodes'))
  })
}

export async function getDraft(workspaceId: string) {
  return withStore<WorkingDraft | null>(workingDraftStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => resolve(((request.result as WorkingDraft[] | undefined) ?? [])[0] ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load draft'))
  })
}

export async function saveDraft(draft: WorkingDraft) {
  await withStore<void>(workingDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(draft)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save draft'))
  })
}

export async function getCandidateImprovementDraft(draftId: string) {
  return withStore<CandidateImprovementDraftArtifact | null>(candidateImprovementDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as CandidateImprovementDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load candidate improvement draft'))
  })
}

export async function saveCandidateImprovementDraft(annotation: CandidateImprovementDraftArtifact) {
  await withStore<void>(candidateImprovementDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save candidate improvement draft'))
  })
}

export async function deleteCandidateImprovementDraft(draftId: string) {
  await withStore<void>(candidateImprovementDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete candidate improvement draft'))
  })
}

export async function getIntentBoundSeededEtfReplacementRankingDraft(draftId: string) {
  return withStore<IntentBoundSeededEtfReplacementRankingDraftArtifact | null>(intentBoundSeededEtfReplacementRankingDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => {
      try {
        const annotation = (request.result as LegacyIntentBoundSeededEtfReplacementRankingDraftArtifact | undefined) ?? null
        resolve(annotation ? toCanonicalIntentBoundSeededEtfReplacementRankingDraft(annotation) : null)
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load intent-bound seeded ETF replacement ranking draft'))
  })
}

export async function saveIntentBoundSeededEtfReplacementRankingDraft(annotation: IntentBoundSeededEtfReplacementRankingDraftArtifact) {
  const canonicalAnnotation = canonicalizeIntentBoundSeededEtfReplacementRankingDraftForWrite(annotation)
  await withStore<void>(intentBoundSeededEtfReplacementRankingDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(canonicalAnnotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save intent-bound seeded ETF replacement ranking draft'))
  })
}

export async function deleteIntentBoundSeededEtfReplacementRankingDraft(draftId: string) {
  await withStore<void>(intentBoundSeededEtfReplacementRankingDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete intent-bound seeded ETF replacement ranking draft'))
  })
}

export async function getReplacementIntentDraft(draftId: string) {
  return withStore<ReplacementIntentDraftArtifact | null>(replacementIntentDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as ReplacementIntentDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load replacement intent draft'))
  })
}

export async function getFormedCandidateArtifact(draftId: string) {
  return withStore<FormedCandidateArtifact | null>(formedCandidateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as FormedCandidateArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load formed candidate artifact'))
  })
}

export async function saveFormedCandidateArtifact(annotation: FormedCandidateArtifact) {
  await withStore<void>(formedCandidateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save formed candidate artifact'))
  })
}

export async function deleteFormedCandidateArtifact(draftId: string) {
  await withStore<void>(formedCandidateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete formed candidate artifact'))
  })
}

export async function getConstructedCandidateArtifact(draftId: string) {
  return withStore<ConstructedCandidateArtifact | null>(constructedCandidateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as ConstructedCandidateArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load constructed candidate artifact'))
  })
}

export async function saveConstructedCandidateArtifact(annotation: ConstructedCandidateArtifact) {
  await withStore<void>(constructedCandidateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save constructed candidate artifact'))
  })
}

export async function getConstructionConstraintValidationArtifact(draftId: string) {
  return withStore<ConstructionConstraintValidationArtifact | null>(constructionConstraintValidationStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as ConstructionConstraintValidationArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load construction constraint validation artifact'))
  })
}

export async function saveConstructionConstraintValidationArtifact(annotation: ConstructionConstraintValidationArtifact) {
  await withStore<void>(constructionConstraintValidationStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save construction constraint validation artifact'))
  })
}

export async function deleteConstructionConstraintValidationArtifact(draftId: string) {
  await withStore<void>(constructionConstraintValidationStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete construction constraint validation artifact'))
  })
}

export async function deleteConstructedCandidateArtifact(draftId: string) {
  await withStore<void>(constructedCandidateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete constructed candidate artifact'))
  })
}

export async function getSelectedConstructionRule(draftId: string) {
  return withStore<SelectedConstructionRuleArtifact | null>(selectedConstructionRuleStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as SelectedConstructionRuleArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load selected construction rule'))
  })
}

export async function saveSelectedConstructionRule(annotation: SelectedConstructionRuleArtifact) {
  await withStore<void>(selectedConstructionRuleStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save selected construction rule'))
  })
}

export async function deleteSelectedConstructionRule(draftId: string) {
  await withStore<void>(selectedConstructionRuleStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete selected construction rule'))
  })
}

export async function saveReplacementIntentDraft(annotation: ReplacementIntentDraftArtifact) {
  await withStore<void>(replacementIntentDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save replacement intent draft'))
  })
}

export async function deleteReplacementIntentDraft(draftId: string) {
  await withStore<void>(replacementIntentDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete replacement intent draft'))
  })
}

export async function getHypotheticalReplacementReplayDraft(draftId: string) {
  return withStore<HypotheticalReplacementReplayDraftArtifact | null>(hypotheticalReplacementReplayDraftStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(draftId)
    request.onsuccess = () => resolve((request.result as HypotheticalReplacementReplayDraftArtifact | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load hypothetical replay draft'))
  })
}

export async function saveHypotheticalReplacementReplayDraft(annotation: HypotheticalReplacementReplayDraftArtifact) {
  await withStore<void>(hypotheticalReplacementReplayDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(annotation)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save hypothetical replay draft'))
  })
}

export async function deleteHypotheticalReplacementReplayDraft(draftId: string) {
  await withStore<void>(hypotheticalReplacementReplayDraftStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(draftId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete hypothetical replay draft'))
  })
}

export async function getWorkspaceProposalArtifacts(workspaceId: string) {
  const loadedProposals = await withStore<VersionedProposalArtifact[]>(versionedProposalStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('workspaceId')
    const request = index.getAll(workspaceId)
    request.onsuccess = () => {
      try {
        resolve((((request.result as VersionedProposalArtifact[] | undefined) ?? []).map(hydrateLoadedSavedProposalArtifact)).sort((left, right) => right.versionNumber - left.versionNumber || right.createdAt.localeCompare(left.createdAt)))
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load proposal artifacts'))
  })

  return Promise.all(loadedProposals.map(async (proposal) => {
    const reviewSnapshotArtifact = await getReviewSnapshotArtifact(proposal.reviewSnapshotArtifactId)
    return assertSavedProposalArtifactRestoreIntegrity(proposal, reviewSnapshotArtifact)
  }))
}

export async function saveProposalArtifact(proposal: VersionedProposalArtifact) {
  assertSavedProposalArtifactIntegrity(proposal)
  if (!proposal.reviewSnapshotArtifactId) {
    throw new Error('Saved proposal is missing authoritative reviewSnapshotArtifactId')
  }
  if (!proposal.reviewSnapshotPMSummary) {
    throw new Error('Saved proposal is missing authoritative reviewSnapshotPMSummary mirror')
  }
  await withStore<void>(versionedProposalStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(proposal)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save proposal artifact'))
  })
}

export async function saveReviewSnapshotArtifact(input: { id: string; workspaceId: string; reviewSnapshotArtifactId: string; artifact: ReviewSnapshotArtifact }) {
  assertValidReviewSnapshotArtifact(input.artifact, 'Review snapshot artifact')
  if (input.artifact.identity.artifact_id !== input.reviewSnapshotArtifactId) {
    throw new Error('Review snapshot artifact id does not match persisted reviewSnapshotArtifactId')
  }
  if (input.artifact.lineage.workspace_id !== input.workspaceId) {
    throw new Error('Review snapshot artifact lineage workspace_id does not match workspaceId')
  }
  await withStore<void>(reviewSnapshotArtifactStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(input)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save review snapshot artifact'))
  })
}

export async function getReviewSnapshotArtifact(reviewSnapshotArtifactId: string) {
  return withStore<ReviewSnapshotArtifact | null>(reviewSnapshotArtifactStoreName, 'readonly', (store, resolve, reject) => {
    const index = store.index('reviewSnapshotArtifactId')
    const request = index.getAll(reviewSnapshotArtifactId)
    request.onsuccess = () => {
      try {
        const row = ((request.result as Array<{ artifact?: unknown }> | undefined) ?? [])[0] ?? null
        if (!row) {
          resolve(null)
          return
        }
        assertValidReviewSnapshotArtifact(row.artifact, 'Persisted review snapshot artifact row')
        resolve(row.artifact)
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load review snapshot artifact'))
  })
}

export async function buildReviewSnapshotOpenHandoffFromProposal(proposal: VersionedProposalArtifact): Promise<ReviewSnapshotOpenHandoff> {
  if (!proposal.reviewSnapshotArtifactId) {
    throw new Error('Saved proposal is missing authoritative reviewSnapshotArtifactId')
  }
  assertSavedProposalProposalCaptureIntegrity(proposal)
  const reviewSnapshotArtifact = await getReviewSnapshotArtifact(proposal.reviewSnapshotArtifactId)
  if (!reviewSnapshotArtifact) {
    throw new Error('Saved proposal review snapshot artifact is missing')
  }
  assertSavedProposalArtifactRestoreIntegrity(proposal, reviewSnapshotArtifact)
  if (JSON.stringify(proposal.proposalCapture.open_handoff) !== JSON.stringify(reviewSnapshotArtifact.proposal_capture.open_handoff)) {
    throw new Error('Saved proposal proposalCapture open_handoff does not match persisted review snapshot artifact proposal_capture open_handoff')
  }
  return proposal.proposalCapture.open_handoff
}

export function assertValidReviewSnapshotOpenResponseEnvelope(response: unknown): ReviewSnapshotOpenResponse {
  assertValidReviewSnapshotOpenResponse(response, 'Review snapshot open response')
  return response
}

export async function buildReviewSnapshotComparisonRefs(proposals: [VersionedProposalArtifact, VersionedProposalArtifact]): Promise<[ReviewSnapshotComparisonArtifactRef, ReviewSnapshotComparisonArtifactRef]> {
  const [baseline, candidate] = proposals
  if (baseline.reviewSnapshotArtifactId === candidate.reviewSnapshotArtifactId) {
    throw new Error('Review snapshot comparison requires two distinct persisted artifacts')
  }
  if (baseline.proposalFamilyId !== candidate.proposalFamilyId) {
    throw new Error('Review snapshot comparison requires matching proposalFamilyId')
  }
  if (baseline.workspaceId !== candidate.workspaceId) {
    throw new Error('Review snapshot comparison requires matching workspaceId')
  }
  if (baseline.sourceDraftId !== candidate.sourceDraftId) {
    throw new Error('Review snapshot comparison requires matching sourceDraftId')
  }
  if (baseline.sourceBaseNodeId !== candidate.sourceBaseNodeId) {
    throw new Error('Review snapshot comparison requires matching sourceBaseNodeId')
  }
  const baselineHandoff = await buildReviewSnapshotOpenHandoffFromProposal(baseline)
  const candidateHandoff = await buildReviewSnapshotOpenHandoffFromProposal(candidate)
  return [
    { role: 'baseline', artifact_id: baselineHandoff.artifact_id, artifact_kind: baselineHandoff.artifact_kind, schema_version: baselineHandoff.schema_version, consumer_kind: baselineHandoff.consumer_kind },
    { role: 'candidate', artifact_id: candidateHandoff.artifact_id, artifact_kind: candidateHandoff.artifact_kind, schema_version: candidateHandoff.schema_version, consumer_kind: candidateHandoff.consumer_kind },
  ]
}

export async function getActiveThesis(workspaceId: string) {
  return withStore<ActiveThesisArtifact | null>(activeThesisStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => {
      void (async () => {
        try {
          const thesis = (request.result as ActiveThesisArtifact | undefined) ?? null
          if (!thesis) {
            resolve(null)
            return
          }
          thesis.thesisProposal = hydrateLoadedSavedProposalArtifact(thesis.thesisProposal)
          const reviewSnapshotArtifact = await getReviewSnapshotArtifact(thesis.thesisProposal.reviewSnapshotArtifactId)
          thesis.thesisProposal = assertSavedProposalArtifactRestoreIntegrity(thesis.thesisProposal, reviewSnapshotArtifact)
          resolve(thesis)
        } catch (error) {
          reject(error)
        }
      })()
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load active thesis'))
  })
}

export async function saveActiveThesis(thesis: ActiveThesisArtifact) {
  thesis.thesisProposal = assertSavedProposalArtifactIntegrity(thesis.thesisProposal)
  await withStore<void>(activeThesisStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(thesis)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save active thesis'))
  })
}

export async function deleteActiveThesis(workspaceId: string) {
  await withStore<void>(activeThesisStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.delete(workspaceId)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to delete active thesis'))
  })
}

export async function createDraftFromNode(input: { workspaceId: string; baseNodeId: string; name?: string }) {
  const node = await getNode(input.baseNodeId)
  if (!node) throw new Error('Base node not found')
  if (!node.portfolioSnapshot) throw new Error('Base node does not contain a portfolio snapshot')
  const existingDraft = await getDraft(input.workspaceId)
  const draft: WorkingDraft = {
    id: existingDraft?.id ?? createId('draft'),
    workspaceId: input.workspaceId,
    baseNodeId: input.baseNodeId,
    updatedAt: new Date().toISOString(),
    name: input.name ?? 'Working Draft',
    status: 'clean',
    portfolioSnapshot: clonePortfolioSnapshot(node.portfolioSnapshot),
  }
  await saveDraft(draft)
  await deleteCandidateImprovementDraft(draft.id)
  await deleteIntentBoundSeededEtfReplacementRankingDraft(draft.id)
  await deleteReplacementIntentDraft(draft.id)
  await deleteFormedCandidateArtifact(draft.id)
  await deleteConstructedCandidateArtifact(draft.id)
  await deleteConstructionConstraintValidationArtifact(draft.id)
  await deleteSelectedConstructionRule(draft.id)
  await deleteHypotheticalReplacementReplayDraft(draft.id)
  return draft
}

export async function discardDraft(workspaceId: string) {
  const state = await getWorkspaceState(workspaceId)
  if (!state) return null
  return createDraftFromNode({ workspaceId, baseNodeId: state.activeNodeId })
}

export async function getWorkspaceState(workspaceId: string) {
  return withStore<WorkspaceState | null>(workspaceStateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(workspaceId)
    request.onsuccess = () => {
      try {
        const state = (request.result as WorkspaceState | undefined) ?? null
        if (state?.monitorDefinitionAlertReview != null) {
          assertValidMonitorDefinitionAlertReviewWorkspaceState(
            state.monitorDefinitionAlertReview,
            'Workspace state monitorDefinitionAlertReview',
          )
        }
        resolve(state)
      } catch (error) {
        reject(error)
      }
    }
    request.onerror = () => reject(request.error ?? new Error('Failed to load workspace state'))
  })
}

export async function setActiveNode(input: { workspaceId: string; nodeId: string; createDraftFromNode?: boolean }) {
  const state = (await getWorkspaceState(input.workspaceId)) ?? {
    workspaceId: input.workspaceId,
    activeNodeId: input.nodeId,
    activeDraftId: null,
    lastOpenedAt: new Date().toISOString(),
  }
  const draft = input.createDraftFromNode === false ? null : await createDraftFromNode({ workspaceId: input.workspaceId, baseNodeId: input.nodeId })
  const nextState: WorkspaceState = {
    ...state,
    activeNodeId: input.nodeId,
    activeDraftId: draft?.id ?? null,
    selectedExposureSnapshotId: draft ? 'draft' : input.nodeId,
    monitorDefinitionAlertReview: null,
    lastOpenedAt: new Date().toISOString(),
  }

  await withStores([workspaceStateStoreName, workspaceStoreName, appStateStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStateStoreName).put(nextState)

    const workspaceStore = transaction.objectStore(workspaceStoreName)
    const workspaceRequest = workspaceStore.get(input.workspaceId)
    workspaceRequest.onsuccess = () => {
      const workspace = workspaceRequest.result as PortfolioWorkspace | undefined
      if (workspace) {
        workspaceStore.put({ ...workspace, activeNodeId: input.nodeId, updatedAt: nextState.lastOpenedAt })
      }
      const pointerRequest = transaction.objectStore(appStateStoreName).put({ id: activeWorkspacePointerKey, workspaceId: input.workspaceId })
      pointerRequest.onsuccess = () => resolve(nextState)
      pointerRequest.onerror = () => reject(pointerRequest.error ?? new Error('Failed to update active workspace pointer'))
    }
    workspaceRequest.onerror = () => reject(workspaceRequest.error ?? new Error('Failed to load workspace for active node update'))
  })

  return nextState
}

export async function setSelectedExposureSnapshot(input: { workspaceId: string; snapshotId: string }) {
  const state = await getWorkspaceState(input.workspaceId)
  if (!state) return null

  const nextState: WorkspaceState = {
    ...state,
    selectedExposureSnapshotId: input.snapshotId,
    monitorDefinitionAlertReview: state.monitorDefinitionAlertReview ?? null,
    lastOpenedAt: new Date().toISOString(),
  }

  await withStore<void>(workspaceStateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(nextState)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to persist selected exposure snapshot'))
  })

  return nextState
}

export async function saveVariantFromDraft(input: { workspaceId: string; draftId: string; variantName: string }) {
  const draft = await getDraft(input.workspaceId)
  if (!draft || draft.id !== input.draftId) throw new Error('Draft not found')
  const baseNode = await getNode(draft.baseNodeId)
  if (!baseNode) throw new Error('Base node not found')
  if (!baseNode.portfolioSnapshot) throw new Error('Base node snapshot not found')

  const node: PortfolioNode = {
    id: createId('node'),
    workspaceId: input.workspaceId,
    parentId: draft.baseNodeId,
    kind: 'variant',
    name: input.variantName,
    createdAt: new Date().toISOString(),
    changeSummary: createChangeSummary(baseNode.portfolioSnapshot, draft.portfolioSnapshot, input.variantName),
    portfolioSnapshot: clonePortfolioSnapshot(draft.portfolioSnapshot),
  }

  await withStore<void>(portfolioNodeStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(node)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save portfolio node'))
  })

  const workspaceState = await setActiveNode({ workspaceId: input.workspaceId, nodeId: node.id, createDraftFromNode: true })
  const workspace = await getWorkspace(input.workspaceId)
  if (!workspace) throw new Error('Workspace not found after saving variant')
  return { node, workspace, workspaceState }
}

export async function saveImportedSnapshotNode(input: {
  workspaceId: string
  parentNodeId: string
  portfolioSnapshot: PortfolioSnapshot
  importedFileNames: string[]
  historyContext?: ImportedHistoryContext | null
  importedHistorySnapshot?: ImportedSnapshot | null
  name: string
}) {
  const workspace = await getWorkspace(input.workspaceId)
  if (!workspace) throw new Error('Workspace not found')

  const parentNode = await getNode(input.parentNodeId)
  if (!parentNode) throw new Error('Parent node not found')
  if (!parentNode.portfolioSnapshot) throw new Error('Parent node snapshot not found')

  const source: ImportedNodeSource = buildPersistedImportedSource({
    importedFileNames: input.importedFileNames,
    importedAt: input.portfolioSnapshot.importedMeta.importedAt,
    importer: input.portfolioSnapshot.importedMeta.importer,
    baseCurrency: input.portfolioSnapshot.baseCurrency,
    historyContext: input.historyContext ?? null,
    importedHistorySnapshot: input.importedHistorySnapshot ?? null,
  })

  const node: PortfolioNode = {
    id: createId('node'),
    workspaceId: input.workspaceId,
    parentId: input.parentNodeId,
    kind: 'imported_snapshot',
    name: input.name,
    createdAt: input.portfolioSnapshot.importedMeta.importedAt,
    changeSummary: createChangeSummary(parentNode.portfolioSnapshot, input.portfolioSnapshot, input.name),
    portfolioSnapshot: input.portfolioSnapshot,
    source,
  }

  await withStore<void>(portfolioNodeStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(node)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to save imported snapshot node'))
  })

  const workspaceState = await setActiveNode({ workspaceId: input.workspaceId, nodeId: node.id, createDraftFromNode: true })
  const nextWorkspace = await getWorkspace(input.workspaceId)
  if (!nextWorkspace) throw new Error('Workspace not found after saving imported snapshot node')
  return { node, workspace: nextWorkspace, workspaceState }
}

export async function clearPortfolioWorkspaceState() {
  await withStores([workspaceStoreName, portfolioNodeStoreName, workingDraftStoreName, workspaceStateStoreName, appStateStoreName, candidateImprovementDraftStoreName, intentBoundSeededEtfReplacementRankingDraftStoreName, replacementIntentDraftStoreName, formedCandidateStoreName, constructedCandidateStoreName, constructionConstraintValidationStoreName, selectedConstructionRuleStoreName, hypotheticalReplacementReplayDraftStoreName, versionedProposalStoreName, activeThesisStoreName, persistedConstructionArtifactReviewStoreName, persistedOptimizerHandoffReviewStoreName], 'readwrite', (transaction, resolve, reject) => {
    transaction.objectStore(workspaceStoreName).clear()
    transaction.objectStore(portfolioNodeStoreName).clear()
    transaction.objectStore(workingDraftStoreName).clear()
    transaction.objectStore(workspaceStateStoreName).clear()
    transaction.objectStore(candidateImprovementDraftStoreName).clear()
    transaction.objectStore(intentBoundSeededEtfReplacementRankingDraftStoreName).clear()
    transaction.objectStore(replacementIntentDraftStoreName).clear()
    transaction.objectStore(formedCandidateStoreName).clear()
    transaction.objectStore(constructedCandidateStoreName).clear()
    transaction.objectStore(constructionConstraintValidationStoreName).clear()
    transaction.objectStore(selectedConstructionRuleStoreName).clear()
    transaction.objectStore(hypotheticalReplacementReplayDraftStoreName).clear()
    transaction.objectStore(versionedProposalStoreName).clear()
    transaction.objectStore(activeThesisStoreName).clear()
    transaction.objectStore(persistedConstructionArtifactReviewStoreName).clear()
    transaction.objectStore(persistedOptimizerHandoffReviewStoreName).clear()
    const request = transaction.objectStore(appStateStoreName).delete(activeWorkspacePointerKey)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to clear workspace state'))
  })
}

export async function resetLocalPortfolioDatabase() {
  await deletePortfolioDatabase()
}

export async function getLastOpenedWorkspaceState() {
  const pointer = await withStore<{ id: string; workspaceId: string } | null>(appStateStoreName, 'readonly', (store, resolve, reject) => {
    const request = store.get(activeWorkspacePointerKey)
    request.onsuccess = () => resolve((request.result as { id: string; workspaceId: string } | undefined) ?? null)
    request.onerror = () => reject(request.error ?? new Error('Failed to load active workspace pointer'))
  })
  if (!pointer) return null
  return getWorkspaceState(pointer.workspaceId)
}

export async function saveMonitorDefinitionAlertReviewWorkspaceState(input: {
  workspaceId: string
  reviewState: MonitorDefinitionAlertReviewWorkspaceState | null
}) {
  const state = await getWorkspaceState(input.workspaceId)
  if (!state) {
    throw new Error('Workspace state is missing')
  }

  if (input.reviewState != null) {
    assertValidMonitorDefinitionAlertReviewWorkspaceState(
      input.reviewState,
      'Workspace state monitorDefinitionAlertReview',
    )
  }

  const nextState: WorkspaceState = {
    ...state,
    monitorDefinitionAlertReview: input.reviewState,
    lastOpenedAt: new Date().toISOString(),
  }

  await withStore<void>(workspaceStateStoreName, 'readwrite', (store, resolve, reject) => {
    const request = store.put(nextState)
    request.onsuccess = () => resolve(undefined)
    request.onerror = () => reject(request.error ?? new Error('Failed to persist monitor definition alert review workspace state'))
  })

  return nextState
}
