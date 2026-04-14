import type {
  DiagnosticsEngineResponse,
  ImportedBootstrapResponse,
  ImportedBaselineSource,
  ImportedDashboardSource,
  ImportedDiagnosticsSource,
  ImportedExposureFactorModelSource,
  ImportedExposureSource,
  ImportedPortfolioSnapshotSource,
} from '../features/portfolio/types'
import { ib2026DashboardGolden, ib2026ImportedDashboardGoldenFixture } from './ib2026DashboardGolden'

type ImportedAnalysisFixture = ImportedDashboardSource
  & ImportedPortfolioSnapshotSource
  & ImportedExposureSource
  & ImportedDiagnosticsSource
  & ImportedExposureFactorModelSource

export function createLegacyImportedAnalysisFixture() {
  const snapshot = {
    statement: {
      importer: 'interactive_brokers' as const,
      account_id: 'U8516450',
      base_currency: 'USD',
      statement_period: '2025-01-01 - 2025-12-31',
      page_count: 25,
    },
    statements: [
      {
        importer: 'interactive_brokers' as const,
        account_id: 'U8516450',
        base_currency: 'USD',
        statement_period: '2025-01-01 - 2025-12-31',
        page_count: 25,
        source_path: 'C:\\docs\\IB2025.pdf',
        detected_format: 'pdf',
        imported_at: '2026-04-10T00:00:00Z',
      },
    ],
    statement_totals: null,
    positions: [
      { symbol: 'AAPL', quantity: 10, market_value: 10000, currency: 'USD' },
      { symbol: 'MSFT', quantity: 8, market_value: 8000, currency: 'USD' },
    ],
    ledger_entries: [],
    instruments: [],
    cash_balances: [{ currency: 'USD', ending_cash: 1000 }],
  }

  const overview = {
    total_market_value: 50000,
    total_unrealized_pnl: 5000,
    positions_count: 10,
    ledger_entries_count: 100,
    top_positions: [
      { symbol: 'AAPL', market_value: 10000, weight: 0.2, unrealized_pnl: 1200 },
      { symbol: 'MSFT', market_value: 8000, weight: 0.16, unrealized_pnl: 900 },
    ],
    sector_allocation: [
      { sector: 'Technology', market_value: 18000, weight: 0.36 },
      { sector: 'Financials', market_value: 12000, weight: 0.24 },
    ],
    sector_position_breakdown: {
      Technology: [
        { symbol: 'AAPL', market_value: 10000, weight: 0.2 },
        { symbol: 'MSFT', market_value: 8000, weight: 0.16 },
      ],
      Financials: [{ symbol: 'JPM', market_value: 12000, weight: 0.24 }],
    },
    cash_by_currency: { USD: 1000 },
  }

  const diagnostics = {
    snapshot,
    availability: {
      historical_sections_available: true,
      history_context_required: true,
      note: null,
    },
    risk_summary: {
      benchmark_symbol: 'SPY',
      methodology: 'historical regression vs SPY daily returns',
      start_date: '2025-01-02',
      end_date: '2025-03-03',
      observations: 2,
      portfolio_beta: 1.1,
      portfolio_correlation: 0.8,
      r_squared: 0.64,
      portfolio_volatility_pct: 18.2,
      benchmark_volatility_pct: 12.4,
    },
    rolling_risk: [
      { date: '2025-02-03', beta_20d: null, correlation_20d: null, beta_60d: null, correlation_60d: null, beta_252d: null, correlation_252d: null },
      { date: '2025-03-03', beta_20d: 1.05, correlation_20d: 0.78, beta_60d: null, correlation_60d: null, beta_252d: null, correlation_252d: null },
    ],
    relative_risk: {
      benchmark_symbol: 'SPY',
      tracking_error_pct: 7.2,
      active_return_pct: 3.5,
      information_ratio: 0.48,
    },
    volatility_regime: {
      methodology: 'Rolling volatility metrics computed from cash-flow-neutral daily portfolio returns and aligned benchmark returns; drawdown is computed from a compounded return index.',
      assumptions: {
        return_basis: 'time_weighted_daily_return',
        cash_flow_timing: 'external_cash_flow_applied_before_end_of_day_measurement',
        drawdown_basis: 'compounded_return_index',
        benchmark_basis: 'aligned_daily_price_return',
        downside_mar: 0,
        annualization_days: 252,
      },
      rolling_series: [
        {
          date: '2025-02-03',
          portfolio_return: null,
          benchmark_return: null,
          active_return: null,
          realized_vol_20d: null,
          realized_vol_60d: null,
          realized_vol_252d: null,
          downside_vol_20d: null,
          downside_vol_60d: null,
          downside_vol_252d: null,
          benchmark_vol_20d: null,
          benchmark_vol_60d: null,
          benchmark_vol_252d: null,
          tracking_error_20d: null,
          tracking_error_60d: null,
          tracking_error_252d: null,
          drawdown_pct: 0,
          wealth_index: 100,
        },
        {
          date: '2025-03-03',
          portfolio_return: 0.01,
          benchmark_return: 0.004,
          active_return: 0.006,
          realized_vol_20d: 18.4,
          realized_vol_60d: null,
          realized_vol_252d: null,
          downside_vol_20d: null,
          downside_vol_60d: 10.1,
          downside_vol_252d: null,
          benchmark_vol_20d: 12.3,
          benchmark_vol_60d: null,
          benchmark_vol_252d: null,
          tracking_error_20d: 7.2,
          tracking_error_60d: null,
          tracking_error_252d: null,
          drawdown_pct: -4.2,
          wealth_index: 101,
        },
      ],
      snapshot: {
        realized_vol_20d: 18.4,
        realized_vol_60d: null,
        realized_vol_252d: null,
        downside_vol_20d: null,
        downside_vol_60d: 10.1,
        downside_vol_252d: null,
        benchmark_vol_20d: 12.3,
        benchmark_vol_60d: null,
        benchmark_vol_252d: null,
        tracking_error_20d: 7.2,
        tracking_error_60d: null,
        tracking_error_252d: null,
        current_drawdown_pct: -4.2,
        max_drawdown_pct: -8.9,
        vol_ratio_20_60: null,
        vol_ratio_20_252: null,
        current_20d_vol_percentile: 0.78,
      },
      regime: { label: 'normal', confidence: 'medium' },
    },
    factor_exposures: [
      { factor: 'Market', exposure: 1.1, description: 'Historical broad-market beta versus SPY.' },
      { factor: 'Growth Tilt', exposure: 0.42, description: 'Technology and related growth sleeves.' },
      { factor: 'Technology Tilt', exposure: 0.4, description: 'Look-through allocation to technology equity and technology ETF exposure.' },
    ],
    factor_shift_diagnostics: { methodology: 'm', snapshots: [], largest_positive_shifts_20d: [], largest_negative_shifts_20d: [], largest_absolute_shifts_20d: [], largest_absolute_shifts_60d: [] },
    risk_contribution_breakdown: {
      methodology: 'm',
      window_days: 60,
      observation_count: 60,
      status: 'ok',
      factor_contributions: [],
      factor_total_variance: null,
      specific_variance: null,
      total_variance: null,
      factor_risk_share_total: null,
      specific_risk_share: null,
      residual_volatility: null,
      position_contributions: [],
      concentration: { top_1_factor_risk_share: null, top_3_factor_risk_share: null, top_1_position_risk_share: null, top_5_position_risk_share: null, factor_hhi: null, position_hhi: null },
    },
    model_reliability: { window_days: 60, observation_count: 60, r_squared: 0.66, residual_volatility: 5.2, collinearity_pair_count: 0, max_abs_factor_correlation: null, factor_count_used: 12, missing_factor_count: 0, status: 'partial', confidence: 'medium', stability_score: 0.91 },
    factor_registry: [
      { key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', target_exposure: 'US large-cap broad market / S&P 500', primary_mapping: { provider: 'iShares', fund_name: 'iShares Core S&P 500 UCITS ETF', isin: null, example_tickers: ['CSPX', 'SXR8'], asset_exposure: 'S&P 500', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: 'Best institutional UCITS mapping for broad US market beta', match_summary: { score_pct: 89, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.95, historical_similarity: null, structure_fit: 1, implementation_fit: 0.82 } } }, alternative_mappings: [{ provider: 'Vanguard', fund_name: 'Vanguard S&P 500 UCITS ETF', isin: null, example_tickers: ['VUAA'], asset_exposure: 'S&P 500', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: null, match_summary: { score_pct: 89, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.95, historical_similarity: null, structure_fit: 1, implementation_fit: 0.82 } } }], ucits_examples: ['CSPX', 'SXR8', 'VUAA'], mapping_quality: 'high', default_enabled: true, orthogonalization_order: 1, description: 'Broad US equity beta.' },
      { key: 'growth', label: 'Growth', category: 'style', us_proxy: 'QQQ', target_exposure: 'Nasdaq-100 / US mega-cap growth', primary_mapping: { provider: 'Invesco', fund_name: 'Invesco EQQQ Nasdaq-100 UCITS ETF', isin: null, example_tickers: ['EQQQ'], asset_exposure: 'Nasdaq-100', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'distributing', mapping_quality: 'high', notes: null, match_summary: { score_pct: 82, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'degraded', hard_cap_reason: null, components: { exposure_match: 0.94, historical_similarity: null, structure_fit: 0.9, implementation_fit: 0.78 } } }, alternative_mappings: [{ provider: 'iShares', fund_name: 'iShares Nasdaq 100 UCITS ETF', isin: null, example_tickers: ['CNDX'], asset_exposure: 'Nasdaq-100', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: null, match_summary: { score_pct: 84, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.94, historical_similarity: null, structure_fit: 0.98, implementation_fit: 0.78 } } }], ucits_examples: ['EQQQ', 'CNDX'], mapping_quality: 'high', default_enabled: true, orthogonalization_order: 2, description: 'Mega-cap growth and tech tilt.' },
    ],
    factor_methodology: 'Orthogonalized rolling ridge factor model using US ETF proxies for market, style, sector, and macro exposures; UCITS symbols are shown separately as EU execution examples.',
    statistical_factor_model: {
      status: 'partial',
      benchmark_symbol: 'SPY',
      windows: [
        { window_days: 20, observations: 60, start_date: '2025-01-02', end_date: '2025-03-03', status: 'ok' },
        { window_days: 60, observations: 60, start_date: '2025-01-02', end_date: '2025-03-03', status: 'partial' },
        { window_days: 252, observations: 60, start_date: '2025-01-02', end_date: '2025-03-03', status: 'insufficient_history' },
      ],
      rolling_loadings_20d: [{ date: '2025-03-03', market: 1.1, growth: 0.35, value: 0.04, small_cap: 0.03, technology: 0.22, financials: 0.1, health_care: 0.05, energy: 0.01, industrials: 0.02, rates_ief: -0.04, rates_tlt: -0.02, credit: 0.01, commodities: 0.01, alpha: 0.0002, r_squared: 0.67, residual_vol: 5.1 }],
      rolling_loadings_60d: [{ date: '2025-03-03', market: 1.08, growth: 0.31, value: 0.03, small_cap: 0.02, technology: 0.2, financials: 0.09, health_care: 0.06, energy: 0.01, industrials: 0.02, rates_ief: -0.03, rates_tlt: -0.02, credit: 0.01, commodities: 0.01, alpha: 0.0002, r_squared: 0.66, residual_vol: 5.2 }],
      rolling_loadings_252d: [{ date: '2025-03-03', market: null, growth: null, value: null, small_cap: null, technology: null, financials: null, health_care: null, energy: null, industrials: null, rates_ief: null, rates_tlt: null, credit: null, commodities: null, alpha: null, r_squared: null, residual_vol: null }],
      current_factor_snapshot: [
        { key: 'market', label: 'Market', category: 'market', us_proxy: 'SPY', latest_loading: 1.08, target_exposure: 'US large-cap broad market / S&P 500', primary_mapping: { provider: 'iShares', fund_name: 'iShares Core S&P 500 UCITS ETF', isin: null, example_tickers: ['CSPX', 'SXR8'], asset_exposure: 'S&P 500', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: 'Best institutional UCITS mapping for broad US market beta', match_summary: { score_pct: 89, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.95, historical_similarity: null, structure_fit: 1, implementation_fit: 0.82 } } }, alternative_mappings: [{ provider: 'Vanguard', fund_name: 'Vanguard S&P 500 UCITS ETF', isin: null, example_tickers: ['VUAA'], asset_exposure: 'S&P 500', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: null, match_summary: { score_pct: 89, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.95, historical_similarity: null, structure_fit: 1, implementation_fit: 0.82 } } }], ucits_examples: ['CSPX', 'SXR8', 'VUAA'], mapping_quality: 'high', description: 'Broad US equity beta.' },
        { key: 'growth', label: 'Growth', category: 'style', us_proxy: 'QQQ', latest_loading: 0.31, target_exposure: 'Nasdaq-100 / US mega-cap growth', primary_mapping: { provider: 'Invesco', fund_name: 'Invesco EQQQ Nasdaq-100 UCITS ETF', isin: null, example_tickers: ['EQQQ'], asset_exposure: 'Nasdaq-100', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'distributing', mapping_quality: 'high', notes: null, match_summary: { score_pct: 82, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'degraded', hard_cap_reason: null, components: { exposure_match: 0.94, historical_similarity: null, structure_fit: 0.9, implementation_fit: 0.78 } } }, alternative_mappings: [{ provider: 'iShares', fund_name: 'iShares Nasdaq 100 UCITS ETF', isin: null, example_tickers: ['CNDX'], asset_exposure: 'Nasdaq-100', domicile: 'Ireland', trading_currency: 'USD', base_currency: 'USD', currency_hedged: false, distribution_policy: 'accumulating', mapping_quality: 'high', notes: null, match_summary: { score_pct: 84, label: 'Strong Match', score_basis: 'metadata_only', score_status: 'ok', hard_cap_reason: null, components: { exposure_match: 0.94, historical_similarity: null, structure_fit: 0.98, implementation_fit: 0.78 } } }], ucits_examples: ['EQQQ', 'CNDX'], mapping_quality: 'high', description: 'Mega-cap growth and tech tilt.' },
      ],
      collinearity_diagnostics: [
        { window_days: 20, threshold: 0.85, high_collinearity_pairs: [], note: 'No high-collinearity pairs detected.' },
        { window_days: 60, threshold: 0.85, high_collinearity_pairs: [], note: 'No high-collinearity pairs detected.' },
        { window_days: 252, threshold: 0.85, high_collinearity_pairs: [], note: 'No high-collinearity pairs detected.' },
      ],
      insufficient_history: [{ window_days: 252, required_observations: 275, available_observations: 60, missing_factors: [] }],
    },
    stress_scenarios: [{ name: 'Broad Market Selloff', estimated_return_pct: -8.5, description: 'Risk-off equity drawdown.' }],
  }

  return {
    analysis: {
      exposure: {
        snapshot,
        overview,
        lookthrough: {
          portfolio_market_value: 50000,
          covered_market_value: 50000,
          coverage_ratio: 1,
          etf_resolution: { VUAA: 'SPY' },
          uncovered_positions: [],
          top_constituents: [
            { symbol: 'AAPL', name: 'Apple', effective_market_value: 12000, portfolio_weight: 0.24, sources: [{ source_symbol: 'AAPL', source_market_value: 10000, source_weight: 1, resolved_via: 'AAPL' }] },
            { symbol: 'MSFT', name: 'Microsoft', effective_market_value: 9000, portfolio_weight: 0.18, sources: [{ source_symbol: 'MSFT', source_market_value: 8000, source_weight: 1, resolved_via: 'MSFT' }] },
          ],
        },
        lookthrough_sector_exposure: [
          { sector: 'Technology', market_value: 20000, weight: 0.4 },
          { sector: 'Health Care', market_value: 10000, weight: 0.2 },
        ],
        market_overlap: {
          benchmark_symbol: 'SPY',
          overlap_weight: 0.28,
          active_share: 0.62,
          portfolio_in_benchmark_weight: 0.55,
          benchmark_covered_weight: 1,
        },
      },
      diagnostics,
    },
    workflow: {
      history_context: {
        benchmark_symbol: 'SPY',
        statement_period: '2025-01-01 - 2025-12-31',
        imported_at: '2026-04-10T00:00:00Z',
        importer: 'interactive_brokers',
        source_file_names: ['IB2025.pdf'],
        history_start_date: '2025-01-02',
        history_end_date: '2025-03-03',
      },
    },
  }
}

export function createImportedBootstrapResponseFixture(): ImportedBootstrapResponse {
  const analysis = createLegacyImportedAnalysisFixture()
  return {
    snapshot: analysis.analysis.exposure.snapshot,
    overview: analysis.analysis.exposure.overview,
    risk_summary: analysis.analysis.diagnostics.risk_summary,
    history_context: analysis.workflow.history_context ?? null,
  }
}

export function createExposureEngineFixture() {
  return createLegacyImportedAnalysisFixture().analysis.exposure
}

export function createDiagnosticsEngineFixture() {
  return createLegacyImportedAnalysisFixture().analysis.diagnostics
}

export function createImportedAnalysisFixture(): ImportedAnalysisFixture {
  const projection = createLegacyImportedAnalysisFixture()
  return {
    snapshot: projection.analysis.exposure.snapshot,
    overview: projection.analysis.exposure.overview,
    risk_summary: projection.analysis.diagnostics.risk_summary,
    benchmark: { symbol: 'SPY', start_price: 100, end_price: 105, return_pct: 5 },
    performance_series: [
      { date: '2025-01-02', portfolio_value: 10000, benchmark_price: 100, portfolio_return_pct: 0, benchmark_return_pct: 0 },
      { date: '2025-02-03', portfolio_value: 11000, benchmark_price: 102, portfolio_return_pct: 10, benchmark_return_pct: 2 },
      { date: '2025-03-03', portfolio_value: 12000, benchmark_price: 105, portfolio_return_pct: 20, benchmark_return_pct: 5 },
    ],
    daily_states: [
      { date: '2025-01-02', total_market_value: 9000, total_portfolio_value: 10000, external_cash_flow: 0, cash: { USD: 1000 }, positions: [] },
      { date: '2025-02-03', total_market_value: 10000, total_portfolio_value: 11000, external_cash_flow: 1000, cash: { USD: 1000 }, positions: [] },
      { date: '2025-03-03', total_market_value: 11000, total_portfolio_value: 12000, external_cash_flow: 0, cash: { USD: 1000 }, positions: [] },
    ],
    source_status: { performance_history: 'live', monthly_returns: 'live' },
    range_metrics: {
      '1M': {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: 5, excess_return_pct: 15 },
        max_drawdown_pct: 0,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
      '3M': {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: 5, excess_return_pct: 15 },
        max_drawdown_pct: 0,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
      YTD: {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: 5, excess_return_pct: 15 },
        max_drawdown_pct: 0,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
      '1Y': {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: 5, excess_return_pct: 15 },
        max_drawdown_pct: 0,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
      All: {
        summary: { start_value: 10000, end_value: 12000, net_contributions: 1000, investment_gain: 1000, time_weighted_return_pct: 20, money_weighted_return_pct: 9.52, benchmark_return_pct: 5, excess_return_pct: 15 },
        max_drawdown_pct: 0,
        monthly_returns: [{ month: '2025-01', return_pct: 0 }, { month: '2025-02', return_pct: 0 }, { month: '2025-03', return_pct: 0 }],
        monthly_returns_reliable: true,
      },
    },
    rolling_risk: projection.analysis.diagnostics.rolling_risk,
    lookthrough: projection.analysis.exposure.lookthrough,
    lookthrough_sector_exposure: projection.analysis.exposure.lookthrough_sector_exposure,
    market_overlap: projection.analysis.exposure.market_overlap,
    relative_risk: projection.analysis.diagnostics.relative_risk,
    volatility_regime: projection.analysis.diagnostics.volatility_regime,
    factor_exposures: projection.analysis.diagnostics.factor_exposures,
    factor_shift_diagnostics: projection.analysis.diagnostics.factor_shift_diagnostics,
    risk_contribution_breakdown: projection.analysis.diagnostics.risk_contribution_breakdown,
    model_reliability: projection.analysis.diagnostics.model_reliability,
    factor_registry: projection.analysis.diagnostics.factor_registry,
    factor_methodology: projection.analysis.diagnostics.factor_methodology,
    statistical_factor_model: projection.analysis.diagnostics.statistical_factor_model,
    stress_scenarios: projection.analysis.diagnostics.stress_scenarios,
    scenario_preview: null,
  }
}

export function createImportedDashboardFixture(): ImportedDashboardSource & ImportedPortfolioSnapshotSource {
  return createImportedAnalysisFixture()
}

export function createIb2026ImportedDashboardFixture(): ImportedDashboardSource & ImportedPortfolioSnapshotSource {
  return ib2026ImportedDashboardGoldenFixture
}

export function createImportedExposureFixture(): ImportedExposureSource & ImportedDiagnosticsSource & ImportedExposureFactorModelSource {
  return createImportedAnalysisFixture()
}

export function createImportedBaselineFixture(): ImportedBaselineSource {
  const fixture = createImportedAnalysisFixture()
  return {
    snapshot: fixture.snapshot,
    overview: fixture.overview,
  }
}

export function createDiagnosticsFixture(): DiagnosticsEngineResponse {
  return {
    snapshot: {
      statement: { importer: 'interactive_brokers', account_id: 'U1', base_currency: 'USD', statement_period: '2025', page_count: 1 },
      statements: [{ importer: 'interactive_brokers', account_id: 'U1', base_currency: 'USD', statement_period: '2025', page_count: 1, source_path: 'C:\\docs\\IB2025.pdf', detected_format: 'pdf', imported_at: '2026-04-10T00:00:00Z' }],
      positions: [],
      ledger_entries: [],
      instruments: [],
      cash_balances: [],
    },
    risk_summary: { benchmark_symbol: 'SPY', methodology: 'm', start_date: null, end_date: null, observations: 0, portfolio_beta: null, portfolio_correlation: null, r_squared: null, portfolio_volatility_pct: null, benchmark_volatility_pct: null },
    rolling_risk: [],
    relative_risk: { benchmark_symbol: 'SPY', tracking_error_pct: null, active_return_pct: null, information_ratio: null },
    volatility_regime: { methodology: 'm', assumptions: { return_basis: 'time_weighted_daily_return', cash_flow_timing: 'external_cash_flow_applied_before_end_of_day_measurement', drawdown_basis: 'compounded_return_index', benchmark_basis: 'aligned_daily_price_return', downside_mar: 0, annualization_days: 252 }, rolling_series: [], snapshot: { realized_vol_20d: null, realized_vol_60d: null, realized_vol_252d: null, downside_vol_20d: null, downside_vol_60d: null, downside_vol_252d: null, benchmark_vol_20d: null, benchmark_vol_60d: null, benchmark_vol_252d: null, tracking_error_20d: null, tracking_error_60d: null, tracking_error_252d: null, current_drawdown_pct: null, max_drawdown_pct: null, vol_ratio_20_60: null, vol_ratio_20_252: null, current_20d_vol_percentile: null }, regime: { label: 'normal', confidence: 'low' } },
    factor_exposures: [],
    factor_shift_diagnostics: { methodology: 'm', snapshots: [{ key: 'market', label: 'Market', us_proxy: 'SPY', category: 'market', current_loading_20d: 1.1, current_loading_60d: 1.0, current_loading_252d: null, change_20d: 0.3, change_60d: null, abs_change_20d: 0.3, abs_change_60d: null, stability_gap_20d_60d: 0.1, stability_gap_60d_252d: null, available_windows_count: 2, shift_flag_20d: true, shift_flag_60d: false, stability_flag: false, collinearity_flag: false, volatility_flag: true, confidence: 'medium' }], largest_positive_shifts_20d: [{ key: 'market', label: 'Market', us_proxy: 'SPY', current_loading: 1.1, change_value: 0.3, absolute_change: 0.3 }], largest_negative_shifts_20d: [], largest_absolute_shifts_20d: [{ key: 'market', label: 'Market', us_proxy: 'SPY', current_loading: 1.1, change_value: 0.3, absolute_change: 0.3 }], largest_absolute_shifts_60d: [] },
    risk_contribution_breakdown: { methodology: 'm', window_days: 60, observation_count: 60, status: 'ok', factor_contributions: [{ key: 'market', label: 'Market', us_proxy: 'SPY', loading: 1.1, factor_volatility: 12.4, variance_contribution: 0.0123, risk_share: 0.52 }], factor_total_variance: 0.0123, specific_variance: 0.0031, total_variance: 0.0154, factor_risk_share_total: 0.7987, specific_risk_share: 0.2013, residual_volatility: 8.4, position_contributions: [{ symbol: 'AAPL', weight: 0.5, volatility: 20.2, marginal_contribution: 0.0123, component_contribution: 0.0061, risk_share: 0.55 }], concentration: { top_1_factor_risk_share: 0.52, top_3_factor_risk_share: 0.52, top_1_position_risk_share: 0.55, top_5_position_risk_share: 1, factor_hhi: 0.27, position_hhi: 0.51 } },
    model_reliability: { window_days: 60, observation_count: 60, r_squared: 0.66, residual_volatility: 8.4, collinearity_pair_count: 1, max_abs_factor_correlation: 0.89, factor_count_used: 5, missing_factor_count: 7, status: 'ok', confidence: 'medium', stability_score: 0.87 },
    factor_registry: [],
    factor_methodology: null,
    statistical_factor_model: { status: 'partial', benchmark_symbol: 'SPY', windows: [], collinearity_diagnostics: [], current_factor_snapshot: [], insufficient_history: [], rolling_loadings_20d: [], rolling_loadings_60d: [], rolling_loadings_252d: [] },
    stress_scenarios: [],
    availability: { historical_sections_available: true, history_context_required: true, note: null },
  }
}
