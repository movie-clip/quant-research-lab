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


# ── US-19.2: ISIN evidence (registry VUAA isin = IE00BFMXXD54) ──────────────

def test_isin_mismatch_flags_with_both_isins():
    snap = _snap([{
        "symbol": "VUAA",
        "description": "VANGUARD S&P 500 UCITS ETF USD ACC",  # description agrees
        "isin": "IE000YYE6WK5",  # but the ISIN is a different fund's
    }])
    out = detect_instrument_identity_mismatches(snap)
    assert len(out) == 1
    assert out[0].kind == "isin"
    assert out[0].statement_isin == "IE000YYE6WK5"
    assert out[0].expected_isin == "IE00BFMXXD54"


def test_matching_isin_is_not_flagged_case_and_whitespace_insensitive():
    snap = _snap([{
        "symbol": "VUAA",
        "description": "VANGUARD S&P 500 UCITS ETF USD ACC",
        "isin": "  ie00bfmxxd54 ",
    }])
    assert detect_instrument_identity_mismatches(snap) == []


def test_registry_entry_without_seeded_isin_is_skipped():
    # AAPL is registry-known but has no seeded ISIN → evidence-gated skip.
    snap = _snap([{"symbol": "AAPL", "description": "APPLE INC", "isin": "US0378331005"}])
    assert detect_instrument_identity_mismatches(snap) == []


def test_statement_without_isin_is_skipped():
    snap = _snap([{"symbol": "VUAA", "description": "VANGUARD S&P 500 UCITS ETF USD ACC", "isin": None}])
    assert detect_instrument_identity_mismatches(snap) == []


def test_isin_catches_mismatch_the_description_heuristic_misses():
    # The heuristic's blind spot: two different funds sharing identity tokens
    # ("iShares … Defence/Defense"). DFND registry name shares tokens with this
    # description, so the description check passes — only the ISIN catches it.
    snap = _snap([{
        "symbol": "DFND",
        "description": "ISHARES DEFENSE INNOVATION UCITS",  # shares iShares+Defence tokens
        "isin": "IE000YYE6WK5",  # VanEck Defense — NOT the registry's IE000U9ODG19
    }])
    out = detect_instrument_identity_mismatches(snap)
    assert [m.kind for m in out] == ["isin"]
    assert out[0].expected_isin == "IE000U9ODG19"
