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


class DiagnosticsResult(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    availability: DiagnosticsAvailability
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
