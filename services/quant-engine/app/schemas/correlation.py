"""Pydantic schemas for the multi-benchmark correlation engine."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.imports import ImportedPortfolioSnapshot


class MultiBenchmarkCorrelationRequest(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    lookback_days: int = Field(default=252, ge=1)


class BenchmarkStats(BaseModel):
    """Correlation statistics for one benchmark over the requested lookback window."""
    symbol: str
    label: str
    correlation: float | None = None
    beta: float | None = None
    r_squared: float | None = None
    trust: Literal["synthetic", "unavailable"]


class MultiBenchmarkCorrelationResult(BaseModel):
    benchmarks: list[BenchmarkStats]
    lookback_days: int
