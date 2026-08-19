from __future__ import annotations

import json
import logging
import math
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



def _coerce_finite_float(value: Any) -> float | None:
    """A finite float, or None. US-34.9.

    `None`, a non-numeric string and NaN/inf all mean "no usable value here".
    NaN in particular passes an `is not None` check and `float()` alike, which
    is how non-finite bars poisoned the correlation engines in 2026-06 — so the
    finiteness check is not optional.
    """
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _join_close_and_adjusted_rows(
    symbol: str,
    full_rows: list[dict[str, Any]],
    adjusted_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Join FMP's two EOD responses into this project's row shape (US-34.9).

    Neither endpoint alone carries both figures — verified against the live API:

      historical-price-eod/full              -> open high low close volume ...   (no adjClose)
      historical-price-eod/dividend-adjusted -> adjOpen adjHigh adjLow adjClose  (no close)

    So they are joined on `date`. `price` stays the REAL traded close and
    `adjClose` carries the dividend-adjusted figure.

    Mapping `price` from `adjClose` instead would have been one call cheaper and
    is what the yfinance client does — which is precisely why it is avoided here.
    That provider makes `price` mean "adjusted close", so holdings it serves are
    valued on a different basis from FMP-served ones; repeating it would spread
    the inconsistency rather than contain it.

    A date present in only one response is dropped, fail-closed: half a row is
    not a row, and completing one side from the other would fabricate an
    adjustment. That also keeps a partially adjusted series visibly partial, so
    `detect_history_return_basis` can refuse it.
    """
    adjusted_by_date: dict[str, float] = {}
    for row in adjusted_rows or []:
        if not isinstance(row, dict):
            continue
        date = row.get("date")
        adj_close = _coerce_finite_float(row.get("adjClose"))
        if isinstance(date, str) and date and adj_close is not None:
            adjusted_by_date[date[:10]] = adj_close

    joined: list[dict[str, Any]] = []
    for row in full_rows or []:
        if not isinstance(row, dict):
            continue
        date = row.get("date")
        if not isinstance(date, str) or not date:
            continue
        date = date[:10]
        close = _coerce_finite_float(row.get("close"))
        adj_close = adjusted_by_date.get(date)
        if close is None or adj_close is None:
            continue
        volume_raw = row.get("volume")
        try:
            volume = int(volume_raw) if volume_raw is not None else None
        except (TypeError, ValueError):
            volume = None
        joined.append({
            "symbol": row.get("symbol") or symbol,
            "date": date,
            "price": close,
            "adjClose": adj_close,
            "volume": volume,
        })
    # US-34.9: ASCENDING by date. FMP returns newest-first, and
    # `_validate_verified_benchmark_slice` requires `ordered_dates ==
    # sorted(ordered_dates)` — so vendor order alone was a SECOND structural
    # disqualifier on the verified rung, independent of the adjClose one F-9
    # named. With both live, the rung stayed unreachable even after the endpoint
    # move, and it failed silently: the basis simply fell to
    # `unverified_adjusted_proxy`, which publishes nothing.
    #
    # Normalising here rather than relaxing the validator keeps the check doing
    # its real job — catching a scrambled or duplicated series — instead of
    # encoding one vendor's sort order as a trust condition.
    joined.sort(key=lambda row: row["date"])
    return joined

class FmpClient:
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.fmp_api_key
        self.base_url = settings.fmp_base_url.rstrip("/")
        # Legacy v3 base — see Settings.fmp_legacy_base_url (US-24.6). Endpoints
        # that exist only on v3 build their URL from this, so no call escapes
        # configuration by hardcoding the vendor host.
        self.legacy_base_url = settings.fmp_legacy_base_url.rstrip("/")
        self.quote_ttl_seconds = settings.fmp_quote_cache_ttl_seconds
        self.history_ttl_seconds = settings.fmp_history_cache_ttl_seconds
        self.max_requests_per_minute = settings.fmp_max_requests_per_minute
        self.client = httpx.Client(timeout=settings.fmp_request_timeout_seconds)
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

    def get_historical_price_dividend_adjusted(self, symbol: str, from_date: str, to_date: str) -> list[dict[str, Any]]:
        """Split- AND dividend-adjusted EOD history (US-34.9, Epic 34 F-9).

        The `light` endpoint above returns `symbol, date, price, volume` and no
        adjusted close, which made the `verified_total_return` benchmark rung
        unsatisfiable: it needs every row to carry `adjClose` AND the fetch to
        come from the endpoint named in `VERIFIED_BENCHMARK_ENDPOINT`, and no
        single endpoint could do both.

        `historical-price-eod/dividend-adjusted` supplies `adjClose`, so both
        conditions can hold at once.

        It takes TWO calls. Checked against the live API, neither response
        carries both figures: `dividend-adjusted` returns
        `adjOpen/adjHigh/adjLow/adjClose` and **no `close`**, while `full`
        returns `close` and no adjusted figure. They are joined on `date` by
        `_join_close_and_adjusted_rows`, which keeps `price` as the real traded
        close and puts the adjustment in `adjClose`.

        Both calls share the `history` namespace and TTL, so the second is a
        cache hit on every subsequent window.

        Mapping is not optional: the adjusted response has no `price` key and
        `MarketDataService._sanitize_price_rows` drops every row whose `price` is
        absent, so passing it through would silently blank the benchmark —
        reaching a fail-closed path for an entirely accidental reason. (That is
        not hypothetical: it is what the first version of this method did, and it
        emptied SPY's 148 rows.)
        """
        params = {"symbol": symbol, "from": from_date, "to": to_date}
        full_rows = self._get(
            "history",
            "historical-price-eod/full",
            params,
            ttl_seconds=self.history_ttl_seconds,
        )
        adjusted_rows = self._get(
            "history",
            "historical-price-eod/dividend-adjusted",
            params,
            ttl_seconds=self.history_ttl_seconds,
        )
        return _join_close_and_adjusted_rows(symbol, full_rows, adjusted_rows)

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
                f"{self.legacy_base_url}/etf-holder/{symbol}",
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
