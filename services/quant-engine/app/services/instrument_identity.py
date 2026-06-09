"""Instrument identity integrity detector (US-19.1).

Cross-checks each registry-known holding's broker-statement description against
the registry's fund name and flags a mismatch only when their normalized
significant-token sets are DISJOINT (conservative — catches different-issuer /
different-fund mislabels like the DFND case, without firing on formatting or
share-class suffix noise).

Flag only — never rewrites the registry, remaps the symbol, or changes
prices/sector. No external lookup; uses only what the statement already carries.
"""
from __future__ import annotations

import re

from app.instruments.registry import InstrumentRegistry
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.provenance import InstrumentIdentityMismatch

# Non-identifying tokens: wrappers, share-class/currency/distribution suffixes,
# legal-entity words. Stripped before comparing identity.
_NOISE_TOKENS = {
    "UCITS", "ETF", "ETC", "ETN", "FUND", "FUNDS", "INDEX",
    "ACC", "ACCUMULATING", "ACCUMULATION", "DIST", "DISTRIBUTING", "INCOME", "INC",
    "PLC", "LTD", "CORP", "CO", "CLASS", "SHARES", "SHARE", "UNITS", "UNIT",
    "HEDGED", "USD", "EUR", "GBP", "GBX", "CHF", "JPY",
    "THE", "AND", "OF", "A", "AN",
}


def _significant_tokens(text: str) -> set[str]:
    """Uppercase identity tokens with noise + 1-char tokens dropped (numbers kept)."""
    raw = re.split(r"[^A-Z0-9]+", text.upper())
    return {
        tok for tok in raw
        if tok and tok not in _NOISE_TOKENS and (len(tok) > 1 or tok.isdigit())
    }


def detect_instrument_identity_mismatches(
    snapshot: ImportedPortfolioSnapshot,
    registry: InstrumentRegistry | None = None,
) -> list[InstrumentIdentityMismatch]:
    """Return identity-disjoint mismatches between broker descriptions and the
    registry fund name, for registry-known holdings with a non-trivial description."""
    reg = registry or InstrumentRegistry()
    mismatches: list[InstrumentIdentityMismatch] = []

    for instrument in snapshot.instruments:
        description = (instrument.description or "").strip()
        if not description:
            continue  # no evidence to compare
        if description.upper() == instrument.symbol.strip().upper():
            continue  # trivial (ticker-only) description

        entry = reg.get_instrument(instrument.symbol)
        if entry is None:
            continue  # not registry-known → no registry name to conflict with

        desc_tokens = _significant_tokens(description) - {instrument.symbol.strip().upper()}
        name_tokens = _significant_tokens(entry.name)
        if not desc_tokens or not name_tokens:
            continue  # not enough signal on one side

        if desc_tokens.isdisjoint(name_tokens):
            mismatches.append(InstrumentIdentityMismatch(
                symbol=instrument.symbol,
                statement_description=description,
                registry_name=entry.name,
            ))

    return mismatches
