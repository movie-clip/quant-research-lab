"""Dependency-vulnerability scan tooling (Epic 36 / US-36.2 / T-36.2.1).

Runs `pip-audit` against the backend's pinned `requirements.txt` and
`npm audit` against the frontend's locked `apps/desktop` dependency set, then
classifies each ecosystem's outcome into one of three states:

  - CLEAN                 no known vulnerabilities found
  - VULNERABILITIES_FOUND at least one known vulnerability found
  - SCAN_UNAVAILABLE      the scan itself could not run (e.g. the
                           vulnerability database was unreachable) — this is
                           distinct from CLEAN and must never be reported as
                           either a false pass or a false vulnerability

This script is deliberately NOT wired into `run_all_tests.py` or
`.github/workflows/ci.yml` — both `pip-audit` and `npm audit` require live
network access to a vulnerability database (PyPI Advisory DB / OSV; npm's
advisory endpoint), which would silently reintroduce a network dependency
into the network-free suite (US-21.1 network guard, US-21.4 frozen goldens).
It is intended to be invoked by a separate, explicitly network-permitted,
scheduled GitHub Actions workflow (T-36.2.2), or run locally/ad hoc.

Design: a pure `classify()` function per invocation, fed a `CompletedProcess`
-shaped result (returncode/stdout/stderr), plus a thin `main()` that only
shells out and reports. This split is what makes AC5 (a network hiccup must
read differently from a real vulnerability) unit-testable without a live
network call — see `services/quant-engine/app/tests/test_audit_dependencies.py`
(a separate ticket) for the pytest coverage.

`classify()` has no side effects and this module does no argv parsing or
network access at import time, so it can be imported freely from a test.

Usage:
  python scripts/audit_dependencies.py

Exit codes (distinct so a caller can branch without parsing text):
  0   both ecosystems CLEAN
  1   at least one ecosystem VULNERABILITIES_FOUND (takes priority over
      SCAN_UNAVAILABLE — a real finding must never be hidden behind an
      unrelated ecosystem's network hiccup)
  3   no VULNERABILITIES_FOUND, but at least one ecosystem SCAN_UNAVAILABLE
"""
from __future__ import annotations

import subprocess
import sys
from enum import Enum
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_REQUIREMENTS = ROOT / "services" / "quant-engine" / "requirements.txt"
FRONTEND_DIR = ROOT / "apps" / "desktop"

EXIT_CLEAN = 0
EXIT_VULNERABILITIES_FOUND = 1
EXIT_SCAN_UNAVAILABLE = 3


class Outcome(str, Enum):
    CLEAN = "CLEAN"
    VULNERABILITIES_FOUND = "VULNERABILITIES_FOUND"
    SCAN_UNAVAILABLE = "SCAN_UNAVAILABLE"


# Both `pip-audit` and `npm audit` exit non-zero for a real "vulnerabilities
# found" result AND for their own scan-side failures (e.g. can't reach the
# advisory database) — a bare exit-code check cannot tell the two apart.
# These markers, checked against the combined stdout+stderr text, are what
# distinguish a scan-unavailable condition from a real finding. Confirmed
# against pip-audit 2.10.1's connection-error framing and npm's ENOTFOUND /
# ECONNREFUSED-style network error codes.
_UNAVAILABLE_MARKERS = (
    "connection error",
    "connectionerror",
    "timed out",
    "timeout",
    "could not connect",
    "failed to establish a new connection",
    "max retries exceeded",
    "network is unreachable",
    "temporary failure in name resolution",
    "getaddrinfo failed",
    "econnrefused",
    "enotfound",
    "name or service not known",
    "no internet",
    "unable to resolve",
)


def classify(returncode: int, stdout: str, stderr: str) -> Outcome:
    """Classify one completed audit-tool invocation.

    Pure function: no subprocess, no I/O, no import-time side effects — so it
    is unit-testable against canned `CompletedProcess`-shaped inputs.

    Order of checks matters: the network/connectivity signature is checked
    FIRST, before falling back to the exit-code convention shared by both
    `pip-audit` and `npm audit --json` (0 == clean, non-zero == vulnerabilities
    found), because a scan-unavailable failure also exits non-zero.
    """
    combined = f"{stdout}\n{stderr}".lower()
    if any(marker in combined for marker in _UNAVAILABLE_MARKERS):
        return Outcome.SCAN_UNAVAILABLE
    if returncode == 0:
        return Outcome.CLEAN
    return Outcome.VULNERABILITIES_FOUND


def _run_pip_audit() -> subprocess.CompletedProcess[str]:
    # Invoked via `-m` (not the `pip-audit` console script) because pip's
    # console-script install directory is not guaranteed to be on PATH in
    # every environment (confirmed locally: `pip-audit.exe` installs outside
    # PATH on this Windows dev box) — matches the `-m ruff` / `-m vulture`
    # invocation convention already used in `scripts/detect_deadcode.py`.
    return subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", str(BACKEND_REQUIREMENTS)],
        capture_output=True,
        text=True,
        check=False,
    )


def _run_npm_audit() -> subprocess.CompletedProcess[str]:
    npm = "npm.cmd" if sys.platform == "win32" else "npm"
    return subprocess.run(
        [npm, "audit", "--prefix", str(FRONTEND_DIR), "--json"],
        capture_output=True,
        text=True,
        check=False,
    )


def main() -> int:
    results: dict[str, Outcome] = {}

    pip_result = _run_pip_audit()
    results["backend (pip-audit)"] = classify(
        pip_result.returncode, pip_result.stdout, pip_result.stderr
    )

    npm_result = _run_npm_audit()
    results["frontend (npm audit)"] = classify(
        npm_result.returncode, npm_result.stdout, npm_result.stderr
    )

    for ecosystem, outcome in results.items():
        print(f"{ecosystem}: {outcome.value}")

    if Outcome.VULNERABILITIES_FOUND in results.values():
        return EXIT_VULNERABILITIES_FOUND
    if Outcome.SCAN_UNAVAILABLE in results.values():
        return EXIT_SCAN_UNAVAILABLE
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
