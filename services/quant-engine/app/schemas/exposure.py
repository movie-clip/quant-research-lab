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


class ExposureResult(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    overview: PortfolioOverview
    lookthrough: LookThroughOverview
    lookthrough_sector_exposure: list[LookThroughSectorExposure]
    market_overlap: MarketOverlapSummary
    availability: ExposureAvailability
