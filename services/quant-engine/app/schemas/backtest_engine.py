from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, TypeAlias

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
    proposal_source: "HypotheticalReplayProposalSource" = Field(default_factory=lambda: HypotheticalReplayProposalSource())
    incumbent_symbol: str
    candidate_symbol: str
    draft_id: str
    base_node_id: str


class HypotheticalReplayProposalSource(BaseModel):
    proposal_source_version: Literal[1] = 1
    proposal_source_kind: Literal["draft_replacement_intent_review_only"] = "draft_replacement_intent_review_only"
    proposal_truth: Literal["review_only_hypothetical_proposal"] = "review_only_hypothetical_proposal"
    portfolio_truth: Literal["draft_snapshot_not_applied"] = "draft_snapshot_not_applied"
    review_scope: Literal["proposal_review_context_only"] = "proposal_review_context_only"


class HypotheticalReplayDerivation(BaseModel):
    baseline_basis: Literal["draft_snapshot_positions_normalized"]
    candidate_construction_rule: Literal["same_weight_substitution_v1", "fixed_split_50_50_substitution_v2"]


HypotheticalReplayBaselineBasis: TypeAlias = Literal["draft_snapshot_positions_normalized"]
HypotheticalReplayConstructionRuleId: TypeAlias = Literal["same_weight_substitution_v1", "fixed_split_50_50_substitution_v2"]


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
    methodology_provenance: "ReplayMethodologyProvenance" = Field(default_factory=lambda: ReplayMethodologyProvenance())
    investor_economics_status: InvestorEconomicsStatus
    reference_result: AllocationBacktestResult | None = None
    candidate_result: AllocationBacktestResult
    comparison: AllocationBacktestComparison | None = None
    reference_diagnostics: PortfolioDiagnosticsSnapshot | None = None
    candidate_diagnostics: PortfolioDiagnosticsSnapshot | None = None
    diagnostics_comparison: PortfolioImprovementComparison | None = None


class ReplayMethodologyProvenance(BaseModel):
    provenance_version: Literal[1] = 1
    source: Literal["portfolio_allocation_backtest_engine"] = "portfolio_allocation_backtest_engine"
    methodology_truth: Literal["review_only_replay_methodology"] = "review_only_replay_methodology"
    assumptions_truth: Literal["review_only_replay_assumptions"] = "review_only_replay_assumptions"
    analytics_truth: Literal["hypothetical_replay_analytics_only"] = "hypothetical_replay_analytics_only"
    review_scope: Literal["workspace_review_context_only"] = "workspace_review_context_only"


class HypotheticalReplacementReplayResponse(BaseModel):
    proposal: HypotheticalReplayProposal
    derivation: HypotheticalReplayDerivation
    replay_provenance: HypotheticalReplayProvenance
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    replay: PortfolioAllocationBacktestResponse
    warnings: list[str] = Field(default_factory=list)


ReviewSnapshotArtifactSchemaVersion = Literal["review_snapshot_artifact_v1"]
ReviewSnapshotArtifactKind = Literal["portfolio_review_snapshot"]
ReviewSnapshotConsumerKind = Literal["saved_hypothetical_replay_proposal"]
ReviewSnapshotSourceKind = Literal["hypothetical_replacement_replay"]
ReviewSnapshotComparisonConsumerKind = Literal["review_snapshot_comparison"]
ReviewSnapshotFamilyReviewConsumerKind = Literal["review_snapshot_family_review"]
ReviewSnapshotFamilyInboxConsumerKind = Literal["review_snapshot_family_inbox"]
ReviewSnapshotActiveThesisCrossFamilyQueueConsumerKind = Literal["review_snapshot_active_thesis_cross_family_queue"]
ReviewSnapshotComparisonRole = Literal["baseline", "candidate"]
ReviewSnapshotPMSummaryRole = Literal["saved_proposal", "baseline", "candidate"]


class ReviewSnapshotArtifactIdentity(BaseModel):
    artifact_id: str
    artifact_kind: ReviewSnapshotArtifactKind = "portfolio_review_snapshot"
    schema_version: ReviewSnapshotArtifactSchemaVersion = "review_snapshot_artifact_v1"
    fingerprint: str
    consumer_kind: ReviewSnapshotConsumerKind = "saved_hypothetical_replay_proposal"


class ReviewSnapshotArtifactLineage(BaseModel):
    workspace_id: str
    source_draft_id: str
    source_base_node_id: str
    proposal_family_id: str
    proposal_id: str
    version_number: int
    source_kind: ReviewSnapshotSourceKind = "hypothetical_replacement_replay"


class ReviewSnapshotArtifactReviewBasis(BaseModel):
    benchmark_symbol: str
    start_date: str
    end_date: str
    rebalance_frequency: str
    commission_bps: float
    slippage_bps: float
    derivation_basis: HypotheticalReplayBaselineBasis
    candidate_construction_rule: HypotheticalReplayConstructionRuleId
    replay_provenance: HypotheticalReplayProvenance


class ReviewSnapshotArtifactTruthLabels(BaseModel):
    proposal_truth: Literal["review_only_hypothetical_proposal"] = "review_only_hypothetical_proposal"
    portfolio_truth: Literal["draft_snapshot_not_applied"] = "draft_snapshot_not_applied"
    analytics_truth: Literal["hypothetical_replay_analytics_only"] = "hypothetical_replay_analytics_only"
    review_scope: Literal["proposal_review_context_only"] = "proposal_review_context_only"


class ReviewSnapshotArtifactAnalyticsSummary(BaseModel):
    methodology: str
    methodology_provenance: "ReplayMethodologyProvenance"
    assumptions: AllocationBacktestAssumptions
    benchmark_symbol: str | None = None
    benchmark_return_pct: float | None = None
    total_return_pct: float | None = None
    annualized_return_pct: float | None = None
    annualized_volatility_pct: float | None = None
    downside_volatility_pct: float | None = None
    max_drawdown_pct: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    excess_return_pct: float | None = None
    tracking_error_pct: float | None = None
    information_ratio: float | None = None
    beta_vs_benchmark: float | None = None
    correlation_vs_benchmark: float | None = None
    total_turnover_pct: float | None = None
    total_cost_paid: float | None = None


class ReviewSnapshotArtifactDiagnosticsSummary(BaseModel):
    diagnostics_available: bool
    top_factor_exposure_change: PortfolioDiagnosticsTopCallout | None = None
    top_volatility_change: PortfolioDiagnosticsTopCallout | None = None
    top_risk_contribution_change: PortfolioDiagnosticsTopCallout | None = None
    top_concentration_change: PortfolioDiagnosticsTopCallout | None = None
    top_stress_scenario_change: PortfolioDiagnosticsTopCallout | None = None


class ReviewSnapshotArtifactCompactSummary(BaseModel):
    replay_type: Literal["standard", "overlay_aware"]
    replay_status: AllocationBacktestStatus
    investor_economics_status: InvestorEconomicsStatus
    candidate_analytics: ReviewSnapshotArtifactAnalyticsSummary
    baseline_analytics: ReviewSnapshotArtifactAnalyticsSummary | None = None
    analytics_comparison: AllocationBacktestComparison | None = None
    diagnostics_summary: ReviewSnapshotArtifactDiagnosticsSummary


class ReviewSnapshotPMSummaryProvenance(BaseModel):
    source: Literal["persisted_review_snapshot_artifact"] = "persisted_review_snapshot_artifact"
    artifact_kind: ReviewSnapshotArtifactKind = "portfolio_review_snapshot"
    schema_version: ReviewSnapshotArtifactSchemaVersion = "review_snapshot_artifact_v1"
    consumer_kind: ReviewSnapshotConsumerKind = "saved_hypothetical_replay_proposal"
    lineage: ReviewSnapshotArtifactLineage
    proposal_source: "HypotheticalReplayProposalSource"
    replay_provenance: HypotheticalReplayProvenance


class ReviewSnapshotPMSummaryReviewBasis(BaseModel):
    benchmark_separation: Literal["explicit_per_snapshot_benchmark_fields"] = "explicit_per_snapshot_benchmark_fields"
    benchmark_symbol: str
    replay_window: WorkspaceReviewWindow
    rebalance_frequency: str
    commission_bps: float
    slippage_bps: float
    derivation_basis: HypotheticalReplayBaselineBasis
    candidate_construction_rule: HypotheticalReplayConstructionRuleId


class ReviewSnapshotPMSummaryMethodology(BaseModel):
    methodology: str
    methodology_provenance: "ReplayMethodologyProvenance"


class ReviewSnapshotPMSummaryAnalyticsSummary(BaseModel):
    candidate_analytics: ReviewSnapshotArtifactAnalyticsSummary
    baseline_analytics: ReviewSnapshotArtifactAnalyticsSummary | None = None
    analytics_comparison: AllocationBacktestComparison | None = None


class ReviewSnapshotPMSummaryEnvelope(BaseModel):
    pm_summary_version: Literal[1] = 1
    role: ReviewSnapshotPMSummaryRole = "saved_proposal"
    provenance: ReviewSnapshotPMSummaryProvenance
    truth_labels: ReviewSnapshotArtifactTruthLabels
    replay_type: Literal["standard", "overlay_aware"]
    replay_status: AllocationBacktestStatus
    investor_economics_status: InvestorEconomicsStatus
    review_basis: ReviewSnapshotPMSummaryReviewBasis
    methodology: ReviewSnapshotPMSummaryMethodology
    assumptions: AllocationBacktestAssumptions
    analytics_summary: ReviewSnapshotPMSummaryAnalyticsSummary
    diagnostics_summary: ReviewSnapshotArtifactDiagnosticsSummary


class ReviewSnapshotOpenHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: Literal["review_snapshot_open_handoff_v1"] = "review_snapshot_open_handoff_v1"
    artifact_id: str
    artifact_kind: ReviewSnapshotArtifactKind = "portfolio_review_snapshot"
    schema_version: ReviewSnapshotArtifactSchemaVersion = "review_snapshot_artifact_v1"
    consumer_kind: ReviewSnapshotConsumerKind = "saved_hypothetical_replay_proposal"


class ReviewSnapshotProposalCaptureProposal(BaseModel):
    source: Literal["draft_replacement_intent"] = "draft_replacement_intent"
    proposal_source: "HypotheticalReplayProposalSource"
    incumbent_symbol: str
    candidate_symbol: str


class ReviewSnapshotProposalCaptureReviewBasis(BaseModel):
    benchmark_separation: Literal["explicit_per_snapshot_benchmark_fields"] = "explicit_per_snapshot_benchmark_fields"
    benchmark_symbol: str
    replay_window: WorkspaceReviewWindow
    rebalance_frequency: str
    commission_bps: float
    slippage_bps: float
    derivation_basis: HypotheticalReplayBaselineBasis
    candidate_construction_rule: HypotheticalReplayConstructionRuleId


class ReviewSnapshotProposalCapture(BaseModel):
    capture_version: Literal[1] = 1
    capture_kind: Literal["workspace_review_saved_proposal"] = "workspace_review_saved_proposal"
    open_handoff: ReviewSnapshotOpenHandoff
    lineage: ReviewSnapshotArtifactLineage
    proposal: ReviewSnapshotProposalCaptureProposal
    replay_type: Literal["standard", "overlay_aware"]
    replay_provenance: HypotheticalReplayProvenance
    review_basis: ReviewSnapshotProposalCaptureReviewBasis


class ReviewSnapshotArtifactSourcePayload(BaseModel):
    replay_type: Literal["standard", "overlay_aware"]
    replay: HypotheticalReplacementReplayResponse | None = None
    overlay_replay: OverlayAwareHypotheticalReplayResponse | None = None

    @model_validator(mode="after")
    def _validate_payload_shape(self) -> "ReviewSnapshotArtifactSourcePayload":
        if self.replay_type == "standard":
            if self.replay is None:
                raise ValueError("replay is required when replay_type=standard")
            if self.overlay_replay is not None:
                raise ValueError("overlay_replay must be omitted when replay_type=standard")
        else:
            if self.overlay_replay is None:
                raise ValueError("overlay_replay is required when replay_type=overlay_aware")
            if self.replay is not None:
                raise ValueError("replay must be omitted when replay_type=overlay_aware")
        return self


class ReviewSnapshotArtifact(BaseModel):
    identity: ReviewSnapshotArtifactIdentity
    lineage: ReviewSnapshotArtifactLineage
    review_basis: ReviewSnapshotArtifactReviewBasis
    truth_labels: ReviewSnapshotArtifactTruthLabels = Field(default_factory=ReviewSnapshotArtifactTruthLabels)
    compact_summary: ReviewSnapshotArtifactCompactSummary
    proposal_capture: ReviewSnapshotProposalCapture
    pm_summary: ReviewSnapshotPMSummaryEnvelope
    source_payload: ReviewSnapshotArtifactSourcePayload

    @model_validator(mode="after")
    def _validate_internal_lineage(self) -> "ReviewSnapshotArtifact":
        response = self.source_payload.replay or self.source_payload.overlay_replay
        if response is None:
            raise ValueError("review snapshot source payload is missing authoritative replay payload")
        if response.replay_provenance.upstream_ids.workspace_id != self.lineage.workspace_id:
            raise ValueError("review snapshot lineage workspace_id does not match source payload replay provenance")
        if response.replay_provenance.upstream_ids.draft_id != self.lineage.source_draft_id:
            raise ValueError("review snapshot lineage source_draft_id does not match source payload replay provenance")
        if response.replay_provenance.upstream_ids.base_node_id != self.lineage.source_base_node_id:
            raise ValueError("review snapshot lineage source_base_node_id does not match source payload replay provenance")
        if response.derivation.candidate_construction_rule != self.review_basis.candidate_construction_rule:
            raise ValueError("review snapshot review_basis candidate_construction_rule does not match source payload derivation")
        if response.derivation.baseline_basis != self.review_basis.derivation_basis:
            raise ValueError("review snapshot review_basis derivation_basis does not match source payload derivation")
        if response.replay_provenance != self.review_basis.replay_provenance:
            raise ValueError("review snapshot review_basis replay_provenance does not match source payload replay provenance")
        if self.pm_summary.role != "saved_proposal":
            raise ValueError("review snapshot pm_summary role must be saved_proposal on the persisted artifact")
        if self.proposal_capture.open_handoff.artifact_id != self.identity.artifact_id:
            raise ValueError("review snapshot proposal_capture open_handoff artifact_id does not match artifact identity")
        if self.proposal_capture.open_handoff.artifact_kind != self.identity.artifact_kind:
            raise ValueError("review snapshot proposal_capture open_handoff artifact_kind does not match artifact identity")
        if self.proposal_capture.open_handoff.schema_version != self.identity.schema_version:
            raise ValueError("review snapshot proposal_capture open_handoff schema_version does not match artifact identity")
        if self.proposal_capture.open_handoff.consumer_kind != self.identity.consumer_kind:
            raise ValueError("review snapshot proposal_capture open_handoff consumer_kind does not match artifact identity")
        if self.proposal_capture.lineage != self.lineage:
            raise ValueError("review snapshot proposal_capture lineage does not match artifact lineage")
        if self.proposal_capture.proposal.source != response.proposal.source:
            raise ValueError("review snapshot proposal_capture proposal source does not match source payload proposal")
        if self.proposal_capture.proposal.proposal_source != response.proposal.proposal_source:
            raise ValueError("review snapshot proposal_capture proposal_source does not match source payload proposal")
        if self.proposal_capture.proposal.incumbent_symbol != response.proposal.incumbent_symbol:
            raise ValueError("review snapshot proposal_capture incumbent_symbol does not match source payload proposal")
        if self.proposal_capture.proposal.candidate_symbol != response.proposal.candidate_symbol:
            raise ValueError("review snapshot proposal_capture candidate_symbol does not match source payload proposal")
        if self.proposal_capture.replay_type != self.source_payload.replay_type:
            raise ValueError("review snapshot proposal_capture replay_type does not match source payload replay_type")
        if self.proposal_capture.replay_provenance != self.review_basis.replay_provenance:
            raise ValueError("review snapshot proposal_capture replay_provenance does not match artifact review_basis replay_provenance")
        if self.proposal_capture.review_basis.benchmark_symbol != self.review_basis.benchmark_symbol:
            raise ValueError("review snapshot proposal_capture benchmark_symbol does not match artifact review_basis")
        if self.proposal_capture.review_basis.replay_window != WorkspaceReviewWindow(start_date=self.review_basis.start_date, end_date=self.review_basis.end_date):
            raise ValueError("review snapshot proposal_capture replay_window does not match artifact review_basis")
        if self.proposal_capture.review_basis.rebalance_frequency != self.review_basis.rebalance_frequency:
            raise ValueError("review snapshot proposal_capture rebalance_frequency does not match artifact review_basis")
        if self.proposal_capture.review_basis.commission_bps != self.review_basis.commission_bps:
            raise ValueError("review snapshot proposal_capture commission_bps does not match artifact review_basis")
        if self.proposal_capture.review_basis.slippage_bps != self.review_basis.slippage_bps:
            raise ValueError("review snapshot proposal_capture slippage_bps does not match artifact review_basis")
        if self.proposal_capture.review_basis.derivation_basis != self.review_basis.derivation_basis:
            raise ValueError("review snapshot proposal_capture derivation_basis does not match artifact review_basis")
        if self.proposal_capture.review_basis.candidate_construction_rule != self.review_basis.candidate_construction_rule:
            raise ValueError("review snapshot proposal_capture candidate_construction_rule does not match artifact review_basis")
        if self.pm_summary.provenance.artifact_kind != self.identity.artifact_kind:
            raise ValueError("review snapshot pm_summary artifact_kind does not match artifact identity")
        if self.pm_summary.provenance.schema_version != self.identity.schema_version:
            raise ValueError("review snapshot pm_summary schema_version does not match artifact identity")
        if self.pm_summary.provenance.consumer_kind != self.identity.consumer_kind:
            raise ValueError("review snapshot pm_summary consumer_kind does not match artifact identity")
        if self.pm_summary.provenance.lineage != self.lineage:
            raise ValueError("review snapshot pm_summary lineage does not match artifact lineage")
        if self.pm_summary.provenance.proposal_source != response.proposal.proposal_source:
            raise ValueError("review snapshot pm_summary proposal_source does not match source payload proposal_source")
        if self.pm_summary.provenance.replay_provenance != self.review_basis.replay_provenance:
            raise ValueError("review snapshot pm_summary replay_provenance does not match artifact review_basis replay_provenance")
        if self.pm_summary.truth_labels != self.truth_labels:
            raise ValueError("review snapshot pm_summary truth_labels do not match artifact truth_labels")
        if self.pm_summary.replay_type != self.compact_summary.replay_type:
            raise ValueError("review snapshot pm_summary replay_type does not match artifact compact_summary")
        if self.pm_summary.replay_status != self.compact_summary.replay_status:
            raise ValueError("review snapshot pm_summary replay_status does not match artifact compact_summary")
        if self.pm_summary.investor_economics_status != self.compact_summary.investor_economics_status:
            raise ValueError("review snapshot pm_summary investor_economics_status does not match artifact compact_summary")
        if self.pm_summary.review_basis.benchmark_symbol != self.review_basis.benchmark_symbol:
            raise ValueError("review snapshot pm_summary benchmark_symbol does not match artifact review_basis")
        if self.pm_summary.review_basis.replay_window != WorkspaceReviewWindow(start_date=self.review_basis.start_date, end_date=self.review_basis.end_date):
            raise ValueError("review snapshot pm_summary replay_window does not match artifact review_basis")
        if self.pm_summary.review_basis.rebalance_frequency != self.review_basis.rebalance_frequency:
            raise ValueError("review snapshot pm_summary rebalance_frequency does not match artifact review_basis")
        if self.pm_summary.review_basis.commission_bps != self.review_basis.commission_bps:
            raise ValueError("review snapshot pm_summary commission_bps does not match artifact review_basis")
        if self.pm_summary.review_basis.slippage_bps != self.review_basis.slippage_bps:
            raise ValueError("review snapshot pm_summary slippage_bps does not match artifact review_basis")
        if self.pm_summary.review_basis.derivation_basis != self.review_basis.derivation_basis:
            raise ValueError("review snapshot pm_summary derivation_basis does not match artifact review_basis")
        if self.pm_summary.review_basis.candidate_construction_rule != self.review_basis.candidate_construction_rule:
            raise ValueError("review snapshot pm_summary candidate_construction_rule does not match artifact review_basis")
        if self.pm_summary.methodology.methodology != self.compact_summary.candidate_analytics.methodology:
            raise ValueError("review snapshot pm_summary methodology does not match artifact candidate analytics methodology")
        if self.pm_summary.methodology.methodology_provenance != self.compact_summary.candidate_analytics.methodology_provenance:
            raise ValueError("review snapshot pm_summary methodology_provenance does not match artifact candidate analytics methodology_provenance")
        if self.pm_summary.assumptions != self.compact_summary.candidate_analytics.assumptions:
            raise ValueError("review snapshot pm_summary assumptions do not match artifact candidate analytics assumptions")
        if self.pm_summary.analytics_summary.candidate_analytics != self.compact_summary.candidate_analytics:
            raise ValueError("review snapshot pm_summary candidate_analytics do not match artifact compact_summary")
        if self.pm_summary.analytics_summary.baseline_analytics != self.compact_summary.baseline_analytics:
            raise ValueError("review snapshot pm_summary baseline_analytics do not match artifact compact_summary")
        if self.pm_summary.analytics_summary.analytics_comparison != self.compact_summary.analytics_comparison:
            raise ValueError("review snapshot pm_summary analytics_comparison does not match artifact compact_summary")
        if self.pm_summary.diagnostics_summary != self.compact_summary.diagnostics_summary:
            raise ValueError("review snapshot pm_summary diagnostics_summary does not match artifact compact_summary")
        return self


class ReviewSnapshotOpenIdentityMismatch(BaseModel):
    requested_artifact_id: str
    persisted_artifact_id: str


class ReviewSnapshotOpenResponse(BaseModel):
    handoff: ReviewSnapshotOpenHandoff
    artifact: ReviewSnapshotArtifact
    pm_summary: ReviewSnapshotPMSummaryEnvelope
    replay_payload: ReviewSnapshotArtifactSourcePayload

    @model_validator(mode="after")
    def _validate_identity(self) -> "ReviewSnapshotOpenResponse":
        if self.handoff.artifact_id != self.artifact.identity.artifact_id:
            raise ValueError("review snapshot handoff artifact_id does not match persisted artifact")
        if self.handoff.artifact_kind != self.artifact.identity.artifact_kind:
            raise ValueError("review snapshot handoff artifact_kind does not match persisted artifact")
        if self.handoff.schema_version != self.artifact.identity.schema_version:
            raise ValueError("review snapshot handoff schema_version does not match persisted artifact")
        if self.handoff.consumer_kind != self.artifact.identity.consumer_kind:
            raise ValueError("review snapshot handoff consumer_kind does not match persisted artifact")
        if self.handoff != self.artifact.proposal_capture.open_handoff:
            raise ValueError("review snapshot open handoff does not match persisted artifact proposal_capture open_handoff")
        if self.pm_summary != self.artifact.pm_summary:
            raise ValueError("review snapshot open pm_summary must match persisted artifact pm_summary")
        if self.replay_payload != self.artifact.source_payload:
            raise ValueError("review snapshot open replay payload must match persisted artifact source payload")
        return self


class ReviewSnapshotComparisonArtifactRef(BaseModel):
    role: ReviewSnapshotComparisonRole
    artifact_id: str
    artifact_kind: ReviewSnapshotArtifactKind = "portfolio_review_snapshot"
    schema_version: ReviewSnapshotArtifactSchemaVersion = "review_snapshot_artifact_v1"
    consumer_kind: ReviewSnapshotConsumerKind = "saved_hypothetical_replay_proposal"


class ReviewSnapshotFamilyKey(BaseModel):
    workspace_id: str
    source_draft_id: str
    source_base_node_id: str
    proposal_family_id: str
    source_kind: ReviewSnapshotSourceKind = "hypothetical_replacement_replay"

    @field_validator("workspace_id", "source_draft_id", "source_base_node_id", "proposal_family_id")
    @classmethod
    def _validate_required_family_key_fields(cls, value: str, info) -> str:
        if not value or not value.strip():
            raise ValueError(f"review snapshot family key {info.field_name} is required")
        return value


def _validate_review_snapshot_family_key_matches_lineage(
    family_key: ReviewSnapshotFamilyKey,
    lineage: ReviewSnapshotArtifactLineage,
    *,
    context: str,
) -> None:
    if lineage.workspace_id != family_key.workspace_id:
        raise ValueError(f"{context} workspace_id does not match family_key")
    if lineage.source_draft_id != family_key.source_draft_id:
        raise ValueError(f"{context} source_draft_id does not match family_key")
    if lineage.source_base_node_id != family_key.source_base_node_id:
        raise ValueError(f"{context} source_base_node_id does not match family_key")
    if lineage.proposal_family_id != family_key.proposal_family_id:
        raise ValueError(f"{context} proposal_family_id does not match family_key")
    if lineage.source_kind != family_key.source_kind:
        raise ValueError(f"{context} source_kind does not match family_key")


class ReviewSnapshotSiblingComparisonEligibility(BaseModel):
    eligible: bool
    reason: Literal["compatible_family_sibling_available", "no_compatible_family_sibling"]
    compatible_sibling_artifact_ids: list[str] = Field(default_factory=list)


class ReviewSnapshotFamilySiblingSummary(BaseModel):
    identity: ReviewSnapshotArtifactIdentity
    open_handoff: ReviewSnapshotOpenHandoff
    lineage: ReviewSnapshotArtifactLineage
    pm_summary: ReviewSnapshotPMSummaryEnvelope
    comparison_eligibility: ReviewSnapshotSiblingComparisonEligibility

    @model_validator(mode="after")
    def _validate_family_sibling_summary(self) -> "ReviewSnapshotFamilySiblingSummary":
        if self.pm_summary.role != "saved_proposal":
            raise ValueError("review snapshot family sibling pm_summary role must be saved_proposal")
        if self.open_handoff.artifact_id != self.identity.artifact_id:
            raise ValueError("review snapshot family sibling open_handoff artifact_id does not match identity")
        if self.open_handoff.artifact_kind != self.identity.artifact_kind:
            raise ValueError("review snapshot family sibling open_handoff artifact_kind does not match identity")
        if self.open_handoff.schema_version != self.identity.schema_version:
            raise ValueError("review snapshot family sibling open_handoff schema_version does not match identity")
        if self.open_handoff.consumer_kind != self.identity.consumer_kind:
            raise ValueError("review snapshot family sibling open_handoff consumer_kind does not match identity")
        if self.lineage != self.pm_summary.provenance.lineage:
            raise ValueError("review snapshot family sibling lineage does not match pm_summary provenance lineage")
        return self


class ReviewSnapshotFamilyCompareReadiness(BaseModel):
    ready: bool
    reason: Literal["compatible_family_pair_available", "no_compatible_family_pair"]
    compatible_pair_count: int = 0

    @model_validator(mode="after")
    def _validate_compare_readiness(self) -> "ReviewSnapshotFamilyCompareReadiness":
        if self.compatible_pair_count < 0:
            raise ValueError("review snapshot family compare readiness compatible_pair_count must be non-negative")
        if self.ready and self.compatible_pair_count < 1:
            raise ValueError("review snapshot family compare readiness requires compatible_pair_count when ready=true")
        if not self.ready and self.compatible_pair_count != 0:
            raise ValueError("review snapshot family compare readiness compatible_pair_count must be zero when ready=false")
        if self.ready and self.reason != "compatible_family_pair_available":
            raise ValueError("review snapshot family compare readiness reason is invalid when ready=true")
        if not self.ready and self.reason != "no_compatible_family_pair":
            raise ValueError("review snapshot family compare readiness reason is invalid when ready=false")
        return self


class ReviewSnapshotFamilyInboxRow(BaseModel):
    family_key: ReviewSnapshotFamilyKey
    latest_identity: ReviewSnapshotArtifactIdentity
    lineage: ReviewSnapshotArtifactLineage
    proposal_capture: ReviewSnapshotProposalCapture
    pm_summary: ReviewSnapshotPMSummaryEnvelope
    sibling_count: int
    compare_readiness: ReviewSnapshotFamilyCompareReadiness
    latest_saved_at: str
    latest_order_provenance: Literal["persisted_artifact_file_mtime"] = "persisted_artifact_file_mtime"

    @model_validator(mode="after")
    def _validate_family_inbox_row(self) -> "ReviewSnapshotFamilyInboxRow":
        if self.sibling_count < 1:
            raise ValueError("review snapshot family inbox row sibling_count must be at least one")
        if self.pm_summary.role != "saved_proposal":
            raise ValueError("review snapshot family inbox row pm_summary role must be saved_proposal")
        if self.lineage != self.pm_summary.provenance.lineage:
            raise ValueError("review snapshot family inbox row lineage does not match pm_summary provenance lineage")
        if self.lineage != self.proposal_capture.lineage:
            raise ValueError("review snapshot family inbox row lineage does not match proposal_capture lineage")
        if self.proposal_capture.open_handoff.artifact_id != self.latest_identity.artifact_id:
            raise ValueError("review snapshot family inbox row proposal_capture open_handoff artifact_id does not match latest identity")
        if self.proposal_capture.open_handoff.artifact_kind != self.latest_identity.artifact_kind:
            raise ValueError("review snapshot family inbox row proposal_capture open_handoff artifact_kind does not match latest identity")
        if self.proposal_capture.open_handoff.schema_version != self.latest_identity.schema_version:
            raise ValueError("review snapshot family inbox row proposal_capture open_handoff schema_version does not match latest identity")
        if self.proposal_capture.open_handoff.consumer_kind != self.latest_identity.consumer_kind:
            raise ValueError("review snapshot family inbox row proposal_capture open_handoff consumer_kind does not match latest identity")
        if self.pm_summary.provenance.proposal_source != self.proposal_capture.proposal.proposal_source:
            raise ValueError("review snapshot family inbox row proposal_source does not match proposal_capture")
        if self.pm_summary.review_basis != ReviewSnapshotPMSummaryReviewBasis(
            benchmark_symbol=self.proposal_capture.review_basis.benchmark_symbol,
            replay_window=self.proposal_capture.review_basis.replay_window,
            rebalance_frequency=self.proposal_capture.review_basis.rebalance_frequency,
            commission_bps=self.proposal_capture.review_basis.commission_bps,
            slippage_bps=self.proposal_capture.review_basis.slippage_bps,
            derivation_basis=self.proposal_capture.review_basis.derivation_basis,
            candidate_construction_rule=self.proposal_capture.review_basis.candidate_construction_rule,
        ):
            raise ValueError("review snapshot family inbox row pm_summary review_basis does not match proposal_capture review_basis")
        _validate_review_snapshot_family_key_matches_lineage(
            self.family_key,
            self.lineage,
            context="review snapshot family inbox row",
        )
        if not self.latest_saved_at:
            raise ValueError("review snapshot family inbox row latest_saved_at is required")
        return self


class ReviewSnapshotComparisonMethodology(BaseModel):
    methodology: str
    methodology_provenance: "ReplayMethodologyProvenance"
    assumptions: AllocationBacktestAssumptions


class ReviewSnapshotComparisonPairSummary(BaseModel):
    benchmark_symbol: str
    replay_window: WorkspaceReviewWindow
    replay_type: Literal["standard", "overlay_aware"]
    candidate_construction_rule: HypotheticalReplayConstructionRuleId
    derivation_basis: HypotheticalReplayBaselineBasis
    source_pair: str
    replay_status: AllocationBacktestStatus
    investor_economics_status: InvestorEconomicsStatus
    methodology: ReviewSnapshotComparisonMethodology
    analytics: ReviewSnapshotArtifactAnalyticsSummary
    diagnostics_summary: ReviewSnapshotArtifactDiagnosticsSummary


class ReviewSnapshotComparisonMethodologyEnvelope(BaseModel):
    baseline_methodology: ReviewSnapshotComparisonMethodology
    candidate_methodology: ReviewSnapshotComparisonMethodology
    assumptions_consistent: bool
    methodology_consistent: bool


class ReviewSnapshotComparisonAssumptionsEnvelope(BaseModel):
    baseline_assumptions: AllocationBacktestAssumptions
    candidate_assumptions: AllocationBacktestAssumptions
    assumptions_consistent: bool


class ReviewSnapshotComparisonResponse(BaseModel):
    comparison_kind: ReviewSnapshotComparisonConsumerKind = "review_snapshot_comparison"
    family_key: ReviewSnapshotFamilyKey
    baseline: ReviewSnapshotComparisonPairSummary
    candidate: ReviewSnapshotComparisonPairSummary
    provenance: Literal["persisted_review_snapshot_artifacts_only"] = "persisted_review_snapshot_artifacts_only"
    benchmark_separation: Literal["explicit_per_snapshot_benchmark_fields"] = "explicit_per_snapshot_benchmark_fields"
    baseline_pm_summary: ReviewSnapshotPMSummaryEnvelope
    candidate_pm_summary: ReviewSnapshotPMSummaryEnvelope
    analytics_comparison: AllocationBacktestComparison | None = None
    methodology: ReviewSnapshotComparisonMethodologyEnvelope
    assumptions: ReviewSnapshotComparisonAssumptionsEnvelope

    @model_validator(mode="after")
    def _validate_pm_summary_roles(self) -> "ReviewSnapshotComparisonResponse":
        if self.baseline_pm_summary.role != "baseline":
            raise ValueError("review snapshot comparison baseline_pm_summary role must be baseline")
        if self.candidate_pm_summary.role != "candidate":
            raise ValueError("review snapshot comparison candidate_pm_summary role must be candidate")
        if self.baseline_pm_summary.review_basis.benchmark_symbol != self.baseline.benchmark_symbol:
            raise ValueError("review snapshot comparison baseline_pm_summary benchmark_symbol does not match baseline summary")
        if self.candidate_pm_summary.review_basis.benchmark_symbol != self.candidate.benchmark_symbol:
            raise ValueError("review snapshot comparison candidate_pm_summary benchmark_symbol does not match candidate summary")
        if self.baseline_pm_summary.review_basis.replay_window != self.baseline.replay_window:
            raise ValueError("review snapshot comparison baseline_pm_summary replay_window does not match baseline summary")
        if self.candidate_pm_summary.review_basis.replay_window != self.candidate.replay_window:
            raise ValueError("review snapshot comparison candidate_pm_summary replay_window does not match candidate summary")
        if self.baseline_pm_summary.review_basis.candidate_construction_rule != self.baseline.candidate_construction_rule:
            raise ValueError("review snapshot comparison baseline_pm_summary candidate_construction_rule does not match baseline summary")
        if self.candidate_pm_summary.review_basis.candidate_construction_rule != self.candidate.candidate_construction_rule:
            raise ValueError("review snapshot comparison candidate_pm_summary candidate_construction_rule does not match candidate summary")
        if self.baseline_pm_summary.review_basis.derivation_basis != self.baseline.derivation_basis:
            raise ValueError("review snapshot comparison baseline_pm_summary derivation_basis does not match baseline summary")
        if self.candidate_pm_summary.review_basis.derivation_basis != self.candidate.derivation_basis:
            raise ValueError("review snapshot comparison candidate_pm_summary derivation_basis does not match candidate summary")
        if self.baseline_pm_summary.methodology.methodology != self.methodology.baseline_methodology.methodology:
            raise ValueError("review snapshot comparison baseline_pm_summary methodology does not match methodology envelope")
        if self.candidate_pm_summary.methodology.methodology != self.methodology.candidate_methodology.methodology:
            raise ValueError("review snapshot comparison candidate_pm_summary methodology does not match methodology envelope")
        if self.baseline_pm_summary.assumptions != self.assumptions.baseline_assumptions:
            raise ValueError("review snapshot comparison baseline_pm_summary assumptions do not match assumptions envelope")
        if self.candidate_pm_summary.assumptions != self.assumptions.candidate_assumptions:
            raise ValueError("review snapshot comparison candidate_pm_summary assumptions do not match assumptions envelope")
        _validate_review_snapshot_family_key_matches_lineage(
            self.family_key,
            self.baseline_pm_summary.provenance.lineage,
            context="review snapshot comparison baseline_pm_summary",
        )
        _validate_review_snapshot_family_key_matches_lineage(
            self.family_key,
            self.candidate_pm_summary.provenance.lineage,
            context="review snapshot comparison candidate_pm_summary",
        )
        return self


class ReviewSnapshotFamilyReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff: ReviewSnapshotOpenHandoff


class ReviewSnapshotFamilyInboxRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workspace_id: str


class ReviewSnapshotFamilyInboxResponse(BaseModel):
    inbox_kind: ReviewSnapshotFamilyInboxConsumerKind = "review_snapshot_family_inbox"
    workspace_id: str
    provenance: Literal["persisted_review_snapshot_artifacts_only"] = "persisted_review_snapshot_artifacts_only"
    rows: list[ReviewSnapshotFamilyInboxRow]

    @model_validator(mode="after")
    def _validate_family_inbox(self) -> "ReviewSnapshotFamilyInboxResponse":
        seen_family_keys: set[tuple[str, str, str, str, str]] = set()
        for row in self.rows:
            if row.family_key.workspace_id != self.workspace_id:
                raise ValueError("review snapshot family inbox row workspace_id does not match response workspace_id")
            family_key = (
                row.family_key.workspace_id,
                row.family_key.source_draft_id,
                row.family_key.source_base_node_id,
                row.family_key.proposal_family_id,
                row.family_key.source_kind,
            )
            if family_key in seen_family_keys:
                raise ValueError("review snapshot family inbox response contains duplicate family_key rows")
            seen_family_keys.add(family_key)
        return self


class ReviewSnapshotActiveThesisCrossFamilyQueueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_proposal_id: str
    handoff: ReviewSnapshotOpenHandoff


class ReviewSnapshotActiveThesisCrossFamilySeparation(BaseModel):
    separation_kind: Literal["distinct_proposal_family_id"] = "distinct_proposal_family_id"
    active_thesis_proposal_family_id: str
    queue_proposal_family_id: str

    @model_validator(mode="after")
    def _validate_family_separation(self) -> "ReviewSnapshotActiveThesisCrossFamilySeparation":
        if self.active_thesis_proposal_family_id == self.queue_proposal_family_id:
            raise ValueError("review snapshot active thesis cross-family queue requires distinct proposal_family_id values")
        return self


class ReviewSnapshotActiveThesisCrossFamilyTrustVisibility(BaseModel):
    investor_economics_status: InvestorEconomicsStatus
    benchmark_separation: Literal["explicit_per_snapshot_benchmark_fields"] = "explicit_per_snapshot_benchmark_fields"


class ReviewSnapshotActiveThesisCrossFamilyPMSummaryFields(BaseModel):
    replay_type: Literal["standard", "overlay_aware"]
    replay_status: AllocationBacktestStatus
    review_basis: ReviewSnapshotPMSummaryReviewBasis
    methodology: ReviewSnapshotPMSummaryMethodology
    assumptions: AllocationBacktestAssumptions
    analytics_summary: ReviewSnapshotPMSummaryAnalyticsSummary
    diagnostics_summary: ReviewSnapshotArtifactDiagnosticsSummary


class ReviewSnapshotActiveThesisCrossFamilyQueueRow(BaseModel):
    latest_identity: ReviewSnapshotArtifactIdentity
    lineage: ReviewSnapshotArtifactLineage
    family_key: ReviewSnapshotFamilyKey
    family_separation: ReviewSnapshotActiveThesisCrossFamilySeparation
    proposal_source: HypotheticalReplayProposalSource
    truth_labels: ReviewSnapshotArtifactTruthLabels
    trust_visibility: ReviewSnapshotActiveThesisCrossFamilyTrustVisibility
    pm_summary_fields: ReviewSnapshotActiveThesisCrossFamilyPMSummaryFields
    latest_saved_at: str
    queue_order_provenance: Literal["persisted_artifact_file_mtime_desc_then_artifact_id_desc"] = "persisted_artifact_file_mtime_desc_then_artifact_id_desc"

    @model_validator(mode="after")
    def _validate_cross_family_queue_row(self) -> "ReviewSnapshotActiveThesisCrossFamilyQueueRow":
        _validate_review_snapshot_family_key_matches_lineage(
            self.family_key,
            self.lineage,
            context="review snapshot active thesis cross-family queue row",
        )
        if self.family_separation.queue_proposal_family_id != self.family_key.proposal_family_id:
            raise ValueError("review snapshot active thesis cross-family queue row family_separation queue_proposal_family_id does not match family_key")
        if self.latest_identity.artifact_id == "":
            raise ValueError("review snapshot active thesis cross-family queue row latest_identity artifact_id is required")
        if self.trust_visibility.benchmark_separation != self.pm_summary_fields.review_basis.benchmark_separation:
            raise ValueError("review snapshot active thesis cross-family queue row benchmark_separation does not match pm_summary_fields review_basis")
        if not self.latest_saved_at:
            raise ValueError("review snapshot active thesis cross-family queue row latest_saved_at is required")
        return self


class ReviewSnapshotActiveThesisCrossFamilyQueueActiveThesis(BaseModel):
    source_proposal_id: str
    handoff: ReviewSnapshotOpenHandoff
    identity: ReviewSnapshotArtifactIdentity
    lineage: ReviewSnapshotArtifactLineage
    family_key: ReviewSnapshotFamilyKey

    @model_validator(mode="after")
    def _validate_active_thesis_context(self) -> "ReviewSnapshotActiveThesisCrossFamilyQueueActiveThesis":
        if self.source_proposal_id != self.lineage.proposal_id:
            raise ValueError("review snapshot active thesis cross-family queue source_proposal_id does not match active thesis lineage proposal_id")
        if self.handoff.artifact_id != self.identity.artifact_id:
            raise ValueError("review snapshot active thesis cross-family queue handoff artifact_id does not match active thesis identity")
        if self.handoff.artifact_kind != self.identity.artifact_kind:
            raise ValueError("review snapshot active thesis cross-family queue handoff artifact_kind does not match active thesis identity")
        if self.handoff.schema_version != self.identity.schema_version:
            raise ValueError("review snapshot active thesis cross-family queue handoff schema_version does not match active thesis identity")
        if self.handoff.consumer_kind != self.identity.consumer_kind:
            raise ValueError("review snapshot active thesis cross-family queue handoff consumer_kind does not match active thesis identity")
        _validate_review_snapshot_family_key_matches_lineage(
            self.family_key,
            self.lineage,
            context="review snapshot active thesis cross-family queue active thesis",
        )
        return self


class ReviewSnapshotFamilyReviewResponse(BaseModel):
    review_kind: ReviewSnapshotFamilyReviewConsumerKind = "review_snapshot_family_review"
    family_key: ReviewSnapshotFamilyKey
    provenance: Literal["persisted_review_snapshot_artifacts_only"] = "persisted_review_snapshot_artifacts_only"
    compare_selection_policy: Literal["exactly_two_distinct_family_siblings"] = "exactly_two_distinct_family_siblings"
    anchor: ReviewSnapshotFamilySiblingSummary
    siblings: list[ReviewSnapshotFamilySiblingSummary]

    @model_validator(mode="after")
    def _validate_family_review(self) -> "ReviewSnapshotFamilyReviewResponse":
        if not self.siblings:
            raise ValueError("review snapshot family review requires at least one sibling")
        if not any(sibling.identity.artifact_id == self.anchor.identity.artifact_id for sibling in self.siblings):
            raise ValueError("review snapshot family review anchor must be present in siblings")
        _validate_review_snapshot_family_key_matches_lineage(
            self.family_key,
            self.anchor.lineage,
            context="review snapshot family review anchor",
        )
        for sibling in self.siblings:
            _validate_review_snapshot_family_key_matches_lineage(
                self.family_key,
                sibling.lineage,
                context="review snapshot family review sibling",
            )
        return self


class ReviewSnapshotActiveThesisCrossFamilyQueueResponse(BaseModel):
    queue_kind: ReviewSnapshotActiveThesisCrossFamilyQueueConsumerKind = "review_snapshot_active_thesis_cross_family_queue"
    provenance: Literal["persisted_review_snapshot_artifacts_and_active_thesis_reference_only"] = "persisted_review_snapshot_artifacts_and_active_thesis_reference_only"
    queue_ordering: Literal["latest_saved_at_desc_then_artifact_id_desc"] = "latest_saved_at_desc_then_artifact_id_desc"
    active_thesis: ReviewSnapshotActiveThesisCrossFamilyQueueActiveThesis
    rows: list[ReviewSnapshotActiveThesisCrossFamilyQueueRow]

    @model_validator(mode="after")
    def _validate_active_thesis_cross_family_queue(self) -> "ReviewSnapshotActiveThesisCrossFamilyQueueResponse":
        seen_family_keys: set[tuple[str, str, str, str, str]] = set()
        seen_artifact_ids: set[str] = set()
        previous_order: tuple[str, str] | None = None
        for row in self.rows:
            family_key = (
                row.family_key.workspace_id,
                row.family_key.source_draft_id,
                row.family_key.source_base_node_id,
                row.family_key.proposal_family_id,
                row.family_key.source_kind,
            )
            if family_key in seen_family_keys:
                raise ValueError("review snapshot active thesis cross-family queue contains duplicate family_key rows")
            seen_family_keys.add(family_key)
            if row.latest_identity.artifact_id in seen_artifact_ids:
                raise ValueError("review snapshot active thesis cross-family queue contains duplicate canonical row identities")
            seen_artifact_ids.add(row.latest_identity.artifact_id)
            if row.family_key.workspace_id != self.active_thesis.family_key.workspace_id:
                raise ValueError("review snapshot active thesis cross-family queue row workspace_id does not match active thesis workspace_id")
            if row.family_key.source_draft_id != self.active_thesis.family_key.source_draft_id:
                raise ValueError("review snapshot active thesis cross-family queue row source_draft_id does not match active thesis source_draft_id")
            if row.family_key.source_base_node_id != self.active_thesis.family_key.source_base_node_id:
                raise ValueError("review snapshot active thesis cross-family queue row source_base_node_id does not match active thesis source_base_node_id")
            if row.family_key.source_kind != self.active_thesis.family_key.source_kind:
                raise ValueError("review snapshot active thesis cross-family queue row source_kind does not match active thesis source_kind")
            if row.family_key.proposal_family_id == self.active_thesis.family_key.proposal_family_id:
                raise ValueError("review snapshot active thesis cross-family queue row proposal_family_id must stay distinct from active thesis family")
            if row.family_separation.active_thesis_proposal_family_id != self.active_thesis.family_key.proposal_family_id:
                raise ValueError("review snapshot active thesis cross-family queue row active thesis proposal_family_id does not match active thesis family")
            current_order = (row.latest_saved_at, row.latest_identity.artifact_id)
            if previous_order is not None and current_order > previous_order:
                raise ValueError("review snapshot active thesis cross-family queue ordering is invalid")
            previous_order = current_order
        return self


ReviewSnapshotOpenRequest: TypeAlias = ReviewSnapshotOpenHandoff


class ReviewSnapshotOpenRequestEnvelope(RootModel[ReviewSnapshotOpenRequest]):
    pass


class ReviewSnapshotComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    baseline: ReviewSnapshotComparisonArtifactRef | ReviewSnapshotOpenHandoff
    candidate: ReviewSnapshotComparisonArtifactRef | ReviewSnapshotOpenHandoff


class ReviewSnapshotCreateRequest(BaseModel):
    proposal_id: str
    workspace_id: str
    source_draft_id: str
    source_base_node_id: str
    proposal_family_id: str
    version_number: int
    review_payload: HypotheticalReplacementReplayResponse | OverlayAwareHypotheticalReplayResponse


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
    review_basis: "ConstructionArtifactWorkspaceReviewBasis"
    replay_provenance: ConstructionArtifactReplayProvenance
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    effective_replay_params: ConstructionArtifactReplayEffectiveParams
    replay: PortfolioAllocationBacktestResponse

    @model_validator(mode="after")
    def _validate_review_basis_identity(self) -> "ConstructionArtifactReplayResponse":
        if self.review_basis.construction_artifact_id != self.construction_artifact_id:
            raise ValueError("review_basis.construction_artifact_id must match construction_artifact_id")
        if self.review_basis.preview_handoff.effective_replay_params != self.effective_replay_params:
            raise ValueError("review_basis.preview_handoff.effective_replay_params must match effective_replay_params")
        return self


class ConstructionArtifactPreviewHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: Literal["construction_artifact_preview_handoff_v1"] = "construction_artifact_preview_handoff_v1"
    construction_artifact_id: str
    effective_replay_params: ConstructionArtifactReplayEffectiveParams


class WorkspaceReviewWindow(BaseModel):
    start_date: str | None = None
    end_date: str | None = None


class ConstructionArtifactWorkspaceReviewBasis(BaseModel):
    basis_version: Literal[1] = 1
    basis_kind: Literal["persisted_construction_artifact_review"] = "persisted_construction_artifact_review"
    review_scope: Literal["workspace_review_only"] = "workspace_review_only"
    canonical_source: Literal["typed_preview_handoff"] = "typed_preview_handoff"
    basis_provenance_label: Literal["artifact_backed_review_basis"] = "artifact_backed_review_basis"
    portfolio_truth: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    candidate_truth: Literal["hypothetical_construction_artifact"] = "hypothetical_construction_artifact"
    construction_artifact_id: str
    preview_handoff: ConstructionArtifactPreviewHandoff
    benchmark_symbol: str | None = None
    base_currency: str | None = None
    replay_window: WorkspaceReviewWindow
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_preview_handoff_identity(self) -> "ConstructionArtifactWorkspaceReviewBasis":
        if self.preview_handoff.construction_artifact_id != self.construction_artifact_id:
            raise ValueError("review_basis.preview_handoff.construction_artifact_id must match construction_artifact_id")
        return self


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
    replay_handoff: "OptimizerHandoffReplayHandoff | None" = None
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


class OptimizerHandoffReplayEffectiveParams(BaseModel):
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


class OptimizerHandoffReplayHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: Literal["optimizer_handoff_replay_handoff_v1"] = "optimizer_handoff_replay_handoff_v1"
    handoff_reference: OptimizerPersistedArtifactReference
    effective_replay_params: OptimizerHandoffReplayEffectiveParams


OptimizerHandoffPreviewRequest: TypeAlias = OptimizerHandoffReplayHandoff | OptimizerHandoffReplayRequest


class OptimizerHandoffPreviewOpenRequest(RootModel[OptimizerHandoffPreviewRequest]):
    @model_validator(mode="before")
    @classmethod
    def _validate_preview_request_shape(cls, value):
        if not isinstance(value, dict):
            return value
        if "handoff_kind" not in value and "effective_replay_params" not in value:
            return value
        if value.get("handoff_kind") != "optimizer_handoff_replay_handoff_v1":
            raise ValueError(f"unsupported replay_handoff.handoff_kind: {value.get('handoff_kind')}")
        mixed_legacy_fields = set(value) - {"handoff_kind", "handoff_reference", "effective_replay_params"}
        if mixed_legacy_fields:
            raise ValueError("replay_handoff request must not mix legacy replay override fields")
        return value


class OptimizerHandoffWorkspaceReviewBasis(BaseModel):
    basis_version: Literal[1] = 1
    basis_kind: Literal["persisted_optimizer_handoff_review"] = "persisted_optimizer_handoff_review"
    review_scope: Literal["workspace_review_only"] = "workspace_review_only"
    canonical_source: Literal["persisted_handoff_reference"] = "persisted_handoff_reference"
    basis_provenance_label: Literal["artifact_backed_review_basis"] = "artifact_backed_review_basis"
    portfolio_truth: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    candidate_truth: Literal["hypothetical_optimizer_handoff"] = "hypothetical_optimizer_handoff"
    handoff_reference: OptimizerPersistedArtifactReference
    benchmark_symbol: str | None = None
    base_currency: str | None = None
    replay_window: "WorkspaceReviewWindow"
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)


class OptimizerHandoffReplayResponse(BaseModel):
    handoff_id: str
    artifact_id: str = Field(deprecated=True)
    source_portfolio_snapshot_id: str
    truth_separation: OptimizerHandoffReplayTruthSeparation = Field(default_factory=OptimizerHandoffReplayTruthSeparation)
    review_basis: OptimizerHandoffWorkspaceReviewBasis
    replay_provenance: OptimizerHandoffReplayProvenance
    optimizer_context: OptimizerHandoffReplayOptimizerContext | None = None
    baseline_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    candidate_weights: list[PortfolioWeightInput] = Field(default_factory=list)
    replay: PortfolioAllocationBacktestResponse

    @model_validator(mode="after")
    def _validate_review_basis_identity(self) -> "OptimizerHandoffReplayResponse":
        artifact_id = self.__dict__.get("artifact_id")
        if self.review_basis.handoff_reference.handoff_id != self.handoff_id:
            raise ValueError("review_basis.handoff_reference.handoff_id must match handoff_id")
        if self.review_basis.handoff_reference.artifact_id != artifact_id:
            raise ValueError("review_basis.handoff_reference.artifact_id must match artifact_id")
        return self


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
MonitorDefinitionCanonicalCauseCode = Literal[
    "benchmark_observation_unconfirmed",
    "benchmark_observation_unavailable",
    "portfolio_truth_non_positive_total_value",
]


def _allowed_monitor_definition_cause_codes_for_status(
    observation_status: MonitorDefinitionObservationStatus,
) -> frozenset[str]:
    if observation_status == "degraded":
        return frozenset({"benchmark_observation_unconfirmed"})
    if observation_status == "unavailable":
        return frozenset(
            {
                "benchmark_observation_unavailable",
                "portfolio_truth_non_positive_total_value",
            }
        )
    return frozenset()


def _expected_monitor_definition_escalation_status(
    observation_status: MonitorDefinitionObservationStatus,
) -> str:
    if observation_status == "ok":
        return "informational"
    if observation_status == "threshold_breach":
        return "action_required"
    if observation_status == "degraded":
        return "degraded"
    return "unavailable"


def _validate_monitor_definition_cause_code_contract(
    observation_status: MonitorDefinitionObservationStatus,
    cause_code: MonitorDefinitionCanonicalCauseCode | None,
) -> None:
    allowed_cause_codes = _allowed_monitor_definition_cause_codes_for_status(observation_status)
    if not allowed_cause_codes:
        if cause_code is not None:
            raise ValueError("cause_code must be null unless observation_status is degraded or unavailable")
        return
    if cause_code is None:
        raise ValueError("cause_code is required when observation_status is degraded or unavailable")
    if cause_code not in allowed_cause_codes:
        raise ValueError("cause_code is unsupported for the supplied observation_status")


def _validate_monitor_definition_escalation_contract(
    observation_status: MonitorDefinitionObservationStatus,
    escalation_status: str,
    *,
    field_name: str,
) -> None:
    expected = _expected_monitor_definition_escalation_status(observation_status)
    if escalation_status != expected:
        raise ValueError(f"{field_name} must match the canonical observation_status escalation mapping")


def _validate_monitor_definition_hysteresis_transition_contract(
    escalation_status: str,
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None,
    *,
    field_name: str,
) -> None:
    if hysteresis_transition is None:
        return
    alert_eligible = escalation_status != "informational"
    allowed = (
        frozenset({"open", "remain_open"})
        if alert_eligible
        else frozenset({"recover", "no_op"})
    )
    if hysteresis_transition not in allowed:
        raise ValueError(
            f"{field_name} must remain consistent with the canonical alert lifecycle transition mapping"
        )


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
MonitorDefinitionLatestObservationStatus = Literal["present", "absent"]
MonitorDefinitionLatestObservationRecency = Literal["recent", "stale"]
MonitorDefinitionLatestEvaluationSnapshotStatus = Literal["present", "absent"]
MonitorDefinitionLatestEvaluationSnapshotRecency = Literal["recent", "stale"]
MonitorDefinitionObservationArtifactSchemaVersion = Literal[
    "monitor_definition_observation_artifact_v1"
]
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
MonitorDefinitionAlertClassification = Literal[
    "informational",
    "action_required",
    "degraded",
    "unavailable",
]
MonitorDefinitionLatestEvaluationSignificanceStatus = MonitorDefinitionAlertClassification
MonitorDefinitionHysteresisTransition = Literal[
    "open",
    "remain_open",
    "recover",
    "no_op",
]
MonitorDefinitionMonitoringSourcePrecedence = Literal[
    "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry",
    "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_persisted_observation_artifact",
    "persisted_evaluation_history_entry_only",
    "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot",
    "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries",
    "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries",
    "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation",
    "persisted_observation_artifact_then_persisted_evaluation_history_entries_then_persisted_latest_alert_episode_projection",
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
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence | None = None
    benchmark_observation_lineage: MonitorDefinitionLatestEvaluationBenchmarkObservationLineage
    portfolio_truth_basis: MonitorDefinitionLatestEvaluationPortfolioTruthBasis

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_cause_and_significance(self) -> "MonitorDefinitionLatestEvaluationSnapshotArtifact":
        _validate_monitor_definition_cause_code_contract(self.outcome_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.outcome_status,
            self.significance_status,
            field_name="significance_status",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.significance_status,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


class MonitorDefinitionDiscoveryFilters(BaseModel):
    overlay_family: MonitorDefinitionOverlayFamily | None = None
    monitor_id: Literal["benchmark_trend_overlay_v1"] | None = None
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus | None = None
    lifecycle_status: MonitorDefinitionDiscoveryLifecycleStatus | None = None
    latest_observation_status: MonitorDefinitionLatestObservationStatus | None = None
    latest_observation_observation_status: MonitorDefinitionObservationStatus | None = None
    latest_observation_alert_classification: MonitorDefinitionAlertClassification | None = None
    latest_observation_cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    latest_observation_recency: MonitorDefinitionLatestObservationRecency | None = None
    latest_evaluation_snapshot_status: MonitorDefinitionLatestEvaluationSnapshotStatus | None = None
    latest_evaluation_snapshot_cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    latest_evaluation_snapshot_recency: MonitorDefinitionLatestEvaluationSnapshotRecency | None = None


class MonitorDefinitionLifecycleStatusMetadata(BaseModel):
    overlay_family: MonitorDefinitionOverlayFamily = "benchmark_trend"
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus = "review_supported"
    lifecycle_status: MonitorDefinitionDiscoveryLifecycleStatus = "enabled"


class MonitorDefinitionLatestEvaluationSnapshotSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluated_at: datetime
    outcome_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    recency_status: MonitorDefinitionLatestEvaluationSnapshotRecency
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence

    @model_validator(mode="after")
    def _validate_summary_contract(self) -> "MonitorDefinitionLatestEvaluationSnapshotSummary":
        _validate_monitor_definition_cause_code_contract(self.outcome_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.outcome_status,
            self.significance_status,
            field_name="significance_status",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.significance_status,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


class MonitorDefinitionLatestObservationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    evaluated_at: datetime
    observation_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    alert_classification: MonitorDefinitionAlertClassification
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    recency_status: MonitorDefinitionLatestObservationRecency
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence

    @model_validator(mode="after")
    def _validate_summary_contract(self) -> "MonitorDefinitionLatestObservationSummary":
        _validate_monitor_definition_cause_code_contract(self.observation_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.observation_status,
            self.alert_classification,
            field_name="alert_classification",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.alert_classification,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


class MonitorDefinitionStatusMetadata(BaseModel):
    lifecycle: MonitorDefinitionLifecycleStatusMetadata = Field(
        default_factory=MonitorDefinitionLifecycleStatusMetadata
    )
    status_source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot"
    )
    latest_observation_status: MonitorDefinitionLatestObservationStatus = "absent"
    latest_observation: MonitorDefinitionLatestObservationSummary | None = None
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


MonitorDefinitionLatestObservationAlertInboxContractVersion = Literal[
    "monitor_definition_latest_observation_alert_inbox_v1"
]
MonitorDefinitionLatestObservationAlertInboxProvenance = Literal[
    "authoritative_persisted_monitor_definition_observations_only"
]
MonitorDefinitionLatestObservationAlertInboxRowProvenance = Literal[
    "persisted_monitor_definition_observation_artifact"
]
MonitorDefinitionLatestObservationAlertInboxOrdering = Literal["newest_first_evaluated_at"]
MonitorDefinitionObservationOpenHandoffKind = Literal[
    "monitor_definition_observation_open_handoff_v1"
]
MonitorDefinitionAlertHistoryQueueContractVersion = Literal[
    "monitor_definition_alert_history_queue_v1"
]
MonitorDefinitionAlertHistoryQueueProvenance = Literal[
    "persisted_monitor_definitions_with_canonical_latest_snapshot_and_evaluation_history"
]
MonitorDefinitionAlertHistoryQueueRowProvenance = Literal[
    "persisted_monitor_definition_evaluation_history_entry_with_latest_snapshot_precedence"
]
MonitorDefinitionAlertHistoryQueueOrdering = Literal[
    "newest_first_evaluated_at_then_latest_snapshot_precedence_then_monitor_definition_id_then_history_entry_id"
]
MonitorDefinitionEvaluationHistoryReviewHandoffKind = Literal[
    "monitor_definition_evaluation_history_review_handoff_v1"
]
MonitorDefinitionRecoveredAlertReviewQueueContractVersion = Literal[
    "monitor_definition_recovered_alert_review_queue_v1"
]
MonitorDefinitionRecoveredAlertReviewQueueProvenance = Literal[
    "persisted_latest_observation_with_latest_snapshot_and_prior_alert_history_lineage"
]
MonitorDefinitionRecoveredAlertReviewQueueRowProvenance = Literal[
    "persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage"
]
MonitorDefinitionRecoveredAlertReviewQueueOrdering = Literal[
    "newest_first_evaluated_at_then_monitor_definition_id_then_observation_id"
]
MonitorDefinitionAlertReviewTimelineOpenHandoffKind = Literal[
    "monitor_definition_alert_review_timeline_open_handoff_v1"
]
MonitorDefinitionAlertReviewTimelineContractVersion = Literal[
    "monitor_definition_alert_review_timeline_v1"
]
MonitorDefinitionAlertEpisodeContractVersion = Literal[
    "monitor_definition_alert_episode_v1"
]
MonitorDefinitionAlertEpisodeStatus = Literal["active", "recovered"]
MonitorDefinitionAlertEpisodeRecordSchemaVersion = Literal[
    "monitor_definition_alert_episode_record_v1"
]
MonitorDefinitionAlertEpisodeLifecycleStatus = Literal["open", "recovered", "closed"]
MonitorDefinitionAlertEpisodeHistoryContractVersion = Literal[
    "monitor_definition_alert_episode_history_v1"
]
MonitorDefinitionAlertEpisodeHistoryTruth = Literal[
    "authoritative_persisted_monitor_definition_alert_episode_history"
]
MonitorDefinitionAlertEpisodeHistoryRowProvenance = Literal[
    "persisted_monitor_definition_alert_episode_record"
]
MonitorDefinitionAlertEpisodeHistoryOrdering = Literal[
    "newest_first_latest_event_at_then_episode_id"
]
MonitorDefinitionAlertEpisodeHistoryWindowing = Literal[
    "before_episode_id_exclusive"
]
MonitorDefinitionActiveAlertEpisodeInboxContractVersion = Literal[
    "monitor_definition_active_alert_episode_inbox_v1"
]
MonitorDefinitionActiveAlertEpisodeInboxProvenance = Literal[
    "authoritative_persisted_monitor_definition_alert_episode_records_only"
]
MonitorDefinitionActiveAlertEpisodeInboxRowProvenance = Literal[
    "persisted_monitor_definition_alert_episode_record"
]
MonitorDefinitionActiveAlertEpisodeInboxOrdering = Literal[
    "newest_first_latest_event_at_then_monitor_definition_id_then_episode_id"
]
MonitorDefinitionActiveAlertEpisodeInboxWindowing = Literal[
    "before_episode_id_exclusive"
]
MonitorDefinitionAlertEpisodeHistoryTimelineHandoffKind = Literal[
    "monitor_definition_alert_episode_history_timeline_handoff_v1"
]
MonitorDefinitionAlertReviewTimelineProvenance = Literal[
    "canonical_latest_observation_artifact_and_append_only_evaluation_history_entries"
]
MonitorDefinitionAlertReviewTimelineOrdering = Literal[
    "newest_first_evaluated_at_then_observation_event_then_history_entry_id"
]
MonitorDefinitionAlertReviewTimelineEventKind = Literal[
    "latest_observation_event",
    "evaluation_history_event",
]
MonitorDefinitionAlertReviewTimelineEventSemantics = Literal[
    "observation_rooted",
    "history_entry_rooted",
]


class MonitorDefinitionObservationOpenHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: MonitorDefinitionObservationOpenHandoffKind = (
        "monitor_definition_observation_open_handoff_v1"
    )
    monitor_definition_id: str
    observation_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str


class MonitorDefinitionEvaluationHistoryReviewHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: MonitorDefinitionEvaluationHistoryReviewHandoffKind = (
        "monitor_definition_evaluation_history_review_handoff_v1"
    )
    monitor_definition_id: str
    history_entry_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str


class MonitorDefinitionAlertReviewTimelineOpenHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: MonitorDefinitionAlertReviewTimelineOpenHandoffKind = (
        "monitor_definition_alert_review_timeline_open_handoff_v1"
    )
    monitor_definition_id: str
    selected_event_kind: Literal["latest_observation_event"] = "latest_observation_event"
    observation_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str


class MonitorDefinitionAlertEpisodeHistoryTimelineHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    handoff_kind: MonitorDefinitionAlertEpisodeHistoryTimelineHandoffKind = (
        "monitor_definition_alert_episode_history_timeline_handoff_v1"
    )
    monitor_definition_id: str
    selected_event_kind: MonitorDefinitionAlertReviewTimelineEventKind
    observation_id: str | None = None
    history_entry_id: str | None = None
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str

    @model_validator(mode="after")
    def _validate_selected_event_identity(
        self,
    ) -> "MonitorDefinitionAlertEpisodeHistoryTimelineHandoff":
        if self.selected_event_kind == "latest_observation_event":
            if self.observation_id is None:
                raise ValueError(
                    "latest_observation_event timeline handoff must define observation_id"
                )
            if self.history_entry_id is not None:
                raise ValueError(
                    "latest_observation_event timeline handoff must not define history_entry_id"
                )
        else:
            if self.history_entry_id is None:
                raise ValueError(
                    "evaluation_history_event timeline handoff must define history_entry_id"
                )
            if self.observation_id is not None:
                raise ValueError(
                    "evaluation_history_event timeline handoff must not define observation_id"
                )
        return self


class MonitorDefinitionAlertEpisodeLatestContributingObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    evaluated_at: datetime
    observation_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    alert_classification: MonitorDefinitionAlertClassification

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_contract(
        self,
    ) -> "MonitorDefinitionAlertEpisodeLatestContributingObservation":
        _validate_monitor_definition_cause_code_contract(
            self.observation_status,
            self.cause_code,
        )
        _validate_monitor_definition_escalation_contract(
            self.observation_status,
            self.alert_classification,
            field_name="alert_classification",
        )
        return self


class MonitorDefinitionAlertEpisodeRecoveryBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recovered_from_history_entry_id: str
    recovered_from_evaluated_at: datetime
    recovered_from_outcome_status: MonitorDefinitionObservationStatus
    recovered_from_cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    recovered_from_significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus

    @field_validator("recovered_from_evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("recovered_from_evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> "MonitorDefinitionAlertEpisodeRecoveryBasis":
        _validate_monitor_definition_cause_code_contract(
            self.recovered_from_outcome_status,
            self.recovered_from_cause_code,
        )
        _validate_monitor_definition_escalation_contract(
            self.recovered_from_outcome_status,
            self.recovered_from_significance_status,
            field_name="recovered_from_significance_status",
        )
        if self.recovered_from_significance_status == "informational":
            raise ValueError(
                "recovered_from_significance_status must remain alert-eligible"
            )
        return self


class MonitorDefinitionAlertEpisode(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: MonitorDefinitionAlertEpisodeContractVersion = (
        "monitor_definition_alert_episode_v1"
    )
    monitor_definition_id: str
    episode_id: str
    episode_status: MonitorDefinitionAlertEpisodeStatus
    started_at: datetime
    ended_at: datetime | None = None
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    )
    latest_contributing_observation: MonitorDefinitionAlertEpisodeLatestContributingObservation
    recovery_basis: MonitorDefinitionAlertEpisodeRecoveryBasis | None = None

    @field_validator("started_at", "ended_at")
    @classmethod
    def _validate_episode_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("alert episode timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_episode_contract(self) -> "MonitorDefinitionAlertEpisode":
        if self.episode_status == "active":
            if self.hysteresis_transition not in {None, "open", "remain_open"}:
                raise ValueError(
                    "active alert episode hysteresis_transition must remain open or remain_open"
                )
        elif self.hysteresis_transition not in {None, "recover"}:
            raise ValueError(
                "recovered alert episode hysteresis_transition must remain recover"
            )
        if self.episode_status == "active":
            if self.ended_at is not None:
                raise ValueError("active alert episode must not define ended_at")
            if self.recovery_basis is not None:
                raise ValueError("active alert episode must not define recovery_basis")
        else:
            if self.ended_at is None:
                raise ValueError("recovered alert episode must define ended_at")
            if self.recovery_basis is None:
                raise ValueError("recovered alert episode must define recovery_basis")
            if self.ended_at < self.started_at:
                raise ValueError("recovered alert episode ended_at must not precede started_at")
            if self.recovery_basis.recovered_from_evaluated_at > self.ended_at:
                raise ValueError(
                    "recovered alert episode recovery basis must not follow ended_at"
                )
        latest_evaluated_at = self.latest_contributing_observation.evaluated_at
        if latest_evaluated_at < self.started_at:
            raise ValueError(
                "alert episode latest contributing observation must not precede started_at"
            )
        if self.ended_at is not None and latest_evaluated_at != self.ended_at:
            raise ValueError(
                "recovered alert episode latest contributing observation must match ended_at"
            )
        return self


class MonitorDefinitionAlertEpisodeRecordArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: MonitorDefinitionAlertEpisodeRecordSchemaVersion = (
        "monitor_definition_alert_episode_record_v1"
    )
    episode_id: str
    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    lifecycle_status: MonitorDefinitionAlertEpisodeLifecycleStatus
    latest_for_monitor_definition: bool
    started_at: datetime
    ended_at: datetime | None = None
    latest_event_at: datetime
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence | None = None
    latest_contributing_observation: MonitorDefinitionAlertEpisodeLatestContributingObservation
    recovery_basis: MonitorDefinitionAlertEpisodeRecoveryBasis | None = None
    terminal_history_entry_id: str
    timeline_handoff: MonitorDefinitionAlertEpisodeHistoryTimelineHandoff

    @field_validator("started_at", "ended_at", "latest_event_at")
    @classmethod
    def _validate_timestamps(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return value
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("alert episode history timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> "MonitorDefinitionAlertEpisodeRecordArtifact":
        if self.lifecycle_status == "open":
            if self.hysteresis_transition not in {None, "open", "remain_open"}:
                raise ValueError(
                    "open alert episode history rows hysteresis_transition must remain open or remain_open"
                )
        elif self.hysteresis_transition not in {None, "recover"}:
            raise ValueError(
                "recovered and closed alert episode history rows hysteresis_transition must remain recover"
            )
        if self.latest_event_at < self.started_at:
            raise ValueError("alert episode history latest_event_at must not precede started_at")
        if self.timeline_handoff.monitor_definition_id != self.monitor_definition_id:
            raise ValueError(
                "alert episode history timeline_handoff monitor_definition_id must match row identity"
            )
        if self.lifecycle_status == "open":
            if not self.latest_for_monitor_definition:
                raise ValueError(
                    "open alert episode history rows must remain latest for the monitor definition"
                )
            if self.ended_at is not None:
                raise ValueError("open alert episode history rows must not define ended_at")
            if self.recovery_basis is not None:
                raise ValueError(
                    "open alert episode history rows must not define recovery_basis"
                )
            if self.timeline_handoff.selected_event_kind != "latest_observation_event":
                raise ValueError(
                    "open alert episode history rows must reopen the latest observation timeline event"
                )
            if self.timeline_handoff.observation_id != self.latest_contributing_observation.observation_id:
                raise ValueError(
                    "open alert episode history rows must reopen the latest contributing observation"
                )
            if self.latest_event_at != self.latest_contributing_observation.evaluated_at:
                raise ValueError(
                    "open alert episode history latest_event_at must match the latest contributing observation"
                )
        else:
            if self.ended_at is None:
                raise ValueError(
                    "recovered and closed alert episode history rows must define ended_at"
                )
            if self.recovery_basis is None:
                raise ValueError(
                    "recovered and closed alert episode history rows must define recovery_basis"
                )
            if self.ended_at < self.started_at:
                raise ValueError(
                    "recovered and closed alert episode history rows ended_at must not precede started_at"
                )
            if self.latest_event_at != self.ended_at:
                raise ValueError(
                    "recovered and closed alert episode history latest_event_at must match ended_at"
                )
            if self.latest_contributing_observation.evaluated_at != self.ended_at:
                raise ValueError(
                    "recovered and closed alert episode latest contributing observation must match ended_at"
                )
            if self.timeline_handoff.selected_event_kind == "latest_observation_event":
                if self.lifecycle_status != "recovered" or not self.latest_for_monitor_definition:
                    raise ValueError(
                        "latest_observation_event handoffs are supported only for the latest recovered alert episode"
                    )
                if self.timeline_handoff.observation_id != self.latest_contributing_observation.observation_id:
                    raise ValueError(
                        "recovered alert episode history latest-observation handoff must match the latest contributing observation"
                    )
            else:
                if self.timeline_handoff.history_entry_id != self.terminal_history_entry_id:
                    raise ValueError(
                        "evaluation_history_event handoff must match terminal_history_entry_id"
                    )
            if self.lifecycle_status == "recovered" and not self.latest_for_monitor_definition:
                raise ValueError(
                    "recovered alert episode history rows must remain latest for the monitor definition"
                )
            if self.lifecycle_status == "closed" and self.latest_for_monitor_definition:
                raise ValueError(
                    "closed alert episode history rows must not remain latest for the monitor definition"
                )
        return self


class MonitorDefinitionAlertEpisodeHistoryRowMetadata(BaseModel):
    history_truth: MonitorDefinitionAlertEpisodeHistoryTruth = (
        "authoritative_persisted_monitor_definition_alert_episode_history"
    )
    row_provenance: MonitorDefinitionAlertEpisodeHistoryRowProvenance = (
        "persisted_monitor_definition_alert_episode_record"
    )


class MonitorDefinitionAlertEpisodeHistoryRow(MonitorDefinitionAlertEpisodeRecordArtifact):
    metadata: MonitorDefinitionAlertEpisodeHistoryRowMetadata = Field(
        default_factory=MonitorDefinitionAlertEpisodeHistoryRowMetadata
    )


class MonitorDefinitionAlertEpisodeHistoryResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionAlertEpisodeHistoryContractVersion = (
        "monitor_definition_alert_episode_history_v1"
    )
    history_truth: MonitorDefinitionAlertEpisodeHistoryTruth = (
        "authoritative_persisted_monitor_definition_alert_episode_history"
    )
    row_provenance: MonitorDefinitionAlertEpisodeHistoryRowProvenance = (
        "persisted_monitor_definition_alert_episode_record"
    )
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    )
    ordering: MonitorDefinitionAlertEpisodeHistoryOrdering = (
        "newest_first_latest_event_at_then_episode_id"
    )
    windowing: MonitorDefinitionAlertEpisodeHistoryWindowing = (
        "before_episode_id_exclusive"
    )
    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    returned_limit: int | None = None
    requested_before_episode_id: str | None = None
    next_before_episode_id: str | None = None
    total_episodes: int = 0


class MonitorDefinitionAlertEpisodeHistoryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MonitorDefinitionAlertEpisodeHistoryRow] = Field(default_factory=list)
    metadata: MonitorDefinitionAlertEpisodeHistoryResponseMetadata


class MonitorDefinitionActiveAlertEpisodeInboxRowMetadata(BaseModel):
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = (
        "authoritative_persisted_artifact_metadata"
    )
    row_provenance: MonitorDefinitionActiveAlertEpisodeInboxRowProvenance = (
        "persisted_monitor_definition_alert_episode_record"
    )


class MonitorDefinitionActiveAlertEpisodeInboxRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_scope: Literal["current_portfolio_truth_only"]
    evaluation_mode: Literal["review_only_observation_evaluation"]
    alert_episode: MonitorDefinitionAlertEpisodeHistoryRow
    metadata: MonitorDefinitionActiveAlertEpisodeInboxRowMetadata = Field(
        default_factory=MonitorDefinitionActiveAlertEpisodeInboxRowMetadata
    )

    @model_validator(mode="after")
    def _validate_row_contract(self) -> "MonitorDefinitionActiveAlertEpisodeInboxRow":
        if self.alert_episode.lifecycle_status != "open":
            raise ValueError(
                "active alert episode inbox rows must remain rooted in open persisted alert episodes"
            )
        if not self.alert_episode.latest_for_monitor_definition:
            raise ValueError(
                "active alert episode inbox rows must remain latest for the monitor definition"
            )
        if self.alert_episode.timeline_handoff.selected_event_kind != "latest_observation_event":
            raise ValueError(
                "active alert episode inbox rows must reopen the latest observation timeline event"
            )
        if (
            self.alert_episode.timeline_handoff.observation_id
            != self.alert_episode.latest_contributing_observation.observation_id
        ):
            raise ValueError(
                "active alert episode inbox rows must reopen the latest contributing observation"
            )
        return self


class MonitorDefinitionActiveAlertEpisodeInboxResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionActiveAlertEpisodeInboxContractVersion = (
        "monitor_definition_active_alert_episode_inbox_v1"
    )
    provenance: MonitorDefinitionActiveAlertEpisodeInboxProvenance = (
        "authoritative_persisted_monitor_definition_alert_episode_records_only"
    )
    row_provenance: MonitorDefinitionActiveAlertEpisodeInboxRowProvenance = (
        "persisted_monitor_definition_alert_episode_record"
    )
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_alert_episode_record_then_canonical_evaluation_lineage_validation"
    )
    ordering: MonitorDefinitionActiveAlertEpisodeInboxOrdering = (
        "newest_first_latest_event_at_then_monitor_definition_id_then_episode_id"
    )
    windowing: MonitorDefinitionActiveAlertEpisodeInboxWindowing = (
        "before_episode_id_exclusive"
    )
    returned_limit: int | None = None
    requested_before_episode_id: str | None = None
    next_before_episode_id: str | None = None
    total_active_episodes: int = 0


class MonitorDefinitionActiveAlertEpisodeInboxResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MonitorDefinitionActiveAlertEpisodeInboxRow] = Field(default_factory=list)
    metadata: MonitorDefinitionActiveAlertEpisodeInboxResponseMetadata = Field(
        default_factory=MonitorDefinitionActiveAlertEpisodeInboxResponseMetadata
    )


class MonitorDefinitionLatestObservationAlertInboxRowMetadata(BaseModel):
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = (
        "authoritative_persisted_artifact_metadata"
    )
    row_provenance: MonitorDefinitionLatestObservationAlertInboxRowProvenance = (
        "persisted_monitor_definition_observation_artifact"
    )


class MonitorDefinitionLatestObservationAlertInboxRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    observation_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    review_scope: Literal["current_portfolio_truth_only"]
    evaluation_mode: Literal["review_only_observation_evaluation"]
    evaluated_at: datetime
    observation_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    alert_classification: MonitorDefinitionAlertClassification
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    recency_status: MonitorDefinitionLatestObservationRecency
    reason: str | None = None
    open_handoff: MonitorDefinitionObservationOpenHandoff
    metadata: MonitorDefinitionLatestObservationAlertInboxRowMetadata = Field(
        default_factory=MonitorDefinitionLatestObservationAlertInboxRowMetadata
    )

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_row_contract(self) -> "MonitorDefinitionLatestObservationAlertInboxRow":
        _validate_monitor_definition_cause_code_contract(self.observation_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.observation_status,
            self.alert_classification,
            field_name="alert_classification",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.alert_classification,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


class MonitorDefinitionLatestObservationAlertInboxResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionLatestObservationAlertInboxContractVersion = (
        "monitor_definition_latest_observation_alert_inbox_v1"
    )
    provenance: MonitorDefinitionLatestObservationAlertInboxProvenance = (
        "authoritative_persisted_monitor_definition_observations_only"
    )
    row_provenance: MonitorDefinitionLatestObservationAlertInboxRowProvenance = (
        "persisted_monitor_definition_observation_artifact"
    )
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry"
    )
    ordering: MonitorDefinitionLatestObservationAlertInboxOrdering = (
        "newest_first_evaluated_at"
    )
    returned_limit: int | None = None


class MonitorDefinitionLatestObservationAlertInboxResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MonitorDefinitionLatestObservationAlertInboxRow] = Field(default_factory=list)
    metadata: MonitorDefinitionLatestObservationAlertInboxResponseMetadata = Field(
        default_factory=MonitorDefinitionLatestObservationAlertInboxResponseMetadata
    )


class MonitorDefinitionAlertHistoryQueueRowMetadata(BaseModel):
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = (
        "authoritative_persisted_artifact_metadata"
    )
    row_provenance: MonitorDefinitionAlertHistoryQueueRowProvenance = (
        "persisted_monitor_definition_evaluation_history_entry_with_latest_snapshot_precedence"
    )


class MonitorDefinitionAlertHistoryQueueRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    history_entry_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    review_scope: Literal["current_portfolio_truth_only"]
    evaluation_mode: Literal["review_only_observation_evaluation"]
    evaluated_at: datetime
    outcome_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus = "review_supported"
    latest_for_monitor_definition: bool
    reason: str | None = None
    review_handoff: MonitorDefinitionEvaluationHistoryReviewHandoff
    metadata: MonitorDefinitionAlertHistoryQueueRowMetadata = Field(
        default_factory=MonitorDefinitionAlertHistoryQueueRowMetadata
    )

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_row_contract(self) -> "MonitorDefinitionAlertHistoryQueueRow":
        _validate_monitor_definition_cause_code_contract(self.outcome_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.outcome_status,
            self.significance_status,
            field_name="significance_status",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.significance_status,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


class MonitorDefinitionAlertHistoryQueueResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionAlertHistoryQueueContractVersion = (
        "monitor_definition_alert_history_queue_v1"
    )
    provenance: MonitorDefinitionAlertHistoryQueueProvenance = (
        "persisted_monitor_definitions_with_canonical_latest_snapshot_and_evaluation_history"
    )
    row_provenance: MonitorDefinitionAlertHistoryQueueRowProvenance = (
        "persisted_monitor_definition_evaluation_history_entry_with_latest_snapshot_precedence"
    )
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries"
    )
    ordering: MonitorDefinitionAlertHistoryQueueOrdering = (
        "newest_first_evaluated_at_then_latest_snapshot_precedence_then_monitor_definition_id_then_history_entry_id"
    )
    returned_limit: int | None = None
    total_queue_rows: int = 0


class MonitorDefinitionAlertHistoryQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MonitorDefinitionAlertHistoryQueueRow] = Field(default_factory=list)
    metadata: MonitorDefinitionAlertHistoryQueueResponseMetadata = Field(
        default_factory=MonitorDefinitionAlertHistoryQueueResponseMetadata
    )


class MonitorDefinitionRecoveredAlertReviewQueueRecoveredFrom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    history_entry_id: str
    evaluated_at: datetime
    outcome_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    reason: str | None = None

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_row_contract(self) -> "MonitorDefinitionRecoveredAlertReviewQueueRecoveredFrom":
        _validate_monitor_definition_cause_code_contract(self.outcome_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.outcome_status,
            self.significance_status,
            field_name="significance_status",
        )
        if self.significance_status == "informational":
            raise ValueError(
                "significance_status must remain alert-eligible for recovered_from lineage"
            )
        return self


class MonitorDefinitionRecoveredAlertReviewQueueRowMetadata(BaseModel):
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = (
        "authoritative_persisted_artifact_metadata"
    )
    row_provenance: MonitorDefinitionRecoveredAlertReviewQueueRowProvenance = (
        "persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage"
    )


class MonitorDefinitionRecoveredAlertReviewQueueRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    observation_id: str
    latest_history_entry_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    review_scope: Literal["current_portfolio_truth_only"]
    evaluation_mode: Literal["review_only_observation_evaluation"]
    evaluated_at: datetime
    observation_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    alert_classification: MonitorDefinitionAlertClassification
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    recency_status: MonitorDefinitionLatestObservationRecency
    reason: str | None = None
    alert_episode: MonitorDefinitionAlertEpisode
    recovered_from: MonitorDefinitionRecoveredAlertReviewQueueRecoveredFrom
    timeline_handoff: MonitorDefinitionAlertReviewTimelineOpenHandoff
    metadata: MonitorDefinitionRecoveredAlertReviewQueueRowMetadata = Field(
        default_factory=MonitorDefinitionRecoveredAlertReviewQueueRowMetadata
    )

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_row_contract(self) -> "MonitorDefinitionRecoveredAlertReviewQueueRow":
        _validate_monitor_definition_cause_code_contract(self.observation_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.observation_status,
            self.alert_classification,
            field_name="alert_classification",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.alert_classification,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        if self.alert_classification != "informational":
            raise ValueError(
                "alert_classification must remain informational for recovered alert queue rows"
            )
        if self.alert_episode.monitor_definition_id != self.monitor_definition_id:
            raise ValueError(
                "alert_episode monitor_definition_id must match row monitor_definition_id"
            )
        if self.alert_episode.episode_status != "recovered":
            raise ValueError("alert_episode episode_status must remain recovered")
        if (
            self.alert_episode.latest_contributing_observation.observation_id
            != self.observation_id
        ):
            raise ValueError(
                "alert_episode latest_contributing_observation observation_id must match row observation_id"
            )
        if self.alert_episode.recovery_basis is None:
            raise ValueError("alert_episode recovery_basis must be present")
        if (
            self.alert_episode.recovery_basis.recovered_from_history_entry_id
            != self.recovered_from.history_entry_id
        ):
            raise ValueError(
                "alert_episode recovery_basis recovered_from_history_entry_id must match recovered_from history_entry_id"
            )
        if self.timeline_handoff.observation_id != self.observation_id:
            raise ValueError("timeline_handoff observation_id must match row observation_id")
        if self.timeline_handoff.monitor_definition_id != self.monitor_definition_id:
            raise ValueError(
                "timeline_handoff monitor_definition_id must match row monitor_definition_id"
            )
        if self.recovered_from.history_entry_id == self.latest_history_entry_id:
            raise ValueError(
                "recovered_from history_entry_id must remain distinct from latest_history_entry_id"
            )
        return self


class MonitorDefinitionRecoveredAlertReviewQueueResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionRecoveredAlertReviewQueueContractVersion = (
        "monitor_definition_recovered_alert_review_queue_v1"
    )
    provenance: MonitorDefinitionRecoveredAlertReviewQueueProvenance = (
        "persisted_latest_observation_with_latest_snapshot_and_prior_alert_history_lineage"
    )
    row_provenance: MonitorDefinitionRecoveredAlertReviewQueueRowProvenance = (
        "persisted_monitor_definition_observation_artifact_with_latest_snapshot_and_prior_alert_history_lineage"
    )
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_observation_artifact_then_persisted_latest_evaluation_snapshot_then_persisted_latest_history_entry_then_prior_alert_history_entries"
    )
    ordering: MonitorDefinitionRecoveredAlertReviewQueueOrdering = (
        "newest_first_evaluated_at_then_monitor_definition_id_then_observation_id"
    )
    returned_limit: int | None = None
    total_queue_rows: int = 0


class MonitorDefinitionRecoveredAlertReviewQueueResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MonitorDefinitionRecoveredAlertReviewQueueRow] = Field(default_factory=list)
    metadata: MonitorDefinitionRecoveredAlertReviewQueueResponseMetadata = Field(
        default_factory=MonitorDefinitionRecoveredAlertReviewQueueResponseMetadata
    )


class MonitorDefinitionAlertReviewTimelineObservationRowMetadata(BaseModel):
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = (
        "authoritative_persisted_artifact_metadata"
    )
    row_provenance: MonitorDefinitionLatestObservationAlertInboxRowProvenance = (
        "persisted_monitor_definition_observation_artifact"
    )


class MonitorDefinitionAlertReviewTimelineObservationRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    observation_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    review_scope: Literal["current_portfolio_truth_only"]
    evaluation_mode: Literal["review_only_observation_evaluation"]
    evaluated_at: datetime
    observation_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    alert_classification: MonitorDefinitionAlertClassification
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    recency_status: MonitorDefinitionLatestObservationRecency
    reason: str | None = None
    open_handoff: MonitorDefinitionObservationOpenHandoff
    event_kind: Literal["latest_observation_event"] = "latest_observation_event"
    event_semantics: Literal["observation_rooted"] = "observation_rooted"
    thresholds: BenchmarkTrendOverlayMonitorThresholds
    benchmark_observation: BenchmarkTrendOverlayMonitorBenchmarkObservationInput
    portfolio_observation: BenchmarkTrendOverlayMonitorPortfolioObservation
    active_observation: BenchmarkTrendOverlayMonitorActiveObservation
    metadata: MonitorDefinitionAlertReviewTimelineObservationRowMetadata = Field(
        default_factory=MonitorDefinitionAlertReviewTimelineObservationRowMetadata
    )

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_row_contract(self) -> "MonitorDefinitionAlertReviewTimelineObservationRow":
        _validate_monitor_definition_cause_code_contract(self.observation_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.observation_status,
            self.alert_classification,
            field_name="alert_classification",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.alert_classification,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


class MonitorDefinitionAlertReviewTimelineHistoryRowMetadata(BaseModel):
    metadata_truth: MonitorDefinitionDiscoveryMetadataTruth = (
        "authoritative_persisted_artifact_metadata"
    )
    row_provenance: MonitorDefinitionEvaluationHistoryRowProvenance = (
        "persisted_monitor_definition_evaluation_history_entry"
    )


class MonitorDefinitionAlertReviewTimelineHistoryRow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    history_entry_id: str
    monitor_id: Literal["benchmark_trend_overlay_v1"]
    benchmark_symbol: str
    review_scope: Literal["current_portfolio_truth_only"]
    evaluation_mode: Literal["review_only_observation_evaluation"]
    evaluated_at: datetime
    outcome_status: MonitorDefinitionObservationStatus
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    review_support_status: MonitorDefinitionDiscoveryReviewSupportStatus = "review_supported"
    latest_for_monitor_definition: bool
    reason: str | None = None
    review_handoff: MonitorDefinitionEvaluationHistoryReviewHandoff
    event_kind: Literal["evaluation_history_event"] = "evaluation_history_event"
    event_semantics: Literal["history_entry_rooted"] = "history_entry_rooted"
    thresholds: BenchmarkTrendOverlayMonitorThresholds
    benchmark_observation: BenchmarkTrendOverlayMonitorBenchmarkObservationInput
    portfolio_observation: BenchmarkTrendOverlayMonitorPortfolioObservation
    active_observation: BenchmarkTrendOverlayMonitorActiveObservation
    metadata: MonitorDefinitionAlertReviewTimelineHistoryRowMetadata = Field(
        default_factory=MonitorDefinitionAlertReviewTimelineHistoryRowMetadata
    )

    @field_validator("evaluated_at")
    @classmethod
    def _validate_evaluated_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evaluated_at must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_row_contract(self) -> "MonitorDefinitionAlertReviewTimelineHistoryRow":
        _validate_monitor_definition_cause_code_contract(self.outcome_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.outcome_status,
            self.significance_status,
            field_name="significance_status",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.significance_status,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


MonitorDefinitionAlertReviewTimelineRow: TypeAlias = Annotated[
    MonitorDefinitionAlertReviewTimelineObservationRow | MonitorDefinitionAlertReviewTimelineHistoryRow,
    Field(discriminator="event_kind"),
]


class MonitorDefinitionAlertReviewTimelineResponseMetadata(BaseModel):
    contract_version: MonitorDefinitionAlertReviewTimelineContractVersion = (
        "monitor_definition_alert_review_timeline_v1"
    )
    provenance: MonitorDefinitionAlertReviewTimelineProvenance = (
        "canonical_latest_observation_artifact_and_append_only_evaluation_history_entries"
    )
    ordering: MonitorDefinitionAlertReviewTimelineOrdering = (
        "newest_first_evaluated_at_then_observation_event_then_history_entry_id"
    )
    monitor_definition_id: str
    monitor_definition_fingerprint: str
    monitor_definition_schema_version: Literal["monitor_definition_artifact_v1"] = (
        "monitor_definition_artifact_v1"
    )
    observation_row_provenance: MonitorDefinitionLatestObservationAlertInboxRowProvenance = (
        "persisted_monitor_definition_observation_artifact"
    )
    history_row_provenance: MonitorDefinitionEvaluationHistoryRowProvenance = (
        "persisted_monitor_definition_evaluation_history_entry"
    )
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_observation_artifact_then_persisted_evaluation_history_entries_then_persisted_latest_alert_episode_projection"
    )
    latest_alert_episode: MonitorDefinitionAlertEpisode | None = None
    total_rows: int = 0
    observation_rows: int = 0
    history_rows: int = 0


class MonitorDefinitionAlertReviewTimelineResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[MonitorDefinitionAlertReviewTimelineRow] = Field(default_factory=list)
    metadata: MonitorDefinitionAlertReviewTimelineResponseMetadata


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
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    reason: str | None = None
    thresholds: BenchmarkTrendOverlayMonitorThresholds
    benchmark_observation: BenchmarkTrendOverlayMonitorBenchmarkObservationInput
    portfolio_observation: BenchmarkTrendOverlayMonitorPortfolioObservation
    active_observation: BenchmarkTrendOverlayMonitorActiveObservation

    @model_validator(mode="after")
    def _validate_cause_code(self) -> "MonitorDefinitionObservationEvaluationResponse":
        _validate_monitor_definition_cause_code_contract(self.observation_status, self.cause_code)
        return self


class MonitorDefinitionObservationArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: MonitorDefinitionObservationArtifactSchemaVersion = (
        "monitor_definition_observation_artifact_v1"
    )
    observation_id: str
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
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    alert_classification: MonitorDefinitionAlertClassification
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence | None = None
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

    @model_validator(mode="after")
    def _validate_cause_and_alert(self) -> "MonitorDefinitionObservationArtifact":
        _validate_monitor_definition_cause_code_contract(self.observation_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.observation_status,
            self.alert_classification,
            field_name="alert_classification",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.alert_classification,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


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
    cause_code: MonitorDefinitionCanonicalCauseCode | None = None
    significance_status: MonitorDefinitionLatestEvaluationSignificanceStatus
    hysteresis_transition: MonitorDefinitionHysteresisTransition | None = None
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence | None = None
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

    @model_validator(mode="after")
    def _validate_cause_and_significance(self) -> "MonitorDefinitionEvaluationHistoryEntryArtifact":
        _validate_monitor_definition_cause_code_contract(self.observation_status, self.cause_code)
        _validate_monitor_definition_escalation_contract(
            self.observation_status,
            self.significance_status,
            field_name="significance_status",
        )
        _validate_monitor_definition_hysteresis_transition_contract(
            self.significance_status,
            self.hysteresis_transition,
            field_name="hysteresis_transition",
        )
        return self


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
    source_precedence: MonitorDefinitionMonitoringSourcePrecedence = (
        "persisted_evaluation_history_entry_only"
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
