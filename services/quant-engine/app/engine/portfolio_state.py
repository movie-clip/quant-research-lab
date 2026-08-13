from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from app.core.constants import (
    REPLAY_RECONCILIATION_TOLERANCE,
    REPLAY_SHARE_UNIT_DISCONTINUITY_RATIO,
    SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT,
)
from app.domain.ledger import snapshot_to_ledger
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition


@dataclass(frozen=True)
class CashAnchorDisclosure:
    """US-31.3 (Epic 31 F-2): how opening cash was derived, and whether to trust it.

    `base_cash = starting_nav − opening_positions_value` is only sound when both
    terms are dated the same day. When the statement NAV's as-of date differs
    from the replay window start, market movement between them is absorbed into
    cash as a plug — the anchor is `degraded`, never `verified`.
    """

    basis: str
    trust: str
    nav_as_of: str | None = None
    window_start: str | None = None
    residual: float | None = None


@dataclass(frozen=True)
class QuantityWithholding:
    """US-33.2 (Epic 33 F-1/F-2): a symbol whose reconstructed quantity is not trustworthy.

    The roll-back `opening = ending + Σ SELL − Σ BUY` presumes one share unit
    for the whole window. A split violates that by construction, and the result
    is a position size the broker never held (IB2026: 199 phantom LQQ units).
    The fabricated object is the QUANTITY, so the quantity is what is withheld —
    the symbol contributes no position line and no market value on any day, and
    this record says why.
    """

    symbol: str
    reason: str
    currency: str
    price_low: float
    price_high: float
    price_ratio: float
    withheld_opening_quantity: float


def detect_share_unit_discontinuities(
    trade_entries: list,
    opening_positions: dict[str, float],
    *,
    ratio_threshold: float = REPLAY_SHARE_UNIT_DISCONTINUITY_RATIO,
) -> dict[str, QuantityWithholding]:
    """Symbols whose own execution prices imply more than one share unit.

    Ratios are computed **within a currency** and the widest currency wins: a
    symbol traded in both EUR and USD must never be flagged by an FX difference
    it never experienced.

    This detects a discontinuity; it does not measure or repair one. Inferring
    the split ratio from the price jump and rewriting quantities would be
    fabricating broker truth from market data (Epic 33 non-goal), so the only
    output is evidence for withholding.
    """
    prices_by_symbol_currency: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    for entry in trade_entries:
        if entry.entry_type not in {"BUY", "SELL"}:
            continue
        if not entry.symbol or entry.price is None:
            continue
        price = float(entry.price)
        if price <= 0:
            continue
        prices_by_symbol_currency[(entry.symbol, entry.cash_currency)].append(price)

    widest: dict[str, QuantityWithholding] = {}
    for (symbol, currency), prices in prices_by_symbol_currency.items():
        low, high = min(prices), max(prices)
        ratio = high / low
        if ratio < ratio_threshold:
            continue
        incumbent = widest.get(symbol)
        if incumbent is not None and incumbent.price_ratio >= ratio:
            continue
        widest[symbol] = QuantityWithholding(
            symbol=symbol,
            reason="share_unit_discontinuity",
            currency=currency,
            price_low=low,
            price_high=high,
            price_ratio=ratio,
            withheld_opening_quantity=float(opening_positions.get(symbol, 0.0)),
        )
    return widest


def _trade_quantity_totals(
    trade_entries: list,
) -> tuple[defaultdict[str, float], defaultdict[str, float]]:
    """Per-symbol BUY / SELL quantity totals from a canonical ledger.

    Shared by `replay_symbol_universe` and `build_daily_states` so the set of
    symbols we FETCH prices for can never drift from the set the replay
    actually values (US-31.2 / Epic 31 F-1 — the two were derived
    independently, which is exactly how they diverged).
    """
    buy_totals: defaultdict[str, float] = defaultdict(float)
    sell_totals: defaultdict[str, float] = defaultdict(float)
    for entry in trade_entries:
        if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
            buy_totals[entry.symbol] += entry.quantity
        elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
            sell_totals[entry.symbol] += entry.quantity
    return buy_totals, sell_totals


def replay_symbol_universe(snapshot: ImportedPortfolioSnapshot) -> list[str]:
    """Every symbol the ledger replay may need a price for (US-31.2, F-1).

    The replay rolls ending positions BACK through BUY/SELL to reconstruct
    opening positions, then walks them forward again — so it values three
    populations, not one:

      1. symbols still held today (the snapshot's positions),
      2. symbols held at the window open and since sold,
      3. symbols bought AND sold entirely inside the window (they appear in
         neither the opening nor the ending set, but are held on interior days).

    Callers previously fetched only (1) — `[p.symbol for p in
    snapshot.positions]` — leaving (2) and (3) with no price rows at all, so
    they silently contributed 0 to market value (Epic 31 F-1: 27 of 38 opening
    positions unpriced on the IB2026 day one).

    Returns a sorted list so the fetch order — and therefore the recorded
    golden fixture — is deterministic.
    """
    buy_totals, sell_totals = _trade_quantity_totals(snapshot_to_ledger(snapshot))
    return sorted(
        {position.symbol for position in snapshot.positions if position.symbol}
        | {symbol for symbol in buy_totals if symbol}
        | {symbol for symbol in sell_totals if symbol}
    )


@dataclass
class PortfolioStateEngine:
    snapshot: ImportedPortfolioSnapshot
    base_currency: str
    fx_history: dict[str, float]
    # US-31.5 (Epic 31 F-4): fund (quote) currency per symbol — the currency the
    # resolved market line is actually quoted in, which is NOT the broker's
    # listing `position.currency` (e.g. DEFS is listed EUR but DEFS.L quotes
    # USD). Sourced from the InstrumentRegistry by the caller. Used for
    # MARKET-priced values; statement-anchored values keep `position.currency`
    # (the anchor is the statement close, in the listing currency). A symbol
    # absent from this map falls back to `position.currency` — never a silent
    # 1:1 base assumption.
    symbol_fund_currencies: dict[str, str] = field(default_factory=dict)
    # US-27.8 (audit F9): currencies for which a base-currency conversion was
    # required but no rate was found in fx_history during the last
    # build_daily_states run. The value is carried UNCONVERTED in that case
    # (the only honest number available) and this set lets callers disclose
    # the degradation instead of silently claiming a converted valuation.
    fx_fallback_currencies: set[str] = field(default_factory=set)
    # US-30.2 (audit F-3): held symbols that had NO fetchable in-window price
    # history during the last build_daily_states run and were therefore
    # valued flat at the statement close price (the documented US-27.7
    # broker-path anchor). Zero return contribution — callers must disclose,
    # never let the flat segment pass as market data.
    statement_anchored_symbols: set[str] = field(default_factory=set)
    # US-31.2 (Epic 31 F-1): symbols the replay held on some day of the window
    # for which there was NO fetchable price history AND no statement close
    # price to anchor on — they contributed 0 to that day's market value. The
    # common case is a since-sold symbol: it is absent from the current
    # snapshot, so it is absent from `fallback_prices` too. Recorded so callers
    # disclose the gap instead of publishing a silently understated NAV.
    unpriced_replay_symbols: set[str] = field(default_factory=set)
    # US-24.10: symbols with NO fetchable price history and NO statement close
    # price that were nonetheless valued, on days at or after their first
    # broker trade, at that trade's execution price carried forward. The third
    # valuation tier (below market history and the statement close): broker
    # truth, but FLAT between trades — zero market movement across the carried
    # segment. Callers must disclose it; it is a weaker basis than a statement
    # close (which is at least a period-end mark) and a stronger one than the
    # $0 valuation it replaces. US-33.3 (Epic 33 F-3): exclusivity is per
    # (symbol, DAY) — `price_for` picks one tier per day — while this set is a
    # union over the window, so a symbol held before its first trade is
    # legitimately named here AND in `unpriced_replay_symbols`.
    trade_price_anchored_symbols: set[str] = field(default_factory=set)
    # US-31.3 (Epic 31 F-2): provenance + trust of the opening cash anchor from
    # the last build_daily_states run — basis, the NAV's as-of date, the replay
    # window start, the residual vs the statement-implied opening cash, and the
    # resulting trust level. `None` until a run has computed it.
    cash_anchor: CashAnchorDisclosure | None = None
    # US-33.2 (Epic 33 F-1/F-2): symbols whose reconstructed quantity was
    # WITHHELD because their own ledger prices imply a share-unit change (a
    # split). They contribute no position line and no market value on any day —
    # never a phantom size valued at a stale pre-split price. Distinct from
    # `unpriced_replay_symbols` (quantity trusted, no price available): here it
    # is the QUANTITY that is untrustworthy, so a flagged symbol appears in this
    # list and in none of the three valuation tiers.
    quantity_withheld: dict[str, QuantityWithholding] = field(default_factory=dict)

    def build_daily_states(
        self,
        price_histories: dict[str, list[dict]],
        valuation_dates: list[str],
        *,
        apply_terminal_reconciliation: bool = True,
    ) -> list[DailyPortfolioState]:
        self.fx_fallback_currencies = set()
        self.statement_anchored_symbols = set()
        self.unpriced_replay_symbols = set()
        self.trade_price_anchored_symbols = set()
        self.quantity_withheld = {}
        if not valuation_dates:
            return []

        canonical_ledger = snapshot_to_ledger(self.snapshot)
        trade_entries = sorted(
            canonical_ledger,
            key=lambda item: (item.date, item.symbol or "", item.entry_type),
        )

        ending_positions = {position.symbol: position.quantity for position in self.snapshot.positions}
        buy_totals, sell_totals = _trade_quantity_totals(trade_entries)

        opening_positions: defaultdict[str, float] = defaultdict(float)
        initial_portfolio_value = self.snapshot.statement_totals.starting_nav if self.snapshot.statement_totals and self.snapshot.statement_totals.starting_nav is not None else 0.0
        if len(self.snapshot.statements) > 1 and abs(initial_portfolio_value) <= 1e-9:
            opening_positions = defaultdict(float)
        else:
            for symbol in set(ending_positions) | set(buy_totals) | set(sell_totals):
                opening_positions[symbol] = ending_positions.get(symbol, 0.0) + sell_totals[symbol] - buy_totals[symbol]

        # US-33.2 (Epic 33 F-1): the roll-back above is only valid while one
        # share unit holds for the whole window. Where the symbol's own prices
        # say otherwise, drop its reconstructed quantity entirely — it is
        # fabricated — and carry the evidence for the disclosure. Detected
        # BEFORE any valuation so no tier, no cash anchor and no state can be
        # built on the phantom.
        self.quantity_withheld = detect_share_unit_discontinuities(trade_entries, opening_positions)
        for withheld_symbol in self.quantity_withheld:
            opening_positions.pop(withheld_symbol, None)

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

        position_currency = {position.symbol: position.currency for position in self.snapshot.positions}

        # US-24.10: per-symbol observed broker execution prices, ascending by
        # date. The third and last valuation tier: a symbol with no market
        # history AND no statement close price is still worth what the broker
        # last traded it at. Derived from the SAME canonical ledger scan that
        # drives quantities, so the prices can never describe a different set of
        # trades than the replay applies.
        trade_prices: defaultdict[str, list[tuple[str, float, str]]] = defaultdict(list)
        for entry in trade_entries:
            if entry.entry_type in {"BUY", "SELL"} and entry.symbol and entry.price is not None:
                trade_prices[entry.symbol].append((entry.date.isoformat(), float(entry.price), entry.cash_currency))

        def trade_anchor(symbol: str, day_str: str) -> tuple[float, str] | None:
            """Most recent broker execution price at or before `day_str`.

            **Forward-carry only.** Before a symbol's first observed trade this
            returns None — reaching backwards would fabricate a price for a date
            the broker never produced one, the US-27.7 rule that also forbids
            back-filling market history.

            **US-33.2 (Epic 33 F-2) — discontinuity guard.** The anchor assumes
            the last observed trade price stays a valid basis until the next
            trade, which a split violates by construction: on IB2026 it carried
            the pre-split EUR 1,457.78 across a ~200:1 split and valued a
            phantom 199-unit position at $336,543. For a symbol whose prices
            imply a share-unit change there is no sound carried price at any
            date, so the anchor declines to produce one. Enforced HERE, at the
            anchor itself, not only at the quantity path — any future caller is
            guarded by construction.
            """
            if symbol in self.quantity_withheld:
                return None
            observed = trade_prices.get(symbol)
            if not observed:
                return None
            anchor: tuple[float, str] | None = None
            for trade_date, price, currency in observed:
                if trade_date > day_str:
                    break
                anchor = (price, currency)
            return anchor

        def valuation_currency(symbol: str, day_str: str) -> str:
            # US-31.5 (Epic 31 F-4): a MARKET-priced value is quoted in the
            # symbol's FUND currency (the resolved line's quote currency, from
            # the registry) — NOT the broker's listing `position.currency`
            # (e.g. DEFS is listed EUR but DEFS.L quotes USD). A STATEMENT-
            # anchored value (no fetchable history) is the statement close,
            # which IS in the listing currency. Falls back to position currency
            # when the fund currency is unknown, then to base — never a silent
            # 1:1 assumption for a known non-base currency.
            # US-24.10: a TRADE-anchored value is quoted in the currency the
            # trade settled in — mirrors `price_for`'s precedence exactly so the
            # value and its currency can never come from different tiers.
            if history_by_symbol.get(symbol):
                return self.symbol_fund_currencies.get(symbol) or position_currency.get(symbol, self.base_currency)
            if fallback_prices.get(symbol) is not None:
                return position_currency.get(symbol, self.base_currency)
            anchored_trade = trade_anchor(symbol, day_str)
            if anchored_trade is not None:
                return anchored_trade[1]
            return position_currency.get(symbol, self.base_currency)

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
            # US-33.2: a withheld symbol is valued by NO tier. Returning None
            # here without recording it as `unpriced` keeps the two states
            # distinct — `unpriced` means "quantity trusted, price missing",
            # this means "the quantity itself is not publishable".
            if symbol in self.quantity_withheld:
                return None
            symbol_history = history_by_symbol.get(symbol)
            if symbol_history:
                # Covered symbol: None before its first quote — never the
                # statement close price (that would fabricate a market price
                # for a date the market never produced one; US-27.7).
                return symbol_history.get(day_str)
            # No fetchable history at all: the statement close price is the
            # last broker-truth-adjacent anchor we have — kept (documented in
            # the methodology coverage rule) so unpriceable instruments do
            # not silently vanish from the replayed NAV. Recorded so callers
            # can disclose the flat segment (US-30.2 / audit F-3).
            anchored = fallback_prices.get(symbol)
            if anchored is not None:
                self.statement_anchored_symbols.add(symbol)
                return anchored
            # US-24.10: neither market history nor a statement close — but the
            # broker traded it, and an execution price for the identical
            # instrument is an observed price. Carried FORWARD from that trade
            # (flat between trades, disclosed as such) so a round-trip position
            # stops being worth $0 while held, which made its BUY/SELL move cash
            # with no offsetting market value and let the TWR publish the step
            # as performance (IB2026: −7.90% / +9.61%).
            anchored_trade = trade_anchor(symbol, day_str)
            if anchored_trade is not None:
                self.trade_price_anchored_symbols.add(symbol)
                return anchored_trade[0]
            return None

        def is_valued(symbol: str, day_str: str) -> bool:
            """Does this symbol contribute to `total_market_value` on this day?

            The side-effect-free predicate behind `price_for` — same precedence,
            no disclosure mutation.
            """
            if symbol in self.quantity_withheld:
                return False
            symbol_history = history_by_symbol.get(symbol)
            if symbol_history:
                return symbol_history.get(day_str) is not None
            if fallback_prices.get(symbol) is not None:
                return True
            # US-24.10: a trade-anchored symbol IS in market value from its
            # first trade onward.
            return trade_anchor(symbol, day_str) is not None

        first_date = valuation_dates[0]
        opening_positions_value = 0.0
        for symbol, opening_quantity in opening_positions.items():
            if abs(opening_quantity) < 1e-9:
                continue
            opening_price = price_for(symbol, first_date)
            currency = valuation_currency(symbol, first_date)
            if opening_price is not None:
                opening_positions_value += to_base_currency(opening_quantity * opening_price, currency, first_date)
            else:
                # Unvaluable opening position — it contributes 0 to
                # `opening_positions_value`, which the cash anchor below then
                # absorbs as a plug (Epic 31 F-2, fixed in US-31.3). Disclose
                # the input gap here (US-31.2 / F-1).
                self.unpriced_replay_symbols.add(symbol)

        if self.snapshot.statement_totals is not None and self.snapshot.statement_totals.starting_nav is not None:
            base_cash = initial_portfolio_value - opening_positions_value
            self.cash_anchor = self._classify_cash_anchor(
                base_cash=base_cash,
                window_start=first_date,
                to_base_currency=to_base_currency,
            )
        else:
            # US-30.1 (audit F-1): without a statement starting NAV the old
            # `0 − opening_positions_value` anchor fabricated a large negative
            # cash balance (request-path snapshots carry no statement_totals),
            # collapsing day-one portfolio value to ~0 and exploding every
            # return computed against it. The snapshot's own cash balances are
            # the honest anchor.
            base_cash = sum(
                to_base_currency(balance.ending_cash, balance.currency, first_date)
                for balance in self.snapshot.cash_balances
                if balance.ending_cash is not None
            )
            self.cash_anchor = CashAnchorDisclosure(
                basis="snapshot_cash_balances",
                trust="verified",
                window_start=first_date,
                residual=0.0,
            )

        states: list[DailyPortfolioState] = []
        entry_index = 0
        current_cash = {self.base_currency: round(base_cash, 2)}
        running_positions = defaultdict(float, opening_positions)
        # US-24.9/US-24.10: symbols that contributed to the PREVIOUS day's
        # market value — one half of the trade-leg test below.
        previous_priced_symbols: set[str] = set()

        for day_str in valuation_dates:
            day = date.fromisoformat(day_str)
            external_cash_flow = 0.0
            # US-24.9: per-symbol net cash moved by this day's trades, each term
            # FX-converted first (never the raw currency-mixed `cash_effect` —
            # the US-31.3 trap). Which of these become `trade_flow` is decided
            # AFTER valuation, once the day's actual market value is known.
            day_trade_amounts: defaultdict[str, float] = defaultdict(float)
            # US-33.2: cash moved by trades in a WITHHELD symbol. Its position is
            # in no market value, so this cash has nothing behind it and the
            # day's return is withheld rather than published (see
            # `DailyPortfolioState.return_is_publishable`).
            unbacked_cash_flow = 0.0
            while entry_index < len(trade_entries) and trade_entries[entry_index].date <= day:
                entry = trade_entries[entry_index]
                amount = to_base_currency(entry.cash_effect, entry.cash_currency, day_str)

                # US-33.2: for a withheld symbol the CASH still moves — the
                # broker really paid and received those amounts, and that is
                # broker truth the unit ambiguity does not touch. Only the
                # QUANTITY is suppressed, so the symbol enters no state and no
                # market value. Its legs stay in `day_trade_amounts` and are
                # filtered out by the US-24.9 trade-leg gate below (the symbol
                # is priced on no day), so no return is fabricated from them.
                withheld_quantity = entry.symbol in self.quantity_withheld
                if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
                    if not withheld_quantity:
                        running_positions[entry.symbol] += entry.quantity
                    else:
                        unbacked_cash_flow += amount
                    current_cash[self.base_currency] += amount
                    day_trade_amounts[entry.symbol] += amount
                elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
                    if not withheld_quantity:
                        running_positions[entry.symbol] -= entry.quantity
                    else:
                        unbacked_cash_flow += amount
                    current_cash[self.base_currency] += amount
                    day_trade_amounts[entry.symbol] += amount
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
                currency = valuation_currency(symbol, day_str)
                price = price_for(symbol, day_str)
                if price is None:
                    # Held on this day but unvaluable (no quote yet, or no
                    # history and no statement anchor) — it contributes 0 to
                    # total_market_value below. Disclose rather than publish a
                    # silently understated NAV (US-31.2 / Epic 31 F-1).
                    self.unpriced_replay_symbols.add(symbol)
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

            # US-24.9 (rule corrected by US-24.10): `trade_flow` may only cancel
            # a trade leg that ACTUALLY crossed the market-value boundary. A
            # symbol's trade counts when it is priced in today's market value
            # (a BUY landed) or was priced in the previous day's (a SELL left).
            # When it is in NEITHER the trade is invisible to the MV series and
            # counting it would fabricate a return. Three real cases this
            # excludes, all reproduced on IB2026:
            #   - trading a symbol with no obtainable price at all
            #     (2026-04-27, the unpriced IUFS/IUHC sale: +9.43%);
            #   - selling a symbol first observed by that very sale (it was
            #     never in yesterday's market value);
            #   - a same-day round trip in a new symbol — bought and fully sold
            #     before any close, so it is in no day's market value at all
            #     (2026-06-11 IITU: −3.45% vs an expected −0.36%).
            # Deciding it here, from the built state rather than from a
            # predicate guessing at it, is what makes all three fall out of one
            # rule instead of three special cases.
            current_priced_symbols = {
                item.symbol for item in state_positions if item.market_value is not None
            }
            trade_flow = -sum(
                amount
                for symbol, amount in day_trade_amounts.items()
                if symbol in current_priced_symbols or symbol in previous_priced_symbols
            )

            total_portfolio_value = round(total_market_value + current_cash[self.base_currency], 2)
            previous_priced_symbols = current_priced_symbols
            states.append(
                DailyPortfolioState(
                    date=day_str,
                    cash={self.base_currency: round(current_cash[self.base_currency], 2)},
                    positions=state_positions,
                    total_market_value=round(total_market_value, 2),
                    total_portfolio_value=total_portfolio_value,
                    external_cash_flow=round(external_cash_flow, 2),
                    trade_flow=round(trade_flow, 2),
                    unbacked_cash_flow=round(unbacked_cash_flow, 2),
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

        US-31.2 (Epic 31 F-1): materiality is DEFINED against current snapshot
        weight, so a reconstructed since-sold symbol has no weight to evaluate.
        Such symbols are excluded from the truncation reference set rather than
        scoring the `.get(symbol, 1.0)` maximum default — otherwise any one of
        them whose history happens to begin mid-window would truncate (or
        wholly eliminate) the replay window for every other holding. This was
        latent until US-31.2 started fetching their history: with no rows they
        never reached `first_covered`. Their coverage gap is surfaced through
        `unpriced_replay_symbols` instead of silently reshaping the window.
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
            # Only symbols the current snapshot can weight participate in the
            # truncation decision (US-31.2 — see the docstring).
            if symbol not in weight_by_symbol:
                continue
            first_covered[symbol] = min(symbol_history)

        material = {
            symbol: first_date
            for symbol, first_date in first_covered.items()
            if weight_by_symbol[symbol] >= SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT
        }
        reference = material or first_covered
        if not reference:
            return valuation_dates
        effective_start = max(reference.values())
        return [valuation_date for valuation_date in valuation_dates if valuation_date >= effective_start]

    def _statement_period_start(self) -> str | None:
        """ISO start date of the statement period, if parseable.

        `statement_period` is normalized to "YYYY-MM-DD - YYYY-MM-DD" by the CSV
        importer (US-28.1); legacy PDF formats may not parse, in which case the
        anchor's as-of date is unknown and it cannot claim `verified`.
        """
        period = self.snapshot.statement.statement_period
        if not period:
            return None
        head = period.split("-")[0:3]
        candidate = "-".join(part.strip() for part in head)[:10]
        try:
            date.fromisoformat(candidate)
        except ValueError:
            return None
        return candidate

    def _statement_implied_opening_cash(self, to_base_currency) -> float | None:
        """Statement-implied opening cash = ending cash − net window flow.

        The net flow MUST be FX-converted per entry: the raw sum of
        `cash_effect` is currency-mixed (on IB2026: EUR −10,317.85 + GBP
        −2,210.55 + USD 12,257.17 = −271.23 "dollars", which is meaningless).
        Converted it is −2,459.29, giving an implied opening cash of 4,452.94
        rather than the wrong 2,264.88. US-31.3 AC3 — do not reintroduce the
        raw sum here.
        """
        totals = self.snapshot.statement_totals
        if totals is None or totals.cash_total is None:
            return None
        net_flow = 0.0
        for entry in snapshot_to_ledger(self.snapshot):
            if entry.cash_effect is None:
                continue
            net_flow += to_base_currency(entry.cash_effect, entry.cash_currency, entry.date.isoformat())
        return totals.cash_total - net_flow

    def _classify_cash_anchor(self, *, base_cash: float, window_start: str, to_base_currency) -> CashAnchorDisclosure:
        """US-31.3 (Epic 31 F-2): trust of `starting_nav − opening_positions_value`.

        The anchor is only sound when the NAV's as-of date equals the date the
        opening positions are valued at. When they differ, market movement
        between the two dates is absorbed into cash as a plug, so the anchor is
        `degraded` — it is still the best number available (and is carried), but
        it is never presented as `verified`.
        """
        nav_as_of = self._statement_period_start()
        implied = self._statement_implied_opening_cash(to_base_currency)
        residual = round(base_cash - implied, 2) if implied is not None else None

        dates_align = nav_as_of is not None and nav_as_of == window_start
        within_tolerance = residual is not None and abs(residual) <= REPLAY_RECONCILIATION_TOLERANCE

        if dates_align and within_tolerance:
            basis, trust = "statement_nav_at_window_start", "verified"
        elif not dates_align:
            basis, trust = "statement_nav_date_mismatch", "degraded"
        else:
            # Dates align but the cash still does not reconcile — the anchor is
            # absorbing something else; degrade rather than claim verified.
            basis, trust = "statement_nav_at_window_start", "degraded"

        return CashAnchorDisclosure(
            basis=basis,
            trust=trust,
            nav_as_of=nav_as_of,
            window_start=window_start,
            residual=residual,
        )

    def _reconcile_terminal_state_to_statement_totals(self, states: list[DailyPortfolioState]) -> None:
        if not states or self.snapshot.statement_totals is None:
            return

        terminal_state = states[-1]
        expected_ending_nav = self.snapshot.statement_totals.ending_nav
        expected_cash_total = self.snapshot.statement_totals.cash_total

        if expected_cash_total is not None:
            terminal_state.cash[self.base_currency] = round(expected_cash_total, 2)

        if expected_ending_nav is not None:
            # US-31.3 (Epic 31 F-3): record the signed amount this correction
            # moves the terminal value by. It is an ACCOUNTING adjustment, not a
            # market move — downstream return builders withhold the day's return
            # rather than publishing it as performance (guardrail #3).
            adjustment = round(expected_ending_nav - terminal_state.total_portfolio_value, 2)
            terminal_state.reconciliation_adjustment = adjustment
            terminal_state.total_portfolio_value = round(expected_ending_nav, 2)
            if expected_cash_total is None:
                reconciled_cash = round(expected_ending_nav - terminal_state.total_market_value, 2)
                terminal_state.cash[self.base_currency] = reconciled_cash
