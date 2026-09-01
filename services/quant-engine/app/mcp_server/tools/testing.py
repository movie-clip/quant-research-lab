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

# Wall-clock ceilings (seconds) for a single subprocess invocation. These bound
# a hung child so the tool returns a structured timeout instead of blocking an
# agent turn forever. `scripts/run_all_tests.py` owns which steps run, in what
# order, with what paths -- it neither owns nor exposes a per-call timeout, so
# defining these here restates nothing it is the source of truth for.
TIMEOUTS = {
    "full": 1800,
    "backend": 600,
    "frontend": 600,
    "typecheck": 300,
    "gate": 300,  # each check_gates subprocess (deadcode, tsc)
    "git": 30,  # git status / diff / checkout
}

# Head/tail cap for the pre-checkout diff captured by reset_goldens.
DIFF_MAX_LINES = 120

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
    command: list[str],
    cwd: Path,
    extra_env: dict[str, str] | None = None,
    *,
    timeout: float | None = None,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    # `timeout` is keyword-only so positional call sites (and the
    # `run.call_args[0][2]` extra_env assertions in the test suite) are
    # unaffected. `subprocess.run` raises `subprocess.TimeoutExpired` on expiry;
    # `_run` lets it propagate -- callers structure it.
    return subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )


def _tail(text: str, n: int = TAIL_LINES) -> list[str]:
    return [line for line in text.strip().splitlines() if line.strip()][-n:]


def _partial_output(exc: subprocess.TimeoutExpired) -> str:
    """Whatever the killed child managed to emit before the timeout fired."""
    return ((exc.stdout or "") + "\n" + (exc.stderr or "")).strip()


def _timeout_result(
    scope: str, command: list[str], cwd: Path, exc: subprocess.TimeoutExpired
) -> dict[str, Any]:
    """Structured stand-in for a run that hit its wall-clock ceiling.

    Distinguishable from a pass (`ok` True) and from a parsed failure
    (`exit_code` an int, `failures` possibly populated): here `timed_out` is
    True, `exit_code` is None, `failures` is empty.
    """
    return {
        "ok": False,
        "timed_out": True,
        "scope": scope,
        "command": " ".join(command),
        "cwd": str(cwd),
        "timeout_seconds": TIMEOUTS[scope],
        "exit_code": None,
        "failure_count": 0,
        "failures": [],
        "failures_truncated": False,
        "tail": _tail(_partial_output(exc)),
    }


def _bound_diff(text: str) -> tuple[str, bool]:
    """Head/tail-bound a git diff so a full golden regen does not flood a caller.

    Returns `(bounded_text, was_truncated)`. Anything at or under
    `2 * DIFF_MAX_LINES + 1` lines is returned whole.
    """
    lines = text.splitlines()
    if len(lines) <= 2 * DIFF_MAX_LINES + 1:
        return text.strip("\n"), False
    elided = len(lines) - 2 * DIFF_MAX_LINES
    bounded = (
        lines[:DIFF_MAX_LINES]
        + [f"... {elided} lines elided ..."]
        + lines[-DIFF_MAX_LINES:]
    )
    return "\n".join(bounded), True


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

    try:
        completed = _run(command, cwd, extra_env, timeout=TIMEOUTS[scope])
    except subprocess.TimeoutExpired as exc:
        return _timeout_result(scope, command, cwd, exc)
    # vitest and tsc write plenty to stderr; pytest keeps summaries on stdout.
    output = completed.stdout + "\n" + completed.stderr
    failures = _parse_failures(scope, output)

    return {
        "ok": completed.returncode == 0,
        "timed_out": False,
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
    # Each gate subprocess is wrapped on its own: a per-gate timeout is reported
    # and named in `timeouts`, while the gates that completed still return real
    # results.
    timeouts: list[str] = []

    try:
        deadcode = _run(
            [sys.executable, str(DEADCODE_SCRIPT), "--strict"],
            ROOT,
            timeout=TIMEOUTS["gate"],
        )
        deadcode_result = {
            "ok": deadcode.returncode == 0,
            "timed_out": False,
            "tail": _tail(deadcode.stdout + "\n" + deadcode.stderr, 12),
        }
    except subprocess.TimeoutExpired as exc:
        timeouts.append("deadcode")
        deadcode_result = {
            "ok": False,
            "timed_out": True,
            "tail": _tail(_partial_output(exc), 12),
        }

    try:
        typecheck = _run(
            [npx_command(), "tsc", "--noEmit"], FRONTEND_DIR, timeout=TIMEOUTS["gate"]
        )
        typecheck_result = {
            "ok": typecheck.returncode == 0,
            "timed_out": False,
            "errors": _parse_failures(
                "typecheck", typecheck.stdout + "\n" + typecheck.stderr
            ),
        }
    except subprocess.TimeoutExpired:
        timeouts.append("typecheck")
        typecheck_result = {"ok": False, "timed_out": True, "errors": []}

    try:
        drift = _run(
            ["git", "status", "--porcelain", "--", GOLDENS_PATH],
            ROOT,
            timeout=TIMEOUTS["git"],
        )
        # Usually an FMP-cache artifact rather than a real change -- call
        # reset_goldens() unless this work genuinely changed dashboard output.
        goldens_drifted = bool(drift.stdout.strip())
    except subprocess.TimeoutExpired:
        timeouts.append("goldens")
        goldens_drifted = False

    return {
        "deadcode": deadcode_result,
        "typecheck": typecheck_result,
        "goldens_drifted": goldens_drifted,
        "timeouts": timeouts,
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
    """Discard `dashboardGoldens.ts` drift, recording what was discarded first."""
    timed_out = False

    # Capture what is about to be thrown away BEFORE the checkout, so a caller
    # (and any audit trail) still has the pre-checkout state even if the
    # checkout itself later fails.
    try:
        stat = _run(
            ["git", "diff", "--stat", "--", GOLDENS_PATH], ROOT, timeout=TIMEOUTS["git"]
        )
        diff_stat = stat.stdout.strip()
    except subprocess.TimeoutExpired:
        timed_out = True
        diff_stat = ""

    try:
        diff = _run(
            ["git", "diff", "--", GOLDENS_PATH], ROOT, timeout=TIMEOUTS["git"]
        )
        bounded_diff, diff_truncated = _bound_diff(diff.stdout)
    except subprocess.TimeoutExpired:
        timed_out = True
        bounded_diff, diff_truncated = "", False

    try:
        completed = _run(
            ["git", "checkout", "--", GOLDENS_PATH], ROOT, timeout=TIMEOUTS["git"]
        )
        ok = completed.returncode == 0
        stderr = completed.stderr.strip()
    except subprocess.TimeoutExpired:
        timed_out = True
        ok = False
        stderr = f"git checkout timed out after {TIMEOUTS['git']}s"

    return {
        "ok": ok,
        "path": GOLDENS_PATH,
        "stderr": stderr,
        # No drift => empty stat, empty diff, discarded False: nothing was thrown
        # away.
        "discarded": bool(diff_stat),
        "diff_stat": diff_stat,
        "diff": bounded_diff,
        "diff_truncated": diff_truncated,
        "timed_out": timed_out,
    }
