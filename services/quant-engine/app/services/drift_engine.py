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


def _portfolio_return(daily_states: list) -> float | None:
    """Compounded cash-flow-neutral TWR over the window's daily states
    (US-27.8 / audit F10; methodology §Portfolio Return Methodology).

    The previous implementation was `last/first − 1` on raw market value —
    a mid-window deposit + BUY (or withdrawal) showed up as "return". The
    TWR chain subtracts external flows before dividing by the prior value,
    so only investment performance moves the number.
    """
    if len(daily_states) < 2:
        return None
    growth = 1.0
    computed_any_return = False
    previous_state = daily_states[0]
    for state in daily_states[1:]:
        daily_return = _time_weighted_daily_return(previous_state, state)
        if daily_return is not None:
            growth *= 1 + daily_return
            computed_any_return = True
        previous_state = state
    if not computed_any_return:
        return None
    return round((growth - 1) * 100, 2)


def _benchmark_return(benchmark_rows: list[dict]) -> float | None:
    if len(benchmark_rows) < 2:
        return None
    price_map, _ = selected_history_price_map(benchmark_rows)
    sorted_prices = [v for _, v in sorted(price_map.items())]
    if len(sorted_prices) < 2 or not sorted_prices[0]:
        return None
    return round(((sorted_prices[-1] / sorted_prices[0]) - 1) * 100, 2)


def _build_daily_series(daily_states: list, benchmark_rows: list[dict]) -> list[DriftDailyPoint]:
    """Indexed daily series (start = 100) from the longest available window.

    US-27.8 (AC4 decision): the portfolio line is the compounded
    cash-flow-neutral TWR chain indexed to 100 — the same basis as the
    window return cards — NOT raw market value (a deposit would draw a
    fake up-move against the benchmark's price line). See methodology
    §Indexed Return Series.
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

    # TWR index by date: 100 on the first state, × (1 + r_t) per state.
    twr_index_by_date: dict[str, float] = {daily_states[0].date: 100.0}
    index_value = 100.0
    previous_state = daily_states[0]
    for state in daily_states[1:]:
        daily_return = _time_weighted_daily_return(previous_state, state)
        if daily_return is not None:
            index_value *= 1 + daily_return
        # daily_return None (zero prior value): index carries unchanged —
        # no return is claimable for that day; never a fabricated move.
        twr_index_by_date[state.date] = index_value
        previous_state = state

    series: list[DriftDailyPoint] = []
    for dt, bprice in sorted_prices:
        indexed = twr_index_by_date.get(dt)
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

        p_ret = _portfolio_return(daily_states)
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
            # US-27.8 (AC3): the basis label states what the engine actually
            # does — a broker-ledger replay measured as a cash-flow-neutral
            # TWR — not the synthetic current-holdings convention.
            note="Broker-ledger replay: compounded time-weighted return (cash-flow-neutral)" if p_ret is not None else None,
        ))

        # Use the Since Import (or the last processed) window for the daily series
        if label in ("Since Import", "12M") and not daily_series:
            daily_series = _build_daily_series(daily_states, benchmark_rows)

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
