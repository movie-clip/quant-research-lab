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
ESPP_PATH = str(Path(r"C:\projects\investments\portfolio\docs\ESPP.pdf"))


def _require_path(path: str) -> None:
    if not Path(path).exists():
        pytest.skip(f"Missing local test fixture: {path}")


def test_health_route() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_import_route_returns_404_for_missing_statement() -> None:
    client = TestClient(app)

    response = client.post("/portfolios/import/interactive-brokers", json={"statement_path": "missing.pdf"})

    assert response.status_code == 404


def test_analyze_route_returns_400_when_no_statement_paths_are_supplied() -> None:
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze",
        json={"benchmark_symbol": "SPY", "symbol_overrides": {}},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "At least one statement file is required"}


def test_cors_preflight_for_local_frontend() -> None:
    client = TestClient(app)

    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_upload_analyze_route_accepts_pdf_statement() -> None:
    _require_path(STATEMENT_PATH)
    client = TestClient(app)

    with open(STATEMENT_PATH, "rb") as statement_file:
        response = client.post(
            "/portfolios/import/interactive-brokers/analyze-upload",
            files=[("statement_files", ("2025.pdf", statement_file, "application/pdf"))],
            data={"benchmark_symbol": "SPY", "symbol_overrides": "{}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["statement"]["account_id"] == "U8516450"


def test_upload_analyze_route_rejects_missing_statement_files() -> None:
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze-upload",
        data={"benchmark_symbol": "SPY", "symbol_overrides": "{}"},
    )

    assert response.status_code == 422


def test_upload_analyze_route_accepts_freedom24_pdf_statement() -> None:
    _require_path(FREEDOM24_PATH)
    client = TestClient(app)

    with open(FREEDOM24_PATH, "rb") as statement_file:
        response = client.post(
            "/portfolios/import/interactive-brokers/analyze-upload",
            files=[("statement_files", ("FF2026.pdf", statement_file, "application/pdf"))],
            data={"benchmark_symbol": "SPY", "symbol_overrides": "{}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["statement"]["importer"] == "freedom24"
    assert payload["snapshot"]["statement"]["account_id"] == "185960"


def test_upload_analyze_route_accepts_espp_pdf_statement() -> None:
    _require_path(ESPP_PATH)
    client = TestClient(app)

    with open(ESPP_PATH, "rb") as statement_file:
        response = client.post(
            "/portfolios/import/interactive-brokers/analyze-upload",
            files=[("statement_files", ("ESPP.pdf", statement_file, "application/pdf"))],
            data={"benchmark_symbol": "SPY", "symbol_overrides": "{}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["statement"]["importer"] == "espp"
    assert payload["snapshot"]["statement"]["account_id"] == "I09548809"


def test_upload_analyze_route_rejects_invalid_symbol_overrides_json() -> None:
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze-upload",
        files=[("statement_files", ("2025.pdf", b"fake-pdf", "application/pdf"))],
        data={"benchmark_symbol": "SPY", "symbol_overrides": "not-json"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Symbol overrides must be valid JSON"}


def test_upload_analyze_route_rejects_non_object_symbol_overrides_json() -> None:
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze-upload",
        files=[("statement_files", ("2025.pdf", b"fake-pdf", "application/pdf"))],
        data={"benchmark_symbol": "SPY", "symbol_overrides": "[]"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Symbol overrides must be valid JSON"}


def test_analyze_route_accepts_multiple_statement_paths() -> None:
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
    assert payload["snapshot"]["statement"]["statement_period"] == "2025-01-01 - 2026-04-08"


def test_analyze_route_accepts_mixed_broker_statement_paths() -> None:
    mixed_ib_path = STATEMENT_2026_PATH
    _require_path(mixed_ib_path)
    _require_path(FREEDOM24_PATH)
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze",
        json={"statement_paths": [mixed_ib_path, FREEDOM24_PATH], "benchmark_symbol": "SPY", "symbol_overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["snapshot"]["statement"]["importer"] == "multi_broker"
    assert "185960" in payload["snapshot"]["statement"]["account_id"]
    assert "U8516450" in payload["snapshot"]["statement"]["account_id"]
    assert len(payload["snapshot"]["statements"]) == 2
    assert payload["history_context"]["importer"] == "multi_broker"
    assert payload["history_context"]["statement_period"] == f'{payload["history_context"]["history_start_date"]} - {payload["history_context"]["history_end_date"]}'
    assert payload["history_context"]["history_start_date"] <= payload["history_context"]["history_end_date"]
    assert set(payload["history_context"]["source_file_names"]) == {FREEDOM24_PATH, STATEMENT_2026_PATH}


def test_analyze_snapshot_route_accepts_portfolio_snapshot_payload() -> None:
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze-snapshot",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2025.pdf"],
            "positions": [
                {"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD", "sector": "Technology"},
                {"symbol": "MSFT", "market_value": 8000, "quantity": 8, "currency": "USD", "sector": "Technology"},
            ],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"]["total_market_value"] == 18000
    assert payload["snapshot"]["statement"]["detected_format"] == "snapshot"


def test_analyze_snapshot_route_rejects_invalid_importer_value() -> None:
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze-snapshot",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "not_a_broker",
            "source_file_names": ["snapshot.json"],
            "positions": [{"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD", "sector": "Technology"}],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
        },
    )

    assert response.status_code == 422


def test_analyze_snapshot_route_rejects_invalid_cash_currency_length() -> None:
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze-snapshot",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["snapshot.json"],
            "positions": [{"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD", "sector": "Technology"}],
            "cash_balances": [{"currency": "US", "amount": 1000}],
        },
    )

    assert response.status_code == 422


def test_analyze_snapshot_route_rejects_position_missing_market_value() -> None:
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze-snapshot",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["snapshot.json"],
            "positions": [{"symbol": "AAPL", "quantity": 10, "currency": "USD", "sector": "Technology"}],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
        },
    )

    assert response.status_code == 422


def test_exposure_engine_route_accepts_portfolio_snapshot_payload() -> None:
    client = TestClient(app)

    response = client.post(
        "/engines/exposure/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2025.pdf"],
            "positions": [
                {"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD", "sector": "Technology"},
                {"symbol": "MSFT", "market_value": 8000, "quantity": 8, "currency": "USD", "sector": "Technology"},
            ],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["overview"]["total_market_value"] == 18000
    assert "lookthrough" in payload
    assert "market_overlap" in payload
    assert payload["provenance"]["snapshot_basis"] == "snapshot_request"
    assert payload["provenance"]["price_basis"] == "not_applicable"
    assert payload["run_metadata"]["engine_id"] == "exposure_engine_v1"
    assert payload["run_metadata"]["source_status"] == {
        "lookthrough_resolution": "live",
        "benchmark_holdings": "live",
    }
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-10T00:00:00+00:00",
        "snapshot_as_of_date": "2026-04-10",
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }
    assert payload["current_state_concentration"]["top_1_position_weight"] == 0.5556
    assert payload["current_state_concentration"]["top_3_position_weight"] == 1.0
    assert payload["current_state_concentration"]["position_hhi"] == 0.5062
    assert payload["current_state_concentration"]["effective_holdings"] == 1.98


def test_diagnostics_engine_route_marks_snapshot_only_history_as_unavailable() -> None:
    client = TestClient(app)

    response = client.post(
        "/engines/diagnostics/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2025",
            "imported_at": "2026-04-10T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["IB2025.pdf"],
            "positions": [
                {"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD", "sector": "Technology"},
            ],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is False
    assert payload["availability"]["history_context_required"] is True
    assert payload["availability"]["status"] == "unavailable"
    assert payload["availability"]["note"] == "Historical diagnostics are unavailable from snapshot-only input. Attach PortfolioHistoryContext to run rolling diagnostics accurately."
    assert payload["provenance"]["note"] == "Historical diagnostics are unavailable because snapshot-style input did not include the history context needed to build a valid historical portfolio path."
    assert payload["provenance"]["history_truth_class"] == "unavailable"
    assert payload["provenance"]["price_basis"] == "unavailable"
    assert payload["run_metadata"]["diagnostics_id"] == "diagnostics_engine_v1"
    assert payload["run_metadata"]["price_basis"] == "unavailable"
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-10T00:00:00+00:00",
        "snapshot_as_of_date": "2026-04-10",
        "history_start_date": None,
        "history_end_date": None,
        "dataset_version": "market_data_service_v1",
    }
    assert payload["run_metadata"]["factor_model_parameters"] == {
        "rolling_windows_days": [20, 60, 252],
        "current_reliability_window_days": 60,
        "minimum_window_observations": {"20": 25, "60": 75, "252": 275},
        "collinearity_warning_threshold": 0.85,
        "orthogonalization_basis": "factor_proxy_definition_order",
        "ridge_lambda": 1e-05,
    }
    assert payload["run_metadata"]["source_status"] == {
        "portfolio_history": "unavailable",
        "benchmark_history": "unavailable",
        "factor_history": "unavailable",
    }
    assert payload["stress_scenarios"][0]["estimated_return_pct"] is None
    assert payload["stress_scenarios"][0]["status"] == "unavailable"
    assert payload["drawdown_summary"] == {
        "current_drawdown_pct": None,
        "max_drawdown_pct": None,
    }
    assert payload["volatility_summary"] == {
        "portfolio_volatility_pct": None,
        "benchmark_volatility_pct": None,
        "downside_volatility_pct": None,
        "tracking_error_pct": None,
    }
    assert payload["risk_concentration_summary"] == {
        "top_1_factor_risk_share": None,
        "top_3_factor_risk_share": None,
        "top_1_position_risk_share": None,
        "top_5_position_risk_share": None,
        "factor_hhi": None,
        "position_hhi": None,
    }


def test_diagnostics_engine_route_uses_history_context_when_present() -> None:
    client = TestClient(app)

    response = client.post(
        "/engines/diagnostics/run",
        json={
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "statement_period": "2026-04-10 - 2026-04-23",
            "imported_at": "2026-04-23T00:00:00Z",
            "importer": "interactive_brokers",
            "source_file_names": ["snapshot.json"],
            "positions": [{"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD", "sector": "Technology"}],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
            "history_context": {
                "benchmark_symbol": "SPY",
                "history_start_date": "2026-04-10",
                "history_end_date": "2026-04-23",
                "statement_period": "2026-04-10 - 2026-04-23",
                "imported_at": "2026-04-23T00:00:00Z",
                "importer": "interactive_brokers",
                "source_file_names": ["snapshot.json"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is True
    assert payload["availability"]["history_context_required"] is True
    assert payload["availability"]["status"] == "ok"
    assert payload["provenance"]["snapshot_basis"] == "snapshot_request"
    assert payload["provenance"]["historical_basis"] == "market_data_history"
    assert payload["provenance"]["history_truth_class"] == "synthetic_history_derived"
    assert payload["provenance"]["price_basis"] == "close"
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-23T00:00:00+00:00",
        "snapshot_as_of_date": "2026-04-23",
        "history_start_date": "2026-04-10",
        "history_end_date": "2026-04-17",
        "dataset_version": "market_data_service_v1",
    }
    assert payload["run_metadata"]["factor_model_parameters"] == {
        "rolling_windows_days": [20, 60, 252],
        "current_reliability_window_days": 60,
        "minimum_window_observations": {"20": 25, "60": 75, "252": 275},
        "collinearity_warning_threshold": 0.85,
        "orthogonalization_basis": "factor_proxy_definition_order",
        "ridge_lambda": 1e-05,
    }
    assert payload["run_metadata"]["source_status"] == {
        "portfolio_history": "synthetic_snapshot_history",
        "benchmark_history": "live_market_data",
        "factor_history": "live_market_data",
    }
    assert payload["run_metadata"]["confidence"] == "medium"
    assert payload["drawdown_summary"]["current_drawdown_pct"] == payload["volatility_regime"]["snapshot"]["current_drawdown_pct"]
    assert payload["drawdown_summary"]["max_drawdown_pct"] == payload["volatility_regime"]["snapshot"]["max_drawdown_pct"]
    assert payload["volatility_summary"]["portfolio_volatility_pct"] == payload["risk_summary"]["portfolio_volatility_pct"]
    assert payload["volatility_summary"]["benchmark_volatility_pct"] == payload["risk_summary"]["benchmark_volatility_pct"]
    assert payload["volatility_summary"]["downside_volatility_pct"] == payload["volatility_regime"]["snapshot"]["downside_vol_60d"]
    assert payload["volatility_summary"]["tracking_error_pct"] == payload["relative_risk"]["tracking_error_pct"]
    assert payload["risk_concentration_summary"]["factor_hhi"] == payload["risk_contribution_breakdown"]["concentration"]["factor_hhi"]
    assert payload["risk_concentration_summary"]["position_hhi"] == payload["risk_contribution_breakdown"]["concentration"]["position_hhi"]


def test_dashboard_history_engine_route_accepts_snapshot_with_history_context() -> None:
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
            "positions": [
                {"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD", "sector": "Technology"},
                {"symbol": "MSFT", "market_value": 8000, "quantity": 8, "currency": "USD", "sector": "Technology"},
            ],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
            "history_context": {
                "benchmark_symbol": "SPY",
                "history_start_date": "2026-04-10",
                "history_end_date": "2026-04-10",
                "statement_period": "2025",
                "source_file_names": ["IB2025.pdf"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert "daily_states" in payload
    assert "performance_series" in payload
    assert "source_status" in payload
    assert payload["source_status"]["performance_history"] == "unavailable"
    assert payload["run_metadata"]["source_status"] == {
        "performance_history": "unavailable",
        "monthly_returns": "unavailable",
        "benchmark_history": "unavailable",
    }
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-10T00:00:00+00:00",
        "snapshot_as_of_date": "2026-04-10",
        "history_start_date": "2026-04-10",
        "history_end_date": "2026-04-10",
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }
    assert "range_metrics" in payload
    assert payload["range_metrics"]["3M"]["summary"]["start_value"] is None


def test_dashboard_history_engine_route_rejects_invalid_history_context_shape() -> None:
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
            "positions": [
                {"symbol": "AAPL", "market_value": 10000, "quantity": 10, "currency": "USD", "sector": "Technology"},
            ],
            "cash_balances": [{"currency": "USD", "amount": 1000}],
            "history_context": "not-an-object",
        },
    )

    assert response.status_code == 422


def test_imported_dashboard_history_engine_route_accepts_imported_snapshot_payload() -> None:
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
    assert "daily_states" in payload
    assert "performance_series" in payload
    assert "range_metrics" in payload
    assert payload["run_metadata"]["source_status"] == {
        "performance_history": "live",
        "monthly_returns": "live",
        "benchmark_history": "live_market_data",
    }
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-10T00:00:00+00:00",
        "snapshot_as_of_date": "2026-04-11",
        "history_start_date": "2026-04-10",
        "history_end_date": "2026-04-11",
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }


def test_imported_dashboard_history_engine_route_marks_missing_imported_history_as_unavailable() -> None:
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
            "positions": [],
            "ledger_entries": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source_status"]["performance_history"] == "unavailable"
    assert payload["source_status"]["monthly_returns"] == "unavailable"
    assert payload["run_metadata"]["source_status"] == {
        "performance_history": "unavailable",
        "monthly_returns": "unavailable",
        "benchmark_history": "unavailable",
    }
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-10T00:00:00+00:00",
        "snapshot_as_of_date": None,
        "history_start_date": None,
        "history_end_date": None,
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }
    assert payload["daily_states"] == []
    assert payload["performance_series"] == []
    assert payload["range_metrics"]["3M"]["summary"]["start_value"] is None


def test_imported_dashboard_history_engine_route_rejects_invalid_imported_position_currency_length() -> None:
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
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1100, "currency": "US", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 110, "unrealized_pnl": 100}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 422


def test_imported_diagnostics_engine_route_accepts_imported_snapshot_payload() -> None:
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
    assert payload["availability"]["status"] == "ok"
    assert payload["provenance"]["snapshot_basis"] == "imported_snapshot"
    assert payload["provenance"]["historical_basis"] == "imported_portfolio_history"
    assert payload["provenance"]["history_truth_class"] == "imported_history_equivalent"
    assert payload["provenance"]["price_basis"] == "close"
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-10T00:00:00+00:00",
        "snapshot_as_of_date": "2026-04-11",
        "history_start_date": "2026-04-10",
        "history_end_date": "2026-04-10",
        "dataset_version": "market_data_service_v1",
    }
    assert payload["run_metadata"]["factor_model_parameters"] == {
        "rolling_windows_days": [20, 60, 252],
        "current_reliability_window_days": 60,
        "minimum_window_observations": {"20": 25, "60": 75, "252": 275},
        "collinearity_warning_threshold": 0.85,
        "orthogonalization_basis": "factor_proxy_definition_order",
        "ridge_lambda": 1e-05,
    }
    assert payload["run_metadata"]["source_status"] == {
        "portfolio_history": "imported_replay",
        "benchmark_history": "live_market_data",
        "factor_history": "live_market_data",
    }
    assert payload["run_metadata"]["confidence"] == "high"
    assert payload["drawdown_summary"]["current_drawdown_pct"] == payload["volatility_regime"]["snapshot"]["current_drawdown_pct"]
    assert payload["drawdown_summary"]["max_drawdown_pct"] == payload["volatility_regime"]["snapshot"]["max_drawdown_pct"]
    assert payload["volatility_summary"]["portfolio_volatility_pct"] == payload["risk_summary"]["portfolio_volatility_pct"]
    assert payload["volatility_summary"]["benchmark_volatility_pct"] == payload["risk_summary"]["benchmark_volatility_pct"]
    assert payload["volatility_summary"]["tracking_error_pct"] == payload["relative_risk"]["tracking_error_pct"]
    assert payload["risk_concentration_summary"]["factor_hhi"] == payload["risk_contribution_breakdown"]["concentration"]["factor_hhi"]
    assert payload["risk_concentration_summary"]["position_hhi"] == payload["risk_contribution_breakdown"]["concentration"]["position_hhi"]
    assert payload["risk_summary"]["benchmark_symbol"] == "SPY"


def test_imported_diagnostics_engine_route_marks_missing_imported_history_as_unavailable() -> None:
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
            "positions": [],
            "ledger_entries": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["availability"]["historical_sections_available"] is False
    assert payload["availability"]["history_context_required"] is False
    assert payload["availability"]["status"] == "unavailable"
    assert payload["availability"]["note"] == "Historical diagnostics are unavailable because this imported snapshot does not contain enough broker history to reconstruct a historical portfolio path."
    assert payload["provenance"]["snapshot_basis"] == "imported_snapshot"
    assert payload["provenance"]["historical_basis"] == "unavailable"
    assert payload["provenance"]["history_truth_class"] == "unavailable"
    assert payload["provenance"]["price_basis"] == "unavailable"
    assert payload["provenance"]["note"] == "Historical diagnostics are unavailable because imported broker history could not be reconstructed from this snapshot."
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-10T00:00:00+00:00",
        "snapshot_as_of_date": None,
        "history_start_date": None,
        "history_end_date": None,
        "dataset_version": "market_data_service_v1",
    }
    assert payload["run_metadata"]["factor_model_parameters"] == {
        "rolling_windows_days": [20, 60, 252],
        "current_reliability_window_days": 60,
        "minimum_window_observations": {"20": 25, "60": 75, "252": 275},
        "collinearity_warning_threshold": 0.85,
        "orthogonalization_basis": "factor_proxy_definition_order",
        "ridge_lambda": 1e-05,
    }
    assert payload["run_metadata"]["source_status"] == {
        "portfolio_history": "unavailable",
        "benchmark_history": "unavailable",
        "factor_history": "unavailable",
    }
    assert payload["drawdown_summary"] == {
        "current_drawdown_pct": None,
        "max_drawdown_pct": None,
    }
    assert payload["volatility_summary"] == {
        "portfolio_volatility_pct": None,
        "benchmark_volatility_pct": None,
        "downside_volatility_pct": None,
        "tracking_error_pct": None,
    }
    assert payload["risk_concentration_summary"] == {
        "top_1_factor_risk_share": None,
        "top_3_factor_risk_share": None,
        "top_1_position_risk_share": None,
        "top_5_position_risk_share": None,
        "factor_hhi": None,
        "position_hhi": None,
    }


def test_imported_diagnostics_engine_route_rejects_invalid_imported_cash_currency_length() -> None:
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
            "cash_balances": [{"currency": "US", "ending_cash": 1000}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1100, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 110, "unrealized_pnl": 100}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 422
