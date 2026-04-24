from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal

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
    ConstructionArtifactReplayEffectiveParams,
    ConstructionArtifactPreviewRequest,
    ConstructionArtifactReplayProvenance,
    ConstructionArtifactReplayRequest,
    ConstructionArtifactReplayResponse,
    ConstructionArtifactReplayValidationResponse,
    ConstructionArtifactPreviewHandoff,
    DistributionPolicy,
    HypotheticalReplayDerivation,
    HypotheticalReplayProvenance,
    HypotheticalReplayProposal,
    HypotheticalReplayUpstreamIds,
    OverlayApplicationSummary,
    OptimizerHandoffReplayBenchmarkAttestationSummary,
    OptimizerHandoffReplayConstraintSummary,
    OptimizerHandoffReplayOptimizerContext,
    OptimizerHandoffReplayOptimizerDiagnostics,
    OptimizerHandoffReplayProvenance,
    OptimizerHandoffReplayRequest,
    OptimizerHandoffReplayResponse,
    OptimizerHandoffReplayOptimizerRunSummary,
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
from app.services.optimizer_handoff_constraints import (
    build_optimizer_handoff_replay_output_policy,
    load_validated_optimizer_handoff_for_replay,
)
from app.services.optimizer_artifact_service import normalize_optimizer_return_basis_attestation


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
    request: OptimizerHandoffReplayRequest,
    *,
    handoff_store=None,
) -> OptimizerHandoffReplayResponse:
    validated_gate = load_validated_optimizer_handoff_for_replay(request, handoff_store=handoff_store)
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
        optimizer_context=_build_optimizer_handoff_context(artifact),
        baseline_weights=baseline_weights,
        candidate_weights=candidate_weights,
        replay=replay,
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
        replay_provenance=ConstructionArtifactReplayProvenance(
            construction_artifact_id=artifact.artifact_id,
            policy_id=artifact.normalized_inputs.policy_id,
            policy_definition_id=artifact.normalized_inputs.policy_definition_id,
            ranked_universe_artifact_id=artifact.normalized_inputs.ranked_universe_artifact_id,
            ranking_id=artifact.normalized_inputs.ranking_id,
            ranking_methodology_id=artifact.normalized_inputs.ranking_methodology_id,
            current_portfolio_artifact_id=artifact.normalized_inputs.current_portfolio_artifact_id,
            selection_rule_trace=artifact.selection_rule_trace,
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
