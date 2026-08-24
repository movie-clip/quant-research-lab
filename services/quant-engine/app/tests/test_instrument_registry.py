"""Sector-classification regression tests for the InstrumentRegistry.

Pins the contract that common US-listed ETFs map to their canonical sector
labels, NOT to "Other". Originally added after a bug where importing VTI
(Vanguard Total Stock Market) via the Freedom24 PDF parser landed VTI in
the "Other" sector because:
  (a) The ticker wasn't in INSTRUMENT_DEFINITIONS, and
  (b) The Freedom24 description is just the bare ticker string, which has
      no "ETF" / "UCITS" / "ETC" substring for the description-based
      fallback in `classify_imported_instrument` to detect.

US-37.1 (T-37.1.4) additions below cover the identity-gated equity-branch
FMP resolution's wiring through `classify_imported_instrument` /
`attach_snapshot_metadata` — AC1 (static fast path), AC2 (equity branch
delegates to `resolve_equity_sector`), AC10 (ETF branch + static-registry
equities unaffected). The resolver's own logic (AC3-AC8) is covered in
`test_equity_sector_resolution.py`; aggregation disclosure (AC9) in
`test_analytics.py`.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from app.instruments.registry import InstrumentRegistry
from app.schemas.imports import (
    ImportedInstrument,
    ImportedPortfolioSnapshot,
    ImportedPosition,
    ImportedStatement,
)
from app.tests.fixtures import FakeMarketData as _SpyMarketData

# `_SpyMarketData()` (no `profile` kwarg) is only ever used where the code
# path under test never reaches `get_company_profile` at all (asserted via
# `market_data.calls == []`) — the static-registry fast path and the ETF
# branch both ignore `market_data` entirely. So `FakeMarketData`'s `profile`
# default of `None` (vs. the old `_SpyMarketData`'s fixed default profile)
# is never actually observed by any test in this file; see
# `app.tests.fixtures.DEFAULT_COMPANY_PROFILE` for that default should a
# future no-arg-and-called test need it explicitly.


def _statement(**overrides: Any) -> ImportedStatement:
    base = dict(
        importer="interactive_brokers",
        imported_at=datetime(2026, 1, 1),
        source_path="sample.csv",
        detected_format="csv",
        account_id="U123",
        base_currency="USD",
        statement_period="2026",
        page_count=1,
    )
    base.update(overrides)
    return ImportedStatement(**base)


def _one_position_snapshot(symbol: str, *, instrument: ImportedInstrument) -> ImportedPortfolioSnapshot:
    return ImportedPortfolioSnapshot(
        statement=_statement(),
        statements=[],
        statement_totals=None,
        instruments=[instrument],
        cash_balances=[],
        positions=[
            ImportedPosition(
                as_of_date=date(2026, 1, 1), symbol=symbol, quantity=1.0,
                cost_basis=100.0, close_price=100.0, market_value=100.0,
                unrealized_pnl=0.0, currency="USD",
            ),
        ],
        ledger_entries=[],
    )


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


def test_enriched_etf_description_with_no_market_data_yields_no_classification() -> None:
    """US-39.1 rewrite of the pre-fix pin (was
    `test_enriched_etf_description_round_trips_to_broad_market_sector`,
    US-14.3): the ETF branch's keyword-substring "Broad Market" default is
    removed entirely (it asserted a fund's *intent* with no evidence behind
    it). An unknown symbol with an enriched description
    (`description="Vanguard Total Stock Market ETF"`, `instrument_type="ETF"`)
    and NO `market_data` supplied never enters the dynamic gate
    (`market_data is not None` is False), so `sector` stays the honest
    `None` — the same "no lookup attempted" outcome the equity branch
    already has for this case. `category` is unaffected: no keyword in this
    description matches any of the category elif branches, so it stays the
    plain `"ETF"` default, same as before this story."""
    registry = InstrumentRegistry()
    enriched = ImportedInstrument(
        symbol="ZZZ1",  # deliberately unknown — not in INSTRUMENT_DEFINITIONS
        description="Vanguard Total Stock Market ETF",
        instrument_type="ETF",
    )
    classified = registry.classify_imported_instrument(enriched)

    assert classified.sector is None
    assert classified.classification_source is None
    assert classified.category == "ETF"


# ── US-37.1 / T-37.1.4: identity-gated equity-branch FMP resolution wiring ──


def test_static_registry_equity_never_calls_fmp_even_when_market_data_supplied() -> None:
    """AC1: a symbol present in INSTRUMENT_DEFINITIONS never triggers
    get_company_profile, even when market_data IS supplied to
    attach_snapshot_metadata — the static-dict fast path
    (_merge_known_instrument_metadata) short-circuits before the equity
    branch of classify_imported_instrument is ever reached."""
    registry = InstrumentRegistry()
    market_data = _SpyMarketData()
    snapshot = _one_position_snapshot(
        "AAPL",
        instrument=ImportedInstrument(symbol="AAPL", isin="US0378331005"),
    )

    metadata = registry.attach_snapshot_metadata(snapshot, market_data=market_data)

    assert market_data.calls == []
    assert metadata["AAPL"].sector == "Technology"  # static registry value, unchanged
    assert metadata["AAPL"].classification_source == "static"


def test_static_registry_hit_sets_classification_source_static_with_no_other_updates() -> None:
    """_merge_known_instrument_metadata behavior change (T-37.1.1): it now
    always sets classification_source="static" on a static-dict hit, even
    when there is nothing else to merge in (no imported record, no currency
    override) — where it previously short-circuited to the SAME Instrument
    instance. Assert field equality, never object identity, per this
    project's containment / no-implicit-identity discipline."""
    registry = InstrumentRegistry()
    instrument = registry.get_instrument("AAPL")
    assert instrument is not None
    assert instrument.classification_source is None  # the raw static-dict entry itself

    merged = registry._merge_known_instrument_metadata(instrument, imported=None, currency=None)

    assert merged.classification_source == "static"
    assert merged.sector == instrument.sector
    assert merged.symbol == instrument.symbol
    assert merged.name == instrument.name


def test_etf_branch_with_market_data_attempts_dynamic_lookup_and_falls_through() -> None:
    """US-39.1 rewrite of the pre-fix pin (was
    `test_etf_branch_ignores_market_data_and_makes_no_fmp_call`): that
    test's entire premise — "the ETF branch ignores market_data entirely" —
    is exactly what this story reverses (AC2). With market_data supplied
    and no configured response, resolve_etf_sector DOES call
    get_company_profile("ZZZ2"), gets None back, and resolves to
    (None, "unavailable") — sector stays None, but the lookup was genuinely
    attempted (market_data.calls is no longer empty). category is
    unaffected: the "FINANCIAL" keyword branch still fires independently of
    sector, since category derivation was left untouched by this story."""
    registry = InstrumentRegistry()
    market_data = _SpyMarketData()
    imported = ImportedInstrument(symbol="ZZZ2", description="Some New Financial Services UCITS ETF", instrument_type="ETF")

    classified = registry.classify_imported_instrument(imported, market_data=market_data)

    assert market_data.calls == ["ZZZ2"]
    assert classified.sector is None
    assert classified.classification_source == "unavailable"
    assert classified.category == "Sector UCITS ETF"  # "FINANCIAL" keyword branch, unaffected by sector


def test_etf_branch_without_market_data_yields_no_classification_not_broad_market() -> None:
    """The case the old `..._ignores_market_data...` test's name used to
    describe: NO market_data supplied at all (the default) → the dynamic
    gate is never entered, classification_source stays None. Distinct from
    the rewrite above, which supplies market_data with no configured
    response."""
    registry = InstrumentRegistry()
    imported = ImportedInstrument(symbol="ZZZ2", description="Some New Financial Services UCITS ETF", instrument_type="ETF")

    classified = registry.classify_imported_instrument(imported)

    assert classified.sector is None
    assert classified.classification_source is None
    assert classified.category == "Sector UCITS ETF"


def test_equity_branch_without_market_data_yields_no_classification_not_other() -> None:
    """Regression / no-fabrication: an unrecognized equity with NO
    market_data supplied (the default, e.g. risk.py's two unrelated
    attach_snapshot_metadata callers) gets sector=None — honest absence,
    never the old literal "Other" sentinel string."""
    registry = InstrumentRegistry()
    imported = ImportedInstrument(symbol="ZZZ3", description="Some Unknown Equity Corp")

    classified = registry.classify_imported_instrument(imported)

    assert classified.sector is None
    assert classified.classification_source is None


def test_equity_branch_with_market_data_and_isin_match_resolves_fmp_sector() -> None:
    """AC2/AC3: classify_imported_instrument's equity branch delegates to
    resolve_equity_sector (this story's new module) when market_data is
    supplied — proving the wiring, not re-testing the resolver's own logic
    (covered directly in test_equity_sector_resolution.py)."""
    registry = InstrumentRegistry()
    market_data = _SpyMarketData(profile={"sector": "Consumer Cyclical", "isin": "US1111111111"})
    imported = ImportedInstrument(symbol="ZZZ4", description="Some Unknown Equity Corp", isin="US1111111111")

    classified = registry.classify_imported_instrument(imported, market_data=market_data)

    assert market_data.calls == ["ZZZ4"]
    assert classified.sector == "Consumer Discretionary"  # taxonomy-mapped, not the raw FMP string
    assert classified.classification_source == "fmp_identity_confirmed"


def test_equity_branch_with_market_data_and_isin_mismatch_resolves_no_classification() -> None:
    """AC4, exercised through the registry wiring (not just the resolver
    directly): an ISIN mismatch reached via classify_imported_instrument
    still yields no classification, not the FMP value."""
    registry = InstrumentRegistry()
    market_data = _SpyMarketData(profile={"sector": "Consumer Cyclical", "isin": "US9999999999"})
    imported = ImportedInstrument(symbol="ZZZ5", description="Some Unknown Equity Corp", isin="US1111111111")

    classified = registry.classify_imported_instrument(imported, market_data=market_data)

    assert classified.sector is None
    assert classified.classification_source == "unavailable"


# ── US-39.1 / T-39.1.6: identity-gated ETF-branch FMP resolution wiring ─────


def test_static_registry_etf_never_calls_fmp_even_when_market_data_supplied() -> None:
    """AC1: a direct-held ETF symbol present in INSTRUMENT_DEFINITIONS
    (SPY) never triggers get_company_profile or get_etf_sector_weightings,
    even when market_data IS supplied to attach_snapshot_metadata — the
    static-dict fast path short-circuits before classify_imported_instrument
    (and therefore resolve_etf_sector) is ever reached."""
    registry = InstrumentRegistry()
    market_data = _SpyMarketData()
    snapshot = _one_position_snapshot(
        "SPY",
        instrument=ImportedInstrument(symbol="SPY", isin="US78462F1030"),
    )

    metadata = registry.attach_snapshot_metadata(snapshot, market_data=market_data)

    assert market_data.calls == []
    assert market_data.weightings_calls == []
    assert metadata["SPY"].sector == "Broad Market"  # static registry value, unchanged
    assert metadata["SPY"].classification_source == "static"


def test_etf_branch_with_market_data_and_isin_match_resolves_fmp_sector() -> None:
    """AC2/AC3: classify_imported_instrument's ETF branch delegates to
    resolve_etf_sector (this story's new module) when market_data is
    supplied — proving the wiring, not re-testing the resolver's own logic
    (covered directly in test_etf_sector_resolution.py)."""
    registry = InstrumentRegistry()
    market_data = _SpyMarketData(
        responses={"ZZZ6": {"isin": "IE00BQ70R696"}},
        sector_weightings={"ZZZ6": [{"sector": "Healthcare", "weightPercentage": 98.0}]},
    )
    imported = ImportedInstrument(symbol="ZZZ6", description="Some New UCITS ETF", instrument_type="ETF", isin="IE00BQ70R696")

    classified = registry.classify_imported_instrument(imported, market_data=market_data)

    assert market_data.calls == ["ZZZ6"]
    assert market_data.weightings_calls == ["ZZZ6"]
    assert classified.sector == "Health Care"  # taxonomy-mapped, not the raw FMP string
    assert classified.classification_source == "fmp_etf_sector_weighting_confirmed"
    assert classified.category == "UCITS ETF"  # unaffected by the dynamic sector resolution
