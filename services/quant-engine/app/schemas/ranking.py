from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RankingArtifactConfidence = Literal["high", "medium", "low"]
RankingSourceStatus = Literal["sample", "live", "mixed"]


class RankingRequestContextBase(BaseModel):
    universe: list[str] = Field(default_factory=list)
    benchmark_symbol: str | None = None
    lookback_months: int | None = None
    prefer_live_data: bool = False


class RankingEffectiveInputsBase(BaseModel):
    benchmark_symbol: str | None = None
    lookback_months: int | None = None
    price_basis: str | None = None
    requested_universe: list[str] = Field(default_factory=list)
    evaluated_universe: list[str] = Field(default_factory=list)


class RankingRunMetadataBase(BaseModel):
    ranking_id: str
    methodology_id: str
    methodology: str
    as_of_date: str
    ranking_basis_date: str
    price_basis: str | None = None
    confidence: RankingArtifactConfidence


class PersistedRankingArtifactEnvelope(BaseModel):
    artifact_id: str


def validate_ranking_artifact_identity(
    *,
    schema_version: str,
    expected_schema_version: str,
    artifact_id: str,
    artifact_id_prefix: str,
    expected_artifact_id: str,
    artifact_label: str,
) -> None:
    if schema_version != expected_schema_version:
        raise ValueError(f"unsupported {artifact_label} schema_version")
    if not artifact_id.startswith(artifact_id_prefix):
        raise ValueError(f"{artifact_label} artifact_id must use the stable {artifact_id_prefix} prefix")
    if artifact_id != expected_artifact_id:
        raise ValueError(f"{artifact_label} artifact_id does not match canonical artifact content")


def validate_ranking_artifact_storage_key(
    *,
    artifact_id: str,
    artifact_id_prefix: str,
    artifact_label: str,
) -> str:
    if not artifact_id.startswith(artifact_id_prefix):
        raise ValueError(f"{artifact_label} artifact_id must use the stable {artifact_id_prefix} prefix")
    if any(separator in artifact_id for separator in ("/", "\\")):
        raise ValueError(f"{artifact_label} artifact_id must be a stable storage key")
    return artifact_id
