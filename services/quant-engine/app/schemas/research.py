from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.reconciliation import RiskContributionBreakdownPayload, SnapshotItem, StressScenarioResult, VolatilitySnapshot


AssetClass = Literal["equity", "etf", "future", "forex", "index", "crypto", "other"]
InstrumentKind = Literal["spot", "continuous_future", "future_contract"]
StrategySide = Literal["long", "short", "both"]
BacktestFrequency = Literal["1d", "1h", "15m", "5m"]
RollMethod = Literal["none", "calendar", "volume", "open_interest"]
DistributionPolicy = Literal["accumulating", "distributing", "unknown"]


class Instrument(BaseModel):
    instrument_id: str
    symbol: str
    name: str | None = None
    asset_class: AssetClass
    kind: InstrumentKind
    sector: str | None = None
    category: str | None = None
    exchange: str | None = None
    currency: str | None = None
    tick_size: float | None = None
    point_value: float | None = None
    multiplier: float | None = None


class FuturesContract(BaseModel):
    instrument_id: str
    root_symbol: str
    contract_symbol: str
    exchange: str
    currency: str
    expiry_date: date
    first_notice_date: date | None = None
    tick_size: float | None = None
    point_value: float | None = None
    multiplier: float | None = None


class ContinuousSeriesSpec(BaseModel):
    root_symbol: str
    roll_method: RollMethod = "calendar"
    roll_days_before_expiry: int = 5
    back_adjusted: bool = True
    price_field: Literal["open", "high", "low", "close", "settle"] = "close"


class BarRecord(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class StrategySignal(BaseModel):
    date: str
    symbol: str
    signal: Literal[-1, 0, 1]
    reason: str


class StrategyParameter(BaseModel):
    name: str
    value: int | float | str | bool


class StrategyDefinition(BaseModel):
    strategy_id: str
    name: str
    description: str | None = None
    timeframe: BacktestFrequency = "1d"
    side: StrategySide = "both"
    universe: list[str] = Field(default_factory=list)
    parameters: list[StrategyParameter] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class EtfMomentumWeight(BaseModel):
    symbol: str
    target_weight: float
    score: float
    trailing_return_pct: float
    average_volume: float | None = None


class EtfMomentumObservation(BaseModel):
    date: str
    rankings: list[EtfMomentumWeight] = Field(default_factory=list)
    holdings: list[EtfMomentumWeight] = Field(default_factory=list)
    leader: str | None = None
    leader_score: float | None = None
    benchmark_return_pct: float | None = None
    strategy_return_pct: float | None = None
    average_volume_ratio: float | None = None


class EtfMomentumPoint(BaseModel):
    date: str
    strategy_equity: float
    benchmark_equity: float
    strategy_drawdown_pct: float | None = None
    benchmark_drawdown_pct: float | None = None


class EtfMomentumMetrics(BaseModel):
    total_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    excess_return_pct: float | None = None
    annualized_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    benchmark_max_drawdown_pct: float | None = None
    win_rate_pct: float | None = None
    average_turnover_pct: float | None = None
    average_volume_participation_ratio: float | None = None


class EtfLeaderConstituent(BaseModel):
    symbol: str
    name: str
    weight: float
    trailing_return_pct: float | None = None
    weighted_contribution_pct: float | None = None


class EtfLeaderInternalsObservation(BaseModel):
    date: str
    leader_symbol: str | None = None
    source_mode: str = "sample"
    snapshot_date: str | None = None
    constituents: list[EtfLeaderConstituent] = Field(default_factory=list)


class EtfConstituentInternalsObservation(BaseModel):
    date: str
    etf_symbol: str
    source_mode: str = "sample"
    snapshot_date: str | None = None
    constituents: list[EtfLeaderConstituent] = Field(default_factory=list)


class EtfMomentumSourceStatus(BaseModel):
    price_history: str
    leader_internals: str
    holdings_snapshot_counts: dict[str, int] = Field(default_factory=dict)
    dated_holdings_symbols: list[str] = Field(default_factory=list)
    sample_fallback_symbols: list[str] = Field(default_factory=list)


class EtfMomentumStrategyResponse(BaseModel):
    strategy_id: str
    title: str
    benchmark_symbol: str
    universe: list[str] = Field(default_factory=list)
    start_date: str
    end_date: str
    rebalance_frequency: AllocationRebalanceFrequency = "monthly"
    lookback_months: int
    top_n: int
    methodology: str
    current_rankings: list[EtfMomentumWeight] = Field(default_factory=list)
    latest_holdings: list[EtfMomentumWeight] = Field(default_factory=list)
    observations: list[EtfMomentumObservation] = Field(default_factory=list)
    leader_internals: list[EtfLeaderInternalsObservation] = Field(default_factory=list)
    etf_internals_history: dict[str, list[EtfConstituentInternalsObservation]] = Field(default_factory=dict)
    source_status: EtfMomentumSourceStatus
    equity_curve: list[EtfMomentumPoint] = Field(default_factory=list)
    metrics: EtfMomentumMetrics
