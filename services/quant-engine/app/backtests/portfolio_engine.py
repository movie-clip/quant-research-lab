from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import sqrt
from statistics import mean, stdev

from app.schemas.backtest_engine import (
    AllocationBacktestAssumptions,
    AllocationBacktestInstrumentMeta,
    AllocationBacktestMetrics,
    AllocationBacktestPoint,
    AllocationBacktestRebalanceEvent,
    AllocationBacktestResult,
    AllocationBacktestStatus,
    AllocationBacktestTrade,
    AllocationBacktestWeight,
    AllocationRebalanceFrequency,
    PortfolioAllocationBacktestRequest,
    PortfolioWeightInput,
)


CALENDAR_POLICY = "intersection_common_dates"
TAX_TREATMENT = "pre_tax"


@dataclass
class DecisionEvent:
    decision_date: str
    execution_date: str


def _safe_stdev(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    return stdev(values)


def _annualized_volatility(values: list[float]) -> float | None:
    sample = _safe_stdev(values)
    if sample is None:
        return None
    return sample * sqrt(252)


def _downside_annualized_volatility(values: list[float]) -> float | None:
    downside = [min(value, 0.0) for value in values]
    sample = _safe_stdev(downside)
    if sample is None:
        return None
    return sample * sqrt(252)


def _covariance(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = mean(left)
    right_mean = mean(right)
    return sum((x - left_mean) * (y - right_mean) for x, y in zip(left, right, strict=False)) / (len(left) - 1)


def _correlation(left: list[float], right: list[float]) -> float | None:
    covariance = _covariance(left, right)
    left_stdev = _safe_stdev(left)
    right_stdev = _safe_stdev(right)
    if covariance is None or left_stdev is None or right_stdev is None or left_stdev == 0 or right_stdev == 0:
        return None
    denominator = left_stdev * right_stdev
    return covariance / denominator


def _annualized_return(start_value: float, end_value: float, start_date: str, end_date: str) -> float | None:
    if start_value <= 0 or end_value <= 0:
        return None
    elapsed_days = (date.fromisoformat(end_date) - date.fromisoformat(start_date)).days
    if elapsed_days <= 0:
        return None
    return (end_value / start_value) ** (365.25 / elapsed_days) - 1


def _allow_allocation_backtest_investor_economics_outputs() -> bool:
    return False


def _row_price(row: dict) -> float:
    if row.get("adjClose") is not None:
        return float(row["adjClose"])
    if row.get("adjusted_close") is not None:
        return float(row["adjusted_close"])
    return float(row["price"])


class PortfolioAllocationBacktestEngine:
    def run(
        self,
        *,
        request: PortfolioAllocationBacktestRequest,
        portfolio_name: str | None,
        weights: list[PortfolioWeightInput],
        benchmark_rows: list[dict],
        price_histories: dict[str, list[dict]],
        ordered_dates: list[str],
        instrument_metadata: list[AllocationBacktestInstrumentMeta],
        status: AllocationBacktestStatus,
    ) -> AllocationBacktestResult:
        if len(ordered_dates) < 2:
            raise ValueError("Not enough aligned price history for portfolio allocation backtest")

        ordered_date_set = set(ordered_dates)
        price_map_by_symbol = {
            symbol: {row["date"]: _row_price(row) for row in rows if row.get("date") in ordered_date_set}
            for symbol, rows in price_histories.items()
        }
        benchmark_by_date = {row["date"]: _row_price(row) for row in benchmark_rows if row.get("date") in ordered_date_set}
        decisions = _determine_rebalance_schedule(ordered_dates, request.rebalance_frequency, request.execution_lag_days)
        decisions_by_decision_date = {event.decision_date: event for event in decisions}
        pending_rebalances: dict[str, DecisionEvent] = {}

        starting_weights = [AllocationBacktestWeight(symbol=item.symbol, target_weight=item.target_weight) for item in weights]
        quantities = {item.symbol: 0.0 for item in weights}
        cash = request.initial_capital
        trades: list[AllocationBacktestTrade] = []
        rebalance_events: list[AllocationBacktestRebalanceEvent] = []

        first_execution_index = min(request.execution_lag_days, len(ordered_dates) - 1)
        active_dates = ordered_dates[first_execution_index:]
        first_execution_date = active_dates[0]
        first_prices = {item.symbol: price_map_by_symbol[item.symbol][first_execution_date] for item in weights}
        quantities, cash, initial_trades, initial_cost = _execute_target_weights(
            execution_date=first_execution_date,
            weights=weights,
            quantities=quantities,
            cash=cash,
            current_prices=first_prices,
            equity=request.initial_capital,
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
        )
        trades.extend(initial_trades)
        rebalance_events.append(
            AllocationBacktestRebalanceEvent(
                decision_date=ordered_dates[0],
                execution_date=first_execution_date,
                turnover_pct=100.0,
                traded_notional=round(request.initial_capital, 2),
                total_cost=round(initial_cost, 2),
            )
        )

        equity_curve: list[AllocationBacktestPoint] = []
        previous_equity: float | None = None
        previous_benchmark_price: float | None = None
        portfolio_returns: list[float] = []
        benchmark_returns: list[float] = []
        active_returns: list[float] = []
        peak_equity = request.initial_capital

        for current_date in active_dates:
            current_prices = {item.symbol: price_map_by_symbol[item.symbol][current_date] for item in weights}
            holdings_value = sum(quantities[item.symbol] * current_prices[item.symbol] for item in weights)
            equity_before_trade = cash + holdings_value

            decision = decisions_by_decision_date.get(current_date)
            if decision is not None:
                should_rebalance = True
                if request.drift_tolerance_pct is not None:
                    should_rebalance = _breaches_drift_tolerance(weights, quantities, current_prices, equity_before_trade, request.drift_tolerance_pct)
                if should_rebalance:
                    pending_rebalances[decision.execution_date] = decision

            scheduled_rebalance = pending_rebalances.pop(current_date, None)
            if scheduled_rebalance is not None and current_date != first_execution_date:
                turnover_pct = _compute_turnover(weights, quantities, current_prices, equity_before_trade)
                quantities, cash, event_trades, total_cost = _execute_target_weights(
                    execution_date=current_date,
                    weights=weights,
                    quantities=quantities,
                    cash=cash,
                    current_prices=current_prices,
                    equity=equity_before_trade,
                    commission_bps=request.commission_bps,
                    slippage_bps=request.slippage_bps,
                )
                traded_notional = sum(trade.traded_notional or 0.0 for trade in event_trades)
                rebalance_events.append(
                    AllocationBacktestRebalanceEvent(
                        decision_date=scheduled_rebalance.decision_date,
                        execution_date=current_date,
                        turnover_pct=round(turnover_pct, 2) if turnover_pct is not None else None,
                        traded_notional=round(traded_notional, 2),
                        total_cost=round(total_cost, 2),
                    )
                )
                trades.extend(event_trades)
                holdings_value = sum(quantities[item.symbol] * current_prices[item.symbol] for item in weights)

            equity = cash + holdings_value
            peak_equity = max(peak_equity, equity)
            drawdown_pct = ((equity / peak_equity) - 1) * 100 if peak_equity else None
            gross_exposure = sum(abs(quantities[item.symbol] * current_prices[item.symbol]) for item in weights)

            equity_curve.append(
                AllocationBacktestPoint(
                    date=current_date,
                    equity=round(equity, 2),
                    cash=round(cash, 2),
                    gross_exposure=round(gross_exposure, 2),
                    drawdown_pct=round(drawdown_pct, 2) if drawdown_pct is not None else None,
                )
            )

            benchmark_price = benchmark_by_date[current_date]
            if previous_equity is not None and previous_equity != 0 and previous_benchmark_price is not None and previous_benchmark_price != 0:
                previous_equity_value = previous_equity
                previous_benchmark_value = previous_benchmark_price
                portfolio_return = (equity / previous_equity_value) - 1
                benchmark_return = (benchmark_price / previous_benchmark_value) - 1
                portfolio_returns.append(portfolio_return)
                benchmark_returns.append(benchmark_return)
                active_returns.append(portfolio_return - benchmark_return)

            previous_equity = equity
            previous_benchmark_price = benchmark_price

        ending_equity = equity_curve[-1].equity
        final_prices = {item.symbol: price_map_by_symbol[item.symbol][active_dates[-1]] for item in weights}
        ending_weights = _build_ending_weights(weights, quantities, final_prices, ending_equity)
        metrics = _compute_metrics(
            equity_curve=equity_curve,
            initial_capital=request.initial_capital,
            portfolio_returns=portfolio_returns,
            benchmark_returns=benchmark_returns,
            active_returns=active_returns,
            benchmark_start=benchmark_by_date[active_dates[0]],
            benchmark_end=benchmark_by_date[active_dates[-1]],
            total_cost_paid=sum(event.total_cost or 0.0 for event in rebalance_events),
            total_turnover_pct=sum(event.turnover_pct or 0.0 for event in rebalance_events[1:]),
            turnover_events_count=max(len(rebalance_events) - 1, 0),
            start_date=active_dates[0],
            end_date=active_dates[-1],
        )

        return AllocationBacktestResult(
            portfolio_name=portfolio_name,
            benchmark_symbol=request.benchmark_symbol,
            start_date=active_dates[0],
            end_date=active_dates[-1],
            observation_count=len(active_dates),
            rebalance_frequency=request.rebalance_frequency,
            commission_bps=request.commission_bps,
            slippage_bps=request.slippage_bps,
            drift_tolerance_pct=request.drift_tolerance_pct,
            assumptions=AllocationBacktestAssumptions(
                price_basis=request.price_basis,
                execution_price_field=request.execution_price_field,
                execution_lag_days=request.execution_lag_days,
                calendar_policy=CALENDAR_POLICY,
                fractional_shares=True,
                long_only=True,
                leverage_allowed=False,
                tax_treatment=TAX_TREATMENT,
                investor_base_currency=request.base_currency,
            ),
            status=status,
            instrument_metadata=instrument_metadata,
            starting_weights=starting_weights,
            ending_weights=ending_weights,
            metrics=metrics,
            equity_curve=equity_curve,
            rebalance_events=rebalance_events,
            trades=trades,
        )


def _determine_rebalance_schedule(
    ordered_dates: list[str],
    frequency: AllocationRebalanceFrequency,
    execution_lag_days: int,
) -> list[DecisionEvent]:
    if frequency == "none":
        return []
    events: list[DecisionEvent] = []
    for index in range(len(ordered_dates) - 1):
        decision_date = ordered_dates[index]
        next_date = ordered_dates[index + 1]
        decision = date.fromisoformat(decision_date)
        next_decision = date.fromisoformat(next_date)
        if frequency == "monthly":
            boundary_changed = (decision.year, decision.month) != (next_decision.year, next_decision.month)
        else:
            decision_quarter = (decision.month - 1) // 3
            next_quarter = (next_decision.month - 1) // 3
            boundary_changed = (decision.year, decision_quarter) != (next_decision.year, next_quarter)
        if not boundary_changed:
            continue
        execution_index = min(index + execution_lag_days, len(ordered_dates) - 1)
        if execution_index <= index:
            continue
        events.append(DecisionEvent(decision_date=decision_date, execution_date=ordered_dates[execution_index]))
    return events


def _breaches_drift_tolerance(
    weights: list[PortfolioWeightInput],
    quantities: dict[str, float],
    current_prices: dict[str, float],
    equity: float,
    drift_tolerance_pct: float,
) -> bool:
    if equity <= 0:
        return False
    for item in weights:
        current_weight_pct = (quantities[item.symbol] * current_prices[item.symbol] / equity) * 100
        target_weight_pct = item.target_weight * 100
        if abs(current_weight_pct - target_weight_pct) > drift_tolerance_pct:
            return True
    return False


def _compute_turnover(
    weights: list[PortfolioWeightInput],
    quantities: dict[str, float],
    current_prices: dict[str, float],
    equity: float,
) -> float | None:
    if equity <= 0:
        return None
    total = 0.0
    for item in weights:
        realized_weight = (quantities[item.symbol] * current_prices[item.symbol]) / equity
        total += abs(item.target_weight - realized_weight)
    return total * 50


def _execute_target_weights(
    *,
    execution_date: str,
    weights: list[PortfolioWeightInput],
    quantities: dict[str, float],
    cash: float,
    current_prices: dict[str, float],
    equity: float,
    commission_bps: float,
    slippage_bps: float,
) -> tuple[dict[str, float], float, list[AllocationBacktestTrade], float]:
    next_quantities = dict(quantities)
    trades: list[AllocationBacktestTrade] = []
    traded_notional = 0.0

    for item in weights:
        current_value = next_quantities[item.symbol] * current_prices[item.symbol]
        target_value = equity * item.target_weight
        trade_value = target_value - current_value
        if abs(trade_value) < 1e-9:
            continue
        trade_quantity = trade_value / current_prices[item.symbol] if current_prices[item.symbol] else 0.0
        action = "buy" if trade_quantity > 0 else "sell"
        traded_notional += abs(trade_value)
        next_quantities[item.symbol] += trade_quantity
        cash -= trade_value
        commission_cost = abs(trade_value) * (commission_bps / 10000)
        slippage_cost = abs(trade_value) * (slippage_bps / 10000)
        trades.append(
            AllocationBacktestTrade(
                date=execution_date,
                symbol=item.symbol,
                action=action,
                quantity=round(abs(trade_quantity), 6),
                price=round(current_prices[item.symbol], 6),
                traded_notional=round(abs(trade_value), 2),
                commission_cost=round(commission_cost, 2),
                slippage_cost=round(slippage_cost, 2),
                total_cost=round(commission_cost + slippage_cost, 2),
            )
        )

    total_cost = sum(trade.total_cost or 0.0 for trade in trades)
    cash -= total_cost
    return next_quantities, cash, trades, total_cost


def _build_ending_weights(
    weights: list[PortfolioWeightInput],
    quantities: dict[str, float],
    final_prices: dict[str, float],
    ending_equity: float,
) -> list[AllocationBacktestWeight]:
    if ending_equity == 0:
        return [AllocationBacktestWeight(symbol=item.symbol, target_weight=0.0) for item in weights]
    return [
        AllocationBacktestWeight(
            symbol=item.symbol,
            target_weight=round((quantities[item.symbol] * final_prices[item.symbol]) / ending_equity, 6),
        )
        for item in weights
    ]


def _compute_metrics(
    *,
    equity_curve: list[AllocationBacktestPoint],
    initial_capital: float,
    portfolio_returns: list[float],
    benchmark_returns: list[float],
    active_returns: list[float],
    benchmark_start: float,
    benchmark_end: float,
    total_cost_paid: float,
    total_turnover_pct: float,
    turnover_events_count: int,
    start_date: str,
    end_date: str,
) -> AllocationBacktestMetrics:
    allow_investor_economics_outputs = _allow_allocation_backtest_investor_economics_outputs()
    start_equity = initial_capital
    end_equity = equity_curve[-1].equity if equity_curve else 0.0
    total_return = ((end_equity / start_equity) - 1) if start_equity else None
    annualized_return = _annualized_return(start_equity, end_equity, start_date, end_date)
    annualized_volatility = _annualized_volatility(portfolio_returns)
    downside_volatility = _downside_annualized_volatility(portfolio_returns)
    tracking_error = _annualized_volatility(active_returns)
    benchmark_return = ((benchmark_end / benchmark_start) - 1) if benchmark_start else None
    average_portfolio_return = mean(portfolio_returns) * 252 if portfolio_returns else None
    average_active_return = mean(active_returns) * 252 if active_returns else None
    beta = None
    benchmark_stdev = _safe_stdev(benchmark_returns)
    covariance = _covariance(portfolio_returns, benchmark_returns)
    if covariance is not None and benchmark_stdev is not None and benchmark_stdev != 0:
        benchmark_variance = benchmark_stdev**2
        beta = covariance / benchmark_variance
    correlation = _correlation(portfolio_returns, benchmark_returns)
    max_drawdown = min((point.drawdown_pct or 0.0) for point in equity_curve) if equity_curve else None

    sharpe = None
    if average_portfolio_return is not None and annualized_volatility is not None and annualized_volatility != 0:
        annualized_volatility_value = annualized_volatility
        sharpe = average_portfolio_return / annualized_volatility_value

    sortino = None
    if average_portfolio_return is not None and downside_volatility is not None and downside_volatility != 0:
        downside_volatility_value = downside_volatility
        sortino = average_portfolio_return / downside_volatility_value

    information_ratio = None
    if average_active_return is not None and tracking_error is not None and tracking_error != 0:
        tracking_error_value = tracking_error
        information_ratio = average_active_return / tracking_error_value

    excess_return = (total_return - benchmark_return) if total_return is not None and benchmark_return is not None else None

    return AllocationBacktestMetrics(
        total_return_pct=round(total_return * 100, 2) if total_return is not None and allow_investor_economics_outputs else None,
        annualized_return_pct=round(annualized_return * 100, 2) if annualized_return is not None and allow_investor_economics_outputs else None,
        annualized_volatility_pct=round(annualized_volatility * 100, 2) if annualized_volatility is not None else None,
        downside_volatility_pct=round(downside_volatility * 100, 2) if downside_volatility is not None else None,
        max_drawdown_pct=round(max_drawdown, 2) if max_drawdown is not None and allow_investor_economics_outputs else None,
        sharpe_ratio=round(sharpe, 4) if sharpe is not None and allow_investor_economics_outputs else None,
        sortino_ratio=round(sortino, 4) if sortino is not None and allow_investor_economics_outputs else None,
        benchmark_return_pct=round(benchmark_return * 100, 2) if benchmark_return is not None and allow_investor_economics_outputs else None,
        excess_return_pct=round(excess_return * 100, 2) if excess_return is not None and allow_investor_economics_outputs else None,
        tracking_error_pct=round(tracking_error * 100, 2) if tracking_error is not None else None,
        information_ratio=round(information_ratio, 4) if information_ratio is not None and allow_investor_economics_outputs else None,
        beta_vs_benchmark=round(beta, 4) if beta is not None else None,
        correlation_vs_benchmark=round(correlation, 4) if correlation is not None else None,
        total_turnover_pct=round(total_turnover_pct, 2),
        turnover_events_count=turnover_events_count,
        total_cost_paid=round(total_cost_paid, 2),
    )
