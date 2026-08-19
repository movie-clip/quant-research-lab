"""Tests for the FMP client's dividend-adjusted history method (US-34.9).

Epic 34 F-9: the `verified_total_return` benchmark rung requires every row to
carry `adjClose` AND the fetch to come from `VERIFIED_BENCHMARK_ENDPOINT`. The
`light` endpoint returns no adjusted close, so the two conditions could never
both hold. This module covers the endpoint that can satisfy both.

The network is never hit — `_get` is stubbed.
"""
from __future__ import annotations

from typing import Any

from app.clients.fmp import FmpClient, _map_dividend_adjusted_rows


def _row(date: str, close: float, adj: float | None = None, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"symbol": "SPY", "date": date, "close": close, "volume": 1000}
    if adj is not None:
        row["adjClose"] = adj
    row.update(extra)
    return row


def test_requests_the_dividend_adjusted_endpoint_in_the_history_namespace(monkeypatch) -> None:
    """US-34.9 AC1 — the path and cache namespace the verified rung is pinned to."""
    client = FmpClient()
    seen: dict[str, Any] = {}

    def fake_get(namespace, path, params, ttl_seconds=None):  # noqa: ANN001, ANN202
        seen.update(namespace=namespace, path=path, params=params, ttl_seconds=ttl_seconds)
        return [_row("2026-08-10", 770.0, 772.5)]

    monkeypatch.setattr(client, "_get", fake_get)
    client.get_historical_price_dividend_adjusted("SPY", "2026-01-08", "2026-08-11")

    assert seen["path"] == "historical-price-eod/dividend-adjusted"
    # Same namespace as the light endpoint: both are daily history for the same
    # symbol, so they share the history TTL and cache partition.
    assert seen["namespace"] == "history"
    assert seen["params"] == {"symbol": "SPY", "from": "2026-01-08", "to": "2026-08-11"}
    assert seen["ttl_seconds"] == client.history_ttl_seconds


def test_maps_close_to_price_and_keeps_adjclose_separate(monkeypatch) -> None:
    """US-34.9 AC2 — the row shape this project's consumers expect.

    `price` must stay the UNADJUSTED close so valuation and the raw chart series
    are untouched; `adjClose` carries the adjusted figure that the shared price
    selector prefers for returns. Collapsing the two would silently change what
    every existing consumer reads.
    """
    client = FmpClient()
    monkeypatch.setattr(
        client,
        "_get",
        lambda *a, **k: [_row("2026-08-10", 770.0, 772.5), _row("2026-08-11", 771.0, 773.6)],
    )

    rows = client.get_historical_price_dividend_adjusted("SPY", "2026-08-10", "2026-08-11")

    assert [r["date"] for r in rows] == ["2026-08-10", "2026-08-11"]
    assert [r["price"] for r in rows] == [770.0, 771.0]
    assert [r["adjClose"] for r in rows] == [772.5, 773.6]
    assert all(r["symbol"] == "SPY" for r in rows)
    assert [r["volume"] for r in rows] == [1000, 1000]


def test_unusable_rows_are_dropped_rather_than_back_filled() -> None:
    """US-34.9 AC2/AC6 — fail-closed at the mapper, never a fabricated adjustment.

    A row with no `adjClose` must NOT inherit the unadjusted close: that would
    invent a dividend adjustment and, worse, would make a partially adjusted
    series look fully adjusted to `detect_history_return_basis` — promoting a
    slice to the verified rung on data that does not support it.

    NaN is checked explicitly because it survives both `is not None` and
    `float()`; non-finite bars poisoning the engines is a bug this project has
    already had once.
    """
    rows = _map_dividend_adjusted_rows(
        "SPY",
        [
            _row("2026-08-10", 770.0, 772.5),
            _row("2026-08-11", 771.0),                      # no adjClose
            {"symbol": "SPY", "date": "2026-08-12", "adjClose": 774.0},  # no close
            _row("2026-08-13", float("nan"), 775.0),        # non-finite close
            _row("2026-08-14", 772.0, float("nan")),        # non-finite adjClose
            {"symbol": "SPY", "close": 773.0, "adjClose": 776.0},        # no date
        ],
    )

    assert [r["date"] for r in rows] == ["2026-08-10"]
    assert rows[0]["price"] == 770.0
    assert rows[0]["adjClose"] == 772.5
