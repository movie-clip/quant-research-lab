from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition, RebalancePoint, SimulatedTrade


def apply_simulated_trades_to_state(
    state: DailyPortfolioState | None,
    trades: list[SimulatedTrade],
) -> DailyPortfolioState | None:
    if state is None:
        return None

    positions = {position.symbol: DailyStatePosition(**position.model_dump()) for position in state.positions}
    cash = dict(state.cash)
    base_currency = next(iter(cash)) if cash else "USD"

    for trade in trades:
        if trade.date != state.date or trade.reference_price in {None, 0}:
            continue

        symbol = trade.symbol
        reference_price = trade.reference_price
        if reference_price is None:
            continue
        price = float(reference_price)
        current = positions.get(symbol, DailyStatePosition(symbol=symbol, quantity=0.0, market_price=price, market_value=0.0))
        if trade.action == "BUY":
            current.quantity += trade.quantity
        elif trade.action == "SELL":
            current.quantity -= trade.quantity

        current.market_price = price
        current.market_value = round(current.quantity * price, 2)
        positions[symbol] = current
        cash[base_currency] = round(cash.get(base_currency, 0.0) + (trade.estimated_cash_impact or 0.0), 2)

    total_market_value = round(sum(position.market_value or 0.0 for position in positions.values()), 2)
    total_portfolio_value = round(total_market_value + sum(cash.values()), 2)

    return DailyPortfolioState(
        date=state.date,
        cash=cash,
        positions=sorted(positions.values(), key=lambda position: position.symbol),
        total_market_value=total_market_value,
        total_portfolio_value=total_portfolio_value,
    )


def build_rebalance_preview(
    daily_states: list[DailyPortfolioState],
    benchmark_rows: list[dict],
    target_equity_weight: float = 0.9,
    tolerance: float = 0.05,
) -> list[RebalancePoint]:
    benchmark_by_date = {row["date"]: float(row["price"]) for row in benchmark_rows}
    preview: list[RebalancePoint] = []

    for state in daily_states:
        if state.total_portfolio_value <= 0:
            continue
        actual_equity_weight = round(state.total_market_value / state.total_portfolio_value, 4)
        action = "hold"
        if actual_equity_weight < target_equity_weight - tolerance:
            action = "buy_equities"
        elif actual_equity_weight > target_equity_weight + tolerance:
            action = "raise_cash"

        preview.append(
            RebalancePoint(
                date=state.date,
                portfolio_value=state.total_portfolio_value,
                benchmark_price=benchmark_by_date.get(state.date),
                target_equity_weight=target_equity_weight,
                actual_equity_weight=actual_equity_weight,
                action=action,
            )
        )

    return preview


def build_simulated_rebalance_trades(
    daily_states: list[DailyPortfolioState],
    target_equity_weight: float = 0.9,
    tolerance: float = 0.05,
) -> list[SimulatedTrade]:
    trades: list[SimulatedTrade] = []

    for state in daily_states:
        if not state.positions or state.total_portfolio_value <= 0:
            continue

        actual_equity_weight = state.total_market_value / state.total_portfolio_value
        cash_gap = target_equity_weight * state.total_portfolio_value - state.total_market_value
        largest_position = max(state.positions, key=lambda position: position.market_value or 0)
        if largest_position.market_price is None or largest_position.market_price == 0:
            continue
        price = largest_position.market_price

        if actual_equity_weight < target_equity_weight - tolerance:
            estimated_cash_impact = min(cash_gap, state.cash[next(iter(state.cash))]) if state.cash else cash_gap
            quantity = round((estimated_cash_impact / price), 4) if estimated_cash_impact > 0 else 0.0
            if quantity > 0:
                trades.append(SimulatedTrade(date=state.date, action="BUY", symbol=largest_position.symbol, quantity=quantity, reference_price=price, estimated_cash_impact=round(-estimated_cash_impact, 2)))
        elif actual_equity_weight > target_equity_weight + tolerance:
            estimated_cash_impact = abs(cash_gap)
            quantity = round((estimated_cash_impact / price), 4) if estimated_cash_impact > 0 else 0.0
            if quantity > 0:
                trades.append(SimulatedTrade(date=state.date, action="SELL", symbol=largest_position.symbol, quantity=quantity, reference_price=price, estimated_cash_impact=round(estimated_cash_impact, 2)))

    return trades
