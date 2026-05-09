from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat, field_validator

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioHistoryContext
from app.schemas.reconciliation import PortfolioOverview, PortfolioRiskSummary


ImportAdmissionDecision = Literal["admitted", "degraded", "withheld"]
ImportAdmissionTrustLevel = Literal["verified", "degraded", "withheld", "unavailable"]
ImportAdmissionCheckStatus = Literal["pass", "warn", "fail", "unavailable"]
ImportAdmissionReviewEvidenceStatus = Literal["warn", "fail", "unavailable"]
ImportAdmissionCheckSeverity = Literal["info", "warning", "error"]
ImportAdmissionTrustImpact = Literal["none", "degraded", "withheld", "unavailable"]
ImportAdmissionReviewDisposition = Literal["accepted_known_exception", "needs_source_correction", "deferred"]


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


class ImportAdmissionReviewEvidenceSummaryV1(BaseModel):
    status: ImportAdmissionReviewEvidenceStatus
    trust_impact: ImportAdmissionTrustImpact
    message: str
    affected_fields: list[str] = Field(default_factory=list)
    observed: ImportAdmissionCheckValue | None = None
    comparison: ImportAdmissionCheckValue | None = None
    delta: FiniteFloat | None = None
    currency: str | None = None


class ImportAdmissionReviewDispositionV1(BaseModel):
    schema_version: Literal["import_admission_review_disposition_v1"] = "import_admission_review_disposition_v1"
    check_id: str
    disposition: ImportAdmissionReviewDisposition
    rationale: str = Field(min_length=1)
    reviewed_at: datetime
    reviewer_label: str
    snapshot_fingerprint: str
    admission_summary_fingerprint: str
    evidence_summary: ImportAdmissionReviewEvidenceSummaryV1

    @field_validator("rationale")
    @classmethod
    def rationale_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rationale must be non-empty")
        return value


class ImportedBootstrapResponse(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    overview: PortfolioOverview
    risk_summary: PortfolioRiskSummary
    admission_summary: ImportAdmissionSummaryV1
    history_context: PortfolioHistoryContext | None = None
