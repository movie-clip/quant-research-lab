"""Currency risk engine (US-26.2 / Epic 26).

Wires market data (fund-currency prices + FX pairs) into the pure
`analytics/currency_risk.py` decomposition.

**Why this is its own engine rather than part of the exposure engine:**
`exposure_engine.py` fetches no historical prices — it is a pure snapshot
engine. This analytic needs windowed price *and* FX history, so attaching it
there would mix snapshot analytics with synthetic history in one response
(guardrail #2) and would slow every Exposure request even when the card is not
viewed. This follows the established dedicated-route + self-fetching-card
pattern (attribution, correlation, and the whole Risk tab).

**The highest-risk detail:** local returns must come from each holding's
REGISTRY FUND CURRENCY, not the broker's listing currency. US-31.5 proved the
two differ (DEFS is listed EUR but `DEFS.L` quotes USD) and that using the
listing currency made replay drift 4.3x worse. A wrong assignment here silently
moves return between the legs — and the identity check still passes, because
both legs come from the same wrong split.
"""

from __future__ import annotations

from datetime import date, timedelta

from app.analytics.currency import position_base_market_values
from app.analytics.currency_risk import build_currency_risk_decomposition, build_holding_legs
from app.core.constants import lookback_calendar_days
from app.schemas.currency_risk import (
    CurrencyLegContribution,
    CurrencyRiskRequest,
    CurrencyRiskResult,
)
from app.services.market_data import MarketDataService


def _unavailable(window: int, note: str) -> CurrencyRiskResult:
    return CurrencyRiskResult(trust="unavailable", window_days=window, note=note)


def fund_currency_map(symbols: list[str]) -> dict[str, str]:
    """Registry fund currency per symbol — the currency its resolved market
    line actually QUOTES in (US-31.5), not the broker's listing currency."""
    from app.instruments import InstrumentRegistry

    registry = InstrumentRegistry()
    resolved: dict[str, str] = {}
    for symbol in symbols:
        instrument = registry.get_instrument(symbol)
        if instrument is not None and instrument.currency:
            resolved[symbol] = instrument.currency
    return resolved


def run_currency_risk_engine(request: CurrencyRiskRequest) -> CurrencyRiskResult:
    snapshot = request.snapshot
    window = request.window
    base_currency = snapshot.statement.base_currency or "USD"

    if not snapshot.positions:
        return _unavailable(window, "No positions to decompose.")

    base_values, _fx_disclosure = position_base_market_values(snapshot)
    total_base = sum(base_values)
    if total_base <= 0:
        return _unavailable(window, "Portfolio has no base-currency market value.")

    symbols = [position.symbol for position in snapshot.positions]
    fund_currencies = fund_currency_map(symbols)

    end = date.today()
    start = end - timedelta(days=lookback_calendar_days(window))
    from_date, to_date = start.isoformat(), end.isoformat()

    market_data = MarketDataService()
    price_histories = market_data.get_historical_prices_for_symbols(symbols, from_date, to_date)

    # FX pairs come from the portfolio's OWN fund currencies, not a fixed list.
    needed_pairs = {
        f"{fund_currencies.get(sym, base_currency)}{base_currency}"
        for sym in symbols
        if fund_currencies.get(sym, base_currency) != base_currency
    }
    fx_series: dict[str, dict[str, float]] = {}
    for pair in sorted(needed_pairs):
        rows = market_data.get_fx_history(pair, from_date, to_date)
        series = {row["date"]: float(row["price"]) for row in rows if row.get("price")}
        if series:
            fx_series[pair] = series

    holdings = []
    excluded: list[str] = []
    excluded_weight = 0.0
    for position, base_value in zip(snapshot.positions, base_values):
        weight = base_value / total_base
        currency = fund_currencies.get(position.symbol, base_currency)
        rows = price_histories.get(position.symbol) or []
        prices = {row["date"]: float(row["price"]) for row in rows if row.get("price")}
        pair = f"{currency}{base_currency}"
        fx = None if currency == base_currency else fx_series.get(pair)

        # US-26.2 AC8: a holding we cannot price in its fund currency — or a
        # non-base holding whose FX pair we cannot fetch — is EXCLUDED and
        # named. It is never assigned to the local leg at zero FX, which would
        # silently understate currency risk.
        if not prices or (currency != base_currency and not fx):
            excluded.append(position.symbol)
            excluded_weight += weight
            continue

        holdings.append(build_holding_legs(position.symbol, weight, currency, prices, fx))

    if not holdings:
        return CurrencyRiskResult(
            trust="unavailable",
            window_days=window,
            excluded_symbols=sorted(excluded),
            excluded_weight=round(excluded_weight, 6),
            note="No holding had both fund-currency price history and (where needed) FX history.",
        )

    decomposition = build_currency_risk_decomposition(holdings)
    if decomposition.local_variance_share is None:
        return CurrencyRiskResult(
            trust="unavailable",
            window_days=window,
            observations=decomposition.observations,
            excluded_symbols=sorted(excluded),
            excluded_weight=round(excluded_weight, 6),
            note=(
                f"Needs at least 20 overlapping days of price and FX history; "
                f"found {decomposition.observations}."
            ),
        )

    weight_by_currency: dict[str, float] = {}
    for holding in holdings:
        weight_by_currency[holding.currency] = weight_by_currency.get(holding.currency, 0.0) + holding.base_weight

    per_currency = [
        CurrencyLegContribution(
            currency=currency,
            base_weight=round(weight_by_currency.get(currency, 0.0), 6),
            contribution=contribution,
        )
        for currency, contribution in sorted(
            decomposition.per_currency_contribution.items(),
            key=lambda item: -abs(item[1]),
        )
    ]

    return CurrencyRiskResult(
        trust="synthetic",
        window_days=window,
        observations=decomposition.observations,
        local_variance_share=decomposition.local_variance_share,
        currency_variance_share=decomposition.currency_variance_share,
        interaction_variance_share=decomposition.interaction_variance_share,
        local_standalone_vol_pct=decomposition.local_standalone_vol_pct,
        currency_standalone_vol_pct=decomposition.currency_standalone_vol_pct,
        local_fx_correlation=decomposition.local_fx_correlation,
        per_currency=per_currency,
        excluded_symbols=sorted(excluded),
        excluded_weight=round(excluded_weight, 6),
    )
