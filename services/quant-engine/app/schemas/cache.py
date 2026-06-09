"""Pydantic schemas for the market-data cache admin endpoints (US-20.1)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class CacheNamespaceStat(BaseModel):
    namespace: str
    entries: int


class CacheStats(BaseModel):
    enabled: bool
    cache_dir: str
    total_entries: int
    namespaces: list[CacheNamespaceStat]


class CacheClearRequest(BaseModel):
    # None clears all market-data cache (FMP + Yahoo); a namespace clears only it.
    namespace: str | None = Field(default=None)


class CacheClearResult(BaseModel):
    removed: int
    namespace: str | None = None
