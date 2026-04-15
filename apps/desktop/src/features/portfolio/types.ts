export type ReconciliationCheck = {
  name: string
  expected: number | null
  actual: number | null
  difference: number | null
  passed: boolean
  detail: string
}

export type ActivityPoint = {
  month: string
  buys: number
  sells: number
  dividends: number
  withholding_tax: number
  interest: number
  fees: number
  deposits: number
  withdrawals: number
  net_cash_flow: number
}

export type CanonicalLedgerRecord = {
  date: string
  entry_type: string
  account_bucket: 'TRADE' | 'INCOME' | 'EXPENSE' | 'TRANSFER'
  symbol: string | null
  description: string | null
  signed_quantity: number | null
  quantity: number | null
  price: number | null
  gross_amount: number | null
  net_amount: number | null
  cash_effect: number
  asset_currency: string | null
  cash_currency: string
  affects_positions: boolean
  affects_cash: boolean
  fee: number | null
  tax: number | null
  source_section: string
  source_line: string | null
}

export type ImportedStatementImporter = 'interactive_brokers' | 'freedom24' | 'espp' | 'multi_broker'

export type ImportedStatementRecord = {
  importer: ImportedStatementImporter
  account_id: string | null
  base_currency: string | null
  statement_period: string | null
  page_count: number | null
  source_path?: string
  detected_format?: string
  imported_at?: string
}

export type ImportedSnapshot = {
  statement: ImportedStatementRecord
  statements: ImportedStatementRecord[]
  statement_totals?: {
    stock_total: number | null
    cash_total: number | null
    dividends_total: number | null
    withholding_tax_total: number | null
    interest_total: number | null
    other_fees_total: number | null
    deposits_total: number | null
    starting_nav: number | null
    ending_nav: number | null
    fx_rates: Record<string, number>
  } | null
  positions: Array<{
    symbol: string
    quantity: number
    market_value: number
    currency: string
    as_of_date?: string
    cost_basis?: number | null
    close_price?: number | null
    unrealized_pnl?: number | null
  }>
  ledger_entries: Array<unknown>
  instruments: Array<unknown>
  cash_balances: Array<{ currency: string; ending_cash: number | null }>
}

export type PortfolioOverview = {
  total_market_value: number
  total_unrealized_pnl: number
  positions_count: number
  ledger_entries_count: number
  top_positions: Array<{ symbol: string; market_value: number; weight: number; unrealized_pnl: number }>
  sector_allocation: Array<{ sector: string; market_value: number; weight: number }>
  sector_position_breakdown: Record<string, Array<{ symbol: string; market_value: number; weight: number }>>
  cash_by_currency: Record<string, number>
}

export type BenchmarkSummary = {
  symbol: string
  start_price: number | null
  end_price: number | null
  return_pct: number | null
}

export type PortfolioRiskSummary = {
  benchmark_symbol: string
  methodology: string
  start_date: string | null
  end_date: string | null
  observations: number
  portfolio_beta: number | null
  portfolio_correlation: number | null
  r_squared: number | null
  portfolio_volatility_pct: number | null
  benchmark_volatility_pct: number | null
}

export type RollingRiskPoint = {
  date: string
  beta_20d: number | null
  correlation_20d: number | null
  beta_60d: number | null
  correlation_60d: number | null
  beta_252d: number | null
  correlation_252d: number | null
}

export type LookThroughOverview = {
  portfolio_market_value: number
  covered_market_value: number
  coverage_ratio: number
  etf_resolution: Record<string, string>
  uncovered_positions: string[]
  top_constituents: Array<{
    symbol: string
    name: string
    effective_market_value: number
    portfolio_weight: number
    sources: Array<{
      source_symbol: string
      source_market_value: number
      source_weight: number
      resolved_via: string
    }>
  }>
}

export type LookThroughSectorExposure = {
  sector: string
  market_value: number
  weight: number
}

export type MarketOverlapSummary = {
  benchmark_symbol: string
  overlap_weight: number | null
  active_share: number | null
  portfolio_in_benchmark_weight: number | null
  benchmark_covered_weight: number | null
}

export type RelativeRiskSummary = {
  benchmark_symbol: string
  tracking_error_pct: number | null
  active_return_pct: number | null
  information_ratio: number | null
}

export type FactorExposurePoint = {
  factor: string
  exposure: number | null
  description: string
  basis?: string
}

export type FactorShiftDiagnostics = {
  methodology: string
  snapshots: Array<{
    key: string
    label: string
    us_proxy: string
    category: string
    current_loading_20d: number | null
    current_loading_60d: number | null
    current_loading_252d: number | null
    change_20d: number | null
    change_60d: number | null
    abs_change_20d: number | null
    abs_change_60d: number | null
    stability_gap_20d_60d: number | null
    stability_gap_60d_252d: number | null
    available_windows_count: number
    shift_flag_20d: boolean
    shift_flag_60d: boolean
    stability_flag: boolean
    collinearity_flag: boolean
    volatility_flag: boolean
    confidence: string
  }>
  largest_positive_shifts_20d: Array<{
    key: string
    label: string
    us_proxy: string
    current_loading: number | null
    change_value: number | null
    absolute_change: number | null
  }>
  largest_negative_shifts_20d: Array<{
    key: string
    label: string
    us_proxy: string
    current_loading: number | null
    change_value: number | null
    absolute_change: number | null
  }>
  largest_absolute_shifts_20d: Array<{
    key: string
    label: string
    us_proxy: string
    current_loading: number | null
    change_value: number | null
    absolute_change: number | null
  }>
  largest_absolute_shifts_60d: Array<{
    key: string
    label: string
    us_proxy: string
    current_loading: number | null
    change_value: number | null
    absolute_change: number | null
  }>
}

export type ModelReliabilitySnapshot = {
  window_days: number
  observation_count: number
  r_squared: number | null
  residual_volatility: number | null
  collinearity_pair_count: number
  max_abs_factor_correlation: number | null
  factor_count_used: number
  missing_factor_count: number
  status: string
  confidence: string
  stability_score: number | null
}

export type SourceStatus = {
  performance_history: string
  monthly_returns: string
}

export type DashboardRangeMetrics = {
  summary: {
    start_value: number | null
    end_value: number | null
    net_contributions: number
    investment_gain: number | null
    time_weighted_return_pct: number | null
    money_weighted_return_pct: number | null
    benchmark_return_pct: number | null
    excess_return_pct: number | null
  }
  max_drawdown_pct: number | null
  monthly_returns: Array<{
    month: string
    return_pct: number
  }>
  monthly_returns_reliable: boolean
}

export type PerformanceSeriesPoint = {
  date: string
  portfolio_value: number
  benchmark_price: number | null
  portfolio_return_pct: number | null
  benchmark_return_pct: number | null
}

export type DailyPortfolioState = {
  date: string
  total_market_value: number
  total_portfolio_value: number
  external_cash_flow: number
  cash: Record<string, number>
  positions: Array<{ symbol: string; quantity: number; market_price: number | null; market_value: number | null }>
}

export type ScenarioPreview = {
  mode: string
  methodology: string
  base_capital: number
  gross_exposure: number
  net_capital: number
  leverage_ratio: number
  scenario_aware_sections: string[]
  historical_baseline_sections: string[]
  sector_drifts: Array<{
    name: string
    base_weight: number
    scenario_weight: number
    delta_weight: number
  }>
  position_drifts: Array<{
    symbol: string
    base_market_value: number
    scenario_market_value: number
    delta_market_value: number
    base_weight: number
    scenario_weight: number
    delta_weight: number
  }>
  factor_drifts: Array<{
    factor: string
    base_exposure: number
    scenario_exposure: number
    delta_exposure: number
    unit: 'ratio' | 'weight'
  }>
  scenario_stress_scenarios?: Array<{
    name: string
    estimated_return_pct: number
    base_estimated_return_pct: number
    delta_return_pct: number
    driver: string
    description: string
  }>
  scenario_risk_contribution?: RiskContributionBreakdown
} | null

export type MappingMatchSummary = {
  score_pct: number | null
  label: string | null
  score_basis: string
  score_status: string
  hard_cap_reason: string | null
  components: {
    exposure_match: number | null
    historical_similarity: number | null
    structure_fit: number | null
    implementation_fit: number | null
  }
}

export type UcitsMapping = {
  provider: string
  fund_name: string
  isin: string | null
  example_tickers: string[]
  asset_exposure: string
  domicile: string | null
  trading_currency: string | null
  base_currency: string | null
  currency_hedged: boolean | null
  distribution_policy: string
  mapping_quality: string
  notes: string | null
  match_summary: MappingMatchSummary | null
}

export type FactorRegistryEntry = {
  key: string
  label: string
  category: 'market' | 'style' | 'sector' | 'macro' | string
  us_proxy: string
  target_exposure: string | null
  primary_mapping: UcitsMapping | null
  alternative_mappings: UcitsMapping[]
  ucits_examples: string[]
  mapping_quality: string
  default_enabled: boolean
  orthogonalization_order: number
  description: string
}

export type VolatilitySnapshot = {
  realized_vol_20d: number | null
  realized_vol_60d: number | null
  realized_vol_252d: number | null
  downside_vol_20d: number | null
  downside_vol_60d: number | null
  downside_vol_252d: number | null
  benchmark_vol_20d: number | null
  benchmark_vol_60d: number | null
  benchmark_vol_252d: number | null
  tracking_error_20d: number | null
  tracking_error_60d: number | null
  tracking_error_252d: number | null
  current_drawdown_pct: number | null
  max_drawdown_pct: number | null
  vol_ratio_20_60: number | null
  vol_ratio_20_252: number | null
  current_20d_vol_percentile: number | null
}

export type VolatilityRegimePayload = {
  methodology: string
  assumptions: {
    return_basis: string
    cash_flow_timing: string
    drawdown_basis: string
    benchmark_basis: string
    downside_mar: number
    annualization_days: number
  }
  rolling_series: Array<{
    date: string
    portfolio_return: number | null
    benchmark_return: number | null
    active_return: number | null
    realized_vol_20d: number | null
    realized_vol_60d: number | null
    realized_vol_252d: number | null
    downside_vol_20d: number | null
    downside_vol_60d: number | null
    downside_vol_252d: number | null
    benchmark_vol_20d: number | null
    benchmark_vol_60d: number | null
    benchmark_vol_252d: number | null
    tracking_error_20d: number | null
    tracking_error_60d: number | null
    tracking_error_252d: number | null
    drawdown_pct: number | null
    wealth_index: number | null
  }>
  snapshot: VolatilitySnapshot
  regime: {
    label: string
    confidence: string
  }
}

export type StatisticalFactorSnapshotItem = {
  key: string
  label: string
  category: string
  us_proxy: string
  latest_loading: number | null
  target_exposure: string | null
  primary_mapping: UcitsMapping | null
  alternative_mappings: UcitsMapping[]
  ucits_examples: string[]
  mapping_quality: string
  description: string
}

export type StatisticalFactorModel = {
  status: 'ok' | 'insufficient_history' | 'partial' | string
  benchmark_symbol: string
  windows: Array<{
    window_days: number
    observations: number
    start_date: string | null
    end_date: string | null
    status: 'ok' | 'insufficient_history' | 'partial' | string
  }>
  collinearity_diagnostics: Array<{
    window_days: number
    threshold: number
    high_collinearity_pairs: Array<{
      left_key: string
      right_key: string
      left_proxy: string
      right_proxy: string
      correlation: number
    }>
    note: string | null
  }>
  current_factor_snapshot: StatisticalFactorSnapshotItem[]
  insufficient_history: Array<{
    window_days: number
    required_observations: number
    available_observations: number
    missing_factors: string[]
  }>
  rolling_loadings_20d: Array<{
    date: string
    market: number | null
    growth: number | null
    value: number | null
    small_cap: number | null
    technology?: number | null
    financials: number | null
    health_care: number | null
    energy: number | null
    industrials: number | null
    rates_ief: number | null
    rates_tlt: number | null
    credit: number | null
    commodities: number | null
    alpha: number | null
    r_squared: number | null
    residual_vol: number | null
  }>
  rolling_loadings_60d: Array<{
    date: string
    market: number | null
    growth: number | null
    value: number | null
    small_cap: number | null
    technology?: number | null
    financials: number | null
    health_care: number | null
    energy: number | null
    industrials: number | null
    rates_ief: number | null
    rates_tlt: number | null
    credit: number | null
    commodities: number | null
    alpha: number | null
    r_squared: number | null
    residual_vol: number | null
  }>
  rolling_loadings_252d: Array<{
    date: string
    market: number | null
    growth: number | null
    value: number | null
    small_cap: number | null
    technology?: number | null
    financials: number | null
    health_care: number | null
    energy: number | null
    industrials: number | null
    rates_ief: number | null
    rates_tlt: number | null
    credit: number | null
    commodities: number | null
    alpha: number | null
    r_squared: number | null
    residual_vol: number | null
  }>
}

export type RiskContributionBreakdown = {
  methodology: string
  window_days: number
  observation_count: number
  status: string
  factor_contributions: Array<{
    key: string
    label: string
    us_proxy: string
    loading: number | null
    factor_volatility: number | null
    variance_contribution: number | null
    risk_share: number | null
  }>
  factor_total_variance: number | null
  specific_variance: number | null
  total_variance: number | null
  factor_risk_share_total: number | null
  specific_risk_share: number | null
  residual_volatility: number | null
  position_contributions: Array<{
    symbol: string
    weight: number
    volatility: number | null
    marginal_contribution: number | null
    component_contribution: number | null
    risk_share: number | null
  }>
  concentration: {
    top_1_factor_risk_share: number | null
    top_3_factor_risk_share: number | null
    top_1_position_risk_share: number | null
    top_5_position_risk_share: number | null
    factor_hhi: number | null
    position_hhi: number | null
  }
}

export type StressScenarioResult = {
  name: string
  estimated_return_pct: number
  description: string
}

export type DiagnosticsAvailability = {
  historical_sections_available: boolean
  history_context_required: boolean
  note: string | null
}

export type ImportedHistoryContext = {
  benchmark_symbol: string
  statement_period: string | null
  imported_at: string | null
  importer: ImportedStatementImporter | null
  source_file_names: string[]
  history_start_date: string | null
  history_end_date: string | null
}

export type ExposureEnginePayload = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  lookthrough: LookThroughOverview
  lookthrough_sector_exposure: LookThroughSectorExposure[]
  market_overlap: MarketOverlapSummary
}

export type DiagnosticsPayload = {
  snapshot: ImportedSnapshot
  availability: DiagnosticsAvailability
  risk_summary: PortfolioRiskSummary
  rolling_risk: RollingRiskPoint[]
  relative_risk: RelativeRiskSummary
  volatility_regime: VolatilityRegimePayload
  factor_exposures: FactorExposurePoint[]
  factor_shift_diagnostics: FactorShiftDiagnostics
  risk_contribution_breakdown: RiskContributionBreakdown
  model_reliability: ModelReliabilitySnapshot
  factor_registry: FactorRegistryEntry[]
  factor_methodology: string | null
  statistical_factor_model: StatisticalFactorModel
  stress_scenarios: StressScenarioResult[]
}

export type ImportedBootstrapResponse = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  risk_summary: PortfolioRiskSummary
  history_context?: ImportedHistoryContext | null
}

export type ImportedPortfolioSnapshotSource = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  risk_summary: PortfolioRiskSummary
  benchmark: BenchmarkSummary | null
}

export type ImportedDashboardSource = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  performance_series: PerformanceSeriesPoint[]
  daily_states: DailyPortfolioState[]
  source_status?: SourceStatus | null
  range_metrics?: Record<string, DashboardRangeMetrics> | null
}

export type ImportedBaselineSource = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
}

export type ExposureAvailabilityStatus = 'live' | 'partial' | 'unavailable'
export type ExposureAvailabilityConfidence = 'high' | 'medium' | 'low'

export type ExposureAvailability = {
  lookthrough_status: ExposureAvailabilityStatus
  lookthrough_confidence: ExposureAvailabilityConfidence
  benchmark_overlap_status: ExposureAvailabilityStatus
  benchmark_overlap_confidence: ExposureAvailabilityConfidence
  note: string | null
}

export type ComposedExposureAvailability = ExposureAvailability & {
  historical_diagnostics_confidence: ExposureAvailabilityConfidence
}

export type ImportedExposureSource = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  lookthrough: LookThroughOverview
  lookthrough_sector_exposure: LookThroughSectorExposure[]
  market_overlap: MarketOverlapSummary
  exposure_availability?: (ExposureAvailability & {
    historical_diagnostics_confidence?: ExposureAvailabilityConfidence
  }) | null
  risk_summary: PortfolioRiskSummary
  rolling_risk: RollingRiskPoint[]
  relative_risk: RelativeRiskSummary
  volatility_regime: VolatilityRegimePayload
  factor_exposures: FactorExposurePoint[]
  model_reliability: ModelReliabilitySnapshot
  factor_registry: FactorRegistryEntry[]
  factor_methodology: string | null
  statistical_factor_model: StatisticalFactorModel
  stress_scenarios: StressScenarioResult[]
  benchmark: BenchmarkSummary | null
  scenario_preview: ScenarioPreview
  availability?: {
    historical_sections_available: boolean
    history_context_required: boolean
    note: string | null
  } | null
}

export type ImportedDiagnosticsSource = {
  snapshot: ImportedSnapshot
  risk_summary: PortfolioRiskSummary
  rolling_risk: RollingRiskPoint[]
  relative_risk: RelativeRiskSummary
  volatility_regime: VolatilityRegimePayload
  factor_exposures: FactorExposurePoint[]
  factor_shift_diagnostics: FactorShiftDiagnostics
  risk_contribution_breakdown: RiskContributionBreakdown
  model_reliability: ModelReliabilitySnapshot
  factor_registry: FactorRegistryEntry[]
  factor_methodology: string | null
  statistical_factor_model: StatisticalFactorModel
  stress_scenarios: StressScenarioResult[]
}

export type ImportedExposureFactorModelSource = {
  benchmark: BenchmarkSummary | null
  factor_methodology: string | null
  factor_registry: FactorRegistryEntry[]
  statistical_factor_model: StatisticalFactorModel
}

export type ExposureEngineResponse = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  lookthrough: LookThroughOverview
  lookthrough_sector_exposure: LookThroughSectorExposure[]
  market_overlap: MarketOverlapSummary
  availability: ExposureAvailability
}

export type DashboardHistoryEngineResponse = {
  daily_states: DailyPortfolioState[]
  performance_series: PerformanceSeriesPoint[]
  source_status?: SourceStatus | null
  benchmark: BenchmarkSummary | null
  range_metrics?: Record<string, DashboardRangeMetrics> | null
}

export type DashboardAnalysis = ImportedDashboardSource

export type PortfolioBaselineAnalysis = ImportedBaselineSource

export type ExposureAnalysis = ImportedExposureSource

export type DiagnosticsEngineResponse = ImportedDiagnosticsSource & {
  availability: {
    historical_sections_available: boolean
    history_context_required: boolean
    note: string | null
  }
}

export type ExposureFactorModelResponse = {
  benchmark_symbol: string
  methodology: string
  factor_registry: Array<{
    key: string
    label: string
    category: 'market' | 'style' | 'sector' | 'macro' | string
    us_proxy: string
    target_exposure: string | null
    primary_mapping: FactorRegistryEntry['primary_mapping']
    alternative_mappings: FactorRegistryEntry['alternative_mappings']
    ucits_examples: string[]
    mapping_quality: string
    default_enabled: boolean
    orthogonalization_order: number
    description: string
  }>
  statistical_factor_model: {
    status: 'ok' | 'insufficient_history' | 'partial' | string
    benchmark_symbol: string
    windows: Array<{
      window_days: number
      observations: number
      start_date: string | null
      end_date: string | null
      status: 'ok' | 'insufficient_history' | 'partial' | string
    }>
    rolling_loadings_20d: StatisticalFactorModel['rolling_loadings_20d']
    rolling_loadings_60d: StatisticalFactorModel['rolling_loadings_60d']
    rolling_loadings_252d: StatisticalFactorModel['rolling_loadings_252d']
    current_factor_snapshot: StatisticalFactorModel['current_factor_snapshot']
    collinearity_diagnostics: StatisticalFactorModel['collinearity_diagnostics']
    insufficient_history: StatisticalFactorModel['insufficient_history']
  }
}

export type StrategyDefinition = {
  strategy_id: string
  name: string
  description: string | null
  timeframe: string
  side: string
  universe: string[]
  parameters: Array<{ name: string; value: string | number | boolean }>
  tags: string[]
}

export type BacktestConfig = {
  strategy: StrategyDefinition
  benchmark_symbol: string | null
  start_date: string
  end_date: string
  initial_capital: number
  base_currency: string
  slippage_bps: number
  commission_per_contract: number
  rebalance_frequency: string
  use_continuous_contracts: boolean
  continuous_series: {
    root_symbol: string
    roll_method: string
    roll_days_before_expiry: number
    back_adjusted: boolean
    price_field: string
  } | null
}

export type BacktestRunResponse = {
  run_id: string
  config: BacktestConfig
  dataset_info: Record<string, { symbol: string; timeframe: string; source: string; continuous: boolean; ready: boolean }>
  trades: Array<{
    date: string
    symbol: string
    action: string
    quantity: number
    price: number | null
    notional: number | null
    fee: number | null
  }>
  positions: Array<{
    date: string
    symbol: string
    quantity: number
    market_price: number | null
    market_value: number | null
    notional_exposure: number | null
  }>
  equity_curve: Array<{
    date: string
    equity: number
    cash: number
    gross_exposure: number | null
    net_exposure: number | null
    drawdown_pct: number | null
  }>
  total_return_pct: number | null
  annualized_return_pct: number | null
  max_drawdown_pct: number | null
  sharpe_ratio: number | null
  overlay_preview: {
    overlay_id: string
    base_portfolio_name: string
    allocations: Array<{
      sleeve_id: string
      name: string
      capital_weight: number
      source: string
      strategy_run_id: string | null
    }>
    equity_curve: Array<{
      date: string
      equity: number
      cash: number
      gross_exposure: number | null
      net_exposure: number | null
      drawdown_pct: number | null
    }>
    notes: string | null
  } | null
}

export type EtfMomentumStrategyResponse = {
  strategy_id: string
  title: string
  benchmark_symbol: string
  universe: string[]
  start_date: string
  end_date: string
  rebalance_frequency: 'monthly' | 'quarterly' | 'none'
  lookback_months: number
  top_n: number
  methodology: string
  current_rankings: Array<{
    symbol: string
    target_weight: number
    score: number
    trailing_return_pct: number
    average_volume: number | null
  }>
  latest_holdings: Array<{
    symbol: string
    target_weight: number
    score: number
    trailing_return_pct: number
    average_volume: number | null
  }>
  observations: Array<{
    date: string
    rankings: Array<{
      symbol: string
      target_weight: number
      score: number
      trailing_return_pct: number
      average_volume: number | null
    }>
    holdings: Array<{
      symbol: string
      target_weight: number
      score: number
      trailing_return_pct: number
      average_volume: number | null
    }>
    leader: string | null
    leader_score: number | null
    benchmark_return_pct: number | null
    strategy_return_pct: number | null
    average_volume_ratio: number | null
  }>
  leader_internals: Array<{
    date: string
    leader_symbol: string | null
    source_mode: string
    snapshot_date: string | null
    constituents: Array<{
      symbol: string
      name: string
      weight: number
      trailing_return_pct: number | null
      weighted_contribution_pct: number | null
    }>
  }>
  etf_internals_history: Record<string, Array<{
    date: string
    etf_symbol: string
    source_mode: string
    snapshot_date: string | null
    constituents: Array<{
      symbol: string
      name: string
      weight: number
      trailing_return_pct: number | null
      weighted_contribution_pct: number | null
    }>
  }>>
  source_status: {
    price_history: string
    leader_internals: string
    holdings_snapshot_counts: Record<string, number>
    dated_holdings_symbols: string[]
    sample_fallback_symbols: string[]
  }
  equity_curve: Array<{
    date: string
    strategy_equity: number
    benchmark_equity: number
    strategy_drawdown_pct: number | null
    benchmark_drawdown_pct: number | null
  }>
  metrics: {
    total_return_pct: number | null
    benchmark_return_pct: number | null
    excess_return_pct: number | null
    annualized_return_pct: number | null
    max_drawdown_pct: number | null
    benchmark_max_drawdown_pct: number | null
    win_rate_pct: number | null
    average_turnover_pct: number | null
    average_volume_participation_ratio: number | null
  }
}

export type AllocationBacktestWeight = {
  symbol: string
  target_weight: number
}

export type AllocationBacktestTrade = {
  date: string
  symbol: string
  action: 'buy' | 'sell'
  quantity: number
  price: number | null
  traded_notional: number | null
  commission_cost: number | null
  slippage_cost: number | null
  total_cost: number | null
}

export type AllocationBacktestRebalanceEvent = {
  decision_date: string
  execution_date: string
  turnover_pct: number | null
  traded_notional: number | null
  total_cost: number | null
}

export type AllocationBacktestAssumptions = {
  price_basis: string
  execution_price_field: string
  execution_lag_days: number
  calendar_policy: string
  fractional_shares: boolean
  long_only: boolean
  leverage_allowed: boolean
  tax_treatment: string
  investor_base_currency: string | null
}

export type AllocationBacktestInstrumentMeta = {
  symbol: string
  trading_currency: string | null
  instrument_base_currency: string | null
  currency_hedged: boolean | null
  distribution_policy: 'accumulating' | 'distributing' | 'unknown'
}

export type AllocationBacktestPoint = {
  date: string
  equity: number
  cash: number
  gross_exposure: number | null
  drawdown_pct: number | null
}

export type AllocationBacktestMetrics = {
  total_return_pct: number | null
  annualized_return_pct: number | null
  annualized_volatility_pct: number | null
  downside_volatility_pct: number | null
  max_drawdown_pct: number | null
  sharpe_ratio: number | null
  sortino_ratio: number | null
  benchmark_return_pct: number | null
  excess_return_pct: number | null
  tracking_error_pct: number | null
  information_ratio: number | null
  beta_vs_benchmark: number | null
  correlation_vs_benchmark: number | null
  total_turnover_pct: number | null
  turnover_events_count: number
  total_cost_paid: number | null
}

export type AllocationBacktestResult = {
  portfolio_name: string | null
  benchmark_symbol: string | null
  start_date: string
  end_date: string
  observation_count: number
  rebalance_frequency: 'none' | 'monthly' | 'quarterly'
  commission_bps: number
  slippage_bps: number
  drift_tolerance_pct: number | null
  assumptions: AllocationBacktestAssumptions
  status: 'ok' | 'degraded' | 'rejected'
  instrument_metadata: AllocationBacktestInstrumentMeta[]
  starting_weights: AllocationBacktestWeight[]
  ending_weights: AllocationBacktestWeight[]
  metrics: AllocationBacktestMetrics
  equity_curve: AllocationBacktestPoint[]
  rebalance_events: AllocationBacktestRebalanceEvent[]
  trades: AllocationBacktestTrade[]
}

export type AllocationBacktestComparison = {
  total_return_diff_pct: number | null
  annualized_return_diff_pct: number | null
  annualized_volatility_diff_pct: number | null
  downside_volatility_diff_pct: number | null
  max_drawdown_diff_pct: number | null
  sharpe_diff: number | null
  sortino_diff: number | null
  excess_return_diff_pct: number | null
  tracking_error_diff_pct: number | null
  information_ratio_diff: number | null
  beta_diff: number | null
  correlation_diff: number | null
  total_turnover_diff_pct: number | null
  total_cost_diff: number | null
}

export type PortfolioDiagnosticsSnapshot = {
  provenance: {
    snapshot_basis: 'synthetic_replay_snapshot'
    historical_basis: 'market_data_history'
    note: string
  }
  factor_snapshot: StatisticalFactorSnapshotItem[]
  volatility_snapshot: VolatilitySnapshot | null
  risk_contribution: RiskContributionBreakdown | null
  stress_scenarios: StressScenarioResult[]
}

export type PortfolioDiagnosticsComparisonRow = {
  key: string
  label: string
  baseline_value: number | null
  candidate_value: number | null
  delta_value: number | null
}

export type PortfolioImprovementComparison = {
  factor_exposure_changes: PortfolioDiagnosticsComparisonRow[]
  volatility_changes: PortfolioDiagnosticsComparisonRow[]
  risk_contribution_changes: PortfolioDiagnosticsComparisonRow[]
  concentration_changes: PortfolioDiagnosticsComparisonRow[]
  stress_scenario_changes: PortfolioDiagnosticsComparisonRow[]
}

export type PortfolioAllocationBacktestResponse = {
  methodology: string
  reference_result: AllocationBacktestResult | null
  candidate_result: AllocationBacktestResult
  comparison: AllocationBacktestComparison | null
  reference_diagnostics: PortfolioDiagnosticsSnapshot | null
  candidate_diagnostics: PortfolioDiagnosticsSnapshot | null
  diagnostics_comparison: PortfolioImprovementComparison | null
}
