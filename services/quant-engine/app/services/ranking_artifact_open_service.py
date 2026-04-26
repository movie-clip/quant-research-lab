from __future__ import annotations

from dataclasses import dataclass

from app.schemas.ranking import (
    ETF_RANKING_ARTIFACT_SCHEMA_VERSION,
    INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION,
    RankingArtifactKind,
    RankingArtifactSchemaVersion,
    infer_ranking_artifact_kind_from_artifact_id,
    validate_ranking_artifact_kind_schema_version,
)
from app.schemas.research import (
    EtfRankingArtifact,
    EtfRankingArtifactOpenResponse,
    EtfRankingArtifactOpenReviewPayload,
    IntentBoundEtfReplacementRankingArtifact,
    IntentBoundEtfReplacementRankingConsumerHandoff,
    IntentBoundEtfReplacementRankingArtifactOpenResponse,
    IntentBoundEtfReplacementRankingOpenReviewPayload,
    RankingArtifactOpenHandoff,
    RankingArtifactOpenResponse,
    RankingArtifactPreflightEligibility,
    RankingArtifactPreflightArtifact,
    RankingArtifactPreflightResponse,
)
from app.services.etf_ranking_artifact_service import EtfRankingArtifactStore, load_etf_ranking_artifact
from app.services.replacement_ranking_artifact_service import (
    ReplacementRankingArtifactStore,
    build_replacement_ranking_consumer_handoff,
    load_replacement_ranking_artifact,
)


class RankingArtifactOpenServiceError(ValueError):
    pass


class RankingArtifactOpenUnsupportedStateError(RankingArtifactOpenServiceError):
    pass


class RankingArtifactOpenIdentityMismatchError(RankingArtifactOpenServiceError):
    pass


@dataclass(frozen=True)
class ResolvedRankingArtifact:
    artifact_kind: RankingArtifactKind
    schema_version: RankingArtifactSchemaVersion
    artifact: EtfRankingArtifact | IntentBoundEtfReplacementRankingArtifact


@dataclass(frozen=True)
class ReplacementEligibilityAssessment:
    open_supported: bool
    replay_eligible: bool
    consumer_handoff_supported: bool
    ineligibility_reason: str | None = None


class RankingArtifactOpenService:
    def __init__(
        self,
        *,
        etf_store: EtfRankingArtifactStore | None = None,
        replacement_store: ReplacementRankingArtifactStore | None = None,
    ) -> None:
        self.etf_store = etf_store or EtfRankingArtifactStore()
        self.replacement_store = replacement_store or ReplacementRankingArtifactStore()

    def preflight(self, artifact_id: str) -> RankingArtifactPreflightResponse:
        resolved = self._resolve_from_artifact_id(artifact_id)
        artifact = resolved.artifact
        open_handoff = RankingArtifactOpenHandoff(
            artifact_kind=resolved.artifact_kind,
            artifact_id=artifact.artifact_id,
            schema_version=resolved.schema_version,
        )
        eligibility = self._build_preflight_eligibility(resolved)
        return RankingArtifactPreflightResponse(
            artifact=RankingArtifactPreflightArtifact(
                artifact_kind=resolved.artifact_kind,
                artifact_id=artifact.artifact_id,
                schema_version=resolved.schema_version,
                ranking_id=artifact.ranking_id,
                methodology_id=artifact.run_metadata.methodology_id,
                as_of_date=artifact.run_metadata.as_of_date,
                ranking_basis_date=artifact.run_metadata.ranking_basis_date,
            ),
            eligibility=eligibility,
            open_handoff=open_handoff,
        )

    def open(self, handoff: RankingArtifactOpenHandoff) -> RankingArtifactOpenResponse:
        resolved = self._resolve_from_handoff(handoff)
        if resolved.artifact_kind == "intent_bound_etf_replacement_ranking":
            replacement_artifact = resolved.artifact
            if not isinstance(replacement_artifact, IntentBoundEtfReplacementRankingArtifact):
                raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
            review_payload = _build_review_payload(resolved)
            if not isinstance(review_payload, IntentBoundEtfReplacementRankingOpenReviewPayload):
                raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
            consumer_handoff = self._build_replacement_consumer_handoff(replacement_artifact)
            return IntentBoundEtfReplacementRankingArtifactOpenResponse(
                open_handoff=handoff,
                review_payload=review_payload,
                consumer_handoff=consumer_handoff,
            )
        review_payload = _build_review_payload(resolved)
        if not isinstance(review_payload, EtfRankingArtifactOpenReviewPayload):
            raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
        return EtfRankingArtifactOpenResponse(
            open_handoff=handoff,
            review_payload=review_payload,
        )

    def _resolve_from_artifact_id(self, artifact_id: str) -> ResolvedRankingArtifact:
        artifact_kind = infer_ranking_artifact_kind_from_artifact_id(artifact_id)
        if artifact_kind is None:
            raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
        return self._load_artifact(artifact_kind=artifact_kind, artifact_id=artifact_id)

    def _resolve_from_handoff(self, handoff: RankingArtifactOpenHandoff) -> ResolvedRankingArtifact:
        inferred_artifact_kind = infer_ranking_artifact_kind_from_artifact_id(handoff.artifact_id)
        if inferred_artifact_kind is None:
            raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
        if inferred_artifact_kind != handoff.artifact_kind:
            raise RankingArtifactOpenIdentityMismatchError(
                "ranking artifact handoff artifact_kind does not match artifact_id"
            )
        try:
            validate_ranking_artifact_kind_schema_version(
                artifact_kind=handoff.artifact_kind,
                schema_version=handoff.schema_version,
            )
        except ValueError as exc:
            raise RankingArtifactOpenUnsupportedStateError(str(exc)) from exc
        resolved = self._load_artifact(
            artifact_kind=handoff.artifact_kind,
            artifact_id=handoff.artifact_id,
        )
        if resolved.schema_version != handoff.schema_version:
            raise RankingArtifactOpenIdentityMismatchError(
                "ranking artifact handoff schema_version does not match persisted artifact"
            )
        return resolved

    def _load_artifact(
        self,
        *,
        artifact_kind: RankingArtifactKind,
        artifact_id: str,
    ) -> ResolvedRankingArtifact:
        if artifact_kind == "etf_ranking":
            artifact = load_etf_ranking_artifact(artifact_id, store=self.etf_store)
            if artifact.schema_version != ETF_RANKING_ARTIFACT_SCHEMA_VERSION:
                raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact schema_version")
            return ResolvedRankingArtifact(
                artifact_kind=artifact_kind,
                schema_version=artifact.schema_version,
                artifact=artifact,
            )
        if artifact_kind == "intent_bound_etf_replacement_ranking":
            artifact = load_replacement_ranking_artifact(artifact_id, store=self.replacement_store)
            if artifact.schema_version != INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION:
                raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact schema_version")
            return ResolvedRankingArtifact(
                artifact_kind=artifact_kind,
                schema_version=artifact.schema_version,
                artifact=artifact,
            )
        raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")

    def _assess_replacement_eligibility(
        self,
        resolved: ResolvedRankingArtifact,
    ) -> ReplacementEligibilityAssessment:
        artifact = resolved.artifact
        if not isinstance(artifact, IntentBoundEtfReplacementRankingArtifact):
            raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
        try:
            self._build_replacement_consumer_handoff(artifact)
        except ValueError as exc:
            return ReplacementEligibilityAssessment(
                open_supported=False,
                replay_eligible=False,
                consumer_handoff_supported=False,
                ineligibility_reason=str(exc),
            )
        return ReplacementEligibilityAssessment(
            open_supported=True,
            replay_eligible=True,
            consumer_handoff_supported=True,
        )

    def _build_preflight_eligibility(
        self,
        resolved: ResolvedRankingArtifact,
    ) -> RankingArtifactPreflightEligibility:
        if resolved.artifact_kind != "intent_bound_etf_replacement_ranking":
            return RankingArtifactPreflightEligibility()
        replacement_eligibility = self._assess_replacement_eligibility(resolved)
        return RankingArtifactPreflightEligibility(
            open_supported=replacement_eligibility.open_supported,
            replay_eligible=replacement_eligibility.replay_eligible,
            consumer_handoff_supported=replacement_eligibility.consumer_handoff_supported,
            ineligibility_reason=replacement_eligibility.ineligibility_reason,
        )

    def _build_replacement_consumer_handoff(
        self,
        artifact: IntentBoundEtfReplacementRankingArtifact,
    ) -> IntentBoundEtfReplacementRankingConsumerHandoff:
        try:
            return build_replacement_ranking_consumer_handoff(artifact)
        except ValueError as exc:
            raise RankingArtifactOpenServiceError(str(exc)) from exc


def preflight_ranking_artifact(
    artifact_id: str,
    *,
    service: RankingArtifactOpenService | None = None,
) -> RankingArtifactPreflightResponse:
    if service is not None:
        return service.preflight(artifact_id)
    return RankingArtifactOpenService(
        etf_store=EtfRankingArtifactStore(),
        replacement_store=ReplacementRankingArtifactStore(),
    ).preflight(artifact_id)


def open_ranking_artifact(
    handoff: RankingArtifactOpenHandoff,
    *,
    service: RankingArtifactOpenService | None = None,
) -> RankingArtifactOpenResponse:
    if service is not None:
        return service.open(handoff)
    return RankingArtifactOpenService(
        etf_store=EtfRankingArtifactStore(),
        replacement_store=ReplacementRankingArtifactStore(),
    ).open(handoff)


def _build_review_payload(
    resolved: ResolvedRankingArtifact,
) -> EtfRankingArtifactOpenReviewPayload | IntentBoundEtfReplacementRankingOpenReviewPayload:
    artifact = resolved.artifact
    if resolved.artifact_kind == "etf_ranking":
        if not isinstance(artifact, EtfRankingArtifact):
            raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
        return EtfRankingArtifactOpenReviewPayload(
            artifact_id=artifact.artifact_id,
            artifact=artifact,
        )
    if resolved.artifact_kind == "intent_bound_etf_replacement_ranking":
        if not isinstance(artifact, IntentBoundEtfReplacementRankingArtifact):
            raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
        return IntentBoundEtfReplacementRankingOpenReviewPayload(
            artifact_id=artifact.artifact_id,
            artifact=artifact,
        )
    raise RankingArtifactOpenUnsupportedStateError("unsupported ranking artifact kind")
