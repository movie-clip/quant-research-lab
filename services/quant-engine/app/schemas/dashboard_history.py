from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest, PortfolioHistoryContext
from app.schemas.reconciliation import BenchmarkComparison, DailyPortfolioState, PerformancePoint


class DashboardHistoryEngineRequest(PortfolioEngineRequest):
    history_context: PortfolioHistoryContext | None = None


class DashboardHistoryResult(BaseModel):
    daily_states: list[DailyPortfolioState]
    performance_series: list[PerformancePoint]
    source_status: dict[str, str] | None = None
    benchmark: BenchmarkComparison | None = None
