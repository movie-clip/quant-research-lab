import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PortfolioImprovementWorkspaceShell } from './PortfolioImprovementWorkspaceShell'

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
  return {
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
    replayBasis: {
      benchmarkSymbol: 'SPY',
      startDate: '2024-01-01',
      endDate: '2024-12-31',
      rebalanceFrequency: 'monthly',
      commissionBps: 0,
      slippageBps: 0,
      derivationBasis: 'draft_snapshot_positions_normalized',
      candidateConstructionRule: 'same_weight_substitution_v1',
    },
    reviewSnapshot: {
      proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: candidateSymbol, draft_id: 'draft-1', base_node_id: 'node-1' },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' },
      replay_provenance: {
        candidate_input_source: 'replacement_intent_preview',
        construction_rule_id: 'same_weight_substitution_v1',
        upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' },
        seed_ranking_id: 'etf_ranking_engine_v1',
        seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null },
      },
      baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
      candidate_weights: [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: candidateSymbol, target_weight: 0.6 }],
      replay: makeReplay(),
      warnings: [],
    },
  } as any
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
    replay: {
      construction_artifact_id: 'artifact-123',
      truth_separation: {
        baseline_truth: 'imported_portfolio_snapshot',
        candidate_truth: 'hypothetical_construction_artifact',
        candidate_applied: false,
        consumption_mode: 'explicit_reference_only',
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
      constructionArtifactId: 'artifact-123',
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

function renderShell(overrides: Record<string, any> = {}) {
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
      onPromoteProposalToThesis={noOp}
      onClearActiveThesis={noOp}
      onSaveProposal={noOp}
      onHypotheticalReplayResult={noOp}
      onFormedCandidateArtifact={noOp}
      onConstructedCandidateArtifact={noOp}
      onConstructionConstraintValidationArtifact={noOp}
      onSelectedConstructionRuleChange={noOp}
      persistedOptimizerHandoffReview={null}
      {...overrides}
    />,
  )
}

describe('PortfolioImprovementWorkspaceShell', () => {
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

    expect(screen.getByText('Portfolio Improvement Decision Summary')).toBeTruthy()
    expect(screen.getByText('Not selected')).toBeTruthy()
    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getAllByText('No artifact').length).toBeGreaterThan(0)
    expect(screen.getByText('Current review state only.')).toBeTruthy()
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

    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getAllByRole('button', { name: 'Viewing For Review' }).length).toBeGreaterThan(0)
    expect(screen.getAllByText('Replay lineage: direct preview replay · same-weight substitution · validation not supplied').length).toBeGreaterThan(0)
  })

  it('opens a read-only saved proposal comparison for exactly two selected artifacts', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

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

    expect(latestByTestIdIn(container, 'saved-proposal-comparison-view')).toBeTruthy()
    expect(ui.getByText('2 of 2 selected')).toBeTruthy()
    expect(ui.getByText('Comparison Checks')).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Swap sides' })).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Open full proposal v2' })).toBeTruthy()
    expect(ui.getByRole('button', { name: 'Open full proposal v1' })).toBeTruthy()
  })

  it('keeps saved proposal comparison on provenance and replay metadata instead of investor-performance rows', () => {
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

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

    expect(within(container).getByText('Replay setup')).toBeTruthy()
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
    const latestProposal = makeSavedProposal(2, '2026-04-17T00:00:00Z', 'IUIT')
    const olderProposal = makeSavedProposal(1, '2026-04-16T00:00:00Z', 'IUFS')

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
    expect(within(comparisonView).getAllByText('v2 · AAPL -> IUIT').length).toBeGreaterThan(0)

    fireEvent.click(ui.getByRole('button', { name: 'Swap sides' }))
    expect(within(latestByTestIdIn(container, 'saved-proposal-comparison-view')).getAllByText('v1 · AAPL -> IUFS').length).toBeGreaterThan(0)

    fireEvent.click(ui.getByRole('button', { name: 'Open full proposal v2' }))
    expect(ui.getAllByText('AAPL -> IUIT').length).toBeGreaterThan(0)
    expect(ui.getAllByRole('button', { name: 'Viewing For Review' }).length).toBeGreaterThan(0)
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
