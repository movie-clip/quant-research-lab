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

from app.clients.fmp import FmpClient, _join_close_and_adjusted_rows


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
