from typing import Literal

from pydantic import BaseModel, Field


ReturnBasisVerificationStatus = Literal["verified", "proxy", "unverified", "unavailable"]
ReturnBasisEconomicBasis = Literal["total_return", "adjusted_close_proxy", "price_return_only", "unavailable"]
ReturnBasisConstructionMethod = Literal[
    "vendor_adjusted_close",
    "raw_close",
    "synthetic_snapshot_history",
    "sample_dataset",
    "unknown",
]


class ReturnBasisEvidence(BaseModel):
    verification_status: ReturnBasisVerificationStatus
    economic_basis: ReturnBasisEconomicBasis
    construction_method: ReturnBasisConstructionMethod
    disqualifiers: list[str] = Field(default_factory=list)
    fallbacks_used: list[str] = Field(default_factory=list)
    source_price_field: str | None = None
    scope: dict[str, str | bool | int | None] = Field(default_factory=dict)


PortfolioProofPathStatus = Literal["withheld", "unverified", "unavailable"]
PortfolioProofVerificationStatus = Literal["unverified", "unavailable"]
PortfolioProofOutputStatus = Literal["withheld", "unavailable"]
PortfolioProofBucketStatus = Literal["supported", "disqualified", "unavailable"]
PortfolioProofReplayStatus = Literal["replay_usable", "replay_unavailable"]
PortfolioProofAdmissionStatus = Literal["withheld", "rejected", "not_applicable"]
PortfolioProofOpeningStateStatus = Literal[
    "opening_state_verified",
    "opening_state_unverified",
    "opening_state_unavailable",
]
PortfolioCorporateActionScope = Literal["broker_native_statement_window", "broker_scope_unproven"]
PortfolioCashDividendCoverageStatus = Literal[
    "cash_dividend_coverage_proven_by_broker_native_evidence",
    "cash_dividend_coverage_unproven",
]
PortfolioCashDividendObservationStatus = Literal[
    "cash_dividend_observed_by_broker_native_evidence",
    "no_cash_dividend_observed_within_covered_broker_scope",
    "cash_dividend_observation_unproven",
]
PortfolioNonDividendCorporateActionStatus = Literal["non_dividend_corporate_actions_unproven_and_disqualifying"]


class PortfolioProofWitness(BaseModel):
    label: str
    status: str
    evidence: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)


class PortfolioProofBucketEvidence(BaseModel):
    status: PortfolioProofBucketStatus
    positive_evidence: list[str] = Field(default_factory=list)
    negative_evidence: list[str] = Field(default_factory=list)
    disqualifiers: list[str] = Field(default_factory=list)
    hard_disqualifiers: list[str] = Field(default_factory=list)
    witnesses: list[PortfolioProofWitness] = Field(default_factory=list)


class PortfolioCorporateActionBasisPolicy(BaseModel):
    """Machine-readable scope policy for the narrow broker-native cash-dividend proof gate."""

    scope: PortfolioCorporateActionScope
    cash_dividend_coverage_status: PortfolioCashDividendCoverageStatus
    cash_dividend_observation_status: PortfolioCashDividendObservationStatus
    non_dividend_status: PortfolioNonDividendCorporateActionStatus
    scope_start_date: str | None = None
    scope_end_date: str | None = None
    statement_window_count: int = 0


class PortfolioCorporateActionBasisEvidence(PortfolioProofBucketEvidence):
    policy: PortfolioCorporateActionBasisPolicy


class PortfolioProofAdmissionBlockingReason(BaseModel):
    code: str
    bucket: str
    provenance_bucket: str
    reason_type: Literal["blocking", "missing", "scope_mismatch", "withheld"]


class PortfolioProofAdmissionBucketDecision(BaseModel):
    bucket: str
    status: PortfolioProofAdmissionStatus
    blocks_admission: bool = False
    provenance_buckets: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    scope: dict[str, str | bool | int | None] = Field(default_factory=dict)


class PortfolioProofAdmissionDecision(BaseModel):
    status: PortfolioProofAdmissionStatus
    scope: dict[str, str | bool | int | None] = Field(default_factory=dict)
    blocking_reasons: list[PortfolioProofAdmissionBlockingReason] = Field(default_factory=list)
    missing_proof_buckets: list[str] = Field(default_factory=list)
    bucket_decisions: list[PortfolioProofAdmissionBucketDecision] = Field(default_factory=list)


class PortfolioProofEvidenceBundle(BaseModel):
    opening_state_basis: PortfolioProofBucketEvidence
    valuation_basis: PortfolioProofBucketEvidence
    cash_flow_basis: PortfolioProofBucketEvidence
    fx_basis: PortfolioProofBucketEvidence
    corporate_action_basis: PortfolioCorporateActionBasisEvidence
    terminal_reconciliation_basis: PortfolioProofBucketEvidence
    calendar_coverage_basis: PortfolioProofBucketEvidence


class PortfolioProofMetadata(BaseModel):
    proof_system: str
    portfolio_path: PortfolioProofPathStatus
    verification_status: PortfolioProofVerificationStatus
    output_status: PortfolioProofOutputStatus
    replay_status: PortfolioProofReplayStatus
    opening_state_status: PortfolioProofOpeningStateStatus
    verified_total_return_emitted: bool = False
    benchmark_proof_independent: bool = True
    disqualifiers: list[str] = Field(default_factory=list)
    hard_disqualifiers: list[str] = Field(default_factory=list)
    admission: PortfolioProofAdmissionDecision
    evidence: PortfolioProofEvidenceBundle
