from fastapi import APIRouter, HTTPException

from app.schemas.provenance import ProvenanceRequest, ProvenanceResult
from app.services.provenance_engine import run_provenance

router = APIRouter(prefix="/engines/provenance", tags=["provenance-engine"])


@router.post("/run", response_model=ProvenanceResult)
def run_provenance_route(request: ProvenanceRequest) -> ProvenanceResult:
    try:
        return run_provenance(request)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
