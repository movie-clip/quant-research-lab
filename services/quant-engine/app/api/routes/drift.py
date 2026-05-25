from fastapi import APIRouter, HTTPException

from app.schemas.drift import DriftEngineRequest, DriftResult
from app.services.drift_engine import run_drift_engine

router = APIRouter(prefix="/engines/drift", tags=["drift-engine"])


@router.post("/run", response_model=DriftResult)
def run_drift(request: DriftEngineRequest) -> DriftResult:
    try:
        return run_drift_engine(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
