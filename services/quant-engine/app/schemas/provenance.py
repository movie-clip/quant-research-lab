"""Pydantic schemas for the portfolio data-provenance engine (US-18.2).

Reports which market-data provider (FMP primary vs Yahoo Finance secondary)
priced each holding, or that a holding is unpriced. Source label only — this is
not a return-basis trust claim.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.imports import ImportedPortfolioSnapshot

ProvenanceVendor = Literal["fmp", "yfinance", "unavailable"]


class ProvenanceRequest(BaseModel):
    snapshot: ImportedPortfolioSnapshot
    # Short probe window (trading days) — provider identity is window-independent.
    lookback_days: int = Field(default=30, ge=1)


class HoldingProvenance(BaseModel):
    symbol: str
    vendor: ProvenanceVendor


class InstrumentIdentityMismatch(BaseModel):
    """A holding whose broker-statement description is identity-disjoint from the
    registry's fund name for that ticker (US-19.1) — a possible mislabel."""
    symbol: str
    statement_description: str
    registry_name: str


class ProvenanceResult(BaseModel):
    holdings: list[HoldingProvenance]
    fmp_symbols: list[str]
    yahoo_sourced_symbols: list[str]
    unavailable_symbols: list[str]
    # Holdings whose statement description disagrees with the registry fund name
    # (possible ticker→fund mislabel). Flag only — never auto-corrected. (US-19.1)
    identity_warnings: list[InstrumentIdentityMismatch] = Field(default_factory=list)
    lookback_days: int
