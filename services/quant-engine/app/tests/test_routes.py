import os
from pathlib import Path
from types import SimpleNamespace
from hashlib import sha256
import json
from datetime import UTC, datetime
from typing import cast

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.backtest_engine import MonitorDefinitionAlertEpisode
from app.schemas.optimizer import OptimizerAlphaFundamentalSnapshot
from app.services import replacement_ranking as replacement_ranking_module
from app.services.optimizer_alpha_service import build_alpha_quality_package
from app.services.construction_artifact_service import _canonical_json
from app.tests._statement_fixtures import (
    ESPP_PATH as ESPP_FIXTURE_PATH,
    FREEDOM24_PATH as FREEDOM24_FIXTURE_PATH,
    STATEMENT_2025_PATH as STATEMENT_2025_FIXTURE_PATH,
    STATEMENT_2026_PATH as STATEMENT_2026_FIXTURE_PATH,
)


def _etf_ranking_request_payload() -> dict[str, object]:
    return {
        "universe": ["XLK", "XLF", "XLV"],
        "benchmark_symbol": "SPY",
        "lookback_months": 6,
    }


def _construction_current_portfolio_payload() -> dict[str, object]:
    return {
        "artifact_id": "portfolio_snapshot_1",
        "as_of_timestamp": "2026-04-23T09:30:00",
        "weights": [
            {"symbol": "BBB", "weight": 0.4},
            {"symbol": "CCC", "weight": 0.35},
            {"symbol": "EEE", "weight": 0.25},
        ],
    }


def _construction_policy_payload() -> dict[str, object]:
    return {"policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2}}


def _construction_constraints_payload() -> dict[str, object]:
    return {
        "hard_constraints": {
            "full_investment": True,
            "long_only": True,
            "eligible_ranked_universe_only": True,
            "max_position_weight": 0.6,
        }
    }


def _construction_constraints_payload_with_min_position_weight(min_position_weight: float) -> dict[str, object]:
    payload = _construction_constraints_payload()
    cast(dict[str, object], payload["hard_constraints"])["min_position_weight"] = min_position_weight
    return payload


def _construction_constraints_payload_with_max_trade_intent_count(max_trade_intent_count: int) -> dict[str, object]:
    payload = _construction_constraints_payload()
    cast(dict[str, object], payload["hard_constraints"])["max_trade_intent_count"] = max_trade_intent_count
    return payload


STATEMENT_PATH = str(STATEMENT_2025_FIXTURE_PATH)
STATEMENT_2026_PATH = str(STATEMENT_2026_FIXTURE_PATH)
FREEDOM24_PATH = str(FREEDOM24_FIXTURE_PATH)
ESPP_PATH = str(ESPP_FIXTURE_PATH)


def _mutate_persisted_json(path: str, mutator) -> None:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    mutator(payload)
    Path(path).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")


def _rekey_construction_artifact_payload(tmp_path: Path, artifact_id: str, payload_mutator) -> str:
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload_mutator(payload)
    payload_without_ids = {key: value for key, value in payload.items() if key not in {"artifact_id", "fingerprint"}}
    fingerprint = sha256(_canonical_json(payload_without_ids).encode("utf-8")).hexdigest()
    legacy_artifact_id = f"construction_artifact_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["artifact_id"] = legacy_artifact_id
    artifact_path.unlink()
    legacy_path = tmp_path / f"{legacy_artifact_id}.json"
    legacy_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    return legacy_artifact_id


def _rekey_etf_ranking_artifact_payload(tmp_path: Path, artifact_id: str, payload_mutator) -> str:
    artifact_path = tmp_path / "etf" / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload_mutator(payload)
    payload_without_id = {key: value for key, value in payload.items() if key != "artifact_id"}
    rekeyed_artifact_id = f"etf_ranking_artifact_{sha256(_canonical_json(payload_without_id).encode('utf-8')).hexdigest()[:16]}"
    payload["artifact_id"] = rekeyed_artifact_id
    artifact_path.unlink()
    rekeyed_path = tmp_path / "etf" / f"{rekeyed_artifact_id}.json"
    rekeyed_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )
    return rekeyed_artifact_id


def _rekey_persisted_handoff(reference: dict[str, str], manifest_mutator) -> dict[str, str]:
    manifest_path = Path(reference["manifest_path"])
    artifact_path = Path(reference["artifact_path"])
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    manifest_mutator(manifest_payload)
    new_handoff_id = f"optimizer_handoff_{sha256(json.dumps({'artifact_id': artifact_payload['artifact_id'], 'return_basis_attestation': manifest_payload['return_basis_attestation']}, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode('utf-8')).hexdigest()[:16]}"
    handoff_dir = manifest_path.parent.parent / new_handoff_id
    handoff_dir.mkdir(parents=True, exist_ok=True)
    manifest_payload["handoff_id"] = new_handoff_id
    new_manifest_path = handoff_dir / "manifest.json"
    new_artifact_path = handoff_dir / "artifact.json"
    new_manifest_path.write_text(json.dumps(manifest_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    new_artifact_path.write_text(json.dumps(artifact_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    return {
        **reference,
        "handoff_id": new_handoff_id,
        "manifest_path": str(new_manifest_path),
        "artifact_path": str(new_artifact_path),
    }


CONSTRUCTION_ARTIFACT_FIXTURE_DIR = Path(__file__).with_name("fixtures") / "construction_artifacts"


def _persist_construction_artifact_fixture(tmp_path: Path, fixture_name: str) -> tuple[str, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    payload = json.loads((CONSTRUCTION_ARTIFACT_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    artifact_path = tmp_path / f"{payload['artifact_id']}.json"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    return payload["artifact_id"], payload


def _single_artifact_id(tmp_path: Path) -> str:
    artifact_paths = list(tmp_path.glob("*.json"))
    assert len(artifact_paths) == 1
    return artifact_paths[0].stem


def _construction_artifact_replay_histories() -> dict[str, list[dict]]:
    return {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "QQQ": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 104.0},
            {"date": "2024-02-01", "price": 104.5},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 112.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.3},
            {"date": "2024-06-03", "price": 101.8},
            {"date": "2024-12-31", "price": 104.5},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.0},
            {"date": "2024-02-01", "price": 98.7},
            {"date": "2024-06-03", "price": 99.8},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 103.2},
            {"date": "2024-06-03", "price": 104.0},
            {"date": "2024-12-31", "price": 107.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.1},
            {"date": "2024-12-31", "price": 103.5},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 97.0},
            {"date": "2024-02-01", "price": 97.2},
            {"date": "2024-06-03", "price": 98.5},
            {"date": "2024-12-31", "price": 101.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.4},
            {"date": "2024-06-03", "price": 103.2},
            {"date": "2024-12-31", "price": 105.2},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.4},
            {"date": "2024-02-01", "price": 100.5},
            {"date": "2024-06-03", "price": 100.6},
            {"date": "2024-12-31", "price": 101.2},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.5},
            {"date": "2024-02-01", "price": 99.0},
            {"date": "2024-06-03", "price": 101.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.8},
            {"date": "2024-02-01", "price": 100.9},
            {"date": "2024-06-03", "price": 101.2},
            {"date": "2024-12-31", "price": 102.3},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.8},
            {"date": "2024-12-31", "price": 104.1},
        ],
    }


def _construction_artifact_preview_payload(artifact_id: str) -> dict[str, object]:
    return {
        "construction_artifact_id": artifact_id,
    }


def _construction_artifact_preview_handoff_payload(
    artifact_id: str,
    **effective_replay_params,
) -> dict[str, object]:
    effective_payload: dict[str, object] = {
        "benchmark_symbol": "SPY",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000.0,
        "rebalance_frequency": "monthly",
        "base_currency": "USD",
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "drift_tolerance_pct": None,
        "price_basis": "adjusted_close",
        "execution_price_field": "close",
        "execution_lag_days": 1,
        "symbol_overrides": {},
    }
    effective_payload.update(effective_replay_params)
    payload: dict[str, object] = {
        "handoff_kind": "construction_artifact_preview_handoff_v1",
        "construction_artifact_id": artifact_id,
        "effective_replay_params": effective_payload,
    }
    return payload


def _construction_artifact_validation_payload(artifact_id: str, **overrides) -> dict[str, object]:
    payload: dict[str, object] = {"construction_artifact_id": artifact_id}
    payload.update(overrides)
    return payload


def _review_snapshot_payload(candidate_symbol: str = "IUFS") -> dict[str, object]:
    return {
        "proposal": {
            "source": "draft_replacement_intent",
            "proposal_source": {
                "proposal_source_version": 1,
                "proposal_source_kind": "draft_replacement_intent_review_only",
                "proposal_truth": "review_only_hypothetical_proposal",
                "portfolio_truth": "draft_snapshot_not_applied",
                "review_scope": "proposal_review_context_only",
            },
            "incumbent_symbol": "AAPL",
            "candidate_symbol": candidate_symbol,
            "draft_id": "draft-1",
            "base_node_id": "node-1",
        },
        "derivation": {
            "baseline_basis": "draft_snapshot_positions_normalized",
            "candidate_construction_rule": "same_weight_substitution_v1",
        },
        "replay_provenance": {
            "candidate_input_source": "replacement_intent_preview",
            "construction_rule_id": "same_weight_substitution_v1",
            "upstream_ids": {
                "draft_id": "draft-1",
                "workspace_id": "workspace-1",
                "base_node_id": "node-1",
            },
            "seed_ranking_id": "etf_ranking_engine_v1",
            "seed_methodology_id": "etf_ranking_methodology_v1",
            "constraint_validation": {
                "supplied": False,
                "validation_status": None,
                "constraint_set_id": None,
            },
        },
        "baseline_weights": [{"symbol": "AAPL", "target_weight": 1.0}],
        "candidate_weights": [{"symbol": candidate_symbol, "target_weight": 1.0}],
        "replay": {
            "methodology": "Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions.",
            "methodology_provenance": {
                "provenance_version": 1,
                "source": "portfolio_allocation_backtest_engine",
                "methodology_truth": "review_only_replay_methodology",
                "assumptions_truth": "review_only_replay_assumptions",
                "analytics_truth": "hypothetical_replay_analytics_only",
                "review_scope": "workspace_review_context_only",
            },
            "investor_economics_status": {"status": "available", "reason": None},
            "reference_result": {
                "portfolio_name": "Reference",
                "benchmark_symbol": "SPY",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "observation_count": 3,
                "rebalance_frequency": "monthly",
                "commission_bps": 0,
                "slippage_bps": 0,
                "drift_tolerance_pct": None,
                "assumptions": {
                    "price_basis": "adjusted_close",
                    "execution_price_field": "close",
                    "execution_lag_days": 1,
                    "calendar_policy": "intersection_common_dates",
                    "fractional_shares": True,
                    "long_only": True,
                    "leverage_allowed": False,
                    "tax_treatment": "pre_tax",
                    "investor_base_currency": "USD",
                },
                "status": "ok",
                "investor_economics_status": {"status": "available", "reason": None},
                "instrument_metadata": [],
                "starting_weights": [{"symbol": "AAPL", "target_weight": 1.0}],
                "ending_weights": [{"symbol": "AAPL", "target_weight": 1.0}],
                "metrics": {
                    "total_return_pct": 8,
                    "annualized_return_pct": 8,
                    "annualized_volatility_pct": 10,
                    "downside_volatility_pct": 6,
                    "max_drawdown_pct": -4,
                    "sharpe_ratio": 0.8,
                    "sortino_ratio": 1.0,
                    "benchmark_return_pct": 7,
                    "excess_return_pct": 1,
                    "tracking_error_pct": 3,
                    "information_ratio": 0.3,
                    "beta_vs_benchmark": 1,
                    "correlation_vs_benchmark": 0.9,
                    "total_turnover_pct": 0,
                    "turnover_events_count": 0,
                    "total_cost_paid": 0,
                },
                "equity_curve": [],
                "rebalance_events": [],
                "trades": [],
            },
            "candidate_result": {
                "portfolio_name": "Candidate",
                "benchmark_symbol": "SPY",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "observation_count": 3,
                "rebalance_frequency": "monthly",
                "commission_bps": 0,
                "slippage_bps": 0,
                "drift_tolerance_pct": None,
                "assumptions": {
                    "price_basis": "adjusted_close",
                    "execution_price_field": "close",
                    "execution_lag_days": 1,
                    "calendar_policy": "intersection_common_dates",
                    "fractional_shares": True,
                    "long_only": True,
                    "leverage_allowed": False,
                    "tax_treatment": "pre_tax",
                    "investor_base_currency": "USD",
                },
                "status": "ok",
                "investor_economics_status": {"status": "available", "reason": None},
                "instrument_metadata": [],
                "starting_weights": [{"symbol": candidate_symbol, "target_weight": 1.0}],
                "ending_weights": [{"symbol": candidate_symbol, "target_weight": 1.0}],
                "metrics": {
                    "total_return_pct": 10,
                    "annualized_return_pct": 10,
                    "annualized_volatility_pct": 9,
                    "downside_volatility_pct": 5,
                    "max_drawdown_pct": -3,
                    "sharpe_ratio": 1.1,
                    "sortino_ratio": 1.3,
                    "benchmark_return_pct": 7,
                    "excess_return_pct": 3,
                    "tracking_error_pct": 4,
                    "information_ratio": 0.5,
                    "beta_vs_benchmark": 0.8,
                    "correlation_vs_benchmark": 0.85,
                    "total_turnover_pct": 12,
                    "turnover_events_count": 2,
                    "total_cost_paid": 45,
                },
                "equity_curve": [],
                "rebalance_events": [],
                "trades": [],
            },
            "comparison": {
                "total_return_diff_pct": 2,
                "annualized_return_diff_pct": 2,
                "benchmark_return_diff_pct": 0,
                "annualized_volatility_diff_pct": -1,
                "downside_volatility_diff_pct": -1,
                "max_drawdown_diff_pct": 1,
                "sharpe_diff": 0.3,
                "sortino_diff": 0.3,
                "excess_return_diff_pct": 2,
                "tracking_error_diff_pct": 1,
                "information_ratio_diff": 0.2,
                "beta_diff": -0.2,
                "correlation_diff": -0.05,
                "total_turnover_diff_pct": 12,
                "total_cost_diff": 45,
            },
            "reference_diagnostics": None,
            "candidate_diagnostics": None,
            "diagnostics_comparison": None,
        },
        "warnings": [],
    }


def _review_snapshot_create_request(candidate_symbol: str = "IUFS") -> dict[str, object]:
    return {
        "proposal_id": f"proposal-{candidate_symbol}",
        "workspace_id": "workspace-1",
        "source_draft_id": "draft-1",
        "source_base_node_id": "node-1",
        "proposal_family_id": f"etf_replacement_intent:AAPL:{candidate_symbol}:2026-04-15T00:05:00Z",
        "version_number": 1,
        "review_payload": _review_snapshot_payload(candidate_symbol),
    }


def _review_snapshot_open_handoff_payload(artifact_id: str, **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "handoff_kind": "review_snapshot_open_handoff_v1",
        "artifact_id": artifact_id,
        "artifact_kind": "portfolio_review_snapshot",
        "schema_version": "review_snapshot_artifact_v1",
        "consumer_kind": "saved_hypothetical_replay_proposal",
    }
    payload.update(overrides)
    return payload


def _review_snapshot_family_review_payload(artifact_id: str, **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "handoff": _review_snapshot_open_handoff_payload(artifact_id),
    }
    payload.update(overrides)
    return payload


def _review_snapshot_family_inbox_payload(workspace_id: str = "workspace-1", **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "workspace_id": workspace_id,
    }
    payload.update(overrides)
    return payload


def _review_snapshot_active_thesis_cross_family_queue_payload(artifact_id: str, source_proposal_id: str, **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_proposal_id": source_proposal_id,
        "handoff": _review_snapshot_open_handoff_payload(artifact_id),
    }
    payload.update(overrides)
    return payload


def _review_snapshot_comparison_ref_payload(role: str, artifact_id: str, **overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "role": role,
        "artifact_id": artifact_id,
        "artifact_kind": "portfolio_review_snapshot",
        "schema_version": "review_snapshot_artifact_v1",
        "consumer_kind": "saved_hypothetical_replay_proposal",
    }
    payload.update(overrides)
    return payload


def _optimizer_preview_payload(
    *,
    objective_id: str = "minimize_l2_distance_to_benchmark",
    include_pit_alpha: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_id": f"preview-{objective_id}",
        "universe_id": "optimizer_universe_large_cap_demo_v1",
        "snapshot": {
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2024-04-15T09:30:00Z",
                "source_path": "IB2024.pdf",
                "detected_format": "statement_pdf",
                "account_id": "U1234567",
                "base_currency": "USD",
                "statement_period": "2024-04",
                "page_count": 4,
            },
            "statements": [
                {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                }
            ],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
            "positions": [
                {"as_of_date": "2024-04-15", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                {"as_of_date": "2024-04-15", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
            ],
            "ledger_entries": [],
        },
        "benchmark": {
            "benchmark_id": "benchmark_spy_demo_v1",
            "benchmark_version": "2024-04-15",
            "benchmark_symbol": "SPY",
            "source_name": "test_benchmark_contract",
            "as_of_timestamp": "2024-12-31T09:30:00",
            "trust_status": "trusted",
            "weights": [
                {"symbol": "AAA", "weight": 0.5},
                {"symbol": "BBB", "weight": 0.3},
                {"symbol": "CCC", "weight": 0.2},
            ],
        },
        "universe": [
            {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
            {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
            {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
        ],
        "objective": {"objective_id": objective_id},
        "hard_constraints": {
            "full_investment": True,
            "long_only": True,
            "benchmark_relative": {"max_abs_active_weight": 0.1},
            "position_limits": {"default_max_weight": 0.6},
            "turnover": {"max_turnover": None},
            "risk": {"max_active_risk": None},
            "active_group_exposures": [],
        },
        "penalties": [],
    }
    if include_pit_alpha:
        payload["pit_alpha"] = {"as_of_date": "2024-04-15"}
    return payload


def _optimizer_handoff_replay_histories() -> dict[str, list[dict]]:
    return {
        **_construction_artifact_replay_histories(),
        "CCC": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 104.0},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 109.0},
        ],
    }


def _optimizer_alpha_package():
    return build_alpha_quality_package(
        rebalance_date="2024-04-15",
        universe_symbols=["AAA", "BBB", "CCC"],
        fundamental_snapshots=[
            OptimizerAlphaFundamentalSnapshot(symbol="AAA", statement_date="2023-12-31", period_type="annual", total_revenue=1000.0, cost_of_revenue=400.0, ebit=200.0, total_assets=800.0, operating_cash_flow=180.0, free_cash_flow=120.0, net_income=150.0, total_debt=160.0, cash_and_equivalents=60.0),
            OptimizerAlphaFundamentalSnapshot(symbol="BBB", statement_date="2023-12-31", period_type="annual", total_revenue=950.0, cost_of_revenue=500.0, ebit=150.0, total_assets=900.0, operating_cash_flow=110.0, free_cash_flow=80.0, net_income=120.0, total_debt=260.0, cash_and_equivalents=30.0),
            OptimizerAlphaFundamentalSnapshot(symbol="CCC", statement_date="2023-12-31", period_type="annual", total_revenue=700.0, cost_of_revenue=420.0, ebit=90.0, total_assets=850.0, operating_cash_flow=70.0, free_cash_flow=40.0, net_income=115.0, total_debt=320.0, cash_and_equivalents=20.0),
        ],
    )


def _monitor_evaluation_payload() -> dict[str, object]:
    return {
        "current_portfolio": {
            "statement": {
                "importer": "interactive_brokers",
                "imported_at": "2024-04-15T09:30:00Z",
                "source_path": "IB2024.pdf",
                "detected_format": "statement_pdf",
                "account_id": "U1234567",
                "base_currency": "USD",
                "statement_period": "2024-04",
                "page_count": 4,
            },
            "statements": [],
            "statement_totals": None,
            "instruments": [],
            "cash_balances": [{"currency": "USD", "ending_cash": 650.0}],
            "positions": [
                {"as_of_date": "2024-01-01", "symbol": "AAA", "quantity": 35.0, "cost_basis": 35.0, "close_price": 1.0, "market_value": 35.0, "unrealized_pnl": 0.0, "currency": "USD"}
            ],
            "ledger_entries": [],
        },
        "benchmark_observation": {
            "overlay_id": "benchmark_trend_overlay_v1",
            "status": "risk_reduced",
            "as_of_month_end": "2024-12-31",
            "benchmark_symbol": "SPY",
            "signal_basis": "10_month_sma_month_end",
            "confirmation_count": 2,
            "rule_version": "v1",
            "source_lineage": {
                "source_kind": "benchmark_overlay_signal",
                "source_id": "overlay-signal-2024-12-31",
                "observed_at": "2025-01-02T09:30:00Z",
            },
        },
    }


def _rekey_monitor_definition_artifact_payload(tmp_path: Path, monitor_definition_id: str, payload_mutator) -> str:
    artifact_path = tmp_path / f"{monitor_definition_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload_mutator(payload)
    payload_without_ids = {
        key: value for key, value in payload.items() if key not in {"monitor_definition_id", "fingerprint"}
    }
    fingerprint = sha256(
        json.dumps(payload_without_ids, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    legacy_monitor_definition_id = f"monitor_definition_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["monitor_definition_id"] = legacy_monitor_definition_id
    artifact_path.unlink()
    legacy_path = tmp_path / f"{legacy_monitor_definition_id}.json"
    legacy_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )
    return legacy_monitor_definition_id


def _rekey_monitor_definition_observation_payload(path: Path, payload_mutator) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload_mutator(payload)
    payload_without_id = {key: value for key, value in payload.items() if key != "observation_id"}
    fingerprint = sha256(
        json.dumps(payload_without_id, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    payload["observation_id"] = f"monitor_definition_observation_{fingerprint[:16]}"
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )


def _write_latest_monitor_evaluation_snapshot(
    tmp_path: Path,
    monitor_definition_id: str,
    *,
    evaluated_at: str = "2026-04-20T09:30:00Z",
    outcome_status: str = "threshold_breach",
    cause_code: str | None = None,
    significance_status: str = "action_required",
    hysteresis_transition: str | None = None,
    benchmark_symbol: str = "SPY",
) -> None:
    (tmp_path / f"{monitor_definition_id}.latest_evaluation.json").write_text(
        json.dumps(
            {
                "schema_version": "monitor_definition_latest_evaluation_snapshot_v1",
                "monitor_definition_id": monitor_definition_id,
                "monitor_id": "benchmark_trend_overlay_v1",
                "benchmark_symbol": benchmark_symbol,
                "evaluated_at": evaluated_at,
                "outcome_status": outcome_status,
                "cause_code": cause_code,
                "significance_status": significance_status,
                "hysteresis_transition": hysteresis_transition,
                "source_precedence": "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact",
                "benchmark_observation_lineage": {
                    "source_kind": "benchmark_overlay_signal",
                    "source_id": "overlay-signal-2024-12-31",
                    "observed_at": "2025-01-02T09:30:00Z",
                },
                "portfolio_truth_basis": {
                    "truth_basis": "imported_portfolio_snapshot",
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "statement_period": "2024-04",
                },
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )


def _write_monitor_definition_observation(
    tmp_path: Path,
    monitor_definition_id: str,
    *,
    evaluated_at: str = "2026-04-20T09:30:00Z",
    observation_status: str = "threshold_breach",
    cause_code: str | None = None,
    alert_classification: str = "action_required",
    hysteresis_transition: str | None = None,
    benchmark_symbol: str = "SPY",
) -> None:
    if hysteresis_transition is None:
        hysteresis_transition = "no_op" if alert_classification == "informational" else "open"
    definition_payload = json.loads((tmp_path / f"{monitor_definition_id}.json").read_text(encoding="utf-8"))
    payload = {
        "schema_version": "monitor_definition_observation_artifact_v1",
        "monitor_definition_id": monitor_definition_id,
        "monitor_definition_fingerprint": definition_payload["fingerprint"],
        "monitor_definition_schema_version": "monitor_definition_artifact_v1",
        "monitor_id": "benchmark_trend_overlay_v1",
        "benchmark_symbol": benchmark_symbol,
        "evaluation_mode": "review_only_observation_evaluation",
        "evaluated_at": evaluated_at,
        "observation_status": observation_status,
        "cause_code": cause_code,
        "alert_classification": alert_classification,
        "hysteresis_transition": hysteresis_transition,
        "source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry",
        "reason": None,
        "thresholds": {
            "minimum_confirmation_count": 2,
            "risk_on_min_risky_weight": 0.95,
            "risk_on_max_cash_weight": 0.05,
            "risk_reduced_max_risky_weight": 0.35,
            "risk_reduced_min_cash_weight": 0.65,
        },
        "benchmark_observation": {
            "overlay_id": "benchmark_trend_overlay_v1",
            "status": "risk_on",
            "as_of_month_end": "2024-12-31",
            "benchmark_symbol": benchmark_symbol,
            "signal_basis": "10_month_sma_month_end",
            "confirmation_count": 2,
            "rule_version": "v1",
            "source_lineage": {
                "source_kind": "benchmark_overlay_signal",
                "source_id": "overlay-signal-2024-12-31",
                "observed_at": "2025-01-02T09:30:00Z",
            },
        },
        "portfolio_observation": {
            "total_portfolio_value": 600.0,
            "risky_value": 100.0,
            "cash_value": 500.0,
            "risky_weight": 0.16666667,
            "cash_weight": 0.83333333,
            "position_count": 2,
            "source_lineage": {
                "truth_basis": "imported_portfolio_snapshot",
                "importer": "interactive_brokers",
                "imported_at": "2024-04-15T09:30:00Z",
                "statement_period": "2024-04",
                "source_paths": ["IB2024.pdf"],
            },
        },
        "active_observation": {
            "required_overlay_status": "risk_on",
            "threshold_evaluation_performed": True,
            "required_min_risky_weight": 0.95,
            "required_max_risky_weight": None,
            "required_min_cash_weight": None,
            "required_max_cash_weight": 0.05,
            "actual_risky_weight": 0.16666667,
            "actual_cash_weight": 0.83333333,
            "risky_weight_gap": -0.78333333,
            "cash_weight_gap": -0.78333333,
            "triggered_thresholds": [],
        },
    }
    observation_payload = dict(payload)
    observation_fingerprint = sha256(
        json.dumps(observation_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    observation_payload["observation_id"] = f"monitor_definition_observation_{observation_fingerprint[:16]}"
    (tmp_path / f"{monitor_definition_id}.observation.json").write_text(
        json.dumps(observation_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )


def _write_monitor_definition_history_entry(
    tmp_path: Path,
    monitor_definition_id: str,
    *,
    evaluated_at: str = "2026-04-20T09:30:00Z",
    observation_status: str = "threshold_breach",
    cause_code: str | None = None,
    significance_status: str = "action_required",
    hysteresis_transition: str | None = None,
    benchmark_symbol: str = "SPY",
    reason: str | None = None,
) -> str:
    if hysteresis_transition is None:
        hysteresis_transition = "no_op" if significance_status == "informational" else "open"
    definition_payload = json.loads((tmp_path / f"{monitor_definition_id}.json").read_text(encoding="utf-8"))
    payload = {
        "schema_version": "monitor_definition_evaluation_history_entry_v1",
        "monitor_definition_id": monitor_definition_id,
        "monitor_definition_fingerprint": definition_payload["fingerprint"],
        "monitor_definition_schema_version": "monitor_definition_artifact_v1",
        "monitor_id": "benchmark_trend_overlay_v1",
        "benchmark_symbol": benchmark_symbol,
        "evaluation_mode": "review_only_observation_evaluation",
        "evaluated_at": evaluated_at,
        "observation_status": observation_status,
        "cause_code": cause_code,
        "significance_status": significance_status,
        "hysteresis_transition": hysteresis_transition,
        "source_precedence": "persisted_evaluation_history_entry_only",
        "reason": reason,
        "thresholds": {
            "minimum_confirmation_count": 2,
            "risk_on_min_risky_weight": 0.95,
            "risk_on_max_cash_weight": 0.05,
            "risk_reduced_max_risky_weight": 0.35,
            "risk_reduced_min_cash_weight": 0.65,
        },
        "benchmark_observation": {
            "overlay_id": "benchmark_trend_overlay_v1",
            "status": "risk_on",
            "as_of_month_end": "2024-12-31",
            "benchmark_symbol": benchmark_symbol,
            "signal_basis": "10_month_sma_month_end",
            "confirmation_count": 2,
            "rule_version": "v1",
            "source_lineage": {
                "source_kind": "benchmark_overlay_signal",
                "source_id": "overlay-signal-2024-12-31",
                "observed_at": "2025-01-02T09:30:00Z",
            },
        },
        "portfolio_observation": {
            "total_portfolio_value": 600.0,
            "risky_value": 100.0,
            "cash_value": 500.0,
            "risky_weight": 0.16666667,
            "cash_weight": 0.83333333,
            "position_count": 2,
            "source_lineage": {
                "truth_basis": "imported_portfolio_snapshot",
                "importer": "interactive_brokers",
                "imported_at": "2024-04-15T09:30:00Z",
                "statement_period": "2024-04",
                "source_paths": ["IB2024.pdf"],
            },
        },
        "active_observation": {
            "required_overlay_status": "risk_on",
            "threshold_evaluation_performed": True,
            "required_min_risky_weight": 0.95,
            "required_max_risky_weight": None,
            "required_min_cash_weight": None,
            "required_max_cash_weight": 0.05,
            "actual_risky_weight": 0.16666667,
            "actual_cash_weight": 0.83333333,
            "risky_weight_gap": -0.78333333,
            "cash_weight_gap": -0.78333333,
            "triggered_thresholds": [],
        },
    }
    fingerprint = sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    history_entry_id = f"monitor_definition_history_{fingerprint[:16]}"
    payload["history_entry_id"] = history_entry_id
    history_dir = tmp_path / f"{monitor_definition_id}.history"
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / f"{history_entry_id}.json").write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )
    return history_entry_id


def _monitor_definition_boundary_response(client: TestClient, boundary: str, monitor_definition_id: str):
    if boundary == "get":
        return client.get(f"/backtests/monitor-definitions/{monitor_definition_id}")
    if boundary == "list":
        return client.get("/backtests/monitor-definitions")
    if boundary == "catalog":
        return client.get("/backtests/monitor-definitions/catalog")
    if boundary == "recent":
        return client.get("/backtests/monitor-definitions/recent")
    if boundary == "evaluate":
        return client.post(
            f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
            json=_monitor_evaluation_payload(),
        )
    if boundary == "history":
        return client.get(f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history")
    if boundary == "episode_history":
        return client.get(f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history")
    raise AssertionError(f"unsupported boundary: {boundary}")


def _cross_sectional_research_request_payload() -> dict[str, object]:
    return {
        "methodology_id": "alpha_quality_v1",
        "rebalance_date": "2024-04-15",
        "as_of_date": "2024-04-15",
        "holdout_start_date": "2024-01-01",
        "dataset_version": "alpha_quality_dataset_demo_v1",
        "universe_definition": "us_large_cap_demo_v1",
        "benchmark": {
            "benchmark_symbol": "SPY",
            "benchmark_name": "SPDR S&P 500 ETF Trust",
            "benchmark_kind": "etf_proxy",
        },
        "universe_symbols": ["AAA", "BBB", "CCC"],
        "source_name": "direct_snapshot_input",
        "fundamental_snapshots": [
            {
                "symbol": "AAA",
                "statement_date": "2023-12-31",
                "period_type": "annual",
                "total_revenue": 1000.0,
                "cost_of_revenue": 400.0,
                "ebit": 200.0,
                "total_assets": 800.0,
                "operating_cash_flow": 180.0,
                "free_cash_flow": 120.0,
                "net_income": 150.0,
                "total_debt": 160.0,
                "cash_and_equivalents": 60.0,
            },
            {
                "symbol": "BBB",
                "statement_date": "2023-12-31",
                "period_type": "annual",
                "total_revenue": 950.0,
                "cost_of_revenue": 500.0,
                "ebit": 150.0,
                "total_assets": 900.0,
                "operating_cash_flow": 110.0,
                "free_cash_flow": 80.0,
                "net_income": 120.0,
                "total_debt": 260.0,
                "cash_and_equivalents": 30.0,
            },
            {
                "symbol": "CCC",
                "statement_date": "2023-12-31",
                "period_type": "annual",
                "total_revenue": 700.0,
                "cost_of_revenue": 420.0,
                "ebit": 90.0,
                "total_assets": 850.0,
                "operating_cash_flow": 70.0,
                "free_cash_flow": 40.0,
                "net_income": 115.0,
                "total_debt": 320.0,
                "cash_and_equivalents": 20.0,
            },
        ],
        "top_ranked_count": 2,
    }


class _ReplacementFakeRegistry:
    def __init__(self, instruments):
        self._instruments = instruments

    def get_instrument(self, symbol: str):
        return self._instruments.get(symbol)


class _ReplacementFakeMarketData:
    def __init__(self, histories):
        self._histories = histories

    def get_historical_prices_for_symbols(self, symbols, from_date, to_date):  # noqa: ANN001
        return {symbol: self._histories.get(symbol, []) for symbol in symbols}

    def get_last_fetch_meta(self, symbol: str):
        return {"resolved_symbol": symbol, "cached": True}


def _replacement_history(*, days: int = 260, start_price: float = 100.0, step: float = 1.0, volume: float = 1000.0) -> list[dict]:
    from datetime import date, timedelta

    end = date(2025, 12, 31)
    start = end - timedelta(days=days - 1)
    rows: list[dict] = []
    for index in range(days):
        price = start_price + (index * step)
        rows.append(
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "close": round(price, 6),
                "volume": volume,
                "adjClose": round(price, 6),
            }
        )
    return rows


def _replacement_instrument(symbol: str):
    return {
        "instrument_id": f"instrument-{symbol.lower()}",
        "symbol": symbol,
        "name": symbol,
        "asset_class": "etf",
        "kind": "spot",
        "sector": "Technology",
        "category": "Sector UCITS ETF",
        "exchange": "TEST",
        "currency": "USD",
    }


def _patch_replacement_ranking_dependencies(mocker) -> None:
    from app.schemas.research import Instrument
    from typing import cast

    histories = {
        "BASE": _replacement_history(),
        "ETF1": _replacement_history(step=0.5),
        "ETF2": _replacement_history(step=0.25),
    }
    instruments = {symbol: Instrument.model_validate(cast(dict[str, object], _replacement_instrument(symbol))) for symbol in histories}
    mocker.patch.object(replacement_ranking_module, "InstrumentRegistry", return_value=_ReplacementFakeRegistry(instruments))
    mocker.patch.object(replacement_ranking_module, "MarketDataService", return_value=_ReplacementFakeMarketData(histories))


def test_health_route() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_monitor_definition_routes_create_get_list_and_evaluate(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    create_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": " spy "},
    )

    assert create_response.status_code == 200
    created = create_response.json()
    monitor_definition_id = created["monitor_definition_id"]
    assert created["benchmark_symbol"] == "SPY"
    assert created["monitor_id"] == "benchmark_trend_overlay_v1"

    get_response = client.get(f"/backtests/monitor-definitions/{monitor_definition_id}")
    list_response = client.get("/backtests/monitor-definitions")
    catalog_response = client.get("/backtests/monitor-definitions/catalog")
    recent_response = client.get("/backtests/monitor-definitions/recent")
    evaluate_response = client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=_monitor_evaluation_payload(),
    )
    history_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"
    )

    assert get_response.status_code == 200
    assert get_response.json()["monitor_definition_id"] == monitor_definition_id
    assert list_response.status_code == 200
    assert list_response.json()["items"] == [
        {
            "monitor_definition_id": monitor_definition_id,
            "monitor_id": "benchmark_trend_overlay_v1",
            "benchmark_symbol": "SPY",
            "schema_version": "monitor_definition_artifact_v1",
            "fingerprint": created["fingerprint"],
        }
    ]
    assert catalog_response.status_code == 200
    assert catalog_response.json() == {
        "items": [
            {
                "monitor_definition_id": monitor_definition_id,
                "monitor_id": "benchmark_trend_overlay_v1",
                "benchmark_symbol": "SPY",
                "schema_version": "monitor_definition_artifact_v1",
                "fingerprint": created["fingerprint"],
                "review_scope": "current_portfolio_truth_only",
                "evaluation_mode": "review_only_observation_evaluation",
                "observation_statuses": ["ok", "threshold_breach", "degraded", "unavailable"],
                "thresholds": {
                    "minimum_confirmation_count": 2,
                    "risk_on_min_risky_weight": 0.95,
                    "risk_on_max_cash_weight": 0.05,
                    "risk_reduced_max_risky_weight": 0.35,
                    "risk_reduced_min_cash_weight": 0.65,
                },
                "source_lineage_requirements": {
                    "benchmark_source_kind": "benchmark_overlay_signal",
                    "portfolio_truth_basis": "imported_portfolio_snapshot",
                    "required_portfolio_statement_fields": ["importer", "imported_at", "source_path", "statement_period"],
                    "required_benchmark_observation_fields": [
                        "overlay_id",
                        "benchmark_symbol",
                        "as_of_month_end",
                        "signal_basis",
                        "confirmation_count",
                        "rule_version",
                        "source_lineage.source_id",
                        "source_lineage.observed_at",
                    ],
                },
                "metadata": {
                    "metadata_truth": "authoritative_persisted_artifact_metadata",
                    "row_provenance": "persisted_monitor_definition_artifact",
                    "status": {
                        "lifecycle": {
                            "overlay_family": "benchmark_trend",
                            "review_support_status": "review_supported",
                            "lifecycle_status": "enabled",
                        },
                        "status_source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot",
                        "latest_observation_status": "absent",
                        "latest_observation": None,
                        "latest_evaluation_snapshot_status": "absent",
                        "latest_evaluation_snapshot": None,
                    },
                },
            }
        ],
        "metadata": {
            "contract_version": "monitor_definition_discovery_v1",
            "metadata_truth": "authoritative_persisted_artifact_metadata",
            "row_provenance": "persisted_monitor_definition_artifact",
            "supported_monitor_ids": ["benchmark_trend_overlay_v1"],
            "supported_overlay_families": ["benchmark_trend"],
            "applied_filters": {
                "overlay_family": None,
                "monitor_id": None,
                "review_support_status": None,
                "lifecycle_status": None,
                "latest_observation_status": None,
                "latest_observation_observation_status": None,
                "latest_observation_alert_classification": None,
                "latest_observation_cause_code": None,
                "latest_observation_recency": None,
                "latest_evaluation_snapshot_status": None,
                "latest_evaluation_snapshot_cause_code": None,
                "latest_evaluation_snapshot_recency": None,
            },
        },
    }
    assert recent_response.status_code == 200
    recent_payload = recent_response.json()
    assert recent_payload["metadata"] == {
        "contract_version": "monitor_definition_discovery_v1",
        "metadata_truth": "authoritative_persisted_artifact_metadata",
        "row_provenance": "persisted_monitor_definition_artifact",
        "recent_order_provenance": "persisted_artifact_file_mtime",
        "supported_monitor_ids": ["benchmark_trend_overlay_v1"],
        "supported_overlay_families": ["benchmark_trend"],
        "applied_filters": {
            "overlay_family": None,
            "monitor_id": None,
            "review_support_status": None,
            "lifecycle_status": None,
            "latest_observation_status": None,
            "latest_observation_observation_status": None,
            "latest_observation_alert_classification": None,
            "latest_observation_cause_code": None,
            "latest_observation_recency": None,
            "latest_evaluation_snapshot_status": None,
            "latest_evaluation_snapshot_cause_code": None,
            "latest_evaluation_snapshot_recency": None,
        },
    }
    assert len(recent_payload["items"]) == 1
    assert recent_payload["items"][0]["monitor_definition_id"] == monitor_definition_id
    assert recent_payload["items"][0]["artifact_last_modified_at"]
    assert recent_payload["items"][0]["metadata"] == {
        "metadata_truth": "authoritative_persisted_artifact_metadata",
        "row_provenance": "persisted_monitor_definition_artifact",
        "recent_order_provenance": "persisted_artifact_file_mtime",
        "status": {
            "lifecycle": {
                "overlay_family": "benchmark_trend",
                "review_support_status": "review_supported",
                "lifecycle_status": "enabled",
            },
            "status_source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot",
            "latest_observation_status": "absent",
            "latest_observation": None,
            "latest_evaluation_snapshot_status": "absent",
            "latest_evaluation_snapshot": None,
        },
    }
    assert evaluate_response.status_code == 200
    assert evaluate_response.json()["observation_status"] == "ok"
    assert evaluate_response.json()["cause_code"] is None
    assert evaluate_response.json()["active_observation"]["required_overlay_status"] == "risk_reduced"
    observation_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/observation"
    )
    assert observation_response.status_code == 200
    assert observation_response.json()["monitor_definition_id"] == monitor_definition_id
    assert observation_response.json()["monitor_definition_fingerprint"] == created["fingerprint"]
    assert observation_response.json()["observation_status"] == "ok"
    assert observation_response.json()["cause_code"] is None
    assert observation_response.json()["alert_classification"] == "informational"
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["metadata"]["contract_version"] == "monitor_definition_evaluation_history_v1"
    assert history_payload["metadata"]["monitor_definition_id"] == monitor_definition_id
    assert history_payload["metadata"]["monitor_definition_fingerprint"] == created["fingerprint"]
    assert history_payload["metadata"]["inspection_order"] == "newest_first_evaluated_at"
    assert history_payload["metadata"]["total_entries"] == 1
    assert len(history_payload["items"]) == 1
    history_entry = history_payload["items"][0]
    assert history_entry["monitor_definition_id"] == monitor_definition_id
    assert history_entry["monitor_definition_fingerprint"] == created["fingerprint"]
    assert history_entry["monitor_definition_schema_version"] == "monitor_definition_artifact_v1"
    assert history_entry["observation_status"] == "ok"
    assert history_entry["cause_code"] is None
    inspect_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history/{history_entry['history_entry_id']}"
    )
    assert inspect_response.status_code == 200
    assert inspect_response.json()["item"]["history_entry_id"] == history_entry["history_entry_id"]
    assert inspect_response.json()["metadata"]["retrieved_history_entry_id"] == history_entry["history_entry_id"]
    persisted_snapshot = json.loads((tmp_path / f"{monitor_definition_id}.latest_evaluation.json").read_text(encoding="utf-8"))
    persisted_observation = json.loads((tmp_path / f"{monitor_definition_id}.observation.json").read_text(encoding="utf-8"))
    assert persisted_snapshot["schema_version"] == "monitor_definition_latest_evaluation_snapshot_v1"
    assert persisted_snapshot["monitor_definition_id"] == monitor_definition_id
    assert persisted_snapshot["benchmark_symbol"] == "SPY"
    assert persisted_snapshot["outcome_status"] == "ok"
    assert persisted_snapshot["cause_code"] is None
    assert persisted_snapshot["significance_status"] == "informational"
    assert persisted_snapshot["hysteresis_transition"] == "no_op"
    assert persisted_snapshot["benchmark_observation_lineage"] == {
        "source_kind": "benchmark_overlay_signal",
        "source_id": "overlay-signal-2024-12-31",
        "observed_at": "2025-01-02T09:30:00Z",
    }
    assert persisted_snapshot["portfolio_truth_basis"] == {
        "truth_basis": "imported_portfolio_snapshot",
        "importer": "interactive_brokers",
        "imported_at": "2024-04-15T09:30:00Z",
        "source_path": "IB2024.pdf",
        "statement_period": "2024-04",
    }
    assert persisted_observation["schema_version"] == "monitor_definition_observation_artifact_v1"
    assert persisted_observation["observation_id"].startswith("monitor_definition_observation_")
    assert persisted_observation["monitor_definition_id"] == monitor_definition_id
    assert persisted_observation["monitor_definition_fingerprint"] == created["fingerprint"]
    assert persisted_observation["monitor_definition_schema_version"] == "monitor_definition_artifact_v1"
    assert persisted_observation["observation_status"] == "ok"
    assert persisted_observation["cause_code"] is None
    assert persisted_observation["alert_classification"] == "informational"
    assert persisted_observation["hysteresis_transition"] == "no_op"
    persisted_history_files = list((tmp_path / f"{monitor_definition_id}.history").glob("*.json"))
    assert len(persisted_history_files) == 1


def test_monitor_definition_create_route_is_immutable_for_identical_requests(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": " spy "},
    )
    second_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    list_response = client.get("/backtests/monitor-definitions")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json() == first_response.json()
    assert list_response.json()["items"] == [
        {
            "monitor_definition_id": first_response.json()["monitor_definition_id"],
            "monitor_id": "benchmark_trend_overlay_v1",
            "benchmark_symbol": "SPY",
            "schema_version": "monitor_definition_artifact_v1",
            "fingerprint": first_response.json()["fingerprint"],
        }
    ]
    assert [path.name for path in tmp_path.glob("monitor_definition_*.json")] == [
        f"{first_response.json()['monitor_definition_id']}.json"
    ]


def test_monitor_definition_route_inventory_stays_aligned_with_shipped_contract_family() -> None:
    route_methods = {
        (tuple(sorted(route.methods - {"HEAD", "OPTIONS"})), route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/backtests/monitor-definitions")
    }

    assert route_methods == {
        (("GET",), "/backtests/monitor-definitions"),
        (("POST",), "/backtests/monitor-definitions"),
        (("GET",), "/backtests/monitor-definitions/catalog"),
        (("GET",), "/backtests/monitor-definitions/recent"),
        (("GET",), "/backtests/monitor-definitions/latest-observation-alert-inbox"),
        (("GET",), "/backtests/monitor-definitions/alert-history-queue"),
        (("GET",), "/backtests/monitor-definitions/recovered-alert-review-queue"),
        (("GET",), "/backtests/monitor-definitions/active-alert-episode-inbox"),
        (("GET",), "/backtests/monitor-definitions/{monitor_definition_id}"),
        (("GET",), "/backtests/monitor-definitions/{monitor_definition_id}/observation"),
        (("GET",), "/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"),
        (("GET",), "/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history"),
        (("GET",), "/backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline"),
        (("GET",), "/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history/{history_entry_id}"),
        (("POST",), "/backtests/monitor-definitions/{monitor_definition_id}/evaluations"),
    }


def test_monitor_definition_alert_review_timeline_contract_docs_and_desktop_types_stay_aligned() -> None:
    schema_text = Path(__file__).resolve().parents[1].joinpath("schemas", "backtest_engine.py").read_text(encoding="utf-8")
    repo_root = Path(__file__).resolve().parents[4]
    desktop_types_text = repo_root / "apps" / "desktop" / "src" / "features" / "portfolio" / "types.ts"
    desktop_types = desktop_types_text.read_text(encoding="utf-8")
    contract_docs = (repo_root / "docs" / "contracts" / "backtest-fields.md").read_text(encoding="utf-8")
    current_state = (repo_root / "docs" / "product" / "current-product-state.md").read_text(encoding="utf-8")
    roadmap = (repo_root / "docs" / "product" / "roadmap.md").read_text(encoding="utf-8")
    technical_roadmap = (repo_root / "docs" / "product" / "technical-roadmap.md").read_text(encoding="utf-8")

    for expected in (
        "monitor_definition_alert_review_timeline_v1",
        "monitor_definition_alert_episode_v1",
        "monitor_definition_active_alert_episode_inbox_v1",
        "monitor_definition_alert_episode_history_v1",
        "monitor_definition_alert_episode_record_v1",
        "authoritative_persisted_monitor_definition_alert_episode_records_only",
        "canonical_latest_observation_artifact_and_append_only_evaluation_history_entries",
        "newest_first_evaluated_at_then_observation_event_then_history_entry_id",
        "newest_first_latest_event_at_then_monitor_definition_id_then_episode_id",
        "newest_first_latest_event_at_then_episode_id",
        "before_episode_id_exclusive",
        "latest_observation_event",
        "evaluation_history_event",
        "observation_rooted",
        "history_entry_rooted",
        "latest_alert_episode",
        "alert_episode",
        "lifecycle_status",
        "latest_for_monitor_definition",
        "terminal_history_entry_id",
        "monitor_definition_alert_episode_history_timeline_handoff_v1",
        "monitor_definition_recovered_alert_review_queue_v1",
        "persisted_latest_observation_with_latest_snapshot_and_prior_alert_history_lineage",
        "newest_first_evaluated_at_then_monitor_definition_id_then_observation_id",
        "monitor_definition_alert_review_timeline_open_handoff_v1",
    ):
        assert expected in schema_text
        assert expected in desktop_types

    assert "GET /backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline" in contract_docs
    assert "GET /backtests/monitor-definitions/active-alert-episode-inbox" in contract_docs
    assert "GET /backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history" in contract_docs
    assert "GET /backtests/monitor-definitions/recovered-alert-review-queue" in contract_docs
    assert "benchmark_observation`, `portfolio_observation`, and `active_observation` remain separate persisted blocks" in contract_docs
    assert "definition-scoped alert-review timeline sourced only from the canonical latest observation artifact plus append-only canonical evaluation-history entries" in current_state
    assert "active alert-episode inbox sourced only from authoritative persisted alert-episode records" in current_state
    assert "broaden monitoring beyond the shipped active alert-episode inbox, definition-scoped persisted alert-episode history index, definition-scoped alert-review timeline, and latest persisted alert-episode lifecycle for one persisted `monitor_definition_id`" in roadmap
    assert "GET /backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline" in technical_roadmap
    assert "GET /backtests/monitor-definitions/active-alert-episode-inbox" in technical_roadmap
    assert "latest_alert_episode" in contract_docs
    assert "alert_episode" in contract_docs
    assert "active alert-episode inbox" in contract_docs
    assert "alert-episode history" in contract_docs
    assert "latest persisted alert-episode lifecycle" in roadmap
    assert "persisted alert-episode lifecycle semantics" in technical_roadmap


def test_monitor_definition_evaluation_route_rejects_contradictory_lineage_state(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    create_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    monitor_definition_id = create_response.json()["monitor_definition_id"]
    payload = cast(dict[str, object], _monitor_evaluation_payload())
    benchmark_observation = cast(dict[str, object], payload["benchmark_observation"])
    benchmark_observation["status"] = "unconfirmed"
    benchmark_observation["confirmation_count"] = 2

    response = client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "benchmark observation status unconfirmed contradicts confirmation_count"}


def test_monitor_definition_evaluation_route_rejects_non_canonical_benchmark_symbol(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    create_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    monitor_definition_id = create_response.json()["monitor_definition_id"]
    payload = cast(dict[str, object], _monitor_evaluation_payload())
    benchmark_observation = cast(dict[str, object], payload["benchmark_observation"])
    benchmark_observation["benchmark_symbol"] = " spy "

    response = client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=payload,
    )

    assert response.status_code == 422
    assert "benchmark_symbol must be canonical uppercase without surrounding whitespace" in response.text


def test_monitor_definition_evaluation_route_rolls_back_partial_persistence_on_history_failure(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    first_response = client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=_monitor_evaluation_payload(),
    )
    assert first_response.status_code == 200

    initial_snapshot = json.loads(
        (tmp_path / f"{monitor_definition_id}.latest_evaluation.json").read_text(encoding="utf-8")
    )
    initial_history_files = list((tmp_path / f"{monitor_definition_id}.history").glob("*.json"))
    original_write_once = (
        __import__(
            "app.services.monitor_definition_artifact_service",
            fromlist=["MonitorDefinitionArtifactStore"],
        ).MonitorDefinitionArtifactStore._write_once
    )

    def fail_history_write(self, path, payload):
        if path.parent.name == f"{monitor_definition_id}.history":
            raise __import__(
                "app.services.monitor_definition_artifact_service",
                fromlist=["MonitorDefinitionPersistenceError"],
            ).MonitorDefinitionPersistenceError("injected history append failure")
        return original_write_once(self, path, payload)

    mocker.patch(
        "app.services.monitor_definition_artifact_service.MonitorDefinitionArtifactStore._write_once",
        autospec=True,
        side_effect=fail_history_write,
    )

    failure_payload = cast(dict[str, object], _monitor_evaluation_payload())
    failure_observation = cast(dict[str, object], failure_payload["benchmark_observation"])
    failure_observation["status"] = "unconfirmed"
    failure_observation["confirmation_count"] = 1

    response = client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=failure_payload,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "injected history append failure"}
    assert json.loads(
        (tmp_path / f"{monitor_definition_id}.latest_evaluation.json").read_text(encoding="utf-8")
    ) == initial_snapshot
    assert [path.name for path in (tmp_path / f"{monitor_definition_id}.history").glob("*.json")] == [
        path.name for path in initial_history_files
    ]


def test_monitor_definition_create_route_rejects_legacy_write_widening() -> None:
    client = TestClient(app)

    response = client.post(
        "/backtests/monitor-definitions",
        json={
            "monitor_id": "benchmark_trend_overlay_v1",
            "benchmark_symbol": "SPY",
            "observation_statuses": ["ok", "threshold_breach", "degraded", "unavailable"],
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("boundary", ["get", "list", "catalog", "recent", "evaluate", "history", "episode_history"])
def test_monitor_definition_routes_fail_closed_on_malformed_json(tmp_path, mocker, boundary: str) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    create_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    monitor_definition_id = create_response.json()["monitor_definition_id"]
    (tmp_path / f"{monitor_definition_id}.json").write_text("{", encoding="utf-8")

    response = _monitor_definition_boundary_response(client, boundary, monitor_definition_id)

    assert response.status_code == 400
    assert "invalid persisted monitor definition json" in response.json()["detail"]


@pytest.mark.parametrize("boundary", ["get", "list", "catalog", "recent", "evaluate", "history", "episode_history"])
def test_monitor_definition_routes_fail_closed_on_non_object_payload(tmp_path, mocker, boundary: str) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    create_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    monitor_definition_id = create_response.json()["monitor_definition_id"]
    (tmp_path / f"{monitor_definition_id}.json").write_text("[]", encoding="utf-8")

    response = _monitor_definition_boundary_response(client, boundary, monitor_definition_id)

    assert response.status_code == 400
    assert "persisted monitor definition payload must be a json object" in response.json()["detail"]


@pytest.mark.parametrize(
    ("mutator", "expected_detail"),
    [
        (lambda payload: payload.pop("thresholds"), "missing required field(s): thresholds"),
        (
            lambda payload: payload.__setitem__("fingerprint", "0" * 64),
            "monitor definition fingerprint does not match canonical persisted payload content",
        ),
        (
            lambda payload: payload.__setitem__("monitor_definition_id", "monitor_definition_0000000000000000"),
            "monitor definition_id does not match canonical persisted payload content",
        ),
    ],
)
@pytest.mark.parametrize("boundary", ["get", "list", "catalog", "recent", "evaluate", "history", "episode_history"])
def test_monitor_definition_routes_fail_closed_on_invalid_persisted_states(
    tmp_path,
    mocker,
    boundary: str,
    mutator,
    expected_detail: str,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    create_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    monitor_definition_id = create_response.json()["monitor_definition_id"]
    _mutate_persisted_json(str(tmp_path / f"{monitor_definition_id}.json"), mutator)

    response = _monitor_definition_boundary_response(client, boundary, monitor_definition_id)

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]


@pytest.mark.parametrize("boundary", ["get", "list", "catalog", "recent", "evaluate", "history", "episode_history"])
def test_monitor_definition_routes_hydrate_only_documented_legacy_omissions(tmp_path, mocker, boundary: str) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    create_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    monitor_definition_id = _rekey_monitor_definition_artifact_payload(
        tmp_path,
        create_response.json()["monitor_definition_id"],
        lambda payload: (payload.pop("observation_statuses"), payload.pop("source_lineage_requirements")),
    )

    response = _monitor_definition_boundary_response(client, boundary, monitor_definition_id)

    assert response.status_code == 200
    if boundary == "list":
        item = response.json()["items"][0]
        assert item["monitor_definition_id"] == monitor_definition_id
        assert item["benchmark_symbol"] == "SPY"
        return
    if boundary == "catalog":
        item = response.json()["items"][0]
        assert item["monitor_definition_id"] == monitor_definition_id
        assert item["observation_statuses"] == ["ok", "threshold_breach", "degraded", "unavailable"]
        assert item["source_lineage_requirements"]["benchmark_source_kind"] == "benchmark_overlay_signal"
        return
    if boundary == "recent":
        item = response.json()["items"][0]
        assert item["monitor_definition_id"] == monitor_definition_id
        assert item["observation_statuses"] == ["ok", "threshold_breach", "degraded", "unavailable"]
        assert item["source_lineage_requirements"]["portfolio_truth_basis"] == "imported_portfolio_snapshot"
        assert item["artifact_last_modified_at"]
        return
    if boundary == "history":
        payload = response.json()
        assert payload["metadata"]["monitor_definition_id"] == monitor_definition_id
        assert payload["metadata"]["total_entries"] == 0
        assert payload["items"] == []
        return
    if boundary == "episode_history":
        payload = response.json()
        assert payload["metadata"]["monitor_definition_id"] == monitor_definition_id
        assert payload["metadata"]["total_episodes"] == 0
        assert payload["items"] == []
        return
    payload = response.json()
    if boundary == "get":
        assert payload["observation_statuses"] == ["ok", "threshold_breach", "degraded", "unavailable"]
        assert payload["source_lineage_requirements"] == {
            "benchmark_source_kind": "benchmark_overlay_signal",
            "portfolio_truth_basis": "imported_portfolio_snapshot",
            "required_portfolio_statement_fields": ["importer", "imported_at", "source_path", "statement_period"],
            "required_benchmark_observation_fields": [
                "overlay_id",
                "benchmark_symbol",
                "as_of_month_end",
                "signal_basis",
                "confirmation_count",
                "rule_version",
                "source_lineage.source_id",
                "source_lineage.observed_at",
            ],
        }
    else:
        assert payload["monitor_definition_id"] == monitor_definition_id
        assert payload["observation_status"] == "ok"


@pytest.mark.parametrize(
    ("rekey_payload", "mutator", "expected_detail"),
    [
        (
            True,
            lambda payload: payload.__setitem__("observation_statuses", ["ok", "threshold_breach", "degraded"]),
            "monitor definition observation_statuses must remain canonical",
        ),
        (
            True,
            lambda payload: payload.__setitem__(
                "source_lineage_requirements",
                {"benchmark_source_kind": "benchmark_overlay_signal"},
            ),
            "monitor definition source_lineage_requirements must be fully specified when present",
        ),
    ],
)
@pytest.mark.parametrize("boundary", ["get", "list", "catalog", "recent", "evaluate", "history", "episode_history"])
def test_monitor_definition_routes_reject_ambiguous_legacy_present_values(
    tmp_path,
    mocker,
    boundary: str,
    rekey_payload: bool,
    mutator,
    expected_detail: str,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    create_response = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    monitor_definition_id = create_response.json()["monitor_definition_id"]
    if rekey_payload:
        monitor_definition_id = _rekey_monitor_definition_artifact_payload(tmp_path, monitor_definition_id, mutator)
    else:
        _mutate_persisted_json(str(tmp_path / f"{monitor_definition_id}.json"), mutator)

    response = _monitor_definition_boundary_response(client, boundary, monitor_definition_id)

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]


def test_monitor_definition_recent_route_returns_newest_first_artifacts(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    )
    second = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    )

    first_id = first.json()["monitor_definition_id"]
    second_id = second.json()["monitor_definition_id"]
    first_path = tmp_path / f"{first_id}.json"
    second_path = tmp_path / f"{second_id}.json"
    os.utime(first_path, (1_700_000_000, 1_700_000_000))
    os.utime(second_path, (1_700_000_100, 1_700_000_100))

    response = client.get("/backtests/monitor-definitions/recent?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert [item["monitor_definition_id"] for item in payload["items"]] == [second_id]
    assert payload["items"][0]["benchmark_symbol"] == "QQQ"


def test_monitor_definition_discovery_routes_apply_additive_status_filters(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    second = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        first["monitor_definition_id"],
        evaluated_at="2999-01-01T09:30:00Z",
        outcome_status="threshold_breach",
        cause_code=None,
        significance_status="action_required",
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        second["monitor_definition_id"],
        evaluated_at="2026-01-01T09:30:00Z",
        outcome_status="ok",
        cause_code=None,
        significance_status="informational",
        benchmark_symbol="QQQ",
    )

    catalog_response = client.get(
        "/backtests/monitor-definitions/catalog?overlay_family=benchmark_trend&review_support_status=review_supported&lifecycle_status=enabled&latest_evaluation_snapshot_status=present&latest_evaluation_snapshot_recency=recent"
    )
    recent_response = client.get(
        "/backtests/monitor-definitions/recent?latest_evaluation_snapshot_status=present"
    )

    assert catalog_response.status_code == 200
    assert [item["monitor_definition_id"] for item in catalog_response.json()["items"]] == [first["monitor_definition_id"]]
    assert catalog_response.json()["items"][0]["metadata"]["status"]["latest_evaluation_snapshot"] == {
        "evaluated_at": "2999-01-01T09:30:00Z",
        "outcome_status": "threshold_breach",
        "cause_code": None,
        "significance_status": "action_required",
        "hysteresis_transition": None,
        "recency_status": "recent",
        "source_precedence": "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact",
    }
    assert recent_response.status_code == 200
    assert [item["monitor_definition_id"] for item in recent_response.json()["items"]] == [second["monitor_definition_id"], first["monitor_definition_id"]]


def test_monitor_definition_discovery_routes_apply_additive_latest_observation_filters(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    action_required = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    informational = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    ).json()
    absent = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "DIA"},
    ).json()
    _write_monitor_definition_observation(
        tmp_path,
        action_required["monitor_definition_id"],
        evaluated_at="2999-01-01T09:30:00Z",
        observation_status="threshold_breach",
        cause_code=None,
        alert_classification="action_required",
        benchmark_symbol="SPY",
    )
    _write_monitor_definition_observation(
        tmp_path,
        informational["monitor_definition_id"],
        evaluated_at="2026-01-01T09:30:00Z",
        observation_status="ok",
        cause_code=None,
        alert_classification="informational",
        benchmark_symbol="QQQ",
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        absent["monitor_definition_id"],
        evaluated_at="2999-01-01T09:30:00Z",
        outcome_status="threshold_breach",
        cause_code=None,
        significance_status="action_required",
        benchmark_symbol="DIA",
    )

    catalog_status_response = client.get(
        "/backtests/monitor-definitions/catalog?latest_observation_status=present"
    )
    catalog_observation_status_response = client.get(
        "/backtests/monitor-definitions/catalog?latest_observation_observation_status=threshold_breach"
    )
    catalog_alert_classification_response = client.get(
        "/backtests/monitor-definitions/catalog?latest_observation_alert_classification=action_required"
    )
    catalog_recency_response = client.get(
        "/backtests/monitor-definitions/catalog?latest_observation_recency=recent"
    )
    catalog_combined_response = client.get(
        "/backtests/monitor-definitions/catalog?overlay_family=benchmark_trend&latest_observation_status=present&latest_observation_observation_status=threshold_breach&latest_observation_alert_classification=action_required&latest_observation_recency=recent"
    )
    catalog_absent_response = client.get(
        "/backtests/monitor-definitions/catalog?latest_observation_status=absent"
    )
    recent_status_response = client.get(
        "/backtests/monitor-definitions/recent?latest_observation_status=present"
    )
    recent_stale_response = client.get(
        "/backtests/monitor-definitions/recent?latest_observation_recency=stale"
    )
    catalog_cause_code_response = client.get(
        "/backtests/monitor-definitions/catalog?latest_observation_cause_code=benchmark_observation_unconfirmed"
    )

    assert catalog_status_response.status_code == 200
    assert [item["monitor_definition_id"] for item in catalog_status_response.json()["items"]] == [
        informational["monitor_definition_id"],
        action_required["monitor_definition_id"],
    ]
    assert catalog_status_response.json()["metadata"]["applied_filters"] == {
        "overlay_family": None,
        "monitor_id": None,
        "review_support_status": None,
        "lifecycle_status": None,
        "latest_observation_status": "present",
        "latest_observation_observation_status": None,
        "latest_observation_alert_classification": None,
        "latest_observation_cause_code": None,
        "latest_observation_recency": None,
        "latest_evaluation_snapshot_status": None,
        "latest_evaluation_snapshot_cause_code": None,
        "latest_evaluation_snapshot_recency": None,
    }
    assert catalog_observation_status_response.status_code == 200
    assert [item["monitor_definition_id"] for item in catalog_observation_status_response.json()["items"]] == [
        action_required["monitor_definition_id"]
    ]
    assert catalog_alert_classification_response.status_code == 200
    assert [item["monitor_definition_id"] for item in catalog_alert_classification_response.json()["items"]] == [
        action_required["monitor_definition_id"]
    ]
    assert catalog_cause_code_response.status_code == 200
    assert catalog_cause_code_response.json()["items"] == []
    assert catalog_recency_response.status_code == 200
    assert [item["monitor_definition_id"] for item in catalog_recency_response.json()["items"]] == [
        action_required["monitor_definition_id"]
    ]
    assert catalog_combined_response.status_code == 200
    assert [item["monitor_definition_id"] for item in catalog_combined_response.json()["items"]] == [
        action_required["monitor_definition_id"]
    ]
    assert catalog_absent_response.status_code == 200
    assert [item["monitor_definition_id"] for item in catalog_absent_response.json()["items"]] == [
        absent["monitor_definition_id"]
    ]
    assert recent_status_response.status_code == 200
    assert [item["monitor_definition_id"] for item in recent_status_response.json()["items"]] == [
        informational["monitor_definition_id"],
        action_required["monitor_definition_id"],
    ]
    assert recent_stale_response.status_code == 200
    assert [item["monitor_definition_id"] for item in recent_stale_response.json()["items"]] == [
        informational["monitor_definition_id"]
    ]


def test_monitor_definition_discovery_routes_filter_by_cause_code_fields(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    degraded = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    unavailable = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    ).json()
    _write_monitor_definition_observation(
        tmp_path,
        degraded["monitor_definition_id"],
        observation_status="degraded",
        cause_code="benchmark_observation_unconfirmed",
        alert_classification="degraded",
        benchmark_symbol="SPY",
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        degraded["monitor_definition_id"],
        outcome_status="degraded",
        cause_code="benchmark_observation_unconfirmed",
        significance_status="degraded",
        benchmark_symbol="SPY",
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        unavailable["monitor_definition_id"],
        outcome_status="unavailable",
        cause_code="benchmark_observation_unavailable",
        significance_status="unavailable",
        benchmark_symbol="QQQ",
    )

    catalog_response = client.get(
        "/backtests/monitor-definitions/catalog?latest_observation_cause_code=benchmark_observation_unconfirmed"
    )
    recent_response = client.get(
        "/backtests/monitor-definitions/recent?latest_evaluation_snapshot_cause_code=benchmark_observation_unavailable"
    )

    assert catalog_response.status_code == 200
    assert [item["monitor_definition_id"] for item in catalog_response.json()["items"]] == [
        degraded["monitor_definition_id"]
    ]
    assert catalog_response.json()["items"][0]["metadata"]["status"]["latest_observation"]["cause_code"] == (
        "benchmark_observation_unconfirmed"
    )
    assert recent_response.status_code == 200
    assert [item["monitor_definition_id"] for item in recent_response.json()["items"]] == [
        unavailable["monitor_definition_id"]
    ]
    assert recent_response.json()["items"][0]["metadata"]["status"]["latest_evaluation_snapshot"]["cause_code"] == (
        "benchmark_observation_unavailable"
    )


def test_monitor_definition_discovery_openapi_query_parameter_inventory_stays_aligned(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )

    paths = app.openapi()["paths"]
    catalog_params = [param["name"] for param in paths["/backtests/monitor-definitions/catalog"]["get"]["parameters"]]
    recent_params = [param["name"] for param in paths["/backtests/monitor-definitions/recent"]["get"]["parameters"]]

    assert catalog_params == [
        "overlay_family",
        "monitor_id",
        "review_support_status",
        "lifecycle_status",
        "latest_observation_status",
        "latest_observation_observation_status",
        "latest_observation_alert_classification",
        "latest_observation_cause_code",
        "latest_observation_recency",
        "latest_evaluation_snapshot_status",
        "latest_evaluation_snapshot_cause_code",
        "latest_evaluation_snapshot_recency",
    ]
    assert recent_params == ["limit", *catalog_params]


def test_monitor_definition_discovery_routes_fail_closed_on_malformed_latest_evaluation_snapshot_metadata(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        created["monitor_definition_id"],
        outcome_status="bad_status",
    )

    response = client.get("/backtests/monitor-definitions/catalog")

    assert response.status_code == 400
    assert "persisted latest evaluation snapshot outcome_status is invalid" in response.json()["detail"]


@pytest.mark.parametrize("evaluated_at", ["2026-04-20T09:30:00", "not-a-timestamp"])
def test_monitor_definition_discovery_routes_fail_closed_on_invalid_present_evaluated_at(
    tmp_path,
    mocker,
    evaluated_at: str,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        created["monitor_definition_id"],
        evaluated_at=evaluated_at,
    )

    response = client.get("/backtests/monitor-definitions/catalog")

    assert response.status_code == 400
    assert "persisted latest evaluation snapshot evaluated_at is invalid" in response.json()["detail"]


def test_monitor_definition_discovery_routes_fail_closed_on_snapshot_definition_mismatch(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(tmp_path, created["monitor_definition_id"])
    _mutate_persisted_json(
        str(tmp_path / f"{created['monitor_definition_id']}.latest_evaluation.json"),
        lambda payload: payload.__setitem__("benchmark_symbol", "QQQ"),
    )

    response = client.get("/backtests/monitor-definitions/catalog")

    assert response.status_code == 400
    assert "persisted latest evaluation snapshot benchmark_symbol does not match persisted monitor definition" in response.json()["detail"]


def test_monitor_definition_discovery_routes_use_persisted_evaluated_at_for_recency_not_sidecar_mtime(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        created["monitor_definition_id"],
        evaluated_at="2026-01-01T09:30:00Z",
    )
    os.utime(
        tmp_path / f"{created['monitor_definition_id']}.latest_evaluation.json",
        (4_102_444_800, 4_102_444_800),
    )

    response = client.get("/backtests/monitor-definitions/catalog?latest_evaluation_snapshot_status=present")

    assert response.status_code == 200
    assert response.json()["items"][0]["metadata"]["status"]["latest_evaluation_snapshot"]["recency_status"] == "stale"


def test_monitor_definition_discovery_routes_read_latest_status_from_snapshot_sidecar_only(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    evaluate_response = client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=_monitor_evaluation_payload(),
    )
    assert evaluate_response.status_code == 200
    (tmp_path / f"{monitor_definition_id}.latest_evaluation.json").unlink()

    catalog_response = client.get("/backtests/monitor-definitions/catalog")
    recent_response = client.get("/backtests/monitor-definitions/recent")
    history_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"
    )
    latest_observation = catalog_response.json()["items"][0]["metadata"]["status"]["latest_observation"]

    assert catalog_response.status_code == 200
    assert recent_response.status_code == 200
    assert history_response.status_code == 200
    assert catalog_response.json()["items"][0]["metadata"]["status"] == {
        "lifecycle": {
            "overlay_family": "benchmark_trend",
            "review_support_status": "review_supported",
            "lifecycle_status": "enabled",
        },
        "status_source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot",
        "latest_observation_status": "present",
        "latest_observation": {
            "observation_id": latest_observation["observation_id"],
            "evaluated_at": latest_observation["evaluated_at"],
            "observation_status": "ok",
            "cause_code": None,
            "alert_classification": "informational",
            "hysteresis_transition": "no_op",
            "recency_status": latest_observation["recency_status"],
            "source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry",
        },
        "latest_evaluation_snapshot_status": "absent",
        "latest_evaluation_snapshot": None,
    }
    assert recent_response.json()["items"][0]["metadata"]["status"]["latest_evaluation_snapshot_status"] == "absent"
    assert recent_response.json()["items"][0]["metadata"]["status"]["latest_evaluation_snapshot"] is None
    assert recent_response.json()["items"][0]["metadata"]["status"]["latest_observation_status"] == "present"
    assert recent_response.json()["items"][0]["metadata"]["status"]["latest_observation"] is not None
    assert history_response.json()["metadata"]["total_entries"] == 1
    assert len(history_response.json()["items"]) == 1


def test_monitor_definition_alert_history_queue_route_returns_newest_alert_eligible_history_rows_only(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    def _queue_payload(
        benchmark_symbol: str,
        status: str,
        *,
        confirmation_count: int,
    ) -> dict[str, object]:
        payload = cast(dict[str, object], _monitor_evaluation_payload())
        benchmark_observation = cast(dict[str, object], payload["benchmark_observation"])
        benchmark_observation["benchmark_symbol"] = benchmark_symbol
        benchmark_observation["status"] = status
        benchmark_observation["confirmation_count"] = confirmation_count
        return payload

    action_required = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    degraded = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    ).json()
    informational = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "DIA"},
    ).json()

    assert client.post(
        f"/backtests/monitor-definitions/{action_required['monitor_definition_id']}/evaluations",
        json=_queue_payload("SPY", "risk_on", confirmation_count=2),
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{degraded['monitor_definition_id']}/evaluations",
        json=_queue_payload("QQQ", "unconfirmed", confirmation_count=1),
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{informational['monitor_definition_id']}/evaluations",
        json=_queue_payload("DIA", "risk_reduced", confirmation_count=2),
    ).status_code == 200

    response = client.get("/backtests/monitor-definitions/alert-history-queue?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"] == {
        "contract_version": "monitor_definition_alert_history_queue_v1",
        "provenance": "persisted_monitor_definitions_with_canonical_latest_snapshot_and_evaluation_history",
        "row_provenance": "persisted_monitor_definition_evaluation_history_entry_with_latest_snapshot_precedence",
        "source_precedence": "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries",
        "ordering": "newest_first_evaluated_at_then_latest_snapshot_precedence_then_monitor_definition_id_then_history_entry_id",
        "returned_limit": 10,
        "total_queue_rows": 2,
    }
    assert [item["monitor_definition_id"] for item in payload["items"]] == [
        degraded["monitor_definition_id"],
        action_required["monitor_definition_id"],
    ]
    assert payload["items"][0]["outcome_status"] == "degraded"
    assert payload["items"][0]["cause_code"] == "benchmark_observation_unconfirmed"
    assert payload["items"][0]["significance_status"] == "degraded"
    assert payload["items"][0]["latest_for_monitor_definition"] is True
    assert payload["items"][0]["review_handoff"]["history_entry_id"] == payload["items"][0]["history_entry_id"]
    assert payload["items"][1]["outcome_status"] == "threshold_breach"
    assert payload["items"][1]["cause_code"] is None
    assert payload["items"][1]["significance_status"] == "action_required"


def test_monitor_definition_alert_history_queue_route_fails_closed_on_persisted_evaluation_alignment_mismatch(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    evaluate_response = client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    )
    assert evaluate_response.status_code == 200
    _mutate_persisted_json(
        str(tmp_path / f"{monitor_definition_id}.latest_evaluation.json"),
        lambda payload: payload.__setitem__("evaluated_at", "2026-04-20T09:30:00Z"),
    )
    _rekey_monitor_definition_observation_payload(
        tmp_path / f"{monitor_definition_id}.observation.json",
        lambda payload: payload.__setitem__("evaluated_at", "2026-04-20T09:30:00Z"),
    )

    response = client.get("/backtests/monitor-definitions/alert-history-queue")

    assert response.status_code == 400
    assert (
        "observation evaluated_at must match persisted evaluation artifacts"
        in response.json()["detail"]
    )


def test_monitor_definition_recovered_alert_review_queue_route_returns_newest_recovered_rows_with_authoritative_lineage(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    second = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    ).json()

    def _payload(benchmark_symbol: str, status: str, *, confirmation_count: int) -> dict[str, object]:
        payload = cast(dict[str, object], _monitor_evaluation_payload())
        benchmark_observation = cast(dict[str, object], payload["benchmark_observation"])
        benchmark_observation["benchmark_symbol"] = benchmark_symbol
        benchmark_observation["status"] = status
        benchmark_observation["confirmation_count"] = confirmation_count
        return payload

    assert client.post(
        f"/backtests/monitor-definitions/{first['monitor_definition_id']}/evaluations",
        json=_payload("SPY", "risk_on", confirmation_count=2),
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{first['monitor_definition_id']}/evaluations",
        json=_payload("SPY", "risk_reduced", confirmation_count=2),
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{second['monitor_definition_id']}/evaluations",
        json=_payload("QQQ", "risk_on", confirmation_count=2),
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{second['monitor_definition_id']}/evaluations",
        json=_payload("QQQ", "risk_reduced", confirmation_count=2),
    ).status_code == 200

    response = client.get("/backtests/monitor-definitions/recovered-alert-review-queue?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"] == {
        "contract_version": "monitor_definition_recovered_alert_review_queue_v1",
        "provenance": "persisted_latest_observation_with_latest_snapshot_and_prior_alert_history_lineage",
        "row_provenance": "persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage",
        "source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries",
        "ordering": "newest_first_evaluated_at_then_monitor_definition_id_then_observation_id",
        "returned_limit": 10,
        "total_queue_rows": 2,
    }
    assert [item["monitor_definition_id"] for item in payload["items"]] == [
        second["monitor_definition_id"],
        first["monitor_definition_id"],
    ]
    assert payload["items"][0]["alert_classification"] == "informational"
    assert payload["items"][0]["hysteresis_transition"] == "recover"
    assert payload["items"][0]["timeline_handoff"]["observation_id"] == payload["items"][0]["observation_id"]
    assert payload["items"][0]["recovered_from"]["significance_status"] == "action_required"
    assert payload["items"][0]["latest_history_entry_id"] != payload["items"][0]["recovered_from"]["history_entry_id"]
    assert payload["items"][0]["alert_episode"]["contract_version"] == "monitor_definition_alert_episode_v1"
    assert payload["items"][0]["alert_episode"]["episode_status"] == "recovered"
    assert payload["items"][0]["alert_episode"]["hysteresis_transition"] == "recover"
    assert payload["items"][0]["alert_episode"]["source_precedence"] == "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    assert payload["items"][0]["alert_episode"]["latest_contributing_observation"]["observation_id"] == payload["items"][0]["observation_id"]


def test_monitor_definition_recovered_alert_review_queue_route_excludes_non_recovered_and_informational_only_states(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    informational_only = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    still_alerting = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    ).json()

    assert client.post(
        f"/backtests/monitor-definitions/{informational_only['monitor_definition_id']}/evaluations",
        json=_monitor_evaluation_payload(),
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{still_alerting['monitor_definition_id']}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "benchmark_symbol": "QQQ",
            },
        },
    ).status_code == 200

    response = client.get("/backtests/monitor-definitions/recovered-alert-review-queue")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["metadata"]["total_queue_rows"] == 0


def test_monitor_definition_recovered_alert_review_queue_route_fails_closed_on_latest_snapshot_history_mismatch(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    _mutate_persisted_json(
        str(tmp_path / f"{monitor_definition_id}.latest_evaluation.json"),
        lambda payload: payload.__setitem__("evaluated_at", "2026-04-22T09:30:00Z"),
    )

    response = client.get("/backtests/monitor-definitions/recovered-alert-review-queue")

    assert response.status_code == 400
    assert "observation evaluated_at must match persisted evaluation artifacts" in response.json()["detail"]


def test_monitor_definition_recovered_alert_review_queue_route_fails_closed_on_ambiguous_latest_history_state(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    latest_snapshot_payload = json.loads(
        (tmp_path / f"{monitor_definition_id}.latest_evaluation.json").read_text(encoding="utf-8")
    )
    _write_monitor_definition_history_entry(
        tmp_path,
        monitor_definition_id,
        evaluated_at=str(latest_snapshot_payload["evaluated_at"]),
        observation_status=str(latest_snapshot_payload["outcome_status"]),
        cause_code=latest_snapshot_payload["cause_code"],
        significance_status=str(latest_snapshot_payload["significance_status"]),
        reason="ambiguous_latest_duplicate",
    )

    response = client.get("/backtests/monitor-definitions/recovered-alert-review-queue")

    assert response.status_code == 400
    assert (
        "monitor definition recovered alert review queue latest history state is ambiguous"
        in response.json()["detail"]
        or "persisted latest observation hysteresis_transition does not match canonical persisted evaluation lineage"
        in response.json()["detail"]
        or "persisted latest evaluation snapshot hysteresis_transition does not match canonical persisted evaluation lineage"
        in response.json()["detail"]
        or "persisted latest evaluation history entry hysteresis_transition does not match canonical persisted evaluation lineage"
        in response.json()["detail"]
    )


def test_monitor_definition_recovered_alert_review_queue_route_fails_closed_on_unsupported_legacy_payloads(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=_monitor_evaluation_payload(),
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    latest_history_payload = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"
    ).json()
    latest_history_entry_id = latest_history_payload["items"][0]["history_entry_id"]
    _mutate_persisted_json(
        str(tmp_path / f"{monitor_definition_id}.history" / f"{latest_history_entry_id}.json"),
        lambda payload: payload.pop("significance_status"),
    )

    response = client.get("/backtests/monitor-definitions/recovered-alert-review-queue")

    assert response.status_code == 400
    assert "persisted monitor definition evaluation history entry payload is missing required field(s): significance_status" in response.json()["detail"]


def test_monitor_definition_latest_observation_alert_inbox_route_returns_newest_persisted_alert_rows_only(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    first = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    second = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    ).json()
    informational = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "DIA"},
    ).json()
    _write_monitor_definition_observation(
        tmp_path,
        first["monitor_definition_id"],
        evaluated_at="2026-04-20T09:30:00Z",
        observation_status="degraded",
        cause_code="benchmark_observation_unconfirmed",
        alert_classification="degraded",
        benchmark_symbol="SPY",
    )
    _write_monitor_definition_observation(
        tmp_path,
        second["monitor_definition_id"],
        evaluated_at="2026-04-21T09:30:00Z",
        observation_status="threshold_breach",
        alert_classification="action_required",
        benchmark_symbol="QQQ",
    )
    _write_monitor_definition_observation(
        tmp_path,
        informational["monitor_definition_id"],
        evaluated_at="2026-04-22T09:30:00Z",
        observation_status="ok",
        alert_classification="informational",
        benchmark_symbol="DIA",
    )

    response = client.get("/backtests/monitor-definitions/latest-observation-alert-inbox?limit=10")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"] == {
        "contract_version": "monitor_definition_latest_observation_alert_inbox_v1",
        "provenance": "authoritative_persisted_monitor_definition_observations_only",
        "row_provenance": "persisted_monitor_definition_observation_artifact",
        "source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry",
        "ordering": "newest_first_evaluated_at",
        "returned_limit": 10,
    }
    assert [item["monitor_definition_id"] for item in payload["items"]] == [
        second["monitor_definition_id"],
        first["monitor_definition_id"],
    ]
    assert payload["items"][0]["hysteresis_transition"] == "open"
    assert payload["items"][0]["open_handoff"]["observation_id"] == payload["items"][0]["observation_id"]
    assert payload["items"][1]["cause_code"] == "benchmark_observation_unconfirmed"


def test_monitor_definition_latest_observation_alert_inbox_route_fails_closed_on_invalid_persisted_observation(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    _write_monitor_definition_observation(tmp_path, monitor_definition_id)
    _mutate_persisted_json(
        str(tmp_path / f"{monitor_definition_id}.observation.json"),
        lambda payload: payload.__setitem__("monitor_definition_fingerprint", "0" * 64),
    )

    response = client.get("/backtests/monitor-definitions/latest-observation-alert-inbox")

    assert response.status_code == 400
    assert "monitor definition observation observation_id does not match canonical persisted payload content" in response.json()["detail"]


def test_monitor_definition_alert_review_timeline_route_returns_definition_scoped_payload_with_authoritative_ids(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=_monitor_evaluation_payload(),
    ).status_code == 200

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"] == {
        "contract_version": "monitor_definition_alert_review_timeline_v1",
        "provenance": "canonical_latest_observation_artifact_and_append_only_evaluation_history_entries",
        "ordering": "newest_first_evaluated_at_then_observation_event_then_history_entry_id",
        "monitor_definition_id": monitor_definition_id,
        "monitor_definition_fingerprint": created["fingerprint"],
        "monitor_definition_schema_version": "monitor_definition_artifact_v1",
        "observation_row_provenance": "persisted_monitor_definition_observation_artifact",
        "history_row_provenance": "persisted_monitor_definition_evaluation_history_entry",
        "source_precedence": "persisted_observation_artifact_then_persisted_evaluation_history_entries_then_persisted_latest_alert_episode_projection",
        "latest_alert_episode": None,
        "total_rows": 2,
        "observation_rows": 1,
        "history_rows": 1,
    }
    assert payload["items"][0]["event_kind"] == "latest_observation_event"
    assert payload["items"][0]["event_semantics"] == "observation_rooted"
    assert payload["items"][0]["hysteresis_transition"] == "no_op"
    assert payload["items"][0]["open_handoff"]["observation_id"] == payload["items"][0]["observation_id"]
    assert payload["items"][0]["metadata"]["row_provenance"] == "persisted_monitor_definition_observation_artifact"
    assert payload["items"][1]["event_kind"] == "evaluation_history_event"
    assert payload["items"][1]["event_semantics"] == "history_entry_rooted"
    assert payload["items"][1]["hysteresis_transition"] == "no_op"
    assert payload["items"][1]["review_handoff"]["history_entry_id"] == payload["items"][1]["history_entry_id"]
    assert payload["items"][1]["metadata"]["row_provenance"] == "persisted_monitor_definition_evaluation_history_entry"
    assert payload["metadata"]["latest_alert_episode"] is None


def test_monitor_definition_alert_review_timeline_route_derives_active_alert_episode_boundaries_from_persisted_history(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline"
    )

    assert response.status_code == 200
    episode = MonitorDefinitionAlertEpisode.model_validate(
        response.json()["metadata"]["latest_alert_episode"]
    )
    assert episode.episode_status == "active"
    assert episode.hysteresis_transition == "open"
    assert episode.source_precedence == "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    assert episode.started_at.isoformat() == response.json()["items"][1]["evaluated_at"].replace("Z", "+00:00")
    assert episode.ended_at is None
    assert episode.latest_contributing_observation.observation_id == response.json()["items"][0]["observation_id"]


def test_monitor_definition_alert_review_timeline_route_derives_recovered_alert_episode_boundaries_from_persisted_history(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline"
    )

    assert response.status_code == 200
    episode = MonitorDefinitionAlertEpisode.model_validate(
        response.json()["metadata"]["latest_alert_episode"]
    )
    assert episode.episode_status == "recovered"
    assert episode.hysteresis_transition == "recover"
    assert episode.source_precedence == "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    assert episode.ended_at is not None
    assert episode.recovery_basis is not None
    assert episode.latest_contributing_observation.observation_id == response.json()["items"][0]["observation_id"]
    assert episode.recovery_basis.recovered_from_history_entry_id == response.json()["items"][2]["history_entry_id"]


def test_monitor_definition_alert_review_timeline_route_derives_degraded_active_alert_episode_boundaries_from_persisted_history(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()

    response = client.post(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "unconfirmed",
                "confirmation_count": 1,
            },
        },
    )
    assert response.status_code == 200

    timeline_response = client.get(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/alert-review-timeline"
    )

    assert timeline_response.status_code == 200
    episode = MonitorDefinitionAlertEpisode.model_validate(
        timeline_response.json()["metadata"]["latest_alert_episode"]
    )
    assert episode.episode_status == "active"
    assert episode.latest_contributing_observation.alert_classification == "degraded"
    assert episode.latest_contributing_observation.cause_code == "benchmark_observation_unconfirmed"


def test_monitor_definition_alert_review_timeline_route_derives_unavailable_active_alert_episode_boundaries_from_persisted_history(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()

    response = client.post(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "unavailable",
                "confirmation_count": 0,
            },
        },
    )
    assert response.status_code == 200

    timeline_response = client.get(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/alert-review-timeline"
    )

    assert timeline_response.status_code == 200
    episode = MonitorDefinitionAlertEpisode.model_validate(
        timeline_response.json()["metadata"]["latest_alert_episode"]
    )
    assert episode.episode_status == "active"
    assert episode.latest_contributing_observation.alert_classification == "unavailable"
    assert episode.latest_contributing_observation.cause_code == "benchmark_observation_unavailable"


def test_monitor_definition_alert_review_timeline_route_fails_closed_on_latest_alert_episode_contradictory_recovered_transition(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    history_payload = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"
    ).json()
    _mutate_persisted_json(
        str(tmp_path / f"{monitor_definition_id}.history" / f"{history_payload['items'][0]['history_entry_id']}.json"),
        lambda payload: payload.__setitem__("evaluated_at", history_payload["items"][1]["evaluated_at"]),
    )

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline"
    )

    assert response.status_code == 400
    assert "monitor definition evaluation history entry history_entry_id does not match canonical persisted payload content" in response.json()["detail"]


def test_monitor_definition_recovered_alert_review_queue_route_returns_alert_episode_contract(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200

    response = client.get("/backtests/monitor-definitions/recovered-alert-review-queue")

    assert response.status_code == 200
    row = response.json()["items"][0]
    assert row["alert_episode"]["contract_version"] == "monitor_definition_alert_episode_v1"
    assert row["alert_episode"]["episode_status"] == "recovered"
    assert row["alert_episode"]["monitor_definition_id"] == row["monitor_definition_id"]
    assert row["alert_episode"]["latest_contributing_observation"]["observation_id"] == row["observation_id"]
    assert row["alert_episode"]["recovery_basis"]["recovered_from_history_entry_id"] == row["recovered_from"]["history_entry_id"]


def test_monitor_definition_recovered_alert_review_queue_route_fails_closed_on_contradictory_alert_episode_transition(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    history_payload = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"
    ).json()
    latest_history_entry_id = history_payload["items"][0]["history_entry_id"]
    _mutate_persisted_json(
        str(tmp_path / f"{monitor_definition_id}.history" / f"{latest_history_entry_id}.json"),
        lambda payload: payload.__setitem__("significance_status", "action_required"),
    )

    response = client.get("/backtests/monitor-definitions/recovered-alert-review-queue")

    assert response.status_code == 400
    assert "monitor definition evaluation history entry history_entry_id does not match canonical persisted payload content" in response.json()["detail"]


def test_monitor_definition_active_alert_episode_inbox_route_returns_ordered_open_persisted_episode_rows_only(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    active_oldest = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    active_newest = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "QQQ"},
    ).json()
    recovered = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "DIA"},
    ).json()

    assert client.post(
        f"/backtests/monitor-definitions/{active_oldest['monitor_definition_id']}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{active_newest['monitor_definition_id']}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "benchmark_symbol": "QQQ",
                "status": "unconfirmed",
                "confirmation_count": 1,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{recovered['monitor_definition_id']}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "benchmark_symbol": "DIA",
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{recovered['monitor_definition_id']}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "benchmark_symbol": "DIA",
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200

    response = client.get("/backtests/monitor-definitions/active-alert-episode-inbox?limit=1")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"] == {
        "contract_version": "monitor_definition_active_alert_episode_inbox_v1",
        "provenance": "authoritative_persisted_monitor_definition_alert_episode_records_only",
        "row_provenance": "persisted_monitor_definition_alert_episode_record",
        "source_precedence": "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation",
        "ordering": "newest_first_latest_event_at_then_monitor_definition_id_then_episode_id",
        "windowing": "before_episode_id_exclusive",
        "returned_limit": 1,
        "requested_before_episode_id": None,
        "next_before_episode_id": payload["items"][0]["alert_episode"]["episode_id"],
        "total_active_episodes": 2,
    }
    assert [item["alert_episode"]["monitor_definition_id"] for item in payload["items"]] == [
        active_newest["monitor_definition_id"]
    ]
    assert payload["items"][0]["alert_episode"]["lifecycle_status"] == "open"
    assert payload["items"][0]["alert_episode"]["hysteresis_transition"] == "open"
    assert payload["items"][0]["alert_episode"]["source_precedence"] == "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    assert payload["items"][0]["alert_episode"]["timeline_handoff"]["selected_event_kind"] == "latest_observation_event"

    next_response = client.get(
        f"/backtests/monitor-definitions/active-alert-episode-inbox?limit=2&before_episode_id={payload['items'][0]['alert_episode']['episode_id']}"
    )

    assert next_response.status_code == 200
    next_payload = next_response.json()
    assert next_payload["metadata"]["requested_before_episode_id"] == payload["items"][0]["alert_episode"]["episode_id"]
    assert next_payload["metadata"]["next_before_episode_id"] is None
    assert next_payload["metadata"]["total_active_episodes"] == 1
    assert [item["alert_episode"]["monitor_definition_id"] for item in next_payload["items"]] == [
        active_oldest["monitor_definition_id"]
    ]


def test_monitor_definition_active_alert_episode_inbox_route_returns_empty_rows_when_no_active_persisted_episodes_exist(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()

    response = client.get("/backtests/monitor-definitions/active-alert-episode-inbox")

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["metadata"]["total_active_episodes"] == 0
    assert response.json()["metadata"]["next_before_episode_id"] is None


def test_monitor_definition_active_alert_episode_inbox_route_fails_closed_on_persisted_episode_lineage_contradiction(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    episode_path = next((tmp_path / f"{monitor_definition_id}.episodes").glob("*.json"))
    _mutate_persisted_json(
        str(episode_path),
        lambda payload: payload.__setitem__("terminal_history_entry_id", "monitor_definition_history_other"),
    )

    response = client.get("/backtests/monitor-definitions/active-alert-episode-inbox")

    assert response.status_code == 400
    assert (
        "persisted alert episode history does not match canonical persisted evaluation lineage"
        in response.json()["detail"]
        or "monitor definition alert episode record episode_id does not match canonical persisted payload content"
        in response.json()["detail"]
    )


def test_monitor_definition_alert_review_timeline_route_reads_persisted_episode_evidence_not_client_reconstruction(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    _write_monitor_definition_observation(
        tmp_path,
        monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        observation_status="ok",
        cause_code=None,
        alert_classification="informational",
        hysteresis_transition="recover",
    )
    _write_monitor_definition_history_entry(
        tmp_path,
        monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        observation_status="ok",
        cause_code=None,
        significance_status="informational",
        hysteresis_transition="recover",
        reason="recovered persisted history",
    )
    _write_monitor_definition_history_entry(
        tmp_path,
        monitor_definition_id,
        evaluated_at="2026-04-20T09:30:00Z",
        observation_status="threshold_breach",
        cause_code=None,
        significance_status="action_required",
        reason="older alert persisted history",
    )

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline"
    )

    assert response.status_code == 200
    episode = response.json()["metadata"]["latest_alert_episode"]
    assert episode["episode_status"] == "recovered"
    assert episode["started_at"] == "2026-04-20T09:30:00Z"
    assert episode["ended_at"] == "2026-04-22T09:30:00Z"
    assert episode["recovery_basis"]["recovered_from_history_entry_id"].startswith("monitor_definition_history_")


def test_monitor_definition_alert_episode_history_route_returns_stable_ordered_bounded_rows(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200

    assert any((tmp_path / f"{monitor_definition_id}.episodes").glob("*.json"))

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history?limit=1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"] == {
        "contract_version": "monitor_definition_alert_episode_history_v1",
        "history_truth": "authoritative_persisted_monitor_definition_alert_episode_history",
        "row_provenance": "persisted_monitor_definition_alert_episode_record",
        "source_precedence": "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation",
        "ordering": "newest_first_latest_event_at_then_episode_id",
        "windowing": "before_episode_id_exclusive",
        "monitor_definition_id": monitor_definition_id,
        "monitor_definition_fingerprint": created["fingerprint"],
        "monitor_definition_schema_version": "monitor_definition_artifact_v1",
        "returned_limit": 1,
        "requested_before_episode_id": None,
        "next_before_episode_id": payload["items"][0]["episode_id"],
        "total_episodes": 2,
    }
    assert len(payload["items"]) == 1
    first_episode = payload["items"][0]
    assert first_episode["lifecycle_status"] == "open"
    assert first_episode["hysteresis_transition"] == "open"
    assert first_episode["source_precedence"] == "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    assert first_episode["latest_for_monitor_definition"] is True
    assert first_episode["timeline_handoff"]["selected_event_kind"] == "latest_observation_event"

    second_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history?limit=2&before_episode_id={first_episode['episode_id']}"
    )

    assert second_response.status_code == 200
    second_payload = second_response.json()
    assert second_payload["metadata"]["requested_before_episode_id"] == first_episode["episode_id"]
    assert second_payload["metadata"]["next_before_episode_id"] is None
    assert second_payload["metadata"]["total_episodes"] == 2
    assert [item["lifecycle_status"] for item in second_payload["items"]] == ["closed"]
    assert second_payload["items"][0]["latest_for_monitor_definition"] is False
    assert second_payload["items"][0]["timeline_handoff"]["selected_event_kind"] == "evaluation_history_event"


def test_monitor_definition_alert_episode_history_route_returns_empty_rows_when_no_persisted_episodes_exist(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()

    response = client.get(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/alert-episode-history"
    )

    assert response.status_code == 200
    assert response.json()["items"] == []
    assert response.json()["metadata"]["total_episodes"] == 0
    assert response.json()["metadata"]["next_before_episode_id"] is None


def test_monitor_definition_alert_episode_history_route_covers_open_recovered_and_closed_persisted_episode_rows(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    for status in ("risk_on", "risk_reduced", "risk_on", "risk_reduced"):
        assert client.post(
            f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
            json={
                **_monitor_evaluation_payload(),
                "benchmark_observation": {
                    **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                    "status": status,
                    "confirmation_count": 2,
                },
            },
        ).status_code == 200

    assert any((tmp_path / f"{monitor_definition_id}.episodes").glob("*.json"))

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history"
    )

    assert response.status_code == 200
    assert [item["lifecycle_status"] for item in response.json()["items"]] == ["recovered", "closed"]
    assert response.json()["items"][0]["latest_for_monitor_definition"] is True
    assert response.json()["items"][1]["latest_for_monitor_definition"] is False

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200

    open_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history"
    )
    assert open_response.status_code == 200
    assert [item["lifecycle_status"] for item in open_response.json()["items"]] == ["open", "closed", "closed"]


def test_monitor_definition_alert_episode_history_latest_row_agrees_with_latest_timeline_lifecycle_surface(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_reduced",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200

    episode_history_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history"
    )
    timeline_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline"
    )

    assert episode_history_response.status_code == 200
    assert timeline_response.status_code == 200
    latest_episode_row = episode_history_response.json()["items"][0]
    latest_timeline_episode = timeline_response.json()["metadata"]["latest_alert_episode"]
    assert latest_episode_row["episode_id"] == latest_timeline_episode["episode_id"]
    assert latest_episode_row["started_at"] == latest_timeline_episode["started_at"]
    assert latest_episode_row["ended_at"] == latest_timeline_episode["ended_at"]
    assert latest_episode_row["recovery_basis"] == latest_timeline_episode["recovery_basis"]
    assert latest_episode_row["latest_contributing_observation"] == latest_timeline_episode["latest_contributing_observation"]
    assert latest_episode_row["lifecycle_status"] == "recovered"


def test_monitor_definition_alert_episode_history_route_returns_404_for_unknown_definition(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.get(
        "/backtests/monitor-definitions/monitor_definition_missing/alert-episode-history"
    )

    assert response.status_code == 404
    assert "missing persisted monitor definition file" in response.json()["detail"]


def test_monitor_definition_alert_episode_history_route_fails_closed_on_malformed_persisted_episode_record(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    episode_dir = tmp_path / f"{monitor_definition_id}.episodes"
    episode_path = next(episode_dir.glob("*.json"))
    episode_path.write_text("{", encoding="utf-8")

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history"
    )

    assert response.status_code == 400
    assert "invalid persisted monitor definition alert episode record json" in response.json()["detail"]


def test_monitor_definition_alert_episode_history_route_fails_closed_on_episode_definition_identity_mismatch(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    episode_path = next((tmp_path / f"{monitor_definition_id}.episodes").glob("*.json"))
    _mutate_persisted_json(
        str(episode_path),
        lambda payload: payload.__setitem__("monitor_definition_id", "monitor_definition_other"),
    )

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history"
    )

    assert response.status_code == 400
    assert (
        "monitor definition alert episode record episode_id does not match canonical persisted payload content"
        in response.json()["detail"]
        or "persisted monitor definition alert episode record monitor_definition_id does not match persisted monitor definition"
        in response.json()["detail"]
    )


def test_monitor_definition_alert_episode_history_route_fails_closed_on_unsupported_ambiguous_state(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    episode_path = next((tmp_path / f"{monitor_definition_id}.episodes").glob("*.json"))
    _mutate_persisted_json(
        str(episode_path),
        lambda payload: payload.__setitem__("latest_for_monitor_definition", False),
    )

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history"
    )

    assert response.status_code == 400
    assert (
        "open alert episode history rows must remain latest for the monitor definition"
        in response.json()["detail"]
        or "persisted monitor definition alert episode record failed schema validation"
        in response.json()["detail"]
    )


def test_monitor_definition_alert_episode_history_route_fails_closed_when_persisted_episode_history_disagrees_with_canonical_lineage(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "risk_on",
                "confirmation_count": 2,
            },
        },
    ).status_code == 200
    episode_path = next((tmp_path / f"{monitor_definition_id}.episodes").glob("*.json"))
    _mutate_persisted_json(
        str(episode_path),
        lambda payload: payload.__setitem__("terminal_history_entry_id", "monitor_definition_history_other"),
    )

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-episode-history"
    )

    assert response.status_code == 400
    assert (
        "persisted alert episode history does not match canonical persisted evaluation lineage"
        in response.json()["detail"]
        or "monitor definition alert episode record episode_id does not match canonical persisted payload content"
        in response.json()["detail"]
    )


def test_monitor_definition_alert_review_timeline_route_fails_closed_on_unsupported_or_malformed_persisted_state(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]

    assert client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=_monitor_evaluation_payload(),
    ).status_code == 200
    history_dir = tmp_path / f"{monitor_definition_id}.history"
    history_entry = next(history_dir.glob("*.json"))
    _mutate_persisted_json(
        str(history_entry),
        lambda payload: payload.__setitem__("monitor_definition_fingerprint", "0" * 64),
    )

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/alert-review-timeline"
    )

    assert response.status_code == 400
    assert (
        "monitor definition evaluation history entry history_entry_id does not match canonical persisted payload content"
        in response.json()["detail"]
        or "persisted monitor definition evaluation history entry fingerprint does not match persisted monitor definition"
        in response.json()["detail"]
    )


def test_monitor_definition_observation_route_reads_persisted_observation_only(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=_monitor_evaluation_payload(),
    )
    (tmp_path / f"{monitor_definition_id}.observation.json").unlink()

    response = client.get(f"/backtests/monitor-definitions/{monitor_definition_id}/observation")

    assert response.status_code == 404
    assert "missing persisted monitor definition observation file" in response.json()["detail"]


@pytest.mark.parametrize(
    ("mutator", "expected_detail"),
    [
        (
            lambda payload: payload.pop("alert_classification"),
            "persisted monitor definition observation payload is missing required field(s): alert_classification",
        ),
        (
            lambda payload: payload.pop("cause_code"),
            "persisted monitor definition observation payload is missing required field(s): cause_code",
        ),
        (
            lambda payload: payload.__setitem__("monitor_definition_id", "monitor_definition_other"),
            "monitor definition observation observation_id does not match canonical persisted payload content",
        ),
        (
            lambda payload: payload["benchmark_observation"].__setitem__("benchmark_symbol", "QQQ"),
            "monitor definition observation observation_id does not match canonical persisted payload content",
        ),
    ],
)
def test_monitor_definition_observation_route_fails_closed_on_invalid_persisted_observation(
    tmp_path,
    mocker,
    mutator,
    expected_detail: str,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    _write_monitor_definition_observation(tmp_path, monitor_definition_id)
    _mutate_persisted_json(str(tmp_path / f"{monitor_definition_id}.observation.json"), mutator)

    response = client.get(f"/backtests/monitor-definitions/{monitor_definition_id}/observation")

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]


@pytest.mark.parametrize("route", ["catalog", "recent"])
@pytest.mark.parametrize(
    ("mutator", "expected_detail"),
    [
        (
            lambda payload: payload.pop("alert_classification"),
            "persisted monitor definition observation payload is missing required field(s): alert_classification",
        ),
        (
            lambda payload: payload.pop("cause_code"),
            "persisted monitor definition observation payload is missing required field(s): cause_code",
        ),
        (
            lambda payload: payload["portfolio_observation"]["source_lineage"].pop("importer"),
            "monitor definition observation observation_id does not match canonical persisted payload content",
        ),
        (
            lambda payload: payload.__setitem__("monitor_definition_fingerprint", "0" * 64),
            "monitor definition observation observation_id does not match canonical persisted payload content",
        ),
    ],
)
def test_monitor_definition_discovery_routes_fail_closed_on_malformed_partial_or_mismatched_present_observation_artifacts(
    tmp_path,
    mocker,
    route: str,
    mutator,
    expected_detail: str,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    _write_monitor_definition_observation(tmp_path, monitor_definition_id)
    _mutate_persisted_json(str(tmp_path / f"{monitor_definition_id}.observation.json"), mutator)

    response = client.get(f"/backtests/monitor-definitions/{route}")

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]


def test_monitor_definition_discovery_routes_fail_closed_on_missing_required_present_snapshot_field(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(tmp_path, created["monitor_definition_id"])
    _mutate_persisted_json(
        str(tmp_path / f"{created['monitor_definition_id']}.latest_evaluation.json"),
        lambda payload: payload.pop("portfolio_truth_basis"),
    )

    response = client.get("/backtests/monitor-definitions/catalog")

    assert response.status_code == 400
    assert "persisted latest evaluation snapshot payload is missing required field(s): portfolio_truth_basis" in response.json()["detail"]


def test_monitor_definition_discovery_routes_fail_closed_on_missing_required_present_snapshot_cause_code(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(tmp_path, created["monitor_definition_id"])
    _mutate_persisted_json(
        str(tmp_path / f"{created['monitor_definition_id']}.latest_evaluation.json"),
        lambda payload: payload.pop("cause_code"),
    )

    response = client.get("/backtests/monitor-definitions/catalog")

    assert response.status_code == 400
    assert "persisted latest evaluation snapshot payload is missing required field(s): cause_code" in response.json()["detail"]


def test_monitor_definition_routes_fail_closed_on_cross_artifact_cause_code_mismatch(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json={
            **_monitor_evaluation_payload(),
            "benchmark_observation": {
                **cast(dict[str, object], _monitor_evaluation_payload()["benchmark_observation"]),
                "status": "unavailable",
                "confirmation_count": 0,
            },
        },
    )
    history_payload = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"
    ).json()
    history_entry_id = history_payload["items"][0]["history_entry_id"]
    _rekey_monitor_definition_observation_payload(
        tmp_path / f"{monitor_definition_id}.observation.json",
        lambda payload: payload.__setitem__("cause_code", "portfolio_truth_non_positive_total_value"),
    )

    observation_response = client.get(f"/backtests/monitor-definitions/{monitor_definition_id}/observation")
    history_response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history/{history_entry_id}"
    )
    catalog_response = client.get("/backtests/monitor-definitions/catalog")

    assert observation_response.status_code == 400
    assert history_response.status_code == 200
    assert catalog_response.status_code == 400
    assert "observation cause_code must match persisted evaluation artifacts" in catalog_response.json()["detail"]


def test_monitor_definition_discovery_routes_fail_closed_on_ambiguous_present_snapshot_nested_state(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(tmp_path, created["monitor_definition_id"])
    _mutate_persisted_json(
        str(tmp_path / f"{created['monitor_definition_id']}.latest_evaluation.json"),
        lambda payload: payload["benchmark_observation_lineage"].pop("observed_at"),
    )

    response = client.get("/backtests/monitor-definitions/catalog")

    assert response.status_code == 400
    assert "persisted latest evaluation snapshot benchmark_observation_lineage must be fully specified when present" in response.json()["detail"]


def test_monitor_definition_discovery_routes_fail_closed_on_present_snapshot_definition_id_mismatch(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(tmp_path, created["monitor_definition_id"])
    _mutate_persisted_json(
        str(tmp_path / f"{created['monitor_definition_id']}.latest_evaluation.json"),
        lambda payload: payload.__setitem__("monitor_definition_id", "monitor_definition_other"),
    )

    response = client.get("/backtests/monitor-definitions/catalog")

    assert response.status_code == 400
    assert "persisted latest evaluation snapshot monitor_definition_id does not match requested definition" in response.json()["detail"]


def test_monitor_definition_history_routes_fail_closed_on_definition_mismatched_history_entry(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    monitor_definition_id = created["monitor_definition_id"]
    client.post(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluations",
        json=_monitor_evaluation_payload(),
    )
    history_payload = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"
    ).json()
    history_entry_id = history_payload["items"][0]["history_entry_id"]
    _mutate_persisted_json(
        str(tmp_path / f"{monitor_definition_id}.history" / f"{history_entry_id}.json"),
        lambda payload: payload.__setitem__("benchmark_symbol", "QQQ"),
    )

    response = client.get(
        f"/backtests/monitor-definitions/{monitor_definition_id}/evaluation-history"
    )

    assert response.status_code == 400
    assert "monitor definition evaluation history entry history_entry_id does not match canonical persisted payload content" in response.json()["detail"] or "persisted monitor definition evaluation history entry benchmark_symbol does not match persisted monitor definition" in response.json()["detail"]


def test_monitor_definition_history_routes_read_append_only_entries_not_latest_snapshot_sidecar(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    _write_latest_monitor_evaluation_snapshot(tmp_path, created["monitor_definition_id"])

    response = client.get(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/evaluation-history"
    )

    assert response.status_code == 200
    assert response.json()["metadata"]["monitor_definition_id"] == created["monitor_definition_id"]
    assert response.json()["metadata"]["total_entries"] == 0
    assert response.json()["items"] == []


def test_monitor_definition_history_inspection_route_returns_404_for_unknown_entry(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()

    response = client.get(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/evaluation-history/monitor_definition_history_missing"
    )

    assert response.status_code == 404
    assert "missing persisted monitor definition evaluation history entry file" in response.json()["detail"]


def test_monitor_definition_evaluation_and_history_routes_keep_observation_blocks_separate(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.monitor_definition_artifact_service.get_settings",
        return_value=SimpleNamespace(monitor_definition_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    created = client.post(
        "/backtests/monitor-definitions",
        json={"monitor_id": "benchmark_trend_overlay_v1", "benchmark_symbol": "SPY"},
    ).json()
    evaluate_response = client.post(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/evaluations",
        json=_monitor_evaluation_payload(),
    )
    history_response = client.get(
        f"/backtests/monitor-definitions/{created['monitor_definition_id']}/evaluation-history"
    )

    assert evaluate_response.status_code == 200
    evaluation_payload = evaluate_response.json()
    assert evaluation_payload["benchmark_observation"]["overlay_id"] == "benchmark_trend_overlay_v1"
    assert evaluation_payload["portfolio_observation"]["total_portfolio_value"] == 685.0
    assert evaluation_payload["active_observation"]["required_overlay_status"] == "risk_reduced"

    assert history_response.status_code == 200
    history_item = history_response.json()["items"][0]
    assert history_item["benchmark_observation"]["status"] == "risk_reduced"
    assert history_item["portfolio_observation"]["cash_value"] == 650.0
    assert history_item["active_observation"]["threshold_evaluation_performed"] is True


def test_replacement_ranking_artifact_route_is_registered(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    run_response = client.post(
        "/ranking/etf-replacements",
        json={
            "replacement_intent": {
                "draft_id": "draft-1",
                "workspace_id": "workspace-1",
                "base_node_id": "node-1",
                "base_symbol": "BASE",
                "candidate_symbol": "ETF1",
                "seed_ranking_id": "etf_ranking_engine_v1",
                "seed_methodology_id": "etf_ranking_methodology_v1",
                "seed_ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
            },
            "seed_context": {
                "ranking_id": "etf_ranking_engine_v1",
                "methodology_id": "etf_ranking_methodology_v1",
                "ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
                "seeded_symbols": ["BASE", "ETF1", "ETF2"],
            },
        },
    )

    assert run_response.status_code == 200
    payload = run_response.json()
    assert "artifact_id" not in payload
    assert payload["ranking_id"] == "intent_bound_etf_replacement_ranking_v1"
    artifact_id = _single_artifact_id(tmp_path)

    response = client.get(f"/ranking/etf-replacements/artifacts/{artifact_id}")

    assert response.status_code == 200
    assert response.json()["artifact_id"] == artifact_id


def test_strategy_lab_replacement_ranking_artifact_routes_are_registered(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    run_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json={
            "replacement_intent": {
                "draft_id": "draft-1",
                "workspace_id": "workspace-1",
                "base_node_id": "node-1",
                "base_symbol": "BASE",
                "candidate_symbol": "ETF1",
                "seed_ranking_id": "etf_ranking_engine_v1",
                "seed_methodology_id": "etf_ranking_methodology_v1",
                "seed_ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
            },
            "seed_context": {
                "ranking_id": "etf_ranking_engine_v1",
                "methodology_id": "etf_ranking_methodology_v1",
                "ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
                "seeded_symbols": ["BASE", "ETF1", "ETF2"],
            },
        },
    )

    assert run_response.status_code == 200
    strategy_lab_payload = run_response.json()
    assert strategy_lab_payload["artifact_id"].startswith("intent_bound_etf_replacement_ranking_artifact_")
    artifact_id = strategy_lab_payload["artifact_id"]

    strategy_lab_response = client.get(f"/strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}")
    legacy_response = client.get(f"/ranking/etf-replacements/artifacts/{artifact_id}")

    assert strategy_lab_response.status_code == 200
    assert legacy_response.status_code == 200
    assert strategy_lab_response.json()["artifact_id"] == artifact_id
    assert legacy_response.json()["artifact_id"] == artifact_id


def test_generalized_ranking_artifact_catalog_routes_are_registered(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert etf_response.status_code == 200

    catalog_response = client.get("/strategy-lab/ranking-artifacts/catalog")
    recent_response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert catalog_response.status_code == 200
    assert recent_response.status_code == 200
    assert catalog_response.json()["items"][0]["artifact_kind"] == "etf_ranking"
    assert recent_response.json()["items"][0]["artifact_kind"] == "etf_ranking"
    assert catalog_response.json()["metadata"]["artifact_kind_registry_version"] == "ranking_artifact_kind_registry_v1"
    assert catalog_response.json()["metadata"]["artifact_kind_registry"][0]["artifact_kind"] == "etf_ranking"
    assert "benchmark_symbol" in catalog_response.json()["metadata"]["artifact_kind_registry"][0]["supported_filters"]


def test_generalized_ranking_artifact_preflight_and_open_routes_are_registered(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert etf_response.status_code == 200
    artifact_id = etf_response.json()["artifact_id"]

    preflight_response = client.post(f"/strategy-lab/ranking-artifacts/preflight/{artifact_id}")

    assert preflight_response.status_code == 200
    open_response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=preflight_response.json()["open_handoff"],
    )

    assert open_response.status_code == 200
    assert open_response.json()["open_handoff"]["artifact_id"] == artifact_id


def test_generalized_ranking_artifact_open_route_rejects_missing_handoff_kind_for_valid_persisted_artifact(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert etf_response.status_code == 200
    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{etf_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200

    handoff_payload = preflight_response.json()["open_handoff"]
    handoff_payload.pop("handoff_kind")

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=handoff_payload,
    )

    assert response.status_code == 422
    assert "open_handoff.handoff_kind is required" in response.text


def test_generalized_ranking_artifact_open_route_rejects_unsupported_handoff_kind_for_valid_persisted_artifact(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert etf_response.status_code == 200
    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{etf_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200

    handoff_payload = preflight_response.json()["open_handoff"]
    handoff_payload["handoff_kind"] = "ranking_artifact_open_handoff_v0"

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=handoff_payload,
    )

    assert response.status_code == 422
    assert "unsupported open_handoff.handoff_kind: ranking_artifact_open_handoff_v0" in response.text


def test_generalized_ranking_artifact_open_route_rejects_handoff_identity_mismatch_for_valid_persisted_artifact(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert etf_response.status_code == 200
    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{etf_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200

    handoff_payload = preflight_response.json()["open_handoff"]
    handoff_payload["artifact_id"] = "etf_ranking_artifact_other"

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=handoff_payload,
    )

    assert response.status_code == 404
    assert "missing persisted etf ranking artifact file" in response.json()["detail"]


def test_generalized_ranking_artifact_open_route_returns_replacement_consumer_handoff(tmp_path, mocker) -> None:
    _patch_replacement_ranking_dependencies(mocker)
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json={
            "replacement_intent": {
                "draft_id": "draft-1",
                "workspace_id": "workspace-1",
                "base_node_id": "node-1",
                "base_symbol": "BASE",
                "candidate_symbol": "ETF1",
                "seed_ranking_id": "etf_ranking_engine_v1",
                "seed_methodology_id": "etf_ranking_methodology_v1",
                "seed_ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
            },
            "seed_context": {
                "ranking_id": "etf_ranking_engine_v1",
                "methodology_id": "etf_ranking_methodology_v1",
                "ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
                "seeded_symbols": ["BASE", "ETF1", "ETF2"],
            },
        },
    )
    assert artifact_response.status_code == 200

    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200
    assert preflight_response.json()["eligibility"]["consumer_handoff_supported"] is True
    assert preflight_response.json()["eligibility"]["ineligibility_reason"] is None

    open_response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=preflight_response.json()["open_handoff"],
    )

    assert open_response.status_code == 200
    assert open_response.json()["consumer_handoff"]["handoff_kind"] == (
        "intent_bound_etf_replacement_ranking_consumer_handoff_v1"
    )
    assert open_response.json()["consumer_handoff"]["candidate_symbol"] == "ETF1"


def test_generalized_ranking_artifact_preflight_route_fails_closed_for_unconstructible_replacement_handoff(
    tmp_path,
    mocker,
) -> None:
    _patch_replacement_ranking_dependencies(mocker)
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json={
            "replacement_intent": {
                "draft_id": "draft-1",
                "workspace_id": "workspace-1",
                "base_node_id": "node-1",
                "base_symbol": "BASE",
                "candidate_symbol": "ETF1",
                "seed_ranking_id": "etf_ranking_engine_v1",
                "seed_methodology_id": "etf_ranking_methodology_v1",
                "seed_ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
            },
            "seed_context": {
                "ranking_id": "etf_ranking_engine_v1",
                "methodology_id": "etf_ranking_methodology_v1",
                "ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
                "seeded_symbols": ["BASE", "ETF2"],
            },
        },
    )
    assert artifact_response.status_code == 200

    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_response.json()['artifact_id']}"
    )

    assert preflight_response.status_code == 200
    assert preflight_response.json()["eligibility"] == {
        "review_truth_basis": "authoritative_persisted_ranking_artifact",
        "review_scope": "artifact_backed_review_only",
        "open_supported": False,
        "replay_eligible": False,
        "consumer_handoff_supported": False,
        "ineligibility_reason": "replacement ranking artifact is unreplayable",
    }
    assert set(preflight_response.json().keys()) == {"contract_version", "artifact", "eligibility", "open_handoff"}


def test_generalized_ranking_artifact_recent_route_returns_400_for_malformed_etf_recent_index(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200
    (tmp_path / "etf" / "recent.jsonl").write_text("not-json\n", encoding="utf-8")

    recent_response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert recent_response.status_code == 400
    assert "invalid persisted etf ranking recent index json" in recent_response.json()["detail"]


def test_cross_sectional_research_routes_are_registered(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    validate_response = client.post(
        "/strategy-lab/cross-sectional-research/validate",
        json=_cross_sectional_research_request_payload(),
    )
    run_response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )

    assert validate_response.status_code == 200
    assert run_response.status_code == 200
    artifact_id = run_response.json()["artifact_id"]

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")
    catalog_response = client.get("/strategy-lab/cross-sectional-research/catalog")
    recent_response = client.get("/strategy-lab/cross-sectional-research/recent")

    assert get_response.status_code == 200
    assert catalog_response.status_code == 200
    assert recent_response.status_code == 200
    assert get_response.json()["contract_version"] == "cross_sectional_research_reload_v1"
    assert get_response.json()["requested_artifact_id"] == artifact_id
    assert get_response.json()["artifact_id"] == artifact_id
    assert get_response.json()["artifact"]["artifact_id"] == artifact_id
    assert catalog_response.json()["items"][0]["artifact_id"] == artifact_id
    assert recent_response.json()["items"][0]["artifact_id"] == artifact_id
    assert catalog_response.json()["metadata"]["contract_version"] == "cross_sectional_research_discovery_v1"
    assert recent_response.json()["metadata"]["contract_version"] == "cross_sectional_research_discovery_v1"
    assert catalog_response.json()["metadata"]["recent_order_basis"] == "persisted_artifact.persisted_at_then_artifact_id"
    assert catalog_response.json()["metadata"]["supported_filters"] == [
        "artifact_kind",
        "schema_version",
        "methodology_id",
        "dataset_version",
        "universe_definition",
        "benchmark_symbol",
        "rebalance_date",
        "as_of_date",
        "holdout_start_date",
        "methodology_family_id",
        "methodology_family_version",
        "active_methodology_version",
        "alpha_package_version",
        "alpha_methodology_id",
        "alpha_input_contract_id",
        "score_basis",
        "benchmark_role",
        "partition_rule",
        "output_shape",
        "artifact_status",
        "diagnostics_status",
        "coverage_status",
        "input_source_kind",
        "replay_provenance_status",
        "benchmark_source_kind",
        "alpha_source_kind",
    ]
    assert catalog_response.json()["metadata"]["methodology_metadata_v1_semantics"] == "descriptive_only"
    assert catalog_response.json()["metadata"]["status_metadata_v1_semantics"] == "descriptive_only"
    assert catalog_response.json()["metadata"]["provenance_metadata_v1_semantics"] == "descriptive_only"
    assert get_response.json()["artifact"]["methodology_metadata_v1"]["active_methodology_id"] == "alpha_quality_v1"
    assert get_response.json()["artifact"]["status_metadata_v1"] == {
        "artifact_status": "complete",
        "diagnostics_status": "ok",
        "coverage_status": "complete",
    }
    assert set(get_response.json()["artifact"]["status_metadata_v1"]) == {
        "artifact_status",
        "diagnostics_status",
        "coverage_status",
    }
    assert get_response.json()["artifact"]["provenance_metadata_v1"] == {
        "input_source_kind": "direct_snapshot_input",
        "replay_provenance_status": "absent",
        "benchmark_source_kind": "request_benchmark_reference",
        "alpha_source_kind": "optimizer_alpha_package",
    }
    assert catalog_response.json()["items"][0]["methodology_metadata_v1"]["benchmark_role"] == "descriptive_reference_only"
    assert catalog_response.json()["items"][0]["status_metadata_v1"]["diagnostics_status"] == "ok"
    assert catalog_response.json()["items"][0]["provenance_metadata_v1"]["benchmark_source_kind"] == "request_benchmark_reference"
    assert recent_response.json()["items"][0]["methodology_metadata_v1"]["output_shape"] == "compact_summary_only"
    assert recent_response.json()["items"][0]["status_metadata_v1"]["coverage_status"] == "complete"
    assert recent_response.json()["items"][0]["provenance_metadata_v1"]["alpha_source_kind"] == "optimizer_alpha_package"
    assert recent_response.json()["items"][0]["recent_order_artifact_id"] == artifact_id
    assert validate_response.json()["status_metadata_v1"] == {
        "artifact_status": "complete",
        "diagnostics_status": "ok",
        "coverage_status": "complete",
    }
    assert validate_response.json()["provenance_metadata_v1"] == {
        "input_source_kind": "direct_snapshot_input",
        "replay_provenance_status": "absent",
        "benchmark_source_kind": "request_benchmark_reference",
        "alpha_source_kind": "optimizer_alpha_package",
    }


def test_cross_sectional_research_missing_reload_route_returns_404(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.get(
        "/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_missing"
    )

    assert response.status_code == 404
    assert "missing persisted cross-sectional research artifact file" in response.json()["detail"]


def test_legacy_replacement_ranking_post_preserves_non_artifact_response_shape(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/ranking/etf-replacements",
        json={
            "replacement_intent": {
                "draft_id": "draft-1",
                "workspace_id": "workspace-1",
                "base_node_id": "node-1",
                "base_symbol": "BASE",
                "candidate_symbol": "ETF1",
                "seed_ranking_id": "etf_ranking_engine_v1",
                "seed_methodology_id": "etf_ranking_methodology_v1",
                "seed_ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
            },
            "seed_context": {
                "ranking_id": "etf_ranking_engine_v1",
                "methodology_id": "etf_ranking_methodology_v1",
                "ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
                "seeded_symbols": ["BASE", "ETF1", "ETF2"],
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_id"] == "intent_bound_etf_replacement_ranking_v1"
    assert "artifact_id" not in payload
    assert "schema_version" not in payload
    assert "lineage" not in payload
    assert payload["request_context"]["benchmark_symbol"] == "SPY"
    assert _single_artifact_id(tmp_path).startswith("intent_bound_etf_replacement_ranking_artifact_")


def test_construction_route_is_registered(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path / "etf")),
    )
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-1",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "CCC", "weight": 0.5},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "feasible"
    assert payload["artifact_id"].startswith("construction_artifact_")
    assert payload["policy"]["policy_id"] == "top_n_equal_weight_v1"
    assert payload["normalized_inputs"]["policy_id"] == "top_n_equal_weight_v1"
    assert payload["normalized_inputs"]["min_position_weight"] is None
    assert payload["normalized_inputs"]["max_trade_intent_count"] is None
    assert payload["turnover_diagnostics_status"] == "available"
    assert payload["turnover_diagnostics_v1"] == {
        "diagnostics_version": "construction_turnover_diagnostics_v1",
        "source": "persisted_construction_artifact",
        "diagnostic_truth": "artifact_backed_hypothetical_construction_diagnostics_only",
        "turnover_basis_method_version": "half_l1_weight_delta_union_v1",
        "reported_value_status": "computed",
        "reported_turnover_weight": 0.5,
        "inclusion_flags": {
            "uses_current_and_target_weight_union": True,
            "includes_initiations": True,
            "includes_exits": True,
            "includes_zero_delta_positions_in_trade_intent_context": True,
            "excludes_zero_delta_positions_from_reported_turnover_sum": True,
        },
        "trade_intent_context": {"source_field": "trade_intents", "intent_count": 3},
        "feasibility_context": {
            "artifact_status": "feasible",
            "failure_reasons_field": "failure_reasons",
            "turnover_failure_reason_present": False,
        },
        "constraint_context": {
            "constraint_id": "max_turnover_weight",
            "requested": False,
            "limit_weight": None,
            "evaluation_status": "not_evaluated",
        },
        "symbol_contributions": [
            {
                "symbol": "AAA",
                "action": "hold",
                "current_weight": 0.5,
                "target_weight": 0.5,
                "delta_weight": 0.0,
                "absolute_delta_weight": 0.0,
                "turnover_contribution_weight": 0.0,
                "contribution_fraction_of_reported_turnover": 0.0,
                "included_in_reported_turnover": False,
            },
            {
                "symbol": "BBB",
                "action": "initiate",
                "current_weight": 0.0,
                "target_weight": 0.5,
                "delta_weight": 0.5,
                "absolute_delta_weight": 0.5,
                "turnover_contribution_weight": 0.25,
                "contribution_fraction_of_reported_turnover": 0.5,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "CCC",
                "action": "exit",
                "current_weight": 0.5,
                "target_weight": 0.0,
                "delta_weight": -0.5,
                "absolute_delta_weight": 0.5,
                "turnover_contribution_weight": 0.25,
                "contribution_fraction_of_reported_turnover": 0.5,
                "included_in_reported_turnover": True,
            },
        ],
    }
    assert payload["weighting_trace_status"] == "available"
    assert payload["weighting_trace_v1"]["trace_version"] == "weighting_trace_v1"
    assert payload["weighting_trace_v1"]["artifact_binding"] == {
        "binding_status": "final_target_weights_persisted",
        "final_target_weights_present": True,
    }
    assert next(item for item in payload["constraint_evaluations"] if item["constraint_id"] == "max_trade_intent_count") == {
        "constraint_id": "max_trade_intent_count",
        "status": "not_evaluated",
        "actual_value": None,
        "limit_value": None,
        "message": "max_trade_intent_count was not requested",
    }


def test_construction_ranking_artifact_preflight_route_returns_canonical_handoff(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path / "etf")),
    )
    client = TestClient(app)

    ranking_response = client.post("/strategy-lab/etf-ranking", json=_etf_ranking_request_payload())
    assert ranking_response.status_code == 200
    ranking_payload = ranking_response.json()

    response = client.post(f"/construction/ranking-artifacts/preflight/{ranking_payload['artifact_id']}")

    assert response.status_code == 200
    assert response.json() == {
        "contract_version": "construction_ranking_artifact_preflight_v1",
        "artifact": {
            "artifact_kind": "etf_ranking",
            "artifact_id": ranking_payload["artifact_id"],
            "schema_version": "etf_ranking_artifact_v1",
            "ranking_id": ranking_payload["ranking_id"],
            "methodology_id": ranking_payload["run_metadata"]["methodology_id"],
            "as_of_date": ranking_payload["run_metadata"]["as_of_date"],
        },
        "handoff": {
            "handoff_kind": "etf_ranking_artifact_construction_handoff_v1",
            "artifact_kind": "etf_ranking",
            "artifact_id": ranking_payload["artifact_id"],
            "schema_version": "etf_ranking_artifact_v1",
            "ranking_id": ranking_payload["ranking_id"],
            "methodology_id": ranking_payload["run_metadata"]["methodology_id"],
            "as_of_date": ranking_payload["run_metadata"]["as_of_date"],
        },
    }


def test_construction_ranking_artifact_preflight_route_returns_404_only_for_missing_artifact(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path / "etf")),
    )
    client = TestClient(app)

    response = client.post("/construction/ranking-artifacts/preflight/etf_ranking_artifact_missing")

    assert response.status_code == 404
    assert "missing persisted etf ranking artifact file" in response.json()["detail"]


@pytest.mark.parametrize(
    ("scenario", "expected_detail"),
    [
        ("invalid_persisted_artifact_json", "invalid persisted etf ranking artifact json"),
        ("non_object_persisted_payload", "persisted etf ranking artifact payload must be a json object"),
        ("unsupported_persisted_schema_version", "unsupported etf ranking schema_version"),
        ("persisted_schema_validation_failure", "persisted etf ranking artifact failed schema validation"),
        (
            "persisted_artifact_identity_integrity_mismatch",
            "etf ranking artifact_id does not match canonical artifact content",
        ),
    ],
)
def test_construction_ranking_artifact_preflight_route_fails_closed_for_malformed_persisted_etf_ranking_states(
    tmp_path,
    mocker,
    scenario: str,
    expected_detail: str,
) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path / "etf")),
    )
    client = TestClient(app)

    ranking_response = client.post("/strategy-lab/etf-ranking", json=_etf_ranking_request_payload())
    assert ranking_response.status_code == 200
    artifact_id = ranking_response.json()["artifact_id"]
    artifact_path = tmp_path / "etf" / f"{artifact_id}.json"

    if scenario == "invalid_persisted_artifact_json":
        artifact_path.write_text("{", encoding="utf-8")
    elif scenario == "non_object_persisted_payload":
        artifact_path.write_text("[]", encoding="utf-8")
    elif scenario == "unsupported_persisted_schema_version":
        _mutate_persisted_json(str(artifact_path), lambda payload: payload.__setitem__("schema_version", "etf_ranking_artifact_v0"))
    elif scenario == "persisted_schema_validation_failure":
        _mutate_persisted_json(str(artifact_path), lambda payload: payload.pop("run_metadata"))
    elif scenario == "persisted_artifact_identity_integrity_mismatch":
        _mutate_persisted_json(
            str(artifact_path),
            lambda payload: payload.__setitem__("artifact_id", "etf_ranking_artifact_other"),
        )
    else:
        raise AssertionError(f"unsupported malformed persisted etf ranking scenario: {scenario}")

    response = client.post(f"/construction/ranking-artifacts/preflight/{artifact_id}")

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]


def test_construction_ranking_artifact_preflight_route_fails_closed_for_construction_unusable_persisted_etf_ranking_state(
    tmp_path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path / "etf")),
    )
    client = TestClient(app)

    ranking_response = client.post("/strategy-lab/etf-ranking", json=_etf_ranking_request_payload())
    assert ranking_response.status_code == 200
    artifact_id = _rekey_etf_ranking_artifact_payload(
        tmp_path,
        ranking_response.json()["artifact_id"],
        lambda payload: payload.__setitem__("ranked_universe", []),
    )

    response = client.post(f"/construction/ranking-artifacts/preflight/{artifact_id}")

    assert response.status_code == 400
    assert response.json()["detail"] == "persisted etf ranking artifact has no eligible ranked candidates for construction"


def test_construction_run_route_accepts_ranking_artifact_handoff_and_persists_construction_artifact(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path / "etf")),
    )
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path / "construction")),
    )
    client = TestClient(app)

    ranking_response = client.post("/strategy-lab/etf-ranking", json=_etf_ranking_request_payload())
    assert ranking_response.status_code == 200
    ranking_payload = ranking_response.json()
    preflight_response = client.post(f"/construction/ranking-artifacts/preflight/{ranking_payload['artifact_id']}")
    assert preflight_response.status_code == 200

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-artifact-handoff-1",
            "ranking_artifact_handoff": preflight_response.json()["handoff"],
            "current_portfolio": _construction_current_portfolio_payload(),
            **_construction_policy_payload(),
            **_construction_constraints_payload(),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_id"].startswith("construction_artifact_")
    assert payload["normalized_inputs"]["ranked_universe_artifact_kind"] == "etf_ranking"
    assert payload["normalized_inputs"]["ranked_universe_artifact_id"] == ranking_payload["artifact_id"]
    assert payload["normalized_inputs"]["ranked_universe_artifact_schema_version"] == "etf_ranking_artifact_v1"
    assert payload["normalized_inputs"]["ranking_id"] == ranking_payload["ranking_id"]
    assert payload["normalized_inputs"]["ranking_methodology_id"] == ranking_payload["run_metadata"]["methodology_id"]


def test_construction_run_route_rejects_mixed_inline_and_handoff_ranking_sources(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path / "etf")),
    )
    client = TestClient(app)

    ranking_response = client.post("/strategy-lab/etf-ranking", json=_etf_ranking_request_payload())
    preflight_response = client.post(
        f"/construction/ranking-artifacts/preflight/{ranking_response.json()['artifact_id']}"
    )

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-mixed-ranking-source-1",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [{"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9}],
            },
            "ranking_artifact_handoff": preflight_response.json()["handoff"],
            "current_portfolio": _construction_current_portfolio_payload(),
            **_construction_policy_payload(),
            **_construction_constraints_payload(),
        },
    )

    assert response.status_code == 422
    assert "construction run request must provide exactly one of ranked_universe or ranking_artifact_handoff" in response.text


@pytest.mark.parametrize(
    ("scenario", "expected_status", "expected_detail"),
    [
        (
            "missing_handoff_kind",
            422,
            "ranking_artifact_handoff.handoff_kind is required",
        ),
        (
            "unsupported_handoff_kind",
            422,
            "unsupported ranking_artifact_handoff.handoff_kind: etf_ranking_artifact_construction_handoff_v0",
        ),
        (
            "unsupported_artifact_kind",
            422,
            "unsupported ranking artifact kind",
        ),
        (
            "unsupported_schema_version",
            422,
            "unsupported etf ranking schema_version",
        ),
        (
            "ranking_id_mismatch",
            400,
            "ranking artifact handoff ranking_id does not match persisted artifact",
        ),
        (
            "missing_artifact",
            404,
            "missing persisted etf ranking artifact file",
        ),
        (
            "corrupt_artifact_json",
            400,
            "invalid persisted etf ranking artifact json",
        ),
    ],
)
def test_construction_ranking_artifact_boundaries_fail_closed_for_invalid_handoff_or_artifact_states(
    tmp_path,
    mocker,
    scenario: str,
    expected_status: int,
    expected_detail: str,
) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path / "etf")),
    )
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path / "construction")),
    )
    client = TestClient(app)

    ranking_response = client.post("/strategy-lab/etf-ranking", json=_etf_ranking_request_payload())
    assert ranking_response.status_code == 200
    ranking_payload = ranking_response.json()
    preflight_response = client.post(f"/construction/ranking-artifacts/preflight/{ranking_payload['artifact_id']}")
    assert preflight_response.status_code == 200
    mutable_preflight = preflight_response.json()
    if scenario == "missing_handoff_kind":
        mutable_preflight["handoff"].pop("handoff_kind")
    elif scenario == "unsupported_handoff_kind":
        mutable_preflight["handoff"]["handoff_kind"] = "etf_ranking_artifact_construction_handoff_v0"
    elif scenario == "unsupported_artifact_kind":
        mutable_preflight["handoff"]["artifact_kind"] = "intent_bound_etf_replacement_ranking"
    elif scenario == "unsupported_schema_version":
        mutable_preflight["handoff"]["schema_version"] = "etf_ranking_artifact_v0"
    elif scenario == "ranking_id_mismatch":
        mutable_preflight["handoff"]["ranking_id"] = "wrong-ranking-id"
    elif scenario == "missing_artifact":
        mutable_preflight["handoff"]["artifact_id"] = "etf_ranking_artifact_missing"
    elif scenario == "corrupt_artifact_json":
        (tmp_path / "etf" / f"{ranking_payload['artifact_id']}.json").write_text("{", encoding="utf-8")
    else:
        raise AssertionError(f"unsupported test scenario: {scenario}")

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-invalid-handoff-1",
            "ranking_artifact_handoff": mutable_preflight["handoff"],
            "current_portfolio": _construction_current_portfolio_payload(),
            **_construction_policy_payload(),
            **_construction_constraints_payload(),
        },
    )

    assert response.status_code == expected_status
    assert expected_detail in response.text

def test_construction_route_accepts_inverse_rank_weight_policy(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-inverse-rank-1",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                    {"symbol": "CCC", "rank": 3, "eligible": True, "score": 0.7},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "policy": {"policy_id": "top_n_inverse_rank_weight_v1", "top_n": 3},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.55,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "feasible"
    assert payload["policy"]["policy_id"] == "top_n_inverse_rank_weight_v1"
    assert payload["normalized_inputs"]["policy_id"] == "top_n_inverse_rank_weight_v1"
    assert payload["final_target_weights"] == [
        {"symbol": "AAA", "weight": 0.54545455},
        {"symbol": "BBB", "weight": 0.27272727},
        {"symbol": "CCC", "weight": 0.18181818},
    ]


def test_construction_route_accepts_linear_rank_weight_policy(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-linear-rank-1",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                    {"symbol": "CCC", "rank": 3, "eligible": True, "score": 0.7},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "policy": {"policy_id": "top_n_linear_rank_weight_v1", "top_n": 3},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.51,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "feasible"
    assert payload["policy"]["policy_id"] == "top_n_linear_rank_weight_v1"
    assert payload["normalized_inputs"]["policy_id"] == "top_n_linear_rank_weight_v1"
    assert payload["normalized_inputs"]["policy_definition_id"] == "construction_policy_definition_top_n_linear_rank_weight_v1"
    assert payload["final_target_weights"] == [
        {"symbol": "AAA", "weight": 0.5},
        {"symbol": "BBB", "weight": 0.33333333},
        {"symbol": "CCC", "weight": 0.16666667},
    ]


def test_construction_route_returns_infeasible_artifact_for_turnover_cap(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-turnover-cap-1",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "BBB", "weight": 0.4},
                    {"symbol": "CCC", "weight": 0.35},
                    {"symbol": "EEE", "weight": 0.25},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
                "max_turnover_weight": 0.59,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "infeasible"
    assert payload["failure_reasons"] == ["target turnover exceeds max_turnover_weight"]
    assert payload["final_target_weights"] == []
    assert next(item for item in payload["constraint_evaluations"] if item["constraint_id"] == "max_turnover_weight") == {
        "constraint_id": "max_turnover_weight",
        "status": "fail",
        "actual_value": 0.6,
        "limit_value": 0.59,
        "message": "portfolio turnover must not exceed max_turnover_weight",
    }


def test_construction_route_returns_infeasible_artifact_for_trade_intent_count_cap(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-trade-intent-cap-1",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "BBB", "weight": 0.4},
                    {"symbol": "CCC", "weight": 0.35},
                    {"symbol": "EEE", "weight": 0.25},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
                "max_trade_intent_count": 3,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "infeasible"
    assert payload["failure_reasons"] == ["trade intent count exceeds max_trade_intent_count"]
    assert payload["trade_intents"] == [
        {"symbol": "AAA", "action": "initiate", "current_weight": 0.0, "target_weight": 0.5, "delta_weight": 0.5},
        {"symbol": "BBB", "action": "buy", "current_weight": 0.4, "target_weight": 0.5, "delta_weight": 0.1},
        {"symbol": "CCC", "action": "exit", "current_weight": 0.35, "target_weight": 0.0, "delta_weight": -0.35},
        {"symbol": "EEE", "action": "exit", "current_weight": 0.25, "target_weight": 0.0, "delta_weight": -0.25},
    ]
    assert next(item for item in payload["constraint_evaluations"] if item["constraint_id"] == "max_trade_intent_count") == {
        "constraint_id": "max_trade_intent_count",
        "status": "fail",
        "actual_value": 4.0,
        "limit_value": 3.0,
        "message": "trade intent count must not exceed max_trade_intent_count",
    }


def test_construction_artifact_route_is_registered(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    run_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-2",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "CCC", "weight": 0.5},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert run_response.status_code == 200
    artifact_id = run_response.json()["artifact_id"]

    response = client.get(f"/construction/artifacts/{artifact_id}")

    assert response.status_code == 200
    assert response.json()["artifact_id"] == artifact_id


def test_construction_policy_catalog_route_returns_shipped_set() -> None:
    client = TestClient(app)

    response = client.get("/construction/policies")

    assert response.status_code == 200
    assert response.json() == [
        {
            "policy_id": "top_n_equal_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
            "name": "Top N Equal Weight v1",
            "description": "Select eligible top-ranked names and assign equal target weights.",
            "family": "top_n_equal_weight",
            "constraints": "long_only_fully_invested_max_position_turnover",
            "inputs": "ranked_universe_and_current_portfolio",
            "determinism": "deterministic_rank_order",
            "ranking_support": "selection_only",
            "full_investment_constraint": "required",
            "long_only_constraint": "required",
            "eligible_ranked_universe_constraint": "required",
            "max_position_weight_constraint": "required",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
            "selection_rule_ids": ["eligible_only", "take_top_n"],
        },
        {
            "policy_id": "top_n_inverse_rank_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_inverse_rank_weight_v1",
            "name": "Top N Inverse Rank Weight v1",
            "description": "Select eligible top-ranked names and weight them by inverse selected-order rank.",
            "family": "top_n_rank_weighted",
            "constraints": "long_only_fully_invested_max_position_turnover",
            "inputs": "ranked_universe_and_current_portfolio",
            "determinism": "deterministic_rank_order",
            "ranking_support": "inverse_selected_order_weighting",
            "full_investment_constraint": "required",
            "long_only_constraint": "required",
            "eligible_ranked_universe_constraint": "required",
            "max_position_weight_constraint": "required",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
            "selection_rule_ids": ["eligible_only", "take_top_n"],
        },
        {
            "policy_id": "top_n_linear_rank_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_linear_rank_weight_v1",
            "name": "Top N Linear Rank Weight v1",
            "description": "Select eligible top-ranked names and weight them by selected-order linear rank numerators N..1.",
            "family": "top_n_rank_weighted",
            "constraints": "long_only_fully_invested_max_position_turnover",
            "inputs": "ranked_universe_and_current_portfolio",
            "determinism": "deterministic_rank_order",
            "ranking_support": "linear_selected_order_weighting",
            "full_investment_constraint": "required",
            "long_only_constraint": "required",
            "eligible_ranked_universe_constraint": "required",
            "max_position_weight_constraint": "required",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
            "selection_rule_ids": ["eligible_only", "take_top_n"],
        },
    ]


@pytest.mark.parametrize(
    ("params", "expected_policy_ids"),
    [
        ({"family": "top_n_rank_weighted"}, ["top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"constraints": "long_only_fully_invested_max_position_turnover"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"inputs": "ranked_universe_and_current_portfolio"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"determinism": "deterministic_rank_order"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"ranking_support": "linear_selected_order_weighting"}, ["top_n_linear_rank_weight_v1"]),
        ({"full_investment_constraint": "required"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"long_only_constraint": "required"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"eligible_ranked_universe_constraint": "required"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"max_position_weight_constraint": "required"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"min_position_weight_constraint": "supported_optional"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"max_turnover_weight_constraint": "supported_optional"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"max_trade_intent_count_constraint": "supported_optional"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"ranked_universe_input": "required"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
        ({"current_portfolio_input": "required"}, ["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1", "top_n_linear_rank_weight_v1"]),
    ],
)
def test_construction_policy_catalog_route_filters_by_each_exact_catalog_metadata_field(params, expected_policy_ids) -> None:
    client = TestClient(app)

    response = client.get("/construction/policies", params=params)

    assert response.status_code == 200
    assert [item["policy_id"] for item in response.json()] == expected_policy_ids


def test_construction_policy_catalog_route_intersects_multiple_exact_filters() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={
            "family": "top_n_rank_weighted",
            "ranking_support": "linear_selected_order_weighting",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
        },
    )

    assert response.status_code == 200
    assert [item["policy_id"] for item in response.json()] == ["top_n_linear_rank_weight_v1"]


def test_construction_policy_catalog_route_rejects_unsupported_filter_key() -> None:
    client = TestClient(app)

    response = client.get("/construction/policies", params={"unsupported_filter": "x"})

    assert response.status_code == 422
    assert response.json() == {
        "detail": "unsupported construction policy filter key(s): unsupported_filter"
    }


def test_construction_policy_catalog_route_rejects_mixed_supported_and_unsupported_filter_keys() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"family": "top_n_equal_weight", "unsupported_filter": "x"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "unsupported construction policy filter key(s): unsupported_filter"
    }


def test_construction_policy_catalog_route_rejects_empty_supported_filter_value() -> None:
    client = TestClient(app)

    response = client.get("/construction/policies?family=")

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'family': ''; supported values: top_n_equal_weight, top_n_rank_weighted"
    }


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("full_investment_constraint", "optional"),
        ("long_only_constraint", "optional"),
        ("eligible_ranked_universe_constraint", "optional"),
        ("max_position_weight_constraint", "optional"),
        ("min_position_weight_constraint", "required"),
        ("max_turnover_weight_constraint", "required"),
        ("max_trade_intent_count_constraint", "required"),
        ("ranked_universe_input", "optional"),
        ("current_portfolio_input", "optional"),
    ],
)
def test_construction_policy_catalog_route_rejects_invalid_typed_filter_values(field_name: str, value: str) -> None:
    client = TestClient(app)

    response = client.get("/construction/policies", params={field_name: value})

    assert response.status_code == 422


def test_construction_policy_catalog_route_rejects_malformed_typed_filter_value() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"max_turnover_weight_constraint": " supported_optional "},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'max_turnover_weight_constraint': ' supported_optional '; supported values: supported_optional"
    }


def test_construction_policy_catalog_route_rejects_malformed_min_position_weight_filter_value() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"min_position_weight_constraint": " supported_optional "},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'min_position_weight_constraint': ' supported_optional '; supported values: supported_optional"
    }


def test_construction_policy_catalog_route_rejects_malformed_max_trade_intent_count_filter_value() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"max_trade_intent_count_constraint": " supported_optional "},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'max_trade_intent_count_constraint': ' supported_optional '; supported values: supported_optional"
    }


def test_construction_policy_catalog_route_rejects_repeated_filter_when_any_raw_value_is_malformed() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies?family=bogus&family=top_n_equal_weight"
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'family': 'bogus'; supported values: top_n_equal_weight, top_n_rank_weighted"
    }


def test_construction_policy_catalog_route_rejects_repeated_filter_when_all_raw_values_are_valid() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies?family=top_n_equal_weight&family=top_n_rank_weighted"
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "repeated construction policy filter key(s): family"
    }


def test_construction_policy_catalog_route_rejects_repeated_filter_when_repeated_values_are_identical() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies?ranking_support=selection_only&ranking_support=selection_only"
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "repeated construction policy filter key(s): ranking_support"
    }


def test_construction_route_treats_missing_and_explicit_null_turnover_caps_the_same(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    omitted_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-turnover-omitted",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    null_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-turnover-null",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
                "max_turnover_weight": None,
            },
        },
    )

    assert omitted_response.status_code == 200
    assert null_response.status_code == 200
    omitted_payload = omitted_response.json()
    null_payload = null_response.json()
    assert omitted_payload["policy"] == null_payload["policy"]
    assert omitted_payload["hard_constraints"] == null_payload["hard_constraints"]
    assert omitted_payload["normalized_inputs"] == null_payload["normalized_inputs"]
    assert omitted_payload["selected_names"] == null_payload["selected_names"]
    assert omitted_payload["final_target_weights"] == null_payload["final_target_weights"]
    assert omitted_payload["trade_intents"] == null_payload["trade_intents"]
    assert omitted_payload["failure_reasons"] == null_payload["failure_reasons"]
    assert next(item for item in omitted_payload["constraint_evaluations"] if item["constraint_id"] == "max_turnover_weight") == {
        "constraint_id": "max_turnover_weight",
        "status": "not_evaluated",
        "actual_value": None,
        "limit_value": None,
        "message": "max_turnover_weight was not requested",
    }
    assert next(item for item in null_payload["constraint_evaluations"] if item["constraint_id"] == "max_turnover_weight") == {
        "constraint_id": "max_turnover_weight",
        "status": "not_evaluated",
        "actual_value": None,
        "limit_value": None,
        "message": "max_turnover_weight was not requested",
    }


def test_construction_route_keeps_zero_turnover_cap_as_real_constraint(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-route-zero-cap",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "BBB", "weight": 0.4},
                    {"symbol": "CCC", "weight": 0.35},
                    {"symbol": "EEE", "weight": 0.25},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
                "max_turnover_weight": 0.0,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "infeasible"
    assert payload["failure_reasons"] == ["target turnover exceeds max_turnover_weight"]
    assert next(item for item in payload["constraint_evaluations"] if item["constraint_id"] == "max_turnover_weight") == {
        "constraint_id": "max_turnover_weight",
        "status": "fail",
        "actual_value": 0.6,
        "limit_value": 0.0,
        "message": "portfolio turnover must not exceed max_turnover_weight",
    }


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


def test_optimizer_preview_route_returns_hypothetical_preview_contract() -> None:
    client = TestClient(app)

    response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-1",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-04-15", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-04-15", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-12-31T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["optimizer_status"] == "feasible"
    assert payload["optimizer_artifact"]["objective"]["objective_id"] == "minimize_l2_distance_to_benchmark"
    assert payload["truth_separation"] == {
        "current_holdings_truth": "imported_portfolio_snapshot",
        "optimized_output_truth": "hypothetical_optimizer_preview",
        "optimized_output_applied": False,
        "optimized_output_storage": "optimizer_artifact_only",
        "replay_role": "downstream_evaluation_only",
    }
    assert payload["provenance"]["benchmark_trust_status"] == "trusted"
    assert payload["provenance"]["return_basis_attestation"]["benchmark_symbol"] == "SPY"
    assert payload["persisted_handoff"]["reference_kind"] == "optimizer_handoff_reference_v1"
    assert payload["persisted_handoff"]["handoff_id"].startswith("optimizer_handoff_")
    assert payload["optimizer_artifact"]["benchmark_id"] == "benchmark_spy_demo_v1"
    assert payload["replay_handoff"]["status"] == "hypothetical_not_applied"
    assert payload["replay_handoff"]["handoff_reference"] == payload["persisted_handoff"]
    assert payload["replay_handoff"]["benchmark_version"] == "2024-04-15"


def test_optimizer_preview_to_handoff_replay_routes_preserve_canonical_benchmark_symbol(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "CCC": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 104.0},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 109.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.3},
            {"date": "2024-06-03", "price": 101.8},
            {"date": "2024-12-31", "price": 104.5},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.0},
            {"date": "2024-02-01", "price": 98.7},
            {"date": "2024-06-03", "price": 99.8},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 103.2},
            {"date": "2024-06-03", "price": 104.0},
            {"date": "2024-12-31", "price": 107.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.1},
            {"date": "2024-12-31", "price": 103.5},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 97.0},
            {"date": "2024-02-01", "price": 97.2},
            {"date": "2024-06-03", "price": 98.5},
            {"date": "2024-12-31", "price": 101.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.4},
            {"date": "2024-06-03", "price": 103.2},
            {"date": "2024-12-31", "price": 105.2},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.4},
            {"date": "2024-02-01", "price": 100.5},
            {"date": "2024-06-03", "price": 100.6},
            {"date": "2024-12-31", "price": 101.2},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.5},
            {"date": "2024-02-01", "price": 99.0},
            {"date": "2024-06-03", "price": 101.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.8},
            {"date": "2024-02-01", "price": 100.9},
            {"date": "2024-06-03", "price": 101.2},
            {"date": "2024-12-31", "price": 102.3},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.8},
            {"date": "2024-12-31", "price": 104.1},
        ],
    }
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-canonical-benchmark",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-01-01", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-01-01", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": " spy ",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-12-31T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["replay_handoff"]["benchmark_symbol"] == "SPY"
    assert preview_payload["persisted_handoff"] is not None

    replay_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": preview_payload["persisted_handoff"],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["replay_provenance"]["benchmark_symbol"] == "SPY"
    assert replay_payload["replay_provenance"]["return_basis_attestation"]["benchmark_symbol"] == "SPY"
    assert replay_payload["replay_provenance"]["replay_output_policy"] == {
        "source": "persisted_return_basis_attestation",
        "section_trust": {
            "benchmark_relative_path": "degraded_unverified_return_basis",
            "factor_model_path": "degraded_unverified_return_basis",
            "risk_contribution_path": "degraded_unverified_return_basis",
        },
        "eligible_families": [],
        "withheld_families": [
            "benchmark_relative_volatility_outputs",
            "factor_exposure_outputs",
            "stress_scenario_outputs",
            "risk_contribution_outputs",
            "concentration_outputs",
        ],
    }
    assert replay_payload["replay"]["reference_result"]["metrics"]["tracking_error_pct"] is None
    assert replay_payload["replay"]["reference_result"]["metrics"]["beta_vs_benchmark"] is None
    assert replay_payload["replay"]["reference_result"]["metrics"]["correlation_vs_benchmark"] is None
    assert replay_payload["replay"]["candidate_result"]["metrics"]["tracking_error_pct"] is None
    assert replay_payload["replay"]["candidate_result"]["metrics"]["beta_vs_benchmark"] is None
    assert replay_payload["replay"]["candidate_result"]["metrics"]["correlation_vs_benchmark"] is None
    assert replay_payload["replay"]["comparison"]["tracking_error_diff_pct"] is None
    assert replay_payload["replay"]["comparison"]["beta_diff"] is None
    assert replay_payload["replay"]["comparison"]["correlation_diff"] is None
    assert "objective_id" not in replay_payload["optimizer_context"]
    assert replay_payload["optimizer_context"]["objective"]["objective_id"] == "minimize_l2_distance_to_benchmark"


def test_optimizer_handoff_routes_preserve_alpha_objective_contract_over_http(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _optimizer_handoff_replay_histories()
    mocker.patch(
        "app.services.optimizer_preview_service.assemble_optimizer_request_with_trusted_pit_alpha",
        side_effect=lambda request, **_: request.model_copy(update={"alpha_package": _optimizer_alpha_package()}),
    )
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json=_optimizer_preview_payload(objective_id="maximize_alpha_quality_v1", include_pit_alpha=True),
    )

    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    assert preview_payload["optimizer_artifact"]["objective"]["objective_id"] == "maximize_alpha_quality_v1"
    assert preview_payload["provenance"]["alpha_input_status"] == "trusted_pit_attached"
    persisted_handoff = preview_payload["persisted_handoff"]
    assert persisted_handoff is not None

    validation_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={"handoff_reference": persisted_handoff},
    )
    replay_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": persisted_handoff,
            "start_date": "2024-04-15",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert validation_response.status_code == 200
    validation_payload = validation_response.json()
    assert validation_payload["provenance"]["objective"] == {
        "objective_id": "maximize_alpha_quality_v1",
        "benchmark_relative": True,
        "description": "Maximize the additive alpha_quality_v1 preference vector inside the unchanged hard-constraint set.",
        "alpha_signal_id": "alpha_quality_v1",
        "requires_alpha_package": True,
    }
    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert "objective_id" not in replay_payload["optimizer_context"]
    assert replay_payload["optimizer_context"]["objective"] == validation_payload["provenance"]["objective"]


def test_optimizer_preview_route_fails_closed_for_alpha_objective_without_required_alpha_inputs() -> None:
    client = TestClient(app)

    response = client.post(
        "/optimizer/preview",
        json=_optimizer_preview_payload(objective_id="maximize_alpha_quality_v1"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["optimizer_status"] == "rejected"
    assert payload["optimizer_artifact"]["objective"]["objective_id"] == "maximize_alpha_quality_v1"
    assert payload["feasibility"]["issues"][0]["code"] == "missing_alpha_package"
    assert payload["persisted_handoff"] is None
    assert payload["replay_handoff"] is None


def test_optimizer_preview_route_fails_closed_for_alpha_objective_when_trusted_pit_alpha_is_unavailable() -> None:
    client = TestClient(app)

    response = client.post(
        "/optimizer/preview",
        json=_optimizer_preview_payload(objective_id="maximize_alpha_quality_v1", include_pit_alpha=True),
    )

    assert response.status_code == 400
    assert "ineligible optimizer symbols" in response.json()["detail"]


def test_optimizer_handoff_constraints_route_returns_handoff_authority_when_reference_artifact_mismatches(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "CCC": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 104.0},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 109.0},
        ],
    }
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-reference-artifact-mismatch",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-01-01", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-01-01", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-12-31T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    persisted_handoff = preview_response.json()["persisted_handoff"]
    assert persisted_handoff is not None
    response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": {
                **persisted_handoff,
                "artifact_id": "opt_artifact_wrong",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_status"] == "blocked"
    assert payload["handoff_id"] == persisted_handoff["handoff_id"]
    assert payload["artifact_id"] == persisted_handoff["artifact_id"]
    assert "artifact_reference_matches_artifact" in payload["blocking_rule_ids"]
    assert payload["replay_handoff"] is None


def test_construction_artifact_replay_route_uses_explicit_reference_only_lineage(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "QQQ": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 104.0},
            {"date": "2024-02-01", "price": 104.5},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 112.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.3},
            {"date": "2024-06-03", "price": 101.8},
            {"date": "2024-12-31", "price": 104.5},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.0},
            {"date": "2024-02-01", "price": 98.7},
            {"date": "2024-06-03", "price": 99.8},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 103.2},
            {"date": "2024-06-03", "price": 104.0},
            {"date": "2024-12-31", "price": 107.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.1},
            {"date": "2024-12-31", "price": 103.5},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 97.0},
            {"date": "2024-02-01", "price": 97.2},
            {"date": "2024-06-03", "price": 98.5},
            {"date": "2024-12-31", "price": 101.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.4},
            {"date": "2024-06-03", "price": 103.2},
            {"date": "2024-12-31", "price": 105.2},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.4},
            {"date": "2024-02-01", "price": 100.5},
            {"date": "2024-06-03", "price": 100.6},
            {"date": "2024-12-31", "price": 101.2},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.5},
            {"date": "2024-02-01", "price": 99.0},
            {"date": "2024-06-03", "price": 101.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.8},
            {"date": "2024-02-01", "price": 100.9},
            {"date": "2024-06-03", "price": 101.2},
            {"date": "2024-12-31", "price": 102.3},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.8},
            {"date": "2024-12-31", "price": 104.1},
        ],
    }
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-1",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]

    replay_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={"construction_artifact_id": artifact_id},
    )

    assert replay_response.status_code == 200
    payload = replay_response.json()
    assert payload["construction_artifact_id"] == artifact_id
    assert payload["truth_separation"] == {
        "baseline_truth": "imported_portfolio_snapshot",
        "candidate_truth": "hypothetical_construction_artifact",
        "candidate_applied": False,
        "consumption_mode": "explicit_reference_only",
    }
    assert payload["replay_provenance"] == {
        "source": "construction_artifact_reference",
        "construction_artifact_id": artifact_id,
        "policy_id": "top_n_equal_weight_v1",
        "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
        "ranked_universe_artifact_id": "ranking_artifact_1",
        "ranking_id": "ranked_candidates_v1",
        "ranking_methodology_id": "ranked_candidates_methodology_v1",
        "current_portfolio_artifact_id": "portfolio_snapshot_1",
        "hard_constraints": construction_response.json()["hard_constraints"],
        "baseline_input_source": "normalized_inputs.current_portfolio_weights",
        "candidate_input_source": "final_target_weights",
        "selection_rule_trace": {
            "rule_ids": ["eligible_only", "take_top_n"],
            "steps": [
                {
                    "rule_id": "eligible_only",
                    "rule_order": 1,
                    "input_candidate_symbols": ["AAA", "BBB"],
                    "output_candidate_symbols": ["AAA", "BBB"],
                },
                {
                    "rule_id": "take_top_n",
                    "rule_order": 2,
                    "input_candidate_symbols": ["AAA", "BBB"],
                    "output_candidate_symbols": ["AAA", "BBB"],
                },
            ],
        },
        "turnover_diagnostics_status": "available",
        "turnover_diagnostics_v1": construction_response.json()["turnover_diagnostics_v1"],
        "weighting_trace_status": "available",
        "weighting_trace_v1": construction_response.json()["weighting_trace_v1"],
    }
    assert payload["baseline_weights"] == [
        {"symbol": "AAA", "target_weight": 0.6},
        {"symbol": "BBB", "target_weight": 0.4},
    ]
    assert payload["candidate_weights"] == [
        {"symbol": "AAA", "target_weight": 0.5},
        {"symbol": "BBB", "target_weight": 0.5},
    ]
    assert payload["review_basis"] == {
        "basis_version": 1,
        "basis_kind": "persisted_construction_artifact_review",
        "review_scope": "workspace_review_only",
        "canonical_source": "typed_preview_handoff",
        "basis_provenance_label": "artifact_backed_review_basis",
        "portfolio_truth": "imported_portfolio_snapshot",
        "candidate_truth": "hypothetical_construction_artifact",
        "construction_artifact_id": artifact_id,
        "preview_handoff": {
            "handoff_kind": "construction_artifact_preview_handoff_v1",
            "construction_artifact_id": artifact_id,
            "effective_replay_params": payload["effective_replay_params"],
        },
        "benchmark_symbol": "SPY",
        "base_currency": "USD",
        "replay_window": {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        },
        "baseline_weights": payload["baseline_weights"],
        "candidate_weights": payload["candidate_weights"],
    }
    assert payload["effective_replay_params"] == {
        "benchmark_symbol": "SPY",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000.0,
        "rebalance_frequency": "monthly",
        "base_currency": "USD",
        "commission_bps": 0.0,
        "slippage_bps": 0.0,
        "drift_tolerance_pct": None,
        "price_basis": "adjusted_close",
        "execution_price_field": "close",
        "execution_lag_days": 1,
        "symbol_overrides": {},
    }
    assert payload["replay"]["methodology_provenance"] == {
        "provenance_version": 1,
        "source": "portfolio_allocation_backtest_engine",
        "methodology_truth": "review_only_replay_methodology",
        "assumptions_truth": "review_only_replay_assumptions",
        "analytics_truth": "hypothetical_replay_analytics_only",
        "review_scope": "workspace_review_context_only",
    }
    assert payload["replay"]["reference_result"] is not None


def test_construction_artifact_replay_route_uses_persisted_inverse_rank_weights(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "CCC": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.2},
            {"date": "2024-02-01", "price": 100.8},
            {"date": "2024-06-03", "price": 101.4},
            {"date": "2024-12-31", "price": 101.9},
        ],
        "QQQ": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 104.0},
            {"date": "2024-02-01", "price": 104.5},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 112.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.3},
            {"date": "2024-06-03", "price": 101.8},
            {"date": "2024-12-31", "price": 104.5},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.0},
            {"date": "2024-02-01", "price": 98.7},
            {"date": "2024-06-03", "price": 99.8},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 103.2},
            {"date": "2024-06-03", "price": 104.0},
            {"date": "2024-12-31", "price": 107.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.1},
            {"date": "2024-12-31", "price": 103.5},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 97.0},
            {"date": "2024-02-01", "price": 97.2},
            {"date": "2024-06-03", "price": 98.5},
            {"date": "2024-12-31", "price": 101.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.4},
            {"date": "2024-06-03", "price": 103.2},
            {"date": "2024-12-31", "price": 105.2},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.4},
            {"date": "2024-02-01", "price": 100.5},
            {"date": "2024-06-03", "price": 100.6},
            {"date": "2024-12-31", "price": 101.2},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.5},
            {"date": "2024-02-01", "price": 99.0},
            {"date": "2024-06-03", "price": 101.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.8},
            {"date": "2024-02-01", "price": 100.9},
            {"date": "2024-06-03", "price": 101.2},
            {"date": "2024-12-31", "price": 102.3},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.8},
            {"date": "2024-12-31", "price": 104.1},
        ],
    }
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-inverse-rank",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                    {"symbol": "CCC", "rank": 3, "eligible": True, "score": 0.7},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "policy": {"policy_id": "top_n_inverse_rank_weight_v1", "top_n": 3},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.55,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]

    replay_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "benchmark_symbol": "QQQ",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
            "initial_capital": 250000,
            "rebalance_frequency": "quarterly",
            "base_currency": "EUR",
            "commission_bps": 4.5,
            "slippage_bps": 6.5,
            "drift_tolerance_pct": 2.0,
            "execution_lag_days": 3,
            "symbol_overrides": {"AAA": ["QQQ"]},
        },
    )

    assert replay_response.status_code == 200
    payload = replay_response.json()
    assert payload["replay_provenance"]["policy_id"] == "top_n_inverse_rank_weight_v1"
    assert payload["replay_provenance"]["turnover_diagnostics_status"] == "available"
    assert payload["replay_provenance"]["turnover_diagnostics_v1"] == construction_response.json()["turnover_diagnostics_v1"]
    assert payload["replay_provenance"]["weighting_trace_status"] == construction_response.json()["weighting_trace_status"]
    assert payload["replay_provenance"]["weighting_trace_v1"] == construction_response.json()["weighting_trace_v1"]
    assert payload["effective_replay_params"] == {
        "benchmark_symbol": "QQQ",
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "initial_capital": 250000.0,
        "rebalance_frequency": "quarterly",
        "base_currency": "EUR",
        "commission_bps": 4.5,
        "slippage_bps": 6.5,
        "drift_tolerance_pct": 2.0,
        "price_basis": "adjusted_close",
        "execution_price_field": "close",
        "execution_lag_days": 3,
        "symbol_overrides": {"AAA": ["QQQ"]},
    }
    assert payload["candidate_weights"] == [
        {"symbol": "AAA", "target_weight": 0.54545455},
        {"symbol": "BBB", "target_weight": 0.27272727},
        {"symbol": "CCC", "target_weight": 0.18181818},
    ]


@pytest.mark.parametrize(
    "payload_mutator",
    [
        lambda payload: payload.pop("weighting_trace_status"),
        lambda payload: payload.pop("weighting_trace_v1"),
        lambda payload: payload["weighting_trace_v1"].__setitem__("trace_version", "weighting_trace_v0"),
        lambda payload: payload["weighting_trace_v1"]["stages"][1].__setitem__(
            "positions",
            payload["weighting_trace_v1"]["stages"][1]["positions"][:-1],
        ),
        lambda payload: payload.__setitem__("weighting_trace_status", "unavailable_legacy_artifact"),
    ],
    ids=[
        "missing_status",
        "missing_body",
        "unsupported_version",
        "partial_payload",
        "status_body_contradiction",
    ],
)
def test_construction_artifact_replay_route_rejects_invalid_persisted_weighting_trace_provenance(
    tmp_path,
    mocker,
    payload_mutator,
) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-invalid-weighting-trace",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = _rekey_construction_artifact_payload(
        tmp_path,
        construction_response.json()["artifact_id"],
        payload_mutator,
    )

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert "persisted construction artifact failed schema validation" in response.json()["detail"]


def test_construction_artifact_replay_route_rejects_missing_inline_weight_contract(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": "construction_artifact_1234567890abcdef",
            "weights": [{"symbol": "AAA", "target_weight": 1.0}],
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 422


def test_construction_artifact_validation_route_resolves_omitted_defaults_without_market_data(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-validation-route-defaults",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload(artifact_id),
    )

    assert response.status_code == 200
    assert response.json() == {
        "construction_artifact_id": artifact_id,
        "effective_replay_params": {
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000.0,
            "rebalance_frequency": "monthly",
            "base_currency": "USD",
            "commission_bps": 0.0,
            "slippage_bps": 0.0,
            "drift_tolerance_pct": None,
            "price_basis": "adjusted_close",
            "execution_price_field": "close",
            "execution_lag_days": 1,
            "symbol_overrides": {},
        },
        "preview_handoff": {
            "handoff_kind": "construction_artifact_preview_handoff_v1",
            "construction_artifact_id": artifact_id,
            "effective_replay_params": {
                "benchmark_symbol": "SPY",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000.0,
                "rebalance_frequency": "monthly",
                "base_currency": "USD",
                "commission_bps": 0.0,
                "slippage_bps": 0.0,
                "drift_tolerance_pct": None,
                "price_basis": "adjusted_close",
                "execution_price_field": "close",
                "execution_lag_days": 1,
                "symbol_overrides": {},
            },
        },
        "open_payload": None,
    }
    mock_service.return_value.get_historical_prices.assert_not_called()
    mock_service.return_value.get_historical_prices_for_symbols.assert_not_called()


def test_construction_artifact_validation_route_prefers_explicit_overrides_and_matches_preview_effective_params(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-validation-route-overrides",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    payload = _construction_artifact_validation_payload(
        artifact_id,
        benchmark_symbol="QQQ",
        start_date="2023-01-01",
        end_date="2023-12-31",
        initial_capital=250000,
        rebalance_frequency="quarterly",
        base_currency="EUR",
        commission_bps=4.5,
        slippage_bps=6.5,
        drift_tolerance_pct=2.0,
        execution_lag_days=3,
        symbol_overrides={"AAA": ["QQQ"]},
    )

    validation_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=payload,
    )
    preview_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=payload,
    )

    assert validation_response.status_code == 200
    assert preview_response.status_code == 200
    assert validation_response.json() == {
        "construction_artifact_id": artifact_id,
        "effective_replay_params": preview_response.json()["effective_replay_params"],
        "preview_handoff": {
            "handoff_kind": "construction_artifact_preview_handoff_v1",
            "construction_artifact_id": artifact_id,
            "effective_replay_params": preview_response.json()["effective_replay_params"],
        },
        "open_payload": None,
    }


def test_construction_artifact_min_position_weight_survives_run_load_validation_and_preview_unchanged(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    run_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-min-position-handoff-roundtrip",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": _construction_current_portfolio_payload(),
            **_construction_policy_payload(),
            **_construction_constraints_payload_with_min_position_weight(0.5),
        },
    )

    assert run_response.status_code == 200
    artifact_id = run_response.json()["artifact_id"]
    get_response = client.get(f"/construction/artifacts/{artifact_id}")
    validation_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload(artifact_id),
    )
    preview_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=validation_response.json()["preview_handoff"],
    )

    assert get_response.status_code == 200
    assert validation_response.status_code == 200
    assert preview_response.status_code == 400
    assert run_response.json()["hard_constraints"]["min_position_weight"] == 0.5
    assert run_response.json()["normalized_inputs"]["min_position_weight"] == 0.5
    assert get_response.json()["hard_constraints"]["min_position_weight"] == 0.5
    assert get_response.json()["normalized_inputs"]["min_position_weight"] == 0.5
    assert preview_response.json()["detail"] == "No historical prices found for symbol: CCC"


def test_construction_artifact_preview_route_accepts_validation_preview_handoff_verbatim(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-preview-route-verbatim-handoff",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    validation_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload(
            artifact_id,
            benchmark_symbol="QQQ",
            start_date="2023-01-01",
            end_date="2023-12-31",
            initial_capital=250000,
            rebalance_frequency="quarterly",
            base_currency="EUR",
            commission_bps=4.5,
            slippage_bps=6.5,
            drift_tolerance_pct=2.0,
            execution_lag_days=3,
            symbol_overrides={"AAA": ["QQQ"]},
        ),
    )

    assert validation_response.status_code == 200
    preview_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=validation_response.json()["preview_handoff"],
    )

    assert preview_response.status_code == 200
    assert preview_response.json()["effective_replay_params"] == validation_response.json()["preview_handoff"]["effective_replay_params"]
    assert preview_response.json()["construction_artifact_id"] == artifact_id


def test_construction_artifact_preview_route_rejects_unsupported_handoff_kind(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            **_construction_artifact_preview_handoff_payload("construction_artifact_1234567890abcdef"),
            "handoff_kind": "construction_artifact_preview_handoff_v0",
        },
    )

    assert response.status_code == 422


def test_construction_artifact_preview_route_rejects_missing_handoff_kind_on_handoff_shape(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    handoff_payload = _construction_artifact_preview_handoff_payload("construction_artifact_1234567890abcdef")
    handoff_payload.pop("handoff_kind")
    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=handoff_payload,
    )

    assert response.status_code == 422


def test_construction_artifact_preview_route_rejects_mixed_handoff_and_legacy_fields(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            **_construction_artifact_preview_handoff_payload("construction_artifact_1234567890abcdef"),
            "benchmark_symbol": "QQQ",
        },
    )

    assert response.status_code == 422


def test_construction_artifact_preview_route_rejects_handoff_artifact_mismatch_against_persisted_content(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-preview-route-handoff-mismatch",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "construction_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=_construction_artifact_preview_handoff_payload(artifact_id),
    )

    assert response.status_code == 400
    assert "construction artifact_id does not match canonical artifact content" in response.json()["detail"]


def test_construction_artifact_validation_route_rejects_invalid_resolved_combinations_without_market_data(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-validation-route-invalid",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload(
            artifact_id,
            start_date="2024-12-31",
            end_date="2024-01-01",
        ),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "end_date must be on or after start_date"
    mock_service.return_value.get_historical_prices.assert_not_called()
    mock_service.return_value.get_historical_prices_for_symbols.assert_not_called()


def test_construction_artifact_validation_route_returns_404_for_missing_artifact(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload("construction_artifact_missing"),
    )

    assert response.status_code == 404
    assert "missing persisted construction artifact file" in response.json()["detail"]


def test_construction_artifact_validation_route_returns_400_for_integrity_validation_failure(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-validation-route-integrity",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "construction_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload(artifact_id),
    )

    assert response.status_code == 400
    assert "construction artifact_id does not match canonical artifact content" in response.json()["detail"]


def test_review_snapshot_routes_create_open_and_compare_roundtrip(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    baseline_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    candidate_payload = _review_snapshot_create_request("IUFS")
    candidate_payload["proposal_id"] = "proposal-IUFS-v2"
    candidate_payload["version_number"] = 2
    candidate_create = client.post(
        "/backtests/review-snapshots",
        json=candidate_payload,
    )

    assert baseline_create.status_code == 200
    assert candidate_create.status_code == 200
    baseline_artifact = baseline_create.json()
    candidate_artifact = candidate_create.json()

    open_response = client.post(
        "/backtests/review-snapshots/open",
        json=_review_snapshot_open_handoff_payload(baseline_artifact["identity"]["artifact_id"]),
    )
    family_review_response = client.post(
        "/backtests/review-snapshots/family-review",
        json=_review_snapshot_family_review_payload(baseline_artifact["identity"]["artifact_id"]),
    )
    compare_response = client.post(
        "/backtests/review-snapshots/compare",
        json={
            "baseline": _review_snapshot_comparison_ref_payload("baseline", baseline_artifact["identity"]["artifact_id"]),
            "candidate": _review_snapshot_comparison_ref_payload("candidate", candidate_artifact["identity"]["artifact_id"]),
        },
    )

    assert open_response.status_code == 200
    assert open_response.json()["artifact"]["identity"]["artifact_id"] == baseline_artifact["identity"]["artifact_id"]
    assert open_response.json()["handoff"] == baseline_artifact["proposal_capture"]["open_handoff"]
    assert open_response.json()["pm_summary"]["role"] == "saved_proposal"
    assert open_response.json()["replay_payload"] == baseline_artifact["source_payload"]
    assert baseline_artifact["proposal_capture"]["capture_kind"] == "workspace_review_saved_proposal"
    assert baseline_artifact["proposal_capture"]["open_handoff"]["artifact_id"] == baseline_artifact["identity"]["artifact_id"]

    assert family_review_response.status_code == 200
    assert family_review_response.json()["review_kind"] == "review_snapshot_family_review"
    assert family_review_response.json()["family_key"]["proposal_family_id"] == baseline_artifact["lineage"]["proposal_family_id"]
    assert family_review_response.json()["anchor"]["identity"]["artifact_id"] == baseline_artifact["identity"]["artifact_id"]
    assert {row["identity"]["artifact_id"] for row in family_review_response.json()["siblings"]} == {
        baseline_artifact["identity"]["artifact_id"],
        candidate_artifact["identity"]["artifact_id"],
    }

    assert compare_response.status_code == 200
    assert compare_response.json()["provenance"] == "persisted_review_snapshot_artifacts_only"
    assert compare_response.json()["family_key"]["proposal_family_id"] == baseline_artifact["lineage"]["proposal_family_id"]
    assert compare_response.json()["baseline_pm_summary"]["role"] == "baseline"
    assert compare_response.json()["candidate_pm_summary"]["role"] == "candidate"
    assert compare_response.json()["baseline"]["source_pair"] == "AAPL -> IUFS"
    assert compare_response.json()["candidate"]["source_pair"] == "AAPL -> IUFS"


def test_review_snapshot_open_route_fails_closed_on_identity_mismatch(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    create_response = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    assert create_response.status_code == 200
    artifact = create_response.json()

    open_response = client.post(
        "/backtests/review-snapshots/open",
        json=_review_snapshot_open_handoff_payload(
            artifact["identity"]["artifact_id"],
            schema_version="review_snapshot_artifact_v0",
        ),
    )

    assert open_response.status_code == 422


def test_review_snapshot_compare_route_rejects_incompatible_pair(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    baseline_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    incompatible_payload = _review_snapshot_create_request("IUFS")
    incompatible_payload["proposal_id"] = "proposal-IUFS-v2"
    incompatible_payload["version_number"] = 2
    incompatible_review_payload = cast(dict[str, object], incompatible_payload["review_payload"])
    incompatible_replay = cast(dict[str, object], incompatible_review_payload["replay"])
    incompatible_candidate_result = cast(dict[str, object], incompatible_replay["candidate_result"])
    incompatible_assumptions = cast(dict[str, object], incompatible_candidate_result["assumptions"])
    incompatible_candidate_result["assumptions"] = {
        **incompatible_assumptions,
        "execution_lag_days": 3,
    }
    incompatible_create = client.post(
        "/backtests/review-snapshots",
        json=incompatible_payload,
    )

    assert baseline_create.status_code == 200
    assert incompatible_create.status_code == 200
    baseline_artifact = baseline_create.json()
    incompatible_artifact = incompatible_create.json()

    compare_response = client.post(
        "/backtests/review-snapshots/compare",
        json={
            "baseline": _review_snapshot_comparison_ref_payload("baseline", baseline_artifact["identity"]["artifact_id"]),
            "candidate": _review_snapshot_comparison_ref_payload("candidate", incompatible_artifact["identity"]["artifact_id"]),
        },
    )

    assert compare_response.status_code == 400
    assert compare_response.json()["detail"] == "review snapshot comparison requires matching replay assumptions"


def test_review_snapshot_family_review_route_discovers_family_siblings_only(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    anchor_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    sibling_payload = _review_snapshot_create_request("IUFS")
    sibling_payload["proposal_id"] = "proposal-IUFS-v2"
    sibling_payload["version_number"] = 2
    sibling_create = client.post(
        "/backtests/review-snapshots",
        json=sibling_payload,
    )
    other_family_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUIT"),
    )

    assert anchor_create.status_code == 200
    assert sibling_create.status_code == 200
    assert other_family_create.status_code == 200
    anchor_artifact = anchor_create.json()
    sibling_artifact = sibling_create.json()
    other_family_artifact = other_family_create.json()

    family_review_response = client.post(
        "/backtests/review-snapshots/family-review",
        json=_review_snapshot_family_review_payload(anchor_artifact["identity"]["artifact_id"]),
    )

    assert family_review_response.status_code == 200
    assert family_review_response.json()["family_key"]["proposal_family_id"] == anchor_artifact["lineage"]["proposal_family_id"]
    assert [row["identity"]["artifact_id"] for row in family_review_response.json()["siblings"]] == [
        sibling_artifact["identity"]["artifact_id"],
        anchor_artifact["identity"]["artifact_id"],
    ]
    assert other_family_artifact["identity"]["artifact_id"] not in [row["identity"]["artifact_id"] for row in family_review_response.json()["siblings"]]


def test_review_snapshot_family_inbox_route_returns_newest_first_rows_and_compare_readiness(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    baseline_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    candidate_payload = _review_snapshot_create_request("IUFS")
    candidate_payload["proposal_id"] = "proposal-IUFS-v2"
    candidate_payload["version_number"] = 2
    candidate_create = client.post(
        "/backtests/review-snapshots",
        json=candidate_payload,
    )
    other_family_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUIT"),
    )

    assert baseline_create.status_code == 200
    assert candidate_create.status_code == 200
    assert other_family_create.status_code == 200
    baseline_artifact = baseline_create.json()
    candidate_artifact = candidate_create.json()
    other_family_artifact = other_family_create.json()

    baseline_path = tmp_path / f"{baseline_artifact['identity']['artifact_id']}.json"
    candidate_path = tmp_path / f"{candidate_artifact['identity']['artifact_id']}.json"
    other_family_path = tmp_path / f"{other_family_artifact['identity']['artifact_id']}.json"
    older_time = datetime(2026, 4, 15, 0, 5, tzinfo=UTC).timestamp()
    newer_time = datetime(2026, 4, 16, 0, 5, tzinfo=UTC).timestamp()
    other_time = datetime(2026, 4, 14, 0, 5, tzinfo=UTC).timestamp()
    os.utime(baseline_path, (older_time, older_time))
    os.utime(candidate_path, (newer_time, newer_time))
    os.utime(other_family_path, (other_time, other_time))

    inbox_response = client.post(
        "/backtests/review-snapshots/family-inbox",
        json=_review_snapshot_family_inbox_payload(),
    )

    assert inbox_response.status_code == 200
    assert inbox_response.json()["inbox_kind"] == "review_snapshot_family_inbox"
    assert inbox_response.json()["workspace_id"] == "workspace-1"
    assert [row["family_key"]["proposal_family_id"] for row in inbox_response.json()["rows"]] == [
        candidate_artifact["lineage"]["proposal_family_id"],
        other_family_artifact["lineage"]["proposal_family_id"],
    ]
    assert inbox_response.json()["rows"][0]["latest_identity"]["artifact_id"] == candidate_artifact["identity"]["artifact_id"]
    assert inbox_response.json()["rows"][0]["proposal_capture"]["open_handoff"]["artifact_id"] == candidate_artifact["identity"]["artifact_id"]
    assert inbox_response.json()["rows"][0]["pm_summary"] == candidate_artifact["pm_summary"]
    assert inbox_response.json()["rows"][0]["sibling_count"] == 2
    assert inbox_response.json()["rows"][0]["compare_readiness"] == {
        "ready": True,
        "reason": "compatible_family_pair_available",
        "compatible_pair_count": 1,
    }
    assert inbox_response.json()["rows"][0]["latest_saved_at"] == "2026-04-16T00:05:00Z"


def test_review_snapshot_active_thesis_cross_family_queue_route_returns_metadata_only(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    active_payload = _review_snapshot_create_request("IUFS")
    active_payload["proposal_id"] = "proposal-thesis"
    active_payload["proposal_family_id"] = "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z"
    active_payload["version_number"] = 4
    active_create = client.post("/backtests/review-snapshots", json=active_payload)

    first_payload = _review_snapshot_create_request("IUIT")
    first_payload["proposal_id"] = "proposal-iuit"
    first_payload["proposal_family_id"] = "etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z"
    first_create = client.post("/backtests/review-snapshots", json=first_payload)

    second_payload = _review_snapshot_create_request("IVV")
    second_payload["proposal_id"] = "proposal-ivv"
    second_payload["proposal_family_id"] = "etf_replacement_intent:AAPL:IVV:2026-04-14T00:05:00Z"
    second_create = client.post("/backtests/review-snapshots", json=second_payload)

    assert active_create.status_code == 200
    assert first_create.status_code == 200
    assert second_create.status_code == 200
    active_artifact = active_create.json()
    first_artifact = first_create.json()
    second_artifact = second_create.json()

    active_path = tmp_path / f"{active_artifact['identity']['artifact_id']}.json"
    first_path = tmp_path / f"{first_artifact['identity']['artifact_id']}.json"
    second_path = tmp_path / f"{second_artifact['identity']['artifact_id']}.json"
    os.utime(active_path, (datetime(2026, 4, 10, 0, 5, tzinfo=UTC).timestamp(), datetime(2026, 4, 10, 0, 5, tzinfo=UTC).timestamp()))
    os.utime(first_path, (datetime(2026, 4, 15, 0, 5, tzinfo=UTC).timestamp(), datetime(2026, 4, 15, 0, 5, tzinfo=UTC).timestamp()))
    os.utime(second_path, (datetime(2026, 4, 14, 0, 5, tzinfo=UTC).timestamp(), datetime(2026, 4, 14, 0, 5, tzinfo=UTC).timestamp()))

    queue_response = client.post(
        "/backtests/review-snapshots/active-thesis-cross-family-queue",
        json=_review_snapshot_active_thesis_cross_family_queue_payload(
            active_artifact["identity"]["artifact_id"],
            active_artifact["lineage"]["proposal_id"],
        ),
    )

    assert queue_response.status_code == 200
    payload = queue_response.json()
    assert payload["queue_kind"] == "review_snapshot_active_thesis_cross_family_queue"
    assert payload["provenance"] == "persisted_review_snapshot_artifacts_and_active_thesis_reference_only"
    assert payload["queue_ordering"] == "latest_saved_at_desc_then_artifact_id_desc"
    assert payload["active_thesis"]["source_proposal_id"] == active_artifact["lineage"]["proposal_id"]
    assert [row["family_key"]["proposal_family_id"] for row in payload["rows"]] == [
        first_artifact["lineage"]["proposal_family_id"],
        second_artifact["lineage"]["proposal_family_id"],
    ]
    assert payload["rows"][0]["latest_identity"] == first_artifact["identity"]
    assert payload["rows"][0]["proposal_source"] == first_artifact["pm_summary"]["provenance"]["proposal_source"]
    assert payload["rows"][0]["truth_labels"] == first_artifact["pm_summary"]["truth_labels"]
    assert payload["rows"][0]["trust_visibility"] == {
        "investor_economics_status": first_artifact["pm_summary"]["investor_economics_status"],
        "benchmark_separation": "explicit_per_snapshot_benchmark_fields",
    }
    assert payload["rows"][0]["pm_summary_fields"]["review_basis"] == first_artifact["pm_summary"]["review_basis"]
    assert payload["rows"][0]["pm_summary_fields"]["methodology"] == first_artifact["pm_summary"]["methodology"]
    assert payload["rows"][0]["pm_summary_fields"]["assumptions"] == first_artifact["pm_summary"]["assumptions"]
    assert payload["rows"][0]["pm_summary_fields"]["analytics_summary"] == first_artifact["pm_summary"]["analytics_summary"]
    assert payload["rows"][0]["pm_summary_fields"]["diagnostics_summary"] == first_artifact["pm_summary"]["diagnostics_summary"]
    assert payload["rows"][0]["family_separation"] == {
        "separation_kind": "distinct_proposal_family_id",
        "active_thesis_proposal_family_id": active_artifact["lineage"]["proposal_family_id"],
        "queue_proposal_family_id": first_artifact["lineage"]["proposal_family_id"],
    }
    assert "replay_payload" not in payload["rows"][0]
    assert "artifact" not in payload["rows"][0]


def test_review_snapshot_active_thesis_cross_family_queue_route_fails_closed_on_source_proposal_mismatch(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    active_payload = _review_snapshot_create_request("IUFS")
    active_payload["proposal_id"] = "proposal-thesis"
    active_payload["proposal_family_id"] = "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z"
    active_create = client.post("/backtests/review-snapshots", json=active_payload)
    assert active_create.status_code == 200
    active_artifact = active_create.json()

    queue_response = client.post(
        "/backtests/review-snapshots/active-thesis-cross-family-queue",
        json=_review_snapshot_active_thesis_cross_family_queue_payload(
            active_artifact["identity"]["artifact_id"],
            "proposal-other",
        ),
    )

    assert queue_response.status_code == 400
    assert queue_response.json()["detail"] == "review snapshot active thesis cross-family queue source_proposal_id does not match persisted artifact lineage"


def test_review_snapshot_family_inbox_route_fails_closed_on_ambiguous_latest_selection(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    second_payload = _review_snapshot_create_request("IUFS")
    second_payload["proposal_id"] = "proposal-IUFS-shadow"
    second_create = client.post(
        "/backtests/review-snapshots",
        json=second_payload,
    )

    assert first_create.status_code == 200
    assert second_create.status_code == 200
    first_artifact = first_create.json()
    second_artifact = second_create.json()
    first_path = tmp_path / f"{first_artifact['identity']['artifact_id']}.json"
    second_path = tmp_path / f"{second_artifact['identity']['artifact_id']}.json"
    shared_time = datetime(2026, 4, 16, 0, 5, tzinfo=UTC).timestamp()
    os.utime(first_path, (shared_time, shared_time))
    os.utime(second_path, (shared_time, shared_time))

    inbox_response = client.post(
        "/backtests/review-snapshots/family-inbox",
        json=_review_snapshot_family_inbox_payload(),
    )

    assert inbox_response.status_code == 400
    assert "review snapshot family inbox latest selection is ambiguous" in inbox_response.json()["detail"]


def test_review_snapshot_family_inbox_route_fails_closed_on_cross_family_contamination(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    anchor_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    contaminated_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUIT"),
    )

    assert anchor_create.status_code == 200
    assert contaminated_create.status_code == 200
    anchor_artifact = anchor_create.json()
    contaminated_artifact = contaminated_create.json()
    contaminated_path = tmp_path / f"{contaminated_artifact['identity']['artifact_id']}.json"
    payload = json.loads(contaminated_path.read_text(encoding="utf-8"))
    payload["lineage"]["proposal_family_id"] = anchor_artifact["lineage"]["proposal_family_id"]
    contaminated_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    inbox_response = client.post(
        "/backtests/review-snapshots/family-inbox",
        json=_review_snapshot_family_inbox_payload(),
    )

    assert inbox_response.status_code == 400
    assert "persisted review snapshot artifact failed schema validation" in inbox_response.json()["detail"]


def test_review_snapshot_compare_route_rejects_proposal_family_mismatch(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    baseline_create = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    candidate_payload = _review_snapshot_create_request("IUIT")
    candidate_payload["proposal_id"] = "proposal-IUFS-v2"
    candidate_payload["version_number"] = 2
    candidate_create = client.post(
        "/backtests/review-snapshots",
        json=candidate_payload,
    )

    assert baseline_create.status_code == 200
    assert candidate_create.status_code == 200
    baseline_artifact = baseline_create.json()
    candidate_artifact = candidate_create.json()

    compare_response = client.post(
        "/backtests/review-snapshots/compare",
        json={
            "baseline": _review_snapshot_comparison_ref_payload("baseline", baseline_artifact["identity"]["artifact_id"]),
            "candidate": _review_snapshot_comparison_ref_payload("candidate", candidate_artifact["identity"]["artifact_id"]),
        },
    )

    assert compare_response.status_code == 400
    assert compare_response.json()["detail"] == "review snapshot comparison requires matching proposal_family_id"


@pytest.mark.parametrize(
    ("route", "service_path", "request_payload_builder", "response_builder"),
    [
        (
            "/backtests/review-snapshots/compare",
            "app.api.routes.backtests.compare_review_snapshots",
            lambda: {
                "baseline": _review_snapshot_comparison_ref_payload("baseline", "review_snapshot_baseline"),
                "candidate": _review_snapshot_comparison_ref_payload("candidate", "review_snapshot_candidate"),
            },
            lambda: {
                "comparison_kind": "review_snapshot_comparison",
                "family_key": {
                    "workspace_id": "workspace-1",
                    "source_draft_id": "draft-1",
                    "source_base_node_id": "node-1",
                    "proposal_family_id": "",
                    "source_kind": "hypothetical_replacement_replay",
                },
                "baseline": {},
            },
        ),
        (
            "/backtests/review-snapshots/family-review",
            "app.api.routes.backtests.build_review_snapshot_family_review",
            lambda: _review_snapshot_family_review_payload("review_snapshot_anchor"),
            lambda: {
                "review_kind": "review_snapshot_family_review",
                "family_key": {
                    "workspace_id": None,
                    "source_draft_id": "draft-1",
                    "source_base_node_id": "node-1",
                    "proposal_family_id": "etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z",
                    "source_kind": "hypothetical_replacement_replay",
                },
                "provenance": "persisted_review_snapshot_artifacts_only",
                "compare_selection_policy": "exactly_two_distinct_family_siblings",
                "anchor": {},
                "siblings": [{}],
            },
        ),
        (
            "/backtests/review-snapshots/family-inbox",
            "app.api.routes.backtests.build_review_snapshot_family_inbox",
            lambda: _review_snapshot_family_inbox_payload(),
            lambda: {
                "inbox_kind": "review_snapshot_family_inbox",
                "workspace_id": "workspace-1",
                "provenance": "persisted_review_snapshot_artifacts_only",
                "rows": [
                    {
                        "family_key": {
                            "workspace_id": "workspace-1",
                            "source_draft_id": "",
                            "source_base_node_id": "node-1",
                            "proposal_family_id": "etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z",
                            "source_kind": "hypothetical_replacement_replay",
                        }
                    }
                ],
            },
        ),
        (
            "/backtests/review-snapshots/active-thesis-cross-family-queue",
            "app.api.routes.backtests.build_review_snapshot_active_thesis_cross_family_queue",
            lambda: _review_snapshot_active_thesis_cross_family_queue_payload("review_snapshot_active", "proposal-thesis"),
            lambda: {
                "queue_kind": "review_snapshot_active_thesis_cross_family_queue",
                "provenance": "persisted_review_snapshot_artifacts_and_active_thesis_reference_only",
                "queue_ordering": "latest_saved_at_desc_then_artifact_id_desc",
                "active_thesis": {
                    "source_proposal_id": "proposal-thesis",
                    "handoff": _review_snapshot_open_handoff_payload("review_snapshot_active"),
                    "identity": {
                        "artifact_id": "review_snapshot_active",
                        "artifact_kind": "portfolio_review_snapshot",
                        "schema_version": "review_snapshot_artifact_v1",
                        "fingerprint": "a" * 64,
                        "consumer_kind": "saved_hypothetical_replay_proposal",
                    },
                    "lineage": {
                        "workspace_id": "workspace-1",
                        "source_draft_id": "draft-1",
                        "source_base_node_id": "node-1",
                        "proposal_family_id": "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z",
                        "proposal_id": "proposal-thesis",
                        "version_number": 1,
                        "source_kind": "hypothetical_replacement_replay",
                    },
                    "family_key": {
                        "workspace_id": "workspace-1",
                        "source_draft_id": "draft-1",
                        "source_base_node_id": "node-1",
                        "proposal_family_id": "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z",
                        "source_kind": None,
                    },
                },
                "rows": [],
            },
        ),
    ],
)
def test_review_snapshot_routes_fail_closed_when_response_family_key_is_invalid(
    mocker,
    route: str,
    service_path: str,
    request_payload_builder,
    response_builder,
) -> None:
    client = TestClient(app, raise_server_exceptions=False)
    mocker.patch(service_path, return_value=response_builder())

    response = client.post(route, json=request_payload_builder())

    assert response.status_code == 500


def test_review_snapshot_open_route_fails_closed_on_malformed_pm_summary_payload(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    create_response = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    assert create_response.status_code == 200
    artifact = create_response.json()
    artifact_path = tmp_path / f"{artifact['identity']['artifact_id']}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["pm_summary"]["role"] = "candidate"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    open_response = client.post(
        "/backtests/review-snapshots/open",
        json=_review_snapshot_open_handoff_payload(artifact["identity"]["artifact_id"]),
    )

    assert open_response.status_code == 400
    assert "persisted review snapshot artifact failed schema validation" in open_response.json()["detail"]


def test_review_snapshot_open_route_fails_closed_on_proposal_capture_open_handoff_mismatch(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    create_response = client.post(
        "/backtests/review-snapshots",
        json=_review_snapshot_create_request("IUFS"),
    )
    assert create_response.status_code == 200
    artifact = create_response.json()
    artifact_path = tmp_path / f"{artifact['identity']['artifact_id']}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["proposal_capture"]["open_handoff"]["artifact_id"] = "review_snapshot_other"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    open_response = client.post(
        "/backtests/review-snapshots/open",
        json=_review_snapshot_open_handoff_payload(artifact["identity"]["artifact_id"]),
    )

    assert open_response.status_code == 400
    assert "persisted review snapshot artifact failed schema validation" in open_response.json()["detail"]


def test_review_snapshot_route_inventory_stays_aligned_with_shipped_contract_family() -> None:
    route_methods = {
        (tuple(sorted(route.methods - {"HEAD", "OPTIONS"})), route.path)
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/backtests/review-snapshots")
    }

    assert route_methods == {
        (("POST",), "/backtests/review-snapshots"),
        (("POST",), "/backtests/review-snapshots/open"),
        (("POST",), "/backtests/review-snapshots/family-inbox"),
        (("POST",), "/backtests/review-snapshots/family-review"),
        (("POST",), "/backtests/review-snapshots/active-thesis-cross-family-queue"),
        (("POST",), "/backtests/review-snapshots/compare"),
    }


def test_construction_artifact_routes_fail_closed_on_malformed_persisted_min_position_weight_state(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-invalid-persisted-min-position",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
                "min_position_weight": 0.5,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["normalized_inputs"]["min_position_weight"] = 0.49
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    get_response = client.get(f"/construction/artifacts/{artifact_id}")
    validation_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload(artifact_id),
    )
    preview_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=_construction_artifact_preview_payload(artifact_id),
    )

    assert get_response.status_code == 400
    assert validation_response.status_code == 400
    assert preview_response.status_code == 400
    assert "persisted construction artifact failed schema validation" in get_response.json()["detail"]


def test_construction_artifact_validation_route_returns_400_for_infeasible_artifact(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-validation-route-infeasible",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload(artifact_id),
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "construction_artifact_id must reference a feasible construction artifact"}


def test_construction_artifact_validation_route_returns_400_for_missing_replay_required_weights(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-validation-route-missing-baseline",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-validation",
        json=_construction_artifact_validation_payload(artifact_id),
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "construction artifact replay requires normalized_inputs.current_portfolio_weights for the baseline replay path"
    }


def test_construction_artifact_replay_route_echoes_empty_selection_trace_for_legacy_artifact(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
    }
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-legacy-trace",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload.pop("selection_rule_trace")
    payload.pop("turnover_diagnostics_status")
    payload.pop("turnover_diagnostics_v1")
    payload.pop("weighting_trace_status")
    payload.pop("weighting_trace_v1")
    payload_without_ids = {key: value for key, value in payload.items() if key not in {"artifact_id", "fingerprint"}}
    fingerprint = sha256(
        json.dumps(payload_without_ids, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    legacy_artifact_id = f"construction_artifact_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["artifact_id"] = legacy_artifact_id
    artifact_path.unlink()
    legacy_path = tmp_path / f"{legacy_artifact_id}.json"
    legacy_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": legacy_artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["replay_provenance"]["selection_rule_trace"] == {"rule_ids": [], "steps": []}
    assert response.json()["replay_provenance"]["turnover_diagnostics_status"] == "unavailable_legacy_artifact"
    assert response.json()["replay_provenance"]["turnover_diagnostics_v1"] is None
    assert response.json()["replay_provenance"]["weighting_trace_status"] == "unavailable_legacy_artifact"
    assert response.json()["replay_provenance"]["weighting_trace_v1"] is None


@pytest.mark.parametrize(
    ("fixture_name", "expected_selection_rule_trace"),
    [
        ("construction_artifact_legacy_missing_selection_rule_trace.json", {"rule_ids": [], "steps": []}),
        ("construction_artifact_legacy_null_selection_rule_trace.json", {"rule_ids": [], "steps": []}),
        ("construction_artifact_legacy_empty_selection_rule_trace.json", {"rule_ids": [], "steps": []}),
        ("construction_artifact_legacy_missing_policy_definition_id.json", None),
        ("construction_artifact_legacy_missing_max_turnover_weight.json", None),
        ("construction_artifact_reference.json", None),
    ],
    ids=[
        "missing_selection_rule_trace",
        "null_selection_rule_trace",
        "empty_selection_rule_trace",
        "missing_policy_definition_id",
        "missing_max_turnover_weight",
        "explicit_null_max_turnover_weight",
    ],
)
def test_construction_artifact_replay_route_fixture_matrix_preserves_legacy_behavior(
    tmp_path,
    mocker,
    fixture_name,
    expected_selection_rule_trace,
) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    client = TestClient(app)

    reference_artifact_id, _ = _persist_construction_artifact_fixture(
        tmp_path,
        "construction_artifact_reference.json",
    )
    reference_response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=_construction_artifact_preview_payload(reference_artifact_id),
    )
    assert reference_response.status_code == 200
    reference_payload = reference_response.json()

    artifact_id, _ = _persist_construction_artifact_fixture(tmp_path, fixture_name)
    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=_construction_artifact_preview_payload(artifact_id),
    )

    assert response.status_code == 200
    payload = response.json()
    expected_provenance = dict(reference_payload["replay_provenance"])
    expected_provenance["construction_artifact_id"] = artifact_id
    expected_provenance["selection_rule_trace"] = (
        expected_selection_rule_trace
        or reference_payload["replay_provenance"]["selection_rule_trace"]
    )
    if expected_selection_rule_trace is not None:
        expected_provenance["turnover_diagnostics_status"] = "unavailable_legacy_artifact"
        expected_provenance["turnover_diagnostics_v1"] = None
        expected_provenance["weighting_trace_status"] = "unavailable_legacy_artifact"
        expected_provenance["weighting_trace_v1"] = None

    assert payload["construction_artifact_id"] == artifact_id
    assert payload["truth_separation"] == reference_payload["truth_separation"]
    assert payload["baseline_weights"] == reference_payload["baseline_weights"]
    assert payload["candidate_weights"] == reference_payload["candidate_weights"]
    assert payload["replay"] == reference_payload["replay"]
    assert payload["replay_provenance"] == expected_provenance


@pytest.mark.parametrize(
    "fixture_name",
    [
        "construction_artifact_malformed_partial_selection_trace_missing_rule_ids.json",
        "construction_artifact_malformed_partial_selection_trace_empty_rule_ids.json",
    ],
    ids=["missing_rule_ids", "empty_rule_ids"],
)
def test_construction_artifact_replay_route_fixture_matrix_rejects_partial_malformed_selection_trace(
    tmp_path,
    mocker,
    fixture_name,
) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    client = TestClient(app)

    artifact_id, _ = _persist_construction_artifact_fixture(tmp_path, fixture_name)
    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json=_construction_artifact_preview_payload(artifact_id),
    )

    assert response.status_code == 400
    assert "persisted construction artifact failed schema validation" in response.json()["detail"]


def test_construction_artifact_replay_route_hydrates_missing_legacy_policy_definition_id(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
    }
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-legacy-policy-definition",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["normalized_inputs"].pop("policy_definition_id")
    payload_without_ids = {key: value for key, value in payload.items() if key not in {"artifact_id", "fingerprint"}}
    fingerprint = sha256(
        json.dumps(payload_without_ids, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    legacy_artifact_id = f"construction_artifact_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["artifact_id"] = legacy_artifact_id
    artifact_path.unlink()
    legacy_path = tmp_path / f"{legacy_artifact_id}.json"
    legacy_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": legacy_artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["replay_provenance"]["policy_definition_id"] == "construction_policy_definition_top_n_equal_weight_v1"


@pytest.mark.parametrize(
    "turnover_mutator",
    [
        lambda payload: payload["hard_constraints"].pop("max_turnover_weight", None),
        lambda payload: payload["hard_constraints"].__setitem__("max_turnover_weight", None),
    ],
    ids=["missing", "explicit_null"],
)
def test_construction_artifact_replay_route_treats_missing_and_explicit_null_turnover_caps_as_equivalent(
    tmp_path,
    mocker,
    turnover_mutator,
) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
    }
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-turnover-null-parity",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                    {"symbol": "BBB", "rank": 2, "eligible": True, "score": 0.8},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 0.6},
                    {"symbol": "BBB", "weight": 0.4},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
                "max_turnover_weight": None,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    legacy_artifact_id = _rekey_construction_artifact_payload(tmp_path, artifact_id, turnover_mutator)

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": legacy_artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["construction_artifact_id"] == artifact_id


def test_construction_artifact_replay_route_returns_404_for_missing_artifact(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": "construction_artifact_missing",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 404
    assert "missing persisted construction artifact file" in response.json()["detail"]


def test_construction_artifact_replay_route_returns_400_for_invalid_persisted_artifact_payload(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-invalid-payload",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload.pop("status")
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert "persisted construction artifact failed schema validation" in response.json()["detail"]


@pytest.mark.parametrize(
    "selection_rule_trace",
    [
        {
            "steps": [
                {
                    "rule_id": "eligible_only",
                    "rule_order": 1,
                    "input_candidate_symbols": ["AAA"],
                    "output_candidate_symbols": ["AAA"],
                }
            ]
        },
        {
            "rule_ids": [],
            "steps": [
                {
                    "rule_id": "eligible_only",
                    "rule_order": 1,
                    "input_candidate_symbols": ["AAA"],
                    "output_candidate_symbols": ["AAA"],
                }
            ],
        },
    ],
    ids=["missing_rule_ids", "empty_rule_ids"],
)
def test_construction_artifact_replay_route_returns_400_for_partial_malformed_selection_trace(
    tmp_path,
    mocker,
    selection_rule_trace,
) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-malformed-trace",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["selection_rule_trace"] = selection_rule_trace
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert "persisted construction artifact failed schema validation" in response.json()["detail"]


def test_construction_artifact_replay_route_returns_400_for_invalid_artifact_json(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-invalid-json",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    artifact_path.write_text("{not-json", encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert "invalid persisted construction artifact json" in response.json()["detail"]


def test_construction_artifact_replay_route_returns_400_for_non_object_artifact_payload(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-non-object",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    artifact_path.write_text("[]", encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert "persisted construction artifact payload must be a json object" in response.json()["detail"]


def test_construction_artifact_replay_route_returns_400_for_integrity_validation_failure(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-integrity",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "construction_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert "construction artifact_id does not match canonical artifact content" in response.json()["detail"]


def test_construction_artifact_replay_route_returns_400_for_infeasible_artifact(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-infeasible",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "AAA", "weight": 1.0},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "construction_artifact_id must reference a feasible construction artifact"}


def test_construction_artifact_replay_route_returns_400_for_missing_replay_required_weights(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=SimpleNamespace(construction_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    construction_response = client.post(
        "/construction/run",
        json={
            "request_id": "construction-replay-route-missing-baseline",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "AAA", "rank": 1, "eligible": True, "score": 0.9},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        },
    )

    assert construction_response.status_code == 200
    artifact_id = construction_response.json()["artifact_id"]

    response = client.post(
        "/backtests/portfolio-allocation/construction-artifact-preview",
        json={
            "construction_artifact_id": artifact_id,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "construction artifact replay requires normalized_inputs.current_portfolio_weights for the baseline replay path"
    }


def test_optimizer_handoff_replay_route_preserves_benchmark_relative_metrics_when_verified_adjusted_close(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "CCC": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 104.0},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 109.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.3},
            {"date": "2024-06-03", "price": 101.8},
            {"date": "2024-12-31", "price": 104.5},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.0},
            {"date": "2024-02-01", "price": 98.7},
            {"date": "2024-06-03", "price": 99.8},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 103.2},
            {"date": "2024-06-03", "price": 104.0},
            {"date": "2024-12-31", "price": 107.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.1},
            {"date": "2024-12-31", "price": 103.5},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 97.0},
            {"date": "2024-02-01", "price": 97.2},
            {"date": "2024-06-03", "price": 98.5},
            {"date": "2024-12-31", "price": 101.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.4},
            {"date": "2024-06-03", "price": 103.2},
            {"date": "2024-12-31", "price": 105.2},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.4},
            {"date": "2024-02-01", "price": 100.5},
            {"date": "2024-06-03", "price": 100.6},
            {"date": "2024-12-31", "price": 101.2},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.5},
            {"date": "2024-02-01", "price": 99.0},
            {"date": "2024-06-03", "price": 101.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.8},
            {"date": "2024-02-01", "price": 100.9},
            {"date": "2024-06-03", "price": 101.2},
            {"date": "2024-12-31", "price": 102.3},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.8},
            {"date": "2024-12-31", "price": 104.1},
        ],
    }
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-verified-benchmark-relative-replay-route",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-01-01", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-01-01", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-12-31T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    persisted_handoff = _rekey_persisted_handoff(
        preview_response.json()["persisted_handoff"],
        lambda payload: payload["return_basis_attestation"]["section_trust"].update(
            {"benchmark_relative_path": "verified_adjusted_close"}
        ),
    )

    replay_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": persisted_handoff,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert replay_response.status_code == 200
    replay_payload = replay_response.json()
    assert replay_payload["replay_provenance"]["replay_output_policy"] == {
        "source": "persisted_return_basis_attestation",
        "section_trust": {
            "benchmark_relative_path": "verified_adjusted_close",
            "factor_model_path": "degraded_unverified_return_basis",
            "risk_contribution_path": "degraded_unverified_return_basis",
        },
        "eligible_families": [
            "benchmark_relative_volatility_outputs",
        ],
        "withheld_families": [
            "factor_exposure_outputs",
            "stress_scenario_outputs",
            "risk_contribution_outputs",
            "concentration_outputs",
        ],
    }
    assert replay_payload["review_basis"] == {
        "basis_version": 1,
        "basis_kind": "persisted_optimizer_handoff_review",
        "review_scope": "workspace_review_only",
        "canonical_source": "persisted_handoff_reference",
        "basis_provenance_label": "artifact_backed_review_basis",
        "portfolio_truth": "imported_portfolio_snapshot",
        "candidate_truth": "hypothetical_optimizer_handoff",
        "handoff_reference": persisted_handoff,
        "benchmark_symbol": "SPY",
        "base_currency": "USD",
        "replay_window": {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        },
        "baseline_weights": replay_payload["baseline_weights"],
        "candidate_weights": replay_payload["candidate_weights"],
    }
    assert replay_payload["replay"]["methodology_provenance"] == {
        "provenance_version": 1,
        "source": "portfolio_allocation_backtest_engine",
        "methodology_truth": "review_only_replay_methodology",
        "assumptions_truth": "review_only_replay_assumptions",
        "analytics_truth": "hypothetical_replay_analytics_only",
        "review_scope": "workspace_review_context_only",
    }

    for result_key in ("reference_result", "candidate_result"):
        metrics = replay_payload["replay"][result_key]["metrics"]
        assert metrics["tracking_error_pct"] is not None
        assert metrics["beta_vs_benchmark"] is not None
        assert metrics["correlation_vs_benchmark"] is not None
        assert metrics["benchmark_return_pct"] is None
        assert metrics["excess_return_pct"] is None
        assert metrics["information_ratio"] is None

    comparison = replay_payload["replay"]["comparison"]
    assert comparison["tracking_error_diff_pct"] is not None
    assert comparison["beta_diff"] is not None
    assert comparison["correlation_diff"] is not None


@pytest.mark.parametrize(
    "legacy_manifest_mutator",
    [
        lambda payload: payload["return_basis_attestation"].pop("factor_basis_path", None),
        lambda payload: payload["return_basis_attestation"].update({"factor_basis_path": None}),
    ],
    ids=["missing_factor_basis_path", "null_factor_basis_path"],
)
def test_optimizer_handoff_replay_route_normalizes_legacy_factor_basis_variants_with_canonical_parity(
    tmp_path,
    mocker,
    legacy_manifest_mutator,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "CCC": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 104.0},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 109.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.3},
            {"date": "2024-06-03", "price": 101.8},
            {"date": "2024-12-31", "price": 104.5},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.0},
            {"date": "2024-02-01", "price": 98.7},
            {"date": "2024-06-03", "price": 99.8},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 103.2},
            {"date": "2024-06-03", "price": 104.0},
            {"date": "2024-12-31", "price": 107.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.1},
            {"date": "2024-12-31", "price": 103.5},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 97.0},
            {"date": "2024-02-01", "price": 97.2},
            {"date": "2024-06-03", "price": 98.5},
            {"date": "2024-12-31", "price": 101.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.4},
            {"date": "2024-06-03", "price": 103.2},
            {"date": "2024-12-31", "price": 105.2},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.4},
            {"date": "2024-02-01", "price": 100.5},
            {"date": "2024-06-03", "price": 100.6},
            {"date": "2024-12-31", "price": 101.2},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 99.5},
            {"date": "2024-02-01", "price": 99.0},
            {"date": "2024-06-03", "price": 101.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.8},
            {"date": "2024-02-01", "price": 100.9},
            {"date": "2024-06-03", "price": 101.2},
            {"date": "2024-12-31", "price": 102.3},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 101.4},
            {"date": "2024-06-03", "price": 102.8},
            {"date": "2024-12-31", "price": 104.1},
        ],
    }
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-legacy-factor-basis-route-parity",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-01-01", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-01-01", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-12-31T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    preview_payload = preview_response.json()
    persisted_handoff = preview_payload["persisted_handoff"]

    canonical_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": persisted_handoff,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert canonical_response.status_code == 200
    canonical_payload = canonical_response.json()

    _mutate_persisted_json(persisted_handoff["manifest_path"], legacy_manifest_mutator)

    legacy_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": persisted_handoff,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert legacy_response.status_code == 200
    legacy_payload = legacy_response.json()
    assert (
        legacy_payload["replay_provenance"]["return_basis_attestation"]
        == canonical_payload["replay_provenance"]["return_basis_attestation"]
    )
    assert legacy_payload["replay_provenance"]["return_basis_attestation"]["factor_basis_path"] == "degraded_unverified_return_basis"
    assert legacy_payload["replay_provenance"]["replay_output_policy"] == canonical_payload["replay_provenance"]["replay_output_policy"]
    assert {
        "benchmark_id": legacy_payload["replay_provenance"]["benchmark_id"],
        "benchmark_version": legacy_payload["replay_provenance"]["benchmark_version"],
        "benchmark_symbol": legacy_payload["replay_provenance"]["benchmark_symbol"],
    } == {
        "benchmark_id": canonical_payload["replay_provenance"]["benchmark_id"],
        "benchmark_version": canonical_payload["replay_provenance"]["benchmark_version"],
        "benchmark_symbol": canonical_payload["replay_provenance"]["benchmark_symbol"],
    }
    assert legacy_payload["replay"]["candidate_result"]["investor_economics_status"] == canonical_payload["replay"]["candidate_result"]["investor_economics_status"]
    assert legacy_payload["replay"]["investor_economics_status"] == canonical_payload["replay"]["investor_economics_status"]
    assert legacy_payload["replay"]["candidate_result"]["metrics"]["tracking_error_pct"] == canonical_payload["replay"]["candidate_result"]["metrics"]["tracking_error_pct"] == None
    assert legacy_payload["replay"]["candidate_result"]["metrics"]["beta_vs_benchmark"] == canonical_payload["replay"]["candidate_result"]["metrics"]["beta_vs_benchmark"] == None
    assert legacy_payload["replay"]["candidate_result"]["metrics"]["correlation_vs_benchmark"] == canonical_payload["replay"]["candidate_result"]["metrics"]["correlation_vs_benchmark"] == None
    assert legacy_payload["replay"]["comparison"]["tracking_error_diff_pct"] == canonical_payload["replay"]["comparison"]["tracking_error_diff_pct"] == None
    assert legacy_payload["replay"]["comparison"]["beta_diff"] == canonical_payload["replay"]["comparison"]["beta_diff"] == None
    assert legacy_payload["replay"]["comparison"]["correlation_diff"] == canonical_payload["replay"]["comparison"]["correlation_diff"] == None
    assert legacy_payload["replay"]["candidate_diagnostics"]["factor_snapshot"] == canonical_payload["replay"]["candidate_diagnostics"]["factor_snapshot"] == []
    assert (
        legacy_payload["replay"]["candidate_diagnostics"]["risk_contribution"]["factor_contributions"]
        == canonical_payload["replay"]["candidate_diagnostics"]["risk_contribution"]["factor_contributions"]
        == []
    )
    assert (
        legacy_payload["replay"]["diagnostics_comparison"]["factor_exposure_changes"]
        == canonical_payload["replay"]["diagnostics_comparison"]["factor_exposure_changes"]
        == []
    )


def test_optimizer_handoff_replay_route_blocks_replay_window_outside_attested_coverage(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices.return_value = []
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {}
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-outside-attested-coverage",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-04-15", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-04-15", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-04-15T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    persisted_handoff = preview_response.json()["persisted_handoff"]
    mock_service.reset_mock()

    replay_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": persisted_handoff,
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert replay_response.status_code == 400
    payload = replay_response.json()["detail"]
    assert payload["validation_status"] == "blocked"
    assert "requested_replay_window_within_attested_return_basis_coverage" in payload["blocking_rule_ids"]
    evaluation = next(item for item in payload["evaluations"] if item["rule_id"] == "requested_replay_window_within_attested_return_basis_coverage")
    assert evaluation["status"] == "fail"
    assert payload["eligible_replay_window"] == {
        "source": "persisted_return_basis_attestation",
        "benchmark_symbol": "SPY",
        "as_of_date": "2024-04-15",
        "start_date": "2024-04-15",
        "end_date": "2024-04-15",
    }
    assert payload["replay_handoff"] is None
    assert payload["provenance"]["replay_output_policy"] == {
        "source": "persisted_return_basis_attestation",
        "section_trust": {
            "benchmark_relative_path": "degraded_unverified_return_basis",
            "factor_model_path": "degraded_unverified_return_basis",
            "risk_contribution_path": "degraded_unverified_return_basis",
        },
        "eligible_families": [],
        "withheld_families": [
            "benchmark_relative_volatility_outputs",
            "factor_exposure_outputs",
            "stress_scenario_outputs",
            "risk_contribution_outputs",
            "concentration_outputs",
        ],
    }
    mock_service.return_value.get_historical_prices.assert_not_called()
    mock_service.return_value.get_historical_prices_for_symbols.assert_not_called()


def test_optimizer_handoff_constraints_route_surfaces_attested_window_and_candidate_window_validation(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices.return_value = []
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {}
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-constraints-attested-window",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-04-15", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-04-15", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-04-15T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    persisted_handoff = preview_response.json()["persisted_handoff"]
    mock_service.reset_mock()

    response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": persisted_handoff,
            "start_date": "2024-04-15",
            "end_date": "2024-04-15",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_status"] == "ok"
    assert payload["eligible_replay_window"] == {
        "source": "persisted_return_basis_attestation",
        "benchmark_symbol": "SPY",
        "as_of_date": "2024-04-15",
        "start_date": "2024-04-15",
        "end_date": "2024-04-15",
    }
    assert payload["replay_handoff"] == {
        "handoff_kind": "optimizer_handoff_replay_handoff_v1",
        "handoff_reference": persisted_handoff,
        "effective_replay_params": {
            "start_date": "2024-04-15",
            "end_date": "2024-04-15",
            "initial_capital": 100000.0,
            "rebalance_frequency": "monthly",
            "base_currency": "USD",
            "commission_bps": 0.0,
            "slippage_bps": 0.0,
            "drift_tolerance_pct": None,
            "price_basis": "adjusted_close",
            "execution_price_field": "close",
            "execution_lag_days": 1,
            "symbol_overrides": {},
        },
    }
    assert payload["provenance"]["replay_output_policy"] == {
        "source": "persisted_return_basis_attestation",
        "section_trust": {
            "benchmark_relative_path": "degraded_unverified_return_basis",
            "factor_model_path": "degraded_unverified_return_basis",
            "risk_contribution_path": "degraded_unverified_return_basis",
        },
        "eligible_families": [],
        "withheld_families": [
            "benchmark_relative_volatility_outputs",
            "factor_exposure_outputs",
            "stress_scenario_outputs",
            "risk_contribution_outputs",
            "concentration_outputs",
        ],
    }
    evaluation = next(item for item in payload["evaluations"] if item["rule_id"] == "requested_replay_window_within_attested_return_basis_coverage")
    assert evaluation["status"] == "pass"
    mock_service.return_value.get_historical_prices.assert_not_called()
    mock_service.return_value.get_historical_prices_for_symbols.assert_not_called()


def test_optimizer_handoff_preview_route_accepts_validation_replay_handoff_verbatim(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices.return_value = []
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "CCC": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 104.0},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 109.0},
        ],
    }
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post("/optimizer/preview", json=_optimizer_preview_payload())

    assert preview_response.status_code == 200
    persisted_handoff = preview_response.json()["persisted_handoff"]

    validation_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": persisted_handoff,
            "start_date": "2024-04-15",
            "end_date": "2024-12-31",
        },
    )

    assert validation_response.status_code == 200
    replay_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json=validation_response.json()["replay_handoff"],
    )

    assert replay_response.status_code == 200
    assert replay_response.json()["review_basis"]["handoff_reference"] == persisted_handoff


def test_optimizer_handoff_preview_route_rejects_replay_handoff_mixed_with_legacy_fields(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_kind": "optimizer_handoff_replay_handoff_v1",
            "handoff_reference": {
                "reference_kind": "optimizer_handoff_reference_v1",
                "handoff_id": "optimizer_handoff_demo",
                "artifact_id": "opt_artifact_demo",
                "manifest_path": "C:/tmp/manifest.json",
                "artifact_path": "C:/tmp/artifact.json",
            },
            "effective_replay_params": {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "initial_capital": 100000,
                "rebalance_frequency": "monthly",
                "base_currency": "USD",
                "commission_bps": 0,
                "slippage_bps": 0,
                "drift_tolerance_pct": None,
                "price_basis": "adjusted_close",
                "execution_price_field": "close",
                "execution_lag_days": 1,
                "symbol_overrides": {},
            },
            "start_date": "2024-01-01",
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    "legacy_manifest_mutator",
    [
        lambda payload: payload["return_basis_attestation"].pop("factor_basis_path", None),
        lambda payload: payload["return_basis_attestation"].update({"factor_basis_path": None}),
    ],
    ids=["missing_factor_basis_path", "null_factor_basis_path"],
)
def test_optimizer_handoff_constraints_route_normalizes_legacy_factor_basis_variants_with_canonical_parity(
    tmp_path,
    mocker,
    legacy_manifest_mutator,
) -> None:
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-legacy-factor-basis-constraints-route-parity",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-01-01", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-01-01", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-12-31T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    persisted_handoff = preview_response.json()["persisted_handoff"]

    canonical_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": persisted_handoff,
        },
    )

    assert canonical_response.status_code == 200
    canonical_payload = canonical_response.json()

    _mutate_persisted_json(persisted_handoff["manifest_path"], legacy_manifest_mutator)

    legacy_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": persisted_handoff,
        },
    )

    assert legacy_response.status_code == 200
    legacy_payload = legacy_response.json()
    assert legacy_payload["validation_status"] == canonical_payload["validation_status"] == "ok"
    assert legacy_payload["blocking_rule_ids"] == canonical_payload["blocking_rule_ids"] == []
    assert legacy_payload["provenance"]["replay_output_policy"] == canonical_payload["provenance"]["replay_output_policy"]
    assert legacy_payload["provenance"]["replay_output_policy"]["section_trust"]["factor_model_path"] == "degraded_unverified_return_basis"
    assert legacy_payload["provenance"]["replay_output_policy"]["section_trust"]["risk_contribution_path"] == "degraded_unverified_return_basis"


@pytest.mark.parametrize(
    "factor_basis_mutator",
    [
        lambda attestation: attestation.pop("factor_basis_path", None),
        lambda attestation: attestation.update({"factor_basis_path": None}),
    ],
    ids=["missing_factor_basis_path", "null_factor_basis_path"],
)
@pytest.mark.parametrize(
    "section_trust_mutator",
    [
        lambda attestation: attestation.pop("section_trust", None),
        lambda attestation: attestation.update({"section_trust": {}}),
    ],
    ids=["missing_section_trust", "malformed_section_trust"],
)
def test_optimizer_handoff_constraints_route_stays_fail_closed_when_invalid_section_trust_cannot_recover_factor_trust(
    tmp_path,
    mocker,
    factor_basis_mutator,
    section_trust_mutator,
) -> None:
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-invalid-section-trust-constraints-route",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-01-01", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-01-01", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-12-31T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    persisted_handoff = preview_response.json()["persisted_handoff"]

    def _invalidate_legacy_factor_trust(payload: dict) -> None:
        attestation = payload["return_basis_attestation"]
        factor_basis_mutator(attestation)
        section_trust_mutator(attestation)

    _mutate_persisted_json(persisted_handoff["manifest_path"], _invalidate_legacy_factor_trust)

    response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": persisted_handoff,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_status"] == "blocked"
    assert "manifest_model_valid" in payload["blocking_rule_ids"]
    assert payload["provenance"]["replay_output_policy"] is None
    evaluation = next(item for item in payload["evaluations"] if item["rule_id"] == "manifest_model_valid")
    assert evaluation["status"] == "fail"


def test_optimizer_handoff_constraints_route_uses_load_normalized_attestation_for_policy_parity(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-normalized-load-boundary-constraints-route",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-01-01", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-01-01", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-12-31T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    persisted_handoff = preview_response.json()["persisted_handoff"]

    _mutate_persisted_json(
        persisted_handoff["manifest_path"],
        lambda payload: payload["return_basis_attestation"].update(
            {
                "factor_basis_path": "unavailable",
                "section_trust": {
                    "benchmark_relative_path": "degraded_unverified_return_basis",
                    "factor_model_path": "verified_adjusted_close",
                    "risk_contribution_path": "verified_adjusted_close",
                },
            }
        ),
    )

    response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": persisted_handoff,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_status"] == "blocked"
    assert payload["blocking_rule_ids"] == ["manifest_artifact_consistent"]
    assert payload["provenance"]["replay_output_policy"] == {
        "source": "persisted_return_basis_attestation",
        "section_trust": {
            "benchmark_relative_path": "degraded_unverified_return_basis",
            "factor_model_path": "unavailable",
            "risk_contribution_path": "unavailable",
        },
        "eligible_families": [],
        "withheld_families": [
            "benchmark_relative_volatility_outputs",
            "factor_exposure_outputs",
            "stress_scenario_outputs",
            "risk_contribution_outputs",
            "concentration_outputs",
        ],
    }


def test_optimizer_handoff_routes_reject_removed_request_benchmark_symbol(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 102.0},
            {"date": "2024-02-01", "price": 102.5},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 108.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 101.0},
            {"date": "2024-02-01", "price": 102.0},
            {"date": "2024-06-03", "price": 103.0},
            {"date": "2024-12-31", "price": 104.0},
        ],
        "BBB": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 100.5},
            {"date": "2024-02-01", "price": 101.0},
            {"date": "2024-06-03", "price": 101.5},
            {"date": "2024-12-31", "price": 102.0},
        ],
        "CCC": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-31", "price": 103.0},
            {"date": "2024-02-01", "price": 104.0},
            {"date": "2024-06-03", "price": 106.0},
            {"date": "2024-12-31", "price": 109.0},
        ],
    }
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    client = TestClient(app)

    preview_response = client.post(
        "/optimizer/preview",
        json={
            "request_id": "preview-removed-benchmark-request-field",
            "universe_id": "optimizer_universe_large_cap_demo_v1",
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                    "account_id": "U1234567",
                    "base_currency": "USD",
                    "statement_period": "2024-04",
                    "page_count": 4,
                },
                "statements": [
                    {
                        "importer": "interactive_brokers",
                        "imported_at": "2024-04-15T09:30:00Z",
                        "source_path": "IB2024.pdf",
                        "detected_format": "statement_pdf",
                        "account_id": "U1234567",
                        "base_currency": "USD",
                        "statement_period": "2024-04",
                        "page_count": 4,
                    }
                ],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [{"currency": "USD", "ending_cash": 500.0}],
                "positions": [
                    {"as_of_date": "2024-04-15", "symbol": "AAA", "quantity": 10.0, "cost_basis": 60.0, "close_price": 6.0, "market_value": 60.0, "unrealized_pnl": 0.0, "currency": "USD"},
                    {"as_of_date": "2024-04-15", "symbol": "BBB", "quantity": 8.0, "cost_basis": 40.0, "close_price": 5.0, "market_value": 40.0, "unrealized_pnl": 0.0, "currency": "USD"},
                ],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-04-15T09:30:00",
                "trust_status": "trusted",
                "weights": [
                    {"symbol": "AAA", "weight": 0.5},
                    {"symbol": "BBB", "weight": 0.3},
                    {"symbol": "CCC", "weight": 0.2},
                ],
            },
            "universe": [
                {"symbol": "AAA", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "BBB", "eligible": True, "taxonomy_labels": {}},
                {"symbol": "CCC", "eligible": True, "taxonomy_labels": {}},
            ],
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {"default_max_weight": 0.6},
                "turnover": {"max_turnover": None},
                "risk": {"max_active_risk": None},
                "active_group_exposures": [],
            },
            "penalties": [],
        },
    )

    assert preview_response.status_code == 200
    persisted_handoff = preview_response.json()["persisted_handoff"]

    replay_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": persisted_handoff,
            "benchmark_symbol": "QQQ",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )
    constraints_response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": persisted_handoff,
            "benchmark_symbol": "QQQ",
        },
    )

    assert replay_response.status_code == 422
    assert constraints_response.status_code == 422


def test_optimizer_preview_route_rejects_untrusted_benchmark() -> None:
    client = TestClient(app)

    response = client.post(
        "/optimizer/preview",
        json={
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2024-04-15T09:30:00Z",
                    "source_path": "IB2024.pdf",
                    "detected_format": "statement_pdf",
                },
                "statements": [],
                "statement_totals": None,
                "instruments": [],
                "cash_balances": [],
                "positions": [{"as_of_date": "2024-04-15", "symbol": "AAA", "quantity": 10.0, "cost_basis": 100.0, "close_price": 10.0, "market_value": 100.0, "unrealized_pnl": 0.0, "currency": "USD"}],
                "ledger_entries": [],
            },
            "benchmark": {
                "benchmark_id": "benchmark_spy_demo_v1",
                "benchmark_version": "2024-04-15",
                "source_name": "test_benchmark_contract",
                "as_of_timestamp": "2024-04-15T09:30:00",
                "trust_status": "untrusted",
                "weights": [{"symbol": "AAA", "weight": 1.0}],
            },
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "benchmark_relative": {"max_abs_active_weight": 0.1},
                "position_limits": {},
                "turnover": {},
                "risk": {},
                "active_group_exposures": [],
            },
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "benchmark preview input must be trusted"}


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
    assert payload["snapshot"]["statement"]["statement_period"] == "2025-01-01 - 2026-04-24"


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
