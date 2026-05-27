"""Attribution engine service.

Wires together market data fetching and the pure build_factor_attribution()
analytics function to produce a FactorAttributionResponse from an
ImportedPortfolioSnapshot.

Mirrors the pattern of run_imported_diagnostics_engine in diagnostics_engine.py.
"""
from __future__ import annotations

from app.analytics.attribution import build_factor_attribution
from app.analytics.risk import FACTOR_PROXY_MAP
from app.schemas.attribution import FactorAttributionRequest, FactorAttributionResponse
from app.services.diagnostics_engine import _build_synthetic_snapshot_history_states
from app.services.market_data import MarketDataService


def run_attribution_engine(request: FactorAttributionRequest) -> FactorAttributionResponse:
    """Compute factor return attribution for an imported portfolio snapshot.

    Fetches factor proxy price histories from the local FMP cache (no new
    external calls beyond what the diagnostics engine already fetches), builds
    synthetic daily portfolio states from current holdings × historical prices,
    then delegates to build_factor_attribution().

    Returns attribution_status="unavailable" when:
      - the snapshot has no ledger or position date information
      - market data cannot be fetched
      - fewer than min_observations trading days of common history are available
    """
    snapshot = request.snapshot
    window = request.window
    benchmark_symbol = request.benchmark_symbol

    # Determine history date range from the snapshot (mirrors run_imported_diagnostics_engine).
    history_dates = [
        entry.trade_date.isoformat()
        for entry in snapshot.ledger_entries
        if entry.trade_date is not None
    ]
    history_dates.extend(
        position.as_of_date.isoformat()
        for position in snapshot.positions
        if position.as_of_date is not None
    )

    if not history_dates:
        from app.analytics.attribution import _unavailable_response
        return _unavailable_response(window)

    history_start_date = min(history_dates)
    history_end_date = max(history_dates)

    market_data = MarketDataService()

    # Fetch benchmark rows (defines the set of valuation dates).
    benchmark_rows = market_data.get_historical_prices(
        benchmark_symbol, history_start_date, history_end_date
    )
    if not benchmark_rows:
        from app.analytics.attribution import _unavailable_response
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
        from app.analytics.attribution import _unavailable_response
        return _unavailable_response(window)

    return build_factor_attribution(
        daily_states=daily_states,
        factor_histories=factor_histories,
        window=window,
    )
