import math

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.api.main import app
from app.schemas.research import BarRecord
from app.services import strategy_lab as strategy_lab_module
from app.services.strategy_lab import _blended_momentum, _median_dollar_volume, _normalize_fmp_holdings, _normalize_fmp_holdings_snapshot, _rows_to_monthly_bars, build_etf_ranking_analysis


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
    assert payload["ranked_universe"][0]["component_scores"]["momentum"]["label"] == "Blended momentum"
    assert payload["ranked_universe"][0]["component_scores"]["realized_volatility"]["direction"] == "lower_is_better"
    assert payload["ranked_universe"][0]["component_scores"]["liquidity"]["label"] == "Median dollar volume"
    assert payload["effective_component_weights"]["momentum"] > 0
    assert payload["effective_peer_group"] is None
    assert payload["source_status"]["price_history"] in {"sample", "live"}
    assert payload["warnings"]["confidence"] in {"high", "medium", "low"}
    assert payload["request"]["universe"] == ["XLK", "XLF", "XLV", "XLE", "XLI"]
    assert payload["request"]["benchmark_symbol"] == "SPY"
    assert payload["request"]["lookback_months"] == 6
    assert payload["effective_inputs"]["requested_universe"] == ["XLK", "XLF", "XLV", "XLE", "XLI"]
    assert payload["effective_inputs"]["evaluated_universe"] == [row["symbol"] for row in payload["ranked_universe"]]
    assert payload["effective_inputs"]["effective_component_weights"] == payload["effective_component_weights"]
    assert payload["run_metadata"]["ranking_id"] == payload["ranking_id"]
    assert payload["run_metadata"]["methodology_id"] == "etf_ranking_methodology_v1"
    assert payload["run_metadata"]["as_of_date"] == payload["as_of_date"]
    assert payload["run_metadata"]["ranking_basis_date"] == payload["as_of_date"]
    assert payload["run_metadata"]["price_basis"] == payload["price_basis"]
    assert payload["run_metadata"]["source_status"] == payload["source_status"]
    assert payload["run_metadata"]["confidence"] == payload["warnings"]["confidence"]


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
    assert payload["request"]["weights"]["realized_volatility"] == 1.0
    assert payload["effective_inputs"]["effective_component_weights"]["realized_volatility"] == 1.0


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


def test_etf_ranking_route_excludes_known_non_etf_symbols_with_explicit_reason() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["AAPL", "XLK", "XLF"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert all(row["symbol"] != "AAPL" for row in payload["ranked_universe"])
    excluded = next(item for item in payload["excluded_symbols"] if item["symbol"] == "AAPL")
    assert excluded["reason"] == "instrument metadata marks AAPL as equity, not etf"


def test_etf_ranking_route_filters_to_requested_peer_group() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_peer_group"] == "Sector UCITS ETF"
    assert payload["request"]["peer_group"] == "Sector UCITS ETF"
    assert payload["effective_inputs"]["effective_peer_group"] == "Sector UCITS ETF"
    assert {row["symbol"] for row in payload["ranked_universe"]} == {"IUFS", "IUHC"}
    excluded = next(item for item in payload["excluded_symbols"] if item["symbol"] == "VDST")
    assert excluded["reason"] == "instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF"
    assert payload["effective_inputs"]["excluded_symbols"] == payload["excluded_symbols"]


def test_etf_ranking_route_reports_warnings_for_unknown_metadata_and_unclassified_peer_group_symbols(monkeypatch: MonkeyPatch) -> None:
    bars_by_symbol = {
        "MYSTERY": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-03-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-04-30", open=106, high=106, low=106, close=106, volume=1000),
            BarRecord(date="2025-05-31", open=108, high=108, low=108, close=108, volume=1000),
            BarRecord(date="2025-06-30", open=110, high=110, low=110, close=110, volume=1000),
            BarRecord(date="2025-07-31", open=112, high=112, low=112, close=112, volume=1000),
        ],
        "IUFS": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=1000),
            BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=1000),
            BarRecord(date="2025-05-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-06-30", open=105, high=105, low=105, close=105, volume=1000),
            BarRecord(date="2025-07-31", open=106, high=106, low=106, close=106, volume=1000),
        ],
        "SPY": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=1000),
            BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=1000),
            BarRecord(date="2025-05-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-06-30", open=105, high=105, low=105, close=105, volume=1000),
            BarRecord(date="2025-07-31", open=106, high=106, low=106, close=106, volume=1000),
        ],
    }

    def fake_load_base_data(symbols, benchmark, lookback_months, prefer_live_data, dataset_catalog):
        return strategy_lab_module._StrategyBaseData(
            bars_by_symbol={symbol: bars_by_symbol[symbol] for symbol in [*symbols, benchmark]},
            price_source_label="test-warnings",
            internals_mode="sample",
            price_history_status="sample",
        )

    monkeypatch.setattr(strategy_lab_module, "_load_base_data", fake_load_base_data)

    result = build_etf_ranking_analysis(universe=["MYSTERY", "IUFS"], benchmark_symbol="SPY", lookback_months=6, peer_group="Sector UCITS ETF")

    assert result.effective_peer_group == "Sector UCITS ETF"
    assert result.warnings.confidence == "medium"
    assert "MYSTERY" in result.warnings.unknown_metadata_symbols
    assert "MYSTERY" in result.warnings.peer_group_unclassified_symbols
    assert any("price history only" in warning for warning in result.warnings.warnings)
    assert result.request.peer_group == "Sector UCITS ETF"
    assert result.effective_inputs.evaluated_universe == [row.symbol for row in result.ranked_universe]
    assert result.run_metadata.methodology_id == "etf_ranking_methodology_v1"
    assert result.run_metadata.confidence == result.warnings.confidence


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


def test_blended_momentum_uses_12_1_and_6_1_style_formula_when_history_is_long_enough() -> None:
    closes = [100, 102, 104, 106, 108, 110, 112, 115, 118, 121, 124, 127, 130]
    bars = [BarRecord(date=f"2025-{index + 1:02d}-28", open=value, high=value, low=value, close=value, volume=1000) for index, value in enumerate(closes)]

    result = _blended_momentum(bars)

    expected_12_1 = (closes[-2] / closes[0]) - 1
    expected_6_1 = (closes[-2] / closes[-7]) - 1
    assert round(result, 8) == round((0.6 * expected_12_1) + (0.4 * expected_6_1), 8)


def test_blended_momentum_falls_back_conservatively_on_shorter_history() -> None:
    closes = [100, 103, 106, 109, 112, 115]
    bars = [BarRecord(date=f"2025-{index + 1:02d}-28", open=value, high=value, low=value, close=value, volume=1000) for index, value in enumerate(closes)]

    result = _blended_momentum(bars)

    assert round(result, 8) == round((closes[-1] / closes[0]) - 1, 8)


def test_median_dollar_volume_uses_logged_median() -> None:
    bars = [
        BarRecord(date="2025-01-31", open=10, high=10, low=10, close=10, volume=100),
        BarRecord(date="2025-02-28", open=10, high=10, low=10, close=10, volume=100),
        BarRecord(date="2025-03-31", open=10, high=10, low=10, close=10, volume=10000),
    ]

    result = _median_dollar_volume(bars)

    assert round(result, 8) == round(math.log(1001), 8)


def test_median_dollar_volume_returns_zero_when_volume_is_missing_or_zero() -> None:
    bars = [
        BarRecord(date="2025-01-31", open=10, high=10, low=10, close=10, volume=None),
        BarRecord(date="2025-02-28", open=10, high=10, low=10, close=10, volume=0),
    ]

    result = _median_dollar_volume(bars)

    assert result == 0.0


def test_etf_ranking_short_but_valid_aligned_history_uses_conservative_momentum_fallback(monkeypatch: MonkeyPatch) -> None:
    bars_by_symbol = {
        "AAA": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=103, high=103, low=103, close=103, volume=1000),
            BarRecord(date="2025-03-31", open=106, high=106, low=106, close=106, volume=1000),
            BarRecord(date="2025-04-30", open=109, high=109, low=109, close=109, volume=1000),
        ],
        "BBB": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=1000),
            BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=1000),
        ],
        "SPY": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-03-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-04-30", open=106, high=106, low=106, close=106, volume=1000),
        ],
    }

    def fake_load_base_data(symbols, benchmark, lookback_months, prefer_live_data, dataset_catalog):
        return strategy_lab_module._StrategyBaseData(
            bars_by_symbol={symbol: bars_by_symbol[symbol] for symbol in [*symbols, benchmark]},
            price_source_label="test-short-history",
            internals_mode="sample",
            price_history_status="sample",
        )

    monkeypatch.setattr(strategy_lab_module, "_load_base_data", fake_load_base_data)

    result = build_etf_ranking_analysis(universe=["AAA", "BBB"], benchmark_symbol="SPY", lookback_months=3)

    aaa = next(row for row in result.ranked_universe if row.symbol == "AAA")
    expected_momentum = ((109 / 100) - 1) * 100
    assert round(aaa.component_scores["momentum"].raw_value, 4) == round(expected_momentum, 4)


def test_etf_ranking_zero_volume_history_keeps_liquidity_raw_value_at_zero(monkeypatch: MonkeyPatch) -> None:
    zero_volume_bars = [
        BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=0),
        BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=0),
        BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=0),
        BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=0),
    ]
    bars_by_symbol = {
        "AAA": zero_volume_bars,
        "BBB": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-03-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-04-30", open=106, high=106, low=106, close=106, volume=1000),
        ],
        "SPY": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=1000),
            BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=1000),
        ],
    }

    def fake_load_base_data(symbols, benchmark, lookback_months, prefer_live_data, dataset_catalog):
        return strategy_lab_module._StrategyBaseData(
            bars_by_symbol={symbol: bars_by_symbol[symbol] for symbol in [*symbols, benchmark]},
            price_source_label="test-zero-volume",
            internals_mode="sample",
            price_history_status="sample",
        )

    monkeypatch.setattr(strategy_lab_module, "_load_base_data", fake_load_base_data)

    result = build_etf_ranking_analysis(universe=["AAA", "BBB"], benchmark_symbol="SPY", lookback_months=3)

    aaa = next(row for row in result.ranked_universe if row.symbol == "AAA")
    assert aaa.component_scores["liquidity"].raw_value == 0.0
