"""Currency risk contribution (US-26.2 / Epic 26).

Contract for the local / currency / interaction variance split. Formulas live
in `financial-methodology.md` §Currency Risk Contribution; the evidence behind
them is in `docs/finance/research/currency-risk-contribution-brief.md`.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.imports import ImportedPortfolioSnapshot


CurrencyRiskTrust = Literal["synthetic", "unavailable"]
CurrencyRiskWindow = Literal[60, 252]


class CurrencyRiskRequest(BaseModel):
    """Snapshot-wrapped, like the sibling Exposure engines (attribution,
    correlation) — NOT the flat `PortfolioEngineRequest` shape. Base-currency
    weights need the statement's own implied `fx_rates`, which only a real
    snapshot carries; the flat shape materialises them conditionally."""

    snapshot: ImportedPortfolioSnapshot
    window: CurrencyRiskWindow = 60


class CurrencyLegContribution(BaseModel):
    currency: str
    base_weight: float
    # Contribution to the CURRENCY variance share, in the same component-
    # covariance units. Null when this currency has no covered holding.
    contribution: float | None = None


class CurrencyRiskResult(BaseModel):
    """The three-way variance split, or an explicit unavailable payload.

    Every share is nullable and MAY BE NEGATIVE: a currency leg moving against
    the local leg genuinely reduces portfolio variance. Shares are never
    clamped — clamping would fabricate a floor the data does not support.
    """

    trust: CurrencyRiskTrust
    window_days: int
    observations: int = 0

    # The three component-covariance shares. Sum to exactly 1.0 by
    # construction when present (Var(r_p) = Cov(L,r_p) + Cov(F,r_p) + Cov(X,r_p)).
    local_variance_share: float | None = None
    currency_variance_share: float | None = None
    interaction_variance_share: float | None = None

    # Standalone annualised volatilities — a different question from
    # contribution, reported alongside so the two are not confused.
    local_standalone_vol_pct: float | None = None
    currency_standalone_vol_pct: float | None = None
    local_fx_correlation: float | None = None

    per_currency: list[CurrencyLegContribution] = Field(default_factory=list)

    # US-26.2 AC8: holdings with no fund-currency price history are EXCLUDED
    # and named — never assigned to the local leg at zero FX, which would
    # silently understate currency risk.
    excluded_symbols: list[str] = Field(default_factory=list)
    excluded_weight: float = 0.0

    note: str | None = None
