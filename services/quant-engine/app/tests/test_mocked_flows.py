from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app


statement_path = Path(r"C:\projects\investments\portfolio\docs\2025.pdf")
if not statement_path.exists():
    statement_path = Path(r"C:\projects\investments\portfolio\docs\IB2025.pdf")
STATEMENT_PATH = str(statement_path)
statement_2026_path = Path(r"C:\projects\investments\portfolio\docs\2026.pdf")
if not statement_2026_path.exists():
    statement_2026_path = Path(r"C:\projects\investments\portfolio\docs\IB2026.pdf")
STATEMENT_2026_PATH = str(statement_2026_path)
FREEDOM24_PATH = str(Path(r"C:\projects\investments\portfolio\docs\FF2026.pdf"))


def _require_path(path: str) -> None:
    if not Path(path).exists():
        pytest.skip(f"Missing local test fixture: {path}")


def test_analyze_route_returns_bootstrap_payload(mocker) -> None:
    _require_path(STATEMENT_PATH)

    client = TestClient(app)
    response = client.post(
        "/portfolios/import/interactive-brokers/analyze",
        json={"statement_path": STATEMENT_PATH, "benchmark_symbol": "SPY", "symbol_overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["statement"]["account_id"] == "U8516450"
    assert "history_context" in payload


def test_analyze_route_returns_bootstrap_payload_for_freedom24(mocker) -> None:
    _require_path(FREEDOM24_PATH)

    client = TestClient(app)
    response = client.post(
        "/portfolios/import/interactive-brokers/analyze",
        json={"statement_path": FREEDOM24_PATH, "benchmark_symbol": "SPY", "symbol_overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["statement"]["importer"] == "freedom24"
    assert payload["snapshot"]["statement"]["account_id"] == "185960"


def test_analyze_route_returns_bootstrap_payload_for_multiple_statement_paths(mocker) -> None:
    _require_path(STATEMENT_PATH)
    _require_path(STATEMENT_2026_PATH)

    client = TestClient(app)
    response = client.post(
        "/portfolios/import/interactive-brokers/analyze",
        json={"statement_paths": [STATEMENT_PATH, STATEMENT_2026_PATH], "benchmark_symbol": "SPY", "symbol_overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["snapshot"]["statements"]) == 2
    assert payload["snapshot"]["statement"]["account_id"] == "U8516450"


def test_dashboard_history_route_with_mocked_market_data(mocker) -> None:
    mock_service = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [{"date": "2026-04-10", "price": 100.0}]
    service_instance.get_historical_prices_for_symbols.return_value = {"AAPL": [{"date": "2026-04-10", "price": 100.0}]}

    client = TestClient(app)
    response = client.post(
        "/engines/dashboard-history/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2025.pdf"],
            "positions": [{"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD"}],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
            "history_context": {
                "benchmark_symbol": "SPY",
                "history_start_date": "2026-04-10",
                "history_end_date": "2026-04-10",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "daily_states" in payload
    assert "performance_series" in payload
    assert payload["source_status"]["performance_history"] == "unavailable"
    service_instance.get_historical_prices.assert_not_called()
    service_instance.get_historical_prices_for_symbols.assert_not_called()


def test_exposure_route_returns_current_state_view_when_etf_holdings_are_unresolved(mocker) -> None:
    mock_service = mocker.patch("app.services.exposure_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_etf_holdings.side_effect = [
        (None, []),
        (None, []),
    ]

    client = TestClient(app)
    response = client.post(
        "/engines/exposure/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2026-04-10 - 2026-04-11",
            "imported_at": "2026-04-11T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["snapshot.json"],
            "positions": [
                {"symbol": "VUAA", "market_value": 900, "quantity": 1, "currency": "USD", "sector": "Broad Market"},
                {"symbol": "AAPL", "market_value": 100, "quantity": 1, "currency": "USD", "sector": "Technology"},
            ],
            "cash_balances": [{"currency": "USD", "amount": 0}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["lookthrough"]["portfolio_market_value"] == 1000
    assert payload["lookthrough"]["covered_market_value"] == 100
    assert payload["lookthrough"]["coverage_ratio"] == 0.1
    assert payload["lookthrough"]["uncovered_positions"] == ["VUAA"]
    assert payload["lookthrough"]["etf_resolution"] == {}
    assert payload["availability"]["lookthrough_status"] == "partial"
    assert payload["availability"]["lookthrough_confidence"] == "medium"
    assert payload["availability"]["benchmark_overlap_status"] == "unavailable"
    assert payload["availability"]["benchmark_overlap_confidence"] == "low"
    assert payload["market_overlap"]["benchmark_symbol"] == "SPY"
    assert payload["market_overlap"]["overlap_weight"] is None
    assert payload["market_overlap"]["portfolio_in_benchmark_weight"] is None
    assert payload["market_overlap"]["benchmark_covered_weight"] is None
    assert payload["market_overlap"]["active_share"] is None
    assert payload["lookthrough"]["top_constituents"][0]["symbol"] == "VUAA"
    assert payload["lookthrough"]["top_constituents"][1]["symbol"] == "AAPL"
    assert payload["current_state_concentration"]["top_1_position_weight"] == 0.9
    assert payload["current_state_concentration"]["top_3_position_weight"] == 1.0
    assert payload["current_state_concentration"]["position_hhi"] == 0.82
    assert payload["current_state_concentration"]["effective_holdings"] == 1.22


def test_exposure_route_keeps_lookthrough_but_zeroes_overlap_when_benchmark_holdings_are_unresolved(mocker) -> None:
    mock_service = mocker.patch("app.services.exposure_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_etf_holdings.side_effect = [
        (
            "SPY",
            [
                {"asset": "AAPL", "name": "APPLE INC", "weightPercentage": 6.0},
                {"asset": "MSFT", "name": "MICROSOFT CORP", "weightPercentage": 5.0},
            ],
        ),
        (None, []),
    ]

    client = TestClient(app)
    response = client.post(
        "/engines/exposure/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2026-04-10 - 2026-04-11",
            "imported_at": "2026-04-11T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["snapshot.json"],
            "positions": [
                {"symbol": "VUAA", "market_value": 900, "quantity": 1, "currency": "USD", "sector": "Broad Market"},
                {"symbol": "AAPL", "market_value": 100, "quantity": 1, "currency": "USD", "sector": "Technology"},
            ],
            "cash_balances": [{"currency": "USD", "amount": 0}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["lookthrough"]["portfolio_market_value"] == 1000
    assert payload["lookthrough"]["covered_market_value"] == 1000
    assert payload["lookthrough"]["coverage_ratio"] == 1.0
    assert payload["lookthrough"]["uncovered_positions"] == []
    assert payload["lookthrough"]["etf_resolution"] == {"VUAA": "SPY"}
    assert payload["availability"]["lookthrough_status"] == "live"
    assert payload["availability"]["lookthrough_confidence"] == "high"
    assert payload["availability"]["benchmark_overlap_status"] == "unavailable"
    assert payload["availability"]["benchmark_overlap_confidence"] == "low"
    assert payload["market_overlap"]["benchmark_symbol"] == "SPY"
    assert payload["market_overlap"]["overlap_weight"] is None
    assert payload["market_overlap"]["portfolio_in_benchmark_weight"] is None
    assert payload["market_overlap"]["benchmark_covered_weight"] is None
    assert payload["market_overlap"]["active_share"] is None
    assert payload["lookthrough"]["top_constituents"][0]["symbol"] == "AAPL"
    assert payload["lookthrough"]["top_constituents"][1]["symbol"] == "MSFT"
    assert payload["current_state_concentration"]["top_1_position_weight"] == 0.9
    assert payload["current_state_concentration"]["top_3_position_weight"] == 1.0
    assert payload["current_state_concentration"]["position_hhi"] == 0.82
    assert payload["current_state_concentration"]["effective_holdings"] == 1.22


def test_dashboard_history_route_without_history_context_returns_unavailable_without_market_data_calls(mocker) -> None:
    mock_service = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service_instance = mock_service.return_value

    client = TestClient(app)
    response = client.post(
        "/engines/dashboard-history/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2025.pdf"],
            "positions": [{"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD"}],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"]["performance_history"] == "unavailable"
    assert payload["source_status"]["monthly_returns"] == "unavailable"
    assert payload["daily_states"] == []
    assert payload["performance_series"] == []
    service_instance.get_historical_prices.assert_not_called()
    service_instance.get_historical_prices_for_symbols.assert_not_called()


def test_dashboard_history_route_with_incomplete_history_context_returns_unavailable_without_market_data_calls(mocker) -> None:
    mock_service = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service_instance = mock_service.return_value

    client = TestClient(app)
    response = client.post(
        "/engines/dashboard-history/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2025.pdf"],
            "positions": [{"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD"}],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
            "history_context": {
                "benchmark_symbol": "SPY",
                "history_start_date": "2026-04-10",
                "history_end_date": None,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"]["performance_history"] == "unavailable"
    assert payload["source_status"]["monthly_returns"] == "unavailable"
    assert payload["daily_states"] == []
    assert payload["performance_series"] == []
    service_instance.get_historical_prices.assert_not_called()
    service_instance.get_historical_prices_for_symbols.assert_not_called()


def test_imported_dashboard_history_route_with_mocked_market_data(mocker) -> None:
    mock_service = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [{"date": "2026-04-10", "price": 100.0}]
    service_instance.get_historical_prices_for_symbols.return_value = {"AAPL": [{"date": "2026-04-10", "price": 100.0}]}

    client = TestClient(app)
    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "IB2026.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-10",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 1000}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1000, "currency": "USD", "as_of_date": "2026-04-10", "cost_basis": 1000, "close_price": 100, "unrealized_pnl": 0}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"]["performance_history"] == "live"


def test_imported_dashboard_history_route_reconciles_terminal_value_to_statement_totals(mocker) -> None:
    mock_service = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 101.0},
    ]
    service_instance.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0},
            {"date": "2026-04-11", "price": 101.0},
        ]
    }

    client = TestClient(app)
    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "IB2026.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": {"starting_nav": 1000, "ending_nav": 1200},
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 100}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1100, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 110, "unrealized_pnl": 100}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"]["performance_history"] == "live"
    assert payload["daily_states"][-1]["total_portfolio_value"] == 1200
    assert payload["range_metrics"]["All"]["summary"]["end_value"] == 1200


def test_imported_dashboard_history_route_accepts_mixed_broker_snapshot_with_mocked_market_data(mocker) -> None:
    mock_service = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 101.0},
    ]
    service_instance.get_historical_prices_for_symbols.return_value = {
        "AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}],
        "VUAA": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}],
    }

    client = TestClient(app)
    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "multi_broker",
                "imported_at": "2026-04-14T00:00:00Z",
                "source_path": "combined.pdf",
                "detected_format": "pdf",
                "account_id": "185960 + U8516450",
                "base_currency": "USD",
                "statement_period": "2025-12-31 - 2026-04-13",
                "page_count": 2,
            },
            "statements": [
                {
                    "importer": "freedom24",
                    "imported_at": "2026-04-14T00:00:00Z",
                    "source_path": "FF2026.pdf",
                    "detected_format": "pdf",
                    "account_id": "185960",
                    "base_currency": "USD",
                    "statement_period": "2025-12-31 - 2026-04-11",
                    "page_count": 1,
                },
                {
                    "importer": "interactive_brokers",
                    "imported_at": "2026-04-14T00:00:00Z",
                    "source_path": "IB2026.pdf",
                    "detected_format": "pdf",
                    "account_id": "U8516450",
                    "base_currency": "USD",
                    "statement_period": "2026-01-01 - 2026-04-13",
                    "page_count": 1,
                },
            ],
            "statement_totals": {"starting_nav": 1000, "ending_nav": 1300},
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 200}],
            "positions": [
                {"symbol": "AAPL", "quantity": 5, "market_value": 550, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 500, "close_price": 110, "unrealized_pnl": 50},
                {"symbol": "VUAA", "quantity": 5, "market_value": 550, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 500, "close_price": 110, "unrealized_pnl": 50},
            ],
            "ledger_entries": [
                {"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 5, "price": 100, "gross_amount": 500, "net_amount": 500, "currency": "USD", "source_section": "Trades"},
                {"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "VUAA", "quantity": 5, "price": 100, "gross_amount": 500, "net_amount": 500, "currency": "USD", "source_section": "Trades"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"]["performance_history"] == "live"
    assert payload["source_status"]["monthly_returns"] == "live"
    assert payload["daily_states"][-1]["total_portfolio_value"] == 1300


def test_imported_dashboard_history_route_marks_missing_symbol_price_history_as_unavailable(mocker) -> None:
    mock_service = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [
        {"date": "2026-04-10", "price": 100.0},
        {"date": "2026-04-11", "price": 101.0},
    ]
    service_instance.get_historical_prices_for_symbols.return_value = {"AAPL": []}

    client = TestClient(app)
    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "IB2026.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 1000}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1100, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 110, "unrealized_pnl": 100}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"]["performance_history"] == "unavailable"
    assert payload["source_status"]["monthly_returns"] == "unavailable"
    assert payload["daily_states"] == []
    assert payload["performance_series"] == []
    assert payload["range_metrics"]["3M"]["summary"]["start_value"] is None


def test_imported_dashboard_history_route_marks_missing_benchmark_history_as_unavailable(mocker) -> None:
    mock_service = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = []
    service_instance.get_historical_prices_for_symbols.return_value = {"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]}

    client = TestClient(app)
    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "IB2026.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 1000}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1100, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 110, "unrealized_pnl": 100}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"]["performance_history"] == "unavailable"
    assert payload["source_status"]["monthly_returns"] == "unavailable"
    assert payload["daily_states"] == []
    assert payload["performance_series"] == []
    assert payload["range_metrics"]["3M"]["summary"]["start_value"] is None


def test_imported_diagnostics_route_with_mocked_market_data(mocker) -> None:
    mock_service = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]
    service_instance.get_historical_prices_for_symbols.return_value = {"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}], "SPY": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]}

    client = TestClient(app)
    response = client.post(
        "/engines/diagnostics/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "IB2026.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 1000}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1100, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 110, "unrealized_pnl": 100}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is True
    assert payload["availability"]["history_context_required"] is True


def test_imported_diagnostics_route_marks_missing_symbol_price_history_as_unavailable(mocker) -> None:
    mock_service = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]
    service_instance.get_historical_prices_for_symbols.side_effect = [
        {"AAPL": []},
        {},
    ]

    client = TestClient(app)
    response = client.post(
        "/engines/diagnostics/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "IB2026.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 1000}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1100, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 110, "unrealized_pnl": 100}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is False
    assert payload["availability"]["history_context_required"] is True
    assert payload["risk_summary"]["observations"] == 0


def test_imported_diagnostics_route_marks_missing_benchmark_history_as_unavailable(mocker) -> None:
    mock_service = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = []
    service_instance.get_historical_prices_for_symbols.side_effect = [
        {"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]},
        {},
    ]

    client = TestClient(app)
    response = client.post(
        "/engines/diagnostics/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "IB2026.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 1000}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1100, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 110, "unrealized_pnl": 100}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is False
    assert payload["availability"]["history_context_required"] is True
    assert payload["risk_summary"]["observations"] == 0


def test_imported_diagnostics_route_accepts_mixed_broker_snapshot_with_mocked_market_data(mocker) -> None:
    mock_service = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]
    service_instance.get_historical_prices_for_symbols.return_value = {
        "AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}],
        "VUAA": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}],
        "SPY": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}],
    }

    client = TestClient(app)
    response = client.post(
        "/engines/diagnostics/run-imported",
        json={
            "statement": {
                "importer": "multi_broker",
                "imported_at": "2026-04-14T00:00:00Z",
                "source_path": "combined.pdf",
                "detected_format": "pdf",
                "account_id": "185960 + U8516450",
                "base_currency": "USD",
                "statement_period": "2025-12-31 - 2026-04-13",
                "page_count": 2,
            },
            "statements": [
                {
                    "importer": "freedom24",
                    "imported_at": "2026-04-14T00:00:00Z",
                    "source_path": "FF2026.pdf",
                    "detected_format": "pdf",
                    "account_id": "185960",
                    "base_currency": "USD",
                    "statement_period": "2025-12-31 - 2026-04-11",
                    "page_count": 1,
                },
                {
                    "importer": "interactive_brokers",
                    "imported_at": "2026-04-14T00:00:00Z",
                    "source_path": "IB2026.pdf",
                    "detected_format": "pdf",
                    "account_id": "U8516450",
                    "base_currency": "USD",
                    "statement_period": "2026-01-01 - 2026-04-13",
                    "page_count": 1,
                },
            ],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 200}],
            "positions": [
                {"symbol": "AAPL", "quantity": 5, "market_value": 550, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 500, "close_price": 110, "unrealized_pnl": 50},
                {"symbol": "VUAA", "quantity": 5, "market_value": 550, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 500, "close_price": 110, "unrealized_pnl": 50},
            ],
            "ledger_entries": [
                {"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 5, "price": 100, "gross_amount": 500, "net_amount": 500, "currency": "USD", "source_section": "Trades"},
                {"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "VUAA", "quantity": 5, "price": 100, "gross_amount": 500, "net_amount": 500, "currency": "USD", "source_section": "Trades"},
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is True
    assert payload["availability"]["history_context_required"] is True
    assert payload["risk_summary"]["benchmark_symbol"] == "SPY"
    assert payload["risk_summary"]["observations"] > 0


def test_diagnostics_route_accepts_mixed_broker_history_context_with_mocked_market_data(mocker) -> None:
    mock_service = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]
    service_instance.get_historical_prices_for_symbols.return_value = {
        "AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}],
        "SPY": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}],
    }

    client = TestClient(app)
    response = client.post(
        "/engines/diagnostics/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025-12-31 - 2026-04-13",
            "imported_at": "2026-04-14T00:00:00Z",
            "importer": "multi_broker",
            "source_file_names": ["FF2026.pdf", "IB2026.pdf"],
            "positions": [{"symbol": "AAPL", "market_value": 1100, "quantity": 10, "currency": "USD", "sector": "Technology"}],
            "cash_balances": [{"currency": "USD", "amount": 100}],
            "history_context": {
                "benchmark_symbol": "SPY",
                "statement_period": "2025-12-31 - 2026-04-13",
                "imported_at": "2026-04-14T00:00:00Z",
                "importer": "multi_broker",
                "source_file_names": ["FF2026.pdf", "IB2026.pdf"],
                "history_start_date": "2025-12-31",
                "history_end_date": "2026-04-13",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is True
    assert payload["availability"]["history_context_required"] is True
    assert payload["risk_summary"]["benchmark_symbol"] == "SPY"
    assert payload["risk_summary"]["observations"] > 0


def test_diagnostics_route_marks_missing_symbol_price_history_as_unavailable(mocker) -> None:
    mock_service = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]
    service_instance.get_historical_prices_for_symbols.side_effect = [
        {"AAPL": []},
        {},
    ]

    client = TestClient(app)
    response = client.post(
        "/engines/diagnostics/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2026-04-10 - 2026-04-11",
            "imported_at": "2026-04-11T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2026.pdf"],
            "positions": [{"symbol": "AAPL", "market_value": 1100, "quantity": 10, "currency": "USD", "sector": "Technology"}],
            "cash_balances": [{"currency": "USD", "amount": 100}],
            "history_context": {
                "benchmark_symbol": "SPY",
                "statement_period": "2026-04-10 - 2026-04-11",
                "imported_at": "2026-04-11T00:00:00Z",
                "importer": "interactive_brokers",
                "source_file_names": ["IB2026.pdf"],
                "history_start_date": "2026-04-10",
                "history_end_date": "2026-04-11",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is False
    assert payload["availability"]["history_context_required"] is True
    assert payload["risk_summary"]["observations"] == 0


def test_diagnostics_route_marks_missing_benchmark_history_as_unavailable(mocker) -> None:
    mock_service = mocker.patch("app.services.diagnostics_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices.return_value = []
    service_instance.get_historical_prices_for_symbols.side_effect = [
        {"AAPL": [{"date": "2026-04-10", "price": 100.0}, {"date": "2026-04-11", "price": 101.0}]},
        {},
    ]

    client = TestClient(app)
    response = client.post(
        "/engines/diagnostics/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2026-04-10 - 2026-04-11",
            "imported_at": "2026-04-11T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2026.pdf"],
            "positions": [{"symbol": "AAPL", "market_value": 1100, "quantity": 10, "currency": "USD", "sector": "Technology"}],
            "cash_balances": [{"currency": "USD", "amount": 100}],
            "history_context": {
                "benchmark_symbol": "SPY",
                "statement_period": "2026-04-10 - 2026-04-11",
                "imported_at": "2026-04-11T00:00:00Z",
                "importer": "interactive_brokers",
                "source_file_names": ["IB2026.pdf"],
                "history_start_date": "2026-04-10",
                "history_end_date": "2026-04-11",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is False
    assert payload["availability"]["history_context_required"] is True
    assert payload["risk_summary"]["observations"] == 0
