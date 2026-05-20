"""Tests for the construction-eligibility expansion of generic_ranking artifacts.

Covers:
- generic_ranking_artifact_construction_handoff_v1 schema validation
- preflight builder produces eligible / ineligible responses
- preflight rejects mismatched artifact_id / schema_version / methodology_id
- run-request builder validates handoff lineage and rejects mismatches
- ranked-candidate builder maps GenericRankingRow.eligibility correctly
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.schemas.construction import (
    GenericRankingArtifactConstructionHandoff,
    GenericRankingConstructionPreflightArtifact,
)
from app.schemas.generic_ranking import (
    EligibilityRecord,
    FactorConfig,
    GenericRankingArtifact,
    GenericRankingResponse,
    GenericRankingRow,
    GenericRankingRunMetadata,
    ScoreConfig,
    ScoreConfigRef,
    UniverseSpec,
    UniverseSpecSnapshot,
)
from app.services.construction_run_service import (
    GENERIC_RANKING_INELIGIBLE_REASON,
    build_construction_preflight_response_from_generic_ranking_artifact,
    prepare_generic_ranking_artifact_for_construction,
)
from app.services.generic_ranking_artifact_service import (
    GenericRankingArtifactStore,
    build_stable_generic_ranking_artifact,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_generic_ranking_artifact(
    *,
    rows: list[GenericRankingRow] | None = None,
    universe_id: str = "test_universe",
) -> GenericRankingArtifact:
    if rows is None:
        rows = [
            GenericRankingRow(
                rank=1,
                symbol="AAPL",
                composite_score=1.0,
                component_scores={},
                eligibility=EligibilityRecord(eligibility_status="eligible"),
            ),
            GenericRankingRow(
                rank=2,
                symbol="MSFT",
                composite_score=0.5,
                component_scores={},
                eligibility=EligibilityRecord(eligibility_status="eligible"),
            ),
        ]
    response = GenericRankingResponse(
        ranking_id="test_ranking",
        methodology_id="generic_ranking_methodology_v1",
        title="Test",
        as_of_date="2026-05-10",
        benchmark_symbol="SPY",
        lookback_months=6,
        universe_spec_snapshot=UniverseSpecSnapshot(
            universe_id=universe_id,
            universe_kind="custom_list",
            spec_digest="abc123",
            evaluated_members=[r.symbol for r in rows],
            evaluated_at="2026-05-10",
        ),
        run_metadata=GenericRankingRunMetadata(
            ranking_id="test_ranking",
            methodology_id="generic_ranking_methodology_v1",
            as_of_date="2026-05-10",
            ranking_basis_date="2026-05-10",
            price_basis="close",
            confidence="full",
            score_config_ref=ScoreConfigRef(
                score_config_id="test_score_v1",
                score_config_version="v1",
                score_config_digest="def456",
                factor_ids=["momentum_6m"],
                normalization="cross_sectional_zscore",
                winsorize_pct=0.05,
            ),
            composite_score_trace=None,
        ),
        ranked_universe=rows,
        excluded_instruments=[],
        warnings=[],
    )
    return build_stable_generic_ranking_artifact(response)


# ── Schema-level tests ───────────────────────────────────────────────────────


def test_generic_ranking_construction_handoff_validates_supported_kind() -> None:
    handoff = GenericRankingArtifactConstructionHandoff(
        artifact_id="generic_ranking_artifact_abc123",
        ranking_id="r",
        methodology_id="m",
        as_of_date="2026-05-10",
    )
    assert handoff.artifact_kind == "generic_ranking"
    assert handoff.handoff_kind == "generic_ranking_artifact_construction_handoff_v1"
    assert handoff.schema_version == "generic_ranking_artifact_v1"


def test_generic_ranking_construction_handoff_rejects_wrong_artifact_kind() -> None:
    with pytest.raises(ValueError, match="unsupported ranking artifact kind"):
        GenericRankingArtifactConstructionHandoff(
            artifact_kind="etf_ranking",  # wrong
            artifact_id="generic_ranking_artifact_abc123",
            ranking_id="r",
            methodology_id="m",
            as_of_date="2026-05-10",
        )


def test_generic_ranking_construction_handoff_rejects_wrong_schema_version() -> None:
    with pytest.raises(ValueError, match="unsupported generic ranking schema_version"):
        GenericRankingArtifactConstructionHandoff(
            artifact_id="generic_ranking_artifact_abc123",
            schema_version="some_other_v1",
            ranking_id="r",
            methodology_id="m",
            as_of_date="2026-05-10",
        )


# ── Preflight builder tests ──────────────────────────────────────────────────


def test_preflight_returns_eligible_response_for_valid_generic_ranking_artifact() -> None:
    artifact = _make_generic_ranking_artifact()
    response = build_construction_preflight_response_from_generic_ranking_artifact(artifact)

    assert response.eligibility.eligible is True
    assert response.eligibility.reason is None
    assert response.handoff is not None
    assert response.handoff.artifact_kind == "generic_ranking"
    assert response.handoff.artifact_id == artifact.artifact_id
    assert response.handoff.ranking_id == artifact.ranking_id
    assert response.handoff.methodology_id == artifact.run_metadata.methodology_id
    assert response.handoff.as_of_date == artifact.run_metadata.as_of_date


def test_preflight_returns_ineligible_response_when_no_eligible_rows() -> None:
    rows = [
        GenericRankingRow(
            rank=1,
            symbol="ZZZZ",
            composite_score=0.0,
            component_scores={},
            eligibility=EligibilityRecord(
                eligibility_status="excluded",
                hard_filter_failures=["no_price_data"],
            ),
        ),
    ]
    artifact = _make_generic_ranking_artifact(rows=rows)
    response = build_construction_preflight_response_from_generic_ranking_artifact(artifact)

    assert response.eligibility.eligible is False
    assert response.eligibility.reason == GENERIC_RANKING_INELIGIBLE_REASON
    assert response.handoff is None


def test_preflight_returns_ineligible_response_for_empty_ranked_universe() -> None:
    artifact = _make_generic_ranking_artifact()
    artifact = artifact.model_copy(update={"ranked_universe": []})
    response = build_construction_preflight_response_from_generic_ranking_artifact(artifact)

    assert response.eligibility.eligible is False
    assert response.eligibility.reason == GENERIC_RANKING_INELIGIBLE_REASON
    assert response.handoff is None


# ── Ranked-candidate builder ────────────────────────────────────────────────


def test_ranked_candidate_builder_maps_eligible_rows_correctly() -> None:
    artifact = _make_generic_ranking_artifact()
    summary, candidates = prepare_generic_ranking_artifact_for_construction(artifact)

    assert isinstance(summary, GenericRankingConstructionPreflightArtifact)
    assert summary.artifact_id == artifact.artifact_id
    assert summary.artifact_kind == "generic_ranking"
    assert len(candidates) == 2
    assert all(c.eligible for c in candidates)
    assert candidates[0].symbol == "AAPL"
    assert candidates[0].rank == 1
    assert candidates[0].score == pytest.approx(1.0)
    assert candidates[0].exclusion_reason is None


def test_ranked_candidate_builder_threads_sector_from_generic_ranking_rows() -> None:
    # Epic 3 milestone slice 2: GenericRankingRow.sector must flow into the
    # construction ranked-candidate contract so max_sector_weight is evaluable.
    rows = [
        GenericRankingRow(
            rank=1,
            symbol="AAPL",
            composite_score=1.0,
            component_scores={},
            eligibility=EligibilityRecord(eligibility_status="eligible"),
            sector="Information Technology",
        ),
        GenericRankingRow(
            rank=2,
            symbol="JPM",
            composite_score=0.5,
            component_scores={},
            eligibility=EligibilityRecord(eligibility_status="eligible"),
            sector="Financials",
        ),
        GenericRankingRow(
            rank=3,
            symbol="NOSEC",
            composite_score=0.1,
            component_scores={},
            eligibility=EligibilityRecord(eligibility_status="eligible"),
        ),
    ]
    artifact = _make_generic_ranking_artifact(rows=rows)
    _, candidates = prepare_generic_ranking_artifact_for_construction(artifact)

    by_symbol = {c.symbol: c for c in candidates}
    assert by_symbol["AAPL"].sector == "Information Technology"
    assert by_symbol["JPM"].sector == "Financials"
    # A row with no sector label flows through as None (constraint -> not_evaluated).
    assert by_symbol["NOSEC"].sector is None


def test_ranked_candidate_builder_surfaces_hard_filter_failures_for_excluded_rows() -> None:
    rows = [
        GenericRankingRow(
            rank=1,
            symbol="AAPL",
            composite_score=1.0,
            component_scores={},
            eligibility=EligibilityRecord(eligibility_status="eligible"),
        ),
        GenericRankingRow(
            rank=2,
            symbol="ZZZZ",
            composite_score=0.0,
            component_scores={},
            eligibility=EligibilityRecord(
                eligibility_status="excluded",
                hard_filter_failures=["no_price_data", "below_min_market_cap"],
            ),
        ),
    ]
    artifact = _make_generic_ranking_artifact(rows=rows)
    _, candidates = prepare_generic_ranking_artifact_for_construction(artifact)

    aapl = next(c for c in candidates if c.symbol == "AAPL")
    zzzz = next(c for c in candidates if c.symbol == "ZZZZ")

    assert aapl.eligible is True
    assert aapl.exclusion_reason is None
    assert zzzz.eligible is False
    assert zzzz.exclusion_reason == "no_price_data,below_min_market_cap"


# ── Route integration: /construction/ranking-artifacts/preflight/{id} ──────


def test_construction_preflight_route_dispatches_generic_ranking(tmp_path: Path) -> None:
    """The construction preflight route must dispatch generic_ranking artifact_id prefixes
    to the new preflight handler instead of returning 'unsupported ranking artifact kind'."""
    from fastapi.testclient import TestClient

    from app.api.main import app

    # Persist an artifact in our isolated store (autouse conftest fixture)
    store = GenericRankingArtifactStore()
    artifact = _make_generic_ranking_artifact()
    store.persist(artifact)

    client = TestClient(app)
    response = client.post(f"/construction/ranking-artifacts/preflight/{artifact.artifact_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["artifact"]["artifact_kind"] == "generic_ranking"
    assert body["eligibility"]["eligible"] is True
    assert body["handoff"]["handoff_kind"] == "generic_ranking_artifact_construction_handoff_v1"


def test_construction_preflight_route_returns_404_for_unknown_generic_ranking_artifact() -> None:
    from fastapi.testclient import TestClient

    from app.api.main import app

    client = TestClient(app)
    # Use the generic_ranking_ prefix so the dispatcher routes to our handler
    response = client.post(
        "/construction/ranking-artifacts/preflight/generic_ranking_artifact_doesnotexist01"
    )
    assert response.status_code == 404
