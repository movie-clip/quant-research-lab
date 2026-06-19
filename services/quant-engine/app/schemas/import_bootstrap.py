from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioHistoryContext
from app.schemas.reconciliation import PortfolioOverview, PortfolioRiskSummary


ImportAdmissionDecision = Literal["admitted", "degraded", "withheld"]
ImportAdmissionTrustLevel = Literal["verified", "degraded", "withheld", "unavailable"]
ImportAdmissionCheckStatus = Literal["pass", "warn", "fail", "unavailable"]
ImportAdmissionCheckSeverity = Literal["info", "warning", "error"]
ImportAdmissionTrustImpact = Literal["none", "degraded", "withheld", "unavailable"]


class ImportAdmissionCheckValue(BaseModel):
    label: str
    value: FiniteFloat | str | None = None


class ImportAdmissionCheckV1(BaseModel):
    check_id: str
    status: ImportAdmissionCheckStatus
    severity: ImportAdmissionCheckSeverity
    trust_impact: ImportAdmissionTrustImpact
    message: str
    affected_fields: list[str] = Field(default_factory=list)
    observed: ImportAdmissionCheckValue | None = None
    comparison: ImportAdmissionCheckValue | None = None
    delta: FiniteFloat | None = None
    currency: str | None = None


class ImportAdmissionProvenanceV1(BaseModel):
    importer: str | None = None
    statement_ids: list[str] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)
    generated_at: datetime
    tolerance_policy: str


class ImportAdmissionSummaryV1(BaseModel):
    schema_version: Literal["import_admission_summary_v1"] = "import_admission_summary_v1"
    decision: ImportAdmissionDecision
    trust_level: ImportAdmissionTrustLevel
    checks: list[ImportAdmissionCheckV1]
    provenance: ImportAdmissionProvenanceV1


class ImportedBootstrapResponse(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    overview: PortfolioOverview
    risk_summary: PortfolioRiskSummary
    admission_summary: ImportAdmissionSummaryV1
    history_context: PortfolioHistoryContext | None = None
