from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.schemas.research import EtfMomentumStrategyResponse, EtfRankingArtifact, EtfRankingArtifactRecentMetadata, EtfRankingArtifactRecentRow, EtfRankingRequest, IntentBoundEtfReplacementRankingRequest, IntentBoundEtfReplacementRankingResponse
from app.services.market_data import MarketDataService
from app.services.etf_ranking_artifact_service import (
    EtfRankingArtifactIntegrityValidationError,
    EtfRankingArtifactInvalidJsonError,
    EtfRankingArtifactMissingFileError,
    EtfRankingArtifactNonObjectPayloadError,
    EtfRankingArtifactPersistenceError,
    EtfRankingArtifactSchemaValidationError,
    get_recent_etf_ranking_artifact_metadata,
    list_recent_etf_ranking_artifacts,
    load_etf_ranking_artifact,
    persist_etf_ranking_artifact,
)
from app.services.replacement_ranking import build_intent_bound_etf_replacement_ranking
from app.services.strategy_lab import DEFAULT_ETF_ROTATION_BENCHMARK, DEFAULT_ETF_ROTATION_UNIVERSE, build_etf_momentum_strategy_analysis, build_etf_ranking_analysis


router = APIRouter(tags=["strategy-lab"])


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
def run_intent_bound_etf_replacement_ranking(request: IntentBoundEtfReplacementRankingRequest) -> IntentBoundEtfReplacementRankingResponse:
    try:
        return build_intent_bound_etf_replacement_ranking(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
