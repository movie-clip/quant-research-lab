from fastapi import APIRouter, HTTPException

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.diagnostics import DiagnosticsEngineRequest, DiagnosticsResult
from app.services.diagnostics_engine import run_diagnostics_engine, run_imported_diagnostics_engine


router = APIRouter(prefix="/engines/diagnostics", tags=["diagnostics-engine"])


@router.post("/run", response_model=DiagnosticsResult)
def run_diagnostics(request: DiagnosticsEngineRequest) -> DiagnosticsResult:
    try:
        return run_diagnostics_engine(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/run-imported", response_model=DiagnosticsResult)
def run_imported_diagnostics(snapshot: ImportedPortfolioSnapshot) -> DiagnosticsResult:
    try:
        return run_imported_diagnostics_engine(snapshot)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
