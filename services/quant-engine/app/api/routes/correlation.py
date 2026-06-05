from fastapi import APIRouter, HTTPException

from app.schemas.correlation import (
    MultiBenchmarkCorrelationRequest,
    MultiBenchmarkCorrelationResult,
)
from app.schemas.intra_correlation import (
    IntraCorrelationRequest,
    IntraCorrelationResult,
)
from app.services.correlation_engine import run_multi_benchmark_correlation
from app.services.intra_correlation_engine import run_intra_correlation

router = APIRouter(prefix="/engines/correlation", tags=["correlation-engine"])


@router.post("/multi", response_model=MultiBenchmarkCorrelationResult)
def run_multi_correlation(
    request: MultiBenchmarkCorrelationRequest,
) -> MultiBenchmarkCorrelationResult:
    try:
        return run_multi_benchmark_correlation(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/intra", response_model=IntraCorrelationResult)
def run_intra_correlation_route(
    request: IntraCorrelationRequest,
) -> IntraCorrelationResult:
    try:
        return run_intra_correlation(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
