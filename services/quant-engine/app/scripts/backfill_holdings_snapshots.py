from __future__ import annotations

from app.services.market_data import MarketDataService


DEFAULT_SYMBOLS = ["SPY", "QQQ", "XLK", "XLF", "XLV", "XLE", "XLI", "IWM"]


def main() -> None:
    service = MarketDataService()
    for symbol in DEFAULT_SYMBOLS:
        resolved_symbol, rows = service.get_etf_holdings(symbol)
        count = service.holdings_history.get_snapshot_count(symbol)
        print(f"{symbol}: resolved={resolved_symbol or 'n/a'} rows={len(rows)} snapshots={count}")


if __name__ == "__main__":
    main()
