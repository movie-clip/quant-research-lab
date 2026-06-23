from collections import defaultdict

from app.domain.ledger import snapshot_to_ledger
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import HoldingsTimelinePoint, PortfolioActivityPoint


def build_activity_series(snapshot: ImportedPortfolioSnapshot) -> list[PortfolioActivityPoint]:
    ledger = snapshot_to_ledger(snapshot)
    grouped: dict[str, dict[str, float]] = defaultdict(
        lambda: {
            "BUY": 0.0,
            "SELL": 0.0,
            "DIVIDEND": 0.0,
            "WITHHOLDING_TAX": 0.0,
            "INTEREST": 0.0,
            "FEE": 0.0,
            "DEPOSIT": 0.0,
            "WITHDRAWAL": 0.0,
        }
    )

    for entry in ledger:
        month = entry.date.strftime("%Y-%m")
        amount = entry.cash_effect
        if entry.entry_type in {"BUY", "FEE", "WITHHOLDING_TAX", "WITHDRAWAL"}:
            grouped[month][entry.entry_type] += abs(amount)
        else:
            grouped[month][entry.entry_type] += amount

    points: list[PortfolioActivityPoint] = []
    for month in sorted(grouped):
        bucket = grouped[month]
        net_cash_flow = round(
            bucket["SELL"] + bucket["DIVIDEND"] + bucket["INTEREST"] + bucket["DEPOSIT"] - bucket["BUY"] - bucket["WITHHOLDING_TAX"] - bucket["FEE"] - bucket["WITHDRAWAL"],
            2,
        )
        points.append(
            PortfolioActivityPoint(
                month=month,
                buys=round(bucket["BUY"], 2),
                sells=round(bucket["SELL"], 2),
                dividends=round(bucket["DIVIDEND"], 2),
                withholding_tax=round(bucket["WITHHOLDING_TAX"], 2),
                interest=round(bucket["INTEREST"], 2),
                fees=round(bucket["FEE"], 2),
                deposits=round(bucket["DEPOSIT"], 2),
                withdrawals=round(bucket["WITHDRAWAL"], 2),
                net_cash_flow=net_cash_flow,
            )
        )

    return points


def build_holdings_timeline(snapshot: ImportedPortfolioSnapshot) -> list[HoldingsTimelinePoint]:
    ledger = snapshot_to_ledger(snapshot)
    ending_positions = {position.symbol: position.quantity for position in snapshot.positions}
    sold_only_symbols = {entry.symbol for entry in ledger if entry.entry_type == "SELL" and entry.symbol}

    buy_totals: defaultdict[str, float] = defaultdict(float)
    sell_totals: defaultdict[str, float] = defaultdict(float)
    for entry in ledger:
        if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
            buy_totals[entry.symbol] += entry.quantity
        elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
            sell_totals[entry.symbol] += entry.quantity

    opening_positions: dict[str, float] = {}
    for symbol in sold_only_symbols:
        ending_qty = ending_positions.get(symbol, 0.0)
        opening_positions[symbol] = ending_qty + sell_totals[symbol] - buy_totals[symbol]

    running_positions: defaultdict[str, float] = defaultdict(float, opening_positions)
    timeline: list[HoldingsTimelinePoint] = []
    trades = sorted(
        [entry for entry in ledger if entry.entry_type in {"BUY", "SELL"} and entry.symbol and entry.quantity],
        key=lambda item: (item.date, item.symbol or ""),
    )

    for trade in trades:
        signed_quantity = trade.quantity or 0.0
        if trade.entry_type == "SELL":
            signed_quantity *= -1
        running_positions[trade.symbol or ""] += signed_quantity
        timeline.append(HoldingsTimelinePoint(date=trade.date.isoformat(), symbol=trade.symbol or "", quantity=round(running_positions[trade.symbol or ""], 6)))

    return timeline
