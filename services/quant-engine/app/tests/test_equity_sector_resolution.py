"""Unit tests for `resolve_equity_sector` (US-37.1, T-37.1.4).

Direct tests of the identity-gated FMP sector resolution logic in
isolation, using `app.tests.fixtures.FakeMarketData` (US-37.2, T-37.2.3):
`resolve_equity_sector`'s `market_data` parameter is duck-typed (anything
exposing `get_company_profile(symbol)`), so a tiny fake stands in for the
real `MarketDataService` rather than a mock of the whole class.

Covers AC3-AC8 of US-37.1 directly against the resolver; AC1/AC2/AC10 (the
registry wiring around this function) are covered in
`test_instrument_registry.py`, and AC9 (aggregation disclosure) in
`test_analytics.py`.
"""
from __future__ import annotations

import pytest

from app.instruments.equity_sector_resolution import (
    SECTOR_TAXONOMY_MAP,
    resolve_equity_sector,
)
from app.schemas.imports import ImportedInstrument
from app.tests.fixtures import FakeMarketData as _FakeMarketData


def _imported(symbol: str = "XYZ1", isin: str | None = "US0378331005") -> ImportedInstrument:
    return ImportedInstrument(symbol=symbol, isin=isin)


# ── AC3: FMP + ISIN-match success ────────────────────────────────────────────


def test_isin_match_resolves_mapped_taxonomy_sector() -> None:
    imported = _imported(isin="US0378331005")
    market_data = _FakeMarketData(responses={
        "XYZ1": {"sector": "Technology", "isin": "US0378331005"},
    })

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector == "Technology"
    assert source == "fmp_identity_confirmed"


def test_isin_match_is_case_and_whitespace_insensitive() -> None:
    """normalize_isin uppercases + strips both sides before comparing —
    reused from instrument_identity.py, not a second implementation."""
    imported = _imported(isin=" us0378331005 ")
    market_data = _FakeMarketData(responses={
        "XYZ1": {"sector": "Technology", "isin": "US0378331005"},
    })

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector == "Technology"
    assert source == "fmp_identity_confirmed"


def test_isin_match_maps_a_divergent_fmp_sector_string() -> None:
    """AC3 + AC7 combined: the identity-confirmed path also goes through
    the taxonomy map, so a divergent FMP string still resolves to the
    project's canonical sector, not the raw FMP value."""
    imported = _imported(isin="US0378331005")
    market_data = _FakeMarketData(responses={
        "XYZ1": {"sector": "Healthcare", "isin": "US0378331005"},
    })

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector == "Health Care"
    assert source == "fmp_identity_confirmed"


# ── AC4: ISIN mismatch — no classification, not the FMP value ───────────────


def test_isin_mismatch_yields_no_classification_not_the_fmp_value() -> None:
    imported = _imported(isin="US0378331005")
    market_data = _FakeMarketData(responses={
        "XYZ1": {"sector": "Technology", "isin": "US9999999999"},
    })

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


# ── AC5: missing ISIN evidence on either side (the conservative default) ────


@pytest.mark.parametrize(
    "statement_isin,profile_isin",
    [
        pytest.param(None, "US0378331005", id="statement-missing"),
        pytest.param("US0378331005", None, id="profile-missing"),
        pytest.param(None, None, id="both-missing"),
        pytest.param("", "", id="both-blank-string"),
    ],
)
def test_missing_isin_evidence_either_side_yields_no_classification(
    statement_isin: str | None, profile_isin: str | None,
) -> None:
    imported = _imported(isin=statement_isin)
    market_data = _FakeMarketData(responses={
        "XYZ1": {"sector": "Technology", "isin": profile_isin},
    })

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


# ── FMP-no-coverage (AC8-adjacent: empty/None profile) ───────────────────────


def test_none_profile_yields_no_classification() -> None:
    imported = _imported()
    market_data = _FakeMarketData(responses={"XYZ1": None})

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


def test_empty_profile_dict_yields_no_classification() -> None:
    imported = _imported()
    market_data = _FakeMarketData(responses={"XYZ1": {}})

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


def test_profile_missing_sector_key_yields_no_classification() -> None:
    imported = _imported()
    market_data = _FakeMarketData(responses={"XYZ1": {"isin": "US0378331005"}})

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


def test_profile_empty_sector_string_yields_no_classification() -> None:
    imported = _imported()
    market_data = _FakeMarketData(responses={"XYZ1": {"sector": "", "isin": "US0378331005"}})

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


# ── AC6: FMP sector string absent from the taxonomy map ─────────────────────


def test_unmapped_fmp_sector_string_never_passed_through_raw() -> None:
    imported = _imported(isin="US0378331005")
    market_data = _FakeMarketData(responses={
        "XYZ1": {"sector": "Some Brand New GICS Bucket", "isin": "US0378331005"},
    })

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert sector != "Some Brand New GICS Bucket"
    assert source == "unavailable"


# ── AC8: FMP lookup raises — swallowed, no crash ─────────────────────────────


def test_fmp_exception_is_swallowed_not_propagated() -> None:
    imported = _imported()
    market_data = _FakeMarketData(raise_for={"XYZ1"})

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


def test_fmp_exception_does_not_short_circuit_other_symbols() -> None:
    """Sanity: the fail-safe is per-call, not global — a second symbol on
    the same market_data instance still resolves normally."""
    market_data = _FakeMarketData(
        responses={"OK1": {"sector": "Energy", "isin": "US1111111111"}},
        raise_for={"BAD1"},
    )

    bad_sector, bad_source = resolve_equity_sector(_imported(symbol="BAD1", isin="US1111111111"), market_data)
    ok_sector, ok_source = resolve_equity_sector(_imported(symbol="OK1", isin="US1111111111"), market_data)

    assert (bad_sector, bad_source) == (None, "unavailable")
    assert (ok_sector, ok_source) == ("Energy", "fmp_identity_confirmed")


# ── AC7: dedicated taxonomy-mapping regression ───────────────────────────────
#
# Pins all 11 GICS-style sectors the research brief verified live against
# FMP (02-quant-research.md § Sector taxonomy normalization), including the
# 5 confirmed-divergent pairs. A future FMP naming drift on any of these
# fails THIS test, not a silently-fragmented sector bucket downstream.


@pytest.mark.parametrize(
    "fmp_sector,project_sector",
    [
        # Confirmed-divergent pairs (AC7) — the 5 this story exists for.
        pytest.param("Healthcare", "Health Care", id="healthcare-divergent"),
        pytest.param("Financial Services", "Financials", id="financials-divergent"),
        pytest.param("Consumer Cyclical", "Consumer Discretionary", id="consumer-discretionary-divergent"),
        pytest.param("Consumer Defensive", "Consumer Staples", id="consumer-staples-divergent"),
        pytest.param("Basic Materials", "Materials", id="materials-divergent"),
        # Exact-match sectors — confirmed live, round-trip unchanged.
        pytest.param("Technology", "Technology", id="technology-exact"),
        pytest.param("Energy", "Energy", id="energy-exact"),
        pytest.param("Industrials", "Industrials", id="industrials-exact"),
        pytest.param("Real Estate", "Real Estate", id="real-estate-exact"),
        pytest.param("Utilities", "Utilities", id="utilities-exact"),
        pytest.param("Communication Services", "Communication Services", id="communication-services-exact"),
    ],
)
def test_sector_taxonomy_map_pins_all_eleven_verified_sectors(fmp_sector: str, project_sector: str) -> None:
    assert SECTOR_TAXONOMY_MAP[fmp_sector] == project_sector


def test_sector_taxonomy_map_covers_at_least_the_eleven_verified_sectors() -> None:
    """AC7's own wording is "at minimum" — this is a containment check, not
    a closed-set pin, so a future addition to the map does not break it."""
    verified_fmp_sectors = {
        "Healthcare", "Financial Services", "Consumer Cyclical", "Consumer Defensive",
        "Basic Materials", "Technology", "Energy", "Industrials", "Real Estate",
        "Utilities", "Communication Services",
    }
    assert verified_fmp_sectors <= SECTOR_TAXONOMY_MAP.keys()


# ── AC1/AC2 (US-37.2, T-37.2.4): taxonomy normalization regression ──────────
#
# Pins the fix for FINDING 2 (02-quant-research.md / 10-quant-audit.md,
# 2026-08-21-dynamic-sector-classification run): a case/whitespace variant of
# a known SECTOR_TAXONOMY_MAP key must resolve identically to the exact-case
# key (AC1), and normalization must not widen what counts as "mapped" — a
# genuinely unknown sector string still degrades to unavailable (AC2).


@pytest.mark.parametrize(
    "fmp_sector",
    [
        pytest.param("TECHNOLOGY", id="all-caps"),
        pytest.param(" Technology", id="leading-whitespace"),
        pytest.param("Technology ", id="trailing-whitespace"),
        pytest.param("technology", id="lowercase"),
        pytest.param(" technology ", id="lowercase-and-whitespace"),
    ],
)
def test_casing_and_whitespace_variant_resolves_same_as_exact_key(fmp_sector: str) -> None:
    """AC1 — the four variants FINDING 2 reproduced against "Technology",
    plus a combined case+whitespace variant, all resolve to the exact-case
    key's mapped sector rather than falling through to unavailable."""
    imported = _imported(isin="US0378331005")
    market_data = _FakeMarketData(responses={
        "XYZ1": {"sector": fmp_sector, "isin": "US0378331005"},
    })

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector == SECTOR_TAXONOMY_MAP["Technology"]
    assert source == "fmp_identity_confirmed"


def test_genuinely_unmapped_sector_still_falls_through_after_normalization() -> None:
    """AC2 — normalization narrows what counts as unmapped, it does not
    widen what counts as mapped: a sector string that is not a
    casing/whitespace variant of any known taxonomy key still resolves to
    unavailable, even when it carries whitespace/casing of its own."""
    imported = _imported(isin="US0378331005")
    market_data = _FakeMarketData(responses={
        "XYZ1": {"sector": "  Some Brand New GICS Bucket  ", "isin": "US0378331005"},
    })

    sector, source = resolve_equity_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"
