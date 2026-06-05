"""Attribution engine service.

Wires together market data fetching and the pure build_factor_attribution()
analytics function to produce a FactorAttributionResponse from an
ImportedPortfolioSnapshot.

Unlike run_imported_diagnostics_engine (which derives its date range from
ledger trade dates), attribution is *synthetic history*: the engine holds
current holdings constant and asks "how would this portfolio have performed?"
The fetched date range is a fixed display span (≈1 year) plus the rolling
`window`, NOT scaled to the window — so the cumulative chart spans the same
range for every window (20 / 60 / 252); the window only sets each rolling
estimate's length. This works even when the snapshot was built by the exposure
engine (which carries no ledger history).
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from app.analytics.attribution import build_factor_attribution, _unavailable_response
from app.analytics.risk import FACTOR_PROXY_MAP
from app.schemas.attribution import FactorAttributionRequest, FactorAttributionResponse
from app.services.diagnostics_engine import _build_synthetic_snapshot_history_states
from app.services.market_data import MarketDataService

# Calendar-day lookback per trading-day count.  We multiply by 1.6 and add a
# 30-day buffer to safely cover weekends, public holidays, and thin trading
# periods.
def _lookback_calendar_days(window: int) -> int:
    return math.ceil(window * 1.6) + 30


# Target span (trading days) of the cumulative-attribution time series shown on
# the chart — independent of the rolling window. The fetch covers this display
# span PLUS the window, so the rolling estimator has `window` days to fill before
# the first plotted point and every window (20/60/252) shows the same ~1-year
# series. (Previously the fetch was scaled to the window alone, so the 20d chart
# only spanned ~2 months — see US-18.x fix.)
ATTRIBUTION_DISPLAY_TRADING_DAYS = 252


def run_attribution_engine(request: FactorAttributionRequest) -> FactorAttributionResponse:
    """Compute factor return attribution for a portfolio snapshot.

    Builds synthetic daily portfolio states (current holdings held constant
    backward in time) from market prices fetched over the last
    _lookback_calendar_days(window) calendar days, then delegates to
    build_factor_attribution().

    Returns attribution_status="unavailable" when:
      - the snapshot has no positions
      - market data cannot be fetched for the lookback period
      - fewer than `window` trading days of common history are available
    """
    snapshot = request.snapshot
    window = request.window
    benchmark_symbol = request.benchmark_symbol

    if not snapshot.positions:
        return _unavailable_response(window)

    # Synthetic history: the date range is driven by the window size, not by
    # the snapshot's import/ledger dates.  The exposure engine always builds
    # snapshots with ledger_entries=[] and as_of_date=today, so we must not
    # rely on those fields here.
    history_end_date = date.today().isoformat()
    # Fetch the full display span PLUS the window so the cumulative series spans
    # the same ~1-year range for every window (the window only sets how many days
    # each rolling beta estimate uses, not how far back the chart starts).
    fetch_trading_days = ATTRIBUTION_DISPLAY_TRADING_DAYS + window
    history_start_date = (
        date.today() - timedelta(days=_lookback_calendar_days(fetch_trading_days))
    ).isoformat()

    market_data = MarketDataService()

    # Fetch benchmark rows (defines the set of valuation dates).
    benchmark_rows = market_data.get_historical_prices(
        benchmark_symbol, history_start_date, history_end_date
    )
    if not benchmark_rows:
        return _unavailable_response(window)

    valuation_dates = sorted({row["date"] for row in benchmark_rows})

    # Fetch symbol price histories (needed for synthetic daily states).
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [position.symbol for position in snapshot.positions],
        history_start_date,
        history_end_date,
    )

    # Fetch factor proxy histories (needed for attribution).
    factor_histories = market_data.get_historical_prices_for_symbols(
        list(FACTOR_PROXY_MAP.values()),
        history_start_date,
        history_end_date,
    )
    # Include benchmark as a factor proxy (some factor models use it as "Market").
    factor_histories[benchmark_symbol] = benchmark_rows

    # Build synthetic daily portfolio states.
    daily_states = _build_synthetic_snapshot_history_states(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
    )

    if not daily_states:
        return _unavailable_response(window)

    return build_factor_attribution(
        daily_states=daily_states,
        factor_histories=factor_histories,
        window=window,
    )
