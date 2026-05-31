"""Pure-analytics tests for app/analytics/drawdown.py.

Verifies the greedy forward-walk episode identification algorithm
against deterministic fixtures — no market data, no engine wiring.
"""
from __future__ import annotations

from app.analytics.drawdown import (
    build_underwater_series,
    current_drawdown_pct,
    identify_drawdown_episodes,
    max_drawdown_pct,
)
from app.schemas.drawdown import DrawdownDailyPoint


def _series(*points: tuple[str, float | None]) -> list[DrawdownDailyPoint]:
    """Convenience: build a list of DrawdownDailyPoint from (date, pct) tuples."""
    return [DrawdownDailyPoint(date=d, drawdown_pct=p) for d, p in points]


# ── identify_drawdown_episodes ────────────────────────────────────────────────


def test_identify_drawdown_episodes_emits_complete_episode_with_recovery() -> None:
    """Wealth-index 100 → 90 → 100 (down 10%, recovers). One episode emitted
    with non-null recovery_date and magnitude_pct == -10.0."""
    # Underwater series: peak day at 0.0, trough at -10.0, recovery back to 0.0.
    series = _series(
        ("2025-01-01", 0.0),     # peak
        ("2025-01-02", -10.0),   # trough
        ("2025-01-03", 0.0),     # recovery
    )
    episodes = identify_drawdown_episodes(series)

    assert len(episodes) == 1
    e = episodes[0]
    assert e.peak_date == "2025-01-01"
    assert e.trough_date == "2025-01-02"
    assert e.recovery_date == "2025-01-03"
    assert e.magnitude_pct == -10.0
    assert e.duration_days == 1   # 01-01 → 01-02
    assert e.underwater_days == 2 # 01-01 → 01-03


def test_identify_drawdown_episodes_emits_incomplete_episode_when_still_underwater() -> None:
    """Series ends below peak. One episode with recovery_date=None and
    underwater_days = (last_date - peak_date)."""
    series = _series(
        ("2025-01-01", 0.0),    # peak
        ("2025-01-02", -5.0),
        ("2025-01-15", -8.0),   # trough, also last date
    )
    episodes = identify_drawdown_episodes(series)

    assert len(episodes) == 1
    e = episodes[0]
    assert e.peak_date == "2025-01-01"
    assert e.trough_date == "2025-01-15"
    assert e.recovery_date is None
    assert e.magnitude_pct == -8.0
    assert e.underwater_days == 14   # 01-01 → 01-15


def test_identify_drawdown_episodes_sorts_by_magnitude_desc_and_caps_at_top_n() -> None:
    """Series with 7 episodes of varying depths; top_n=5 → 5 deepest first."""
    # Build 7 distinct episodes with magnitudes: -3, -8, -2, -15, -5, -11, -1
    # Each: peak (0.0) → trough → recovery (0.0).
    magnitudes = [-3.0, -8.0, -2.0, -15.0, -5.0, -11.0, -1.0]
    points: list[tuple[str, float | None]] = []
    day = 1
    for mag in magnitudes:
        points.append((f"2025-01-{day:02d}", 0.0))      # peak
        day += 1
        points.append((f"2025-01-{day:02d}", mag))      # trough
        day += 1
        points.append((f"2025-01-{day:02d}", 0.0))      # recovery
        day += 1
    series = _series(*points)

    episodes = identify_drawdown_episodes(series, top_n=5)

    assert len(episodes) == 5
    assert [e.magnitude_pct for e in episodes] == [-15.0, -11.0, -8.0, -5.0, -3.0]


def test_identify_drawdown_episodes_handles_single_day_dip_with_duration_zero() -> None:
    """A 1-day dip: peak → trough on the same calendar day-pair → recovery.
    duration_days = 1 - 1 = 0 only if peak and trough are the same date.
    Here we construct exactly that scenario: the dip date IS the peak's
    next day, and the recovery is the day after.

    Note: the algorithm sets peak_date = prior point's date, so a 1-day
    excursion (peak at idx 0, trough at idx 1, recovery at idx 2) yields
    duration_days = 1. For duration_days=0 we need an episode where the
    very first point of the series is already in drawdown (so peak_date
    == trough_date == first point's date).
    """
    series = _series(
        ("2025-01-01", -3.0),    # series starts under water
        ("2025-01-02", 0.0),     # immediate recovery
    )
    episodes = identify_drawdown_episodes(series)

    assert len(episodes) == 1
    e = episodes[0]
    assert e.peak_date == "2025-01-01"
    assert e.trough_date == "2025-01-01"
    assert e.duration_days == 0
    assert e.recovery_date == "2025-01-02"


def test_current_drawdown_pct_returns_last_non_null() -> None:
    series = _series(
        ("2025-01-01", 0.0),
        ("2025-01-02", -5.0),
        ("2025-01-03", -3.0),
    )
    assert current_drawdown_pct(series) == -3.0

    # Trailing null is ignored
    series_with_trailing_null = _series(
        ("2025-01-01", -2.0),
        ("2025-01-02", None),
    )
    assert current_drawdown_pct(series_with_trailing_null) == -2.0

    # All-null returns None
    assert current_drawdown_pct(_series(("2025-01-01", None))) is None

    # Empty returns None
    assert current_drawdown_pct([]) is None


def test_max_drawdown_pct_returns_minimum_or_none_on_empty() -> None:
    series = _series(
        ("2025-01-01", 0.0),
        ("2025-01-02", -5.0),
        ("2025-01-03", -12.0),
        ("2025-01-04", -3.0),
    )
    assert max_drawdown_pct(series) == -12.0

    # Empty list and all-null both yield None
    assert max_drawdown_pct([]) is None
    assert max_drawdown_pct(_series(("2025-01-01", None))) is None


# ── build_underwater_series ──────────────────────────────────────────────────


def test_build_underwater_series_emits_one_point_per_wealth_date_in_order() -> None:
    """Sanity check on the wealth-index → underwater-series conversion."""
    wealth_index = {
        "2025-01-03": 100.0,   # at-peak after rebase
        "2025-01-01": 90.0,    # initial — but peak walks up from 0
        "2025-01-02": 95.0,
    }
    series = build_underwater_series(wealth_index)

    # Dates must be sorted ascending
    assert [p.date for p in series] == ["2025-01-01", "2025-01-02", "2025-01-03"]
    # All three points have a defined drawdown_pct (none null on happy path)
    assert all(p.drawdown_pct is not None for p in series)
    # Final point (peak = 100) → drawdown_pct == 0
    assert series[-1].drawdown_pct == 0.0


def test_build_underwater_series_empty_input_returns_empty_list() -> None:
    assert build_underwater_series({}) == []
