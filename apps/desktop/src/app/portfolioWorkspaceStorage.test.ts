import { afterEach, describe, expect, it, vi } from 'vitest'

import { createImportedBootstrapResponseFixture } from '../test/portfolioFixtures'
import { projectImportedBootstrap } from '../features/portfolio/importedBootstrapMapper'
import * as portfolioDb from './portfolioDb'
import * as portfolioWorkspaceStorage from './portfolioWorkspaceStorage'
import { buildPersistedImportedSource } from './portfolioWorkspaceStorage'
import type { ConstructionArtifactReplayResponse, OptimizerHandoffReplayResponse, OptimizerHandoffValidationResponse, OptimizerPersistedArtifactReference } from '../features/portfolio/types'
import type {
  ImportedHistoryContext,
  RawPersistedVersionedProposalArtifact,
  WorkspaceState,
  PersistedOptimizerHandoffWorkspaceReview,
  PortfolioNode,
  PortfolioWorkspace,
  ReviewSnapshotActiveThesisCrossFamilyQueueResponse,
  ReviewSnapshotArtifact,
  ReviewSnapshotComparisonResponse,
  ReviewSnapshotFamilyKey,
  ReviewSnapshotFamilyReviewResponse,
  VersionedProposalArtifact,
} from '../features/portfolio/workspaceTypes'

function expectPersistedOptimizerHandoffSource(value: PortfolioWorkspace['source']) {
  expect('kind' in value && value.kind === 'persisted_optimizer_handoff').toBe(true)
  if (!('kind' in value) || value.kind !== 'persisted_optimizer_handoff') {
    throw new Error('Expected persisted optimizer handoff workspace source in test fixture')
  }
  return value
}

const availableInvestorEconomicsStatus = { status: 'available' as const, reason: null }

const importedSnapshot = createImportedBootstrapResponseFixture().snapshot

function createHistoryContext(): ImportedHistoryContext {
  return {
    benchmarkSymbol: 'SPY',
    statementPeriod: '2025-01-01 - 2025-12-31',
    importedAt: '2026-04-10T00:00:00Z',
    importer: 'interactive_brokers',
    sourceFileNames: ['IB2025.pdf'],
    historyStartDate: '2025-01-02',
    historyEndDate: '2025-03-03',
  }
}

function createConstructionArtifactReplayResponse(): ConstructionArtifactReplayResponse {
  return {
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
        steps: [
          {
            rule_id: 'rule-1',
            rule_order: 1,
            input_candidate_symbols: ['AAPL'],
            output_candidate_symbols: ['MSFT'],
          },
        ],
      },
      turnover_diagnostics_status: 'unavailable_legacy_artifact',
      turnover_diagnostics_v1: null,
      weighting_trace_status: 'unavailable_legacy_artifact',
      weighting_trace_v1: null,
    },
    baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
    candidate_weights: [{ symbol: 'MSFT', target_weight: 0.6 }],
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
    replay: {
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
        assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
        status: 'ok',
        investor_economics_status: { status: 'available', reason: null },
        instrument_metadata: [],
        starting_weights: [],
        ending_weights: [],
        metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
        equity_curve: [],
        rebalance_events: [],
        trades: [],
      },
      comparison: null,
      reference_diagnostics: null,
      candidate_diagnostics: null,
      diagnostics_comparison: null,
    },
  }
}

function createOptimizerHandoffReference(): OptimizerPersistedArtifactReference {
  return {
    reference_kind: 'optimizer_handoff_reference_v1',
    handoff_id: 'optimizer_handoff_123',
    artifact_id: 'optimizer_artifact_123',
    manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
    artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
  }
}

function createOptimizerHandoffValidationResponse(): OptimizerHandoffValidationResponse {
  return {
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
      objective: {
        objective_id: 'minimize_l2_distance_to_benchmark',
        benchmark_relative: true,
        description: 'Minimize squared distance to benchmark weights inside the hard-constraint set.',
        alpha_signal_id: null,
        requires_alpha_package: false,
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
      constraint_set_fingerprint: 'constraint-fingerprint-1',
    },
    validation_status: 'ok',
    evaluations: [],
    blocking_rule_ids: [],
    warnings: [],
  }
}

function createOptimizerHandoffReplayResponse(): OptimizerHandoffReplayResponse {
  return {
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
      handoff_reference: createOptimizerHandoffReference(),
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
    replay: createConstructionArtifactReplayResponse().replay,
  }
}

function createPersistedOptimizerHandoffWorkspaceReview(overrides: Partial<PersistedOptimizerHandoffWorkspaceReview> = {}): PersistedOptimizerHandoffWorkspaceReview {
  return {
    workspaceId: 'workspace-optimizer',
    handoffReference: createOptimizerHandoffReference(),
    openedAt: '2026-04-24T00:00:00Z',
    validation: createOptimizerHandoffValidationResponse(),
    replay: createOptimizerHandoffReplayResponse(),
    ...overrides,
  }
}

function createOptimizerHandoffWorkspaceReviewBasisFixture() {
  return {
    basisVersion: 1 as const,
    basisKind: 'persisted_optimizer_handoff_review' as const,
    reviewScope: 'workspace_review_only' as const,
    canonicalSource: 'persisted_handoff_reference' as const,
    basisProvenanceLabel: 'artifact_backed_review_basis' as const,
    portfolioTruth: 'imported_portfolio_snapshot' as const,
    candidateTruth: 'hypothetical_optimizer_handoff' as const,
    handoffReference: createOptimizerHandoffReference(),
    openedAt: '2026-04-24T00:00:00Z',
    benchmarkSymbol: 'SPY',
    baseCurrency: 'USD',
    replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
    baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
    candidateWeights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
  }
}

function createConstructionArtifactWorkspaceReviewBasisFixture() {
  return {
    basisVersion: 1 as const,
    basisKind: 'persisted_construction_artifact_review' as const,
    reviewScope: 'workspace_review_only' as const,
    canonicalSource: 'typed_preview_handoff' as const,
    basisProvenanceLabel: 'artifact_backed_review_basis' as const,
    portfolioTruth: 'imported_portfolio_snapshot' as const,
    candidateTruth: 'hypothetical_construction_artifact' as const,
    constructionArtifactId: 'artifact-123',
    previewHandoff: createConstructionArtifactReplayResponse().review_basis!.preview_handoff,
    openedAt: '2026-04-23T00:00:00Z',
    benchmarkSymbol: 'SPY',
    baseCurrency: 'USD',
    replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
    baselineWeights: [{ symbol: 'AAPL', target_weight: 0.6 }],
    candidateWeights: [{ symbol: 'MSFT', target_weight: 0.6 }],
  }
}

type SavedProposalFixtureOptions = {
  includeMethodologyProvenance?: boolean
  replayType?: ReviewSnapshotArtifact['source_payload']['replay_type']
}

function createMethodologyProvenanceFixture() {
  return {
    provenance_version: 1 as const,
    source: 'portfolio_allocation_backtest_engine' as const,
    methodology_truth: 'review_only_replay_methodology' as const,
    assumptions_truth: 'review_only_replay_assumptions' as const,
    analytics_truth: 'hypothetical_replay_analytics_only' as const,
    review_scope: 'workspace_review_context_only' as const,
  }
}

function buildFixtureMethodology(methodology: string, methodologyProvenance: VersionedProposalArtifact['reviewSnapshot']['replay']['methodology_provenance']) {
  return {
    methodology,
    ...(methodologyProvenance ? { methodology_provenance: methodologyProvenance } : {}),
  }
}

function buildFixtureAnalyticsSummary(input: {
  methodology: string
  methodologyProvenance: VersionedProposalArtifact['reviewSnapshot']['replay']['methodology_provenance']
  assumptions: VersionedProposalArtifact['reviewSnapshot']['replay']['candidate_result']['assumptions']
  benchmarkSymbol: string | null
  metrics: VersionedProposalArtifact['reviewSnapshot']['replay']['candidate_result']['metrics']
}) {
  return {
    methodology: input.methodology,
    ...(input.methodologyProvenance ? { methodology_provenance: input.methodologyProvenance } : {}),
    assumptions: input.assumptions,
    benchmark_symbol: input.benchmarkSymbol,
    benchmark_return_pct: input.metrics.benchmark_return_pct,
    total_return_pct: input.metrics.total_return_pct,
    annualized_return_pct: input.metrics.annualized_return_pct,
    annualized_volatility_pct: input.metrics.annualized_volatility_pct,
    downside_volatility_pct: input.metrics.downside_volatility_pct,
    max_drawdown_pct: input.metrics.max_drawdown_pct,
    sharpe_ratio: input.metrics.sharpe_ratio,
    sortino_ratio: input.metrics.sortino_ratio,
    excess_return_pct: input.metrics.excess_return_pct,
    tracking_error_pct: input.metrics.tracking_error_pct,
    information_ratio: input.metrics.information_ratio,
    beta_vs_benchmark: input.metrics.beta_vs_benchmark,
    correlation_vs_benchmark: input.metrics.correlation_vs_benchmark,
    total_turnover_pct: input.metrics.total_turnover_pct,
    total_cost_paid: input.metrics.total_cost_paid,
  }
}

function createReplayCandidateResultFixture(): ConstructionArtifactReplayResponse['replay']['candidate_result'] {
  return {
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
    investor_economics_status: availableInvestorEconomicsStatus,
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
    equity_curve: [],
    rebalance_events: [],
    trades: [],
  }
}

function createPortfolioAllocationReplayFixture(
  methodologyProvenance: ConstructionArtifactReplayResponse['replay']['methodology_provenance'],
): ConstructionArtifactReplayResponse['replay'] {
  return {
    methodology: 'm',
    ...(methodologyProvenance ? { methodology_provenance: methodologyProvenance } : {}),
    investor_economics_status: availableInvestorEconomicsStatus,
    reference_result: null,
    candidate_result: createReplayCandidateResultFixture(),
    comparison: null,
    reference_diagnostics: null,
    candidate_diagnostics: null,
    diagnostics_comparison: null,
  }
}

function createSnapshotProposalSourceFixture() {
  return {
    proposal_source_version: 1 as const,
    proposal_source_kind: 'draft_replacement_intent_review_only' as const,
    proposal_truth: 'review_only_hypothetical_proposal' as const,
    portfolio_truth: 'draft_snapshot_not_applied' as const,
    review_scope: 'proposal_review_context_only' as const,
  }
}

function createProposalSourceFixture(): VersionedProposalArtifact['proposalSource'] {
  return {
    proposalSourceVersion: 1,
    proposalSourceKind: 'draft_replacement_intent_review_only',
    proposalTruth: 'review_only_hypothetical_proposal',
    portfolioTruth: 'draft_snapshot_not_applied',
    reviewScope: 'proposal_review_context_only',
  }
}

function createHypotheticalReplayProvenanceFixture(): VersionedProposalArtifact['replayBasis']['replayProvenance'] {
  return {
    candidate_input_source: 'replacement_intent_preview',
    construction_rule_id: 'same_weight_substitution_v1',
    upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' },
    seed_ranking_id: 'etf_ranking_engine_v1',
    seed_methodology_id: 'etf_ranking_methodology_v1',
    constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null },
  }
}

function createSavedProposalReviewSnapshotFixtureSource(options: SavedProposalFixtureOptions = {}) {
  const methodologyProvenance = options.includeMethodologyProvenance === false ? undefined : createMethodologyProvenanceFixture()
  const replayType = options.replayType ?? 'standard'
  const snapshotProposalSource = createSnapshotProposalSourceFixture()
  const replayProvenance = createHypotheticalReplayProvenanceFixture()
  const activeReplay = createPortfolioAllocationReplayFixture(methodologyProvenance)

  return {
    id: 'proposal-1',
    kind: 'single_replacement_hypothetical_replay_proposal' as const,
    schemaVersion: 1 as const,
    createdAt: '2026-04-16T00:00:00Z',
    workspaceId: 'workspace-1',
    sourceDraftId: 'draft-1',
    sourceBaseNodeId: 'node-1',
    proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
    versionNumber: 1,
    savedFrom: 'desktop_hypothetical_replay_review' as const,
    reviewStatus: 'recorded' as const,
    sourceIntent: {
      kind: 'etf_replacement_intent' as const,
      source: 'candidate_seed' as const,
      createdAt: '2026-04-15T00:05:00Z',
      draftId: 'draft-1',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
      seededFromDraftId: 'draft-1',
      seedRankingId: 'etf_ranking_engine_v1',
      seedMethodologyId: 'etf_ranking_methodology_v1',
      seedRankingBasisDate: '2026-04-15',
      peerGroup: 'Sector UCITS ETF',
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      confidence: 'medium' as const,
      holdingsSupport: 'mixed' as const,
      warningCount: 1,
    },
    proposalSource: createProposalSourceFixture(),
    reviewSnapshotArtifactId: 'review_snapshot_1234567890abcdef',
    replayBasis: {
      benchmarkSymbol: 'SPY',
      startDate: '2024-01-01',
      endDate: '2024-12-31',
      rebalanceFrequency: 'monthly',
      commissionBps: 0,
      slippageBps: 0,
      derivationBasis: 'draft_snapshot_positions_normalized' as const,
      candidateConstructionRule: 'same_weight_substitution_v1' as const,
      replayProvenance: replayProvenance,
    },
    reviewSnapshot: replayType === 'overlay_aware'
      ? {
          proposal: {
            source: 'draft_replacement_intent' as const,
            proposal_source: snapshotProposalSource,
            incumbent_symbol: 'AAPL',
            candidate_symbol: 'IUFS',
            draft_id: 'draft-1',
            base_node_id: 'node-1',
          },
          derivation: {
            baseline_basis: 'draft_snapshot_positions_normalized' as const,
            candidate_construction_rule: 'same_weight_substitution_v1' as const,
          },
          replay_provenance: replayProvenance,
          overlay_application: {
            overlay_id: 'benchmark_trend_overlay_v1' as const,
            overlay_status: 'risk_on' as const,
            as_of_month_end: '2024-12-31',
            benchmark_symbol: 'SPY',
            risky_weight_scale: 1,
            cash_residual_weight: 0,
            applied_to_candidate_only: true,
          },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights_pre_overlay: [{ symbol: 'IUFS', target_weight: 1 }],
          candidate_weights_post_overlay: [{ symbol: 'IUFS', target_weight: 1 }],
          base_replay: createPortfolioAllocationReplayFixture(methodologyProvenance),
          overlay_replay: activeReplay,
          warnings: [],
        }
      : {
          proposal: {
            source: 'draft_replacement_intent' as const,
            proposal_source: snapshotProposalSource,
            incumbent_symbol: 'AAPL',
            candidate_symbol: 'IUFS',
            draft_id: 'draft-1',
            base_node_id: 'node-1',
          },
          derivation: {
            baseline_basis: 'draft_snapshot_positions_normalized' as const,
            candidate_construction_rule: 'same_weight_substitution_v1' as const,
          },
          replay_provenance: replayProvenance,
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: activeReplay,
          warnings: [],
        },
  }
}

function deriveFixtureEffectiveReplay(
  reviewSnapshotPayload: VersionedProposalArtifact['reviewSnapshot'] | ReviewSnapshotArtifact['source_payload'],
) {
  const replayPayload = 'proposal' in reviewSnapshotPayload
    ? reviewSnapshotPayload
    : reviewSnapshotPayload.overlay_replay ?? reviewSnapshotPayload.replay

  if (!replayPayload) {
    throw new Error('Fixture review snapshot replay payload is missing')
  }

  if ('replay' in replayPayload) {
    return {
      replayPayload,
      replayType: 'standard' as const,
      replay: replayPayload.replay,
    }
  }

  return {
    replayPayload,
    replayType: 'overlay_aware' as const,
    replay: replayPayload.overlay_replay,
  }
}

function createReviewSnapshotArtifactSourcePayloadFixture(
  reviewSnapshotPayload: VersionedProposalArtifact['reviewSnapshot'],
): ReviewSnapshotArtifact['source_payload'] {
  const effectiveReplay = deriveFixtureEffectiveReplay(reviewSnapshotPayload)

  return effectiveReplay.replayType === 'standard'
    ? {
        replay_type: 'standard',
        replay: effectiveReplay.replayPayload as Extract<VersionedProposalArtifact['reviewSnapshot'], { replay: unknown }>,
        overlay_replay: null,
      }
    : {
        replay_type: 'overlay_aware',
        replay: null,
        overlay_replay: effectiveReplay.replayPayload as Extract<VersionedProposalArtifact['reviewSnapshot'], { overlay_replay: unknown }>,
      }
}

function createProposalCaptureFixture(
  proposal: Omit<VersionedProposalArtifact, 'reviewSnapshotPMSummary'>,
): VersionedProposalArtifact['proposalCapture'] {
  const effectiveReplay = deriveFixtureEffectiveReplay(proposal.reviewSnapshot)

  return {
    capture_version: 1,
    capture_kind: 'workspace_review_saved_proposal',
    open_handoff: {
      handoff_kind: 'review_snapshot_open_handoff_v1',
      artifact_id: proposal.reviewSnapshotArtifactId,
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      consumer_kind: 'saved_hypothetical_replay_proposal',
    },
    lineage: {
      workspace_id: proposal.workspaceId,
      source_draft_id: proposal.sourceDraftId,
      source_base_node_id: proposal.sourceBaseNodeId,
      proposal_family_id: proposal.proposalFamilyId,
      proposal_id: proposal.id,
      version_number: proposal.versionNumber,
      source_kind: 'hypothetical_replacement_replay',
    },
    proposal: {
      source: proposal.reviewSnapshot.proposal.source,
      proposal_source: proposal.reviewSnapshot.proposal.proposal_source ?? createSnapshotProposalSourceFixture(),
      incumbent_symbol: proposal.reviewSnapshot.proposal.incumbent_symbol,
      candidate_symbol: proposal.reviewSnapshot.proposal.candidate_symbol,
    },
    replay_type: effectiveReplay.replayType,
    replay_provenance: proposal.reviewSnapshot.replay_provenance,
    review_basis: {
      benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
      benchmark_symbol: proposal.replayBasis.benchmarkSymbol,
      replay_window: { start_date: proposal.replayBasis.startDate, end_date: proposal.replayBasis.endDate },
      rebalance_frequency: proposal.replayBasis.rebalanceFrequency,
      commission_bps: proposal.replayBasis.commissionBps,
      slippage_bps: proposal.replayBasis.slippageBps,
      derivation_basis: proposal.replayBasis.derivationBasis,
      candidate_construction_rule: proposal.replayBasis.candidateConstructionRule,
    },
  }
}

function createReviewSnapshotPMSummaryFixture(proposal: VersionedProposalArtifact): ReviewSnapshotArtifact['pm_summary'] {
  const effectiveReplay = deriveFixtureEffectiveReplay(proposal.reviewSnapshot)
  const methodologyProvenance = effectiveReplay.replay.methodology_provenance
  const proposalSource = proposal.reviewSnapshot.proposal.proposal_source ?? {
    proposal_source_version: 1,
    proposal_source_kind: 'draft_replacement_intent_review_only',
    proposal_truth: 'review_only_hypothetical_proposal',
    portfolio_truth: 'draft_snapshot_not_applied',
    review_scope: 'proposal_review_context_only',
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
    replay_type: effectiveReplay.replayType,
    replay_status: effectiveReplay.replay.candidate_result.status,
    investor_economics_status: effectiveReplay.replay.investor_economics_status,
    review_basis: {
      benchmark_separation: 'explicit_per_snapshot_benchmark_fields' as const,
      benchmark_symbol: proposal.replayBasis.benchmarkSymbol,
      replay_window: { start_date: proposal.replayBasis.startDate, end_date: proposal.replayBasis.endDate },
      rebalance_frequency: proposal.replayBasis.rebalanceFrequency,
      commission_bps: proposal.replayBasis.commissionBps,
      slippage_bps: proposal.replayBasis.slippageBps,
      derivation_basis: proposal.replayBasis.derivationBasis,
      candidate_construction_rule: proposal.replayBasis.candidateConstructionRule,
    },
    methodology: buildFixtureMethodology(effectiveReplay.replay.methodology, methodologyProvenance),
    assumptions: effectiveReplay.replay.candidate_result.assumptions,
    analytics_summary: {
      candidate_analytics: buildFixtureAnalyticsSummary({
        methodology: effectiveReplay.replay.methodology,
        methodologyProvenance,
        assumptions: effectiveReplay.replay.candidate_result.assumptions,
        benchmarkSymbol: proposal.replayBasis.benchmarkSymbol,
        metrics: effectiveReplay.replay.candidate_result.metrics,
      }),
      baseline_analytics: effectiveReplay.replay.reference_result ? buildFixtureAnalyticsSummary({
        methodology: effectiveReplay.replay.methodology,
        methodologyProvenance,
        assumptions: effectiveReplay.replay.reference_result.assumptions,
        benchmarkSymbol: effectiveReplay.replay.reference_result.benchmark_symbol,
        metrics: effectiveReplay.replay.reference_result.metrics,
      }) : null,
      analytics_comparison: effectiveReplay.replay.comparison,
    },
    diagnostics_summary: {
      diagnostics_available: effectiveReplay.replay.diagnostics_comparison != null,
      top_factor_exposure_change: effectiveReplay.replay.diagnostics_comparison?.top_factor_exposure_change ?? null,
      top_volatility_change: effectiveReplay.replay.diagnostics_comparison?.top_volatility_change ?? null,
      top_risk_contribution_change: effectiveReplay.replay.diagnostics_comparison?.top_risk_contribution_change ?? null,
      top_concentration_change: effectiveReplay.replay.diagnostics_comparison?.top_concentration_change ?? null,
      top_stress_scenario_change: effectiveReplay.replay.diagnostics_comparison?.top_stress_scenario_change ?? null,
    },
  }
}

function createSavedProposalArtifactFixtureBase(options: SavedProposalFixtureOptions = {}): Omit<VersionedProposalArtifact, 'reviewSnapshotPMSummary'> {
  const source = createSavedProposalReviewSnapshotFixtureSource(options)
  const proposal = {
    id: source.id,
    kind: source.kind,
    schemaVersion: source.schemaVersion,
    createdAt: source.createdAt,
    workspaceId: source.workspaceId,
    sourceDraftId: source.sourceDraftId,
    sourceBaseNodeId: source.sourceBaseNodeId,
    proposalFamilyId: source.proposalFamilyId,
    versionNumber: source.versionNumber,
    savedFrom: source.savedFrom,
    reviewStatus: source.reviewStatus,
    sourceIntent: source.sourceIntent,
    proposalCapture: null as unknown as VersionedProposalArtifact['proposalCapture'],
    proposalSource: source.proposalSource,
    reviewSnapshotArtifactId: source.reviewSnapshotArtifactId,
    replayBasis: source.replayBasis,
    reviewSnapshot: source.reviewSnapshot,
  } satisfies Omit<VersionedProposalArtifact, 'reviewSnapshotPMSummary'>

  proposal.proposalCapture = createProposalCaptureFixture(proposal)
  return proposal
}

function createReviewSnapshotCompactSummaryFixture(proposal: VersionedProposalArtifact): ReviewSnapshotArtifact['compact_summary'] {
  const effectiveReplay = deriveFixtureEffectiveReplay(proposal.reviewSnapshot)
  const methodologyProvenance = effectiveReplay.replay.methodology_provenance

  return {
    replay_type: effectiveReplay.replayType,
    replay_status: effectiveReplay.replay.candidate_result.status,
    investor_economics_status: effectiveReplay.replay.investor_economics_status,
    candidate_analytics: buildFixtureAnalyticsSummary({
      methodology: effectiveReplay.replay.methodology,
      methodologyProvenance,
      assumptions: effectiveReplay.replay.candidate_result.assumptions,
      benchmarkSymbol: effectiveReplay.replay.candidate_result.benchmark_symbol,
      metrics: effectiveReplay.replay.candidate_result.metrics,
    }),
    baseline_analytics: effectiveReplay.replay.reference_result ? buildFixtureAnalyticsSummary({
      methodology: effectiveReplay.replay.methodology,
      methodologyProvenance,
      assumptions: effectiveReplay.replay.reference_result.assumptions,
      benchmarkSymbol: effectiveReplay.replay.reference_result.benchmark_symbol,
      metrics: effectiveReplay.replay.reference_result.metrics,
    }) : null,
    analytics_comparison: effectiveReplay.replay.comparison,
    diagnostics_summary: {
      diagnostics_available: effectiveReplay.replay.diagnostics_comparison != null,
      top_factor_exposure_change: effectiveReplay.replay.diagnostics_comparison?.top_factor_exposure_change ?? null,
      top_volatility_change: effectiveReplay.replay.diagnostics_comparison?.top_volatility_change ?? null,
      top_risk_contribution_change: effectiveReplay.replay.diagnostics_comparison?.top_risk_contribution_change ?? null,
      top_concentration_change: effectiveReplay.replay.diagnostics_comparison?.top_concentration_change ?? null,
      top_stress_scenario_change: effectiveReplay.replay.diagnostics_comparison?.top_stress_scenario_change ?? null,
    },
  }
}

function createSavedProposalReviewSnapshotFixtureBundle(options: SavedProposalFixtureOptions = {}) {
  const proposal = createSavedProposalArtifactFixtureBase(options) as VersionedProposalArtifact

  proposal.reviewSnapshotPMSummary = createReviewSnapshotPMSummaryFixture(proposal)
  return {
    proposal,
    reviewSnapshotArtifact: createReviewSnapshotArtifactFromProposalFixture(proposal),
  }
}

function createSavedProposalArtifactFixture(options: SavedProposalFixtureOptions = {}): VersionedProposalArtifact {
  return createSavedProposalReviewSnapshotFixtureBundle(options).proposal
}

function createReviewSnapshotArtifactFromProposalFixture(proposal: VersionedProposalArtifact): ReviewSnapshotArtifact {
  return {
    identity: {
      artifact_id: proposal.reviewSnapshotArtifactId,
      artifact_kind: 'portfolio_review_snapshot',
      schema_version: 'review_snapshot_artifact_v1',
      fingerprint: 'f'.repeat(64),
      consumer_kind: 'saved_hypothetical_replay_proposal',
    },
    lineage: {
      workspace_id: proposal.workspaceId,
      source_draft_id: proposal.sourceDraftId,
      source_base_node_id: proposal.sourceBaseNodeId,
      proposal_family_id: proposal.proposalFamilyId,
      proposal_id: proposal.id,
      version_number: proposal.versionNumber,
      source_kind: 'hypothetical_replacement_replay',
    },
    review_basis: {
      benchmark_symbol: proposal.replayBasis.benchmarkSymbol,
      start_date: proposal.replayBasis.startDate,
      end_date: proposal.replayBasis.endDate,
      rebalance_frequency: proposal.replayBasis.rebalanceFrequency,
      commission_bps: proposal.replayBasis.commissionBps,
      slippage_bps: proposal.replayBasis.slippageBps,
      derivation_basis: proposal.replayBasis.derivationBasis,
      candidate_construction_rule: proposal.replayBasis.candidateConstructionRule,
      replay_provenance: proposal.replayBasis.replayProvenance,
    },
    truth_labels: {
      proposal_truth: 'review_only_hypothetical_proposal',
      portfolio_truth: 'draft_snapshot_not_applied',
      analytics_truth: 'hypothetical_replay_analytics_only',
      review_scope: 'proposal_review_context_only',
    },
    compact_summary: createReviewSnapshotCompactSummaryFixture(proposal),
    proposal_capture: proposal.proposalCapture,
    pm_summary: proposal.reviewSnapshotPMSummary,
    source_payload: createReviewSnapshotArtifactSourcePayloadFixture(proposal.reviewSnapshot),
  }
}

function createReviewSnapshotArtifactFixture(options: SavedProposalFixtureOptions = {}): ReviewSnapshotArtifact {
  return createSavedProposalReviewSnapshotFixtureBundle(options).reviewSnapshotArtifact
}

function createReviewSnapshotFamilyInboxRowFixture(artifact: ReviewSnapshotArtifact) {
  return {
    family_key: createReviewSnapshotFamilyKeyFixture(artifact),
    latest_identity: artifact.identity,
    lineage: artifact.lineage,
    proposal_capture: artifact.proposal_capture,
    pm_summary: artifact.pm_summary,
    sibling_count: 1,
    compare_readiness: {
      ready: false as const,
      reason: 'no_compatible_family_pair' as const,
      compatible_pair_count: 0,
    },
    latest_saved_at: '2026-04-16T00:05:00Z',
    latest_order_provenance: 'persisted_artifact_file_mtime' as const,
  }
}

function createReviewSnapshotFamilyInboxResponseFixture(artifact: ReviewSnapshotArtifact) {
  return {
    inbox_kind: 'review_snapshot_family_inbox' as const,
    workspace_id: artifact.lineage.workspace_id,
    provenance: 'persisted_review_snapshot_artifacts_only' as const,
    rows: [createReviewSnapshotFamilyInboxRowFixture(artifact)],
  }
}

function createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact: ReviewSnapshotArtifact): ReviewSnapshotActiveThesisCrossFamilyQueueResponse {
  return {
    queue_kind: 'review_snapshot_active_thesis_cross_family_queue',
    provenance: 'persisted_review_snapshot_artifacts_and_active_thesis_reference_only',
    queue_ordering: 'latest_saved_at_desc_then_artifact_id_desc',
    active_thesis: {
      source_proposal_id: 'proposal-thesis',
      handoff: {
        handoff_kind: 'review_snapshot_open_handoff_v1',
        artifact_id: 'review_snapshot_active_thesis',
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      identity: {
        artifact_id: 'review_snapshot_active_thesis',
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        fingerprint: 'a'.repeat(64),
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      lineage: {
        workspace_id: artifact.lineage.workspace_id,
        source_draft_id: artifact.lineage.source_draft_id,
        source_base_node_id: artifact.lineage.source_base_node_id,
        proposal_family_id: 'etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z',
        proposal_id: 'proposal-thesis',
        version_number: 4,
        source_kind: 'hypothetical_replacement_replay',
      },
      family_key: {
        workspace_id: artifact.lineage.workspace_id,
        source_draft_id: artifact.lineage.source_draft_id,
        source_base_node_id: artifact.lineage.source_base_node_id,
        proposal_family_id: 'etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z',
        source_kind: 'hypothetical_replacement_replay',
      },
    },
    rows: [
      {
        latest_identity: artifact.identity,
        lineage: artifact.lineage,
        family_key: createReviewSnapshotFamilyKeyFixture(artifact),
        family_separation: {
          separation_kind: 'distinct_proposal_family_id',
          active_thesis_proposal_family_id: 'etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z',
          queue_proposal_family_id: artifact.lineage.proposal_family_id,
        },
        proposal_source: artifact.pm_summary.provenance.proposal_source,
        truth_labels: artifact.pm_summary.truth_labels,
        trust_visibility: {
          investor_economics_status: artifact.pm_summary.investor_economics_status,
          benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
        },
        pm_summary_fields: {
          replay_type: artifact.pm_summary.replay_type,
          replay_status: artifact.pm_summary.replay_status,
          review_basis: artifact.pm_summary.review_basis,
          methodology: artifact.pm_summary.methodology,
          assumptions: artifact.pm_summary.assumptions,
          analytics_summary: artifact.pm_summary.analytics_summary,
          diagnostics_summary: artifact.pm_summary.diagnostics_summary,
        },
        latest_saved_at: '2026-04-16T00:05:00Z',
        queue_order_provenance: 'persisted_artifact_file_mtime_desc_then_artifact_id_desc',
      },
    ],
  }
}

function createReviewSnapshotFamilyKeyFixture(artifact: ReviewSnapshotArtifact): ReviewSnapshotFamilyKey {
  return {
    workspace_id: artifact.lineage.workspace_id,
    source_draft_id: artifact.lineage.source_draft_id,
    source_base_node_id: artifact.lineage.source_base_node_id,
    proposal_family_id: artifact.lineage.proposal_family_id,
    source_kind: artifact.lineage.source_kind,
  }
}

function createReviewSnapshotComparisonResponseFixture(artifact: ReviewSnapshotArtifact): ReviewSnapshotComparisonResponse {
  return {
    comparison_kind: 'review_snapshot_comparison',
    family_key: createReviewSnapshotFamilyKeyFixture(artifact),
    baseline: {
      benchmark_symbol: artifact.review_basis.benchmark_symbol,
      replay_window: { start_date: artifact.review_basis.start_date, end_date: artifact.review_basis.end_date },
      replay_type: artifact.compact_summary.replay_type,
      candidate_construction_rule: artifact.review_basis.candidate_construction_rule,
      derivation_basis: artifact.review_basis.derivation_basis,
      source_pair: 'AAPL -> IUFS',
      replay_status: artifact.compact_summary.replay_status,
      investor_economics_status: artifact.compact_summary.investor_economics_status,
      methodology: {
        methodology: 'm',
        methodology_provenance: artifact.compact_summary.candidate_analytics.methodology_provenance,
        assumptions: artifact.compact_summary.candidate_analytics.assumptions,
      },
      analytics: artifact.compact_summary.candidate_analytics,
      diagnostics_summary: artifact.compact_summary.diagnostics_summary,
    },
    candidate: {
      benchmark_symbol: artifact.review_basis.benchmark_symbol,
      replay_window: { start_date: artifact.review_basis.start_date, end_date: artifact.review_basis.end_date },
      replay_type: artifact.compact_summary.replay_type,
      candidate_construction_rule: artifact.review_basis.candidate_construction_rule,
      derivation_basis: artifact.review_basis.derivation_basis,
      source_pair: 'AAPL -> IUIT',
      replay_status: artifact.compact_summary.replay_status,
      investor_economics_status: artifact.compact_summary.investor_economics_status,
      methodology: {
        methodology: 'm',
        methodology_provenance: artifact.compact_summary.candidate_analytics.methodology_provenance,
        assumptions: artifact.compact_summary.candidate_analytics.assumptions,
      },
      analytics: artifact.compact_summary.candidate_analytics,
      diagnostics_summary: artifact.compact_summary.diagnostics_summary,
    },
    provenance: 'persisted_review_snapshot_artifacts_only',
    benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
    baseline_pm_summary: { ...artifact.pm_summary, role: 'baseline' },
    candidate_pm_summary: { ...artifact.pm_summary, role: 'candidate' },
    analytics_comparison: artifact.compact_summary.analytics_comparison,
    methodology: {
      baseline_methodology: {
        methodology: 'm',
        methodology_provenance: artifact.compact_summary.candidate_analytics.methodology_provenance,
        assumptions: artifact.compact_summary.candidate_analytics.assumptions,
      },
      candidate_methodology: {
        methodology: 'm',
        methodology_provenance: artifact.compact_summary.candidate_analytics.methodology_provenance,
        assumptions: artifact.compact_summary.candidate_analytics.assumptions,
      },
      methodology_consistent: true,
      assumptions_consistent: true,
    },
    assumptions: {
      baseline_assumptions: artifact.compact_summary.candidate_analytics.assumptions,
      candidate_assumptions: artifact.compact_summary.candidate_analytics.assumptions,
      assumptions_consistent: true,
    },
  }
}

function createReviewSnapshotFamilyReviewResponseFixture(artifact: ReviewSnapshotArtifact): ReviewSnapshotFamilyReviewResponse {
  return {
    review_kind: 'review_snapshot_family_review',
    family_key: createReviewSnapshotFamilyKeyFixture(artifact),
    provenance: 'persisted_review_snapshot_artifacts_only',
    compare_selection_policy: 'exactly_two_distinct_family_siblings',
    anchor: {
      identity: artifact.identity,
      open_handoff: artifact.proposal_capture.open_handoff,
      lineage: artifact.lineage,
      pm_summary: artifact.pm_summary,
      comparison_eligibility: {
        eligible: false,
        reason: 'no_compatible_family_sibling',
        compatible_sibling_artifact_ids: [],
      },
    },
    siblings: [{
      identity: artifact.identity,
      open_handoff: artifact.proposal_capture.open_handoff,
      lineage: artifact.lineage,
      pm_summary: artifact.pm_summary,
      comparison_eligibility: {
        eligible: false,
        reason: 'no_compatible_family_sibling',
        compatible_sibling_artifact_ids: [],
      },
    }],
  }
}

function buildLegacySavedProposalMirrorFromProposal(proposal: VersionedProposalArtifact) {
  return createReviewSnapshotPMSummaryFixture(proposal)
}

function mockProposalAndArtifactLoad(
  proposals: RawPersistedVersionedProposalArtifact[],
  artifactsById: Record<string, ReviewSnapshotArtifact> = {},
) {
  return vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
    const store = storeName === portfolioDb.versionedProposalStoreName
      ? {
          index() {
            return {
              getAll(_key: string) {
                const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: proposals as unknown }
                queueMicrotask(() => request.onsuccess?.())
                return request
              },
            }
          },
        }
      : {
          index() {
            return {
              getAll(key: string) {
                const artifact = artifactsById[key]
                const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: artifact ? [{ id: artifact.lineage.proposal_id, workspaceId: artifact.lineage.workspace_id, reviewSnapshotArtifactId: key, artifact }] as unknown : [] as unknown }
                queueMicrotask(() => request.onsuccess?.())
                return request
              },
            }
          },
        }
    return new Promise((resolve, reject) => handler(store as unknown as IDBObjectStore, resolve, reject))
  })
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('portfolioWorkspaceStorage', () => {
  it('builds persisted sources with historySource only', () => {
    const persistedSource = buildPersistedImportedSource({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      historyContext: createHistoryContext(),
      importedHistorySnapshot: importedSnapshot,
    })

    expect(persistedSource).toEqual({
      importedFileNames: ['IB2025.pdf'],
      importedAt: '2026-04-10T00:00:00Z',
      importer: 'interactive_brokers',
      baseCurrency: 'USD',
      historySource: {
        kind: 'imported_replay',
        historyContext: createHistoryContext(),
        importedHistorySnapshot: importedSnapshot,
      },
    })
    expect('historyContext' in persistedSource).toBe(false)
    expect('importedHistorySnapshot' in persistedSource).toBe(false)
  })

  it('embeds current-format persisted sources inside workspaces', () => {
    const cleanWorkspace: PortfolioWorkspace = {
      id: 'workspace-clean',
      name: 'Portfolio Workspace',
      createdAt: '2026-04-10T00:00:00Z',
      updatedAt: '2026-04-10T00:00:00Z',
      rootNodeId: 'node-1',
      activeNodeId: 'node-1',
      source: buildPersistedImportedSource({
        importedFileNames: ['IB2025.pdf'],
        importedAt: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        baseCurrency: 'USD',
        historyContext: createHistoryContext(),
        importedHistorySnapshot: importedSnapshot,
      }),
    }

    expect('historySource' in cleanWorkspace.source && cleanWorkspace.source.historySource.kind).toBe('imported_replay')
  })

  it('creates imported workspaces with dashboard-first startup selection', async () => {
    const persisted = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, structuredClone(value))
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    const bootstrap = createImportedBootstrapResponseFixture()
    const created = await portfolioWorkspaceStorage.createWorkspaceFromImport({
      analysis: projectImportedBootstrap(bootstrap).workspace,
      importedFileNames: ['IB2025.pdf'],
      historyContext: createHistoryContext(),
      importedHistorySnapshot: importedSnapshot,
    })

    expect(created.workspaceState.activeDraftId).toBe(created.draft.id)
    expect(created.workspaceState.selectedExposureSnapshotId).toBe(created.rootNode.id)
  })

  it('creates and restores persisted construction artifact workspace reviews', async () => {
    const replay = createConstructionArtifactReplayResponse()
    const persisted = new Map<string, unknown>()
    const withStoresSpy = vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })
    const withStoreSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      if (storeName === portfolioDb.persistedConstructionArtifactReviewStoreName) {
        const store = {
          get(key: string) {
            const request = { ...requestTemplate, result: persisted.get(`${storeName}:${key}`) }
            queueMicrotask(() => request.onsuccess?.())
            return request
          },
        } as unknown as IDBObjectStore
        return new Promise((resolve, reject) => handler(store, resolve, reject))
      }
      return Promise.resolve(null as never)
    })

    const created = await portfolioWorkspaceStorage.createWorkspaceFromPersistedConstructionArtifact({
      constructionArtifactId: 'artifact-123',
      openedAt: '2026-04-23T00:00:00Z',
      replay,
    })

    expect(created.workspace.source).toEqual({
      kind: 'persisted_construction_artifact',
      constructionArtifactId: 'artifact-123',
      openedAt: '2026-04-23T00:00:00Z',
      reviewBasis: {
        basisVersion: 1,
        basisKind: 'persisted_construction_artifact_review',
        reviewScope: 'workspace_review_only',
        canonicalSource: 'typed_preview_handoff',
        basisProvenanceLabel: 'artifact_backed_review_basis',
        portfolioTruth: 'imported_portfolio_snapshot',
        candidateTruth: 'hypothetical_construction_artifact',
        constructionArtifactId: 'artifact-123',
        previewHandoff: replay.review_basis!.preview_handoff,
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
    })
    expect(created.draft).toBeNull()
    expect(created.rootNode.name).toBe('Artifact Review Basis')
    expect(created.rootNode.kind).toBe('artifact_review_basis')
    expect(created.rootNode.portfolioSnapshot).toBeNull()
    expect(created.rootNode.artifactReviewBasis).toMatchObject({
      canonicalSource: 'typed_preview_handoff',
      basisProvenanceLabel: 'artifact_backed_review_basis',
      constructionArtifactId: 'artifact-123',
      basisKind: 'persisted_construction_artifact_review',
      previewHandoff: replay.review_basis!.preview_handoff,
    })
    expect(created.review).toMatchObject({
      workspaceId: created.workspace.id,
      constructionArtifactId: 'artifact-123',
      reviewBasisSource: {
        canonical_source: 'typed_preview_handoff',
        basis_provenance_label: 'artifact_backed_review_basis',
      },
      replay,
    })

    await expect(portfolioWorkspaceStorage.getPersistedConstructionArtifactWorkspaceReview(created.workspace.id)).resolves.toMatchObject({
      workspaceId: created.workspace.id,
      constructionArtifactId: 'artifact-123',
      reviewBasisSource: {
        canonical_source: 'typed_preview_handoff',
        basis_provenance_label: 'artifact_backed_review_basis',
      },
      replay,
    })
    expect(withStoresSpy).toHaveBeenCalled()
    expect(withStoreSpy).toHaveBeenCalled()
  })

  it('hydrates effective replay params for older cached construction artifact reviews', async () => {
    const legacyReplay = createConstructionArtifactReplayResponse()
    delete (legacyReplay as { effective_replay_params?: unknown }).effective_replay_params
    const review = {
      workspaceId: 'workspace-artifact',
      constructionArtifactId: 'artifact-123',
      openedAt: '2026-04-23T00:00:00Z',
      replay: legacyReplay,
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate, result: storeName === portfolioDb.persistedConstructionArtifactReviewStoreName ? review : undefined }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedConstructionArtifactWorkspaceReview('workspace-artifact')).resolves.toMatchObject({
      replay: {
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
    })
  })

  it('uses current-contract construction artifact fixtures with max_trade_intent_count', () => {
    expect(createConstructionArtifactReplayResponse().replay_provenance.hard_constraints).toMatchObject({
      max_trade_intent_count: null,
    })
  })

  it('normalizes legacy cached artifact review workspaces to review-basis records', async () => {
    const review = {
      workspaceId: 'workspace-artifact',
      constructionArtifactId: 'artifact-123',
      openedAt: '2026-04-23T00:00:00Z',
      replay: createConstructionArtifactReplayResponse(),
    }
    const writes = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string }).id
              if (key) writes.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    const workspace = {
      id: 'workspace-artifact',
      name: 'Construction Artifact artifact-123',
      createdAt: '2026-04-23T00:00:00Z',
      updatedAt: '2026-04-23T00:00:00Z',
      rootNodeId: 'node-artifact',
      activeNodeId: 'node-artifact',
      source: {
        kind: 'persisted_construction_artifact' as const,
        constructionArtifactId: 'artifact-123',
        openedAt: '2026-04-23T00:00:00Z',
      },
    } satisfies PortfolioWorkspace
    const node = {
      id: 'node-artifact',
      workspaceId: 'workspace-artifact',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Construction Artifact Review',
      createdAt: '2026-04-23T00:00:00Z',
      changeSummary: { label: 'Construction Artifact Review', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: {
        snapshotVersion: 1 as const,
        baseCurrency: 'USD',
        importedMeta: { importer: null, statementPeriod: '2024-01-01 - 2024-12-31', importedAt: '2026-04-23T00:00:00Z', sourceFileNames: ['artifact-123'] },
        positions: [{ symbol: 'AAPL', marketValue: 0.6, quantity: null, currency: null, sector: null, sourceType: 'other' as const }],
        cashBalances: [],
        metadata: { benchmarkSymbol: 'SPY', notes: null, tags: ['persisted_construction_artifact_review'] },
      },
    } satisfies PortfolioNode

    const normalized = await portfolioWorkspaceStorage.normalizeLegacyPersistedConstructionArtifactWorkspaceCache({ workspace, node, review })

    expect(normalized.workspace.source).toMatchObject({
      kind: 'persisted_construction_artifact',
        reviewBasis: {
          basisKind: 'persisted_construction_artifact_review',
          previewHandoff: review.replay.review_basis!.preview_handoff,
        },
      })
    expect(normalized.node).toMatchObject({
      kind: 'artifact_review_basis',
      name: 'Artifact Review Basis',
      portfolioSnapshot: null,
    })
    expect(writes.get(`${portfolioDb.workspaceStoreName}:workspace-artifact`)).toBeTruthy()
    expect(writes.get(`${portfolioDb.portfolioNodeStoreName}:node-artifact`)).toBeTruthy()
  })

  it('creates and restores persisted optimizer handoff workspace reviews', async () => {
    const validation = createOptimizerHandoffValidationResponse()
    const replay = createOptimizerHandoffReplayResponse()
    const handoffReference = createOptimizerHandoffReference()
    const persisted = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      if (storeName === portfolioDb.persistedOptimizerHandoffReviewStoreName) {
        const store = {
          get(key: string) {
            const request = { ...requestTemplate, result: persisted.get(`${storeName}:${key}`) }
            queueMicrotask(() => request.onsuccess?.())
            return request
          },
        } as unknown as IDBObjectStore
        return new Promise((resolve, reject) => handler(store, resolve, reject))
      }
      return Promise.resolve(null as never)
    })

    const created = await portfolioWorkspaceStorage.createWorkspaceFromPersistedOptimizerHandoff({ handoffReference, validation, replay, openedAt: '2026-04-24T00:00:00Z' })

    expect(created.workspace.source).toMatchObject({
      kind: 'persisted_optimizer_handoff',
      handoffReference,
      reviewBasis: {
        basisKind: 'persisted_optimizer_handoff_review',
        canonicalSource: 'persisted_handoff_reference',
        basisProvenanceLabel: 'artifact_backed_review_basis',
        handoffReference,
      },
    })
    expect('handoffId' in created.workspace.source).toBe(false)
    expect('artifactId' in created.workspace.source).toBe(false)
    const createdWorkspaceSource = expectPersistedOptimizerHandoffSource(created.workspace.source)
    if (createdWorkspaceSource.reviewBasis) {
      expect('handoffId' in createdWorkspaceSource.reviewBasis).toBe(false)
      expect('artifactId' in createdWorkspaceSource.reviewBasis).toBe(false)
    }
    expect(created.rootNode.kind).toBe('artifact_review_basis')
    expect(created.rootNode.portfolioSnapshot).toBeNull()
    expect(created.review.validation.validation_status).toBe('ok')
    expect('handoffId' in created.review).toBe(false)
    expect('artifactId' in created.review).toBe(false)
    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview(created.workspace.id)).resolves.toMatchObject({
      workspaceId: created.workspace.id,
      handoffReference,
      reviewBasisSource: {
        canonical_source: 'persisted_handoff_reference',
        basis_provenance_label: 'artifact_backed_review_basis',
      },
      validation: { validation_status: 'ok' },
      replay: { handoff_id: 'optimizer_handoff_123' },
    })
    const persistedReview = persisted.get(`${portfolioDb.persistedOptimizerHandoffReviewStoreName}:${created.workspace.id}`) as Record<string, unknown>
    expect(persistedReview).toBeTruthy()
    expect('handoffId' in persistedReview).toBe(false)
    expect('artifactId' in persistedReview).toBe(false)
  })

  it('uses the same canonical optimizer handoff contract across create and save writes', async () => {
    const persisted = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, structuredClone(value))
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        put(value: unknown) {
          const key = (value as { workspaceId?: string }).workspaceId
          if (key) persisted.set(`${storeName}:${key}`, structuredClone(value))
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    const created = await portfolioWorkspaceStorage.createWorkspaceFromPersistedOptimizerHandoff({
      handoffReference: createOptimizerHandoffReference(),
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
      replay: createOptimizerHandoffReplayResponse(),
      openedAt: '2026-04-24T00:00:00Z',
    })
    const createdPersistedReview = structuredClone(
      persisted.get(`${portfolioDb.persistedOptimizerHandoffReviewStoreName}:${created.workspace.id}`),
    )

    await portfolioWorkspaceStorage.savePersistedOptimizerHandoffWorkspaceReview({
      ...created.review,
      validation: { ...created.review.validation, artifact_id: null },
      handoffId: created.review.handoffReference.handoff_id,
      artifactId: created.review.handoffReference.artifact_id,
    } as PersistedOptimizerHandoffWorkspaceReview)

    expect(persisted.get(`${portfolioDb.persistedOptimizerHandoffReviewStoreName}:${created.workspace.id}`)).toEqual(createdPersistedReview)
    expect(createdPersistedReview).toEqual({
      workspaceId: created.workspace.id,
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
      reviewBasisSource: {
        basis_version: 1,
        basis_kind: 'persisted_optimizer_handoff_review',
        review_scope: 'workspace_review_only',
        canonical_source: 'persisted_handoff_reference',
        basis_provenance_label: 'artifact_backed_review_basis',
        portfolio_truth: 'imported_portfolio_snapshot',
        candidate_truth: 'hypothetical_optimizer_handoff',
        handoff_reference: createOptimizerHandoffReference(),
        benchmark_symbol: 'SPY',
        base_currency: 'USD',
        replay_window: { start_date: '2024-01-01', end_date: '2024-12-31' },
        baseline_weights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
        candidate_weights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
      },
      replay: createOptimizerHandoffReplayResponse(),
    })
  })

  it('fails closed when construction artifact review payload is missing canonical review_basis', async () => {
    await expect(portfolioWorkspaceStorage.createWorkspaceFromPersistedConstructionArtifact({
      constructionArtifactId: 'artifact-123',
      replay: {
        ...createConstructionArtifactReplayResponse(),
        review_basis: undefined,
      } as unknown as ConstructionArtifactReplayResponse,
    })).rejects.toThrow('Persisted construction artifact review payload is missing canonical review_basis')
  })

  it('fails closed when construction artifact review payload review_basis preview handoff is missing', async () => {
    await expect(portfolioWorkspaceStorage.createWorkspaceFromPersistedConstructionArtifact({
      constructionArtifactId: 'artifact-123',
      replay: {
        ...createConstructionArtifactReplayResponse(),
        review_basis: {
          ...createConstructionArtifactReplayResponse().review_basis!,
          preview_handoff: undefined,
        },
      } as unknown as ConstructionArtifactReplayResponse,
    })).rejects.toThrow('Persisted construction artifact review payload review_basis is missing canonical preview handoff')
  })

  it('fails closed when construction artifact review payload review_basis preview handoff conflicts with canonical replay params', async () => {
    await expect(portfolioWorkspaceStorage.createWorkspaceFromPersistedConstructionArtifact({
      constructionArtifactId: 'artifact-123',
      replay: {
        ...createConstructionArtifactReplayResponse(),
        review_basis: {
          ...createConstructionArtifactReplayResponse().review_basis!,
          preview_handoff: {
            ...createConstructionArtifactReplayResponse().review_basis!.preview_handoff,
            effective_replay_params: {
              ...createConstructionArtifactReplayResponse().review_basis!.preview_handoff.effective_replay_params,
              benchmark_symbol: 'QQQ',
            },
          },
        },
      },
    })).rejects.toThrow('Persisted construction artifact review payload review_basis preview handoff conflicts with canonical replay params')
  })

  it('fails closed when optimizer handoff review payload is missing canonical review_basis', async () => {
    await expect(portfolioWorkspaceStorage.createWorkspaceFromPersistedOptimizerHandoff({
      handoffReference: createOptimizerHandoffReference(),
      validation: createOptimizerHandoffValidationResponse(),
      replay: {
        ...createOptimizerHandoffReplayResponse(),
        review_basis: undefined,
      } as unknown as OptimizerHandoffReplayResponse,
    })).rejects.toThrow('Persisted optimizer handoff review payload is missing canonical review_basis')
  })

  it('repairs legacy optimizer handoff cache identities at load time only', async () => {
    const legacyReview = {
      workspaceId: 'workspace-optimizer',
      handoffId: 'optimizer_handoff_123',
      artifactId: 'optimizer_artifact_123',
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
      replay: createOptimizerHandoffReplayResponse(),
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: legacyReview as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')).resolves.toMatchObject({
      handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
      validation: { artifact_id: null },
    })
    const restored = await portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')
    expect(restored).toBeTruthy()
    expect(restored && 'handoffId' in restored).toBe(false)
    expect(restored && 'artifactId' in restored).toBe(false)
  })

  it('fails closed when persisted optimizer handoff cache is missing a valid canonical handoff reference', async () => {
    const badReview = {
      workspaceId: 'workspace-optimizer',
      handoffReference: {
        reference_kind: 'optimizer_handoff_reference_v1',
        handoff_id: 'optimizer_handoff_123',
        artifact_id: '',
        manifest_path: '/tmp/optimizer_handoff_123/manifest.json',
        artifact_path: '/tmp/optimizer_handoff_123/artifact.json',
      },
      openedAt: '2026-04-24T00:00:00Z',
      validation: createOptimizerHandoffValidationResponse(),
      replay: createOptimizerHandoffReplayResponse(),
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badReview as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')).rejects.toThrow(
      'Persisted optimizer handoff review cache is missing or invalid handoff reference',
    )
  })

  it('fails closed when persisted optimizer handoff cache replay identity mismatches the reference', async () => {
    const badReview = {
      workspaceId: 'workspace-optimizer',
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: createOptimizerHandoffValidationResponse(),
      replay: { ...createOptimizerHandoffReplayResponse(), handoff_id: 'optimizer_handoff_other' },
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badReview as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')).rejects.toThrow(
      'Persisted optimizer handoff review cache is inconsistent with replay identity',
    )
  })

  it('fails closed before saving optimizer handoff reviews when validation artifact identity mismatches', async () => {
    const persisted = new Map<string, unknown>()
    const withStoreSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        put(value: unknown) {
          const key = (value as { workspaceId?: string }).workspaceId
          if (key) persisted.set(`${storeName}:${key}`, value)
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.savePersistedOptimizerHandoffWorkspaceReview(
      createPersistedOptimizerHandoffWorkspaceReview({
        validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: 'optimizer_artifact_other' },
      }),
    )).rejects.toThrow('Persisted optimizer handoff review cache is inconsistent with validation artifact identity')

    expect(withStoreSpy).not.toHaveBeenCalled()
    expect(persisted.size).toBe(0)
  })

  it('fails closed when persisted optimizer handoff cache is missing the canonical replay objective', async () => {
    const badReview = {
      workspaceId: 'workspace-optimizer',
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: createOptimizerHandoffValidationResponse(),
      replay: {
        ...createOptimizerHandoffReplayResponse(),
        optimizer_context: {
          ...createOptimizerHandoffReplayResponse().optimizer_context!,
          objective: null,
        },
      },
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badReview as unknown }
      const store = {
        get(_key: string) {
          const request = { ...requestTemplate }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getPersistedOptimizerHandoffWorkspaceReview('workspace-optimizer')).rejects.toThrow(
      'Persisted optimizer handoff review cache is missing replay optimizer objective',
    )
  })

  it('fails closed before creating optimizer handoff workspaces when replay identity mismatches', async () => {
    const persisted = new Map<string, unknown>()
    const withStoresSpy = vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) persisted.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.createWorkspaceFromPersistedOptimizerHandoff({
      handoffReference: createOptimizerHandoffReference(),
      validation: createOptimizerHandoffValidationResponse(),
      replay: { ...createOptimizerHandoffReplayResponse(), handoff_id: 'optimizer_handoff_other' },
      openedAt: '2026-04-24T00:00:00Z',
    })).rejects.toThrow('Persisted optimizer handoff review cache is inconsistent with replay identity')

    expect(withStoresSpy).not.toHaveBeenCalled()
    expect(persisted.size).toBe(0)
  })

  it('normalizes legacy cached optimizer handoff workspaces to handoff-centric review records', async () => {
    const review = {
      workspaceId: 'workspace-optimizer',
      handoffId: 'optimizer_handoff_123',
      artifactId: 'optimizer_artifact_123',
      handoffReference: createOptimizerHandoffReference(),
      openedAt: '2026-04-24T00:00:00Z',
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
      replay: createOptimizerHandoffReplayResponse(),
    }
    const writes = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) writes.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    const workspace = {
      id: 'workspace-optimizer',
      name: 'Optimizer Handoff optimizer_handoff_123',
      createdAt: '2026-04-24T00:00:00Z',
      updatedAt: '2026-04-24T00:00:00Z',
      rootNodeId: 'node-optimizer',
      activeNodeId: 'node-optimizer',
      source: {
        kind: 'persisted_optimizer_handoff' as const,
        handoffId: 'optimizer_handoff_123',
        artifactId: 'optimizer_artifact_123',
        handoffReference: createOptimizerHandoffReference(),
        openedAt: '2026-04-24T00:00:00Z',
        reviewBasis: {
          basisVersion: 1 as const,
          basisKind: 'persisted_optimizer_handoff_review' as const,
          reviewScope: 'workspace_review_only' as const,
          canonicalSource: 'persisted_handoff_reference' as const,
          basisProvenanceLabel: 'artifact_backed_review_basis' as const,
          portfolioTruth: 'imported_portfolio_snapshot' as const,
          candidateTruth: 'hypothetical_optimizer_handoff' as const,
          handoffId: 'optimizer_handoff_123',
          artifactId: 'optimizer_artifact_123',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          benchmarkSymbol: 'SPY',
          baseCurrency: 'USD',
          replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
          baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
          candidateWeights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
        },
      },
    } as unknown as PortfolioWorkspace
    const node = {
      id: 'node-optimizer',
      workspaceId: 'workspace-optimizer',
      parentId: null,
      kind: 'imported_base' as const,
      name: 'Optimizer Handoff Review',
      createdAt: '2026-04-24T00:00:00Z',
      changeSummary: { label: 'Optimizer Handoff Review', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
      portfolioSnapshot: null,
      artifactReviewBasis: {
        basisVersion: 1 as const,
        basisKind: 'persisted_optimizer_handoff_review' as const,
        reviewScope: 'workspace_review_only' as const,
        canonicalSource: 'persisted_handoff_reference' as const,
        basisProvenanceLabel: 'artifact_backed_review_basis' as const,
        portfolioTruth: 'imported_portfolio_snapshot' as const,
        candidateTruth: 'hypothetical_optimizer_handoff' as const,
        handoffId: 'optimizer_handoff_123',
        artifactId: 'optimizer_artifact_123',
        handoffReference: createOptimizerHandoffReference(),
        openedAt: '2026-04-24T00:00:00Z',
        benchmarkSymbol: 'SPY',
        baseCurrency: 'USD',
        replayWindow: { startDate: '2024-01-01', endDate: '2024-12-31' },
        baselineWeights: [{ symbol: 'AAA', target_weight: 0.6 }, { symbol: 'BBB', target_weight: 0.4 }],
        candidateWeights: [{ symbol: 'AAA', target_weight: 0.5 }, { symbol: 'BBB', target_weight: 0.3 }, { symbol: 'CCC', target_weight: 0.2 }],
      },
    } as unknown as PortfolioNode

    const normalized = await portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({ workspace, node, review })

    expect(normalized.workspace.source).toMatchObject({
      kind: 'persisted_optimizer_handoff',
      handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
      reviewBasis: {
        basisKind: 'persisted_optimizer_handoff_review',
        handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
      },
    })
    expect(normalized.node).toMatchObject({
      kind: 'artifact_review_basis',
      name: 'Artifact Review Basis',
      portfolioSnapshot: null,
      artifactReviewBasis: {
        basisKind: 'persisted_optimizer_handoff_review',
        handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
      },
    })
    expect(normalized.review).toMatchObject({
      handoffReference: { handoff_id: 'optimizer_handoff_123', artifact_id: 'optimizer_artifact_123' },
    })
    expect('handoffId' in normalized.workspace.source).toBe(false)
    expect('artifactId' in normalized.workspace.source).toBe(false)
    const normalizedWorkspaceSource = expectPersistedOptimizerHandoffSource(normalized.workspace.source)
    if (normalizedWorkspaceSource.reviewBasis) {
      expect('handoffId' in normalizedWorkspaceSource.reviewBasis).toBe(false)
      expect('artifactId' in normalizedWorkspaceSource.reviewBasis).toBe(false)
    }
    expect(normalized.node.artifactReviewBasis && 'handoffId' in normalized.node.artifactReviewBasis).toBe(false)
    expect(normalized.node.artifactReviewBasis && 'artifactId' in normalized.node.artifactReviewBasis).toBe(false)
    expect(writes.get(`${portfolioDb.workspaceStoreName}:workspace-optimizer`)).toBeTruthy()
    expect(writes.get(`${portfolioDb.portfolioNodeStoreName}:workspace-optimizer`)).toBeTruthy()
  })

  it('repairs missing optimizer handoff reviewBasis but only for documented legacy cache cases', async () => {
    const review = createPersistedOptimizerHandoffWorkspaceReview({
      validation: { ...createOptimizerHandoffValidationResponse(), artifact_id: null },
    })
    const writes = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStores').mockImplementation(async (_storeNames, _mode, handler) => {
      const transaction = {
        objectStore(name: string) {
          return {
            put(value: unknown) {
              const key = (value as { id?: string; workspaceId?: string }).workspaceId ?? (value as { id?: string }).id
              if (key) writes.set(`${name}:${key}`, value)
              const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBTransaction
      return new Promise((resolve, reject) => handler(transaction, resolve, reject))
    })

    const normalized = await portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
        artifactReviewBasis: null,
      } as unknown as PortfolioNode,
      review,
    })

    expect(normalized.workspace.source).toMatchObject({
      kind: 'persisted_optimizer_handoff',
      reviewBasis: {
        basisKind: 'persisted_optimizer_handoff_review',
        handoffReference: createOptimizerHandoffReference(),
      },
    })
    expect(normalized.node.artifactReviewBasis).toMatchObject({
      basisKind: 'persisted_optimizer_handoff_review',
      handoffReference: createOptimizerHandoffReference(),
    })
    expect(writes.get(`${portfolioDb.workspaceStoreName}:workspace-optimizer`)).toBeTruthy()
    expect(writes.get(`${portfolioDb.portfolioNodeStoreName}:workspace-optimizer`)).toBeTruthy()
  })

  it('fails closed when present optimizer workspace reviewBasis has the wrong basis kind', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            basisKind: 'persisted_construction_artifact_review',
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis has unsupported basis kind')
  })

  it('fails closed when present construction workspace reviewBasis has the wrong basis kind', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedConstructionArtifactWorkspaceCache({
      workspace: {
        id: 'workspace-artifact',
        name: 'Construction Artifact artifact-123',
        createdAt: '2026-04-23T00:00:00Z',
        updatedAt: '2026-04-23T00:00:00Z',
        rootNodeId: 'node-artifact',
        activeNodeId: 'node-artifact',
        source: {
          kind: 'persisted_construction_artifact',
          constructionArtifactId: 'artifact-123',
          openedAt: '2026-04-23T00:00:00Z',
          reviewBasis: {
            ...createConstructionArtifactWorkspaceReviewBasisFixture(),
            basisKind: 'persisted_optimizer_handoff_review',
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-artifact',
        workspaceId: 'workspace-artifact',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-23T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: { workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay: createConstructionArtifactReplayResponse() },
    })).rejects.toThrow('Persisted construction artifact workspace review basis has unsupported basis kind')
  })

  it('fails closed when present construction workspace reviewBasis conflicts with canonical persisted review data', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedConstructionArtifactWorkspaceCache({
      workspace: {
        id: 'workspace-artifact',
        name: 'Construction Artifact artifact-123',
        createdAt: '2026-04-23T00:00:00Z',
        updatedAt: '2026-04-23T00:00:00Z',
        rootNodeId: 'node-artifact',
        activeNodeId: 'node-artifact',
        source: {
          kind: 'persisted_construction_artifact',
          constructionArtifactId: 'artifact-123',
          openedAt: '2026-04-23T00:00:00Z',
          reviewBasis: {
            ...createConstructionArtifactWorkspaceReviewBasisFixture(),
            benchmarkSymbol: 'QQQ',
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-artifact',
        workspaceId: 'workspace-artifact',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-23T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: { workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay: createConstructionArtifactReplayResponse() },
    })).rejects.toThrow('Persisted construction artifact workspace review basis conflicts with canonical persisted review')
  })

  it('fails closed when present construction node reviewBasis conflicts with canonical persisted review data', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedConstructionArtifactWorkspaceCache({
      workspace: {
        id: 'workspace-artifact',
        name: 'Construction Artifact artifact-123',
        createdAt: '2026-04-23T00:00:00Z',
        updatedAt: '2026-04-23T00:00:00Z',
        rootNodeId: 'node-artifact',
        activeNodeId: 'node-artifact',
        source: {
          kind: 'persisted_construction_artifact',
          constructionArtifactId: 'artifact-123',
          openedAt: '2026-04-23T00:00:00Z',
          reviewBasis: createConstructionArtifactWorkspaceReviewBasisFixture(),
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-artifact',
        workspaceId: 'workspace-artifact',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-23T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 1, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
        artifactReviewBasis: {
          ...createConstructionArtifactWorkspaceReviewBasisFixture(),
          candidateWeights: [{ symbol: 'QQQ', target_weight: 1 }],
        },
      } as unknown as PortfolioNode,
      review: { workspaceId: 'workspace-artifact', constructionArtifactId: 'artifact-123', openedAt: '2026-04-23T00:00:00Z', replay: createConstructionArtifactReplayResponse() },
    })).rejects.toThrow('Persisted construction artifact node review basis conflicts with canonical persisted review')
  })

  it('fails closed when present optimizer workspace reviewBasis has the wrong basis version', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            basisVersion: 2,
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis has unsupported basis version')
  })

  it('fails closed when present optimizer workspace reviewBasis has an invalid handoff reference', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            handoffReference: {
              ...createOptimizerHandoffReference(),
              artifact_id: '',
            },
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis is missing or invalid handoff reference')
  })

  it('fails closed when present optimizer workspace reviewBasis mixes canonical and partial legacy identity fields', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            handoffId: 'optimizer_handoff_123',
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis has partial legacy identity fields')
  })

  it('fails closed when present optimizer workspace reviewBasis conflicts with canonical persisted review data', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
          reviewBasis: {
            ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
            benchmarkSymbol: 'QQQ',
          },
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff workspace review basis conflicts with canonical persisted review')
  })

  it('fails closed when present optimizer node reviewBasis conflicts with canonical persisted review data', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
        },
      } as unknown as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
        artifactReviewBasis: {
          ...createOptimizerHandoffWorkspaceReviewBasisFixture(),
          candidateWeights: [{ symbol: 'DDD', target_weight: 0.2 }],
        },
      } as unknown as PortfolioNode,
      review: createPersistedOptimizerHandoffWorkspaceReview(),
    })).rejects.toThrow('Persisted optimizer handoff node review basis conflicts with canonical persisted review')
  })

  it('fails closed when legacy optimizer workspace source identity conflicts with the handoff reference', async () => {
    await expect(portfolioWorkspaceStorage.normalizeLegacyPersistedOptimizerHandoffWorkspaceCache({
      workspace: {
        id: 'workspace-optimizer',
        name: 'Optimizer Handoff optimizer_handoff_123',
        createdAt: '2026-04-24T00:00:00Z',
        updatedAt: '2026-04-24T00:00:00Z',
        rootNodeId: 'node-optimizer',
        activeNodeId: 'node-optimizer',
        source: {
          kind: 'persisted_optimizer_handoff',
          handoffId: 'optimizer_handoff_other',
          handoffReference: createOptimizerHandoffReference(),
          openedAt: '2026-04-24T00:00:00Z',
        },
      } as PortfolioWorkspace,
      node: {
        id: 'node-optimizer',
        workspaceId: 'workspace-optimizer',
        parentId: null,
        kind: 'artifact_review_basis',
        name: 'Artifact Review Basis',
        createdAt: '2026-04-24T00:00:00Z',
        changeSummary: { label: 'Artifact Review Basis', changedPositionsCount: 3, changedSectorsCount: 0, grossExposureDelta: null, netCapitalDelta: null },
        portfolioSnapshot: null,
      } as PortfolioNode,
      review: {
        workspaceId: 'workspace-optimizer',
        handoffReference: createOptimizerHandoffReference(),
        openedAt: '2026-04-24T00:00:00Z',
        validation: createOptimizerHandoffValidationResponse(),
        replay: createOptimizerHandoffReplayResponse(),
      },
    })).rejects.toThrow('Persisted optimizer handoff workspace source has partial legacy identity fields')
  })

  it('persists and overwrites candidate improvement draft annotations by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveCandidateImprovementDraft').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft')
      .mockResolvedValueOnce({
        workspaceId: 'workspace-1',
        draftId: 'draft-1',
        baseNodeId: 'node-1',
        seed: {
          kind: 'etf_replacement_candidate',
          source: 'etf_ranking',
          seededAt: '2026-04-16T00:00:00Z',
          baseSymbol: 'IWDA',
          candidateSymbol: 'IUHC',
          candidateRank: 2,
          peerGroup: 'Sector UCITS ETF',
          benchmarkSymbol: 'SPY',
          lookbackMonths: 6,
          rankingId: 'etf_ranking_engine_v1',
          methodologyId: 'etf_ranking_methodology_v1',
          rankingBasisDate: '2026-04-16',
          confidence: 'high',
          holdingsSupport: 'sample',
          requestUniverse: ['IWDA', 'IUHC'],
          evaluatedUniverse: ['IUHC'],
          warningCount: 0,
          excludedSymbolsCount: 1,
        },
      })

    await portfolioWorkspaceStorage.saveCandidateImprovementDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'VUAA',
        candidateSymbol: 'IUFS',
        candidateRank: 1,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-15',
        confidence: 'medium',
        holdingsSupport: 'mixed',
        requestUniverse: ['VUAA', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })

    await portfolioWorkspaceStorage.saveCandidateImprovementDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-16T00:00:00Z',
        baseSymbol: 'IWDA',
        candidateSymbol: 'IUHC',
        candidateRank: 2,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-16',
        confidence: 'high',
        holdingsSupport: 'sample',
        requestUniverse: ['IWDA', 'IUHC'],
        evaluatedUniverse: ['IUHC'],
        warningCount: 0,
        excludedSymbolsCount: 1,
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(2)
    expect(await portfolioWorkspaceStorage.getCandidateImprovementDraft('draft-1')).toMatchObject({
      draftId: 'draft-1',
      seed: {
        baseSymbol: 'IWDA',
        candidateSymbol: 'IUHC',
        candidateRank: 2,
        confidence: 'high',
      },
    })
  })

  it('deletes and clears candidate improvement draft annotations separately from portfolio truth', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveCandidateImprovementDraft').mockResolvedValue()
    const deleteSpy = vi.spyOn(portfolioWorkspaceStorage, 'deleteCandidateImprovementDraft').mockResolvedValue()
    const clearSpy = vi.spyOn(portfolioWorkspaceStorage, 'clearPortfolioWorkspaceState').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getCandidateImprovementDraft')
      .mockResolvedValueOnce(null)
      .mockResolvedValueOnce(null)

    await portfolioWorkspaceStorage.saveCandidateImprovementDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'VUAA',
        candidateSymbol: 'IUFS',
        candidateRank: 1,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-15',
        confidence: 'medium',
        holdingsSupport: 'mixed',
        requestUniverse: ['VUAA', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })

    await portfolioWorkspaceStorage.deleteCandidateImprovementDraft('draft-1')
    expect(deleteSpy).toHaveBeenCalledWith('draft-1')
    expect(await portfolioWorkspaceStorage.getCandidateImprovementDraft('draft-1')).toBeNull()

    await portfolioWorkspaceStorage.saveCandidateImprovementDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-2',
      baseNodeId: 'node-2',
      seed: {
        kind: 'etf_replacement_candidate',
        source: 'etf_ranking',
        seededAt: '2026-04-15T00:00:00Z',
        baseSymbol: 'VUAA',
        candidateSymbol: 'IUFS',
        candidateRank: 1,
        peerGroup: 'Sector UCITS ETF',
        benchmarkSymbol: 'SPY',
        lookbackMonths: 6,
        rankingId: 'etf_ranking_engine_v1',
        methodologyId: 'etf_ranking_methodology_v1',
        rankingBasisDate: '2026-04-15',
        confidence: 'medium',
        holdingsSupport: 'mixed',
        requestUniverse: ['VUAA', 'IUFS'],
        evaluatedUniverse: ['IUFS'],
        warningCount: 1,
        excludedSymbolsCount: 0,
      },
    })

    await portfolioWorkspaceStorage.clearPortfolioWorkspaceState()
    expect(clearSpy).toHaveBeenCalled()
    expect(saveSpy).toHaveBeenCalledTimes(2)
    expect(await portfolioWorkspaceStorage.getCandidateImprovementDraft('draft-2')).toBeNull()
  })

  it('clears candidate improvement draft annotation when recreating a fresh draft from a node', async () => {
    const getNodeSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation((storeName) => {
      if (storeName === portfolioDb.portfolioNodeStoreName) {
        return Promise.resolve({
          id: 'node-1',
          workspaceId: 'workspace-1',
          parentId: null,
          kind: 'imported_base',
          name: 'Base Import',
          createdAt: '2026-04-10T00:00:00Z',
          changeSummary: {
            label: 'Base Import',
            changedPositionsCount: 1,
            changedSectorsCount: 1,
            grossExposureDelta: 10000,
            netCapitalDelta: 10000,
          },
          portfolioSnapshot: {
            snapshotVersion: 1,
            baseCurrency: 'USD',
            importedMeta: {
              importer: 'interactive_brokers',
              statementPeriod: '2025-01-01 - 2025-12-31',
              importedAt: '2026-04-10T00:00:00Z',
              sourceFileNames: ['IB2025.pdf'],
            },
            positions: [{ symbol: 'AAPL', marketValue: 10000, quantity: 10, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
            cashBalances: [{ currency: 'USD', amount: 1000 }],
            metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
          },
        })
      }
      if (storeName === portfolioDb.workingDraftStoreName) {
        return Promise.resolve({
          id: 'draft-1',
          workspaceId: 'workspace-1',
          baseNodeId: 'node-legacy',
          updatedAt: '2026-04-10T00:00:00Z',
          name: 'Working Draft',
          status: 'dirty',
          portfolioSnapshot: {
            snapshotVersion: 1,
            baseCurrency: 'USD',
            importedMeta: {
              importer: 'interactive_brokers',
              statementPeriod: '2025-01-01 - 2025-12-31',
              importedAt: '2026-04-10T00:00:00Z',
              sourceFileNames: ['IB2025.pdf'],
            },
            positions: [{ symbol: 'MSFT', marketValue: 9000, quantity: 9, currency: 'USD', sector: 'Technology', sourceType: 'equity' }],
            cashBalances: [{ currency: 'USD', amount: 500 }],
            metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
          },
        })
      }
      return Promise.resolve(undefined)
    })
    const draft = await portfolioWorkspaceStorage.createDraftFromNode({ workspaceId: 'workspace-1', baseNodeId: 'node-1' })

    expect(getNodeSpy).toHaveBeenCalled()
    expect(getNodeSpy.mock.calls.some((call) => call[0] === portfolioDb.candidateImprovementDraftStoreName && call[1] === 'readwrite')).toBe(true)
    expect(draft).toMatchObject({
      id: 'draft-1',
      workspaceId: 'workspace-1',
      baseNodeId: 'node-1',
      status: 'clean',
    })
  })

  it('persists and restores intent-bound seeded ETF replacement ranking artifacts by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getIntentBoundSeededEtfReplacementRankingDraft').mockResolvedValue({
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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
    })

    await portfolioWorkspaceStorage.saveIntentBoundSeededEtfReplacementRankingDraft({
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).toMatchObject({
      draftId: 'draft-1',
      baseSymbol: 'AAPL',
      candidateSymbol: 'IUFS',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('fails closed on malformed cached monitor definition alert review state', async () => {
    vi.spyOn(portfolioDb, 'withStore').mockImplementation((storeName, _mode, callback) => {
      if (storeName === portfolioDb.workspaceStateStoreName) {
        const store = {
          get: () => {
            const request: Record<string, unknown> = {}
            queueMicrotask(() => {
              request.result = {
                workspaceId: 'workspace-1',
                activeNodeId: 'node-1',
                activeDraftId: 'draft-1',
                selectedExposureSnapshotId: 'draft',
                monitorDefinitionAlertReview: {
                  source: 'definition_scoped_alert_review_timeline',
                  monitorDefinitionId: '',
                  openedAt: '2026-04-10T00:05:00Z',
                  selectedEvent: { eventKind: 'latest_observation_event', observationId: 'monitor_definition_observation_abc12345' },
                  cachedTimeline: {},
                },
                lastOpenedAt: '2026-04-10T00:00:00Z',
              }
              ;(request.onsuccess as (() => void) | undefined)?.()
            })
            return request
          },
        }
        return new Promise((resolve, reject) => callback(store as never, resolve, reject))
      }
      return Promise.resolve(undefined)
    })

    await expect(portfolioWorkspaceStorage.getWorkspaceState('workspace-1')).rejects.toThrow('Workspace state monitorDefinitionAlertReview monitorDefinitionId is invalid')
  })

  it('uses the same canonical seeded ranking contract across save and restore', async () => {
    const persisted = new Map<string, unknown>()
    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const store = {
        put(value: unknown) {
          const key = (value as { draftId?: string }).draftId
          if (key) persisted.set(`${storeName}:${key}`, structuredClone(value))
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
        get(key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: persisted.get(`${storeName}:${key}`) }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await portfolioWorkspaceStorage.saveIntentBoundSeededEtfReplacementRankingDraft({
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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
    })

    expect(persisted.get(`${portfolioDb.intentBoundSeededEtfReplacementRankingDraftStoreName}:draft-1`)).toEqual({
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).resolves.toMatchObject({
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
    })
  })

  it('hydrates only documented seeded ranking legacy omissions at load time', async () => {
    const legacyDraft = {
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
      warnings: ['warning'],
      excludedSymbols: [{ symbol: 'VDST', reason: 'excluded' }],
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: legacyDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).resolves.toMatchObject({
      openHandoff: {
        artifact_id: 'etf_ranking_artifact_sector_1',
        artifact_kind: 'etf_ranking',
        schema_version: 'etf_ranking_artifact_v1',
      },
    })
  })

  it('allows documented legacy seeded ranking cache reads that omit mirrored artifact identity fields', async () => {
    const badDraft = {
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
      warnings: [],
      excludedSymbols: [],
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).resolves.toMatchObject({
      openHandoff: {
        artifact_id: 'etf_ranking_artifact_sector_1',
        artifact_kind: 'etf_ranking',
        schema_version: 'etf_ranking_artifact_v1',
      },
    })
  })

  it('fails closed when seeded ranking cache is missing a valid typed open handoff', async () => {
    const badDraft = {
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
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      peerGroup: 'Sector UCITS ETF',
      confidence: 'medium',
      holdingsSupport: 'mixed',
      requestUniverse: ['AAPL', 'IUFS'],
      evaluatedUniverse: ['IUFS'],
      warnings: [],
      excludedSymbols: [],
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache is missing or invalid open handoff',
    )
  })

  it('fails closed when seeded ranking cache has unsupported open handoff kind', async () => {
    const badDraft = {
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
        handoff_kind: 'ranking_artifact_open_handoff_v2',
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
      warnings: [],
      excludedSymbols: [],
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache has unsupported open handoff kind',
    )
  })

  it('fails closed when seeded ranking cache has unsupported open handoff schema version', async () => {
    const badDraft = {
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
        schema_version: 'intent_bound_etf_replacement_ranking_artifact_v1',
      },
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      peerGroup: 'Sector UCITS ETF',
      confidence: 'medium',
      holdingsSupport: 'mixed',
      requestUniverse: ['AAPL', 'IUFS'],
      evaluatedUniverse: ['IUFS'],
      warnings: [],
      excludedSymbols: [],
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache has unsupported open handoff schema version',
    )
  })

  it('fails closed when seeded ranking cache has contradictory present legacy mirrored fields', async () => {
    const badDraft = {
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
      artifactId: 'etf_ranking_artifact_sector_1',
      artifactKind: 'intent_bound_etf_replacement_ranking',
      schemaVersion: 'intent_bound_etf_replacement_ranking_artifact_v1',
      openHandoff: {
        handoff_kind: 'ranking_artifact_open_handoff_v1',
        artifact_kind: 'etf_ranking',
        artifact_id: 'etf_ranking_artifact_sector_1',
        schema_version: 'etf_ranking_artifact_v1',
      },
      reviewPayloadKind: 'intent_bound_etf_replacement_ranking_review_payload_v1',
      benchmarkSymbol: 'SPY',
      lookbackMonths: 6,
      peerGroup: 'Sector UCITS ETF',
      confidence: 'medium',
      holdingsSupport: 'mixed',
      requestUniverse: ['AAPL', 'IUFS'],
      evaluatedUniverse: ['IUFS'],
      warnings: [],
      excludedSymbols: [],
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
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache conflicts with open handoff artifact kind',
    )
  })

  it('fails closed when seeded ranking cache carries unsupported consumer handoff state', async () => {
    const badDraft = {
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
      warnings: [],
      excludedSymbols: [],
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
      consumerHandoff: {
        handoff_kind: 'intent_bound_etf_replacement_ranking_consumer_handoff_v1',
      },
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        get(_key: string) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: badDraft as unknown }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getIntentBoundSeededEtfReplacementRankingDraft('draft-1')).rejects.toThrow(
      'Persisted seeded ranking review cache has unsupported consumer handoff state',
    )
  })

  it('fails closed when saving seeded ranking cache with contradictory present review payload state', async () => {
    const withStoreSpy = vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const store = {
        put(_value: unknown) {
          const request = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null }
          queueMicrotask(() => request.onsuccess?.())
          return request
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.saveIntentBoundSeededEtfReplacementRankingDraft({
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
      warnings: [],
      excludedSymbols: [],
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
    })).resolves.toBeUndefined()

    expect(withStoreSpy).toHaveBeenCalledOnce()
  })

  it('persists hypothetical replay drafts by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveHypotheticalReplacementReplayDraft').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getHypotheticalReplacementReplayDraft').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: {
        proposal: { source: 'draft_replacement_intent', proposal_source: { proposal_source_version: 1, proposal_source_kind: 'draft_replacement_intent_review_only', proposal_truth: 'review_only_hypothetical_proposal', portfolio_truth: 'draft_snapshot_not_applied', review_scope: 'proposal_review_context_only' }, incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          methodology_provenance: { provenance_version: 1, source: 'portfolio_allocation_backtest_engine', methodology_truth: 'review_only_replay_methodology', assumptions_truth: 'review_only_replay_assumptions', analytics_truth: 'hypothetical_replay_analytics_only', review_scope: 'workspace_review_context_only' },
          investor_economics_status: availableInvestorEconomicsStatus,
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
            assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
            status: 'ok',
            investor_economics_status: availableInvestorEconomicsStatus,
            instrument_metadata: [],
            starting_weights: [],
            ending_weights: [],
            metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
            equity_curve: [],
            rebalance_events: [],
            trades: [],
          },
          comparison: null,
          reference_diagnostics: null,
          candidate_diagnostics: null,
          diagnostics_comparison: null,
        },
        warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
      },
    })

    await portfolioWorkspaceStorage.saveHypotheticalReplacementReplayDraft({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      replay: {
        proposal: { source: 'draft_replacement_intent', proposal_source: { proposal_source_version: 1, proposal_source_kind: 'draft_replacement_intent_review_only', proposal_truth: 'review_only_hypothetical_proposal', portfolio_truth: 'draft_snapshot_not_applied', review_scope: 'proposal_review_context_only' }, incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          methodology_provenance: { provenance_version: 1, source: 'portfolio_allocation_backtest_engine', methodology_truth: 'review_only_replay_methodology', assumptions_truth: 'review_only_replay_assumptions', analytics_truth: 'hypothetical_replay_analytics_only', review_scope: 'workspace_review_context_only' },
          investor_economics_status: availableInvestorEconomicsStatus,
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
            assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
            status: 'ok',
            investor_economics_status: availableInvestorEconomicsStatus,
            instrument_metadata: [],
            starting_weights: [],
            ending_weights: [],
            metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
            equity_curve: [],
            rebalance_events: [],
            trades: [],
          },
          comparison: null,
          reference_diagnostics: null,
          candidate_diagnostics: null,
          diagnostics_comparison: null,
        },
        warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getHypotheticalReplacementReplayDraft('draft-1')).toMatchObject({
      draftId: 'draft-1',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('persists formed candidate artifacts by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveFormedCandidateArtifact').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getFormedCandidateArtifact').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      formation: {
        formation: { kind: 'single_replacement_candidate_formation', status: 'ok' },
        proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        formation_summary: { incumbent_start_weight: 1, candidate_start_weight: 1, unchanged_positions_count: 0, baseline_positions_count: 1, candidate_positions_count: 1, starting_turnover_pct: 1 },
        truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
        warnings: [],
        rejection_reason: null,
      },
    })

    await portfolioWorkspaceStorage.saveFormedCandidateArtifact({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      formation: {
        formation: { kind: 'single_replacement_candidate_formation', status: 'ok' },
        proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        formation_summary: { incumbent_start_weight: 1, candidate_start_weight: 1, unchanged_positions_count: 0, baseline_positions_count: 1, candidate_positions_count: 1, starting_turnover_pct: 1 },
        truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
        warnings: [],
        rejection_reason: null,
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getFormedCandidateArtifact('draft-1')).toMatchObject({
      draftId: 'draft-1',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('persists constructed candidate artifacts by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveConstructedCandidateArtifact').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getConstructedCandidateArtifact').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      constructionRuleId: 'same_weight_substitution_v1',
      construction: {
        construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'same_weight_substitution_v1' },
        proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
        inputs: { baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], construction_rule: 'same_weight_substitution_v1', incumbent_start_weight: 1 },
        outputs: { candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }], starting_turnover_pct: 1, unchanged_positions_count: 0 },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', construction_basis: 'explicit_single_replacement_rule', cash_treatment: 'excluded_from_construction_basis', position_scope: 'positive_market_value_positions_only' },
        truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', note: 'Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.' },
        warnings: [],
        rejection_reason: null,
      },
    })

    await portfolioWorkspaceStorage.saveConstructedCandidateArtifact({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
      replacementIntentBaseSymbol: 'AAPL',
      replacementIntentCandidateSymbol: 'IUFS',
      constructionRuleId: 'same_weight_substitution_v1',
      construction: {
        construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'same_weight_substitution_v1' },
        proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
        inputs: { baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], construction_rule: 'same_weight_substitution_v1', incumbent_start_weight: 1 },
        outputs: { candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }], starting_turnover_pct: 1, unchanged_positions_count: 0 },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', construction_basis: 'explicit_single_replacement_rule', cash_treatment: 'excluded_from_construction_basis', position_scope: 'positive_market_value_positions_only' },
        truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', note: 'Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.' },
        warnings: [],
        rejection_reason: null,
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getConstructedCandidateArtifact('draft-1')).toMatchObject({
      draftId: 'draft-1',
      replacementIntentBaseSymbol: 'AAPL',
      constructionRuleId: 'same_weight_substitution_v1',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('persists selected construction rule by draft id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveSelectedConstructionRule').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getSelectedConstructionRule').mockResolvedValue({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      selectedRuleId: 'fixed_split_50_50_substitution_v2',
    })

    await portfolioWorkspaceStorage.saveSelectedConstructionRule({
      workspaceId: 'workspace-1',
      draftId: 'draft-1',
      baseNodeId: 'node-1',
      selectedRuleId: 'fixed_split_50_50_substitution_v2',
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getSelectedConstructionRule('draft-1')).toMatchObject({
      draftId: 'draft-1',
      selectedRuleId: 'fixed_split_50_50_substitution_v2',
    })
    expect(getSpy).toHaveBeenCalledWith('draft-1')
  })

  it('persists proposal artifacts by workspace id', async () => {
    const proposalFixture = createSavedProposalArtifactFixture()
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveProposalArtifact').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getWorkspaceProposalArtifacts').mockResolvedValue([
      proposalFixture,
    ])

    await portfolioWorkspaceStorage.saveProposalArtifact(proposalFixture)

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')).toMatchObject([{ id: 'proposal-1', versionNumber: 1 }])
    expect(getSpy).toHaveBeenCalledWith('workspace-1')
  })

  it('builds saved proposal artifacts with canonical proposal source labels', () => {
    const canonicalFixture = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFromProposalFixture(canonicalFixture)
    const proposal = portfolioWorkspaceStorage.buildSavedProposalArtifact({
      id: 'proposal-1',
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
      sourceIntent: {
        kind: 'etf_replacement_intent',
        source: 'candidate_seed',
        createdAt: '2026-04-15T00:05:00Z',
        draftId: 'draft-1',
        workspaceId: 'workspace-1',
        baseNodeId: 'node-1',
        baseSymbol: 'AAPL',
        candidateSymbol: 'IUFS',
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
      reviewSnapshotArtifactId: 'review_snapshot_1234567890abcdef',
      proposalCapture: reviewSnapshotArtifact.proposal_capture,
      reviewSnapshotPMSummary: reviewSnapshotArtifact.pm_summary,
      hypotheticalReplay: canonicalFixture.reviewSnapshot,
    })

    expect(proposal.proposalSource).toEqual({
      proposalSourceVersion: 1,
      proposalSourceKind: 'draft_replacement_intent_review_only',
      proposalTruth: 'review_only_hypothetical_proposal',
      portfolioTruth: 'draft_snapshot_not_applied',
      reviewScope: 'proposal_review_context_only',
    })
    expect(proposal.reviewSnapshotArtifactId).toBe('review_snapshot_1234567890abcdef')
    expect(proposal.reviewSnapshotPMSummary).toEqual(reviewSnapshotArtifact.pm_summary)
    expect(proposal.proposalCapture).toEqual(reviewSnapshotArtifact.proposal_capture)
  })

  it('builds canonical saved proposal and review snapshot fixtures from overlay-aware replay state', () => {
    const proposal = createSavedProposalArtifactFixture({ replayType: 'overlay_aware' })
    const artifact = createReviewSnapshotArtifactFromProposalFixture(proposal)

    expect(proposal.proposalCapture.replay_type).toBe('overlay_aware')
    expect(proposal.reviewSnapshotPMSummary.replay_type).toBe('overlay_aware')
    expect(artifact.compact_summary.replay_type).toBe('overlay_aware')
    expect(artifact.source_payload).toEqual({
      replay_type: 'overlay_aware',
      replay: null,
      overlay_replay: proposal.reviewSnapshot,
    })
    expect(artifact.pm_summary).toEqual(proposal.reviewSnapshotPMSummary)
    expect(artifact.proposal_capture).toEqual(proposal.proposalCapture)
  })

  it('builds saved proposal artifacts when methodology provenance is absent', () => {
    const baseProposal = createSavedProposalArtifactFixtureBase({ includeMethodologyProvenance: false }) as VersionedProposalArtifact
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()

    const proposal = portfolioWorkspaceStorage.buildSavedProposalArtifact({
      id: 'proposal-1',
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
      sourceIntent: baseProposal.sourceIntent,
      reviewSnapshotArtifactId: 'review_snapshot_1234567890abcdef',
      proposalCapture: reviewSnapshotArtifact.proposal_capture,
      reviewSnapshotPMSummary: createReviewSnapshotPMSummaryFixture(baseProposal),
      hypotheticalReplay: baseProposal.reviewSnapshot,
    })

    expect(proposal.reviewSnapshotPMSummary.methodology).not.toHaveProperty('methodology_provenance')
    expect(proposal.reviewSnapshotPMSummary.analytics_summary.candidate_analytics).not.toHaveProperty('methodology_provenance')
  })

  it('builds review snapshot open handoff from persisted artifact only', async () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      const store = {
        index(indexName: string) {
          expect(storeName).toBe(portfolioDb.reviewSnapshotArtifactStoreName)
          expect(indexName).toBe('reviewSnapshotArtifactId')
          return {
            getAll(_key: string) {
              const request = { ...requestTemplate, result: [{ id: proposal.id, workspaceId: proposal.workspaceId, reviewSnapshotArtifactId: proposal.reviewSnapshotArtifactId, artifact: reviewSnapshotArtifact }] }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.buildReviewSnapshotOpenHandoffFromProposal(proposal)).resolves.toEqual(proposal.proposalCapture.open_handoff)
  })

  it('fails closed when review snapshot open handoff sees persisted identity mismatch', async () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    reviewSnapshotArtifact.identity.artifact_id = 'review_snapshot_other'

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      const store = {
        index(indexName: string) {
          expect(storeName).toBe(portfolioDb.reviewSnapshotArtifactStoreName)
          expect(indexName).toBe('reviewSnapshotArtifactId')
          return {
            getAll(_key: string) {
              const request = { ...requestTemplate, result: [{ id: proposal.id, workspaceId: proposal.workspaceId, reviewSnapshotArtifactId: proposal.reviewSnapshotArtifactId, artifact: reviewSnapshotArtifact }] }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.buildReviewSnapshotOpenHandoffFromProposal(proposal)).rejects.toThrow(
      'Saved proposal reviewSnapshotArtifactId does not match persisted review snapshot artifact identity',
    )
  })

  it('fails closed when review snapshot open handoff sees contradictory persisted proposal_capture handoff', async () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    reviewSnapshotArtifact.proposal_capture = {
      ...reviewSnapshotArtifact.proposal_capture,
      open_handoff: {
        ...reviewSnapshotArtifact.proposal_capture.open_handoff,
        artifact_id: 'review_snapshot_other',
      },
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      const store = {
        index(indexName: string) {
          expect(storeName).toBe(portfolioDb.reviewSnapshotArtifactStoreName)
          expect(indexName).toBe('reviewSnapshotArtifactId')
          return {
            getAll(_key: string) {
              const request = { ...requestTemplate, result: [{ id: proposal.id, workspaceId: proposal.workspaceId, reviewSnapshotArtifactId: proposal.reviewSnapshotArtifactId, artifact: reviewSnapshotArtifact }] }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.buildReviewSnapshotOpenHandoffFromProposal(proposal)).rejects.toThrow(
      'Saved proposal review snapshot proposal_capture open_handoff artifact_id does not match saved proposal reviewSnapshotArtifactId',
    )
  })

  it('validates review snapshot open response envelopes strictly', () => {
    const artifact = createReviewSnapshotArtifactFixture()
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotOpenResponseEnvelope({
      handoff: {
        handoff_kind: 'review_snapshot_open_handoff_v1',
        artifact_id: artifact.identity.artifact_id,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      artifact,
      pm_summary: artifact.pm_summary,
      replay_payload: artifact.source_payload,
    })).not.toThrow()

    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotOpenResponseEnvelope({
      handoff: {
        handoff_kind: 'review_snapshot_open_handoff_v0',
        artifact_id: artifact.identity.artifact_id,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      artifact,
      pm_summary: artifact.pm_summary,
      replay_payload: artifact.source_payload,
    })).toThrow('Review snapshot open response handoff has unsupported handoff kind')

    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotOpenResponseEnvelope({
      handoff: {
        handoff_kind: 'review_snapshot_open_handoff_v1',
        artifact_id: artifact.identity.artifact_id,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      artifact,
      pm_summary: artifact.pm_summary,
      replay_payload: { ...artifact.source_payload, replay: null, overlay_replay: null },
    })).toThrow('Review snapshot open response replay_payload does not match persisted artifact source_payload')

    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotOpenResponseEnvelope({
      handoff: {
        handoff_kind: 'review_snapshot_open_handoff_v1',
        artifact_id: artifact.identity.artifact_id,
        artifact_kind: 'portfolio_review_snapshot',
        schema_version: 'review_snapshot_artifact_v1',
        consumer_kind: 'saved_hypothetical_replay_proposal',
      },
      artifact: { ...artifact, pm_summary: { ...artifact.pm_summary, pm_summary_version: 2 as never } },
      pm_summary: { ...artifact.pm_summary, pm_summary_version: 2 as never },
      replay_payload: artifact.source_payload,
    })).toThrow('Review snapshot open response artifact pm_summary has unsupported pm_summary_version')
  })

  it('fails closed when saved proposal restore sees cached pm summary mismatch against persisted artifact', () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    proposal.reviewSnapshotPMSummary = {
      ...proposal.reviewSnapshotPMSummary,
      review_basis: {
        ...proposal.reviewSnapshotPMSummary.review_basis,
        benchmark_symbol: 'QQQ',
      },
    }

    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactRestoreIntegrity(proposal, reviewSnapshotArtifact)).toThrow(
      'Saved proposal cached reviewSnapshotPMSummary does not match persisted review snapshot artifact pm_summary',
    )
  })

  it('fails closed when saved proposal restore sees cached pm summary missing while persisted artifact exists', () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()

    delete (proposal as { reviewSnapshotPMSummary?: unknown }).reviewSnapshotPMSummary

    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactRestoreIntegrity(proposal as RawPersistedVersionedProposalArtifact, reviewSnapshotArtifact)).toThrow(
      'Saved proposal cached reviewSnapshotPMSummary is missing while persisted review snapshot artifact pm_summary exists',
    )
  })

  it('fails closed when saved proposal restore sees missing authoritative proposalCapture while persisted artifact exists', () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()

    delete (proposal as { proposalCapture?: unknown }).proposalCapture

    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactRestoreIntegrity(proposal as RawPersistedVersionedProposalArtifact, reviewSnapshotArtifact)).toThrow(
      'Saved proposal proposalCapture is missing',
    )
  })

  it('fails closed when saved proposal restore sees malformed cached pm summary while persisted artifact exists', () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    proposal.reviewSnapshotPMSummary = {
      ...proposal.reviewSnapshotPMSummary,
      role: 'baseline' as never,
    }

    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactRestoreIntegrity(proposal, reviewSnapshotArtifact)).toThrow(
      'Saved proposal cached reviewSnapshotPMSummary role is invalid',
    )
  })

  it('validates review snapshot comparison response envelopes strictly', () => {
    const artifact = createReviewSnapshotArtifactFixture()
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(
      createReviewSnapshotComparisonResponseFixture(artifact),
    )).not.toThrow()

    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope({
      family_key: {
        workspace_id: artifact.lineage.workspace_id,
        source_draft_id: artifact.lineage.source_draft_id,
        source_base_node_id: artifact.lineage.source_base_node_id,
        proposal_family_id: artifact.lineage.proposal_family_id,
        source_kind: artifact.lineage.source_kind,
      },
      provenance: 'persisted_review_snapshot_artifacts_only',
      benchmark_separation: 'explicit_per_snapshot_benchmark_fields',
      baseline_pm_summary: { ...artifact.pm_summary, role: 'candidate' },
      candidate_pm_summary: { ...artifact.pm_summary, role: 'candidate' },
    })).toThrow('Review snapshot comparison response baseline_pm_summary role is invalid')
  })

  it('fails closed when review snapshot comparison family identity does not fully align', () => {
    const artifact = createReviewSnapshotArtifactFixture()

    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(
      createReviewSnapshotComparisonResponseFixture(artifact),
    )).not.toThrow()

    const workspaceMismatch = createReviewSnapshotComparisonResponseFixture(artifact)
    workspaceMismatch.baseline_pm_summary = {
      ...workspaceMismatch.baseline_pm_summary,
      provenance: {
        ...workspaceMismatch.baseline_pm_summary.provenance,
        lineage: {
          ...workspaceMismatch.baseline_pm_summary.provenance.lineage,
          workspace_id: 'workspace-other',
        },
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(workspaceMismatch)).toThrow(
      'Review snapshot comparison response baseline_pm_summary provenance lineage workspace_id is invalid',
    )

    const sourceDraftMismatch = createReviewSnapshotComparisonResponseFixture(artifact)
    sourceDraftMismatch.candidate_pm_summary = {
      ...sourceDraftMismatch.candidate_pm_summary,
      provenance: {
        ...sourceDraftMismatch.candidate_pm_summary.provenance,
        lineage: {
          ...sourceDraftMismatch.candidate_pm_summary.provenance.lineage,
          source_draft_id: 'draft-other',
        },
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(sourceDraftMismatch)).toThrow(
      'Review snapshot comparison response candidate_pm_summary provenance lineage source_draft_id is invalid',
    )

    const sourceBaseNodeMismatch = createReviewSnapshotComparisonResponseFixture(artifact)
    sourceBaseNodeMismatch.baseline_pm_summary = {
      ...sourceBaseNodeMismatch.baseline_pm_summary,
      provenance: {
        ...sourceBaseNodeMismatch.baseline_pm_summary.provenance,
        lineage: {
          ...sourceBaseNodeMismatch.baseline_pm_summary.provenance.lineage,
          source_base_node_id: 'node-other',
        },
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(sourceBaseNodeMismatch)).toThrow(
      'Review snapshot comparison response baseline_pm_summary provenance lineage source_base_node_id is invalid',
    )

    const proposalFamilyMismatch = createReviewSnapshotComparisonResponseFixture(artifact)
    proposalFamilyMismatch.candidate_pm_summary = {
      ...proposalFamilyMismatch.candidate_pm_summary,
      provenance: {
        ...proposalFamilyMismatch.candidate_pm_summary.provenance,
        lineage: {
          ...proposalFamilyMismatch.candidate_pm_summary.provenance.lineage,
          proposal_family_id: 'etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z',
        },
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(proposalFamilyMismatch)).toThrow(
      'Review snapshot comparison response candidate_pm_summary provenance lineage proposal_family_id is invalid',
    )

    const sourceKindMismatch = createReviewSnapshotComparisonResponseFixture(artifact)
    sourceKindMismatch.baseline_pm_summary = {
      ...sourceKindMismatch.baseline_pm_summary,
      provenance: {
        ...sourceKindMismatch.baseline_pm_summary.provenance,
        lineage: {
          ...sourceKindMismatch.baseline_pm_summary.provenance.lineage,
          source_kind: 'persisted_optimizer_handoff' as never,
        },
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(sourceKindMismatch)).toThrow(
      'Review snapshot comparison response baseline_pm_summary provenance lineage is invalid',
    )
  })

  it('fails closed when review snapshot comparison family_key fields are missing or partial', () => {
    const artifact = createReviewSnapshotArtifactFixture()

    const missingWorkspaceId = createReviewSnapshotComparisonResponseFixture(artifact)
    delete (missingWorkspaceId.family_key as { workspace_id?: string }).workspace_id
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(missingWorkspaceId)).toThrow(
      'Review snapshot comparison response family_key is invalid',
    )

    const emptySourceDraftId = createReviewSnapshotComparisonResponseFixture(artifact)
    emptySourceDraftId.family_key.source_draft_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(emptySourceDraftId)).toThrow(
      'Review snapshot comparison response family_key is invalid',
    )

    const emptySourceBaseNodeId = createReviewSnapshotComparisonResponseFixture(artifact)
    emptySourceBaseNodeId.family_key.source_base_node_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(emptySourceBaseNodeId)).toThrow(
      'Review snapshot comparison response family_key is invalid',
    )

    const emptyProposalFamilyId = createReviewSnapshotComparisonResponseFixture(artifact)
    emptyProposalFamilyId.family_key.proposal_family_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(emptyProposalFamilyId)).toThrow(
      'Review snapshot comparison response family_key is invalid',
    )

    const invalidSourceKind = createReviewSnapshotComparisonResponseFixture(artifact)
    invalidSourceKind.family_key.source_kind = 'persisted_optimizer_handoff' as never
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotComparisonResponseEnvelope(invalidSourceKind)).toThrow(
      'Review snapshot comparison response family_key is invalid',
    )
  })

  it('validates review snapshot family review response envelopes strictly', () => {
    const artifact = createReviewSnapshotArtifactFixture()
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(
      createReviewSnapshotFamilyReviewResponseFixture(artifact),
    )).not.toThrow()

    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope({
      review_kind: 'review_snapshot_family_review',
      provenance: 'persisted_review_snapshot_artifacts_only',
      compare_selection_policy: 'exactly_two_distinct_family_siblings',
      siblings: [],
    })).toThrow('Review snapshot family review response family_key is invalid')
  })

  it('fails closed when review snapshot family review sibling identity does not fully align', () => {
    const artifact = createReviewSnapshotArtifactFixture()

    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(
      createReviewSnapshotFamilyReviewResponseFixture(artifact),
    )).not.toThrow()

    const workspaceMismatch = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    workspaceMismatch.siblings[0] = {
      ...workspaceMismatch.siblings[0]!,
      lineage: {
        ...workspaceMismatch.siblings[0]!.lineage,
        workspace_id: 'workspace-other',
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(workspaceMismatch)).toThrow(
      'Review snapshot family review response sibling 1 lineage workspace_id is invalid',
    )

    const sourceDraftMismatch = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    sourceDraftMismatch.siblings[0] = {
      ...sourceDraftMismatch.siblings[0]!,
      pm_summary: {
        ...sourceDraftMismatch.siblings[0]!.pm_summary,
        provenance: {
          ...sourceDraftMismatch.siblings[0]!.pm_summary.provenance,
          lineage: {
            ...sourceDraftMismatch.siblings[0]!.pm_summary.provenance.lineage,
            source_draft_id: 'draft-other',
          },
        },
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(sourceDraftMismatch)).toThrow(
      'Review snapshot family review response sibling 1 pm_summary provenance lineage source_draft_id is invalid',
    )

    const sourceBaseNodeMismatch = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    sourceBaseNodeMismatch.anchor = {
      ...sourceBaseNodeMismatch.anchor,
      lineage: {
        ...sourceBaseNodeMismatch.anchor.lineage,
        source_base_node_id: 'node-other',
      },
    }
    sourceBaseNodeMismatch.siblings[0] = sourceBaseNodeMismatch.anchor
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(sourceBaseNodeMismatch)).toThrow(
      'Review snapshot family review response anchor lineage source_base_node_id is invalid',
    )

    const proposalFamilyMismatch = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    proposalFamilyMismatch.siblings[0] = {
      ...proposalFamilyMismatch.siblings[0]!,
      lineage: {
        ...proposalFamilyMismatch.siblings[0]!.lineage,
        proposal_family_id: 'etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z',
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(proposalFamilyMismatch)).toThrow(
      'Review snapshot family review response sibling 1 lineage proposal_family_id is invalid',
    )

    const sourceKindMismatch = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    sourceKindMismatch.siblings[0] = {
      ...sourceKindMismatch.siblings[0]!,
      pm_summary: {
        ...sourceKindMismatch.siblings[0]!.pm_summary,
        provenance: {
          ...sourceKindMismatch.siblings[0]!.pm_summary.provenance,
          lineage: {
            ...sourceKindMismatch.siblings[0]!.pm_summary.provenance.lineage,
            source_kind: 'persisted_optimizer_handoff' as never,
          },
        },
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(sourceKindMismatch)).toThrow(
      'Review snapshot family review response sibling 1 pm_summary provenance lineage is invalid',
    )
  })

  it('fails closed when review snapshot family review family_key fields are missing or partial', () => {
    const artifact = createReviewSnapshotArtifactFixture()

    const missingWorkspaceId = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    delete (missingWorkspaceId.family_key as { workspace_id?: string }).workspace_id
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(missingWorkspaceId)).toThrow(
      'Review snapshot family review response family_key is invalid',
    )

    const emptySourceDraftId = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    emptySourceDraftId.family_key.source_draft_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(emptySourceDraftId)).toThrow(
      'Review snapshot family review response family_key is invalid',
    )

    const emptySourceBaseNodeId = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    emptySourceBaseNodeId.family_key.source_base_node_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(emptySourceBaseNodeId)).toThrow(
      'Review snapshot family review response family_key is invalid',
    )

    const emptyProposalFamilyId = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    emptyProposalFamilyId.family_key.proposal_family_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(emptyProposalFamilyId)).toThrow(
      'Review snapshot family review response family_key is invalid',
    )

    const invalidSourceKind = createReviewSnapshotFamilyReviewResponseFixture(artifact)
    invalidSourceKind.family_key.source_kind = 'persisted_optimizer_handoff' as never
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyReviewResponseEnvelope(invalidSourceKind)).toThrow(
      'Review snapshot family review response family_key is invalid',
    )
  })

  it('validates review snapshot family inbox response envelopes strictly', () => {
    const artifact = createReviewSnapshotArtifactFixture()
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(
      createReviewSnapshotFamilyInboxResponseFixture(artifact),
    )).not.toThrow()

    const invalidCompareReadinessResponse = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    invalidCompareReadinessResponse.rows[0]!.compare_readiness = {
      ready: true,
      reason: 'compatible_family_pair_available',
      compatible_pair_count: 0,
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(
      invalidCompareReadinessResponse,
    )).toThrow('Review snapshot family inbox response row 1 compare_readiness is invalid')
  })

  it('fails closed when review snapshot family inbox family identity does not fully align', () => {
    const artifact = createReviewSnapshotArtifactFixture()

    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(
      createReviewSnapshotFamilyInboxResponseFixture(artifact),
    )).not.toThrow()

    const workspaceMismatch = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    workspaceMismatch.rows[0]!.lineage = {
      ...workspaceMismatch.rows[0]!.lineage,
      workspace_id: 'workspace-other',
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(workspaceMismatch)).toThrow(
      'Review snapshot family inbox response row 1 lineage workspace_id is invalid',
    )

    const sourceDraftMismatch = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    sourceDraftMismatch.rows[0]!.pm_summary = {
      ...sourceDraftMismatch.rows[0]!.pm_summary,
      provenance: {
        ...sourceDraftMismatch.rows[0]!.pm_summary.provenance,
        lineage: {
          ...sourceDraftMismatch.rows[0]!.pm_summary.provenance.lineage,
          source_draft_id: 'draft-other',
        },
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(sourceDraftMismatch)).toThrow(
      'Review snapshot family inbox response row 1 pm_summary provenance lineage source_draft_id is invalid',
    )

    const sourceBaseNodeMismatch = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    sourceBaseNodeMismatch.rows[0]!.proposal_capture = {
      ...sourceBaseNodeMismatch.rows[0]!.proposal_capture,
      lineage: {
        ...sourceBaseNodeMismatch.rows[0]!.proposal_capture.lineage,
        source_base_node_id: 'node-other',
      },
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(sourceBaseNodeMismatch)).toThrow(
      'Review snapshot family inbox response row 1 proposal_capture lineage source_base_node_id is invalid',
    )

    const proposalFamilyMismatch = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    proposalFamilyMismatch.rows[0]!.lineage = {
      ...proposalFamilyMismatch.rows[0]!.lineage,
      proposal_family_id: 'etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z',
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(proposalFamilyMismatch)).toThrow(
      'Review snapshot family inbox response row 1 lineage proposal_family_id is invalid',
    )

    const sourceKindMismatch = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    sourceKindMismatch.rows[0]!.lineage = {
      ...sourceKindMismatch.rows[0]!.lineage,
      source_kind: 'persisted_optimizer_handoff' as never,
    }
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(sourceKindMismatch)).toThrow(
      'Review snapshot family inbox response row 1 lineage source_kind is invalid',
    )
  })

  it('fails closed when review snapshot family inbox family_key fields are missing, empty, or duplicated', () => {
    const artifact = createReviewSnapshotArtifactFixture()

    const missingWorkspaceId = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    delete (missingWorkspaceId.rows[0]!.family_key as { workspace_id?: string }).workspace_id
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(missingWorkspaceId)).toThrow(
      'Review snapshot family inbox response row 1 family_key is invalid',
    )

    const emptySourceDraftId = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    emptySourceDraftId.rows[0]!.family_key.source_draft_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(emptySourceDraftId)).toThrow(
      'Review snapshot family inbox response row 1 family_key is invalid',
    )

    const emptySourceBaseNodeId = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    emptySourceBaseNodeId.rows[0]!.family_key.source_base_node_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(emptySourceBaseNodeId)).toThrow(
      'Review snapshot family inbox response row 1 family_key is invalid',
    )

    const emptyProposalFamilyId = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    emptyProposalFamilyId.rows[0]!.family_key.proposal_family_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(emptyProposalFamilyId)).toThrow(
      'Review snapshot family inbox response row 1 family_key is invalid',
    )

    const invalidSourceKind = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    invalidSourceKind.rows[0]!.family_key.source_kind = 'persisted_optimizer_handoff' as never
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(invalidSourceKind)).toThrow(
      'Review snapshot family inbox response row 1 family_key is invalid',
    )

    const duplicateRows = createReviewSnapshotFamilyInboxResponseFixture(artifact)
    duplicateRows.rows = [
      createReviewSnapshotFamilyInboxRowFixture(artifact),
      createReviewSnapshotFamilyInboxRowFixture(artifact),
    ]
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotFamilyInboxResponseEnvelope(duplicateRows)).toThrow(
      'Review snapshot family inbox response contains duplicate family_key rows',
    )
  })

  it('validates review snapshot active thesis cross-family queue response envelopes strictly', () => {
    const artifact = createReviewSnapshotArtifactFixture()
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(
      createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact),
    )).not.toThrow()

    const invalidShape = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    delete (invalidShape.rows[0] as { pm_summary_fields?: unknown }).pm_summary_fields
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(invalidShape)).toThrow(
      'Review snapshot active thesis cross-family queue response row 1 pm_summary_fields are invalid',
    )

    const sameFamily = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    sameFamily.rows[0]!.family_key.proposal_family_id = sameFamily.active_thesis.family_key.proposal_family_id
    sameFamily.rows[0]!.family_separation.queue_proposal_family_id = sameFamily.active_thesis.family_key.proposal_family_id
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(sameFamily)).toThrow(
      'Review snapshot active thesis cross-family queue response row 1 lineage proposal_family_id is invalid',
    )

    const duplicateRows = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    duplicateRows.rows = [duplicateRows.rows[0]!, { ...duplicateRows.rows[0]! }]
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(duplicateRows)).toThrow(
      'Review snapshot active thesis cross-family queue response contains duplicate family_key rows',
    )

    const invalidOrdering = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    invalidOrdering.rows = [
      {
        ...invalidOrdering.rows[0]!,
        latest_identity: { ...invalidOrdering.rows[0]!.latest_identity, artifact_id: 'review_snapshot_b' },
        family_key: { ...invalidOrdering.rows[0]!.family_key, proposal_family_id: 'etf_replacement_intent:AAPL:IUFS:2026-04-16T00:05:00Z' },
        family_separation: { ...invalidOrdering.rows[0]!.family_separation, queue_proposal_family_id: 'etf_replacement_intent:AAPL:IUFS:2026-04-16T00:05:00Z' },
        lineage: { ...invalidOrdering.rows[0]!.lineage, proposal_family_id: 'etf_replacement_intent:AAPL:IUFS:2026-04-16T00:05:00Z', proposal_id: 'proposal-b' },
        latest_saved_at: '2026-04-15T00:05:00Z',
      },
      {
        ...invalidOrdering.rows[0]!,
        latest_identity: { ...invalidOrdering.rows[0]!.latest_identity, artifact_id: 'review_snapshot_c' },
        family_key: { ...invalidOrdering.rows[0]!.family_key, proposal_family_id: 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:05:00Z' },
        family_separation: { ...invalidOrdering.rows[0]!.family_separation, queue_proposal_family_id: 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:05:00Z' },
        lineage: { ...invalidOrdering.rows[0]!.lineage, proposal_family_id: 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:05:00Z', proposal_id: 'proposal-c' },
        latest_saved_at: '2026-04-16T00:05:00Z',
      },
    ]
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(invalidOrdering)).toThrow(
      'Review snapshot active thesis cross-family queue response ordering is invalid',
    )
  })

  it('fails closed when review snapshot active thesis cross-family queue family_key fields are missing, null, empty, or invalid', () => {
    const artifact = createReviewSnapshotArtifactFixture()

    const missingActiveWorkspaceId = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    delete (missingActiveWorkspaceId.active_thesis.family_key as { workspace_id?: string }).workspace_id
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(missingActiveWorkspaceId)).toThrow(
      'Review snapshot active thesis cross-family queue response active_thesis family_key is invalid',
    )

    const nullActiveSourceDraftId = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    ;(nullActiveSourceDraftId.active_thesis.family_key as { source_draft_id: string | null }).source_draft_id = null
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(nullActiveSourceDraftId)).toThrow(
      'Review snapshot active thesis cross-family queue response active_thesis family_key is invalid',
    )

    const emptyRowSourceBaseNodeId = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    emptyRowSourceBaseNodeId.rows[0]!.family_key.source_base_node_id = ''
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(emptyRowSourceBaseNodeId)).toThrow(
      'Review snapshot active thesis cross-family queue response row 1 family_key is invalid',
    )

    const nullRowProposalFamilyId = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    ;(nullRowProposalFamilyId.rows[0]!.family_key as { proposal_family_id: string | null }).proposal_family_id = null
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(nullRowProposalFamilyId)).toThrow(
      'Review snapshot active thesis cross-family queue response row 1 family_key is invalid',
    )

    const invalidActiveSourceKind = createReviewSnapshotActiveThesisCrossFamilyQueueResponseFixture(artifact)
    invalidActiveSourceKind.active_thesis.family_key.source_kind = 'persisted_optimizer_handoff' as never
    expect(() => portfolioWorkspaceStorage.assertValidReviewSnapshotActiveThesisCrossFamilyQueueResponseEnvelope(invalidActiveSourceKind)).toThrow(
      'Review snapshot active thesis cross-family queue response active_thesis family_key is invalid',
    )
  })

  it('rejects review snapshot comparison refs when proposal family differs', async () => {
    const baseline = createSavedProposalArtifactFixture()
    const candidate = createSavedProposalArtifactFixture()
    candidate.id = 'proposal-other'
    candidate.reviewSnapshotArtifactId = 'review_snapshot_other'
    candidate.proposalFamilyId = 'etf_replacement_intent:AAPL:IUIT:2026-04-17T00:00:00Z'

    await expect(portfolioWorkspaceStorage.buildReviewSnapshotComparisonRefs([baseline, candidate])).rejects.toThrow(
      'Review snapshot comparison requires matching proposalFamilyId',
    )
  })

  it('fails closed when saved proposal review snapshot artifact is missing during restore', async () => {
    const proposal = createSavedProposalArtifactFixture()

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: undefined as unknown }
      const store = {
        index(indexName: string) {
          expect(storeName).toBe(portfolioDb.reviewSnapshotArtifactStoreName)
          expect(indexName).toBe('reviewSnapshotArtifactId')
          return {
            getAll(_key: string) {
              const request = { ...requestTemplate, result: [] }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.buildReviewSnapshotOpenHandoffFromProposal(proposal)).rejects.toThrow('Saved proposal review snapshot artifact is missing')
  })

  it('hydrates effective proposalSource for legacy saved proposal artifacts missing both proposal-source locations at load time', async () => {
    const legacyProposal = createSavedProposalArtifactFixture()
    delete (legacyProposal as { proposalSource?: unknown }).proposalSource
    delete (legacyProposal.reviewSnapshot.proposal as { proposal_source?: unknown }).proposal_source
    delete (legacyProposal.proposalCapture.proposal as { proposal_source?: unknown }).proposal_source
    delete (legacyProposal as { reviewSnapshotPMSummary?: unknown }).reviewSnapshotPMSummary
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    reviewSnapshotArtifact.source_payload.replay = legacyProposal.reviewSnapshot as any
    reviewSnapshotArtifact.pm_summary = buildLegacySavedProposalMirrorFromProposal(legacyProposal)

    mockProposalAndArtifactLoad([legacyProposal], { [legacyProposal.reviewSnapshotArtifactId]: reviewSnapshotArtifact })

    await expect(portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')).resolves.toMatchObject([
      {
        proposalSource: {
          proposalSourceVersion: 1,
          proposalSourceKind: 'draft_replacement_intent_review_only',
          proposalTruth: 'review_only_hypothetical_proposal',
          portfolioTruth: 'draft_snapshot_not_applied',
          reviewScope: 'proposal_review_context_only',
        },
      },
    ])
    expect(legacyProposal.proposalSource).toBeUndefined()
    expect(legacyProposal.reviewSnapshot.proposal.proposal_source).toBeUndefined()
  })

  it('hydrates legacy saved proposal PM summaries when methodology provenance is absent', async () => {
    const legacyProposal = createSavedProposalArtifactFixture({ includeMethodologyProvenance: false })
    delete (legacyProposal as { proposalSource?: unknown }).proposalSource
    delete (legacyProposal.reviewSnapshot.proposal as { proposal_source?: unknown }).proposal_source
    delete (legacyProposal.proposalCapture.proposal as { proposal_source?: unknown }).proposal_source
    delete (legacyProposal as { reviewSnapshotPMSummary?: unknown }).reviewSnapshotPMSummary
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    reviewSnapshotArtifact.source_payload.replay = legacyProposal.reviewSnapshot as any
    reviewSnapshotArtifact.pm_summary = buildLegacySavedProposalMirrorFromProposal(legacyProposal)

    mockProposalAndArtifactLoad([legacyProposal], { [legacyProposal.reviewSnapshotArtifactId]: reviewSnapshotArtifact })

    const loaded = await portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')

    expect(loaded[0]?.reviewSnapshotPMSummary.methodology).not.toHaveProperty('methodology_provenance')
    expect(loaded[0]?.reviewSnapshotPMSummary.analytics_summary.candidate_analytics).not.toHaveProperty('methodology_provenance')
  })

  it('fails closed when loaded saved proposal mirror pm summary conflicts with persisted artifact pm_summary', async () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    proposal.reviewSnapshotPMSummary = {
      ...proposal.reviewSnapshotPMSummary,
      review_basis: {
        ...proposal.reviewSnapshotPMSummary.review_basis,
        benchmark_symbol: 'QQQ',
      },
    }

    mockProposalAndArtifactLoad([proposal], { [proposal.reviewSnapshotArtifactId]: reviewSnapshotArtifact })

    await expect(portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')).rejects.toThrow(
      'Saved proposal cached reviewSnapshotPMSummary does not match persisted review snapshot artifact pm_summary',
    )
  })

  it('keeps canonical top-level proposalSource authoritative over the fallback path on load', async () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    delete (proposal.reviewSnapshot.proposal as { proposal_source?: unknown }).proposal_source
    reviewSnapshotArtifact.source_payload.replay = proposal.reviewSnapshot as any

    mockProposalAndArtifactLoad([proposal], { [proposal.reviewSnapshotArtifactId]: reviewSnapshotArtifact })

    const loaded = await portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')
    expect(loaded[0]?.proposalSource).toEqual(proposal.proposalSource)
    expect(loaded[0]?.reviewSnapshot.proposal.proposal_source).toEqual({
      proposal_source_version: proposal.proposalSource.proposalSourceVersion,
      proposal_source_kind: proposal.proposalSource.proposalSourceKind,
      proposal_truth: proposal.proposalSource.proposalTruth,
      portfolio_truth: proposal.proposalSource.portfolioTruth,
      review_scope: proposal.proposalSource.reviewScope,
    })
    expect(loaded[0]?.proposalCapture.proposal.proposal_source).toEqual({
      proposal_source_version: proposal.proposalSource.proposalSourceVersion,
      proposal_source_kind: proposal.proposalSource.proposalSourceKind,
      proposal_truth: proposal.proposalSource.proposalTruth,
      portfolio_truth: proposal.proposalSource.portfolioTruth,
      review_scope: proposal.proposalSource.reviewScope,
    })
  })

  it('loads saved proposal artifacts when nested and top-level proposal-source labels match', async () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()

    mockProposalAndArtifactLoad([proposal], { [proposal.reviewSnapshotArtifactId]: reviewSnapshotArtifact })

    const loaded = await portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')
    expect(loaded[0]?.proposalSource).toEqual(proposal.proposalSource)
    expect(loaded[0]?.reviewSnapshot.proposal.proposal_source).toEqual(proposal.reviewSnapshot.proposal.proposal_source)
  })

  it('restores overlay-aware saved proposal artifacts from canonical proposal and persisted review snapshot fixtures', async () => {
    const { proposal, reviewSnapshotArtifact } = createSavedProposalReviewSnapshotFixtureBundle({ replayType: 'overlay_aware' })

    mockProposalAndArtifactLoad([proposal], { [proposal.reviewSnapshotArtifactId]: reviewSnapshotArtifact })

    const loaded = await portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')

    expect(loaded).toHaveLength(1)
    expect(loaded[0]?.proposalCapture.replay_type).toBe('overlay_aware')
    expect(loaded[0]?.reviewSnapshotPMSummary.replay_type).toBe('overlay_aware')
    expect(loaded[0]?.reviewSnapshot).toEqual(proposal.reviewSnapshot)
  })

  it('hydrates the exact dual-omission legacy case but rejects top-level-only omission even when nested fallback exists', async () => {
    const proposal = createSavedProposalArtifactFixture()
    const reviewSnapshotArtifact = createReviewSnapshotArtifactFixture()
    delete (proposal as { proposalSource?: unknown }).proposalSource

    mockProposalAndArtifactLoad([proposal], { [proposal.reviewSnapshotArtifactId]: reviewSnapshotArtifact })

    await expect(portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')).rejects.toThrow(
      'Saved proposal is missing authoritative proposalSource',
    )
  })

  it('rejects malformed nested proposal-source data during load when authoritative top-level proposalSource is present', async () => {
    const malformedProposal = createSavedProposalArtifactFixture()
    malformedProposal.proposalSource = {
      proposalSourceVersion: 1,
      proposalSourceKind: 'draft_replacement_intent_review_only',
      proposalTruth: 'review_only_hypothetical_proposal',
      portfolioTruth: 'draft_snapshot_not_applied',
      reviewScope: 'proposal_review_context_only',
    }
    malformedProposal.reviewSnapshot.proposal.proposal_source = {
      proposal_source_version: 1,
      proposal_source_kind: 'draft_replacement_intent_review_only',
      proposal_truth: 'review_only_hypothetical_proposal',
      portfolio_truth: 'review_only_hypothetical_proposal' as never,
      review_scope: 'proposal_review_context_only',
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: [malformedProposal] as unknown }
      const store = {
        index() {
          return {
            getAll(_key: string) {
              const request = { ...requestTemplate }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')).rejects.toThrow(
      'Saved proposal reviewSnapshot proposal.proposal_source is invalid',
    )
  })

  it('rejects conflicting nested proposal-source data during load when authoritative top-level proposalSource is present', async () => {
    const conflictingProposal = createSavedProposalArtifactFixture()
    conflictingProposal.reviewSnapshot.proposal.proposal_source = {
      proposal_source_version: 1,
      proposal_source_kind: 'draft_replacement_intent_review_only',
      proposal_truth: 'review_only_hypothetical_proposal',
      portfolio_truth: 'draft_snapshot_not_applied',
      review_scope: 'mismatched_review_scope' as never,
    }

    vi.spyOn(portfolioDb, 'withStore').mockImplementation(async (_storeName, _mode, handler) => {
      const requestTemplate = { onsuccess: null as null | (() => void), onerror: null as null | (() => void), error: null, result: [conflictingProposal] as unknown }
      const store = {
        index() {
          return {
            getAll(_key: string) {
              const request = { ...requestTemplate }
              queueMicrotask(() => request.onsuccess?.())
              return request
            },
          }
        },
      } as unknown as IDBObjectStore
      return new Promise((resolve, reject) => handler(store, resolve, reject))
    })

    await expect(portfolioWorkspaceStorage.getWorkspaceProposalArtifacts('workspace-1')).rejects.toThrow(
      'Saved proposal reviewSnapshot proposal.proposal_source is invalid',
    )
  })

  it('rejects contradictory proposal artifacts before saving', async () => {
    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity({
      id: 'proposal-1',
      kind: 'single_replacement_hypothetical_replay_proposal',
      schemaVersion: 1,
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
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
        candidateSymbol: 'IUFS',
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
      proposalSource: {
        proposalSourceVersion: 1,
        proposalSourceKind: 'draft_replacement_intent_review_only',
        proposalTruth: 'review_only_hypothetical_proposal',
        portfolioTruth: 'draft_snapshot_not_applied',
        reviewScope: 'proposal_review_context_only',
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
        replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
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
          candidate_symbol: 'IUFS',
          draft_id: 'draft-1',
          base_node_id: 'node-1',
        },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'fixed_split_50_50_substitution_v2' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
        candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          investor_economics_status: availableInvestorEconomicsStatus,
          reference_result: null,
          candidate_result: {
            portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
            assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
            status: 'ok', investor_economics_status: availableInvestorEconomicsStatus, instrument_metadata: [], starting_weights: [], ending_weights: [], metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [], rebalance_events: [], trades: [],
          },
          comparison: null,
          reference_diagnostics: null,
          candidate_diagnostics: null,
          diagnostics_comparison: null,
        },
        warnings: [],
      },
  } as any)).toThrow('Saved proposal candidateConstructionRule does not match reviewSnapshot derivation')
  })

  it('rejects present proposal-source values that differ from the nested canonical label before saving', () => {
    const proposal = createSavedProposalArtifactFixture()
    proposal.proposalSource = {
      ...proposal.proposalSource,
      portfolioTruth: 'review_only_hypothetical_proposal' as never,
    }

    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity(proposal)).toThrow(
      'Saved proposal proposalSource conflicts with reviewSnapshot proposal.proposal_source',
    )
  })

  it('fails deterministically when loading contradictory proposal artifacts', async () => {
    const valid = {
      id: 'proposal-1',
      kind: 'single_replacement_hypothetical_replay_proposal',
      schemaVersion: 1,
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
      savedFrom: 'desktop_hypothetical_replay_review',
      reviewStatus: 'recorded',
      sourceIntent: {
        kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1,
      },
      proposalSource: {
        proposalSourceVersion: 1,
        proposalSourceKind: 'draft_replacement_intent_review_only',
        proposalTruth: 'review_only_hypothetical_proposal',
        portfolioTruth: 'draft_snapshot_not_applied',
        reviewScope: 'proposal_review_context_only',
      },
      replayBasis: {
        benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized',
        candidateConstructionRule: 'same_weight_substitution_v1',
        replayProvenance: { candidate_input_source: 'constructed_candidate_payload', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
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
          candidate_symbol: 'IUFS',
          draft_id: 'draft-1',
          base_node_id: 'node-1',
        },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
        replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm', reference_result: null,
          candidate_result: {
            portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
            assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
            status: 'ok', investor_economics_status: availableInvestorEconomicsStatus, instrument_metadata: [], starting_weights: [], ending_weights: [], metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [], rebalance_events: [], trades: [],
          }, comparison: null, reference_diagnostics: null, candidate_diagnostics: null, diagnostics_comparison: null,
        },
        warnings: [],
      },
    }

    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity({
      ...valid,
      replayBasis: {
        ...valid.replayBasis,
        replayProvenance: { ...valid.replayBasis.replayProvenance, candidate_input_source: 'constructed_candidate_payload' },
      },
    } as any)).toThrow('Saved proposal replayProvenance candidate_input_source does not match reviewSnapshot replay_provenance')
  })

  it('persists active thesis by workspace id', async () => {
    const saveSpy = vi.spyOn(portfolioWorkspaceStorage, 'saveActiveThesis').mockResolvedValue()
    const getSpy = vi.spyOn(portfolioWorkspaceStorage, 'getActiveThesis').mockResolvedValue({
      workspaceId: 'workspace-1',
      promotedAt: '2026-04-17T00:00:00Z',
      sourceProposalId: 'proposal-1',
      thesisProposal: {
        id: 'proposal-1',
        kind: 'single_replacement_hypothetical_replay_proposal',
        schemaVersion: 1,
        createdAt: '2026-04-16T00:00:00Z',
        workspaceId: 'workspace-1',
        sourceDraftId: 'draft-1',
        sourceBaseNodeId: 'node-1',
        proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
        versionNumber: 1,
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
          candidateSymbol: 'IUFS',
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
        proposalSource: {
          proposalSourceVersion: 1,
          proposalSourceKind: 'draft_replacement_intent_review_only',
          proposalTruth: 'review_only_hypothetical_proposal',
          portfolioTruth: 'draft_snapshot_not_applied',
          reviewScope: 'proposal_review_context_only',
        },
        replayBasis: {
          benchmarkSymbol: 'SPY',
          startDate: '2024-01-01',
          endDate: '2024-12-31',
          rebalanceFrequency: 'monthly',
          commissionBps: 0,
          slippageBps: 0,
          derivationBasis: 'draft_snapshot_positions_normalized',
          candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
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
            candidate_symbol: 'IUFS',
            draft_id: 'draft-1',
            base_node_id: 'node-1',
          },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm',
          investor_economics_status: availableInvestorEconomicsStatus,
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
              assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
              status: 'ok',
              investor_economics_status: availableInvestorEconomicsStatus,
              instrument_metadata: [],
              starting_weights: [],
              ending_weights: [],
              metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
              equity_curve: [],
              rebalance_events: [],
              trades: [],
            },
            comparison: null,
            reference_diagnostics: null,
            candidate_diagnostics: null,
            diagnostics_comparison: null,
          },
          warnings: [],
        },
      },
    })

    await portfolioWorkspaceStorage.saveActiveThesis({
      workspaceId: 'workspace-1',
      promotedAt: '2026-04-17T00:00:00Z',
      sourceProposalId: 'proposal-1',
      thesisProposal: {
        id: 'proposal-1',
        kind: 'single_replacement_hypothetical_replay_proposal',
        schemaVersion: 1,
        createdAt: '2026-04-16T00:00:00Z',
        workspaceId: 'workspace-1',
        sourceDraftId: 'draft-1',
        sourceBaseNodeId: 'node-1',
        proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
        versionNumber: 1,
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
          candidateSymbol: 'IUFS',
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
        proposalSource: {
          proposalSourceVersion: 1,
          proposalSourceKind: 'draft_replacement_intent_review_only',
          proposalTruth: 'review_only_hypothetical_proposal',
          portfolioTruth: 'draft_snapshot_not_applied',
          reviewScope: 'proposal_review_context_only',
        },
        replayBasis: {
          benchmarkSymbol: 'SPY',
          startDate: '2024-01-01',
          endDate: '2024-12-31',
          rebalanceFrequency: 'monthly',
          commissionBps: 0,
          slippageBps: 0,
          derivationBasis: 'draft_snapshot_positions_normalized',
          candidateConstructionRule: 'same_weight_substitution_v1', replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
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
            candidate_symbol: 'IUFS',
            draft_id: 'draft-1',
            base_node_id: 'node-1',
          },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }],
          candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: {
            methodology: 'm',
            investor_economics_status: availableInvestorEconomicsStatus,
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
              assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
              status: 'ok',
              investor_economics_status: availableInvestorEconomicsStatus,
              instrument_metadata: [],
              starting_weights: [],
              ending_weights: [],
              metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
              equity_curve: [],
              rebalance_events: [],
              trades: [],
            },
            comparison: null,
            reference_diagnostics: null,
            candidate_diagnostics: null,
            diagnostics_comparison: null,
          },
          warnings: [],
        },
      },
    })

    expect(saveSpy).toHaveBeenCalledTimes(1)
    expect(await portfolioWorkspaceStorage.getActiveThesis('workspace-1')).toMatchObject({ workspaceId: 'workspace-1', sourceProposalId: 'proposal-1' })
    expect(getSpy).toHaveBeenCalledWith('workspace-1')
  })

  it('rejects contradictory active thesis artifacts before saving', async () => {
    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity({
        id: 'proposal-1',
        kind: 'single_replacement_hypothetical_replay_proposal',
        schemaVersion: 1,
        createdAt: '2026-04-16T00:00:00Z',
        workspaceId: 'workspace-1',
        sourceDraftId: 'draft-1',
        sourceBaseNodeId: 'node-1',
        proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
        versionNumber: 1,
        savedFrom: 'desktop_hypothetical_replay_review',
        reviewStatus: 'recorded',
        sourceIntent: {
          kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1,
        },
        proposalSource: {
          proposalSourceVersion: 1,
          proposalSourceKind: 'draft_replacement_intent_review_only',
          proposalTruth: 'review_only_hypothetical_proposal',
          portfolioTruth: 'draft_snapshot_not_applied',
          reviewScope: 'proposal_review_context_only',
        },
        replayBasis: {
          benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized',
          candidateConstructionRule: 'same_weight_substitution_v1',
          replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: true, validation_status: null, constraint_set_id: null } },
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
            candidate_symbol: 'IUFS',
            draft_id: 'draft-1',
            base_node_id: 'node-1',
          },
          derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
          replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
          baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
          replay: {
            methodology: 'm', investor_economics_status: availableInvestorEconomicsStatus, reference_result: null,
            candidate_result: {
              portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
              assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
              status: 'ok', investor_economics_status: availableInvestorEconomicsStatus, instrument_metadata: [], starting_weights: [], ending_weights: [], metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [], rebalance_events: [], trades: [],
            }, comparison: null, reference_diagnostics: null, candidate_diagnostics: null, diagnostics_comparison: null,
        },
        warnings: [],
      },
    } as any)).toThrow('Saved proposal replayProvenance constraint_validation.supplied does not match reviewSnapshot replay_provenance')
  })

  it('fails deterministically when loading contradictory active thesis artifacts', async () => {
    expect(() => portfolioWorkspaceStorage.assertSavedProposalArtifactIntegrity({
      id: 'proposal-1',
      kind: 'single_replacement_hypothetical_replay_proposal',
      schemaVersion: 1,
      createdAt: '2026-04-16T00:00:00Z',
      workspaceId: 'workspace-1',
      sourceDraftId: 'draft-1',
      sourceBaseNodeId: 'node-1',
      proposalFamilyId: 'etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z',
      versionNumber: 1,
      savedFrom: 'desktop_hypothetical_replay_review',
      reviewStatus: 'recorded',
      sourceIntent: {
        kind: 'etf_replacement_intent', source: 'candidate_seed', createdAt: '2026-04-15T00:05:00Z', draftId: 'draft-1', workspaceId: 'workspace-1', baseNodeId: 'node-1', baseSymbol: 'AAPL', candidateSymbol: 'IUFS', seededFromDraftId: 'draft-1', seedRankingId: 'etf_ranking_engine_v1', seedMethodologyId: 'etf_ranking_methodology_v1', seedRankingBasisDate: '2026-04-15', peerGroup: 'Sector UCITS ETF', benchmarkSymbol: 'SPY', lookbackMonths: 6, confidence: 'medium', holdingsSupport: 'mixed', warningCount: 1,
      },
      proposalSource: {
        proposalSourceVersion: 1,
        proposalSourceKind: 'draft_replacement_intent_review_only',
        proposalTruth: 'review_only_hypothetical_proposal',
        portfolioTruth: 'draft_snapshot_not_applied',
        reviewScope: 'proposal_review_context_only',
      },
      replayBasis: {
        benchmarkSymbol: 'SPY', startDate: '2024-01-01', endDate: '2024-12-31', rebalanceFrequency: 'monthly', commissionBps: 0, slippageBps: 0, derivationBasis: 'draft_snapshot_positions_normalized', candidateConstructionRule: 'same_weight_substitution_v1',
        replayProvenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'mismatched_methodology', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
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
          candidate_symbol: 'IUFS',
          draft_id: 'draft-1',
          base_node_id: 'node-1',
        },
        derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
        replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
        baseline_weights: [{ symbol: 'AAPL', target_weight: 1 }], candidate_weights: [{ symbol: 'IUFS', target_weight: 1 }],
        replay: {
          methodology: 'm', investor_economics_status: availableInvestorEconomicsStatus, reference_result: null,
          candidate_result: {
            portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 2, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null,
            assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
              status: 'ok', investor_economics_status: availableInvestorEconomicsStatus, instrument_metadata: [], starting_weights: [], ending_weights: [], metrics: { total_return_pct: 1, annualized_return_pct: 1, annualized_volatility_pct: 1, downside_volatility_pct: 1, max_drawdown_pct: -1, sharpe_ratio: 1, sortino_ratio: 1, benchmark_return_pct: 1, excess_return_pct: 0, tracking_error_pct: 1, information_ratio: 0, beta_vs_benchmark: 1, correlation_vs_benchmark: 1, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [], rebalance_events: [], trades: [],
          }, comparison: null, reference_diagnostics: null, candidate_diagnostics: null, diagnostics_comparison: null,
        },
        warnings: [],
      },
    } as any)).toThrow('Saved proposal replayProvenance seed_methodology_id does not match reviewSnapshot replay_provenance')
  })
})
