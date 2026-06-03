"""Pure-analytics drawdown helpers (Epic 13 — Risk tab).

Functions in this module are I/O-free: they consume an already-computed
wealth index (or its derived underwater series) and emit deterministic
results. The market-data fetching happens in
`services/drawdown_engine.py`; the algorithm here is independently
testable from fixture data.

Methodology: see §Wealth Index and Drawdown + §Drawdown episode
identification in docs/finance/financial-methodology.md.
"""
from __future__ import annotations

from typing import Literal

from app.analytics.risk import _build_drawdown_from_return_index
from app.schemas.drawdown import DrawdownDailyPoint, DrawdownEpisode, EpisodeContributor
from app.schemas.reconciliation import DailyPortfolioState


def build_underwater_series(wealth_index: dict[str, float]) -> list[DrawdownDailyPoint]:
    """Convert a wealth-index dict (date → wealth value) to an ordered list
    of underwater curve points.

    Reuses the existing `_build_drawdown_from_return_index` helper from
    risk.py so the per-date drawdown_pct formula has a single source of
    truth in the codebase.

    Empty wealth_index → empty list (the engine surfaces unavailable).
    """
    if not wealth_index:
        return []
    drawdown_by_date = _build_drawdown_from_return_index(wealth_index)
    return [
        DrawdownDailyPoint(date=dt, drawdown_pct=drawdown_by_date[dt])
        for dt in sorted(drawdown_by_date)
    ]


def current_drawdown_pct(underwater_series: list[DrawdownDailyPoint]) -> float | None:
    """Return the last non-null drawdown_pct, or None if the series has none."""
    for point in reversed(underwater_series):
        if point.drawdown_pct is not None:
            return point.drawdown_pct
    return None


def max_drawdown_pct(underwater_series: list[DrawdownDailyPoint]) -> float | None:
    """Return the minimum (most-negative) drawdown_pct, or None if no
    non-null value exists."""
    candidates = [p.drawdown_pct for p in underwater_series if p.drawdown_pct is not None]
    if not candidates:
        return None
    return min(candidates)


def _calendar_days_between(start_iso: str, end_iso: str) -> int:
    """Whole calendar days between two ISO-8601 date strings (YYYY-MM-DD)."""
    from datetime import date as _date

    start = _date.fromisoformat(start_iso)
    end = _date.fromisoformat(end_iso)
    return (end - start).days


def identify_drawdown_episodes(
    underwater_series: list[DrawdownDailyPoint],
    top_n: int = 5,
) -> list[DrawdownEpisode]:
    """Identify drawdown episodes via the greedy forward-walk algorithm
    documented in financial-methodology.md §Drawdown episode identification.

    An *episode* is a contiguous run of `drawdown_pct < 0` between two
    equal peaks in the wealth index. The trough is the deepest point of
    the run.

    Returns episodes sorted by `magnitude_pct` ascending (deepest first),
    capped at `top_n`. The total emitted may be fewer than `top_n` if the
    series has fewer episodes.

    Edge cases (matching methodology):
      - End of series still underwater → episode emitted with
        `recovery_date=None` and `underwater_days = (last_date - peak_date)`.
      - Single-day dip (one date in the < 0 run) → episode with
        `duration_days = 0`.
      - Empty input → empty list.

    The algorithm operates on (date, drawdown_pct) pairs, but we need the
    wealth-index *values* implicit in the underwater series to detect
    peak-equality. Since drawdown_pct = 0 iff the wealth index is at its
    running peak, we use drawdown_pct as the state signal:
      drawdown_pct == 0 (or null treated as not-in-drawdown) → at peak
      drawdown_pct < 0                                       → in drawdown
    """
    if not underwater_series:
        return []

    episodes: list[DrawdownEpisode] = []
    in_drawdown = False
    peak_date: str | None = None
    trough_date: str | None = None
    trough_pct: float | None = None  # deepest (most negative) seen this episode

    for idx, point in enumerate(underwater_series):
        pct = point.drawdown_pct
        date = point.date

        # Treat None as "not in drawdown" (no data → don't fabricate an
        # episode boundary).
        is_underwater = pct is not None and pct < 0

        if not in_drawdown:
            if is_underwater:
                # New episode starts. Peak date is the prior point's date if
                # one exists; otherwise this very point (series starts under
                # water — edge case).
                peak_date = underwater_series[idx - 1].date if idx > 0 else date
                trough_date = date
                trough_pct = pct
                in_drawdown = True
            continue

        # in_drawdown == True
        assert peak_date is not None and trough_date is not None and trough_pct is not None
        if is_underwater:
            # Track the deepest point within this episode.
            if pct < trough_pct:
                trough_pct = pct
                trough_date = date
        else:
            # Either pct == 0 (recovery) or pct is None (gap). Treat both as
            # boundary: emit the episode using whichever case applies.
            recovery_date: str | None = date if pct == 0 else None
            episodes.append(_finalize_episode(
                peak_date=peak_date,
                trough_date=trough_date,
                trough_pct=trough_pct,
                recovery_date=recovery_date,
                last_date_if_underwater=date,
            ))
            in_drawdown = False
            peak_date = None
            trough_date = None
            trough_pct = None

    # End of series still underwater → emit incomplete episode.
    if in_drawdown:
        assert peak_date is not None and trough_date is not None and trough_pct is not None
        episodes.append(_finalize_episode(
            peak_date=peak_date,
            trough_date=trough_date,
            trough_pct=trough_pct,
            recovery_date=None,
            last_date_if_underwater=underwater_series[-1].date,
        ))

    # Sort deepest first; cap at top_n.
    episodes.sort(key=lambda e: e.magnitude_pct)  # ascending = most negative first
    return episodes[:top_n]


def _finalize_episode(
    *,
    peak_date: str,
    trough_date: str,
    trough_pct: float,
    recovery_date: str | None,
    last_date_if_underwater: str,
) -> DrawdownEpisode:
    """Assemble a DrawdownEpisode with the calendar-day fields filled in.

    `last_date_if_underwater` is used to compute `underwater_days` when
    `recovery_date is None` (the still-underwater path).
    """
    duration_days = _calendar_days_between(peak_date, trough_date)
    if recovery_date is not None:
        underwater_days = _calendar_days_between(peak_date, recovery_date)
    else:
        underwater_days = _calendar_days_between(peak_date, last_date_if_underwater)

    return DrawdownEpisode(
        peak_date=peak_date,
        trough_date=trough_date,
        recovery_date=recovery_date,
        magnitude_pct=round(trough_pct, 2),
        duration_days=duration_days,
        underwater_days=underwater_days,
    )


# ── Drawdown episode decomposition (Epic 15 / US-15.1) ───────────────────────


# Reconciliation tolerance: |magnitude − (sum_top + other + residual)| < 1e-9.
# By construction the equation holds exactly since residual_pct is defined as
# the remainder, so this is a defensive post-condition that catches
# floating-point edge cases and implementation bugs.
_RECONCILIATION_TOLERANCE = 1e-9


def _find_state_by_date(
    daily_states: list[DailyPortfolioState], target_date: str
) -> DailyPortfolioState | None:
    """Linear scan — daily_states is sorted ascending by date and typically
    has a few hundred entries, so binary search would be premature
    optimisation."""
    for state in daily_states:
        if state.date == target_date:
            return state
    return None


def decompose_drawdown_episode(
    daily_states: list[DailyPortfolioState],
    episode: DrawdownEpisode,
    top_n: int = 5,
) -> tuple[
    list[EpisodeContributor],
    float | None,
    float | None,
    Literal["synthetic", "partial", "unavailable"],
]:
    """Decompose an episode's portfolio-level magnitude into per-position
    contributions using arithmetic Brinson-style attribution under the
    synthetic-history convention (current holdings × historical prices, no
    rebalancing).

    Methodology: see §Drawdown episode decomposition in
    docs/finance/financial-methodology.md.

    Returns (top_contributors, other_contribution_pct, residual_pct,
    decomposition_trust):
      - top_contributors: up to top_n EpisodeContributor entries, sorted by
        abs(contribution_pct) descending. Includes positions with non-null
        contribution AND positions with null contribution (data gap) so the
        UI can surface unavailable rows distinctly; null contributors sort
        after non-null ones.
      - other_contribution_pct: aggregated Σ contribution_pct over
        decomposable positions ranked top_n+1 and beyond. None when there
        are ≤ top_n decomposable positions OR when decomposition is
        unavailable.
      - residual_pct: episode.magnitude_pct − Σ non-null contribution_pct.
        None when decomposition is unavailable. Near zero under 'synthetic'
        trust; material under 'partial' (captures missing-data share).
      - decomposition_trust: 'unavailable' when no positions could be
        decomposed; 'partial' when some had null contribution; 'synthetic'
        when all decomposable AND residual is floating-point noise only.

    Raises ValueError if the reconciliation invariant is violated beyond
    _RECONCILIATION_TOLERANCE — defensive check; by construction
    residual_pct = magnitude − Σ_non_null so violation indicates a bug.
    """
    peak_state = _find_state_by_date(daily_states, episode.peak_date)
    trough_state = _find_state_by_date(daily_states, episode.trough_date)

    # Hard fail-closed: missing state on either endpoint → no decomposition.
    if peak_state is None or trough_state is None:
        return ([], None, None, "unavailable")

    # We use total_market_value (positions-only) as V_p(t_peak), NOT
    # total_portfolio_value (which would include cash). The cash contribution
    # is 0 by construction (r_cash = 0) per methodology Contract rule, so
    # excluding cash from both numerator (positions iteration) and
    # denominator keeps the weights consistent and sums to portfolio return.
    v_p_peak = peak_state.total_market_value
    if v_p_peak is None or v_p_peak <= 0:
        return ([], None, None, "unavailable")

    # Build a lookup of trough position prices by symbol.
    trough_price_by_symbol: dict[str, float | None] = {
        position.symbol: position.market_price for position in trough_state.positions
    }

    # Per-position contribution. Iterate positions present AT PEAK only —
    # positions added after peak have no peak weight (consistent with
    # methodology edge case).
    contributors: list[EpisodeContributor] = []
    any_non_null = False
    any_null = False
    for position in peak_state.positions:
        peak_price = position.market_price
        peak_value = position.market_value
        trough_price = trough_price_by_symbol.get(position.symbol)

        # Weight at peak: V_i / V_p. Need non-null peak_value.
        weight_at_peak = (peak_value / v_p_peak) if peak_value is not None else None

        # Return: trough/peak − 1. Need non-null prices and peak > 0.
        if (
            peak_price is not None
            and peak_price > 0
            and trough_price is not None
        ):
            return_decimal: float | None = (trough_price / peak_price) - 1.0
        else:
            return_decimal = None

        # Contribution: weight × return × 100. Null if either component null.
        if weight_at_peak is not None and return_decimal is not None:
            contribution_pct: float | None = weight_at_peak * return_decimal * 100
            trust: Literal["synthetic", "unavailable"] = "synthetic"
            any_non_null = True
        else:
            contribution_pct = None
            trust = "unavailable"
            any_null = True

        contributors.append(
            EpisodeContributor(
                symbol=position.symbol,
                weight_at_peak_pct=(weight_at_peak * 100) if weight_at_peak is not None else None,
                return_pct=(return_decimal * 100) if return_decimal is not None else None,
                contribution_pct=contribution_pct,
                trust=trust,
            )
        )

    # No decomposable positions at all → unavailable.
    if not any_non_null:
        return ([], None, None, "unavailable")

    # Sort by abs(contribution_pct) descending. None values sort last
    # (key: (is_null, -abs)) so non-null contributors always come first.
    def _sort_key(c: EpisodeContributor) -> tuple[int, float]:
        if c.contribution_pct is None:
            return (1, 0.0)  # nulls last
        return (0, -abs(c.contribution_pct))

    contributors.sort(key=_sort_key)

    # Top-N split. The "other" aggregate sums non-null contributions ranked
    # top_n+1 and beyond. Null contributors (if they sort into top_n+ region)
    # are NOT added to other — their absence from Σ is what makes residual
    # non-zero on the 'partial' path.
    top_contributors = contributors[:top_n]
    rest = contributors[top_n:]

    other_non_null = [c.contribution_pct for c in rest if c.contribution_pct is not None]
    other_contribution_pct: float | None = (
        sum(other_non_null) if (len(rest) > 0 and len(other_non_null) > 0) else None
    )

    # Residual: magnitude − Σ all non-null contributions (top + other).
    top_non_null_sum = sum(
        c.contribution_pct for c in top_contributors if c.contribution_pct is not None
    )
    explained_pct = top_non_null_sum + (other_contribution_pct or 0.0)
    residual_pct = episode.magnitude_pct - explained_pct

    # Trust derivation.
    if any_null:
        decomposition_trust: Literal["synthetic", "partial", "unavailable"] = "partial"
    elif abs(residual_pct) < 0.001:
        # All positions decomposed AND residual is floating-point noise → fully synthetic.
        decomposition_trust = "synthetic"
    else:
        # All positions decomposed but residual is material — methodology
        # says this shouldn't happen under static synthetic-history (Σ w×r
        # exactly = r_p), but if it does (numerical issue, partial day data),
        # surface as 'partial' rather than claim full synthetic.
        decomposition_trust = "partial"

    # Reconciliation invariant (defensive post-condition).
    invariant_lhs = abs(
        episode.magnitude_pct
        - (top_non_null_sum + (other_contribution_pct or 0.0) + residual_pct)
    )
    if invariant_lhs > _RECONCILIATION_TOLERANCE:
        raise ValueError(
            f"Drawdown decomposition reconciliation failed for episode "
            f"{episode.peak_date} → {episode.trough_date}: "
            f"|magnitude − (sum_top + other + residual)| = {invariant_lhs:.2e} "
            f"(tolerance = {_RECONCILIATION_TOLERANCE:.2e})"
        )

    return (top_contributors, other_contribution_pct, residual_pct, decomposition_trust)
