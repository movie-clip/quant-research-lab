from __future__ import annotations

import argparse
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "services" / "quant-engine"
FRONTEND_DIR = ROOT / "apps" / "desktop"
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000
FRONTEND_HOST = "127.0.0.1"
FRONTEND_PORT = 5173


def _npm_command() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def _stream_output(prefix: str, process: subprocess.Popen[str]) -> None:
    assert process.stdout is not None
    for line in process.stdout:
        print(f"[{prefix}] {line.rstrip()}")


def _is_localhost_port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.settimeout(0.25)
        return candidate.connect_ex((BACKEND_HOST, port)) != 0


def _require_port(port: int, service_name: str) -> int:
    if not _is_localhost_port_available(port):
        raise RuntimeError(
            f"{service_name} port {port} is already in use on {BACKEND_HOST}; stop the existing process and retry"
        )
    return port


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
    backend_port = _require_port(BACKEND_PORT, "backend")
    frontend_port = _require_port(FRONTEND_PORT, "frontend")
    backend_command = [sys.executable, "-m", "uvicorn", "app.api.main:app", "--host", BACKEND_HOST, "--port", str(backend_port), "--reload"]
    frontend_command = [_npm_command(), "run", "dev", "--", "--host", FRONTEND_HOST, "--port", str(frontend_port)]

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
        while True:
            backend_return = backend.poll()
            frontend_return = frontend.poll()
            if backend_return is not None:
                if frontend.poll() is None:
                    print(f"Backend exited with code {backend_return}; stopping frontend.")
                return backend_return
            if frontend_return is not None:
                if backend.poll() is None:
                    print(f"Frontend exited with code {frontend_return}; stopping backend.")
                return frontend_return
            threading.Event().wait(0.25)
    finally:
        shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run frontend and backend dev servers together.")
    parser.add_argument("--check", action="store_true", help="Validate paths and required executables without starting servers.")
    args = parser.parse_args()

    try:
        if args.check:
            return check_environment()

        if check_environment() != 0:
            return 1
        return run()
    except RuntimeError as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
