from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.return_basis import ReturnBasisContract, ReturnBasisEvidence, ReturnBasisPathTrust


OptimizerStatus = Literal["feasible", "infeasible", "rejected"]
OptimizerConstraintStatus = Literal["pass", "binding", "violated", "not_applicable"]
OptimizerArtifactSchemaVersion = Literal["optimizer_artifact_v1"]
OptimizerHandoffSchemaVersion = Literal["optimizer_handoff_manifest_v1"]
OptimizerArtifactState = Literal["complete", "degraded", "stale", "infeasible", "rejected"]
OptimizerObjectiveId = Literal["minimize_l2_distance_to_benchmark", "maximize_alpha_quality_v1"]
OptimizerArtifactInputKind = Literal["request", "universe", "benchmark", "constraints", "solver", "alpha_package", "risk_package"]
OptimizerBenchmarkAttestationType = Literal["max_abs_active_weight", "active_group_exposure", "benchmark_alignment"]
OptimizerTradeIntentAction = Literal["buy", "sell", "hold", "initiate", "exit"]
OptimizerRiskPackageStatus = Literal["ok", "invalid"]
OptimizerRiskPackageVersion = Literal["optimizer_risk_package_v1", "optimizer_risk_package_v2"]
OptimizerRiskRepresentation = Literal["diagonal_covariance", "structured_shrunk_covariance"]
OptimizerGroupTaxonomy = Literal["sector", "industry", "country", "region"]
OptimizerAlphaPackageStatus = Literal["ok", "invalid"]
OptimizerAlphaPackageVersion = Literal["alpha_quality_v1"]
OptimizerAlphaInputContractId = Literal["alpha_quality_v1_pit_fundamentals_v1"]
OptimizerAlphaPitTrustStatus = Literal["trusted", "quarantined"]
OptimizerAlphaNormalizationMethod = Literal["winsorized_zscore"]
OptimizerAlphaFallbackBehavior = Literal["conservative_negative"]
OptimizerAlphaAvailabilitySemantics = Literal["available_date", "publication_date", "filing_date", "derived_reporting_lag"]
OptimizerAlphaSignalId = Literal["profitability", "cash_generation", "accrual_quality", "leverage_discipline"]
OptimizerAlphaMeasureId = Literal[
    "gross_profitability",
    "ebit_to_assets",
    "cfo_to_assets",
    "fcf_to_assets",
    "accruals_to_assets",
    "net_leverage_to_assets",
]
OptimizerFundamentalPeriodType = Literal["quarterly", "annual"]


def canonicalize_benchmark_symbol(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized or None


class OptimizerWeight(BaseModel):
    symbol: str
    weight: float = Field(ge=0.0, le=1.0)


class OptimizerUniverseAsset(BaseModel):
    symbol: str
    eligible: bool = True
    min_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    max_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    taxonomy_labels: dict[OptimizerGroupTaxonomy, str] = Field(default_factory=dict)


class OptimizerObjective(BaseModel):
    objective_id: OptimizerObjectiveId = "minimize_l2_distance_to_benchmark"
    benchmark_relative: Literal[True] = True
    description: str | None = None
    alpha_signal_id: OptimizerAlphaPackageVersion | None = None
    requires_alpha_package: bool = False

    @model_validator(mode="before")
    @classmethod
    def _apply_objective_defaults(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        objective_id = value.get("objective_id", "minimize_l2_distance_to_benchmark")
        defaults_by_objective = {
            "minimize_l2_distance_to_benchmark": {
                "description": "Minimize squared distance to benchmark weights inside the hard-constraint set.",
                "alpha_signal_id": None,
                "requires_alpha_package": False,
            },
            "maximize_alpha_quality_v1": {
                "description": "Maximize the additive alpha_quality_v1 preference vector inside the unchanged hard-constraint set.",
                "alpha_signal_id": "alpha_quality_v1",
                "requires_alpha_package": True,
            },
        }
        defaults = defaults_by_objective.get(objective_id)
        if defaults is None:
            return value
        normalized = dict(value)
        normalized.setdefault("description", defaults["description"])
        normalized.setdefault("alpha_signal_id", defaults["alpha_signal_id"])
        normalized.setdefault("requires_alpha_package", defaults["requires_alpha_package"])
        return normalized

    @model_validator(mode="after")
    def _validate_objective_metadata(self) -> "OptimizerObjective":
        if self.objective_id == "minimize_l2_distance_to_benchmark":
            if self.alpha_signal_id is not None:
                raise ValueError("benchmark-distance objective must not declare alpha_signal_id")
            if self.requires_alpha_package:
                raise ValueError("benchmark-distance objective must not require alpha_package")
            if self.description is None:
                raise ValueError("benchmark-distance objective requires description")
            return self
        if self.alpha_signal_id != "alpha_quality_v1":
            raise ValueError("alpha objective must declare alpha_signal_id=alpha_quality_v1")
        if not self.requires_alpha_package:
            raise ValueError("alpha objective must require alpha_package")
        if self.description is None:
            raise ValueError("alpha objective requires description")
        return self


class OptimizerPenalty(BaseModel):
    penalty_id: Literal["l2_distance_to_current"]
    penalty_weight: float = Field(ge=0.0)
    description: str = "Optional convex stability penalty that keeps weights closer to the current portfolio."


class OptimizerBenchmarkRelativeConstraint(BaseModel):
    max_abs_active_weight: float = Field(ge=0.0, le=1.0)


class OptimizerPositionLimitConstraint(BaseModel):
    default_max_weight: float | None = Field(default=None, ge=0.0, le=1.0)


class OptimizerTurnoverConstraint(BaseModel):
    max_turnover: float | None = Field(default=None, ge=0.0, le=1.0)


class OptimizerRiskConstraint(BaseModel):
    max_active_risk: float | None = Field(default=None, ge=0.0)


class OptimizerActiveGroupConstraint(BaseModel):
    taxonomy: OptimizerGroupTaxonomy
    max_abs_active_exposure: float = Field(ge=0.0, le=1.0)


class OptimizerHardConstraints(BaseModel):
    full_investment: Literal[True] = True
    long_only: Literal[True] = True
    benchmark_relative: OptimizerBenchmarkRelativeConstraint
    position_limits: OptimizerPositionLimitConstraint = Field(default_factory=OptimizerPositionLimitConstraint)
    turnover: OptimizerTurnoverConstraint = Field(default_factory=OptimizerTurnoverConstraint)
    risk: OptimizerRiskConstraint = Field(default_factory=OptimizerRiskConstraint)
    active_group_exposures: list[OptimizerActiveGroupConstraint] = Field(default_factory=list)


class OptimizerRiskBenchmarkAlignment(BaseModel):
    benchmark_symbol: str
    benchmark_weight_coverage: float = Field(ge=0.0, le=1.0)
    aligned: bool = True
    benchmark_symbols_missing_from_package: list[str] = Field(default_factory=list)


class OptimizerRiskDiagnostics(BaseModel):
    status: OptimizerRiskPackageStatus = "ok"
    risk_model_version: str | None = None
    universe_symbol_count: int = Field(ge=0)
    covered_symbol_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    minimum_coverage_ratio: float = Field(ge=0.0, le=1.0)
    minimum_observations: int = Field(ge=1)
    stale_after_days: int = Field(ge=0)
    observation_count_by_symbol: dict[str, int] = Field(default_factory=dict)
    latest_data_by_symbol: dict[str, str | None] = Field(default_factory=dict)
    missing_symbols: list[str] = Field(default_factory=list)
    stale_symbols: list[str] = Field(default_factory=list)
    low_observation_symbols: list[str] = Field(default_factory=list)
    pairwise_coverage_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    average_positive_correlation: float | None = None
    diagonal_fallback_symbols: list[str] = Field(default_factory=list)
    covariance_min_eigenvalue: float | None = None
    covariance_psd: bool = True


class OptimizerRiskPackage(BaseModel):
    package_id: str
    version: OptimizerRiskPackageVersion = "optimizer_risk_package_v2"
    rebalance_date: str
    benchmark_symbol: str
    representation: OptimizerRiskRepresentation = "structured_shrunk_covariance"
    annualization_factor: int = Field(default=252, ge=1)
    ordered_symbols: list[str] = Field(default_factory=list)
    covariance_matrix: list[list[float]] = Field(default_factory=list)
    benchmark_alignment: OptimizerRiskBenchmarkAlignment
    diagnostics: OptimizerRiskDiagnostics


class OptimizerAlphaLagPolicy(BaseModel):
    quarterly_reporting_lag_days: int = Field(default=45, ge=0)
    annual_reporting_lag_days: int = Field(default=90, ge=0)
    stale_after_days: int = Field(default=450, ge=0)


class OptimizerAlphaFundamentalSnapshot(BaseModel):
    source_dataset: str | None = None
    source_record_id: str | None = None
    symbol: str
    issuer_id: str | None = None
    statement_date: str
    period_type: OptimizerFundamentalPeriodType
    publication_date: str | None = None
    filing_date: str | None = None
    available_date: str | None = None
    availability_semantics: OptimizerAlphaAvailabilitySemantics | None = None
    currency: str | None = None
    total_revenue: float | None = None
    cost_of_revenue: float | None = None
    ebit: float | None = None
    total_assets: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    net_income: float | None = None
    total_debt: float | None = None
    cash_and_equivalents: float | None = None


class OptimizerAlphaPitFundamentalRecord(BaseModel):
    source_dataset: str
    source_record_id: str
    symbol: str
    issuer_id: str
    statement_date: str
    period_type: OptimizerFundamentalPeriodType
    availability_semantics: OptimizerAlphaAvailabilitySemantics
    publication_date: str | None = None
    filing_date: str | None = None
    available_date: str | None = None
    currency: str | None = None
    total_revenue: float | None = None
    cost_of_revenue: float | None = None
    ebit: float | None = None
    total_assets: float | None = None
    operating_cash_flow: float | None = None
    free_cash_flow: float | None = None
    net_income: float | None = None
    total_debt: float | None = None
    cash_and_equivalents: float | None = None

    @model_validator(mode="after")
    def _validate_availability_fields(self) -> "OptimizerAlphaPitFundamentalRecord":
        required_field_by_semantics = {
            "available_date": "available_date",
            "publication_date": "publication_date",
            "filing_date": "filing_date",
        }
        required_field = required_field_by_semantics.get(self.availability_semantics)
        if required_field is not None and getattr(self, required_field) is None:
            raise ValueError(f"availability_semantics={self.availability_semantics} requires {required_field}")
        return self


class OptimizerAlphaPitFundamentalsInput(BaseModel):
    contract_id: OptimizerAlphaInputContractId = "alpha_quality_v1_pit_fundamentals_v1"
    decision_date: str
    as_of_date: str
    source_name: str
    replay_id: str | None = None
    universe_symbols: list[str] = Field(default_factory=list)
    records: list[OptimizerAlphaPitFundamentalRecord] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_dates(self) -> "OptimizerAlphaPitFundamentalsInput":
        if date.fromisoformat(self.as_of_date) > date.fromisoformat(self.decision_date):
            raise ValueError("as_of_date cannot be later than decision_date")
        return self


class OptimizerAlphaPitTrustIssue(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class OptimizerAlphaPitTrustReport(BaseModel):
    status: OptimizerAlphaPitTrustStatus = "trusted"
    as_of_date: str
    decision_date: str | None = None
    source_name: str | None = None
    replay_id: str | None = None
    requested_universe_symbols: list[str] = Field(default_factory=list)
    snapshot_universe_symbols: list[str] = Field(default_factory=list)
    raw_snapshot_symbols: list[str] = Field(default_factory=list)
    normalized_record_count: int = Field(default=0, ge=0)
    raw_bundle_count: int = Field(default=0, ge=0)
    lineage_valid: bool = False
    replay_valid: bool = False
    approved_universe_valid: bool = False
    persisted_input_digest: str | None = None
    replay_input_digest: str | None = None
    issues: list[OptimizerAlphaPitTrustIssue] = Field(default_factory=list)


class OptimizerAlphaCoverageFlags(BaseModel):
    has_eligible_snapshot: bool
    has_fresh_snapshot: bool
    has_any_signal_coverage: bool
    has_complete_signal_set: bool
    used_conservative_fallback: bool
    stale_snapshot: bool
    lag_blocked: bool
    missing_snapshot: bool


class OptimizerAlphaSubSignal(BaseModel):
    component_id: OptimizerAlphaSignalId
    weight: float = Field(ge=0.0, le=1.0)
    measure_id: OptimizerAlphaMeasureId | None = None
    higher_is_better: bool
    raw_value: float | None = None
    winsorized_value: float | None = None
    normalized_score: float
    available: bool
    fallback_applied: bool
    stale_input: bool = False
    missing_fields: list[str] = Field(default_factory=list)
    note: str | None = None


class OptimizerAlphaSecurityRow(BaseModel):
    symbol: str
    selected_snapshot: OptimizerAlphaFundamentalSnapshot | None = None
    effective_date: str | None = None
    coverage_flags: OptimizerAlphaCoverageFlags
    sub_signals: list[OptimizerAlphaSubSignal] = Field(default_factory=list)
    final_score: float


class OptimizerAlphaMetadata(BaseModel):
    methodology_id: str
    point_in_time_only: Literal[True] = True
    normalization_method: OptimizerAlphaNormalizationMethod = "winsorized_zscore"
    fallback_behavior: OptimizerAlphaFallbackBehavior = "conservative_negative"
    winsor_lower_quantile: float = Field(ge=0.0, le=0.5)
    winsor_upper_quantile: float = Field(ge=0.5, le=1.0)
    zscore_cap: float = Field(gt=0.0)
    conservative_fallback_score: float
    lag_policy: OptimizerAlphaLagPolicy
    input_descriptor: "OptimizerAlphaInputDescriptor"
    component_weights: dict[OptimizerAlphaSignalId, float] = Field(default_factory=dict)
    component_definitions: dict[OptimizerAlphaSignalId, str] = Field(default_factory=dict)


class OptimizerAlphaInputContract(BaseModel):
    contract_id: OptimizerAlphaInputContractId = "alpha_quality_v1_pit_fundamentals_v1"
    required_identifier_fields: list[str] = Field(
        default_factory=lambda: ["symbol", "issuer_id", "source_dataset", "source_record_id"]
    )
    required_timestamp_fields: list[str] = Field(default_factory=lambda: ["statement_date", "period_type", "availability_semantics"])
    conditional_timestamp_fields: dict[OptimizerAlphaAvailabilitySemantics, str] = Field(
        default_factory=lambda: {
            "available_date": "available_date",
            "publication_date": "publication_date",
            "filing_date": "filing_date",
            "derived_reporting_lag": "statement_date_plus_reporting_lag",
        }
    )
    required_fundamental_fields: list[str] = Field(
        default_factory=lambda: [
            "total_assets",
            "total_revenue",
            "cost_of_revenue",
            "ebit",
            "operating_cash_flow",
            "free_cash_flow",
            "net_income",
            "total_debt",
            "cash_and_equivalents",
        ]
    )
    effective_date_priority: list[OptimizerAlphaAvailabilitySemantics] = Field(
        default_factory=lambda: ["available_date", "publication_date", "filing_date", "derived_reporting_lag"]
    )
    as_of_policy: str = "Only records whose effective date is on or before as_of_date may enter alpha_quality_v1."
    reporting_lag_policy: OptimizerAlphaLagPolicy
    staleness_policy: str = "A selected record is stale when rebalance_date minus effective_date exceeds stale_after_days."
    missingness_policy: str = "No hidden imputation. Missing required component fields force component-level conservative fallback only."
    fallback_policy: str = "No fallback to latest-known, current, final, or restated records beyond the as_of_date boundary."
    coverage_validation_policy: str = "Package status is invalid when any symbol is missing, lag-blocked, stale, or requires conservative fallback."


class OptimizerAlphaPitProvenance(BaseModel):
    trust_status: OptimizerAlphaPitTrustStatus
    as_of_date: str
    decision_date: str
    snapshot_digest: str
    replay_digest: str | None = None


class OptimizerAlphaInputDescriptor(BaseModel):
    contract: OptimizerAlphaInputContract
    as_of_date: str
    source_name: str
    replay_id: str | None = None
    input_record_count: int = Field(ge=0)
    input_digest: str
    pit_provenance: OptimizerAlphaPitProvenance | None = None

    @model_validator(mode="after")
    def _validate_pit_provenance(self) -> "OptimizerAlphaInputDescriptor":
        if self.pit_provenance is not None and self.pit_provenance.as_of_date != self.as_of_date:
            raise ValueError("pit_provenance.as_of_date must match input_descriptor.as_of_date")
        return self


class OptimizerAlphaDiagnostics(BaseModel):
    status: OptimizerAlphaPackageStatus = "ok"
    universe_symbol_count: int = Field(ge=0)
    covered_symbol_count: int = Field(ge=0)
    fresh_snapshot_count: int = Field(ge=0)
    coverage_ratio: float = Field(ge=0.0, le=1.0)
    complete_coverage_ratio: float = Field(ge=0.0, le=1.0)
    component_coverage_counts: dict[OptimizerAlphaSignalId, int] = Field(default_factory=dict)
    selected_effective_date_by_symbol: dict[str, str | None] = Field(default_factory=dict)
    missing_snapshot_symbols: list[str] = Field(default_factory=list)
    stale_symbols: list[str] = Field(default_factory=list)
    lag_blocked_symbols: list[str] = Field(default_factory=list)
    fallback_symbols: list[str] = Field(default_factory=list)


class OptimizerAlphaPackage(BaseModel):
    package_id: str
    version: OptimizerAlphaPackageVersion = "alpha_quality_v1"
    rebalance_date: str
    ordered_symbols: list[str] = Field(default_factory=list)
    securities: list[OptimizerAlphaSecurityRow] = Field(default_factory=list)
    metadata: OptimizerAlphaMetadata
    diagnostics: OptimizerAlphaDiagnostics


class OptimizationRequest(BaseModel):
    request_id: str | None = None
    as_of_timestamp: str
    effective_timestamp: str
    universe_id: str
    benchmark_id: str
    current_portfolio_weights: list[OptimizerWeight] = Field(default_factory=list)
    benchmark_weights: list[OptimizerWeight] = Field(default_factory=list)
    universe: list[OptimizerUniverseAsset] = Field(default_factory=list)
    objective: OptimizerObjective = Field(default_factory=OptimizerObjective)
    hard_constraints: OptimizerHardConstraints
    penalties: list[OptimizerPenalty] = Field(default_factory=list)
    risk_package: OptimizerRiskPackage | None = None
    alpha_package: OptimizerAlphaPackage | None = None

    @model_validator(mode="after")
    def _validate_timestamps(self) -> "OptimizationRequest":
        as_of_ts = datetime.fromisoformat(self.as_of_timestamp)
        effective_ts = datetime.fromisoformat(self.effective_timestamp)
        if as_of_ts > effective_ts:
            raise ValueError("as_of_timestamp cannot be later than effective_timestamp")
        return self


class OptimizationConstraintEvaluation(BaseModel):
    constraint_id: str
    status: OptimizerConstraintStatus
    actual_value: float | None = None
    limit_value: float | None = None
    slack: float | None = None
    binding_symbols: list[str] = Field(default_factory=list)
    message: str


class OptimizerActiveWeight(BaseModel):
    symbol: str
    weight: float = Field(ge=-1.0, le=1.0)


class OptimizationIssue(BaseModel):
    code: str
    constraint_id: str | None = None
    message: str
    actual_value: float | str | None = None
    required_value: float | str | None = None
    gap: float | None = None
    symbols: list[str] = Field(default_factory=list)


class OptimizationFeasibilityDiagnostics(BaseModel):
    status: OptimizerStatus
    summary: str
    issues: list[OptimizationIssue] = Field(default_factory=list)
    binding_constraints: list[str] = Field(default_factory=list)
    violated_constraints: list[str] = Field(default_factory=list)


class OptimizationExAnteDiagnostics(BaseModel):
    active_share: float | None = None
    turnover: float | None = None
    max_abs_active_weight: float | None = None
    active_risk: float | None = None
    weight_hhi: float | None = None
    effective_holdings: float | None = None
    invested_names_count: int = 0
    eligible_names_count: int = 0
    benchmark_weight_coverage: float | None = None
    risk_package_coverage_ratio: float | None = None
    risk_package_version: str | None = None
    risk_package_representation: str | None = None
    risk_package_rebalance_date: str | None = None
    risk_package_pairwise_coverage_ratio: float | None = None
    risk_package_diagonal_fallback_count: int | None = None
    alpha_package_coverage_ratio: float | None = None
    alpha_package_version: str | None = None
    alpha_preference_applied: bool = False
    alpha_preference_l1_budget: float | None = None
    current_to_proposed_l2: float | None = None
    benchmark_to_proposed_l2: float | None = None
    active_group_exposures: list["OptimizationActiveGroupExposureDiagnostic"] = Field(default_factory=list)


class OptimizationActiveGroupExposureDiagnostic(BaseModel):
    constraint_id: str
    taxonomy: OptimizerGroupTaxonomy
    group_name: str
    portfolio_weight: float = Field(ge=0.0, le=1.0)
    benchmark_weight: float = Field(ge=0.0, le=1.0)
    active_weight: float = Field(ge=-1.0, le=1.0)
    max_abs_active_exposure: float = Field(ge=0.0, le=1.0)
    status: OptimizerConstraintStatus


class OptimizationRunMetadata(BaseModel):
    engine_id: str
    methodology_id: str
    solver_id: str
    risk_package_id: str | None = None
    risk_package_version: str | None = None
    risk_package_representation: str | None = None
    risk_package_rebalance_date: str | None = None
    risk_package_pairwise_coverage_ratio: float | None = None
    risk_package_diagonal_fallback_count: int | None = None
    alpha_package_id: str | None = None
    alpha_package_version: str | None = None
    alpha_package_rebalance_date: str | None = None
    alpha_package_coverage_ratio: float | None = None
    alpha_preference_l1_budget: float | None = None
    deterministic_symbol_order: list[str] = Field(default_factory=list)
    converged: bool
    iteration_count: int
    tolerance: float
    max_iterations: int
    constraint_residual: float | None = None


class OptimizerReturnBasisSectionTrust(BaseModel):
    benchmark_relative_path: ReturnBasisPathTrust
    factor_model_path: ReturnBasisPathTrust
    risk_contribution_path: ReturnBasisPathTrust


class OptimizerReturnBasisEvidenceBundle(BaseModel):
    benchmark_history: ReturnBasisEvidence
    factor_history: ReturnBasisEvidence


class OptimizerReturnBasisAttestation(BaseModel):
    benchmark_symbol: str
    as_of_date: str
    history_start_date: str
    history_end_date: str
    factor_proxy_symbols: list[str] = Field(default_factory=list)
    benchmark_return_basis_contract: ReturnBasisContract
    factor_return_basis_contract: ReturnBasisContract
    factor_basis_path: ReturnBasisPathTrust | None = None
    section_trust: OptimizerReturnBasisSectionTrust
    evidence: OptimizerReturnBasisEvidenceBundle


class OptimizationReplayArtifact(BaseModel):
    ordered_symbols: list[str] = Field(default_factory=list)
    current_weights: list[OptimizerWeight] = Field(default_factory=list)
    benchmark_weights: list[OptimizerWeight] = Field(default_factory=list)
    target_weights: list[OptimizerWeight] = Field(default_factory=list)
    lower_bounds: list[OptimizerWeight] = Field(default_factory=list)
    upper_bounds: list[OptimizerWeight] = Field(default_factory=list)
    turnover_cap: float | None = None
    risk_package_id: str | None = None
    alpha_package_id: str | None = None


class OptimizationInputFingerprint(BaseModel):
    input_kind: OptimizerArtifactInputKind
    version: str
    fingerprint: str
    provenance: str
    as_of_timestamp: str | None = None
    effective_timestamp: str | None = None


class OptimizationPackageStamp(BaseModel):
    package_name: str
    package_id: str | None = None
    package_version: str
    package_status: str
    provenance: str
    as_of_timestamp: str | None = None
    effective_timestamp: str | None = None


class OptimizationArtifactStateSummary(BaseModel):
    artifact_state: OptimizerArtifactState
    feasibility_status: OptimizerStatus
    stale_inputs: list[str] = Field(default_factory=list)
    degraded_inputs: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)


class OptimizationBenchmarkRelativeAttestation(BaseModel):
    attestation_id: str
    attestation_type: OptimizerBenchmarkAttestationType
    constraint_id: str
    benchmark_id: str
    status: OptimizerConstraintStatus | Literal["aligned", "misaligned"]
    actual_value: float | None = None
    limit_value: float | None = None
    slack: float | None = None
    binding_symbols: list[str] = Field(default_factory=list)
    details: dict[str, str | float | bool] = Field(default_factory=dict)
    message: str


class OptimizationTradeIntent(BaseModel):
    symbol: str
    action: OptimizerTradeIntentAction
    current_weight: float = Field(ge=0.0, le=1.0)
    proposed_weight: float = Field(ge=0.0, le=1.0)
    active_weight: float = Field(ge=-1.0, le=1.0)
    trade_weight: float = Field(ge=-1.0, le=1.0)


class OptimizationArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: OptimizerArtifactSchemaVersion = "optimizer_artifact_v1"
    artifact_id: str
    request_id: str | None = None
    as_of_timestamp: str
    effective_timestamp: str
    universe_id: str
    benchmark_id: str
    input_fingerprints: list[OptimizationInputFingerprint] = Field(default_factory=list)
    package_stamps: list[OptimizationPackageStamp] = Field(default_factory=list)
    artifact_state: OptimizationArtifactStateSummary
    objective: OptimizerObjective = Field(default_factory=OptimizerObjective)
    hard_constraints: OptimizerHardConstraints
    penalties: list[OptimizerPenalty] = Field(default_factory=list)
    run_metadata: OptimizationRunMetadata
    feasibility: OptimizationFeasibilityDiagnostics
    benchmark_relative_attestations: list[OptimizationBenchmarkRelativeAttestation] = Field(default_factory=list)
    key_diagnostics: OptimizationExAnteDiagnostics = Field(default_factory=OptimizationExAnteDiagnostics)
    constraint_evaluations: list[OptimizationConstraintEvaluation] = Field(default_factory=list)
    proposed_weights: list[OptimizerWeight] = Field(default_factory=list)
    active_weights: list[OptimizerActiveWeight] = Field(default_factory=list)
    trade_intents: list[OptimizationTradeIntent] = Field(default_factory=list)
    failure_reasons: list[OptimizationIssue] = Field(default_factory=list)
    replay: OptimizationReplayArtifact


class OptimizationResult(BaseModel):
    request_id: str | None = None
    objective: OptimizerObjective
    hard_constraints: OptimizerHardConstraints
    penalties: list[OptimizerPenalty] = Field(default_factory=list)
    proposed_weights: list[OptimizerWeight] = Field(default_factory=list)
    active_weights: list[OptimizerActiveWeight] = Field(default_factory=list)
    feasibility: OptimizationFeasibilityDiagnostics
    constraint_evaluations: list[OptimizationConstraintEvaluation] = Field(default_factory=list)
    ex_ante_diagnostics: OptimizationExAnteDiagnostics = Field(default_factory=OptimizationExAnteDiagnostics)
    run_metadata: OptimizationRunMetadata
    replay: OptimizationReplayArtifact
    artifact: OptimizationArtifact | None = None


class OptimizerPreviewBenchmarkInput(BaseModel):
    benchmark_id: str
    benchmark_version: str
    benchmark_symbol: str | None = None
    source_name: str
    as_of_timestamp: str
    trust_status: Literal["trusted", "untrusted"] = "trusted"
    weights: list[OptimizerWeight] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_weights(self) -> "OptimizerPreviewBenchmarkInput":
        if not self.weights:
            raise ValueError("benchmark preview input must include weights")
        total_weight = sum(item.weight for item in self.weights)
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError("benchmark preview weights must sum to 1.0")
        return self


class OptimizerPreviewPitAlphaInput(BaseModel):
    source_kind: Literal["trusted_live_pit"] = "trusted_live_pit"
    as_of_date: str | None = None
    trust_required: Literal[True] = True


class OptimizerPreviewRequest(BaseModel):
    request_id: str | None = None
    universe_id: str | None = None
    snapshot: ImportedPortfolioSnapshot
    benchmark: OptimizerPreviewBenchmarkInput
    objective: OptimizerObjective = Field(default_factory=OptimizerObjective)
    hard_constraints: OptimizerHardConstraints
    penalties: list[OptimizerPenalty] = Field(default_factory=list)
    universe: list[OptimizerUniverseAsset] | None = None
    risk_package: OptimizerRiskPackage | None = None
    pit_alpha: OptimizerPreviewPitAlphaInput | None = None


class OptimizerPreviewSnapshotReference(BaseModel):
    snapshot_id: str
    account_id: str | None = None
    importer: str | None = None
    imported_at: str
    statement_period: str | None = None
    source_files: list[str] = Field(default_factory=list)


class OptimizerPersistedArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reference_kind: Literal["optimizer_handoff_reference_v1"] = "optimizer_handoff_reference_v1"
    handoff_id: str
    artifact_id: str
    manifest_path: str
    artifact_path: str


class OptimizerHandoffBenchmarkReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    benchmark_id: str
    benchmark_version: str
    benchmark_symbol: str | None = None
    source_name: str
    as_of_timestamp: str

    @field_validator("benchmark_symbol", mode="before")
    @classmethod
    def _canonicalize_benchmark_symbol(cls, value: str | None) -> str | None:
        return canonicalize_benchmark_symbol(value)


class OptimizerHandoffConstraintSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    constraint_set_version: str
    constraint_set_fingerprint: str
    hard_constraint_count: int = Field(ge=1)
    penalty_count: int = Field(ge=0)
    package_versions: dict[str, str] = Field(default_factory=dict)


class OptimizerHandoffManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: OptimizerHandoffSchemaVersion = "optimizer_handoff_manifest_v1"
    handoff_id: str
    artifact_id: str
    artifact_schema_version: OptimizerArtifactSchemaVersion
    artifact_as_of_timestamp: str
    artifact_effective_timestamp: str
    source_portfolio_snapshot: OptimizerPreviewSnapshotReference
    benchmark: OptimizerHandoffBenchmarkReference
    return_basis_attestation: OptimizerReturnBasisAttestation
    objective: OptimizerObjective
    optimizer_input_provenance: list[OptimizationInputFingerprint] = Field(default_factory=list)
    constraint_set: OptimizerHandoffConstraintSet
    package_stamps: list[OptimizationPackageStamp] = Field(default_factory=list)
    optimizer_output_target_weights: list[OptimizerWeight] = Field(default_factory=list)
    artifact_state: OptimizerArtifactState
    hypothetical: Literal[True] = True
    preview_only: Literal[True] = True
    replay_consumption_mode: Literal["explicit_reference_only"] = "explicit_reference_only"

    @model_validator(mode="after")
    def _validate_required_metadata(self) -> "OptimizerHandoffManifest":
        required_kinds = {"request", "universe", "benchmark", "constraints", "solver"}
        provenance_kinds = {item.input_kind for item in self.optimizer_input_provenance}
        if required_kinds - provenance_kinds:
            raise ValueError("handoff manifest is missing required optimizer input provenance")
        if len(provenance_kinds) != len(self.optimizer_input_provenance):
            raise ValueError("handoff manifest contains ambiguous duplicate optimizer input provenance entries")
        if not self.source_portfolio_snapshot.snapshot_id:
            raise ValueError("handoff manifest requires source_portfolio_snapshot.snapshot_id")
        if not self.benchmark.benchmark_version:
            raise ValueError("handoff manifest requires benchmark.benchmark_version")
        if not self.optimizer_output_target_weights:
            raise ValueError("handoff manifest requires optimizer_output_target_weights")
        return self


class OptimizerPreviewTruthSeparation(BaseModel):
    current_holdings_truth: Literal["imported_portfolio_snapshot"] = "imported_portfolio_snapshot"
    optimized_output_truth: Literal["hypothetical_optimizer_preview"] = "hypothetical_optimizer_preview"
    optimized_output_applied: Literal[False] = False
    optimized_output_storage: Literal["optimizer_artifact_only"] = "optimizer_artifact_only"
    replay_role: Literal["downstream_evaluation_only"] = "downstream_evaluation_only"


class OptimizerPreviewProvenance(BaseModel):
    workflow_id: Literal["optimizer_preview_workflow_v1"] = "optimizer_preview_workflow_v1"
    snapshot_reference: OptimizerPreviewSnapshotReference
    benchmark_source_name: str
    benchmark_trust_status: Literal["trusted"] = "trusted"
    return_basis_attestation: OptimizerReturnBasisAttestation
    risk_input_status: Literal["not_requested", "provided", "required_but_missing", "invalid"]
    alpha_input_status: Literal["not_requested", "trusted_pit_attached", "trusted_pit_degraded"]


class OptimizerPreviewReplayHandoff(BaseModel):
    handoff_kind: Literal["portfolio_allocation_replay_candidate_v1"] = "portfolio_allocation_replay_candidate_v1"
    status: Literal["hypothetical_not_applied"] = "hypothetical_not_applied"
    applied: Literal[False] = False
    source_artifact_id: str
    source_portfolio_snapshot_id: str
    benchmark_id: str
    benchmark_version: str
    benchmark_symbol: str | None = None
    handoff_reference: OptimizerPersistedArtifactReference
    current_snapshot_reference: OptimizerPreviewSnapshotReference
    ready_for_replay: bool = True
    note: str = (
        "Replay handoff remains downstream-only. Consumers must load the persisted manifest and artifact by explicit reference; snapshot-derived current holdings remain truth, and optimizer targets remain hypothetical until a later explicit workflow applies them."
    )


class OptimizerPreviewResponse(BaseModel):
    workflow_id: Literal["optimizer_preview_workflow_v1"] = "optimizer_preview_workflow_v1"
    optimizer_status: OptimizerStatus
    truth_separation: OptimizerPreviewTruthSeparation = Field(default_factory=OptimizerPreviewTruthSeparation)
    provenance: OptimizerPreviewProvenance
    persisted_handoff: OptimizerPersistedArtifactReference | None = None
    feasibility: OptimizationFeasibilityDiagnostics
    run_metadata: OptimizationRunMetadata
    ex_ante_diagnostics: OptimizationExAnteDiagnostics = Field(default_factory=OptimizationExAnteDiagnostics)
    constraint_evaluations: list[OptimizationConstraintEvaluation] = Field(default_factory=list)
    optimizer_artifact: OptimizationArtifact
    replay_handoff: OptimizerPreviewReplayHandoff | None = None
