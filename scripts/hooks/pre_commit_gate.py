"""PreToolUse hook: block `git commit` unless the full test suite passed
on the current working tree.

This is the Claude-Code-specific half of the commit-freshness gate — it fires
only for the `Bash` tool (wired in `.claude/settings.json`), parses the tool's
JSON-over-stdin payload, and sniffs the command text for `git commit`. It is a
faster-feedback duplicate inside agent sessions; the actual, tool-independent
enforcement boundary is the git-level hook (`scripts/githooks/pre-commit` ->
`git_pre_commit.py`, wired via `core.hooksPath`). The staleness rule itself
(marker existence, mtime comparison, the `.md` exemption) is shared with that
hook via `_commit_gate.py` — do not re-derive it here.

Exit codes (Claude Code hook contract):
  0 — allow the tool call
  2 — block it; stderr is fed back to the agent
"""

from __future__ import annotations

import json
import re
import sys

from _commit_gate import check

GIT_COMMIT_RE = re.compile(r"\bgit\b[^|;&]*\bcommit\b")


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

    message = check()
    if message:
        block(message)

    sys.exit(0)


if __name__ == "__main__":
    main()
