"""Tests for the no-live-network guard (US-21.1).

pytest.ini enables pytest-socket (`--disable-socket --allow-hosts=127.0.0.1,::1`)
so any test attempting a real external connection fails loudly, while loopback
(in-process TestClient / Windows asyncio internals) and file I/O keep working.
Tests that must hit live providers are marked `live_data` and deselected by
default (`-m "not live_data"` in addopts).
"""
from __future__ import annotations

import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pytest_socket import SocketConnectBlockedError

from app.api.main import app


def test_external_connection_is_blocked():
    # 203.0.113.0/24 is TEST-NET-3 (never routable) — the guard must block the
    # connect attempt BEFORE any real network activity happens.
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(("203.0.113.1", 443), timeout=1)


def test_live_data_marker_is_deselected_by_default(request):
    # Pins the addopts contract: the default run excludes live_data tests
    # (deselected — not silently green-skipped).
    markexpr = request.config.getoption("markexpr")
    assert "not live_data" in markexpr


def test_loopback_and_file_io_still_work(tmp_path: Path):
    # File I/O is unaffected by the socket guard.
    p = tmp_path / "guard-check.txt"
    p.write_text("ok", encoding="utf-8")
    assert p.read_text(encoding="utf-8") == "ok"

    # In-process ASGI requests (TestClient) must keep working under the guard.
    response = TestClient(app).get("/health")
    assert response.status_code == 200
