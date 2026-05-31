"""Tests for the standalone stress-scenario engine and route.

Coverage:
  - run_stress_engine: happy path (real portfolio → 3 scenarios with non-null pct,
    trust='synthetic'), empty-positions path (trust='unavailable', per-scenario
    pct=None + status='unavailable'), canonical scenario list shape
  - POST /engines/stress/run route: 200 happy path, 422 on malformed payload
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.analytics.risk import STRESS_SCENARIOS
from app.api.main import app
from app.schemas.stress import StressEngineRequest
from app.services.stress_engine import run_stress_engine


CANONICAL_SCENARIO_NAMES = {name for name, _shocks, _description in STRESS_SCENARIOS}


def _make_request(**kwargs) -> StressEngineRequest:
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
    return StressEngineRequest(**defaults)


# ── Service-level tests ───────────────────────────────────────────────────────


def test_run_stress_engine_returns_three_scenarios_with_non_null_pct() -> None:
    """Real portfolio (AAPL + MSFT) → factor model fits → every scenario has
    a non-null estimated_return_pct + status='ok' + wrapper trust='synthetic'."""
    request = _make_request()
    result = run_stress_engine(request)

    assert result.trust == "synthetic"
    assert len(result.scenarios) == len(STRESS_SCENARIOS)
    for scenario in result.scenarios:
        assert scenario.estimated_return_pct is not None, (
            f"{scenario.name}: expected non-null pct on populated factor model"
        )
        assert scenario.status == "ok"
        assert isinstance(scenario.estimated_return_pct, float)
    # No fabrication: scenario names must be the canonical set.
    assert {s.name for s in result.scenarios} == CANONICAL_SCENARIO_NAMES


def test_run_stress_engine_returns_unavailable_when_no_positions() -> None:
    """Empty positions → factor model cannot be fit → wrapper trust='unavailable',
    every per-scenario pct is None, every status='unavailable'. The scenario
    list is still complete (one row per canonical scenario) so the UI never
    has to special-case 'list is empty'."""
    request = _make_request(positions=[])
    result = run_stress_engine(request)

    assert result.trust == "unavailable"
    assert len(result.scenarios) == len(STRESS_SCENARIOS)
    for scenario in result.scenarios:
        assert scenario.estimated_return_pct is None
        assert scenario.status == "unavailable"


def test_run_stress_engine_scenario_names_match_canonical_list_on_both_paths() -> None:
    """Scenario names are NEVER fabricated — even on the unavailable path,
    the engine emits the canonical 3 names from analytics.risk.STRESS_SCENARIOS.
    Pins the no-drift contract: a researcher comparing the populated and
    unavailable responses sees the same scenario names; only the numbers
    change. This also catches accidental list reordering or renaming."""
    populated = run_stress_engine(_make_request())
    empty = run_stress_engine(_make_request(positions=[]))

    populated_names = [s.name for s in populated.scenarios]
    empty_names = [s.name for s in empty.scenarios]
    canonical_names = [name for name, _shocks, _description in STRESS_SCENARIOS]

    assert populated_names == canonical_names
    assert empty_names == canonical_names


# ── Route-level tests ─────────────────────────────────────────────────────────


def test_post_stress_run_returns_200_with_valid_response_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/engines/stress/run",
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
    assert "scenarios" in body
    assert "trust" in body
    assert body["trust"] in ("synthetic", "unavailable")
    assert isinstance(body["scenarios"], list)
    assert len(body["scenarios"]) == len(STRESS_SCENARIOS)
    for scenario in body["scenarios"]:
        assert {"name", "estimated_return_pct", "description", "status"} <= scenario.keys()


def test_post_stress_run_returns_422_on_malformed_payload() -> None:
    """Body with wrong types fails Pydantic validation with HTTP 422,
    not a 500. (Empty body {} is also accepted by PortfolioEngineRequest
    since all fields have defaults — so we use a typed-but-wrong payload.)"""
    client = TestClient(app)
    response = client.post(
        "/engines/stress/run",
        json={"positions": "not-a-list"},  # type violation
    )
    assert response.status_code == 422
