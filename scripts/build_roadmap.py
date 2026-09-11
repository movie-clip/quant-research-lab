#!/usr/bin/env python3
"""Generate `docs/product/ROADMAP.md` from story and epic frontmatter.

    python scripts/build_roadmap.py            # write docs/product/ROADMAP.md
    python scripts/build_roadmap.py --check    # fail if it is stale (CI gate)

Why this exists
---------------

The previous `docs/product/epic-roadmap.md` was a hand-maintained "living
execution snapshot". It reached 2,090 lines before it was deleted at commit
`ce9c97d`, and roughly nine tenths of it was completed-epic prose that no
reader needed and every writer had to scroll past. Two properties made that
inevitable, and neither was about discipline:

1. It mixed three things with three different lifetimes - what is active
   (changes every slice), why a thing exists (written once), and what shipped
   (append-only forever) - in one file.
2. It was a second copy of facts the story files already carried, so every
   slice had to write both, and the copies drifted the moment one was skipped.

The fix is the same one the rest of this repo already uses for goldens and for
`docs/tech-debt-register.md`: keep exactly one hand-written home per fact, and
*derive* the index instead of maintaining it. A story's status lives in the
story file - the file the author is editing anyway - and this script reads it
back. There is nothing to remember to update, so nothing can go stale, and
`--check` in `run_all_tests.py` makes that structural rather than a habit.

History does not accumulate here either: a shipped story is one generated row,
and the narrative stays in the story file and in Git.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIR = ROOT / "docs" / "product"
STORY_DIR = PRODUCT_DIR / "stories"
EPIC_DIR = PRODUCT_DIR / "epics"
ROADMAP = PRODUCT_DIR / "ROADMAP.md"

STORY_ID = re.compile(r"^US-\d+\.\d+$")
EPIC_ID = re.compile(r"^EP-\d+$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Ordered: this is the order sections appear in the generated file.
STATUSES = ("active", "backlog", "done", "dropped")
HEADINGS = {
    "active": "Active",
    "backlog": "Backlog",
    "done": "Shipped",
    "dropped": "Dropped",
}

HEADER = """# Roadmap

<!-- GENERATED FILE - do not edit.
     Source of truth is the frontmatter of each file under
     `docs/product/stories/` and `docs/product/epics/`.
     Regenerate with `python scripts/build_roadmap.py`;
     `scripts/run_all_tests.py` fails if this file is stale. -->

To change what this says, edit the story or epic file it came from. A shipped
story keeps one row here and its full record in its own file and in Git.
"""


class FrontmatterError(Exception):
    """A source file's frontmatter is missing or malformed."""


@dataclass(frozen=True)
class Item:
    path: Path
    id: str
    title: str
    status: str
    epic: str | None
    opened: str | None
    closed: str | None

    @property
    def sort_key(self) -> tuple[int, int]:
        """Numeric, so `US-9.2` sorts before `US-45.1` rather than after it."""
        nums = [int(n) for n in re.findall(r"\d+", self.id)]
        return (nums[0], nums[1] if len(nums) > 1 else 0)


def parse_frontmatter(path: Path) -> dict[str, str]:
    """Read the leading `---` block as flat `key: value` pairs.

    Deliberately not YAML: the fields are all short scalars, and a dependency
    that only ever parses `key: value` is a dependency that can fail in ways
    the format cannot.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError(
            f"{path.name}: no frontmatter - the file must open with a `---` "
            f"block (see docs/product/planning.md)"
        )
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise FrontmatterError(f"{path.name}: frontmatter block is never closed") from None
    fields: dict[str, str] = {}
    for lineno, raw in enumerate(lines[1:end], start=2):
        if not raw.strip():
            continue
        if ":" not in raw:
            raise FrontmatterError(f"{path.name}:{lineno}: not a `key: value` line: {raw!r}")
        key, _, value = raw.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def _require(fields: dict[str, str], key: str, path: Path) -> str:
    value = fields.get(key, "")
    if not value:
        raise FrontmatterError(f"{path.name}: frontmatter is missing `{key}`")
    return value


def load_item(path: Path, id_pattern: re.Pattern[str], kind: str) -> Item:
    fields = parse_frontmatter(path)
    item_id = _require(fields, "id", path)
    if not id_pattern.match(item_id):
        raise FrontmatterError(f"{path.name}: `id: {item_id}` is not a valid {kind} id")
    if not path.name.startswith(item_id + "-"):
        raise FrontmatterError(
            f"{path.name}: `id: {item_id}` does not match the filename - "
            f"expected `{item_id}-<slug>.md`"
        )
    status = _require(fields, "status", path).lower()
    if status not in STATUSES:
        raise FrontmatterError(
            f"{path.name}: `status: {status}` is not one of {', '.join(STATUSES)}"
        )
    for date_key in ("opened", "closed"):
        value = fields.get(date_key)
        if value and not ISO_DATE.match(value):
            raise FrontmatterError(f"{path.name}: `{date_key}: {value}` is not `YYYY-MM-DD`")
    if status == "done" and not fields.get("closed"):
        raise FrontmatterError(f"{path.name}: status is `done` but no `closed:` date is set")
    epic = fields.get("epic") or None
    if epic and not EPIC_ID.match(epic):
        raise FrontmatterError(
            f"{path.name}: `epic: {epic}` is not an epic id - use `EP-<n>`, or "
            f"omit the field entirely when the story stands alone"
        )
    return Item(
        path=path,
        id=item_id,
        title=_require(fields, "title", path),
        status=status,
        epic=epic,
        opened=fields.get("opened"),
        closed=fields.get("closed"),
    )


def load_all() -> tuple[list[Item], dict[str, Item]]:
    stories = [load_item(p, STORY_ID, "story") for p in sorted(STORY_DIR.glob("US-*.md"))]
    epics = {}
    if EPIC_DIR.is_dir():
        for path in sorted(EPIC_DIR.glob("EP-*.md")):
            epic = load_item(path, EPIC_ID, "epic")
            epics[epic.id] = epic
    missing = {s.epic for s in stories if s.epic} - set(epics)
    if missing:
        raise FrontmatterError(
            f"stories name epics with no file under docs/product/epics/: "
            f"{', '.join(sorted(missing))}"
        )
    return stories, epics


def _rows(items: list[Item], epics: dict[str, Item], newest_first: bool) -> list[str]:
    ordered = sorted(items, key=lambda i: i.sort_key, reverse=newest_first)
    out = ["| Story | Epic | Title | Date |", "|---|---|---|---|"]
    for item in ordered:
        epic = epics[item.epic].title if item.epic else "-"
        date = item.closed or item.opened or "-"
        link = f"[{item.id}](stories/{item.path.name})"
        out.append(f"| {link} | {epic} | {item.title} | {date} |")
    return out


def render(stories: list[Item], epics: dict[str, Item]) -> str:
    parts = [HEADER]
    for status in STATUSES:
        group = [s for s in stories if s.status == status]
        if not group and status == "dropped":
            continue
        parts.append(f"## {HEADINGS[status]}\n")
        if not group:
            parts.append("_None._\n")
        else:
            parts.append("\n".join(_rows(group, epics, newest_first=status == "done")) + "\n")
    open_epics = [e for e in epics.values() if e.status in ("active", "backlog")]
    if open_epics:
        parts.append("## Open epics\n")
        rows = ["| Epic | Status | Title |", "|---|---|---|"]
        for epic in sorted(open_epics, key=lambda e: e.sort_key):
            rows.append(
                f"| [{epic.id}](epics/{epic.path.name}) | {epic.status} | {epic.title} |"
            )
        parts.append("\n".join(rows) + "\n")
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write; exit non-zero if ROADMAP.md is missing or stale.",
    )
    args = parser.parse_args()
    try:
        stories, epics = load_all()
    except FrontmatterError as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1
    generated = render(stories, epics)
    current = ROADMAP.read_text(encoding="utf-8") if ROADMAP.exists() else None
    if args.check:
        if current == generated:
            print(f"ok   {ROADMAP.relative_to(ROOT)} ({len(stories)} stories, {len(epics)} epics)")
            return 0
        print(
            f"FAIL {ROADMAP.relative_to(ROOT)} is "
            f"{'missing' if current is None else 'stale'} - run "
            f"`python scripts/build_roadmap.py` and commit the result",
            file=sys.stderr,
        )
        return 1
    ROADMAP.write_text(generated, encoding="utf-8")
    print(f"wrote {ROADMAP.relative_to(ROOT)} ({len(stories)} stories, {len(epics)} epics)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
