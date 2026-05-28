"""Tests for the multi-benchmark correlation engine.

Coverage:
  - analytics/correlation.py: pearson(), beta(), r_squared() scalar functions
  - /engines/correlation/multi route: schema, empty-positions, structural response
  - BenchmarkStats trust field: 'synthetic' when data available, 'unavailable' when not
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.analytics.correlation import beta, pearson, r_squared
from app.api.main import app


# ── Scalar analytics tests ────────────────────────────────────────────────────

class TestPearson:
    def test_perfect_positive_correlation(self):
        r_p = [0.01, 0.02, 0.03, 0.04, 0.05]
        r_b = [0.01, 0.02, 0.03, 0.04, 0.05]
        result = pearson(r_p, r_b)
        assert result is not None
        assert abs(result - 1.0) < 1e-9

    def test_perfect_negative_correlation(self):
        r_p = [0.01, 0.02, 0.03, 0.04, 0.05]
        r_b = [-0.01, -0.02, -0.03, -0.04, -0.05]
        result = pearson(r_p, r_b)
        assert result is not None
        assert abs(result - (-1.0)) < 1e-9

    def test_zero_correlation_orthogonal_series(self):
        # Construct two series with zero covariance: [1,-1,1,-1] vs [1,1,-1,-1]
        r_p = [0.01, -0.01, 0.01, -0.01]
        r_b = [0.01, 0.01, -0.01, -0.01]
        result = pearson(r_p, r_b)
        assert result is not None
        assert abs(result) < 1e-9

    def test_none_when_fewer_than_two_pairs(self):
        assert pearson([], []) is None
        assert pearson([0.01], [0.01]) is None

    def test_none_when_all_none_inputs(self):
        assert pearson([None, None], [None, None]) is None

    def test_drops_none_entries_before_computing(self):
        # 4 valid pairs + 1 None-pair; result should still be valid.
        r_p = [0.01, None, 0.02, 0.03, 0.04]
        r_b = [0.01, 0.99, 0.02, 0.03, 0.04]
        full = pearson([0.01, 0.02, 0.03, 0.04], [0.01, 0.02, 0.03, 0.04])
        sparse = pearson(r_p, r_b)
        assert sparse is not None
        assert full is not None
        # Sparse drops the pair where r_p=None; result should equal full (4 pairs, same values).
        assert abs(sparse - full) < 1e-9

    def test_none_when_zero_variance_portfolio(self):
        r_p = [0.01, 0.01, 0.01, 0.01, 0.01]
        r_b = [0.01, 0.02, 0.03, 0.04, 0.05]
        assert pearson(r_p, r_b) is None

    def test_none_when_zero_variance_benchmark(self):
        r_p = [0.01, 0.02, 0.03, 0.04, 0.05]
        r_b = [0.01, 0.01, 0.01, 0.01, 0.01]
        assert pearson(r_p, r_b) is None

    def test_result_in_minus1_to_1_range(self):
        import random
        random.seed(42)
        r_p = [random.gauss(0.001, 0.01) for _ in range(100)]
        r_b = [random.gauss(0.001, 0.01) for _ in range(100)]
        result = pearson(r_p, r_b)
        assert result is not None
        assert -1.0 <= result <= 1.0


class TestBeta:
    def test_beta_equals_one_for_identical_series(self):
        r_p = [i * 0.001 for i in range(1, 25)]
        r_b = r_p[:]
        result = beta(r_p, r_b)
        assert result is not None
        assert abs(result - 1.0) < 1e-9

    def test_beta_two_for_double_return_series(self):
        r_b = [i * 0.001 for i in range(1, 25)]
        r_p = [2 * x for x in r_b]
        result = beta(r_p, r_b)
        assert result is not None
        assert abs(result - 2.0) < 1e-9

    def test_none_when_fewer_than_min_observations(self):
        r_p = [0.01] * 19
        r_b = [0.01] * 19
        assert beta(r_p, r_b, min_observations=20) is None

    def test_not_none_at_min_observations(self):
        r_p = [i * 0.001 for i in range(1, 21)]
        r_b = r_p[:]
        assert beta(r_p, r_b, min_observations=20) is not None

    def test_none_when_benchmark_has_zero_variance(self):
        r_p = [0.01] * 25
        r_b = [0.005] * 25
        assert beta(r_p, r_b) is None


class TestRSquared:
    def test_r_squared_is_pearson_squared(self):
        r_p = [i * 0.001 for i in range(1, 10)]
        r_b = [i * 0.0008 for i in range(1, 10)]
        rho = pearson(r_p, r_b)
        r2 = r_squared(r_p, r_b)
        assert rho is not None and r2 is not None
        assert abs(r2 - rho ** 2) < 1e-12

    def test_r_squared_none_when_pearson_none(self):
        assert r_squared([], []) is None

    def test_r_squared_one_for_perfect_correlation(self):
        r_p = [0.01, 0.02, 0.03, 0.04, 0.05]
        r_b = [0.01, 0.02, 0.03, 0.04, 0.05]
        result = r_squared(r_p, r_b)
        assert result is not None
        assert abs(result - 1.0) < 1e-9


# ── Route structural tests ────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


def _minimal_snapshot(with_positions: bool = True) -> dict:
    """Minimal ImportedPortfolioSnapshot-shaped dict for route tests."""
    positions = [
        {
            "as_of_date": "2024-12-31",
            "symbol": "AAPL",
            "quantity": 10.0,
            "cost_basis": 1500.0,
            "close_price": 190.0,
            "market_value": 1900.0,
            "unrealized_pnl": 400.0,
            "currency": "USD",
        }
    ] if with_positions else []
    return {
        "statement": {
            "importer": "interactive_brokers",
            "imported_at": "2024-12-31T00:00:00",
            "source_path": "/test/fixture.csv",
            "detected_format": "ib_flex_2023",
        },
        "instruments": [],
        "positions": positions,
        "cash_balances": [],
        "ledger_entries": [],
    }


class TestMultiCorrelationRoute:
    def test_empty_positions_returns_all_unavailable(self, client):
        payload = {
            "snapshot": _minimal_snapshot(with_positions=False),
            "lookback_days": 252,
        }
        response = client.post("/engines/correlation/multi", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["lookback_days"] == 252
        assert len(data["benchmarks"]) == 5
        for row in data["benchmarks"]:
            assert row["trust"] == "unavailable"
            assert row["correlation"] is None
            assert row["beta"] is None
            assert row["r_squared"] is None

    def test_response_has_five_benchmark_rows(self, client):
        payload = {"snapshot": _minimal_snapshot(), "lookback_days": 252}
        response = client.post("/engines/correlation/multi", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["benchmarks"]) == 5

    def test_response_includes_expected_benchmark_symbols(self, client):
        payload = {"snapshot": _minimal_snapshot(), "lookback_days": 252}
        response = client.post("/engines/correlation/multi", json=payload)
        assert response.status_code == 200
        symbols = {row["symbol"] for row in response.json()["benchmarks"]}
        assert symbols == {"SPY", "QQQ", "GLD", "IEF", "VT"}

    def test_benchmark_rows_have_required_fields(self, client):
        payload = {"snapshot": _minimal_snapshot(), "lookback_days": 60}
        response = client.post("/engines/correlation/multi", json=payload)
        assert response.status_code == 200
        for row in response.json()["benchmarks"]:
            assert "symbol" in row
            assert "label" in row
            assert "trust" in row
            assert row["trust"] in ("synthetic", "unavailable")

    def test_lookback_days_echoed_in_response(self, client):
        payload = {"snapshot": _minimal_snapshot(), "lookback_days": 60}
        response = client.post("/engines/correlation/multi", json=payload)
        assert response.status_code == 200
        assert response.json()["lookback_days"] == 60
