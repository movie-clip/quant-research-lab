"""Market-data cache admin (US-20.1).

Read-only stats + clear over the local JSON file cache shared by the FMP and
Yahoo clients. Pure file operations — no network.
"""
from __future__ import annotations

from collections import Counter
from pathlib import Path

from app.core.cache import JsonFileCache
from app.core.settings import get_settings
from app.schemas.cache import CacheClearResult, CacheNamespaceStat, CacheStats


def _cache() -> JsonFileCache:
    return JsonFileCache(Path(get_settings().fmp_cache_dir))


def get_cache_stats() -> CacheStats:
    settings = get_settings()
    entries = _cache().list_entries()
    counts = Counter(entry["namespace"] for entry in entries)
    namespaces = [
        CacheNamespaceStat(namespace=namespace, entries=count)
        for namespace, count in sorted(counts.items())
    ]
    return CacheStats(
        enabled=settings.fmp_cache_enabled,
        cache_dir=settings.fmp_cache_dir,
        total_entries=len(entries),
        namespaces=namespaces,
    )


def clear_cache(namespace: str | None = None) -> CacheClearResult:
    removed = _cache().clear(namespace=namespace)
    return CacheClearResult(removed=removed, namespace=namespace)
