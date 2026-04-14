from __future__ import annotations

from app.schemas.backtest_engine import BacktestConfig
from app.schemas.research import BarRecord, StrategySignal


class BookMovingAverageFilterStrategy:
    strategy_id = "book_ma_filter"

    def generate_signals(self, symbol: str, bars: list[BarRecord], config: BacktestConfig) -> list[StrategySignal]:
        if not bars:
            return []

        closes: list[float] = []
        signals: list[StrategySignal] = []

        for bar in bars:
            closes.append(bar.close)
            moving_average = sum(closes) / len(closes)
            signal = 1 if bar.close >= moving_average else -1
            reason = "close_above_average" if signal == 1 else "close_below_average"
            signals.append(StrategySignal(date=bar.date, symbol=symbol, signal=signal, reason=reason))

        return signals
