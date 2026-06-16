"""Run the dead-code detectors and print a summary (Epic 23 / US-23.1).

Informational by default — it reports findings but does NOT fail the build yet,
because the baseline is still dirty (US-23.2–23.7 clean it). US-23.8 promotes
this to a zero-findings gate wired into `run_all_tests.py`.

Detectors:
  - ruff  : Python in-file unused (F401 import / F811 redef / F841 local)
  - vulture: Python whole-program unused functions/classes/attributes
  - knip  : TypeScript unused files / exports / types / dependencies

Install the dev tooling first:
  pip install -r services/quant-engine/requirements-dev.txt
  (knip is already an apps/desktop devDependency: npm install)

Usage:
  python scripts/detect_deadcode.py            # report (exit 0 regardless)
  python scripts/detect_deadcode.py --strict   # exit non-zero if any detector reports findings (US-23.8 mode)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "services" / "quant-engine"
FRONTEND_DIR = ROOT / "apps" / "desktop"


def npm_command() -> str:
    return "npx.cmd" if os.name == "nt" else "npx"


def run(label: str, command: list[str], cwd: Path) -> int:
    print(f"\n==> {label}")
    print(f"    cwd: {cwd}")
    print(f"    cmd: {' '.join(command)}")
    completed = subprocess.run(command, cwd=cwd, check=False)
    return completed.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the dead-code detectors (ruff, vulture, knip).")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if any detector reports findings (the US-23.8 gate mode).",
    )
    args = parser.parse_args()

    codes: dict[str, int] = {}
    codes["ruff"] = run(
        "ruff - Python unused imports/redefs/locals",
        [sys.executable, "-m", "ruff", "check", "app", "--select", "F401,F811,F841"],
        BACKEND_DIR,
    )
    codes["vulture"] = run(
        "vulture - Python unused functions/classes/attributes",
        [sys.executable, "-m", "vulture", "app", "vulture_allowlist.py", "--min-confidence", "80"],
        BACKEND_DIR,
    )
    codes["knip"] = run(
        "knip - TypeScript unused files/exports/types/deps",
        [npm_command(), "knip"],
        FRONTEND_DIR,
    )

    any_findings = any(code != 0 for code in codes.values())
    print("\n" + "=" * 60)
    print("Dead-code detector summary:")
    for name, code in codes.items():
        print(f"  {name:8s}: {'findings' if code != 0 else 'clean'}")
    print("=" * 60)

    if args.strict:
        if any_findings:
            print("STRICT: dead-code findings present — failing (US-23.8 gate mode).")
            return 1
        print("STRICT: no dead-code findings — clean.")
        return 0

    print("Informational run (not gating). Triage findings into docs/tech-debt-register.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
