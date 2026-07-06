"""Stress-scenario engine — standalone surface for the Risk tab.

Reuses `build_statistical_factor_model` + `build_stress_scenarios` from
`analytics/risk.py` so the standalone stress route cannot drift from the
diagnostics pipeline. When the portfolio has insufficient history to fit
a factor model, the engine surfaces `trust = 'unavailable'` and returns
per-scenario rows with `estimated_return_pct = None` + `status =
'unavailable'` — never fabricated zeroes.

Methodology: see §Stress Scenarios in docs/finance/financial-methodology.md
  estimated_scenario_return = sum(current_factor_loading_i * shock_i)
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.constants import DEFAULT_BENCHMARK_SYMBOL, lookback_calendar_days
from app.analytics.risk import (
    FACTOR_PROXY_MAP,
    STRESS_SCENARIOS,
    build_statistical_factor_model,
    build_stress_scenarios,
)
from app.schemas.reconciliation import StressScenarioResult
from app.schemas.stress import StressEngineRequest, StressEngineResponse
from app.services.diagnostics_engine import _build_synthetic_snapshot_history_states_with_coverage
from app.services.market_data import MarketDataService
from app.services.portfolio_snapshot_builder import build_imported_snapshot_from_request


# Stress needs enough history for the 252-day rolling factor model to produce
# stable loadings; use the shared lookback heuristic at the 252-day window
# (→ ~434 calendar days).
_STRESS_LOOKBACK_CALENDAR_DAYS = lookback_calendar_days(252)


def _build_unavailable_scenarios() -> list[StressScenarioResult]:
    """Return one scenario row per canonical entry in STRESS_SCENARIOS with
    null pct + status='unavailable'. Preserves the scenario list shape so
    the UI never has to special-case "scenarios is empty"."""
    return [
        StressScenarioResult(
            name=name,
            estimated_return_pct=None,
            description=description,
            status="unavailable",
        )
        for name, _shocks, description in STRESS_SCENARIOS
    ]


def _has_any_factor_loading(model) -> bool:
    """Factor model is considered usable for stress when at least one
    factor in `current_factor_snapshot` has a non-null latest_loading."""
    return any(
        item.latest_loading is not None for item in model.current_factor_snapshot
    )


def run_stress_engine(request: StressEngineRequest) -> StressEngineResponse:
    snapshot = build_imported_snapshot_from_request(request)
    benchmark_symbol = request.benchmark_symbol or DEFAULT_BENCHMARK_SYMBOL

    # Empty portfolio: factor model cannot be fit; return unavailable
    # without burning a market-data fetch.
    if not request.positions:
        return StressEngineResponse(
            scenarios=_build_unavailable_scenarios(),
            trust="unavailable",
        )

    market_data = MarketDataService()
    today = date.today()
    history_start = (today - timedelta(days=_STRESS_LOOKBACK_CALENDAR_DAYS)).isoformat()
    history_end = today.isoformat()

    benchmark_rows = market_data.get_historical_prices(
        benchmark_symbol, history_start, history_end
    )
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [p.symbol for p in snapshot.positions], history_start, history_end
    )
    factor_histories = market_data.get_historical_prices_for_symbols(
        list(FACTOR_PROXY_MAP.values()), history_start, history_end
    )
    factor_histories[benchmark_symbol] = benchmark_rows

    if not benchmark_rows:
        return StressEngineResponse(
            scenarios=_build_unavailable_scenarios(),
            trust="unavailable",
        )

    valuation_dates = sorted({row["date"] for row in benchmark_rows})
    daily_states, coverage = _build_synthetic_snapshot_history_states_with_coverage(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
    )

    model = build_statistical_factor_model(
        daily_states, factor_histories, benchmark_symbol
    )

    if not _has_any_factor_loading(model):
        return StressEngineResponse(
            scenarios=_build_unavailable_scenarios(),
            trust="unavailable",
            coverage=coverage,
        )

    scenarios = build_stress_scenarios(model)
    return StressEngineResponse(scenarios=scenarios, trust="synthetic", coverage=coverage)
