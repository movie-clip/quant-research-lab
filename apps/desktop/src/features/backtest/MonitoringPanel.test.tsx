import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { HypotheticalReplayResponse, PortfolioAllocationBacktestResponse } from '../portfolio/types'
import { MonitoringPanel } from './MonitoringPanel'

const baseReplay: PortfolioAllocationBacktestResponse = {
  methodology: 'm',
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
    instrument_metadata: [],
    starting_weights: [],
    ending_weights: [],
    metrics: { total_return_pct: 10, annualized_return_pct: 10, annualized_volatility_pct: 9, downside_volatility_pct: 5, max_drawdown_pct: -3, sharpe_ratio: 1.1, sortino_ratio: 1.4, benchmark_return_pct: 7, excess_return_pct: 3, tracking_error_pct: 4, information_ratio: 0.5, beta_vs_benchmark: 0.8, correlation_vs_benchmark: 0.85, total_turnover_pct: 12, turnover_events_count: 2, total_cost_paid: 45 },
    equity_curve: [],
    rebalance_events: [],
    trades: [],
  },
  comparison: { total_return_diff_pct: 2, annualized_return_diff_pct: 2, annualized_volatility_diff_pct: -1, downside_volatility_diff_pct: -1, max_drawdown_diff_pct: 1, sharpe_diff: 0.3, sortino_diff: 0.3, excess_return_diff_pct: 2, tracking_error_diff_pct: 1, information_ratio_diff: 0.2, beta_diff: -0.2, correlation_diff: -0.05, total_turnover_diff_pct: 12, total_cost_diff: 45 },
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
    top_volatility_change: { key: 'annualized_volatility', label: 'Annualized Volatility', baseline_value: 10, candidate_value: 9, delta_value: -1, selection_rule: 'fixed_priority', rationale: 'Selected by fixed priority order: max drawdown, then annualized volatility, then downside volatility.' },
    risk_contribution_changes: [],
    top_risk_contribution_change: null,
    concentration_changes: [{ key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16 }],
    top_concentration_change: { key: 'factor_hhi', label: 'Factor HHI', baseline_value: 0.36, candidate_value: 0.2, delta_value: -0.16, selection_rule: 'fixed_priority', rationale: 'Selected by fixed priority order: factor HHI, then top 1 position risk share.' },
    stress_scenario_changes: [],
    top_stress_scenario_change: null,
  },
}

const hypotheticalReplay: HypotheticalReplayResponse = {
  proposal: { source: 'draft_replacement_intent', incumbent_symbol: 'AAPL', candidate_symbol: 'IUFS', draft_id: 'draft-1', base_node_id: 'node-1' },
  derivation: { baseline_basis: 'draft_snapshot_positions_normalized', candidate_construction_rule: 'single_symbol_weight_substitution' },
  baseline_weights: [{ symbol: 'AAPL', target_weight: 0.6 }],
  candidate_weights: [{ symbol: 'IUFS', target_weight: 0.6 }],
  replay: baseReplay,
  warnings: [],
}

describe('MonitoringPanel', () => {
  it('renders top callouts, grouped monitors, and detail drilldown', () => {
    render(<MonitoringPanel result={baseReplay} hypotheticalReplayResult={hypotheticalReplay} />)

    expect(screen.getByText('Monitoring')).toBeTruthy()
    expect(screen.getByText('Research watch surface')).toBeTruthy()
    expect(screen.getByText('Top Factor Callout')).toBeTruthy()
    expect(screen.getByText('Top Concentration Callout')).toBeTruthy()
    expect(screen.getByText('Watch Groups')).toBeTruthy()
    expect(screen.getAllByText('Factor Drift').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Concentration Drift').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Benchmark-Relative Drift').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Volatility / Regime').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Data Quality').length).toBeGreaterThan(0)
    expect(screen.getByText('Monitoring reflects the active hypothetical replay for AAPL -> IUFS.')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /Data Quality/i }))

    expect(screen.getAllByText('Degraded').length).toBeGreaterThan(0)
    expect(screen.getByText('Candidate replay status: degraded.')).toBeTruthy()
  })

  it('shows explicit waiting state when no replay evidence exists', () => {
    render(<MonitoringPanel result={null} hypotheticalReplayResult={null} />)

    expect(screen.getByText('Monitoring is waiting for replay evidence.')).toBeTruthy()
    expect(screen.getByText('Run a portfolio improvement replay or restore a saved replay review to populate the first monitoring surface.')).toBeTruthy()
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
  })
})
