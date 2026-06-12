"""Refresh the golden pipeline after a broker-statement update.

Run this after replacing/adding a statement PDF under `docs/` (e.g. a new
`IB2026.pdf`). It performs the full recovery flow that the goldens-freshness
guard (US-21.4) demands when the statements change:

    1. Re-capture the frozen market-data fixture
       (`app/scripts/golden_market_data.json`) against live FMP for the new
       statement's history window.
    2. Regenerate `apps/desktop/src/test/dashboardGoldens.ts` from the frozen
       fixture (deterministic, no network).
    3. Run the full canonical test suite (`run_all_tests.py`).

If step 3 fails, the remaining failures are *portfolio-truth drift*: tests that
pin holdings from the previous statement (e.g. a position that was sold or
newly added). Update those tests — and add a registry entry + symbol rule for
any brand-new holding — then re-run. Review the diff and commit
`docs/<statement>.pdf`, `golden_market_data.json`, and `dashboardGoldens.ts`
together.

A real `FMP_API_KEY` is required for step 1 (set it in the environment or
`.env`). Capturing without one would record empty series and poison the local
cache with negative entries.
"""
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
GOLDEN_FIXTURE = BACKEND_DIR / "app" / "scripts" / "golden_market_data.json"
DASHBOARD_GOLDENS = FRONTEND_DIR / "src" / "test" / "dashboardGoldens.ts"
RUN_ALL_TESTS = ROOT / "scripts" / "run_all_tests.py"


def npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def check_environment() -> list[str]:
    errors: list[str] = []
    if not BACKEND_DIR.exists():
        errors.append(f"missing backend directory: {BACKEND_DIR}")
    if not FRONTEND_DIR.exists():
        errors.append(f"missing frontend directory: {FRONTEND_DIR}")
    if not RUN_ALL_TESTS.exists():
        errors.append(f"missing test runner: {RUN_ALL_TESTS}")
    if shutil.which(sys.executable) is None:
        errors.append(f"python executable not found: {sys.executable}")
    if shutil.which(npm_command()) is None:
        errors.append("npm executable not found")
    return errors


def check_fmp_api_key() -> bool:
    """The capture step fetches live market data for the new statement window.
    Without a real key, FMP requests fail and the capture would record empty
    series (and write negative-cache entries) — fail fast instead."""
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "from app.core.settings import get_settings; "
            "import sys; sys.exit(0 if get_settings().fmp_api_key else 1)",
        ],
        cwd=BACKEND_DIR,
        check=False,
    )
    return probe.returncode == 0


def run_step(label: str, command: list[str], cwd: Path) -> None:
    print(f"==> {label}")
    print(f"    cwd: {cwd}")
    print(f"    cmd: {' '.join(command)}")
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def refresh(*, skip_tests: bool) -> None:
    run_step(
        "Re-capture frozen golden market data (live FMP)",
        [sys.executable, "-m", "app.scripts.export_dashboard_goldens", "--capture"],
        BACKEND_DIR,
    )
    run_step(
        "Regenerate dashboard goldens from the frozen fixture",
        [sys.executable, "-m", "app.scripts.export_dashboard_goldens"],
        BACKEND_DIR,
    )
    if skip_tests:
        print("Skipping test suite (--skip-tests).")
    else:
        run_step(
            "Run full test suite",
            [sys.executable, str(RUN_ALL_TESTS)],
            ROOT,
        )
    print("Statement refresh complete.")
    print("Review the diff, then commit the statement PDF together with:")
    print(f"  {GOLDEN_FIXTURE.relative_to(ROOT)}")
    print(f"  {DASHBOARD_GOLDENS.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Re-capture frozen market data + regenerate goldens after a broker-statement update."
    )
    parser.add_argument("--check", action="store_true", help="Validate required paths and the FMP API key without running anything.")
    parser.add_argument("--skip-tests", action="store_true", help="Capture and regenerate only; do not run the test suite.")
    args = parser.parse_args()

    errors = check_environment()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print(f"Backend dir: {BACKEND_DIR}")
    print(f"Frontend dir: {FRONTEND_DIR}")

    if not check_fmp_api_key():
        print(
            "ERROR: FMP_API_KEY is not configured. The capture step fetches live\n"
            "market data for the new statement window; without a key it would\n"
            "record empty series and poison the local cache with negative entries.\n"
            "Set FMP_API_KEY in the environment or services/quant-engine/.env and retry."
        )
        return 1

    if args.check:
        print("Statement-refresh check passed (paths + FMP API key OK).")
        return 0

    refresh(skip_tests=args.skip_tests)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
