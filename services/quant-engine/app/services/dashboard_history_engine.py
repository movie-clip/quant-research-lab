from typing import TypedDict

from app.analytics.performance import build_daily_portfolio_states, build_true_performance_series
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.dashboard_history import DashboardHistoryEngineRequest, DashboardHistoryResult, DashboardMonthlyReturn, DashboardRangeMetrics
from app.schemas.reconciliation import PerformanceSummary
from app.services.benchmark_service import build_benchmark_comparison
from app.services.market_data import MarketDataService


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

    if history_context is None or not history_context.history_start_date or not history_context.history_end_date:
        return _build_unavailable_dashboard_history_result()

    return _build_unavailable_dashboard_history_result()


def run_imported_dashboard_history(snapshot: ImportedPortfolioSnapshot, benchmark_symbol: str | None = None) -> DashboardHistoryResult:
    history_start_date, history_end_date = _derive_imported_history_window(snapshot)
    if not history_start_date or not history_end_date:
        return _build_unavailable_dashboard_history_result()

    resolved_benchmark_symbol = benchmark_symbol or "SPY"
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
        return _build_unavailable_dashboard_history_result()

    valuation_dates = sorted({row["date"] for row in benchmark_rows})
    daily_states = build_daily_portfolio_states(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
        fx_history={},
    )
    performance_series = build_true_performance_series(daily_states, benchmark_rows)

    return DashboardHistoryResult(
        daily_states=daily_states,
        performance_series=performance_series,
        source_status={
            "performance_history": "live",
            "monthly_returns": "suppressed" if any(state.total_portfolio_value < 0 for state in daily_states) else "live",
        },
        benchmark=build_benchmark_comparison(resolved_benchmark_symbol, benchmark_rows),
        range_metrics=_build_range_metrics(daily_states, performance_series),
    )


def _build_unavailable_dashboard_history_result() -> DashboardHistoryResult:
    return DashboardHistoryResult(
        daily_states=[],
        performance_series=[],
        source_status={"performance_history": "unavailable", "monthly_returns": "unavailable"},
        benchmark=None,
        range_metrics=_build_range_metrics([], []),
    )


def _derive_imported_history_window(snapshot: ImportedPortfolioSnapshot) -> tuple[str | None, str | None]:
    dates = [entry.trade_date.isoformat() for entry in snapshot.ledger_entries if entry.trade_date is not None]
    dates.extend(position.as_of_date.isoformat() for position in snapshot.positions if position.as_of_date is not None)
    if not dates:
        return None, None
    return min(dates), max(dates)


def _has_any_symbol_price_history(symbol_price_histories: dict[str, list[dict]]) -> bool:
    return any(rows for rows in symbol_price_histories.values())


def _build_range_metrics(daily_states, performance_series) -> dict[str, DashboardRangeMetrics]:
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
            summary=_compute_visible_summary(states, perf),
            max_drawdown_pct=_compute_max_drawdown(perf),
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


def _compute_visible_summary(daily_states, performance_series) -> PerformanceSummary:
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
    time_weighted_return_pct = anchored_perf[-1].portfolio_return_pct if anchored_perf else None
    benchmark_return_pct = anchored_perf[-1].benchmark_return_pct if anchored_perf else None
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
