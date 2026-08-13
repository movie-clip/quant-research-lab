from typing import TypedDict, cast

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL
from app.analytics.performance import build_replay_currency_context, build_replay_states_with_cash_anchor, build_true_performance_series, replay_disclosures, withheld_return_impact_pct
from app.engine.portfolio_state import replay_symbol_universe
from app.analytics.risk import (
    _build_drawdown_from_return_index,
    _build_wealth_index,
    _portfolio_time_weighted_return_series,
)
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.dashboard_history import (
    DashboardHistoryEngineRequest,
    DashboardHistoryInvestorEconomicsPartialUnlock,
    DashboardHistoryInvestorEconomicsScalarPolicy,
    DashboardHistoryResult,
    DashboardHistoryRunMetadata,
    ReplayCashAnchor,
    ReplayQuantityWithholding,
    DashboardHistoryRunReproducibility,
    DashboardHistoryRunSourceStatus,
    DashboardMonthlyReturn,
    DashboardRangeMetrics,
)
from app.schemas.dashboard_history import InvestorEconomicsStatus, build_investor_economics_status
from app.schemas.reconciliation import PerformanceSummary
from app.services.benchmark_service import build_benchmark_comparison
from app.services.market_data import (
    MarketDataService,
    VERIFIED_BENCHMARK_ENDPOINT,
    VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST,
    VERIFIED_BENCHMARK_VENDOR,
    build_histories_return_basis_evidence,
    build_history_return_basis_evidence,
    classify_history_return_basis_contract,
    detect_history_return_basis,
)
from app.services.portfolio_proof import build_portfolio_proof_metadata, build_unavailable_portfolio_proof_metadata


DASHBOARD_HISTORY_ID = "dashboard_history_engine_v1"
DASHBOARD_HISTORY_METHODOLOGY_ID = "dashboard_history_methodology_v1"
DASHBOARD_HISTORY_DATASET_VERSION = "market_data_service_v1"
DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED = True


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _validate_verified_benchmark_slice(
    *,
    benchmark_symbol: str,
    benchmark_rows: list[dict],
    benchmark_fetch_meta: dict[str, object] | None,
    history_start_date: str,
    history_end_date: str,
) -> dict[str, str | bool | int | None] | None:
    if benchmark_symbol not in VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST:
        return None
    if not benchmark_rows or benchmark_fetch_meta is None:
        return None
    if benchmark_fetch_meta.get("requested_symbol") != benchmark_symbol:
        return None
    if benchmark_fetch_meta.get("resolved_symbol") != benchmark_symbol:
        return None
    if benchmark_fetch_meta.get("vendor") != VERIFIED_BENCHMARK_VENDOR:
        return None
    if benchmark_fetch_meta.get("endpoint") != VERIFIED_BENCHMARK_ENDPOINT:
        return None
    if benchmark_fetch_meta.get("direct_path_only") is not True:
        return None
    if benchmark_fetch_meta.get("fallback_used") is not False:
        return None
    if benchmark_fetch_meta.get("proxy_used") is not False:
        return None
    if benchmark_fetch_meta.get("mixed_source") is not False:
        return None
    if benchmark_fetch_meta.get("symbol_override_used") is not False:
        return None

    in_window_rows = [
        row
        for row in benchmark_rows
        if isinstance(row.get("date"), str) and history_start_date <= row["date"] <= history_end_date
    ]
    if not in_window_rows:
        return None

    ordered_dates = [row["date"] for row in in_window_rows]
    if ordered_dates != sorted(ordered_dates):
        return None
    if len(set(ordered_dates)) != len(ordered_dates):
        return None
    if any(_coerce_float(row.get("adjClose")) is None for row in in_window_rows):
        return None

    return {
        "symbol": benchmark_symbol,
        "requested_symbol": benchmark_symbol,
        "resolved_symbol": benchmark_symbol,
        "vendor": VERIFIED_BENCHMARK_VENDOR,
        "endpoint": VERIFIED_BENCHMARK_ENDPOINT,
        "direct_path_only": True,
        "fallback_used": False,
        "proxy_used": False,
        "mixed_source": False,
        "symbol_override_used": False,
        "window_start": history_start_date,
        "window_end": history_end_date,
        "row_count": len(in_window_rows),
        "rows_ordered": True,
        "rows_unique_by_date": True,
        "adjclose_complete": True,
        "validation_version": f"{benchmark_symbol.lower()}_fmp_light_adjclose_v1",
    }


def _build_dashboard_benchmark_history_status(benchmark_rows: list[dict]) -> str:
    basis = detect_history_return_basis(benchmark_rows)
    if basis == "verified_adjusted_close":
        return "live_market_data_verified_adjusted_close"
    if basis == "unverified_close_only":
        return "live_market_data_unverified_return_basis"
    return "unavailable"


def _build_dashboard_section_trust(
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


def _classify_portfolio_return_basis(
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


def _build_dashboard_return_basis_contract(
    benchmark_rows: list[dict],
    *,
    portfolio_path: str = "unavailable",
) -> DashboardHistoryRunMetadata.ReturnBasisContract:
    benchmark_contract = classify_history_return_basis_contract(benchmark_rows)
    return DashboardHistoryRunMetadata.ReturnBasisContract(
        portfolio_path=portfolio_path,
        benchmark_path=benchmark_contract,
    )


def _build_dashboard_return_basis_evidence(
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


def _build_dashboard_portfolio_proof_metadata(
    *,
    snapshot: ImportedPortfolioSnapshot,
    symbol_price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    history_available: bool,
):
    if not history_available:
        return build_unavailable_portfolio_proof_metadata()
    return build_portfolio_proof_metadata(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
        fx_history={},
        history_source="imported_replay",
    )


def _allow_dashboard_drawdown_outputs(
    *,
    benchmark_rows: list[dict],
    symbol_price_histories: dict[str, list[dict]],
) -> bool:
    # Dashboard investor-economics policy stays narrower than the underlying proof
    # system: drawdown and other path-derived outputs remain withheld for now.
    #
    # US-34.2 deliberately did NOT open this gate alongside the return. The two
    # parameters — never read by this stub — say what the intent was: allow the
    # drawdown when the PRICE INPUTS are on an adjusted basis, not when the
    # replay is publishable. A drawdown chained from unadjusted closes is a
    # PRICE drawdown, which overstates the loss on dividend-paying holdings, and
    # that is a methodology question this story did not research. It is
    # Epic 34's own follow-up (see the PRD story list), not a line to flip while
    # publishing the return.
    return False


def _build_dashboard_investor_economics_status() -> InvestorEconomicsStatus:
    return build_investor_economics_status(
        available=False,
    )


def _build_dashboard_investor_economics_partial_unlock() -> DashboardHistoryInvestorEconomicsPartialUnlock:
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
                unlock_condition="identical_admitted_exact_slice_with_independently_verified_benchmark_total_return_only",
                runtime_enabled=True,
            ),
            DashboardHistoryInvestorEconomicsScalarPolicy(
                field="range_metrics[*].summary.excess_return_pct",
                unlock_condition="identical_admitted_exact_slice_pair_only",
                runtime_enabled=DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED,
            ),
        ],
        client_derivation_rule="server_side_scalar_only_no_daily_series_subtraction_equivalence",
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


RANGE_WINDOWS: dict[str, int | None] = {
    "1M": 21,
    "3M": 63,
    "YTD": None,
    "1Y": 252,
    "All": None,
}


class MonthlyReturnPoint(TypedDict):
    month: str
    return_pct: float


def _admitted_exact_slice_scope(portfolio_proof) -> tuple[str, str, int] | None:
    if portfolio_proof.admission.status != "admitted":
        return None
    if portfolio_proof.admission.readiness_status != "exact_slice_admitted":
        return None

    start_date = portfolio_proof.admission.scope.get("valuation_window_start")
    end_date = portfolio_proof.admission.scope.get("valuation_window_end")
    count = portfolio_proof.admission.scope.get("valuation_date_count")
    if not isinstance(start_date, str) or not isinstance(end_date, str) or not isinstance(count, int) or count <= 0:
        return None
    return start_date, end_date, count


def _slice_matches_admitted_scope(
    performance_points,
    admitted_scope: tuple[str, str, int] | None,
    *,
    source_performance_series=None,
) -> bool:
    if admitted_scope is None or not performance_points:
        return False

    dates = sorted({point.date for point in performance_points})
    if not dates:
        return False

    start_date, end_date, count = admitted_scope
    if dates[0] != start_date or dates[-1] != end_date or len(dates) != count:
        return False

    if source_performance_series is None:
        return True

    source_slice = [point for point in source_performance_series if start_date <= point.date <= end_date]
    if len(source_slice) != len(performance_points):
        return False

    return all(
        point.date == source_point.date
        and point.portfolio_value == source_point.portfolio_value
        and point.benchmark_price == source_point.benchmark_price
        and point.portfolio_return_pct == source_point.portfolio_return_pct
        and point.benchmark_return_pct == source_point.benchmark_return_pct
        for point, source_point in zip(performance_points, source_slice)
    )


def _allow_exact_slice_benchmark_return_output(
    *,
    performance_points,
    admitted_portfolio_twr_scope: tuple[str, str, int] | None,
    benchmark_return_basis_contract: str,
    source_performance_series=None,
) -> bool:
    return (
        benchmark_return_basis_contract == "verified_total_return"
        and _slice_matches_admitted_scope(
            performance_points,
            admitted_portfolio_twr_scope,
            source_performance_series=source_performance_series,
        )
    )


def _allow_future_exact_slice_excess_return_output(
    *,
    performance_points,
    admitted_portfolio_twr_scope: tuple[str, str, int] | None,
    allow_portfolio_twr_outputs: bool,
    allow_exact_slice_benchmark_return_output: bool,
    time_weighted_return_pct: float | None,
    benchmark_return_pct: float | None,
    source_performance_series=None,
) -> bool:
    if not allow_portfolio_twr_outputs or not allow_exact_slice_benchmark_return_output:
        return False
    if time_weighted_return_pct is None or benchmark_return_pct is None:
        return False
    return _slice_matches_admitted_scope(
        performance_points,
        admitted_portfolio_twr_scope,
        source_performance_series=source_performance_series,
    )


def _compute_future_exact_slice_excess_return_pct(
    *,
    performance_points,
    admitted_portfolio_twr_scope: tuple[str, str, int] | None,
    allow_portfolio_twr_outputs: bool,
    allow_exact_slice_benchmark_return_output: bool,
    time_weighted_return_pct: float | None,
    benchmark_return_pct: float | None,
    source_performance_series=None,
) -> float | None:
    if not _allow_future_exact_slice_excess_return_output(
        performance_points=performance_points,
        admitted_portfolio_twr_scope=admitted_portfolio_twr_scope,
        allow_portfolio_twr_outputs=allow_portfolio_twr_outputs,
        allow_exact_slice_benchmark_return_output=allow_exact_slice_benchmark_return_output,
        time_weighted_return_pct=time_weighted_return_pct,
        benchmark_return_pct=benchmark_return_pct,
        source_performance_series=source_performance_series,
    ):
        return None
    if not DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED:
        return None
    portfolio_return = cast(float, time_weighted_return_pct)
    benchmark_return = cast(float, benchmark_return_pct)
    return portfolio_return - benchmark_return


def _withhold_benchmark_return_series(performance_series):
    return [point.model_copy(update={"benchmark_return_pct": None}) for point in performance_series]


def run_dashboard_history_engine(request: DashboardHistoryEngineRequest) -> DashboardHistoryResult:
    history_context = request.history_context
    benchmark_symbol = request.benchmark_symbol or DEFAULT_BENCHMARK_SYMBOL

    if history_context is None or not history_context.history_start_date or not history_context.history_end_date:
        return _build_unavailable_dashboard_history_result(
            input_imported_at=request.imported_at.isoformat() if request.imported_at is not None else None,
            snapshot_as_of_date=request.imported_at.date().isoformat() if request.imported_at is not None else None,
            history_start_date=history_context.history_start_date if history_context is not None else None,
            history_end_date=history_context.history_end_date if history_context is not None else None,
            benchmark_symbol=benchmark_symbol,
        )

    return _build_unavailable_dashboard_history_result(
        input_imported_at=request.imported_at.isoformat() if request.imported_at is not None else None,
        snapshot_as_of_date=request.imported_at.date().isoformat() if request.imported_at is not None else None,
        history_start_date=history_context.history_start_date,
        history_end_date=history_context.history_end_date,
        benchmark_symbol=benchmark_symbol,
    )


def run_imported_dashboard_history(
    snapshot: ImportedPortfolioSnapshot,
    benchmark_symbol: str | None = None,
    *,
    market_data: object | None = None,
) -> DashboardHistoryResult:
    # `market_data` is an injection seam for the dashboard golden pipeline
    # (US-21.4): the generator passes a deterministic frozen provider so goldens
    # don't depend on the live FMP cache. Production callers leave it None and
    # get a live MarketDataService.
    history_start_date, history_end_date = _derive_imported_history_window(snapshot)
    resolved_benchmark_symbol = benchmark_symbol or DEFAULT_BENCHMARK_SYMBOL
    if not history_start_date or not history_end_date:
        return _build_unavailable_dashboard_history_result(
            input_imported_at=snapshot.statement.imported_at.isoformat() if snapshot.statement.imported_at is not None else None,
            snapshot_as_of_date=_derive_snapshot_as_of_date(snapshot),
            history_start_date=None,
            history_end_date=None,
            benchmark_symbol=resolved_benchmark_symbol,
        )

    if market_data is None:
        market_data = MarketDataService()
    if resolved_benchmark_symbol in VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST:
        benchmark_rows = market_data.get_direct_verified_benchmark_history(
            resolved_benchmark_symbol,
            history_start_date,
            history_end_date,
        )
    else:
        benchmark_rows = market_data.get_historical_prices(
            resolved_benchmark_symbol,
            history_start_date,
            history_end_date,
        )
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [position.symbol for position in snapshot.positions],
        history_start_date,
        history_end_date,
    )

    if not benchmark_rows or not _has_any_symbol_price_history(symbol_price_histories):
        return _build_unavailable_dashboard_history_result(
            input_imported_at=snapshot.statement.imported_at.isoformat() if snapshot.statement.imported_at is not None else None,
            snapshot_as_of_date=_derive_snapshot_as_of_date(snapshot),
            history_start_date=None,
            history_end_date=None,
            benchmark_symbol=resolved_benchmark_symbol,
        )

    valuation_dates = sorted({row["date"] for row in benchmark_rows})
    # US-31.2 (Epic 31 F-1): the replay reconstructs OPENING positions and walks
    # them forward, so it values since-sold symbols that are absent from
    # `symbol_price_histories` (today's holdings). Fetched SEPARATELY and used
    # ONLY for the replay — `symbol_price_histories` still feeds the
    # return-basis evidence and the downstream fan-out on the current-holdings
    # basis those consumers are specified against.
    replay_symbols = replay_symbol_universe(snapshot)
    replay_price_histories = market_data.get_historical_prices_for_symbols(
        replay_symbols,
        history_start_date,
        history_end_date,
    )
    # US-31.5 (Epic 31 F-4): convert each holding by its fund currency using the
    # statement's implied rates, instead of carrying values unconverted.
    replay_fund_currencies, replay_fx_history = build_replay_currency_context(
        snapshot, replay_symbols, valuation_dates
    )
    (
        daily_states,
        fx_fallback_currencies,
        unpriced_replay_symbols,
        replay_cash_anchor,
        trade_price_anchored_symbols,
        quantity_withheld,
    ) = build_replay_states_with_cash_anchor(
        snapshot=snapshot,
        price_histories=replay_price_histories,
        valuation_dates=valuation_dates,
        fx_history=replay_fx_history,
        symbol_fund_currencies=replay_fund_currencies,
    )
    # US-31.3 (Epic 31 F-3): dates whose return is withheld because the state
    # carries a material reconciliation adjustment.
    withheld_return_dates, withheld_return_reason = replay_disclosures(daily_states)
    verified_benchmark_scope = _validate_verified_benchmark_slice(
        benchmark_symbol=resolved_benchmark_symbol,
        benchmark_rows=benchmark_rows,
        benchmark_fetch_meta=market_data.get_last_fetch_meta(resolved_benchmark_symbol),
        history_start_date=history_start_date,
        history_end_date=history_end_date,
    )
    portfolio_proof = _build_dashboard_portfolio_proof_metadata(
        snapshot=snapshot,
        symbol_price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
        history_available=True,
    )
    admitted_portfolio_twr_scope = _admitted_exact_slice_scope(portfolio_proof)
    # US-34.2: the proof is built FIRST so the basis can be classified from it.
    # Previously the contract was constructed with a literal and then patched.
    return_basis_contract = _build_dashboard_return_basis_contract(
        benchmark_rows,
        portfolio_path=_classify_portfolio_return_basis(
            daily_states=daily_states,
            admitted_exact_slice=admitted_portfolio_twr_scope is not None,
        ),
    )
    if verified_benchmark_scope is not None:
        return_basis_contract = DashboardHistoryRunMetadata.ReturnBasisContract(
            portfolio_path=return_basis_contract.portfolio_path,
            benchmark_path="verified_total_return",
        )
    raw_performance_series = build_true_performance_series(
        daily_states,
        benchmark_rows,
        portfolio_return_basis_contract=return_basis_contract.portfolio_path,
        benchmark_return_basis_contract=return_basis_contract.benchmark_path,
    )
    if not _has_replay_outputs(daily_states, raw_performance_series):
        return _build_unavailable_dashboard_history_result(
            input_imported_at=snapshot.statement.imported_at.isoformat() if snapshot.statement.imported_at is not None else None,
            snapshot_as_of_date=_derive_snapshot_as_of_date(snapshot),
            history_start_date=None,
            history_end_date=None,
            benchmark_symbol=resolved_benchmark_symbol,
        )
    performance_series = _withhold_benchmark_return_series(raw_performance_series)
    benchmark_history_status = _build_dashboard_benchmark_history_status(benchmark_rows)
    monthly_returns_suppressed = any(state.total_portfolio_value < 0 for state in daily_states)
    allow_drawdown_outputs = _allow_dashboard_drawdown_outputs(
        benchmark_rows=benchmark_rows,
        symbol_price_histories=symbol_price_histories,
    )

    return DashboardHistoryResult(
        daily_states=daily_states,
        performance_series=performance_series,
        source_status={
            "performance_history": "live",
            "monthly_returns": "suppressed" if monthly_returns_suppressed else "live",
        },
        run_metadata=DashboardHistoryRunMetadata(
            history_id=DASHBOARD_HISTORY_ID,
            methodology_id=DASHBOARD_HISTORY_METHODOLOGY_ID,
            source_status=DashboardHistoryRunSourceStatus(
                performance_history="live",
                monthly_returns="suppressed" if monthly_returns_suppressed else "live",
                benchmark_history=benchmark_history_status,
            ),
            section_trust=_build_dashboard_section_trust(
                benchmark_rows=benchmark_rows,
                daily_states=daily_states,
                monthly_returns_suppressed=monthly_returns_suppressed,
            ),
            return_basis_contract=return_basis_contract,
            return_basis_evidence=_build_dashboard_return_basis_evidence(
                benchmark_rows=benchmark_rows,
                symbol_price_histories=symbol_price_histories,
                verified_benchmark_scope=verified_benchmark_scope,
            ),
            portfolio_proof=portfolio_proof,
            investor_economics_status=_build_dashboard_investor_economics_status(),
            investor_economics_partial_unlock=_build_dashboard_investor_economics_partial_unlock(),
            fx_fallback_currencies=fx_fallback_currencies,
            unpriced_replay_symbols=unpriced_replay_symbols,
            trade_price_anchored_symbols=trade_price_anchored_symbols,
            # US-33.2 (Epic 33 F-1/F-2): quantities the replay refused to
            # publish because the symbol's own prices imply a share-unit change.
            quantity_withheld_symbols=[
                ReplayQuantityWithholding(
                    symbol=withholding.symbol,
                    reason=withholding.reason,
                    currency=withholding.currency,
                    price_low=withholding.price_low,
                    price_high=withholding.price_high,
                    price_ratio=withholding.price_ratio,
                    withheld_opening_quantity=withholding.withheld_opening_quantity,
                )
                for withholding in quantity_withheld
            ],
            replay_cash_anchor=(
                ReplayCashAnchor(
                    basis=replay_cash_anchor.basis,
                    nav_as_of=replay_cash_anchor.nav_as_of,
                    window_start=replay_cash_anchor.window_start,
                    residual=replay_cash_anchor.residual,
                    trust=replay_cash_anchor.trust,
                )
                if replay_cash_anchor is not None
                else None
            ),
            withheld_return_dates=withheld_return_dates,
            withheld_return_reason=withheld_return_reason,
            withheld_return_impact_pct=withheld_return_impact_pct(daily_states),
            reproducibility=DashboardHistoryRunReproducibility(
                input_imported_at=snapshot.statement.imported_at.isoformat() if snapshot.statement.imported_at is not None else None,
                snapshot_as_of_date=_derive_snapshot_as_of_date(snapshot),
                history_start_date=history_start_date,
                history_end_date=history_end_date,
                benchmark_symbol=resolved_benchmark_symbol,
                dataset_version=DASHBOARD_HISTORY_DATASET_VERSION,
            ),
        ),
        benchmark=build_benchmark_comparison(
            resolved_benchmark_symbol,
            benchmark_rows,
            return_basis_contract=return_basis_contract.benchmark_path,
            allow_return_pct=False,
        ),
        range_metrics=_build_range_metrics(
            daily_states,
            raw_performance_series,
            allow_drawdown_outputs=allow_drawdown_outputs,
            admitted_portfolio_twr_scope=admitted_portfolio_twr_scope,
            benchmark_return_basis_contract=return_basis_contract.benchmark_path,
            portfolio_return_basis=return_basis_contract.portfolio_path,
        ),
    )


def _build_unavailable_dashboard_history_result(
    *,
    input_imported_at: str | None,
    snapshot_as_of_date: str | None,
    history_start_date: str | None,
    history_end_date: str | None,
    benchmark_symbol: str,
) -> DashboardHistoryResult:
    return DashboardHistoryResult(
        daily_states=[],
        performance_series=[],
        source_status={"performance_history": "unavailable", "monthly_returns": "unavailable"},
        run_metadata=DashboardHistoryRunMetadata(
            history_id=DASHBOARD_HISTORY_ID,
            methodology_id=DASHBOARD_HISTORY_METHODOLOGY_ID,
            source_status=DashboardHistoryRunSourceStatus(
                performance_history="unavailable",
                monthly_returns="unavailable",
                benchmark_history="unavailable",
            ),
            section_trust=DashboardHistoryRunMetadata.SectionTrust(
                portfolio_path="unavailable",
                benchmark_path="unavailable",
                monthly_returns_path="unavailable",
            ),
            return_basis_contract=DashboardHistoryRunMetadata.ReturnBasisContract(
                portfolio_path="unavailable",
                benchmark_path="unavailable",
            ),
            return_basis_evidence=_build_dashboard_return_basis_evidence(benchmark_rows=[]),
            portfolio_proof=build_unavailable_portfolio_proof_metadata(),
            investor_economics_status=build_investor_economics_status(available=False),
            investor_economics_partial_unlock=_build_dashboard_investor_economics_partial_unlock(),
            reproducibility=DashboardHistoryRunReproducibility(
                input_imported_at=input_imported_at,
                snapshot_as_of_date=snapshot_as_of_date,
                history_start_date=history_start_date,
                history_end_date=history_end_date,
                benchmark_symbol=benchmark_symbol,
                dataset_version=DASHBOARD_HISTORY_DATASET_VERSION,
            ),
        ),
        benchmark=None,
        range_metrics=_build_range_metrics(
            [],
            [],
            allow_drawdown_outputs=False,
            admitted_portfolio_twr_scope=None,
            benchmark_return_basis_contract="unavailable",
        ),
    )


def _derive_imported_history_window(snapshot: ImportedPortfolioSnapshot) -> tuple[str | None, str | None]:
    dates = [entry.trade_date.isoformat() for entry in snapshot.ledger_entries if entry.trade_date is not None]
    dates.extend(position.as_of_date.isoformat() for position in snapshot.positions if position.as_of_date is not None)
    if not dates:
        return None, None
    return min(dates), max(dates)


def _derive_snapshot_as_of_date(snapshot: ImportedPortfolioSnapshot) -> str | None:
    return max((position.as_of_date.isoformat() for position in snapshot.positions if position.as_of_date is not None), default=None)


def _has_any_symbol_price_history(symbol_price_histories: dict[str, list[dict]]) -> bool:
    return any(rows for rows in symbol_price_histories.values())


def _has_replay_outputs(daily_states, performance_series) -> bool:
    return bool(daily_states) and bool(performance_series)


def _build_range_metrics(
    daily_states,
    performance_series,
    *,
    allow_drawdown_outputs: bool,
    admitted_portfolio_twr_scope: tuple[str, str, int] | None,
    benchmark_return_basis_contract: str = "unavailable",
    portfolio_return_basis: str = "unavailable",
) -> dict[str, DashboardRangeMetrics]:
    if not performance_series:
        return {
            range_name: DashboardRangeMetrics(
                summary=PerformanceSummary(
                    start_value=None,
                    end_value=None,
                    net_contributions=0.0,
                    investment_gain=None,
                    time_weighted_return_pct=None,
                    money_weighted_return_pct=None,
                    benchmark_return_pct=None,
                    excess_return_pct=None,
                ),
                max_drawdown_pct=None,
                monthly_returns=[],
                monthly_returns_reliable=False,
                portfolio_return_trust="unavailable",
            )
            for range_name in RANGE_WINDOWS
        }

    metrics: dict[str, DashboardRangeMetrics] = {}
    latest_year = performance_series[-1].date[:4]
    for range_name, window in RANGE_WINDOWS.items():
        perf = _slice_performance_series(performance_series, daily_states, range_name, window, latest_year)
        visible_dates = {point.date for point in perf}
        states = [state for state in daily_states if state.date in visible_dates]
        monthly_returns = _compute_contribution_adjusted_monthly_returns(states)
        # US-34.2: the admitted exact slice is the VERIFIED route; a
        # `replay_derived` basis publishes the same number one rung lower. The
        # two are tracked separately so the trust reported below can tell them
        # apart — publishing a degraded return as verified is the failure this
        # story exists to avoid.
        verified_twr_slice = _slice_matches_admitted_scope(
            perf,
            admitted_portfolio_twr_scope,
            source_performance_series=performance_series,
        )
        allow_portfolio_twr_outputs = verified_twr_slice or portfolio_return_basis == "replay_derived"
        allow_exact_slice_benchmark_return_output = _allow_exact_slice_benchmark_return_output(
            performance_points=perf,
            admitted_portfolio_twr_scope=admitted_portfolio_twr_scope,
            benchmark_return_basis_contract=benchmark_return_basis_contract,
            source_performance_series=performance_series,
        )
        metrics[range_name] = DashboardRangeMetrics(
                summary=_compute_visible_summary(
                    states,
                    perf,
                    allow_portfolio_twr_outputs=allow_portfolio_twr_outputs,
                    allow_exact_slice_benchmark_return_output=allow_exact_slice_benchmark_return_output,
                    admitted_portfolio_twr_scope=admitted_portfolio_twr_scope,
                    source_performance_series=performance_series,
                ),
                max_drawdown_pct=_compute_max_drawdown(states) if allow_drawdown_outputs else None,
            monthly_returns=[DashboardMonthlyReturn(month=item["month"], return_pct=item["return_pct"]) for item in monthly_returns],
            monthly_returns_reliable=_monthly_returns_are_reliable(monthly_returns, states),
            portfolio_return_trust=(
                "verified"
                if verified_twr_slice
                else "degraded"
                if allow_portfolio_twr_outputs
                else "unavailable"
            ),
        )
    return metrics


def _slice_performance_series(performance_series, daily_states, range_name: str, window: int | None, latest_year: str):
    if range_name == "YTD":
        return [point for point in performance_series if point.date.startswith(latest_year)]
    if window is None:
        return performance_series
    if len(performance_series) <= window:
        return performance_series

    sliced = performance_series[-window:]
    first_date = sliced[0].date
    # US-34.2: the LATEST state before the window, not the earliest. `next()` over
    # the ascending list returned the first qualifying state in the whole series,
    # so every windowed range was anchored at the series start (2026-01-08) —
    # the 1M slice plotted a 21-day tail against a seven-month-old anchor, and
    # re-basing a range return against it gave since-inception for every window.
    # Invisible until US-34.2 published the numbers.
    prior_state = next(
        (
            state
            for state in reversed(daily_states)
            if state.date < first_date and state.total_portfolio_value > 0
        ),
        None,
    )
    if prior_state is None:
        return sliced

    synthetic_anchor = type(sliced[0])(
        date=prior_state.date,
        portfolio_value=prior_state.total_portfolio_value,
        benchmark_price=sliced[0].benchmark_price,
        portfolio_return_pct=sliced[0].portfolio_return_pct,
        benchmark_return_pct=sliced[0].benchmark_return_pct,
    )
    return [synthetic_anchor, *sliced]


def _compute_money_weighted_return(states) -> float | None:
    if len(states) < 2:
        return None
    start_value = states[0].total_portfolio_value
    end_value = states[-1].total_portfolio_value
    flow_states = states[1:]
    total_flows = sum(state.external_cash_flow for state in flow_states)
    total_periods = max(len(states) - 1, 1)
    weighted_flows = 0.0
    for index, state in enumerate(flow_states):
        periods_remaining = total_periods - index - 1
        weight = periods_remaining / total_periods if total_periods > 0 else 0.0
        weighted_flows += state.external_cash_flow * weight
    denominator = start_value + weighted_flows
    if denominator == 0:
        return None
    return ((end_value - start_value - total_flows) / denominator) * 100


def _last_published_return_pct(performance_points) -> float | None:
    """The most recent non-null cumulative return in a slice (US-34.2)."""
    for point in reversed(performance_points):
        if point.portfolio_return_pct is not None:
            return point.portfolio_return_pct
    return None


def _range_time_weighted_return_pct(anchored_perf, source_performance_series) -> float | None:
    """A range's TWR, re-based to the range's own starting point (US-34.2).

    `portfolio_return_pct` on each point is CUMULATIVE FROM THE SERIES START —
    one chain, computed once. Slicing it therefore does not produce a window
    return: reading the slice's last point gives since-inception for every
    window, so 1M, 3M, YTD, 1Y and All all reported the same number. (The defect
    was invisible while every range was null.)

    Re-basing divides the two cumulative growth factors:

        r_range = (1 + c_end) / (1 + c_start) - 1

    where `c_start` is the cumulative return AT the range's first plotted point,
    so the figure covers exactly the segment the chart draws. Windowed slices
    carry a synthetic anchor at the prior state's date; using `<=` bases on that
    same date, which is why the anchor's own copied return is never the base.
    """
    end_pct = _last_published_return_pct(anchored_perf)
    if end_pct is None or not anchored_perf:
        return end_pct
    start_pct = 0.0
    if source_performance_series:
        range_start = anchored_perf[0].date
        prior = [
            point.portfolio_return_pct
            for point in source_performance_series
            if point.date <= range_start and point.portfolio_return_pct is not None
        ]
        if prior:
            start_pct = prior[-1]
    if start_pct == -100.0:
        return None
    return round((((1 + end_pct / 100) / (1 + start_pct / 100)) - 1) * 100, 2)


def _compute_visible_summary(
    daily_states,
    performance_series,
    *,
    allow_portfolio_twr_outputs: bool,
    allow_exact_slice_benchmark_return_output: bool,
    admitted_portfolio_twr_scope: tuple[str, str, int] | None,
    source_performance_series=None,
) -> PerformanceSummary:
    if not daily_states:
        return PerformanceSummary(
            start_value=None,
            end_value=None,
            net_contributions=0.0,
            investment_gain=None,
            time_weighted_return_pct=None,
            money_weighted_return_pct=None,
            benchmark_return_pct=None,
            excess_return_pct=None,
        )

    anchor_index = next((index for index, state in enumerate(daily_states) if state.total_portfolio_value > 0), 0)
    anchored_states = daily_states[anchor_index:]
    anchor_date = anchored_states[0].date if anchored_states else daily_states[0].date
    anchored_perf = [point for point in performance_series if point.date >= anchor_date]
    start_value = anchored_states[0].total_portfolio_value if anchored_states else None
    end_value = daily_states[-1].total_portfolio_value
    net_contributions = sum(state.external_cash_flow for state in anchored_states[1:]) if anchored_states else 0.0
    investment_gain = (end_value - start_value - net_contributions) if start_value is not None else None
    # US-34.2: the LAST point is not necessarily a published one — the terminal
    # day's return is withheld whenever the state was reconciled (US-31.3), and
    # US-33.2 withholds any day a withheld-quantity holding traded. Reading
    # `[-1]` blindly reported None for the whole range even once the chain was
    # computed. The cumulative return as of the last day we can claim one is the
    # honest figure; the withheld days are already disclosed by name.
    time_weighted_return_pct = (
        _range_time_weighted_return_pct(anchored_perf, source_performance_series)
        if allow_portfolio_twr_outputs
        else None
    )
    benchmark_return_pct = (
        anchored_perf[-1].benchmark_return_pct
        if anchored_perf and allow_exact_slice_benchmark_return_output
        else None
    )
    excess_return_pct = _compute_future_exact_slice_excess_return_pct(
        performance_points=performance_series,
        admitted_portfolio_twr_scope=admitted_portfolio_twr_scope,
        allow_portfolio_twr_outputs=allow_portfolio_twr_outputs,
        allow_exact_slice_benchmark_return_output=allow_exact_slice_benchmark_return_output,
        time_weighted_return_pct=time_weighted_return_pct,
        benchmark_return_pct=benchmark_return_pct,
        source_performance_series=source_performance_series,
    )
    money_weighted_return_pct = _compute_money_weighted_return(anchored_states)
    return PerformanceSummary(
        start_value=start_value,
        end_value=end_value,
        net_contributions=net_contributions,
        investment_gain=investment_gain,
        time_weighted_return_pct=time_weighted_return_pct,
        money_weighted_return_pct=money_weighted_return_pct,
        benchmark_return_pct=benchmark_return_pct,
        excess_return_pct=excess_return_pct,
    )


def _compute_contribution_adjusted_monthly_returns(states) -> list[MonthlyReturnPoint]:
    """Cash-flow-neutral monthly TWR, chained across month boundaries.

    Each daily return is bucketed into the month of its *end* date, so the
    first trading day of month M+1 compounds against the prior month's last
    state (US-27.2 / audit F3 — the previous per-month grouping reset the
    baseline at each month start, dropping every month-boundary return and
    breaking Π(1+mᵢ) = period TWR). A month with no computable daily return
    (e.g. the anchor month containing only the anchor state) emits no entry —
    never a fabricated 0.0%.
    """
    anchor_index = next((index for index, state in enumerate(states) if state.total_portfolio_value > 0), 0)
    anchored_states = states[anchor_index:]
    if not anchored_states:
        return []
    growth_by_month: dict[str, float] = {}
    previous_state = None
    for state in anchored_states:
        if previous_state is not None and previous_state.total_portfolio_value != 0:
            daily_return = ((state.total_portfolio_value - state.external_cash_flow) / previous_state.total_portfolio_value) - 1
            month = state.date[:7]
            growth_by_month[month] = growth_by_month.get(month, 1.0) * (1 + daily_return)
        previous_state = state
    return [
        {"month": month, "return_pct": float((growth - 1) * 100)}
        for month, growth in growth_by_month.items()
    ]


def _monthly_returns_are_reliable(monthly_returns, states) -> bool:
    if len(monthly_returns) < 2:
        return False
    anchor_index = next((index for index, state in enumerate(states) if state.total_portfolio_value > 0), 0)
    anchored_states = states[anchor_index:]
    if len(anchored_states) < 2:
        return False
    has_negative_portfolio_value = any(state.total_portfolio_value < 0 for state in anchored_states)
    extreme_monthly_move = any(abs(item["return_pct"]) > 100 for item in monthly_returns)
    return not has_negative_portfolio_value and not extreme_monthly_move


def _compute_max_drawdown(daily_states) -> float | None:
    """Max drawdown over the compounded return index (methodology
    `drawdown_basis="compounded_return_index"`).

    Built from cash-flow-neutral TWR daily returns so external flows are not
    read as performance (US-27.2 / audit F2 — the previous implementation
    tracked raw `portfolio_value`, letting a deposit mask a real drawdown and
    a withdrawal fabricate one). The wealth index is anchored at 100 on the
    first state's date, matching the drawdown-engine convention, so a decline
    starting on the very first return day still registers.
    """
    if not daily_states:
        return None
    ordered = sorted(daily_states, key=lambda state: state.date)
    returns = _portfolio_time_weighted_return_series(ordered)
    if not returns:
        return None
    wealth_index = _build_wealth_index([(ordered[0].date, 0.0), *returns])
    drawdown_by_date = _build_drawdown_from_return_index(wealth_index)
    if not drawdown_by_date:
        return None
    return min(drawdown_by_date.values())
