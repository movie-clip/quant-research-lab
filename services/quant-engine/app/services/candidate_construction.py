from __future__ import annotations

from dataclasses import dataclass

from app.schemas.backtest_engine import (
    CandidateConstructionDerivation,
    CandidateConstructionInputs,
    CandidateConstructionOutputs,
    CandidateConstructionRuleInput,
    CandidateConstructionState,
    CandidateConstructionTruthProvenance,
    CandidateFormationProposal,
    DraftPortfolioSnapshotInput,
    PortfolioWeightInput,
    ReplacementIntentReplayInput,
    SingleReplacementCandidateConstructionRequest,
    SingleReplacementCandidateConstructionResponse,
)


RULE_ID = "same_weight_substitution_v1"
RULE_ID_FIXED_SPLIT = "fixed_split_50_50_substitution_v2"
ALLOWED_RULE_IDS = {RULE_ID, RULE_ID_FIXED_SPLIT}


@dataclass(frozen=True)
class SingleReplacementConstructionResult:
    baseline_weights: list[PortfolioWeightInput]
    candidate_weights: list[PortfolioWeightInput]
    incumbent_start_weight: float
    starting_turnover_pct: float
    unchanged_positions_count: int
    candidate_added_weight: float
    incumbent_remaining_weight: float


def build_single_replacement_candidate_construction(request: SingleReplacementCandidateConstructionRequest) -> SingleReplacementCandidateConstructionResponse:
    if request.snapshot is None:
        return _rejected_response("snapshot is required", request.replacement_intent)
    if request.replacement_intent is None:
        return _rejected_response("replacement_intent is required")
    if request.construction_rule is None:
        return _rejected_response("construction_rule is required", request.replacement_intent)
    if request.construction_rule.rule_id not in ALLOWED_RULE_IDS:
        return _rejected_response(f"unsupported construction rule: {request.construction_rule.rule_id}", request.replacement_intent, request.construction_rule.rule_id)

    try:
        result = derive_single_replacement_construction(request.snapshot, request.replacement_intent, request.construction_rule)
    except ValueError as exc:
        return _rejected_response(str(exc), request.replacement_intent, request.construction_rule.rule_id)

    return SingleReplacementCandidateConstructionResponse(
        construction=CandidateConstructionState(kind="single_replacement_construction", status="ok", rule_id=request.construction_rule.rule_id),
        proposal=_proposal_from_intent(request.replacement_intent),
        inputs=CandidateConstructionInputs(
            baseline_weights=result.baseline_weights,
            construction_rule=request.construction_rule.rule_id,
            incumbent_start_weight=result.incumbent_start_weight,
            candidate_added_weight=result.candidate_added_weight,
            incumbent_remaining_weight=result.incumbent_remaining_weight,
        ),
        outputs=CandidateConstructionOutputs(
            candidate_weights=result.candidate_weights,
            starting_turnover_pct=result.starting_turnover_pct,
            unchanged_positions_count=result.unchanged_positions_count,
            candidate_added_weight=result.candidate_added_weight,
            incumbent_remaining_weight=result.incumbent_remaining_weight,
        ),
        derivation=_construction_derivation(),
        truth_provenance=_construction_truth_provenance(),
        warnings=_build_construction_warnings(request.snapshot, request.replacement_intent),
        rejection_reason=None,
    )


def derive_single_replacement_construction(
    snapshot: DraftPortfolioSnapshotInput,
    replacement_intent: ReplacementIntentReplayInput,
    construction_rule: CandidateConstructionRuleInput,
) -> SingleReplacementConstructionResult:
    if construction_rule.rule_id == RULE_ID:
        return derive_same_weight_substitution_construction(snapshot, replacement_intent)
    if construction_rule.rule_id == RULE_ID_FIXED_SPLIT:
        return derive_fixed_split_50_50_substitution_construction(snapshot, replacement_intent)
    raise ValueError(f"unsupported construction rule: {construction_rule.rule_id}")


def derive_same_weight_substitution_construction(snapshot: DraftPortfolioSnapshotInput, replacement_intent: ReplacementIntentReplayInput) -> SingleReplacementConstructionResult:
    baseline_weights = build_snapshot_baseline_weights(snapshot)
    candidate_weights = build_candidate_weights_from_replacement_intent(baseline_weights, replacement_intent.base_symbol, replacement_intent.candidate_symbol, rule_id=RULE_ID)
    incumbent_symbol = replacement_intent.base_symbol.upper()
    incumbent_weight = next((item.target_weight for item in baseline_weights if item.symbol == incumbent_symbol), None)
    if incumbent_weight is None or incumbent_weight <= 0:
        raise ValueError(f"replacement intent incumbent has non-positive starting weight: {incumbent_symbol}")

    return SingleReplacementConstructionResult(
        baseline_weights=baseline_weights,
        candidate_weights=candidate_weights,
        incumbent_start_weight=incumbent_weight,
        starting_turnover_pct=incumbent_weight,
        unchanged_positions_count=max(len(baseline_weights) - 1, 0),
        candidate_added_weight=incumbent_weight,
        incumbent_remaining_weight=0.0,
    )


def derive_fixed_split_50_50_substitution_construction(snapshot: DraftPortfolioSnapshotInput, replacement_intent: ReplacementIntentReplayInput) -> SingleReplacementConstructionResult:
    baseline_weights = build_snapshot_baseline_weights(snapshot)
    candidate_weights = build_candidate_weights_from_replacement_intent(baseline_weights, replacement_intent.base_symbol, replacement_intent.candidate_symbol, rule_id=RULE_ID_FIXED_SPLIT)
    incumbent_symbol = replacement_intent.base_symbol.upper()
    incumbent_weight = next((item.target_weight for item in baseline_weights if item.symbol == incumbent_symbol), None)
    if incumbent_weight is None or incumbent_weight <= 0:
        raise ValueError(f"replacement intent incumbent has non-positive starting weight: {incumbent_symbol}")

    split_weight = round(incumbent_weight * 0.5, 8)
    return SingleReplacementConstructionResult(
        baseline_weights=baseline_weights,
        candidate_weights=candidate_weights,
        incumbent_start_weight=incumbent_weight,
        starting_turnover_pct=split_weight,
        unchanged_positions_count=max(len(baseline_weights) - 1, 0),
        candidate_added_weight=split_weight,
        incumbent_remaining_weight=split_weight,
    )


def build_snapshot_baseline_weights(snapshot: DraftPortfolioSnapshotInput) -> list[PortfolioWeightInput]:
    positions = [position for position in snapshot.positions if position.symbol and position.market_value > 0]
    if not positions:
        raise ValueError("snapshot must include at least one positive-weight position")
    total_market_value = sum(position.market_value for position in positions)
    if total_market_value <= 0:
        raise ValueError("snapshot positions must sum to a positive market value")

    weights = [PortfolioWeightInput(symbol=position.symbol.upper(), target_weight=round(position.market_value / total_market_value, 8)) for position in positions]
    total_weight = sum(item.target_weight for item in weights)
    if abs(total_weight - 1.0) > 0.000001:
        raise ValueError("snapshot position weights could not be represented deterministically")
    return weights


def build_candidate_weights_from_replacement_intent(baseline_weights: list[PortfolioWeightInput], incumbent_symbol: str, candidate_symbol: str, *, rule_id: str = RULE_ID) -> list[PortfolioWeightInput]:
    incumbent = incumbent_symbol.upper()
    candidate = candidate_symbol.upper()
    if candidate == incumbent:
        raise ValueError("replacement intent candidate must differ from incumbent")

    baseline_by_symbol = {item.symbol: item for item in baseline_weights}
    incumbent_weight = baseline_by_symbol.get(incumbent)
    if incumbent_weight is None:
        raise ValueError(f"replacement intent incumbent not found in draft snapshot: {incumbent}")
    if incumbent_weight.target_weight <= 0:
        raise ValueError(f"replacement intent incumbent has non-positive starting weight: {incumbent}")
    if candidate in baseline_by_symbol:
        raise ValueError(f"replacement intent candidate is already held in draft snapshot: {candidate}")

    if rule_id == RULE_ID:
        candidate_weights = [PortfolioWeightInput(symbol=item.symbol, target_weight=item.target_weight) for item in baseline_weights if item.symbol != incumbent]
        candidate_weights.append(PortfolioWeightInput(symbol=candidate, target_weight=incumbent_weight.target_weight))
    elif rule_id == RULE_ID_FIXED_SPLIT:
        split_weight = round(incumbent_weight.target_weight * 0.5, 8)
        candidate_weights = []
        for item in baseline_weights:
            if item.symbol == incumbent:
                candidate_weights.append(PortfolioWeightInput(symbol=incumbent, target_weight=split_weight))
            else:
                candidate_weights.append(PortfolioWeightInput(symbol=item.symbol, target_weight=item.target_weight))
        candidate_weights.append(PortfolioWeightInput(symbol=candidate, target_weight=split_weight))
    else:
        raise ValueError(f"unsupported construction rule: {rule_id}")
    total_weight = sum(item.target_weight for item in candidate_weights)
    if abs(total_weight - 1.0) > 0.000001:
        raise ValueError("candidate weights must preserve the baseline total exactly")
    return candidate_weights


def _proposal_from_intent(replacement_intent: ReplacementIntentReplayInput | None) -> CandidateFormationProposal:
    if replacement_intent is None:
        return CandidateFormationProposal(source="draft_replacement_intent")
    return CandidateFormationProposal(
        source="draft_replacement_intent",
        draft_id=replacement_intent.draft_id,
        workspace_id=replacement_intent.workspace_id,
        base_node_id=replacement_intent.base_node_id,
        incumbent_symbol=replacement_intent.base_symbol,
        candidate_symbol=replacement_intent.candidate_symbol,
    )


def _construction_derivation() -> CandidateConstructionDerivation:
    return CandidateConstructionDerivation(
        baseline_basis="draft_snapshot_positions_normalized",
        construction_basis="explicit_single_replacement_rule",
        cash_treatment="excluded_from_construction_basis",
        position_scope="positive_market_value_positions_only",
    )


def _construction_truth_provenance() -> CandidateConstructionTruthProvenance:
    return CandidateConstructionTruthProvenance(
        baseline_truth_class="draft_snapshot_basis",
        construction_truth_class="candidate_construction_derived",
        candidate_truth_class="hypothetical_candidate_input_only",
        note="Candidate construction is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed and no replay has been run.",
    )


def _build_construction_warnings(snapshot: DraftPortfolioSnapshotInput, replacement_intent: ReplacementIntentReplayInput) -> list[str]:
    warnings: list[str] = []
    if snapshot.cash_balances:
        warnings.append("Cash balances are excluded from the construction basis in this MVP.")
    if replacement_intent.warning_count > 0:
        warnings.append(f"Replacement intent carries {replacement_intent.warning_count} prior review warning(s).")
    return warnings


def _rejected_response(reason: str, replacement_intent: ReplacementIntentReplayInput | None = None, rule_id: str | None = None) -> SingleReplacementCandidateConstructionResponse:
    return SingleReplacementCandidateConstructionResponse(
        construction=CandidateConstructionState(kind="single_replacement_construction", status="rejected", rule_id=rule_id),
        proposal=_proposal_from_intent(replacement_intent),
        inputs=CandidateConstructionInputs(construction_rule=rule_id),
        outputs=CandidateConstructionOutputs(),
        derivation=_construction_derivation(),
        truth_provenance=_construction_truth_provenance(),
        warnings=[],
        rejection_reason=reason,
    )
