from __future__ import annotations

from typing import Protocol

from app.schemas.backtest_engine import BacktestConfig
from app.schemas.research import BarRecord, StrategySignal


class StrategyImplementation(Protocol):
    strategy_id: str

    def generate_signals(self, symbol: str, bars: list[BarRecord], config: BacktestConfig) -> list[StrategySignal]: ...
