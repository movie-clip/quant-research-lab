"""Currency exposure by weight (US-26.1 / Epic 26).

How much of the portfolio is denominated in each currency, and how much is not
in the base currency. `ImportedPosition.currency` has been imported on every
statement since the beginning and aggregated by nothing — a researcher holding
UCITS ETFs traded in EUR/GBP could not see that exposure on any tab.

**Snapshot analytics**: current holdings only, no historical prices, no
market-data call. Same truth class as sector exposure.

Two corrections to the research brief's formula, both made here (see the story
US-26.1 and methodology §Currency Exposure):

1. **The denominator is base-currency converted.** The brief specified raw
   ``market_value`` in numerator and denominator, which is exactly the F-7
   defect US-30.5a fixed as Critical: raw-summing values across currencies
   mixes units (IB2026: $58,588.76 raw vs $61,238.53 converted, the latter
   reproducing the statement's own ``stock_total`` to the cent). Shipping that
   on a card *about currency* would be the worst place to reintroduce it. Each
   position is converted first, then grouped by the currency it is
   **denominated in** — group by original currency, measure in one unit.

2. **The "unclassified" bucket the brief specifies is unreachable, and the
   real fabrication is upstream.** `ImportedPosition.currency` is
   ``str = Field(min_length=3, max_length=3)`` — required, so a snapshot with a
   currency-less position cannot be constructed; Pydantic rejects it. The brief
   also contradicted itself, saying such a position was "excluded from both
   numerator and denominator" AND "surfaced as a residual so the total still
   reconciles to 100%", which cannot both hold.

   The fabrication the brief was reaching for is real, but it happens BEFORE
   this module: on the request path,
   ``portfolio_snapshot_builder.py:43`` coerces
   ``currency=item.currency or request.base_currency or 'USD'``, so a position
   that stated no currency arrives here already labelled. This analytic cannot
   see that and must not pretend to — it is recorded as a finding for its own
   story rather than papered over with a bucket that can never fill.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.analytics.currency import FxDisclosure, position_base_market_values
from app.schemas.imports import ImportedPortfolioSnapshot


@dataclass(frozen=True)
class CurrencyWeight:
    currency: str
    market_value: float
    weight: float


@dataclass
class CurrencyExposure:
    """Per-currency composition of the portfolio, in base-currency terms.

    ``weights`` sum to 1.0 (within rounding) whenever the portfolio has value.
    ``non_base_weight`` is None when the statement carries no base currency —
    there is no baseline to compare against, and 0.0 would read as "no currency
    risk".
    """

    base_currency: str | None
    total_base_market_value: float
    weights: list[CurrencyWeight] = field(default_factory=list)
    non_base_weight: float | None = None
    fx_disclosure: FxDisclosure = field(default_factory=FxDisclosure)


def build_currency_exposure(snapshot: ImportedPortfolioSnapshot) -> CurrencyExposure:
    """Per-currency weights from an imported snapshot.

    Takes ONLY the snapshot: no market-data dependency (the Epic 26 success
    signal). FX conversion reuses `analytics/currency.py`'s helpers rather than
    re-deriving a second conversion path — the US-31.2 "one shared chain"
    lesson, and what keeps this card's denominator equal to the rest of the
    Exposure tab's.
    """
    base_currency = snapshot.statement.base_currency
    base_values, fx_disclosure = position_base_market_values(snapshot)

    by_currency: dict[str, float] = {}
    for position, base_value in zip(snapshot.positions, base_values):
        # `currency` is schema-required (3 chars), so every position is
        # attributable here. See the module docstring for where a currency-less
        # position actually gets labelled, and why that is not this module's
        # problem to hide.
        by_currency[position.currency] = by_currency.get(position.currency, 0.0) + base_value

    total = sum(by_currency.values())
    if total == 0:
        return CurrencyExposure(
            base_currency=base_currency,
            total_base_market_value=0.0,
            weights=[],
            non_base_weight=None,
            fx_disclosure=fx_disclosure,
        )

    weights = [
        CurrencyWeight(
            currency=currency,
            market_value=round(value, 2),
            weight=round(value / total, 6),
        )
        for currency, value in by_currency.items()
    ]
    # Weight desc, then currency for a stable order among equal weights.
    weights.sort(key=lambda item: (-item.weight, item.currency))

    non_base_weight: float | None = None
    if base_currency is not None:
        non_base_weight = round(
            (total - by_currency.get(base_currency, 0.0)) / total, 6
        )

    return CurrencyExposure(
        base_currency=base_currency,
        total_base_market_value=round(total, 2),
        weights=weights,
        non_base_weight=non_base_weight,
        fx_disclosure=fx_disclosure,
    )
