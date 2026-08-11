from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.imports import ImportedPortfolioSnapshot, LedgerEntryType


LedgerAccountBucket = Literal["TRADE", "INCOME", "EXPENSE", "TRANSFER"]
LotSource = Literal["opening_balance", "statement_trade"]
CashMovementClassification = Literal[
    "external_capital_flow",
    "internal_trading_flow",
    "broker_explicit_dividend",
    "broker_explicit_interest",
    "broker_explicit_fee",
    "broker_explicit_tax",
    "unknown",
]
OpeningStateSource = Literal["broker_proven", "trade_window_covered", "unknown_inferred"]

# ── Broker section-role registry (US-24.5) ──────────────────────────────────
#
# `source_section` is PROVENANCE: it records what the statement actually called
# the section, so an importer must never relabel its broker's vocabulary to
# satisfy a downstream matcher. What the domain needs is the section's semantic
# ROLE, and this registry is the single place that knows the mapping.
#
# Before this existed, `broker_evidence` matched broker display strings inline,
# so any label the IBKR-derived list did not happen to contain fell through to
# `cash_movement_classification == "unknown"` — silently. That was not
# hypothetical: every Freedom24 trade ("Transactions") and every ESPP
# contribution and purchase ("Employee Stock Purchase Summary") was
# unclassified, which left the proof system reporting an ESPP payroll deposit
# as `not_observed` while the statement stated it plainly.
#
# A label may serve several roles — the same ESPP section produces both the
# payroll DEPOSIT and the BUY — so a role is resolved from (label, entry_type),
# exactly as the pre-existing IBKR aliases already required.
#
# `test_ledger_domain.py` asserts that every `source_section` any importer
# emits resolves here, so the next broker fails the suite instead of degrading
# output in production.
LedgerSectionRole = Literal["trade", "external_transfer", "dividend", "interest", "fee", "tax"]

_SECTION_ROLES: dict[str, frozenset[LedgerSectionRole]] = {
    # Interactive Brokers (PDF + CSV) — the original inline vocabulary.
    "Trades": frozenset({"trade"}),
    "Deposits & Withdrawals": frozenset({"external_transfer"}),
    "Dividends": frozenset({"dividend"}),
    "Interest": frozenset({"interest"}),
    "Fees": frozenset({"fee"}),
    "Other Fees": frozenset({"fee"}),
    "Commissions": frozenset({"fee"}),
    "Withholding Tax": frozenset({"tax"}),
    "Account Summary": frozenset({"tax"}),
    "Income Summary": frozenset({"dividend"}),
    "Cash deposits/ withdrawals": frozenset({"dividend", "tax"}),
    # Freedom24 (US-24.5 F-1): its trade section is called "Transactions".
    "Transactions": frozenset({"trade"}),
    # ESPP (US-24.5 F-2): one section carries the payroll contribution AND the
    # resulting purchase, so it holds both roles.
    "Employee Stock Purchase Summary": frozenset({"trade", "external_transfer"}),
}

# Which role each entry type needs its section to carry for broker evidence.
_ENTRY_TYPE_REQUIRED_ROLE: dict[str, LedgerSectionRole] = {
    "BUY": "trade",
    "SELL": "trade",
    "DEPOSIT": "external_transfer",
    "WITHDRAWAL": "external_transfer",
    "DIVIDEND": "dividend",
    "INTEREST": "interest",
    "FEE": "fee",
    "WITHHOLDING_TAX": "tax",
}

_ROLE_EVIDENCE: dict[LedgerSectionRole, str] = {
    "trade": "broker_trade_ledger_line",
    "external_transfer": "broker_transfer_section_line",
    "dividend": "broker_dividend_section_line",
    "interest": "broker_interest_section_line",
    "fee": "broker_fee_section_line",
    "tax": "broker_tax_section_line",
}


def section_roles(source_section: str) -> frozenset[LedgerSectionRole]:
    """Semantic roles a broker section label carries, empty if unregistered.

    An empty result is the honest "we do not recognise this section" answer and
    leaves the entry `unknown` (US-24.5 AC6) — it must stay reachable, because
    defaulting an unrecognised label to a role would fabricate provenance.
    """
    return _SECTION_ROLES.get(source_section, frozenset())


def registered_section_labels() -> frozenset[str]:
    """Every section label the domain recognises (US-24.5 AC7 coverage guard)."""
    return frozenset(_SECTION_ROLES)


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
    cash_movement_classification: CashMovementClassification = "unknown"
    broker_evidence: list[str] = Field(default_factory=list)
    opening_state_source: OpeningStateSource | None = None


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

    def broker_evidence(entry_type: LedgerEntryType, source_section: str, source_line: str | None) -> list[str]:
        evidence = [f"source_section:{source_section.lower().replace(' ', '_').replace('&', 'and')}"]
        if source_line:
            evidence.append("source_line_present")
        # US-24.5: resolved through the section-role registry rather than by
        # matching broker display strings here, so a broker whose vocabulary
        # differs (Freedom24's "Transactions", ESPP's "Employee Stock Purchase
        # Summary") is recognised instead of silently falling through.
        required_role = _ENTRY_TYPE_REQUIRED_ROLE.get(entry_type)
        if required_role is not None and required_role in section_roles(source_section):
            evidence.append(_ROLE_EVIDENCE[required_role])
        return evidence

    def cash_movement_classification(entry_type: LedgerEntryType, source_section: str, evidence: list[str]) -> CashMovementClassification:
        if entry_type in {"DEPOSIT", "WITHDRAWAL"} and "broker_transfer_section_line" in evidence:
            return "external_capital_flow"
        if entry_type in {"BUY", "SELL"} and "broker_trade_ledger_line" in evidence:
            return "internal_trading_flow"
        if entry_type == "DIVIDEND" and "broker_dividend_section_line" in evidence:
            return "broker_explicit_dividend"
        if entry_type == "INTEREST" and "broker_interest_section_line" in evidence:
            return "broker_explicit_interest"
        if entry_type == "FEE" and "broker_fee_section_line" in evidence:
            return "broker_explicit_fee"
        if entry_type == "WITHHOLDING_TAX" and "broker_tax_section_line" in evidence:
            return "broker_explicit_tax"
        return "unknown"

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

    records: list[LedgerRecord] = []
    for entry in snapshot.ledger_entries:
        evidence = broker_evidence(entry.entry_type, entry.source_section, entry.source_line)
        records.append(
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
                cash_movement_classification=cash_movement_classification(entry.entry_type, entry.source_section, evidence),
                broker_evidence=evidence,
            )
        )

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


def classify_opening_state(snapshot: ImportedPortfolioSnapshot) -> OpeningStateSource:
    ledger = snapshot_to_ledger(snapshot)
    if any(balance.starting_cash is not None for balance in snapshot.cash_balances):
        return "broker_proven"

    ending_positions = {position.symbol: position.quantity for position in snapshot.positions}
    buy_totals: dict[str, float] = {}
    sell_totals: dict[str, float] = {}
    for entry in ledger:
        if entry.entry_type == "BUY" and entry.symbol and entry.quantity:
            buy_totals[entry.symbol] = buy_totals.get(entry.symbol, 0.0) + entry.quantity
        elif entry.entry_type == "SELL" and entry.symbol and entry.quantity:
            sell_totals[entry.symbol] = sell_totals.get(entry.symbol, 0.0) + entry.quantity

    inferred_symbols: list[str] = []
    for symbol in sorted(set(ending_positions) | set(buy_totals) | set(sell_totals)):
        opening_quantity = ending_positions.get(symbol, 0.0) + sell_totals.get(symbol, 0.0) - buy_totals.get(symbol, 0.0)
        if abs(opening_quantity) > 1e-9:
            inferred_symbols.append(symbol)

    if inferred_symbols:
        return "unknown_inferred"
    return "trade_window_covered"
