from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.settings import get_settings
from app.schemas.construction import ConstructionArtifact


class ConstructionArtifactPersistenceError(ValueError):
    pass


class ConstructionArtifactReadError(ConstructionArtifactPersistenceError):
    pass


class ConstructionArtifactMissingFileError(ConstructionArtifactReadError):
    pass


class ConstructionArtifactInvalidJsonError(ConstructionArtifactReadError):
    pass


class ConstructionArtifactNonObjectPayloadError(ConstructionArtifactReadError):
    pass


class ConstructionArtifactSchemaValidationError(ConstructionArtifactReadError):
    pass


class ConstructionArtifactIntegrityValidationError(ConstructionArtifactReadError):
    pass


@dataclass(frozen=True)
class RawPersistedConstructionArtifact:
    artifact_path: Path
    payload: dict[str, Any]


class ConstructionArtifactStore:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.construction_artifact_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def artifact_path(self, artifact_id: str) -> Path:
        return self.base_dir / f"{_validated_artifact_id_key(artifact_id)}.json"

    def persist(self, artifact: ConstructionArtifact) -> ConstructionArtifact:
        validated_artifact = validate_construction_artifact(artifact)
        self._write_once(
            self.artifact_path(validated_artifact.artifact_id),
            validated_artifact.model_dump(mode="json"),
        )
        return validated_artifact

    def load(self, artifact_id: str) -> ConstructionArtifact:
        raw = self.load_raw(artifact_id)
        try:
            artifact = ConstructionArtifact.model_validate(
                _normalize_legacy_construction_artifact_payload(raw.payload)
            )
        except ValidationError as exc:
            raise ConstructionArtifactSchemaValidationError(
                f"persisted construction artifact failed schema validation: {raw.artifact_path}"
            ) from exc
        return validate_construction_artifact(artifact)

    def load_raw(self, artifact_id: str) -> RawPersistedConstructionArtifact:
        path = self.artifact_path(artifact_id)
        return RawPersistedConstructionArtifact(
            artifact_path=path,
            payload=_read_json_object(path),
        )

    def _write_once(self, path: Path, payload: object) -> None:
        serialized = _canonical_json(payload)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise ConstructionArtifactPersistenceError(f"immutable construction artifact conflict at {path}")
            return
        path.write_text(serialized, encoding="utf-8")


def build_stable_construction_artifact(artifact: ConstructionArtifact) -> ConstructionArtifact:
    payload = artifact.model_dump(mode="json", exclude={"artifact_id", "fingerprint"})
    fingerprint = _fingerprint(payload)
    return artifact.model_copy(
        update={
            "fingerprint": fingerprint,
            "artifact_id": f"construction_artifact_{fingerprint[:16]}",
        }
    )


def persist_construction_artifact(
    artifact: ConstructionArtifact,
    *,
    store: ConstructionArtifactStore | None = None,
) -> ConstructionArtifact:
    return (store or ConstructionArtifactStore()).persist(artifact)


def load_construction_artifact(
    artifact_id: str,
    *,
    store: ConstructionArtifactStore | None = None,
) -> ConstructionArtifact:
    return (store or ConstructionArtifactStore()).load(artifact_id)


def validate_construction_artifact(artifact: ConstructionArtifact) -> ConstructionArtifact:
    if artifact.schema_version != "construction_artifact_v1":
        raise ConstructionArtifactIntegrityValidationError("unsupported construction artifact schema_version")
    if not artifact.artifact_id.startswith("construction_artifact_"):
        raise ConstructionArtifactIntegrityValidationError(
            "construction artifact_id must use the stable construction_artifact_ prefix"
        )
    expected_artifact_id = _canonical_artifact_id(artifact)
    if artifact.artifact_id != expected_artifact_id:
        raise ConstructionArtifactIntegrityValidationError(
            "construction artifact_id does not match canonical artifact content"
        )
    expected_fingerprint = _canonical_fingerprint(artifact)
    if artifact.fingerprint != expected_fingerprint:
        raise ConstructionArtifactIntegrityValidationError(
            "construction artifact fingerprint does not match canonical artifact content"
        )
    if artifact.status == "feasible" and not artifact.final_target_weights:
        raise ConstructionArtifactIntegrityValidationError(
            "feasible construction artifact requires final_target_weights"
        )
    if artifact.status != "feasible" and artifact.final_target_weights:
        raise ConstructionArtifactIntegrityValidationError(
            "infeasible or rejected construction artifact must not include final_target_weights"
        )
    return artifact


def _validated_artifact_id_key(artifact_id: str) -> str:
    if not artifact_id.startswith("construction_artifact_"):
        raise ConstructionArtifactIntegrityValidationError(
            "construction artifact_id must use the stable construction_artifact_ prefix"
        )
    if any(separator in artifact_id for separator in ("/", "\\")):
        raise ConstructionArtifactIntegrityValidationError(
            "construction artifact_id must be a stable storage key"
        )
    return artifact_id


def _canonical_artifact_id(artifact: ConstructionArtifact) -> str:
    return f"construction_artifact_{_canonical_fingerprint(artifact)[:16]}"


def _canonical_fingerprint(artifact: ConstructionArtifact) -> str:
    payload = artifact.model_dump(mode="json", exclude={"artifact_id", "fingerprint"})
    return _fingerprint(payload)


def _fingerprint(payload: object) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(_canonicalize_construction_artifact_payload(payload), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _canonicalize_construction_artifact_payload(payload: object) -> object:
    if isinstance(payload, dict):
        canonical = {
            key: _canonicalize_construction_artifact_payload(value)
            for key, value in payload.items()
        }
        selection_rule_trace = canonical.get("selection_rule_trace")
        if selection_rule_trace in (None, {}, {"rule_ids": [], "steps": []}):
            canonical.pop("selection_rule_trace", None)
        return canonical
    if isinstance(payload, list):
        return [_canonicalize_construction_artifact_payload(item) for item in payload]
    return payload


def _normalize_legacy_construction_artifact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("selection_rule_trace") in (None, {}):
        normalized["selection_rule_trace"] = {"rule_ids": [], "steps": []}
    return normalized


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConstructionArtifactMissingFileError(f"missing persisted construction artifact file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConstructionArtifactInvalidJsonError(f"invalid persisted construction artifact json: {path}") from exc
    if not isinstance(payload, dict):
        raise ConstructionArtifactNonObjectPayloadError(
            f"persisted construction artifact payload must be a json object: {path}"
        )
    return payload
