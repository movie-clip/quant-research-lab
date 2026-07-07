"""Integration tests for Freedom24 import + FMP enrichment wire-up.

The Freedom24 parser at `app.importers.freedom24.import_statement` was
extended in US-14.3 to call `enrich_imported_instruments` after
constructing the `ImportedPortfolioSnapshot`. These tests verify the
wire-up:

1. Construction-failure fail-graceful: when `MarketDataService()` raises
   on construction, the import still returns a valid snapshot with the
   original (un-enriched) instruments.

2. FMP-call fail-graceful: when `get_company_profile` raises during
   enrichment, ditto.

3. Fast-path skip for known symbols: the bundled FF2026.pdf fixture
   only contains VTI, which is in the static `INSTRUMENT_DEFINITIONS`
   after commit `cf30cfc`. The enrichment should run but skip the FMP
   call for VTI — verified by patching the MarketDataService class so
   `get_company_profile` is observable.

Patch target: `app.services.market_data.MarketDataService` (the source
module). The Freedom24 parser imports `MarketDataService` lazily inside
the `import_statement` try/except block, so the source-module binding is
the only one we can intercept.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.importers.freedom24 import import_statement as import_freedom24_statement


# Path to the bundled Freedom24 fixture PDF — repo-relative, matching
# test_importer.py's existing Freedom24 tests.
_DOCS_DIR = Path(__file__).resolve().parents[4] / "docs"
_FF2026_PATH = _DOCS_DIR / "FF2026.pdf"

pytestmark = pytest.mark.skipif(
    not _FF2026_PATH.exists(),
    reason="FF2026.pdf fixture missing — Freedom24 enrichment tests require it",
)


def test_freedom24_import_skips_fmp_for_known_static_registry_symbol_vti() -> None:
    """The bundled FF2026.pdf fixture contains VTI, which is in
    INSTRUMENT_DEFINITIONS. The enrichment wire-up should construct a
    MarketDataService but skip the FMP call for VTI (fast path).
    Confirms the wire-up is reachable without making an unnecessary
    network call for a known symbol."""
    mock_md_class = MagicMock()
    mock_md_instance = MagicMock()
    mock_md_instance.get_company_profile.return_value = {
        "companyName": "Should Not Be Used",
        "isEtf": True,
    }
    mock_md_class.return_value = mock_md_instance

    with patch("app.services.market_data.MarketDataService", mock_md_class):
        snapshot = import_freedom24_statement(_FF2026_PATH)

    # MarketDataService WAS constructed (proves wire-up is reachable).
    assert mock_md_class.call_count == 1
    # But get_company_profile was NOT called for VTI — fast-path skip.
    profile_calls = [args[0] for (args, _kwargs) in mock_md_instance.get_company_profile.call_args_list]
    assert "VTI" not in profile_calls
    # Snapshot is still well-formed.
    assert any(instrument.symbol == "VTI" for instrument in snapshot.instruments)


def test_freedom24_import_handles_market_data_construction_failure_gracefully() -> None:
    """If MarketDataService() raises on construction (no API key, FMP
    unavailable, etc.), the import flow must NOT fail. The snapshot is
    returned with un-enriched instruments."""
    mock_md_class = MagicMock(side_effect=RuntimeError("FMP unavailable"))

    with patch("app.services.market_data.MarketDataService", mock_md_class):
        snapshot = import_freedom24_statement(_FF2026_PATH)

    # Import still succeeded
    assert snapshot is not None
    assert snapshot.statement.importer == "freedom24"
    # Instruments are present (un-enriched). VTI was parsed with its
    # original bare-ticker description.
    vti = next((i for i in snapshot.instruments if i.symbol == "VTI"), None)
    assert vti is not None


def test_freedom24_import_handles_fmp_call_failure_gracefully() -> None:
    """If get_company_profile raises during enrichment, the import flow
    must still succeed. (Note: in the FF2026 fixture all instruments are
    in the static registry, so this path is only reached if enrich_one
    runs into the slow path for some symbol — but the import-level
    try/except is the outer safety net regardless.)"""
    mock_md_class = MagicMock()
    mock_md_instance = MagicMock()
    mock_md_instance.get_company_profile.side_effect = RuntimeError("FMP timeout")
    mock_md_class.return_value = mock_md_instance

    with patch("app.services.market_data.MarketDataService", mock_md_class):
        snapshot = import_freedom24_statement(_FF2026_PATH)

    # Import still succeeded; snapshot well-formed.
    assert snapshot is not None
    assert any(instrument.symbol == "VTI" for instrument in snapshot.instruments)
