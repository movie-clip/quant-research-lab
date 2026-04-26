from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from app.schemas.construction import (
    ConstructionArtifact,
    ConstructionConstraintEvaluation,
    ConstructionCurrentPortfolioInput,
    ConstructionDeterministicOrdering,
    EtfRankingArtifactConstructionHandoff,
    ConstructionExcludedName,
    ConstructionHardConstraints,
    ConstructionNormalizedInputs,
    ConstructionPolicyInput,
    ConstructionRankedCandidateInput,
    ConstructionRankedUniverseInput,
    ConstructionRunRequest,
    ConstructionSelectionRuleId,
    ConstructionSelectionRuleTrace,
    ConstructionSelectionRuleTraceStep,
    ConstructionSelectedName,
    ConstructionTurnoverConstraintContext,
    ConstructionTurnoverDiagnosticsInclusionFlags,
    ConstructionTurnoverDiagnosticsV1,
    ConstructionTurnoverFeasibilityContext,
    ConstructionTurnoverTradeIntentContext,
    ConstructionTradeIntent,
    ConstructionWeight,
    ConstructionWeightingTraceArtifactBinding,
    ConstructionWeightingTraceNormalization,
    ConstructionWeightingTracePosition,
    ConstructionWeightingTraceStage,
    ConstructionWeightingTraceV1,
    build_construction_turnover_symbol_contributions,
    calculate_construction_turnover,
    resolve_construction_trade_action,
)
from app.schemas.research import EtfRankingArtifact, EtfRankingRow
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
    weighting_trace_v1: ConstructionWeightingTraceV1
    max_position_failure_reason: str | None = None
    min_position_failure_reason: str | None = None


TURNOVER_FAILURE_REASON = "target turnover exceeds max_turnover_weight"
TRADE_INTENT_COUNT_FAILURE_REASON = "trade intent count exceeds max_trade_intent_count"
MIN_POSITION_OVER_MAX_FAILURE_REASON = "min_position_weight exceeds max_position_weight"


def _min_position_selected_capacity_failure_reason(min_position_weight: float, selected_count: int) -> str:
    return (
        f"min_position_weight={min_position_weight:.8f} is infeasible for selected_count={selected_count} under full investment"
    )


def _min_position_policy_output_failure_reason(min_position_weight: float) -> str:
    return f"policy output violates min_position_weight={min_position_weight:.8f}"


def build_construction_run(
    request: ConstructionRunRequest,
    *,
    artifact_store: ConstructionArtifactStore | None = None,
) -> ConstructionArtifact:
    prepared_request = prepare_construction_run_request(request)
    if prepared_request.ranked_universe is None:
        raise ValueError("construction run request must include resolved ranked_universe")
    ranked_universe = prepared_request.ranked_universe
    policy_definition = get_construction_policy_definition(prepared_request.policy.policy_id)
    if policy_definition is None:
        raise ValueError(f"unsupported construction policy: {request.policy.policy_id}")

    normalized_ranked = _normalize_ranked_candidates(ranked_universe.ranked_candidates)
    normalized_current = _normalize_current_weights(prepared_request.current_portfolio)
    selection = _run_selection_rule_pipeline(
        normalized_ranked,
        top_n=prepared_request.policy.top_n,
        policy_definition=policy_definition,
    )
    normalized_inputs = _build_normalized_inputs(
        prepared_request,
        policy_definition=policy_definition,
        normalized_current=normalized_current,
        normalized_ranked=normalized_ranked,
    )
    failure_reasons: list[str] = []

    if not selection.eligible_candidates:
        failure_reasons.append("eligible ranked universe is empty")
    if len(selection.eligible_candidates) < prepared_request.policy.top_n:
        failure_reasons.append("eligible ranked universe has fewer names than requested top_n")

    selected = selection.selected_candidates
    weighting = _build_policy_weights(
        policy_definition,
        selected,
        max_position_weight=prepared_request.hard_constraints.max_position_weight,
        min_position_weight=prepared_request.hard_constraints.min_position_weight,
    )
    if weighting.max_position_failure_reason is not None:
        failure_reasons.append(weighting.max_position_failure_reason)
    if weighting.min_position_failure_reason is not None:
        failure_reasons.append(weighting.min_position_failure_reason)

    generated_target_weights = weighting.final_target_weights
    max_trade_intent_count = prepared_request.hard_constraints.max_trade_intent_count
    generated_trade_intents = (
        _build_trade_intents(normalized_current, generated_target_weights)
        if generated_target_weights and max_trade_intent_count is not None
        else []
    )
    generated_turnover = (
        calculate_construction_turnover(normalized_current, generated_target_weights)
        if generated_target_weights
        else None
    )
    max_turnover_weight = prepared_request.hard_constraints.max_turnover_weight
    if (
        generated_turnover is not None
        and max_turnover_weight is not None
        and generated_turnover > max_turnover_weight + EPSILON
    ):
        failure_reasons.append(TURNOVER_FAILURE_REASON)
    if (
        max_trade_intent_count is not None
        and len(generated_trade_intents) > max_trade_intent_count
    ):
        failure_reasons.append(TRADE_INTENT_COUNT_FAILURE_REASON)
    persisted_infeasible_trade_intents = (
        generated_trade_intents
        if TRADE_INTENT_COUNT_FAILURE_REASON in failure_reasons
        else []
    )

    if failure_reasons:
        turnover_diagnostics_v1 = _build_turnover_diagnostics(
            status="infeasible",
            current_weights=normalized_current,
            generated_target_weights=generated_target_weights,
            trade_intents=persisted_infeasible_trade_intents,
            max_turnover_weight=max_turnover_weight,
            failure_reasons=failure_reasons,
        )
        infeasible_weighting_trace = weighting.weighting_trace_v1.model_copy(
            update={
                "artifact_binding": weighting.weighting_trace_v1.artifact_binding.model_copy(
                    update={
                        "binding_status": "generated_target_weights_not_persisted_due_to_infeasible_artifact",
                        "final_target_weights_present": False,
                    }
                )
            }
        )
        artifact = ConstructionArtifact(
            artifact_id="construction_artifact_pending",
            fingerprint="0" * 64,
            status="infeasible",
            request_id=prepared_request.request_id,
            policy=prepared_request.policy,
            hard_constraints=prepared_request.hard_constraints,
            normalized_inputs=normalized_inputs,
            selected_names=[ConstructionSelectedName(symbol=item.symbol, rank=item.rank, score=item.score) for item in selected],
            excluded_names=_build_excluded_names(
                normalized_ranked,
                selected_symbols=[item.symbol for item in selected],
                policy_definition=policy_definition,
            ),
            seed_weights=[],
            final_target_weights=[],
            trade_intents=persisted_infeasible_trade_intents,
            constraint_evaluations=_evaluate_constraints(
                prepared_request,
                current_weights=normalized_current,
                final_target_weights=[],
                generated_target_weights=generated_target_weights,
                trade_intents=persisted_infeasible_trade_intents,
                trade_intents_persisted=TRADE_INTENT_COUNT_FAILURE_REASON in failure_reasons,
                selected=selected,
                infeasible_reasons=failure_reasons,
            ),
            deterministic_ordering=ConstructionDeterministicOrdering(
                ranked_candidate_symbols=[item.symbol for item in normalized_ranked],
                selected_symbols=[item.symbol for item in selected],
                trade_symbols=[item.symbol for item in persisted_infeasible_trade_intents],
            ),
            selection_rule_trace=selection.trace,
            turnover_diagnostics_status="available",
            turnover_diagnostics_v1=turnover_diagnostics_v1,
            weighting_trace_status="available",
            weighting_trace_v1=infeasible_weighting_trace,
            failure_reasons=failure_reasons,
        )
        return persist_construction_artifact(build_stable_construction_artifact(artifact), store=artifact_store)

    seed_weights = weighting.seed_weights
    final_target_weights = generated_target_weights
    trade_intents = _build_trade_intents(normalized_current, final_target_weights)
    turnover_diagnostics_v1 = _build_turnover_diagnostics(
        status="feasible",
        current_weights=normalized_current,
        generated_target_weights=final_target_weights,
        trade_intents=trade_intents,
        max_turnover_weight=max_turnover_weight,
        failure_reasons=[],
    )
    feasible_weighting_trace = weighting.weighting_trace_v1.model_copy(
        update={
            "artifact_binding": weighting.weighting_trace_v1.artifact_binding.model_copy(
                update={
                    "binding_status": "final_target_weights_persisted",
                    "final_target_weights_present": True,
                }
            )
        }
    )
    artifact = ConstructionArtifact(
        artifact_id="construction_artifact_pending",
        fingerprint="0" * 64,
        status="feasible",
        request_id=prepared_request.request_id,
        policy=prepared_request.policy,
        hard_constraints=prepared_request.hard_constraints,
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
            prepared_request,
            current_weights=normalized_current,
            final_target_weights=final_target_weights,
            generated_target_weights=final_target_weights,
            trade_intents=trade_intents,
            trade_intents_persisted=True,
            selected=selected,
            infeasible_reasons=[],
        ),
        deterministic_ordering=ConstructionDeterministicOrdering(
            ranked_candidate_symbols=[item.symbol for item in normalized_ranked],
            selected_symbols=[item.symbol for item in selected],
            trade_symbols=[item.symbol for item in trade_intents],
        ),
        selection_rule_trace=selection.trace,
        turnover_diagnostics_status="available",
        turnover_diagnostics_v1=turnover_diagnostics_v1,
        weighting_trace_status="available",
        weighting_trace_v1=feasible_weighting_trace,
        failure_reasons=[],
    )
    return persist_construction_artifact(build_stable_construction_artifact(artifact), store=artifact_store)


def prepare_construction_run_request(request: ConstructionRunRequest) -> ConstructionRunRequest:
    if request.ranked_universe is not None and request.ranking_artifact_handoff is None:
        return request
    handoff = request.ranking_artifact_handoff
    if handoff is None:
        raise ValueError("construction run request must provide exactly one of ranked_universe or ranking_artifact_handoff")
    if request.ranked_universe is None:
        raise ValueError("ranking artifact handoff must be resolved to ranked_universe before construction execution")
    return request


def build_construction_run_request_from_ranking_artifact_handoff(
    *,
    request_id: str | None,
    handoff: EtfRankingArtifactConstructionHandoff,
    artifact: EtfRankingArtifact,
    current_portfolio: ConstructionCurrentPortfolioInput,
    policy: ConstructionPolicyInput,
    hard_constraints: ConstructionHardConstraints,
) -> ConstructionRunRequest:
    if handoff.artifact_kind != "etf_ranking":
        raise ValueError("unsupported ranking artifact kind")
    if artifact.schema_version != "etf_ranking_artifact_v1":
        raise ValueError("unsupported etf ranking schema_version")
    if handoff.artifact_id != artifact.artifact_id:
        raise ValueError("ranking artifact handoff artifact_id does not match persisted artifact")
    if handoff.schema_version != artifact.schema_version:
        raise ValueError("ranking artifact handoff schema_version does not match persisted artifact")
    if handoff.ranking_id != artifact.ranking_id:
        raise ValueError("ranking artifact handoff ranking_id does not match persisted artifact")
    if handoff.methodology_id != artifact.run_metadata.methodology_id:
        raise ValueError("ranking artifact handoff methodology_id does not match persisted artifact")
    if handoff.as_of_date != artifact.run_metadata.as_of_date:
        raise ValueError("ranking artifact handoff as_of_date does not match persisted artifact")

    ranked_candidates = _build_ranked_candidates_from_etf_ranking_artifact(artifact)
    if not any(candidate.eligible for candidate in ranked_candidates):
        raise ValueError("persisted etf ranking artifact has no eligible ranked candidates for construction")

    return ConstructionRunRequest.model_construct(
        request_id=request_id,
        ranked_universe=ConstructionRankedUniverseInput(
            artifact_id=artifact.artifact_id,
            ranking_id=artifact.ranking_id,
            methodology_id=artifact.run_metadata.methodology_id,
            as_of_date=artifact.run_metadata.as_of_date,
            ranked_candidates=ranked_candidates,
        ),
        ranking_artifact_handoff=handoff,
        current_portfolio=current_portfolio,
        policy=policy,
        hard_constraints=hard_constraints,
    )


def _build_ranked_candidates_from_etf_ranking_artifact(
    artifact: EtfRankingArtifact,
) -> list[ConstructionRankedCandidateInput]:
    return [_build_ranked_candidate_from_etf_ranking_row(row) for row in artifact.ranked_universe]


def _build_ranked_candidate_from_etf_ranking_row(
    row: EtfRankingRow,
) -> ConstructionRankedCandidateInput:
    return ConstructionRankedCandidateInput(
        symbol=row.symbol,
        rank=row.rank,
        eligible=True,
        score=row.composite_score,
        exclusion_reason=None,
    )


def _build_normalized_inputs(
    request: ConstructionRunRequest,
    *,
    policy_definition: ConstructionPolicyDefinition,
    normalized_current: list[ConstructionWeight],
    normalized_ranked: list[ConstructionRankedCandidateInput],
) -> ConstructionNormalizedInputs:
    ranked_universe = request.ranked_universe
    if ranked_universe is None:
        raise ValueError("construction run request must include resolved ranked_universe")
    handoff = request.ranking_artifact_handoff
    return ConstructionNormalizedInputs(
        ranked_universe_artifact_kind=handoff.artifact_kind if handoff is not None else None,
        ranked_universe_artifact_id=ranked_universe.artifact_id,
        ranked_universe_artifact_schema_version=handoff.schema_version if handoff is not None else None,
        ranking_id=ranked_universe.ranking_id,
        ranking_methodology_id=ranked_universe.methodology_id,
        ranking_as_of_date=ranked_universe.as_of_date,
        current_portfolio_artifact_id=request.current_portfolio.artifact_id,
        current_portfolio_as_of_timestamp=request.current_portfolio.as_of_timestamp,
        policy_id=request.policy.policy_id,
        policy_definition_id=policy_definition.catalog_entry.policy_definition_id,
        top_n=request.policy.top_n,
        max_position_weight=request.hard_constraints.max_position_weight,
        min_position_weight=request.hard_constraints.min_position_weight,
        max_trade_intent_count=request.hard_constraints.max_trade_intent_count,
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
    min_position_weight: float | None,
) -> _WeightingResult:
    raw_weight_numerators = policy_definition.raw_weight_numerator_builder(len(selected)) if selected else []
    seed_weights, final_target_weights, max_position_failure_reason = build_policy_weights(
        policy_definition,
        selected,
        max_position_weight=max_position_weight,
        epsilon=EPSILON,
        normalize_weights=_normalized_fractional_weights,
    )
    min_position_failure_reason = None
    if min_position_weight is not None and selected:
        if min_position_weight > max_position_weight + EPSILON:
            min_position_failure_reason = MIN_POSITION_OVER_MAX_FAILURE_REASON
        elif min_position_weight * len(selected) > 1.0 + EPSILON:
            min_position_failure_reason = _min_position_selected_capacity_failure_reason(
                min_position_weight,
                len(selected),
            )
        elif final_target_weights and min(item.weight for item in final_target_weights) + EPSILON < min_position_weight:
            min_position_failure_reason = _min_position_policy_output_failure_reason(min_position_weight)
    return _WeightingResult(
        seed_weights=seed_weights,
        final_target_weights=final_target_weights,
        weighting_trace_v1=_build_weighting_trace(
            policy_definition=policy_definition,
            selected=selected,
            raw_weight_numerators=raw_weight_numerators,
            seed_weights=seed_weights,
            final_target_weights=final_target_weights,
        ),
        max_position_failure_reason=max_position_failure_reason,
        min_position_failure_reason=min_position_failure_reason,
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


def _build_weighting_trace(
    *,
    policy_definition: ConstructionPolicyDefinition,
    selected: list[ConstructionRankedCandidateInput],
    raw_weight_numerators: list[Fraction],
    seed_weights: list[ConstructionWeight],
    final_target_weights: list[ConstructionWeight],
) -> ConstructionWeightingTraceV1:
    seed_weights_by_symbol = {item.symbol: item.weight for item in seed_weights}
    final_weights_by_symbol = {item.symbol: item.weight for item in final_target_weights}
    raw_weights_by_symbol = {
        candidate.symbol: float(raw_weight_numerator)
        for candidate, raw_weight_numerator in zip(selected, raw_weight_numerators, strict=True)
    }
    positions = [
        ConstructionWeightingTracePosition(
            symbol=candidate.symbol,
            rank=candidate.rank,
            selected_order=selected_order,
            input_value=float(selected_order),
            output_value=raw_weights_by_symbol[candidate.symbol],
        )
        for selected_order, candidate in enumerate(selected, start=1)
    ]
    seed_positions = [
        ConstructionWeightingTracePosition(
            symbol=position.symbol,
            rank=position.rank,
            selected_order=position.selected_order,
            input_value=position.output_value,
            output_value=seed_weights_by_symbol[position.symbol],
        )
        for position in positions
    ]
    target_positions = [
        ConstructionWeightingTracePosition(
            symbol=position.symbol,
            rank=position.rank,
            selected_order=position.selected_order,
            input_value=position.output_value,
            output_value=final_weights_by_symbol[position.symbol],
        )
        for position in seed_positions
    ]
    normalization = _build_weighting_trace_normalization(raw_weight_numerators, seed_weights)
    return ConstructionWeightingTraceV1(
        policy_id=policy_definition.catalog_entry.policy_id,
        policy_definition_id=policy_definition.catalog_entry.policy_definition_id,
        stages=[
            ConstructionWeightingTraceStage(
                stage_id="selected_order_to_raw_weight_numerator",
                stage_order=1,
                input_metric_id="selected_order",
                output_metric_id="raw_weight_numerator",
                positions=positions,
            ),
            ConstructionWeightingTraceStage(
                stage_id="raw_weight_numerator_to_seed_weight",
                stage_order=2,
                input_metric_id="raw_weight_numerator",
                output_metric_id="seed_weight",
                positions=seed_positions,
            ),
            ConstructionWeightingTraceStage(
                stage_id="seed_weight_to_target_weight",
                stage_order=3,
                input_metric_id="seed_weight",
                output_metric_id="target_weight",
                positions=target_positions,
            ),
        ],
        normalization=normalization,
        artifact_binding=ConstructionWeightingTraceArtifactBinding(
            binding_status="final_target_weights_persisted" if final_target_weights else "generated_target_weights_not_persisted_due_to_infeasible_artifact",
            final_target_weights_present=bool(final_target_weights),
        ),
    )


def _build_weighting_trace_normalization(
    raw_weight_numerators: list[Fraction],
    seed_weights: list[ConstructionWeight],
) -> ConstructionWeightingTraceNormalization:
    if not raw_weight_numerators:
        return ConstructionWeightingTraceNormalization(
            normalization_applied=False,
            normalization_method="not_applicable",
        )
    total = float(sum(raw_weight_numerators, start=Fraction(0, 1)))
    normalized_sum = round(sum(item.weight for item in seed_weights), 8)
    residual_symbol = seed_weights[-1].symbol
    residual_delta = round(seed_weights[-1].weight - round(float(raw_weight_numerators[-1] / sum(raw_weight_numerators, start=Fraction(0, 1))), 8), 8)
    normalization_method = (
        "single_position_force_to_one"
        if len(seed_weights) == 1
        else "fractional_sum_division_with_last_position_reconciliation"
    )
    return ConstructionWeightingTraceNormalization(
        normalization_applied=True,
        raw_value_sum=total,
        normalized_value_sum=normalized_sum,
        rounding_scale=8,
        normalization_method=normalization_method,
        residual_reconciliation_symbol=residual_symbol,
        residual_reconciliation_delta=residual_delta,
    )


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
                action=resolve_construction_trade_action(current_weight, target_weight, delta_weight),
                current_weight=current_weight,
                target_weight=target_weight,
                delta_weight=delta_weight,
            )
        )
    return trades


def _evaluate_constraints(
    request: ConstructionRunRequest,
    current_weights: list[ConstructionWeight],
    final_target_weights: list[ConstructionWeight],
    generated_target_weights: list[ConstructionWeight],
    trade_intents: list[ConstructionTradeIntent],
    trade_intents_persisted: bool,
    selected: list[ConstructionRankedCandidateInput],
    *,
    infeasible_reasons: list[str],
) -> list[ConstructionConstraintEvaluation]:
    ranked_universe = request.ranked_universe
    if ranked_universe is None:
        raise ValueError("construction run request must include resolved ranked_universe")
    constraint_weights = generated_target_weights if generated_target_weights else final_target_weights
    total = round(sum(item.weight for item in constraint_weights), 8)
    max_weight = max((item.weight for item in constraint_weights), default=0.0)
    min_weight = min((item.weight for item in constraint_weights), default=0.0)
    eligible_symbols = {item.symbol for item in ranked_universe.ranked_candidates if item.eligible}
    target_symbols = {item.symbol for item in constraint_weights}
    only_eligible = target_symbols.issubset(eligible_symbols)
    any_negative = any(item.weight < -EPSILON for item in constraint_weights)
    top_n_short = len(selected) < request.policy.top_n
    has_constraint_weights = bool(constraint_weights)
    min_position_weight = request.hard_constraints.min_position_weight
    max_turnover_weight = request.hard_constraints.max_turnover_weight
    max_trade_intent_count = request.hard_constraints.max_trade_intent_count
    turnover = calculate_construction_turnover(current_weights, constraint_weights) if has_constraint_weights else None
    has_trade_intent_count_evaluation = has_constraint_weights and max_trade_intent_count is not None and trade_intents_persisted
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
            constraint_id="min_position_weight",
            status=(
                "not_evaluated"
                if not has_constraint_weights or min_position_weight is None
                else (
                    "fail"
                    if min_weight + EPSILON < min_position_weight
                    else ("binding" if abs(min_weight - min_position_weight) <= 1e-6 else "pass")
                )
            ),
            actual_value=min_weight if has_constraint_weights and min_position_weight is not None else None,
            limit_value=min_position_weight,
            message="all target weights must be at least min_position_weight" if min_position_weight is not None else "min_position_weight was not requested",
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
        ConstructionConstraintEvaluation(
            constraint_id="max_trade_intent_count",
            status=(
                "not_evaluated"
                if not has_trade_intent_count_evaluation
                else (
                    "fail"
                    if len(trade_intents) > max_trade_intent_count
                    else ("binding" if len(trade_intents) == max_trade_intent_count else "pass")
                )
            ),
            actual_value=float(len(trade_intents)) if has_trade_intent_count_evaluation else None,
            limit_value=float(max_trade_intent_count) if max_trade_intent_count is not None else None,
            message=(
                "trade intent count must not exceed max_trade_intent_count"
                if has_trade_intent_count_evaluation
                else (
                    "target trade intents were not persisted because the request is infeasible"
                    if max_trade_intent_count is not None
                    else "max_trade_intent_count was not requested"
                )
            ),
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
            constraint_id="min_position_weight",
            status="not_evaluated",
            actual_value=None,
            limit_value=min_position_weight,
            message="target weights were not produced because the request is infeasible" if min_position_weight is not None else "min_position_weight was not requested",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="max_turnover_weight",
            status="not_evaluated",
            actual_value=None,
            limit_value=max_turnover_weight,
            message="target weights were not produced because the request is infeasible" if max_turnover_weight is not None else "max_turnover_weight was not requested",
        ),
        ConstructionConstraintEvaluation(
            constraint_id="max_trade_intent_count",
            status="not_evaluated",
            actual_value=None,
            limit_value=float(max_trade_intent_count) if max_trade_intent_count is not None else None,
            message=(
                "target weights were not produced because the request is infeasible"
                if max_trade_intent_count is not None
                else "max_trade_intent_count was not requested"
            ),
        ),
    ]


def _build_turnover_diagnostics(
    *,
    status,
    current_weights: list[ConstructionWeight],
    generated_target_weights: list[ConstructionWeight],
    trade_intents: list[ConstructionTradeIntent],
    max_turnover_weight: float | None,
    failure_reasons: list[str],
) -> ConstructionTurnoverDiagnosticsV1:
    turnover = (
        calculate_construction_turnover(current_weights, generated_target_weights)
        if generated_target_weights
        else None
    )
    requested = max_turnover_weight is not None
    evaluation_status = (
        "not_evaluated"
        if not requested
        else (
            "fail"
            if turnover is not None and turnover > max_turnover_weight + EPSILON
            else ("binding" if turnover is not None and abs(turnover - max_turnover_weight) <= 1e-6 else "pass")
        )
    )
    return ConstructionTurnoverDiagnosticsV1(
        reported_value_status="computed" if turnover is not None else "not_computed_no_generated_target_weights",
        reported_turnover_weight=turnover,
        inclusion_flags=ConstructionTurnoverDiagnosticsInclusionFlags(),
        trade_intent_context=ConstructionTurnoverTradeIntentContext(intent_count=len(trade_intents)),
        feasibility_context=ConstructionTurnoverFeasibilityContext(
            artifact_status=status,
            turnover_failure_reason_present=TURNOVER_FAILURE_REASON in failure_reasons,
        ),
        constraint_context=ConstructionTurnoverConstraintContext(
            requested=requested,
            limit_weight=max_turnover_weight,
            evaluation_status=evaluation_status,
        ),
        symbol_contributions=(
            build_construction_turnover_symbol_contributions(current_weights, generated_target_weights)
            if turnover is not None
            else []
        ),
    )
