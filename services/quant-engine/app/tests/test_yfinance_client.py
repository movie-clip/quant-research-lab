"""Tests for the YFinanceClient secondary market-data provider (US-18.1).

yfinance is always mocked — no network is ever hit.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.clients.yfinance_client import YFinanceClient
from app.core.cache import JsonFileCache


def _frame(n: int = 25) -> pd.DataFrame:
    idx = pd.to_datetime([f"2024-01-{d:02d}" for d in range(1, n + 1)])
    return pd.DataFrame(
        {
            "Open": [1.0] * n,
            "High": [1.0] * n,
            "Low": [1.0] * n,
            "Close": [10.0 + i for i in range(n)],
            "Adj Close": [9.0 + i for i in range(n)],
            "Volume": [100 + i for i in range(n)],
        },
        index=idx,
    )


def _install_yf(monkeypatch, *, frame=None, raises=False, calls=None):
    class FakeTicker:
        def __init__(self, symbol):
            if calls is not None:
                calls.append(symbol)

        def history(self, start, end, auto_adjust=False):  # noqa: ANN001
            if raises:
                raise RuntimeError("yahoo down")
            return frame

    monkeypatch.setattr("yfinance.Ticker", FakeTicker)


def _client_no_cache() -> YFinanceClient:
    c = YFinanceClient()
    c.cache = None
    return c


def test_maps_frame_to_fmp_shaped_rows(monkeypatch):
    _install_yf(monkeypatch, frame=_frame(25))
    rows = _client_no_cache().get_historical_price_light("VUAA.L", "2024-01-01", "2024-02-01")
    assert len(rows) == 25
    first = rows[0]
    assert first["symbol"] == "VUAA.L"
    assert first["date"] == "2024-01-01"
    # price == adjClose (adjusted close), so return-basis classifies verified.
    assert first["price"] == first["adjClose"] == 9.0
    assert "volume" in first


def test_empty_frame_returns_empty(monkeypatch):
    _install_yf(monkeypatch, frame=pd.DataFrame())
    assert _client_no_cache().get_historical_price_light("DEFS.L", "2024-01-01", "2024-02-01") == []


def test_exception_is_swallowed(monkeypatch):
    _install_yf(monkeypatch, raises=True)
    assert _client_no_cache().get_historical_price_light("VUAA.L", "2024-01-01", "2024-02-01") == []


def test_nan_bars_are_skipped(monkeypatch):
    # pandas encodes missing bars as float('nan') — not None — so they must be
    # filtered by a finiteness check (bug 2026-06-10: cached NaN bars 500'd the
    # correlation routes).
    frame = _frame(5)
    frame.loc[frame.index[2], "Adj Close"] = float("nan")
    frame.loc[frame.index[4], "Adj Close"] = float("inf")
    _install_yf(monkeypatch, frame=frame)

    rows = _client_no_cache().get_historical_price_light("VUAA.L", "2024-01-01", "2024-02-01")

    assert len(rows) == 3  # the NaN and inf bars are omitted, finite rows kept
    assert all(
        isinstance(r["price"], float) and r["price"] == r["adjClose"] and r["price"] == r["price"]  # not NaN
        for r in rows
    )
    assert [r["date"] for r in rows] == ["2024-01-01", "2024-01-02", "2024-01-04"]


def test_result_is_cached(monkeypatch, tmp_path: Path):
    calls: list[str] = []
    _install_yf(monkeypatch, frame=_frame(22), calls=calls)
    client = YFinanceClient()
    client.cache = JsonFileCache(tmp_path)
    client.history_ttl_seconds = 10_000

    rows1 = client.get_historical_price_light("VUAA.L", "2024-01-01", "2024-02-01")
    rows2 = client.get_historical_price_light("VUAA.L", "2024-01-01", "2024-02-01")

    assert rows1 == rows2 and len(rows1) == 22
    assert len(calls) == 1  # second call served from cache, yfinance not re-invoked
    assert any(p.name.startswith("history_yf-") for p in tmp_path.glob("*.json"))


def test_negative_result_is_cached(monkeypatch, tmp_path: Path):
    calls: list[str] = []
    _install_yf(monkeypatch, frame=pd.DataFrame(), calls=calls)
    client = YFinanceClient()
    client.cache = JsonFileCache(tmp_path)
    client.history_ttl_seconds = 10_000

    assert client.get_historical_price_light("DEFS.L", "2024-01-01", "2024-02-01") == []
    assert client.get_historical_price_light("DEFS.L", "2024-01-01", "2024-02-01") == []
    assert len(calls) == 1  # empty negative cached → no second yfinance call
