from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import SyntheticHistoryCoverage


class FactorAttributionRequest(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    window: Literal[20, 60, 252] = 60
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL


class FactorContributionPoint(BaseModel):
    """Cumulative contribution for one factor at one date (decimal, not pct)."""
    factor_key: str
    cumul_contribution: float | None = None


class AttributionSeriesEntry(BaseModel):
    """One entry in the cumulative attribution time series."""
    date: str
    contributions: list[FactorContributionPoint] = Field(default_factory=list)
    cumul_unexplained: float | None = None
    cumul_portfolio_return: float | None = None


class FactorPeriodRow(BaseModel):
    """One row in the period attribution table."""
    factor_key: str
    factor_label: str
    avg_beta: float | None = None
    factor_return_pct: float | None = None     # Σ f*_k(t) × 100 over period
    contribution_pct: float | None = None      # Σ β̂_k × f*_k(t) × 100 over period


class FactorAttributionResponse(BaseModel):
    attribution_status: Literal["available", "unavailable"]
    window: int
    cumulative_series: list[AttributionSeriesEntry] = Field(default_factory=list)
    period_attribution: list[FactorPeriodRow] = Field(default_factory=list)
    total_portfolio_return_pct: float | None = None
    total_unexplained_pct: float | None = None
    methodology_note: str
    # US-27.7: synthetic-history coverage disclosure (effective window /
    # excluded holdings). None only on pre-coverage error paths.
    coverage: SyntheticHistoryCoverage | None = None