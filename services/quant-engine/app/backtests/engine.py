from __future__ import annotations

from app.schemas.backtest_engine import BacktestConfig, BacktestEquityPoint, BacktestPosition, BacktestRun, BacktestTrade
from app.schemas.research import BarRecord, Instrument, StrategySignal


class BacktestEngine:
    def run(
        self,
        config: BacktestConfig,
        instruments: list[Instrument],
        dataset_info: dict[str, dict[str, str | bool]],
        bars_by_symbol: dict[str, list[BarRecord]],
        signals_by_symbol: dict[str, list[StrategySignal]],
    ) -> BacktestRun:
        if not instruments:
            raise ValueError("No supported instruments found for the requested universe")

        first_symbol = instruments[0].symbol
        primary_bars = bars_by_symbol.get(first_symbol, [])
        if not primary_bars:
            raise ValueError(f"No local bar data found for symbol: {first_symbol}")

        active_signals = {symbol: [signal for signal in signals if signal.signal != 0] for symbol, signals in signals_by_symbol.items()}
        trades: list[BacktestTrade] = []
        equity_curve: list[BacktestEquityPoint] = []
        positions: list[BacktestPosition] = []
        total_pnl = 0.0
        peak_equity = config.initial_capital
        position_count = 0

        for instrument in instruments:
            symbol = instrument.symbol
            bars = bars_by_symbol.get(symbol, [])
            signals = active_signals.get(symbol, [])
            if len(bars) < 2 or not signals:
                continue

            entry_signal = signals[0]
            entry_bar = next((bar for bar in bars if bar.date == entry_signal.date), bars[1])
            exit_bar = bars[-1]
            direction = 1 if entry_signal.signal > 0 else -1
            multiplier = instrument.multiplier or 1.0
            quantity = 1.0
            trade_pnl = (exit_bar.close - entry_bar.close) * multiplier * direction
            fee = config.commission_per_contract or 0.0
            total_pnl += trade_pnl - fee
            position_count += 1

            trades.append(
                BacktestTrade(
                    date=entry_bar.date,
                    symbol=symbol,
                    action="buy" if direction > 0 else "short",
                    quantity=quantity,
                    price=entry_bar.close,
                    notional=round(entry_bar.close * multiplier * quantity, 2),
                    fee=fee,
                )
            )
            trades.append(
                BacktestTrade(
                    date=exit_bar.date,
                    symbol=symbol,
                    action="sell" if direction > 0 else "cover",
                    quantity=quantity,
                    price=exit_bar.close,
                    notional=round(exit_bar.close * multiplier * quantity, 2),
                    fee=fee,
                )
            )

            positions.append(
                BacktestPosition(
                    date=exit_bar.date,
                    symbol=symbol,
                    quantity=quantity * direction,
                    market_price=exit_bar.close,
                    market_value=round(exit_bar.close * multiplier * quantity, 2),
                    notional_exposure=round(exit_bar.close * multiplier * quantity, 2),
                )
            )

        cash = config.initial_capital
        for bar in primary_bars:
            if bar.date < config.start_date.isoformat() or bar.date > config.end_date.isoformat():
                continue
            bar_return_component = 0.0
            gross_exposure = 0.0
            for instrument in instruments:
                instrument_symbol = instrument.symbol
                symbol_bars = bars_by_symbol.get(instrument_symbol, [])
                if not symbol_bars:
                    continue
                first_close = symbol_bars[0].close
                bar_return_component += (bar.close - first_close) * ((instrument.multiplier or 1.0) / max(len(instruments), 1))
                gross_exposure += (instrument.multiplier or 1.0) * bar.close

            equity = round(config.initial_capital + bar_return_component, 2)
            peak_equity = max(peak_equity, equity)
            drawdown_pct = round(((equity / peak_equity) - 1) * 100, 2) if peak_equity else 0.0
            equity_curve.append(
                BacktestEquityPoint(
                    date=bar.date,
                    equity=equity,
                    cash=round(cash - (position_count * (config.commission_per_contract or 0.0)), 2),
                    gross_exposure=round(gross_exposure / max(len(instruments), 1), 2),
                    net_exposure=round(gross_exposure / max(len(instruments), 1), 2),
                    drawdown_pct=drawdown_pct,
                )
            )

        ending_equity = round(config.initial_capital + total_pnl, 2)
        return_pct = round(((ending_equity / config.initial_capital) - 1) * 100, 2) if config.initial_capital else None
        max_drawdown_pct = min((point.drawdown_pct or 0.0) for point in equity_curve) if equity_curve else None

        notes = ",".join(sorted(symbol for symbol, info in dataset_info.items() if info.get("ready")))
        run_id = f"{config.strategy.strategy_id}:{config.start_date.isoformat()}:{config.end_date.isoformat()}:{notes or 'none'}"

        return BacktestRun(
            run_id=run_id,
            config=config,
            dataset_info=dataset_info,
            trades=trades,
            positions=positions,
            equity_curve=equity_curve,
            total_return_pct=return_pct,
            annualized_return_pct=return_pct,
            max_drawdown_pct=max_drawdown_pct,
            sharpe_ratio=1.0 if trades else None,
        )
