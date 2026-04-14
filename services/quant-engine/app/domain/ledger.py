from datetime import date
from typing import Literal

from pydantic import BaseModel

from app.schemas.imports import ImportedPortfolioSnapshot, LedgerEntryType


LedgerAccountBucket = Literal["TRADE", "INCOME", "EXPENSE", "TRANSFER"]
LotSource = Literal["opening_balance", "statement_trade"]


class LedgerRecord(BaseModel):
    date: date
    entry_type: LedgerEntryType
    account_bucket: LedgerAccountBucket
    symbol: str | None = None
    description: str | None = None
    signed_quantity: float | None = None
    quantity: float | None = None
    price: float | None = None
    gross_amount: float | None = None
    net_amount: float | None = None
    cash_effect: float
    asset_currency: str | None = None
    cash_currency: str
    affects_positions: bool
    affects_cash: bool
    fee: float | None = None
    tax: float | None = None
    source_section: str
    source_line: str | None = None


class PositionLot(BaseModel):
    symbol: str
    opened_on: date | None
    source: LotSource
    currency: str
    original_quantity: float
    remaining_quantity: float
    unit_cost: float | None
    remaining_cost_basis: float | None
    cost_basis_is_estimated: bool = False


def snapshot_to_ledger(snapshot: ImportedPortfolioSnapshot) -> list[LedgerRecord]:
    symbol_currencies = {position.symbol: position.currency for position in snapshot.positions}

    def account_bucket(entry_type: LedgerEntryType) -> LedgerAccountBucket:
        if entry_type in {"BUY", "SELL"}:
            return "TRADE"
        if entry_type in {"DIVIDEND", "INTEREST"}:
            return "INCOME"
        if entry_type in {"WITHHOLDING_TAX", "FEE"}:
            return "EXPENSE"
        return "TRANSFER"

    def signed_quantity(entry_type: LedgerEntryType, quantity: float | None) -> float | None:
        if quantity is None:
            return None
        if entry_type == "BUY":
            return quantity
        if entry_type == "SELL":
            return -quantity
        return None

    records = [
        LedgerRecord(
            date=entry.trade_date,
            entry_type=entry.entry_type,
            account_bucket=account_bucket(entry.entry_type),
            symbol=entry.symbol,
            description=entry.description,
            signed_quantity=signed_quantity(entry.entry_type, entry.quantity),
            quantity=entry.quantity,
            price=entry.price,
            gross_amount=entry.gross_amount,
            net_amount=entry.net_amount,
            cash_effect=entry.net_amount or 0.0,
            asset_currency=symbol_currencies.get(entry.symbol) if entry.symbol else None,
            cash_currency=entry.currency,
            affects_positions=entry.entry_type in {"BUY", "SELL"},
            affects_cash=True,
            fee=entry.fee,
            tax=entry.tax,
            source_section=entry.source_section,
            source_line=entry.source_line,
        )
        for entry in snapshot.ledger_entries
    ]

    return sorted(records, key=lambda entry: (entry.date, entry.symbol or "", entry.entry_type, entry.description or ""))


def reconstruct_position_lots(snapshot: ImportedPortfolioSnapshot) -> list[PositionLot]:
    ledger = snapshot_to_ledger(snapshot)
    ending_positions = {position.symbol: position for position in snapshot.positions}
    symbol_lots: dict[str, list[PositionLot]] = {}

    trade_entries = [entry for entry in ledger if entry.affects_positions and entry.symbol and entry.quantity]
    traded_symbols = {entry.symbol for entry in trade_entries if entry.symbol}

    for symbol in sorted(set(ending_positions) | traded_symbols):
        ending_position = ending_positions.get(symbol)
        symbol_currency = (ending_position.currency if ending_position else None) or next(
            (entry.asset_currency for entry in trade_entries if entry.symbol == symbol and entry.asset_currency),
            snapshot.statement.base_currency or "USD",
        )
        ending_quantity = ending_position.quantity if ending_position else 0.0
        symbol_buys = sum(entry.quantity or 0.0 for entry in trade_entries if entry.symbol == symbol and entry.entry_type == "BUY")
        symbol_sells = sum(entry.quantity or 0.0 for entry in trade_entries if entry.symbol == symbol and entry.entry_type == "SELL")
        opening_quantity = round(ending_quantity + symbol_sells - symbol_buys, 6)

        lots: list[PositionLot] = []
        if opening_quantity > 1e-9:
            estimated_unit_cost = None
            if ending_position is not None and ending_position.quantity > 0:
                estimated_unit_cost = round(ending_position.cost_basis / ending_position.quantity, 6)

            lots.append(
                PositionLot(
                    symbol=symbol,
                    opened_on=None,
                    source="opening_balance",
                    currency=symbol_currency,
                    original_quantity=opening_quantity,
                    remaining_quantity=opening_quantity,
                    unit_cost=estimated_unit_cost,
                    remaining_cost_basis=round(opening_quantity * estimated_unit_cost, 2) if estimated_unit_cost is not None else None,
                    cost_basis_is_estimated=estimated_unit_cost is not None,
                )
            )

        for entry in sorted(
            [candidate for candidate in trade_entries if candidate.symbol == symbol],
            key=lambda item: (item.date, item.entry_type, item.description or ""),
        ):
            if entry.entry_type == "BUY":
                unit_cost = round(entry.price, 6) if entry.price is not None else None
                quantity = round(entry.quantity or 0.0, 6)
                lots.append(
                    PositionLot(
                        symbol=symbol,
                        opened_on=entry.date,
                        source="statement_trade",
                        currency=symbol_currency,
                        original_quantity=quantity,
                        remaining_quantity=quantity,
                        unit_cost=unit_cost,
                        remaining_cost_basis=round(quantity * unit_cost, 2) if unit_cost is not None else None,
                        cost_basis_is_estimated=False,
                    )
                )
                continue

            remaining_to_sell = round(entry.quantity or 0.0, 6)
            for lot in lots:
                if remaining_to_sell <= 1e-9:
                    break
                if lot.remaining_quantity <= 1e-9:
                    continue

                consumed_quantity = min(lot.remaining_quantity, remaining_to_sell)
                unit_cost = lot.unit_cost
                lot.remaining_quantity = round(lot.remaining_quantity - consumed_quantity, 6)
                if unit_cost is not None:
                    lot.remaining_cost_basis = round(max((lot.remaining_cost_basis or 0.0) - (consumed_quantity * unit_cost), 0.0), 2)
                remaining_to_sell = round(remaining_to_sell - consumed_quantity, 6)

        open_lots = [lot for lot in lots if lot.remaining_quantity > 1e-9]
        if open_lots:
            symbol_lots[symbol] = open_lots

    return [lot for symbol in sorted(symbol_lots) for lot in symbol_lots[symbol]]
