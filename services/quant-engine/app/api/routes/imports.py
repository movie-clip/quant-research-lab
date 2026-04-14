import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.schemas.imported_analysis import ImportedBootstrapResponse
from app.schemas.imports import ImportedPortfolioSnapshot, SnapshotAnalysisRequest
from app.services.import_engine import build_import_bootstrap, build_import_bootstrap_from_portfolio_snapshot_request
from app.services.statement_importer import import_statements


router = APIRouter(prefix="/portfolios/import", tags=["imports"])


class InteractiveBrokersImportRequest(BaseModel):
    statement_path: str | None = None
    statement_paths: list[str] = Field(default_factory=list)
    benchmark_symbol: str = "SPY"
    symbol_overrides: dict[str, list[str]] = Field(default_factory=dict)


def _resolve_statement_paths(request: InteractiveBrokersImportRequest) -> list[Path]:
    raw_paths = request.statement_paths or ([request.statement_path] if request.statement_path else [])
    if not raw_paths:
        raise HTTPException(status_code=400, detail="At least one statement file is required")

    resolved_paths = [Path(raw_path) for raw_path in raw_paths]
    missing_path = next((path for path in resolved_paths if not path.exists()), None)
    if missing_path is not None:
        raise HTTPException(status_code=404, detail=f"Statement file not found: {missing_path}")

    return resolved_paths


@router.post("/interactive-brokers", response_model=ImportedPortfolioSnapshot)
def import_interactive_brokers_statement(
    request: InteractiveBrokersImportRequest,
) -> ImportedPortfolioSnapshot:
    paths = _resolve_statement_paths(request)

    try:
        return import_statements([str(path) for path in paths])
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/interactive-brokers/analyze", response_model=ImportedBootstrapResponse)
def analyze_interactive_brokers_statement(
    request: InteractiveBrokersImportRequest,
) -> ImportedBootstrapResponse:
    paths = _resolve_statement_paths(request)

    try:
        return build_import_bootstrap([str(path) for path in paths], request.benchmark_symbol, request.symbol_overrides)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/interactive-brokers/analyze-upload", response_model=ImportedBootstrapResponse)
async def analyze_uploaded_interactive_brokers_statement(
    statement_files: list[UploadFile] = File(...),
    benchmark_symbol: str = Form("SPY"),
    symbol_overrides: str = Form("{}"),
) -> ImportedBootstrapResponse:
    try:
        parsed_overrides = json.loads(symbol_overrides)
        if not isinstance(parsed_overrides, dict):
            raise ValueError
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Symbol overrides must be valid JSON") from exc

    if not statement_files:
        raise HTTPException(status_code=400, detail="At least one statement file is required")

    temp_paths: list[Path] = []
    for statement_file in statement_files:
        suffix = Path(statement_file.filename or "statement.pdf").suffix or ".pdf"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(await statement_file.read())
            temp_paths.append(temp_path)

    try:
        return build_import_bootstrap([str(temp_path) for temp_path in temp_paths], benchmark_symbol, parsed_overrides)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        for temp_path in temp_paths:
            temp_path.unlink(missing_ok=True)


@router.post("/interactive-brokers/analyze-snapshot", response_model=ImportedBootstrapResponse)
def analyze_snapshot_portfolio(
    request: SnapshotAnalysisRequest,
) -> ImportedBootstrapResponse:
    try:
        return build_import_bootstrap_from_portfolio_snapshot_request(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
