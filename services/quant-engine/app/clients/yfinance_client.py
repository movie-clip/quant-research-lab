"""Yahoo Finance (yfinance) market-data client — secondary/fallback provider.

Used by MarketDataService only when the primary provider (FMP) returns no
history for a symbol — typically European exchange-listed UCITS ETFs that FMP's
plan 402s (e.g. VUAA.L, SXRV.DE). Yahoo serves those with adjusted-close
history for free.

Returns rows in the SAME shape FmpClient produces for
`get_historical_price_light` (`symbol`, `date`, `price`, `adjClose`, `volume`)
so the existing return-basis classifier (`detect_history_return_basis`) treats
them as `verified_adjusted_close`. `price` is set to the adjusted close, matching
how the engines consume FMP's `price`.

yfinance is imported lazily inside the fetch so importing this module never
pulls pandas/yfinance unless the fallback path is actually exercised. All
network/library errors are swallowed to `[]` (fail-closed), and results
(including empty negatives) are cached via the shared JsonFileCache.
"""
from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any

from app.core.cache import JsonFileCache
from app.core.settings import get_settings

logger = logging.getLogger(__name__)

_CACHE_NAMESPACE = "history_yf"


class YFinanceClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.history_ttl_seconds = settings.fmp_history_cache_ttl_seconds
        self.cache = JsonFileCache(Path(settings.fmp_cache_dir)) if settings.fmp_cache_enabled else None

    @staticmethod
    def _build_cache_identifier(symbol: str, from_date: str, to_date: str) -> str:
        """The one formula that decides cache-key identity for a yfinance
        history call (US-38.2 / T-38.2.2). A narrow, independent twin of
        `FmpClient.build_cache_identifier` — yfinance is a different
        provider on a different cache line, so it is not shared with FMP's
        formula, but `get_historical_price_light` and `is_cached` below both
        derive their key from this single place rather than each keeping
        their own copy.
        """
        return json.dumps(
            {"path": "yfinance/history", "params": {"symbol": symbol, "from": from_date, "to": to_date}},
            sort_keys=True,
        )

    def is_cached(self, symbol: str, from_date: str, to_date: str) -> bool:
        """Read-only pre-check: would a call with this exact (symbol, from,
        to) be served from cache right now, with no live request (US-38.2 /
        T-38.2.2). Never mutates cache state.
        """
        if self.cache is None:
            return False
        cache_key = self.cache.build_key(_CACHE_NAMESPACE, self._build_cache_identifier(symbol, from_date, to_date))
        return self.cache.get(cache_key, max_age_seconds=self.history_ttl_seconds) is not None

    def get_historical_price_light(self, symbol: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
        """Daily history for `symbol` between `from_date` and `to_date` (inclusive
        of the range yfinance returns), as FMP-shaped row dicts. Returns `[]` when
        Yahoo has no data or any error occurs."""
        cache_key = None
        if self.cache is not None:
            cache_identifier = self._build_cache_identifier(symbol, from_date, to_date)
            cache_key = self.cache.build_key(_CACHE_NAMESPACE, cache_identifier)
            cached = self.cache.get(cache_key, max_age_seconds=self.history_ttl_seconds)
            if cached is not None:
                logger.info("yfinance cache hit [%s] %s", _CACHE_NAMESPACE, symbol)
                return cached
            logger.info("yfinance cache miss [%s] %s", _CACHE_NAMESPACE, symbol)

        rows = self._fetch(symbol, from_date, to_date)

        if self.cache is not None and cache_key is not None:
            # Cache both hits and empty negatives (blocks repeated misses).
            self.cache.set(cache_key, rows)
        return rows

    def _fetch(self, symbol: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
        try:
            import yfinance as yf  # lazy: avoids importing pandas/yfinance unless used

            frame = yf.Ticker(symbol).history(start=from_date, end=to_date, auto_adjust=False)
            if frame is None or frame.empty:
                logger.info("yfinance empty [%s] %s", _CACHE_NAMESPACE, symbol)
                return []

            # US-34.9: `price` is the TRADED close and `adjClose` the adjusted
            # one — the same split FMP's benchmark path uses.
            #
            # This client previously put the ADJUSTED close in both. Because
            # `price` is what values holdings, every dividend silently rewrote
            # the history of the 14 positions this provider serves, dragging the
            # replay away from the broker's own statement: on the 2026-08-17
            # re-capture the terminal market value moved from $64,934.40 to
            # $64,896.27 against a stated `stock_total` of $64,922.99 — drift
            # +$11.41 -> -$26.72, growing with each dividend.
            #
            # A dividend-adjusted series is a RETURN series, not a VALUE series.
            # Returns still use `adjClose`: `select_history_price_series` prefers
            # it, so nothing that wants total-return behaviour loses it.
            adj_col = "Adj Close" if "Adj Close" in frame.columns else "Close"
            close_col = "Close" if "Close" in frame.columns else adj_col
            rows: list[dict[str, Any]] = []
            for index, record in frame.iterrows():
                adj = record.get(adj_col)
                if adj is None:
                    continue
                try:
                    adj_value = float(adj)
                except (TypeError, ValueError):
                    continue
                close_raw = record.get(close_col)
                try:
                    close_value = float(close_raw) if close_raw is not None else None
                except (TypeError, ValueError):
                    close_value = None
                if close_value is None or not math.isfinite(close_value):
                    # No usable traded price: fail closed rather than valuing the
                    # holding at an adjusted price that is not what it traded at.
                    continue
                # pandas encodes missing bars as float('nan'), which passes the
                # None check and float() conversion above. A non-finite bar is
                # "no data for that date" — skip it (fail-closed), never cache it.
                # (Bug 2026-06-10: NaN bars cached for 2026-06-09 poisoned the
                # correlation engines → JSON 500.)
                if not math.isfinite(adj_value):
                    continue
                date_str = index.date().isoformat() if hasattr(index, "date") else str(index)[:10]
                volume_raw = record.get("Volume")
                try:
                    volume = int(volume_raw) if volume_raw is not None else None
                except (TypeError, ValueError):
                    volume = None
                rows.append({
                    "symbol": symbol,
                    "date": date_str,
                    "price": close_value,
                    "adjClose": adj_value,
                    "volume": volume,
                })
            return rows
        except Exception:  # noqa: BLE001 — fail-closed: any yfinance/network error → no data
            logger.warning("yfinance fetch failed [%s] %s", _CACHE_NAMESPACE, symbol, exc_info=True)
            return []
