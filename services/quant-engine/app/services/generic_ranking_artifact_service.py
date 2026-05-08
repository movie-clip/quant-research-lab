from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.settings import get_settings
from app.schemas.generic_ranking import (
    GENERIC_RANKING_ARTIFACT_ID_PREFIX,
    GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION,
    GenericRankingArtifact,
    GenericRankingArtifactRecentRow,
    GenericRankingResponse,
)
from app.schemas.ranking import (
    validate_ranking_artifact_identity,
    validate_ranking_artifact_storage_key,
)


# ── Error hierarchy ────────────────────────────────────────────────────────────

class GenericRankingPersistenceError(ValueError):
    pass


class GenericRankingReadError(GenericRankingPersistenceError):
    pass


class GenericRankingMissingFileError(GenericRankingReadError):
    pass


class GenericRankingInvalidJsonError(GenericRankingReadError):
    pass


class GenericRankingNonObjectPayloadError(GenericRankingReadError):
    pass


class GenericRankingSchemaValidationError(GenericRankingReadError):
    pass


class GenericRankingIntegrityError(GenericRankingReadError):
    pass


class GenericRankingRecentIndexError(GenericRankingReadError):
    pass


class GenericRankingRecentIndexInvalidJsonError(GenericRankingRecentIndexError):
    pass


class GenericRankingRecentIndexNonObjectPayloadError(GenericRankingRecentIndexError):
    pass


class GenericRankingRecentIndexSchemaValidationError(GenericRankingRecentIndexError):
    pass


# ── Raw dataclasses ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RawPersistedGenericRankingArtifact:
    artifact_path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class RawPersistedGenericRankingRecentRow:
    payload: dict[str, Any]
    line_number: int


# ── Artifact store ─────────────────────────────────────────────────────────────

class GenericRankingArtifactStore:
    recent_index_name = "recent.jsonl"

    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.generic_ranking_artifacts_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def artifact_path(self, artifact_id: str) -> Path:
        return self.base_dir / f"{_validated_artifact_id_key(artifact_id)}.json"

    def recent_index_path(self) -> Path:
        return self.base_dir / self.recent_index_name

    def persist(self, artifact: GenericRankingArtifact) -> GenericRankingArtifact:
        validated = validate_generic_ranking_artifact(artifact)
        self._write_once(
            self.artifact_path(validated.artifact_id),
            validated.model_dump(mode="json"),
        )
        self._append_recent_index(validated)
        return validated

    def load(self, artifact_id: str) -> GenericRankingArtifact:
        raw = self.load_raw(artifact_id)
        _validate_raw_schema_version(raw.payload)
        try:
            artifact = GenericRankingArtifact.model_validate(raw.payload)
        except ValidationError as exc:
            raise GenericRankingSchemaValidationError(
                f"persisted generic ranking artifact failed schema validation: {raw.artifact_path}"
            ) from exc
        return validate_generic_ranking_artifact(artifact)

    def load_raw(self, artifact_id: str) -> RawPersistedGenericRankingArtifact:
        path = self.artifact_path(artifact_id)
        return RawPersistedGenericRankingArtifact(
            artifact_path=path,
            payload=_read_json_object(path),
        )

    def list_recent(self, *, limit: int) -> list[GenericRankingArtifactRecentRow]:
        if limit < 1:
            return []
        recent_rows: list[GenericRankingArtifactRecentRow] = []
        for row in self._iter_recent_rows():
            recent_rows.append(row)
            if len(recent_rows) >= limit:
                break
        return recent_rows

    def _append_recent_index(self, artifact: GenericRankingArtifact) -> None:
        index_path = self.recent_index_path()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(_build_recent_index_entry(artifact)))
            handle.write("\n")

    def _load_recent_index_rows(self) -> list[RawPersistedGenericRankingRecentRow]:
        path = self.recent_index_path()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []

        rows: list[RawPersistedGenericRankingRecentRow] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            rows.append(RawPersistedGenericRankingRecentRow(payload=payload, line_number=line_number))
        return rows

    def _iter_recent_rows(self) -> list[GenericRankingArtifactRecentRow]:
        recent_rows: list[GenericRankingArtifactRecentRow] = []
        seen_artifact_ids: set[str] = set()
        for raw_row in reversed(self._load_recent_index_rows()):
            try:
                row = GenericRankingArtifactRecentRow.model_validate(raw_row.payload)
            except ValidationError:
                continue
            if row.artifact_id in seen_artifact_ids:
                continue
            seen_artifact_ids.add(row.artifact_id)
            recent_rows.append(row)
        return recent_rows

    def _write_once(self, path: Path, payload: object) -> None:
        serialized = _canonical_json(payload)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise GenericRankingPersistenceError(
                    f"immutable generic ranking artifact conflict at {path}"
                )
            return
        path.write_text(serialized, encoding="utf-8")


# ── Public builder ─────────────────────────────────────────────────────────────

def build_stable_generic_ranking_artifact(response: GenericRankingResponse) -> GenericRankingArtifact:
    artifact = GenericRankingArtifact(
        artifact_id=f"{GENERIC_RANKING_ARTIFACT_ID_PREFIX}pending",
        **response.model_dump(mode="json"),
    )
    artifact_id = _canonical_artifact_id(artifact)
    return artifact.model_copy(update={"artifact_id": artifact_id})


def persist_generic_ranking_artifact(
    response: GenericRankingResponse,
    *,
    store: GenericRankingArtifactStore | None = None,
) -> GenericRankingArtifact:
    return (store or GenericRankingArtifactStore()).persist(
        build_stable_generic_ranking_artifact(response)
    )


def load_generic_ranking_artifact(
    artifact_id: str,
    *,
    store: GenericRankingArtifactStore | None = None,
) -> GenericRankingArtifact:
    return (store or GenericRankingArtifactStore()).load(artifact_id)


def list_recent_generic_ranking_artifacts(
    *,
    limit: int,
    store: GenericRankingArtifactStore | None = None,
) -> list[GenericRankingArtifactRecentRow]:
    return (store or GenericRankingArtifactStore()).list_recent(limit=limit)


def validate_generic_ranking_artifact(artifact: GenericRankingArtifact) -> GenericRankingArtifact:
    try:
        validate_ranking_artifact_identity(
            schema_version=artifact.schema_version,
            expected_schema_version=GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION,
            artifact_id=artifact.artifact_id,
            artifact_id_prefix=GENERIC_RANKING_ARTIFACT_ID_PREFIX,
            expected_artifact_id=_canonical_artifact_id(artifact),
            artifact_label="generic ranking",
        )
    except ValueError as exc:
        raise GenericRankingIntegrityError(str(exc)) from exc
    return artifact


# ── Private helpers ────────────────────────────────────────────────────────────

def _validated_artifact_id_key(artifact_id: str) -> str:
    try:
        return validate_ranking_artifact_storage_key(
            artifact_id=artifact_id,
            artifact_id_prefix=GENERIC_RANKING_ARTIFACT_ID_PREFIX,
            artifact_label="generic ranking",
        )
    except ValueError as exc:
        raise GenericRankingIntegrityError(str(exc)) from exc


def _canonical_artifact_id(artifact: GenericRankingArtifact) -> str:
    payload = artifact.model_dump(mode="json", exclude={"artifact_id"})
    return f"{GENERIC_RANKING_ARTIFACT_ID_PREFIX}{_fingerprint(payload)[:16]}"


def _fingerprint(payload: object) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise GenericRankingMissingFileError(
            f"missing persisted generic ranking artifact file: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise GenericRankingInvalidJsonError(
            f"invalid persisted generic ranking artifact json: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise GenericRankingNonObjectPayloadError(
            f"persisted generic ranking artifact payload must be a json object: {path}"
        )
    return payload


def _validate_raw_schema_version(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION:
        raise GenericRankingSchemaValidationError("unsupported generic ranking schema_version")


def _build_recent_index_entry(artifact: GenericRankingArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "ranking_id": artifact.ranking_id,
        "methodology_id": artifact.methodology_id,
        "as_of_date": artifact.as_of_date,
        "ranking_basis_date": artifact.run_metadata.ranking_basis_date,
        "benchmark_symbol": artifact.benchmark_symbol,
        "lookback_months": artifact.lookback_months,
        "universe_id": artifact.universe_spec_snapshot.universe_id,
        "universe_kind": artifact.universe_spec_snapshot.universe_kind,
        "score_config_id": artifact.run_metadata.score_config_ref.score_config_id,
        "evaluated_universe_size": len(artifact.ranked_universe),
        "confidence": artifact.run_metadata.confidence,
    }
