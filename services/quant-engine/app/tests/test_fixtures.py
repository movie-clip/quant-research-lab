"""Tests for the shared fixtures module (US-21.2)."""
from __future__ import annotations

from app.schemas.imports import ImportedPortfolioSnapshot
from app.tests.fixtures import (
    imported_snapshot,
    install_market_data_mock,
    position,
    price_rows,
)


def test_imported_snapshot_validates_against_real_schema():
    # The whole point: the 422 gotcha is structurally impossible for users.
    ImportedPortfolioSnapshot.model_validate(imported_snapshot())
    ImportedPortfolioSnapshot.model_validate(
        imported_snapshot(
            positions=[position("AAPL", 1900.0), position("VUAA", 500.0)],
            instruments=[{"symbol": "VUAA", "description": "Vanguard S&P 500 UCITS ETF"}],
            cash_balances=[{"currency": "USD", "ending_cash": 100.0}],
        )
    )


def test_position_overrides_apply():
    p = position("MSFT", 8000.0, quantity=25.0, currency="EUR")
    assert p["symbol"] == "MSFT"
    assert p["market_value"] == 8000.0
    assert p["quantity"] == 25.0
    assert p["currency"] == "EUR"
    assert p["cost_basis"] == 8000.0 * 0.8  # defaults derived from market value


def test_install_market_data_mock_serves_histories_and_meta(mocker):
    rows = price_rows(5, symbol="AAA")
    inst = install_market_data_mock(
        mocker,
        "app.services.provenance_engine",
        histories={"AAA": rows, "BBB": []},
        vendor_by_symbol={"AAA": "yfinance"},
    )

    # The target module's MarketDataService is the mock.
    import app.services.provenance_engine as prov
    assert prov.MarketDataService.return_value is inst

    assert inst.get_historical_prices("AAA", "x", "y") == rows
    assert inst.get_historical_prices("ZZZ", "x", "y") == []  # no default_rows
    assert inst.get_historical_prices_for_symbols(["AAA", "ZZZ"], "x", "y") == {"AAA": rows, "ZZZ": []}
    assert inst.last_fetch_meta["AAA"]["vendor"] == "yfinance"
    assert "BBB" not in inst.last_fetch_meta  # empty + no vendor → no meta
