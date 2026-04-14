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
