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
    witnesses: list[PortfolioProofWitness] = Field(default_factory=list)


class PortfolioProofEvidenceBundle(BaseModel):
    opening_state_basis: PortfolioProofBucketEvidence
    valuation_basis: PortfolioProofBucketEvidence
    cash_flow_basis: PortfolioProofBucketEvidence
    fx_basis: PortfolioProofBucketEvidence
    corporate_action_basis: PortfolioProofBucketEvidence
    terminal_reconciliation_basis: PortfolioProofBucketEvidence
    calendar_coverage_basis: PortfolioProofBucketEvidence


class PortfolioProofMetadata(BaseModel):
    proof_system: str
    portfolio_path: PortfolioProofPathStatus
    verification_status: PortfolioProofVerificationStatus
    output_status: PortfolioProofOutputStatus
    verified_total_return_emitted: bool = False
    benchmark_proof_independent: bool = True
    disqualifiers: list[str] = Field(default_factory=list)
    evidence: PortfolioProofEvidenceBundle
