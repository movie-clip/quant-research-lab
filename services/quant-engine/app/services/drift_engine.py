from __future__ import annotations

from datetime import date, timedelta
from typing import Literal

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL
from app.analytics.performance import _time_weighted_daily_return, build_daily_portfolio_states_with_fx_disclosure
from app.analytics.risk import selected_history_price_map
from app.schemas.drift import DriftEngineRequest, DriftResult, DriftWindow, DriftDailyPoint
from app.services.market_data import MarketDataService, VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request


_WINDOWS: list[tuple[str, int | None]] = [
    ("1M", 30),
    ("3M", 90),
    ("6M", 180),
    ("12M", 365),
    ("Since Import", None),  # None means use imported_at as start
]


def _fetch_benchmark_rows(market_data: MarketDataService, symbol: str, start: str, end: str) -> list[dict]:
    if symbol in VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST:
        return market_data.get_direct_verified_benchmark_history(symbol, start, end)
    return market_data.get_historical_prices(symbol, start, end)


# US-30.1 (audit F-2): a daily return at or below −100% is impossible for a
# long-only portfolio — it means the valuation inputs are broken. The chain
# fails closed (window → unavailable) instead of compounding a sign-flipped
# growth into a plausible-looking number. Deliberately NOT a clamp: clamping
# would fabricate.
IMPOSSIBLE_DAILY_RETURN = -1.0

# Per-path basis notes (US-30.1 / audit F-2): the note must state what the
# engine actually computed for THIS request.
LEDGER_REPLAY_NOTE = "Broker-ledger replay: compounded time-weighted return (cash-flow-neutral)"
SYNTHETIC_BASIS_NOTE = "Synthetic: current holdings × historical prices (market-value chain)"
DEGRADED_VALUATION_NOTE = (
    "Unavailable: degraded valuation inputs produced an impossible (≤ −100%) daily return"
)


def _daily_return(previous_state, state, *, use_ledger_basis: bool) -> float | None:
    """One day's return on the window's basis (US-30.1 / audit F-1).

    With ledger entries the cash-flow-neutral TWR formula applies
    (§Portfolio Return Methodology). Without a ledger there are no external
    flows to neutralize and `total_portfolio_value` rests on a reconstructed
    cash anchor the request cannot verify — the market-value chain of the
    held positions is the honest synthetic-history basis (§Synthetic
    History), matching the `Synthetic` trust badge this panel already shows.
    """
    if use_ledger_basis:
        return _time_weighted_daily_return(previous_state, state)
    if previous_state.total_market_value == 0:
        return None
    return (state.total_market_value / previous_state.total_market_value) - 1


def _compound_chain(daily_states: list, *, use_ledger_basis: bool) -> tuple[dict[str, float] | None, bool, bool]:
    """Indexed growth chain (100 on the first state) shared by the window
    return and the daily series, so the chart can never disagree with the
    cards (US-30.1 AC4). Returns (index_by_date, degraded, computed_any):
    degraded=True means an impossible daily return was encountered and the
    whole chain is withheld (fail-closed, audit F-2); computed_any=False
    means no day produced a claimable return (the caller must report None,
    never a fabricated flat 0.0%)."""
    if not daily_states:
        return None, False, False
    index_by_date: dict[str, float] = {daily_states[0].date: 100.0}
    index_value = 100.0
    computed_any = False
    previous_state = daily_states[0]
    for state in daily_states[1:]:
        daily_return = _daily_return(previous_state, state, use_ledger_basis=use_ledger_basis)
        if daily_return is not None:
            if daily_return <= IMPOSSIBLE_DAILY_RETURN:
                return None, True, computed_any
            index_value *= 1 + daily_return
            computed_any = True
        # daily_return None (zero prior value): index carries unchanged —
        # no return is claimable for that day; never a fabricated move.
        index_by_date[state.date] = index_value
        previous_state = state
    return index_by_date, False, computed_any


def _portfolio_return(daily_states: list, *, use_ledger_basis: bool) -> tuple[float | None, bool]:
    """Window return from the shared chain. Returns (pct, degraded)."""
    if len(daily_states) < 2:
        return None, False
    index_by_date, degraded, computed_any = _compound_chain(daily_states, use_ledger_basis=use_ledger_basis)
    if degraded or index_by_date is None or not computed_any:
        return None, degraded
    return round(index_by_date[daily_states[-1].date] - 100.0, 2), False


def _basis_note(p_ret: float | None, degraded: bool, *, use_ledger_basis: bool) -> str | None:
    """The note states what the engine actually computed for THIS request
    (US-30.1 AC3): the ledger-replay claim only when a ledger drove the
    numbers, the synthetic convention otherwise, and the degradation reason
    when the chain failed closed."""
    if p_ret is not None:
        return LEDGER_REPLAY_NOTE if use_ledger_basis else SYNTHETIC_BASIS_NOTE
    if degraded:
        return DEGRADED_VALUATION_NOTE
    return None


def _benchmark_return(benchmark_rows: list[dict]) -> float | None:
    if len(benchmark_rows) < 2:
        return None
    price_map, _ = selected_history_price_map(benchmark_rows)
    sorted_prices = [v for _, v in sorted(price_map.items())]
    if len(sorted_prices) < 2 or not sorted_prices[0]:
        return None
    return round(((sorted_prices[-1] / sorted_prices[0]) - 1) * 100, 2)


def _build_daily_series(daily_states: list, benchmark_rows: list[dict], *, use_ledger_basis: bool) -> list[DriftDailyPoint]:
    """Indexed daily series (start = 100) from the longest available window.

    US-30.1 (AC4): built from the SAME `_compound_chain` as the window cards
    — one basis, one code path, so the chart can never disagree with the
    cards. On the ledger path this is the cash-flow-neutral TWR chain
    (US-27.8: a deposit must not draw a fake up-move against the benchmark);
    on the no-ledger path it is the market-value chain of current holdings.
    A degraded chain (impossible daily return, audit F-2) withholds the
    portfolio line entirely — benchmark-only series, explicit nulls.
    """
    if not daily_states or not benchmark_rows:
        return []

    price_map, _ = selected_history_price_map(benchmark_rows)
    sorted_prices = sorted(price_map.items())
    if not sorted_prices:
        return []
    first_benchmark = sorted_prices[0][1]
    if not first_benchmark:
        return []

    index_by_date, degraded, computed_any = _compound_chain(daily_states, use_ledger_basis=use_ledger_basis)
    if degraded or index_by_date is None or not computed_any:
        index_by_date = {}

    series: list[DriftDailyPoint] = []
    for dt, bprice in sorted_prices:
        indexed = index_by_date.get(dt)
        series.append(DriftDailyPoint(
            date=dt,
            portfolio_indexed=round(indexed, 2) if indexed is not None else None,
            benchmark_indexed=round((float(bprice) / float(first_benchmark)) * 100, 2),
        ))
    return series


def run_drift_engine(request: DriftEngineRequest) -> DriftResult:
    snapshot = build_imported_snapshot_from_request(request)
    benchmark_symbol = request.benchmark_symbol or DEFAULT_BENCHMARK_SYMBOL
    market_data = MarketDataService()

    # US-30.1 (audit F-1): the basis is chosen by what the snapshot actually
    # carries. Only a ledger justifies the cash-flow-neutral TWR claim; the
    # request path (positions + cash, no ledger) gets the synthetic
    # market-value chain — the convention its `Synthetic` badge states.
    use_ledger_basis = bool(snapshot.ledger_entries)

    today = date.today()
    today_str = today.isoformat()

    since_import_date: date | None = request.imported_at.date() if request.imported_at else None
    symbols = [p.symbol for p in request.positions]

    windows: list[DriftWindow] = []
    daily_series: list[DriftDailyPoint] = []
    fx_fallback_currencies: set[str] = set()

    for label, days in _WINDOWS:
        if days is not None:
            start_date = today - timedelta(days=days)
        elif since_import_date is not None:
            start_date = since_import_date
        else:
            windows.append(DriftWindow(
                label=label,
                trust="unavailable",
                note="No import date available",
            ))
            continue

        start_str = start_date.isoformat()

        benchmark_rows = _fetch_benchmark_rows(market_data, benchmark_symbol, start_str, today_str)
        if not benchmark_rows:
            windows.append(DriftWindow(label=label, start_date=start_str, end_date=today_str, trust="unavailable"))
            continue

        symbol_prices = market_data.get_historical_prices_for_symbols(symbols, start_str, today_str)
        valuation_dates = sorted({row["date"] for row in benchmark_rows})

        daily_states, window_fx_fallback = build_daily_portfolio_states_with_fx_disclosure(
            snapshot=snapshot,
            price_histories=symbol_prices,
            valuation_dates=valuation_dates,
            fx_history={},
        )
        fx_fallback_currencies.update(window_fx_fallback)

        p_ret, degraded = _portfolio_return(daily_states, use_ledger_basis=use_ledger_basis)
        b_ret = _benchmark_return(benchmark_rows)
        spread = round(p_ret - b_ret, 2) if p_ret is not None and b_ret is not None else None

        windows.append(DriftWindow(
            label=label,
            start_date=valuation_dates[0] if valuation_dates else start_str,
            end_date=valuation_dates[-1] if valuation_dates else today_str,
            portfolio_return_pct=p_ret,
            benchmark_return_pct=b_ret,
            spread_pct=spread,
            trust="synthetic" if p_ret is not None else "unavailable",
            note=_basis_note(p_ret, degraded, use_ledger_basis=use_ledger_basis),
        ))

        # Use the Since Import (or the last processed) window for the daily series
        if label in ("Since Import", "12M") and not daily_series:
            daily_series = _build_daily_series(daily_states, benchmark_rows, use_ledger_basis=use_ledger_basis)

    available = sum(1 for w in windows if w.trust == "synthetic")
    availability: Literal["available", "partial", "unavailable"] = (
        "available" if available == len(windows)
        else "partial" if available > 0
        else "unavailable"
    )

    return DriftResult(
        windows=windows,
        benchmark_symbol=benchmark_symbol,
        daily_series=daily_series,
        availability=availability,
        fx_fallback_currencies=sorted(fx_fallback_currencies),
    )
