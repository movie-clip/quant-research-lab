from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.core.constants import SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT
from app.domain.ledger import snapshot_to_ledger
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition


@dataclass
class PortfolioStateEngine:
    snapshot: ImportedPortfolioSnapshot
    base_currency: str
    fx_history: dict[str, float]
    # US-27.8 (audit F9): currencies for which a base-currency conversion was
    # required but no rate was found in fx_history during the last
    # build_daily_states run. The value is carried UNCONVERTED in that case
    # (the only honest number available) and this set lets callers disclose
    # the degradation instead of silently claiming a converted valuation.
    fx_fallback_currencies: set[str] = field(default_factory=set)

    def build_daily_states(
        self,
        price_histories: dict[str, list[dict]],
        valuation_dates: list[str],
        *,
        apply_terminal_reconciliation: bool = True,
    ) -> list[DailyPortfolioState]:
        self.fx_fallback_currencies = set()
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
            row_lookup = {row["date"]: float(row["price"]) for row in ordered_rows}
            # Carry may be seeded by a REAL quote dated before the valuation
            # window (that is still a carry-forward of an observed price).
            # A price is never fabricated BEFORE a symbol's first quote —
            # the previous implementation back-filled the first fetched quote
            # flat across the leading dates (US-27.7 / audit F8).
            pre_window_rows = [row for row in ordered_rows if row["date"] < valuation_dates[0]]
            last_price: float | None = float(pre_window_rows[-1]["price"]) if pre_window_rows else None
            for valuation_date in valuation_dates:
                if valuation_date in row_lookup:
                    last_price = row_lookup[valuation_date]
                if last_price is not None:
                    symbol_history[valuation_date] = last_price
            history_by_symbol[symbol] = symbol_history

        # US-27.7 coverage rule (broker path): the replay starts at the latest
        # first-covered date across MATERIAL opening positions, so an opening
        # holding whose price history begins mid-window can never enter as a
        # fabricated flat segment or a mid-window value jump. Symbols with no
        # fetchable history at all keep the statement close-price anchor below
        # (broker-truth-adjacent, not market fabrication) and do not truncate.
        valuation_dates = self._effective_valuation_dates(valuation_dates, opening_positions, history_by_symbol)
        if not valuation_dates:
            return []

        instrument_currency = {position.symbol: position.currency for position in self.snapshot.positions}

        def to_base_currency(value: float, currency: str, day_str: str) -> float:
            if currency == self.base_currency:
                return value
            fx_key = f"{currency}{self.base_currency}:{day_str}"
            fx_rate = self.fx_history.get(fx_key)
            if fx_rate is not None:
                return value * fx_rate
            # No rate: carry the raw value (the only honest number we hold)
            # and RECORD the degradation — never a silent 1:1 conversion claim.
            self.fx_fallback_currencies.add(currency)
            return value

        def price_for(symbol: str, day_str: str) -> float | None:
            symbol_history = history_by_symbol.get(symbol)
            if symbol_history:
                # Covered symbol: None before its first quote — never the
                # statement close price (that would fabricate a market price
                # for a date the market never produced one; US-27.7).
                return symbol_history.get(day_str)
            # No fetchable history at all: the statement close price is the
            # last broker-truth-adjacent anchor we have — kept (documented in
            # the methodology coverage rule) so unpriceable instruments do
            # not silently vanish from the replayed NAV.
            return fallback_prices.get(symbol)

        first_date = valuation_dates[0]
        opening_positions_value = 0.0
        for symbol, opening_quantity in opening_positions.items():
            opening_price = price_for(symbol, first_date)
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
                price = price_for(symbol, day_str)
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

    def _effective_valuation_dates(
        self,
        valuation_dates: list[str],
        opening_positions: dict[str, float],
        history_by_symbol: dict[str, dict[str, float]],
    ) -> list[str]:
        """US-27.7 coverage rule for the broker-replay path.

        The replay window starts at the latest first-covered date across
        MATERIAL opening positions (weight ≥ the shared de-minimis constant,
        by current snapshot market value). Opening symbols with no fetchable
        history do not truncate (they keep the statement-price anchor);
        sub-de-minimis late-coverage symbols do not truncate either — their
        pre-coverage days simply carry no market price (bounded by the
        de-minimis weight, never a fabricated flat segment).
        """
        total_value = sum(float(position.market_value) for position in self.snapshot.positions)
        weight_by_symbol = {
            position.symbol: (float(position.market_value) / total_value if total_value > 0 else 1.0)
            for position in self.snapshot.positions
        }

        first_covered: dict[str, str] = {}
        for symbol, quantity in opening_positions.items():
            if abs(quantity) < 1e-9:
                continue
            symbol_history = history_by_symbol.get(symbol)
            if not symbol_history:
                continue
            first_covered[symbol] = min(symbol_history)

        material = {
            symbol: first_date
            for symbol, first_date in first_covered.items()
            if weight_by_symbol.get(symbol, 1.0) >= SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT
        }
        reference = material or first_covered
        if not reference:
            return valuation_dates
        effective_start = max(reference.values())
        return [valuation_date for valuation_date in valuation_dates if valuation_date >= effective_start]

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
