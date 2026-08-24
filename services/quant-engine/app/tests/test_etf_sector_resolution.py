"""Unit tests for `resolve_etf_sector` (US-39.1, T-39.1.6).

Direct tests of the identity-gated, dominance-thresholded FMP sector
resolution logic for direct-held ETFs, in isolation, using
`app.tests.fixtures.FakeMarketData` (extended US-39.1 to also serve
`get_etf_sector_weightings`): `resolve_etf_sector`'s `market_data`
parameter is duck-typed (anything exposing `get_company_profile(symbol)`
and `get_etf_sector_weightings(symbol)`), so a tiny fake stands in for the
real `MarketDataService`.

Covers AC3-AC10 of US-39.1 directly against the resolver; AC1/AC2 (the
registry wiring around this function) are covered in
`test_instrument_registry.py`, and AC11 (aggregation disclosure) in
`test_analytics.py`.
"""
from __future__ import annotations

import pytest

from app.instruments.etf_sector_resolution import (
    DOMINANCE_THRESHOLD,
    resolve_etf_sector,
)
from app.schemas.imports import ImportedInstrument
from app.tests.fixtures import FakeMarketData as _FakeMarketData

# SBIO's real, live-verified ISIN pair (docs/product/stories/US-39.1-.../
# Context "The SBIO ticker-collision case"): the statement's actual holding
# (Invesco NASDAQ Biotech UCITS ETF, LSE) vs. the DIFFERENT US-listed
# security FMP's bare "SBIO" ticker resolves to (ALPS Medical Breakthroughs
# ETF) — two distinct funds that merely share a bare ticker string.
SBIO_STATEMENT_ISIN = "IE00BQ70R696"
SBIO_WRONG_FUND_ISIN = "US00162Q5936"


def _imported(symbol: str = "XYZ1", isin: str | None = "IE00BQ70R696") -> ImportedInstrument:
    return ImportedInstrument(symbol=symbol, isin=isin)


def _weights(*pairs: tuple[str, float]) -> list[dict]:
    return [{"sector": sector, "weightPercentage": weight} for sector, weight in pairs]


# ── Identity-match + above-threshold success ─────────────────────────────────


def test_isin_match_and_dominant_sector_resolves_mapped_taxonomy_sector() -> None:
    imported = _imported(isin="IE00BQ70R696")
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00BQ70R696"}},
        sector_weightings={"XYZ1": _weights(("Healthcare", 98.0), ("Cash & Others", 2.0))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector == "Health Care"
    assert source == "fmp_etf_sector_weighting_confirmed"


# ── SBIO-collision-prevented case, specifically (AC4) ────────────────────────


def test_sbio_bare_ticker_wrong_security_is_rejected_before_weights_fetch() -> None:
    """The bare "SBIO" candidate resolves, on FMP, to a DIFFERENT security
    (confirmed live). The identity gate must reject it on ISIN mismatch —
    and, since the gate runs before the weights fetch, must never even call
    get_etf_sector_weightings for the wrong security."""
    imported = ImportedInstrument(symbol="SBIO", isin=SBIO_STATEMENT_ISIN)
    market_data = _FakeMarketData(
        responses={"SBIO": {"isin": SBIO_WRONG_FUND_ISIN}},
        sector_weightings={"SBIO": _weights(("Healthcare", 100.0))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"
    assert market_data.weightings_calls == []


# ── ISIN mismatch (generic) ──────────────────────────────────────────────────


def test_isin_mismatch_yields_no_classification_not_the_fmp_value() -> None:
    imported = _imported(isin="IE00BQ70R696")
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00SOMEOTHER1"}},
        sector_weightings={"XYZ1": _weights(("Healthcare", 98.0))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"
    assert market_data.weightings_calls == []


# ── No-ISIN-evidence (either side) ───────────────────────────────────────────


@pytest.mark.parametrize(
    "statement_isin,profile_isin",
    [
        pytest.param(None, "IE00BQ70R696", id="statement-missing"),
        pytest.param("IE00BQ70R696", None, id="profile-missing"),
        pytest.param(None, None, id="both-missing"),
        pytest.param("", "", id="both-blank-string"),
    ],
)
def test_missing_isin_evidence_either_side_yields_no_classification(
    statement_isin: str | None, profile_isin: str | None,
) -> None:
    imported = _imported(isin=statement_isin)
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": profile_isin}},
        sector_weightings={"XYZ1": _weights(("Healthcare", 98.0))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


# ── Dominance-threshold pass / fail (AC6, AC7) ───────────────────────────────


def test_dominance_threshold_pass_at_exactly_the_threshold() -> None:
    imported = _imported()
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00BQ70R696"}},
        sector_weightings={"XYZ1": _weights(("Healthcare", 55.0), ("Technology", 45.0))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector == "Health Care"
    assert source == "fmp_etf_sector_weighting_confirmed"


def test_dominance_threshold_pass_just_above_the_threshold() -> None:
    imported = _imported()
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00BQ70R696"}},
        sector_weightings={"XYZ1": _weights(("Healthcare", 55.1), ("Technology", 44.9))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector == "Health Care"
    assert source == "fmp_etf_sector_weighting_confirmed"


def test_dominance_threshold_fail_just_below_the_threshold_never_broad_market() -> None:
    """AC7: a below-threshold dynamic result never defaults to "Broad
    Market" — the outcome is the same "no classification" state as every
    other failure mode."""
    imported = _imported()
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00BQ70R696"}},
        sector_weightings={"XYZ1": _weights(("Healthcare", 54.9), ("Technology", 45.1))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert sector != "Broad Market"
    assert source == "unavailable"


def test_dominance_threshold_constant_is_fifty_five_percent() -> None:
    assert DOMINANCE_THRESHOLD == 0.55


# ── Unmapped sector bucket (AC8) ──────────────────────────────────────────────


def test_unmapped_top_sector_bucket_never_passed_through_raw() -> None:
    imported = _imported()
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00BQ70R696"}},
        sector_weightings={"XYZ1": _weights(("Cash & Others", 99.0), ("Technology", 1.0))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert sector != "Cash & Others"
    assert source == "unavailable"


# ── Empty weights list / zero-total-weight (AC9) ──────────────────────────────


def test_empty_weights_list_yields_no_classification() -> None:
    imported = _imported()
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00BQ70R696"}},
        sector_weightings={"XYZ1": []},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


def test_no_coverage_symbol_yields_no_classification() -> None:
    """A nonexistent/non-ETF/uncovered symbol: the fake's default (no
    `sector_weightings` entry) already returns []."""
    imported = _imported()
    market_data = _FakeMarketData(responses={"XYZ1": {"isin": "IE00BQ70R696"}})

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


def test_zero_total_weight_yields_no_classification() -> None:
    imported = _imported()
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00BQ70R696"}},
        sector_weightings={"XYZ1": _weights(("Healthcare", 0.0), ("Technology", 0.0))},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"


# ── Lookup exceptions — two distinct network calls (AC10) ────────────────────


def test_get_company_profile_exception_is_swallowed_not_propagated() -> None:
    imported = _imported()
    market_data = _FakeMarketData(raise_for={"XYZ1"})

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"
    assert market_data.weightings_calls == []


def test_get_etf_sector_weightings_exception_is_swallowed_not_propagated() -> None:
    """A second, distinct exception surface from get_company_profile's own
    — the identity gate must have already cleared for this call to be
    reached at all."""
    imported = _imported()
    market_data = _FakeMarketData(
        responses={"XYZ1": {"isin": "IE00BQ70R696"}},
        raise_for_weightings={"XYZ1"},
    )

    sector, source = resolve_etf_sector(imported, market_data)

    assert sector is None
    assert source == "unavailable"
    assert market_data.weightings_calls == ["XYZ1"]
