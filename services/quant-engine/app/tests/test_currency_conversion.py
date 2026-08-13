"""US-30.5a (audit F-7): base-currency conversion of portfolio weights.

The headline test is `test_total_base_market_value_matches_statement_stock_total`:
FX-converting the committed IB2026 positions with the statement's own implied
rates reproduces the statement's own `stock_total` to the cent. **The statement
is the arbiter** — that is what makes F-7 a bug and not a modelling preference.
"""

from __future__ import annotations

import pytest

from app.analytics.currency import (
    FxDisclosure,
    base_market_value_by_symbol,
    convert_to_base,
    snapshot_fx_disclosure,
    total_base_market_value,
)
from app.importers.interactive_brokers_csv import import_statement
from app.schemas.imports import ImportedPortfolioSnapshot
from app.tests._statement_fixtures import STATEMENT_2026_CSV_PATH
from app.tests.statement_truths import (
    IB_BASE_WEIGHTS_PCT,
    IB_POSITION_HHI_BASE,
    IB_RAW_MIXED_CURRENCY_SUM,
    IB_TOTALS_2DP,
)
from app.tests.fixtures import imported_snapshot, position


@pytest.fixture(scope="module")
def ib2026() -> ImportedPortfolioSnapshot:
    return import_statement(STATEMENT_2026_CSV_PATH)


def _snapshot(positions, fx_rates=None, base_currency="USD") -> ImportedPortfolioSnapshot:
    payload = imported_snapshot(positions=positions)
    payload["statement"]["base_currency"] = base_currency
    payload["statement_totals"] = {"fx_rates": fx_rates} if fx_rates else None
    return ImportedPortfolioSnapshot.model_validate(payload)


# ── convert_to_base ──────────────────────────────────────────────────────────

def test_convert_to_base_converts_when_a_rate_exists():
    disclosure = FxDisclosure()
    value, converted = convert_to_base(1000.0, "EUR", "USD", {"EURUSD": 1.1422}, disclosure)
    assert value == pytest.approx(1142.2)
    assert converted is True
    assert disclosure.static_rate_currencies == {"EUR"}
    assert disclosure.fallback_currencies == set()


def test_convert_to_base_carries_raw_value_when_no_rate_exists():
    """Never a silent 1:1 claim, never dropped — carried raw AND disclosed."""
    disclosure = FxDisclosure()
    value, converted = convert_to_base(1000.0, "GBP", "USD", {"EURUSD": 1.1422}, disclosure)
    assert value == 1000.0  # the only honest number held
    assert converted is False
    assert disclosure.fallback_currencies == {"GBP"}
    assert disclosure.static_rate_currencies == set()


def test_convert_to_base_passes_base_currency_through_undisclosed():
    disclosure = FxDisclosure()
    value, converted = convert_to_base(1000.0, "USD", "USD", {"EURUSD": 1.1422}, disclosure)
    assert (value, converted) == (1000.0, False)
    assert disclosure.static_rate_currencies == set()
    assert disclosure.fallback_currencies == set()


# ── the statement-arbiter tests (F-7) ────────────────────────────────────────

def test_total_base_market_value_matches_statement_stock_total(ib2026):
    """THE F-7 test: converted total == the statement's own stock total.

    Pre-fix the code summed raw mixed-currency numerals to 58,588.76.
    """
    assert ib2026.statement_totals is not None
    expected = ib2026.statement_totals.stock_total
    assert round(total_base_market_value(ib2026), 2) == pytest.approx(expected, abs=0.01)
    # US-33.4: the literal used to live here, which made a statement refresh
    # fail a structural test. Statement values belong in ONE module.
    assert round(total_base_market_value(ib2026), 2) == pytest.approx(
        IB_TOTALS_2DP["stock_total"], abs=0.01
    )

    # The counter-example that makes F-7 a bug: the raw currency-mixed sum is a
    # different number, and summing numerals across currencies is meaningless.
    raw_sum = sum(p.market_value for p in ib2026.positions)
    assert round(raw_sum, 2) == pytest.approx(IB_RAW_MIXED_CURRENCY_SUM, abs=0.01)
    assert round(raw_sum, 2) != pytest.approx(IB_TOTALS_2DP["stock_total"], abs=0.01)


def test_base_weights_pin_the_currency_corrected_values(ib2026):
    """Per-position weights on the base-currency denominator (US-30.5a AC1)."""
    total = total_base_market_value(ib2026)
    by_symbol = base_market_value_by_symbol(ib2026)
    weight = lambda sym: by_symbol[sym] / total * 100  # noqa: E731

    # US-33.4: pins re-homed to `statement_truths` — a refresh moves every one
    # of these, and they are statement truths, not properties of the weighting.
    for symbol, expected in IB_BASE_WEIGHTS_PCT.items():
        assert weight(symbol) == pytest.approx(expected, abs=0.01), symbol
    # The property that does NOT depend on the statement: converting changes the
    # answer, so a non-base holding must not weigh the same either way.
    raw_total = sum(p.market_value for p in ib2026.positions)
    raw_semi = next(p.market_value for p in ib2026.positions if p.symbol == "SEMI")
    assert weight("SEMI") != pytest.approx(raw_semi / raw_total * 100, abs=0.01)


def test_position_hhi_on_base_weights(ib2026):
    """Concentration moves too — it is computed on the base weights.

    On the pre-refresh statement this was 0.11536 (raw) → 0.11272 (base);
    US-33.4 moved the pin into `statement_truths` so the next refresh does not
    fail this test for the wrong reason.
    """
    total = total_base_market_value(ib2026)
    hhi = sum((value / total) ** 2 for value in base_market_value_by_symbol(ib2026).values())
    assert hhi == pytest.approx(IB_POSITION_HHI_BASE, abs=1e-5)


# ── disclosure tiers ─────────────────────────────────────────────────────────

def test_each_currency_lands_in_exactly_one_disclosure_tier():
    """EUR has a rate (static tier); GBP does not (fallback); USD in neither."""
    snapshot = _snapshot(
        positions=[
            position("AAPL", market_value=1000.0, quantity=10.0, currency="USD"),
            position("SXRV", market_value=1000.0, quantity=10.0, currency="EUR"),
            position("SEMI", market_value=1000.0, quantity=10.0, currency="GBP"),
        ],
        fx_rates={"EURUSD": 1.1422},
    )
    disclosure = snapshot_fx_disclosure(snapshot)

    assert disclosure.sorted_static() == ["EUR"]
    assert disclosure.sorted_fallback() == ["GBP"]
    assert disclosure.static_rate_currencies & disclosure.fallback_currencies == set()


def test_without_rates_totals_are_byte_identical_to_the_raw_sum():
    """US-30.5a AC6: no fx_rates → today's behaviour exactly (and disclosed)."""
    positions = [
        position("AAPL", market_value=1000.0, quantity=10.0, currency="USD"),
        position("SXRV", market_value=2000.0, quantity=10.0, currency="EUR"),
    ]
    snapshot = _snapshot(positions=positions, fx_rates=None)

    assert total_base_market_value(snapshot) == 3000.0  # raw sum, unconverted
    assert snapshot.statement_totals is None
    assert snapshot_fx_disclosure(snapshot).sorted_fallback() == ["EUR"]
