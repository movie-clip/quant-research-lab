from __future__ import annotations

from dataclasses import dataclass, replace
from functools import cmp_to_key
from typing import Literal, cast

from pydantic import ValidationError

from app.schemas.ranking import (
    CANONICAL_RANKING_ARTIFACT_SCHEMA_VERSIONS,
    ETF_RANKING_ARTIFACT_SCHEMA_VERSION,
    INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION,
    RANKING_ARTIFACT_KIND_REGISTRY,
    RankingArtifactDiscoveryFilterName,
    RankingArtifactKind,
    RankingArtifactKindRegistryEntry,
    RankingArtifactSchemaVersion,
    SUPPORTED_RANKING_ARTIFACT_DISCOVERY_FILTERS,
    SUPPORTED_RANKING_ARTIFACT_KINDS,
    SUPPORTED_RANKING_ARTIFACT_SCHEMA_VERSIONS,
    validate_ranking_artifact_discovery_filters,
    validate_ranking_artifact_supported_schema_versions,
)
from app.schemas.research import (
    EtfRankingArtifact,
    EtfRankingArtifactRecentRow,
    IntentBoundEtfReplacementRankingArtifact,
    RankingArtifactCatalogEtfSummary,
    RankingArtifactCatalogListResponse,
    RankingArtifactCatalogMetadata,
    RankingArtifactCatalogReplacementSummary,
    RankingArtifactCatalogRow,
    RankingArtifactCatalogRowMetadata,
    RankingArtifactDiscoveryFilters,
    RankingArtifactKindCapabilities,
)
from app.services.etf_ranking_artifact_service import (
    EtfRankingArtifactMissingFileError,
    EtfRankingArtifactStore,
    list_recent_etf_ranking_artifacts_strict,
    load_etf_ranking_artifact,
)
from app.services.replacement_ranking_artifact_service import (
    ReplacementRankingArtifactStore,
    load_replacement_ranking_artifact,
)


class RankingArtifactCatalogServiceError(ValueError):
    pass


class RankingArtifactCatalogUnsupportedStateError(RankingArtifactCatalogServiceError):
    pass


class RankingArtifactCatalogMalformedMetadataError(RankingArtifactCatalogServiceError):
    pass


ETF_RANKING_KIND = cast(RankingArtifactKind, "etf_ranking")
REPLACEMENT_RANKING_KIND = cast(RankingArtifactKind, "intent_bound_etf_replacement_ranking")
PERSISTED_ARTIFACT_BODY_PROVENANCE = cast(Literal["persisted_artifact_body", "persisted_etf_recent_index"], "persisted_artifact_body")
PERSISTED_ETF_RECENT_INDEX_PROVENANCE = cast(Literal["persisted_artifact_body", "persisted_etf_recent_index"], "persisted_etf_recent_index")
ARTIFACT_ID_RECENCY_PROVENANCE = cast(Literal["artifact_id", "etf_recent_index"], "artifact_id")
ETF_RECENT_INDEX_RECENCY_PROVENANCE = cast(Literal["artifact_id", "etf_recent_index"], "etf_recent_index")
SUPPORTED_DISCOVERY_FILTERS_SET = frozenset(SUPPORTED_RANKING_ARTIFACT_DISCOVERY_FILTERS)


@dataclass(frozen=True)
class PersistedRankingArtifactMetadataRow:
    artifact_kind: RankingArtifactKind
    artifact_id: str
    schema_version: RankingArtifactSchemaVersion
    ranking_id: str
    methodology_id: str
    as_of_date: str
    ranking_basis_date: str
    recent_order_primary_date: str
    recent_order_secondary_date: str
    recent_order_artifact_id: str
    metadata_provenance: Literal["persisted_artifact_body", "persisted_etf_recent_index"]
    matched_metadata_provenance: Literal["persisted_artifact_body", "persisted_etf_recent_index"]
    recency_same_day_provenance: Literal["artifact_id", "etf_recent_index"]
    etf_summary: RankingArtifactCatalogEtfSummary | None = None
    replacement_summary: RankingArtifactCatalogReplacementSummary | None = None

    def to_catalog_row(self) -> RankingArtifactCatalogRow:
        return RankingArtifactCatalogRow(
            artifact_kind=self.artifact_kind,
            artifact_id=self.artifact_id,
            schema_version=self.schema_version,
            ranking_id=self.ranking_id,
            methodology_id=self.methodology_id,
            as_of_date=self.as_of_date,
            ranking_basis_date=self.ranking_basis_date,
            recent_order_primary_date=self.recent_order_primary_date,
            recent_order_secondary_date=self.recent_order_secondary_date,
            recent_order_artifact_id=self.recent_order_artifact_id,
            metadata=RankingArtifactCatalogRowMetadata(
                metadata_provenance=self.metadata_provenance,
                matched_metadata_provenance=self.matched_metadata_provenance,
                recency_same_day_provenance=self.recency_same_day_provenance,
            ),
            etf_summary=self.etf_summary,
            replacement_summary=self.replacement_summary,
        )


class RankingArtifactCatalogService:
    def __init__(
        self,
        *,
        etf_store: EtfRankingArtifactStore | None = None,
        replacement_store: ReplacementRankingArtifactStore | None = None,
    ) -> None:
        self.etf_store = etf_store or EtfRankingArtifactStore()
        self.replacement_store = replacement_store or ReplacementRankingArtifactStore()

    def list_catalog(
        self,
        *,
        filters: RankingArtifactDiscoveryFilters | None = None,
    ) -> RankingArtifactCatalogListResponse:
        normalized_filters = _normalize_filters(filters)
        registry = get_ranking_artifact_kind_capabilities()
        rows: list[RankingArtifactCatalogRow] = []
        etf_same_day_order: dict[str, int] = {}

        if normalized_filters.artifact_kind in (None, "etf_ranking"):
            etf_same_day_order = self._load_recent_etf_same_day_order(filters=normalized_filters)
            rows.extend(self._list_all_etf_rows(filters=normalized_filters))
        if normalized_filters.artifact_kind in (None, "intent_bound_etf_replacement_ranking"):
            rows.extend(self._list_all_replacement_rows(filters=normalized_filters))

        return RankingArtifactCatalogListResponse(
            items=_sort_catalog_rows_for_catalog(rows, etf_same_day_order=etf_same_day_order),
            metadata=RankingArtifactCatalogMetadata(
                applied_filters=normalized_filters,
                artifact_kind_registry=registry,
            ),
        )

    def list_recent(
        self,
        *,
        limit: int,
        filters: RankingArtifactDiscoveryFilters | None = None,
    ) -> RankingArtifactCatalogListResponse:
        normalized_filters = _normalize_filters(filters)
        registry = get_ranking_artifact_kind_capabilities()
        if limit < 1:
            return RankingArtifactCatalogListResponse(
                items=[],
                metadata=RankingArtifactCatalogMetadata(
                    applied_filters=normalized_filters,
                    artifact_kind_registry=registry,
                ),
            )

        rows: list[RankingArtifactCatalogRow] = []
        if normalized_filters.artifact_kind in (None, "etf_ranking"):
            rows.extend(self._list_recent_etf_rows(filters=normalized_filters))
        if normalized_filters.artifact_kind in (None, "intent_bound_etf_replacement_ranking"):
            rows.extend(self._list_all_replacement_rows(filters=normalized_filters))

        return RankingArtifactCatalogListResponse(
            items=_sort_catalog_rows(rows, preserve_same_day_input_order=True)[:limit],
            metadata=RankingArtifactCatalogMetadata(
                applied_filters=normalized_filters,
                artifact_kind_registry=registry,
            ),
        )

    def _load_recent_etf_same_day_order(self, *, filters: RankingArtifactDiscoveryFilters) -> dict[str, int]:
        rows = list_recent_etf_ranking_artifacts_strict(limit=2**31 - 1, store=self.etf_store)
        order_filters = filters.model_copy(
            update={
                "metadata_truth": None,
                "metadata_provenance": None,
            }
        )
        metadata_rows = [_build_etf_recent_metadata_row(row) for row in rows]
        filtered_rows = [row for row in metadata_rows if _matches_filters(row, order_filters)]
        return {row.artifact_id: index for index, row in enumerate(filtered_rows)}

    def _list_all_etf_rows(self, *, filters: RankingArtifactDiscoveryFilters) -> list[RankingArtifactCatalogRow]:
        rows: list[RankingArtifactCatalogRow] = []
        for artifact_path in sorted(self.etf_store.base_dir.glob("*.json")):
            metadata_row = _build_etf_artifact_metadata_row(
                load_etf_ranking_artifact(artifact_path.stem, store=self.etf_store)
            )
            if _matches_filters(metadata_row, filters):
                rows.append(metadata_row.to_catalog_row())
        return _sort_rows_with_metadata_tiebreak(rows)

    def _list_recent_etf_rows(self, *, filters: RankingArtifactDiscoveryFilters) -> list[RankingArtifactCatalogRow]:
        rows: list[RankingArtifactCatalogRow] = []
        recent_rows = list_recent_etf_ranking_artifacts_strict(limit=2**31 - 1, store=self.etf_store)
        for recent_row in recent_rows:
            metadata_row = _build_etf_recent_metadata_row(recent_row)
            if not _matches_filters(metadata_row, filters):
                continue
            artifact_metadata_row = _build_etf_artifact_metadata_row(
                load_etf_ranking_artifact(recent_row.artifact_id, store=self.etf_store)
            )
            if artifact_metadata_row.metadata_provenance != "persisted_artifact_body":
                raise RankingArtifactCatalogUnsupportedStateError("unsupported etf metadata provenance")
            _validate_etf_recent_index_artifact_alignment(
                recent_row=metadata_row,
                artifact_row=artifact_metadata_row,
            )
            rows.append(
                replace(
                    artifact_metadata_row,
                    matched_metadata_provenance=metadata_row.matched_metadata_provenance,
                ).to_catalog_row()
            )
        return rows

    def _list_all_replacement_rows(self, *, filters: RankingArtifactDiscoveryFilters) -> list[RankingArtifactCatalogRow]:
        rows: list[RankingArtifactCatalogRow] = []
        for artifact_path in sorted(self.replacement_store.base_dir.glob("*.json")):
            metadata_row = _build_replacement_artifact_metadata_row(
                load_replacement_ranking_artifact(artifact_path.stem, store=self.replacement_store)
            )
            if _matches_filters(metadata_row, filters):
                rows.append(metadata_row.to_catalog_row())
        return _sort_rows_with_metadata_tiebreak(rows)


def list_ranking_artifact_catalog(
    *,
    filters: RankingArtifactDiscoveryFilters | None = None,
    service: RankingArtifactCatalogService | None = None,
) -> RankingArtifactCatalogListResponse:
    normalized_filters = _normalize_filters(filters)
    return (service or RankingArtifactCatalogService()).list_catalog(filters=normalized_filters)


def list_recent_ranking_artifacts(
    *,
    limit: int,
    filters: RankingArtifactDiscoveryFilters | None = None,
    service: RankingArtifactCatalogService | None = None,
) -> RankingArtifactCatalogListResponse:
    normalized_filters = _normalize_filters(filters)
    return (service or RankingArtifactCatalogService()).list_recent(limit=limit, filters=normalized_filters)


def get_ranking_artifact_kind_capabilities() -> list[RankingArtifactKindCapabilities]:
    capabilities: list[RankingArtifactKindCapabilities] = []
    seen_kinds: set[str] = set()
    for entry in RANKING_ARTIFACT_KIND_REGISTRY:
        _validate_registry_entry(entry)
        if entry.artifact_kind in seen_kinds:
            raise RankingArtifactCatalogMalformedMetadataError(
                f"duplicate ranking artifact registry entry for kind {entry.artifact_kind}"
            )
        seen_kinds.add(entry.artifact_kind)
        capabilities.append(
            RankingArtifactKindCapabilities(
                artifact_kind=entry.artifact_kind,
                supported_schema_versions=list(entry.supported_schema_versions),
                supported_filters=list(entry.supported_filters),
            )
        )
    if set(seen_kinds) != set(SUPPORTED_RANKING_ARTIFACT_KINDS):
        raise RankingArtifactCatalogMalformedMetadataError("ranking artifact registry kinds do not match supported kinds")
    return capabilities


def _normalize_filters(filters: RankingArtifactDiscoveryFilters | None) -> RankingArtifactDiscoveryFilters:
    normalized = filters or RankingArtifactDiscoveryFilters()
    if normalized.metadata_truth is not None and normalized.metadata_truth != "authoritative_persisted_metadata":
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact metadata_truth")
    if normalized.metadata_provenance is not None and normalized.metadata_provenance not in {
        "persisted_artifact_body",
        "persisted_etf_recent_index",
    }:
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact metadata_provenance")
    if normalized.recency_same_day_provenance is not None and normalized.recency_same_day_provenance not in {
        "artifact_id",
        "etf_recent_index",
    }:
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact recency_same_day_provenance")
    if normalized.schema_version is not None and normalized.schema_version not in SUPPORTED_RANKING_ARTIFACT_SCHEMA_VERSIONS:
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact schema_version")
    try:
        validate_ranking_artifact_discovery_filters(
            artifact_kind=normalized.artifact_kind,
            schema_version=normalized.schema_version,
            applied_filters=tuple(_applied_filter_names(normalized)),
        )
    except ValueError as exc:
        raise RankingArtifactCatalogUnsupportedStateError(str(exc)) from exc
    return normalized


def _validate_artifact_kind(artifact_kind: RankingArtifactKind | None) -> None:
    if artifact_kind is None:
        return
    if artifact_kind not in SUPPORTED_RANKING_ARTIFACT_KINDS:
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact kind")


def _normalize_artifact_kind(artifact_kind: str | None) -> RankingArtifactKind | None:
    if artifact_kind is None:
        return None
    if artifact_kind not in SUPPORTED_RANKING_ARTIFACT_KINDS:
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact kind")
    return cast(RankingArtifactKind, artifact_kind)


def _validate_registry_entry(entry: RankingArtifactKindRegistryEntry) -> None:
    if entry.artifact_kind not in SUPPORTED_RANKING_ARTIFACT_KINDS:
        raise RankingArtifactCatalogMalformedMetadataError("unsupported ranking artifact registry kind")
    try:
        validate_ranking_artifact_supported_schema_versions(
            artifact_kind=entry.artifact_kind,
            schema_versions=entry.supported_schema_versions,
        )
    except ValueError as exc:
        raise RankingArtifactCatalogMalformedMetadataError(str(exc)) from exc
    if not entry.supported_filters:
        raise RankingArtifactCatalogMalformedMetadataError(
            f"ranking artifact registry entry {entry.artifact_kind} must declare supported_filters"
        )
    for filter_name in entry.supported_filters:
        if filter_name not in SUPPORTED_DISCOVERY_FILTERS_SET:
            raise RankingArtifactCatalogMalformedMetadataError(
                f"ranking artifact registry entry {entry.artifact_kind} declares unsupported filter {filter_name}"
            )

    unknown_supported_versions = set(SUPPORTED_RANKING_ARTIFACT_SCHEMA_VERSIONS) - set(CANONICAL_RANKING_ARTIFACT_SCHEMA_VERSIONS)
    if unknown_supported_versions:
        raise RankingArtifactCatalogMalformedMetadataError(
            "ranking artifact supported schema versions diverge from canonical allowlist"
        )


def _supported_filters_for_kind(artifact_kind: RankingArtifactKind | None) -> set[RankingArtifactDiscoveryFilterName]:
    if artifact_kind is None:
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact kind")
    for entry in RANKING_ARTIFACT_KIND_REGISTRY:
        if entry.artifact_kind == artifact_kind:
            _validate_registry_entry(entry)
            return set(entry.supported_filters)
    raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact kind")


def _applied_filter_names(filters: RankingArtifactDiscoveryFilters) -> list[RankingArtifactDiscoveryFilterName]:
    return [
        cast(RankingArtifactDiscoveryFilterName, field_name)
        for field_name, value in filters.model_dump().items()
        if value is not None
    ]


def _build_etf_artifact_metadata_row(artifact: EtfRankingArtifact) -> PersistedRankingArtifactMetadataRow:
    if artifact.schema_version != ETF_RANKING_ARTIFACT_SCHEMA_VERSION:
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact schema_version")
    return PersistedRankingArtifactMetadataRow(
        artifact_kind=ETF_RANKING_KIND,
        artifact_id=artifact.artifact_id,
        schema_version=artifact.schema_version,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.as_of_date,
        ranking_basis_date=artifact.run_metadata.ranking_basis_date,
        recent_order_primary_date=artifact.run_metadata.ranking_basis_date,
        recent_order_secondary_date=artifact.as_of_date,
        recent_order_artifact_id=artifact.artifact_id,
        metadata_provenance=PERSISTED_ARTIFACT_BODY_PROVENANCE,
        matched_metadata_provenance=PERSISTED_ARTIFACT_BODY_PROVENANCE,
        recency_same_day_provenance=ETF_RECENT_INDEX_RECENCY_PROVENANCE,
        etf_summary=RankingArtifactCatalogEtfSummary(
            benchmark_symbol=artifact.benchmark_symbol,
            lookback_months=artifact.lookback_months,
            effective_peer_group=artifact.effective_peer_group,
            universe_size=len(artifact.universe),
            evaluated_universe_size=len(artifact.ranked_universe),
            confidence=artifact.warnings.confidence,
        ),
        replacement_summary=None,
    )


def _build_replacement_artifact_metadata_row(
    artifact: IntentBoundEtfReplacementRankingArtifact,
) -> PersistedRankingArtifactMetadataRow:
    if artifact.schema_version != INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION:
        raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact schema_version")
    return PersistedRankingArtifactMetadataRow(
        artifact_kind=REPLACEMENT_RANKING_KIND,
        artifact_id=artifact.artifact_id,
        schema_version=artifact.schema_version,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
        ranking_basis_date=artifact.run_metadata.ranking_basis_date,
        recent_order_primary_date=artifact.run_metadata.ranking_basis_date,
        recent_order_secondary_date=artifact.run_metadata.as_of_date,
        recent_order_artifact_id=artifact.artifact_id,
        metadata_provenance=PERSISTED_ARTIFACT_BODY_PROVENANCE,
        matched_metadata_provenance=PERSISTED_ARTIFACT_BODY_PROVENANCE,
        recency_same_day_provenance=ARTIFACT_ID_RECENCY_PROVENANCE,
        etf_summary=None,
        replacement_summary=RankingArtifactCatalogReplacementSummary(
            basis_date=artifact.basis_date,
            status=artifact.status,
            base_symbol=artifact.lineage.base_symbol,
            candidate_symbol=artifact.lineage.candidate_symbol,
            peer_group=artifact.lineage.peer_group,
            eligible_count=artifact.eligible_count,
            excluded_count=artifact.excluded_count,
            confidence=artifact.run_metadata.confidence,
        ),
    )


def _build_etf_recent_metadata_row(recent_row: EtfRankingArtifactRecentRow) -> PersistedRankingArtifactMetadataRow:
    try:
        validated = RankingArtifactCatalogEtfSummary(
            benchmark_symbol=recent_row.benchmark_symbol,
            lookback_months=recent_row.lookback_months,
            effective_peer_group=recent_row.effective_peer_group,
            universe_size=recent_row.universe_size,
            evaluated_universe_size=recent_row.evaluated_universe_size,
            confidence=recent_row.confidence,
        )
    except ValidationError as exc:
        raise RankingArtifactCatalogMalformedMetadataError("malformed persisted etf recent metadata state") from exc
    return PersistedRankingArtifactMetadataRow(
        artifact_kind=ETF_RANKING_KIND,
        artifact_id=recent_row.artifact_id,
        schema_version=ETF_RANKING_ARTIFACT_SCHEMA_VERSION,
        ranking_id=recent_row.ranking_id,
        methodology_id=recent_row.methodology_id,
        as_of_date=recent_row.as_of_date,
        ranking_basis_date=recent_row.ranking_basis_date,
        recent_order_primary_date=recent_row.ranking_basis_date,
        recent_order_secondary_date=recent_row.as_of_date,
        recent_order_artifact_id=recent_row.artifact_id,
        metadata_provenance=PERSISTED_ETF_RECENT_INDEX_PROVENANCE,
        matched_metadata_provenance=PERSISTED_ETF_RECENT_INDEX_PROVENANCE,
        recency_same_day_provenance=ETF_RECENT_INDEX_RECENCY_PROVENANCE,
        etf_summary=validated,
        replacement_summary=None,
    )


def _validate_etf_recent_index_artifact_alignment(
    *,
    recent_row: PersistedRankingArtifactMetadataRow,
    artifact_row: PersistedRankingArtifactMetadataRow,
) -> None:
    recent_summary = recent_row.etf_summary
    artifact_summary = artifact_row.etf_summary
    if recent_summary is None or artifact_summary is None:
        raise RankingArtifactCatalogMalformedMetadataError("malformed persisted etf metadata state")

    contradictory_fields: list[str] = []
    for field_name in (
        "artifact_id",
        "ranking_id",
        "methodology_id",
        "as_of_date",
        "ranking_basis_date",
        "recent_order_primary_date",
        "recent_order_secondary_date",
        "recent_order_artifact_id",
    ):
        if getattr(recent_row, field_name) != getattr(artifact_row, field_name):
            contradictory_fields.append(field_name)

    for field_name in (
        "benchmark_symbol",
        "lookback_months",
        "effective_peer_group",
        "universe_size",
        "evaluated_universe_size",
        "confidence",
    ):
        if getattr(recent_summary, field_name) != getattr(artifact_summary, field_name):
            contradictory_fields.append(f"etf_summary.{field_name}")

    if contradictory_fields:
        raise RankingArtifactCatalogMalformedMetadataError(
            "persisted etf recent index metadata contradicts persisted artifact metadata: "
            + ", ".join(contradictory_fields)
        )


def _matches_filters(row: PersistedRankingArtifactMetadataRow, filters: RankingArtifactDiscoveryFilters) -> bool:
    if filters.artifact_kind is not None and row.artifact_kind != filters.artifact_kind:
        return False
    if filters.schema_version is not None and row.schema_version != filters.schema_version:
        return False
    if filters.metadata_truth is not None and filters.metadata_truth != "authoritative_persisted_metadata":
        return False
    if filters.metadata_provenance is not None and row.metadata_provenance != filters.metadata_provenance:
        return False
    if (
        filters.recency_same_day_provenance is not None
        and row.recency_same_day_provenance != filters.recency_same_day_provenance
    ):
        return False
    if filters.methodology_id is not None and row.methodology_id != filters.methodology_id:
        return False
    if filters.confidence is not None and _row_confidence(row) != filters.confidence:
        return False
    if filters.as_of_date is not None and row.as_of_date != filters.as_of_date:
        return False
    if filters.ranking_basis_date is not None and row.ranking_basis_date != filters.ranking_basis_date:
        return False

    if row.artifact_kind == "etf_ranking":
        summary = row.etf_summary
        if summary is None:
            raise RankingArtifactCatalogMalformedMetadataError("malformed persisted etf metadata state")
        if filters.benchmark_symbol is not None and summary.benchmark_symbol != filters.benchmark_symbol:
            return False
        if filters.effective_peer_group is not None and summary.effective_peer_group != filters.effective_peer_group:
            return False
        if any(
            value is not None
            for value in (filters.base_symbol, filters.candidate_symbol, filters.peer_group, filters.status, filters.basis_date)
        ):
            return False
        return True

    if row.artifact_kind == "intent_bound_etf_replacement_ranking":
        summary = row.replacement_summary
        if summary is None:
            raise RankingArtifactCatalogMalformedMetadataError("malformed persisted replacement metadata state")
        if filters.base_symbol is not None and summary.base_symbol != filters.base_symbol:
            return False
        if filters.candidate_symbol is not None and summary.candidate_symbol != filters.candidate_symbol:
            return False
        if filters.peer_group is not None and summary.peer_group != filters.peer_group:
            return False
        if filters.status is not None and summary.status != filters.status:
            return False
        if filters.basis_date is not None and summary.basis_date != filters.basis_date:
            return False
        if filters.benchmark_symbol is not None or filters.effective_peer_group is not None:
            return False
        return True

    raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact kind")


def _row_confidence(row: PersistedRankingArtifactMetadataRow) -> str:
    if row.artifact_kind == "etf_ranking":
        if row.etf_summary is None:
            raise RankingArtifactCatalogMalformedMetadataError("malformed persisted etf metadata state")
        return row.etf_summary.confidence
    if row.artifact_kind == "intent_bound_etf_replacement_ranking":
        if row.replacement_summary is None:
            raise RankingArtifactCatalogMalformedMetadataError("malformed persisted replacement metadata state")
        return row.replacement_summary.confidence
    raise RankingArtifactCatalogUnsupportedStateError("unsupported ranking artifact kind")


def _sort_rows_with_metadata_tiebreak(rows: list[RankingArtifactCatalogRow]) -> list[RankingArtifactCatalogRow]:
    return sorted(
        rows,
        key=lambda row: (
            row.recent_order_primary_date,
            row.recent_order_secondary_date,
            row.recent_order_artifact_id,
        ),
        reverse=True,
    )


def _sort_catalog_rows(
    rows: list[RankingArtifactCatalogRow],
    *,
    preserve_same_day_input_order: bool,
) -> list[RankingArtifactCatalogRow]:
    if not preserve_same_day_input_order:
        return _sort_rows_with_metadata_tiebreak(rows)
    return sorted(
        rows,
        key=lambda row: (
            row.recent_order_primary_date,
            row.recent_order_secondary_date,
        ),
        reverse=True,
    )


def _sort_catalog_rows_for_catalog(
    rows: list[RankingArtifactCatalogRow],
    *,
    etf_same_day_order: dict[str, int],
) -> list[RankingArtifactCatalogRow]:
    return sorted(rows, key=cmp_to_key(lambda left, right: _compare_catalog_rows(left, right, etf_same_day_order)))


def _compare_catalog_rows(
    left: RankingArtifactCatalogRow,
    right: RankingArtifactCatalogRow,
    etf_same_day_order: dict[str, int],
) -> int:
    if left.recent_order_primary_date != right.recent_order_primary_date:
        return -1 if left.recent_order_primary_date > right.recent_order_primary_date else 1
    if left.recent_order_secondary_date != right.recent_order_secondary_date:
        return -1 if left.recent_order_secondary_date > right.recent_order_secondary_date else 1

    if left.artifact_kind == right.artifact_kind == "etf_ranking":
        left_index = etf_same_day_order.get(left.artifact_id)
        right_index = etf_same_day_order.get(right.artifact_id)
        if left_index is not None and right_index is not None and left_index != right_index:
            return -1 if left_index < right_index else 1

    if left.recent_order_artifact_id == right.recent_order_artifact_id:
        return 0
    return -1 if left.recent_order_artifact_id > right.recent_order_artifact_id else 1
