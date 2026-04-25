from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, cast

from pydantic import ValidationError

from app.core.settings import get_settings
from app.schemas.research import (
    CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND,
    CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION,
    CrossSectionalResearchArtifact,
    CrossSectionalResearchCatalogResponse,
    CrossSectionalResearchCatalogRow,
    CrossSectionalResearchDiscoveryMetadata,
    CrossSectionalResearchDiscoveryFilters,
    CrossSectionalResearchRecentResponse,
    CrossSectionalResearchRecentRow,
)


class CrossSectionalResearchArtifactPersistenceError(ValueError):
    pass


class CrossSectionalResearchArtifactReadError(CrossSectionalResearchArtifactPersistenceError):
    pass


class CrossSectionalResearchArtifactMissingFileError(CrossSectionalResearchArtifactReadError):
    pass


class CrossSectionalResearchArtifactInvalidJsonError(CrossSectionalResearchArtifactReadError):
    pass


class CrossSectionalResearchArtifactNonObjectPayloadError(CrossSectionalResearchArtifactReadError):
    pass


class CrossSectionalResearchArtifactSchemaValidationError(CrossSectionalResearchArtifactReadError):
    pass


class CrossSectionalResearchArtifactIntegrityValidationError(CrossSectionalResearchArtifactReadError):
    pass


class CrossSectionalResearchArtifactStore:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.cross_sectional_research_artifact_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def artifact_path(self, artifact_id: str) -> Path:
        return self.base_dir / f"{_validated_artifact_id_key(artifact_id)}.json"

    def persist(self, artifact: CrossSectionalResearchArtifact) -> CrossSectionalResearchArtifact:
        if self.artifact_path(artifact.artifact_id).exists():
            existing_artifact = self.load(artifact.artifact_id)
            if existing_artifact.fingerprint != artifact.fingerprint:
                raise CrossSectionalResearchArtifactPersistenceError(
                    f"immutable cross-sectional research artifact conflict at {self.artifact_path(artifact.artifact_id)}"
                )
            return existing_artifact
        validated_artifact = validate_cross_sectional_research_artifact(
            artifact.model_copy(update={"persisted_at": _canonical_utc_now()})
        )
        self._write_once(
            self.artifact_path(validated_artifact.artifact_id),
            validated_artifact.model_dump(mode="json"),
        )
        return validated_artifact

    def load(self, artifact_id: str) -> CrossSectionalResearchArtifact:
        path = self.artifact_path(artifact_id)
        return _load_validated_artifact_from_path(path, hydrate_legacy_metadata=True)

    def list_catalog(
        self,
        *,
        filters: CrossSectionalResearchDiscoveryFilters,
    ) -> CrossSectionalResearchCatalogResponse:
        items = [_build_catalog_row(artifact) for artifact in self._iter_artifacts(filters=filters)]
        items.sort(key=lambda item: (item.recent_order_persisted_at, item.recent_order_artifact_id), reverse=True)
        return CrossSectionalResearchCatalogResponse(
            items=items,
            applied_filters=filters,
            metadata=CrossSectionalResearchDiscoveryMetadata(applied_filters=filters),
        )

    def list_recent(
        self,
        *,
        limit: int,
        filters: CrossSectionalResearchDiscoveryFilters,
    ) -> CrossSectionalResearchRecentResponse:
        if limit < 1:
            return CrossSectionalResearchRecentResponse(
                items=[],
                applied_filters=filters,
                metadata=CrossSectionalResearchDiscoveryMetadata(applied_filters=filters),
            )
        rows = [_build_recent_row(artifact) for artifact in self._iter_artifacts(filters=filters)]
        rows.sort(key=lambda item: (item.recent_order_persisted_at, item.recent_order_artifact_id), reverse=True)
        return CrossSectionalResearchRecentResponse(
            items=rows[:limit],
            applied_filters=filters,
            metadata=CrossSectionalResearchDiscoveryMetadata(applied_filters=filters),
        )

    def _iter_artifacts(self, *, filters: CrossSectionalResearchDiscoveryFilters) -> list[CrossSectionalResearchArtifact]:
        artifacts: list[CrossSectionalResearchArtifact] = []
        for path in sorted(self.base_dir.glob("cross_sectional_research_artifact_*.json")):
            validated_artifact = _load_validated_artifact_from_path(path, hydrate_legacy_metadata=False)
            if _matches_filters(validated_artifact, filters):
                artifacts.append(validated_artifact)
        return artifacts

    def _write_once(self, path: Path, payload: object) -> None:
        serialized = _canonical_json(payload)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise CrossSectionalResearchArtifactPersistenceError(
                    f"immutable cross-sectional research artifact conflict at {path}"
                )
            return
        path.write_text(serialized, encoding="utf-8")


def build_stable_cross_sectional_research_artifact(
    artifact: CrossSectionalResearchArtifact,
) -> CrossSectionalResearchArtifact:
    artifact_id, fingerprint = _stable_artifact_identity(
        artifact.model_dump(
            mode="json",
            exclude={"artifact_id", "fingerprint", "persisted_at"},
        )
    )
    return artifact.model_copy(update={"artifact_id": artifact_id, "fingerprint": fingerprint})


def persist_cross_sectional_research_artifact(
    artifact: CrossSectionalResearchArtifact,
    *,
    store: CrossSectionalResearchArtifactStore | None = None,
) -> CrossSectionalResearchArtifact:
    stable_artifact = build_stable_cross_sectional_research_artifact(artifact)
    return (store or CrossSectionalResearchArtifactStore()).persist(stable_artifact)


def load_cross_sectional_research_artifact(
    artifact_id: str,
    *,
    store: CrossSectionalResearchArtifactStore | None = None,
) -> CrossSectionalResearchArtifact:
    return (store or CrossSectionalResearchArtifactStore()).load(artifact_id)


def list_cross_sectional_research_catalog(
    *,
    filters: CrossSectionalResearchDiscoveryFilters,
    store: CrossSectionalResearchArtifactStore | None = None,
) -> CrossSectionalResearchCatalogResponse:
    return (store or CrossSectionalResearchArtifactStore()).list_catalog(filters=filters)


def list_recent_cross_sectional_research_artifacts(
    *,
    limit: int,
    filters: CrossSectionalResearchDiscoveryFilters,
    store: CrossSectionalResearchArtifactStore | None = None,
) -> CrossSectionalResearchRecentResponse:
    return (store or CrossSectionalResearchArtifactStore()).list_recent(limit=limit, filters=filters)


def validate_cross_sectional_research_artifact(
    artifact: CrossSectionalResearchArtifact,
    *,
    identity_payload_without_ids: object | None = None,
) -> CrossSectionalResearchArtifact:
    if artifact.artifact_kind != CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND:
        raise CrossSectionalResearchArtifactIntegrityValidationError("unsupported cross-sectional research artifact kind")
    if artifact.schema_version != CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION:
        raise CrossSectionalResearchArtifactSchemaValidationError("unsupported cross-sectional research schema_version")
    canonical_artifact_id, canonical_fingerprint = _stable_artifact_identity(
        identity_payload_without_ids
        if identity_payload_without_ids is not None
        else artifact.model_dump(
            mode="json",
            exclude={"artifact_id", "fingerprint", "persisted_at"},
        )
    )
    if artifact.artifact_id != canonical_artifact_id:
        raise CrossSectionalResearchArtifactIntegrityValidationError(
            "cross-sectional research artifact_id does not match canonical artifact content"
        )
    if artifact.fingerprint != canonical_fingerprint:
        raise CrossSectionalResearchArtifactIntegrityValidationError(
            "cross-sectional research fingerprint does not match canonical artifact content"
        )
    return artifact


def _validated_artifact_id_key(artifact_id: str) -> str:
    if not artifact_id.startswith("cross_sectional_research_artifact_"):
        raise CrossSectionalResearchArtifactIntegrityValidationError(
            "artifact_id must use the stable cross_sectional_research_artifact_ prefix"
        )
    if any(separator in artifact_id for separator in ("/", "\\")):
        raise CrossSectionalResearchArtifactIntegrityValidationError("artifact_id must be a stable storage key")
    return artifact_id


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CrossSectionalResearchArtifactMissingFileError(
            f"missing persisted cross-sectional research artifact file: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise CrossSectionalResearchArtifactInvalidJsonError(
            f"invalid persisted cross-sectional research artifact json: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise CrossSectionalResearchArtifactNonObjectPayloadError(
            f"persisted cross-sectional research artifact payload must be a json object: {path}"
        )
    return payload


def _validate_raw_schema(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != CROSS_SECTIONAL_RESEARCH_ARTIFACT_SCHEMA_VERSION:
        raise CrossSectionalResearchArtifactSchemaValidationError(
            "unsupported cross-sectional research schema_version"
        )
    if payload.get("artifact_kind") != CROSS_SECTIONAL_RESEARCH_ARTIFACT_KIND:
        raise CrossSectionalResearchArtifactSchemaValidationError(
            "unsupported cross-sectional research artifact kind"
        )


def _load_validated_artifact_from_path(
    path: Path,
    *,
    hydrate_legacy_metadata: bool,
) -> CrossSectionalResearchArtifact:
    payload = _read_json_object(path)
    _validate_raw_schema(payload)
    hydrated_payload = (
        _hydrate_legacy_cross_sectional_research_payload(payload)
        if hydrate_legacy_metadata
        else payload
    )
    try:
        artifact = CrossSectionalResearchArtifact.model_validate(hydrated_payload)
    except ValidationError as exc:
        detail = _validation_error_detail(exc)
        raise CrossSectionalResearchArtifactSchemaValidationError(
            f"persisted cross-sectional research artifact failed schema validation: {path}: {detail}"
        ) from exc
    identity_payload_without_ids = None
    if hydrate_legacy_metadata and hydrated_payload is not payload:
        identity_payload_without_ids = {
            key: value
            for key, value in payload.items()
            if key not in {"artifact_id", "fingerprint", "persisted_at"}
        }
    return validate_cross_sectional_research_artifact(
        artifact,
        identity_payload_without_ids=identity_payload_without_ids,
    )


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonical_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _fingerprint(payload: object) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _stable_artifact_identity(payload_without_ids: object) -> tuple[str, str]:
    fingerprint = _fingerprint(payload_without_ids)
    return (f"cross_sectional_research_artifact_{fingerprint[:16]}", fingerprint)


def _validation_error_detail(exc: ValidationError) -> str:
    if not exc.errors():
        return "schema validation error"
    error = exc.errors()[0]
    location = ".".join(str(part) for part in error.get("loc", ()))
    message = error.get("msg", "schema validation error")
    if isinstance(message, str) and message.startswith("Value error, "):
        message = message[len("Value error, "):]
    if location:
        return f"{location}: {message}"
    return str(message)


def _matches_filters(
    artifact: CrossSectionalResearchArtifact,
    filters: CrossSectionalResearchDiscoveryFilters,
) -> bool:
    provenance_metadata = artifact.provenance_metadata_v1
    if filters.artifact_kind is not None and artifact.artifact_kind != filters.artifact_kind:
        return False
    if filters.schema_version is not None and artifact.schema_version != filters.schema_version:
        return False
    if filters.methodology_id is not None and artifact.methodology_id != filters.methodology_id:
        return False
    if filters.dataset_version is not None and artifact.dataset_version != filters.dataset_version:
        return False
    if filters.universe_definition is not None and artifact.universe_definition != filters.universe_definition:
        return False
    if filters.benchmark_symbol is not None and artifact.benchmark.benchmark_symbol != filters.benchmark_symbol:
        return False
    if filters.rebalance_date is not None and artifact.request.rebalance_date != filters.rebalance_date:
        return False
    if filters.as_of_date is not None and artifact.request.as_of_date != filters.as_of_date:
        return False
    if filters.holdout_start_date is not None and artifact.request.holdout_start_date != filters.holdout_start_date:
        return False
    if (
        filters.methodology_family_id is not None
        and artifact.methodology_metadata_v1.methodology_family_id != filters.methodology_family_id
    ):
        return False
    if (
        filters.methodology_family_version is not None
        and artifact.methodology_metadata_v1.methodology_family_version != filters.methodology_family_version
    ):
        return False
    if (
        filters.active_methodology_version is not None
        and artifact.methodology_metadata_v1.active_methodology_version != filters.active_methodology_version
    ):
        return False
    if (
        filters.alpha_package_version is not None
        and artifact.methodology_metadata_v1.alpha_package_version != filters.alpha_package_version
    ):
        return False
    if (
        filters.alpha_methodology_id is not None
        and artifact.methodology_metadata_v1.alpha_methodology_id != filters.alpha_methodology_id
    ):
        return False
    if (
        filters.alpha_input_contract_id is not None
        and artifact.methodology_metadata_v1.alpha_input_contract_id != filters.alpha_input_contract_id
    ):
        return False
    if filters.score_basis is not None and artifact.methodology_metadata_v1.score_basis != filters.score_basis:
        return False
    if (
        filters.benchmark_role is not None
        and artifact.methodology_metadata_v1.benchmark_role != filters.benchmark_role
    ):
        return False
    if (
        filters.partition_rule is not None
        and artifact.methodology_metadata_v1.partition_rule != filters.partition_rule
    ):
        return False
    if (
        filters.output_shape is not None
        and artifact.methodology_metadata_v1.output_shape != filters.output_shape
    ):
        return False
    if (
        filters.artifact_status is not None
        and artifact.status_metadata_v1.artifact_status != filters.artifact_status
    ):
        return False
    if (
        filters.diagnostics_status is not None
        and artifact.status_metadata_v1.diagnostics_status != filters.diagnostics_status
    ):
        return False
    if (
        filters.coverage_status is not None
        and artifact.status_metadata_v1.coverage_status != filters.coverage_status
    ):
        return False
    if (
        filters.input_source_kind is not None
        and provenance_metadata is not None
        and provenance_metadata.input_source_kind != filters.input_source_kind
    ):
        return False
    if (
        filters.replay_provenance_status is not None
        and provenance_metadata is not None
        and provenance_metadata.replay_provenance_status != filters.replay_provenance_status
    ):
        return False
    if (
        filters.benchmark_source_kind is not None
        and provenance_metadata is not None
        and provenance_metadata.benchmark_source_kind != filters.benchmark_source_kind
    ):
        return False
    if (
        filters.alpha_source_kind is not None
        and provenance_metadata is not None
        and provenance_metadata.alpha_source_kind != filters.alpha_source_kind
    ):
        return False
    return True


def _build_catalog_row(artifact: CrossSectionalResearchArtifact) -> CrossSectionalResearchCatalogRow:
    return CrossSectionalResearchCatalogRow(
        artifact_id=artifact.artifact_id,
        fingerprint=artifact.fingerprint,
        artifact_kind=artifact.artifact_kind,
        schema_version=artifact.schema_version,
        methodology_id=artifact.methodology_id,
        methodology_metadata_v1=artifact.methodology_metadata_v1,
        status_metadata_v1=artifact.status_metadata_v1,
        provenance_metadata_v1=artifact.provenance_metadata_v1,
        dataset_version=artifact.dataset_version,
        universe_definition=artifact.universe_definition,
        benchmark_symbol=artifact.benchmark.benchmark_symbol,
        as_of_date=artifact.request.as_of_date,
        rebalance_date=artifact.request.rebalance_date,
        holdout_start_date=artifact.request.holdout_start_date,
        recent_order_persisted_at=artifact.persisted_at,
        recent_order_artifact_id=artifact.artifact_id,
        universe_size=len(artifact.request.universe_symbols),
        walk_forward_sample_count=artifact.walk_forward_summary.sample_count,
        holdout_sample_count=artifact.holdout_summary.sample_count,
        alpha_diagnostics_status=artifact.provenance.alpha_diagnostics_status,
    )


def _build_recent_row(artifact: CrossSectionalResearchArtifact) -> CrossSectionalResearchRecentRow:
    return CrossSectionalResearchRecentRow(
        artifact_id=artifact.artifact_id,
        fingerprint=artifact.fingerprint,
        methodology_id=artifact.methodology_id,
        methodology_metadata_v1=artifact.methodology_metadata_v1,
        status_metadata_v1=artifact.status_metadata_v1,
        provenance_metadata_v1=artifact.provenance_metadata_v1,
        dataset_version=artifact.dataset_version,
        universe_definition=artifact.universe_definition,
        benchmark_symbol=artifact.benchmark.benchmark_symbol,
        recent_order_persisted_at=artifact.persisted_at,
        recent_order_artifact_id=artifact.artifact_id,
        rebalance_date=artifact.request.rebalance_date,
        as_of_date=artifact.request.as_of_date,
        holdout_start_date=artifact.request.holdout_start_date,
        universe_size=len(artifact.request.universe_symbols),
        walk_forward_sample_count=artifact.walk_forward_summary.sample_count,
        holdout_sample_count=artifact.holdout_summary.sample_count,
    )


def _hydrate_legacy_cross_sectional_research_payload(payload: dict[str, Any]) -> dict[str, Any]:
    hydrated = dict(payload)
    request_value = hydrated.get("request")
    provenance_value = hydrated.get("provenance")
    request: dict[str, Any] = cast(dict[str, Any], request_value) if isinstance(request_value, dict) else {}
    provenance: dict[str, Any] = cast(dict[str, Any], provenance_value) if isinstance(provenance_value, dict) else {}

    if "status_metadata_v1" not in hydrated:
        diagnostics_status = provenance.get("alpha_diagnostics_status", "unknown")
        if diagnostics_status == "ok":
            artifact_status = "complete"
        elif diagnostics_status == "invalid":
            artifact_status = "degraded"
        else:
            artifact_status = "unknown"
        complete_coverage_ratio = provenance.get("complete_coverage_ratio")
        if complete_coverage_ratio == 1 or complete_coverage_ratio == 1.0:
            coverage_status = "complete"
        elif isinstance(complete_coverage_ratio, (int, float)):
            coverage_status = "partial"
        else:
            coverage_status = "unknown"
        hydrated["status_metadata_v1"] = {
            "artifact_status": artifact_status,
            "diagnostics_status": diagnostics_status,
            "coverage_status": coverage_status,
        }

    if "provenance_metadata_v1" not in hydrated:
        replay_id = request.get("replay_id")
        source_name = request.get("source_name")
        if replay_id is not None:
            input_source_kind = "replay_snapshot_input"
            replay_provenance_status = "present"
        elif source_name == "direct_snapshot_input":
            input_source_kind = "direct_snapshot_input"
            replay_provenance_status = "absent"
        elif isinstance(source_name, str) and source_name.strip():
            input_source_kind = "backend_owned_other"
            replay_provenance_status = "absent"
        else:
            input_source_kind = "unknown"
            replay_provenance_status = "unknown"
        hydrated["provenance_metadata_v1"] = {
            "input_source_kind": input_source_kind,
            "replay_provenance_status": replay_provenance_status,
            "benchmark_source_kind": "request_benchmark_reference",
            "alpha_source_kind": "optimizer_alpha_package",
        }

    return hydrated
