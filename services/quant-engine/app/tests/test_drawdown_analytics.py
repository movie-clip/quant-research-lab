"""Pure-analytics tests for app/analytics/drawdown.py.

Verifies the greedy forward-walk episode identification algorithm
against deterministic fixtures — no market data, no engine wiring.
"""
from __future__ import annotations

import pytest

from app.analytics.drawdown import (
    build_underwater_series,
    current_drawdown_pct,
    decompose_drawdown_episode,
    identify_drawdown_episodes,
    max_drawdown_pct,
)
from app.schemas.drawdown import DrawdownDailyPoint, DrawdownEpisode
from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition


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


# ── decompose_drawdown_episode (US-15.1) ──────────────────────────────────────


def _episode(peak: str, trough: str, magnitude_pct: float) -> DrawdownEpisode:
    return DrawdownEpisode(
        peak_date=peak,
        trough_date=trough,
        recovery_date=None,
        magnitude_pct=magnitude_pct,
        duration_days=0,
        underwater_days=0,
    )


def _state(
    date: str,
    positions: list[tuple[str, float | None, float | None, float | None]],
    total_market_value: float | None = None,
) -> DailyPortfolioState:
    """positions = [(symbol, quantity, market_price, market_value), ...].
    total_market_value defaults to sum of position market_values."""
    state_positions = [
        DailyStatePosition(symbol=sym, quantity=qty or 0.0, market_price=mp, market_value=mv)
        for sym, qty, mp, mv in positions
    ]
    if total_market_value is None:
        total_market_value = sum(p.market_value or 0.0 for p in state_positions)
    return DailyPortfolioState(
        date=date,
        cash={"USD": 0.0},
        positions=state_positions,
        total_market_value=total_market_value,
        total_portfolio_value=total_market_value,
    )


def test_decompose_returns_unavailable_when_peak_state_missing() -> None:
    """Empty daily_states → no peak state can be found → unavailable, no fabrication."""
    episode = _episode("2025-01-01", "2025-01-10", -10.0)
    result = decompose_drawdown_episode([], episode)
    top, other, residual, trust = result
    assert trust == "unavailable"
    assert top == []
    assert other is None
    assert residual is None


def test_decompose_returns_unavailable_when_total_market_value_zero() -> None:
    """V_p(t_peak) == 0 makes weights undefined → unavailable."""
    peak_state = _state("2025-01-01", [("AAPL", 1.0, 100.0, 0.0)], total_market_value=0.0)
    trough_state = _state("2025-01-10", [("AAPL", 1.0, 90.0, 0.0)], total_market_value=0.0)
    episode = _episode("2025-01-01", "2025-01-10", -10.0)
    top, other, residual, trust = decompose_drawdown_episode([peak_state, trough_state], episode)
    assert trust == "unavailable"
    assert top == []
    assert other is None
    assert residual is None


def test_decompose_basic_two_position_portfolio_reconciles_to_magnitude() -> None:
    """Two positions at 50/50 weight, both drop 10% → each contribution = -5%;
    total = -10% = magnitude; residual ≈ 0; trust='synthetic'."""
    peak_state = _state("2025-01-01", [
        ("AAPL", 50.0, 100.0, 5000.0),
        ("MSFT", 25.0, 200.0, 5000.0),
    ])
    trough_state = _state("2025-01-10", [
        ("AAPL", 50.0, 90.0, 4500.0),
        ("MSFT", 25.0, 180.0, 4500.0),
    ])
    episode = _episode("2025-01-01", "2025-01-10", -10.0)
    top, other, residual, trust = decompose_drawdown_episode([peak_state, trough_state], episode)

    assert trust == "synthetic"
    assert len(top) == 2
    # Both contributions should be -5%; order doesn't matter (equal magnitudes).
    contribs = sorted(c.contribution_pct for c in top)
    assert all(c is not None for c in contribs)
    assert abs(contribs[0] - (-5.0)) < 1e-9
    assert abs(contribs[1] - (-5.0)) < 1e-9
    assert other is None  # ≤ top_n positions; no aggregate
    assert residual is not None and abs(residual) < 1e-9


def test_decompose_handles_position_with_null_price_at_trough() -> None:
    """One position has null trough price → its contribution is null,
    decomposition_trust='partial', residual captures the missing share."""
    peak_state = _state("2025-01-01", [
        ("AAPL", 50.0, 100.0, 5000.0),
        ("MSFT", 25.0, 200.0, 5000.0),
    ])
    trough_state = _state("2025-01-10", [
        ("AAPL", 50.0, 90.0, 4500.0),
        ("MSFT", 25.0, None, None),  # MSFT data gap at trough
    ])
    episode = _episode("2025-01-01", "2025-01-10", -10.0)
    top, _other, residual, trust = decompose_drawdown_episode([peak_state, trough_state], episode)

    assert trust == "partial"
    msft = next(c for c in top if c.symbol == "MSFT")
    assert msft.contribution_pct is None
    assert msft.trust == "unavailable"
    aapl = next(c for c in top if c.symbol == "AAPL")
    assert aapl.contribution_pct is not None
    assert abs(aapl.contribution_pct - (-5.0)) < 1e-9
    # Residual = magnitude (-10) − (-5) = -5  (MSFT's missing share)
    assert residual is not None and abs(residual - (-5.0)) < 1e-9


def test_decompose_caps_top_n_at_5_and_aggregates_rest_as_other_contribution() -> None:
    """7 positions with distinct magnitudes → top_contributors has 5;
    other_contribution_pct = sum of bottom 2."""
    # 7 positions, each $1000 (equal weight ~14.29%); returns -1%, -2%, ..., -7%.
    # Contributions: weight × return × 100 = (1/7) × r × 100.
    # Sorted by abs descending: -7 → -1.
    n_positions = 7
    weight = 1.0 / n_positions
    peak_positions = [
        (f"S{i}", 10.0, 100.0, 1000.0) for i in range(1, n_positions + 1)
    ]
    trough_positions = [
        (f"S{i}", 10.0, 100.0 * (1.0 - i / 100.0), 1000.0 * (1.0 - i / 100.0))
        for i in range(1, n_positions + 1)
    ]
    peak_state = _state("2025-01-01", peak_positions)
    trough_state = _state("2025-01-10", trough_positions)
    # Total portfolio return: 7000 → sum(1000*(1-i/100)) = 7000 - 10*sum(1..7) = 7000 - 280 = 6720
    # magnitude = (6720/7000 − 1) × 100 = -4.0
    episode = _episode("2025-01-01", "2025-01-10", -4.0)
    top, other, residual, trust = decompose_drawdown_episode([peak_state, trough_state], episode, top_n=5)

    assert trust == "synthetic"
    assert len(top) == 5
    # Top 5 by abs(contribution): -7, -6, -5, -4, -3 (each scaled by weight).
    top_returns = [round(c.contribution_pct / weight / 100 * (-100), 2) for c in top]
    # Approximately the return percents −7 to −3 in some order — just check the set.
    assert {round(c.contribution_pct, 4) for c in top} == {
        round(weight * -i, 4) for i in range(3, 8)
    }
    # other = bottom 2: returns −1 and −2; contributions = weight × −1 + weight × −2 = −3 × weight
    assert other is not None
    assert abs(other - (weight * -3.0)) < 1e-9
    assert residual is not None and abs(residual) < 1e-9


def test_decompose_sorts_top_contributors_by_abs_contribution_descending() -> None:
    """Mixed positive + negative contributions (some positions rallied, others
    sank); top_contributors is sorted by abs(contribution) desc."""
    peak_state = _state("2025-01-01", [
        ("BIGGAIN", 10.0, 100.0, 1000.0),    # 50% weight, return +20% → contrib +10%
        ("SMALLLOSS", 10.0, 100.0, 1000.0),  # 50% weight, return -2% → contrib -1%
    ])
    trough_state = _state("2025-01-10", [
        ("BIGGAIN", 10.0, 120.0, 1200.0),
        ("SMALLLOSS", 10.0, 98.0, 980.0),
    ])
    # Portfolio: 2000 → 2180 = +9% (not really a drawdown but methodology is symmetric)
    episode = _episode("2025-01-01", "2025-01-10", 9.0)
    top, _other, _residual, _trust = decompose_drawdown_episode([peak_state, trough_state], episode)

    assert len(top) == 2
    # BIGGAIN (|contrib|=10) before SMALLLOSS (|contrib|=1)
    assert top[0].symbol == "BIGGAIN"
    assert top[1].symbol == "SMALLLOSS"


def test_decompose_raises_when_reconciliation_invariant_violated(monkeypatch) -> None:
    """The defensive ValueError check fires when the reconciliation invariant
    is violated. We force the violation by setting the tolerance to a
    negative value — any real abs(...) computation is ≥ 0, so the
    `invariant_lhs > _RECONCILIATION_TOLERANCE` condition always fires.
    Proves the check is wired in, not just decorative."""
    peak_state = _state("2025-01-01", [("AAPL", 10.0, 100.0, 1000.0)])
    trough_state = _state("2025-01-10", [("AAPL", 10.0, 90.0, 900.0)])
    episode = _episode("2025-01-01", "2025-01-10", -10.0)

    import app.analytics.drawdown as drawdown_module
    monkeypatch.setattr(drawdown_module, "_RECONCILIATION_TOLERANCE", -1.0)

    with pytest.raises(ValueError, match="reconciliation failed"):
        decompose_drawdown_episode([peak_state, trough_state], episode)
