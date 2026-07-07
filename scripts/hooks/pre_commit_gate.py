"""PreToolUse hook: block `git commit` unless the full test suite passed
on the current working tree.

`scripts/run_all_tests.py` writes a marker file (.claude/.last-test-pass) when
the whole suite is green. This hook blocks any Bash `git commit` if the marker
is missing or if any changed file has been modified after the marker was
written — i.e. the tree the tests blessed is not the tree being committed.

Markdown files are exempt (they cannot affect the suite), so the update-docs
close-out flow can commit doc reconciliation without a full re-run. Statement
PDFs under docs/ are NOT exempt — they feed golden generation.

Exit codes (Claude Code hook contract):
  0 — allow the tool call
  2 — block it; stderr is fed back to the agent
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER = ROOT / ".claude" / ".last-test-pass"

GIT_COMMIT_RE = re.compile(r"\bgit\b[^|;&]*\bcommit\b")


def changed_files() -> list[Path]:
    out = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths: list[Path] = []
    for entry in out.split("\0"):
        if len(entry) < 4:
            continue
        # Rename entries ("R  new -> old" in -z: two NUL-separated fields) —
        # the first field after the status code is the current path.
        paths.append(ROOT / entry[3:])
    return paths


def block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    command = (payload.get("tool_input") or {}).get("command") or ""
    if not GIT_COMMIT_RE.search(command):
        sys.exit(0)

    if not MARKER.exists():
        block(
            "COMMIT BLOCKED: no test-pass marker found. Run "
            "`python scripts/run_all_tests.py` (the full suite) and commit "
            "only after it passes."
        )

    marker_mtime = MARKER.stat().st_mtime
    stale = [
        path
        for path in changed_files()
        if path.suffix.lower() != ".md"
        and path.exists()
        and path.stat().st_mtime > marker_mtime
    ]
    if stale:
        listing = "\n".join(
            f"  - {path.relative_to(ROOT)}" for path in stale[:10]
        )
        block(
            "COMMIT BLOCKED: these files changed after the last green test "
            f"run:\n{listing}\nRe-run `python scripts/run_all_tests.py` and "
            "commit only after it passes."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
