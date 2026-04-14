from __future__ import annotations

from app.strategies.base import StrategyImplementation
from app.strategies.book_ma_filter import BookMovingAverageFilterStrategy
from app.strategies.book_trend_breakout import BookTrendBreakoutStrategy
from app.schemas.research import BacktestFrequency, StrategyDefinition, StrategyParameter, StrategySide


class StrategyRegistry:
    def __init__(self) -> None:
        self._implementations: dict[str, StrategyImplementation] = {
            "book_trend_breakout": BookTrendBreakoutStrategy(),
            "book_ma_filter": BookMovingAverageFilterStrategy(),
        }
        self._definitions: dict[str, dict] = {
            "book_trend_breakout": {
                "name": "Book Trend Breakout",
                "description": "Starter daily futures breakout template for strategy research scaffolding.",
                "side": "both",
                "tags": ["book", "trend", "breakout", "futures"],
                "parameters": [
                    StrategyParameter(name="lookback_days", value=50),
                    StrategyParameter(name="atr_period", value=20),
                    StrategyParameter(name="risk_per_trade_pct", value=0.01),
                ],
            },
            "book_ma_filter": {
                "name": "Book Moving Average Filter",
                "description": "Starter moving-average filter template for daily futures systems.",
                "side": "both",
                "tags": ["book", "moving-average", "futures"],
                "parameters": [
                    StrategyParameter(name="fast_window", value=20),
                    StrategyParameter(name="slow_window", value=100),
                ],
            },
        }

    def get_definition(self, strategy_id: str, universe: list[str], timeframe: BacktestFrequency = "1d") -> StrategyDefinition | None:
        template = self._definitions.get(strategy_id)
        if template is None:
            return None

        return StrategyDefinition(
            strategy_id=strategy_id,
            name=template["name"],
            description=template["description"],
            timeframe=timeframe,
            side=template["side"],
            universe=universe,
            parameters=template["parameters"],
            tags=template["tags"],
        )

    def list_strategy_ids(self) -> list[str]:
        return sorted(self._definitions)

    def get_implementation(self, strategy_id: str) -> StrategyImplementation | None:
        return self._implementations.get(strategy_id)
