from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from app.domain.ledger import snapshot_to_ledger
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition


@dataclass
class PortfolioStateEngine:
    snapshot: ImportedPortfolioSnapshot
    base_currency: str
    fx_history: dict[str, float]

    def build_daily_states(
        self,
        price_histories: dict[str, list[dict]],
        valuation_dates: list[str],
        *,
        apply_terminal_reconciliation: bool = True,
    ) -> list[DailyPortfolioState]:
        if not valuation_dates:
            return []

        canonical_ledger = snapshot_to_ledger(self.snapshot)
        trade_entries = sorted(
            canonical_ledger,
            key=lambda item: (item.date, item.symbol or "", item.entry_type),
        )

        ending_positions = {position.symbol: position.quantity for position in self.snapshot.positions}
        buy_totals: defaultdict[str, float] = defaultdict(float)
        sell_totals: defaultdict[str, float] = defaultdict(float)
        for entry in trade_entries:
            if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
                buy_totals[entry.symbol] += entry.quantity
            elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
                sell_totals[entry.symbol] += entry.quantity

        opening_positions: defaultdict[str, float] = defaultdict(float)
        initial_portfolio_value = self.snapshot.statement_totals.starting_nav if self.snapshot.statement_totals and self.snapshot.statement_totals.starting_nav is not None else 0.0
        if len(self.snapshot.statements) > 1 and abs(initial_portfolio_value) <= 1e-9:
            opening_positions = defaultdict(float)
        else:
            for symbol in set(ending_positions) | set(buy_totals) | set(sell_totals):
                opening_positions[symbol] = ending_positions.get(symbol, 0.0) + sell_totals[symbol] - buy_totals[symbol]

        history_by_symbol: dict[str, dict[str, float]] = {}
        fallback_prices = {position.symbol: position.close_price for position in self.snapshot.positions}
        for symbol, rows in price_histories.items():
            ordered_rows = sorted(rows, key=lambda row: row["date"])
            symbol_history: dict[str, float] = {}
            last_price: float | None = None
            row_lookup = {row["date"]: float(row["price"]) for row in ordered_rows}
            first_price = float(ordered_rows[0]["price"]) if ordered_rows else fallback_prices.get(symbol)
            for valuation_date in valuation_dates:
                if valuation_date in row_lookup:
                    last_price = row_lookup[valuation_date]
                if last_price is not None:
                    symbol_history[valuation_date] = last_price
                elif first_price is not None:
                    symbol_history[valuation_date] = first_price
            history_by_symbol[symbol] = symbol_history

        instrument_currency = {position.symbol: position.currency for position in self.snapshot.positions}

        def to_base_currency(value: float, currency: str, day_str: str) -> float:
            if currency == self.base_currency:
                return value
            fx_key = f"{currency}{self.base_currency}:{day_str}"
            fx_rate = self.fx_history.get(fx_key)
            if fx_rate is not None:
                return value * fx_rate
            return value

        first_date = valuation_dates[0]
        opening_positions_value = 0.0
        for symbol, opening_quantity in opening_positions.items():
            opening_price = history_by_symbol.get(symbol, {}).get(first_date, fallback_prices.get(symbol))
            currency = instrument_currency.get(symbol, self.base_currency)
            if opening_price is not None:
                opening_positions_value += to_base_currency(opening_quantity * opening_price, currency, first_date)

        base_cash = initial_portfolio_value - opening_positions_value

        states: list[DailyPortfolioState] = []
        entry_index = 0
        current_cash = {self.base_currency: round(base_cash, 2)}
        running_positions = defaultdict(float, opening_positions)

        for day_str in valuation_dates:
            day = date.fromisoformat(day_str)
            external_cash_flow = 0.0
            while entry_index < len(trade_entries) and trade_entries[entry_index].date <= day:
                entry = trade_entries[entry_index]
                amount = to_base_currency(entry.cash_effect, entry.cash_currency, day_str)

                if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
                    running_positions[entry.symbol] += entry.quantity
                    current_cash[self.base_currency] += amount
                elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
                    running_positions[entry.symbol] -= entry.quantity
                    current_cash[self.base_currency] += amount
                else:
                    current_cash[self.base_currency] += amount
                    if entry.entry_type in {"DEPOSIT", "WITHDRAWAL"}:
                        external_cash_flow += amount

                entry_index += 1

            state_positions: list[DailyStatePosition] = []
            total_market_value = 0.0
            for symbol in sorted(running_positions):
                quantity = running_positions.get(symbol, 0.0)
                if abs(quantity) < 1e-9:
                    continue
                currency = instrument_currency.get(symbol, self.base_currency)
                price = history_by_symbol.get(symbol, {}).get(day_str, fallback_prices.get(symbol))
                market_value = round(to_base_currency(quantity * price, currency, day_str), 2) if price is not None else None
                if market_value is not None:
                    total_market_value += market_value
                state_positions.append(
                    DailyStatePosition(
                        symbol=symbol,
                        quantity=round(quantity, 6),
                        market_price=price,
                        market_value=market_value,
                    )
                )

            total_portfolio_value = round(total_market_value + current_cash[self.base_currency], 2)
            states.append(
                DailyPortfolioState(
                    date=day_str,
                    cash={self.base_currency: round(current_cash[self.base_currency], 2)},
                    positions=state_positions,
                    total_market_value=round(total_market_value, 2),
                    total_portfolio_value=total_portfolio_value,
                    external_cash_flow=round(external_cash_flow, 2),
                )
            )

        if apply_terminal_reconciliation:
            self._reconcile_terminal_state_to_statement_totals(states)

        return states

    def _reconcile_terminal_state_to_statement_totals(self, states: list[DailyPortfolioState]) -> None:
        if not states or self.snapshot.statement_totals is None:
            return

        terminal_state = states[-1]
        expected_ending_nav = self.snapshot.statement_totals.ending_nav
        expected_cash_total = self.snapshot.statement_totals.cash_total

        if expected_cash_total is not None:
            terminal_state.cash[self.base_currency] = round(expected_cash_total, 2)

        if expected_ending_nav is not None:
            terminal_state.total_portfolio_value = round(expected_ending_nav, 2)
            if expected_cash_total is None:
                reconciled_cash = round(expected_ending_nav - terminal_state.total_market_value, 2)
                terminal_state.cash[self.base_currency] = reconciled_cash
