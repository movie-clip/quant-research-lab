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
    # US-34.2 (Epic 34 F-1): the trust of THIS range's `time_weighted_return_pct`
    # and `max_drawdown_pct`, so the UI can render the number with a marker
    # rather than the researcher having to cross-reference
    # `run_metadata.return_basis_contract`. `verified` only when the proof
    # admission granted an exact slice; `degraded` for a `replay_derived` basis
    # (a real measurement on reconstructed inputs); `unavailable` when no return
    # was published at all. Never collapses a published-but-degraded number into
    # `unavailable` — that is the distinction the whole ladder exists for.
    portfolio_return_trust: Literal["verified", "degraded", "unavailable"] = "unavailable"


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
        "statement_starting_cash",
        "statement_nav_at_window_start",
        "statement_nav_date_mismatch",
        "snapshot_cash_balances",
        "unavailable",
    ]
    # US-34.3 (Epic 34 F-2): `statement_starting_cash` is the strongest basis and
    # the one used whenever the statement reports its own opening cash. It is
    # DIRECTLY OBSERVED broker truth, exactly dated at the period start, so it
    # carries none of the date mismatch that makes the derived
    # `starting_nav − opening_positions_value` identity a plug.
    #
    # Trust follows the anchor's SOURCE, not its residual: an observed figure is
    # `verified`, and the residual reports a different fact — how well the
    # ledger's flows reconcile the statement's two cash endpoints. Above
    # `REPLAY_OPENING_CASH_RESIDUAL_SHARE` of opening cash the ledger has failed
    # to explain its own statement, and the anchor degrades.
    #
    # For the DERIVED bases the old rule still holds: any residual above
    # `REPLAY_RECONCILIATION_TOLERANCE` means the derivation is absorbing
    # something, so it degrades.
    nav_as_of: str | None = None
    window_start: str | None = None
    residual: float | None = None
    trust: Literal["verified", "degraded", "unavailable"]


class ReplayQuantityWithholding(BaseModel):
    """US-33.2 (Epic 33 F-1/F-2): a reconstructed quantity the replay refused to publish.

    The opening-position roll-back (`opening = ending + Σ SELL − Σ BUY`) presumes
    a single share unit across the window. A split breaks that identity, and the
    result is a position size the broker never held — on IB2026, 199 phantom LQQ
    units which the US-24.10 trade-price anchor then valued at the stale
    pre-split EUR 1,457.78 ($336,543), inflating market value ~8x for three
    months. Detected from the symbol's OWN execution prices spanning a ratio no
    market move explains, measured within a single currency.

    The fabricated object is the quantity, so the quantity is withheld: the
    symbol contributes no position line and no market value on any day, and
    appears in NONE of the three valuation tiers. Its cash movements are
    unaffected — those are broker truth.
    """

    symbol: str
    reason: Literal["share_unit_discontinuity"]
    currency: str
    price_low: float
    price_high: float
    price_ratio: float
    withheld_opening_quantity: float
    # US-34.4 (Epic 34 F-3): HOW MUCH the researcher is not being shown.
    #
    # Derived from the broker's own cash movements alone — no price, no quantity,
    # no market data — because the quantity is precisely the untrusted thing.
    # `peak_net_cash_invested` is the largest END-OF-DAY net cash the broker had
    # in the symbol (each trade FX-converted before it enters the running total);
    # the within-day gross figure would overstate what was ever held overnight.
    #
    # It is a LOWER BOUND, not a valuation: it is what the broker paid, not what
    # the position was worth on any day. Erring low is the honest direction — it
    # can understate what is missing, never overstate it — so surfaces must word
    # it as "at least". It must never enter `total_market_value`.
    peak_net_cash_invested: float = 0.0
    # `None` when the portfolio value on the peak day is not positive — the
    # ratio would be meaningless, and an absent measurement is honest where a
    # fabricated percentage is not.
    peak_share_of_portfolio_pct: float | None = None
    exposure_day_count: int = 0


class DashboardHistoryRunMetadata(BaseModel):
    class SectionTrust(BaseModel):
        portfolio_path: str
        benchmark_path: str
        monthly_returns_path: str

    class ReturnBasisContract(BaseModel):
        # US-34.2 (Epic 34 F-1): `replay_derived` is a PORTFOLIO-path-only rung,
        # BELOW `verified_total_return`. It means the return was chained from the
        # imported ledger replay's own daily states — a real measurement on
        # RECONSTRUCTED inputs (rolled-back opening positions, a mixed valuation
        # basis, a terminal reconciliation), which is exactly what the strict
        # proof admission refuses to certify as a verified total return. Before
        # this rung existed `portfolio_path` was a hardcoded literal
        # `"unavailable"`, so the whole cumulative series and every headline
        # scalar were null on every run. The benchmark path deliberately does
        # NOT accept it: a benchmark is priced from market data, never replayed.
        portfolio_path: Literal[
            "verified_total_return",
            "replay_derived",
            "price_return_only",
            "unverified_adjusted_proxy",
            "unavailable",
        ]
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
    # performance. US-33.3 (Epic 33 F-3): exactly one tier values a symbol on any
    # given DAY; these lists are unions over the window, so a symbol held before
    # its first trade appears both here and in `unpriced_replay_symbols`.
    trade_price_anchored_symbols: list[str] = []
    # US-33.2 (Epic 33 F-1/F-2): symbols whose RECONSTRUCTED QUANTITY was
    # withheld because their own ledger prices imply a share-unit change (a
    # split). Withheld, not unpriced: `unpriced_replay_symbols` means the
    # quantity is trusted and no price exists, this means the quantity itself is
    # not publishable — so a withheld symbol appears in NO valuation tier and
    # contributes no position line on any day. Empty when the window contains no
    # detectable discontinuity.
    quantity_withheld_symbols: list[ReplayQuantityWithholding] = []
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
    # US-34.2 (Epic 34 F-1): how much the withheld days cost the published
    # return, in percentage points. Measured as the difference between the
    # published chain and the same chain with the withheld days included.
    #
    # This is an IMPACT ESTIMATE, never a return. The withheld days' moves are
    # unpublishable AS PERFORMANCE — their states were contaminated by an
    # accounting adjustment (US-31.3) or by cash with no position behind it
    # (US-33.2) — but their magnitude is still the best available measure of what
    # the gap costs, and it comes from the same states. Publishing a return that
    # omits 7 of 148 days without saying what that omission is worth would be
    # more misleading than publishing nothing: on IB2026 the published 2.43%
    # understates the all-days chain of 4.23% by 1.80pp.
    #
    # `None` when nothing was withheld — never 0.0, which would claim a measured
    # zero impact.
    withheld_return_impact_pct: float | None = None


class DashboardHistoryResult(BaseModel):
    daily_states: list[DailyPortfolioState]
    performance_series: list[PerformancePoint]
    source_status: dict[str, str] | None = None
    run_metadata: DashboardHistoryRunMetadata
    benchmark: BenchmarkComparison | None = None
    range_metrics: dict[str, DashboardRangeMetrics] | None = None
