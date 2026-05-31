from fastapi import APIRouter, HTTPException

from app.schemas.stress import StressEngineRequest, StressEngineResponse
from app.services.stress_engine import run_stress_engine


router = APIRouter(prefix="/engines/stress", tags=["stress-engine"])


@router.post("/run", response_model=StressEngineResponse)
def run_stress(request: StressEngineRequest) -> StressEngineResponse:
    try:
        return run_stress_engine(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
