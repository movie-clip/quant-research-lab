from app.analytics.performance import build_daily_portfolio_states, build_true_performance_series
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.dashboard_history import DashboardHistoryEngineRequest, DashboardHistoryResult
from app.services.benchmark_service import build_benchmark_comparison
from app.services.market_data import MarketDataService


def run_dashboard_history_engine(request: DashboardHistoryEngineRequest) -> DashboardHistoryResult:
    history_context = request.history_context

    if history_context is None or not history_context.history_start_date or not history_context.history_end_date:
        return DashboardHistoryResult(
            daily_states=[],
            performance_series=[],
            source_status={"performance_history": "unavailable", "monthly_returns": "unavailable"},
            benchmark=None,
        )

    return _build_unavailable_dashboard_history_result()


def run_imported_dashboard_history(snapshot: ImportedPortfolioSnapshot, benchmark_symbol: str | None = None) -> DashboardHistoryResult:
    history_start_date, history_end_date = _derive_imported_history_window(snapshot)
    if not history_start_date or not history_end_date:
        return _build_unavailable_dashboard_history_result()

    resolved_benchmark_symbol = benchmark_symbol or "SPY"
    market_data = MarketDataService()
    benchmark_rows = market_data.get_historical_prices(
        resolved_benchmark_symbol,
        history_start_date,
        history_end_date,
    )
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [position.symbol for position in snapshot.positions],
        history_start_date,
        history_end_date,
    )

    valuation_dates = sorted({row["date"] for row in benchmark_rows})
    daily_states = build_daily_portfolio_states(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
        fx_history={},
    )
    performance_series = build_true_performance_series(daily_states, benchmark_rows)

    return DashboardHistoryResult(
        daily_states=daily_states,
        performance_series=performance_series,
        source_status={
            "performance_history": "live" if benchmark_rows and symbol_price_histories else "sample",
            "monthly_returns": "suppressed" if any(state.total_portfolio_value < 0 for state in daily_states) else "live",
        },
        benchmark=build_benchmark_comparison(resolved_benchmark_symbol, benchmark_rows),
    )


def _build_unavailable_dashboard_history_result() -> DashboardHistoryResult:
    return DashboardHistoryResult(
        daily_states=[],
        performance_series=[],
        source_status={"performance_history": "unavailable", "monthly_returns": "unavailable"},
        benchmark=None,
    )


def _derive_imported_history_window(snapshot: ImportedPortfolioSnapshot) -> tuple[str | None, str | None]:
    dates = [entry.trade_date.isoformat() for entry in snapshot.ledger_entries if entry.trade_date is not None]
    dates.extend(position.as_of_date.isoformat() for position in snapshot.positions if position.as_of_date is not None)
    if not dates:
        return None, None
    return min(dates), max(dates)
