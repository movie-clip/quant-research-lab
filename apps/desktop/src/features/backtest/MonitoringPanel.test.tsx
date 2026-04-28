import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  HypotheticalReplayResponse,
  MonitorDefinitionRecentResponse,
  PortfolioAllocationBacktestResponse,
} from '../portfolio/types'
import { MonitoringPanel } from './MonitoringPanel'

const baseReplay: PortfolioAllocationBacktestResponse = {
  methodology: 'm',
  investor_economics_status: { status: 'available', reason: null },
  reference_result: {
    portfolio_name: 'Reference',
    benchmark_symbol: 'SPY',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    observation_count: 3,
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
    metrics: { total_return_pct: 8, annualized_return_pct: 8, annualized_volatility_pct: 10, downside_volatility_pct: 6, max_drawdown_pct: -4, sharpe_ratio: 0.8, sortino_ratio: 1.1, benchmark_return_pct: 7, excess_return_pct: 1, tracking_error_pct: 3, information_ratio: 0.3, beta_vs_benchmark: 1, correlation_vs_benchmark: 0.9, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 },
    equity_curve: [],
    rebalance_events: [],
    trades: [],
  },
  candidate_result: {
    portfolio_name: 'Candidate',
    benchmark_symbol: 'SPY',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    observation_count: 3,
    rebalance_frequency: 'monthly',
    commission_bps: 0,
    slippage_bps: 0,
    drift_tolerance_pct: null,
    assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' },
    status: 'degraded',
    investor_economics_status: { status: 'available', reason: null },
    instrument_metadata: [],
    starting_weights: [],
    ending_weights: [],
    metrics: { total_return_pct: 10, annualized_return_pct: 10, annualized_volatility_pct: 9, downside_volatility_pct: 5, max_drawdown_pct: -3, sharpe_ratio: 1.1, sortino_ratio: 1.4, benchmark_return_pct: 7, excess_return_pct: 3, tracking_error_pct: 4, information_ratio: 0.5, beta_vs_benchmark: 0.8, correlation_vs_benchmark: 0.85, total_turnover_pct: 12, turnover_events_count: 2, total_cost_paid: 45 },
    equity_curve: [],
    rebalance_events: [],
    trades: [],
  },
  comparison: { total_return_diff_pct: 2, annualized_return_diff_pct: 2, benchmark_return_diff_pct: 0, annualized_volatility_diff_pct: -1, downside_volatility_diff_pct: -1, max_drawdown_diff_pct: 1, sharpe_diff: 0.3, sortino_diff: 0.3, excess_return_diff_pct: 2, tracking_error_diff_pct: 1, information_ratio_diff: 0.2, beta_diff: -0.2, correlation_diff: -0.05, total_turnover_diff_pct: 12, total_cost_diff: 45 },
  reference_diagnostics: {
    provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' },
    factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 1, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }],
    volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 10, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 6, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 3, current_drawdown_pct: -2, max_drawdown_pct: -4, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null },
    risk_contribution: null,
    stress_scenarios: [],
  },
  candidate_diagnostics: {
    provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' },
    factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 0.8, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }],
    volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 9, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 5, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 4, current_drawdown_pct: -1.5, max_drawdown_pct: -3, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null },
    risk_contribution: null,
    stress_scenarios: [],
  },
  diagnostics_comparison: {
    factor_exposure_changes: [{ key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2 }],
    top_factor_exposure_change: { key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2, selection_rule: 'largest_absolute_delta', rationale: 'Largest valid factor exposure delta in this group (candidate - baseline).' },
    volatility_changes: [{ key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1 }],
    top_volatility_change: { key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1, selection_rule: 'fixed_priority', rationale: 'When replay/backtest investor total-return equivalence is unverified, suppress all user-facing investor-economics metrics and any derived or comparative views from that basis, including drawdown surfaces, Sharpe, Sortino, benchmark-relative deltas, and monitoring callouts; emit only null/withheld semantics, never numeric fallbacks or zero-equivalent UI states. Selected by fixed priority order across allowed replay risk-shape metrics: annualized volatility, then downside volatility, then tracking error.' },
    risk_contribution_changes: [],
    top_risk_contribution_change: null,
    concentration_changes: [{ key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16 }],
    top_concentration_change: { key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16, selection_rule: 'fixed_priority', rationale: 'Selected by fixed priority order: factor HHI, then top 1 position risk share.' },
    stress_scenario_changes: [],
    top_stress_scenario_change: null,
  },
}

const hypotheticalReplay: HypotheticalReplayResponse = {
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
  baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
  candidate_weights: [{ symbol: 'IUFS', target_weight: 0.6 }],
  replay: baseReplay,
  warnings: [],
}

afterEach(() => {
  cleanup()
})

describe('MonitoringPanel', () => {
  it('deserializes monitor-definition recent discovery metadata with canonical latest-snapshot fields', () => {
    const payload: MonitorDefinitionRecentResponse = {
      items: [
        {
          monitor_definition_id: 'monitor-1',
          monitor_id: 'benchmark_trend_overlay_v1',
          benchmark_symbol: 'SPY',
          schema_version: 'monitor_definition_artifact_v1',
          fingerprint: 'fp-1',
          review_scope: 'current_portfolio_truth_only',
          evaluation_mode: 'review_only_observation_evaluation',
          observation_statuses: ['ok', 'threshold_breach'],
          thresholds: {
            minimum_confirmation_count: 2,
            risk_on_min_risky_weight: 0.8,
            risk_on_max_cash_weight: 0.2,
            risk_reduced_max_risky_weight: 0.5,
            risk_reduced_min_cash_weight: 0.5,
          },
          source_lineage_requirements: {
            benchmark_source_kind: 'benchmark_overlay_signal',
            portfolio_truth_basis: 'imported_portfolio_snapshot',
            required_portfolio_statement_fields: ['positions'],
            required_benchmark_observation_fields: ['status'],
          },
          artifact_last_modified_at: '2026-04-24T10:00:00Z',
          metadata: {
            metadata_truth: 'authoritative_persisted_artifact_metadata',
            row_provenance: 'persisted_monitor_definition_artifact',
            recent_order_provenance: 'persisted_artifact_file_mtime',
            status: {
              lifecycle: {
                overlay_family: 'benchmark_trend',
                review_support_status: 'review_supported',
                lifecycle_status: 'enabled',
              },
              latest_evaluation_snapshot_status: 'present',
              latest_evaluation_snapshot: {
                evaluated_at: '2026-04-24T09:30:00Z',
                outcome_status: 'threshold_breach',
                significance_status: 'action_required',
                recency_status: 'recent',
              },
            },
          },
        },
      ],
      metadata: {
        contract_version: 'monitor_definition_discovery_v1',
        metadata_truth: 'authoritative_persisted_artifact_metadata',
        row_provenance: 'persisted_monitor_definition_artifact',
        recent_order_provenance: 'persisted_artifact_file_mtime',
        supported_monitor_ids: ['benchmark_trend_overlay_v1'],
        supported_overlay_families: ['benchmark_trend'],
        applied_filters: {
          overlay_family: 'benchmark_trend',
          monitor_id: null,
          review_support_status: 'review_supported',
          lifecycle_status: 'enabled',
          latest_evaluation_snapshot_status: 'present',
          latest_evaluation_snapshot_recency: 'recent',
        },
      },
    }

    expect(Object.keys(payload.items[0].metadata)).toEqual([
      'metadata_truth',
      'row_provenance',
      'recent_order_provenance',
      'status',
    ])
    expect(Object.keys(payload.items[0].metadata.status)).toEqual([
      'lifecycle',
      'latest_evaluation_snapshot_status',
      'latest_evaluation_snapshot',
    ])
    expect(payload.items[0].metadata.status.lifecycle).toEqual({
      overlay_family: 'benchmark_trend',
      review_support_status: 'review_supported',
      lifecycle_status: 'enabled',
    })
    expect(payload.items[0].metadata.status.latest_evaluation_snapshot_status).toBe('present')
    expect(payload.items[0].metadata.status.latest_evaluation_snapshot).toEqual({
      evaluated_at: '2026-04-24T09:30:00Z',
      outcome_status: 'threshold_breach',
      significance_status: 'action_required',
      recency_status: 'recent',
    })
    expect(payload.metadata).toEqual({
      contract_version: 'monitor_definition_discovery_v1',
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_artifact',
      recent_order_provenance: 'persisted_artifact_file_mtime',
      supported_monitor_ids: ['benchmark_trend_overlay_v1'],
      supported_overlay_families: ['benchmark_trend'],
      applied_filters: {
        overlay_family: 'benchmark_trend',
        monitor_id: null,
        review_support_status: 'review_supported',
        lifecycle_status: 'enabled',
        latest_evaluation_snapshot_status: 'present',
        latest_evaluation_snapshot_recency: 'recent',
      },
    })
  })

  it('renders top callouts, grouped monitors, and detail drilldown', () => {
    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={hypotheticalReplay} />)

    expect(screen.getByText('Monitoring')).toBeTruthy()
    expect(screen.getByText('Watch surface')).toBeTruthy()
    expect(screen.getByText('Top Factor Callout')).toBeTruthy()
    expect(screen.getByText('Top Concentration Callout')).toBeTruthy()
    expect(screen.queryByText('Top Volatility Callout')).toBeNull()
    expect(screen.getByText('Watch Groups')).toBeTruthy()
    expect(screen.getAllByText('Factor Drift').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Concentration Drift').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Benchmark-Relative Drift').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Volatility Shape').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Data Quality').length).toBeGreaterThan(0)
    expect(screen.getByText('Monitoring reflects the active hypothetical replay for AAPL -> IUFS.')).toBeTruthy()
    expect(screen.getByText(/Replay-derived market history/)).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Data Quality/i }))

    expect(screen.getAllByText('Degraded').length).toBeGreaterThan(0)
    expect(screen.getByText('Candidate replay status: degraded.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Benchmark-Relative Drift/i }))
    expect(screen.getByText('This monitor stays on tracking error, beta, and correlation only rather than investor-performance benchmark-relative outcomes.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Volatility Shape/i }))
    expect(screen.getByText('This monitor stays on allowed volatility-shape context and does not rely on investor-performance drawdown readouts.')).toBeTruthy()
  })

  it('uses explicit investor economics metadata for withheld monitoring guidance', () => {
    render(
      <MonitoringPanel
        result={{
          ...baseReplay,
          investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
          reference_result: baseReplay.reference_result ? {
            ...baseReplay.reference_result,
            investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
          } : null,
          candidate_result: {
            ...baseReplay.candidate_result,
            investor_economics_status: { status: 'withheld', reason: 'withheld_unverified_total_return_equivalence' },
          },
        }}
        hypotheticalReplayResult={null}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Benchmark-Relative Drift/i }))
    expect(screen.getByText('Investor-performance benchmark-relative deltas are withheld for this replay state because total-return equivalence is unverified.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Volatility Shape/i }))
    expect(screen.getByText('Investor-performance drawdown views are withheld for this replay state because total-return equivalence is unverified.')).toBeTruthy()
  })

  it('shows explicit waiting state when no replay evidence exists', () => {
    render(<MonitoringPanel result={null} hypotheticalReplayResult={null} />)

    expect(screen.getByText('Monitoring is waiting for replay evidence.')).toBeTruthy()
    expect(screen.getByText('Run or reopen a replay to populate this view.')).toBeTruthy()
  })

  it('handles unavailable diagnostics rows honestly', () => {
    render(
      <MonitoringPanel
        result={{
          ...baseReplay,
          candidate_result: { ...baseReplay.candidate_result, status: 'ok' },
          candidate_diagnostics: null,
          reference_diagnostics: null,
          diagnostics_comparison: null,
        }}
        hypotheticalReplayResult={null}
      />,
    )

    expect(screen.getAllByText('Unavailable').length).toBeGreaterThan(0)
    expect(screen.getByText('No factor-drift callout is available for the current replay state.')).toBeTruthy()
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0)
  })

  it('offers explicit Review In Workspace only for supported monitoring items', () => {
    const onReviewInResearch = vi.fn()

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={hypotheticalReplay} onReviewInResearch={onReviewInResearch} />)

    expect(screen.getByRole('button', { name: 'Review In Workspace' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Review In Workspace' }))

    expect(onReviewInResearch).toHaveBeenCalledWith(expect.objectContaining({
      version: 1,
      source: 'monitoring',
      monitorKey: 'factor-drift',
      monitorTitle: 'Factor Drift',
      researchTarget: 'diagnostics_change',
      replayContext: 'AAPL -> IUFS',
    }))

    fireEvent.click(screen.getByRole('button', { name: /Data Quality/i }))
    expect(screen.queryByRole('button', { name: 'Review In Workspace' })).toBeNull()
  })
})
