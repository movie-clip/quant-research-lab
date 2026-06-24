"""Intra-portfolio correlation engine service.

Builds a holdings × holdings pairwise Pearson correlation matrix over a
requested lookback window, plus the average pairwise correlation and the
most/least-correlated holding pairs.

Trust class: synthetic history.  Each holding's daily return series is the
simple price return of its symbol over the window (current holdings applied to
historical prices).  Results are never labelled "verified".

Reuses the existing synthetic-history plumbing from correlation_engine.py
(`_returns_from_price_series`, the shared `lookback_calendar_days`) and the pure
analytics in analytics/correlation.py (`pearson` via `pairwise_correlation_matrix`).

See docs/finance/financial-methodology.md §Intra-Portfolio Correlation.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.analytics.correlation import (
    average_pairwise_correlation,
    diversification_ratio,
    effective_number_of_bets,
    pairwise_correlation_matrix,
    population_stdev,
)
from app.schemas.intra_correlation import (
    IntraCorrelationRequest,
    IntraCorrelationResult,
    PairStat,
)
from app.core.constants import MIN_DAILY_OBSERVATIONS, lookback_calendar_days
from app.services.correlation_engine import _returns_from_price_series
from app.services.market_data import MarketDataService


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
        date.today() - timedelta(days=lookback_calendar_days(lookback_days))
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
        if non_null < MIN_DAILY_OBSERVATIONS:
            excluded_symbols.append(sym)
            continue
        returns_by_symbol[sym] = series
        priceable_in_rank_order.append(sym)

    # Cap to top-N priceable holdings by weight (already rank-ordered).
    selected = priceable_in_rank_order[:max_holdings]

    # Provenance: which selected holdings were sourced from the secondary
    # provider (Yahoo Finance) rather than FMP. Read from MarketDataService's
    # per-symbol fetch metadata recorded during get_historical_prices_for_symbols.
    yahoo_sourced_symbols = [
        sym for sym in selected
        if (market_data.last_fetch_meta.get(sym) or {}).get("vendor") == "yfinance"
    ]

    if len(selected) < 2:
        return _unavailable(excluded_symbols)

    matrix = pairwise_correlation_matrix(
        returns_by_symbol, selected, min_observations=MIN_DAILY_OBSERVATIONS
    )
    avg = average_pairwise_correlation(matrix)
    most, least = _extreme_pairs(matrix, selected)

    # ── Diversification summary (US-17.2) ──────────────────────────────────────
    # Current market-value weights renormalised over the selected priceable
    # universe (the same universe the matrix is built over).
    raw_weights = [mv_by_symbol[sym] for sym in selected]
    total_weight = sum(raw_weights)
    weights = [w / total_weight for w in raw_weights] if total_weight > 0 else []

    # Per-holding standalone volatilities (population stdev of daily returns).
    sigmas = [population_stdev(returns_by_symbol[sym]) for sym in selected]

    # Synthetic portfolio daily return under *constant current weights*:
    # r_p(t) = Σ wᵢ rᵢ(t), defined only on dates where every selected holding has
    # a return. This is the coherent DR denominator (guarantees DR ≥ 1) and is
    # consistent with the weights/σ used in the numerator.
    portfolio_returns: list[float | None] = []
    n_dates = len(valuation_dates)
    for idx in range(n_dates):
        components = [returns_by_symbol[sym][idx] for sym in selected]
        if weights and all(c is not None for c in components):
            portfolio_returns.append(sum(w * c for w, c in zip(weights, components)))  # type: ignore[misc]
        else:
            portfolio_returns.append(None)
    non_null_portfolio = sum(1 for r in portfolio_returns if r is not None)
    portfolio_stdev = (
        population_stdev(portfolio_returns) if non_null_portfolio >= MIN_DAILY_OBSERVATIONS else None
    )

    dr = diversification_ratio(weights, sigmas, portfolio_stdev)
    enb = effective_number_of_bets(matrix)

    return IntraCorrelationResult(
        symbols=selected,
        matrix=matrix,
        average_pairwise_correlation=avg,
        most_correlated_pair=most,
        least_correlated_pair=least,
        diversification_ratio=dr,
        effective_number_of_bets=enb,
        excluded_symbols=excluded_symbols,
        yahoo_sourced_symbols=yahoo_sourced_symbols,
        lookback_days=lookback_days,
        trust="synthetic",
    )
