from fastapi import APIRouter, HTTPException

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.dashboard_history import DashboardHistoryEngineRequest, DashboardHistoryResult
from app.services.dashboard_history_engine import run_dashboard_history_engine, run_imported_dashboard_history


router = APIRouter(prefix="/engines/dashboard-history", tags=["dashboard-history-engine"])


@router.post("/run", response_model=DashboardHistoryResult)
def run_dashboard_history(request: DashboardHistoryEngineRequest) -> DashboardHistoryResult:
    try:
        return run_dashboard_history_engine(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run-imported", response_model=DashboardHistoryResult)
def run_imported_dashboard_history_route(snapshot: ImportedPortfolioSnapshot) -> DashboardHistoryResult:
    try:
        return run_imported_dashboard_history(snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
