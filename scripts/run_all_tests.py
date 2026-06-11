from __future__ import annotations

import argparse
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


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


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
