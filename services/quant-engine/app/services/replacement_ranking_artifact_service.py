from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.settings import get_settings
from app.schemas.ranking import (
    INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_ID_PREFIX,
    validate_ranking_artifact_identity,
    validate_ranking_artifact_storage_key,
)
from app.schemas.research import (
    IntentBoundEtfReplacementRankingConsumerCandidate,
    IntentBoundEtfReplacementRankingConsumerHandoff,
    IntentBoundEtfReplacementArtifactRequest,
    IntentBoundEtfReplacementRankingArtifact,
    IntentBoundEtfReplacementRankingResponse,
)
from app.services.replacement_ranking import build_intent_bound_etf_replacement_artifact_lineage


DEFAULT_REPLACEMENT_RANKING_ARTIFACT_DIR = str(
    Path(__file__).resolve().parents[4] / "data" / "artifacts" / "etf-replacement-ranking-artifacts"
)


class ReplacementRankingArtifactPersistenceError(ValueError):
    pass


class ReplacementRankingArtifactReadError(ReplacementRankingArtifactPersistenceError):
    pass


class ReplacementRankingArtifactMissingFileError(ReplacementRankingArtifactReadError):
    pass


class ReplacementRankingArtifactInvalidJsonError(ReplacementRankingArtifactReadError):
    pass


class ReplacementRankingArtifactNonObjectPayloadError(ReplacementRankingArtifactReadError):
    pass


class ReplacementRankingArtifactSchemaValidationError(ReplacementRankingArtifactReadError):
    pass


class ReplacementRankingArtifactIntegrityValidationError(ReplacementRankingArtifactReadError):
    pass


@dataclass(frozen=True)
class RawPersistedReplacementRankingArtifact:
    artifact_path: Path
    payload: dict[str, Any]


class ReplacementRankingArtifactStore:
    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(
            base_dir
            or getattr(settings, "replacement_ranking_artifact_dir", DEFAULT_REPLACEMENT_RANKING_ARTIFACT_DIR)
        )
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def artifact_path(self, artifact_id: str) -> Path:
        return self.base_dir / f"{_validated_artifact_id_key(artifact_id)}.json"

    def persist(self, artifact: IntentBoundEtfReplacementRankingArtifact) -> IntentBoundEtfReplacementRankingArtifact:
        validated_artifact = validate_replacement_ranking_artifact(artifact)
        self._write_once(
            self.artifact_path(validated_artifact.artifact_id),
            validated_artifact.model_dump(mode="json"),
        )
        return validated_artifact

    def load(self, artifact_id: str) -> IntentBoundEtfReplacementRankingArtifact:
        raw = self.load_raw(artifact_id)
        _validate_raw_replacement_ranking_artifact_schema_version(raw.payload)
        try:
            artifact = IntentBoundEtfReplacementRankingArtifact.model_validate(raw.payload)
        except ValidationError as exc:
            detail = exc.errors()[0].get("msg", "schema validation error") if exc.errors() else "schema validation error"
            raise ReplacementRankingArtifactSchemaValidationError(
                f"persisted replacement ranking artifact failed schema validation: {raw.artifact_path}: {detail}"
            ) from exc
        return validate_replacement_ranking_artifact(artifact)

    def load_raw(self, artifact_id: str) -> RawPersistedReplacementRankingArtifact:
        path = self.artifact_path(artifact_id)
        return RawPersistedReplacementRankingArtifact(
            artifact_path=path,
            payload=_read_json_object(path),
        )

    def _write_once(self, path: Path, payload: object) -> None:
        serialized = _canonical_json(payload)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing != serialized:
                raise ReplacementRankingArtifactPersistenceError(
                    f"immutable replacement ranking artifact conflict at {path}"
                )
            return
        path.write_text(serialized, encoding="utf-8")


def build_stable_replacement_ranking_artifact(
    response: IntentBoundEtfReplacementRankingResponse,
) -> IntentBoundEtfReplacementRankingArtifact:
    artifact = IntentBoundEtfReplacementRankingArtifact(
        artifact_id="intent_bound_etf_replacement_ranking_artifact_pending",
        ranking_id=response.ranking_id,
        methodology_id=response.methodology_id,
        basis_date=response.basis_date,
        status=response.status,
        request=IntentBoundEtfReplacementArtifactRequest(
            replacement_intent=response.submitted_request.replacement_intent,
            seed_context=response.submitted_request.seed_context,
            prefer_live_data=response.submitted_request.prefer_live_data,
            normalized_request=response.normalized_request,
        ),
        request_context=response.request_context,
        submitted_request=response.submitted_request,
        normalized_request=response.normalized_request,
        effective_inputs=response.effective_inputs,
        request_hash=response.request_hash,
        run_metadata=response.run_metadata,
        eligible_count=response.eligible_count,
        excluded_count=response.excluded_count,
        ranked_candidates=response.ranked_candidates,
        excluded_candidates=response.excluded_candidates,
        warnings=response.warnings,
        unavailable_reason=response.unavailable_reason,
        lineage=build_intent_bound_etf_replacement_artifact_lineage(response),
    )
    artifact_id = _canonical_artifact_id(artifact)
    return artifact.model_copy(update={"artifact_id": artifact_id})


def persist_replacement_ranking_artifact(
    response: IntentBoundEtfReplacementRankingResponse,
    *,
    store: ReplacementRankingArtifactStore | None = None,
) -> IntentBoundEtfReplacementRankingArtifact:
    return (store or ReplacementRankingArtifactStore()).persist(build_stable_replacement_ranking_artifact(response))


def build_legacy_replacement_ranking_response(
    artifact: IntentBoundEtfReplacementRankingArtifact,
) -> IntentBoundEtfReplacementRankingResponse:
    return IntentBoundEtfReplacementRankingResponse(
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.methodology_id,
        basis_date=artifact.basis_date,
        status=artifact.status,
        request=artifact.request_context,
        request_context=artifact.request_context,
        submitted_request=artifact.submitted_request,
        normalized_request=artifact.normalized_request,
        effective_inputs=artifact.effective_inputs,
        request_hash=artifact.request_hash,
        run_metadata=artifact.run_metadata,
        eligible_count=artifact.eligible_count,
        excluded_count=artifact.excluded_count,
        ranked_candidates=artifact.ranked_candidates,
        excluded_candidates=artifact.excluded_candidates,
        warnings=artifact.warnings,
        unavailable_reason=artifact.unavailable_reason,
    )


def load_replacement_ranking_artifact(
    artifact_id: str,
    *,
    store: ReplacementRankingArtifactStore | None = None,
) -> IntentBoundEtfReplacementRankingArtifact:
    return (store or ReplacementRankingArtifactStore()).load(artifact_id)


def validate_replacement_ranking_artifact(
    artifact: IntentBoundEtfReplacementRankingArtifact,
) -> IntentBoundEtfReplacementRankingArtifact:
    try:
        validate_ranking_artifact_identity(
            schema_version=artifact.schema_version,
            expected_schema_version="intent_bound_etf_replacement_ranking_artifact_v1",
            artifact_id=artifact.artifact_id,
            artifact_id_prefix=INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_ID_PREFIX,
            expected_artifact_id=_canonical_artifact_id(artifact),
            artifact_label="replacement ranking",
        )
    except ValueError as exc:
        raise ReplacementRankingArtifactIntegrityValidationError(str(exc)) from exc
    return artifact


def build_replacement_ranking_consumer_handoff(
    artifact: IntentBoundEtfReplacementRankingArtifact,
) -> IntentBoundEtfReplacementRankingConsumerHandoff:
    try:
        if artifact.status != "ok":
            raise ValueError("replacement ranking artifact is unreplayable")
        if not artifact.ranked_candidates:
            raise ValueError("replacement ranking artifact is unreplayable")

        selected_candidate = next(
            (row for row in artifact.ranked_candidates if row.symbol == artifact.lineage.candidate_symbol),
            None,
        )
        if selected_candidate is None:
            raise ValueError("replacement ranking artifact candidate_symbol is not present in ranked_candidates")
        if selected_candidate.rank is None:
            raise ValueError("replacement ranking artifact selected candidate rank is required")
        if selected_candidate.composite_score is None:
            raise ValueError("replacement ranking artifact selected candidate composite_score is required")

        consumer_handoff = IntentBoundEtfReplacementRankingConsumerHandoff(
            artifact_id=artifact.artifact_id,
            ranking_id=artifact.ranking_id,
            methodology_id=artifact.methodology_id,
            basis_date=artifact.basis_date,
            draft_id=artifact.lineage.draft_id,
            workspace_id=artifact.lineage.workspace_id,
            base_node_id=artifact.lineage.base_node_id,
            base_symbol=artifact.lineage.base_symbol,
            candidate_symbol=artifact.lineage.candidate_symbol,
            seed_ranking_id=artifact.lineage.seed_ranking_id,
            seed_methodology_id=artifact.lineage.seed_methodology_id,
            seed_ranking_basis_date=artifact.lineage.seed_ranking_basis_date,
            peer_group=artifact.lineage.peer_group,
            benchmark_symbol=artifact.lineage.benchmark_symbol,
            lookback_months=artifact.lineage.lookback_months,
            eligible_count=artifact.eligible_count,
            excluded_count=artifact.excluded_count,
            selected_candidate=IntentBoundEtfReplacementRankingConsumerCandidate(
                symbol=selected_candidate.symbol,
                rank=selected_candidate.rank,
                composite_score=selected_candidate.composite_score,
                basis_date=selected_candidate.basis_date,
                draft_id=selected_candidate.draft_id,
                base_node_id=selected_candidate.base_node_id,
                base_symbol=selected_candidate.base_symbol,
                seed_ranking_id=selected_candidate.seed_ranking_id,
                seed_methodology_id=selected_candidate.seed_methodology_id,
            ),
        )
    except ValueError as exc:
        raise ReplacementRankingArtifactIntegrityValidationError(str(exc)) from exc

    if consumer_handoff.ranking_id != artifact.run_metadata.ranking_id:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff ranking_id does not match artifact run_metadata.ranking_id"
        )
    if consumer_handoff.methodology_id != artifact.run_metadata.methodology_id:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff methodology_id does not match artifact run_metadata.methodology_id"
        )
    if consumer_handoff.basis_date != artifact.run_metadata.basis_date:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff basis_date does not match artifact run_metadata.basis_date"
        )
    if consumer_handoff.seed_ranking_basis_date != artifact.lineage.seed_ranking_basis_date:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff seed_ranking_basis_date does not match artifact lineage"
        )
    if consumer_handoff.benchmark_symbol != artifact.effective_inputs.benchmark_symbol:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff benchmark_symbol does not match artifact effective_inputs.benchmark_symbol"
        )
    if consumer_handoff.lookback_months != artifact.effective_inputs.lookback_months:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff lookback_months does not match artifact effective_inputs.lookback_months"
        )
    if consumer_handoff.base_symbol != artifact.effective_inputs.base_symbol:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff base_symbol does not match artifact effective_inputs.base_symbol"
        )
    if consumer_handoff.candidate_symbol != artifact.effective_inputs.candidate_symbol:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff candidate_symbol does not match artifact effective_inputs.candidate_symbol"
        )
    if consumer_handoff.peer_group != artifact.effective_inputs.peer_group:
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff peer_group does not match artifact effective_inputs.peer_group"
        )
    if consumer_handoff.eligible_count != len(artifact.ranked_candidates):
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff eligible_count does not match ranked_candidates"
        )
    if consumer_handoff.excluded_count != len(artifact.excluded_candidates):
        raise ReplacementRankingArtifactIntegrityValidationError(
            "replacement ranking consumer handoff excluded_count does not match excluded_candidates"
        )
    return consumer_handoff


def _validated_artifact_id_key(artifact_id: str) -> str:
    try:
        return validate_ranking_artifact_storage_key(
            artifact_id=artifact_id,
            artifact_id_prefix=INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_ID_PREFIX,
            artifact_label="replacement ranking",
        )
    except ValueError as exc:
        raise ReplacementRankingArtifactIntegrityValidationError(str(exc)) from exc


def _canonical_artifact_id(artifact: IntentBoundEtfReplacementRankingArtifact) -> str:
    payload = artifact.model_dump(mode="json", exclude={"artifact_id"})
    return f"{INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_ID_PREFIX}{_fingerprint(payload)[:16]}"


def _fingerprint(payload: object) -> str:
    return sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReplacementRankingArtifactMissingFileError(
            f"missing persisted replacement ranking artifact file: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise ReplacementRankingArtifactInvalidJsonError(
            f"invalid persisted replacement ranking artifact json: {path}"
        ) from exc
    if not isinstance(payload, dict):
        raise ReplacementRankingArtifactNonObjectPayloadError(
            f"persisted replacement ranking artifact payload must be a json object: {path}"
        )
    return payload


def _validate_raw_replacement_ranking_artifact_schema_version(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != "intent_bound_etf_replacement_ranking_artifact_v1":
        raise ReplacementRankingArtifactSchemaValidationError("unsupported replacement ranking schema_version")
