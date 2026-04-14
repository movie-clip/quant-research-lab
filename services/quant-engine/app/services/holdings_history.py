from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.settings import get_settings


class HoldingsHistoryStore:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.fmp_holdings_snapshot_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def record_snapshot(self, symbol: str, resolved_symbol: str | None, rows: list[dict[str, Any]]) -> str | None:
        if not rows:
            return None
        snapshot_date = self._extract_snapshot_date(rows)
        if snapshot_date is None:
            return None

        symbol_dir = self.base_dir / symbol.upper()
        symbol_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path = symbol_dir / f"{snapshot_date}.json"
        payload = {
            "symbol": symbol.upper(),
            "resolved_symbol": (resolved_symbol or symbol).upper(),
            "snapshot_date": snapshot_date,
            "recorded_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "rows": rows,
        }
        snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
        return snapshot_date

    def get_snapshot_for_date(self, symbol: str, as_of_date: str) -> list[dict[str, Any]]:
        symbol_dir = self.base_dir / symbol.upper()
        if not symbol_dir.exists():
            return []

        selected_path: Path | None = None
        for path in sorted(symbol_dir.glob("*.json")):
            snapshot_date = path.stem
            if snapshot_date <= as_of_date:
                selected_path = path
            else:
                break

        if selected_path is None:
            paths = sorted(symbol_dir.glob("*.json"))
            if not paths:
                return []
            selected_path = paths[0]

        payload = json.loads(selected_path.read_text(encoding="utf-8"))
        rows = payload.get("rows")
        return rows if isinstance(rows, list) else []

    def list_snapshot_dates(self, symbol: str) -> list[str]:
        symbol_dir = self.base_dir / symbol.upper()
        if not symbol_dir.exists():
            return []
        return [path.stem for path in sorted(symbol_dir.glob("*.json"))]

    def get_snapshot_count(self, symbol: str) -> int:
        return len(self.list_snapshot_dates(symbol))

    def delete_symbol_snapshots(self, symbol: str) -> int:
        symbol_dir = self.base_dir / symbol.upper()
        if not symbol_dir.exists():
            return 0
        removed = 0
        for path in symbol_dir.glob("*.json"):
            path.unlink(missing_ok=True)
            removed += 1
        try:
            symbol_dir.rmdir()
        except OSError:
            pass
        return removed

    def _extract_snapshot_date(self, rows: list[dict[str, Any]]) -> str | None:
        dates: list[str] = []
        for row in rows:
            updated = row.get("updated")
            if not updated:
                continue
            try:
                dates.append(str(updated)[:10])
            except Exception:  # noqa: BLE001
                continue
        return max(dates) if dates else None
