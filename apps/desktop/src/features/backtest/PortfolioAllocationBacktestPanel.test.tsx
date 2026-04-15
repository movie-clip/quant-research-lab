import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { PortfolioAllocationBacktestPanel } from './PortfolioAllocationBacktestPanel'
import type { ImportedBaselineSource, PortfolioAllocationBacktestResponse } from '../portfolio/types'

const mockAnalysis = {
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

const mockResponse: PortfolioAllocationBacktestResponse = {
  methodology: 'm',
  reference_result: {
    portfolio_name: 'Reference', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 3, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null, assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' }, status: 'ok', instrument_metadata: [{ symbol: 'SPY', trading_currency: 'USD', instrument_base_currency: 'USD', currency_hedged: null, distribution_policy: 'unknown' }], starting_weights: [{ symbol: 'SPY', target_weight: 1 }], ending_weights: [{ symbol: 'SPY', target_weight: 1 }], metrics: { total_return_pct: 8, annualized_return_pct: 8, annualized_volatility_pct: 10, downside_volatility_pct: 6, max_drawdown_pct: -4, sharpe_ratio: 0.8, sortino_ratio: 1.1, benchmark_return_pct: 7, excess_return_pct: 1, tracking_error_pct: 3, information_ratio: 0.3, beta_vs_benchmark: 1, correlation_vs_benchmark: 0.9, total_turnover_pct: 0, turnover_events_count: 0, total_cost_paid: 0 }, equity_curve: [{ date: '2024-01-01', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-06-01', equity: 103000, cash: 0, gross_exposure: 103000, drawdown_pct: -1 }, { date: '2024-12-31', equity: 108000, cash: 0, gross_exposure: 108000, drawdown_pct: -2 }], rebalance_events: [], trades: [] },
  candidate_result: {
    portfolio_name: 'Candidate', benchmark_symbol: 'SPY', start_date: '2024-01-01', end_date: '2024-12-31', observation_count: 3, rebalance_frequency: 'monthly', commission_bps: 0, slippage_bps: 0, drift_tolerance_pct: null, assumptions: { price_basis: 'adjusted_close', execution_price_field: 'close', execution_lag_days: 1, calendar_policy: 'intersection_common_dates', fractional_shares: true, long_only: true, leverage_allowed: false, tax_treatment: 'pre_tax', investor_base_currency: 'USD' }, status: 'degraded', instrument_metadata: [{ symbol: 'SPY', trading_currency: 'USD', instrument_base_currency: 'USD', currency_hedged: null, distribution_policy: 'unknown' }, { symbol: 'TLT', trading_currency: 'USD', instrument_base_currency: 'USD', currency_hedged: null, distribution_policy: 'unknown' }], starting_weights: [{ symbol: 'SPY', target_weight: 0.6 }, { symbol: 'TLT', target_weight: 0.4 }], ending_weights: [{ symbol: 'SPY', target_weight: 0.58 }, { symbol: 'TLT', target_weight: 0.42 }], metrics: { total_return_pct: 10, annualized_return_pct: 10, annualized_volatility_pct: 9, downside_volatility_pct: 5, max_drawdown_pct: -3, sharpe_ratio: 1.1, sortino_ratio: 1.4, benchmark_return_pct: 7, excess_return_pct: 3, tracking_error_pct: 4, information_ratio: 0.5, beta_vs_benchmark: 0.8, correlation_vs_benchmark: 0.85, total_turnover_pct: 12, turnover_events_count: 2, total_cost_paid: 45 }, equity_curve: [{ date: '2024-01-01', equity: 100000, cash: 0, gross_exposure: 100000, drawdown_pct: 0 }, { date: '2024-06-01', equity: 104000, cash: 0, gross_exposure: 104000, drawdown_pct: -0.5 }, { date: '2024-12-31', equity: 110000, cash: 0, gross_exposure: 110000, drawdown_pct: -1.5 }], rebalance_events: [{ decision_date: '2024-01-31', execution_date: '2024-02-01', turnover_pct: 5, traded_notional: 5000, total_cost: 15 }], trades: [{ date: '2024-02-01', symbol: 'SPY', action: 'buy', quantity: 1, price: 100, traded_notional: 100, commission_cost: 0.5, slippage_cost: 0.5, total_cost: 1 }] },
  comparison: { total_return_diff_pct: 2, annualized_return_diff_pct: 2, annualized_volatility_diff_pct: -1, downside_volatility_diff_pct: -1, max_drawdown_diff_pct: 1, sharpe_diff: 0.3, sortino_diff: 0.3, excess_return_diff_pct: 2, tracking_error_diff_pct: 1, information_ratio_diff: 0.2, beta_diff: -0.2, correlation_diff: -0.05, total_turnover_diff_pct: 12, total_cost_diff: 45 },
  reference_diagnostics: { provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' }, factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 1, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }], volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 10, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 6, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 3, current_drawdown_pct: -2, max_drawdown_pct: -4, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null }, risk_contribution: { methodology: 'm', window_days: 60, observation_count: 60, status: 'ok', factor_contributions: [{ key: 'market', label: 'Market', us_proxy: 'SPY', loading: 1, factor_volatility: 12, variance_contribution: 0.01, risk_share: 0.6 }], factor_total_variance: 0.01, specific_variance: 0.005, total_variance: 0.015, factor_risk_share_total: 0.6667, specific_risk_share: 0.3333, residual_volatility: 5, position_contributions: [{ symbol: 'SPY', weight: 1, volatility: 10, marginal_contribution: 0.01, component_contribution: 0.01, risk_share: 1 }], concentration: { top_1_factor_risk_share: 0.6, top_3_factor_risk_share: 0.6, top_1_position_risk_share: 1, top_5_position_risk_share: 1, factor_hhi: 0.36, position_hhi: 1 } }, stress_scenarios: [{ name: 'Broad Market Selloff', estimated_return_pct: -8.5, description: 'x' }] },
  candidate_diagnostics: { provenance: { snapshot_basis: 'synthetic_replay_snapshot', historical_basis: 'market_data_history', note: 'Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.' }, factor_snapshot: [{ key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 0.8, target_exposure: null, primary_mapping: null, alternative_mappings: [], ucits_examples: [], mapping_quality: 'high', description: 'broad market' }], volatility_snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: 9, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: 5, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: 4, current_drawdown_pct: -1.5, max_drawdown_pct: -3, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null }, risk_contribution: { methodology: 'm', window_days: 60, observation_count: 60, status: 'ok', factor_contributions: [{ key: 'market', label: 'Market', us_proxy: 'SPY', loading: 0.8, factor_volatility: 11, variance_contribution: 0.008, risk_share: 0.45 }], factor_total_variance: 0.008, specific_variance: 0.004, total_variance: 0.012, factor_risk_share_total: 0.6667, specific_risk_share: 0.3333, residual_volatility: 4.5, position_contributions: [{ symbol: 'SPY', weight: 0.6, volatility: 9, marginal_contribution: 0.008, component_contribution: 0.006, risk_share: 0.7 }], concentration: { top_1_factor_risk_share: 0.45, top_3_factor_risk_share: 0.45, top_1_position_risk_share: 0.7, top_5_position_risk_share: 1, factor_hhi: 0.2, position_hhi: 0.58 } }, stress_scenarios: [{ name: 'Broad Market Selloff', estimated_return_pct: -6.4, description: 'x' }] },
  diagnostics_comparison: {
    factor_exposure_changes: [{ key: 'market', label: 'Market', baseline_value: 1, candidate_value: 0.8, delta_value: -0.2 }],
    volatility_changes: [{ key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1 }],
    risk_contribution_changes: [{ key: 'market', label: 'Market', baseline_value: 0.6, candidate_value: 0.45, delta_value: -0.15 }],
    concentration_changes: [{ key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16 }],
    stress_scenario_changes: [{ key: 'broad_market_selloff', label: 'Broad Market Selloff', baseline_value: -8.5, candidate_value: -6.4, delta_value: 2.1 }],
  },
}

describe('PortfolioAllocationBacktestPanel', () => {
  afterEach(() => {
    cleanup()
    vi.restoreAllMocks()
  })

  it('renders workspace sections and diagnostics comparison', () => {
    render(<PortfolioAllocationBacktestPanel result={mockResponse} onResult={() => {}} analysis={mockAnalysis} />)

    expect(screen.getByText('Current Import')).toBeTruthy()
    expect(screen.getByText('Baseline Portfolio')).toBeTruthy()
    expect(screen.getByText('Candidate Portfolio Builder')).toBeTruthy()
    expect(screen.getByText('Replay Summary')).toBeTruthy()
    expect(screen.getByText('Before / After Diagnostics')).toBeTruthy()
    expect(screen.getByText(/Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data/)).toBeTruthy()
    expect(screen.getByText('Factor Exposure Change')).toBeTruthy()
    expect(screen.getByText('Stress Scenario Change')).toBeTruthy()
    expect(screen.getByText('Implementation Details')).toBeTruthy()
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
})
