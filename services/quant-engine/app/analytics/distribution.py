"""Pure-analytics distribution helpers (Epic 13 — Risk tab US-13.3).

Functions in this module are I/O-free: they consume a list of daily returns
(decimal, not percent) and emit deterministic results. The market-data
fetching happens in `services/distribution_engine.py`.

Pure Python — no numpy or scipy (consistent with the rest of the analytics
codebase). Uses `statistics` standard library + hand-rolled quantile /
moment formulas per the methodology.

Methodology: see §Value-at-Risk and Distribution in
docs/finance/financial-methodology.md.
"""
from __future__ import annotations

import statistics

from app.core.constants import MIN_DAILY_OBSERVATIONS
from app.schemas.distribution import HistogramBin


# Histogram default. Methodology: "bins = 30 (default)".
_DEFAULT_HISTOGRAM_BINS = 30


# ── Percentiles (NIST linear interpolation) ───────────────────────────────────


def _quantile_linear(sorted_values: list[float], q: float) -> float:
    """NIST linear-interpolation quantile (equivalent to numpy.quantile default).

    sorted_values must be sorted ascending.
    q ∈ [0, 1].

    Formula: rank = q * (n - 1); interpolate linearly between floor(rank)
    and ceil(rank). For q=0 returns sorted_values[0]; for q=1 returns
    sorted_values[-1].
    """
    if not sorted_values:
        raise ValueError("Cannot compute quantile of empty series")
    if q <= 0:
        return sorted_values[0]
    if q >= 1:
        return sorted_values[-1]
    n = len(sorted_values)
    rank = q * (n - 1)
    lo = int(rank)
    hi = lo + 1 if lo + 1 < n else lo
    weight = rank - lo
    return sorted_values[lo] * (1.0 - weight) + sorted_values[hi] * weight


def compute_percentiles(returns: list[float]) -> dict[str, float | None]:
    """Compute the canonical 5 percentiles (5 / 10 / 50 / 90 / 95).

    Returns a dict with string keys (matching the schema-field naming
    convention). All values None when `len(returns) < MIN_DAILY_OBSERVATIONS`.
    """
    keys = ("5", "10", "50", "90", "95")
    if len(returns) < MIN_DAILY_OBSERVATIONS:
        return {k: None for k in keys}
    sorted_returns = sorted(returns)
    return {
        "5": _quantile_linear(sorted_returns, 0.05),
        "10": _quantile_linear(sorted_returns, 0.10),
        "50": _quantile_linear(sorted_returns, 0.50),
        "90": _quantile_linear(sorted_returns, 0.90),
        "95": _quantile_linear(sorted_returns, 0.95),
    }


# ── Historical VaR ────────────────────────────────────────────────────────────


def compute_var(returns: list[float], confidence: float) -> float | None:
    """Historical Value-at-Risk at the given confidence level.

    VaR_α = -quantile(returns, 1 - α) * 100   (positive = loss in percent)

    Returns None when `len(returns) < MIN_DAILY_OBSERVATIONS`.

    NEVER clipped to a positive number — a NEGATIVE VaR is a meaningful
    signal that the window contained no loss days at the requested
    confidence ("the tail day was still positive"). Methodology Contract
    rule.
    """
    if len(returns) < MIN_DAILY_OBSERVATIONS:
        return None
    sorted_returns = sorted(returns)
    threshold = _quantile_linear(sorted_returns, 1.0 - confidence)
    return -threshold * 100


# ── Conditional VaR (Expected Shortfall) ──────────────────────────────────────


def compute_cvar(returns: list[float], confidence: float) -> float | None:
    """Conditional VaR (Expected Shortfall) at the given confidence level.

    CVaR_α = -mean({r : r ≤ quantile(returns, 1 - α)}) * 100
    (positive = loss in percent)

    Returns None when:
      - `len(returns) < MIN_DAILY_OBSERVATIONS`
      - the tail (returns ≤ the quantile) contains fewer than 2 elements
    """
    if len(returns) < MIN_DAILY_OBSERVATIONS:
        return None
    sorted_returns = sorted(returns)
    threshold = _quantile_linear(sorted_returns, 1.0 - confidence)
    tail = [r for r in sorted_returns if r <= threshold]
    if len(tail) < 2:
        return None
    return -statistics.mean(tail) * 100


# ── Distribution shape (mean / std / skew / excess kurtosis) ──────────────────


def compute_distribution_shape(returns: list[float]) -> dict[str, float | None]:
    """Mean, std (population), skewness (Fisher-Pearson), excess kurtosis.

    Returns a dict with keys:
      mean_pct, std_pct, skewness, kurtosis_excess

    Edge cases:
      - len(returns) < MIN_DAILY_OBSERVATIONS: all four fields None
      - std == 0 (constant series): mean_pct and std_pct computed normally;
        skewness and kurtosis_excess return None

    Formulas:
      mean      = mean(r)
      std       = sqrt(pvar(r))            (population N denominator)
      m_k       = mean((r - mean)^k)
      skewness  = m_3 / m_2^(3/2)          (Fisher-Pearson, population)
      kurtosis  = m_4 / m_2^2 - 3          (EXCESS, Fisher convention)
    """
    keys = ("mean_pct", "std_pct", "skewness", "kurtosis_excess")
    if len(returns) < MIN_DAILY_OBSERVATIONS:
        return {k: None for k in keys}

    mean = statistics.mean(returns)
    pvar = statistics.pvariance(returns, mu=mean)
    std = pvar ** 0.5

    mean_pct = mean * 100
    std_pct = std * 100

    if std == 0:
        return {
            "mean_pct": mean_pct,
            "std_pct": std_pct,
            "skewness": None,
            "kurtosis_excess": None,
        }

    n = len(returns)
    m2 = pvar
    m3 = sum((r - mean) ** 3 for r in returns) / n
    m4 = sum((r - mean) ** 4 for r in returns) / n

    skewness = m3 / (m2 ** 1.5)
    kurtosis_excess = (m4 / (m2 ** 2)) - 3

    return {
        "mean_pct": mean_pct,
        "std_pct": std_pct,
        "skewness": skewness,
        "kurtosis_excess": kurtosis_excess,
    }


# ── Histogram ─────────────────────────────────────────────────────────────────


def compute_histogram(
    returns: list[float],
    num_bins: int = _DEFAULT_HISTOGRAM_BINS,
) -> list[HistogramBin]:
    """30-bin histogram of daily returns (range auto-fit, no padding/trim).

    Each bin's `center` is the bin midpoint (decimal return, NOT percent —
    the UI multiplies by 100 for display). The sum of `count` across all
    bins equals `len(returns)`.

    Returns an empty list when `len(returns) < MIN_DAILY_OBSERVATIONS`.

    All values fall inside [min(returns), max(returns)]. The bin
    assignment uses half-open intervals [edge_i, edge_{i+1}) for all bins
    EXCEPT the last, which uses [edge_n-1, edge_n] (closed) so the max
    value lands in the final bin (matches numpy.histogram behaviour).
    """
    if len(returns) < MIN_DAILY_OBSERVATIONS:
        return []

    lo = min(returns)
    hi = max(returns)

    if lo == hi:
        # Degenerate (all values identical). Put everything in a single
        # bin centred at lo so the total count still reconciles. Pad the
        # other bins with empty entries to honour the num_bins contract.
        bins: list[HistogramBin] = []
        for i in range(num_bins):
            bins.append(HistogramBin(center=lo, count=len(returns) if i == 0 else 0))
        return bins

    width = (hi - lo) / num_bins
    counts = [0] * num_bins
    for r in returns:
        # Bin index via floor(((r - lo) / width)); clamp to last bin for r == hi.
        idx = int((r - lo) / width)
        if idx >= num_bins:
            idx = num_bins - 1
        counts[idx] += 1

    return [
        HistogramBin(center=lo + (i + 0.5) * width, count=counts[i])
        for i in range(num_bins)
    ]
