from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ValidationError

from app.schemas.ranking import (
    RankingArtifactConfidence,
    RankingArtifactMetadataProvenance,
    RankingArtifactMetadataTruth,
    RankingArtifactRecencySameDayProvenance,
)
from app.schemas.research import (
    EtfMomentumStrategyResponse,
    EtfRankingArtifact,
    EtfRankingArtifactRecentMetadata,
    EtfRankingArtifactRecentRow,
    EtfRankingRequest,
    IntentBoundEtfReplacementRankingArtifact,
    IntentBoundEtfReplacementRankingRequest,
    IntentBoundEtfReplacementRankingResponse,
    RankingArtifactCatalogListResponse,
    RankingArtifactDiscoveryFilters,
)
from app.services.market_data import MarketDataService
from app.services.etf_ranking_artifact_service import (
    EtfRankingArtifactIntegrityValidationError,
    EtfRankingArtifactInvalidJsonError,
    EtfRankingArtifactMissingFileError,
    EtfRankingArtifactNonObjectPayloadError,
    EtfRankingArtifactPersistenceError,
    EtfRankingArtifactRecentIndexInvalidJsonError,
    EtfRankingArtifactRecentIndexNonObjectPayloadError,
    EtfRankingArtifactRecentIndexSchemaValidationError,
    EtfRankingArtifactSchemaValidationError,
    get_recent_etf_ranking_artifact_metadata,
    list_recent_etf_ranking_artifacts,
    load_etf_ranking_artifact,
    persist_etf_ranking_artifact,
)
from app.services.ranking_artifact_catalog_service import (
    RankingArtifactCatalogMalformedMetadataError,
    RankingArtifactCatalogServiceError,
    RankingArtifactCatalogUnsupportedStateError,
    list_ranking_artifact_catalog,
    list_recent_ranking_artifacts,
)
from app.services.replacement_ranking import build_intent_bound_etf_replacement_ranking
from app.services.replacement_ranking_artifact_service import (
    ReplacementRankingArtifactIntegrityValidationError,
    ReplacementRankingArtifactInvalidJsonError,
    ReplacementRankingArtifactMissingFileError,
    ReplacementRankingArtifactNonObjectPayloadError,
    ReplacementRankingArtifactPersistenceError,
    ReplacementRankingArtifactSchemaValidationError,
    build_legacy_replacement_ranking_response,
    load_replacement_ranking_artifact,
    persist_replacement_ranking_artifact,
)
from app.services.strategy_lab import (
    DEFAULT_ETF_ROTATION_BENCHMARK,
    DEFAULT_ETF_ROTATION_UNIVERSE,
    build_etf_momentum_strategy_analysis,
    build_etf_ranking_analysis,
)


router = APIRouter(tags=["strategy-lab"])


def _build_ranking_artifact_discovery_filters(
    *,
    artifact_kind: str | None,
    schema_version: str | None,
    metadata_truth: RankingArtifactMetadataTruth | None,
    metadata_provenance: RankingArtifactMetadataProvenance | None,
    recency_same_day_provenance: RankingArtifactRecencySameDayProvenance | None,
    methodology_id: str | None,
    benchmark_symbol: str | None,
    effective_peer_group: str | None,
    base_symbol: str | None,
    candidate_symbol: str | None,
    peer_group: str | None,
    confidence: RankingArtifactConfidence | None,
    status: Literal["ok", "unavailable"] | None,
    as_of_date: str | None,
    ranking_basis_date: str | None,
    basis_date: str | None,
) -> RankingArtifactDiscoveryFilters:
    try:
        return RankingArtifactDiscoveryFilters(
            artifact_kind=artifact_kind,
            schema_version=schema_version,
            metadata_truth=metadata_truth,
            metadata_provenance=metadata_provenance,
            recency_same_day_provenance=recency_same_day_provenance,
            methodology_id=methodology_id,
            benchmark_symbol=benchmark_symbol,
            effective_peer_group=effective_peer_group,
            base_symbol=base_symbol,
            candidate_symbol=candidate_symbol,
            peer_group=peer_group,
            confidence=confidence,
            status=status,
            as_of_date=as_of_date,
            ranking_basis_date=ranking_basis_date,
            basis_date=basis_date,
        )
    except ValidationError as exc:
        detail = exc.errors()[0].get("msg", "invalid ranking artifact discovery filters") if exc.errors() else (
            "invalid ranking artifact discovery filters"
        )
        if isinstance(detail, str) and detail.startswith("Value error, "):
            detail = detail[len("Value error, ") :]
        raise HTTPException(status_code=400, detail=detail) from exc


class EtfMomentumRequest(BaseModel):
    universe: list[str] = Field(default_factory=lambda: DEFAULT_ETF_ROTATION_UNIVERSE.copy())
    benchmark_symbol: str = DEFAULT_ETF_ROTATION_BENCHMARK
    lookback_months: int = 3
    top_n: int = 3
    prefer_live_data: bool = False


class HoldingsRefreshRequest(BaseModel):
    symbols: list[str] = Field(default_factory=lambda: DEFAULT_ETF_ROTATION_UNIVERSE.copy())


class HoldingsRefreshResponse(BaseModel):
    refreshed: list[dict[str, int | str | None]] = Field(default_factory=list)


@router.post("/strategy-lab/etf-ranking", response_model=EtfRankingArtifact)
def run_etf_ranking(request: EtfRankingRequest) -> EtfRankingArtifact:
    if request.lookback_months < 1:
        raise HTTPException(status_code=400, detail="lookback_months must be at least 1")
    if not request.universe:
        raise HTTPException(status_code=400, detail="universe must include at least one symbol")

    try:
        ranking = build_etf_ranking_analysis(
            universe=request.universe,
            benchmark_symbol=request.benchmark_symbol,
            lookback_months=request.lookback_months,
            prefer_live_data=request.prefer_live_data,
            peer_group=request.peer_group,
            weights=request.weights,
        )
        return persist_etf_ranking_artifact(ranking)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/strategy-lab/etf-ranking/artifacts/recent", response_model=list[EtfRankingArtifactRecentRow])
def get_recent_etf_ranking_artifacts(
    limit: int = Query(20, ge=1, le=100),
    effective_peer_group: str | None = Query(None),
) -> list[EtfRankingArtifactRecentRow]:
    return list_recent_etf_ranking_artifacts(limit=limit, effective_peer_group=effective_peer_group)


@router.get("/strategy-lab/etf-ranking/artifacts/recent/metadata", response_model=EtfRankingArtifactRecentMetadata)
def get_recent_etf_ranking_artifact_filters_metadata() -> EtfRankingArtifactRecentMetadata:
    return get_recent_etf_ranking_artifact_metadata()


@router.get("/strategy-lab/etf-ranking/artifacts/{artifact_id}", response_model=EtfRankingArtifact)
def get_etf_ranking_artifact(artifact_id: str) -> EtfRankingArtifact:
    try:
        return load_etf_ranking_artifact(artifact_id)
    except EtfRankingArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        EtfRankingArtifactInvalidJsonError,
        EtfRankingArtifactNonObjectPayloadError,
        EtfRankingArtifactSchemaValidationError,
        EtfRankingArtifactIntegrityValidationError,
        EtfRankingArtifactPersistenceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/strategy-lab/ranking-artifacts/catalog", response_model=RankingArtifactCatalogListResponse)
def get_ranking_artifact_catalog(
    artifact_kind: str | None = Query(None),
    schema_version: str | None = Query(None),
    metadata_truth: RankingArtifactMetadataTruth | None = Query(None),
    metadata_provenance: RankingArtifactMetadataProvenance | None = Query(None),
    recency_same_day_provenance: RankingArtifactRecencySameDayProvenance | None = Query(None),
    methodology_id: str | None = Query(None),
    benchmark_symbol: str | None = Query(None),
    effective_peer_group: str | None = Query(None),
    base_symbol: str | None = Query(None),
    candidate_symbol: str | None = Query(None),
    peer_group: str | None = Query(None),
    confidence: RankingArtifactConfidence | None = Query(None),
    status: Literal["ok", "unavailable"] | None = Query(None),
    as_of_date: str | None = Query(None),
    ranking_basis_date: str | None = Query(None),
    basis_date: str | None = Query(None),
) -> RankingArtifactCatalogListResponse:
    try:
        return list_ranking_artifact_catalog(
            filters=_build_ranking_artifact_discovery_filters(
                artifact_kind=artifact_kind,
                schema_version=schema_version,
                metadata_truth=metadata_truth,
                metadata_provenance=metadata_provenance,
                recency_same_day_provenance=recency_same_day_provenance,
                methodology_id=methodology_id,
                benchmark_symbol=benchmark_symbol,
                effective_peer_group=effective_peer_group,
                base_symbol=base_symbol,
                candidate_symbol=candidate_symbol,
                peer_group=peer_group,
                confidence=confidence,
                status=status,
                as_of_date=as_of_date,
                ranking_basis_date=ranking_basis_date,
                basis_date=basis_date,
            )
        )
    except (
        RankingArtifactCatalogMalformedMetadataError,
        RankingArtifactCatalogUnsupportedStateError,
        RankingArtifactCatalogServiceError,
        EtfRankingArtifactInvalidJsonError,
        EtfRankingArtifactNonObjectPayloadError,
        EtfRankingArtifactRecentIndexInvalidJsonError,
        EtfRankingArtifactRecentIndexNonObjectPayloadError,
        EtfRankingArtifactRecentIndexSchemaValidationError,
        EtfRankingArtifactSchemaValidationError,
        EtfRankingArtifactIntegrityValidationError,
        EtfRankingArtifactPersistenceError,
        ReplacementRankingArtifactInvalidJsonError,
        ReplacementRankingArtifactNonObjectPayloadError,
        ReplacementRankingArtifactSchemaValidationError,
        ReplacementRankingArtifactIntegrityValidationError,
        ReplacementRankingArtifactPersistenceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/strategy-lab/ranking-artifacts/recent", response_model=RankingArtifactCatalogListResponse)
def get_recent_ranking_artifact_catalog(
    limit: int = Query(20, ge=1, le=100),
    artifact_kind: str | None = Query(None),
    schema_version: str | None = Query(None),
    metadata_truth: RankingArtifactMetadataTruth | None = Query(None),
    metadata_provenance: RankingArtifactMetadataProvenance | None = Query(None),
    recency_same_day_provenance: RankingArtifactRecencySameDayProvenance | None = Query(None),
    methodology_id: str | None = Query(None),
    benchmark_symbol: str | None = Query(None),
    effective_peer_group: str | None = Query(None),
    base_symbol: str | None = Query(None),
    candidate_symbol: str | None = Query(None),
    peer_group: str | None = Query(None),
    confidence: RankingArtifactConfidence | None = Query(None),
    status: Literal["ok", "unavailable"] | None = Query(None),
    as_of_date: str | None = Query(None),
    ranking_basis_date: str | None = Query(None),
    basis_date: str | None = Query(None),
) -> RankingArtifactCatalogListResponse:
    try:
        return list_recent_ranking_artifacts(
            limit=limit,
            filters=_build_ranking_artifact_discovery_filters(
                artifact_kind=artifact_kind,
                schema_version=schema_version,
                metadata_truth=metadata_truth,
                metadata_provenance=metadata_provenance,
                recency_same_day_provenance=recency_same_day_provenance,
                methodology_id=methodology_id,
                benchmark_symbol=benchmark_symbol,
                effective_peer_group=effective_peer_group,
                base_symbol=base_symbol,
                candidate_symbol=candidate_symbol,
                peer_group=peer_group,
                confidence=confidence,
                status=status,
                as_of_date=as_of_date,
                ranking_basis_date=ranking_basis_date,
                basis_date=basis_date,
            ),
        )
    except (
        RankingArtifactCatalogMalformedMetadataError,
        RankingArtifactCatalogUnsupportedStateError,
        RankingArtifactCatalogServiceError,
        EtfRankingArtifactMissingFileError,
        EtfRankingArtifactInvalidJsonError,
        EtfRankingArtifactNonObjectPayloadError,
        EtfRankingArtifactRecentIndexInvalidJsonError,
        EtfRankingArtifactRecentIndexNonObjectPayloadError,
        EtfRankingArtifactRecentIndexSchemaValidationError,
        EtfRankingArtifactSchemaValidationError,
        EtfRankingArtifactIntegrityValidationError,
        EtfRankingArtifactPersistenceError,
        ReplacementRankingArtifactMissingFileError,
        ReplacementRankingArtifactInvalidJsonError,
        ReplacementRankingArtifactNonObjectPayloadError,
        ReplacementRankingArtifactSchemaValidationError,
        ReplacementRankingArtifactIntegrityValidationError,
        ReplacementRankingArtifactPersistenceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/strategy-lab/etf-cross-sectional-momentum", response_model=EtfMomentumStrategyResponse)
def run_etf_cross_sectional_momentum(request: EtfMomentumRequest) -> EtfMomentumStrategyResponse:
    if request.lookback_months < 1:
        raise HTTPException(status_code=400, detail="lookback_months must be at least 1")
    if request.top_n < 1:
        raise HTTPException(status_code=400, detail="top_n must be at least 1")
    if request.top_n > len(request.universe):
        raise HTTPException(status_code=400, detail="top_n must be less than or equal to universe size")

    try:
        return build_etf_momentum_strategy_analysis(
            universe=request.universe,
            benchmark_symbol=request.benchmark_symbol,
            lookback_months=request.lookback_months,
            top_n=request.top_n,
            prefer_live_data=request.prefer_live_data,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/strategy-lab/holdings/refresh", response_model=HoldingsRefreshResponse)
def refresh_strategy_lab_holdings(request: HoldingsRefreshRequest) -> HoldingsRefreshResponse:
    service = MarketDataService()
    refreshed: list[dict[str, int | str | None]] = []
    for symbol in request.symbols:
        resolved_symbol, rows = service.refresh_etf_holdings_snapshot(symbol)
        refreshed.append(
            {
                "symbol": symbol.upper(),
                "resolved_symbol": resolved_symbol,
                "rows": len(rows),
                "snapshots": service.holdings_history.get_snapshot_count(symbol),
            }
        )
    return HoldingsRefreshResponse(refreshed=refreshed)


@router.post("/ranking/etf-replacements", response_model=IntentBoundEtfReplacementRankingResponse)
def run_legacy_intent_bound_etf_replacement_ranking(
    request: IntentBoundEtfReplacementRankingRequest,
) -> IntentBoundEtfReplacementRankingResponse:
    try:
        ranking = build_intent_bound_etf_replacement_ranking(request)
        artifact = persist_replacement_ranking_artifact(ranking)
        return build_legacy_replacement_ranking_response(artifact)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/strategy-lab/etf-ranking/replacements", response_model=IntentBoundEtfReplacementRankingArtifact)
def run_intent_bound_etf_replacement_ranking(
    request: IntentBoundEtfReplacementRankingRequest,
) -> IntentBoundEtfReplacementRankingArtifact:
    try:
        ranking = build_intent_bound_etf_replacement_ranking(request)
        return persist_replacement_ranking_artifact(ranking)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/ranking/etf-replacements/artifacts/{artifact_id}",
    response_model=IntentBoundEtfReplacementRankingArtifact,
)
@router.get(
    "/strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}",
    response_model=IntentBoundEtfReplacementRankingArtifact,
)
def get_intent_bound_etf_replacement_ranking_artifact(artifact_id: str) -> IntentBoundEtfReplacementRankingArtifact:
    try:
        return load_replacement_ranking_artifact(artifact_id)
    except ReplacementRankingArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ReplacementRankingArtifactInvalidJsonError,
        ReplacementRankingArtifactNonObjectPayloadError,
        ReplacementRankingArtifactSchemaValidationError,
        ReplacementRankingArtifactIntegrityValidationError,
        ReplacementRankingArtifactPersistenceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
