from app.schemas.imports import ImportedPortfolioSnapshot, SnapshotAnalysisRequest
from app.schemas.import_bootstrap import ImportedBootstrapResponse
from app.schemas.reconciliation import PortfolioRiskSummary

from app.services.import_engine_composer import compose_import_bootstrap_response
from app.services.exposure_engine import build_exposure_result
from app.services.history_context_builder import build_history_context, derive_analysis_window
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request
from app.services.statement_importer import import_statements


def build_import_bootstrap(statement_paths: str | list[str], benchmark_symbol: str, symbol_overrides: dict[str, list[str]]) -> ImportedBootstrapResponse:
    normalized_paths = [statement_paths] if isinstance(statement_paths, str) else statement_paths
    snapshot = import_statements(normalized_paths)
    return build_import_bootstrap_from_snapshot(snapshot, benchmark_symbol, symbol_overrides)


def build_import_bootstrap_from_portfolio_snapshot_request(request: SnapshotAnalysisRequest) -> ImportedBootstrapResponse:
    snapshot = build_imported_snapshot_from_request(request)
    return build_import_bootstrap_from_snapshot(snapshot, request.benchmark_symbol, {})


def build_import_bootstrap_from_snapshot(
    snapshot: ImportedPortfolioSnapshot,
    benchmark_symbol: str,
    symbol_overrides: dict[str, list[str]],
) -> ImportedBootstrapResponse:
    exposure_result = build_exposure_result(snapshot, benchmark_symbol, symbol_overrides)
    start_date, end_date = derive_analysis_window(snapshot)
    history_context = build_history_context(snapshot, benchmark_symbol)
    return compose_import_bootstrap_response(
        snapshot=snapshot,
        overview=exposure_result.overview,
        risk_summary=PortfolioRiskSummary(
            benchmark_symbol=benchmark_symbol,
            methodology='import_bootstrap',
            start_date=start_date,
            end_date=end_date,
            observations=0,
            portfolio_beta=None,
            portfolio_correlation=None,
            r_squared=None,
            portfolio_volatility_pct=None,
            benchmark_volatility_pct=None,
        ),
        history_context=history_context,
    )
