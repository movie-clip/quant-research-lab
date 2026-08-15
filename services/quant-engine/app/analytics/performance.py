from app.engine.portfolio_state import PortfolioStateEngine
from app.analytics.risk import selected_history_price_map
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import DailyPortfolioState, EnrichedPosition, PerformancePoint, PerformanceSummary
from typing import Literal

from app.services.market_data import HistoryReturnBasisContract, classify_history_return_basis_contract

# US-34.2 (Epic 34 F-1): the portfolio path accepts one rung the benchmark path
# does not. `replay_derived` is a real measurement chained from the imported
# replay's own daily states — reconstructed inputs, so below
# `verified_total_return` and never a substitute for it. A benchmark is priced
# from market data and can never be replayed, which is why this widening is
# deliberately one-sided.
PortfolioReturnBasisContract = HistoryReturnBasisContract | Literal["replay_derived"]

# The bases on which a cumulative portfolio return chain may be PUBLISHED. Any
# other basis yields a fully null series rather than a fabricated one.
_PUBLISHING_PORTFOLIO_BASES: frozenset[str] = frozenset(
    {"verified_total_return", "replay_derived"}
)


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


def build_replay_currency_context(
    snapshot: ImportedPortfolioSnapshot,
    symbols: list[str],
    valuation_dates: list[str],
) -> tuple[dict[str, str], dict[str, float]]:
    """US-31.5 (Epic 31 F-4): the fund-currency map + statement-rate fx_history
    a ledger-replay caller must pass so market values convert correctly.

    - fund currency per symbol comes from the InstrumentRegistry (the resolved
      line's quote currency; e.g. DEFS.L → USD though DEFS is listed EUR);
    - fx_history is a static per-date table built from the statement's own
      implied `fx_rates` (US-28.1 broker truth), the same basis US-30.2 uses for
      the drift path. Empty when the statement carries no rates, so behaviour is
      unchanged for snapshots without them (values carried unconverted, US-27.8).
    """
    from app.instruments import InstrumentRegistry

    registry = InstrumentRegistry()
    fund_currencies: dict[str, str] = {}
    for symbol in symbols:
        instrument = registry.get_instrument(symbol)
        if instrument is not None and instrument.currency:
            fund_currencies[symbol] = instrument.currency

    rates = (snapshot.statement_totals.fx_rates if snapshot.statement_totals else None) or {}
    fx_history: dict[str, float] = {}
    for pair, rate in rates.items():
        if rate is None:
            continue
        for day in valuation_dates:
            fx_history[f"{pair}:{day}"] = rate
    return fund_currencies, fx_history


def build_daily_portfolio_states(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    fx_history: dict[str, float],
    symbol_fund_currencies: dict[str, str] | None = None,
) -> list[DailyPortfolioState]:
    states, _fx_fallback_currencies = build_daily_portfolio_states_with_fx_disclosure(
        snapshot=snapshot,
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        fx_history=fx_history,
        symbol_fund_currencies=symbol_fund_currencies,
    )
    return states


def build_daily_portfolio_states_with_fx_disclosure(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    fx_history: dict[str, float],
    symbol_fund_currencies: dict[str, str] | None = None,
) -> tuple[list[DailyPortfolioState], list[str]]:
    """Daily broker-replay states + the FX-fallback disclosure (US-27.8).

    The second element lists currencies that required base conversion but had
    no rate in fx_history — those values are carried unconverted and the
    consuming response must surface the degradation.
    """
    states, fx_fallback_currencies, _unpriced = build_daily_portfolio_states_with_replay_disclosure(
        snapshot=snapshot,
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        fx_history=fx_history,
        symbol_fund_currencies=symbol_fund_currencies,
    )
    return states, fx_fallback_currencies


def build_daily_portfolio_states_with_replay_disclosure(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    fx_history: dict[str, float],
    symbol_fund_currencies: dict[str, str] | None = None,
) -> tuple[list[DailyPortfolioState], list[str], list[str]]:
    """Daily broker-replay states + the FX-fallback (US-27.8) and unpriced-symbol
    (US-31.2 / Epic 31 F-1) disclosures.

    The third element lists symbols the replay held on some day of the window
    that could not be valued at all (no fetchable history, no statement close
    anchor) — they contributed 0, and the consuming response must surface that
    rather than publish an understated NAV.

    `symbol_fund_currencies` (US-31.5 / Epic 31 F-4) maps each symbol to the
    currency its market price is quoted in (the fund currency, from the
    registry) so market values convert correctly; omit it to keep values in the
    position currency (backward-compatible).
    """
    engine = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=snapshot.statement.base_currency or "USD",
        fx_history=fx_history,
        symbol_fund_currencies=symbol_fund_currencies or {},
    )
    states = engine.build_daily_states(price_histories=price_histories, valuation_dates=valuation_dates)
    return states, sorted(engine.fx_fallback_currencies), sorted(engine.unpriced_replay_symbols)


def build_replay_states_with_cash_anchor(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
    fx_history: dict[str, float],
    symbol_fund_currencies: dict[str, str] | None = None,
):
    """Replay states + all six disclosures: the US-27.8 FX fallback, the
    US-31.2 unpriced symbols, the US-31.3 cash anchor, the US-24.10
    trade-price-anchored tier, and the US-33.2 quantity withholdings.

    Returned as an explicit tuple (no shared mutable state) so it is safe under
    the parallel test suite and concurrent requests.
    """
    engine = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=snapshot.statement.base_currency or "USD",
        fx_history=fx_history,
        symbol_fund_currencies=symbol_fund_currencies or {},
    )
    states = engine.build_daily_states(price_histories=price_histories, valuation_dates=valuation_dates)
    return (
        states,
        sorted(engine.fx_fallback_currencies),
        sorted(engine.unpriced_replay_symbols),
        engine.cash_anchor,
        sorted(engine.trade_price_anchored_symbols),
        # US-33.2 (Epic 33 F-1/F-2): quantity withholdings, sorted by symbol so
        # the disclosure order is deterministic across runs.
        [engine.quantity_withheld[symbol] for symbol in sorted(engine.quantity_withheld)],
    )


def replay_disclosures(states: list[DailyPortfolioState]) -> tuple[list[str], str | None]:
    """US-31.3 (Epic 31 F-3): dates whose return was withheld, and why.

    A day carrying a material `reconciliation_adjustment` has no publishable
    return — the caller surfaces these so the gap is visible with a stated
    reason rather than an unexplained missing point.

    US-33.2 added a second cause: a day on which a WITHHELD-quantity symbol
    traded moves cash with no offsetting position in market value, so the
    portfolio value steps with nothing behind it. The reason names whichever
    causes actually occurred — collapsing two different degradations into one
    sentence would tell the researcher the wrong thing about their data.
    """
    withheld = [state.date for state in states if not state.return_is_publishable]
    if not withheld:
        return withheld, None

    causes: list[str] = []
    if any(not state.return_is_publishable and state.reconciliation_adjustment for state in states):
        causes.append(
            "the state was adjusted to match the statement's ending NAV, which is an "
            "accounting entry rather than a market move"
        )
    if any(not state.return_is_publishable and state.unbacked_cash_flow for state in states):
        causes.append(
            "a holding whose reconstructed quantity was withheld traded that day, moving cash "
            "with no position behind it in market value"
        )
    return withheld, "Return withheld: " + "; ".join(causes) + "."


def market_derived_terminal_value(states: list[DailyPortfolioState]) -> float | None:
    """US-34.6 (Epic 34 F-7): the terminal value with the accounting entry removed.

    `_reconcile_terminal_state_to_statement_totals` snaps the last state's
    `total_portfolio_value` to the statement's ending NAV. That value is correct
    as a LEVEL — it is the broker's own number — but the amount it moved by is an
    accounting correction, not a market move, and US-31.3 established that such a
    correction must never be published as performance.

    US-31.3 applied that rule to the time-weighted return only. Every other
    period-level figure — Modified Dietz, and the investment gain — reads the
    reconciled terminal value straight, so each silently republished the entry
    the TWR refuses (IB2026: 2.35pp of a 5.30% money-weighted return, and
    $1,366.17 of a $3,080.88 gain).

    Returns the terminal value less its recorded adjustment, or the terminal
    value unchanged when nothing was reconciled. `None` for an empty series.

    Deliberately ONE helper: the two Modified Dietz implementations doing the
    same subtraction independently is precisely how they would drift apart.
    """
    if not states:
        return None
    terminal = states[-1]
    return terminal.total_portfolio_value - (terminal.reconciliation_adjustment or 0.0)


def withheld_return_impact_pct(states: list[DailyPortfolioState]) -> float | None:
    """US-34.2: percentage points the withheld days remove from the published return.

    The difference between the chain that skips unpublishable days (what the
    Dashboard shows) and the same chain including them. An impact estimate for
    disclosure — NOT a return, and never published as one: the withheld days'
    states carry an accounting adjustment or unbacked cash, which is exactly why
    their returns cannot be performance. Their size, however, is what tells the
    researcher how incomplete the published figure is.

    `None` when nothing was withheld, so an absent impact is never reported as a
    measured zero.
    """
    if not any(not state.return_is_publishable for state in states):
        return None

    def _chain(*, honour_withholding: bool) -> float:
        growth = 1.0
        for previous, current in zip(states, states[1:]):
            if previous.total_portfolio_value == 0:
                continue
            if honour_withholding and not current.return_is_publishable:
                continue
            growth *= 1 + (
                (current.total_portfolio_value - current.external_cash_flow)
                / previous.total_portfolio_value
                - 1
            )
        return (growth - 1) * 100

    return round(_chain(honour_withholding=False) - _chain(honour_withholding=True), 2)


def build_true_performance_series(
    daily_states: list[DailyPortfolioState],
    benchmark_rows: list[dict],
    *,
    portfolio_return_basis_contract: PortfolioReturnBasisContract = "verified_total_return",
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
        # US-27.9 (audit F11): never fabricate a plausible-looking 0.0 —
        # an unverified return basis suppresses the whole cumulative series
        # (null, explicit withholding), and a mid-series day whose prior
        # value is zero has no claimable return (null point; the chain
        # resumes on the next computable day). Only the verified series'
        # first point is a genuine 0.0 (the cumulative anchor).
        portfolio_return_pct: float | None = None
        # US-34.2: `replay_derived` chains identically — same daily return, same
        # withholding. The basis records where the inputs came from; it does not
        # change the arithmetic, and it must not silently widen to a basis that
        # has no claim to a return at all.
        if portfolio_return_basis_contract in _PUBLISHING_PORTFOLIO_BASES:
            if previous_state is None:
                portfolio_return_pct = 0.0
            else:
                daily_return = _time_weighted_daily_return(previous_state, state)
                if daily_return is not None:
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
    # US-33.2: a day whose cash moved with no position behind it cannot be read
    # as a market move at all — withhold rather than fabricate (guardrail #3).
    if not current_state.return_is_publishable:
        return None
    # US-34.8 (Epic 34 F-8): a reconciled day uses the MARKET-DERIVED value, so
    # the accounting adjustment never enters the return. US-31.3 achieved the
    # same guarantee by publishing nothing; this achieves it while keeping the
    # day's real market movement.
    current_value = current_state.total_portfolio_value - (current_state.reconciliation_adjustment or 0.0)
    return ((current_value - current_state.external_cash_flow) / previous_state.total_portfolio_value) - 1


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
    # US-34.6: LEVELS keep the reconciled value (it is the broker's ending NAV);
    # PERFORMANCE figures use the market-derived one, so neither the gain nor the
    # money-weighted return republishes the accounting entry the TWR withholds.
    performance_end_value = market_derived_terminal_value(daily_states)
    net_contributions = round(sum(state.external_cash_flow for state in daily_states[1:]), 2)
    investment_gain = round(performance_end_value - start_value - net_contributions, 2)
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
            money_weighted_return_pct = round(((performance_end_value - start_value - total_flows) / denominator) * 100, 2)

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
