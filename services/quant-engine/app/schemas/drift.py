from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from app.schemas.portfolio_engine import PortfolioEngineRequest


DriftTrustLevel = Literal["synthetic", "unavailable"]


class DriftWindow(BaseModel):
    label: str  # "1M", "3M", "6M", "12M", "Since Import"
    start_date: str | None = None
    end_date: str | None = None
    portfolio_return_pct: float | None = None
    benchmark_return_pct: float | None = None
    spread_pct: float | None = None  # portfolio - benchmark
    trust: DriftTrustLevel = "unavailable"
    note: str | None = None


class DriftDailyPoint(BaseModel):
    date: str
    # US-27.8: the portfolio line is the compounded cash-flow-neutral TWR
    # chain indexed to 100.0 at the series start (deposits/withdrawals/trades
    # are not chart moves) — see methodology §Indexed Return Series.
    portfolio_indexed: float | None = None
    benchmark_indexed: float | None = None


class DriftEngineRequest(PortfolioEngineRequest):
    # benchmark_symbol (default "SPY") and imported_at already in PortfolioEngineRequest.
    # US-30.2 (audit F-6): statement-implied FX rates from the imported
    # snapshot's statement_totals.fx_rates (broker truth as of the statement
    # period end, US-28.1), keyed "EURUSD"-style. Applied as STATIC rates to
    # every valuation date; currencies converted this way are disclosed in
    # DriftResult.fx_static_rate_currencies. Empty → US-27.8 fallback tier.
    fx_rates: dict[str, float] = {}


class DriftResult(BaseModel):
    windows: list[DriftWindow]
    benchmark_symbol: str
    daily_series: list[DriftDailyPoint]
    availability: Literal["available", "partial", "unavailable"]
    # US-27.8 (audit F9): currencies for which a base-currency conversion was
    # required but no FX rate was available — the affected values are carried
    # UNCONVERTED (never silently pretended to be converted). Non-empty means
    # the replay's valuations are degraded for these currencies; the UI must
    # surface it. Empty when every position is base-currency or converted.
    fx_fallback_currencies: list[str] = []
    # US-30.2 (audit F-6): currencies converted at the statement's implied
    # period-end rate (a STATIC rate across the window — levels are broker
    # truth as of period end, FX return dynamics are still absent). Distinct
    # from the fallback tier above: converted, but not with a daily series.
    fx_static_rate_currencies: list[str] = []
    # US-30.2 (audit F-3): held symbols valued FLAT at the statement close
    # price for the whole window (zero in-window price coverage) — zero
    # return contribution, dampening returns/volatility. Never silent.
    statement_anchored_symbols: list[str] = []
