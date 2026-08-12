"""Currency risk contribution (US-26.2 / Epic 26).

How much of a portfolio's return volatility came from currency moves rather
than from the underlying securities. Implements `financial-methodology.md`
§Currency Risk Contribution verbatim; the evidence behind those formulas is in
`docs/finance/research/currency-risk-contribution-brief.md`.

**Synthetic history**: current holdings × historical prices. Trust ceiling
`synthetic`, never `verified`.

Two decisions worth knowing before editing:

1. **The decomposition is an exact identity, not an approximation.**
   `(1 + r_base) = (1 + r_local) × (1 + r_fx)`, so
   `r_base = r_local + r_fx + (r_local × r_fx)` exactly. The cross term is
   negligible per day (≤5.4bp measured on IB2026) but **compounds** — +0.504pp
   of cumulative return on SEMI over six months — so it is retained and
   reported as its own leg rather than dropped or folded into currency.

2. **Variance splits by component covariance, not by `Var(F)/Var(r_p)`.**
   Since `r_p = L + F + X`, bilinearity gives
   `Var(r_p) = Cov(L, r_p) + Cov(F, r_p) + Cov(X, r_p)` exactly, so the three
   shares sum to 1.0 with no residual. The naive ratio ignores `Cov(L, F)` and
   would not account for the portfolio. This is the same identity `risk.py`
   already uses for factor and position risk-share.

A share **may be negative** — a currency leg moving against the local leg
genuinely reduces portfolio variance — and is never clamped.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.core.constants import MIN_DAILY_OBSERVATIONS

TRADING_DAYS_PER_YEAR = 252


@dataclass(frozen=True)
class HoldingReturnLegs:
    """One holding's daily legs, keyed by date. Days missing either input are
    absent entirely — never zero-filled."""

    symbol: str
    base_weight: float
    currency: str
    local: dict[str, float] = field(default_factory=dict)
    fx: dict[str, float] = field(default_factory=dict)

    def interaction(self, date: str) -> float:
        return self.local[date] * self.fx[date]


@dataclass
class CurrencyRiskDecomposition:
    observations: int = 0
    local_variance_share: float | None = None
    currency_variance_share: float | None = None
    interaction_variance_share: float | None = None
    local_standalone_vol_pct: float | None = None
    currency_standalone_vol_pct: float | None = None
    local_fx_correlation: float | None = None
    per_currency_contribution: dict[str, float] = field(default_factory=dict)


def build_holding_legs(
    symbol: str,
    base_weight: float,
    currency: str,
    local_prices: dict[str, float],
    fx_prices: dict[str, float] | None,
) -> HoldingReturnLegs:
    """Daily local / FX legs for one holding.

    `fx_prices` is None for a base-currency holding: `r_fx ≡ 0` exactly, so both
    the FX and interaction legs are zero — not a degradation, just arithmetic.

    A day is included only when BOTH sides have a usable prior and current
    observation. A day missing either is dropped from every leg, never
    zero-filled and never carried (the US-27.7 no-fabrication rule).
    """
    dates = sorted(local_prices) if fx_prices is None else sorted(set(local_prices) & set(fx_prices))
    local: dict[str, float] = {}
    fx: dict[str, float] = {}
    for previous, current in zip(dates, dates[1:]):
        previous_price = local_prices.get(previous)
        current_price = local_prices.get(current)
        if not previous_price or current_price is None:
            continue
        if fx_prices is None:
            local[current] = current_price / previous_price - 1
            fx[current] = 0.0
            continue
        previous_rate = fx_prices.get(previous)
        current_rate = fx_prices.get(current)
        if not previous_rate or current_rate is None:
            continue
        local[current] = current_price / previous_price - 1
        fx[current] = current_rate / previous_rate - 1
    return HoldingReturnLegs(symbol=symbol, base_weight=base_weight, currency=currency, local=local, fx=fx)


def _portfolio_legs(holdings: list[HoldingReturnLegs]) -> tuple[list[str], list[float], list[float], list[float]]:
    """Weighted portfolio legs over the dates EVERY holding covers.

    Intersecting rather than unioning keeps the identity exact: a date where
    one holding is missing would otherwise silently change the effective weight
    of the rest.
    """
    if not holdings:
        return [], [], [], []
    covered = set(holdings[0].local)
    for holding in holdings[1:]:
        covered &= set(holding.local)
    dates = sorted(covered)

    local_series: list[float] = []
    fx_series: list[float] = []
    interaction_series: list[float] = []
    for date in dates:
        local_series.append(sum(h.base_weight * h.local[date] for h in holdings))
        fx_series.append(sum(h.base_weight * h.fx[date] for h in holdings))
        interaction_series.append(sum(h.base_weight * h.interaction(date) for h in holdings))
    return dates, local_series, fx_series, interaction_series


def _covariance(left: list[float], right: list[float]) -> float:
    """Sample covariance (N−1), matching risk.py's convention (US-27.9)."""
    n = len(left)
    if n < 2:
        return 0.0
    mean_left = statistics.fmean(left)
    mean_right = statistics.fmean(right)
    return sum((a - mean_left) * (b - mean_right) for a, b in zip(left, right)) / (n - 1)


def build_currency_risk_decomposition(holdings: list[HoldingReturnLegs]) -> CurrencyRiskDecomposition:
    """The three-way variance split. Fails closed on thin or degenerate data."""
    dates, local, fx, interaction = _portfolio_legs(holdings)
    observations = len(dates)
    if observations < MIN_DAILY_OBSERVATIONS:
        # Below the floor nothing is publishable — never a confident number
        # from a handful of days (methodology §Beta's len < 20 → null rule).
        return CurrencyRiskDecomposition(observations=observations)

    portfolio = [l + f + x for l, f, x in zip(local, fx, interaction)]
    total_variance = _covariance(portfolio, portfolio)
    if total_variance == 0:
        # A constant series carries no information; a 0/1 share would claim one.
        return CurrencyRiskDecomposition(observations=observations)

    local_share = _covariance(local, portfolio) / total_variance
    currency_share = _covariance(fx, portfolio) / total_variance
    interaction_share = _covariance(interaction, portfolio) / total_variance

    local_sd = statistics.stdev(local) if len(local) > 1 else 0.0
    fx_sd = statistics.stdev(fx) if len(fx) > 1 else 0.0
    correlation: float | None = None
    if local_sd > 0 and fx_sd > 0:
        correlation = round(_covariance(local, fx) / (local_sd * fx_sd), 4)

    # Per-currency contribution to the CURRENCY share: each currency's own
    # weighted FX leg, measured against the same portfolio series so the parts
    # sum to the whole.
    per_currency: dict[str, float] = {}
    currencies = {h.currency for h in holdings if any(h.fx.get(d) for d in dates)}
    for currency in currencies:
        members = [h for h in holdings if h.currency == currency]
        leg = [sum(h.base_weight * h.fx[date] for h in members) for date in dates]
        per_currency[currency] = round(_covariance(leg, portfolio) / total_variance, 6)

    return CurrencyRiskDecomposition(
        observations=observations,
        # Deliberately NOT clamped: a negative share is a real finding.
        local_variance_share=round(local_share, 6),
        currency_variance_share=round(currency_share, 6),
        interaction_variance_share=round(interaction_share, 6),
        local_standalone_vol_pct=round(local_sd * (TRADING_DAYS_PER_YEAR ** 0.5) * 100, 4),
        currency_standalone_vol_pct=round(fx_sd * (TRADING_DAYS_PER_YEAR ** 0.5) * 100, 4),
        local_fx_correlation=correlation,
        per_currency_contribution=per_currency,
    )
