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


def pairwise_correlation_matrix(
    returns_by_symbol: dict[str, Sequence[float | None]],
    symbols: Sequence[str],
    min_observations: int = 20,
) -> list[list[float | None]]:
    """Symmetric holdings × holdings Pearson correlation matrix.

    See docs/finance/financial-methodology.md §Intra-Portfolio Correlation.

    Args:
        returns_by_symbol: symbol → daily return series, each aligned to a
            common date index (may contain None for missing days).
        symbols: ordered symbols defining the matrix rows/columns.
        min_observations: minimum overlapping non-null daily-return pairs
            required for an off-diagonal cell; below this the cell is None.

    Returns:
        An N×N matrix (N = len(symbols)) where:
        - matrix[i][i] == 1.0 (diagonal, by definition)
        - matrix[i][j] == matrix[j][i] (symmetric)
        - matrix[i][j] is None when the (i, j) pair has fewer than
          min_observations overlapping returns or a zero-variance series
          (pearson() returns None) — never 0 as a fabricated fill.
    """
    n = len(symbols)
    matrix: list[list[float | None]] = [[None] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 1.0

    for i in range(n):
        r_i = returns_by_symbol.get(symbols[i], [])
        for j in range(i + 1, n):
            r_j = returns_by_symbol.get(symbols[j], [])
            overlap = sum(
                1 for a, b in zip(r_i, r_j) if a is not None and b is not None
            )
            rho = pearson(r_i, r_j) if overlap >= min_observations else None
            matrix[i][j] = rho
            matrix[j][i] = rho

    return matrix


def average_pairwise_correlation(
    matrix: Sequence[Sequence[float | None]],
) -> float | None:
    """Mean of the off-diagonal (upper-triangle) non-null entries of a
    symmetric correlation matrix.

    Returns None when there are no non-null off-diagonal pairs (fewer than 2
    holdings with a computable correlation).
    """
    values: list[float] = []
    n = len(matrix)
    for i in range(n):
        for j in range(i + 1, n):
            v = matrix[i][j]
            if v is not None:
                values.append(v)
    if not values:
        return None
    return sum(values) / len(values)


def population_stdev(values: Sequence[float | None]) -> float | None:
    """Population (N-denominator) standard deviation of a return series.

    Nulls are dropped first.  Returns None when fewer than 2 non-null values
    remain (variance undefined / not meaningful) — never a fabricated 0.
    """
    xs = [v for v in values if v is not None]
    if len(xs) < 2:
        return None
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / n
    return math.sqrt(var)


def diversification_ratio(
    weights: Sequence[float],
    stdevs: Sequence[float | None],
    portfolio_stdev: float | None,
) -> float | None:
    """Diversification Ratio = Σ wᵢ σᵢ / σ_p (Choueifaty & Coignard 2008).

    See docs/finance/financial-methodology.md §Intra-Portfolio Correlation.

    Args:
        weights: per-holding weights (renormalised over the priceable universe).
        stdevs: per-holding population stdev of daily returns (aligned to weights).
        portfolio_stdev: population stdev of the synthetic portfolio daily returns.

    Returns:
        DR (≥ 1 in the absence of negative weights / perfect anti-correlation),
        or None when:
        - portfolio_stdev is None or 0
        - any per-holding stdev is None (incomplete inputs)
        - weights and stdevs lengths differ or are empty
    """
    if portfolio_stdev is None or portfolio_stdev == 0.0:
        return None
    if not weights or len(weights) != len(stdevs):
        return None
    if any(s is None for s in stdevs):
        return None
    weighted_vol = sum(w * s for w, s in zip(weights, stdevs))  # type: ignore[misc]
    return weighted_vol / portfolio_stdev


def effective_number_of_bets(
    matrix: Sequence[Sequence[float | None]],
) -> float | None:
    """Effective Number of Bets = exp(−Σ pₖ ln pₖ) over the normalised
    eigenvalues pₖ = λₖ / Σλ of the holdings correlation matrix (Meucci 2009).

    See docs/finance/financial-methodology.md §Intra-Portfolio Correlation.

    Returns None when:
    - the matrix has fewer than 2 rows
    - any off-diagonal cell is None (the matrix is not fully populated — the
      eigendecomposition requires a complete numeric matrix)
    - the eigenvalue sum is non-positive (degenerate / non-PSD)

    Tiny-negative eigenvalues from floating-point noise are clamped to 0
    (0·ln 0 ≡ 0).
    """
    n = len(matrix)
    if n < 2:
        return None
    # Require a fully-populated matrix (no null cell anywhere).
    for i in range(n):
        if len(matrix[i]) != n:
            return None
        for j in range(n):
            if matrix[i][j] is None:
                return None

    import numpy as np  # local import: numpy is only needed for the ENB path

    arr = np.array(matrix, dtype=float)
    eigenvalues = np.linalg.eigvalsh(arr)
    eigenvalues = np.clip(eigenvalues, 0.0, None)
    total = float(eigenvalues.sum())
    if total <= 0.0:
        return None

    p = eigenvalues / total
    # 0·ln0 ≡ 0 — only sum over strictly-positive probabilities.
    entropy = float(-np.sum(p[p > 0.0] * np.log(p[p > 0.0])))
    return float(np.exp(entropy))
