from typing import Literal

from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest, PortfolioHistoryContext
from app.schemas.return_basis import PortfolioProofMetadata, ReturnBasisEvidence
from app.schemas.reconciliation import BenchmarkComparison, DailyPortfolioState, PerformancePoint, PerformanceSummary


InvestorEconomicsWithheldReason = Literal["withheld_unverified_total_return_equivalence"]
INVESTOR_ECONOMICS_WITHHELD_REASON: InvestorEconomicsWithheldReason = "withheld_unverified_total_return_equivalence"


class InvestorEconomicsStatus(BaseModel):
    status: Literal["available", "withheld"]
    reason: InvestorEconomicsWithheldReason | None = None


def build_investor_economics_status(*, available: bool) -> InvestorEconomicsStatus:
    if available:
        return InvestorEconomicsStatus(status="available", reason=None)
    return InvestorEconomicsStatus(
        status="withheld",
        reason=INVESTOR_ECONOMICS_WITHHELD_REASON,
    )


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


class DashboardHistoryInvestorEconomicsScalarPolicy(BaseModel):
    field: Literal[
        "range_metrics[*].summary.time_weighted_return_pct",
        "range_metrics[*].summary.benchmark_return_pct",
        "range_metrics[*].summary.excess_return_pct",
    ]
    unlock_condition: Literal[
        "identical_admitted_exact_slice_only",
        "identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only",
        "identical_admitted_exact_slice_pair_only",
    ]
    runtime_enabled: bool


class DashboardHistoryInvestorEconomicsPartialUnlock(BaseModel):
    mode: Literal["allowlisted_exact_slice_scalars_only"]
    exact_slice_scalar_allowlist: list[DashboardHistoryInvestorEconomicsScalarPolicy]
    client_derivation_rule: Literal["server_side_scalar_only_no_daily_series_subtraction_equivalence"]
    withheld_families: list[
        Literal[
            "benchmark_relative_series",
            "benchmark_relative_path_derived_outputs",
            "drawdown_family",
            "rebucketed_window_summaries",
            "rewindowed_range_summaries",
            "diagnostics_benchmark_relative_outputs",
            "replay_benchmark_relative_outputs",
            "strategy_lab_benchmark_relative_outputs",
        ]
    ]


class DashboardHistoryRunMetadata(BaseModel):
    class SectionTrust(BaseModel):
        portfolio_path: str
        benchmark_path: str
        monthly_returns_path: str

    class ReturnBasisContract(BaseModel):
        portfolio_path: Literal["verified_total_return", "price_return_only", "unverified_adjusted_proxy", "unavailable"]
        benchmark_path: Literal["verified_total_return", "price_return_only", "unverified_adjusted_proxy", "unavailable"]

    class ReturnBasisEvidenceBundle(BaseModel):
        portfolio_path: ReturnBasisEvidence
        benchmark_path: ReturnBasisEvidence

    history_id: str
    methodology_id: str
    source_status: DashboardHistoryRunSourceStatus
    section_trust: SectionTrust
    return_basis_contract: ReturnBasisContract
    return_basis_evidence: ReturnBasisEvidenceBundle
    portfolio_proof: PortfolioProofMetadata
    investor_economics_status: InvestorEconomicsStatus
    investor_economics_partial_unlock: DashboardHistoryInvestorEconomicsPartialUnlock
    reproducibility: DashboardHistoryRunReproducibility


class DashboardHistoryResult(BaseModel):
    daily_states: list[DailyPortfolioState]
    performance_series: list[PerformancePoint]
    source_status: dict[str, str] | None = None
    run_metadata: DashboardHistoryRunMetadata
    benchmark: BenchmarkComparison | None = None
    range_metrics: dict[str, DashboardRangeMetrics] | None = None
