from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.backtest_engine import BacktestConfig, BacktestRequest, HypotheticalReplacementReplayRequest, HypotheticalReplacementReplayResponse, PortfolioAllocationBacktestRequest, PortfolioAllocationBacktestResponse, SingleReplacementCandidateConstructionRequest, SingleReplacementCandidateConstructionResponse, SingleReplacementCandidateFormationRequest, SingleReplacementCandidateFormationResponse
from app.schemas.research import BacktestFrequency, ContinuousSeriesSpec, StrategyDefinition
from app.services.backtest_engine_service import BacktestAnalysisResult, build_backtest_analysis
from app.services.candidate_construction import build_single_replacement_candidate_construction
from app.services.candidate_formation import build_single_replacement_candidate_formation
from app.services.portfolio_backtest_engine import build_hypothetical_replacement_replay_preview, build_portfolio_allocation_backtest_analysis


router = APIRouter(prefix="/backtests", tags=["backtests"])

ALLOWED_BACKTEST_FREQUENCIES: set[BacktestFrequency] = {"1d", "1h", "15m", "5m"}


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


@router.post("/candidate-formation/replacement-intent", response_model=SingleReplacementCandidateFormationResponse)
def run_single_replacement_candidate_formation(request: SingleReplacementCandidateFormationRequest) -> SingleReplacementCandidateFormationResponse:
    return build_single_replacement_candidate_formation(request)


@router.post("/candidate-construction/replacement-intent", response_model=SingleReplacementCandidateConstructionResponse)
def run_single_replacement_candidate_construction(request: SingleReplacementCandidateConstructionRequest) -> SingleReplacementCandidateConstructionResponse:
    return build_single_replacement_candidate_construction(request)


def _validate_weights(weights, field_name: str) -> None:
    total = sum(item.target_weight for item in weights)
    if not all(item.symbol for item in weights):
        raise HTTPException(status_code=400, detail=f"{field_name} must include symbols")
    if any(item.target_weight < 0 for item in weights):
        raise HTTPException(status_code=400, detail=f"{field_name} must not contain negative target_weight values")
    if abs(total - 1.0) > 0.01:
        raise HTTPException(status_code=400, detail=f"{field_name} must sum to approximately 1.0")
