from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


AssetClass = Literal["equity", "etf", "future", "forex", "index", "crypto", "other"]
InstrumentKind = Literal["spot", "continuous_future", "future_contract"]

# Provenance of `Instrument.sector` (US-37.1). Never "verified" — that word is
# reserved for `verified_total_return`'s distinct, narrower meaning (guardrail
# 3: truth-class separation). "static" = curated INSTRUMENT_DEFINITIONS hit.
# "fmp_identity_confirmed" = resolved via FMP company profile, accepted only
# because the statement's ISIN and the FMP profile's ISIN were both present
# and matched. "unavailable" = an FMP resolution attempt was made and did not
# clear the identity gate (mismatch, missing evidence either side, no/empty
# profile, unmapped sector string, or lookup failure) — collapsed to one value
# by design (see 05-technical-plan.md § Decisions #3); the distinction between
# these sub-cases is preserved only in code structure, not exposed.
ClassificationSource = Literal["static", "fmp_identity_confirmed", "unavailable"]


class Instrument(BaseModel):
    instrument_id: str
    symbol: str
    name: str | None = None
    asset_class: AssetClass
    kind: InstrumentKind
    sector: str | None = None
    category: str | None = None
    exchange: str | None = None
    currency: str | None = None
    tick_size: float | None = None
    point_value: float | None = None
    multiplier: float | None = None
    # Authoritative ISIN sourced from real broker statements (US-19.2). Used to
    # validate the statement's ISIN against the registry mapping at import.
    # None = not yet sourced → the ISIN identity check skips this instrument.
    isin: str | None = None
    # None = this instrument's classification mechanism was not invoked on
    # this code path (e.g. ETF branch, futures, no-imported-instrument
    # catchall, or a static-dict hit reached via any path other than
    # `_merge_known_instrument_metadata`) — not a claim that no provenance
    # exists, just that this story didn't touch or verify that path. Backend-
    # internal only; never serialized to the client (US-37.1).
    classification_source: ClassificationSource | None = None


class FuturesContract(BaseModel):
    instrument_id: str
    root_symbol: str
    contract_symbol: str
    exchange: str
    currency: str
    expiry_date: date
    first_notice_date: date | None = None
    tick_size: float | None = None
    point_value: float | None = None
    multiplier: float | None = None
