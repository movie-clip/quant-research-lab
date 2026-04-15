from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.schemas.research import EtfMomentumStrategyResponse, EtfRankingRequest, EtfRankingResponse
from app.services.market_data import MarketDataService
from app.services.strategy_lab import DEFAULT_ETF_ROTATION_BENCHMARK, DEFAULT_ETF_ROTATION_UNIVERSE, build_etf_momentum_strategy_analysis, build_etf_ranking_analysis


router = APIRouter(prefix="/strategy-lab", tags=["strategy-lab"])


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


@router.post("/etf-ranking", response_model=EtfRankingResponse)
def run_etf_ranking(request: EtfRankingRequest) -> EtfRankingResponse:
    if request.lookback_months < 1:
        raise HTTPException(status_code=400, detail="lookback_months must be at least 1")
    if not request.universe:
        raise HTTPException(status_code=400, detail="universe must include at least one symbol")

    try:
        return build_etf_ranking_analysis(
            universe=request.universe,
            benchmark_symbol=request.benchmark_symbol,
            lookback_months=request.lookback_months,
            prefer_live_data=request.prefer_live_data,
            weights=request.weights,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/etf-cross-sectional-momentum", response_model=EtfMomentumStrategyResponse)
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


@router.post("/holdings/refresh", response_model=HoldingsRefreshResponse)
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
