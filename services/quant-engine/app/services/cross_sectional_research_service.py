from __future__ import annotations

from statistics import mean, median
from typing import Literal, cast

from app.schemas.optimizer import OptimizerAlphaPackage
from app.schemas.research import (
    CrossSectionalResearchArtifact,
    CrossSectionalResearchArtifactProvenance,
    CrossSectionalResearchCompactSummary,
    CrossSectionalResearchMethodologyMetadataV1,
    CrossSectionalResearchProvenanceMetadataV1,
    CrossSectionalResearchRequest,
    CrossSectionalResearchStatusMetadataV1,
    CrossSectionalResearchSummaryProvenance,
    CrossSectionalResearchValidationResponse,
)
from app.services.optimizer_alpha_service import build_alpha_quality_package


ALPHA_QUALITY_RESEARCH_METHODOLOGY = (
    "Cross-sectional research family v1: build one canonical alpha-quality signal package, "
    "treat alpha_quality_v1 as the active methodology inside that family, and expose only compact walk-forward and holdout summaries for persisted research review."
)

ALPHA_QUALITY_RESEARCH_ASSUMPTIONS = [
    "Outputs are hypothetical research artifacts only and are not portfolio, trading, or execution truth.",
    "alpha_quality_v1 scores come from deterministic PIT fundamental snapshots using the locked backend alpha package contract.",
    "walk_forward and holdout sections are compact summary partitions for research review and do not claim realized live performance.",
]


def _build_methodology_metadata_v1() -> CrossSectionalResearchMethodologyMetadataV1:
    return CrossSectionalResearchMethodologyMetadataV1(
        methodology_family_id="cross_sectional_research_family_v1",
        methodology_family_version="v1",
        active_methodology_id="alpha_quality_v1",
        active_methodology_version="v1",
        alpha_package_version="alpha_quality_v1",
        alpha_methodology_id="alpha_quality_v1_methodology",
        alpha_input_contract_id="alpha_quality_v1_pit_fundamentals_v1",
        score_basis="optimizer_alpha_package.final_score",
        benchmark_role="descriptive_reference_only",
        partition_rule="effective_date_before_holdout_start_else_holdout",
        output_shape="compact_summary_only",
        component_signal_ids=[
            "profitability",
            "cash_generation",
            "accrual_quality",
            "leverage_discipline",
        ],
    )


def build_cross_sectional_research_validation(
    request: CrossSectionalResearchRequest,
) -> CrossSectionalResearchValidationResponse:
    alpha_package = build_alpha_quality_package(
        rebalance_date=request.rebalance_date,
        as_of_date=request.as_of_date,
        universe_symbols=request.universe_symbols,
        fundamental_snapshots=request.fundamental_snapshots,
        source_name=request.source_name,
        replay_id=request.replay_id,
    )
    walk_forward_symbols = [
        row.symbol
        for row in alpha_package.securities
        if row.effective_date is not None and row.effective_date < request.holdout_start_date
    ]
    holdout_symbols = [
        row.symbol
        for row in alpha_package.securities
        if row.effective_date is not None and row.effective_date >= request.holdout_start_date
    ]
    walk_forward_summary = _build_compact_summary(
        split_label="walk_forward",
        alpha_package=alpha_package,
        request=request,
        included_symbols=walk_forward_symbols,
    )
    holdout_summary = _build_compact_summary(
        split_label="holdout",
        alpha_package=alpha_package,
        request=request,
        included_symbols=holdout_symbols,
    )
    provenance = _build_artifact_provenance(alpha_package=alpha_package, request=request)
    methodology_metadata_v1 = _build_methodology_metadata_v1()
    status_metadata_v1 = _build_status_metadata_v1(alpha_package=alpha_package)
    provenance_metadata_v1 = _build_provenance_metadata_v1(request=request)
    draft_artifact = CrossSectionalResearchArtifact(
        artifact_id="cross_sectional_research_artifact_pending",
        fingerprint="0" * 64,
        run_id=_canonical_run_id(request),
        persisted_at="1970-01-01T00:00:00Z",
        methodology_id=request.methodology_id,
        request=request,
        methodology=ALPHA_QUALITY_RESEARCH_METHODOLOGY,
        methodology_metadata_v1=methodology_metadata_v1,
        status_metadata_v1=status_metadata_v1,
        provenance_metadata_v1=provenance_metadata_v1,
        assumptions=list(ALPHA_QUALITY_RESEARCH_ASSUMPTIONS),
        dataset_version=request.dataset_version,
        universe_definition=request.universe_definition,
        benchmark=request.benchmark,
        walk_forward_summary=walk_forward_summary,
        holdout_summary=holdout_summary,
        provenance=provenance,
    )
    from app.services.cross_sectional_research_artifact_service import build_stable_cross_sectional_research_artifact

    stable_artifact = build_stable_cross_sectional_research_artifact(draft_artifact)
    return CrossSectionalResearchValidationResponse(
        would_persist_artifact_id=stable_artifact.artifact_id,
        would_persist_fingerprint=stable_artifact.fingerprint,
        normalized_request=request,
        methodology=stable_artifact.methodology,
        methodology_metadata_v1=stable_artifact.methodology_metadata_v1,
        status_metadata_v1=stable_artifact.status_metadata_v1,
        provenance_metadata_v1=stable_artifact.provenance_metadata_v1,
        assumptions=stable_artifact.assumptions,
        dataset_version=stable_artifact.dataset_version,
        universe_definition=stable_artifact.universe_definition,
        benchmark=stable_artifact.benchmark,
        walk_forward_summary=stable_artifact.walk_forward_summary,
        holdout_summary=stable_artifact.holdout_summary,
        provenance=stable_artifact.provenance,
    )


def build_cross_sectional_research_artifact(
    request: CrossSectionalResearchRequest,
) -> CrossSectionalResearchArtifact:
    validation = build_cross_sectional_research_validation(request)
    artifact = CrossSectionalResearchArtifact(
        artifact_id=validation.would_persist_artifact_id,
        fingerprint=validation.would_persist_fingerprint,
        run_id=_canonical_run_id(request),
        persisted_at="1970-01-01T00:00:00Z",
        methodology_id=request.methodology_id,
        request=validation.normalized_request,
        methodology=validation.methodology,
        methodology_metadata_v1=validation.methodology_metadata_v1,
        status_metadata_v1=validation.status_metadata_v1,
        provenance_metadata_v1=validation.provenance_metadata_v1,
        assumptions=validation.assumptions,
        dataset_version=validation.dataset_version,
        universe_definition=validation.universe_definition,
        benchmark=validation.benchmark,
        walk_forward_summary=validation.walk_forward_summary,
        holdout_summary=validation.holdout_summary,
        provenance=validation.provenance,
    )
    return artifact


def _build_compact_summary(
    *,
    split_label: Literal["walk_forward", "holdout"],
    alpha_package: OptimizerAlphaPackage,
    request: CrossSectionalResearchRequest,
    included_symbols: list[str],
) -> CrossSectionalResearchCompactSummary:
    included_rows = [row for row in alpha_package.securities if row.symbol in set(included_symbols)]
    scores = [row.final_score for row in included_rows]
    top_ranked_symbols = [row.symbol for row in sorted(included_rows, key=lambda item: item.final_score, reverse=True)[: request.top_ranked_count]]
    date_values = sorted({row.effective_date for row in included_rows if row.effective_date is not None})
    universe_size = len(request.universe_symbols)
    sample_count = len(included_rows)
    return CrossSectionalResearchCompactSummary(
        split_label=cast(Literal["walk_forward", "holdout"], split_label),
        sample_count=sample_count,
        universe_size=universe_size,
        coverage_ratio=(sample_count / universe_size) if universe_size else 0.0,
        complete_coverage_ratio=(sample_count / universe_size) if universe_size else 0.0,
        mean_score=round(mean(scores), 6) if scores else None,
        median_score=round(median(scores), 6) if scores else None,
        positive_score_share=round(sum(1 for value in scores if value > 0) / len(scores), 6) if scores else None,
        top_ranked_symbols=top_ranked_symbols,
        effective_start_date=date_values[0] if date_values else None,
        effective_end_date=date_values[-1] if date_values else None,
        provenance=CrossSectionalResearchSummaryProvenance(
            alpha_package_id=alpha_package.package_id,
            alpha_package_version=alpha_package.version,
            alpha_methodology_id=alpha_package.metadata.methodology_id,
            input_digest=alpha_package.metadata.input_descriptor.input_digest,
            source_name=request.source_name,
            as_of_date=request.as_of_date,
            rebalance_date=request.rebalance_date,
            holdout_start_date=request.holdout_start_date,
            benchmark_symbol=request.benchmark.benchmark_symbol,
            benchmark_kind=request.benchmark.benchmark_kind,
            partition_rule=(
                "Rows with effective_date before holdout_start_date belong to walk_forward; "
                "rows on or after holdout_start_date belong to holdout."
            ),
        ),
    )


def _build_artifact_provenance(
    *,
    alpha_package: OptimizerAlphaPackage,
    request: CrossSectionalResearchRequest,
) -> CrossSectionalResearchArtifactProvenance:
    diagnostics = alpha_package.diagnostics
    return CrossSectionalResearchArtifactProvenance(
        source_name=request.source_name,
        replay_id=request.replay_id,
        input_digest=alpha_package.metadata.input_descriptor.input_digest,
        alpha_input_contract_id=alpha_package.metadata.input_descriptor.contract.contract_id,
        point_in_time_only=alpha_package.metadata.point_in_time_only,
        alpha_package_id=alpha_package.package_id,
        alpha_package_version=alpha_package.version,
        alpha_diagnostics_status=diagnostics.status,
        coverage_ratio=diagnostics.coverage_ratio,
        complete_coverage_ratio=diagnostics.complete_coverage_ratio,
        missing_snapshot_symbols=diagnostics.missing_snapshot_symbols,
        stale_symbols=diagnostics.stale_symbols,
        lag_blocked_symbols=diagnostics.lag_blocked_symbols,
        fallback_symbols=diagnostics.fallback_symbols,
    )


def _build_status_metadata_v1(
    *,
    alpha_package: OptimizerAlphaPackage,
) -> CrossSectionalResearchStatusMetadataV1:
    diagnostics_status = alpha_package.diagnostics.status
    return CrossSectionalResearchStatusMetadataV1(
        artifact_status="complete" if diagnostics_status == "ok" else "degraded",
        diagnostics_status=diagnostics_status,
        coverage_status=(
            "complete" if alpha_package.diagnostics.complete_coverage_ratio >= 1.0 else "partial"
        ),
    )


def _build_provenance_metadata_v1(
    *,
    request: CrossSectionalResearchRequest,
) -> CrossSectionalResearchProvenanceMetadataV1:
    if request.replay_id is not None:
        input_source_kind = "replay_snapshot_input"
        replay_provenance_status = "present"
    elif request.source_name == "direct_snapshot_input":
        input_source_kind = "direct_snapshot_input"
        replay_provenance_status = "absent"
    else:
        input_source_kind = "backend_owned_other"
        replay_provenance_status = "absent"
    return CrossSectionalResearchProvenanceMetadataV1(
        input_source_kind=input_source_kind,
        replay_provenance_status=replay_provenance_status,
        benchmark_source_kind="request_benchmark_reference",
        alpha_source_kind="optimizer_alpha_package",
    )


def _canonical_run_id(request: CrossSectionalResearchRequest) -> str:
    return (
        f"cross_sectional_research_{request.methodology_id}_{request.rebalance_date}_{request.benchmark.benchmark_symbol}"
    )
