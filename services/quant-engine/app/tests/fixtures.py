"""Canonical shared test fixtures (US-21.2).

Single source of truth for:
- the 422-proof `ImportedPortfolioSnapshot` payload shape (`imported_snapshot`,
  `position`) — the schema requires the full statement/instruments/positions/
  cash_balances/ledger_entries shape, and re-implementing it per file was the
  most-tripped gotcha in the suite;
- deterministic price-row builders (`price_rows`, `price_rows_from_returns`);
- `install_market_data_mock(...)` — patches an engine module's
  `MarketDataService` with a MagicMock serving given histories plus a real
  `last_fetch_meta` (every engine imports MarketDataService at module load, so
  the mock must target the ENGINE module, not app.services.market_data).

Policy: new engine tests import from here instead of re-implementing builders
(see .claude/skills/write-tests/SKILL.md).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock


def position(symbol: str, market_value: float = 1000.0, **overrides: Any) -> dict:
    """ImportedPosition-shaped dict with sane defaults; override any field."""
    base = {
        "as_of_date": "2024-12-31",
        "symbol": symbol,
        "quantity": 10.0,
        "cost_basis": market_value * 0.8,
        "close_price": market_value / 10.0,
        "market_value": market_value,
        "unrealized_pnl": market_value * 0.2,
        "currency": "USD",
    }
    base.update(overrides)
    return base


def imported_snapshot(
    *,
    positions: list[dict] | None = None,
    instruments: list[dict] | None = None,
    cash_balances: list[dict] | None = None,
    ledger_entries: list[dict] | None = None,
    statement_overrides: dict | None = None,
) -> dict:
    """The full, 422-proof ImportedPortfolioSnapshot payload."""
    statement = {
        "importer": "interactive_brokers",
        "imported_at": "2024-12-31T00:00:00",
        "source_path": "/test/fixture.csv",
        "detected_format": "ib_flex_2023",
    }
    if statement_overrides:
        statement.update(statement_overrides)
    return {
        "statement": statement,
        "instruments": instruments or [],
        "positions": positions or [],
        "cash_balances": cash_balances or [],
        "ledger_entries": ledger_entries or [],
    }


def price_rows(
    n_days: int = 80,
    *,
    start: date = date(2025, 1, 1),
    start_price: float = 100.0,
    step: float = 0.1,
    symbol: str | None = None,
) -> list[dict]:
    """Deterministic linear daily price rows (consecutive calendar days)."""
    rows = []
    for d in range(n_days):
        row: dict[str, Any] = {
            "date": (start + timedelta(days=d)).isoformat(),
            "price": round(start_price + d * step, 6),
        }
        if symbol is not None:
            row["symbol"] = symbol
        rows.append(row)
    return rows


def price_rows_from_returns(
    returns: list[float],
    *,
    start: date = date(2025, 1, 1),
    start_price: float = 100.0,
    symbol: str | None = None,
) -> list[dict]:
    """Price rows whose daily returns reproduce `returns` exactly
    (len(returns)+1 rows; first row at `start_price`)."""
    prices = [start_price]
    for r in returns:
        prices.append(prices[-1] * (1.0 + r))
    rows = []
    for d, p in enumerate(prices):
        row: dict[str, Any] = {"date": (start + timedelta(days=d)).isoformat(), "price": p}
        if symbol is not None:
            row["symbol"] = symbol
        rows.append(row)
    return rows


def install_market_data_mock(
    mocker,
    target_module: str,
    *,
    histories: dict[str, list[dict]] | None = None,
    default_rows: list[dict] | None = None,
    vendor_by_symbol: dict[str, str] | None = None,
) -> MagicMock:
    """Patch `{target_module}.MarketDataService` with a deterministic mock.

    - `histories`: symbol → rows served by both `get_historical_prices` and
      `get_historical_prices_for_symbols`.
    - `default_rows`: served for any symbol NOT in `histories` (omit → []).
    - `vendor_by_symbol`: populates a REAL `last_fetch_meta` dict (vendor per
      symbol; symbols with rows default to 'fmp').

    Returns the mock service instance (for call assertions).
    """
    lookup = dict(histories or {})

    def _rows_for(sym: str) -> list[dict]:
        if sym in lookup:
            return lookup[sym]
        return list(default_rows) if default_rows is not None else []

    mock_svc = MagicMock()
    inst = mock_svc.return_value
    inst.get_historical_prices.side_effect = lambda sym, *a, **k: _rows_for(sym)
    inst.get_historical_prices_for_symbols.side_effect = (
        lambda syms, *a, **k: {s: _rows_for(s) for s in syms}
    )

    meta_symbols = set(lookup) | set(vendor_by_symbol or {})
    inst.last_fetch_meta = {
        sym: {"type": "history", "vendor": (vendor_by_symbol or {}).get(sym, "fmp")}
        for sym in meta_symbols
        if _rows_for(sym) or (vendor_by_symbol or {}).get(sym)
    }

    mocker.patch(f"{target_module}.MarketDataService", mock_svc)
    return inst
