from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from pypdf import PdfReader

from app.schemas.imports import (
    ImportedCashBalance,
    ImportedInstrument,
    ImportedLedgerEntry,
    ImportedPortfolioSnapshot,
    ImportedPosition,
    ImportedStatement,
    ImportedStatementTotals,
)


@dataclass
class EsppPreview:
    account_id: str | None
    period: str | None
    base_currency: str | None
    page_count: int


def _extract_text_by_page(path: str | Path) -> list[str]:
    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def _normalize_number(value: str) -> float:
    return float(value.replace("$", "").replace(",", "").replace("-", "0").strip())


def preview_pdf_statement(path: str | Path) -> EsppPreview:
    page_texts = _extract_text_by_page(path)
    full_text = "\n".join(page_texts)
    first_page = page_texts[0] if page_texts else ""

    if "YEAR-END INVESTMENT REPORT" not in full_text or "Participant Number:" not in full_text or "Stock Plan" not in full_text:
        raise ValueError("PDF does not look like an ESPP stock plan statement")

    period_match = re.search(r"([A-Za-z]+\s+\d{1,2},\s+\d{4}) - ([A-Za-z]+\s+\d{1,2},\s+\d{4})", first_page)
    participant_match = re.search(r"Participant Number:\s*(?P<participant>[A-Z0-9]+)", full_text)
    period = None
    if period_match:
        period = f"{period_match.group(1)} - {period_match.group(2)}"

    return EsppPreview(
        account_id=participant_match.group("participant") if participant_match else None,
        period=period,
        base_currency="USD",
        page_count=len(page_texts),
    )


def _parse_period_end_date(period: str | None) -> date:
    if period is None or " - " not in period:
        raise ValueError("Could not determine ESPP statement period")
    _, end_raw = period.split(" - ", 1)
    return datetime.strptime(end_raw, "%B %d, %Y").date()


def _parse_statement_totals(full_text: str) -> ImportedStatementTotals:
    totals = ImportedStatementTotals(fx_rates={"USDUSD": 1.0})

    beginning_match = re.search(r"Beg\. Stock Plan Account Value as of Jan 1, \d{4}\s+(?P<value>-|\$?[\d,]+\.\d+)", full_text)
    ending_match = re.search(r"Ending Stock Plan Account Value as of Dec 31, \d{4}.*?\$?(?P<value>[\d,]+\.\d+)", full_text)
    subtractions_match = re.search(r"Subtractions\s+(?P<value>-?[\d,]+\.\d+)", full_text)
    change_match = re.search(r"Change in Investment Value \*\s+(?P<value>-?[\d,]+\.\d+)", full_text)
    income_match = re.search(r"Income Summary.*?Total\s+\$?(?P<value>[\d,]+\.\d+)", full_text, re.DOTALL)
    cash_match = re.search(r"Total Core Account .*?\$?(?P<value>[\d,]+\.\d+)\s+\$?(?P<income>[\d,]+\.\d+)", full_text, re.DOTALL)
    stock_match = re.search(r"Total Stocks .*?\$?(?P<value>[\d,]+\.\d+)\s+\$?(?P<cost>[\d,]+\.\d+)\s+\$?(?P<gain>[\d,]+\.\d+)\s+\$?(?P<income>[\d,]+\.\d+)", full_text)
    purchase_match = re.search(r"Total for all Offering Periods\s+(?P<shares>[\d,]+\.\d+)\s+\$?(?P<gain>[\d,]+\.\d+)", full_text)
    stock_position_match = re.search(
        r"MICROSOFT CORP \(MSFT\)\s+(?P<quantity>[\d,]+\.\d+)\s+\$?(?P<price>[\d,]+\.\d+)\s+\$?(?P<market>[\d,]+\.\d+)\s+\$?(?P<cost>[\d,]+\.\d+)\s+\$?(?P<gain>[\d,]+\.\d+)\s+\$?(?P<income>[\d,]+\.\d+)",
        full_text,
    )

    totals.starting_nav = None if beginning_match and beginning_match.group("value") == "-" else (_normalize_number(beginning_match.group("value")) if beginning_match else None)
    totals.ending_nav = _normalize_number(ending_match.group("value")) if ending_match else None
    totals.cash_total = _normalize_number(cash_match.group("value")) if cash_match else None
    totals.stock_total = _normalize_number(stock_match.group("value")) if stock_match else (_normalize_number(stock_position_match.group("market")) if stock_position_match else None)
    totals.other_fees_total = abs(_normalize_number(subtractions_match.group("value"))) if subtractions_match else None
    totals.withholding_tax_total = abs(_normalize_number(subtractions_match.group("value"))) if subtractions_match else None
    totals.dividends_total = _normalize_number(income_match.group("value")) if income_match else None
    totals.time_weighted_return_pct = None
    if purchase_match and stock_position_match:
        implied_purchase_cost = round(_normalize_number(stock_position_match.group("cost")), 2)
        totals.deposits_total = implied_purchase_cost
    elif totals.starting_nav == 0 and totals.ending_nav is not None:
        totals.deposits_total = totals.ending_nav - (change_match and _normalize_number(change_match.group("value")) or 0.0) + (subtractions_match and abs(_normalize_number(subtractions_match.group("value"))) or 0.0)
    return totals


def _parse_core_cash_value(full_text: str) -> float | None:
    match = re.search(
        r"FID TREASURY ONLY MMKT FUND CL\s+OUS\s+\(FYIXX\).*?(?P<quantity>[\d,]+\.\d+)\s+\$?(?P<price>[\d,]+\.\d+)\s+\$?(?P<market>[\d,]+\.\d+)",
        full_text,
        re.DOTALL,
    )
    if not match:
        return None
    return _normalize_number(match.group("market"))


def _parse_stock_position(full_text: str, as_of_date: date) -> ImportedPosition:
    match = re.search(
        r"MICROSOFT CORP \(MSFT\)\s+(?P<quantity>[\d,]+\.\d+)\s+\$?(?P<price>[\d,]+\.\d+)\s+\$?(?P<market>[\d,]+\.\d+)\s+\$?(?P<cost>[\d,]+\.\d+)\s+\$?(?P<gain>[\d,]+\.\d+)\s+\$?(?P<income>[\d,]+\.\d+)",
        full_text,
    )
    if not match:
        raise ValueError("Could not parse ESPP stock holdings section")
    quantity = _normalize_number(match.group("quantity"))
    price = _normalize_number(match.group("price"))
    market_value = _normalize_number(match.group("market"))
    cost_basis = _normalize_number(match.group("cost"))
    gain = _normalize_number(match.group("gain"))
    return ImportedPosition(
        as_of_date=as_of_date,
        symbol="MSFT",
        quantity=quantity,
        cost_basis=cost_basis,
        close_price=price,
        market_value=market_value,
        unrealized_pnl=gain,
        currency="USD",
    )


def _parse_cash_balances(core_cash_value: float | None) -> list[ImportedCashBalance]:
    if core_cash_value is None:
        return []
    return [ImportedCashBalance(currency="USD", ending_cash=core_cash_value, ending_settled_cash=core_cash_value)]


def _parse_purchase_ledger(full_text: str) -> list[ImportedLedgerEntry]:
    match = re.search(
        r"(\d{2}/\d{2}/\d{4})-(\d{2}/\d{2}/\d{4})\s+Employee Purchase\s+(\d{2}/\d{2}/\d{4})\s+\$?(?P<purchase_price>[\d,]+\.\d+)\s+\$?(?P<fmv>[\d,]+\.\d+)\s+(?P<shares>[\d,]+\.\d+)\s+\$?(?P<gain>[\d,]+\.\d+)",
        full_text,
    )
    if not match:
        return []
    purchase_date = datetime.strptime(match.group(3), "%m/%d/%Y").date()
    purchase_price = _normalize_number(match.group("purchase_price"))
    shares = _normalize_number(match.group("shares"))
    gross_amount = round(-(purchase_price * shares), 2)
    return [
        ImportedLedgerEntry(
            entry_type="DEPOSIT",
            trade_date=purchase_date,
            description="ESPP payroll contribution funding purchase",
            gross_amount=abs(gross_amount),
            net_amount=abs(gross_amount),
            currency="USD",
            source_section="Employee Stock Purchase Summary",
        ),
        ImportedLedgerEntry(
            entry_type="BUY",
            trade_date=purchase_date,
            symbol="MSFT",
            description="ESPP employee purchase",
            quantity=shares,
            price=purchase_price,
            gross_amount=gross_amount,
            net_amount=gross_amount,
            currency="USD",
            source_section="Employee Stock Purchase Summary",
        )
    ]


def _parse_tax_ledger(full_text: str, as_of_date: date) -> list[ImportedLedgerEntry]:
    match = re.search(r"Taxes Withheld\s+(?P<value>-?[\d,]+\.\d+)", full_text)
    if not match:
        return []
    amount = _normalize_number(match.group("value"))
    return [
        ImportedLedgerEntry(
            entry_type="WITHHOLDING_TAX",
            trade_date=as_of_date,
            description="ESPP taxes withheld",
            gross_amount=-abs(amount),
            net_amount=-abs(amount),
            tax=abs(amount),
            currency="USD",
            source_section="Account Summary",
        )
    ]


def _parse_income_ledger(full_text: str, as_of_date: date) -> list[ImportedLedgerEntry]:
    match = re.search(r"Dividends\s+(?P<value>[\d,]+\.\d+)", full_text)
    if not match:
        return []
    amount = _normalize_number(match.group("value"))
    return [
        ImportedLedgerEntry(
            entry_type="DIVIDEND",
            trade_date=as_of_date,
            symbol="MSFT",
            description="ESPP dividend income summary",
            gross_amount=amount,
            net_amount=amount,
            currency="USD",
            source_section="Income Summary",
        )
    ]


def _parse_instruments() -> list[ImportedInstrument]:
    return [
        ImportedInstrument(symbol="MSFT", description="MICROSOFT CORP", listing_exchange="NASDAQ", instrument_type="COMMON", currency="USD"),
    ]


def import_statement(path: str | Path) -> ImportedPortfolioSnapshot:
    preview = preview_pdf_statement(path)
    page_texts = _extract_text_by_page(path)
    full_text = "\n".join(page_texts)
    as_of_date = _parse_period_end_date(preview.period)

    stock_position = _parse_stock_position(full_text, as_of_date)
    core_cash_value = _parse_core_cash_value(full_text)
    positions = [stock_position]

    ledger_entries = [
        *_parse_purchase_ledger(full_text),
        *_parse_tax_ledger(full_text, as_of_date),
        *_parse_income_ledger(full_text, as_of_date),
    ]
    statement = ImportedStatement(
        importer="espp",
        imported_at=datetime.now(UTC),
        source_path=str(path),
        detected_format="pdf",
        account_id=preview.account_id,
        base_currency=preview.base_currency,
        statement_period=preview.period,
        page_count=preview.page_count,
    )

    return ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=_parse_statement_totals(full_text),
        instruments=_parse_instruments(),
        cash_balances=_parse_cash_balances(core_cash_value),
        positions=positions,
        ledger_entries=ledger_entries,
    )
