"""Daily return distribution / VaR / CVaR engine schemas (Epic 13 — Risk tab).

Surfaces the daily return histogram, percentiles, historical Value-at-Risk
(95% / 99%), Conditional VaR (95% Expected Shortfall), and distribution
shape (mean / std / skew / excess kurtosis) for the synthetic portfolio.
All outputs are synthetic-history trust class.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest


DistributionTrustLevel = Literal["synthetic", "unavailable"]

# Lookback windows (trading days). NO None/"max" — VaR is interpretable
# only relative to a fixed lookback.
DistributionWindow = Literal[60, 252, 504]


class DistributionEngineRequest(PortfolioEngineRequest):
    """Distribution engine request. Inherits `positions`, `imported_at`, etc.
    from PortfolioEngineRequest.

    `window_trading_days` selects the lookback. Default 252 ≈ 1 year.
    """

    window_trading_days: DistributionWindow = 252


class HistogramBin(BaseModel):
    """One bin in the daily return histogram.

    `center` is the bin midpoint as a DECIMAL return (not percent) — the UI
    formatter multiplies by 100 for display.
    """

    center: float
    count: int


class DistributionEngineResponse(BaseModel):
    """Wrapper. `trust='unavailable'` => every scalar None,
    `return_count == 0`, `histogram_bins == []`.

    All percent fields are reported as percent units (multiplied by 100).
    `var_*` and `cvar_*` are sign-flipped: a positive number is a loss.
    A NEGATIVE VaR means "the tail day at the requested confidence was
    still positive" — surfaced as-is, never clipped (methodology
    Contract rule).
    """

    window_trading_days: int
    return_count: int
    var_95: float | None
    var_99: float | None
    cvar_95: float | None
    percentile_5: float | None
    percentile_10: float | None
    percentile_50: float | None
    percentile_90: float | None
    percentile_95: float | None
    mean_pct: float | None
    std_pct: float | None
    skewness: float | None
    kurtosis_excess: float | None
    histogram_bins: list[HistogramBin]
    trust: DistributionTrustLevel
