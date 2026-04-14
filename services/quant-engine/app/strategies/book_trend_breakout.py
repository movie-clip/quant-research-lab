from __future__ import annotations

from app.schemas.backtest_engine import BacktestConfig
from app.schemas.research import BarRecord, StrategySignal


class BookTrendBreakoutStrategy:
    strategy_id = "book_trend_breakout"

    def generate_signals(self, symbol: str, bars: list[BarRecord], config: BacktestConfig) -> list[StrategySignal]:
        if len(bars) < 2:
            return []

        signals: list[StrategySignal] = []
        running_high = bars[0].high
        running_low = bars[0].low

        for index, bar in enumerate(bars):
            if index == 0:
                signals.append(StrategySignal(date=bar.date, symbol=symbol, signal=0, reason="initial_bar"))
                continue

            previous_high = running_high
            previous_low = running_low
            signal = 0
            reason = "inside_range"

            if bar.close > previous_high:
                signal = 1
                reason = "breakout_above_prior_range"
            elif bar.close < previous_low:
                signal = -1
                reason = "breakdown_below_prior_range"

            signals.append(StrategySignal(date=bar.date, symbol=symbol, signal=signal, reason=reason))
            running_high = max(running_high, bar.high)
            running_low = min(running_low, bar.low)

        return signals
