"""MCP entrypoint. Wrappers only -- no logic lives in this file.

Every tool below delegates to a plain `*_impl` function in `tools/`, which is
what `app/tests/test_mcp_tools.py` exercises. Keeping this file logic-free is
what makes the server testable at all: the MCP transport itself cannot be
verified in-session, so nothing worth verifying may live behind it.

Docstrings here are the tool descriptions agents see, and they load into every
agent's context on every dispatch. Keep them to two lines.

Run:  python services/quant-engine/app/mcp_server/server.py
      (with PYTHONPATH=services/quant-engine)
"""

from __future__ import annotations

from typing import Any

from mcp.server.mcpserver import MCPServer

from app.mcp_server.tools import probing, testing

server = MCPServer("portfolio")


@server.tool()
def run_tests(
    scope: str = "backend", path: str | None = None, k: str | None = None
) -> dict[str, Any]:
    """Run the suite: scope backend|frontend|typecheck|full, optional path and -k filter.
    Returns parsed failures plus a short tail, never the full output dump."""
    return testing.run_tests_impl(scope=scope, path=path, k=k)


@server.tool()
def check_gates() -> dict[str, Any]:
    """Report dead-code, type-check, goldens-drift and commit-gate status.
    Use before committing to see whether the pre-commit hook will block you."""
    return testing.check_gates_impl()


@server.tool()
def reset_goldens() -> dict[str, Any]:
    """Discard drift in dashboardGoldens.ts (usually an FMP-cache artifact).
    Use when the file is modified but your work did not change dashboard output."""
    return testing.reset_goldens_impl()


@server.tool()
def build_snapshot(
    positions: list[dict] | None = None,
    instruments: list[dict] | None = None,
    cash_balances: list[dict] | None = None,
    ledger_entries: list[dict] | None = None,
    statement_overrides: dict | None = None,
) -> dict[str, Any]:
    """Build a 422-proof ImportedPortfolioSnapshot payload for engine requests.
    Positions may be shorthand: {"symbol": "AAPL", "market_value": 500}."""
    return probing.build_snapshot_impl(
        positions=positions,
        instruments=instruments,
        cash_balances=cash_balances,
        ledger_entries=ledger_entries,
        statement_overrides=statement_overrides,
    )


@server.tool()
def probe_engine(
    route: str,
    payload: dict,
    histories: dict[str, list[dict]] | None = None,
    default_rows: list[dict] | None = None,
    vendor_by_symbol: dict[str, str] | None = None,
    engine_module: str | None = None,
) -> dict[str, Any]:
    """POST one engine route in-process with market data mocked, e.g. /engines/drawdown/run.
    Use instead of writing a throwaway probe script; returns the route's JSON."""
    return probing.probe_engine_impl(
        route=route,
        payload=payload,
        histories=histories,
        default_rows=default_rows,
        vendor_by_symbol=vendor_by_symbol,
        engine_module=engine_module,
    )


if __name__ == "__main__":
    server.run()  # transport defaults to stdio
