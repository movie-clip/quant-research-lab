from __future__ import annotations

import argparse
import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "services" / "quant-engine"
FRONTEND_DIR = ROOT / "apps" / "desktop"


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _stream_output(prefix: str, process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{prefix}] {line.rstrip()}")


def check_environment() -> int:
    missing: list[str] = []
    if not BACKEND_DIR.exists():
        missing.append(f"missing backend directory: {BACKEND_DIR}")
    if not FRONTEND_DIR.exists():
        missing.append(f"missing frontend directory: {FRONTEND_DIR}")
    if shutil.which(sys.executable) is None:
        missing.append(f"python executable not found: {sys.executable}")
    if shutil.which(_npm_command()) is None:
        missing.append("npm executable not found")

    if missing:
        for item in missing:
            print(f"ERROR: {item}")
        return 1

    print("Development runner check passed.")
    print(f"Backend dir: {BACKEND_DIR}")
    print(f"Frontend dir: {FRONTEND_DIR}")
    return 0


def run() -> int:
    backend_command = [sys.executable, "-m", "uvicorn", "app.api.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    frontend_command = [_npm_command(), "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173"]

    backend = subprocess.Popen(backend_command, cwd=BACKEND_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    frontend = subprocess.Popen(frontend_command, cwd=FRONTEND_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)

    threads = [
        threading.Thread(target=_stream_output, args=("backend", backend), daemon=True),
        threading.Thread(target=_stream_output, args=("frontend", frontend), daemon=True),
    ]
    for thread in threads:
        thread.start()

    def shutdown(*_: object) -> None:
        for process in (backend, frontend):
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, shutdown)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, shutdown)

    try:
        backend_return = backend.wait()
        frontend_return = frontend.wait()
        return backend_return or frontend_return
    finally:
        shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frontend and backend dev servers together.")
    parser.add_argument("--check", action="store_true", help="Validate paths and required executables without starting servers.")
    args = parser.parse_args()

    if args.check:
        return check_environment()

    if check_environment() != 0:
        return 1
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
