"""Pure scalar correlation analytics.

Provides Pearson ρ, beta, and R² over paired return series.
All functions accept sequences with null (None) entries; nulls are dropped
before computation so sparse histories degrade gracefully.

Formulas (see docs/finance/financial-methodology.md §Multi-Benchmark Correlation):

  pearson(r_p, r_b) = cov(r_p, r_b) / (std(r_p) × std(r_b))
  beta(r_p, r_b)    = cov(r_p, r_b) / var(r_b)
  r_squared(r_p, r_b) = pearson(r_p, r_b)²

All statistics use population (N-denominator) covariance and variance so
results are consistent regardless of sample size.  Returns are expected as
decimal fractions (e.g. 0.01, not 1.0) but any consistent scale is fine
because correlation is unit-free and beta is scale-invariant when both
series share the same units.

Trust class: synthetic history.  Results are always labelled "synthetic"
(current holdings applied to historical prices) — never "verified".
"""
from __future__ import annotations

import math
from typing import Sequence


def pearson(
    r_p: Sequence[float | None],
    r_b: Sequence[float | None],
) -> float | None:
    """Pearson correlation coefficient between two return series.

    Args:
        r_p: Portfolio daily returns (may contain None).
        r_b: Benchmark daily returns (may contain None).

    Returns:
        Pearson ρ in [-1, 1], or None when:
        - fewer than 2 overlapping non-null pairs are available
        - either series has zero variance over the overlapping window
    """
    pairs = [
        (p, b)
        for p, b in zip(r_p, r_b)
        if p is not None and b is not None
    ]
    if len(pairs) < 2:
        return None

    ps, bs = zip(*pairs)
    n = len(ps)
    mean_p = sum(ps) / n
    mean_b = sum(bs) / n

    cov = sum((p - mean_p) * (b - mean_b) for p, b in zip(ps, bs)) / n
    std_p = math.sqrt(sum((p - mean_p) ** 2 for p in ps) / n)
    std_b = math.sqrt(sum((b - mean_b) ** 2 for b in bs) / n)

    if std_p == 0.0 or std_b == 0.0:
        return None

    # Clamp to [-1, 1] to absorb floating-point rounding at extremes.
    return max(-1.0, min(1.0, cov / (std_p * std_b)))


def beta(
    r_p: Sequence[float | None],
    r_b: Sequence[float | None],
    min_observations: int = 20,
) -> float | None:
    """Portfolio beta vs benchmark.

    Args:
        r_p: Portfolio daily returns (may contain None).
        r_b: Benchmark daily returns (may contain None).
        min_observations: Minimum overlapping pairs required (default 20).

    Returns:
        Beta (cov / var_b), or None when:
        - fewer than min_observations overlapping non-null pairs exist
        - benchmark variance is zero
    """
    pairs = [
        (p, b)
        for p, b in zip(r_p, r_b)
        if p is not None and b is not None
    ]
    if len(pairs) < min_observations:
        return None

    ps, bs = zip(*pairs)
    n = len(ps)
    mean_p = sum(ps) / n
    mean_b = sum(bs) / n

    cov = sum((p - mean_p) * (b - mean_b) for p, b in zip(ps, bs)) / n
    var_b = sum((b - mean_b) ** 2 for b in bs) / n

    if var_b == 0.0:
        return None

    return cov / var_b


def r_squared(
    r_p: Sequence[float | None],
    r_b: Sequence[float | None],
) -> float | None:
    """Coefficient of determination (R²) between portfolio and benchmark.

    R² = ρ² where ρ is the Pearson correlation coefficient.

    Returns None when pearson() returns None.
    """
    rho = pearson(r_p, r_b)
    return rho * rho if rho is not None else None
