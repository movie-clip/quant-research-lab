from fastapi import APIRouter, HTTPException

from app.schemas.exposure import ExposureEngineRequest, ExposureResult
from app.services.exposure_engine import run_exposure_engine


router = APIRouter(prefix="/engines/exposure", tags=["exposure-engine"])


@router.post("/run", response_model=ExposureResult)
def run_exposure(request: ExposureEngineRequest) -> ExposureResult:
    try:
        return run_exposure_engine(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
