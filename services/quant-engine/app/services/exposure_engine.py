from app.analytics.portfolio_imports import build_portfolio_overview
from app.analytics.risk import (
    build_lookthrough_exposure,
    build_lookthrough_sector_exposure,
    build_market_overlap_summary,
)
from app.schemas.exposure import ExposureAvailability, ExposureEngineRequest, ExposureResult
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioEngineRequest
from app.schemas.reconciliation import LookThroughOverview
from app.services.market_data import MarketDataService
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request


def build_snapshot_from_exposure_request(request: PortfolioEngineRequest) -> ImportedPortfolioSnapshot:
    return build_imported_snapshot_from_request(request)


def build_exposure_result(snapshot: ImportedPortfolioSnapshot, benchmark_symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> ExposureResult:
    benchmark_symbol = benchmark_symbol or 'SPY'
    symbol_overrides = symbol_overrides or {}

    market_data = MarketDataService()
    lookthrough_constituents, etf_resolution, uncovered_positions, covered_market_value = build_lookthrough_exposure(snapshot, market_data, symbol_overrides)
    total_market_value = round(sum(position.market_value for position in snapshot.positions), 2)
    _, benchmark_holdings = market_data.get_etf_holdings(benchmark_symbol)
    lookthrough_sector_exposure = build_lookthrough_sector_exposure(lookthrough_constituents)
    market_overlap = build_market_overlap_summary(lookthrough_constituents, benchmark_symbol, benchmark_holdings)
    availability = _build_exposure_availability(
        total_market_value=total_market_value,
        lookthrough_constituents=lookthrough_constituents,
        uncovered_positions=uncovered_positions,
        benchmark_holdings=benchmark_holdings,
    )

    return ExposureResult(
        snapshot=snapshot,
        overview=build_portfolio_overview(snapshot),
        lookthrough=LookThroughOverview(
            portfolio_market_value=total_market_value,
            covered_market_value=round(covered_market_value, 2),
            coverage_ratio=round((covered_market_value / total_market_value), 4) if total_market_value else 0.0,
            etf_resolution=etf_resolution,
            uncovered_positions=sorted(uncovered_positions),
            top_constituents=lookthrough_constituents[:25],
        ),
        lookthrough_sector_exposure=lookthrough_sector_exposure,
        market_overlap=market_overlap,
        availability=availability,
    )


def run_exposure_engine(request: ExposureEngineRequest) -> ExposureResult:
    snapshot = build_snapshot_from_exposure_request(request)
    return build_exposure_result(snapshot, request.benchmark_symbol)


def _build_exposure_availability(
    total_market_value: float,
    lookthrough_constituents,
    uncovered_positions: list[str],
    benchmark_holdings: list[dict],
) -> ExposureAvailability:
    if total_market_value <= 0 or not lookthrough_constituents:
        return ExposureAvailability(
            lookthrough_status="unavailable",
            lookthrough_confidence="low",
            benchmark_overlap_status="unavailable",
            benchmark_overlap_confidence="low",
            note="Look-through exposure is unavailable for this snapshot because no resolvable holdings were produced.",
        )

    lookthrough_status = "partial" if uncovered_positions else "live"
    lookthrough_confidence = "medium" if uncovered_positions else "high"
    if not benchmark_holdings:
        benchmark_overlap_status = "unavailable"
        benchmark_overlap_confidence = "low"
    elif lookthrough_status != "live":
        benchmark_overlap_status = "partial"
        benchmark_overlap_confidence = "medium"
    else:
        benchmark_overlap_status = "live"
        benchmark_overlap_confidence = "high"

    if lookthrough_status == "live" and benchmark_overlap_status == "live":
        note = None
    elif lookthrough_status == "partial" and benchmark_overlap_status == "unavailable":
        note = "Look-through exposure is partial because some holdings could not be resolved, and benchmark overlap is unavailable because benchmark composition could not be loaded."
    elif lookthrough_status == "partial":
        note = "Look-through exposure is partial because some holdings could not be resolved from ETF constituents. Constituent coverage counts only direct single-name positions and ETFs with resolved holdings."
    elif benchmark_overlap_status == "unavailable":
        note = "Benchmark-relative overlap is unavailable because benchmark holdings could not be loaded. Overlap metrics render as unavailable rather than as implied zero overlap. Current look-through exposure is still shown."
    else:
        note = "Exposure is available with partial benchmark-relative coverage."

    return ExposureAvailability(
        lookthrough_status=lookthrough_status,
        lookthrough_confidence=lookthrough_confidence,
        benchmark_overlap_status=benchmark_overlap_status,
        benchmark_overlap_confidence=benchmark_overlap_confidence,
        note=note,
    )
