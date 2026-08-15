from typing import Literal

from pydantic import BaseModel



class ReconciliationCheck(BaseModel):
    name: str
    expected: float | int | None
    actual: float | int | None
    difference: float | None
    passed: bool
    detail: str


class ReconciliationSummary(BaseModel):
    passed: bool
    checks: list[ReconciliationCheck]


class PortfolioOverview(BaseModel):
    account_id: str | None
    base_currency: str | None
    statement_period: str | None
    positions_count: int
    instruments_count: int
    ledger_entries_count: int
    total_market_value: float
    total_cost_basis: float
    total_unrealized_pnl: float
    cash_by_currency: dict[str, float]
    top_positions: list[dict[str, float | str]]
    sector_allocation: list[dict[str, float | str]]
    sector_position_breakdown: dict[str, list[dict[str, float | str]]]
    ledger_counts: dict[str, int]
    realized_cash_flow: dict[str, float]


class PortfolioActivityPoint(BaseModel):
    month: str
    buys: float
    sells: float
    dividends: float
    withholding_tax: float
    interest: float
    fees: float
    deposits: float
    withdrawals: float
    net_cash_flow: float


class HoldingsTimelinePoint(BaseModel):
    date: str
    symbol: str
    quantity: float


class BenchmarkPoint(BaseModel):
    date: str
    price: float


class BenchmarkComparison(BaseModel):
    symbol: str
    start_price: float | None
    end_price: float | None
    return_pct: float | None
    return_basis_contract: Literal["verified_total_return", "price_return_only", "unverified_adjusted_proxy", "unavailable"] = "unavailable"
    points: list[BenchmarkPoint]


class EnrichedPosition(BaseModel):
    symbol: str
    quantity: float
    statement_price: float
    statement_market_value: float
    latest_price: float | None
    latest_market_value: float | None
    daily_change: float | None
    daily_change_pct: float | None
    unrealized_pnl: float
    currency: str


class PortfolioRiskSummary(BaseModel):
    benchmark_symbol: str
    methodology: str
    start_date: str | None
    end_date: str | None
    observations: int
    portfolio_beta: float | None
    portfolio_correlation: float | None
    r_squared: float | None
    portfolio_volatility_pct: float | None
    benchmark_volatility_pct: float | None


class LookThroughSource(BaseModel):
    source_symbol: str
    source_market_value: float
    source_weight: float
    resolved_via: str


class LookThroughConstituent(BaseModel):
    symbol: str
    name: str
    effective_market_value: float
    portfolio_weight: float
    sources: list[LookThroughSource]


class LookThroughOverview(BaseModel):
    portfolio_market_value: float
    covered_market_value: float
    coverage_ratio: float
    etf_resolution: dict[str, str]
    uncovered_positions: list[str]
    top_constituents: list[LookThroughConstituent]


class RollingRiskPoint(BaseModel):
    date: str
    beta_20d: float | None = None
    correlation_20d: float | None = None
    beta_60d: float | None = None
    correlation_60d: float | None = None
    beta_252d: float | None = None
    correlation_252d: float | None = None


class BenchmarkRelativePositioningCue(BaseModel):
    symbol: str
    name: str
    portfolio_weight: float
    benchmark_weight: float
    active_weight: float


class MarketOverlapSummary(BaseModel):
    benchmark_symbol: str
    overlap_weight: float | None
    active_share: float | None
    portfolio_in_benchmark_weight: float | None
    benchmark_covered_weight: float | None
    top_overweights: list[BenchmarkRelativePositioningCue] = []
    top_underweights: list[BenchmarkRelativePositioningCue] = []


class EtfOverlapConstituent(BaseModel):
    symbol: str
    name: str
    left_weight: float
    right_weight: float
    overlap_weight: float


class EtfOverlapPair(BaseModel):
    left_symbol: str
    right_symbol: str
    left_resolved: str
    right_resolved: str
    overlap_weight: float
    shared_constituent_count: int
    top_shared_constituents: list[EtfOverlapConstituent]
    sector_overlap: list["LookThroughSectorExposure"]


class LookThroughSectorExposure(BaseModel):
    sector: str
    market_value: float
    weight: float


class RelativeRiskSummary(BaseModel):
    benchmark_symbol: str
    tracking_error_pct: float | None
    active_return_pct: float | None
    information_ratio: float | None


class RollingVolatilityPoint(BaseModel):
    date: str
    portfolio_return: float | None = None
    benchmark_return: float | None = None
    active_return: float | None = None
    realized_vol_20d: float | None = None
    realized_vol_60d: float | None = None
    realized_vol_252d: float | None = None
    downside_vol_20d: float | None = None
    downside_vol_60d: float | None = None
    downside_vol_252d: float | None = None
    benchmark_vol_20d: float | None = None
    benchmark_vol_60d: float | None = None
    benchmark_vol_252d: float | None = None
    tracking_error_20d: float | None = None
    tracking_error_60d: float | None = None
    tracking_error_252d: float | None = None
    drawdown_pct: float | None = None
    wealth_index: float | None = None


class VolatilitySnapshot(BaseModel):
    realized_vol_20d: float | None = None
    realized_vol_60d: float | None = None
    realized_vol_252d: float | None = None
    downside_vol_20d: float | None = None
    downside_vol_60d: float | None = None
    downside_vol_252d: float | None = None
    benchmark_vol_20d: float | None = None
    benchmark_vol_60d: float | None = None
    benchmark_vol_252d: float | None = None
    tracking_error_20d: float | None = None
    tracking_error_60d: float | None = None
    tracking_error_252d: float | None = None
    current_drawdown_pct: float | None = None
    max_drawdown_pct: float | None = None
    vol_ratio_20_60: float | None = None
    vol_ratio_20_252: float | None = None
    current_20d_vol_percentile: float | None = None


class VolatilityAssumptions(BaseModel):
    return_basis: str
    cash_flow_timing: str
    drawdown_basis: str
    benchmark_basis: str
    downside_mar: float
    annualization_days: int


class RegimeAssessment(BaseModel):
    label: str
    confidence: str


class VolatilityRegimePayload(BaseModel):
    methodology: str
    assumptions: VolatilityAssumptions
    rolling_series: list[RollingVolatilityPoint]
    snapshot: VolatilitySnapshot
    regime: RegimeAssessment


class FactorShiftSnapshot(BaseModel):
    key: str
    label: str
    us_proxy: str
    category: str
    current_loading_20d: float | None = None
    current_loading_60d: float | None = None
    current_loading_252d: float | None = None
    change_20d: float | None = None
    change_60d: float | None = None
    abs_change_20d: float | None = None
    abs_change_60d: float | None = None
    stability_gap_20d_60d: float | None = None
    stability_gap_60d_252d: float | None = None
    available_windows_count: int
    shift_flag_20d: bool
    shift_flag_60d: bool
    stability_flag: bool
    collinearity_flag: bool
    volatility_flag: bool
    confidence: str


class RankedFactorShiftItem(BaseModel):
    key: str
    label: str
    us_proxy: str
    current_loading: float | None = None
    change_value: float | None = None
    absolute_change: float | None = None


class FactorShiftDiagnosticsPayload(BaseModel):
    methodology: str
    snapshots: list[FactorShiftSnapshot]
    largest_positive_shifts_20d: list[RankedFactorShiftItem]
    largest_negative_shifts_20d: list[RankedFactorShiftItem]
    largest_absolute_shifts_20d: list[RankedFactorShiftItem]
    largest_absolute_shifts_60d: list[RankedFactorShiftItem]


class FactorRiskContributionItem(BaseModel):
    key: str
    label: str
    us_proxy: str
    loading: float | None = None
    factor_volatility: float | None = None
    variance_contribution: float | None = None
    risk_share: float | None = None


class PositionRiskContributionItem(BaseModel):
    symbol: str
    weight: float
    volatility: float | None = None
    marginal_contribution: float | None = None
    component_contribution: float | None = None
    risk_share: float | None = None


class RiskConcentrationSnapshot(BaseModel):
    top_1_factor_risk_share: float | None = None
    top_3_factor_risk_share: float | None = None
    top_1_position_risk_share: float | None = None
    top_5_position_risk_share: float | None = None
    factor_hhi: float | None = None
    position_hhi: float | None = None


class ModelReliabilitySnapshot(BaseModel):
    window_days: int
    observation_count: int
    r_squared: float | None = None
    residual_volatility: float | None = None
    collinearity_pair_count: int
    max_abs_factor_correlation: float | None = None
    factor_count_used: int
    missing_factor_count: int
    status: str
    confidence: str
    stability_score: float | None = None


class RiskContributionBreakdownPayload(BaseModel):
    methodology: str
    window_days: int
    observation_count: int
    status: str
    factor_contributions: list[FactorRiskContributionItem]
    factor_total_variance: float | None = None
    specific_variance: float | None = None
    total_variance: float | None = None
    factor_risk_share_total: float | None = None
    specific_risk_share: float | None = None
    residual_volatility: float | None = None
    position_contributions: list[PositionRiskContributionItem]
    concentration: RiskConcentrationSnapshot


class FactorExposurePoint(BaseModel):
    factor: str
    exposure: float | None
    description: str
    basis: str = "current_state"


class StatisticalFactorLoading(BaseModel):
    key: str
    factor: str
    category: str
    proxy_symbol: str
    ucits_examples: list[str] = []
    mapping_quality: str
    orthogonalization_order: int
    loading: float


class FactorRiskContribution(BaseModel):
    key: str
    factor: str
    category: str
    proxy_symbol: str
    ucits_examples: list[str] = []
    mapping_quality: str
    orthogonalization_order: int
    loading: float
    variance_share: float


class MappingMatchComponents(BaseModel):
    exposure_match: float | None = None
    historical_similarity: float | None = None
    structure_fit: float | None = None
    implementation_fit: float | None = None


class MappingMatchSummary(BaseModel):
    score_pct: float | None = None
    label: str | None = None
    score_basis: str
    score_status: str
    hard_cap_reason: str | None = None
    components: MappingMatchComponents


class UcitsMapping(BaseModel):
    provider: str
    fund_name: str
    isin: str | None = None
    example_tickers: list[str] = []
    asset_exposure: str
    domicile: str | None = None
    trading_currency: str | None = None
    base_currency: str | None = None
    currency_hedged: bool | None = None
    distribution_policy: str = "unknown"
    mapping_quality: str
    notes: str | None = None
    match_summary: MappingMatchSummary | None = None


class FactorProxyDefinition(BaseModel):
    key: str
    label: str
    category: str
    us_proxy: str
    target_exposure: str | None = None
    primary_mapping: UcitsMapping | None = None
    alternative_mappings: list[UcitsMapping] = []
    ucits_examples: list[str] = []
    mapping_quality: str
    default_enabled: bool
    orthogonalization_order: int
    description: str


class FactorCollinearityWarning(BaseModel):
    left_key: str
    right_key: str
    left_proxy: str
    right_proxy: str
    correlation: float


class FactorCollinearityDiagnostics(BaseModel):
    window_days: int
    threshold: float
    high_collinearity_pairs: list[FactorCollinearityWarning]
    note: str | None = None


class WindowSummary(BaseModel):
    window_days: int
    observations: int
    start_date: str | None
    end_date: str | None
    status: str


class SnapshotItem(BaseModel):
    key: str
    label: str
    category: str
    us_proxy: str
    latest_loading: float | None = None
    target_exposure: str | None = None
    primary_mapping: UcitsMapping | None = None
    alternative_mappings: list[UcitsMapping] = []
    ucits_examples: list[str] = []
    mapping_quality: str
    description: str


class InsufficientHistoryPoint(BaseModel):
    window_days: int
    required_observations: int
    available_observations: int
    missing_factors: list[str] = []


class RollingFactorLoadingPoint(BaseModel):
    date: str
    market: float | None = None
    growth: float | None = None
    value: float | None = None
    small_cap: float | None = None
    technology: float | None = None
    financials: float | None = None
    health_care: float | None = None
    energy: float | None = None
    industrials: float | None = None
    consumer_staples: float | None = None
    utilities: float | None = None
    consumer_discretionary: float | None = None
    rates_ief: float | None = None
    rates_tlt: float | None = None
    credit: float | None = None
    commodities: float | None = None
    alpha: float | None = None
    r_squared: float | None = None
    residual_vol: float | None = None


class StatisticalFactorModel(BaseModel):
    status: str
    benchmark_symbol: str
    windows: list[WindowSummary]
    rolling_loadings_20d: list[RollingFactorLoadingPoint]
    rolling_loadings_60d: list[RollingFactorLoadingPoint]
    rolling_loadings_252d: list[RollingFactorLoadingPoint]
    current_factor_snapshot: list[SnapshotItem]
    collinearity_diagnostics: list[FactorCollinearityDiagnostics]
    insufficient_history: list[InsufficientHistoryPoint] = []
class StressScenarioResult(BaseModel):
    name: str
    estimated_return_pct: float | None = None
    description: str
    # "partial": estimate computed over the AVAILABLE loadings only —
    # `missing_factors` lists the shocked factors whose loading was
    # unavailable and whose contribution is therefore absent (US-27.4;
    # never silently zero-filled).
    status: Literal["ok", "partial", "unavailable"] = "ok"
    missing_factors: list[str] = []


class PerformancePoint(BaseModel):
    date: str
    portfolio_value: float
    benchmark_price: float | None
    portfolio_return_pct: float | None
    benchmark_return_pct: float | None


class PerformanceSummary(BaseModel):
    start_value: float | None
    end_value: float | None
    net_contributions: float
    investment_gain: float | None
    time_weighted_return_pct: float | None
    money_weighted_return_pct: float | None
    benchmark_return_pct: float | None
    excess_return_pct: float | None


class DailyStatePosition(BaseModel):
    symbol: str
    quantity: float
    market_price: float | None
    market_value: float | None


class SyntheticHistoryCoverage(BaseModel):
    """Coverage disclosure for the synthetic snapshot-history convention
    (US-27.7). Prices are never back-filled before a symbol's first quote;
    instead the effective window starts at the latest first-quote across
    material holdings, and holdings that cannot be honestly covered are
    excluded — both surfaced here, never silently."""

    requested_start_date: str | None = None
    effective_start_date: str | None = None
    # Set only when the effective window is SHORTER than requested — the
    # material holding whose first available quote set the effective start.
    limiting_symbol: str | None = None
    # Holdings excluded from the synthetic universe: no in-window price
    # history at all, or below the de-minimis weight with a first quote
    # after the effective start (would otherwise force a mid-window entry).
    excluded_symbols: list[str] = []


class DailyPortfolioState(BaseModel):
    date: str
    cash: dict[str, float]
    positions: list[DailyStatePosition]
    total_market_value: float
    total_portfolio_value: float
    external_cash_flow: float = 0.0
    # US-24.9: net base-currency market value moved INTO the holdings by
    # BUY/SELL entries settled on this day — positive for a net buy, negative
    # for a net sell (it is the negation of those entries' `cash_effect`, each
    # FX-converted before summing; the raw currency-mixed sum is meaningless —
    # the US-31.3 measurement trap). Distinct from `external_cash_flow`, which
    # is DEPOSIT/WITHDRAWAL only: a trade is an internal transfer between the
    # cash and holdings sleeves, not investor money entering or leaving.
    # Subtracting it neutralises the trade leg in a market-value return chain
    # (`ReturnBasis="market_value_trade_neutral"`), which is what lets the
    # imported ledger-replay path exclude cash without reading a BUY as a gain.
    # 0.0 on a day with no trades; never null.
    trade_flow: float = 0.0
    # US-31.3 (Epic 31 F-3): signed amount by which the terminal reconciliation
    # moved this state's `total_portfolio_value` to match the statement's ending
    # NAV. It is an ACCOUNTING CORRECTION, not a market move — a day carrying a
    # material adjustment has its return WITHHELD rather than published
    # (guardrail #3). None on every state that was not reconciled.
    reconciliation_adjustment: float | None = None
    # US-33.2 (Epic 33 F-1/F-2): base-currency cash moved on this day by trades
    # in a symbol whose reconstructed QUANTITY was withheld. That cash is real
    # broker truth, but the position it bought or sold is not in market value at
    # all — so `total_portfolio_value` steps with no offsetting position, and a
    # cash-inclusive return chain would publish the step as performance. Exactly
    # the US-24.9 fabrication class, re-opened by withholding, so the day's
    # return is WITHHELD rather than computed. 0.0 on a day with no such trades.
    unbacked_cash_flow: float = 0.0

    @property
    def return_is_publishable(self) -> bool:
        """US-33.2 + US-34.8: may a return be published for this day?

        False only when the state carries a material **unbacked cash flow** —
        cash moved by a withheld-quantity symbol, whose position is in no market
        value, so the portfolio value steps with nothing behind it. That state
        cannot be interpreted as a market move at all, and no corrected value
        exists for it.

        A reconciled terminal day is publishable (US-34.8): its return is
        computed from the market-derived value, so the accounting adjustment
        never enters it. US-31.3's requirement is met by correction rather than
        by blanking the day.

        Defined here, on the state itself, so the three consumers
        (`performance.py`, `risk.py`, `attribution.py`) cannot drift apart — the
        US-31.2 "one shared chain" lesson.
        """
        from app.core.constants import REPLAY_UNBACKED_CASH_MATERIAL_SHARE

        # US-34.8 (Epic 34 F-8): a reconciled terminal day is PUBLISHABLE again.
        #
        # US-31.3 required that an accounting adjustment never be published as a
        # return, and satisfied that by withholding the day — because the day's
        # value had been overwritten and no un-overwritten one existed. US-34.6
        # created that value (`market_derived_terminal_value`), so the return is
        # now computed with the adjustment REMOVED. F-3's requirement holds by
        # construction, and a real day of market movement stops being discarded.
        #
        # The unbacked-cash cause below is untouched: there the missing thing is
        # a POSITION, not an adjustment, and no corrected value exists for it.
        # US-34.4 (Epic 34 F-4): the unbacked-cash guard is MATERIALITY, so it is
        # a share of that day's portfolio value — not the $1.00 rounding
        # tolerance US-33.2 borrowed, which discarded real return days for flows
        # worth 0.008% of the book.
        if not self.unbacked_cash_flow:
            return True
        if not self.total_portfolio_value:
            return False
        share = abs(self.unbacked_cash_flow) / abs(self.total_portfolio_value)
        return share <= REPLAY_UNBACKED_CASH_MATERIAL_SHARE
