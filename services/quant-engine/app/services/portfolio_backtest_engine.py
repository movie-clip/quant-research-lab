from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from app.analytics.risk import build_factor_registry, build_portfolio_risk_summary, build_relative_risk_summary, build_risk_contribution_breakdown, build_rolling_risk_series, build_statistical_factor_model, build_stress_scenarios, build_volatility_regime_payload
from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement
from app.schemas.reconciliation import DailyPortfolioState, DailyStatePosition, SnapshotItem
from app.backtests.portfolio_engine import PortfolioAllocationBacktestEngine
from app.instruments.registry import InstrumentRegistry
from app.schemas.backtest_engine import (
    AllocationBacktestComparison,
    AllocationBacktestInstrumentMeta,
    AllocationBacktestResult,
    AllocationBacktestStatus,
    DistributionPolicy,
    PortfolioDiagnosticsProvenance,
    PortfolioDiagnosticsComparisonRow,
    PortfolioDiagnosticsSnapshot,
    PortfolioImprovementComparison,
    PortfolioAllocationBacktestRequest,
    PortfolioAllocationBacktestResponse,
)
from app.services.market_data import MarketDataService


METHODOLOGY = "Historical allocation replay using adjusted prices, aligned valuation dates, next-available-date execution after signal generation, fractional shares, long-only target weights, and transaction cost assumptions."


@dataclass(frozen=True)
class BacktestDiagnosticsInputs:
    synthetic_snapshot: ImportedPortfolioSnapshot
    replay_daily_states: list[DailyPortfolioState]
    benchmark_price_history: list[dict]
    factor_price_histories: dict[str, list[dict]]


def build_portfolio_allocation_backtest_analysis(request: PortfolioAllocationBacktestRequest) -> PortfolioAllocationBacktestResponse:
    symbols = [item.symbol for item in request.weights]
    if request.reference_weights:
        symbols.extend(item.symbol for item in request.reference_weights)
    symbols.extend(item.us_proxy for item in build_factor_registry())
    symbols.append(request.benchmark_symbol)

    market_data = MarketDataService()
    histories = market_data.get_historical_prices_for_symbols(
        symbols,
        request.start_date.isoformat(),
        request.end_date.isoformat(),
        symbol_overrides=request.symbol_overrides,
        allow_proxy_fallback=True,
    )
    benchmark_rows = histories.get(request.benchmark_symbol, [])
    if not benchmark_rows:
        raise ValueError(f"No historical prices found for benchmark: {request.benchmark_symbol}")

    registry = InstrumentRegistry()
    engine = PortfolioAllocationBacktestEngine()
    candidate_symbols = [item.symbol for item in request.weights]
    candidate_dates = _aligned_dates(candidate_symbols, histories, benchmark_rows)
    candidate_histories = {symbol: histories.get(symbol, []) for symbol in candidate_symbols}
    candidate_status = _derive_status(
        symbols=candidate_symbols,
        ordered_dates=candidate_dates,
        requested_start=request.start_date.isoformat(),
        requested_end=request.end_date.isoformat(),
        registry=registry,
        histories=candidate_histories,
        benchmark_rows=benchmark_rows,
    )
    candidate_result = engine.run(
        request=request,
        portfolio_name=request.portfolio_name or "Candidate",
        weights=request.weights,
        benchmark_rows=benchmark_rows,
        price_histories=candidate_histories,
        ordered_dates=candidate_dates,
        instrument_metadata=_instrument_metadata(candidate_symbols, registry),
        status=candidate_status,
    )

    reference_result = None
    comparison = None
    reference_diagnostics = None
    candidate_diagnostics = None
    diagnostics_comparison = None
    if request.reference_weights:
        reference_symbols = [item.symbol for item in request.reference_weights]
        reference_dates = _aligned_dates(reference_symbols, histories, benchmark_rows)
        common_dates = sorted(set(candidate_dates) & set(reference_dates))
        if len(common_dates) < 2:
            raise ValueError("Not enough common dates across candidate, reference, and benchmark")
        candidate_result = engine.run(
            request=request,
            portfolio_name=request.portfolio_name or "Candidate",
            weights=request.weights,
            benchmark_rows=benchmark_rows,
            price_histories=candidate_histories,
            ordered_dates=common_dates,
            instrument_metadata=_instrument_metadata(candidate_symbols, registry),
            status=_derive_status(
                symbols=candidate_symbols,
                ordered_dates=common_dates,
                requested_start=request.start_date.isoformat(),
                requested_end=request.end_date.isoformat(),
                registry=registry,
                histories=candidate_histories,
                benchmark_rows=benchmark_rows,
            ),
        )
        reference_histories = {symbol: histories.get(symbol, []) for symbol in reference_symbols}
        reference_result = engine.run(
            request=request,
            portfolio_name="Reference",
            weights=request.reference_weights,
            benchmark_rows=benchmark_rows,
            price_histories=reference_histories,
            ordered_dates=common_dates,
            instrument_metadata=_instrument_metadata(reference_symbols, registry),
            status=_derive_status(
                symbols=reference_symbols,
                ordered_dates=common_dates,
                requested_start=request.start_date.isoformat(),
                requested_end=request.end_date.isoformat(),
                registry=registry,
                histories=reference_histories,
                benchmark_rows=benchmark_rows,
            ),
        )
        comparison = _compare_results(reference_result, candidate_result)
        reference_diagnostics = _build_portfolio_diagnostics_snapshot(
            portfolio_name="Reference",
            weights=request.reference_weights,
            result=reference_result,
            benchmark_rows=benchmark_rows,
            histories=histories,
        )
        candidate_diagnostics = _build_portfolio_diagnostics_snapshot(
            portfolio_name=request.portfolio_name or "Candidate",
            weights=request.weights,
            result=candidate_result,
            benchmark_rows=benchmark_rows,
            histories=histories,
        )
        diagnostics_comparison = _build_diagnostics_comparison(reference_diagnostics, candidate_diagnostics)
    else:
        candidate_diagnostics = _build_portfolio_diagnostics_snapshot(
            portfolio_name=request.portfolio_name or "Candidate",
            weights=request.weights,
            result=candidate_result,
            benchmark_rows=benchmark_rows,
            histories=histories,
        )

    return PortfolioAllocationBacktestResponse(
        methodology=METHODOLOGY,
        reference_result=reference_result,
        candidate_result=candidate_result,
        comparison=comparison,
        reference_diagnostics=reference_diagnostics,
        candidate_diagnostics=candidate_diagnostics,
        diagnostics_comparison=diagnostics_comparison,
    )


def _aligned_dates(symbols: list[str], histories: dict[str, list[dict]], benchmark_rows: list[dict]) -> list[str]:
    common_dates = {row["date"] for row in benchmark_rows}
    for symbol in symbols:
        rows = histories.get(symbol, [])
        if not rows:
            raise ValueError(f"No historical prices found for symbol: {symbol}")
        common_dates &= {row["date"] for row in rows}
    ordered = sorted(common_dates)
    if len(ordered) < 2:
        raise ValueError("Not enough common dates across portfolio symbols and benchmark")
    return ordered


def _compare_results(reference: AllocationBacktestResult, candidate: AllocationBacktestResult) -> AllocationBacktestComparison:
    return AllocationBacktestComparison(
        total_return_diff_pct=_diff(reference.metrics.total_return_pct, candidate.metrics.total_return_pct),
        annualized_return_diff_pct=_diff(reference.metrics.annualized_return_pct, candidate.metrics.annualized_return_pct),
        annualized_volatility_diff_pct=_diff(reference.metrics.annualized_volatility_pct, candidate.metrics.annualized_volatility_pct),
        downside_volatility_diff_pct=_diff(reference.metrics.downside_volatility_pct, candidate.metrics.downside_volatility_pct),
        max_drawdown_diff_pct=_diff(reference.metrics.max_drawdown_pct, candidate.metrics.max_drawdown_pct),
        sharpe_diff=_diff(reference.metrics.sharpe_ratio, candidate.metrics.sharpe_ratio),
        sortino_diff=_diff(reference.metrics.sortino_ratio, candidate.metrics.sortino_ratio),
        excess_return_diff_pct=_diff(reference.metrics.excess_return_pct, candidate.metrics.excess_return_pct),
        tracking_error_diff_pct=_diff(reference.metrics.tracking_error_pct, candidate.metrics.tracking_error_pct),
        information_ratio_diff=_diff(reference.metrics.information_ratio, candidate.metrics.information_ratio),
        beta_diff=_diff(reference.metrics.beta_vs_benchmark, candidate.metrics.beta_vs_benchmark),
        correlation_diff=_diff(reference.metrics.correlation_vs_benchmark, candidate.metrics.correlation_vs_benchmark),
        total_turnover_diff_pct=_diff(reference.metrics.total_turnover_pct, candidate.metrics.total_turnover_pct),
        total_cost_diff=_diff(reference.metrics.total_cost_paid, candidate.metrics.total_cost_paid),
    )


def _diff(left: float | None, right: float | None) -> float | None:
    if left is None or right is None:
        return None
    return round(right - left, 4)


def _build_portfolio_diagnostics_snapshot(
    *,
    portfolio_name: str,
    weights,
    result: AllocationBacktestResult,
    benchmark_rows: list[dict],
    histories: dict[str, list[dict]],
) -> PortfolioDiagnosticsSnapshot:
    diagnostics_inputs = _build_backtest_diagnostics_inputs(
        portfolio_name=portfolio_name,
        weights=weights,
        result=result,
        benchmark_rows=benchmark_rows,
        histories=histories,
    )
    factor_registry = build_factor_registry()
    model = build_statistical_factor_model(diagnostics_inputs.replay_daily_states, diagnostics_inputs.factor_price_histories, result.benchmark_symbol or "SPY")
    factor_snapshot = model.current_factor_snapshot if model.current_factor_snapshot else _build_fallback_factor_snapshot(weights, factor_registry)
    volatility = build_volatility_regime_payload(diagnostics_inputs.replay_daily_states, diagnostics_inputs.benchmark_price_history)
    risk_contribution = build_risk_contribution_breakdown(diagnostics_inputs.synthetic_snapshot, diagnostics_inputs.replay_daily_states, {item.symbol: histories.get(item.symbol, []) for item in weights}, diagnostics_inputs.factor_price_histories, factor_registry, model)

    return PortfolioDiagnosticsSnapshot(
        provenance=PortfolioDiagnosticsProvenance(
            snapshot_basis="synthetic_replay_snapshot",
            historical_basis="market_data_history",
            note="Backtest diagnostics combine a synthetic replay snapshot with replay-derived daily states and external historical market data.",
        ),
        factor_snapshot=factor_snapshot,
        volatility_snapshot=volatility.snapshot,
        risk_contribution=risk_contribution,
        stress_scenarios=build_stress_scenarios(model),
    )


def _build_backtest_diagnostics_inputs(
    *,
    portfolio_name: str,
    weights,
    result: AllocationBacktestResult,
    benchmark_rows: list[dict],
    histories: dict[str, list[dict]],
) -> BacktestDiagnosticsInputs:
    factor_registry = build_factor_registry()
    return BacktestDiagnosticsInputs(
        synthetic_snapshot=_build_synthetic_snapshot_from_weights(portfolio_name, weights, result),
        replay_daily_states=_build_daily_states_from_equity_curve(result, weights, histories),
        benchmark_price_history=[row for row in benchmark_rows if result.start_date <= row["date"] <= result.end_date],
        factor_price_histories={definition.us_proxy: histories.get(definition.us_proxy, benchmark_rows) for definition in factor_registry},
    )


def _build_synthetic_snapshot_from_weights(portfolio_name: str, weights, result: AllocationBacktestResult):
    imported_at = datetime.fromisoformat(result.end_date).replace(tzinfo=UTC)
    ending_equity = result.equity_curve[-1].equity if result.equity_curve else 0.0
    base_currency = result.assumptions.investor_base_currency or "USD"
    return ImportedPortfolioSnapshot(
        statement=ImportedStatement(
            importer="multi_broker",
            imported_at=imported_at,
            source_path=f"{portfolio_name.lower()}-backtest",
            detected_format="synthetic_backtest",
            account_id=portfolio_name,
            base_currency=base_currency,
            statement_period=f"{result.start_date} - {result.end_date}",
            page_count=1,
        ),
        statements=[],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency=base_currency, ending_cash=0.0)],
        positions=[
            ImportedPosition(
                as_of_date=datetime.fromisoformat(result.end_date).date(),
                symbol=item.symbol,
                quantity=1.0,
                cost_basis=round(ending_equity * item.target_weight, 2),
                close_price=round(ending_equity * item.target_weight, 2),
                market_value=round(ending_equity * item.target_weight, 2),
                unrealized_pnl=0.0,
                currency=base_currency,
            )
            for item in weights
        ],
        ledger_entries=[],
    )


def _build_daily_states_from_equity_curve(result: AllocationBacktestResult, weights, histories: dict[str, list[dict]]) -> list[DailyPortfolioState]:
    history_maps = {
        item.symbol: {row["date"]: float(row.get("adjClose") or row.get("adjusted_close") or row.get("price") or 0.0) for row in histories.get(item.symbol, [])}
        for item in weights
    }
    states: list[DailyPortfolioState] = []
    for point in result.equity_curve:
        positions: list[DailyStatePosition] = []
        total_market_value = 0.0
        for item in weights:
            price = history_maps.get(item.symbol, {}).get(point.date)
            market_value = (point.equity * item.target_weight) if price is not None else None
            total_market_value += market_value or 0.0
            quantity = 0.0
            if market_value is not None and isinstance(price, (int, float)) and price != 0:
                quantity = float(market_value) / float(price)
            market_price = float(price) if isinstance(price, (int, float)) else None
            positions.append(DailyStatePosition(symbol=item.symbol, quantity=quantity, market_price=market_price, market_value=market_value))
        states.append(
            DailyPortfolioState(
                date=point.date,
                cash={result.assumptions.investor_base_currency or "USD": point.cash},
                positions=positions,
                total_market_value=round(total_market_value, 2),
                total_portfolio_value=point.equity,
                external_cash_flow=0.0,
            )
        )
    return states


def _build_fallback_factor_snapshot(weights, factor_registry) -> list[SnapshotItem]:
    weight_by_symbol = {item.symbol.upper(): item.target_weight for item in weights}
    snapshots: list[SnapshotItem] = []
    for definition in factor_registry:
        mapping_symbols: set[str] = {definition.us_proxy.upper()}
        if definition.primary_mapping is not None:
            mapping_symbols.update(symbol.upper() for symbol in definition.primary_mapping.example_tickers)
        for mapping in definition.alternative_mappings:
            mapping_symbols.update(symbol.upper() for symbol in mapping.example_tickers)
        loading = sum(weight_by_symbol.get(symbol, 0.0) for symbol in mapping_symbols)
        snapshots.append(
            SnapshotItem(
                key=definition.key,
                label=definition.label,
                category=definition.category,
                us_proxy=definition.us_proxy,
                latest_loading=round(loading, 4) if loading > 0 else 0.0,
                target_exposure=definition.target_exposure,
                primary_mapping=definition.primary_mapping,
                alternative_mappings=definition.alternative_mappings,
                ucits_examples=definition.ucits_examples,
                mapping_quality=definition.mapping_quality,
                description=definition.description,
            )
        )
    return snapshots


def _build_diagnostics_comparison(
    baseline: PortfolioDiagnosticsSnapshot,
    candidate: PortfolioDiagnosticsSnapshot,
) -> PortfolioImprovementComparison:
    return PortfolioImprovementComparison(
        factor_exposure_changes=_factor_exposure_change_rows(baseline, candidate),
        volatility_changes=_volatility_change_rows(baseline, candidate),
        risk_contribution_changes=_risk_contribution_change_rows(baseline, candidate),
        concentration_changes=_concentration_change_rows(baseline, candidate),
        stress_scenario_changes=_stress_change_rows(baseline, candidate),
    )


def _factor_exposure_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    baseline_map = {item.key: item for item in baseline.factor_snapshot}
    candidate_map = {item.key: item for item in candidate.factor_snapshot}
    keys = sorted(set(baseline_map) | set(candidate_map))
    rows: list[PortfolioDiagnosticsComparisonRow] = []
    for key in keys:
        baseline_item = baseline_map.get(key)
        candidate_item = candidate_map.get(key)
        label = key
        if candidate_item is not None:
            label = candidate_item.label
        elif baseline_item is not None:
            label = baseline_item.label
        baseline_value = baseline_item.latest_loading if baseline_item is not None else None
        candidate_value = candidate_item.latest_loading if candidate_item is not None else None
        rows.append(
            PortfolioDiagnosticsComparisonRow(
                key=key,
                label=label,
                baseline_value=baseline_value,
                candidate_value=candidate_value,
                delta_value=_diff(baseline_value, candidate_value),
            )
        )
    return rows


def _volatility_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    rows = [
        ("annualized_volatility", "Annualized Volatility", baseline.volatility_snapshot.realized_vol_252d if baseline.volatility_snapshot else None, candidate.volatility_snapshot.realized_vol_252d if candidate.volatility_snapshot else None),
        ("downside_volatility", "Downside Volatility", baseline.volatility_snapshot.downside_vol_252d if baseline.volatility_snapshot else None, candidate.volatility_snapshot.downside_vol_252d if candidate.volatility_snapshot else None),
        ("max_drawdown", "Max Drawdown", baseline.volatility_snapshot.max_drawdown_pct if baseline.volatility_snapshot else None, candidate.volatility_snapshot.max_drawdown_pct if candidate.volatility_snapshot else None),
        ("tracking_error", "Tracking Error", baseline.volatility_snapshot.tracking_error_252d if baseline.volatility_snapshot else None, candidate.volatility_snapshot.tracking_error_252d if candidate.volatility_snapshot else None),
    ]
    return [PortfolioDiagnosticsComparisonRow(key=key, label=label, baseline_value=left, candidate_value=right, delta_value=_diff(left, right)) for key, label, left, right in rows]


def _risk_contribution_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    baseline_map = {item.key: item for item in (baseline.risk_contribution.factor_contributions if baseline.risk_contribution else [])}
    candidate_map = {item.key: item for item in (candidate.risk_contribution.factor_contributions if candidate.risk_contribution else [])}
    keys = sorted(set(baseline_map) | set(candidate_map))
    rows: list[PortfolioDiagnosticsComparisonRow] = []
    for key in keys:
        baseline_item = baseline_map.get(key)
        candidate_item = candidate_map.get(key)
        label = key
        if candidate_item is not None:
            label = candidate_item.label
        elif baseline_item is not None:
            label = baseline_item.label
        baseline_value = baseline_item.risk_share if baseline_item is not None else None
        candidate_value = candidate_item.risk_share if candidate_item is not None else None
        rows.append(
            PortfolioDiagnosticsComparisonRow(
                key=key,
                label=label,
                baseline_value=baseline_value,
                candidate_value=candidate_value,
                delta_value=_diff(baseline_value, candidate_value),
            )
        )
    return rows


def _concentration_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    if not baseline.risk_contribution or not candidate.risk_contribution:
        return []
    rows = [
        ("top_1_position_risk_share", "Top 1 Position Risk Share", baseline.risk_contribution.concentration.top_1_position_risk_share, candidate.risk_contribution.concentration.top_1_position_risk_share),
        ("top_5_position_risk_share", "Top 5 Position Risk Share", baseline.risk_contribution.concentration.top_5_position_risk_share, candidate.risk_contribution.concentration.top_5_position_risk_share),
        ("factor_hhi", "Factor HHI", baseline.risk_contribution.concentration.factor_hhi, candidate.risk_contribution.concentration.factor_hhi),
        ("position_hhi", "Position HHI", baseline.risk_contribution.concentration.position_hhi, candidate.risk_contribution.concentration.position_hhi),
    ]
    return [PortfolioDiagnosticsComparisonRow(key=key, label=label, baseline_value=left, candidate_value=right, delta_value=_diff(left, right)) for key, label, left, right in rows]


def _stress_change_rows(baseline: PortfolioDiagnosticsSnapshot, candidate: PortfolioDiagnosticsSnapshot) -> list[PortfolioDiagnosticsComparisonRow]:
    baseline_map = {item.name: item for item in baseline.stress_scenarios}
    candidate_map = {item.name: item for item in candidate.stress_scenarios}
    keys = sorted(set(baseline_map) | set(candidate_map))
    rows: list[PortfolioDiagnosticsComparisonRow] = []
    for key in keys:
        baseline_item = baseline_map.get(key)
        candidate_item = candidate_map.get(key)
        baseline_value = baseline_item.estimated_return_pct if baseline_item is not None else None
        candidate_value = candidate_item.estimated_return_pct if candidate_item is not None else None
        rows.append(
            PortfolioDiagnosticsComparisonRow(
                key=key.lower().replace(" ", "_"),
                label=key,
                baseline_value=baseline_value,
                candidate_value=candidate_value,
                delta_value=_diff(baseline_value, candidate_value),
            )
        )
    return rows


def _derive_status(
    *,
    symbols: list[str],
    ordered_dates: list[str],
    requested_start: str,
    requested_end: str,
    registry: InstrumentRegistry,
    histories: dict[str, list[dict]],
    benchmark_rows: list[dict],
) -> AllocationBacktestStatus:
    if not ordered_dates:
        return "rejected"
    status: AllocationBacktestStatus = "ok"
    if ordered_dates[0] > requested_start or ordered_dates[-1] < requested_end:
        status = "degraded"
    if not _has_adjusted_price_history(benchmark_rows):
        status = "degraded"
    if any(not _has_adjusted_price_history(histories.get(symbol, [])) for symbol in symbols):
        status = "degraded"
    if any(_is_distributing_without_adjusted_history(symbol, histories.get(symbol, []), registry) for symbol in symbols):
        status = "degraded"
    return status


def _instrument_metadata(symbols: list[str], registry: InstrumentRegistry) -> list[AllocationBacktestInstrumentMeta]:
    metadata: list[AllocationBacktestInstrumentMeta] = []
    for symbol in symbols:
        instrument = registry.get_instrument(symbol)
        metadata.append(
            AllocationBacktestInstrumentMeta(
                symbol=symbol,
                trading_currency=instrument.currency if instrument else None,
                instrument_base_currency=instrument.currency if instrument else None,
                currency_hedged=None,
                distribution_policy=_distribution_policy(instrument.category if instrument else None),
            )
        )
    return metadata


def _is_ucits_symbol(symbol: str, registry: InstrumentRegistry) -> bool:
    instrument = registry.get_instrument(symbol)
    if instrument is None or instrument.category is None:
        return False
    return instrument.category.endswith("UCITS ETF")


def _has_adjusted_price_history(rows: list[dict]) -> bool:
    return any(row.get("adjClose") is not None or row.get("adjusted_close") is not None for row in rows)


def _distribution_policy(category: str | None) -> DistributionPolicy:
    if category is None:
        return "unknown"
    if "UCITS" in category:
        return "accumulating"
    return "unknown"


def _is_distributing_without_adjusted_history(symbol: str, rows: list[dict], registry: InstrumentRegistry) -> bool:
    instrument = registry.get_instrument(symbol)
    if instrument is None:
        return False
    if _distribution_policy(instrument.category) != "distributing":
        return False
    return not _has_adjusted_price_history(rows)
