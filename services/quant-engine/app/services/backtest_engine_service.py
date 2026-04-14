from __future__ import annotations

from app.backtests import BacktestEngine
from app.datasets import DatasetCatalog
from app.instruments import InstrumentRegistry
from app.overlay import build_overlay_run
from app.schemas.backtest_engine import BacktestConfig, BacktestRun, OverlayRun
from app.strategies import StrategyRegistry


class BacktestAnalysisResult(BacktestRun):
    overlay_preview: OverlayRun | None = None


def build_backtest_analysis(config: BacktestConfig) -> BacktestAnalysisResult:
    strategy_registry = StrategyRegistry()
    instrument_registry = InstrumentRegistry()
    dataset_catalog = DatasetCatalog()
    engine = BacktestEngine()

    strategy = strategy_registry.get_definition(
        config.strategy.strategy_id,
        config.strategy.universe,
        config.strategy.timeframe,
    )
    if strategy is None:
        raise ValueError(f"Unknown strategy id: {config.strategy.strategy_id}")

    implementation = strategy_registry.get_implementation(config.strategy.strategy_id)
    if implementation is None:
        raise ValueError(f"No strategy implementation registered for: {config.strategy.strategy_id}")

    resolved_config = config.model_copy(update={"strategy": strategy})
    instruments = instrument_registry.list_instruments(strategy.universe)
    dataset_info = dataset_catalog.get_series_info_for_symbols(strategy.universe, strategy.timeframe)
    bars_by_symbol = dataset_catalog.get_daily_bars_for_symbols(strategy.universe)
    signals_by_symbol = {
        symbol: implementation.generate_signals(symbol, bars_by_symbol.get(symbol, []), resolved_config)
        for symbol in strategy.universe
    }
    run = engine.run(resolved_config, instruments, dataset_info, bars_by_symbol, signals_by_symbol)

    return BacktestAnalysisResult(**run.model_dump(), overlay_preview=build_overlay_run(run))
