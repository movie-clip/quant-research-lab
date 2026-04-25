from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
from hashlib import sha256
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from pydantic import ValidationError

from app.core.settings import get_settings
from app.schemas.backtest_engine import (
    CreateMonitorDefinitionRequest,
    MonitorDefinitionArtifact,
    MonitorDefinitionArtifactListItem,
    MonitorDefinitionCatalogResponseMetadata,
    MonitorDefinitionCatalogResponse,
    MonitorDefinitionCatalogRowMetadata,
    MonitorDefinitionCatalogRow,
    MonitorDefinitionDiscoveryFilters,
    MonitorDefinitionEvaluationHistoryEntryArtifact,
    MonitorDefinitionEvaluationHistoryEntryResponse,
    MonitorDefinitionEvaluationHistoryEntryResponseMetadata,
    MonitorDefinitionEvaluationHistoryResponse,
    MonitorDefinitionEvaluationHistoryResponseMetadata,
    MonitorDefinitionEvaluationHistoryRow,
    MonitorDefinitionLatestEvaluationSnapshotArtifact,
    MonitorDefinitionLatestEvaluationSnapshotSummary,
    MonitorDefinitionLatestEvaluationSnapshotStatus,
    MonitorDefinitionLatestEvaluationSignificanceStatus,
    MonitorDefinitionLatestEvaluationSnapshotRecency,
    MonitorDefinitionObservationStatus,
    MonitorDefinitionRecentResponseMetadata,
    MonitorDefinitionRecentResponse,
    MonitorDefinitionRecentRowMetadata,
    MonitorDefinitionRecentRow,
    MonitorDefinitionStatusMetadata,
)


class MonitorDefinitionPersistenceError(ValueError):
    pass


class MonitorDefinitionReadError(MonitorDefinitionPersistenceError):
    pass


class MonitorDefinitionMissingFileError(MonitorDefinitionReadError):
    pass


class MonitorDefinitionInvalidJsonError(MonitorDefinitionReadError):
    pass


class MonitorDefinitionNonObjectPayloadError(MonitorDefinitionReadError):
    pass


class MonitorDefinitionSchemaValidationError(MonitorDefinitionReadError):
    pass


class MonitorDefinitionIntegrityValidationError(MonitorDefinitionReadError):
    pass


class MonitorDefinitionDiscoveryMetadataValidationError(MonitorDefinitionReadError):
    pass


CANONICAL_MONITOR_DEFINITION_OBSERVATION_STATUSES = ["ok", "threshold_breach", "degraded", "unavailable"]
CANONICAL_MONITOR_DEFINITION_REQUIRED_PORTFOLIO_STATEMENT_FIELDS = [
    "importer",
    "imported_at",
    "source_path",
    "statement_period",
]
CANONICAL_MONITOR_DEFINITION_REQUIRED_BENCHMARK_OBSERVATION_FIELDS = [
    "overlay_id",
    "benchmark_symbol",
    "as_of_month_end",
    "signal_basis",
    "confirmation_count",
    "rule_version",
    "source_lineage.source_id",
    "source_lineage.observed_at",
]
CANONICAL_MONITOR_DEFINITION_SOURCE_LINEAGE_REQUIREMENTS = {
    "benchmark_source_kind": "benchmark_overlay_signal",
    "portfolio_truth_basis": "imported_portfolio_snapshot",
    "required_portfolio_statement_fields": CANONICAL_MONITOR_DEFINITION_REQUIRED_PORTFOLIO_STATEMENT_FIELDS,
    "required_benchmark_observation_fields": CANONICAL_MONITOR_DEFINITION_REQUIRED_BENCHMARK_OBSERVATION_FIELDS,
}
MONITOR_DEFINITION_ALLOWED_LEGACY_MISSING_FIELDS = frozenset({"observation_statuses", "source_lineage_requirements"})
MONITOR_DEFINITION_REQUIRED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "monitor_definition_id",
        "fingerprint",
        "monitor_id",
        "benchmark_symbol",
        "review_scope",
        "evaluation_mode",
        "thresholds",
    }
)
MONITOR_DEFINITION_THRESHOLD_FIELDS = frozenset(
    {
        "minimum_confirmation_count",
        "risk_on_min_risky_weight",
        "risk_on_max_cash_weight",
        "risk_reduced_max_risky_weight",
        "risk_reduced_min_cash_weight",
    }
)
MONITOR_DEFINITION_SOURCE_LINEAGE_REQUIREMENT_FIELDS = frozenset(
    {
        "benchmark_source_kind",
        "portfolio_truth_basis",
        "required_portfolio_statement_fields",
        "required_benchmark_observation_fields",
    }
)
MONITOR_DEFINITION_LATEST_EVALUATION_SNAPSHOT_REQUIRED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "monitor_definition_id",
        "monitor_id",
        "benchmark_symbol",
        "evaluated_at",
        "outcome_status",
        "significance_status",
        "benchmark_observation_lineage",
        "portfolio_truth_basis",
    }
)
MONITOR_DEFINITION_LATEST_EVALUATION_SNAPSHOT_BENCHMARK_OBSERVATION_LINEAGE_FIELDS = frozenset(
    {"source_kind", "source_id", "observed_at"}
)
MONITOR_DEFINITION_LATEST_EVALUATION_SNAPSHOT_PORTFOLIO_TRUTH_BASIS_FIELDS = frozenset(
    {"truth_basis", "importer", "imported_at", "source_path", "statement_period"}
)
MONITOR_DEFINITION_EVALUATION_HISTORY_ENTRY_REQUIRED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "history_entry_id",
        "monitor_definition_id",
        "monitor_definition_fingerprint",
        "monitor_definition_schema_version",
        "monitor_id",
        "benchmark_symbol",
        "evaluation_mode",
        "evaluated_at",
        "observation_status",
        "significance_status",
        "thresholds",
        "benchmark_observation",
        "portfolio_observation",
        "active_observation",
    }
)
LATEST_EVALUATION_RECENCY_WINDOW = timedelta(days=31)


def _validated_history_entry_id_key(history_entry_id: str) -> str:
    if not history_entry_id.startswith("monitor_definition_history_"):
        raise MonitorDefinitionIntegrityValidationError(
            "history_entry_id must use the stable monitor_definition_history_ prefix"
        )
    if any(separator in history_entry_id for separator in ("/", "\\")):
        raise MonitorDefinitionIntegrityValidationError("history_entry_id must be a stable storage key")
    return history_entry_id


def _validate_raw_persisted_monitor_definition_evaluation_history_entry_payload(
    payload: dict[str, Any],
) -> None:
    missing_fields = sorted(
        field_name
        for field_name in MONITOR_DEFINITION_EVALUATION_HISTORY_ENTRY_REQUIRED_TOP_LEVEL_FIELDS
        if field_name not in payload
    )
    if missing_fields:
        raise MonitorDefinitionSchemaValidationError(
            "persisted monitor definition evaluation history entry payload is missing required field(s): "
            + ", ".join(missing_fields)
        )
    expected_history_entry_id = _canonical_monitor_definition_history_entry_id_from_payload(
        _canonical_validation_payload_from_persisted_evaluation_history_payload(payload)
    )
    if payload.get("history_entry_id") != expected_history_entry_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition evaluation history entry history_entry_id does not match canonical persisted payload content"
        )


def _validate_loaded_monitor_definition_evaluation_history_entry(
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
    *,
    expected_monitor_definition_id: str | None = None,
    expected_monitor_definition_fingerprint: str | None = None,
    expected_monitor_definition_schema_version: str | None = None,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
) -> MonitorDefinitionEvaluationHistoryEntryArtifact:
    if entry.schema_version != "monitor_definition_evaluation_history_entry_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition evaluation history entry schema_version"
        )
    _validated_history_entry_id_key(entry.history_entry_id)
    expected_history_entry_id = _canonical_monitor_definition_history_entry_id_from_payload(
        _canonical_validation_payload_from_evaluation_history_entry(entry)
    )
    if entry.history_entry_id != expected_history_entry_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition evaluation history entry history_entry_id does not match canonical entry content"
        )
    if not entry.monitor_definition_id.startswith("monitor_definition_") or any(
        separator in entry.monitor_definition_id for separator in ("/", "\\")
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "monitor_definition_id must use the stable monitor_definition_ prefix"
        )
    if expected_monitor_definition_id is not None and entry.monitor_definition_id != expected_monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition evaluation history entry monitor_definition_id does not match requested definition"
        )
    if entry.monitor_definition_schema_version != "monitor_definition_artifact_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition evaluation history entry monitor_definition_schema_version"
        )
    if (
        expected_monitor_definition_schema_version is not None
        and entry.monitor_definition_schema_version != expected_monitor_definition_schema_version
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition evaluation history entry schema version does not match persisted monitor definition"
        )
    if expected_monitor_definition_fingerprint is not None and entry.monitor_definition_fingerprint != expected_monitor_definition_fingerprint:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition evaluation history entry fingerprint does not match persisted monitor definition"
        )
    if entry.monitor_id != "benchmark_trend_overlay_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition evaluation history entry monitor_id"
        )
    if expected_monitor_id is not None and entry.monitor_id != expected_monitor_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition evaluation history entry monitor_id does not match persisted monitor definition"
        )
    if entry.benchmark_symbol != _validated_benchmark_symbol(entry.benchmark_symbol):
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition evaluation history entry benchmark_symbol must be canonical"
        )
    if expected_benchmark_symbol is not None and entry.benchmark_symbol != expected_benchmark_symbol:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition evaluation history entry benchmark_symbol does not match persisted monitor definition"
        )
    if entry.evaluation_mode != "review_only_observation_evaluation":
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition evaluation history entry evaluation_mode is unsupported"
        )
    if entry.benchmark_observation.overlay_id != entry.monitor_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition evaluation history entry benchmark observation overlay_id must match entry monitor_id"
        )
    if entry.benchmark_observation.benchmark_symbol != entry.benchmark_symbol:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition evaluation history entry benchmark observation benchmark_symbol must match entry benchmark_symbol"
        )
    return entry


def validate_monitor_definition_evaluation_history_entry(
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
    *,
    expected_monitor_definition_id: str | None = None,
    expected_monitor_definition_fingerprint: str | None = None,
    expected_monitor_definition_schema_version: str | None = None,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
) -> MonitorDefinitionEvaluationHistoryEntryArtifact:
    return _validate_loaded_monitor_definition_evaluation_history_entry(
        entry,
        expected_monitor_definition_id=expected_monitor_definition_id,
        expected_monitor_definition_fingerprint=expected_monitor_definition_fingerprint,
        expected_monitor_definition_schema_version=expected_monitor_definition_schema_version,
        expected_monitor_id=expected_monitor_id,
        expected_benchmark_symbol=expected_benchmark_symbol,
    )


def build_stable_monitor_definition_evaluation_history_entry(
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
) -> MonitorDefinitionEvaluationHistoryEntryArtifact:
    return entry.model_copy(
        update={
            "history_entry_id": _canonical_monitor_definition_history_entry_id_from_payload(
                _canonical_validation_payload_from_evaluation_history_entry(entry)
            )
        }
    )


@dataclass(frozen=True)
class PersistedMonitorDefinitionLatestEvaluationSnapshot:
    artifact: MonitorDefinitionLatestEvaluationSnapshotArtifact
    evaluated_at: datetime
    outcome_status: MonitorDefinitionObservationStatus
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus


@dataclass(frozen=True)
class PersistedMonitorDefinitionDiscoveryStatus:
    latest_evaluation_snapshot_status: MonitorDefinitionLatestEvaluationSnapshotStatus
    latest_evaluation_snapshot: PersistedMonitorDefinitionLatestEvaluationSnapshot | None


@dataclass(frozen=True)
class RawPersistedMonitorDefinitionArtifact:
    artifact_path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class PersistedMonitorDefinitionArtifact:
    artifact_path: Path
    artifact: MonitorDefinitionArtifact
    artifact_last_modified_at: datetime
    discovery_status: PersistedMonitorDefinitionDiscoveryStatus


@dataclass(frozen=True)
class RawPersistedMonitorDefinitionEvaluationHistoryEntry:
    entry_path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class PersistedMonitorDefinitionEvaluationHistoryEntry:
    entry_path: Path
    artifact: MonitorDefinitionEvaluationHistoryEntryArtifact


class MonitorDefinitionArtifactStore:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.monitor_definition_artifact_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def artifact_path(self, monitor_definition_id: str) -> Path:
        return self.base_dir / f"{_validated_monitor_definition_id_key(monitor_definition_id)}.json"

    def persist(self, artifact: MonitorDefinitionArtifact) -> MonitorDefinitionArtifact:
        validated_artifact = validate_monitor_definition_artifact(artifact)
        self._write_once(
            self.artifact_path(validated_artifact.monitor_definition_id),
            validated_artifact.model_dump(mode="json"),
        )
        return validated_artifact

    def load(self, monitor_definition_id: str) -> MonitorDefinitionArtifact:
        raw = self.load_raw(monitor_definition_id)
        _validate_raw_persisted_monitor_definition_payload(raw.payload)
        try:
            artifact = MonitorDefinitionArtifact.model_validate(_hydrate_legacy_monitor_definition_payload(raw.payload))
        except ValidationError as exc:
            raise MonitorDefinitionSchemaValidationError(
                f"persisted monitor definition failed schema validation: {raw.artifact_path}"
            ) from exc
        return _validate_loaded_monitor_definition_artifact(artifact, persisted_payload=raw.payload)

    def load_raw(self, monitor_definition_id: str) -> RawPersistedMonitorDefinitionArtifact:
        path = self.artifact_path(monitor_definition_id)
        return RawPersistedMonitorDefinitionArtifact(artifact_path=path, payload=_read_json_object(path))

    def list(self) -> list[MonitorDefinitionArtifactListItem]:
        items: list[tuple[float, MonitorDefinitionArtifactListItem]] = []
        for path in self.base_dir.glob("monitor_definition_*.json"):
            if path.name.endswith(".latest_evaluation.json"):
                continue
            artifact = self.load(path.stem)
            items.append(
                (
                    path.stat().st_mtime,
                    MonitorDefinitionArtifactListItem(
                        monitor_definition_id=artifact.monitor_definition_id,
                        monitor_id=artifact.monitor_id,
                        benchmark_symbol=artifact.benchmark_symbol,
                        schema_version=artifact.schema_version,
                        fingerprint=artifact.fingerprint,
                    ),
                )
            )
        items.sort(key=lambda item: (-item[0], item[1].monitor_definition_id))
        return [item for _, item in items]

    def latest_evaluation_snapshot_path(self, monitor_definition_id: str) -> Path:
        return self.base_dir / f"{_validated_monitor_definition_id_key(monitor_definition_id)}.latest_evaluation.json"

    def evaluation_history_dir(self, monitor_definition_id: str) -> Path:
        return self.base_dir / f"{_validated_monitor_definition_id_key(monitor_definition_id)}.history"

    def evaluation_history_entry_path(self, monitor_definition_id: str, history_entry_id: str) -> Path:
        return self.evaluation_history_dir(monitor_definition_id) / f"{_validated_history_entry_id_key(history_entry_id)}.json"

    def persist_latest_evaluation_snapshot(
        self,
        snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    ) -> MonitorDefinitionLatestEvaluationSnapshotArtifact:
        validated_snapshot = validate_monitor_definition_latest_evaluation_snapshot(snapshot)
        definition_artifact = self.load(validated_snapshot.monitor_definition_id)
        validated_snapshot = validate_monitor_definition_latest_evaluation_snapshot(
            validated_snapshot,
            expected_monitor_definition_id=definition_artifact.monitor_definition_id,
            expected_monitor_id=definition_artifact.monitor_id,
            expected_benchmark_symbol=definition_artifact.benchmark_symbol,
        )
        path = self.latest_evaluation_snapshot_path(validated_snapshot.monitor_definition_id)
        if path.exists():
            existing = self.load_latest_evaluation_snapshot(
                validated_snapshot.monitor_definition_id,
                expected_monitor_id=validated_snapshot.monitor_id,
                expected_benchmark_symbol=validated_snapshot.benchmark_symbol,
            )
            if existing.monitor_definition_id != validated_snapshot.monitor_definition_id:
                raise MonitorDefinitionPersistenceError(
                    f"persisted latest evaluation snapshot identity mismatch at {path}"
                )
        self._atomic_write_json(path, validated_snapshot.model_dump(mode="json"))
        return validated_snapshot

    def append_evaluation_history_entry(
        self,
        entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
    ) -> MonitorDefinitionEvaluationHistoryEntryArtifact:
        definition_artifact = self.load(entry.monitor_definition_id)
        validated_entry = validate_monitor_definition_evaluation_history_entry(
            entry,
            expected_monitor_definition_id=definition_artifact.monitor_definition_id,
            expected_monitor_definition_fingerprint=definition_artifact.fingerprint,
            expected_monitor_definition_schema_version=definition_artifact.schema_version,
            expected_monitor_id=definition_artifact.monitor_id,
            expected_benchmark_symbol=definition_artifact.benchmark_symbol,
        )
        history_dir = self.evaluation_history_dir(validated_entry.monitor_definition_id)
        history_dir.mkdir(parents=True, exist_ok=True)
        self._write_once(
            self.evaluation_history_entry_path(
                validated_entry.monitor_definition_id,
                validated_entry.history_entry_id,
            ),
            validated_entry.model_dump(mode="json"),
        )
        return validated_entry

    def persist_evaluation_artifacts(
        self,
        snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
        entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
    ) -> tuple[
        MonitorDefinitionLatestEvaluationSnapshotArtifact,
        MonitorDefinitionEvaluationHistoryEntryArtifact,
    ]:
        definition_artifact = self.load(snapshot.monitor_definition_id)
        validated_snapshot = validate_monitor_definition_latest_evaluation_snapshot(
            snapshot,
            expected_monitor_definition_id=definition_artifact.monitor_definition_id,
            expected_monitor_id=definition_artifact.monitor_id,
            expected_benchmark_symbol=definition_artifact.benchmark_symbol,
        )
        validated_entry = validate_monitor_definition_evaluation_history_entry(
            entry,
            expected_monitor_definition_id=definition_artifact.monitor_definition_id,
            expected_monitor_definition_fingerprint=definition_artifact.fingerprint,
            expected_monitor_definition_schema_version=definition_artifact.schema_version,
            expected_monitor_id=definition_artifact.monitor_id,
            expected_benchmark_symbol=definition_artifact.benchmark_symbol,
        )
        _validate_monitor_definition_evaluation_persistence_pair(
            validated_snapshot,
            validated_entry,
        )

        snapshot_path = self.latest_evaluation_snapshot_path(validated_snapshot.monitor_definition_id)
        previous_snapshot_serialized = (
            snapshot_path.read_text(encoding="utf-8") if snapshot_path.exists() else None
        )
        history_dir = self.evaluation_history_dir(validated_entry.monitor_definition_id)
        history_dir_existed = history_dir.exists()
        history_path = self.evaluation_history_entry_path(
            validated_entry.monitor_definition_id,
            validated_entry.history_entry_id,
        )

        self._atomic_write_json(snapshot_path, validated_snapshot.model_dump(mode="json"))
        try:
            history_dir.mkdir(parents=True, exist_ok=True)
            self._write_once(history_path, validated_entry.model_dump(mode="json"))
        except Exception as exc:
            rollback_errors = self._rollback_evaluation_artifact_persistence(
                snapshot_path=snapshot_path,
                previous_snapshot_serialized=previous_snapshot_serialized,
                history_dir=history_dir,
                history_dir_existed=history_dir_existed,
                history_path=history_path,
            )
            if rollback_errors:
                raise MonitorDefinitionPersistenceError(
                    "monitor definition evaluation persistence failed and rollback left residual state: "
                    + "; ".join(rollback_errors)
                ) from exc
            raise

        return validated_snapshot, validated_entry

    def load_latest_evaluation_snapshot(
        self,
        monitor_definition_id: str,
        *,
        expected_monitor_id: str | None = None,
        expected_benchmark_symbol: str | None = None,
    ) -> MonitorDefinitionLatestEvaluationSnapshotArtifact:
        path = self.latest_evaluation_snapshot_path(monitor_definition_id)
        payload = _read_json_object(path, subject="persisted latest evaluation snapshot")
        _validate_raw_persisted_monitor_definition_latest_evaluation_snapshot_payload(payload)
        try:
            snapshot = MonitorDefinitionLatestEvaluationSnapshotArtifact.model_validate(payload)
        except ValidationError as exc:
            error_locations = {tuple(error.get("loc", ())) for error in exc.errors()}
            if ("outcome_status",) in error_locations:
                raise MonitorDefinitionDiscoveryMetadataValidationError(
                    f"persisted latest evaluation snapshot outcome_status is invalid: {path}"
                ) from exc
            if ("significance_status",) in error_locations:
                raise MonitorDefinitionDiscoveryMetadataValidationError(
                    f"persisted latest evaluation snapshot significance_status is invalid: {path}"
                ) from exc
            if ("evaluated_at",) in error_locations:
                raise MonitorDefinitionDiscoveryMetadataValidationError(
                    f"persisted latest evaluation snapshot evaluated_at is invalid: {path}"
                ) from exc
            raise MonitorDefinitionDiscoveryMetadataValidationError(
                f"persisted latest evaluation snapshot failed schema validation: {path}"
            ) from exc
        return _validate_loaded_monitor_definition_latest_evaluation_snapshot(
            snapshot,
            expected_monitor_definition_id=monitor_definition_id,
            expected_monitor_id=expected_monitor_id,
            expected_benchmark_symbol=expected_benchmark_symbol,
        )

    def load_evaluation_history_entry(
        self,
        monitor_definition_id: str,
        history_entry_id: str,
    ) -> MonitorDefinitionEvaluationHistoryEntryArtifact:
        definition_artifact = self.load(monitor_definition_id)
        raw = self.load_raw_evaluation_history_entry(monitor_definition_id, history_entry_id)
        _validate_raw_persisted_monitor_definition_evaluation_history_entry_payload(raw.payload)
        try:
            entry = MonitorDefinitionEvaluationHistoryEntryArtifact.model_validate(raw.payload)
        except ValidationError as exc:
            raise MonitorDefinitionSchemaValidationError(
                f"persisted monitor definition evaluation history entry failed schema validation: {raw.entry_path}"
            ) from exc
        return _validate_loaded_monitor_definition_evaluation_history_entry(
            entry,
            expected_monitor_definition_id=definition_artifact.monitor_definition_id,
            expected_monitor_definition_fingerprint=definition_artifact.fingerprint,
            expected_monitor_definition_schema_version=definition_artifact.schema_version,
            expected_monitor_id=definition_artifact.monitor_id,
            expected_benchmark_symbol=definition_artifact.benchmark_symbol,
        )

    def load_raw_evaluation_history_entry(
        self,
        monitor_definition_id: str,
        history_entry_id: str,
    ) -> RawPersistedMonitorDefinitionEvaluationHistoryEntry:
        path = self.evaluation_history_entry_path(monitor_definition_id, history_entry_id)
        return RawPersistedMonitorDefinitionEvaluationHistoryEntry(
            entry_path=path,
            payload=_read_json_object(path, subject="persisted monitor definition evaluation history entry"),
        )

    def list_evaluation_history(
        self,
        monitor_definition_id: str,
        *,
        limit: int | None = None,
    ) -> MonitorDefinitionEvaluationHistoryResponse:
        definition_artifact = self.load(monitor_definition_id)
        entries = self._list_persisted_evaluation_history_entries(monitor_definition_id, definition_artifact)
        if limit is not None and limit < 0:
            limit = 0
        returned_entries = entries if limit is None else entries[:limit]
        return MonitorDefinitionEvaluationHistoryResponse(
            items=[MonitorDefinitionEvaluationHistoryRow.model_validate(item.artifact.model_dump(mode="json")) for item in returned_entries],
            metadata=MonitorDefinitionEvaluationHistoryResponseMetadata(
                monitor_definition_id=definition_artifact.monitor_definition_id,
                monitor_definition_fingerprint=definition_artifact.fingerprint,
                returned_limit=limit,
                total_entries=len(entries),
            ),
        )

    def inspect_evaluation_history_entry(
        self,
        monitor_definition_id: str,
        history_entry_id: str,
    ) -> MonitorDefinitionEvaluationHistoryEntryResponse:
        definition_artifact = self.load(monitor_definition_id)
        entries = self._list_persisted_evaluation_history_entries(monitor_definition_id, definition_artifact)
        for entry in entries:
            if entry.artifact.history_entry_id == history_entry_id:
                return MonitorDefinitionEvaluationHistoryEntryResponse(
                    item=MonitorDefinitionEvaluationHistoryRow.model_validate(entry.artifact.model_dump(mode="json")),
                    metadata=MonitorDefinitionEvaluationHistoryEntryResponseMetadata(
                        monitor_definition_id=definition_artifact.monitor_definition_id,
                        monitor_definition_fingerprint=definition_artifact.fingerprint,
                        total_entries=len(entries),
                        retrieved_history_entry_id=history_entry_id,
                    ),
                )
        raise MonitorDefinitionMissingFileError(
            "missing persisted monitor definition evaluation history entry file: "
            f"{self.evaluation_history_entry_path(monitor_definition_id, history_entry_id)}"
        )

    def list_catalog(
        self,
        *,
        filters: MonitorDefinitionDiscoveryFilters | None = None,
    ) -> MonitorDefinitionCatalogResponse:
        normalized_filters = filters or MonitorDefinitionDiscoveryFilters()
        persisted = self._list_persisted_artifacts(filters=normalized_filters)
        return MonitorDefinitionCatalogResponse(
            items=[_catalog_row_from_persisted_artifact(item) for item in persisted],
            metadata=MonitorDefinitionCatalogResponseMetadata(applied_filters=normalized_filters),
        )

    def list_recent(
        self,
        *,
        limit: int = 20,
        filters: MonitorDefinitionDiscoveryFilters | None = None,
    ) -> MonitorDefinitionRecentResponse:
        normalized_filters = filters or MonitorDefinitionDiscoveryFilters()
        if limit < 1:
            return MonitorDefinitionRecentResponse(
                items=[],
                metadata=MonitorDefinitionRecentResponseMetadata(applied_filters=normalized_filters),
            )
        persisted = self._list_persisted_artifacts(filters=normalized_filters)[:limit]
        return MonitorDefinitionRecentResponse(
            items=[_recent_row_from_persisted_artifact(item) for item in persisted],
            metadata=MonitorDefinitionRecentResponseMetadata(applied_filters=normalized_filters),
        )

    def _list_persisted_artifacts(
        self,
        *,
        filters: MonitorDefinitionDiscoveryFilters | None = None,
    ) -> list[PersistedMonitorDefinitionArtifact]:
        normalized_filters = filters or MonitorDefinitionDiscoveryFilters()
        artifacts: list[PersistedMonitorDefinitionArtifact] = []
        for path in self.base_dir.glob("monitor_definition_*.json"):
            if path.name.endswith(".latest_evaluation.json"):
                continue
            artifact = self.load(path.stem)
            persisted = PersistedMonitorDefinitionArtifact(
                artifact_path=path,
                artifact=artifact,
                artifact_last_modified_at=datetime.fromtimestamp(path.stat().st_mtime, tz=UTC),
                discovery_status=self._load_discovery_status(artifact),
            )
            if _matches_discovery_filters(persisted, normalized_filters):
                artifacts.append(persisted)
        artifacts.sort(
            key=lambda item: (
                -item.artifact_last_modified_at.timestamp(),
                item.artifact.monitor_definition_id,
            )
        )
        return artifacts

    def _load_discovery_status(
        self,
        definition_artifact: MonitorDefinitionArtifact,
    ) -> PersistedMonitorDefinitionDiscoveryStatus:
        path = self.latest_evaluation_snapshot_path(definition_artifact.monitor_definition_id)
        if not path.exists():
            return PersistedMonitorDefinitionDiscoveryStatus(
                latest_evaluation_snapshot_status="absent",
                latest_evaluation_snapshot=None,
            )
        snapshot_artifact: MonitorDefinitionLatestEvaluationSnapshotArtifact = self.load_latest_evaluation_snapshot(
            definition_artifact.monitor_definition_id,
            expected_monitor_id=definition_artifact.monitor_id,
            expected_benchmark_symbol=definition_artifact.benchmark_symbol,
        )
        snapshot = PersistedMonitorDefinitionLatestEvaluationSnapshot(
            artifact=snapshot_artifact,
            evaluated_at=snapshot_artifact.evaluated_at,
            outcome_status=snapshot_artifact.outcome_status,
            significance_status=snapshot_artifact.significance_status,
        )
        return PersistedMonitorDefinitionDiscoveryStatus(
            latest_evaluation_snapshot_status="present",
            latest_evaluation_snapshot=snapshot,
        )

    def _list_persisted_evaluation_history_entries(
        self,
        monitor_definition_id: str,
        definition_artifact: MonitorDefinitionArtifact,
    ) -> list[PersistedMonitorDefinitionEvaluationHistoryEntry]:
        history_dir = self.evaluation_history_dir(monitor_definition_id)
        if not history_dir.exists():
            return []
        entries: list[PersistedMonitorDefinitionEvaluationHistoryEntry] = []
        for path in history_dir.glob("*.json"):
            raw = RawPersistedMonitorDefinitionEvaluationHistoryEntry(
                entry_path=path,
                payload=_read_json_object(path, subject="persisted monitor definition evaluation history entry"),
            )
            _validate_raw_persisted_monitor_definition_evaluation_history_entry_payload(raw.payload)
            try:
                entry = MonitorDefinitionEvaluationHistoryEntryArtifact.model_validate(raw.payload)
            except ValidationError as exc:
                raise MonitorDefinitionSchemaValidationError(
                    f"persisted monitor definition evaluation history entry failed schema validation: {path}"
                ) from exc
            entries.append(
                PersistedMonitorDefinitionEvaluationHistoryEntry(
                    entry_path=path,
                    artifact=_validate_loaded_monitor_definition_evaluation_history_entry(
                        entry,
                        expected_monitor_definition_id=definition_artifact.monitor_definition_id,
                        expected_monitor_definition_fingerprint=definition_artifact.fingerprint,
                        expected_monitor_definition_schema_version=definition_artifact.schema_version,
                        expected_monitor_id=definition_artifact.monitor_id,
                        expected_benchmark_symbol=definition_artifact.benchmark_symbol,
                    ),
                )
            )
        entries.sort(
            key=lambda item: (
                -item.artifact.evaluated_at.timestamp(),
                item.artifact.history_entry_id,
            )
        )
        return entries

    def _write_once(self, path: Path, payload: object) -> None:
        serialized = _canonical_json(payload)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise MonitorDefinitionPersistenceError(f"immutable monitor definition conflict at {path}")
            return
        path.write_text(serialized, encoding="utf-8")

    def _atomic_write_json(self, path: Path, payload: object) -> None:
        self._atomic_write_text(path, _canonical_json(payload))

    def _atomic_write_text(self, path: Path, content: str) -> None:
        temp_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
        try:
            temp_path.write_text(content, encoding="utf-8")
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _rollback_evaluation_artifact_persistence(
        self,
        *,
        snapshot_path: Path,
        previous_snapshot_serialized: str | None,
        history_dir: Path,
        history_dir_existed: bool,
        history_path: Path,
    ) -> list[str]:
        rollback_errors: list[str] = []

        try:
            if previous_snapshot_serialized is None:
                if snapshot_path.exists():
                    snapshot_path.unlink()
            else:
                self._atomic_write_text(snapshot_path, previous_snapshot_serialized)
        except OSError as exc:
            rollback_errors.append(f"snapshot rollback failed at {snapshot_path}: {exc}")

        try:
            if history_path.exists():
                history_path.unlink()
            if not history_dir_existed and history_dir.exists() and not any(history_dir.iterdir()):
                history_dir.rmdir()
        except OSError as exc:
            rollback_errors.append(f"history rollback failed at {history_path}: {exc}")

        return rollback_errors


def build_stable_monitor_definition_artifact(request: CreateMonitorDefinitionRequest) -> MonitorDefinitionArtifact:
    normalized_benchmark_symbol = _validated_benchmark_symbol(request.benchmark_symbol)
    artifact = MonitorDefinitionArtifact(
        monitor_definition_id="monitor_definition_pending",
        fingerprint="pending",
        monitor_id=request.monitor_id,
        benchmark_symbol=normalized_benchmark_symbol,
    )
    payload = artifact.model_dump(mode="json", exclude={"monitor_definition_id", "fingerprint"})
    fingerprint = _fingerprint(payload)
    return artifact.model_copy(
        update={
            "fingerprint": fingerprint,
            "monitor_definition_id": f"monitor_definition_{fingerprint[:16]}",
        }
    )


def create_monitor_definition_artifact(
    request: CreateMonitorDefinitionRequest,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionArtifact:
    return (store or MonitorDefinitionArtifactStore()).persist(build_stable_monitor_definition_artifact(request))


def load_monitor_definition_artifact(
    monitor_definition_id: str,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionArtifact:
    return (store or MonitorDefinitionArtifactStore()).load(monitor_definition_id)


def list_monitor_definition_artifacts(
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> list[MonitorDefinitionArtifactListItem]:
    return (store or MonitorDefinitionArtifactStore()).list()


def list_monitor_definition_catalog(
    *,
    filters: MonitorDefinitionDiscoveryFilters | None = None,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionCatalogResponse:
    return (store or MonitorDefinitionArtifactStore()).list_catalog(filters=filters)


def list_recent_monitor_definition_artifacts(
    *,
    limit: int = 20,
    filters: MonitorDefinitionDiscoveryFilters | None = None,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionRecentResponse:
    return (store or MonitorDefinitionArtifactStore()).list_recent(limit=limit, filters=filters)


def persist_monitor_definition_latest_evaluation_snapshot(
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionLatestEvaluationSnapshotArtifact:
    return (store or MonitorDefinitionArtifactStore()).persist_latest_evaluation_snapshot(snapshot)


def load_monitor_definition_latest_evaluation_snapshot(
    monitor_definition_id: str,
    *,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionLatestEvaluationSnapshotArtifact:
    return (store or MonitorDefinitionArtifactStore()).load_latest_evaluation_snapshot(
        monitor_definition_id,
        expected_monitor_id=expected_monitor_id,
        expected_benchmark_symbol=expected_benchmark_symbol,
    )


def append_monitor_definition_evaluation_history_entry(
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionEvaluationHistoryEntryArtifact:
    return (store or MonitorDefinitionArtifactStore()).append_evaluation_history_entry(entry)


def persist_monitor_definition_evaluation_artifacts(
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> tuple[
    MonitorDefinitionLatestEvaluationSnapshotArtifact,
    MonitorDefinitionEvaluationHistoryEntryArtifact,
]:
    return (store or MonitorDefinitionArtifactStore()).persist_evaluation_artifacts(
        snapshot,
        entry,
    )


def load_monitor_definition_evaluation_history_entry(
    monitor_definition_id: str,
    history_entry_id: str,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionEvaluationHistoryEntryArtifact:
    return (store or MonitorDefinitionArtifactStore()).load_evaluation_history_entry(
        monitor_definition_id,
        history_entry_id,
    )


def list_monitor_definition_evaluation_history(
    monitor_definition_id: str,
    *,
    limit: int | None = None,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionEvaluationHistoryResponse:
    return (store or MonitorDefinitionArtifactStore()).list_evaluation_history(
        monitor_definition_id,
        limit=limit,
    )


def inspect_monitor_definition_evaluation_history_entry(
    monitor_definition_id: str,
    history_entry_id: str,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionEvaluationHistoryEntryResponse:
    return (store or MonitorDefinitionArtifactStore()).inspect_evaluation_history_entry(
        monitor_definition_id,
        history_entry_id,
    )


def validate_monitor_definition_artifact(artifact: MonitorDefinitionArtifact) -> MonitorDefinitionArtifact:
    return _validate_loaded_monitor_definition_artifact(artifact)


def validate_monitor_definition_latest_evaluation_snapshot(
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    *,
    expected_monitor_definition_id: str | None = None,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
) -> MonitorDefinitionLatestEvaluationSnapshotArtifact:
    return _validate_loaded_monitor_definition_latest_evaluation_snapshot(
        snapshot,
        expected_monitor_definition_id=expected_monitor_definition_id,
        expected_monitor_id=expected_monitor_id,
        expected_benchmark_symbol=expected_benchmark_symbol,
    )


def _validate_loaded_monitor_definition_artifact(
    artifact: MonitorDefinitionArtifact,
    *,
    persisted_payload: dict[str, Any] | None = None,
) -> MonitorDefinitionArtifact:
    if artifact.schema_version != "monitor_definition_artifact_v1":
        raise MonitorDefinitionIntegrityValidationError("unsupported monitor definition schema_version")
    if artifact.monitor_id != "benchmark_trend_overlay_v1":
        raise MonitorDefinitionIntegrityValidationError("unsupported monitor_id")
    if artifact.monitor_definition_id == "monitor_definition_pending":
        raise MonitorDefinitionIntegrityValidationError("monitor_definition_id must be stable before persistence")
    if not artifact.monitor_definition_id.startswith("monitor_definition_"):
        raise MonitorDefinitionIntegrityValidationError(
            "monitor_definition_id must use the stable monitor_definition_ prefix"
        )
    if artifact.benchmark_symbol != _validated_benchmark_symbol(artifact.benchmark_symbol):
        raise MonitorDefinitionIntegrityValidationError("monitor definition benchmark_symbol must be canonical")
    if artifact.review_scope != "current_portfolio_truth_only":
        raise MonitorDefinitionIntegrityValidationError("monitor definition review_scope is unsupported")
    if artifact.evaluation_mode != "review_only_observation_evaluation":
        raise MonitorDefinitionIntegrityValidationError("monitor definition evaluation_mode is unsupported")
    if artifact.observation_statuses != CANONICAL_MONITOR_DEFINITION_OBSERVATION_STATUSES:
        raise MonitorDefinitionIntegrityValidationError("monitor definition observation_statuses must remain canonical")
    if (
        artifact.source_lineage_requirements.required_portfolio_statement_fields
        != CANONICAL_MONITOR_DEFINITION_REQUIRED_PORTFOLIO_STATEMENT_FIELDS
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition required_portfolio_statement_fields must remain canonical"
        )
    if (
        artifact.source_lineage_requirements.required_benchmark_observation_fields
        != CANONICAL_MONITOR_DEFINITION_REQUIRED_BENCHMARK_OBSERVATION_FIELDS
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition required_benchmark_observation_fields must remain canonical"
        )
    canonical_payload = (
        _canonical_validation_payload_from_artifact(artifact)
        if persisted_payload is None
        else _canonical_validation_payload_from_persisted_payload(persisted_payload)
    )
    expected_monitor_definition_id = _canonical_monitor_definition_id_from_payload(canonical_payload)
    if artifact.monitor_definition_id != expected_monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition_id does not match canonical artifact content"
        )
    expected_fingerprint = _fingerprint(canonical_payload)
    if artifact.fingerprint != expected_fingerprint:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition fingerprint does not match canonical artifact content"
        )
    return artifact


def _validated_monitor_definition_id_key(monitor_definition_id: str) -> str:
    if not monitor_definition_id.startswith("monitor_definition_"):
        raise MonitorDefinitionIntegrityValidationError(
            "monitor_definition_id must use the stable monitor_definition_ prefix"
        )
    if any(separator in monitor_definition_id for separator in ("/", "\\")):
        raise MonitorDefinitionIntegrityValidationError("monitor_definition_id must be a stable storage key")
    return monitor_definition_id


def _validate_loaded_monitor_definition_latest_evaluation_snapshot(
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    *,
    expected_monitor_definition_id: str | None = None,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
) -> MonitorDefinitionLatestEvaluationSnapshotArtifact:
    if snapshot.schema_version != "monitor_definition_latest_evaluation_snapshot_v1":
        raise MonitorDefinitionIntegrityValidationError("unsupported latest evaluation snapshot schema_version")
    if snapshot.monitor_id != "benchmark_trend_overlay_v1":
        raise MonitorDefinitionIntegrityValidationError("unsupported latest evaluation snapshot monitor_id")
    monitor_definition_id = _validated_monitor_definition_id_key(snapshot.monitor_definition_id)
    if expected_monitor_definition_id is not None and monitor_definition_id != expected_monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted latest evaluation snapshot monitor_definition_id does not match requested definition"
        )
    if expected_monitor_id is not None and snapshot.monitor_id != expected_monitor_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted latest evaluation snapshot monitor_id does not match persisted monitor definition"
        )
    if snapshot.benchmark_symbol != _validated_benchmark_symbol(snapshot.benchmark_symbol):
        raise MonitorDefinitionIntegrityValidationError(
            "latest evaluation snapshot benchmark_symbol must be canonical"
        )
    if expected_benchmark_symbol is not None and snapshot.benchmark_symbol != expected_benchmark_symbol:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted latest evaluation snapshot benchmark_symbol does not match persisted monitor definition"
        )
    if snapshot.evaluated_at.tzinfo is None or snapshot.evaluated_at.utcoffset() is None:
        raise MonitorDefinitionIntegrityValidationError(
            "latest evaluation snapshot evaluated_at must be timezone-aware"
        )
    if not snapshot.portfolio_truth_basis.source_path.strip():
        raise MonitorDefinitionIntegrityValidationError(
            "latest evaluation snapshot portfolio_truth_basis.source_path must be non-blank"
        )
    if not snapshot.portfolio_truth_basis.statement_period.strip():
        raise MonitorDefinitionIntegrityValidationError(
            "latest evaluation snapshot portfolio_truth_basis.statement_period must be non-blank"
        )
    if not snapshot.benchmark_observation_lineage.source_id.strip():
        raise MonitorDefinitionIntegrityValidationError(
            "latest evaluation snapshot benchmark_observation_lineage.source_id must be non-blank"
        )
    return snapshot


def _validate_monitor_definition_evaluation_persistence_pair(
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
) -> None:
    if entry.monitor_definition_id != snapshot.monitor_definition_id:
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry monitor_definition_id must match latest evaluation snapshot"
        )
    if entry.monitor_id != snapshot.monitor_id:
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry monitor_id must match latest evaluation snapshot"
        )
    if entry.benchmark_symbol != snapshot.benchmark_symbol:
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry benchmark_symbol must match latest evaluation snapshot"
        )
    if entry.evaluated_at != snapshot.evaluated_at:
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry evaluated_at must match latest evaluation snapshot"
        )
    if entry.observation_status != snapshot.outcome_status:
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry observation_status must match latest evaluation snapshot outcome_status"
        )
    if entry.significance_status != snapshot.significance_status:
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry significance_status must match latest evaluation snapshot"
        )


def _canonical_monitor_definition_id_from_payload(payload: object) -> str:
    return f"monitor_definition_{_fingerprint(payload)[:16]}"


def _canonical_monitor_definition_history_entry_id_from_payload(payload: object) -> str:
    return f"monitor_definition_history_{_fingerprint(payload)[:16]}"


def _canonical_validation_payload_from_artifact(artifact: MonitorDefinitionArtifact) -> dict[str, Any]:
    return artifact.model_dump(mode="json", exclude={"monitor_definition_id", "fingerprint"})


def _canonical_validation_payload_from_persisted_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in {"monitor_definition_id", "fingerprint"}}


def _canonical_validation_payload_from_evaluation_history_entry(
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
) -> dict[str, Any]:
    return entry.model_dump(mode="json", exclude={"history_entry_id"})


def _canonical_validation_payload_from_persisted_evaluation_history_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "history_entry_id"}


def _validate_raw_persisted_monitor_definition_payload(payload: dict[str, Any]) -> None:
    _validate_monitor_definition_required_top_level_fields(payload)
    _validate_monitor_definition_object_field_shape(
        payload,
        field_name="thresholds",
        required_keys=MONITOR_DEFINITION_THRESHOLD_FIELDS,
    )
    if "source_lineage_requirements" in payload:
        _validate_monitor_definition_object_field_shape(
            payload,
            field_name="source_lineage_requirements",
            required_keys=MONITOR_DEFINITION_SOURCE_LINEAGE_REQUIREMENT_FIELDS,
        )
    canonical_payload = _canonical_validation_payload_from_persisted_payload(payload)
    expected_monitor_definition_id = _canonical_monitor_definition_id_from_payload(canonical_payload)
    if payload.get("monitor_definition_id") != expected_monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition_id does not match canonical persisted payload content"
        )
    expected_fingerprint = _fingerprint(canonical_payload)
    if payload.get("fingerprint") != expected_fingerprint:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition fingerprint does not match canonical persisted payload content"
        )


def _validate_monitor_definition_required_top_level_fields(payload: dict[str, Any]) -> None:
    missing_fields = sorted(
        field_name
        for field_name in MONITOR_DEFINITION_REQUIRED_TOP_LEVEL_FIELDS
        if field_name not in payload
    )
    if missing_fields:
        raise MonitorDefinitionSchemaValidationError(
            "persisted monitor definition payload is missing required field(s): " + ", ".join(missing_fields)
        )

    missing_non_legacy_fields = sorted(
        field_name
        for field_name in (set(MonitorDefinitionArtifact.model_fields) - MONITOR_DEFINITION_ALLOWED_LEGACY_MISSING_FIELDS)
        if field_name not in payload
    )
    if missing_non_legacy_fields:
        raise MonitorDefinitionSchemaValidationError(
            "persisted monitor definition payload is missing non-legacy field(s): "
            + ", ".join(missing_non_legacy_fields)
        )


def _validate_monitor_definition_object_field_shape(
    payload: dict[str, Any],
    *,
    field_name: str,
    required_keys: frozenset[str],
    entity_label: str = "monitor definition",
) -> None:
    value = payload.get(field_name)
    if not isinstance(value, dict):
        return
    present_keys = frozenset(value.keys())
    if present_keys != required_keys:
        raise MonitorDefinitionIntegrityValidationError(
            f"{entity_label} {field_name} must be fully specified when present"
        )


def _validate_raw_persisted_monitor_definition_latest_evaluation_snapshot_payload(
    payload: dict[str, Any],
) -> None:
    missing_fields = sorted(
        field_name
        for field_name in MONITOR_DEFINITION_LATEST_EVALUATION_SNAPSHOT_REQUIRED_TOP_LEVEL_FIELDS
        if field_name not in payload
    )
    if missing_fields:
        raise MonitorDefinitionSchemaValidationError(
            "persisted latest evaluation snapshot payload is missing required field(s): "
            + ", ".join(missing_fields)
        )
    _validate_monitor_definition_object_field_shape(
        payload,
        field_name="benchmark_observation_lineage",
        required_keys=MONITOR_DEFINITION_LATEST_EVALUATION_SNAPSHOT_BENCHMARK_OBSERVATION_LINEAGE_FIELDS,
        entity_label="persisted latest evaluation snapshot",
    )
    _validate_monitor_definition_object_field_shape(
        payload,
        field_name="portfolio_truth_basis",
        required_keys=MONITOR_DEFINITION_LATEST_EVALUATION_SNAPSHOT_PORTFOLIO_TRUTH_BASIS_FIELDS,
        entity_label="persisted latest evaluation snapshot",
    )


def _hydrate_legacy_monitor_definition_payload(payload: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(payload)
    if "observation_statuses" not in hydrated:
        hydrated["observation_statuses"] = list(CANONICAL_MONITOR_DEFINITION_OBSERVATION_STATUSES)
    if "source_lineage_requirements" not in hydrated:
        hydrated["source_lineage_requirements"] = {
            "benchmark_source_kind": CANONICAL_MONITOR_DEFINITION_SOURCE_LINEAGE_REQUIREMENTS[
                "benchmark_source_kind"
            ],
            "portfolio_truth_basis": CANONICAL_MONITOR_DEFINITION_SOURCE_LINEAGE_REQUIREMENTS[
                "portfolio_truth_basis"
            ],
            "required_portfolio_statement_fields": list(
                CANONICAL_MONITOR_DEFINITION_REQUIRED_PORTFOLIO_STATEMENT_FIELDS
            ),
            "required_benchmark_observation_fields": list(
                CANONICAL_MONITOR_DEFINITION_REQUIRED_BENCHMARK_OBSERVATION_FIELDS
            ),
        }
    return hydrated


def _fingerprint(payload: object) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _validated_benchmark_symbol(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise MonitorDefinitionIntegrityValidationError("monitor definition benchmark_symbol must be non-blank")
    return normalized


def _read_json_object(path: Path, *, subject: str = "persisted monitor definition") -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MonitorDefinitionMissingFileError(f"missing {subject} file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MonitorDefinitionInvalidJsonError(f"invalid {subject} json: {path}") from exc
    if not isinstance(payload, dict):
        raise MonitorDefinitionNonObjectPayloadError(
            f"{subject} payload must be a json object: {path}"
        )
    return payload


def _catalog_row_from_persisted_artifact(item: PersistedMonitorDefinitionArtifact) -> MonitorDefinitionCatalogRow:
    artifact = item.artifact
    return MonitorDefinitionCatalogRow(
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        schema_version=artifact.schema_version,
        fingerprint=artifact.fingerprint,
        review_scope=artifact.review_scope,
        evaluation_mode=artifact.evaluation_mode,
        observation_statuses=list(artifact.observation_statuses),
        thresholds=artifact.thresholds,
        source_lineage_requirements=artifact.source_lineage_requirements,
        metadata=_catalog_row_metadata_from_persisted_artifact(item),
    )


def _recent_row_from_persisted_artifact(item: PersistedMonitorDefinitionArtifact) -> MonitorDefinitionRecentRow:
    artifact = item.artifact
    return MonitorDefinitionRecentRow(
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        schema_version=artifact.schema_version,
        fingerprint=artifact.fingerprint,
        review_scope=artifact.review_scope,
        evaluation_mode=artifact.evaluation_mode,
        observation_statuses=list(artifact.observation_statuses),
        thresholds=artifact.thresholds,
        source_lineage_requirements=artifact.source_lineage_requirements,
        artifact_last_modified_at=item.artifact_last_modified_at,
        metadata=_recent_row_metadata_from_persisted_artifact(item),
    )


def _catalog_row_metadata_from_persisted_artifact(
    item: PersistedMonitorDefinitionArtifact,
) -> MonitorDefinitionCatalogRowMetadata:
    return MonitorDefinitionCatalogRowMetadata(status=_status_metadata_from_persisted_artifact(item))


def _recent_row_metadata_from_persisted_artifact(
    item: PersistedMonitorDefinitionArtifact,
) -> MonitorDefinitionRecentRowMetadata:
    return MonitorDefinitionRecentRowMetadata(status=_status_metadata_from_persisted_artifact(item))


def _status_metadata_from_persisted_artifact(item: PersistedMonitorDefinitionArtifact) -> MonitorDefinitionStatusMetadata:
    snapshot = item.discovery_status.latest_evaluation_snapshot
    snapshot_summary = None
    if snapshot is not None:
        snapshot_summary = MonitorDefinitionLatestEvaluationSnapshotSummary(
            evaluated_at=snapshot.evaluated_at,
            outcome_status=cast(MonitorDefinitionObservationStatus, snapshot.outcome_status),
            significance_status=cast(MonitorDefinitionLatestEvaluationSignificanceStatus, snapshot.significance_status),
            recency_status=_latest_evaluation_snapshot_recency(snapshot.evaluated_at),
        )
    return MonitorDefinitionStatusMetadata(
        latest_evaluation_snapshot_status=item.discovery_status.latest_evaluation_snapshot_status,
        latest_evaluation_snapshot=snapshot_summary,
    )


def _latest_evaluation_snapshot_recency(
    evaluated_at: datetime,
) -> MonitorDefinitionLatestEvaluationSnapshotRecency:
    return cast(
        MonitorDefinitionLatestEvaluationSnapshotRecency,
        "recent" if datetime.now(UTC) - evaluated_at <= LATEST_EVALUATION_RECENCY_WINDOW else "stale",
    )


def _matches_discovery_filters(
    item: PersistedMonitorDefinitionArtifact,
    filters: MonitorDefinitionDiscoveryFilters,
) -> bool:
    snapshot = item.discovery_status.latest_evaluation_snapshot
    lifecycle = "enabled"
    review_support_status = "review_supported"
    overlay_family = "benchmark_trend"
    if filters.overlay_family is not None and filters.overlay_family != overlay_family:
        return False
    if filters.monitor_id is not None and filters.monitor_id != item.artifact.monitor_id:
        return False
    if filters.review_support_status is not None and filters.review_support_status != review_support_status:
        return False
    if filters.lifecycle_status is not None and filters.lifecycle_status != lifecycle:
        return False
    if (
        filters.latest_evaluation_snapshot_status is not None
        and filters.latest_evaluation_snapshot_status != item.discovery_status.latest_evaluation_snapshot_status
    ):
        return False
    if filters.latest_evaluation_snapshot_recency is not None:
        if snapshot is None:
            return False
        if filters.latest_evaluation_snapshot_recency != _latest_evaluation_snapshot_recency(snapshot.evaluated_at):
            return False
    return True
