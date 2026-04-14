from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "services" / "quant-engine"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.cache import JsonFileCache
from app.core.settings import get_settings


def _cache() -> JsonFileCache:
    settings = get_settings()
    return JsonFileCache(Path(settings.fmp_cache_dir))


def list_cache() -> int:
    entries = _cache().list_entries()
    if not entries:
        print("Cache is empty.")
        return 0

    for entry in entries:
        print(f"{entry['namespace']} {entry['file']} payload_size={entry['payload_size']} fetched_at={entry['fetched_at']:.0f}")
    return 0


def clear_cache(namespace: str | None) -> int:
    removed = _cache().clear(namespace=namespace)
    print(f"Removed {removed} cache file(s).")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Manage local FMP cache files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List cache files.")
    clear_parser = subparsers.add_parser("clear", help="Clear cache files.")
    clear_parser.add_argument("--namespace", choices=["quote", "history", "fx", "fmp"], default=None)

    args = parser.parse_args()

    if args.command == "list":
        return list_cache()
    if args.command == "clear":
        return clear_cache(args.namespace)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
