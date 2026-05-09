from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, model_validator

# ── Constants ────────────────────────────────────────────────────────────────

GENERIC_RANKING_ARTIFACT_KIND = "generic_ranking"
GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION = "generic_ranking_artifact_v1"
GENERIC_RANKING_ARTIFACT_ID_PREFIX = "generic_ranking_artifact_"

GenericRankingArtifactSchemaVersion = Literal["generic_ranking_artifact_v1"]

UniverseKind = Literal[
    "etf_peer_group",       # explicit list, ETF peer group
    "custom_list",          # explicit list, any instruments
    "broad_equity_screen",  # FMP screener: exchange + cap + ADV filters
    "sector_screen",        # broad_equity_screen + sector include/exclude
    "index_constituent",    # FMP index endpoint (sp500); resolved to current snapshot
]

# Supported index identifiers for universe_kind="index_constituent".
IndexId = Literal["sp500"]

FactorFamily = Literal["momentum", "volatility", "liquidity", "quality", "value", "sentiment"]
NormalizationMethod = Literal["cross_sectional_zscore", "percentile_rank", "minmax"]

# ── Universe spec ─────────────────────────────────────────────────────────────

class UniverseSpec(BaseModel):
    universe_id: str                          # e.g. "broad_us_equity", "tech_sector", "custom"
    universe_kind: UniverseKind
    universe_label: str | None = None
    # Explicit membership (required for etf_peer_group and custom_list)
    explicit_symbols: list[str] = Field(default_factory=list)
    # Screener eligibility filters (for broad_equity_screen and sector_screen)
    min_market_cap_usd: float | None = None   # e.g. 300_000_000
    min_adv_usd: float | None = None          # average daily dollar volume floor
    price_floor_usd: float | None = None      # e.g. 1.0
    allowed_exchanges: list[str] = Field(default_factory=lambda: ["NASDAQ", "NYSE", "NYSE AMERICAN"])
    sector_include: list[str] = Field(default_factory=list)   # GICS sectors to keep (sector_screen)
    sector_exclude: list[str] = Field(default_factory=list)   # GICS sectors to drop
    country_iso2: list[str] = Field(default_factory=lambda: ["US"])
    exclude_etf: bool = True
    exclude_adr: bool = True
    # Required for universe_kind="index_constituent"; identifies which index members to fetch.
    index_id: IndexId | None = None

    @model_validator(mode="after")
    def _validate_kind_requirements(self) -> "UniverseSpec":
        if self.universe_kind in ("etf_peer_group", "custom_list") and not self.explicit_symbols:
            raise ValueError(f"universe_kind={self.universe_kind!r} requires explicit_symbols")
        if self.universe_kind == "index_constituent" and self.index_id is None:
            raise ValueError("universe_kind='index_constituent' requires index_id")
        return self


class UniverseSpecSnapshot(BaseModel):
    """Resolved universe state captured at run-time, stored in the artifact."""
    spec_version: str = "universe_spec_v1"
    universe_id: str
    universe_kind: str
    spec_digest: str                          # sha256 of canonical UniverseSpec JSON
    evaluated_members: list[str]              # resolved, sorted symbol list as of as_of_date
    evaluated_at: str                         # ISO date


# ── Score config ──────────────────────────────────────────────────────────────

class FactorConfig(BaseModel):
    factor_id: str                            # "momentum_6_1", "realized_volatility_126d", etc.
    family: FactorFamily
    direction: Literal["higher_is_better", "lower_is_better"]
    weight: float = Field(ge=0.0)
    lookback_days: int | None = None          # for price-based factors
    raw_unit: str = "score"                   # "pct", "volume", "score"


class ScoreConfig(BaseModel):
    score_config_id: str                      # "equity_momentum_v1", "etf_momentum_v1"
    score_config_version: str = "v1"
    normalization: NormalizationMethod = "cross_sectional_zscore"
    winsorize_pct: float = Field(0.05, ge=0.0, le=0.5)
    factors: list[FactorConfig]

    @model_validator(mode="after")
    def _validate_weights(self) -> "ScoreConfig":
        total = sum(f.weight for f in self.factors)
        if total <= 0:
            raise ValueError("factor weights must sum to a positive value")
        return self

    def normalized_weights(self) -> dict[str, float]:
        total = sum(f.weight for f in self.factors)
        return {f.factor_id: f.weight / total for f in self.factors}


class ScoreConfigRef(BaseModel):
    """Compact reference stored in the artifact's run_metadata."""
    score_config_id: str
    score_config_version: str
    score_config_digest: str                  # sha256 of canonical ScoreConfig JSON
    factor_ids: list[str]
    normalization: str
    winsorize_pct: float


# ── Per-instrument models ─────────────────────────────────────────────────────

class GenericRankingComponentScore(BaseModel):
    label: str
    family: FactorFamily
    direction: Literal["higher_is_better", "lower_is_better"]
    raw_value: float | None
    raw_unit: str
    normalized_score: float | None
    normalization_method: str
    weight: float
    weighted_score: float | None


class EligibilityRecord(BaseModel):
    eligibility_status: Literal["eligible", "excluded"]
    hard_filter_failures: list[str] = Field(default_factory=list)   # filter names that failed
    soft_filter_flags: list[str] = Field(default_factory=list)


class GenericRankingRow(BaseModel):
    rank: int
    symbol: str
    composite_score: float
    component_scores: dict[str, GenericRankingComponentScore]
    eligibility: EligibilityRecord


class GenericRankingExcludedInstrument(BaseModel):
    symbol: str
    eligibility: EligibilityRecord


# ── Run metadata ─────────────────────────────────────────────────────────────

class CompositeScoreTrace(BaseModel):
    normalization_method: str
    winsorize_pct: float
    universe_size_at_normalization: int
    cross_sectional_mean: dict[str, float]    # per-factor means
    cross_sectional_std: dict[str, float]     # per-factor stds


class GenericRankingRunMetadata(BaseModel):
    ranking_id: str
    methodology_id: str
    as_of_date: str
    ranking_basis_date: str
    price_basis: str
    confidence: Literal["full", "partial", "degraded"]
    score_config_ref: ScoreConfigRef
    composite_score_trace: CompositeScoreTrace | None = None


# ── Request / Response / Artifact ────────────────────────────────────────────

class GenericRankingRequest(BaseModel):
    universe_spec: UniverseSpec
    score_config: ScoreConfig
    benchmark_symbol: str = "SPY"
    lookback_months: int = Field(6, ge=1, le=60)
    prefer_live_data: bool = False


class GenericRankingResponse(BaseModel):
    ranking_id: str
    methodology_id: str
    title: str
    as_of_date: str
    benchmark_symbol: str
    lookback_months: int
    universe_spec_snapshot: UniverseSpecSnapshot
    run_metadata: GenericRankingRunMetadata
    ranked_universe: list[GenericRankingRow]
    excluded_instruments: list[GenericRankingExcludedInstrument]
    warnings: list[str] = Field(default_factory=list)


class GenericRankingArtifact(GenericRankingResponse):
    schema_version: GenericRankingArtifactSchemaVersion = GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION
    artifact_id: str

    @model_validator(mode="after")
    def _validate_artifact_id(self) -> "GenericRankingArtifact":
        if not self.artifact_id.startswith(GENERIC_RANKING_ARTIFACT_ID_PREFIX):
            raise ValueError(f"artifact_id must start with '{GENERIC_RANKING_ARTIFACT_ID_PREFIX}'")
        return self


class GenericRankingArtifactRecentRow(BaseModel):
    artifact_id: str
    ranking_id: str
    methodology_id: str
    as_of_date: str
    ranking_basis_date: str
    benchmark_symbol: str
    lookback_months: int
    universe_id: str
    universe_kind: str
    score_config_id: str
    evaluated_universe_size: int
    confidence: str
