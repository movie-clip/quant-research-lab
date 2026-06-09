from pathlib import Path
from fastapi.testclient import TestClient

from app.api.main import app
from app.tests._statement_fixtures import (
    ESPP_PATH as ESPP_FIXTURE_PATH,
    FREEDOM24_PATH as FREEDOM24_FIXTURE_PATH,
    STATEMENT_2025_PATH as STATEMENT_2025_FIXTURE_PATH,
    STATEMENT_2026_PATH as STATEMENT_2026_FIXTURE_PATH,
)

STATEMENT_PATH = str(STATEMENT_2025_FIXTURE_PATH)
STATEMENT_2026_PATH = str(STATEMENT_2026_FIXTURE_PATH)
FREEDOM24_PATH = str(FREEDOM24_FIXTURE_PATH)
ESPP_PATH = str(ESPP_FIXTURE_PATH)


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
    client = TestClient(app)

    response = client.post(
        "/portfolios/import/interactive-brokers/analyze",
        json={"statement_paths": [STATEMENT_PATH, STATEMENT_2026_PATH], "benchmark_symbol": "SPY", "symbol_overrides": {}},
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["snapshot"]["statements"]) == 2
    assert payload["snapshot"]["statement"]["statement_period"] == (
        f'{payload["history_context"]["history_start_date"]} - {payload["history_context"]["history_end_date"]}'
    )


def test_analyze_route_accepts_mixed_broker_statement_paths() -> None:
    mixed_ib_path = STATEMENT_2026_PATH
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
    assert payload["admission_summary"]["schema_version"] == "import_admission_summary_v1"
    assert payload["admission_summary"]["decision"] == "degraded"
    assert payload["admission_summary"]["trust_level"] == "degraded"
    assert {check["check_id"] for check in payload["admission_summary"]["checks"]} == {
        "residual_cash_comparability",
        "symbol_security_identity_consistency",
        "parsed_position_market_value_comparability",
        "nav_market_value_comparability",
        "instrument_description_registry_consistency",
    }


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
        "benchmark_holdings": "verified",
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
    assert payload["run_metadata"]["return_basis_evidence"] == {
        "portfolio_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "benchmark_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "factor_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
    }
    portfolio_proof = payload["run_metadata"]["portfolio_proof"]
    assert portfolio_proof["admission"]["readiness_status"] == "not_applicable"
    assert {key: value for key, value in portfolio_proof["admission"].items() if key != "readiness_status"} == {
        "status": "not_applicable",
        "scope": {
            "account_id": None,
            "base_currency": None,
            "history_source": "unavailable",
            "valuation_window_start": None,
            "valuation_window_end": None,
            "valuation_date_count": 0,
            "statement_window_start": None,
            "statement_window_end": None,
            "statement_window_count": 0,
        },
        "blocking_reasons": [
            {
                "code": "portfolio_history_unavailable",
                "bucket": "portfolio_admission",
                "provenance_bucket": "portfolio_history",
                "reason_type": "missing",
            }
        ],
        "missing_proof_buckets": [
            "boundary_hardening",
            "capital_boundary_proof",
            "corporate_action_proof",
            "fx_proof",
            "investor_economics_proof",
            "opening_state_admission",
            "return_basis_metadata",
            "valuation_basis_separation",
        ],
        "bucket_decisions": [
            {
                "bucket": bucket,
                "status": "not_applicable",
                "blocks_admission": True,
                "provenance_buckets": [bucket],
                "blocking_reasons": ["portfolio_history_unavailable"],
                "scope": {
                    "account_id": None,
                    "base_currency": None,
                    "history_source": "unavailable",
                    "valuation_window_start": None,
                    "valuation_window_end": None,
                    "valuation_date_count": 0,
                    "statement_window_start": None,
                    "statement_window_end": None,
                    "statement_window_count": 0,
                },
            }
            for bucket in [
                "return_basis_metadata",
                "capital_boundary_proof",
                "valuation_basis_separation",
                "boundary_hardening",
                "opening_state_admission",
                "fx_proof",
                "corporate_action_proof",
                "investor_economics_proof",
            ]
        ],
    }
    proof_without_admission = {key: value for key, value in portfolio_proof.items() if key != "admission"}
    preparation = proof_without_admission.pop("preparation")
    assert proof_without_admission == {
        "proof_system": "portfolio_verified_total_return_v1",
        "portfolio_path": "unavailable",
        "verification_status": "unavailable",
        "output_status": "unavailable",
        "replay_status": "replay_unavailable",
        "opening_state_status": "opening_state_unavailable",
        "verified_total_return_emitted": False,
        "benchmark_proof_independent": True,
        "disqualifiers": ["portfolio_history_unavailable"],
        "hard_disqualifiers": ["portfolio_history_unavailable"],
        "evidence": {
            "opening_state_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "valuation_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "cash_flow_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "fx_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "corporate_action_basis": {"status": "disqualified", "policy": {"scope": "broker_scope_unproven", "cash_dividend_coverage_status": "cash_dividend_coverage_unproven", "cash_dividend_observation_status": "cash_dividend_observation_unproven", "non_dividend_status": "non_dividend_corporate_actions_unproven_and_disqualifying", "scope_start_date": None, "scope_end_date": None, "statement_window_count": 0}, "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "terminal_reconciliation_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "calendar_coverage_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "investor_economics_proof": {"status": "unavailable", "claim_id": "portfolio_investor_economics_proof_v1", "claim": "For a specific portfolio account set, base currency, valuation window, and statement window, the computed portfolio wealth path is proven enough to support investor-economics outputs that require portfolio total-return equivalence.", "decision": "not_applicable", "preparation_status": "not_applicable", "required_inputs": ["capital_boundary_proof", "valuation_basis_proof", "boundary_calendar_terminal_proof", "opening_state_proof", "fx_proof", "corporate_action_proof", "cross_bucket_scope_consistency"], "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": [], "hard_disqualifiers": [], "witnesses": [], "blocking_reasons": ["portfolio_history_unavailable"], "missing_proof_buckets": ["capital_boundary_proof", "valuation_basis_proof", "boundary_calendar_terminal_proof", "opening_state_proof", "fx_proof", "corporate_action_proof", "cross_bucket_scope_consistency"], "scope_mismatches": [], "scope": {"account_id": None, "base_currency": None, "history_source": "unavailable", "valuation_window_start": None, "valuation_window_end": None, "valuation_date_count": 0, "statement_window_start": None, "statement_window_end": None, "statement_window_count": 0}},
        },
    }
    assert preparation["readiness_status"] == "not_applicable"
    assert preparation["all_prerequisite_buckets_supported"] is False
    assert payload["run_metadata"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["run_metadata"]["investor_economics_partial_unlock"] == {
        "mode": "allowlisted_exact_slice_scalars_only",
        "exact_slice_scalar_allowlist": [
            {
                "field": "range_metrics[*].summary.time_weighted_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_only",
                "runtime_enabled": True,
            },
            {
                "field": "range_metrics[*].summary.benchmark_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only",
                "runtime_enabled": True,
            },
            {
                "field": "range_metrics[*].summary.excess_return_pct",
                "unlock_condition": "identical_admitted_exact_slice_pair_only",
                "runtime_enabled": True,
            },
        ],
        "client_derivation_rule": "server_side_scalar_only_no_daily_series_subtraction_equivalence",
        "withheld_families": [
            "benchmark_relative_series",
            "benchmark_relative_path_derived_outputs",
            "drawdown_family",
            "rebucketed_window_summaries",
            "rewindowed_range_summaries",
            "diagnostics_benchmark_relative_outputs",
            "replay_benchmark_relative_outputs",
            "strategy_lab_benchmark_relative_outputs",
        ],
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
        "history_end_date": payload["run_metadata"]["reproducibility"]["history_end_date"],
        "dataset_version": "market_data_service_v1",
    }
    assert payload["run_metadata"]["reproducibility"]["history_end_date"] is not None
    assert payload["run_metadata"]["reproducibility"]["history_end_date"] <= "2026-04-23"
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
        "benchmark_history": "live_market_data_unverified_return_basis",
        "factor_history": "live_market_data_unverified_return_basis",
    }
    assert payload["run_metadata"]["return_basis_evidence"] == {
        "portfolio_history": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "synthetic_snapshot_history",
            "disqualifiers": [
                "synthetic_snapshot_history",
                "missing_total_return_reconstruction",
                "missing_dividend_coverage_proof",
            ],
            "fallbacks_used": ["synthetic_snapshot_history"],
            "source_price_field": "price",
            "scope": {},
        },
        "benchmark_history": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
        "factor_history": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
    }
    portfolio_proof = payload["run_metadata"]["portfolio_proof"]
    assert portfolio_proof["proof_system"] == "portfolio_verified_total_return_v1"
    assert portfolio_proof["portfolio_path"] == "withheld"
    assert portfolio_proof["verification_status"] == "unverified"
    assert portfolio_proof["output_status"] == "withheld"
    assert portfolio_proof["replay_status"] == "replay_usable"
    assert portfolio_proof["opening_state_status"] == "opening_state_unverified"
    assert portfolio_proof["verified_total_return_emitted"] is False
    assert portfolio_proof["benchmark_proof_independent"] is True
    assert portfolio_proof["disqualifiers"] == sorted([
        "calendar_coverage_not_broker_proven",
        "corporate_action_proof_missing",
        "opening_cash_state_missing",
        "opening_timestamp_semantics_missing",
        "portfolio_verified_total_return_withheld",
        "raw_price_used_for_valuation",
        "synthetic_snapshot_history",
        "synthetic_snapshot_opening_holdings_quantities",
        "synthetic_snapshot_opening_state",
    ])
    assert portfolio_proof["hard_disqualifiers"] == sorted([
        "calendar_coverage_not_broker_proven",
        "corporate_action_proof_missing",
        "opening_cash_state_missing",
        "opening_timestamp_semantics_missing",
        "raw_price_used_for_valuation",
        "synthetic_snapshot_history",
        "synthetic_snapshot_opening_holdings_quantities",
        "synthetic_snapshot_opening_state",
    ])
    assert portfolio_proof["admission"]["status"] == "withheld"
    assert portfolio_proof["admission"]["missing_proof_buckets"] == [
        "boundary_calendar_terminal_proof",
        "boundary_hardening",
        "capital_boundary_proof",
        "corporate_action_proof",
        "cross_bucket_scope_consistency",
        "investor_economics_proof",
        "opening_state_admission",
        "opening_state_proof",
        "return_basis_metadata",
        "valuation_basis_proof",
        "valuation_basis_separation",
    ]
    assert portfolio_proof["admission"]["bucket_decisions"][0]["blocking_reasons"] == [
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "synthetic_snapshot_history",
    ]
    assert portfolio_proof["admission"]["bucket_decisions"][6]["blocking_reasons"] == [
        "corporate_action_positive_support_missing_for_portfolio_slice",
        "corporate_action_proof_missing",
        "corporate_action_scope_unproven_for_portfolio_slice",
        "statement_window_scope_unproven_for_portfolio_slice",
    ]
    assert portfolio_proof["admission"]["bucket_decisions"][7]["blocking_reasons"] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "calendar_coverage_not_broker_proven",
        "capital_boundary_positive_support_missing_for_portfolio_slice",
        "corporate_action_positive_support_missing_for_portfolio_slice",
        "corporate_action_proof_missing",
        "corporate_action_scope_unproven_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_anchor_scope_unproven_for_portfolio_slice",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "opening_timestamp_semantics_missing",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "statement_window_scope_unproven_for_portfolio_slice",
        "synthetic_snapshot_history",
        "synthetic_snapshot_opening_holdings_quantities",
        "synthetic_snapshot_opening_state",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    assert portfolio_proof["evidence"]["opening_state_basis"] == {
        "status": "disqualified",
        "positive_evidence": [
            "no_broker_ledger_entries_available",
            "broker_statement_account_id_available",
            "broker_statement_base_currency_available",
        ],
        "negative_evidence": [
            "opening_cash_state_missing_broker_evidence",
            "opening_holdings_state_derived_from_current_snapshot",
            "opening_quantities_state_derived_from_current_snapshot",
            "opening_timestamp_semantics_not_broker_proven",
        ],
        "disqualifiers": [
            "opening_cash_state_missing",
            "opening_timestamp_semantics_missing",
            "synthetic_snapshot_opening_holdings_quantities",
            "synthetic_snapshot_opening_state",
        ],
        "hard_disqualifiers": [
            "opening_cash_state_missing",
            "opening_timestamp_semantics_missing",
            "synthetic_snapshot_opening_holdings_quantities",
            "synthetic_snapshot_opening_state",
        ],
        "witnesses": [
            {
                "label": "opening_account_identity",
                "status": "broker_proven",
                "evidence": ["accepted_source:broker_statement_account_id"],
                "counts": {},
            },
            {
                "label": "opening_base_currency_state",
                "status": "broker_proven",
                "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                "counts": {},
            },
            {
                "label": "opening_cash_state",
                "status": "unknown_inferred",
                "evidence": [
                    "accepted_source_missing:broker_cash_report_starting_cash",
                    "synthetic_snapshot_history_has_no_broker_opening_cash_state",
                ],
                "counts": {},
            },
            {
                "label": "opening_holdings_state",
                "status": "unknown_inferred",
                "evidence": [
                    "accepted_source_missing:broker_trade_window_opening_holdings",
                    "opening_holdings_derived_from_current_snapshot",
                ],
                "counts": {},
            },
            {
                "label": "opening_quantities_state",
                "status": "unknown_inferred",
                "evidence": [
                    "accepted_source_missing:broker_trade_window_opening_quantities",
                    "opening_quantities_derived_from_current_snapshot",
                ],
                "counts": {},
            },
            {
                "label": "opening_timestamp_semantics",
                "status": "replay_boundary_only",
                "evidence": ["accepted_source_missing:broker_statement_period_boundary"],
                "counts": {},
            },
            {
                "label": "opening_state_admission",
                "status": "opening_state_unverified",
                "evidence": [
                    "replay_status:replay_usable",
                    "proof_eligibility_blocked_until_opening_state_verified",
                ],
                "counts": {},
            },
        ],
    }
    assert portfolio_proof["evidence"]["cash_flow_basis"] == {
        "status": "disqualified",
        "positive_evidence": ["no_broker_ledger_entries_available"],
        "negative_evidence": ["synthetic_snapshot_history_has_no_external_flow_replay"],
        "disqualifiers": ["synthetic_snapshot_history"],
        "hard_disqualifiers": ["synthetic_snapshot_history"],
        "witnesses": [
            {
                "label": "cash_flow_classification",
                "status": "not_observed",
                "evidence": ["no_broker_proven_external_capital_flow_entries_observed"],
                "counts": {"external_capital_flow": 0},
            },
            {
                "label": "internal_trading_flow_classification",
                "status": "not_observed",
                "evidence": ["no_internal_trading_cash_flows_observed"],
                "counts": {"internal_trading_flow": 0},
            },
            {
                "label": "broker_explicit_income_expense_classification",
                "status": "not_observed",
                "evidence": ["no_broker_explicit_income_or_expense_cash_flows_observed"],
                "counts": {
                    "broker_explicit_dividend": 0,
                    "broker_explicit_interest": 0,
                    "broker_explicit_fee": 0,
                    "broker_explicit_tax": 0,
                },
            },
            {
                "label": "unknown_cash_flow_classification",
                "status": "none_observed",
                "evidence": ["no_unknown_cash_flow_entries_observed"],
                "counts": {"unknown": 0},
            },
        ],
    }
    assert portfolio_proof["evidence"]["fx_basis"] == {
        "status": "supported",
        "positive_evidence": ["all_observed_statement_currencies_match_base_currency"],
        "negative_evidence": [],
        "disqualifiers": [],
        "hard_disqualifiers": [],
        "witnesses": [
            {
                "label": "fx_base_currency_state",
                "status": "broker_proven",
                "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                "counts": {},
            },
            {
                "label": "fx_currency_observation_scope",
                "status": "observed_currency_scope",
                "evidence": [
                    "observed_statement_currencies:USD",
                    "observed_cash_currencies:USD",
                    "observed_ledger_currencies:none",
                    "observed_position_currencies:USD",
                ],
                "counts": {
                    "statement_currency_count": 1,
                    "cash_currency_count": 1,
                    "ledger_currency_count": 0,
                    "position_currency_count": 1,
                    "observed_currency_count": 1,
                },
            },
            {
                "label": "fx_translation_requirement",
                "status": "identity_case_supported",
                "evidence": ["all_observed_currencies_equal_base:USD"],
                "counts": {"observed_currency_count": 1},
            },
        ],
    }
    assert portfolio_proof["evidence"]["corporate_action_basis"] == {
        "status": "disqualified",
        "policy": {
            "scope": "broker_scope_unproven",
            "cash_dividend_coverage_status": "cash_dividend_coverage_unproven",
            "cash_dividend_observation_status": "cash_dividend_observation_unproven",
            "non_dividend_status": "non_dividend_corporate_actions_unproven_and_disqualifying",
            "scope_start_date": None,
            "scope_end_date": None,
            "statement_window_count": 0,
        },
        "positive_evidence": [],
        "negative_evidence": [
            "cash_dividend_coverage_unproven_without_broker_native_statement_window",
            "cash_dividend_observation_unproven_without_covered_broker_scope",
            "non_dividend_corporate_actions_unproven_and_disqualifying",
        ],
        "disqualifiers": ["corporate_action_proof_missing"],
        "hard_disqualifiers": ["corporate_action_proof_missing"],
        "witnesses": [
            {
                "label": "corporate_action_basis_policy",
                "status": "cash_dividend_scope_only",
                "evidence": [
                    "positive_proof_limited_to:cash_dividend",
                    "coverage_and_absence_semantics_require:broker_native_statement_window",
                    "positive_observation_requires:broker_dividend_section_line_within_statement_window",
                    "non_dividend_corporate_actions_remain_unproven_and_disqualifying",
                ],
                "counts": {"statement_window_count": 0},
            },
            {
                "label": "cash_dividend_coverage_scope",
                "status": "cash_dividend_coverage_unproven",
                "evidence": ["broker_native_statement_window_missing_for_cash_dividend_scope"],
                "counts": {"statement_window_count": 0},
            },
            {
                "label": "cash_dividend_observation_scope",
                "status": "cash_dividend_observation_unproven",
                "evidence": ["cash_dividend_absence_not_provable_without_covered_broker_scope"],
                "counts": {"broker_native_dividend_count": 0},
            },
            {
                "label": "non_dividend_corporate_action_scope",
                "status": "non_dividend_corporate_actions_unproven_and_disqualifying",
                "evidence": [
                    "unproven_action_classes:splits,reverse_splits,spin_offs,mergers,rights,return_of_capital,symbol_changes"
                ],
                "counts": {},
            },
        ],
    }
    assert portfolio_proof["evidence"]["terminal_reconciliation_basis"] == {
        "status": "supported",
        "positive_evidence": ["terminal_replay_state_available"],
        "negative_evidence": ["terminal_statement_totals_not_available_for_comparison"],
        "disqualifiers": [],
        "hard_disqualifiers": [],
        "witnesses": [
            {
                "label": "terminal_reconciliation_basis",
                "status": "terminal_statement_totals_missing",
                "evidence": ["terminal_statement_totals_not_available_for_comparison"],
                "counts": {"compared_field_count": 0},
            }
        ],
    }
    calendar_basis = portfolio_proof["evidence"]["calendar_coverage_basis"]
    assert calendar_basis["status"] == "disqualified"
    assert calendar_basis["positive_evidence"] == ["valuation_window_dates_available", "valuation_dates_are_sorted_and_unique"]
    assert calendar_basis["negative_evidence"] == ["valuation_calendar_is_derived_from_benchmark_history", "broker_statement_period_windows_missing"]
    assert calendar_basis["disqualifiers"] == ["calendar_coverage_not_broker_proven"]
    assert calendar_basis["hard_disqualifiers"] == ["calendar_coverage_not_broker_proven"]
    assert calendar_basis["witnesses"][0] == {
        "label": "first_covered_date_basis",
        "status": "replay_boundary_only",
        "evidence": ["broker_statement_period_first_covered_date_missing", "replay_window_first_date:2026-04-10"],
        "counts": {},
    }
    assert calendar_basis["witnesses"][1] == {
        "label": "last_covered_date_basis",
        "status": "replay_boundary_only",
        "evidence": ["broker_statement_period_last_covered_date_missing", f"replay_window_last_date:{payload['run_metadata']['reproducibility']['history_end_date']}"],
        "counts": {},
    }
    assert calendar_basis["witnesses"][2]["status"] == "replay_derived_window"
    assert calendar_basis["witnesses"][2]["label"].startswith("replay_derived_window:2026-04-10")
    assert calendar_basis["witnesses"][2]["evidence"] == [f"replay_window_dates:2026-04-10->{payload['run_metadata']['reproducibility']['history_end_date']}"]
    assert calendar_basis["witnesses"][2]["counts"]["valuation_date_count"] >= 1
    assert calendar_basis["witnesses"][3] == {
        "label": "calendar_continuity_basis",
        "status": "broker_statement_period_missing",
        "evidence": ["broker_statement_period_windows_missing"],
        "counts": {},
    }
    assert calendar_basis["witnesses"][4]["status"] == "disqualified_window"
    assert calendar_basis["witnesses"][4]["label"].startswith("disqualified_window:2026-04-10")
    assert calendar_basis["witnesses"][4]["evidence"] == [f"replay_window_not_backed_by_broker_statement_window:2026-04-10->{payload['run_metadata']['reproducibility']['history_end_date']}"]
    assert calendar_basis["witnesses"][4]["counts"]["valuation_date_count"] >= 1
    valuation_witnesses = portfolio_proof["evidence"]["valuation_basis"]["witnesses"]
    assert portfolio_proof["evidence"]["valuation_basis"]["status"] == "disqualified"
    assert portfolio_proof["evidence"]["valuation_basis"]["positive_evidence"] == ["valuation_dates_available", "position_price_histories_loaded"]
    assert portfolio_proof["evidence"]["valuation_basis"]["negative_evidence"] == ["vendor_raw_price_used_for_valuation", "valuation_path_is_synthetic_snapshot_history"]
    assert portfolio_proof["evidence"]["valuation_basis"]["disqualifiers"] == ["raw_price_used_for_valuation", "synthetic_snapshot_history"]
    assert portfolio_proof["evidence"]["valuation_basis"]["hard_disqualifiers"] == ["raw_price_used_for_valuation", "synthetic_snapshot_history"]
    assert valuation_witnesses[0] == {
        "label": "valuation_input_policy",
        "status": "explicit_withholding_contract",
        "evidence": [
            "proof_eligible:broker_proven_mark_to_market_inputs",
            "replay_only:raw_vendor_price",
            "replay_only:forward_fill",
            "replay_only:synthetic_snapshot_history",
            "replay_only:snapshot_fallback",
            "replay_only:other_fallback_construction",
            "replay_only:mixed_basis_construction",
            "verified_total_return_withheld_when_any_replay_only_valuation_input_is_observed",
        ],
        "counts": {"proof_eligible_input_types": 1, "replay_only_input_types": 6},
    }
    assert valuation_witnesses[1]["label"] == "valuation_history_construction"
    assert valuation_witnesses[1]["status"] == "synthetic_snapshot_history"
    assert valuation_witnesses[1]["evidence"] == ["valuation_states_constructed_from_synthetic_snapshot_history"]
    assert valuation_witnesses[1]["counts"]["valuation_date_count"] >= 1
    assert valuation_witnesses[2]["label"].startswith("valuation_window_basis:2026-04-10")
    assert valuation_witnesses[2]["status"] == "raw_vendor_price"
    assert valuation_witnesses[2]["counts"]["valuation_date_count"] >= 1
    assert valuation_witnesses[2]["counts"]["valued_symbol_count"] >= 1
    assert valuation_witnesses[2]["counts"]["raw_vendor_price"] >= 1
    assert payload["run_metadata"]["section_trust"] == {
        "benchmark_relative_path": "degraded_unverified_return_basis",
        "factor_model_path": "degraded_unverified_return_basis",
        "risk_contribution_path": "degraded_unverified_return_basis",
    }
    assert portfolio_proof["admission"]["readiness_status"] == "exact_slice_prerequisites_incomplete"
    assert portfolio_proof["preparation"]["readiness_status"] == "exact_slice_prerequisites_incomplete"
    assert portfolio_proof["preparation"]["all_prerequisite_buckets_supported"] is False
    assert portfolio_proof["evidence"]["investor_economics_proof"]["preparation_status"] == "exact_slice_prerequisites_incomplete"
    assert payload["run_metadata"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["provenance"]["note"].endswith(
        "Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice."
    )
    assert payload["run_metadata"]["confidence"] == "low"
    assert payload["statistical_factor_model"]["status"] == "insufficient_history"
    assert payload["model_reliability"]["status"] == "insufficient_history"
    assert payload["risk_contribution_breakdown"]["status"] == "insufficient_history"
    assert payload["drawdown_summary"]["current_drawdown_pct"] is None
    assert payload["drawdown_summary"]["max_drawdown_pct"] is None
    assert payload["volatility_regime"]["snapshot"]["current_drawdown_pct"] is None
    assert payload["volatility_regime"]["snapshot"]["max_drawdown_pct"] is None
    assert payload["relative_risk"]["active_return_pct"] is None
    assert payload["relative_risk"]["information_ratio"] is None
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
    assert payload["run_metadata"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
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
        "benchmark_history": "live_market_data_unverified_return_basis",
    }
    assert payload["run_metadata"]["section_trust"] == {
        "portfolio_path": "imported_replay",
        "benchmark_path": "degraded_unverified_return_basis",
        "monthly_returns_path": "imported_replay",
    }
    assert payload["run_metadata"]["return_basis_contract"] == {
        "portfolio_path": "unavailable",
        "benchmark_path": "price_return_only",
    }
    assert payload["run_metadata"]["return_basis_evidence"] == {
        "portfolio_path": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
        "benchmark_path": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
    }
    portfolio_proof = payload["run_metadata"]["portfolio_proof"]
    assert portfolio_proof["proof_system"] == "portfolio_verified_total_return_v1"
    assert portfolio_proof["portfolio_path"] == "withheld"
    assert portfolio_proof["verification_status"] == "unverified"
    assert portfolio_proof["output_status"] == "withheld"
    assert portfolio_proof["replay_status"] == "replay_usable"
    assert portfolio_proof["opening_state_status"] == "opening_state_unverified"
    assert portfolio_proof["verified_total_return_emitted"] is False
    assert portfolio_proof["benchmark_proof_independent"] is True
    assert portfolio_proof["disqualifiers"] == [
        "opening_cash_state_missing",
        "portfolio_verified_total_return_withheld",
        "raw_price_used_for_valuation",
    ]
    assert portfolio_proof["hard_disqualifiers"] == [
        "opening_cash_state_missing",
        "raw_price_used_for_valuation",
    ]
    assert portfolio_proof["evidence"]["opening_state_basis"] == {
        "status": "disqualified",
        "positive_evidence": [
            "broker_ledger_entries_available",
            "broker_statement_account_id_available",
            "broker_statement_base_currency_available",
            "opening_holdings_covered_by_observed_trade_window",
            "opening_quantities_covered_by_observed_trade_window",
            "opening_timestamp_semantics_backed_by_broker_statement_period",
        ],
        "negative_evidence": ["opening_cash_state_missing_broker_evidence"],
        "disqualifiers": ["opening_cash_state_missing"],
        "hard_disqualifiers": ["opening_cash_state_missing"],
        "witnesses": [
            {
                "label": "opening_account_identity",
                "status": "broker_proven",
                "evidence": ["accepted_source:broker_statement_account_id"],
                "counts": {},
            },
            {
                "label": "opening_base_currency_state",
                "status": "broker_proven",
                "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                "counts": {},
            },
            {
                "label": "opening_cash_state",
                "status": "missing_broker_evidence",
                "evidence": ["accepted_source_missing:broker_cash_report_starting_cash"],
                "counts": {},
            },
            {
                "label": "opening_holdings_state",
                "status": "trade_window_covered",
                "evidence": ["accepted_source:broker_trade_window_opening_holdings"],
                "counts": {"covered_symbol_count": 1},
            },
            {
                "label": "opening_quantities_state",
                "status": "trade_window_covered",
                "evidence": ["accepted_source:broker_trade_window_opening_quantities"],
                "counts": {"covered_symbol_count": 1},
            },
            {
                "label": "opening_timestamp_semantics",
                "status": "broker_statement_period_boundary",
                "evidence": ["accepted_source:broker_statement_period_boundary:2026-04-10"],
                "counts": {"statement_window_count": 1},
            },
            {
                "label": "opening_state_admission",
                "status": "opening_state_unverified",
                "evidence": [
                    "replay_status:replay_usable",
                    "proof_eligibility_blocked_until_opening_state_verified",
                ],
                "counts": {},
            },
        ],
    }
    assert portfolio_proof["evidence"]["cash_flow_basis"] == {
        "status": "supported",
        "positive_evidence": ["broker_ledger_entries_available", "cash_movement_entries_classified_with_broker_native_evidence"],
        "negative_evidence": [],
        "disqualifiers": [],
        "hard_disqualifiers": [],
        "witnesses": [
            {
                "label": "cash_flow_classification",
                "status": "not_observed",
                "evidence": ["no_broker_proven_external_capital_flow_entries_observed"],
                "counts": {"external_capital_flow": 0},
            },
            {
                "label": "internal_trading_flow_classification",
                "status": "broker_proven",
                "evidence": ["broker_trade_ledger_line"],
                "counts": {"internal_trading_flow": 1},
            },
            {
                "label": "broker_explicit_income_expense_classification",
                "status": "not_observed",
                "evidence": ["no_broker_explicit_income_or_expense_cash_flows_observed"],
                "counts": {
                    "broker_explicit_dividend": 0,
                    "broker_explicit_interest": 0,
                    "broker_explicit_fee": 0,
                    "broker_explicit_tax": 0,
                },
            },
            {
                "label": "unknown_cash_flow_classification",
                "status": "none_observed",
                "evidence": ["no_unknown_cash_flow_entries_observed"],
                "counts": {"unknown": 0},
            },
        ],
    }
    assert portfolio_proof["evidence"]["fx_basis"] == {
        "status": "supported",
        "positive_evidence": ["all_observed_statement_currencies_match_base_currency"],
        "negative_evidence": [],
        "disqualifiers": [],
        "hard_disqualifiers": [],
        "witnesses": [
            {
                "label": "fx_base_currency_state",
                "status": "broker_proven",
                "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                "counts": {},
            },
            {
                "label": "fx_currency_observation_scope",
                "status": "observed_currency_scope",
                "evidence": [
                    "observed_statement_currencies:USD",
                    "observed_cash_currencies:USD",
                    "observed_ledger_currencies:USD",
                    "observed_position_currencies:USD",
                ],
                "counts": {
                    "statement_currency_count": 1,
                    "cash_currency_count": 1,
                    "ledger_currency_count": 1,
                    "position_currency_count": 1,
                    "observed_currency_count": 1,
                },
            },
            {
                "label": "fx_translation_requirement",
                "status": "identity_case_supported",
                "evidence": ["all_observed_currencies_equal_base:USD"],
                "counts": {"observed_currency_count": 1},
            },
        ],
    }
    assert portfolio_proof["evidence"]["corporate_action_basis"] == {
        "status": "supported",
        "policy": {
            "scope": "broker_native_statement_window",
            "cash_dividend_coverage_status": "cash_dividend_coverage_proven_by_broker_native_evidence",
            "cash_dividend_observation_status": "no_cash_dividend_observed_within_covered_broker_scope",
            "non_dividend_status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
            "scope_start_date": "2026-04-10",
            "scope_end_date": "2026-04-11",
            "statement_window_count": 1,
        },
        "positive_evidence": [
            "cash_dividend_coverage_proven_by_broker_native_evidence",
            "no_cash_dividend_observed_within_covered_broker_scope",
            "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
        ],
        "negative_evidence": [],
        "disqualifiers": [],
        "hard_disqualifiers": [],
        "witnesses": [
            {
                "label": "corporate_action_basis_policy",
                "status": "cash_dividend_scope_only",
                "evidence": [
                    "positive_proof_limited_to:cash_dividend",
                    "coverage_and_absence_semantics_require:broker_native_statement_window",
                    "positive_observation_requires:broker_dividend_section_line_within_statement_window",
                    "non_dividend_corporate_actions_remain_unproven_and_disqualifying",
                ],
                "counts": {"statement_window_count": 1},
            },
            {
                "label": "cash_dividend_coverage_scope",
                "status": "cash_dividend_coverage_proven_by_broker_native_evidence",
                "evidence": ["broker_native_statement_windows:2026-04-10->2026-04-11"],
                "counts": {"statement_window_count": 1},
            },
            {
                "label": "cash_dividend_observation_scope",
                "status": "no_cash_dividend_observed_within_covered_broker_scope",
                "evidence": ["no_broker_native_dividend_rows_observed_within_statement_window_scope"],
                "counts": {"broker_native_dividend_count": 0},
            },
            {
                "label": "non_dividend_corporate_action_scope",
                "status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                "evidence": [
                    "supported_non_dividend_classes:none_observed_within_broker_native_statement_window",
                    "unresolved_non_dividend_classes_would_remain_blocking:splits,reverse_splits,spin_offs,mergers,rights,return_of_capital,symbol_changes",
                ],
                "counts": {},
            },
        ],
    }
    assert portfolio_proof["evidence"]["terminal_reconciliation_basis"] == {
        "status": "supported",
        "positive_evidence": ["terminal_replay_state_available"],
        "negative_evidence": ["terminal_statement_totals_not_available_for_comparison"],
        "disqualifiers": [],
        "hard_disqualifiers": [],
        "witnesses": [
            {
                "label": "terminal_reconciliation_basis",
                "status": "terminal_statement_totals_missing",
                "evidence": ["terminal_statement_totals_not_available_for_comparison"],
                "counts": {"compared_field_count": 0},
            }
        ],
    }
    calendar_basis = portfolio_proof["evidence"]["calendar_coverage_basis"]
    assert calendar_basis["status"] == "supported"
    assert calendar_basis["positive_evidence"] == [
        "valuation_window_dates_available",
        "valuation_dates_are_sorted_and_unique",
        "broker_statement_period_windows_available",
        "broker_statement_calendar_continuity_observed",
        "replay_window_within_broker_statement_boundaries",
    ]
    assert calendar_basis["negative_evidence"] == ["valuation_calendar_is_derived_from_benchmark_history"]
    assert calendar_basis["disqualifiers"] == []
    assert calendar_basis["hard_disqualifiers"] == []
    assert calendar_basis["witnesses"][0] == {
        "label": "first_covered_date_basis",
        "status": "broker_statement_period_boundary",
        "evidence": ["broker_statement_period_first_covered_date:2026-04-10"],
        "counts": {},
    }
    assert calendar_basis["witnesses"][1] == {
        "label": "last_covered_date_basis",
        "status": "broker_statement_period_boundary",
        "evidence": ["broker_statement_period_last_covered_date:2026-04-11"],
        "counts": {},
    }
    assert calendar_basis["witnesses"][2] == {
        "label": "replay_derived_window:2026-04-10",
        "status": "replay_derived_window",
        "evidence": ["replay_window_dates:2026-04-10->2026-04-10"],
        "counts": {"valuation_date_count": 1},
    }
    assert calendar_basis["witnesses"][3] == {
        "label": "calendar_continuity_basis",
        "status": "broker_statement_period_contiguous",
        "evidence": ["broker_statement_calendar_window:2026-04-10->2026-04-11"],
        "counts": {"statement_window_count": 1, "gap_count": 0},
    }
    assert calendar_basis["witnesses"][4] == {
        "label": "broker_covered_window:2026-04-10",
        "status": "broker_covered_window",
        "evidence": ["broker_statement_period_window:2026-04-10->2026-04-10"],
        "counts": {"valuation_date_count": 1},
    }
    valuation_witnesses = portfolio_proof["evidence"]["valuation_basis"]["witnesses"]
    assert portfolio_proof["evidence"]["valuation_basis"]["status"] == "disqualified"
    assert portfolio_proof["evidence"]["valuation_basis"]["positive_evidence"] == ["valuation_dates_available", "position_price_histories_loaded"]
    assert portfolio_proof["evidence"]["valuation_basis"]["negative_evidence"] == ["vendor_raw_price_used_for_valuation"]
    assert portfolio_proof["evidence"]["valuation_basis"]["disqualifiers"] == ["raw_price_used_for_valuation"]
    assert portfolio_proof["evidence"]["valuation_basis"]["hard_disqualifiers"] == ["raw_price_used_for_valuation"]
    assert valuation_witnesses[0] == {
        "label": "valuation_input_policy",
        "status": "explicit_withholding_contract",
        "evidence": [
            "proof_eligible:broker_proven_mark_to_market_inputs",
            "replay_only:raw_vendor_price",
            "replay_only:forward_fill",
            "replay_only:synthetic_snapshot_history",
            "replay_only:snapshot_fallback",
            "replay_only:other_fallback_construction",
            "replay_only:mixed_basis_construction",
            "verified_total_return_withheld_when_any_replay_only_valuation_input_is_observed",
        ],
        "counts": {"proof_eligible_input_types": 1, "replay_only_input_types": 6},
    }
    assert valuation_witnesses[1]["label"] == "valuation_history_construction"
    assert valuation_witnesses[1]["status"] == "imported_replay"
    assert valuation_witnesses[1]["evidence"] == ["valuation_states_replayed_from_imported_broker_activity"]
    assert valuation_witnesses[1]["counts"]["valuation_date_count"] >= 1
    assert valuation_witnesses[2]["label"].startswith("valuation_window_basis:2026-04-10")
    assert valuation_witnesses[2]["status"] == "raw_vendor_price"
    assert valuation_witnesses[2]["counts"]["valuation_date_count"] >= 1
    assert valuation_witnesses[2]["counts"]["valued_symbol_count"] >= 1
    assert valuation_witnesses[2]["counts"]["raw_vendor_price"] >= 1
    assert payload["run_metadata"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["run_metadata"]["reproducibility"] == {
        "input_imported_at": "2026-04-10T00:00:00+00:00",
        "snapshot_as_of_date": "2026-04-11",
        "history_start_date": "2026-04-10",
        "history_end_date": "2026-04-11",
        "benchmark_symbol": "SPY",
        "dataset_version": "market_data_service_v1",
    }


def test_imported_dashboard_history_engine_route_exposes_verified_total_return_for_direct_allowlisted_fmp_slice(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.5},
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 110.0},
            {"date": "2026-04-11", "price": 115.0},
        ],
    }
    client = TestClient(app)

    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "snapshot.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 100.0}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1150, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 115, "unrealized_pnl": 150}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": 1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_metadata"]["return_basis_contract"]["benchmark_path"] == "verified_total_return"
    assert payload["run_metadata"]["return_basis_evidence"]["benchmark_path"]["verification_status"] == "verified"
    assert payload["run_metadata"]["return_basis_evidence"]["benchmark_path"]["source_price_field"] == "adjClose"
    assert payload["run_metadata"]["return_basis_evidence"]["benchmark_path"]["scope"]["vendor"] == "FMP"
    assert payload["run_metadata"]["return_basis_evidence"]["benchmark_path"]["scope"]["direct_path_only"] is True


def test_imported_dashboard_history_engine_route_admits_exact_slice_when_full_portfolio_proof_bar_is_met(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.0},
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0, "basis": "broker_proven_mark_to_market"},
            {"date": "2026-04-11", "price": 103.0, "basis": "broker_proven_mark_to_market"},
        ]
    }
    client = TestClient(app)

    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "snapshot.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": {"starting_nav": 1000, "ending_nav": 1030, "cash_total": 0, "stock_total": 1030, "dividends_total": None, "withholding_tax_total": None, "interest_total": None, "other_fees_total": None, "deposits_total": None, "time_weighted_return_pct": None, "fx_rates": {"USDUSD": 1.0}},
            "instruments": [],
            "cash_balances": [{"currency": "USD", "starting_cash": 1000, "ending_cash": 0}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1030, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 103, "unrealized_pnl": 30}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": -1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    portfolio_proof = payload["run_metadata"]["portfolio_proof"]
    assert portfolio_proof["portfolio_path"] == "verified"
    assert portfolio_proof["verification_status"] == "verified"
    assert portfolio_proof["output_status"] == "available"
    assert portfolio_proof["verified_total_return_emitted"] is True
    assert portfolio_proof["disqualifiers"] == []
    assert portfolio_proof["hard_disqualifiers"] == []
    assert portfolio_proof["preparation"]["readiness_status"] == "exact_slice_admitted"
    assert portfolio_proof["admission"]["status"] == "admitted"
    assert portfolio_proof["admission"]["readiness_status"] == "exact_slice_admitted"
    assert portfolio_proof["admission"]["blocking_reasons"] == []
    assert portfolio_proof["admission"]["missing_proof_buckets"] == []
    assert payload["performance_series"][-1]["portfolio_return_pct"] == 3.0
    assert payload["performance_series"][-1]["benchmark_return_pct"] is None
    assert payload["range_metrics"]["All"]["summary"]["time_weighted_return_pct"] == 3.0
    assert payload["range_metrics"]["All"]["summary"]["benchmark_return_pct"] == 1.0
    assert payload["range_metrics"]["All"]["summary"]["excess_return_pct"] == 2.0
    assert payload["range_metrics"]["All"]["max_drawdown_pct"] is None
    assert payload["benchmark"]["return_basis_contract"] == "verified_total_return"
    assert payload["benchmark"]["return_pct"] is None
    assert payload["run_metadata"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }


def test_imported_dashboard_history_engine_route_keeps_exact_slice_benchmark_return_withheld_without_independent_benchmark_proof(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.0},
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": False,
        "fallback_used": True,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0, "basis": "broker_proven_mark_to_market"},
            {"date": "2026-04-11", "price": 103.0, "basis": "broker_proven_mark_to_market"},
        ]
    }
    client = TestClient(app)

    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "snapshot.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": {"starting_nav": 1000, "ending_nav": 1030, "cash_total": 0, "stock_total": 1030, "dividends_total": None, "withholding_tax_total": None, "interest_total": None, "other_fees_total": None, "deposits_total": None, "time_weighted_return_pct": None, "fx_rates": {"USDUSD": 1.0}},
            "instruments": [],
            "cash_balances": [{"currency": "USD", "starting_cash": 1000, "ending_cash": 0}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1030, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 103, "unrealized_pnl": 30}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": -1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_metadata"]["portfolio_proof"]["admission"]["readiness_status"] == "exact_slice_admitted"
    assert payload["performance_series"][-1]["benchmark_return_pct"] is None
    assert payload["range_metrics"]["All"]["summary"]["time_weighted_return_pct"] == 3.0
    assert payload["range_metrics"]["All"]["summary"]["benchmark_return_pct"] is None
    assert payload["range_metrics"]["All"]["summary"]["excess_return_pct"] is None
    assert payload["range_metrics"]["All"]["max_drawdown_pct"] is None
    assert payload["benchmark"]["return_pct"] is None
    assert all(metrics["max_drawdown_pct"] is None for metrics in payload["range_metrics"].values())


def test_imported_dashboard_history_engine_route_unlocks_only_exact_slice_excess_return_and_keeps_drawdown_withheld(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": "2026-04-10", "price": 100.0, "adjClose": 100.0},
        {"date": "2026-04-11", "price": 101.0, "adjClose": 101.0},
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": "2026-04-10", "price": 100.0, "basis": "broker_proven_mark_to_market"},
            {"date": "2026-04-11", "price": 103.0, "basis": "broker_proven_mark_to_market"},
        ]
    }
    client = TestClient(app)

    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-04-10T00:00:00Z",
                "source_path": "snapshot.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": "2026-04-10 - 2026-04-11",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": {"starting_nav": 1000, "ending_nav": 1030, "cash_total": 0, "stock_total": 1030, "dividends_total": None, "withholding_tax_total": None, "interest_total": None, "other_fees_total": None, "deposits_total": None, "time_weighted_return_pct": None, "fx_rates": {"USDUSD": 1.0}},
            "instruments": [],
            "cash_balances": [{"currency": "USD", "starting_cash": 1000, "ending_cash": 0}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1030, "currency": "USD", "as_of_date": "2026-04-11", "cost_basis": 1000, "close_price": 103, "unrealized_pnl": 30}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": "2026-04-10", "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": -1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["range_metrics"]["All"]["summary"]["time_weighted_return_pct"] == 3.0
    assert payload["range_metrics"]["All"]["summary"]["benchmark_return_pct"] == 1.0
    assert payload["range_metrics"]["All"]["summary"]["excess_return_pct"] == 2.0
    assert payload["performance_series"][-1]["benchmark_return_pct"] is None
    assert payload["benchmark"]["return_pct"] is None
    assert all(metrics["max_drawdown_pct"] is None for metrics in payload["range_metrics"].values())
    assert payload["run_metadata"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["run_metadata"]["investor_economics_partial_unlock"]["exact_slice_scalar_allowlist"][2] == {
        "field": "range_metrics[*].summary.excess_return_pct",
        "unlock_condition": "identical_admitted_exact_slice_pair_only",
        "runtime_enabled": True,
    }
    assert payload["run_metadata"]["investor_economics_partial_unlock"]["withheld_families"] == [
        "benchmark_relative_series",
        "benchmark_relative_path_derived_outputs",
        "drawdown_family",
        "rebucketed_window_summaries",
        "rewindowed_range_summaries",
        "diagnostics_benchmark_relative_outputs",
        "replay_benchmark_relative_outputs",
        "strategy_lab_benchmark_relative_outputs",
    ]


def test_imported_dashboard_history_engine_route_keeps_non_exact_windows_withheld_after_exact_slice_excess_return_unlock(mocker) -> None:
    market_data = mocker.patch("app.services.dashboard_history_engine.MarketDataService")
    service = market_data.return_value
    dates = [f"2026-01-{index:02d}" for index in range(1, 23)]
    service.get_direct_verified_benchmark_history.return_value = [
        {"date": day_str, "price": 100.0 + index, "adjClose": 100.0 + index}
        for index, day_str in enumerate(dates)
    ]
    service.get_last_fetch_meta.return_value = {
        "type": "history",
        "requested_symbol": "SPY",
        "resolved_symbol": "SPY",
        "cached": True,
        "vendor": "FMP",
        "endpoint": "historical-price-eod/light",
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
    }
    service.get_historical_prices_for_symbols.return_value = {
        "AAPL": [
            {"date": day_str, "price": 100.0 + index, "basis": "broker_proven_mark_to_market"}
            for index, day_str in enumerate(dates)
        ]
    }
    client = TestClient(app)

    response = client.post(
        "/engines/dashboard-history/run-imported",
        json={
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2026-01-01T00:00:00Z",
                "source_path": "snapshot.pdf",
                "detected_format": "pdf",
                "account_id": "U123",
                "base_currency": "USD",
                "statement_period": f"{dates[0]} - {dates[-1]}",
                "page_count": 1,
            },
            "statements": [],
            "statement_totals": {"starting_nav": 1000, "ending_nav": 1210, "cash_total": 0, "stock_total": 1210, "dividends_total": None, "withholding_tax_total": None, "interest_total": None, "other_fees_total": None, "deposits_total": None, "time_weighted_return_pct": None, "fx_rates": {"USDUSD": 1.0}},
            "instruments": [],
            "cash_balances": [{"currency": "USD", "starting_cash": 1000, "ending_cash": 0}],
            "positions": [{"symbol": "AAPL", "quantity": 10, "market_value": 1210, "currency": "USD", "as_of_date": dates[-1], "cost_basis": 1000, "close_price": 121, "unrealized_pnl": 210}],
            "ledger_entries": [{"entry_type": "BUY", "trade_date": dates[0], "symbol": "AAPL", "quantity": 10, "price": 100, "gross_amount": 1000, "net_amount": -1000, "currency": "USD", "source_section": "Trades"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["range_metrics"]["All"]["summary"]["time_weighted_return_pct"] == 21.0
    assert payload["range_metrics"]["All"]["summary"]["benchmark_return_pct"] == 21.0
    assert payload["range_metrics"]["All"]["summary"]["excess_return_pct"] == 0.0
    assert payload["range_metrics"]["YTD"]["summary"]["time_weighted_return_pct"] == 21.0
    assert payload["range_metrics"]["YTD"]["summary"]["benchmark_return_pct"] == 21.0
    assert payload["range_metrics"]["YTD"]["summary"]["excess_return_pct"] == 0.0
    assert payload["range_metrics"]["1M"]["summary"]["time_weighted_return_pct"] is None
    assert payload["range_metrics"]["1M"]["summary"]["benchmark_return_pct"] is None
    assert payload["range_metrics"]["1M"]["summary"]["excess_return_pct"] is None
    assert payload["performance_series"][-1]["benchmark_return_pct"] is None
    assert payload["benchmark"]["return_pct"] is None
    assert all(metrics["max_drawdown_pct"] is None for metrics in payload["range_metrics"].values())


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
    portfolio_proof = payload["run_metadata"]["portfolio_proof"]
    assert portfolio_proof["admission"]["readiness_status"] == "not_applicable"
    assert {key: value for key, value in portfolio_proof["admission"].items() if key != "readiness_status"} == {
        "status": "not_applicable",
        "scope": {
            "account_id": None,
            "base_currency": None,
            "history_source": "unavailable",
            "valuation_window_start": None,
            "valuation_window_end": None,
            "valuation_date_count": 0,
            "statement_window_start": None,
            "statement_window_end": None,
            "statement_window_count": 0,
        },
        "blocking_reasons": [
            {
                "code": "portfolio_history_unavailable",
                "bucket": "portfolio_admission",
                "provenance_bucket": "portfolio_history",
                "reason_type": "missing",
            }
        ],
        "missing_proof_buckets": [
            "boundary_hardening",
            "capital_boundary_proof",
            "corporate_action_proof",
            "fx_proof",
            "investor_economics_proof",
            "opening_state_admission",
            "return_basis_metadata",
            "valuation_basis_separation",
        ],
        "bucket_decisions": [
            {
                "bucket": bucket,
                "status": "not_applicable",
                "blocks_admission": True,
                "provenance_buckets": [bucket],
                "blocking_reasons": ["portfolio_history_unavailable"],
                "scope": {
                    "account_id": None,
                    "base_currency": None,
                    "history_source": "unavailable",
                    "valuation_window_start": None,
                    "valuation_window_end": None,
                    "valuation_date_count": 0,
                    "statement_window_start": None,
                    "statement_window_end": None,
                    "statement_window_count": 0,
                },
            }
            for bucket in [
                "return_basis_metadata",
                "capital_boundary_proof",
                "valuation_basis_separation",
                "boundary_hardening",
                "opening_state_admission",
                "fx_proof",
                "corporate_action_proof",
                "investor_economics_proof",
            ]
        ],
    }
    proof_without_admission = {key: value for key, value in portfolio_proof.items() if key != "admission"}
    preparation = proof_without_admission.pop("preparation")
    assert proof_without_admission == {
        "proof_system": "portfolio_verified_total_return_v1",
        "portfolio_path": "unavailable",
        "verification_status": "unavailable",
        "output_status": "unavailable",
        "replay_status": "replay_unavailable",
        "opening_state_status": "opening_state_unavailable",
        "verified_total_return_emitted": False,
        "benchmark_proof_independent": True,
        "disqualifiers": ["portfolio_history_unavailable"],
        "hard_disqualifiers": ["portfolio_history_unavailable"],
        "evidence": {
            "opening_state_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "valuation_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "cash_flow_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "fx_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "corporate_action_basis": {"status": "disqualified", "policy": {"scope": "broker_scope_unproven", "cash_dividend_coverage_status": "cash_dividend_coverage_unproven", "cash_dividend_observation_status": "cash_dividend_observation_unproven", "non_dividend_status": "non_dividend_corporate_actions_unproven_and_disqualifying", "scope_start_date": None, "scope_end_date": None, "statement_window_count": 0}, "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "terminal_reconciliation_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "calendar_coverage_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "investor_economics_proof": {"status": "unavailable", "claim_id": "portfolio_investor_economics_proof_v1", "claim": "For a specific portfolio account set, base currency, valuation window, and statement window, the computed portfolio wealth path is proven enough to support investor-economics outputs that require portfolio total-return equivalence.", "decision": "not_applicable", "preparation_status": "not_applicable", "required_inputs": ["capital_boundary_proof", "valuation_basis_proof", "boundary_calendar_terminal_proof", "opening_state_proof", "fx_proof", "corporate_action_proof", "cross_bucket_scope_consistency"], "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": [], "hard_disqualifiers": [], "witnesses": [], "blocking_reasons": ["portfolio_history_unavailable"], "missing_proof_buckets": ["capital_boundary_proof", "valuation_basis_proof", "boundary_calendar_terminal_proof", "opening_state_proof", "fx_proof", "corporate_action_proof", "cross_bucket_scope_consistency"], "scope_mismatches": [], "scope": {"account_id": None, "base_currency": None, "history_source": "unavailable", "valuation_window_start": None, "valuation_window_end": None, "valuation_date_count": 0, "statement_window_start": None, "statement_window_end": None, "statement_window_count": 0}},
        },
    }
    assert preparation["readiness_status"] == "not_applicable"
    assert preparation["all_prerequisite_buckets_supported"] is False
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
        "benchmark_history": "live_market_data_unverified_return_basis",
        "factor_history": "live_market_data_unverified_return_basis",
    }
    assert payload["run_metadata"]["return_basis_evidence"] == {
        "portfolio_history": {
            "verification_status": "unverified",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_portfolio_return_basis_proof"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "benchmark_history": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
        "factor_history": {
            "verification_status": "unverified",
            "economic_basis": "price_return_only",
            "construction_method": "raw_close",
            "disqualifiers": ["missing_adjusted_close_series", "missing_total_return_reconstruction"],
            "fallbacks_used": [],
            "source_price_field": "price",
            "scope": {},
        },
    }
    portfolio_proof = payload["run_metadata"]["portfolio_proof"]
    assert portfolio_proof["admission"]["status"] == "withheld"
    assert portfolio_proof["admission"]["missing_proof_buckets"] == [
        "boundary_calendar_terminal_proof",
        "boundary_hardening",
        "investor_economics_proof",
        "opening_state_admission",
        "opening_state_proof",
        "return_basis_metadata",
        "valuation_basis_proof",
        "valuation_basis_separation",
    ]
    assert portfolio_proof["admission"]["readiness_status"] == "exact_slice_prerequisites_incomplete"
    assert portfolio_proof["admission"]["bucket_decisions"][7]["blocking_reasons"] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    proof_without_admission = {key: value for key, value in portfolio_proof.items() if key != "admission"}
    preparation = proof_without_admission.pop("preparation")
    evidence = proof_without_admission.pop("evidence")
    assert proof_without_admission == {
        "proof_system": "portfolio_verified_total_return_v1",
        "portfolio_path": "withheld",
        "verification_status": "unverified",
        "output_status": "withheld",
        "replay_status": "replay_usable",
        "opening_state_status": "opening_state_unverified",
        "verified_total_return_emitted": False,
        "benchmark_proof_independent": True,
        "disqualifiers": [
            "opening_cash_state_missing",
            "portfolio_verified_total_return_withheld",
            "raw_price_used_for_valuation",
        ],
        "hard_disqualifiers": [
            "opening_cash_state_missing",
            "raw_price_used_for_valuation",
        ],
    }
    assert evidence["opening_state_basis"] == {
                "status": "disqualified",
                "positive_evidence": [
                    "broker_ledger_entries_available",
                    "broker_statement_account_id_available",
                    "broker_statement_base_currency_available",
                    "opening_holdings_covered_by_observed_trade_window",
                    "opening_quantities_covered_by_observed_trade_window",
                    "opening_timestamp_semantics_backed_by_broker_statement_period",
                ],
                "negative_evidence": ["opening_cash_state_missing_broker_evidence"],
                "disqualifiers": ["opening_cash_state_missing"],
                "hard_disqualifiers": ["opening_cash_state_missing"],
                "witnesses": [
                    {
                        "label": "opening_account_identity",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_account_id"],
                        "counts": {},
                    },
                    {
                        "label": "opening_base_currency_state",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                        "counts": {},
                    },
                    {
                        "label": "opening_cash_state",
                        "status": "missing_broker_evidence",
                        "evidence": ["accepted_source_missing:broker_cash_report_starting_cash"],
                        "counts": {},
                    },
                    {
                        "label": "opening_holdings_state",
                        "status": "trade_window_covered",
                        "evidence": ["accepted_source:broker_trade_window_opening_holdings"],
                        "counts": {"covered_symbol_count": 1},
                    },
                    {
                        "label": "opening_quantities_state",
                        "status": "trade_window_covered",
                        "evidence": ["accepted_source:broker_trade_window_opening_quantities"],
                        "counts": {"covered_symbol_count": 1},
                    },
                    {
                        "label": "opening_timestamp_semantics",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["accepted_source:broker_statement_period_boundary:2026-04-10"],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "opening_state_admission",
                        "status": "opening_state_unverified",
                        "evidence": [
                            "replay_status:replay_usable",
                            "proof_eligibility_blocked_until_opening_state_verified",
                        ],
                        "counts": {},
                    },
                ],
            }
    assert evidence["valuation_basis"] == {
                "status": "disqualified",
                "positive_evidence": ["valuation_dates_available", "position_price_histories_loaded"],
                "negative_evidence": ["vendor_raw_price_used_for_valuation"],
                "disqualifiers": ["raw_price_used_for_valuation"],
                "hard_disqualifiers": ["raw_price_used_for_valuation"],
                "witnesses": [
                    {
                        "label": "valuation_input_policy",
                        "status": "explicit_withholding_contract",
                        "evidence": [
                            "proof_eligible:broker_proven_mark_to_market_inputs",
                            "replay_only:raw_vendor_price",
                            "replay_only:forward_fill",
                            "replay_only:synthetic_snapshot_history",
                            "replay_only:snapshot_fallback",
                            "replay_only:other_fallback_construction",
                            "replay_only:mixed_basis_construction",
                            "verified_total_return_withheld_when_any_replay_only_valuation_input_is_observed",
                        ],
                        "counts": {"proof_eligible_input_types": 1, "replay_only_input_types": 6},
                    },
                    {
                        "label": "valuation_history_construction",
                        "status": "imported_replay",
                        "evidence": ["valuation_states_replayed_from_imported_broker_activity"],
                        "counts": {"valuation_date_count": 1},
                    },
                    {
                        "label": "valuation_window_basis:2026-04-10",
                        "status": "raw_vendor_price",
                        "evidence": [
                            "valuation_date:2026-04-10",
                            "valuation_window_uses:raw_vendor_price",
                        ],
                        "counts": {"valuation_date_count": 1, "valued_symbol_count": 1, "raw_vendor_price": 1},
                    },
                ],
            }
    assert evidence["cash_flow_basis"] == {
                "status": "supported",
                "positive_evidence": ["broker_ledger_entries_available", "cash_movement_entries_classified_with_broker_native_evidence"],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "cash_flow_classification",
                        "status": "not_observed",
                        "evidence": ["no_broker_proven_external_capital_flow_entries_observed"],
                        "counts": {"external_capital_flow": 0},
                    },
                    {
                        "label": "internal_trading_flow_classification",
                        "status": "broker_proven",
                        "evidence": ["broker_trade_ledger_line"],
                        "counts": {"internal_trading_flow": 1},
                    },
                    {
                        "label": "broker_explicit_income_expense_classification",
                        "status": "not_observed",
                        "evidence": ["no_broker_explicit_income_or_expense_cash_flows_observed"],
                        "counts": {
                            "broker_explicit_dividend": 0,
                            "broker_explicit_interest": 0,
                            "broker_explicit_fee": 0,
                            "broker_explicit_tax": 0,
                        },
                    },
                    {
                        "label": "unknown_cash_flow_classification",
                        "status": "none_observed",
                        "evidence": ["no_unknown_cash_flow_entries_observed"],
                        "counts": {"unknown": 0},
                    },
                ],
            }
    assert evidence["fx_basis"] == {
                "status": "supported",
                "positive_evidence": ["all_observed_statement_currencies_match_base_currency"],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "fx_base_currency_state",
                        "status": "broker_proven",
                        "evidence": ["accepted_source:broker_statement_base_currency:USD"],
                        "counts": {},
                    },
                    {
                        "label": "fx_currency_observation_scope",
                        "status": "observed_currency_scope",
                        "evidence": [
                            "observed_statement_currencies:USD",
                            "observed_cash_currencies:USD",
                            "observed_ledger_currencies:USD",
                            "observed_position_currencies:USD",
                        ],
                        "counts": {
                            "statement_currency_count": 1,
                            "cash_currency_count": 1,
                            "ledger_currency_count": 1,
                            "position_currency_count": 1,
                            "observed_currency_count": 1,
                        },
                    },
                    {
                        "label": "fx_translation_requirement",
                        "status": "identity_case_supported",
                        "evidence": ["all_observed_currencies_equal_base:USD"],
                        "counts": {"observed_currency_count": 1},
                    },
                ],
            }
    assert evidence["corporate_action_basis"] == {
                "status": "supported",
                "policy": {
                    "scope": "broker_native_statement_window",
                    "cash_dividend_coverage_status": "cash_dividend_coverage_proven_by_broker_native_evidence",
                    "cash_dividend_observation_status": "no_cash_dividend_observed_within_covered_broker_scope",
                    "non_dividend_status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                    "scope_start_date": "2026-04-10",
                    "scope_end_date": "2026-04-11",
                    "statement_window_count": 1,
                },
                "positive_evidence": [
                    "cash_dividend_coverage_proven_by_broker_native_evidence",
                    "no_cash_dividend_observed_within_covered_broker_scope",
                    "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                ],
                "negative_evidence": [],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "corporate_action_basis_policy",
                        "status": "cash_dividend_scope_only",
                        "evidence": [
                            "positive_proof_limited_to:cash_dividend",
                            "coverage_and_absence_semantics_require:broker_native_statement_window",
                            "positive_observation_requires:broker_dividend_section_line_within_statement_window",
                            "non_dividend_corporate_actions_remain_unproven_and_disqualifying",
                        ],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "cash_dividend_coverage_scope",
                        "status": "cash_dividend_coverage_proven_by_broker_native_evidence",
                        "evidence": ["broker_native_statement_windows:2026-04-10->2026-04-11"],
                        "counts": {"statement_window_count": 1},
                    },
                    {
                        "label": "cash_dividend_observation_scope",
                        "status": "no_cash_dividend_observed_within_covered_broker_scope",
                        "evidence": ["no_broker_native_dividend_rows_observed_within_statement_window_scope"],
                        "counts": {"broker_native_dividend_count": 0},
                    },
                    {
                        "label": "non_dividend_corporate_action_scope",
                        "status": "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
                        "evidence": [
                            "supported_non_dividend_classes:none_observed_within_broker_native_statement_window",
                            "unresolved_non_dividend_classes_would_remain_blocking:splits,reverse_splits,spin_offs,mergers,rights,return_of_capital,symbol_changes",
                        ],
                        "counts": {},
                    },
                ],
            }
    assert evidence["terminal_reconciliation_basis"] == {
                "status": "supported",
                "positive_evidence": ["terminal_replay_state_available"],
                "negative_evidence": ["terminal_statement_totals_not_available_for_comparison"],
                "disqualifiers": [],
                "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "terminal_reconciliation_basis",
                        "status": "terminal_statement_totals_missing",
                        "evidence": ["terminal_statement_totals_not_available_for_comparison"],
                        "counts": {"compared_field_count": 0},
                    }
                ],
            }
    assert evidence["calendar_coverage_basis"] == {
                "status": "supported",
                "positive_evidence": [
                    "valuation_window_dates_available",
                    "valuation_dates_are_sorted_and_unique",
                    "broker_statement_period_windows_available",
                    "broker_statement_calendar_continuity_observed",
                    "replay_window_within_broker_statement_boundaries",
                ],
                "negative_evidence": ["valuation_calendar_is_derived_from_benchmark_history"],
        "disqualifiers": [],
        "hard_disqualifiers": [],
                "witnesses": [
                    {
                        "label": "first_covered_date_basis",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["broker_statement_period_first_covered_date:2026-04-10"],
                        "counts": {},
                    },
                    {
                        "label": "last_covered_date_basis",
                        "status": "broker_statement_period_boundary",
                        "evidence": ["broker_statement_period_last_covered_date:2026-04-11"],
                        "counts": {},
                    },
                    {
                        "label": "replay_derived_window:2026-04-10",
                        "status": "replay_derived_window",
                        "evidence": ["replay_window_dates:2026-04-10->2026-04-10"],
                        "counts": {"valuation_date_count": 1},
                    },
                    {
                        "label": "calendar_continuity_basis",
                        "status": "broker_statement_period_contiguous",
                        "evidence": ["broker_statement_calendar_window:2026-04-10->2026-04-11"],
                        "counts": {"statement_window_count": 1, "gap_count": 0},
                    },
                    {
                        "label": "broker_covered_window:2026-04-10",
                        "status": "broker_covered_window",
                        "evidence": ["broker_statement_period_window:2026-04-10->2026-04-10"],
                        "counts": {"valuation_date_count": 1},
                    },
                ],
            }
    investor_proof = portfolio_proof["evidence"]["investor_economics_proof"]
    assert investor_proof["status"] == "disqualified"
    assert investor_proof["decision"] == "withheld"
    assert investor_proof["preparation_status"] == "exact_slice_prerequisites_incomplete"
    assert investor_proof["blocking_reasons"] == [
        "boundary_calendar_terminal_positive_support_missing_for_portfolio_slice",
        "opening_cash_state_missing",
        "opening_state_positive_support_missing_for_portfolio_slice",
        "opening_state_unverified_for_portfolio_slice",
        "raw_price_used_for_valuation",
        "return_basis_positive_support_missing_for_portfolio_slice",
        "valuation_basis_positive_support_missing_for_portfolio_slice",
    ]
    assert investor_proof["missing_proof_buckets"] == [
        "boundary_calendar_terminal_proof",
        "opening_state_proof",
        "valuation_basis_proof",
    ]
    assert investor_proof["scope_mismatches"] == []
    assert [witness["label"] for witness in investor_proof["witnesses"]] == [
        "prerequisite:capital_boundary_proof",
        "prerequisite:valuation_basis_proof",
        "prerequisite:boundary_calendar_terminal_proof",
        "prerequisite:opening_state_proof",
        "prerequisite:fx_proof",
        "prerequisite:corporate_action_proof",
        "scope:account_set",
        "scope:base_currency",
        "scope:valuation_window",
        "scope:statement_window",
        "scope:opening_state_anchor",
        "scope:fx_scope",
        "scope:corporate_action_scope",
        "exact_slice_admission_policy",
        "benchmark_scope_transfer_policy",
    ]
    assert payload["run_metadata"]["section_trust"] == {
        "benchmark_relative_path": "degraded_unverified_return_basis",
        "factor_model_path": "degraded_unverified_return_basis",
        "risk_contribution_path": "degraded_unverified_return_basis",
    }
    assert payload["run_metadata"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert preparation["readiness_status"] == "exact_slice_prerequisites_incomplete"
    assert preparation["all_prerequisite_buckets_supported"] is False
    assert payload["provenance"]["note"].endswith(
        "Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice."
    )
    assert payload["run_metadata"]["confidence"] == "low"
    assert payload["statistical_factor_model"]["status"] == "insufficient_history"
    assert payload["model_reliability"]["status"] == "insufficient_history"
    assert payload["risk_contribution_breakdown"]["status"] == "insufficient_history"
    assert payload["drawdown_summary"]["current_drawdown_pct"] is None
    assert payload["drawdown_summary"]["max_drawdown_pct"] is None
    assert payload["volatility_regime"]["snapshot"]["current_drawdown_pct"] is None
    assert payload["volatility_regime"]["snapshot"]["max_drawdown_pct"] is None
    assert payload["relative_risk"]["active_return_pct"] is None
    assert payload["relative_risk"]["information_ratio"] is None
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
    assert payload["run_metadata"]["return_basis_evidence"] == {
        "portfolio_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "benchmark_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
        "factor_history": {
            "verification_status": "unavailable",
            "economic_basis": "unavailable",
            "construction_method": "unknown",
            "disqualifiers": ["missing_history_rows"],
            "fallbacks_used": [],
            "source_price_field": None,
            "scope": {},
        },
    }
    portfolio_proof = payload["run_metadata"]["portfolio_proof"]
    assert portfolio_proof["admission"]["readiness_status"] == "not_applicable"
    assert {key: value for key, value in portfolio_proof["admission"].items() if key != "readiness_status"} == {
        "status": "not_applicable",
        "scope": {
            "account_id": None,
            "base_currency": None,
            "history_source": "unavailable",
            "valuation_window_start": None,
            "valuation_window_end": None,
            "valuation_date_count": 0,
            "statement_window_start": None,
            "statement_window_end": None,
            "statement_window_count": 0,
        },
        "blocking_reasons": [
            {
                "code": "portfolio_history_unavailable",
                "bucket": "portfolio_admission",
                "provenance_bucket": "portfolio_history",
                "reason_type": "missing",
            }
        ],
        "missing_proof_buckets": [
            "boundary_hardening",
            "capital_boundary_proof",
            "corporate_action_proof",
            "fx_proof",
            "investor_economics_proof",
            "opening_state_admission",
            "return_basis_metadata",
            "valuation_basis_separation",
        ],
        "bucket_decisions": [
            {
                "bucket": bucket,
                "status": "not_applicable",
                "blocks_admission": True,
                "provenance_buckets": [bucket],
                "blocking_reasons": ["portfolio_history_unavailable"],
                "scope": {
                    "account_id": None,
                    "base_currency": None,
                    "history_source": "unavailable",
                    "valuation_window_start": None,
                    "valuation_window_end": None,
                    "valuation_date_count": 0,
                    "statement_window_start": None,
                    "statement_window_end": None,
                    "statement_window_count": 0,
                },
            }
            for bucket in [
                "return_basis_metadata",
                "capital_boundary_proof",
                "valuation_basis_separation",
                "boundary_hardening",
                "opening_state_admission",
                "fx_proof",
                "corporate_action_proof",
                "investor_economics_proof",
            ]
        ],
    }
    proof_without_admission = {key: value for key, value in portfolio_proof.items() if key != "admission"}
    preparation = proof_without_admission.pop("preparation")
    assert proof_without_admission == {
        "proof_system": "portfolio_verified_total_return_v1",
        "portfolio_path": "unavailable",
        "verification_status": "unavailable",
        "output_status": "unavailable",
        "replay_status": "replay_unavailable",
        "opening_state_status": "opening_state_unavailable",
        "verified_total_return_emitted": False,
        "benchmark_proof_independent": True,
        "disqualifiers": ["portfolio_history_unavailable"],
        "hard_disqualifiers": ["portfolio_history_unavailable"],
        "evidence": {
            "opening_state_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "valuation_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "cash_flow_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "fx_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "corporate_action_basis": {"status": "disqualified", "policy": {"scope": "broker_scope_unproven", "cash_dividend_coverage_status": "cash_dividend_coverage_unproven", "cash_dividend_observation_status": "cash_dividend_observation_unproven", "non_dividend_status": "non_dividend_corporate_actions_unproven_and_disqualifying", "scope_start_date": None, "scope_end_date": None, "statement_window_count": 0}, "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "terminal_reconciliation_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "calendar_coverage_basis": {"status": "disqualified", "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": ["portfolio_history_unavailable"], "hard_disqualifiers": ["portfolio_history_unavailable"], "witnesses": []},
            "investor_economics_proof": {"status": "unavailable", "claim_id": "portfolio_investor_economics_proof_v1", "claim": "For a specific portfolio account set, base currency, valuation window, and statement window, the computed portfolio wealth path is proven enough to support investor-economics outputs that require portfolio total-return equivalence.", "decision": "not_applicable", "preparation_status": "not_applicable", "required_inputs": ["capital_boundary_proof", "valuation_basis_proof", "boundary_calendar_terminal_proof", "opening_state_proof", "fx_proof", "corporate_action_proof", "cross_bucket_scope_consistency"], "positive_evidence": [], "negative_evidence": ["portfolio_history_unavailable"], "disqualifiers": [], "hard_disqualifiers": [], "witnesses": [], "blocking_reasons": ["portfolio_history_unavailable"], "missing_proof_buckets": ["capital_boundary_proof", "valuation_basis_proof", "boundary_calendar_terminal_proof", "opening_state_proof", "fx_proof", "corporate_action_proof", "cross_bucket_scope_consistency"], "scope_mismatches": [], "scope": {"account_id": None, "base_currency": None, "history_source": "unavailable", "valuation_window_start": None, "valuation_window_end": None, "valuation_date_count": 0, "statement_window_start": None, "statement_window_end": None, "statement_window_count": 0}},
        },
    }
    assert preparation["readiness_status"] == "not_applicable"
    assert preparation["all_prerequisite_buckets_supported"] is False
    assert payload["run_metadata"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
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
