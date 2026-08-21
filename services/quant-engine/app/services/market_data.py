from __future__ import annotations

import json
import math
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from typing import Iterable, Literal

from app.core.symbols import canonicalize_symbol, resolve_etf_holdings_candidates, resolve_symbol_candidates
from app.clients.fmp import FmpClient, MarketDataAuthError
from app.clients.yfinance_client import YFinanceClient
from app.schemas.return_basis import ReturnBasisContract, ReturnBasisEvidence, ReturnBasisPathTrust
from app.services.holdings_history import HoldingsHistoryStore


HistoricalReturnBasisStatus = Literal[
    "verified_adjusted_close",
    "unverified_close_only",
    "unavailable",
]

HistoryReturnBasisContract = Literal[
    "verified_total_return",
    "price_return_only",
    "unverified_adjusted_proxy",
    "unavailable",
]

VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST = frozenset({"SPY", "QQQ"})
VERIFIED_BENCHMARK_VENDOR = "FMP"
# US-34.9 (Epic 34 F-9): the verified rung requires every row to carry
# `adjClose` AND the fetch to have come from this endpoint. Pinned to the
# `light` endpoint — which returns no adjusted close — those two conditions
# were mutually unsatisfiable, so the rung could never fire in production.
# The dividend-adjusted endpoint returns both `close` and `adjClose`.
VERIFIED_BENCHMARK_ENDPOINT = "historical-price-eod/dividend-adjusted"


def _row_has_adjusted_close(row: dict) -> bool:
    return row.get("adjClose") is not None or row.get("adjusted_close") is not None


def detect_history_return_basis(rows: list[dict]) -> HistoricalReturnBasisStatus:
    if not rows:
        return "unavailable"
    if all(_row_has_adjusted_close(row) for row in rows):
        return "verified_adjusted_close"
    return "unverified_close_only"


def detect_histories_return_basis(histories: dict[str, list[dict]]) -> HistoricalReturnBasisStatus:
    populated_histories = [rows for rows in histories.values() if rows]
    if not populated_histories:
        return "unavailable"
    if all(detect_history_return_basis(rows) == "verified_adjusted_close" for rows in populated_histories):
        return "verified_adjusted_close"
    return "unverified_close_only"


def classify_history_return_basis_contract(rows: list[dict]) -> HistoryReturnBasisContract:
    basis = detect_history_return_basis(rows)
    if basis == "verified_adjusted_close":
        return "unverified_adjusted_proxy"
    if basis == "unverified_close_only":
        return "price_return_only"
    return "unavailable"


def classify_histories_return_basis_contract(histories: dict[str, list[dict]]) -> HistoryReturnBasisContract:
    populated_histories = [rows for rows in histories.values() if rows]
    if not populated_histories:
        return "unavailable"
    contracts = {classify_history_return_basis_contract(rows) for rows in populated_histories}
    if contracts == {"unverified_adjusted_proxy"}:
        return "unverified_adjusted_proxy"
    if contracts <= {"unverified_adjusted_proxy", "price_return_only"}:
        return "price_return_only"
    return "unavailable"


def build_history_return_basis_evidence(
    rows: list[dict],
    *,
    construction_method_hint: Literal["synthetic_snapshot_history", "sample_dataset"] | None = None,
    verified_total_return_scope: dict[str, str | bool | int | None] | None = None,
) -> ReturnBasisEvidence:
    if not rows:
        disqualifiers = ["missing_history_rows"]
        if construction_method_hint == "synthetic_snapshot_history":
            disqualifiers.append("synthetic_snapshot_history")
        if construction_method_hint == "sample_dataset":
            disqualifiers.append("sample_dataset")
        return ReturnBasisEvidence(
            verification_status="unavailable",
            economic_basis="unavailable",
            construction_method=construction_method_hint or "unknown",
            disqualifiers=disqualifiers,
            scope={},
        )

    if verified_total_return_scope is not None:
        return ReturnBasisEvidence(
            verification_status="verified",
            economic_basis="total_return",
            construction_method="vendor_adjusted_close",
            disqualifiers=[],
            fallbacks_used=[],
            source_price_field="adjClose",
            scope=verified_total_return_scope,
        )

    if construction_method_hint == "synthetic_snapshot_history":
        return ReturnBasisEvidence(
            verification_status="unverified",
            economic_basis="price_return_only",
            construction_method="synthetic_snapshot_history",
            disqualifiers=[
                "synthetic_snapshot_history",
                "missing_total_return_reconstruction",
                "missing_dividend_coverage_proof",
            ],
            fallbacks_used=["synthetic_snapshot_history"],
            source_price_field="price",
            scope={},
        )

    if construction_method_hint == "sample_dataset":
        return ReturnBasisEvidence(
            verification_status="unverified",
            economic_basis="price_return_only",
            construction_method="sample_dataset",
            disqualifiers=[
                "sample_dataset",
                "missing_total_return_reconstruction",
                "missing_vendor_scope_proof",
            ],
            fallbacks_used=["sample_dataset"],
            source_price_field="price",
            scope={},
        )

    adjusted_field_names = {
        field_name
        for field_name in ("adjClose", "adjusted_close")
        if all(row.get(field_name) is not None for row in rows)
    }
    has_any_adjusted_field = bool(adjusted_field_names)

    if has_any_adjusted_field:
        source_price_field = "adjusted_close" if "adjusted_close" in adjusted_field_names else "adjClose"
        return ReturnBasisEvidence(
            verification_status="proxy",
            economic_basis="adjusted_close_proxy",
            construction_method="vendor_adjusted_close",
            disqualifiers=[
                "missing_dividend_coverage_proof",
                "missing_vendor_scope_proof",
                "adjusted_close_is_not_verified_total_return",
            ],
            source_price_field=source_price_field,
            scope={},
        )

    return ReturnBasisEvidence(
        verification_status="unverified",
        economic_basis="price_return_only",
        construction_method="raw_close",
        disqualifiers=[
            "missing_adjusted_close_series",
            "missing_total_return_reconstruction",
        ],
        source_price_field="price",
        scope={},
    )


def build_histories_return_basis_evidence(
    histories: dict[str, list[dict]],
    *,
    construction_method_hint: Literal["synthetic_snapshot_history", "sample_dataset"] | None = None,
) -> ReturnBasisEvidence:
    populated_histories = [rows for rows in histories.values() if rows]
    if not populated_histories:
        return build_history_return_basis_evidence([], construction_method_hint=construction_method_hint)

    evidences = [
        build_history_return_basis_evidence(rows, construction_method_hint=construction_method_hint)
        for rows in populated_histories
    ]

    verification_priority = {"verified": 3, "proxy": 2, "unverified": 1, "unavailable": 0}
    economic_priority = {"total_return": 3, "adjusted_close_proxy": 2, "price_return_only": 1, "unavailable": 0}
    representative = min(evidences, key=lambda item: verification_priority[item.verification_status])
    weakest_economic_basis = min(evidences, key=lambda item: economic_priority[item.economic_basis]).economic_basis
    disqualifiers = sorted({disqualifier for item in evidences for disqualifier in item.disqualifiers})
    fallbacks_used = sorted({fallback for item in evidences for fallback in item.fallbacks_used})
    source_fields = {item.source_price_field for item in evidences if item.source_price_field}

    return ReturnBasisEvidence(
        verification_status=representative.verification_status,
        economic_basis=weakest_economic_basis,
        construction_method=construction_method_hint or representative.construction_method,
        disqualifiers=disqualifiers,
        fallbacks_used=fallbacks_used,
        source_price_field=source_fields.pop() if len(source_fields) == 1 else None,
        scope={},
    )


def return_basis_contract_from_evidence(evidence: ReturnBasisEvidence) -> ReturnBasisContract:
    if evidence.verification_status == "verified" and evidence.economic_basis == "total_return":
        return "verified_total_return"
    if evidence.verification_status == "proxy" and evidence.economic_basis == "adjusted_close_proxy":
        return "unverified_adjusted_proxy"
    if evidence.verification_status == "unverified" and evidence.economic_basis == "price_return_only":
        return "price_return_only"
    return "unavailable"


def return_basis_path_trust_from_evidence(evidence: ReturnBasisEvidence) -> ReturnBasisPathTrust:
    if evidence.verification_status == "verified":
        return "verified_adjusted_close"
    if evidence.verification_status in {"proxy", "unverified"}:
        return "degraded_unverified_return_basis"
    return "unavailable"


def _canonical_history_range(from_date: str, to_date: str) -> tuple[str, str]:
    """Widen a requested history window to a canonical, deterministic superset
    range quantized to calendar-year boundaries (US-20.2).

    Every request whose window falls in the same year-span maps to the same
    ``(from, to)`` — and therefore the same FMP cache key — so the many
    overlapping ranges an analysis fetches (attribution display+window,
    correlation lookback, drift windows, provenance 30d, …) collapse onto one
    underlying fetch per symbol per span instead of one per distinct window.

    Pure function of the inputs (no wall-clock), so behaviour is reproducible.
    ISO dates (`YYYY-MM-DD`) sort lexicographically, so the year prefix is the
    quantization key.
    """
    return f"{from_date[:4]}-01-01", f"{to_date[:4]}-12-31"


def _slice_price_rows(rows: list[dict], from_date: str, to_date: str) -> list[dict]:
    """Slice canonical-range rows back to the caller's exact window.

    Returns exactly the bars a direct ``(from_date, to_date)`` fetch would —
    order preserved, nothing outside the window. ISO date strings compare
    chronologically under lexicographic ordering.
    """
    return [
        row for row in rows
        if isinstance(row.get("date"), str) and from_date <= row["date"] <= to_date
    ]


class MarketDataService:
    def __init__(self) -> None:
        self.client = FmpClient()
        self.holdings_history = HoldingsHistoryStore()
        self.last_fetch_meta: dict[str, dict[str, object]] = {}
        # Secondary provider, constructed lazily on first fallback use.
        self._yfinance_client: YFinanceClient | None = None
        # Guards the lazy build under parallel get_historical_prices_for_symbols (US-20.3).
        self._yfinance_lock = Lock()

    def _yfinance(self) -> YFinanceClient:
        if self._yfinance_client is None:
            with self._yfinance_lock:
                if self._yfinance_client is None:
                    self._yfinance_client = YFinanceClient()
        return self._yfinance_client

    def get_latest_quotes(self, symbols: Iterable[str], symbol_overrides: dict[str, list[str]] | None = None) -> dict[str, dict]:
        quotes: dict[str, dict] = {}
        for symbol in sorted({symbol for symbol in symbols if symbol}):
            requested_symbol = canonicalize_symbol(symbol)
            for candidate in resolve_symbol_candidates(requested_symbol, symbol_overrides, kind="quote"):
                try:
                    rows = self.client.get_quote_short(candidate)
                except MarketDataAuthError:
                    # US-35.1: a configuration failure is not a fact about this
                    # symbol, so it must not be flattened into "no data for it".
                    # Every OTHER exception still degrades below -- those catches
                    # are load-bearing for symbol resolution, which tries
                    # VUAA.L -> VUAA -> a US proxy and expects most to fail.
                    raise
                except Exception:  # noqa: BLE001
                    continue
                if rows:
                    quotes[requested_symbol] = rows[0] | {"requested_symbol": requested_symbol, "resolved_symbol": candidate}
                    self.last_fetch_meta[requested_symbol] = {"type": "quote", "resolved_symbol": candidate, "cached": True}
                    break
        return quotes

    @staticmethod
    def _sanitize_price_rows(rows: list[dict]) -> list[dict]:
        """Drop rows whose `price` is absent or non-finite (NaN/inf).

        A non-finite bar means "no data for that date" (e.g. Yahoo/pandas NaN
        for an untraded day) — it must never reach the engines or the JSON
        layer. Order and valid rows are preserved untouched. This is the single
        choke-point for all providers AND for already-cached poisoned entries.
        (Bug 2026-06-10: cached NaN bars 500'd the correlation routes.)
        """
        return [
            row for row in rows
            if isinstance(row.get("price"), (int, float)) and math.isfinite(row["price"])
        ]

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

        # US-20.2: fetch one canonical (year-quantized) superset range per
        # candidate — so overlapping windows share a cache key — then slice back
        # to the caller's exact (from, to). Sanitization happens BEFORE the
        # slice + truthiness check so an all-bad result counts as "no data" and
        # falls through to the next candidate/provider.
        canonical_from, canonical_to = _canonical_history_range(from_date, to_date)
        for candidate in ordered_candidates:
            try:
                rows = self._sanitize_price_rows(
                    self.client.get_historical_price_light(candidate, canonical_from, canonical_to)
                )
            except MarketDataAuthError:
                # US-35.1: a configuration failure is not a fact about this
                # symbol, so it must not be flattened into "no data for it".
                # Every OTHER exception still degrades below -- those catches
                # are load-bearing for symbol resolution, which tries
                # VUAA.L -> VUAA -> a US proxy and expects most to fail.
                raise
            except Exception:  # noqa: BLE001
                continue
            rows = _slice_price_rows(rows, from_date, to_date)
            if rows:
                self.last_fetch_meta[requested_symbol] = {"type": "history", "resolved_symbol": candidate, "cached": True, "vendor": "fmp"}
                return rows

        # Secondary provider (Yahoo Finance) fallback — only when FMP has nothing.
        # Uses the same real-symbol candidates (e.g. VUAA.L), never proxy substitutes.
        for candidate in symbol_candidates:
            try:
                rows = self._sanitize_price_rows(
                    self._yfinance().get_historical_price_light(candidate, canonical_from, canonical_to)
                )
            except MarketDataAuthError:
                # US-35.1: a configuration failure is not a fact about this
                # symbol, so it must not be flattened into "no data for it".
                # Every OTHER exception still degrades below -- those catches
                # are load-bearing for symbol resolution, which tries
                # VUAA.L -> VUAA -> a US proxy and expects most to fail.
                raise
            except Exception:  # noqa: BLE001
                continue
            rows = _slice_price_rows(rows, from_date, to_date)
            if rows:
                self.last_fetch_meta[requested_symbol] = {"type": "history", "resolved_symbol": candidate, "cached": True, "vendor": "yfinance"}
                return rows

        return []

    def get_direct_spy_benchmark_history(self, from_date: str, to_date: str) -> list[dict]:
        return self.get_direct_verified_benchmark_history("SPY", from_date, to_date)

    def get_direct_verified_benchmark_history(self, symbol: str, from_date: str, to_date: str) -> list[dict]:
        requested_symbol = canonicalize_symbol(symbol)
        if requested_symbol not in VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST:
            return []
        # US-20.2: the verified benchmark (SPY/QQQ) is fetched over many windows
        # (drift, dashboard, correlation) — normalize to the shared canonical
        # range and slice, same as get_historical_prices.
        canonical_from, canonical_to = _canonical_history_range(from_date, to_date)
        # US-34.9: the benchmark — and ONLY the benchmark — reads adjusted closes.
        # Position and FX history stay on `get_historical_price_light`, because a
        # dividend-adjusted series is a RETURN series, not a VALUE series: using
        # it to value holdings would make `total_market_value` disagree with the
        # broker's own statement. This method has no other callers, which is what
        # makes that scope enforceable rather than merely intended.
        try:
            rows = self._sanitize_price_rows(
                self.client.get_historical_price_dividend_adjusted(requested_symbol, canonical_from, canonical_to)
            )
        except MarketDataAuthError:
            # US-35.1: a configuration failure is not a fact about this
            # symbol, so it must not be flattened into "no data for it".
            # Every OTHER exception still degrades below -- those catches
            # are load-bearing for symbol resolution, which tries
            # VUAA.L -> VUAA -> a US proxy and expects most to fail.
            raise
        except Exception:  # noqa: BLE001
            return []
        rows = _slice_price_rows(rows, from_date, to_date)
        if rows:
            self.last_fetch_meta[requested_symbol] = {
                "type": "history",
                "requested_symbol": requested_symbol,
                "resolved_symbol": requested_symbol,
                "cached": True,
                "vendor": VERIFIED_BENCHMARK_VENDOR,
                "endpoint": VERIFIED_BENCHMARK_ENDPOINT,
                "direct_path_only": True,
                "fallback_used": False,
                "proxy_used": False,
                "mixed_source": False,
                "symbol_override_used": False,
            }
        return rows

    def get_historical_prices_for_symbols(
        self,
        symbols: Iterable[str],
        from_date: str,
        to_date: str,
        symbol_overrides: dict[str, list[str]] | None = None,
        *,
        allow_proxy_fallback: bool = False,
    ) -> dict[str, list[dict]]:
        # US-20.3: fetch symbols concurrently (I/O-bound: httpx + disk-cache
        # reads). Each get_historical_prices is independent and writes its own
        # last_fetch_meta key, so there is no shared-state race; results are
        # reassembled in the deterministic canonical-symbol order.
        requested_symbols = list(
            dict.fromkeys(canonicalize_symbol(symbol) for symbol in sorted({symbol for symbol in symbols if symbol}))
        )
        if not requested_symbols:
            return {}

        def _fetch(requested_symbol: str) -> tuple[str, list[dict]]:
            return requested_symbol, self.get_historical_prices(
                requested_symbol, from_date, to_date, symbol_overrides, allow_proxy_fallback=allow_proxy_fallback
            )

        if len(requested_symbols) == 1:
            symbol, rows = _fetch(requested_symbols[0])
            return {symbol: rows}

        fetched: dict[str, list[dict]] = {}
        with ThreadPoolExecutor(max_workers=min(8, len(requested_symbols))) as executor:
            for requested_symbol, rows in executor.map(_fetch, requested_symbols):
                fetched[requested_symbol] = rows
        return {requested_symbol: fetched[requested_symbol] for requested_symbol in requested_symbols}

    def get_fx_history(self, pair: str, from_date: str, to_date: str) -> list[dict]:
        return self.get_historical_prices(pair, from_date, to_date)

    def _profile_will_be_served_from_cache(self, symbol: str) -> bool:
        """Whether an FMP profile fetch for `symbol` is about to be answered
        from the on-disk cache rather than a live request (US-37.2 / T-37.2.2).

        `FmpClient.get_profile` -> `_get` has no return-side signal for cache
        hit/miss (only a log line), and this ticket's scope is
        `services/market_data.py` only -- adding one to `fmp.py` is out of
        scope. This instead reuses the cache wrapper's own already-public
        `build_key`/`get`, mirroring the exact namespace/path/params/TTL
        `_get` uses for a profile call, to answer the same question
        read-only and *before* the fetch (a post-fetch check cannot tell a
        hit from a fetch that just populated the cache).

        Narrow edge case, not resolvable without a signal from `fmp.py`: if
        this reports a miss but the live request that follows then fails and
        `_get` falls back to serving stale cached data, the response is in
        fact cache-served even though this reported `False` -- see risks.
        """
        cache = self.client.cache
        if cache is None:
            return False
        cache_identifier = json.dumps({"path": "profile", "params": {"symbol": symbol}}, sort_keys=True)
        cache_key = cache.build_key("profile", cache_identifier)
        return cache.get(cache_key, max_age_seconds=self.client.profile_ttl_seconds) is not None

    def get_company_profile(self, symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> dict | None:
        requested_symbol = canonicalize_symbol(symbol)
        for candidate in resolve_symbol_candidates(requested_symbol, symbol_overrides, kind="quote"):
            was_cached = self._profile_will_be_served_from_cache(candidate)
            try:
                rows = self.client.get_profile(candidate)
            except MarketDataAuthError:
                # US-35.1: a configuration failure is not a fact about this
                # symbol, so it must not be flattened into "no data for it".
                # Every OTHER exception still degrades below -- those catches
                # are load-bearing for symbol resolution, which tries
                # VUAA.L -> VUAA -> a US proxy and expects most to fail.
                raise
            except Exception:  # noqa: BLE001
                continue
            if rows:
                self.last_fetch_meta[requested_symbol] = {"type": "profile", "resolved_symbol": candidate, "cached": was_cached}
                return rows[0]
        return None

    def get_etf_holdings(self, symbol: str, symbol_overrides: dict[str, list[str]] | None = None) -> tuple[str | None, list[dict]]:
        requested_symbol = canonicalize_symbol(symbol)
        for candidate in resolve_etf_holdings_candidates(requested_symbol, symbol_overrides):
            try:
                rows = self.client.get_etf_holders(candidate)
            except MarketDataAuthError:
                # US-35.1: a configuration failure is not a fact about this
                # symbol, so it must not be flattened into "no data for it".
                # Every OTHER exception still degrades below -- those catches
                # are load-bearing for symbol resolution, which tries
                # VUAA.L -> VUAA -> a US proxy and expects most to fail.
                raise
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

    def get_last_fetch_meta(self, symbol: str) -> dict[str, object] | None:
        return self.last_fetch_meta.get(symbol)
