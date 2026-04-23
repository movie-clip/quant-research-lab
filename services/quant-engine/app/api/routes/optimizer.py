from fastapi import APIRouter, HTTPException

from app.schemas.optimizer import OptimizerPreviewRequest, OptimizerPreviewResponse
from app.services.optimizer_preview_service import build_optimizer_preview


router = APIRouter(prefix="/optimizer", tags=["optimizer"])


@router.post("/preview", response_model=OptimizerPreviewResponse)
def run_optimizer_preview(request: OptimizerPreviewRequest) -> OptimizerPreviewResponse:
    try:
        return build_optimizer_preview(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
