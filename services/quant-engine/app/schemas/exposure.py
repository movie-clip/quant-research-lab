from typing import Literal

from pydantic import BaseModel

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioEngineRequest
from app.schemas.reconciliation import (
    LookThroughOverview,
    LookThroughSectorExposure,
    MarketOverlapSummary,
    PortfolioOverview,
)


ExposureAvailabilityStatus = Literal["live", "partial", "unavailable"]
ExposureAvailabilityConfidence = Literal["high", "medium", "low"]


class ExposureEngineRequest(PortfolioEngineRequest):
    pass


class ExposureAvailability(BaseModel):
    lookthrough_status: ExposureAvailabilityStatus
    lookthrough_confidence: ExposureAvailabilityConfidence
    benchmark_overlap_status: ExposureAvailabilityStatus
    benchmark_overlap_confidence: ExposureAvailabilityConfidence
    note: str | None = None


class ExposureProvenance(BaseModel):
    snapshot_basis: Literal["snapshot_request"]
    historical_basis: Literal["current_state_only"]
    price_basis: Literal["not_applicable"]
    note: str


class ExposureRunSourceStatus(BaseModel):
    lookthrough_resolution: ExposureAvailabilityStatus
    benchmark_holdings: Literal["live", "unavailable"]


class ExposureRunReproducibilityMetadata(BaseModel):
    input_imported_at: str | None = None
    snapshot_as_of_date: str | None = None
    benchmark_symbol: str
    dataset_version: str


class ExposureRunMetadata(BaseModel):
    engine_id: str
    methodology_id: str
    price_basis: Literal["not_applicable"]
    source_status: ExposureRunSourceStatus
    confidence: ExposureAvailabilityConfidence
    reproducibility: ExposureRunReproducibilityMetadata


class ExposureConcentrationItem(BaseModel):
    name: str
    market_value: float
    weight: float


class ExposureCurrentStateConcentration(BaseModel):
    top_positions: list[ExposureConcentrationItem]
    top_sectors: list[ExposureConcentrationItem]
    top_1_position_weight: float | None = None
    top_3_position_weight: float | None = None
    top_5_position_weight: float | None = None
    top_sector_weight: float | None = None
    top_3_sector_weight: float | None = None
    position_hhi: float | None = None
    sector_hhi: float | None = None
    effective_holdings: float | None = None


class ExposureResult(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    provenance: ExposureProvenance
    run_metadata: ExposureRunMetadata
    overview: PortfolioOverview
    lookthrough: LookThroughOverview
    lookthrough_sector_exposure: list[LookThroughSectorExposure]
    market_overlap: MarketOverlapSummary
    current_state_concentration: ExposureCurrentStateConcentration
    availability: ExposureAvailability
