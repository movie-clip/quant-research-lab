from fastapi import APIRouter, HTTPException

from app.schemas.attribution import FactorAttributionRequest, FactorAttributionResponse
from app.services.attribution_engine import run_attribution_engine


router = APIRouter(prefix="/engines/attribution", tags=["attribution-engine"])


@router.post("/run", response_model=FactorAttributionResponse)
def run_attribution(request: FactorAttributionRequest) -> FactorAttributionResponse:
    try:
        return run_attribution_engine(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
