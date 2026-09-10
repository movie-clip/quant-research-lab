from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.dashboard_history import DashboardHistoryInvestorEconomicsPartialUnlock, InvestorEconomicsStatus
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioEngineRequest, PortfolioHistoryContext
from app.schemas.return_basis import PortfolioProofMetadata, ReturnBasisEvidence
from app.schemas.reconciliation import (
    FactorExposurePoint,
    FactorProxyDefinition,
    FactorShiftDiagnosticsPayload,
    ModelReliabilitySnapshot,
    PortfolioRiskSummary,
    RelativeRiskSummary,
    RiskContributionBreakdownPayload,
    RollingRiskPoint,
    StatisticalFactorModel,
    StressScenarioResult,
    VolatilityRegimePayload,
)


class DiagnosticsEngineRequest(PortfolioEngineRequest):
    history_context: PortfolioHistoryContext | None = None


class DiagnosticsAvailability(BaseModel):
    historical_sections_available: bool
    history_context_required: bool = True
    note: str | None = None
    status: Literal["ok", "unavailable"] = "ok"


class DiagnosticsProvenance(BaseModel):
    snapshot_basis: Literal["imported_snapshot", "snapshot_request"]
    historical_basis: Literal["imported_portfolio_history", "market_data_history", "unavailable"]
    history_truth_class: Literal["imported_history_equivalent", "synthetic_history_derived", "unavailable"]
    price_basis: Literal["close", "unavailable"]
    note: str


class DiagnosticsSourceStatus(BaseModel):
    portfolio_history: Literal["imported_replay", "synthetic_snapshot_history", "unavailable"]
    benchmark_history: Literal["live_market_data_verified_adjusted_close", "live_market_data_unverified_return_basis", "unavailable"]
    factor_history: Literal["live_market_data_verified_adjusted_close", "live_market_data_unverified_return_basis", "unavailable"]


class DiagnosticsRunMetadata(BaseModel):
    class SectionTrust(BaseModel):
        benchmark_relative_path: Literal["verified_adjusted_close", "degraded_unverified_return_basis", "unavailable"]
        factor_model_path: Literal["verified_adjusted_close", "degraded_unverified_return_basis", "unavailable"]
        risk_contribution_path: Literal["verified_adjusted_close", "degraded_unverified_return_basis", "unavailable"]

    class FactorModelParameters(BaseModel):
        rolling_windows_days: list[int]
        current_reliability_window_days: int
        minimum_window_observations: dict[str, int]
        collinearity_warning_threshold: float
        orthogonalization_basis: str
        ridge_lambda: float

    class ReproducibilityMetadata(BaseModel):
        input_imported_at: str | None = None
        snapshot_as_of_date: str | None = None
        history_start_date: str | None = None
        history_end_date: str | None = None
        dataset_version: str

    class ReturnBasisEvidenceBundle(BaseModel):
        portfolio_history: ReturnBasisEvidence
        benchmark_history: ReturnBasisEvidence
        factor_history: ReturnBasisEvidence

    diagnostics_id: str
    methodology_id: str
    price_basis: Literal["close", "unavailable"]
    source_status: DiagnosticsSourceStatus
    section_trust: SectionTrust
    return_basis_evidence: ReturnBasisEvidenceBundle
    portfolio_proof: PortfolioProofMetadata
    investor_economics_status: InvestorEconomicsStatus
    investor_economics_partial_unlock: DashboardHistoryInvestorEconomicsPartialUnlock
    confidence: Literal["high", "medium", "low"]
    factor_model_parameters: FactorModelParameters
    reproducibility: ReproducibilityMetadata


class DiagnosticsDrawdownSummary(BaseModel):
    current_drawdown_pct: float | None = None
    max_drawdown_pct: float | None = None


class DiagnosticsVolatilitySummary(BaseModel):
    portfolio_volatility_pct: float | None = None
    benchmark_volatility_pct: float | None = None
    downside_volatility_pct: float | None = None
    tracking_error_pct: float | None = None


RiskTabVolatilityTrust = Literal["synthetic", "withheld", "unavailable"]


class RiskTabAnnualizedVolatility(BaseModel):
    """Risk-tab publication-gated view of the SAME scalar as
    ``volatility_summary.portfolio_volatility_pct`` (US-44.1).

    Not a recomputation: ``annualized_volatility_pct`` is copied straight from
    ``risk_summary.portfolio_volatility_pct`` when the paired-observation floor
    (``RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS`` = 60) is met, and is then
    byte-identical to the Dashboard figure for the same response.

    Formula (unchanged, one documented code path):
    ``stdev_sample(daily_returns) * sqrt(252) * 100`` — sample (N-1) standard
    deviation, square-root-of-time annualization; ``_calculate_annualized_volatility``
    in ``analytics/risk.py``. Units: percent, already x100 (``_pct`` suffix).
    Truth class: synthetic history (current holdings x historical prices).
    Methodology: ``docs/finance/financial-methodology.md`` section
    "Annualized realized volatility".

    Trust rungs, on the paired daily-return observation count N:
      * ``N >= 60``     -> ``synthetic``   : published, value non-null
      * ``1 <= N < 60`` -> ``withheld``    : series exists but the annualized
                                             projection over a sub-quarter sample
                                             is not trustworthy; value null
      * ``N == 0``      -> ``unavailable`` : no return series; value null
    ``withheld`` is never serialized or collapsed to ``unavailable`` (guardrail 4).
    """

    annualized_volatility_pct: float | None = None
    trust: RiskTabVolatilityTrust = "unavailable"
    observations: int = 0
    minimum_observations: int


class DiagnosticsRiskConcentrationSummary(BaseModel):
    top_1_factor_risk_share: float | None = None
    top_3_factor_risk_share: float | None = None
    top_1_position_risk_share: float | None = None
    top_5_position_risk_share: float | None = None
    factor_hhi: float | None = None
    position_hhi: float | None = None


class DiagnosticsResult(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    provenance: DiagnosticsProvenance
    availability: DiagnosticsAvailability
    run_metadata: DiagnosticsRunMetadata
    drawdown_summary: DiagnosticsDrawdownSummary
    volatility_summary: DiagnosticsVolatilitySummary
    risk_tab_volatility: RiskTabAnnualizedVolatility
    risk_concentration_summary: DiagnosticsRiskConcentrationSummary
    risk_summary: PortfolioRiskSummary
    rolling_risk: list[RollingRiskPoint]
    relative_risk: RelativeRiskSummary
    volatility_regime: VolatilityRegimePayload
    factor_exposures: list[FactorExposurePoint]
    factor_shift_diagnostics: FactorShiftDiagnosticsPayload
    risk_contribution_breakdown: RiskContributionBreakdownPayload
    model_reliability: ModelReliabilitySnapshot
    factor_registry: list[FactorProxyDefinition] = Field(default_factory=list)
    factor_methodology: str | None = None
    statistical_factor_model: StatisticalFactorModel
    stress_scenarios: list[StressScenarioResult]
