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
    request = make_request()  # no imported_at
    result = run_drift_engine(request)
    since_import = next(w for w in result.windows if w.label == "Since Import")
    assert since_import.trust == "unavailable"


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
    """US-27.8 (audit F10) — a mid-window 1000 deposit with flat prices must
    report ~0% (the pre-fix last/first market-value ratio reported +100%);
    a real price move with no flows is measured exactly."""
    from app.services.drift_engine import _portfolio_return

    deposit_only = [
        _drift_state("2026-01-02", 1000.0),
        _drift_state("2026-01-03", 2000.0, external_cash_flow=1000.0),
        _drift_state("2026-01-04", 2000.0),
    ]
    assert _portfolio_return(deposit_only) == 0.0

    price_move_only = [
        _drift_state("2026-01-02", 1000.0),
        _drift_state("2026-01-03", 1030.0),   # +3%
        _drift_state("2026-01-04", 1060.9),   # +3%
    ]
    assert _portfolio_return(price_move_only) == 6.09  # 1.03² − 1


def test_drift_daily_series_is_twr_indexed():
    """US-27.8 (AC4) — the chart line is the TWR chain indexed to 100: the
    deposit day stays flat instead of drawing a fake +100% move."""
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

    series = _build_daily_series(states, benchmark_rows)
    by_date = {p.date: p.portfolio_indexed for p in series}

    assert by_date["2026-01-02"] == 100.0
    assert by_date["2026-01-03"] == 100.0   # deposit is not a chart move
    assert by_date["2026-01-04"] == 105.0   # the real +5%


def test_drift_note_states_the_ledger_replay_twr_basis(mocker):
    """US-27.8 (AC3) — the basis label on available windows describes what the
    engine actually does (ledger replay + TWR), not the synthetic convention."""
    from app.tests.fixtures import install_market_data_mock, price_rows

    inst = install_market_data_mock(
        mocker,
        "app.services.drift_engine",
        histories={"SPY": price_rows(80), "AAPL": price_rows(80), "MSFT": price_rows(80)},
    )
    # Drift fetches SPY through the verified-benchmark endpoint; serve the
    # same deterministic rows there.
    inst.get_direct_verified_benchmark_history.side_effect = (
        lambda sym, *a, **k: price_rows(80)
    )

    result = run_drift_engine(make_request())

    synthetic = [w for w in result.windows if w.trust == "synthetic"]
    assert synthetic, "expected at least one available window"
    for w in synthetic:
        assert "Broker-ledger replay" in (w.note or "")
        assert "time-weighted" in (w.note or "")


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
