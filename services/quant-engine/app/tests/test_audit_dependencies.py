"""`scripts/audit_dependencies.py`'s `classify()` (Epic 36 / US-36.2 AC5).

`classify()` turns one completed `pip-audit` / `npm audit` invocation
(returncode/stdout/stderr) into an `Outcome` — `CLEAN`, `VULNERABILITIES_FOUND`,
or `SCAN_UNAVAILABLE`. Both tools exit non-zero for a real "vulnerabilities
found" result AND for their own scan-side failures (a database unreachable,
a timeout), so a bare exit-code check cannot tell the two apart. AC5's whole
point is that a network hiccup must never read as a false "clean" pass NOR as
a false "vulnerability found" report — this file pins that distinction.

`scripts/audit_dependencies.py` lives at the repo root, not under
`services/quant-engine/`. It is the first script in this repo to get pytest
coverage, so there is no existing `sys.path` precedent to copy — reached here
by inserting `scripts/` onto `sys.path` directly (see REPO_ROOT below). No
production code under `scripts/` or `app/` is modified by this file; `classify`
is a pure function (no subprocess, no I/O), so no market-data mocking or
network guard interaction is needed here.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from audit_dependencies import Outcome, classify  # noqa: E402  (path set up above)


# Each case is (id, returncode, stdout, stderr, expected). Real-shaped, not
# synthetic one-liners — copied from the two tools' actual output framing so a
# wording change in a future pip-audit/npm-audit version is what would break
# this test, not an invented shorthand that never occurs in practice.

_PIP_AUDIT_FOUND_STDOUT = """\
Found 1 known vulnerability in 1 package
Name    Version ID                  Fix Versions
------- ------- -------------------- ------------
pypdf   6.9.1   GHSA-xxxx-xxxx-xxxx  6.9.2
"""

_PIP_AUDIT_CLEAN_STDOUT = "No known vulnerabilities found\n"

_PIP_AUDIT_CONNECTION_ERROR_STDERR = """\
Traceback (most recent call last):
  File "pip_audit/_service/pypi.py", line 89, in _get_metadata
    response = await session.get(url)
  ...
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='pypi.org', port=443): \
Max retries exceeded with url: /pypi/pypdf/json \
(Caused by NewConnectionError('Failed to establish a new connection: \
[Errno -3] Temporary failure in name resolution'))
"""

_NPM_AUDIT_FOUND_STDOUT = """\
{
  "auditReportVersion": 2,
  "vulnerabilities": {
    "@babel/core": {
      "name": "@babel/core",
      "severity": "low",
      "isDirect": false,
      "via": ["GHSA-yyyy-yyyy-yyyy"]
    }
  },
  "metadata": {"vulnerabilities": {"low": 1, "total": 1}}
}
"""

_NPM_AUDIT_CLEAN_STDOUT = """\
{
  "auditReportVersion": 2,
  "vulnerabilities": {},
  "metadata": {"vulnerabilities": {"total": 0}}
}
"""

# npm's own network-failure framing (ENOTFOUND / getaddrinfo), distinct
# wording from pip-audit's — this is the half order 07's report flagged as
# untested against a real npm failure (network was reachable in that session).
_NPM_AUDIT_NETWORK_ERROR_STDERR = """\
npm error code ENOTFOUND
npm error syscall getaddrinfo
npm error errno ENOTFOUND
npm error network request to https://registry.npmjs.org/-/npm/v1/security/audits/quick \
failed, reason: getaddrinfo ENOTFOUND registry.npmjs.org
npm error A complete log of this run can be found in: /home/user/.npm/_logs/2026-08-20.log
"""

CASES: list[tuple[str, int, str, str, Outcome]] = [
    (
        "pip_audit_found",
        1,
        _PIP_AUDIT_FOUND_STDOUT,
        "",
        Outcome.VULNERABILITIES_FOUND,
    ),
    (
        "npm_audit_found",
        1,
        _NPM_AUDIT_FOUND_STDOUT,
        "",
        Outcome.VULNERABILITIES_FOUND,
    ),
    (
        "pip_audit_clean",
        0,
        _PIP_AUDIT_CLEAN_STDOUT,
        "",
        Outcome.CLEAN,
    ),
    (
        "npm_audit_clean",
        0,
        _NPM_AUDIT_CLEAN_STDOUT,
        "",
        Outcome.CLEAN,
    ),
    (
        "pip_audit_connection_error",
        1,
        "",
        _PIP_AUDIT_CONNECTION_ERROR_STDERR,
        Outcome.SCAN_UNAVAILABLE,
    ),
    (
        "npm_audit_network_error",
        1,
        "",
        _NPM_AUDIT_NETWORK_ERROR_STDERR,
        Outcome.SCAN_UNAVAILABLE,
    ),
]


@pytest.mark.parametrize(
    "returncode, stdout, stderr, expected",
    [case[1:] for case in CASES],
    ids=[case[0] for case in CASES],
)
def test_classify_representative_cases(
    returncode: int, stdout: str, stderr: str, expected: Outcome
) -> None:
    """One case per named scenario, so a broken marker list names the exact
    tool/ecosystem that regressed rather than a generic parametrize failure."""
    assert classify(returncode, stdout, stderr) == expected


def test_scan_unavailable_never_reads_as_clean() -> None:
    """AC5, the false-pass half: a connection failure exits non-zero for both
    tools, so a classifier that only looked at the exit code would already get
    this right by accident. This pins the network-error TEXT as the actual
    signal, not the exit code — swap the returncode below and the assertion
    still must hold, because the marker check runs first."""
    outcome = classify(1, "", _PIP_AUDIT_CONNECTION_ERROR_STDERR)
    assert outcome is Outcome.SCAN_UNAVAILABLE
    assert outcome is not Outcome.CLEAN


def test_scan_unavailable_never_reads_as_vulnerabilities_found() -> None:
    """AC5, the false-alarm half: stdout carries real "found" phrasing (as
    pip-audit's own output does when the vulnerability check throws mid-scan)
    while stderr carries the connection-error signature. The unavailable
    marker must win — a real finding must never be manufactured from a
    scan that could not actually complete."""
    outcome = classify(1, _PIP_AUDIT_FOUND_STDOUT, _PIP_AUDIT_CONNECTION_ERROR_STDERR)
    assert outcome is Outcome.SCAN_UNAVAILABLE
    assert outcome is not Outcome.VULNERABILITIES_FOUND


def test_unavailable_marker_matched_case_insensitively() -> None:
    """The production marker list is lower-cased before matching; pin that
    behaviour directly rather than relying on it holding by coincidence in the
    other cases above, all of which happen to use lowercase/mixed source text."""
    outcome = classify(1, "", "TEMPORARY FAILURE IN NAME RESOLUTION")
    assert outcome is Outcome.SCAN_UNAVAILABLE


def test_empty_output_with_zero_exit_is_clean() -> None:
    """Boundary case distinct from the "No known vulnerabilities found" case
    above: nothing printed at all, zero exit. Neither marker list nor
    vulnerability text is present, so this must fall through to CLEAN rather
    than to VULNERABILITIES_FOUND or SCAN_UNAVAILABLE by default."""
    assert classify(0, "", "") == Outcome.CLEAN
