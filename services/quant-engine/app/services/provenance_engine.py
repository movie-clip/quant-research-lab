"""Portfolio data-provenance engine (US-18.2).

For each holding, reports which market-data provider priced it — FMP (primary)
vs Yahoo Finance (secondary) — or that it is unpriced. Determines provenance by
a short market-data probe and reading `MarketDataService.last_fetch_meta`
vendor. Provider identity is window-independent, so the probe uses a small
lookback (cheap; cached histories make it near-free).

Source label only — not a return-basis trust claim.
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.constants import lookback_calendar_days
from app.core.symbols import canonicalize_symbol
from app.schemas.provenance import HoldingProvenance, ProvenanceRequest, ProvenanceResult
from app.services.instrument_identity import detect_instrument_identity_mismatches
from app.services.market_data import MarketDataService


def run_provenance(request: ProvenanceRequest) -> ProvenanceResult:
    snapshot = request.snapshot
    lookback_days = request.lookback_days

    # Identity warnings come from instrument descriptions vs the registry, so they
    # are computed independently of price-history provenance (and of positions).
    identity_warnings = detect_instrument_identity_mismatches(snapshot)

    symbols = sorted({pos.symbol for pos in snapshot.positions if pos.symbol})
    if not symbols:
        return ProvenanceResult(
            holdings=[],
            fmp_symbols=[],
            yahoo_sourced_symbols=[],
            unavailable_symbols=[],
            identity_warnings=identity_warnings,
            lookback_days=lookback_days,
        )

    history_end = date.today().isoformat()
    history_start = (date.today() - timedelta(days=lookback_calendar_days(lookback_days))).isoformat()
    market_data = MarketDataService()

    holdings: list[HoldingProvenance] = []
    fmp_symbols: list[str] = []
    yahoo_sourced_symbols: list[str] = []
    unavailable_symbols: list[str] = []

    for sym in symbols:
        rows = market_data.get_historical_prices(sym, history_start, history_end)
        meta = market_data.last_fetch_meta.get(canonicalize_symbol(sym)) or {}
        vendor_meta = meta.get("vendor")
        if rows:
            vendor = vendor_meta if vendor_meta in ("fmp", "yfinance") else "fmp"
        else:
            vendor = "unavailable"

        holdings.append(HoldingProvenance(symbol=sym, vendor=vendor))
        if vendor == "fmp":
            fmp_symbols.append(sym)
        elif vendor == "yfinance":
            yahoo_sourced_symbols.append(sym)
        else:
            unavailable_symbols.append(sym)

    return ProvenanceResult(
        holdings=holdings,
        fmp_symbols=fmp_symbols,
        yahoo_sourced_symbols=yahoo_sourced_symbols,
        unavailable_symbols=unavailable_symbols,
        identity_warnings=identity_warnings,
        lookback_days=lookback_days,
    )
