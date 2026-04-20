from app.engine.portfolio_state import PortfolioStateEngine
from app.analytics.risk import selected_history_price_map
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import DailyPortfolioState, EnrichedPosition, PerformancePoint, PerformanceSummary
from app.services.market_data import HistoryReturnBasisContract, classify_history_return_basis_contract


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None

    return float(str(value))


def build_enriched_positions(snapshot: ImportedPortfolioSnapshot, quotes: dict[str, dict]) -> list[EnrichedPosition]:
    positions: list[EnrichedPosition] = []
    for position in sorted(snapshot.positions, key=lambda item: item.market_value, reverse=True):
        quote = quotes.get(position.symbol, {})
        latest_price_float = _coerce_float(quote.get("price"))
        daily_change_float = _coerce_float(quote.get("change"))
        latest_market_value = round(latest_price_float * position.quantity, 2) if latest_price_float is not None else None
        previous_price_float = (latest_price_float - daily_change_float) if latest_price_float is not None and daily_change_float is not None else None
        daily_change_pct = None
        if daily_change_float is not None and previous_price_float is not None and previous_price_float != 0:
            previous_price = float(previous_price_float)
            daily_change_pct = round((daily_change_float / previous_price) * 100, 2)

        positions.append(
            EnrichedPosition(
                symbol=position.symbol,
                quantity=position.quantity,
                statement_price=position.close_price,
                statement_market_value=position.market_value,
                latest_price=latest_price_float,
                latest_market_value=latest_market_value,
                daily_change=daily_change_float,
                daily_change_pct=daily_change_pct,
                unrealized_pnl=position.unrealized_pnl,
                currency=position.currency,
            )
        )

    return positions


def build_daily_portfolio_states(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    fx_history: dict[str, float],
) -> list[DailyPortfolioState]:
    engine = PortfolioStateEngine(snapshot=snapshot, base_currency=snapshot.statement.base_currency or "USD", fx_history=fx_history)
    return engine.build_daily_states(price_histories=price_histories, valuation_dates=valuation_dates)


def build_true_performance_series(
    daily_states: list[DailyPortfolioState],
    benchmark_rows: list[dict],
    *,
    portfolio_return_basis_contract: HistoryReturnBasisContract = "verified_total_return",
    benchmark_return_basis_contract: HistoryReturnBasisContract | None = None,
) -> list[PerformancePoint]:
    if not daily_states or not benchmark_rows:
        return []

    benchmark_by_date, _ = selected_history_price_map(benchmark_rows)
    resolved_benchmark_return_basis_contract = benchmark_return_basis_contract or classify_history_return_basis_contract(benchmark_rows)
    first_portfolio_value = next((state.total_portfolio_value for state in daily_states if state.total_portfolio_value > 0), None)
    benchmark_dates = sorted(benchmark_by_date)
    first_benchmark_price = benchmark_by_date[benchmark_dates[0]] if benchmark_dates else None
    if first_portfolio_value is None or first_benchmark_price is None:
        return []

    points: list[PerformancePoint] = []
    benchmark_start_price = float(first_benchmark_price)
    cumulative_growth = 1.0
    previous_state: DailyPortfolioState | None = None
    for state in daily_states:
        benchmark_price = benchmark_by_date.get(state.date)
        portfolio_return_pct = 0.0
        if previous_state is not None:
            daily_return = _time_weighted_daily_return(previous_state, state)
            if daily_return is not None and portfolio_return_basis_contract == "verified_total_return":
                cumulative_growth *= 1 + daily_return
                portfolio_return_pct = round((cumulative_growth - 1) * 100, 2)
        benchmark_return_pct = (
            round(((benchmark_price / benchmark_start_price) - 1) * 100, 2)
            if benchmark_price is not None and benchmark_start_price != 0 and resolved_benchmark_return_basis_contract == "verified_total_return"
            else None
        )
        points.append(
            PerformancePoint(
                date=state.date,
                portfolio_value=state.total_portfolio_value,
                benchmark_price=benchmark_price,
                portfolio_return_pct=portfolio_return_pct,
                benchmark_return_pct=benchmark_return_pct,
            )
        )
        previous_state = state

    return points


def _time_weighted_daily_return(previous_state: DailyPortfolioState, current_state: DailyPortfolioState) -> float | None:
    if previous_state.total_portfolio_value == 0:
        return None
    return ((current_state.total_portfolio_value - current_state.external_cash_flow) / previous_state.total_portfolio_value) - 1


def build_performance_summary(daily_states: list[DailyPortfolioState], performance_series: list[PerformancePoint]) -> PerformanceSummary:
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

    start_value = daily_states[0].total_portfolio_value
    end_value = daily_states[-1].total_portfolio_value
    net_contributions = round(sum(state.external_cash_flow for state in daily_states[1:]), 2)
    investment_gain = round(end_value - start_value - net_contributions, 2)
    time_weighted_return_pct = performance_series[-1].portfolio_return_pct if performance_series else None
    benchmark_return_pct = performance_series[-1].benchmark_return_pct if performance_series else None
    excess_return_pct = round(time_weighted_return_pct - benchmark_return_pct, 2) if time_weighted_return_pct is not None and benchmark_return_pct is not None else None

    money_weighted_return_pct: float | None = None
    if len(daily_states) >= 2:
        flow_states = daily_states[1:]
        total_flows = sum(state.external_cash_flow for state in flow_states)
        total_periods = max(len(daily_states) - 1, 1)
        weighted_flows = sum(
            state.external_cash_flow * ((total_periods - index - 1) / total_periods)
            for index, state in enumerate(flow_states)
        )
        denominator = start_value + weighted_flows
        if denominator != 0:
            money_weighted_return_pct = round(((end_value - start_value - total_flows) / denominator) * 100, 2)

    return PerformanceSummary(
        start_value=round(start_value, 2),
        end_value=round(end_value, 2),
        net_contributions=net_contributions,
        investment_gain=investment_gain,
        time_weighted_return_pct=time_weighted_return_pct,
        money_weighted_return_pct=money_weighted_return_pct,
        benchmark_return_pct=benchmark_return_pct,
        excess_return_pct=excess_return_pct,
    )
