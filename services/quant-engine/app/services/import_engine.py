from collections.abc import Sequence

from app.schemas.exposure import ExposureAvailability, ExposureCurrentStateConcentration
from app.schemas.imports import ImportedPortfolioSnapshot, SnapshotAnalysisRequest
from app.schemas.import_bootstrap import ImportAdmissionSummaryV1, ImportedBootstrapResponse
from app.schemas.portfolio_engine import PortfolioHistoryContext
from app.schemas.reconciliation import LookThroughOverview, LookThroughSectorExposure, MarketOverlapSummary, PortfolioOverview, PortfolioRiskSummary

from app.services.exposure_engine import build_exposure_result
from app.services.history_context_builder import build_history_context, derive_analysis_window
from app.services.import_admission import build_combined_admission_summary, build_import_admission_summary
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request
from app.services.statement_importer import combine_imported_snapshots, import_statement, scrub_legacy_freedom24_cost_basis


def build_import_bootstrap(statement_paths: str | list[str], benchmark_symbol: str, symbol_overrides: dict[str, list[str]]) -> ImportedBootstrapResponse:
    normalized_paths = [statement_paths] if isinstance(statement_paths, str) else statement_paths
    if not normalized_paths:
        raise ValueError("At least one broker statement is required")
    snapshots = [import_statement(path) for path in normalized_paths]
    response = build_combined_import_bootstrap(snapshots, benchmark_symbol, symbol_overrides)
    if len(snapshots) > 1:
        response.constituent_snapshots = snapshots
    return response


def build_combined_import_bootstrap(
    snapshots: Sequence[ImportedPortfolioSnapshot],
    benchmark_symbol: str,
    symbol_overrides: dict[str, list[str]],
    carried_admissions: Sequence[ImportAdmissionSummaryV1] = (),
) -> ImportedBootstrapResponse:
    """The one seam where a multi-statement portfolio is combined and labelled.

    Flat combine of the individual ``snapshots`` (same account replaces, distinct
    accounts sum; refused combines raise ValueError), exposure and history context
    from the combined snapshot, and the D-3 admission roll-up over every input,
    the recompute on the combined snapshot and any ``carried_admissions``.
    A single input with no carried evidence equals ``build_import_bootstrap_from_snapshot``.
    """
    # D-5 / D-12: stored snapshots from before US-46.4 carry an invented Freedom24
    # cost basis; scrub it before anything is combined or derived from it.
    snapshots = [scrub_legacy_freedom24_cost_basis(snapshot) for snapshot in snapshots]
    combined = combine_imported_snapshots(snapshots)
    admission_summary = build_combined_admission_summary(snapshots, combined, carried_admissions)
    return _build_bootstrap(combined, benchmark_symbol, symbol_overrides, admission_summary)


def build_import_bootstrap_from_portfolio_snapshot_request(request: SnapshotAnalysisRequest) -> ImportedBootstrapResponse:
    snapshot = build_imported_snapshot_from_request(request)
    return build_import_bootstrap_from_snapshot(snapshot, request.benchmark_symbol, {})


def _compose_import_bootstrap_response(
    snapshot,
    overview: PortfolioOverview,
    lookthrough: LookThroughOverview,
    lookthrough_sector_exposure: list[LookThroughSectorExposure],
    market_overlap: MarketOverlapSummary,
    current_state_concentration: ExposureCurrentStateConcentration,
    availability: ExposureAvailability,
    risk_summary: PortfolioRiskSummary,
    admission_summary: ImportAdmissionSummaryV1,
    history_context: PortfolioHistoryContext | None,
) -> ImportedBootstrapResponse:
    return ImportedBootstrapResponse(
        snapshot=snapshot,
        overview=overview,
        lookthrough=lookthrough,
        lookthrough_sector_exposure=lookthrough_sector_exposure,
        market_overlap=market_overlap,
        current_state_concentration=current_state_concentration,
        availability=availability,
        risk_summary=risk_summary,
        admission_summary=admission_summary,
        history_context=history_context,
    )


def build_import_bootstrap_from_snapshot(
    snapshot: ImportedPortfolioSnapshot,
    benchmark_symbol: str,
    symbol_overrides: dict[str, list[str]],
) -> ImportedBootstrapResponse:
    return _build_bootstrap(snapshot, benchmark_symbol, symbol_overrides, build_import_admission_summary(snapshot))


def _build_bootstrap(
    snapshot: ImportedPortfolioSnapshot,
    benchmark_symbol: str,
    symbol_overrides: dict[str, list[str]],
    admission_summary: ImportAdmissionSummaryV1,
) -> ImportedBootstrapResponse:
    exposure_result = build_exposure_result(snapshot, benchmark_symbol, symbol_overrides)
    start_date, end_date = derive_analysis_window(snapshot)
    history_context = build_history_context(snapshot, benchmark_symbol)
    return _compose_import_bootstrap_response(
        snapshot=snapshot,
        overview=exposure_result.overview,
        lookthrough=exposure_result.lookthrough,
        lookthrough_sector_exposure=exposure_result.lookthrough_sector_exposure,
        market_overlap=exposure_result.market_overlap,
        current_state_concentration=exposure_result.current_state_concentration,
        availability=exposure_result.availability,
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
        admission_summary=admission_summary,
        history_context=history_context,
    )
