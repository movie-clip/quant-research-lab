from app.schemas.import_bootstrap import ImportedBootstrapResponse
from app.schemas.portfolio_engine import PortfolioHistoryContext
from app.schemas.reconciliation import PortfolioOverview, PortfolioRiskSummary


def compose_import_bootstrap_response(
    snapshot,
    overview: PortfolioOverview,
    risk_summary: PortfolioRiskSummary,
    history_context: PortfolioHistoryContext | None,
) -> ImportedBootstrapResponse:
    return ImportedBootstrapResponse(
        snapshot=snapshot,
        overview=overview,
        risk_summary=risk_summary,
        history_context=history_context,
    )
