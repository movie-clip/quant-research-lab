import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PortfolioImprovementWorkspaceShell } from './PortfolioImprovementWorkspaceShell'
import * as portfolioWorkspaceStorage from '../../app/portfolioWorkspaceStorage'
import type {
  MonitorDefinitionAlertReviewTimelineHistoryRow,
  MonitorDefinitionAlertReviewTimelineObservationRow,
  MonitorDefinitionAlertReviewTimelineResponse,
  MonitorDefinitionEvaluationHistoryEntryResponse,
  MonitorDefinitionObservationArtifact,
  MonitorDefinitionRecoveredAlertReviewQueueRow,
} from '../portfolio/types'
import type { MonitorDefinitionAlertReviewSessionState } from '../portfolio/workspaceTypes'

const noOp = () => {}

function textContentOf(testId: string) {
  const matches = screen.getAllByTestId(testId)
  return matches[matches.length - 1]?.textContent ?? ''
}

function clickCompareFor(proposalId: string) {
  const matches = screen.getAllByTestId(`saved-proposal-compare-${proposalId}`)
  fireEvent.click(matches[matches.length - 1])
}

function latestByTestId(testId: string) {
  const matches = screen.getAllByTestId(testId)
  return matches[matches.length - 1]
}

function textContentOfIn(root: HTMLElement, testId: string) {
  const matches = within(root).getAllByTestId(testId)
  return matches[matches.length - 1]?.textContent ?? ''
}

function clickCompareForIn(root: HTMLElement, proposalId: string) {
  const matches = within(root).getAllByTestId(`saved-proposal-compare-${proposalId}`)
  fireEvent.click(matches[matches.length - 1])
}

function makeFamilyReviewResponse(anchorProposal: ReturnType<typeof makeSavedProposal>, siblings: ReturnType<typeof makeSavedProposal>[]) {
  return {
    review_kind: 'review_snapshot_family_review',
    family_key: {
      workspace_id: anchorProposal.workspaceId,
      source_draft_id: anchorProposal.sourceDraftId,
      source_base_node_id: anchorProposal.sourceBaseNodeId,
      proposal_family_id: anchorProposal.proposalFamilyId,
      source_kind: 'hypothetical_replacement_replay',
    },
    provenance: 'persisted_review_snapshot_artifacts_only',
    compare_selection_policy: 'exactly_two_distinct_family_siblings',
    anchor: {
      identity: {
        artifact_id: anchorProposal.reviewSnapshotArtifactId,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        fingerprint: `fingerprint-${anchorProposal.versionNumber}`,
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      open_handoff: anchorProposal.proposalCapture.open_handoff,
      lineage: anchorProposal.proposalCapture.lineage,
      pm_summary: anchorProposal.reviewSnapshotPMSummary,
      comparison_eligibility: { eligible: siblings.length > 1, reason: siblings.length > 1 ? 'compatible_family_sibling_available' : 'no_compatible_family_sibling', compatible_sibling_artifact_ids: siblings.filter((item) => item.reviewSnapshotArtifactId !== anchorProposal.reviewSnapshotArtifactId).map((item) => item.reviewSnapshotArtifactId) },
    },
    siblings: siblings.map((proposal) => ({
      identity: {
        artifact_id: proposal.reviewSnapshotArtifactId,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        fingerprint: `fingerprint-${proposal.versionNumber}`,
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      open_handoff: proposal.proposalCapture.open_handoff,
      lineage: proposal.proposalCapture.lineage,
      pm_summary: proposal.reviewSnapshotPMSummary,
      comparison_eligibility: { eligible: siblings.length > 1, reason: siblings.length > 1 ? 'compatible_family_sibling_available' : 'no_compatible_family_sibling', compatible_sibling_artifact_ids: siblings.filter((item) => item.reviewSnapshotArtifactId !== proposal.reviewSnapshotArtifactId).map((item) => item.reviewSnapshotArtifactId) },
    })),
  }
}

function makeFamilyInboxResponse(proposals: ReturnType<typeof makeSavedProposal>[]) {
  const grouped = new Map<string, ReturnType<typeof makeSavedProposal>[]>()
  proposals.forEach((proposal) => {
    grouped.set(proposal.proposalFamilyId, [...(grouped.get(proposal.proposalFamilyId) ?? []), proposal])
  })
  return {
    inbox_kind: 'review_snapshot_family_inbox',
    workspace_id: proposals[0]?.workspaceId ?? 'workspace-1',
    provenance: 'persisted_review_snapshot_artifacts_only',
    rows: [...grouped.values()]
      .map((familyProposals) => [...familyProposals].sort((left, right) => right.versionNumber - left.versionNumber || new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime()))
      .sort((left, right) => new Date(right[0]!.createdAt).getTime() - new Date(left[0]!.createdAt).getTime())
      .map((familyProposals) => {
        const latest = familyProposals[0]!
        return {
          family_key: {
            workspace_id: latest.workspaceId,
            source_draft_id: latest.sourceDraftId,
            source_base_node_id: latest.sourceBaseNodeId,
            proposal_family_id: latest.proposalFamilyId,
            source_kind: 'hypothetical_replacement_replay',
          },
          latest_identity: {
            artifact_id: latest.reviewSnapshotArtifactId,
            artifact_kind: 'portfolio_review_snapshot',
            schema_version: 'review_snapshot_artifact_v1',
            fingerprint: `fingerprint-${latest.versionNumber}`,
            consumer_kind: 'saved_hypothetical_replay_proposal',
          },
          lineage: latest.proposalCapture.lineage,
          proposal_capture: latest.proposalCapture,
          pm_summary: latest.reviewSnapshotPMSummary,
          sibling_count: familyProposals.length,
          compare_readiness: {
            ready: familyProposals.length > 1,
            reason: familyProposals.length > 1 ? 'compatible_family_pair_available' : 'no_compatible_family_pair',
            compatible_pair_count: familyProposals.length > 1 ? 1 : 0,
          },
          latest_saved_at: latest.createdAt,
          latest_order_provenance: 'persisted_artifact_file_mtime',
        }
      }),
  }
}

function makeActiveThesisCrossFamilyQueueResponse(activeProposal: ReturnType<typeof makeSavedProposal>, proposals: ReturnType<typeof makeSavedProposal>[]) {
  return {
    queue_kind: 'review_snapshot_active_thesis_cross_family_queue',
    provenance: 'persisted_review_snapshot_artifacts_and_active_thesis_reference_only',
    queue_ordering: 'latest_saved_at_desc_then_artifact_id_desc',
    active_thesis: {
      source_proposal_id: activeProposal.id,
      handoff: activeProposal.proposalCapture.open_handoff,
      identity: {
        artifact_id: activeProposal.reviewSnapshotArtifactId,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        fingerprint: `fingerprint-${activeProposal.versionNumber}`,
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      lineage: activeProposal.proposalCapture.lineage,
      family_key: {
        workspace_id: activeProposal.workspaceId,
        source_draft_id: activeProposal.sourceDraftId,
        source_base_node_id: activeProposal.sourceBaseNodeId,
        proposal_family_id: activeProposal.proposalFamilyId,
        source_kind: 'hypothetical_replacement_replay',
      },
    },
    rows: proposals
      .filter((proposal) => proposal.proposalFamilyId !== activeProposal.proposalFamilyId)
      .sort((left, right) => new Date(right.createdAt).getTime() - new Date(left.createdAt).getTime() || right.reviewSnapshotArtifactId.localeCompare(left.reviewSnapshotArtifactId))
      .map((proposal) => ({
        latest_identity: {
          artifact_id: proposal.reviewSnapshotArtifactId,
          artifact_kind: 'portfolio_review_snapshot',
          schema_version: 'review_snapshot_artifact_v1',
          fingerprint: `fingerprint-${proposal.versionNumber}`,
          consumer_kind: 'saved_hypothetical_replay_proposal',
        },
        lineage: proposal.proposalCapture.lineage,
        family_key: {
          workspace_id: proposal.workspaceId,
          source_draft_id: proposal.sourceDraftId,
          source_base_node_id: proposal.sourceBaseNodeId,
          proposal_family_id: proposal.proposalFamilyId,
          source_kind: 'hypothetical_replacement_replay',
        },
        family_separation: {
          separation_kind: 'distinct_proposal_family_id',
          active_thesis_proposal_family_id: activeProposal.proposalFamilyId,
          queue_proposal_family_id: proposal.proposalFamilyId,
        },
        proposal_source: proposal.reviewSnapshot.proposal.proposal_source,
        truth_labels: proposal.reviewSnapshotPMSummary.truth_labels,
        trust_visibility: {
          investor_economics_status: proposal.reviewSnapshotPMSummary.investor_economics_status,
          benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
        },
        pm_summary_fields: {
          replay_type: proposal.reviewSnapshotPMSummary.replay_type,
          replay_status: proposal.reviewSnapshotPMSummary.replay_status,
          review_basis: proposal.reviewSnapshotPMSummary.review_basis,
          methodology: proposal.reviewSnapshotPMSummary.methodology,
          assumptions: proposal.reviewSnapshotPMSummary.assumptions,
          analytics_summary: proposal.reviewSnapshotPMSummary.analytics_summary,
          diagnostics_summary: proposal.reviewSnapshotPMSummary.diagnostics_summary,
        },
        latest_saved_at: proposal.createdAt,
        queue_order_provenance: 'persisted_artifact_file_mtime_desc_then_artifact_id_desc',
      })),
  }
}

function latestByTestIdIn(root: HTMLElement, testId: string) {
  const matches = within(root).getAllByTestId(testId)
  return matches[matches.length - 1]
}

const analysis = {
  snapshot: { statement: { importer: 'interactive_brokers', account_id: 'U1', base_currency: 'USD', statement_period: '2025', page_count: 1 }, positions: [{ symbol: 'AAPL', market_value: 60000 }, { symbol: 'MSFT', market_value: 40000 }] },
  overview: { total_market_value: 100000 },
  risk_summary: { benchmark_symbol: 'SPY' },
} as any

const draftSnapshot = {
  snapshotVersion: 1,
  baseCurrency: 'USD',
  importedMeta: { importer: 'interactive_brokers', statementPeriod: '2025', importedAt: '2026-04-10T00:00:00Z', sourceFileNames: ['IB2025.pdf'] },
  positions: [{ symbol: 'AAPL', marketValue: 60000 }, { symbol: 'MSFT', marketValue: 40000 }],
  cashBalances: [],
  metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
} as any

function makeReplay() {
  return {
    methodology: 'm',
    methodology_provenance: {
      provenance_version: 1,
      source: 'portfolio_allocation_backtest_engine',
      methodology_truth: 'review_only_replay_methodology',
      assumptions_truth: 'review_only_replay_assumptions',
      analytics_truth: 'hypothetical_replay_analytics_only',
      review_scope: 'workspace_review_context_only',
    },
    investor_economics_status: { status: 'available', reason: null },
    reference_result: null,
    candidate_result: {
      portfolio_name: 'Candidate',
      benchmark_symbol: 'SPY',
      start_date: '2024-01-01',
      end_date: '2024-12-31',
      observation_count: 2,
      rebalance_frequency: 'monthly',
      commission_bps: 0,
      slippage_bps: 0,
      drift_tolerance_pct: null,
      assumptions: {
        price_basis: 'adjusted_close',
        execution_price_field: 'close',
        execution_lag_days: 1,
        calendar_policy: 'intersection_common_dates',
        fractional_shares: true,
        long_only: true,
        leverage_allowed: false,
        tax_treatment: 'pre_tax',
        investor_base_currency: 'USD',
      },
      status: 'ok',
      investor_economics_status: { status: 'available', reason: null },
      instrument_metadata: [],
      starting_weights: [],
      ending_weights: [],
      metrics: {
        total_return_pct: 1,
        annualized_return_pct: 1,
        annualized_volatility_pct: 1,
        downside_volatility_pct: 1,
        max_drawdown_pct: -1,
        sharpe_ratio: 1,
        sortino_ratio: 1,
        benchmark_return_pct: 1,
        excess_return_pct: 0,
        tracking_error_pct: 1,
        information_ratio: 0,
        beta_vs_benchmark: 1,
        correlation_vs_benchmark: 1,
        total_turnover_pct: 0,
        turnover_events_count: 0,
        total_cost_paid: 0,
      },
      equity_curve: [
        { date: '2024-01-02', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 },
        { date: '2024-12-31', equity: 101000, cash: 0, gross_exposure: 101000, drawdown_pct: -1 },
      ],
      rebalance_events: [],
      trades: [],
    },
    comparison: null,
    reference_diagnostics: null,
    candidate_diagnostics: null,
    diagnostics_comparison: null,
  }
}

function makeSavedProposal(versionNumber: number, createdAt: string, candidateSymbol: string) {
  const replayProvenance = {
    candidate_input_source: 'replacement_intent_preview',
    construction_rule_id: 'same_weight_substitution_v1',
    upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' },
    seed_ranking_id: 'etf_ranking_engine_v1',
    seed_methodology_id: 'etf_ranking_methodology_v1',
    constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null },
  }
  const proposal = {
    id: `proposal-${versionNumber}`,
    kind: 'single_replacement_hypothetical_replay_proposal',
    schemaVersion: 1,
    createdAt,
    workspaceId: 'workspace-1',
    sourceDraftId: 'draft-1',
    sourceBaseNodeId: 'node-1',
    proposalFamilyId: `etf_replacement_intent:AAPL:${candidateSymbol}:${createdAt}`,
    versionNumber,
    savedFrom: 'desktop_hypothetical_replay_review',
    reviewStatus: 'recorded',
    sourceIntent: {
      kind: 'etf_replacement_intent',
      source: 'candidate_seed',
      createdAt: '2026-04-15T00:05:00Z',
      draftId: 'draft-1',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      baseSymbol: 'AAPL',
      candidateSymbol,
      seededFromDraftId: 'draft-1',
      seedRankingId: 'etf_ranking_engine_v1',
      seedMethodologyId: 'etf_ranking_methodology_v1',
      seedRankingBasisDate: '2026-04-15',
      peerGroup: 'Sector UCITS ETF',
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      confidence: 'medium',
      holdingsSupport: 'mixed',
      warningCount: 1,
    },
    proposalCapture: {
      capture_version: 1,
      capture_kind: 'workspace_review_saved_proposal',
      open_handoff: {
        handoff_kind: 'review_snapshot_open_handoff_v1',
        artifact_id: `review_snapshot_${versionNumber}`,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      lineage: {
        workspace_id: 'workspace-1',
        source_draft_id: 'draft-1',
        source_base_node_id: 'node-1',
        proposal_family_id: `etf_replacement_intent:AAPL:${candidateSymbol}:${createdAt}`,
        proposal_id: `proposal-${versionNumber}`,
        version_number: versionNumber,
        source_kind: 'hypothetical_replacement_replay',
      },
      proposal: {
        source: 'draft_replacement_intent',
        proposal_source: {
          proposal_source_version: 1,
          proposal_source_kind: 'draft_replacement_intent_review_only',
          proposal_truth: 'review_only_hypothetical_proposal',
          portfolio_truth: 'draft_snapshot_not_applied',
          review_scope: 'proposal_review_context_only',
        },
        incumbent_symbol: 'AAPL',
        candidate_symbol: candidateSymbol,
      },
      replay_type: 'standard',
      replay_provenance: replayProvenance,
      review_basis: {
        benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
        benchmark_symbol: 'SPY',
        replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
        rebalance_frequency: 'monthly',
        commission_bps: 0,
        slippage_bps: 0,
        derivation_basis: 'draft_snapshot_positions_normalized',
        candidate_construction_rule: 'same_weight_substitution_v1',
      },
    },
    proposalSource: {
      proposalSourceVersion: 1,
      proposalSourceKind: 'draft_replacement_intent_review_only',
      proposalTruth: 'review_only_hypothetical_proposal',
      portfolioTruth: 'draft_snapshot_not_applied',
      reviewScope: 'proposal_review_context_only',
    },
    reviewSnapshotArtifactId: `review_snapshot_${versionNumber}`,
    reviewSnapshotPMSummary: {
      pm_summary_version: 1,
      role: 'saved_proposal',
      provenance: {
        source: 'persisted_review_snapshot_artifact',
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        consumer_kind: 'saved_hypothetical_replay_proposal',
        lineage: {
          workspace_id: 'workspace-1',
          source_draft_id: 'draft-1',
          source_base_node_id: 'node-1',
          proposal_family_id: `etf_replacement_intent:AAPL:${candidateSymbol}:${createdAt}`,
          proposal_id: `proposal-${versionNumber}`,
          version_number: versionNumber,
          source_kind: 'hypothetical_replacement_replay',
        },
        proposal_source: {
          proposal_source_version: 1,
          proposal_source_kind: 'draft_replacement_intent_review_only',
          proposal_truth: 'review_only_hypothetical_proposal',
          portfolio_truth: 'draft_snapshot_not_applied',
          review_scope: 'proposal_review_context_only',
        },
        replay_provenance: replayProvenance,
      },
      truth_labels: {
        proposal_truth: 'review_only_hypothetical_proposal',
        portfolio_truth: 'draft_snapshot_not_applied',
        analytics_truth: 'hypothetical_replay_analytics_only',
        review_scope: 'proposal_review_context_only',
      },
      replay_type: 'standard',
      replay_status: 'ok',
      investor_economics_status: { status: 'available', reason: null },
      review_basis: {
        benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
        benchmark_symbol: 'SPY',
        replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
        rebalance_frequency: 'monthly',
        commission_bps: 0,
        slippage_bps: 0,
        derivation_basis: 'draft_snapshot_positions_normalized',
        candidate_construction_rule: 'same_weight_substitution_v1',
      },
      methodology: {
        methodology: 'm',
        methodology_provenance: makeReplay().methodology_provenance,
      },
      assumptions: makeReplay().candidate_result.assumptions,
      analytics_summary: {
        candidate_analytics: {
          methodology: 'm',
          methodology_provenance: makeReplay().methodology_provenance,
          assumptions: makeReplay().candidate_result.assumptions,
          benchmark_symbol: 'SPY',
          benchmark_return_pct: 1,
          total_return_pct: 1,
          annualized_return_pct: 1,
          annualized_volatility_pct: 1,
          downside_volatility_pct: 1,
          max_drawdown_pct: -1,
          sharpe_ratio: 1,
          sortino_ratio: 1,
          excess_return_pct: 0,
          tracking_error_pct: 1,
          information_ratio: 0,
          beta_vs_benchmark: 1,
          correlation_vs_benchmark: 1,
          total_turnover_pct: 0,
          total_cost_paid: 0,
        },
        baseline_analytics: null,
        analytics_comparison: null,
      },
      diagnostics_summary: {
        diagnostics_available: false,
        top_factor_exposure_change: null,
        top_volatility_change: null,
        top_risk_contribution_change: null,
        top_concentration_change: null,
        top_stress_scenario_change: null,
      },
    },
    replayBasis: {
      benchmarkSymbol: 'SPY',
      startDate: '2024-01-01',
      endDate: '2024-12-31',
      rebalanceFrequency: 'monthly',
      commissionBps: 0,
      slippageBps: 0,
      derivationBasis: 'draft_snapshot_positions_normalized',
      candidateConstructionRule: 'same_weight_substitution_v1',
      replayProvenance,
    },
    reviewSnapshot: {
      proposal: {
        source: 'draft_replacement_intent',
        proposal_source: {
          proposal_source_version: 1,
          proposal_source_kind: 'draft_replacement_intent_review_only',
          proposal_truth: 'review_only_hypothetical_proposal',
          portfolio_truth: 'draft_snapshot_not_applied',
          review_scope: 'proposal_review_context_only',
        },
        incumbent_symbol: 'AAPL',
        candidate_symbol: candidateSymbol,
        draft_id: 'draft-1',
        base_node_id: 'node-1',
      },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
      replay_provenance: replayProvenance,
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
      candidate_weights: [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: candidateSymbol, target_weight: 0.6 }],
      replay: makeReplay(),
      warnings: [],
    },
  } as any

  return proposal
}

function makeFormedCandidate(status: 'ok' | 'rejected' = 'ok') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    formation: {
      formation: { kind: 'single_replacement_candidate_formation', status },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
      candidate_weights: status === 'ok' ? [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.6 }] : [],
      formation_summary: { incumbent_start_weight: 0.6, candidate_start_weight: status === 'ok' ? 0.6 : null, unchanged_positions_count: status === 'ok' ? 1 : 0, baseline_positions_count: status === 'ok' ? 2 : 0, candidate_positions_count: status === 'ok' ? 2 : 0, starting_turnover_pct: status === 'ok' ? 0.6 : null },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
      warnings: [],
      rejection_reason: status === 'rejected' ? 'replacement intent candidate is already held in draft snapshot: IUFS' : null,
    },
  } as any
}

function makeConstructedCandidate(status: 'ok' | 'rejected' = 'ok') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: 'same_weight_substitution_v1',
    construction: {
      construction: { kind: 'single_replacement_construction', status, rule_id: 'same_weight_substitution_v1' },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      inputs: { baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }], construction_rule: 'same_weight_substitution_v1', incumbent_start_weight: 0.6 },
      outputs: { candidate_weights: status === 'ok' ? [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.6 }] : [], starting_turnover_pct: status === 'ok' ? 0.6 : null, unchanged_positions_count: status === 'ok' ? 1 : 0 },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', construction_basis: 'explicit_single_replacement_rule', cash_treatment: 'excluded_from_construction_basis', position_scope: 'positive_market_value_positions_only' },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', note: 'Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.' },
      warnings: [],
      rejection_reason: status === 'rejected' ? 'replacement intent candidate is already held in draft snapshot: IUFS' : null,
    },
  } as any
}

function makeConstraintValidation(status: 'ok' | 'blocked' | 'rejected' = 'ok') {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: 'same_weight_substitution_v1',
    validation: {
      validation: {
        kind: 'single_replacement_construction_constraint_validation',
        status,
        constraint_set_id: 'single_replacement_construction_constraints_v1',
      },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'same_weight_substitution_v1' },
      derivation: { validation_timing: 'post_construction_pre_replay', validation_basis: 'explicit_constraint_set', candidate_input_source: 'constructed_candidate_payload', constraint_set_id: 'single_replacement_construction_constraints_v1' },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', constraint_validation_truth_class: 'constraint_validation_derived', note: 'Constraint validation remains review-only.' },
      evaluations: [
        { constraint_id: 'weight_sum_matches_rule', severity: 'hard_block', status: status === 'blocked' ? 'fail' : 'pass', message: status === 'blocked' ? 'Constraint failed.' : 'Constraint passed.', rationale: null, actual_value: status === 'blocked' ? 0.97 : 1, expected_value: 1, operator: '==' },
      ],
      blocking_constraint_ids: status === 'blocked' ? ['weight_sum_matches_rule'] : [],
      warnings: [],
      rejection_reason: status === 'rejected' ? 'constructed candidate could not be evaluated safely' : null,
    },
  } as any
}

function makeActiveThesis(versionNumber = 1, candidateSymbol = 'IUFS') {
  const thesisProposal = makeSavedProposal(versionNumber, '2026-04-17T00:00:00Z', candidateSymbol)
  return {
    workspaceId: 'workspace-1',
    promotedAt: '2026-04-17T12:00:00Z',
    sourceProposalId: thesisProposal.id,
    thesisProposal,
  } as any
}

function makePersistedConstructionArtifactReview() {
  return {
    workspaceId: 'workspace-artifact',
    constructionArtifactId: 'artifact-123',
    openedAt: '2026-04-23T00:00:00Z',
    reviewBasisSource: {
      basis_version: 1,
      basis_kind: 'persisted_construction_artifact_review',
      review_scope: 'workspace_review_only',
      canonical_source: 'typed_preview_handoff',
      basis_provenance_label: 'artifact_backed_review_basis',
      portfolio_truth: 'imported_portfolio_snapshot',
      candidate_truth: 'hypothetical_construction_artifact',
      construction_artifact_id: 'artifact-123',
      preview_handoff: {
        handoff_kind: 'construction_artifact_preview_handoff_v1',
        construction_artifact_id: 'artifact-123',
        effective_replay_params: {
          benchmark_symbol: 'SPY',
          start_date: '2024-01-01',
          end_date: '2024-12-31',
          initial_capital: 100000,
          rebalance_frequency: 'monthly',
          base_currency: 'USD',
          commission_bps: 0,
          slippage_bps: 0,
          drift_tolerance_pct: null,
          price_basis: 'adjusted_close',
          execution_price_field: 'close',
          execution_lag_days: 1,
          symbol_overrides: {},
        },
      },
      benchmark_symbol: 'SPY',
      base_currency: 'USD',
      replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
      candidate_weights: [{ symbol: 'MSFT', target_weight: 0.6 }],
    },
    replay: {
      construction_artifact_id: 'artifact-123',
      truth_separation: {
        baseline_truth: 'imported_portfolio_snapshot',
        candidate_truth: 'hypothetical_construction_artifact',
        candidate_applied: false,
        consumption_mode: 'explicit_reference_only',
      },
      review_basis: {
        basis_version: 1,
        basis_kind: 'persisted_construction_artifact_review',
        review_scope: 'workspace_review_only',
        canonical_source: 'typed_preview_handoff',
        basis_provenance_label: 'artifact_backed_review_basis',
        portfolio_truth: 'imported_portfolio_snapshot',
        candidate_truth: 'hypothetical_construction_artifact',
        construction_artifact_id: 'artifact-123',
        preview_handoff: {
          handoff_kind: 'construction_artifact_preview_handoff_v1',
          construction_artifact_id: 'artifact-123',
          effective_replay_params: {
            benchmark_symbol: 'SPY',
            start_date: '2024-01-01',
            end_date: '2024-12-31',
            initial_capital: 100000,
            rebalance_frequency: 'monthly',
            base_currency: 'USD',
            commission_bps: 0,
            slippage_bps: 0,
            drift_tolerance_pct: null,
            price_basis: 'adjusted_close',
            execution_price_field: 'close',
            execution_lag_days: 1,
            symbol_overrides: {},
          },
        },
        benchmark_symbol: 'SPY',
        base_currency: 'USD',
        replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
        candidate_weights: [{ symbol: 'MSFT', target_weight: 0.6 }],
      },
      replay_provenance: {
        source: 'construction_artifact_reference',
        construction_artifact_id: 'artifact-123',
        policy_id: 'policy-1',
        policy_definition_id: 'policy-def-1',
        ranked_universe_artifact_id: 'ranked-1',
        ranking_id: 'ranking-1',
        ranking_methodology_id: 'method-1',
        current_portfolio_artifact_id: 'portfolio-1',
        hard_constraints: {
          full_investment: true,
          long_only: true,
          eligible_ranked_universe_only: true,
          max_position_weight: 0.6,
          min_position_weight: null,
          max_turnover_weight: null,
          max_trade_intent_count: null,
        },
        baseline_input_source: 'normalized_inputs.current_portfolio_weights',
        candidate_input_source: 'final_target_weights',
        selection_rule_trace: {
          rule_ids: ['rule-1'],
          steps: [{ rule_id: 'rule-1', rule_order: 1, input_candidate_symbols: ['AAPL'], output_candidate_symbols: ['MSFT'] }],
        },
        turnover_diagnostics_status: 'unavailable_legacy_artifact',
        turnover_diagnostics_v1: null,
        weighting_trace_status: 'unavailable_legacy_artifact',
        weighting_trace_v1: null,
      },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
      candidate_weights: [{ symbol: 'MSFT', target_weight: 0.6 }],
      replay: makeReplay(),
    },
  } as any
}

function makePersistedOptimizerHandoffReview() {
  return {
    workspaceId: 'workspace-optimizer',
    handoffReference: {
      reference_kind: 'optimizer_handoff_reference_v1',
      handoff_id: 'optimizer_handoff_123',
      artifact_id: 'optimizer_artifact_123',
      manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
      artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
    },
    openedAt: '2026-04-24T00:00:00Z',
    reviewBasisSource: {
      basis_version: 1,
      basis_kind: 'persisted_optimizer_handoff_review',
      review_scope: 'workspace_review_only',
      canonical_source: 'persisted_handoff_reference',
      basis_provenance_label: 'artifact_backed_review_basis',
      portfolio_truth: 'imported_portfolio_snapshot',
      candidate_truth: 'hypothetical_optimizer_handoff',
      handoff_reference: {
        reference_kind: 'optimizer_handoff_reference_v1',
        handoff_id: 'optimizer_handoff_123',
        artifact_id: 'optimizer_artifact_123',
        manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
        artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
      },
      benchmark_symbol: 'SPY',
      base_currency: 'USD',
      replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
      baseline_weights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
      candidate_weights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
    },
    validation: {
      handoff_id: 'optimizer_handoff_123',
      artifact_id: 'optimizer_artifact_123',
      source_portfolio_snapshot_id: 'portfolio_snapshot_123',
      truth_separation: {
        source_truth: 'persisted_hypothetical_optimizer_handoff',
        holdings_truth: 'imported_portfolio_snapshot',
        optimizer_output_applied: false,
        consumption_mode: 'explicit_reference_only',
      },
      eligible_replay_window: {
        source: 'persisted_return_basis_attestation',
        benchmark_symbol: 'SPY',
        as_of_date: '2024-12-31',
        start_date: '2024-01-01',
        end_date: '2024-12-31',
      },
      provenance: {
        source: 'optimizer_handoff_reference',
        benchmark_id: 'benchmark_spy_demo_v1',
        benchmark_version: '2024-04-15',
        benchmark_symbol: 'SPY',
        replay_output_policy: {
          source: 'persisted_return_basis_attestation',
          section_trust: {
            benchmark_relative_path: 'degraded_unverified_return_basis',
            factor_model_path: 'degraded_unverified_return_basis',
            risk_contribution_path: 'degraded_unverified_return_basis',
          },
          eligible_families: [],
          withheld_families: ['benchmark_relative_volatility_outputs', 'factor_exposure_outputs'],
        },
        artifact_state: 'fresh',
        constraint_set_fingerprint: 'constraint-fingerprint-1',
      },
      validation_status: 'ok',
      evaluations: [],
      blocking_rule_ids: [],
      warnings: [],
    },
    replay: {
      handoff_id: 'optimizer_handoff_123',
      artifact_id: 'optimizer_artifact_123',
      source_portfolio_snapshot_id: 'portfolio_snapshot_123',
      truth_separation: {
        baseline_truth: 'imported_portfolio_snapshot',
        candidate_truth: 'hypothetical_optimizer_handoff',
        candidate_applied: false,
        consumption_mode: 'explicit_reference_only',
      },
      review_basis: {
        basis_version: 1,
        basis_kind: 'persisted_optimizer_handoff_review',
        review_scope: 'workspace_review_only',
        canonical_source: 'persisted_handoff_reference',
        basis_provenance_label: 'artifact_backed_review_basis',
        portfolio_truth: 'imported_portfolio_snapshot',
        candidate_truth: 'hypothetical_optimizer_handoff',
        handoff_reference: {
          reference_kind: 'optimizer_handoff_reference_v1',
          handoff_id: 'optimizer_handoff_123',
          artifact_id: 'optimizer_artifact_123',
          manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
          artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
        },
        benchmark_symbol: 'SPY',
        base_currency: 'USD',
        replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
        baseline_weights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
        candidate_weights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
      },
      replay_provenance: {
        source: 'optimizer_handoff_reference',
        benchmark_id: 'benchmark_spy_demo_v1',
        benchmark_version: '2024-04-15',
        benchmark_symbol: 'SPY',
        return_basis_attestation: {
          benchmark_symbol: 'SPY',
          as_of_date: '2024-12-31',
          history_start_date: '2024-01-01',
          history_end_date: '2024-12-31',
          factor_proxy_symbols: ['QQQ'],
          benchmark_return_basis_contract: 'unverified_adjusted_proxy',
          factor_return_basis_contract: 'unverified_adjusted_proxy',
          factor_basis_path: 'degraded_unverified_return_basis',
          section_trust: {
            benchmark_relative_path: 'degraded_unverified_return_basis',
            factor_model_path: 'degraded_unverified_return_basis',
            risk_contribution_path: 'degraded_unverified_return_basis',
          },
          evidence: {
            benchmark_history: { verification_status: 'unverified', economic_basis: 'adjusted_close_proxy', construction_method: 'vendor_adjusted_close', disqualifiers: [], fallbacks_used: [], source_price_field: 'adj_close' },
            factor_history: { verification_status: 'unverified', economic_basis: 'adjusted_close_proxy', construction_method: 'vendor_adjusted_close', disqualifiers: [], fallbacks_used: [], source_price_field: 'adj_close' },
          },
        },
        replay_output_policy: {
          source: 'persisted_return_basis_attestation',
          section_trust: {
            benchmark_relative_path: 'degraded_unverified_return_basis',
            factor_model_path: 'degraded_unverified_return_basis',
            risk_contribution_path: 'degraded_unverified_return_basis',
          },
          eligible_families: [],
          withheld_families: ['benchmark_relative_volatility_outputs', 'factor_exposure_outputs'],
        },
        artifact_state: 'fresh',
        optimizer_status: 'feasible',
        constraint_set_fingerprint: 'constraint-fingerprint-1',
      },
      optimizer_context: {
        objective: {
          objective_id: 'minimize_l2_distance_to_benchmark',
          benchmark_relative: true,
          description: 'Minimize squared distance to benchmark weights inside the hard-constraint set.',
          alpha_signal_id: null,
          requires_alpha_package: false,
        },
        penalty_ids: [],
        artifact_state: 'fresh',
        stale_inputs: [],
        degraded_inputs: [],
        reasons: [],
        run_summary: { engine_id: 'optimizer_engine_v1', solver_id: 'solver_v1', methodology_id: 'optimizer_methodology_v1' },
        diagnostics: { turnover: 0.2, active_share: 0.1 },
        binding_constraints: [],
        violated_constraints: [],
        benchmark_relative_attestations: [],
        binding_constraint_evaluations: [],
      },
      baseline_weights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
      candidate_weights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
      replay: makeReplay(),
    },
  } as any
}

function makePersistedOptimizerHandoffWorkspaceSource() {
  return {
    kind: 'persisted_optimizer_handoff' as const,
    handoffReference: makePersistedOptimizerHandoffReview().handoffReference,
    openedAt: '2026-04-24T00:00:00Z',
    reviewBasis: {
      basisVersion: 1 as const,
      basisKind: 'persisted_optimizer_handoff_review' as const,
      reviewScope: 'workspace_review_only' as const,
      canonicalSource: 'persisted_handoff_reference' as const,
      basisProvenanceLabel: 'artifact_backed_review_basis' as const,
      portfolioTruth: 'imported_portfolio_snapshot' as const,
      candidateTruth: 'hypothetical_optimizer_handoff' as const,
      handoffReference: makePersistedOptimizerHandoffReview().handoffReference,
      openedAt: '2026-04-24T00:00:00Z',
      benchmarkSymbol: 'SPY',
      baseCurrency: 'USD',
      replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
      baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }],
      candidateWeights: [{ symbol: 'CCC', target_weight: 0.2 }],
    },
  }
}

function makePersistedConstructionArtifactWorkspaceSource() {
  return {
    kind: 'persisted_construction_artifact' as const,
    constructionArtifactId: 'artifact-123',
    openedAt: '2026-04-23T00:00:00Z',
    reviewBasis: {
      basisVersion: 1 as const,
      basisKind: 'persisted_construction_artifact_review' as const,
      reviewScope: 'workspace_review_only' as const,
      canonicalSource: 'typed_preview_handoff' as const,
      basisProvenanceLabel: 'artifact_backed_review_basis' as const,
      portfolioTruth: 'imported_portfolio_snapshot' as const,
      candidateTruth: 'hypothetical_construction_artifact' as const,
      constructionArtifactId: 'artifact-123',
      previewHandoff: makePersistedConstructionArtifactReview().replay.review_basis!.preview_handoff,
      openedAt: '2026-04-23T00:00:00Z',
      benchmarkSymbol: 'SPY',
      baseCurrency: 'USD',
      replayWindow: {
        startDate: '2024-01-01',
        endDate: '2024-12-31',
      },
      baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
      candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
    },
  }
}

function makeReplacementRankingDraft(overrides: Record<string, unknown> = {}) {
  return {
    kind: 'intent_bound_seeded_etf_replacement_ranking',
    source: 'etf_ranking',
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    selectedAt: '2026-04-15T00:00:00Z',
    baseSymbol: 'AAPL',
    candidateSymbol: 'IUFS',
    candidateRank: 1,
    rankingId: 'etf_ranking_engine_v1',
    methodologyId: 'etf_ranking_methodology_v1',
    rankingBasisDate: '2026-04-15',
    openHandoff: {
      handoff_kind: 'ranking_artifact_open_handoff_v1',
      artifact_kind: 'etf_ranking',
      artifact_id: 'etf_ranking_artifact_sector_1',
      schema_version: 'etf_ranking_artifact_v1',
    },
    benchmarkSymbol: 'SPY',
    lookbackMonths: 6,
    peerGroup: 'Sector UCITS ETF',
    confidence: 'medium',
    holdingsSupport: 'mixed',
    requestUniverse: ['AAPL', 'IUFS'],
    evaluatedUniverse: ['IUFS'],
    warnings: ['Implementation-fit support is not complete across the ranked universe.'],
    excludedSymbols: [{ symbol: 'VDST', reason: 'instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF' }],
    selectedCandidate: {
      symbol: 'IUFS',
      rank: 1,
      compositeScore: 0.8123,
      instrument: {
        name: 'ETF',
        assetClass: 'etf',
        sector: 'Financials',
        category: 'Sector UCITS ETF',
        currency: 'USD',
      },
    },
    topCandidate: null,
    runnerUpCandidate: null,
    ...overrides,
  } as any
}

function makeLatestObservationInboxRow(overrides: Record<string, unknown> = {}): MonitorDefinitionAlertReviewTimelineObservationRow {
  return {
    monitor_definition_id: 'monitor_definition_abc12345def67890',
    monitor_definition_fingerprint: 'f'.repeat(64),
    monitor_definition_schema_version: 'monitor_definition_artifact_v1',
    observation_id: 'monitor_definition_observation_abc12345',
    monitor_id: 'benchmark_trend_overlay_v1',
    benchmark_symbol: 'SPY',
    review_scope: 'current_portfolio_truth_only',
    evaluation_mode: 'review_only_observation_evaluation',
    evaluated_at: '2026-04-21T09:30:00Z',
    observation_status: 'threshold_breach',
    cause_code: null,
    alert_classification: 'action_required',
    hysteresis_transition: 'open',
    recency_status: 'recent',
    reason: 'current portfolio truth breaches canonical overlay thresholds',
    open_handoff: {
      handoff_kind: 'monitor_definition_observation_open_handoff_v1',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      observation_id: 'monitor_definition_observation_abc12345',
      monitor_id: 'benchmark_trend_overlay_v1',
      benchmark_symbol: 'SPY',
    },
    metadata: {
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_observation_artifact',
    },
    ...overrides,
  } as MonitorDefinitionAlertReviewTimelineObservationRow
}

function makeAlertReviewTimeline(
  rows: Array<MonitorDefinitionAlertReviewTimelineObservationRow | MonitorDefinitionAlertReviewTimelineHistoryRow> = [makeTimelineObservationRow(), makeTimelineHistoryRow()],
): MonitorDefinitionAlertReviewTimelineResponse {
  const observationRows = rows.filter((row) => row.event_kind === 'latest_observation_event').length
  const historyRows = rows.filter((row) => row.event_kind === 'evaluation_history_event').length
  return {
    items: rows,
    metadata: {
      contract_version: 'monitor_definition_alert_review_timeline_v1',
      provenance: 'canonical_latest_observation_artifact_and_append_only_evaluation_history_entries',
      ordering: 'newest_first_evaluated_at_then_observation_event_then_history_entry_id',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      monitor_definition_fingerprint: 'f'.repeat(64),
      monitor_definition_schema_version: 'monitor_definition_artifact_v1',
      observation_row_provenance: 'persisted_monitor_definition_observation_artifact',
      history_row_provenance: 'persisted_monitor_definition_evaluation_history_entry',
      source_precedence: 'persisted_observation_artifact_then_persisted_evaluation_history_entries_then_persisted_latest_alert_episode_projection',
      latest_alert_episode: null,
      total_rows: rows.length,
      observation_rows: observationRows,
      history_rows: historyRows,
    },
  } satisfies MonitorDefinitionAlertReviewTimelineResponse
}

function makeObservationArtifact(overrides: Record<string, unknown> = {}): MonitorDefinitionObservationArtifact {
  return {
    schema_version: 'monitor_definition_observation_artifact_v1',
    observation_id: 'monitor_definition_observation_abc12345',
    monitor_definition_id: 'monitor_definition_abc12345def67890',
    monitor_definition_fingerprint: 'f'.repeat(64),
    monitor_definition_schema_version: 'monitor_definition_artifact_v1',
    monitor_id: 'benchmark_trend_overlay_v1',
    benchmark_symbol: 'SPY',
    evaluation_mode: 'review_only_observation_evaluation',
    evaluated_at: '2026-04-21T09:30:00Z',
    observation_status: 'threshold_breach',
    cause_code: null,
    alert_classification: 'action_required',
    hysteresis_transition: 'open',
    source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry',
    reason: 'current portfolio truth breaches canonical overlay thresholds',
    thresholds: {
      minimum_confirmation_count: 2,
      risk_on_min_risky_weight: 0.95,
      risk_on_max_cash_weight: 0.05,
      risk_reduced_max_risky_weight: 0.35,
      risk_reduced_min_cash_weight: 0.65,
    },
    benchmark_observation: {
      overlay_id: 'benchmark_trend_overlay_v1',
      status: 'risk_reduced',
      as_of_month_end: '2024-12-31',
      benchmark_symbol: 'SPY',
      signal_basis: '10_month_sma_month_end',
      confirmation_count: 2,
      rule_version: 'v1',
      source_lineage: {
        source_kind: 'benchmark_overlay_signal',
        source_id: 'overlay-signal-2024-12-31',
        observed_at: '2025-01-02T09:30:00Z',
      },
    },
    portfolio_observation: {
      total_portfolio_value: 685,
      risky_value: 35,
      cash_value: 650,
      risky_weight: 0.05109489,
      cash_weight: 0.94890511,
      position_count: 2,
      source_lineage: {
        truth_basis: 'imported_portfolio_snapshot',
        importer: 'interactive_brokers',
        imported_at: '2024-04-15T09:30:00Z',
        statement_period: '2024-04',
        source_paths: ['IB2024.pdf'],
      },
    },
    active_observation: {
      required_overlay_status: 'risk_reduced',
      threshold_evaluation_performed: true,
      required_min_risky_weight: null,
      required_max_risky_weight: 0.35,
      required_min_cash_weight: 0.65,
      required_max_cash_weight: null,
      actual_risky_weight: 0.05109489,
      actual_cash_weight: 0.94890511,
      risky_weight_gap: -0.29890511,
      cash_weight_gap: 0.29890511,
      triggered_thresholds: [],
    },
    ...overrides,
  } as MonitorDefinitionObservationArtifact
}

function makeAlertHistoryQueueRow(overrides: Record<string, unknown> = {}) {
  return {
    monitor_definition_id: 'monitor_definition_abc12345def67890',
    monitor_definition_fingerprint: 'f'.repeat(64),
    monitor_definition_schema_version: 'monitor_definition_artifact_v1',
    history_entry_id: 'monitor_definition_history_entry_abc12345',
    monitor_id: 'benchmark_trend_overlay_v1',
    benchmark_symbol: 'SPY',
    review_scope: 'current_portfolio_truth_only',
    evaluation_mode: 'review_only_observation_evaluation',
    evaluated_at: '2026-04-21T09:30:00Z',
    outcome_status: 'threshold_breach',
    cause_code: null,
    significance_status: 'action_required',
    hysteresis_transition: 'open',
    review_support_status: 'review_supported',
    latest_for_monitor_definition: true,
    reason: 'current portfolio truth breaches canonical overlay thresholds',
    review_handoff: {
      handoff_kind: 'monitor_definition_evaluation_history_review_handoff_v1',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      history_entry_id: 'monitor_definition_history_entry_abc12345',
      monitor_id: 'benchmark_trend_overlay_v1',
      benchmark_symbol: 'SPY',
    },
    metadata: {
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_evaluation_history_entry_with_latest_snapshot_precedence',
    },
    ...overrides,
  }
}

function makeTimelineObservationRow(overrides: Record<string, unknown> = {}): MonitorDefinitionAlertReviewTimelineObservationRow {
  return {
    ...makeLatestObservationInboxRow(),
    event_kind: 'latest_observation_event',
    event_semantics: 'observation_rooted',
    thresholds: makeObservationArtifact().thresholds,
    benchmark_observation: makeObservationArtifact().benchmark_observation,
    portfolio_observation: makeObservationArtifact().portfolio_observation,
    active_observation: makeObservationArtifact().active_observation,
    metadata: {
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_observation_artifact',
    },
    ...overrides,
  } as MonitorDefinitionAlertReviewTimelineObservationRow
}

function makeTimelineHistoryRow(overrides: Record<string, unknown> = {}): MonitorDefinitionAlertReviewTimelineHistoryRow {
  return {
    ...makeAlertHistoryQueueRow(),
    event_kind: 'evaluation_history_event',
    event_semantics: 'history_entry_rooted',
    thresholds: makeEvaluationHistoryEntryResponse().item.thresholds,
    benchmark_observation: makeEvaluationHistoryEntryResponse().item.benchmark_observation,
    portfolio_observation: makeEvaluationHistoryEntryResponse().item.portfolio_observation,
    active_observation: makeEvaluationHistoryEntryResponse().item.active_observation,
    metadata: {
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_evaluation_history_entry',
    },
    ...overrides,
  } as MonitorDefinitionAlertReviewTimelineHistoryRow
}

function makeRecoveredAlertQueueRow(overrides: Record<string, unknown> = {}): MonitorDefinitionRecoveredAlertReviewQueueRow {
  return {
    monitor_definition_id: 'monitor_definition_abc12345def67890',
    monitor_definition_fingerprint: 'f'.repeat(64),
    monitor_definition_schema_version: 'monitor_definition_artifact_v1',
    observation_id: 'monitor_definition_observation_abc12345',
    latest_history_entry_id: 'monitor_definition_history_entry_latest_info',
    monitor_id: 'benchmark_trend_overlay_v1',
    benchmark_symbol: 'SPY',
    review_scope: 'current_portfolio_truth_only',
    evaluation_mode: 'review_only_observation_evaluation',
    evaluated_at: '2026-04-21T09:30:00Z',
    observation_status: 'ok',
    cause_code: null,
    alert_classification: 'informational',
    hysteresis_transition: 'recover',
    recency_status: 'recent',
    reason: 'latest persisted evaluation recovered to informational state',
    alert_episode: {
      contract_version: 'monitor_definition_alert_episode_v1',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      episode_id: 'monitor_definition_alert_episode_abc12345def67890',
      episode_status: 'recovered',
      started_at: '2026-04-20T09:30:00Z',
      ended_at: '2026-04-21T09:30:00Z',
      hysteresis_transition: 'recover',
      source_precedence: 'persisted_alert_episode_record_then_canonical_evaluation_lineage_validation',
      latest_contributing_observation: {
        observation_id: 'monitor_definition_observation_abc12345',
        evaluated_at: '2026-04-21T09:30:00Z',
        observation_status: 'ok',
        cause_code: null,
        alert_classification: 'informational',
      },
      recovery_basis: {
        recovered_from_history_entry_id: 'monitor_definition_history_entry_alert',
        recovered_from_evaluated_at: '2026-04-20T09:30:00Z',
        recovered_from_outcome_status: 'threshold_breach',
        recovered_from_cause_code: null,
        recovered_from_significance_status: 'action_required',
      },
    },
    recovered_from: {
      history_entry_id: 'monitor_definition_history_entry_alert',
      evaluated_at: '2026-04-20T09:30:00Z',
      outcome_status: 'threshold_breach',
      cause_code: null,
      significance_status: 'action_required',
      reason: 'prior persisted alert state',
    },
    timeline_handoff: {
      handoff_kind: 'monitor_definition_alert_review_timeline_open_handoff_v1',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      selected_event_kind: 'latest_observation_event',
      observation_id: 'monitor_definition_observation_abc12345',
      monitor_id: 'benchmark_trend_overlay_v1',
      benchmark_symbol: 'SPY',
    },
    metadata: {
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage',
    },
    ...overrides,
  }
}

function makeEvaluationHistoryEntryResponse(overrides: Record<string, unknown> = {}): MonitorDefinitionEvaluationHistoryEntryResponse {
  return {
    item: {
      schema_version: 'monitor_definition_evaluation_history_entry_v1',
      history_entry_id: 'monitor_definition_history_entry_abc12345',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      monitor_definition_fingerprint: 'f'.repeat(64),
      monitor_definition_schema_version: 'monitor_definition_artifact_v1',
      monitor_id: 'benchmark_trend_overlay_v1',
      benchmark_symbol: 'SPY',
      evaluation_mode: 'review_only_observation_evaluation',
      evaluated_at: '2026-04-21T09:30:00Z',
      observation_status: 'threshold_breach',
      cause_code: null,
      significance_status: 'action_required',
      hysteresis_transition: 'open',
      source_precedence: 'persisted_evaluation_history_entry_only',
      reason: 'current portfolio truth breaches canonical overlay thresholds',
      thresholds: {
        minimum_confirmation_count: 2,
        risk_on_min_risky_weight: 0.95,
        risk_on_max_cash_weight: 0.05,
        risk_reduced_max_risky_weight: 0.35,
        risk_reduced_min_cash_weight: 0.65,
      },
      benchmark_observation: {
        overlay_id: 'benchmark_trend_overlay_v1',
        status: 'risk_reduced',
        as_of_month_end: '2024-12-31',
        benchmark_symbol: 'SPY',
        signal_basis: '10_month_sma_month_end',
        confirmation_count: 2,
        rule_version: 'v1',
        source_lineage: {
          source_kind: 'benchmark_overlay_signal',
          source_id: 'overlay-signal-2024-12-31',
          observed_at: '2025-01-02T09:30:00Z',
        },
      },
      portfolio_observation: {
        total_portfolio_value: 685,
        risky_value: 35,
        cash_value: 650,
        risky_weight: 0.05109489,
        cash_weight: 0.94890511,
        position_count: 2,
        source_lineage: {
          truth_basis: 'imported_portfolio_snapshot',
          importer: 'interactive_brokers',
          imported_at: '2024-04-15T09:30:00Z',
          statement_period: '2024-04',
          source_paths: ['IB2024.pdf'],
        },
      },
      active_observation: {
        required_overlay_status: 'risk_reduced',
        threshold_evaluation_performed: true,
        required_min_risky_weight: null,
        required_max_risky_weight: 0.35,
        required_min_cash_weight: 0.65,
        required_max_cash_weight: null,
        actual_risky_weight: 0.05109489,
        actual_cash_weight: 0.94890511,
        risky_weight_gap: -0.29890511,
        cash_weight_gap: 0.29890511,
        triggered_thresholds: [],
      },
      metadata: {
        history_truth: 'authoritative_persisted_monitor_definition_evaluation_history',
        row_provenance: 'persisted_monitor_definition_evaluation_history_entry',
      },
    },
    metadata: {
      contract_version: 'monitor_definition_evaluation_history_v1',
      history_truth: 'authoritative_persisted_monitor_definition_evaluation_history',
      row_provenance: 'persisted_monitor_definition_evaluation_history_entry',
      source_precedence: 'persisted_evaluation_history_entry_only',
      inspection_order: 'newest_first_evaluated_at',
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      monitor_definition_fingerprint: 'f'.repeat(64),
      monitor_definition_schema_version: 'monitor_definition_artifact_v1',
      returned_limit: 20,
      total_entries: 1,
      retrieved_history_entry_id: 'monitor_definition_history_entry_abc12345',
    },
    ...overrides,
  }
}

function renderShell(overrides: Record<string, any> = {}) {
  const monitorDefinitionAlertReviewSession: MonitorDefinitionAlertReviewSessionState = {
    navigation: null,
    timeline: makeAlertReviewTimeline([]),
    timelineStatus: 'ready',
    timelineError: null,
    latestObservation: { status: 'idle', row: null, observation: null, error: null },
    alertHistory: { status: 'idle', row: null, entry: null, error: null },
  }

  return render(
    <PortfolioImprovementWorkspaceShell
      analysis={analysis}
      draftSnapshot={draftSnapshot}
      candidateImprovementDraft={null}
      intentBoundSeededEtfReplacementRankingDraft={null}
      replacementIntentDraft={null}
      formedCandidateArtifact={null}
      constructedCandidateArtifact={null}
      constructionConstraintValidationArtifact={null}
      selectedConstructionRuleId="same_weight_substitution_v1"
      allocationBacktestResult={null}
      hypotheticalReplayResult={null}
      savedProposals={[]}
      activeThesis={null}
      onOpenSavedProposal={noOp}
      openedSavedProposalArtifactId={null}
      onPromoteProposalToThesis={noOp}
      onClearActiveThesis={noOp}
      onSaveProposal={noOp}
      onHypotheticalReplayResult={noOp}
      onFormedCandidateArtifact={noOp}
      onConstructedCandidateArtifact={noOp}
      onConstructionConstraintValidationArtifact={noOp}
      onSelectedConstructionRuleChange={noOp}
      persistedOptimizerHandoffReview={null}
      monitorDefinitionAlertReviewSession={monitorDefinitionAlertReviewSession}
      recoveredAlertReviewQueue={[]}
      onOpenLatestObservation={noOp}
      onOpenAlertHistoryReview={noOp}
      onReopenRecoveredAlertReview={noOp}
      {...overrides}
    />,
  )
}

describe('PortfolioImprovementWorkspaceShell', () => {
  it('renders latest observation timeline rows and opens the read-only observation review surface from authoritative ids', async () => {
    const onOpenLatestObservation = vi.fn()
    const row = makeTimelineObservationRow()

    renderShell({
      monitorDefinitionAlertReviewSession: {
        navigation: null,
        timeline: makeAlertReviewTimeline([row]),
        timelineStatus: 'ready',
        timelineError: null,
        latestObservation: { status: 'ready', row, observation: makeObservationArtifact(), error: null },
        alertHistory: { status: 'idle', row: null, entry: null, error: null },
      },
      onOpenLatestObservation,
    })

    expect(screen.getByText('Latest Observation Alerts')).toBeTruthy()
    expect(screen.getAllByText('Rows: 1 · provenance: canonical_latest_observation_artifact_and_append_only_evaluation_history_entries · ordering: newest_first_evaluated_at_then_observation_event_then_history_entry_id').length).toBeGreaterThan(0)
    expect(screen.getByText('Opened by timeline ids only: monitor_definition_abc12345def67890 · monitor_definition_observation_abc12345')).toBeTruthy()
    expect(screen.getByText('Threshold observation')).toBeTruthy()

    fireEvent.click(screen.getByText('Open observation'))
    expect(onOpenLatestObservation).toHaveBeenCalledWith(expect.objectContaining({
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      open_handoff: expect.objectContaining({ observation_id: 'monitor_definition_observation_abc12345' }),
    }))
  })

  it('renders explicit empty and degraded observation timeline states', () => {
    const degradedRow = makeTimelineObservationRow({
      observation_id: 'monitor_definition_observation_degraded',
      observation_status: 'degraded',
      cause_code: 'benchmark_observation_unconfirmed',
      alert_classification: 'degraded',
      open_handoff: {
        handoff_kind: 'monitor_definition_observation_open_handoff_v1',
        monitor_definition_id: 'monitor_definition_abc12345def67890',
        observation_id: 'monitor_definition_observation_degraded',
        monitor_id: 'benchmark_trend_overlay_v1',
        benchmark_symbol: 'SPY',
      },
    })

    const { rerender } = renderShell({
      monitorDefinitionAlertReviewSession: {
        navigation: null,
        timeline: makeAlertReviewTimeline([]),
        timelineStatus: 'ready',
        timelineError: null,
        latestObservation: { status: 'idle', row: null, observation: null, error: null },
        alertHistory: { status: 'idle', row: null, entry: null, error: null },
      },
    })

    expect(screen.getByText('No definition-scoped latest-observation review events are currently available in the authoritative timeline.')).toBeTruthy()

    rerender(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={noOp}
        onHypotheticalReplayResult={noOp}
        onFormedCandidateArtifact={noOp}
        onConstructedCandidateArtifact={noOp}
        onConstructionConstraintValidationArtifact={noOp}
        onSelectedConstructionRuleChange={noOp}
        persistedOptimizerHandoffReview={null}
        monitorDefinitionAlertReviewSession={{
          navigation: null,
          timeline: makeAlertReviewTimeline([degradedRow]),
          timelineStatus: 'ready',
          timelineError: null,
          latestObservation: { status: 'error', row: degradedRow, observation: null, error: 'Unable to open timeline observation review: persisted observation observation_id does not match selected timeline observation event' },
          alertHistory: { status: 'idle', row: null, entry: null, error: null },
        }}
        onOpenLatestObservation={noOp}
      />,
    )

    expect(screen.getByText('degraded · recent')).toBeTruthy()
    expect(screen.getByText('degraded · cause benchmark observation unconfirmed')).toBeTruthy()
    expect(screen.getByText('Unable to open timeline observation review: persisted observation observation_id does not match selected timeline observation event')).toBeTruthy()
  })

  it('renders alert history queue rows and opens the read-only history review surface from authoritative ids', () => {
    const onOpenAlertHistoryReview = vi.fn()
    const row = makeTimelineHistoryRow()

    renderShell({
      monitorDefinitionAlertReviewSession: {
        navigation: null,
        timeline: makeAlertReviewTimeline([row]),
        timelineStatus: 'ready',
        timelineError: null,
        latestObservation: { status: 'idle', row: null, observation: null, error: null },
        alertHistory: { status: 'ready', row, entry: makeEvaluationHistoryEntryResponse(), error: null },
      },
      onOpenAlertHistoryReview,
    })

    expect(screen.getAllByText('Alert History Queue').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Rows: 1 · provenance: canonical_latest_observation_artifact_and_append_only_evaluation_history_entries · ordering: newest_first_evaluated_at_then_observation_event_then_history_entry_id').length).toBeGreaterThan(0)
    expect(screen.getByText('Opened by timeline ids only: monitor_definition_abc12345def67890 · monitor_definition_history_entry_abc12345')).toBeTruthy()
    expect(screen.getAllByText('History Review').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByText('Open history review'))
    expect(onOpenAlertHistoryReview).toHaveBeenCalledWith(expect.objectContaining({
      monitor_definition_id: 'monitor_definition_abc12345def67890',
      review_handoff: expect.objectContaining({ history_entry_id: 'monitor_definition_history_entry_abc12345' }),
    }))
  })

  it('renders explicit empty and mismatch alert history timeline states', () => {
    const degradedRow = makeTimelineHistoryRow({
      history_entry_id: 'monitor_definition_history_entry_degraded',
      outcome_status: 'degraded',
      cause_code: 'benchmark_observation_unconfirmed',
      significance_status: 'degraded',
      latest_for_monitor_definition: false,
      review_handoff: {
        handoff_kind: 'monitor_definition_evaluation_history_review_handoff_v1',
        monitor_definition_id: 'monitor_definition_abc12345def67890',
        history_entry_id: 'monitor_definition_history_entry_degraded',
        monitor_id: 'benchmark_trend_overlay_v1',
        benchmark_symbol: 'SPY',
      },
    })

    const { rerender } = renderShell({
      monitorDefinitionAlertReviewSession: {
        navigation: null,
        timeline: makeAlertReviewTimeline([]),
        timelineStatus: 'ready',
        timelineError: null,
        latestObservation: { status: 'idle', row: null, observation: null, error: null },
        alertHistory: { status: 'idle', row: null, entry: null, error: null },
      },
    })

    expect(screen.getAllByText('No definition-scoped evaluation-history review events are currently available in the authoritative timeline.').length).toBeGreaterThan(0)

    rerender(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={noOp}
        onHypotheticalReplayResult={noOp}
        onFormedCandidateArtifact={noOp}
        onConstructedCandidateArtifact={noOp}
        onConstructionConstraintValidationArtifact={noOp}
        onSelectedConstructionRuleChange={noOp}
        persistedOptimizerHandoffReview={null}
        monitorDefinitionAlertReviewSession={{
          navigation: null,
          timeline: makeAlertReviewTimeline([degradedRow]),
          timelineStatus: 'ready',
          timelineError: null,
          latestObservation: { status: 'idle', row: null, observation: null, error: null },
          alertHistory: { status: 'error', row: degradedRow, entry: null, error: 'Unable to open timeline history review: persisted history entry history_entry_id does not match selected timeline history event' },
        }}
        recoveredAlertReviewQueue={[]}
        onOpenLatestObservation={noOp}
        onOpenAlertHistoryReview={noOp}
        onReopenRecoveredAlertReview={noOp}
      />,
    )

    expect(screen.getByText('degraded · degraded · historical')).toBeTruthy()
    expect(screen.getByText('review supported · cause benchmark observation unconfirmed')).toBeTruthy()
    expect(screen.getByText('Unable to open timeline history review: persisted history entry history_entry_id does not match selected timeline history event')).toBeTruthy()
  })

  it('renders recovered review queue rows from backend payloads directly and reopens timeline review by authoritative ids', () => {
    const onReopenRecoveredAlertReview = vi.fn()
    const row = makeRecoveredAlertQueueRow()

    renderShell({
      recoveredAlertReviewQueue: [row],
      onReopenRecoveredAlertReview,
    })

    expect(screen.getAllByTestId('recovered-alert-review-queue').at(-1)).toBeTruthy()
    expect(screen.getByText('Rows: 1 · newest first · discovery-only handoff to the authoritative definition-scoped timeline latest-observation event.')).toBeTruthy()
    expect(screen.getAllByText('Active alert episodes reopen from the persisted active alert-episode inbox by authoritative persisted episode and timeline ids only; this recovered queue stays recovered-only.').length).toBeGreaterThan(0)
    expect(screen.getByTestId('recovered-alert-row-monitor_definition_observation_abc12345')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Reopen timeline review' }))

    expect(onReopenRecoveredAlertReview).toHaveBeenCalledTimes(1)
    expect(onReopenRecoveredAlertReview).toHaveBeenCalledWith(row)
  })

  it('shows an explicit decision summary when no candidate exists yet', () => {
    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Portfolio Improvement Decision Summary').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Not selected').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No artifact').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Current review state only.').length).toBeGreaterThan(0)
  })

  it('shows partial decision summary state when candidate exists but replay has not run', () => {
    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={{ workspaceId: 'workspace-1', draftId: 'draft-1', baseNodeId: 'node-1', seed: { kind: 'etf_replacement_candidate', source: 'etf_ranking', seededAt: '2026-04-15T00:00:00Z', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', candidateRank: 1, peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, rankingId: 'etf_ranking_engine_v1', methodologyId: 'etf_ranking_methodology_v1', rankingBasisDate: '2026-04-15', confidence: 'medium', holdingsSupport: 'mixed', requestUniverse: ['AAPL', 'IUFS'], evaluatedUniverse: ['IUFS'], warningCount: 1, excludedSymbolsCount: 0 } }}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getByText('Hypothetical replay cannot run until the selected candidate is promoted into an explicit replacement intent.')).toBeTruthy()
  })

  it('renders seeded replacement review from canonical open handoff only', () => {
    renderShell({
      candidateImprovementDraft: null,
      intentBoundSeededEtfReplacementRankingDraft: makeReplacementRankingDraft(),
    })

    expect(screen.getByText('Ranked Review')).toBeTruthy()
    expect(screen.getByText('Open Handoff')).toBeTruthy()
    expect(screen.queryByText('consumer_handoff')).toBeNull()
    expect(screen.queryByText('intent_bound_etf_replacement_ranking_consumer_handoff_v1')).toBeNull()
  })

  it('renders workspace sections in the approved order', () => {
    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={{ workspaceId: 'workspace-1', draftId: 'draft-1', baseNodeId: 'node-1', seed: { kind: 'etf_replacement_candidate', source: 'etf_ranking', seededAt: '2026-04-15T00:00:00Z', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', candidateRank: 1, peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, rankingId: 'etf_ranking_engine_v1', methodologyId: 'etf_ranking_methodology_v1', rankingBasisDate: '2026-04-15', confidence: 'medium', holdingsSupport: 'mixed', requestUniverse: ['AAPL', 'IUFS'], evaluatedUniverse: ['IUFS'], warningCount: 1, excludedSymbolsCount: 0 } }}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Overview').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Portfolio Research Workspace').length).toBeGreaterThan(0)
    expect(screen.queryByText('Workflow / Analysis Guide')).toBeNull()
    expect(screen.queryByText('Workflow Readiness')).toBeNull()
    expect(screen.queryByText('Section Status Guidance')).toBeNull()

    const overviewMatches = screen.getAllByText('Overview')
    const currentMatches = screen.getAllByText('Current Portfolio')
    const candidateMatches = screen.getAllByText('Candidate')
    const compareMatches = screen.getAllByText('Compare')
    const proposalMatches = screen.getAllByText('Proposal')

    const overview = overviewMatches[overviewMatches.length - 1] as HTMLElement
    const current = currentMatches[currentMatches.length - 1] as HTMLElement
    const candidate = candidateMatches[candidateMatches.length - 1] as HTMLElement
    const compare = compareMatches[compareMatches.length - 1] as HTMLElement
    const proposal = proposalMatches[proposalMatches.length - 1] as HTMLElement

    expect(overview.compareDocumentPosition(current) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(current.compareDocumentPosition(candidate) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(candidate.compareDocumentPosition(compare) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(compare.compareDocumentPosition(proposal) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it('owns the shell-level replay, diagnostics, and proposal framing', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Hypothetical Replay').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Diagnostics Change').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Saved Proposal').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No saved proposal artifact yet.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
  })

  it('updates readiness guidance when replay and saved proposal state exist', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={savedProposal.sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={savedProposal.reviewSnapshot}
        savedProposals={[savedProposal]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Recorded').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Construction Constraints').length).toBeGreaterThan(0)
    expect(screen.getAllByText('An immutable proposal artifact has been recorded for this workflow.').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Replay lineage: direct preview replay · same-weight substitution · validation not supplied').length).toBeGreaterThan(0)
  })

  it('shows constructed candidate replay lineage with the actual construction rule', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    const constructedReplay = {
      ...savedProposal.reviewSnapshot,
      derivation: {
        baseline_basis: 'draft_snapshot_positions_normalized',
        candidate_construction_rule: 'fixed_split_50_50_substitution_v2',
      },
      replay_provenance: {
        candidate_input_source: 'constructed_candidate_payload',
        construction_rule_id: 'fixed_split_50_50_substitution_v2',
        upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' },
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1',
        constraint_validation: { supplied: true, validation_status: 'blocked', constraint_set_id: 'single_replacement_construction_constraints_v1' },
      },
    }

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={savedProposal.sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={{ ...makeConstructedCandidate(), constructionRuleId: 'fixed_split_50_50_substitution_v2' }}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="fixed_split_50_50_substitution_v2"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={constructedReplay}
        savedProposals={[savedProposal]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getByText('Replay lineage: constructed candidate replay · fixed split 50/50 · validated blocked')).toBeTruthy()
  })

  it('renders explicit candidate formation state between candidate idea and replay', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    const candidateMatches = screen.getAllByText('Candidate')
    const formationMatches = screen.getAllByText('Candidate Formation')
    const constructionMatches = screen.getAllByText('Construction Rule')
    const replayMatches = screen.getAllByText('Hypothetical Replay')
    const candidate = candidateMatches[candidateMatches.length - 1] as HTMLElement
    const formation = formationMatches[formationMatches.length - 1] as HTMLElement
    const construction = constructionMatches[constructionMatches.length - 1] as HTMLElement
    const replay = replayMatches[replayMatches.length - 1] as HTMLElement

    expect(candidate.compareDocumentPosition(formation) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(formation.compareDocumentPosition(construction) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(construction.compareDocumentPosition(replay) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getAllByText('Formed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Constructed').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Pass').length).toBeGreaterThan(0)
    expect(screen.getAllByText('candidate_formation_derived').length).toBeGreaterThan(0)
    expect(screen.getAllByText('candidate_construction_derived').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Truth provenance: .*constraint_validation_derived/).length).toBeGreaterThan(0)
  })

  it('shows explicit candidate formation rejection state', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate('rejected')}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        onAllocationBacktestResult={noOp}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onSaveProposal={() => {}}
        onPromoteProposalToThesis={() => {}}
        onClearActiveThesis={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Rejected').length).toBeGreaterThan(0)
    expect(screen.getByText('Formation rejected: replacement intent candidate is already held in draft snapshot: IUFS')).toBeTruthy()
    expect(screen.getAllByText('replacement intent candidate is already held in draft snapshot: IUFS').length).toBeGreaterThan(0)
  })

  it('summarizes replay and diagnostics state without presenting a recommendation', () => {
    const replayWithDiagnostics = {
      ...makeReplay(),
      comparison: {
        total_return_diff_pct: 2.5,
        annualized_return_diff_pct: 1.5,
        benchmark_return_diff_pct: null,
        annualized_volatility_diff_pct: -0.5,
        downside_volatility_diff_pct: -0.4,
        max_drawdown_diff_pct: 0.3,
        sharpe_diff: 0.2,
        sortino_diff: 0.2,
        excess_return_diff_pct: 1.1,
        tracking_error_diff_pct: 0.2,
        information_ratio_diff: 0.1,
        beta_diff: 0,
        correlation_diff: 0,
        total_turnover_diff_pct: 0,
        total_cost_diff: 0,
      },
      diagnostics_comparison: {
        concentration_changes: [],
        top_concentration_change: { key: 'position_hhi', label: 'Position HHI', baseline_value: 0.4, candidate_value: 0.35, delta_value: -0.05, selection_rule: 'largest_absolute_delta', rationale: 'candidate modestly reduces concentration' },
        factor_exposure_changes: [],
        top_factor_exposure_change: null,
        volatility_changes: [],
        top_volatility_change: null,
        risk_contribution_changes: [],
        top_risk_contribution_change: null,
        stress_scenario_changes: [],
        top_stress_scenario_change: null,
      },
    } as any

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={{ ...makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').reviewSnapshot, replay: replayWithDiagnostics }}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Formed').length).toBeGreaterThan(0)
    expect(screen.getByText('Total return delta +2.50% versus baseline under the shared replay window.')).toBeTruthy()
    expect(screen.getAllByText('Position HHI').length).toBeGreaterThan(0)
    expect(screen.getByText('Concentration shows -0.05. candidate modestly reduces concentration')).toBeTruthy()
  })

  it('gates shell summary wording when replay investor-economics are withheld', () => {
    const withheldReplay = {
      ...makeReplay(),
      investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
      candidate_result: {
        ...makeReplay().candidate_result,
        investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
        metrics: {
          ...makeReplay().candidate_result.metrics,
          total_return_pct: 1,
          max_drawdown_pct: -1,
          sharpe_ratio: 1,
        },
      },
      comparison: {
        total_return_diff_pct: 2.5,
        annualized_return_diff_pct: 1.5,
        benchmark_return_diff_pct: 0,
        annualized_volatility_diff_pct: -0.5,
        downside_volatility_diff_pct: -0.4,
        max_drawdown_diff_pct: 0.3,
        sharpe_diff: 0.2,
        sortino_diff: 0.2,
        excess_return_diff_pct: 1.1,
        tracking_error_diff_pct: 0.2,
        information_ratio_diff: 0.1,
        beta_diff: 0,
        correlation_diff: 0,
        total_turnover_diff_pct: 0,
        total_cost_diff: 0,
      },
    } as any

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={{ ...makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').reviewSnapshot, replay: withheldReplay }}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    const ui = within(container)

    expect(ui.getByText('Replay evidence is recorded for this workflow, but investor-performance outputs are withheld. Review replay status, lineage, window, and allowed diagnostics only.')).toBeTruthy()
    expect(ui.queryByText('Total return delta +2.50% versus baseline under the shared replay window.')).toBeNull()
  })

  it('summarizes recorded proposal state when an artifact exists', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={savedProposal.sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={savedProposal.reviewSnapshot}
        savedProposals={[savedProposal]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Recorded v1').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Recorded Apr/).length).toBeGreaterThan(0)
  })

  it('shows newest-first saved proposal index and reopens an older artifact for review only', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    const onOpenSavedProposal = vi.fn()

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        activeThesis={null}
        onOpenSavedProposal={onOpenSavedProposal}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Latest Saved Artifact').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/v2 .* AAPL/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Latest .* Apr/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Saved artifact .* Apr/).length).toBeGreaterThan(0)
    expect(screen.getAllByText('AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: 'Reopen In Workspace' }))

    expect(onOpenSavedProposal).toHaveBeenCalledWith(olderProposal.reviewSnapshotArtifactId)
    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Viewing For Review' }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Replay lineage: direct preview replay · same-weight substitution · validation not supplied').length).toBeGreaterThan(0)
  })

  it('uses authoritative openedSavedProposalArtifactId as the sole reopen authority', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        activeThesis={null}
        openedSavedProposalArtifactId={olderProposal.reviewSnapshotArtifactId}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByText(`Review snapshot artifact: ${olderProposal.reviewSnapshotArtifactId}`).length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Viewing For Review' }).length).toBeGreaterThan(0)
  })

  it('fails closed when shell reopen action receives a proposal missing authoritative reviewSnapshotArtifactId', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const malformedProposal = {
      ...makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS'),
      reviewSnapshotArtifactId: undefined,
    }

    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[malformedProposal as any, latestProposal]}
        activeThesis={null}
        onOpenSavedProposal={vi.fn()}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    fireEvent.click(screen.getAllByRole('button', { name: 'Reopen In Workspace' })[1]!)
    expect(screen.getAllByRole('button', { name: 'Reopen In Workspace' }).length).toBeGreaterThan(0)
    consoleErrorSpy.mockRestore()
  })

  it('fails closed when shell reopen state receives a proposal missing authoritative proposalCapture', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const malformedProposal = {
      ...makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS'),
      proposalCapture: undefined,
    }

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[malformedProposal as any, latestProposal]}
        activeThesis={null}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    const ui = within(container)
    expect(ui.getByTestId('saved-proposal-contract-error').textContent).toBe(
      'Unable to reopen saved proposal: saved proposal proposalCapture is missing',
    )
    expect(ui.queryByText('Latest Saved Artifact')).toBeNull()
    expect(ui.getByText('No saved proposal artifact yet.')).toBeTruthy()
  })

  it('keeps persisted construction artifact reopen deterministic when unrelated saved proposal state lacks authoritative proposalCapture', () => {
    const malformedProposal = {
      ...makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS'),
      proposalCapture: undefined,
    }

    const { container } = renderShell({
      analysis: null,
      draftSnapshot,
      workspaceSource: makePersistedConstructionArtifactWorkspaceSource(),
      persistedConstructionArtifactReview: makePersistedConstructionArtifactReview(),
      allocationBacktestResult: makeReplay(),
      savedProposals: [malformedProposal as any],
    })

    const ui = within(container)
    expect(ui.getByTestId('persisted-construction-artifact-banner')).toBeTruthy()
    expect(ui.queryByTestId('saved-proposal-contract-error')).toBeNull()
    expect(ui.queryByTestId('workspace-section-proposal')).toBeNull()
  })

  it('keeps persisted optimizer handoff reopen deterministic when unrelated saved proposal state lacks authoritative proposalCapture', () => {
    const malformedProposal = {
      ...makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS'),
      proposalCapture: undefined,
    }

    const { container } = renderShell({
      analysis: null,
      draftSnapshot,
      workspaceSource: makePersistedOptimizerHandoffWorkspaceSource(),
      persistedOptimizerHandoffReview: makePersistedOptimizerHandoffReview(),
      allocationBacktestResult: makeReplay(),
      savedProposals: [malformedProposal as any],
    })

    const ui = within(container)
    expect(ui.getByTestId('persisted-construction-artifact-banner')).toBeTruthy()
    expect(ui.queryByTestId('saved-proposal-contract-error')).toBeNull()
    expect(ui.queryByTestId('workspace-section-proposal')).toBeNull()
  })

  it('opens a read-only saved proposal comparison for exactly two selected artifacts', async () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUFS')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    latestProposal.proposalFamilyId = olderProposal.proposalFamilyId
    latestProposal.proposalCapture.lineage.proposal_family_id = olderProposal.proposalFamilyId
    latestProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = olderProposal.proposalFamilyId
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotComparisonRefs').mockResolvedValue([
      { role: 'baseline', artifact_id: olderProposal.reviewSnapshotArtifactId!, artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', consumer_kind: 'saved_hypothetical_replay_proposal' },
      { role: 'candidate', artifact_id: latestProposal.reviewSnapshotArtifactId!, artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', consumer_kind: 'saved_hypothetical_replay_proposal' },
    ])
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([latestProposal, olderProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify(makeFamilyReviewResponse(latestProposal, [latestProposal, olderProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({
      comparison_kind: 'review_snapshot_comparison',
      family_key: { workspace_id: 'workspace-1', source_draft_id: 'draft-1', source_base_node_id: 'node-1', proposal_family_id: olderProposal.proposalFamilyId, source_kind: 'hypothetical_replacement_replay' },
      baseline: {
        benchmark_symbol: 'SPY',
        replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
        replay_type: 'standard',
        candidate_construction_rule: 'same_weight_substitution_v1',
        derivation_basis: 'draft_snapshot_positions_normalized',
        source_pair: 'AAPL -> IUFS',
        replay_status: 'ok',
        investor_economics_status: { status: 'available', reason: null },
        methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions },
        analytics: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions, benchmark_symbol: 'SPY', benchmark_return_pct: 1, total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, total_cost_paid: 0 },
        diagnostics_summary: { diagnostics_available: false, top_factor_exposure_change: null, top_volatility_change: null, top_risk_contribution_change: null, top_concentration_change: null, top_stress_scenario_change: null },
      },
      candidate: {
        benchmark_symbol: 'SPY',
        replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
        replay_type: 'standard',
        candidate_construction_rule: 'same_weight_substitution_v1',
        derivation_basis: 'draft_snapshot_positions_normalized',
        source_pair: 'AAPL -> IUIT',
        replay_status: 'ok',
        investor_economics_status: { status: 'available', reason: null },
        methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions },
        analytics: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions, benchmark_symbol: 'SPY', benchmark_return_pct: 1, total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, total_cost_paid: 0 },
        diagnostics_summary: { diagnostics_available: false, top_factor_exposure_change: null, top_volatility_change: null, top_risk_contribution_change: null, top_concentration_change: null, top_stress_scenario_change: null },
      },
      provenance: 'persisted_review_snapshot_artifacts_only',
      benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
      baseline_pm_summary: {
        pm_summary_version: 1,
        role: 'baseline',
        provenance: { source: 'persisted_review_snapshot_artifact', artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', consumer_kind: 'saved_hypothetical_replay_proposal', lineage: { workspace_id: 'workspace-1', source_draft_id: 'draft-1', source_base_node_id: 'node-1', proposal_family_id: olderProposal.proposalFamilyId, proposal_id: olderProposal.id, version_number: olderProposal.versionNumber, source_kind: 'hypothetical_replacement_replay' }, proposal_source: olderProposal.reviewSnapshot.proposal.proposal_source, replay_provenance: olderProposal.reviewSnapshot.replay_provenance },
        truth_labels: { proposal_truth: 'review_only_hypothetical_proposal', portfolio_truth: 'draft_snapshot_not_applied', analytics_truth: 'hypothetical_replay_analytics_only', review_scope: 'proposal_review_context_only' },
        replay_type: 'standard', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null },
        review_basis: { benchmark_separation: 'explicit_per_snapshot_benchmark_fields', benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, derivation_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
        methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance },
        assumptions: makeReplay().candidate_result.assumptions,
        analytics_summary: { candidate_analytics: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions, benchmark_symbol: 'SPY', benchmark_return_pct: 1, total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, total_cost_paid: 0 }, baseline_analytics: null, analytics_comparison: null },
        diagnostics_summary: { diagnostics_available: false, top_factor_exposure_change: null, top_volatility_change: null, top_risk_contribution_change: null, top_concentration_change: null, top_stress_scenario_change: null },
      },
      candidate_pm_summary: {
        pm_summary_version: 1,
        role: 'candidate',
        provenance: { source: 'persisted_review_snapshot_artifact', artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', consumer_kind: 'saved_hypothetical_replay_proposal', lineage: { workspace_id: 'workspace-1', source_draft_id: 'draft-1', source_base_node_id: 'node-1', proposal_family_id: latestProposal.proposalFamilyId, proposal_id: latestProposal.id, version_number: latestProposal.versionNumber, source_kind: 'hypothetical_replacement_replay' }, proposal_source: latestProposal.reviewSnapshot.proposal.proposal_source, replay_provenance: latestProposal.reviewSnapshot.replay_provenance },
        truth_labels: { proposal_truth: 'review_only_hypothetical_proposal', portfolio_truth: 'draft_snapshot_not_applied', analytics_truth: 'hypothetical_replay_analytics_only', review_scope: 'proposal_review_context_only' },
        replay_type: 'standard', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null },
        review_basis: { benchmark_separation: 'explicit_per_snapshot_benchmark_fields', benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, derivation_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
        methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance },
        assumptions: makeReplay().candidate_result.assumptions,
        analytics_summary: { candidate_analytics: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions, benchmark_symbol: 'SPY', benchmark_return_pct: 1, total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, total_cost_paid: 0 }, baseline_analytics: null, analytics_comparison: null },
        diagnostics_summary: { diagnostics_available: false, top_factor_exposure_change: null, top_volatility_change: null, top_risk_contribution_change: null, top_concentration_change: null, top_stress_scenario_change: null },
      },
      analytics_comparison: null,
      methodology: { baseline_methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, candidate_methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, methodology_consistent: true, assumptions_consistent: true },
      assumptions: { baseline_assumptions: makeReplay().candidate_result.assumptions, candidate_assumptions: makeReplay().candidate_result.assumptions, assumptions_consistent: true },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    const ui = within(container)

    clickCompareForIn(container, 'proposal-2')
    expect(textContentOfIn(container, 'saved-proposal-comparison-status')).toContain('Choose one more saved proposal to open the comparison surface.')
    clickCompareForIn(container, 'proposal-1')

    await screen.findByText('Comparison Checks')
    expect(latestByTestIdIn(container, 'saved-proposal-comparison-view')).toBeTruthy()
    expect(latestByTestIdIn(container, 'saved-proposal-family-inbox')).toBeTruthy()
    expect(latestByTestIdIn(container, 'saved-proposal-family-review')).toBeTruthy()
    expect(ui.getByText('2 of 2 selected')).toBeTruthy()
    expect(ui.getByText('Comparison Checks')).toBeTruthy()
    expect(ui.getByText(/Provenance: persisted_review_snapshot_artifacts_only/)).toBeTruthy()
    expect(ui.getByText('Saved Proposal Family Inbox')).toBeTruthy()
    expect(ui.getByText('Proposal Family PM Review')).toBeTruthy()
    expect(ui.getByText(new RegExp(`Family: ${olderProposal.proposalFamilyId}`))).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Swap sides' })).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Open full proposal v2' })).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Open full proposal v1' })).toBeTruthy()
  })

  it('keeps saved proposal comparison on provenance and replay metadata instead of investor-performance rows', async () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUFS')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    latestProposal.proposalFamilyId = olderProposal.proposalFamilyId
    latestProposal.proposalCapture.lineage.proposal_family_id = olderProposal.proposalFamilyId
    latestProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = olderProposal.proposalFamilyId
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotComparisonRefs').mockResolvedValue([
      { role: 'baseline', artifact_id: olderProposal.reviewSnapshotArtifactId!, artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', consumer_kind: 'saved_hypothetical_replay_proposal' },
      { role: 'candidate', artifact_id: latestProposal.reviewSnapshotArtifactId!, artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', consumer_kind: 'saved_hypothetical_replay_proposal' },
    ])
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([latestProposal, olderProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify(makeFamilyReviewResponse(latestProposal, [latestProposal, olderProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({
      comparison_kind: 'review_snapshot_comparison',
      family_key: { workspace_id: 'workspace-1', source_draft_id: 'draft-1', source_base_node_id: 'node-1', proposal_family_id: olderProposal.proposalFamilyId, source_kind: 'hypothetical_replacement_replay' },
      baseline: {
        benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, replay_type: 'standard', candidate_construction_rule: 'same_weight_substitution_v1', derivation_basis: 'draft_snapshot_positions_normalized', source_pair: 'AAPL -> IUFS', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, analytics: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions, benchmark_symbol: 'SPY', benchmark_return_pct: 1, total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, total_cost_paid: 0 }, diagnostics_summary: { diagnostics_available: false, top_factor_exposure_change: null, top_volatility_change: null, top_risk_contribution_change: null, top_concentration_change: null, top_stress_scenario_change: null },
      },
      candidate: {
        benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, replay_type: 'standard', candidate_construction_rule: 'same_weight_substitution_v1', derivation_basis: 'draft_snapshot_positions_normalized', source_pair: 'AAPL -> IUIT', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, analytics: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions, benchmark_symbol: 'SPY', benchmark_return_pct: 1, total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, total_cost_paid: 0 }, diagnostics_summary: { diagnostics_available: false, top_factor_exposure_change: null, top_volatility_change: null, top_risk_contribution_change: null, top_concentration_change: null, top_stress_scenario_change: null },
      },
      provenance: 'persisted_review_snapshot_artifacts_only', benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
      baseline_pm_summary: { pm_summary_version: 1, role: 'baseline', provenance: { source: 'persisted_review_snapshot_artifact', artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', consumer_kind: 'saved_hypothetical_replay_proposal', lineage: { workspace_id: 'workspace-1', source_draft_id: 'draft-1', source_base_node_id: 'node-1', proposal_family_id: olderProposal.proposalFamilyId, proposal_id: olderProposal.id, version_number: olderProposal.versionNumber, source_kind: 'hypothetical_replacement_replay' }, proposal_source: olderProposal.reviewSnapshot.proposal.proposal_source, replay_provenance: olderProposal.reviewSnapshot.replay_provenance }, truth_labels: { proposal_truth: 'review_only_hypothetical_proposal', portfolio_truth: 'draft_snapshot_not_applied', analytics_truth: 'hypothetical_replay_analytics_only', review_scope: 'proposal_review_context_only' }, replay_type: 'standard', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, review_basis: { benchmark_separation: 'explicit_per_snapshot_benchmark_fields', benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, derivation_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance }, assumptions: makeReplay().candidate_result.assumptions, analytics_summary: { candidate_analytics: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions, benchmark_symbol: 'SPY', benchmark_return_pct: 1, total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, total_cost_paid: 0 }, baseline_analytics: null, analytics_comparison: null }, diagnostics_summary: { diagnostics_available: false, top_factor_exposure_change: null, top_volatility_change: null, top_risk_contribution_change: null, top_concentration_change: null, top_stress_scenario_change: null } },
      candidate_pm_summary: { pm_summary_version: 1, role: 'candidate', provenance: { source: 'persisted_review_snapshot_artifact', artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', consumer_kind: 'saved_hypothetical_replay_proposal', lineage: { workspace_id: 'workspace-1', source_draft_id: 'draft-1', source_base_node_id: 'node-1', proposal_family_id: latestProposal.proposalFamilyId, proposal_id: latestProposal.id, version_number: latestProposal.versionNumber, source_kind: 'hypothetical_replacement_replay' }, proposal_source: latestProposal.reviewSnapshot.proposal.proposal_source, replay_provenance: latestProposal.reviewSnapshot.replay_provenance }, truth_labels: { proposal_truth: 'review_only_hypothetical_proposal', portfolio_truth: 'draft_snapshot_not_applied', analytics_truth: 'hypothetical_replay_analytics_only', review_scope: 'proposal_review_context_only' }, replay_type: 'standard', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, review_basis: { benchmark_separation: 'explicit_per_snapshot_benchmark_fields', benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, derivation_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance }, assumptions: makeReplay().candidate_result.assumptions, analytics_summary: { candidate_analytics: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions, benchmark_symbol: 'SPY', benchmark_return_pct: 1, total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, total_cost_paid: 0 }, baseline_analytics: null, analytics_comparison: null }, diagnostics_summary: { diagnostics_available: false, top_factor_exposure_change: null, top_volatility_change: null, top_risk_contribution_change: null, top_concentration_change: null, top_stress_scenario_change: null } },
      analytics_comparison: null, methodology: { baseline_methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, candidate_methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, methodology_consistent: true, assumptions_consistent: true }, assumptions: { baseline_assumptions: makeReplay().candidate_result.assumptions, candidate_assumptions: makeReplay().candidate_result.assumptions, assumptions_consistent: true },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    clickCompareForIn(container, 'proposal-2')
    clickCompareForIn(container, 'proposal-1')

    await screen.findByText('Replay status')
    expect(within(container).getByText('Comparison Checks')).toBeTruthy()
    expect(within(container).getByText('Replay status')).toBeTruthy()
    expect(within(container).getByText(/Provenance: persisted_review_snapshot_artifacts_only/)).toBeTruthy()
    expect(within(container).getByText(/Methodology consistent: yes/)).toBeTruthy()
    expect(within(container).queryByText('Candidate total return')).toBeNull()
    expect(within(container).queryByText('Max drawdown')).toBeNull()
    expect(within(container).queryByText('Sharpe ratio')).toBeNull()
  })

  it('shows comparison ineligible state when fewer than two saved proposals exist', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={savedProposal.sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation()}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={savedProposal.reviewSnapshot}
        savedProposals={[savedProposal]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(textContentOfIn(container, 'saved-proposal-comparison-status')).toContain('Comparison is unavailable until at least two saved proposal artifacts exist.')
    expect(within(container).queryByTestId('saved-proposal-comparison-view')).toBeNull()
  })

  it('swaps sides and opens a full proposal from comparison mode', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUFS')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    latestProposal.proposalFamilyId = olderProposal.proposalFamilyId
    latestProposal.proposalCapture.lineage.proposal_family_id = olderProposal.proposalFamilyId
    latestProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = olderProposal.proposalFamilyId
    const onOpenSavedProposal = vi.fn()
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([latestProposal, olderProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify(makeFamilyReviewResponse(latestProposal, [latestProposal, olderProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ detail: 'Unable to compare saved review snapshots' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal]}
        activeThesis={null}
        onOpenSavedProposal={onOpenSavedProposal}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    const ui = within(container)

    clickCompareForIn(container, 'proposal-2')
    clickCompareForIn(container, 'proposal-1')
    const comparisonView = latestByTestIdIn(container, 'saved-proposal-comparison-view')
    expect(comparisonView).toBeTruthy()
    expect(within(comparisonView).getAllByText('v2 · AAPL -> IUFS').length).toBeGreaterThan(0)

    fireEvent.click(ui.getByRole('button', { name: 'Swap sides' }))
    expect(within(latestByTestIdIn(container, 'saved-proposal-comparison-view')).getAllByText('v1 · AAPL -> IUFS').length).toBeGreaterThan(0)

    fireEvent.click(ui.getByRole('button', { name: 'Open full proposal v2' }))
    expect(onOpenSavedProposal).toHaveBeenCalledWith(latestProposal.reviewSnapshotArtifactId)
  })

  it('renders family review rejection when family review artifact payload is malformed', async () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([latestProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ review_kind: 'review_snapshot_family_review', provenance: 'persisted_review_snapshot_artifacts_only' }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[latestProposal]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    await screen.findAllByText('Saved proposal comparison')
    expect(textContentOfIn(container, 'saved-proposal-comparison-status')).toContain('Review snapshot family review response compare_selection_policy is invalid')
  })

  it('renders family inbox newest-first and opens PM review from the authoritative latest row', async () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUFS')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    const separateFamily = makeSavedProposal(3, '2026-04-15T00:00:00Z', 'IUIT')
    latestProposal.proposalFamilyId = olderProposal.proposalFamilyId
    latestProposal.proposalCapture.lineage.proposal_family_id = olderProposal.proposalFamilyId
    latestProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = olderProposal.proposalFamilyId
    const onOpenSavedProposal = vi.fn()

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([olderProposal, latestProposal, separateFamily])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify(makeFamilyReviewResponse(latestProposal, [latestProposal, olderProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ detail: 'Unable to compare saved review snapshots' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[olderProposal, latestProposal, separateFamily]}
        activeThesis={null}
        onOpenSavedProposal={onOpenSavedProposal}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    await screen.findAllByTestId('saved-proposal-family-inbox')
    const inbox = latestByTestIdIn(container, 'saved-proposal-family-inbox')
    const rows = within(inbox).getAllByTestId(/saved-proposal-family-inbox-row-/)
    expect(rows).toHaveLength(2)
    expect(rows[0]?.textContent).toContain(latestProposal.proposalFamilyId)
    expect(rows[0]?.textContent).toContain('2 siblings')
    expect(rows[1]?.textContent).toContain(separateFamily.proposalFamilyId)
    fireEvent.click(within(rows[0]!).getByRole('button', { name: 'Open PM Review' }))
    expect(onOpenSavedProposal).toHaveBeenCalledWith(latestProposal.reviewSnapshotArtifactId)
  })

  it('refuses family inbox rows that are not indexed by saved proposals', async () => {
    const proposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    const inboxPayload = JSON.parse(JSON.stringify(makeFamilyInboxResponse([proposal])))
    inboxPayload.rows[0]!.latest_identity.artifact_id = 'review_snapshot_missing'
    inboxPayload.rows[0]!.proposal_capture.open_handoff.artifact_id = 'review_snapshot_missing'

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (value) => value.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(inboxPayload), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify(makeFamilyReviewResponse(proposal, [proposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ detail: 'Unable to compare saved review snapshots' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[proposal]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    await screen.findAllByText('Saved proposal comparison')
    expect(textContentOfIn(container, 'saved-proposal-comparison-status')).toContain('Saved proposal family inbox latest artifact is not indexed by any saved proposal')
  })

  it('keeps candidate idea actions inside the shell and promotes to replacement intent', () => {
    const onCreateReplacementIntent = vi.fn()

    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={{ workspaceId: 'workspace-1', draftId: 'draft-1', baseNodeId: 'node-1', seed: { kind: 'etf_replacement_candidate', source: 'etf_ranking', seededAt: '2026-04-15T00:00:00Z', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', candidateRank: 1, peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, rankingId: 'etf_ranking_engine_v1', methodologyId: 'etf_ranking_methodology_v1', rankingBasisDate: '2026-04-15', confidence: 'medium', holdingsSupport: 'mixed', requestUniverse: ['AAPL', 'IUFS'], evaluatedUniverse: ['IUFS'], warningCount: 1, excludedSymbolsCount: 0 } }}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={null}
        formedCandidateArtifact={null}
        constructedCandidateArtifact={null}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onCreateReplacementIntent={onCreateReplacementIntent}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Promote to Replacement Intent' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create Intent' }))
    expect(onCreateReplacementIntent).toHaveBeenCalledTimes(1)
  })

  it('marks construction stale when the selected rule differs from the saved artifact rule', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={null}
        selectedConstructionRuleId="fixed_split_50_50_substitution_v2"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Stale').length).toBeGreaterThan(0)
    expect(screen.getByText('The existing construction artifact was built with same_weight_substitution_v1 and must be rerun for fixed_split_50_50_substitution_v2.')).toBeTruthy()
    expect(screen.getAllByText('fixed_split_50_50_substitution_v2').length).toBeGreaterThan(0)
  })

  it('shows blocked construction constraints before replay can run', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation('blocked')}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getAllByText('Construction Constraints').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getByText('Constraint validation blocked replay with 1 hard-block result.')).toBeTruthy()
    expect(screen.getByText('Hypothetical replay remains unavailable until the current constructed candidate passes construction constraints.')).toBeTruthy()
  })

  it('gates candidate and proposal sections in persisted construction artifact review mode', () => {
    const { container } = renderShell({
      analysis: null,
      draftSnapshot: {
        ...draftSnapshot,
        importedMeta: { ...draftSnapshot.importedMeta, importer: null, sourceFileNames: ['artifact-123'] },
      },
      workspaceSource: {
        ...makePersistedConstructionArtifactWorkspaceSource(),
      },
      persistedConstructionArtifactReview: makePersistedConstructionArtifactReview(),
      allocationBacktestResult: makeReplay(),
    })

    const ui = within(container)
    expect(ui.getByTestId('persisted-construction-artifact-banner')).toBeTruthy()
    expect(ui.getByText('Artifact Review Mode')).toBeTruthy()
    expect(ui.queryByTestId('workspace-section-candidate')).toBeNull()
    expect(ui.queryByTestId('workspace-section-proposal')).toBeNull()
    expect(ui.getAllByText('Recorded').length).toBeGreaterThan(0)
    expect(ui.getByText('Artifact review basis is available.')).toBeTruthy()
    expect(ui.getAllByText('Review Basis').length).toBeGreaterThan(0)
    expect(ui.getByText('This workspace reopens a persisted construction artifact as a desktop-only artifact review basis while keeping replay review surfaces intact.')).toBeTruthy()
  })

  it('gates candidate and proposal sections in persisted optimizer handoff review mode', () => {
    const { container } = renderShell({
      analysis: null,
      draftSnapshot: {
        ...draftSnapshot,
        importedMeta: { ...draftSnapshot.importedMeta, importer: null, sourceFileNames: ['optimizer_handoff_123'] },
      },
      workspaceSource: makePersistedOptimizerHandoffWorkspaceSource(),
      persistedOptimizerHandoffReview: makePersistedOptimizerHandoffReview(),
      allocationBacktestResult: makeReplay(),
    })

    const ui = within(container)
    expect(ui.getByTestId('persisted-construction-artifact-banner')).toBeTruthy()
    expect(ui.getByText('This workspace reopens a hypothetical artifact-backed optimizer review by persisted handoff reference while keeping replay review surfaces intact.')).toBeTruthy()
    expect(ui.getByText('Review basis: optimizer_handoff_123')).toBeTruthy()
    expect(ui.queryByTestId('workspace-section-candidate')).toBeNull()
    expect(ui.queryByTestId('workspace-section-proposal')).toBeNull()
    expect(ui.getByText('Candidate review comes from the persisted optimizer handoff reopened by handoff reference.')).toBeTruthy()
  })

  it('shows optimizer handoff overview basis from handoffReference', () => {
    const { container } = renderShell({
      analysis: null,
      draftSnapshot,
      workspaceSource: makePersistedOptimizerHandoffWorkspaceSource(),
      persistedOptimizerHandoffReview: makePersistedOptimizerHandoffReview(),
    })

    const ui = within(container)
    expect(ui.getByText('Optimizer handoff reference review basis')).toBeTruthy()
    expect(ui.getAllByText('optimizer_handoff_123').length).toBeGreaterThan(0)
  })

  it('shortens rejected constraint copy in the decision summary', () => {
    render(
      <PortfolioImprovementWorkspaceShell
        analysis={analysis}
        draftSnapshot={draftSnapshot}
        candidateImprovementDraft={null}
        intentBoundSeededEtfReplacementRankingDraft={null}
        replacementIntentDraft={makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS').sourceIntent}
        formedCandidateArtifact={makeFormedCandidate()}
        constructedCandidateArtifact={makeConstructedCandidate()}
        constructionConstraintValidationArtifact={makeConstraintValidation('rejected')}
        selectedConstructionRuleId="same_weight_substitution_v1"
        allocationBacktestResult={null}
        hypotheticalReplayResult={null}
        savedProposals={[]}
        activeThesis={null}
        onOpenSavedProposal={noOp}
        openedSavedProposalArtifactId={null}
        onPromoteProposalToThesis={noOp}
        onClearActiveThesis={noOp}
        onSaveProposal={() => {}}
        onHypotheticalReplayResult={() => {}}
        onFormedCandidateArtifact={() => {}}
        onConstructedCandidateArtifact={() => {}}
        onConstructionConstraintValidationArtifact={() => {}}
        onSelectedConstructionRuleChange={() => {}}
      />,
    )

    expect(screen.getByText('Constraint validation rejected replay input: constructed candidate could not be evaluated safely')).toBeTruthy()
  })

  it('shows active thesis state and marks the promoted proposal row', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

    const { container } = renderShell({
      savedProposals: [savedProposal],
      activeThesis: makeActiveThesis(1, 'IUFS'),
    })

    const ui = within(container)

    expect(ui.getAllByText('Active Thesis').length).toBeGreaterThan(0)
    expect(ui.getAllByText('v1 · AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(ui.getByTestId('saved-proposal-status-proposal-1').textContent).toContain('active thesis')
    expect(ui.getByTestId('saved-proposal-status-proposal-1').textContent).toContain('active thesis')
  })

  it('renders active thesis PM summary and same-family delta from persisted artifact-backed routes only', async () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUIT')
    latestProposal.proposalFamilyId = olderProposal.proposalFamilyId
    latestProposal.proposalCapture.lineage.proposal_family_id = olderProposal.proposalFamilyId
    latestProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = olderProposal.proposalFamilyId

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([olderProposal, latestProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/open')) {
        return new Response(JSON.stringify({
          handoff: latestProposal.proposalCapture.open_handoff,
          artifact: {
            identity: {
              artifact_id: latestProposal.reviewSnapshotArtifactId,
              artifact_kind: 'portfolio_review_snapshot',
              schema_version: 'review_snapshot_artifact_v1',
              fingerprint: 'fingerprint-2',
              consumer_kind: 'saved_hypothetical_replay_proposal',
            },
            lineage: latestProposal.proposalCapture.lineage,
            review_basis: {
              benchmark_symbol: 'SPY',
              start_date: '2024-01-01',
              end_date: '2024-12-31',
              rebalance_frequency: 'monthly',
              commission_bps: 0,
              slippage_bps: 0,
              derivation_basis: 'draft_snapshot_positions_normalized',
              candidate_construction_rule: 'same_weight_substitution_v1',
              replay_provenance: latestProposal.reviewSnapshot.replay_provenance,
            },
            truth_labels: latestProposal.reviewSnapshotPMSummary.truth_labels,
            compact_summary: {
              replay_type: 'standard',
              replay_status: 'ok',
              investor_economics_status: { status: 'available', reason: null },
              candidate_analytics: latestProposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics,
              baseline_analytics: latestProposal.reviewSnapshotPMSummary.analytics_summary.baseline_analytics,
              analytics_comparison: latestProposal.reviewSnapshotPMSummary.analytics_summary.analytics_comparison,
              diagnostics_summary: latestProposal.reviewSnapshotPMSummary.diagnostics_summary,
            },
            proposal_capture: latestProposal.proposalCapture,
            pm_summary: latestProposal.reviewSnapshotPMSummary,
            source_payload: {
              replay_type: 'standard',
              replay: latestProposal.reviewSnapshot,
              overlay_replay: null,
            },
          },
          pm_summary: latestProposal.reviewSnapshotPMSummary,
          replay_payload: {
            replay_type: 'standard',
            replay: latestProposal.reviewSnapshot,
            overlay_replay: null,
          },
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify(makeFamilyReviewResponse(latestProposal, [latestProposal, olderProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({
        comparison_kind: 'review_snapshot_comparison',
        family_key: { workspace_id: 'workspace-1', source_draft_id: 'draft-1', source_base_node_id: 'node-1', proposal_family_id: olderProposal.proposalFamilyId, source_kind: 'hypothetical_replacement_replay' },
        baseline: { benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, replay_type: 'standard', candidate_construction_rule: 'same_weight_substitution_v1', derivation_basis: 'draft_snapshot_positions_normalized', source_pair: 'AAPL -> IUIT', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, analytics: latestProposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics, diagnostics_summary: latestProposal.reviewSnapshotPMSummary.diagnostics_summary },
        candidate: { benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, replay_type: 'standard', candidate_construction_rule: 'same_weight_substitution_v1', derivation_basis: 'draft_snapshot_positions_normalized', source_pair: 'AAPL -> IUIT', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, analytics: latestProposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics, diagnostics_summary: latestProposal.reviewSnapshotPMSummary.diagnostics_summary },
        provenance: 'persisted_review_snapshot_artifacts_only',
        benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
        baseline_pm_summary: { ...olderProposal.reviewSnapshotPMSummary, role: 'baseline' },
        candidate_pm_summary: { ...latestProposal.reviewSnapshotPMSummary, role: 'candidate' },
        analytics_comparison: null,
        methodology: { baseline_methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, candidate_methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, methodology_consistent: true, assumptions_consistent: true },
        assumptions: { baseline_assumptions: makeReplay().candidate_result.assumptions, candidate_assumptions: makeReplay().candidate_result.assumptions, assumptions_consistent: true },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = renderShell({
      savedProposals: [olderProposal, latestProposal],
      activeThesis: {
        workspaceId: 'workspace-1',
        promotedAt: '2026-04-17T12:00:00Z',
        sourceProposalId: latestProposal.id,
        thesisProposal: latestProposal,
      },
    })

    await within(container).findAllByTestId('active-thesis-artifact-review')
    expect(textContentOfIn(container, 'active-thesis-pm-summary-status')).toContain('Role: saved_proposal')
    expect(textContentOfIn(container, 'active-thesis-pm-summary-status')).toContain(`artifact: ${latestProposal.reviewSnapshotArtifactId}`)
    expect(textContentOfIn(container, 'active-thesis-delta-readout')).toContain('role baseline')
    expect(textContentOfIn(container, 'active-thesis-delta-readout')).toContain('role candidate')
    expect(textContentOfIn(container, 'active-thesis-delta-readout')).toContain(`proposal ${latestProposal.id}`)
  })

  it('renders the active thesis cross-family PM review queue in the desktop workspace shell', async () => {
    const activeProposal = makeSavedProposal(3, '2026-04-18T00:00:00Z', 'IUIT')
    const siblingProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const queuedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    activeProposal.proposalFamilyId = siblingProposal.proposalFamilyId
    activeProposal.proposalCapture.lineage.proposal_family_id = siblingProposal.proposalFamilyId
    activeProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = siblingProposal.proposalFamilyId
    const onOpenSavedProposal = vi.fn()

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([queuedProposal, siblingProposal, activeProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/active-thesis-cross-family-queue')) {
        return new Response(JSON.stringify(makeActiveThesisCrossFamilyQueueResponse(activeProposal, [queuedProposal, siblingProposal, activeProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/open')) {
        return new Response(JSON.stringify({
          handoff: activeProposal.proposalCapture.open_handoff,
          artifact: {
            identity: { artifact_id: activeProposal.reviewSnapshotArtifactId, artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', fingerprint: 'fingerprint-3', consumer_kind: 'saved_hypothetical_replay_proposal' },
            lineage: activeProposal.proposalCapture.lineage,
            review_basis: { benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, derivation_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1', replay_provenance: activeProposal.reviewSnapshot.replay_provenance },
            truth_labels: activeProposal.reviewSnapshotPMSummary.truth_labels,
            compact_summary: { replay_type: 'standard', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, candidate_analytics: activeProposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics, baseline_analytics: activeProposal.reviewSnapshotPMSummary.analytics_summary.baseline_analytics, analytics_comparison: activeProposal.reviewSnapshotPMSummary.analytics_summary.analytics_comparison, diagnostics_summary: activeProposal.reviewSnapshotPMSummary.diagnostics_summary },
            proposal_capture: activeProposal.proposalCapture,
            pm_summary: activeProposal.reviewSnapshotPMSummary,
            source_payload: { replay_type: 'standard', replay: activeProposal.reviewSnapshot, overlay_replay: null },
          },
          pm_summary: activeProposal.reviewSnapshotPMSummary,
          replay_payload: { replay_type: 'standard', replay: activeProposal.reviewSnapshot, overlay_replay: null },
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify(makeFamilyReviewResponse(activeProposal, [activeProposal, siblingProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({
        comparison_kind: 'review_snapshot_comparison',
        family_key: { workspace_id: 'workspace-1', source_draft_id: 'draft-1', source_base_node_id: 'node-1', proposal_family_id: siblingProposal.proposalFamilyId, source_kind: 'hypothetical_replacement_replay' },
        baseline: { benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, replay_type: 'standard', candidate_construction_rule: 'same_weight_substitution_v1', derivation_basis: 'draft_snapshot_positions_normalized', source_pair: 'AAPL -> IUIT', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, analytics: activeProposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics, diagnostics_summary: activeProposal.reviewSnapshotPMSummary.diagnostics_summary },
        candidate: { benchmark_symbol: 'SPY', replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' }, replay_type: 'standard', candidate_construction_rule: 'same_weight_substitution_v1', derivation_basis: 'draft_snapshot_positions_normalized', source_pair: 'AAPL -> IUIT', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, analytics: activeProposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics, diagnostics_summary: activeProposal.reviewSnapshotPMSummary.diagnostics_summary },
        provenance: 'persisted_review_snapshot_artifacts_only',
        benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
        baseline_pm_summary: { ...siblingProposal.reviewSnapshotPMSummary, role: 'baseline' },
        candidate_pm_summary: { ...activeProposal.reviewSnapshotPMSummary, role: 'candidate' },
        analytics_comparison: null,
        methodology: { baseline_methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, candidate_methodology: { methodology: 'm', methodology_provenance: makeReplay().methodology_provenance, assumptions: makeReplay().candidate_result.assumptions }, methodology_consistent: true, assumptions_consistent: true },
        assumptions: { baseline_assumptions: makeReplay().candidate_result.assumptions, candidate_assumptions: makeReplay().candidate_result.assumptions, assumptions_consistent: true },
      }), { status: 200, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = renderShell({
      savedProposals: [queuedProposal, siblingProposal, activeProposal],
      activeThesis: {
        workspaceId: 'workspace-1',
        promotedAt: '2026-04-18T12:00:00Z',
        sourceProposalId: activeProposal.id,
        thesisProposal: activeProposal,
      },
      onOpenSavedProposal,
    })

    await within(container).findAllByTestId('active-thesis-cross-family-queue')
    expect(textContentOfIn(container, 'active-thesis-cross-family-queue-status')).toContain('Queued families: 1')
    const queue = latestByTestIdIn(container, 'active-thesis-cross-family-queue')
    expect(queue.textContent).toContain(queuedProposal.proposalFamilyId)
    expect(queue.textContent).toContain(`investor economics ${queuedProposal.reviewSnapshotPMSummary.investor_economics_status.status}`)
    fireEvent.click(within(queue).getByRole('button', { name: 'Open PM Review' }))
    expect(onOpenSavedProposal).toHaveBeenCalledWith(queuedProposal.reviewSnapshotArtifactId)
  })

  it('shows active thesis cross-family PM review queue loading state before rows arrive', () => {
    const activeProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const siblingProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUIT')
    activeProposal.proposalFamilyId = siblingProposal.proposalFamilyId
    activeProposal.proposalCapture.lineage.proposal_family_id = siblingProposal.proposalFamilyId
    activeProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = siblingProposal.proposalFamilyId

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/active-thesis-cross-family-queue')) {
        return new Promise<Response>(() => {})
      }
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([siblingProposal, activeProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/open')) {
        return new Promise<Response>(() => {})
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Promise<Response>(() => {})
      }
      return new Promise<Response>(() => {})
    })

    const { container } = renderShell({
      savedProposals: [siblingProposal, activeProposal],
      activeThesis: {
        workspaceId: 'workspace-1',
        promotedAt: '2026-04-17T12:00:00Z',
        sourceProposalId: activeProposal.id,
        thesisProposal: activeProposal,
      },
    })

    expect(textContentOfIn(container, 'active-thesis-cross-family-queue-status')).toContain('Loading active thesis cross-family PM review queue from persisted discovery.')
  })

  it('shows active thesis cross-family PM review queue empty state when no distinct families exist', async () => {
    const activeProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const siblingProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUIT')
    activeProposal.proposalFamilyId = siblingProposal.proposalFamilyId
    activeProposal.proposalCapture.lineage.proposal_family_id = siblingProposal.proposalFamilyId
    activeProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = siblingProposal.proposalFamilyId

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([siblingProposal, activeProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/active-thesis-cross-family-queue')) {
        return new Response(JSON.stringify(makeActiveThesisCrossFamilyQueueResponse(activeProposal, [siblingProposal, activeProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/open')) {
        return new Response(JSON.stringify({
          handoff: activeProposal.proposalCapture.open_handoff,
          artifact: {
            identity: { artifact_id: activeProposal.reviewSnapshotArtifactId, artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', fingerprint: 'fingerprint-2', consumer_kind: 'saved_hypothetical_replay_proposal' },
            lineage: activeProposal.proposalCapture.lineage,
            review_basis: { benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, derivation_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1', replay_provenance: activeProposal.reviewSnapshot.replay_provenance },
            truth_labels: activeProposal.reviewSnapshotPMSummary.truth_labels,
            compact_summary: { replay_type: 'standard', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, candidate_analytics: activeProposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics, baseline_analytics: activeProposal.reviewSnapshotPMSummary.analytics_summary.baseline_analytics, analytics_comparison: activeProposal.reviewSnapshotPMSummary.analytics_summary.analytics_comparison, diagnostics_summary: activeProposal.reviewSnapshotPMSummary.diagnostics_summary },
            proposal_capture: activeProposal.proposalCapture,
            pm_summary: activeProposal.reviewSnapshotPMSummary,
            source_payload: { replay_type: 'standard', replay: activeProposal.reviewSnapshot, overlay_replay: null },
          },
          pm_summary: activeProposal.reviewSnapshotPMSummary,
          replay_payload: { replay_type: 'standard', replay: activeProposal.reviewSnapshot, overlay_replay: null },
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify(makeFamilyReviewResponse(activeProposal, [activeProposal, siblingProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ detail: 'Unable to compare saved review snapshots' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = renderShell({
      savedProposals: [siblingProposal, activeProposal],
      activeThesis: {
        workspaceId: 'workspace-1',
        promotedAt: '2026-04-17T12:00:00Z',
        sourceProposalId: activeProposal.id,
        thesisProposal: activeProposal,
      },
    })

    await within(container).findAllByTestId('active-thesis-cross-family-queue-status')
    expect(textContentOfIn(container, 'active-thesis-cross-family-queue-status')).toContain('Queued families: 0')
    expect(textContentOfIn(container, 'active-thesis-cross-family-queue-status')).toContain('No persisted cross-family PM review rows are available for the active thesis lineage.')
    expect(within(container).queryByTestId('active-thesis-cross-family-queue')).toBeNull()
  })

  it('shows active thesis cross-family PM review queue error state when the route fails', async () => {
    const activeProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const siblingProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUIT')
    activeProposal.proposalFamilyId = siblingProposal.proposalFamilyId
    activeProposal.proposalCapture.lineage.proposal_family_id = siblingProposal.proposalFamilyId
    activeProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = siblingProposal.proposalFamilyId

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/active-thesis-cross-family-queue')) {
        return new Response(JSON.stringify({ detail: 'Unable to load active thesis cross-family PM review queue' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([siblingProposal, activeProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/open')) {
        return new Response(JSON.stringify({ detail: 'Unable to load active thesis PM summary' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify({ detail: 'Unable to load active thesis same-family review' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ detail: 'Unable to compare saved review snapshots' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = renderShell({
      savedProposals: [siblingProposal, activeProposal],
      activeThesis: {
        workspaceId: 'workspace-1',
        promotedAt: '2026-04-17T12:00:00Z',
        sourceProposalId: activeProposal.id,
        thesisProposal: activeProposal,
      },
    })

    await within(container).findAllByTestId('active-thesis-cross-family-queue-status')
    expect(textContentOfIn(container, 'active-thesis-cross-family-queue-status')).toContain('Unable to load active thesis cross-family PM review queue')
  })

  it('fails closed when active thesis cross-family queue rows are not indexed by saved proposals', async () => {
    const activeProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const siblingProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUIT')
    const queuedProposal = makeSavedProposal(3, '2026-04-15T00:00:00Z', 'IUFS')
    activeProposal.proposalFamilyId = siblingProposal.proposalFamilyId
    activeProposal.proposalCapture.lineage.proposal_family_id = siblingProposal.proposalFamilyId
    activeProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = siblingProposal.proposalFamilyId
    const queuePayload = makeActiveThesisCrossFamilyQueueResponse(activeProposal, [queuedProposal, siblingProposal, activeProposal])
    queuePayload.rows[0]!.latest_identity.artifact_id = 'review_snapshot_missing'

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([queuedProposal, siblingProposal, activeProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/active-thesis-cross-family-queue')) {
        return new Response(JSON.stringify(queuePayload), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/open')) {
        return new Response(JSON.stringify({ detail: 'Unable to load active thesis PM summary' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        return new Response(JSON.stringify({ detail: 'Unable to load active thesis same-family review' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ detail: 'Unable to compare saved review snapshots' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = renderShell({
      savedProposals: [siblingProposal, activeProposal],
      activeThesis: {
        workspaceId: 'workspace-1',
        promotedAt: '2026-04-17T12:00:00Z',
        sourceProposalId: activeProposal.id,
        thesisProposal: activeProposal,
      },
    })

    await within(container).findAllByTestId('active-thesis-cross-family-queue-status')
    expect(textContentOfIn(container, 'active-thesis-cross-family-queue-status')).toContain('Active thesis cross-family PM review queue latest artifact is not indexed by any saved proposal')
  })

  it('fails closed when active thesis same-family sibling selection is ambiguous', async () => {
    const activeProposal = makeSavedProposal(3, '2026-04-18T00:00:00Z', 'IUIT')
    const siblingOne = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const siblingTwo = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUIT')
    activeProposal.proposalFamilyId = siblingOne.proposalFamilyId
    siblingTwo.proposalFamilyId = siblingOne.proposalFamilyId
    activeProposal.proposalCapture.lineage.proposal_family_id = siblingOne.proposalFamilyId
    siblingTwo.proposalCapture.lineage.proposal_family_id = siblingOne.proposalFamilyId
    activeProposal.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = siblingOne.proposalFamilyId
    siblingTwo.reviewSnapshotPMSummary.provenance.lineage.proposal_family_id = siblingOne.proposalFamilyId

    vi.spyOn(portfolioWorkspaceStorage, 'buildReviewSnapshotOpenHandoffFromProposal').mockImplementation(async (proposal) => proposal.proposalCapture.open_handoff)
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : String(input)
      if (url.includes('/api/backtests/review-snapshots/family-inbox')) {
        return new Response(JSON.stringify(makeFamilyInboxResponse([siblingTwo, siblingOne, activeProposal])), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/open')) {
        return new Response(JSON.stringify({
          handoff: activeProposal.proposalCapture.open_handoff,
          artifact: {
            identity: { artifact_id: activeProposal.reviewSnapshotArtifactId, artifact_kind: 'portfolio_review_snapshot', schema_version: 'review_snapshot_artifact_v1', fingerprint: 'fingerprint-3', consumer_kind: 'saved_hypothetical_replay_proposal' },
            lineage: activeProposal.proposalCapture.lineage,
            review_basis: { benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, derivation_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1', replay_provenance: activeProposal.reviewSnapshot.replay_provenance },
            truth_labels: activeProposal.reviewSnapshotPMSummary.truth_labels,
            compact_summary: { replay_type: 'standard', replay_status: 'ok', investor_economics_status: { status: 'available', reason: null }, candidate_analytics: activeProposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics, baseline_analytics: activeProposal.reviewSnapshotPMSummary.analytics_summary.baseline_analytics, analytics_comparison: activeProposal.reviewSnapshotPMSummary.analytics_summary.analytics_comparison, diagnostics_summary: activeProposal.reviewSnapshotPMSummary.diagnostics_summary },
            proposal_capture: activeProposal.proposalCapture,
            pm_summary: activeProposal.reviewSnapshotPMSummary,
            source_payload: { replay_type: 'standard', replay: activeProposal.reviewSnapshot, overlay_replay: null },
          },
          pm_summary: activeProposal.reviewSnapshotPMSummary,
          replay_payload: { replay_type: 'standard', replay: activeProposal.reviewSnapshot, overlay_replay: null },
        }), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      if (url.includes('/api/backtests/review-snapshots/family-review')) {
        const response = makeFamilyReviewResponse(activeProposal, [activeProposal, siblingOne, siblingTwo])
        response.anchor.comparison_eligibility.compatible_sibling_artifact_ids = [siblingOne.reviewSnapshotArtifactId, siblingTwo.reviewSnapshotArtifactId]
        return new Response(JSON.stringify(response), { status: 200, headers: { 'Content-Type': 'application/json' } })
      }
      return new Response(JSON.stringify({ detail: 'should not compare' }), { status: 400, headers: { 'Content-Type': 'application/json' } })
    })

    const { container } = renderShell({
      savedProposals: [siblingTwo, siblingOne, activeProposal],
      activeThesis: {
        workspaceId: 'workspace-1',
        promotedAt: '2026-04-18T12:00:00Z',
        sourceProposalId: activeProposal.id,
        thesisProposal: activeProposal,
      },
    })

    await within(container).findAllByTestId('active-thesis-artifact-review')
    expect(textContentOfIn(container, 'active-thesis-delta-status')).toContain('Unable to load active thesis same-family delta: ambiguous sibling selection')
  })

  it('promotes and clears the active thesis from saved proposal actions', () => {
    const savedProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')
    const onPromoteProposalToThesis = vi.fn()
    const onClearActiveThesis = vi.fn()

    const { container } = renderShell({
      savedProposals: [savedProposal],
      onPromoteProposalToThesis,
      onClearActiveThesis,
      activeThesis: makeActiveThesis(1, 'IUFS'),
    })

    const ui = within(container)

    const promoteButtons = ui.getAllByTestId('saved-proposal-promote-proposal-1')

    fireEvent.click(promoteButtons[promoteButtons.length - 1] as HTMLElement)
    expect(onPromoteProposalToThesis).toHaveBeenCalledWith('proposal-1')

    fireEvent.click(ui.getByTestId('clear-active-thesis'))
    expect(onClearActiveThesis).toHaveBeenCalledTimes(1)
  })
})
