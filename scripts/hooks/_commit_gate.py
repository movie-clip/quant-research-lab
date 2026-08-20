"""Shared commit-freshness gate logic (US-36.1 / T-36.1.1).

`scripts/run_all_tests.py` writes a marker file (.claude/.last-test-pass) when
the whole suite is green. A commit should be blocked if the marker is missing
or if any changed non-`.md` file has been modified after the marker was
written — i.e. the tree the tests blessed is not the tree being committed.

This module is the ONE place that rule lives. Two entry points call into it,
each wrapping the same `check()` result in its own protocol:

  - `pre_commit_gate.py` — the Claude Code `PreToolUse` hook, matched on the
    `Bash` tool only. JSON-over-stdin input, sniffs the command for `git
    commit`, exits 2 to block (Claude Code hook contract).
  - `git_pre_commit.py` — the real git-level `pre-commit` hook (wired via
    `core.hooksPath` -> `scripts/githooks/pre-commit`), which git invokes for
    *any* `git commit` regardless of which tool or terminal issued it. No
    stdin JSON, no command-sniffing needed — git only calls this hook when a
    commit is actually about to happen. Exits 1 to block (git hook contract).

Markdown files are exempt (they cannot affect the suite), so the update-docs
close-out flow can commit doc reconciliation without a full re-run. Statement
PDFs under docs/ are NOT exempt — they feed golden generation.

A change to the staleness rule or the `.md` exemption belongs HERE, not in
either entry point — duplicating this logic is exactly how one path silently
regresses while the other stays fixed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MARKER = ROOT / ".claude" / ".last-test-pass"

MISSING_MARKER_MESSAGE = (
    "COMMIT BLOCKED: no test-pass marker found. Run "
    "`python scripts/run_all_tests.py` (the full suite) and commit "
    "only after it passes."
)


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


def stale_files_message(stale: list[Path]) -> str:
    listing = "\n".join(f"  - {path.relative_to(ROOT)}" for path in stale[:10])
    return (
        "COMMIT BLOCKED: these files changed after the last green test "
        f"run:\n{listing}\nRe-run `python scripts/run_all_tests.py` and "
        "commit only after it passes."
    )


def check() -> str | None:
    """Return a block message if the commit should be blocked, else `None`."""
    if not MARKER.exists():
        return MISSING_MARKER_MESSAGE

    marker_mtime = MARKER.stat().st_mtime
    stale = [
        path
        for path in changed_files()
        if path.suffix.lower() != ".md"
        and path.exists()
        and path.stat().st_mtime > marker_mtime
    ]
    if stale:
        return stale_files_message(stale)

    return None
