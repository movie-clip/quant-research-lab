"""Tests for the instrument identity-mismatch detector (US-19.1)."""
from __future__ import annotations

from app.schemas.imports import ImportedPortfolioSnapshot
from app.services.instrument_identity import detect_instrument_identity_mismatches


def _snap(instruments: list[dict]) -> ImportedPortfolioSnapshot:
    return ImportedPortfolioSnapshot.model_validate({
        "statement": {
            "importer": "interactive_brokers",
            "imported_at": "2026-01-01T00:00:00",
            "source_path": "/test/fixture.csv",
            "detected_format": "ib_flex_2023",
        },
        "instruments": instruments,
        "cash_balances": [],
        "positions": [],
        "ledger_entries": [],
    })


# VUAA is registry-known as "Vanguard S&P 500 UCITS ETF".

def test_disjoint_description_flags_mismatch():
    snap = _snap([{"symbol": "VUAA", "description": "iShares Core MSCI World UCITS ETF"}])
    out = detect_instrument_identity_mismatches(snap)
    assert len(out) == 1
    assert out[0].symbol == "VUAA"
    assert "iShares Core MSCI World" in out[0].statement_description
    assert "Vanguard" in out[0].registry_name


def test_different_issuer_flags_mismatch():
    # DFND-style: same registry entry, a different-issuer description → disjoint.
    snap = _snap([{"symbol": "VUAA", "description": "VanEck Defense UCITS ETF"}])
    assert len(detect_instrument_identity_mismatches(snap)) == 1


def test_formatting_variant_does_not_flag():
    snap = _snap([{"symbol": "VUAA", "description": "VANGUARD S&P 500 UCITS ETF USD ACC"}])
    assert detect_instrument_identity_mismatches(snap) == []


def test_unknown_symbol_is_skipped():
    snap = _snap([{"symbol": "ZZZZ", "description": "Some Totally Different Fund Name"}])
    assert detect_instrument_identity_mismatches(snap) == []


def test_ticker_only_description_is_skipped():
    snap = _snap([{"symbol": "VUAA", "description": "VUAA"}])
    assert detect_instrument_identity_mismatches(snap) == []


def test_missing_description_is_skipped():
    snap = _snap([{"symbol": "VUAA", "description": None}])
    assert detect_instrument_identity_mismatches(snap) == []
