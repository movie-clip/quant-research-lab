from pathlib import Path

from app.core.cache import JsonFileCache


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

    cache.set(key, payload)

    assert cache.get(key, max_age_seconds=0) is None
    assert cache.get(key, max_age_seconds=0, allow_stale=True) == payload


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
