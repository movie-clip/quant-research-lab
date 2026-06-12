import json
import os
import time
from pathlib import Path

import app.core.cache as cache_module
from app.core.cache import JsonFileCache, clear_memory_cache


def test_json_file_cache_returns_fresh_payload(tmp_path: Path) -> None:
    cache = JsonFileCache(tmp_path)
    key = cache.build_key("fmp", "quote-short:AAPL")
    payload = [{"symbol": "AAPL", "price": 100.0}]

    cache.set(key, payload)

    assert cache.get(key, max_age_seconds=60) == payload


def test_json_file_cache_can_return_stale_payload(tmp_path: Path) -> None:
    cache = JsonFileCache(tmp_path)
    key = cache.build_key("fmp", "historical:SPY")
    payload = [{"date": "2025-01-02", "price": 100.0}]

    # Write an envelope with a deterministically-old fetched_at (an hour ago) so
    # the expiry check doesn't depend on sub-tick timing (the in-memory layer
    # makes set→get instantaneous, so a `max_age=0` boundary would be flaky).
    path = tmp_path / key
    path.write_text(
        json.dumps({"fetched_at": time.time() - 3600, "payload": payload}),
        encoding="utf-8",
    )

    assert cache.get(key, max_age_seconds=60) is None
    assert cache.get(key, max_age_seconds=60, allow_stale=True) == payload


def test_json_file_cache_lists_and_clears_entries(tmp_path: Path) -> None:
    cache = JsonFileCache(tmp_path)
    quote_key = cache.build_key("quote", "quote-short:AAPL")
    history_key = cache.build_key("history", "historical:SPY")

    cache.set(quote_key, [{"symbol": "AAPL", "price": 100.0}])
    cache.set(history_key, [{"date": "2025-01-02", "price": 100.0}])

    entries = cache.list_entries()
    assert len(entries) == 2

    removed = cache.clear(namespace="quote")
    assert removed == 1
    assert len(cache.list_entries()) == 1


def test_json_file_cache_clear_fmp_removes_all_namespaces(tmp_path: Path) -> None:
    cache = JsonFileCache(tmp_path)
    cache.set(cache.build_key("quote", "quote-short:AAPL"), [{"symbol": "AAPL", "price": 100.0}])
    cache.set(cache.build_key("history", "historical:SPY"), [{"date": "2025-01-02", "price": 100.0}])
    cache.set(cache.build_key("fx", "GBPUSD:2025"), [{"date": "2025-01-02", "price": 1.25}])

    removed = cache.clear(namespace="fmp")

    assert removed == 3
    assert cache.list_entries() == []


# ── US-20.3: in-memory layer ────────────────────────────────────────────────

def test_in_memory_layer_parses_file_once_for_repeated_gets(tmp_path: Path, mocker) -> None:
    cache = JsonFileCache(tmp_path)
    key = cache.build_key("history", "AAA")
    cache.set(key, [{"date": "2025-01-02", "price": 1.0}])
    # Drop the memo populated by set() so we exercise the disk-read-then-memo path.
    clear_memory_cache()

    spy = mocker.spy(cache_module.json, "loads")
    first = cache.get(key, max_age_seconds=60)
    second = cache.get(key, max_age_seconds=60)

    assert first == second == [{"date": "2025-01-02", "price": 1.0}]
    assert spy.call_count == 1  # first read parses; second is an in-memory hit


def test_set_refreshes_memo_immediately(tmp_path: Path) -> None:
    cache = JsonFileCache(tmp_path)
    key = cache.build_key("history", "AAA")
    cache.set(key, [{"date": "2025-01-02", "price": 1.0}])
    assert cache.get(key, max_age_seconds=60) == [{"date": "2025-01-02", "price": 1.0}]

    cache.set(key, [{"date": "2025-01-03", "price": 2.0}])
    assert cache.get(key, max_age_seconds=60) == [{"date": "2025-01-03", "price": 2.0}]


def test_external_file_change_invalidates_memo(tmp_path: Path) -> None:
    cache = JsonFileCache(tmp_path)
    key = cache.build_key("history", "AAA")
    cache.set(key, [{"date": "2025-01-02", "price": 1.0}])
    assert cache.get(key) == [{"date": "2025-01-02", "price": 1.0}]  # memoized

    # Rewrite the file directly and force a clearly-different mtime so the memo's
    # (path, mtime) key no longer matches → next get must re-read.
    path = tmp_path / key
    path.write_text(
        json.dumps({"fetched_at": time.time(), "payload": [{"date": "2025-01-02", "price": 9.9}]}),
        encoding="utf-8",
    )
    bumped = path.stat().st_mtime_ns + 1_000_000_000
    os.utime(path, ns=(bumped, bumped))

    assert cache.get(key) == [{"date": "2025-01-02", "price": 9.9}]


def test_memo_respects_max_age_and_allow_stale(tmp_path: Path) -> None:
    cache = JsonFileCache(tmp_path)
    key = cache.build_key("history", "AAA")
    payload = [{"date": "2025-01-02", "price": 1.0}]
    # Deterministically-old fetched_at so expiry is independent of timing.
    (tmp_path / key).write_text(
        json.dumps({"fetched_at": time.time() - 3600, "payload": payload}),
        encoding="utf-8",
    )

    # Memoizes on first read; the age check still runs on the memoized envelope.
    assert cache.get(key, max_age_seconds=60) is None
    assert cache.get(key, max_age_seconds=60, allow_stale=True) == payload


def test_memo_is_shared_across_instances(tmp_path: Path, mocker) -> None:
    first_cache = JsonFileCache(tmp_path)
    key = first_cache.build_key("history", "AAA")
    first_cache.set(key, [{"date": "2025-01-02", "price": 1.0}])
    clear_memory_cache()

    spy = mocker.spy(cache_module.json, "loads")
    first_cache.get(key)  # reads + memoizes (1 parse)
    second_cache = JsonFileCache(tmp_path)
    assert second_cache.get(key) == [{"date": "2025-01-02", "price": 1.0}]  # shared memo hit
    assert spy.call_count == 1


def test_clear_memory_forces_reparse_and_missing_file_is_none(tmp_path: Path, mocker) -> None:
    cache = JsonFileCache(tmp_path)
    key = cache.build_key("history", "AAA")
    cache.set(key, [{"date": "2025-01-02", "price": 1.0}])
    clear_memory_cache()

    spy = mocker.spy(cache_module.json, "loads")
    cache.get(key)  # re-reads after clear
    assert spy.call_count == 1
    assert cache.get(cache.build_key("history", "MISSING")) is None
