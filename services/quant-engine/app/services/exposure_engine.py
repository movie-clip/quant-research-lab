from app.analytics.portfolio_imports import build_portfolio_overview
from app.analytics.risk import (
    build_lookthrough_exposure,
    build_lookthrough_sector_exposure,
    build_market_overlap_summary,
)
from app.schemas.exposure import ExposureEngineRequest, ExposureResult
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
    )


def run_exposure_engine(request: ExposureEngineRequest) -> ExposureResult:
    snapshot = build_snapshot_from_exposure_request(request)
    return build_exposure_result(snapshot, request.benchmark_symbol)
