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
class Freedom24Preview:
    account_id: str | None
    period: str | None
    base_currency: str | None
    page_count: int


GROUPED_ENTRY_DAY = 1


def _statement_grouped_date(period: str | None) -> date:
    if period is None:
        return date(2026, 1, 1)
    start_date_str, _ = period.split(" - ")
    start_date = date.fromisoformat(start_date_str)
    return date(start_date.year, start_date.month, GROUPED_ENTRY_DAY)


def _extract_text_by_page(path: str | Path) -> list[str]:
    reader = PdfReader(str(path))
    return [(page.extract_text() or "") for page in reader.pages]


def _normalize_number(value: str) -> float:
    cleaned = value.replace("USD", "").replace("EUR", "").replace("GBP", "").replace(" ", "").strip()
    return float(cleaned)


def _merge_split_date(lines: list[str], index: int) -> tuple[str | None, int]:
    if index >= len(lines):
        return None, index
    current = lines[index].strip()
    if re.fullmatch(r"\d{4}-\d{2}-", current) and index + 1 < len(lines):
        next_part = lines[index + 1].strip()
        if re.fullmatch(r"\d{2}", next_part):
            return f"{current}{next_part}", index + 2
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", current):
        return current, index + 1
    return None, index


def _is_ticker(value: str) -> bool:
    return "." in value and value.upper() == value and any(char.isalpha() for char in value)


def preview_pdf_statement(path: str | Path) -> Freedom24Preview:
    page_texts = _extract_text_by_page(path)
    full_text = "\n".join(page_texts)
    first_page = page_texts[0] if page_texts else ""

    account_id_match = re.search(r"Client ID\s+(?P<account_id>\d+)", first_page)
    period_match = re.search(r"(?P<start>\d{4}-\d{2}-\d{2}) 23:59:59 - (?P<end>\d{4}-\d{2}-\d{2}) 23:59:59", first_page)
    currency_match = re.search(r"Commission currency\s+(?P<currency>[A-Z]{3})", first_page)

    period = None
    if period_match:
        period = f"{period_match.group('start')} - {period_match.group('end')}"

    if "Freedom24" not in full_text:
        raise ValueError("PDF does not look like a Freedom24 broker statement")

    return Freedom24Preview(
        account_id=account_id_match.group("account_id") if account_id_match else None,
        period=period,
        base_currency=currency_match.group("currency") if currency_match else "USD",
        page_count=len(page_texts),
    )


def _parse_statement_totals(page_texts: list[str]) -> ImportedStatementTotals:
    totals = ImportedStatementTotals(fx_rates={"USDUSD": 1.0})
    joined = "\n".join(page_texts)

    beginning_match = re.search(r"Beginning balance \([^)]*\)\s+Net assets, USD\s+(?P<value>[\d ]+\.\d+)", joined)
    ending_match = re.search(r"Ending balance \([^)]*\)\s+Net assets, USD\s+(?P<value>[\d ]+\.\d+)", joined)
    deposits_match = re.search(r"Total deposits/withdrawals for the period on trading accounts in foreign currency\s+USD : (?P<value>-?[\d ]+\.\d+)", joined)
    commissions_match = re.search(r"Total commissions for the period\s+USD : (?P<value>[\d ]+\.\d+)", joined)
    dividends_match = re.search(r"Total for the period in foreign currency\s+USD : (?P<value>-?[\d ]+\.\d+)", joined)

    if beginning_match:
        totals.starting_nav = _normalize_number(beginning_match.group("value"))
    if ending_match:
        totals.ending_nav = _normalize_number(ending_match.group("value"))
    if deposits_match:
        totals.deposits_total = abs(_normalize_number(deposits_match.group("value")))
    if commissions_match:
        totals.commissions_total = abs(_normalize_number(commissions_match.group("value")))
        totals.other_fees_total = abs(_normalize_number(commissions_match.group("value")))
    if dividends_match:
        totals.dividends_total = abs(_normalize_number(dividends_match.group("value")))

    tax_match = re.search(r"Taxes\s+Grouped\s+trading\s+(?P<value>-?[\d ]+\.\d+)\s+USD", joined)
    if tax_match:
        totals.withholding_tax_total = abs(_normalize_number(tax_match.group("value")))

    cash_total_match = re.search(r"Ending balance \([^)]*\)\s+Net assets, USD\s+[\d ]+\.\d+\s+Funds in the trading account\s+USD\s+(?P<cash>[\d ]+\.\d+)", joined)
    stock_total_match = re.search(r"Ending balance \([^)]*\)\s+Net assets, USD\s+[\d ]+\.\d+\s+Funds in the trading account\s+USD\s+[\d ]+\.\d+\s+Opened positions, USD\s+(?P<stock>[\d ]+\.\d+)", joined)
    if cash_total_match:
        totals.cash_total = _normalize_number(cash_total_match.group("cash"))
    if stock_total_match:
        totals.stock_total = _normalize_number(stock_total_match.group("stock"))

    return totals


def _parse_positions(page_texts: list[str], as_of_date: date) -> list[ImportedPosition]:
    lines = (page_texts[3] if len(page_texts) >= 4 else "").splitlines()
    positions: list[ImportedPosition] = []
    index = 10

    while index + 7 < len(lines):
        ticker = lines[index].strip()
        if not _is_ticker(ticker):
            index += 1
            continue

        isin = lines[index + 1].strip()  # noqa: F841 — parsed-but-dropped; ISIN is modeled on ImportedInstrument but not yet flowed from Freedom24 positions (data gap → Epic 24, tech-debt-register)
        account = lines[index + 2].strip()
        asset_type = lines[index + 3].strip()
        beginning_balance = _normalize_number(lines[index + 4])
        ending_balance = _normalize_number(lines[index + 5])
        price_raw = lines[index + 6].strip()
        currency_or_value = lines[index + 7].strip()

        if currency_or_value in {"USD", "EUR", "GBP"} and index + 8 < len(lines):
            currency = currency_or_value
            market_value = _normalize_number(lines[index + 8])
            close_price = _normalize_number(price_raw)
            step = 9
        else:
            currency = "USD"
            market_value = _normalize_number(currency_or_value)
            close_price = _normalize_number(price_raw) if price_raw not in {"0", "0.00"} else 0.0
            step = 8

        if account.lower() == "trading" and asset_type.lower() == "funds" and ending_balance > 0:
            symbol = ticker.replace(".US", "")
            trade_delta = ending_balance - beginning_balance
            if beginning_balance > 0 and trade_delta > 0:
                cost_basis = round((trade_delta * close_price) + (beginning_balance * close_price), 2)
            else:
                cost_basis = round(ending_balance * close_price, 2)
            positions.append(
                ImportedPosition(
                    as_of_date=as_of_date,
                    symbol=symbol,
                    quantity=ending_balance,
                    cost_basis=cost_basis,
                    close_price=close_price,
                    market_value=market_value,
                    unrealized_pnl=round(market_value - cost_basis, 2),
                    currency=currency,
                )
            )

        index += step

    return positions


def _parse_cash_balances(page_texts: list[str]) -> list[ImportedCashBalance]:
    lines = (page_texts[9] if len(page_texts) >= 10 else "").splitlines()
    balances: list[ImportedCashBalance] = []
    index = 7

    while index + 5 < len(lines):
        currency = lines[index].strip()
        if not re.fullmatch(r"[A-Z]{3}", currency):
            index += 1
            continue

        balances.append(
            ImportedCashBalance(
                currency=currency,
                starting_cash=_normalize_number(lines[index + 1]),
                ending_cash=_normalize_number(lines[index + 5]),
                ending_settled_cash=_normalize_number(lines[index + 5]),
            )
        )
        index += 6

    return balances


def _parse_transactions(page_texts: list[str], grouped_trade_date: date) -> list[ImportedLedgerEntry]:
    lines = (page_texts[6] if len(page_texts) >= 7 else "").splitlines()
    entries: list[ImportedLedgerEntry] = []
    index = 13

    while index + 11 < len(lines):
        ticker = lines[index].strip()
        if not _is_ticker(ticker):
            index += 1
            continue

        direction = lines[index + 3].strip()
        quantity = _normalize_number(lines[index + 4])
        price = _normalize_number(lines[index + 5])
        amount = _normalize_number(lines[index + 6])
        realized_pnl = _normalize_number(lines[index + 7])  # noqa: F841 — parsed-but-dropped; realized P&L is not modeled in ImportedLedgerEntry (scope decision → Epic 24, tech-debt-register)
        fee = _normalize_number(lines[index + 8])
        symbol = ticker.replace(".US", "")
        gross_amount = -amount if direction == "Buy" else amount
        net_amount = gross_amount - fee

        entries.append(
            ImportedLedgerEntry(
                entry_type="BUY" if direction == "Buy" else "SELL",
                trade_date=grouped_trade_date,
                symbol=symbol,
                description=f"Freedom24 grouped {direction.lower()} trade for statement period",
                quantity=quantity,
                price=price,
                gross_amount=gross_amount,
                net_amount=net_amount,
                fee=fee,
                currency="USD",
                source_section="Transactions",
                source_line=" | ".join(lines[index : index + 12]),
            )
        )

        index += 12

    return entries


def _parse_cash_movements(page_texts: list[str], grouped_trade_date: date) -> list[ImportedLedgerEntry]:
    lines = (page_texts[4] if len(page_texts) >= 5 else "").splitlines()
    entries: list[ImportedLedgerEntry] = []
    index = 7

    while index < len(lines):
        entry_type = lines[index].strip()
        if entry_type.startswith("Total deposits/withdrawals"):
            break
        if entry_type not in {"Dividends", "Taxes"}:
            index += 1
            continue

        parsed_date, next_index = _merge_split_date(lines, index + 1)
        if parsed_date is None or next_index + 2 >= len(lines):
            index += 1
            continue
        account = lines[next_index].strip()  # noqa: F841 — parsed-but-dropped; account identity is modeled at statement level (ImportedStatement.account_id), per-line value intentionally unused (→ Epic 24, tech-debt-register)
        amount = _normalize_number(lines[next_index + 1])
        currency = lines[next_index + 2].strip()
        description_parts: list[str] = []
        cursor = next_index + 3
        while cursor < len(lines) and lines[cursor].strip() not in {"Dividends", "Taxes"} and not lines[cursor].strip().startswith("Total deposits/withdrawals"):
            description_parts.append(lines[cursor].strip())
            cursor += 1
        description = " ".join(part for part in description_parts if part)
        trade_date = date.fromisoformat(parsed_date)
        if entry_type == "Dividends":
            entries.append(
                ImportedLedgerEntry(
                    entry_type="DIVIDEND",
                    trade_date=trade_date,
                    description=description or "Freedom24 dividends",
                    gross_amount=amount,
                    net_amount=amount,
                    currency=currency,
                    source_section="Cash deposits/ withdrawals",
                    source_line=" | ".join(lines[index:cursor]),
                )
            )
        else:
            entries.append(
                ImportedLedgerEntry(
                    entry_type="WITHHOLDING_TAX",
                    trade_date=trade_date,
                    description=description or "Freedom24 taxes",
                    gross_amount=amount,
                    net_amount=amount,
                    tax=abs(amount),
                    currency=currency,
                    source_section="Cash deposits/ withdrawals",
                    source_line=" | ".join(lines[index:cursor]),
                )
            )

        index = cursor

    return entries


def _parse_commissions(page_texts: list[str], grouped_trade_date: date) -> list[ImportedLedgerEntry]:
    lines = (page_texts[7] if len(page_texts) >= 8 else "").splitlines()
    if len(lines) < 10:
        return []

    entries: list[ImportedLedgerEntry] = []
    index = 6
    while index < len(lines):
        if lines[index].strip() == "Total commissions for the period":
            if index + 1 < len(lines):
                total_line = lines[index + 1].strip()
                match = re.fullmatch(r"([A-Z]{3})\s*:\s*([\d ]+\.\d+)", total_line)
                if match:
                    amount = _normalize_number(match.group(2))
                    currency = match.group(1)
                    entries.append(
                        ImportedLedgerEntry(
                            entry_type="FEE",
                            trade_date=grouped_trade_date,
                            description="Freedom24 grouped trading fee for statement period",
                            gross_amount=-amount,
                            net_amount=-amount,
                            fee=amount,
                            currency=currency,
                            source_section="Commissions",
                            source_line=" | ".join(lines[index:index + 2]),
                        )
                    )
            break
        index += 1
    return entries


def _parse_instruments(positions: list[ImportedPosition], page_texts: list[str]) -> list[ImportedInstrument]:
    lines = (page_texts[3] if len(page_texts) >= 4 else "").splitlines()
    instruments: list[ImportedInstrument] = []
    index = 10
    position_symbols = {position.symbol for position in positions}

    while index + 7 < len(lines):
        ticker = lines[index].strip()
        if not _is_ticker(ticker):
            index += 1
            continue

        symbol = ticker.replace(".US", "")
        isin = lines[index + 1].strip()
        asset_type = lines[index + 3].strip()
        if symbol in position_symbols:
            instruments.append(
                ImportedInstrument(
                    symbol=symbol,
                    description=ticker,
                    isin=isin,
                    listing_exchange="ITS",
                    instrument_type="ETF" if asset_type.lower() == "funds" else asset_type.upper(),
                    currency="USD",
                )
            )
        index += 9 if index + 8 < len(lines) and lines[index + 7].strip() in {"USD", "EUR", "GBP"} else 8

    return instruments


def import_statement(path: str | Path) -> ImportedPortfolioSnapshot:
    preview = preview_pdf_statement(path)
    page_texts = _extract_text_by_page(path)

    if preview.period is None:
        raise ValueError("Could not determine Freedom24 statement period")

    _, end_date_str = preview.period.split(" - ")
    as_of_date = date.fromisoformat(end_date_str)
    grouped_trade_date = _statement_grouped_date(preview.period)
    positions = _parse_positions(page_texts, as_of_date)
    ledger_entries = [
        *_parse_transactions(page_texts, grouped_trade_date),
        *_parse_cash_movements(page_texts, grouped_trade_date),
        *_parse_commissions(page_texts, grouped_trade_date),
    ]

    statement = ImportedStatement(
        importer="freedom24",
        imported_at=datetime.now(UTC),
        source_path=str(path),
        detected_format="pdf",
        account_id=preview.account_id,
        base_currency=preview.base_currency,
        statement_period=preview.period,
        page_count=preview.page_count,
    )

    snapshot = ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=_parse_statement_totals(page_texts),
        instruments=_parse_instruments(positions, page_texts),
        cash_balances=_parse_cash_balances(page_texts),
        positions=positions,
        ledger_entries=ledger_entries,
    )

    # US-14.3: enrich instruments with FMP company-profile data so unknown
    # symbols get their description + instrument_type populated (the
    # Freedom24 parser sets description=ticker by design — too thin for
    # the description-based ETF classification fallback in InstrumentRegistry).
    # Fail-graceful: any enrichment failure leaves the import flow intact.
    try:
        from app.services.instrument_enrichment import enrich_imported_instruments
        from app.services.market_data import MarketDataService

        snapshot = enrich_imported_instruments(snapshot, MarketDataService())
    except Exception:  # noqa: BLE001 — a bad import is worse than a missing sector
        pass

    return snapshot
