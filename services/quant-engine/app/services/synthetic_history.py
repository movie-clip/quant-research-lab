"""Synthetic History truth-class reconstruction.

Owns the daily portfolio-state series built from current holdings × historical
prices, under the US-27.7 coverage rule
(``docs/finance/financial-methodology.md`` §"Synthetic History Coverage Rule").

Extracted verbatim from ``diagnostics_engine.py`` in US-43.1 so the seam is
importable as a public function and testable on its own. Any engine needing
synthetic history imports from here.
"""

from app.core.constants import SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import (
    DailyPortfolioState,
    DailyStatePosition,
    SyntheticHistoryCoverage,
)


def build_synthetic_snapshot_history_states(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
) -> list[DailyPortfolioState]:
    states, _coverage = build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot,
        price_histories=price_histories,
        valuation_dates=valuation_dates,
    )
    return states


def build_synthetic_snapshot_history_states_with_coverage(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
) -> tuple[list[DailyPortfolioState], SyntheticHistoryCoverage]:
    """Synthetic daily states (current holdings × historical prices) under the
    US-27.7 coverage rule — methodology §Synthetic history coverage rule.

    - A price is NEVER fabricated before a symbol's first in-window quote
      (the previous implementation back-filled the first quote flat, and
      flat-filled the statement close price for symbols with no history at
      all — fabricated zero returns that understated vol/VaR/drawdown).
    - The effective window starts at the latest first-quote across MATERIAL
      holdings (weight ≥ SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT); the limiting
      symbol is disclosed when this truncates the requested window.
    - Holdings with no in-window history, and sub-de-minimis holdings whose
      history starts after the effective start, are excluded and disclosed.
    - INTERIOR gaps (non-trading days, missing quotes after the first one)
      keep the carry-last-known-price convention: standard practice for
      aligning mixed calendars, disclosed in the methodology.
    """
    requested_start = valuation_dates[0] if valuation_dates else None
    if not valuation_dates or not snapshot.positions:
        return [], SyntheticHistoryCoverage(requested_start_date=requested_start)

    base_currency = snapshot.statement.base_currency or 'USD'
    total_cash = sum(float(balance.ending_cash or 0.0) for balance in snapshot.cash_balances)

    valuation_date_set = set(valuation_dates)
    in_window_quotes: dict[str, dict[str, float]] = {}
    first_quote_date: dict[str, str] = {}
    for symbol, rows in price_histories.items():
        quotes = {row['date']: float(row['price']) for row in rows if row['date'] in valuation_date_set}
        if not quotes:
            continue
        in_window_quotes[symbol] = quotes
        first_quote_date[symbol] = min(quotes)

    total_positions_value = sum(float(position.market_value) for position in snapshot.positions)

    def _weight(position) -> float:
        if total_positions_value <= 0:
            return 1.0  # degenerate snapshot: treat every holding as material
        return float(position.market_value) / total_positions_value

    excluded_symbols: list[str] = []
    covered_positions = []
    material_first_quotes: dict[str, str] = {}
    for position in snapshot.positions:
        first_quote = first_quote_date.get(position.symbol)
        if first_quote is None:
            if position.symbol not in excluded_symbols:
                excluded_symbols.append(position.symbol)  # no in-window history at all
            continue
        covered_positions.append(position)
        if _weight(position) >= SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT:
            material_first_quotes[position.symbol] = first_quote

    if not covered_positions:
        return [], SyntheticHistoryCoverage(
            requested_start_date=requested_start,
            excluded_symbols=excluded_symbols,
        )

    # Effective start: latest material first-quote. If no holding clears the
    # de-minimis bar (e.g. very many small positions), every covered holding
    # is treated as material so the window is still set by real coverage.
    reference_first_quotes = material_first_quotes or {
        position.symbol: first_quote_date[position.symbol] for position in covered_positions
    }
    effective_start = max(reference_first_quotes.values())
    limiting_symbol = None
    if effective_start > requested_start:
        limiting_symbol = max(reference_first_quotes, key=lambda sym: reference_first_quotes[sym])

    # Sub-de-minimis holdings whose coverage starts after the effective start
    # cannot be included without a mid-window fabricated entry — exclude them.
    included_positions = []
    for position in covered_positions:
        if first_quote_date[position.symbol] > effective_start:
            if position.symbol not in excluded_symbols:
                excluded_symbols.append(position.symbol)
            continue
        included_positions.append(position)

    effective_dates = [d for d in valuation_dates if d >= effective_start]

    # Carried price series over the effective window: the carry starts at the
    # symbol's first REAL quote (≤ effective_start for included symbols) and
    # bridges interior gaps only — never a back-fill.
    history_by_symbol: dict[str, dict[str, float]] = {}
    included_symbols = {position.symbol for position in included_positions}
    for symbol in included_symbols:
        quotes = in_window_quotes[symbol]
        symbol_history: dict[str, float] = {}
        last_price: float | None = None
        for valuation_date in valuation_dates:
            if valuation_date in quotes:
                last_price = quotes[valuation_date]
            if last_price is not None and valuation_date >= effective_start:
                symbol_history[valuation_date] = last_price
        history_by_symbol[symbol] = symbol_history

    synthetic_quantities: dict[str, float] = {}
    for position in included_positions:
        anchor_price = history_by_symbol.get(position.symbol, {}).get(effective_start)
        if anchor_price is None or anchor_price <= 0:
            if position.symbol not in excluded_symbols:
                excluded_symbols.append(position.symbol)
            continue
        synthetic_quantities[position.symbol] = float(position.market_value) / float(anchor_price)

    states: list[DailyPortfolioState] = []
    for valuation_date in effective_dates:
        state_positions: list[DailyStatePosition] = []
        total_market_value = 0.0
        for position in included_positions:
            quantity = synthetic_quantities.get(position.symbol)
            if quantity is None:
                continue
            price = history_by_symbol.get(position.symbol, {}).get(valuation_date)
            if price is None:
                continue
            market_value = round(quantity * float(price), 2)
            total_market_value += market_value
            state_positions.append(
                DailyStatePosition(
                    symbol=position.symbol,
                    quantity=round(quantity, 6),
                    market_price=float(price),
                    market_value=market_value,
                )
            )

        states.append(
            DailyPortfolioState(
                date=valuation_date,
                cash={base_currency: round(total_cash, 2)},
                positions=state_positions,
                total_market_value=round(total_market_value, 2),
                total_portfolio_value=round(total_market_value + total_cash, 2),
                external_cash_flow=0.0,
            )
        )

    return states, SyntheticHistoryCoverage(
        requested_start_date=requested_start,
        effective_start_date=effective_start,
        limiting_symbol=limiting_symbol,
        excluded_symbols=excluded_symbols,
    )
