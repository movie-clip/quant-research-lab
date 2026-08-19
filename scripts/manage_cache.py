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


# `fmp` is not a namespace anything writes — it is the CLI's alias for "every
# namespace", matching `JsonFileCache.clear`, which treats it like `None`.
ALL_NAMESPACES_ALIAS = "fmp"


def _cache() -> JsonFileCache:
    settings = get_settings()
    return JsonFileCache(Path(settings.fmp_cache_dir))


def list_cache() -> int:
    cache = _cache()
    entries = cache.list_entries()
    if not entries:
        print("Cache is empty.")
        return 0

    for entry in entries:
        print(f"{entry['namespace']} {entry['file']} payload_size={entry['payload_size']} fetched_at={entry['fetched_at']:.0f}")

    # US-35.2: a per-namespace summary, so choosing what to clear does not
    # require eyeballing hundreds of hashed filenames.
    print()
    print("Namespaces:")
    for namespace, count in cache.namespaces().items():
        print(f"  {namespace:<20} {count} entr{'y' if count == 1 else 'ies'}")
    print(f"  {'TOTAL':<20} {len(entries)}")
    return 0


def clear_cache(namespace: str | None) -> int:
    cache = _cache()
    before = cache.namespaces()

    # US-35.2: an unknown namespace used to remove nothing and report
    # "Removed 0 cache file(s)." — indistinguishable from an already-empty one.
    if namespace is not None and namespace != ALL_NAMESPACES_ALIAS and namespace not in before:
        known = ", ".join(before) or "(cache is empty)"
        print(f"No such namespace: {namespace!r}. Present: {known}", file=sys.stderr)
        return 1

    removed = cache.clear(namespace=namespace)
    print(f"Removed {removed} cache file(s).")

    # US-35.2: the reason this story exists. Clearing `history` on a cache that
    # also holds `history_yf` used to say nothing about the 51 entries left
    # standing, so "I cleared the history cache" was wrong in a way that only
    # showed up during the NEXT debugging round. Namespace matching is exact —
    # `history-*.json` does not match `history_yf-*.json` — which is correct and
    # deliberate, but it has to be visible.
    remaining = cache.namespaces()
    if remaining:
        left = ", ".join(f"{ns} ({count})" for ns, count in remaining.items())
        print(f"Still cached: {left}")
        if namespace is not None and namespace != ALL_NAMESPACES_ALIAS:
            near = [ns for ns in remaining if ns.startswith(namespace)]
            if near:
                print(
                    f"Note: {', '.join(near)} {'is' if len(near) == 1 else 'are'} a separate "
                    f"namespace and was NOT cleared by --namespace {namespace}. "
                    f"Clear it explicitly, or run without --namespace to clear everything."
                )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage local FMP cache files.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List cache files.")
    clear_parser = subparsers.add_parser("clear", help="Clear cache files.")
    # US-35.2: derived from what is on disk, not a hand-written list. Nothing
    # declares the set of namespaces — one exists because a caller passed that
    # string to `build_key` — so a literal list is guaranteed to drift, and had:
    # `history_yf`, `holdings`, `profile`, `fundamentals`, `screener` and
    # `index_constituents` all existed and none could be named.
    clear_parser.add_argument(
        "--namespace",
        default=None,
        metavar="NAME",
        help=(
            "Namespace to clear. Run `list` to see what is present. "
            f"Omit, or use {ALL_NAMESPACES_ALIAS!r}, to clear everything."
        ),
    )

    args = parser.parse_args(argv)

    if args.command == "list":
        return list_cache()
    if args.command == "clear":
        return clear_cache(args.namespace)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
