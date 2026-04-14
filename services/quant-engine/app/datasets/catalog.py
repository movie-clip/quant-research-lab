from __future__ import annotations

from datetime import date, timedelta

from app.core.symbols import resolve_proxy_candidates
from app.services.market_data import MarketDataService
from app.datasets.sample_data import SAMPLE_BAR_SERIES, SAMPLE_ETF_HOLDINGS, SAMPLE_ETF_HOLDINGS_BY_DATE
from app.schemas.research import BarRecord

class DatasetCatalog:
    def __init__(self) -> None:
        self.market_data = MarketDataService()

    def _is_continuous_future(self, symbol: str) -> bool:
        normalized_symbol = symbol.upper()
        return normalized_symbol in {"ES", "NQ", "CL", "GC"} or "future" in normalized_symbol.lower()

    def _continuous_proxy_label(self, symbol: str) -> str:
        candidates = resolve_proxy_candidates(symbol)
        if not candidates:
            return "proxy approximation"
        return f"proxy approximation ({candidates[0]})"

    def get_series_info(self, symbol: str, timeframe: str) -> dict[str, str | bool]:
        is_continuous_future = self._is_continuous_future(symbol)
        has_live_history = bool(self._load_live_bars(symbol, allow_continuous_proxy=is_continuous_future))
        sample_ready = bool(SAMPLE_BAR_SERIES.get(symbol.upper()))
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "source": self._continuous_proxy_label(symbol) if is_continuous_future and has_live_history else "fmp" if has_live_history else "local approximation" if is_continuous_future and sample_ready else "local-sample" if sample_ready else "unavailable",
            "continuous": is_continuous_future,
            "ready": has_live_history or sample_ready,
        }

    def get_series_info_for_symbols(self, symbols: list[str], timeframe: str) -> dict[str, dict[str, str | bool]]:
        return {symbol: self.get_series_info(symbol, timeframe) for symbol in symbols}

    def get_daily_bars(self, symbol: str) -> list[BarRecord]:
        live_bars = self._load_live_bars(symbol, allow_continuous_proxy=self._is_continuous_future(symbol))
        if live_bars:
            return live_bars
        return SAMPLE_BAR_SERIES.get(symbol.upper(), [])

    def get_daily_bars_for_symbols(self, symbols: list[str]) -> dict[str, list[BarRecord]]:
        return {symbol: self.get_daily_bars(symbol) for symbol in symbols}

    def _load_live_bars(self, symbol: str, *, allow_continuous_proxy: bool = False) -> list[BarRecord]:
        normalized_symbol = symbol.upper()

        to_date = date.today()
        from_date = to_date - timedelta(days=365 * 8)
        rows = self.market_data.get_historical_prices(normalized_symbol, from_date.isoformat(), to_date.isoformat(), allow_proxy_fallback=allow_continuous_proxy or not self._is_continuous_future(normalized_symbol))
        bars: list[BarRecord] = []
        for row in sorted(rows, key=lambda item: str(item.get("date") or "")):
            price_value = row.get("price", row.get("close"))
            if price_value is None:
                continue
            close = float(price_value)
            volume_value = row.get("volume")
            bars.append(
                BarRecord(
                    date=str(row.get("date")),
                    open=close,
                    high=close,
                    low=close,
                    close=close,
                    volume=float(volume_value) if volume_value is not None else None,
                )
            )
        return bars

    def get_etf_holdings(self, symbol: str) -> list[dict[str, str | float]]:
        return SAMPLE_ETF_HOLDINGS.get(symbol.upper(), [])

    def get_etf_holdings_for_date(self, symbol: str, as_of_date: str) -> list[dict[str, str | float]]:
        dated = SAMPLE_ETF_HOLDINGS_BY_DATE.get(symbol.upper())
        if not dated:
            return self.get_etf_holdings(symbol)
        selected = None
        for effective_date, holdings in dated:
            if effective_date <= as_of_date:
                selected = holdings
            else:
                break
        return selected if selected is not None else dated[0][1]
