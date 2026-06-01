from fastapi import APIRouter, HTTPException

from app.schemas.distribution import DistributionEngineRequest, DistributionEngineResponse
from app.services.distribution_engine import run_distribution_engine


router = APIRouter(prefix="/engines/distribution", tags=["distribution-engine"])


@router.post("/run", response_model=DistributionEngineResponse)
def run_distribution(request: DistributionEngineRequest) -> DistributionEngineResponse:
    try:
        return run_distribution_engine(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
