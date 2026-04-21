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
    commissions_total?: number | null
    deposits_total: number | null
    starting_nav: number | null
    ending_nav: number | null
    time_weighted_return_pct?: number | null
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
  cash_balances: Array<{
    currency: string
    starting_cash?: number | null
    ending_cash: number | null
    ending_settled_cash?: number | null
  }>
}

export type PortfolioOverview = {
  account_id?: string | null
  base_currency?: string | null
  statement_period?: string | null
  total_market_value: number
  total_cost_basis?: number
  total_unrealized_pnl: number
  positions_count: number
  instruments_count?: number
  ledger_entries_count: number
  top_positions: Array<{ symbol: string; market_value: number; weight: number; unrealized_pnl: number }>
  sector_allocation: Array<{ sector: string; market_value: number; weight: number }>
  sector_position_breakdown: Record<string, Array<{ symbol: string; market_value: number; weight: number }>>
  cash_by_currency: Record<string, number>
  ledger_counts?: Record<string, number>
  realized_cash_flow?: Record<string, number>
}

export type BenchmarkSummary = {
  symbol: string
  start_price: number | null
  end_price: number | null
  return_pct: number | null
  return_basis_contract?: 'verified_total_return' | 'price_return_only' | 'unverified_adjusted_proxy' | 'unavailable'
  points?: Array<{
    date: string
    price: number
  }>
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

export type InvestorEconomicsStatus = {
  status: 'available' | 'withheld'
  reason: 'withheld_unverified_total_return_equivalence' | null
}

export type ReturnBasisEvidence = {
  verification_status: 'verified' | 'proxy' | 'unverified' | 'unavailable'
  economic_basis: 'total_return' | 'adjusted_close_proxy' | 'price_return_only' | 'unavailable'
  construction_method: 'vendor_adjusted_close' | 'raw_close' | 'synthetic_snapshot_history' | 'sample_dataset' | 'unknown'
  disqualifiers: string[]
  fallbacks_used: string[]
  source_price_field: string | null
  scope?: Record<string, string | number | boolean | null>
}

export type PortfolioProofBucketEvidence = {
  status: 'supported' | 'disqualified' | 'unavailable'
  positive_evidence: string[]
  negative_evidence: string[]
  disqualifiers: string[]
  hard_disqualifiers: string[]
  witnesses: Array<{
    label: string
    status: string
    evidence: string[]
    counts: Record<string, number>
  }>
}

export type PortfolioCorporateActionBasisEvidence = PortfolioProofBucketEvidence & {
  policy: {
    scope: 'broker_native_statement_window' | 'broker_scope_unproven'
    cash_dividend_coverage_status:
      | 'cash_dividend_coverage_proven_by_broker_native_evidence'
      | 'cash_dividend_coverage_unproven'
    cash_dividend_observation_status:
      | 'cash_dividend_observed_by_broker_native_evidence'
      | 'no_cash_dividend_observed_within_covered_broker_scope'
      | 'cash_dividend_observation_unproven'
    non_dividend_status: 'non_dividend_corporate_actions_unproven_and_disqualifying'
    scope_start_date: string | null
    scope_end_date: string | null
    statement_window_count: number
  }
}

export type PortfolioProofAdmissionDecision = {
  status: 'withheld' | 'rejected' | 'not_applicable'
  scope: Record<string, string | number | boolean | null>
  blocking_reasons: Array<{
    code: string
    bucket: string
    provenance_bucket: string
    reason_type: 'blocking' | 'missing' | 'scope_mismatch' | 'withheld'
  }>
  missing_proof_buckets: string[]
  bucket_decisions: Array<{
    bucket: string
    status: 'withheld' | 'rejected' | 'not_applicable'
    blocks_admission: boolean
    provenance_buckets: string[]
    blocking_reasons: string[]
    scope: Record<string, string | number | boolean | null>
  }>
}

export type PortfolioProofMetadata = {
  proof_system: string
  portfolio_path: 'withheld' | 'unverified' | 'unavailable'
  verification_status: 'unverified' | 'unavailable'
  output_status: 'withheld' | 'unavailable'
  replay_status: 'replay_usable' | 'replay_unavailable'
  opening_state_status: 'opening_state_verified' | 'opening_state_unverified' | 'opening_state_unavailable'
  verified_total_return_emitted: boolean
  benchmark_proof_independent: boolean
  disqualifiers: string[]
  hard_disqualifiers: string[]
  admission: PortfolioProofAdmissionDecision
  evidence: {
    opening_state_basis: PortfolioProofBucketEvidence
    valuation_basis: PortfolioProofBucketEvidence
    cash_flow_basis: PortfolioProofBucketEvidence
    fx_basis: PortfolioProofBucketEvidence
    corporate_action_basis: PortfolioCorporateActionBasisEvidence
    terminal_reconciliation_basis: PortfolioProofBucketEvidence
    calendar_coverage_basis: PortfolioProofBucketEvidence
  }
}

export type DashboardHistoryRunMetadata = {
  history_id: string
  methodology_id: string
  source_status: {
    performance_history: string
    monthly_returns: string
    benchmark_history: 'live_market_data_verified_adjusted_close' | 'live_market_data_unverified_return_basis' | 'unavailable'
  }
  section_trust: {
    portfolio_path: 'imported_replay' | 'unavailable'
    benchmark_path: 'verified_adjusted_close' | 'degraded_unverified_return_basis' | 'unavailable'
    monthly_returns_path: 'imported_replay' | 'suppressed_unstable_path' | 'unavailable'
  }
  return_basis_contract: {
    portfolio_path: 'verified_total_return' | 'price_return_only' | 'unverified_adjusted_proxy' | 'unavailable'
    benchmark_path: 'verified_total_return' | 'price_return_only' | 'unverified_adjusted_proxy' | 'unavailable'
  }
  return_basis_evidence: {
    portfolio_path: ReturnBasisEvidence
    benchmark_path: ReturnBasisEvidence
  }
  portfolio_proof: PortfolioProofMetadata
  investor_economics_status: InvestorEconomicsStatus
  reproducibility: {
    input_imported_at: string | null
    snapshot_as_of_date: string | null
    history_start_date: string | null
    history_end_date: string | null
    benchmark_symbol: string
    dataset_version: string
  }
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
    consumer_staples?: number | null
    utilities?: number | null
    consumer_discretionary?: number | null
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
    consumer_staples?: number | null
    utilities?: number | null
    consumer_discretionary?: number | null
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
    consumer_staples?: number | null
    utilities?: number | null
    consumer_discretionary?: number | null
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
  estimated_return_pct: number | null
  description: string
  status?: 'ok' | 'unavailable'
}

export type HistoryTruthClass =
  | 'imported_history_equivalent'
  | 'synthetic_history_derived'
  | 'unavailable'

export type DiagnosticsProvenance = {
  snapshot_basis: 'imported_snapshot' | 'snapshot_request'
  historical_basis: 'imported_portfolio_history' | 'market_data_history' | 'unavailable'
  history_truth_class: HistoryTruthClass
  price_basis: 'close' | 'unavailable'
  note: string
}

export type DiagnosticsRunMetadata = {
  source_status: {
    portfolio_history: 'imported_replay' | 'synthetic_snapshot_history' | 'unavailable'
    benchmark_history: 'live_market_data_verified_adjusted_close' | 'live_market_data_unverified_return_basis' | 'unavailable'
    factor_history: 'live_market_data_verified_adjusted_close' | 'live_market_data_unverified_return_basis' | 'unavailable'
  }
  section_trust: {
    benchmark_relative_path: 'verified_adjusted_close' | 'degraded_unverified_return_basis' | 'unavailable'
    factor_model_path: 'verified_adjusted_close' | 'degraded_unverified_return_basis' | 'unavailable'
    risk_contribution_path: 'verified_adjusted_close' | 'degraded_unverified_return_basis' | 'unavailable'
  }
  return_basis_evidence: {
    portfolio_history: ReturnBasisEvidence
    benchmark_history: ReturnBasisEvidence
    factor_history: ReturnBasisEvidence
  }
  portfolio_proof: PortfolioProofMetadata
  investor_economics_status: InvestorEconomicsStatus
  factor_model_parameters: {
    rolling_windows_days: number[]
    current_reliability_window_days: number
    minimum_window_observations: Record<string, number>
    collinearity_warning_threshold: number
    orthogonalization_basis: string
    ridge_lambda: number
  }
  reproducibility: {
    input_imported_at: string | null
    snapshot_as_of_date: string | null
    history_start_date: string | null
    history_end_date: string | null
    dataset_version: string
  }
  diagnostics_id: string
  methodology_id: string
  price_basis: 'close' | 'unavailable'
  confidence: 'high' | 'medium' | 'low'
}

export type DiagnosticsAvailability = {
  historical_sections_available: boolean
  history_context_required: boolean
  note: string | null
  status: 'ok' | 'unavailable'
}

export type DiagnosticsDrawdownSummary = {
  current_drawdown_pct: number | null
  max_drawdown_pct: number | null
}

export type DiagnosticsVolatilitySummary = {
  portfolio_volatility_pct: number | null
  benchmark_volatility_pct: number | null
  downside_volatility_pct: number | null
  tracking_error_pct: number | null
}

export type DiagnosticsRiskConcentrationSummary = {
  top_1_factor_risk_share: number | null
  top_3_factor_risk_share: number | null
  top_1_position_risk_share: number | null
  top_5_position_risk_share: number | null
  factor_hhi: number | null
  position_hhi: number | null
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
  run_metadata: DiagnosticsRunMetadata
  drawdown_summary: DiagnosticsDrawdownSummary
  volatility_summary: DiagnosticsVolatilitySummary
  risk_concentration_summary: DiagnosticsRiskConcentrationSummary
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
  risk_summary?: PortfolioRiskSummary
  benchmark?: BenchmarkSummary | null
  performance_series: PerformanceSeriesPoint[]
  daily_states: DailyPortfolioState[]
  source_status?: SourceStatus | null
  run_metadata?: DashboardHistoryRunMetadata | null
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

export type ExposureConcentrationItem = {
  name: string
  market_value: number
  weight: number
}

export type ExposureCurrentStateConcentration = {
  top_positions: ExposureConcentrationItem[]
  top_sectors: ExposureConcentrationItem[]
  top_1_position_weight: number | null
  top_3_position_weight: number | null
  top_5_position_weight: number | null
  top_sector_weight: number | null
  top_3_sector_weight: number | null
  position_hhi: number | null
  sector_hhi: number | null
  effective_holdings: number | null
}

export type ExposureProvenance = {
  snapshot_basis: 'snapshot_request'
  historical_basis: 'current_state_only'
  price_basis: 'not_applicable'
  note: string
}

export type ExposureRunMetadata = {
  engine_id: string
  methodology_id: string
  price_basis: 'not_applicable'
  source_status: {
    lookthrough_resolution: ExposureAvailabilityStatus
    benchmark_holdings: 'live' | 'unavailable'
  }
  confidence: ExposureAvailabilityConfidence
  reproducibility: {
    input_imported_at: string | null
    snapshot_as_of_date: string | null
    benchmark_symbol: string
    dataset_version: string
  }
}

export type ImportedExposureSource = {
  snapshot: ImportedSnapshot
  provenance?: ExposureProvenance | null
  run_metadata?: ExposureRunMetadata | null
  diagnostics_run_metadata?: DiagnosticsRunMetadata | null
  overview: PortfolioOverview
  lookthrough: LookThroughOverview
  lookthrough_sector_exposure: LookThroughSectorExposure[]
  market_overlap: MarketOverlapSummary
  current_state_concentration: ExposureCurrentStateConcentration
  exposure_availability?: ExposureAvailability | null
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
  availability?: DiagnosticsAvailability | null
}

export type ImportedDiagnosticsSource = {
  snapshot: ImportedSnapshot
  provenance: DiagnosticsProvenance
  availability: DiagnosticsAvailability
  run_metadata: DiagnosticsRunMetadata
  drawdown_summary: DiagnosticsDrawdownSummary
  volatility_summary: DiagnosticsVolatilitySummary
  risk_concentration_summary: DiagnosticsRiskConcentrationSummary
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
  provenance: ExposureProvenance
  run_metadata: ExposureRunMetadata
  diagnostics_run_metadata?: DiagnosticsRunMetadata | null
  overview: PortfolioOverview
  lookthrough: LookThroughOverview
  lookthrough_sector_exposure: LookThroughSectorExposure[]
  market_overlap: MarketOverlapSummary
  current_state_concentration: ExposureCurrentStateConcentration
  availability: ExposureAvailability
}

export type DashboardHistoryEngineResponse = {
  daily_states: DailyPortfolioState[]
  performance_series: PerformanceSeriesPoint[]
  source_status?: SourceStatus | null
  run_metadata: DashboardHistoryRunMetadata
  benchmark: BenchmarkSummary | null
  range_metrics?: Record<string, DashboardRangeMetrics> | null
}

export type DashboardAnalysis = ImportedDashboardSource

export type PortfolioBaselineView = ImportedBaselineSource

export type ExposureAnalysis = ImportedExposureSource

export type DiagnosticsEngineResponse = ImportedDiagnosticsSource

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
  investor_economics_status: InvestorEconomicsStatus
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
    equity: number | null
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
      equity: number | null
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
  investor_economics_status: InvestorEconomicsStatus
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
    strategy_equity: number | null
    benchmark_equity: number | null
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

export type EtfRankingResponse = {
  ranking_id: string
  title: string
  as_of_date: string
  benchmark_symbol: string
  universe: string[]
  lookback_months: number
  price_basis: 'close'
  methodology: string
  effective_peer_group: string | null
  effective_component_weights: {
    momentum: number
    benchmark_relative_strength: number
    realized_volatility: number
    downside_volatility: number
    max_drawdown: number
    liquidity: number
    implementation_fit: number
  }
  source_status: {
    price_history: 'sample' | 'live' | 'mixed'
    benchmark_history: 'sample' | 'live'
    holdings_support: 'sample' | 'mixed' | 'unavailable'
  }
  warnings: {
    confidence: 'high' | 'medium' | 'low'
    warnings: string[]
    unknown_metadata_symbols: string[]
    peer_group_unclassified_symbols: string[]
  }
  request: {
    peer_group: string | null
    universe: string[]
    benchmark_symbol: string
    lookback_months: number
  }
  effective_inputs: {
    effective_peer_group: string | null
    effective_component_weights: {
      momentum: number
      benchmark_relative_strength: number
      realized_volatility: number
      downside_volatility: number
      max_drawdown: number
      liquidity: number
      implementation_fit: number
    }
    requested_universe: string[]
    evaluated_universe: string[]
    excluded_symbols: Array<{
      symbol: string
      reason: string
    }>
  }
  run_metadata: {
    ranking_id: string
    methodology_id: string
    methodology: string
    as_of_date: string
    ranking_basis_date: string
    price_basis: 'close'
    source_status: {
      price_history: 'sample' | 'live' | 'mixed'
      benchmark_history: 'sample' | 'live'
      holdings_support: 'sample' | 'mixed' | 'unavailable'
    }
    confidence: 'high' | 'medium' | 'low'
  }
  ranked_universe: Array<{
    rank: number
    symbol: string
    composite_score: number
    instrument: {
      symbol: string
      name: string | null
      asset_class: string | null
      sector: string | null
      category: string | null
      currency: string | null
    }
    component_scores: Record<string, {
      label: string
      direction: 'higher_is_better' | 'lower_is_better'
      raw_value: number
      raw_unit: 'pct' | 'volume' | 'score'
      normalized_score: number
      weight: number
      weighted_score: number
    }>
  }>
  excluded_symbols: Array<{
    symbol: string
    reason: string
  }>
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
  investor_economics_status: InvestorEconomicsStatus
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
  benchmark_return_diff_pct: number | null
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

export type PortfolioDiagnosticsProvenance = {
  snapshot_basis: 'synthetic_replay_snapshot'
  historical_basis: 'market_data_history'
  note: string
}

export type PortfolioDiagnosticsSnapshot = {
  provenance: PortfolioDiagnosticsProvenance
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

export type PortfolioDiagnosticsTopCallout = {
  key: string
  label: string
  baseline_value: number | null
  candidate_value: number | null
  delta_value: number | null
  selection_rule: string
  rationale: string
}

export type PortfolioImprovementComparison = {
  factor_exposure_changes: PortfolioDiagnosticsComparisonRow[]
  top_factor_exposure_change: PortfolioDiagnosticsTopCallout | null
  volatility_changes: PortfolioDiagnosticsComparisonRow[]
  top_volatility_change: PortfolioDiagnosticsTopCallout | null
  risk_contribution_changes: PortfolioDiagnosticsComparisonRow[]
  top_risk_contribution_change: PortfolioDiagnosticsTopCallout | null
  concentration_changes: PortfolioDiagnosticsComparisonRow[]
  top_concentration_change: PortfolioDiagnosticsTopCallout | null
  stress_scenario_changes: PortfolioDiagnosticsComparisonRow[]
  top_stress_scenario_change: PortfolioDiagnosticsTopCallout | null
}

export type PortfolioAllocationBacktestResponse = {
  methodology: string
  investor_economics_status: InvestorEconomicsStatus
  reference_result: AllocationBacktestResult | null
  candidate_result: AllocationBacktestResult
  comparison: AllocationBacktestComparison | null
  reference_diagnostics: PortfolioDiagnosticsSnapshot | null
  candidate_diagnostics: PortfolioDiagnosticsSnapshot | null
  diagnostics_comparison: PortfolioImprovementComparison | null
}

export type HypotheticalReplayDerivation = {
  baseline_basis: 'draft_snapshot_positions_normalized'
  candidate_construction_rule: 'same_weight_substitution_v1' | 'fixed_split_50_50_substitution_v2'
}

export type HypotheticalReplayProvenance = {
  candidate_input_source: 'replacement_intent_preview' | 'constructed_candidate_payload'
  construction_rule_id: 'same_weight_substitution_v1' | 'fixed_split_50_50_substitution_v2'
  upstream_ids: {
    draft_id: string
    workspace_id: string
    base_node_id: string
  }
  seed_ranking_id: string
  seed_methodology_id: string
  constraint_validation: {
    supplied: boolean
    validation_status: 'ok' | 'blocked' | 'rejected' | null
    constraint_set_id: 'single_replacement_construction_constraints_v1' | null
  }
}

export type HypotheticalReplacementReplayResponse = {
  proposal: {
    source: 'draft_replacement_intent'
    incumbent_symbol: string
    candidate_symbol: string
    draft_id: string
    base_node_id: string
  }
  derivation: HypotheticalReplayDerivation
  replay_provenance: HypotheticalReplayProvenance
  baseline_weights: AllocationBacktestWeight[]
  candidate_weights: AllocationBacktestWeight[]
  replay: PortfolioAllocationBacktestResponse
  warnings: string[]
}

export type OverlayStateInput = {
  overlay_id: 'benchmark_trend_overlay_v1'
  status: 'risk_on' | 'risk_reduced' | 'unconfirmed' | 'unavailable'
  as_of_month_end: string
  benchmark_symbol: string
  signal_basis: '10_month_sma_month_end'
  confirmation_count: number
  rule_version: string
}

export type OverlayApplicationSummary = {
  overlay_id: 'benchmark_trend_overlay_v1'
  overlay_status: 'risk_on' | 'risk_reduced'
  as_of_month_end: string
  benchmark_symbol: string
  risky_weight_scale: number
  cash_residual_weight: number
  applied_to_candidate_only: boolean
}

export type OverlayAwareHypotheticalReplayResponse = {
  proposal: HypotheticalReplacementReplayResponse['proposal']
  derivation: HypotheticalReplayDerivation
  replay_provenance: HypotheticalReplayProvenance
  overlay_application: OverlayApplicationSummary
  baseline_weights: AllocationBacktestWeight[]
  candidate_weights_pre_overlay: AllocationBacktestWeight[]
  candidate_weights_post_overlay: AllocationBacktestWeight[]
  base_replay: PortfolioAllocationBacktestResponse
  overlay_replay: PortfolioAllocationBacktestResponse
  warnings: string[]
}

export type HypotheticalReplayResponse = HypotheticalReplacementReplayResponse | OverlayAwareHypotheticalReplayResponse

export type MonitoringResearchHandoffTarget = 'hypothetical_replay' | 'diagnostics_change'

export type MonitoringResearchHandoff = {
  version: 1
  source: 'monitoring'
  monitorKey: string
  monitorTitle: string
  researchTarget: MonitoringResearchHandoffTarget
  contextLabel: string
  replayContext: string | null
}

export type CandidateFormationState = {
  kind: 'single_replacement_candidate_formation'
  status: 'ok' | 'rejected'
}

export type CandidateFormationProposal = {
  source: 'draft_replacement_intent'
  draft_id: string | null
  workspace_id: string | null
  base_node_id: string | null
  incumbent_symbol: string | null
  candidate_symbol: string | null
}

export type CandidateFormationDerivation = {
  baseline_basis: 'draft_snapshot_positions_normalized'
  candidate_construction_rule: 'single_symbol_weight_substitution'
  cash_treatment: 'excluded_from_candidate_formation_basis'
  position_scope: 'positive_market_value_positions_only'
}

export type CandidateFormationSummary = {
  incumbent_start_weight: number | null
  candidate_start_weight: number | null
  unchanged_positions_count: number
  baseline_positions_count: number
  candidate_positions_count: number
  starting_turnover_pct: number | null
}

export type CandidateFormationTruthProvenance = {
  baseline_truth_class: 'draft_snapshot_basis'
  candidate_truth_class: 'hypothetical_candidate_input_only'
  formation_truth_class: 'candidate_formation_derived'
  note: string
}

export type SingleReplacementCandidateFormationResponse = {
  formation: CandidateFormationState
  proposal: CandidateFormationProposal
  derivation: CandidateFormationDerivation
  baseline_weights: AllocationBacktestWeight[]
  candidate_weights: AllocationBacktestWeight[]
  formation_summary: CandidateFormationSummary
  truth_provenance: CandidateFormationTruthProvenance
  warnings: string[]
  rejection_reason: string | null
}

export type SingleReplacementConstructionRuleId = 'same_weight_substitution_v1' | 'fixed_split_50_50_substitution_v2'

export type CandidateConstructionRuleInput = {
  rule_id: SingleReplacementConstructionRuleId
}

export type CandidateConstructionState = {
  kind: 'single_replacement_construction'
  status: 'ok' | 'rejected'
  rule_id: SingleReplacementConstructionRuleId | null
}

export type CandidateConstructionInputs = {
  baseline_weights: AllocationBacktestWeight[]
  construction_rule: SingleReplacementConstructionRuleId | null
  incumbent_start_weight: number | null
  candidate_added_weight?: number | null
  incumbent_remaining_weight?: number | null
}

export type CandidateConstructionOutputs = {
  candidate_weights: AllocationBacktestWeight[]
  starting_turnover_pct: number | null
  unchanged_positions_count: number
  candidate_added_weight?: number | null
  incumbent_remaining_weight?: number | null
}

export type CandidateConstructionDerivation = {
  baseline_basis: 'draft_snapshot_positions_normalized'
  construction_basis: 'explicit_single_replacement_rule'
  cash_treatment: 'excluded_from_construction_basis'
  position_scope: 'positive_market_value_positions_only'
}

export type CandidateConstructionTruthProvenance = {
  baseline_truth_class: 'draft_snapshot_basis'
  construction_truth_class: 'candidate_construction_derived'
  candidate_truth_class: 'hypothetical_candidate_input_only'
  note: string
}

export type SingleReplacementCandidateConstructionResponse = {
  construction: CandidateConstructionState
  proposal: CandidateFormationProposal
  inputs: CandidateConstructionInputs
  outputs: CandidateConstructionOutputs
  derivation: CandidateConstructionDerivation
  truth_provenance: CandidateConstructionTruthProvenance
  warnings: string[]
  rejection_reason: string | null
}

export type SingleReplacementConstructionConstraintSetId = 'single_replacement_construction_constraints_v1'

export type SingleReplacementConstructionConstraintSetInput = {
  constraint_set_id: SingleReplacementConstructionConstraintSetId
}

export type SingleReplacementConstraintValidationState = {
  kind: 'single_replacement_construction_constraint_validation'
  status: 'ok' | 'blocked' | 'rejected'
  constraint_set_id: SingleReplacementConstructionConstraintSetId
}

export type SingleReplacementConstraintEvaluation = {
  constraint_id: string
  severity: 'hard_block' | 'warning'
  status: 'pass' | 'fail' | 'not_applicable'
  message: string
  rationale: string | null
  actual_value: number | string | null
  expected_value: number | string | null
  operator: '<=' | '>=' | '==' | '!=' | 'in' | null
}

export type SingleReplacementConstraintValidationDerivation = {
  validation_timing: 'post_construction_pre_replay'
  validation_basis: 'explicit_constraint_set'
  candidate_input_source: 'constructed_candidate_payload'
  constraint_set_id: SingleReplacementConstructionConstraintSetId
}

export type SingleReplacementConstraintValidationTruthProvenance = {
  baseline_truth_class: 'draft_snapshot_basis'
  construction_truth_class: 'candidate_construction_derived'
  candidate_truth_class: 'hypothetical_candidate_input_only'
  constraint_validation_truth_class: 'constraint_validation_derived'
  note: string
}

export type SingleReplacementConstructionConstraintValidationResponse = {
  validation: SingleReplacementConstraintValidationState
  proposal: CandidateFormationProposal
  construction: CandidateConstructionState
  derivation: SingleReplacementConstraintValidationDerivation
  truth_provenance: SingleReplacementConstraintValidationTruthProvenance
  evaluations: SingleReplacementConstraintEvaluation[]
  blocking_constraint_ids: string[]
  warnings: string[]
  rejection_reason: string | null
}
