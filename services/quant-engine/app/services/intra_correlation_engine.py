"""Intra-portfolio correlation engine service.

Builds a holdings × holdings pairwise Pearson correlation matrix over a
requested lookback window, plus the average pairwise correlation and the
most/least-correlated holding pairs.

Trust class: synthetic history.  Each holding's daily return series is the
simple price return of its symbol over the window (current holdings applied to
historical prices).  Results are never labelled "verified".

Reuses the existing synthetic-history plumbing from correlation_engine.py
(`_returns_from_price_series`, `_lookback_calendar_days`) and the pure
analytics in analytics/correlation.py (`pearson` via `pairwise_correlation_matrix`).

See docs/finance/financial-methodology.md §Intra-Portfolio Correlation.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.analytics.correlation import (
    average_pairwise_correlation,
    pairwise_correlation_matrix,
)
from app.schemas.intra_correlation import (
    IntraCorrelationRequest,
    IntraCorrelationResult,
    PairStat,
)
from app.services.correlation_engine import (
    _lookback_calendar_days,
    _returns_from_price_series,
)
from app.services.market_data import MarketDataService

# Minimum overlapping trading-day returns needed for a non-null pair / a
# holding to count as having "sufficient history".  Matches the multi-benchmark
# engine's threshold.
_MIN_OBSERVATIONS = 20


def _extreme_pairs(
    matrix: list[list[float | None]],
    symbols: list[str],
) -> tuple[PairStat | None, PairStat | None]:
    """Return the (most_correlated, least_correlated) off-diagonal pairs.

    Both are None when there is no non-null off-diagonal entry.
    """
    most: PairStat | None = None
    least: PairStat | None = None
    n = len(symbols)
    for i in range(n):
        for j in range(i + 1, n):
            v = matrix[i][j]
            if v is None:
                continue
            pair = PairStat(symbol_a=symbols[i], symbol_b=symbols[j], correlation=v)
            if most is None or v > most.correlation:
                most = pair
            if least is None or v < least.correlation:
                least = pair
    return most, least


def run_intra_correlation(request: IntraCorrelationRequest) -> IntraCorrelationResult:
    """Compute the intra-portfolio correlation matrix for a snapshot.

    Returns trust='unavailable' (empty matrix) when fewer than 2 priceable
    holdings have sufficient history; otherwise trust='synthetic'.  A holding
    with no fetchable / insufficient price history is dropped and surfaced in
    `excluded_symbols`.  Cash and non-priceable instruments never enter the
    matrix (positions only).
    """
    snapshot = request.snapshot
    lookback_days = request.lookback_days
    max_holdings = request.max_holdings

    def _unavailable(excluded: list[str]) -> IntraCorrelationResult:
        return IntraCorrelationResult(
            symbols=[],
            matrix=[],
            average_pairwise_correlation=None,
            most_correlated_pair=None,
            least_correlated_pair=None,
            excluded_symbols=excluded,
            lookback_days=lookback_days,
            trust="unavailable",
        )

    if not snapshot.positions:
        return _unavailable([])

    # Aggregate market value by symbol (dedupe lots); rank by weight desc,
    # breaking ties by symbol for determinism.
    mv_by_symbol: dict[str, float] = {}
    for pos in snapshot.positions:
        mv_by_symbol[pos.symbol] = mv_by_symbol.get(pos.symbol, 0.0) + pos.market_value
    ranked_symbols = [
        sym for sym, _ in sorted(mv_by_symbol.items(), key=lambda kv: (-kv[1], kv[0]))
    ]

    history_end = date.today().isoformat()
    history_start = (
        date.today() - timedelta(days=_lookback_calendar_days(lookback_days))
    ).isoformat()

    market_data = MarketDataService()

    # SPY establishes the common trading-date grid.
    spy_rows = market_data.get_historical_prices("SPY", history_start, history_end)
    if not spy_rows:
        return _unavailable([])
    valuation_dates = sorted({row["date"] for row in spy_rows})

    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        ranked_symbols, history_start, history_end
    )

    # Build per-symbol return series; split into priceable (sufficient history)
    # and excluded (no / insufficient history).
    returns_by_symbol: dict[str, list[float | None]] = {}
    priceable_in_rank_order: list[str] = []
    excluded_symbols: list[str] = []

    for sym in ranked_symbols:
        rows = symbol_price_histories.get(sym) or []
        if not rows:
            excluded_symbols.append(sym)
            continue
        price_by_date = {row["date"]: float(row["price"]) for row in rows}
        ret_by_date = _returns_from_price_series(price_by_date, valuation_dates)
        series = [ret_by_date.get(d) for d in valuation_dates]
        non_null = sum(1 for r in series if r is not None)
        if non_null < _MIN_OBSERVATIONS:
            excluded_symbols.append(sym)
            continue
        returns_by_symbol[sym] = series
        priceable_in_rank_order.append(sym)

    # Cap to top-N priceable holdings by weight (already rank-ordered).
    selected = priceable_in_rank_order[:max_holdings]

    if len(selected) < 2:
        return _unavailable(excluded_symbols)

    matrix = pairwise_correlation_matrix(
        returns_by_symbol, selected, min_observations=_MIN_OBSERVATIONS
    )
    avg = average_pairwise_correlation(matrix)
    most, least = _extreme_pairs(matrix, selected)

    return IntraCorrelationResult(
        symbols=selected,
        matrix=matrix,
        average_pairwise_correlation=avg,
        most_correlated_pair=most,
        least_correlated_pair=least,
        excluded_symbols=excluded_symbols,
        lookback_days=lookback_days,
        trust="synthetic",
    )
