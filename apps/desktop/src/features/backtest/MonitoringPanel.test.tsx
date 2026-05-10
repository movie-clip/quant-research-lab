import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type {
  HypotheticalReplayResponse,
  MonitorDefinitionCatalogResponse,
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

const catalogUrl = '/api/backtests/monitor-definitions/catalog?overlay_family=benchmark_trend&monitor_id=benchmark_trend_overlay_v1'
const recentUrl = '/api/backtests/monitor-definitions/recent?limit=1&overlay_family=benchmark_trend&monitor_id=benchmark_trend_overlay_v1&review_support_status=review_supported&lifecycle_status=enabled'

function monitorDefinitionCatalog(overrides: Partial<MonitorDefinitionCatalogResponse> = {}): MonitorDefinitionCatalogResponse {
  const payload: MonitorDefinitionCatalogResponse = {
    items: [
      {
        monitor_definition_id: 'monitor_definition_abc12345def67890',
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
        metadata: {
          metadata_truth: 'authoritative_persisted_artifact_metadata',
          row_provenance: 'persisted_monitor_definition_artifact',
          status: {
            lifecycle: {
              overlay_family: 'benchmark_trend',
              review_support_status: 'review_supported',
              lifecycle_status: 'enabled',
            },
            status_source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot',
            latest_observation_status: 'present',
            latest_observation: {
              observation_id: 'monitor_definition_observation_abc123',
              evaluated_at: '2026-04-24T09:30:00Z',
              observation_status: 'threshold_breach',
              cause_code: null,
              alert_classification: 'action_required',
              hysteresis_transition: 'open',
              recency_status: 'recent',
              source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry',
            },
            latest_evaluation_snapshot_status: 'present',
            latest_evaluation_snapshot: {
              evaluated_at: '2026-04-24T09:30:00Z',
              outcome_status: 'threshold_breach',
              cause_code: null,
              significance_status: 'action_required',
              hysteresis_transition: 'open',
              recency_status: 'recent',
              source_precedence: 'persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact',
            },
          },
        },
      },
    ],
    metadata: {
      contract_version: 'monitor_definition_discovery_v1',
      metadata_truth: 'authoritative_persisted_artifact_metadata',
      row_provenance: 'persisted_monitor_definition_artifact',
      supported_monitor_ids: ['benchmark_trend_overlay_v1'],
      supported_overlay_families: ['benchmark_trend'],
      applied_filters: {
        overlay_family: 'benchmark_trend',
        monitor_id: 'benchmark_trend_overlay_v1',
        review_support_status: null,
        lifecycle_status: null,
        latest_observation_status: null,
        latest_observation_observation_status: null,
        latest_observation_alert_classification: null,
        latest_observation_cause_code: null,
        latest_observation_recency: null,
        latest_evaluation_snapshot_status: null,
        latest_evaluation_snapshot_cause_code: null,
        latest_evaluation_snapshot_recency: null,
      },
    },
  }

  return { ...payload, ...overrides }
}

function stubCatalogResponse(payload: MonitorDefinitionCatalogResponse, ok = true) {
  const fetchMock = vi.fn().mockResolvedValue({ ok, json: async () => payload })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
  vi.unstubAllGlobals()
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
              status_source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot',
              latest_observation_status: 'present',
              latest_observation: {
                observation_id: 'monitor_definition_observation_abc123',
                evaluated_at: '2026-04-24T09:30:00Z',
                observation_status: 'threshold_breach',
                cause_code: null,
                alert_classification: 'action_required',
                hysteresis_transition: 'open',
                recency_status: 'recent',
                source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry',
              },
              latest_evaluation_snapshot_status: 'present',
              latest_evaluation_snapshot: {
                evaluated_at: '2026-04-24T09:30:00Z',
                outcome_status: 'threshold_breach',
                cause_code: null,
                significance_status: 'action_required',
                hysteresis_transition: 'open',
                recency_status: 'recent',
                source_precedence: 'persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact',
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
          latest_observation_status: null,
          latest_observation_observation_status: null,
          latest_observation_alert_classification: null,
          latest_observation_cause_code: null,
          latest_observation_recency: null,
          latest_evaluation_snapshot_status: 'present',
          latest_evaluation_snapshot_cause_code: null,
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
      'status_source_precedence',
      'latest_observation_status',
      'latest_observation',
      'latest_evaluation_snapshot_status',
      'latest_evaluation_snapshot',
    ])
    expect(payload.items[0].metadata.status.lifecycle).toEqual({
      overlay_family: 'benchmark_trend',
      review_support_status: 'review_supported',
      lifecycle_status: 'enabled',
    })
    expect(payload.items[0].metadata.status.status_source_precedence).toBe(
      'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot',
    )
    expect(payload.items[0].metadata.status.latest_evaluation_snapshot_status).toBe('present')
    expect(payload.items[0].metadata.status.latest_observation_status).toBe('present')
    expect(payload.items[0].metadata.status.latest_observation).toEqual({
      observation_id: 'monitor_definition_observation_abc123',
      evaluated_at: '2026-04-24T09:30:00Z',
      observation_status: 'threshold_breach',
      cause_code: null,
      alert_classification: 'action_required',
      hysteresis_transition: 'open',
      recency_status: 'recent',
      source_precedence: 'persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry',
    })
    expect(payload.items[0].metadata.status.latest_evaluation_snapshot).toEqual({
      evaluated_at: '2026-04-24T09:30:00Z',
      outcome_status: 'threshold_breach',
      cause_code: null,
      significance_status: 'action_required',
      hysteresis_transition: 'open',
      recency_status: 'recent',
      source_precedence: 'persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact',
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
        latest_observation_status: null,
        latest_observation_observation_status: null,
        latest_observation_alert_classification: null,
        latest_observation_cause_code: null,
        latest_observation_recency: null,
        latest_evaluation_snapshot_status: 'present',
        latest_evaluation_snapshot_cause_code: null,
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

  it('renders persisted monitoring discipline counts and recent definitions table', async () => {
    const fetchMock = stubCatalogResponse(monitorDefinitionCatalog())

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring Discipline Overview')).toBeTruthy())
    expect(fetchMock).toHaveBeenCalledWith(catalogUrl)
    expect(screen.getByText('1 / 1')).toBeTruthy()
    expect(screen.getAllByText(/present 1/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/recent 1/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/threshold breach 1/).length).toBeGreaterThan(0)
    expect(screen.getByText('monitor_definition_abc12345def67890')).toBeTruthy()
    expect(screen.getByText('SPY')).toBeTruthy()
    expect(screen.getAllByText('present / recent / threshold_breach').length).toBe(2)
  })

  it('marks the benchmark family persisted and review-supported when the catalog is ready with rows', async () => {
    stubCatalogResponse(monitorDefinitionCatalog())

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitor Family Readiness Overview')).toBeTruthy())
    expect(screen.getByText('Benchmark trend overlay')).toBeTruthy()
    expect(screen.getByText('Persisted monitor definition catalog')).toBeTruthy()
    expect(screen.getByText(/Ready \/ ready_persisted_review_supported \/ ready_persisted_review_supported/)).toBeTruthy()
    expect(screen.getByText(/1 persisted definition row with 1 enabled: monitor_definition_abc12345def67890/)).toBeTruthy()
    expect(screen.getByText(/backend catalog metadata truth authoritative_persisted_artifact_metadata/)).toBeTruthy()
    expect(screen.getByText(/row provenance persisted_monitor_definition_artifact/)).toBeTruthy()
    expect(screen.getByText(/monitor definition count 1/)).toBeTruthy()
    expect(screen.getByText(/monitor definition ids monitor_definition_abc12345def67890/)).toBeTruthy()
    expect(screen.getByText(/monitor definition artifact: passed/)).toBeTruthy()
    expect(screen.getByText(/thresholds: passed/)).toBeTruthy()
    expect(screen.getByText(/lineage\/provenance: passed/)).toBeTruthy()
    expect(screen.getByText(/lifecycle metadata: passed/)).toBeTruthy()
    expect(screen.getByText(/review support decision: passed/)).toBeTruthy()
    expect(screen.getByText(/replay evidence: not_applicable/)).toBeTruthy()
  })

  it('blocks benchmark family persisted readiness when catalog rows are disabled only', async () => {
    const payload = monitorDefinitionCatalog()
    payload.items[0].metadata.status.lifecycle.lifecycle_status = 'disabled'
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitor Family Readiness Overview')).toBeTruthy())
    expect(screen.getByText('0 / 1')).toBeTruthy()
    expect(screen.getByText('disabled / review_supported')).toBeTruthy()
    expect(screen.getByText(/Blocked \/ blocked_no_enabled_monitor_definition \/ blocked_no_enabled_monitor_definition/)).toBeTruthy()
    expect(screen.getByText(/1 persisted definition row returned, but 0 are enabled: monitor_definition_abc12345def67890/)).toBeTruthy()
    expect(screen.getByText(/enabled monitor definition count 0/)).toBeTruthy()
    expect(screen.getByText(/lifecycle metadata: blocked \(blocked_no_enabled_monitor_definition\)/)).toBeTruthy()
    expect(screen.queryByText(/Ready \/ ready_persisted_review_supported/)).toBeNull()
  })

  it('renders an explicit empty state for an empty persisted monitoring catalog', async () => {
    stubCatalogResponse(monitorDefinitionCatalog({ items: [] }))

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('No persisted benchmark-trend monitor definitions are available.')).toBeTruthy())
    expect(screen.getByText('The catalog returned no rows for benchmark_trend_overlay_v1.')).toBeTruthy()
    expect(screen.queryByText('1 / 1')).toBeNull()
  })

  it('marks the benchmark family as a persisted empty catalog when no rows are returned', async () => {
    stubCatalogResponse(monitorDefinitionCatalog({ items: [] }))

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText(/Blocked \/ blocked_missing_monitor_definition \/ blocked_missing_monitor_definition/)).toBeTruthy())
    expect(screen.getByText(/No persisted benchmark-trend definitions returned/)).toBeTruthy()
    expect(screen.getAllByText(/monitor definition artifact: blocked \(blocked_missing_monitor_definition\)/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/thresholds: blocked \(blocked_missing_thresholds\)/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/lineage\/provenance: blocked \(blocked_missing_lineage\)/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/lifecycle metadata: blocked \(blocked_missing_lifecycle_metadata\)/).length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText(/review support decision: blocked \(blocked_missing_review_support\)/).length).toBeGreaterThanOrEqual(1)
  })

  it('fails closed without computed counts when persisted monitoring catalog metadata is invalid', async () => {
    stubCatalogResponse({
      ...monitorDefinitionCatalog(),
      metadata: {
        ...monitorDefinitionCatalog().metadata,
        metadata_truth: 'invalid_metadata_truth' as never,
      },
    })

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.getByText('Catalog metadata or row lineage did not match the persisted benchmark-trend monitor definition contract, so no counts were computed.')).toBeTruthy()
    expect(screen.queryByText('1 / 1')).toBeNull()
  })

  it('marks the benchmark family invalid when persisted catalog validation fails', async () => {
    stubCatalogResponse({
      ...monitorDefinitionCatalog(),
      metadata: {
        ...monitorDefinitionCatalog().metadata,
        row_provenance: 'invalid_row_provenance' as never,
      },
    })

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText(/Unavailable \/ unavailable_catalog_invalid \/ unavailable_catalog_invalid/)).toBeTruthy())
    expect(screen.getByText(/Catalog metadata or row lineage failed validation/)).toBeTruthy()
    expect(screen.getByText(/Catalog validation failed before persisted row provenance could be trusted/)).toBeTruthy()
  })

  it('fails closed when persisted monitoring catalog row thresholds are missing', async () => {
    const payload = monitorDefinitionCatalog()
    delete (payload.items[0] as unknown as Record<string, unknown>).thresholds
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText(/Ready \/ ready_persisted_review_supported/)).toBeNull()
    expect(screen.getByText(/thresholds: unavailable \(unavailable_catalog_invalid\)/)).toBeTruthy()
  })

  it('fails closed when persisted monitoring catalog row thresholds are invalid', async () => {
    const payload = monitorDefinitionCatalog()
    ;(payload.items[0].thresholds as unknown as Record<string, unknown>).risk_on_min_risky_weight = Number.POSITIVE_INFINITY
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText(/Ready \/ ready_persisted_review_supported/)).toBeNull()
    expect(screen.getByText(/thresholds: unavailable \(unavailable_catalog_invalid\)/)).toBeTruthy()
  })

  it('fails closed when persisted monitoring catalog row source lineage requirements are missing', async () => {
    const payload = monitorDefinitionCatalog()
    delete (payload.items[0] as unknown as Record<string, unknown>).source_lineage_requirements
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText(/Ready \/ ready_persisted_review_supported/)).toBeNull()
    expect(screen.getByText(/lineage\/provenance: unavailable \(unavailable_catalog_invalid\)/)).toBeTruthy()
  })

  it('fails closed when persisted monitoring catalog row source lineage requirements are invalid', async () => {
    const payload = monitorDefinitionCatalog()
    payload.items[0].source_lineage_requirements.required_portfolio_statement_fields = ['cash']
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText(/Ready \/ ready_persisted_review_supported/)).toBeNull()
    expect(screen.getByText(/lineage\/provenance: unavailable \(unavailable_catalog_invalid\)/)).toBeTruthy()
  })

  it('fails closed when persisted monitoring catalog row status metadata is missing', async () => {
    const payload = monitorDefinitionCatalog()
    delete (payload.items[0].metadata as unknown as Record<string, unknown>).status
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText('1 / 1')).toBeNull()
  })

  it('fails closed when persisted monitoring catalog row lifecycle metadata is missing', async () => {
    const payload = monitorDefinitionCatalog()
    delete (payload.items[0].metadata.status as unknown as Record<string, unknown>).lifecycle
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText('1 / 1')).toBeNull()
  })

  it('fails closed when latest observation is marked present without a nested observation', async () => {
    const payload = monitorDefinitionCatalog()
    payload.items[0].metadata.status.latest_observation_status = 'present'
    payload.items[0].metadata.status.latest_observation = null
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText('1 / 1')).toBeNull()
  })

  it('fails closed when latest snapshot is marked present without a nested snapshot', async () => {
    const payload = monitorDefinitionCatalog()
    payload.items[0].metadata.status.latest_evaluation_snapshot_status = 'present'
    payload.items[0].metadata.status.latest_evaluation_snapshot = null
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText('1 / 1')).toBeNull()
  })

  it('renders explicit absent labels for missing latest observation and snapshot', async () => {
    const payload = monitorDefinitionCatalog()
    payload.items[0].metadata.status.latest_observation_status = 'absent'
    payload.items[0].metadata.status.latest_observation = null
    payload.items[0].metadata.status.latest_evaluation_snapshot_status = 'absent'
    payload.items[0].metadata.status.latest_evaluation_snapshot = null
    stubCatalogResponse(payload)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('monitor_definition_abc12345def67890')).toBeTruthy())
    expect(screen.getByText('absent / no latest observation')).toBeTruthy()
    expect(screen.getByText('absent / no latest snapshot')).toBeTruthy()
  })

  it('fails closed when persisted monitoring catalog rows mix monitor id or overlay family', async () => {
    const payload = monitorDefinitionCatalog()
    stubCatalogResponse({
      ...payload,
      items: [
        payload.items[0],
        {
          ...payload.items[0],
          monitor_definition_id: 'monitor_definition_wrong_family',
          monitor_id: 'unexpected_monitor_id' as never,
        },
      ],
    })

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview failed validation.')).toBeTruthy())
    expect(screen.queryByText('monitor_definition_abc12345def67890')).toBeNull()
    expect(screen.queryByText('2 / 2')).toBeNull()
  })

  it('shows unavailable when the persisted monitoring catalog request fails', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitoring discipline overview is unavailable.')).toBeTruthy())
    expect(screen.getByText('The persisted monitor-definition catalog could not be loaded.')).toBeTruthy()
  })

  it('marks the benchmark family unavailable when the persisted catalog cannot load', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('network down')))

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText(/Catalog unavailable/)).toBeTruthy())
    expect(screen.getByText(/Unavailable \/ unavailable_catalog_load_failed \/ unavailable_catalog_load_failed/)).toBeTruthy()
    expect(screen.getByText(/backend catalog request failed/)).toBeTruthy()
  })

  it('keeps non-persisted replay signals separate with explicit blocked reason codes and gates', async () => {
    stubCatalogResponse(monitorDefinitionCatalog())

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={null} />)

    await waitFor(() => expect(screen.getByText('Monitor Family Readiness Overview')).toBeTruthy())
    expect(screen.getByText('Factor drift signal')).toBeTruthy()
    expect(screen.getByText('Concentration drift signal')).toBeTruthy()
    expect(screen.getByText('Benchmark-relative signal')).toBeTruthy()
    expect(screen.getByText('Volatility signal')).toBeTruthy()
    expect(screen.getByText('Data quality signal')).toBeTruthy()
    expect(screen.getAllByText('Replay-derived only')).toHaveLength(5)
    expect(screen.getAllByText(/Blocked \/ not_persisted \/ blocked_missing_monitor_definition/)).toHaveLength(5)
    expect(screen.getAllByText(/Replay-derived diagnostics\/watch-group evidence:/)).toHaveLength(5)
    expect(screen.getAllByText(/Replay-derived diagnostics\/watch-group signal evidence only\. Not a persisted monitor family/)).toHaveLength(5)
    expect(screen.getAllByText(/monitor definition artifact: blocked \(blocked_missing_monitor_definition\)/).length).toBeGreaterThanOrEqual(5)
    expect(screen.getAllByText(/thresholds: blocked \(blocked_missing_thresholds\)/).length).toBeGreaterThanOrEqual(5)
    expect(screen.getAllByText(/lineage\/provenance: blocked \(blocked_missing_lineage\)/).length).toBeGreaterThanOrEqual(5)
    expect(screen.getAllByText(/lifecycle metadata: blocked \(blocked_missing_lifecycle_metadata\)/).length).toBeGreaterThanOrEqual(5)
    expect(screen.getAllByText(/review support decision: blocked \(blocked_missing_review_support\)/).length).toBeGreaterThanOrEqual(5)
    expect(screen.getAllByText(/replay evidence: passed/)).toHaveLength(5)
  })

  it('does not render review handoff buttons inside replay signal readiness rows', async () => {
    const fetchMock = vi.fn((url: string) => Promise.resolve({
      ok: true,
      json: async () => url === catalogUrl ? monitorDefinitionCatalog() : {
        items: [{ monitor_definition_id: 'monitor_definition_abc12345def67890', monitor_id: 'benchmark_trend_overlay_v1' }],
        metadata: {},
      },
    }))
    vi.stubGlobal('fetch', fetchMock)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={hypotheticalReplay} onReviewInResearch={vi.fn()} />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Review In Workspace' })).toBeTruthy())
    const readinessSection = screen.getByTestId('monitor-family-readiness-overview')
    expect(readinessSection.querySelectorAll('button')).toHaveLength(0)
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

  it('marks candidate readiness evidence unavailable when replay diagnostics are unavailable', async () => {
    stubCatalogResponse(monitorDefinitionCatalog())

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

    await waitFor(() => expect(screen.getByText('Monitor Family Readiness Overview')).toBeTruthy())
    expect(screen.getAllByText(/Unavailable \/ evidence_unavailable \/ blocked_replay_evidence_unavailable/)).toHaveLength(5)
    expect(screen.getAllByText(/Replay diagnostics\/watch-group evidence unavailable; readiness is not assessed/)).toHaveLength(5)
    expect(screen.getAllByText(/replay evidence: unavailable \(blocked_replay_evidence_unavailable\)/)).toHaveLength(5)
    expect(screen.queryByText(/Blocked \/ not_persisted \/ blocked_missing_monitor_definition/)).toBeNull()
  })

  it('resolves the recent definition and hands off the definition-scoped review contract for supported monitoring items', async () => {
    const onReviewInResearch = vi.fn()
    const fetchMock = vi.fn((url: string) => Promise.resolve({
      ok: true,
      json: async () => url === catalogUrl ? monitorDefinitionCatalog() : {
        items: [{ monitor_definition_id: 'monitor_definition_abc12345def67890', monitor_id: 'benchmark_trend_overlay_v1' }],
        metadata: {},
      },
    }))

    vi.stubGlobal('fetch', fetchMock)

    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={hypotheticalReplay} onReviewInResearch={onReviewInResearch} />)

    await waitFor(() => expect(screen.getByRole('button', { name: 'Review In Workspace' })).toBeTruthy())

    expect(fetchMock).toHaveBeenCalledWith(recentUrl)

    fireEvent.click(screen.getByRole('button', { name: 'Review In Workspace' }))

    expect(onReviewInResearch).toHaveBeenCalledTimes(1)
    expect(onReviewInResearch).toHaveBeenCalledWith({
      version: 1,
      source: 'monitoring',
      monitorKey: 'factor-drift',
      monitorTitle: 'Factor Drift',
      researchTarget: 'diagnostics_change',
      contextLabel: 'Market',
      replayContext: 'AAPL -> IUFS',
      monitorDefinitionReview: {
        source: 'definition_scoped_alert_review_entrypoint',
        monitorDefinitionId: 'monitor_definition_abc12345def67890',
      },
    })

    fireEvent.click(screen.getByRole('button', { name: /Data Quality/i }))
    expect(screen.queryByRole('button', { name: 'Review In Workspace' })).toBeNull()
  })
})
