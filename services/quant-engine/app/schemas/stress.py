from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest
from app.schemas.reconciliation import StressScenarioResult


StressTrustLevel = Literal["synthetic", "unavailable"]


class StressEngineRequest(PortfolioEngineRequest):
    """Stress-scenario engine request.

    Inherits `positions`, `cash_balances`, `imported_at`, `benchmark_symbol`,
    etc. from PortfolioEngineRequest. No additional fields — the stress
    engine builds its own lookback window internally from `imported_at`
    (defaults to today when missing).
    """

    pass


class StressEngineResponse(BaseModel):
    """Wrapper around per-scenario projections + engine-level trust.

    Per-scenario `status` (on StressScenarioResult) indicates row-level
    availability. The wrapper-level `trust` indicates engine-level
    availability — 'unavailable' when the factor model has no rolling
    history at all, 'synthetic' otherwise.
    """

    scenarios: list[StressScenarioResult]
    trust: StressTrustLevel
