from fastapi import APIRouter, HTTPException

from app.schemas.currency_risk import CurrencyRiskRequest, CurrencyRiskResult
from app.services.currency_risk_engine import run_currency_risk_engine

router = APIRouter(prefix="/engines/currency-risk", tags=["currency-risk"])


@router.post("/run", response_model=CurrencyRiskResult)
def run_currency_risk(request: CurrencyRiskRequest) -> CurrencyRiskResult:
    try:
        return run_currency_risk_engine(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
