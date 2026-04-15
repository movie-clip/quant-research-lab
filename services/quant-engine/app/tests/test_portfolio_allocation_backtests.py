from app.schemas.backtest_engine import AllocationBacktestAssumptions, AllocationBacktestMetrics, AllocationBacktestPoint, AllocationBacktestResult, AllocationBacktestWeight, PortfolioWeightInput
from app.services.portfolio_backtest_engine import _build_backtest_diagnostics_inputs, _build_synthetic_snapshot_from_weights
from fastapi.testclient import TestClient

from app.api.main import app


def _history(*prices: float) -> list[dict]:
    dates = ["2024-01-02", "2024-01-31", "2024-02-01", "2024-06-03", "2024-12-31"]
    return [{"date": date, "price": price} for date, price in zip(dates[: len(prices)], prices, strict=False)]


def test_build_synthetic_snapshot_from_weights_returns_explicit_imported_snapshot() -> None:
    result = AllocationBacktestResult(
        portfolio_name="Candidate",
        benchmark_symbol="SPY",
        start_date="2024-01-01",
        end_date="2024-12-31",
        observation_count=3,
        rebalance_frequency="monthly",
        commission_bps=0,
        slippage_bps=0,
        assumptions=AllocationBacktestAssumptions(
            price_basis="adjusted_close",
            execution_price_field="close",
            execution_lag_days=1,
            calendar_policy="intersection_common_dates",
            fractional_shares=True,
            long_only=True,
            leverage_allowed=False,
            tax_treatment="pre_tax",
            investor_base_currency="USD",
        ),
        status="ok",
        instrument_metadata=[],
        starting_weights=[AllocationBacktestWeight(symbol="SPY", target_weight=1.0)],
        ending_weights=[AllocationBacktestWeight(symbol="SPY", target_weight=1.0)],
        metrics=AllocationBacktestMetrics(),
        equity_curve=[AllocationBacktestPoint(date="2024-01-01", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=110000, cash=0)],
        rebalance_events=[],
        trades=[],
    )

    snapshot = _build_synthetic_snapshot_from_weights("Candidate", [PortfolioWeightInput(symbol="SPY", target_weight=1.0)], result)

    assert snapshot.statement.detected_format == "synthetic_backtest"
    assert snapshot.statement.importer == "multi_broker"
    assert snapshot.statement.source_path == "candidate-backtest"
    assert snapshot.statement.statement_period == "2024-01-01 - 2024-12-31"
    assert snapshot.positions[0].symbol == "SPY"
    assert snapshot.positions[0].market_value == 110000


def test_build_backtest_diagnostics_inputs_separates_replay_and_historical_inputs() -> None:
    result = AllocationBacktestResult(
        portfolio_name="Candidate",
        benchmark_symbol="SPY",
        start_date="2024-01-01",
        end_date="2024-12-31",
        observation_count=2,
        rebalance_frequency="monthly",
        commission_bps=0,
        slippage_bps=0,
        assumptions=AllocationBacktestAssumptions(
            price_basis="adjusted_close",
            execution_price_field="close",
            execution_lag_days=1,
            calendar_policy="intersection_common_dates",
            fractional_shares=True,
            long_only=True,
            leverage_allowed=False,
            tax_treatment="pre_tax",
            investor_base_currency="USD",
        ),
        status="ok",
        instrument_metadata=[],
        starting_weights=[AllocationBacktestWeight(symbol="SPY", target_weight=1.0)],
        ending_weights=[AllocationBacktestWeight(symbol="SPY", target_weight=1.0)],
        metrics=AllocationBacktestMetrics(),
        equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=110000, cash=0)],
        rebalance_events=[],
        trades=[],
    )
    histories = {
        "SPY": _history(100.0, 102.0, 108.0),
        "QQQ": _history(100.0, 104.0, 112.0),
        "IWD": _history(100.0, 101.0, 104.0),
        "IWM": _history(100.0, 99.0, 102.0),
        "XLF": _history(100.0, 103.0, 107.0),
        "XLV": _history(100.0, 101.0, 103.0),
        "XLE": _history(100.0, 97.0, 101.0),
        "XLI": _history(100.0, 102.0, 105.0),
        "IEF": _history(100.0, 100.4, 101.2),
        "TLT": _history(100.0, 99.5, 104.0),
        "LQD": _history(100.0, 100.8, 102.3),
        "GLD": _history(100.0, 101.0, 104.1),
    }

    diagnostics_inputs = _build_backtest_diagnostics_inputs(
        portfolio_name="Candidate",
        weights=[PortfolioWeightInput(symbol="SPY", target_weight=1.0)],
        result=result,
        benchmark_rows=histories["SPY"],
        histories=histories,
    )

    assert diagnostics_inputs.synthetic_snapshot.statement.detected_format == "synthetic_backtest"
    assert diagnostics_inputs.replay_daily_states[-1].total_portfolio_value == 110000
    assert diagnostics_inputs.benchmark_price_history[-1]["date"] == "2024-02-01"
    assert "QQQ" in diagnostics_inputs.factor_price_histories


def test_portfolio_allocation_backtest_route_returns_reference_assumptions_and_metadata(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "VUAA", "target_weight": 0.6}, {"symbol": "TLT", "target_weight": 0.4}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "commission_bps": 2,
            "slippage_bps": 3,
            "price_basis": "adjusted_close",
            "execution_price_field": "close",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reference_result"] is not None
    assert payload["candidate_result"]["assumptions"]["execution_lag_days"] == 1
    assert payload["candidate_result"]["assumptions"]["tax_treatment"] == "pre_tax"
    assert payload["candidate_result"]["instrument_metadata"][0]["symbol"] == "VUAA"
    assert payload["candidate_result"]["status"] in {"ok", "degraded"}
    assert payload["reference_diagnostics"] is not None
    assert payload["candidate_diagnostics"] is not None
    assert payload["candidate_diagnostics"]["provenance"]["snapshot_basis"] == "synthetic_replay_snapshot"
    assert payload["candidate_diagnostics"]["provenance"]["historical_basis"] == "market_data_history"
    assert payload["diagnostics_comparison"] is not None
    assert payload["diagnostics_comparison"]["factor_exposure_changes"]
    assert payload["diagnostics_comparison"]["volatility_changes"]


def test_portfolio_allocation_backtest_route_enforces_execution_lag() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 0,
        },
    )

    assert response.status_code == 400


def test_portfolio_allocation_backtest_route_rejects_invalid_weight_sum() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "weights": [{"symbol": "SPY", "target_weight": 0.7}, {"symbol": "TLT", "target_weight": 0.1}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400


def test_portfolio_allocation_backtest_route_rejects_negative_weights() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "weights": [{"symbol": "SPY", "target_weight": 1.1}, {"symbol": "TLT", "target_weight": -0.1}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400


def test_portfolio_allocation_backtest_falls_back_to_spy_history_for_vuaa(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "VUAA", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_result"]["starting_weights"][0]["symbol"] == "VUAA"


def test_portfolio_allocation_backtest_route_rejects_candidate_reference_with_insufficient_common_dates(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 50.0},
            {"date": "2024-01-03", "price": 51.0},
        ],
        "BBB": [
            {"date": "2024-01-03", "price": 80.0},
            {"date": "2024-01-04", "price": 81.0},
        ],
        "QQQ": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "AAA", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "BBB", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Not enough common dates across candidate, reference, and benchmark"}


def test_portfolio_allocation_backtest_falls_back_to_gld_history_for_sgld(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "SGLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "SGLD", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_result"]["starting_weights"][0]["symbol"] == "SGLD"


def test_portfolio_allocation_backtest_falls_back_to_dbc_history_for_icom(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "ICOM": _history(20.0, 20.5, 20.8, 21.0, 21.2),
        "DBC": _history(20.0, 20.5, 20.8, 21.0, 21.2),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "ICOM", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_result"]["starting_weights"][0]["symbol"] == "ICOM"


def test_portfolio_allocation_backtest_falls_back_to_slv_history_for_isln(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "ISLN": _history(20.0, 20.4, 20.8, 21.0, 21.2),
        "SLV": _history(20.0, 20.4, 20.8, 21.0, 21.2),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
        "DBC": _history(20.0, 20.5, 20.8, 21.0, 21.2),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "ISLN", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_result"]["starting_weights"][0]["symbol"] == "ISLN"
