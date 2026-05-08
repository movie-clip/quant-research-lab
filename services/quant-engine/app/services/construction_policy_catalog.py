from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from app.schemas.construction import (
    ConstructionPolicyCatalogEntry,
    ConstructionPolicyId,
    ConstructionPolicyLaunchProfile,
    ConstructionPolicyLaunchProfilePolicyStatus,
    ConstructionRankedCandidateInput,
    ConstructionSelectionRuleId,
    ConstructionWeight,
)

ELIGIBLE_ONLY_RULE_ID: ConstructionSelectionRuleId = "eligible_only"
TAKE_TOP_N_RULE_ID: ConstructionSelectionRuleId = "take_top_n"
RANKING_ARTIFACT_REVIEW_HANDOFF_PROFILE_ID = "ranking_artifact_review_handoff_v1"


def _ranking_artifact_review_handoff_launch_profile(
    policy_status: ConstructionPolicyLaunchProfilePolicyStatus,
) -> ConstructionPolicyLaunchProfile:
    return ConstructionPolicyLaunchProfile(
        profile_id=RANKING_ARTIFACT_REVIEW_HANDOFF_PROFILE_ID,
        profile_kind="ranking_artifact_review_handoff",
        policy_status=policy_status,
        launch_top_n=2,
    )


def _validate_launch_profile(definition: ConstructionPolicyDefinition) -> None:
    entry = definition.catalog_entry
    profile = entry.launch_profile
    if profile.profile_id != RANKING_ARTIFACT_REVIEW_HANDOFF_PROFILE_ID:
        raise ValueError(f"construction policy {entry.policy_id} has unsupported launch_profile.profile_id")
    if profile.profile_kind != "ranking_artifact_review_handoff":
        raise ValueError(f"construction policy {entry.policy_id} has unsupported launch_profile.profile_kind")
    if profile.launch_top_n != entry.launch_top_n:
        raise ValueError(f"construction policy {entry.policy_id} launch profile launch_top_n must match launch_top_n")

    expected_rows = {
        "top_n_equal_weight_v1": {
            "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
            "ranking_support": "selection_only",
            "launch_status": "default",
        },
        "top_n_linear_rank_weight_v1": {
            "policy_definition_id": "construction_policy_definition_top_n_linear_rank_weight_v1",
            "ranking_support": "linear_selected_order_weighting",
            "launch_status": "opt_in",
        },
        "top_n_inverse_rank_weight_v1": {
            "policy_definition_id": "construction_policy_definition_top_n_inverse_rank_weight_v1",
            "ranking_support": "inverse_selected_order_weighting",
            "launch_status": "excluded",
        },
    }
    expected = expected_rows.get(entry.policy_id)
    if expected is None:
        raise ValueError(f"construction policy {entry.policy_id} is not supported by the canonical launch profile")
    if entry.policy_definition_id != expected["policy_definition_id"]:
        raise ValueError(f"construction policy {entry.policy_id} launch profile metadata disagrees with policy_definition_id")
    if entry.ranking_support != expected["ranking_support"]:
        raise ValueError(f"construction policy {entry.policy_id} launch profile metadata disagrees with ranking_support")
    if profile.policy_status != expected["launch_status"]:
        raise ValueError(f"construction policy {entry.policy_id} launch profile metadata disagrees with policy_id")


def _validate_canonical_launch_profile_catalog(policy_catalog: tuple[ConstructionPolicyDefinition, ...]) -> None:
    matching_profiles = [
        definition
        for definition in policy_catalog
        if definition.catalog_entry.launch_profile.profile_id == RANKING_ARTIFACT_REVIEW_HANDOFF_PROFILE_ID
    ]
    if not matching_profiles:
        raise ValueError("construction policy catalog is missing the canonical ranking-artifact review handoff launch profile")

    default_rows = [
        definition.catalog_entry.policy_id
        for definition in matching_profiles
        if definition.catalog_entry.launch_profile.policy_status == "default"
    ]
    if len(default_rows) != 1 or default_rows[0] != "top_n_equal_weight_v1":
        raise ValueError("construction policy catalog must define exactly one default launch policy for ranking-artifact review handoff")

    included_rows = sorted(
        definition.catalog_entry.policy_id
        for definition in matching_profiles
        if definition.catalog_entry.launch_profile.policy_status in {"default", "opt_in"}
    )
    if included_rows != ["top_n_equal_weight_v1", "top_n_linear_rank_weight_v1"]:
        raise ValueError("construction policy catalog ranking-artifact review handoff profile must include only equal-weight and linear-rank launch policies")

    excluded_rows = sorted(
        definition.catalog_entry.policy_id
        for definition in matching_profiles
        if definition.catalog_entry.launch_profile.policy_status == "excluded"
    )
    if excluded_rows != ["top_n_inverse_rank_weight_v1"]:
        raise ValueError("construction policy catalog ranking-artifact review handoff profile must exclude inverse-rank from launch")

    for definition in matching_profiles:
        _validate_launch_profile(definition)


@dataclass(frozen=True)
class ConstructionPolicyDefinition:
    catalog_entry: ConstructionPolicyCatalogEntry
    max_position_failure_reason: str
    cutoff_exclusion_reason: str
    raw_weight_numerator_builder: Callable[[int], list[Fraction]]

    @property
    def selection_rule_ids(self) -> tuple[ConstructionSelectionRuleId, ...]:
        return tuple(self.catalog_entry.selection_rule_ids)


def _equal_weight_numerators(selected_count: int) -> list[Fraction]:
    return [Fraction(1, selected_count)] * selected_count


def _inverse_rank_weight_numerators(selected_count: int) -> list[Fraction]:
    return [Fraction(1, selected_order_rank) for selected_order_rank in range(1, selected_count + 1)]


def _linear_rank_weight_numerators(selected_count: int) -> list[Fraction]:
    return [Fraction(selected_count - selected_order_rank + 1, 1) for selected_order_rank in range(1, selected_count + 1)]


POLICY_CATALOG: tuple[ConstructionPolicyDefinition, ...] = (
    ConstructionPolicyDefinition(
        catalog_entry=ConstructionPolicyCatalogEntry(
            policy_id="top_n_equal_weight_v1",
            policy_definition_id="construction_policy_definition_top_n_equal_weight_v1",
            name="Top N Equal Weight v1",
            description="Select eligible top-ranked names and assign equal target weights.",
            family="top_n_equal_weight",
            constraints="long_only_fully_invested_max_position_turnover",
            inputs="ranked_universe_and_current_portfolio",
            determinism="deterministic_rank_order",
            ranking_support="selection_only",
            full_investment_constraint="required",
            long_only_constraint="required",
            eligible_ranked_universe_constraint="required",
            max_position_weight_constraint="required",
            min_position_weight_constraint="supported_optional",
            max_turnover_weight_constraint="supported_optional",
            max_trade_intent_count_constraint="supported_optional",
            ranked_universe_input="required",
            current_portfolio_input="required",
            launch_top_n=2,
            selection_rule_ids=[ELIGIBLE_ONLY_RULE_ID, TAKE_TOP_N_RULE_ID],
            launch_profile=_ranking_artifact_review_handoff_launch_profile("default"),
        ),
        max_position_failure_reason="equal-weight seed exceeds max_position_weight",
        cutoff_exclusion_reason="not selected by top_n_equal_weight_v1 cutoff",
        raw_weight_numerator_builder=_equal_weight_numerators,
    ),
    ConstructionPolicyDefinition(
        catalog_entry=ConstructionPolicyCatalogEntry(
            policy_id="top_n_inverse_rank_weight_v1",
            policy_definition_id="construction_policy_definition_top_n_inverse_rank_weight_v1",
            name="Top N Inverse Rank Weight v1",
            description="Select eligible top-ranked names and weight them by inverse selected-order rank.",
            family="top_n_rank_weighted",
            constraints="long_only_fully_invested_max_position_turnover",
            inputs="ranked_universe_and_current_portfolio",
            determinism="deterministic_rank_order",
            ranking_support="inverse_selected_order_weighting",
            full_investment_constraint="required",
            long_only_constraint="required",
            eligible_ranked_universe_constraint="required",
            max_position_weight_constraint="required",
            min_position_weight_constraint="supported_optional",
            max_turnover_weight_constraint="supported_optional",
            max_trade_intent_count_constraint="supported_optional",
            ranked_universe_input="required",
            current_portfolio_input="required",
            launch_top_n=2,
            selection_rule_ids=[ELIGIBLE_ONLY_RULE_ID, TAKE_TOP_N_RULE_ID],
            launch_profile=_ranking_artifact_review_handoff_launch_profile("excluded"),
        ),
        max_position_failure_reason="inverse-rank seed exceeds max_position_weight",
        cutoff_exclusion_reason="not selected by top_n_inverse_rank_weight_v1 cutoff",
        raw_weight_numerator_builder=_inverse_rank_weight_numerators,
    ),
    ConstructionPolicyDefinition(
        catalog_entry=ConstructionPolicyCatalogEntry(
            policy_id="top_n_linear_rank_weight_v1",
            policy_definition_id="construction_policy_definition_top_n_linear_rank_weight_v1",
            name="Top N Linear Rank Weight v1",
            description="Select eligible top-ranked names and weight them by selected-order linear rank numerators N..1.",
            family="top_n_rank_weighted",
            constraints="long_only_fully_invested_max_position_turnover",
            inputs="ranked_universe_and_current_portfolio",
            determinism="deterministic_rank_order",
            ranking_support="linear_selected_order_weighting",
            full_investment_constraint="required",
            long_only_constraint="required",
            eligible_ranked_universe_constraint="required",
            max_position_weight_constraint="required",
            min_position_weight_constraint="supported_optional",
            max_turnover_weight_constraint="supported_optional",
            max_trade_intent_count_constraint="supported_optional",
            ranked_universe_input="required",
            current_portfolio_input="required",
            launch_top_n=2,
            selection_rule_ids=[ELIGIBLE_ONLY_RULE_ID, TAKE_TOP_N_RULE_ID],
            launch_profile=_ranking_artifact_review_handoff_launch_profile("opt_in"),
        ),
        max_position_failure_reason="linear-rank seed exceeds max_position_weight",
        cutoff_exclusion_reason="not selected by top_n_linear_rank_weight_v1 cutoff",
        raw_weight_numerator_builder=_linear_rank_weight_numerators,
    ),
)

_POLICY_BY_ID: dict[str, ConstructionPolicyDefinition] = {
    definition.catalog_entry.policy_id: definition for definition in POLICY_CATALOG
}

_validate_canonical_launch_profile_catalog(POLICY_CATALOG)


def list_construction_policies(
    *,
    family: str | None = None,
    constraints: str | None = None,
    inputs: str | None = None,
    determinism: str | None = None,
    ranking_support: str | None = None,
    full_investment_constraint: str | None = None,
    long_only_constraint: str | None = None,
    eligible_ranked_universe_constraint: str | None = None,
    max_position_weight_constraint: str | None = None,
    min_position_weight_constraint: str | None = None,
    max_turnover_weight_constraint: str | None = None,
    max_trade_intent_count_constraint: str | None = None,
    ranked_universe_input: str | None = None,
    current_portfolio_input: str | None = None,
    launch_top_n: int | None = None,
) -> list[ConstructionPolicyCatalogEntry]:
    _validate_canonical_launch_profile_catalog(POLICY_CATALOG)
    policies: list[ConstructionPolicyCatalogEntry] = []
    for definition in POLICY_CATALOG:
        entry = definition.catalog_entry
        if family is not None and entry.family != family:
            continue
        if constraints is not None and entry.constraints != constraints:
            continue
        if inputs is not None and entry.inputs != inputs:
            continue
        if determinism is not None and entry.determinism != determinism:
            continue
        if ranking_support is not None and entry.ranking_support != ranking_support:
            continue
        if full_investment_constraint is not None and entry.full_investment_constraint != full_investment_constraint:
            continue
        if long_only_constraint is not None and entry.long_only_constraint != long_only_constraint:
            continue
        if (
            eligible_ranked_universe_constraint is not None
            and entry.eligible_ranked_universe_constraint != eligible_ranked_universe_constraint
        ):
            continue
        if max_position_weight_constraint is not None and entry.max_position_weight_constraint != max_position_weight_constraint:
            continue
        if min_position_weight_constraint is not None and entry.min_position_weight_constraint != min_position_weight_constraint:
            continue
        if max_turnover_weight_constraint is not None and entry.max_turnover_weight_constraint != max_turnover_weight_constraint:
            continue
        if (
            max_trade_intent_count_constraint is not None
            and entry.max_trade_intent_count_constraint != max_trade_intent_count_constraint
        ):
            continue
        if ranked_universe_input is not None and entry.ranked_universe_input != ranked_universe_input:
            continue
        if current_portfolio_input is not None and entry.current_portfolio_input != current_portfolio_input:
            continue
        if launch_top_n is not None and entry.launch_top_n != launch_top_n:
            continue
        policies.append(entry.model_copy(deep=True))
    return policies


def get_construction_policy_definition(policy_id: str) -> ConstructionPolicyDefinition | None:
    return _POLICY_BY_ID.get(policy_id)


def build_policy_weights(
    definition: ConstructionPolicyDefinition,
    selected: list[ConstructionRankedCandidateInput],
    *,
    max_position_weight: float,
    epsilon: float,
    normalize_weights,
) -> tuple[list[ConstructionWeight], list[ConstructionWeight], str | None]:
    if not selected:
        return [], [], None
    weights = normalize_weights(definition.raw_weight_numerator_builder(len(selected)))
    failure_reason = None
    if weights and max(weights) > max_position_weight + epsilon:
        failure_reason = definition.max_position_failure_reason
    construction_weights = [
        ConstructionWeight(symbol=item.symbol, weight=weight)
        for item, weight in zip(selected, weights, strict=True)
    ]
    return construction_weights, construction_weights.copy(), failure_reason


def get_policy_cutoff_exclusion_reason(definition: ConstructionPolicyDefinition) -> str:
    return definition.cutoff_exclusion_reason
