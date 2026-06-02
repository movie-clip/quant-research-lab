"""Unit tests for `enrich_imported_instruments`.

Tests the helper in isolation: the `market_data` argument is duck-typed
so we pass a tiny mock object instead of a real `MarketDataService`.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from app.schemas.imports import (
    ImportedInstrument,
    ImportedPortfolioSnapshot,
    ImportedStatement,
)
from app.services.instrument_enrichment import enrich_imported_instruments


# ── Fixture helpers ─────────────────────────────────────────────────────────


class _FakeMarketData:
    """Records every get_company_profile call + returns a configurable
    response per symbol. `responses[symbol] = dict | None`."""

    def __init__(self, responses: dict[str, Any] | None = None, raise_for: set[str] | None = None) -> None:
        self.responses = responses or {}
        self.raise_for = raise_for or set()
        self.calls: list[str] = []

    def get_company_profile(self, symbol: str) -> dict[str, Any] | None:
        self.calls.append(symbol)
        if symbol in self.raise_for:
            raise RuntimeError(f"FMP boom for {symbol}")
        return self.responses.get(symbol)


def _make_snapshot(*instruments: ImportedInstrument) -> ImportedPortfolioSnapshot:
    """Build a minimal `ImportedPortfolioSnapshot` with only the instruments
    populated (positions / cash / ledger empty). Sufficient for testing the
    enrichment walk."""
    statement = ImportedStatement(
        importer="freedom24",
        imported_at=datetime(2026, 6, 1),
        source_path="/test/fixture.pdf",
        detected_format="pdf",
        account_id="test",
        base_currency="USD",
        statement_period="2026-01-01 - 2026-06-01",
        page_count=1,
    )
    return ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=None,
        instruments=list(instruments),
        cash_balances=[],
        positions=[],
        ledger_entries=[],
    )


# ── Tests ───────────────────────────────────────────────────────────────────


def test_enrich_skips_known_symbols_in_static_registry() -> None:
    """Fast-path: VTI is in INSTRUMENT_DEFINITIONS (added in cf30cfc) so
    `get_company_profile` must NOT be called for it. The unknown symbol
    DOES get the FMP call."""
    snapshot = _make_snapshot(
        ImportedInstrument(symbol="VTI", description="VTI"),
        ImportedInstrument(symbol="UNKW", description="UNKW"),
    )
    market_data = _FakeMarketData(responses={
        "UNKW": {"companyName": "Unknown Corp", "isEtf": False},
    })

    result = enrich_imported_instruments(snapshot, market_data)

    assert "VTI" not in market_data.calls
    assert "UNKW" in market_data.calls
    # Sanity: VTI instrument preserved verbatim.
    vti = next(i for i in result.instruments if i.symbol == "VTI")
    assert vti.description == "VTI"


def test_enrich_fetches_fmp_for_unknown_symbol_with_bare_ticker_description() -> None:
    snapshot = _make_snapshot(
        ImportedInstrument(symbol="XYZW", description="XYZW"),
    )
    market_data = _FakeMarketData(responses={
        "XYZW": {"companyName": "XYZ World Corp", "sector": "Technology", "isEtf": False},
    })

    result = enrich_imported_instruments(snapshot, market_data)

    enriched = result.instruments[0]
    assert enriched.symbol == "XYZW"
    assert enriched.description == "XYZ World Corp"
    assert enriched.instrument_type == "STOCK"


def test_enrich_fetches_fmp_and_classifies_etf_when_isEtf_true() -> None:
    snapshot = _make_snapshot(
        ImportedInstrument(symbol="XYZE", description="XYZE"),
    )
    market_data = _FakeMarketData(responses={
        "XYZE": {"companyName": "Vanguard Some Fund", "sector": "Broad Market", "isEtf": True},
    })

    result = enrich_imported_instruments(snapshot, market_data)

    enriched = result.instruments[0]
    assert enriched.description == "Vanguard Some Fund"
    assert enriched.instrument_type == "ETF"


def test_enrich_skips_when_description_already_non_trivial() -> None:
    """A multi-word description (with whitespace + lowercase) is
    non-trivial — the description-based fallback can handle it. No FMP
    call needed."""
    snapshot = _make_snapshot(
        ImportedInstrument(symbol="AAPL", description="Apple Inc"),
    )
    market_data = _FakeMarketData()

    result = enrich_imported_instruments(snapshot, market_data)

    assert "AAPL" not in market_data.calls
    # Original preserved verbatim.
    assert result.instruments[0].description == "Apple Inc"


def test_enrich_handles_fmp_returning_none_gracefully() -> None:
    """When FMP returns None (no profile available), the original
    instrument is preserved verbatim. No exception, no mutation."""
    snapshot = _make_snapshot(
        ImportedInstrument(symbol="GHST", description="GHST", instrument_type=""),
    )
    market_data = _FakeMarketData(responses={"GHST": None})

    result = enrich_imported_instruments(snapshot, market_data)

    enriched = result.instruments[0]
    assert enriched.symbol == "GHST"
    assert enriched.description == "GHST"
    assert (enriched.instrument_type or "") == ""


def test_enrich_handles_fmp_raising_gracefully() -> None:
    """When FMP raises (e.g. network outage), the original instrument is
    preserved. No exception propagates."""
    snapshot = _make_snapshot(
        ImportedInstrument(symbol="ERR", description="ERR"),
    )
    market_data = _FakeMarketData(raise_for={"ERR"})

    result = enrich_imported_instruments(snapshot, market_data)

    assert result.instruments[0].description == "ERR"


def test_enrich_preserves_existing_explicit_instrument_type_when_fmp_says_not_etf() -> None:
    """Asymmetric type contract: when the parser explicitly set
    instrument_type='STOCK' (non-empty), and FMP says isEtf=False, we
    preserve the parser's value. FMP only upgrades on isEtf=True."""
    snapshot = _make_snapshot(
        ImportedInstrument(symbol="ABCD", description="ABCD", instrument_type="STOCK"),
    )
    market_data = _FakeMarketData(responses={
        "ABCD": {"companyName": "ABC Defense Inc", "isEtf": False},
    })

    result = enrich_imported_instruments(snapshot, market_data)

    enriched = result.instruments[0]
    assert enriched.description == "ABC Defense Inc"
    assert enriched.instrument_type == "STOCK"  # parser's STOCK preserved
