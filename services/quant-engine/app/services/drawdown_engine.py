"""Drawdown analytics engine (Epic 13 — Risk tab).

Wires market data → synthetic daily portfolio states → wealth index →
underwater series + episodes. All outputs are synthetic-history trust.

Mirrors the structure of stress_engine.py (US-13.1) and
attribution_engine.py.

Methodology: see §Wealth Index and Drawdown + §Drawdown episode
identification in docs/finance/financial-methodology.md.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL, MIN_DAILY_OBSERVATIONS, lookback_calendar_days
from app.analytics.drawdown import (
    build_underwater_series,
    current_drawdown_pct,
    decompose_drawdown_episode,
    identify_drawdown_episodes,
    max_drawdown_pct,
)
from app.analytics.risk import _build_wealth_index
from app.schemas.drawdown import DrawdownEngineRequest, DrawdownEngineResponse
from app.services.synthetic_history import build_synthetic_snapshot_history_states_with_coverage
from app.services.market_data import MarketDataService
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request


# Cap on calendar-day fetch when the request specifies window=None ("Max").
# 3000 days ≈ 8.2 years. Beyond this, factor stability concerns outweigh the
# value of more data, and FMP cache misses become common. Kept as a module
# constant so it's greppable + documented at the implementation site.
_MAX_LOOKBACK_CALENDAR_DAYS = 3000

# Top-N drawdown episodes shown in the UI. Fixed at 5 per US-13.2 scope.
_TOP_N_EPISODES = 5


def _empty_response(window_trading_days: int | None, coverage=None) -> DrawdownEngineResponse:
    """Build the fail-closed (unavailable) response. No fabrication."""
    return DrawdownEngineResponse(
        window_trading_days=window_trading_days,
        underwater_series=[],
        current_drawdown_pct=None,
        max_drawdown_pct=None,
        episodes=[],
        trust="unavailable",
        coverage=coverage,
    )


def _compute_daily_returns(
    daily_states: list,
) -> list[tuple[str, float]]:
    """Convert daily portfolio states into (date, daily_return) pairs.

    Uses each state's `total_market_value`. The first date carries
    return = 0 (no prior baseline) and is included so the wealth index
    starts at 100 on that date.
    """
    if not daily_states:
        return []
    returns: list[tuple[str, float]] = []
    prev_value: float | None = None
    for state in daily_states:
        value = state.total_market_value
        if prev_value is None:
            returns.append((state.date, 0.0))
        elif prev_value > 0 and value is not None:
            returns.append((state.date, (value / prev_value) - 1))
        else:
            # Gap in valuation — drop the day rather than fabricate a return.
            pass
        prev_value = value
    return returns


def run_drawdown_engine(request: DrawdownEngineRequest) -> DrawdownEngineResponse:
    """Compute the underwater curve + top-N drawdown episodes for the
    requested portfolio over the requested lookback window.

    Returns trust='unavailable' when:
      - request has no positions
      - market data cannot be fetched for the lookback period
      - fewer than MIN_DAILY_OBSERVATIONS daily underwater points result
    """
    window = request.window_trading_days  # 252 | 756 | 1260 | None

    # Fail-closed: no positions → no synthetic history possible.
    if not request.positions:
        return _empty_response(window)

    snapshot = build_imported_snapshot_from_request(request)

    today = date.today()
    if window is None:
        history_start = (today - timedelta(days=_MAX_LOOKBACK_CALENDAR_DAYS)).isoformat()
    else:
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
    daily_states, coverage = build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
    )

    daily_returns = _compute_daily_returns(daily_states)
    if len(daily_returns) < MIN_DAILY_OBSERVATIONS:
        return _empty_response(window, coverage=coverage)

    wealth_index = _build_wealth_index(daily_returns)
    underwater = build_underwater_series(wealth_index)

    if len(underwater) < MIN_DAILY_OBSERVATIONS:
        return _empty_response(window, coverage=coverage)

    episodes = identify_drawdown_episodes(underwater, top_n=_TOP_N_EPISODES)

    # US-15.1: per-position decomposition for each top-N episode.
    # Mutates each episode in place via model_copy (Pydantic) to populate the
    # top_contributors / other_contribution_pct / decomposition_residual_pct
    # / decomposition_trust fields. Skipped naturally when daily_states is
    # empty (decompose returns 'unavailable'); fail-graceful per methodology.
    decomposed_episodes = [
        episode.model_copy(update=_decompose_fields(daily_states, episode))
        for episode in episodes
    ]

    return DrawdownEngineResponse(
        window_trading_days=window,
        underwater_series=underwater,
        current_drawdown_pct=current_drawdown_pct(underwater),
        max_drawdown_pct=max_drawdown_pct(underwater),
        episodes=decomposed_episodes,
        trust="synthetic",
        coverage=coverage,
    )


def _decompose_fields(daily_states: list, episode) -> dict:
    """Run decompose_drawdown_episode and return a dict ready for
    `model_copy(update=...)`. Pulled into a helper so the engine's main
    body stays readable."""
    top_contributors, other_contribution_pct, residual_pct, trust = (
        decompose_drawdown_episode(daily_states, episode, top_n=_TOP_N_EPISODES)
    )
    return {
        "top_contributors": top_contributors,
        "other_contribution_pct": other_contribution_pct,
        "decomposition_residual_pct": residual_pct,
        "decomposition_trust": trust,
    }
