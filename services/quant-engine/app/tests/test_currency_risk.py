"""US-26.2: currency risk contribution — the local / FX / interaction split.

The identity pins here are the important ones: the decomposition is EXACT, so
a leg computed from the wrong currency shows up as a broken identity rather
than as a plausible-looking number.
"""
from __future__ import annotations

import pytest

from app.analytics.currency_risk import (
    HoldingReturnLegs,
    build_currency_risk_decomposition,
    build_holding_legs,
)


def _series(start: float, steps: list[float], first_date_index: int = 1) -> dict[str, float]:
    """Price series from a list of daily returns, on sequential dates."""
    prices = {f"2026-01-{first_date_index:02d}": start}
    value = start
    for offset, step in enumerate(steps, start=first_date_index + 1):
        value *= 1 + step
        prices[f"2026-01-{offset:02d}"] = value
    return prices


def _flat(n: int, value: float = 1.0) -> dict[str, float]:
    return {f"2026-01-{i:02d}": value for i in range(1, n + 2)}


def test_per_holding_identity_is_exact() -> None:
    """AC3 — r_base == r_local + r_fx + (r_local x r_fx), to float precision."""
    local_prices = _series(100.0, [0.02, -0.01, 0.03, 0.005])
    fx_prices = _series(1.10, [0.01, 0.004, -0.006, 0.002])

    legs = build_holding_legs("EUE", 1.0, "EUR", local_prices, fx_prices)

    dates = sorted(legs.local)
    assert dates, "expected paired days"
    base_dates = sorted(set(local_prices) & set(fx_prices))
    for previous, current in zip(base_dates, base_dates[1:]):
        base_before = local_prices[previous] * fx_prices[previous]
        base_after = local_prices[current] * fx_prices[current]
        r_base = base_after / base_before - 1
        reconstructed = legs.local[current] + legs.fx[current] + legs.interaction(current)
        assert reconstructed == pytest.approx(r_base, abs=1e-12)


def test_portfolio_legs_reconstruct_the_weighted_base_return() -> None:
    """AC3 at portfolio level — L + F + X == sum(w_i x r_base_i) every day."""
    a = build_holding_legs("EUE", 0.6, "EUR", _series(100.0, [0.01, -0.02, 0.015]), _series(1.10, [0.003, 0.001, -0.002]))
    b = build_holding_legs("GBX", 0.4, "GBP", _series(50.0, [-0.005, 0.02, 0.01]), _series(1.30, [0.002, -0.004, 0.001]))

    dates = sorted(set(a.local) & set(b.local))
    for date in dates:
        legs_total = (
            0.6 * (a.local[date] + a.fx[date] + a.interaction(date))
            + 0.4 * (b.local[date] + b.fx[date] + b.interaction(date))
        )
        base_total = (
            0.6 * ((1 + a.local[date]) * (1 + a.fx[date]) - 1)
            + 0.4 * ((1 + b.local[date]) * (1 + b.fx[date]) - 1)
        )
        assert legs_total == pytest.approx(base_total, abs=1e-12)


def _long_legs(local_steps: list[float], fx_steps: list[float], weight: float = 1.0, currency: str = "EUR") -> HoldingReturnLegs:
    return build_holding_legs("SYM", weight, currency, _series(100.0, local_steps), _series(1.10, fx_steps))


def test_the_three_shares_sum_to_exactly_one() -> None:
    """AC2 — component covariances of an exact identity leave no residual."""
    n = 40
    local_steps = [0.01 if i % 3 else -0.012 for i in range(n)]
    fx_steps = [0.002 if i % 4 else -0.003 for i in range(n)]

    result = build_currency_risk_decomposition([_long_legs(local_steps, fx_steps)])

    total = (
        result.local_variance_share
        + result.currency_variance_share
        + result.interaction_variance_share
    )
    assert total == pytest.approx(1.0, abs=1e-6)


def test_base_currency_only_portfolio_has_zero_currency_share() -> None:
    """AC11 — correct in the trivial case."""
    n = 40
    local_steps = [0.01 if i % 3 else -0.012 for i in range(n)]
    legs = build_holding_legs("USA", 1.0, "USD", _series(100.0, local_steps), None)

    result = build_currency_risk_decomposition([legs])

    assert result.currency_variance_share == pytest.approx(0.0, abs=1e-9)
    assert result.interaction_variance_share == pytest.approx(0.0, abs=1e-9)
    assert result.local_variance_share == pytest.approx(1.0, abs=1e-9)
    assert result.currency_standalone_vol_pct == pytest.approx(0.0, abs=1e-9)


def test_a_currency_leg_moving_against_the_local_leg_gives_a_negative_share() -> None:
    """AC5 — the share is NOT clamped. A currency that offsets the local leg
    genuinely reduces portfolio variance, and a floor of 0 would fabricate
    confidence the data does not support."""
    n = 40
    local_steps = [0.02 if i % 2 else -0.02 for i in range(n)]
    # Perfectly anti-correlated with the local leg, at smaller amplitude.
    fx_steps = [-0.006 if i % 2 else 0.006 for i in range(n)]

    result = build_currency_risk_decomposition([_long_legs(local_steps, fx_steps)])

    assert result.currency_variance_share < 0
    assert result.local_fx_correlation == pytest.approx(-1.0, abs=1e-3)
    # Still sums to 1 — a negative share is part of an exact split.
    total = (
        result.local_variance_share
        + result.currency_variance_share
        + result.interaction_variance_share
    )
    assert total == pytest.approx(1.0, abs=1e-6)


def test_the_interaction_share_is_reported_even_when_tiny() -> None:
    """AC4 — never folded into the currency leg (the Ankrim-Hensel convention
    this project departs from), never dropped."""
    n = 40
    local_steps = [0.01 if i % 3 else -0.008 for i in range(n)]
    fx_steps = [0.0004 if i % 5 else -0.0003 for i in range(n)]

    result = build_currency_risk_decomposition([_long_legs(local_steps, fx_steps)])

    assert result.interaction_variance_share is not None
    assert abs(result.interaction_variance_share) < 0.01, "expected a tiny share for this input"


def test_below_the_observation_floor_everything_is_null() -> None:
    """AC7 — fail closed. 19 paired days is under MIN_DAILY_OBSERVATIONS."""
    local_steps = [0.01] * 18
    fx_steps = [0.002] * 18

    result = build_currency_risk_decomposition([_long_legs(local_steps, fx_steps)])

    assert result.observations < 20
    assert result.local_variance_share is None
    assert result.currency_variance_share is None
    assert result.interaction_variance_share is None
    assert result.local_fx_correlation is None


def test_zero_portfolio_variance_nulls_every_share() -> None:
    """AC9 — a constant series carries no information; 0 or 1 would claim one."""
    n = 40
    legs = build_holding_legs("USA", 1.0, "USD", _flat(n, 100.0), None)

    result = build_currency_risk_decomposition([legs])

    assert result.observations >= 20
    assert result.local_variance_share is None
    assert result.currency_variance_share is None
    assert result.interaction_variance_share is None


def test_a_zero_variance_fx_leg_nulls_the_correlation_but_keeps_the_shares() -> None:
    """AC9 — the zero-variance guard is on the correlation only."""
    n = 40
    local_steps = [0.01 if i % 3 else -0.012 for i in range(n)]
    legs = build_holding_legs("EUE", 1.0, "EUR", _series(100.0, local_steps), _flat(n + 1, 1.10))

    result = build_currency_risk_decomposition([legs])

    assert result.local_fx_correlation is None
    assert result.local_variance_share == pytest.approx(1.0, abs=1e-9)
    assert result.currency_variance_share == pytest.approx(0.0, abs=1e-9)


def test_per_currency_contributions_sum_to_the_currency_share() -> None:
    """The per-currency table must account for the headline number, not merely
    sit beside it."""
    n = 40
    eur = build_holding_legs(
        "EUE", 0.5, "EUR",
        _series(100.0, [0.01 if i % 3 else -0.01 for i in range(n)]),
        _series(1.10, [0.002 if i % 4 else -0.003 for i in range(n)]),
    )
    gbp = build_holding_legs(
        "GBX", 0.5, "GBP",
        _series(80.0, [0.008 if i % 2 else -0.006 for i in range(n)]),
        _series(1.30, [-0.001 if i % 3 else 0.004 for i in range(n)]),
    )

    result = build_currency_risk_decomposition([eur, gbp])

    assert set(result.per_currency_contribution) == {"EUR", "GBP"}
    assert sum(result.per_currency_contribution.values()) == pytest.approx(
        result.currency_variance_share, abs=1e-5
    )


def test_a_day_missing_either_side_is_dropped_never_zero_filled() -> None:
    """No fabrication: a missing FX quote drops the DAY. It does NOT become a
    zero FX return, which would silently reassign that day's whole move to the
    local leg — the exact mislabelling this analytic exists to avoid.

    The next observation spans the gap, per methodology §Synthetic History
    Coverage Rule's interior-gap convention ("carry the last known price to the
    next quote", for aligning mixed trading calendars). That is safe HERE for a
    reason worth stating: both legs are computed over the *same* surviving date
    pair, so the identity still holds exactly across the gap — the split stays
    honest even though that observation covers more than one calendar day.
    """
    local_prices = _series(100.0, [0.01, 0.02, 0.03])
    fx_prices = _series(1.10, [0.005, 0.004, 0.001])
    del fx_prices["2026-01-03"]

    legs = build_holding_legs("EUE", 1.0, "EUR", local_prices, fx_prices)

    # The unpaired day contributes nothing to either leg.
    assert "2026-01-03" not in legs.local
    assert "2026-01-03" not in legs.fx
    # The next observation spans 01-02 -> 01-04 (interior-gap convention)...
    assert "2026-01-04" in legs.local
    # ...and the identity still holds exactly over that spanning interval.
    base = (local_prices["2026-01-04"] * fx_prices["2026-01-04"]) / (
        local_prices["2026-01-02"] * fx_prices["2026-01-02"]
    ) - 1
    reconstructed = (
        legs.local["2026-01-04"] + legs.fx["2026-01-04"] + legs.interaction("2026-01-04")
    )
    assert reconstructed == pytest.approx(base, abs=1e-12)
