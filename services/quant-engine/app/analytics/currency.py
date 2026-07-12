"""Base-currency conversion for portfolio weights (US-30.5a / audit F-7).

Every Exposure weight denominator used to raw-sum ``position.market_value``
across EUR/GBP/USD — mixing currency numerals. Reproduced on the committed
IB2026 statement: the raw sum is $58,588.76 while FX-converting with the
statement's own implied rates yields $61,238.53, which reproduces the
statement's own ``stock_total`` to the cent. **The statement is the arbiter**,
so this is a unit-correctness bug, not a modelling preference.

Conversion policy (established by US-27.8 / US-30.2):

- a non-base position whose pair has a rate is converted at that STATIC
  period-end rate and its currency disclosed in ``static_rate_currencies``
  (never a claim of FX return dynamics);
- a non-base position with no rate is **carried unconverted** — the only
  honest number held — and its currency disclosed in
  ``fallback_currencies``. It is never dropped from the denominator (that
  would silently shrink the portfolio and inflate every other weight) and
  never converted 1:1;
- the base currency is disclosed in neither tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.imports import ImportedPortfolioSnapshot


DEFAULT_BASE_CURRENCY = "USD"


@dataclass
class FxDisclosure:
    """Which currencies were converted, and which were carried unconverted.

    Exactly one tier per non-base currency; the base currency is in neither.
    """

    static_rate_currencies: set[str] = field(default_factory=set)
    fallback_currencies: set[str] = field(default_factory=set)

    def sorted_static(self) -> list[str]:
        return sorted(self.static_rate_currencies)

    def sorted_fallback(self) -> list[str]:
        return sorted(self.fallback_currencies)


def fx_rate_key(currency: str, base_currency: str) -> str:
    """The ``"EURUSD"``-style key the statement's implied rates use."""
    return f"{currency}{base_currency}"


def convert_to_base(
    value: float,
    currency: str | None,
    base_currency: str,
    fx_rates: dict[str, float],
    disclosure: FxDisclosure | None = None,
) -> tuple[float, bool]:
    """Convert one value into the base currency.

    Returns ``(converted_value, converted)``. When no rate exists the RAW
    value is returned with ``converted=False`` — carried unconverted, never a
    silent 1:1 conversion claim. Records the currency in `disclosure` when
    given.
    """
    resolved = currency or base_currency
    if resolved == base_currency:
        return value, False

    rate = fx_rates.get(fx_rate_key(resolved, base_currency))
    if rate is None:
        if disclosure is not None:
            disclosure.fallback_currencies.add(resolved)
        return value, False

    if disclosure is not None:
        disclosure.static_rate_currencies.add(resolved)
    return value * rate, True


def snapshot_fx_context(snapshot: ImportedPortfolioSnapshot) -> tuple[str, dict[str, float]]:
    """The base currency + statement-implied rates carried by a snapshot.

    Imported snapshots carry these on ``statement_totals.fx_rates`` (US-28.1);
    request-built snapshots get them via ``PortfolioEngineRequest.fx_rates``
    (US-30.5a). Missing totals → no rates (everything carried unconverted).
    """
    base_currency = snapshot.statement.base_currency or DEFAULT_BASE_CURRENCY
    totals = snapshot.statement_totals
    fx_rates = dict(totals.fx_rates) if totals is not None else {}
    return base_currency, fx_rates


def position_base_market_values(
    snapshot: ImportedPortfolioSnapshot,
) -> tuple[list[float], FxDisclosure]:
    """Each position's market value in the base currency, in snapshot order."""
    base_currency, fx_rates = snapshot_fx_context(snapshot)
    disclosure = FxDisclosure()
    values = [
        convert_to_base(position.market_value, position.currency, base_currency, fx_rates, disclosure)[0]
        for position in snapshot.positions
    ]
    return values, disclosure


def base_market_value_by_symbol(snapshot: ImportedPortfolioSnapshot) -> dict[str, float]:
    """Base-currency market value per symbol (summed across duplicate lots)."""
    values, _ = position_base_market_values(snapshot)
    by_symbol: dict[str, float] = {}
    for position, value in zip(snapshot.positions, values):
        by_symbol[position.symbol] = by_symbol.get(position.symbol, 0.0) + value
    return by_symbol


def total_base_market_value(snapshot: ImportedPortfolioSnapshot) -> float:
    """Portfolio market value in the base currency — the honest weight
    denominator. For the committed IB2026 statement this reproduces the
    statement's own ``stock_total`` ($61,238.53) to the cent."""
    values, _ = position_base_market_values(snapshot)
    return sum(values)


def snapshot_fx_disclosure(snapshot: ImportedPortfolioSnapshot) -> FxDisclosure:
    """The disclosure tiers implied by a snapshot's positions + rates."""
    _, disclosure = position_base_market_values(snapshot)
    return disclosure
