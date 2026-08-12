"""Engine response-integrity property test (US-21.3).

Two production 500s in one week came from non-finite floats (NaN) reaching
FastAPI's strict JSON encoder (attribution 2026-06-10; correlation 2026-06-10).
This file guards the CLASS across the API surface:

1. Every analytics engine route, driven by a standard mocked portfolio, must
   return HTTP 200 with parseable strict JSON. (Starlette's `json.dumps` raises
   on NaN/inf — that WAS both bugs — so a 200 with parseable body is exactly
   the property "no non-finite value reached the response".)
2. A self-policing coverage check introspects the FastAPI route table: any NEW
   `POST /engines/*` route must be added to the parametrization (or explicitly
   waived with a reason) — a forgotten engine fails the suite, not code review.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.tests.conftest import _mock_price_rows, _mock_prices_for_symbols
from app.tests.fixtures import imported_snapshot, position

_FLAT_PORTFOLIO = {
    "benchmark_symbol": "SPY",
    "positions": [
        {"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"},
        {"symbol": "MSFT", "market_value": 8000.0, "quantity": 25.0, "currency": "USD"},
    ],
    "cash_balances": [],
    "base_currency": "USD",
}

_SNAPSHOT = imported_snapshot(positions=[position("AAPL", 10000.0), position("MSFT", 8000.0)])

# (route path, engine module whose MarketDataService gets mocked, payload)
ENGINE_ROUTES: list[tuple[str, str, dict]] = [
    ("/engines/stress/run", "app.services.stress_engine", _FLAT_PORTFOLIO),
    ("/engines/drawdown/run", "app.services.drawdown_engine", _FLAT_PORTFOLIO),
    ("/engines/distribution/run", "app.services.distribution_engine", _FLAT_PORTFOLIO),
    ("/engines/drift/run", "app.services.drift_engine", _FLAT_PORTFOLIO),
    ("/engines/attribution/run", "app.services.attribution_engine",
     {"snapshot": _SNAPSHOT, "window": 20, "benchmark_symbol": "SPY"}),
    ("/engines/correlation/multi", "app.services.correlation_engine",
     {"snapshot": _SNAPSHOT, "lookback_days": 60}),
    ("/engines/correlation/intra", "app.services.intra_correlation_engine",
     {"snapshot": _SNAPSHOT, "lookback_days": 60}),
    ("/engines/provenance/run", "app.services.provenance_engine",
     {"snapshot": _SNAPSHOT, "lookback_days": 30}),
    ("/engines/currency-risk/run", "app.services.currency_risk_engine",
     {"snapshot": _SNAPSHOT, "window": 60}),
]

# Routes deliberately NOT in the parametrization — each needs a reason.
WAIVED_ROUTES: dict[str, str] = {
    "/engines/exposure/run": "heavier request contract (PortfolioSnapshot workspace shape); output golden-pinned",
    "/engines/diagnostics/run": "heavier request contract (history context); output golden-pinned",
    "/engines/diagnostics/run-imported": "imported-bootstrap contract; output golden-pinned",
    "/engines/dashboard-history/run": "heavier request contract (history context); output golden-pinned",
    "/engines/dashboard-history/run-imported": "imported-bootstrap contract; output golden-pinned",
}


def _install_engine_market_data(mocker, target_module: str) -> None:
    """Mock the engine's MarketDataService with the conftest deterministic
    per-symbol synthetic generators (distinct series per symbol, holiday-aware).
    Installed per-parametrization so this test never depends on the conftest
    autouse module list staying in sync."""
    mock_svc = MagicMock()
    inst = mock_svc.return_value
    inst.get_historical_prices.side_effect = _mock_price_rows
    inst.get_historical_prices_for_symbols.side_effect = _mock_prices_for_symbols
    inst.last_fetch_meta = {}
    mocker.patch(f"{target_module}.MarketDataService", mock_svc)


@pytest.mark.parametrize(
    ("path", "module", "payload"),
    ENGINE_ROUTES,
    ids=[path for path, _, _ in ENGINE_ROUTES],
)
def test_engine_route_responses_are_strict_json(path, module, payload, mocker):
    _install_engine_market_data(mocker, module)

    response = TestClient(app).post(path, json=payload)

    # 200 proves no NaN/inf reached the encoder (it raises → 500).
    assert response.status_code == 200, f"{path} returned {response.status_code}: {response.text[:300]}"
    body = json.loads(response.text)  # parseable strict JSON
    assert isinstance(body, dict) and body, f"{path} returned an empty/non-object body"


def test_all_engine_run_routes_are_covered():
    engine_posts = sorted(
        route.path
        for route in app.routes
        if "POST" in (getattr(route, "methods", None) or set())
        and route.path.startswith("/engines/")
    )
    covered = {path for path, _, _ in ENGINE_ROUTES}
    missing = [p for p in engine_posts if p not in covered and p not in WAIVED_ROUTES]
    assert missing == [], (
        "New engine route(s) lack response-integrity coverage — add them to "
        f"ENGINE_ROUTES (or WAIVED_ROUTES with a reason): {missing}"
    )
    # Waivers must not go stale: every waived path must still exist.
    stale = [p for p in WAIVED_ROUTES if p not in engine_posts]
    assert stale == [], f"Stale waivers for removed routes: {stale}"
