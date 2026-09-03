from typing import Literal

from pydantic import BaseModel, Field


ReturnBasisContract = Literal["verified_total_return", "price_return_only", "unverified_adjusted_proxy", "unavailable"]
ReturnBasisPathTrust = Literal["verified_adjusted_close", "degraded_unverified_return_basis", "unavailable"]
ReturnBasisVerificationStatus = Literal["verified", "proxy", "unverified", "unavailable"]
ReturnBasisEconomicBasis = Literal["total_return", "adjusted_close_proxy", "price_return_only", "unavailable"]
ReturnBasisConstructionMethod = Literal[
    "vendor_adjusted_close",
    "raw_close",
    "synthetic_snapshot_history",
    "sample_dataset",
    "unknown",
]

# Return-series basis selected by provenance (US-30.5c / PRD F-10; third basis
# added by US-24.9).
# "portfolio_value": cash-flow-neutral TWR on total_portfolio_value — trade-safe
#   but cash-INCLUSIVE, so it stays the investor-performance basis.
# "market_value": plain market-value chain on total_market_value — excludes the
#   flat synthetic cash balance, used ONLY on synthetic series (no trades).
# "market_value_trade_neutral": market-value chain with the day's trade leg
#   removed — cash-excluded AND trade-safe, so the imported ledger-replay path's
#   RISK statistics can drop their cash sleeve without reading a BUY as a gain.
# See methodology §Rolling Pearson Correlation / §Indexed Return Series.
ReturnBasis = Literal["portfolio_value", "market_value", "market_value_trade_neutral"]


class ReturnBasisEvidence(BaseModel):
    verification_status: ReturnBasisVerificationStatus
    economic_basis: ReturnBasisEconomicBasis
    construction_method: ReturnBasisConstructionMethod
    disqualifiers: list[str] = Field(default_factory=list)
    fallbacks_used: list[str] = Field(default_factory=list)
    source_price_field: str | None = None
    scope: dict[str, str | bool | int | None] = Field(default_factory=dict)


PortfolioProofPathStatus = Literal["verified", "withheld", "unverified", "unavailable"]
PortfolioProofVerificationStatus = Literal["verified", "unverified", "unavailable"]
PortfolioProofOutputStatus = Literal["available", "withheld", "unavailable"]
PortfolioProofBucketStatus = Literal["supported", "disqualified", "unavailable"]
PortfolioProofReplayStatus = Literal["replay_usable", "replay_unavailable"]
PortfolioProofAdmissionStatus = Literal["admitted", "withheld", "rejected", "not_applicable"]
PortfolioProofPreparationStatus = Literal[
    "exact_slice_admitted",
    "exact_slice_prerequisites_incomplete",
    "exact_slice_ready_but_withheld_by_policy",
    "not_applicable",
]
PortfolioProofPreparationGapType = Literal[
    "blocking",
    "missing",
    "scope_unproven",
    "scope_mismatch",
    "policy_withheld",
]
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
PortfolioNonDividendCorporateActionStatus = Literal[
    "no_non_dividend_corporate_actions_observed_within_covered_broker_scope",
    "non_dividend_corporate_actions_unproven_and_disqualifying",
]


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


class PortfolioInvestorEconomicsProofEvidence(PortfolioProofBucketEvidence):
    claim_id: str
    claim: str
    decision: PortfolioProofAdmissionStatus
    preparation_status: PortfolioProofPreparationStatus
    required_inputs: list[str] = Field(default_factory=list)
    blocking_reasons: list[str] = Field(default_factory=list)
    missing_proof_buckets: list[str] = Field(default_factory=list)
    scope_mismatches: list[str] = Field(default_factory=list)
    scope: dict[str, str | bool | int | None] = Field(default_factory=dict)


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


class PortfolioProofPreparationGap(BaseModel):
    code: str
    bucket: str
    provenance_buckets: list[str] = Field(default_factory=list)
    gap_type: PortfolioProofPreparationGapType


class PortfolioProofWindowTarget(BaseModel):
    start_date: str | None = None
    end_date: str | None = None
    count: int = 0


class PortfolioProofOpeningStateAnchorTarget(BaseModel):
    required_anchor_date: str | None = None
    observed_anchor_date: str | None = None
    status: str


class PortfolioProofFxScopeTarget(BaseModel):
    translation_case: str
    base_currency: str | None = None
    observed_currencies: list[str] = Field(default_factory=list)
    required_pairs: list[str] = Field(default_factory=list)
    required_pair_dates: list[str] = Field(default_factory=list)


class PortfolioProofCorporateActionScopeTarget(BaseModel):
    scope: PortfolioCorporateActionScope
    scope_start_date: str | None = None
    scope_end_date: str | None = None
    statement_window_count: int = 0
    positive_proof_classes: list[str] = Field(default_factory=list)
    unproven_disqualifying_classes: list[str] = Field(default_factory=list)


class PortfolioProofExactSliceTarget(BaseModel):
    account_set: list[str] = Field(default_factory=list)
    base_currency: str | None = None
    valuation_window: PortfolioProofWindowTarget
    statement_window: PortfolioProofWindowTarget
    opening_state_anchor: PortfolioProofOpeningStateAnchorTarget
    fx_scope: PortfolioProofFxScopeTarget
    corporate_action_scope: PortfolioProofCorporateActionScopeTarget


class PortfolioProofPreparationMetadata(BaseModel):
    readiness_status: PortfolioProofPreparationStatus
    all_prerequisite_buckets_supported: bool = False
    exact_slice_target: PortfolioProofExactSliceTarget
    readiness_gaps: list[PortfolioProofPreparationGap] = Field(default_factory=list)
    policy_blockers: list[PortfolioProofPreparationGap] = Field(default_factory=list)


class PortfolioProofAdmissionDecision(BaseModel):
    status: PortfolioProofAdmissionStatus
    readiness_status: PortfolioProofPreparationStatus
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
    investor_economics_proof: PortfolioInvestorEconomicsProofEvidence


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
    preparation: PortfolioProofPreparationMetadata
    admission: PortfolioProofAdmissionDecision
    evidence: PortfolioProofEvidenceBundle
