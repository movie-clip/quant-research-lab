from fastapi import APIRouter, HTTPException

from app.schemas.drawdown import DrawdownEngineRequest, DrawdownEngineResponse
from app.services.drawdown_engine import run_drawdown_engine


router = APIRouter(prefix="/engines/drawdown", tags=["drawdown-engine"])


@router.post("/run", response_model=DrawdownEngineResponse)
def run_drawdown(request: DrawdownEngineRequest) -> DrawdownEngineResponse:
    try:
        return run_drawdown_engine(request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
