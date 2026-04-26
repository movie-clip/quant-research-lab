from __future__ import annotations

from datetime import date, datetime
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, RootModel, field_validator, model_validator

from app.schemas.construction import (
    ConstructionPolicyDefinitionId,
    ConstructionSelectionRuleTrace,
    ConstructionHardConstraints,
    ConstructionTurnoverDiagnosticsStatus,
    ConstructionTurnoverDiagnosticsV1,
    ConstructionWeightingTraceStatus,
    ConstructionWeightingTraceV1,
)
from app.schemas.imports import ImportedPortfolioSnapshot, StatementImporter
from app.schemas.optimizer import OptimizerArtifactState, OptimizerBenchmarkAttestationType, OptimizerConstraintStatus, OptimizerObjective, OptimizerObjectiveId, OptimizerPersistedArtifactReference, OptimizerReturnBasisAttestation, OptimizerReturnBasisSectionTrust
from app.schemas.reconciliation import RiskContributionBreakdownPayload, SnapshotItem, StressScenarioResult, VolatilitySnapshot
from app.schemas.research import AllocationRebalanceFrequency, BacktestFrequency, ContinuousSeriesSpec, DistributionPolicy, InvestorEconomicsStatus, StrategyDefinition


class BacktestConfig(BaseModel):
    strategy: StrategyDefinition
    benchmark_symbol: str | None = None
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    base_currency: str = "USD"
    slippage_bps: float = 0.0
    commission_per_contract: float = 0.0
    rebalance_frequency: Literal["daily", "weekly", "monthly", "signal"] = "signal"
    use_continuous_contracts: bool = True
    continuous_series: ContinuousSeriesSpec | None = None


class BacktestRequest(BaseModel):
    strategy_id: str = "book_trend_breakout"
    universe: list[str] = Field(default_factory=lambda: ["ES", "NQ"])
    benchmark_symbol: str | None = None
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    base_currency: str = "USD"
    timeframe: BacktestFrequency = "1d"
    slippage_bps: float = 0.0
    commission_per_contract: float = 2.5
    use_continuous_contracts: bool = True


class BacktestTrade(BaseModel):
    date: str
    symbol: str
    action: Literal["buy", "sell", "short", "cover", "roll"]
    quantity: float
    price: float | None = None
    notional: float | None = None
    fee: float | None = None


class BacktestPosition(BaseModel):
    date: str
    symbol: str
    quantity: float
    market_price: float | None = None
    market_value: float | None = None
    notional_exposure: float | None = None


class BacktestEquityPoint(BaseModel):
    date: str
    equity: float | None = None
    cash: float
    gross_exposure: float | None = None
    net_exposure: float | None = None
    drawdown_pct: float | None = None


class BacktestRun(BaseModel):
    run_id: str
    config: BacktestConfig
    dataset_info: dict[str, dict[str, str | bool]] = Field(default_factory=dict)
    investor_economics_status: InvestorEconomicsStatus
    trades: list[BacktestTrade] = Field(default_factory=list)
    positions: list[BacktestPosition] = Field(default_factory=list)
    equity_curve: list[BacktestEquityPoint] = Field(default_factory=list)
    total_return_pct: float | None = None
    annualized_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_ratio: float | None = None


class StrategyAllocation(BaseModel):
    sleeve_id: str
    name: str
    capital_weight: float
    source: Literal["imported_portfolio", "strategy_run"]
    strategy_run_id: str | None = None


class OverlayRun(BaseModel):
    overlay_id: str
    base_portfolio_name: str
    allocations: list[StrategyAllocation] = Field(default_factory=list)
    equity_curve: list[BacktestEquityPoint] = Field(default_factory=list)
    notes: str | None = None


AllocationBacktestStatus = Literal["ok", "degraded", "rejected"]


class PortfolioWeightInput(BaseModel):
    symbol: str
    target_weight: float


class DraftPortfolioImportedMetaInput(BaseModel):
    importer: StatementImporter | None = None
    statement_period: str | None = None
    imported_at: datetime | None = None
    source_file_names: list[str] = Field(default_factory=list)


class DraftPortfolioPositionInput(BaseModel):
    symbol: str
    market_value: float
    quantity: float | None = None
    currency: str | None = None
    sector: str | None = None
    name: str | None = None
    source_type: Literal["equity", "etf", "cash_equivalent", "other"] | None = None


class DraftPortfolioCashBalanceInput(BaseModel):
    currency: str
    amount: float


class DraftPortfolioSnapshotInput(BaseModel):
    snapshot_version: int = 1
    base_currency: str | None = None
    imported_meta: DraftPortfolioImportedMetaInput
    positions: list[DraftPortfolioPositionInput] = Field(default_factory=list)
    cash_balances: list[DraftPortfolioCashBalanceInput] = Field(default_factory=list)


class ReplacementIntentReplayInput(BaseModel):
    kind: Literal["etf_replacement_intent"]
    source: Literal["candidate_seed"]
    created_at: datetime | None = None
    draft_id: str
    workspace_id: str
    base_node_id: str
    base_symbol: str
    candidate_symbol: str
    seeded_from_draft_id: str
    seed_ranking_id: str
    seed_methodology_id: str
    seed_ranking_basis_date: str
    peer_group: str | None = None
    benchmark_symbol: str
    lookback_months: int
    confidence: Literal["high", "medium", "low"]
    holdings_support: Literal["sample", "mixed", "unavailable"]
    warning_count: int = 0


class PortfolioAllocationBacktestRequest(BaseModel):
    portfolio_name: str | None = None
    weights: list[PortfolioWeightInput] = Field(default_factory=list)
    reference_weights: list[PortfolioWeightInput] | None = None
    benchmark_symbol: str = "SPY"
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    rebalance_frequency: AllocationRebalanceFrequency = "monthly"
    base_currency: str = "USD"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    drift_tolerance_pct: float | None = None
    price_basis: Literal["adjusted_close"] = "adjusted_close"
    execution_price_field: Literal["close"] = "close"
    execution_lag_days: int = 1
    symbol_overrides: dict[str, list[str]] = Field(default_factory=dict)


class ConstructionArtifactReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    construction_artifact_id: str
    benchmark_symbol: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    initial_capital: float | None = None
    rebalance_frequency: AllocationRebalanceFrequency | None = None
    base_currency: str | None = None
    commission_bps: float | None = None
    slippage_bps: float | None = None
    drift_tolerance_pct: float | None = None
    price_basis: Literal["adjusted_close"] | None = None
    execution_price_field: Literal["close"] | None = None
    execution_lag_days: int | None = None
    symbol_overrides: dict[str, list[str]] | None = None


class ConstructionArtifactReplayEffectiveParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_symbol: str = "SPY"
    start_date: date = date(2024, 1, 1)
    end_date: date = date(2024, 12, 31)
    initial_capital: float = 100_000.0
    rebalance_frequency: AllocationRebalanceFrequency = "monthly"
    base_currency: str = "USD"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    drift_tolerance_pct: float | None = None
    price_basis: Literal["adjusted_close"] = "adjusted_close"
    execution_price_field: Literal["close"] = "close"
    execution_lag_days: int = 1
    symbol_overrides: dict[str, list[str]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_effective_replay_params(self) -> "ConstructionArtifactReplayEffectiveParams":
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")
        if self.execution_lag_days < 1:
            raise ValueError("execution_lag_days must be at least 1")
        return self


class HypotheticalReplayProposal(BaseModel):
    source: Literal["draft_replacement_intent"]
    incumbent_symbol: str
    candidate_symbol: str
    draft_id: str
    base_node_id: str


class HypotheticalReplayDerivation(BaseModel):
    baseline_basis: Literal["draft_snapshot_positions_normalized"]
    candidate_construction_rule: Literal["same_weight_substitution_v1", "fixed_split_50_50_substitution_v2"]


class HypotheticalReplayUpstreamIds(BaseModel):
    draft_id: str
    workspace_id: str
    base_node_id: str


class HypotheticalReplayProvenance(BaseModel):
    class ConstraintValidationLineage(BaseModel):
        supplied: bool
        validation_status: Literal["ok", "blocked", "rejected"] | None = None
        constraint_set_id: Literal["single_replacement_construction_constraints_v1"] | None = None

    candidate_input_source: Literal["replacement_intent_preview", "constructed_candidate_payload"]
    construction_rule_id: Literal["same_weight_substitution_v1", "fixed_split_50_50_substitution_v2"]
    upstream_ids: HypotheticalReplayUpstreamIds
    seed_ranking_id: str
    seed_methodology_id: str
    constraint_validation: ConstraintValidationLineage


class ConstructedCandidateReplayInput(BaseModel):
    construction: CandidateConstructionState
    proposal: CandidateFormationProposal
    inputs: CandidateConstructionInputs
    outputs: CandidateConstructionOutputs
    derivation: CandidateConstructionDerivation
    truth_provenance: CandidateConstructionTruthProvenance
    warnings: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None


class HypotheticalReplacementReplayRequest(BaseModel):
    snapshot: DraftPortfolioSnapshotInput
    replacement_intent: ReplacementIntentReplayInput | None = None
    constructed_candidate: ConstructedCandidateReplayInput | None = None
    constraint_validation: SingleReplacementConstructionConstraintValidationResponse | None = None
    benchmark_symbol: str = "SPY"
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    rebalance_frequency: AllocationRebalanceFrequency = "monthly"
    base_currency: str = "USD"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    drift_tolerance_pct: float | None = None
    price_basis: Literal["adjusted_close"] = "adjusted_close"
    execution_price_field: Literal["close"] = "close"
    execution_lag_days: int = 1
    symbol_overrides: dict[str, list[str]] = Field(default_factory=dict)


class AllocationBacktestAssumptions(BaseModel):
    price_basis: str
    execution_price_field: str
    execution_lag_days: int
    calendar_policy: str
    fractional_shares: bool
    long_only: bool
    leverage_allowed: bool
    tax_treatment: str
    investor_base_currency: str | None = None


class AllocationBacktestInstrumentMeta(BaseModel):
    symbol: str
    trading_currency: str | None = None
    instrument_base_currency: str | None = None
    currency_hedged: bool | None = None
    distribution_policy: DistributionPolicy = "unknown"


class AllocationBacktestWeight(BaseModel):
    symbol: str
    target_weight: float


class AllocationBacktestTrade(BaseModel):
    date: str
    symbol: str
    action: Literal["buy", "sell"]
    quantity: float
    price: float | None = None
    traded_notional: float | None = None
    commission_cost: float | None = None
    slippage_cost: float | None = None
    total_cost: float | None = None


class AllocationBacktestRebalanceEvent(BaseModel):
    decision_date: str
    execution_date: str
    turnover_pct: float | None = None
    traded_notional: float | None = None
    total_cost: float | None = None


class AllocationBacktestPoint(BaseModel):
    date: str
    equity: float
    cash: float
    gross_exposure: float | None = None
    drawdown_pct: float | None = None


class AllocationBacktestMetrics(BaseModel):
    total_return_pct: float | None = None
    annualized_return_pct: float | None = None
    annualized_volatility_pct: float | None = None
    downside_volatility_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    benchmark_return_pct: float | None = None
    excess_return_pct: float | None = None
    tracking_error_pct: float | None = None
    information_ratio: float | None = None
    beta_vs_benchmark: float | None = None
    correlation_vs_benchmark: float | None = None
    total_turnover_pct: float | None = None
    turnover_events_count: int = 0
    total_cost_paid: float | None = None


class AllocationBacktestResult(BaseModel):
    portfolio_name: str | None = None
    benchmark_symbol: str | None = None
    start_date: str
    end_date: str
    observation_count: int
    rebalance_frequency: AllocationRebalanceFrequency
    commission_bps: float
    slippage_bps: float
    drift_tolerance_pct: float | None = None
    assumptions: AllocationBacktestAssumptions
    status: AllocationBacktestStatus
    investor_economics_status: InvestorEconomicsStatus
    instrument_metadata: list[AllocationBacktestInstrumentMeta] = Field(default_factory=list)
    starting_weights: list[AllocationBacktestWeight] = Field(default_factory=list)
    ending_weights: list[AllocationBacktestWeight] = Field(default_factory=list)
    metrics: AllocationBacktestMetrics
    equity_curve: list[AllocationBacktestPoint] = Field(default_factory=list)
    rebalance_events: list[AllocationBacktestRebalanceEvent] = Field(default_factory=list)
    trades: list[AllocationBacktestTrade] = Field(default_factory=list)


class AllocationBacktestComparison(BaseModel):
    total_return_diff_pct: float | None = None
    annualized_return_diff_pct: float | None = None
    benchmark_return_diff_pct: float | None = None
    annualized_volatility_diff_pct: float | None = None
    downside_volatility_diff_pct: float | None = None
    max_drawdown_diff_pct: float | None = None
    sharpe_diff: float | None = None
    sortino_diff: float | None = None
    excess_return_diff_pct: float | None = None
    tracking_error_diff_pct: float | None = None
    information_ratio_diff: float | None = None
    beta_diff: float | None = None
    correlation_diff: float | None = None
    total_turnover_diff_pct: float | None = None
    total_cost_diff: float | None = None


class PortfolioDiagnosticsProvenance(BaseModel):
    snapshot_basis: Literal["synthetic_replay_snapshot"]
    historical_basis: Literal["market_data_history"]
    note: str


class PortfolioDiagnosticsSnapshot(BaseModel):
    provenance: PortfolioDiagnosticsProvenance
    factor_snapshot: list[SnapshotItem] = Field(default_factory=list)
    volatility_snapshot: VolatilitySnapshot | None = None
    risk_contribution: RiskContributionBreakdownPayload | None = None
    stress_scenarios: list[StressScenarioResult] = Field(default_factory=list)


class PortfolioDiagnosticsComparisonRow(BaseModel):
    key: str
    label: str
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta_value: float | None = None


class PortfolioDiagnosticsTopCallout(BaseModel):
    key: str
    label: str
    baseline_value: float | None = None
    candidate_value: float | None = None
    delta_value: float | None = None
    selection_rule: str
    rationale: str


class PortfolioImprovementComparison(BaseModel):
    factor_exposure_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    top_factor_exposure_change: PortfolioDiagnosticsTopCallout | None = None
    volatility_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    top_volatility_change: PortfolioDiagnosticsTopCallout | None = None
    risk_contribution_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    top_risk_contribution_change: PortfolioDiagnosticsTopCallout | None = None
    concentration_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    top_concentration_change: PortfolioDiagnosticsTopCallout | None = None
    stress_scenario_changes: list[PortfolioDiagnosticsComparisonRow] = Field(default_factory=list)
    top_stress_scenario_change: PortfolioDiagnosticsTopCallout | None = None


class PortfolioAllocationBacktestResponse(BaseModel):
    methodology: str
    investor_economics_status: InvestorEconomicsStatus
    reference_result: AllocationBacktestResult | None = None
    candidate_result: AllocationBacktestResult
    comparison: AllocationBacktestComparison | None = None
    reference_diagnostics: PortfolioDiagnosticsSnapshot | None = None
    candidate_diagnostics: PortfolioDiagnosticsSnapshot | None = None
    diagnostics_comparison: PortfolioImprovementComparison | None = None


class HypotheticalReplacementReplayResponse(BaseModel):
    proposal: HypotheticalReplayProposal
    derivation: HypotheticalReplayDerivation
    replay_provenance: HypotheticalReplayProvenance
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    replay: PortfolioAllocationBacktestResponse
    warnings: list[str] = Field(default_factory=list)


class ConstructionArtifactReplayTruthSeparation(BaseModel):
    baseline_truth: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    candidate_truth: Literal["hypothetical_construction_artifact"] = "hypothetical_construction_artifact"
    candidate_applied: Literal[False] = False
    consumption_mode: Literal["explicit_reference_only"] = "explicit_reference_only"


class ConstructionArtifactReplayProvenance(BaseModel):
    source: Literal["construction_artifact_reference"] = "construction_artifact_reference"
    construction_artifact_id: str
    policy_id: str
    policy_definition_id: ConstructionPolicyDefinitionId
    ranked_universe_artifact_id: str | None = None
    ranking_id: str | None = None
    ranking_methodology_id: str | None = None
    current_portfolio_artifact_id: str | None = None
    hard_constraints: ConstructionHardConstraints
    baseline_input_source: Literal["normalized_inputs.current_portfolio_weights"] = "normalized_inputs.current_portfolio_weights"
    candidate_input_source: Literal["final_target_weights"] = "final_target_weights"
    selection_rule_trace: ConstructionSelectionRuleTrace
    turnover_diagnostics_status: ConstructionTurnoverDiagnosticsStatus = "unavailable_legacy_artifact"
    turnover_diagnostics_v1: ConstructionTurnoverDiagnosticsV1 | None = None
    weighting_trace_status: ConstructionWeightingTraceStatus
    weighting_trace_v1: ConstructionWeightingTraceV1 | None

    @model_validator(mode="after")
    def _validate_turnover_diagnostics_contract(self) -> "ConstructionArtifactReplayProvenance":
        if self.turnover_diagnostics_status == "available" and self.turnover_diagnostics_v1 is None:
            raise ValueError("turnover_diagnostics_v1 is required when turnover_diagnostics_status=available")
        if self.turnover_diagnostics_status == "unavailable_legacy_artifact" and self.turnover_diagnostics_v1 is not None:
            raise ValueError("turnover_diagnostics_v1 must be omitted when turnover_diagnostics_status=unavailable_legacy_artifact")
        return self

    @model_validator(mode="after")
    def _validate_weighting_trace_contract(self) -> "ConstructionArtifactReplayProvenance":
        if self.weighting_trace_status == "available" and self.weighting_trace_v1 is None:
            raise ValueError("weighting_trace_v1 is required when weighting_trace_status=available")
        if self.weighting_trace_status == "unavailable_legacy_artifact" and self.weighting_trace_v1 is not None:
            raise ValueError("weighting_trace_v1 must be omitted when weighting_trace_status=unavailable_legacy_artifact")
        return self


class ConstructionArtifactReplayResponse(BaseModel):
    construction_artifact_id: str
    truth_separation: ConstructionArtifactReplayTruthSeparation = Field(default_factory=ConstructionArtifactReplayTruthSeparation)
    replay_provenance: ConstructionArtifactReplayProvenance
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    effective_replay_params: ConstructionArtifactReplayEffectiveParams
    replay: PortfolioAllocationBacktestResponse


class ConstructionArtifactPreviewHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: Literal["construction_artifact_preview_handoff_v1"] = "construction_artifact_preview_handoff_v1"
    construction_artifact_id: str
    effective_replay_params: ConstructionArtifactReplayEffectiveParams


class ConstructionArtifactReplayValidationResponse(BaseModel):
    construction_artifact_id: str
    effective_replay_params: ConstructionArtifactReplayEffectiveParams
    preview_handoff: ConstructionArtifactPreviewHandoff
    open_payload: ConstructionArtifactReplayResponse | None = Field(default=None, deprecated=True)


ConstructionArtifactPreviewRequest: TypeAlias = ConstructionArtifactPreviewHandoff | ConstructionArtifactReplayRequest


class ConstructionArtifactPreviewOpenRequest(RootModel[ConstructionArtifactPreviewRequest]):
    @model_validator(mode="before")
    @classmethod
    def _validate_preview_request_shape(cls, value):
        if not isinstance(value, dict):
            return value
        if "handoff_kind" not in value and "effective_replay_params" not in value:
            return value
        if "handoff_kind" not in value:
            raise ValueError("preview_handoff.handoff_kind is required")
        if value["handoff_kind"] != "construction_artifact_preview_handoff_v1":
            raise ValueError(f"unsupported preview_handoff.handoff_kind: {value['handoff_kind']}")
        mixed_legacy_fields = set(value) - {"handoff_kind", "construction_artifact_id", "effective_replay_params"}
        if mixed_legacy_fields:
            raise ValueError("preview_handoff request must not mix legacy replay override fields")
        return value


class OptimizerHandoffReplayTruthSeparation(BaseModel):
    baseline_truth: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    candidate_truth: Literal["hypothetical_optimizer_handoff"] = "hypothetical_optimizer_handoff"
    candidate_applied: Literal[False] = False
    consumption_mode: Literal["explicit_reference_only"] = "explicit_reference_only"


OptimizerHandoffReplayAnalyticsFamily = Literal[
    "benchmark_relative_volatility_outputs",
    "factor_exposure_outputs",
    "stress_scenario_outputs",
    "risk_contribution_outputs",
    "concentration_outputs",
]


class OptimizerHandoffReplayOutputPolicy(BaseModel):
    source: Literal["persisted_return_basis_attestation"] = "persisted_return_basis_attestation"
    section_trust: OptimizerReturnBasisSectionTrust
    eligible_families: list[OptimizerHandoffReplayAnalyticsFamily] = Field(default_factory=list)
    withheld_families: list[OptimizerHandoffReplayAnalyticsFamily] = Field(default_factory=list)


class OptimizerHandoffReplayProvenance(BaseModel):
    source: Literal["optimizer_handoff_reference"] = "optimizer_handoff_reference"
    benchmark_id: str
    benchmark_version: str
    benchmark_symbol: str
    return_basis_attestation: OptimizerReturnBasisAttestation
    replay_output_policy: OptimizerHandoffReplayOutputPolicy
    artifact_state: OptimizerArtifactState
    optimizer_status: Literal["feasible"] = "feasible"
    constraint_set_fingerprint: str


class OptimizerHandoffReplayOptimizerRunSummary(BaseModel):
    engine_id: str
    solver_id: str
    methodology_id: str
    risk_package_id: str | None = None
    risk_package_version: str | None = None
    alpha_package_id: str | None = None
    alpha_package_version: str | None = None


class OptimizerHandoffReplayOptimizerDiagnostics(BaseModel):
    active_share: float | None = None
    turnover: float | None = None
    max_abs_active_weight: float | None = None
    active_risk: float | None = None
    effective_holdings: float | None = None
    current_to_proposed_l2: float | None = None
    benchmark_to_proposed_l2: float | None = None
    risk_package_coverage_ratio: float | None = None
    alpha_package_coverage_ratio: float | None = None


class OptimizerHandoffReplayConstraintSummary(BaseModel):
    constraint_id: str
    status: OptimizerConstraintStatus
    actual_value: float | None = None
    limit_value: float | None = None
    slack: float | None = None
    message: str


class OptimizerHandoffReplayBenchmarkAttestationSummary(BaseModel):
    attestation_id: str
    attestation_type: OptimizerBenchmarkAttestationType
    status: OptimizerConstraintStatus | Literal["aligned", "misaligned"]
    actual_value: float | None = None
    limit_value: float | None = None
    slack: float | None = None
    message: str


class OptimizerHandoffReplayOptimizerContext(BaseModel):
    objective: OptimizerObjective
    penalty_ids: list[str] = Field(default_factory=list)
    artifact_state: OptimizerArtifactState
    stale_inputs: list[str] = Field(default_factory=list)
    degraded_inputs: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    run_summary: OptimizerHandoffReplayOptimizerRunSummary
    diagnostics: OptimizerHandoffReplayOptimizerDiagnostics
    binding_constraints: list[str] = Field(default_factory=list)
    violated_constraints: list[str] = Field(default_factory=list)
    benchmark_relative_attestations: list[OptimizerHandoffReplayBenchmarkAttestationSummary] = Field(default_factory=list)
    binding_constraint_evaluations: list[OptimizerHandoffReplayConstraintSummary] = Field(default_factory=list)


class OptimizerHandoffValidationTruthSeparation(BaseModel):
    source_truth: Literal["persisted_hypothetical_optimizer_handoff"] = "persisted_hypothetical_optimizer_handoff"
    holdings_truth: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    optimizer_output_applied: Literal[False] = False
    consumption_mode: Literal["explicit_reference_only"] = "explicit_reference_only"


OptimizerHandoffValidationReasonFamily = Literal["schema", "benchmark_context", "constraint_violation", "provenance", "truth_separation"]
OptimizerHandoffValidationPhase = Literal[
    "raw_persisted_payload",
    "model_validation",
    "cross_file_invariants",
    "benchmark_relative_checks",
    "truth_separation_checks",
]


class OptimizerHandoffValidationEvaluation(BaseModel):
    rule_id: str
    phase: OptimizerHandoffValidationPhase
    reason_family: OptimizerHandoffValidationReasonFamily
    severity: Literal["hard_block", "warning"]
    status: Literal["pass", "fail"]
    message: str
    rationale: str | None = None
    actual_value: float | str | bool | None = None
    expected_value: float | str | bool | None = None
    operator: Literal["<=", ">=", "==", "!=", "in"] | None = None


class OptimizerHandoffValidationProvenance(BaseModel):
    source: Literal["optimizer_handoff_reference"] = "optimizer_handoff_reference"
    benchmark_id: str | None = None
    benchmark_version: str | None = None
    benchmark_symbol: str | None = None
    objective: OptimizerObjective | None = None
    replay_output_policy: OptimizerHandoffReplayOutputPolicy | None = None
    artifact_state: OptimizerArtifactState | None = None
    constraint_set_fingerprint: str | None = None


class OptimizerHandoffEligibleReplayWindow(BaseModel):
    source: Literal["persisted_return_basis_attestation"] = "persisted_return_basis_attestation"
    benchmark_symbol: str | None = None
    as_of_date: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class OptimizerHandoffValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_reference: OptimizerPersistedArtifactReference
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def _validate_candidate_window(self) -> "OptimizerHandoffValidationRequest":
        if (self.start_date is None) != (self.end_date is None):
            raise ValueError("start_date and end_date must be supplied together")
        return self


class OptimizerHandoffValidationResponse(BaseModel):
    handoff_id: str | None = None
    artifact_id: str | None = Field(default=None, deprecated=True)
    source_portfolio_snapshot_id: str | None = None
    truth_separation: OptimizerHandoffValidationTruthSeparation = Field(default_factory=OptimizerHandoffValidationTruthSeparation)
    eligible_replay_window: OptimizerHandoffEligibleReplayWindow | None = None
    provenance: OptimizerHandoffValidationProvenance
    validation_status: Literal["ok", "blocked", "rejected"]
    evaluations: list[OptimizerHandoffValidationEvaluation] = Field(default_factory=list)
    blocking_rule_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class OptimizerHandoffReplayRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_reference: OptimizerPersistedArtifactReference
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    rebalance_frequency: AllocationRebalanceFrequency = "monthly"
    base_currency: str = "USD"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    drift_tolerance_pct: float | None = None
    price_basis: Literal["adjusted_close"] = "adjusted_close"
    execution_price_field: Literal["close"] = "close"
    execution_lag_days: int = 1
    symbol_overrides: dict[str, list[str]] = Field(default_factory=dict)


class OptimizerHandoffReplayResponse(BaseModel):
    handoff_id: str
    artifact_id: str = Field(deprecated=True)
    source_portfolio_snapshot_id: str
    truth_separation: OptimizerHandoffReplayTruthSeparation = Field(default_factory=OptimizerHandoffReplayTruthSeparation)
    replay_provenance: OptimizerHandoffReplayProvenance
    optimizer_context: OptimizerHandoffReplayOptimizerContext | None = None
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    replay: PortfolioAllocationBacktestResponse


class OverlayStateInput(BaseModel):
    overlay_id: Literal["benchmark_trend_overlay_v1"]
    status: Literal["risk_on", "risk_reduced", "unconfirmed", "unavailable"]
    as_of_month_end: str
    benchmark_symbol: str
    signal_basis: Literal["10_month_sma_month_end"]
    confirmation_count: int
    rule_version: str


class OverlayApplicationSummary(BaseModel):
    overlay_id: Literal["benchmark_trend_overlay_v1"]
    overlay_status: Literal["risk_on", "risk_reduced"]
    as_of_month_end: str
    benchmark_symbol: str
    risky_weight_scale: float
    cash_residual_weight: float
    applied_to_candidate_only: bool = True


class OverlayAwareHypotheticalReplayRequest(BaseModel):
    snapshot: DraftPortfolioSnapshotInput
    replacement_intent: ReplacementIntentReplayInput | None = None
    constructed_candidate: ConstructedCandidateReplayInput | None = None
    constraint_validation: SingleReplacementConstructionConstraintValidationResponse | None = None
    overlay_state: OverlayStateInput | None = None
    benchmark_symbol: str = "SPY"
    start_date: date
    end_date: date
    initial_capital: float = 100_000.0
    rebalance_frequency: AllocationRebalanceFrequency = "monthly"
    base_currency: str = "USD"
    commission_bps: float = 0.0
    slippage_bps: float = 0.0
    drift_tolerance_pct: float | None = None
    price_basis: Literal["adjusted_close"] = "adjusted_close"
    execution_price_field: Literal["close"] = "close"
    execution_lag_days: int = 1
    symbol_overrides: dict[str, list[str]] = Field(default_factory=dict)


class OverlayAwareHypotheticalReplayResponse(BaseModel):
    proposal: HypotheticalReplayProposal
    derivation: HypotheticalReplayDerivation
    replay_provenance: HypotheticalReplayProvenance
    overlay_application: OverlayApplicationSummary
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights_pre_overlay: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights_post_overlay: list[PortfolioWeightInput] = Field(default_factory=list)
    base_replay: PortfolioAllocationBacktestResponse
    overlay_replay: PortfolioAllocationBacktestResponse
    warnings: list[str] = Field(default_factory=list)


MonitorDefinitionObservationStatus = Literal["ok", "threshold_breach", "degraded", "unavailable"]


class BenchmarkTrendOverlayMonitorThresholds(BaseModel):
    minimum_confirmation_count: int = 2
    risk_on_min_risky_weight: float = 0.95
    risk_on_max_cash_weight: float = 0.05
    risk_reduced_max_risky_weight: float = 0.35
    risk_reduced_min_cash_weight: float = 0.65

    @model_validator(mode="after")
    def _validate_thresholds(self) -> "BenchmarkTrendOverlayMonitorThresholds":
        if self.minimum_confirmation_count < 1:
            raise ValueError("minimum_confirmation_count must be at least 1")
        bounded_values = {
            "risk_on_min_risky_weight": self.risk_on_min_risky_weight,
            "risk_on_max_cash_weight": self.risk_on_max_cash_weight,
            "risk_reduced_max_risky_weight": self.risk_reduced_max_risky_weight,
            "risk_reduced_min_cash_weight": self.risk_reduced_min_cash_weight,
        }
        for field_name, value in bounded_values.items():
            if value < 0 or value > 1:
                raise ValueError(f"{field_name} must be between 0 and 1")
        return self


class BenchmarkTrendOverlayMonitorSourceLineageRequirements(BaseModel):
    benchmark_source_kind: Literal["benchmark_overlay_signal"] = "benchmark_overlay_signal"
    portfolio_truth_basis: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    required_portfolio_statement_fields: list[str] = Field(
        default_factory=lambda: ["importer", "imported_at", "source_path", "statement_period"]
    )
    required_benchmark_observation_fields: list[str] = Field(
        default_factory=lambda: [
            "overlay_id",
            "benchmark_symbol",
            "as_of_month_end",
            "signal_basis",
            "confirmation_count",
            "rule_version",
            "source_lineage.source_id",
            "source_lineage.observed_at",
        ]
    )


class MonitorDefinitionArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal["monitor_definition_artifact_v1"] = "monitor_definition_artifact_v1"
    monitor_definition_id: str
    fingerprint: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    review_scope: Literal["current_portfolio_truth_only"] = "current_portfolio_truth_only"
    evaluation_mode: Literal["review_only_observation_evaluation"] = "review_only_observation_evaluation"
    observation_statuses: list[MonitorDefinitionObservationStatus] = Field(
        default_factory=lambda: ["ok", "threshold_breach", "degraded", "unavailable"]
    )
    thresholds: BenchmarkTrendOverlayMonitorThresholds = Field(default_factory=BenchmarkTrendOverlayMonitorThresholds)
    source_lineage_requirements: BenchmarkTrendOverlayMonitorSourceLineageRequirements = Field(
        default_factory=BenchmarkTrendOverlayMonitorSourceLineageRequirements
    )


class CreateMonitorDefinitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str


class MonitorDefinitionArtifactListItem(BaseModel):
    monitor_definition_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    schema_version: Literal["monitor_definition_artifact_v1"]
    fingerprint: str


class MonitorDefinitionArtifactListResponse(BaseModel):
    items: list[MonitorDefinitionArtifactListItem] = Field(default_factory=list)


MonitorDefinitionDiscoveryContractVersion = Literal["monitor_definition_discovery_v1"]
MonitorDefinitionDiscoveryMetadataTruth = Literal["authoritative_persisted_artifact_metadata"]
MonitorDefinitionDiscoveryRowProvenance = Literal["persisted_monitor_definition_artifact"]
MonitorDefinitionDiscoveryRecentOrderProvenance = Literal["persisted_artifact_file_mtime"]
MonitorDefinitionOverlayFamily = Literal["benchmark_trend"]
MonitorDefinitionDiscoveryReviewSupportStatus = Literal["review_supported"]
MonitorDefinitionDiscoveryLifecycleStatus = Literal["enabled", "disabled"]
MonitorDefinitionLatestEvaluationSnapshotStatus = Literal["present", "absent"]
MonitorDefinitionLatestEvaluationSnapshotRecency = Literal["recent", "stale"]
MonitorDefinitionLatestEvaluationSnapshotSchemaVersion = Literal[
    "monitor_definition_latest_evaluation_snapshot_v1"
]
MonitorDefinitionEvaluationHistorySchemaVersion = Literal[
    "monitor_definition_evaluation_history_entry_v1"
]
MonitorDefinitionEvaluationHistoryContractVersion = Literal[
    "monitor_definition_evaluation_history_v1"
]
MonitorDefinitionEvaluationHistoryTruth = Literal[
    "authoritative_persisted_monitor_definition_evaluation_history"
]
MonitorDefinitionEvaluationHistoryRowProvenance = Literal[
    "persisted_monitor_definition_evaluation_history_entry"
]
MonitorDefinitionEvaluationHistoryOrder = Literal["newest_first_evaluated_at"]
MonitorDefinitionLatestEvaluationSignificanceStatus = Literal[
    "informational",
    "action_required",
    "degraded",
    "unavailable",
]


class MonitorDefinitionLatestEvaluationBenchmarkObservationLineage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["benchmark_overlay_signal"] = "benchmark_overlay_signal"
    source_id: str
    observed_at: datetime


class MonitorDefinitionLatestEvaluationPortfolioTruthBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    truth_basis: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    importer: StatementImporter
    imported_at: datetime
    source_path: str
    statement_period: str

    @field_validator("source_path")
    @classmethod
    def _validate_source_path(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("source_path must be non-blank")
        return normalized


class MonitorDefinitionLatestEvaluationSnapshotArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: MonitorDefinitionLatestEvaluationSnapshotSchemaVersion = (
        "monitor_definition_latest_evaluation_snapshot_v1"
    )
    monitor_definition_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    evaluated_at: datetime
    outcome_status: MonitorDefinitionObservationStatus
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    benchmark_observation_lineage: MonitorDefinitionLatestEvaluationBenchmarkObservationLineage
    portfolio_truth_basis: MonitorDefinitionLatestEvaluationPortfolioTruthBasis

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value


class MonitorDefinitionDiscoveryFilters(BaseModel):
    overlay_family: MonitorDefinitionOverlayFamily | None = None
    monitor_id: Literal["benchmark_trend_overlay_v1"] | None = None
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus | None = None
    lifecycle_status: MonitorDefinitionDiscoveryLifecycleStatus | None = None
    latest_evaluation_snapshot_status: MonitorDefinitionLatestEvaluationSnapshotStatus | None = None
    latest_evaluation_snapshot_recency: MonitorDefinitionLatestEvaluationSnapshotRecency | None = None


class MonitorDefinitionLifecycleStatusMetadata(BaseModel):
    overlay_family: MonitorDefinitionOverlayFamily = "benchmark_trend"
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus = "review_supported"
    lifecycle_status: MonitorDefinitionDiscoveryLifecycleStatus = "enabled"


class MonitorDefinitionLatestEvaluationSnapshotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluated_at: datetime
    outcome_status: MonitorDefinitionObservationStatus
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    recency_status: MonitorDefinitionLatestEvaluationSnapshotRecency


class MonitorDefinitionStatusMetadata(BaseModel):
    lifecycle: MonitorDefinitionLifecycleStatusMetadata = Field(
        default_factory=MonitorDefinitionLifecycleStatusMetadata
    )
    latest_evaluation_snapshot_status: MonitorDefinitionLatestEvaluationSnapshotStatus = "absent"
    latest_evaluation_snapshot: MonitorDefinitionLatestEvaluationSnapshotSummary | None = None


class MonitorDefinitionCatalogRowMetadata(BaseModel):
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = "authoritative_persisted_artifact_metadata"
    row_provenance: MonitorDefinitionDiscoveryRowProvenance = "persisted_monitor_definition_artifact"
    status: MonitorDefinitionStatusMetadata = Field(default_factory=MonitorDefinitionStatusMetadata)


class MonitorDefinitionCatalogRow(BaseModel):
    monitor_definition_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    schema_version: Literal["monitor_definition_artifact_v1"]
    fingerprint: str
    review_scope: Literal["current_portfolio_truth_only"]
    evaluation_mode: Literal["review_only_observation_evaluation"]
    observation_statuses: list[MonitorDefinitionObservationStatus] = Field(default_factory=list)
    thresholds: BenchmarkTrendOverlayMonitorThresholds
    source_lineage_requirements: BenchmarkTrendOverlayMonitorSourceLineageRequirements
    metadata: MonitorDefinitionCatalogRowMetadata = Field(default_factory=MonitorDefinitionCatalogRowMetadata)


class MonitorDefinitionCatalogResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionDiscoveryContractVersion = "monitor_definition_discovery_v1"
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = "authoritative_persisted_artifact_metadata"
    row_provenance: MonitorDefinitionDiscoveryRowProvenance = "persisted_monitor_definition_artifact"
    supported_monitor_ids: list[Literal["benchmark_trend_overlay_v1"]] = Field(
        default_factory=lambda: ["benchmark_trend_overlay_v1"]
    )
    supported_overlay_families: list[MonitorDefinitionOverlayFamily] = Field(
        default_factory=lambda: ["benchmark_trend"]
    )
    applied_filters: MonitorDefinitionDiscoveryFilters = Field(default_factory=MonitorDefinitionDiscoveryFilters)


class MonitorDefinitionCatalogResponse(BaseModel):
    items: list[MonitorDefinitionCatalogRow] = Field(default_factory=list)
    metadata: MonitorDefinitionCatalogResponseMetadata = Field(default_factory=MonitorDefinitionCatalogResponseMetadata)


class MonitorDefinitionRecentRowMetadata(BaseModel):
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = "authoritative_persisted_artifact_metadata"
    row_provenance: MonitorDefinitionDiscoveryRowProvenance = "persisted_monitor_definition_artifact"
    recent_order_provenance: MonitorDefinitionDiscoveryRecentOrderProvenance = "persisted_artifact_file_mtime"
    status: MonitorDefinitionStatusMetadata = Field(default_factory=MonitorDefinitionStatusMetadata)


class MonitorDefinitionRecentRow(BaseModel):
    monitor_definition_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    schema_version: Literal["monitor_definition_artifact_v1"]
    fingerprint: str
    review_scope: Literal["current_portfolio_truth_only"]
    evaluation_mode: Literal["review_only_observation_evaluation"]
    observation_statuses: list[MonitorDefinitionObservationStatus] = Field(default_factory=list)
    thresholds: BenchmarkTrendOverlayMonitorThresholds
    source_lineage_requirements: BenchmarkTrendOverlayMonitorSourceLineageRequirements
    artifact_last_modified_at: datetime
    metadata: MonitorDefinitionRecentRowMetadata = Field(default_factory=MonitorDefinitionRecentRowMetadata)


class MonitorDefinitionRecentResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionDiscoveryContractVersion = "monitor_definition_discovery_v1"
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = "authoritative_persisted_artifact_metadata"
    row_provenance: MonitorDefinitionDiscoveryRowProvenance = "persisted_monitor_definition_artifact"
    recent_order_provenance: MonitorDefinitionDiscoveryRecentOrderProvenance = "persisted_artifact_file_mtime"
    supported_monitor_ids: list[Literal["benchmark_trend_overlay_v1"]] = Field(
        default_factory=lambda: ["benchmark_trend_overlay_v1"]
    )
    supported_overlay_families: list[MonitorDefinitionOverlayFamily] = Field(
        default_factory=lambda: ["benchmark_trend"]
    )
    applied_filters: MonitorDefinitionDiscoveryFilters = Field(default_factory=MonitorDefinitionDiscoveryFilters)


class MonitorDefinitionRecentResponse(BaseModel):
    items: list[MonitorDefinitionRecentRow] = Field(default_factory=list)
    metadata: MonitorDefinitionRecentResponseMetadata = Field(default_factory=MonitorDefinitionRecentResponseMetadata)


class BenchmarkTrendOverlayObservationSourceLineage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_kind: Literal["benchmark_overlay_signal"] = "benchmark_overlay_signal"
    source_id: str
    observed_at: datetime


class BenchmarkTrendOverlayMonitorBenchmarkObservationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overlay_id: Literal["benchmark_trend_overlay_v1"]
    status: Literal["risk_on", "risk_reduced", "unconfirmed", "unavailable"]
    as_of_month_end: date
    benchmark_symbol: str
    signal_basis: Literal["10_month_sma_month_end"]
    confirmation_count: int
    rule_version: str
    source_lineage: BenchmarkTrendOverlayObservationSourceLineage

    @field_validator("benchmark_symbol", mode="before")
    @classmethod
    def _validate_benchmark_symbol_canonicality(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("benchmark_symbol must be non-blank")
        if value != normalized:
            raise ValueError(
                "benchmark_symbol must be canonical uppercase without surrounding whitespace"
            )
        return value


class EvaluateMonitorDefinitionObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_portfolio: ImportedPortfolioSnapshot
    benchmark_observation: BenchmarkTrendOverlayMonitorBenchmarkObservationInput


class CurrentPortfolioTruthLineage(BaseModel):
    truth_basis: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    importer: StatementImporter
    imported_at: datetime
    statement_period: str
    source_paths: list[str] = Field(default_factory=list)


class BenchmarkTrendOverlayMonitorPortfolioObservation(BaseModel):
    total_portfolio_value: float
    risky_value: float
    cash_value: float
    risky_weight: float | None = None
    cash_weight: float | None = None
    position_count: int
    source_lineage: CurrentPortfolioTruthLineage


class MonitorThresholdTrigger(BaseModel):
    threshold_id: Literal[
        "risk_on_min_risky_weight",
        "risk_on_max_cash_weight",
        "risk_reduced_max_risky_weight",
        "risk_reduced_min_cash_weight",
    ]
    operator: Literal[">=", "<="]
    threshold_value: float
    actual_value: float
    breach_amount: float


class BenchmarkTrendOverlayMonitorActiveObservation(BaseModel):
    required_overlay_status: Literal["risk_on", "risk_reduced", "unconfirmed", "unavailable"]
    threshold_evaluation_performed: bool
    required_min_risky_weight: float | None = None
    required_max_risky_weight: float | None = None
    required_min_cash_weight: float | None = None
    required_max_cash_weight: float | None = None
    actual_risky_weight: float | None = None
    actual_cash_weight: float | None = None
    risky_weight_gap: float | None = None
    cash_weight_gap: float | None = None
    triggered_thresholds: list[MonitorThresholdTrigger] = Field(default_factory=list)


class MonitorDefinitionObservationEvaluationResponse(BaseModel):
    monitor_definition_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    evaluation_mode: Literal["review_only_observation_evaluation"] = "review_only_observation_evaluation"
    observation_status: MonitorDefinitionObservationStatus
    reason: str | None = None
    thresholds: BenchmarkTrendOverlayMonitorThresholds
    benchmark_observation: BenchmarkTrendOverlayMonitorBenchmarkObservationInput
    portfolio_observation: BenchmarkTrendOverlayMonitorPortfolioObservation
    active_observation: BenchmarkTrendOverlayMonitorActiveObservation


class MonitorDefinitionEvaluationHistoryEntryArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: MonitorDefinitionEvaluationHistorySchemaVersion = (
        "monitor_definition_evaluation_history_entry_v1"
    )
    history_entry_id: str
    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    evaluation_mode: Literal["review_only_observation_evaluation"] = "review_only_observation_evaluation"
    evaluated_at: datetime
    observation_status: MonitorDefinitionObservationStatus
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    reason: str | None = None
    thresholds: BenchmarkTrendOverlayMonitorThresholds
    benchmark_observation: BenchmarkTrendOverlayMonitorBenchmarkObservationInput
    portfolio_observation: BenchmarkTrendOverlayMonitorPortfolioObservation
    active_observation: BenchmarkTrendOverlayMonitorActiveObservation

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value


class MonitorDefinitionEvaluationHistoryRowMetadata(BaseModel):
    history_truth: MonitorDefinitionEvaluationHistoryTruth = (
        "authoritative_persisted_monitor_definition_evaluation_history"
    )
    row_provenance: MonitorDefinitionEvaluationHistoryRowProvenance = (
        "persisted_monitor_definition_evaluation_history_entry"
    )


class MonitorDefinitionEvaluationHistoryRow(MonitorDefinitionEvaluationHistoryEntryArtifact):
    metadata: MonitorDefinitionEvaluationHistoryRowMetadata = Field(
        default_factory=MonitorDefinitionEvaluationHistoryRowMetadata
    )


class MonitorDefinitionEvaluationHistoryResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionEvaluationHistoryContractVersion = (
        "monitor_definition_evaluation_history_v1"
    )
    history_truth: MonitorDefinitionEvaluationHistoryTruth = (
        "authoritative_persisted_monitor_definition_evaluation_history"
    )
    row_provenance: MonitorDefinitionEvaluationHistoryRowProvenance = (
        "persisted_monitor_definition_evaluation_history_entry"
    )
    inspection_order: MonitorDefinitionEvaluationHistoryOrder = "newest_first_evaluated_at"
    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    returned_limit: int | None = None
    total_entries: int = 0


class MonitorDefinitionEvaluationHistoryResponse(BaseModel):
    items: list[MonitorDefinitionEvaluationHistoryRow] = Field(default_factory=list)
    metadata: MonitorDefinitionEvaluationHistoryResponseMetadata


class MonitorDefinitionEvaluationHistoryEntryResponseMetadata(
    MonitorDefinitionEvaluationHistoryResponseMetadata
):
    retrieved_history_entry_id: str


class MonitorDefinitionEvaluationHistoryEntryResponse(BaseModel):
    item: MonitorDefinitionEvaluationHistoryRow
    metadata: MonitorDefinitionEvaluationHistoryEntryResponseMetadata


class CandidateFormationState(BaseModel):
    kind: Literal["single_replacement_candidate_formation"]
    status: Literal["ok", "rejected"]


class CandidateFormationProposal(BaseModel):
    source: Literal["draft_replacement_intent"]
    draft_id: str | None = None
    workspace_id: str | None = None
    base_node_id: str | None = None
    incumbent_symbol: str | None = None
    candidate_symbol: str | None = None


class CandidateFormationDerivation(BaseModel):
    baseline_basis: Literal["draft_snapshot_positions_normalized"]
    candidate_construction_rule: Literal["single_symbol_weight_substitution"]
    cash_treatment: Literal["excluded_from_candidate_formation_basis"]
    position_scope: Literal["positive_market_value_positions_only"]


class CandidateFormationSummary(BaseModel):
    incumbent_start_weight: float | None = None
    candidate_start_weight: float | None = None
    unchanged_positions_count: int = 0
    baseline_positions_count: int = 0
    candidate_positions_count: int = 0
    starting_turnover_pct: float | None = None


class CandidateFormationTruthProvenance(BaseModel):
    baseline_truth_class: Literal["draft_snapshot_basis"]
    candidate_truth_class: Literal["hypothetical_candidate_input_only"]
    formation_truth_class: Literal["candidate_formation_derived"]
    note: str


class SingleReplacementCandidateFormationRequest(BaseModel):
    snapshot: DraftPortfolioSnapshotInput | None = None
    replacement_intent: ReplacementIntentReplayInput | None = None


class SingleReplacementCandidateFormationResponse(BaseModel):
    formation: CandidateFormationState
    proposal: CandidateFormationProposal
    derivation: CandidateFormationDerivation
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    formation_summary: CandidateFormationSummary
    truth_provenance: CandidateFormationTruthProvenance
    warnings: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None


class CandidateConstructionRuleInput(BaseModel):
    rule_id: str


class CandidateConstructionState(BaseModel):
    kind: Literal["single_replacement_construction"]
    status: Literal["ok", "rejected"]
    rule_id: str | None = None


class CandidateConstructionInputs(BaseModel):
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    construction_rule: str | None = None
    incumbent_start_weight: float | None = None
    candidate_added_weight: float | None = None
    incumbent_remaining_weight: float | None = None


class CandidateConstructionOutputs(BaseModel):
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    starting_turnover_pct: float | None = None
    unchanged_positions_count: int = 0
    candidate_added_weight: float | None = None
    incumbent_remaining_weight: float | None = None


class CandidateConstructionDerivation(BaseModel):
    baseline_basis: Literal["draft_snapshot_positions_normalized"]
    construction_basis: Literal["explicit_single_replacement_rule"]
    cash_treatment: Literal["excluded_from_construction_basis"]
    position_scope: Literal["positive_market_value_positions_only"]


class CandidateConstructionTruthProvenance(BaseModel):
    baseline_truth_class: Literal["draft_snapshot_basis"]
    construction_truth_class: Literal["candidate_construction_derived"]
    candidate_truth_class: Literal["hypothetical_candidate_input_only"]
    note: str


class SingleReplacementCandidateConstructionRequest(BaseModel):
    snapshot: DraftPortfolioSnapshotInput | None = None
    replacement_intent: ReplacementIntentReplayInput | None = None
    construction_rule: CandidateConstructionRuleInput | None = None


class SingleReplacementCandidateConstructionResponse(BaseModel):
    construction: CandidateConstructionState
    proposal: CandidateFormationProposal
    inputs: CandidateConstructionInputs
    outputs: CandidateConstructionOutputs
    derivation: CandidateConstructionDerivation
    truth_provenance: CandidateConstructionTruthProvenance
    warnings: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None


class SingleReplacementConstructionConstraintSetInput(BaseModel):
    constraint_set_id: str


class SingleReplacementConstraintValidationState(BaseModel):
    kind: Literal["single_replacement_construction_constraint_validation"]
    status: Literal["ok", "blocked", "rejected"]
    constraint_set_id: Literal["single_replacement_construction_constraints_v1"]


class SingleReplacementConstraintEvaluation(BaseModel):
    constraint_id: str
    severity: Literal["hard_block", "warning"]
    status: Literal["pass", "fail", "not_applicable"]
    message: str
    rationale: str | None = None
    actual_value: float | str | None = None
    expected_value: float | str | None = None
    operator: Literal["<=", ">=", "==", "!=", "in"] | None = None


class SingleReplacementConstraintValidationDerivation(BaseModel):
    validation_timing: Literal["post_construction_pre_replay"]
    validation_basis: Literal["explicit_constraint_set"]
    candidate_input_source: Literal["constructed_candidate_payload"]
    constraint_set_id: Literal["single_replacement_construction_constraints_v1"]


class SingleReplacementConstraintValidationTruthProvenance(BaseModel):
    baseline_truth_class: Literal["draft_snapshot_basis"]
    construction_truth_class: Literal["candidate_construction_derived"]
    candidate_truth_class: Literal["hypothetical_candidate_input_only"]
    constraint_validation_truth_class: Literal["constraint_validation_derived"]
    note: str


class SingleReplacementConstructionConstraintValidationRequest(BaseModel):
    constructed_candidate: ConstructedCandidateReplayInput | None = None
    constraint_set: SingleReplacementConstructionConstraintSetInput | None = None


class SingleReplacementConstructionConstraintValidationResponse(BaseModel):
    validation: SingleReplacementConstraintValidationState
    proposal: CandidateFormationProposal
    construction: CandidateConstructionState
    derivation: SingleReplacementConstraintValidationDerivation
    truth_provenance: SingleReplacementConstraintValidationTruthProvenance
    evaluations: list[SingleReplacementConstraintEvaluation] = Field(default_factory=list)
    blocking_constraint_ids: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    rejection_reason: str | None = None
