"""Tests for the market-data cache admin service + routes (US-20.1)."""
from __future__ import annotations

import types
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.services.cache_admin as cache_admin
from app.api.main import app
from app.core.cache import JsonFileCache
from app.services.cache_admin import clear_cache, get_cache_stats


def _seed(directory: Path, namespace: str, n: int) -> None:
    cache = JsonFileCache(directory)
    for i in range(n):
        cache.set(cache.build_key(namespace, f"id-{namespace}-{i}"), [{"row": i}])


@pytest.fixture
def cache_dir(tmp_path: Path, monkeypatch) -> Path:
    stub = types.SimpleNamespace(fmp_cache_dir=str(tmp_path), fmp_cache_enabled=True)
    monkeypatch.setattr(cache_admin, "get_settings", lambda: stub)
    return tmp_path


def test_stats_empty_cache(cache_dir: Path):
    stats = get_cache_stats()
    assert stats.total_entries == 0
    assert stats.namespaces == []
    assert stats.enabled is True


def test_stats_counts_by_namespace(cache_dir: Path):
    _seed(cache_dir, "history", 2)
    _seed(cache_dir, "quote", 1)
    stats = get_cache_stats()
    assert stats.total_entries == 3
    by_ns = {n.namespace: n.entries for n in stats.namespaces}
    assert by_ns == {"history": 2, "quote": 1}


def test_clear_all_removes_everything(cache_dir: Path):
    _seed(cache_dir, "history", 2)
    _seed(cache_dir, "history_yf", 1)
    result = clear_cache(None)
    assert result.removed == 3
    assert get_cache_stats().total_entries == 0


def test_clear_namespace_removes_only_that_namespace(cache_dir: Path):
    _seed(cache_dir, "history", 2)
    _seed(cache_dir, "quote", 1)
    result = clear_cache("history")
    assert result.removed == 2
    by_ns = {n.namespace: n.entries for n in get_cache_stats().namespaces}
    assert by_ns == {"quote": 1}


def test_cache_routes(cache_dir: Path):
    _seed(cache_dir, "history", 2)
    client = TestClient(app)

    stats = client.get("/cache/stats")
    assert stats.status_code == 200
    assert stats.json()["total_entries"] == 2

    cleared = client.post("/cache/clear", json={"namespace": None})
    assert cleared.status_code == 200
    assert cleared.json()["removed"] == 2
    assert client.get("/cache/stats").json()["total_entries"] == 0
