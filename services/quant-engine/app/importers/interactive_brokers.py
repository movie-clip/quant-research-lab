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
    LedgerEntryType,
)


@dataclass
class StatementSectionPresence:
    trades: bool = False
    open_positions: bool = False
    dividends: bool = False
    withholding_tax: bool = False
    deposits_withdrawals: bool = False
    cash_report: bool = False
    financial_instrument_info: bool = False


@dataclass
class StatementPreview:
    account_id: str | None
    period: str | None
    base_currency: str | None
    page_count: int
    sections: StatementSectionPresence


_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _parse_period_end_date(period: str | None) -> date | None:
    if not period:
        return None

    match = re.search(r"-\s*([A-Za-z]+\s+\d{1,2},\s+\d{4})$", period)
    if match:
        return datetime.strptime(match.group(1), "%B %d, %Y").date()

    return None


def detect_statement_format(path: str | Path) -> str:
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix in {".csv", ".txt"}:
        return "delimited"
    if suffix == ".xml":
        return "xml"
    return "unknown"


def _extract_text_by_page(path: str | Path) -> list[str]:
    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def preview_pdf_statement(path: str | Path) -> StatementPreview:
    page_texts = _extract_text_by_page(path)
    first_page_text = page_texts[0] if page_texts else ""
    full_text = "\n".join(page_texts)

    if "Activity Statement" not in full_text or "Open Positions" not in full_text:
        raise ValueError("PDF does not look like an Interactive Brokers activity statement")

    account_id = None
    period = None
    base_currency = None

    for line in first_page_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Account ") and stripped not in {"Account Information", "Account Type Individual", "Account Capabilities Cash"}:
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2 and parts[1].startswith("U"):
                account_id = parts[1]
        elif stripped.startswith("Base Currency"):
            base_currency = stripped.split()[-1]
        elif stripped.startswith("January "):
            period = stripped

    sections = StatementSectionPresence(
        trades="Trades" in full_text,
        open_positions="Open Positions" in full_text,
        dividends="Dividends" in full_text,
        withholding_tax="Withholding Tax" in full_text,
        deposits_withdrawals="Deposits & Withdrawals" in full_text,
        cash_report="Cash Report" in full_text,
        financial_instrument_info="Financial Instrument Information" in full_text,
    )

    return StatementPreview(
        account_id=account_id,
        period=period,
        base_currency=base_currency,
        page_count=len(page_texts),
        sections=sections,
    )


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_number(value: str) -> float:
    return float(value.replace(",", ""))


def _is_currency_heading(value: str) -> bool:
    return bool(_CURRENCY_RE.fullmatch(value))


def _parse_statement_totals(page_texts: list[str]) -> ImportedStatementTotals:
    first_page = page_texts[0] if page_texts else ""
    full_text = "\n".join(page_texts)
    totals = ImportedStatementTotals()

    line_patterns: dict[str, str] = {
        "cash_total": r"^Cash [\d,.-]+ (?P<value>[\d,.-]+) 0\.00 [\d,.-]+",
        "stock_total": r"^Stock [\d,.-]+ (?P<value>[\d,.-]+) 0\.00 [\d,.-]+",
        "starting_nav": r"^Starting Value (?P<value>[\d,.-]+)$",
        "ending_nav": r"^Ending Value (?P<value>[\d,.-]+)$",
        "dividends_total": r"^Dividends (?P<value>[\d,.-]+)$",
        "withholding_tax_total": r"^Withholding Tax (?P<value>-?[\d,.-]+)$",
        "interest_total": r"^Interest (?P<value>[\d,.-]+)$",
        "other_fees_total": r"^Other Fees (?P<value>-?[\d,.-]+)$",
        "commissions_total": r"^Commissions (?P<value>-?[\d,.-]+)$",
        "deposits_total": r"^Deposits & Withdrawals (?P<value>[\d,.-]+)$",
    }

    for raw_line in first_page.splitlines():
        line = raw_line.strip()
        if line.startswith("Time Weighted Rate of Return"):
            pct = line.removeprefix("Time Weighted Rate of Return").strip().removesuffix("%")
            if pct:
                totals.time_weighted_return_pct = float(pct)
        for field, pattern in line_patterns.items():
            match = re.match(pattern, line)
            if match:
                setattr(totals, field, abs(_parse_number(match.group("value"))))

    usd_fx = 1.0
    eur_match = re.search(r"EUR 0\.00 0\.00 1\.0353 (?P<rate>[\d.]+)", full_text)
    if eur_match:
        totals.fx_rates["EURUSD"] = float(eur_match.group("rate"))
    totals.fx_rates["USDUSD"] = usd_fx

    return totals


def _collect_section_lines(page_texts: list[str], heading: str) -> list[str]:
    lines: list[str] = []
    capturing = False
    stop_prefixes = {
        "Trades",
        "Open Positions",
        "Dividends",
        "Withholding Tax",
        "Fees",
        "Interest",
        "Deposits & Withdrawals",
        "Change in Dividend Accruals",
        "Financial Instrument Information",
        "Codes",
        "Notes/Legal Notes",
        "Cash Report",
        "Realized & Unrealized Performance Summary",
        "Mark-to-Market Performance Summary",
    }

    for page_text in page_texts:
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == heading:
                capturing = True
                lines.append(line)
                continue
            if capturing and any(line.startswith(prefix) and line != heading for prefix in stop_prefixes):
                capturing = False
            if capturing:
                lines.append(line)

    return lines


def _parse_open_positions(page_texts: list[str], as_of_date: date) -> list[ImportedPosition]:
    lines = _collect_section_lines(page_texts, "Open Positions")
    positions: list[ImportedPosition] = []
    current_currency: str | None = None

    pattern = re.compile(
        r"^(?P<symbol>[A-Z0-9. ]+)\s+(?P<quantity>-?\d+(?:\.\d+)?)\s+(?P<multiplier>\d+)\s+"
        r"(?P<cost_price>-?[\d,]+(?:\.\d+)?)\s+(?P<cost_basis>-?[\d,]+(?:\.\d+)?)\s+"
        r"(?P<close_price>-?[\d,]+(?:\.\d+)?)\s+(?P<value>-?[\d,]+(?:\.\d+)?)\s+"
        r"(?P<unrealized>-?[\d,]+(?:\.\d+)?)$"
    )

    for line in lines:
        if _is_currency_heading(line):
            current_currency = line
            continue
        match = pattern.match(line)
        if not match or current_currency is None:
            continue

        positions.append(
            ImportedPosition(
                as_of_date=as_of_date,
                symbol=match.group("symbol").strip(),
                quantity=_parse_number(match.group("quantity")),
                cost_basis=_parse_number(match.group("cost_basis")),
                close_price=_parse_number(match.group("close_price")),
                market_value=_parse_number(match.group("value")),
                unrealized_pnl=_parse_number(match.group("unrealized")),
                currency=current_currency,
            )
        )

    return positions


def _normalize_trade_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\n", " ")).strip()


def _parse_trades(page_texts: list[str]) -> list[ImportedLedgerEntry]:
    lines = _collect_section_lines(page_texts, "Trades")
    entries: list[ImportedLedgerEntry] = []
    current_currency: str | None = None
    pending_trade: str | None = None

    pattern = re.compile(
        r"^(?P<symbol>.+?) (?P<trade_date>\d{4}-\d{2}-\d{2}), (?P<time>\d{2}:\d{2}:\d{2}) "
        r"(?P<quantity>-?\d+(?:\.\d+)?) (?P<trade_price>-?[\d,]+(?:\.\d+)?) (?P<close_price>-?[\d,]+(?:\.\d+)?) "
        r"(?P<proceeds>-?[\d,]+(?:\.\d+)?) (?P<fee>-?[\d,]+(?:\.\d+)?) (?P<basis>-?[\d,]+(?:\.\d+)?) "
        r"(?P<realized>-?[\d,]+(?:\.\d+)?) (?P<mtm>-?[\d,]+(?:\.\d+)?) (?P<code>.+)$"
    )

    for raw_line in lines:
        line = raw_line.strip()
        if _is_currency_heading(line):
            current_currency = line
            continue
        if not line or line.startswith("Symbol Date/Time") or line in {"Stocks", "Trades"}:
            continue
        if line.startswith("Total") or line.startswith("Activity Statement"):
            continue

        if pending_trade is not None:
            combined = _normalize_trade_line(f"{pending_trade} {line}")
            match = pattern.match(combined)
            pending_trade = None
            if match and current_currency:
                quantity = _parse_number(match.group("quantity"))
                gross_amount = _parse_number(match.group("proceeds"))
                fee = abs(_parse_number(match.group("fee")))
                entries.append(
                    ImportedLedgerEntry(
                        entry_type="BUY" if quantity > 0 else "SELL",
                        trade_date=_parse_date(match.group("trade_date")),
                        symbol=match.group("symbol").strip(),
                        description=f"IB trade {match.group('time')}",
                        quantity=abs(quantity),
                        price=_parse_number(match.group("trade_price")),
                        gross_amount=gross_amount,
                        net_amount=gross_amount - fee if gross_amount > 0 else gross_amount - fee,
                        fee=fee,
                        currency=current_currency,
                        source_section="Trades",
                        source_line=combined,
                    )
                )
            continue

        if _DATE_RE.search(line) and not pattern.match(_normalize_trade_line(line)):
            pending_trade = line
            continue

        match = pattern.match(_normalize_trade_line(line))
        if match and current_currency:
            quantity = _parse_number(match.group("quantity"))
            gross_amount = _parse_number(match.group("proceeds"))
            fee = abs(_parse_number(match.group("fee")))
            entries.append(
                ImportedLedgerEntry(
                    entry_type="BUY" if quantity > 0 else "SELL",
                    trade_date=_parse_date(match.group("trade_date")),
                    symbol=match.group("symbol").strip(),
                    description=f"IB trade {match.group('time')}",
                    quantity=abs(quantity),
                    price=_parse_number(match.group("trade_price")),
                    gross_amount=gross_amount,
                    net_amount=gross_amount - fee if gross_amount > 0 else gross_amount - fee,
                    fee=fee,
                    currency=current_currency,
                    source_section="Trades",
                    source_line=_normalize_trade_line(line),
                )
            )

    return entries


def _parse_simple_cash_section(page_texts: list[str], heading: str, entry_type: LedgerEntryType) -> list[ImportedLedgerEntry]:
    lines = _collect_section_lines(page_texts, heading)
    entries: list[ImportedLedgerEntry] = []
    current_currency: str | None = None

    pattern = re.compile(r"^(?P<trade_date>\d{4}-\d{2}-\d{2}) (?P<description>.+) (?P<amount>-?[\d,]+(?:\.\d+)?)(?: (?P<code>[A-Za-z;]+))?$")
    records: list[tuple[str, str]] = []
    pending_record: str | None = None

    for line in lines:
        if _is_currency_heading(line):
            if pending_record is not None and current_currency is not None:
                records.append((current_currency, pending_record))
                pending_record = None
            current_currency = line
            continue
        if line in {heading, "Date Description Amount", "Date Description Amount Code", "Other Fees"}:
            continue
        if line.startswith("Total") or line.startswith("Activity Statement"):
            continue

        if current_currency is None:
            continue

        if _DATE_RE.match(line):
            if pending_record is not None:
                records.append((current_currency, pending_record))
            pending_record = line
        elif pending_record is not None:
            pending_record = f"{pending_record} {line}".strip()

    if pending_record is not None and current_currency is not None:
        records.append((current_currency, pending_record))

    for currency, record in records:
        normalized = re.sub(r"\s+", " ", record)
        match = pattern.match(normalized)
        if not match:
            continue

        amount = _parse_number(match.group("amount"))
        symbol_match = re.match(r"^(?P<symbol>[^()]+)\(", match.group("description"))
        entries.append(
            ImportedLedgerEntry(
                entry_type=entry_type,
                trade_date=_parse_date(match.group("trade_date")),
                symbol=symbol_match.group("symbol").strip() if symbol_match else None,
                description=match.group("description"),
                gross_amount=amount,
                net_amount=amount,
                fee=abs(amount) if entry_type == "FEE" else 0,
                tax=abs(amount) if entry_type == "WITHHOLDING_TAX" else 0,
                currency=currency,
                source_section=heading,
                source_line=normalized,
            )
        )

    return entries


def _parse_deposits_and_withdrawals(page_texts: list[str]) -> list[ImportedLedgerEntry]:
    lines = _collect_section_lines(page_texts, "Deposits & Withdrawals")
    entries: list[ImportedLedgerEntry] = []
    current_currency: str | None = None
    pattern = re.compile(r"^(?P<trade_date>\d{4}-\d{2}-\d{2}) (?P<description>.+) (?P<amount>-?[\d,]+(?:\.\d+)?)$")

    for line in lines:
        if _is_currency_heading(line):
            current_currency = line
            continue
        if line in {"Deposits & Withdrawals", "Date Description Amount"}:
            continue
        if line.startswith("Total") or line.startswith("Activity Statement"):
            continue
        match = pattern.match(line)
        if not match or current_currency is None:
            continue

        amount = _parse_number(match.group("amount"))
        entries.append(
            ImportedLedgerEntry(
                entry_type="DEPOSIT" if amount >= 0 else "WITHDRAWAL",
                trade_date=_parse_date(match.group("trade_date")),
                description=match.group("description"),
                gross_amount=amount,
                net_amount=amount,
                currency=current_currency,
                source_section="Deposits & Withdrawals",
                source_line=line,
            )
        )

    return entries


def _parse_cash_balances(page_texts: list[str]) -> list[ImportedCashBalance]:
    lines: list[str] = []
    in_cash_report = False
    for page_text in page_texts:
        for raw_line in page_text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line == "Cash Report":
                in_cash_report = True
                continue
            if in_cash_report and line == "Open Positions":
                in_cash_report = False
                break
            if in_cash_report and not line.startswith("Activity Statement"):
                lines.append(line)

    balances: list[ImportedCashBalance] = []
    pending: ImportedCashBalance | None = None

    start_re = re.compile(r"^Starting Cash (?P<amount>-?[\d,]+(?:\.\d+)?)")
    end_re = re.compile(r"^Ending Cash (?P<amount>-?[\d,]+(?:\.\d+)?)")
    settled_re = re.compile(r"^Ending Settled Cash (?P<amount>-?[\d,]+(?:\.\d+)?)")

    for line in lines:
        if _is_currency_heading(line):
            if pending is not None:
                balances.append(pending)
            pending = ImportedCashBalance(currency=line)
            continue
        if line in {"Total Securities Futures", "Base Currency Summary"}:
            continue
        if line.startswith("Activity Statement"):
            continue

        if pending is None:
            continue

        start_match = start_re.match(line)
        end_match = end_re.match(line)
        settled_match = settled_re.match(line)
        if start_match:
            pending.starting_cash = _parse_number(start_match.group("amount"))
        elif end_match:
            pending.ending_cash = _parse_number(end_match.group("amount"))
        elif settled_match:
            pending.ending_settled_cash = _parse_number(settled_match.group("amount"))

    if pending is not None:
        balances.append(pending)

    return balances


def _parse_instruments(page_texts: list[str]) -> list[ImportedInstrument]:
    start_index = next((i for i, text in enumerate(page_texts) if "Financial Instrument Information" in text), None)
    if start_index is None:
        return []

    lines: list[str] = []
    for page_text in page_texts[start_index:]:
        if "Codes" in page_text:
            page_text = page_text.split("Codes", 1)[0]
            lines.extend(page_text.splitlines())
            break
        lines.extend(page_text.splitlines())

    instruments: list[ImportedInstrument] = []
    pattern = re.compile(
        r"^(?P<prefix>.+?) (?P<conid>\d+) (?P<isin>[A-Z]{2}[A-Z0-9]{10}) (?P<underlying>.+?) (?P<exchange>[A-Z0-9.]+) 1 (?P<instrument_type>.+)$"
    )

    buffer = ""
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line in {"Financial Instrument Information", "Symbol Description Conid Security ID Underlying Listing Exch Multiplier Type Code", "Stocks"}:
            continue
        if line.startswith("Activity Statement"):
            continue

        candidate = f"{buffer} {line}".strip() if buffer else line
        normalized = re.sub(r"\s+", " ", candidate)
        match = pattern.match(normalized)
        if match:
            symbol = match.group("underlying").split(",")[0].strip()
            prefix = match.group("prefix").strip()
            description = prefix
            if prefix == symbol:
                description = symbol
            elif prefix.startswith(f"{symbol} "):
                description = prefix[len(symbol) :].strip()
            instruments.append(
                ImportedInstrument(
                    symbol=symbol,
                    description=description,
                    isin=match.group("isin").strip(),
                    listing_exchange=match.group("exchange").strip(),
                    instrument_type=match.group("instrument_type").strip(),
                )
            )
            buffer = ""
        else:
            buffer = candidate

    return instruments


def import_statement(path: str | Path) -> ImportedPortfolioSnapshot:
    detected_format = detect_statement_format(path)
    if detected_format != "pdf":
        raise ValueError("Only PDF Interactive Brokers statements are supported in the current importer.")

    preview = preview_pdf_statement(path)
    page_texts = _extract_text_by_page(path)
    as_of_date = _parse_period_end_date(preview.period) or date(2025, 12, 31)

    ledger_entries = []
    ledger_entries.extend(_parse_trades(page_texts))
    ledger_entries.extend(_parse_simple_cash_section(page_texts, "Dividends", "DIVIDEND"))
    ledger_entries.extend(_parse_simple_cash_section(page_texts, "Withholding Tax", "WITHHOLDING_TAX"))
    ledger_entries.extend(_parse_simple_cash_section(page_texts, "Interest", "INTEREST"))
    ledger_entries.extend(_parse_simple_cash_section(page_texts, "Fees", "FEE"))
    ledger_entries.extend(_parse_deposits_and_withdrawals(page_texts))

    statement = ImportedStatement(
        importer="interactive_brokers",
        imported_at=datetime.now(UTC),
        source_path=str(path),
        detected_format=detected_format,
        account_id=preview.account_id,
        base_currency=preview.base_currency,
        statement_period=preview.period,
        page_count=preview.page_count,
    )

    return ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=_parse_statement_totals(page_texts),
        instruments=_parse_instruments(page_texts),
        cash_balances=_parse_cash_balances(page_texts),
        positions=_parse_open_positions(page_texts, as_of_date=as_of_date),
        ledger_entries=ledger_entries,
    )
