from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, FiniteFloat

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL
from app.schemas.exposure import ExposureAvailability, ExposureCurrentStateConcentration
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioHistoryContext
from app.schemas.reconciliation import (
    LookThroughOverview,
    LookThroughSectorExposure,
    MarketOverlapSummary,
    PortfolioOverview,
    PortfolioRiskSummary,
)


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


ImportAdmissionConstituentOrigin = Literal["statement", "carried"]


class ImportAdmissionConstituentV1(BaseModel):
    """One input's own admission, kept alongside the combined roll-up (US-46.3).

    ``origin="statement"``: the admission engine ran on that input snapshot
    (one per input, in input order). ``origin="carried"``: evidence recorded
    earlier and passed back in by the caller (legacy saved nodes only, D-11);
    listed after every statement constituent. Truth class: Broker Truth
    evidence; nothing here is a market or synthetic-history value.
    """

    origin: ImportAdmissionConstituentOrigin
    statement_ids: list[str] = Field(default_factory=list)
    source_names: list[str] = Field(default_factory=list)
    decision: ImportAdmissionDecision
    trust_level: ImportAdmissionTrustLevel
    checks: list[ImportAdmissionCheckV1]


class ImportAdmissionRollupV1(BaseModel):
    """Combined-portfolio admission roll-up (US-46.3, decision D-3).

    Rule ``weakest_of_constituents_and_combined_snapshot``: the summary's
    top-level ``decision`` and ``trust_level`` are the weakest (highest rank)
    across ``combined_snapshot_*`` and every constituent, on the ladders
    decision admitted < degraded < withheld and trust verified < degraded <
    withheld < unavailable. No numeric tolerance is changed and no rung is
    raised. Methodology: docs/finance/financial-methodology.md, Import
    admission rule (combined-snapshot paragraph pending the docs close-out).
    """

    rule: Literal["weakest_of_constituents_and_combined_snapshot"]
    combined_snapshot_decision: ImportAdmissionDecision
    combined_snapshot_trust_level: ImportAdmissionTrustLevel
    constituents: list[ImportAdmissionConstituentV1]


class ImportAdmissionSummaryV1(BaseModel):
    schema_version: Literal["import_admission_summary_v1"] = "import_admission_summary_v1"
    decision: ImportAdmissionDecision
    trust_level: ImportAdmissionTrustLevel
    checks: list[ImportAdmissionCheckV1]
    provenance: ImportAdmissionProvenanceV1
    # None for a single input with no carried evidence (single-statement rules unchanged).
    rollup: ImportAdmissionRollupV1 | None = None


class CombinedImportBootstrapRequest(BaseModel):
    """POST /portfolios/import/analyze-combined (US-46.1 / US-46.3).

    ``snapshots`` are individual input snapshots; the engine combines them flat
    with the one merge (same account replaces, distinct accounts sum) and rolls
    up admission. ``carried_admissions`` is legacy-node evidence only: saved
    admission summaries recorded earlier whose statements are not among
    ``snapshots``.
    """

    snapshots: list[ImportedPortfolioSnapshot] = Field(min_length=1)
    benchmark_symbol: str = DEFAULT_BENCHMARK_SYMBOL
    symbol_overrides: dict[str, list[str]] = Field(default_factory=dict)
    carried_admissions: list[ImportAdmissionSummaryV1] = Field(default_factory=list)


class ImportedBootstrapResponse(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    overview: PortfolioOverview
    lookthrough: LookThroughOverview
    lookthrough_sector_exposure: list[LookThroughSectorExposure]
    market_overlap: MarketOverlapSummary
    current_state_concentration: ExposureCurrentStateConcentration
    availability: ExposureAvailability
    risk_summary: PortfolioRiskSummary
    admission_summary: ImportAdmissionSummaryV1
    history_context: PortfolioHistoryContext | None = None
    # Individual input snapshots, set only by the multi-file upload/analyze path
    # when more than one file was combined. Empty for a single input and on
    # analyze-combined (the caller already holds its inputs).
    constituent_snapshots: list[ImportedPortfolioSnapshot] = Field(default_factory=list)
