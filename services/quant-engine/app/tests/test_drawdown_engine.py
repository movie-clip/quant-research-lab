"""Engine + route tests for the standalone drawdown analytics engine.

Service-level tests hit the FMP cache via MarketDataService (same pattern
as test_stress_engine.py and test_drift_engine.py). Route tests use
TestClient with the canonical PortfolioEngineRequest-shaped payload.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.drawdown import DrawdownEngineRequest
from app.services.drawdown_engine import run_drawdown_engine


def _make_request(**kwargs) -> DrawdownEngineRequest:
    """Same canonical helper shape as test_stress_engine._make_request — the
    PortfolioEngineRequest schema accepts the flat positions/imported_at/
    benchmark_symbol shape."""
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
    return DrawdownEngineRequest(**defaults)


# ── Service-level tests ───────────────────────────────────────────────────────


def test_run_drawdown_engine_returns_synthetic_for_real_portfolio() -> None:
    """Real AAPL + MSFT portfolio over default window (None = max). FMP cache
    provides multi-year history → underwater curve is non-empty, scalars
    are populated, drawdown is non-positive."""
    request = _make_request()
    result = run_drawdown_engine(request)

    assert result.trust == "synthetic"
    assert len(result.underwater_series) >= 20
    assert result.current_drawdown_pct is not None
    assert result.max_drawdown_pct is not None
    # Drawdown is by construction ≤ 0
    assert result.max_drawdown_pct <= 0
    # Sanity: current is at least as good as the worst (or equal)
    assert result.current_drawdown_pct >= result.max_drawdown_pct


def test_run_drawdown_engine_returns_unavailable_when_no_positions() -> None:
    """Empty positions → fail-closed: trust='unavailable', every list empty,
    every scalar None. No fabrication."""
    request = _make_request(positions=[])
    result = run_drawdown_engine(request)

    assert result.trust == "unavailable"
    assert result.underwater_series == []
    assert result.episodes == []
    assert result.current_drawdown_pct is None
    assert result.max_drawdown_pct is None


# ── Route-level tests ─────────────────────────────────────────────────────────


def test_post_drawdown_run_returns_200_with_valid_response_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/engines/drawdown/run",
        json={
            "benchmark_symbol": "SPY",
            "positions": [
                {"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"},
            ],
            "cash_balances": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    expected_keys = {
        "window_trading_days",
        "underwater_series",
        "current_drawdown_pct",
        "max_drawdown_pct",
        "episodes",
        "trust",
    }
    assert expected_keys <= body.keys()
    assert body["trust"] in ("synthetic", "unavailable")
    assert isinstance(body["underwater_series"], list)
    assert isinstance(body["episodes"], list)


def test_post_drawdown_run_returns_422_on_malformed_payload() -> None:
    """Wrong type for window_trading_days fails Pydantic validation with 422."""
    client = TestClient(app)
    response = client.post(
        "/engines/drawdown/run",
        json={"window_trading_days": "not-an-int"},
    )
    assert response.status_code == 422
