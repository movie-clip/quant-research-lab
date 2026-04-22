from typing import TypedDict, cast

from app.analytics.performance import build_daily_portfolio_states, build_true_performance_series
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.dashboard_history import (
    DashboardHistoryEngineRequest,
    DashboardHistoryInvestorEconomicsPartialUnlock,
    DashboardHistoryInvestorEconomicsScalarPolicy,
    DashboardHistoryResult,
    DashboardHistoryRunMetadata,
    DashboardHistoryRunReproducibility,
    DashboardHistoryRunSourceStatus,
    DashboardMonthlyReturn,
    DashboardRangeMetrics,
)
from app.schemas.research import InvestorEconomicsStatus, build_investor_economics_status
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


def _build_dashboard_return_basis_contract(benchmark_rows: list[dict]) -> DashboardHistoryRunMetadata.ReturnBasisContract:
    benchmark_contract = classify_history_return_basis_contract(benchmark_rows)
    return DashboardHistoryRunMetadata.ReturnBasisContract(
        portfolio_path="unavailable",
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
    benchmark_symbol = request.benchmark_symbol or "SPY"

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


def run_imported_dashboard_history(snapshot: ImportedPortfolioSnapshot, benchmark_symbol: str | None = None) -> DashboardHistoryResult:
    history_start_date, history_end_date = _derive_imported_history_window(snapshot)
    resolved_benchmark_symbol = benchmark_symbol or "SPY"
    if not history_start_date or not history_end_date:
        return _build_unavailable_dashboard_history_result(
            input_imported_at=snapshot.statement.imported_at.isoformat() if snapshot.statement.imported_at is not None else None,
            snapshot_as_of_date=_derive_snapshot_as_of_date(snapshot),
            history_start_date=None,
            history_end_date=None,
            benchmark_symbol=resolved_benchmark_symbol,
        )

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
    daily_states = build_daily_portfolio_states(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
        fx_history={},
    )
    verified_benchmark_scope = _validate_verified_benchmark_slice(
        benchmark_symbol=resolved_benchmark_symbol,
        benchmark_rows=benchmark_rows,
        benchmark_fetch_meta=market_data.get_last_fetch_meta(resolved_benchmark_symbol),
        history_start_date=history_start_date,
        history_end_date=history_end_date,
    )
    return_basis_contract = _build_dashboard_return_basis_contract(benchmark_rows)
    if verified_benchmark_scope is not None:
        return_basis_contract = DashboardHistoryRunMetadata.ReturnBasisContract(
            portfolio_path=return_basis_contract.portfolio_path,
            benchmark_path="verified_total_return",
        )
    portfolio_proof = _build_dashboard_portfolio_proof_metadata(
        snapshot=snapshot,
        symbol_price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
        history_available=True,
    )
    admitted_portfolio_twr_scope = _admitted_exact_slice_scope(portfolio_proof)
    raw_performance_series = build_true_performance_series(
        daily_states,
        benchmark_rows,
        portfolio_return_basis_contract=(
            "verified_total_return" if admitted_portfolio_twr_scope is not None else return_basis_contract.portfolio_path
        ),
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
    allow_exact_slice_benchmark_return_output = _allow_exact_slice_benchmark_return_output(
        performance_points=raw_performance_series,
        admitted_portfolio_twr_scope=admitted_portfolio_twr_scope,
        benchmark_return_basis_contract=return_basis_contract.benchmark_path,
        source_performance_series=raw_performance_series,
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
        allow_portfolio_twr_outputs = _slice_matches_admitted_scope(
            perf,
            admitted_portfolio_twr_scope,
            source_performance_series=performance_series,
        )
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
                max_drawdown_pct=_compute_max_drawdown(perf) if allow_drawdown_outputs else None,
            monthly_returns=[DashboardMonthlyReturn(month=item["month"], return_pct=item["return_pct"]) for item in monthly_returns],
            monthly_returns_reliable=_monthly_returns_are_reliable(monthly_returns, states),
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
    prior_state = next((state for state in daily_states if state.date < first_date and state.total_portfolio_value > 0), None)
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
    time_weighted_return_pct = anchored_perf[-1].portfolio_return_pct if anchored_perf and allow_portfolio_twr_outputs else None
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
    anchor_index = next((index for index, state in enumerate(states) if state.total_portfolio_value > 0), 0)
    anchored_states = states[anchor_index:]
    if not anchored_states:
        return []
    grouped: dict[str, list] = {}
    for state in anchored_states:
        grouped.setdefault(state.date[:7], []).append(state)
    results: list[MonthlyReturnPoint] = []
    for month, month_states in grouped.items():
        cumulative_growth = 1.0
        previous_state = None
        for state in month_states:
            if previous_state is not None and previous_state.total_portfolio_value != 0:
                daily_return = ((state.total_portfolio_value - state.external_cash_flow) / previous_state.total_portfolio_value) - 1
                cumulative_growth *= 1 + daily_return
            previous_state = state
        results.append({"month": month, "return_pct": float((cumulative_growth - 1) * 100)})
    return results


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


def _compute_max_drawdown(performance_series) -> float | None:
    if not performance_series:
        return None
    peak = 0.0
    max_drawdown = 0.0
    for point in performance_series:
        peak = max(peak, point.portfolio_value)
        if peak > 0:
            max_drawdown = min(max_drawdown, ((point.portfolio_value - peak) / peak) * 100)
    return max_drawdown
