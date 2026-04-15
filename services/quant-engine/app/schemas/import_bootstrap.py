from pydantic import BaseModel

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioHistoryContext
from app.schemas.reconciliation import PortfolioOverview, PortfolioRiskSummary


class ImportedBootstrapResponse(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    overview: PortfolioOverview
    risk_summary: PortfolioRiskSummary
    history_context: PortfolioHistoryContext | None = None
