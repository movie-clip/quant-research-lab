from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


class JsonFileCache:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def build_key(self, namespace: str, identifier: str) -> str:
        digest = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return f"{namespace}-{digest}.json"

    def get(self, key: str, max_age_seconds: int | None = None, allow_stale: bool = False) -> list[dict[str, Any]] | None:
        path = self.base_dir / key
        if not path.exists():
            return None

        payload = json.loads(path.read_text(encoding="utf-8"))
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
            removed += 1
        return removed
