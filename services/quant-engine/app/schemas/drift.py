from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest


DriftTrustLevel = Literal["synthetic", "unavailable"]


class DriftWindow(BaseModel):
    label: str  # "1M", "3M", "6M", "12M", "Since Import"
    start_date: str | None = None
    end_date: str | None = None
    portfolio_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    spread_pct: float | None = None  # portfolio - benchmark
    trust: DriftTrustLevel = "unavailable"
    note: str | None = None


class DriftDailyPoint(BaseModel):
    date: str
    portfolio_indexed: float | None = None   # indexed to 100.0 at series start
    benchmark_indexed: float | None = None


class DriftEngineRequest(PortfolioEngineRequest):
    pass  # benchmark_symbol (default "SPY") and imported_at already in PortfolioEngineRequest


class DriftResult(BaseModel):
    windows: list[DriftWindow]
    benchmark_symbol: str
    daily_series: list[DriftDailyPoint]
    availability: Literal["available", "partial", "unavailable"]
