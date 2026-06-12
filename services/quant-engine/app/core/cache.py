from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from threading import Lock
from typing import Any


# Process-level in-memory layer over the on-disk cache (US-20.3). Keyed by the
# absolute file path → (mtime_ns, parsed envelope dict). Because every engine
# builds its own FmpClient → JsonFileCache over the same directory, this shared
# memo lets repeated reads of the same file (across engines, in one analysis)
# skip the disk read + json.loads after the first. mtime validation makes it
# self-invalidating on any write; absolute-path keys mean real-cache and
# tmp_path test caches never collide. Cleared per-test by an autouse fixture for
# determinism (see conftest `_clear_cache_memory`).
_MEMORY_LOCK = Lock()
_MEMORY_CACHE: dict[str, tuple[int, dict[str, Any]]] = {}


def clear_memory_cache() -> None:
    """Drop the entire in-memory layer (test isolation / explicit invalidation)."""
    with _MEMORY_LOCK:
        _MEMORY_CACHE.clear()


class JsonFileCache:
    # Exposed so callers/tests can clear the shared in-memory layer.
    clear_memory_cache = staticmethod(clear_memory_cache)

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def build_key(self, namespace: str, identifier: str) -> str:
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return f"{namespace}-{digest}.json"

    def _read_envelope(self, path: Path) -> dict[str, Any] | None:
        """Return the parsed cache envelope for `path`, served from the in-memory
        layer when the file is unchanged (same mtime). Returns None for a
        missing or corrupted file (treated as a cache miss). The returned dict
        may be shared across callers — consistent with the existing in-flight
        request sharing in FmpClient; downstream code copies before mutating
        (e.g. `_sanitize_price_rows`)."""
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return None
        abs_key = str(path)
        with _MEMORY_LOCK:
            memo = _MEMORY_CACHE.get(abs_key)
            if memo is not None and memo[0] == mtime_ns:
                return memo[1]
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupted cache file — treat as a cache miss so the caller fetches fresh data.
            return None
        if not isinstance(payload, dict):
            return None
        with _MEMORY_LOCK:
            _MEMORY_CACHE[abs_key] = (mtime_ns, payload)
        return payload

    def get(self, key: str, max_age_seconds: int | None = None, allow_stale: bool = False) -> list[dict[str, Any]] | None:
        path = self.base_dir / key
        payload = self._read_envelope(path)
        if payload is None:
            return None

        fetched_at = float(payload.get("fetched_at", 0))
        age_seconds = time.time() - fetched_at

        if not allow_stale and max_age_seconds is not None and age_seconds > max_age_seconds:
            return None

        cached_payload = payload.get("payload")
        return cached_payload if isinstance(cached_payload, list) else None

    def set(self, key: str, payload: list[dict[str, Any]]) -> None:
        path = self.base_dir / key
        serialized = {
            "fetched_at": time.time(),
            "payload": payload,
        }
        path.write_text(json.dumps(serialized), encoding="utf-8")
        # Refresh the in-memory layer so the next get sees the write immediately.
        try:
            mtime_ns = path.stat().st_mtime_ns
        except OSError:
            return
        with _MEMORY_LOCK:
            _MEMORY_CACHE[str(path)] = (mtime_ns, serialized)

    def list_entries(self) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                namespace = path.name.split("-", 1)[0] if "-" in path.name else "unknown"
                entries.append(
                    {
                        "namespace": namespace,
                        "file": path.name,
                        "fetched_at": float(payload.get("fetched_at", 0)),
                        "payload_size": len(payload.get("payload", [])) if isinstance(payload.get("payload"), list) else 0,
                    }
                )
            except Exception:  # noqa: BLE001
                continue
        return entries

    def clear(self, namespace: str | None = None) -> int:
        removed = 0
        pattern = "*.json" if namespace in {None, "fmp"} else f"{namespace}-*.json"
        for path in self.base_dir.glob(pattern):
            path.unlink(missing_ok=True)
            with _MEMORY_LOCK:
                _MEMORY_CACHE.pop(str(path), None)
            removed += 1
        return removed
