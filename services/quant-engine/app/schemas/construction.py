from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, field_validator, model_validator

from app.schemas.ranking import (
    ETF_RANKING_ARTIFACT_SCHEMA_VERSION,
    INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION,
)
from app.schemas.generic_ranking import (
    GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION,
)


ConstructionRunStatus = Literal["feasible", "infeasible", "rejected"]
ConstructionConstraintStatus = Literal["pass", "binding", "fail", "not_evaluated"]
ConstructionPolicyId = Literal[
    "top_n_equal_weight_v1",
    "top_n_inverse_rank_weight_v1",
    "top_n_linear_rank_weight_v1",
]
ConstructionPolicyDefinitionId = Literal[
    "construction_policy_definition_top_n_equal_weight_v1",
    "construction_policy_definition_top_n_inverse_rank_weight_v1",
    "construction_policy_definition_top_n_linear_rank_weight_v1",
]
ConstructionArtifactSchemaVersion = Literal["construction_artifact_v1"]
ConstructionTradeAction = Literal["buy", "sell", "hold", "initiate", "exit"]
ConstructionSelectionRuleId = Literal["eligible_only", "take_top_n"]
ConstructionPolicyFamily = Literal["top_n_equal_weight", "top_n_rank_weighted"]
ConstructionPolicyConstraints = Literal["long_only_fully_invested_max_position_turnover"]
ConstructionPolicyInputs = Literal["ranked_universe_and_current_portfolio"]
ConstructionPolicyDeterminism = Literal["deterministic_rank_order"]
ConstructionPolicyRankingSupport = Literal[
    "selection_only",
    "inverse_selected_order_weighting",
    "linear_selected_order_weighting",
]
ConstructionPolicyRequiredConstraintSupport = Literal["required"]
ConstructionPolicyOptionalConstraintSupport = Literal["supported_optional"]
ConstructionPolicyRequiredInputSupport = Literal["required"]
# ConstructionPolicyLaunchTopN is the top_n value carried inside a launch profile.
# Was Literal[2] when the launch boundary was a fixed pair comparison. Widened to a
# range [2, 20] to support configurable top_n at construction launch (Epic 3 breadth).
# Per-policy catalog entries still default to launch_top_n=2 for backward compatibility;
# users override at request time via ConstructionPolicyInput.top_n which is independent.
ConstructionPolicyLaunchTopN = Annotated[int, Field(ge=2, le=20)]
CONSTRUCTION_POLICY_LAUNCH_TOP_N_MIN = 2
CONSTRUCTION_POLICY_LAUNCH_TOP_N_MAX = 20
ConstructionPolicyLaunchProfileId = Literal["ranking_artifact_review_handoff_v1"]
ConstructionPolicyLaunchProfileKind = Literal["ranking_artifact_review_handoff"]
ConstructionPolicyLaunchProfilePolicyStatus = Literal["default", "opt_in", "excluded"]
ConstructionRankingArtifactPreflightContractVersion = Literal["construction_ranking_artifact_preflight_v1"]
ConstructionRankingArtifactHandoffKind = Literal[
    "etf_ranking_artifact_construction_handoff_v1",
    "intent_bound_etf_replacement_ranking_artifact_construction_handoff_v1",
    "generic_ranking_artifact_construction_handoff_v1",
]
ConstructionWeightingTraceVersion = Literal["weighting_trace_v1"]
ConstructionWeightingTraceStatus = Literal["available", "unavailable_legacy_artifact"]
ConstructionWeightingTraceSource = Literal["persisted_construction_artifact"]
ConstructionWeightingTraceTruth = Literal["artifact_backed_hypothetical_construction_diagnostics_only"]
ConstructionTurnoverDiagnosticsStatus = Literal["available", "unavailable_legacy_artifact"]
ConstructionTurnoverDiagnosticsVersion = Literal["construction_turnover_diagnostics_v1"]
ConstructionTurnoverDiagnosticsSource = Literal["persisted_construction_artifact"]
ConstructionTurnoverDiagnosticsTruth = Literal["artifact_backed_hypothetical_construction_diagnostics_only"]
ConstructionTurnoverMethodVersion = Literal["half_l1_weight_delta_union_v1"]
ConstructionTurnoverValueStatus = Literal["computed", "not_computed_no_generated_target_weights"]
ConstructionWeightingTraceStageId = Literal[
    "selected_order_to_raw_weight_numerator",
    "raw_weight_numerator_to_seed_weight",
    "seed_weight_to_target_weight",
]
ConstructionWeightingTraceMetricId = Literal[
    "selected_order",
    "raw_weight_numerator",
    "seed_weight",
    "target_weight",
]
ConstructionWeightingNormalizationMethod = Literal[
    "not_applicable",
    "single_position_force_to_one",
    "fractional_sum_division_with_last_position_reconciliation",
]
ConstructionWeightingArtifactBindingStatus = Literal[
    "final_target_weights_persisted",
    "generated_target_weights_not_persisted_due_to_infeasible_artifact",
]

_WEIGHTING_TRACE_STAGE_METRICS: dict[str, tuple[str, str]] = {
    "selected_order_to_raw_weight_numerator": ("selected_order", "raw_weight_numerator"),
    "raw_weight_numerator_to_seed_weight": ("raw_weight_numerator", "seed_weight"),
    "seed_weight_to_target_weight": ("seed_weight", "target_weight"),
}


def _normalize_symbol(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized:
        raise ValueError("symbol must not be empty")
    return normalized


class ConstructionWeight(BaseModel):
    symbol: str
    weight: float = Field(ge=0.0, le=1.0)

    @field_validator("symbol", mode="before")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        return _normalize_symbol(value)


class ConstructionRankedCandidateInput(BaseModel):
    symbol: str
    rank: int = Field(ge=1)
    eligible: bool = True
    score: float | None = None
    exclusion_reason: str | None = None
    sector: str | None = None

    @field_validator("symbol", mode="before")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        return _normalize_symbol(value)

    @field_validator("sector", mode="before")
    @classmethod
    def _validate_sector(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ConstructionRankedUniverseInput(BaseModel):
    artifact_id: str | None = None
    ranking_id: str
    methodology_id: str | None = None
    as_of_date: str | None = None
    ranked_candidates: list[ConstructionRankedCandidateInput] = Field(default_factory=list)


class ConstructionCurrentPortfolioInput(BaseModel):
    artifact_id: str | None = None
    as_of_timestamp: str | None = None
    weights: list[ConstructionWeight] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_identity_pairing(self) -> "ConstructionCurrentPortfolioInput":
        if (self.artifact_id is None) != (self.as_of_timestamp is None):
            raise ValueError(
                "current_portfolio.artifact_id and current_portfolio.as_of_timestamp must be provided together"
            )
        return self


class ConstructionPolicyInput(BaseModel):
    policy_id: ConstructionPolicyId = "top_n_equal_weight_v1"
    top_n: int = Field(ge=1)


class ConstructionPolicyCatalogEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    policy_id: ConstructionPolicyId
    policy_definition_id: ConstructionPolicyDefinitionId
    name: str
    description: str
    family: ConstructionPolicyFamily
    constraints: ConstructionPolicyConstraints
    inputs: ConstructionPolicyInputs
    determinism: ConstructionPolicyDeterminism
    ranking_support: ConstructionPolicyRankingSupport
    full_investment_constraint: ConstructionPolicyRequiredConstraintSupport
    long_only_constraint: ConstructionPolicyRequiredConstraintSupport
    eligible_ranked_universe_constraint: ConstructionPolicyRequiredConstraintSupport
    max_position_weight_constraint: ConstructionPolicyRequiredConstraintSupport
    min_position_weight_constraint: ConstructionPolicyOptionalConstraintSupport
    max_turnover_weight_constraint: ConstructionPolicyOptionalConstraintSupport
    max_trade_intent_count_constraint: ConstructionPolicyOptionalConstraintSupport
    max_sector_weight_constraint: ConstructionPolicyOptionalConstraintSupport
    ranked_universe_input: ConstructionPolicyRequiredInputSupport
    current_portfolio_input: ConstructionPolicyRequiredInputSupport
    launch_top_n: ConstructionPolicyLaunchTopN
    selection_rule_ids: list[ConstructionSelectionRuleId] = Field(default_factory=list)
    launch_profile: "ConstructionPolicyLaunchProfile"


class ConstructionPolicyLaunchProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: ConstructionPolicyLaunchProfileId
    profile_kind: ConstructionPolicyLaunchProfileKind
    policy_status: ConstructionPolicyLaunchProfilePolicyStatus
    launch_top_n: ConstructionPolicyLaunchTopN


class ConstructionHardConstraints(BaseModel):
    full_investment: Literal[True] = True
    long_only: Literal[True] = True
    eligible_ranked_universe_only: Literal[True] = True
    max_position_weight: float = Field(gt=0.0, le=1.0)
    min_position_weight: float | None = Field(default=None, gt=0.0, le=1.0)
    max_turnover_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    max_trade_intent_count: StrictInt | None = Field(default=None, ge=0)
    max_sector_weight: float | None = Field(default=None, gt=0.0, le=1.0)

    @model_validator(mode="after")
    def _validate_min_max_position_weight_consistency(self) -> "ConstructionHardConstraints":
        if (
            self.min_position_weight is not None
            and self.min_position_weight > self.max_position_weight
        ):
            raise ValueError("min_position_weight must be less than or equal to max_position_weight")
        if (
            self.max_sector_weight is not None
            and self.max_sector_weight < self.max_position_weight
        ):
            raise ValueError("max_sector_weight must be greater than or equal to max_position_weight")
        return self


class EtfRankingArtifactConstructionHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: Literal["etf_ranking_artifact_construction_handoff_v1"] = (
        "etf_ranking_artifact_construction_handoff_v1"
    )
    artifact_kind: str = "etf_ranking"
    artifact_id: str
    schema_version: str = ETF_RANKING_ARTIFACT_SCHEMA_VERSION
    ranking_id: str
    methodology_id: str
    as_of_date: str

    @model_validator(mode="after")
    def _validate_supported_contract(self) -> "EtfRankingArtifactConstructionHandoff":
        if self.artifact_kind != "etf_ranking":
            raise ValueError("unsupported ranking artifact kind")
        if self.schema_version != ETF_RANKING_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported etf ranking schema_version")
        return self


class IntentBoundEtfReplacementRankingArtifactConstructionHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: Literal[
        "intent_bound_etf_replacement_ranking_artifact_construction_handoff_v1"
    ] = "intent_bound_etf_replacement_ranking_artifact_construction_handoff_v1"
    artifact_kind: str = "intent_bound_etf_replacement_ranking"
    artifact_id: str
    schema_version: str = INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION
    ranking_id: str
    methodology_id: str
    as_of_date: str

    @model_validator(mode="after")
    def _validate_supported_contract(
        self,
    ) -> "IntentBoundEtfReplacementRankingArtifactConstructionHandoff":
        if self.artifact_kind != "intent_bound_etf_replacement_ranking":
            raise ValueError("unsupported ranking artifact kind")
        if self.schema_version != INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported replacement ranking schema_version")
        return self


class GenericRankingArtifactConstructionHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: Literal["generic_ranking_artifact_construction_handoff_v1"] = (
        "generic_ranking_artifact_construction_handoff_v1"
    )
    artifact_kind: str = "generic_ranking"
    artifact_id: str
    schema_version: str = GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION
    ranking_id: str
    methodology_id: str
    as_of_date: str

    @model_validator(mode="after")
    def _validate_supported_contract(self) -> "GenericRankingArtifactConstructionHandoff":
        if self.artifact_kind != "generic_ranking":
            raise ValueError("unsupported ranking artifact kind")
        if self.schema_version != GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported generic ranking schema_version")
        return self


ConstructionRankingArtifactHandoff = Annotated[
    EtfRankingArtifactConstructionHandoff
    | IntentBoundEtfReplacementRankingArtifactConstructionHandoff
    | GenericRankingArtifactConstructionHandoff,
    Field(discriminator="handoff_kind"),
]


class ConstructionRunRequest(BaseModel):
    request_id: str | None = None
    ranked_universe: ConstructionRankedUniverseInput | None = None
    ranking_artifact_handoff: ConstructionRankingArtifactHandoff | None = None
    current_portfolio: ConstructionCurrentPortfolioInput
    policy: ConstructionPolicyInput
    hard_constraints: ConstructionHardConstraints

    @model_validator(mode="before")
    @classmethod
    def _validate_handoff_request_shape(cls, value):
        if not isinstance(value, dict):
            return value
        handoff = value.get("ranking_artifact_handoff")
        if not isinstance(handoff, dict):
            return value
        if "handoff_kind" not in handoff:
            raise ValueError("ranking_artifact_handoff.handoff_kind is required")
        if handoff["handoff_kind"] not in {
            "etf_ranking_artifact_construction_handoff_v1",
            "intent_bound_etf_replacement_ranking_artifact_construction_handoff_v1",
            "generic_ranking_artifact_construction_handoff_v1",
        }:
            raise ValueError(
                f"unsupported ranking_artifact_handoff.handoff_kind: {handoff['handoff_kind']}"
            )
        return value

    @model_validator(mode="after")
    def _validate_exactly_one_ranking_input_source(self) -> "ConstructionRunRequest":
        has_inline_ranked_universe = self.ranked_universe is not None
        has_ranking_artifact_handoff = self.ranking_artifact_handoff is not None
        if has_inline_ranked_universe == has_ranking_artifact_handoff:
            raise ValueError(
                "construction run request must provide exactly one of ranked_universe or ranking_artifact_handoff"
            )
        if has_ranking_artifact_handoff:
            if not self.current_portfolio.artifact_id:
                raise ValueError(
                    "ranking artifact handoff requests require current_portfolio.artifact_id"
                )
            if not self.current_portfolio.as_of_timestamp:
                raise ValueError(
                    "ranking artifact handoff requests require current_portfolio.as_of_timestamp"
                )
        return self


class ConstructionRankingArtifactPreflightArtifact(BaseModel):
    artifact_kind: Literal["etf_ranking"] = "etf_ranking"
    artifact_id: str
    schema_version: Literal["etf_ranking_artifact_v1"] = ETF_RANKING_ARTIFACT_SCHEMA_VERSION
    ranking_id: str
    methodology_id: str
    as_of_date: str

    @model_validator(mode="after")
    def _validate_supported_contract(self) -> "ConstructionRankingArtifactPreflightArtifact":
        if self.artifact_kind != "etf_ranking":
            raise ValueError("unsupported ranking artifact kind")
        if self.schema_version != ETF_RANKING_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported etf ranking schema_version")
        return self


class IntentBoundEtfReplacementRankingConstructionPreflightArtifact(BaseModel):
    artifact_kind: Literal["intent_bound_etf_replacement_ranking"] = "intent_bound_etf_replacement_ranking"
    artifact_id: str
    schema_version: Literal["intent_bound_etf_replacement_ranking_artifact_v1"] = (
        INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION
    )
    ranking_id: str
    methodology_id: str
    as_of_date: str

    @model_validator(mode="after")
    def _validate_supported_contract(
        self,
    ) -> "IntentBoundEtfReplacementRankingConstructionPreflightArtifact":
        if self.artifact_kind != "intent_bound_etf_replacement_ranking":
            raise ValueError("unsupported ranking artifact kind")
        if self.schema_version != INTENT_BOUND_ETF_REPLACEMENT_RANKING_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported replacement ranking schema_version")
        return self


class GenericRankingConstructionPreflightArtifact(BaseModel):
    artifact_kind: Literal["generic_ranking"] = "generic_ranking"
    artifact_id: str
    schema_version: Literal["generic_ranking_artifact_v1"] = GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION
    ranking_id: str
    methodology_id: str
    as_of_date: str

    @model_validator(mode="after")
    def _validate_supported_contract(self) -> "GenericRankingConstructionPreflightArtifact":
        if self.artifact_kind != "generic_ranking":
            raise ValueError("unsupported ranking artifact kind")
        if self.schema_version != GENERIC_RANKING_ARTIFACT_SCHEMA_VERSION:
            raise ValueError("unsupported generic ranking schema_version")
        return self


ConstructionRankingArtifactPreflightArtifactUnion = Annotated[
    ConstructionRankingArtifactPreflightArtifact
    | IntentBoundEtfReplacementRankingConstructionPreflightArtifact
    | GenericRankingConstructionPreflightArtifact,
    Field(discriminator="artifact_kind"),
]


class ConstructionRankingArtifactPreflightResponse(BaseModel):
    contract_version: ConstructionRankingArtifactPreflightContractVersion = (
        "construction_ranking_artifact_preflight_v1"
    )
    artifact: ConstructionRankingArtifactPreflightArtifactUnion
    eligibility: "ConstructionRankingArtifactEligibility"
    handoff: ConstructionRankingArtifactHandoff | None = None

    @model_validator(mode="after")
    def _validate_alignment(self) -> "ConstructionRankingArtifactPreflightResponse":
        if self.eligibility.eligible and self.handoff is None:
            raise ValueError("handoff is required when eligibility.eligible=true")
        if not self.eligibility.eligible and self.handoff is not None:
            raise ValueError("handoff must be omitted when eligibility.eligible=false")
        if self.handoff is None:
            return self
        if self.handoff.artifact_kind != self.artifact.artifact_kind:
            raise ValueError("handoff.artifact_kind must match artifact.artifact_kind")
        if self.handoff.artifact_id != self.artifact.artifact_id:
            raise ValueError("handoff.artifact_id must match artifact.artifact_id")
        if self.handoff.schema_version != self.artifact.schema_version:
            raise ValueError("handoff.schema_version must match artifact.schema_version")
        if self.handoff.ranking_id != self.artifact.ranking_id:
            raise ValueError("handoff.ranking_id must match artifact.ranking_id")
        if self.handoff.methodology_id != self.artifact.methodology_id:
            raise ValueError("handoff.methodology_id must match artifact.methodology_id")
        if self.handoff.as_of_date != self.artifact.as_of_date:
            raise ValueError("handoff.as_of_date must match artifact.as_of_date")
        return self


class ConstructionRankingArtifactEligibility(BaseModel):
    eligible: bool
    reason: str | None = None

    @model_validator(mode="after")
    def _validate_reason_presence(self) -> "ConstructionRankingArtifactEligibility":
        if self.eligible and self.reason is not None:
            raise ValueError("eligibility.reason must be omitted when eligibility.eligible=true")
        if not self.eligible and not self.reason:
            raise ValueError("eligibility.reason is required when eligibility.eligible=false")
        return self


class ConstructionSelectedName(BaseModel):
    symbol: str
    rank: int = Field(ge=1)
    score: float | None = None
    sector: str | None = None


class ConstructionExcludedName(BaseModel):
    symbol: str
    rank: int = Field(ge=1)
    eligible: bool
    reason: str


class ConstructionConstraintEvaluation(BaseModel):
    constraint_id: Literal[
        "full_investment",
        "long_only",
        "eligible_ranked_universe_only",
        "max_position_weight",
        "min_position_weight",
        "max_turnover_weight",
        "max_trade_intent_count",
        "max_sector_weight",
    ]
    status: ConstructionConstraintStatus
    actual_value: float | None = None
    limit_value: float | None = None
    message: str


class ConstructionTradeIntent(BaseModel):
    symbol: str
    action: ConstructionTradeAction
    current_weight: float = Field(ge=0.0, le=1.0)
    target_weight: float = Field(ge=0.0, le=1.0)
    delta_weight: float = Field(ge=-1.0, le=1.0)


class ConstructionDeterministicOrdering(BaseModel):
    ranked_candidate_symbols: list[str] = Field(default_factory=list)
    selected_symbols: list[str] = Field(default_factory=list)
    trade_symbols: list[str] = Field(default_factory=list)


class ConstructionSelectionRuleTraceStep(BaseModel):
    rule_id: ConstructionSelectionRuleId
    rule_order: int = Field(ge=1)
    input_candidate_symbols: list[str] = Field(default_factory=list)
    output_candidate_symbols: list[str] = Field(default_factory=list)


class ConstructionSelectionRuleTrace(BaseModel):
    rule_ids: list[ConstructionSelectionRuleId]
    steps: list[ConstructionSelectionRuleTraceStep]

    @model_validator(mode="after")
    def _validate_trace_sequence(self) -> "ConstructionSelectionRuleTrace":
        if self.steps and not self.rule_ids:
            raise ValueError("selection_rule_trace.rule_ids must be non-empty when steps are present")
        if self.rule_ids and not self.steps:
            raise ValueError("selection_rule_trace.steps must be non-empty when rule_ids are present")
        if self.rule_ids and self.rule_ids != [step.rule_id for step in self.steps]:
            raise ValueError("selection_rule_trace.rule_ids must match step rule order")
        expected_orders = list(range(1, len(self.steps) + 1))
        if expected_orders and [step.rule_order for step in self.steps] != expected_orders:
            raise ValueError("selection_rule_trace.steps must use contiguous 1-based rule_order values")
        return self


class ConstructionNormalizedInputs(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ranked_universe_artifact_kind: str | None = None
    ranked_universe_artifact_id: str | None = None
    ranked_universe_artifact_schema_version: str | None = None
    ranking_id: str | None = None
    ranking_methodology_id: str | None = None
    ranking_as_of_date: str | None = None
    current_portfolio_artifact_id: str | None = None
    current_portfolio_as_of_timestamp: str | None = None
    policy_id: ConstructionPolicyId = "top_n_equal_weight_v1"
    policy_definition_id: ConstructionPolicyDefinitionId
    top_n: int = Field(ge=1)
    max_position_weight: float = Field(gt=0.0, le=1.0)
    min_position_weight: float | None = Field(default=None, gt=0.0, le=1.0)
    max_trade_intent_count: StrictInt | None = Field(default=None, ge=0)
    current_portfolio_weights: list[ConstructionWeight] = Field(default_factory=list)
    ranked_candidates: list[ConstructionRankedCandidateInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_min_max_position_weight_consistency(self) -> "ConstructionNormalizedInputs":
        if (
            self.min_position_weight is not None
            and self.min_position_weight > self.max_position_weight
        ):
            raise ValueError(
                "normalized_inputs.min_position_weight must be less than or equal to normalized_inputs.max_position_weight"
            )
        return self


class ConstructionWeightingTracePosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    rank: int = Field(ge=1)
    selected_order: int = Field(ge=1)
    input_value: float
    output_value: float

    @field_validator("symbol", mode="before")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        return _normalize_symbol(value)


class ConstructionWeightingTraceStage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage_id: ConstructionWeightingTraceStageId
    stage_order: int = Field(ge=1)
    input_metric_id: ConstructionWeightingTraceMetricId
    output_metric_id: ConstructionWeightingTraceMetricId
    positions: list[ConstructionWeightingTracePosition] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_stage_metrics(self) -> "ConstructionWeightingTraceStage":
        expected_input_metric_id, expected_output_metric_id = _WEIGHTING_TRACE_STAGE_METRICS[self.stage_id]
        if self.input_metric_id != expected_input_metric_id:
            raise ValueError(f"weighting_trace stage {self.stage_id} must use input_metric_id={expected_input_metric_id}")
        if self.output_metric_id != expected_output_metric_id:
            raise ValueError(f"weighting_trace stage {self.stage_id} must use output_metric_id={expected_output_metric_id}")
        expected_selected_orders = list(range(1, len(self.positions) + 1))
        if [position.selected_order for position in self.positions] != expected_selected_orders:
            raise ValueError("weighting_trace stage positions must use contiguous 1-based selected_order values")
        return self


class ConstructionWeightingTraceNormalization(BaseModel):
    model_config = ConfigDict(extra="forbid")

    normalization_source: Literal["raw_weight_numerator_to_seed_weight"] = "raw_weight_numerator_to_seed_weight"
    normalization_applied: bool
    input_metric_id: Literal["raw_weight_numerator"] = "raw_weight_numerator"
    output_metric_id: Literal["seed_weight"] = "seed_weight"
    raw_value_sum: float | None = Field(default=None, ge=0.0)
    normalized_value_sum: float | None = Field(default=None, ge=0.0)
    rounding_scale: int | None = Field(default=None, ge=0)
    normalization_method: ConstructionWeightingNormalizationMethod
    residual_reconciliation_symbol: str | None = None
    residual_reconciliation_delta: float | None = None

    @field_validator("residual_reconciliation_symbol", mode="before")
    @classmethod
    def _validate_residual_symbol(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_symbol(value)

    @model_validator(mode="after")
    def _validate_normalization_state(self) -> "ConstructionWeightingTraceNormalization":
        if not self.normalization_applied:
            if self.raw_value_sum is not None:
                raise ValueError("weighting_trace normalization raw_value_sum must be omitted when normalization_applied=false")
            if self.normalized_value_sum is not None:
                raise ValueError("weighting_trace normalization normalized_value_sum must be omitted when normalization_applied=false")
            if self.rounding_scale is not None:
                raise ValueError("weighting_trace normalization rounding_scale must be omitted when normalization_applied=false")
            if self.normalization_method != "not_applicable":
                raise ValueError("weighting_trace normalization_method must be not_applicable when normalization_applied=false")
            if self.residual_reconciliation_symbol is not None:
                raise ValueError("weighting_trace normalization residual_reconciliation_symbol must be omitted when normalization_applied=false")
            if self.residual_reconciliation_delta is not None:
                raise ValueError("weighting_trace normalization residual_reconciliation_delta must be omitted when normalization_applied=false")
            return self
        if self.raw_value_sum is None or self.raw_value_sum <= 0.0:
            raise ValueError("weighting_trace normalization raw_value_sum must be > 0 when normalization_applied=true")
        if self.normalized_value_sum is None or abs(self.normalized_value_sum - 1.0) > 1e-8:
            raise ValueError("weighting_trace normalization normalized_value_sum must equal 1.0 when normalization_applied=true")
        if self.rounding_scale != 8:
            raise ValueError("weighting_trace normalization rounding_scale must equal 8 when normalization_applied=true")
        if self.normalization_method == "not_applicable":
            raise ValueError("weighting_trace normalization_method must not be not_applicable when normalization_applied=true")
        if self.residual_reconciliation_symbol is None:
            raise ValueError("weighting_trace normalization residual_reconciliation_symbol is required when normalization_applied=true")
        if self.residual_reconciliation_delta is None:
            raise ValueError("weighting_trace normalization residual_reconciliation_delta is required when normalization_applied=true")
        return self


class ConstructionWeightingTraceArtifactBinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    binding_status: ConstructionWeightingArtifactBindingStatus
    final_target_weights_present: bool

    @model_validator(mode="after")
    def _validate_binding(self) -> "ConstructionWeightingTraceArtifactBinding":
        if self.binding_status == "final_target_weights_persisted" and not self.final_target_weights_present:
            raise ValueError("weighting_trace artifact binding requires final_target_weights_present=true when binding_status=final_target_weights_persisted")
        if (
            self.binding_status == "generated_target_weights_not_persisted_due_to_infeasible_artifact"
            and self.final_target_weights_present
        ):
            raise ValueError("weighting_trace artifact binding requires final_target_weights_present=false when binding_status=generated_target_weights_not_persisted_due_to_infeasible_artifact")
        return self


class ConstructionWeightingTraceV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_version: ConstructionWeightingTraceVersion = "weighting_trace_v1"
    source: ConstructionWeightingTraceSource = "persisted_construction_artifact"
    diagnostic_truth: ConstructionWeightingTraceTruth = "artifact_backed_hypothetical_construction_diagnostics_only"
    policy_id: ConstructionPolicyId
    policy_definition_id: ConstructionPolicyDefinitionId
    stages: list[ConstructionWeightingTraceStage]
    normalization: ConstructionWeightingTraceNormalization
    artifact_binding: ConstructionWeightingTraceArtifactBinding

    @model_validator(mode="after")
    def _validate_trace(self) -> "ConstructionWeightingTraceV1":
        expected_stage_ids = list(_WEIGHTING_TRACE_STAGE_METRICS)
        if [stage.stage_id for stage in self.stages] != expected_stage_ids:
            raise ValueError("weighting_trace stages must use the canonical stage sequence")
        if [stage.stage_order for stage in self.stages] != [1, 2, 3]:
            raise ValueError("weighting_trace stages must use contiguous 1-based stage_order values")

        stage_positions = [stage.positions for stage in self.stages]
        base_positions = stage_positions[0]
        if any(len(positions) != len(base_positions) for positions in stage_positions[1:]):
            raise ValueError("weighting_trace stages must carry the same position count")
        if not base_positions:
            if self.normalization.normalization_applied:
                raise ValueError("weighting_trace normalization must be unavailable when no weighted positions are present")
            return self
        if not self.normalization.normalization_applied:
            raise ValueError("weighting_trace normalization must be applied when weighted positions are present")

        base_identity = [(position.symbol, position.rank, position.selected_order) for position in base_positions]
        for positions in stage_positions[1:]:
            if [(position.symbol, position.rank, position.selected_order) for position in positions] != base_identity:
                raise ValueError("weighting_trace stages must carry the same ordered positions")

        first_stage, second_stage, third_stage = self.stages
        for position in first_stage.positions:
            if abs(position.input_value - float(position.selected_order)) > 1e-8:
                raise ValueError("weighting_trace selected_order stage input_value must equal selected_order")
        for upstream, downstream in zip(first_stage.positions, second_stage.positions, strict=True):
            if abs(upstream.output_value - downstream.input_value) > 1e-8:
                raise ValueError("weighting_trace raw_weight_numerator stage outputs must match seed_weight stage inputs")
        for upstream, downstream in zip(second_stage.positions, third_stage.positions, strict=True):
            if abs(upstream.output_value - downstream.input_value) > 1e-8:
                raise ValueError("weighting_trace seed_weight stage outputs must match target_weight stage inputs")
        return self


class ConstructionTurnoverDiagnosticsInclusionFlags(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uses_current_and_target_weight_union: Literal[True] = True
    includes_initiations: Literal[True] = True
    includes_exits: Literal[True] = True
    includes_zero_delta_positions_in_trade_intent_context: Literal[True] = True
    excludes_zero_delta_positions_from_reported_turnover_sum: Literal[True] = True


class ConstructionTurnoverTradeIntentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_field: Literal["trade_intents"] = "trade_intents"
    intent_count: int = Field(ge=0)


class ConstructionTurnoverFeasibilityContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_status: ConstructionRunStatus
    failure_reasons_field: Literal["failure_reasons"] = "failure_reasons"
    turnover_failure_reason_present: bool


class ConstructionTurnoverConstraintContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constraint_id: Literal["max_turnover_weight"] = "max_turnover_weight"
    requested: bool
    limit_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    evaluation_status: ConstructionConstraintStatus

    @model_validator(mode="after")
    def _validate_constraint_context(self) -> "ConstructionTurnoverConstraintContext":
        if self.requested and self.limit_weight is None:
            raise ValueError("turnover_diagnostics_v1 constraint_context.limit_weight is required when requested=true")
        if not self.requested and self.limit_weight is not None:
            raise ValueError("turnover_diagnostics_v1 constraint_context.limit_weight must be omitted when requested=false")
        if not self.requested and self.evaluation_status != "not_evaluated":
            raise ValueError(
                "turnover_diagnostics_v1 constraint_context.evaluation_status must be not_evaluated when requested=false"
            )
        return self


class ConstructionTurnoverSymbolContribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str
    action: ConstructionTradeAction
    current_weight: float = Field(ge=0.0, le=1.0)
    target_weight: float = Field(ge=0.0, le=1.0)
    delta_weight: float = Field(ge=-1.0, le=1.0)
    absolute_delta_weight: float = Field(ge=0.0, le=1.0)
    turnover_contribution_weight: float = Field(ge=0.0, le=1.0)
    contribution_fraction_of_reported_turnover: float | None = Field(default=None, ge=0.0, le=1.0)
    included_in_reported_turnover: bool

    @field_validator("symbol", mode="before")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        return _normalize_symbol(value)

    @model_validator(mode="after")
    def _validate_symbol_contribution(self) -> "ConstructionTurnoverSymbolContribution":
        expected_delta_weight = round(self.target_weight - self.current_weight, 8)
        if abs(self.delta_weight - expected_delta_weight) > 1e-8:
            raise ValueError(
                "turnover symbol contribution delta_weight must equal target_weight - current_weight"
            )
        expected_absolute_delta_weight = round(abs(self.delta_weight), 8)
        if abs(self.absolute_delta_weight - expected_absolute_delta_weight) > 1e-8:
            raise ValueError(
                "turnover symbol contribution absolute_delta_weight must equal abs(delta_weight)"
            )
        expected_action = resolve_construction_trade_action(
            self.current_weight,
            self.target_weight,
            self.delta_weight,
        )
        if self.action != expected_action:
            raise ValueError(
                "turnover symbol contribution action must match the canonical construction trade action"
            )
        expected_inclusion = self.absolute_delta_weight > 1e-8
        if self.included_in_reported_turnover != expected_inclusion:
            raise ValueError(
                "turnover symbol contribution included_in_reported_turnover must match non-zero absolute_delta_weight"
            )
        if not self.included_in_reported_turnover and abs(self.turnover_contribution_weight) > 1e-8:
            raise ValueError(
                "turnover symbol contribution turnover_contribution_weight must be zero when included_in_reported_turnover=false"
            )
        return self


def resolve_construction_trade_action(
    current_weight: float,
    target_weight: float,
    delta_weight: float,
) -> ConstructionTradeAction:
    if abs(delta_weight) <= 1e-8:
        return "hold"
    if current_weight <= 1e-8 and target_weight > 1e-8:
        return "initiate"
    if target_weight <= 1e-8 and current_weight > 1e-8:
        return "exit"
    if delta_weight > 0:
        return "buy"
    return "sell"


def calculate_construction_turnover(
    current_weights: list[ConstructionWeight],
    target_weights: list[ConstructionWeight],
) -> float:
    current_by_symbol = {item.symbol: item.weight for item in current_weights}
    target_by_symbol = {item.symbol: item.weight for item in target_weights}
    symbols = set(current_by_symbol) | set(target_by_symbol)
    return round(
        0.5
        * sum(
            abs(target_by_symbol.get(symbol, 0.0) - current_by_symbol.get(symbol, 0.0))
            for symbol in symbols
        ),
        8,
    )


def build_construction_turnover_symbol_contributions(
    current_weights: list[ConstructionWeight],
    target_weights: list[ConstructionWeight],
) -> list[ConstructionTurnoverSymbolContribution]:
    current_by_symbol = {item.symbol: item.weight for item in current_weights}
    target_by_symbol = {item.symbol: item.weight for item in target_weights}
    symbols = sorted(set(current_by_symbol) | set(target_by_symbol))
    if not symbols:
        return []

    rows: list[dict[str, object]] = []
    included_indexes: list[int] = []
    raw_contributions: list[float] = []
    for symbol in symbols:
        current_weight = current_by_symbol.get(symbol, 0.0)
        target_weight = target_by_symbol.get(symbol, 0.0)
        delta_weight = round(target_weight - current_weight, 8)
        absolute_delta_weight = round(abs(delta_weight), 8)
        included = absolute_delta_weight > 1e-8
        rows.append(
            {
                "symbol": symbol,
                "action": resolve_construction_trade_action(current_weight, target_weight, delta_weight),
                "current_weight": current_weight,
                "target_weight": target_weight,
                "delta_weight": delta_weight,
                "absolute_delta_weight": absolute_delta_weight,
                "turnover_contribution_weight": 0.0,
                "contribution_fraction_of_reported_turnover": None,
                "included_in_reported_turnover": included,
            }
        )
        raw_contributions.append(0.5 * absolute_delta_weight if included else 0.0)
        if included:
            included_indexes.append(len(rows) - 1)

    reported_turnover_weight = calculate_construction_turnover(current_weights, target_weights)
    running_contribution_weight = 0.0
    for contribution_order, row_index in enumerate(included_indexes, start=1):
        if contribution_order == len(included_indexes):
            contribution_weight = round(reported_turnover_weight - running_contribution_weight, 8)
        else:
            contribution_weight = round(raw_contributions[row_index], 8)
            running_contribution_weight = round(running_contribution_weight + contribution_weight, 8)
        rows[row_index]["turnover_contribution_weight"] = contribution_weight

    if reported_turnover_weight > 1e-8:
        running_fraction = 0.0
        for contribution_order, row_index in enumerate(included_indexes, start=1):
            contribution_weight = rows[row_index]["turnover_contribution_weight"]
            assert isinstance(contribution_weight, float)
            if contribution_order == len(included_indexes):
                contribution_fraction = round(1.0 - running_fraction, 8)
            else:
                contribution_fraction = round(contribution_weight / reported_turnover_weight, 8)
                running_fraction = round(running_fraction + contribution_fraction, 8)
            rows[row_index]["contribution_fraction_of_reported_turnover"] = contribution_fraction
        for row in rows:
            if not row["included_in_reported_turnover"]:
                row["contribution_fraction_of_reported_turnover"] = 0.0

    return [ConstructionTurnoverSymbolContribution.model_validate(row) for row in rows]


class ConstructionTurnoverDiagnosticsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    diagnostics_version: ConstructionTurnoverDiagnosticsVersion = "construction_turnover_diagnostics_v1"
    source: ConstructionTurnoverDiagnosticsSource = "persisted_construction_artifact"
    diagnostic_truth: ConstructionTurnoverDiagnosticsTruth = "artifact_backed_hypothetical_construction_diagnostics_only"
    turnover_basis_method_version: ConstructionTurnoverMethodVersion = "half_l1_weight_delta_union_v1"
    reported_value_status: ConstructionTurnoverValueStatus
    reported_turnover_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    inclusion_flags: ConstructionTurnoverDiagnosticsInclusionFlags
    trade_intent_context: ConstructionTurnoverTradeIntentContext
    feasibility_context: ConstructionTurnoverFeasibilityContext
    constraint_context: ConstructionTurnoverConstraintContext
    symbol_contributions: list[ConstructionTurnoverSymbolContribution] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_turnover_value_presence(self) -> "ConstructionTurnoverDiagnosticsV1":
        if self.reported_value_status == "computed" and self.reported_turnover_weight is None:
            raise ValueError("turnover_diagnostics_v1.reported_turnover_weight is required when reported_value_status=computed")
        if (
            self.reported_value_status == "not_computed_no_generated_target_weights"
            and self.reported_turnover_weight is not None
        ):
            raise ValueError(
                "turnover_diagnostics_v1.reported_turnover_weight must be omitted when reported_value_status=not_computed_no_generated_target_weights"
            )
        if self.reported_value_status == "not_computed_no_generated_target_weights" and self.symbol_contributions:
            raise ValueError(
                "turnover_diagnostics_v1.symbol_contributions must be empty when reported_value_status=not_computed_no_generated_target_weights"
            )
        if not self.symbol_contributions:
            return self

        expected_order = sorted(item.symbol for item in self.symbol_contributions)
        if [item.symbol for item in self.symbol_contributions] != expected_order:
            raise ValueError(
                "turnover_diagnostics_v1.symbol_contributions must be ordered by symbol ascending"
            )

        reported_turnover_weight = self.reported_turnover_weight or 0.0
        if (
            abs(
                sum(item.turnover_contribution_weight for item in self.symbol_contributions)
                - reported_turnover_weight
            )
            > 1e-8
        ):
            raise ValueError(
                "turnover_diagnostics_v1.symbol_contributions must reconcile to reported_turnover_weight"
            )
        return self


class ConstructionArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: ConstructionArtifactSchemaVersion = "construction_artifact_v1"
    artifact_id: str
    fingerprint: str
    status: ConstructionRunStatus
    request_id: str | None = None
    policy: ConstructionPolicyInput
    hard_constraints: ConstructionHardConstraints
    normalized_inputs: ConstructionNormalizedInputs
    selected_names: list[ConstructionSelectedName] = Field(default_factory=list)
    excluded_names: list[ConstructionExcludedName] = Field(default_factory=list)
    seed_weights: list[ConstructionWeight] = Field(default_factory=list)
    final_target_weights: list[ConstructionWeight] = Field(default_factory=list)
    trade_intents: list[ConstructionTradeIntent] = Field(default_factory=list)
    constraint_evaluations: list[ConstructionConstraintEvaluation] = Field(default_factory=list)
    deterministic_ordering: ConstructionDeterministicOrdering = Field(default_factory=ConstructionDeterministicOrdering)
    selection_rule_trace: ConstructionSelectionRuleTrace
    turnover_diagnostics_status: ConstructionTurnoverDiagnosticsStatus
    turnover_diagnostics_v1: ConstructionTurnoverDiagnosticsV1 | None
    weighting_trace_status: ConstructionWeightingTraceStatus
    weighting_trace_v1: ConstructionWeightingTraceV1 | None
    failure_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_artifact_identifiers(self) -> "ConstructionArtifact":
        if not self.artifact_id.startswith("construction_artifact_"):
            raise ValueError("artifact_id must use the stable construction_artifact_ prefix")
        if len(self.fingerprint) != 64:
            raise ValueError("fingerprint must be a full sha256 hex digest")
        if self.normalized_inputs.policy_id != self.policy.policy_id:
            raise ValueError("normalized_inputs.policy_id must match policy.policy_id")
        if self.hard_constraints.min_position_weight != self.normalized_inputs.min_position_weight:
            raise ValueError(
                "normalized_inputs.min_position_weight must match hard_constraints.min_position_weight"
            )
        if self.hard_constraints.max_trade_intent_count != self.normalized_inputs.max_trade_intent_count:
            raise ValueError(
                "normalized_inputs.max_trade_intent_count must match hard_constraints.max_trade_intent_count"
            )
        min_position_constraint = next(
            item for item in self.constraint_evaluations if item.constraint_id == "min_position_weight"
        )
        max_trade_intent_count_constraint = next(
            item for item in self.constraint_evaluations if item.constraint_id == "max_trade_intent_count"
        )
        if min_position_constraint.limit_value != self.hard_constraints.min_position_weight:
            raise ValueError(
                "min_position_weight constraint evaluation limit_value must match hard_constraints.min_position_weight"
            )
        if self.hard_constraints.min_position_weight is None and min_position_constraint.status != "not_evaluated":
            raise ValueError(
                "min_position_weight constraint evaluation must be not_evaluated when hard_constraints.min_position_weight is omitted"
            )
        if self.hard_constraints.min_position_weight is not None:
            min_position_actual_weights = self.final_target_weights
            if not min_position_actual_weights and self.weighting_trace_v1 is not None:
                min_position_actual_weights = [
                    ConstructionWeight(symbol=position.symbol, weight=round(position.output_value, 8))
                    for position in self.weighting_trace_v1.stages[2].positions
                ]
            if min_position_actual_weights:
                min_weight = min(item.weight for item in min_position_actual_weights)
                expected_status: ConstructionConstraintStatus = (
                    "fail"
                    if min_weight + 1e-8 < self.hard_constraints.min_position_weight
                    else (
                        "binding"
                        if abs(min_weight - self.hard_constraints.min_position_weight) <= 1e-6
                        else "pass"
                    )
                )
                if min_position_constraint.actual_value != min_weight:
                    raise ValueError(
                        "min_position_weight constraint evaluation actual_value must match persisted artifact weights"
                    )
                if min_position_constraint.status != expected_status:
                    raise ValueError(
                        "min_position_weight constraint evaluation status must match persisted artifact weights"
                    )
        trade_intent_count_evaluation_available = (
            self.status == "feasible"
            or "trade intent count exceeds max_trade_intent_count" in self.failure_reasons
        )
        if max_trade_intent_count_constraint.limit_value != self.hard_constraints.max_trade_intent_count:
            raise ValueError(
                "max_trade_intent_count constraint evaluation limit_value must match hard_constraints.max_trade_intent_count"
            )
        if self.hard_constraints.max_trade_intent_count is None:
            if max_trade_intent_count_constraint.status != "not_evaluated":
                raise ValueError(
                    "max_trade_intent_count constraint evaluation must be not_evaluated when hard_constraints.max_trade_intent_count is omitted"
                )
            if max_trade_intent_count_constraint.actual_value is not None:
                raise ValueError(
                    "max_trade_intent_count constraint evaluation actual_value must be omitted when hard_constraints.max_trade_intent_count is omitted"
                )
        elif not trade_intent_count_evaluation_available:
            if max_trade_intent_count_constraint.status != "not_evaluated":
                raise ValueError(
                    "max_trade_intent_count constraint evaluation must be not_evaluated when canonical trade intents were not persisted"
                )
            if max_trade_intent_count_constraint.actual_value is not None:
                raise ValueError(
                    "max_trade_intent_count constraint evaluation actual_value must be omitted when canonical trade intents were not persisted"
                )
        else:
            canonical_trade_intent_count = len(self.trade_intents)
            expected_status = (
                "fail"
                if canonical_trade_intent_count > self.hard_constraints.max_trade_intent_count
                else (
                    "binding"
                    if canonical_trade_intent_count == self.hard_constraints.max_trade_intent_count
                    else "pass"
                )
            )
            if max_trade_intent_count_constraint.actual_value != canonical_trade_intent_count:
                raise ValueError(
                    "max_trade_intent_count constraint evaluation actual_value must match trade_intents length"
                )
            if max_trade_intent_count_constraint.status != expected_status:
                raise ValueError(
                    "max_trade_intent_count constraint evaluation status must match trade_intents length"
                )
            trade_intent_failure_reason_present = (
                "trade intent count exceeds max_trade_intent_count" in self.failure_reasons
            )
            if expected_status == "fail" and not trade_intent_failure_reason_present:
                raise ValueError(
                    "max_trade_intent_count failure reason must be present when the constraint evaluation fails"
                )
            if expected_status != "fail" and trade_intent_failure_reason_present:
                raise ValueError(
                    "max_trade_intent_count failure reason must be absent when the constraint evaluation does not fail"
                )
        max_sector_weight_constraint = next(
            (item for item in self.constraint_evaluations if item.constraint_id == "max_sector_weight"),
            None,
        )
        if max_sector_weight_constraint is not None:
            if max_sector_weight_constraint.limit_value != self.hard_constraints.max_sector_weight:
                raise ValueError(
                    "max_sector_weight constraint evaluation limit_value must match hard_constraints.max_sector_weight"
                )
            sector_failure_reason_present = (
                "selected sector weight exceeds max_sector_weight" in self.failure_reasons
            )
            if self.hard_constraints.max_sector_weight is None:
                if max_sector_weight_constraint.status != "not_evaluated":
                    raise ValueError(
                        "max_sector_weight constraint evaluation must be not_evaluated when hard_constraints.max_sector_weight is omitted"
                    )
                if max_sector_weight_constraint.actual_value is not None:
                    raise ValueError(
                        "max_sector_weight constraint evaluation actual_value must be omitted when hard_constraints.max_sector_weight is omitted"
                    )
                if sector_failure_reason_present:
                    raise ValueError(
                        "max_sector_weight failure reason must be absent when hard_constraints.max_sector_weight is omitted"
                    )
            else:
                if (max_sector_weight_constraint.status == "fail") != sector_failure_reason_present:
                    raise ValueError(
                        "max_sector_weight failure reason must be present exactly when the constraint evaluation fails"
                    )
                if sector_failure_reason_present and self.status == "feasible":
                    raise ValueError(
                        "a feasible construction artifact must not carry the max_sector_weight failure reason"
                    )
        if self.turnover_diagnostics_status == "available" and self.turnover_diagnostics_v1 is None:
            raise ValueError("turnover_diagnostics_v1 is required when turnover_diagnostics_status=available")
        if self.turnover_diagnostics_status == "unavailable_legacy_artifact" and self.turnover_diagnostics_v1 is not None:
            raise ValueError("turnover_diagnostics_v1 must be omitted when turnover_diagnostics_status=unavailable_legacy_artifact")
        if self.turnover_diagnostics_v1 is not None:
            turnover_constraint = next(
                item for item in self.constraint_evaluations if item.constraint_id == "max_turnover_weight"
            )
            requested = self.hard_constraints.max_turnover_weight is not None
            if self.turnover_diagnostics_v1.constraint_context.requested != requested:
                raise ValueError(
                    "turnover_diagnostics_v1 constraint_context.requested must match hard_constraints.max_turnover_weight presence"
                )
            if self.turnover_diagnostics_v1.constraint_context.limit_weight != self.hard_constraints.max_turnover_weight:
                raise ValueError(
                    "turnover_diagnostics_v1 constraint_context.limit_weight must match hard_constraints.max_turnover_weight"
                )
            if self.turnover_diagnostics_v1.constraint_context.evaluation_status != turnover_constraint.status:
                raise ValueError(
                    "turnover_diagnostics_v1 constraint_context.evaluation_status must match max_turnover_weight constraint evaluation status"
                )
            if self.turnover_diagnostics_v1.trade_intent_context.intent_count != len(self.trade_intents):
                raise ValueError(
                    "turnover_diagnostics_v1 trade_intent_context.intent_count must match trade_intents length"
                )
            if self.turnover_diagnostics_v1.feasibility_context.artifact_status != self.status:
                raise ValueError(
                    "turnover_diagnostics_v1 feasibility_context.artifact_status must match artifact status"
                )
            if self.turnover_diagnostics_v1.feasibility_context.turnover_failure_reason_present != (
                "target turnover exceeds max_turnover_weight" in self.failure_reasons
            ):
                raise ValueError(
                    "turnover_diagnostics_v1 feasibility_context.turnover_failure_reason_present must match failure_reasons"
                )
        if self.weighting_trace_status == "available" and self.weighting_trace_v1 is None:
            raise ValueError("weighting_trace_v1 is required when weighting_trace_status=available")
        if self.weighting_trace_status == "unavailable_legacy_artifact" and self.weighting_trace_v1 is not None:
            raise ValueError("weighting_trace_v1 must be omitted when weighting_trace_status=unavailable_legacy_artifact")
        if self.weighting_trace_v1 is None:
            return self
        if self.weighting_trace_v1.policy_id != self.policy.policy_id:
            raise ValueError("weighting_trace_v1.policy_id must match policy.policy_id")
        if self.weighting_trace_v1.policy_definition_id != self.normalized_inputs.policy_definition_id:
            raise ValueError("weighting_trace_v1.policy_definition_id must match normalized_inputs.policy_definition_id")
        trace_positions = self.weighting_trace_v1.stages[0].positions
        if [(position.symbol, position.rank) for position in trace_positions] != [
            (item.symbol, item.rank) for item in self.selected_names
        ]:
            raise ValueError("weighting_trace_v1 positions must match selected_names")
        if self.weighting_trace_v1.artifact_binding.final_target_weights_present != bool(self.final_target_weights):
            raise ValueError("weighting_trace_v1 artifact binding must match final_target_weights presence")
        if self.status == "feasible":
            if self.weighting_trace_v1.artifact_binding.binding_status != "final_target_weights_persisted":
                raise ValueError("feasible construction artifacts must persist weighting_trace_v1 final_target_weights binding")
            if [
                {"symbol": position.symbol, "weight": round(position.output_value, 8)}
                for position in self.weighting_trace_v1.stages[1].positions
            ] != [item.model_dump(mode="json") for item in self.seed_weights]:
                raise ValueError("weighting_trace_v1 seed_weight stage outputs must match seed_weights")
            if [
                {"symbol": position.symbol, "weight": round(position.output_value, 8)}
                for position in self.weighting_trace_v1.stages[2].positions
            ] != [item.model_dump(mode="json") for item in self.final_target_weights]:
                raise ValueError("weighting_trace_v1 target_weight stage outputs must match final_target_weights")
        elif self.weighting_trace_v1.artifact_binding.binding_status != "generated_target_weights_not_persisted_due_to_infeasible_artifact":
            raise ValueError("infeasible or rejected construction artifacts must label weighting_trace_v1 as generated_target_weights_not_persisted_due_to_infeasible_artifact")
        return self
