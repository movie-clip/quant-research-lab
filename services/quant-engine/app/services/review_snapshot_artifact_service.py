from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.settings import get_settings
from app.schemas.backtest_engine import ReviewSnapshotArtifact


class ReviewSnapshotArtifactPersistenceError(ValueError):
    pass


class ReviewSnapshotArtifactReadError(ReviewSnapshotArtifactPersistenceError):
    pass


class ReviewSnapshotArtifactMissingFileError(ReviewSnapshotArtifactReadError):
    pass


class ReviewSnapshotArtifactInvalidJsonError(ReviewSnapshotArtifactReadError):
    pass


class ReviewSnapshotArtifactNonObjectPayloadError(ReviewSnapshotArtifactReadError):
    pass


class ReviewSnapshotArtifactSchemaValidationError(ReviewSnapshotArtifactReadError):
    pass


class ReviewSnapshotArtifactIntegrityValidationError(ReviewSnapshotArtifactReadError):
    pass


class ReviewSnapshotArtifactStore:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.review_snapshot_artifact_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def artifact_path(self, artifact_id: str) -> Path:
        return self.base_dir / f"{_validated_artifact_id_key(artifact_id)}.json"

    def persist(self, artifact: ReviewSnapshotArtifact) -> ReviewSnapshotArtifact:
        validated_artifact = validate_review_snapshot_artifact(artifact)
        self._write_once(
            self.artifact_path(validated_artifact.identity.artifact_id),
            validated_artifact.model_dump(mode="json"),
        )
        return validated_artifact

    def load(self, artifact_id: str) -> ReviewSnapshotArtifact:
        path = self.artifact_path(artifact_id)
        payload = _read_json_object(path)
        try:
            artifact = ReviewSnapshotArtifact.model_validate(payload)
        except ValidationError as exc:
            raise ReviewSnapshotArtifactSchemaValidationError(
                f"persisted review snapshot artifact failed schema validation: {path}"
            ) from exc
        return _validate_loaded_review_snapshot_artifact(artifact, persisted_payload=payload)

    def _write_once(self, path: Path, payload: object) -> None:
        serialized = _canonical_json(payload)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise ReviewSnapshotArtifactPersistenceError(f"immutable review snapshot artifact conflict at {path}")
            return
        path.write_text(serialized, encoding="utf-8")


def build_stable_review_snapshot_artifact(artifact: ReviewSnapshotArtifact) -> ReviewSnapshotArtifact:
    payload = artifact.model_dump(mode="json", exclude={
        "identity": {"artifact_id", "fingerprint"},
        "proposal_capture": {"open_handoff": {"artifact_id"}},
    })
    fingerprint = _fingerprint(payload)
    stable_artifact_id = f"review_snapshot_{fingerprint[:16]}"
    return artifact.model_copy(update={
        "identity": artifact.identity.model_copy(update={
            "fingerprint": fingerprint,
            "artifact_id": stable_artifact_id,
        }),
        "proposal_capture": artifact.proposal_capture.model_copy(update={
            "open_handoff": artifact.proposal_capture.open_handoff.model_copy(update={
                "artifact_id": stable_artifact_id,
            })
        }),
    })


def persist_review_snapshot_artifact(
    artifact: ReviewSnapshotArtifact,
    *,
    store: ReviewSnapshotArtifactStore | None = None,
) -> ReviewSnapshotArtifact:
    return (store or ReviewSnapshotArtifactStore()).persist(artifact)


def load_review_snapshot_artifact(
    artifact_id: str,
    *,
    store: ReviewSnapshotArtifactStore | None = None,
) -> ReviewSnapshotArtifact:
    return (store or ReviewSnapshotArtifactStore()).load(artifact_id)


def list_review_snapshot_artifacts(
    *,
    store: ReviewSnapshotArtifactStore | None = None,
) -> list[ReviewSnapshotArtifact]:
    active_store = store or ReviewSnapshotArtifactStore()
    artifacts: list[ReviewSnapshotArtifact] = []
    for path in sorted(active_store.base_dir.glob("*.json")):
        payload = _read_json_object(path)
        try:
            artifact = ReviewSnapshotArtifact.model_validate(payload)
        except ValidationError as exc:
            raise ReviewSnapshotArtifactSchemaValidationError(
                f"persisted review snapshot artifact failed schema validation: {path}"
            ) from exc
        artifacts.append(_validate_loaded_review_snapshot_artifact(artifact, persisted_payload=payload))
    return artifacts


def validate_review_snapshot_artifact(artifact: ReviewSnapshotArtifact) -> ReviewSnapshotArtifact:
    return _validate_loaded_review_snapshot_artifact(artifact)


def _validate_loaded_review_snapshot_artifact(
    artifact: ReviewSnapshotArtifact,
    *,
    persisted_payload: dict[str, Any] | None = None,
) -> ReviewSnapshotArtifact:
    if artifact.identity.schema_version != "review_snapshot_artifact_v1":
        raise ReviewSnapshotArtifactIntegrityValidationError("unsupported review snapshot artifact schema_version")
    if artifact.identity.artifact_kind != "portfolio_review_snapshot":
        raise ReviewSnapshotArtifactIntegrityValidationError("unsupported review snapshot artifact_kind")
    if artifact.identity.consumer_kind != "saved_hypothetical_replay_proposal":
        raise ReviewSnapshotArtifactIntegrityValidationError("unsupported review snapshot consumer_kind")
    if not artifact.identity.artifact_id.startswith("review_snapshot_"):
        raise ReviewSnapshotArtifactIntegrityValidationError(
            "review snapshot artifact_id must use the stable review_snapshot_ prefix"
        )
    canonical_payload = (
        _canonical_validation_payload_from_artifact(artifact)
        if persisted_payload is None
        else _canonical_validation_payload_from_persisted_payload(persisted_payload)
    )
    expected_artifact_id = _canonical_artifact_id_from_payload(canonical_payload)
    if artifact.identity.artifact_id != expected_artifact_id:
        raise ReviewSnapshotArtifactIntegrityValidationError(
            "review snapshot artifact_id does not match canonical artifact content"
        )
    expected_fingerprint = _fingerprint(canonical_payload)
    if artifact.identity.fingerprint != expected_fingerprint:
        raise ReviewSnapshotArtifactIntegrityValidationError(
            "review snapshot artifact fingerprint does not match canonical artifact content"
        )
    return artifact


def _validated_artifact_id_key(artifact_id: str) -> str:
    if not artifact_id.startswith("review_snapshot_"):
        raise ReviewSnapshotArtifactIntegrityValidationError(
            "review snapshot artifact_id must use the stable review_snapshot_ prefix"
        )
    if any(separator in artifact_id for separator in ("/", "\\")):
        raise ReviewSnapshotArtifactIntegrityValidationError(
            "review snapshot artifact_id must be a stable storage key"
        )
    return artifact_id


def _canonical_artifact_id_from_payload(payload: object) -> str:
    return f"review_snapshot_{_fingerprint(payload)[:16]}"


def _canonical_validation_payload_from_artifact(artifact: ReviewSnapshotArtifact) -> dict[str, Any]:
    return artifact.model_dump(mode="json", exclude={
        "identity": {"artifact_id", "fingerprint"},
        "proposal_capture": {"open_handoff": {"artifact_id"}},
    })


def _canonical_validation_payload_from_persisted_payload(payload: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(payload)
    identity = dict(canonical.get("identity") or {})
    identity.pop("artifact_id", None)
    identity.pop("fingerprint", None)
    canonical["identity"] = identity
    proposal_capture = dict(canonical.get("proposal_capture") or {})
    open_handoff = dict(proposal_capture.get("open_handoff") or {})
    open_handoff.pop("artifact_id", None)
    proposal_capture["open_handoff"] = open_handoff
    canonical["proposal_capture"] = proposal_capture
    return canonical


def _fingerprint(payload: object) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewSnapshotArtifactMissingFileError(f"missing persisted review snapshot artifact file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewSnapshotArtifactInvalidJsonError(f"invalid persisted review snapshot artifact json: {path}") from exc
    if not isinstance(payload, dict):
        raise ReviewSnapshotArtifactNonObjectPayloadError(
            f"persisted review snapshot artifact payload must be a json object: {path}"
        )
    return payload
