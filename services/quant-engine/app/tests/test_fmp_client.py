"""Tests for the FMP client's dividend-adjusted history method (US-34.9).

Epic 34 F-9: the `verified_total_return` benchmark rung requires every row to
carry `adjClose` AND the fetch to come from `VERIFIED_BENCHMARK_ENDPOINT`. The
`light` endpoint returns no adjusted close, so the two conditions could never
both hold. This module covers the endpoints that can satisfy both.

The response shapes below were verified against the live API on 2026-08-17:

    historical-price-eod/full              -> open high low close volume ...   (no adjClose)
    historical-price-eod/dividend-adjusted -> adjOpen adjHigh adjLow adjClose  (no close)

which is why the client joins them. The network is never hit here — `_get` is
stubbed.
"""
from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.clients.fmp import FmpClient, MarketDataAuthError, _join_close_and_adjusted_rows
from app.core.cache import JsonFileCache


def _full(date: str, close: float, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"symbol": "SPY", "date": date, "close": close, "volume": 1000}
    row.update(extra)
    return row


def _adjusted(date: str, adj_close: float, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"symbol": "SPY", "date": date, "adjClose": adj_close, "volume": 1000}
    row.update(extra)
    return row


def _stub(client, calls: list[tuple[str, dict]] | None = None):
    """Stub `_get` to answer both endpoints from their real-world shapes."""
    def fake_get(namespace, path, params, ttl_seconds=None):  # noqa: ANN001, ANN202
        if calls is not None:
            calls.append((path, dict(params), namespace, ttl_seconds))
        if path.endswith("/full"):
            return [_full("2026-08-10", 770.0), _full("2026-08-11", 771.0)]
        if path.endswith("/dividend-adjusted"):
            return [_adjusted("2026-08-10", 766.0), _adjusted("2026-08-11", 771.0)]
        raise AssertionError(f"unexpected path {path}")
    client._get = fake_get  # noqa: SLF001
    return client


def test_requests_both_endpoints_in_the_history_namespace() -> None:
    """US-34.9 AC1 — the paths and cache namespace the verified rung is pinned to.

    Two calls are required because neither response carries both `close` and
    `adjClose`. They share the `history` namespace and TTL, so the second is a
    cache hit on every subsequent window.
    """
    calls: list[tuple[str, dict]] = []
    client = _stub(FmpClient(), calls)

    client.get_historical_price_dividend_adjusted("SPY", "2026-01-08", "2026-08-11")

    paths = [c[0] for c in calls]
    assert paths == ["historical-price-eod/full", "historical-price-eod/dividend-adjusted"]
    for _path, params, namespace, ttl in calls:
        assert params == {"symbol": "SPY", "from": "2026-01-08", "to": "2026-08-11"}
        assert namespace == "history"
        assert ttl == client.history_ttl_seconds


def test_price_is_the_traded_close_and_adjclose_carries_the_adjustment() -> None:
    """US-34.9 AC2 — the row shape this project's consumers expect.

    `price` must stay the REAL traded close so valuation and the raw chart series
    are untouched; `adjClose` carries the adjusted figure that the shared price
    selector prefers for returns.

    Collapsing the two — mapping `price` from `adjClose`, as the yfinance client
    does — would value FMP-served holdings on a different basis from the rest and
    spread that inconsistency rather than contain it.
    """
    client = _stub(FmpClient())

    rows = client.get_historical_price_dividend_adjusted("SPY", "2026-08-10", "2026-08-11")

    assert [r["date"] for r in rows] == ["2026-08-10", "2026-08-11"]
    assert [r["price"] for r in rows] == [770.0, 771.0]
    assert [r["adjClose"] for r in rows] == [766.0, 771.0]
    assert all(r["symbol"] == "SPY" for r in rows)
    assert [r["volume"] for r in rows] == [1000, 1000]


def test_an_adjusted_only_response_yields_no_rows_rather_than_a_silent_blank() -> None:
    """US-34.9 AC2 — regression for the bug that emptied SPY's 148 rows.

    The first version of this method mapped `price` from a `close` key that the
    dividend-adjusted response does not have, so every row was dropped. The
    benchmark came back EMPTY, which downstream looks exactly like "no data" —
    a fail-closed path reached for an entirely accidental reason, and one that
    then degraded the whole golden capture.

    The join makes that impossible to reach silently: with no `full` response
    there are no rows, and the caller sees an empty benchmark rather than a
    plausible-looking wrong one. This test exists so the failure mode cannot
    return unnoticed.
    """
    assert _join_close_and_adjusted_rows("SPY", [], [_adjusted("2026-08-10", 766.0)]) == []
    assert _join_close_and_adjusted_rows("SPY", [_full("2026-08-10", 770.0)], []) == []


def test_unmatched_or_unusable_dates_are_dropped_never_back_filled() -> None:
    """US-34.9 AC2/AC6 — fail-closed at the join, never a fabricated adjustment.

    A date present on only one side must NOT inherit the other side's value:
    that would invent a dividend adjustment and, worse, would make a partially
    adjusted series look fully adjusted to `detect_history_return_basis` —
    promoting a slice to the verified rung on data that does not support it.

    NaN is checked explicitly because it survives both `is not None` and
    `float()`; non-finite bars poisoning the engines is a bug this project has
    already had once.
    """
    rows = _join_close_and_adjusted_rows(
        "SPY",
        [
            _full("2026-08-10", 770.0),
            _full("2026-08-11", 771.0),              # no adjusted counterpart
            _full("2026-08-12", float("nan")),       # non-finite close
            _full("2026-08-13", 773.0),              # adjusted side is non-finite
            {"symbol": "SPY", "close": 774.0},       # no date
        ],
        [
            _adjusted("2026-08-10", 766.0),
            _adjusted("2026-08-12", 769.0),
            _adjusted("2026-08-13", float("nan")),
            _adjusted("2026-08-14", 775.0),          # no full counterpart
        ],
    )

    assert [r["date"] for r in rows] == ["2026-08-10"]
    assert rows[0]["price"] == 770.0
    assert rows[0]["adjClose"] == 766.0


# -- US-35.1 (Epic 35 F-1): an auth failure is not missing data ---------------


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://example.invalid/stable/whatever")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


def _client_with_cache(tmp_path, monkeypatch, status: int):
    """A client whose transport always fails with `status`."""
    client = FmpClient()
    client.api_key = "a-key-that-will-be-rejected"
    client.cache = JsonFileCache(tmp_path)

    def boom(*_a, **_k):
        raise _http_error(status)

    monkeypatch.setattr(client.client, "get", boom)
    return client


def test_a_rejected_key_raises_instead_of_returning_no_data(tmp_path, monkeypatch) -> None:
    """US-35.1 AC1 — the defect this story exists for.

    A 401 used to be negative-cached and then immediately re-read by the
    stale-fallback branch, which returned the `[]` it had just written. The
    error vanished, and every engine downstream degraded to `unavailable`
    perfectly correctly — so nothing anywhere reported that the key was wrong.
    """
    client = _client_with_cache(tmp_path, monkeypatch, 401)

    with pytest.raises(MarketDataAuthError) as excinfo:
        client.get_historical_price_light("AAPL", "2026-08-01", "2026-08-11")

    # The message has to name the cause; "no data" was the old failure mode.
    assert "401" in str(excinfo.value)
    assert "FMP_API_KEY" in str(excinfo.value)


def test_a_rejected_key_is_never_cached_so_fixing_it_works_immediately(tmp_path, monkeypatch) -> None:
    """US-35.1 AC2 — the 24-hour tail is what made this expensive.

    `fmp_history_cache_ttl_seconds` is 86400, so a single bad run used to answer
    `[]` for every symbol it touched for a day. Fixing the key did not help
    until the TTL expired or the cache was cleared by hand.
    """
    client = _client_with_cache(tmp_path, monkeypatch, 401)
    with pytest.raises(MarketDataAuthError):
        client.get_historical_price_light("AAPL", "2026-08-01", "2026-08-11")

    assert list(tmp_path.glob("*.json")) == [], "a 401 must not write a cache entry"

    # With the key fixed, the very next call succeeds — no manual clear.
    monkeypatch.setattr(
        client.client,
        "get",
        lambda *_a, **_k: httpx.Response(
            200,
            json=[{"symbol": "AAPL", "date": "2026-08-11", "price": 304.91, "volume": 1}],
            request=httpx.Request("GET", "https://example.invalid/x"),
        ),
    )
    rows = client.get_historical_price_light("AAPL", "2026-08-01", "2026-08-11")
    assert [r["date"] for r in rows] == ["2026-08-11"]


def test_an_unknown_symbol_still_negative_caches_and_returns_empty(tmp_path, monkeypatch) -> None:
    """US-35.1 AC3 — 404 is a durable fact about the request, and stays.

    "This symbol does not exist" genuinely is an answer about the symbol, and
    caching it is what stops a retry storm. Narrowing the auth case must not
    take this with it.
    """
    client = _client_with_cache(tmp_path, monkeypatch, 404)

    rows = client.get_historical_price_light("NOPE", "2026-08-01", "2026-08-11")

    assert rows == []
    assert len(list(tmp_path.glob("*.json"))) == 1, "404 should still be negative-cached"


def test_an_unset_key_is_not_treated_as_a_rejected_one(tmp_path) -> None:
    """US-35.1 AC7 was WRONG, and this test records why.

    The story claimed "no key" and "rejected key" are the same failure class, so
    both should raise `MarketDataAuthError`. Shipping that turned every route
    into a 400 in CI, which runs **deliberately keyless** — the suite is
    network-free, so engines are expected to reach the client, get nothing, and
    degrade to `unavailable`. Running without a key is a supported mode, not a
    misconfiguration.

    So an unset key keeps raising the plain `ValueError` that
    `MarketDataService` swallows on its way to `[]`. A REJECTED key still raises
    `MarketDataAuthError` uncached — the part of the story that mattered.

    This test is the guard against re-unifying them: they look like the same
    thing and are not.
    """
    client = FmpClient()
    client.api_key = ""
    client.cache = JsonFileCache(tmp_path)

    with pytest.raises(ValueError) as excinfo:
        client.get_historical_price_light("AAPL", "2026-08-01", "2026-08-11")
    assert not isinstance(excinfo.value, MarketDataAuthError), (
        "an unset key must stay swallowable so the keyless offline mode keeps working"
    )
    assert "not configured" in str(excinfo.value)


def test_a_plan_entitlement_response_keeps_its_negative_cache(tmp_path, monkeypatch) -> None:
    """US-35.1 AC8 — 402 is deliberately unchanged, and that is pinned here.

    The UCITS listings FMP does not serve return 402 on every run and fall
    through to the yfinance fallback. That is working as intended, so this test
    exists to stop a later reader "tidying" 402 in with 401 on the assumption
    that both are auth failures. They are not: 402 is an answer about the
    symbol on this plan.
    """
    client = _client_with_cache(tmp_path, monkeypatch, 402)

    rows = client.get_historical_price_light("ISLN.L", "2026-08-01", "2026-08-11")

    assert rows == []
    assert len(list(tmp_path.glob("*.json"))) == 1
