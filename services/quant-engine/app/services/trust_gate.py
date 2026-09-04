"""Trust gate for the Dashboard-history and Diagnostics engines (Epic 43 — US-43.3).

Single home for the "is this output trustworthy enough to publish, and at what
level" decision shared by `dashboard_history_engine.py` and `diagnostics_engine.py`:
section-trust rollups, per-section output-admission policy, the price-history /
replay-output presence primitives, and the dashboard return-basis classification.

This is a **relocation, not a unification** (guardrail #3 / Epic 43). Each engine
keeps its own section-trust builder and its own output-admission gates as separate
engine-qualified functions; only `has_any_symbol_price_history` is merged, because
the two former engine copies were byte-identical. No formula lives here — every
function body is verbatim from its former engine home.
"""
from typing import Literal

from app.schemas.dashboard_history import (
    DashboardHistoryInvestorEconomicsPartialUnlock,
    DashboardHistoryInvestorEconomicsScalarPolicy,
    DashboardHistoryRunMetadata,
    InvestorEconomicsStatus,
    build_investor_economics_status,
)
from app.schemas.diagnostics import DiagnosticsDrawdownSummary, DiagnosticsRunMetadata
from app.schemas.reconciliation import VolatilityRegimePayload
from app.services.market_data import (
    build_histories_return_basis_evidence,
    build_history_return_basis_evidence,
    classify_history_return_basis_contract,
    detect_history_return_basis,
)


DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED = True


# --- shared presence primitives -------------------------------------------------


def has_any_symbol_price_history(symbol_price_histories: dict[str, list[dict]]) -> bool:
    return any(rows for rows in symbol_price_histories.values())


def has_replay_outputs(daily_states, performance_series) -> bool:
    return bool(daily_states) and bool(performance_series)


# --- dashboard-history engine trust helpers -----------------------------------


def build_dashboard_section_trust(
    *,
    benchmark_rows: list[dict],
    daily_states: list,
    monthly_returns_suppressed: bool,
) -> DashboardHistoryRunMetadata.SectionTrust:
    benchmark_basis = detect_history_return_basis(benchmark_rows)
    benchmark_path = (
        "verified_adjusted_close"
        if benchmark_basis == "verified_adjusted_close"
        else "degraded_unverified_return_basis"
        if benchmark_basis == "unverified_close_only"
        else "unavailable"
    )
    portfolio_path = "imported_replay" if daily_states else "unavailable"
    monthly_returns_path = (
        "suppressed_unstable_path"
        if monthly_returns_suppressed
        else "imported_replay"
        if daily_states
        else "unavailable"
    )
    return DashboardHistoryRunMetadata.SectionTrust(
        portfolio_path=portfolio_path,
        benchmark_path=benchmark_path,
        monthly_returns_path=monthly_returns_path,
    )


def classify_portfolio_return_basis(
    *,
    daily_states: list,
    admitted_exact_slice: bool,
) -> str:
    """US-34.2 (Epic 34 F-1): the portfolio return basis, as a function of the run.

    This was a hardcoded `"unavailable"` literal, which no input could change —
    and because `build_true_performance_series` only chains a return on a
    publishing basis, that literal suppressed the ENTIRE cumulative series and
    every headline scalar on the Dashboard, on every run.

    The ladder, strongest first:
      - `verified_total_return` — the proof admission granted an exact slice.
        Unreachable on the imported path today, and deliberately so: five of its
        hard disqualifiers are structural properties of replaying a statement.
      - `replay_derived`        — the replay produced daily states. A real
        measurement on reconstructed inputs.
      - `unavailable`           — no states, so no claimable return.
    """
    if admitted_exact_slice:
        return "verified_total_return"
    return "replay_derived" if daily_states else "unavailable"


def build_dashboard_return_basis_contract(
    benchmark_rows: list[dict],
    *,
    portfolio_path: str = "unavailable",
) -> DashboardHistoryRunMetadata.ReturnBasisContract:
    benchmark_contract = classify_history_return_basis_contract(benchmark_rows)
    return DashboardHistoryRunMetadata.ReturnBasisContract(
        portfolio_path=portfolio_path,
        benchmark_path=benchmark_contract,
    )


def build_dashboard_return_basis_evidence(
    *,
    benchmark_rows: list[dict],
    symbol_price_histories: dict[str, list[dict]] | None = None,
    verified_benchmark_scope: dict[str, str | bool | int | None] | None = None,
) -> DashboardHistoryRunMetadata.ReturnBasisEvidenceBundle:
    portfolio_evidence = (
        build_histories_return_basis_evidence(symbol_price_histories or {})
        if symbol_price_histories
        else build_history_return_basis_evidence([])
    )
    return DashboardHistoryRunMetadata.ReturnBasisEvidenceBundle(
        portfolio_path=portfolio_evidence,
        benchmark_path=build_history_return_basis_evidence(
            benchmark_rows,
            verified_total_return_scope=verified_benchmark_scope,
        ),
    )


def allow_dashboard_drawdown_outputs(
    *,
    benchmark_rows: list[dict],
    symbol_price_histories: dict[str, list[dict]],
) -> bool:
    # Dashboard investor-economics policy stays narrower than the underlying proof
    # system: `drawdown_family` is one of
    # `investor_economics_partial_unlock.withheld_families`, so this output stays
    # withheld until that policy is decided. Reopening it is blocked on Epic 34
    # F-10, the same decision that parked US-34.5 — it would move 22 pinned
    # `max_drawdown_pct is None` assertions and two named policy tests.
    #
    # US-34.7 CORRECTED the justification that used to sit here. US-34.2 claimed
    # the gate was really about whether the price inputs are adjusted, because a
    # drawdown from unadjusted closes "overstates the loss on dividend-paying
    # holdings". That is false on THIS path: `_compute_max_drawdown` chains the
    # `portfolio_value` basis over the imported replay, where dividends arrive as
    # LEDGER CASH ($125.72 gross / $107.79 net over the IB2026 window, verified
    # in the daily states), so the ex-date price drop is offset by the receipt
    # and the chain is already total-return-like.
    #
    # The exposure is real on the SYNTHETIC path (Risk tab), which applies a flat
    # cash balance and no ledger — see `financial-methodology.md` §Wealth Index
    # and Drawdown. The two parameters below are retained because that is the
    # question a future gate would ask; they are not read today.
    return False


def build_dashboard_investor_economics_status() -> InvestorEconomicsStatus:
    return build_investor_economics_status(
        available=False,
    )


def build_dashboard_investor_economics_partial_unlock() -> DashboardHistoryInvestorEconomicsPartialUnlock:
    return DashboardHistoryInvestorEconomicsPartialUnlock(
        mode="allowlisted_exact_slice_scalars_only",
        exact_slice_scalar_allowlist=[
            DashboardHistoryInvestorEconomicsScalarPolicy(
                field="range_metrics[*].summary.time_weighted_return_pct",
                unlock_condition="identical_admitted_exact_slice_only",
                runtime_enabled=True,
            ),
            DashboardHistoryInvestorEconomicsScalarPolicy(
                field="range_metrics[*].summary.benchmark_return_pct",
                # US-34.5 (F-10): published whenever the benchmark's own basis
                # supports a return, labelled with that basis. It no longer
                # depends on the PORTFOLIO's exact-slice admission — the two
                # legs are measured from different data and one leg's proof
                # status was never evidence about the other's.
                unlock_condition="publishing_benchmark_return_basis_only",
                runtime_enabled=True,
            ),
            DashboardHistoryInvestorEconomicsScalarPolicy(
                field="range_metrics[*].summary.excess_return_pct",
                # US-34.5: strictly the difference of the two published legs.
                # A missing leg yields no excess — never a figure computed
                # against a null silently read as zero.
                unlock_condition="both_published_legs_present_only",
                runtime_enabled=DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED,
            ),
        ],
        # US-34.5 (F-10): the benchmark scalars are published with their basis;
        # the daily benchmark chain stays withheld.
        client_derivation_rule="labelled_scalars_published_daily_series_withheld",
        withheld_families=[
            "benchmark_relative_series",
            "benchmark_relative_path_derived_outputs",
            "drawdown_family",
            "rebucketed_window_summaries",
            "rewindowed_range_summaries",
            "diagnostics_benchmark_relative_outputs",
            "replay_benchmark_relative_outputs",
            "strategy_lab_benchmark_relative_outputs",
        ],
    )


# --- diagnostics engine trust helpers ---------------------------------------


def build_diagnostics_section_trust(
    *,
    benchmark_return_basis: Literal["verified_adjusted_close", "unverified_close_only", "unavailable"],
    factor_return_basis: Literal["verified_adjusted_close", "unverified_close_only", "unavailable"],
    historical_sections_available: bool,
) -> DiagnosticsRunMetadata.SectionTrust:
    if not historical_sections_available:
        return DiagnosticsRunMetadata.SectionTrust(
            benchmark_relative_path="unavailable",
            factor_model_path="unavailable",
            risk_contribution_path="unavailable",
        )

    benchmark_relative_path = "verified_adjusted_close" if benchmark_return_basis == "verified_adjusted_close" else "degraded_unverified_return_basis"
    factor_model_path = (
        "verified_adjusted_close"
        if benchmark_return_basis == "verified_adjusted_close" and factor_return_basis == "verified_adjusted_close"
        else "degraded_unverified_return_basis"
    )
    risk_contribution_path = factor_model_path
    return DiagnosticsRunMetadata.SectionTrust(
        benchmark_relative_path=benchmark_relative_path,
        factor_model_path=factor_model_path,
        risk_contribution_path=risk_contribution_path,
    )


def allow_diagnostics_drawdown_outputs() -> bool:
    return False


def apply_diagnostics_drawdown_output_policy(
    volatility_regime: VolatilityRegimePayload,
    *,
    allow_drawdown_outputs: bool,
) -> VolatilityRegimePayload:
    if allow_drawdown_outputs:
        return volatility_regime

    return volatility_regime.model_copy(
        update={
            "rolling_series": [
                point.model_copy(update={"drawdown_pct": None, "wealth_index": None})
                for point in volatility_regime.rolling_series
            ],
            "snapshot": volatility_regime.snapshot.model_copy(
                update={
                    "current_drawdown_pct": None,
                    "max_drawdown_pct": None,
                }
            ),
        }
    )


def build_diagnostics_drawdown_summary(
    volatility_regime: VolatilityRegimePayload,
    *,
    allow_drawdown_outputs: bool,
) -> DiagnosticsDrawdownSummary:
    if not allow_drawdown_outputs:
        return DiagnosticsDrawdownSummary(
            current_drawdown_pct=None,
            max_drawdown_pct=None,
        )

    return DiagnosticsDrawdownSummary(
        current_drawdown_pct=volatility_regime.snapshot.current_drawdown_pct,
        max_drawdown_pct=volatility_regime.snapshot.max_drawdown_pct,
    )


def build_diagnostics_investor_economics_status(
    *,
    historical_sections_available: bool,
    allow_drawdown_outputs: bool,
    allow_relative_return_outputs: bool,
) -> InvestorEconomicsStatus:
    if not historical_sections_available:
        return build_investor_economics_status(available=False)
    if allow_drawdown_outputs and allow_relative_return_outputs:
        return build_investor_economics_status(available=True)
    return build_investor_economics_status(
        available=False,
    )
