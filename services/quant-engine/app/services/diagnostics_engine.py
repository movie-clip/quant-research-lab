from typing import Literal

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL
from app.analytics.risk import (
    COLLINEARITY_WARNING_THRESHOLD,
    FACTOR_PROXY_MAP,
    RISK_CONTRIBUTION_WINDOW_DAYS,
    ROLLING_WINDOWS,
    WINDOW_MIN_OBSERVATIONS,
    apply_return_basis_status_to_factor_model,
    apply_return_basis_status_to_model_reliability,
    build_factor_exposures,
    build_factor_registry,
    build_factor_shift_diagnostics,
    build_model_reliability_snapshot,
    build_portfolio_risk_summary,
    build_relative_risk_summary,
    build_risk_contribution_breakdown,
    build_rolling_risk_series,
    build_statistical_factor_model,
    build_stress_scenarios,
    build_volatility_regime_payload,
    factor_model_methodology,
)
from app.analytics.performance import build_daily_portfolio_states
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.diagnostics import (
    DiagnosticsAvailability,
    DiagnosticsDrawdownSummary,
    DiagnosticsEngineRequest,
    DiagnosticsProvenance,
    DiagnosticsResult,
    DiagnosticsRunMetadata,
    DiagnosticsSourceStatus,
    DiagnosticsRiskConcentrationSummary,
    DiagnosticsVolatilitySummary,
)
from app.schemas.return_basis import ReturnBasisEvidence
from app.schemas.dashboard_history import InvestorEconomicsStatus, build_investor_economics_status
from app.schemas.reconciliation import (
    DailyPortfolioState,
    DailyStatePosition,
    LookThroughSectorExposure,
    MarketOverlapSummary,
    FactorShiftDiagnosticsPayload,
    ModelReliabilitySnapshot,
    PortfolioRiskSummary,
    RelativeRiskSummary,
    RiskConcentrationSnapshot,
    RiskContributionBreakdownPayload,
    StatisticalFactorModel,
    StressScenarioResult,
    VolatilityAssumptions,
    VolatilityRegimePayload,
    VolatilitySnapshot,
    RegimeAssessment,
)
from app.services.exposure_engine import build_snapshot_from_exposure_request
from app.services.dashboard_history_engine import _build_dashboard_investor_economics_partial_unlock
from app.services.market_data import (
    MarketDataService,
    build_histories_return_basis_evidence,
    build_history_return_basis_evidence,
    detect_histories_return_basis,
    detect_history_return_basis,
)
from app.services.portfolio_proof import build_portfolio_proof_metadata, build_unavailable_portfolio_proof_metadata


DIAGNOSTICS_ID = "diagnostics_engine_v1"
DIAGNOSTICS_METHODOLOGY_ID = "diagnostics_history_methodology_v1"
DIAGNOSTICS_PRICE_BASIS = "close"
DIAGNOSTICS_ORTHOGONALIZATION_BASIS = "factor_proxy_definition_order"
DIAGNOSTICS_RIDGE_LAMBDA = 1e-5
DIAGNOSTICS_DATASET_VERSION = "market_data_service_v1"


DiagnosticsUnavailableReason = Literal[
    "missing_request_history_context",
    "missing_imported_history_path",
    "missing_market_data",
]


def _build_diagnostics_source_status(
    historical_basis: Literal["imported_portfolio_history", "market_data_history", "unavailable"],
    benchmark_return_basis: Literal["verified_adjusted_close", "unverified_close_only", "unavailable"],
    factor_return_basis: Literal["verified_adjusted_close", "unverified_close_only", "unavailable"],
) -> DiagnosticsSourceStatus:
    benchmark_history_status = (
        "live_market_data_verified_adjusted_close"
        if benchmark_return_basis == "verified_adjusted_close"
        else "live_market_data_unverified_return_basis"
        if benchmark_return_basis == "unverified_close_only"
        else "unavailable"
    )
    factor_history_status = (
        "live_market_data_verified_adjusted_close"
        if factor_return_basis == "verified_adjusted_close"
        else "live_market_data_unverified_return_basis"
        if factor_return_basis == "unverified_close_only"
        else "unavailable"
    )
    if historical_basis == "imported_portfolio_history":
        return DiagnosticsSourceStatus(
            portfolio_history="imported_replay",
            benchmark_history=benchmark_history_status,
            factor_history=factor_history_status,
        )
    if historical_basis == "market_data_history":
        return DiagnosticsSourceStatus(
            portfolio_history="synthetic_snapshot_history",
            benchmark_history=benchmark_history_status,
            factor_history=factor_history_status,
        )
    return DiagnosticsSourceStatus(
        portfolio_history="unavailable",
        benchmark_history="unavailable",
        factor_history="unavailable",
    )


def _build_factor_model_parameters() -> DiagnosticsRunMetadata.FactorModelParameters:
    return DiagnosticsRunMetadata.FactorModelParameters(
        rolling_windows_days=list(ROLLING_WINDOWS),
        current_reliability_window_days=RISK_CONTRIBUTION_WINDOW_DAYS,
        minimum_window_observations={str(window): required for window, required in WINDOW_MIN_OBSERVATIONS.items()},
        collinearity_warning_threshold=COLLINEARITY_WARNING_THRESHOLD,
        orthogonalization_basis=DIAGNOSTICS_ORTHOGONALIZATION_BASIS,
        ridge_lambda=DIAGNOSTICS_RIDGE_LAMBDA,
    )


def _build_reproducibility_metadata(
    snapshot: ImportedPortfolioSnapshot,
    history_start_date: str | None,
    history_end_date: str | None,
) -> DiagnosticsRunMetadata.ReproducibilityMetadata:
    snapshot_as_of_date = max((position.as_of_date.isoformat() for position in snapshot.positions if position.as_of_date is not None), default=None)
    return DiagnosticsRunMetadata.ReproducibilityMetadata(
        input_imported_at=snapshot.statement.imported_at.isoformat() if snapshot.statement.imported_at is not None else None,
        snapshot_as_of_date=snapshot_as_of_date,
        history_start_date=history_start_date,
        history_end_date=history_end_date,
        dataset_version=DIAGNOSTICS_DATASET_VERSION,
    )


def _build_unavailable_provenance_note(reason: DiagnosticsUnavailableReason) -> str:
    if reason == "missing_request_history_context":
        return "Historical diagnostics are unavailable because snapshot-style input did not include the history context needed to build a valid historical portfolio path."
    if reason == "missing_imported_history_path":
        return "Historical diagnostics are unavailable because imported broker history could not be reconstructed from this snapshot."
    return "Historical diagnostics are unavailable because the required benchmark or symbol market data could not be loaded for the requested history window."


def _build_history_available_provenance_note(historical_basis: Literal["imported_portfolio_history", "market_data_history"]) -> str:
    if historical_basis == "imported_portfolio_history":
        return "Historical diagnostics are derived from imported portfolio history replay plus external benchmark and factor market data. Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice."
    return "Historical diagnostics are derived from synthetic snapshot-history states built from the current snapshot plus external market data. Benchmark and factor return histories remain unverified for adjusted-close or total-return equivalence in this diagnostics slice."


def _resolve_diagnostics_confidence(
    source_status: DiagnosticsSourceStatus,
    model_reliability: ModelReliabilitySnapshot,
) -> Literal["high", "medium", "low"]:
    if (
        source_status.benchmark_history != "live_market_data_verified_adjusted_close"
        or source_status.factor_history != "live_market_data_verified_adjusted_close"
    ):
        return "low"
    if model_reliability.confidence == "high":
        return "high"
    if model_reliability.confidence == "medium":
        return "medium"
    return "low"


def _resolve_section_trust(
    *,
    benchmark_return_basis: Literal["verified_adjusted_close", "unverified_close_only", "unavailable"],
    factor_return_basis: Literal["verified_adjusted_close", "unverified_close_only", "unavailable"],
    historical_sections_available: bool,
) -> DiagnosticsRunMetadata.SectionTrust:
    if not historical_sections_available:
        return DiagnosticsRunMetadata.SectionTrust(
            benchmark_relative_path="unavailable",
            factor_model_path="unavailable",
            risk_contribution_path="unavailable",
        )

    benchmark_relative_path = "verified_adjusted_close" if benchmark_return_basis == "verified_adjusted_close" else "degraded_unverified_return_basis"
    factor_model_path = (
        "verified_adjusted_close"
        if benchmark_return_basis == "verified_adjusted_close" and factor_return_basis == "verified_adjusted_close"
        else "degraded_unverified_return_basis"
    )
    risk_contribution_path = factor_model_path
    return DiagnosticsRunMetadata.SectionTrust(
        benchmark_relative_path=benchmark_relative_path,
        factor_model_path=factor_model_path,
        risk_contribution_path=risk_contribution_path,
    )


def _allow_diagnostics_drawdown_outputs() -> bool:
    return False


def _apply_diagnostics_drawdown_output_policy(
    volatility_regime: VolatilityRegimePayload,
    *,
    allow_drawdown_outputs: bool,
) -> VolatilityRegimePayload:
    if allow_drawdown_outputs:
        return volatility_regime

    return volatility_regime.model_copy(
        update={
            "rolling_series": [
                point.model_copy(update={"drawdown_pct": None, "wealth_index": None})
                for point in volatility_regime.rolling_series
            ],
            "snapshot": volatility_regime.snapshot.model_copy(
                update={
                    "current_drawdown_pct": None,
                    "max_drawdown_pct": None,
                }
            ),
        }
    )


def _build_diagnostics_drawdown_summary(
    volatility_regime: VolatilityRegimePayload,
    *,
    allow_drawdown_outputs: bool,
) -> DiagnosticsDrawdownSummary:
    if not allow_drawdown_outputs:
        return DiagnosticsDrawdownSummary(
            current_drawdown_pct=None,
            max_drawdown_pct=None,
        )

    return DiagnosticsDrawdownSummary(
        current_drawdown_pct=volatility_regime.snapshot.current_drawdown_pct,
        max_drawdown_pct=volatility_regime.snapshot.max_drawdown_pct,
    )


def _allow_diagnostics_relative_return_outputs() -> bool:
    return False


def _build_diagnostics_investor_economics_status(
    *,
    historical_sections_available: bool,
    allow_drawdown_outputs: bool,
    allow_relative_return_outputs: bool,
) -> InvestorEconomicsStatus:
    if not historical_sections_available:
        return build_investor_economics_status(available=False)
    if allow_drawdown_outputs and allow_relative_return_outputs:
        return build_investor_economics_status(available=True)
    return build_investor_economics_status(
        available=False,
    )


def _apply_diagnostics_relative_return_output_policy(
    relative_risk: RelativeRiskSummary,
    *,
    allow_relative_return_outputs: bool,
) -> RelativeRiskSummary:
    if allow_relative_return_outputs:
        return relative_risk

    return relative_risk.model_copy(
        update={
            "active_return_pct": None,
            "information_ratio": None,
        }
    )


def _build_unavailable_availability(reason: DiagnosticsUnavailableReason) -> DiagnosticsAvailability:
    if reason == "missing_request_history_context":
        return DiagnosticsAvailability(
            historical_sections_available=False,
            history_context_required=True,
            note="Historical diagnostics are unavailable from snapshot-only input. Attach PortfolioHistoryContext to run rolling diagnostics accurately.",
            status="unavailable",
        )
    if reason == "missing_imported_history_path":
        return DiagnosticsAvailability(
            historical_sections_available=False,
            history_context_required=False,
            note="Historical diagnostics are unavailable because this imported snapshot does not contain enough broker history to reconstruct a historical portfolio path.",
            status="unavailable",
        )
    return DiagnosticsAvailability(
        historical_sections_available=False,
        history_context_required=False,
        note="Historical diagnostics are unavailable because the required benchmark or symbol market data could not be loaded for the requested history window.",
        status="unavailable",
    )


def _build_unavailable_stress_scenarios(reason: DiagnosticsUnavailableReason) -> list[StressScenarioResult]:
    if reason == "missing_request_history_context":
        description = "Attach PortfolioHistoryContext to run historically grounded diagnostics and stress scenarios."
    elif reason == "missing_imported_history_path":
        description = "Imported broker history is not sufficient to reconstruct historically grounded diagnostics and stress scenarios for this snapshot."
    else:
        description = "Required benchmark or symbol market data could not be loaded for historically grounded diagnostics and stress scenarios."

    return [
        StressScenarioResult(
            name='Unavailable historical diagnostics',
            estimated_return_pct=None,
            description=description,
            status='unavailable',
        ),
    ]


def build_historical_diagnostics_result(
    snapshot,
    benchmark_symbol: str,
    daily_states: list,
    benchmark_rows: list[dict],
    symbol_price_histories: dict[str, list[dict]],
    factor_histories: dict[str, list[dict]],
    market_overlap: MarketOverlapSummary,
    lookthrough_sector_exposure: list[LookThroughSectorExposure],
    provenance: DiagnosticsProvenance,
) -> DiagnosticsResult:
    factor_registry = build_factor_registry()
    benchmark_return_basis = detect_history_return_basis(benchmark_rows)
    factor_return_basis = detect_histories_return_basis({
        symbol: rows
        for symbol, rows in factor_histories.items()
        if symbol != benchmark_symbol
    })
    portfolio_history_evidence = (
        ReturnBasisEvidence(
            verification_status="unverified",
            economic_basis="price_return_only",
            construction_method="synthetic_snapshot_history",
            disqualifiers=[
                "synthetic_snapshot_history",
                "missing_total_return_reconstruction",
                "missing_dividend_coverage_proof",
            ],
            fallbacks_used=["synthetic_snapshot_history"],
            source_price_field="price",
        )
        if provenance.historical_basis == "market_data_history"
        else ReturnBasisEvidence(
            verification_status="unverified",
            economic_basis="unavailable",
            construction_method="unknown",
            disqualifiers=["missing_portfolio_return_basis_proof"],
            fallbacks_used=[],
            source_price_field=None,
        )
    )
    return_basis_evidence = DiagnosticsRunMetadata.ReturnBasisEvidenceBundle(
        portfolio_history=portfolio_history_evidence,
        benchmark_history=build_history_return_basis_evidence(benchmark_rows),
        factor_history=build_histories_return_basis_evidence(
            {
                symbol: rows
                for symbol, rows in factor_histories.items()
                if symbol != benchmark_symbol
            }
        ),
    )
    source_status = _build_diagnostics_source_status(
        provenance.historical_basis,
        benchmark_return_basis=benchmark_return_basis,
        factor_return_basis=factor_return_basis,
    )
    section_trust = _resolve_section_trust(
        benchmark_return_basis=benchmark_return_basis,
        factor_return_basis=factor_return_basis,
        historical_sections_available=True,
    )
    allow_relative_return_outputs = _allow_diagnostics_relative_return_outputs()
    risk_summary = build_portfolio_risk_summary(daily_states, benchmark_rows, benchmark_symbol)
    rolling_risk = build_rolling_risk_series(daily_states, benchmark_rows)
    relative_risk = _apply_diagnostics_relative_return_output_policy(
        build_relative_risk_summary(daily_states, benchmark_rows, benchmark_symbol),
        allow_relative_return_outputs=allow_relative_return_outputs,
    )
    statistical_factor_model = build_statistical_factor_model(daily_states, factor_histories, benchmark_symbol)
    statistical_factor_model = apply_return_basis_status_to_factor_model(
        statistical_factor_model,
        benchmark_rows=benchmark_rows,
        factor_histories=factor_histories,
    )
    allow_drawdown_outputs = _allow_diagnostics_drawdown_outputs()
    volatility_regime = _apply_diagnostics_drawdown_output_policy(
        build_volatility_regime_payload(daily_states, benchmark_rows),
        allow_drawdown_outputs=allow_drawdown_outputs,
    )
    factor_shift_diagnostics = build_factor_shift_diagnostics(factor_registry, statistical_factor_model, volatility_regime)
    risk_contribution_breakdown = build_risk_contribution_breakdown(
        snapshot,
        daily_states,
        symbol_price_histories,
        factor_histories,
        factor_registry,
        statistical_factor_model,
    )
    model_reliability = apply_return_basis_status_to_model_reliability(
        build_model_reliability_snapshot(statistical_factor_model),
        benchmark_rows=benchmark_rows,
        factor_histories=factor_histories,
    )
    diagnostics_confidence = _resolve_diagnostics_confidence(source_status, model_reliability)
    stress_scenarios = build_stress_scenarios(statistical_factor_model)
    factor_exposures = build_factor_exposures(risk_summary, market_overlap, lookthrough_sector_exposure)
    concentration = risk_contribution_breakdown.concentration
    portfolio_proof_history_source = (
        "imported_replay"
        if provenance.historical_basis == "imported_portfolio_history"
        else "synthetic_snapshot_history"
    )

    return DiagnosticsResult(
        snapshot=snapshot,
        provenance=provenance,
        availability=DiagnosticsAvailability(
            historical_sections_available=True,
            history_context_required=True,
            note=None,
            status="ok",
        ),
        run_metadata=DiagnosticsRunMetadata(
            diagnostics_id=DIAGNOSTICS_ID,
            methodology_id=DIAGNOSTICS_METHODOLOGY_ID,
            price_basis=DIAGNOSTICS_PRICE_BASIS,
            source_status=source_status,
            section_trust=section_trust,
            return_basis_evidence=return_basis_evidence,
            portfolio_proof=build_portfolio_proof_metadata(
                snapshot=snapshot,
                price_histories=symbol_price_histories,
                valuation_dates=[state.date for state in daily_states],
                fx_history={},
                history_source=portfolio_proof_history_source,
            ),
            investor_economics_status=_build_diagnostics_investor_economics_status(
                historical_sections_available=True,
                allow_drawdown_outputs=allow_drawdown_outputs,
                allow_relative_return_outputs=allow_relative_return_outputs,
            ),
            investor_economics_partial_unlock=_build_dashboard_investor_economics_partial_unlock(),
            confidence=diagnostics_confidence,
            factor_model_parameters=_build_factor_model_parameters(),
            reproducibility=_build_reproducibility_metadata(
                snapshot,
                history_start_date=daily_states[0].date if daily_states else None,
                history_end_date=daily_states[-1].date if daily_states else None,
            ),
        ),
        drawdown_summary=_build_diagnostics_drawdown_summary(
            volatility_regime,
            allow_drawdown_outputs=allow_drawdown_outputs,
        ),
        volatility_summary=DiagnosticsVolatilitySummary(
            portfolio_volatility_pct=risk_summary.portfolio_volatility_pct,
            benchmark_volatility_pct=risk_summary.benchmark_volatility_pct,
            downside_volatility_pct=volatility_regime.snapshot.downside_vol_60d,
            tracking_error_pct=relative_risk.tracking_error_pct,
        ),
        risk_concentration_summary=DiagnosticsRiskConcentrationSummary(
            top_1_factor_risk_share=concentration.top_1_factor_risk_share,
            top_3_factor_risk_share=concentration.top_3_factor_risk_share,
            top_1_position_risk_share=concentration.top_1_position_risk_share,
            top_5_position_risk_share=concentration.top_5_position_risk_share,
            factor_hhi=concentration.factor_hhi,
            position_hhi=concentration.position_hhi,
        ),
        risk_summary=risk_summary,
        rolling_risk=rolling_risk,
        relative_risk=relative_risk,
        volatility_regime=volatility_regime,
        factor_exposures=factor_exposures,
        factor_shift_diagnostics=factor_shift_diagnostics,
        risk_contribution_breakdown=risk_contribution_breakdown,
        model_reliability=model_reliability,
        factor_registry=factor_registry,
        factor_methodology=factor_model_methodology(),
        statistical_factor_model=statistical_factor_model,
        stress_scenarios=stress_scenarios,
    )


def build_unavailable_diagnostics_result(
    snapshot,
    benchmark_symbol: str,
    snapshot_basis: Literal["imported_snapshot", "snapshot_request"] = "snapshot_request",
    reason: DiagnosticsUnavailableReason = "missing_request_history_context",
) -> DiagnosticsResult:
    factor_registry = build_factor_registry()

    return DiagnosticsResult(
        snapshot=snapshot,
        provenance=DiagnosticsProvenance(
            snapshot_basis=snapshot_basis,
            historical_basis="unavailable",
            history_truth_class="unavailable",
            price_basis="unavailable",
            note=_build_unavailable_provenance_note(reason),
        ),
        availability=_build_unavailable_availability(reason),
        run_metadata=DiagnosticsRunMetadata(
            diagnostics_id=DIAGNOSTICS_ID,
            methodology_id=DIAGNOSTICS_METHODOLOGY_ID,
            price_basis="unavailable",
            source_status=_build_diagnostics_source_status(
                "unavailable",
                benchmark_return_basis="unavailable",
                factor_return_basis="unavailable",
            ),
            section_trust=_resolve_section_trust(
                benchmark_return_basis="unavailable",
                factor_return_basis="unavailable",
                historical_sections_available=False,
            ),
            return_basis_evidence=DiagnosticsRunMetadata.ReturnBasisEvidenceBundle(
                portfolio_history=build_history_return_basis_evidence([]),
                benchmark_history=build_history_return_basis_evidence([]),
                factor_history=build_history_return_basis_evidence([]),
            ),
            portfolio_proof=build_unavailable_portfolio_proof_metadata(),
            investor_economics_status=_build_diagnostics_investor_economics_status(
                historical_sections_available=False,
                allow_drawdown_outputs=False,
                allow_relative_return_outputs=False,
            ),
            investor_economics_partial_unlock=_build_dashboard_investor_economics_partial_unlock(),
            confidence="low",
            factor_model_parameters=_build_factor_model_parameters(),
            reproducibility=_build_reproducibility_metadata(snapshot, history_start_date=None, history_end_date=None),
        ),
        drawdown_summary=DiagnosticsDrawdownSummary(),
        volatility_summary=DiagnosticsVolatilitySummary(),
        risk_concentration_summary=DiagnosticsRiskConcentrationSummary(),
        risk_summary=PortfolioRiskSummary(
            benchmark_symbol=benchmark_symbol,
            methodology='unavailable_without_history_context',
            start_date=None,
            end_date=None,
            observations=0,
            portfolio_beta=None,
            portfolio_correlation=None,
            r_squared=None,
            portfolio_volatility_pct=None,
            benchmark_volatility_pct=None,
        ),
        rolling_risk=[],
        relative_risk=RelativeRiskSummary(
            benchmark_symbol=benchmark_symbol,
            tracking_error_pct=None,
            active_return_pct=None,
            information_ratio=None,
        ),
        volatility_regime=VolatilityRegimePayload(
            methodology='unavailable_without_history_context',
            assumptions=VolatilityAssumptions(
                return_basis='unavailable',
                cash_flow_timing='unavailable',
                drawdown_basis='unavailable',
                benchmark_basis='unavailable',
                downside_mar=0.0,
                annualization_days=252,
            ),
            rolling_series=[],
            snapshot=VolatilitySnapshot(),
            regime=RegimeAssessment(label='unavailable', confidence='low'),
        ),
        factor_exposures=[],
        factor_shift_diagnostics=FactorShiftDiagnosticsPayload(
            methodology='unavailable_without_history_context',
            snapshots=[],
            largest_positive_shifts_20d=[],
            largest_negative_shifts_20d=[],
            largest_absolute_shifts_20d=[],
            largest_absolute_shifts_60d=[],
        ),
        risk_contribution_breakdown=RiskContributionBreakdownPayload(
            methodology='unavailable_without_history_context',
            window_days=20,
            observation_count=0,
            status='unavailable',
            factor_contributions=[],
            position_contributions=[],
            concentration=RiskConcentrationSnapshot(),
        ),
        model_reliability=ModelReliabilitySnapshot(
            window_days=20,
            observation_count=0,
            r_squared=None,
            residual_volatility=None,
            collinearity_pair_count=0,
            max_abs_factor_correlation=None,
            factor_count_used=0,
            missing_factor_count=0,
            status='unavailable',
            confidence='low',
            stability_score=None,
        ),
        factor_registry=factor_registry,
        factor_methodology=factor_model_methodology(),
        statistical_factor_model=StatisticalFactorModel(
            status='unavailable',
            benchmark_symbol=benchmark_symbol,
            windows=[],
            rolling_loadings_20d=[],
            rolling_loadings_60d=[],
            rolling_loadings_252d=[],
            current_factor_snapshot=[],
            collinearity_diagnostics=[],
            insufficient_history=[],
        ),
        stress_scenarios=_build_unavailable_stress_scenarios(reason),
    )


def run_diagnostics_engine(request: DiagnosticsEngineRequest) -> DiagnosticsResult:
    snapshot = build_snapshot_from_exposure_request(request)
    history_context = request.history_context
    if history_context is None or not history_context.history_start_date or not history_context.history_end_date:
        return build_unavailable_diagnostics_result(
            snapshot,
            request.benchmark_symbol,
            snapshot_basis="snapshot_request",
            reason="missing_request_history_context",
        )

    return _run_diagnostics_with_history(
        snapshot=snapshot,
        benchmark_symbol=history_context.benchmark_symbol or request.benchmark_symbol,
        history_start_date=history_context.history_start_date,
        history_end_date=history_context.history_end_date,
        snapshot_basis="snapshot_request",
        historical_basis="market_data_history",
        provenance_note=_build_history_available_provenance_note("market_data_history"),
    )


def _run_diagnostics_with_history(
    *,
    snapshot: ImportedPortfolioSnapshot,
    benchmark_symbol: str,
    history_start_date: str,
    history_end_date: str,
    snapshot_basis: Literal["imported_snapshot", "snapshot_request"],
    historical_basis: Literal["imported_portfolio_history", "market_data_history"],
    provenance_note: str,
) -> DiagnosticsResult:
    market_data = MarketDataService()
    benchmark_rows = market_data.get_historical_prices(benchmark_symbol, history_start_date, history_end_date)
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [position.symbol for position in snapshot.positions],
        history_start_date,
        history_end_date,
    )
    factor_histories = market_data.get_historical_prices_for_symbols(
        list(FACTOR_PROXY_MAP.values()),
        history_start_date,
        history_end_date,
    )
    factor_histories[benchmark_symbol] = benchmark_rows
    if not benchmark_rows or not _has_any_symbol_price_history(symbol_price_histories):
        return build_unavailable_diagnostics_result(
            snapshot,
            benchmark_symbol,
            snapshot_basis=snapshot_basis,
            reason="missing_market_data",
        )

    valuation_dates = sorted({row['date'] for row in benchmark_rows})
    if historical_basis == "imported_portfolio_history":
        daily_states = build_daily_portfolio_states(
            snapshot=snapshot,
            price_histories=symbol_price_histories,
            valuation_dates=valuation_dates,
            fx_history={},
        )
    else:
        daily_states = _build_synthetic_snapshot_history_states(
            snapshot=snapshot,
            price_histories=symbol_price_histories,
            valuation_dates=valuation_dates,
        )

    from app.services.exposure_engine import build_exposure_result

    exposure_result = build_exposure_result(snapshot, benchmark_symbol)
    return build_historical_diagnostics_result(
        snapshot=snapshot,
        benchmark_symbol=benchmark_symbol,
        daily_states=daily_states,
        benchmark_rows=benchmark_rows,
        symbol_price_histories=symbol_price_histories,
        factor_histories=factor_histories,
        market_overlap=exposure_result.market_overlap,
        lookthrough_sector_exposure=exposure_result.lookthrough_sector_exposure,
        provenance=DiagnosticsProvenance(
            snapshot_basis=snapshot_basis,
            historical_basis=historical_basis,
            history_truth_class="synthetic_history_derived" if historical_basis == "market_data_history" else "imported_history_equivalent",
            price_basis=DIAGNOSTICS_PRICE_BASIS,
            note=provenance_note,
        ),
    )


def _build_synthetic_snapshot_history_states(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
) -> list[DailyPortfolioState]:
    if not valuation_dates or not snapshot.positions:
        return []

    base_currency = snapshot.statement.base_currency or 'USD'
    total_cash = sum(float(balance.ending_cash or 0.0) for balance in snapshot.cash_balances)
    fallback_prices = {
        position.symbol: float(position.close_price or 0.0) if position.close_price is not None else (float(position.market_value) / float(position.quantity) if position.quantity not in (None, 0) else None)
        for position in snapshot.positions
    }

    history_by_symbol: dict[str, dict[str, float]] = {}
    first_date = valuation_dates[0]
    for symbol, rows in price_histories.items():
        ordered_rows = sorted(rows, key=lambda row: row['date'])
        row_lookup = {row['date']: float(row['price']) for row in ordered_rows}
        symbol_history: dict[str, float] = {}
        last_price: float | None = None
        first_price = float(ordered_rows[0]['price']) if ordered_rows else fallback_prices.get(symbol)
        for valuation_date in valuation_dates:
            if valuation_date in row_lookup:
                last_price = row_lookup[valuation_date]
            if last_price is not None:
                symbol_history[valuation_date] = last_price
            elif first_price is not None:
                symbol_history[valuation_date] = first_price
        history_by_symbol[symbol] = symbol_history

    synthetic_quantities: dict[str, float] = {}
    for position in snapshot.positions:
        first_price = history_by_symbol.get(position.symbol, {}).get(first_date, fallback_prices.get(position.symbol))
        if first_price is None or first_price <= 0:
            continue
        synthetic_quantities[position.symbol] = float(position.market_value) / float(first_price)

    states: list[DailyPortfolioState] = []
    for valuation_date in valuation_dates:
        state_positions: list[DailyStatePosition] = []
        total_market_value = 0.0
        for position in snapshot.positions:
            quantity = synthetic_quantities.get(position.symbol)
            if quantity is None:
                continue
            price = history_by_symbol.get(position.symbol, {}).get(valuation_date, fallback_prices.get(position.symbol))
            if price is None:
                continue
            market_value = round(quantity * float(price), 2)
            total_market_value += market_value
            state_positions.append(
                DailyStatePosition(
                    symbol=position.symbol,
                    quantity=round(quantity, 6),
                    market_price=float(price),
                    market_value=market_value,
                )
            )

        states.append(
            DailyPortfolioState(
                date=valuation_date,
                cash={base_currency: round(total_cash, 2)},
                positions=state_positions,
                total_market_value=round(total_market_value, 2),
                total_portfolio_value=round(total_market_value + total_cash, 2),
                external_cash_flow=0.0,
            )
        )

    return states


def run_imported_diagnostics_engine(snapshot: ImportedPortfolioSnapshot, benchmark_symbol: str | None = None) -> DiagnosticsResult:
    history_dates = [entry.trade_date.isoformat() for entry in snapshot.ledger_entries if entry.trade_date is not None]
    history_dates.extend(position.as_of_date.isoformat() for position in snapshot.positions if position.as_of_date is not None)
    if not history_dates:
        return build_unavailable_diagnostics_result(
            snapshot,
            benchmark_symbol or DEFAULT_BENCHMARK_SYMBOL,
            snapshot_basis="imported_snapshot",
            reason="missing_imported_history_path",
        )

    history_start_date = min(history_dates)
    history_end_date = max(history_dates)
    resolved_benchmark_symbol = benchmark_symbol or DEFAULT_BENCHMARK_SYMBOL
    return _run_diagnostics_with_history(
        snapshot=snapshot,
        benchmark_symbol=resolved_benchmark_symbol,
        history_start_date=history_start_date,
        history_end_date=history_end_date,
        snapshot_basis="imported_snapshot",
        historical_basis="imported_portfolio_history",
        provenance_note=_build_history_available_provenance_note("imported_portfolio_history"),
    )


def _has_any_symbol_price_history(symbol_price_histories: dict[str, list[dict]]) -> bool:
    return any(rows for rows in symbol_price_histories.values())
