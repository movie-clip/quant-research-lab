from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.schemas.ranking import (
    ETF_RANKING_ARTIFACT_SCHEMA_VERSION,
    EtfRankingArtifactSchemaVersion,
    INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION,
    IntentBoundEtfReplacementRankingArtifactSchemaVersion,
    PersistedRankingArtifactEnvelope,
    RankingArtifactConfidence,
    RankingArtifactDiscoveryContractVersion,
    RankingArtifactDiscoveryFilterName,
    RankingArtifactKind,
    RankingArtifactKindRegistryVersion,
    RankingEffectiveInputsBase,
    RANKING_ARTIFACT_KIND_REGISTRY_VERSION,
    RankingArtifactMetadataProvenance,
    RankingArtifactSchemaVersion,
    RankingArtifactMetadataTruth,
    RankingArtifactRecencySameDayProvenance,
    RankingRequestContextBase,
    RankingRunMetadataBase,
    RankingSourceStatus,
    RANKING_ARTIFACT_KIND_REGISTRY,
    SUPPORTED_RANKING_ARTIFACT_KINDS,
    SUPPORTED_RANKING_ARTIFACT_DISCOVERY_FILTERS,
    SUPPORTED_RANKING_ARTIFACT_METADATA_PROVENANCE,
    validate_ranking_artifact_discovery_filters,
)
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


InvestorEconomicsWithheldReason = Literal["withheld_unverified_total_return_equivalence"]
INVESTOR_ECONOMICS_WITHHELD_REASON: InvestorEconomicsWithheldReason = "withheld_unverified_total_return_equivalence"


class InvestorEconomicsStatus(BaseModel):
    status: Literal["available", "withheld"]
    reason: InvestorEconomicsWithheldReason | None = None


def build_investor_economics_status(*, available: bool) -> InvestorEconomicsStatus:
    if available:
        return InvestorEconomicsStatus(status="available", reason=None)
    return InvestorEconomicsStatus(
        status="withheld",
        reason=INVESTOR_ECONOMICS_WITHHELD_REASON,
    )


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
    investor_economics_status: InvestorEconomicsStatus
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
    lookback_months: int = Field(3, ge=1)
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


class EtfRankingRequestContext(RankingRequestContextBase):
    benchmark_symbol: str | None = None
    lookback_months: int | None = None
    peer_group: str | None = None
    weights: EtfRankingComponentWeights

    @model_validator(mode="after")
    def validate_strict_fields(self) -> "EtfRankingRequestContext":
        if self.benchmark_symbol is None:
            raise ValueError("benchmark_symbol is required")
        if self.lookback_months is None:
            raise ValueError("lookback_months is required")
        if self.lookback_months < 1:
            raise ValueError("lookback_months must be at least 1")
        return self


class EtfRankingEffectiveInputs(RankingEffectiveInputsBase):
    benchmark_symbol: str | None = None
    lookback_months: int | None = None
    price_basis: str | None = "close"
    effective_peer_group: str | None = None
    effective_component_weights: EtfRankingComponentWeights
    excluded_symbols: list[EtfRankingExcludedSymbol] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_strict_fields(self) -> "EtfRankingEffectiveInputs":
        if self.benchmark_symbol is None:
            raise ValueError("benchmark_symbol is required")
        if self.lookback_months is None:
            raise ValueError("lookback_months is required")
        if self.lookback_months < 1:
            raise ValueError("lookback_months must be at least 1")
        if self.price_basis != "close":
            raise ValueError("price_basis must be close")
        return self


class EtfRankingRunMetadata(RankingRunMetadataBase):
    price_basis: str | None = "close"
    source_status: EtfRankingSourceStatus

    @model_validator(mode="after")
    def validate_close_price_basis(self) -> "EtfRankingRunMetadata":
        if self.price_basis != "close":
            raise ValueError("price_basis must be close")
        return self


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


class EtfRankingArtifact(EtfRankingResponse, PersistedRankingArtifactEnvelope):
    schema_version: EtfRankingArtifactSchemaVersion = ETF_RANKING_ARTIFACT_SCHEMA_VERSION
    artifact_id: str

    @model_validator(mode="after")
    def _validate_artifact_identifier(self) -> "EtfRankingArtifact":
        if not self.artifact_id.startswith("etf_ranking_artifact_"):
            raise ValueError("artifact_id must use the stable etf_ranking_artifact_ prefix")
        return self


class EtfRankingArtifactRecentRow(BaseModel):
    artifact_id: str
    ranking_id: str
    methodology_id: str
    as_of_date: str
    ranking_basis_date: str
    benchmark_symbol: str
    lookback_months: int
    universe_size: int
    evaluated_universe_size: int
    effective_peer_group: str | None = None
    confidence: Literal["high", "medium", "low"]


class EtfRankingArtifactRecentMetadata(BaseModel):
    available_effective_peer_groups: list[str] = Field(default_factory=list)


class RankingArtifactCatalogEtfSummary(BaseModel):
    benchmark_symbol: str
    lookback_months: int
    effective_peer_group: str | None = None
    universe_size: int
    evaluated_universe_size: int
    confidence: RankingArtifactConfidence


class RankingArtifactCatalogReplacementSummary(BaseModel):
    basis_date: str
    status: Literal["ok", "unavailable"]
    base_symbol: str
    candidate_symbol: str
    peer_group: str
    eligible_count: int
    excluded_count: int
    confidence: RankingArtifactConfidence


class RankingArtifactDiscoveryFilters(BaseModel):
    artifact_kind: str | None = None
    schema_version: str | None = None
    metadata_truth: RankingArtifactMetadataTruth | None = None
    metadata_provenance: RankingArtifactMetadataProvenance | None = None
    recency_same_day_provenance: RankingArtifactRecencySameDayProvenance | None = None
    methodology_id: str | None = None
    benchmark_symbol: str | None = None
    effective_peer_group: str | None = None
    base_symbol: str | None = None
    candidate_symbol: str | None = None
    peer_group: str | None = None
    confidence: RankingArtifactConfidence | None = None
    status: Literal["ok", "unavailable"] | None = None
    as_of_date: str | None = None
    ranking_basis_date: str | None = None
    basis_date: str | None = None

    @model_validator(mode="after")
    def validate_supported_contract_state(self) -> "RankingArtifactDiscoveryFilters":
        try:
            validate_ranking_artifact_discovery_filters(
                artifact_kind=self.artifact_kind,
                schema_version=self.schema_version,
                applied_filters=tuple(
                    field_name
                    for field_name, value in self.model_dump().items()
                    if value is not None
                ),
            )
        except ValueError as exc:
            raise ValueError(str(exc)) from exc
        return self


class RankingArtifactCatalogRowMetadata(BaseModel):
    metadata_truth: RankingArtifactMetadataTruth = "authoritative_persisted_metadata"
    metadata_provenance: RankingArtifactMetadataProvenance
    matched_metadata_provenance: RankingArtifactMetadataProvenance
    recency_same_day_provenance: RankingArtifactRecencySameDayProvenance

    @model_validator(mode="after")
    def validate_provenance_state(self) -> "RankingArtifactCatalogRowMetadata":
        if (
            self.metadata_provenance == "persisted_etf_recent_index"
            and self.matched_metadata_provenance != "persisted_etf_recent_index"
        ):
            raise ValueError(
                "matched_metadata_provenance must remain persisted_etf_recent_index when row metadata_provenance uses the etf recent index"
            )
        return self


class RankingArtifactCatalogRow(BaseModel):
    artifact_kind: RankingArtifactKind
    artifact_id: str
    schema_version: RankingArtifactSchemaVersion
    ranking_id: str
    methodology_id: str
    as_of_date: str
    ranking_basis_date: str
    recent_order_primary_date: str
    recent_order_secondary_date: str
    recent_order_artifact_id: str
    metadata: RankingArtifactCatalogRowMetadata
    etf_summary: RankingArtifactCatalogEtfSummary | None = None
    replacement_summary: RankingArtifactCatalogReplacementSummary | None = None

    @model_validator(mode="after")
    def validate_kind_specific_contract(self) -> "RankingArtifactCatalogRow":
        if self.artifact_kind == "etf_ranking":
            if self.schema_version != ETF_RANKING_ARTIFACT_SCHEMA_VERSION:
                raise ValueError("unsupported ranking artifact schema_version")
            if self.etf_summary is None or self.replacement_summary is not None:
                raise ValueError("etf_ranking rows must populate only etf_summary")
            return self

        if self.artifact_kind == "intent_bound_etf_replacement_ranking":
            if self.schema_version != INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION:
                raise ValueError("unsupported ranking artifact schema_version")
            if self.replacement_summary is None or self.etf_summary is not None:
                raise ValueError(
                    "intent_bound_etf_replacement_ranking rows must populate only replacement_summary"
                )
            return self

        raise ValueError("unsupported ranking artifact kind")


class RankingArtifactKindCapabilities(BaseModel):
    artifact_kind: RankingArtifactKind
    supported_schema_versions: list[str] = Field(default_factory=list)
    supported_filters: list[RankingArtifactDiscoveryFilterName] = Field(default_factory=list)


class RankingArtifactCatalogMetadata(BaseModel):
    contract_version: RankingArtifactDiscoveryContractVersion = "ranking_artifact_discovery_v1"
    supported_artifact_kinds: list[RankingArtifactKind] = Field(
        default_factory=lambda: list(SUPPORTED_RANKING_ARTIFACT_KINDS)
    )
    metadata_truth: RankingArtifactMetadataTruth = "authoritative_persisted_metadata"
    supported_metadata_provenance: list[RankingArtifactMetadataProvenance] = Field(
        default_factory=lambda: list(SUPPORTED_RANKING_ARTIFACT_METADATA_PROVENANCE)
    )
    artifact_kind_registry_version: RankingArtifactKindRegistryVersion = RANKING_ARTIFACT_KIND_REGISTRY_VERSION
    supported_filters: list[RankingArtifactDiscoveryFilterName] = Field(
        default_factory=lambda: list(SUPPORTED_RANKING_ARTIFACT_DISCOVERY_FILTERS)
    )
    artifact_kind_registry: list["RankingArtifactKindCapabilities"] = Field(
        default_factory=lambda: [
            RankingArtifactKindCapabilities(
                artifact_kind=entry.artifact_kind,
                supported_schema_versions=list(entry.supported_schema_versions),
                supported_filters=list(entry.supported_filters),
            )
            for entry in RANKING_ARTIFACT_KIND_REGISTRY
        ]
    )
    applied_filters: RankingArtifactDiscoveryFilters = Field(default_factory=RankingArtifactDiscoveryFilters)


class RankingArtifactCatalogListResponse(BaseModel):
    items: list[RankingArtifactCatalogRow] = Field(default_factory=list)
    metadata: RankingArtifactCatalogMetadata = Field(default_factory=RankingArtifactCatalogMetadata)


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
    benchmark_symbol: str
    lookback_months: int = Field(..., ge=1)


class IntentBoundSeedContext(BaseModel):
    ranking_id: str
    methodology_id: str
    ranking_basis_date: str
    peer_group: str
    benchmark_symbol: str
    lookback_months: int = Field(..., ge=1)
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
    benchmark_symbol: str
    lookback_months: int = Field(..., ge=1)


class IntentBoundEtfReplacementRequestContext(RankingRequestContextBase):
    benchmark_symbol: str | None = None
    lookback_months: int | None = None
    base_symbol: str
    candidate_symbol: str
    peer_group: str
    ranking_basis_date: str
    seed_ranking_id: str
    seed_methodology_id: str

    @model_validator(mode="after")
    def validate_strict_fields(self) -> "IntentBoundEtfReplacementRequestContext":
        if self.benchmark_symbol is None:
            raise ValueError("benchmark_symbol is required")
        if self.lookback_months is None:
            raise ValueError("lookback_months is required")
        if self.lookback_months < 1:
            raise ValueError("lookback_months must be at least 1")
        return self


class IntentBoundEtfReplacementEffectiveInputs(RankingEffectiveInputsBase):
    benchmark_symbol: str | None = None
    lookback_months: int | None = None
    price_basis: str | None = "close"
    base_symbol: str
    candidate_symbol: str
    peer_group: str
    ranking_basis_date: str

    @model_validator(mode="after")
    def validate_strict_fields(self) -> "IntentBoundEtfReplacementEffectiveInputs":
        if self.benchmark_symbol is None:
            raise ValueError("benchmark_symbol is required")
        if self.lookback_months is None:
            raise ValueError("lookback_months is required")
        if self.lookback_months < 1:
            raise ValueError("lookback_months must be at least 1")
        if self.price_basis != "close":
            raise ValueError("price_basis must be close")
        return self


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


class IntentBoundEtfReplacementIntentLineage(BaseModel):
    draft_id: str
    workspace_id: str
    base_node_id: str
    base_symbol: str
    candidate_symbol: str
    seed_ranking_id: str
    seed_methodology_id: str
    seed_ranking_basis_date: str
    peer_group: str
    benchmark_symbol: str
    lookback_months: int = Field(..., ge=1)


class IntentBoundEtfReplacementArtifactRequest(BaseModel):
    replacement_intent: IntentBoundReplacementIntent
    seed_context: IntentBoundSeedContext
    prefer_live_data: bool = False
    normalized_request: IntentBoundEtfReplacementNormalizedRequest


class IntentBoundEtfReplacementRankingRunMetadata(RankingRunMetadataBase):
    basis_date: str
    request_hash: str
    price_basis: str | None = "close"
    source_status: RankingSourceStatus
    tie_break_order: list[str] = Field(default_factory=list)
    factor_weights: dict[str, float] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_close_price_basis(self) -> "IntentBoundEtfReplacementRankingRunMetadata":
        if self.price_basis != "close":
            raise ValueError("price_basis must be close")
        return self


class IntentBoundEtfReplacementRankingResponse(BaseModel):
    ranking_id: str
    methodology_id: str
    basis_date: str
    status: Literal["ok", "unavailable"]
    request: IntentBoundEtfReplacementRequestContext
    request_context: IntentBoundEtfReplacementRequestContext
    submitted_request: IntentBoundEtfReplacementRankingRequest
    normalized_request: IntentBoundEtfReplacementNormalizedRequest
    effective_inputs: IntentBoundEtfReplacementEffectiveInputs
    request_hash: str
    run_metadata: IntentBoundEtfReplacementRankingRunMetadata
    eligible_count: int
    excluded_count: int
    ranked_candidates: list[IntentBoundEtfReplacementCandidateRow] = Field(default_factory=list)
    excluded_candidates: list[IntentBoundEtfReplacementCandidateRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unavailable_reason: str | None = None


class IntentBoundEtfReplacementRankingArtifact(PersistedRankingArtifactEnvelope, BaseModel):
    schema_version: IntentBoundEtfReplacementRankingArtifactSchemaVersion = (
        INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION
    )
    artifact_id: str
    ranking_id: str
    methodology_id: str
    basis_date: str
    status: Literal["ok", "unavailable"]
    request: IntentBoundEtfReplacementArtifactRequest
    request_context: IntentBoundEtfReplacementRequestContext
    submitted_request: IntentBoundEtfReplacementRankingRequest
    normalized_request: IntentBoundEtfReplacementNormalizedRequest
    effective_inputs: IntentBoundEtfReplacementEffectiveInputs
    request_hash: str
    run_metadata: IntentBoundEtfReplacementRankingRunMetadata
    eligible_count: int
    excluded_count: int
    ranked_candidates: list[IntentBoundEtfReplacementCandidateRow] = Field(default_factory=list)
    excluded_candidates: list[IntentBoundEtfReplacementCandidateRow] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    unavailable_reason: str | None = None
    lineage: IntentBoundEtfReplacementIntentLineage

    @model_validator(mode="after")
    def _validate_artifact_identifier(self) -> "IntentBoundEtfReplacementRankingArtifact":
        if not self.artifact_id.startswith("intent_bound_etf_replacement_ranking_artifact_"):
            raise ValueError(
                "artifact_id must use the stable intent_bound_etf_replacement_ranking_artifact_ prefix"
            )
        if self.request.normalized_request != self.normalized_request:
            raise ValueError("request.normalized_request must match the persisted normalized_request")
        if self.request_context.base_symbol != self.lineage.base_symbol:
            raise ValueError("lineage.base_symbol must match request_context.base_symbol")
        if self.request_context.candidate_symbol != self.lineage.candidate_symbol:
            raise ValueError("lineage.candidate_symbol must match request_context.candidate_symbol")
        if self.request_context.seed_ranking_id != self.lineage.seed_ranking_id:
            raise ValueError("lineage.seed_ranking_id must match request_context.seed_ranking_id")
        if self.request_context.seed_methodology_id != self.lineage.seed_methodology_id:
            raise ValueError("lineage.seed_methodology_id must match request_context.seed_methodology_id")
        if self.effective_inputs.base_symbol != self.lineage.base_symbol:
            raise ValueError("lineage.base_symbol must match effective_inputs.base_symbol")
        if self.effective_inputs.candidate_symbol != self.lineage.candidate_symbol:
            raise ValueError("lineage.candidate_symbol must match effective_inputs.candidate_symbol")
        return self
