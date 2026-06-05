"""Pydantic schemas for the intra-portfolio correlation engine.

Holdings × holdings pairwise Pearson correlation matrix plus summary stats.

Trust class: synthetic history.  Each holding's daily return series is the
simple price return of its symbol over the lookback window (current holdings
applied to historical prices).  Results are never labelled "verified".

See docs/finance/financial-methodology.md §Intra-Portfolio Correlation.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.imports import ImportedPortfolioSnapshot


class IntraCorrelationRequest(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    lookback_days: int = Field(default=60, ge=1)
    # Cap the rendered matrix to the top-N holdings by weight for legibility.
    max_holdings: int = Field(default=15, ge=2)


class PairStat(BaseModel):
    """A single holding pair and its correlation (used for most/least callouts)."""
    symbol_a: str
    symbol_b: str
    correlation: float


class IntraCorrelationResult(BaseModel):
    """Pairwise correlation matrix over the priceable holdings universe.

    `symbols` are ordered by current weight descending and capped at
    `max_holdings`.  `matrix` is a square, symmetric N×N grid aligned to
    `symbols`; the diagonal is always exactly 1.0; an off-diagonal cell is
    None when the pair has fewer than the minimum overlapping returns or a
    zero-variance series (never 0).

    `trust='unavailable'` when fewer than 2 priceable holdings have sufficient
    history (matrix empty); otherwise 'synthetic'.
    """
    symbols: list[str]
    matrix: list[list[float | None]]
    average_pairwise_correlation: float | None = None
    most_correlated_pair: PairStat | None = None
    least_correlated_pair: PairStat | None = None
    # Holdings dropped because they had no fetchable / insufficient price history.
    excluded_symbols: list[str] = Field(default_factory=list)
    lookback_days: int
    trust: Literal["synthetic", "unavailable"]
