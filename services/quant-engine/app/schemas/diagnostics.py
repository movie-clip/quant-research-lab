from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioEngineRequest, PortfolioHistoryContext
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


class DiagnosticsProvenance(BaseModel):
    snapshot_basis: Literal["imported_snapshot", "snapshot_request"]
    historical_basis: Literal["imported_portfolio_history", "market_data_history", "unavailable"]
    note: str


class DiagnosticsDrawdownSummary(BaseModel):
    current_drawdown_pct: float | None = None
    max_drawdown_pct: float | None = None


class DiagnosticsVolatilitySummary(BaseModel):
    portfolio_volatility_pct: float | None = None
    benchmark_volatility_pct: float | None = None
    downside_volatility_pct: float | None = None
    tracking_error_pct: float | None = None


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
    drawdown_summary: DiagnosticsDrawdownSummary
    volatility_summary: DiagnosticsVolatilitySummary
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
