"""Tests for the intra-portfolio correlation engine (US-17.1).

Covers:
- the pure analytics helpers (pairwise_correlation_matrix, average_pairwise_correlation)
- the engine service (run_intra_correlation) with MarketDataService mocked
- the POST /engines/correlation/intra route shape
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.analytics.correlation import (
    average_pairwise_correlation,
    diversification_ratio,
    effective_number_of_bets,
    pairwise_correlation_matrix,
    population_stdev,
)
from app.api.main import app
from app.schemas.intra_correlation import IntraCorrelationRequest
from app.services.intra_correlation_engine import run_intra_correlation


# ── Analytics helpers ─────────────────────────────────────────────────────────

# A non-constant return pattern of length 39 (→ ≥ 20 overlapping pairs).
_RET_A = [0.01 * math.sin(d) for d in range(1, 40)]


class TestPairwiseCorrelationMatrix:
    def test_symmetric_with_unit_diagonal(self):
        # B = 2×A → perfectly correlated; matrix symmetric, diagonal 1.0.
        rb = {"A": _RET_A, "B": [2.0 * x for x in _RET_A]}
        m = pairwise_correlation_matrix(rb, ["A", "B"], min_observations=20)
        assert m[0][0] == 1.0 and m[1][1] == 1.0
        assert m[0][1] == m[1][0]
        assert m[0][1] is not None and abs(m[0][1] - 1.0) < 1e-9

    def test_perfect_negative_correlation(self):
        rb = {"A": _RET_A, "C": [-x for x in _RET_A]}
        m = pairwise_correlation_matrix(rb, ["A", "C"], min_observations=20)
        assert m[0][1] is not None and abs(m[0][1] - (-1.0)) < 1e-9

    def test_none_below_min_overlap(self):
        # Only 5 overlapping non-null pairs; rest None → cell is None.
        a = [0.01, -0.02, 0.03, -0.01, 0.02] + [None] * 34
        b = [0.01, -0.02, 0.03, -0.01, 0.02] + [None] * 34
        m = pairwise_correlation_matrix({"A": a, "B": b}, ["A", "B"], min_observations=20)
        assert m[0][1] is None
        assert m[0][0] == 1.0  # diagonal still 1.0

    def test_none_for_zero_variance_series(self):
        flat = [0.0] * 39  # constant → zero variance → pearson None
        m = pairwise_correlation_matrix({"A": _RET_A, "B": flat}, ["A", "B"], min_observations=20)
        assert m[0][1] is None

    def test_average_is_mean_of_offdiagonal_non_null(self):
        # 3 symbols: corr(A,B)=+1, corr(A,C)=-1, corr(B,C)=-1 → mean = -1/3.
        rb = {"A": _RET_A, "B": [2.0 * x for x in _RET_A], "C": [-x for x in _RET_A]}
        m = pairwise_correlation_matrix(rb, ["A", "B", "C"], min_observations=20)
        avg = average_pairwise_correlation(m)
        assert avg is not None and abs(avg - (-1.0 / 3.0)) < 1e-9

    def test_average_none_when_no_valid_pairs(self):
        # Non-overlapping series → off-diagonal None → average None.
        a = _RET_A[:5] + [None] * 34
        b = [None] * 5 + _RET_A[5:]
        m = pairwise_correlation_matrix({"A": a, "B": b}, ["A", "B"], min_observations=20)
        assert average_pairwise_correlation(m) is None


# ── Diversification summary analytics (US-17.2) ───────────────────────────────

class TestDiversificationAnalytics:
    def test_population_stdev_value_and_none(self):
        # mean 0; var = (0.02² + 0.02²)/4 = 0.0002 → std = sqrt(0.0002)
        assert population_stdev([0.0, 0.02, -0.02, 0.0]) == pytest.approx(math.sqrt(0.0002))
        assert population_stdev([0.01]) is None          # < 2 values
        assert population_stdev([None, 0.01]) is None     # < 2 non-null

    def test_diversification_ratio_value(self):
        # Σwσ = .5×.2 + .5×.2 = .2 ; /σ_p .1 → 2.0
        assert diversification_ratio([0.5, 0.5], [0.2, 0.2], 0.1) == pytest.approx(2.0)

    def test_diversification_ratio_none_when_portfolio_vol_zero_or_none(self):
        assert diversification_ratio([0.5, 0.5], [0.2, 0.2], 0.0) is None
        assert diversification_ratio([0.5, 0.5], [0.2, 0.2], None) is None

    def test_effective_number_of_bets_identity_matrix(self):
        identity = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
        assert effective_number_of_bets(identity) == pytest.approx(3.0)

    def test_effective_number_of_bets_all_ones_matrix(self):
        ones = [[1.0, 1.0, 1.0], [1.0, 1.0, 1.0], [1.0, 1.0, 1.0]]
        assert effective_number_of_bets(ones) == pytest.approx(1.0)

    def test_effective_number_of_bets_none_when_cell_missing(self):
        partial = [[1.0, None, 0.2], [None, 1.0, 0.3], [0.2, 0.3, 1.0]]
        assert effective_number_of_bets(partial) is None


# ── Engine service (MarketDataService mocked) ─────────────────────────────────

def _position(symbol: str, market_value: float) -> dict:
    return {
        "as_of_date": "2024-12-31",
        "symbol": symbol,
        "quantity": 10.0,
        "cost_basis": market_value * 0.8,
        "close_price": market_value / 10.0,
        "market_value": market_value,
        "unrealized_pnl": market_value * 0.2,
        "currency": "USD",
    }


def _snapshot(positions: list[dict], cash: list[dict] | None = None) -> dict:
    return {
        "statement": {
            "importer": "interactive_brokers",
            "imported_at": "2024-12-31T00:00:00",
            "source_path": "/test/fixture.csv",
            "detected_format": "ib_flex_2023",
        },
        "instruments": [],
        "positions": positions,
        "cash_balances": cash or [],
        "ledger_entries": [],
    }


def _request(positions, *, lookback_days=60, max_holdings=15, cash=None) -> IntraCorrelationRequest:
    return IntraCorrelationRequest.model_validate({
        "snapshot": _snapshot(positions, cash),
        "lookback_days": lookback_days,
        "max_holdings": max_holdings,
    })


def _install_market_data_mock(mocker, returns_by_symbol: dict[str, list[float]], *, n_dates=40, missing=()):
    dates = [(date(2025, 1, 1) + timedelta(days=d)).isoformat() for d in range(n_dates)]
    spy_rows = [{"date": d, "price": 100.0 + i} for i, d in enumerate(dates)]
    histories: dict[str, list[dict]] = {}
    for sym, rets in returns_by_symbol.items():
        prices = [100.0]
        for r in rets:
            prices.append(prices[-1] * (1.0 + r))
        histories[sym] = [{"date": dates[i], "price": prices[i]} for i in range(n_dates)]
    for sym in missing:
        histories[sym] = []
    mock_svc = MagicMock()
    inst = mock_svc.return_value
    inst.get_historical_prices.return_value = spy_rows
    inst.get_historical_prices_for_symbols.return_value = histories
    mocker.patch("app.services.intra_correlation_engine.MarketDataService", mock_svc)


class TestIntraCorrelationEngine:
    def test_happy_path_matrix_shape_and_order(self, mocker):
        _install_market_data_mock(mocker, {
            "AAA": _RET_A,
            "BBB": [2.0 * x for x in _RET_A],
            "CCC": [-x for x in _RET_A],
        })
        # Weights AAA>BBB>CCC → rank order AAA, BBB, CCC.
        res = run_intra_correlation(_request([
            _position("AAA", 300.0), _position("BBB", 200.0), _position("CCC", 100.0),
        ]))
        assert res.trust == "synthetic"
        assert res.symbols == ["AAA", "BBB", "CCC"]
        assert len(res.matrix) == 3 and all(len(row) == 3 for row in res.matrix)
        assert res.matrix[0][0] == 1.0
        assert res.matrix[0][1] is not None and abs(res.matrix[0][1] - 1.0) < 1e-9

    def test_caps_to_top_n_by_weight(self, mocker):
        _install_market_data_mock(mocker, {
            "AAA": _RET_A, "BBB": [2.0 * x for x in _RET_A], "CCC": [-x for x in _RET_A],
        })
        res = run_intra_correlation(_request([
            _position("CCC", 100.0), _position("AAA", 300.0), _position("BBB", 200.0),
        ], max_holdings=2))
        assert res.symbols == ["AAA", "BBB"]  # top 2 by weight
        assert len(res.matrix) == 2

    def test_cash_not_in_matrix(self, mocker):
        _install_market_data_mock(mocker, {"AAA": _RET_A, "BBB": [2.0 * x for x in _RET_A]})
        res = run_intra_correlation(_request(
            [_position("AAA", 300.0), _position("BBB", 200.0)],
            cash=[{"currency": "USD", "ending_cash": 5000.0}],
        ))
        assert res.symbols == ["AAA", "BBB"]  # no "USD" / cash entry

    def test_no_history_symbol_excluded_and_surfaced(self, mocker):
        _install_market_data_mock(mocker, {
            "AAA": _RET_A, "BBB": [2.0 * x for x in _RET_A], "CCC": [-x for x in _RET_A],
        }, missing=("DDD",))
        res = run_intra_correlation(_request([
            _position("AAA", 400.0), _position("BBB", 300.0),
            _position("CCC", 200.0), _position("DDD", 100.0),
        ]))
        assert "DDD" not in res.symbols
        assert res.excluded_symbols == ["DDD"]

    def test_fewer_than_two_priceable_is_unavailable(self, mocker):
        _install_market_data_mock(mocker, {"AAA": _RET_A}, missing=("BBB",))
        res = run_intra_correlation(_request([
            _position("AAA", 300.0), _position("BBB", 200.0),
        ]))
        assert res.trust == "unavailable"
        assert res.symbols == [] and res.matrix == []
        assert "BBB" in res.excluded_symbols

    def test_most_and_least_correlated_pairs(self, mocker):
        _install_market_data_mock(mocker, {
            "AAA": _RET_A, "BBB": [2.0 * x for x in _RET_A], "CCC": [-x for x in _RET_A],
        })
        res = run_intra_correlation(_request([
            _position("AAA", 300.0), _position("BBB", 200.0), _position("CCC", 100.0),
        ]))
        assert res.most_correlated_pair is not None
        assert abs(res.most_correlated_pair.correlation - 1.0) < 1e-9
        assert {res.most_correlated_pair.symbol_a, res.most_correlated_pair.symbol_b} == {"AAA", "BBB"}
        assert res.least_correlated_pair is not None
        assert abs(res.least_correlated_pair.correlation - (-1.0)) < 1e-9

    def test_populates_diversification_summary_on_happy_path(self, mocker):
        # Three independent-ish series → matrix fully populated → DR + ENB finite.
        _install_market_data_mock(mocker, {
            "AAA": [0.01 * math.sin(d) for d in range(1, 40)],
            "BBB": [0.01 * math.cos(d) for d in range(1, 40)],
            "CCC": [0.01 * math.sin(d * 0.5 + 1.0) for d in range(1, 40)],
        })
        res = run_intra_correlation(_request([
            _position("AAA", 300.0), _position("BBB", 200.0), _position("CCC", 100.0),
        ]))
        assert res.diversification_ratio is not None and res.diversification_ratio > 0
        assert res.effective_number_of_bets is not None
        assert 1.0 - 1e-9 <= res.effective_number_of_bets <= 3.0 + 1e-9

    def test_diversification_summary_null_when_unavailable(self, mocker):
        _install_market_data_mock(mocker, {"AAA": _RET_A}, missing=("BBB",))
        res = run_intra_correlation(_request([
            _position("AAA", 300.0), _position("BBB", 200.0),
        ]))
        assert res.trust == "unavailable"
        assert res.diversification_ratio is None
        assert res.effective_number_of_bets is None


# ── Route shape ───────────────────────────────────────────────────────────────

@pytest.fixture
def client():
    return TestClient(app)


class TestIntraCorrelationRoute:
    def test_empty_positions_returns_unavailable(self, client):
        payload = {"snapshot": _snapshot([]), "lookback_days": 60}
        response = client.post("/engines/correlation/intra", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["trust"] == "unavailable"
        assert data["symbols"] == []
        assert data["matrix"] == []
        assert data["lookback_days"] == 60

    def test_route_returns_valid_shape_with_positions(self, client, mocker):
        _install_market_data_mock(mocker, {
            "AAA": _RET_A, "BBB": [2.0 * x for x in _RET_A],
        })
        payload = {
            "snapshot": _snapshot([_position("AAA", 300.0), _position("BBB", 200.0)]),
            "lookback_days": 60,
        }
        response = client.post("/engines/correlation/intra", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert set(data.keys()) >= {
            "symbols", "matrix", "average_pairwise_correlation",
            "most_correlated_pair", "least_correlated_pair",
            "diversification_ratio", "effective_number_of_bets",
            "excluded_symbols", "lookback_days", "trust",
        }
        assert data["lookback_days"] == 60
        assert data["trust"] in ("synthetic", "unavailable")
