"""Daily return distribution / VaR / CVaR engine (Epic 13 — US-13.3).

Wires market data → synthetic daily portfolio states → daily returns →
percentile / VaR / CVaR / distribution shape / histogram. All outputs are
synthetic-history trust.

Mirrors the structure of drawdown_engine.py (US-13.2).

Methodology: see §Value-at-Risk and Distribution in
docs/finance/financial-methodology.md.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL, MIN_DAILY_OBSERVATIONS, lookback_calendar_days
from app.analytics.distribution import (
    compute_cvar,
    compute_distribution_shape,
    compute_histogram,
    compute_percentiles,
    compute_var,
)
from app.schemas.distribution import DistributionEngineRequest, DistributionEngineResponse
from app.services.diagnostics_engine import _build_synthetic_snapshot_history_states_with_coverage
from app.services.market_data import MarketDataService
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request


def _empty_response(window: int, coverage=None) -> DistributionEngineResponse:
    """Fail-closed (unavailable) response. No fabrication — every scalar
    is None, return_count is 0, histogram is empty."""
    return DistributionEngineResponse(
        window_trading_days=window,
        return_count=0,
        var_95=None,
        var_99=None,
        cvar_95=None,
        percentile_5=None,
        percentile_10=None,
        percentile_50=None,
        percentile_90=None,
        percentile_95=None,
        mean_pct=None,
        std_pct=None,
        skewness=None,
        kurtosis_excess=None,
        histogram_bins=[],
        trust="unavailable",
        coverage=coverage,
    )


def _compute_daily_returns(daily_states: list) -> list[float]:
    """Convert daily portfolio states into a list of daily returns.

    Returns are simple (not log) returns from each state's
    `total_market_value` vs the prior state's value. Days where the prior
    value is null/zero are skipped rather than fabricated. The first day
    (no baseline) is NOT included.

    Duplicated from drawdown_engine._compute_daily_returns — the two
    engines diverge in error handling (drawdown returns (date, return)
    tuples for wealth-index construction; distribution wants a flat
    list of returns).
    """
    if not daily_states:
        return []
    returns: list[float] = []
    prev_value: float | None = None
    for state in daily_states:
        value = state.total_market_value
        if prev_value is not None and prev_value > 0 and value is not None:
            returns.append((value / prev_value) - 1.0)
        prev_value = value
    return returns


def run_distribution_engine(request: DistributionEngineRequest) -> DistributionEngineResponse:
    """Compute the daily return distribution + VaR + CVaR + shape stats
    over the requested lookback window.

    Returns trust='unavailable' when:
      - request has no positions
      - market data cannot be fetched for the lookback period
      - fewer than MIN_DAILY_OBSERVATIONS daily returns result

    Sanity invariant: cvar_95 ≥ var_95 (CVaR ≥ VaR by construction, Acerbi
    & Tasche). If violated, raises rather than emitting inconsistent data
    (methodology Contract rule).
    """
    window = request.window_trading_days  # 60 | 252 | 504

    # Fail-closed: no positions → no synthetic history possible.
    if not request.positions:
        return _empty_response(window)

    snapshot = build_imported_snapshot_from_request(request)

    today = date.today()
    history_start = (today - timedelta(days=lookback_calendar_days(window))).isoformat()
    history_end = today.isoformat()

    market_data = MarketDataService()
    benchmark_symbol = request.benchmark_symbol or DEFAULT_BENCHMARK_SYMBOL
    benchmark_rows = market_data.get_historical_prices(
        benchmark_symbol, history_start, history_end,
    )
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [p.symbol for p in snapshot.positions], history_start, history_end,
    )

    if not benchmark_rows:
        return _empty_response(window)

    valuation_dates = sorted({row["date"] for row in benchmark_rows})
    daily_states, coverage = _build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
    )

    returns = _compute_daily_returns(daily_states)
    if len(returns) < MIN_DAILY_OBSERVATIONS:
        return _empty_response(window, coverage=coverage)

    percentiles = compute_percentiles(returns)
    var_95 = compute_var(returns, 0.95)
    var_99 = compute_var(returns, 0.99)
    cvar_95 = compute_cvar(returns, 0.95)
    shape = compute_distribution_shape(returns)
    histogram = compute_histogram(returns)

    # Methodology Contract rule: CVaR ≥ VaR by construction. Inconsistent
    # data should raise, not propagate. (Tolerate floating-point noise of
    # 1e-9; anything beyond that signals a real bug.)
    if (
        cvar_95 is not None
        and var_95 is not None
        and cvar_95 + 1e-9 < var_95
    ):
        raise ValueError(
            f"Coherent risk measure invariant violated: "
            f"CVaR_95 ({cvar_95}) < VaR_95 ({var_95}). "
            f"This is impossible by construction; engine output is inconsistent."
        )

    return DistributionEngineResponse(
        window_trading_days=window,
        return_count=len(returns),
        var_95=var_95,
        var_99=var_99,
        cvar_95=cvar_95,
        percentile_5=percentiles["5"],
        percentile_10=percentiles["10"],
        percentile_50=percentiles["50"],
        percentile_90=percentiles["90"],
        percentile_95=percentiles["95"],
        mean_pct=shape["mean_pct"],
        std_pct=shape["std_pct"],
        skewness=shape["skewness"],
        kurtosis_excess=shape["kurtosis_excess"],
        histogram_bins=histogram,
        trust="synthetic",
        coverage=coverage,
    )
