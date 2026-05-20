import json
import re
import os
from dataclasses import replace
from datetime import UTC, date, datetime
from fractions import Fraction
from hashlib import sha256
from pathlib import Path

import pytest
from types import SimpleNamespace
from typing import Literal, cast
from pydantic import ValidationError

from app.schemas.backtest_engine import AllocationBacktestAssumptions, AllocationBacktestMetrics, AllocationBacktestPoint, AllocationBacktestResult, AllocationBacktestWeight, BenchmarkTrendOverlayMonitorBenchmarkObservationInput, BenchmarkTrendOverlayObservationSourceLineage, CandidateConstructionRuleInput, ConstructedCandidateReplayInput, ConstructionArtifactPreviewHandoff, ConstructionArtifactReplayProvenance, ConstructionArtifactReplayRequest, ConstructionArtifactReplayResponse, ConstructionArtifactWorkspaceReviewBasis, CreateMonitorDefinitionRequest, DraftPortfolioImportedMetaInput, DraftPortfolioSnapshotInput, DraftPortfolioPositionInput, EvaluateMonitorDefinitionObservationRequest, HypotheticalReplayProposalSource, HypotheticalReplacementReplayRequest, MonitorDefinitionArtifactListResponse, MonitorDefinitionDiscoveryFilters, MonitorDefinitionEvaluationHistoryEntryArtifact, MonitorDefinitionLatestEvaluationBenchmarkObservationLineage, MonitorDefinitionLatestEvaluationPortfolioTruthBasis, MonitorDefinitionLatestEvaluationSnapshotArtifact, MonitorDefinitionObservationArtifact, MonitorDefinitionObservationEvaluationResponse, OptimizerHandoffReplayRequest, OptimizerHandoffReplayResponse, OptimizerHandoffValidationRequest, OptimizerHandoffWorkspaceReviewBasis, PortfolioAllocationBacktestResponse, PortfolioDiagnosticsComparisonRow, PortfolioDiagnosticsProvenance, PortfolioDiagnosticsSnapshot, PortfolioDiagnosticsTopCallout, PortfolioWeightInput, ReplacementIntentReplayInput, ReviewSnapshotActiveThesisCrossFamilyQueueRequest, ReviewSnapshotComparisonRequest, ReviewSnapshotCreateRequest, ReviewSnapshotFamilyInboxRequest, ReviewSnapshotFamilyKey, ReviewSnapshotFamilyReviewRequest, ReviewSnapshotOpenHandoff, SingleReplacementCandidateConstructionRequest, SingleReplacementConstraintValidationState, SingleReplacementConstructionConstraintSetInput, SingleReplacementConstructionConstraintValidationRequest, SingleReplacementConstructionConstraintValidationResponse, WorkspaceReviewWindow
from app.schemas.optimizer import OptimizationRequest, OptimizerAlphaFundamentalSnapshot, OptimizerObjective, OptimizerPreviewBenchmarkInput, OptimizerPreviewRequest, OptimizerPreviewSnapshotReference, OptimizerBenchmarkRelativeConstraint, OptimizerHardConstraints, OptimizerPositionLimitConstraint, OptimizerReturnBasisAttestation, OptimizerReturnBasisEvidenceBundle, OptimizerReturnBasisSectionTrust, OptimizerTurnoverConstraint, OptimizerUniverseAsset, OptimizerWeight
from app.schemas.research import InvestorEconomicsStatus
from app.schemas.reconciliation import FactorRiskContributionItem, RiskConcentrationSnapshot, RiskContributionBreakdownPayload, SnapshotItem, StressScenarioResult, VolatilitySnapshot
from app.schemas.return_basis import ReturnBasisEvidence
from app.schemas.construction import ConstructionRunRequest
from app.services import construction_policy_catalog
from app.services.optimizer_artifact_service import OptimizerHandoffStore
from app.services.construction_artifact_service import ConstructionArtifactMissingFileError, ConstructionArtifactStore, _canonical_json
from app.services.construction_run_service import build_construction_run
from app.services.optimizer_handoff_constraints import OptimizerHandoffValidationBlockedError, validate_optimizer_handoff_constraints
from app.services.optimizer_alpha_service import build_alpha_quality_package
from app.services.optimizer_preview_service import build_optimizer_preview
from app.services.optimizer_service import run_optimizer
from app.services.monitor_definition_artifact_service import MonitorDefinitionDiscoveryMetadataValidationError, MonitorDefinitionIntegrityValidationError, MonitorDefinitionPersistenceError, MonitorDefinitionSchemaValidationError, MonitorDefinitionArtifactStore, build_stable_monitor_definition_evaluation_history_entry, build_stable_monitor_definition_observation, create_monitor_definition_artifact, get_monitor_definition_alert_review_timeline, inspect_monitor_definition_evaluation_history_entry, list_monitor_definition_active_alert_episode_inbox, list_monitor_definition_alert_history_queue, list_monitor_definition_artifacts, list_monitor_definition_catalog, list_monitor_definition_evaluation_history, list_monitor_definition_latest_observation_alert_inbox, list_monitor_definition_recovered_alert_review_queue, list_recent_monitor_definition_artifacts, load_monitor_definition_artifact, load_monitor_definition_evaluation_history_entry, load_monitor_definition_latest_evaluation_snapshot, load_monitor_definition_observation, persist_monitor_definition_evaluation_artifacts
from app.services.portfolio_backtest_engine import _apply_return_basis_attestation_to_replay_comparison, _apply_return_basis_attestation_to_replay_result, _build_backtest_diagnostics_inputs, _build_candidate_weights_from_replacement_intent, _build_diagnostics_comparison, _build_snapshot_baseline_weights, _build_synthetic_snapshot_from_weights, _compare_results, _review_snapshot_family_key_from_artifact, build_construction_artifact_replay_preview, build_hypothetical_replacement_replay_preview, build_optimizer_handoff_replay_preview, build_review_snapshot_active_thesis_cross_family_queue, build_review_snapshot_family_inbox, build_review_snapshot_family_review, compare_review_snapshots, create_review_snapshot_artifact, evaluate_monitor_definition_observation, open_review_snapshot_artifact, preflight_construction_artifact_replay, resolve_and_validate_construction_artifact_replay_params, resolve_construction_artifact_replay_params, validate_construction_artifact_replay_params
from app.services.candidate_constraints import CONSTRAINT_SET_ID, validate_single_replacement_candidate_construction_constraints
from app.services.candidate_construction import RULE_ID_FIXED_SPLIT, build_single_replacement_candidate_construction
from fastapi.testclient import TestClient

from app.api.main import app


def _history(*prices: float) -> list[dict]:
    dates = ["2024-01-02", "2024-01-31", "2024-02-01", "2024-06-03", "2024-12-31"]
    return [{"date": date, "price": price} for date, price in zip(dates[: len(prices)], prices, strict=False)]


def _draft_snapshot(*positions: tuple[str, float]) -> DraftPortfolioSnapshotInput:
    return DraftPortfolioSnapshotInput(
        base_currency="USD",
        imported_meta=DraftPortfolioImportedMetaInput(
            importer="interactive_brokers",
            statement_period="2025-01-01 - 2025-12-31",
            imported_at=datetime(2026, 4, 10),
            source_file_names=["IB2025.pdf"],
        ),
        positions=[
            DraftPortfolioPositionInput(symbol=symbol, market_value=market_value, quantity=1.0, currency="USD", source_type="etf")
            for symbol, market_value in positions
        ],
        cash_balances=[],
    )


def _replacement_intent(base_symbol: str = "VUAA", candidate_symbol: str = "IUFS") -> ReplacementIntentReplayInput:
    return ReplacementIntentReplayInput(
        kind="etf_replacement_intent",
        source="candidate_seed",
        created_at=datetime(2026, 4, 15, 0, 5, 0),
        draft_id="draft-1",
        workspace_id="workspace-1",
        base_node_id="node-1",
        base_symbol=base_symbol,
        candidate_symbol=candidate_symbol,
        seeded_from_draft_id="draft-1",
        seed_ranking_id="etf_ranking_engine_v1",
        seed_methodology_id="etf_ranking_methodology_v1",
        seed_ranking_basis_date="2026-04-15",
        peer_group="Sector UCITS ETF",
        benchmark_symbol="SPY",
        lookback_months=6,
        confidence="medium",
        holdings_support="mixed",
        warning_count=1,
    )


def _optimizer_preview_request() -> OptimizerPreviewRequest:
    return OptimizerPreviewRequest(
        request_id="preview-1",
        universe_id="optimizer_universe_large_cap_demo_v1",
        snapshot=_build_imported_snapshot_for_optimizer(),
        benchmark=OptimizerPreviewBenchmarkInput(
            benchmark_id="benchmark_spy_demo_v1",
            benchmark_version="2024-04-15",
            benchmark_symbol="SPY",
            source_name="test_benchmark_contract",
            as_of_timestamp="2024-12-31T09:30:00",
            weights=[
                OptimizerWeight(symbol="AAA", weight=0.50),
                OptimizerWeight(symbol="BBB", weight=0.30),
                OptimizerWeight(symbol="CCC", weight=0.20),
            ],
        ),
        universe=[
            OptimizerUniverseAsset(symbol="AAA", eligible=True),
            OptimizerUniverseAsset(symbol="BBB", eligible=True),
            OptimizerUniverseAsset(symbol="CCC", eligible=True),
        ],
        hard_constraints=OptimizerHardConstraints(
            benchmark_relative=OptimizerBenchmarkRelativeConstraint(max_abs_active_weight=0.10),
            position_limits=OptimizerPositionLimitConstraint(default_max_weight=0.60),
            turnover=OptimizerTurnoverConstraint(max_turnover=None),
        ),
    )


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


def _mutate_persisted_json(path: str, mutator) -> None:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    mutator(payload)
    Path(path).write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")


def _rekey_monitor_definition_observation_payload(path: Path, mutator) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutator(payload)
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
    observation_fingerprint = sha256(_canonical_json(observation_payload).encode("utf-8")).hexdigest()
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
    history_payload = dict(payload)
    history_entry_id = f"monitor_definition_history_{sha256(_canonical_json(history_payload).encode('utf-8')).hexdigest()[:16]}"
    history_payload["history_entry_id"] = history_entry_id
    history_dir = tmp_path / f"{monitor_definition_id}.history"
    history_dir.mkdir(parents=True, exist_ok=True)
    (history_dir / f"{history_entry_id}.json").write_text(
        json.dumps(history_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )
    return history_entry_id


def _hypothetical_review_payload() -> PortfolioAllocationBacktestResponse:
    return PortfolioAllocationBacktestResponse.model_validate({
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
            "assumptions": {"price_basis": "adjusted_close", "execution_price_field": "close", "execution_lag_days": 1, "calendar_policy": "intersection_common_dates", "fractional_shares": True, "long_only": True, "leverage_allowed": False, "tax_treatment": "pre_tax", "investor_base_currency": "USD"},
            "status": "ok",
            "investor_economics_status": {"status": "available", "reason": None},
            "instrument_metadata": [],
            "starting_weights": [{"symbol": "AAPL", "target_weight": 1.0}],
            "ending_weights": [{"symbol": "AAPL", "target_weight": 1.0}],
            "metrics": {"total_return_pct": 8, "annualized_return_pct": 8, "annualized_volatility_pct": 10, "downside_volatility_pct": 6, "max_drawdown_pct": -4, "sharpe_ratio": 0.8, "sortino_ratio": 1.0, "benchmark_return_pct": 7, "excess_return_pct": 1, "tracking_error_pct": 3, "information_ratio": 0.3, "beta_vs_benchmark": 1, "correlation_vs_benchmark": 0.9, "total_turnover_pct": 0, "turnover_events_count": 0, "total_cost_paid": 0},
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
            "assumptions": {"price_basis": "adjusted_close", "execution_price_field": "close", "execution_lag_days": 1, "calendar_policy": "intersection_common_dates", "fractional_shares": True, "long_only": True, "leverage_allowed": False, "tax_treatment": "pre_tax", "investor_base_currency": "USD"},
            "status": "ok",
            "investor_economics_status": {"status": "available", "reason": None},
            "instrument_metadata": [],
            "starting_weights": [{"symbol": "IUFS", "target_weight": 1.0}],
            "ending_weights": [{"symbol": "IUFS", "target_weight": 1.0}],
            "metrics": {"total_return_pct": 10, "annualized_return_pct": 10, "annualized_volatility_pct": 9, "downside_volatility_pct": 5, "max_drawdown_pct": -3, "sharpe_ratio": 1.1, "sortino_ratio": 1.3, "benchmark_return_pct": 7, "excess_return_pct": 3, "tracking_error_pct": 4, "information_ratio": 0.5, "beta_vs_benchmark": 0.8, "correlation_vs_benchmark": 0.85, "total_turnover_pct": 12, "turnover_events_count": 2, "total_cost_paid": 45},
            "equity_curve": [],
            "rebalance_events": [],
            "trades": [],
        },
        "comparison": {"total_return_diff_pct": 2, "annualized_return_diff_pct": 2, "benchmark_return_diff_pct": 0, "annualized_volatility_diff_pct": -1, "downside_volatility_diff_pct": -1, "max_drawdown_diff_pct": 1, "sharpe_diff": 0.3, "sortino_diff": 0.3, "excess_return_diff_pct": 2, "tracking_error_diff_pct": 1, "information_ratio_diff": 0.2, "beta_diff": -0.2, "correlation_diff": -0.05, "total_turnover_diff_pct": 12, "total_cost_diff": 45},
        "reference_diagnostics": None,
        "candidate_diagnostics": None,
        "diagnostics_comparison": None,
    })


def _review_snapshot_request(candidate_symbol: str = "IUFS"):
    return {
        "proposal_id": f"proposal-{candidate_symbol}",
        "workspace_id": "workspace-1",
        "source_draft_id": "draft-1",
        "source_base_node_id": "node-1",
        "proposal_family_id": f"etf_replacement_intent:AAPL:{candidate_symbol}:2026-04-15T00:05:00Z",
        "version_number": 1,
        "review_payload": {
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
                "upstream_ids": {"draft_id": "draft-1", "workspace_id": "workspace-1", "base_node_id": "node-1"},
                "seed_ranking_id": "etf_ranking_engine_v1",
                "seed_methodology_id": "etf_ranking_methodology_v1",
                "constraint_validation": {"supplied": False, "validation_status": None, "constraint_set_id": None},
            },
            "baseline_weights": [{"symbol": "AAPL", "target_weight": 1.0}],
            "candidate_weights": [{"symbol": candidate_symbol, "target_weight": 1.0}],
            "replay": _hypothetical_review_payload().model_dump(mode="json"),
            "warnings": [],
        },
    }


def _rewrite_construction_artifact_payload(tmp_path: Path, artifact_id: str, payload_mutator) -> str:
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


CONSTRUCTION_ARTIFACT_FIXTURE_DIR = Path(__file__).with_name("fixtures") / "construction_artifacts"


def _persist_construction_artifact_fixture(tmp_path: Path, fixture_name: str) -> tuple[str, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    payload = json.loads((CONSTRUCTION_ARTIFACT_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    artifact_path = tmp_path / f"{payload['artifact_id']}.json"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    return payload["artifact_id"], payload


def _construction_artifact_replay_histories() -> dict[str, list[dict]]:
    return {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
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


def _construction_artifact_replay_request(artifact_id: str) -> ConstructionArtifactReplayRequest:
    return ConstructionArtifactReplayRequest(
        construction_artifact_id=artifact_id,
        start_date=date(2024, 1, 1),
        end_date=date(2024, 12, 31),
        initial_capital=100000,
        execution_lag_days=1,
    )


def test_resolve_construction_artifact_replay_params_uses_backend_defaults_when_request_omits_frontend_defaults() -> None:
    effective = resolve_construction_artifact_replay_params(
        ConstructionArtifactReplayRequest(construction_artifact_id="artifact-123")
    )

    assert effective.model_dump(mode="json") == {
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


def test_resolve_construction_artifact_replay_params_prefers_explicit_request_overrides() -> None:
    effective = resolve_construction_artifact_replay_params(
        ConstructionArtifactReplayRequest(
            construction_artifact_id="artifact-123",
            benchmark_symbol="QQQ",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=250000,
            rebalance_frequency="quarterly",
            base_currency="EUR",
            commission_bps=4.5,
            slippage_bps=6.5,
            drift_tolerance_pct=2.0,
            execution_lag_days=3,
            symbol_overrides={"AAA": ["QQQ"]},
        )
    )

    assert effective.model_dump(mode="json") == {
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


def test_resolve_and_validate_construction_artifact_replay_params_rejects_invalid_resolved_defaults() -> None:
    with pytest.raises(ValueError, match="end_date must be on or after start_date"):
        resolve_and_validate_construction_artifact_replay_params(
            ConstructionArtifactReplayRequest(
                construction_artifact_id="artifact-123",
                start_date=date(2024, 12, 31),
                end_date=date(2024, 1, 1),
            )
        )


def test_validate_construction_artifact_replay_params_requires_openable_artifact(tmp_path) -> None:
    artifact_store = ConstructionArtifactStore(str(tmp_path))

    with pytest.raises(ConstructionArtifactMissingFileError, match="missing persisted construction artifact file"):
        validate_construction_artifact_replay_params(
            _construction_artifact_replay_request("construction_artifact_missing"),
            artifact_store=artifact_store,
        )


def _update_constraint_evaluation(payload: dict, constraint_id: str, **updates) -> None:
    payload["constraint_evaluations"] = [
        {**item, **updates} if item["constraint_id"] == constraint_id else item
        for item in payload["constraint_evaluations"]
    ]


def _update_benchmark_attestation(payload: dict, attestation_id: str, **updates) -> None:
    payload["benchmark_relative_attestations"] = [
        {**item, **updates} if item["attestation_id"] == attestation_id else item
        for item in payload["benchmark_relative_attestations"]
    ]


def _build_imported_snapshot_for_optimizer():
    from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement

    return ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2024, 4, 15, 9, 30),
            source_path="IB2024.pdf",
            detected_format="statement_pdf",
            account_id="U1234567",
            base_currency="USD",
            statement_period="2024-04",
            page_count=4,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=500.0)],
        positions=[
            ImportedPosition(as_of_date=datetime(2024, 1, 1).date(), symbol="AAA", quantity=10.0, cost_basis=60.0, close_price=6.0, market_value=60.0, unrealized_pnl=0.0, currency="USD"),
            ImportedPosition(as_of_date=datetime(2024, 1, 1).date(), symbol="BBB", quantity=8.0, cost_basis=40.0, close_price=5.0, market_value=40.0, unrealized_pnl=0.0, currency="USD"),
        ],
        ledger_entries=[],
    )


def _monitor_benchmark_observation(
    *,
    status: Literal["risk_on", "risk_reduced", "unconfirmed", "unavailable"] = "risk_reduced",
    confirmation_count: int = 2,
) -> BenchmarkTrendOverlayMonitorBenchmarkObservationInput:
    return BenchmarkTrendOverlayMonitorBenchmarkObservationInput(
        overlay_id="benchmark_trend_overlay_v1",
        status=status,
        as_of_month_end=date(2024, 12, 31),
        benchmark_symbol="SPY",
        signal_basis="10_month_sma_month_end",
        confirmation_count=confirmation_count,
        rule_version="v1",
        source_lineage=BenchmarkTrendOverlayObservationSourceLineage(
            source_kind="benchmark_overlay_signal",
            source_id="overlay-signal-2024-12-31",
            observed_at=datetime(2025, 1, 2, 9, 30),
        ),
    )


def _return_basis_attestation_for_test(
    benchmark_relative_path: Literal["verified_adjusted_close", "degraded_unverified_return_basis", "unavailable"] = "degraded_unverified_return_basis",
) -> OptimizerReturnBasisAttestation:
    evidence = ReturnBasisEvidence(
        verification_status="unverified",
        economic_basis="adjusted_close_proxy",
        construction_method="vendor_adjusted_close",
        source_price_field="adjClose",
    )
    return OptimizerReturnBasisAttestation(
        benchmark_symbol="SPY",
        as_of_date="2024-04-15",
        history_start_date="2024-01-01",
        history_end_date="2024-12-31",
        factor_proxy_symbols=["IWD", "IWM"],
        benchmark_return_basis_contract="unverified_adjusted_proxy",
        factor_return_basis_contract="unverified_adjusted_proxy",
        factor_basis_path="degraded_unverified_return_basis",
        section_trust=OptimizerReturnBasisSectionTrust(
            benchmark_relative_path=benchmark_relative_path,
            factor_model_path="degraded_unverified_return_basis",
            risk_contribution_path="degraded_unverified_return_basis",
        ),
        evidence=OptimizerReturnBasisEvidenceBundle(
            benchmark_history=evidence,
            factor_history=evidence,
        ),
    )


def _constructed_candidate_and_constraint_validation() -> tuple[ConstructedCandidateReplayInput, SingleReplacementConstructionConstraintValidationResponse]:
    constructed_candidate = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID_FIXED_SPLIT),
        )
    )
    constructed_candidate_input = ConstructedCandidateReplayInput.model_validate(constructed_candidate.model_dump(mode="json"))
    constraint_validation = validate_single_replacement_candidate_construction_constraints(
        SingleReplacementConstructionConstraintValidationRequest(
            constructed_candidate=constructed_candidate_input,
            constraint_set=SingleReplacementConstructionConstraintSetInput(constraint_set_id=CONSTRAINT_SET_ID),
        )
    )
    return constructed_candidate_input, constraint_validation


def _clone_constraint_validation(
    constraint_validation: SingleReplacementConstructionConstraintValidationResponse,
) -> SingleReplacementConstructionConstraintValidationResponse:
    return SingleReplacementConstructionConstraintValidationResponse.model_validate(constraint_validation.model_dump(mode="json"))


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
        investor_economics_status=InvestorEconomicsStatus(status="withheld", reason="withheld_unverified_total_return_equivalence"),
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
        investor_economics_status=InvestorEconomicsStatus(status="withheld", reason="withheld_unverified_total_return_equivalence"),
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


def test_build_snapshot_baseline_weights_uses_draft_snapshot_market_values_without_extra_normalization() -> None:
    weights = _build_snapshot_baseline_weights(_draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)))

    assert weights == [
        PortfolioWeightInput(symbol="VUAA", target_weight=0.6),
        PortfolioWeightInput(symbol="IB01", target_weight=0.4),
    ]


def test_build_candidate_weights_from_replacement_intent_performs_exact_one_for_one_substitution() -> None:
    baseline = [
        PortfolioWeightInput(symbol="VUAA", target_weight=0.6),
        PortfolioWeightInput(symbol="IB01", target_weight=0.4),
    ]

    candidate = _build_candidate_weights_from_replacement_intent(baseline, "VUAA", "IUFS")

    assert candidate == [
        PortfolioWeightInput(symbol="IB01", target_weight=0.4),
        PortfolioWeightInput(symbol="IUFS", target_weight=0.6),
    ]
    assert sum(item.target_weight for item in candidate) == 1.0


def test_build_diagnostics_comparison_adds_explicit_top_callouts() -> None:
    baseline = PortfolioDiagnosticsSnapshot(
        provenance=PortfolioDiagnosticsProvenance(snapshot_basis="synthetic_replay_snapshot", historical_basis="market_data_history", note="n"),
        factor_snapshot=[SnapshotItem(key="market", label="Market", category="market", us_proxy="SPY", latest_loading=1.0, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="broad market"), SnapshotItem(key="value", label="Value", category="style", us_proxy="IWD", latest_loading=0.1, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="value")],
        volatility_snapshot=VolatilitySnapshot(realized_vol_252d=10.0, downside_vol_252d=6.0, tracking_error_252d=3.0, max_drawdown_pct=-4.0),
        risk_contribution=RiskContributionBreakdownPayload(methodology="m", window_days=60, observation_count=60, status="ok", factor_contributions=[FactorRiskContributionItem(key="market", label="Market", us_proxy="SPY", loading=1.0, factor_volatility=12.0, variance_contribution=0.01, risk_share=0.6)], factor_total_variance=0.01, specific_variance=0.005, total_variance=0.015, factor_risk_share_total=0.66, specific_risk_share=0.34, residual_volatility=5.0, position_contributions=[], concentration=RiskConcentrationSnapshot(top_1_factor_risk_share=0.6, top_3_factor_risk_share=0.6, top_1_position_risk_share=1.0, top_5_position_risk_share=1.0, factor_hhi=0.36, position_hhi=1.0)),
        stress_scenarios=[StressScenarioResult(name="Broad Market Selloff", estimated_return_pct=-8.5, description="x"), StressScenarioResult(name="Rates Shock", estimated_return_pct=-2.0, description="x")],
    )
    candidate = PortfolioDiagnosticsSnapshot(
        provenance=PortfolioDiagnosticsProvenance(snapshot_basis="synthetic_replay_snapshot", historical_basis="market_data_history", note="n"),
        factor_snapshot=[SnapshotItem(key="market", label="Market", category="market", us_proxy="SPY", latest_loading=0.8, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="broad market"), SnapshotItem(key="value", label="Value", category="style", us_proxy="IWD", latest_loading=0.4, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="value")],
        volatility_snapshot=VolatilitySnapshot(realized_vol_252d=9.0, downside_vol_252d=5.0, tracking_error_252d=4.0, max_drawdown_pct=-2.5),
        risk_contribution=RiskContributionBreakdownPayload(methodology="m", window_days=60, observation_count=60, status="ok", factor_contributions=[FactorRiskContributionItem(key="market", label="Market", us_proxy="SPY", loading=0.8, factor_volatility=11.0, variance_contribution=0.008, risk_share=0.3), FactorRiskContributionItem(key="value", label="Value", us_proxy="IWD", loading=0.4, factor_volatility=9.0, variance_contribution=0.007, risk_share=0.55)], factor_total_variance=0.015, specific_variance=0.004, total_variance=0.019, factor_risk_share_total=0.8, specific_risk_share=0.2, residual_volatility=4.5, position_contributions=[], concentration=RiskConcentrationSnapshot(top_1_factor_risk_share=0.55, top_3_factor_risk_share=0.55, top_1_position_risk_share=0.7, top_5_position_risk_share=1.0, factor_hhi=0.2, position_hhi=0.58)),
        stress_scenarios=[StressScenarioResult(name="Broad Market Selloff", estimated_return_pct=-6.0, description="x"), StressScenarioResult(name="Rates Shock", estimated_return_pct=-5.5, description="x")],
    )

    comparison = _build_diagnostics_comparison(baseline, candidate)

    assert comparison.top_factor_exposure_change is not None
    assert comparison.top_factor_exposure_change == PortfolioDiagnosticsTopCallout(key="value", label="Value", baseline_value=0.1, candidate_value=0.4, delta_value=0.3, selection_rule="largest_absolute_delta", rationale="Largest valid factor exposure delta in this group (candidate - baseline).")
    assert comparison.top_volatility_change is not None
    assert comparison.top_volatility_change.key == "annualized_volatility"
    assert comparison.top_volatility_change.selection_rule == "fixed_priority"
    assert "drawdown surfaces" in comparison.top_volatility_change.rationale
    assert comparison.top_risk_contribution_change is not None
    assert comparison.top_risk_contribution_change.key == "market"
    assert comparison.top_concentration_change is not None
    assert comparison.top_concentration_change.key == "factor_hhi"
    assert comparison.top_stress_scenario_change is not None
    assert comparison.top_stress_scenario_change.key == "rates_shock"


def test_build_diagnostics_comparison_returns_null_top_callouts_when_groups_have_no_eligible_rows() -> None:
    empty = PortfolioDiagnosticsSnapshot(
        provenance=PortfolioDiagnosticsProvenance(snapshot_basis="synthetic_replay_snapshot", historical_basis="market_data_history", note="n"),
        factor_snapshot=[SnapshotItem(key="market", label="Market", category="market", us_proxy="SPY", latest_loading=None, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="broad market")],
        volatility_snapshot=VolatilitySnapshot(realized_vol_252d=None, downside_vol_252d=None, tracking_error_252d=None, max_drawdown_pct=None),
        risk_contribution=None,
        stress_scenarios=[],
    )

    comparison = _build_diagnostics_comparison(empty, empty)

    assert comparison.top_factor_exposure_change is None
    assert comparison.top_volatility_change is None
    assert comparison.top_risk_contribution_change is None
    assert comparison.top_concentration_change is None
    assert comparison.top_stress_scenario_change is None


def test_compare_results_returns_null_diffs_for_refused_investor_economics_metrics() -> None:
    reference = AllocationBacktestResult(
        portfolio_name="Reference",
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
        investor_economics_status=InvestorEconomicsStatus(status="withheld", reason="withheld_unverified_total_return_equivalence"),
        instrument_metadata=[],
        starting_weights=[],
        ending_weights=[],
        metrics=AllocationBacktestMetrics(
            total_return_pct=None,
            annualized_return_pct=None,
            annualized_volatility_pct=10.0,
            downside_volatility_pct=6.0,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            sortino_ratio=None,
            benchmark_return_pct=None,
            excess_return_pct=None,
            tracking_error_pct=3.0,
            information_ratio=None,
            beta_vs_benchmark=1.0,
            correlation_vs_benchmark=0.9,
            total_turnover_pct=5.0,
            total_cost_paid=10.0,
        ),
        equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=101000, cash=0)],
        rebalance_events=[],
        trades=[],
    )
    candidate = AllocationBacktestResult(
        portfolio_name="Candidate",
        benchmark_symbol="SPY",
        start_date="2024-01-01",
        end_date="2024-12-31",
        observation_count=2,
        rebalance_frequency="monthly",
        commission_bps=0,
        slippage_bps=0,
        assumptions=reference.assumptions,
        status="ok",
        investor_economics_status=InvestorEconomicsStatus(status="withheld", reason="withheld_unverified_total_return_equivalence"),
        instrument_metadata=[],
        starting_weights=[],
        ending_weights=[],
        metrics=AllocationBacktestMetrics(
            total_return_pct=None,
            annualized_return_pct=None,
            annualized_volatility_pct=9.0,
            downside_volatility_pct=5.0,
            max_drawdown_pct=None,
            sharpe_ratio=None,
            sortino_ratio=None,
            benchmark_return_pct=None,
            excess_return_pct=None,
            tracking_error_pct=4.0,
            information_ratio=None,
            beta_vs_benchmark=0.8,
            correlation_vs_benchmark=0.85,
            total_turnover_pct=12.0,
            total_cost_paid=45.0,
        ),
        equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=102000, cash=0)],
        rebalance_events=[],
        trades=[],
    )

    comparison = _compare_results(reference, candidate)

    assert comparison.total_return_diff_pct is None
    assert comparison.annualized_return_diff_pct is None
    assert comparison.benchmark_return_diff_pct is None
    assert comparison.max_drawdown_diff_pct is None
    assert comparison.sharpe_diff is None
    assert comparison.sortino_diff is None
    assert comparison.excess_return_diff_pct is None
    assert comparison.information_ratio_diff is None
    assert comparison.tracking_error_diff_pct == 1.0
    assert comparison.beta_diff == -0.2
    assert comparison.correlation_diff == -0.05


def test_apply_return_basis_attestation_to_replay_result_suppresses_top_level_benchmark_relative_metrics() -> None:
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
        investor_economics_status=InvestorEconomicsStatus(status="available", reason=None),
        instrument_metadata=[],
        starting_weights=[],
        ending_weights=[],
        metrics=AllocationBacktestMetrics(
            total_return_pct=5.0,
            annualized_return_pct=5.0,
            annualized_volatility_pct=10.0,
            downside_volatility_pct=6.0,
            max_drawdown_pct=-4.0,
            sharpe_ratio=0.5,
            sortino_ratio=0.7,
            benchmark_return_pct=4.0,
            excess_return_pct=1.0,
            tracking_error_pct=3.0,
            information_ratio=0.2,
            beta_vs_benchmark=0.9,
            correlation_vs_benchmark=0.8,
            total_turnover_pct=2.0,
            total_cost_paid=1.0,
        ),
        equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=105000, cash=0)],
        rebalance_events=[],
        trades=[],
    )

    suppressed = _apply_return_basis_attestation_to_replay_result(
        result,
        _return_basis_attestation_for_test(),
    )

    assert suppressed is not None
    assert suppressed.metrics.total_return_pct == 5.0
    assert suppressed.metrics.annualized_volatility_pct == 10.0
    assert suppressed.metrics.total_turnover_pct == 2.0
    assert suppressed.metrics.benchmark_return_pct is None
    assert suppressed.metrics.excess_return_pct is None
    assert suppressed.metrics.tracking_error_pct is None
    assert suppressed.metrics.information_ratio is None
    assert suppressed.metrics.beta_vs_benchmark is None
    assert suppressed.metrics.correlation_vs_benchmark is None


def test_apply_return_basis_attestation_to_replay_result_preserves_top_level_benchmark_relative_metrics_when_verified_adjusted_close() -> None:
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
        investor_economics_status=InvestorEconomicsStatus(status="available", reason=None),
        instrument_metadata=[],
        starting_weights=[],
        ending_weights=[],
        metrics=AllocationBacktestMetrics(
            total_return_pct=5.0,
            annualized_return_pct=5.0,
            annualized_volatility_pct=10.0,
            downside_volatility_pct=6.0,
            max_drawdown_pct=-4.0,
            sharpe_ratio=0.5,
            sortino_ratio=0.7,
            benchmark_return_pct=4.0,
            excess_return_pct=1.0,
            tracking_error_pct=3.0,
            information_ratio=0.2,
            beta_vs_benchmark=0.9,
            correlation_vs_benchmark=0.8,
            total_turnover_pct=2.0,
            total_cost_paid=1.0,
        ),
        equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=105000, cash=0)],
        rebalance_events=[],
        trades=[],
    )

    preserved = _apply_return_basis_attestation_to_replay_result(
        result,
        _return_basis_attestation_for_test(benchmark_relative_path="verified_adjusted_close"),
    )

    assert preserved is not None
    assert preserved.metrics.total_return_pct == 5.0
    assert preserved.metrics.annualized_volatility_pct == 10.0
    assert preserved.metrics.total_turnover_pct == 2.0
    assert preserved.metrics.benchmark_return_pct == 4.0
    assert preserved.metrics.excess_return_pct == 1.0
    assert preserved.metrics.tracking_error_pct == 3.0
    assert preserved.metrics.information_ratio == 0.2
    assert preserved.metrics.beta_vs_benchmark == 0.9
    assert preserved.metrics.correlation_vs_benchmark == 0.8


def test_apply_return_basis_attestation_to_replay_comparison_suppresses_top_level_benchmark_relative_diffs() -> None:
    comparison = _compare_results(
        AllocationBacktestResult(
            portfolio_name="Reference",
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
            investor_economics_status=InvestorEconomicsStatus(status="available", reason=None),
            instrument_metadata=[],
            starting_weights=[],
            ending_weights=[],
            metrics=AllocationBacktestMetrics(
                total_return_pct=4.0,
                annualized_return_pct=4.0,
                annualized_volatility_pct=11.0,
                downside_volatility_pct=7.0,
                max_drawdown_pct=-5.0,
                sharpe_ratio=0.4,
                sortino_ratio=0.6,
                benchmark_return_pct=3.0,
                excess_return_pct=1.0,
                tracking_error_pct=2.0,
                information_ratio=0.1,
                beta_vs_benchmark=1.0,
                correlation_vs_benchmark=0.9,
                total_turnover_pct=3.0,
                total_cost_paid=1.0,
            ),
            equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=104000, cash=0)],
            rebalance_events=[],
            trades=[],
        ),
        AllocationBacktestResult(
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
            investor_economics_status=InvestorEconomicsStatus(status="available", reason=None),
            instrument_metadata=[],
            starting_weights=[],
            ending_weights=[],
            metrics=AllocationBacktestMetrics(
                total_return_pct=5.0,
                annualized_return_pct=5.0,
                annualized_volatility_pct=10.0,
                downside_volatility_pct=6.0,
                max_drawdown_pct=-4.0,
                sharpe_ratio=0.5,
                sortino_ratio=0.7,
                benchmark_return_pct=4.0,
                excess_return_pct=1.0,
                tracking_error_pct=3.0,
                information_ratio=0.2,
                beta_vs_benchmark=0.9,
                correlation_vs_benchmark=0.8,
                total_turnover_pct=2.0,
                total_cost_paid=1.5,
            ),
            equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=105000, cash=0)],
            rebalance_events=[],
            trades=[],
        ),
    )

    suppressed = _apply_return_basis_attestation_to_replay_comparison(
        comparison,
        _return_basis_attestation_for_test(),
    )

    assert suppressed is not None
    assert suppressed.total_return_diff_pct == 1.0
    assert suppressed.annualized_volatility_diff_pct == -1.0
    assert suppressed.total_turnover_diff_pct == -1.0
    assert suppressed.benchmark_return_diff_pct is None
    assert suppressed.excess_return_diff_pct is None
    assert suppressed.tracking_error_diff_pct is None
    assert suppressed.information_ratio_diff is None
    assert suppressed.beta_diff is None
    assert suppressed.correlation_diff is None


def test_apply_return_basis_attestation_to_replay_comparison_preserves_top_level_benchmark_relative_diffs_when_verified_adjusted_close() -> None:
    comparison = _compare_results(
        AllocationBacktestResult(
            portfolio_name="Reference",
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
            investor_economics_status=InvestorEconomicsStatus(status="available", reason=None),
            instrument_metadata=[],
            starting_weights=[],
            ending_weights=[],
            metrics=AllocationBacktestMetrics(
                total_return_pct=4.0,
                annualized_return_pct=4.0,
                annualized_volatility_pct=11.0,
                downside_volatility_pct=7.0,
                max_drawdown_pct=-5.0,
                sharpe_ratio=0.4,
                sortino_ratio=0.6,
                benchmark_return_pct=3.0,
                excess_return_pct=1.0,
                tracking_error_pct=2.0,
                information_ratio=0.1,
                beta_vs_benchmark=1.0,
                correlation_vs_benchmark=0.9,
                total_turnover_pct=3.0,
                total_cost_paid=1.0,
            ),
            equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=104000, cash=0)],
            rebalance_events=[],
            trades=[],
        ),
        AllocationBacktestResult(
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
            investor_economics_status=InvestorEconomicsStatus(status="available", reason=None),
            instrument_metadata=[],
            starting_weights=[],
            ending_weights=[],
            metrics=AllocationBacktestMetrics(
                total_return_pct=5.0,
                annualized_return_pct=5.0,
                annualized_volatility_pct=10.0,
                downside_volatility_pct=6.0,
                max_drawdown_pct=-4.0,
                sharpe_ratio=0.5,
                sortino_ratio=0.7,
                benchmark_return_pct=4.0,
                excess_return_pct=1.0,
                tracking_error_pct=3.0,
                information_ratio=0.2,
                beta_vs_benchmark=0.9,
                correlation_vs_benchmark=0.8,
                total_turnover_pct=2.0,
                total_cost_paid=1.5,
            ),
            equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=105000, cash=0)],
            rebalance_events=[],
            trades=[],
        ),
    )

    preserved = _apply_return_basis_attestation_to_replay_comparison(
        comparison,
        _return_basis_attestation_for_test(benchmark_relative_path="verified_adjusted_close"),
    )

    assert preserved is not None
    assert preserved.total_return_diff_pct == 1.0
    assert preserved.annualized_volatility_diff_pct == -1.0
    assert preserved.total_turnover_diff_pct == -1.0
    assert preserved.benchmark_return_diff_pct == 1.0
    assert preserved.excess_return_diff_pct == 0.0
    assert preserved.tracking_error_diff_pct == 1.0
    assert preserved.information_ratio_diff == 0.1
    assert preserved.beta_diff == -0.1
    assert preserved.correlation_diff == -0.1


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
    assert payload["reference_result"]["metrics"]["total_return_pct"] is None
    assert payload["reference_result"]["metrics"]["annualized_return_pct"] is None
    assert payload["reference_result"]["metrics"]["max_drawdown_pct"] is None
    assert payload["reference_result"]["metrics"]["sharpe_ratio"] is None
    assert payload["reference_result"]["metrics"]["sortino_ratio"] is None
    assert payload["reference_result"]["metrics"]["benchmark_return_pct"] is None
    assert payload["reference_result"]["metrics"]["excess_return_pct"] is None
    assert payload["reference_result"]["metrics"]["information_ratio"] is None
    assert payload["reference_result"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["candidate_result"]["metrics"]["total_return_pct"] is None
    assert payload["candidate_result"]["metrics"]["annualized_return_pct"] is None
    assert payload["candidate_result"]["metrics"]["max_drawdown_pct"] is None
    assert payload["candidate_result"]["metrics"]["sharpe_ratio"] is None
    assert payload["candidate_result"]["metrics"]["sortino_ratio"] is None
    assert payload["candidate_result"]["metrics"]["benchmark_return_pct"] is None
    assert payload["candidate_result"]["metrics"]["excess_return_pct"] is None
    assert payload["candidate_result"]["metrics"]["information_ratio"] is None
    assert payload["candidate_result"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["candidate_result"]["metrics"]["tracking_error_pct"] is not None
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


def test_hypothetical_replacement_preview_route_returns_proposal_derivation_and_wrapped_replay(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IUFS": _history(100.0, 103.0, 103.5, 105.0, 109.0),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
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
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {
                    "importer": "interactive_brokers",
                    "statement_period": "2025-01-01 - 2025-12-31",
                    "imported_at": "2026-04-10T00:00:00Z",
                    "source_file_names": ["IB2025.pdf"],
                },
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "commission_bps": 2,
            "slippage_bps": 3,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal"] == {
        "source": "draft_replacement_intent",
        "proposal_source": {
            "proposal_source_version": 1,
            "proposal_source_kind": "draft_replacement_intent_review_only",
            "proposal_truth": "review_only_hypothetical_proposal",
            "portfolio_truth": "draft_snapshot_not_applied",
            "review_scope": "proposal_review_context_only",
        },
        "incumbent_symbol": "VUAA",
        "candidate_symbol": "IUFS",
        "draft_id": "draft-1",
        "base_node_id": "node-1",
    }
    assert payload["derivation"] == {
        "baseline_basis": "draft_snapshot_positions_normalized",
        "candidate_construction_rule": "same_weight_substitution_v1",
    }
    assert payload["replay_provenance"] == {
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
    }
    assert payload["baseline_weights"] == [
        {"symbol": "VUAA", "target_weight": 0.6},
        {"symbol": "IB01", "target_weight": 0.4},
    ]
    assert payload["candidate_weights"] == [
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.6},
    ]
    assert payload["replay"]["reference_result"] is not None
    assert payload["replay"]["methodology_provenance"] == {
        "provenance_version": 1,
        "source": "portfolio_allocation_backtest_engine",
        "methodology_truth": "review_only_replay_methodology",
        "assumptions_truth": "review_only_replay_assumptions",
        "analytics_truth": "hypothetical_replay_analytics_only",
        "review_scope": "workspace_review_context_only",
    }
    assert payload["replay"]["candidate_result"]["portfolio_name"] == "Hypothetical Candidate"
    assert payload["replay"]["candidate_result"]["commission_bps"] == 2
    assert payload["replay"]["candidate_result"]["slippage_bps"] == 3
    assert payload["replay"]["reference_result"]["metrics"]["total_return_pct"] is None
    assert payload["replay"]["reference_result"]["metrics"]["annualized_return_pct"] is None
    assert payload["replay"]["reference_result"]["metrics"]["max_drawdown_pct"] is None
    assert payload["replay"]["reference_result"]["metrics"]["sharpe_ratio"] is None
    assert payload["replay"]["reference_result"]["metrics"]["sortino_ratio"] is None
    assert payload["replay"]["reference_result"]["metrics"]["benchmark_return_pct"] is None
    assert payload["replay"]["reference_result"]["metrics"]["excess_return_pct"] is None
    assert payload["replay"]["reference_result"]["metrics"]["information_ratio"] is None
    assert payload["replay"]["reference_result"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["replay"]["candidate_result"]["metrics"]["total_return_pct"] is None
    assert payload["replay"]["candidate_result"]["metrics"]["annualized_return_pct"] is None
    assert payload["replay"]["candidate_result"]["metrics"]["max_drawdown_pct"] is None
    assert payload["replay"]["candidate_result"]["metrics"]["sharpe_ratio"] is None
    assert payload["replay"]["candidate_result"]["metrics"]["sortino_ratio"] is None
    assert payload["replay"]["candidate_result"]["metrics"]["benchmark_return_pct"] is None
    assert payload["replay"]["candidate_result"]["metrics"]["excess_return_pct"] is None
    assert payload["replay"]["candidate_result"]["metrics"]["information_ratio"] is None
    assert payload["replay"]["candidate_result"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["replay"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["replay"]["candidate_result"]["metrics"]["tracking_error_pct"] is not None
    assert payload["replay"]["candidate_diagnostics"]["provenance"]["snapshot_basis"] == "synthetic_replay_snapshot"
    assert payload["replay"]["diagnostics_comparison"]["top_factor_exposure_change"] is not None
    top_volatility_change = payload["replay"]["diagnostics_comparison"]["top_volatility_change"]
    if top_volatility_change is not None:
        assert top_volatility_change["key"] != "max_drawdown"
    assert payload["replay"]["diagnostics_comparison"]["top_factor_exposure_change"]["selection_rule"] == "largest_absolute_delta"
    assert "candidate - baseline" in payload["replay"]["diagnostics_comparison"]["top_factor_exposure_change"]["rationale"]


def test_build_optimizer_handoff_replay_preview_runs_from_explicit_persisted_reference(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 103.0, 104.0, 106.0, 109.0),
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
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    replay_response = build_optimizer_handoff_replay_preview(
        OptimizerHandoffReplayRequest(
            handoff_reference=preview_response.persisted_handoff,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        handoff_store=handoff_store,
    )

    assert replay_response.handoff_id == preview_response.persisted_handoff.handoff_id
    assert replay_response.review_basis.handoff_reference.artifact_id == preview_response.optimizer_artifact.artifact_id
    assert replay_response.source_portfolio_snapshot_id.startswith("portfolio_snapshot_")
    assert replay_response.truth_separation.model_dump() == {
        "baseline_truth": "imported_portfolio_snapshot",
        "candidate_truth": "hypothetical_optimizer_handoff",
        "candidate_applied": False,
        "consumption_mode": "explicit_reference_only",
    }
    assert replay_response.review_basis.model_dump(mode="json") == {
        "basis_version": 1,
        "basis_kind": "persisted_optimizer_handoff_review",
        "review_scope": "workspace_review_only",
        "canonical_source": "persisted_handoff_reference",
        "basis_provenance_label": "artifact_backed_review_basis",
        "portfolio_truth": "imported_portfolio_snapshot",
        "candidate_truth": "hypothetical_optimizer_handoff",
        "handoff_reference": preview_response.persisted_handoff.model_dump(mode="json"),
        "benchmark_symbol": "SPY",
        "base_currency": "USD",
        "replay_window": {
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
        },
        "baseline_weights": [
            {"symbol": "AAA", "target_weight": 0.6},
            {"symbol": "BBB", "target_weight": 0.4},
        ],
        "candidate_weights": [
            {"symbol": "AAA", "target_weight": 0.5},
            {"symbol": "BBB", "target_weight": 0.3},
            {"symbol": "CCC", "target_weight": 0.2},
        ],
    }
    assert replay_response.replay_provenance.benchmark_id == "benchmark_spy_demo_v1"
    assert replay_response.replay_provenance.benchmark_version == "2024-04-15"
    assert replay_response.replay_provenance.benchmark_symbol == "SPY"
    assert replay_response.replay_provenance.return_basis_attestation.benchmark_symbol == "SPY"
    assert replay_response.replay_provenance.replay_output_policy.model_dump() == {
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
    assert replay_response.replay.reference_result is not None
    assert replay_response.replay.comparison is not None
    assert replay_response.optimizer_context is not None
    assert "objective_id" not in replay_response.optimizer_context.model_dump()
    assert replay_response.optimizer_context.objective is not None
    assert replay_response.optimizer_context.objective.objective_id == "minimize_l2_distance_to_benchmark"
    assert replay_response.optimizer_context.run_summary.solver_id == "deterministic_projected_dykstra_v1"
    assert replay_response.optimizer_context.diagnostics.turnover == 0.2
    assert replay_response.optimizer_context.diagnostics.active_share == 0.0
    assert replay_response.optimizer_context.benchmark_relative_attestations[0].attestation_id == "benchmark_relative_max_abs_active_weight"
    assert replay_response.baseline_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.6),
        PortfolioWeightInput(symbol="BBB", target_weight=0.4),
    ]
    assert replay_response.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.5),
        PortfolioWeightInput(symbol="BBB", target_weight=0.3),
        PortfolioWeightInput(symbol="CCC", target_weight=0.2),
    ]
    assert replay_response.replay.candidate_result.portfolio_name == "Optimizer Handoff Candidate"
    assert replay_response.replay.methodology_provenance.model_dump(mode="json") == {
        "provenance_version": 1,
        "source": "portfolio_allocation_backtest_engine",
        "methodology_truth": "review_only_replay_methodology",
        "assumptions_truth": "review_only_replay_assumptions",
        "analytics_truth": "hypothetical_replay_analytics_only",
        "review_scope": "workspace_review_context_only",
    }
    assert replay_response.replay.reference_result.metrics.tracking_error_pct is None
    assert replay_response.replay.reference_result.metrics.beta_vs_benchmark is None
    assert replay_response.replay.reference_result.metrics.correlation_vs_benchmark is None
    assert replay_response.replay.candidate_result.metrics.tracking_error_pct is None
    assert replay_response.replay.candidate_result.metrics.beta_vs_benchmark is None
    assert replay_response.replay.candidate_result.metrics.correlation_vs_benchmark is None
    assert replay_response.replay.comparison.tracking_error_diff_pct is None
    assert replay_response.replay.comparison.beta_diff is None
    assert replay_response.replay.comparison.correlation_diff is None


def test_build_optimizer_handoff_replay_preview_uses_persisted_benchmark_symbol_only(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 103.0, 104.0, 106.0, 109.0),
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
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    replay_response = build_optimizer_handoff_replay_preview(
        OptimizerHandoffReplayRequest(
            handoff_reference=preview_response.persisted_handoff,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        handoff_store=handoff_store,
    )

    assert replay_response.replay_provenance.benchmark_symbol == "SPY"
    assert replay_response.replay_provenance.replay_output_policy.withheld_families == [
        "benchmark_relative_volatility_outputs",
        "factor_exposure_outputs",
        "stress_scenario_outputs",
        "risk_contribution_outputs",
        "concentration_outputs",
    ]
    assert replay_response.replay.candidate_result.benchmark_symbol == "SPY"
    assert replay_response.replay.candidate_result.metrics.tracking_error_pct is None
    assert replay_response.replay.candidate_result.metrics.beta_vs_benchmark is None
    assert replay_response.replay.candidate_result.metrics.correlation_vs_benchmark is None
    assert replay_response.replay.candidate_diagnostics is not None
    assert replay_response.replay.candidate_diagnostics.factor_snapshot == []
    assert replay_response.replay.candidate_diagnostics.risk_contribution is not None
    assert replay_response.replay.candidate_diagnostics.risk_contribution.factor_contributions == []
    assert replay_response.replay.diagnostics_comparison is not None
    assert replay_response.replay.diagnostics_comparison.factor_exposure_changes == []


def test_build_construction_artifact_replay_preview_uses_persisted_final_target_weights_and_normalized_baseline(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
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
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-1",
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
        }),
        artifact_store=artifact_store,
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=artifact.artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert artifact.weighting_trace_v1 is not None
    assert artifact.turnover_diagnostics_v1 is not None
    assert replay_response.construction_artifact_id == artifact.artifact_id
    assert replay_response.truth_separation.model_dump() == {
        "baseline_truth": "imported_portfolio_snapshot",
        "candidate_truth": "hypothetical_construction_artifact",
        "candidate_applied": False,
        "consumption_mode": "explicit_reference_only",
    }
    assert replay_response.replay_provenance.model_dump() == {
        "source": "construction_artifact_reference",
        "construction_artifact_id": artifact.artifact_id,
        "policy_id": "top_n_equal_weight_v1",
        "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
        "ranked_universe_artifact_id": "ranking_artifact_1",
        "ranked_universe_artifact_schema_version": None,
        "ranking_id": "ranked_candidates_v1",
        "ranking_methodology_id": "ranked_candidates_methodology_v1",
        "ranking_as_of_date": "2026-04-23",
        "current_portfolio_artifact_id": "portfolio_snapshot_1",
        "current_portfolio_as_of_timestamp": "2026-04-23T09:30:00",
        "top_n": 2,
        "hard_constraints": artifact.hard_constraints.model_dump(mode="json"),
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
        "turnover_diagnostics_v1": artifact.turnover_diagnostics_v1.model_dump(mode="json"),
        "weighting_trace_status": "available",
        "weighting_trace_v1": artifact.weighting_trace_v1.model_dump(mode="json"),
    }
    assert replay_response.baseline_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.6),
        PortfolioWeightInput(symbol="BBB", target_weight=0.4),
    ]
    assert replay_response.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.5),
        PortfolioWeightInput(symbol="BBB", target_weight=0.5),
    ]
    assert replay_response.effective_replay_params.model_dump(mode="json") == {
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
    assert replay_response.replay.reference_result is not None
    assert replay_response.replay.candidate_result.portfolio_name == "Construction Artifact Candidate"


def test_build_construction_artifact_replay_preview_applies_override_precedence_and_echoes_effective_params(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "QQQ": _history(100.0, 101.0, 102.0, 103.0, 110.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
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
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-override-precedence",
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
        }),
        artifact_store=artifact_store,
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=artifact.artifact_id,
            benchmark_symbol="QQQ",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=250000,
            rebalance_frequency="quarterly",
            base_currency="EUR",
            commission_bps=4.5,
            slippage_bps=6.5,
            drift_tolerance_pct=2.0,
            execution_lag_days=3,
            symbol_overrides={"AAA": ["QQQ"]},
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.effective_replay_params.model_dump(mode="json") == {
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
    mock_service.return_value.get_historical_prices_for_symbols.assert_called_once()
    call_args = mock_service.return_value.get_historical_prices_for_symbols.call_args
    assert call_args.args[1] == "2023-01-01"
    assert call_args.args[2] == "2023-12-31"
    assert replay_response.replay.candidate_result.benchmark_symbol == "QQQ"
    assert replay_response.replay.candidate_result.rebalance_frequency == "quarterly"
    assert replay_response.replay.candidate_result.commission_bps == 4.5
    assert replay_response.replay.candidate_result.slippage_bps == 6.5
    assert replay_response.replay.candidate_result.assumptions.execution_lag_days == 3
    assert replay_response.replay.candidate_result.assumptions.investor_base_currency == "EUR"


def test_construction_artifact_preview_and_validation_share_effective_param_resolution(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-validation-parity",
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
        }),
        artifact_store=artifact_store,
    )
    request = ConstructionArtifactReplayRequest(
        construction_artifact_id=artifact.artifact_id,
        benchmark_symbol="QQQ",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        initial_capital=250000,
        rebalance_frequency="quarterly",
        base_currency="EUR",
        commission_bps=4.5,
        slippage_bps=6.5,
        drift_tolerance_pct=2.0,
        execution_lag_days=3,
        symbol_overrides={"AAA": ["QQQ"]},
    )

    preview_response = build_construction_artifact_replay_preview(request, artifact_store=artifact_store)
    validation_response = validate_construction_artifact_replay_params(request, artifact_store=artifact_store)

    assert validation_response.effective_replay_params == preview_response.effective_replay_params
    assert validation_response.preview_handoff.model_dump(mode="json") == {
        "handoff_kind": "construction_artifact_preview_handoff_v1",
        "construction_artifact_id": artifact.artifact_id,
        "effective_replay_params": preview_response.effective_replay_params.model_dump(mode="json"),
    }
    assert validation_response.model_dump(mode="json").get("open_payload") is None


def test_construction_artifact_preview_uses_validation_preview_handoff_as_exact_contract(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-handoff-contract",
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
        }),
        artifact_store=artifact_store,
    )
    validation_request = ConstructionArtifactReplayRequest(
        construction_artifact_id=artifact.artifact_id,
        benchmark_symbol="QQQ",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        initial_capital=250000,
        rebalance_frequency="quarterly",
        base_currency="EUR",
        commission_bps=4.5,
        slippage_bps=6.5,
        drift_tolerance_pct=2.0,
        execution_lag_days=3,
        symbol_overrides={"AAA": ["QQQ"]},
    )

    validation_response = validate_construction_artifact_replay_params(validation_request, artifact_store=artifact_store)
    preview_from_handoff = build_construction_artifact_replay_preview(validation_response.preview_handoff, artifact_store=artifact_store)
    preview_from_request = build_construction_artifact_replay_preview(validation_request, artifact_store=artifact_store)

    assert preview_from_handoff.model_dump(mode="json") == preview_from_request.model_dump(mode="json")


def test_construction_artifact_preview_handoff_model_rejects_unsupported_kind() -> None:
    with pytest.raises(ValidationError):
        ConstructionArtifactPreviewHandoff.model_validate({
            "handoff_kind": "construction_artifact_preview_handoff_v0",
            "construction_artifact_id": "artifact-123",
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
        })


@pytest.mark.parametrize(
    ("payload_mutator", "expected_error", "preserve_integrity"),
    [
        (
            lambda payload: payload.__setitem__("artifact_id", "construction_artifact_wrong"),
            "construction artifact_id does not match canonical artifact content",
            False,
        ),
        (
            lambda payload: payload["normalized_inputs"].__setitem__("current_portfolio_weights", []),
            "construction artifact replay requires normalized_inputs.current_portfolio_weights for the baseline replay path",
            True,
        ),
    ],
    ids=["integrity_failure", "missing_baseline_weights"],
)
def test_validate_construction_artifact_replay_params_matches_preview_openability_gate(
    tmp_path,
    mocker,
    payload_mutator,
    expected_error,
    preserve_integrity,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-validation-openability-gate",
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
        }),
        artifact_store=artifact_store,
    )
    artifact_id = artifact.artifact_id
    if preserve_integrity:
        artifact_id = _rewrite_construction_artifact_payload(tmp_path, artifact.artifact_id, payload_mutator)
    else:
        artifact_path = tmp_path / f"{artifact.artifact_id}.json"
        payload = json.loads(artifact_path.read_text(encoding="utf-8"))
        payload_mutator(payload)
        artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ValueError, match=expected_error):
        validate_construction_artifact_replay_params(
            _construction_artifact_replay_request(artifact_id),
            artifact_store=artifact_store,
        )


def test_validate_construction_artifact_replay_params_rejects_infeasible_artifact(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-validation-infeasible-artifact",
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
        }),
        artifact_store=artifact_store,
    )

    with pytest.raises(ValueError, match="construction_artifact_id must reference a feasible construction artifact"):
        validate_construction_artifact_replay_params(
            _construction_artifact_replay_request(artifact.artifact_id),
            artifact_store=artifact_store,
        )


def test_validate_construction_artifact_replay_params_succeeds_for_openable_artifact(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-validation-valid-success",
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
        }),
        artifact_store=artifact_store,
    )
    request = _construction_artifact_replay_request(artifact.artifact_id)

    preview_response = build_construction_artifact_replay_preview(request, artifact_store=artifact_store)
    validation_response = validate_construction_artifact_replay_params(request, artifact_store=artifact_store)

    assert validation_response.model_dump(mode="json") == {
        "construction_artifact_id": artifact.artifact_id,
        "effective_replay_params": preview_response.effective_replay_params.model_dump(mode="json"),
        "preview_handoff": {
            "handoff_kind": "construction_artifact_preview_handoff_v1",
            "construction_artifact_id": artifact.artifact_id,
            "effective_replay_params": preview_response.effective_replay_params.model_dump(mode="json"),
        },
        "open_payload": None,
    }


def test_preflight_construction_artifact_replay_is_lightweight_and_matches_preview_inputs(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-preflight-lightweight",
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
        }),
        artifact_store=artifact_store,
    )
    request = _construction_artifact_replay_request(artifact.artifact_id)

    preflight = preflight_construction_artifact_replay(request, artifact_store=artifact_store)

    assert preflight.artifact.artifact_id == artifact.artifact_id
    assert preflight.baseline_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.6),
        PortfolioWeightInput(symbol="BBB", target_weight=0.4),
    ]
    assert preflight.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.5),
        PortfolioWeightInput(symbol="BBB", target_weight=0.5),
    ]
    assert preflight.effective_replay_params.model_dump(mode="json") == {
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
    mock_service.return_value.get_historical_prices.assert_not_called()
    mock_service.return_value.get_historical_prices_for_symbols.assert_not_called()


def test_preflight_does_not_change_construction_artifact_preview_output(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-preflight-parity",
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
        }),
        artifact_store=artifact_store,
    )
    request = ConstructionArtifactReplayRequest(
        construction_artifact_id=artifact.artifact_id,
        benchmark_symbol="QQQ",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        initial_capital=250000,
        rebalance_frequency="quarterly",
        base_currency="EUR",
        commission_bps=4.5,
        slippage_bps=6.5,
        drift_tolerance_pct=2.0,
        execution_lag_days=3,
        symbol_overrides={"AAA": ["QQQ"]},
    )

    preflight = preflight_construction_artifact_replay(request, artifact_store=artifact_store)
    preview_response = build_construction_artifact_replay_preview(request, artifact_store=artifact_store)

    assert preview_response.construction_artifact_id == preflight.artifact.artifact_id
    assert preview_response.baseline_weights == preflight.baseline_weights
    assert preview_response.candidate_weights == preflight.candidate_weights
    assert preview_response.effective_replay_params == preflight.effective_replay_params


def test_build_construction_artifact_replay_preview_emits_canonical_review_basis_and_methodology_provenance(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-review-basis",
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
        }),
        artifact_store=artifact_store,
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=artifact.artifact_id,
            benchmark_symbol="QQQ",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
            initial_capital=250000,
            rebalance_frequency="quarterly",
            base_currency="EUR",
            commission_bps=4.5,
            slippage_bps=6.5,
            drift_tolerance_pct=2.0,
            execution_lag_days=3,
            symbol_overrides={"AAA": ["QQQ"]},
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.review_basis.model_dump(mode="json") == {
        "basis_version": 1,
        "basis_kind": "persisted_construction_artifact_review",
        "review_scope": "workspace_review_only",
        "canonical_source": "typed_preview_handoff",
        "basis_provenance_label": "artifact_backed_review_basis",
        "portfolio_truth": "imported_portfolio_snapshot",
        "candidate_truth": "hypothetical_construction_artifact",
        "construction_artifact_id": artifact.artifact_id,
        "preview_handoff": {
            "handoff_kind": "construction_artifact_preview_handoff_v1",
            "construction_artifact_id": artifact.artifact_id,
            "effective_replay_params": replay_response.effective_replay_params.model_dump(mode="json"),
        },
        "launch_context": {
            "construction_artifact_id": artifact.artifact_id,
            "ranked_universe_artifact_id": "ranking_artifact_1",
            "ranked_universe_artifact_schema_version": None,
            "ranking_id": "ranked_candidates_v1",
            "ranking_methodology_id": "ranked_candidates_methodology_v1",
            "ranking_as_of_date": "2026-04-23",
            "current_portfolio_artifact_id": "portfolio_snapshot_1",
            "current_portfolio_as_of_timestamp": "2026-04-23T09:30:00",
            "policy_id": "top_n_equal_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
            "top_n": 2,
        },
        "benchmark_symbol": "QQQ",
        "base_currency": "EUR",
        "replay_window": {
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        },
        "baseline_weights": [
            {"symbol": "AAA", "target_weight": 0.6},
            {"symbol": "BBB", "target_weight": 0.4},
        ],
        "candidate_weights": [
            {"symbol": "AAA", "target_weight": 0.5},
            {"symbol": "BBB", "target_weight": 0.5},
        ],
    }
    assert replay_response.replay.methodology_provenance.model_dump(mode="json") == {
        "provenance_version": 1,
        "source": "portfolio_allocation_backtest_engine",
        "methodology_truth": "review_only_replay_methodology",
        "assumptions_truth": "review_only_replay_assumptions",
        "analytics_truth": "hypothetical_replay_analytics_only",
        "review_scope": "workspace_review_context_only",
    }


def test_create_open_and_compare_review_snapshot_artifacts_roundtrip(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    baseline = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    candidate_request = _review_snapshot_request("IUFS")
    candidate_request["proposal_id"] = "proposal-IUFS-v2"
    candidate_request["version_number"] = 2
    candidate = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(candidate_request))

    opened = open_review_snapshot_artifact(
        ReviewSnapshotOpenHandoff(
            artifact_id=baseline.identity.artifact_id,
        )
    )
    family_review = build_review_snapshot_family_review(
        ReviewSnapshotFamilyReviewRequest.model_validate({
            "handoff": {"artifact_id": baseline.identity.artifact_id}
        })
    )
    comparison = compare_review_snapshots(
        ReviewSnapshotComparisonRequest.model_validate({
            "baseline": {"role": "baseline", "artifact_id": baseline.identity.artifact_id, "artifact_kind": "portfolio_review_snapshot", "schema_version": "review_snapshot_artifact_v1", "consumer_kind": "saved_hypothetical_replay_proposal"},
            "candidate": {"role": "candidate", "artifact_id": candidate.identity.artifact_id, "artifact_kind": "portfolio_review_snapshot", "schema_version": "review_snapshot_artifact_v1", "consumer_kind": "saved_hypothetical_replay_proposal"},
        })
    )

    assert opened.artifact.identity.artifact_id == baseline.identity.artifact_id
    assert opened.handoff == baseline.proposal_capture.open_handoff
    assert opened.pm_summary == baseline.pm_summary
    assert opened.replay_payload == baseline.source_payload
    assert baseline.proposal_capture.capture_kind == "workspace_review_saved_proposal"
    assert baseline.proposal_capture.open_handoff.artifact_id == baseline.identity.artifact_id
    assert baseline.proposal_capture.lineage == baseline.lineage
    assert baseline.proposal_capture.proposal.proposal_source == baseline.pm_summary.provenance.proposal_source
    assert baseline.proposal_capture.review_basis.benchmark_separation == "explicit_per_snapshot_benchmark_fields"
    assert family_review.review_kind == "review_snapshot_family_review"
    assert family_review.family_key.proposal_family_id == baseline.lineage.proposal_family_id
    assert family_review.anchor.identity.artifact_id == baseline.identity.artifact_id
    assert [sibling.identity.artifact_id for sibling in family_review.siblings] == [candidate.identity.artifact_id, baseline.identity.artifact_id]
    assert family_review.anchor.comparison_eligibility.reason == "compatible_family_sibling_available"
    assert candidate.identity.artifact_id in family_review.anchor.comparison_eligibility.compatible_sibling_artifact_ids
    assert comparison.provenance == "persisted_review_snapshot_artifacts_only"
    assert comparison.benchmark_separation == "explicit_per_snapshot_benchmark_fields"
    assert comparison.family_key.proposal_family_id == baseline.lineage.proposal_family_id
    assert comparison.baseline_pm_summary.role == "baseline"
    assert comparison.candidate_pm_summary.role == "candidate"
    assert comparison.baseline.source_pair == "AAPL -> IUFS"
    assert comparison.candidate.source_pair == "AAPL -> IUFS"
    assert comparison.analytics_comparison is not None
    assert comparison.analytics_comparison.benchmark_return_diff_pct == 0
    assert comparison.methodology.baseline_methodology.assumptions.execution_lag_days == 1
    assert comparison.assumptions.assumptions_consistent is True


def test_review_snapshot_open_fails_closed_on_malformed_pm_summary_payload(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    artifact = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    artifact_path = tmp_path / f"{artifact.identity.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["pm_summary"]["truth_labels"]["analytics_truth"] = "wrong_truth_label"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(Exception, match="persisted review snapshot artifact failed schema validation"):
        open_review_snapshot_artifact(ReviewSnapshotOpenHandoff(artifact_id=artifact.identity.artifact_id))


def test_review_snapshot_open_fails_closed_on_pm_summary_lineage_contradiction(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    artifact = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    artifact_path = tmp_path / f"{artifact.identity.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["pm_summary"]["provenance"]["lineage"]["proposal_id"] = "proposal-other"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(Exception, match="persisted review snapshot artifact failed schema validation"):
        open_review_snapshot_artifact(ReviewSnapshotOpenHandoff(artifact_id=artifact.identity.artifact_id))


def test_review_snapshot_open_fails_closed_on_proposal_capture_open_handoff_mismatch(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    artifact = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    artifact_path = tmp_path / f"{artifact.identity.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["proposal_capture"]["open_handoff"]["artifact_id"] = "review_snapshot_other"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(Exception, match="persisted review snapshot artifact failed schema validation"):
        open_review_snapshot_artifact(ReviewSnapshotOpenHandoff(artifact_id=artifact.identity.artifact_id))


def test_review_snapshot_open_fails_closed_on_missing_artifact(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    with pytest.raises(Exception, match="missing persisted review snapshot artifact file"):
        open_review_snapshot_artifact(ReviewSnapshotOpenHandoff(artifact_id="review_snapshot_missing0001"))


def test_review_snapshot_compare_rejects_incompatible_pair(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    baseline = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    incompatible_request = _review_snapshot_request("IUFS")
    incompatible_request["proposal_id"] = "proposal-IUFS-v2"
    incompatible_request["version_number"] = 2
    incompatible_request["review_payload"]["replay"]["candidate_result"]["assumptions"]["execution_lag_days"] = 3
    incompatible = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(incompatible_request))

    with pytest.raises(ValueError, match="review snapshot comparison requires matching replay assumptions"):
        compare_review_snapshots(
            ReviewSnapshotComparisonRequest.model_validate({
                "baseline": {"role": "baseline", "artifact_id": baseline.identity.artifact_id, "artifact_kind": "portfolio_review_snapshot", "schema_version": "review_snapshot_artifact_v1", "consumer_kind": "saved_hypothetical_replay_proposal"},
                "candidate": {"role": "candidate", "artifact_id": incompatible.identity.artifact_id, "artifact_kind": "portfolio_review_snapshot", "schema_version": "review_snapshot_artifact_v1", "consumer_kind": "saved_hypothetical_replay_proposal"},
            })
        )


def test_review_snapshot_family_review_discovers_only_same_family_siblings(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    anchor = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    sibling_request = _review_snapshot_request("IUFS")
    sibling_request["proposal_id"] = "proposal-IUFS-v2"
    sibling_request["version_number"] = 2
    sibling = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(sibling_request))
    other_family = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUIT")))

    family_review = build_review_snapshot_family_review(
        ReviewSnapshotFamilyReviewRequest.model_validate({
            "handoff": {"artifact_id": anchor.identity.artifact_id}
        })
    )

    assert family_review.family_key.proposal_family_id == anchor.lineage.proposal_family_id
    assert [row.identity.artifact_id for row in family_review.siblings] == [sibling.identity.artifact_id, anchor.identity.artifact_id]
    assert all(row.lineage.proposal_family_id == anchor.lineage.proposal_family_id for row in family_review.siblings)
    assert other_family.identity.artifact_id not in [row.identity.artifact_id for row in family_review.siblings]


def test_review_snapshot_family_inbox_discovers_latest_anchor_and_compare_readiness(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    baseline = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    baseline_path = tmp_path / f"{baseline.identity.artifact_id}.json"
    older_time = datetime(2026, 4, 15, 0, 5, tzinfo=UTC).timestamp()
    os.utime(baseline_path, (older_time, older_time))

    candidate_request = _review_snapshot_request("IUFS")
    candidate_request["proposal_id"] = "proposal-IUFS-v2"
    candidate_request["version_number"] = 2
    candidate = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(candidate_request))
    candidate_path = tmp_path / f"{candidate.identity.artifact_id}.json"
    newer_time = datetime(2026, 4, 16, 0, 5, tzinfo=UTC).timestamp()
    os.utime(candidate_path, (newer_time, newer_time))

    other_family = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUIT")))
    other_family_path = tmp_path / f"{other_family.identity.artifact_id}.json"
    other_time = datetime(2026, 4, 14, 0, 5, tzinfo=UTC).timestamp()
    os.utime(other_family_path, (other_time, other_time))

    inbox = build_review_snapshot_family_inbox(
        ReviewSnapshotFamilyInboxRequest.model_validate({"workspace_id": "workspace-1"})
    )

    assert inbox.inbox_kind == "review_snapshot_family_inbox"
    assert inbox.workspace_id == "workspace-1"
    assert [row.family_key.proposal_family_id for row in inbox.rows] == [
        candidate.lineage.proposal_family_id,
        other_family.lineage.proposal_family_id,
    ]
    assert inbox.rows[0].latest_identity.artifact_id == candidate.identity.artifact_id
    assert inbox.rows[0].proposal_capture.open_handoff.artifact_id == candidate.identity.artifact_id
    assert inbox.rows[0].pm_summary == candidate.pm_summary
    assert inbox.rows[0].sibling_count == 2
    assert inbox.rows[0].compare_readiness.ready is True
    assert inbox.rows[0].compare_readiness.reason == "compatible_family_pair_available"
    assert inbox.rows[0].compare_readiness.compatible_pair_count == 1
    assert inbox.rows[0].latest_saved_at == "2026-04-16T00:05:00Z"
    assert inbox.rows[0].pm_summary.analytics_summary.candidate_analytics.benchmark_return_pct == candidate.pm_summary.analytics_summary.candidate_analytics.benchmark_return_pct
    assert inbox.rows[1].latest_identity.artifact_id == other_family.identity.artifact_id
    assert inbox.rows[1].compare_readiness.ready is False
    assert inbox.rows[1].compare_readiness.reason == "no_compatible_family_pair"
    assert inbox.rows[1].compare_readiness.compatible_pair_count == 0


def test_review_snapshot_active_thesis_cross_family_queue_returns_metadata_only_and_preserves_pm_summary_fields(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    active_thesis_request = _review_snapshot_request("IUFS")
    active_thesis_request["proposal_id"] = "proposal-thesis"
    active_thesis_request["proposal_family_id"] = "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z"
    active_thesis_request["version_number"] = 4
    active_thesis = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(active_thesis_request))
    active_path = tmp_path / f"{active_thesis.identity.artifact_id}.json"
    active_time = datetime(2026, 4, 10, 0, 5, tzinfo=UTC).timestamp()
    os.utime(active_path, (active_time, active_time))

    first_family_request = _review_snapshot_request("IUIT")
    first_family_request["proposal_id"] = "proposal-iuit"
    first_family_request["proposal_family_id"] = "etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z"
    first_family = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(first_family_request))
    first_family_path = tmp_path / f"{first_family.identity.artifact_id}.json"
    first_time = datetime(2026, 4, 15, 0, 5, tzinfo=UTC).timestamp()
    os.utime(first_family_path, (first_time, first_time))

    second_family_request = _review_snapshot_request("IVV")
    second_family_request["proposal_id"] = "proposal-ivv"
    second_family_request["proposal_family_id"] = "etf_replacement_intent:AAPL:IVV:2026-04-14T00:05:00Z"
    second_family = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(second_family_request))
    second_family_path = tmp_path / f"{second_family.identity.artifact_id}.json"
    second_time = datetime(2026, 4, 14, 0, 5, tzinfo=UTC).timestamp()
    os.utime(second_family_path, (second_time, second_time))

    queue = build_review_snapshot_active_thesis_cross_family_queue(
        ReviewSnapshotActiveThesisCrossFamilyQueueRequest.model_validate({
            "source_proposal_id": active_thesis.lineage.proposal_id,
            "handoff": active_thesis.proposal_capture.open_handoff.model_dump(mode="json"),
        })
    )

    assert queue.queue_kind == "review_snapshot_active_thesis_cross_family_queue"
    assert queue.provenance == "persisted_review_snapshot_artifacts_and_active_thesis_reference_only"
    assert queue.queue_ordering == "latest_saved_at_desc_then_artifact_id_desc"
    assert queue.active_thesis.source_proposal_id == active_thesis.lineage.proposal_id
    assert [row.family_key.proposal_family_id for row in queue.rows] == [
        first_family.lineage.proposal_family_id,
        second_family.lineage.proposal_family_id,
    ]
    assert queue.rows[0].latest_identity.artifact_id == first_family.identity.artifact_id
    assert queue.rows[0].proposal_source == first_family.pm_summary.provenance.proposal_source
    assert queue.rows[0].truth_labels == first_family.pm_summary.truth_labels
    assert queue.rows[0].trust_visibility.investor_economics_status == first_family.pm_summary.investor_economics_status
    assert queue.rows[0].trust_visibility.benchmark_separation == "explicit_per_snapshot_benchmark_fields"
    assert queue.rows[0].pm_summary_fields.review_basis == first_family.pm_summary.review_basis
    assert queue.rows[0].pm_summary_fields.methodology == first_family.pm_summary.methodology
    assert queue.rows[0].pm_summary_fields.assumptions == first_family.pm_summary.assumptions
    assert queue.rows[0].pm_summary_fields.analytics_summary.candidate_analytics.benchmark_symbol == first_family.pm_summary.analytics_summary.candidate_analytics.benchmark_symbol
    assert queue.rows[0].pm_summary_fields.analytics_summary.candidate_analytics.benchmark_return_pct == first_family.pm_summary.analytics_summary.candidate_analytics.benchmark_return_pct
    assert queue.rows[0].pm_summary_fields.analytics_summary.candidate_analytics.methodology == first_family.pm_summary.analytics_summary.candidate_analytics.methodology
    assert queue.rows[0].pm_summary_fields.analytics_summary.candidate_analytics.assumptions == first_family.pm_summary.analytics_summary.candidate_analytics.assumptions
    assert queue.rows[0].pm_summary_fields.diagnostics_summary == first_family.pm_summary.diagnostics_summary
    assert queue.rows[0].family_separation.active_thesis_proposal_family_id == active_thesis.lineage.proposal_family_id
    assert queue.rows[0].family_separation.queue_proposal_family_id == first_family.lineage.proposal_family_id
    assert queue.rows[0].latest_saved_at == "2026-04-15T00:05:00Z"


def test_review_snapshot_active_thesis_cross_family_queue_uses_persisted_artifacts_only_not_loose_state(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    active_thesis_request = _review_snapshot_request("IUFS")
    active_thesis_request["proposal_id"] = "proposal-thesis"
    active_thesis_request["proposal_family_id"] = "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z"
    active_thesis = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(active_thesis_request))

    candidate_request = _review_snapshot_request("IUIT")
    candidate_request["proposal_id"] = "proposal-iuit"
    candidate_request["proposal_family_id"] = "etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z"
    candidate = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(candidate_request))
    candidate.pm_summary.methodology.methodology = "Loose in-memory methodology"
    candidate.pm_summary.analytics_summary.candidate_analytics.methodology = "Loose in-memory methodology"

    queue = build_review_snapshot_active_thesis_cross_family_queue(
        ReviewSnapshotActiveThesisCrossFamilyQueueRequest.model_validate({
            "source_proposal_id": active_thesis.lineage.proposal_id,
            "handoff": active_thesis.proposal_capture.open_handoff.model_dump(mode="json"),
        })
    )

    assert queue.rows[0].pm_summary_fields.methodology.methodology == "Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions."
    assert queue.rows[0].pm_summary_fields.analytics_summary.candidate_analytics.methodology == "Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions."


def test_review_snapshot_family_inbox_fails_closed_on_ambiguous_latest_selection(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    first = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    second_request = _review_snapshot_request("IUFS")
    second_request["proposal_id"] = "proposal-IUFS-shadow"
    second = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(second_request))
    first_path = tmp_path / f"{first.identity.artifact_id}.json"
    second_path = tmp_path / f"{second.identity.artifact_id}.json"
    shared_time = datetime(2026, 4, 16, 0, 5, tzinfo=UTC).timestamp()
    os.utime(first_path, (shared_time, shared_time))
    os.utime(second_path, (shared_time, shared_time))

    with pytest.raises(ValueError, match="review snapshot family inbox latest selection is ambiguous"):
        build_review_snapshot_family_inbox(
            ReviewSnapshotFamilyInboxRequest.model_validate({"workspace_id": "workspace-1"})
        )


def test_review_snapshot_active_thesis_cross_family_queue_fails_closed_on_same_family_candidate(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    active_thesis_request = _review_snapshot_request("IUFS")
    active_thesis_request["proposal_id"] = "proposal-thesis"
    active_thesis_request["proposal_family_id"] = "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z"
    active_thesis = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(active_thesis_request))
    same_family_request = _review_snapshot_request("IUIT")
    same_family_request["proposal_id"] = "proposal-same-family"
    same_family_request["proposal_family_id"] = active_thesis.lineage.proposal_family_id
    same_family = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(same_family_request))
    same_family_path = tmp_path / f"{same_family.identity.artifact_id}.json"
    payload = json.loads(same_family_path.read_text(encoding="utf-8"))
    payload["lineage"]["proposal_family_id"] = "etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z"
    same_family_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(Exception, match="persisted review snapshot artifact failed schema validation"):
        build_review_snapshot_active_thesis_cross_family_queue(
            ReviewSnapshotActiveThesisCrossFamilyQueueRequest.model_validate({
                "source_proposal_id": active_thesis.lineage.proposal_id,
                "handoff": active_thesis.proposal_capture.open_handoff.model_dump(mode="json"),
            })
        )


def test_review_snapshot_active_thesis_cross_family_queue_fails_closed_on_source_proposal_mismatch(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    active_thesis_request = _review_snapshot_request("IUFS")
    active_thesis_request["proposal_id"] = "proposal-thesis"
    active_thesis_request["proposal_family_id"] = "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z"
    active_thesis = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(active_thesis_request))

    with pytest.raises(ValueError, match="review snapshot active thesis cross-family queue source_proposal_id does not match persisted artifact lineage"):
        build_review_snapshot_active_thesis_cross_family_queue(
            ReviewSnapshotActiveThesisCrossFamilyQueueRequest.model_validate({
                "source_proposal_id": "proposal-other",
                "handoff": active_thesis.proposal_capture.open_handoff.model_dump(mode="json"),
            })
        )


def test_review_snapshot_active_thesis_cross_family_queue_fails_closed_on_ambiguous_latest_ordering(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    active_thesis_request = _review_snapshot_request("IUFS")
    active_thesis_request["proposal_id"] = "proposal-thesis"
    active_thesis_request["proposal_family_id"] = "etf_replacement_intent:AAPL:THESIS:2026-04-10T00:05:00Z"
    active_thesis = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(active_thesis_request))

    first_request = _review_snapshot_request("IUIT")
    first_request["proposal_id"] = "proposal-iuit-a"
    first_request["proposal_family_id"] = "etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z"
    first = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(first_request))
    second_request = _review_snapshot_request("IUIT")
    second_request["proposal_id"] = "proposal-iuit-b"
    second_request["proposal_family_id"] = "etf_replacement_intent:AAPL:IUIT:2026-04-15T00:05:00Z"
    second = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(second_request))
    first_path = tmp_path / f"{first.identity.artifact_id}.json"
    second_path = tmp_path / f"{second.identity.artifact_id}.json"
    shared_time = datetime(2026, 4, 16, 0, 5, tzinfo=UTC).timestamp()
    os.utime(first_path, (shared_time, shared_time))
    os.utime(second_path, (shared_time, shared_time))

    with pytest.raises(ValueError, match="review snapshot family inbox latest selection is ambiguous"):
        build_review_snapshot_active_thesis_cross_family_queue(
            ReviewSnapshotActiveThesisCrossFamilyQueueRequest.model_validate({
                "source_proposal_id": active_thesis.lineage.proposal_id,
                "handoff": active_thesis.proposal_capture.open_handoff.model_dump(mode="json"),
            })
        )


def test_review_snapshot_family_inbox_fails_closed_on_cross_family_contamination(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    anchor = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    cross_family = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUIT")))
    cross_family_path = tmp_path / f"{cross_family.identity.artifact_id}.json"
    payload = json.loads(cross_family_path.read_text(encoding="utf-8"))
    payload["lineage"]["proposal_family_id"] = anchor.lineage.proposal_family_id
    cross_family_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(Exception, match="persisted review snapshot artifact failed schema validation"):
        build_review_snapshot_family_inbox(
            ReviewSnapshotFamilyInboxRequest.model_validate({"workspace_id": "workspace-1"})
        )


def test_review_snapshot_compare_rejects_proposal_family_mismatch(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    baseline = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    candidate = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUIT")))

    with pytest.raises(ValueError, match="review snapshot comparison requires matching proposal_family_id"):
        compare_review_snapshots(
            ReviewSnapshotComparisonRequest.model_validate({
                "baseline": {"role": "baseline", "artifact_id": baseline.identity.artifact_id, "artifact_kind": "portfolio_review_snapshot", "schema_version": "review_snapshot_artifact_v1", "consumer_kind": "saved_hypothetical_replay_proposal"},
                "candidate": {"role": "candidate", "artifact_id": candidate.identity.artifact_id, "artifact_kind": "portfolio_review_snapshot", "schema_version": "review_snapshot_artifact_v1", "consumer_kind": "saved_hypothetical_replay_proposal"},
            })
        )


@pytest.mark.parametrize(
    ("field", "value", "expected_error"),
    [
        ("workspace_id", None, "Input should be a valid string"),
        ("workspace_id", "", "review snapshot family key workspace_id is required"),
        ("source_draft_id", None, "Input should be a valid string"),
        ("source_draft_id", "", "review snapshot family key source_draft_id is required"),
        ("source_base_node_id", None, "Input should be a valid string"),
        ("source_base_node_id", "", "review snapshot family key source_base_node_id is required"),
        ("proposal_family_id", None, "Input should be a valid string"),
        ("proposal_family_id", "", "review snapshot family key proposal_family_id is required"),
        ("source_kind", None, "Input should be 'hypothetical_replacement_replay'"),
        ("source_kind", "", "Input should be 'hypothetical_replacement_replay'"),
        ("source_kind", "persisted_optimizer_handoff", "Input should be 'hypothetical_replacement_replay'"),
    ],
)
def test_review_snapshot_family_key_schema_fails_closed_for_missing_and_invalid_fields(field: str, value: object, expected_error: str) -> None:
    payload: dict[str, object] = {
        "workspace_id": "workspace-1",
        "source_draft_id": "draft-1",
        "source_base_node_id": "node-1",
        "proposal_family_id": "etf_replacement_intent:AAPL:IUFS:2026-04-15T00:05:00Z",
        "source_kind": "hypothetical_replacement_replay",
    }
    payload[field] = value

    with pytest.raises(ValidationError, match=expected_error):
        ReviewSnapshotFamilyKey.model_validate(payload)


def test_review_snapshot_family_key_extraction_fails_closed_when_artifact_lineage_fields_are_missing(tmp_path, mocker) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    artifact = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    invalid_artifact = artifact.model_copy(
        update={
            "lineage": artifact.lineage.model_copy(update={"proposal_family_id": ""}),
        }
    )

    with pytest.raises(ValueError, match="review snapshot artifact lineage family_key is invalid: review snapshot family key proposal_family_id is required"):
        _review_snapshot_family_key_from_artifact(invalid_artifact)

@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
        (lambda payload: payload["review_basis"].__setitem__("benchmark_symbol", "QQQ"), "persisted review snapshot artifact failed schema validation"),
        (lambda payload: payload["review_basis"].__setitem__("start_date", "2024-02-01"), "persisted review snapshot artifact failed schema validation"),
        (lambda payload: payload["review_basis"].__setitem__("derivation_basis", "wrong_basis"), "persisted review snapshot artifact failed schema validation"),
        (lambda payload: payload["compact_summary"].__setitem__("replay_type", "overlay_aware"), "persisted review snapshot artifact failed schema validation"),
    ],
)
def test_review_snapshot_compare_fails_closed_on_incompatible_persisted_pair_dimensions(tmp_path, mocker, mutator, expected_error) -> None:
    mocker.patch(
        "app.services.review_snapshot_artifact_service.get_settings",
        return_value=SimpleNamespace(review_snapshot_artifact_dir=str(tmp_path)),
    )

    baseline = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUFS")))
    candidate = create_review_snapshot_artifact(ReviewSnapshotCreateRequest.model_validate(_review_snapshot_request("IUIT")))
    artifact_path = tmp_path / f"{candidate.identity.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    mutator(payload)
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(Exception, match=expected_error):
        compare_review_snapshots(
            ReviewSnapshotComparisonRequest.model_validate({
                "baseline": {"role": "baseline", "artifact_id": baseline.identity.artifact_id, "artifact_kind": "portfolio_review_snapshot", "schema_version": "review_snapshot_artifact_v1", "consumer_kind": "saved_hypothetical_replay_proposal"},
                "candidate": {"role": "candidate", "artifact_id": candidate.identity.artifact_id, "artifact_kind": "portfolio_review_snapshot", "schema_version": "review_snapshot_artifact_v1", "consumer_kind": "saved_hypothetical_replay_proposal"},
            })
        )


def test_construction_artifact_replay_response_rejects_review_basis_identity_mismatch() -> None:
    with pytest.raises(ValidationError, match="review_basis.construction_artifact_id must match construction_artifact_id"):
        ConstructionArtifactReplayResponse.model_validate({
            "construction_artifact_id": "artifact-123",
            "review_basis": {
                "basis_version": 1,
                "basis_kind": "persisted_construction_artifact_review",
                "review_scope": "workspace_review_only",
                "canonical_source": "typed_preview_handoff",
                "basis_provenance_label": "artifact_backed_review_basis",
                "portfolio_truth": "imported_portfolio_snapshot",
                "candidate_truth": "hypothetical_construction_artifact",
                "construction_artifact_id": "artifact-other",
                "preview_handoff": {
                    "handoff_kind": "construction_artifact_preview_handoff_v1",
                    "construction_artifact_id": "artifact-other",
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
                "launch_context": {
                    "construction_artifact_id": "artifact-other",
                    "ranked_universe_artifact_id": "ranking-1",
                    "ranked_universe_artifact_schema_version": None,
                    "ranking_id": "ranking-id-1",
                    "ranking_methodology_id": "ranking-method-1",
                    "ranking_as_of_date": None,
                    "current_portfolio_artifact_id": "portfolio-1",
                    "current_portfolio_as_of_timestamp": None,
                    "policy_id": "policy-1",
                    "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
                    "top_n": 2,
                },
                "benchmark_symbol": "SPY",
                "base_currency": "USD",
                "replay_window": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
                "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
                "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
            },
            "replay_provenance": {
                "source": "construction_artifact_reference",
                "construction_artifact_id": "artifact-123",
                "policy_id": "policy-1",
                "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
                "ranked_universe_artifact_id": "ranking-1",
                "ranked_universe_artifact_schema_version": None,
                "ranking_id": "ranking-id-1",
                "ranking_methodology_id": "ranking-method-1",
                "ranking_as_of_date": None,
                "current_portfolio_artifact_id": "portfolio-1",
                "current_portfolio_as_of_timestamp": None,
                "top_n": 2,
                "hard_constraints": {
                    "full_investment": True,
                    "long_only": True,
                    "eligible_ranked_universe_only": True,
                    "max_position_weight": 0.6,
                    "min_position_weight": None,
                    "max_turnover_weight": None,
                    "max_trade_intent_count": None,
                },
                "baseline_input_source": "normalized_inputs.current_portfolio_weights",
                "candidate_input_source": "final_target_weights",
                "selection_rule_trace": {
                    "rule_ids": ["eligible_only"],
                    "steps": [{
                        "rule_id": "eligible_only",
                        "rule_order": 1,
                        "input_candidate_symbols": ["AAA"],
                        "output_candidate_symbols": ["AAA"],
                    }],
                },
                "turnover_diagnostics_status": "unavailable_legacy_artifact",
                "turnover_diagnostics_v1": None,
                "weighting_trace_status": "unavailable_legacy_artifact",
                "weighting_trace_v1": None,
            },
            "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
            "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
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
            "replay": PortfolioAllocationBacktestResponse.model_validate({
                "methodology": "m",
                "investor_economics_status": {"status": "available", "reason": None},
                "candidate_result": {
                    "portfolio_name": "Candidate",
                    "benchmark_symbol": "SPY",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "observation_count": 2,
                    "rebalance_frequency": "monthly",
                    "commission_bps": 0.0,
                    "slippage_bps": 0.0,
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
                    "starting_weights": [],
                    "ending_weights": [],
                    "metrics": {},
                    "equity_curve": [],
                    "rebalance_events": [],
                    "trades": [],
                },
            }).model_dump(mode="json"),
        })


def test_construction_artifact_replay_response_rejects_launch_context_lineage_mismatch() -> None:
    payload = {
        "construction_artifact_id": "artifact-123",
        "review_basis": {
            "basis_version": 1,
            "basis_kind": "persisted_construction_artifact_review",
            "review_scope": "workspace_review_only",
            "canonical_source": "typed_preview_handoff",
            "basis_provenance_label": "artifact_backed_review_basis",
            "portfolio_truth": "imported_portfolio_snapshot",
            "candidate_truth": "hypothetical_construction_artifact",
            "construction_artifact_id": "artifact-123",
            "preview_handoff": {
                "handoff_kind": "construction_artifact_preview_handoff_v1",
                "construction_artifact_id": "artifact-123",
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
            "launch_context": {
                "construction_artifact_id": "artifact-123",
                "ranked_universe_artifact_id": "ranking-1",
                "ranked_universe_artifact_schema_version": None,
                "ranking_id": "ranking-id-1",
                "ranking_methodology_id": "ranking-method-1",
                "ranking_as_of_date": "2026-04-23",
                "current_portfolio_artifact_id": "portfolio-1",
                "current_portfolio_as_of_timestamp": "2026-04-23T09:30:00",
                "policy_id": "policy-1",
                "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
                "top_n": 3,
            },
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "replay_window": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
            "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
            "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
        },
        "replay_provenance": {
            "source": "construction_artifact_reference",
            "construction_artifact_id": "artifact-123",
            "policy_id": "policy-1",
            "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
            "ranked_universe_artifact_id": "ranking-1",
            "ranked_universe_artifact_schema_version": None,
            "ranking_id": "ranking-id-1",
            "ranking_methodology_id": "ranking-method-1",
            "ranking_as_of_date": "2026-04-23",
            "current_portfolio_artifact_id": "portfolio-1",
            "current_portfolio_as_of_timestamp": "2026-04-23T09:30:00",
            "top_n": 2,
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
                "min_position_weight": None,
                "max_turnover_weight": None,
                "max_trade_intent_count": None,
            },
            "baseline_input_source": "normalized_inputs.current_portfolio_weights",
            "candidate_input_source": "final_target_weights",
            "selection_rule_trace": {
                "rule_ids": ["eligible_only"],
                "steps": [{
                    "rule_id": "eligible_only",
                    "rule_order": 1,
                    "input_candidate_symbols": ["AAA"],
                    "output_candidate_symbols": ["AAA"],
                }],
            },
            "turnover_diagnostics_status": "unavailable_legacy_artifact",
            "turnover_diagnostics_v1": None,
            "weighting_trace_status": "unavailable_legacy_artifact",
            "weighting_trace_v1": None,
        },
        "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
        "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
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
        "replay": PortfolioAllocationBacktestResponse.model_validate({
            "methodology": "m",
            "investor_economics_status": {"status": "available", "reason": None},
            "candidate_result": {
                "portfolio_name": "Candidate",
                "benchmark_symbol": "SPY",
                "start_date": "2024-01-01",
                "end_date": "2024-12-31",
                "observation_count": 2,
                "rebalance_frequency": "monthly",
                "commission_bps": 0.0,
                "slippage_bps": 0.0,
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
                "starting_weights": [],
                "ending_weights": [],
                "metrics": {},
                "equity_curve": [],
                "rebalance_events": [],
                "trades": [],
            },
        }).model_dump(mode="json"),
    }

    with pytest.raises(ValidationError, match="review_basis.launch_context must match replay_provenance launch lineage"):
        ConstructionArtifactReplayResponse.model_validate(payload)


def test_optimizer_handoff_replay_response_rejects_review_basis_identity_mismatch() -> None:
    with pytest.raises(ValidationError, match="review_basis.handoff_reference.handoff_id must match handoff_id"):
        OptimizerHandoffReplayResponse.model_validate({
            "handoff_id": "handoff-123",
            "artifact_id": "artifact-123",
            "source_portfolio_snapshot_id": "portfolio-123",
            "review_basis": {
                "basis_version": 1,
                "basis_kind": "persisted_optimizer_handoff_review",
                "review_scope": "workspace_review_only",
                "canonical_source": "persisted_handoff_reference",
                "basis_provenance_label": "artifact_backed_review_basis",
                "portfolio_truth": "imported_portfolio_snapshot",
                "candidate_truth": "hypothetical_optimizer_handoff",
                "handoff_reference": {
                    "reference_kind": "optimizer_handoff_reference_v1",
                    "handoff_id": "handoff-other",
                    "artifact_id": "artifact-123",
                    "manifest_path": "/tmp/manifest.json",
                    "artifact_path": "/tmp/artifact.json",
                },
                "benchmark_symbol": "SPY",
                "base_currency": "USD",
                "replay_window": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
                "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
                "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
            },
            "replay_provenance": {
                "source": "optimizer_handoff_reference",
                "benchmark_id": "benchmark-1",
                "benchmark_version": "2024-04-15",
                "benchmark_symbol": "SPY",
                "return_basis_attestation": {
                    "benchmark_symbol": "SPY",
                    "as_of_date": "2024-12-31",
                    "history_start_date": "2024-01-01",
                    "history_end_date": "2024-12-31",
                    "factor_proxy_symbols": ["QQQ"],
                    "benchmark_return_basis_contract": "unverified_adjusted_proxy",
                    "factor_return_basis_contract": "unverified_adjusted_proxy",
                    "section_trust": {
                        "benchmark_relative_path": "degraded_unverified_return_basis",
                        "factor_model_path": "degraded_unverified_return_basis",
                        "risk_contribution_path": "degraded_unverified_return_basis",
                    },
                    "evidence": {
                        "benchmark_history": {
                            "verification_status": "unverified",
                            "economic_basis": "adjusted_close_proxy",
                            "construction_method": "vendor_adjusted_close",
                            "disqualifiers": [],
                            "fallbacks_used": [],
                            "source_price_field": "adj_close",
                        },
                        "factor_history": {
                            "verification_status": "unverified",
                            "economic_basis": "adjusted_close_proxy",
                            "construction_method": "vendor_adjusted_close",
                            "disqualifiers": [],
                            "fallbacks_used": [],
                            "source_price_field": "adj_close",
                        },
                    },
                },
                "replay_output_policy": {
                    "source": "persisted_return_basis_attestation",
                    "section_trust": {
                        "benchmark_relative_path": "degraded_unverified_return_basis",
                        "factor_model_path": "degraded_unverified_return_basis",
                        "risk_contribution_path": "degraded_unverified_return_basis",
                    },
                    "eligible_families": [],
                    "withheld_families": ["benchmark_relative_volatility_outputs"],
                },
                "artifact_state": "complete",
                "optimizer_status": "feasible",
                "constraint_set_fingerprint": "constraint-fingerprint-1",
            },
            "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
            "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
            "replay": PortfolioAllocationBacktestResponse.model_validate({
                "methodology": "m",
                "investor_economics_status": {"status": "available", "reason": None},
                "candidate_result": {
                    "portfolio_name": "Candidate",
                    "benchmark_symbol": "SPY",
                    "start_date": "2024-01-01",
                    "end_date": "2024-12-31",
                    "observation_count": 2,
                    "rebalance_frequency": "monthly",
                    "commission_bps": 0.0,
                    "slippage_bps": 0.0,
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
                    "starting_weights": [],
                    "ending_weights": [],
                    "metrics": {},
                    "equity_curve": [],
                    "rebalance_events": [],
                    "trades": [],
                },
            }).model_dump(mode="json"),
        })


def test_construction_artifact_workspace_review_basis_requires_canonical_identity_field() -> None:
    with pytest.raises(ValidationError, match="construction_artifact_id"):
        ConstructionArtifactWorkspaceReviewBasis.model_validate({
            "basis_version": 1,
            "basis_kind": "persisted_construction_artifact_review",
            "review_scope": "workspace_review_only",
            "canonical_source": "typed_preview_handoff",
            "basis_provenance_label": "artifact_backed_review_basis",
            "portfolio_truth": "imported_portfolio_snapshot",
            "candidate_truth": "hypothetical_construction_artifact",
            "preview_handoff": {
                "handoff_kind": "construction_artifact_preview_handoff_v1",
                "construction_artifact_id": "artifact-123",
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
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "replay_window": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
            "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
            "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
        })


def test_construction_artifact_workspace_review_basis_rejects_unsupported_basis_version() -> None:
    with pytest.raises(ValidationError, match="basis_version"):
        ConstructionArtifactWorkspaceReviewBasis.model_validate({
            "basis_version": 2,
            "basis_kind": "persisted_construction_artifact_review",
            "review_scope": "workspace_review_only",
            "canonical_source": "typed_preview_handoff",
            "basis_provenance_label": "artifact_backed_review_basis",
            "portfolio_truth": "imported_portfolio_snapshot",
            "candidate_truth": "hypothetical_construction_artifact",
            "construction_artifact_id": "artifact-123",
            "preview_handoff": {
                "handoff_kind": "construction_artifact_preview_handoff_v1",
                "construction_artifact_id": "artifact-123",
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
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "replay_window": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
            "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
            "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
        })


def test_optimizer_handoff_workspace_review_basis_rejects_malformed_handoff_reference() -> None:
    with pytest.raises(ValidationError):
        OptimizerHandoffWorkspaceReviewBasis.model_validate({
            "basis_version": 1,
            "basis_kind": "persisted_optimizer_handoff_review",
            "review_scope": "workspace_review_only",
            "canonical_source": "persisted_handoff_reference",
            "basis_provenance_label": "artifact_backed_review_basis",
            "portfolio_truth": "imported_portfolio_snapshot",
            "candidate_truth": "hypothetical_optimizer_handoff",
            "handoff_reference": {
                "reference_kind": "optimizer_handoff_reference_v1",
                "handoff_id": "handoff-123",
                "artifact_id": "artifact-123",
                "manifest_path": "/tmp/manifest.json",
            },
            "benchmark_symbol": "SPY",
            "base_currency": "USD",
            "replay_window": {"start_date": "2024-01-01", "end_date": "2024-12-31"},
            "baseline_weights": [{"symbol": "AAA", "target_weight": 0.6}],
            "candidate_weights": [{"symbol": "BBB", "target_weight": 0.4}],
        })


def test_build_construction_artifact_replay_preview_uses_persisted_inverse_rank_weights(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 100.2, 100.8, 101.4, 101.9),
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
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-inverse-rank-1",
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
        }),
        artifact_store=artifact_store,
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=artifact.artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.replay_provenance.policy_id == "top_n_inverse_rank_weight_v1"
    assert replay_response.replay_provenance.hard_constraints.model_dump(mode="json") == {
        "full_investment": True,
        "long_only": True,
        "eligible_ranked_universe_only": True,
        "max_position_weight": 0.55,
        "min_position_weight": None,
        "max_turnover_weight": None,
        "max_trade_intent_count": None,
        "max_sector_weight": None,
    }
    assert replay_response.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.54545455),
        PortfolioWeightInput(symbol="BBB", target_weight=0.27272727),
        PortfolioWeightInput(symbol="CCC", target_weight=0.18181818),
    ]


def test_build_construction_artifact_replay_preview_remains_compatible_with_turnover_capped_artifact(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
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
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-turnover-cap-1",
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
                "max_turnover_weight": 0.6,
            },
        }),
        artifact_store=artifact_store,
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=artifact.artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert artifact.weighting_trace_v1 is not None
    assert artifact.turnover_diagnostics_v1 is not None
    assert replay_response.construction_artifact_id == artifact.artifact_id
    assert replay_response.replay_provenance.model_dump() == {
        "source": "construction_artifact_reference",
        "construction_artifact_id": artifact.artifact_id,
        "policy_id": "top_n_equal_weight_v1",
        "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
        "ranked_universe_artifact_id": "ranking_artifact_1",
        "ranked_universe_artifact_schema_version": None,
        "ranking_id": "ranked_candidates_v1",
        "ranking_methodology_id": "ranked_candidates_methodology_v1",
        "ranking_as_of_date": "2026-04-23",
        "current_portfolio_artifact_id": "portfolio_snapshot_1",
        "current_portfolio_as_of_timestamp": "2026-04-23T09:30:00",
        "top_n": 2,
        "hard_constraints": artifact.hard_constraints.model_dump(mode="json"),
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
        "turnover_diagnostics_v1": artifact.turnover_diagnostics_v1.model_dump(mode="json"),
        "weighting_trace_status": "available",
        "weighting_trace_v1": artifact.weighting_trace_v1.model_dump(mode="json"),
    }
    assert replay_response.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.5),
        PortfolioWeightInput(symbol="BBB", target_weight=0.5),
    ]


def test_build_construction_artifact_replay_preview_uses_persisted_artifact_weights_after_catalog_changes(
    tmp_path,
    mocker,
    monkeypatch,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 100.2, 100.8, 101.4, 101.9),
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
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-persisted-weights-only",
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
        }),
        artifact_store=artifact_store,
    )
    original_definition = construction_policy_catalog.get_construction_policy_definition("top_n_inverse_rank_weight_v1")
    assert original_definition is not None
    monkeypatch.setitem(
        construction_policy_catalog._POLICY_BY_ID,
        "top_n_inverse_rank_weight_v1",
        replace(
            original_definition,
            raw_weight_numerator_builder=lambda selected_count: [Fraction(1, 1)] * selected_count,
            max_position_failure_reason="mutated catalog should not affect replay",
            cutoff_exclusion_reason="mutated catalog should not affect replay",
        ),
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=artifact.artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.replay_provenance.policy_id == "top_n_inverse_rank_weight_v1"
    assert replay_response.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.54545455),
        PortfolioWeightInput(symbol="BBB", target_weight=0.27272727),
        PortfolioWeightInput(symbol="CCC", target_weight=0.18181818),
    ]


def test_build_construction_artifact_replay_preview_echoes_persisted_min_position_weight_unchanged(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-min-position-weight",
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
        }),
        artifact_store=artifact_store,
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=artifact.artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.replay_provenance.hard_constraints.model_dump(mode="json") == {
        "full_investment": True,
        "long_only": True,
        "eligible_ranked_universe_only": True,
        "max_position_weight": 0.6,
        "min_position_weight": 0.5,
        "max_turnover_weight": None,
        "max_trade_intent_count": None,
        "max_sector_weight": None,
    }


def test_build_construction_artifact_replay_preview_supports_linear_rank_policy_from_persisted_artifact(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 100.2, 100.8, 101.4, 101.9),
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
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-linear-rank-1",
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
        }),
        artifact_store=artifact_store,
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=artifact.artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.replay_provenance.policy_id == "top_n_linear_rank_weight_v1"
    assert replay_response.replay_provenance.policy_definition_id == "construction_policy_definition_top_n_linear_rank_weight_v1"
    assert replay_response.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.5),
        PortfolioWeightInput(symbol="BBB", target_weight=0.33333333),
        PortfolioWeightInput(symbol="CCC", target_weight=0.16666667),
    ]


def test_build_construction_artifact_replay_preview_requires_normalized_current_portfolio_weights(
    tmp_path,
) -> None:
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-missing-baseline",
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
        }),
        artifact_store=artifact_store,
    )

    with pytest.raises(
        ValueError,
        match="construction artifact replay requires normalized_inputs.current_portfolio_weights for the baseline replay path",
    ):
        build_construction_artifact_replay_preview(
            ConstructionArtifactReplayRequest(
                construction_artifact_id=artifact.artifact_id,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                initial_capital=100000,
                execution_lag_days=1,
            ),
            artifact_store=artifact_store,
        )


@pytest.mark.parametrize(
    "trace_mutator",
    [
        lambda payload: payload.pop("selection_rule_trace"),
        lambda payload: payload.update({"selection_rule_trace": None}),
        lambda payload: payload.update({"selection_rule_trace": {}}),
    ],
    ids=["missing", "null", "empty_object"],
)
def test_construction_artifact_replay_provenance_requires_explicit_selection_trace(trace_mutator) -> None:
    payload = {
        "construction_artifact_id": "construction_artifact_1234567890abcdef",
        "policy_id": "top_n_equal_weight_v1",
        "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
        "hard_constraints": {
            "full_investment": True,
            "long_only": True,
            "eligible_ranked_universe_only": True,
            "max_position_weight": 0.6,
            "min_position_weight": None,
            "max_turnover_weight": None,
            "max_trade_intent_count": None,
        },
        "selection_rule_trace": {"rule_ids": [], "steps": []},
    }
    trace_mutator(payload)

    with pytest.raises(ValidationError):
        ConstructionArtifactReplayProvenance.model_validate(payload)


@pytest.mark.parametrize(
    "turnover_mutator",
    [
        lambda payload: payload.pop("turnover_diagnostics_status"),
        lambda payload: payload.pop("turnover_diagnostics_v1"),
        lambda payload: payload["turnover_diagnostics_v1"].__setitem__("diagnostics_version", "construction_turnover_diagnostics_v0"),
    ],
    ids=["missing_status", "missing_body", "unsupported_version"],
)
def test_construction_artifact_replay_provenance_fails_closed_for_invalid_turnover_diagnostics(turnover_mutator) -> None:
    payload = {
        "construction_artifact_id": "construction_artifact_1234567890abcdef",
        "policy_id": "top_n_equal_weight_v1",
        "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
        "hard_constraints": {
            "full_investment": True,
            "long_only": True,
            "eligible_ranked_universe_only": True,
            "max_position_weight": 0.6,
            "min_position_weight": None,
            "max_turnover_weight": None,
            "max_trade_intent_count": None,
        },
        "selection_rule_trace": {"rule_ids": [], "steps": []},
        "turnover_diagnostics_status": "available",
        "turnover_diagnostics_v1": {
            "diagnostics_version": "construction_turnover_diagnostics_v1",
            "source": "persisted_construction_artifact",
            "diagnostic_truth": "artifact_backed_hypothetical_construction_diagnostics_only",
            "turnover_basis_method_version": "half_l1_weight_delta_union_v1",
            "reported_value_status": "computed",
            "reported_turnover_weight": 0.6,
            "inclusion_flags": {
                "uses_current_and_target_weight_union": True,
                "includes_initiations": True,
                "includes_exits": True,
                "includes_zero_delta_positions_in_trade_intent_context": True,
                "excludes_zero_delta_positions_from_reported_turnover_sum": True,
            },
            "trade_intent_context": {"source_field": "trade_intents", "intent_count": 2},
            "feasibility_context": {
                "artifact_status": "feasible",
                "failure_reasons_field": "failure_reasons",
                "turnover_failure_reason_present": False,
            },
            "constraint_context": {
                "constraint_id": "max_turnover_weight",
                "requested": True,
                "limit_weight": 0.61,
                "evaluation_status": "pass",
            },
            "symbol_contributions": [
                {
                    "symbol": "AAA",
                    "action": "buy",
                    "current_weight": 0.4,
                    "target_weight": 0.6,
                    "delta_weight": 0.2,
                    "absolute_delta_weight": 0.2,
                    "turnover_contribution_weight": 0.1,
                    "contribution_fraction_of_reported_turnover": 0.16666667,
                    "included_in_reported_turnover": True,
                },
                {
                    "symbol": "BBB",
                    "action": "sell",
                    "current_weight": 0.6,
                    "target_weight": 0.0,
                    "delta_weight": -0.6,
                    "absolute_delta_weight": 0.6,
                    "turnover_contribution_weight": 0.3,
                    "contribution_fraction_of_reported_turnover": 0.5,
                    "included_in_reported_turnover": True,
                },
                {
                    "symbol": "CCC",
                    "action": "initiate",
                    "current_weight": 0.0,
                    "target_weight": 0.4,
                    "delta_weight": 0.4,
                    "absolute_delta_weight": 0.4,
                    "turnover_contribution_weight": 0.2,
                    "contribution_fraction_of_reported_turnover": 0.33333333,
                    "included_in_reported_turnover": True,
                },
            ],
        },
    }
    turnover_mutator(payload)

    with pytest.raises(ValidationError):
        ConstructionArtifactReplayProvenance.model_validate(payload)


@pytest.mark.parametrize(
    "weighting_mutator",
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
def test_construction_artifact_replay_provenance_fails_closed_for_invalid_weighting_trace(weighting_mutator) -> None:
    payload = {
        "construction_artifact_id": "construction_artifact_1234567890abcdef",
        "policy_id": "top_n_equal_weight_v1",
        "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
        "hard_constraints": {
            "full_investment": True,
            "long_only": True,
            "eligible_ranked_universe_only": True,
            "max_position_weight": 0.6,
            "min_position_weight": None,
            "max_turnover_weight": None,
            "max_trade_intent_count": None,
        },
        "selection_rule_trace": {"rule_ids": [], "steps": []},
        "turnover_diagnostics_status": "unavailable_legacy_artifact",
        "turnover_diagnostics_v1": None,
        "weighting_trace_status": "available",
        "weighting_trace_v1": {
            "trace_version": "weighting_trace_v1",
            "source": "persisted_construction_artifact",
            "diagnostic_truth": "artifact_backed_hypothetical_construction_diagnostics_only",
            "policy_id": "top_n_equal_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
            "stages": [
                {
                    "stage_id": "selected_order_to_raw_weight_numerator",
                    "stage_order": 1,
                    "input_metric_id": "selected_order",
                    "output_metric_id": "raw_weight_numerator",
                    "positions": [
                        {"symbol": "AAA", "rank": 1, "selected_order": 1, "input_value": 1.0, "output_value": 1.0},
                        {"symbol": "BBB", "rank": 2, "selected_order": 2, "input_value": 2.0, "output_value": 1.0},
                    ],
                },
                {
                    "stage_id": "raw_weight_numerator_to_seed_weight",
                    "stage_order": 2,
                    "input_metric_id": "raw_weight_numerator",
                    "output_metric_id": "seed_weight",
                    "positions": [
                        {"symbol": "AAA", "rank": 1, "selected_order": 1, "input_value": 1.0, "output_value": 0.5},
                        {"symbol": "BBB", "rank": 2, "selected_order": 2, "input_value": 1.0, "output_value": 0.5},
                    ],
                },
                {
                    "stage_id": "seed_weight_to_target_weight",
                    "stage_order": 3,
                    "input_metric_id": "seed_weight",
                    "output_metric_id": "target_weight",
                    "positions": [
                        {"symbol": "AAA", "rank": 1, "selected_order": 1, "input_value": 0.5, "output_value": 0.5},
                        {"symbol": "BBB", "rank": 2, "selected_order": 2, "input_value": 0.5, "output_value": 0.5},
                    ],
                },
            ],
            "normalization": {
                "normalization_source": "raw_weight_numerator_to_seed_weight",
                "normalization_applied": True,
                "input_metric_id": "raw_weight_numerator",
                "output_metric_id": "seed_weight",
                "raw_value_sum": 2.0,
                "normalized_value_sum": 1.0,
                "rounding_scale": 8,
                "normalization_method": "fractional_sum_division_with_last_position_reconciliation",
                "residual_reconciliation_symbol": "BBB",
                "residual_reconciliation_delta": 0.0,
            },
            "artifact_binding": {
                "binding_status": "final_target_weights_persisted",
                "final_target_weights_present": True,
            },
        },
    }
    weighting_mutator(payload)

    with pytest.raises(ValidationError):
        ConstructionArtifactReplayProvenance.model_validate(payload)


def test_construction_artifact_replay_provenance_accepts_explicit_empty_selection_trace() -> None:
    provenance = ConstructionArtifactReplayProvenance.model_validate(
        {
            "construction_artifact_id": "construction_artifact_1234567890abcdef",
            "policy_id": "top_n_equal_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
            "top_n": 2,
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
                "min_position_weight": None,
                "max_turnover_weight": None,
                "max_trade_intent_count": None,
            },
            "selection_rule_trace": {"rule_ids": [], "steps": []},
            "turnover_diagnostics_status": "unavailable_legacy_artifact",
            "turnover_diagnostics_v1": None,
            "weighting_trace_status": "unavailable_legacy_artifact",
            "weighting_trace_v1": None,
        }
    )

    assert provenance.selection_rule_trace.model_dump(mode="json") == {"rule_ids": [], "steps": []}


def test_construction_artifact_replay_provenance_rejects_missing_hard_constraints() -> None:
    with pytest.raises(ValidationError):
        ConstructionArtifactReplayProvenance.model_validate(
            {
                "construction_artifact_id": "construction_artifact_1234567890abcdef",
                "policy_id": "top_n_equal_weight_v1",
                "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
                "selection_rule_trace": {"rule_ids": [], "steps": []},
                "turnover_diagnostics_status": "unavailable_legacy_artifact",
                "turnover_diagnostics_v1": None,
                "weighting_trace_status": "unavailable_legacy_artifact",
                "weighting_trace_v1": None,
            }
        )


def test_build_construction_artifact_replay_preview_echoes_empty_selection_trace_for_legacy_artifact(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
    }
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-legacy-trace",
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
        }),
        artifact_store=artifact_store,
    )
    original_path = tmp_path / f"{artifact.artifact_id}.json"
    payload = json.loads(original_path.read_text(encoding="utf-8"))
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
    original_path.unlink()
    legacy_path = tmp_path / f"{legacy_artifact_id}.json"
    legacy_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=legacy_artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.replay_provenance.selection_rule_trace.model_dump(mode="json") == {
        "rule_ids": [],
        "steps": [],
    }
    assert replay_response.replay_provenance.turnover_diagnostics_status == "unavailable_legacy_artifact"
    assert replay_response.replay_provenance.turnover_diagnostics_v1 is None
    assert replay_response.replay_provenance.weighting_trace_status == "unavailable_legacy_artifact"
    assert replay_response.replay_provenance.weighting_trace_v1 is None


def test_build_construction_artifact_replay_preview_uses_persisted_turnover_diagnostics_directly(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-persisted-turnover-diagnostics",
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
        }),
        artifact_store=artifact_store,
    )
    assert artifact.turnover_diagnostics_v1 is not None
    diagnostics_payload = artifact.turnover_diagnostics_v1.model_dump(mode="json")
    replacement_payload = {
        **diagnostics_payload,
        "reported_turnover_weight": 0.12345678,
        "symbol_contributions": [],
    }
    legacy_artifact_id = _rewrite_construction_artifact_payload(
        tmp_path,
        artifact.artifact_id,
        lambda payload: payload.__setitem__("turnover_diagnostics_v1", replacement_payload),
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=legacy_artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.replay_provenance.turnover_diagnostics_v1 is not None
    assert replay_response.replay_provenance.turnover_diagnostics_v1.reported_turnover_weight == 0.12345678


def test_build_construction_artifact_replay_preview_echoes_persisted_turnover_symbol_contributions_directly(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-persisted-turnover-symbol-contributions",
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
        }),
        artifact_store=artifact_store,
    )
    assert artifact.turnover_diagnostics_v1 is not None
    diagnostics_payload = artifact.turnover_diagnostics_v1.model_dump(mode="json")
    replacement_payload = {
        **diagnostics_payload,
        "symbol_contributions": [],
    }
    legacy_artifact_id = _rewrite_construction_artifact_payload(
        tmp_path,
        artifact.artifact_id,
        lambda payload: payload.__setitem__("turnover_diagnostics_v1", replacement_payload),
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=legacy_artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.replay_provenance.turnover_diagnostics_v1 is not None
    assert replay_response.replay_provenance.turnover_diagnostics_v1.symbol_contributions == []


def test_build_construction_artifact_replay_preview_uses_persisted_weighting_trace_directly(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-persisted-weighting-trace",
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
        }),
        artifact_store=artifact_store,
    )
    legacy_artifact_id = _rewrite_construction_artifact_payload(
        tmp_path,
        artifact.artifact_id,
        lambda payload: payload["weighting_trace_v1"]["normalization"].__setitem__("residual_reconciliation_delta", 0.12345678),
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=legacy_artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.replay_provenance.weighting_trace_v1 is not None
    assert replay_response.replay_provenance.weighting_trace_v1.normalization.residual_reconciliation_delta == 0.12345678


def test_build_construction_artifact_replay_preview_fails_closed_for_contradictory_persisted_min_position_state(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-contradictory-min-position",
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
        }),
        artifact_store=artifact_store,
    )
    contradictory_artifact_id = _rewrite_construction_artifact_payload(
        tmp_path,
        artifact.artifact_id,
        lambda payload: payload["constraint_evaluations"][4].update({"status": "pass", "actual_value": 0.49}),
    )

    with pytest.raises(
        Exception,
        match="persisted construction artifact failed schema validation",
    ):
        build_construction_artifact_replay_preview(
            ConstructionArtifactReplayRequest(
                construction_artifact_id=contradictory_artifact_id,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                initial_capital=100000,
                execution_lag_days=1,
            ),
            artifact_store=artifact_store,
        )


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
def test_build_construction_artifact_replay_preview_fixture_matrix_preserves_legacy_behavior(
    tmp_path,
    mocker,
    fixture_name,
    expected_selection_rule_trace,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()

    reference_store = ConstructionArtifactStore(str(tmp_path / "reference"))
    reference_artifact_id, _ = _persist_construction_artifact_fixture(
        tmp_path / "reference",
        "construction_artifact_reference.json",
    )
    reference = build_construction_artifact_replay_preview(
        _construction_artifact_replay_request(reference_artifact_id),
        artifact_store=reference_store,
    )

    artifact_store = ConstructionArtifactStore(str(tmp_path / "fixture"))
    artifact_id, _ = _persist_construction_artifact_fixture(tmp_path / "fixture", fixture_name)
    replay_response = build_construction_artifact_replay_preview(
        _construction_artifact_replay_request(artifact_id),
        artifact_store=artifact_store,
    )

    expected_provenance = reference.replay_provenance.model_dump(mode="json")
    expected_provenance["construction_artifact_id"] = artifact_id
    expected_provenance["selection_rule_trace"] = (
        expected_selection_rule_trace
        or reference.replay_provenance.selection_rule_trace.model_dump(mode="json")
    )
    if expected_selection_rule_trace is not None:
        expected_provenance["weighting_trace_status"] = "unavailable_legacy_artifact"
        expected_provenance["weighting_trace_v1"] = None

    assert replay_response.construction_artifact_id == artifact_id
    assert replay_response.truth_separation.model_dump(mode="json") == reference.truth_separation.model_dump(mode="json")
    assert [item.model_dump(mode="json") for item in replay_response.baseline_weights] == [
        item.model_dump(mode="json") for item in reference.baseline_weights
    ]
    assert [item.model_dump(mode="json") for item in replay_response.candidate_weights] == [
        item.model_dump(mode="json") for item in reference.candidate_weights
    ]
    assert replay_response.replay.model_dump(mode="json") == reference.replay.model_dump(mode="json")
    assert replay_response.replay_provenance.model_dump(mode="json") == expected_provenance


@pytest.mark.parametrize(
    "fixture_name",
    [
        "construction_artifact_malformed_partial_selection_trace_missing_rule_ids.json",
        "construction_artifact_malformed_partial_selection_trace_empty_rule_ids.json",
    ],
    ids=["missing_rule_ids", "empty_rule_ids"],
)
def test_build_construction_artifact_replay_preview_fixture_matrix_rejects_partial_malformed_selection_trace(
    tmp_path,
    mocker,
    fixture_name,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = _construction_artifact_replay_histories()
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact_id, _ = _persist_construction_artifact_fixture(tmp_path, fixture_name)

    with pytest.raises(
        ValueError,
        match="persisted construction artifact failed schema validation",
    ):
        build_construction_artifact_replay_preview(
            _construction_artifact_replay_request(artifact_id),
            artifact_store=artifact_store,
        )


def test_build_construction_artifact_replay_preview_hydrates_missing_legacy_policy_definition_id(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
    }
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-legacy-policy-definition",
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
        }),
        artifact_store=artifact_store,
    )
    legacy_artifact_id = _rewrite_construction_artifact_payload(
        tmp_path,
        artifact.artifact_id,
        lambda payload: payload["normalized_inputs"].pop("policy_definition_id"),
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=legacy_artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.construction_artifact_id == legacy_artifact_id
    assert replay_response.replay_provenance.policy_definition_id == "construction_policy_definition_top_n_equal_weight_v1"


def test_build_construction_artifact_replay_preview_accepts_legacy_artifact_without_max_turnover_weight(
    tmp_path,
    mocker,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
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
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-legacy-turnover-field",
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
        }),
        artifact_store=artifact_store,
    )
    legacy_artifact_id = _rewrite_construction_artifact_payload(
        tmp_path,
        artifact.artifact_id,
        lambda payload: payload["hard_constraints"].pop("max_turnover_weight", None),
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=legacy_artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert replay_response.construction_artifact_id == legacy_artifact_id
    assert replay_response.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.5),
        PortfolioWeightInput(symbol="BBB", target_weight=0.5),
    ]


@pytest.mark.parametrize(
    "turnover_mutator",
    [
            lambda payload: payload["hard_constraints"].pop("max_turnover_weight", None),
        lambda payload: payload["hard_constraints"].__setitem__("max_turnover_weight", None),
    ],
    ids=["missing", "explicit_null"],
)
def test_build_construction_artifact_replay_preview_treats_missing_and_explicit_null_turnover_caps_as_legacy_equivalent(
    tmp_path,
    mocker,
    turnover_mutator,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
    }
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-turnover-null-parity",
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
        }),
        artifact_store=artifact_store,
    )

    legacy_artifact_id = _rewrite_construction_artifact_payload(
        tmp_path,
        artifact.artifact_id,
        turnover_mutator,
    )

    replay_response = build_construction_artifact_replay_preview(
        ConstructionArtifactReplayRequest(
            construction_artifact_id=legacy_artifact_id,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        artifact_store=artifact_store,
    )

    assert legacy_artifact_id == artifact.artifact_id
    assert replay_response.construction_artifact_id == artifact.artifact_id
    assert replay_response.candidate_weights == [
        PortfolioWeightInput(symbol="AAA", target_weight=0.5),
        PortfolioWeightInput(symbol="BBB", target_weight=0.5),
    ]


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
def test_build_construction_artifact_replay_preview_rejects_partial_malformed_selection_trace(
    tmp_path,
    mocker,
    selection_rule_trace,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
    }
    artifact_store = ConstructionArtifactStore(str(tmp_path))
    artifact = build_construction_run(
        ConstructionRunRequest.model_validate({
            "request_id": "construction-replay-malformed-trace",
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
        }),
        artifact_store=artifact_store,
    )
    artifact_path = tmp_path / f"{artifact.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["selection_rule_trace"] = selection_rule_trace
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(
        ValueError,
        match="persisted construction artifact failed schema validation",
    ):
        build_construction_artifact_replay_preview(
            ConstructionArtifactReplayRequest(
                construction_artifact_id=artifact.artifact_id,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                initial_capital=100000,
                execution_lag_days=1,
            ),
            artifact_store=artifact_store,
        )


@pytest.mark.parametrize(
    "legacy_manifest_mutator",
    [
        lambda payload: payload["return_basis_attestation"].pop("factor_basis_path", None),
        lambda payload: payload["return_basis_attestation"].update({"factor_basis_path": None}),
    ],
    ids=["missing_factor_basis_path", "null_factor_basis_path"],
)
def test_build_optimizer_handoff_replay_preview_normalizes_legacy_factor_basis_variants_with_canonical_parity(
    tmp_path,
    mocker,
    legacy_manifest_mutator,
) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 103.0, 104.0, 106.0, 109.0),
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
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    canonical_response = build_optimizer_handoff_replay_preview(
        OptimizerHandoffReplayRequest(
            handoff_reference=preview_response.persisted_handoff,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        handoff_store=handoff_store,
    )

    _mutate_persisted_json(
        preview_response.persisted_handoff.manifest_path,
        legacy_manifest_mutator,
    )

    legacy_response = build_optimizer_handoff_replay_preview(
        OptimizerHandoffReplayRequest(
            handoff_reference=preview_response.persisted_handoff,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        handoff_store=handoff_store,
    )

    assert legacy_response.replay_provenance.return_basis_attestation.model_dump() == canonical_response.replay_provenance.return_basis_attestation.model_dump()
    assert legacy_response.replay_provenance.return_basis_attestation.factor_basis_path == "degraded_unverified_return_basis"
    assert legacy_response.replay_provenance.replay_output_policy.model_dump() == canonical_response.replay_provenance.replay_output_policy.model_dump()
    assert (
        legacy_response.replay_provenance.benchmark_id,
        legacy_response.replay_provenance.benchmark_version,
        legacy_response.replay_provenance.benchmark_symbol,
    ) == (
        canonical_response.replay_provenance.benchmark_id,
        canonical_response.replay_provenance.benchmark_version,
        canonical_response.replay_provenance.benchmark_symbol,
    )
    assert legacy_response.replay.candidate_result.investor_economics_status == canonical_response.replay.candidate_result.investor_economics_status
    assert legacy_response.replay.candidate_diagnostics is not None
    assert canonical_response.replay.candidate_diagnostics is not None
    assert legacy_response.replay.candidate_diagnostics.factor_snapshot == canonical_response.replay.candidate_diagnostics.factor_snapshot == []
    assert legacy_response.replay.candidate_diagnostics.risk_contribution is not None
    assert canonical_response.replay.candidate_diagnostics.risk_contribution is not None
    assert (
        legacy_response.replay.candidate_diagnostics.risk_contribution.factor_contributions
        == canonical_response.replay.candidate_diagnostics.risk_contribution.factor_contributions
        == []
    )
    assert legacy_response.replay.diagnostics_comparison is not None
    assert canonical_response.replay.diagnostics_comparison is not None
    assert (
        legacy_response.replay.diagnostics_comparison.factor_exposure_changes
        == canonical_response.replay.diagnostics_comparison.factor_exposure_changes
        == []
    )


def test_optimizer_handoff_replay_request_rejects_removed_benchmark_symbol_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OptimizerHandoffReplayRequest.model_validate(
            {
                "handoff_reference": {
                "reference_kind": "optimizer_handoff_reference_v1",
                "handoff_id": "optimizer_handoff_demo",
                "artifact_id": "opt_artifact_demo",
                "manifest_path": "C:/tmp/manifest.json",
                "artifact_path": "C:/tmp/artifact.json",
                },
                "benchmark_symbol": "QQQ",
                "start_date": date(2024, 1, 1),
                "end_date": date(2024, 12, 31),
            }
        )

    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_optimizer_handoff_replay_route_returns_explicit_reference_contract(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 103.0, 104.0, 106.0, 109.0),
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
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)
    client = TestClient(app)

    assert preview_response.persisted_handoff is not None
    response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": preview_response.persisted_handoff.model_dump(mode="json"),
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["handoff_id"] == preview_response.persisted_handoff.handoff_id
    assert payload["artifact_id"] == preview_response.persisted_handoff.artifact_id
    assert payload["truth_separation"] == {
        "baseline_truth": "imported_portfolio_snapshot",
        "candidate_truth": "hypothetical_optimizer_handoff",
        "candidate_applied": False,
        "consumption_mode": "explicit_reference_only",
    }
    assert payload["replay_provenance"]["source"] == "optimizer_handoff_reference"
    assert payload["replay_provenance"]["benchmark_id"] == "benchmark_spy_demo_v1"
    assert payload["replay_provenance"]["benchmark_version"] == "2024-04-15"
    assert payload["replay_provenance"]["benchmark_symbol"] == "SPY"
    assert payload["replay_provenance"]["replay_output_policy"] == {
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
    assert "objective_id" not in payload["optimizer_context"]
    assert payload["optimizer_context"]["objective"]["objective_id"] == "minimize_l2_distance_to_benchmark"
    assert payload["optimizer_context"]["run_summary"]["solver_id"] == "deterministic_projected_dykstra_v1"
    assert payload["optimizer_context"]["diagnostics"]["turnover"] == 0.2
    assert payload["optimizer_context"]["benchmark_relative_attestations"][0]["attestation_id"] == "benchmark_relative_max_abs_active_weight"
    assert payload["candidate_weights"][2] == {"symbol": "CCC", "target_weight": 0.2}


def test_optimizer_handoff_replay_route_rejects_non_canonical_reference(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {}
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)
    client = TestClient(app)

    assert preview_response.persisted_handoff is not None
    bad_reference = preview_response.persisted_handoff.model_copy(update={"handoff_id": "optimizer_handoff_wrong"})
    response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff-preview",
        json={
            "handoff_reference": bad_reference.model_dump(mode="json"),
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    payload = response.json()["detail"]
    assert payload["handoff_id"] is None
    assert payload["artifact_id"] is None
    assert payload["validation_status"] == "blocked"
    assert payload["blocking_rule_ids"] == ["persisted_payload_accessible"]
    assert payload["provenance"]["source"] == "optimizer_handoff_reference"


def test_validate_optimizer_handoff_constraints_returns_ok_with_explicit_reference(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "ok"
    assert response.blocking_rule_ids == []
    assert {item.reason_family for item in response.evaluations} == {
        "schema",
        "benchmark_context",
        "constraint_violation",
        "provenance",
        "truth_separation",
    }
    assert response.truth_separation.model_dump() == {
        "source_truth": "persisted_hypothetical_optimizer_handoff",
        "holdings_truth": "imported_portfolio_snapshot",
        "optimizer_output_applied": False,
        "consumption_mode": "explicit_reference_only",
    }
    assert response.provenance.benchmark_symbol == "SPY"
    assert response.provenance.benchmark_id == "benchmark_spy_demo_v1"
    assert response.provenance.benchmark_version == "2024-04-15"
    assert response.provenance.objective is not None
    assert response.provenance.objective.objective_id == "minimize_l2_distance_to_benchmark"
    assert response.eligible_replay_window is not None
    assert response.eligible_replay_window.model_dump() == {
        "source": "persisted_return_basis_attestation",
        "benchmark_symbol": "SPY",
        "as_of_date": "2024-12-31",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }
    assert response.replay_handoff is None
    assert response.provenance.replay_output_policy is not None
    assert response.provenance.replay_output_policy.model_dump() == {
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
    assert any(item.phase == "raw_persisted_payload" for item in response.evaluations)
    assert any(item.rule_id == "artifact_feasible" and item.status == "pass" for item in response.evaluations)


def test_optimizer_handoff_roundtrip_preserves_alpha_objective_metadata_in_validation_and_replay(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 103.0, 104.0, 106.0, 109.0),
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
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)
    result = run_optimizer(
        OptimizationRequest(
            request_id="alpha-handoff-roundtrip",
            as_of_timestamp="2024-04-15T09:30:00",
            effective_timestamp="2024-04-15T09:30:00",
            universe_id="optimizer_universe_large_cap_demo_v1",
            benchmark_id="benchmark_spy_demo_v1",
            current_portfolio_weights=[OptimizerWeight(symbol="AAA", weight=0.6), OptimizerWeight(symbol="BBB", weight=0.4)],
            benchmark_weights=[OptimizerWeight(symbol="AAA", weight=0.5), OptimizerWeight(symbol="BBB", weight=0.3), OptimizerWeight(symbol="CCC", weight=0.2)],
            universe=[OptimizerUniverseAsset(symbol="AAA", eligible=True), OptimizerUniverseAsset(symbol="BBB", eligible=True), OptimizerUniverseAsset(symbol="CCC", eligible=True)],
            objective=OptimizerObjective(objective_id="maximize_alpha_quality_v1"),
            hard_constraints=_optimizer_preview_request().hard_constraints,
            alpha_package=_optimizer_alpha_package(),
        )
    )
    assert result.artifact is not None
    handoff_reference = handoff_store.persist_handoff(
        artifact=result.artifact,
        snapshot_reference=OptimizerPreviewSnapshotReference(
            snapshot_id="portfolio_snapshot_alpha_roundtrip",
            account_id="U1234567",
            importer="interactive_brokers",
            imported_at="2024-04-15T09:30:00+00:00",
            statement_period="2024-04",
            source_files=["IB2024.pdf"],
        ),
        benchmark=_optimizer_preview_request().benchmark,
        return_basis_attestation=preview_response.provenance.return_basis_attestation,
    )

    validation = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=handoff_reference),
        handoff_store=handoff_store,
    )
    replay_response = build_optimizer_handoff_replay_preview(
        OptimizerHandoffReplayRequest(
            handoff_reference=handoff_reference,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        handoff_store=handoff_store,
    )

    assert validation.validation_status == "ok"
    assert validation.replay_handoff is None
    assert validation.provenance.objective is not None
    assert validation.provenance.objective.objective_id == "maximize_alpha_quality_v1"
    assert replay_response.optimizer_context is not None
    assert "objective_id" not in replay_response.optimizer_context.model_dump()
    assert replay_response.optimizer_context.objective is not None
    assert replay_response.optimizer_context.objective.alpha_signal_id == "alpha_quality_v1"


def test_validate_optimizer_handoff_constraints_allows_missing_validation_artifact_id_when_handoff_matches(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "ok"
    assert response.handoff_id == preview_response.persisted_handoff.handoff_id
    assert response.model_dump(mode="json").get("artifact_id") == preview_response.persisted_handoff.artifact_id


def test_validate_optimizer_handoff_constraints_emits_canonical_replay_handoff_when_candidate_window_is_requested(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(
            handoff_reference=preview_response.persisted_handoff,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        ),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "ok"
    assert response.replay_handoff is not None
    assert response.replay_handoff.model_dump(mode="json") == {
        "handoff_kind": "optimizer_handoff_replay_handoff_v1",
        "handoff_reference": preview_response.persisted_handoff.model_dump(mode="json"),
        "effective_replay_params": {
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
    }


def test_build_optimizer_handoff_replay_preview_accepts_validation_replay_handoff_verbatim(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    mock_service.return_value.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "AAA": _history(100.0, 101.0, 102.0, 103.0, 104.0),
        "BBB": _history(100.0, 100.5, 101.0, 101.5, 102.0),
        "CCC": _history(100.0, 103.0, 104.0, 106.0, 109.0),
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
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    validation_response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(
            handoff_reference=preview_response.persisted_handoff,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        ),
        handoff_store=handoff_store,
    )

    assert validation_response.replay_handoff is not None
    replay_from_handoff = build_optimizer_handoff_replay_preview(validation_response.replay_handoff, handoff_store=handoff_store)
    replay_from_request = build_optimizer_handoff_replay_preview(
        OptimizerHandoffReplayRequest(
            handoff_reference=preview_response.persisted_handoff,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
            initial_capital=100000,
            execution_lag_days=1,
        ),
        handoff_store=handoff_store,
    )

    assert replay_from_handoff.model_dump(mode="json") == replay_from_request.model_dump(mode="json")


def test_validate_optimizer_handoff_constraints_blocks_handoff_reference_artifact_mismatch_even_when_handoff_path_resolves(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    bad_reference = preview_response.persisted_handoff.model_copy(update={"artifact_id": "opt_artifact_wrong"})
    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=bad_reference),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert "artifact_reference_matches_artifact" in response.blocking_rule_ids
    assert response.handoff_id == preview_response.persisted_handoff.handoff_id
    assert response.model_dump(mode="json").get("artifact_id") == preview_response.persisted_handoff.artifact_id


def test_build_optimizer_handoff_replay_preview_blocks_reference_artifact_mismatch_before_market_data(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    bad_reference = preview_response.persisted_handoff.model_copy(update={"artifact_id": "opt_artifact_wrong"})
    with pytest.raises(OptimizerHandoffValidationBlockedError) as exc_info:
        build_optimizer_handoff_replay_preview(
            OptimizerHandoffReplayRequest(
                handoff_reference=bad_reference,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                initial_capital=100000,
                execution_lag_days=1,
            ),
            handoff_store=handoff_store,
        )

    assert exc_info.value.response.validation_status == "blocked"
    assert "artifact_reference_matches_artifact" in exc_info.value.response.blocking_rule_ids
    mock_service.assert_not_called()


@pytest.mark.parametrize(
    "legacy_manifest_mutator",
    [
        lambda payload: payload["return_basis_attestation"].pop("factor_basis_path", None),
        lambda payload: payload["return_basis_attestation"].update({"factor_basis_path": None}),
    ],
    ids=["missing_factor_basis_path", "null_factor_basis_path"],
)
def test_validate_optimizer_handoff_constraints_normalizes_legacy_factor_basis_variants_with_canonical_parity(
    tmp_path,
    legacy_manifest_mutator,
) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    canonical_response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    _mutate_persisted_json(preview_response.persisted_handoff.manifest_path, legacy_manifest_mutator)

    legacy_response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert legacy_response.validation_status == canonical_response.validation_status == "ok"
    assert legacy_response.blocking_rule_ids == canonical_response.blocking_rule_ids == []
    assert legacy_response.provenance.replay_output_policy is not None
    assert canonical_response.provenance.replay_output_policy is not None
    assert (
        legacy_response.provenance.replay_output_policy.model_dump()
        == canonical_response.provenance.replay_output_policy.model_dump()
    )
    assert legacy_response.provenance.replay_output_policy.section_trust.factor_model_path == "degraded_unverified_return_basis"
    assert legacy_response.provenance.replay_output_policy.section_trust.risk_contribution_path == "degraded_unverified_return_basis"


@pytest.mark.parametrize(
    "section_trust_mutator",
    [
        lambda attestation: attestation.pop("section_trust", None),
        lambda attestation: attestation.update({"section_trust": {}}),
    ],
    ids=["missing_section_trust", "malformed_section_trust"],
)
def test_validate_optimizer_handoff_constraints_does_not_unlock_factor_families_without_valid_section_trust(
    tmp_path,
    section_trust_mutator,
) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None

    def _remove_factor_basis_with_invalid_section_trust(payload: dict) -> None:
        attestation = payload["return_basis_attestation"]
        attestation.pop("factor_basis_path", None)
        section_trust_mutator(attestation)

    _mutate_persisted_json(
        preview_response.persisted_handoff.manifest_path,
        _remove_factor_basis_with_invalid_section_trust,
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert "manifest_model_valid" in response.blocking_rule_ids
    assert response.provenance.replay_output_policy is None


def test_validate_optimizer_handoff_constraints_maps_replay_output_families_from_persisted_section_trust(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.manifest_path,
        lambda payload: payload["return_basis_attestation"].update(
            {
                "factor_basis_path": "unavailable",
                "section_trust": {
                    "benchmark_relative_path": "verified_adjusted_close",
                    "factor_model_path": "unavailable",
                    "risk_contribution_path": "verified_adjusted_close",
                },
            }
        ),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert response.blocking_rule_ids == ["manifest_artifact_consistent"]
    assert response.provenance.replay_output_policy is not None
    assert response.provenance.replay_output_policy.model_dump() == {
        "source": "persisted_return_basis_attestation",
        "section_trust": {
            "benchmark_relative_path": "verified_adjusted_close",
            "factor_model_path": "unavailable",
            "risk_contribution_path": "unavailable",
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


def test_validate_optimizer_handoff_constraints_prefers_persisted_factor_basis_path_for_factor_families(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.manifest_path,
        lambda payload: payload["return_basis_attestation"].update(
            {
                "factor_basis_path": "unavailable",
                "section_trust": {
                    "benchmark_relative_path": "verified_adjusted_close",
                    "factor_model_path": "verified_adjusted_close",
                    "risk_contribution_path": "verified_adjusted_close",
                },
            }
        ),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert response.blocking_rule_ids == ["manifest_artifact_consistent"]
    assert response.provenance.replay_output_policy is not None
    assert response.provenance.replay_output_policy.model_dump() == {
        "source": "persisted_return_basis_attestation",
        "section_trust": {
            "benchmark_relative_path": "verified_adjusted_close",
            "factor_model_path": "unavailable",
            "risk_contribution_path": "unavailable",
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


def test_validate_optimizer_handoff_constraints_normalizes_loaded_attestation_before_policy_mapping(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    canonical_response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    _mutate_persisted_json(
        preview_response.persisted_handoff.manifest_path,
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

    normalized_response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert canonical_response.provenance.replay_output_policy is not None
    assert normalized_response.provenance.replay_output_policy is not None
    assert canonical_response.validation_status == "ok"
    assert canonical_response.blocking_rule_ids == []
    assert normalized_response.validation_status == "blocked"
    assert normalized_response.blocking_rule_ids == ["manifest_artifact_consistent"]
    assert normalized_response.provenance.replay_output_policy.model_dump() == {
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


def test_validate_optimizer_handoff_constraints_uses_persisted_benchmark_symbol_only(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(
            handoff_reference=preview_response.persisted_handoff,
        ),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "ok"
    assert response.provenance.benchmark_symbol == "SPY"
    assert all(item.rule_id != "request_benchmark_matches_persisted" for item in response.evaluations)
    assert any(item.rule_id == "persisted_return_basis_attestation_present" and item.status == "pass" for item in response.evaluations)


def test_validate_optimizer_handoff_constraints_blocks_replay_window_outside_attested_coverage(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    with pytest.raises(OptimizerHandoffValidationBlockedError) as exc_info:
        build_optimizer_handoff_replay_preview(
            OptimizerHandoffReplayRequest(
                handoff_reference=preview_response.persisted_handoff,
                start_date=date(2023, 12, 31),
                end_date=date(2024, 12, 31),
                initial_capital=100000,
                execution_lag_days=1,
            ),
            handoff_store=handoff_store,
        )

    response = exc_info.value.response
    assert response.validation_status == "blocked"
    assert "requested_replay_window_within_attested_return_basis_coverage" in response.blocking_rule_ids
    assert response.eligible_replay_window is not None
    assert response.eligible_replay_window.start_date == "2024-01-01"
    assert response.eligible_replay_window.end_date == "2024-12-31"
    evaluation = next(item for item in response.evaluations if item.rule_id == "requested_replay_window_within_attested_return_basis_coverage")
    assert evaluation.status == "fail"
    assert evaluation.actual_value == "2023-12-31..2024-12-31"
    assert evaluation.expected_value == "2024-01-01..2024-12-31"


def test_validate_optimizer_handoff_constraints_returns_candidate_window_check_when_requested(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(
            handoff_reference=preview_response.persisted_handoff,
            start_date=date(2024, 1, 1),
            end_date=date(2024, 12, 31),
        ),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "ok"
    evaluation = next(item for item in response.evaluations if item.rule_id == "requested_replay_window_within_attested_return_basis_coverage")
    assert evaluation.status == "pass"
    assert evaluation.actual_value == "2024-01-01..2024-12-31"
    assert evaluation.expected_value == "2024-01-01..2024-12-31"


def test_optimizer_handoff_validation_request_requires_candidate_window_dates_together() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OptimizerHandoffValidationRequest.model_validate(
            {
                "handoff_reference": {
                    "reference_kind": "optimizer_handoff_reference_v1",
                    "handoff_id": "optimizer_handoff_demo",
                    "artifact_id": "opt_artifact_demo",
                    "manifest_path": "C:/tmp/manifest.json",
                    "artifact_path": "C:/tmp/artifact.json",
                },
                "start_date": "2024-01-01",
            }
        )

    assert "start_date and end_date must be supplied together" in str(exc_info.value)


def test_validate_optimizer_handoff_constraints_blocks_missing_return_basis_attestation(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.manifest_path,
        lambda payload: payload.pop("return_basis_attestation"),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(
            handoff_reference=preview_response.persisted_handoff,
        ),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert "manifest_model_valid" in response.blocking_rule_ids


def test_optimizer_handoff_validation_request_rejects_removed_benchmark_symbol_field() -> None:
    with pytest.raises(ValidationError) as exc_info:
        OptimizerHandoffValidationRequest.model_validate(
            {
                "handoff_reference": {
                "reference_kind": "optimizer_handoff_reference_v1",
                "handoff_id": "optimizer_handoff_demo",
                "artifact_id": "opt_artifact_demo",
                "manifest_path": "C:/tmp/manifest.json",
                "artifact_path": "C:/tmp/artifact.json",
                },
                "benchmark_symbol": "QQQ",
            }
        )

    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_validate_optimizer_handoff_constraints_uses_canonical_persisted_benchmark_symbol(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_request = _optimizer_preview_request()
    preview_request.benchmark.benchmark_symbol = " spy "
    preview_response = build_optimizer_preview(preview_request, handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(
            handoff_reference=preview_response.persisted_handoff,
        ),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "ok"
    assert response.provenance.benchmark_symbol == "SPY"
    assert all(item.rule_id != "request_benchmark_matches_persisted" for item in response.evaluations)


def test_validate_optimizer_handoff_constraints_blocks_schema_failures(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.artifact_path,
        lambda payload: payload.pop("replay"),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert response.blocking_rule_ids == ["artifact_model_valid"]
    assert response.evaluations[-1].reason_family == "schema"
    assert response.provenance.benchmark_id == "benchmark_spy_demo_v1"
    assert response.provenance.artifact_state is None


def test_validate_optimizer_handoff_constraints_blocks_benchmark_context_failure(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.manifest_path,
        lambda payload: payload["benchmark"].update({"benchmark_symbol": None}),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(
            handoff_reference=preview_response.persisted_handoff,
        ),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert "persisted_benchmark_symbol_present" in response.blocking_rule_ids
    assert any(item.rule_id == "persisted_benchmark_symbol_present" and item.reason_family == "benchmark_context" for item in response.evaluations)
    assert all(item.rule_id != "request_benchmark_matches_persisted" for item in response.evaluations)


def test_validate_optimizer_handoff_constraints_blocks_constraint_failure(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.artifact_path,
        lambda payload: _update_constraint_evaluation(payload, "benchmark_relative_max_abs_active_weight", status="violated"),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert "benchmark_relative_attestation_consistency" in response.blocking_rule_ids
    assert "benchmark_relative_constraints_clear" in response.blocking_rule_ids
    assert any(item.rule_id == "benchmark_relative_constraints_clear" and item.reason_family == "constraint_violation" for item in response.evaluations)


def test_validate_optimizer_handoff_constraints_blocks_provenance_failure(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.manifest_path,
        lambda payload: payload.update({"artifact_id": "opt_artifact_wrong"}),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert "manifest_artifact_consistent" in response.blocking_rule_ids
    assert any(item.rule_id == "manifest_artifact_consistent" and item.reason_family == "provenance" for item in response.evaluations)
    assert response.provenance.constraint_set_fingerprint is not None


def test_validate_optimizer_handoff_constraints_blocks_forged_external_paths_before_read(tmp_path, mocker) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)
    read_json = mocker.patch("app.services.optimizer_artifact_service._read_json_object")

    assert preview_response.persisted_handoff is not None
    forged_reference = preview_response.persisted_handoff.model_copy(
        update={
            "manifest_path": str(tmp_path / "forged" / "manifest.json"),
            "artifact_path": str(tmp_path / "forged" / "artifact.json"),
        }
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=forged_reference),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert response.blocking_rule_ids == ["persisted_payload_accessible"]
    assert response.evaluations[-1].reason_family == "provenance"
    assert response.evaluations[-1].message == "handoff reference manifest_path is not the canonical persisted path"
    read_json.assert_not_called()


def test_validate_optimizer_handoff_constraints_blocks_traversal_non_canonical_paths_before_read(tmp_path, mocker) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)
    read_json = mocker.patch("app.services.optimizer_artifact_service._read_json_object")

    assert preview_response.persisted_handoff is not None
    canonical_manifest = Path(preview_response.persisted_handoff.manifest_path)
    canonical_artifact = Path(preview_response.persisted_handoff.artifact_path)
    non_canonical_reference = preview_response.persisted_handoff.model_copy(
        update={
            "manifest_path": str(canonical_manifest.parent / ".." / canonical_manifest.parent.name / canonical_manifest.name),
            "artifact_path": str(canonical_artifact.parent / ".." / canonical_artifact.parent.name / canonical_artifact.name),
        }
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=non_canonical_reference),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert response.blocking_rule_ids == ["persisted_payload_accessible"]
    assert response.evaluations[-1].reason_family == "provenance"
    assert response.evaluations[-1].message == "handoff reference manifest_path is not the canonical persisted path"
    read_json.assert_not_called()


def test_validate_optimizer_handoff_constraints_blocks_truth_separation_failure(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.artifact_path,
        lambda payload: payload["replay"].update({"target_weights": payload["replay"]["current_weights"]}),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert "candidate_target_matches_optimizer_output" in response.blocking_rule_ids
    assert any(item.rule_id == "candidate_target_matches_optimizer_output" and item.reason_family == "truth_separation" for item in response.evaluations)


def test_validate_optimizer_handoff_constraints_blocks_benchmark_misalignment_attestation(tmp_path) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.artifact_path,
        lambda payload: _update_benchmark_attestation(
            payload,
            "benchmark_relative_max_abs_active_weight",
            status="misaligned",
            attestation_type="benchmark_alignment",
        ),
    )

    response = validate_optimizer_handoff_constraints(
        OptimizerHandoffValidationRequest(handoff_reference=preview_response.persisted_handoff),
        handoff_store=handoff_store,
    )

    assert response.validation_status == "blocked"
    assert "benchmark_relative_attestation_consistency" in response.blocking_rule_ids
    assert "benchmark_relative_attestations_clear" in response.blocking_rule_ids


def test_build_optimizer_handoff_replay_preview_aborts_before_market_data_when_validation_blocked(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    _mutate_persisted_json(
        preview_response.persisted_handoff.artifact_path,
        lambda payload: payload["replay"].update({"target_weights": payload["replay"]["current_weights"]}),
    )

    with pytest.raises(OptimizerHandoffValidationBlockedError) as exc_info:
        build_optimizer_handoff_replay_preview(
            OptimizerHandoffReplayRequest(
                handoff_reference=preview_response.persisted_handoff,
                start_date=date(2024, 1, 1),
                end_date=date(2024, 12, 31),
                initial_capital=100000,
                execution_lag_days=1,
            ),
            handoff_store=handoff_store,
        )

    assert exc_info.value.response.validation_status == "blocked"
    assert "candidate_target_matches_optimizer_output" in exc_info.value.response.blocking_rule_ids
    mock_service.assert_not_called()


def test_build_optimizer_handoff_replay_preview_aborts_before_market_data_when_replay_window_outside_attested_coverage(tmp_path, mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)

    assert preview_response.persisted_handoff is not None
    with pytest.raises(OptimizerHandoffValidationBlockedError) as exc_info:
        build_optimizer_handoff_replay_preview(
            OptimizerHandoffReplayRequest(
                handoff_reference=preview_response.persisted_handoff,
                start_date=date(2023, 12, 31),
                end_date=date(2024, 12, 31),
                initial_capital=100000,
                execution_lag_days=1,
            ),
            handoff_store=handoff_store,
        )

    assert exc_info.value.response.validation_status == "blocked"
    assert "requested_replay_window_within_attested_return_basis_coverage" in exc_info.value.response.blocking_rule_ids
    mock_service.assert_not_called()


def test_optimizer_handoff_constraints_route_returns_validation_contract(tmp_path, mocker) -> None:
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    mocker.patch(
        "app.services.optimizer_artifact_service.get_settings",
        return_value=SimpleNamespace(optimizer_handoff_dir=str(tmp_path)),
    )
    preview_response = build_optimizer_preview(_optimizer_preview_request(), handoff_store=handoff_store)
    client = TestClient(app)

    assert preview_response.persisted_handoff is not None
    response = client.post(
        "/backtests/portfolio-allocation/optimizer-handoff/constraints",
        json={
            "handoff_reference": preview_response.persisted_handoff.model_dump(mode="json"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation_status"] == "ok"
    assert payload["truth_separation"] == {
        "source_truth": "persisted_hypothetical_optimizer_handoff",
        "holdings_truth": "imported_portfolio_snapshot",
        "optimizer_output_applied": False,
        "consumption_mode": "explicit_reference_only",
    }
    assert payload["provenance"]["source"] == "optimizer_handoff_reference"
    assert payload["provenance"]["benchmark_id"] == "benchmark_spy_demo_v1"
    assert payload["provenance"]["benchmark_version"] == "2024-04-15"
    assert payload["provenance"]["benchmark_symbol"] == "SPY"
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
    assert payload["eligible_replay_window"] == {
        "source": "persisted_return_basis_attestation",
        "benchmark_symbol": "SPY",
        "as_of_date": "2024-12-31",
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
    }
    assert payload["blocking_rule_ids"] == []
def test_hypothetical_replacement_preview_route_rejects_missing_intent() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [{"symbol": "VUAA", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"}],
                "cash_balances": [],
            },
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement_intent is required"}


def test_hypothetical_replacement_preview_route_rejects_incumbent_not_found() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [{"symbol": "IB01", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"}],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement intent incumbent not found in draft snapshot: VUAA"}


def test_hypothetical_replacement_preview_route_rejects_zero_weight_incumbent() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [
                    {"symbol": "VUAA", "market_value": 0, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement intent incumbent not found in draft snapshot: VUAA"}


def test_hypothetical_replacement_preview_route_rejects_same_symbol_candidate() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [{"symbol": "VUAA", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"}],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent(candidate_symbol="VUAA").model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement intent candidate must differ from incumbent"}


def test_hypothetical_replacement_preview_route_rejects_candidate_already_held() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IUFS", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement intent candidate is already held in draft snapshot: IUFS"}


def test_hypothetical_replacement_preview_route_rejects_candidate_with_missing_history(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "No historical prices found for symbol: IUFS"}


def test_hypothetical_replacement_preview_route_rejects_insufficient_common_dates(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "VUAA": [
            {"date": "2024-01-02", "price": 50.0},
            {"date": "2024-01-03", "price": 51.0},
        ],
        "IB01": [
            {"date": "2024-01-02", "price": 90.0},
            {"date": "2024-01-03", "price": 91.0},
        ],
        "IUFS": [
            {"date": "2024-01-03", "price": 80.0},
        ],
        "QQQ": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Not enough common dates across portfolio symbols and benchmark"}


def test_overlay_aware_hypothetical_replacement_preview_route_returns_base_and_overlay_replays(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IUFS": _history(100.0, 103.0, 103.5, 105.0, 109.0),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
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
        "/backtests/portfolio-allocation/replacement-intent-overlay-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {
                    "importer": "interactive_brokers",
                    "statement_period": "2025-01-01 - 2025-12-31",
                    "imported_at": "2026-04-10T00:00:00Z",
                    "source_file_names": ["IB2025.pdf"],
                },
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "overlay_state": {
                "overlay_id": "benchmark_trend_overlay_v1",
                "status": "risk_reduced",
                "as_of_month_end": "2024-12-31",
                "benchmark_symbol": "SPY",
                "signal_basis": "10_month_sma_month_end",
                "confirmation_count": 2,
                "rule_version": "v1",
            },
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "commission_bps": 2,
            "slippage_bps": 3,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["overlay_application"] == {
        "overlay_id": "benchmark_trend_overlay_v1",
        "overlay_status": "risk_reduced",
        "as_of_month_end": "2024-12-31",
        "benchmark_symbol": "SPY",
        "risky_weight_scale": 0.35,
        "cash_residual_weight": 0.65,
        "applied_to_candidate_only": True,
    }
    assert payload["derivation"] == {
        "baseline_basis": "draft_snapshot_positions_normalized",
        "candidate_construction_rule": "same_weight_substitution_v1",
    }
    assert payload["replay_provenance"] == {
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
    }
    assert payload["candidate_weights_pre_overlay"] == [
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.6},
    ]
    assert payload["candidate_weights_post_overlay"] == [
        {"symbol": "IB01", "target_weight": 0.14},
        {"symbol": "IUFS", "target_weight": 0.21},
        {"symbol": "__CASH__", "target_weight": 0.65},
    ]
    assert payload["base_replay"]["candidate_result"]["portfolio_name"] == "Hypothetical Candidate"
    assert payload["overlay_replay"]["candidate_result"]["portfolio_name"] == "Hypothetical Candidate Overlay-Aware"
    assert payload["overlay_replay"]["candidate_result"]["starting_weights"][-1]["symbol"] == "__CASH__"
    assert payload["base_replay"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["overlay_replay"]["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }


def test_overlay_aware_hypothetical_replacement_preview_route_rejects_unconfirmed_overlay() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-overlay-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [{"symbol": "VUAA", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"}],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "overlay_state": {
                "overlay_id": "benchmark_trend_overlay_v1",
                "status": "unconfirmed",
                "as_of_month_end": "2024-12-31",
                "benchmark_symbol": "SPY",
                "signal_basis": "10_month_sma_month_end",
                "confirmation_count": 1,
                "rule_version": "v1",
            },
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "overlay_state status unconfirmed is not replayable"}


def test_create_monitor_definition_artifact_persists_canonical_overlay_monitor_definition(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))

    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol=" spy "),
        store=store,
    )

    assert artifact.monitor_definition_id.startswith("monitor_definition_")
    assert artifact.benchmark_symbol == "SPY"
    assert artifact.schema_version == "monitor_definition_artifact_v1"
    assert artifact.observation_statuses == ["ok", "threshold_breach", "degraded", "unavailable"]
    assert artifact.source_lineage_requirements.model_dump(mode="json") == {
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
    assert artifact.thresholds.model_dump(mode="json") == {
        "minimum_confirmation_count": 2,
        "risk_on_min_risky_weight": 0.95,
        "risk_on_max_cash_weight": 0.05,
        "risk_reduced_max_risky_weight": 0.35,
        "risk_reduced_min_cash_weight": 0.65,
    }


def test_create_monitor_definition_artifact_is_immutable_for_same_canonical_request(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))

    first = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol=" spy "),
        store=store,
    )
    second = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    assert second.model_dump(mode="json") == first.model_dump(mode="json")
    assert [path.name for path in tmp_path.glob("monitor_definition_*.json")] == [
        f"{first.monitor_definition_id}.json"
    ]


def test_load_monitor_definition_artifact_hydrates_documented_legacy_omissions_only(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    artifact_path = tmp_path / f"{artifact.monitor_definition_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload.pop("observation_statuses")
    payload.pop("source_lineage_requirements")
    payload_without_ids = {
        key: value for key, value in payload.items() if key not in {"monitor_definition_id", "fingerprint"}
    }
    fingerprint = sha256(_canonical_json(payload_without_ids).encode("utf-8")).hexdigest()
    legacy_monitor_definition_id = f"monitor_definition_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["monitor_definition_id"] = legacy_monitor_definition_id
    artifact_path.unlink()
    (tmp_path / f"{legacy_monitor_definition_id}.json").write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    loaded = load_monitor_definition_artifact(legacy_monitor_definition_id, store=store)

    assert loaded.monitor_definition_id == legacy_monitor_definition_id
    assert loaded.observation_statuses == ["ok", "threshold_breach", "degraded", "unavailable"]
    assert loaded.source_lineage_requirements.model_dump(mode="json") == {
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


def test_load_monitor_definition_artifact_rejects_present_noncanonical_legacy_values(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    artifact_path = tmp_path / f"{artifact.monitor_definition_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["observation_statuses"] = ["ok", "threshold_breach", "degraded"]
    payload_without_ids = {
        key: value for key, value in payload.items() if key not in {"monitor_definition_id", "fingerprint"}
    }
    fingerprint = sha256(_canonical_json(payload_without_ids).encode("utf-8")).hexdigest()
    noncanonical_monitor_definition_id = f"monitor_definition_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["monitor_definition_id"] = noncanonical_monitor_definition_id
    artifact_path.unlink()
    (tmp_path / f"{noncanonical_monitor_definition_id}.json").write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    with pytest.raises(
        MonitorDefinitionIntegrityValidationError,
        match="monitor definition observation_statuses must remain canonical",
    ):
        load_monitor_definition_artifact(noncanonical_monitor_definition_id, store=store)


def test_list_monitor_definition_catalog_uses_persisted_artifact_metadata_only(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    response = list_monitor_definition_catalog(store=store)

    assert response.metadata.model_dump(mode="json") == {
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
    }
    assert response.items[0].model_dump(mode="json") == {
        "monitor_definition_id": artifact.monitor_definition_id,
        "monitor_id": "benchmark_trend_overlay_v1",
        "benchmark_symbol": "SPY",
        "schema_version": "monitor_definition_artifact_v1",
        "fingerprint": artifact.fingerprint,
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


def test_list_monitor_definition_artifacts_returns_narrow_identity_inventory(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    items = list_monitor_definition_artifacts(store=store)
    response = MonitorDefinitionArtifactListResponse(items=items)

    assert response.model_dump(mode="json") == {
        "items": [
            {
                "monitor_definition_id": artifact.monitor_definition_id,
                "monitor_id": "benchmark_trend_overlay_v1",
                "benchmark_symbol": "SPY",
                "schema_version": "monitor_definition_artifact_v1",
                "fingerprint": artifact.fingerprint,
            }
        ]
    }


def test_list_recent_monitor_definition_artifacts_uses_newest_persisted_artifact_first(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    first = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    second = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="QQQ"),
        store=store,
    )
    os.utime(tmp_path / f"{first.monitor_definition_id}.json", (1_700_000_000, 1_700_000_000))
    os.utime(tmp_path / f"{second.monitor_definition_id}.json", (1_700_000_100, 1_700_000_100))

    response = list_recent_monitor_definition_artifacts(limit=1, store=store)

    assert response.metadata.model_dump(mode="json") == {
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
    assert len(response.items) == 1
    assert response.items[0].monitor_definition_id == second.monitor_definition_id
    assert response.items[0].benchmark_symbol == "QQQ"
    assert response.items[0].metadata.model_dump(mode="json") == {
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


def test_list_monitor_definition_catalog_supports_presence_and_recency_filters_from_persisted_snapshot_metadata(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    stale = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    recent = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="QQQ"),
        store=store,
    )
    absent = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="DIA"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        stale.monitor_definition_id,
        evaluated_at="2026-01-01T09:30:00Z",
        outcome_status="ok",
        significance_status="informational",
        benchmark_symbol=stale.benchmark_symbol,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        recent.monitor_definition_id,
        evaluated_at="2999-01-01T09:30:00Z",
        outcome_status="threshold_breach",
        significance_status="action_required",
        benchmark_symbol=recent.benchmark_symbol,
    )
    _write_monitor_definition_observation(
        tmp_path,
        stale.monitor_definition_id,
        evaluated_at="2026-01-01T09:30:00Z",
        observation_status="ok",
        alert_classification="informational",
        benchmark_symbol=stale.benchmark_symbol,
    )
    _write_monitor_definition_observation(
        tmp_path,
        recent.monitor_definition_id,
        evaluated_at="2999-01-01T09:30:00Z",
        observation_status="threshold_breach",
        alert_classification="action_required",
        benchmark_symbol=recent.benchmark_symbol,
    )

    present = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(latest_evaluation_snapshot_status="present"),
    )
    recent_only = list_recent_monitor_definition_artifacts(
        store=store,
        limit=10,
        filters=MonitorDefinitionDiscoveryFilters(
            latest_evaluation_snapshot_status="present",
            latest_evaluation_snapshot_recency="recent",
        ),
    )
    absent_only = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(latest_evaluation_snapshot_status="absent"),
    )

    assert [item.monitor_definition_id for item in present.items] == [recent.monitor_definition_id, stale.monitor_definition_id]
    assert present.items[0].metadata.status.latest_evaluation_snapshot_status == "present"
    assert present.items[0].metadata.status.latest_evaluation_snapshot is not None
    assert present.items[0].metadata.status.latest_observation_status == "present"
    assert present.items[0].metadata.status.latest_observation is not None
    assert present.items[0].metadata.status.latest_observation.observation_status == "threshold_breach"
    assert present.items[0].metadata.status.latest_observation.alert_classification == "action_required"
    assert present.items[0].metadata.status.latest_evaluation_snapshot.recency_status == "recent"
    assert present.items[0].metadata.status.latest_evaluation_snapshot.outcome_status == "threshold_breach"
    assert present.items[0].metadata.status.latest_evaluation_snapshot.significance_status == "action_required"
    assert present.items[1].metadata.status.latest_evaluation_snapshot is not None
    assert present.items[1].metadata.status.latest_evaluation_snapshot.recency_status == "stale"
    assert [item.monitor_definition_id for item in recent_only.items] == [recent.monitor_definition_id]
    assert [item.monitor_definition_id for item in absent_only.items] == [absent.monitor_definition_id]


def test_list_monitor_definition_catalog_supports_additive_latest_observation_filters_from_canonical_metadata(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    action_required = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    informational = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="QQQ"),
        store=store,
    )
    absent = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="DIA"),
        store=store,
    )
    _write_monitor_definition_observation(
        tmp_path,
        action_required.monitor_definition_id,
        evaluated_at="2999-01-01T09:30:00Z",
        observation_status="threshold_breach",
        alert_classification="action_required",
        benchmark_symbol=action_required.benchmark_symbol,
    )
    _write_monitor_definition_observation(
        tmp_path,
        informational.monitor_definition_id,
        evaluated_at="2026-01-01T09:30:00Z",
        observation_status="ok",
        alert_classification="informational",
        benchmark_symbol=informational.benchmark_symbol,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        absent.monitor_definition_id,
        evaluated_at="2999-01-01T09:30:00Z",
        outcome_status="threshold_breach",
        significance_status="action_required",
        benchmark_symbol=absent.benchmark_symbol,
    )

    present_only = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(latest_observation_status="present"),
    )
    absent_only = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(latest_observation_status="absent"),
    )
    threshold_breach_only = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(
            latest_observation_observation_status="threshold_breach"
        ),
    )
    action_required_only = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(
            latest_observation_alert_classification="action_required"
        ),
    )
    recent_only = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(latest_observation_recency="recent"),
    )
    stale_only = list_recent_monitor_definition_artifacts(
        store=store,
        limit=10,
        filters=MonitorDefinitionDiscoveryFilters(latest_observation_recency="stale"),
    )
    combined = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(
            overlay_family="benchmark_trend",
            latest_observation_status="present",
            latest_observation_observation_status="threshold_breach",
            latest_observation_alert_classification="action_required",
            latest_observation_recency="recent",
        ),
    )

    assert [item.monitor_definition_id for item in present_only.items] == [
        informational.monitor_definition_id,
        action_required.monitor_definition_id,
    ]
    assert [item.monitor_definition_id for item in absent_only.items] == [absent.monitor_definition_id]
    assert [item.monitor_definition_id for item in threshold_breach_only.items] == [action_required.monitor_definition_id]
    assert [item.monitor_definition_id for item in action_required_only.items] == [action_required.monitor_definition_id]
    assert [item.monitor_definition_id for item in recent_only.items] == [action_required.monitor_definition_id]
    assert [item.monitor_definition_id for item in stale_only.items] == [informational.monitor_definition_id]
    assert [item.monitor_definition_id for item in combined.items] == [action_required.monitor_definition_id]


def test_list_monitor_definition_catalog_uses_absent_latest_observation_for_missing_canonical_observation_even_with_other_persisted_artifacts(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    (tmp_path / f"{artifact.monitor_definition_id}.observation.json").unlink()

    present = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(latest_observation_status="present"),
    )
    absent = list_monitor_definition_catalog(
        store=store,
        filters=MonitorDefinitionDiscoveryFilters(latest_observation_status="absent"),
    )

    assert present.items == []
    assert [item.monitor_definition_id for item in absent.items] == [artifact.monitor_definition_id]


@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
        (
            lambda payload: payload.pop("alert_classification"),
            re.escape("persisted monitor definition observation payload is missing required field(s): alert_classification"),
        ),
        (
            lambda payload: payload["portfolio_observation"]["source_lineage"].pop("importer"),
            "persisted monitor definition observation failed schema validation",
        ),
        (
            lambda payload: payload.__setitem__("monitor_definition_fingerprint", "0" * 64),
            "monitor definition observation observation_id does not match canonical persisted payload content|persisted monitor definition observation fingerprint does not match persisted monitor definition",
        ),
        (
            lambda payload: payload.__setitem__("benchmark_symbol", "QQQ"),
            "monitor definition observation observation_id does not match canonical persisted payload content|persisted monitor definition observation benchmark_symbol does not match persisted monitor definition",
        ),
    ],
)
def test_list_monitor_definition_catalog_fails_closed_on_malformed_partial_or_mismatched_present_observation_metadata(
    tmp_path,
    mutator,
    expected_error: str,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_monitor_definition_observation(tmp_path, artifact.monitor_definition_id, benchmark_symbol=artifact.benchmark_symbol)
    _rekey_monitor_definition_observation_payload(
        tmp_path / f"{artifact.monitor_definition_id}.observation.json",
        mutator,
    )

    with pytest.raises((MonitorDefinitionSchemaValidationError, MonitorDefinitionIntegrityValidationError), match=expected_error):
        list_monitor_definition_catalog(store=store)


def test_list_monitor_definition_catalog_fails_closed_on_malformed_latest_evaluation_snapshot_metadata(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        artifact.monitor_definition_id,
        outcome_status="bad_status",
    )

    with pytest.raises(
        ValueError,
        match="persisted latest evaluation snapshot outcome_status is invalid",
    ):
        list_monitor_definition_catalog(store=store)


def test_list_monitor_definition_catalog_fails_closed_on_snapshot_definition_mismatch(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        artifact.monitor_definition_id,
        benchmark_symbol="QQQ",
    )

    with pytest.raises(
        ValueError,
        match="persisted latest evaluation snapshot benchmark_symbol does not match persisted monitor definition",
    ):
        list_monitor_definition_catalog(store=store)


def test_list_monitor_definition_catalog_uses_persisted_evaluated_at_for_recency_not_file_mtime(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at="2026-01-01T09:30:00Z",
    )
    os.utime(tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json", (4_102_444_800, 4_102_444_800))

    response = list_monitor_definition_catalog(store=store)

    assert response.items[0].metadata.status.latest_evaluation_snapshot is not None
    assert response.items[0].metadata.status.latest_evaluation_snapshot.recency_status == "stale"


def test_list_monitor_definition_catalog_reads_latest_status_from_snapshot_sidecar_only(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_reduced", confirmation_count=2),
        ),
        artifact_store=store,
    )
    (tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json").unlink()

    catalog = list_monitor_definition_catalog(store=store)
    recent = list_recent_monitor_definition_artifacts(store=store)
    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)
    latest_observation = catalog.items[0].metadata.status.latest_observation

    assert latest_observation is not None

    assert catalog.items[0].metadata.status.model_dump(mode="json") == {
        "lifecycle": {
            "overlay_family": "benchmark_trend",
            "review_support_status": "review_supported",
            "lifecycle_status": "enabled",
        },
        "status_source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot",
        "latest_observation_status": "present",
        "latest_observation": {
            "observation_id": latest_observation.observation_id,
            "evaluated_at": latest_observation.evaluated_at.isoformat().replace("+00:00", "Z"),
            "observation_status": "ok",
            "cause_code": None,
            "alert_classification": "informational",
            "hysteresis_transition": "no_op",
            "recency_status": latest_observation.recency_status,
            "source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry",
        },
        "latest_evaluation_snapshot_status": "absent",
        "latest_evaluation_snapshot": None,
    }
    assert recent.items[0].metadata.status.latest_evaluation_snapshot_status == "absent"
    assert recent.items[0].metadata.status.latest_evaluation_snapshot is None
    assert recent.items[0].metadata.status.latest_observation_status == "present"
    assert recent.items[0].metadata.status.latest_observation is not None
    assert history.metadata.total_entries == 1
    assert len(history.items) == 1


def test_list_monitor_definition_latest_observation_alert_inbox_uses_latest_persisted_observations_only_and_newest_first(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    oldest = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    newest = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="QQQ"),
        store=store,
    )
    informational = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="DIA"),
        store=store,
    )
    _write_monitor_definition_observation(
        tmp_path,
        oldest.monitor_definition_id,
        evaluated_at="2026-04-20T09:30:00Z",
        observation_status="degraded",
        cause_code="benchmark_observation_unconfirmed",
        alert_classification="degraded",
        benchmark_symbol=oldest.benchmark_symbol,
    )
    _write_monitor_definition_observation(
        tmp_path,
        newest.monitor_definition_id,
        evaluated_at="2026-04-21T09:30:00Z",
        observation_status="threshold_breach",
        alert_classification="action_required",
        benchmark_symbol=newest.benchmark_symbol,
    )
    _write_monitor_definition_observation(
        tmp_path,
        informational.monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        observation_status="ok",
        alert_classification="informational",
        benchmark_symbol=informational.benchmark_symbol,
    )

    response = list_monitor_definition_latest_observation_alert_inbox(limit=10, store=store)

    assert response.metadata.model_dump(mode="json") == {
        "contract_version": "monitor_definition_latest_observation_alert_inbox_v1",
        "provenance": "authoritative_persisted_monitor_definition_observations_only",
        "row_provenance": "persisted_monitor_definition_observation_artifact",
        "source_precedence": "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry",
        "ordering": "newest_first_evaluated_at",
        "returned_limit": 10,
    }
    assert [item.monitor_definition_id for item in response.items] == [newest.monitor_definition_id, oldest.monitor_definition_id]
    assert response.items[0].open_handoff.model_dump(mode="json") == {
        "handoff_kind": "monitor_definition_observation_open_handoff_v1",
        "monitor_definition_id": newest.monitor_definition_id,
        "observation_id": response.items[0].observation_id,
        "monitor_id": "benchmark_trend_overlay_v1",
        "benchmark_symbol": newest.benchmark_symbol,
    }
    assert response.items[0].alert_classification == "action_required"
    assert response.items[1].cause_code == "benchmark_observation_unconfirmed"


def test_list_monitor_definition_latest_observation_alert_inbox_fails_closed_on_mismatched_observation_lineage(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_monitor_definition_observation(tmp_path, artifact.monitor_definition_id, benchmark_symbol=artifact.benchmark_symbol)
    _rekey_monitor_definition_observation_payload(
        tmp_path / f"{artifact.monitor_definition_id}.observation.json",
        lambda payload: payload.__setitem__("monitor_definition_fingerprint", "0" * 64),
    )

    with pytest.raises(
        MonitorDefinitionIntegrityValidationError,
        match="persisted monitor definition observation fingerprint does not match persisted monitor definition",
    ):
        list_monitor_definition_latest_observation_alert_inbox(store=store)


def test_list_monitor_definition_alert_history_queue_returns_only_alert_eligible_rows_with_latest_first(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    action_required = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    degraded = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="QQQ"),
        store=store,
    )
    informational = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="DIA"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        action_required.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    evaluate_monitor_definition_observation(
        degraded.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1).model_copy(
                update={"benchmark_symbol": degraded.benchmark_symbol}
            ),
        ),
        artifact_store=store,
    )
    evaluate_monitor_definition_observation(
        informational.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_reduced", confirmation_count=2).model_copy(
                update={"benchmark_symbol": informational.benchmark_symbol}
            ),
        ),
        artifact_store=store,
    )

    response = list_monitor_definition_alert_history_queue(limit=10, store=store)

    assert response.metadata.model_dump(mode="json") == {
        "contract_version": "monitor_definition_alert_history_queue_v1",
        "provenance": "persisted_monitor_definitions_with_canonical_latest_snapshot_and_evaluation_history",
        "row_provenance": "persisted_monitor_definition_evaluation_history_entry_with_latest_snapshot_precedence",
        "source_precedence": "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries",
        "ordering": "newest_first_evaluated_at_then_latest_snapshot_precedence_then_monitor_definition_id_then_history_entry_id",
        "returned_limit": 10,
        "total_queue_rows": 2,
    }
    assert [item.monitor_definition_id for item in response.items] == [
        degraded.monitor_definition_id,
        action_required.monitor_definition_id,
    ]
    assert response.items[0].outcome_status == "degraded"
    assert response.items[0].cause_code == "benchmark_observation_unconfirmed"
    assert response.items[0].significance_status == "degraded"
    assert response.items[0].hysteresis_transition == "open"
    assert response.items[0].latest_for_monitor_definition is True
    assert response.items[0].review_handoff.history_entry_id == response.items[0].history_entry_id
    assert response.items[1].outcome_status == "threshold_breach"
    assert response.items[1].cause_code is None
    assert response.items[1].significance_status == "action_required"
    assert response.items[1].hysteresis_transition == "open"


def test_list_monitor_definition_alert_history_queue_fails_closed_when_persisted_evaluation_artifacts_conflict(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    _mutate_persisted_json(
        str(tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json"),
        lambda payload: payload.__setitem__("evaluated_at", "2026-04-20T09:30:00Z"),
    )
    _rekey_monitor_definition_observation_payload(
        tmp_path / f"{artifact.monitor_definition_id}.observation.json",
        lambda payload: payload.__setitem__("evaluated_at", "2026-04-20T09:30:00Z"),
    )

    with pytest.raises(
        MonitorDefinitionPersistenceError,
        match="observation evaluated_at must match persisted evaluation artifacts",
    ):
        list_monitor_definition_alert_history_queue(store=store)


def test_list_monitor_definition_active_alert_episode_inbox_returns_only_open_persisted_episode_rows_with_stable_ordering_and_windowing(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    active_oldest = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    active_newest = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="QQQ"),
        store=store,
    )
    recovered = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="DIA"),
        store=store,
    )

    evaluate_monitor_definition_observation(
        active_oldest.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    evaluate_monitor_definition_observation(
        active_newest.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1).model_copy(
                update={"benchmark_symbol": active_newest.benchmark_symbol}
            ),
        ),
        artifact_store=store,
    )
    evaluate_monitor_definition_observation(
        recovered.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2).model_copy(
                update={"benchmark_symbol": recovered.benchmark_symbol}
            ),
        ),
        artifact_store=store,
    )
    evaluate_monitor_definition_observation(
        recovered.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_reduced", confirmation_count=2).model_copy(
                update={"benchmark_symbol": recovered.benchmark_symbol}
            ),
        ),
        artifact_store=store,
    )

    response = list_monitor_definition_active_alert_episode_inbox(limit=1, store=store)

    assert response.metadata.model_dump(mode="json") == {
        "contract_version": "monitor_definition_active_alert_episode_inbox_v1",
        "provenance": "authoritative_persisted_monitor_definition_alert_episode_records_only",
        "row_provenance": "persisted_monitor_definition_alert_episode_record",
        "source_precedence": "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation",
        "ordering": "newest_first_latest_event_at_then_monitor_definition_id_then_episode_id",
        "windowing": "before_episode_id_exclusive",
        "returned_limit": 1,
        "requested_before_episode_id": None,
        "next_before_episode_id": response.items[0].alert_episode.episode_id,
        "total_active_episodes": 2,
    }
    assert [row.alert_episode.monitor_definition_id for row in response.items] == [active_newest.monitor_definition_id]
    assert response.items[0].review_scope == "current_portfolio_truth_only"
    assert response.items[0].evaluation_mode == "review_only_observation_evaluation"
    assert response.items[0].alert_episode.lifecycle_status == "open"
    assert response.items[0].alert_episode.hysteresis_transition == "open"
    assert response.items[0].alert_episode.source_precedence == "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    assert response.items[0].alert_episode.timeline_handoff.selected_event_kind == "latest_observation_event"
    assert response.items[0].alert_episode.latest_contributing_observation.alert_classification == "degraded"

    next_response = list_monitor_definition_active_alert_episode_inbox(
        limit=2,
        before_episode_id=response.items[0].alert_episode.episode_id,
        store=store,
    )
    assert next_response.metadata.requested_before_episode_id == response.items[0].alert_episode.episode_id
    assert next_response.metadata.next_before_episode_id is None
    assert next_response.metadata.total_active_episodes == 1
    assert [row.alert_episode.monitor_definition_id for row in next_response.items] == [active_oldest.monitor_definition_id]
    assert all(row.alert_episode.lifecycle_status == "open" for row in next_response.items)


def test_list_monitor_definition_active_alert_episode_inbox_fails_closed_on_persisted_episode_lineage_contradiction(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    episode_path = next((tmp_path / f"{artifact.monitor_definition_id}.episodes").glob("*.json"))
    _mutate_persisted_json(
        str(episode_path),
        lambda payload: payload.__setitem__("terminal_history_entry_id", "monitor_definition_history_other"),
    )

    with pytest.raises(
        MonitorDefinitionIntegrityValidationError,
        match="persisted alert episode history does not match canonical persisted evaluation lineage|monitor definition alert episode record episode_id does not match canonical persisted payload content",
    ):
        list_monitor_definition_active_alert_episode_inbox(store=store)


def test_list_monitor_definition_active_alert_episode_inbox_does_not_reconstruct_from_latest_observation_only_state(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_monitor_definition_observation(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at="2026-04-21T09:30:00Z",
        observation_status="threshold_breach",
        alert_classification="action_required",
        benchmark_symbol=artifact.benchmark_symbol,
    )

    response = list_monitor_definition_active_alert_episode_inbox(store=store)

    assert response.items == []
    assert response.metadata.total_active_episodes == 0
    assert response.metadata.next_before_episode_id is None


def test_get_monitor_definition_alert_review_timeline_returns_observation_and_history_rows_in_authoritative_order(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    first = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    second = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1),
        ),
        artifact_store=store,
    )

    timeline = get_monitor_definition_alert_review_timeline(artifact.monitor_definition_id, store=store)
    latest_observation = load_monitor_definition_observation(artifact.monitor_definition_id, store=store)

    assert timeline.metadata.model_dump(mode="json", exclude={"latest_alert_episode"}) == {
        "contract_version": "monitor_definition_alert_review_timeline_v1",
        "provenance": "canonical_latest_observation_artifact_and_append_only_evaluation_history_entries",
        "ordering": "newest_first_evaluated_at_then_observation_event_then_history_entry_id",
        "monitor_definition_id": artifact.monitor_definition_id,
        "monitor_definition_fingerprint": artifact.fingerprint,
        "monitor_definition_schema_version": "monitor_definition_artifact_v1",
        "observation_row_provenance": "persisted_monitor_definition_observation_artifact",
        "history_row_provenance": "persisted_monitor_definition_evaluation_history_entry",
        "source_precedence": "persisted_observation_artifact_then_persisted_evaluation_history_entries_then_persisted_latest_alert_episode_projection",
        "total_rows": 3,
        "observation_rows": 1,
        "history_rows": 2,
    }
    assert timeline.metadata.latest_alert_episode is not None
    assert timeline.metadata.latest_alert_episode.episode_status == "active"
    assert timeline.metadata.latest_alert_episode.hysteresis_transition == "remain_open"
    assert timeline.metadata.latest_alert_episode.source_precedence == "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    assert (
        timeline.metadata.latest_alert_episode.latest_contributing_observation.observation_id
        == latest_observation.observation_id
    )
    assert [row.event_kind for row in timeline.items] == [
        "latest_observation_event",
        "evaluation_history_event",
        "evaluation_history_event",
    ]
    assert timeline.items[0].event_semantics == "observation_rooted"
    assert timeline.items[1].event_semantics == "history_entry_rooted"
    assert timeline.items[0].observation_id == latest_observation.observation_id
    assert timeline.items[0].open_handoff.observation_id == timeline.items[0].observation_id
    assert timeline.items[0].hysteresis_transition == "remain_open"
    assert timeline.items[0].thresholds.model_dump(mode="json") == second.thresholds.model_dump(mode="json")
    assert timeline.items[0].benchmark_observation.model_dump(mode="json") == second.benchmark_observation.model_dump(mode="json")
    assert timeline.items[0].portfolio_observation.model_dump(mode="json") == second.portfolio_observation.model_dump(mode="json")
    assert timeline.items[0].active_observation.model_dump(mode="json") == second.active_observation.model_dump(mode="json")
    assert timeline.items[1].review_handoff.history_entry_id == timeline.items[1].history_entry_id
    assert timeline.items[1].latest_for_monitor_definition is True
    assert timeline.items[1].hysteresis_transition == "remain_open"
    assert timeline.items[1].thresholds.model_dump(mode="json") == second.thresholds.model_dump(mode="json")
    assert timeline.items[2].hysteresis_transition == "open"
    assert timeline.items[2].thresholds.model_dump(mode="json") == first.thresholds.model_dump(mode="json")
    assert timeline.items[0].benchmark_observation.benchmark_symbol == "SPY"
    assert timeline.items[0].portfolio_observation.source_lineage.truth_basis == "imported_portfolio_snapshot"
    assert timeline.items[0].active_observation.required_overlay_status == "unconfirmed"


def test_get_monitor_definition_alert_review_timeline_does_not_emit_recovered_episode_for_informational_no_op_state(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_monitor_definition_observation(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        observation_status="ok",
        cause_code=None,
        alert_classification="informational",
        hysteresis_transition="no_op",
        benchmark_symbol=artifact.benchmark_symbol,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        outcome_status="ok",
        cause_code=None,
        significance_status="informational",
        hysteresis_transition="no_op",
        benchmark_symbol=artifact.benchmark_symbol,
    )
    _write_monitor_definition_history_entry(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        observation_status="ok",
        cause_code=None,
        significance_status="informational",
        hysteresis_transition="no_op",
        benchmark_symbol=artifact.benchmark_symbol,
        reason="steady informational state",
    )

    timeline = get_monitor_definition_alert_review_timeline(artifact.monitor_definition_id, store=store)

    assert timeline.metadata.latest_alert_episode is None


def test_list_monitor_definition_recovered_alert_review_queue_excludes_informational_no_op_states(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_monitor_definition_observation(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        observation_status="ok",
        cause_code=None,
        alert_classification="informational",
        hysteresis_transition="no_op",
        benchmark_symbol=artifact.benchmark_symbol,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        outcome_status="ok",
        cause_code=None,
        significance_status="informational",
        hysteresis_transition="no_op",
        benchmark_symbol=artifact.benchmark_symbol,
    )
    _write_monitor_definition_history_entry(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at="2026-04-22T09:30:00Z",
        observation_status="ok",
        cause_code=None,
        significance_status="informational",
        hysteresis_transition="no_op",
        benchmark_symbol=artifact.benchmark_symbol,
        reason="steady informational state",
    )

    response = list_monitor_definition_recovered_alert_review_queue(limit=10, store=store)

    assert response.items == []
    assert response.metadata.total_queue_rows == 0


def test_get_monitor_definition_alert_review_timeline_fails_closed_on_lineage_mismatch_between_observation_and_history(
    tmp_path,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    _rekey_monitor_definition_observation_payload(
        tmp_path / f"{artifact.monitor_definition_id}.observation.json",
        lambda payload: payload.__setitem__("evaluated_at", "2026-04-20T09:30:00Z"),
    )

    with pytest.raises(
        MonitorDefinitionPersistenceError,
        match="observation evaluated_at must match persisted evaluation artifacts",
    ):
        get_monitor_definition_alert_review_timeline(artifact.monitor_definition_id, store=store)


def test_get_monitor_definition_alert_review_timeline_fails_closed_on_history_fingerprint_mismatch(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)
    history_entry_id = history.items[0].history_entry_id
    _mutate_persisted_json(
        str(tmp_path / f"{artifact.monitor_definition_id}.history" / f"{history_entry_id}.json"),
        lambda payload: payload.__setitem__("monitor_definition_fingerprint", "0" * 64),
    )

    with pytest.raises(
        MonitorDefinitionIntegrityValidationError,
        match="monitor definition evaluation history entry history_entry_id does not match canonical persisted payload content|persisted monitor definition evaluation history entry fingerprint does not match persisted monitor definition",
    ):
        get_monitor_definition_alert_review_timeline(artifact.monitor_definition_id, store=store)


def test_list_monitor_definition_catalog_reads_latest_observation_from_canonical_observation_only(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_reduced", confirmation_count=2),
        ),
        artifact_store=store,
    )
    (tmp_path / f"{artifact.monitor_definition_id}.observation.json").unlink()

    catalog = list_monitor_definition_catalog(store=store)
    recent = list_recent_monitor_definition_artifacts(store=store)
    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)

    assert catalog.items[0].metadata.status.latest_observation_status == "absent"
    assert catalog.items[0].metadata.status.latest_observation is None
    assert recent.items[0].metadata.status.latest_observation_status == "absent"
    assert recent.items[0].metadata.status.latest_observation is None
    assert history.metadata.total_entries == 1
    assert len(history.items) == 1


def test_load_monitor_definition_latest_evaluation_snapshot_rejects_missing_required_top_level_field(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(tmp_path, artifact.monitor_definition_id)
    _mutate_persisted_json(
        str(tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json"),
        lambda payload: payload.pop("portfolio_truth_basis"),
    )

    with pytest.raises(
        MonitorDefinitionSchemaValidationError,
        match=r"persisted latest evaluation snapshot payload is missing required field\(s\): portfolio_truth_basis",
    ):
        load_monitor_definition_latest_evaluation_snapshot(artifact.monitor_definition_id, store=store)


def test_load_monitor_definition_latest_evaluation_snapshot_rejects_ambiguous_present_nested_state(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(tmp_path, artifact.monitor_definition_id)
    _mutate_persisted_json(
        str(tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json"),
        lambda payload: payload["portfolio_truth_basis"].pop("source_path"),
    )

    with pytest.raises(
        MonitorDefinitionIntegrityValidationError,
        match="persisted latest evaluation snapshot portfolio_truth_basis must be fully specified when present",
    ):
        load_monitor_definition_latest_evaluation_snapshot(artifact.monitor_definition_id, store=store)


def test_load_monitor_definition_latest_evaluation_snapshot_rejects_monitor_definition_identity_mismatch(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(tmp_path, artifact.monitor_definition_id)
    _mutate_persisted_json(
        str(tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json"),
        lambda payload: payload.__setitem__("monitor_definition_id", "monitor_definition_other"),
    )

    with pytest.raises(
        MonitorDefinitionIntegrityValidationError,
        match="persisted latest evaluation snapshot monitor_definition_id does not match requested definition",
    ):
        load_monitor_definition_latest_evaluation_snapshot(artifact.monitor_definition_id, store=store)


def test_evaluate_monitor_definition_observation_returns_threshold_breach_for_risk_on_overlay(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    snapshot = _build_imported_snapshot_for_optimizer()

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=snapshot,
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )

    assert response.observation_status == "threshold_breach"
    assert response.reason == "current portfolio truth breaches canonical overlay thresholds"
    assert response.portfolio_observation.model_dump(mode="json") == {
        "total_portfolio_value": 600.0,
        "risky_value": 100.0,
        "cash_value": 500.0,
        "risky_weight": 0.16666667,
        "cash_weight": 0.83333333,
        "position_count": 2,
        "source_lineage": {
            "truth_basis": "imported_portfolio_snapshot",
            "importer": "interactive_brokers",
            "imported_at": "2024-04-15T09:30:00",
            "statement_period": "2024-04",
            "source_paths": ["IB2024.pdf"],
        },
    }
    assert response.active_observation.model_dump(mode="json") == {
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
        "triggered_thresholds": [
            {
                "threshold_id": "risk_on_min_risky_weight",
                "operator": ">=",
                "threshold_value": 0.95,
                "actual_value": 0.16666667,
                "breach_amount": 0.78333333,
            },
            {
                "threshold_id": "risk_on_max_cash_weight",
                "operator": "<=",
                "threshold_value": 0.05,
                "actual_value": 0.83333333,
                "breach_amount": 0.78333333,
            },
        ],
    }


def test_evaluate_monitor_definition_observation_persists_authoritative_latest_snapshot(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    persisted = load_monitor_definition_latest_evaluation_snapshot(artifact.monitor_definition_id, store=store)

    assert response.observation_status == "threshold_breach"
    assert isinstance(persisted, MonitorDefinitionLatestEvaluationSnapshotArtifact)
    assert persisted.evaluated_at.tzinfo is not None
    assert persisted.model_dump(mode="json") == {
        "schema_version": "monitor_definition_latest_evaluation_snapshot_v1",
        "monitor_definition_id": artifact.monitor_definition_id,
        "monitor_id": "benchmark_trend_overlay_v1",
        "benchmark_symbol": "SPY",
        "evaluated_at": persisted.evaluated_at.isoformat().replace("+00:00", "Z"),
        "outcome_status": "threshold_breach",
        "cause_code": None,
        "significance_status": "action_required",
        "hysteresis_transition": "open",
        "source_precedence": "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact",
        "benchmark_observation_lineage": {
            "source_kind": "benchmark_overlay_signal",
            "source_id": "overlay-signal-2024-12-31",
            "observed_at": "2025-01-02T09:30:00",
        },
        "portfolio_truth_basis": {
            "truth_basis": "imported_portfolio_snapshot",
            "importer": "interactive_brokers",
            "imported_at": "2024-04-15T09:30:00",
            "source_path": "IB2024.pdf",
            "statement_period": "2024-04",
        },
    }


def test_evaluate_monitor_definition_observation_persists_authoritative_observation(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    persisted = load_monitor_definition_observation(artifact.monitor_definition_id, store=store)

    assert isinstance(persisted, MonitorDefinitionObservationArtifact)
    assert persisted.observation_id.startswith("monitor_definition_observation_")
    assert persisted.monitor_definition_id == artifact.monitor_definition_id
    assert persisted.monitor_definition_fingerprint == artifact.fingerprint
    assert persisted.monitor_definition_schema_version == "monitor_definition_artifact_v1"
    assert persisted.observation_status == response.observation_status
    assert persisted.cause_code is None
    assert persisted.alert_classification == "action_required"
    assert persisted.benchmark_observation.overlay_id == artifact.monitor_id
    assert persisted.benchmark_observation.benchmark_symbol == artifact.benchmark_symbol


def test_evaluate_monitor_definition_observation_persists_latest_snapshot_source_path_from_canonical_root(tmp_path) -> None:
    from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement

    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2024, 4, 15, 9, 30),
            source_path="canonical-root.pdf",
            detected_format="statement_pdf",
            account_id="U1234567",
            base_currency="USD",
            statement_period="2024-04",
            page_count=4,
        ),
        statements=[
            ImportedStatement(
                importer="interactive_brokers",
                imported_at=datetime(2024, 4, 15, 9, 30),
                source_path="lineage-first.pdf",
                detected_format="statement_pdf",
                account_id="U1234567",
                base_currency="USD",
                statement_period="2024-04",
                page_count=4,
            ),
            ImportedStatement(
                importer="interactive_brokers",
                imported_at=datetime(2024, 4, 15, 9, 30),
                source_path="canonical-root.pdf",
                detected_format="statement_pdf",
                account_id="U1234567",
                base_currency="USD",
                statement_period="2024-04",
                page_count=4,
            ),
        ],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=500.0)],
        positions=[ImportedPosition(as_of_date=date(2024, 1, 1), symbol="AAA", quantity=10.0, cost_basis=60.0, close_price=6.0, market_value=60.0, unrealized_pnl=0.0, currency="USD")],
        ledger_entries=[],
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=snapshot,
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    persisted = load_monitor_definition_latest_evaluation_snapshot(artifact.monitor_definition_id, store=store)

    assert response.portfolio_observation.source_lineage.source_paths[0] == "lineage-first.pdf"
    assert persisted.portfolio_truth_basis.source_path == "canonical-root.pdf"


@pytest.mark.parametrize("evaluated_at", ["2026-04-20T09:30:00", "not-a-timestamp"])
def test_load_monitor_definition_latest_evaluation_snapshot_rejects_invalid_present_evaluated_at(
    tmp_path,
    evaluated_at: str,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        artifact.monitor_definition_id,
        evaluated_at=evaluated_at,
    )

    with pytest.raises(
        MonitorDefinitionDiscoveryMetadataValidationError,
        match="persisted latest evaluation snapshot evaluated_at is invalid",
    ):
        load_monitor_definition_latest_evaluation_snapshot(artifact.monitor_definition_id, store=store)


def test_evaluate_monitor_definition_observation_overwrites_latest_snapshot_without_history_fanout(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    first_payload = json.loads(
        (tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json").read_text(encoding="utf-8")
    )

    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1),
        ),
        artifact_store=store,
    )
    second_payload = json.loads(
        (tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json").read_text(encoding="utf-8")
    )
    observation_payload = json.loads(
        (tmp_path / f"{artifact.monitor_definition_id}.observation.json").read_text(encoding="utf-8")
    )

    assert len(list(tmp_path.glob(f"{artifact.monitor_definition_id}.latest_evaluation.json"))) == 1
    assert len(list(tmp_path.glob(f"{artifact.monitor_definition_id}.observation.json"))) == 1
    assert first_payload["outcome_status"] == "threshold_breach"
    assert second_payload["outcome_status"] == "degraded"
    assert first_payload["cause_code"] is None
    assert second_payload["cause_code"] == "benchmark_observation_unconfirmed"
    assert second_payload["significance_status"] == "degraded"
    assert observation_payload["observation_status"] == "degraded"
    assert observation_payload["cause_code"] == "benchmark_observation_unconfirmed"
    assert observation_payload["alert_classification"] == "degraded"


def test_evaluate_monitor_definition_observation_appends_canonical_history_entries(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1),
        ),
        artifact_store=store,
    )

    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)

    assert history.metadata.monitor_definition_id == artifact.monitor_definition_id
    assert history.metadata.monitor_definition_fingerprint == artifact.fingerprint
    assert history.metadata.total_entries == 2
    assert history.metadata.inspection_order == "newest_first_evaluated_at"
    assert [item.observation_status for item in history.items] == ["degraded", "threshold_breach"]
    assert [item.cause_code for item in history.items] == ["benchmark_observation_unconfirmed", None]
    assert all(item.monitor_definition_fingerprint == artifact.fingerprint for item in history.items)
    assert all(item.monitor_definition_schema_version == "monitor_definition_artifact_v1" for item in history.items)
    assert all(item.metadata.history_truth == "authoritative_persisted_monitor_definition_evaluation_history" for item in history.items)
    assert all(item.metadata.row_provenance == "persisted_monitor_definition_evaluation_history_entry" for item in history.items)
    assert len(list((tmp_path / f"{artifact.monitor_definition_id}.history").glob("*.json"))) == 2


def test_list_monitor_definition_evaluation_history_reads_append_only_entries_only(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_latest_monitor_evaluation_snapshot(tmp_path, artifact.monitor_definition_id)

    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)

    assert history.metadata.monitor_definition_id == artifact.monitor_definition_id
    assert history.metadata.total_entries == 0
    assert history.items == []


def test_load_monitor_definition_evaluation_history_entry_fails_closed_on_definition_fingerprint_mismatch(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)
    history_entry_id = history.items[0].history_entry_id
    _mutate_persisted_json(
        str(tmp_path / f"{artifact.monitor_definition_id}.history" / f"{history_entry_id}.json"),
        lambda payload: payload.__setitem__("monitor_definition_fingerprint", "0" * 64),
    )

    with pytest.raises(
        MonitorDefinitionIntegrityValidationError,
        match="monitor definition evaluation history entry history_entry_id does not match canonical persisted payload content|persisted monitor definition evaluation history entry fingerprint does not match persisted monitor definition",
    ):
        load_monitor_definition_evaluation_history_entry(
            artifact.monitor_definition_id,
            history_entry_id,
            store=store,
        )


def test_load_monitor_definition_observation_fails_closed_on_definition_fingerprint_mismatch(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    _mutate_persisted_json(
        str(tmp_path / f"{artifact.monitor_definition_id}.observation.json"),
        lambda payload: payload.__setitem__("monitor_definition_fingerprint", "0" * 64),
    )

    with pytest.raises(
        MonitorDefinitionIntegrityValidationError,
        match="monitor definition observation observation_id does not match canonical persisted payload content|persisted monitor definition observation fingerprint does not match persisted monitor definition",
    ):
        load_monitor_definition_observation(artifact.monitor_definition_id, store=store)


@pytest.mark.parametrize(
    ("mutator", "expected_error"),
    [
            (
                lambda payload: payload.pop("alert_classification"),
                re.escape("persisted monitor definition observation payload is missing required field(s): alert_classification"),
            ),
        (
            lambda payload: payload["benchmark_observation"].pop("source_lineage"),
            "persisted monitor definition observation failed schema validation",
        ),
        (
            lambda payload: payload.__setitem__("monitor_id", "unsupported_monitor"),
            "persisted monitor definition observation failed schema validation",
        ),
    ],
)
def test_load_monitor_definition_observation_fails_closed_on_malformed_or_unsupported_payload(
    tmp_path,
    mutator,
    expected_error: str,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_monitor_definition_observation(tmp_path, artifact.monitor_definition_id, benchmark_symbol=artifact.benchmark_symbol)
    _rekey_monitor_definition_observation_payload(
        tmp_path / f"{artifact.monitor_definition_id}.observation.json",
        mutator,
    )

    with pytest.raises((MonitorDefinitionSchemaValidationError, MonitorDefinitionIntegrityValidationError), match=expected_error):
        load_monitor_definition_observation(artifact.monitor_definition_id, store=store)


def test_list_monitor_definition_catalog_prefers_canonical_observation_without_reconstructing_from_history(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    (tmp_path / f"{artifact.monitor_definition_id}.observation.json").unlink()

    catalog = list_monitor_definition_catalog(store=store)
    recent = list_recent_monitor_definition_artifacts(store=store)
    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)

    assert catalog.items[0].metadata.status.latest_observation_status == "absent"
    assert catalog.items[0].metadata.status.latest_observation is None
    assert recent.items[0].metadata.status.latest_observation_status == "absent"
    assert recent.items[0].metadata.status.latest_observation is None
    assert history.metadata.total_entries == 1


def test_inspect_monitor_definition_evaluation_history_entry_returns_canonical_entry(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_reduced", confirmation_count=2),
        ),
        artifact_store=store,
    )
    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)

    inspected = inspect_monitor_definition_evaluation_history_entry(
        artifact.monitor_definition_id,
        history.items[0].history_entry_id,
        store=store,
    )

    assert inspected.item.history_entry_id == history.items[0].history_entry_id
    assert inspected.item.observation_status == response.observation_status
    assert inspected.item.significance_status == "informational"
    assert inspected.metadata.retrieved_history_entry_id == history.items[0].history_entry_id
    assert inspected.metadata.total_entries == 1


def test_evaluate_monitor_definition_observation_returns_ok_for_risk_reduced_overlay(tmp_path) -> None:
    from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement

    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2024, 4, 15, 9, 30),
            source_path="IB2024.pdf",
            detected_format="statement_pdf",
            account_id="U1234567",
            base_currency="USD",
            statement_period="2024-04",
            page_count=4,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=650.0)],
        positions=[ImportedPosition(as_of_date=date(2024, 1, 1), symbol="AAA", quantity=35.0, cost_basis=35.0, close_price=1.0, market_value=35.0, unrealized_pnl=0.0, currency="USD")],
        ledger_entries=[],
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=snapshot,
            benchmark_observation=_monitor_benchmark_observation(status="risk_reduced", confirmation_count=2),
        ),
        artifact_store=store,
    )

    assert response.observation_status == "ok"
    assert response.reason is None
    assert response.active_observation.triggered_thresholds == []
    assert load_monitor_definition_latest_evaluation_snapshot(
        artifact.monitor_definition_id,
        store=store,
    ).evaluated_at.tzinfo is not None


def test_evaluate_monitor_definition_observation_returns_degraded_for_unconfirmed_overlay(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1),
        ),
        artifact_store=store,
    )

    assert response.observation_status == "degraded"
    assert response.cause_code == "benchmark_observation_unconfirmed"
    assert response.reason == "benchmark observation is unconfirmed"
    assert response.active_observation.threshold_evaluation_performed is False


def test_evaluate_monitor_definition_observation_returns_unavailable_cause_code_for_unavailable_benchmark(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unavailable", confirmation_count=0),
        ),
        artifact_store=store,
    )

    assert response.observation_status == "unavailable"
    assert response.cause_code == "benchmark_observation_unavailable"
    assert load_monitor_definition_latest_evaluation_snapshot(
        artifact.monitor_definition_id,
        store=store,
    ).cause_code == "benchmark_observation_unavailable"
    assert load_monitor_definition_observation(artifact.monitor_definition_id, store=store).cause_code == (
        "benchmark_observation_unavailable"
    )
    assert list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store).items[0].cause_code == (
        "benchmark_observation_unavailable"
    )


def test_evaluate_monitor_definition_observation_returns_unavailable_cause_code_for_non_positive_portfolio_truth(tmp_path) -> None:
    from app.schemas.imports import ImportedPortfolioSnapshot, ImportedStatement

    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    snapshot = ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="interactive_brokers",
            imported_at=datetime(2024, 4, 15, 9, 30),
            source_path="IB2024.pdf",
            detected_format="statement_pdf",
            account_id="U1234567",
            base_currency="USD",
            statement_period="2024-04",
            page_count=4,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[],
        positions=[],
        ledger_entries=[],
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=snapshot,
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )

    assert response.observation_status == "unavailable"
    assert response.cause_code == "portfolio_truth_non_positive_total_value"
    assert load_monitor_definition_latest_evaluation_snapshot(
        artifact.monitor_definition_id,
        store=store,
    ).cause_code == "portfolio_truth_non_positive_total_value"


def test_evaluate_monitor_definition_observation_rejects_contradictory_overlay_confirmation_state(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    with pytest.raises(ValueError, match="benchmark observation status unconfirmed contradicts confirmation_count"):
        evaluate_monitor_definition_observation(
            artifact.monitor_definition_id,
            EvaluateMonitorDefinitionObservationRequest(
                current_portfolio=_build_imported_snapshot_for_optimizer(),
                benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=2),
            ),
            artifact_store=store,
        )


def test_evaluate_monitor_definition_observation_request_rejects_non_canonical_benchmark_symbol() -> None:
    payload = {
        "current_portfolio": _build_imported_snapshot_for_optimizer().model_dump(mode="json"),
        "benchmark_observation": _monitor_benchmark_observation().model_dump(mode="json"),
    }
    payload["benchmark_observation"]["benchmark_symbol"] = " spy "

    with pytest.raises(
        ValidationError,
        match="benchmark_symbol must be canonical uppercase without surrounding whitespace",
    ):
        EvaluateMonitorDefinitionObservationRequest.model_validate(payload)


def test_evaluate_monitor_definition_observation_rolls_back_snapshot_when_history_persist_fails(
    tmp_path,
    monkeypatch,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_on", confirmation_count=2),
        ),
        artifact_store=store,
    )
    initial_snapshot = json.loads(
        (tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json").read_text(encoding="utf-8")
    )
    initial_history_files = list((tmp_path / f"{artifact.monitor_definition_id}.history").glob("*.json"))
    original_write_once = MonitorDefinitionArtifactStore._write_once

    def fail_history_write(self, path, payload):
        if path.parent.name == f"{artifact.monitor_definition_id}.history":
            raise MonitorDefinitionPersistenceError("injected history append failure")
        return original_write_once(self, path, payload)

    monkeypatch.setattr(MonitorDefinitionArtifactStore, "_write_once", fail_history_write)

    with pytest.raises(MonitorDefinitionPersistenceError, match="injected history append failure"):
        evaluate_monitor_definition_observation(
            artifact.monitor_definition_id,
            EvaluateMonitorDefinitionObservationRequest(
                current_portfolio=_build_imported_snapshot_for_optimizer(),
                benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1),
            ),
            artifact_store=store,
        )

    rolled_back_snapshot = json.loads(
        (tmp_path / f"{artifact.monitor_definition_id}.latest_evaluation.json").read_text(encoding="utf-8")
    )
    rolled_back_history_files = list((tmp_path / f"{artifact.monitor_definition_id}.history").glob("*.json"))

    assert rolled_back_snapshot == initial_snapshot
    assert [path.name for path in rolled_back_history_files] == [path.name for path in initial_history_files]
    assert len(rolled_back_history_files) == 1


def test_monitor_definition_evaluation_response_preserves_shared_contract_entities(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1),
        ),
        artifact_store=store,
    )

    typed_response = MonitorDefinitionObservationEvaluationResponse.model_validate(
        response.model_dump(mode="json")
    )

    assert typed_response.monitor_definition_id == artifact.monitor_definition_id
    assert typed_response.monitor_id == artifact.monitor_id
    assert typed_response.evaluation_mode == artifact.evaluation_mode
    assert typed_response.thresholds.model_dump(mode="json") == artifact.thresholds.model_dump(mode="json")
    assert typed_response.observation_status == "degraded"
    assert typed_response.cause_code == "benchmark_observation_unconfirmed"


def test_monitor_definition_evaluation_history_entry_preserves_separate_observation_blocks(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )

    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="risk_reduced", confirmation_count=2),
        ),
        artifact_store=store,
    )
    history = list_monitor_definition_evaluation_history(artifact.monitor_definition_id, store=store)
    entry = history.items[0]

    assert response.benchmark_observation.overlay_id == "benchmark_trend_overlay_v1"
    assert response.portfolio_observation.total_portfolio_value == 600.0
    assert response.active_observation.required_overlay_status == "risk_reduced"
    assert entry.benchmark_observation.status == "risk_reduced"
    assert entry.portfolio_observation.cash_value == 500.0
    assert entry.active_observation.threshold_evaluation_performed is True


@pytest.mark.parametrize(
    ("observation_status", "cause_code", "alert_classification", "significance_status"),
    [
        ("degraded", "benchmark_observation_unconfirmed", "degraded", "degraded"),
        ("unavailable", "benchmark_observation_unavailable", "unavailable", "unavailable"),
        ("unavailable", "portfolio_truth_non_positive_total_value", "unavailable", "unavailable"),
    ],
)
def test_monitor_definition_cause_code_contract_supports_each_canonical_degraded_or_unavailable_code(
    tmp_path,
    observation_status: str,
    cause_code: str,
    alert_classification: str,
    significance_status: str,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_monitor_definition_observation(
        tmp_path,
        artifact.monitor_definition_id,
        observation_status=observation_status,
        cause_code=cause_code,
        alert_classification=alert_classification,
        benchmark_symbol="SPY",
    )
    _write_latest_monitor_evaluation_snapshot(
        tmp_path,
        artifact.monitor_definition_id,
        outcome_status=observation_status,
        cause_code=cause_code,
        significance_status=significance_status,
        benchmark_symbol="SPY",
    )

    observation = load_monitor_definition_observation(artifact.monitor_definition_id, store=store)
    snapshot = load_monitor_definition_latest_evaluation_snapshot(artifact.monitor_definition_id, store=store)

    assert observation.cause_code == cause_code
    assert snapshot.cause_code == cause_code


@pytest.mark.parametrize(
    ("observation_status", "alert_classification"),
    [("ok", "informational"), ("threshold_breach", "action_required")],
)
def test_monitor_definition_cause_code_contract_uses_explicit_null_for_ok_and_threshold_breach(
    observation_status: str,
    alert_classification: str,
) -> None:
    observation_payload = {
        "schema_version": "monitor_definition_observation_artifact_v1",
        "observation_id": "monitor_definition_observation_contract_check",
        "monitor_definition_id": "monitor_definition_contract_check",
        "monitor_definition_fingerprint": "fingerprint",
        "monitor_definition_schema_version": "monitor_definition_artifact_v1",
        "monitor_id": "benchmark_trend_overlay_v1",
        "benchmark_symbol": "SPY",
        "evaluation_mode": "review_only_observation_evaluation",
        "evaluated_at": "2026-04-20T09:30:00Z",
        "observation_status": observation_status,
        "cause_code": None,
        "alert_classification": alert_classification,
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
    snapshot_payload = {
        "schema_version": "monitor_definition_latest_evaluation_snapshot_v1",
        "monitor_definition_id": "monitor_definition_contract_check",
        "monitor_id": "benchmark_trend_overlay_v1",
        "benchmark_symbol": "SPY",
        "evaluated_at": "2026-04-20T09:30:00Z",
        "outcome_status": observation_status,
        "cause_code": None,
        "significance_status": alert_classification,
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
    }
    history_payload = {
        "history_entry_id": "monitor_definition_history_contract_check",
        "monitor_definition_id": "monitor_definition_contract_check",
        "monitor_definition_fingerprint": "fingerprint",
        "monitor_definition_schema_version": "monitor_definition_artifact_v1",
        "monitor_id": "benchmark_trend_overlay_v1",
        "benchmark_symbol": "SPY",
        "evaluation_mode": "review_only_observation_evaluation",
        "evaluated_at": "2026-04-20T09:30:00Z",
        "observation_status": observation_status,
        "cause_code": None,
        "significance_status": alert_classification,
        "reason": None,
        "thresholds": observation_payload["thresholds"],
        "benchmark_observation": observation_payload["benchmark_observation"],
        "portfolio_observation": observation_payload["portfolio_observation"],
        "active_observation": observation_payload["active_observation"],
    }

    assert MonitorDefinitionObservationArtifact.model_validate(observation_payload).cause_code is None
    assert MonitorDefinitionLatestEvaluationSnapshotArtifact.model_validate(snapshot_payload).cause_code is None
    assert MonitorDefinitionEvaluationHistoryEntryArtifact.model_validate(history_payload).cause_code is None

    for payload, model_cls in (
        (observation_payload, MonitorDefinitionObservationArtifact),
        (snapshot_payload, MonitorDefinitionLatestEvaluationSnapshotArtifact),
        (history_payload, MonitorDefinitionEvaluationHistoryEntryArtifact),
    ):
        with pytest.raises(
            ValidationError,
            match=re.escape("cause_code must be null unless observation_status is degraded or unavailable"),
        ):
            model_cls.model_validate({**payload, "cause_code": "benchmark_observation_unconfirmed"})


@pytest.mark.parametrize(
    ("mutator", "expected_error"),
        [
            (
                lambda payload: payload.__setitem__("cause_code", None),
                "persisted monitor definition observation failed schema validation",
            ),
            (
                lambda payload: payload.__setitem__("cause_code", "benchmark_observation_unavailable"),
                "persisted monitor definition observation failed schema validation",
            ),
            (
                lambda payload: payload.__setitem__("alert_classification", "informational"),
                "persisted monitor definition observation failed schema validation",
            ),
        ],
)
def test_load_monitor_definition_observation_rejects_unsupported_or_contradictory_cause_contract(
    tmp_path,
    mutator,
    expected_error: str,
) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    _write_monitor_definition_observation(
        tmp_path,
        artifact.monitor_definition_id,
        observation_status="degraded",
        cause_code="benchmark_observation_unconfirmed",
        alert_classification="degraded",
        benchmark_symbol="SPY",
    )
    _rekey_monitor_definition_observation_payload(
        tmp_path / f"{artifact.monitor_definition_id}.observation.json",
        mutator,
    )

    with pytest.raises((MonitorDefinitionSchemaValidationError, MonitorDefinitionIntegrityValidationError), match=expected_error):
        load_monitor_definition_observation(artifact.monitor_definition_id, store=store)


def test_persist_monitor_definition_evaluation_artifacts_fails_closed_on_cause_code_mismatch(tmp_path) -> None:
    store = MonitorDefinitionArtifactStore(base_dir=str(tmp_path))
    artifact = create_monitor_definition_artifact(
        CreateMonitorDefinitionRequest(monitor_id="benchmark_trend_overlay_v1", benchmark_symbol="SPY"),
        store=store,
    )
    response = evaluate_monitor_definition_observation(
        artifact.monitor_definition_id,
        EvaluateMonitorDefinitionObservationRequest(
            current_portfolio=_build_imported_snapshot_for_optimizer(),
            benchmark_observation=_monitor_benchmark_observation(status="unconfirmed", confirmation_count=1),
        ),
        artifact_store=store,
    )
    evaluated_at = load_monitor_definition_latest_evaluation_snapshot(artifact.monitor_definition_id, store=store).evaluated_at
    observation = build_stable_monitor_definition_observation(MonitorDefinitionObservationArtifact(
        observation_id="monitor_definition_observation_pending",
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_definition_fingerprint=artifact.fingerprint,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        evaluated_at=evaluated_at,
        observation_status=response.observation_status,
        cause_code="benchmark_observation_unconfirmed",
        alert_classification="degraded",
        reason=response.reason,
        thresholds=response.thresholds,
        benchmark_observation=response.benchmark_observation,
        portfolio_observation=response.portfolio_observation,
        active_observation=response.active_observation,
    ))
    snapshot = MonitorDefinitionLatestEvaluationSnapshotArtifact.model_construct(
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        evaluated_at=evaluated_at,
        outcome_status=response.observation_status,
        cause_code="benchmark_observation_unavailable",
        significance_status="degraded",
        benchmark_observation_lineage=MonitorDefinitionLatestEvaluationBenchmarkObservationLineage(
            source_id=response.benchmark_observation.source_lineage.source_id,
            observed_at=response.benchmark_observation.source_lineage.observed_at,
        ),
        portfolio_truth_basis=MonitorDefinitionLatestEvaluationPortfolioTruthBasis(
            importer=response.portfolio_observation.source_lineage.importer,
            imported_at=response.portfolio_observation.source_lineage.imported_at,
            source_path="IB2024.pdf",
            statement_period=response.portfolio_observation.source_lineage.statement_period,
        ),
    )
    entry = build_stable_monitor_definition_evaluation_history_entry(MonitorDefinitionEvaluationHistoryEntryArtifact(
        history_entry_id="monitor_definition_history_pending",
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_definition_fingerprint=artifact.fingerprint,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        evaluated_at=evaluated_at,
        observation_status=response.observation_status,
        cause_code="benchmark_observation_unconfirmed",
        significance_status="degraded",
        hysteresis_transition="open",
        source_precedence="persisted_evaluation_history_entry_only",
        reason=response.reason,
        thresholds=response.thresholds,
        benchmark_observation=response.benchmark_observation,
        portfolio_observation=response.portfolio_observation,
        active_observation=response.active_observation,
    ))

    with pytest.raises(MonitorDefinitionPersistenceError, match="observation cause_code must match persisted evaluation artifacts"):
        persist_monitor_definition_evaluation_artifacts(observation, snapshot, entry, store=store)


def test_hypothetical_replacement_preview_route_uses_constructed_candidate_rule_in_derivation_and_provenance(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IUFS": _history(100.0, 103.0, 103.5, 105.0, 109.0),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
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
    constructed_candidate = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID_FIXED_SPLIT),
        )
    )

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": _draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)).model_dump(mode="json"),
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "constructed_candidate": constructed_candidate.model_dump(mode="json"),
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
    assert payload["derivation"] == {
        "baseline_basis": "draft_snapshot_positions_normalized",
        "candidate_construction_rule": "fixed_split_50_50_substitution_v2",
    }
    assert payload["replay_provenance"] == {
        "candidate_input_source": "constructed_candidate_payload",
        "construction_rule_id": "fixed_split_50_50_substitution_v2",
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
    }
    assert payload["candidate_weights"] == [
        {"symbol": "VUAA", "target_weight": 0.3},
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.3},
    ]


def test_hypothetical_replacement_preview_route_echoes_constraint_validation_lineage_without_enforcement(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IUFS": _history(100.0, 103.0, 103.5, 105.0, 109.0),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
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
    constructed_candidate = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID_FIXED_SPLIT),
        )
    )
    constructed_candidate_input = ConstructedCandidateReplayInput.model_validate(constructed_candidate.model_dump(mode="json"))
    constraint_validation = validate_single_replacement_candidate_construction_constraints(
        SingleReplacementConstructionConstraintValidationRequest(
            constructed_candidate=constructed_candidate_input,
            constraint_set=SingleReplacementConstructionConstraintSetInput(constraint_set_id=CONSTRAINT_SET_ID),
        )
    )
    constraint_validation.validation.status = "blocked"

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": _draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)).model_dump(mode="json"),
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "constructed_candidate": constructed_candidate_input.model_dump(mode="json"),
            "constraint_validation": constraint_validation.model_dump(mode="json"),
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
    assert payload["replay_provenance"]["constraint_validation"] == {
        "supplied": True,
        "validation_status": "blocked",
        "constraint_set_id": "single_replacement_construction_constraints_v1",
    }


def test_hypothetical_replacement_preview_rejects_constraint_validation_without_constructed_candidate() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constraint_validation=constraint_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation requires constructed_candidate"


def test_hypothetical_replacement_preview_rejects_constraint_validation_proposal_incumbent_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.proposal.incumbent_symbol = "QQQ"

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation incumbent does not match constructed_candidate proposal"


def test_hypothetical_replacement_preview_rejects_constraint_validation_proposal_candidate_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.proposal.candidate_symbol = "IUIT"

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation candidate does not match constructed_candidate proposal"


def test_hypothetical_replacement_preview_rejects_constraint_validation_rule_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.construction.rule_id = "same_weight_substitution_v1"

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation rule_id does not match constructed_candidate"


def test_hypothetical_replacement_preview_rejects_constraint_validation_status_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.construction.status = "rejected"

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation construction status does not match constructed_candidate"


def test_hypothetical_replacement_preview_rejects_constraint_validation_constraint_set_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.validation = cast(
        SingleReplacementConstraintValidationState,
        SimpleNamespace(
        kind=mismatched_validation.validation.kind,
        status=mismatched_validation.validation.status,
        constraint_set_id="unsupported_constraint_set_v0",
        ),
    )

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation constraint_set_id is unsupported: unsupported_constraint_set_v0"
