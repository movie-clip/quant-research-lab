from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ConstructionRunStatus = Literal["feasible", "infeasible", "rejected"]
ConstructionConstraintStatus = Literal["pass", "binding", "fail", "not_evaluated"]
ConstructionPolicyId = Literal["top_n_equal_weight_v1", "top_n_inverse_rank_weight_v1"]
ConstructionArtifactSchemaVersion = Literal["construction_artifact_v1"]
ConstructionTradeAction = Literal["buy", "sell", "hold", "initiate", "exit"]
ConstructionSelectionRuleId = Literal["eligible_only", "take_top_n"]


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

    @field_validator("symbol", mode="before")
    @classmethod
    def _validate_symbol(cls, value: str) -> str:
        return _normalize_symbol(value)


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


class ConstructionPolicyInput(BaseModel):
    policy_id: ConstructionPolicyId = "top_n_equal_weight_v1"
    top_n: int = Field(ge=1)


class ConstructionHardConstraints(BaseModel):
    full_investment: Literal[True] = True
    long_only: Literal[True] = True
    eligible_ranked_universe_only: Literal[True] = True
    max_position_weight: float = Field(gt=0.0, le=1.0)


class ConstructionRunRequest(BaseModel):
    request_id: str | None = None
    ranked_universe: ConstructionRankedUniverseInput
    current_portfolio: ConstructionCurrentPortfolioInput
    policy: ConstructionPolicyInput
    hard_constraints: ConstructionHardConstraints


class ConstructionSelectedName(BaseModel):
    symbol: str
    rank: int = Field(ge=1)
    score: float | None = None


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

    ranked_universe_artifact_id: str | None = None
    ranking_id: str | None = None
    ranking_methodology_id: str | None = None
    ranking_as_of_date: str | None = None
    current_portfolio_artifact_id: str | None = None
    current_portfolio_as_of_timestamp: str | None = None
    policy_id: ConstructionPolicyId = "top_n_equal_weight_v1"
    top_n: int = Field(ge=1)
    max_position_weight: float = Field(gt=0.0, le=1.0)
    current_portfolio_weights: list[ConstructionWeight] = Field(default_factory=list)
    ranked_candidates: list[ConstructionRankedCandidateInput] = Field(default_factory=list)


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
    failure_reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_artifact_identifiers(self) -> "ConstructionArtifact":
        if not self.artifact_id.startswith("construction_artifact_"):
            raise ValueError("artifact_id must use the stable construction_artifact_ prefix")
        if len(self.fingerprint) != 64:
            raise ValueError("fingerprint must be a full sha256 hex digest")
        return self
