from typing import Literal

from app.analytics.risk import (
    FACTOR_PROXY_MAP,
    build_factor_exposures,
    build_factor_registry,
    build_factor_shift_diagnostics,
    build_model_reliability_snapshot,
    build_portfolio_risk_summary,
    build_relative_risk_summary,
    build_risk_contribution_breakdown,
    build_rolling_risk_series,
    build_statistical_factor_model,
    build_stress_scenarios,
    build_volatility_regime_payload,
    factor_model_methodology,
)
from app.analytics.performance import build_daily_portfolio_states
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.diagnostics import (
    DiagnosticsAvailability,
    DiagnosticsDrawdownSummary,
    DiagnosticsEngineRequest,
    DiagnosticsProvenance,
    DiagnosticsResult,
    DiagnosticsRiskConcentrationSummary,
    DiagnosticsVolatilitySummary,
)
from app.schemas.reconciliation import (
    DailyPortfolioState,
    DailyStatePosition,
    LookThroughSectorExposure,
    MarketOverlapSummary,
    FactorShiftDiagnosticsPayload,
    ModelReliabilitySnapshot,
    PortfolioRiskSummary,
    RelativeRiskSummary,
    RiskConcentrationSnapshot,
    RiskContributionBreakdownPayload,
    StatisticalFactorModel,
    StressScenarioResult,
    VolatilityAssumptions,
    VolatilityRegimePayload,
    VolatilitySnapshot,
    RegimeAssessment,
)
from app.services.exposure_engine import build_snapshot_from_exposure_request
from app.services.market_data import MarketDataService


def build_historical_diagnostics_result(
    snapshot,
    benchmark_symbol: str,
    daily_states: list,
    benchmark_rows: list[dict],
    symbol_price_histories: dict[str, list[dict]],
    factor_histories: dict[str, list[dict]],
    market_overlap: MarketOverlapSummary,
    lookthrough_sector_exposure: list[LookThroughSectorExposure],
    provenance: DiagnosticsProvenance,
) -> DiagnosticsResult:
    factor_registry = build_factor_registry()
    risk_summary = build_portfolio_risk_summary(daily_states, benchmark_rows, benchmark_symbol)
    rolling_risk = build_rolling_risk_series(daily_states, benchmark_rows)
    relative_risk = build_relative_risk_summary(daily_states, benchmark_rows, benchmark_symbol)
    volatility_regime = build_volatility_regime_payload(daily_states, benchmark_rows)
    statistical_factor_model = build_statistical_factor_model(daily_states, factor_histories, benchmark_symbol)
    factor_shift_diagnostics = build_factor_shift_diagnostics(factor_registry, statistical_factor_model, volatility_regime)
    risk_contribution_breakdown = build_risk_contribution_breakdown(
        snapshot,
        daily_states,
        symbol_price_histories,
        factor_histories,
        factor_registry,
        statistical_factor_model,
    )
    model_reliability = build_model_reliability_snapshot(statistical_factor_model)
    stress_scenarios = build_stress_scenarios(statistical_factor_model)
    factor_exposures = build_factor_exposures(risk_summary, market_overlap, lookthrough_sector_exposure)
    concentration = risk_contribution_breakdown.concentration

    return DiagnosticsResult(
        snapshot=snapshot,
        provenance=provenance,
        availability=DiagnosticsAvailability(
            historical_sections_available=True,
            history_context_required=True,
            note=None,
        ),
        drawdown_summary=DiagnosticsDrawdownSummary(
            current_drawdown_pct=volatility_regime.snapshot.current_drawdown_pct,
            max_drawdown_pct=volatility_regime.snapshot.max_drawdown_pct,
        ),
        volatility_summary=DiagnosticsVolatilitySummary(
            portfolio_volatility_pct=risk_summary.portfolio_volatility_pct,
            benchmark_volatility_pct=risk_summary.benchmark_volatility_pct,
            downside_volatility_pct=volatility_regime.snapshot.downside_vol_60d,
            tracking_error_pct=relative_risk.tracking_error_pct,
        ),
        risk_concentration_summary=DiagnosticsRiskConcentrationSummary(
            top_1_factor_risk_share=concentration.top_1_factor_risk_share,
            top_3_factor_risk_share=concentration.top_3_factor_risk_share,
            top_1_position_risk_share=concentration.top_1_position_risk_share,
            top_5_position_risk_share=concentration.top_5_position_risk_share,
            factor_hhi=concentration.factor_hhi,
            position_hhi=concentration.position_hhi,
        ),
        risk_summary=risk_summary,
        rolling_risk=rolling_risk,
        relative_risk=relative_risk,
        volatility_regime=volatility_regime,
        factor_exposures=factor_exposures,
        factor_shift_diagnostics=factor_shift_diagnostics,
        risk_contribution_breakdown=risk_contribution_breakdown,
        model_reliability=model_reliability,
        factor_registry=factor_registry,
        factor_methodology=factor_model_methodology(),
        statistical_factor_model=statistical_factor_model,
        stress_scenarios=stress_scenarios,
    )


def build_unavailable_diagnostics_result(snapshot, benchmark_symbol: str, snapshot_basis: Literal["imported_snapshot", "snapshot_request"] = "snapshot_request") -> DiagnosticsResult:
    factor_registry = build_factor_registry()

    return DiagnosticsResult(
        snapshot=snapshot,
        provenance=DiagnosticsProvenance(
            snapshot_basis=snapshot_basis,
            historical_basis="unavailable",
            note="Historical diagnostics are unavailable because no valid historical portfolio path was available for this input.",
        ),
        availability=DiagnosticsAvailability(
            historical_sections_available=False,
            history_context_required=True,
            note='Historical diagnostics are unavailable from snapshot-only input. Attach PortfolioHistoryContext to run rolling diagnostics accurately.',
        ),
        drawdown_summary=DiagnosticsDrawdownSummary(),
        volatility_summary=DiagnosticsVolatilitySummary(),
        risk_concentration_summary=DiagnosticsRiskConcentrationSummary(),
        risk_summary=PortfolioRiskSummary(
            benchmark_symbol=benchmark_symbol,
            methodology='unavailable_without_history_context',
            start_date=None,
            end_date=None,
            observations=0,
            portfolio_beta=None,
            portfolio_correlation=None,
            r_squared=None,
            portfolio_volatility_pct=None,
            benchmark_volatility_pct=None,
        ),
        rolling_risk=[],
        relative_risk=RelativeRiskSummary(
            benchmark_symbol=benchmark_symbol,
            tracking_error_pct=None,
            active_return_pct=None,
            information_ratio=None,
        ),
        volatility_regime=VolatilityRegimePayload(
            methodology='unavailable_without_history_context',
            assumptions=VolatilityAssumptions(
                return_basis='unavailable',
                cash_flow_timing='unavailable',
                drawdown_basis='unavailable',
                benchmark_basis='unavailable',
                downside_mar=0.0,
                annualization_days=252,
            ),
            rolling_series=[],
            snapshot=VolatilitySnapshot(),
            regime=RegimeAssessment(label='unavailable', confidence='low'),
        ),
        factor_exposures=[],
        factor_shift_diagnostics=FactorShiftDiagnosticsPayload(
            methodology='unavailable_without_history_context',
            snapshots=[],
            largest_positive_shifts_20d=[],
            largest_negative_shifts_20d=[],
            largest_absolute_shifts_20d=[],
            largest_absolute_shifts_60d=[],
        ),
        risk_contribution_breakdown=RiskContributionBreakdownPayload(
            methodology='unavailable_without_history_context',
            window_days=20,
            observation_count=0,
            status='unavailable',
            factor_contributions=[],
            position_contributions=[],
            concentration=RiskConcentrationSnapshot(),
        ),
        model_reliability=ModelReliabilitySnapshot(
            window_days=20,
            observation_count=0,
            r_squared=None,
            residual_volatility=None,
            collinearity_pair_count=0,
            max_abs_factor_correlation=None,
            factor_count_used=0,
            missing_factor_count=0,
            status='unavailable',
            confidence='low',
            stability_score=None,
        ),
        factor_registry=factor_registry,
        factor_methodology=factor_model_methodology(),
        statistical_factor_model=StatisticalFactorModel(
            status='unavailable',
            benchmark_symbol=benchmark_symbol,
            windows=[],
            rolling_loadings_20d=[],
            rolling_loadings_60d=[],
            rolling_loadings_252d=[],
            current_factor_snapshot=[],
            collinearity_diagnostics=[],
            insufficient_history=[],
        ),
        stress_scenarios=[
            StressScenarioResult(
                name='Unavailable without history context',
                estimated_return_pct=0.0,
                description='Attach PortfolioHistoryContext to run historically grounded diagnostics and stress scenarios.',
            ),
        ],
    )


def run_diagnostics_engine(request: DiagnosticsEngineRequest) -> DiagnosticsResult:
    snapshot = build_snapshot_from_exposure_request(request)
    history_context = request.history_context
    if history_context is None or not history_context.history_start_date or not history_context.history_end_date:
        return build_unavailable_diagnostics_result(snapshot, request.benchmark_symbol, snapshot_basis="snapshot_request")

    market_data = MarketDataService()
    benchmark_rows = market_data.get_historical_prices(
        history_context.benchmark_symbol or request.benchmark_symbol,
        history_context.history_start_date,
        history_context.history_end_date,
    )
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [position.symbol for position in snapshot.positions],
        history_context.history_start_date,
        history_context.history_end_date,
    )
    factor_histories = market_data.get_historical_prices_for_symbols(
        list(FACTOR_PROXY_MAP.values()),
        history_context.history_start_date,
        history_context.history_end_date,
    )
    factor_histories[history_context.benchmark_symbol or request.benchmark_symbol] = benchmark_rows
    if not benchmark_rows or not _has_any_symbol_price_history(symbol_price_histories):
        return build_unavailable_diagnostics_result(snapshot, history_context.benchmark_symbol or request.benchmark_symbol, snapshot_basis="snapshot_request")
    valuation_dates = sorted({row['date'] for row in benchmark_rows})
    daily_states = _build_synthetic_snapshot_history_states(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
    )

    from app.services.exposure_engine import build_exposure_result

    exposure_result = build_exposure_result(snapshot, history_context.benchmark_symbol or request.benchmark_symbol)
    return build_historical_diagnostics_result(
        snapshot=snapshot,
        benchmark_symbol=history_context.benchmark_symbol or request.benchmark_symbol,
        daily_states=daily_states,
        benchmark_rows=benchmark_rows,
        symbol_price_histories=symbol_price_histories,
        factor_histories=factor_histories,
        market_overlap=exposure_result.market_overlap,
        lookthrough_sector_exposure=exposure_result.lookthrough_sector_exposure,
        provenance=DiagnosticsProvenance(
            snapshot_basis="snapshot_request",
            historical_basis="market_data_history",
            note="Historical diagnostics are derived from synthetic snapshot-history states built from the current snapshot plus external market data.",
        ),
    )


def _build_synthetic_snapshot_history_states(
    snapshot: ImportedPortfolioSnapshot,
    price_histories: dict[str, list[dict]],
    valuation_dates: list[str],
) -> list[DailyPortfolioState]:
    if not valuation_dates or not snapshot.positions:
        return []

    base_currency = snapshot.statement.base_currency or 'USD'
    total_cash = sum(float(balance.ending_cash or 0.0) for balance in snapshot.cash_balances)
    fallback_prices = {
        position.symbol: float(position.close_price or 0.0) if position.close_price is not None else (float(position.market_value) / float(position.quantity) if position.quantity not in (None, 0) else None)
        for position in snapshot.positions
    }

    history_by_symbol: dict[str, dict[str, float]] = {}
    first_date = valuation_dates[0]
    for symbol, rows in price_histories.items():
        ordered_rows = sorted(rows, key=lambda row: row['date'])
        row_lookup = {row['date']: float(row['price']) for row in ordered_rows}
        symbol_history: dict[str, float] = {}
        last_price: float | None = None
        first_price = float(ordered_rows[0]['price']) if ordered_rows else fallback_prices.get(symbol)
        for valuation_date in valuation_dates:
            if valuation_date in row_lookup:
                last_price = row_lookup[valuation_date]
            if last_price is not None:
                symbol_history[valuation_date] = last_price
            elif first_price is not None:
                symbol_history[valuation_date] = first_price
        history_by_symbol[symbol] = symbol_history

    synthetic_quantities: dict[str, float] = {}
    for position in snapshot.positions:
        first_price = history_by_symbol.get(position.symbol, {}).get(first_date, fallback_prices.get(position.symbol))
        if first_price is None or first_price <= 0:
            continue
        synthetic_quantities[position.symbol] = float(position.market_value) / float(first_price)

    states: list[DailyPortfolioState] = []
    for valuation_date in valuation_dates:
        state_positions: list[DailyStatePosition] = []
        total_market_value = 0.0
        for position in snapshot.positions:
            quantity = synthetic_quantities.get(position.symbol)
            if quantity is None:
                continue
            price = history_by_symbol.get(position.symbol, {}).get(valuation_date, fallback_prices.get(position.symbol))
            if price is None:
                continue
            market_value = round(quantity * float(price), 2)
            total_market_value += market_value
            state_positions.append(
                DailyStatePosition(
                    symbol=position.symbol,
                    quantity=round(quantity, 6),
                    market_price=float(price),
                    market_value=market_value,
                )
            )

        states.append(
            DailyPortfolioState(
                date=valuation_date,
                cash={base_currency: round(total_cash, 2)},
                positions=state_positions,
                total_market_value=round(total_market_value, 2),
                total_portfolio_value=round(total_market_value + total_cash, 2),
                external_cash_flow=0.0,
            )
        )

    return states


def run_imported_diagnostics_engine(snapshot: ImportedPortfolioSnapshot, benchmark_symbol: str | None = None) -> DiagnosticsResult:
    history_dates = [entry.trade_date.isoformat() for entry in snapshot.ledger_entries if entry.trade_date is not None]
    history_dates.extend(position.as_of_date.isoformat() for position in snapshot.positions if position.as_of_date is not None)
    if not history_dates:
        return build_unavailable_diagnostics_result(snapshot, benchmark_symbol or 'SPY', snapshot_basis="imported_snapshot")

    history_start_date = min(history_dates)
    history_end_date = max(history_dates)
    resolved_benchmark_symbol = benchmark_symbol or 'SPY'
    market_data = MarketDataService()
    benchmark_rows = market_data.get_historical_prices(resolved_benchmark_symbol, history_start_date, history_end_date)
    symbol_price_histories = market_data.get_historical_prices_for_symbols(
        [position.symbol for position in snapshot.positions],
        history_start_date,
        history_end_date,
    )
    factor_histories = market_data.get_historical_prices_for_symbols(list(FACTOR_PROXY_MAP.values()), history_start_date, history_end_date)
    factor_histories[resolved_benchmark_symbol] = benchmark_rows
    if not benchmark_rows or not _has_any_symbol_price_history(symbol_price_histories):
        return build_unavailable_diagnostics_result(snapshot, resolved_benchmark_symbol, snapshot_basis="imported_snapshot")
    valuation_dates = sorted({row['date'] for row in benchmark_rows})
    daily_states = build_daily_portfolio_states(
        snapshot=snapshot,
        price_histories=symbol_price_histories,
        valuation_dates=valuation_dates,
        fx_history={},
    )

    from app.services.exposure_engine import build_exposure_result

    exposure_result = build_exposure_result(snapshot, resolved_benchmark_symbol)
    return build_historical_diagnostics_result(
        snapshot=snapshot,
        benchmark_symbol=resolved_benchmark_symbol,
        daily_states=daily_states,
        benchmark_rows=benchmark_rows,
        symbol_price_histories=symbol_price_histories,
        factor_histories=factor_histories,
        market_overlap=exposure_result.market_overlap,
        lookthrough_sector_exposure=exposure_result.lookthrough_sector_exposure,
        provenance=DiagnosticsProvenance(
            snapshot_basis="imported_snapshot",
            historical_basis="imported_portfolio_history",
            note="Historical diagnostics are derived from imported portfolio history replay plus external benchmark and factor market data.",
        ),
    )


def _has_any_symbol_price_history(symbol_price_histories: dict[str, list[dict]]) -> bool:
    return any(rows for rows in symbol_price_histories.values())
