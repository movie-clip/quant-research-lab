from __future__ import annotations

from app.schemas.construction import (
    ConstructionRankingArtifactPreflightArtifact,
    ConstructionRankingArtifactPreflightResponse,
    EtfRankingArtifactConstructionHandoff,
)
from app.services.etf_ranking_artifact_service import EtfRankingArtifactStore, load_etf_ranking_artifact


def preflight_etf_ranking_artifact_for_construction(
    artifact_id: str,
    *,
    store: EtfRankingArtifactStore | None = None,
) -> ConstructionRankingArtifactPreflightResponse:
    artifact = load_etf_ranking_artifact(artifact_id, store=store)
    if artifact.artifact_id != artifact_id:
        raise ValueError("ranking artifact handoff artifact_id does not match persisted artifact")
    if artifact.schema_version != "etf_ranking_artifact_v1":
        raise ValueError("unsupported etf ranking schema_version")
    if not artifact.ranked_universe:
        raise ValueError("persisted etf ranking artifact has no eligible ranked candidates for construction")

    handoff = EtfRankingArtifactConstructionHandoff(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
    )
    return ConstructionRankingArtifactPreflightResponse(
        artifact=ConstructionRankingArtifactPreflightArtifact(
            artifact_id=artifact.artifact_id,
            ranking_id=artifact.ranking_id,
            methodology_id=artifact.run_metadata.methodology_id,
            as_of_date=artifact.run_metadata.as_of_date,
        ),
        handoff=handoff,
    )
