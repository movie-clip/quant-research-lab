from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
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
    ConstructionSelectionRuleId,
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
from app.services.construction_policy_catalog import (
    ConstructionPolicyDefinition,
    ELIGIBLE_ONLY_RULE_ID,
    TAKE_TOP_N_RULE_ID,
    build_policy_weights,
    get_construction_policy_definition,
    get_policy_cutoff_exclusion_reason,
)

EPSILON = 1e-8


@dataclass(frozen=True)
class _SelectionPipelineResult:
    eligible_candidates: list[ConstructionRankedCandidateInput]
    selected_candidates: list[ConstructionRankedCandidateInput]
    trace: ConstructionSelectionRuleTrace


@dataclass(frozen=True)
class _WeightingResult:
    seed_weights: list[ConstructionWeight]
    final_target_weights: list[ConstructionWeight]
    max_position_failure_reason: str | None = None


TURNOVER_FAILURE_REASON = "target turnover exceeds max_turnover_weight"


def build_construction_run(
    request: ConstructionRunRequest,
    *,
    artifact_store: ConstructionArtifactStore | None = None,
) -> ConstructionArtifact:
    policy_definition = get_construction_policy_definition(request.policy.policy_id)
    if policy_definition is None:
        raise ValueError(f"unsupported construction policy: {request.policy.policy_id}")

    normalized_ranked = _normalize_ranked_candidates(request.ranked_universe.ranked_candidates)
    normalized_current = _normalize_current_weights(request.current_portfolio)
    selection = _run_selection_rule_pipeline(
        normalized_ranked,
        top_n=request.policy.top_n,
        policy_definition=policy_definition,
    )
    normalized_inputs = _build_normalized_inputs(
        request,
        policy_definition=policy_definition,
        normalized_current=normalized_current,
        normalized_ranked=normalized_ranked,
    )
    failure_reasons: list[str] = []

    if not selection.eligible_candidates:
        failure_reasons.append("eligible ranked universe is empty")
    if len(selection.eligible_candidates) < request.policy.top_n:
        failure_reasons.append("eligible ranked universe has fewer names than requested top_n")

    selected = selection.selected_candidates
    weighting = _build_policy_weights(
        policy_definition,
        selected,
        max_position_weight=request.hard_constraints.max_position_weight,
    )
    if weighting.max_position_failure_reason is not None:
        failure_reasons.append(weighting.max_position_failure_reason)

    generated_target_weights = weighting.final_target_weights
    generated_turnover = (
        _calculate_turnover(normalized_current, generated_target_weights) if generated_target_weights else None
    )
    max_turnover_weight = request.hard_constraints.max_turnover_weight
    if (
        generated_turnover is not None
        and max_turnover_weight is not None
        and generated_turnover > max_turnover_weight + EPSILON
    ):
        failure_reasons.append(TURNOVER_FAILURE_REASON)

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
            excluded_names=_build_excluded_names(
                normalized_ranked,
                selected_symbols=[item.symbol for item in selected],
                policy_definition=policy_definition,
            ),
            seed_weights=[],
            final_target_weights=[],
            trade_intents=[],
            constraint_evaluations=_evaluate_constraints(
                request,
                current_weights=normalized_current,
                final_target_weights=[],
                generated_target_weights=generated_target_weights,
                selected=selected,
                infeasible_reasons=failure_reasons,
            ),
            deterministic_ordering=ConstructionDeterministicOrdering(
                ranked_candidate_symbols=[item.symbol for item in normalized_ranked],
                selected_symbols=[item.symbol for item in selected],
                trade_symbols=[],
            ),
            selection_rule_trace=selection.trace,
            failure_reasons=failure_reasons,
        )
        return persist_construction_artifact(build_stable_construction_artifact(artifact), store=artifact_store)

    seed_weights = weighting.seed_weights
    final_target_weights = generated_target_weights
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
        excluded_names=_build_excluded_names(
            normalized_ranked,
            selected_symbols=[item.symbol for item in selected],
            policy_definition=policy_definition,
        ),
        seed_weights=seed_weights,
        final_target_weights=final_target_weights,
        trade_intents=trade_intents,
        constraint_evaluations=_evaluate_constraints(
            request,
            current_weights=normalized_current,
            final_target_weights=final_target_weights,
            generated_target_weights=final_target_weights,
            selected=selected,
            infeasible_reasons=[],
        ),
        deterministic_ordering=ConstructionDeterministicOrdering(
            ranked_candidate_symbols=[item.symbol for item in normalized_ranked],
            selected_symbols=[item.symbol for item in selected],
            trade_symbols=[item.symbol for item in trade_intents],
        ),
        selection_rule_trace=selection.trace,
        failure_reasons=[],
    )
    return persist_construction_artifact(build_stable_construction_artifact(artifact), store=artifact_store)


def _build_normalized_inputs(
    request: ConstructionRunRequest,
    *,
    policy_definition: ConstructionPolicyDefinition,
    normalized_current: list[ConstructionWeight],
    normalized_ranked: list[ConstructionRankedCandidateInput],
) -> ConstructionNormalizedInputs:
    return ConstructionNormalizedInputs(
        ranked_universe_artifact_id=request.ranked_universe.artifact_id,
        ranking_id=request.ranked_universe.ranking_id,
        ranking_methodology_id=request.ranked_universe.methodology_id,
        ranking_as_of_date=request.ranked_universe.as_of_date,
        current_portfolio_artifact_id=request.current_portfolio.artifact_id,
        current_portfolio_as_of_timestamp=request.current_portfolio.as_of_timestamp,
        policy_id=request.policy.policy_id,
        policy_definition_id=policy_definition.catalog_entry.policy_definition_id,
        top_n=request.policy.top_n,
        max_position_weight=request.hard_constraints.max_position_weight,
        current_portfolio_weights=normalized_current,
        ranked_candidates=normalized_ranked,
    )


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
    policy_definition: ConstructionPolicyDefinition,
) -> _SelectionPipelineResult:
    current = list(candidates)
    eligible_candidates = current
    trace_steps: list[ConstructionSelectionRuleTraceStep] = []
    selection_rule_ids = policy_definition.selection_rule_ids
    for rule_order, rule_id in enumerate(selection_rule_ids, start=1):
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
            rule_ids=[*selection_rule_ids],
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


def _build_policy_weights(
    policy_definition: ConstructionPolicyDefinition,
    selected: list[ConstructionRankedCandidateInput],
    *,
    max_position_weight: float,
) -> _WeightingResult:
    seed_weights, final_target_weights, max_position_failure_reason = build_policy_weights(
        policy_definition,
        selected,
        max_position_weight=max_position_weight,
        epsilon=EPSILON,
        normalize_weights=_normalized_fractional_weights,
    )
    return _WeightingResult(
        seed_weights=seed_weights,
        final_target_weights=final_target_weights,
        max_position_failure_reason=max_position_failure_reason,
    )


def _normalized_fractional_weights(raw_weights: list[Fraction]) -> list[float]:
    if not raw_weights:
        return []
    total = sum(raw_weights, start=Fraction(0, 1))
    normalized = [round(float(weight / total), 8) for weight in raw_weights]
    if len(normalized) == 1:
        return [1.0]
    normalized[-1] = round(1.0 - sum(normalized[:-1]), 8)
    return normalized


def _normalize_current_weights(current_portfolio: ConstructionCurrentPortfolioInput) -> list[ConstructionWeight]:
    deduped: dict[str, float] = {}
    for weight in current_portfolio.weights:
        deduped[weight.symbol] = deduped.get(weight.symbol, 0.0) + weight.weight
    normalized = [ConstructionWeight(symbol=symbol, weight=round(weight, 8)) for symbol, weight in sorted(deduped.items()) if weight > 0.0]
    total = sum(item.weight for item in normalized)
    if normalized and abs(total - 1.0) > 1e-6:
        raise ValueError("current_portfolio.weights must sum to 1.0")
    return normalized


def _build_excluded_names(
    candidates: list[ConstructionRankedCandidateInput],
    *,
    selected_symbols: list[str],
    policy_definition: ConstructionPolicyDefinition,
) -> list[ConstructionExcludedName]:
    selected = set(selected_symbols)
    excluded: list[ConstructionExcludedName] = []
    top_n_cutoff_reason = get_policy_cutoff_exclusion_reason(policy_definition)
    for item in candidates:
        if item.symbol in selected:
            continue
        reason = item.exclusion_reason or top_n_cutoff_reason
        if item.eligible and item.exclusion_reason is None:
            reason = top_n_cutoff_reason
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


def _calculate_turnover(current_weights: list[ConstructionWeight], target_weights: list[ConstructionWeight]) -> float:
    current_by_symbol = {item.symbol: item.weight for item in current_weights}
    target_by_symbol = {item.symbol: item.weight for item in target_weights}
    symbols = set(current_by_symbol) | set(target_by_symbol)
    return round(0.5 * sum(abs(target_by_symbol.get(symbol, 0.0) - current_by_symbol.get(symbol, 0.0)) for symbol in symbols), 8)


def _evaluate_constraints(
    request: ConstructionRunRequest,
    current_weights: list[ConstructionWeight],
    final_target_weights: list[ConstructionWeight],
    generated_target_weights: list[ConstructionWeight],
    selected: list[ConstructionRankedCandidateInput],
    *,
    infeasible_reasons: list[str],
) -> list[ConstructionConstraintEvaluation]:
    constraint_weights = generated_target_weights if generated_target_weights else final_target_weights
    total = round(sum(item.weight for item in constraint_weights), 8)
    max_weight = max((item.weight for item in constraint_weights), default=0.0)
    eligible_symbols = {item.symbol for item in request.ranked_universe.ranked_candidates if item.eligible}
    target_symbols = {item.symbol for item in constraint_weights}
    only_eligible = target_symbols.issubset(eligible_symbols)
    any_negative = any(item.weight < -EPSILON for item in constraint_weights)
    top_n_short = len(selected) < request.policy.top_n
    has_constraint_weights = bool(constraint_weights)
    max_turnover_weight = request.hard_constraints.max_turnover_weight
    turnover = _calculate_turnover(current_weights, constraint_weights) if has_constraint_weights else None
    return [
        ConstructionConstraintEvaluation(
            constraint_id="full_investment",
            status="fail" if has_constraint_weights and abs(total - 1.0) > 1e-6 else ("not_evaluated" if not has_constraint_weights else "binding"),
            actual_value=total if has_constraint_weights else None,
            limit_value=1.0,
            message="target weights must sum to 1.0",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="long_only",
            status="fail" if any_negative else ("not_evaluated" if not has_constraint_weights else "pass"),
            actual_value=min((item.weight for item in constraint_weights), default=None),
            limit_value=0.0,
            message="target weights must remain non-negative",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="eligible_ranked_universe_only",
            status="fail" if (not only_eligible or top_n_short) else ("not_evaluated" if not has_constraint_weights else "pass"),
            actual_value=float(len(target_symbols - eligible_symbols)) if has_constraint_weights else None,
            limit_value=0.0,
            message="selected names must come only from the eligible ranked universe",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="max_position_weight",
            status="fail" if has_constraint_weights and max_weight > request.hard_constraints.max_position_weight + EPSILON else ("not_evaluated" if not has_constraint_weights else ("binding" if abs(max_weight - request.hard_constraints.max_position_weight) <= 1e-6 else "pass")),
            actual_value=max_weight if has_constraint_weights else None,
            limit_value=request.hard_constraints.max_position_weight,
            message="no target weight may exceed max_position_weight",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="max_turnover_weight",
            status=(
                "not_evaluated"
                if not has_constraint_weights or max_turnover_weight is None
                else (
                    "fail"
                    if turnover is not None and turnover > max_turnover_weight + EPSILON
                    else ("binding" if turnover is not None and abs(turnover - max_turnover_weight) <= 1e-6 else "pass")
                )
            ),
            actual_value=turnover if has_constraint_weights and max_turnover_weight is not None else None,
            limit_value=max_turnover_weight,
            message="portfolio turnover must not exceed max_turnover_weight" if max_turnover_weight is not None else "max_turnover_weight was not requested",
        ),
    ] if not infeasible_reasons or has_constraint_weights else [
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
            actual_value=float(max(request.policy.top_n - len(selected), 0)) if top_n_short else None,
            limit_value=0.0,
            message="eligible ranked universe does not contain enough names for the requested top_n" if top_n_short else "target weights were not produced because the request is infeasible",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="max_position_weight",
            status="not_evaluated",
            actual_value=None,
            limit_value=request.hard_constraints.max_position_weight,
            message="target weights were not produced because the request is infeasible",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="max_turnover_weight",
            status="not_evaluated",
            actual_value=None,
            limit_value=max_turnover_weight,
            message="target weights were not produced because the request is infeasible" if max_turnover_weight is not None else "max_turnover_weight was not requested",
        ),
    ]
