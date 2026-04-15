from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.reconciliation import RiskContributionBreakdownPayload, SnapshotItem, StressScenarioResult, VolatilitySnapshot
from app.schemas.research import AllocationRebalanceFrequency, BacktestFrequency, ContinuousSeriesSpec, DistributionPolicy, StrategyDefinition


class BacktestConfig(BaseModel):
    strategy: StrategyDefinition
    benchmark_symbol: str | None = None
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    base_currency: str = "USD"
    slippage_bps: float = 0.0
    commission_per_contract: float = 0.0
    rebalance_frequency: Literal["daily", "weekly", "monthly", "signal"] = "signal"
    use_continuous_contracts: bool = True
    continuous_series: ContinuousSeriesSpec | None = None


class BacktestRequest(BaseModel):
    strategy_id: str = "book_trend_breakout"
    universe: list[str] = Field(default_factory=lambda: ["ES", "NQ"])
    benchmark_symbol: str | None = None
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    base_currency: str = "USD"
    timeframe: BacktestFrequency = "1d"
    slippage_bps: float = 0.0
    commission_per_contract: float = 2.5
    use_continuous_contracts: bool = True


class BacktestTrade(BaseModel):
    date: str
    symbol: str
    action: Literal["buy", "sell", "short", "cover", "roll"]
    quantity: float
    price: float | None = None
    notional: float | None = None
    fee: float | None = None


class BacktestPosition(BaseModel):
    date: str
    symbol: str
    quantity: float
    market_price: float | None = None
    market_value: float | None = None
    notional_exposure: float | None = None


class BacktestEquityPoint(BaseModel):
    date: str
    equity: float
    cash: float
    gross_exposure: float | None = None
    net_exposure: float | None = None
    drawdown_pct: float | None = None


class BacktestRun(BaseModel):
    run_id: str
    config: BacktestConfig
    dataset_info: dict[str, dict[str, str | bool]] = Field(default_factory=dict)
    trades: list[BacktestTrade] = Field(default_factory=list)
    positions: list[BacktestPosition] = Field(default_factory=list)
    equity_curve: list[BacktestEquityPoint] = Field(default_factory=list)
    total_return_pct: float | None = None
    annualized_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_ratio: float | None = None


class StrategyAllocation(BaseModel):
    sleeve_id: str
    name: str
    capital_weight: float
    source: Literal["imported_portfolio", "strategy_run"]
    strategy_run_id: str | None = None


class OverlayRun(BaseModel):
    overlay_id: str
    base_portfolio_name: str
    allocations: list[StrategyAllocation] = Field(default_factory=list)
    equity_curve: list[BacktestEquityPoint] = Field(default_factory=list)
    notes: str | None = None


AllocationBacktestStatus = Literal["ok", "degraded", "rejected"]


class PortfolioWeightInput(BaseModel):
    symbol: str
    target_weight: float


class PortfolioAllocationBacktestRequest(BaseModel):
    portfolio_name: str | None = None
    weights: list[PortfolioWeightInput] = Field(default_factory=list)
    reference_weights: list[PortfolioWeightInput] | None = None
    benchmark_symbol: str = "SPY"
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    rebalance_frequency: AllocationRebalanceFrequency = "monthly"
    base_currency: str = "USD"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    drift_tolerance_pct: float | None = None
    price_basis: Literal["adjusted_close"] = "adjusted_close"
    execution_price_field: Literal["close"] = "close"
    execution_lag_days: int = 1
    symbol_overrides: dict[str, list[str]] = Field(default_factory=dict)


class AllocationBacktestAssumptions(BaseModel):
    price_basis: str
    execution_price_field: str
    execution_lag_days: int
    calendar_policy: str
    fractional_shares: bool
    long_only: bool
    leverage_allowed: bool
    tax_treatment: str
    investor_base_currency: str | None = None


class AllocationBacktestInstrumentMeta(BaseModel):
    symbol: str
    trading_currency: str | None = None
    instrument_base_currency: str | None = None
    currency_hedged: bool | None = None
    distribution_policy: DistributionPolicy = "unknown"


class AllocationBacktestWeight(BaseModel):
    symbol: str
    target_weight: float


class AllocationBacktestTrade(BaseModel):
    date: str
    symbol: str
    action: Literal["buy", "sell"]
    quantity: float
    price: float | None = None
    traded_notional: float | None = None
    commission_cost: float | None = None
    slippage_cost: float | None = None
    total_cost: float | None = None


class AllocationBacktestRebalanceEvent(BaseModel):
    decision_date: str
    execution_date: str
    turnover_pct: float | None = None
    traded_notional: float | None = None
    total_cost: float | None = None


class AllocationBacktestPoint(BaseModel):
    date: str
    equity: float
    cash: float
    gross_exposure: float | None = None
    drawdown_pct: float | None = None


class AllocationBacktestMetrics(BaseModel):
    total_return_pct: float | None = None
    annualized_return_pct: float | None = None
    annualized_volatility_pct: float | None = None
    downside_volatility_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    benchmark_return_pct: float | None = None
    excess_return_pct: float | None = None
    tracking_error_pct: float | None = None
    information_ratio: float | None = None
    beta_vs_benchmark: float | None = None
    correlation_vs_benchmark: float | None = None
    total_turnover_pct: float | None = None
    turnover_events_count: int = 0
    total_cost_paid: float | None = None


class AllocationBacktestResult(BaseModel):
    portfolio_name: str | None = None
    benchmark_symbol: str | None = None
    start_date: str
    end_date: str
    observation_count: int
    rebalance_frequency: AllocationRebalanceFrequency
    commission_bps: float
    slippage_bps: float
    drift_tolerance_pct: float | None = None
    assumptions: AllocationBacktestAssumptions
    status: AllocationBacktestStatus
    instrument_metadata: list[AllocationBacktestInstrumentMeta] = Field(default_factory=list)
    starting_weights: list[AllocationBacktestWeight] = Field(default_factory=list)
    ending_weights: list[AllocationBacktestWeight] = Field(default_factory=list)
    metrics: AllocationBacktestMetrics
    equity_curve: list[AllocationBacktestPoint] = Field(default_factory=list)
    rebalance_events: list[AllocationBacktestRebalanceEvent] = Field(default_factory=list)
    trades: list[AllocationBacktestTrade] = Field(default_factory=list)


class AllocationBacktestComparison(BaseModel):
    total_return_diff_pct: float | None = None
    annualized_return_diff_pct: float | None = None
    annualized_volatility_diff_pct: float | None = None
    downside_volatility_diff_pct: float | None = None
    max_drawdown_diff_pct: float | None = None
    sharpe_diff: float | None = None
    sortino_diff: float | None = None
    excess_return_diff_pct: float | None = None
    tracking_error_diff_pct: float | None = None
    information_ratio_diff: float | None = None
    beta_diff: float | None = None
    correlation_diff: float | None = None
    total_turnover_diff_pct: float | None = None
    total_cost_diff: float | None = None


class PortfolioDiagnosticsProvenance(BaseModel):
    snapshot_basis: Literal["synthetic_replay_snapshot"]
    historical_basis: Literal["market_data_history"]
    note: str


class PortfolioDiagnosticsSnapshot(BaseModel):
    provenance: PortfolioDiagnosticsProvenance
    factor_snapshot: list[SnapshotItem] = Field(default_factory=list)
    volatility_snapshot: VolatilitySnapshot | None = None
    risk_contribution: RiskContributionBreakdownPayload | None = None
    stress_scenarios: list[StressScenarioResult] = Field(default_factory=list)


class PortfolioDiagnosticsComparisonRow(BaseModel):
    key: str
    label: str
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta_value: float | None = None


class PortfolioImprovementComparison(BaseModel):
    factor_exposure_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    volatility_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    risk_contribution_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    concentration_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    stress_scenario_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)


class PortfolioAllocationBacktestResponse(BaseModel):
    methodology: str
    reference_result: AllocationBacktestResult | None = None
    candidate_result: AllocationBacktestResult
    comparison: AllocationBacktestComparison | None = None
    reference_diagnostics: PortfolioDiagnosticsSnapshot | None = None
    candidate_diagnostics: PortfolioDiagnosticsSnapshot | None = None
    diagnostics_comparison: PortfolioImprovementComparison | None = None
