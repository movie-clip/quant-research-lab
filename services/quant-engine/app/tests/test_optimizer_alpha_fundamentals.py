from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from app.services.optimizer_alpha_fundamentals import (
    ALPHA_QUALITY_PIT_SOURCE_NAME,
    AlphaQualityPitIngestionError,
    AlphaQualityPitIngestionService,
    AlphaQualityPitSnapshotStore,
    AlphaQualityPitTrustError,
    AlphaQualityPitTrustGate,
)
from app.services.optimizer_alpha_service import build_alpha_quality_package_from_live_pit_universe


def _profile(symbol: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "companyName": f"{symbol} Operating Co",
        "exchangeShortName": "NASDAQ",
        "country": "US",
        "industry": "SOFTWARE",
        "cik": f"00000{symbol}",
        "isEtf": False,
        "isFund": False,
        "isAdr": False,
    }


def _income_statement(symbol: str, *, accepted_date: str | None = "2024-03-20 16:01:00") -> dict[str, object]:
    return {
        "symbol": symbol,
        "date": "2023-12-31",
        "period": "quarter",
        "acceptedDate": accepted_date,
        "revenue": 1000.0,
        "costOfRevenue": 400.0,
        "ebit": 200.0,
        "netIncome": 150.0,
        "reportedCurrency": "USD",
    }


def _balance_sheet(symbol: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "date": "2023-12-31",
        "period": "quarter",
        "totalAssets": 800.0,
        "totalDebt": 160.0,
        "cashAndCashEquivalents": 60.0,
        "reportedCurrency": "USD",
    }


def _cash_flow(symbol: str) -> dict[str, object]:
    return {
        "symbol": symbol,
        "date": "2023-12-31",
        "period": "quarter",
        "operatingCashFlow": 180.0,
        "freeCashFlow": 120.0,
        "reportedCurrency": "USD",
    }


class FakeFmpClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.profiles: dict[str, list[dict[str, object]]] = {}
        self.income_statements: dict[str, list[dict[str, object]]] = {}
        self.balance_sheets: dict[str, list[dict[str, object]]] = {}
        self.cash_flows: dict[str, list[dict[str, object]]] = {}

    def get_profile(self, symbol: str) -> list[dict[str, object]]:
        self.calls.append(("profile", symbol))
        return self.profiles.get(symbol, [])

    def get_income_statements(self, symbol: str, *, limit: int = 8, period: str = "quarter") -> list[dict[str, object]]:
        self.calls.append(("income", symbol))
        return self.income_statements.get(symbol, [])

    def get_balance_sheet_statements(self, symbol: str, *, limit: int = 8, period: str = "quarter") -> list[dict[str, object]]:
        self.calls.append(("balance", symbol))
        return self.balance_sheets.get(symbol, [])

    def get_cash_flow_statements(self, symbol: str, *, limit: int = 8, period: str = "quarter") -> list[dict[str, object]]:
        self.calls.append(("cash_flow", symbol))
        return self.cash_flows.get(symbol, [])


def _build_client(symbols: list[str]) -> FakeFmpClient:
    client = FakeFmpClient()
    for symbol in symbols:
        client.profiles[symbol] = [_profile(symbol)]
        client.income_statements[symbol] = [_income_statement(symbol)]
        client.balance_sheets[symbol] = [_balance_sheet(symbol)]
        client.cash_flows[symbol] = [_cash_flow(symbol)]
    return client


def test_ingest_alpha_quality_pit_snapshot_persists_raw_and_normalized(tmp_path: Path) -> None:
    client = _build_client(["AAPL", "MSFT"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)

    pit_input = service.ingest_for_universe(
        as_of_date="2024-04-15",
        decision_date="2024-04-15",
        universe_symbols=["MSFT", "AAPL"],
    )

    assert pit_input.source_name == ALPHA_QUALITY_PIT_SOURCE_NAME
    assert pit_input.universe_symbols == ["AAPL", "MSFT"]
    assert len(pit_input.records) == 2
    assert {record.symbol for record in pit_input.records} == {"AAPL", "MSFT"}
    assert all(record.availability_semantics == "publication_date" for record in pit_input.records)
    assert all(record.currency == "USD" for record in pit_input.records)

    normalized_path = tmp_path / "2024-04-15" / "normalized" / "pit_fundamentals.json"
    coverage_path = tmp_path / "2024-04-15" / "normalized" / "coverage.json"
    raw_paths = sorted((tmp_path / "2024-04-15" / "raw").glob("*.json"))
    assert normalized_path.exists()
    assert coverage_path.exists()
    assert len(raw_paths) == 2
    coverage_payload = json.loads(coverage_path.read_text(encoding="utf-8"))
    assert coverage_payload["coverage"] == {"missing": [], "ambiguous": [], "incomplete": []}


def test_load_or_ingest_replays_snapshot_without_vendor_queries(tmp_path: Path) -> None:
    ingest_client = _build_client(["AAPL", "MSFT"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    ingestion_service = AlphaQualityPitIngestionService(client=cast(Any, ingest_client), snapshot_store=snapshot_store)
    ingestion_service.ingest_for_universe(
        as_of_date="2024-04-15",
        decision_date="2024-04-15",
        universe_symbols=["AAPL", "MSFT"],
    )

    replay_client = FakeFmpClient()
    replay_service = AlphaQualityPitIngestionService(client=cast(Any, replay_client), snapshot_store=snapshot_store)
    package = build_alpha_quality_package_from_live_pit_universe(
        rebalance_date="2024-04-15",
        as_of_date="2024-04-15",
        universe_symbols=["MSFT", "AAPL"],
        ingestion_service=replay_service,
    )

    assert replay_client.calls == []
    assert package.metadata.input_descriptor.source_name == ALPHA_QUALITY_PIT_SOURCE_NAME
    assert package.metadata.input_descriptor.input_digest.startswith("pit_")
    assert package.metadata.input_descriptor.pit_provenance is not None
    assert package.metadata.input_descriptor.pit_provenance.trust_status == "trusted"
    assert package.metadata.input_descriptor.pit_provenance.as_of_date == "2024-04-15"
    assert package.metadata.input_descriptor.pit_provenance.snapshot_digest == package.metadata.input_descriptor.input_digest
    assert package.diagnostics.status == "ok"
    assert package.ordered_symbols == ["AAPL", "MSFT"]

    trust_report_path = tmp_path / "2024-04-15" / "normalized" / "trust_report.json"
    assert trust_report_path.exists()
    trust_report = json.loads(trust_report_path.read_text(encoding="utf-8"))
    assert trust_report["status"] == "trusted"
    assert trust_report["lineage_valid"] is True
    assert trust_report["replay_valid"] is True
    assert trust_report["approved_universe_valid"] is True
    assert trust_report["issues"] == []


def test_ingestion_fails_closed_for_missing_ambiguous_and_incomplete_coverage(tmp_path: Path) -> None:
    client = FakeFmpClient()
    client.profiles["AAPL"] = [_profile("AAPL"), _profile("AAPL")]
    client.profiles["MSFT"] = [_profile("MSFT")]
    client.income_statements["MSFT"] = [_income_statement("MSFT", accepted_date=None)]
    client.balance_sheets["MSFT"] = [_balance_sheet("MSFT")]
    client.cash_flows["MSFT"] = [_cash_flow("MSFT")]

    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)

    with pytest.raises(AlphaQualityPitIngestionError) as exc_info:
        service.ingest_for_universe(
            as_of_date="2024-04-15",
            decision_date="2024-04-15",
            universe_symbols=["AAPL", "MSFT", "GOOG"],
        )

    message = str(exc_info.value)
    assert "missing=['GOOG']" in message
    assert "ambiguous=['AAPL']" in message
    assert "incomplete=['MSFT']" in message
    assert not (tmp_path / "2024-04-15" / "normalized" / "pit_fundamentals.json").exists()


def test_ingestion_rejects_non_operating_equity_universe_members(tmp_path: Path) -> None:
    client = _build_client(["AAPL"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)

    with pytest.raises(AlphaQualityPitIngestionError) as exc_info:
        service.ingest_for_universe(
            as_of_date="2024-04-15",
            decision_date="2024-04-15",
            universe_symbols=["AAPL", "VNQ"],
        )

    assert "ineligible optimizer symbols: ['VNQ']" in str(exc_info.value)


def test_trust_gate_quarantines_snapshot_when_replay_diverges(tmp_path: Path) -> None:
    client = _build_client(["AAPL", "MSFT"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)
    service.ingest_for_universe(
        as_of_date="2024-04-15",
        decision_date="2024-04-15",
        universe_symbols=["AAPL", "MSFT"],
    )

    normalized_path = tmp_path / "2024-04-15" / "normalized" / "pit_fundamentals.json"
    payload = json.loads(normalized_path.read_text(encoding="utf-8"))
    payload["records"][0]["total_revenue"] = 9999.0
    normalized_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    gate = AlphaQualityPitTrustGate(snapshot_store=snapshot_store)
    report = gate.validate_snapshot(
        as_of_date="2024-04-15",
        decision_date="2024-04-15",
        universe_symbols=["MSFT", "AAPL"],
    )

    assert report.status == "quarantined"
    assert report.lineage_valid is True
    assert report.replay_valid is False
    assert report.approved_universe_valid is True
    assert [issue.code for issue in report.issues] == ["replay_mismatch"]


def test_trust_gate_detects_missing_and_duplicate_raw_snapshots(tmp_path: Path) -> None:
    client = _build_client(["AAPL", "MSFT"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)
    service.ingest_for_universe(
        as_of_date="2024-04-15",
        decision_date="2024-04-15",
        universe_symbols=["AAPL", "MSFT"],
    )

    raw_dir = tmp_path / "2024-04-15" / "raw"
    raw_paths = sorted(raw_dir.glob("*.json"))
    assert len(raw_paths) == 2
    duplicate_payload = json.loads(raw_paths[0].read_text(encoding="utf-8"))
    (raw_dir / "AAPL_duplicate.json").write_text(json.dumps(duplicate_payload, sort_keys=True), encoding="utf-8")
    raw_paths[1].unlink()

    gate = AlphaQualityPitTrustGate(snapshot_store=snapshot_store)
    report = gate.validate_snapshot(
        as_of_date="2024-04-15",
        decision_date="2024-04-15",
        universe_symbols=["AAPL", "MSFT"],
    )

    issue_codes = {issue.code for issue in report.issues}
    assert report.status == "quarantined"
    assert report.lineage_valid is False
    assert report.replay_valid is False
    assert "duplicate_raw_snapshots" in issue_codes
    assert "missing_raw_snapshot_symbols" in issue_codes


def test_live_pit_package_build_blocks_quarantined_snapshot(tmp_path: Path) -> None:
    client = _build_client(["AAPL", "MSFT"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    ingestion_service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)
    ingestion_service.ingest_for_universe(
        as_of_date="2024-04-15",
        decision_date="2024-04-15",
        universe_symbols=["AAPL", "MSFT"],
    )

    raw_path = sorted((tmp_path / "2024-04-15" / "raw").glob("AAPL_*.json"))[0]
    payload = json.loads(raw_path.read_text(encoding="utf-8"))
    payload["as_of_date"] = "2024-04-16"
    raw_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(AlphaQualityPitTrustError) as exc_info:
        build_alpha_quality_package_from_live_pit_universe(
            rebalance_date="2024-04-15",
            as_of_date="2024-04-15",
            universe_symbols=["MSFT", "AAPL"],
            ingestion_service=ingestion_service,
        )

    report = exc_info.value.report
    assert report.status == "quarantined"
    assert {issue.code for issue in report.issues} == {"stale_raw_snapshot"}
