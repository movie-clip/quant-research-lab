from __future__ import annotations

from app.schemas.backtest_engine import BacktestRun, OverlayRun, StrategyAllocation


def build_overlay_run(backtest_run: BacktestRun, base_portfolio_name: str = "Imported Portfolio") -> OverlayRun:
    return OverlayRun(
        overlay_id=f"overlay:{backtest_run.run_id}",
        base_portfolio_name=base_portfolio_name,
        allocations=[
            StrategyAllocation(
                sleeve_id="base-portfolio",
                name=base_portfolio_name,
                capital_weight=0.8,
                source="imported_portfolio",
            ),
            StrategyAllocation(
                sleeve_id=f"strategy:{backtest_run.config.strategy.strategy_id}",
                name=backtest_run.config.strategy.name,
                capital_weight=0.2,
                source="strategy_run",
                strategy_run_id=backtest_run.run_id,
            ),
        ],
        equity_curve=backtest_run.equity_curve,
        notes="Starter overlay preview generated from the research engine skeleton.",
    )
