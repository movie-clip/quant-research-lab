from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query

from app.schemas.backtest_engine import BacktestConfig, BacktestRequest, ConstructionArtifactPreviewOpenRequest, ConstructionArtifactReplayRequest, ConstructionArtifactReplayResponse, ConstructionArtifactReplayValidationResponse, CreateMonitorDefinitionRequest, EvaluateMonitorDefinitionObservationRequest, HypotheticalReplacementReplayRequest, HypotheticalReplacementReplayResponse, MonitorDefinitionArtifact, MonitorDefinitionArtifactListResponse, MonitorDefinitionCatalogResponse, MonitorDefinitionDiscoveryFilters, MonitorDefinitionDiscoveryLifecycleStatus, MonitorDefinitionDiscoveryReviewSupportStatus, MonitorDefinitionEvaluationHistoryEntryResponse, MonitorDefinitionEvaluationHistoryResponse, MonitorDefinitionLatestEvaluationSnapshotRecency, MonitorDefinitionLatestEvaluationSnapshotStatus, MonitorDefinitionObservationEvaluationResponse, MonitorDefinitionOverlayFamily, MonitorDefinitionRecentResponse, OptimizerHandoffReplayRequest, OptimizerHandoffReplayResponse, OptimizerHandoffValidationRequest, OptimizerHandoffValidationResponse, OverlayAwareHypotheticalReplayRequest, OverlayAwareHypotheticalReplayResponse, PortfolioAllocationBacktestRequest, PortfolioAllocationBacktestResponse, SingleReplacementCandidateConstructionRequest, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationRequest, SingleReplacementCandidateFormationResponse, SingleReplacementConstructionConstraintValidationRequest, SingleReplacementConstructionConstraintValidationResponse
from app.schemas.research import BacktestFrequency, ContinuousSeriesSpec, StrategyDefinition
from app.services.backtest_engine_service import BacktestAnalysisResult, build_backtest_analysis
from app.services.candidate_constraints import CONSTRAINT_SET_ID, validate_single_replacement_candidate_construction_constraints
from app.services.candidate_construction import build_single_replacement_candidate_construction
from app.services.candidate_formation import build_single_replacement_candidate_formation
from app.services.construction_artifact_service import (
    ConstructionArtifactIntegrityValidationError,
    ConstructionArtifactInvalidJsonError,
    ConstructionArtifactMissingFileError,
    ConstructionArtifactNonObjectPayloadError,
    ConstructionArtifactPersistenceError,
    ConstructionArtifactSchemaValidationError,
)
from app.services.optimizer_handoff_constraints import OptimizerHandoffValidationBlockedError, validate_optimizer_handoff_constraints
from app.services.monitor_definition_artifact_service import MonitorDefinitionDiscoveryMetadataValidationError, MonitorDefinitionIntegrityValidationError, MonitorDefinitionInvalidJsonError, MonitorDefinitionMissingFileError, MonitorDefinitionNonObjectPayloadError, MonitorDefinitionPersistenceError, MonitorDefinitionSchemaValidationError, create_monitor_definition_artifact, inspect_monitor_definition_evaluation_history_entry, list_monitor_definition_artifacts, list_monitor_definition_catalog, list_monitor_definition_evaluation_history, list_recent_monitor_definition_artifacts, load_monitor_definition_artifact
from app.services.portfolio_backtest_engine import build_construction_artifact_replay_preview, build_hypothetical_replacement_replay_preview, build_optimizer_handoff_replay_preview, build_overlay_aware_hypothetical_replay_preview, build_portfolio_allocation_backtest_analysis, evaluate_monitor_definition_observation, validate_construction_artifact_replay_params


router = APIRouter(prefix="/backtests", tags=["backtests"])

ALLOWED_BACKTEST_FREQUENCIES: set[BacktestFrequency] = {"1d", "1h", "15m", "5m"}
MONITOR_DEFINITION_READ_ERRORS = (
    MonitorDefinitionMissingFileError,
    MonitorDefinitionInvalidJsonError,
    MonitorDefinitionNonObjectPayloadError,
    MonitorDefinitionSchemaValidationError,
    MonitorDefinitionIntegrityValidationError,
    MonitorDefinitionDiscoveryMetadataValidationError,
    MonitorDefinitionPersistenceError,
)
MONITOR_DEFINITION_LOAD_ERRORS = MONITOR_DEFINITION_READ_ERRORS[1:]


@router.post("/run", response_model=BacktestAnalysisResult)
def run_backtest(request: BacktestRequest) -> BacktestAnalysisResult:
    if request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")

    if request.timeframe not in ALLOWED_BACKTEST_FREQUENCIES:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")

    config = BacktestConfig(
        strategy=StrategyDefinition(strategy_id=request.strategy_id, name=request.strategy_id, timeframe=request.timeframe, universe=request.universe),
        benchmark_symbol=request.benchmark_symbol,
        start_date=request.start_date,
        end_date=request.end_date,
        initial_capital=request.initial_capital,
        base_currency=request.base_currency,
        slippage_bps=request.slippage_bps,
        commission_per_contract=request.commission_per_contract,
        use_continuous_contracts=request.use_continuous_contracts,
        continuous_series=ContinuousSeriesSpec(root_symbol=request.universe[0]) if request.universe and request.use_continuous_contracts else None,
    )

    try:
        return build_backtest_analysis(config)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio-allocation", response_model=PortfolioAllocationBacktestResponse)
def run_portfolio_allocation_backtest(request: PortfolioAllocationBacktestRequest) -> PortfolioAllocationBacktestResponse:
    if request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    if request.initial_capital <= 0:
        raise HTTPException(status_code=400, detail="initial_capital must be positive")
    if request.execution_lag_days < 1:
        raise HTTPException(status_code=400, detail="execution_lag_days must be at least 1")
    if not request.weights:
        raise HTTPException(status_code=400, detail="weights must not be empty")
    _validate_weights(request.weights, "weights")
    if request.reference_weights is not None:
        _validate_weights(request.reference_weights, "reference_weights")

    try:
        return build_portfolio_allocation_backtest_analysis(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio-allocation/replacement-intent-preview", response_model=HypotheticalReplacementReplayResponse)
def run_hypothetical_replacement_preview(request: HypotheticalReplacementReplayRequest) -> HypotheticalReplacementReplayResponse:
    if request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    if request.initial_capital <= 0:
        raise HTTPException(status_code=400, detail="initial_capital must be positive")
    if request.execution_lag_days < 1:
        raise HTTPException(status_code=400, detail="execution_lag_days must be at least 1")

    try:
        return build_hypothetical_replacement_replay_preview(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio-allocation/optimizer-handoff-preview", response_model=OptimizerHandoffReplayResponse)
def run_optimizer_handoff_replay_preview(request: OptimizerHandoffReplayRequest) -> OptimizerHandoffReplayResponse:
    if request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    if request.initial_capital <= 0:
        raise HTTPException(status_code=400, detail="initial_capital must be positive")
    if request.execution_lag_days < 1:
        raise HTTPException(status_code=400, detail="execution_lag_days must be at least 1")

    try:
        return build_optimizer_handoff_replay_preview(request)
    except OptimizerHandoffValidationBlockedError as exc:
        raise HTTPException(status_code=400, detail=exc.response.model_dump(mode="json")) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio-allocation/construction-artifact-preview", response_model=ConstructionArtifactReplayResponse)
def run_construction_artifact_replay_preview(request: ConstructionArtifactPreviewOpenRequest) -> ConstructionArtifactReplayResponse:
    try:
        return build_construction_artifact_replay_preview(request.root)
    except ConstructionArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ConstructionArtifactInvalidJsonError,
        ConstructionArtifactNonObjectPayloadError,
        ConstructionArtifactSchemaValidationError,
        ConstructionArtifactIntegrityValidationError,
        ConstructionArtifactPersistenceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio-allocation/construction-artifact-validation", response_model=ConstructionArtifactReplayValidationResponse)
def run_construction_artifact_replay_validation(request: ConstructionArtifactReplayRequest) -> ConstructionArtifactReplayValidationResponse:
    try:
        return validate_construction_artifact_replay_params(request)
    except ConstructionArtifactMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (
        ConstructionArtifactInvalidJsonError,
        ConstructionArtifactNonObjectPayloadError,
        ConstructionArtifactSchemaValidationError,
        ConstructionArtifactIntegrityValidationError,
        ConstructionArtifactPersistenceError,
    ) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio-allocation/optimizer-handoff/constraints", response_model=OptimizerHandoffValidationResponse)
def run_optimizer_handoff_constraints(request: OptimizerHandoffValidationRequest) -> OptimizerHandoffValidationResponse:
    if request.start_date is not None and request.end_date is not None and request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    try:
        return validate_optimizer_handoff_constraints(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/portfolio-allocation/replacement-intent-overlay-preview", response_model=OverlayAwareHypotheticalReplayResponse)
def run_overlay_aware_hypothetical_replacement_preview(request: OverlayAwareHypotheticalReplayRequest) -> OverlayAwareHypotheticalReplayResponse:
    if request.end_date < request.start_date:
        raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
    if request.initial_capital <= 0:
        raise HTTPException(status_code=400, detail="initial_capital must be positive")
    if request.execution_lag_days < 1:
        raise HTTPException(status_code=400, detail="execution_lag_days must be at least 1")

    try:
        return build_overlay_aware_hypothetical_replay_preview(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/monitor-definitions", response_model=MonitorDefinitionArtifact)
def create_monitor_definition(request: CreateMonitorDefinitionRequest) -> MonitorDefinitionArtifact:
    try:
        return create_monitor_definition_artifact(request)
    except (MonitorDefinitionIntegrityValidationError, MonitorDefinitionPersistenceError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/monitor-definitions", response_model=MonitorDefinitionArtifactListResponse)
def list_monitor_definitions() -> MonitorDefinitionArtifactListResponse:
    try:
        return MonitorDefinitionArtifactListResponse(items=list_monitor_definition_artifacts())
    except MONITOR_DEFINITION_READ_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/monitor-definitions/catalog", response_model=MonitorDefinitionCatalogResponse)
def get_monitor_definition_catalog(
    overlay_family: MonitorDefinitionOverlayFamily | None = Query(default=None),
    monitor_id: Literal["benchmark_trend_overlay_v1"] | None = Query(default=None),
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus | None = Query(default=None),
    lifecycle_status: MonitorDefinitionDiscoveryLifecycleStatus | None = Query(default=None),
    latest_evaluation_snapshot_status: MonitorDefinitionLatestEvaluationSnapshotStatus | None = Query(default=None),
    latest_evaluation_snapshot_recency: MonitorDefinitionLatestEvaluationSnapshotRecency | None = Query(default=None),
) -> MonitorDefinitionCatalogResponse:
    try:
        return list_monitor_definition_catalog(
            filters=_monitor_definition_discovery_filters(
                overlay_family=overlay_family,
                monitor_id=monitor_id,
                review_support_status=review_support_status,
                lifecycle_status=lifecycle_status,
                latest_evaluation_snapshot_status=latest_evaluation_snapshot_status,
                latest_evaluation_snapshot_recency=latest_evaluation_snapshot_recency,
            )
        )
    except MONITOR_DEFINITION_READ_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/monitor-definitions/recent", response_model=MonitorDefinitionRecentResponse)
def get_recent_monitor_definitions(
    limit: int = Query(20, ge=1, le=100),
    overlay_family: MonitorDefinitionOverlayFamily | None = Query(default=None),
    monitor_id: Literal["benchmark_trend_overlay_v1"] | None = Query(default=None),
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus | None = Query(default=None),
    lifecycle_status: MonitorDefinitionDiscoveryLifecycleStatus | None = Query(default=None),
    latest_evaluation_snapshot_status: MonitorDefinitionLatestEvaluationSnapshotStatus | None = Query(default=None),
    latest_evaluation_snapshot_recency: MonitorDefinitionLatestEvaluationSnapshotRecency | None = Query(default=None),
) -> MonitorDefinitionRecentResponse:
    try:
        return list_recent_monitor_definition_artifacts(
            limit=limit,
            filters=_monitor_definition_discovery_filters(
                overlay_family=overlay_family,
                monitor_id=monitor_id,
                review_support_status=review_support_status,
                lifecycle_status=lifecycle_status,
                latest_evaluation_snapshot_status=latest_evaluation_snapshot_status,
                latest_evaluation_snapshot_recency=latest_evaluation_snapshot_recency,
            ),
        )
    except MONITOR_DEFINITION_READ_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/monitor-definitions/{monitor_definition_id}", response_model=MonitorDefinitionArtifact)
def get_monitor_definition(monitor_definition_id: str) -> MonitorDefinitionArtifact:
    try:
        return load_monitor_definition_artifact(monitor_definition_id)
    except MonitorDefinitionMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MONITOR_DEFINITION_LOAD_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/monitor-definitions/{monitor_definition_id}/evaluations",
    response_model=MonitorDefinitionObservationEvaluationResponse,
)
def evaluate_monitor_definition(
    monitor_definition_id: str,
    request: EvaluateMonitorDefinitionObservationRequest,
) -> MonitorDefinitionObservationEvaluationResponse:
    try:
        return evaluate_monitor_definition_observation(monitor_definition_id, request)
    except MonitorDefinitionMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MONITOR_DEFINITION_LOAD_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/monitor-definitions/{monitor_definition_id}/evaluation-history",
    response_model=MonitorDefinitionEvaluationHistoryResponse,
)
def get_monitor_definition_evaluation_history(
    monitor_definition_id: str,
    limit: int | None = Query(default=None, ge=1, le=100),
) -> MonitorDefinitionEvaluationHistoryResponse:
    try:
        return list_monitor_definition_evaluation_history(monitor_definition_id, limit=limit)
    except MonitorDefinitionMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MONITOR_DEFINITION_LOAD_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/monitor-definitions/{monitor_definition_id}/evaluation-history/{history_entry_id}",
    response_model=MonitorDefinitionEvaluationHistoryEntryResponse,
)
def inspect_monitor_definition_evaluation_history(
    monitor_definition_id: str,
    history_entry_id: str,
) -> MonitorDefinitionEvaluationHistoryEntryResponse:
    try:
        return inspect_monitor_definition_evaluation_history_entry(monitor_definition_id, history_entry_id)
    except MonitorDefinitionMissingFileError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except MONITOR_DEFINITION_LOAD_ERRORS as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/candidate-formation/replacement-intent", response_model=SingleReplacementCandidateFormationResponse)
def run_single_replacement_candidate_formation(request: SingleReplacementCandidateFormationRequest) -> SingleReplacementCandidateFormationResponse:
    return build_single_replacement_candidate_formation(request)


@router.post("/candidate-construction/replacement-intent", response_model=SingleReplacementCandidateConstructionResponse)
def run_single_replacement_candidate_construction(request: SingleReplacementCandidateConstructionRequest) -> SingleReplacementCandidateConstructionResponse:
    return build_single_replacement_candidate_construction(request)


@router.post("/candidate-construction/replacement-intent/constraints", response_model=SingleReplacementConstructionConstraintValidationResponse)
def run_single_replacement_candidate_construction_constraints(
    request: SingleReplacementConstructionConstraintValidationRequest,
) -> SingleReplacementConstructionConstraintValidationResponse:
    if request.constructed_candidate is None:
        raise HTTPException(status_code=400, detail="constructed_candidate is required")
    if request.constraint_set is None:
        raise HTTPException(status_code=400, detail="constraint_set is required")
    if request.constraint_set.constraint_set_id != CONSTRAINT_SET_ID:
        raise HTTPException(status_code=400, detail=f"unsupported constraint_set_id: {request.constraint_set.constraint_set_id}")
    return validate_single_replacement_candidate_construction_constraints(request)


def _validate_weights(weights, field_name: str) -> None:
    total = sum(item.target_weight for item in weights)
    if not all(item.symbol for item in weights):
        raise HTTPException(status_code=400, detail=f"{field_name} must include symbols")
    if any(item.target_weight < 0 for item in weights):
        raise HTTPException(status_code=400, detail=f"{field_name} must not contain negative target_weight values")
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"{field_name} must sum to approximately 1.0")


def _monitor_definition_discovery_filters(
    *,
    overlay_family: MonitorDefinitionOverlayFamily | None,
    monitor_id: Literal["benchmark_trend_overlay_v1"] | None,
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus | None,
    lifecycle_status: MonitorDefinitionDiscoveryLifecycleStatus | None,
    latest_evaluation_snapshot_status: MonitorDefinitionLatestEvaluationSnapshotStatus | None,
    latest_evaluation_snapshot_recency: MonitorDefinitionLatestEvaluationSnapshotRecency | None,
) -> MonitorDefinitionDiscoveryFilters:
    return MonitorDefinitionDiscoveryFilters.model_validate(
        {
            "overlay_family": overlay_family,
            "monitor_id": monitor_id,
            "review_support_status": review_support_status,
            "lifecycle_status": lifecycle_status,
            "latest_evaluation_snapshot_status": latest_evaluation_snapshot_status,
            "latest_evaluation_snapshot_recency": latest_evaluation_snapshot_recency,
        }
    )
