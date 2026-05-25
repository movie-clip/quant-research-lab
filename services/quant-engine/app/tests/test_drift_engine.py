import pytest
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
