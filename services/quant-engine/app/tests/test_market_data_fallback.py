"""Tests for the FMP→yfinance fallback in MarketDataService (US-18.1).

Both providers are mocked — no network.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import app.services.market_data as md


@pytest.fixture
def svc(monkeypatch):
    fmp = MagicMock()
    yf = MagicMock()
    monkeypatch.setattr(md, "FmpClient", MagicMock(return_value=fmp))
    monkeypatch.setattr(md, "YFinanceClient", MagicMock(return_value=yf))
    service = md.MarketDataService()
    return service, fmp, yf


def test_fmp_hit_skips_yfinance(svc):
    service, fmp, yf = svc
    fmp.get_historical_price_light.return_value = [{"symbol": "AAPL", "date": "2024-01-02", "price": 1.0}]

    rows = service.get_historical_prices("AAPL", "2024-01-01", "2024-02-01")

    assert rows and rows[0]["symbol"] == "AAPL"
    assert service.last_fetch_meta["AAPL"]["vendor"] == "fmp"
    yf.get_historical_price_light.assert_not_called()


def test_yfinance_fallback_when_fmp_empty(svc):
    service, fmp, yf = svc
    fmp.get_historical_price_light.return_value = []  # FMP 402 / empty for every candidate
    yf.get_historical_price_light.side_effect = (
        lambda sym, f, t: [{"symbol": sym, "date": "2024-01-02", "price": 95.0, "adjClose": 95.0}]
        if sym == "VUAA.L"
        else []
    )

    rows = service.get_historical_prices("VUAA", "2024-01-01", "2024-02-01")

    assert rows and rows[0]["adjClose"] == 95.0
    assert service.last_fetch_meta["VUAA"]["vendor"] == "yfinance"


def test_yfinance_receives_suffixed_candidate(svc):
    service, fmp, yf = svc
    fmp.get_historical_price_light.return_value = []
    yf.get_historical_price_light.return_value = [{"symbol": "VUAA.L", "date": "2024-01-02", "price": 95.0, "adjClose": 95.0}]

    service.get_historical_prices("VUAA", "2024-01-01", "2024-02-01")

    # First candidate tried via yfinance is the exchange-suffixed symbol.
    first_call_symbol = yf.get_historical_price_light.call_args_list[0].args[0]
    assert first_call_symbol == "VUAA.L"


def test_both_providers_empty_returns_empty(svc):
    service, fmp, yf = svc
    fmp.get_historical_price_light.return_value = []
    yf.get_historical_price_light.return_value = []

    rows = service.get_historical_prices("VUAA", "2024-01-01", "2024-02-01")

    assert rows == []


def test_nonfinite_fmp_rows_are_filtered(svc):
    # Seam sanitization (US-18.4): rows with NaN/inf/absent price never leave
    # get_historical_prices — covers already-poisoned cache entries too.
    service, fmp, yf = svc
    fmp.get_historical_price_light.return_value = [
        {"symbol": "AAPL", "date": "2024-01-02", "price": 1.0},
        {"symbol": "AAPL", "date": "2024-01-03", "price": float("nan")},
        {"symbol": "AAPL", "date": "2024-01-04", "price": float("inf")},
        {"symbol": "AAPL", "date": "2024-01-05"},  # absent price
        {"symbol": "AAPL", "date": "2024-01-08", "price": 2.0},
    ]

    rows = service.get_historical_prices("AAPL", "2024-01-01", "2024-02-01")

    assert [r["date"] for r in rows] == ["2024-01-02", "2024-01-08"]  # order kept
    assert service.last_fetch_meta["AAPL"]["vendor"] == "fmp"
    yf.get_historical_price_light.assert_not_called()


def test_nonfinite_yfinance_rows_are_filtered_and_all_bad_falls_through(svc):
    service, fmp, yf = svc
    fmp.get_historical_price_light.return_value = []
    yf.get_historical_price_light.side_effect = (
        # First candidate (VUAA.L): all-NaN → sanitized empty → falls through.
        # Second candidate (VUAA): one good row → returned.
        lambda sym, f, t: [{"symbol": sym, "date": "2024-01-02", "price": float("nan"), "adjClose": float("nan")}]
        if sym == "VUAA.L"
        else [{"symbol": sym, "date": "2024-01-02", "price": 95.0, "adjClose": 95.0}]
    )

    rows = service.get_historical_prices("VUAA", "2024-01-01", "2024-02-01")

    assert rows == [{"symbol": "VUAA", "date": "2024-01-02", "price": 95.0, "adjClose": 95.0}]
    assert service.last_fetch_meta["VUAA"]["resolved_symbol"] == "VUAA"
