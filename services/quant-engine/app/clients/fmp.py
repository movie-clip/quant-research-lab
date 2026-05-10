from __future__ import annotations

import json
import logging
import time
from collections import deque
from pathlib import Path
from threading import Lock
from typing import Any

import httpx

from app.core.cache import JsonFileCache
from app.core.settings import get_settings


logger = logging.getLogger(__name__)

_IN_FLIGHT_LOCK = Lock()
_IN_FLIGHT_REQUESTS: dict[str, list[dict[str, Any]]] = {}
_RATE_LIMIT_LOCK = Lock()
_REQUEST_TIMESTAMPS: deque[float] = deque()


class FmpClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.fmp_api_key
        self.base_url = settings.fmp_base_url.rstrip("/")
        self.quote_ttl_seconds = settings.fmp_quote_cache_ttl_seconds
        self.history_ttl_seconds = settings.fmp_history_cache_ttl_seconds
        self.max_requests_per_minute = settings.fmp_max_requests_per_minute
        self.client = httpx.Client(timeout=30.0)
        self.cache = JsonFileCache(Path(settings.fmp_cache_dir)) if settings.fmp_cache_enabled else None

    def _wait_for_rate_limit(self) -> None:
        if self.max_requests_per_minute <= 0:
            return

        while True:
            now = time.monotonic()
            with _RATE_LIMIT_LOCK:
                while _REQUEST_TIMESTAMPS and now - _REQUEST_TIMESTAMPS[0] >= 60:
                    _REQUEST_TIMESTAMPS.popleft()
                if len(_REQUEST_TIMESTAMPS) < self.max_requests_per_minute:
                    _REQUEST_TIMESTAMPS.append(now)
                    return
                sleep_seconds = max(0.05, 60 - (now - _REQUEST_TIMESTAMPS[0]))
            time.sleep(min(sleep_seconds, 1.0))

    def _get(self, namespace: str, path: str, params: dict[str, Any], ttl_seconds: int) -> list[dict[str, Any]]:
        if not self.api_key:
            raise ValueError("FMP_API_KEY is not configured")

        cache_key = None
        if self.cache is not None:
            cache_identifier = json.dumps({"path": path, "params": params}, sort_keys=True)
            cache_key = self.cache.build_key(namespace, cache_identifier)
            cached = self.cache.get(cache_key, max_age_seconds=ttl_seconds)
            if cached is not None:
                logger.info("FMP cache hit [%s] %s", namespace, params)
                return cached
            logger.info("FMP cache miss [%s] %s", namespace, params)
        else:
            cache_identifier = json.dumps({"path": path, "params": params}, sort_keys=True)

        with _IN_FLIGHT_LOCK:
            in_flight = _IN_FLIGHT_REQUESTS.get(cache_identifier)
            if in_flight is not None:
                logger.info("FMP request coalesced [%s] %s", namespace, params)
                return in_flight

        query = {**params, "apikey": self.api_key}
        try:
            self._wait_for_rate_limit()
            response = self.client.get(f"{self.base_url}/{path.lstrip('/')}", params=query)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list):
                rows = payload
            elif isinstance(payload, dict):
                rows = [payload]
            else:
                raise ValueError("Unexpected FMP response format")

            if self.cache is not None and cache_key is not None:
                self.cache.set(cache_key, rows)
                logger.info("FMP cache store [%s] %s", namespace, params)
            with _IN_FLIGHT_LOCK:
                _IN_FLIGHT_REQUESTS[cache_identifier] = rows
            return rows
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code if exc.response is not None else None
            if self.cache is not None and cache_key is not None and status_code in {401, 402, 403, 404}:
                logger.warning("FMP negative cache [%s] %s status=%s", namespace, params, status_code)
                self.cache.set(cache_key, [])
            if self.cache is not None and cache_key is not None:
                stale = self.cache.get(cache_key, allow_stale=True)
                if stale is not None:
                    logger.warning("FMP stale cache fallback [%s] %s", namespace, params)
                    with _IN_FLIGHT_LOCK:
                        _IN_FLIGHT_REQUESTS[cache_identifier] = stale
                    return stale
            raise
        except Exception:  # noqa: BLE001
            if self.cache is not None and cache_key is not None:
                stale = self.cache.get(cache_key, allow_stale=True)
                if stale is not None:
                    logger.warning("FMP stale cache fallback [%s] %s", namespace, params)
                    with _IN_FLIGHT_LOCK:
                        _IN_FLIGHT_REQUESTS[cache_identifier] = stale
                    return stale
            raise
        finally:
            with _IN_FLIGHT_LOCK:
                _IN_FLIGHT_REQUESTS.pop(cache_identifier, None)

    def get_quote_short(self, symbol: str) -> list[dict[str, Any]]:
        return self._get("quote", "quote-short", {"symbol": symbol}, ttl_seconds=self.quote_ttl_seconds)

    def get_historical_price_light(self, symbol: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
        return self._get(
            "history" if not symbol.endswith("USD") else "fx",
            "historical-price-eod/light",
            {
                "symbol": symbol,
                "from": from_date,
                "to": to_date,
            },
            ttl_seconds=self.history_ttl_seconds,
        )

    def get_profile(self, symbol: str) -> list[dict[str, Any]]:
        return self._get("profile", "profile", {"symbol": symbol}, ttl_seconds=self.quote_ttl_seconds)

    def get_income_statements(self, symbol: str, *, limit: int = 8, period: str = "quarter") -> list[dict[str, Any]]:
        return self._get(
            "fundamentals",
            "income-statement",
            {"symbol": symbol, "limit": limit, "period": period},
            ttl_seconds=self.history_ttl_seconds,
        )

    def get_balance_sheet_statements(self, symbol: str, *, limit: int = 8, period: str = "quarter") -> list[dict[str, Any]]:
        return self._get(
            "fundamentals",
            "balance-sheet-statement",
            {"symbol": symbol, "limit": limit, "period": period},
            ttl_seconds=self.history_ttl_seconds,
        )

    def get_cash_flow_statements(self, symbol: str, *, limit: int = 8, period: str = "quarter") -> list[dict[str, Any]]:
        return self._get(
            "fundamentals",
            "cash-flow-statement",
            {"symbol": symbol, "limit": limit, "period": period},
            ttl_seconds=self.history_ttl_seconds,
        )

    def get_etf_holders(self, symbol: str) -> list[dict[str, Any]]:
        if not self.api_key:
            raise ValueError("FMP_API_KEY is not configured")

        cache_key = None
        cache_identifier = json.dumps({"path": f"api/v3/etf-holder/{symbol}", "params": {}}, sort_keys=True)
        if self.cache is not None:
            cache_key = self.cache.build_key("holdings", cache_identifier)
            cached = self.cache.get(cache_key, max_age_seconds=self.history_ttl_seconds)
            if cached is not None:
                logger.info("FMP cache hit [holdings] %s", symbol)
                return cached
            logger.info("FMP cache miss [holdings] %s", symbol)

        with _IN_FLIGHT_LOCK:
            in_flight = _IN_FLIGHT_REQUESTS.get(cache_identifier)
            if in_flight is not None:
                logger.info("FMP request coalesced [holdings] %s", symbol)
                return in_flight

        try:
            self._wait_for_rate_limit()
            response = self.client.get(
                f"https://financialmodelingprep.com/api/v3/etf-holder/{symbol}",
                params={"apikey": self.api_key},
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload if isinstance(payload, list) else []
            if self.cache is not None and cache_key is not None:
                self.cache.set(cache_key, rows)
                logger.info("FMP cache store [holdings] %s", symbol)
            with _IN_FLIGHT_LOCK:
                _IN_FLIGHT_REQUESTS[cache_identifier] = rows
            return rows
        except Exception:  # noqa: BLE001
            if self.cache is not None and cache_key is not None:
                stale = self.cache.get(cache_key, allow_stale=True)
                if stale is not None:
                    logger.warning("FMP stale cache fallback [holdings] %s", symbol)
                    with _IN_FLIGHT_LOCK:
                        _IN_FLIGHT_REQUESTS[cache_identifier] = stale
                    return stale
            raise
        finally:
            with _IN_FLIGHT_LOCK:
                _IN_FLIGHT_REQUESTS.pop(cache_identifier, None)

    def get_ratios_ttm(self, symbol: str) -> list[dict[str, Any]]:
        # FMP ratios TTM endpoint — Phase 2 value-factor support.
        # Fields used: priceToBookRatioTTM, priceToFreeCashFlowsRatioTTM, enterpriseValueMultipleTTM.
        return self._get(
            "fundamentals",
            "ratios-ttm",
            {"symbol": symbol},
            ttl_seconds=self.history_ttl_seconds,
        )

    def get_key_metrics_ttm(self, symbol: str) -> list[dict[str, Any]]:
        # FMP key-metrics TTM endpoint — Phase 2 value-factor support.
        # Fields used: enterpriseValueTTM, freeCashFlowYieldTTM, enterpriseValueOverEBITDATTM, marketCapTTM.
        return self._get(
            "fundamentals",
            "key-metrics-ttm",
            {"symbol": symbol},
            ttl_seconds=self.history_ttl_seconds,
        )

    def get_sp500_constituents(self) -> list[dict[str, Any]]:
        # FMP S&P 500 constituent endpoint — Phase 2 index_constituent universe support.
        # Returns list of dicts with: symbol, name, sector, subSector, headQuarter, dateFirstAdded, cik, founded.
        return self._get(
            "index_constituents",
            "sp500-constituent",
            {},
            ttl_seconds=self.history_ttl_seconds,
        )

    def get_screener_results(
        self,
        *,
        exchange: str | None = None,
        market_cap_more_than: float | None = None,
        volume_more_than: float | None = None,
        price_more_than: float | None = None,
        sector: str | None = None,
        country: str | None = None,
        is_etf: bool | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        # NOTE: FMP /stock-screener endpoint — added to support generic_ranking universe resolution.
        # Follows the exact _get() pattern used by all other client methods.
        params: dict[str, Any] = {"limit": limit}
        if exchange is not None:
            params["exchange"] = exchange
        if market_cap_more_than is not None:
            params["marketCapMoreThan"] = int(market_cap_more_than)
        if volume_more_than is not None:
            params["volumeMoreThan"] = int(volume_more_than)
        if price_more_than is not None:
            params["priceMoreThan"] = price_more_than
        if sector is not None:
            params["sector"] = sector
        if country is not None:
            params["country"] = country
        if is_etf is not None:
            params["isEtf"] = str(is_etf).lower()
        return self._get("screener", "stock-screener", params, ttl_seconds=self.history_ttl_seconds)

    def __del__(self) -> None:
        try:
            self.client.close()
        except Exception:  # noqa: BLE001
            pass
