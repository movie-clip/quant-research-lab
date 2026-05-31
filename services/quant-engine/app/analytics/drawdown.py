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

from app.analytics.risk import _build_drawdown_from_return_index
from app.schemas.drawdown import DrawdownDailyPoint, DrawdownEpisode


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
