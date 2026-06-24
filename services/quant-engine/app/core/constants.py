"""Shared analytics defaults — single source of truth (US-24.3).

These three values were previously copy-pasted across the engine layer. They
live in ``app/core`` (the lowest layer) so ``app/schemas``, ``app/analytics``,
and ``app/services`` can all import them without a layering cycle.
"""
import math


# Default benchmark symbol when a request omits one. Used by request schemas
# (Field/attribute defaults) and the engine ``... or DEFAULT_BENCHMARK_SYMBOL``
# fallbacks.
DEFAULT_BENCHMARK_SYMBOL = "SPY"

# Flat minimum daily-return observations for the distribution / correlation /
# drawdown engines: below this a metric is ``unavailable`` rather than
# fabricated. Distinct from ``risk.py``'s per-window ``WINDOW_MIN_OBSERVATIONS``
# OLS buffer ({20: 25, 60: 75, 252: 275}), which is a different concept.
MIN_DAILY_OBSERVATIONS = 20


def lookback_calendar_days(window_trading_days: int) -> int:
    """Calendar days to fetch to cover a trading-day window.

    Empirical heuristic (no academic basis): over-fetch by ~60% + 30 days so a
    ``window_trading_days`` window is reliably covered across weekends/holidays.
    e.g. 20 -> 62, 60 -> 126, 252 -> 434.
    """
    return math.ceil(window_trading_days * 1.6) + 30
