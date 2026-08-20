"""Git-level `pre-commit` hook entry point (US-36.1 / T-36.1.1).

Wired via `core.hooksPath` -> `scripts/githooks/pre-commit`, which `exec`s
this script. Unlike `pre_commit_gate.py` (the Claude-Code-specific
`PreToolUse` duplicate), this is the actual, tool-independent enforcement
boundary: git invokes it for every `git commit`, regardless of which tool or
terminal issued it — Bash, PowerShell, a human's own shell, a future agent
runtime. No stdin JSON to parse and no command-sniffing needed; git only
calls this hook when a commit is actually about to happen.

The staleness rule itself (marker existence, mtime comparison, the `.md`
exemption) lives once in `_commit_gate.py` and is shared with
`pre_commit_gate.py` — do not re-derive it here.

Exit codes (git hook contract — see githooks(5)):
  0 — allow the commit
  1 — abort it; the printed message is shown to the user
"""

from __future__ import annotations

import sys

from _commit_gate import check


def main() -> int:
    message = check()
    if message:
        print(message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
