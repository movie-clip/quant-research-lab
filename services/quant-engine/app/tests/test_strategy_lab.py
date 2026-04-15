from fastapi.testclient import TestClient

from app.api.main import app
from app.services.strategy_lab import _normalize_fmp_holdings, _normalize_fmp_holdings_snapshot, _rows_to_monthly_bars


def test_etf_ranking_route_returns_ranked_universe_and_component_scores() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_id"] == "etf_ranking_engine_v1"
    assert payload["ranked_universe"]
    assert payload["ranked_universe"][0]["rank"] == 1
    assert payload["ranked_universe"][0]["component_scores"]["momentum"]["normalized_score"] is not None
    assert payload["ranked_universe"][0]["component_scores"]["realized_volatility"]["direction"] == "lower_is_better"
    assert payload["effective_component_weights"]["momentum"] > 0
    assert payload["source_status"]["price_history"] in {"sample", "live"}


def test_etf_ranking_route_supports_custom_weights() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "weights": {
                "momentum": 0.0,
                "benchmark_relative_strength": 0.0,
                "realized_volatility": 1.0,
                "downside_volatility": 0.0,
                "max_drawdown": 0.0,
                "liquidity": 0.0,
                "implementation_fit": 0.0,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_component_weights"]["realized_volatility"] == 1.0
    assert payload["effective_component_weights"]["momentum"] == 0.0


def test_etf_ranking_route_rejects_empty_universe() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": [],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 400


def test_etf_cross_sectional_momentum_route_returns_rankings_and_curve() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 3,
            "top_n": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "book_etf_cross_sectional_momentum"
    assert payload["current_rankings"]
    assert payload["equity_curve"]
    assert payload["metrics"]["total_return_pct"] is not None
    assert payload["metrics"]["average_volume_participation_ratio"] is not None
    assert payload["observations"][0]["rankings"]
    assert payload["observations"][0]["average_volume_ratio"] is not None
    assert len(payload["latest_holdings"]) == 2
    assert payload["leader_internals"]
    assert payload["source_status"]["price_history"] in {"sample", "live"}
    assert payload["source_status"]["leader_internals"] in {"sample", "live-dated", "mixed"}
    assert payload["leader_internals"][0]["leader_symbol"] in {"XLK", "XLI", "XLV", "XLF", "XLE"}
    assert payload["leader_internals"][0]["constituents"][0]["weighted_contribution_pct"] is not None
    assert payload["leader_internals"][0]["snapshot_date"] is not None


def test_etf_cross_sectional_momentum_route_rejects_invalid_top_n() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK", "XLF"],
            "benchmark_symbol": "SPY",
            "lookback_months": 3,
            "top_n": 3,
        },
    )

    assert response.status_code == 400


def test_etf_cross_sectional_momentum_supports_long_quarter_lookbacks() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 36,
            "top_n": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["observations"]) >= 48


def test_etf_cross_sectional_momentum_uses_dated_leader_holdings_snapshots() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK"],
            "benchmark_symbol": "SPY",
            "lookback_months": 12,
            "top_n": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    constituent_sets = [tuple(item["symbol"] for item in row["constituents"]) for row in payload["leader_internals"] if row["constituents"]]
    assert len(set(constituent_sets)) >= 2


def test_rows_to_monthly_bars_keeps_latest_row_per_month() -> None:
    bars = _rows_to_monthly_bars(
        [
            {"date": "2024-01-02", "price": 100.0, "volume": 1000},
            {"date": "2024-01-31", "price": 105.0, "volume": 1200},
            {"date": "2024-02-15", "price": 110.0, "volume": 1300},
        ]
    )

    assert [bar.date for bar in bars] == ["2024-01-31", "2024-02-15"]
    assert [bar.close for bar in bars] == [105.0, 110.0]


def test_normalize_fmp_holdings_converts_weight_percentages() -> None:
    rows = _normalize_fmp_holdings(
        [
            {"asset": "MSFT", "name": "Microsoft", "weightPercentage": 6.0},
            {"asset": "AAPL", "name": "Apple", "weightPercentage": 7.5},
        ]
    )

    assert [row["symbol"] for row in rows] == ["AAPL", "MSFT"]
    assert rows[0]["weight"] == 0.075


def test_normalize_fmp_holdings_snapshot_reads_snapshot_date() -> None:
    snapshot = _normalize_fmp_holdings_snapshot(
        [
            {"asset": "MSFT", "name": "Microsoft", "weightPercentage": 6.0, "updated": "2026-04-08 11:04:21"},
            {"asset": "AAPL", "name": "Apple", "weightPercentage": 7.5, "updated": "2026-04-08 11:04:21"},
        ]
    )

    assert snapshot is not None
    assert snapshot.snapshot_date == "2026-04-08"
    assert snapshot.holdings[0]["symbol"] == "AAPL"


def test_normalize_fmp_holdings_snapshot_returns_none_without_updated_timestamp() -> None:
    snapshot = _normalize_fmp_holdings_snapshot(
        [
            {"asset": "MSFT", "name": "Microsoft", "weightPercentage": 6.0},
        ]
    )

    assert snapshot is None
