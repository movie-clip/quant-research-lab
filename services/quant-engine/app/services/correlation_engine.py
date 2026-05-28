"""Multi-benchmark correlation engine service.

Computes Pearson ρ, beta, and R² for a portfolio snapshot vs five standard
benchmark proxies over a requested lookback window.

Trust class: synthetic history.  Current holdings are held constant and
applied backward in time to reconstruct daily portfolio returns.  Results
are never labelled "verified".

Benchmark universe (hardcoded):
  SPY  → S&P 500 (US Large-Cap / Broad Market)
  QQQ  → Nasdaq-100 (US Large-Cap Growth / Technology)
  GLD  → Gold (Commodities / Inflation Hedge)
  IEF  → US 7-10yr Treasuries (Intermediate Bonds)
  VT   → Vanguard Total World (Global Equity)

Formula (see docs/finance/financial-methodology.md §Multi-Benchmark Correlation):
  ρ   = cov(r_p, r_b) / (std(r_p) × std(r_b))
  β   = cov(r_p, r_b) / var(r_b)
  R²  = ρ²
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from app.analytics.correlation import beta as compute_beta
from app.analytics.correlation import pearson as compute_pearson
from app.analytics.correlation import r_squared as compute_r_squared
from app.schemas.correlation import (
    BenchmarkStats,
    MultiBenchmarkCorrelationRequest,
    MultiBenchmarkCorrelationResult,
)
from app.services.diagnostics_engine import _build_synthetic_snapshot_history_states
from app.services.market_data import MarketDataService


# Five benchmark proxies: symbol → human label.
BENCHMARK_UNIVERSE: list[tuple[str, str]] = [
    ("SPY", "S&P 500"),
    ("QQQ", "Nasdaq-100"),
    ("GLD", "Gold"),
    ("IEF", "US 7-10yr Bonds"),
    ("VT",  "Global Equity"),
]

# Minimum overlapping trading-day returns needed to produce a non-null result.
_MIN_OBSERVATIONS = 20


def _lookback_calendar_days(lookback_trading_days: int) -> int:
    """Convert a trading-day lookback to a calendar-day fetch window.

    Multiplies by 1.6 and adds a 30-day buffer to absorb weekends,
    public holidays, and thin trading periods — same heuristic as the
    attribution engine.
    """
    return math.ceil(lookback_trading_days * 1.6) + 30


def _returns_from_price_series(price_by_date: dict[str, float], dates: list[str]) -> dict[str, float | None]:
    """Compute simple daily returns from a price series aligned to trading dates."""
    returns: dict[str, float | None] = {}
    prev_price: float | None = None
    for d in dates:
        price = price_by_date.get(d)
        if price is None or prev_price is None or prev_price == 0.0:
            returns[d] = None
        else:
            returns[d] = (price / prev_price) - 1.0
        if price is not None:
            prev_price = price
    return returns


def run_multi_benchmark_correlation(
    request: MultiBenchmarkCorrelationRequest,
) -> MultiBenchmarkCorrelationResult:
    """Compute multi-benchmark correlation statistics for a portfolio snapshot.

    Returns MultiBenchmarkCorrelationResult with a BenchmarkStats row for each
    of the five benchmark proxies.  Individual fields are None when:
    - fewer than _MIN_OBSERVATIONS overlapping trading days are available
    - benchmark or portfolio price history cannot be fetched
    - portfolio has no positions

    When all fields for a benchmark are None, trust='unavailable'; otherwise
    trust='synthetic'.
    """
    snapshot = request.snapshot
    lookback_days = request.lookback_days

    empty_result = MultiBenchmarkCorrelationResult(
        benchmarks=[
            BenchmarkStats(
                symbol=sym,
                label=label,
                correlation=None,
                beta=None,
                r_squared=None,
                trust="unavailable",
            )
            for sym, label in BENCHMARK_UNIVERSE
        ],
        lookback_days=lookback_days,
    )

    if not snapshot.positions:
        return empty_result

    history_end = date.today().isoformat()
    history_start = (
        date.today() - timedelta(days=_lookback_calendar_days(lookback_days))
    ).isoformat()

    market_data = MarketDataService()

    # Fetch SPY rows to establish the common trading-date grid.
    spy_rows = market_data.get_historical_prices("SPY", history_start, history_end)
    if not spy_rows:
        return empty_result

    valuation_dates = sorted({row["date"] for row in spy_rows})

    # Fetch price histories for all portfolio symbols.
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [pos.symbol for pos in snapshot.positions],
        history_start,
        history_end,
    )

    # Build synthetic daily portfolio states.
    daily_states = _build_synthetic_snapshot_history_states(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
    )
    if not daily_states:
        return empty_result

    # Derive portfolio daily return series from synthetic states.
    portfolio_value_by_date: dict[str, float] = {
        state.date: state.total_portfolio_value
        for state in sorted(daily_states, key=lambda s: s.date)
    }
    portfolio_price_series = {d: portfolio_value_by_date[d] for d in valuation_dates if d in portfolio_value_by_date}
    portfolio_returns_by_date = _returns_from_price_series(portfolio_price_series, valuation_dates)

    # Compute stats for each benchmark.
    benchmark_rows_cache: dict[str, list[dict]] = {"SPY": spy_rows}

    benchmark_stats: list[BenchmarkStats] = []
    for sym, label in BENCHMARK_UNIVERSE:
        if sym not in benchmark_rows_cache:
            rows = market_data.get_historical_prices(sym, history_start, history_end)
            benchmark_rows_cache[sym] = rows or []

        rows = benchmark_rows_cache[sym]
        if not rows:
            benchmark_stats.append(BenchmarkStats(
                symbol=sym, label=label,
                correlation=None, beta=None, r_squared=None,
                trust="unavailable",
            ))
            continue

        bench_price_by_date: dict[str, float] = {
            row["date"]: float(row["price"]) for row in rows
        }
        bench_returns_by_date = _returns_from_price_series(bench_price_by_date, valuation_dates)

        # Align both return series to common dates.
        common_dates = [
            d for d in valuation_dates
            if portfolio_returns_by_date.get(d) is not None
            and bench_returns_by_date.get(d) is not None
        ]

        r_p = [portfolio_returns_by_date[d] for d in common_dates]
        r_b = [bench_returns_by_date[d] for d in common_dates]

        if len(common_dates) < _MIN_OBSERVATIONS:
            benchmark_stats.append(BenchmarkStats(
                symbol=sym, label=label,
                correlation=None, beta=None, r_squared=None,
                trust="unavailable",
            ))
            continue

        corr = compute_pearson(r_p, r_b)
        b = compute_beta(r_p, r_b, min_observations=_MIN_OBSERVATIONS)
        r2 = compute_r_squared(r_p, r_b)

        trust = "unavailable" if (corr is None and b is None and r2 is None) else "synthetic"
        benchmark_stats.append(BenchmarkStats(
            symbol=sym, label=label,
            correlation=corr, beta=b, r_squared=r2,
            trust=trust,
        ))

    # Sort rows by |correlation| descending; unavailable (null) rows go last.
    benchmark_stats.sort(
        key=lambda s: abs(s.correlation) if s.correlation is not None else -1.0,
        reverse=True,
    )

    return MultiBenchmarkCorrelationResult(
        benchmarks=benchmark_stats,
        lookback_days=lookback_days,
    )
