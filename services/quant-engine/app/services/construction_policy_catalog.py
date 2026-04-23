from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Callable

from app.schemas.construction import ConstructionPolicyCatalogEntry, ConstructionPolicyId, ConstructionRankedCandidateInput, ConstructionSelectionRuleId, ConstructionWeight

ELIGIBLE_ONLY_RULE_ID: ConstructionSelectionRuleId = "eligible_only"
TAKE_TOP_N_RULE_ID: ConstructionSelectionRuleId = "take_top_n"


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


POLICY_CATALOG: tuple[ConstructionPolicyDefinition, ...] = (
    ConstructionPolicyDefinition(
        catalog_entry=ConstructionPolicyCatalogEntry(
            policy_id="top_n_equal_weight_v1",
            policy_definition_id="construction_policy_definition_top_n_equal_weight_v1",
            name="Top N Equal Weight v1",
            description="Select eligible top-ranked names and assign equal target weights.",
            selection_rule_ids=[ELIGIBLE_ONLY_RULE_ID, TAKE_TOP_N_RULE_ID],
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
            selection_rule_ids=[ELIGIBLE_ONLY_RULE_ID, TAKE_TOP_N_RULE_ID],
        ),
        max_position_failure_reason="inverse-rank seed exceeds max_position_weight",
        cutoff_exclusion_reason="not selected by top_n_inverse_rank_weight_v1 cutoff",
        raw_weight_numerator_builder=_inverse_rank_weight_numerators,
    ),
)

_POLICY_BY_ID: dict[str, ConstructionPolicyDefinition] = {
    definition.catalog_entry.policy_id: definition for definition in POLICY_CATALOG
}


def list_construction_policies() -> list[ConstructionPolicyCatalogEntry]:
    return [definition.catalog_entry.model_copy(deep=True) for definition in POLICY_CATALOG]


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
