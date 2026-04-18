from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.imports import StatementImporter
from app.schemas.reconciliation import RiskContributionBreakdownPayload, SnapshotItem, StressScenarioResult, VolatilitySnapshot
from app.schemas.research import AllocationRebalanceFrequency, BacktestFrequency, ContinuousSeriesSpec, DistributionPolicy, StrategyDefinition


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
    equity: float
    cash: float
    gross_exposure: float | None = None
    net_exposure: float | None = None
    drawdown_pct: float | None = None


class BacktestRun(BaseModel):
    run_id: str
    config: BacktestConfig
    dataset_info: dict[str, dict[str, str | bool]] = Field(default_factory=dict)
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
    candidate_input_source: Literal["replacement_intent_preview", "constructed_candidate_payload"]
    construction_rule_id: Literal["same_weight_substitution_v1", "fixed_split_50_50_substitution_v2"]
    upstream_ids: HypotheticalReplayUpstreamIds
    seed_ranking_id: str
    seed_methodology_id: str


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
