from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.backtest_engine import (
    CandidateConstructionRuleInput,
    ConstructedCandidateReplayInput,
    DraftPortfolioImportedMetaInput,
    DraftPortfolioSnapshotInput,
    DraftPortfolioPositionInput,
    ReplacementIntentReplayInput,
    SingleReplacementCandidateConstructionRequest,
    SingleReplacementConstructionConstraintSetInput,
    SingleReplacementConstructionConstraintValidationRequest,
)
from app.services.candidate_constraints import CONSTRAINT_SET_ID, validate_single_replacement_candidate_construction_constraints
from app.services.candidate_construction import RULE_ID, RULE_ID_FIXED_SPLIT, build_single_replacement_candidate_construction


def _draft_snapshot(*positions: tuple[str, float]) -> DraftPortfolioSnapshotInput:
    return DraftPortfolioSnapshotInput(
        base_currency="USD",
        imported_meta=DraftPortfolioImportedMetaInput(
            importer="interactive_brokers",
            statement_period="2025-01-01 - 2025-12-31",
            imported_at=datetime(2026, 4, 10),
            source_file_names=["IB2025.pdf"],
        ),
        positions=[
            DraftPortfolioPositionInput(symbol=symbol, market_value=market_value, quantity=1.0, currency="USD", source_type="etf")
            for symbol, market_value in positions
        ],
        cash_balances=[],
    )


def _replacement_intent(base_symbol: str = "VUAA", candidate_symbol: str = "IUFS") -> ReplacementIntentReplayInput:
    return ReplacementIntentReplayInput(
        kind="etf_replacement_intent",
        source="candidate_seed",
        created_at=datetime(2026, 4, 15, 0, 5, 0),
        draft_id="draft-1",
        workspace_id="workspace-1",
        base_node_id="node-1",
        base_symbol=base_symbol,
        candidate_symbol=candidate_symbol,
        seeded_from_draft_id="draft-1",
        seed_ranking_id="etf_ranking_engine_v1",
        seed_methodology_id="etf_ranking_methodology_v1",
        seed_ranking_basis_date="2026-04-15",
        peer_group="Sector UCITS ETF",
        benchmark_symbol="SPY",
        lookback_months=6,
        confidence="medium",
        holdings_support="mixed",
        warning_count=0,
    )


def _build_validated_request(rule_id: str = RULE_ID) -> SingleReplacementConstructionConstraintValidationRequest:
    construction_response = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=rule_id),
        )
    )
    constructed_candidate = ConstructedCandidateReplayInput.model_validate(construction_response.model_dump(mode="json"))
    return SingleReplacementConstructionConstraintValidationRequest(
        constructed_candidate=constructed_candidate,
        constraint_set=SingleReplacementConstructionConstraintSetInput(constraint_set_id=CONSTRAINT_SET_ID),
    )


def test_constraint_validation_returns_ok_for_same_weight_candidate() -> None:
    response = validate_single_replacement_candidate_construction_constraints(_build_validated_request(RULE_ID))

    assert response.validation.status == "ok"
    assert response.blocking_constraint_ids == []
    assert response.rejection_reason is None
    assert response.truth_provenance.constraint_validation_truth_class == "constraint_validation_derived"
    assert all(item.status in {"pass", "not_applicable"} for item in response.evaluations)
    assert response.warnings == []


def test_constraint_validation_returns_ok_for_fixed_split_candidate() -> None:
    response = validate_single_replacement_candidate_construction_constraints(_build_validated_request(RULE_ID_FIXED_SPLIT))

    assert response.validation.status == "ok"
    assert response.blocking_constraint_ids == []
    assert any(item.constraint_id == "fixed_split_candidate_added_matches_half_incumbent" and item.status == "pass" for item in response.evaluations)
    assert any(item.constraint_id == "same_weight_candidate_added_matches_incumbent" and item.status == "not_applicable" for item in response.evaluations)


def test_constraint_validation_returns_blocked_for_invalid_weight_sum() -> None:
    request = _build_validated_request(RULE_ID)
    request.constructed_candidate.outputs.candidate_weights[0].target_weight = 0.5

    response = validate_single_replacement_candidate_construction_constraints(request)

    assert response.validation.status == "blocked"
    assert "candidate_weights_sum_to_one" in response.blocking_constraint_ids
    assert response.rejection_reason is None
    assert any(item.constraint_id == "candidate_weights_sum_to_one" and item.status == "fail" for item in response.evaluations)


def test_constraint_validation_returns_blocked_for_rule_interaction_failure() -> None:
    request = _build_validated_request(RULE_ID_FIXED_SPLIT)
    request.constructed_candidate.outputs.incumbent_remaining_weight = 0.2

    response = validate_single_replacement_candidate_construction_constraints(request)

    assert response.validation.status == "blocked"
    assert "fixed_split_incumbent_remaining_matches_half_incumbent" in response.blocking_constraint_ids
    assert any(item.constraint_id == "fixed_split_incumbent_remaining_matches_half_incumbent" and item.status == "fail" for item in response.evaluations)


def test_constraint_validation_returns_rejected_for_non_ok_constructed_candidate() -> None:
    request = _build_validated_request(RULE_ID)
    request.constructed_candidate.construction.status = "rejected"
    request.constructed_candidate.rejection_reason = "construction failed"

    response = validate_single_replacement_candidate_construction_constraints(request)

    assert response.validation.status == "rejected"
    assert response.rejection_reason == "constructed_candidate could not be evaluated safely"
    assert response.blocking_constraint_ids == []
    assert any(item.constraint_id == "construction_status_ok" and item.status == "fail" for item in response.evaluations)


def test_constraint_validation_returns_rejected_for_missing_candidate_weights() -> None:
    request = _build_validated_request(RULE_ID)
    request.constructed_candidate.outputs.candidate_weights = []

    response = validate_single_replacement_candidate_construction_constraints(request)

    assert response.validation.status == "rejected"
    assert response.rejection_reason == "constructed_candidate could not be evaluated safely"
    assert any(item.constraint_id == "candidate_weights_present" and item.status == "fail" for item in response.evaluations)


def test_constraint_validation_route_returns_ok_contract() -> None:
    client = TestClient(app)
    request = _build_validated_request(RULE_ID)

    response = client.post(
        "/backtests/candidate-construction/replacement-intent/constraints",
        json=request.model_dump(mode="json"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["validation"] == {
        "kind": "single_replacement_construction_constraint_validation",
        "status": "ok",
        "constraint_set_id": CONSTRAINT_SET_ID,
    }
    assert payload["blocking_constraint_ids"] == []


def test_constraint_validation_route_rejects_missing_constraint_set() -> None:
    client = TestClient(app)
    request = _build_validated_request(RULE_ID)
    payload = request.model_dump(mode="json")
    payload.pop("constraint_set")

    response = client.post(
        "/backtests/candidate-construction/replacement-intent/constraints",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "constraint_set is required"}


def test_constraint_validation_route_rejects_unsupported_constraint_set_id() -> None:
    client = TestClient(app)
    request = _build_validated_request(RULE_ID)
    payload = request.model_dump(mode="json")
    payload["constraint_set"] = {"constraint_set_id": "unsupported_constraint_set_v0"}

    response = client.post(
        "/backtests/candidate-construction/replacement-intent/constraints",
        json=payload,
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "unsupported constraint_set_id: unsupported_constraint_set_v0"}
