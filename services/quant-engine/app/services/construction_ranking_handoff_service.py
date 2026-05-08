from __future__ import annotations

from app.schemas.construction import (
    ConstructionRankingArtifactPreflightResponse,
)
from app.services.construction_run_service import (
    build_construction_preflight_response_from_etf_ranking_artifact,
    build_construction_preflight_response_from_replacement_ranking_artifact,
)
from app.services.etf_ranking_artifact_service import EtfRankingArtifactStore, load_etf_ranking_artifact
from app.services.replacement_ranking_artifact_service import (
    ReplacementRankingArtifactStore,
    load_replacement_ranking_artifact,
)


def preflight_etf_ranking_artifact_for_construction(
    artifact_id: str,
    *,
    store: EtfRankingArtifactStore | None = None,
) -> ConstructionRankingArtifactPreflightResponse:
    artifact = load_etf_ranking_artifact(artifact_id, store=store)
    if artifact.artifact_id != artifact_id:
        raise ValueError("ranking artifact handoff artifact_id does not match persisted artifact")
    return build_construction_preflight_response_from_etf_ranking_artifact(artifact)


def preflight_intent_bound_etf_replacement_ranking_artifact_for_construction(
    artifact_id: str,
    *,
    store: ReplacementRankingArtifactStore | None = None,
) -> ConstructionRankingArtifactPreflightResponse:
    artifact = load_replacement_ranking_artifact(artifact_id, store=store)
    if artifact.artifact_id != artifact_id:
        raise ValueError("ranking artifact handoff artifact_id does not match persisted artifact")
    return build_construction_preflight_response_from_replacement_ranking_artifact(artifact)
