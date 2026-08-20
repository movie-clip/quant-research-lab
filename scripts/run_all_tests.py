from __future__ import annotations

import argparse
import datetime
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "services" / "quant-engine"
FRONTEND_DIR = ROOT / "apps" / "desktop"
BACKEND_REQUIREMENTS = BACKEND_DIR / "requirements.txt"
GOLDEN_GENERATOR = BACKEND_DIR / "app" / "scripts" / "export_dashboard_goldens.py"
# Written on a fully green run; the pre_commit_gate hook refuses `git commit`
# when it is missing or older than the working-tree changes being committed.
TEST_PASS_MARKER = ROOT / ".claude" / ".last-test-pass"


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def npx_command() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def check_environment() -> list[str]:
    errors: list[str] = []
    if not BACKEND_DIR.exists():
        errors.append(f"missing backend directory: {BACKEND_DIR}")
    if not FRONTEND_DIR.exists():
        errors.append(f"missing frontend directory: {FRONTEND_DIR}")
    if not BACKEND_REQUIREMENTS.exists():
        errors.append(f"missing backend requirements file: {BACKEND_REQUIREMENTS}")
    if not GOLDEN_GENERATOR.exists():
        errors.append(f"missing golden generator: {GOLDEN_GENERATOR}")
    if shutil.which(sys.executable) is None:
        errors.append(f"python executable not found: {sys.executable}")
    if shutil.which(npm_command()) is None:
        errors.append("npm executable not found")
    return errors


def ensure_git_hooks_wired() -> None:
    """Idempotently point git at `scripts/githooks` (US-36.1 / T-36.1.1).

    `core.hooksPath` is local git config, not committed — a fresh clone has it
    unset until something sets it, which would leave `scripts/githooks/pre-commit`
    present in the repo but inert (never invoked). Running this on every
    `run_all_tests.py` invocation means any legitimate dev/agent session
    self-heals the wiring instead of depending on a one-time manual setup step
    nobody remembers. Safe to call repeatedly: `git config` simply overwrites
    the same value each time. Best-effort — a missing `git` executable or a
    non-git checkout should not fail the test run itself.

    **Never set the config without verifying the target exists.** Git treats a
    `core.hooksPath` pointing at a missing directory as "no hooks" — silently,
    with no error and no exit code. Wiring the config while the hook file is
    absent therefore produces the worst possible state: config that claims the
    gate is installed, and no gate. That is the same class of failure US-36.1
    was written to close, one layer up, so this function refuses to create it
    and says so loudly instead.
    """
    hook = ROOT / "scripts" / "githooks" / "pre-commit"
    if not hook.is_file():
        print(
            f"WARNING: {hook.relative_to(ROOT)} is missing - NOT setting "
            "core.hooksPath.\n"
            "         Git silently ignores a hooksPath that does not exist, so "
            "wiring it now\n"
            "         would advertise a commit gate that cannot fire.",
            file=sys.stderr,
        )
        return

    try:
        subprocess.run(
            ["git", "config", "core.hooksPath", "scripts/githooks"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        pass


def run_step(label: str, command: list[str], cwd: Path) -> None:
    print(f"==> {label}")
    print(f"    cwd: {cwd}")
    print(f"    cmd: {' '.join(command)}")
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def install_dependencies() -> None:
    run_step(
        "Install backend dependencies",
        [sys.executable, "-m", "pip", "install", "-r", str(BACKEND_REQUIREMENTS)],
        ROOT,
    )
    run_step(
        "Install desktop dependencies",
        [npm_command(), "install"],
        FRONTEND_DIR,
    )


def run_all_tests() -> None:
    run_step(
        "Generate dashboard golden fixtures",
        [sys.executable, "-m", "app.scripts.export_dashboard_goldens"],
        BACKEND_DIR,
    )
    run_step(
        "Run backend tests",
        # `-n auto` (pytest-xdist) parallelizes across CPU cores. Safe since
        # US-21.1 (network guard) + US-21.4 (frozen goldens) made the suite
        # order-independent and network-free.
        [sys.executable, "-m", "pytest", "-n", "auto"],
        BACKEND_DIR,
    )
    run_step(
        "Run desktop tests",
        [npm_command(), "test"],
        FRONTEND_DIR,
    )
    run_step(
        "Type-check desktop (tsc --noEmit)",
        [npx_command(), "tsc", "--noEmit"],
        FRONTEND_DIR,
    )
    # Dead-code gate (US-23.8): ruff + vulture (backend) + knip (frontend),
    # zero-tolerance vs the committed allowlists. Fails the run on any finding so
    # newly-introduced dead code can't re-accumulate. Static + offline (consistent
    # with the US-21.1 network guard).
    run_step(
        "Dead-code gate (ruff + vulture + knip, zero-findings)",
        [sys.executable, str(ROOT / "scripts" / "detect_deadcode.py"), "--strict"],
        ROOT,
    )
    TEST_PASS_MARKER.parent.mkdir(exist_ok=True)
    TEST_PASS_MARKER.write_text(
        datetime.datetime.now(datetime.timezone.utc).isoformat() + "\n"
    )
    print("All tests passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the full backend + desktop test workflow.")
    parser.add_argument("--install-deps", action="store_true", help="Install backend and desktop dependencies before running tests.")
    parser.add_argument("--check", action="store_true", help="Validate required paths and executables without running anything.")
    args = parser.parse_args()

    errors = check_environment()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    ensure_git_hooks_wired()

    print(f"Backend dir: {BACKEND_DIR}")
    print(f"Frontend dir: {FRONTEND_DIR}")

    if args.check:
        print("Environment check passed.")
        return 0

    if args.install_deps:
        install_dependencies()

    run_all_tests()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
