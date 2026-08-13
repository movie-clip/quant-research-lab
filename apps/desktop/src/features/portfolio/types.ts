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
  top_overweights: Array<{
    symbol: string
    name: string
    portfolio_weight: number
    benchmark_weight: number
    active_weight: number
  }>
  top_underweights: Array<{
    symbol: string
    name: string
    portfolio_weight: number
    benchmark_weight: number
    active_weight: number
  }>
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

export type DashboardHistoryInvestorEconomicsScalarPolicy = {
  field:
    | 'range_metrics[*].summary.time_weighted_return_pct'
    | 'range_metrics[*].summary.benchmark_return_pct'
    | 'range_metrics[*].summary.excess_return_pct'
  unlock_condition:
    | 'identical_admitted_exact_slice_only'
    | 'identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only'
    | 'identical_admitted_exact_slice_pair_only'
  runtime_enabled: boolean
}

export type DashboardHistoryInvestorEconomicsPartialUnlock = {
  mode: 'allowlisted_exact_slice_scalars_only'
  exact_slice_scalar_allowlist: DashboardHistoryInvestorEconomicsScalarPolicy[]
  client_derivation_rule: 'server_side_scalar_only_no_daily_series_subtraction_equivalence'
  withheld_families: Array<
    | 'benchmark_relative_series'
    | 'benchmark_relative_path_derived_outputs'
    | 'drawdown_family'
    | 'rebucketed_window_summaries'
    | 'rewindowed_range_summaries'
    | 'diagnostics_benchmark_relative_outputs'
    | 'replay_benchmark_relative_outputs'
    | 'strategy_lab_benchmark_relative_outputs'
  >
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
    non_dividend_status:
      | 'no_non_dividend_corporate_actions_observed_within_covered_broker_scope'
      | 'non_dividend_corporate_actions_unproven_and_disqualifying'
    scope_start_date: string | null
    scope_end_date: string | null
    statement_window_count: number
  }
}

export type PortfolioInvestorEconomicsProofEvidence = PortfolioProofBucketEvidence & {
  claim_id: string
  claim: string
  decision: 'admitted' | 'withheld' | 'rejected' | 'not_applicable'
  preparation_status:
    | 'exact_slice_admitted'
    | 'exact_slice_prerequisites_incomplete'
    | 'exact_slice_ready_but_withheld_by_policy'
    | 'not_applicable'
  required_inputs: string[]
  blocking_reasons: string[]
  missing_proof_buckets: string[]
  scope_mismatches: string[]
  scope: Record<string, string | number | boolean | null>
}

export type PortfolioProofAdmissionDecision = {
  status: 'admitted' | 'withheld' | 'rejected' | 'not_applicable'
  readiness_status:
    | 'exact_slice_admitted'
    | 'exact_slice_prerequisites_incomplete'
    | 'exact_slice_ready_but_withheld_by_policy'
    | 'not_applicable'
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
    status: 'admitted' | 'withheld' | 'rejected' | 'not_applicable'
    blocks_admission: boolean
    provenance_buckets: string[]
    blocking_reasons: string[]
    scope: Record<string, string | number | boolean | null>
  }>
}

export type PortfolioProofPreparationGap = {
  code: string
  bucket: string
  provenance_buckets: string[]
  gap_type: 'blocking' | 'missing' | 'scope_unproven' | 'scope_mismatch' | 'policy_withheld'
}

export type PortfolioProofPreparationMetadata = {
  readiness_status:
    | 'exact_slice_admitted'
    | 'exact_slice_prerequisites_incomplete'
    | 'exact_slice_ready_but_withheld_by_policy'
    | 'not_applicable'
  all_prerequisite_buckets_supported: boolean
  exact_slice_target: {
    account_set: string[]
    base_currency: string | null
    valuation_window: {
      start_date: string | null
      end_date: string | null
      count: number
    }
    statement_window: {
      start_date: string | null
      end_date: string | null
      count: number
    }
    opening_state_anchor: {
      required_anchor_date: string | null
      observed_anchor_date: string | null
      status: string
    }
    fx_scope: {
      translation_case: string
      base_currency: string | null
      observed_currencies: string[]
      required_pairs: string[]
      required_pair_dates: string[]
    }
    corporate_action_scope: {
      scope: 'broker_native_statement_window' | 'broker_scope_unproven'
      scope_start_date: string | null
      scope_end_date: string | null
      statement_window_count: number
      positive_proof_classes: string[]
      unproven_disqualifying_classes: string[]
    }
  }
  readiness_gaps: PortfolioProofPreparationGap[]
  policy_blockers: PortfolioProofPreparationGap[]
}

export type PortfolioProofMetadata = {
  proof_system: string
  portfolio_path: 'verified' | 'withheld' | 'unverified' | 'unavailable'
  verification_status: 'verified' | 'unverified' | 'unavailable'
  output_status: 'available' | 'withheld' | 'unavailable'
  replay_status: 'replay_usable' | 'replay_unavailable'
  opening_state_status: 'opening_state_verified' | 'opening_state_unverified' | 'opening_state_unavailable'
  verified_total_return_emitted: boolean
  benchmark_proof_independent: boolean
  disqualifiers: string[]
  hard_disqualifiers: string[]
  preparation: PortfolioProofPreparationMetadata
  admission: PortfolioProofAdmissionDecision
  evidence: {
    opening_state_basis: PortfolioProofBucketEvidence
    valuation_basis: PortfolioProofBucketEvidence
    cash_flow_basis: PortfolioProofBucketEvidence
    fx_basis: PortfolioProofBucketEvidence
    corporate_action_basis: PortfolioCorporateActionBasisEvidence
    terminal_reconciliation_basis: PortfolioProofBucketEvidence
    calendar_coverage_basis: PortfolioProofBucketEvidence
    investor_economics_proof: PortfolioInvestorEconomicsProofEvidence
  }
}

export type DashboardHistoryRunMetadata = {
  history_id: string
  methodology_id: string
  /** US-27.8 (audit F9): currencies that needed base conversion but had no FX
   *  rate during the replay — values carried unconverted (disclosed, never a
   *  silent 1:1 conversion claim). */
  fx_fallback_currencies?: string[]
  /** US-31.2 (Epic 31 F-1): reconstructed positions held during the window with
   *  no fetchable price history and no statement close-price anchor — they
   *  contributed 0 to the replayed market value. Disclosed, never silently
   *  zeroed. */
  unpriced_replay_symbols?: string[]
  /** US-24.10: symbols valued at the broker's own execution price, carried
   *  forward from the trade — the third valuation tier, below market history and
   *  the statement close. Broker truth, but the carried segment is flat: it
   *  contains no market movement. Exactly one tier applies per symbol. */
  trade_price_anchored_symbols?: string[]
  /** US-33.2 (Epic 33 F-1/F-2): symbols whose reconstructed QUANTITY was
   *  withheld because their own ledger prices imply a share-unit change (a
   *  split). Distinct from `unpriced_replay_symbols`, where the quantity is
   *  trusted and only the price is missing: here the quantity itself is not
   *  publishable, so the symbol contributes no position and appears in no
   *  valuation tier. */
  quantity_withheld_symbols?: ReplayQuantityWithholding[]
  /** US-31.3 (Epic 31 F-2): how the replay's opening cash was derived, and
   *  whether that derivation is trustworthy. */
  replay_cash_anchor?: ReplayCashAnchor | null
  /** US-31.3 (Epic 31 F-3): dates whose replayed return was withheld because the
   *  state carried a material reconciliation adjustment. */
  withheld_return_dates?: string[]
  withheld_return_reason?: string | null
  /** US-34.2 (Epic 34 F-1): percentage points the withheld days remove from the
   *  published return — an impact ESTIMATE for disclosure, never a return.
   *  Publishing a figure that omits days without saying what the omission is
   *  worth misleads more than publishing nothing. `null` when nothing was
   *  withheld (never 0.0, which would claim a measured zero). */
  withheld_return_impact_pct?: number | null
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
    /** US-34.2: `replay_derived` is portfolio-path only — the return was chained
     *  from the imported replay's own daily states (reconstructed opening
     *  positions, mixed valuation basis, terminal reconciliation), which the
     *  strict proof admission will not certify as a verified total return. */
    portfolio_path:
      | 'verified_total_return'
      | 'replay_derived'
      | 'price_return_only'
      | 'unverified_adjusted_proxy'
      | 'unavailable'
    benchmark_path: 'verified_total_return' | 'price_return_only' | 'unverified_adjusted_proxy' | 'unavailable'
  }
  return_basis_evidence: {
    portfolio_path: ReturnBasisEvidence
    benchmark_path: ReturnBasisEvidence
  }
  portfolio_proof: PortfolioProofMetadata
  investor_economics_status: InvestorEconomicsStatus
  investor_economics_partial_unlock: DashboardHistoryInvestorEconomicsPartialUnlock
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
  /** US-34.2 (Epic 34 F-1): trust of this range's time_weighted_return_pct and
   *  max_drawdown_pct. `verified` only when the proof admission granted an exact
   *  slice; `degraded` for a `replay_derived` basis — a real measurement on the
   *  replay's reconstructed inputs; `unavailable` when nothing was published.
   *  Render the marker: a degraded return must never read as a verified one. */
  portfolio_return_trust?: 'verified' | 'degraded' | 'unavailable'
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
  /** US-24.9: net base-currency market value moved INTO the holdings by this
   *  day's BUY/SELL entries (positive = net buy), FX-converted per entry.
   *  Distinct from external_cash_flow (DEPOSIT/WITHDRAWAL only) — a trade is an
   *  internal transfer, not investor money entering or leaving. Subtracting it
   *  neutralises the trade leg in the imported path's cash-excluded return
   *  chain. 0.0 on a day with no trades. */
  trade_flow?: number
  /** US-31.3 (Epic 31 F-3): signed amount the terminal reconciliation moved this
   *  state's total_portfolio_value by — an accounting correction, not a market
   *  move. A day carrying a material adjustment has its return withheld. */
  reconciliation_adjustment?: number | null
  /** US-33.2 (Epic 33 F-1/F-2): base-currency cash moved this day by trades in a
   *  symbol whose reconstructed quantity was withheld. The cash is real, but the
   *  position behind it is in no market value, so the portfolio value steps with
   *  nothing behind it and the day's return is withheld. 0.0 normally. */
  unbacked_cash_flow?: number
  cash: Record<string, number>
  positions: Array<{ symbol: string; quantity: number; market_price: number | null; market_value: number | null }>
}

/** US-31.3 (Epic 31 F-2): provenance + trust of the replay's opening cash.
 *  `starting_nav − opening_positions_value` is only sound when both terms share
 *  an as-of date; when they differ, market movement between them is absorbed
 *  into cash as a plug and the anchor is `degraded`, never `verified`. */
export type ReplayCashAnchor = {
  /** US-34.3 (Epic 34 F-2): `statement_starting_cash` is the strongest basis —
   *  the broker's own reported opening cash, exactly dated at the period start.
   *  Trust follows the SOURCE (observed = verified); the residual separately
   *  reports how well the ledger reconciles the statement's two cash endpoints. */
  basis:
    | 'statement_starting_cash'
    | 'statement_nav_at_window_start'
    | 'statement_nav_date_mismatch'
    | 'snapshot_cash_balances'
    | 'unavailable'
  nav_as_of?: string | null
  window_start?: string | null
  residual?: number | null
  trust: 'verified' | 'degraded' | 'unavailable'
}

/** US-33.2 (Epic 33 F-1/F-2): a reconstructed quantity the replay refused to
 *  publish. The roll-back `opening = ending + Σ SELL − Σ BUY` presumes one share
 *  unit across the window; a split breaks it and yields a position size the
 *  broker never held. Evidence is the symbol's own execution prices spanning a
 *  ratio no market move explains, measured within a single currency. */
export type ReplayQuantityWithholding = {
  symbol: string
  reason: 'share_unit_discontinuity'
  currency: string
  price_low: number
  price_high: number
  price_ratio: number
  withheld_opening_quantity: number
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
  /** 'partial': estimate computed over the available loadings only —
   *  `missing_factors` names the shocked factors excluded from the sum
   *  (US-27.4; never silently zero-filled). */
  status?: 'ok' | 'partial' | 'unavailable'
  missing_factors?: string[]
}

/** Engine-level trust for the standalone /engines/stress/run response.
 *  `'synthetic'` = factor model fit, scenarios have non-null pcts.
 *  `'unavailable'` = factor model could not be fit (empty/short history);
 *                    per-scenario rows still present with null pcts. */
export type StressTrustLevel = 'synthetic' | 'unavailable'

/** Response wrapper from POST /engines/stress/run (Epic 13 — Risk tab). */
/** US-27.7: synthetic/broker history coverage disclosure. Prices are never
 *  back-filled before a symbol's first quote; the effective window and any
 *  excluded holdings are surfaced here — never silently. Mirrors the Pydantic
 *  SyntheticHistoryCoverage. */
export type SyntheticHistoryCoverage = {
  requested_start_date: string | null
  effective_start_date: string | null
  limiting_symbol: string | null
  excluded_symbols: string[]
}

export type StressEngineResponse = {
  scenarios: StressScenarioResult[]
  trust: StressTrustLevel
  coverage?: SyntheticHistoryCoverage | null
}

// ── Drawdown analytics (US-13.2) ─────────────────────────────────────────────

/** Engine-level trust for the /engines/drawdown/run response.
 *  Mirrors the Pydantic DrawdownTrustLevel literal. */
export type DrawdownTrustLevel = 'synthetic' | 'unavailable'

/** Supported lookback windows for the drawdown engine. `null` = max
 *  available history (engine-capped at ~8 years). */
export type DrawdownWindow = 252 | 756 | 1260

/** One point on the underwater curve. drawdown_pct is signed percentage
 *  from peak (0 at all-time high, -12.5 = 12.5 % below). */
export type DrawdownDailyPoint = {
  date: string
  drawdown_pct: number | null
}

/** Per-episode decomposition trust (Epic 15 / US-15.1). 'partial' when
 *  the episode could be decomposed but some positions had missing prices
 *  at peak/trough. */
export type DrawdownDecompositionTrust = 'synthetic' | 'partial' | 'unavailable'

/** One position's contribution to a drawdown episode (Epic 15 / US-15.1).
 *  contribution_pct is signed — negative = drag, positive = position rallied
 *  while portfolio overall sank. trust='unavailable' when any of the three
 *  pcts is null (missing price at peak or trough). */
export type EpisodeContributor = {
  symbol: string
  weight_at_peak_pct: number | null
  return_pct: number | null
  contribution_pct: number | null
  trust: 'synthetic' | 'unavailable'
}

/** One drawdown episode (peak → trough → optional recovery).
 *  `recovery_date === null` means still underwater at series end.
 *  Decomposition fields (Epic 15) are nullable defaults — episodes
 *  constructed without decomposition (older fixtures) stay valid. */
export type DrawdownEpisode = {
  peak_date: string
  trough_date: string
  recovery_date: string | null
  magnitude_pct: number   // always ≤ 0; "deepest" = most negative
  duration_days: number   // trough - peak (calendar days)
  underwater_days: number // (recovery or last) - peak (calendar days)
  // Per-position decomposition (Epic 15 / US-15.1):
  top_contributors?: EpisodeContributor[] | null
  other_contribution_pct?: number | null
  decomposition_residual_pct?: number | null
  decomposition_trust?: DrawdownDecompositionTrust
}

/** Response wrapper from POST /engines/drawdown/run (Epic 13 — Risk tab). */
export type DrawdownEngineResponse = {
  window_trading_days: number | null
  underwater_series: DrawdownDailyPoint[]
  current_drawdown_pct: number | null
  max_drawdown_pct: number | null
  episodes: DrawdownEpisode[]
  trust: DrawdownTrustLevel
  coverage?: SyntheticHistoryCoverage | null
}

// ── VaR & Distribution analytics (US-13.3) ───────────────────────────────────

/** Engine-level trust for the /engines/distribution/run response. */
export type DistributionTrustLevel = 'synthetic' | 'unavailable'

/** Supported lookback windows for the distribution engine (trading days). */
export type DistributionWindow = 60 | 252 | 504

/** One bin in the daily return histogram. `center` is decimal return,
 *  NOT percent — UI multiplies by 100 for display. */
export type HistogramBin = {
  center: number
  count: number
}

/** Response wrapper from POST /engines/distribution/run (Epic 13 — Risk tab).
 *  All percent fields are in percent units (multiplied by 100).
 *  `var_*` / `cvar_*` are sign-flipped: positive = loss. A negative VaR
 *  means "tail day at requested confidence was still positive" — UI styles
 *  this muted to distinguish from a real loss (methodology contract rule). */
export type DistributionEngineResponse = {
  window_trading_days: number
  return_count: number
  var_95: number | null
  var_99: number | null
  cvar_95: number | null
  percentile_5: number | null
  percentile_10: number | null
  percentile_50: number | null
  percentile_90: number | null
  percentile_95: number | null
  mean_pct: number | null
  std_pct: number | null
  skewness: number | null
  kurtosis_excess: number | null
  histogram_bins: HistogramBin[]
  trust: DistributionTrustLevel
  coverage?: SyntheticHistoryCoverage | null
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

export type ImportAdmissionSummaryV1 = {
  schema_version: 'import_admission_summary_v1'
  decision: 'admitted' | 'degraded' | 'withheld'
  trust_level: 'verified' | 'degraded' | 'withheld' | 'unavailable'
  checks: Array<{
    check_id: string
    status: 'pass' | 'warn' | 'fail' | 'unavailable'
    severity: 'info' | 'warning' | 'error'
    trust_impact: 'none' | 'degraded' | 'withheld' | 'unavailable'
    message: string
    affected_fields?: string[]
    observed?: { label: string; value: number | string | null } | null
    comparison?: { label: string; value: number | string | null } | null
    delta?: number | null
    currency?: string | null
  }>
  provenance: {
    importer: string | null
    statement_ids: string[]
    source_names: string[]
    generated_at: string
    tolerance_policy: string
  }
}

export type ImportedBootstrapResponse = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  risk_summary: PortfolioRiskSummary
  admission_summary: ImportAdmissionSummaryV1
  history_context?: ImportedHistoryContext | null
}

export type ImportedPortfolioSnapshotSource = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  risk_summary: PortfolioRiskSummary
  admission_summary?: ImportAdmissionSummaryV1 | null
  benchmark: BenchmarkSummary | null
}

export type ImportedDashboardSource = {
  snapshot: ImportedSnapshot
  overview: PortfolioOverview
  risk_summary?: PortfolioRiskSummary
  admission_summary?: ImportAdmissionSummaryV1 | null
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
    benchmark_holdings: 'verified' | 'degraded' | 'unavailable'
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
  /** US-30.5a (audit F-8): the currency basis behind every weight on the tab. */
  fx_static_rate_currencies?: string[]
  fx_fallback_currencies?: string[]
  /** US-26.1: per-currency composition on the same base-currency denominator
   *  every other Exposure weight uses. */
  currency_exposure?: CurrencyExposureSummary | null
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
  /** US-30.5a (audit F-8): currencies converted at the statement's implied
   *  period-end rate (static across the window). */
  fx_static_rate_currencies?: string[]
  /** US-30.5a (audit F-8): non-base currencies with no rate — values carried
   *  unconverted (never dropped, never a 1:1 claim). */
  fx_fallback_currencies?: string[]
  /** US-26.1: per-currency composition on the same base-currency denominator
   *  every other Exposure weight uses. */
  currency_exposure?: CurrencyExposureSummary | null
}

export type CurrencyExposureWeight = {
  currency: string
  market_value: number
  weight: number
}

export type CurrencyLegContribution = {
  currency: string
  base_weight: number
  /** Contribution to the currency variance share; null when the currency has
   *  no covered holding. */
  contribution?: number | null
}

/** US-26.2: the local / currency / interaction variance split.
 *  Shares sum to exactly 1.0 when present, and MAY BE NEGATIVE — a currency leg
 *  moving against the local leg genuinely reduces portfolio variance. Never
 *  clamp; render the sign. */
export type CurrencyRiskResult = {
  trust: 'synthetic' | 'unavailable'
  window_days: number
  observations: number
  local_variance_share?: number | null
  currency_variance_share?: number | null
  interaction_variance_share?: number | null
  local_standalone_vol_pct?: number | null
  currency_standalone_vol_pct?: number | null
  local_fx_correlation?: number | null
  per_currency: CurrencyLegContribution[]
  /** Holdings with no fund-currency price history — excluded and named, never
   *  assigned to the local leg at zero FX. */
  excluded_symbols: string[]
  excluded_weight: number
  note?: string | null
}

export type CurrencyExposureSummary = {
  base_currency?: string | null
  total_base_market_value: number
  weights: CurrencyExposureWeight[]
  /** Null when the statement carries no base currency — there is no baseline,
   *  and 0 would read as "no currency risk". Render "—", never 0. */
  non_base_weight?: number | null
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


// --- Market-data cache admin (Epic 20 / US-20.1) ---
export type CacheNamespaceStat = {
  namespace: string
  entries: number
}

export type CacheStats = {
  enabled: boolean
  cache_dir: string
  total_entries: number
  namespaces: CacheNamespaceStat[]
}

export type CacheClearResult = {
  removed: number
  namespace: string | null
}

// --- Data provenance (Epic 18 / US-18.2) ---
export type ProvenanceVendor = 'fmp' | 'yfinance' | 'unavailable'

export type HoldingProvenance = {
  symbol: string
  vendor: ProvenanceVendor
}

export type InstrumentIdentityMismatch = {
  symbol: string
  statement_description: string
  registry_name: string
  /** Evidence class: 'description' = token-disjoint heuristic (US-19.1);
   *  'isin' = definitive ISO 6166 identifier mismatch (US-19.2). */
  kind: 'description' | 'isin'
  statement_isin: string | null
  expected_isin: string | null
}

export type ProvenanceResult = {
  holdings: HoldingProvenance[]
  fmp_symbols: string[]
  yahoo_sourced_symbols: string[]
  unavailable_symbols: string[]
  /** Holdings whose statement description disagrees with the registry fund name
   *  (possible ticker→fund mislabel). Flag only. (US-19.1) */
  identity_warnings: InstrumentIdentityMismatch[]
  lookback_days: number
}

// --- Drift vs Benchmark ---
export type DriftTrust = 'synthetic' | 'unavailable'

export type DriftWindow = {
  label: string
  start_date: string | null
  end_date: string | null
  portfolio_return_pct: number | null
  benchmark_return_pct: number | null
  spread_pct: number | null
  trust: DriftTrust
  note: string | null
}

export type DriftDailyPoint = {
  date: string
  portfolio_indexed: number | null
  benchmark_indexed: number | null
}

export type DriftResult = {
  windows: DriftWindow[]
  benchmark_symbol: string
  daily_series: DriftDailyPoint[]
  availability: 'available' | 'partial' | 'unavailable'
  /** US-27.8 (audit F9): currencies that needed base conversion but had no FX
   *  rate — values are carried unconverted; non-empty must be surfaced. */
  fx_fallback_currencies?: string[]
  /** US-30.2 (audit F-6): currencies converted at the statement's implied
   *  period-end rate (static across the window — levels are broker truth as
   *  of period end; FX return dynamics still absent). */
  fx_static_rate_currencies?: string[]
  /** US-30.2 (audit F-3): held symbols valued FLAT at the statement close for
   *  the whole window (zero in-window price coverage) — zero return
   *  contribution; non-empty must be surfaced. */
  statement_anchored_symbols?: string[]
}

// --- Factor Return Attribution ---

export type FactorContributionPoint = {
  factor_key: string
  cumul_contribution: number | null
}

export type AttributionSeriesEntry = {
  date: string
  contributions: FactorContributionPoint[]
  cumul_unexplained: number | null
  cumul_portfolio_return: number | null
}

export type FactorPeriodRow = {
  factor_key: string
  factor_label: string
  avg_beta: number | null
  factor_return_pct: number | null
  contribution_pct: number | null
}

export type FactorAttributionResponse = {
  attribution_status: 'available' | 'unavailable'
  window: number
  cumulative_series: AttributionSeriesEntry[]
  period_attribution: FactorPeriodRow[]
  total_portfolio_return_pct: number | null
  total_unexplained_pct: number | null
  methodology_note: string
  coverage?: SyntheticHistoryCoverage | null
}

// ── Multi-Benchmark Correlation ───────────────────────────────────────────────

export type BenchmarkStats = {
  symbol: string
  label: string
  correlation: number | null
  beta: number | null
  r_squared: number | null
  trust: 'synthetic' | 'unavailable'
}

export type MultiBenchmarkCorrelationResult = {
  benchmarks: BenchmarkStats[]
  lookback_days: number
  coverage?: SyntheticHistoryCoverage | null
}

// --- Intra-Portfolio Correlation (Epic 17 / US-17.1) ---
export type IntraCorrelationPair = {
  symbol_a: string
  symbol_b: string
  correlation: number
}

export type IntraCorrelationResult = {
  /** Priceable holdings in matrix order (by weight desc, capped at max_holdings). */
  symbols: string[]
  /** Square symmetric N×N matrix aligned to `symbols`. Diagonal = 1.0; a cell is
   *  null when the pair is below the overlap minimum or has zero variance. */
  matrix: Array<Array<number | null>>
  average_pairwise_correlation: number | null
  most_correlated_pair: IntraCorrelationPair | null
  least_correlated_pair: IntraCorrelationPair | null
  /** Diversification Ratio Σwᵢσᵢ/σ_p (Choueifaty & Coignard 2008); null when σ_p
   *  is 0 or history is insufficient. (US-17.2) */
  diversification_ratio: number | null
  /** Effective Number of Bets exp(−Σpₖln pₖ) over the correlation eigenvalues
   *  (Meucci 2009); null when <2 holdings, an incomplete matrix, or non-PSD. (US-17.2) */
  effective_number_of_bets: number | null
  /** Holdings dropped for no / insufficient price history. */
  excluded_symbols: string[]
  /** Holdings whose history came from the secondary provider (Yahoo Finance)
   *  rather than the primary (FMP). Surfaced as a visible provenance marker. (US-18.1) */
  yahoo_sourced_symbols: string[]
  lookback_days: number
  trust: 'synthetic' | 'unavailable'
}
