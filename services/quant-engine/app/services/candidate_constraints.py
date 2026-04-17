from __future__ import annotations

from app.schemas.backtest_engine import (
    CandidateConstructionState,
    CandidateFormationProposal,
    ConstructedCandidateReplayInput,
    PortfolioWeightInput,
    SingleReplacementConstraintEvaluation,
    SingleReplacementConstraintValidationDerivation,
    SingleReplacementConstraintValidationState,
    SingleReplacementConstraintValidationTruthProvenance,
    SingleReplacementConstructionConstraintValidationRequest,
    SingleReplacementConstructionConstraintValidationResponse,
)
from app.services.candidate_construction import ALLOWED_RULE_IDS, RULE_ID, RULE_ID_FIXED_SPLIT


CONSTRAINT_SET_ID = "single_replacement_construction_constraints_v1"
TOLERANCE = 0.000001


def validate_single_replacement_candidate_construction_constraints(
    request: SingleReplacementConstructionConstraintValidationRequest,
) -> SingleReplacementConstructionConstraintValidationResponse:
    constructed_candidate = request.constructed_candidate
    if constructed_candidate is None:
        return _rejected_response("constructed_candidate is required")
    if request.constraint_set is None:
        return _rejected_response("constraint_set is required", constructed_candidate=constructed_candidate)

    evaluations = _build_evaluations(constructed_candidate)
    failed_hard_blocks = [item.constraint_id for item in evaluations if item.severity == "hard_block" and item.status == "fail"]

    if _has_rejection_failure(evaluations):
        return SingleReplacementConstructionConstraintValidationResponse(
            validation=_validation_state("rejected"),
            proposal=constructed_candidate.proposal,
            construction=constructed_candidate.construction,
            derivation=_derivation(),
            truth_provenance=_truth_provenance(),
            evaluations=evaluations,
            blocking_constraint_ids=[],
            warnings=[],
            rejection_reason="constructed_candidate could not be evaluated safely",
        )

    status = "blocked" if failed_hard_blocks else "ok"
    return SingleReplacementConstructionConstraintValidationResponse(
        validation=_validation_state(status),
        proposal=constructed_candidate.proposal,
        construction=constructed_candidate.construction,
        derivation=_derivation(),
        truth_provenance=_truth_provenance(),
        evaluations=evaluations,
        blocking_constraint_ids=failed_hard_blocks,
        warnings=[],
        rejection_reason=None,
    )


def _build_evaluations(constructed_candidate: ConstructedCandidateReplayInput) -> list[SingleReplacementConstraintEvaluation]:
    construction = constructed_candidate.construction
    proposal = constructed_candidate.proposal
    baseline_weights = constructed_candidate.inputs.baseline_weights
    candidate_weights = constructed_candidate.outputs.candidate_weights

    incumbent_symbol = (proposal.incumbent_symbol or "").upper()
    candidate_symbol = (proposal.candidate_symbol or "").upper()
    baseline_map = _weight_map(baseline_weights)
    candidate_map = _weight_map(candidate_weights)
    incumbent_start_weight = constructed_candidate.inputs.incumbent_start_weight
    candidate_added_weight = constructed_candidate.outputs.candidate_added_weight
    incumbent_remaining_weight = constructed_candidate.outputs.incumbent_remaining_weight
    starting_turnover_pct = constructed_candidate.outputs.starting_turnover_pct

    baseline_sum = round(sum(item.target_weight for item in baseline_weights), 8)
    candidate_sum = round(sum(item.target_weight for item in candidate_weights), 8)
    incumbent_in_candidate = incumbent_symbol in candidate_map if incumbent_symbol else False
    candidate_in_baseline = candidate_symbol in baseline_map if candidate_symbol else False
    candidate_in_candidate = candidate_symbol in candidate_map if candidate_symbol else False
    incumbent_baseline_weight = baseline_map.get(incumbent_symbol)
    half_incumbent_weight = round((incumbent_baseline_weight or 0.0) * 0.5, 8)

    evaluations = [
        _evaluation(
            "construction_status_ok",
            passed=construction.status == "ok",
            message_pass="Constructed candidate status is ok.",
            message_fail="Constructed candidate must have status ok before constraints can run.",
            actual_value=construction.status,
            expected_value="ok",
            operator="==",
            rejection_failure=True,
        ),
        _evaluation(
            "construction_rule_supported",
            passed=construction.rule_id in ALLOWED_RULE_IDS,
            message_pass="Constructed candidate rule is supported by the V1 constraint layer.",
            message_fail="Constructed candidate rule_id is unsupported for V1 constraint validation.",
            actual_value=construction.rule_id,
            expected_value="same_weight_substitution_v1|fixed_split_50_50_substitution_v2",
            operator="in",
            rejection_failure=True,
        ),
        _evaluation(
            "proposal_symbols_present",
            passed=bool(incumbent_symbol and candidate_symbol),
            message_pass="Proposal symbols are present.",
            message_fail="Constructed candidate proposal must include incumbent_symbol and candidate_symbol.",
            actual_value=f"{proposal.incumbent_symbol}|{proposal.candidate_symbol}",
            expected_value="non_empty_symbols",
            operator="!=",
            rejection_failure=True,
        ),
        _evaluation(
            "proposal_symbols_distinct",
            passed=bool(incumbent_symbol and candidate_symbol and incumbent_symbol != candidate_symbol),
            message_pass="Proposal candidate differs from incumbent.",
            message_fail="Constructed candidate proposal must use different incumbent and candidate symbols.",
            actual_value=f"{incumbent_symbol}|{candidate_symbol}",
            expected_value="distinct_symbols",
            operator="!=",
            rejection_failure=True,
        ),
        _evaluation(
            "baseline_weights_present",
            passed=bool(baseline_weights),
            message_pass="Baseline weights are present.",
            message_fail="Constructed candidate baseline weights are required.",
            actual_value=len(baseline_weights),
            expected_value=1,
            operator=">=",
            rejection_failure=True,
        ),
        _evaluation(
            "candidate_weights_present",
            passed=bool(candidate_weights),
            message_pass="Candidate weights are present.",
            message_fail="Constructed candidate candidate weights are required.",
            actual_value=len(candidate_weights),
            expected_value=1,
            operator=">=",
            rejection_failure=True,
        ),
        _evaluation(
            "baseline_symbols_unique",
            passed=len(baseline_map) == len(baseline_weights),
            message_pass="Baseline weights use unique symbols.",
            message_fail="Constructed candidate baseline weights must not contain duplicate symbols.",
            actual_value=len(baseline_weights),
            expected_value=len(baseline_map),
            operator="==",
        ),
        _evaluation(
            "candidate_symbols_unique",
            passed=len(candidate_map) == len(candidate_weights),
            message_pass="Candidate weights use unique symbols.",
            message_fail="Constructed candidate candidate weights must not contain duplicate symbols.",
            actual_value=len(candidate_weights),
            expected_value=len(candidate_map),
            operator="==",
        ),
        _evaluation(
            "baseline_weights_sum_to_one",
            passed=abs(baseline_sum - 1.0) <= TOLERANCE,
            message_pass="Baseline weights preserve a total weight of 1.0.",
            message_fail="Constructed candidate baseline weights must sum to 1.0.",
            actual_value=baseline_sum,
            expected_value=1.0,
            operator="==",
        ),
        _evaluation(
            "candidate_weights_sum_to_one",
            passed=abs(candidate_sum - 1.0) <= TOLERANCE,
            message_pass="Candidate weights preserve a total weight of 1.0.",
            message_fail="Constructed candidate candidate weights must sum to 1.0.",
            actual_value=candidate_sum,
            expected_value=1.0,
            operator="==",
        ),
        _evaluation(
            "incumbent_present_in_baseline",
            passed=incumbent_baseline_weight is not None and incumbent_baseline_weight > 0,
            message_pass="Incumbent is present in baseline weights with positive weight.",
            message_fail="Constructed candidate incumbent must be present in baseline weights with positive weight.",
            actual_value=incumbent_baseline_weight,
            expected_value=0.0,
            operator=">=",
        ),
        _evaluation(
            "candidate_not_already_present_in_baseline",
            passed=not candidate_in_baseline,
            message_pass="Candidate is not already present in baseline weights.",
            message_fail="Constructed candidate candidate symbol must not already be present in baseline weights.",
            actual_value=str(candidate_in_baseline).lower(),
            expected_value="false",
            operator="==",
        ),
        _evaluation(
            "candidate_present_in_candidate_weights",
            passed=candidate_in_candidate,
            message_pass="Candidate symbol is present in candidate weights.",
            message_fail="Constructed candidate candidate symbol must be present in candidate weights.",
            actual_value=str(candidate_in_candidate).lower(),
            expected_value="true",
            operator="==",
        ),
        _rule_specific_evaluation(
            construction.rule_id,
            RULE_ID,
            "same_weight_candidate_added_matches_incumbent",
            _float_equal(candidate_added_weight, incumbent_baseline_weight),
            "Same-weight rule assigns full incumbent weight to the candidate.",
            "Same-weight rule must assign full incumbent weight to the candidate.",
            candidate_added_weight,
            incumbent_baseline_weight,
        ),
        _rule_specific_evaluation(
            construction.rule_id,
            RULE_ID,
            "same_weight_incumbent_removed_from_candidate_weights",
            not incumbent_in_candidate,
            "Same-weight rule removes the incumbent from candidate weights.",
            "Same-weight rule must remove the incumbent from candidate weights.",
            str(incumbent_in_candidate).lower(),
            "false",
        ),
        _rule_specific_evaluation(
            construction.rule_id,
            RULE_ID,
            "same_weight_incumbent_remaining_weight_zero",
            _float_equal(incumbent_remaining_weight, 0.0),
            "Same-weight rule leaves zero incumbent remaining weight.",
            "Same-weight rule must leave zero incumbent remaining weight.",
            incumbent_remaining_weight,
            0.0,
        ),
        _rule_specific_evaluation(
            construction.rule_id,
            RULE_ID,
            "same_weight_starting_turnover_matches_incumbent",
            _float_equal(starting_turnover_pct, incumbent_baseline_weight),
            "Same-weight rule turnover matches the full incumbent starting weight.",
            "Same-weight rule turnover must match the full incumbent starting weight.",
            starting_turnover_pct,
            incumbent_baseline_weight,
        ),
        _rule_specific_evaluation(
            construction.rule_id,
            RULE_ID_FIXED_SPLIT,
            "fixed_split_candidate_added_matches_half_incumbent",
            _float_equal(candidate_added_weight, half_incumbent_weight),
            "Fixed-split rule assigns half of the incumbent weight to the candidate.",
            "Fixed-split rule must assign half of the incumbent weight to the candidate.",
            candidate_added_weight,
            half_incumbent_weight,
        ),
        _rule_specific_evaluation(
            construction.rule_id,
            RULE_ID_FIXED_SPLIT,
            "fixed_split_incumbent_retained_at_half_weight",
            _float_equal(candidate_map.get(incumbent_symbol), half_incumbent_weight),
            "Fixed-split rule retains the incumbent at half weight in candidate weights.",
            "Fixed-split rule must retain the incumbent at half weight in candidate weights.",
            candidate_map.get(incumbent_symbol),
            half_incumbent_weight,
        ),
        _rule_specific_evaluation(
            construction.rule_id,
            RULE_ID_FIXED_SPLIT,
            "fixed_split_incumbent_remaining_matches_half_incumbent",
            _float_equal(incumbent_remaining_weight, half_incumbent_weight),
            "Fixed-split rule leaves half of the incumbent weight in place.",
            "Fixed-split rule must leave half of the incumbent weight in place.",
            incumbent_remaining_weight,
            half_incumbent_weight,
        ),
        _rule_specific_evaluation(
            construction.rule_id,
            RULE_ID_FIXED_SPLIT,
            "fixed_split_starting_turnover_matches_half_incumbent",
            _float_equal(starting_turnover_pct, half_incumbent_weight),
            "Fixed-split rule turnover matches half of the incumbent starting weight.",
            "Fixed-split rule turnover must match half of the incumbent starting weight.",
            starting_turnover_pct,
            half_incumbent_weight,
        ),
    ]
    return evaluations


def _rule_specific_evaluation(
    actual_rule_id: str | None,
    expected_rule_id: str,
    constraint_id: str,
    passed: bool,
    message_pass: str,
    message_fail: str,
    actual_value: float | str | None,
    expected_value: float | str | None,
) -> SingleReplacementConstraintEvaluation:
    if actual_rule_id != expected_rule_id:
        return SingleReplacementConstraintEvaluation(
            constraint_id=constraint_id,
            severity="hard_block",
            status="not_applicable",
            message=f"Constraint is not applicable for rule {actual_rule_id}.",
            rationale="This rule-specific check only applies to a different construction rule.",
            actual_value=actual_value,
            expected_value=expected_value,
            operator="==",
        )
    return _evaluation(
        constraint_id,
        passed=passed,
        message_pass=message_pass,
        message_fail=message_fail,
        actual_value=actual_value,
        expected_value=expected_value,
        operator="==",
    )


def _evaluation(
    constraint_id: str,
    *,
    passed: bool,
    message_pass: str,
    message_fail: str,
    actual_value: float | str | None,
    expected_value: float | str | None,
    operator: str,
    rejection_failure: bool = False,
) -> SingleReplacementConstraintEvaluation:
    rationale = "This check hard-blocks replay progression when candidate construction semantics are invalid."
    if rejection_failure:
        rationale = "This check must pass before the constructed candidate can be evaluated safely."
    return SingleReplacementConstraintEvaluation(
        constraint_id=constraint_id,
        severity="hard_block",
        status="pass" if passed else "fail",
        message=message_pass if passed else message_fail,
        rationale=rationale,
        actual_value=actual_value,
        expected_value=expected_value,
        operator=operator,  # type: ignore[arg-type]
    )


def _has_rejection_failure(evaluations: list[SingleReplacementConstraintEvaluation]) -> bool:
    rejection_constraint_ids = {
        "construction_status_ok",
        "construction_rule_supported",
        "proposal_symbols_present",
        "proposal_symbols_distinct",
        "baseline_weights_present",
        "candidate_weights_present",
    }
    return any(item.constraint_id in rejection_constraint_ids and item.status == "fail" for item in evaluations)


def _weight_map(weights: list[PortfolioWeightInput]) -> dict[str, float]:
    result: dict[str, float] = {}
    for item in weights:
        result[item.symbol] = item.target_weight
    return result


def _float_equal(left: float | None, right: float | None) -> bool:
    if left is None or right is None:
        return False
    return abs(left - right) <= TOLERANCE


def _validation_state(status: str) -> SingleReplacementConstraintValidationState:
    return SingleReplacementConstraintValidationState(
        kind="single_replacement_construction_constraint_validation",
        status=status,  # type: ignore[arg-type]
        constraint_set_id=CONSTRAINT_SET_ID,
    )


def _derivation() -> SingleReplacementConstraintValidationDerivation:
    return SingleReplacementConstraintValidationDerivation(
        validation_timing="post_construction_pre_replay",
        validation_basis="explicit_constraint_set",
        candidate_input_source="constructed_candidate_payload",
        constraint_set_id=CONSTRAINT_SET_ID,
    )


def _truth_provenance() -> SingleReplacementConstraintValidationTruthProvenance:
    return SingleReplacementConstraintValidationTruthProvenance(
        baseline_truth_class="draft_snapshot_basis",
        construction_truth_class="candidate_construction_derived",
        candidate_truth_class="hypothetical_candidate_input_only",
        constraint_validation_truth_class="constraint_validation_derived",
        note="Constraint validation is a review-only derived object evaluated against a constructed hypothetical candidate. No holdings have been changed and no replay has been run.",
    )


def _empty_proposal() -> CandidateFormationProposal:
    return CandidateFormationProposal(source="draft_replacement_intent")


def _empty_construction() -> CandidateConstructionState:
    return CandidateConstructionState(kind="single_replacement_construction", status="rejected", rule_id=None)


def _rejected_response(
    reason: str,
    *,
    constructed_candidate: ConstructedCandidateReplayInput | None = None,
) -> SingleReplacementConstructionConstraintValidationResponse:
    return SingleReplacementConstructionConstraintValidationResponse(
        validation=_validation_state("rejected"),
        proposal=constructed_candidate.proposal if constructed_candidate is not None else _empty_proposal(),
        construction=constructed_candidate.construction if constructed_candidate is not None else _empty_construction(),
        derivation=_derivation(),
        truth_provenance=_truth_provenance(),
        evaluations=[],
        blocking_constraint_ids=[],
        warnings=[],
        rejection_reason=reason,
    )
