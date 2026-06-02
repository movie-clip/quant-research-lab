"""FMP-driven enrichment for `ImportedInstrument` entries.

When a parser (notably Freedom24) produces `ImportedInstrument` entries
whose `description` is just the bare ticker, the existing
`InstrumentRegistry.classify_imported_instrument` description-based
fallback can't infer the right sector. This module fills the gap by
looking up the symbol on FMP at import time and populating the
`description` (companyName) + `instrument_type` (ETF/STOCK from isEtf)
so downstream classification works.

Fast path: the static `INSTRUMENT_DEFINITIONS` dict skips FMP entirely
for known symbols (no I/O, deterministic).

Slow path: any unknown symbol with a bare-ticker description triggers a
single `get_company_profile` call. Fail-graceful — FMP outage or `None`
return leaves the original instrument unchanged.

Design notes:
- This module does NOT bypass the registry's classification logic.
  It just makes the description richer so the existing
  `classify_imported_instrument` keyword fallback can do its job.
- `instrument_type` is ASYMMETRIC: FMP can upgrade STOCK→ETF (when
  `isEtf=True` overrides a falsy parser declaration) but never
  downgrades ETF→STOCK. An explicit non-empty parser declaration of
  `"ETF"` (or anything else) is preserved.
"""
from __future__ import annotations

from app.instruments.registry import INSTRUMENT_DEFINITIONS, InstrumentRegistry
from app.schemas.imports import ImportedInstrument, ImportedPortfolioSnapshot


def _is_description_trivial(description: str | None, symbol: str) -> bool:
    """A description is trivial when it provides no information beyond
    the symbol itself — i.e. it's empty, OR identical to the upper-cased
    symbol, OR contains no whitespace and no lowercase letters (the
    Freedom24 `description=ticker` pattern).

    A description like ``"Apple Inc"`` (mixed case + whitespace) is
    non-trivial; we leave it alone and save an FMP call.
    """
    if not description:
        return True
    stripped = description.strip()
    if not stripped:
        return True
    if stripped.upper() == symbol.upper():
        return True
    has_lower = any(c.islower() for c in stripped)
    has_whitespace = any(c.isspace() for c in stripped)
    return not has_lower and not has_whitespace


def _enrich_one(
    instrument: ImportedInstrument,
    market_data,
    registry: InstrumentRegistry,
) -> ImportedInstrument:
    """Return either `instrument` unchanged, or a new ImportedInstrument
    with FMP-populated `description` and `instrument_type`.

    Fast-path skip for symbols already in the static registry. Description-
    aware skip when the parser already provided a non-trivial description.
    Fail-graceful on any FMP error or None return.
    """
    normalized = registry.normalize_symbol(instrument.symbol)
    # Fast path — known static symbol.
    if normalized in INSTRUMENT_DEFINITIONS:
        return instrument

    # Description-aware skip.
    if not _is_description_trivial(instrument.description, instrument.symbol):
        return instrument

    try:
        profile = market_data.get_company_profile(instrument.symbol)
    except Exception:  # noqa: BLE001 — fail-graceful per AC6
        return instrument

    if not profile:
        return instrument
    company_name = profile.get("companyName")
    if not company_name or not isinstance(company_name, str):
        return instrument

    # Asymmetric instrument_type: FMP can upgrade STOCK→ETF, but a
    # non-empty parser declaration always wins.
    fmp_is_etf = bool(profile.get("isEtf"))
    existing_type = (instrument.instrument_type or "").strip()
    if fmp_is_etf:
        new_instrument_type = "ETF"
    elif existing_type:
        new_instrument_type = existing_type
    else:
        new_instrument_type = "STOCK"

    return instrument.model_copy(update={
        "description": company_name.strip(),
        "instrument_type": new_instrument_type,
    })


def enrich_imported_instruments(
    snapshot: ImportedPortfolioSnapshot,
    market_data,
) -> ImportedPortfolioSnapshot:
    """Walk `snapshot.instruments`, enriching unknown-symbol entries with
    FMP company-profile data. Returns a NEW snapshot — the input is not
    mutated. Positions / cash / ledger / statement metadata preserved
    verbatim.

    `market_data` is duck-typed: any object exposing
    `get_company_profile(symbol) -> dict | None` works. In production
    this is `MarketDataService`.
    """
    registry = InstrumentRegistry()
    enriched: list[ImportedInstrument] = [
        _enrich_one(instrument, market_data, registry)
        for instrument in snapshot.instruments
    ]
    return snapshot.model_copy(update={"instruments": enriched})
