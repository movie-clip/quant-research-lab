"""Tests for the portfolio data-provenance engine + route (US-18.2).

MarketDataService is mocked — no network.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.provenance import ProvenanceRequest
from app.services.provenance_engine import run_provenance


def _position(symbol: str) -> dict:
    return {
        "as_of_date": "2024-12-31",
        "symbol": symbol,
        "quantity": 10.0,
        "cost_basis": 800.0,
        "close_price": 100.0,
        "market_value": 1000.0,
        "unrealized_pnl": 200.0,
        "currency": "USD",
    }


def _snapshot(symbols: list[str]) -> dict:
    return {
        "statement": {
            "importer": "interactive_brokers",
            "imported_at": "2024-12-31T00:00:00",
            "source_path": "/test/fixture.csv",
            "detected_format": "ib_flex_2023",
        },
        "instruments": [],
        "positions": [_position(s) for s in symbols],
        "cash_balances": [],
        "ledger_entries": [],
    }


def _request(symbols: list[str]) -> ProvenanceRequest:
    return ProvenanceRequest.model_validate({"snapshot": _snapshot(symbols), "lookback_days": 30})


def _install_md(mocker, vendor_by_symbol: dict[str, str | None]):
    """vendor_by_symbol: symbol -> 'fmp' | 'yfinance' | None (None = unpriced)."""
    mock_svc = MagicMock()
    inst = mock_svc.return_value

    def _hist(sym, start, end, *a, **k):
        return [{"date": "2024-01-02", "price": 1.0}] if vendor_by_symbol.get(sym) else []

    inst.get_historical_prices.side_effect = _hist
    inst.last_fetch_meta = {s: {"vendor": v} for s, v in vendor_by_symbol.items() if v}
    mocker.patch("app.services.provenance_engine.MarketDataService", mock_svc)


def test_classifies_mixed_providers(mocker):
    _install_md(mocker, {"AAPL": "fmp", "VUAA": "yfinance", "ZZZ": None})
    res = run_provenance(_request(["AAPL", "VUAA", "ZZZ"]))
    assert res.fmp_symbols == ["AAPL"]
    assert res.yahoo_sourced_symbols == ["VUAA"]
    assert res.unavailable_symbols == ["ZZZ"]
    vendors = {h.symbol: h.vendor for h in res.holdings}
    assert vendors == {"AAPL": "fmp", "VUAA": "yfinance", "ZZZ": "unavailable"}


def test_all_fmp_portfolio_has_no_yahoo(mocker):
    _install_md(mocker, {"AAPL": "fmp", "MSFT": "fmp"})
    res = run_provenance(_request(["AAPL", "MSFT"]))
    assert res.yahoo_sourced_symbols == []
    assert set(res.fmp_symbols) == {"AAPL", "MSFT"}


def test_empty_positions_returns_empty_groups(mocker):
    _install_md(mocker, {})
    res = run_provenance(_request([]))
    assert res.holdings == []
    assert res.fmp_symbols == [] and res.yahoo_sourced_symbols == [] and res.unavailable_symbols == []


def test_no_history_symbol_is_unavailable(mocker):
    _install_md(mocker, {"VUAA": "yfinance", "NOPE": None})
    res = run_provenance(_request(["VUAA", "NOPE"]))
    assert res.unavailable_symbols == ["NOPE"]
    assert res.yahoo_sourced_symbols == ["VUAA"]


def test_route_returns_grouped_shape(mocker):
    _install_md(mocker, {"AAPL": "fmp", "VUAA": "yfinance"})
    client = TestClient(app)
    response = client.post("/engines/provenance/run", json={"snapshot": _snapshot(["AAPL", "VUAA"]), "lookback_days": 30})
    assert response.status_code == 200
    data = response.json()
    assert set(data.keys()) >= {"holdings", "fmp_symbols", "yahoo_sourced_symbols", "unavailable_symbols", "lookback_days"}
    assert data["yahoo_sourced_symbols"] == ["VUAA"]


# ── Identity warnings (US-19.1) ─────────────────────────────────────────────────

def _snapshot_with_instruments(instruments: list[dict]) -> dict:
    snap = _snapshot([])  # no positions → run_provenance early-returns (no market data)
    snap["instruments"] = instruments
    return snap


def test_identity_warnings_surfaced_for_mislabeled_holding():
    # VUAA is registry-known as "Vanguard S&P 500 UCITS ETF".
    req = ProvenanceRequest.model_validate({
        "snapshot": _snapshot_with_instruments([
            {"symbol": "VUAA", "description": "iShares Core MSCI World UCITS ETF"},
        ]),
        "lookback_days": 30,
    })
    res = run_provenance(req)
    assert len(res.identity_warnings) == 1
    assert res.identity_warnings[0].symbol == "VUAA"


def test_identity_warnings_empty_when_consistent():
    req = ProvenanceRequest.model_validate({
        "snapshot": _snapshot_with_instruments([
            {"symbol": "VUAA", "description": "VANGUARD S&P 500 UCITS ETF USD ACC"},
        ]),
        "lookback_days": 30,
    })
    res = run_provenance(req)
    assert res.identity_warnings == []
