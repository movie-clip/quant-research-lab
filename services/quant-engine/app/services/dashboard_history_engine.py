from typing import TypedDict

from app.analytics.performance import build_daily_portfolio_states, build_true_performance_series
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.dashboard_history import DashboardHistoryEngineRequest, DashboardHistoryResult, DashboardHistoryRunMetadata, DashboardHistoryRunReproducibility, DashboardHistoryRunSourceStatus, DashboardMonthlyReturn, DashboardRangeMetrics
from app.schemas.reconciliation import PerformanceSummary
from app.services.benchmark_service import build_benchmark_comparison
from app.services.market_data import MarketDataService, classify_histories_return_basis_contract, classify_history_return_basis_contract, detect_history_return_basis


DASHBOARD_HISTORY_ID = "dashboard_history_engine_v1"
DASHBOARD_HISTORY_METHODOLOGY_ID = "dashboard_history_methodology_v1"
DASHBOARD_HISTORY_DATASET_VERSION = "market_data_service_v1"


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


def _allow_dashboard_compounded_return_outputs(return_basis_contract: DashboardHistoryRunMetadata.ReturnBasisContract) -> bool:
    return (
        return_basis_contract.portfolio_path == "verified_total_return"
        and return_basis_contract.benchmark_path == "verified_total_return"
    )


def _allow_dashboard_drawdown_outputs(
    *,
    benchmark_rows: list[dict],
    symbol_price_histories: dict[str, list[dict]],
) -> bool:
    benchmark_contract = classify_history_return_basis_contract(benchmark_rows)
    position_contract = classify_histories_return_basis_contract(symbol_price_histories)
    return benchmark_contract == "verified_total_return" and position_contract == "verified_total_return"


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
    return_basis_contract = _build_dashboard_return_basis_contract(benchmark_rows)
    performance_series = build_true_performance_series(
        daily_states,
        benchmark_rows,
        portfolio_return_basis_contract=return_basis_contract.portfolio_path,
        benchmark_return_basis_contract=return_basis_contract.benchmark_path,
    )
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
            reproducibility=DashboardHistoryRunReproducibility(
                input_imported_at=snapshot.statement.imported_at.isoformat() if snapshot.statement.imported_at is not None else None,
                snapshot_as_of_date=_derive_snapshot_as_of_date(snapshot),
                history_start_date=history_start_date,
                history_end_date=history_end_date,
                benchmark_symbol=resolved_benchmark_symbol,
                dataset_version=DASHBOARD_HISTORY_DATASET_VERSION,
            ),
        ),
        benchmark=build_benchmark_comparison(resolved_benchmark_symbol, benchmark_rows),
        range_metrics=_build_range_metrics(
            daily_states,
            performance_series,
            allow_drawdown_outputs=allow_drawdown_outputs,
            allow_compounded_return_outputs=_allow_dashboard_compounded_return_outputs(return_basis_contract),
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
        range_metrics=_build_range_metrics([], [], allow_drawdown_outputs=False, allow_compounded_return_outputs=False),
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


def _build_range_metrics(daily_states, performance_series, *, allow_drawdown_outputs: bool, allow_compounded_return_outputs: bool) -> dict[str, DashboardRangeMetrics]:
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
        metrics[range_name] = DashboardRangeMetrics(
                summary=_compute_visible_summary(states, perf, allow_compounded_return_outputs=allow_compounded_return_outputs),
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


def _compute_visible_summary(daily_states, performance_series, *, allow_compounded_return_outputs: bool) -> PerformanceSummary:
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
    time_weighted_return_pct = anchored_perf[-1].portfolio_return_pct if anchored_perf and allow_compounded_return_outputs else None
    benchmark_return_pct = anchored_perf[-1].benchmark_return_pct if anchored_perf and allow_compounded_return_outputs else None
    money_weighted_return_pct = _compute_money_weighted_return(anchored_states)
    excess_return_pct = None
    if time_weighted_return_pct is not None and benchmark_return_pct is not None:
        excess_return_pct = time_weighted_return_pct - benchmark_return_pct
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
