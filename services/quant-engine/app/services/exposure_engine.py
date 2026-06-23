from typing import Literal

from app.analytics.portfolio_imports import build_portfolio_overview
from app.analytics.risk import (
    build_lookthrough_exposure,
    build_lookthrough_sector_exposure,
    build_market_overlap_summary,
)
from app.schemas.exposure import (
    ExposureAvailability,
    ExposureAvailabilityConfidence,
    ExposureConcentrationItem,
    ExposureCurrentStateConcentration,
    ExposureEngineRequest,
    ExposureProvenance,
    ExposureResult,
    ExposureRunMetadata,
    ExposureRunReproducibilityMetadata,
    ExposureRunSourceStatus,
)
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioEngineRequest
from app.schemas.reconciliation import LookThroughOverview, PortfolioOverview
from app.services.market_data import MarketDataService
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request


EXPOSURE_DATASET_VERSION = "market_data_service_v1"

# Benchmark-holdings coverage threshold (US-24.2): the loaded constituent weight
# (sum of weightPercentage) must reach this % for the benchmark-holdings status to
# be "verified"; below it (but > 0) the status degrades. Heuristic policy value.
BENCHMARK_HOLDINGS_VERIFIED_COVERAGE_PCT = 99.0


def build_snapshot_from_exposure_request(request: PortfolioEngineRequest) -> ImportedPortfolioSnapshot:
    return build_imported_snapshot_from_request(request)


def build_exposure_result(snapshot: ImportedPortfolioSnapshot, benchmark_symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> ExposureResult:
    benchmark_symbol = benchmark_symbol or 'SPY'
    symbol_overrides = symbol_overrides or {}
    overview = build_portfolio_overview(snapshot)

    market_data = MarketDataService()
    lookthrough_constituents, etf_resolution, uncovered_positions, covered_market_value = build_lookthrough_exposure(snapshot, market_data, symbol_overrides)
    total_market_value = round(sum(position.market_value for position in snapshot.positions), 2)
    _, benchmark_holdings = market_data.get_etf_holdings(benchmark_symbol)
    lookthrough_sector_exposure = build_lookthrough_sector_exposure(lookthrough_constituents)
    market_overlap = build_market_overlap_summary(lookthrough_constituents, benchmark_symbol, benchmark_holdings)
    current_state_concentration = _build_current_state_concentration(snapshot, overview)
    availability = _build_exposure_availability(
        total_market_value=total_market_value,
        lookthrough_constituents=lookthrough_constituents,
        uncovered_positions=uncovered_positions,
        benchmark_holdings=benchmark_holdings,
    )

    return ExposureResult(
        snapshot=snapshot,
        provenance=ExposureProvenance(
            snapshot_basis="snapshot_request",
            historical_basis="current_state_only",
            price_basis="not_applicable",
            note="Exposure is a current-state engine view built from the submitted snapshot and look-through resolution inputs. Historical diagnostics are separate.",
        ),
        run_metadata=ExposureRunMetadata(
            engine_id="exposure_engine_v1",
            methodology_id="exposure_current_state_methodology_v1",
            price_basis="not_applicable",
            source_status=_build_exposure_source_status(
                total_market_value=total_market_value,
                lookthrough_constituents=lookthrough_constituents,
                uncovered_positions=uncovered_positions,
                benchmark_holdings=benchmark_holdings,
            ),
            confidence=_combine_exposure_confidence(availability.lookthrough_confidence, availability.benchmark_overlap_confidence),
            reproducibility=_build_exposure_reproducibility(snapshot, benchmark_symbol),
        ),
        overview=overview,
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
        current_state_concentration=current_state_concentration,
        availability=availability,
    )


def run_exposure_engine(request: ExposureEngineRequest) -> ExposureResult:
    snapshot = build_snapshot_from_exposure_request(request)
    return build_exposure_result(snapshot, request.benchmark_symbol)


def _build_exposure_source_status(
    total_market_value: float,
    lookthrough_constituents,
    uncovered_positions: list[str],
    benchmark_holdings: list[dict],
) -> ExposureRunSourceStatus:
    lookthrough_resolution: str
    benchmark_holdings_status: Literal["verified", "degraded", "unavailable"] = _classify_benchmark_holdings_support(benchmark_holdings)
    if total_market_value <= 0 or not lookthrough_constituents:
        lookthrough_resolution = "unavailable"
    elif uncovered_positions:
        lookthrough_resolution = "partial"
    else:
        lookthrough_resolution = "live"

    return ExposureRunSourceStatus(
        lookthrough_resolution=lookthrough_resolution,
        benchmark_holdings=benchmark_holdings_status,
    )


def _build_exposure_reproducibility(
    snapshot: ImportedPortfolioSnapshot,
    benchmark_symbol: str,
) -> ExposureRunReproducibilityMetadata:
    snapshot_as_of_date = max((position.as_of_date.isoformat() for position in snapshot.positions if position.as_of_date is not None), default=None)
    return ExposureRunReproducibilityMetadata(
        input_imported_at=snapshot.statement.imported_at.isoformat() if snapshot.statement.imported_at is not None else None,
        snapshot_as_of_date=snapshot_as_of_date,
        benchmark_symbol=benchmark_symbol,
        dataset_version=EXPOSURE_DATASET_VERSION,
    )


def _build_exposure_availability(
    total_market_value: float,
    lookthrough_constituents,
    uncovered_positions: list[str],
    benchmark_holdings: list[dict],
) -> ExposureAvailability:
    benchmark_holdings_status = _classify_benchmark_holdings_support(benchmark_holdings)
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
    if benchmark_holdings_status == "unavailable":
        benchmark_overlap_status = "unavailable"
        benchmark_overlap_confidence = "low"
    elif lookthrough_status != "live":
        benchmark_overlap_status = "partial"
        benchmark_overlap_confidence = "medium"
    elif benchmark_holdings_status == "degraded":
        benchmark_overlap_status = "live"
        benchmark_overlap_confidence = "medium"
    else:
        benchmark_overlap_status = "live"
        benchmark_overlap_confidence = "high"

    if lookthrough_status == "live" and benchmark_overlap_status == "live" and benchmark_holdings_status == "verified":
        note = None
    elif lookthrough_status == "partial" and benchmark_overlap_status == "unavailable":
        note = "Look-through exposure is partial because some holdings could not be resolved, and benchmark overlap is unavailable because benchmark composition could not be loaded."
    elif benchmark_holdings_status == "degraded":
        note = "Benchmark-relative overlap is available from incomplete benchmark holdings coverage, so overlap metrics remain usable but benchmark support is degraded."
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


def _build_current_state_concentration(snapshot: ImportedPortfolioSnapshot, overview: PortfolioOverview) -> ExposureCurrentStateConcentration:
    top_positions = [_coerce_concentration_item(item, "symbol") for item in overview.top_positions]
    top_sectors = [_coerce_concentration_item(item, "sector") for item in overview.sector_allocation[:8]]
    total_market_value = round(sum(position.market_value for position in snapshot.positions), 2)
    position_weights = [round(position.market_value / total_market_value, 4) for position in snapshot.positions if total_market_value > 0 and position.market_value >= 0]
    sector_weights = [float(item.get("weight") or 0.0) for item in overview.sector_allocation]
    position_hhi = _herfindahl_index(position_weights)
    sector_hhi = _herfindahl_index(sector_weights)

    return ExposureCurrentStateConcentration(
        top_positions=top_positions,
        top_sectors=top_sectors,
        top_1_position_weight=_sum_top_weights(position_weights, 1),
        top_3_position_weight=_sum_top_weights(position_weights, 3),
        top_5_position_weight=_sum_top_weights(position_weights, 5),
        top_sector_weight=_sum_top_weights(sector_weights, 1),
        top_3_sector_weight=_sum_top_weights(sector_weights, 3),
        position_hhi=position_hhi,
        sector_hhi=sector_hhi,
        effective_holdings=round(1 / position_hhi, 2) if position_hhi not in (None, 0) else None,
    )


def _coerce_concentration_item(item: dict[str, float | str], name_key: str) -> ExposureConcentrationItem:
    return ExposureConcentrationItem(
        name=str(item.get(name_key) or "n/a"),
        market_value=round(float(item.get("market_value") or 0.0), 2),
        weight=round(float(item.get("weight") or 0.0), 4),
    )


def _sum_top_weights(values: list[float], limit: int) -> float | None:
    if not values:
        return None
    return round(sum(sorted(values, reverse=True)[:limit]), 4)


def _herfindahl_index(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(value * value for value in values), 4)


def _combine_exposure_confidence(*values: str) -> ExposureAvailabilityConfidence:
    if "low" in values:
        confidence: ExposureAvailabilityConfidence = "low"
        return confidence
    if "medium" in values:
        confidence = "medium"
        return confidence
    confidence = "high"
    return confidence


def _classify_benchmark_holdings_support(benchmark_holdings: list[dict]) -> Literal["verified", "degraded", "unavailable"]:
    if not benchmark_holdings:
        return "unavailable"

    loaded_weight = 0.0
    for row in benchmark_holdings:
        symbol = str(row.get("asset") or "").strip().upper()
        if not symbol:
            continue
        loaded_weight += max(float(row.get("weightPercentage") or 0.0), 0.0)

    if loaded_weight <= 0:
        return "unavailable"

    return "verified" if loaded_weight >= BENCHMARK_HOLDINGS_VERIFIED_COVERAGE_PCT else "degraded"
