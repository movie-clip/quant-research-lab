from pydantic import BaseModel

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioEngineRequest
from app.schemas.reconciliation import (
    LookThroughOverview,
    LookThroughSectorExposure,
    MarketOverlapSummary,
    PortfolioOverview,
)


class ExposureEngineRequest(PortfolioEngineRequest):
    pass


class ExposureResult(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    overview: PortfolioOverview
    lookthrough: LookThroughOverview
    lookthrough_sector_exposure: list[LookThroughSectorExposure]
    market_overlap: MarketOverlapSummary
