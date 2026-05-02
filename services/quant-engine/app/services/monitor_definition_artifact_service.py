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
    MonitorDefinitionAlertEpisode,
    MonitorDefinitionAlertEpisodeRecordArtifact,
    MonitorDefinitionAlertEpisodeHistoryResponse,
    MonitorDefinitionAlertEpisodeHistoryResponseMetadata,
    MonitorDefinitionAlertEpisodeHistoryRow,
    MonitorDefinitionAlertEpisodeHistoryTimelineHandoff,
    MonitorDefinitionAlertEpisodeLatestContributingObservation,
    MonitorDefinitionAlertEpisodeRecoveryBasis,
    MonitorDefinitionActiveAlertEpisodeInboxResponse,
    MonitorDefinitionActiveAlertEpisodeInboxResponseMetadata,
    MonitorDefinitionActiveAlertEpisodeInboxRow,
    CreateMonitorDefinitionRequest,
    MonitorDefinitionAlertReviewTimelineOpenHandoff,
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
    MonitorDefinitionCanonicalCauseCode,
    MonitorDefinitionHysteresisTransition,
    MonitorDefinitionLatestEvaluationSnapshotArtifact,
    MonitorDefinitionLatestEvaluationSnapshotSummary,
    MonitorDefinitionLatestEvaluationSnapshotStatus,
    MonitorDefinitionLatestEvaluationSignificanceStatus,
    MonitorDefinitionLatestEvaluationSnapshotRecency,
    MonitorDefinitionLatestObservationAlertInboxResponse,
    MonitorDefinitionLatestObservationAlertInboxResponseMetadata,
    MonitorDefinitionLatestObservationAlertInboxRow,
    MonitorDefinitionAlertHistoryQueueResponse,
    MonitorDefinitionAlertHistoryQueueResponseMetadata,
    MonitorDefinitionAlertHistoryQueueRow,
    MonitorDefinitionRecoveredAlertReviewQueueRecoveredFrom,
    MonitorDefinitionRecoveredAlertReviewQueueResponse,
    MonitorDefinitionRecoveredAlertReviewQueueResponseMetadata,
    MonitorDefinitionRecoveredAlertReviewQueueRow,
    MonitorDefinitionAlertReviewTimelineHistoryRow,
    MonitorDefinitionAlertReviewTimelineObservationRow,
    MonitorDefinitionAlertReviewTimelineResponse,
    MonitorDefinitionAlertReviewTimelineResponseMetadata,
    MonitorDefinitionEvaluationHistoryReviewHandoff,
    MonitorDefinitionObservationOpenHandoff,
    MonitorDefinitionLatestObservationRecency,
    MonitorDefinitionLatestObservationStatus,
    MonitorDefinitionLatestObservationSummary,
    MonitorDefinitionObservationArtifact,
    MonitorDefinitionObservationStatus,
    MonitorDefinitionMonitoringSourcePrecedence,
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
MONITOR_DEFINITION_OBSERVATION_REQUIRED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "observation_id",
        "monitor_definition_id",
        "monitor_definition_fingerprint",
        "monitor_definition_schema_version",
        "monitor_id",
        "benchmark_symbol",
        "evaluation_mode",
        "evaluated_at",
        "observation_status",
        "cause_code",
        "alert_classification",
        "thresholds",
        "benchmark_observation",
        "portfolio_observation",
        "active_observation",
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
        "cause_code",
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
        "cause_code",
        "significance_status",
        "thresholds",
        "benchmark_observation",
        "portfolio_observation",
        "active_observation",
    }
)
MONITOR_DEFINITION_ALERT_EPISODE_RECORD_REQUIRED_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "episode_id",
        "monitor_definition_id",
        "monitor_definition_fingerprint",
        "monitor_definition_schema_version",
        "monitor_id",
        "benchmark_symbol",
        "lifecycle_status",
        "latest_for_monitor_definition",
        "started_at",
        "latest_event_at",
        "latest_contributing_observation",
        "recovery_basis",
        "terminal_history_entry_id",
        "timeline_handoff",
    }
)
LATEST_EVALUATION_RECENCY_WINDOW = timedelta(days=31)
DISCOVERY_STATUS_SOURCE_PRECEDENCE: MonitorDefinitionMonitoringSourcePrecedence = (
    "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot"
)
LATEST_OBSERVATION_SOURCE_PRECEDENCE: MonitorDefinitionMonitoringSourcePrecedence = (
    "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry"
)
LATEST_SNAPSHOT_SOURCE_PRECEDENCE: MonitorDefinitionMonitoringSourcePrecedence = (
    "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact"
)
EVALUATION_HISTORY_SOURCE_PRECEDENCE: MonitorDefinitionMonitoringSourcePrecedence = (
    "persisted_evaluation_history_entry_only"
)
ALERT_HISTORY_QUEUE_SOURCE_PRECEDENCE: MonitorDefinitionMonitoringSourcePrecedence = (
    "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries"
)
RECOVERED_ALERT_QUEUE_SOURCE_PRECEDENCE: MonitorDefinitionMonitoringSourcePrecedence = (
    "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries"
)
ALERT_EPISODE_SOURCE_PRECEDENCE: MonitorDefinitionMonitoringSourcePrecedence = (
    "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
)
TIMELINE_SOURCE_PRECEDENCE: MonitorDefinitionMonitoringSourcePrecedence = (
    "persisted_observation_artifact_then_persisted_evaluation_history_entries_then_persisted_latest_alert_episode_projection"
)


def _derive_hysteresis_transition(
    *,
    current_significance_status: str,
    previous_significance_status: str | None,
) -> str:
    current_alert_eligible = current_significance_status != "informational"
    previous_alert_eligible = previous_significance_status != "informational" if previous_significance_status is not None else False
    if current_alert_eligible:
        return "remain_open" if previous_alert_eligible else "open"
    return "recover" if previous_alert_eligible else "no_op"


def _resolved_hysteresis_transition(
    *,
    current_significance_status: str,
    current_hysteresis_transition: str | None,
    previous_significance_status: str | None,
    source_label: str,
 ) -> str:
    derived_transition = _derive_hysteresis_transition(
        current_significance_status=current_significance_status,
        previous_significance_status=previous_significance_status,
    )
    if (
        current_hysteresis_transition is not None
        and current_hysteresis_transition != derived_transition
    ):
        raise MonitorDefinitionIntegrityValidationError(
            f"{source_label} hysteresis_transition does not match canonical persisted evaluation lineage"
        )
    return derived_transition


def _validate_matching_hysteresis_transition(
    *,
    current_hysteresis_transition: str | None,
    expected_hysteresis_transition: str,
    source_label: str,
) -> None:
    if current_hysteresis_transition is None:
        return
    if current_hysteresis_transition != expected_hysteresis_transition:
        raise MonitorDefinitionIntegrityValidationError(
            f"{source_label} hysteresis_transition does not match canonical persisted evaluation lineage"
        )


def _resolved_latest_persisted_hysteresis_transition(
    *,
    observation: MonitorDefinitionObservationArtifact | None,
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact | None,
    history_entries: list["PersistedMonitorDefinitionEvaluationHistoryEntry"],
) -> str | None:
    if history_entries:
        latest_entry = history_entries[0].artifact
        previous_significance_status = (
            history_entries[1].artifact.significance_status if len(history_entries) > 1 else None
        )
        resolved_transition = _resolved_hysteresis_transition(
            current_significance_status=latest_entry.significance_status,
            current_hysteresis_transition=latest_entry.hysteresis_transition,
            previous_significance_status=previous_significance_status,
            source_label="persisted latest evaluation history entry",
        )
        if observation is not None:
            _validate_matching_hysteresis_transition(
                current_hysteresis_transition=observation.hysteresis_transition,
                expected_hysteresis_transition=resolved_transition,
                source_label="persisted latest observation",
            )
        if snapshot is not None:
            _validate_matching_hysteresis_transition(
                current_hysteresis_transition=snapshot.hysteresis_transition,
                expected_hysteresis_transition=resolved_transition,
                source_label="persisted latest evaluation snapshot",
            )
        return cast(MonitorDefinitionHysteresisTransition, resolved_transition)
    if observation is not None:
        resolved_transition = _resolved_hysteresis_transition(
            current_significance_status=observation.alert_classification,
            current_hysteresis_transition=observation.hysteresis_transition,
            previous_significance_status=None,
            source_label="persisted latest observation",
        )
        if snapshot is not None:
            _validate_matching_hysteresis_transition(
                current_hysteresis_transition=snapshot.hysteresis_transition,
                expected_hysteresis_transition=resolved_transition,
                source_label="persisted latest evaluation snapshot",
            )
        return cast(MonitorDefinitionHysteresisTransition, resolved_transition)
    if snapshot is not None:
        return cast(
            MonitorDefinitionHysteresisTransition,
            _resolved_hysteresis_transition(
            current_significance_status=snapshot.significance_status,
            current_hysteresis_transition=snapshot.hysteresis_transition,
            previous_significance_status=None,
            source_label="persisted latest evaluation snapshot",
            ),
        )
    return None


def _resolved_history_entry_hysteresis_transition(
    *,
    history_entries: list["PersistedMonitorDefinitionEvaluationHistoryEntry"],
    index: int,
) -> MonitorDefinitionHysteresisTransition:
    entry = history_entries[index].artifact
    if entry.hysteresis_transition is None:
        return cast(
            MonitorDefinitionHysteresisTransition,
            _derive_hysteresis_transition(
                current_significance_status=entry.significance_status,
                previous_significance_status=(
                    history_entries[index + 1].artifact.significance_status
                    if index + 1 < len(history_entries)
                    else None
                ),
            ),
        )
    previous_significance_status = (
        history_entries[index + 1].artifact.significance_status
        if index + 1 < len(history_entries)
        else None
    )
    return cast(
        MonitorDefinitionHysteresisTransition,
        _resolved_hysteresis_transition(
            current_significance_status=entry.significance_status,
            current_hysteresis_transition=entry.hysteresis_transition,
            previous_significance_status=previous_significance_status,
            source_label=(
                "persisted latest evaluation history entry"
                if index == 0
                else "persisted evaluation history entry"
            ),
        ),
    )


def _history_entry_hysteresis_transition_for_row(
    *,
    history_entries: list["PersistedMonitorDefinitionEvaluationHistoryEntry"],
    index: int,
) -> MonitorDefinitionHysteresisTransition | None:
    entry = history_entries[index].artifact
    if entry.hysteresis_transition is None:
        return None
    return _resolved_history_entry_hysteresis_transition(
        history_entries=history_entries,
        index=index,
    )


def _validated_history_entry_id_key(history_entry_id: str) -> str:
    if not history_entry_id.startswith("monitor_definition_history_"):
        raise MonitorDefinitionIntegrityValidationError(
            "history_entry_id must use the stable monitor_definition_history_ prefix"
        )
    if any(separator in history_entry_id for separator in ("/", "\\")):
        raise MonitorDefinitionIntegrityValidationError("history_entry_id must be a stable storage key")
    return history_entry_id


def _validated_observation_id_key(observation_id: str) -> str:
    if not observation_id.startswith("monitor_definition_observation_"):
        raise MonitorDefinitionIntegrityValidationError(
            "observation_id must use the stable monitor_definition_observation_ prefix"
        )
    if any(separator in observation_id for separator in ("/", "\\")):
        raise MonitorDefinitionIntegrityValidationError("observation_id must be a stable storage key")
    return observation_id


def _validated_episode_id_key(episode_id: str) -> str:
    if not episode_id.startswith("monitor_definition_alert_episode_"):
        raise MonitorDefinitionIntegrityValidationError(
            "episode_id must use the stable monitor_definition_alert_episode_ prefix"
        )
    if any(separator in episode_id for separator in ("/", "\\")):
        raise MonitorDefinitionIntegrityValidationError("episode_id must be a stable storage key")
    return episode_id


def _validate_raw_persisted_monitor_definition_observation_payload(payload: dict[str, Any]) -> None:
    missing_fields = sorted(
        field_name
        for field_name in MONITOR_DEFINITION_OBSERVATION_REQUIRED_TOP_LEVEL_FIELDS
        if field_name not in payload
    )
    if missing_fields:
        raise MonitorDefinitionSchemaValidationError(
            "persisted monitor definition observation payload is missing required field(s): "
            + ", ".join(missing_fields)
        )
    expected_observation_id = _canonical_monitor_definition_observation_id_from_payload(
        _canonical_validation_payload_from_persisted_observation_payload(payload)
    )
    if payload.get("observation_id") != expected_observation_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition observation observation_id does not match canonical persisted payload content"
        )


def _validate_loaded_monitor_definition_observation(
    observation: MonitorDefinitionObservationArtifact,
    *,
    expected_monitor_definition_id: str | None = None,
    expected_monitor_definition_fingerprint: str | None = None,
    expected_monitor_definition_schema_version: str | None = None,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
) -> MonitorDefinitionObservationArtifact:
    if observation.schema_version != "monitor_definition_observation_artifact_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition observation schema_version"
        )
    _validated_observation_id_key(observation.observation_id)
    expected_observation_id = _canonical_monitor_definition_observation_id_from_payload(
        _canonical_validation_payload_from_observation(observation)
    )
    if observation.observation_id != expected_observation_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition observation observation_id does not match canonical entry content"
        )
    monitor_definition_id = _validated_monitor_definition_id_key(observation.monitor_definition_id)
    if expected_monitor_definition_id is not None and monitor_definition_id != expected_monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation monitor_definition_id does not match persisted monitor definition"
        )
    if observation.monitor_definition_schema_version != "monitor_definition_artifact_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition observation monitor_definition_schema_version"
        )
    if (
        expected_monitor_definition_schema_version is not None
        and observation.monitor_definition_schema_version != expected_monitor_definition_schema_version
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation schema version does not match persisted monitor definition"
        )
    if (
        expected_monitor_definition_fingerprint is not None
        and observation.monitor_definition_fingerprint != expected_monitor_definition_fingerprint
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation fingerprint does not match persisted monitor definition"
        )
    if observation.monitor_id != "benchmark_trend_overlay_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition observation monitor_id"
        )
    if expected_monitor_id is not None and observation.monitor_id != expected_monitor_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation monitor_id does not match persisted monitor definition"
        )
    if observation.benchmark_symbol != _validated_benchmark_symbol(observation.benchmark_symbol):
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition observation benchmark_symbol must be canonical"
        )
    if expected_benchmark_symbol is not None and observation.benchmark_symbol != expected_benchmark_symbol:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation benchmark_symbol does not match persisted monitor definition"
        )
    if observation.evaluation_mode != "review_only_observation_evaluation":
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition observation evaluation_mode is unsupported"
        )
    if observation.benchmark_observation.overlay_id != observation.monitor_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition observation benchmark observation overlay_id must match observation monitor_id"
        )
    if observation.benchmark_observation.benchmark_symbol != observation.benchmark_symbol:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition observation benchmark observation benchmark_symbol must match observation benchmark_symbol"
        )
    return observation


def validate_monitor_definition_observation(
    observation: MonitorDefinitionObservationArtifact,
    *,
    expected_monitor_definition_id: str | None = None,
    expected_monitor_definition_fingerprint: str | None = None,
    expected_monitor_definition_schema_version: str | None = None,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
) -> MonitorDefinitionObservationArtifact:
    return _validate_loaded_monitor_definition_observation(
        observation,
        expected_monitor_definition_id=expected_monitor_definition_id,
        expected_monitor_definition_fingerprint=expected_monitor_definition_fingerprint,
        expected_monitor_definition_schema_version=expected_monitor_definition_schema_version,
        expected_monitor_id=expected_monitor_id,
        expected_benchmark_symbol=expected_benchmark_symbol,
    )


def build_stable_monitor_definition_observation(
    observation: MonitorDefinitionObservationArtifact,
) -> MonitorDefinitionObservationArtifact:
    return observation.model_copy(
        update={
            "observation_id": _canonical_monitor_definition_observation_id_from_payload(
                _canonical_validation_payload_from_observation(observation)
            )
        }
    )


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


def _canonical_validation_payload_from_alert_episode_record(
    record: MonitorDefinitionAlertEpisodeRecordArtifact,
) -> dict[str, Any]:
    return {
        "monitor_definition_id": record.monitor_definition_id,
        "started_at": record.started_at.isoformat(),
        "recovered_from_history_entry_id": (
            None if record.recovery_basis is None else record.recovery_basis.recovered_from_history_entry_id
        ),
    }


def _canonical_validation_payload_from_persisted_alert_episode_record_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    recovery_basis = payload.get("recovery_basis")
    recovered_from_history_entry_id = None
    if isinstance(recovery_basis, dict):
        recovered_from_history_entry_id = recovery_basis.get(
            "recovered_from_history_entry_id"
        )
    started_at = payload.get("started_at")
    if isinstance(started_at, str):
        try:
            started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00")).isoformat()
        except ValueError:
            pass
    return {
        "monitor_definition_id": payload.get("monitor_definition_id"),
        "started_at": started_at,
        "recovered_from_history_entry_id": recovered_from_history_entry_id,
    }


def _canonical_monitor_definition_alert_episode_id_from_payload(payload: object) -> str:
    return f"monitor_definition_alert_episode_{_fingerprint(payload)[:16]}"


def _validate_raw_persisted_monitor_definition_alert_episode_record_payload(
    payload: dict[str, Any],
) -> None:
    missing_fields = sorted(
        field_name
        for field_name in MONITOR_DEFINITION_ALERT_EPISODE_RECORD_REQUIRED_TOP_LEVEL_FIELDS
        if field_name not in payload
    )
    if missing_fields:
        raise MonitorDefinitionSchemaValidationError(
            "persisted monitor definition alert episode record payload is missing required field(s): "
            + ", ".join(missing_fields)
        )
    expected_episode_id = _canonical_monitor_definition_alert_episode_id_from_payload(
        _canonical_validation_payload_from_persisted_alert_episode_record_payload(payload)
    )
    if payload.get("episode_id") != expected_episode_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition alert episode record episode_id does not match canonical persisted payload content"
        )


def _validate_loaded_monitor_definition_alert_episode_record(
    record: MonitorDefinitionAlertEpisodeRecordArtifact,
    *,
    expected_monitor_definition_id: str | None = None,
    expected_monitor_definition_fingerprint: str | None = None,
    expected_monitor_definition_schema_version: str | None = None,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
) -> MonitorDefinitionAlertEpisodeRecordArtifact:
    if record.schema_version != "monitor_definition_alert_episode_record_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition alert episode record schema_version"
        )
    _validated_episode_id_key(record.episode_id)
    expected_episode_id = _canonical_monitor_definition_alert_episode_id_from_payload(
        _canonical_validation_payload_from_alert_episode_record(record)
    )
    if record.episode_id != expected_episode_id:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition alert episode record episode_id does not match canonical entry content"
        )
    monitor_definition_id = _validated_monitor_definition_id_key(record.monitor_definition_id)
    if expected_monitor_definition_id is not None and monitor_definition_id != expected_monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition alert episode record monitor_definition_id does not match persisted monitor definition"
        )
    if record.monitor_definition_schema_version != "monitor_definition_artifact_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition alert episode record monitor_definition_schema_version"
        )
    if (
        expected_monitor_definition_schema_version is not None
        and record.monitor_definition_schema_version != expected_monitor_definition_schema_version
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition alert episode record schema version does not match persisted monitor definition"
        )
    if (
        expected_monitor_definition_fingerprint is not None
        and record.monitor_definition_fingerprint != expected_monitor_definition_fingerprint
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition alert episode record fingerprint does not match persisted monitor definition"
        )
    if record.monitor_id != "benchmark_trend_overlay_v1":
        raise MonitorDefinitionIntegrityValidationError(
            "unsupported monitor definition alert episode record monitor_id"
        )
    if expected_monitor_id is not None and record.monitor_id != expected_monitor_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition alert episode record monitor_id does not match persisted monitor definition"
        )
    if record.benchmark_symbol != _validated_benchmark_symbol(record.benchmark_symbol):
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition alert episode record benchmark_symbol must be canonical"
        )
    if expected_benchmark_symbol is not None and record.benchmark_symbol != expected_benchmark_symbol:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition alert episode record benchmark_symbol does not match persisted monitor definition"
        )
    if (
        record.timeline_handoff.selected_event_kind == "latest_observation_event"
        and record.timeline_handoff.observation_id
        != record.latest_contributing_observation.observation_id
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition alert episode record latest-observation handoff does not match latest contributing observation"
        )
    if (
        record.timeline_handoff.selected_event_kind == "evaluation_history_event"
        and record.timeline_handoff.history_entry_id != record.terminal_history_entry_id
    ):
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition alert episode record evaluation-history handoff does not match terminal_history_entry_id"
        )
    return record


@dataclass(frozen=True)
class PersistedMonitorDefinitionLatestEvaluationSnapshot:
    artifact: MonitorDefinitionLatestEvaluationSnapshotArtifact
    evaluated_at: datetime
    outcome_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None


@dataclass(frozen=True)
class PersistedMonitorDefinitionObservation:
    artifact: MonitorDefinitionObservationArtifact
    evaluated_at: datetime
    observation_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None
    alert_classification: MonitorDefinitionLatestEvaluationSignificanceStatus
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None


@dataclass(frozen=True)
class PersistedMonitorDefinitionDiscoveryStatus:
    latest_observation_status: MonitorDefinitionLatestObservationStatus
    latest_observation: PersistedMonitorDefinitionObservation | None
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


@dataclass(frozen=True)
class PersistedMonitorDefinitionAlertHistoryQueueCandidate:
    definition_artifact: MonitorDefinitionArtifact
    latest_snapshot: PersistedMonitorDefinitionLatestEvaluationSnapshot
    history_entry: PersistedMonitorDefinitionEvaluationHistoryEntry
    latest_for_monitor_definition: bool


@dataclass(frozen=True)
class PersistedMonitorDefinitionAlertReviewTimelineState:
    definition_artifact: MonitorDefinitionArtifact
    observation: MonitorDefinitionObservationArtifact | None
    history_entries: list[PersistedMonitorDefinitionEvaluationHistoryEntry]
    latest_alert_episode: MonitorDefinitionAlertEpisode | None


@dataclass(frozen=True)
class PersistedMonitorDefinitionAlertEpisodeHistoryCandidate:
    definition_artifact: MonitorDefinitionArtifact
    episode_row: MonitorDefinitionAlertEpisodeHistoryRow


@dataclass(frozen=True)
class PersistedMonitorDefinitionActiveAlertEpisodeInboxCandidate:
    definition_artifact: MonitorDefinitionArtifact
    episode_row: MonitorDefinitionAlertEpisodeHistoryRow


@dataclass(frozen=True)
class PersistedMonitorDefinitionRecoveredAlertReviewQueueCandidate:
    definition_artifact: MonitorDefinitionArtifact
    latest_observation: MonitorDefinitionObservationArtifact
    latest_snapshot: PersistedMonitorDefinitionLatestEvaluationSnapshot
    latest_history_entry: PersistedMonitorDefinitionEvaluationHistoryEntry
    recovered_from_history_entry: PersistedMonitorDefinitionEvaluationHistoryEntry
    alert_episode: MonitorDefinitionAlertEpisode


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
            if path.name.endswith(".latest_evaluation.json") or path.name.endswith(".observation.json"):
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

    def observation_path(self, monitor_definition_id: str) -> Path:
        return self.base_dir / f"{_validated_monitor_definition_id_key(monitor_definition_id)}.observation.json"

    def evaluation_history_dir(self, monitor_definition_id: str) -> Path:
        return self.base_dir / f"{_validated_monitor_definition_id_key(monitor_definition_id)}.history"

    def evaluation_history_entry_path(self, monitor_definition_id: str, history_entry_id: str) -> Path:
        return self.evaluation_history_dir(monitor_definition_id) / f"{_validated_history_entry_id_key(history_entry_id)}.json"

    def alert_episode_history_dir(self, monitor_definition_id: str) -> Path:
        return self.base_dir / f"{_validated_monitor_definition_id_key(monitor_definition_id)}.episodes"

    def alert_episode_record_path(self, monitor_definition_id: str, episode_id: str) -> Path:
        return self.alert_episode_history_dir(monitor_definition_id) / f"{_validated_episode_id_key(episode_id)}.json"

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

    def persist_observation(
        self,
        observation: MonitorDefinitionObservationArtifact,
    ) -> MonitorDefinitionObservationArtifact:
        definition_artifact = self.load(observation.monitor_definition_id)
        validated_observation = validate_monitor_definition_observation(
            observation,
            expected_monitor_definition_id=definition_artifact.monitor_definition_id,
            expected_monitor_definition_fingerprint=definition_artifact.fingerprint,
            expected_monitor_definition_schema_version=definition_artifact.schema_version,
            expected_monitor_id=definition_artifact.monitor_id,
            expected_benchmark_symbol=definition_artifact.benchmark_symbol,
        )
        path = self.observation_path(validated_observation.monitor_definition_id)
        if path.exists():
            existing = self.load_observation(
                validated_observation.monitor_definition_id,
                expected_monitor_id=validated_observation.monitor_id,
                expected_benchmark_symbol=validated_observation.benchmark_symbol,
            )
            if existing.monitor_definition_id != validated_observation.monitor_definition_id:
                raise MonitorDefinitionPersistenceError(
                    f"persisted observation identity mismatch at {path}"
                )
        self._atomic_write_json(path, validated_observation.model_dump(mode="json"))
        return validated_observation

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
        observation: MonitorDefinitionObservationArtifact,
        snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
        entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
    ) -> tuple[
        MonitorDefinitionObservationArtifact,
        MonitorDefinitionLatestEvaluationSnapshotArtifact,
        MonitorDefinitionEvaluationHistoryEntryArtifact,
    ]:
        definition_artifact = self.load(snapshot.monitor_definition_id)
        validated_observation = validate_monitor_definition_observation(
            observation,
            expected_monitor_definition_id=definition_artifact.monitor_definition_id,
            expected_monitor_definition_fingerprint=definition_artifact.fingerprint,
            expected_monitor_definition_schema_version=definition_artifact.schema_version,
            expected_monitor_id=definition_artifact.monitor_id,
            expected_benchmark_symbol=definition_artifact.benchmark_symbol,
        )
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
            validated_observation,
            validated_snapshot,
            validated_entry,
        )

        observation_path = self.observation_path(validated_observation.monitor_definition_id)
        previous_observation_serialized = (
            observation_path.read_text(encoding="utf-8") if observation_path.exists() else None
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

        self._atomic_write_json(observation_path, validated_observation.model_dump(mode="json"))
        try:
            self._atomic_write_json(snapshot_path, validated_snapshot.model_dump(mode="json"))
            history_dir.mkdir(parents=True, exist_ok=True)
            self._write_once(history_path, validated_entry.model_dump(mode="json"))
        except Exception as exc:
            rollback_errors = self._rollback_evaluation_artifact_persistence(
                observation_path=observation_path,
                previous_observation_serialized=previous_observation_serialized,
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

        episode_history_rows = self._list_alert_episode_history_rows(
            validated_entry.monitor_definition_id,
            definition_artifact,
        )
        self._persist_alert_episode_history_rows(
            validated_entry.monitor_definition_id,
            episode_history_rows,
        )

        return validated_observation, validated_snapshot, validated_entry

    def load_observation(
        self,
        monitor_definition_id: str,
        *,
        expected_monitor_id: str | None = None,
        expected_benchmark_symbol: str | None = None,
    ) -> MonitorDefinitionObservationArtifact:
        definition_artifact = self.load(monitor_definition_id)
        path = self.observation_path(monitor_definition_id)
        payload = _read_json_object(path, subject="persisted monitor definition observation")
        _validate_raw_persisted_monitor_definition_observation_payload(payload)
        try:
            observation = MonitorDefinitionObservationArtifact.model_validate(payload)
        except ValidationError as exc:
            raise MonitorDefinitionSchemaValidationError(
                f"persisted monitor definition observation failed schema validation: {path}"
            ) from exc
        validated = _validate_loaded_monitor_definition_observation(
            observation,
            expected_monitor_definition_id=definition_artifact.monitor_definition_id,
            expected_monitor_definition_fingerprint=definition_artifact.fingerprint,
            expected_monitor_definition_schema_version=definition_artifact.schema_version,
            expected_monitor_id=expected_monitor_id,
            expected_benchmark_symbol=expected_benchmark_symbol,
        )
        snapshot = None
        if self.latest_evaluation_snapshot_path(monitor_definition_id).exists():
            snapshot = self.load_latest_evaluation_snapshot(
                monitor_definition_id,
                expected_monitor_id=expected_monitor_id,
                expected_benchmark_symbol=expected_benchmark_symbol,
            )
        entries = self._list_persisted_evaluation_history_entries(monitor_definition_id, definition_artifact)
        _validate_latest_persisted_evaluation_alignment(
            observation=validated,
            snapshot=snapshot,
            entries=entries,
        )
        return validated

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

    def load_raw_alert_episode_record(
        self,
        monitor_definition_id: str,
        episode_id: str,
    ) -> RawPersistedMonitorDefinitionEvaluationHistoryEntry:
        path = self.alert_episode_record_path(monitor_definition_id, episode_id)
        return RawPersistedMonitorDefinitionEvaluationHistoryEntry(
            entry_path=path,
            payload=_read_json_object(path, subject="persisted monitor definition alert episode record"),
        )

    def list_evaluation_history(
        self,
        monitor_definition_id: str,
        *,
        limit: int | None = None,
    ) -> MonitorDefinitionEvaluationHistoryResponse:
        definition_artifact = self.load(monitor_definition_id)
        entries = self._list_persisted_evaluation_history_entries(monitor_definition_id, definition_artifact)
        observation = None
        if self.observation_path(monitor_definition_id).exists():
            observation = self.load_observation(
                monitor_definition_id,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
        snapshot = None
        if self.latest_evaluation_snapshot_path(monitor_definition_id).exists():
            snapshot = self.load_latest_evaluation_snapshot(
                monitor_definition_id,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
        _validate_latest_persisted_evaluation_alignment(
            observation=observation,
            snapshot=snapshot,
            entries=entries,
        )
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

    def list_latest_observation_alert_inbox(
        self,
        *,
        limit: int = 20,
    ) -> MonitorDefinitionLatestObservationAlertInboxResponse:
        if limit < 1:
            return MonitorDefinitionLatestObservationAlertInboxResponse(
                items=[],
                metadata=MonitorDefinitionLatestObservationAlertInboxResponseMetadata(
                    returned_limit=limit,
                ),
            )
        rows = self._list_latest_observation_alert_rows()[:limit]
        return MonitorDefinitionLatestObservationAlertInboxResponse(
            items=rows,
            metadata=MonitorDefinitionLatestObservationAlertInboxResponseMetadata(
                returned_limit=limit,
            ),
        )

    def list_alert_history_queue(
        self,
        *,
        limit: int = 20,
    ) -> MonitorDefinitionAlertHistoryQueueResponse:
        if limit < 1:
            return MonitorDefinitionAlertHistoryQueueResponse(
                items=[],
                metadata=MonitorDefinitionAlertHistoryQueueResponseMetadata(
                    returned_limit=limit,
                    total_queue_rows=0,
                ),
            )
        rows = self._list_alert_history_queue_rows()
        return MonitorDefinitionAlertHistoryQueueResponse(
            items=rows[:limit],
            metadata=MonitorDefinitionAlertHistoryQueueResponseMetadata(
                returned_limit=limit,
                total_queue_rows=len(rows),
            ),
        )

    def list_recovered_alert_review_queue(
        self,
        *,
        limit: int = 20,
    ) -> MonitorDefinitionRecoveredAlertReviewQueueResponse:
        if limit < 1:
            return MonitorDefinitionRecoveredAlertReviewQueueResponse(
                items=[],
                metadata=MonitorDefinitionRecoveredAlertReviewQueueResponseMetadata(
                    returned_limit=limit,
                    total_queue_rows=0,
                ),
            )
        rows = self._list_recovered_alert_review_queue_rows()
        return MonitorDefinitionRecoveredAlertReviewQueueResponse(
            items=rows[:limit],
            metadata=MonitorDefinitionRecoveredAlertReviewQueueResponseMetadata(
                returned_limit=limit,
                total_queue_rows=len(rows),
            ),
        )

    def list_active_alert_episode_inbox(
        self,
        *,
        limit: int | None = 20,
        before_episode_id: str | None = None,
    ) -> MonitorDefinitionActiveAlertEpisodeInboxResponse:
        rows = [
            _active_alert_episode_inbox_row_from_candidate(candidate)
            for candidate in self._list_active_alert_episode_inbox_candidates()
        ]
        if before_episode_id is not None:
            matching_index = next(
                (
                    index
                    for index, row in enumerate(rows)
                    if row.alert_episode.episode_id == before_episode_id
                ),
                None,
            )
            if matching_index is None:
                raise MonitorDefinitionIntegrityValidationError(
                    "requested before_episode_id is not present in persisted active alert episode inbox"
                )
            rows = rows[matching_index + 1 :]
        if limit is not None and limit < 0:
            limit = 0
        returned_rows = rows if limit is None else rows[:limit]
        next_before_episode_id = None
        if limit is not None and len(rows) > len(returned_rows) and returned_rows:
            next_before_episode_id = returned_rows[-1].alert_episode.episode_id
        return MonitorDefinitionActiveAlertEpisodeInboxResponse(
            items=returned_rows,
            metadata=MonitorDefinitionActiveAlertEpisodeInboxResponseMetadata(
                returned_limit=limit,
                requested_before_episode_id=before_episode_id,
                next_before_episode_id=next_before_episode_id,
                total_active_episodes=len(rows),
            ),
        )

    def get_alert_review_timeline(
        self,
        monitor_definition_id: str,
    ) -> MonitorDefinitionAlertReviewTimelineResponse:
        definition_artifact = self.load(monitor_definition_id)
        timeline_state = self._load_alert_review_timeline_state(monitor_definition_id, definition_artifact)
        rows = self._build_alert_review_timeline_rows(timeline_state)
        return MonitorDefinitionAlertReviewTimelineResponse(
            items=rows,
            metadata=MonitorDefinitionAlertReviewTimelineResponseMetadata(
                monitor_definition_id=definition_artifact.monitor_definition_id,
                monitor_definition_fingerprint=definition_artifact.fingerprint,
                latest_alert_episode=timeline_state.latest_alert_episode,
                total_rows=len(rows),
                observation_rows=sum(1 for row in rows if row.event_kind == "latest_observation_event"),
                history_rows=sum(1 for row in rows if row.event_kind == "evaluation_history_event"),
            ),
        )

    def list_alert_episode_history(
        self,
        monitor_definition_id: str,
        *,
        limit: int | None = None,
        before_episode_id: str | None = None,
    ) -> MonitorDefinitionAlertEpisodeHistoryResponse:
        definition_artifact = self.load(monitor_definition_id)
        rebuilt_rows = self._list_alert_episode_history_rows(
            monitor_definition_id,
            definition_artifact,
        )
        persisted_candidates = self._list_persisted_alert_episode_history_candidates(
            monitor_definition_id,
            definition_artifact,
        )
        if persisted_candidates:
            persisted_rows = [candidate.episode_row for candidate in persisted_candidates]
            if [row.model_dump(mode="json") for row in persisted_rows] != [
                row.model_dump(mode="json") for row in rebuilt_rows
            ]:
                raise MonitorDefinitionIntegrityValidationError(
                    "persisted alert episode history does not match canonical persisted evaluation lineage"
                )
            all_rows = persisted_rows
        else:
            all_rows = rebuilt_rows
        rows = all_rows
        if before_episode_id is not None:
            matching_index = next(
                (
                    index
                    for index, row in enumerate(rows)
                    if row.episode_id == before_episode_id
                ),
                None,
            )
            if matching_index is None:
                raise MonitorDefinitionIntegrityValidationError(
                    "requested before_episode_id is not present in persisted alert episode history"
                )
            rows = rows[matching_index + 1 :]
        if limit is not None and limit < 0:
            limit = 0
        returned_rows = rows if limit is None else rows[:limit]
        next_before_episode_id = None
        if limit is not None and limit >= 0 and len(rows) > len(returned_rows) and returned_rows:
            next_before_episode_id = returned_rows[-1].episode_id
        return MonitorDefinitionAlertEpisodeHistoryResponse(
            items=returned_rows,
            metadata=MonitorDefinitionAlertEpisodeHistoryResponseMetadata(
                monitor_definition_id=definition_artifact.monitor_definition_id,
                monitor_definition_fingerprint=definition_artifact.fingerprint,
                returned_limit=limit,
                requested_before_episode_id=before_episode_id,
                next_before_episode_id=next_before_episode_id,
                total_episodes=len(all_rows),
            ),
        )

    def _list_latest_observation_alert_rows(
        self,
    ) -> list[MonitorDefinitionLatestObservationAlertInboxRow]:
        rows: list[MonitorDefinitionLatestObservationAlertInboxRow] = []
        for item in self._list_persisted_artifacts():
            observation = item.discovery_status.latest_observation
            if observation is None:
                continue
            if observation.alert_classification == "informational":
                continue
            rows.append(_latest_observation_alert_inbox_row_from_persisted_artifact(item, observation))
        rows.sort(
            key=lambda row: (
                -row.evaluated_at.timestamp(),
                row.monitor_definition_id,
                row.observation_id,
            )
        )
        return rows

    def _list_alert_history_queue_rows(
        self,
    ) -> list[MonitorDefinitionAlertHistoryQueueRow]:
        rows = [
            _alert_history_queue_row_from_candidate(candidate)
            for candidate in self._list_alert_history_queue_candidates()
        ]
        previous_order: tuple[float, int, str, str] | None = None
        for row in rows:
            current_order = (
                row.evaluated_at.timestamp(),
                1 if row.latest_for_monitor_definition else 0,
                row.monitor_definition_id,
                row.history_entry_id,
            )
            if previous_order is not None and current_order > previous_order:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition alert history queue ordering is ambiguous"
                )
            previous_order = current_order
        return rows

    def _list_alert_episode_history_rows(
        self,
        monitor_definition_id: str,
        definition_artifact: MonitorDefinitionArtifact,
    ) -> list[MonitorDefinitionAlertEpisodeHistoryRow]:
        observation = None
        if self.observation_path(monitor_definition_id).exists():
            observation = self.load_observation(
                monitor_definition_id,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
        history_entries = self._list_persisted_evaluation_history_entries(
            monitor_definition_id,
            definition_artifact,
        )
        snapshot = None
        if self.latest_evaluation_snapshot_path(monitor_definition_id).exists():
            snapshot = self.load_latest_evaluation_snapshot(
                monitor_definition_id,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
        _validate_latest_persisted_evaluation_alignment(
            observation=observation,
            snapshot=snapshot,
            entries=history_entries,
        )
        if observation is not None and history_entries:
            _validate_latest_observation_history_alignment(observation, history_entries[0].artifact)
        return _build_alert_episode_history_rows(
            definition_artifact=definition_artifact,
            observation=observation,
            history_entries=history_entries,
        )

    def _list_persisted_alert_episode_history_candidates(
        self,
        monitor_definition_id: str,
        definition_artifact: MonitorDefinitionArtifact,
    ) -> list[PersistedMonitorDefinitionAlertEpisodeHistoryCandidate]:
        episode_dir = self.alert_episode_history_dir(monitor_definition_id)
        if not episode_dir.exists():
            return []
        candidates: list[PersistedMonitorDefinitionAlertEpisodeHistoryCandidate] = []
        for path in episode_dir.glob("*.json"):
            raw = RawPersistedMonitorDefinitionEvaluationHistoryEntry(
                entry_path=path,
                payload=_read_json_object(path, subject="persisted monitor definition alert episode record"),
            )
            _validate_raw_persisted_monitor_definition_alert_episode_record_payload(raw.payload)
            try:
                record = MonitorDefinitionAlertEpisodeRecordArtifact.model_validate(raw.payload)
            except ValidationError as exc:
                raise MonitorDefinitionSchemaValidationError(
                    f"persisted monitor definition alert episode record failed schema validation: {path}"
                ) from exc
            validated = _validate_loaded_monitor_definition_alert_episode_record(
                record,
                expected_monitor_definition_id=definition_artifact.monitor_definition_id,
                expected_monitor_definition_fingerprint=definition_artifact.fingerprint,
                expected_monitor_definition_schema_version=definition_artifact.schema_version,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
            candidates.append(
                PersistedMonitorDefinitionAlertEpisodeHistoryCandidate(
                    definition_artifact=definition_artifact,
                    episode_row=MonitorDefinitionAlertEpisodeHistoryRow.model_validate(
                        validated.model_dump(mode="json")
                    ),
                )
            )
        candidates.sort(
            key=lambda candidate: (
                -candidate.episode_row.latest_event_at.timestamp(),
                candidate.episode_row.episode_id,
            )
        )
        return candidates

    def _persist_alert_episode_history_rows(
        self,
        monitor_definition_id: str,
        rows: list[MonitorDefinitionAlertEpisodeHistoryRow],
    ) -> None:
        episode_dir = self.alert_episode_history_dir(monitor_definition_id)
        episode_dir.mkdir(parents=True, exist_ok=True)
        expected_ids = {row.episode_id for row in rows}
        for path in episode_dir.glob("*.json"):
            if path.stem not in expected_ids:
                path.unlink()
        for row in rows:
            self._atomic_write_json(
                self.alert_episode_record_path(monitor_definition_id, row.episode_id),
                MonitorDefinitionAlertEpisodeRecordArtifact.model_validate(
                    row.model_dump(mode="json", exclude={"metadata"})
                ).model_dump(mode="json"),
            )
        if not rows and episode_dir.exists() and not any(episode_dir.iterdir()):
            episode_dir.rmdir()

    def _list_recovered_alert_review_queue_rows(
        self,
    ) -> list[MonitorDefinitionRecoveredAlertReviewQueueRow]:
        rows = [
            _recovered_alert_review_queue_row_from_candidate(candidate)
            for candidate in self._list_recovered_alert_review_queue_candidates()
        ]
        previous_order: tuple[float, str, str] | None = None
        for row in rows:
            current_order = (
                row.evaluated_at.timestamp(),
                row.monitor_definition_id,
                row.observation_id,
            )
            if previous_order is not None and current_order > previous_order:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition recovered alert review queue ordering is ambiguous"
                )
            previous_order = current_order
        return rows

    def _list_active_alert_episode_inbox_candidates(
        self,
    ) -> list[PersistedMonitorDefinitionActiveAlertEpisodeInboxCandidate]:
        candidates: list[PersistedMonitorDefinitionActiveAlertEpisodeInboxCandidate] = []
        for item in self._list_persisted_artifacts():
            definition_artifact = item.artifact
            rebuilt_rows = self._list_alert_episode_history_rows(
                definition_artifact.monitor_definition_id,
                definition_artifact,
            )
            persisted_candidates = self._list_persisted_alert_episode_history_candidates(
                definition_artifact.monitor_definition_id,
                definition_artifact,
            )
            if not persisted_candidates:
                if rebuilt_rows:
                    raise MonitorDefinitionIntegrityValidationError(
                        "active alert episode inbox requires authoritative persisted alert episode records when canonical persisted alert lineage is present"
                    )
                continue
            persisted_rows = [candidate.episode_row for candidate in persisted_candidates]
            if [row.model_dump(mode="json") for row in persisted_rows] != [
                row.model_dump(mode="json") for row in rebuilt_rows
            ]:
                raise MonitorDefinitionIntegrityValidationError(
                    "persisted alert episode history does not match canonical persisted evaluation lineage"
                )
            latest_row = persisted_rows[0]
            if latest_row.lifecycle_status != "open":
                continue
            candidates.append(
                PersistedMonitorDefinitionActiveAlertEpisodeInboxCandidate(
                    definition_artifact=definition_artifact,
                    episode_row=latest_row,
                )
            )
        candidates.sort(
            key=lambda candidate: (
                -candidate.episode_row.latest_event_at.timestamp(),
                candidate.definition_artifact.monitor_definition_id,
                candidate.episode_row.episode_id,
            )
        )
        previous_order: tuple[float, str, str] | None = None
        for candidate in candidates:
            current_order = (
                candidate.episode_row.latest_event_at.timestamp(),
                candidate.definition_artifact.monitor_definition_id,
                candidate.episode_row.episode_id,
            )
            if previous_order is not None and current_order > previous_order:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition active alert episode inbox ordering is ambiguous"
                )
            previous_order = current_order
        return candidates

    def _load_alert_review_timeline_state(
        self,
        monitor_definition_id: str,
        definition_artifact: MonitorDefinitionArtifact,
    ) -> PersistedMonitorDefinitionAlertReviewTimelineState:
        observation = None
        if self.observation_path(monitor_definition_id).exists():
            observation = self.load_observation(
                monitor_definition_id,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
        history_entries = self._list_persisted_evaluation_history_entries(
            monitor_definition_id,
            definition_artifact,
        )
        snapshot = None
        if self.latest_evaluation_snapshot_path(monitor_definition_id).exists():
            snapshot = self.load_latest_evaluation_snapshot(
                monitor_definition_id,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
        _validate_latest_persisted_evaluation_alignment(
            observation=observation,
            snapshot=snapshot,
            entries=history_entries,
        )
        if observation is not None and history_entries:
            _validate_latest_observation_history_alignment(observation, history_entries[0].artifact)
        return PersistedMonitorDefinitionAlertReviewTimelineState(
            definition_artifact=definition_artifact,
            observation=observation,
            history_entries=history_entries,
            latest_alert_episode=_build_latest_alert_episode(
                monitor_definition_id=definition_artifact.monitor_definition_id,
                observation=observation,
                history_entries=history_entries,
            ),
        )

    def _build_alert_review_timeline_rows(
        self,
        timeline_state: PersistedMonitorDefinitionAlertReviewTimelineState,
    ) -> list[MonitorDefinitionAlertReviewTimelineObservationRow | MonitorDefinitionAlertReviewTimelineHistoryRow]:
        definition_artifact = timeline_state.definition_artifact
        rows: list[
            MonitorDefinitionAlertReviewTimelineObservationRow | MonitorDefinitionAlertReviewTimelineHistoryRow
        ] = []
        if timeline_state.observation is not None:
            observation = timeline_state.observation
            rows.append(
                MonitorDefinitionAlertReviewTimelineObservationRow(
                    monitor_definition_id=definition_artifact.monitor_definition_id,
                    monitor_definition_fingerprint=definition_artifact.fingerprint,
                    monitor_definition_schema_version=definition_artifact.schema_version,
                    observation_id=observation.observation_id,
                    monitor_id=definition_artifact.monitor_id,
                    benchmark_symbol=definition_artifact.benchmark_symbol,
                    review_scope=definition_artifact.review_scope,
                    evaluation_mode=definition_artifact.evaluation_mode,
                    evaluated_at=observation.evaluated_at,
                    observation_status=observation.observation_status,
                    cause_code=observation.cause_code,
                    alert_classification=observation.alert_classification,
                    hysteresis_transition=observation.hysteresis_transition,
                    recency_status=_latest_observation_recency(observation.evaluated_at),
                    reason=observation.reason,
                    open_handoff=MonitorDefinitionObservationOpenHandoff(
                        monitor_definition_id=definition_artifact.monitor_definition_id,
                        observation_id=observation.observation_id,
                        monitor_id=definition_artifact.monitor_id,
                        benchmark_symbol=definition_artifact.benchmark_symbol,
                    ),
                    thresholds=observation.thresholds,
                    benchmark_observation=observation.benchmark_observation,
                    portfolio_observation=observation.portfolio_observation,
                    active_observation=observation.active_observation,
                )
            )
        for index, entry in enumerate(timeline_state.history_entries):
            history_artifact = entry.artifact
            resolved_hysteresis_transition = _history_entry_hysteresis_transition_for_row(
                history_entries=timeline_state.history_entries,
                index=index,
            )
            rows.append(
                MonitorDefinitionAlertReviewTimelineHistoryRow(
                    monitor_definition_id=definition_artifact.monitor_definition_id,
                    monitor_definition_fingerprint=definition_artifact.fingerprint,
                    monitor_definition_schema_version=definition_artifact.schema_version,
                    history_entry_id=history_artifact.history_entry_id,
                    monitor_id=definition_artifact.monitor_id,
                    benchmark_symbol=definition_artifact.benchmark_symbol,
                    review_scope=definition_artifact.review_scope,
                    evaluation_mode=definition_artifact.evaluation_mode,
                    evaluated_at=history_artifact.evaluated_at,
                    outcome_status=history_artifact.observation_status,
                    cause_code=history_artifact.cause_code,
                    significance_status=history_artifact.significance_status,
                    hysteresis_transition=resolved_hysteresis_transition,
                    review_support_status="review_supported",
                    latest_for_monitor_definition=index == 0,
                    reason=history_artifact.reason,
                    review_handoff=MonitorDefinitionEvaluationHistoryReviewHandoff(
                        monitor_definition_id=definition_artifact.monitor_definition_id,
                        history_entry_id=history_artifact.history_entry_id,
                        monitor_id=definition_artifact.monitor_id,
                        benchmark_symbol=definition_artifact.benchmark_symbol,
                    ),
                    thresholds=history_artifact.thresholds,
                    benchmark_observation=history_artifact.benchmark_observation,
                    portfolio_observation=history_artifact.portfolio_observation,
                    active_observation=history_artifact.active_observation,
                )
            )
        rows.sort(
            key=lambda row: (
                -row.evaluated_at.timestamp(),
                0 if row.event_kind == "latest_observation_event" else 1,
                "" if row.event_kind == "latest_observation_event" else row.history_entry_id,
            )
        )
        return rows

    def _list_alert_history_queue_candidates(
        self,
    ) -> list[PersistedMonitorDefinitionAlertHistoryQueueCandidate]:
        candidates: list[PersistedMonitorDefinitionAlertHistoryQueueCandidate] = []
        for item in self._list_persisted_artifacts():
            entries = self._list_persisted_evaluation_history_entries(
                item.artifact.monitor_definition_id,
                item.artifact,
            )
            queue_entries = [
                entry for entry in entries if entry.artifact.significance_status != "informational"
            ]
            snapshot = item.discovery_status.latest_evaluation_snapshot
            if queue_entries and snapshot is None:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition alert history queue requires a canonical latest snapshot when persisted alert history entries are present"
                )
            if snapshot is None:
                continue
            latest_entry = entries[0].artifact if entries else None
            if latest_entry is None:
                if snapshot.significance_status != "informational":
                    raise MonitorDefinitionIntegrityValidationError(
                        "monitor definition alert history queue requires canonical persisted evaluation history when latest snapshot is alert-eligible"
                    )
                continue
            if latest_entry.evaluated_at != snapshot.evaluated_at:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition alert history queue latest snapshot evaluated_at must match the latest persisted evaluation history entry"
                )
            if latest_entry.observation_status != snapshot.outcome_status:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition alert history queue latest snapshot outcome_status must match the latest persisted evaluation history entry"
                )
            if latest_entry.cause_code != snapshot.cause_code:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition alert history queue latest snapshot cause_code must match the latest persisted evaluation history entry"
                )
            if latest_entry.significance_status != snapshot.significance_status:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition alert history queue latest snapshot significance_status must match the latest persisted evaluation history entry"
                )
            for entry in queue_entries:
                candidates.append(
                    PersistedMonitorDefinitionAlertHistoryQueueCandidate(
                        definition_artifact=item.artifact,
                        latest_snapshot=snapshot,
                        history_entry=entry,
                        latest_for_monitor_definition=(
                            entry.artifact.history_entry_id == latest_entry.history_entry_id
                        ),
                    )
                )
        candidates.sort(
            key=lambda candidate: (
                -candidate.history_entry.artifact.evaluated_at.timestamp(),
                -int(candidate.latest_for_monitor_definition),
                candidate.definition_artifact.monitor_definition_id,
                candidate.history_entry.artifact.history_entry_id,
            )
        )
        return candidates

    def _list_recovered_alert_review_queue_candidates(
        self,
    ) -> list[PersistedMonitorDefinitionRecoveredAlertReviewQueueCandidate]:
        candidates: list[PersistedMonitorDefinitionRecoveredAlertReviewQueueCandidate] = []
        for item in self._list_persisted_artifacts():
            definition_artifact = item.artifact
            observation = item.discovery_status.latest_observation
            snapshot = item.discovery_status.latest_evaluation_snapshot
            if observation is None or snapshot is None:
                continue
            if observation.artifact.alert_classification != "informational":
                continue
            if observation.artifact.hysteresis_transition != "recover":
                continue
            entries = self._list_persisted_evaluation_history_entries(
                definition_artifact.monitor_definition_id,
                definition_artifact,
            )
            if not entries:
                continue
            latest_entry = entries[0]
            if len(entries) > 1 and entries[1].artifact.evaluated_at == latest_entry.artifact.evaluated_at:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition recovered alert review queue latest history state is ambiguous"
                )
            _validate_monitor_definition_evaluation_persistence_pair(
                observation.artifact,
                snapshot.artifact,
                latest_entry.artifact,
            )
            if latest_entry.artifact.significance_status != "informational":
                continue
            recovered_from_entry = next(
                (
                    entry
                    for entry in entries[1:]
                    if entry.artifact.significance_status != "informational"
                ),
                None,
            )
            if recovered_from_entry is None:
                continue
            alert_episode = _build_latest_alert_episode(
                monitor_definition_id=definition_artifact.monitor_definition_id,
                observation=observation.artifact,
                history_entries=entries,
            )
            if alert_episode is None:
                raise MonitorDefinitionIntegrityValidationError(
                    "monitor definition recovered alert review queue requires a recovered alert episode"
                )
            candidates.append(
                PersistedMonitorDefinitionRecoveredAlertReviewQueueCandidate(
                    definition_artifact=definition_artifact,
                    latest_observation=observation.artifact,
                    latest_snapshot=snapshot,
                    latest_history_entry=latest_entry,
                    recovered_from_history_entry=recovered_from_entry,
                    alert_episode=alert_episode,
                )
            )
        candidates.sort(
            key=lambda candidate: (
                -candidate.latest_observation.evaluated_at.timestamp(),
                candidate.definition_artifact.monitor_definition_id,
                candidate.latest_observation.observation_id,
            )
        )
        return candidates

    def _list_persisted_artifacts(
        self,
        *,
        filters: MonitorDefinitionDiscoveryFilters | None = None,
    ) -> list[PersistedMonitorDefinitionArtifact]:
        normalized_filters = filters or MonitorDefinitionDiscoveryFilters()
        artifacts: list[PersistedMonitorDefinitionArtifact] = []
        for path in self.base_dir.glob("monitor_definition_*.json"):
            if path.name.endswith(".latest_evaluation.json") or path.name.endswith(".observation.json"):
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
        observation_path = self.observation_path(definition_artifact.monitor_definition_id)
        observation = None
        observation_status: MonitorDefinitionLatestObservationStatus = "absent"
        if observation_path.exists():
            observation_artifact = self.load_observation(
                definition_artifact.monitor_definition_id,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
            observation = PersistedMonitorDefinitionObservation(
                artifact=observation_artifact,
                evaluated_at=observation_artifact.evaluated_at,
                observation_status=observation_artifact.observation_status,
                cause_code=observation_artifact.cause_code,
                alert_classification=observation_artifact.alert_classification,
            )
            observation_status = "present"

        snapshot_path = self.latest_evaluation_snapshot_path(definition_artifact.monitor_definition_id)
        snapshot = None
        snapshot_status: MonitorDefinitionLatestEvaluationSnapshotStatus = "absent"
        if snapshot_path.exists():
            snapshot_artifact = self.load_latest_evaluation_snapshot(
                definition_artifact.monitor_definition_id,
                expected_monitor_id=definition_artifact.monitor_id,
                expected_benchmark_symbol=definition_artifact.benchmark_symbol,
            )
            snapshot = PersistedMonitorDefinitionLatestEvaluationSnapshot(
                artifact=snapshot_artifact,
                evaluated_at=snapshot_artifact.evaluated_at,
                outcome_status=snapshot_artifact.outcome_status,
                cause_code=snapshot_artifact.cause_code,
                significance_status=snapshot_artifact.significance_status,
            )
            snapshot_status = "present"

        entries = self._list_persisted_evaluation_history_entries(
            definition_artifact.monitor_definition_id,
            definition_artifact,
        )
        _validate_latest_persisted_evaluation_alignment(
            observation=observation.artifact if observation is not None else None,
            snapshot=snapshot.artifact if snapshot is not None else None,
            entries=entries,
        )

        return PersistedMonitorDefinitionDiscoveryStatus(
            latest_observation_status=observation_status,
            latest_observation=observation,
            latest_evaluation_snapshot_status=snapshot_status,
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
        observation_path: Path,
        previous_observation_serialized: str | None,
        snapshot_path: Path,
        previous_snapshot_serialized: str | None,
        history_dir: Path,
        history_dir_existed: bool,
        history_path: Path,
    ) -> list[str]:
        rollback_errors: list[str] = []

        try:
            if previous_observation_serialized is None:
                if observation_path.exists():
                    observation_path.unlink()
            else:
                self._atomic_write_text(observation_path, previous_observation_serialized)
        except OSError as exc:
            rollback_errors.append(f"observation rollback failed at {observation_path}: {exc}")

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


def list_monitor_definition_latest_observation_alert_inbox(
    *,
    limit: int = 20,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionLatestObservationAlertInboxResponse:
    return (store or MonitorDefinitionArtifactStore()).list_latest_observation_alert_inbox(limit=limit)


def list_monitor_definition_alert_history_queue(
    *,
    limit: int = 20,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionAlertHistoryQueueResponse:
    return (store or MonitorDefinitionArtifactStore()).list_alert_history_queue(limit=limit)


def list_monitor_definition_recovered_alert_review_queue(
    *,
    limit: int = 20,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionRecoveredAlertReviewQueueResponse:
    return (store or MonitorDefinitionArtifactStore()).list_recovered_alert_review_queue(
        limit=limit
    )


def list_monitor_definition_active_alert_episode_inbox(
    *,
    limit: int | None = 20,
    before_episode_id: str | None = None,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionActiveAlertEpisodeInboxResponse:
    return (store or MonitorDefinitionArtifactStore()).list_active_alert_episode_inbox(
        limit=limit,
        before_episode_id=before_episode_id,
    )


def list_monitor_definition_alert_episode_history(
    monitor_definition_id: str,
    *,
    limit: int | None = None,
    before_episode_id: str | None = None,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionAlertEpisodeHistoryResponse:
    return (store or MonitorDefinitionArtifactStore()).list_alert_episode_history(
        monitor_definition_id,
        limit=limit,
        before_episode_id=before_episode_id,
    )


def get_monitor_definition_alert_review_timeline(
    monitor_definition_id: str,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionAlertReviewTimelineResponse:
    return (store or MonitorDefinitionArtifactStore()).get_alert_review_timeline(monitor_definition_id)


def persist_monitor_definition_latest_evaluation_snapshot(
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionLatestEvaluationSnapshotArtifact:
    return (store or MonitorDefinitionArtifactStore()).persist_latest_evaluation_snapshot(snapshot)


def persist_monitor_definition_observation(
    observation: MonitorDefinitionObservationArtifact,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionObservationArtifact:
    return (store or MonitorDefinitionArtifactStore()).persist_observation(observation)


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


def load_monitor_definition_observation(
    monitor_definition_id: str,
    *,
    expected_monitor_id: str | None = None,
    expected_benchmark_symbol: str | None = None,
    store: MonitorDefinitionArtifactStore | None = None,
) -> MonitorDefinitionObservationArtifact:
    return (store or MonitorDefinitionArtifactStore()).load_observation(
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
    observation: MonitorDefinitionObservationArtifact,
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
    *,
    store: MonitorDefinitionArtifactStore | None = None,
) -> tuple[
    MonitorDefinitionObservationArtifact,
    MonitorDefinitionLatestEvaluationSnapshotArtifact,
    MonitorDefinitionEvaluationHistoryEntryArtifact,
]:
    return (store or MonitorDefinitionArtifactStore()).persist_evaluation_artifacts(
        observation,
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
    observation: MonitorDefinitionObservationArtifact,
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact,
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
) -> None:
    if observation.monitor_definition_id != snapshot.monitor_definition_id:
        raise MonitorDefinitionPersistenceError(
            "observation monitor_definition_id must match latest evaluation snapshot"
        )
    if observation.monitor_definition_id != entry.monitor_definition_id:
        raise MonitorDefinitionPersistenceError(
            "observation monitor_definition_id must match evaluation history entry"
        )
    if observation.monitor_id != snapshot.monitor_id or observation.monitor_id != entry.monitor_id:
        raise MonitorDefinitionPersistenceError(
            "observation monitor_id must match persisted evaluation artifacts"
        )
    if observation.benchmark_symbol != snapshot.benchmark_symbol or observation.benchmark_symbol != entry.benchmark_symbol:
        raise MonitorDefinitionPersistenceError(
            "observation benchmark_symbol must match persisted evaluation artifacts"
        )
    if observation.evaluated_at != snapshot.evaluated_at or observation.evaluated_at != entry.evaluated_at:
        raise MonitorDefinitionPersistenceError(
            "observation evaluated_at must match persisted evaluation artifacts"
        )
    if observation.observation_status != snapshot.outcome_status or observation.observation_status != entry.observation_status:
        raise MonitorDefinitionPersistenceError(
            "observation observation_status must match persisted evaluation artifacts"
        )
    if observation.cause_code != snapshot.cause_code or observation.cause_code != entry.cause_code:
        raise MonitorDefinitionPersistenceError(
            "observation cause_code must match persisted evaluation artifacts"
        )
    if observation.alert_classification != snapshot.significance_status or observation.alert_classification != entry.significance_status:
        raise MonitorDefinitionPersistenceError(
            "observation alert_classification must match persisted evaluation artifacts"
        )
    present_hysteresis_transitions = [
        transition
        for transition in (
            observation.hysteresis_transition,
            snapshot.hysteresis_transition,
            entry.hysteresis_transition,
        )
        if transition is not None
    ]
    if present_hysteresis_transitions and any(
        transition != present_hysteresis_transitions[0]
        for transition in present_hysteresis_transitions[1:]
    ):
        raise MonitorDefinitionPersistenceError(
            "observation hysteresis_transition must match persisted evaluation artifacts"
        )
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
    if entry.cause_code != snapshot.cause_code:
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry cause_code must match latest evaluation snapshot"
        )
    if entry.significance_status != snapshot.significance_status:
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry significance_status must match latest evaluation snapshot"
        )
    if (
        entry.hysteresis_transition is not None
        and snapshot.hysteresis_transition is not None
        and entry.hysteresis_transition != snapshot.hysteresis_transition
    ):
        raise MonitorDefinitionPersistenceError(
            "evaluation history entry hysteresis_transition must match latest evaluation snapshot"
        )


def _validate_latest_persisted_evaluation_alignment(
    *,
    observation: MonitorDefinitionObservationArtifact | None,
    snapshot: MonitorDefinitionLatestEvaluationSnapshotArtifact | None,
    entries: list[PersistedMonitorDefinitionEvaluationHistoryEntry],
) -> None:
    if len(entries) > 1 and entries[1].artifact.evaluated_at == entries[0].artifact.evaluated_at:
        return
    if entries:
        latest_entry = entries[0].artifact
        previous_significance_status = (
            entries[1].artifact.significance_status if len(entries) > 1 else None
        )
        resolved_hysteresis_transition = _resolved_hysteresis_transition(
            current_significance_status=latest_entry.significance_status,
            current_hysteresis_transition=latest_entry.hysteresis_transition,
            previous_significance_status=previous_significance_status,
            source_label="persisted latest evaluation history entry",
        )
        if observation is not None:
            _validate_matching_hysteresis_transition(
                current_hysteresis_transition=observation.hysteresis_transition,
                expected_hysteresis_transition=resolved_hysteresis_transition,
                source_label="persisted latest observation",
            )
        if snapshot is not None:
            _validate_matching_hysteresis_transition(
                current_hysteresis_transition=snapshot.hysteresis_transition,
                expected_hysteresis_transition=resolved_hysteresis_transition,
                source_label="persisted latest evaluation snapshot",
            )
    elif observation is not None:
        resolved_hysteresis_transition = _resolved_hysteresis_transition(
            current_significance_status=observation.alert_classification,
            current_hysteresis_transition=observation.hysteresis_transition,
            previous_significance_status=None,
            source_label="persisted latest observation",
        )
        if snapshot is not None:
            _validate_matching_hysteresis_transition(
                current_hysteresis_transition=snapshot.hysteresis_transition,
                expected_hysteresis_transition=resolved_hysteresis_transition,
                source_label="persisted latest evaluation snapshot",
            )
    elif snapshot is not None:
        _resolved_hysteresis_transition(
            current_significance_status=snapshot.significance_status,
            current_hysteresis_transition=snapshot.hysteresis_transition,
            previous_significance_status=None,
            source_label="persisted latest evaluation snapshot",
        )
    if observation is None or snapshot is None or not entries:
        return
    latest_entry = entries[0].artifact
    _validate_monitor_definition_evaluation_persistence_pair(observation, snapshot, latest_entry)


def _validate_latest_observation_history_alignment(
    observation: MonitorDefinitionObservationArtifact,
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
) -> None:
    if observation.monitor_definition_id != entry.monitor_definition_id:
        raise MonitorDefinitionPersistenceError(
            "observation monitor_definition_id must match evaluation history entry"
        )
    if observation.monitor_id != entry.monitor_id:
        raise MonitorDefinitionPersistenceError(
            "observation monitor_id must match evaluation history entry"
        )
    if observation.benchmark_symbol != entry.benchmark_symbol:
        raise MonitorDefinitionPersistenceError(
            "observation benchmark_symbol must match evaluation history entry"
        )
    if observation.evaluated_at != entry.evaluated_at:
        raise MonitorDefinitionPersistenceError(
            "observation evaluated_at must match evaluation history entry"
        )
    if observation.observation_status != entry.observation_status:
        raise MonitorDefinitionPersistenceError(
            "observation observation_status must match evaluation history entry"
        )
    if observation.cause_code != entry.cause_code:
        raise MonitorDefinitionPersistenceError(
            "observation cause_code must match evaluation history entry"
        )
    if observation.alert_classification != entry.significance_status:
        raise MonitorDefinitionPersistenceError(
            "observation alert_classification must match evaluation history entry"
        )
    if (
        observation.hysteresis_transition is not None
        and entry.hysteresis_transition is not None
        and observation.hysteresis_transition != entry.hysteresis_transition
    ):
        raise MonitorDefinitionPersistenceError(
            "observation hysteresis_transition must match evaluation history entry"
        )


def _canonical_monitor_definition_id_from_payload(payload: object) -> str:
    return f"monitor_definition_{_fingerprint(payload)[:16]}"


def _canonical_monitor_definition_history_entry_id_from_payload(payload: object) -> str:
    return f"monitor_definition_history_{_fingerprint(payload)[:16]}"


def _canonical_monitor_definition_observation_id_from_payload(payload: object) -> str:
    return f"monitor_definition_observation_{_fingerprint(payload)[:16]}"


def _canonical_validation_payload_from_artifact(artifact: MonitorDefinitionArtifact) -> dict[str, Any]:
    return artifact.model_dump(mode="json", exclude={"monitor_definition_id", "fingerprint"})


def _canonical_validation_payload_from_persisted_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key not in {"monitor_definition_id", "fingerprint"}}


def _canonical_validation_payload_from_evaluation_history_entry(
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
) -> dict[str, Any]:
    return entry.model_dump(mode="json", exclude={"history_entry_id"})


def _canonical_validation_payload_from_observation(
    observation: MonitorDefinitionObservationArtifact,
) -> dict[str, Any]:
    return observation.model_dump(mode="json", exclude={"observation_id"})


def _canonical_validation_payload_from_persisted_evaluation_history_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "history_entry_id"}


def _canonical_validation_payload_from_persisted_observation_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {key: value for key, value in payload.items() if key != "observation_id"}


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


def _alert_history_queue_row_from_candidate(
    candidate: PersistedMonitorDefinitionAlertHistoryQueueCandidate,
) -> MonitorDefinitionAlertHistoryQueueRow:
    artifact = candidate.definition_artifact
    history_entry = candidate.history_entry.artifact
    snapshot = candidate.latest_snapshot.artifact
    resolved_hysteresis_transition = cast(
        MonitorDefinitionHysteresisTransition | None,
        history_entry.hysteresis_transition,
    )
    if candidate.latest_for_monitor_definition:
        if history_entry.evaluated_at != snapshot.evaluated_at:
            raise MonitorDefinitionIntegrityValidationError(
                "monitor definition alert history queue latest row evaluated_at must match the canonical latest snapshot"
            )
        if history_entry.observation_status != snapshot.outcome_status:
            raise MonitorDefinitionIntegrityValidationError(
                "monitor definition alert history queue latest row outcome_status must match the canonical latest snapshot"
            )
        if history_entry.cause_code != snapshot.cause_code:
            raise MonitorDefinitionIntegrityValidationError(
                "monitor definition alert history queue latest row cause_code must match the canonical latest snapshot"
            )
        if history_entry.significance_status != snapshot.significance_status:
            raise MonitorDefinitionIntegrityValidationError(
                "monitor definition alert history queue latest row significance_status must match the canonical latest snapshot"
            )
        resolved_hysteresis_transition = cast(
            MonitorDefinitionHysteresisTransition,
            _resolved_hysteresis_transition(
                current_significance_status=history_entry.significance_status,
                current_hysteresis_transition=history_entry.hysteresis_transition,
                previous_significance_status=None,
                source_label="persisted latest evaluation history entry",
            ),
        )
        _validate_matching_hysteresis_transition(
            current_hysteresis_transition=snapshot.hysteresis_transition,
            expected_hysteresis_transition=resolved_hysteresis_transition,
            source_label="persisted latest evaluation snapshot",
        )
    return MonitorDefinitionAlertHistoryQueueRow(
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_definition_fingerprint=artifact.fingerprint,
        monitor_definition_schema_version=artifact.schema_version,
        history_entry_id=history_entry.history_entry_id,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        review_scope=artifact.review_scope,
        evaluation_mode=artifact.evaluation_mode,
        evaluated_at=history_entry.evaluated_at,
        outcome_status=history_entry.observation_status,
        cause_code=history_entry.cause_code,
        significance_status=history_entry.significance_status,
        hysteresis_transition=resolved_hysteresis_transition,
        latest_for_monitor_definition=candidate.latest_for_monitor_definition,
        reason=history_entry.reason,
        review_handoff=MonitorDefinitionEvaluationHistoryReviewHandoff(
            monitor_definition_id=artifact.monitor_definition_id,
            history_entry_id=history_entry.history_entry_id,
            monitor_id=artifact.monitor_id,
            benchmark_symbol=artifact.benchmark_symbol,
        ),
    )


def _recovered_alert_review_queue_row_from_candidate(
    candidate: PersistedMonitorDefinitionRecoveredAlertReviewQueueCandidate,
) -> MonitorDefinitionRecoveredAlertReviewQueueRow:
    artifact = candidate.definition_artifact
    latest_observation = candidate.latest_observation
    latest_snapshot = candidate.latest_snapshot.artifact
    latest_history_entry = candidate.latest_history_entry.artifact
    recovered_from_entry = candidate.recovered_from_history_entry.artifact
    _validate_monitor_definition_evaluation_persistence_pair(
        latest_observation,
        latest_snapshot,
        latest_history_entry,
    )
    if latest_history_entry.significance_status != "informational":
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition recovered alert review queue latest history entry must be informational"
        )
    if recovered_from_entry.significance_status == "informational":
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition recovered alert review queue recovered_from history entry must be alert-eligible"
        )
    if recovered_from_entry.evaluated_at >= latest_history_entry.evaluated_at:
        raise MonitorDefinitionIntegrityValidationError(
            "monitor definition recovered alert review queue recovered_from history entry must precede the latest informational history entry"
        )
    return MonitorDefinitionRecoveredAlertReviewQueueRow(
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_definition_fingerprint=artifact.fingerprint,
        monitor_definition_schema_version=artifact.schema_version,
        observation_id=latest_observation.observation_id,
        latest_history_entry_id=latest_history_entry.history_entry_id,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        review_scope=artifact.review_scope,
        evaluation_mode=artifact.evaluation_mode,
        evaluated_at=latest_observation.evaluated_at,
        observation_status=latest_observation.observation_status,
        cause_code=latest_observation.cause_code,
        alert_classification=latest_observation.alert_classification,
        hysteresis_transition=latest_observation.hysteresis_transition,
        recency_status=_latest_observation_recency(latest_observation.evaluated_at),
        reason=latest_observation.reason,
        alert_episode=candidate.alert_episode,
        recovered_from=MonitorDefinitionRecoveredAlertReviewQueueRecoveredFrom(
            history_entry_id=recovered_from_entry.history_entry_id,
            evaluated_at=recovered_from_entry.evaluated_at,
            outcome_status=recovered_from_entry.observation_status,
            cause_code=recovered_from_entry.cause_code,
            significance_status=recovered_from_entry.significance_status,
            reason=recovered_from_entry.reason,
        ),
        timeline_handoff=MonitorDefinitionAlertReviewTimelineOpenHandoff(
            monitor_definition_id=artifact.monitor_definition_id,
            observation_id=latest_observation.observation_id,
            monitor_id=artifact.monitor_id,
            benchmark_symbol=artifact.benchmark_symbol,
        ),
    )


def _active_alert_episode_inbox_row_from_candidate(
    candidate: PersistedMonitorDefinitionActiveAlertEpisodeInboxCandidate,
) -> MonitorDefinitionActiveAlertEpisodeInboxRow:
    artifact = candidate.definition_artifact
    episode_row = candidate.episode_row
    if episode_row.monitor_definition_id != artifact.monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "active alert episode inbox row monitor_definition_id does not match persisted monitor definition"
        )
    if episode_row.monitor_definition_fingerprint != artifact.fingerprint:
        raise MonitorDefinitionIntegrityValidationError(
            "active alert episode inbox row fingerprint does not match persisted monitor definition"
        )
    if episode_row.monitor_definition_schema_version != artifact.schema_version:
        raise MonitorDefinitionIntegrityValidationError(
            "active alert episode inbox row schema_version does not match persisted monitor definition"
        )
    if episode_row.monitor_id != artifact.monitor_id:
        raise MonitorDefinitionIntegrityValidationError(
            "active alert episode inbox row monitor_id does not match persisted monitor definition"
        )
    if episode_row.benchmark_symbol != artifact.benchmark_symbol:
        raise MonitorDefinitionIntegrityValidationError(
            "active alert episode inbox row benchmark_symbol does not match persisted monitor definition"
        )
    return MonitorDefinitionActiveAlertEpisodeInboxRow(
        review_scope=artifact.review_scope,
        evaluation_mode=artifact.evaluation_mode,
        alert_episode=episode_row,
    )


def _build_latest_alert_episode(
    *,
    monitor_definition_id: str,
    observation: MonitorDefinitionObservationArtifact | None,
    history_entries: list[PersistedMonitorDefinitionEvaluationHistoryEntry],
) -> MonitorDefinitionAlertEpisode | None:
    if observation is None or not history_entries:
        return None
    latest_entry = history_entries[0].artifact
    if latest_entry.monitor_definition_id != monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "alert episode latest history entry monitor_definition_id does not match requested definition"
        )
    if observation.monitor_definition_id != monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "alert episode latest observation monitor_definition_id does not match requested definition"
        )
    latest_hysteresis_transition = _resolved_latest_persisted_hysteresis_transition(
        observation=observation,
        snapshot=None,
        history_entries=history_entries,
    )
    latest_history_entry_transition = _resolved_history_entry_hysteresis_transition(
        history_entries=history_entries,
        index=0,
    )
    episode_entries = _build_latest_alert_episode_entry_lineage(
        monitor_definition_id=monitor_definition_id,
        history_entries=history_entries,
    )
    if not episode_entries:
        return None
    started_entry = episode_entries[0]
    latest_contributing_observation = MonitorDefinitionAlertEpisodeLatestContributingObservation(
        observation_id=observation.observation_id,
        evaluated_at=observation.evaluated_at,
        observation_status=observation.observation_status,
        cause_code=observation.cause_code,
        alert_classification=observation.alert_classification,
    )
    if latest_entry.significance_status == "informational":
        if latest_hysteresis_transition != "recover":
            if latest_hysteresis_transition == "no_op":
                return None
            raise MonitorDefinitionIntegrityValidationError(
                "recovered alert episode latest observation hysteresis_transition must remain recover"
            )
        recovered_from_entry = _alert_episode_recovered_from_entry(episode_entries)
        if observation.evaluated_at <= recovered_from_entry.evaluated_at:
            raise MonitorDefinitionIntegrityValidationError(
                "alert episode recovered observation must follow the recovered_from history entry"
            )
        return MonitorDefinitionAlertEpisode(
            monitor_definition_id=monitor_definition_id,
            episode_id=_alert_episode_id(
                monitor_definition_id=monitor_definition_id,
                started_at=started_entry.evaluated_at,
                recovered_from_history_entry_id=recovered_from_entry.history_entry_id,
            ),
            episode_status="recovered",
            started_at=started_entry.evaluated_at,
            ended_at=observation.evaluated_at,
            hysteresis_transition=latest_hysteresis_transition,
            source_precedence=ALERT_EPISODE_SOURCE_PRECEDENCE,
            latest_contributing_observation=latest_contributing_observation,
            recovery_basis=MonitorDefinitionAlertEpisodeRecoveryBasis(
                recovered_from_history_entry_id=recovered_from_entry.history_entry_id,
                recovered_from_evaluated_at=recovered_from_entry.evaluated_at,
                recovered_from_outcome_status=recovered_from_entry.observation_status,
                recovered_from_cause_code=recovered_from_entry.cause_code,
                recovered_from_significance_status=recovered_from_entry.significance_status,
            ),
        )
    if latest_history_entry_transition not in {"open", "remain_open"}:
        raise MonitorDefinitionIntegrityValidationError(
            "active alert episode latest observation hysteresis_transition must remain open or remain_open"
        )
    active_hysteresis_transition = cast(
        MonitorDefinitionHysteresisTransition,
        latest_history_entry_transition,
    )
    if observation.evaluated_at != latest_entry.evaluated_at:
        raise MonitorDefinitionIntegrityValidationError(
            "active alert episode latest contributing observation must match the latest persisted alert history entry"
        )
    return MonitorDefinitionAlertEpisode(
        monitor_definition_id=monitor_definition_id,
        episode_id=_alert_episode_id(
            monitor_definition_id=monitor_definition_id,
            started_at=started_entry.evaluated_at,
            recovered_from_history_entry_id=None,
        ),
        episode_status="active",
        started_at=started_entry.evaluated_at,
        ended_at=None,
        hysteresis_transition=active_hysteresis_transition,
        source_precedence=ALERT_EPISODE_SOURCE_PRECEDENCE,
        latest_contributing_observation=latest_contributing_observation,
        recovery_basis=None,
    )


def _build_latest_alert_episode_entry_lineage(
    *,
    monitor_definition_id: str,
    history_entries: list[PersistedMonitorDefinitionEvaluationHistoryEntry],
) -> list[MonitorDefinitionEvaluationHistoryEntryArtifact]:
    if not history_entries:
        return []
    latest_entry = history_entries[0].artifact
    if latest_entry.significance_status == "informational":
        lineage: list[MonitorDefinitionEvaluationHistoryEntryArtifact] = [latest_entry]
        previous_evaluated_at = latest_entry.evaluated_at
        found_alert_eligible = False
        for persisted in history_entries[1:]:
            entry = persisted.artifact
            if entry.monitor_definition_id != monitor_definition_id:
                raise MonitorDefinitionIntegrityValidationError(
                    "alert episode history entry monitor_definition_id does not match requested definition"
                )
            if entry.evaluated_at >= previous_evaluated_at:
                raise MonitorDefinitionIntegrityValidationError(
                    "alert episode history entries must remain newest-first by evaluated_at"
                )
            lineage.append(entry)
            previous_evaluated_at = entry.evaluated_at
            if entry.significance_status != "informational":
                found_alert_eligible = True
                continue
            if found_alert_eligible:
                lineage.pop()
                break
        if not found_alert_eligible:
            return []
        lineage.reverse()
        return lineage
    lineage: list[MonitorDefinitionEvaluationHistoryEntryArtifact] = []
    previous_evaluated_at: datetime | None = None
    for persisted in reversed(history_entries):
        entry = persisted.artifact
        if entry.monitor_definition_id != monitor_definition_id:
            raise MonitorDefinitionIntegrityValidationError(
                "alert episode history entry monitor_definition_id does not match requested definition"
            )
        if previous_evaluated_at is not None and entry.evaluated_at <= previous_evaluated_at:
            raise MonitorDefinitionIntegrityValidationError(
                "alert episode history entries must remain oldest-first within the active lineage"
            )
        if entry.significance_status == "informational":
            lineage = []
            previous_evaluated_at = None
            continue
        lineage.append(entry)
        previous_evaluated_at = entry.evaluated_at
    return lineage


def _alert_episode_recovered_from_entry(
    episode_entries: list[MonitorDefinitionEvaluationHistoryEntryArtifact],
) -> MonitorDefinitionEvaluationHistoryEntryArtifact:
    if len(episode_entries) < 2:
        raise MonitorDefinitionIntegrityValidationError(
            "recovered alert episode requires alert-eligible history before the recovery history entry"
        )
    recovered_from_entry = episode_entries[-2]
    recovery_entry = episode_entries[-1]
    if recovery_entry.significance_status != "informational":
        raise MonitorDefinitionIntegrityValidationError(
            "recovered alert episode latest history entry must be informational"
        )
    if recovered_from_entry.significance_status == "informational":
        raise MonitorDefinitionIntegrityValidationError(
            "recovered alert episode recovered_from history entry must remain alert-eligible"
        )
    if recovered_from_entry.evaluated_at >= recovery_entry.evaluated_at:
        raise MonitorDefinitionIntegrityValidationError(
            "recovered alert episode recovered_from history entry must precede the recovery history entry"
        )
    return recovered_from_entry


def _alert_episode_id(
    *,
    monitor_definition_id: str,
    started_at: datetime,
    recovered_from_history_entry_id: str | None,
) -> str:
    payload = {
        "monitor_definition_id": monitor_definition_id,
        "started_at": started_at.isoformat(),
        "recovered_from_history_entry_id": recovered_from_history_entry_id,
    }
    return f"monitor_definition_alert_episode_{_fingerprint(payload)[:16]}"


def _build_alert_episode_history_rows(
    *,
    definition_artifact: MonitorDefinitionArtifact,
    observation: MonitorDefinitionObservationArtifact | None,
    history_entries: list[PersistedMonitorDefinitionEvaluationHistoryEntry],
) -> list[MonitorDefinitionAlertEpisodeHistoryRow]:
    if not history_entries:
        return []
    if observation is None:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted alert episode history requires an authoritative latest observation"
        )
    latest_episode = _build_latest_alert_episode(
        monitor_definition_id=definition_artifact.monitor_definition_id,
        observation=observation,
        history_entries=history_entries,
    )
    segments = _build_alert_episode_history_segments(
        monitor_definition_id=definition_artifact.monitor_definition_id,
        history_entries=history_entries,
    )
    if latest_episode is None:
        if segments:
            raise MonitorDefinitionIntegrityValidationError(
                "persisted alert episode history segments are ambiguous without an authoritative latest episode"
            )
        return []
    rows: list[MonitorDefinitionAlertEpisodeHistoryRow] = []
    recovered_row_consumed = False
    for index, segment in enumerate(segments):
        latest_for_monitor_definition = index == 0
        terminal_entry = segment[-1]
        started_entry = segment[0]
        if latest_for_monitor_definition:
            if latest_episode.started_at != started_entry.evaluated_at:
                raise MonitorDefinitionIntegrityValidationError(
                    "latest alert episode started_at does not match persisted alert episode history"
                )
            if latest_episode.recovery_basis is None:
                if latest_episode.episode_status != "active":
                    raise MonitorDefinitionIntegrityValidationError(
                        "latest alert episode recovery basis is missing for a non-active lifecycle"
                    )
                if observation is None:
                    raise MonitorDefinitionIntegrityValidationError(
                        "active latest alert episode requires an authoritative latest observation"
                    )
                row_artifact = MonitorDefinitionAlertEpisodeRecordArtifact(
                    episode_id=latest_episode.episode_id,
                    monitor_definition_id=definition_artifact.monitor_definition_id,
                    monitor_definition_fingerprint=definition_artifact.fingerprint,
                    monitor_definition_schema_version=definition_artifact.schema_version,
                    monitor_id=definition_artifact.monitor_id,
                    benchmark_symbol=definition_artifact.benchmark_symbol,
                    lifecycle_status="open",
                    latest_for_monitor_definition=True,
                    started_at=latest_episode.started_at,
                    ended_at=None,
                    latest_event_at=latest_episode.latest_contributing_observation.evaluated_at,
                    hysteresis_transition=latest_episode.hysteresis_transition,
                    source_precedence=ALERT_EPISODE_SOURCE_PRECEDENCE,
                    latest_contributing_observation=latest_episode.latest_contributing_observation,
                    recovery_basis=None,
                    terminal_history_entry_id=terminal_entry.history_entry_id,
                    timeline_handoff=MonitorDefinitionAlertEpisodeHistoryTimelineHandoff(
                        monitor_definition_id=definition_artifact.monitor_definition_id,
                        selected_event_kind="latest_observation_event",
                        observation_id=latest_episode.latest_contributing_observation.observation_id,
                        monitor_id=definition_artifact.monitor_id,
                        benchmark_symbol=definition_artifact.benchmark_symbol,
                    ),
                )
                rows.append(
                    MonitorDefinitionAlertEpisodeHistoryRow.model_validate(
                        row_artifact.model_dump(mode="json")
                    )
                )
                continue
            if latest_episode.episode_status != "recovered":
                raise MonitorDefinitionIntegrityValidationError(
                    "latest alert episode lifecycle is unsupported for persisted alert episode history"
                )
            row_artifact = MonitorDefinitionAlertEpisodeRecordArtifact(
                episode_id=latest_episode.episode_id,
                monitor_definition_id=definition_artifact.monitor_definition_id,
                monitor_definition_fingerprint=definition_artifact.fingerprint,
                monitor_definition_schema_version=definition_artifact.schema_version,
                monitor_id=definition_artifact.monitor_id,
                benchmark_symbol=definition_artifact.benchmark_symbol,
                lifecycle_status="recovered",
                latest_for_monitor_definition=True,
                started_at=latest_episode.started_at,
                ended_at=latest_episode.ended_at,
                latest_event_at=latest_episode.latest_contributing_observation.evaluated_at,
                hysteresis_transition=latest_episode.hysteresis_transition,
                source_precedence=ALERT_EPISODE_SOURCE_PRECEDENCE,
                latest_contributing_observation=latest_episode.latest_contributing_observation,
                recovery_basis=latest_episode.recovery_basis,
                terminal_history_entry_id=terminal_entry.history_entry_id,
                timeline_handoff=MonitorDefinitionAlertEpisodeHistoryTimelineHandoff(
                    monitor_definition_id=definition_artifact.monitor_definition_id,
                    selected_event_kind="latest_observation_event",
                    observation_id=latest_episode.latest_contributing_observation.observation_id,
                    monitor_id=definition_artifact.monitor_id,
                    benchmark_symbol=definition_artifact.benchmark_symbol,
                ),
            )
            rows.append(
                MonitorDefinitionAlertEpisodeHistoryRow.model_validate(
                    row_artifact.model_dump(mode="json")
                )
            )
            recovered_row_consumed = True
            continue

        if latest_episode.recovery_basis is not None and not recovered_row_consumed:
            raise MonitorDefinitionIntegrityValidationError(
                "recovered latest alert episode must be emitted before closed persisted alert episode history rows"
            )
        recovered_from_entry = terminal_entry
        latest_contributing_entry = terminal_entry
        if terminal_entry.significance_status == "informational":
            if len(segment) < 2:
                raise MonitorDefinitionIntegrityValidationError(
                    "closed persisted alert episode history requires prior alert-eligible history"
                )
            recovered_from_entry = segment[-2]
            if recovered_from_entry.significance_status == "informational":
                raise MonitorDefinitionIntegrityValidationError(
                    "closed persisted alert episode recovery basis must remain alert-eligible"
                )
        latest_contributing_observation = MonitorDefinitionAlertEpisodeLatestContributingObservation(
            observation_id=_canonical_monitor_definition_observation_id_from_payload(
                _canonical_validation_payload_from_evaluation_history_entry_as_observation(latest_contributing_entry)
            ),
            evaluated_at=latest_contributing_entry.evaluated_at,
            observation_status=latest_contributing_entry.observation_status,
            cause_code=latest_contributing_entry.cause_code,
            alert_classification=latest_contributing_entry.significance_status,
        )
        row_artifact = MonitorDefinitionAlertEpisodeRecordArtifact(
            episode_id=_alert_episode_id(
                monitor_definition_id=definition_artifact.monitor_definition_id,
                started_at=started_entry.evaluated_at,
                recovered_from_history_entry_id=recovered_from_entry.history_entry_id,
            ),
            monitor_definition_id=definition_artifact.monitor_definition_id,
            monitor_definition_fingerprint=definition_artifact.fingerprint,
            monitor_definition_schema_version=definition_artifact.schema_version,
            monitor_id=definition_artifact.monitor_id,
            benchmark_symbol=definition_artifact.benchmark_symbol,
            lifecycle_status="closed",
            latest_for_monitor_definition=False,
            started_at=started_entry.evaluated_at,
            ended_at=latest_contributing_entry.evaluated_at,
            latest_event_at=latest_contributing_entry.evaluated_at,
            hysteresis_transition=latest_contributing_entry.hysteresis_transition,
            source_precedence=ALERT_EPISODE_SOURCE_PRECEDENCE,
            latest_contributing_observation=latest_contributing_observation,
            recovery_basis=MonitorDefinitionAlertEpisodeRecoveryBasis(
                recovered_from_history_entry_id=recovered_from_entry.history_entry_id,
                recovered_from_evaluated_at=recovered_from_entry.evaluated_at,
                recovered_from_outcome_status=recovered_from_entry.observation_status,
                recovered_from_cause_code=recovered_from_entry.cause_code,
                recovered_from_significance_status=recovered_from_entry.significance_status,
            ),
            terminal_history_entry_id=latest_contributing_entry.history_entry_id,
            timeline_handoff=MonitorDefinitionAlertEpisodeHistoryTimelineHandoff(
                monitor_definition_id=definition_artifact.monitor_definition_id,
                selected_event_kind="evaluation_history_event",
                history_entry_id=latest_contributing_entry.history_entry_id,
                monitor_id=definition_artifact.monitor_id,
                benchmark_symbol=definition_artifact.benchmark_symbol,
            ),
        )
        rows.append(
            MonitorDefinitionAlertEpisodeHistoryRow.model_validate(
                row_artifact.model_dump(mode="json")
            )
        )
    rows.sort(key=lambda row: (-row.latest_event_at.timestamp(), row.episode_id))
    previous_order: tuple[float, str] | None = None
    for row in rows:
        current_order = (row.latest_event_at.timestamp(), row.episode_id)
        if previous_order is not None and current_order > previous_order:
            raise MonitorDefinitionIntegrityValidationError(
                "monitor definition alert episode history ordering is ambiguous"
            )
        previous_order = current_order
    return rows


def _build_alert_episode_history_segments(
    *,
    monitor_definition_id: str,
    history_entries: list[PersistedMonitorDefinitionEvaluationHistoryEntry],
) -> list[list[MonitorDefinitionEvaluationHistoryEntryArtifact]]:
    segments: list[list[MonitorDefinitionEvaluationHistoryEntryArtifact]] = []
    current_segment: list[MonitorDefinitionEvaluationHistoryEntryArtifact] = []
    previous_evaluated_at: datetime | None = None
    for persisted in reversed(history_entries):
        entry = persisted.artifact
        if entry.monitor_definition_id != monitor_definition_id:
            raise MonitorDefinitionIntegrityValidationError(
                "alert episode history entry monitor_definition_id does not match requested definition"
            )
        if previous_evaluated_at is not None and entry.evaluated_at <= previous_evaluated_at:
            raise MonitorDefinitionIntegrityValidationError(
                "alert episode history entries must remain oldest-first within alert episode history segmentation"
            )
        previous_evaluated_at = entry.evaluated_at
        if entry.significance_status == "informational":
            if current_segment:
                current_segment.append(entry)
                segments.append(current_segment)
                current_segment = []
            continue
        current_segment.append(entry)
    if current_segment:
        segments.append(current_segment)
    segments.reverse()
    return segments


def _canonical_validation_payload_from_evaluation_history_entry_as_observation(
    entry: MonitorDefinitionEvaluationHistoryEntryArtifact,
) -> dict[str, Any]:
    payload = entry.model_dump(mode="json")
    payload.pop("history_entry_id", None)
    payload.pop("significance_status", None)
    payload["schema_version"] = "monitor_definition_observation_artifact_v1"
    payload["alert_classification"] = entry.significance_status
    return payload


def _latest_observation_alert_inbox_row_from_persisted_artifact(
    item: PersistedMonitorDefinitionArtifact,
    observation: PersistedMonitorDefinitionObservation,
) -> MonitorDefinitionLatestObservationAlertInboxRow:
    artifact = item.artifact
    observation_artifact = observation.artifact
    if observation_artifact.monitor_definition_id != artifact.monitor_definition_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation monitor_definition_id does not match persisted monitor definition"
        )
    if observation_artifact.monitor_definition_fingerprint != artifact.fingerprint:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation fingerprint does not match persisted monitor definition"
        )
    if observation_artifact.monitor_definition_schema_version != artifact.schema_version:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation schema_version does not match persisted monitor definition"
        )
    if observation_artifact.monitor_id != artifact.monitor_id:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation monitor_id does not match persisted monitor definition"
        )
    if observation_artifact.benchmark_symbol != artifact.benchmark_symbol:
        raise MonitorDefinitionIntegrityValidationError(
            "persisted monitor definition observation benchmark_symbol does not match persisted monitor definition"
        )
    return MonitorDefinitionLatestObservationAlertInboxRow(
        monitor_definition_id=artifact.monitor_definition_id,
        monitor_definition_fingerprint=artifact.fingerprint,
        monitor_definition_schema_version=artifact.schema_version,
        observation_id=observation_artifact.observation_id,
        monitor_id=artifact.monitor_id,
        benchmark_symbol=artifact.benchmark_symbol,
        review_scope=artifact.review_scope,
        evaluation_mode=artifact.evaluation_mode,
        evaluated_at=observation_artifact.evaluated_at,
        observation_status=observation_artifact.observation_status,
        cause_code=observation_artifact.cause_code,
        alert_classification=observation_artifact.alert_classification,
        hysteresis_transition=observation_artifact.hysteresis_transition,
        recency_status=_latest_observation_recency(observation_artifact.evaluated_at),
        reason=observation_artifact.reason,
        open_handoff=MonitorDefinitionObservationOpenHandoff(
            monitor_definition_id=artifact.monitor_definition_id,
            observation_id=observation_artifact.observation_id,
            monitor_id=artifact.monitor_id,
            benchmark_symbol=artifact.benchmark_symbol,
        ),
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
    if item.discovery_status.latest_observation is not None and item.discovery_status.latest_evaluation_snapshot is not None:
        _validate_monitor_definition_evaluation_persistence_pair(
            item.discovery_status.latest_observation.artifact,
            item.discovery_status.latest_evaluation_snapshot.artifact,
            MonitorDefinitionEvaluationHistoryEntryArtifact(
                history_entry_id="monitor_definition_history_alignment_probe",
                monitor_definition_id=item.discovery_status.latest_observation.artifact.monitor_definition_id,
                monitor_definition_fingerprint=item.discovery_status.latest_observation.artifact.monitor_definition_fingerprint,
                monitor_definition_schema_version=item.discovery_status.latest_observation.artifact.monitor_definition_schema_version,
                monitor_id=item.discovery_status.latest_observation.artifact.monitor_id,
                benchmark_symbol=item.discovery_status.latest_observation.artifact.benchmark_symbol,
                evaluation_mode=item.discovery_status.latest_observation.artifact.evaluation_mode,
                evaluated_at=item.discovery_status.latest_observation.artifact.evaluated_at,
                observation_status=item.discovery_status.latest_observation.artifact.observation_status,
                cause_code=item.discovery_status.latest_observation.artifact.cause_code,
                significance_status=item.discovery_status.latest_observation.artifact.alert_classification,
                hysteresis_transition=item.discovery_status.latest_observation.artifact.hysteresis_transition,
                source_precedence=EVALUATION_HISTORY_SOURCE_PRECEDENCE,
                reason=item.discovery_status.latest_observation.artifact.reason,
                thresholds=item.discovery_status.latest_observation.artifact.thresholds,
                benchmark_observation=item.discovery_status.latest_observation.artifact.benchmark_observation,
                portfolio_observation=item.discovery_status.latest_observation.artifact.portfolio_observation,
                active_observation=item.discovery_status.latest_observation.artifact.active_observation,
            ),
        )
    observation = item.discovery_status.latest_observation
    observation_summary = None
    if observation is not None:
        observation_summary = MonitorDefinitionLatestObservationSummary(
            observation_id=observation.artifact.observation_id,
            evaluated_at=observation.evaluated_at,
            observation_status=cast(MonitorDefinitionObservationStatus, observation.observation_status),
            cause_code=cast(MonitorDefinitionCanonicalCauseCode | None, observation.cause_code),
            alert_classification=cast(MonitorDefinitionLatestEvaluationSignificanceStatus, observation.alert_classification),
            hysteresis_transition=observation.artifact.hysteresis_transition,
            recency_status=_latest_observation_recency(observation.evaluated_at),
            source_precedence=LATEST_OBSERVATION_SOURCE_PRECEDENCE,
        )
    snapshot = item.discovery_status.latest_evaluation_snapshot
    snapshot_summary = None
    if snapshot is not None:
        snapshot_summary = MonitorDefinitionLatestEvaluationSnapshotSummary(
            evaluated_at=snapshot.evaluated_at,
            outcome_status=cast(MonitorDefinitionObservationStatus, snapshot.outcome_status),
            cause_code=cast(MonitorDefinitionCanonicalCauseCode | None, snapshot.cause_code),
            significance_status=cast(MonitorDefinitionLatestEvaluationSignificanceStatus, snapshot.significance_status),
            hysteresis_transition=snapshot.artifact.hysteresis_transition,
            recency_status=_latest_evaluation_snapshot_recency(snapshot.evaluated_at),
            source_precedence=LATEST_SNAPSHOT_SOURCE_PRECEDENCE,
        )
    return MonitorDefinitionStatusMetadata(
        status_source_precedence=DISCOVERY_STATUS_SOURCE_PRECEDENCE,
        latest_observation_status=item.discovery_status.latest_observation_status,
        latest_observation=observation_summary,
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


def _latest_observation_recency(
    evaluated_at: datetime,
) -> MonitorDefinitionLatestObservationRecency:
    return cast(
        MonitorDefinitionLatestObservationRecency,
        "recent" if datetime.now(UTC) - evaluated_at <= LATEST_EVALUATION_RECENCY_WINDOW else "stale",
    )


def _matches_discovery_filters(
    item: PersistedMonitorDefinitionArtifact,
    filters: MonitorDefinitionDiscoveryFilters,
) -> bool:
    observation = item.discovery_status.latest_observation
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
        filters.latest_observation_status is not None
        and filters.latest_observation_status != item.discovery_status.latest_observation_status
    ):
        return False
    if filters.latest_observation_observation_status is not None:
        if observation is None:
            return False
        if filters.latest_observation_observation_status != observation.observation_status:
            return False
    if filters.latest_observation_alert_classification is not None:
        if observation is None:
            return False
        if filters.latest_observation_alert_classification != observation.alert_classification:
            return False
    if filters.latest_observation_cause_code is not None:
        if observation is None:
            return False
        if filters.latest_observation_cause_code != observation.cause_code:
            return False
    if filters.latest_observation_recency is not None:
        if observation is None:
            return False
        if filters.latest_observation_recency != _latest_observation_recency(observation.evaluated_at):
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
    if filters.latest_evaluation_snapshot_cause_code is not None:
        if snapshot is None:
            return False
        if filters.latest_evaluation_snapshot_cause_code != snapshot.cause_code:
            return False
    return True
