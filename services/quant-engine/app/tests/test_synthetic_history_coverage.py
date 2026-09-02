"""US-27.7 (audit F8) — synthetic-history coverage rule.

Prices are never fabricated before a symbol's first quote (the previous
builders back-filled the first quote flat and flat-filled statement close
prices for zero-history symbols → fabricated zero returns that understated
volatility, VaR, and drawdown). The effective window starts at the latest
first-quote across material holdings; sub-de-minimis late-listers and
zero-coverage holdings are excluded — all disclosed via
SyntheticHistoryCoverage.

Covers: the synthetic builder (diagnostics_engine), the broker replay path
(PortfolioStateEngine), and engine-level coverage passthrough.
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from app.engine.portfolio_state import PortfolioStateEngine
from app.schemas.imports import ImportedPortfolioSnapshot
from app.services.synthetic_history import (
    build_synthetic_snapshot_history_states_with_coverage,
)
from app.tests.fixtures import imported_snapshot, position


_START = date(2025, 1, 2)


def _dates(n: int) -> list[str]:
    return [(_START + timedelta(days=offset)).isoformat() for offset in range(n)]


def _rows(dates: list[str], start_price: float, daily_return: float) -> list[dict]:
    rows = []
    price = start_price
    for d in dates:
        rows.append({"date": d, "price": round(price, 8)})
        price *= 1 + daily_return
    return rows


def _snapshot(positions: list[dict]) -> ImportedPortfolioSnapshot:
    return ImportedPortfolioSnapshot.model_validate(imported_snapshot(positions=positions))


def test_material_short_history_symbol_truncates_the_window_and_is_disclosed() -> None:
    """A (50%) covers the full window; B (50%, material) starts at day 10 →
    effective window starts at B's first quote, limiting_symbol=B, and no
    state carries a fabricated pre-listing price for B."""
    dates = _dates(30)
    snapshot = _snapshot([
        position("AAA", market_value=5000.0),
        position("BBB", market_value=5000.0),
    ])
    histories = {
        "AAA": _rows(dates, 100.0, 0.01),
        "BBB": _rows(dates[10:], 50.0, 0.02),
    }

    states, coverage = build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot, price_histories=histories, valuation_dates=dates,
    )

    assert coverage.requested_start_date == dates[0]
    assert coverage.effective_start_date == dates[10]
    assert coverage.limiting_symbol == "BBB"
    assert coverage.excluded_symbols == []
    assert states[0].date == dates[10]
    assert len(states) == 20
    # Both positions valued on every state; B anchored at its first REAL quote.
    for state in states:
        assert {p.symbol for p in state.positions} == {"AAA", "BBB"}


def test_sub_de_minimis_late_lister_is_excluded_not_truncating() -> None:
    """A (99.5%) full coverage; C (0.5%, below the 1% de-minimis) starts at
    day 20 → the window is NOT truncated; C is excluded and disclosed."""
    dates = _dates(30)
    snapshot = _snapshot([
        position("AAA", market_value=9950.0),
        position("CCC", market_value=50.0),
    ])
    histories = {
        "AAA": _rows(dates, 100.0, 0.01),
        "CCC": _rows(dates[20:], 5.0, 0.0),
    }

    states, coverage = build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot, price_histories=histories, valuation_dates=dates,
    )

    assert coverage.effective_start_date == dates[0]
    assert coverage.limiting_symbol is None
    assert coverage.excluded_symbols == ["CCC"]
    assert states[0].date == dates[0]
    assert all({p.symbol for p in state.positions} == {"AAA"} for state in states)


def test_zero_coverage_symbol_is_excluded_never_statement_price_filled() -> None:
    """A symbol with no in-window quotes at all was previously flat-filled at
    the statement close price for the WHOLE window (fabricated zero returns);
    it is now excluded and disclosed."""
    dates = _dates(30)
    snapshot = _snapshot([
        position("AAA", market_value=9000.0),
        position("ZZZ", market_value=1000.0, close_price=10.0),
    ])
    histories = {"AAA": _rows(dates, 100.0, 0.01)}

    states, coverage = build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot, price_histories=histories, valuation_dates=dates,
    )

    assert coverage.excluded_symbols == ["ZZZ"]
    assert coverage.effective_start_date == dates[0]
    assert all({p.symbol for p in state.positions} == {"AAA"} for state in states)


def test_no_covered_positions_returns_empty_states_with_full_disclosure() -> None:
    dates = _dates(30)
    snapshot = _snapshot([position("ZZZ", market_value=1000.0)])

    states, coverage = build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot, price_histories={}, valuation_dates=dates,
    )

    assert states == []
    assert coverage.excluded_symbols == ["ZZZ"]
    assert coverage.effective_start_date is None


def test_interior_gap_keeps_carry_to_next_quote_convention() -> None:
    """AC4 — a missing quote AFTER the first one carries the last known price
    (documented convention); this is not the back-fill case."""
    dates = _dates(5)
    gap_rows = [
        {"date": dates[0], "price": 100.0},
        {"date": dates[1], "price": 110.0},
        # dates[2] missing — interior gap
        {"date": dates[3], "price": 120.0},
        {"date": dates[4], "price": 130.0},
    ]
    snapshot = _snapshot([position("AAA", market_value=1000.0)])

    states, coverage = build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot, price_histories={"AAA": gap_rows}, valuation_dates=dates,
    )

    assert coverage.effective_start_date == dates[0]
    prices = [state.positions[0].market_price for state in states]
    assert prices == [100.0, 110.0, 110.0, 120.0, 130.0]


def test_truncated_window_volatility_exceeds_the_old_flat_fill_output() -> None:
    """AC3 — hand-verifiable variant. Covered window (10 dates from BBB's
    first quote): AAA alternates +2%/−2%, BBB flat → portfolio daily returns
    alternate ±1% (equal weights at anchor, hand-derived below). The pre-fix
    flat-fill produced 20 leading ZERO returns for BBB and (with AAA's moves
    diluted by a flat 50% sleeve) a strictly smaller stdev over the full
    window. New population stdev ≈ 0.01 > flat-fill-era stdev."""
    dates = _dates(30)
    aaa_prices: list[dict] = []
    price = 100.0
    for i, d in enumerate(dates):
        aaa_prices.append({"date": d, "price": round(price, 8)})
        price *= 1.02 if i % 2 == 0 else 0.98
    snapshot = _snapshot([
        position("AAA", market_value=5000.0),
        position("BBB", market_value=5000.0),
    ])
    histories = {
        "AAA": aaa_prices,
        "BBB": [{"date": d, "price": 50.0} for d in dates[20:]],  # material, late, flat
    }

    states, coverage = build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot, price_histories=histories, valuation_dates=dates,
    )

    assert coverage.effective_start_date == dates[20]
    returns = [
        states[i].total_market_value / states[i - 1].total_market_value - 1
        for i in range(1, len(states))
    ]
    # AAA sleeve alternates ±2% on half the portfolio → portfolio return
    # magnitude ≈ 1% every day of the covered window (never a zero segment).
    assert all(abs(r) > 0.009 for r in returns)
    new_stdev = _population_stdev(returns)

    # What the pre-fix flat-fill produced: BBB flat at its first quote across
    # the 20 leading dates too — same ±1% portfolio returns PLUS nothing
    # excluded, i.e. the same distribution over 29 returns instead of 9.
    # The real understatement case is the zero-coverage variant: statement
    # flat-fill turned the WHOLE BBB sleeve into zeros. Reconstruct it:
    flat_fill_returns = [0.0] * 20 + returns  # leading fabricated-zero segment
    old_stdev = _population_stdev(flat_fill_returns)
    assert new_stdev > old_stdev


def _population_stdev(values: list[float]) -> float:
    mean = sum(values) / len(values)
    return math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))


# ── Broker replay path (PortfolioStateEngine) ─────────────────────────────────


def _broker_snapshot(positions: list[dict]) -> ImportedPortfolioSnapshot:
    payload = imported_snapshot(positions=positions)
    payload["statement_totals"] = {"starting_nav": 10000.0, "ending_nav": 10000.0}
    return ImportedPortfolioSnapshot.model_validate(payload)


def test_broker_path_truncates_to_material_opening_coverage() -> None:
    """An opening position whose price history starts mid-window truncates
    the replay window instead of being back-filled flat (US-27.7)."""
    dates = _dates(30)
    snapshot = _broker_snapshot([
        position("AAA", market_value=5000.0, quantity=50.0),
        position("BBB", market_value=5000.0, quantity=100.0),
    ])
    engine = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history={})
    histories = {
        "AAA": _rows(dates, 100.0, 0.01),
        "BBB": _rows(dates[10:], 50.0, 0.0),
    }

    states = engine.build_daily_states(price_histories=histories, valuation_dates=dates)

    assert states[0].date == dates[10]
    assert len(states) == 20


def test_broker_path_seeds_carry_from_a_real_pre_window_quote() -> None:
    """A quote dated before the valuation window seeds the carry (an observed
    price carried forward — not a back-fill), so the window is not truncated."""
    dates = _dates(10)
    pre_window_date = (_START - timedelta(days=3)).isoformat()
    snapshot = _broker_snapshot([position("AAA", market_value=1000.0, quantity=10.0)])
    engine = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history={})
    histories = {
        "AAA": [{"date": pre_window_date, "price": 95.0}] + _rows(dates[2:], 100.0, 0.0),
    }

    states = engine.build_daily_states(price_histories=histories, valuation_dates=dates)

    assert states[0].date == dates[0]
    assert states[0].positions[0].market_price == 95.0  # carried real quote
    assert states[2].positions[0].market_price == 100.0


def test_broker_path_keeps_statement_anchor_for_zero_history_symbols() -> None:
    """A symbol with no fetchable history at all keeps the statement close
    anchor (broker-truth-adjacent) and does not truncate the window."""
    dates = _dates(10)
    snapshot = _broker_snapshot([
        position("AAA", market_value=5000.0, quantity=50.0),
        position("VUAA", market_value=5000.0, quantity=40.0, close_price=125.0),
    ])
    engine = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history={})
    histories = {"AAA": _rows(dates, 100.0, 0.01)}

    states = engine.build_daily_states(price_histories=histories, valuation_dates=dates)

    assert states[0].date == dates[0]
    vuaa = next(p for p in states[0].positions if p.symbol == "VUAA")
    assert vuaa.market_price == 125.0


# ── Engine-level passthrough (distribution engine, mocked market data) ────────


def test_distribution_engine_surfaces_coverage(mocker) -> None:
    from app.services.distribution_engine import run_distribution_engine
    from app.schemas.distribution import DistributionEngineRequest
    from app.tests.fixtures import install_market_data_mock, price_rows

    install_market_data_mock(
        mocker,
        "app.services.distribution_engine",
        histories={"SPY": price_rows(90), "AAPL": price_rows(90)},
    )
    request = DistributionEngineRequest(
        benchmark_symbol="SPY",
        positions=[{"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"}],
        cash_balances=[],
        base_currency="USD",
        window_trading_days=60,
    )

    result = run_distribution_engine(request)

    assert result.coverage is not None
    assert result.coverage.effective_start_date is not None
    assert result.coverage.excluded_symbols == []


def test_distribution_engine_fails_closed_when_truncated_below_the_floor(mocker) -> None:
    """AC5 — the MIN_DAILY_OBSERVATIONS floor applies to the EFFECTIVE
    (post-truncation) series: a material symbol covering only the last 10
    days truncates the window below the floor -> trust='unavailable' WITH
    the coverage disclosure attached (never fabricated data to reach the
    floor)."""
    from app.services.distribution_engine import run_distribution_engine
    from app.schemas.distribution import DistributionEngineRequest
    from app.tests.fixtures import install_market_data_mock, price_rows

    full = price_rows(90)
    install_market_data_mock(
        mocker,
        "app.services.distribution_engine",
        histories={"SPY": full, "AAPL": full, "NEWCO": full[-10:]},
    )
    request = DistributionEngineRequest(
        benchmark_symbol="SPY",
        positions=[
            {"symbol": "AAPL", "market_value": 5000.0, "quantity": 50.0, "currency": "USD"},
            {"symbol": "NEWCO", "market_value": 5000.0, "quantity": 100.0, "currency": "USD"},
        ],
        cash_balances=[],
        base_currency="USD",
        window_trading_days=60,
    )

    result = run_distribution_engine(request)

    assert result.trust == "unavailable"
    assert result.var_95 is None
    assert result.coverage is not None
    assert result.coverage.limiting_symbol == "NEWCO"
    assert result.coverage.effective_start_date == full[-10]["date"]


# ── AC2 — the extraction pin: every consumer binds to the shared module ───────


def test_all_engine_consumers_bind_to_the_shared_synthetic_history_symbol() -> None:
    """AC2 — the five coverage-consuming engines import the builder from
    app.services.synthetic_history (object identity, not a re-implementation),
    and the old private diagnostics_engine names are gone."""
    from app.services import (
        attribution_engine,
        correlation_engine,
        diagnostics_engine,
        distribution_engine,
        drawdown_engine,
        stress_engine,
    )
    from app.services import synthetic_history

    for engine in (
        attribution_engine,
        correlation_engine,
        distribution_engine,
        drawdown_engine,
        stress_engine,
    ):
        assert (
            engine.build_synthetic_snapshot_history_states_with_coverage
            is synthetic_history.build_synthetic_snapshot_history_states_with_coverage
        )

    assert not hasattr(diagnostics_engine, "_build_synthetic_snapshot_history_states")
    assert not hasattr(
        diagnostics_engine, "_build_synthetic_snapshot_history_states_with_coverage"
    )
