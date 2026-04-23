from __future__ import annotations

from typing import Iterable, Literal

from app.core.symbols import canonicalize_symbol, resolve_etf_holdings_candidates, resolve_symbol_candidates
from app.clients.fmp import FmpClient
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
VERIFIED_BENCHMARK_ENDPOINT = "historical-price-eod/light"


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


class MarketDataService:
    def __init__(self) -> None:
        self.client = FmpClient()
        self.holdings_history = HoldingsHistoryStore()
        self.last_fetch_meta: dict[str, dict[str, object]] = {}

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

    def get_direct_spy_benchmark_history(self, from_date: str, to_date: str) -> list[dict]:
        return self.get_direct_verified_benchmark_history("SPY", from_date, to_date)

    def get_direct_verified_benchmark_history(self, symbol: str, from_date: str, to_date: str) -> list[dict]:
        requested_symbol = canonicalize_symbol(symbol)
        if requested_symbol not in VERIFIED_BENCHMARK_SYMBOL_ALLOWLIST:
            return []
        try:
            rows = self.client.get_historical_price_light(requested_symbol, from_date, to_date)
        except Exception:  # noqa: BLE001
            return []
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

    def get_last_fetch_meta(self, symbol: str) -> dict[str, object] | None:
        return self.last_fetch_meta.get(symbol)
