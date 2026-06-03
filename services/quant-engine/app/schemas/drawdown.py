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

# Per-episode decomposition trust (Epic 15 / US-15.1). Distinct from the
# wrapper-level DrawdownTrustLevel because a decomposition can be 'partial'
# (some positions have data, others don't) while the overall response is
# still 'synthetic'.
DrawdownDecompositionTrust = Literal["synthetic", "partial", "unavailable"]

# Supported lookback windows (trading days). None = use the maximum available
# history capped by the engine's _MAX_LOOKBACK_CALENDAR_DAYS constant.
DrawdownWindow = Literal[252, 756, 1260]


class EpisodeContributor(BaseModel):
    """One position's contribution to a drawdown episode (Epic 15 / US-15.1).

    Methodology: see §Drawdown episode decomposition in
    financial-methodology.md. `contribution_pct = weight_at_peak × return × 100`
    under arithmetic Brinson-style attribution.

    All percent fields are in percent units (already × 100). `contribution_pct`
    is signed: negative means the position dragged the portfolio down during
    the episode; positive means the position rallied while the portfolio
    overall sank.
    """

    symbol: str
    weight_at_peak_pct: float | None = None
    return_pct: float | None = None
    contribution_pct: float | None = None
    # Per-row trust. 'synthetic' when all three pcts are non-null;
    # 'unavailable' when any of them is null (missing price at peak or trough).
    trust: Literal["synthetic", "unavailable"] = "unavailable"


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

    Per-position decomposition fields (Epic 15 / US-15.1) are nullable
    defaults so episodes constructed without decomposition (e.g. by older
    tests) remain valid. `decomposition_trust='unavailable'` is the
    fail-closed default when the engine can't decompose.
    """

    peak_date: str
    trough_date: str
    recovery_date: str | None = None
    magnitude_pct: float       # always ≤ 0; "deepest" = most negative
    duration_days: int         # trough_date - peak_date (calendar days)
    underwater_days: int       # (recovery_date or last_date) - peak_date

    # ── Per-position decomposition (Epic 15 / US-15.1) ────────────────────
    # Top-N contributors sorted by abs(contribution_pct) descending.
    top_contributors: list[EpisodeContributor] | None = None
    # Aggregated contribution of positions ranked N+1 and beyond. None when
    # decomposition wasn't run OR when there are ≤ top_n positions.
    other_contribution_pct: float | None = None
    # Unexplained share: magnitude_pct − Σ non-null contribution_pct.
    # Near zero under 'synthetic' trust; material under 'partial' when some
    # positions had missing prices.
    decomposition_residual_pct: float | None = None
    # Decomposition-level trust. See DrawdownDecompositionTrust above.
    decomposition_trust: DrawdownDecompositionTrust = "unavailable"


class DrawdownEngineResponse(BaseModel):
    """Wrapper. `trust='unavailable'` => every scalar None + lists empty."""

    window_trading_days: int | None
    underwater_series: list[DrawdownDailyPoint]
    current_drawdown_pct: float | None
    max_drawdown_pct: float | None
    episodes: list[DrawdownEpisode]
    trust: DrawdownTrustLevel
