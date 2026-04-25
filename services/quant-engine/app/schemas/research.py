from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.optimizer import OptimizerAlphaFundamentalSnapshot, OptimizerAlphaPackageStatus
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


def _validate_canonical_date_string(value: str, field_name: str) -> str:
    if value.strip() != value:
        raise ValueError(f"{field_name} must be a canonical YYYY-MM-DD date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a canonical YYYY-MM-DD date") from exc
    if parsed.isoformat() != value:
        raise ValueError(f"{field_name} must be a canonical YYYY-MM-DD date")
    return value


def _validate_canonical_utc_timestamp(value: str, field_name: str) -> str:
    if value.strip() != value:
        raise ValueError(f"{field_name} must be a canonical UTC timestamp")
    if not value.endswith("Z"):
        raise ValueError(f"{field_name} must be a canonical UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field_name} must be a canonical UTC timestamp") from exc
    if parsed.tzinfo != timezone.utc:
        raise ValueError(f"{field_name} must be a canonical UTC timestamp")
    canonical = parsed.replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise ValueError(f"{field_name} must be a canonical UTC timestamp")
    return value


def _validate_canonical_exact_string(value: str, field_name: str, expected: str) -> str:
    if value != expected:
        raise ValueError(f"{field_name} must be the canonical value {expected}")
    return value


def _validate_required_trimmed_string(value: str, field_name: str) -> str:
    if value.strip() != value or not value:
        raise ValueError(f"{field_name} must be a non-empty canonical string")
    return value


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


CrossSectionalResearchArtifactKind = Literal["cross_sectional_research_run"]
CrossSectionalResearchArtifactSchemaVersion = Literal["cross_sectional_research_artifact_v1"]
CrossSectionalResearchReloadContractVersion = Literal["cross_sectional_research_reload_v1"]
CrossSectionalResearchDiscoveryContractVersion = Literal["cross_sectional_research_discovery_v1"]
CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND: CrossSectionalResearchArtifactKind = "cross_sectional_research_run"
CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION: CrossSectionalResearchArtifactSchemaVersion = (
    "cross_sectional_research_artifact_v1"
)
CROSS_SECTIONAL_RESEARCH_RELOAD_CONTRACT_VERSION: CrossSectionalResearchReloadContractVersion = (
    "cross_sectional_research_reload_v1"
)
CROSS_SECTIONAL_RESEARCH_DISCOVERY_CONTRACT_VERSION: CrossSectionalResearchDiscoveryContractVersion = (
    "cross_sectional_research_discovery_v1"
)
CrossSectionalResearchArtifactStatus = Literal["complete", "degraded", "unknown", "unsupported"]
CrossSectionalResearchCoverageStatus = Literal["complete", "partial", "unknown", "unsupported"]
CrossSectionalResearchInputSourceKind = Literal[
    "direct_snapshot_input",
    "replay_snapshot_input",
    "backend_owned_other",
    "unknown",
    "unsupported",
]
CrossSectionalResearchReplayProvenanceStatus = Literal["present", "absent", "unknown", "unsupported"]
CrossSectionalResearchBenchmarkSourceKind = Literal[
    "request_benchmark_reference",
    "unknown",
    "unsupported",
]
CrossSectionalResearchAlphaSourceKind = Literal[
    "optimizer_alpha_package",
    "unknown",
    "unsupported",
]
CrossSectionalResearchDiscoveryFilterName = Literal[
    "artifact_kind",
    "schema_version",
    "methodology_id",
    "dataset_version",
    "universe_definition",
    "benchmark_symbol",
    "rebalance_date",
    "as_of_date",
    "holdout_start_date",
    "methodology_family_id",
    "methodology_family_version",
    "active_methodology_version",
    "alpha_package_version",
    "alpha_methodology_id",
    "alpha_input_contract_id",
    "score_basis",
    "benchmark_role",
    "partition_rule",
    "output_shape",
    "artifact_status",
    "diagnostics_status",
    "coverage_status",
    "input_source_kind",
    "replay_provenance_status",
    "benchmark_source_kind",
    "alpha_source_kind",
]
SUPPORTED_CROSS_SECTIONAL_RESEARCH_DISCOVERY_FILTERS: tuple[
    CrossSectionalResearchDiscoveryFilterName,
    ...,
] = (
    "artifact_kind",
    "schema_version",
    "methodology_id",
    "dataset_version",
    "universe_definition",
    "benchmark_symbol",
    "rebalance_date",
    "as_of_date",
    "holdout_start_date",
    "methodology_family_id",
    "methodology_family_version",
    "active_methodology_version",
    "alpha_package_version",
    "alpha_methodology_id",
    "alpha_input_contract_id",
    "score_basis",
    "benchmark_role",
    "partition_rule",
    "output_shape",
    "artifact_status",
    "diagnostics_status",
    "coverage_status",
    "input_source_kind",
    "replay_provenance_status",
    "benchmark_source_kind",
    "alpha_source_kind",
)
CrossSectionalResearchMethodologyComponentId = Literal[
    "profitability",
    "cash_generation",
    "accrual_quality",
    "leverage_discipline",
]
CANONICAL_CROSS_SECTIONAL_RESEARCH_METHODOLOGY_COMPONENT_IDS: tuple[
    CrossSectionalResearchMethodologyComponentId,
    ...,
] = (
    "profitability",
    "cash_generation",
    "accrual_quality",
    "leverage_discipline",
)
CROSS_SECTIONAL_RESEARCH_SUMMARY_PARTITION_RULE: str = (
    "Rows with effective_date before holdout_start_date belong to walk_forward; "
    "rows on or after holdout_start_date belong to holdout."
)


class CrossSectionalResearchMethodologyMetadataV1(BaseModel):
    methodology_family_id: str
    methodology_family_version: str
    active_methodology_id: str
    active_methodology_version: str
    alpha_package_version: str
    alpha_methodology_id: str
    alpha_input_contract_id: str
    score_basis: str
    benchmark_role: str
    partition_rule: str
    output_shape: str
    component_signal_ids: list[CrossSectionalResearchMethodologyComponentId] = Field(
        default_factory=lambda: list(CANONICAL_CROSS_SECTIONAL_RESEARCH_METHODOLOGY_COMPONENT_IDS)
    )

    @field_validator(
        "methodology_family_id",
        "methodology_family_version",
        "active_methodology_id",
        "active_methodology_version",
        "alpha_package_version",
        "alpha_methodology_id",
        "alpha_input_contract_id",
        "score_basis",
        "benchmark_role",
        "partition_rule",
        "output_shape",
    )
    @classmethod
    def validate_canonical_fields(cls, value: str, info) -> str:
        expected_by_field = {
            "methodology_family_id": "cross_sectional_research_family_v1",
            "methodology_family_version": "v1",
            "active_methodology_id": "alpha_quality_v1",
            "active_methodology_version": "v1",
            "alpha_package_version": "alpha_quality_v1",
            "alpha_methodology_id": "alpha_quality_v1_methodology",
            "alpha_input_contract_id": "alpha_quality_v1_pit_fundamentals_v1",
            "score_basis": "optimizer_alpha_package.final_score",
            "benchmark_role": "descriptive_reference_only",
            "partition_rule": "effective_date_before_holdout_start_else_holdout",
            "output_shape": "compact_summary_only",
        }
        return _validate_canonical_exact_string(value, info.field_name, expected_by_field[info.field_name])

    @field_validator("component_signal_ids")
    @classmethod
    def validate_component_signal_ids(
        cls,
        value: list[CrossSectionalResearchMethodologyComponentId],
    ) -> list[CrossSectionalResearchMethodologyComponentId]:
        canonical = list(CANONICAL_CROSS_SECTIONAL_RESEARCH_METHODOLOGY_COMPONENT_IDS)
        if value != canonical:
            raise ValueError(
                "component_signal_ids must match the canonical backend-owned signal order"
            )
        return value


class CrossSectionalResearchBenchmark(BaseModel):
    benchmark_symbol: str
    benchmark_name: str | None = None
    benchmark_kind: Literal["reference_index", "etf_proxy", "custom"] = "reference_index"

    @field_validator("benchmark_symbol")
    @classmethod
    def validate_benchmark_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("benchmark_symbol is required")
        if normalized != value:
            raise ValueError("benchmark_symbol must be canonical uppercase without surrounding whitespace")
        return normalized


class CrossSectionalResearchRequest(BaseModel):
    methodology_id: Literal["alpha_quality_v1"] = "alpha_quality_v1"
    rebalance_date: str
    as_of_date: str
    holdout_start_date: str
    dataset_version: str
    universe_definition: str
    benchmark: CrossSectionalResearchBenchmark
    universe_symbols: list[str] = Field(default_factory=list)
    fundamental_snapshots: list[OptimizerAlphaFundamentalSnapshot] = Field(default_factory=list)
    source_name: str = "direct_snapshot_input"
    replay_id: str | None = None
    top_ranked_count: int = Field(3, ge=1, le=10)

    @field_validator("rebalance_date", "as_of_date", "holdout_start_date")
    @classmethod
    def validate_canonical_dates(cls, value: str, info) -> str:
        return _validate_canonical_date_string(value, info.field_name)

    @field_validator("dataset_version", "universe_definition", "source_name")
    @classmethod
    def validate_non_empty_string(cls, value: str, info) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError(f"{info.field_name} is required")
        return normalized

    @field_validator("universe_symbols")
    @classmethod
    def validate_universe_symbols(cls, value: list[str]) -> list[str]:
        normalized = [symbol.strip().upper() for symbol in value if symbol and symbol.strip()]
        if not normalized:
            raise ValueError("universe_symbols must include at least one symbol")
        deduped: list[str] = []
        seen: set[str] = set()
        for symbol in normalized:
            if symbol in seen:
                continue
            seen.add(symbol)
            deduped.append(symbol)
        return deduped

    @model_validator(mode="after")
    def validate_dates_and_snapshot_coverage(self) -> "CrossSectionalResearchRequest":
        rebalance_dt = date.fromisoformat(self.rebalance_date)
        as_of_dt = date.fromisoformat(self.as_of_date)
        holdout_start_dt = date.fromisoformat(self.holdout_start_date)
        if as_of_dt > rebalance_dt:
            raise ValueError("as_of_date cannot be later than rebalance_date")
        if holdout_start_dt > rebalance_dt:
            raise ValueError("holdout_start_date cannot be later than rebalance_date")
        if not self.fundamental_snapshots:
            raise ValueError("fundamental_snapshots must include at least one record")
        snapshot_symbols = {snapshot.symbol.strip().upper() for snapshot in self.fundamental_snapshots if snapshot.symbol}
        missing_symbols = [symbol for symbol in self.universe_symbols if symbol not in snapshot_symbols]
        if missing_symbols:
            raise ValueError(
                "fundamental_snapshots must include at least one record for every universe symbol: "
                + ", ".join(missing_symbols)
            )
        return self


class CrossSectionalResearchSummaryProvenance(BaseModel):
    alpha_package_id: str
    alpha_package_version: str
    alpha_methodology_id: str
    input_digest: str
    source_name: str
    as_of_date: str
    rebalance_date: str
    holdout_start_date: str
    benchmark_symbol: str
    benchmark_kind: Literal["reference_index", "etf_proxy", "custom"]
    partition_rule: str

    @field_validator(
        "alpha_package_id",
        "alpha_package_version",
        "alpha_methodology_id",
        "input_digest",
        "source_name",
    )
    @classmethod
    def validate_required_strings(cls, value: str, info) -> str:
        return _validate_required_trimmed_string(value, info.field_name)

    @field_validator("as_of_date", "rebalance_date", "holdout_start_date")
    @classmethod
    def validate_canonical_dates(cls, value: str, info) -> str:
        return _validate_canonical_date_string(value, info.field_name)

    @field_validator("benchmark_symbol")
    @classmethod
    def validate_benchmark_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != value or not normalized:
            raise ValueError("benchmark_symbol must be canonical uppercase without surrounding whitespace")
        return normalized

    @field_validator("partition_rule")
    @classmethod
    def validate_partition_rule(cls, value: str) -> str:
        return _validate_canonical_exact_string(
            value,
            "partition_rule",
            CROSS_SECTIONAL_RESEARCH_SUMMARY_PARTITION_RULE,
        )


class CrossSectionalResearchCompactSummary(BaseModel):
    split_label: Literal["walk_forward", "holdout"]
    sample_count: int = Field(ge=0)
    universe_size: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    complete_coverage_ratio: float = Field(ge=0.0, le=1.0)
    mean_score: float | None = None
    median_score: float | None = None
    positive_score_share: float | None = None
    top_ranked_symbols: list[str] = Field(default_factory=list)
    effective_start_date: str | None = None
    effective_end_date: str | None = None
    provenance: CrossSectionalResearchSummaryProvenance

    @field_validator("effective_start_date", "effective_end_date")
    @classmethod
    def validate_optional_dates(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _validate_canonical_date_string(value, info.field_name)

    @field_validator("top_ranked_symbols")
    @classmethod
    def validate_top_ranked_symbols(cls, value: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for symbol in value:
            normalized = symbol.strip().upper()
            if normalized != symbol or not normalized:
                raise ValueError("top_ranked_symbols must contain canonical uppercase symbols")
            if normalized in seen:
                raise ValueError("top_ranked_symbols must not contain duplicates")
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    @model_validator(mode="after")
    def validate_summary_consistency(self) -> "CrossSectionalResearchCompactSummary":
        if self.sample_count > self.universe_size:
            raise ValueError("sample_count cannot exceed universe_size")
        if len(self.top_ranked_symbols) > self.sample_count:
            raise ValueError("top_ranked_symbols cannot exceed sample_count")
        if self.effective_start_date is not None and self.effective_end_date is not None:
            if date.fromisoformat(self.effective_start_date) > date.fromisoformat(self.effective_end_date):
                raise ValueError("effective_start_date cannot be later than effective_end_date")
        return self


class CrossSectionalResearchArtifactProvenance(BaseModel):
    source_name: str
    replay_id: str | None = None
    input_digest: str
    alpha_input_contract_id: str
    point_in_time_only: bool
    alpha_package_id: str
    alpha_package_version: str
    alpha_diagnostics_status: OptimizerAlphaPackageStatus
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    complete_coverage_ratio: float = Field(ge=0.0, le=1.0)
    missing_snapshot_symbols: list[str] = Field(default_factory=list)
    stale_symbols: list[str] = Field(default_factory=list)
    lag_blocked_symbols: list[str] = Field(default_factory=list)
    fallback_symbols: list[str] = Field(default_factory=list)

    @field_validator(
        "source_name",
        "input_digest",
        "alpha_input_contract_id",
        "alpha_package_id",
        "alpha_package_version",
    )
    @classmethod
    def validate_required_strings(cls, value: str, info) -> str:
        return _validate_required_trimmed_string(value, info.field_name)

    @field_validator("replay_id")
    @classmethod
    def validate_optional_replay_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_required_trimmed_string(value, "replay_id")

    @field_validator(
        "missing_snapshot_symbols",
        "stale_symbols",
        "lag_blocked_symbols",
        "fallback_symbols",
    )
    @classmethod
    def validate_symbol_lists(cls, value: list[str], info) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for symbol in value:
            normalized = symbol.strip().upper()
            if normalized != symbol or not normalized:
                raise ValueError(f"{info.field_name} must contain canonical uppercase symbols")
            if normalized in seen:
                raise ValueError(f"{info.field_name} must not contain duplicates")
            seen.add(normalized)
            deduped.append(normalized)
        return deduped


class CrossSectionalResearchStatusMetadataV1(BaseModel):
    artifact_status: CrossSectionalResearchArtifactStatus
    diagnostics_status: OptimizerAlphaPackageStatus | Literal["unknown", "unsupported"]
    coverage_status: CrossSectionalResearchCoverageStatus

    @model_validator(mode="after")
    def validate_descriptive_status_consistency(self) -> "CrossSectionalResearchStatusMetadataV1":
        if self.diagnostics_status == "ok" and self.artifact_status != "complete":
            raise ValueError("artifact_status must be complete when diagnostics_status is ok")
        if self.diagnostics_status == "invalid" and self.artifact_status != "degraded":
            raise ValueError("artifact_status must be degraded when diagnostics_status is invalid")
        return self


class CrossSectionalResearchProvenanceMetadataV1(BaseModel):
    input_source_kind: CrossSectionalResearchInputSourceKind
    replay_provenance_status: CrossSectionalResearchReplayProvenanceStatus
    benchmark_source_kind: CrossSectionalResearchBenchmarkSourceKind
    alpha_source_kind: CrossSectionalResearchAlphaSourceKind

    @model_validator(mode="after")
    def validate_descriptive_provenance_consistency(self) -> "CrossSectionalResearchProvenanceMetadataV1":
        if self.input_source_kind == "replay_snapshot_input" and self.replay_provenance_status != "present":
            raise ValueError(
                "replay_provenance_status must be present when input_source_kind is replay_snapshot_input"
            )
        if (
            self.input_source_kind in {"direct_snapshot_input", "backend_owned_other"}
            and self.replay_provenance_status == "present"
        ):
            raise ValueError(
                "replay_provenance_status present requires input_source_kind replay_snapshot_input"
            )
        return self


class CrossSectionalResearchValidationResponse(BaseModel):
    valid: Literal[True] = True
    artifact_kind: CrossSectionalResearchArtifactKind = CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND
    schema_version: CrossSectionalResearchArtifactSchemaVersion = CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION
    would_persist_artifact_id: str
    would_persist_fingerprint: str
    normalized_request: CrossSectionalResearchRequest
    methodology: str
    methodology_metadata_v1: CrossSectionalResearchMethodologyMetadataV1
    status_metadata_v1: CrossSectionalResearchStatusMetadataV1
    provenance_metadata_v1: CrossSectionalResearchProvenanceMetadataV1
    assumptions: list[str] = Field(default_factory=list)
    dataset_version: str
    universe_definition: str
    benchmark: CrossSectionalResearchBenchmark
    walk_forward_summary: CrossSectionalResearchCompactSummary
    holdout_summary: CrossSectionalResearchCompactSummary
    provenance: CrossSectionalResearchArtifactProvenance

    @model_validator(mode="after")
    def validate_consumer_contract(self) -> "CrossSectionalResearchValidationResponse":
        if not self.would_persist_artifact_id.startswith("cross_sectional_research_artifact_"):
            raise ValueError("would_persist_artifact_id must use the stable cross_sectional_research_artifact_ prefix")
        if len(self.would_persist_fingerprint) != 64:
            raise ValueError("would_persist_fingerprint must be a full sha256 hex digest")
        if self.methodology_metadata_v1.active_methodology_id != self.normalized_request.methodology_id:
            raise ValueError(
                "methodology_metadata_v1.active_methodology_id must match normalized_request.methodology_id"
            )
        if self.status_metadata_v1.diagnostics_status != self.provenance.alpha_diagnostics_status:
            raise ValueError(
                "status_metadata_v1.diagnostics_status must match provenance.alpha_diagnostics_status"
            )
        if self.dataset_version != self.normalized_request.dataset_version:
            raise ValueError("dataset_version must match normalized_request.dataset_version")
        if self.universe_definition != self.normalized_request.universe_definition:
            raise ValueError("universe_definition must match normalized_request.universe_definition")
        if self.benchmark != self.normalized_request.benchmark:
            raise ValueError("benchmark must match normalized_request.benchmark")
        return self


class CrossSectionalResearchArtifact(BaseModel):
    schema_version: CrossSectionalResearchArtifactSchemaVersion = CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION
    artifact_kind: CrossSectionalResearchArtifactKind = CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND
    artifact_id: str
    fingerprint: str
    run_id: str
    persisted_at: str
    methodology_id: Literal["alpha_quality_v1"]
    request: CrossSectionalResearchRequest
    methodology: str
    methodology_metadata_v1: CrossSectionalResearchMethodologyMetadataV1
    status_metadata_v1: CrossSectionalResearchStatusMetadataV1
    provenance_metadata_v1: CrossSectionalResearchProvenanceMetadataV1
    assumptions: list[str] = Field(default_factory=list)
    dataset_version: str
    universe_definition: str
    benchmark: CrossSectionalResearchBenchmark
    walk_forward_summary: CrossSectionalResearchCompactSummary
    holdout_summary: CrossSectionalResearchCompactSummary
    provenance: CrossSectionalResearchArtifactProvenance

    @model_validator(mode="after")
    def validate_contract_consistency(self) -> "CrossSectionalResearchArtifact":
        if not self.artifact_id.startswith("cross_sectional_research_artifact_"):
            raise ValueError("artifact_id must use the stable cross_sectional_research_artifact_ prefix")
        if len(self.fingerprint) != 64:
            raise ValueError("fingerprint must be a full sha256 hex digest")
        _validate_canonical_utc_timestamp(self.persisted_at, "persisted_at")
        if self.request.methodology_id != self.methodology_id:
            raise ValueError("request.methodology_id must match methodology_id")
        if self.methodology_metadata_v1.active_methodology_id != self.methodology_id:
            raise ValueError("methodology_metadata_v1.active_methodology_id must match methodology_id")
        if self.methodology_metadata_v1.alpha_package_version != self.provenance.alpha_package_version:
            raise ValueError(
                "methodology_metadata_v1.alpha_package_version must match provenance.alpha_package_version"
            )
        if self.methodology_metadata_v1.alpha_input_contract_id != self.provenance.alpha_input_contract_id:
            raise ValueError(
                "methodology_metadata_v1.alpha_input_contract_id must match provenance.alpha_input_contract_id"
            )
        if self.status_metadata_v1.diagnostics_status != self.provenance.alpha_diagnostics_status:
            raise ValueError(
                "status_metadata_v1.diagnostics_status must match provenance.alpha_diagnostics_status"
            )
        expected_coverage_status: CrossSectionalResearchCoverageStatus = (
            "complete" if self.provenance.complete_coverage_ratio >= 1.0 else "partial"
        )
        if self.status_metadata_v1.coverage_status != expected_coverage_status:
            raise ValueError(
                "status_metadata_v1.coverage_status must match provenance.complete_coverage_ratio"
            )
        expected_input_source_kind: CrossSectionalResearchInputSourceKind
        if self.request.replay_id is not None:
            expected_input_source_kind = "replay_snapshot_input"
        elif self.request.source_name == "direct_snapshot_input":
            expected_input_source_kind = "direct_snapshot_input"
        else:
            expected_input_source_kind = "backend_owned_other"
        if self.provenance_metadata_v1.input_source_kind != expected_input_source_kind:
            raise ValueError(
                "provenance_metadata_v1.input_source_kind must match persisted request source inputs"
            )
        expected_replay_provenance_status: CrossSectionalResearchReplayProvenanceStatus = (
            "present" if self.request.replay_id is not None else "absent"
        )
        if self.provenance_metadata_v1.replay_provenance_status != expected_replay_provenance_status:
            raise ValueError(
                "provenance_metadata_v1.replay_provenance_status must match persisted request replay_id"
            )
        if self.provenance_metadata_v1.benchmark_source_kind != "request_benchmark_reference":
            raise ValueError(
                "provenance_metadata_v1.benchmark_source_kind must remain request_benchmark_reference"
            )
        if self.provenance_metadata_v1.alpha_source_kind != "optimizer_alpha_package":
            raise ValueError(
                "provenance_metadata_v1.alpha_source_kind must remain optimizer_alpha_package"
            )
        if self.provenance.source_name != self.request.source_name:
            raise ValueError("provenance.source_name must match request.source_name")
        if self.provenance.replay_id != self.request.replay_id:
            raise ValueError("provenance.replay_id must match request.replay_id")
        if self.walk_forward_summary.split_label != "walk_forward":
            raise ValueError("walk_forward_summary.split_label must be walk_forward")
        if self.holdout_summary.split_label != "holdout":
            raise ValueError("holdout_summary.split_label must be holdout")
        if self.walk_forward_summary.universe_size != len(self.request.universe_symbols):
            raise ValueError("walk_forward_summary.universe_size must match request.universe_symbols")
        if self.holdout_summary.universe_size != len(self.request.universe_symbols):
            raise ValueError("holdout_summary.universe_size must match request.universe_symbols")
        if self.methodology_metadata_v1.alpha_methodology_id != self.walk_forward_summary.provenance.alpha_methodology_id:
            raise ValueError(
                "methodology_metadata_v1.alpha_methodology_id must match walk_forward_summary.provenance.alpha_methodology_id"
            )
        if self.methodology_metadata_v1.alpha_methodology_id != self.holdout_summary.provenance.alpha_methodology_id:
            raise ValueError(
                "methodology_metadata_v1.alpha_methodology_id must match holdout_summary.provenance.alpha_methodology_id"
            )
        if self.dataset_version != self.request.dataset_version:
            raise ValueError("dataset_version must match request.dataset_version")
        if self.universe_definition != self.request.universe_definition:
            raise ValueError("universe_definition must match request.universe_definition")
        if self.benchmark != self.request.benchmark:
            raise ValueError("benchmark must match request.benchmark")
        for summary_name, summary in (
            ("walk_forward_summary", self.walk_forward_summary),
            ("holdout_summary", self.holdout_summary),
        ):
            if summary.provenance.alpha_package_id != self.provenance.alpha_package_id:
                raise ValueError(
                    f"{summary_name}.provenance.alpha_package_id must match provenance.alpha_package_id"
                )
            if summary.provenance.alpha_package_version != self.provenance.alpha_package_version:
                raise ValueError(
                    f"{summary_name}.provenance.alpha_package_version must match provenance.alpha_package_version"
                )
            if summary.provenance.input_digest != self.provenance.input_digest:
                raise ValueError(
                    f"{summary_name}.provenance.input_digest must match provenance.input_digest"
                )
            if summary.provenance.source_name != self.request.source_name:
                raise ValueError(f"{summary_name}.provenance.source_name must match request.source_name")
            if summary.provenance.as_of_date != self.request.as_of_date:
                raise ValueError(f"{summary_name}.provenance.as_of_date must match request.as_of_date")
            if summary.provenance.rebalance_date != self.request.rebalance_date:
                raise ValueError(
                    f"{summary_name}.provenance.rebalance_date must match request.rebalance_date"
                )
            if summary.provenance.holdout_start_date != self.request.holdout_start_date:
                raise ValueError(
                    f"{summary_name}.provenance.holdout_start_date must match request.holdout_start_date"
                )
            if summary.provenance.benchmark_symbol != self.request.benchmark.benchmark_symbol:
                raise ValueError(
                    f"{summary_name}.provenance.benchmark_symbol must match request.benchmark.benchmark_symbol"
                )
            if summary.provenance.benchmark_kind != self.request.benchmark.benchmark_kind:
                raise ValueError(
                    f"{summary_name}.provenance.benchmark_kind must match request.benchmark.benchmark_kind"
                )
        return self


class CrossSectionalResearchReloadResponse(BaseModel):
    contract_version: CrossSectionalResearchReloadContractVersion = (
        CROSS_SECTIONAL_RESEARCH_RELOAD_CONTRACT_VERSION
    )
    requested_artifact_id: str
    artifact_id: str
    artifact_kind: CrossSectionalResearchArtifactKind = CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND
    schema_version: CrossSectionalResearchArtifactSchemaVersion = (
        CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION
    )
    artifact: CrossSectionalResearchArtifact

    @model_validator(mode="after")
    def validate_identity_alignment(self) -> "CrossSectionalResearchReloadResponse":
        if self.requested_artifact_id != self.artifact_id:
            raise ValueError("requested_artifact_id must match artifact_id")
        if self.artifact.artifact_id != self.artifact_id:
            raise ValueError("artifact.artifact_id must match artifact_id")
        if self.artifact.artifact_kind != self.artifact_kind:
            raise ValueError("artifact.artifact_kind must match artifact_kind")
        if self.artifact.schema_version != self.schema_version:
            raise ValueError("artifact.schema_version must match schema_version")
        return self


class CrossSectionalResearchCatalogRow(BaseModel):
    artifact_id: str
    fingerprint: str
    artifact_kind: CrossSectionalResearchArtifactKind
    schema_version: CrossSectionalResearchArtifactSchemaVersion
    methodology_id: Literal["alpha_quality_v1"]
    methodology_metadata_v1: CrossSectionalResearchMethodologyMetadataV1
    status_metadata_v1: CrossSectionalResearchStatusMetadataV1
    provenance_metadata_v1: CrossSectionalResearchProvenanceMetadataV1
    dataset_version: str
    universe_definition: str
    benchmark_symbol: str
    as_of_date: str
    rebalance_date: str
    holdout_start_date: str
    recent_order_persisted_at: str
    recent_order_artifact_id: str
    universe_size: int = Field(ge=0)
    walk_forward_sample_count: int = Field(ge=0)
    holdout_sample_count: int = Field(ge=0)
    alpha_diagnostics_status: OptimizerAlphaPackageStatus

    @field_validator("dataset_version", "universe_definition")
    @classmethod
    def validate_required_strings(cls, value: str, info) -> str:
        return _validate_required_trimmed_string(value, info.field_name)

    @field_validator("benchmark_symbol")
    @classmethod
    def validate_benchmark_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != value or not normalized:
            raise ValueError("benchmark_symbol must be canonical uppercase without surrounding whitespace")
        return normalized

    @field_validator("as_of_date", "rebalance_date", "holdout_start_date")
    @classmethod
    def validate_canonical_dates(cls, value: str, info) -> str:
        return _validate_canonical_date_string(value, info.field_name)

    @model_validator(mode="after")
    def validate_recent_order_metadata(self) -> "CrossSectionalResearchCatalogRow":
        if self.artifact_kind != CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND:
            raise ValueError("unsupported cross-sectional research artifact kind")
        if self.schema_version != CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported cross-sectional research schema_version")
        _validate_canonical_utc_timestamp(self.recent_order_persisted_at, "recent_order_persisted_at")
        if self.recent_order_artifact_id != self.artifact_id:
            raise ValueError("recent_order_artifact_id must match artifact_id")
        if self.methodology_metadata_v1.active_methodology_id != self.methodology_id:
            raise ValueError("methodology_metadata_v1.active_methodology_id must match methodology_id")
        if self.status_metadata_v1.diagnostics_status != self.alpha_diagnostics_status:
            raise ValueError("status_metadata_v1.diagnostics_status must match alpha_diagnostics_status")
        return self


class CrossSectionalResearchRecentRow(BaseModel):
    artifact_id: str
    fingerprint: str
    methodology_id: Literal["alpha_quality_v1"]
    methodology_metadata_v1: CrossSectionalResearchMethodologyMetadataV1
    status_metadata_v1: CrossSectionalResearchStatusMetadataV1
    provenance_metadata_v1: CrossSectionalResearchProvenanceMetadataV1
    dataset_version: str
    universe_definition: str
    benchmark_symbol: str
    recent_order_persisted_at: str
    recent_order_artifact_id: str
    rebalance_date: str
    as_of_date: str
    holdout_start_date: str
    universe_size: int = Field(ge=0)
    walk_forward_sample_count: int = Field(ge=0)
    holdout_sample_count: int = Field(ge=0)

    @field_validator("dataset_version", "universe_definition")
    @classmethod
    def validate_required_strings(cls, value: str, info) -> str:
        return _validate_required_trimmed_string(value, info.field_name)

    @field_validator("benchmark_symbol")
    @classmethod
    def validate_benchmark_symbol(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != value or not normalized:
            raise ValueError("benchmark_symbol must be canonical uppercase without surrounding whitespace")
        return normalized

    @field_validator("rebalance_date", "as_of_date", "holdout_start_date")
    @classmethod
    def validate_canonical_dates(cls, value: str, info) -> str:
        return _validate_canonical_date_string(value, info.field_name)

    @model_validator(mode="after")
    def validate_recent_order_metadata(self) -> "CrossSectionalResearchRecentRow":
        _validate_canonical_utc_timestamp(self.recent_order_persisted_at, "recent_order_persisted_at")
        if self.recent_order_artifact_id != self.artifact_id:
            raise ValueError("recent_order_artifact_id must match artifact_id")
        if self.methodology_metadata_v1.active_methodology_id != self.methodology_id:
            raise ValueError("methodology_metadata_v1.active_methodology_id must match methodology_id")
        return self


class CrossSectionalResearchDiscoveryFilters(BaseModel):
    artifact_kind: CrossSectionalResearchArtifactKind | None = None
    schema_version: CrossSectionalResearchArtifactSchemaVersion | None = None
    methodology_id: Literal["alpha_quality_v1"] | None = None
    dataset_version: str | None = None
    universe_definition: str | None = None
    benchmark_symbol: str | None = None
    rebalance_date: str | None = None
    as_of_date: str | None = None
    holdout_start_date: str | None = None
    methodology_family_id: str | None = None
    methodology_family_version: str | None = None
    active_methodology_version: str | None = None
    alpha_package_version: str | None = None
    alpha_methodology_id: str | None = None
    alpha_input_contract_id: str | None = None
    score_basis: str | None = None
    benchmark_role: str | None = None
    partition_rule: str | None = None
    output_shape: str | None = None
    artifact_status: CrossSectionalResearchArtifactStatus | None = None
    diagnostics_status: OptimizerAlphaPackageStatus | Literal["unknown", "unsupported"] | None = None
    coverage_status: CrossSectionalResearchCoverageStatus | None = None
    input_source_kind: CrossSectionalResearchInputSourceKind | None = None
    replay_provenance_status: CrossSectionalResearchReplayProvenanceStatus | None = None
    benchmark_source_kind: CrossSectionalResearchBenchmarkSourceKind | None = None
    alpha_source_kind: CrossSectionalResearchAlphaSourceKind | None = None

    @field_validator("dataset_version", "universe_definition")
    @classmethod
    def validate_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("discovery filters must not contain blank string values")
        return normalized

    @field_validator("benchmark_symbol")
    @classmethod
    def validate_optional_benchmark_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if normalized != value:
            raise ValueError("benchmark_symbol must be canonical uppercase without surrounding whitespace")
        return normalized

    @field_validator("rebalance_date", "as_of_date", "holdout_start_date")
    @classmethod
    def validate_optional_canonical_dates(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        return _validate_canonical_date_string(value, info.field_name)

    @field_validator(
        "methodology_family_id",
        "methodology_family_version",
        "active_methodology_version",
        "alpha_package_version",
        "alpha_methodology_id",
        "alpha_input_contract_id",
        "score_basis",
        "benchmark_role",
        "partition_rule",
        "output_shape",
    )
    @classmethod
    def validate_optional_canonical_metadata_filters(cls, value: str | None, info) -> str | None:
        if value is None:
            return None
        expected_by_field = {
            "methodology_family_id": "cross_sectional_research_family_v1",
            "methodology_family_version": "v1",
            "active_methodology_version": "v1",
            "alpha_package_version": "alpha_quality_v1",
            "alpha_methodology_id": "alpha_quality_v1_methodology",
            "alpha_input_contract_id": "alpha_quality_v1_pit_fundamentals_v1",
            "score_basis": "optimizer_alpha_package.final_score",
            "benchmark_role": "descriptive_reference_only",
            "partition_rule": "effective_date_before_holdout_start_else_holdout",
            "output_shape": "compact_summary_only",
        }
        return _validate_canonical_exact_string(value, info.field_name, expected_by_field[info.field_name])


class CrossSectionalResearchDiscoveryMetadata(BaseModel):
    contract_version: CrossSectionalResearchDiscoveryContractVersion = (
        CROSS_SECTIONAL_RESEARCH_DISCOVERY_CONTRACT_VERSION
    )
    metadata_truth: Literal["authoritative_persisted_artifact_metadata"] = (
        "authoritative_persisted_artifact_metadata"
    )
    recent_order_basis: Literal["persisted_artifact.persisted_at_then_artifact_id"] = (
        "persisted_artifact.persisted_at_then_artifact_id"
    )
    supported_filters: list[CrossSectionalResearchDiscoveryFilterName] = Field(
        default_factory=lambda: list(SUPPORTED_CROSS_SECTIONAL_RESEARCH_DISCOVERY_FILTERS)
    )
    methodology_metadata_v1_semantics: Literal["descriptive_only"] = "descriptive_only"
    status_metadata_v1_semantics: Literal["descriptive_only"] = "descriptive_only"
    provenance_metadata_v1_semantics: Literal["descriptive_only"] = "descriptive_only"
    applied_filters: CrossSectionalResearchDiscoveryFilters = Field(
        default_factory=CrossSectionalResearchDiscoveryFilters
    )


class CrossSectionalResearchCatalogResponse(BaseModel):
    items: list[CrossSectionalResearchCatalogRow] = Field(default_factory=list)
    applied_filters: CrossSectionalResearchDiscoveryFilters = Field(
        default_factory=CrossSectionalResearchDiscoveryFilters
    )
    metadata: CrossSectionalResearchDiscoveryMetadata = Field(default_factory=CrossSectionalResearchDiscoveryMetadata)

    @model_validator(mode="after")
    def validate_filter_alignment(self) -> "CrossSectionalResearchCatalogResponse":
        if self.metadata.applied_filters != self.applied_filters:
            raise ValueError("metadata.applied_filters must match applied_filters")
        return self


class CrossSectionalResearchRecentResponse(BaseModel):
    items: list[CrossSectionalResearchRecentRow] = Field(default_factory=list)
    applied_filters: CrossSectionalResearchDiscoveryFilters = Field(
        default_factory=CrossSectionalResearchDiscoveryFilters
    )
    metadata: CrossSectionalResearchDiscoveryMetadata = Field(default_factory=CrossSectionalResearchDiscoveryMetadata)

    @model_validator(mode="after")
    def validate_filter_alignment(self) -> "CrossSectionalResearchRecentResponse":
        if self.metadata.applied_filters != self.applied_filters:
            raise ValueError("metadata.applied_filters must match applied_filters")
        return self
