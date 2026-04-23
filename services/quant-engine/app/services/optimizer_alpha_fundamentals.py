from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.clients.fmp import FmpClient
from app.core.settings import get_settings
from app.instruments.registry import InstrumentRegistry
from app.schemas.optimizer import (
    OptimizerAlphaPitFundamentalRecord,
    OptimizerAlphaPitFundamentalsInput,
    OptimizerAlphaPitTrustIssue,
    OptimizerAlphaPitTrustReport,
)


ALPHA_QUALITY_PIT_SOURCE_NAME = "fmp_pit_ingestion_v1"
ALPHA_QUALITY_PIT_SOURCE_DATASET = "fmp_stable_fundamentals"
ALPHA_QUALITY_ALLOWED_CURRENCIES = frozenset({"USD"})
ALPHA_QUALITY_REQUIRED_FIELDS = (
    "total_revenue",
    "cost_of_revenue",
    "ebit",
    "total_assets",
    "operating_cash_flow",
    "free_cash_flow",
    "net_income",
    "total_debt",
    "cash_and_equivalents",
)
ALPHA_QUALITY_ALLOWED_PROFILE_EXCHANGES = frozenset(
    {
        "NASDAQ",
        "NASDAQ GLOBAL SELECT",
        "NASDAQ GLOBAL MARKET",
        "NASDAQ CAPITAL MARKET",
        "NEW YORK STOCK EXCHANGE",
        "NYSE",
        "NYSE AMERICAN",
    }
)
ALPHA_QUALITY_DISALLOWED_PROFILE_MARKERS = (
    "ETF",
    "ETN",
    "FUND",
    "TRUST",
    "PREFERRED",
    "RIGHT",
    "WARRANT",
    "UNIT",
    "ADR",
    "ADS",
    "OTC",
)
ALPHA_QUALITY_ALLOWED_PERIOD_TYPES = {"annual": "annual", "quarter": "quarterly"}


class AlphaQualityPitIngestionError(ValueError):
    pass


class AlphaQualityPitTrustError(ValueError):
    def __init__(self, report: OptimizerAlphaPitTrustReport) -> None:
        self.report = report
        codes = ", ".join(issue.code for issue in report.issues) or "unknown"
        super().__init__(f"PIT snapshot trust gate quarantined {report.as_of_date}: {codes}")


@dataclass(frozen=True)
class FmpStatementBundle:
    symbol: str
    profile: dict[str, Any]
    income_statements: list[dict[str, Any]]
    balance_sheets: list[dict[str, Any]]
    cash_flows: list[dict[str, Any]]


class AlphaQualityPitSnapshotStore:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.fmp_alpha_pit_snapshot_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def load(self, as_of_date: str) -> OptimizerAlphaPitFundamentalsInput | None:
        normalized_path = self._normalized_snapshot_path(as_of_date)
        if not normalized_path.exists():
            return None
        return load_alpha_pit_fundamentals_snapshot(normalized_path)

    def load_trust_report(self, as_of_date: str) -> OptimizerAlphaPitTrustReport | None:
        path = self.trust_report_path(as_of_date)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        return OptimizerAlphaPitTrustReport.model_validate(payload)

    def load_raw_payloads(self, as_of_date: str) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for path in self.raw_snapshot_paths(as_of_date):
            payloads.append(json.loads(path.read_text(encoding="utf-8")))
        return payloads

    def has_snapshot(self, as_of_date: str) -> bool:
        return self._normalized_snapshot_path(as_of_date).exists()

    def raw_snapshot_paths(self, as_of_date: str) -> list[Path]:
        raw_dir = self.base_dir / as_of_date / "raw"
        if not raw_dir.exists():
            return []
        return sorted(raw_dir.glob("*.json"))

    def coverage_manifest_path(self, as_of_date: str) -> Path:
        return self.base_dir / as_of_date / "normalized" / "coverage.json"

    def trust_report_path(self, as_of_date: str) -> Path:
        return self.base_dir / as_of_date / "normalized" / "trust_report.json"

    def persist_trust_report(self, report: OptimizerAlphaPitTrustReport) -> None:
        path = self.trust_report_path(report.as_of_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.model_dump(mode="json"), sort_keys=True), encoding="utf-8")

    def persist(
        self,
        *,
        pit_input: OptimizerAlphaPitFundamentalsInput,
        raw_payloads: list[dict[str, Any]],
        coverage: dict[str, list[str]],
    ) -> None:
        snapshot_dir = self.base_dir / pit_input.as_of_date
        raw_dir = snapshot_dir / "raw"
        normalized_dir = snapshot_dir / "normalized"
        raw_dir.mkdir(parents=True, exist_ok=True)
        normalized_dir.mkdir(parents=True, exist_ok=True)

        for payload in raw_payloads:
            symbol = str(payload["symbol"]).upper()
            digest = sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
            raw_path = raw_dir / f"{symbol}_{digest}.json"
            self._write_once(raw_path, payload)

        normalized_payload = pit_input.model_dump(mode="json")
        self._write_once(self._normalized_snapshot_path(pit_input.as_of_date), normalized_payload)
        self._write_once(
            normalized_dir / "coverage.json",
            {
                "as_of_date": pit_input.as_of_date,
                "decision_date": pit_input.decision_date,
                "source_name": pit_input.source_name,
                "replay_id": pit_input.replay_id,
                "coverage": coverage,
            },
        )

    def _normalized_snapshot_path(self, as_of_date: str) -> Path:
        return self.base_dir / as_of_date / "normalized" / "pit_fundamentals.json"

    def _write_once(self, path: Path, payload: dict[str, Any]) -> None:
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise AlphaQualityPitIngestionError(f"immutable snapshot conflict at {path}")
            return
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


class AlphaQualityPitIngestionService:
    def __init__(
        self,
        *,
        client: FmpClient | None = None,
        snapshot_store: AlphaQualityPitSnapshotStore | None = None,
        instrument_registry: InstrumentRegistry | None = None,
    ) -> None:
        self.client = client or FmpClient()
        self.snapshot_store = snapshot_store or AlphaQualityPitSnapshotStore()
        self.instrument_registry = instrument_registry or InstrumentRegistry()

    def load_or_ingest_for_universe(
        self,
        *,
        as_of_date: str,
        decision_date: str,
        universe_symbols: list[str],
    ) -> OptimizerAlphaPitFundamentalsInput:
        snapshot = self.snapshot_store.load(as_of_date)
        if snapshot is not None:
            expected_symbols = sorted({self.instrument_registry.normalize_symbol(symbol) for symbol in universe_symbols})
            if snapshot.universe_symbols != expected_symbols:
                raise AlphaQualityPitIngestionError(
                    f"persisted PIT snapshot universe mismatch for {as_of_date}: expected {expected_symbols}, found {snapshot.universe_symbols}"
                )
            return snapshot
        return self.ingest_for_universe(as_of_date=as_of_date, decision_date=decision_date, universe_symbols=universe_symbols)

    def ingest_for_universe(
        self,
        *,
        as_of_date: str,
        decision_date: str,
        universe_symbols: list[str],
    ) -> OptimizerAlphaPitFundamentalsInput:
        existing_snapshot = self.snapshot_store.load(as_of_date)
        if existing_snapshot is not None:
            expected_symbols = sorted({self.instrument_registry.normalize_symbol(symbol) for symbol in universe_symbols})
            if existing_snapshot.universe_symbols != expected_symbols:
                raise AlphaQualityPitIngestionError(
                    f"persisted PIT snapshot universe mismatch for {as_of_date}: expected {expected_symbols}, found {existing_snapshot.universe_symbols}"
                )
            return existing_snapshot
        ordered_symbols = self._eligible_target_symbols(universe_symbols)
        raw_payloads: list[dict[str, Any]] = []
        records: list[OptimizerAlphaPitFundamentalRecord] = []
        coverage = {"missing": [], "ambiguous": [], "incomplete": []}

        for symbol in ordered_symbols:
            try:
                bundle = self._fetch_bundle(symbol)
                raw_payloads.append(self._raw_payload(bundle=bundle, as_of_date=as_of_date, decision_date=decision_date))
                records.extend(self._normalize_bundle(bundle))
            except AlphaQualityPitIngestionError as exc:
                message = str(exc)
                if "ambiguous" in message:
                    coverage["ambiguous"].append(symbol)
                elif "missing required statement fields" in message or "missing approved effective date" in message:
                    coverage["incomplete"].append(symbol)
                else:
                    coverage["missing"].append(symbol)

        self._fail_closed_if_needed(ordered_symbols, coverage)
        pit_input = OptimizerAlphaPitFundamentalsInput(
            decision_date=decision_date,
            as_of_date=as_of_date,
            source_name=ALPHA_QUALITY_PIT_SOURCE_NAME,
            replay_id=f"alpha-quality-pit-{as_of_date}",
            universe_symbols=ordered_symbols,
            records=records,
        )
        self.snapshot_store.persist(pit_input=pit_input, raw_payloads=raw_payloads, coverage=coverage)
        return pit_input

    def _eligible_target_symbols(self, universe_symbols: list[str]) -> list[str]:
        ordered_symbols = sorted({self.instrument_registry.normalize_symbol(symbol) for symbol in universe_symbols})
        disallowed: list[str] = []
        eligible: list[str] = []
        for symbol in ordered_symbols:
            instrument = self.instrument_registry.get_instrument(symbol)
            if instrument is None or instrument.asset_class != "equity" or (instrument.currency or "").upper() != "USD":
                disallowed.append(symbol)
                continue
            eligible.append(symbol)
        if disallowed:
            raise AlphaQualityPitIngestionError(
                f"PIT ingestion supports only U.S. listed operating equities; ineligible optimizer symbols: {disallowed}"
            )
        return eligible

    def _fetch_bundle(self, symbol: str) -> FmpStatementBundle:
        profile_rows = self.client.get_profile(symbol)
        if not profile_rows:
            raise AlphaQualityPitIngestionError(f"missing issuer profile for {symbol}")
        if len(profile_rows) != 1:
            raise AlphaQualityPitIngestionError(f"ambiguous issuer profile for {symbol}")
        profile = profile_rows[0]
        self._validate_profile(symbol, profile)
        return FmpStatementBundle(
            symbol=symbol,
            profile=profile,
            income_statements=self.client.get_income_statements(symbol, limit=8, period="quarter"),
            balance_sheets=self.client.get_balance_sheet_statements(symbol, limit=8, period="quarter"),
            cash_flows=self.client.get_cash_flow_statements(symbol, limit=8, period="quarter"),
        )

    def _validate_profile(self, symbol: str, profile: dict[str, Any]) -> None:
        if str(profile.get("symbol") or "").upper() != symbol:
            raise AlphaQualityPitIngestionError(f"ambiguous symbol-to-issuer mapping for {symbol}")
        company_name = str(profile.get("companyName") or profile.get("name") or "").upper()
        exchange = str(profile.get("exchangeShortName") or profile.get("exchange") or "").upper()
        country = str(profile.get("country") or "").upper()
        industry = str(profile.get("industry") or "").upper()
        if not profile.get("cik"):
            raise AlphaQualityPitIngestionError(f"ambiguous issuer mapping for {symbol}: missing cik")
        if country not in {"US", "USA", "UNITED STATES"}:
            raise AlphaQualityPitIngestionError(f"missing or non-U.S. issuer coverage for {symbol}")
        if exchange not in ALPHA_QUALITY_ALLOWED_PROFILE_EXCHANGES:
            raise AlphaQualityPitIngestionError(f"missing or non-U.S. listed issuer coverage for {symbol}")
        if any(marker in company_name or marker in industry for marker in ALPHA_QUALITY_DISALLOWED_PROFILE_MARKERS):
            raise AlphaQualityPitIngestionError(f"missing or unsupported security type for {symbol}")
        if bool(profile.get("isEtf")) or bool(profile.get("isFund")) or bool(profile.get("isAdr")):
            raise AlphaQualityPitIngestionError(f"missing or unsupported security type for {symbol}")

    def _normalize_bundle(self, bundle: FmpStatementBundle) -> list[OptimizerAlphaPitFundamentalRecord]:
        issuer_id = str(bundle.profile.get("cik") or "").strip()
        if not issuer_id:
            raise AlphaQualityPitIngestionError(f"ambiguous issuer mapping for {bundle.symbol}: missing cik")
        income_by_key = self._statement_index(bundle.income_statements)
        balance_by_key = self._statement_index(bundle.balance_sheets)
        cash_flow_by_key = self._statement_index(bundle.cash_flows)
        common_keys = sorted(set(income_by_key) & set(balance_by_key) & set(cash_flow_by_key))
        if not common_keys:
            raise AlphaQualityPitIngestionError(f"missing vendor statements for {bundle.symbol}")

        records: list[OptimizerAlphaPitFundamentalRecord] = []
        for key in common_keys:
            income_statement = income_by_key[key]
            balance_statement = balance_by_key[key]
            cash_flow_statement = cash_flow_by_key[key]
            record = self._normalize_statement_set(
                symbol=bundle.symbol,
                issuer_id=issuer_id,
                income_statement=income_statement,
                balance_statement=balance_statement,
                cash_flow_statement=cash_flow_statement,
            )
            records.append(record)
        if not records:
            raise AlphaQualityPitIngestionError(f"missing vendor statements for {bundle.symbol}")
        return records

    def _normalize_statement_set(
        self,
        *,
        symbol: str,
        issuer_id: str,
        income_statement: dict[str, Any],
        balance_statement: dict[str, Any],
        cash_flow_statement: dict[str, Any],
    ) -> OptimizerAlphaPitFundamentalRecord:
        statement_date = self._required_date(symbol, income_statement, "date")
        period_type = self._period_type(symbol, income_statement)
        publication_date, filing_date, availability_semantics = self._approved_effective_date(symbol, income_statement)
        currency = self._statement_currency(symbol, income_statement, balance_statement, cash_flow_statement)
        source_record_id = self._source_record_id(symbol, income_statement, period_type, availability_semantics)
        return OptimizerAlphaPitFundamentalRecord.model_validate(
            {
                "source_dataset": ALPHA_QUALITY_PIT_SOURCE_DATASET,
                "source_record_id": source_record_id,
                "symbol": symbol,
                "issuer_id": issuer_id,
                "statement_date": statement_date,
                "period_type": period_type,
                "availability_semantics": availability_semantics,
                "publication_date": publication_date,
                "filing_date": filing_date,
                "currency": currency,
                "total_revenue": self._required_numeric(symbol, income_statement, "revenue"),
                "cost_of_revenue": self._required_numeric(symbol, income_statement, "costOfRevenue"),
                "ebit": self._required_numeric(symbol, income_statement, "ebit"),
                "total_assets": self._required_numeric(symbol, balance_statement, "totalAssets"),
                "operating_cash_flow": self._required_numeric(symbol, cash_flow_statement, "operatingCashFlow"),
                "free_cash_flow": self._required_numeric(symbol, cash_flow_statement, "freeCashFlow"),
                "net_income": self._required_numeric(symbol, income_statement, "netIncome"),
                "total_debt": self._required_numeric(symbol, balance_statement, "totalDebt"),
                "cash_and_equivalents": self._required_numeric(symbol, balance_statement, "cashAndCashEquivalents"),
            }
        )

    def _statement_index(self, rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
        indexed: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            date_value = row.get("date")
            period_value = str(row.get("period") or "").lower()
            if not date_value or period_value not in ALPHA_QUALITY_ALLOWED_PERIOD_TYPES:
                continue
            key = (str(date_value), period_value)
            if key in indexed:
                raise AlphaQualityPitIngestionError(f"ambiguous vendor statement set for {row.get('symbol') or 'unknown'}")
            indexed[key] = row
        return indexed

    def _approved_effective_date(
        self,
        symbol: str,
        statement: dict[str, Any],
    ) -> tuple[str | None, str | None, str]:
        publication_date = self._optional_date(statement.get("acceptedDate"))
        if publication_date is not None:
            return publication_date, None, "publication_date"
        filing_date = self._optional_date(statement.get("fillingDate")) or self._optional_date(statement.get("filingDate"))
        if filing_date is not None:
            return None, filing_date, "filing_date"
        raise AlphaQualityPitIngestionError(f"missing approved effective date for {symbol}")

    def _statement_currency(self, symbol: str, *statements: dict[str, Any]) -> str:
        currencies = {str(statement.get("reportedCurrency") or "").upper() for statement in statements if statement.get("reportedCurrency")}
        if len(currencies) != 1:
            raise AlphaQualityPitIngestionError(f"missing required statement fields for {symbol}: currency")
        currency = next(iter(currencies))
        if currency not in ALPHA_QUALITY_ALLOWED_CURRENCIES:
            raise AlphaQualityPitIngestionError(f"missing or unsupported currency coverage for {symbol}: {currency}")
        return currency

    def _period_type(self, symbol: str, statement: dict[str, Any]) -> str:
        period = str(statement.get("period") or "").lower()
        mapped = ALPHA_QUALITY_ALLOWED_PERIOD_TYPES.get(period)
        if mapped is None:
            raise AlphaQualityPitIngestionError(f"missing required statement fields for {symbol}: period")
        return mapped

    def _required_date(self, symbol: str, statement: dict[str, Any], field_name: str) -> str:
        value = self._optional_date(statement.get(field_name))
        if value is None:
            raise AlphaQualityPitIngestionError(f"missing required statement fields for {symbol}: {field_name}")
        return value

    def _required_numeric(self, symbol: str, statement: dict[str, Any], field_name: str) -> float:
        value = statement.get(field_name)
        if value is None:
            raise AlphaQualityPitIngestionError(f"missing required statement fields for {symbol}: {field_name}")
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise AlphaQualityPitIngestionError(f"missing required statement fields for {symbol}: {field_name}") from exc

    def _optional_date(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        if len(text) < 10:
            return None
        candidate = text[:10]
        try:
            datetime.fromisoformat(candidate)
        except ValueError:
            return None
        return candidate

    def _source_record_id(self, symbol: str, statement: dict[str, Any], period_type: str, semantics: str) -> str:
        statement_date = self._required_date(symbol, statement, "date")
        return f"{symbol}:{statement_date}:{period_type}:{semantics}"

    def _raw_payload(self, *, bundle: FmpStatementBundle, as_of_date: str, decision_date: str) -> dict[str, Any]:
        return {
            "symbol": bundle.symbol,
            "as_of_date": as_of_date,
            "decision_date": decision_date,
            "source_name": ALPHA_QUALITY_PIT_SOURCE_NAME,
            "fetched_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "profile": bundle.profile,
            "income_statements": bundle.income_statements,
            "balance_sheets": bundle.balance_sheets,
            "cash_flows": bundle.cash_flows,
        }

    def _fail_closed_if_needed(self, ordered_symbols: list[str], coverage: dict[str, list[str]]) -> None:
        if not any(coverage.values()):
            return
        message = (
            "PIT ingestion failed closed for alpha_quality_v1 coverage: "
            f"missing={sorted(coverage['missing'])}, "
            f"ambiguous={sorted(coverage['ambiguous'])}, "
            f"incomplete={sorted(coverage['incomplete'])}, "
            f"universe={ordered_symbols}"
        )
        raise AlphaQualityPitIngestionError(message)


def load_alpha_pit_fundamentals_snapshot(file_path: str | Path) -> OptimizerAlphaPitFundamentalsInput:
    path = Path(file_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    return OptimizerAlphaPitFundamentalsInput.model_validate(payload)


class AlphaQualityPitTrustGate:
    def __init__(
        self,
        *,
        snapshot_store: AlphaQualityPitSnapshotStore | None = None,
        instrument_registry: InstrumentRegistry | None = None,
    ) -> None:
        self.snapshot_store = snapshot_store or AlphaQualityPitSnapshotStore()
        self.instrument_registry = instrument_registry or InstrumentRegistry()
        self._replay_service = AlphaQualityPitIngestionService(
            snapshot_store=self.snapshot_store,
            instrument_registry=self.instrument_registry,
        )

    def assert_trusted_snapshot(
        self,
        *,
        as_of_date: str,
        decision_date: str,
        universe_symbols: list[str],
    ) -> OptimizerAlphaPitFundamentalsInput:
        report = self.validate_snapshot(
            as_of_date=as_of_date,
            decision_date=decision_date,
            universe_symbols=universe_symbols,
        )
        if report.status != "trusted":
            raise AlphaQualityPitTrustError(report)
        snapshot = self.snapshot_store.load(as_of_date)
        if snapshot is None:
            raise AlphaQualityPitTrustError(report)
        return snapshot

    def validate_snapshot(
        self,
        *,
        as_of_date: str,
        decision_date: str,
        universe_symbols: list[str],
    ) -> OptimizerAlphaPitTrustReport:
        requested_symbols = sorted({self.instrument_registry.normalize_symbol(symbol) for symbol in universe_symbols})
        issues: list[OptimizerAlphaPitTrustIssue] = []
        snapshot: OptimizerAlphaPitFundamentalsInput | None = None
        raw_payloads: list[dict[str, Any]] = []
        replay_snapshot: OptimizerAlphaPitFundamentalsInput | None = None
        persisted_digest: str | None = None
        replay_digest: str | None = None
        raw_snapshot_symbols: list[str] = []
        snapshot_universe_symbols: list[str] = []

        def add_issue(code: str, message: str, **details: Any) -> None:
            issues.append(OptimizerAlphaPitTrustIssue(code=code, message=message, details=details))

        if not self.snapshot_store.coverage_manifest_path(as_of_date).exists():
            add_issue(
                "missing_coverage_manifest",
                "Immutable PIT coverage manifest is missing for the requested as_of_date.",
                as_of_date=as_of_date,
            )

        try:
            approved_requested_symbols = self._replay_service._eligible_target_symbols(universe_symbols)
        except AlphaQualityPitIngestionError as exc:
            approved_requested_symbols = []
            add_issue(
                "unsupported_requested_universe",
                "Requested optimizer universe falls outside the approved PIT trust gate coverage.",
                as_of_date=as_of_date,
                requested_universe_symbols=requested_symbols,
                error=str(exc),
            )

        try:
            snapshot = self.snapshot_store.load(as_of_date)
        except Exception as exc:
            add_issue(
                "invalid_normalized_snapshot",
                "Persisted normalized PIT snapshot cannot be parsed deterministically.",
                as_of_date=as_of_date,
                error=str(exc),
            )

        if snapshot is None:
            add_issue(
                "missing_normalized_snapshot",
                "Immutable normalized PIT snapshot is missing for the requested as_of_date.",
                as_of_date=as_of_date,
            )
        else:
            snapshot_universe_symbols = list(snapshot.universe_symbols)
            persisted_digest = _pit_input_digest(snapshot)
            if snapshot.as_of_date != as_of_date:
                add_issue(
                    "stale_normalized_snapshot",
                    "Persisted normalized PIT snapshot embeds a different as_of_date than the requested directory.",
                    requested_as_of_date=as_of_date,
                    embedded_as_of_date=snapshot.as_of_date,
                )
            if requested_symbols != snapshot.universe_symbols:
                add_issue(
                    "snapshot_universe_mismatch",
                    "Persisted normalized PIT snapshot universe does not match the requested optimizer universe.",
                    requested_universe_symbols=requested_symbols,
                    snapshot_universe_symbols=snapshot.universe_symbols,
                )
            duplicates = _duplicate_record_keys(snapshot.records)
            if duplicates:
                add_issue(
                    "duplicate_normalized_records",
                    "Persisted normalized PIT snapshot contains duplicate records for the same lineage key.",
                    duplicates=duplicates,
                )
            unsupported_restatements = _unsupported_restatement_keys(snapshot.records)
            if unsupported_restatements:
                add_issue(
                    "unsupported_restatement_pattern",
                    "Persisted normalized PIT snapshot contains multiple records for the same symbol, statement_date, and period_type.",
                    duplicate_statement_sets=unsupported_restatements,
                )

        try:
            raw_payloads = self.snapshot_store.load_raw_payloads(as_of_date)
        except Exception as exc:
            add_issue(
                "invalid_raw_snapshot",
                "Immutable raw PIT snapshot payloads cannot be parsed deterministically.",
                as_of_date=as_of_date,
                error=str(exc),
            )
            raw_payloads = []

        if not raw_payloads:
            add_issue(
                "missing_raw_snapshots",
                "Immutable raw PIT snapshot payloads are missing for the requested as_of_date.",
                as_of_date=as_of_date,
            )

        raw_by_symbol: dict[str, list[dict[str, Any]]] = {}
        for payload in raw_payloads:
            symbol = self.instrument_registry.normalize_symbol(str(payload.get("symbol") or ""))
            if not symbol:
                add_issue(
                    "invalid_raw_snapshot_symbol",
                    "A raw PIT payload is missing its symbol lineage key.",
                    payload=payload,
                )
                continue
            raw_by_symbol.setdefault(symbol, []).append(payload)
            if str(payload.get("as_of_date") or "") != as_of_date:
                add_issue(
                    "stale_raw_snapshot",
                    "A raw PIT payload embeds a different as_of_date than the requested directory.",
                    symbol=symbol,
                    requested_as_of_date=as_of_date,
                    embedded_as_of_date=payload.get("as_of_date"),
                )
            if snapshot is not None and str(payload.get("decision_date") or "") != snapshot.decision_date:
                add_issue(
                    "raw_snapshot_decision_date_mismatch",
                    "A raw PIT payload decision_date does not match the normalized snapshot decision_date.",
                    symbol=symbol,
                    raw_decision_date=payload.get("decision_date"),
                    snapshot_decision_date=snapshot.decision_date,
                )

        duplicate_raw_symbols = sorted(symbol for symbol, payloads in raw_by_symbol.items() if len(payloads) > 1)
        if duplicate_raw_symbols:
            add_issue(
                "duplicate_raw_snapshots",
                "Immutable raw PIT payloads contain duplicate symbol bundles for the same as_of_date.",
                duplicate_symbols=duplicate_raw_symbols,
            )

        raw_snapshot_symbols = sorted(raw_by_symbol)
        if snapshot is not None:
            missing_raw_symbols = sorted(set(snapshot.universe_symbols) - set(raw_snapshot_symbols))
            extra_raw_symbols = sorted(set(raw_snapshot_symbols) - set(snapshot.universe_symbols))
            if missing_raw_symbols:
                add_issue(
                    "missing_raw_snapshot_symbols",
                    "Immutable raw PIT payloads are missing required symbol bundles declared by the normalized snapshot.",
                    missing_symbols=missing_raw_symbols,
                )
            if extra_raw_symbols:
                add_issue(
                    "unexpected_raw_snapshot_symbols",
                    "Immutable raw PIT payloads contain symbol bundles outside the normalized snapshot universe.",
                    unexpected_symbols=extra_raw_symbols,
                )

        for symbol, payload_list in raw_by_symbol.items():
            if len(payload_list) != 1:
                continue
            payload = payload_list[0]
            profile = payload.get("profile")
            if not isinstance(profile, dict):
                add_issue(
                    "invalid_raw_profile",
                    "A raw PIT payload is missing its issuer profile required for lineage validation.",
                    symbol=symbol,
                )
                continue
            try:
                self._replay_service._validate_profile(symbol, profile)
            except AlphaQualityPitIngestionError as exc:
                add_issue(
                    "unsupported_raw_profile",
                    "A raw PIT payload fails the approved U.S. operating equity universe checks.",
                    symbol=symbol,
                    error=str(exc),
                )

        if snapshot is not None:
            try:
                self._assert_snapshot_records_are_usd(snapshot)
                self._assert_snapshot_universe_is_approved(snapshot.universe_symbols)
            except AlphaQualityPitIngestionError as exc:
                add_issue(
                    "unsupported_snapshot_coverage",
                    "Persisted normalized PIT snapshot falls outside the approved alpha_quality_v1 coverage contract.",
                    error=str(exc),
                    snapshot_universe_symbols=snapshot.universe_symbols,
                )

        if snapshot is not None and not any(issue.code in _REPLAY_BLOCKING_CODES for issue in issues):
            try:
                replay_snapshot = self._replay_snapshot(snapshot=snapshot, raw_by_symbol=raw_by_symbol, requested_symbols=approved_requested_symbols)
                replay_digest = _pit_input_digest(replay_snapshot)
                if replay_snapshot.model_dump(mode="json") != snapshot.model_dump(mode="json"):
                    add_issue(
                        "replay_mismatch",
                        "Deterministic PIT replay from immutable raw payloads does not match the persisted normalized snapshot.",
                        persisted_input_digest=persisted_digest,
                        replay_input_digest=replay_digest,
                    )
            except AlphaQualityPitIngestionError as exc:
                add_issue(
                    "replay_failed",
                    "Deterministic PIT replay failed closed from immutable raw payloads.",
                    error=str(exc),
                )

        report = OptimizerAlphaPitTrustReport(
            status="quarantined" if issues else "trusted",
            as_of_date=as_of_date,
            decision_date=snapshot.decision_date if snapshot is not None else decision_date,
            source_name=snapshot.source_name if snapshot is not None else None,
            replay_id=snapshot.replay_id if snapshot is not None else None,
            requested_universe_symbols=requested_symbols,
            snapshot_universe_symbols=snapshot_universe_symbols,
            raw_snapshot_symbols=raw_snapshot_symbols,
            normalized_record_count=len(snapshot.records) if snapshot is not None else 0,
            raw_bundle_count=len(raw_payloads),
            lineage_valid=not any(issue.code in _LINEAGE_FAILURE_CODES for issue in issues),
            replay_valid=not any(issue.code in _REPLAY_FAILURE_CODES for issue in issues),
            approved_universe_valid=not any(issue.code in _UNIVERSE_FAILURE_CODES for issue in issues),
            persisted_input_digest=persisted_digest,
            replay_input_digest=replay_digest,
            issues=issues,
        )
        self.snapshot_store.persist_trust_report(report)
        return report

    def _replay_snapshot(
        self,
        *,
        snapshot: OptimizerAlphaPitFundamentalsInput,
        raw_by_symbol: dict[str, list[dict[str, Any]]],
        requested_symbols: list[str],
    ) -> OptimizerAlphaPitFundamentalsInput:
        records: list[OptimizerAlphaPitFundamentalRecord] = []
        for symbol in requested_symbols:
            payloads = raw_by_symbol.get(symbol)
            if payloads is None or len(payloads) != 1:
                raise AlphaQualityPitIngestionError(f"missing immutable raw bundle for {symbol}")
            payload = payloads[0]
            bundle = FmpStatementBundle(
                symbol=symbol,
                profile=dict(payload.get("profile") or {}),
                income_statements=[dict(item) for item in payload.get("income_statements") or []],
                balance_sheets=[dict(item) for item in payload.get("balance_sheets") or []],
                cash_flows=[dict(item) for item in payload.get("cash_flows") or []],
            )
            records.extend(self._replay_service._normalize_bundle(bundle))
        return OptimizerAlphaPitFundamentalsInput(
            decision_date=snapshot.decision_date,
            as_of_date=snapshot.as_of_date,
            source_name=snapshot.source_name,
            replay_id=snapshot.replay_id,
            universe_symbols=list(snapshot.universe_symbols),
            records=records,
        )

    def _assert_snapshot_records_are_usd(self, snapshot: OptimizerAlphaPitFundamentalsInput) -> None:
        invalid_symbols = sorted({record.symbol for record in snapshot.records if (record.currency or "").upper() != "USD"})
        if invalid_symbols:
            raise AlphaQualityPitIngestionError(
                f"PIT trust gate supports only USD denominated records; invalid symbols: {invalid_symbols}"
            )

    def _assert_snapshot_universe_is_approved(self, universe_symbols: list[str]) -> None:
        self._replay_service._eligible_target_symbols(universe_symbols)


_LINEAGE_FAILURE_CODES = {
    "missing_coverage_manifest",
    "invalid_normalized_snapshot",
    "missing_normalized_snapshot",
    "stale_normalized_snapshot",
    "duplicate_normalized_records",
    "unsupported_restatement_pattern",
    "invalid_raw_snapshot",
    "missing_raw_snapshots",
    "invalid_raw_snapshot_symbol",
    "stale_raw_snapshot",
    "raw_snapshot_decision_date_mismatch",
    "duplicate_raw_snapshots",
    "missing_raw_snapshot_symbols",
    "unexpected_raw_snapshot_symbols",
    "invalid_raw_profile",
}

_REPLAY_FAILURE_CODES = {
    "invalid_normalized_snapshot",
    "missing_normalized_snapshot",
    "invalid_raw_snapshot",
    "missing_raw_snapshots",
    "duplicate_raw_snapshots",
    "missing_raw_snapshot_symbols",
    "unexpected_raw_snapshot_symbols",
    "replay_failed",
    "replay_mismatch",
}

_UNIVERSE_FAILURE_CODES = {
    "unsupported_requested_universe",
    "snapshot_universe_mismatch",
    "unsupported_raw_profile",
    "unsupported_snapshot_coverage",
}

_REPLAY_BLOCKING_CODES = _LINEAGE_FAILURE_CODES | _UNIVERSE_FAILURE_CODES


def _duplicate_record_keys(records: list[OptimizerAlphaPitFundamentalRecord]) -> list[str]:
    counts: dict[str, int] = {}
    for record in records:
        key = _record_lineage_key(record)
        counts[key] = counts.get(key, 0) + 1
    return sorted(key for key, count in counts.items() if count > 1)


def _record_lineage_key(record: OptimizerAlphaPitFundamentalRecord) -> str:
    return "|".join(
        [
            record.symbol,
            record.statement_date,
            record.period_type,
            record.availability_semantics,
            record.source_dataset,
            record.source_record_id,
        ]
    )


def _pit_input_digest(snapshot: OptimizerAlphaPitFundamentalsInput) -> str:
    records_payload = [record.model_dump(mode="json") for record in sorted(snapshot.records, key=_pit_record_digest_sort_key)]
    payload = {
        "decision_date": snapshot.decision_date,
        "as_of_date": snapshot.as_of_date,
        "source_name": snapshot.source_name,
        "replay_id": snapshot.replay_id,
        "universe_symbols": sorted({symbol.upper() for symbol in snapshot.universe_symbols}),
        "records": records_payload,
    }
    return f"pit_{sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()[:16]}"


def _unsupported_restatement_keys(records: list[OptimizerAlphaPitFundamentalRecord]) -> list[str]:
    counts: dict[str, int] = {}
    for record in records:
        key = "|".join([record.symbol, record.statement_date, record.period_type])
        counts[key] = counts.get(key, 0) + 1
    return sorted(key for key, count in counts.items() if count > 1)


def _pit_record_digest_sort_key(record: OptimizerAlphaPitFundamentalRecord) -> tuple[str, str, str, str, str, str]:
    effective_date = record.available_date or record.publication_date or record.filing_date or record.statement_date
    return (
        record.symbol.upper(),
        record.statement_date,
        record.period_type,
        effective_date,
        record.source_dataset.strip(),
        record.source_record_id.strip(),
    )
