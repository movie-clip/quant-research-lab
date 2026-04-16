from __future__ import annotations

from app.schemas.backtest_engine import (
    CandidateFormationDerivation,
    CandidateFormationProposal,
    CandidateFormationState,
    CandidateFormationSummary,
    CandidateFormationTruthProvenance,
    ReplacementIntentReplayInput,
    SingleReplacementCandidateFormationRequest,
    SingleReplacementCandidateFormationResponse,
)
from app.services.candidate_construction import derive_same_weight_substitution_construction


def build_single_replacement_candidate_formation(request: SingleReplacementCandidateFormationRequest) -> SingleReplacementCandidateFormationResponse:
    if request.snapshot is None:
        return _rejected_response("snapshot is required")
    if request.replacement_intent is None:
        return _rejected_response("replacement_intent is required")

    try:
        construction = derive_same_weight_substitution_construction(request.snapshot, request.replacement_intent)
    except ValueError as exc:
        return _rejected_response(str(exc), request.replacement_intent)
    warnings = _build_candidate_formation_warnings(request.snapshot, request.replacement_intent)

    return SingleReplacementCandidateFormationResponse(
        formation=CandidateFormationState(kind="single_replacement_candidate_formation", status="ok"),
        proposal=_proposal_from_intent(request.replacement_intent),
        derivation=_formation_derivation(),
        baseline_weights=construction.baseline_weights,
        candidate_weights=construction.candidate_weights,
        formation_summary=CandidateFormationSummary(
            incumbent_start_weight=construction.incumbent_start_weight,
            candidate_start_weight=construction.incumbent_start_weight,
            unchanged_positions_count=construction.unchanged_positions_count,
            baseline_positions_count=len(construction.baseline_weights),
            candidate_positions_count=len(construction.candidate_weights),
            starting_turnover_pct=construction.starting_turnover_pct,
        ),
        truth_provenance=_truth_provenance(),
        warnings=warnings,
        rejection_reason=None,
    )


def _rejected_response(reason: str, replacement_intent: ReplacementIntentReplayInput | None = None) -> SingleReplacementCandidateFormationResponse:
    return SingleReplacementCandidateFormationResponse(
        formation=CandidateFormationState(kind="single_replacement_candidate_formation", status="rejected"),
        proposal=_proposal_from_intent(replacement_intent),
        derivation=_formation_derivation(),
        baseline_weights=[],
        candidate_weights=[],
        formation_summary=CandidateFormationSummary(),
        truth_provenance=_truth_provenance(),
        warnings=[],
        rejection_reason=reason,
    )


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


def _formation_derivation() -> CandidateFormationDerivation:
    return CandidateFormationDerivation(
        baseline_basis="draft_snapshot_positions_normalized",
        candidate_construction_rule="single_symbol_weight_substitution",
        cash_treatment="excluded_from_candidate_formation_basis",
        position_scope="positive_market_value_positions_only",
    )


def _truth_provenance() -> CandidateFormationTruthProvenance:
    return CandidateFormationTruthProvenance(
        baseline_truth_class="draft_snapshot_basis",
        candidate_truth_class="hypothetical_candidate_input_only",
        formation_truth_class="candidate_formation_derived",
        note="Candidate formation is a review-only derived object built from the draft snapshot and explicit replacement intent. No holdings have been changed.",
    )
def _build_candidate_formation_warnings(snapshot: DraftPortfolioSnapshotInput, replacement_intent: ReplacementIntentReplayInput) -> list[str]:
    warnings: list[str] = []
    if snapshot.cash_balances:
        warnings.append("Cash balances are excluded from the candidate-formation basis in this MVP.")
    if replacement_intent.warning_count > 0:
        warnings.append(f"Replacement intent carries {replacement_intent.warning_count} prior review warning(s).")
    return warnings
