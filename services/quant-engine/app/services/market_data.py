from __future__ import annotations

from typing import Iterable

from app.core.symbols import canonicalize_symbol, resolve_etf_holdings_candidates, resolve_symbol_candidates
from app.clients.fmp import FmpClient
from app.services.holdings_history import HoldingsHistoryStore


class MarketDataService:
    def __init__(self) -> None:
        self.client = FmpClient()
        self.holdings_history = HoldingsHistoryStore()
        self.last_fetch_meta: dict[str, dict[str, str | bool]] = {}

    def get_latest_quotes(self, symbols: Iterable[str], symbol_overrides: dict[str, list[str]] | None = None) -> dict[str, dict]:
        quotes: dict[str, dict] = {}
        for symbol in sorted({symbol for symbol in symbols if symbol}):
            requested_symbol = canonicalize_symbol(symbol)
            for candidate in resolve_symbol_candidates(requested_symbol, symbol_overrides, kind="quote"):
                try:
                    rows = self.client.get_quote_short(candidate)
                except Exception:  # noqa: BLE001
                    continue
                if rows:
                    quotes[requested_symbol] = rows[0] | {"requested_symbol": requested_symbol, "resolved_symbol": candidate}
                    self.last_fetch_meta[requested_symbol] = {"type": "quote", "resolved_symbol": candidate, "cached": True}
                    break
        return quotes

    def get_historical_prices(
        self,
        symbol: str,
        from_date: str,
        to_date: str,
        symbol_overrides: dict[str, list[str]] | None = None,
        *,
        allow_proxy_fallback: bool = False,
    ) -> list[dict]:
        requested_symbol = canonicalize_symbol(symbol)
        symbol_candidates = resolve_symbol_candidates(requested_symbol, symbol_overrides, kind="history")
        ordered_candidates = list(symbol_candidates)
        if allow_proxy_fallback:
            holdings_candidates = resolve_etf_holdings_candidates(requested_symbol, symbol_overrides)
            ordered_candidates = list(dict.fromkeys([*symbol_candidates, *holdings_candidates]))

        for candidate in ordered_candidates:
            try:
                rows = self.client.get_historical_price_light(candidate, from_date, to_date)
            except Exception:  # noqa: BLE001
                continue
            if rows:
                self.last_fetch_meta[requested_symbol] = {"type": "history", "resolved_symbol": candidate, "cached": True}
                return rows
        return []

    def get_historical_prices_for_symbols(
        self,
        symbols: Iterable[str],
        from_date: str,
        to_date: str,
        symbol_overrides: dict[str, list[str]] | None = None,
        *,
        allow_proxy_fallback: bool = False,
    ) -> dict[str, list[dict]]:
        histories: dict[str, list[dict]] = {}
        for symbol in sorted({symbol for symbol in symbols if symbol}):
            requested_symbol = canonicalize_symbol(symbol)
            histories[requested_symbol] = self.get_historical_prices(requested_symbol, from_date, to_date, symbol_overrides, allow_proxy_fallback=allow_proxy_fallback)
        return histories

    def get_fx_history(self, pair: str, from_date: str, to_date: str) -> list[dict]:
        return self.get_historical_prices(pair, from_date, to_date)

    def get_company_profile(self, symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> dict | None:
        requested_symbol = canonicalize_symbol(symbol)
        for candidate in resolve_symbol_candidates(requested_symbol, symbol_overrides, kind="quote"):
            try:
                rows = self.client.get_profile(candidate)
            except Exception:  # noqa: BLE001
                continue
            if rows:
                self.last_fetch_meta[requested_symbol] = {"type": "profile", "resolved_symbol": candidate, "cached": True}
                return rows[0]
        return None

    def get_etf_holdings(self, symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> tuple[str | None, list[dict]]:
        requested_symbol = canonicalize_symbol(symbol)
        for candidate in resolve_etf_holdings_candidates(requested_symbol, symbol_overrides):
            try:
                rows = self.client.get_etf_holders(candidate)
            except Exception:  # noqa: BLE001
                continue
            if rows:
                self.holdings_history.record_snapshot(requested_symbol, candidate, rows)
                self.last_fetch_meta[requested_symbol] = {"type": "holdings", "resolved_symbol": candidate, "cached": True}
                return candidate, rows
        return None, []

    def get_etf_holdings_for_date(
        self,
        symbol: str,
        as_of_date: str,
        symbol_overrides: dict[str, list[str]] | None = None,
    ) -> tuple[str | None, list[dict]]:
        requested_symbol = canonicalize_symbol(symbol)
        snapshot_rows = self.holdings_history.get_snapshot_for_date(requested_symbol, as_of_date)
        if snapshot_rows:
            self.last_fetch_meta[requested_symbol] = {"type": "holdings-history", "resolved_symbol": requested_symbol, "cached": True}
            return requested_symbol, snapshot_rows

        resolved_symbol, rows = self.get_etf_holdings(requested_symbol, symbol_overrides)
        return resolved_symbol, rows

    def refresh_etf_holdings_snapshot(self, symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> tuple[str | None, list[dict]]:
        requested_symbol = canonicalize_symbol(symbol)
        self.holdings_history.delete_symbol_snapshots(requested_symbol)
        return self.get_etf_holdings(requested_symbol, symbol_overrides)

    def get_last_fetch_meta(self, symbol: str) -> dict[str, str | bool] | None:
        return self.last_fetch_meta.get(symbol)
