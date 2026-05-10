from app.schemas.import_bootstrap import ImportedBootstrapResponse
from app.schemas.portfolio_engine import PortfolioHistoryContext
from app.schemas.reconciliation import PortfolioOverview, PortfolioRiskSummary
from app.services.import_admission import build_import_admission_summary


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
        admission_summary=build_import_admission_summary(snapshot),
        history_context=history_context,
    )
