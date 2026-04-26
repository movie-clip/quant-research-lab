from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.settings import get_settings
from app.schemas.ranking import (
    ETF_RANKING_ARTIFACT_ID_PREFIX,
    validate_ranking_artifact_identity,
    validate_ranking_artifact_storage_key,
)
from app.schemas.research import EtfRankingArtifact, EtfRankingArtifactRecentMetadata, EtfRankingArtifactRecentRow, EtfRankingResponse


class EtfRankingArtifactPersistenceError(ValueError):
    pass


class EtfRankingArtifactReadError(EtfRankingArtifactPersistenceError):
    pass


class EtfRankingArtifactMissingFileError(EtfRankingArtifactReadError):
    pass


class EtfRankingArtifactInvalidJsonError(EtfRankingArtifactReadError):
    pass


class EtfRankingArtifactNonObjectPayloadError(EtfRankingArtifactReadError):
    pass


class EtfRankingArtifactSchemaValidationError(EtfRankingArtifactReadError):
    pass


class EtfRankingArtifactIntegrityValidationError(EtfRankingArtifactReadError):
    pass


class EtfRankingArtifactRecentIndexError(EtfRankingArtifactReadError):
    pass


class EtfRankingArtifactRecentIndexInvalidJsonError(EtfRankingArtifactRecentIndexError):
    pass


class EtfRankingArtifactRecentIndexNonObjectPayloadError(EtfRankingArtifactRecentIndexError):
    pass


class EtfRankingArtifactRecentIndexSchemaValidationError(EtfRankingArtifactRecentIndexError):
    pass


@dataclass(frozen=True)
class RawPersistedEtfRankingArtifact:
    artifact_path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class RawPersistedEtfRankingRecentRow:
    payload: dict[str, Any]
    line_number: int


class EtfRankingArtifactStore:
    recent_index_name = "recent.jsonl"

    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or settings.etf_ranking_artifact_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def artifact_path(self, artifact_id: str) -> Path:
        return self.base_dir / f"{_validated_artifact_id_key(artifact_id)}.json"

    def recent_index_path(self) -> Path:
        return self.base_dir / self.recent_index_name

    def persist(self, artifact: EtfRankingArtifact) -> EtfRankingArtifact:
        validated_artifact = validate_etf_ranking_artifact(artifact)
        self._write_once(
            self.artifact_path(validated_artifact.artifact_id),
            validated_artifact.model_dump(mode="json"),
        )
        self._append_recent_index(validated_artifact)
        return validated_artifact

    def load(self, artifact_id: str) -> EtfRankingArtifact:
        raw = self.load_raw(artifact_id)
        _validate_raw_etf_ranking_artifact_schema_version(raw.payload)
        try:
            artifact = EtfRankingArtifact.model_validate(raw.payload)
        except ValidationError as exc:
            raise EtfRankingArtifactSchemaValidationError(
                f"persisted etf ranking artifact failed schema validation: {raw.artifact_path}"
            ) from exc
        return validate_etf_ranking_artifact(artifact)

    def load_raw(self, artifact_id: str) -> RawPersistedEtfRankingArtifact:
        path = self.artifact_path(artifact_id)
        return RawPersistedEtfRankingArtifact(
            artifact_path=path,
            payload=_read_json_object(path),
        )

    def list_recent(
        self,
        *,
        limit: int,
        effective_peer_group: str | None = None,
    ) -> list[EtfRankingArtifactRecentRow]:
        if limit < 1:
            return []

        recent_rows: list[EtfRankingArtifactRecentRow] = []
        for recent_row in self._iter_recent_rows(effective_peer_group=effective_peer_group):
            recent_rows.append(recent_row)
            if len(recent_rows) >= limit:
                break
        return recent_rows

    def recent_metadata(self) -> EtfRankingArtifactRecentMetadata:
        available_effective_peer_groups: list[str] = []
        seen_effective_peer_groups: set[str] = set()
        for recent_row in self._iter_recent_rows():
            if recent_row.effective_peer_group is None:
                continue
            if recent_row.effective_peer_group in seen_effective_peer_groups:
                continue
            seen_effective_peer_groups.add(recent_row.effective_peer_group)
            available_effective_peer_groups.append(recent_row.effective_peer_group)
        return EtfRankingArtifactRecentMetadata(
            available_effective_peer_groups=available_effective_peer_groups,
        )

    def _append_recent_index(self, artifact: EtfRankingArtifact) -> None:
        index_path = self.recent_index_path()
        index_path.parent.mkdir(parents=True, exist_ok=True)
        with index_path.open("a", encoding="utf-8") as handle:
            handle.write(_canonical_json(_build_recent_index_entry(artifact)))
            handle.write("\n")

    def _load_recent_index_rows(self) -> list[RawPersistedEtfRankingRecentRow]:
        path = self.recent_index_path()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []

        rows: list[RawPersistedEtfRankingRecentRow] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict):
                continue
            rows.append(RawPersistedEtfRankingRecentRow(payload=payload, line_number=line_number))
        return rows

    def _load_recent_index_rows_strict(self) -> list[RawPersistedEtfRankingRecentRow]:
        path = self.recent_index_path()
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []

        rows: list[RawPersistedEtfRankingRecentRow] = []
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EtfRankingArtifactRecentIndexInvalidJsonError(
                    f"invalid persisted etf ranking recent index json: {path}: line {line_number}"
                ) from exc
            if not isinstance(payload, dict):
                raise EtfRankingArtifactRecentIndexNonObjectPayloadError(
                    f"persisted etf ranking recent index payload must be a json object: {path}: line {line_number}"
                )
            rows.append(RawPersistedEtfRankingRecentRow(payload=payload, line_number=line_number))
        return rows

    def _iter_recent_rows(
        self,
        *,
        effective_peer_group: str | None = None,
    ) -> list[EtfRankingArtifactRecentRow]:
        recent_rows: list[EtfRankingArtifactRecentRow] = []
        seen_artifact_ids: set[str] = set()
        for raw_row in reversed(self._load_recent_index_rows()):
            try:
                recent_row = EtfRankingArtifactRecentRow.model_validate(raw_row.payload)
            except ValidationError:
                continue

            if effective_peer_group is not None and recent_row.effective_peer_group != effective_peer_group:
                continue

            if recent_row.artifact_id in seen_artifact_ids:
                continue

            seen_artifact_ids.add(recent_row.artifact_id)
            recent_rows.append(recent_row)
        return recent_rows

    def list_recent_strict(
        self,
        *,
        limit: int,
        effective_peer_group: str | None = None,
    ) -> list[EtfRankingArtifactRecentRow]:
        if limit < 1:
            return []

        recent_rows: list[EtfRankingArtifactRecentRow] = []
        for recent_row in self._iter_recent_rows_strict(effective_peer_group=effective_peer_group):
            recent_rows.append(recent_row)
            if len(recent_rows) >= limit:
                break
        return recent_rows

    def _iter_recent_rows_strict(
        self,
        *,
        effective_peer_group: str | None = None,
    ) -> list[EtfRankingArtifactRecentRow]:
        recent_rows: list[EtfRankingArtifactRecentRow] = []
        seen_artifact_ids: set[str] = set()
        for raw_row in reversed(self._load_recent_index_rows_strict()):
            try:
                recent_row = EtfRankingArtifactRecentRow.model_validate(raw_row.payload)
            except ValidationError as exc:
                detail = exc.errors()[0].get("msg", "schema validation error") if exc.errors() else "schema validation error"
                raise EtfRankingArtifactRecentIndexSchemaValidationError(
                    "persisted etf ranking recent index row failed schema validation: "
                    f"{self.recent_index_path()}: line {raw_row.line_number}: {detail}"
                ) from exc

            if effective_peer_group is not None and recent_row.effective_peer_group != effective_peer_group:
                continue

            if recent_row.artifact_id in seen_artifact_ids:
                continue

            seen_artifact_ids.add(recent_row.artifact_id)
            recent_rows.append(recent_row)
        return recent_rows

    def _write_once(self, path: Path, payload: object) -> None:
        serialized = _canonical_json(payload)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise EtfRankingArtifactPersistenceError(f"immutable etf ranking artifact conflict at {path}")
            return
        path.write_text(serialized, encoding="utf-8")


def build_stable_etf_ranking_artifact(response: EtfRankingResponse) -> EtfRankingArtifact:
    artifact = EtfRankingArtifact(
        artifact_id="etf_ranking_artifact_pending",
        **response.model_dump(mode="json"),
    )
    artifact_id = _canonical_artifact_id(artifact)
    return artifact.model_copy(update={"artifact_id": artifact_id})


def persist_etf_ranking_artifact(
    response: EtfRankingResponse,
    *,
    store: EtfRankingArtifactStore | None = None,
) -> EtfRankingArtifact:
    return (store or EtfRankingArtifactStore()).persist(build_stable_etf_ranking_artifact(response))


def load_etf_ranking_artifact(
    artifact_id: str,
    *,
    store: EtfRankingArtifactStore | None = None,
) -> EtfRankingArtifact:
    return (store or EtfRankingArtifactStore()).load(artifact_id)


def list_recent_etf_ranking_artifacts(
    *,
    limit: int,
    effective_peer_group: str | None = None,
    store: EtfRankingArtifactStore | None = None,
) -> list[EtfRankingArtifactRecentRow]:
    return (store or EtfRankingArtifactStore()).list_recent(
        limit=limit,
        effective_peer_group=effective_peer_group,
    )


def list_recent_etf_ranking_artifacts_strict(
    *,
    limit: int,
    effective_peer_group: str | None = None,
    store: EtfRankingArtifactStore | None = None,
) -> list[EtfRankingArtifactRecentRow]:
    return (store or EtfRankingArtifactStore()).list_recent_strict(
        limit=limit,
        effective_peer_group=effective_peer_group,
    )


def get_recent_etf_ranking_artifact_metadata(
    *,
    store: EtfRankingArtifactStore | None = None,
) -> EtfRankingArtifactRecentMetadata:
    return (store or EtfRankingArtifactStore()).recent_metadata()


def validate_etf_ranking_artifact(artifact: EtfRankingArtifact) -> EtfRankingArtifact:
    try:
        validate_ranking_artifact_identity(
            schema_version=artifact.schema_version,
            expected_schema_version="etf_ranking_artifact_v1",
            artifact_id=artifact.artifact_id,
            artifact_id_prefix=ETF_RANKING_ARTIFACT_ID_PREFIX,
            expected_artifact_id=_canonical_artifact_id(artifact),
            artifact_label="etf ranking",
        )
    except ValueError as exc:
        raise EtfRankingArtifactIntegrityValidationError(str(exc)) from exc
    return artifact


def _validated_artifact_id_key(artifact_id: str) -> str:
    try:
        return validate_ranking_artifact_storage_key(
            artifact_id=artifact_id,
            artifact_id_prefix=ETF_RANKING_ARTIFACT_ID_PREFIX,
            artifact_label="etf ranking",
        )
    except ValueError as exc:
        raise EtfRankingArtifactIntegrityValidationError(str(exc)) from exc


def _canonical_artifact_id(artifact: EtfRankingArtifact) -> str:
    payload = artifact.model_dump(mode="json", exclude={"artifact_id"})
    return f"{ETF_RANKING_ARTIFACT_ID_PREFIX}{_fingerprint(payload)[:16]}"


def _fingerprint(payload: object) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise EtfRankingArtifactMissingFileError(f"missing persisted etf ranking artifact file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise EtfRankingArtifactInvalidJsonError(f"invalid persisted etf ranking artifact json: {path}") from exc
    if not isinstance(payload, dict):
        raise EtfRankingArtifactNonObjectPayloadError(
            f"persisted etf ranking artifact payload must be a json object: {path}"
        )
    return payload


def _validate_raw_etf_ranking_artifact_schema_version(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "etf_ranking_artifact_v1":
        raise EtfRankingArtifactSchemaValidationError("unsupported etf ranking schema_version")


def _build_recent_index_entry(artifact: EtfRankingArtifact) -> dict[str, Any]:
    return {
        "artifact_id": artifact.artifact_id,
        "ranking_id": artifact.ranking_id,
        "methodology_id": artifact.run_metadata.methodology_id,
        "as_of_date": artifact.as_of_date,
        "ranking_basis_date": artifact.run_metadata.ranking_basis_date,
        "benchmark_symbol": artifact.benchmark_symbol,
        "lookback_months": artifact.lookback_months,
        "universe_size": len(artifact.universe),
        "evaluated_universe_size": len(artifact.ranked_universe),
        "effective_peer_group": artifact.effective_peer_group,
        "confidence": artifact.warnings.confidence,
    }


def _build_recent_row(artifact: EtfRankingArtifact) -> EtfRankingArtifactRecentRow:
    return EtfRankingArtifactRecentRow(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.as_of_date,
        ranking_basis_date=artifact.run_metadata.ranking_basis_date,
        benchmark_symbol=artifact.benchmark_symbol,
        lookback_months=artifact.lookback_months,
        universe_size=len(artifact.universe),
        evaluated_universe_size=len(artifact.ranked_universe),
        effective_peer_group=artifact.effective_peer_group,
        confidence=artifact.warnings.confidence,
    )
