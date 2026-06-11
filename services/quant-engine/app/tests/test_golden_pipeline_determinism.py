"""US-21.4 — Golden pipeline determinism.

These tests pin the property that makes the dashboard goldens trustworthy
offline: generation reads a committed frozen market-data fixture, never the
live FMP cache, so the output is byte-stable across machines and runs and the
freshness check needs no env var or warm cache.

They run under the default network guard (pytest.ini `--disable-socket`); the
fact that they pass with sockets disabled is itself the proof that the golden
path is network-free.
"""
from __future__ import annotations

import re

import pytest

from app.scripts.export_dashboard_goldens import (
    _dashboard_golden_output_path,
    _repo_root,
    render_dashboard_goldens_text,
)
from app.scripts.frozen_market_data import (
    FrozenMarketData,
    FrozenMarketDataMiss,
)


_SOURCE_PATH_RE = re.compile(r'"source_path": "[^"]*"')


def _strip_source_paths(text: str) -> str:
    # Worktree/machine absolute paths differ; the freshness check normalizes
    # them, so this comparison must too. Real content drift still fails.
    return _SOURCE_PATH_RE.sub('"source_path": "<normalized>"', text)


def test_render_is_deterministic() -> None:
    # Two consecutive renders (frozen provider, no network) are byte-identical.
    first = render_dashboard_goldens_text()
    second = render_dashboard_goldens_text()
    assert first == second


def test_generated_matches_committed_goldens() -> None:
    # The in-process analogue of the conftest freshness fixture, but now
    # deterministic: regenerated text equals the committed dashboardGoldens.ts.
    repo_root = _repo_root()
    committed = _dashboard_golden_output_path(repo_root).read_text(encoding="utf-8")
    fresh = render_dashboard_goldens_text(repo_root)
    assert _strip_source_paths(fresh) == _strip_source_paths(committed)


def test_frozen_provider_replays_rows_and_meta() -> None:
    payload = {
        "series": [
            {
                "symbol": "SPY",
                "from": "2026-01-08",
                "to": "2026-05-25",
                "rows": [{"date": "2026-01-08", "price": 100.0}],
            },
            {
                "symbol": "VTI",
                "from": "2026-01-08",
                "to": "2026-05-25",
                "rows": [{"date": "2026-01-08", "price": 50.0}],
            },
        ],
        "fetch_meta": {"SPY": {"type": "history", "vendor": "fmp-verified-benchmark"}},
    }
    provider = FrozenMarketData(payload)

    benchmark = provider.get_direct_verified_benchmark_history("SPY", "2026-01-08", "2026-05-25")
    assert benchmark == [{"date": "2026-01-08", "price": 100.0}]
    # Row fetch records meta, which the engine reads afterwards.
    assert provider.get_last_fetch_meta("SPY") == {"type": "history", "vendor": "fmp-verified-benchmark"}

    histories = provider.get_historical_prices_for_symbols(
        ["VTI", "SPY"], "2026-01-08", "2026-05-25"
    )
    assert histories["VTI"] == [{"date": "2026-01-08", "price": 50.0}]
    assert histories["SPY"] == [{"date": "2026-01-08", "price": 100.0}]

    # Defensive copy: mutating a returned row must not corrupt the fixture.
    benchmark[0]["price"] = -1.0
    assert provider.get_direct_verified_benchmark_history("SPY", "2026-01-08", "2026-05-25") == [
        {"date": "2026-01-08", "price": 100.0}
    ]


def test_frozen_provider_raises_on_missing_series() -> None:
    # A symbol/window absent from the fixture must fail loudly (stale-fixture
    # detection), never silently return [] (which would look like a legitimate
    # 'unavailable' golden).
    provider = FrozenMarketData({"series": [], "fetch_meta": {}})
    with pytest.raises(FrozenMarketDataMiss):
        provider.get_historical_prices("NOPE", "2026-01-08", "2026-05-25")
    with pytest.raises(FrozenMarketDataMiss):
        provider.get_historical_prices_for_symbols(["NOPE"], "2026-01-08", "2026-05-25")
