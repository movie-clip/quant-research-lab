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


# Tolerance (base-currency units) for the imported ledger-replay reconciliation
# (US-31.3 / Epic 31 F-2, F-3). Two uses, both fail-closed:
#   1. the opening cash anchor's residual vs the statement-implied opening cash
#      — at or below this the anchor is `verified`, above it `degraded`;
#   2. the terminal reconciliation adjustment — above this the affected day's
#      return is WITHHELD, because an accounting correction of that size would
#      otherwise be published as a market move (guardrail #3).
# $1.00 admits cent-level rounding across ~120 daily states and per-currency
# conversions while catching any real plug (the IB2026 anchor residual is
# ~$1,192). Heuristic policy value, no academic basis — tune only as a
# reviewed change (US-24.2 discipline).
REPLAY_RECONCILIATION_TOLERANCE = 1.00


# US-33.2 (Epic 33 F-1/F-2): share-unit discontinuity threshold for the ledger
# replay. The opening-position roll-back
# (`opening = ending + Σ SELL − Σ BUY`) is only valid while every quantity is
# denominated in the SAME share unit; a split breaks the identity and produces
# a phantom position. The detectable signature is a symbol whose own broker
# execution prices, WITHIN one currency, span a ratio no market move explains.
# At or above this ratio the symbol's reconstructed quantity is WITHHELD and
# disclosed rather than valued (guardrail #3).
# Calibrated on the committed IB2026 statement (68 symbols): the highest
# LEGITIMATE within-symbol ratio is 1.40 (NFLX); the true positive is LQQ at
# 218.10 (EUR 9.069 … 1,977.94). 5.0 sits ~3.6x above the highest legitimate
# observation and ~44x below the true positive.
# Known limitation, deliberate: a small split (2:1, 3:1) stays below this
# threshold and is NOT detected — lowering the bar far enough to catch it would
# start withholding genuinely volatile holdings over long windows. Closing that
# gap needs a corporate-action data source, an explicit Epic 33 non-goal.
# Heuristic policy value, no academic basis — tune only as a reviewed change
# (US-24.2 discipline).
REPLAY_SHARE_UNIT_DISCONTINUITY_RATIO = 5.0


# US-24.7: statement-reconciliation materiality. A reconciliation check passes
# when |actual - expected| is within this many base-currency units. Set at a
# quarter of a unit to absorb per-record rounding across a statement's worth of
# summed entries without masking a real discrepancy. Heuristic policy value, no
# academic basis — tune only as a reviewed change.
STATEMENT_RECONCILIATION_TOLERANCE = 0.25

# US-24.7: portfolio-proof terminal totals match. Deliberately far TIGHTER than
# REPLAY_RECONCILIATION_TOLERANCE (1.00) because the two answer different
# questions: this one compares the proof path's own recomputed totals against
# the statement's stated totals, where any disagreement beyond a cent means the
# recomputation is wrong; the replay tolerance absorbs genuine valuation
# residuals (FX rounding, a statement-anchored holding) across a whole window.
PORTFOLIO_PROOF_TERMINAL_MATCH_TOLERANCE = 0.01
