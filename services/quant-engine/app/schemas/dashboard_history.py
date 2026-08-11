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


class ReplayCashAnchor(BaseModel):
    """US-31.3 (Epic 31 F-2): provenance + trust of the replay's opening cash.

    `base_cash = starting_nav − opening_positions_value` is only sound when both
    terms are dated the same day. On the committed IB2026 statement they are
    not: `starting_nav` is as of the statement-period start while the positions
    are valued at the replay window start, so market movement between the two
    dates is absorbed into cash as a plug. The residual is measured against the
    statement-implied opening cash (computed from FX-CONVERTED ledger flows —
    the raw per-currency sum is currency-mixed and would give a wrong figure)
    and the trust level is set from it.
    """

    basis: Literal[
        "statement_nav_at_window_start",
        "statement_nav_date_mismatch",
        "snapshot_cash_balances",
        "unavailable",
    ]
    nav_as_of: str | None = None
    window_start: str | None = None
    residual: float | None = None
    trust: Literal["verified", "degraded", "unavailable"]


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
    # US-27.8 (audit F9): currencies needing base conversion with no FX rate
    # available — affected values are carried UNCONVERTED and this discloses
    # the degradation (never a silent 1:1 fallback claim).
    fx_fallback_currencies: list[str] = []
    # US-31.2 (Epic 31 F-1): reconstructed opening/interior positions that had
    # NO fetchable price history AND no statement close-price anchor, so they
    # contributed 0 to the replayed market value on the days they were held.
    # Since-sold symbols are the common case (they are absent from the current
    # snapshot, hence from `fallback_prices`). Disclosed rather than silently
    # zeroed — guardrail #3.
    unpriced_replay_symbols: list[str] = []
    # US-24.10: symbols valued at the broker's own execution price, carried
    # forward from the trade (the third valuation tier, below market history and
    # the statement close). Broker truth, but the carried segment is FLAT — it
    # contains no market movement, so it must be disclosed rather than passed
    # off as a priced series. Replaces a $0 valuation, which let a BUY/SELL move
    # cash with no offsetting market value and the TWR publish the step as
    # performance. A symbol appears in exactly one of the three valuation tiers.
    trade_price_anchored_symbols: list[str] = []
    # US-31.3 (Epic 31 F-2): how the replay's OPENING CASH was derived and
    # whether that derivation is trustworthy. The anchor is
    # `starting_nav − opening_positions_value`; when the NAV's as-of date and
    # the replay window start differ, market movement between them is absorbed
    # into cash as a plug, so the anchor is `degraded`, never `verified`.
    replay_cash_anchor: ReplayCashAnchor | None = None
    # US-31.3 (Epic 31 F-3): dates whose replayed return was WITHHELD because
    # the state carried a material reconciliation adjustment (an accounting
    # correction, not a market move). Empty when nothing was withheld — a
    # visible gap with a stated reason, never a silent missing point.
    withheld_return_dates: list[str] = []
    withheld_return_reason: str | None = None


class DashboardHistoryResult(BaseModel):
    daily_states: list[DailyPortfolioState]
    performance_series: list[PerformancePoint]
    source_status: dict[str, str] | None = None
    run_metadata: DashboardHistoryRunMetadata
    benchmark: BenchmarkComparison | None = None
    range_metrics: dict[str, DashboardRangeMetrics] | None = None
