"""US-26.2: the currency risk engine's wiring.

The pin that matters most here is AC6 — local returns must come from the
REGISTRY FUND CURRENCY, not the broker's listing currency. US-31.5 proved the
two differ, and a wrong assignment is invisible to the identity check (both
legs come from the same wrong split), so it needs its own two-directional test.
"""
from __future__ import annotations

import pytest

from app.core.constants import lookback_calendar_days
from app.schemas.currency_risk import CurrencyRiskRequest
from app.services import currency_risk_engine
from app.services.currency_risk_engine import fund_currency_map, run_currency_risk_engine


def _request(positions: list[dict], window: int = 60) -> CurrencyRiskRequest:
    from app.tests.fixtures import imported_snapshot, position as make_position

    snapshot = imported_snapshot(
        positions=[
            make_position(p["symbol"], market_value=p["market_value"], currency=p["currency"])
            for p in positions
        ],
        ledger_entries=[],
        cash_balances=[],
    )
    return CurrencyRiskRequest.model_validate({"snapshot": snapshot, "window": window})


class _StubMarketData:
    """Records what was asked for, so the test can assert the fetch shape."""

    def __init__(self, prices: dict[str, list[dict]], fx: dict[str, list[dict]]):
        self._prices = prices
        self._fx = fx
        self.price_calls: list[tuple[tuple[str, ...], str, str]] = []
        self.fx_calls: list[tuple[str, str, str]] = []

    def get_historical_prices_for_symbols(self, symbols, from_date, to_date):
        self.price_calls.append((tuple(symbols), from_date, to_date))
        return {s: self._prices.get(s, []) for s in symbols}

    def get_fx_history(self, pair, from_date, to_date):
        self.fx_calls.append((pair, from_date, to_date))
        return self._fx.get(pair, [])


def _rows(n: int, start: float, step: float) -> list[dict]:
    out = []
    value = start
    for i in range(1, n + 1):
        out.append({"date": f"2026-01-{i:02d}", "price": round(value, 6)})
        value *= 1 + step
    return out


def _install(mocker, prices, fx) -> _StubMarketData:
    stub = _StubMarketData(prices, fx)
    mocker.patch.object(currency_risk_engine, "MarketDataService", return_value=stub)
    return stub


def test_local_returns_use_the_registry_fund_currency_not_the_listing(mocker) -> None:
    """AC6, direction 1 — a holding LISTED in EUR whose line QUOTES in USD gets
    a ZERO fx leg. This is the US-31.5 trap: using `position.currency` here
    would invent a EUR leg for a USD-quoted fund."""
    mocker.patch.object(currency_risk_engine, "fund_currency_map", return_value={"DEFS": "USD"})
    stub = _install(mocker, {"DEFS": _rows(40, 100.0, 0.004)}, {})

    # The broker LISTS this position in EUR...
    result = run_currency_risk_engine(
        _request([{"symbol": "DEFS", "market_value": 1000.0, "quantity": 10.0, "currency": "EUR"}])
    )

    # ...but the registry says the line quotes USD, so there is no FX leg at all.
    assert result.trust == "synthetic"
    assert result.currency_variance_share == pytest.approx(0.0, abs=1e-9)
    assert stub.fx_calls == [], "no FX pair should be fetched for a USD-quoting line"


def test_a_genuinely_non_base_line_does_produce_an_fx_leg(mocker) -> None:
    """AC6, direction 2 — the negative pin above must not be satisfiable by
    simply never producing an FX leg."""
    mocker.patch.object(currency_risk_engine, "fund_currency_map", return_value={"SXRV": "EUR"})
    stub = _install(
        mocker,
        {"SXRV": _rows(40, 100.0, 0.006)},
        {"EURUSD": _rows(40, 1.10, 0.001)},
    )

    result = run_currency_risk_engine(
        _request([{"symbol": "SXRV", "market_value": 1000.0, "quantity": 10.0, "currency": "EUR"}])
    )

    assert result.trust == "synthetic"
    assert [pair for pair, _, _ in stub.fx_calls] == ["EURUSD"]
    assert result.currency_variance_share != pytest.approx(0.0, abs=1e-9)


def test_fx_pairs_are_derived_from_the_portfolio_not_a_fixed_list(mocker) -> None:
    mocker.patch.object(
        currency_risk_engine, "fund_currency_map",
        return_value={"SXRV": "EUR", "SEMI": "GBP", "AAPL": "USD"},
    )
    stub = _install(
        mocker,
        {s: _rows(40, 100.0, 0.005) for s in ("SXRV", "SEMI", "AAPL")},
        {"EURUSD": _rows(40, 1.10, 0.001), "GBPUSD": _rows(40, 1.30, 0.002)},
    )

    run_currency_risk_engine(
        _request([
            {"symbol": "SXRV", "market_value": 1000.0, "quantity": 10.0, "currency": "EUR"},
            {"symbol": "SEMI", "market_value": 500.0, "quantity": 5.0, "currency": "GBP"},
            {"symbol": "AAPL", "market_value": 2000.0, "quantity": 20.0, "currency": "USD"},
        ])
    )

    # Exactly the portfolio's own non-base currencies — no USD self-pair, no
    # speculative extras.
    assert sorted(pair for pair, _, _ in stub.fx_calls) == ["EURUSD", "GBPUSD"]


def test_the_lookback_uses_the_shared_heuristic(mocker) -> None:
    """The project standard, not a re-derivation (US-24.3)."""
    from datetime import date, timedelta

    mocker.patch.object(currency_risk_engine, "fund_currency_map", return_value={"AAPL": "USD"})
    stub = _install(mocker, {"AAPL": _rows(40, 100.0, 0.004)}, {})

    run_currency_risk_engine(
        _request([{"symbol": "AAPL", "market_value": 1000.0, "quantity": 10.0, "currency": "USD"}], window=252)
    )

    _symbols, from_date, to_date = stub.price_calls[0]
    expected_from = (date.fromisoformat(to_date) - timedelta(days=lookback_calendar_days(252))).isoformat()
    assert from_date == expected_from
    assert lookback_calendar_days(252) == 434
    assert lookback_calendar_days(60) == 126


def test_a_holding_without_price_history_is_excluded_and_named(mocker) -> None:
    """AC8 — excluded and disclosed, never assigned to the local leg at zero FX
    (which would silently understate currency risk)."""
    mocker.patch.object(
        currency_risk_engine, "fund_currency_map", return_value={"AAPL": "USD", "GHOST": "USD"},
    )
    _install(mocker, {"AAPL": _rows(40, 100.0, 0.004)}, {})

    result = run_currency_risk_engine(
        _request([
            {"symbol": "AAPL", "market_value": 750.0, "quantity": 10.0, "currency": "USD"},
            {"symbol": "GHOST", "market_value": 250.0, "quantity": 5.0, "currency": "USD"},
        ])
    )

    assert result.excluded_symbols == ["GHOST"]
    assert result.excluded_weight == pytest.approx(0.25, abs=1e-6)
    assert result.trust == "synthetic"


def test_an_empty_portfolio_returns_unavailable_without_raising(mocker) -> None:
    _install(mocker, {}, {})
    result = run_currency_risk_engine(_request([]))

    assert result.trust == "unavailable"
    assert result.local_variance_share is None
    assert result.note


def test_thin_history_fails_closed_with_a_stated_reason(mocker) -> None:
    """AC7 — 10 days is well under MIN_DAILY_OBSERVATIONS."""
    mocker.patch.object(currency_risk_engine, "fund_currency_map", return_value={"AAPL": "USD"})
    _install(mocker, {"AAPL": _rows(10, 100.0, 0.004)}, {})

    result = run_currency_risk_engine(
        _request([{"symbol": "AAPL", "market_value": 1000.0, "quantity": 10.0, "currency": "USD"}])
    )

    assert result.trust == "unavailable"
    assert result.local_variance_share is None
    assert "20 overlapping days" in (result.note or "")


def test_fund_currency_map_reads_the_registry() -> None:
    """The real registry, not a mock — SEMI is a GBP-quoting LSE UCITS line."""
    resolved = fund_currency_map(["SEMI", "AAPL"])

    assert resolved.get("SEMI") == "GBP"
    assert resolved.get("AAPL") == "USD"


# ── US-26.2: route contract ────────────────────────────────────────────────


def _client():
    from fastapi.testclient import TestClient

    from app.api.main import app

    return TestClient(app)


def test_route_returns_the_documented_shape(mocker) -> None:
    mocker.patch.object(currency_risk_engine, "fund_currency_map", return_value={"SXRV": "EUR"})
    _install(mocker, {"SXRV": _rows(40, 100.0, 0.006)}, {"EURUSD": _rows(40, 1.10, 0.001)})

    payload = _request(
        [{"symbol": "SXRV", "market_value": 1000.0, "quantity": 10.0, "currency": "EUR"}]
    ).model_dump(mode="json")
    response = _client().post("/engines/currency-risk/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["trust"] == "synthetic"
    assert body["window_days"] == 60
    total = (
        body["local_variance_share"]
        + body["currency_variance_share"]
        + body["interaction_variance_share"]
    )
    assert total == pytest.approx(1.0, abs=1e-6)


def test_route_rejects_an_unsupported_window() -> None:
    payload = _request(
        [{"symbol": "AAPL", "market_value": 1000.0, "quantity": 10.0, "currency": "USD"}]
    ).model_dump(mode="json")
    payload["window"] = 20  # valid for attribution, NOT for this engine

    response = _client().post("/engines/currency-risk/run", json=payload)

    assert response.status_code == 422


def test_route_reports_zero_currency_share_for_an_all_base_portfolio(mocker) -> None:
    mocker.patch.object(currency_risk_engine, "fund_currency_map", return_value={"AAPL": "USD"})
    _install(mocker, {"AAPL": _rows(40, 100.0, 0.004)}, {})

    payload = _request(
        [{"symbol": "AAPL", "market_value": 1000.0, "quantity": 10.0, "currency": "USD"}]
    ).model_dump(mode="json")
    response = _client().post("/engines/currency-risk/run", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["trust"] == "synthetic"
    assert body["currency_variance_share"] == pytest.approx(0.0, abs=1e-9)
