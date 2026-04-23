from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from app.schemas.construction import (
    ConstructionArtifact,
    ConstructionConstraintEvaluation,
    ConstructionCurrentPortfolioInput,
    ConstructionDeterministicOrdering,
    ConstructionExcludedName,
    ConstructionNormalizedInputs,
    ConstructionRankedCandidateInput,
    ConstructionRunRequest,
    ConstructionSelectionRuleTrace,
    ConstructionSelectionRuleTraceStep,
    ConstructionSelectedName,
    ConstructionTradeAction,
    ConstructionTradeIntent,
    ConstructionWeight,
)
from app.services.construction_artifact_service import (
    ConstructionArtifactStore,
    build_stable_construction_artifact,
    persist_construction_artifact,
)

POLICY_ID = "top_n_equal_weight_v1"
ELIGIBLE_ONLY_RULE_ID = "eligible_only"
TAKE_TOP_N_RULE_ID = "take_top_n"
SELECTION_RULE_SEQUENCE = (ELIGIBLE_ONLY_RULE_ID, TAKE_TOP_N_RULE_ID)
TOP_N_CUTOFF_REASON = f"not selected by {POLICY_ID} cutoff"
EPSILON = 1e-8


@dataclass(frozen=True)
class _SelectionPipelineResult:
    eligible_candidates: list[ConstructionRankedCandidateInput]
    selected_candidates: list[ConstructionRankedCandidateInput]
    trace: ConstructionSelectionRuleTrace


def build_construction_run(
    request: ConstructionRunRequest,
    *,
    artifact_store: ConstructionArtifactStore | None = None,
) -> ConstructionArtifact:
    normalized_ranked = _normalize_ranked_candidates(request.ranked_universe.ranked_candidates)
    normalized_current = _normalize_current_weights(request.current_portfolio)
    selection = _run_selection_rule_pipeline(normalized_ranked, top_n=request.policy.top_n)
    normalized_inputs = ConstructionNormalizedInputs(
        ranked_universe_artifact_id=request.ranked_universe.artifact_id,
        ranking_id=request.ranked_universe.ranking_id,
        ranking_methodology_id=request.ranked_universe.methodology_id,
        ranking_as_of_date=request.ranked_universe.as_of_date,
        current_portfolio_artifact_id=request.current_portfolio.artifact_id,
        current_portfolio_as_of_timestamp=request.current_portfolio.as_of_timestamp,
        policy_id=request.policy.policy_id,
        top_n=request.policy.top_n,
        max_position_weight=request.hard_constraints.max_position_weight,
        current_portfolio_weights=normalized_current,
        ranked_candidates=normalized_ranked,
    )
    failure_reasons: list[str] = []

    if request.policy.policy_id != POLICY_ID:
        failure_reasons.append(f"unsupported construction policy: {request.policy.policy_id}")
    if not selection.eligible_candidates:
        failure_reasons.append("eligible ranked universe is empty")
    if len(selection.eligible_candidates) < request.policy.top_n:
        failure_reasons.append("eligible ranked universe has fewer names than requested top_n")

    selected = selection.selected_candidates
    target_weight = round(1.0 / request.policy.top_n, 8) if request.policy.top_n > 0 else 0.0
    if target_weight > request.hard_constraints.max_position_weight + EPSILON:
        failure_reasons.append("equal-weight seed exceeds max_position_weight")

    if failure_reasons:
        artifact = ConstructionArtifact(
            artifact_id="construction_artifact_pending",
            fingerprint="0" * 64,
            status="infeasible",
            request_id=request.request_id,
            policy=request.policy,
            hard_constraints=request.hard_constraints,
            normalized_inputs=normalized_inputs,
            selected_names=[ConstructionSelectedName(symbol=item.symbol, rank=item.rank, score=item.score) for item in selected],
            excluded_names=_build_excluded_names(normalized_ranked, selected_symbols=[item.symbol for item in selected]),
            seed_weights=[],
            final_target_weights=[],
            trade_intents=[],
            constraint_evaluations=_evaluate_constraints(request, [], selected, infeasible_reasons=failure_reasons),
            deterministic_ordering=ConstructionDeterministicOrdering(
                ranked_candidate_symbols=[item.symbol for item in normalized_ranked],
                selected_symbols=[item.symbol for item in selected],
                trade_symbols=[],
            ),
            selection_rule_trace=selection.trace,
            failure_reasons=failure_reasons,
        )
        return persist_construction_artifact(build_stable_construction_artifact(artifact), store=artifact_store)

    seed_weights = [ConstructionWeight(symbol=item.symbol, weight=target_weight) for item in selected]
    final_target_weights = seed_weights
    trade_intents = _build_trade_intents(normalized_current, final_target_weights)
    artifact = ConstructionArtifact(
        artifact_id="construction_artifact_pending",
        fingerprint="0" * 64,
        status="feasible",
        request_id=request.request_id,
        policy=request.policy,
        hard_constraints=request.hard_constraints,
        normalized_inputs=normalized_inputs,
        selected_names=[ConstructionSelectedName(symbol=item.symbol, rank=item.rank, score=item.score) for item in selected],
        excluded_names=_build_excluded_names(normalized_ranked, selected_symbols=[item.symbol for item in selected]),
        seed_weights=seed_weights,
        final_target_weights=final_target_weights,
        trade_intents=trade_intents,
        constraint_evaluations=_evaluate_constraints(request, final_target_weights, selected, infeasible_reasons=[]),
        deterministic_ordering=ConstructionDeterministicOrdering(
            ranked_candidate_symbols=[item.symbol for item in normalized_ranked],
            selected_symbols=[item.symbol for item in selected],
            trade_symbols=[item.symbol for item in trade_intents],
        ),
        selection_rule_trace=selection.trace,
        failure_reasons=[],
    )
    return persist_construction_artifact(build_stable_construction_artifact(artifact), store=artifact_store)


def _normalize_ranked_candidates(candidates: list[ConstructionRankedCandidateInput]) -> list[ConstructionRankedCandidateInput]:
    deduped: dict[str, ConstructionRankedCandidateInput] = {}
    for candidate in sorted(candidates, key=lambda item: (item.rank, item.symbol)):
        if candidate.symbol not in deduped:
            deduped[candidate.symbol] = candidate.model_copy(update={"exclusion_reason": _normalized_exclusion_reason(candidate)})
    return list(deduped.values())


def _run_selection_rule_pipeline(
    candidates: list[ConstructionRankedCandidateInput],
    *,
    top_n: int,
) -> _SelectionPipelineResult:
    current = list(candidates)
    eligible_candidates = current
    trace_steps: list[ConstructionSelectionRuleTraceStep] = []
    for rule_order, rule_id in enumerate(SELECTION_RULE_SEQUENCE, start=1):
        input_candidates = list(current)
        current = _apply_selection_rule(rule_id, input_candidates, top_n=top_n)
        trace_steps.append(
            ConstructionSelectionRuleTraceStep(
                rule_id=rule_id,
                rule_order=rule_order,
                input_candidate_symbols=[candidate.symbol for candidate in input_candidates],
                output_candidate_symbols=[candidate.symbol for candidate in current],
            )
        )
        if rule_id == ELIGIBLE_ONLY_RULE_ID:
            eligible_candidates = current
    return _SelectionPipelineResult(
        eligible_candidates=eligible_candidates,
        selected_candidates=current,
        trace=ConstructionSelectionRuleTrace(
            rule_ids=list(SELECTION_RULE_SEQUENCE),
            steps=trace_steps,
        ),
    )


def _apply_selection_rule(
    rule_id: str,
    candidates: list[ConstructionRankedCandidateInput],
    *,
    top_n: int,
) -> list[ConstructionRankedCandidateInput]:
    if rule_id == ELIGIBLE_ONLY_RULE_ID:
        return [candidate for candidate in candidates if candidate.eligible]
    if rule_id == TAKE_TOP_N_RULE_ID:
        return candidates[:top_n]
    raise ValueError(f"unsupported selection rule: {rule_id}")


def _normalized_exclusion_reason(candidate: ConstructionRankedCandidateInput) -> str | None:
    if candidate.eligible:
        return None
    if candidate.exclusion_reason:
        return candidate.exclusion_reason
    return "ranked candidate marked ineligible"


def _normalize_current_weights(current_portfolio: ConstructionCurrentPortfolioInput) -> list[ConstructionWeight]:
    deduped: dict[str, float] = {}
    for weight in current_portfolio.weights:
        deduped[weight.symbol] = deduped.get(weight.symbol, 0.0) + weight.weight
    normalized = [ConstructionWeight(symbol=symbol, weight=round(weight, 8)) for symbol, weight in sorted(deduped.items()) if weight > 0.0]
    total = sum(item.weight for item in normalized)
    if normalized and abs(total - 1.0) > 1e-6:
        raise ValueError("current_portfolio.weights must sum to 1.0")
    return normalized


def _build_excluded_names(candidates: list[ConstructionRankedCandidateInput], *, selected_symbols: list[str]) -> list[ConstructionExcludedName]:
    selected = set(selected_symbols)
    excluded: list[ConstructionExcludedName] = []
    for item in candidates:
        if item.symbol in selected:
            continue
        reason = item.exclusion_reason or TOP_N_CUTOFF_REASON
        if item.eligible and item.exclusion_reason is None:
            reason = TOP_N_CUTOFF_REASON
        excluded.append(
            ConstructionExcludedName(
                symbol=item.symbol,
                rank=item.rank,
                eligible=item.eligible,
                reason=reason,
            )
        )
    return excluded


def _build_trade_intents(current_weights: list[ConstructionWeight], target_weights: list[ConstructionWeight]) -> list[ConstructionTradeIntent]:
    current_by_symbol = {item.symbol: item.weight for item in current_weights}
    target_by_symbol = {item.symbol: item.weight for item in target_weights}
    symbols = sorted(set(current_by_symbol) | set(target_by_symbol))
    trades: list[ConstructionTradeIntent] = []
    for symbol in symbols:
        current_weight = current_by_symbol.get(symbol, 0.0)
        target_weight = target_by_symbol.get(symbol, 0.0)
        delta_weight = round(target_weight - current_weight, 8)
        trades.append(
            ConstructionTradeIntent(
                symbol=symbol,
                action=_trade_action(current_weight, target_weight, delta_weight),
                current_weight=current_weight,
                target_weight=target_weight,
                delta_weight=delta_weight,
            )
        )
    return trades


def _trade_action(current_weight: float, target_weight: float, delta_weight: float) -> ConstructionTradeAction:
    if abs(delta_weight) <= EPSILON:
        return cast(ConstructionTradeAction, "hold")
    if current_weight <= EPSILON and target_weight > EPSILON:
        return cast(ConstructionTradeAction, "initiate")
    if target_weight <= EPSILON and current_weight > EPSILON:
        return cast(ConstructionTradeAction, "exit")
    if delta_weight > 0:
        return cast(ConstructionTradeAction, "buy")
    return cast(ConstructionTradeAction, "sell")


def _evaluate_constraints(
    request: ConstructionRunRequest,
    final_target_weights: list[ConstructionWeight],
    selected: list[ConstructionRankedCandidateInput],
    *,
    infeasible_reasons: list[str],
) -> list[ConstructionConstraintEvaluation]:
    total = round(sum(item.weight for item in final_target_weights), 8)
    max_weight = max((item.weight for item in final_target_weights), default=0.0)
    eligible_symbols = {item.symbol for item in request.ranked_universe.ranked_candidates if item.eligible}
    target_symbols = {item.symbol for item in final_target_weights}
    only_eligible = target_symbols.issubset(eligible_symbols)
    any_negative = any(item.weight < -EPSILON for item in final_target_weights)
    top_n_short = len(selected) < request.policy.top_n
    return [
        ConstructionConstraintEvaluation(
            constraint_id="full_investment",
            status="fail" if final_target_weights and abs(total - 1.0) > 1e-6 else ("not_evaluated" if not final_target_weights else "binding"),
            actual_value=total if final_target_weights else None,
            limit_value=1.0,
            message="target weights must sum to 1.0",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="long_only",
            status="fail" if any_negative else ("not_evaluated" if not final_target_weights else "pass"),
            actual_value=min((item.weight for item in final_target_weights), default=None),
            limit_value=0.0,
            message="target weights must remain non-negative",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="eligible_ranked_universe_only",
            status="fail" if (not only_eligible or top_n_short) else ("not_evaluated" if not final_target_weights else "pass"),
            actual_value=float(len(target_symbols - eligible_symbols)) if final_target_weights else None,
            limit_value=0.0,
            message="selected names must come only from the eligible ranked universe",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="max_position_weight",
            status="fail" if final_target_weights and max_weight > request.hard_constraints.max_position_weight + EPSILON else ("not_evaluated" if not final_target_weights else ("binding" if abs(max_weight - request.hard_constraints.max_position_weight) <= 1e-6 else "pass")),
            actual_value=max_weight if final_target_weights else None,
            limit_value=request.hard_constraints.max_position_weight,
            message="no target weight may exceed max_position_weight",
        ),
    ] if not infeasible_reasons or final_target_weights else [
        ConstructionConstraintEvaluation(
            constraint_id="full_investment",
            status="not_evaluated",
            actual_value=None,
            limit_value=1.0,
            message="target weights were not produced because the request is infeasible",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="long_only",
            status="not_evaluated",
            actual_value=None,
            limit_value=0.0,
            message="target weights were not produced because the request is infeasible",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="eligible_ranked_universe_only",
            status="fail" if top_n_short else "not_evaluated",
            actual_value=float(max(request.policy.top_n - len(selected), 0)),
            limit_value=0.0,
            message="eligible ranked universe does not contain enough names for the requested top_n" if top_n_short else "target weights were not produced because the request is infeasible",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="max_position_weight",
            status="fail" if "equal-weight seed exceeds max_position_weight" in infeasible_reasons else "not_evaluated",
            actual_value=round(1.0 / request.policy.top_n, 8),
            limit_value=request.hard_constraints.max_position_weight,
            message="equal-weight seed exceeds max_position_weight" if "equal-weight seed exceeds max_position_weight" in infeasible_reasons else "target weights were not produced because the request is infeasible",
        ),
    ]
