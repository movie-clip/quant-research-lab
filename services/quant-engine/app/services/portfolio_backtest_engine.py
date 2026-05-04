from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal, cast

from pydantic import ValidationError

from app.analytics.risk import build_factor_registry, build_portfolio_risk_summary, build_relative_risk_summary, build_risk_contribution_breakdown, build_rolling_risk_series, build_statistical_factor_model, build_stress_scenarios, build_volatility_regime_payload
from app.schemas.construction import ConstructionArtifact
from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement
from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition, SnapshotItem
from app.backtests.portfolio_engine import PortfolioAllocationBacktestEngine
from app.instruments.registry import InstrumentRegistry
from app.schemas.backtest_engine import (
    AllocationBacktestComparison,
    AllocationBacktestInstrumentMeta,
    AllocationBacktestResult,
    AllocationBacktestStatus,
    BenchmarkTrendOverlayMonitorActiveObservation,
    BenchmarkTrendOverlayMonitorBenchmarkObservationInput,
    BenchmarkTrendOverlayMonitorPortfolioObservation,
    ConstructionArtifactReplayEffectiveParams,
    ConstructionArtifactPreviewRequest,
    ConstructionArtifactReplayProvenance,
    ConstructionArtifactReplayRequest,
    ConstructionArtifactReplayResponse,
    ConstructionArtifactReplayValidationResponse,
    ConstructionArtifactPreviewHandoff,
    ConstructionArtifactWorkspaceReviewBasis,
    CurrentPortfolioTruthLineage,
    EvaluateMonitorDefinitionObservationRequest,
    DistributionPolicy,
    HypotheticalReplayDerivation,
    HypotheticalReplayProvenance,
    HypotheticalReplayProposal,
    HypotheticalReplayUpstreamIds,
    MonitorDefinitionEvaluationHistoryEntryArtifact,
    MonitorDefinitionObservationArtifact,
    MonitorDefinitionLatestEvaluationBenchmarkObservationLineage,
    MonitorDefinitionLatestEvaluationPortfolioTruthBasis,
    MonitorDefinitionLatestEvaluationSnapshotArtifact,
    MonitorDefinitionObservationEvaluationResponse,
    MonitorThresholdTrigger,
    OverlayApplicationSummary,
    OptimizerHandoffReplayBenchmarkAttestationSummary,
    OptimizerHandoffReplayConstraintSummary,
    OptimizerHandoffReplayHandoff,
    OptimizerHandoffReplayOptimizerContext,
    OptimizerHandoffReplayOptimizerDiagnostics,
    OptimizerHandoffReplayProvenance,
    OptimizerHandoffReplayRequest,
    OptimizerHandoffReplayResponse,
    OptimizerHandoffReplayOptimizerRunSummary,
    OptimizerHandoffWorkspaceReviewBasis,
    OverlayAwareHypotheticalReplayRequest,
    OverlayAwareHypotheticalReplayResponse,
    HypotheticalReplacementReplayRequest,
    HypotheticalReplacementReplayResponse,
    PortfolioDiagnosticsProvenance,
    PortfolioDiagnosticsComparisonRow,
    PortfolioDiagnosticsSnapshot,
    PortfolioDiagnosticsTopCallout,
    PortfolioImprovementComparison,
    PortfolioAllocationBacktestRequest,
    PortfolioAllocationBacktestResponse,
    PortfolioWeightInput,
    ReplayMethodologyProvenance,
    ReviewSnapshotArtifact,
    ReviewSnapshotArtifactAnalyticsSummary,
    ReviewSnapshotArtifactCompactSummary,
    ReviewSnapshotArtifactDiagnosticsSummary,
    ReviewSnapshotArtifactIdentity,
    ReviewSnapshotArtifactLineage,
    ReviewSnapshotArtifactReviewBasis,
    ReviewSnapshotArtifactSourcePayload,
    ReviewSnapshotArtifactTruthLabels,
    ReviewSnapshotComparisonArtifactRef,
    ReviewSnapshotComparisonAssumptionsEnvelope,
    ReviewSnapshotActiveThesisCrossFamilyPMSummaryFields,
    ReviewSnapshotActiveThesisCrossFamilyQueueActiveThesis,
    ReviewSnapshotActiveThesisCrossFamilyQueueRequest,
    ReviewSnapshotActiveThesisCrossFamilyQueueResponse,
    ReviewSnapshotActiveThesisCrossFamilyQueueRow,
    ReviewSnapshotActiveThesisCrossFamilySeparation,
    ReviewSnapshotActiveThesisCrossFamilyTrustVisibility,
    ReviewSnapshotFamilyCompareReadiness,
    ReviewSnapshotFamilyInboxRequest,
    ReviewSnapshotFamilyInboxResponse,
    ReviewSnapshotFamilyInboxRow,
    ReviewSnapshotFamilyKey,
    ReviewSnapshotFamilyReviewRequest,
    ReviewSnapshotFamilyReviewResponse,
    ReviewSnapshotFamilySiblingSummary,
    ReviewSnapshotSiblingComparisonEligibility,
    ReviewSnapshotPMSummaryAnalyticsSummary,
    ReviewSnapshotPMSummaryEnvelope,
    ReviewSnapshotPMSummaryMethodology,
    ReviewSnapshotPMSummaryProvenance,
    ReviewSnapshotPMSummaryReviewBasis,
    ReviewSnapshotComparisonMethodology,
    ReviewSnapshotComparisonMethodologyEnvelope,
    ReviewSnapshotComparisonPairSummary,
    ReviewSnapshotComparisonRequest,
    ReviewSnapshotComparisonResponse,
    ReviewSnapshotProposalCapture,
    ReviewSnapshotProposalCaptureProposal,
    ReviewSnapshotProposalCaptureReviewBasis,
    ReviewSnapshotCreateRequest,
    ReviewSnapshotOpenHandoff,
    ReviewSnapshotOpenResponse,
    WorkspaceReviewWindow,
)
from app.schemas.optimizer import OptimizerReturnBasisAttestation
from app.schemas.research import InvestorEconomicsStatus, build_investor_economics_status
from app.schemas.reconciliation import RiskConcentrationSnapshot
from app.services.construction_artifact_service import load_construction_artifact
from app.services.candidate_construction import build_candidate_weights_from_replacement_intent as _shared_build_candidate_weights_from_replacement_intent
from app.services.candidate_construction import build_snapshot_baseline_weights as _shared_build_snapshot_baseline_weights
from app.services.candidate_construction import derive_single_replacement_construction
from app.services.candidate_construction import derive_same_weight_substitution_construction
from app.services.market_data import MarketDataService
from app.services.monitor_definition_artifact_service import (
    MonitorDefinitionMissingFileError,
    build_stable_monitor_definition_evaluation_history_entry,
    build_stable_monitor_definition_observation,
    load_monitor_definition_artifact,
    load_monitor_definition_latest_evaluation_snapshot,
    persist_monitor_definition_evaluation_artifacts,
)
from app.services.optimizer_handoff_constraints import (
    build_optimizer_handoff_replay_output_policy,
    load_validated_optimizer_handoff_for_replay,
)
from app.services.optimizer_artifact_service import normalize_optimizer_return_basis_attestation
from app.services.review_snapshot_artifact_service import (
    ReviewSnapshotArtifactStore,
    build_stable_review_snapshot_artifact,
    list_review_snapshot_artifacts,
    load_review_snapshot_artifact,
    persist_review_snapshot_artifact,
)


METHODOLOGY = "Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions."
CASH_SYMBOL = "__CASH__"
REPLAY_REFUSAL_POLICY_RATIONALE = "When replay/backtest investor total-return equivalence is unverified, suppress all user-facing investor-economics metrics and any derived or comparative views from that basis, including drawdown surfaces, Sharpe, Sortino, benchmark-relative deltas, and monitoring callouts; emit only null/withheld semantics, never numeric fallbacks or zero-equivalent UI states."
REPLAY_BENCHMARK_RELATIVE_METRIC_FIELDS = (
    "benchmark_return_pct",
    "excess_return_pct",
    "tracking_error_pct",
    "information_ratio",
    "beta_vs_benchmark",
    "correlation_vs_benchmark",
)
REPLAY_BENCHMARK_RELATIVE_COMPARISON_FIELDS = (
    "benchmark_return_diff_pct",
    "excess_return_diff_pct",
    "tracking_error_diff_pct",
    "information_ratio_diff",
    "beta_diff",
    "correlation_diff",
)


@dataclass(frozen=True)
class BacktestDiagnosticsInputs:
    synthetic_snapshot: ImportedPortfolioSnapshot
    replay_daily_states: list[DailyPortfolioState]
    benchmark_price_history: list[dict]
    factor_price_histories: dict[str, list[dict]]


def build_portfolio_allocation_backtest_analysis(request: PortfolioAllocationBacktestRequest) -> PortfolioAllocationBacktestResponse:
    return _build_portfolio_allocation_backtest_analysis(request)


def _build_portfolio_allocation_backtest_analysis(
    request: PortfolioAllocationBacktestRequest,
    *,
    return_basis_attestation: OptimizerReturnBasisAttestation | None = None,
) -> PortfolioAllocationBacktestResponse:
    symbols = [item.symbol for item in request.weights]
    if request.reference_weights:
        symbols.extend(item.symbol for item in request.reference_weights)
    symbols.extend(item.us_proxy for item in build_factor_registry())
    symbols.append(request.benchmark_symbol)

    market_data = MarketDataService()
    histories = market_data.get_historical_prices_for_symbols(
        symbols,
        request.start_date.isoformat(),
        request.end_date.isoformat(),
        symbol_overrides=request.symbol_overrides,
        allow_proxy_fallback=True,
    )
    benchmark_rows = histories.get(request.benchmark_symbol, [])
    if not benchmark_rows:
        raise ValueError(f"No historical prices found for benchmark: {request.benchmark_symbol}")
    _inject_cash_history(histories, benchmark_rows, symbols)

    registry = InstrumentRegistry()
    engine = PortfolioAllocationBacktestEngine()
    candidate_symbols = [item.symbol for item in request.weights]
    candidate_dates = _aligned_dates(candidate_symbols, histories, benchmark_rows)
    candidate_histories = {symbol: histories.get(symbol, []) for symbol in candidate_symbols}
    candidate_status = _derive_status(
        symbols=candidate_symbols,
        ordered_dates=candidate_dates,
        requested_start=request.start_date.isoformat(),
        requested_end=request.end_date.isoformat(),
        registry=registry,
        histories=candidate_histories,
        benchmark_rows=benchmark_rows,
    )
    candidate_result = engine.run(
        request=request,
        portfolio_name=request.portfolio_name or "Candidate",
        weights=request.weights,
        benchmark_rows=benchmark_rows,
        price_histories=candidate_histories,
        ordered_dates=candidate_dates,
        instrument_metadata=_instrument_metadata(candidate_symbols, registry),
        status=candidate_status,
    )

    reference_result = None
    comparison = None
    reference_diagnostics = None
    candidate_diagnostics = None
    diagnostics_comparison = None
    if request.reference_weights:
        reference_symbols = [item.symbol for item in request.reference_weights]
        reference_dates = _aligned_dates(reference_symbols, histories, benchmark_rows)
        common_dates = sorted(set(candidate_dates) & set(reference_dates))
        if len(common_dates) < 2:
            raise ValueError("Not enough common dates across candidate, reference, and benchmark")
        candidate_result = engine.run(
            request=request,
            portfolio_name=request.portfolio_name or "Candidate",
            weights=request.weights,
            benchmark_rows=benchmark_rows,
            price_histories=candidate_histories,
            ordered_dates=common_dates,
            instrument_metadata=_instrument_metadata(candidate_symbols, registry),
            status=_derive_status(
                symbols=candidate_symbols,
                ordered_dates=common_dates,
                requested_start=request.start_date.isoformat(),
                requested_end=request.end_date.isoformat(),
                registry=registry,
                histories=candidate_histories,
                benchmark_rows=benchmark_rows,
            ),
        )
        reference_histories = {symbol: histories.get(symbol, []) for symbol in reference_symbols}
        reference_result = engine.run(
            request=request,
            portfolio_name="Reference",
            weights=request.reference_weights,
            benchmark_rows=benchmark_rows,
            price_histories=reference_histories,
            ordered_dates=common_dates,
            instrument_metadata=_instrument_metadata(reference_symbols, registry),
            status=_derive_status(
                symbols=reference_symbols,
                ordered_dates=common_dates,
                requested_start=request.start_date.isoformat(),
                requested_end=request.end_date.isoformat(),
                registry=registry,
                histories=reference_histories,
                benchmark_rows=benchmark_rows,
            ),
        )
        comparison = _compare_results(reference_result, candidate_result)
        reference_diagnostics = _build_portfolio_diagnostics_snapshot(
            portfolio_name="Reference",
            weights=request.reference_weights,
            result=reference_result,
            benchmark_rows=benchmark_rows,
            histories=histories,
            return_basis_attestation=return_basis_attestation,
        )
        candidate_diagnostics = _build_portfolio_diagnostics_snapshot(
            portfolio_name=request.portfolio_name or "Candidate",
            weights=request.weights,
            result=candidate_result,
            benchmark_rows=benchmark_rows,
            histories=histories,
            return_basis_attestation=return_basis_attestation,
        )
        diagnostics_comparison = _build_diagnostics_comparison(
            reference_diagnostics,
            candidate_diagnostics,
            return_basis_attestation=return_basis_attestation,
        )
    else:
        candidate_diagnostics = _build_portfolio_diagnostics_snapshot(
            portfolio_name=request.portfolio_name or "Candidate",
            weights=request.weights,
            result=candidate_result,
            benchmark_rows=benchmark_rows,
            histories=histories,
            return_basis_attestation=return_basis_attestation,
        )

    reference_result = _apply_return_basis_attestation_to_replay_result(reference_result, return_basis_attestation)
    candidate_result = _apply_return_basis_attestation_to_replay_result(candidate_result, return_basis_attestation)
    comparison = _apply_return_basis_attestation_to_replay_comparison(comparison, return_basis_attestation)
    if candidate_result is None:
        raise ValueError("candidate replay result was not produced")
    assert candidate_result is not None

    return PortfolioAllocationBacktestResponse(
        methodology=METHODOLOGY,
        methodology_provenance=ReplayMethodologyProvenance(),
        investor_economics_status=_build_response_investor_economics_status(reference_result, candidate_result),
        reference_result=reference_result,
        candidate_result=candidate_result,
        comparison=comparison,
        reference_diagnostics=reference_diagnostics,
        candidate_diagnostics=candidate_diagnostics,
        diagnostics_comparison=diagnostics_comparison,
    )


def _build_response_investor_economics_status(
    reference_result: AllocationBacktestResult | None,
    candidate_result: AllocationBacktestResult,
) -> InvestorEconomicsStatus:
    statuses = [candidate_result.investor_economics_status]
    if reference_result is not None:
        statuses.append(reference_result.investor_economics_status)
    return build_investor_economics_status(
        available=not any(status.status == "withheld" for status in statuses),
    )


def _aligned_dates(symbols: list[str], histories: dict[str, list[dict]], benchmark_rows: list[dict]) -> list[str]:
    common_dates = {row["date"] for row in benchmark_rows}
    for symbol in symbols:
        rows = histories.get(symbol, [])
        if not rows:
            raise ValueError(f"No historical prices found for symbol: {symbol}")
        common_dates &= {row["date"] for row in rows}
    ordered = sorted(common_dates)
    if len(ordered) < 2:
        raise ValueError("Not enough common dates across portfolio symbols and benchmark")
    return ordered


def _build_snapshot_baseline_weights(snapshot):
    return _shared_build_snapshot_baseline_weights(snapshot)


def _build_candidate_weights_from_replacement_intent(baseline_weights, incumbent_symbol: str, candidate_symbol: str):
    return _shared_build_candidate_weights_from_replacement_intent(baseline_weights, incumbent_symbol, candidate_symbol)


def _build_hypothetical_replay_warnings(snapshot) -> list[str]:
    warnings: list[str] = []
    if snapshot.cash_balances:
        warnings.append("Cash balances are not included in the hypothetical replay baseline for this MVP.")
    warnings.append("Candidate weights are derived from a single-symbol replacement intent and remain hypothetical replay inputs only.")
    return warnings


def build_hypothetical_replacement_replay_preview(request: HypotheticalReplacementReplayRequest) -> HypotheticalReplacementReplayResponse:
    if request.replacement_intent is None:
        raise ValueError("replacement_intent is required")

    replay_provenance = _build_hypothetical_replay_provenance(request)
    baseline_weights, candidate_weights = _resolve_hypothetical_replay_weights(request)
    if request.replacement_intent.benchmark_symbol and request.replacement_intent.benchmark_symbol != request.benchmark_symbol:
        raise ValueError("replacement intent benchmark does not match replay benchmark")

    symbols = [item.symbol for item in candidate_weights]
    market_data = MarketDataService()
    histories = market_data.get_historical_prices_for_symbols(
        symbols,
        request.start_date.isoformat(),
        request.end_date.isoformat(),
        symbol_overrides=request.symbol_overrides,
        allow_proxy_fallback=True,
    )
    candidate_symbol = request.replacement_intent.candidate_symbol.upper()
    if not histories.get(candidate_symbol):
        raise ValueError(f"No historical prices found for symbol: {candidate_symbol}")

    replay_request = PortfolioAllocationBacktestRequest(
        portfolio_name="Hypothetical Candidate",
        weights=candidate_weights,
        reference_weights=baseline_weights,
        benchmark_symbol=request.benchmark_symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        rebalance_frequency=request.rebalance_frequency,
        base_currency=request.base_currency,
        commission_bps=request.commission_bps,
        slippage_bps=request.slippage_bps,
        drift_tolerance_pct=request.drift_tolerance_pct,
        price_basis=request.price_basis,
        execution_price_field=request.execution_price_field,
        execution_lag_days=request.execution_lag_days,
        symbol_overrides=request.symbol_overrides,
    )

    replay = build_portfolio_allocation_backtest_analysis(replay_request)

    return HypotheticalReplacementReplayResponse(
        proposal=HypotheticalReplayProposal(
            source="draft_replacement_intent",
            incumbent_symbol=request.replacement_intent.base_symbol,
            candidate_symbol=request.replacement_intent.candidate_symbol,
            draft_id=request.replacement_intent.draft_id,
            base_node_id=request.replacement_intent.base_node_id,
        ),
        derivation=HypotheticalReplayDerivation(
            baseline_basis="draft_snapshot_positions_normalized",
            candidate_construction_rule=replay_provenance.construction_rule_id,
        ),
        replay_provenance=replay_provenance,
        baseline_weights=baseline_weights,
        candidate_weights=candidate_weights,
        replay=replay,
        warnings=_build_hypothetical_replay_warnings(request.snapshot),
    )


def build_optimizer_handoff_replay_preview(
    request: OptimizerHandoffReplayRequest | OptimizerHandoffReplayHandoff,
    *,
    handoff_store=None,
) -> OptimizerHandoffReplayResponse:
    replay_request = resolve_optimizer_handoff_replay_request(request)
    validated_gate = load_validated_optimizer_handoff_for_replay(replay_request, handoff_store=handoff_store)
    persisted_handoff = validated_gate.persisted_handoff
    manifest = persisted_handoff.manifest
    artifact = persisted_handoff.artifact
    benchmark_symbol = validated_gate.benchmark_symbol
    normalized_return_basis_attestation = manifest.return_basis_attestation

    baseline_weights = _portfolio_weight_inputs_from_optimizer_weights(artifact.replay.current_weights)
    candidate_weights = _portfolio_weight_inputs_from_optimizer_weights(artifact.proposed_weights)
    replay = _build_portfolio_allocation_backtest_analysis(
        PortfolioAllocationBacktestRequest(
            portfolio_name="Optimizer Handoff Candidate",
            weights=candidate_weights,
            reference_weights=baseline_weights,
            benchmark_symbol=benchmark_symbol,
            start_date=replay_request.start_date,
            end_date=replay_request.end_date,
            initial_capital=replay_request.initial_capital,
            rebalance_frequency=replay_request.rebalance_frequency,
            base_currency=replay_request.base_currency,
            commission_bps=replay_request.commission_bps,
            slippage_bps=replay_request.slippage_bps,
            drift_tolerance_pct=replay_request.drift_tolerance_pct,
            price_basis=replay_request.price_basis,
            execution_price_field=replay_request.execution_price_field,
            execution_lag_days=replay_request.execution_lag_days,
            symbol_overrides=replay_request.symbol_overrides,
        ),
        return_basis_attestation=normalized_return_basis_attestation,
    )

    return OptimizerHandoffReplayResponse(
        handoff_id=manifest.handoff_id,
        artifact_id=artifact.artifact_id,
        source_portfolio_snapshot_id=manifest.source_portfolio_snapshot.snapshot_id,
        replay_provenance=OptimizerHandoffReplayProvenance(
            benchmark_id=manifest.benchmark.benchmark_id,
            benchmark_version=manifest.benchmark.benchmark_version,
            benchmark_symbol=benchmark_symbol,
            return_basis_attestation=normalized_return_basis_attestation,
            replay_output_policy=build_optimizer_handoff_replay_output_policy(normalized_return_basis_attestation),
            artifact_state=artifact.artifact_state.artifact_state,
            constraint_set_fingerprint=manifest.constraint_set.constraint_set_fingerprint,
        ),
        review_basis=OptimizerHandoffWorkspaceReviewBasis(
            handoff_reference=replay_request.handoff_reference,
            benchmark_symbol=benchmark_symbol,
            base_currency=replay_request.base_currency,
            replay_window=WorkspaceReviewWindow(
                start_date=replay_request.start_date.isoformat(),
                end_date=replay_request.end_date.isoformat(),
            ),
            baseline_weights=baseline_weights,
            candidate_weights=candidate_weights,
        ),
        optimizer_context=_build_optimizer_handoff_context(artifact),
        baseline_weights=baseline_weights,
        candidate_weights=candidate_weights,
        replay=replay,
    )


def resolve_optimizer_handoff_replay_request(
    request: OptimizerHandoffReplayRequest | OptimizerHandoffReplayHandoff,
) -> OptimizerHandoffReplayRequest:
    if isinstance(request, OptimizerHandoffReplayRequest):
        return request
    return OptimizerHandoffReplayRequest(
        handoff_reference=request.handoff_reference,
        start_date=request.effective_replay_params.start_date,
        end_date=request.effective_replay_params.end_date,
        initial_capital=request.effective_replay_params.initial_capital,
        rebalance_frequency=request.effective_replay_params.rebalance_frequency,
        base_currency=request.effective_replay_params.base_currency,
        commission_bps=request.effective_replay_params.commission_bps,
        slippage_bps=request.effective_replay_params.slippage_bps,
        drift_tolerance_pct=request.effective_replay_params.drift_tolerance_pct,
        price_basis=request.effective_replay_params.price_basis,
        execution_price_field=request.effective_replay_params.execution_price_field,
        execution_lag_days=request.effective_replay_params.execution_lag_days,
        symbol_overrides=request.effective_replay_params.symbol_overrides,
    )


def build_construction_artifact_replay_preview(
    request: ConstructionArtifactPreviewRequest,
    *,
    artifact_store=None,
) -> ConstructionArtifactReplayResponse:
    preflight = preflight_construction_artifact_replay(request, artifact_store=artifact_store)
    artifact = preflight.artifact
    baseline_weights = preflight.baseline_weights
    candidate_weights = preflight.candidate_weights
    effective_params = preflight.effective_replay_params
    replay = build_portfolio_allocation_backtest_analysis(
        PortfolioAllocationBacktestRequest(
            portfolio_name="Construction Artifact Candidate",
            weights=candidate_weights,
            reference_weights=baseline_weights,
            benchmark_symbol=effective_params.benchmark_symbol,
            start_date=effective_params.start_date,
            end_date=effective_params.end_date,
            initial_capital=effective_params.initial_capital,
            rebalance_frequency=effective_params.rebalance_frequency,
            base_currency=effective_params.base_currency,
            commission_bps=effective_params.commission_bps,
            slippage_bps=effective_params.slippage_bps,
            drift_tolerance_pct=effective_params.drift_tolerance_pct,
            price_basis=effective_params.price_basis,
            execution_price_field=effective_params.execution_price_field,
            execution_lag_days=effective_params.execution_lag_days,
            symbol_overrides=effective_params.symbol_overrides,
        )
    )

    return ConstructionArtifactReplayResponse(
        construction_artifact_id=artifact.artifact_id,
        review_basis=ConstructionArtifactWorkspaceReviewBasis(
            construction_artifact_id=artifact.artifact_id,
            preview_handoff=ConstructionArtifactPreviewHandoff(
                construction_artifact_id=artifact.artifact_id,
                effective_replay_params=effective_params,
            ),
            benchmark_symbol=effective_params.benchmark_symbol,
            base_currency=effective_params.base_currency,
            replay_window=WorkspaceReviewWindow(
                start_date=effective_params.start_date.isoformat(),
                end_date=effective_params.end_date.isoformat(),
            ),
            baseline_weights=baseline_weights,
            candidate_weights=candidate_weights,
        ),
        replay_provenance=ConstructionArtifactReplayProvenance(
            construction_artifact_id=artifact.artifact_id,
            policy_id=artifact.normalized_inputs.policy_id,
            policy_definition_id=artifact.normalized_inputs.policy_definition_id,
            ranked_universe_artifact_id=artifact.normalized_inputs.ranked_universe_artifact_id,
            ranking_id=artifact.normalized_inputs.ranking_id,
            ranking_methodology_id=artifact.normalized_inputs.ranking_methodology_id,
            current_portfolio_artifact_id=artifact.normalized_inputs.current_portfolio_artifact_id,
            hard_constraints=artifact.hard_constraints,
            selection_rule_trace=artifact.selection_rule_trace,
            turnover_diagnostics_status=artifact.turnover_diagnostics_status,
            turnover_diagnostics_v1=artifact.turnover_diagnostics_v1,
            weighting_trace_status=artifact.weighting_trace_status,
            weighting_trace_v1=artifact.weighting_trace_v1,
        ),
        baseline_weights=baseline_weights,
        candidate_weights=candidate_weights,
        effective_replay_params=effective_params,
        replay=replay,
    )


@dataclass(frozen=True)
class ConstructionArtifactReplayPreflight:
    artifact: ConstructionArtifact
    baseline_weights: list[PortfolioWeightInput]
    candidate_weights: list[PortfolioWeightInput]
    effective_replay_params: ConstructionArtifactReplayEffectiveParams


def validate_construction_artifact_replay_params(
    request: ConstructionArtifactReplayRequest,
    *,
    artifact_store=None,
) -> ConstructionArtifactReplayValidationResponse:
    preflight = preflight_construction_artifact_replay(
        request,
        artifact_store=artifact_store,
    )
    return ConstructionArtifactReplayValidationResponse(
        construction_artifact_id=preflight.artifact.artifact_id,
        effective_replay_params=preflight.effective_replay_params,
        preview_handoff=ConstructionArtifactPreviewHandoff(
            construction_artifact_id=preflight.artifact.artifact_id,
            effective_replay_params=preflight.effective_replay_params,
        ),
    )


def preflight_construction_artifact_replay(
    request: ConstructionArtifactPreviewRequest,
    *,
    artifact_store=None,
) -> ConstructionArtifactReplayPreflight:
    preview_handoff = resolve_construction_artifact_preview_handoff(request)
    artifact = load_construction_artifact(preview_handoff.construction_artifact_id, store=artifact_store)
    if artifact.status != "feasible":
        raise ValueError("construction_artifact_id must reference a feasible construction artifact")
    if not artifact.final_target_weights:
        raise ValueError("construction_artifact_id must reference an artifact with final_target_weights")
    if not artifact.normalized_inputs.current_portfolio_weights:
        raise ValueError(
            "construction artifact replay requires normalized_inputs.current_portfolio_weights for the baseline replay path"
        )

    return ConstructionArtifactReplayPreflight(
        artifact=artifact,
        baseline_weights=_portfolio_weight_inputs_from_construction_weights(
            artifact.normalized_inputs.current_portfolio_weights
        ),
        candidate_weights=_portfolio_weight_inputs_from_construction_weights(artifact.final_target_weights),
        effective_replay_params=preview_handoff.effective_replay_params,
    )


def resolve_construction_artifact_preview_handoff(
    request: ConstructionArtifactPreviewRequest,
) -> ConstructionArtifactPreviewHandoff:
    if isinstance(request, ConstructionArtifactPreviewHandoff):
        return request
    return ConstructionArtifactPreviewHandoff(
        construction_artifact_id=request.construction_artifact_id,
        effective_replay_params=resolve_and_validate_construction_artifact_replay_params(request),
    )


def resolve_and_validate_construction_artifact_replay_params(
    request: ConstructionArtifactReplayRequest,
) -> ConstructionArtifactReplayEffectiveParams:
    return _validate_effective_construction_artifact_replay_params(
        resolve_construction_artifact_replay_params(request)
    )


def resolve_construction_artifact_replay_params(
    request: ConstructionArtifactReplayRequest,
) -> ConstructionArtifactReplayEffectiveParams:
    defaults = ConstructionArtifactReplayEffectiveParams()
    return ConstructionArtifactReplayEffectiveParams.model_construct(
        benchmark_symbol=request.benchmark_symbol if request.benchmark_symbol is not None else defaults.benchmark_symbol,
        start_date=request.start_date if request.start_date is not None else defaults.start_date,
        end_date=request.end_date if request.end_date is not None else defaults.end_date,
        initial_capital=request.initial_capital if request.initial_capital is not None else defaults.initial_capital,
        rebalance_frequency=request.rebalance_frequency if request.rebalance_frequency is not None else defaults.rebalance_frequency,
        base_currency=request.base_currency if request.base_currency is not None else defaults.base_currency,
        commission_bps=request.commission_bps if request.commission_bps is not None else defaults.commission_bps,
        slippage_bps=request.slippage_bps if request.slippage_bps is not None else defaults.slippage_bps,
        drift_tolerance_pct=request.drift_tolerance_pct,
        price_basis=request.price_basis if request.price_basis is not None else defaults.price_basis,
        execution_price_field=request.execution_price_field if request.execution_price_field is not None else defaults.execution_price_field,
        execution_lag_days=request.execution_lag_days if request.execution_lag_days is not None else defaults.execution_lag_days,
        symbol_overrides=request.symbol_overrides if request.symbol_overrides is not None else defaults.symbol_overrides,
    )


def _validate_effective_construction_artifact_replay_params(
    effective_params: ConstructionArtifactReplayEffectiveParams,
) -> ConstructionArtifactReplayEffectiveParams:
    try:
        return ConstructionArtifactReplayEffectiveParams.model_validate(effective_params.model_dump())
    except ValidationError as exc:
        message = exc.errors()[0]["msg"]
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        raise ValueError(message) from exc


def create_review_snapshot_artifact(
    request: ReviewSnapshotCreateRequest,
    *,
    store=None,
) -> ReviewSnapshotArtifact:
    replay_type = "overlay_aware" if isinstance(request.review_payload, OverlayAwareHypotheticalReplayResponse) else "standard"
    active_replay = _active_replay_from_review_snapshot_payload(request.review_payload)
    diagnostics_summary = _build_review_snapshot_diagnostics_summary(active_replay.diagnostics_comparison)
    standard_payload = request.review_payload if isinstance(request.review_payload, HypotheticalReplacementReplayResponse) else None
    overlay_payload = request.review_payload if isinstance(request.review_payload, OverlayAwareHypotheticalReplayResponse) else None
    lineage = ReviewSnapshotArtifactLineage(
        workspace_id=request.workspace_id,
        source_draft_id=request.source_draft_id,
        source_base_node_id=request.source_base_node_id,
        proposal_family_id=request.proposal_family_id,
        proposal_id=request.proposal_id,
        version_number=request.version_number,
    )
    review_basis = ReviewSnapshotArtifactReviewBasis(
        benchmark_symbol=active_replay.candidate_result.benchmark_symbol or "SPY",
        start_date=active_replay.candidate_result.start_date,
        end_date=active_replay.candidate_result.end_date,
        rebalance_frequency=active_replay.candidate_result.rebalance_frequency,
        commission_bps=active_replay.candidate_result.commission_bps,
        slippage_bps=active_replay.candidate_result.slippage_bps,
        derivation_basis=request.review_payload.derivation.baseline_basis,
        candidate_construction_rule=request.review_payload.derivation.candidate_construction_rule,
        replay_provenance=request.review_payload.replay_provenance,
    )
    truth_labels = ReviewSnapshotArtifactTruthLabels()
    compact_summary = ReviewSnapshotArtifactCompactSummary(
        replay_type=replay_type,
        replay_status=active_replay.candidate_result.status,
        investor_economics_status=active_replay.investor_economics_status,
        candidate_analytics=_build_review_snapshot_analytics_summary(active_replay, role="candidate"),
        baseline_analytics=_build_review_snapshot_analytics_summary(active_replay, role="baseline") if active_replay.reference_result is not None else None,
        analytics_comparison=active_replay.comparison,
        diagnostics_summary=diagnostics_summary,
    )
    artifact = ReviewSnapshotArtifact(
        identity=ReviewSnapshotArtifactIdentity(
            artifact_id="review_snapshot_pending",
            fingerprint="pending",
        ),
        lineage=lineage,
        review_basis=review_basis,
        truth_labels=truth_labels,
        compact_summary=compact_summary,
        proposal_capture=_build_review_snapshot_proposal_capture(
            lineage=lineage,
            review_payload=request.review_payload,
            review_basis=review_basis,
            replay_type=replay_type,
        ),
        pm_summary=_build_review_snapshot_pm_summary(
            lineage=lineage,
            review_basis=review_basis,
            truth_labels=truth_labels,
            compact_summary=compact_summary,
            proposal_source=request.review_payload.proposal.proposal_source,
            role="saved_proposal",
        ),
        source_payload=ReviewSnapshotArtifactSourcePayload(
            replay_type=replay_type,
            replay=standard_payload,
            overlay_replay=overlay_payload,
        ),
    )
    stable_artifact = build_stable_review_snapshot_artifact(artifact)
    return persist_review_snapshot_artifact(stable_artifact, store=store)


def open_review_snapshot_artifact(
    handoff: ReviewSnapshotOpenHandoff,
    *,
    store=None,
) -> ReviewSnapshotOpenResponse:
    if handoff.handoff_kind != "review_snapshot_open_handoff_v1":
        raise ValueError(f"unsupported review snapshot handoff_kind: {handoff.handoff_kind}")
    artifact = load_review_snapshot_artifact(handoff.artifact_id, store=store)
    return ReviewSnapshotOpenResponse(
        handoff=handoff,
        artifact=artifact,
        pm_summary=artifact.pm_summary,
        replay_payload=artifact.source_payload,
    )


def compare_review_snapshots(
    request: ReviewSnapshotComparisonRequest,
    *,
    store=None,
) -> ReviewSnapshotComparisonResponse:
    baseline_artifact = _resolve_review_snapshot_comparison_artifact(request.baseline, expected_role="baseline", store=store)
    candidate_artifact = _resolve_review_snapshot_comparison_artifact(request.candidate, expected_role="candidate", store=store)
    _validate_review_snapshot_comparison_pair(baseline_artifact, candidate_artifact)
    baseline_replay = _active_replay_from_review_snapshot_payload(_required_review_snapshot_payload(baseline_artifact))
    candidate_replay = _active_replay_from_review_snapshot_payload(_required_review_snapshot_payload(candidate_artifact))
    return ReviewSnapshotComparisonResponse(
        family_key=_review_snapshot_family_key_from_artifact(baseline_artifact),
        baseline=_build_review_snapshot_comparison_pair_summary(baseline_artifact, role="baseline"),
        candidate=_build_review_snapshot_comparison_pair_summary(candidate_artifact, role="candidate"),
        baseline_pm_summary=_review_snapshot_pm_summary_for_role(baseline_artifact, role="baseline"),
        candidate_pm_summary=_review_snapshot_pm_summary_for_role(candidate_artifact, role="candidate"),
        analytics_comparison=_compare_review_snapshot_candidate_results(
            baseline_replay.candidate_result,
            candidate_replay.candidate_result,
        ),
        methodology=ReviewSnapshotComparisonMethodologyEnvelope(
            baseline_methodology=_build_review_snapshot_comparison_methodology(baseline_replay),
            candidate_methodology=_build_review_snapshot_comparison_methodology(candidate_replay),
            assumptions_consistent=baseline_replay.candidate_result.assumptions == candidate_replay.candidate_result.assumptions,
            methodology_consistent=baseline_replay.methodology == candidate_replay.methodology,
        ),
        assumptions=ReviewSnapshotComparisonAssumptionsEnvelope(
            baseline_assumptions=baseline_replay.candidate_result.assumptions,
            candidate_assumptions=candidate_replay.candidate_result.assumptions,
            assumptions_consistent=baseline_replay.candidate_result.assumptions == candidate_replay.candidate_result.assumptions,
        ),
    )


def build_review_snapshot_family_review(
    request: ReviewSnapshotFamilyReviewRequest,
    *,
    store=None,
) -> ReviewSnapshotFamilyReviewResponse:
    anchor_artifact = open_review_snapshot_artifact(request.handoff, store=store).artifact
    family_key = _review_snapshot_family_key_from_artifact(anchor_artifact)
    family_artifacts = [
        artifact
        for artifact in list_review_snapshot_artifacts(store=store)
        if _review_snapshot_family_key_from_artifact(artifact) == family_key
    ]
    sibling_summaries = [
        _build_review_snapshot_family_sibling_summary(
            artifact,
            compatible_sibling_artifact_ids=[
                candidate.identity.artifact_id
                for candidate in family_artifacts
                if candidate.identity.artifact_id != artifact.identity.artifact_id
                and _review_snapshot_artifacts_are_comparable(artifact, candidate)
            ],
        )
        for artifact in sorted(
            family_artifacts,
            key=lambda artifact: (artifact.lineage.version_number, artifact.identity.artifact_id),
            reverse=True,
        )
    ]
    anchor_summary = next(
        sibling for sibling in sibling_summaries if sibling.identity.artifact_id == anchor_artifact.identity.artifact_id
    )
    return ReviewSnapshotFamilyReviewResponse(
        family_key=family_key,
        anchor=anchor_summary,
        siblings=sibling_summaries,
    )


def build_review_snapshot_family_inbox(
    request: ReviewSnapshotFamilyInboxRequest,
    *,
    store=None,
) -> ReviewSnapshotFamilyInboxResponse:
    active_store = store or ReviewSnapshotArtifactStore()
    family_members: dict[
        tuple[str, str, str, str, Literal["hypothetical_replacement_replay"]],
        list[tuple[ReviewSnapshotArtifact, float, str]],
    ] = {}
    for artifact, artifact_path in _list_review_snapshot_artifacts_with_paths(store=active_store):
        family_key = _review_snapshot_family_key_from_artifact(artifact)
        if family_key.workspace_id != request.workspace_id:
            continue
        family_members.setdefault(_review_snapshot_family_sort_key(family_key), []).append(
            (artifact, artifact_path.stat().st_mtime, artifact_path.as_posix())
        )

    rows = [
        _build_review_snapshot_family_inbox_row(family_key=_family_key_from_tuple(family_key), family_members=members)
        for family_key, members in family_members.items()
    ]
    rows.sort(key=lambda row: (row.latest_saved_at, row.latest_identity.artifact_id), reverse=True)
    return ReviewSnapshotFamilyInboxResponse(
        workspace_id=request.workspace_id,
        rows=rows,
    )


def build_review_snapshot_active_thesis_cross_family_queue(
    request: ReviewSnapshotActiveThesisCrossFamilyQueueRequest,
    *,
    store=None,
) -> ReviewSnapshotActiveThesisCrossFamilyQueueResponse:
    active_store = store or ReviewSnapshotArtifactStore()
    active_thesis_artifact = open_review_snapshot_artifact(request.handoff, store=active_store).artifact
    if active_thesis_artifact.lineage.proposal_id != request.source_proposal_id:
        raise ValueError("review snapshot active thesis cross-family queue source_proposal_id does not match persisted artifact lineage")
    active_family_key = _review_snapshot_family_key_from_artifact(active_thesis_artifact)

    family_members: dict[
        tuple[str, str, str, str, Literal["hypothetical_replacement_replay"]],
        list[tuple[ReviewSnapshotArtifact, float, str]],
    ] = {}
    for artifact, artifact_path in _list_review_snapshot_artifacts_with_paths(store=active_store):
        family_key = _review_snapshot_family_key_from_artifact(artifact)
        if family_key.workspace_id != active_family_key.workspace_id:
            continue
        if family_key.source_draft_id != active_family_key.source_draft_id:
            continue
        if family_key.source_base_node_id != active_family_key.source_base_node_id:
            continue
        if family_key.source_kind != active_family_key.source_kind:
            continue
        if family_key.proposal_family_id == active_family_key.proposal_family_id:
            continue
        family_members.setdefault(_review_snapshot_family_sort_key(family_key), []).append(
            (artifact, artifact_path.stat().st_mtime, artifact_path.as_posix())
        )

    rows = [
        _build_review_snapshot_active_thesis_cross_family_queue_row(
            active_thesis=active_thesis_artifact,
            family_key=_family_key_from_tuple(cast(tuple[str, str, str, str, Literal["hypothetical_replacement_replay"]], family_key)),
            family_members=members,
        )
        for family_key, members in family_members.items()
    ]
    rows.sort(key=lambda row: (row.latest_saved_at, row.latest_identity.artifact_id), reverse=True)
    return ReviewSnapshotActiveThesisCrossFamilyQueueResponse(
        active_thesis=ReviewSnapshotActiveThesisCrossFamilyQueueActiveThesis(
            source_proposal_id=request.source_proposal_id,
            handoff=request.handoff,
            identity=active_thesis_artifact.identity,
            lineage=active_thesis_artifact.lineage,
            family_key=active_family_key,
        ),
        rows=rows,
    )


def _build_review_snapshot_analytics_summary(
    replay: PortfolioAllocationBacktestResponse,
    *,
    role: Literal["baseline", "candidate"],
) -> ReviewSnapshotArtifactAnalyticsSummary:
    result = replay.reference_result if role == "baseline" else replay.candidate_result
    if result is None:
        raise ValueError("review snapshot baseline analytics summary requires reference_result")
    return ReviewSnapshotArtifactAnalyticsSummary(
        methodology=replay.methodology,
        methodology_provenance=replay.methodology_provenance,
        assumptions=result.assumptions,
        benchmark_symbol=result.benchmark_symbol,
        benchmark_return_pct=result.metrics.benchmark_return_pct,
        total_return_pct=result.metrics.total_return_pct,
        annualized_return_pct=result.metrics.annualized_return_pct,
        annualized_volatility_pct=result.metrics.annualized_volatility_pct,
        downside_volatility_pct=result.metrics.downside_volatility_pct,
        max_drawdown_pct=result.metrics.max_drawdown_pct,
        sharpe_ratio=result.metrics.sharpe_ratio,
        sortino_ratio=result.metrics.sortino_ratio,
        excess_return_pct=result.metrics.excess_return_pct,
        tracking_error_pct=result.metrics.tracking_error_pct,
        information_ratio=result.metrics.information_ratio,
        beta_vs_benchmark=result.metrics.beta_vs_benchmark,
        correlation_vs_benchmark=result.metrics.correlation_vs_benchmark,
        total_turnover_pct=result.metrics.total_turnover_pct,
        total_cost_paid=result.metrics.total_cost_paid,
    )


def _build_review_snapshot_diagnostics_summary(
    diagnostics_comparison: PortfolioImprovementComparison | None,
) -> ReviewSnapshotArtifactDiagnosticsSummary:
    return ReviewSnapshotArtifactDiagnosticsSummary(
        diagnostics_available=diagnostics_comparison is not None,
        top_factor_exposure_change=diagnostics_comparison.top_factor_exposure_change if diagnostics_comparison else None,
        top_volatility_change=diagnostics_comparison.top_volatility_change if diagnostics_comparison else None,
        top_risk_contribution_change=diagnostics_comparison.top_risk_contribution_change if diagnostics_comparison else None,
        top_concentration_change=diagnostics_comparison.top_concentration_change if diagnostics_comparison else None,
        top_stress_scenario_change=diagnostics_comparison.top_stress_scenario_change if diagnostics_comparison else None,
    )


def _build_review_snapshot_pm_summary(
    *,
    lineage: ReviewSnapshotArtifactLineage,
    review_basis: ReviewSnapshotArtifactReviewBasis,
    truth_labels: ReviewSnapshotArtifactTruthLabels,
    compact_summary: ReviewSnapshotArtifactCompactSummary,
    proposal_source,
    role: Literal["saved_proposal", "baseline", "candidate"],
) -> ReviewSnapshotPMSummaryEnvelope:
    return ReviewSnapshotPMSummaryEnvelope(
        role=role,
        provenance=ReviewSnapshotPMSummaryProvenance(
            lineage=lineage,
            proposal_source=proposal_source,
            replay_provenance=review_basis.replay_provenance,
        ),
        truth_labels=truth_labels,
        replay_type=compact_summary.replay_type,
        replay_status=compact_summary.replay_status,
        investor_economics_status=compact_summary.investor_economics_status,
        review_basis=ReviewSnapshotPMSummaryReviewBasis(
            benchmark_symbol=review_basis.benchmark_symbol,
            replay_window=WorkspaceReviewWindow(
                start_date=review_basis.start_date,
                end_date=review_basis.end_date,
            ),
            rebalance_frequency=review_basis.rebalance_frequency,
            commission_bps=review_basis.commission_bps,
            slippage_bps=review_basis.slippage_bps,
            derivation_basis=review_basis.derivation_basis,
            candidate_construction_rule=review_basis.candidate_construction_rule,
        ),
        methodology=ReviewSnapshotPMSummaryMethodology(
            methodology=compact_summary.candidate_analytics.methodology,
            methodology_provenance=compact_summary.candidate_analytics.methodology_provenance,
        ),
        assumptions=compact_summary.candidate_analytics.assumptions,
        analytics_summary=ReviewSnapshotPMSummaryAnalyticsSummary(
            candidate_analytics=compact_summary.candidate_analytics,
            baseline_analytics=compact_summary.baseline_analytics,
            analytics_comparison=compact_summary.analytics_comparison,
        ),
        diagnostics_summary=compact_summary.diagnostics_summary,
    )


def _build_review_snapshot_proposal_capture(
    *,
    lineage: ReviewSnapshotArtifactLineage,
    review_payload: HypotheticalReplacementReplayResponse | OverlayAwareHypotheticalReplayResponse,
    review_basis: ReviewSnapshotArtifactReviewBasis,
    replay_type: Literal["standard", "overlay_aware"],
) -> ReviewSnapshotProposalCapture:
    return ReviewSnapshotProposalCapture(
        open_handoff=ReviewSnapshotOpenHandoff(
            artifact_id="review_snapshot_pending",
        ),
        lineage=lineage,
        proposal=ReviewSnapshotProposalCaptureProposal(
            source=review_payload.proposal.source,
            proposal_source=review_payload.proposal.proposal_source,
            incumbent_symbol=review_payload.proposal.incumbent_symbol,
            candidate_symbol=review_payload.proposal.candidate_symbol,
        ),
        replay_type=replay_type,
        replay_provenance=review_payload.replay_provenance,
        review_basis=ReviewSnapshotProposalCaptureReviewBasis(
            benchmark_symbol=review_basis.benchmark_symbol,
            replay_window=WorkspaceReviewWindow(
                start_date=review_basis.start_date,
                end_date=review_basis.end_date,
            ),
            rebalance_frequency=review_basis.rebalance_frequency,
            commission_bps=review_basis.commission_bps,
            slippage_bps=review_basis.slippage_bps,
            derivation_basis=review_basis.derivation_basis,
            candidate_construction_rule=review_basis.candidate_construction_rule,
        ),
    )


def _review_snapshot_pm_summary_for_role(
    artifact: ReviewSnapshotArtifact,
    *,
    role: Literal["baseline", "candidate"],
) -> ReviewSnapshotPMSummaryEnvelope:
    return artifact.pm_summary.model_copy(update={"role": role})


def _build_review_snapshot_family_key(
    *,
    workspace_id: object,
    source_draft_id: object,
    source_base_node_id: object,
    proposal_family_id: object,
    source_kind: object,
    context: str,
) -> ReviewSnapshotFamilyKey:
    try:
        return ReviewSnapshotFamilyKey.model_validate(
            {
                "workspace_id": workspace_id,
                "source_draft_id": source_draft_id,
                "source_base_node_id": source_base_node_id,
                "proposal_family_id": proposal_family_id,
                "source_kind": source_kind,
            }
        )
    except ValidationError as exc:
        message = exc.errors()[0]["msg"]
        if message.startswith("Value error, "):
            message = message.removeprefix("Value error, ")
        raise ValueError(f"{context} family_key is invalid: {message}") from exc


def _assert_review_snapshot_family_key_matches_lineage(
    family_key: ReviewSnapshotFamilyKey,
    lineage: ReviewSnapshotArtifactLineage,
    *,
    context: str,
) -> None:
    if lineage.workspace_id != family_key.workspace_id:
        raise ValueError(f"{context} workspace_id does not match family_key")
    if lineage.source_draft_id != family_key.source_draft_id:
        raise ValueError(f"{context} source_draft_id does not match family_key")
    if lineage.source_base_node_id != family_key.source_base_node_id:
        raise ValueError(f"{context} source_base_node_id does not match family_key")
    if lineage.proposal_family_id != family_key.proposal_family_id:
        raise ValueError(f"{context} proposal_family_id does not match family_key")
    if lineage.source_kind != family_key.source_kind:
        raise ValueError(f"{context} source_kind does not match family_key")


def _review_snapshot_family_key_from_artifact(
    artifact: ReviewSnapshotArtifact,
) -> ReviewSnapshotFamilyKey:
    family_key = _build_review_snapshot_family_key(
        workspace_id=artifact.lineage.workspace_id,
        source_draft_id=artifact.lineage.source_draft_id,
        source_base_node_id=artifact.lineage.source_base_node_id,
        proposal_family_id=artifact.lineage.proposal_family_id,
        source_kind=artifact.lineage.source_kind,
        context="review snapshot artifact lineage",
    )
    _assert_review_snapshot_family_key_matches_lineage(
        family_key,
        artifact.lineage,
        context="review snapshot artifact lineage",
    )
    _assert_review_snapshot_family_key_matches_lineage(
        family_key,
        artifact.pm_summary.provenance.lineage,
        context="review snapshot artifact pm_summary provenance lineage",
    )
    _assert_review_snapshot_family_key_matches_lineage(
        family_key,
        artifact.proposal_capture.lineage,
        context="review snapshot artifact proposal_capture lineage",
    )
    return family_key


def _review_snapshot_family_sort_key(
    family_key: ReviewSnapshotFamilyKey,
) -> tuple[str, str, str, str, Literal["hypothetical_replacement_replay"]]:
    return (
        family_key.workspace_id,
        family_key.source_draft_id,
        family_key.source_base_node_id,
        family_key.proposal_family_id,
        family_key.source_kind,
    )


def _family_key_from_tuple(
    value: tuple[str, str, str, str, Literal["hypothetical_replacement_replay"]],
) -> ReviewSnapshotFamilyKey:
    return _build_review_snapshot_family_key(
        workspace_id=value[0],
        source_draft_id=value[1],
        source_base_node_id=value[2],
        proposal_family_id=value[3],
        source_kind=value[4],
        context="review snapshot family grouping",
    )


def _build_review_snapshot_family_inbox_row(
    *,
    family_key: ReviewSnapshotFamilyKey,
    family_members: list[tuple[ReviewSnapshotArtifact, float, str]],
) -> ReviewSnapshotFamilyInboxRow:
    if not family_members:
        raise ValueError("review snapshot family inbox row requires at least one persisted family member")
    latest_artifact, latest_saved_at = _select_review_snapshot_family_latest_artifact(family_key=family_key, family_members=family_members)
    comparable_pair_count = _count_review_snapshot_family_compatible_pairs([artifact for artifact, _, _ in family_members])
    compare_readiness = ReviewSnapshotFamilyCompareReadiness(
        ready=comparable_pair_count > 0,
        reason="compatible_family_pair_available" if comparable_pair_count > 0 else "no_compatible_family_pair",
        compatible_pair_count=comparable_pair_count,
    )
    return ReviewSnapshotFamilyInboxRow(
        family_key=family_key,
        latest_identity=latest_artifact.identity,
        lineage=latest_artifact.lineage,
        proposal_capture=latest_artifact.proposal_capture,
        pm_summary=latest_artifact.pm_summary,
        sibling_count=len(family_members),
        compare_readiness=compare_readiness,
        latest_saved_at=latest_saved_at,
    )


def _build_review_snapshot_active_thesis_cross_family_queue_row(
    *,
    active_thesis: ReviewSnapshotArtifact,
    family_key: ReviewSnapshotFamilyKey,
    family_members: list[tuple[ReviewSnapshotArtifact, float, str]],
) -> ReviewSnapshotActiveThesisCrossFamilyQueueRow:
    latest_artifact, latest_saved_at = _select_review_snapshot_family_latest_artifact(
        family_key=family_key,
        family_members=family_members,
    )
    _validate_review_snapshot_cross_family_queue_candidate(active_thesis=active_thesis, candidate=latest_artifact)
    return ReviewSnapshotActiveThesisCrossFamilyQueueRow(
        latest_identity=latest_artifact.identity,
        lineage=latest_artifact.lineage,
        family_key=family_key,
        family_separation=ReviewSnapshotActiveThesisCrossFamilySeparation(
            active_thesis_proposal_family_id=active_thesis.lineage.proposal_family_id,
            queue_proposal_family_id=latest_artifact.lineage.proposal_family_id,
        ),
        proposal_source=latest_artifact.pm_summary.provenance.proposal_source,
        truth_labels=latest_artifact.pm_summary.truth_labels,
        trust_visibility=ReviewSnapshotActiveThesisCrossFamilyTrustVisibility(
            investor_economics_status=latest_artifact.pm_summary.investor_economics_status,
        ),
        pm_summary_fields=ReviewSnapshotActiveThesisCrossFamilyPMSummaryFields(
            replay_type=latest_artifact.pm_summary.replay_type,
            replay_status=latest_artifact.pm_summary.replay_status,
            review_basis=latest_artifact.pm_summary.review_basis,
            methodology=latest_artifact.pm_summary.methodology,
            assumptions=latest_artifact.pm_summary.assumptions,
            analytics_summary=latest_artifact.pm_summary.analytics_summary,
            diagnostics_summary=latest_artifact.pm_summary.diagnostics_summary,
        ),
        latest_saved_at=latest_saved_at,
    )


def _select_review_snapshot_family_latest_artifact(
    *,
    family_key: ReviewSnapshotFamilyKey,
    family_members: list[tuple[ReviewSnapshotArtifact, float, str]],
) -> tuple[ReviewSnapshotArtifact, str]:
    if len(family_members) == 1:
        artifact, mtime, _ = family_members[0]
        return artifact, _review_snapshot_saved_at_from_mtime(mtime)
    sorted_members = sorted(
        family_members,
        key=lambda item: (item[0].lineage.version_number, item[1], item[0].identity.artifact_id),
        reverse=True,
    )
    latest_artifact, latest_mtime, _ = sorted_members[0]
    second_artifact, second_mtime, _ = sorted_members[1]
    if latest_artifact.lineage.version_number == second_artifact.lineage.version_number:
        raise ValueError(
            f"review snapshot family inbox latest selection is ambiguous for family {family_key.proposal_family_id}"
        )
    if any(
        artifact.lineage.version_number == latest_artifact.lineage.version_number and artifact.identity.artifact_id != latest_artifact.identity.artifact_id
        for artifact, _, _ in family_members
    ):
        raise ValueError(
            f"review snapshot family inbox latest selection is ambiguous for family {family_key.proposal_family_id}"
        )
    if latest_mtime < second_mtime and latest_artifact.lineage.version_number > second_artifact.lineage.version_number:
        raise ValueError(
            f"review snapshot family inbox latest selection contradicts persisted ordering for family {family_key.proposal_family_id}"
        )
    return latest_artifact, _review_snapshot_saved_at_from_mtime(latest_mtime)


def _validate_review_snapshot_cross_family_queue_candidate(
    *,
    active_thesis: ReviewSnapshotArtifact,
    candidate: ReviewSnapshotArtifact,
) -> None:
    if candidate.identity.artifact_id == active_thesis.identity.artifact_id:
        raise ValueError("review snapshot active thesis cross-family queue requires distinct persisted artifacts")
    if candidate.lineage.workspace_id != active_thesis.lineage.workspace_id:
        raise ValueError("review snapshot active thesis cross-family queue requires matching workspace_id")
    if candidate.lineage.source_draft_id != active_thesis.lineage.source_draft_id:
        raise ValueError("review snapshot active thesis cross-family queue requires matching source_draft_id")
    if candidate.lineage.source_base_node_id != active_thesis.lineage.source_base_node_id:
        raise ValueError("review snapshot active thesis cross-family queue requires matching source_base_node_id")
    if candidate.lineage.source_kind != active_thesis.lineage.source_kind:
        raise ValueError("review snapshot active thesis cross-family queue requires matching source_kind")
    if candidate.lineage.proposal_family_id == active_thesis.lineage.proposal_family_id:
        raise ValueError("review snapshot active thesis cross-family queue requires distinct proposal_family_id")
    if candidate.lineage.proposal_id == active_thesis.lineage.proposal_id:
        raise ValueError("review snapshot active thesis cross-family queue requires distinct proposal_id")
    if candidate.pm_summary.role != "saved_proposal":
        raise ValueError("review snapshot active thesis cross-family queue requires saved_proposal pm_summary role")
    if candidate.pm_summary.provenance.lineage != candidate.lineage:
        raise ValueError("review snapshot active thesis cross-family queue candidate lineage does not match pm_summary provenance lineage")


def _count_review_snapshot_family_compatible_pairs(family_artifacts: list[ReviewSnapshotArtifact]) -> int:
    compatible_pair_count = 0
    for index, baseline in enumerate(family_artifacts):
        for candidate in family_artifacts[index + 1:]:
            if _review_snapshot_artifacts_are_comparable(baseline, candidate):
                compatible_pair_count += 1
    return compatible_pair_count


def _review_snapshot_saved_at_from_mtime(mtime: float) -> str:
    return datetime.fromtimestamp(mtime, tz=UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _list_review_snapshot_artifacts_with_paths(
    *,
    store: ReviewSnapshotArtifactStore,
) -> list[tuple[ReviewSnapshotArtifact, Path]]:
    artifacts_with_paths: list[tuple[ReviewSnapshotArtifact, Path]] = []
    for path in sorted(store.base_dir.glob("*.json")):
        artifact_id = path.stem
        artifacts_with_paths.append((load_review_snapshot_artifact(artifact_id, store=store), path))
    return artifacts_with_paths


def _build_review_snapshot_family_sibling_summary(
    artifact: ReviewSnapshotArtifact,
    *,
    compatible_sibling_artifact_ids: list[str],
) -> ReviewSnapshotFamilySiblingSummary:
    return ReviewSnapshotFamilySiblingSummary(
        identity=artifact.identity,
        open_handoff=artifact.proposal_capture.open_handoff,
        lineage=artifact.lineage,
        pm_summary=artifact.pm_summary,
        comparison_eligibility=ReviewSnapshotSiblingComparisonEligibility(
            eligible=len(compatible_sibling_artifact_ids) > 0,
            reason="compatible_family_sibling_available" if compatible_sibling_artifact_ids else "no_compatible_family_sibling",
            compatible_sibling_artifact_ids=compatible_sibling_artifact_ids,
        ),
    )


def _resolve_review_snapshot_comparison_artifact(
    value: ReviewSnapshotComparisonArtifactRef | ReviewSnapshotOpenHandoff,
    *,
    expected_role: Literal["baseline", "candidate"],
    store=None,
) -> ReviewSnapshotArtifact:
    if isinstance(value, ReviewSnapshotOpenHandoff):
        return open_review_snapshot_artifact(value, store=store).artifact
    if value.role != expected_role:
        raise ValueError(f"review snapshot comparison {expected_role} role is required")
    artifact = load_review_snapshot_artifact(value.artifact_id, store=store)
    if value.artifact_kind != artifact.identity.artifact_kind:
        raise ValueError(f"review snapshot comparison {expected_role} artifact_kind does not match persisted artifact")
    if value.schema_version != artifact.identity.schema_version:
        raise ValueError(f"review snapshot comparison {expected_role} schema_version does not match persisted artifact")
    if value.consumer_kind != artifact.identity.consumer_kind:
        raise ValueError(f"review snapshot comparison {expected_role} consumer_kind does not match persisted artifact")
    return artifact


def _validate_review_snapshot_comparison_pair(
    baseline: ReviewSnapshotArtifact,
    candidate: ReviewSnapshotArtifact,
) -> None:
    if baseline.identity.artifact_id == candidate.identity.artifact_id:
        raise ValueError("review snapshot comparison requires two distinct persisted artifacts")
    if baseline.lineage.proposal_family_id != candidate.lineage.proposal_family_id:
        raise ValueError("review snapshot comparison requires matching proposal_family_id")
    if baseline.lineage.workspace_id != candidate.lineage.workspace_id:
        raise ValueError("review snapshot comparison requires matching workspace_id")
    if baseline.lineage.source_draft_id != candidate.lineage.source_draft_id:
        raise ValueError("review snapshot comparison requires matching source_draft_id")
    if baseline.lineage.source_base_node_id != candidate.lineage.source_base_node_id:
        raise ValueError("review snapshot comparison requires matching source_base_node_id")
    if baseline.lineage.source_kind != candidate.lineage.source_kind:
        raise ValueError("review snapshot comparison requires matching source_kind")
    if baseline.review_basis.benchmark_symbol != candidate.review_basis.benchmark_symbol:
        raise ValueError("review snapshot comparison requires matching benchmark_symbol")
    if baseline.review_basis.start_date != candidate.review_basis.start_date or baseline.review_basis.end_date != candidate.review_basis.end_date:
        raise ValueError("review snapshot comparison requires matching replay_window")
    if baseline.review_basis.derivation_basis != candidate.review_basis.derivation_basis:
        raise ValueError("review snapshot comparison requires matching derivation_basis")
    if baseline.compact_summary.replay_type != candidate.compact_summary.replay_type:
        raise ValueError("review snapshot comparison requires matching replay_type")
    if baseline.compact_summary.candidate_analytics.assumptions != candidate.compact_summary.candidate_analytics.assumptions:
        raise ValueError("review snapshot comparison requires matching replay assumptions")


def _review_snapshot_artifacts_are_comparable(
    baseline: ReviewSnapshotArtifact,
    candidate: ReviewSnapshotArtifact,
) -> bool:
    try:
        _validate_review_snapshot_comparison_pair(baseline, candidate)
    except ValueError:
        return False
    return True


def _build_review_snapshot_comparison_methodology(
    replay: PortfolioAllocationBacktestResponse,
) -> ReviewSnapshotComparisonMethodology:
    return ReviewSnapshotComparisonMethodology(
        methodology=replay.methodology,
        methodology_provenance=replay.methodology_provenance,
        assumptions=replay.candidate_result.assumptions,
    )


def _build_review_snapshot_comparison_pair_summary(
    artifact: ReviewSnapshotArtifact,
    *,
    role: Literal["baseline", "candidate"],
) -> ReviewSnapshotComparisonPairSummary:
    return ReviewSnapshotComparisonPairSummary(
        benchmark_symbol=artifact.review_basis.benchmark_symbol,
        replay_window=WorkspaceReviewWindow(
            start_date=artifact.review_basis.start_date,
            end_date=artifact.review_basis.end_date,
        ),
        replay_type=artifact.compact_summary.replay_type,
        candidate_construction_rule=artifact.review_basis.candidate_construction_rule,
        derivation_basis=artifact.review_basis.derivation_basis,
        source_pair=f"{_source_pair_from_review_snapshot_artifact(artifact)}",
        replay_status=artifact.compact_summary.replay_status,
        investor_economics_status=artifact.compact_summary.investor_economics_status,
        methodology=_build_review_snapshot_comparison_methodology(
            _active_replay_from_review_snapshot_payload(
                _required_review_snapshot_payload(artifact)
            )
        ),
        analytics=artifact.compact_summary.candidate_analytics,
        diagnostics_summary=artifact.compact_summary.diagnostics_summary,
    )


def _compare_review_snapshot_candidate_results(
    baseline: AllocationBacktestResult,
    candidate: AllocationBacktestResult,
) -> AllocationBacktestComparison:
    return _compare_results(
        AllocationBacktestResult.model_validate(baseline.model_dump(mode="json")),
        AllocationBacktestResult.model_validate(candidate.model_dump(mode="json")),
    )


def _active_replay_from_review_snapshot_payload(
    payload: HypotheticalReplacementReplayResponse | OverlayAwareHypotheticalReplayResponse,
) -> PortfolioAllocationBacktestResponse:
    return payload.overlay_replay if isinstance(payload, OverlayAwareHypotheticalReplayResponse) else payload.replay


def _required_review_snapshot_payload(
    artifact: ReviewSnapshotArtifact,
) -> HypotheticalReplacementReplayResponse | OverlayAwareHypotheticalReplayResponse:
    payload = artifact.source_payload.overlay_replay or artifact.source_payload.replay
    if payload is None:
        raise ValueError("review snapshot artifact is missing authoritative source payload")
    return payload


def _source_pair_from_review_snapshot_artifact(artifact: ReviewSnapshotArtifact) -> str:
    payload = _required_review_snapshot_payload(artifact)
    return f"{payload.proposal.incumbent_symbol} -> {payload.proposal.candidate_symbol}"


def build_overlay_aware_hypothetical_replay_preview(request: OverlayAwareHypotheticalReplayRequest) -> OverlayAwareHypotheticalReplayResponse:
    if request.replacement_intent is None:
        raise ValueError("replacement_intent is required")
    if request.overlay_state is None:
        raise ValueError("overlay_state is required")
    if request.overlay_state.overlay_id != "benchmark_trend_overlay_v1":
        raise ValueError(f"unsupported overlay_id: {request.overlay_state.overlay_id}")
    if request.overlay_state.benchmark_symbol != request.benchmark_symbol:
        raise ValueError("overlay benchmark does not match replay benchmark")
    if request.overlay_state.status == "unavailable":
        raise ValueError("overlay_state status unavailable is not replayable")
    if request.overlay_state.status == "unconfirmed":
        raise ValueError("overlay_state status unconfirmed is not replayable")

    base_request = HypotheticalReplacementReplayRequest(
        snapshot=request.snapshot,
        replacement_intent=request.replacement_intent,
        constructed_candidate=request.constructed_candidate,
        constraint_validation=request.constraint_validation,
        benchmark_symbol=request.benchmark_symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        rebalance_frequency=request.rebalance_frequency,
        base_currency=request.base_currency,
        commission_bps=request.commission_bps,
        slippage_bps=request.slippage_bps,
        drift_tolerance_pct=request.drift_tolerance_pct,
        price_basis=request.price_basis,
        execution_price_field=request.execution_price_field,
        execution_lag_days=request.execution_lag_days,
        symbol_overrides=request.symbol_overrides,
    )
    replay_provenance = _build_hypothetical_replay_provenance(base_request)
    baseline_weights, candidate_weights_pre_overlay = _resolve_hypothetical_replay_weights(base_request)
    candidate_weights_post_overlay, overlay_application = _apply_overlay_to_candidate_weights(candidate_weights_pre_overlay, request.overlay_state)

    base_replay = build_portfolio_allocation_backtest_analysis(
        PortfolioAllocationBacktestRequest(
            portfolio_name="Hypothetical Candidate",
            weights=candidate_weights_pre_overlay,
            reference_weights=baseline_weights,
            benchmark_symbol=request.benchmark_symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            rebalance_frequency=request.rebalance_frequency,
            base_currency=request.base_currency,
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
            drift_tolerance_pct=request.drift_tolerance_pct,
            price_basis=request.price_basis,
            execution_price_field=request.execution_price_field,
            execution_lag_days=request.execution_lag_days,
            symbol_overrides=request.symbol_overrides,
        )
    )
    overlay_replay = build_portfolio_allocation_backtest_analysis(
        PortfolioAllocationBacktestRequest(
            portfolio_name="Hypothetical Candidate Overlay-Aware",
            weights=candidate_weights_post_overlay,
            reference_weights=baseline_weights,
            benchmark_symbol=request.benchmark_symbol,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            rebalance_frequency=request.rebalance_frequency,
            base_currency=request.base_currency,
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
            drift_tolerance_pct=request.drift_tolerance_pct,
            price_basis=request.price_basis,
            execution_price_field=request.execution_price_field,
            execution_lag_days=request.execution_lag_days,
            symbol_overrides=request.symbol_overrides,
        )
    )

    return OverlayAwareHypotheticalReplayResponse(
        proposal=HypotheticalReplayProposal(
            source="draft_replacement_intent",
            incumbent_symbol=request.replacement_intent.base_symbol,
            candidate_symbol=request.replacement_intent.candidate_symbol,
            draft_id=request.replacement_intent.draft_id,
            base_node_id=request.replacement_intent.base_node_id,
        ),
        derivation=HypotheticalReplayDerivation(
            baseline_basis="draft_snapshot_positions_normalized",
            candidate_construction_rule=replay_provenance.construction_rule_id,
        ),
        replay_provenance=replay_provenance,
        overlay_application=overlay_application,
        baseline_weights=baseline_weights,
        candidate_weights_pre_overlay=candidate_weights_pre_overlay,
        candidate_weights_post_overlay=candidate_weights_post_overlay,
        base_replay=base_replay,
        overlay_replay=overlay_replay,
        warnings=_build_overlay_aware_hypothetical_replay_warnings(request.snapshot, overlay_application.cash_residual_weight),
    )


def evaluate_monitor_definition_observation(
    monitor_definition_id: str,
    request: EvaluateMonitorDefinitionObservationRequest,
    *,
    artifact_store=None,
) -> MonitorDefinitionObservationEvaluationResponse:
    artifact = load_monitor_definition_artifact(monitor_definition_id, store=artifact_store)
    benchmark_observation = request.benchmark_observation
    canonical_portfolio_source_path = _canonical_monitor_portfolio_source_path(request.current_portfolio)
    if artifact.monitor_id != "benchmark_trend_overlay_v1":
        raise ValueError(f"unsupported monitor_id: {artifact.monitor_id}")
    if benchmark_observation.overlay_id != artifact.monitor_id:
        raise ValueError("benchmark observation overlay_id does not match monitor definition")
    if benchmark_observation.benchmark_symbol.strip().upper() != artifact.benchmark_symbol:
        raise ValueError("benchmark observation benchmark_symbol does not match monitor definition")
    if benchmark_observation.source_lineage.source_kind != artifact.source_lineage_requirements.benchmark_source_kind:
        raise ValueError("benchmark observation source_lineage.source_kind is unsupported")
    if benchmark_observation.status == "unconfirmed" and benchmark_observation.confirmation_count >= artifact.thresholds.minimum_confirmation_count:
        raise ValueError("benchmark observation status unconfirmed contradicts confirmation_count")
    if benchmark_observation.status in {"risk_on", "risk_reduced"} and benchmark_observation.confirmation_count < artifact.thresholds.minimum_confirmation_count:
        raise ValueError("benchmark observation confirmation_count does not meet monitor threshold")

    portfolio_observation = _build_monitor_portfolio_observation(request.current_portfolio)
    if portfolio_observation.total_portfolio_value <= 0:
        response = MonitorDefinitionObservationEvaluationResponse(
            monitor_definition_id=artifact.monitor_definition_id,
            monitor_id=artifact.monitor_id,
            benchmark_symbol=artifact.benchmark_symbol,
            observation_status="unavailable",
            cause_code="portfolio_truth_non_positive_total_value",
            reason="current portfolio truth has no positive market value or cash basis",
            thresholds=artifact.thresholds,
            benchmark_observation=benchmark_observation,
            portfolio_observation=portfolio_observation,
            active_observation=BenchmarkTrendOverlayMonitorActiveObservation(
                required_overlay_status=benchmark_observation.status,
                threshold_evaluation_performed=False,
            ),
        )
        _persist_monitor_definition_evaluation_snapshot(
            response,
            canonical_portfolio_source_path=canonical_portfolio_source_path,
            monitor_definition_fingerprint=artifact.fingerprint,
            artifact_store=artifact_store,
        )
        return response

    if benchmark_observation.status == "unavailable":
        response = MonitorDefinitionObservationEvaluationResponse(
            monitor_definition_id=artifact.monitor_definition_id,
            monitor_id=artifact.monitor_id,
            benchmark_symbol=artifact.benchmark_symbol,
            observation_status="unavailable",
            cause_code="benchmark_observation_unavailable",
            reason="benchmark observation is unavailable",
            thresholds=artifact.thresholds,
            benchmark_observation=benchmark_observation,
            portfolio_observation=portfolio_observation,
            active_observation=BenchmarkTrendOverlayMonitorActiveObservation(
                required_overlay_status=benchmark_observation.status,
                threshold_evaluation_performed=False,
            ),
        )
        _persist_monitor_definition_evaluation_snapshot(
            response,
            canonical_portfolio_source_path=canonical_portfolio_source_path,
            monitor_definition_fingerprint=artifact.fingerprint,
            artifact_store=artifact_store,
        )
        return response

    if benchmark_observation.status == "unconfirmed":
        response = MonitorDefinitionObservationEvaluationResponse(
            monitor_definition_id=artifact.monitor_definition_id,
            monitor_id=artifact.monitor_id,
            benchmark_symbol=artifact.benchmark_symbol,
            observation_status="degraded",
            cause_code="benchmark_observation_unconfirmed",
            reason="benchmark observation is unconfirmed",
            thresholds=artifact.thresholds,
            benchmark_observation=benchmark_observation,
            portfolio_observation=portfolio_observation,
            active_observation=BenchmarkTrendOverlayMonitorActiveObservation(
                required_overlay_status=benchmark_observation.status,
                threshold_evaluation_performed=False,
            ),
        )
        _persist_monitor_definition_evaluation_snapshot(
            response,
            canonical_portfolio_source_path=canonical_portfolio_source_path,
            monitor_definition_fingerprint=artifact.fingerprint,
            artifact_store=artifact_store,
        )
        return response

    active_observation = _build_monitor_active_observation(
        benchmark_observation=benchmark_observation,
        portfolio_observation=portfolio_observation,
        minimum_confirmation_count=artifact.thresholds.minimum_confirmation_count,
        thresholds=artifact.thresholds,
    )
    observation_status = "ok" if not active_observation.triggered_thresholds else "threshold_breach"
    reason = None if observation_status == "ok" else "current portfolio truth breaches canonical overlay thresholds"
    response = MonitorDefinitionObservationEvaluationResponse(
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        observation_status=observation_status,
        reason=reason,
        thresholds=artifact.thresholds,
        benchmark_observation=benchmark_observation,
        portfolio_observation=portfolio_observation,
        active_observation=active_observation,
    )
    _persist_monitor_definition_evaluation_snapshot(
        response,
        canonical_portfolio_source_path=canonical_portfolio_source_path,
        monitor_definition_fingerprint=artifact.fingerprint,
        artifact_store=artifact_store,
    )
    return response


def _persist_monitor_definition_evaluation_snapshot(
    response: MonitorDefinitionObservationEvaluationResponse,
    *,
    canonical_portfolio_source_path: str,
    monitor_definition_fingerprint: str,
    artifact_store=None,
) -> None:
    evaluated_at = datetime.now(UTC)
    significance_status = _latest_evaluation_significance_status(response.observation_status)
    previous_significance_status = None
    try:
        previous_snapshot = load_monitor_definition_latest_evaluation_snapshot(
            response.monitor_definition_id,
            expected_monitor_id=response.monitor_id,
            expected_benchmark_symbol=response.benchmark_symbol,
            store=artifact_store,
        )
    except MonitorDefinitionMissingFileError:
        previous_snapshot = None
    if previous_snapshot is not None:
        previous_significance_status = previous_snapshot.significance_status
    hysteresis_transition = _monitor_definition_hysteresis_transition(
        current_significance_status=significance_status,
        previous_significance_status=previous_significance_status,
    )
    observation = build_stable_monitor_definition_observation(
        MonitorDefinitionObservationArtifact(
            observation_id="monitor_definition_observation_pending",
            monitor_definition_id=response.monitor_definition_id,
            monitor_definition_fingerprint=monitor_definition_fingerprint,
            monitor_id=response.monitor_id,
            benchmark_symbol=response.benchmark_symbol,
            evaluated_at=evaluated_at,
            observation_status=response.observation_status,
            cause_code=response.cause_code,
            alert_classification=significance_status,
            hysteresis_transition=hysteresis_transition,
            source_precedence="persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry",
            reason=response.reason,
            thresholds=response.thresholds,
            benchmark_observation=response.benchmark_observation,
            portfolio_observation=response.portfolio_observation,
            active_observation=response.active_observation,
        )
    )
    latest_snapshot = MonitorDefinitionLatestEvaluationSnapshotArtifact(
        monitor_definition_id=response.monitor_definition_id,
        monitor_id=response.monitor_id,
        benchmark_symbol=response.benchmark_symbol,
        evaluated_at=evaluated_at,
        outcome_status=response.observation_status,
        cause_code=response.cause_code,
        significance_status=significance_status,
        hysteresis_transition=hysteresis_transition,
        source_precedence="persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact",
        benchmark_observation_lineage=MonitorDefinitionLatestEvaluationBenchmarkObservationLineage(
            source_id=response.benchmark_observation.source_lineage.source_id,
            observed_at=response.benchmark_observation.source_lineage.observed_at,
        ),
        portfolio_truth_basis=MonitorDefinitionLatestEvaluationPortfolioTruthBasis(
            importer=response.portfolio_observation.source_lineage.importer,
            imported_at=response.portfolio_observation.source_lineage.imported_at,
            source_path=canonical_portfolio_source_path,
            statement_period=response.portfolio_observation.source_lineage.statement_period,
        ),
    )

    history_entry = build_stable_monitor_definition_evaluation_history_entry(
        MonitorDefinitionEvaluationHistoryEntryArtifact(
            history_entry_id="monitor_definition_history_pending",
            monitor_definition_id=response.monitor_definition_id,
            monitor_definition_fingerprint=monitor_definition_fingerprint,
            monitor_id=response.monitor_id,
            benchmark_symbol=response.benchmark_symbol,
            evaluated_at=evaluated_at,
            observation_status=response.observation_status,
            cause_code=response.cause_code,
            significance_status=significance_status,
            hysteresis_transition=hysteresis_transition,
            source_precedence="persisted_evaluation_history_entry_only",
            reason=response.reason,
            thresholds=response.thresholds,
            benchmark_observation=response.benchmark_observation,
            portfolio_observation=response.portfolio_observation,
            active_observation=response.active_observation,
        )
    )

    persist_monitor_definition_evaluation_artifacts(
        observation,
        latest_snapshot,
        history_entry,
        store=artifact_store,
    )


def _latest_evaluation_significance_status(observation_status):
    if observation_status == "ok":
        return "informational"
    if observation_status == "threshold_breach":
        return "action_required"
    if observation_status == "degraded":
        return "degraded"
    return "unavailable"


def _monitor_definition_hysteresis_transition(
    *,
    current_significance_status: str,
    previous_significance_status: str | None,
) -> str:
    current_alert_eligible = current_significance_status != "informational"
    previous_alert_eligible = previous_significance_status != "informational" if previous_significance_status is not None else False
    if current_alert_eligible:
        return "remain_open" if previous_alert_eligible else "open"
    return "recover" if previous_alert_eligible else "no_op"


def _canonical_monitor_portfolio_source_path(snapshot: ImportedPortfolioSnapshot) -> str:
    statement_source_path = snapshot.statement.source_path.strip()
    if not statement_source_path:
        raise ValueError("current portfolio truth requires non-blank canonical imported snapshot root source_path")
    return statement_source_path


def _resolve_hypothetical_replay_weights(request: HypotheticalReplacementReplayRequest) -> tuple[list, list]:
    _validate_constraint_validation_lineage(request)
    constructed_candidate = request.constructed_candidate
    if constructed_candidate is None:
        if request.replacement_intent is None:
            raise ValueError("replacement_intent is required")
        construction = derive_same_weight_substitution_construction(request.snapshot, request.replacement_intent)
        return construction.baseline_weights, construction.candidate_weights

    if constructed_candidate.construction.status != "ok":
        raise ValueError("constructed_candidate must be ok before hypothetical replay can run")
    if constructed_candidate.construction.rule_id not in {"same_weight_substitution_v1", "fixed_split_50_50_substitution_v2"}:
        raise ValueError("constructed_candidate rule_id is unsupported")
    if request.replacement_intent is None:
        raise ValueError("replacement_intent is required")
    if constructed_candidate.proposal.incumbent_symbol != request.replacement_intent.base_symbol:
        raise ValueError("constructed_candidate incumbent does not match replacement_intent")
    if constructed_candidate.proposal.candidate_symbol != request.replacement_intent.candidate_symbol:
        raise ValueError("constructed_candidate candidate does not match replacement_intent")
    if constructed_candidate.rejection_reason is not None:
        raise ValueError("constructed_candidate must not include a rejection_reason when status is ok")

    baseline_weights = constructed_candidate.inputs.baseline_weights
    candidate_weights = constructed_candidate.outputs.candidate_weights
    if not baseline_weights:
        raise ValueError("constructed_candidate baseline weights are required")
    if not candidate_weights:
        raise ValueError("constructed_candidate candidate weights are required")
    return baseline_weights, candidate_weights


def _portfolio_weight_inputs_from_optimizer_weights(weights) -> list[PortfolioWeightInput]:
    return [
        PortfolioWeightInput(symbol=item.symbol.upper(), target_weight=item.weight)
        for item in weights
        if item.weight > 0
    ]


def _portfolio_weight_inputs_from_construction_weights(weights) -> list[PortfolioWeightInput]:
    return [
        PortfolioWeightInput(symbol=item.symbol.upper(), target_weight=item.weight)
        for item in weights
        if item.weight > 0
    ]


def _build_optimizer_handoff_context(artifact) -> OptimizerHandoffReplayOptimizerContext:
    return OptimizerHandoffReplayOptimizerContext(
        objective=artifact.objective,
        penalty_ids=[penalty.penalty_id for penalty in artifact.penalties],
        artifact_state=artifact.artifact_state.artifact_state,
        stale_inputs=artifact.artifact_state.stale_inputs,
        degraded_inputs=artifact.artifact_state.degraded_inputs,
        reasons=artifact.artifact_state.reasons,
        run_summary=OptimizerHandoffReplayOptimizerRunSummary(
            engine_id=artifact.run_metadata.engine_id,
            solver_id=artifact.run_metadata.solver_id,
            methodology_id=artifact.run_metadata.methodology_id,
            risk_package_id=artifact.run_metadata.risk_package_id,
            risk_package_version=artifact.run_metadata.risk_package_version,
            alpha_package_id=artifact.run_metadata.alpha_package_id,
            alpha_package_version=artifact.run_metadata.alpha_package_version,
        ),
        diagnostics=OptimizerHandoffReplayOptimizerDiagnostics(
            active_share=artifact.key_diagnostics.active_share,
            turnover=artifact.key_diagnostics.turnover,
            max_abs_active_weight=artifact.key_diagnostics.max_abs_active_weight,
            active_risk=artifact.key_diagnostics.active_risk,
            effective_holdings=artifact.key_diagnostics.effective_holdings,
            current_to_proposed_l2=artifact.key_diagnostics.current_to_proposed_l2,
            benchmark_to_proposed_l2=artifact.key_diagnostics.benchmark_to_proposed_l2,
            risk_package_coverage_ratio=artifact.key_diagnostics.risk_package_coverage_ratio,
            alpha_package_coverage_ratio=artifact.key_diagnostics.alpha_package_coverage_ratio,
        ),
        binding_constraints=artifact.feasibility.binding_constraints,
        violated_constraints=artifact.feasibility.violated_constraints,
        benchmark_relative_attestations=[
            OptimizerHandoffReplayBenchmarkAttestationSummary(
                attestation_id=item.attestation_id,
                attestation_type=item.attestation_type,
                status=item.status,
                actual_value=item.actual_value,
                limit_value=item.limit_value,
                slack=item.slack,
                message=item.message,
            )
            for item in artifact.benchmark_relative_attestations
        ],
        binding_constraint_evaluations=[
            OptimizerHandoffReplayConstraintSummary(
                constraint_id=item.constraint_id,
                status=item.status,
                actual_value=item.actual_value,
                limit_value=item.limit_value,
                slack=item.slack,
                message=item.message,
            )
            for item in artifact.constraint_evaluations
            if item.status == "binding"
        ],
    )


def _validate_constraint_validation_lineage(request: HypotheticalReplacementReplayRequest) -> None:
    constraint_validation = request.constraint_validation
    if constraint_validation is None:
        return

    constructed_candidate = request.constructed_candidate
    if constructed_candidate is None:
        raise ValueError("constraint_validation requires constructed_candidate")
    if constraint_validation.validation.constraint_set_id != "single_replacement_construction_constraints_v1":
        raise ValueError(f"constraint_validation constraint_set_id is unsupported: {constraint_validation.validation.constraint_set_id}")
    if constraint_validation.proposal.incumbent_symbol != constructed_candidate.proposal.incumbent_symbol:
        raise ValueError("constraint_validation incumbent does not match constructed_candidate proposal")
    if constraint_validation.proposal.candidate_symbol != constructed_candidate.proposal.candidate_symbol:
        raise ValueError("constraint_validation candidate does not match constructed_candidate proposal")
    if constraint_validation.construction.rule_id != constructed_candidate.construction.rule_id:
        raise ValueError("constraint_validation rule_id does not match constructed_candidate")
    if constraint_validation.construction.status != constructed_candidate.construction.status:
        raise ValueError("constraint_validation construction status does not match constructed_candidate")


def _resolve_supported_replay_construction_rule_id(constructed_candidate) -> Literal["same_weight_substitution_v1", "fixed_split_50_50_substitution_v2"]:
    if constructed_candidate is None:
        return "same_weight_substitution_v1"
    if constructed_candidate.construction.rule_id == "same_weight_substitution_v1":
        return "same_weight_substitution_v1"
    if constructed_candidate.construction.rule_id == "fixed_split_50_50_substitution_v2":
        return "fixed_split_50_50_substitution_v2"
    raise ValueError("constructed_candidate rule_id is unsupported")


def _build_hypothetical_replay_provenance(request: HypotheticalReplacementReplayRequest) -> HypotheticalReplayProvenance:
    if request.replacement_intent is None:
        raise ValueError("replacement_intent is required")

    _validate_constraint_validation_lineage(request)

    constructed_candidate = request.constructed_candidate
    construction_rule_id = _resolve_supported_replay_construction_rule_id(constructed_candidate)

    return HypotheticalReplayProvenance(
        candidate_input_source="constructed_candidate_payload" if constructed_candidate is not None else "replacement_intent_preview",
        construction_rule_id=construction_rule_id,
        upstream_ids=HypotheticalReplayUpstreamIds(
            draft_id=request.replacement_intent.draft_id,
            workspace_id=request.replacement_intent.workspace_id,
            base_node_id=request.replacement_intent.base_node_id,
        ),
        seed_ranking_id=request.replacement_intent.seed_ranking_id,
        seed_methodology_id=request.replacement_intent.seed_methodology_id,
        constraint_validation=HypotheticalReplayProvenance.ConstraintValidationLineage(
            supplied=request.constraint_validation is not None,
            validation_status=request.constraint_validation.validation.status if request.constraint_validation is not None else None,
            constraint_set_id=request.constraint_validation.validation.constraint_set_id if request.constraint_validation is not None else None,
        ),
    )


def _apply_overlay_to_candidate_weights(candidate_weights: list, overlay_state) -> tuple[list, OverlayApplicationSummary]:
    if overlay_state.status == "risk_on":
        return candidate_weights, OverlayApplicationSummary(
            overlay_id="benchmark_trend_overlay_v1",
            overlay_status="risk_on",
            as_of_month_end=overlay_state.as_of_month_end,
            benchmark_symbol=overlay_state.benchmark_symbol,
            risky_weight_scale=1.0,
            cash_residual_weight=0.0,
            applied_to_candidate_only=True,
        )

    scaled_weights = [type(item)(symbol=item.symbol, target_weight=round(item.target_weight * 0.35, 8)) for item in candidate_weights if item.symbol != CASH_SYMBOL]
    scaled_total = sum(item.target_weight for item in scaled_weights)
    cash_residual = round(1.0 - scaled_total, 8)
    if cash_residual < 0 or cash_residual > 1:
        raise ValueError("overlay cash residual is out of bounds")
    if cash_residual > 0:
        scaled_weights.append(type(candidate_weights[0])(symbol=CASH_SYMBOL, target_weight=cash_residual))
    total_weight = sum(item.target_weight for item in scaled_weights)
    if abs(total_weight - 1.0) > 0.000001:
        raise ValueError("overlay-adjusted candidate weights must preserve a total weight of 1.0")
    return scaled_weights, OverlayApplicationSummary(
        overlay_id="benchmark_trend_overlay_v1",
        overlay_status="risk_reduced",
        as_of_month_end=overlay_state.as_of_month_end,
        benchmark_symbol=overlay_state.benchmark_symbol,
        risky_weight_scale=0.35,
        cash_residual_weight=cash_residual,
        applied_to_candidate_only=True,
    )


def _build_overlay_aware_hypothetical_replay_warnings(snapshot, cash_residual_weight: float) -> list[str]:
    warnings = _build_hypothetical_replay_warnings(snapshot)
    warnings.append("Overlay-aware replay applies the benchmark trend overlay to the hypothetical candidate only.")
    if cash_residual_weight > 0:
        warnings.append("Overlay risk reduction allocates residual candidate weight to a synthetic cash sleeve.")
    return warnings


def _build_monitor_portfolio_observation(snapshot: ImportedPortfolioSnapshot) -> BenchmarkTrendOverlayMonitorPortfolioObservation:
    _validate_monitor_portfolio_snapshot(snapshot)
    risky_value = round(sum(position.market_value for position in snapshot.positions), 8)
    cash_value = round(sum((balance.ending_cash or 0.0) for balance in snapshot.cash_balances), 8)
    total_portfolio_value = round(risky_value + cash_value, 8)
    risky_weight = None
    cash_weight = None
    if total_portfolio_value > 0:
        risky_weight = round(risky_value / total_portfolio_value, 8)
        cash_weight = round(cash_value / total_portfolio_value, 8)
    source_paths = [statement.source_path for statement in snapshot.statements if statement.source_path]
    return BenchmarkTrendOverlayMonitorPortfolioObservation(
        total_portfolio_value=total_portfolio_value,
        risky_value=risky_value,
        cash_value=cash_value,
        risky_weight=risky_weight,
        cash_weight=cash_weight,
        position_count=len(snapshot.positions),
        source_lineage=CurrentPortfolioTruthLineage(
            importer=snapshot.statement.importer,
            imported_at=snapshot.statement.imported_at,
            statement_period=snapshot.statement.statement_period or "",
            source_paths=source_paths,
        ),
    )


def _validate_monitor_portfolio_snapshot(snapshot: ImportedPortfolioSnapshot) -> None:
    if not snapshot.statement.source_path:
        raise ValueError("current portfolio truth requires statement.source_path")
    if not snapshot.statement.statement_period:
        raise ValueError("current portfolio truth requires statement.statement_period")
    if any(position.market_value < 0 for position in snapshot.positions):
        raise ValueError("current portfolio truth must not include negative position market_value")
    if any((balance.ending_cash or 0.0) < 0 for balance in snapshot.cash_balances):
        raise ValueError("current portfolio truth must not include negative ending_cash")


def _build_monitor_active_observation(
    *,
    benchmark_observation: BenchmarkTrendOverlayMonitorBenchmarkObservationInput,
    portfolio_observation: BenchmarkTrendOverlayMonitorPortfolioObservation,
    minimum_confirmation_count: int,
    thresholds,
) -> BenchmarkTrendOverlayMonitorActiveObservation:
    if portfolio_observation.risky_weight is None or portfolio_observation.cash_weight is None:
        raise ValueError("current portfolio truth did not produce usable weights")
    if benchmark_observation.confirmation_count < minimum_confirmation_count:
        raise ValueError("benchmark observation confirmation_count does not meet monitor threshold")

    triggered_thresholds: list[MonitorThresholdTrigger] = []
    if benchmark_observation.status == "risk_on":
        _append_breach(
            triggered_thresholds,
            threshold_id="risk_on_min_risky_weight",
            operator=">=",
            threshold_value=thresholds.risk_on_min_risky_weight,
            actual_value=portfolio_observation.risky_weight,
        )
        _append_breach(
            triggered_thresholds,
            threshold_id="risk_on_max_cash_weight",
            operator="<=",
            threshold_value=thresholds.risk_on_max_cash_weight,
            actual_value=portfolio_observation.cash_weight,
        )
        return BenchmarkTrendOverlayMonitorActiveObservation(
            required_overlay_status="risk_on",
            threshold_evaluation_performed=True,
            required_min_risky_weight=thresholds.risk_on_min_risky_weight,
            required_max_cash_weight=thresholds.risk_on_max_cash_weight,
            actual_risky_weight=portfolio_observation.risky_weight,
            actual_cash_weight=portfolio_observation.cash_weight,
            risky_weight_gap=round(portfolio_observation.risky_weight - thresholds.risk_on_min_risky_weight, 8),
            cash_weight_gap=round(thresholds.risk_on_max_cash_weight - portfolio_observation.cash_weight, 8),
            triggered_thresholds=triggered_thresholds,
        )

    _append_breach(
        triggered_thresholds,
        threshold_id="risk_reduced_max_risky_weight",
        operator="<=",
        threshold_value=thresholds.risk_reduced_max_risky_weight,
        actual_value=portfolio_observation.risky_weight,
    )
    _append_breach(
        triggered_thresholds,
        threshold_id="risk_reduced_min_cash_weight",
        operator=">=",
        threshold_value=thresholds.risk_reduced_min_cash_weight,
        actual_value=portfolio_observation.cash_weight,
    )
    return BenchmarkTrendOverlayMonitorActiveObservation(
        required_overlay_status="risk_reduced",
        threshold_evaluation_performed=True,
        required_max_risky_weight=thresholds.risk_reduced_max_risky_weight,
        required_min_cash_weight=thresholds.risk_reduced_min_cash_weight,
        actual_risky_weight=portfolio_observation.risky_weight,
        actual_cash_weight=portfolio_observation.cash_weight,
        risky_weight_gap=round(thresholds.risk_reduced_max_risky_weight - portfolio_observation.risky_weight, 8),
        cash_weight_gap=round(portfolio_observation.cash_weight - thresholds.risk_reduced_min_cash_weight, 8),
        triggered_thresholds=triggered_thresholds,
    )


def _append_breach(
    triggered_thresholds: list[MonitorThresholdTrigger],
    *,
    threshold_id,
    operator: Literal[">=", "<="],
    threshold_value: float,
    actual_value: float,
) -> None:
    if operator == ">=" and actual_value >= threshold_value:
        return
    if operator == "<=" and actual_value <= threshold_value:
        return
    breach_amount = round((threshold_value - actual_value) if operator == ">=" else (actual_value - threshold_value), 8)
    triggered_thresholds.append(
        MonitorThresholdTrigger(
            threshold_id=threshold_id,
            operator=operator,
            threshold_value=threshold_value,
            actual_value=actual_value,
            breach_amount=breach_amount,
        )
    )


def _inject_cash_history(histories: dict[str, list[dict]], benchmark_rows: list[dict], symbols: list[str]) -> None:
    if CASH_SYMBOL not in symbols:
        return
    histories[CASH_SYMBOL] = [{"date": row["date"], "price": 1.0, "close": 1.0, "adjClose": 1.0} for row in benchmark_rows if row.get("date") is not None]


def _compare_results(reference: AllocationBacktestResult, candidate: AllocationBacktestResult) -> AllocationBacktestComparison:
    return AllocationBacktestComparison(
        total_return_diff_pct=_diff(reference.metrics.total_return_pct, candidate.metrics.total_return_pct),
        annualized_return_diff_pct=_diff(reference.metrics.annualized_return_pct, candidate.metrics.annualized_return_pct),
        benchmark_return_diff_pct=_diff(reference.metrics.benchmark_return_pct, candidate.metrics.benchmark_return_pct),
        annualized_volatility_diff_pct=_diff(reference.metrics.annualized_volatility_pct, candidate.metrics.annualized_volatility_pct),
        downside_volatility_diff_pct=_diff(reference.metrics.downside_volatility_pct, candidate.metrics.downside_volatility_pct),
        max_drawdown_diff_pct=_diff(reference.metrics.max_drawdown_pct, candidate.metrics.max_drawdown_pct),
        sharpe_diff=_diff(reference.metrics.sharpe_ratio, candidate.metrics.sharpe_ratio),
        sortino_diff=_diff(reference.metrics.sortino_ratio, candidate.metrics.sortino_ratio),
        excess_return_diff_pct=_diff(reference.metrics.excess_return_pct, candidate.metrics.excess_return_pct),
        tracking_error_diff_pct=_diff(reference.metrics.tracking_error_pct, candidate.metrics.tracking_error_pct),
        information_ratio_diff=_diff(reference.metrics.information_ratio, candidate.metrics.information_ratio),
        beta_diff=_diff(reference.metrics.beta_vs_benchmark, candidate.metrics.beta_vs_benchmark),
        correlation_diff=_diff(reference.metrics.correlation_vs_benchmark, candidate.metrics.correlation_vs_benchmark),
        total_turnover_diff_pct=_diff(reference.metrics.total_turnover_pct, candidate.metrics.total_turnover_pct),
        total_cost_diff=_diff(reference.metrics.total_cost_paid, candidate.metrics.total_cost_paid),
    )


def _diff(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(right - left, 4)


def _benchmark_relative_replay_outputs_verified(
    return_basis_attestation: OptimizerReturnBasisAttestation | None,
) -> bool:
    if return_basis_attestation is None:
        return True
    normalized_attestation = normalize_optimizer_return_basis_attestation(return_basis_attestation)
    return normalized_attestation.section_trust.benchmark_relative_path == "verified_adjusted_close"


def _apply_return_basis_attestation_to_replay_result(
    result: AllocationBacktestResult | None,
    return_basis_attestation: OptimizerReturnBasisAttestation | None,
) -> AllocationBacktestResult | None:
    if result is None or _benchmark_relative_replay_outputs_verified(return_basis_attestation):
        return result

    return result.model_copy(
        update={
            "metrics": result.metrics.model_copy(
                update={field_name: None for field_name in REPLAY_BENCHMARK_RELATIVE_METRIC_FIELDS}
            )
        }
    )


def _apply_return_basis_attestation_to_replay_comparison(
    comparison: AllocationBacktestComparison | None,
    return_basis_attestation: OptimizerReturnBasisAttestation | None,
) -> AllocationBacktestComparison | None:
    if comparison is None or _benchmark_relative_replay_outputs_verified(return_basis_attestation):
        return comparison

    return comparison.model_copy(
        update={field_name: None for field_name in REPLAY_BENCHMARK_RELATIVE_COMPARISON_FIELDS}
    )


def _build_portfolio_diagnostics_snapshot(
    *,
    portfolio_name: str,
    weights,
    result: AllocationBacktestResult,
    benchmark_rows: list[dict],
    histories: dict[str, list[dict]],
    return_basis_attestation: OptimizerReturnBasisAttestation | None = None,
) -> PortfolioDiagnosticsSnapshot:
    diagnostics_inputs = _build_backtest_diagnostics_inputs(
        portfolio_name=portfolio_name,
        weights=weights,
        result=result,
        benchmark_rows=benchmark_rows,
        histories=histories,
    )
    factor_registry = build_factor_registry()
    model = build_statistical_factor_model(diagnostics_inputs.replay_daily_states, diagnostics_inputs.factor_price_histories, result.benchmark_symbol or "SPY")
    factor_snapshot = model.current_factor_snapshot if model.current_factor_snapshot else _build_fallback_factor_snapshot(weights, factor_registry)
    volatility = build_volatility_regime_payload(diagnostics_inputs.replay_daily_states, diagnostics_inputs.benchmark_price_history)
    risk_contribution = build_risk_contribution_breakdown(diagnostics_inputs.synthetic_snapshot, diagnostics_inputs.replay_daily_states, {item.symbol: histories.get(item.symbol, []) for item in weights}, diagnostics_inputs.factor_price_histories, factor_registry, model)

    snapshot = PortfolioDiagnosticsSnapshot(
        provenance=PortfolioDiagnosticsProvenance(
            snapshot_basis="synthetic_replay_snapshot",
            historical_basis="market_data_history",
            note="Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.",
        ),
        factor_snapshot=factor_snapshot,
        volatility_snapshot=volatility.snapshot,
        risk_contribution=risk_contribution,
        stress_scenarios=build_stress_scenarios(model),
    )
    return _apply_return_basis_attestation_to_diagnostics_snapshot(snapshot, return_basis_attestation)


def _build_backtest_diagnostics_inputs(
    *,
    portfolio_name: str,
    weights,
    result: AllocationBacktestResult,
    benchmark_rows: list[dict],
    histories: dict[str, list[dict]],
) -> BacktestDiagnosticsInputs:
    factor_registry = build_factor_registry()
    return BacktestDiagnosticsInputs(
        synthetic_snapshot=_build_synthetic_snapshot_from_weights(portfolio_name, weights, result),
        replay_daily_states=_build_daily_states_from_equity_curve(result, weights, histories),
        benchmark_price_history=[row for row in benchmark_rows if result.start_date <= row["date"] <= result.end_date],
        factor_price_histories={definition.us_proxy: histories.get(definition.us_proxy, benchmark_rows) for definition in factor_registry},
    )


def _build_synthetic_snapshot_from_weights(portfolio_name: str, weights, result: AllocationBacktestResult):
    imported_at = datetime.fromisoformat(result.end_date).replace(tzinfo=UTC)
    ending_equity = result.equity_curve[-1].equity if result.equity_curve else 0.0
    base_currency = result.assumptions.investor_base_currency or "USD"
    return ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="multi_broker",
            imported_at=imported_at,
            source_path=f"{portfolio_name.lower()}-backtest",
            detected_format="synthetic_backtest",
            account_id=portfolio_name,
            base_currency=base_currency,
            statement_period=f"{result.start_date} - {result.end_date}",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency=base_currency, ending_cash=0.0)],
        positions=[
            ImportedPosition(
                as_of_date=datetime.fromisoformat(result.end_date).date(),
                symbol=item.symbol,
                quantity=1.0,
                cost_basis=round(ending_equity * item.target_weight, 2),
                close_price=round(ending_equity * item.target_weight, 2),
                market_value=round(ending_equity * item.target_weight, 2),
                unrealized_pnl=0.0,
                currency=base_currency,
            )
            for item in weights
        ],
        ledger_entries=[],
    )


def _build_daily_states_from_equity_curve(result: AllocationBacktestResult, weights, histories: dict[str, list[dict]]) -> list[DailyPortfolioState]:
    history_maps = {
        item.symbol: {row["date"]: float(row.get("adjClose") or row.get("adjusted_close") or row.get("price") or 0.0) for row in histories.get(item.symbol, [])}
        for item in weights
    }
    states: list[DailyPortfolioState] = []
    for point in result.equity_curve:
        positions: list[DailyStatePosition] = []
        total_market_value = 0.0
        for item in weights:
            price = history_maps.get(item.symbol, {}).get(point.date)
            market_value = (point.equity * item.target_weight) if price is not None else None
            total_market_value += market_value or 0.0
            quantity = 0.0
            if market_value is not None and isinstance(price, (int, float)) and price != 0:
                quantity = float(market_value) / float(price)
            market_price = float(price) if isinstance(price, (int, float)) else None
            positions.append(DailyStatePosition(symbol=item.symbol, quantity=quantity, market_price=market_price, market_value=market_value))
        states.append(
            DailyPortfolioState(
                date=point.date,
                cash={result.assumptions.investor_base_currency or "USD": point.cash},
                positions=positions,
                total_market_value=round(total_market_value, 2),
                total_portfolio_value=point.equity,
                external_cash_flow=0.0,
            )
        )
    return states


def _build_fallback_factor_snapshot(weights, factor_registry) -> list[SnapshotItem]:
    weight_by_symbol = {item.symbol.upper(): item.target_weight for item in weights}
    snapshots: list[SnapshotItem] = []
    for definition in factor_registry:
        mapping_symbols: set[str] = {definition.us_proxy.upper()}
        if definition.primary_mapping is not None:
            mapping_symbols.update(symbol.upper() for symbol in definition.primary_mapping.example_tickers)
        for mapping in definition.alternative_mappings:
            mapping_symbols.update(symbol.upper() for symbol in mapping.example_tickers)
        loading = sum(weight_by_symbol.get(symbol, 0.0) for symbol in mapping_symbols)
        snapshots.append(
            SnapshotItem(
                key=definition.key,
                label=definition.label,
                category=definition.category,
                us_proxy=definition.us_proxy,
                latest_loading=round(loading, 4) if loading > 0 else 0.0,
                target_exposure=definition.target_exposure,
                primary_mapping=definition.primary_mapping,
                alternative_mappings=definition.alternative_mappings,
                ucits_examples=definition.ucits_examples,
                mapping_quality=definition.mapping_quality,
                description=definition.description,
            )
        )
    return snapshots


def _build_diagnostics_comparison(
    baseline: PortfolioDiagnosticsSnapshot,
    candidate: PortfolioDiagnosticsSnapshot,
    *,
    return_basis_attestation: OptimizerReturnBasisAttestation | None = None,
) -> PortfolioImprovementComparison:
    factor_rows = _factor_exposure_change_rows(baseline, candidate)
    volatility_rows = _volatility_change_rows(baseline, candidate)
    risk_rows = _risk_contribution_change_rows(baseline, candidate)
    concentration_rows = _concentration_change_rows(baseline, candidate)
    stress_rows = _stress_change_rows(baseline, candidate)

    comparison = PortfolioImprovementComparison(
        factor_exposure_changes=factor_rows,
        top_factor_exposure_change=_top_largest_absolute_delta_callout(factor_rows, rationale="Largest valid factor exposure delta in this group (candidate - baseline)."),
        volatility_changes=volatility_rows,
        top_volatility_change=_top_priority_callout(volatility_rows, ["annualized_volatility", "downside_volatility", "tracking_error"], selection_rule="fixed_priority", rationale=f"{REPLAY_REFUSAL_POLICY_RATIONALE} Selected by fixed priority order across allowed replay risk-shape metrics: annualized volatility, then downside volatility, then tracking error."),
        risk_contribution_changes=risk_rows,
        top_risk_contribution_change=_top_largest_absolute_delta_callout(risk_rows, rationale="Largest valid factor risk-contribution delta in this group (candidate - baseline)."),
        concentration_changes=concentration_rows,
        top_concentration_change=_top_priority_callout(concentration_rows, ["factor_hhi", "top_1_position_risk_share"], selection_rule="fixed_priority", rationale="Selected by fixed priority order: factor HHI, then top 1 position risk share."),
        stress_scenario_changes=stress_rows,
        top_stress_scenario_change=_top_largest_absolute_delta_callout(stress_rows, rationale="Largest valid stress-scenario delta in this group (candidate - baseline)."),
    )
    return _apply_return_basis_attestation_to_diagnostics_comparison(comparison, return_basis_attestation)


def _apply_return_basis_attestation_to_diagnostics_snapshot(
    snapshot: PortfolioDiagnosticsSnapshot,
    return_basis_attestation: OptimizerReturnBasisAttestation | None,
) -> PortfolioDiagnosticsSnapshot:
    if return_basis_attestation is None:
        return snapshot

    return_basis_attestation = normalize_optimizer_return_basis_attestation(return_basis_attestation)

    note = (
        f"{snapshot.provenance.note} Replay consumption is capped by persisted optimizer return-basis attestation "
        f"for {return_basis_attestation.history_start_date} to {return_basis_attestation.history_end_date}."
    )
    updated = snapshot.model_copy(update={"provenance": snapshot.provenance.model_copy(update={"note": note})})

    if not _benchmark_relative_replay_outputs_verified(return_basis_attestation) and updated.volatility_snapshot is not None:
        updated = updated.model_copy(
            update={
                "volatility_snapshot": updated.volatility_snapshot.model_copy(
                    update={
                        "benchmark_vol_20d": None,
                        "benchmark_vol_60d": None,
                        "benchmark_vol_252d": None,
                        "tracking_error_20d": None,
                        "tracking_error_60d": None,
                        "tracking_error_252d": None,
                    }
                )
            }
        )

    if return_basis_attestation.section_trust.factor_model_path != "verified_adjusted_close":
        updated = updated.model_copy(update={"factor_snapshot": [], "stress_scenarios": []})

    if return_basis_attestation.section_trust.risk_contribution_path != "verified_adjusted_close" and updated.risk_contribution is not None:
        updated = updated.model_copy(
            update={
                "risk_contribution": updated.risk_contribution.model_copy(
                    update={
                        "status": "degraded_unverified_return_basis",
                        "factor_contributions": [],
                        "factor_total_variance": None,
                        "specific_variance": None,
                        "total_variance": None,
                        "factor_risk_share_total": None,
                        "specific_risk_share": None,
                        "residual_volatility": None,
                        "position_contributions": [],
                        "concentration": RiskConcentrationSnapshot(),
                    }
                )
            }
        )

    return updated


def _apply_return_basis_attestation_to_diagnostics_comparison(
    comparison: PortfolioImprovementComparison,
    return_basis_attestation: OptimizerReturnBasisAttestation | None,
) -> PortfolioImprovementComparison:
    if return_basis_attestation is None:
        return comparison

    return_basis_attestation = normalize_optimizer_return_basis_attestation(return_basis_attestation)

    updated = comparison
    if not _benchmark_relative_replay_outputs_verified(return_basis_attestation):
        updated = updated.model_copy(
            update={
                "volatility_changes": [item for item in updated.volatility_changes if item.key != "tracking_error"],
                "top_volatility_change": _top_priority_callout(
                    [item for item in updated.volatility_changes if item.key != "tracking_error"],
                    ["annualized_volatility", "downside_volatility"],
                    selection_rule="fixed_priority",
                    rationale=f"{REPLAY_REFUSAL_POLICY_RATIONALE} Benchmark-relative volatility readouts stay withheld when persisted optimizer return-basis attestation is unverified.",
                ),
            }
        )
    if return_basis_attestation.section_trust.factor_model_path != "verified_adjusted_close":
        updated = updated.model_copy(
            update={
                "factor_exposure_changes": [],
                "top_factor_exposure_change": None,
                "stress_scenario_changes": [],
                "top_stress_scenario_change": None,
            }
        )
    if return_basis_attestation.section_trust.risk_contribution_path != "verified_adjusted_close":
        updated = updated.model_copy(
            update={
                "risk_contribution_changes": [],
                "top_risk_contribution_change": None,
                "concentration_changes": [],
                "top_concentration_change": None,
            }
        )
    return updated
def _factor_exposure_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    baseline_map = {item.key: item for item in baseline.factor_snapshot}
    candidate_map = {item.key: item for item in candidate.factor_snapshot}
    keys = sorted(set(baseline_map) | set(candidate_map))
    rows: list[PortfolioDiagnosticsComparisonRow] = []
    for key in keys:
        baseline_item = baseline_map.get(key)
        candidate_item = candidate_map.get(key)
        label = key
        if candidate_item is not None:
            label = candidate_item.label
        elif baseline_item is not None:
            label = baseline_item.label
        baseline_value = baseline_item.latest_loading if baseline_item is not None else None
        candidate_value = candidate_item.latest_loading if candidate_item is not None else None
        rows.append(
            PortfolioDiagnosticsComparisonRow(
                key=key,
                label=label,
                baseline_value=baseline_value,
                candidate_value=candidate_value,
                delta_value=_diff(baseline_value, candidate_value),
            )
        )
    return rows


def _volatility_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    rows = [
        ("annualized_volatility", "Annualized Volatility", baseline.volatility_snapshot.realized_vol_252d if baseline.volatility_snapshot else None, candidate.volatility_snapshot.realized_vol_252d if candidate.volatility_snapshot else None),
        ("downside_volatility", "Downside Volatility", baseline.volatility_snapshot.downside_vol_252d if baseline.volatility_snapshot else None, candidate.volatility_snapshot.downside_vol_252d if candidate.volatility_snapshot else None),
        ("tracking_error", "Tracking Error", baseline.volatility_snapshot.tracking_error_252d if baseline.volatility_snapshot else None, candidate.volatility_snapshot.tracking_error_252d if candidate.volatility_snapshot else None),
    ]
    return [PortfolioDiagnosticsComparisonRow(key=key, label=label, baseline_value=left, candidate_value=right, delta_value=_diff(left, right)) for key, label, left, right in rows]


def _risk_contribution_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    baseline_map = {item.key: item for item in (baseline.risk_contribution.factor_contributions if baseline.risk_contribution else [])}
    candidate_map = {item.key: item for item in (candidate.risk_contribution.factor_contributions if candidate.risk_contribution else [])}
    keys = sorted(set(baseline_map) | set(candidate_map))
    rows: list[PortfolioDiagnosticsComparisonRow] = []
    for key in keys:
        baseline_item = baseline_map.get(key)
        candidate_item = candidate_map.get(key)
        label = key
        if candidate_item is not None:
            label = candidate_item.label
        elif baseline_item is not None:
            label = baseline_item.label
        baseline_value = baseline_item.risk_share if baseline_item is not None else None
        candidate_value = candidate_item.risk_share if candidate_item is not None else None
        rows.append(
            PortfolioDiagnosticsComparisonRow(
                key=key,
                label=label,
                baseline_value=baseline_value,
                candidate_value=candidate_value,
                delta_value=_diff(baseline_value, candidate_value),
            )
        )
    return rows


def _concentration_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    if not baseline.risk_contribution or not candidate.risk_contribution:
        return []
    rows = [
        ("top_1_position_risk_share", "Top 1 Position Risk Share", baseline.risk_contribution.concentration.top_1_position_risk_share, candidate.risk_contribution.concentration.top_1_position_risk_share),
        ("top_5_position_risk_share", "Top 5 Position Risk Share", baseline.risk_contribution.concentration.top_5_position_risk_share, candidate.risk_contribution.concentration.top_5_position_risk_share),
        ("factor_hhi", "Factor HHI", baseline.risk_contribution.concentration.factor_hhi, candidate.risk_contribution.concentration.factor_hhi),
        ("position_hhi", "Position HHI", baseline.risk_contribution.concentration.position_hhi, candidate.risk_contribution.concentration.position_hhi),
    ]
    return [PortfolioDiagnosticsComparisonRow(key=key, label=label, baseline_value=left, candidate_value=right, delta_value=_diff(left, right)) for key, label, left, right in rows]


def _stress_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    baseline_map = {item.name: item for item in baseline.stress_scenarios}
    candidate_map = {item.name: item for item in candidate.stress_scenarios}
    keys = sorted(set(baseline_map) | set(candidate_map))
    rows: list[PortfolioDiagnosticsComparisonRow] = []
    for key in keys:
        baseline_item = baseline_map.get(key)
        candidate_item = candidate_map.get(key)
        baseline_value = baseline_item.estimated_return_pct if baseline_item is not None else None
        candidate_value = candidate_item.estimated_return_pct if candidate_item is not None else None
        rows.append(
            PortfolioDiagnosticsComparisonRow(
                key=key.lower().replace(" ", "_"),
                label=key,
                baseline_value=baseline_value,
                candidate_value=candidate_value,
                delta_value=_diff(baseline_value, candidate_value),
            )
        )
    return rows


def _largest_absolute_delta_row(rows: list[PortfolioDiagnosticsComparisonRow]) -> PortfolioDiagnosticsComparisonRow | None:
    eligible = [row for row in rows if row.delta_value is not None and row.baseline_value is not None and row.candidate_value is not None]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (abs(row.delta_value or 0.0), row.label, row.key))


def _top_priority_row(rows: list[PortfolioDiagnosticsComparisonRow], priority_keys: list[str]) -> PortfolioDiagnosticsComparisonRow | None:
    row_map = {row.key: row for row in rows if row.delta_value is not None and row.baseline_value is not None and row.candidate_value is not None}
    for key in priority_keys:
        if key in row_map:
            return row_map[key]
    return None


def _build_top_callout(row: PortfolioDiagnosticsComparisonRow | None, *, selection_rule: str, rationale: str) -> PortfolioDiagnosticsTopCallout | None:
    if row is None:
        return None
    return PortfolioDiagnosticsTopCallout(
        key=row.key,
        label=row.label,
        baseline_value=row.baseline_value,
        candidate_value=row.candidate_value,
        delta_value=row.delta_value,
        selection_rule=selection_rule,
        rationale=rationale,
    )


def _top_largest_absolute_delta_callout(rows: list[PortfolioDiagnosticsComparisonRow], *, rationale: str) -> PortfolioDiagnosticsTopCallout | None:
    return _build_top_callout(_largest_absolute_delta_row(rows), selection_rule="largest_absolute_delta", rationale=rationale)


def _top_priority_callout(rows: list[PortfolioDiagnosticsComparisonRow], priority_keys: list[str], *, selection_rule: str, rationale: str) -> PortfolioDiagnosticsTopCallout | None:
    return _build_top_callout(_top_priority_row(rows, priority_keys), selection_rule=selection_rule, rationale=rationale)


def _derive_status(
    *,
    symbols: list[str],
    ordered_dates: list[str],
    requested_start: str,
    requested_end: str,
    registry: InstrumentRegistry,
    histories: dict[str, list[dict]],
    benchmark_rows: list[dict],
) -> AllocationBacktestStatus:
    if not ordered_dates:
        return "rejected"
    status: AllocationBacktestStatus = "ok"
    if ordered_dates[0] > requested_start or ordered_dates[-1] < requested_end:
        status = "degraded"
    if not _has_adjusted_price_history(benchmark_rows):
        status = "degraded"
    if any(not _has_adjusted_price_history(histories.get(symbol, [])) for symbol in symbols):
        status = "degraded"
    if any(_is_distributing_without_adjusted_history(symbol, histories.get(symbol, []), registry) for symbol in symbols):
        status = "degraded"
    return status


def _instrument_metadata(symbols: list[str], registry: InstrumentRegistry) -> list[AllocationBacktestInstrumentMeta]:
    metadata: list[AllocationBacktestInstrumentMeta] = []
    for symbol in symbols:
        if symbol == CASH_SYMBOL:
            metadata.append(
                AllocationBacktestInstrumentMeta(
                    symbol=CASH_SYMBOL,
                    trading_currency="USD",
                    instrument_base_currency="USD",
                    currency_hedged=None,
                    distribution_policy="unknown",
                )
            )
            continue
        instrument = registry.get_instrument(symbol)
        metadata.append(
            AllocationBacktestInstrumentMeta(
                symbol=symbol,
                trading_currency=instrument.currency if instrument else None,
                instrument_base_currency=instrument.currency if instrument else None,
                currency_hedged=None,
                distribution_policy=_distribution_policy(instrument.category if instrument else None),
            )
        )
    return metadata


def _is_ucits_symbol(symbol: str, registry: InstrumentRegistry) -> bool:
    instrument = registry.get_instrument(symbol)
    if instrument is None or instrument.category is None:
        return False
    return instrument.category.endswith("UCITS ETF")


def _has_adjusted_price_history(rows: list[dict]) -> bool:
    return any(row.get("adjClose") is not None or row.get("adjusted_close") is not None for row in rows)


def _distribution_policy(category: str | None) -> DistributionPolicy:
    if category is None:
        return "unknown"
    if "UCITS" in category:
        return "accumulating"
    return "unknown"


def _is_distributing_without_adjusted_history(symbol: str, rows: list[dict], registry: InstrumentRegistry) -> bool:
    instrument = registry.get_instrument(symbol)
    if instrument is None:
        return False
    if _distribution_policy(instrument.category) != "distributing":
        return False
    return not _has_adjusted_price_history(rows)
