from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest, PortfolioHistoryContext
from app.schemas.reconciliation import BenchmarkComparison, DailyPortfolioState, PerformancePoint, PerformanceSummary


class DashboardHistoryEngineRequest(PortfolioEngineRequest):
    history_context: PortfolioHistoryContext | None = None


class DashboardMonthlyReturn(BaseModel):
    month: str
    return_pct: float


class DashboardRangeMetrics(BaseModel):
    summary: PerformanceSummary
    max_drawdown_pct: float | None = None
    monthly_returns: list[DashboardMonthlyReturn]
    monthly_returns_reliable: bool = False


class DashboardHistoryResult(BaseModel):
    daily_states: list[DailyPortfolioState]
    performance_series: list[PerformancePoint]
    source_status: dict[str, str] | None = None
    benchmark: BenchmarkComparison | None = None
    range_metrics: dict[str, DashboardRangeMetrics] | None = None
