import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { createImportedBaselineFixture } from '../../test/portfolioFixtures'
import { CandidateFormationSection, ConstructionRuleSection, DiagnosticsChangeSection, HypotheticalReplaySection, PortfolioAllocationBacktestPanel, SavedProposalReadoutSection } from './PortfolioAllocationBacktestPanel'
import type { HypotheticalReplayResponse, OverlayAwareHypotheticalReplayResponse, ImportedBaselineSource, PortfolioAllocationBacktestResponse, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationResponse, SingleReplacementConstructionRuleId } from '../portfolio/types'
import type { ConstructionConstraintValidationArtifact, ConstructedCandidateArtifact, FormedCandidateArtifact, ReplacementIntentDraftArtifact, VersionedProposalArtifact } from '../portfolio/workspaceTypes'

const legacyMockAnalysis = {
  snapshot: {
    statement: { importer: 'interactive_brokers', account_id: 'U1', base_currency: 'USD', statement_period: '2025', page_count: 1 },
    statements: [{ importer: 'interactive_brokers', account_id: 'U1', base_currency: 'USD', statement_period: '2025', page_count: 1, source_path: 'sample.pdf', detected_format: 'pdf', imported_at: '2026-04-10T00:00:00Z' }],
    statement_totals: null,
    instruments: [],
    cash_balances: [],
    positions: [
      { as_of_date: '2025-12-31', symbol: 'AAPL', quantity: 1, cost_basis: 50000, close_price: 50000, market_value: 60000, unrealized_pnl: 0, currency: 'USD' },
      { as_of_date: '2025-12-31', symbol: 'MSFT', quantity: 1, cost_basis: 40000, close_price: 40000, market_value: 40000, unrealized_pnl: 0, currency: 'USD' },
    ],
    ledger_entries: [],
  },
  canonical_ledger: [], overview: { total_market_value: 100000, total_unrealized_pnl: 0, positions_count: 2, ledger_entries_count: 0, top_positions: [], sector_allocation: [], sector_position_breakdown: {}, cash_by_currency: {} }, reconciliation: { passed: true, checks: [] }, activity: [], holdings_timeline: [], enriched_positions: [], risk_summary: { benchmark_symbol: 'SPY', methodology: 'm', start_date: null, end_date: null, observations: 0, portfolio_beta: null, portfolio_correlation: null, r_squared: null, portfolio_volatility_pct: null, benchmark_volatility_pct: null }, rolling_risk: [], lookthrough: { portfolio_market_value: 0, covered_market_value: 0, coverage_ratio: 0, etf_resolution: {}, uncovered_positions: [], top_constituents: [] }, lookthrough_sector_exposure: [], market_overlap: { benchmark_symbol: 'SPY', overlap_weight: 0, active_share: 0, portfolio_in_benchmark_weight: 0, benchmark_covered_weight: 0 }, relative_risk: { benchmark_symbol: 'SPY', tracking_error_pct: null, active_return_pct: null, information_ratio: null }, volatility_regime: { methodology: 'm', assumptions: { return_basis: 'time_weighted_daily_return', cash_flow_timing: 'external_cash_flow_applied_before_end_of_day_measurement', drawdown_basis: 'compounded_return_index', benchmark_basis: 'aligned_daily_price_return', downside_mar: 0, annualization_days: 252 }, rolling_series: [], snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: null, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: null, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: null, current_drawdown_pct: null, max_drawdown_pct: null, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null }, regime: { label: 'normal', confidence: 'low' } }, factor_exposures: [], factor_shift_diagnostics: { methodology: 'm', snapshots: [], largest_positive_shifts_20d: [], largest_negative_shifts_20d: [], largest_absolute_shifts_20d: [], largest_absolute_shifts_60d: [] }, risk_contribution_breakdown: { methodology: 'm', window_days: 60, observation_count: 0, status: 'ok', factor_contributions: [], factor_total_variance: null, specific_variance: null, total_variance: null, factor_risk_share_total: null, specific_risk_share: null, residual_volatility: null, position_contributions: [], concentration: { top_1_factor_risk_share: null, top_3_factor_risk_share: null, top_1_position_risk_share: null, top_5_position_risk_share: null, factor_hhi: null, position_hhi: null } }, model_reliability: { window_days: 60, observation_count: 0, r_squared: null, residual_volatility: null, collinearity_pair_count: 0, max_abs_factor_correlation: null, factor_count_used: 0, missing_factor_count: 12, status: 'ok', confidence: 'low', stability_score: null }, factor_registry: [], factor_methodology: null, statistical_factor_model: { status: 'partial', benchmark_symbol: 'SPY', windows: [], rolling_loadings_20d: [], rolling_loadings_60d: [], rolling_loadings_252d: [], current_factor_snapshot: [], collinearity_diagnostics: [], insufficient_history: [] }, stress_scenarios: [], performance_series: [], performance_summary: { start_value: null, end_value: null, net_contributions: 0, investment_gain: null, time_weighted_return_pct: null, money_weighted_return_pct: null, benchmark_return_pct: null, excess_return_pct: null }, daily_states: [], rebalance_preview: [], simulated_trades: [], benchmark: null,
} as ImportedBaselineSource

const baselineFixture = createImportedBaselineFixture()
const mockAnalysis = {
  ...baselineFixture,
  snapshot: {
    ...baselineFixture.snapshot,
    positions: [
      { as_of_date: '2025-12-31', symbol: 'AAPL', quantity: 1, cost_basis: 50000, close_price: 50000, market_value: 60000, unrealized_pnl: 0, currency: 'USD' },
      { as_of_date: '2025-12-31', symbol: 'MSFT', quantity: 1, cost_basis: 40000, close_price: 40000, market_value: 40000, unrealized_pnl: 0, currency: 'USD' },
    ],
    cash_balances: [],
  },
  overview: {
    ...baselineFixture.overview,
    total_market_value: 100000,
    positions_count: 2,
    top_positions: [],
    sector_allocation: [],
    sector_position_breakdown: {},
    cash_by_currency: {},
  },
}

void legacyMockAnalysis

const mockResponse: PortfolioAllocationBacktestResponse = {
  methodology: 'm',
  investor_economics_status: { status: 'available', reason: null },
  reference_result: {
    portfolio_name: 'Reference', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 3, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null, assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' }, status: 'ok', investor_economics_status: { status: 'available', reason: null }, instrument_metadata: [{ symbol: 'SPY', trading_currency: 'USD', instrument_base_currency: 'USD', currency_hedged: null, distribution_policy: 'unknown' }], starting_weights: [{ symbol: 'SPY', target_weight: 1 }], ending_weights: [{ symbol: 'SPY', target_weight: 1 }], metrics: { total_return_pct: 8, annualized_return_pct: 8, annualized_volatility_pct: 10, downside_volatility_pct: 6, max_drawdown_pct: -4, sharpe_ratio: 0.8, sortino_ratio: 1.1, benchmark_return_pct: 7, excess_return_pct: 1, tracking_error_pct: 3, information_ratio: 0.3, beta_vs_benchmark: 1, correlation_vs_benchmark: 0.9, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [{ date: '2024-01-01', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-06-01', equity: 103000, cash: 0, gross_exposure: 103000, drawdown_pct: -1 }, { date: '2024-12-31', equity: 108000, cash: 0, gross_exposure: 108000, drawdown_pct: -2 }], rebalance_events: [], trades: [] },
  candidate_result: {
    portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 3, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null, assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' }, status: 'degraded', investor_economics_status: { status: 'available', reason: null }, instrument_metadata: [{ symbol: 'SPY', trading_currency: 'USD', instrument_base_currency: 'USD', currency_hedged: null, distribution_policy: 'unknown' }, { symbol: 'TLT', trading_currency: 'USD', instrument_base_currency: 'USD', currency_hedged: null, distribution_policy: 'unknown' }], starting_weights: [{ symbol: 'SPY', target_weight: 0.6 }, { symbol: 'TLT', target_weight: 0.4 }], ending_weights: [{ symbol: 'SPY', target_weight: 0.58 }, { symbol: 'TLT', target_weight: 0.42 }], metrics: { total_return_pct: 10, annualized_return_pct: 10, annualized_volatility_pct: 9, downside_volatility_pct: 5, max_drawdown_pct: -3, sharpe_ratio: 1.1, sortino_ratio: 1.4, benchmark_return_pct: 7, excess_return_pct: 3, tracking_error_pct: 4, information_ratio: 0.5, beta_vs_benchmark: 0.8, correlation_vs_benchmark: 0.85, total_turnover_pct: 12, turnover_events_count: 2, total_cost_paid: 45 }, equity_curve: [{ date: '2024-01-01', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-06-01', equity: 104000, cash: 0, gross_exposure: 104000, drawdown_pct: -0.5 }, { date: '2024-12-31', equity: 110000, cash: 0, gross_exposure: 110000, drawdown_pct: -1.5 }], rebalance_events: [{ decision_date: '2024-01-31', execution_date: '2024-02-01', turnover_pct: 5, traded_notional: 5000, total_cost: 15 }], trades: [{ date: '2024-02-01', symbol: 'SPY', action: 'buy', quantity: 1, price: 100, traded_notional: 100, commission_cost: 0.5, slippage_cost: 0.5, total_cost: 1 }] },
  comparison: { total_return_diff_pct: 2, annualized_return_diff_pct: 2, benchmark_return_diff_pct: 0, annualized_volatility_diff_pct: -1, downside_volatility_diff_pct: -1, max_drawdown_diff_pct: 1, sharpe_diff: 0.3, sortino_diff: 0.3, excess_return_diff_pct: 2, tracking_error_diff_pct: 1, information_ratio_diff: 0.2, beta_diff: -0.2, correlation_diff: -0.05, total_turnover_diff_pct: 12, total_cost_diff: 45 },
  reference_diagnostics: { provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' }, factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 1, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }], volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 10, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 6, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 3, current_drawdown_pct: -2, max_drawdown_pct: -4, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null }, risk_contribution: { methodology: 'm', window_days: 60, observation_count: 60, status: 'ok', factor_contributions: [{ key: 'market', label: 'Market', us_proxy: 'SPY', loading: 1, factor_volatility: 12, variance_contribution: 0.01, risk_share: 0.6 }], factor_total_variance: 0.01, specific_variance: 0.005, total_variance: 0.015, factor_risk_share_total: 0.6667, specific_risk_share: 0.3333, residual_volatility: 5, position_contributions: [{ symbol: 'SPY', weight: 1, volatility: 10, marginal_contribution: 0.01, component_contribution: 0.01, risk_share: 1 }], concentration: { top_1_factor_risk_share: 0.6, top_3_factor_risk_share: 0.6, top_1_position_risk_share: 1, top_5_position_risk_share: 1, factor_hhi: 0.36, position_hhi: 1 } }, stress_scenarios: [{ name: 'Broad Market Selloff', estimated_return_pct: -8.5, description: 'x' }] },
  candidate_diagnostics: { provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' }, factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 0.8, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }], volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 9, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 5, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 4, current_drawdown_pct: -1.5, max_drawdown_pct: -3, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null }, risk_contribution: { methodology: 'm', window_days: 60, observation_count: 60, status: 'ok', factor_contributions: [{ key: 'market', label: 'Market', us_proxy: 'SPY', loading: 0.8, factor_volatility: 11, variance_contribution: 0.008, risk_share: 0.45 }], factor_total_variance: 0.008, specific_variance: 0.004, total_variance: 0.012, factor_risk_share_total: 0.6667, specific_risk_share: 0.3333, residual_volatility: 4.5, position_contributions: [{ symbol: 'SPY', weight: 0.6, volatility: 9, marginal_contribution: 0.008, component_contribution: 0.006, risk_share: 0.7 }], concentration: { top_1_factor_risk_share: 0.45, top_3_factor_risk_share: 0.45, top_1_position_risk_share: 0.7, top_5_position_risk_share: 1, factor_hhi: 0.2, position_hhi: 0.58 } }, stress_scenarios: [{ name: 'Broad Market Selloff', estimated_return_pct: -6.4, description: 'x' }] },
  diagnostics_comparison: {
    factor_exposure_changes: [{ key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2 }],
    top_factor_exposure_change: { key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2, selection_rule: 'largest_absolute_delta', rationale: 'Largest valid factor exposure delta in this group (candidate - baseline).' },
    volatility_changes: [{ key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1 }],
    top_volatility_change: { key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1, selection_rule: 'fixed_priority', rationale: 'When replay/backtest investor total-return equivalence is unverified, suppress all user-facing investor-economics metrics and any derived or comparative views from that basis, including drawdown surfaces, Sharpe, Sortino, benchmark-relative deltas, and monitoring callouts; emit only null/withheld semantics, never numeric fallbacks or zero-equivalent UI states. Selected by fixed priority order across allowed replay risk-shape metrics: annualized volatility, then downside volatility, then tracking error.' },
    risk_contribution_changes: [{ key: 'market', label: 'Market', baseline_value: 0.6, candidate_value: 0.45, delta_value: -0.15 }],
    top_risk_contribution_change: { key: 'market', label: 'Market', baseline_value: 0.6, candidate_value: 0.45, delta_value: -0.15, selection_rule: 'largest_absolute_delta', rationale: 'Largest valid factor risk-contribution delta in this group (candidate - baseline).' },
    concentration_changes: [{ key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16 }],
    top_concentration_change: { key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16, selection_rule: 'fixed_priority', rationale: 'Selected by fixed priority order: factor HHI, then top 1 position risk share.' },
    stress_scenario_changes: [{ key: 'broad_market_selloff', label: 'Broad Market Selloff', baseline_value: -8.5, candidate_value: -6.4, delta_value: 2.1 }],
    top_stress_scenario_change: { key: 'broad_market_selloff', label: 'Broad Market Selloff', baseline_value: -8.5, candidate_value: -6.4, delta_value: 2.1, selection_rule: 'largest_absolute_delta', rationale: 'Largest valid stress-scenario delta in this group (candidate - baseline).' },
  },
}

const replacementIntent: ReplacementIntentDraftArtifact = {
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
}

const hypotheticalResponse: HypotheticalReplayResponse = {
  proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
  derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
  baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
  candidate_weights: [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.6 }],
  replay: mockResponse,
  warnings: ['Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.'],
}

const overlayAwareHypotheticalResponse: OverlayAwareHypotheticalReplayResponse = {
  proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
  derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'same_weight_substitution_v1' }, replay_provenance: { candidate_input_source: 'replacement_intent_preview', construction_rule_id: 'same_weight_substitution_v1', upstream_ids: { draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1' }, seed_ranking_id: 'etf_ranking_engine_v1', seed_methodology_id: 'etf_ranking_methodology_v1', constraint_validation: { supplied: false, validation_status: null, constraint_set_id: null } },
  overlay_application: { overlay_id: 'benchmark_trend_overlay_v1', overlay_status: 'risk_reduced', as_of_month_end: '2024-12-31', benchmark_symbol: 'SPY', risky_weight_scale: 0.35, cash_residual_weight: 0.65, applied_to_candidate_only: true },
  baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
  candidate_weights_pre_overlay: [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.6 }],
  candidate_weights_post_overlay: [{ symbol: 'MSFT', target_weight: 0.14 }, { symbol: 'IUFS', target_weight: 0.21 }, { symbol: '__CASH__', target_weight: 0.65 }],
  base_replay: mockResponse,
  overlay_replay: {
    ...mockResponse,
    candidate_result: {
      ...mockResponse.candidate_result,
      portfolio_name: 'Hypothetical Candidate Overlay-Aware',
      starting_weights: [{ symbol: 'MSFT', target_weight: 0.14 }, { symbol: 'IUFS', target_weight: 0.21 }, { symbol: '__CASH__', target_weight: 0.65 }],
      ending_weights: [{ symbol: 'MSFT', target_weight: 0.14 }, { symbol: 'IUFS', target_weight: 0.21 }, { symbol: '__CASH__', target_weight: 0.65 }],
    },
  },
  warnings: ['Overlay-aware replay keeps the cash residual as hypothetical residual cash only.'],
}

const withheldInvestorEconomicsStatus = {
  status: 'withheld' as const,
  reason: 'withheld_unverified_total_return_equivalence' as const,
}

const formedCandidateResponse: SingleReplacementCandidateFormationResponse = {
  formation: { kind: 'single_replacement_candidate_formation', status: 'ok' },
  proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
  derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution', cash_treatment: 'excluded_from_candidate_formation_basis', position_scope: 'positive_market_value_positions_only' },
  baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }],
  candidate_weights: [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.6 }],
  formation_summary: { incumbent_start_weight: 0.6, candidate_start_weight: 0.6, unchanged_positions_count: 1, baseline_positions_count: 2, candidate_positions_count: 2, starting_turnover_pct: 0.6 },
  truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', candidate_truth_class: 'hypothetical_candidate_input_only', formation_truth_class: 'candidate_formation_derived', note: 'Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.' },
  warnings: ['Cash balances are excluded from the candidate-formation basis in this MVP.'],
  rejection_reason: null,
}

const formedCandidateArtifact: FormedCandidateArtifact = {
  workspaceId: 'workspace-1',
  draftId: 'draft-1',
  baseNodeId: 'node-1',
  replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
  replacementIntentBaseSymbol: 'AAPL',
  replacementIntentCandidateSymbol: 'IUFS',
  formation: formedCandidateResponse,
}

const constructedCandidateResponse: SingleReplacementCandidateConstructionResponse = {
  construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'same_weight_substitution_v1' },
  proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
  inputs: { baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }], construction_rule: 'same_weight_substitution_v1', incumbent_start_weight: 0.6 },
  outputs: { candidate_weights: [{ symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.6 }], starting_turnover_pct: 0.6, unchanged_positions_count: 1 },
  derivation: { baseline_basis: 'draft_snapshot_positions_normalized', construction_basis: 'explicit_single_replacement_rule', cash_treatment: 'excluded_from_construction_basis', position_scope: 'positive_market_value_positions_only' },
  truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', note: 'Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.' },
  warnings: ['Cash balances are excluded from the construction basis in this MVP.'],
  rejection_reason: null,
}

const constructedCandidateArtifact: ConstructedCandidateArtifact = {
  workspaceId: 'workspace-1',
  draftId: 'draft-1',
  baseNodeId: 'node-1',
  replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
  replacementIntentBaseSymbol: 'AAPL',
  replacementIntentCandidateSymbol: 'IUFS',
  constructionRuleId: 'same_weight_substitution_v1',
  construction: constructedCandidateResponse,
}

const constructionConstraintValidationResponse: SingleReplacementConstructionConstraintValidationResponse = {
  validation: {
    kind: 'single_replacement_construction_constraint_validation',
    status: 'ok',
    constraint_set_id: 'single_replacement_construction_constraints_v1',
  },
  proposal: constructedCandidateResponse.proposal,
  construction: constructedCandidateResponse.construction,
  derivation: {
    validation_timing: 'post_construction_pre_replay',
    validation_basis: 'explicit_constraint_set',
    candidate_input_source: 'constructed_candidate_payload',
    constraint_set_id: 'single_replacement_construction_constraints_v1',
  },
  truth_provenance: {
    baseline_truth_class: 'draft_snapshot_basis',
    construction_truth_class: 'candidate_construction_derived',
    candidate_truth_class: 'hypothetical_candidate_input_only',
    constraint_validation_truth_class: 'constraint_validation_derived',
    note: 'Constraint validation is a review-only derived object built from the constructed candidate payload.',
  },
  evaluations: [
    {
      constraint_id: 'weight_sum_matches_rule',
      severity: 'hard_block',
      status: 'pass',
      message: 'Candidate weights sum to the rule target.',
      rationale: 'Construction output totals 1.0.',
      actual_value: 1,
      expected_value: 1,
      operator: '==',
    },
    {
      constraint_id: 'single_replacement_pair_consistent',
      severity: 'warning',
      status: 'pass',
      message: 'Replacement pair is consistent with intent.',
      rationale: 'Constructed output preserves the intended pair.',
      actual_value: 'AAPL->IUFS',
      expected_value: 'AAPL->IUFS',
      operator: '==',
    },
  ],
  blocking_constraint_ids: [],
  warnings: ['Constraint validation warnings remain review-only context.'],
  rejection_reason: null,
}

function makeConstructionConstraintValidationArtifact(
  status: 'ok' | 'blocked' | 'rejected' = 'ok',
): ConstructionConstraintValidationArtifact {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: 'same_weight_substitution_v1',
    validation: {
      ...constructionConstraintValidationResponse,
      validation: {
        ...constructionConstraintValidationResponse.validation,
        status,
      },
      blocking_constraint_ids: status === 'blocked' ? ['weight_sum_matches_rule'] : [],
      rejection_reason: status === 'rejected' ? 'constructed candidate could not be evaluated safely' : null,
      evaluations: status === 'blocked'
        ? [
            {
              ...constructionConstraintValidationResponse.evaluations[0],
              status: 'fail',
              message: 'Candidate weights do not satisfy the locked rule.',
              actual_value: 0.97,
            },
            constructionConstraintValidationResponse.evaluations[1],
          ]
        : constructionConstraintValidationResponse.evaluations,
    },
  }
}

function makeConstructionResponse(ruleId: SingleReplacementConstructionRuleId): SingleReplacementCandidateConstructionResponse {
  if (ruleId === 'fixed_split_50_50_substitution_v2') {
    return {
      construction: { kind: 'single_replacement_construction', status: 'ok', rule_id: 'fixed_split_50_50_substitution_v2' },
      proposal: { source: 'draft_replacement_intent', draft_id: 'draft-1', workspace_id: 'workspace-1', base_node_id: 'node-1', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS' },
      inputs: { baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }], construction_rule: 'fixed_split_50_50_substitution_v2', incumbent_start_weight: 0.6, candidate_added_weight: 0.3, incumbent_remaining_weight: 0.3 },
      outputs: { candidate_weights: [{ symbol: 'AAPL', target_weight: 0.3 }, { symbol: 'MSFT', target_weight: 0.4 }, { symbol: 'IUFS', target_weight: 0.3 }], starting_turnover_pct: 0.3, unchanged_positions_count: 1, candidate_added_weight: 0.3, incumbent_remaining_weight: 0.3 },
      derivation: { baseline_basis: 'draft_snapshot_positions_normalized', construction_basis: 'explicit_single_replacement_rule', cash_treatment: 'excluded_from_construction_basis', position_scope: 'positive_market_value_positions_only' },
      truth_provenance: { baseline_truth_class: 'draft_snapshot_basis', construction_truth_class: 'candidate_construction_derived', candidate_truth_class: 'hypothetical_candidate_input_only', note: 'Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.' },
      warnings: ['Cash balances are excluded from the construction basis in this MVP.'],
      rejection_reason: null,
    }
  }
  return constructedCandidateResponse
}

function makeConstructedCandidateArtifact(ruleId: SingleReplacementConstructionRuleId): ConstructedCandidateArtifact {
  return {
    workspaceId: 'workspace-1',
    draftId: 'draft-1',
    baseNodeId: 'node-1',
    replacementIntentCreatedAt: '2026-04-15T00:05:00Z',
    replacementIntentBaseSymbol: 'AAPL',
    replacementIntentCandidateSymbol: 'IUFS',
    constructionRuleId: ruleId,
    construction: makeConstructionResponse(ruleId),
  }
}

const mockDraftSnapshot = {
  snapshotVersion: 1 as const,
  baseCurrency: 'USD',
  importedMeta: { importer: 'interactive_brokers' as const, statementPeriod: '2025', importedAt: '2026-04-10T00:00:00Z', sourceFileNames: ['IB2025.pdf'] },
  positions: [
    { symbol: 'AAPL', marketValue: 60000, quantity: 1, currency: 'USD', sector: 'Technology', sourceType: 'etf' as const },
    { symbol: 'MSFT', marketValue: 40000, quantity: 1, currency: 'USD', sector: 'Technology', sourceType: 'etf' as const },
  ],
  cashBalances: [],
  metadata: { benchmarkSymbol: 'SPY', notes: null, tags: [] },
}

const savedProposal: VersionedProposalArtifact = {
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
  sourceIntent: replacementIntent,
  replayBasis: {
    benchmarkSymbol: 'SPY',
    startDate: '2024-01-01',
    endDate: '2024-12-31',
    rebalanceFrequency: 'monthly',
    commissionBps: 0,
    slippageBps: 0,
    derivationBasis: 'draft_snapshot_positions_normalized',
    candidateConstructionRule: 'same_weight_substitution_v1',
    replayProvenance: hypotheticalResponse.replay_provenance,
  },
  reviewSnapshot: hypotheticalResponse,
}

describe('PortfolioAllocationBacktestPanel', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('keeps the panel focused on builder controls and excludes shell-owned review sections', () => {
    render(<PortfolioAllocationBacktestPanel result={mockResponse} onResult={() => {}} analysis={mockAnalysis} />)

    expect(screen.getByText('Current Import')).toBeTruthy()
    expect(screen.getByText('Baseline Portfolio')).toBeTruthy()
    expect(screen.getByText('Candidate Portfolio Builder')).toBeTruthy()
    expect(screen.getByText('Replay Engine Status')).toBeTruthy()
    expect(screen.getByText('The lower-level builder has a completed replay result available for shell-owned review surfaces.')).toBeTruthy()
    expect(screen.getByText('Candidate Status')).toBeTruthy()
    expect(screen.getByText('Comparison')).toBeTruthy()
    expect(screen.queryByText('Hypothetical Replay')).toBeNull()
    expect(screen.queryByText('Replay Summary')).toBeNull()
    expect(screen.queryByText('Before / After Diagnostics')).toBeNull()
    expect(screen.queryByText('Saved Proposal Review')).toBeNull()
    expect(screen.queryByText('Implementation Details')).toBeNull()
  })

  it('uses current portfolio and submits improvement replay payload', async () => {
    const onResult = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => mockResponse })
    vi.stubGlobal('fetch', fetchMock)

    render(<PortfolioAllocationBacktestPanel result={null} onResult={onResult} analysis={mockAnalysis} />)

    fireEvent.click(screen.getByText('Use Current Portfolio'))
    fireEvent.click(screen.getByText('Copy Baseline to Candidate'))
    fireEvent.click(screen.getByText('Normalize'))
    fireEvent.click(screen.getByText('Run Portfolio Improvement Replay'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, request] = fetchMock.mock.calls[0]
    const payload = JSON.parse(String(request.body))
    expect(String(url)).toContain('/api/backtests/portfolio-allocation')
    expect(payload.reference_weights).toEqual([{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }])
    expect(payload.weights).toEqual([{ symbol: 'AAPL', target_weight: 0.6 }, { symbol: 'MSFT', target_weight: 0.4 }])
    expect(onResult).toHaveBeenCalledWith(mockResponse)
  })

  it('prefills baseline weights from imported portfolio holdings', () => {
    render(<PortfolioAllocationBacktestPanel result={null} onResult={() => {}} analysis={mockAnalysis} />)

    expect(screen.getByDisplayValue('AAPL')).toBeTruthy()
    expect(screen.getByDisplayValue('0.6000')).toBeTruthy()
    expect(screen.getByDisplayValue('MSFT')).toBeTruthy()
    expect(screen.getByDisplayValue('0.4000')).toBeTruthy()
    expect(screen.getByText('$100000.00')).toBeTruthy()
  })

  it('renders hypothetical replay controls and submits replacement-intent preview payload', async () => {
    const onHypotheticalReplayResult = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => hypotheticalResponse })
    vi.stubGlobal('fetch', fetchMock)

    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact()} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={null} savedProposalCount={0} onSaveProposal={() => {}} onHypotheticalReplayResult={onHypotheticalReplayResult} />)

    expect(screen.getByText('Hypothetical Replay')).toBeTruthy()
    expect(screen.getByText('Replay Preflight')).toBeTruthy()
    expect(screen.getByText('Ready for backend validation')).toBeTruthy()
    expect(screen.getByText('The construction artifact supplies 2 candidate weights for review-only replay handoff.')).toBeTruthy()
    expect(screen.getByText('The construction artifact matches AAPL -> IUFS.')).toBeTruthy()
    expect(screen.getByText('The backend still has to confirm candidate history coverage and sufficient common replay dates before a preview can succeed.')).toBeTruthy()
    expect(screen.getByText('Truth class: replay-derived hypothetical evidence only. Review this as a draft-only comparison built from one explicit construction output handoff.')).toBeTruthy()
    expect(screen.getByText('No hypothetical replay has been run for this replacement intent yet.')).toBeTruthy()
    fireEvent.click(screen.getByText('Preview Hypothetical Replay'))
    expect(screen.getByText('Preview hypothetical current-vs-candidate replay')).toBeTruthy()
    expect(screen.getAllByText('Baseline').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Hypothetical Candidate').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Intent Source').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Replay Basis').length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText('Run Preview'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, request] = fetchMock.mock.calls[0]
    const payload = JSON.parse(String(request.body))
    expect(String(url)).toContain('/api/backtests/portfolio-allocation/replacement-intent-preview')
    expect(payload.constructed_candidate.construction.status).toBe('ok')
    expect(payload.constraint_validation.validation.status).toBe('ok')
    expect(payload.constraint_validation.validation.constraint_set_id).toBe('single_replacement_construction_constraints_v1')
    expect(payload.constructed_candidate.outputs.candidate_weights).toEqual([
      { symbol: 'MSFT', target_weight: 0.4 },
      { symbol: 'IUFS', target_weight: 0.6 },
    ])
    expect(payload.replacement_intent.base_symbol).toBe('AAPL')
    expect(payload.replacement_intent.candidate_symbol).toBe('IUFS')
    expect(payload.snapshot.positions).toHaveLength(2)
    expect(onHypotheticalReplayResult).toHaveBeenCalledWith(hypotheticalResponse)
  })

  it('renders artifact-specific replay integrity failures without softening the backend message', async () => {
    const onHypotheticalReplayResult = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, json: async () => ({ detail: 'constraint_validation rule_id does not match constructed_candidate' }) })
    vi.stubGlobal('fetch', fetchMock)

    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact()} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={null} savedProposalCount={0} onSaveProposal={() => {}} onHypotheticalReplayResult={onHypotheticalReplayResult} />)

    fireEvent.click(screen.getByText('Preview Hypothetical Replay'))
    fireEvent.click(screen.getByText('Run Preview'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    expect(screen.getByText('Replay preview failed: constraint_validation rule_id does not match constructed_candidate')).toBeTruthy()
    expect(onHypotheticalReplayResult).not.toHaveBeenCalled()
  })

  it('submits overlay-aware hypothetical replay payload to the dedicated endpoint', async () => {
    const onHypotheticalReplayResult = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => overlayAwareHypotheticalResponse })
    vi.stubGlobal('fetch', fetchMock)

    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact()} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={null} savedProposalCount={0} onSaveProposal={() => {}} onHypotheticalReplayResult={onHypotheticalReplayResult} />)

    fireEvent.click(screen.getByText('Preview Hypothetical Replay'))
    fireEvent.click(screen.getByRole('radio', { name: /Overlay-aware replay/i }))
    expect(screen.getByText('Overlay State')).toBeTruthy()
    expect(screen.getByText('Cash Residual')).toBeTruthy()
    fireEvent.click(screen.getByText('Run Preview'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, request] = fetchMock.mock.calls[0]
    const payload = JSON.parse(String(request.body))
    expect(String(url)).toContain('/api/backtests/portfolio-allocation/replacement-intent-overlay-preview')
    expect(payload.overlay_state).toMatchObject({
      overlay_id: 'benchmark_trend_overlay_v1',
      status: 'risk_reduced',
      as_of_month_end: '2024-12-31',
      benchmark_symbol: 'SPY',
      signal_basis: '10_month_sma_month_end',
      confirmation_count: 2,
      rule_version: 'v1',
    })
    expect(onHypotheticalReplayResult).toHaveBeenCalledWith(overlayAwareHypotheticalResponse)
  })

  it('blocks hypothetical replay preview when the intent candidate is already held in the draft basis', () => {
    render(<HypotheticalReplaySection result={null} draftSnapshot={{ ...mockDraftSnapshot, positions: [{ symbol: 'AAPL', marketValue: 60000, quantity: 1, currency: 'USD', sector: 'Technology', sourceType: 'etf' }, { symbol: 'IUFS', marketValue: 40000, quantity: 1, currency: 'USD', sector: 'Technology', sourceType: 'etf' }] }} replacementIntentDraft={replacementIntent} formedCandidateArtifact={null} constructedCandidateArtifact={null} constructionConstraintValidationArtifact={null} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={null} savedProposalCount={0} onSaveProposal={() => {}} onHypotheticalReplayResult={() => {}} />)

    expect(screen.getByText('Blocked before preview')).toBeTruthy()
    expect(screen.getByText('A constructed candidate review artifact must exist before hypothetical replay can run.')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Preview Hypothetical Replay' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('renders hypothetical replay provenance and interpretation notes after a preview run', () => {
    const onSaveProposal = vi.fn()
    const referenceResult = hypotheticalResponse.replay.reference_result
    expect(referenceResult).not.toBeNull()
    const replayWithRefusedInvestorEconomics: HypotheticalReplayResponse = {
      ...hypotheticalResponse,
      replay: {
        ...hypotheticalResponse.replay,
        investor_economics_status: withheldInvestorEconomicsStatus,
        reference_result: {
          ...referenceResult!,
          investor_economics_status: withheldInvestorEconomicsStatus,
          metrics: {
            ...referenceResult!.metrics,
            total_return_pct: null,
            annualized_return_pct: null,
            max_drawdown_pct: null,
            sharpe_ratio: null,
            sortino_ratio: null,
            benchmark_return_pct: null,
            excess_return_pct: null,
            information_ratio: null,
          },
        },
        candidate_result: {
          ...hypotheticalResponse.replay.candidate_result,
          investor_economics_status: withheldInvestorEconomicsStatus,
          metrics: {
            ...hypotheticalResponse.replay.candidate_result.metrics,
            total_return_pct: null,
            annualized_return_pct: null,
            max_drawdown_pct: null,
            sharpe_ratio: null,
            sortino_ratio: null,
            benchmark_return_pct: null,
            excess_return_pct: null,
            information_ratio: null,
          },
        },
        comparison: {
          ...hypotheticalResponse.replay.comparison!,
          total_return_diff_pct: null,
          annualized_return_diff_pct: null,
          benchmark_return_diff_pct: null,
          max_drawdown_diff_pct: null,
          sharpe_diff: null,
          sortino_diff: null,
          excess_return_diff_pct: null,
          information_ratio_diff: null,
        },
      },
    }

    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact()} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={replayWithRefusedInvestorEconomics} savedProposalCount={1} onSaveProposal={onSaveProposal} onHypotheticalReplayResult={() => {}} />)

    const readout = screen.getByText('Replay Decision Readout')
    const summary = screen.getAllByText('Replay Summary').find((element) => element.className === 'panel-label') as HTMLElement
    expect(readout.compareDocumentPosition(summary) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(screen.getByText('Baseline: current portfolio basis')).toBeTruthy()
    expect(screen.getByText('Candidate: hypothetical replacement-intent variant')).toBeTruthy()
    expect(screen.getByText('Status: not applied to holdings')).toBeTruthy()
    expect(screen.getByText('Start here before reading the charts and tables. Confirm what this replay compares, what changed in the candidate, and what did not.')).toBeTruthy()
    expect(screen.getByText('Replay Type')).toBeTruthy()
    expect(screen.getByText('Hypothetical current-vs-candidate')).toBeTruthy()
    expect(screen.getAllByText('Intent Pair').length).toBeGreaterThan(0)
    expect(screen.getAllByText('AAPL -> IUFS').length).toBeGreaterThan(0)
    expect(screen.getByText('Baseline Basis')).toBeTruthy()
    expect(screen.getByText('Current draft or imported portfolio state')).toBeTruthy()
    expect(screen.getByText('Candidate Basis')).toBeTruthy()
    expect(screen.getByText('Single replacement-intent variant')).toBeTruthy()
    expect(screen.getByText('What Changed')).toBeTruthy()
    expect(screen.getByText('The candidate replay changes one thing only: it replaces AAPL with IUFS inside a hypothetical draft-only portfolio variant.')).toBeTruthy()
    expect(screen.getByText('What Did Not Change')).toBeTruthy()
    expect(screen.getByText('No holdings have been updated. No construction, optimization, turnover repair, or execution logic has been applied.')).toBeTruthy()
    expect(screen.getAllByText('Baseline and candidate are shown on the same replay window. Treat the candidate as a hypothetical test of the intent, not as an approved portfolio change.').length).toBeGreaterThan(0)
    expect(screen.getByText('When replay/backtest investor total-return equivalence is unverified, suppress all user-facing investor-economics metrics and any derived or comparative views from that basis, including drawdown surfaces, Sharpe, Sortino, benchmark-relative deltas, and monitoring callouts; emit only null/withheld semantics, never numeric fallbacks or zero-equivalent UI states.')).toBeTruthy()
    expect(screen.queryByText('Replay Drawdown')).toBeNull()
    expect(screen.queryByText('Max Drawdown')).toBeNull()
    expect(screen.queryByText('Sharpe Ratio')).toBeNull()
    expect(screen.queryByText('Sortino Ratio')).toBeNull()
    expect(screen.getByText('Tracking Error')).toBeTruthy()
    expect(screen.getByText('Beta vs Benchmark')).toBeTruthy()
    expect(screen.getByText('Save Proposal v2')).toBeTruthy()
    fireEvent.click(screen.getByText('Save Proposal v2'))
    expect(onSaveProposal).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Use this surface to review whether the explicit replacement intent produces a meaningfully different hypothetical path under a shared window. It does not recommend the change or prove it should be applied.')).toBeTruthy()
  })

  it('renders overlay-aware replay framing, overlay basis, and cash residual after preview', () => {
    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact()} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={overlayAwareHypotheticalResponse} savedProposalCount={1} onSaveProposal={() => {}} onHypotheticalReplayResult={() => {}} />)

    expect(screen.getByText('Overlay-aware hypothetical replay')).toBeTruthy()
    expect(screen.getByText('Single replacement-intent variant with overlay-aware candidate scaling')).toBeTruthy()
    expect(screen.getByText('Overlay basis: benchmark_trend_overlay_v1 · risk_reduced · Cash residual 65.00%')).toBeTruthy()
    expect(screen.getByText('Candidate Pre-Overlay')).toBeTruthy()
    expect(screen.getByText('Candidate Post-Overlay')).toBeTruthy()
    expect(screen.getByText('__CASH__')).toBeTruthy()
    expect(screen.getByText('Residual held as hypothetical cash only')).toBeTruthy()
  })

  it('maps candidate formation status and rejection copy for review display', () => {
    render(<CandidateFormationSection draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} onFormedCandidateArtifact={() => {}} />)

    expect(screen.getByText('Formation Status')).toBeTruthy()
    expect(screen.getByText('Formed')).toBeTruthy()
  })

  it('renders explicit construction rule review state', () => {
    render(<ConstructionRuleSection draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact()} selectedConstructionRuleId="same_weight_substitution_v1" onConstructedCandidateArtifact={() => {}} onConstructionConstraintValidationArtifact={() => {}} onSelectedConstructionRuleChange={() => {}} />)

    expect(screen.getAllByText('Construction Rule').length).toBeGreaterThan(0)
    expect(screen.getByText('Constructed')).toBeTruthy()
    expect(screen.getByText('same_weight_substitution_v1')).toBeTruthy()
    expect(screen.getByText('candidate_construction_derived')).toBeTruthy()
  })

  it('reruns construction using the selected fixed split rule', async () => {
    const onConstructedCandidateArtifact = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => makeConstructionResponse('fixed_split_50_50_substitution_v2') })
    vi.stubGlobal('fetch', fetchMock)

    render(<ConstructionRuleSection draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={null} constructionConstraintValidationArtifact={null} selectedConstructionRuleId="fixed_split_50_50_substitution_v2" onConstructedCandidateArtifact={onConstructedCandidateArtifact} onConstructionConstraintValidationArtifact={() => {}} onSelectedConstructionRuleChange={() => {}} />)

    expect(screen.getByDisplayValue('Fixed split 50/50 substitution v2')).toBeTruthy()
    fireEvent.click(screen.getByText('Construct Candidate For Replay'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const payload = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))
    expect(payload.construction_rule.rule_id).toBe('fixed_split_50_50_substitution_v2')
    expect(onConstructedCandidateArtifact).toHaveBeenCalledWith(expect.objectContaining({
      construction: expect.objectContaining({ rule_id: 'fixed_split_50_50_substitution_v2' }),
    }))
  })

  it('shows stale construction state when the selected rule changes', () => {
    render(<ConstructionRuleSection draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={null} selectedConstructionRuleId="fixed_split_50_50_substitution_v2" onConstructedCandidateArtifact={() => {}} onConstructionConstraintValidationArtifact={() => {}} onSelectedConstructionRuleChange={() => {}} />)

    expect(screen.getByText('Stale')).toBeTruthy()
    expect(screen.getByText('The saved construction artifact was built with same_weight_substitution_v1. Rerun construction for fixed_split_50_50_substitution_v2.')).toBeTruthy()
  })

  it('runs construction constraints and renders the validation summary', async () => {
    const onConstructionConstraintValidationArtifact = vi.fn()
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => constructionConstraintValidationResponse })
    vi.stubGlobal('fetch', fetchMock)

    render(<ConstructionRuleSection draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={null} selectedConstructionRuleId="same_weight_substitution_v1" onConstructedCandidateArtifact={() => {}} onConstructionConstraintValidationArtifact={onConstructionConstraintValidationArtifact} onSelectedConstructionRuleChange={() => {}} />)

    fireEvent.click(screen.getByText('Validate Construction Constraints'))

    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1))
    const [url, request] = fetchMock.mock.calls[0]
    const payload = JSON.parse(String(request.body))
    expect(String(url)).toContain('/api/backtests/candidate-construction/replacement-intent/constraints')
    expect(payload.constraint_set).toEqual({ constraint_set_id: 'single_replacement_construction_constraints_v1' })
    expect(payload.constructed_candidate.construction.rule_id).toBe('same_weight_substitution_v1')
    expect(onConstructionConstraintValidationArtifact).toHaveBeenCalledWith(constructionConstraintValidationResponse)
  })

  it('renders construction constraint details and warnings', () => {
    render(<ConstructionRuleSection draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact()} selectedConstructionRuleId="same_weight_substitution_v1" onConstructedCandidateArtifact={() => {}} onConstructionConstraintValidationArtifact={() => {}} onSelectedConstructionRuleChange={() => {}} />)

    expect(screen.getByText('Construction Constraints')).toBeTruthy()
    expect(screen.getByText('Pass')).toBeTruthy()
    expect(screen.getByText('single_replacement_construction_constraints_v1')).toBeTruthy()
    expect(screen.getByText(/Truth provenance: .*constraint_validation_derived/)).toBeTruthy()
    expect(screen.getByText('weight_sum_matches_rule')).toBeTruthy()
    expect(screen.getByText('Warning')).toBeTruthy()
    expect(screen.getByText('Hard block')).toBeTruthy()
    expect(screen.getByText('Constraint validation warnings remain review-only context.')).toBeTruthy()
  })

  it('blocks replay when the constructed artifact does not match the selected rule', () => {
    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact()} selectedConstructionRuleId="fixed_split_50_50_substitution_v2" hypotheticalReplayResult={null} savedProposalCount={0} onSaveProposal={() => {}} onHypotheticalReplayResult={() => {}} />)

    expect(screen.getByText('Blocked before preview')).toBeTruthy()
    expect(screen.getByText('The selected rule is fixed_split_50_50_substitution_v2, but the saved construction artifact was built for same_weight_substitution_v1.')).toBeTruthy()
  })

  it('blocks replay until construction constraints pass', () => {
    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={null} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={null} savedProposalCount={0} onSaveProposal={() => {}} onHypotheticalReplayResult={() => {}} />)

    expect(screen.getByText('Run construction constraints before replay.')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Preview Hypothetical Replay' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows blocked construction constraints in replay preflight', () => {
    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact('blocked')} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={null} savedProposalCount={0} onSaveProposal={() => {}} onHypotheticalReplayResult={() => {}} />)

    expect(screen.getAllByText('Blocked').length).toBeGreaterThan(0)
    expect(screen.getByText('Constraint validation did not pass, so replay remains unavailable.')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Preview Hypothetical Replay' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows rejected construction constraints in replay preflight', () => {
    render(<HypotheticalReplaySection result={null} draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={formedCandidateArtifact} constructedCandidateArtifact={constructedCandidateArtifact} constructionConstraintValidationArtifact={makeConstructionConstraintValidationArtifact('rejected')} selectedConstructionRuleId="same_weight_substitution_v1" hypotheticalReplayResult={null} savedProposalCount={0} onSaveProposal={() => {}} onHypotheticalReplayResult={() => {}} />)

    expect(screen.getByText('Rejected')).toBeTruthy()
    expect(screen.getByText('constructed candidate could not be evaluated safely')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Preview Hypothetical Replay' }) as HTMLButtonElement).disabled).toBe(true)
  })

  it('shows shortened rejection copy in shell-adjacent formation review', () => {
    const rejectedArtifact: FormedCandidateArtifact = {
      ...formedCandidateArtifact,
      formation: {
        ...formedCandidateArtifact.formation,
        formation: { ...formedCandidateArtifact.formation.formation, status: 'rejected' },
        candidate_weights: [],
        formation_summary: { ...formedCandidateArtifact.formation.formation_summary, candidate_start_weight: null, unchanged_positions_count: 0, baseline_positions_count: 0, candidate_positions_count: 0, starting_turnover_pct: null },
        rejection_reason: 'replacement intent candidate is already held in draft snapshot: IUFS',
      },
    }

    render(<CandidateFormationSection draftSnapshot={mockDraftSnapshot} replacementIntentDraft={replacementIntent} formedCandidateArtifact={rejectedArtifact} onFormedCandidateArtifact={() => {}} />)

    expect(screen.getByText('Rejected')).toBeTruthy()
    expect(screen.getByText('replacement intent candidate is already held in draft snapshot: IUFS')).toBeTruthy()
  })

  it('renders diagnostics change as a separate reusable section', () => {
    render(<DiagnosticsChangeSection result={null} hypotheticalReplayResult={hypotheticalResponse} />)

    expect(screen.getByText('Hypothetical Replay Diagnostics Delta Review')).toBeTruthy()
    expect(screen.getByText('Candidate - baseline')).toBeTruthy()
    expect(screen.getByText('Available with degradation. Interpret this comparison cautiously because one or both replay variants have limited diagnostics support.')).toBeTruthy()
    expect(screen.getByText('Volatility Shape')).toBeTruthy()
    expect(screen.queryByText('Volatility & Drawdown')).toBeNull()
    expect(screen.queryByText('Max Drawdown')).toBeNull()
  })

  it('renders saved proposal review from artifact data without relying on live draft state', () => {
    render(<SavedProposalReadoutSection proposal={savedProposal} />)

    expect(screen.getByText('Saved Proposal Review')).toBeTruthy()
    expect(screen.getByText('This is a saved proposal artifact, not live portfolio truth. It preserves prior hypothetical replay outputs and lineage exactly as reviewed when saved, even if the current draft or portfolio state has changed.')).toBeTruthy()
    expect(screen.getByText('Proposal Artifact')).toBeTruthy()
    expect(screen.getAllByText('v1').length).toBeGreaterThan(0)
    expect(screen.getByText('Proposal Lineage')).toBeTruthy()
    expect(screen.getByText(/Workspace: workspace-1 · Draft: draft-1 · Base node: node-1/)).toBeTruthy()
    expect(screen.getByText('Replay lineage: direct preview replay · same-weight substitution · validation not supplied')).toBeTruthy()
    expect(screen.getByText('Proposal Basis')).toBeTruthy()
    expect(screen.getByText('draft_snapshot_positions_normalized')).toBeTruthy()
    expect(screen.getAllByText('Replay Summary').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Diagnostics Delta Summary').length).toBeGreaterThan(0)
    expect(screen.getByText('This proposal is a saved review snapshot, not applied holdings, candidate truth, or live draft state.')).toBeTruthy()
  })
})
