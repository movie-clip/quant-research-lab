"""Pure-analytics tests for app/analytics/distribution.py.

Verifies percentile / VaR / CVaR / distribution-shape / histogram against
deterministic fixtures — no market data, no engine wiring. All pure Python.
"""
from __future__ import annotations

from app.analytics.distribution import (
    compute_cvar,
    compute_distribution_shape,
    compute_histogram,
    compute_percentiles,
    compute_var,
)


# ── Percentiles ───────────────────────────────────────────────────────────────


def test_compute_percentiles_matches_known_values_for_symmetric_series() -> None:
    """28-value symmetric series. The 50th percentile (median) must be 0.
    The 5th percentile via NIST linear interpolation (rank = 0.05 * 27 = 1.35)
    interpolates between sorted_values[1] = -3.0 and sorted_values[2] = -3.0
    → still -3.0 (the bottom three values tie)."""
    series = [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0] * 4
    result = compute_percentiles(series)
    assert result["50"] is not None
    assert abs(result["50"]) < 1e-9
    assert result["5"] is not None
    assert abs(result["5"] - (-3.0)) < 1e-6


def test_compute_percentiles_returns_all_none_when_below_min_obs() -> None:
    """Series of 5 values → below the 20-obs threshold → every key is None."""
    series = [0.01, 0.02, 0.03, 0.04, 0.05]
    result = compute_percentiles(series)
    assert set(result.keys()) == {"5", "10", "50", "90", "95"}
    assert all(v is None for v in result.values())


# ── VaR ───────────────────────────────────────────────────────────────────────


def test_compute_var_95_returns_positive_loss_for_typical_returns() -> None:
    """20 small positives + 5 large negatives → 5th percentile is a loss
    → var_95 > 0 (positive number = loss reported as positive)."""
    series = [0.001] * 20 + [-0.04, -0.05, -0.06, -0.07, -0.08]
    var_95 = compute_var(series, 0.95)
    assert var_95 is not None
    assert var_95 > 0


def test_compute_var_95_returns_negative_for_window_without_losses() -> None:
    """25 all-positive returns → the 5th percentile is still POSITIVE
    → var_95 < 0. This is the methodology Contract rule — NEVER clip to 0,
    a negative VaR is a meaningful signal."""
    series = [0.001 * (i + 1) for i in range(25)]  # 0.001 .. 0.025
    var_95 = compute_var(series, 0.95)
    assert var_95 is not None
    assert var_95 < 0


def test_compute_var_returns_none_below_min_obs() -> None:
    series = [0.001] * 10
    assert compute_var(series, 0.95) is None


# ── CVaR ──────────────────────────────────────────────────────────────────────


def test_compute_cvar_95_returns_at_least_var_95_for_typical_returns() -> None:
    """CVaR ≥ VaR by construction (coherent risk measure, Acerbi & Tasche)."""
    series = [0.001] * 20 + [-0.04, -0.05, -0.06, -0.07, -0.08]
    var_95 = compute_var(series, 0.95)
    cvar_95 = compute_cvar(series, 0.95)
    assert var_95 is not None
    assert cvar_95 is not None
    assert cvar_95 >= var_95


def test_compute_cvar_returns_none_when_tail_too_small() -> None:
    """A series of exactly n=20 with a single large negative outlier and
    19 identical positives forces the tail to size 1.

    At n=20, α=0.95 → rank = 0.95 * 19 = 0.95, which interpolates between
    sorted[0]=-1.0 and sorted[1]=0.1 → threshold = 0.05 * (-1.0) + 0.95 *
    0.1 = 0.045. The tail {r ≤ 0.045} contains only the outlier −1.0
    (the 19 positives are all 0.1 > 0.045) → tail size 1 → CVaR returns
    None per methodology contract."""
    series = [-1.0] + [0.1] * 19
    cvar_95 = compute_cvar(series, 0.95)
    assert cvar_95 is None


# ── Distribution shape ────────────────────────────────────────────────────────


def test_compute_distribution_shape_returns_zero_skew_for_symmetric_series() -> None:
    series = [-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0] * 4
    result = compute_distribution_shape(series)
    assert result["mean_pct"] is not None
    assert result["skewness"] is not None
    assert abs(result["mean_pct"]) < 1e-6
    assert abs(result["skewness"]) < 1e-6


def test_compute_distribution_shape_returns_none_when_std_is_zero() -> None:
    """Constant series → std is 0 → skew and kurtosis are mathematically
    undefined → both return None. mean_pct and std_pct still computed."""
    series = [0.001] * 25
    result = compute_distribution_shape(series)
    assert result["mean_pct"] is not None
    assert result["std_pct"] is not None
    assert abs(result["std_pct"]) < 1e-12
    assert result["skewness"] is None
    assert result["kurtosis_excess"] is None


# ── Histogram ─────────────────────────────────────────────────────────────────


def test_compute_histogram_returns_thirty_bins_with_total_count_matching_input() -> None:
    """100 deterministic values spanning [-0.05, 0.05] → 30 bins, total
    count = 100, each bin's center inside [min(r), max(r)]."""
    # Use a deterministic generator (no randomness): linspace-like spread
    series = [-0.05 + (i / 99) * 0.10 for i in range(100)]
    bins = compute_histogram(series)

    assert len(bins) == 30
    assert sum(b.count for b in bins) == 100

    lo = min(series)
    hi = max(series)
    for b in bins:
        # Each center must fall inside [min, max]
        assert lo <= b.center <= hi
