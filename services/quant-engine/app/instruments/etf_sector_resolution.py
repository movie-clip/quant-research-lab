"""Identity-gated FMP sector-weighting resolution for direct-held ETFs
outside the static registry (US-39.1, T-39.1.4).

Resolution order for a direct-held ETF classify_imported_instrument's ETF
branch does not already resolve via INSTRUMENT_DEFINITIONS: identity-gate
the security (statement ISIN vs. FMP company-profile ISIN, same mechanism
as the equity branch), then read a DIFFERENT FMP field for the theme
(etf/sector-weightings' dominant sector bucket, not the profile's own
`sector` field -- confirmed unreliable for ETFs, 03-quant-research.md
Live evidence log item 1). A dynamically-resolved sector is accepted only
when the top bucket's share of total reported weight clears
DOMINANCE_THRESHOLD. Every other outcome -- lookup failure, no/empty
profile, ISIN mismatch or missing evidence, empty/zero-weight response,
below-threshold top share, an unmapped sector bucket -- resolves to no
classification (None, "unavailable"). Never a fallback guess, and
specifically never "Broad Market" (see registry.py's ETF branch, where
that literal used to be the unconditional default).

Truth class: snapshot analytics, mirroring the equity dynamic tier -- never
"verified" (guardrail 3).

Identity gate reuses instrument_identity.normalize_isin, same as
equity_sector_resolution.py -- no second, divergent ISIN-comparison
implementation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from app.instruments.equity_sector_resolution import SECTOR_TAXONOMY_MAP
from app.schemas.imports import ImportedInstrument
from app.schemas.instruments import ClassificationSource
from app.services.instrument_identity import normalize_isin

if TYPE_CHECKING:
    from app.services.market_data import MarketDataService

# Human-confirmed 2026-08-24 -- see docs/product/stories/US-39.1-.../ Context
# "DOMINANCE_THRESHOLD = 55% -- resolved" for the evidence table. A fraction,
# not a percentage -- scale-invariant against whether FMP's raw weights are
# reported on a 0-100 or 0-1 basis, since only the RATIO top/total is used.
DOMINANCE_THRESHOLD = 0.55

_NORMALIZED_ETF_SECTOR_TAXONOMY_MAP: dict[str, str] = {
    key.strip().casefold(): value for key, value in SECTOR_TAXONOMY_MAP.items()
}


def _coerce_weight(value: object) -> float | None:
    """Defensive numeric coercion for one sector-weightings row's weight
    field. Live evidence (03-quant-research.md) rendered values as plain
    numbers (e.g. 37.4); this endpoint's raw JSON type was not captured
    verbatim, and FMP's legacy v3 surface is known to return a percentage
    as a "NN.NN%" string on some routes -- both shapes are handled here so
    a format difference degrades to "excluded from this weight vector"
    rather than crashing the import. None/non-numeric -> None."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().rstrip("%")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def resolve_etf_sector(
    imported: ImportedInstrument,
    market_data: "MarketDataService",
) -> tuple[str | None, ClassificationSource]:
    """Resolve one direct-held ETF's sector via FMP's sector-weightings
    endpoint, gated by ISIN identity match and a dominance-threshold
    aggregation over the reported weight vector.

    Returns (mapped_sector, "fmp_etf_sector_weighting_confirmed") only when
    ALL of: the statement ISIN and FMP profile ISIN are present and equal
    (AC3/AC4/AC5); the sector-weightings response is non-empty with a
    positive total weight (AC9); the top bucket's share of total weight is
    >= DOMINANCE_THRESHOLD (AC6/AC7); and the top bucket's sector string is
    present in SECTOR_TAXONOMY_MAP (AC8). Returns (None, "unavailable") for
    every other outcome, including any lookup exception (AC10).
    """
    try:
        profile = market_data.get_company_profile(imported.symbol)
    except Exception:  # noqa: BLE001 -- mirrors resolve_equity_sector's fail-safe pattern; AC10
        return None, "unavailable"

    if not profile or not profile.get("isin"):
        return None, "unavailable"

    statement_isin = normalize_isin(imported.isin)
    profile_isin = normalize_isin(profile.get("isin"))
    if not statement_isin or not profile_isin or statement_isin != profile_isin:
        return None, "unavailable"  # mismatch (AC4) or no evidence either side (AC5) -- collapsed, same as US-37.1

    try:
        weights = market_data.get_etf_sector_weightings(imported.symbol)
    except Exception:  # noqa: BLE001 -- AC10
        return None, "unavailable"

    if not weights:
        return None, "unavailable"  # AC9: empty response

    weighted_rows = [
        (row.get("sector"), _coerce_weight(row.get("weightPercentage")))
        for row in weights
        if isinstance(row, dict)
    ]
    usable_rows = [(sector, weight) for sector, weight in weighted_rows if weight is not None]
    total = sum(weight for _, weight in usable_rows)
    if total <= 0 or not usable_rows:
        return None, "unavailable"  # AC9: zero/degenerate total weight

    top_sector, top_weight = max(usable_rows, key=lambda row: row[1])
    top_share = top_weight / total
    if top_share < DOMINANCE_THRESHOLD:
        return None, "unavailable"  # AC6/AC7: genuinely diversified/mixed-theme -- never "Broad Market"

    if not top_sector:
        return None, "unavailable"

    mapped_sector = _NORMALIZED_ETF_SECTOR_TAXONOMY_MAP.get(top_sector.strip().casefold())
    if mapped_sector is None:
        return None, "unavailable"  # AC8: unmapped bucket, e.g. "Cash & Others" -- never passed through raw

    return mapped_sector, "fmp_etf_sector_weighting_confirmed"
