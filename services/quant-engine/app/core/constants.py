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


# De-minimis snapshot weight for the synthetic/broker history coverage rule
# (US-27.7). A holding at or above this share of the snapshot's positions
# market value is "material": its first available quote may truncate the
# effective valuation window. Below it, a holding whose price history starts
# after the effective start is excluded from the replayed universe (and, on
# the synthetic path, disclosed via SyntheticHistoryCoverage) rather than
# allowed to truncate a long window or enter mid-window with a fabricated
# weight jump. Heuristic policy value with no academic basis — tune only as
# a reviewed change (US-24.2 discipline).
SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT = 0.01
