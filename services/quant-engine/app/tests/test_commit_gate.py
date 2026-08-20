"""The commit-freshness gate must block regardless of which tool issued the
commit (Epic 36 / US-36.1, T-36.1.2).

F-R1 (`docs/product/review-2026-08-20-findings.md`): a fix was claimed
("fixed 2026-08-20") for exactly this gap, but the fix only ever covered the
Claude Code `Bash` tool's `PreToolUse` hook (`pre_commit_gate.py`) — a commit
issued through any other tool (PowerShell, a human's own terminal) walked
straight past it. Nothing caught that the claim was false. T-36.1.1 closed the
gap for real with a git-level `pre-commit` hook
(`scripts/hooks/git_pre_commit.py`, wired via `core.hooksPath`); this module
is what makes a *future* regression of either path mechanical instead of
another unverified claim.

Both `git_pre_commit.py` and `pre_commit_gate.py` share their staleness rule
via `scripts/hooks/_commit_gate.py`'s `check()`. `_commit_gate.MARKER` and
`_commit_gate.ROOT` are computed from `Path(__file__).resolve().parents[...]`
— i.e. from wherever the module file itself lives — not from an env var or
`cwd` that a test could simply point elsewhere. So the only way to exercise
the REAL entry points against an isolated tree (rather than reimplementing
their logic) is to give each fixture repo its own copy of
`scripts/hooks/*.py`, at the same relative depth (`<repo>/scripts/hooks/`),
copied fresh from the real files on every test run. Nothing in this file
re-derives the staleness rule, the `.md` exemption, or the message text —
doing so would be exactly the "duplicated computation, invisible to any
single lane" pattern `_commit_gate.py`'s own module docstring warns against.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
REAL_HOOKS_DIR = REPO_ROOT / "scripts" / "hooks"
HOOK_FILES = ["git_pre_commit.py", "pre_commit_gate.py", "_commit_gate.py"]

SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import run_all_tests  # noqa: E402  (path set up above; precedent: test_manage_cache_cli.py)

# Fixed epoch anchors rather than `time.time()`-relative ordering: some
# filesystems truncate mtimes to whole seconds, and a test that relies on
# "write A, sleep, write B" to establish ordering is flaky by construction.
# Explicit, widely-separated epochs make every staleness comparison in this
# file deterministic regardless of clock resolution.
_T_OLD = 1_700_000_000
_T_MARKER = 1_700_001_000
_T_NEW = 1_700_002_000


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _write(path: Path, content: str, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.utime(path, (mtime, mtime))


@pytest.fixture()
def hook_repo(tmp_path: Path) -> Path:
    """A throwaway git repo carrying a live copy of the real hook modules.

    Layout mirrors the real repo exactly two levels down from
    `scripts/hooks/`, which is what `_commit_gate.ROOT` needs to resolve to
    this fixture's root instead of the real checkout's. `scripts/hooks/*.py`
    is committed in the baseline so it never itself shows up as a "changed"
    file in `git status` and pollutes the staleness comparisons the tests
    below are trying to isolate. `code.py` (non-`.md`) and `notes.md` (`.md`)
    are committed too, so each test can produce a realistic "existing tracked
    file modified after the marker" change rather than a synthetic untracked
    one.
    """
    repo = tmp_path / "repo"
    hooks_dir = repo / "scripts" / "hooks"
    hooks_dir.mkdir(parents=True)
    for name in HOOK_FILES:
        (hooks_dir / name).write_text(
            (REAL_HOOKS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )

    _run_git(["init", "--quiet"], repo)
    _run_git(["config", "user.email", "test@example.invalid"], repo)
    _run_git(["config", "user.name", "Commit Gate Test"], repo)
    _run_git(["config", "commit.gpgsign", "false"], repo)

    # Mirrors the real repo's `.gitignore` (`.claude/.last-test-pass`,
    # `__pycache__/`) — without it, the marker file and the `__pycache__/`
    # directory produced by running the copied hook scripts show up as
    # untracked "changed" files in every scenario below and are mistaken for
    # stale ones, which is not a hypothetical: it is exactly what happened
    # the first time this fixture ran.
    _write(repo / ".gitignore", ".claude/.last-test-pass\n__pycache__/\n", _T_OLD)
    _write(repo / "code.py", "print('baseline')\n", _T_OLD)
    _write(repo / "notes.md", "# baseline notes\n", _T_OLD)
    _run_git(["add", ".gitignore", "code.py", "notes.md", "scripts"], repo)
    _run_git(["commit", "--quiet", "-m", "baseline"], repo)

    return repo


def _write_marker(repo: Path, mtime: float) -> None:
    _write(repo / ".claude" / ".last-test-pass", "2026-08-20T00:00:00\n", mtime)


def _invoke_git_hook(repo: Path) -> subprocess.CompletedProcess[str]:
    """Exercise the real, tool-independent boundary: what git itself invokes
    via `core.hooksPath` -> `scripts/githooks/pre-commit` -> this script, for
    a commit issued through ANY tool or terminal."""
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "hooks" / "git_pre_commit.py")],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def _invoke_bash_hook(
    repo: Path, command: str = "git commit -m 'msg'"
) -> subprocess.CompletedProcess[str]:
    """Exercise the Claude Code `PreToolUse` duplicate exactly as the harness
    drives it: JSON-over-stdin with `tool_input.command`."""
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        [sys.executable, str(repo / "scripts" / "hooks" / "pre_commit_gate.py")],
        cwd=repo,
        input=payload,
        capture_output=True,
        text=True,
    )


# ---------------------------------------------------------------------------
# Missing marker
# ---------------------------------------------------------------------------


def test_git_hook_blocks_when_marker_missing(hook_repo: Path) -> None:
    result = _invoke_git_hook(hook_repo)
    assert result.returncode == 1
    assert "COMMIT BLOCKED" in result.stderr
    assert "no test-pass marker found" in result.stderr


def test_bash_hook_blocks_when_marker_missing(hook_repo: Path) -> None:
    """AC3: the Bash path must reach the identical block for the identical
    condition, with its own protocol's exit code (2, not git's 1)."""
    result = _invoke_bash_hook(hook_repo)
    assert result.returncode == 2
    assert "COMMIT BLOCKED" in result.stderr
    assert "no test-pass marker found" in result.stderr


# ---------------------------------------------------------------------------
# Stale file (AC1/AC2 for the git path, AC3 for the Bash path)
# ---------------------------------------------------------------------------


def test_git_hook_blocks_on_stale_file(hook_repo: Path) -> None:
    _write_marker(hook_repo, _T_MARKER)
    _write(hook_repo / "code.py", "print('changed')\n", _T_NEW)

    result = _invoke_git_hook(hook_repo)

    assert result.returncode == 1
    assert "COMMIT BLOCKED" in result.stderr
    assert "changed after the last green test run" in result.stderr
    assert "code.py" in result.stderr


def test_bash_hook_blocks_on_stale_file(hook_repo: Path) -> None:
    """This is the exact regression the epic exists to catch: before
    T-36.1.1, this staleness condition was only ever checked when the commit
    happened to be issued through the Bash tool. This case, run against
    `git_pre_commit.py` above and `pre_commit_gate.py` here, is what pins
    that both paths now agree — a future refactor that narrows the shared
    check for only one entry point fails one of this pair, not neither."""
    _write_marker(hook_repo, _T_MARKER)
    _write(hook_repo / "code.py", "print('changed')\n", _T_NEW)

    result = _invoke_bash_hook(hook_repo)

    assert result.returncode == 2
    assert "COMMIT BLOCKED" in result.stderr
    assert "changed after the last green test run" in result.stderr
    assert "code.py" in result.stderr


# ---------------------------------------------------------------------------
# Fresh tree (AC4)
# ---------------------------------------------------------------------------


def test_git_hook_allows_fresh_tree(hook_repo: Path) -> None:
    _write(hook_repo / "code.py", "print('changed')\n", _T_OLD)
    _write_marker(hook_repo, _T_MARKER)

    result = _invoke_git_hook(hook_repo)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_bash_hook_allows_fresh_tree(hook_repo: Path) -> None:
    _write(hook_repo / "code.py", "print('changed')\n", _T_OLD)
    _write_marker(hook_repo, _T_MARKER)

    result = _invoke_bash_hook(hook_repo)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# .md exemption (AC5)
# ---------------------------------------------------------------------------


def test_git_hook_allows_md_only_change(hook_repo: Path) -> None:
    _write_marker(hook_repo, _T_MARKER)
    _write(hook_repo / "notes.md", "# updated notes\n", _T_NEW)

    result = _invoke_git_hook(hook_repo)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_bash_hook_allows_md_only_change(hook_repo: Path) -> None:
    _write_marker(hook_repo, _T_MARKER)
    _write(hook_repo / "notes.md", "# updated notes\n", _T_NEW)

    result = _invoke_bash_hook(hook_repo)

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# Bash-path command sniffing: must not fire for a non-commit command, even
# when the marker/staleness state would otherwise block. Guards against the
# sniffing regressing into "block every Bash call" (which would be caught
# immediately in practice) or, more subtly, sniffing too narrowly so a real
# `git commit` slips through unrecognised.
# ---------------------------------------------------------------------------


def test_bash_hook_ignores_non_commit_commands(hook_repo: Path) -> None:
    # No marker at all — every case above shows this blocks a real commit.
    result = _invoke_bash_hook(hook_repo, command="ls -la")

    assert result.returncode == 0
    assert result.stdout == ""
    assert result.stderr == ""


# ---------------------------------------------------------------------------
# `run_all_tests.py` bootstrap idempotency
# ---------------------------------------------------------------------------


def test_ensure_git_hooks_wired_is_idempotent() -> None:
    """`ensure_git_hooks_wired()` runs on every `run_all_tests.py` invocation
    (T-36.1.1) so `core.hooksPath` self-heals in any session that has not run
    the one-time manual `git config` step. Calling it twice — the shape of
    two agent sessions, or a session plus CI, both running the suite against
    the same checkout — must not raise, and must leave the real repo's
    `core.hooksPath` pointed at `scripts/githooks` either way. This is the
    one check in this file that runs against the REAL repo's git config
    (the function has no fixture-repo indirection point, unlike the two hook
    scripts above) — safe because the call is idempotent and is exactly what
    `python scripts/run_all_tests.py` already does on every green run.
    """
    run_all_tests.ensure_git_hooks_wired()
    run_all_tests.ensure_git_hooks_wired()

    result = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "scripts/githooks"


# ---------------------------------------------------------------------------
# End-to-end wiring: does the gate actually FIRE?
#
# Everything above invokes the hook scripts directly, which proves the
# staleness *logic* cannot regress. It does not prove the gate is reachable.
# The original F-R1 defect was never a logic bug — it was a gate that existed
# and never ran, and a test suite that validates only the logic would have
# passed against it happily.
#
# So these tests drive a real `git commit` through a repo wired exactly the
# way the real one is, exercising the parts nothing else covers: the
# `scripts/githooks/pre-commit` shell wrapper, its interpreter discovery,
# `core.hooksPath` resolution, and git's own decision to invoke the file.
# ---------------------------------------------------------------------------

REAL_GITHOOK = REPO_ROOT / "scripts" / "githooks" / "pre-commit"


@pytest.fixture()
def wired_repo(hook_repo: Path) -> Path:
    """`hook_repo`, plus the real shell wrapper and `core.hooksPath` set —
    i.e. a repo where `git commit` should be gated by the real mechanism."""
    githooks = hook_repo / "scripts" / "githooks"
    githooks.mkdir(parents=True, exist_ok=True)
    wrapper = githooks / "pre-commit"
    wrapper.write_text(REAL_GITHOOK.read_text(encoding="utf-8"), encoding="utf-8")
    wrapper.chmod(0o755)

    _run_git(["config", "core.hooksPath", "scripts/githooks"], hook_repo)
    _run_git(["add", "scripts"], hook_repo)
    _run_git(["commit", "--quiet", "--no-verify", "-m", "wire hooks"], hook_repo)
    return hook_repo


def _attempt_commit(repo: Path) -> subprocess.CompletedProcess[str]:
    """A real `git commit` — the thing a human or any tool actually runs."""
    return subprocess.run(
        ["git", "commit", "-m", "attempt"],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def test_real_git_commit_is_blocked_when_marker_missing(wired_repo: Path) -> None:
    _write(wired_repo / "code.py", "print('changed')\n", _T_NEW)
    _run_git(["add", "code.py"], wired_repo)

    result = _attempt_commit(wired_repo)

    assert result.returncode != 0, (
        "git commit succeeded with no test-pass marker — the hook did not "
        f"fire. stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "COMMIT BLOCKED" in result.stderr


def test_real_git_commit_is_blocked_on_stale_file(wired_repo: Path) -> None:
    _write_marker(wired_repo, _T_MARKER)
    _write(wired_repo / "code.py", "print('stale')\n", _T_NEW)
    _run_git(["add", "code.py"], wired_repo)

    result = _attempt_commit(wired_repo)

    assert result.returncode != 0, "stale non-.md change was not blocked"
    assert "COMMIT BLOCKED" in result.stderr
    assert "code.py" in result.stderr


def test_real_git_commit_is_allowed_when_fresh(wired_repo: Path) -> None:
    """The other half of the contract: a wired gate that blocks everything is
    just as broken as one that blocks nothing, and far more likely to be
    ripped out."""
    _write(wired_repo / "code.py", "print('fresh')\n", _T_OLD)
    _run_git(["add", "code.py"], wired_repo)
    _write_marker(wired_repo, _T_MARKER)

    result = _attempt_commit(wired_repo)

    assert result.returncode == 0, (
        f"a fresh tree was blocked. stdout={result.stdout!r} "
        f"stderr={result.stderr!r}"
    )


# ---------------------------------------------------------------------------
# Shipping state: the hook must be tracked, and tracked EXECUTABLE.
#
# This checkout has `core.filemode=false` (Windows), under which a plain
# `git add` records a `chmod +x`-ed file as mode 100644. Git applies the
# stored mode on checkout regardless of the cloning machine's own filemode
# setting, so a 100644 hook is silently non-executable on Linux and CI —
# where git skips it without a word. The gate would then be inert for
# everyone except the person who created it, which is indistinguishable from
# the F-R1 state this epic closed.
#
# `git add --chmod=+x scripts/githooks/pre-commit` is the fix.
# ---------------------------------------------------------------------------


def test_git_hook_is_tracked_and_executable() -> None:
    result = subprocess.run(
        ["git", "ls-files", "--stage", "--", "scripts/githooks/pre-commit"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    entry = result.stdout.strip()

    assert entry, (
        "scripts/githooks/pre-commit is not tracked by git. A clone would not "
        "receive the commit hook at all, leaving every other checkout "
        "ungated.\n"
        "Fix: git add --chmod=+x scripts/githooks/pre-commit"
    )

    mode = entry.split()[0]
    assert mode == "100755", (
        f"scripts/githooks/pre-commit is tracked as mode {mode}, not 100755. "
        "Git applies the stored mode on checkout, so a non-executable hook is "
        "silently skipped on Linux and in CI — the gate exists but never "
        "fires.\n"
        "Fix: git add --chmod=+x scripts/githooks/pre-commit"
    )
