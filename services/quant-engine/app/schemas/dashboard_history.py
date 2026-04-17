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


class DashboardHistoryRunSourceStatus(BaseModel):
    performance_history: str
    monthly_returns: str
    benchmark_history: str


class DashboardHistoryRunReproducibility(BaseModel):
    input_imported_at: str | None = None
    snapshot_as_of_date: str | None = None
    history_start_date: str | None = None
    history_end_date: str | None = None
    benchmark_symbol: str
    dataset_version: str


class DashboardHistoryRunMetadata(BaseModel):
    history_id: str
    methodology_id: str
    source_status: DashboardHistoryRunSourceStatus
    reproducibility: DashboardHistoryRunReproducibility


class DashboardHistoryResult(BaseModel):
    daily_states: list[DailyPortfolioState]
    performance_series: list[PerformancePoint]
    source_status: dict[str, str] | None = None
    run_metadata: DashboardHistoryRunMetadata
    benchmark: BenchmarkComparison | None = None
    range_metrics: dict[str, DashboardRangeMetrics] | None = None
