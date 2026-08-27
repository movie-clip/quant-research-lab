"""Running the suite and the mechanical gates, for agents.

Thin wrappers only. `scripts/run_all_tests.py` and `scripts/detect_deadcode.py`
remain the single source of truth for how tests and gates run; nothing here
restates a step list or a path. The path constants below are IMPORTED from the
canonical runner so that a layout change follows automatically.

Return values are deliberately bounded. These functions are called from inside
an agent's context window, so a failing suite must come back as parsed failures
plus a short tail -- never the full stdout dump.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    """Locate the repo root by walking up for `scripts/run_all_tests.py`.

    Deliberately not `parents[N]` -- an index silently points somewhere wrong
    the moment this module moves a level, and the failure mode (running commands
    in the wrong cwd) is invisible.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "scripts" / "run_all_tests.py").is_file():
            return parent
    raise RuntimeError(f"could not locate repo root from {__file__}")


ROOT = _repo_root()
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from run_all_tests import (  # noqa: E402  (path must be set up first)
    BACKEND_DIR,
    FRONTEND_DIR,
    TEST_PASS_MARKER,
    npx_command,
)

GOLDENS_PATH = "apps/desktop/src/test/dashboardGoldens.ts"
DEADCODE_SCRIPT = ROOT / "scripts" / "detect_deadcode.py"
RUN_ALL_TESTS = ROOT / "scripts" / "run_all_tests.py"

VALID_SCOPES = ("backend", "frontend", "typecheck", "full")
MAX_FAILURES = 25
TAIL_LINES = 15

# `-q` pytest summary lines: "FAILED path::test - AssertionError: ..."
_PYTEST_FAILURE = re.compile(
    r"^(?:FAILED|ERROR)\s+([^\s:]+)(?:::(\S+))?\s*(?:-\s*(.*))?$", re.MULTILINE
)
# tsc: "src/app/Foo.tsx(12,3): error TS2345: Argument of type ..."
_TSC_ERROR = re.compile(r"^(\S+?)\((\d+),(\d+)\):\s+(error TS\d+:.*)$", re.MULTILINE)
# vitest prints far less structured output than pytest; match the FAIL header
# and lean on `tail` for the detail rather than pretending to parse more.
_VITEST_FAILURE = re.compile(r"^\s*FAIL\s+(\S+)\s*(?:>\s*(.*))?$", re.MULTILINE)


def _run(
    command: list[str], cwd: Path, extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        command, cwd=str(cwd), capture_output=True, text=True, env=env
    )


def _tail(text: str, n: int = TAIL_LINES) -> list[str]:
    return [line for line in text.strip().splitlines() if line.strip()][-n:]


def _parse_failures(scope: str, output: str) -> list[dict[str, Any]]:
    if scope in ("backend", "full"):
        found = [
            {
                "file": m.group(1),
                "test": m.group(2),
                "message": (m.group(3) or "").strip(),
            }
            for m in _PYTEST_FAILURE.finditer(output)
        ]
    elif scope == "typecheck":
        found = [
            {
                "file": m.group(1),
                "line": int(m.group(2)),
                "column": int(m.group(3)),
                "message": m.group(4),
            }
            for m in _TSC_ERROR.finditer(output)
        ]
    elif scope == "frontend":
        found = [
            {"file": m.group(1), "test": (m.group(2) or "").strip(), "message": ""}
            for m in _VITEST_FAILURE.finditer(output)
        ]
    else:
        found = []
    return found[:MAX_FAILURES]


def run_tests_impl(
    scope: str = "backend", path: str | None = None, k: str | None = None
) -> dict[str, Any]:
    """Run one scope of the suite and return a bounded, parsed result."""
    scope = (scope or "backend").lower()
    extra_env: dict[str, str] | None = None

    if scope == "full":
        command = [sys.executable, str(RUN_ALL_TESTS)]
        cwd = ROOT
    elif scope == "backend":
        command = [sys.executable, "-m", "pytest", "-q", "--no-header"]
        if path:
            command.append(path)
        if k:
            command += ["-k", k]
        cwd = BACKEND_DIR
        # Narrow iteration skips the golden freshness check (testing pack,
        # "Running tests"). `full` deliberately does not -- that is the gate.
        extra_env = {"SKIP_GOLDEN_FRESHNESS_CHECK": "1"}
    elif scope == "frontend":
        command = [npx_command(), "vitest", "run"]
        if path:
            command.append(path)
        if k:
            command += ["-t", k]
        cwd = FRONTEND_DIR
    elif scope == "typecheck":
        command = [npx_command(), "tsc", "--noEmit"]
        cwd = FRONTEND_DIR
    else:
        return {
            "ok": False,
            "scope": scope,
            "error": f"unknown scope: {scope!r}",
            "valid_scopes": list(VALID_SCOPES),
        }

    completed = _run(command, cwd, extra_env)
    # vitest and tsc write plenty to stderr; pytest keeps summaries on stdout.
    output = completed.stdout + "\n" + completed.stderr
    failures = _parse_failures(scope, output)

    return {
        "ok": completed.returncode == 0,
        "scope": scope,
        "command": " ".join(command),
        "cwd": str(cwd),
        "exit_code": completed.returncode,
        "failure_count": len(failures),
        "failures": failures,
        "failures_truncated": len(failures) == MAX_FAILURES,
        "tail": _tail(output),
    }


def check_gates_impl() -> dict[str, Any]:
    """Report whether the mechanical gates would pass, without running the suite.

    Answers the question a lane actually has -- "will my commit be blocked?" --
    before it tries to commit and gets bounced by the pre-commit hook.
    """
    deadcode = _run([sys.executable, str(DEADCODE_SCRIPT), "--strict"], ROOT)
    typecheck = _run([npx_command(), "tsc", "--noEmit"], FRONTEND_DIR)
    drift = _run(["git", "status", "--porcelain", "--", GOLDENS_PATH], ROOT)

    return {
        "deadcode": {
            "ok": deadcode.returncode == 0,
            "tail": _tail(deadcode.stdout + "\n" + deadcode.stderr, 12),
        },
        "typecheck": {
            "ok": typecheck.returncode == 0,
            "errors": _parse_failures(
                "typecheck", typecheck.stdout + "\n" + typecheck.stderr
            ),
        },
        # Usually an FMP-cache artifact rather than a real change -- call
        # reset_goldens() unless this work genuinely changed dashboard output.
        "goldens_drifted": bool(drift.stdout.strip()),
        "commit_gate": {
            "marker_present": TEST_PASS_MARKER.exists(),
            "marker_path": str(TEST_PASS_MARKER),
            "note": (
                "The hook requires this marker to be FRESHER than every changed "
                "non-.md file; presence alone does not mean a commit will pass."
            ),
        },
    }


def reset_goldens_impl() -> dict[str, Any]:
    """Discard `dashboardGoldens.ts` drift. Never hand-edit that file."""
    completed = _run(["git", "checkout", "--", GOLDENS_PATH], ROOT)
    return {
        "ok": completed.returncode == 0,
        "path": GOLDENS_PATH,
        "stderr": completed.stderr.strip(),
    }
