from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.reconciliation import RiskContributionBreakdownPayload, SnapshotItem, StressScenarioResult, VolatilitySnapshot


AssetClass = Literal["equity", "etf", "future", "forex", "index", "crypto", "other"]
InstrumentKind = Literal["spot", "continuous_future", "future_contract"]
StrategySide = Literal["long", "short", "both"]
BacktestFrequency = Literal["1d", "1h", "15m", "5m"]
RollMethod = Literal["none", "calendar", "volume", "open_interest"]
DistributionPolicy = Literal["accumulating", "distributing", "unknown"]
AllocationRebalanceFrequency = Literal["none", "monthly", "quarterly"]


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
    strategy_equity: float | None = None
    benchmark_equity: float | None = None
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


RankingDirection = Literal["higher_is_better", "lower_is_better"]
RankingUnit = Literal["pct", "volume", "score"]


class EtfRankingComponentWeights(BaseModel):
    momentum: float = 0.30
    benchmark_relative_strength: float = 0.20
    realized_volatility: float = 0.15
    downside_volatility: float = 0.10
    max_drawdown: float = 0.10
    liquidity: float = 0.10
    implementation_fit: float = 0.05

    @model_validator(mode="after")
    def validate_weights(self) -> "EtfRankingComponentWeights":
        values = [
            self.momentum,
            self.benchmark_relative_strength,
            self.realized_volatility,
            self.downside_volatility,
            self.max_drawdown,
            self.liquidity,
            self.implementation_fit,
        ]
        if any(value < 0 for value in values):
            raise ValueError("ranking component weights must be non-negative")
        if sum(values) <= 0:
            raise ValueError("at least one ranking component weight must be positive")
        return self

    def normalized(self) -> "EtfRankingComponentWeights":
        total = (
            self.momentum
            + self.benchmark_relative_strength
            + self.realized_volatility
            + self.downside_volatility
            + self.max_drawdown
            + self.liquidity
            + self.implementation_fit
        )
        return EtfRankingComponentWeights(
            momentum=self.momentum / total,
            benchmark_relative_strength=self.benchmark_relative_strength / total,
            realized_volatility=self.realized_volatility / total,
            downside_volatility=self.downside_volatility / total,
            max_drawdown=self.max_drawdown / total,
            liquidity=self.liquidity / total,
            implementation_fit=self.implementation_fit / total,
        )


class EtfRankingRequest(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark_symbol: str = "SPY"
    lookback_months: int = 6
    prefer_live_data: bool = False
    peer_group: str | None = None
    weights: EtfRankingComponentWeights = Field(default_factory=EtfRankingComponentWeights)


class EtfRankingInstrumentContext(BaseModel):
    symbol: str
    name: str | None = None
    asset_class: AssetClass | None = None
    sector: str | None = None
    category: str | None = None
    currency: str | None = None


class EtfRankingComponentScore(BaseModel):
    label: str
    direction: RankingDirection
    raw_value: float
    raw_unit: RankingUnit
    normalized_score: float
    weight: float
    weighted_score: float


class EtfRankingRow(BaseModel):
    rank: int
    symbol: str
    composite_score: float
    instrument: EtfRankingInstrumentContext
    component_scores: dict[str, EtfRankingComponentScore] = Field(default_factory=dict)


class EtfRankingExcludedSymbol(BaseModel):
    symbol: str
    reason: str


class EtfRankingSourceStatus(BaseModel):
    price_history: Literal["sample", "live", "mixed"]
    benchmark_history: Literal["sample", "live"]
    holdings_support: Literal["sample", "mixed", "unavailable"]


class EtfRankingWarnings(BaseModel):
    confidence: Literal["high", "medium", "low"]
    warnings: list[str] = Field(default_factory=list)
    unknown_metadata_symbols: list[str] = Field(default_factory=list)
    peer_group_unclassified_symbols: list[str] = Field(default_factory=list)


class EtfRankingRequestContext(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark_symbol: str
    lookback_months: int
    prefer_live_data: bool = False
    peer_group: str | None = None
    weights: EtfRankingComponentWeights


class EtfRankingEffectiveInputs(BaseModel):
    benchmark_symbol: str
    lookback_months: int
    price_basis: Literal["close"] = "close"
    requested_universe: list[str] = Field(default_factory=list)
    evaluated_universe: list[str] = Field(default_factory=list)
    effective_peer_group: str | None = None
    effective_component_weights: EtfRankingComponentWeights
    excluded_symbols: list[EtfRankingExcludedSymbol] = Field(default_factory=list)


class EtfRankingRunMetadata(BaseModel):
    ranking_id: str
    methodology_id: str
    methodology: str
    as_of_date: str
    ranking_basis_date: str
    price_basis: Literal["close"] = "close"
    source_status: EtfRankingSourceStatus
    confidence: Literal["high", "medium", "low"]


class EtfRankingResponse(BaseModel):
    ranking_id: str
    title: str
    as_of_date: str
    benchmark_symbol: str
    universe: list[str] = Field(default_factory=list)
    lookback_months: int
    price_basis: Literal["close"] = "close"
    methodology: str
    effective_peer_group: str | None = None
    effective_component_weights: EtfRankingComponentWeights
    source_status: EtfRankingSourceStatus
    warnings: EtfRankingWarnings
    request: EtfRankingRequestContext
    effective_inputs: EtfRankingEffectiveInputs
    run_metadata: EtfRankingRunMetadata
    ranked_universe: list[EtfRankingRow] = Field(default_factory=list)
    excluded_symbols: list[EtfRankingExcludedSymbol] = Field(default_factory=list)


class IntentBoundReplacementIntent(BaseModel):
    draft_id: str
    workspace_id: str
    base_node_id: str
    base_symbol: str
    candidate_symbol: str
    seed_ranking_id: str
    seed_methodology_id: str
    seed_ranking_basis_date: str
    peer_group: str


class IntentBoundSeedContext(BaseModel):
    ranking_id: str
    methodology_id: str
    ranking_basis_date: str
    peer_group: str
    seeded_symbols: list[str] = Field(default_factory=list)


class IntentBoundEtfReplacementRankingRequest(BaseModel):
    replacement_intent: IntentBoundReplacementIntent
    seed_context: IntentBoundSeedContext
    prefer_live_data: bool = False


class IntentBoundEtfReplacementNormalizedRequest(BaseModel):
    base_symbol: str
    candidate_symbol: str
    seeded_symbols: list[str] = Field(default_factory=list)
    peer_group: str
    ranking_basis_date: str


class IntentBoundEtfReplacementRawFactors(BaseModel):
    momentum_12_1: float
    momentum_6_1: float
    momentum_blended: float
    realized_volatility_126d: float
    max_drawdown_252d: float
    liquidity_60d: float


class IntentBoundEtfReplacementNormalizedScores(BaseModel):
    momentum: float
    realized_volatility: float
    max_drawdown: float
    liquidity: float


class IntentBoundEtfReplacementCandidateRow(BaseModel):
    symbol: str
    rank: int | None = None
    composite_score: float | None = None
    raw_factors: IntentBoundEtfReplacementRawFactors | None = None
    normalized_scores: IntentBoundEtfReplacementNormalizedScores | None = None
    eligibility_status: Literal["eligible", "excluded"]
    exclusion_reason: str | None = None
    basis_date: str
    draft_id: str
    base_node_id: str
    base_symbol: str
    seed_ranking_id: str
    seed_methodology_id: str


class IntentBoundEtfReplacementRankingRunMetadata(BaseModel):
    ranking_id: str
    methodology_id: str
    basis_date: str
    request_hash: str
    source_status: Literal["sample", "live", "mixed"]
    tie_break_order: list[str] = Field(default_factory=list)
    factor_weights: dict[str, float] = Field(default_factory=dict)


class IntentBoundEtfReplacementRankingResponse(BaseModel):
    ranking_id: str
    methodology_id: str
    basis_date: str
    status: Literal["ok", "unavailable"]
    request: IntentBoundEtfReplacementRankingRequest
    normalized_request: IntentBoundEtfReplacementNormalizedRequest
    request_hash: str
    run_metadata: IntentBoundEtfReplacementRankingRunMetadata
    eligible_count: int
    excluded_count: int
    ranked_candidates: list[IntentBoundEtfReplacementCandidateRow] = Field(default_factory=list)
    excluded_candidates: list[IntentBoundEtfReplacementCandidateRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unavailable_reason: str | None = None
