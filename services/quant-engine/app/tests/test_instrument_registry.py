"""Sector-classification regression tests for the InstrumentRegistry.

Pins the contract that common US-listed ETFs map to their canonical sector
labels, NOT to "Other". Originally added after a bug where importing VTI
(Vanguard Total Stock Market) via the Freedom24 PDF parser landed VTI in
the "Other" sector because:
  (a) The ticker wasn't in INSTRUMENT_DEFINITIONS, and
  (b) The Freedom24 description is just the bare ticker string, which has
      no "ETF" / "UCITS" / "ETC" substring for the description-based
      fallback in `classify_imported_instrument` to detect.
"""
from __future__ import annotations

import pytest

from app.instruments.registry import InstrumentRegistry


@pytest.mark.parametrize(
    "symbol,expected_sector",
    [
        # Broad-market US equity ETFs
        ("VTI", "Broad Market"),
        ("SPY", "Broad Market"),
        ("VOO", "Broad Market"),
        ("IVV", "Broad Market"),
        ("VT",  "Broad Market"),
        ("VEA", "Broad Market"),
        ("VWO", "Broad Market"),
        # UCITS sibling already in registry — confirms we didn't regress it
        ("VUAA", "Broad Market"),
        # Sector / thematic ETFs that are commonly held + used as benchmarks
        ("QQQ", "Technology"),
        ("GLD", "Commodities"),
        ("SLV", "Commodities"),
        ("IEF", "Fixed Income"),
        ("TLT", "Fixed Income"),
        ("AGG", "Fixed Income"),
        ("BND", "Fixed Income"),
    ],
)
def test_common_us_etfs_map_to_canonical_sector(symbol: str, expected_sector: str) -> None:
    registry = InstrumentRegistry()
    assert registry.get_sector(symbol) == expected_sector


def test_unknown_symbol_falls_back_to_other() -> None:
    """Sanity check: the "Other" fallback still works for unknown tickers.
    Prevents regression where every symbol matches something by accident."""
    registry = InstrumentRegistry()
    assert registry.get_sector("UNKNOWN_TICKER_ZZZZ") == "Other"


def test_enriched_etf_description_round_trips_to_broad_market_sector() -> None:
    """US-14.3: pin the contract that the existing
    `classify_imported_instrument` description-based fallback correctly
    handles FMP-style company names. An unknown symbol with an enriched
    description (`description="Vanguard Total Stock Market ETF"`,
    `instrument_type="ETF"`) should classify as `sector="Broad Market"`
    via the existing description-keyword fallback — confirming that the
    enrichment + registry combination produces correct sectors for new
    tickers without needing static-registry additions."""
    from app.schemas.imports import ImportedInstrument

    registry = InstrumentRegistry()
    enriched = ImportedInstrument(
        symbol="ZZZ1",  # deliberately unknown — not in INSTRUMENT_DEFINITIONS
        description="Vanguard Total Stock Market ETF",
        instrument_type="ETF",
    )
    classified = registry.classify_imported_instrument(enriched)
    # The description path falls through to the default ETF branch
    # ("Broad Market") because none of the more specific keyword tests
    # (commodities, defense, technology, financials, healthcare, bond,
    # nasdaq-100, S&P500) match "Vanguard Total Stock Market ETF".
    assert classified.sector == "Broad Market"
