"""US-19.2 — registry ISIN seeds must agree with the committed real statements.

The registry's `isin` values are *sourced from* the broker statements (the
product's broker-truth identity evidence). This guard imports the committed
statements and asserts every seeded ISIN equals the ISIN the statement actually
carries for that symbol — so a typo'd or stale seed can never silently pass,
and re-importing the real statements yields zero ISIN identity warnings.
"""
from __future__ import annotations

from pathlib import Path

from app.instruments.registry import INSTRUMENT_DEFINITIONS, InstrumentRegistry
from app.services.instrument_identity import detect_instrument_identity_mismatches
from app.services.statement_importer import import_statements


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def test_seeded_registry_isins_match_committed_statements() -> None:
    registry = InstrumentRegistry()
    docs = _repo_root() / "docs"
    statement_isins: dict[str, str] = {}
    for name in ("IB2026.csv", "FF2026.pdf"):
        snapshot = import_statements([str(docs / name)])
        for instrument in snapshot.instruments:
            if instrument.isin:
                statement_isins[registry.normalize_symbol(instrument.symbol)] = instrument.isin.strip().upper()

    seeded = {
        symbol: entry.isin.strip().upper()
        for symbol, entry in INSTRUMENT_DEFINITIONS.items()
        if entry.isin
    }
    assert seeded, "expected at least one seeded registry ISIN (US-19.2)"

    mismatched = {
        symbol: (isin, statement_isins[symbol])
        for symbol, isin in seeded.items()
        if symbol in statement_isins and isin != statement_isins[symbol]
    }
    assert mismatched == {}, f"registry ISIN seeds drifted from statement evidence: {mismatched}"

    # And the user-facing consequence: re-importing the real statements raises
    # zero ISIN identity warnings (no false positives on true data).
    for name in ("IB2026.csv", "FF2026.pdf"):
        snapshot = import_statements([str(docs / name)])
        isin_warnings = [m for m in detect_instrument_identity_mismatches(snapshot) if m.kind == "isin"]
        assert isin_warnings == [], f"{name}: unexpected ISIN warnings: {isin_warnings}"
