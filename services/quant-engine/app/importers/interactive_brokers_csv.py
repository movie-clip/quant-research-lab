"""IBKR Activity-Statement CSV importer (US-28.1).

Parses the machine-readable CSV export of the same Activity Statement the PDF
importer reconstructs from layout. Every row is
``<Section>,<RowType>,<cells...>`` with per-section column headers; a section
may restate its Header mid-file with a different column subset (seen in
``Trades``), so the reader tracks the *current* header per section.

Fail-safe per record (US-24.4/24.8 discipline): a malformed record is skipped
and parsing continues — partial snapshot, never a crash, never a fabricated
zero; the totals gap surfaces through statement reconciliation.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from app.schemas.imports import (
    ImportedCashBalance,
    ImportedInstrument,
    ImportedLedgerEntry,
    ImportedPortfolioSnapshot,
    ImportedPosition,
    ImportedStatement,
    ImportedStatementTotals,
    LedgerEntryType,
)


# ── IBKR Activity-Statement CSV format constants (US-24.4 convention) ─────────
_ENCODING = "utf-8-sig"          # the export carries a UTF-8 BOM
_ROW_HEADER = "Header"           # column-definition row for the section
_ROW_DATA = "Data"               # record row
_ROW_TOTAL = "Total"             # section/currency-group total row
_MISSING_CELL = "--"             # IBKR's "no value" sentinel in numeric cells
_TOTAL_MARKER = "Total"          # pseudo-value marking a summary row inside Data rows
_BASE_SUMMARY_MARKER = "Base Currency Summary"  # Cash Report pseudo-currency
_SUMMARY_DISCRIMINATOR = "Summary"  # Open Positions per-currency position rows
_ORDER_DISCRIMINATOR = "Order"      # Trades executed-order rows
_STOCKS_CATEGORY = "Stocks"
_PERIOD_DATE_FORMAT = "%B %d, %Y"   # "January 1, 2026"
_EXPECTED_TITLE = "Activity Statement"
_EXPECTED_BROKER = "Interactive Brokers"

_SECTION_STATEMENT = "Statement"
_SECTION_ACCOUNT = "Account Information"
_SECTION_NAV = "Net Asset Value"
_SECTION_CHANGE_IN_NAV = "Change in NAV"
_SECTION_OPEN_POSITIONS = "Open Positions"
_SECTION_TRADES = "Trades"
_SECTION_DEPOSITS = "Deposits & Withdrawals"
_SECTION_DIVIDENDS = "Dividends"
_SECTION_WITHHOLDING = "Withholding Tax"
_SECTION_FEES = "Fees"
_SECTION_INTEREST = "Interest"
_SECTION_CASH_REPORT = "Cash Report"
_SECTION_INSTRUMENTS = "Financial Instrument Information"

# `Change in NAV` field name → ImportedStatementTotals attribute. Totals are
# stored as absolute values — the established schema convention shared with the
# PDF path and assumed by build_reconciliation_summary; signs live on the
# ledger entries.
_CHANGE_IN_NAV_FIELDS: dict[str, str] = {
    "Starting Value": "starting_nav",
    "Ending Value": "ending_nav",
    "Dividends": "dividends_total",
    "Withholding Tax": "withholding_tax_total",
    "Interest": "interest_total",
    "Other Fees": "other_fees_total",
    "Commissions": "commissions_total",
    "Deposits & Withdrawals": "deposits_total",
}

_NAV_ASSET_CLASS_CASH = "Cash"
_NAV_ASSET_CLASS_STOCK = "Stock"
_NAV_TWR_COLUMN = "Time Weighted Rate of Return"

# Cash Report "Currency Summary" field → ImportedCashBalance attribute.
_CASH_REPORT_FIELDS: dict[str, str] = {
    "Starting Cash": "starting_cash",
    "Ending Cash": "ending_cash",
    "Ending Settled Cash": "ending_settled_cash",
}

_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")
_SYMBOL_FROM_DESCRIPTION_RE = re.compile(r"^(?P<symbol>[^()]+)\(")


@dataclass
class SectionRecord:
    section: str
    row_type: str
    record: dict[str, str]
    cells: list[str]


@dataclass
class IbkrCsvPreview:
    account_id: str | None
    period: str | None
    base_currency: str | None
    section_count: int


def _read_records(path: str | Path) -> list[SectionRecord]:
    """Read every non-Header row as a column-name → cell mapping.

    Header rows update the current column set for their section, so a
    mid-file Header restatement (seen in ``Trades``) remaps the rows that
    follow it. Rows shorter than their header simply omit those keys; extra
    cells are dropped — both degrade to skipped records downstream.
    """
    records: list[SectionRecord] = []
    section_columns: dict[str, list[str]] = {}
    with open(path, encoding=_ENCODING, newline="") as handle:
        for cells in csv.reader(handle):
            if len(cells) < 2:
                continue
            section, row_type, rest = cells[0], cells[1], cells[2:]
            if row_type == _ROW_HEADER:
                section_columns[section] = rest
                continue
            columns = section_columns.get(section, [])
            records.append(
                SectionRecord(
                    section=section,
                    row_type=row_type,
                    record=dict(zip(columns, rest)),
                    cells=rest,
                )
            )
    return records


def _section_data(records: list[SectionRecord], section: str) -> list[SectionRecord]:
    return [r for r in records if r.section == section and r.row_type == _ROW_DATA]


def _parse_number(value: str | None) -> float:
    if value is None:
        raise ValueError("missing numeric cell")
    cleaned = value.replace(",", "").strip()
    if not cleaned or cleaned == _MISSING_CELL:
        raise ValueError(f"empty numeric cell: {value!r}")
    return float(cleaned)


def _is_currency(value: str | None) -> bool:
    return bool(value) and bool(_CURRENCY_RE.fullmatch(value))


def _normalize_period(raw: str | None) -> str | None:
    """"January 1, 2026 - June 30, 2026" → "2026-01-01 - 2026-06-30"."""
    if not raw or " - " not in raw:
        return None
    start_raw, end_raw = raw.split(" - ", 1)
    try:
        start = datetime.strptime(start_raw.strip(), _PERIOD_DATE_FORMAT).date()
        end = datetime.strptime(end_raw.strip(), _PERIOD_DATE_FORMAT).date()
    except ValueError:
        return None
    return f"{start.isoformat()} - {end.isoformat()}"


def _field_map(records: list[SectionRecord], section: str) -> dict[str, str]:
    """Field Name → Field Value mapping for key/value sections."""
    mapping: dict[str, str] = {}
    for row in _section_data(records, section):
        name = row.record.get("Field Name")
        value = row.record.get("Field Value")
        if name:
            mapping[name] = value or ""
    return mapping


def preview_csv_statement(path: str | Path) -> IbkrCsvPreview:
    records = _read_records(path)
    statement_fields = _field_map(records, _SECTION_STATEMENT)
    account_fields = _field_map(records, _SECTION_ACCOUNT)

    broker_name = statement_fields.get("BrokerName", "")
    title = statement_fields.get("Title", "")
    if _EXPECTED_BROKER not in broker_name or title != _EXPECTED_TITLE:
        raise ValueError("CSV does not look like an Interactive Brokers activity statement")

    return IbkrCsvPreview(
        account_id=account_fields.get("Account"),
        period=_normalize_period(statement_fields.get("Period")),
        base_currency=account_fields.get("Base Currency"),
        section_count=len({record.section for record in records}),
    )


def _parse_statement_totals(records: list[SectionRecord], base_currency: str) -> ImportedStatementTotals:
    totals = ImportedStatementTotals()

    change_in_nav = _field_map(records, _SECTION_CHANGE_IN_NAV)
    for field_name, attribute in _CHANGE_IN_NAV_FIELDS.items():
        raw = change_in_nav.get(field_name)
        try:
            setattr(totals, attribute, abs(_parse_number(raw)))
        except ValueError:
            # Field absent or malformed: leave it None rather than fabricate;
            # the gap surfaces through reconciliation.
            continue

    for row in _section_data(records, _SECTION_NAV):
        twr_raw = row.record.get(_NAV_TWR_COLUMN)
        if twr_raw is not None:
            try:
                totals.time_weighted_return_pct = _parse_number(twr_raw.removesuffix("%"))
            except ValueError:
                pass
            continue
        asset_class = (row.record.get("Asset Class") or "").strip()
        try:
            current_total = _parse_number(row.record.get("Current Total"))
        except ValueError:
            continue
        if asset_class == _NAV_ASSET_CLASS_CASH:
            totals.cash_total = current_total
        elif asset_class == _NAV_ASSET_CLASS_STOCK:
            totals.stock_total = current_total

    totals.fx_rates = _implied_fx_rates(records, base_currency)
    return totals


def _implied_fx_rates(records: list[SectionRecord], base_currency: str) -> dict[str, float]:
    """FX rates implied by the statement's own Open Positions totals.

    Each non-base currency group closes with two Total rows — the group total
    in its own currency, then the same total restated in the base currency —
    so ``base_value / local_value`` is the statement's own conversion rate
    (broker truth, not an external lookup). Missing/malformed pairs simply
    yield no rate; the unconverted gap then surfaces through reconciliation.
    """
    rates: dict[str, float] = {f"{base_currency}{base_currency}": 1.0}
    total_rows = [
        row
        for row in records
        if row.section == _SECTION_OPEN_POSITIONS and row.row_type == _ROW_TOTAL
    ]
    for row, next_row in zip(total_rows, total_rows[1:]):
        currency = row.record.get("Currency")
        next_currency = next_row.record.get("Currency")
        if currency == base_currency or not _is_currency(currency) or next_currency != base_currency:
            continue
        try:
            local_value = _parse_number(row.record.get("Value"))
            base_value = _parse_number(next_row.record.get("Value"))
        except ValueError:
            continue
        if local_value:
            rates[f"{currency}{base_currency}"] = base_value / local_value
    return rates


def _parse_positions(records: list[SectionRecord], as_of_date: date) -> list[ImportedPosition]:
    positions: list[ImportedPosition] = []
    for row in _section_data(records, _SECTION_OPEN_POSITIONS):
        fields = row.record
        if fields.get("DataDiscriminator") != _SUMMARY_DISCRIMINATOR:
            continue
        if fields.get("Asset Category") != _STOCKS_CATEGORY:
            continue
        currency = fields.get("Currency")
        symbol = (fields.get("Symbol") or "").strip()
        if not _is_currency(currency) or not symbol:
            continue
        try:
            positions.append(
                ImportedPosition(
                    as_of_date=as_of_date,
                    symbol=symbol,
                    quantity=_parse_number(fields.get("Quantity")),
                    cost_basis=_parse_number(fields.get("Cost Basis")),
                    close_price=_parse_number(fields.get("Close Price")),
                    market_value=_parse_number(fields.get("Value")),
                    unrealized_pnl=_parse_number(fields.get("Unrealized P/L")),
                    currency=currency,
                )
            )
        except ValueError:
            # Malformed record: skip it, keep the rest of the section.
            continue
    return positions


def _parse_trade_date(raw: str | None) -> date:
    if raw is None:
        raise ValueError("missing Date/Time cell")
    return date.fromisoformat(raw.split(",", 1)[0].strip())


def _parse_trades(records: list[SectionRecord]) -> list[ImportedLedgerEntry]:
    entries: list[ImportedLedgerEntry] = []
    for row in _section_data(records, _SECTION_TRADES):
        fields = row.record
        if fields.get("DataDiscriminator") != _ORDER_DISCRIMINATOR:
            continue
        if fields.get("Asset Category") != _STOCKS_CATEGORY:
            continue
        currency = fields.get("Currency")
        symbol = (fields.get("Symbol") or "").strip()
        if not _is_currency(currency) or not symbol:
            continue
        try:
            quantity = _parse_number(fields.get("Quantity"))
            gross_amount = _parse_number(fields.get("Proceeds"))
            fee = abs(_parse_number(fields.get("Comm/Fee")))
            trade_date = _parse_trade_date(fields.get("Date/Time"))
            price = _parse_number(fields.get("T. Price"))
        except ValueError:
            continue
        time_part = (fields.get("Date/Time") or "").split(",", 1)[-1].strip()
        entries.append(
            ImportedLedgerEntry(
                entry_type="BUY" if quantity > 0 else "SELL",
                trade_date=trade_date,
                symbol=symbol,
                description=f"IB trade {time_part}",
                quantity=abs(quantity),
                price=price,
                gross_amount=gross_amount,
                net_amount=gross_amount - fee,
                fee=fee,
                currency=currency,
                source_section=_SECTION_TRADES,
                source_line=",".join(row.cells),
            )
        )
    return entries


def _parse_cash_flow_section(
    records: list[SectionRecord], section: str, entry_type: LedgerEntryType
) -> list[ImportedLedgerEntry]:
    """Dividends / Withholding Tax / Fees / Interest: Currency,Date,Description,Amount
    rows (Fees adds a leading Subtitle column). Section-total rows carry the
    Total marker (or a blank) where a real currency belongs, so the currency
    check screens them out."""
    entries: list[ImportedLedgerEntry] = []
    for row in _section_data(records, section):
        fields = row.record
        currency = fields.get("Currency")
        if not _is_currency(currency):
            continue
        description = fields.get("Description") or ""
        try:
            amount = _parse_number(fields.get("Amount"))
            trade_date = date.fromisoformat((fields.get("Date") or "").strip())
        except ValueError:
            continue
        symbol_match = _SYMBOL_FROM_DESCRIPTION_RE.match(description)
        entries.append(
            ImportedLedgerEntry(
                entry_type=entry_type,
                trade_date=trade_date,
                symbol=symbol_match.group("symbol").strip() if symbol_match else None,
                description=description,
                gross_amount=amount,
                net_amount=amount,
                fee=abs(amount) if entry_type == "FEE" else 0,
                tax=abs(amount) if entry_type == "WITHHOLDING_TAX" else 0,
                currency=currency,
                source_section=section,
                source_line=",".join(row.cells),
            )
        )
    return entries


def _parse_deposits_and_withdrawals(records: list[SectionRecord]) -> list[ImportedLedgerEntry]:
    entries: list[ImportedLedgerEntry] = []
    for row in _section_data(records, _SECTION_DEPOSITS):
        fields = row.record
        currency = fields.get("Currency")
        if not _is_currency(currency):
            # Currency-summary rows carry the Total marker here; skip them.
            continue
        try:
            amount = _parse_number(fields.get("Amount"))
            trade_date = date.fromisoformat((fields.get("Settle Date") or "").strip())
        except ValueError:
            continue
        entries.append(
            ImportedLedgerEntry(
                entry_type="DEPOSIT" if amount >= 0 else "WITHDRAWAL",
                trade_date=trade_date,
                description=fields.get("Description") or "",
                gross_amount=amount,
                net_amount=amount,
                currency=currency,
                source_section=_SECTION_DEPOSITS,
                source_line=",".join(row.cells),
            )
        )
    return entries


def _parse_cash_balances(records: list[SectionRecord]) -> list[ImportedCashBalance]:
    balances: dict[str, ImportedCashBalance] = {}
    for row in _section_data(records, _SECTION_CASH_REPORT):
        fields = row.record
        currency = fields.get("Currency")
        if not _is_currency(currency):
            # The Base Currency Summary pseudo-currency restates the base
            # currency's rows; keeping only real currencies avoids double
            # counting the base.
            continue
        attribute = _CASH_REPORT_FIELDS.get(fields.get("Currency Summary") or "")
        if attribute is None:
            continue
        try:
            amount = _parse_number(fields.get("Total"))
        except ValueError:
            continue
        balance = balances.setdefault(currency, ImportedCashBalance(currency=currency))
        setattr(balance, attribute, amount)
    return list(balances.values())


def _parse_instruments(records: list[SectionRecord]) -> list[ImportedInstrument]:
    instruments: list[ImportedInstrument] = []
    for row in _section_data(records, _SECTION_INSTRUMENTS):
        fields = row.record
        symbol = (fields.get("Symbol") or "").strip()
        if not symbol:
            continue
        instruments.append(
            ImportedInstrument(
                symbol=symbol,
                description=(fields.get("Description") or "").strip() or None,
                isin=(fields.get("Security ID") or "").strip() or None,
                listing_exchange=(fields.get("Listing Exch") or "").strip() or None,
                instrument_type=(fields.get("Type") or "").strip() or None,
            )
        )
    return instruments


def import_statement(path: str | Path) -> ImportedPortfolioSnapshot:
    preview = preview_csv_statement(path)
    records = _read_records(path)

    if preview.period is None:
        raise ValueError("Could not determine Interactive Brokers statement period")

    _, end_date_str = preview.period.split(" - ")
    as_of_date = date.fromisoformat(end_date_str)
    base_currency = preview.base_currency or "USD"

    ledger_entries = [
        *_parse_trades(records),
        *_parse_cash_flow_section(records, _SECTION_DIVIDENDS, "DIVIDEND"),
        *_parse_cash_flow_section(records, _SECTION_WITHHOLDING, "WITHHOLDING_TAX"),
        *_parse_cash_flow_section(records, _SECTION_INTEREST, "INTEREST"),
        *_parse_cash_flow_section(records, _SECTION_FEES, "FEE"),
        *_parse_deposits_and_withdrawals(records),
    ]

    statement = ImportedStatement(
        importer="interactive_brokers",
        imported_at=datetime.now(UTC),
        source_path=str(path),
        detected_format="csv",
        account_id=preview.account_id,
        base_currency=preview.base_currency,
        statement_period=preview.period,
        page_count=None,
    )

    return ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=_parse_statement_totals(records, base_currency),
        instruments=_parse_instruments(records),
        cash_balances=_parse_cash_balances(records),
        positions=_parse_positions(records, as_of_date),
        ledger_entries=ledger_entries,
    )
