"""Drawdown analytics engine schemas (Epic 13 — Risk tab).

Surfaces the underwater curve and top-N drawdown episodes for the
synthetic portfolio history. All outputs are synthetic-history trust
class: current holdings × historical prices.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest


DrawdownTrustLevel = Literal["synthetic", "unavailable"]

# Supported lookback windows (trading days). None = use the maximum available
# history capped by the engine's _MAX_LOOKBACK_CALENDAR_DAYS constant.
DrawdownWindow = Literal[252, 756, 1260]


class DrawdownEngineRequest(PortfolioEngineRequest):
    """Drawdown engine request. Inherits `positions`, `imported_at`, etc.
    from PortfolioEngineRequest.

    `window_trading_days` selects how much history to fetch:
      - 252  ≈ 1 year
      - 756  ≈ 3 years
      - 1260 ≈ 5 years
      - None = maximum available (engine-capped at ~8 years)
    """

    window_trading_days: DrawdownWindow | None = None


class DrawdownDailyPoint(BaseModel):
    """One point on the underwater curve.

    `drawdown_pct` is signed percentage from peak:
       0.0   → at all-time high
      -12.5  → 12.5 % below all-time high
    """

    date: str
    drawdown_pct: float | None = None


class DrawdownEpisode(BaseModel):
    """One drawdown episode (peak → trough → optional recovery).

    `recovery_date` is null when the portfolio is still under water at the
    end of the series — the UI must surface this distinctly from "no episode"
    (per methodology Contract rule).
    """

    peak_date: str
    trough_date: str
    recovery_date: str | None = None
    magnitude_pct: float       # always ≤ 0; "deepest" = most negative
    duration_days: int         # trough_date - peak_date (calendar days)
    underwater_days: int       # (recovery_date or last_date) - peak_date


class DrawdownEngineResponse(BaseModel):
    """Wrapper. `trust='unavailable'` => every scalar None + lists empty."""

    window_trading_days: int | None
    underwater_series: list[DrawdownDailyPoint]
    current_drawdown_pct: float | None
    max_drawdown_pct: float | None
    episodes: list[DrawdownEpisode]
    trust: DrawdownTrustLevel
