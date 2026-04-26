from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


RankingArtifactConfidence = Literal["high", "medium", "low"]
RankingSourceStatus = Literal["sample", "live", "mixed"]
RankingArtifactKind = Literal["etf_ranking", "intent_bound_etf_replacement_ranking"]
RankingArtifactDiscoveryContractVersion = Literal["ranking_artifact_discovery_v1"]
RankingArtifactKindRegistryVersion = Literal["ranking_artifact_kind_registry_v1"]
RankingArtifactPreflightContractVersion = Literal["ranking_artifact_preflight_v1"]
RankingArtifactOpenContractVersion = Literal["ranking_artifact_open_v1"]
RankingArtifactOpenHandoffKind = Literal["ranking_artifact_open_handoff_v1"]
IntentBoundEtfReplacementRankingConsumerContractVersion = Literal[
    "intent_bound_etf_replacement_ranking_consumer_contract_v1"
]
IntentBoundEtfReplacementRankingConsumerHandoffKind = Literal[
    "intent_bound_etf_replacement_ranking_consumer_handoff_v1"
]
RankingArtifactMetadataTruth = Literal["authoritative_persisted_metadata"]
RankingArtifactMetadataProvenance = Literal["persisted_artifact_body", "persisted_etf_recent_index"]
RankingArtifactRecencySameDayProvenance = Literal["artifact_id", "etf_recent_index"]
RankingArtifactReviewTruthBasis = Literal["authoritative_persisted_ranking_artifact"]
RankingArtifactReviewScope = Literal["artifact_backed_review_only"]
RankingArtifactReviewPayloadKind = Literal[
    "etf_ranking_review_payload_v1",
    "intent_bound_etf_replacement_ranking_review_payload_v1",
]
RankingArtifactSchemaVersion = Literal[
    "etf_ranking_artifact_v1",
    "intent_bound_etf_replacement_ranking_artifact_v1",
]
RankingArtifactDiscoveryFilterName = Literal[
    "artifact_kind",
    "schema_version",
    "metadata_truth",
    "metadata_provenance",
    "recency_same_day_provenance",
    "methodology_id",
    "benchmark_symbol",
    "effective_peer_group",
    "base_symbol",
    "candidate_symbol",
    "peer_group",
    "confidence",
    "status",
    "as_of_date",
    "ranking_basis_date",
    "basis_date",
]
EtfRankingArtifactSchemaVersion = Literal["etf_ranking_artifact_v1"]
IntentBoundEtfReplacementRankingArtifactSchemaVersion = Literal[
    "intent_bound_etf_replacement_ranking_artifact_v1"
]

ETF_RANKING_ARTIFACT_KIND: RankingArtifactKind = "etf_ranking"
INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_KIND: RankingArtifactKind = (
    "intent_bound_etf_replacement_ranking"
)
RANKING_ARTIFACT_KIND_REGISTRY_VERSION: RankingArtifactKindRegistryVersion = "ranking_artifact_kind_registry_v1"
RANKING_ARTIFACT_PREFLIGHT_CONTRACT_VERSION: RankingArtifactPreflightContractVersion = (
    "ranking_artifact_preflight_v1"
)
RANKING_ARTIFACT_OPEN_CONTRACT_VERSION: RankingArtifactOpenContractVersion = "ranking_artifact_open_v1"
RANKING_ARTIFACT_OPEN_HANDOFF_KIND: RankingArtifactOpenHandoffKind = "ranking_artifact_open_handoff_v1"
INTENT_BOUND_ETF_REPLACEMENT_RANKING_CONSUMER_CONTRACT_VERSION: (
    IntentBoundEtfReplacementRankingConsumerContractVersion
) = "intent_bound_etf_replacement_ranking_consumer_contract_v1"
INTENT_BOUND_ETF_REPLACEMENT_RANKING_CONSUMER_HANDOFF_KIND: (
    IntentBoundEtfReplacementRankingConsumerHandoffKind
) = "intent_bound_etf_replacement_ranking_consumer_handoff_v1"
ETF_RANKING_ARTIFACT_SCHEMA_VERSION: EtfRankingArtifactSchemaVersion = "etf_ranking_artifact_v1"
INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION: (
    IntentBoundEtfReplacementRankingArtifactSchemaVersion
) = "intent_bound_etf_replacement_ranking_artifact_v1"
AUTHORITATIVE_PERSISTED_RANKING_ARTIFACT_REVIEW_TRUTH: RankingArtifactReviewTruthBasis = (
    "authoritative_persisted_ranking_artifact"
)
RANKING_ARTIFACT_BACKED_REVIEW_SCOPE: RankingArtifactReviewScope = "artifact_backed_review_only"
ETF_RANKING_REVIEW_PAYLOAD_KIND: RankingArtifactReviewPayloadKind = "etf_ranking_review_payload_v1"
INTENT_BOUND_ETF_REPLACEMENT_RANKING_REVIEW_PAYLOAD_KIND: RankingArtifactReviewPayloadKind = (
    "intent_bound_etf_replacement_ranking_review_payload_v1"
)
RANKING_ARTIFACT_OPEN_HANDOFF_FIELD_NAMES: tuple[str, ...] = (
    "handoff_kind",
    "artifact_kind",
    "artifact_id",
    "schema_version",
)
SUPPORTED_RANKING_ARTIFACT_REVIEW_PAYLOAD_KINDS: tuple[RankingArtifactReviewPayloadKind, ...] = (
    ETF_RANKING_REVIEW_PAYLOAD_KIND,
    INTENT_BOUND_ETF_REPLACEMENT_RANKING_REVIEW_PAYLOAD_KIND,
)
ETF_RANKING_ARTIFACT_ID_PREFIX = "etf_ranking_artifact_"
INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_ID_PREFIX = (
    "intent_bound_etf_replacement_ranking_artifact_"
)
CANONICAL_RANKING_ARTIFACT_SCHEMA_VERSIONS: tuple[RankingArtifactSchemaVersion, ...] = (
    ETF_RANKING_ARTIFACT_SCHEMA_VERSION,
    INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION,
)
DEPRECATED_RANKING_ARTIFACT_SCHEMA_VERSIONS: tuple[RankingArtifactSchemaVersion, ...] = ()
CANONICAL_RANKING_ARTIFACT_SCHEMA_VERSIONS_SET = frozenset(CANONICAL_RANKING_ARTIFACT_SCHEMA_VERSIONS)
DEPRECATED_RANKING_ARTIFACT_SCHEMA_VERSIONS_SET = frozenset(DEPRECATED_RANKING_ARTIFACT_SCHEMA_VERSIONS)

COMMON_RANKING_ARTIFACT_DISCOVERY_FILTERS: tuple[RankingArtifactDiscoveryFilterName, ...] = (
    "artifact_kind",
    "schema_version",
    "metadata_truth",
    "metadata_provenance",
    "recency_same_day_provenance",
    "methodology_id",
    "confidence",
    "as_of_date",
    "ranking_basis_date",
)
ETF_RANKING_DISCOVERY_FILTERS: tuple[RankingArtifactDiscoveryFilterName, ...] = (
    *COMMON_RANKING_ARTIFACT_DISCOVERY_FILTERS,
    "benchmark_symbol",
    "effective_peer_group",
)
INTENT_BOUND_ETF_REPLACEMENT_RANKING_DISCOVERY_FILTERS: tuple[RankingArtifactDiscoveryFilterName, ...] = (
    *COMMON_RANKING_ARTIFACT_DISCOVERY_FILTERS,
    "base_symbol",
    "candidate_symbol",
    "peer_group",
    "status",
    "basis_date",
)


@dataclass(frozen=True)
class RankingArtifactKindRegistryEntry:
    artifact_kind: RankingArtifactKind
    supported_schema_versions: tuple[str, ...]
    supported_filters: tuple[RankingArtifactDiscoveryFilterName, ...]


RANKING_ARTIFACT_KIND_REGISTRY: tuple[RankingArtifactKindRegistryEntry, ...] = (
    RankingArtifactKindRegistryEntry(
        artifact_kind=ETF_RANKING_ARTIFACT_KIND,
        supported_schema_versions=(ETF_RANKING_ARTIFACT_SCHEMA_VERSION,),
        supported_filters=ETF_RANKING_DISCOVERY_FILTERS,
    ),
    RankingArtifactKindRegistryEntry(
        artifact_kind=INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_KIND,
        supported_schema_versions=(INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION,),
        supported_filters=INTENT_BOUND_ETF_REPLACEMENT_RANKING_DISCOVERY_FILTERS,
    ),
)

SUPPORTED_RANKING_ARTIFACT_KINDS: tuple[RankingArtifactKind, ...] = (
    *(entry.artifact_kind for entry in RANKING_ARTIFACT_KIND_REGISTRY),
)

SUPPORTED_RANKING_ARTIFACT_SCHEMA_VERSIONS: tuple[RankingArtifactSchemaVersion, ...] = tuple(
    schema_version
    for schema_version in CANONICAL_RANKING_ARTIFACT_SCHEMA_VERSIONS
    if schema_version not in DEPRECATED_RANKING_ARTIFACT_SCHEMA_VERSIONS_SET
)

SUPPORTED_RANKING_ARTIFACT_DISCOVERY_FILTERS: tuple[RankingArtifactDiscoveryFilterName, ...] = (
    "artifact_kind",
    "schema_version",
    "metadata_truth",
    "metadata_provenance",
    "recency_same_day_provenance",
    "methodology_id",
    "benchmark_symbol",
    "effective_peer_group",
    "base_symbol",
    "candidate_symbol",
    "peer_group",
    "confidence",
    "status",
    "as_of_date",
    "ranking_basis_date",
    "basis_date",
)
SUPPORTED_RANKING_ARTIFACT_DISCOVERY_FILTERS_SET = frozenset(SUPPORTED_RANKING_ARTIFACT_DISCOVERY_FILTERS)

SUPPORTED_RANKING_ARTIFACT_METADATA_PROVENANCE: tuple[RankingArtifactMetadataProvenance, ...] = (
    "persisted_artifact_body",
    "persisted_etf_recent_index",
)


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


def validate_ranking_artifact_supported_schema_versions(
    *,
    artifact_kind: RankingArtifactKind,
    schema_versions: tuple[str, ...],
) -> None:
    if not schema_versions:
        raise ValueError(
            f"ranking artifact registry entry {artifact_kind} must declare supported_schema_versions"
        )

    seen_schema_versions: set[str] = set()
    for schema_version in schema_versions:
        if not isinstance(schema_version, str) or not schema_version or schema_version.strip() != schema_version:
            raise ValueError(
                f"ranking artifact registry entry {artifact_kind} declares malformed schema_version"
            )
        if schema_version in seen_schema_versions:
            raise ValueError(
                f"ranking artifact registry entry {artifact_kind} declares duplicate schema_version {schema_version}"
            )
        if schema_version in DEPRECATED_RANKING_ARTIFACT_SCHEMA_VERSIONS_SET:
            raise ValueError(
                f"ranking artifact registry entry {artifact_kind} declares deprecated schema_version {schema_version}"
            )
        if schema_version not in CANONICAL_RANKING_ARTIFACT_SCHEMA_VERSIONS_SET:
            raise ValueError(
                f"ranking artifact registry entry {artifact_kind} declares unsupported schema_version {schema_version}"
            )
        seen_schema_versions.add(schema_version)


def get_ranking_artifact_kind_registry_entry(
    artifact_kind: RankingArtifactKind,
) -> RankingArtifactKindRegistryEntry | None:
    for entry in RANKING_ARTIFACT_KIND_REGISTRY:
        if entry.artifact_kind == artifact_kind:
            return entry
    return None


def infer_ranking_artifact_kind_from_artifact_id(
    artifact_id: str,
) -> RankingArtifactKind | None:
    artifact_id_prefixes: tuple[tuple[RankingArtifactKind, str], ...] = (
        ("intent_bound_etf_replacement_ranking", INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_ID_PREFIX),
        ("etf_ranking", ETF_RANKING_ARTIFACT_ID_PREFIX),
    )
    for artifact_kind, artifact_id_prefix in artifact_id_prefixes:
        if artifact_id.startswith(artifact_id_prefix):
            return artifact_kind
    return None


def validate_ranking_artifact_kind_schema_version(
    *,
    artifact_kind: RankingArtifactKind,
    schema_version: str,
) -> None:
    registry_entry = get_ranking_artifact_kind_registry_entry(artifact_kind)
    if registry_entry is None:
        raise ValueError("unsupported ranking artifact kind")
    if schema_version not in registry_entry.supported_schema_versions:
        raise ValueError(
            f"schema_version {schema_version} is not supported for ranking artifact kind {artifact_kind}"
        )


def validate_ranking_artifact_discovery_filters(
    *,
    artifact_kind: str | None,
    schema_version: str | None,
    applied_filters: tuple[str, ...],
) -> None:
    normalized_artifact_kind: RankingArtifactKind | None = None
    if artifact_kind is not None:
        if artifact_kind not in SUPPORTED_RANKING_ARTIFACT_KINDS:
            raise ValueError("unsupported ranking artifact kind")
        normalized_artifact_kind = artifact_kind

    if schema_version is not None:
        if schema_version not in SUPPORTED_RANKING_ARTIFACT_SCHEMA_VERSIONS:
            raise ValueError("unsupported ranking artifact schema_version")
        if normalized_artifact_kind is not None:
            registry_entry = get_ranking_artifact_kind_registry_entry(normalized_artifact_kind)
            if registry_entry is None:
                raise ValueError("unsupported ranking artifact kind")
            if schema_version not in registry_entry.supported_schema_versions:
                raise ValueError(
                    f"schema_version {schema_version} is not supported for ranking artifact kind {normalized_artifact_kind}"
                )

    if normalized_artifact_kind is None:
        return

    registry_entry = get_ranking_artifact_kind_registry_entry(normalized_artifact_kind)
    if registry_entry is None:
        raise ValueError("unsupported ranking artifact kind")

    allowed_filters = set(registry_entry.supported_filters)
    for filter_name in applied_filters:
        if filter_name == "artifact_kind":
            continue
        if filter_name not in SUPPORTED_RANKING_ARTIFACT_DISCOVERY_FILTERS_SET:
            raise ValueError(f"unsupported ranking artifact filter {filter_name}")
        if filter_name not in allowed_filters:
            raise ValueError(
                f"filter {filter_name} is not supported for ranking artifact kind {normalized_artifact_kind}"
            )


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
