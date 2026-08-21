"""Identity-gated FMP sector resolution for equities outside the static
registry (US-37.1, T-37.1.1).

Resolution order for an equity `classify_imported_instrument`'s equity branch
does not already resolve via `INSTRUMENT_DEFINITIONS`: FMP company profile,
accepted only when the statement's ISIN and the FMP profile's ISIN are both
present and match. Every other outcome — lookup failure, no/empty profile, an
FMP `sector` string absent from `SECTOR_TAXONOMY_MAP`, an ISIN mismatch, or
missing identity evidence on either side — resolves to no classification
(`None, "unavailable"`). This module never guesses a sector and never passes
an unmapped FMP sector string through to the caller.

Truth class: snapshot analytics — a classification derived from current
market data at snapshot/import time, not broker truth.

Identity gate reuses `instrument_identity.normalize_isin` (US-19.1/US-19.2)
rather than a second, divergent ISIN-comparison implementation — see
docs/product/stories/US-37.1-dynamic-equity-sector-classification.md and
02-quant-research.md § Identity risk.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.schemas.imports import ImportedInstrument
from app.schemas.instruments import ClassificationSource
from app.services.instrument_identity import normalize_isin

if TYPE_CHECKING:
    from app.services.market_data import MarketDataService

# FMP `sector` string -> this project's sector-taxonomy string. Covers the 11
# GICS-style sectors live-verified against FMP (02-quant-research.md § Sector
# taxonomy normalization), including the five confirmed-divergent pairs:
# Health Care/Healthcare, Financials/Financial Services, Consumer
# Discretionary/Consumer Cyclical, Consumer Staples/Consumer Defensive,
# Materials/Basic Materials (AC7). An FMP sector string not present here is
# treated as no classification (AC6) — never passed through raw.
SECTOR_TAXONOMY_MAP: dict[str, str] = {
    "Technology": "Technology",
    "Energy": "Energy",
    "Industrials": "Industrials",
    "Real Estate": "Real Estate",
    "Utilities": "Utilities",
    "Communication Services": "Communication Services",
    "Healthcare": "Health Care",
    "Financial Services": "Financials",
    "Consumer Cyclical": "Consumer Discretionary",
    "Consumer Defensive": "Consumer Staples",
    "Basic Materials": "Materials",
}

# Whitespace/case-normalized lookup derived from SECTOR_TAXONOMY_MAP, used only
# at the taxonomy-matching step (US-37.2, T-37.2.1). Mirrors the identity
# gate's `normalize_isin` discipline: an FMP `sector` string that differs from
# a SECTOR_TAXONOMY_MAP key only by leading/trailing whitespace or letter case
# still resolves (AC1). A string genuinely absent from the map — not a
# casing/whitespace variant of a known key — still falls through to
# `unavailable` (AC2): this narrows what counts as unmapped, it does not widen
# what counts as mapped. SECTOR_TAXONOMY_MAP itself is left untouched — it is
# read directly (exact-case) elsewhere, e.g. by test_equity_sector_resolution.py.
_NORMALIZED_SECTOR_TAXONOMY_MAP: dict[str, str] = {
    key.strip().casefold(): value for key, value in SECTOR_TAXONOMY_MAP.items()
}


def resolve_equity_sector(
    imported: ImportedInstrument,
    market_data: "MarketDataService",
) -> tuple[str | None, ClassificationSource]:
    """Resolve one equity's sector via FMP, gated by ISIN identity match.

    Returns `(mapped_sector, "fmp_identity_confirmed")` only when both the
    statement's ISIN and the FMP profile's ISIN are present and equal (AC3).
    Returns `(None, "unavailable")` for every other outcome: lookup exception
    (AC8), no/empty profile, missing/unmapped `sector` value (AC6), ISIN
    mismatch (AC4), or missing identity evidence on either side (AC5).
    """
    try:
        profile = market_data.get_company_profile(imported.symbol)
    except Exception:  # noqa: BLE001 — mirrors instrument_enrichment.py's fail-safe pattern; AC8
        return None, "unavailable"

    if not profile or not profile.get("sector"):
        return None, "unavailable"

    mapped_sector = _NORMALIZED_SECTOR_TAXONOMY_MAP.get(profile["sector"].strip().casefold())
    if mapped_sector is None:
        return None, "unavailable"  # unmapped FMP sector string — never pass through raw, AC6

    statement_isin = normalize_isin(imported.isin)
    profile_isin = normalize_isin(profile.get("isin"))
    if statement_isin and profile_isin and statement_isin == profile_isin:
        return mapped_sector, "fmp_identity_confirmed"

    return None, "unavailable"  # mismatch (AC4) or no evidence either side (AC5) — collapsed, see US-37.1 design decision 3
