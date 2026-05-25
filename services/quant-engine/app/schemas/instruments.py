from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


AssetClass = Literal["equity", "etf", "future", "forex", "index", "crypto", "other"]
InstrumentKind = Literal["spot", "continuous_future", "future_contract"]


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
