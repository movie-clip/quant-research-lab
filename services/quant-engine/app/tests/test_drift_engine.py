from fastapi.testclient import TestClient

from app.api.main import app
from app.services.drift_engine import run_drift_engine
from app.schemas.drift import DriftEngineRequest


def make_request(**kwargs) -> DriftEngineRequest:
    defaults = {
        "benchmark_symbol": "SPY",
        "positions": [
            {"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"},
            {"symbol": "MSFT", "market_value": 8000.0, "quantity": 25.0, "currency": "USD"},
        ],
        "cash_balances": [],
        "base_currency": "USD",
    }
    defaults.update(kwargs)
    return DriftEngineRequest(**defaults)


def test_drift_engine_returns_five_windows():
    request = make_request()
    result = run_drift_engine(request)
    assert len(result.windows) == 5
    labels = [w.label for w in result.windows]
    assert "1M" in labels
    assert "3M" in labels
    assert "6M" in labels
    assert "12M" in labels
    assert "Since Import" in labels


def test_drift_engine_since_import_unavailable_without_imported_at():
    # US-30.3 (AC5 fail-closed): no statement_period AND no imported_at → no
    # anchor → the window fails closed.
    request = make_request()  # neither statement_period nor imported_at
    result = run_drift_engine(request)
    since_import = next(w for w in result.windows if w.label == "Since Import")
    assert since_import.trust == "unavailable"


def test_since_import_anchor_prefers_statement_period_start():
    """US-30.3 (AC5 / F-5) — the anchor is the statement-period START (not the
    import timestamp); a malformed/absent period falls back to imported_at,
    then to None. Pure-function pin, no market data."""
    from datetime import date, datetime

    from app.services.drift_engine import _since_import_anchor

    imported = datetime(2026, 7, 8, 12, 0, 0)
    # Period start wins over imported_at (the F-5 fix).
    assert _since_import_anchor("2026-01-01 - 2026-06-30", imported) == date(2026, 1, 1)
    # No period → imported_at.date() (prior behaviour).
    assert _since_import_anchor(None, imported) == date(2026, 7, 8)
    # Malformed period → imported_at fallback (never raises).
    assert _since_import_anchor("not-a-period", imported) == date(2026, 7, 8)
    assert _since_import_anchor("2026-13-99 - x", imported) == date(2026, 7, 8)
    # Neither → None (caller fails the window closed).
    assert _since_import_anchor(None, None) is None


def test_since_import_window_available_with_statement_period(mocker):
    """US-30.3 (AC5 / F-5) — with a statement_period the "Since Import" window
    is a real window (synthetic + computed return), not the pre-fix
    `unavailable` that imported_at ≈ today produced."""
    from app.tests.fixtures import install_market_data_mock, price_rows

    inst = install_market_data_mock(
        mocker,
        "app.services.drift_engine",
        histories={"SPY": price_rows(180), "AAPL": price_rows(180), "MSFT": price_rows(180)},
    )
    inst.get_direct_verified_benchmark_history.side_effect = (
        lambda sym, *a, **k: price_rows(180)
    )

    result = run_drift_engine(make_request(statement_period="2026-01-01 - 2026-06-30"))

    since_import = next(w for w in result.windows if w.label == "Since Import")
    assert since_import.trust == "synthetic"
    assert since_import.portfolio_return_pct is not None


def test_drift_engine_returns_valid_availability():
    request = make_request()
    result = run_drift_engine(request)
    assert result.availability in ("available", "partial", "unavailable")
    assert result.benchmark_symbol == "SPY"


def test_drift_engine_spread_is_none_when_data_unavailable():
    request = make_request(positions=[])  # empty portfolio
    result = run_drift_engine(request)
    for w in result.windows:
        if w.trust == "unavailable":
            assert w.spread_pct is None


def test_drift_route_exists():
    client = TestClient(app)
    response = client.post(
        "/engines/drift/run",
        json={
            "benchmark_symbol": "SPY",
            "positions": [{"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0}],
            "cash_balances": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "windows" in body
    assert "benchmark_symbol" in body
    assert body["benchmark_symbol"] == "SPY"


# ── US-27.8: TWR window basis + FX-fallback disclosure ────────────────────────

def _drift_state(date_str: str, value: float, external_cash_flow: float = 0.0):
    from app.schemas.reconciliation import DailyPortfolioState

    return DailyPortfolioState(
        date=date_str,
        cash={"USD": 0.0},
        positions=[],
        total_market_value=value,
        total_portfolio_value=value,
        external_cash_flow=external_cash_flow,
    )


def test_drift_portfolio_return_is_cash_flow_neutral():
    """US-27.8 (audit F10), retained on the LEDGER basis (US-30.1 AC5) — a
    mid-window 1000 deposit with flat prices must report ~0%; a real price
    move with no flows is measured exactly."""
    from app.services.drift_engine import _portfolio_return

    deposit_only = [
        _drift_state("2026-01-02", 1000.0),
        _drift_state("2026-01-03", 2000.0, external_cash_flow=1000.0),
        _drift_state("2026-01-04", 2000.0),
    ]
    assert _portfolio_return(deposit_only, use_ledger_basis=True) == (0.0, False)

    price_move_only = [
        _drift_state("2026-01-02", 1000.0),
        _drift_state("2026-01-03", 1030.0),   # +3%
        _drift_state("2026-01-04", 1060.9),   # +3%
    ]
    assert _portfolio_return(price_move_only, use_ledger_basis=True) == (6.09, False)  # 1.03² − 1


def test_drift_daily_series_is_twr_indexed():
    """US-27.8 (AC4), retained on the LEDGER basis — the chart line is the TWR
    chain indexed to 100: the deposit day stays flat instead of drawing a fake
    +100% move."""
    from app.services.drift_engine import _build_daily_series

    states = [
        _drift_state("2026-01-02", 1000.0),
        _drift_state("2026-01-03", 2000.0, external_cash_flow=1000.0),
        _drift_state("2026-01-04", 2100.0),  # +5% real move on 2000 base
    ]
    benchmark_rows = [
        {"date": "2026-01-02", "price": 100.0},
        {"date": "2026-01-03", "price": 101.0},
        {"date": "2026-01-04", "price": 102.0},
    ]

    series = _build_daily_series(states, benchmark_rows, use_ledger_basis=True)
    by_date = {p.date: p.portfolio_indexed for p in series}

    assert by_date["2026-01-02"] == 100.0
    assert by_date["2026-01-03"] == 100.0   # deposit is not a chart move
    assert by_date["2026-01-04"] == 105.0   # the real +5%


def test_drift_note_states_the_synthetic_basis_on_the_no_ledger_path(mocker):
    """US-30.1 (AC3) — the request path carries no ledger, so available
    windows state the synthetic market-value-chain convention; the
    ledger-replay claim must NOT appear."""
    from app.tests.fixtures import install_market_data_mock, price_rows

    inst = install_market_data_mock(
        mocker,
        "app.services.drift_engine",
        histories={"SPY": price_rows(80), "AAPL": price_rows(80), "MSFT": price_rows(80)},
    )
    inst.get_direct_verified_benchmark_history.side_effect = (
        lambda sym, *a, **k: price_rows(80)
    )

    result = run_drift_engine(make_request())

    synthetic = [w for w in result.windows if w.trust == "synthetic"]
    assert synthetic, "expected at least one available window"
    for w in synthetic:
        assert "Synthetic: current holdings" in (w.note or "")
        assert "Broker-ledger replay" not in (w.note or "")


def test_drift_note_selection_per_basis_and_degradation():
    """US-30.1 (AC3) — unit pin on the note chooser: ledger basis keeps the
    US-27.8 replay claim; no-ledger gets the synthetic convention; a degraded
    chain names the reason; unavailable-without-degradation stays bare."""
    from app.services.drift_engine import (
        DEGRADED_VALUATION_NOTE,
        LEDGER_REPLAY_NOTE,
        SYNTHETIC_BASIS_NOTE,
        _basis_note,
    )

    assert _basis_note(5.0, False, use_ledger_basis=True) == LEDGER_REPLAY_NOTE
    assert _basis_note(5.0, False, use_ledger_basis=False) == SYNTHETIC_BASIS_NOTE
    assert _basis_note(None, True, use_ledger_basis=False) == DEGRADED_VALUATION_NOTE
    assert _basis_note(None, False, use_ledger_basis=False) is None


def test_drift_surfaces_fx_fallback_currencies_for_non_base_positions(mocker):
    """US-27.8 (audit F9) — a EUR position valued with fx_history={} is
    carried unconverted AND disclosed; USD-only portfolios disclose nothing."""
    from app.tests.fixtures import install_market_data_mock, price_rows

    inst = install_market_data_mock(
        mocker,
        "app.services.drift_engine",
        histories={"SPY": price_rows(80), "AAPL": price_rows(80), "SXRV": price_rows(80)},
    )
    inst.get_direct_verified_benchmark_history.side_effect = (
        lambda sym, *a, **k: price_rows(80)
    )
    request = make_request(positions=[
        {"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"},
        {"symbol": "SXRV", "market_value": 5000.0, "quantity": 5.0, "currency": "EUR"},
    ])

    result = run_drift_engine(request)

    assert result.fx_fallback_currencies == ["EUR"]

    inst = install_market_data_mock(
        mocker,
        "app.services.drift_engine",
        histories={"SPY": price_rows(80), "AAPL": price_rows(80)},
    )
    inst.get_direct_verified_benchmark_history.side_effect = (
        lambda sym, *a, **k: price_rows(80)
    )
    usd_only = run_drift_engine(make_request())
    assert usd_only.fx_fallback_currencies == []


# ── US-30.1: drift valuation basis (audit F-1) + fail-closed chain (F-2) ─────

def _mv_state(date_str: str, market_value: float, portfolio_value: float):
    from app.schemas.reconciliation import DailyPortfolioState

    return DailyPortfolioState(
        date=date_str,
        cash={"USD": 0.0},
        positions=[],
        total_market_value=market_value,
        total_portfolio_value=portfolio_value,
        external_cash_flow=0.0,
    )


def test_no_ledger_basis_is_the_market_value_chain():
    """US-30.1 (AC1) — F-1 regression: the no-ledger basis compounds
    total_market_value and NEVER touches total_portfolio_value. The fixture
    reproduces the bug shape: sane market values, garbage portfolio values
    (the broken −opening_value cash anchor)."""
    from app.services.drift_engine import _portfolio_return

    states = [
        _mv_state("2026-01-02", 62000.0, 0.0),      # pv broken exactly as F-1
        _mv_state("2026-01-03", 63240.0, -900.0),   # mv +2%
        _mv_state("2026-01-04", 64504.8, 740.0),    # mv +2%
    ]
    pct, degraded = _portfolio_return(states, use_ledger_basis=False)
    assert degraded is False
    assert pct == 4.04  # 1.02² − 1 — from market values, untouched by the pv garbage


def test_no_ledger_chain_reports_none_when_no_return_is_computable():
    """US-30.1 — an all-zero market-value window has no claimable return:
    None, never a fabricated flat 0.0%."""
    from app.services.drift_engine import _portfolio_return

    states = [_mv_state(f"2026-01-0{i}", 0.0, 0.0) for i in range(2, 5)]
    assert _portfolio_return(states, use_ledger_basis=False) == (None, False)


def test_impossible_daily_return_fails_the_window_closed():
    """US-30.1 (AC2) — a ≤ −100% daily return on the ledger basis (the F-2
    shape: portfolio value crossing zero) withholds the window: (None,
    degraded=True), never a compounded number."""
    from app.services.drift_engine import _portfolio_return

    states = [
        _drift_state("2026-01-02", 740.0),
        _drift_state("2026-01-03", -226.0),   # −130% day — impossible
        _drift_state("2026-01-04", 101.0),
    ]
    assert _portfolio_return(states, use_ledger_basis=True) == (None, True)


def test_degraded_chain_withholds_the_chart_portfolio_line():
    """US-30.1 (AC2/AC4) — the daily series built from a degraded chain keeps
    the benchmark line and nulls every portfolio point (explicit withholding,
    no partial fabricated chain)."""
    from app.services.drift_engine import _build_daily_series

    states = [
        _drift_state("2026-01-02", 740.0),
        _drift_state("2026-01-03", -226.0),
        _drift_state("2026-01-04", 101.0),
    ]
    benchmark_rows = [{"date": s.date, "price": 100.0 + i} for i, s in enumerate(states)]

    series = _build_daily_series(states, benchmark_rows, use_ledger_basis=True)

    assert len(series) == 3
    assert all(p.portfolio_indexed is None for p in series)
    assert all(p.benchmark_indexed is not None for p in series)


def test_chart_final_index_equals_the_window_return():
    """US-30.1 (AC4) — one chain, two views: the chart's final indexed value
    minus 100 IS the window return, on both bases."""
    from app.services.drift_engine import _build_daily_series, _portfolio_return

    states = [
        _mv_state("2026-01-02", 1000.0, 1000.0),
        _mv_state("2026-01-03", 1030.0, 1030.0),
        _mv_state("2026-01-04", 1060.9, 1060.9),
    ]
    benchmark_rows = [{"date": s.date, "price": 100.0} for s in states]

    for use_ledger in (False, True):
        pct, _ = _portfolio_return(states, use_ledger_basis=use_ledger)
        series = _build_daily_series(states, benchmark_rows, use_ledger_basis=use_ledger)
        assert round(series[-1].portfolio_indexed - 100.0, 2) == pct


def test_state_engine_anchors_cash_from_balances_when_starting_nav_absent():
    """US-30.1 (AC6) — F-1 root-cause pin: without statement_totals the cash
    anchor is the snapshot's own cash balances, so day-one portfolio value is
    market value + real cash — not (market value − opening value) ≈ 0."""
    from app.engine.portfolio_state import PortfolioStateEngine
    from app.schemas.imports import ImportedPortfolioSnapshot
    from app.tests.fixtures import imported_snapshot, position

    dates = ["2026-01-02", "2026-01-03"]
    rows = [{"date": dates[0], "price": 100.0}, {"date": dates[1], "price": 102.0}]
    payload = imported_snapshot(
        positions=[position("AAPL", market_value=1000.0, quantity=10.0, currency="USD")],
    )
    payload["statement_totals"] = None
    payload["cash_balances"] = [{"currency": "USD", "ending_cash": 500.0}]
    snapshot = ImportedPortfolioSnapshot.model_validate(payload)

    engine = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history={})
    states = engine.build_daily_states(price_histories={"AAPL": rows}, valuation_dates=dates)

    assert states[0].total_market_value == 1000.0   # 10 × 100
    assert states[0].total_portfolio_value == 1500.0  # mv + REAL cash, not 0.0
    assert states[1].total_portfolio_value == 1520.0  # 10 × 102 + 500


def test_state_engine_keeps_starting_nav_anchor_when_totals_present():
    """US-30.1 (AC6/AC7) — dashboard-path regression: with a starting NAV the
    legacy anchor (starting_nav − opening value) is byte-identical."""
    from app.engine.portfolio_state import PortfolioStateEngine
    from app.schemas.imports import ImportedPortfolioSnapshot
    from app.tests.fixtures import imported_snapshot, position

    dates = ["2026-01-02", "2026-01-03"]
    rows = [{"date": dates[0], "price": 100.0}, {"date": dates[1], "price": 102.0}]
    payload = imported_snapshot(
        positions=[position("AAPL", market_value=1000.0, quantity=10.0, currency="USD")],
    )
    payload["statement_totals"] = {"starting_nav": 1200.0}
    payload["cash_balances"] = [{"currency": "USD", "ending_cash": 500.0}]
    snapshot = ImportedPortfolioSnapshot.model_validate(payload)

    engine = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history={})
    states = engine.build_daily_states(price_histories={"AAPL": rows}, valuation_dates=dates)

    # base_cash = 1200 − (10 × 100) = 200; pv day one = 1000 + 200.
    assert states[0].total_portfolio_value == 1200.0
    assert states[1].total_portfolio_value == 1220.0


def test_drift_end_to_end_returns_sane_windows_for_a_no_ledger_request(mocker):
    """US-30.1 (AC1) — e2e smoke on the request path with deterministic
    prices: every available window's return sits in (−100, +100)% and
    availability is not 'unavailable' (the F-1 garbage was ±thousands)."""
    from app.tests.fixtures import install_market_data_mock, price_rows

    inst = install_market_data_mock(
        mocker,
        "app.services.drift_engine",
        histories={"SPY": price_rows(400), "AAPL": price_rows(400), "MSFT": price_rows(400)},
    )
    inst.get_direct_verified_benchmark_history.side_effect = (
        lambda sym, *a, **k: price_rows(400)
    )

    result = run_drift_engine(make_request(cash_balances=[{"currency": "USD", "amount": 1500.0}]))

    available = [w for w in result.windows if w.portfolio_return_pct is not None]
    assert available, "expected available windows with deterministic prices"
    for w in available:
        assert -100.0 < w.portfolio_return_pct < 100.0, w
    assert result.availability != "unavailable"


def test_portfolio_state_engine_records_fx_fallback_only_when_rate_missing():
    """Unit-level F9 pin: a present rate converts (not recorded); a missing
    rate carries the raw value AND records the currency."""
    from app.engine.portfolio_state import PortfolioStateEngine
    from app.schemas.imports import ImportedPortfolioSnapshot
    from app.tests.fixtures import imported_snapshot, position

    dates = ["2026-01-02", "2026-01-03"]
    rows = [{"date": d, "price": 100.0} for d in dates]
    snapshot = ImportedPortfolioSnapshot.model_validate(imported_snapshot(
        positions=[position("SXRV", market_value=1000.0, quantity=10.0, currency="EUR")],
    ))

    with_rate = PortfolioStateEngine(
        snapshot=snapshot, base_currency="USD",
        fx_history={f"EURUSD:{d}": 1.10 for d in dates},
    )
    states = with_rate.build_daily_states(price_histories={"SXRV": rows}, valuation_dates=dates)
    assert with_rate.fx_fallback_currencies == set()
    assert states[-1].positions[0].market_value == 1100.0  # 10 × 100 × 1.10

    without_rate = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history={})
    states = without_rate.build_daily_states(price_histories={"SXRV": rows}, valuation_dates=dates)
    assert without_rate.fx_fallback_currencies == {"EUR"}
    assert states[-1].positions[0].market_value == 1000.0  # carried unconverted


# ── US-30.2: statement-anchored disclosure (F-3) + three-tier FX (F-6) ────────

def _engine_for(positions, price_histories, dates, fx_history=None):
    from app.engine.portfolio_state import PortfolioStateEngine
    from app.schemas.imports import ImportedPortfolioSnapshot
    from app.tests.fixtures import imported_snapshot

    payload = imported_snapshot(positions=positions)
    payload["statement_totals"] = None
    payload["cash_balances"] = []
    snapshot = ImportedPortfolioSnapshot.model_validate(payload)
    engine = PortfolioStateEngine(snapshot=snapshot, base_currency="USD", fx_history=fx_history or {})
    states = engine.build_daily_states(price_histories=price_histories, valuation_dates=dates)
    return engine, states


def test_state_engine_records_statement_anchored_symbols():
    """US-30.2 (AC1/F-3) — a held symbol with zero in-window price coverage is
    valued flat at the statement close AND recorded as anchored; covered
    symbols are not."""
    from app.tests.fixtures import position

    dates = ["2026-01-02", "2026-01-03"]
    engine, states = _engine_for(
        positions=[
            position("AAPL", market_value=1000.0, quantity=10.0, currency="USD"),
            position("LQQ", market_value=500.0, quantity=1.0, currency="USD"),
        ],
        price_histories={"AAPL": [{"date": d, "price": 100.0} for d in dates]},  # LQQ: none
        dates=dates,
    )
    assert engine.statement_anchored_symbols == {"LQQ"}
    lqq_values = [p.market_value for s in states for p in s.positions if p.symbol == "LQQ"]
    assert lqq_values == [50.0, 50.0]  # flat statement close (mv/10 per fixture) both days


def test_state_engine_records_no_anchored_symbols_when_fully_covered():
    from app.tests.fixtures import position

    dates = ["2026-01-02", "2026-01-03"]
    engine, _ = _engine_for(
        positions=[position("AAPL", market_value=1000.0, quantity=10.0, currency="USD")],
        price_histories={"AAPL": [{"date": d, "price": 100.0} for d in dates]},
        dates=dates,
    )
    assert engine.statement_anchored_symbols == set()


def test_drift_result_surfaces_statement_anchored_symbols(mocker):
    """US-30.2 (AC1) — the anchored set flows to DriftResult (e2e, one symbol
    with no provider rows)."""
    from app.tests.fixtures import install_market_data_mock, price_rows

    inst = install_market_data_mock(
        mocker,
        "app.services.drift_engine",
        histories={"SPY": price_rows(80), "AAPL": price_rows(80), "MSFT": []},
    )
    inst.get_direct_verified_benchmark_history.side_effect = (
        lambda sym, *a, **k: price_rows(80)
    )

    result = run_drift_engine(make_request())

    assert result.statement_anchored_symbols == ["MSFT"]


def test_static_fx_rate_converts_and_discloses_in_its_own_tier():
    """US-30.2 (AC2) — a supplied statement-implied rate converts every
    valuation date; nothing lands in the fallback tier."""
    from app.tests.fixtures import position

    dates = ["2026-01-02", "2026-01-03"]
    fx = {f"EURUSD:{d}": 1.10 for d in dates}
    engine, states = _engine_for(
        positions=[position("SXRV", market_value=1000.0, quantity=10.0, currency="EUR")],
        price_histories={"SXRV": [{"date": d, "price": 100.0} for d in dates]},
        dates=dates,
        fx_history=fx,
    )
    assert engine.fx_fallback_currencies == set()
    assert all(s.positions[0].market_value == 1100.0 for s in states)  # 10 x 100 x 1.10


def test_mixed_currencies_disclose_each_in_exactly_one_tier(mocker):
    """US-30.2 (AC3) — EUR has a supplied rate (static tier); GBP does not
    (fallback tier); no currency appears in both."""
    from app.tests.fixtures import install_market_data_mock, price_rows

    inst = install_market_data_mock(
        mocker,
        "app.services.drift_engine",
        histories={"SPY": price_rows(80), "SXRV": price_rows(80), "SEMI": price_rows(80)},
    )
    inst.get_direct_verified_benchmark_history.side_effect = (
        lambda sym, *a, **k: price_rows(80)
    )
    request = make_request(
        positions=[
            {"symbol": "SXRV", "market_value": 5000.0, "quantity": 5.0, "currency": "EUR"},
            {"symbol": "SEMI", "market_value": 2700.0, "quantity": 150.0, "currency": "GBP"},
        ],
        fx_rates={"EURUSD": 1.1422},
    )

    result = run_drift_engine(request)

    assert result.fx_static_rate_currencies == ["EUR"]
    assert result.fx_fallback_currencies == ["GBP"]
    assert set(result.fx_static_rate_currencies) & set(result.fx_fallback_currencies) == set()


def test_empty_fx_rates_is_byte_identical_to_the_fallback_behaviour(mocker):
    """US-30.2 (AC6) — without fx_rates the result equals the US-30.1
    behaviour exactly (fallback tier only, same windows)."""
    from app.tests.fixtures import install_market_data_mock, price_rows

    def _mock():
        inst = install_market_data_mock(
            mocker,
            "app.services.drift_engine",
            histories={"SPY": price_rows(80), "AAPL": price_rows(80), "SXRV": price_rows(80)},
        )
        inst.get_direct_verified_benchmark_history.side_effect = (
            lambda sym, *a, **k: price_rows(80)
        )

    positions = [
        {"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"},
        {"symbol": "SXRV", "market_value": 5000.0, "quantity": 5.0, "currency": "EUR"},
    ]
    _mock()
    without_field = run_drift_engine(make_request(positions=positions))
    _mock()
    with_empty = run_drift_engine(make_request(positions=positions, fx_rates={}))

    assert without_field.model_dump() == with_empty.model_dump()
    assert with_empty.fx_fallback_currencies == ["EUR"]
    assert with_empty.fx_static_rate_currencies == []


def test_drift_route_accepts_fx_rates_and_returns_disclosure_tiers():
    """US-30.2 (AC2, route) — the request field round-trips and the response
    body carries all three disclosure fields."""
    client = TestClient(app)
    response = client.post(
        "/engines/drift/run",
        json={
            "benchmark_symbol": "SPY",
            "positions": [{"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0}],
            "cash_balances": [],
            "fx_rates": {"EURUSD": 1.1422},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "fx_static_rate_currencies" in body
    assert "statement_anchored_symbols" in body
    assert "fx_fallback_currencies" in body


def test_static_rate_scales_levels_but_not_single_currency_returns():
    """US-30.2 (AC2/notes) — a static rate multiplies a single-currency
    series by a constant: the window return is identical with or without it
    (the honesty is in the disclosed tier, not a different number)."""
    from app.services.drift_engine import _portfolio_return
    from app.tests.fixtures import position

    dates = ["2026-01-02", "2026-01-03", "2026-01-06"]
    prices = [
        {"date": dates[0], "price": 100.0},
        {"date": dates[1], "price": 103.0},
        {"date": dates[2], "price": 106.09},
    ]

    _, states_no_fx = _engine_for(
        positions=[position("SXRV", market_value=1000.0, quantity=10.0, currency="EUR")],
        price_histories={"SXRV": prices}, dates=dates,
    )
    _, states_fx = _engine_for(
        positions=[position("SXRV", market_value=1000.0, quantity=10.0, currency="EUR")],
        price_histories={"SXRV": prices}, dates=dates,
        fx_history={f"EURUSD:{d}": 1.10 for d in dates},
    )

    assert _portfolio_return(states_no_fx, use_ledger_basis=False) == (6.09, False)
    assert _portfolio_return(states_fx, use_ledger_basis=False) == (6.09, False)
    assert states_fx[0].total_market_value == round(states_no_fx[0].total_market_value * 1.10, 2)
