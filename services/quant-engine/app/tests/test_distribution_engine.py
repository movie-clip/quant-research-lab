"""Engine + route tests for the standalone distribution analytics engine.

Service-level tests hit the FMP cache via MarketDataService (same pattern
as test_drawdown_engine.py). Route tests use TestClient with the canonical
PortfolioEngineRequest-shaped payload.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.distribution import DistributionEngineRequest
from app.services.distribution_engine import run_distribution_engine


def _make_request(**kwargs) -> DistributionEngineRequest:
    """Canonical helper — same shape as test_stress_engine + test_drawdown_engine."""
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
    return DistributionEngineRequest(**defaults)


# ── Service-level tests ───────────────────────────────────────────────────────


def test_run_distribution_engine_returns_synthetic_for_real_portfolio() -> None:
    """Real AAPL + MSFT portfolio, default window 252. FMP cache provides
    multi-year history → return_count ≥ 20, var_95 + cvar_95 non-None,
    CVaR ≥ VaR coherence sanity holds."""
    request = _make_request()
    result = run_distribution_engine(request)

    assert result.trust == "synthetic"
    assert result.return_count >= 20
    assert result.var_95 is not None
    assert result.cvar_95 is not None
    # Coherent risk measure invariant (Acerbi & Tasche 2002): CVaR ≥ VaR.
    assert result.cvar_95 >= result.var_95


def test_run_distribution_engine_returns_unavailable_when_no_positions() -> None:
    """Empty positions → fail-closed: trust='unavailable', return_count=0,
    every scalar None, histogram_bins=[]. No fabrication."""
    request = _make_request(positions=[])
    result = run_distribution_engine(request)

    assert result.trust == "unavailable"
    assert result.return_count == 0
    assert result.var_95 is None
    assert result.var_99 is None
    assert result.cvar_95 is None
    assert result.percentile_50 is None
    assert result.mean_pct is None
    assert result.std_pct is None
    assert result.skewness is None
    assert result.kurtosis_excess is None
    assert result.histogram_bins == []


# ── Route-level tests ─────────────────────────────────────────────────────────


def test_post_distribution_run_returns_200_with_valid_response_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/engines/distribution/run",
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
        "return_count",
        "var_95",
        "var_99",
        "cvar_95",
        "percentile_5",
        "percentile_10",
        "percentile_50",
        "percentile_90",
        "percentile_95",
        "mean_pct",
        "std_pct",
        "skewness",
        "kurtosis_excess",
        "histogram_bins",
        "trust",
    }
    assert expected_keys <= body.keys()
    assert body["trust"] in ("synthetic", "unavailable")
    assert isinstance(body["histogram_bins"], list)


def test_post_distribution_run_returns_422_on_invalid_window() -> None:
    """window_trading_days=1000 is not in Literal[60, 252, 504] →
    Pydantic validation fails with HTTP 422."""
    client = TestClient(app)
    response = client.post(
        "/engines/distribution/run",
        json={
            "benchmark_symbol": "SPY",
            "positions": [
                {"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"},
            ],
            "cash_balances": [],
            "window_trading_days": 1000,
        },
    )
    assert response.status_code == 422
