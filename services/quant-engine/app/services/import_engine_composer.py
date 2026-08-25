from app.schemas.exposure import ExposureAvailability, ExposureCurrentStateConcentration
from app.schemas.import_bootstrap import ImportedBootstrapResponse
from app.schemas.portfolio_engine import PortfolioHistoryContext
from app.schemas.reconciliation import (
    LookThroughOverview,
    LookThroughSectorExposure,
    MarketOverlapSummary,
    PortfolioOverview,
    PortfolioRiskSummary,
)
from app.services.import_admission import build_import_admission_summary


def compose_import_bootstrap_response(
    snapshot,
    overview: PortfolioOverview,
    lookthrough: LookThroughOverview,
    lookthrough_sector_exposure: list[LookThroughSectorExposure],
    market_overlap: MarketOverlapSummary,
    current_state_concentration: ExposureCurrentStateConcentration,
    availability: ExposureAvailability,
    risk_summary: PortfolioRiskSummary,
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
        admission_summary=build_import_admission_summary(snapshot),
        history_context=history_context,
    )
