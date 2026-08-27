"""Probing one engine route in-process, for agents.

This replaces the throwaway probe script. Instead of writing a one-off module
into scratchpad to build a snapshot, patch market data and call an engine, a
lane calls `probe_engine` and gets the route's JSON response back.

Everything delegates to `app/tests/fixtures.py`. No fixture logic is
reimplemented here -- if the canonical snapshot shape changes, this follows.
"""

from __future__ import annotations

from contextlib import contextmanager, nullcontext
from typing import Any, Iterator
from unittest import mock

from app.tests.fixtures import imported_snapshot, install_market_data_mock, position


class _Patcher:
    """Supplies the single method `install_market_data_mock` needs from pytest-mock.

    That fixture takes a `mocker` and calls `mocker.patch(target, new)`. Outside
    a pytest session there is no `mocker`, so rather than duplicating the fixture
    for non-pytest callers we hand it an adapter backed by `unittest.mock` and
    unwind the patches ourselves.
    """

    def __init__(self) -> None:
        self._started: list[Any] = []

    def patch(self, target: str, new: Any) -> Any:
        patcher = mock.patch(target, new)
        patcher.start()
        self._started.append(patcher)
        return new

    def stop_all(self) -> None:
        for patcher in reversed(self._started):
            patcher.stop()
        self._started.clear()


@contextmanager
def _market_data(
    engine_module: str,
    histories: dict[str, list[dict]] | None,
    default_rows: list[dict] | None,
    vendor_by_symbol: dict[str, str] | None,
) -> Iterator[Any]:
    patcher = _Patcher()
    try:
        yield install_market_data_mock(
            patcher,
            engine_module,
            histories=histories,
            default_rows=default_rows,
            vendor_by_symbol=vendor_by_symbol,
        )
    finally:
        patcher.stop_all()


def engine_module_for(route: str) -> str | None:
    """Derive the module to patch from the route.

    Every engine router is mounted at `/engines/<name>` and its service module is
    `app.services.<name>_engine` (hyphens become underscores). Derived rather than
    table-driven so a new engine works without touching this file.

    Returns None for non-engine routes (imports, cache, market-data, health),
    which do not read market data through an engine module.
    """
    parts = [p for p in route.split("/") if p]
    if len(parts) >= 2 and parts[0] == "engines":
        return f"app.services.{parts[1].replace('-', '_')}_engine"
    return None


def build_snapshot_impl(
    positions: list[dict] | None = None,
    instruments: list[dict] | None = None,
    cash_balances: list[dict] | None = None,
    ledger_entries: list[dict] | None = None,
    statement_overrides: dict | None = None,
) -> dict[str, Any]:
    """Build a 422-proof ImportedPortfolioSnapshot payload.

    Position entries may be shorthand (`{"symbol": "AAPL", "market_value": 500}`)
    -- anything carrying a `symbol` is routed through the canonical `position()`
    builder, so unspecified required fields get their defaults.
    """
    built = [
        position(**entry) if isinstance(entry, dict) and "symbol" in entry else entry
        for entry in (positions or [])
    ]
    return imported_snapshot(
        positions=built,
        instruments=instruments,
        cash_balances=cash_balances,
        ledger_entries=ledger_entries,
        statement_overrides=statement_overrides,
    )


def probe_engine_impl(
    route: str,
    payload: dict,
    histories: dict[str, list[dict]] | None = None,
    default_rows: list[dict] | None = None,
    vendor_by_symbol: dict[str, str] | None = None,
    engine_module: str | None = None,
) -> dict[str, Any]:
    """POST one engine route in-process with `MarketDataService` mocked.

    NOTE: pytest.ini's `--disable-socket` guard does NOT apply here -- there is
    no pytest session. The mock installed from the derived `engine_module` is
    what keeps this offline, which is why the derivation exists rather than
    making the argument required. Passing a route whose module cannot be derived
    and giving no `engine_module` runs UNMOCKED.

    conftest.py's autouse fixtures do not apply either: anything the route needs
    must be passed in explicitly.
    """
    from fastapi.testclient import TestClient

    from app.api.main import app

    target = engine_module or engine_module_for(route)
    context = (
        _market_data(target, histories, default_rows, vendor_by_symbol)
        if target
        else nullcontext()
    )

    with context:
        with TestClient(app) as client:
            response = client.post(route, json=payload)

    content_type = response.headers.get("content-type", "")
    return {
        "status": response.status_code,
        "ok": response.status_code < 400,
        "engine_module": target,
        "mocked": target is not None,
        "body": response.json()
        if content_type.startswith("application/json")
        else response.text,
    }
