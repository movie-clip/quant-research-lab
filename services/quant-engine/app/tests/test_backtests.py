from fastapi.testclient import TestClient

from app.api.main import app


def test_backtest_route_returns_skeleton_run() -> None:
    client = TestClient(app)

    response = client.post(
        "/backtests/run",
        json={
            "strategy_id": "book_trend_breakout",
            "universe": ["ES", "NQ"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["config"]["strategy"]["strategy_id"] == "book_trend_breakout"
    assert payload["dataset_info"]
    assert payload["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["equity_curve"]
    assert payload["trades"]
    assert payload["total_return_pct"] is None
    assert payload["annualized_return_pct"] is None
    assert payload["max_drawdown_pct"] is None
    assert payload["sharpe_ratio"] is None
    assert payload["equity_curve"][0]["equity"] is None
    assert payload["equity_curve"][0]["drawdown_pct"] is None
    assert payload["overlay_preview"] is not None
    assert payload["overlay_preview"]["allocations"]
    assert payload["overlay_preview"]["equity_curve"][0]["equity"] is None
    assert payload["overlay_preview"]["equity_curve"][0]["drawdown_pct"] is None
    assert payload["dataset_info"]["ES"]["source"] == "proxy approximation (SPY)"
    assert payload["dataset_info"]["NQ"]["source"] == "proxy approximation (QQQ)"


def test_backtest_route_exposes_fmp_dataset_info_for_spy() -> None:
    client = TestClient(app)

    response = client.post(
        "/backtests/run",
        json={
            "strategy_id": "book_trend_breakout",
            "universe": ["AAPL"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_info"]["AAPL"]["source"] == "fmp"
    assert payload["dataset_info"]["AAPL"]["ready"] is True


def test_backtest_route_rejects_invalid_dates() -> None:
    client = TestClient(app)

    response = client.post(
        "/backtests/run",
        json={
            "strategy_id": "book_trend_breakout",
            "universe": ["ES"],
            "start_date": "2024-12-31",
            "end_date": "2024-01-01",
        },
    )

    assert response.status_code == 400


def test_backtest_route_rejects_unknown_strategy() -> None:
    client = TestClient(app)

    response = client.post(
        "/backtests/run",
        json={
            "strategy_id": "unknown_strategy",
            "universe": ["ES"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        },
    )

    assert response.status_code == 400
