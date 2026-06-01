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
