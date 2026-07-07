"""US-28.1: IBKR Activity-Statement CSV importer.

Golden-master tests pin the import of docs/IB2026.csv (the real statement,
2026-01-01 → 2026-06-30); mutation tests pin the fail-safe per-record
discipline (US-24.4/24.8): a malformed record is skipped — import succeeds,
the record is absent, nothing is zero-filled.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest

from app.analytics.reconciliation import build_reconciliation_summary
from app.importers.interactive_brokers import import_statement as import_pdf_statement
from app.importers.interactive_brokers_csv import (
    _parse_number,
    _read_records,
    import_statement,
    preview_csv_statement,
)
from app.tests._statement_fixtures import STATEMENT_2025_PATH, STATEMENT_2026_CSV_PATH


# Statement-truth pins for docs/IB2026.csv (values from the statement itself).
EXPECTED_ACCOUNT = "U8516450"
EXPECTED_PERIOD = "2026-01-01 - 2026-06-30"
EXPECTED_POSITION_COUNT = 20
EXPECTED_INSTRUMENT_COUNT = 65
EXPECTED_LEDGER_COUNTS = {
    "BUY": 79,
    "SELL": 67,
    "DIVIDEND": 24,
    "WITHHOLDING_TAX": 27,
    "INTEREST": 1,
    "FEE": 5,
    "DEPOSIT": 1,
}


@pytest.fixture(scope="module")
def snapshot():
    return import_statement(STATEMENT_2026_CSV_PATH)


# ── AC1: statement identity + totals ──────────────────────────────────────────

def test_preview_extracts_statement_identity() -> None:
    preview = preview_csv_statement(STATEMENT_2026_CSV_PATH)
    assert preview.account_id == EXPECTED_ACCOUNT
    assert preview.period == EXPECTED_PERIOD
    assert preview.base_currency == "USD"


def test_preview_rejects_non_ibkr_csv(tmp_path: Path) -> None:
    other = tmp_path / "other.csv"
    other.write_text("Statement,Header,Field Name,Field Value\nStatement,Data,BrokerName,Some Other Broker\n")
    with pytest.raises(ValueError, match="does not look like an Interactive Brokers"):
        preview_csv_statement(other)


def test_import_statement_identity(snapshot) -> None:
    statement = snapshot.statement
    assert statement.importer == "interactive_brokers"
    assert statement.detected_format == "csv"
    assert statement.account_id == EXPECTED_ACCOUNT
    assert statement.base_currency == "USD"
    assert statement.statement_period == EXPECTED_PERIOD
    assert snapshot.statements == [statement]


def test_import_statement_totals_match_change_in_nav(snapshot) -> None:
    totals = snapshot.statement_totals
    assert totals is not None
    # Absolute values — the schema's established convention (shared with the
    # PDF path and assumed by build_reconciliation_summary); the CSV's signs
    # (withholding −17.47, other fees −1.05) live on the ledger entries.
    assert totals.starting_nav == pytest.approx(52381.12, abs=0.005)
    assert totals.ending_nav == pytest.approx(63234.80, abs=0.005)
    assert totals.cash_total == pytest.approx(1993.65, abs=0.005)
    assert totals.stock_total == pytest.approx(61238.53, abs=0.005)
    assert totals.dividends_total == pytest.approx(122.64)
    assert totals.withholding_tax_total == pytest.approx(17.47)
    assert totals.interest_total == pytest.approx(1.64)
    assert totals.other_fees_total == pytest.approx(1.05)
    assert totals.commissions_total == pytest.approx(185.08, abs=0.005)
    assert totals.deposits_total == pytest.approx(9963.00)
    assert totals.time_weighted_return_pct == pytest.approx(1.250764, abs=1e-6)


def test_fx_rates_implied_from_open_positions_totals(snapshot) -> None:
    fx_rates = snapshot.statement_totals.fx_rates
    assert fx_rates["USDUSD"] == 1.0
    # 14212.3946 / 12443 and 3580.07217 / 2699.7 — the statement's own
    # base-currency restatements of the EUR and GBP position totals.
    assert fx_rates["EURUSD"] == pytest.approx(1.1422, abs=1e-4)
    assert fx_rates["GBPUSD"] == pytest.approx(1.3261, abs=1e-4)


# ── AC2: per-currency positions ───────────────────────────────────────────────

def test_positions_are_per_currency_and_complete(snapshot) -> None:
    assert len(snapshot.positions) == EXPECTED_POSITION_COUNT
    by_currency = Counter(position.currency for position in snapshot.positions)
    assert by_currency == {"USD": 16, "EUR": 3, "GBP": 1}
    for position in snapshot.positions:
        assert position.as_of_date.isoformat() == "2026-06-30"


def test_pinned_per_currency_positions(snapshot) -> None:
    by_symbol = {position.symbol: position for position in snapshot.positions}

    defs = by_symbol["DEFS"]  # EUR
    assert (defs.currency, defs.quantity) == ("EUR", 500)
    assert defs.cost_basis == pytest.approx(2796.475015)
    assert defs.close_price == pytest.approx(5.635)
    assert defs.market_value == pytest.approx(2817.5)
    assert defs.unrealized_pnl == pytest.approx(21.024985)

    semi = by_symbol["SEMI"]  # GBP
    assert (semi.currency, semi.quantity) == ("GBP", 150)
    assert semi.market_value == pytest.approx(2699.7)
    assert semi.unrealized_pnl == pytest.approx(660.0)

    amzn = by_symbol["AMZN"]  # USD
    assert (amzn.currency, amzn.quantity) == ("USD", 10)
    assert amzn.cost_basis == pytest.approx(1654.07584)
    assert amzn.market_value == pytest.approx(2383.4)


def test_positions_market_value_reconciles_to_nav_stock_total(snapshot) -> None:
    summary = build_reconciliation_summary(snapshot)
    check = next(c for c in summary.checks if c.name == "open_positions_market_value")
    assert check.passed, f"expected {check.expected}, actual {check.actual}"


# ── AC3: ledger coverage + reconciliation ─────────────────────────────────────

def test_ledger_entry_type_counts(snapshot) -> None:
    counts = Counter(entry.entry_type for entry in snapshot.ledger_entries)
    assert counts == EXPECTED_LEDGER_COUNTS


def test_section_total_rows_are_excluded(snapshot) -> None:
    # Every ledger entry came from a real record row: a section-total row has
    # no parsable date/currency and must not appear as a ledger entry.
    for entry in snapshot.ledger_entries:
        assert entry.currency.isalpha() and len(entry.currency) == 3
        assert entry.source_line is not None


def test_reconciliation_summary_passes(snapshot) -> None:
    summary = build_reconciliation_summary(snapshot)
    by_name = {check.name: check for check in summary.checks}
    for name in (
        "dividends_total",
        "withholding_tax_total",
        "interest_total",
        "other_fees_total",
        "deposits_total",
    ):
        assert by_name[name].passed, f"{name}: expected {by_name[name].expected}, actual {by_name[name].actual}"
    assert summary.passed


def test_credit_interest_withholding_counts_toward_total(snapshot) -> None:
    # Regression (US-28.1): IBKR's own Withholding Tax total includes
    # credit-interest withholding; the reconciliation used to exclude it and
    # therefore failed against the statement's own number.
    credit_rows = [
        entry
        for entry in snapshot.ledger_entries
        if entry.entry_type == "WITHHOLDING_TAX" and "Credit Interest" in (entry.description or "")
    ]
    assert len(credit_rows) == 1
    assert credit_rows[0].gross_amount == pytest.approx(-0.33)


def test_withholding_reconciliation_fix_holds_for_legacy_pdf() -> None:
    # The same fix must reconcile the legacy 2025 PDF statement (which has
    # credit-interest withholding rows of its own).
    summary = build_reconciliation_summary(import_pdf_statement(STATEMENT_2025_PATH))
    check = next(c for c in summary.checks if c.name == "withholding_tax_total")
    assert check.passed, f"expected {check.expected}, actual {check.actual}"


# ── AC4: instruments ──────────────────────────────────────────────────────────

def test_instruments_carry_isin_exchange_and_type(snapshot) -> None:
    assert len(snapshot.instruments) == EXPECTED_INSTRUMENT_COUNT
    assert all(instrument.isin for instrument in snapshot.instruments)

    by_symbol = {instrument.symbol: instrument for instrument in snapshot.instruments}
    aapl = by_symbol["AAPL"]
    assert aapl.description == "APPLE INC"
    assert aapl.isin == "US0378331005"
    assert aapl.listing_exchange == "NASDAQ"
    assert aapl.instrument_type == "COMMON"

    cibr = by_symbol["CIBR"]
    assert cibr.isin == "IE00BF16M727"
    assert cibr.listing_exchange == "LSEETF"
    assert cibr.instrument_type == "ETF"


# ── cash balances ─────────────────────────────────────────────────────────────

def test_cash_balances_per_currency_without_base_summary_double_count(snapshot) -> None:
    by_currency = {balance.currency: balance for balance in snapshot.cash_balances}
    assert set(by_currency) == {"USD", "EUR", "GBP"}
    usd = by_currency["USD"]
    assert usd.starting_cash == pytest.approx(4672.04, abs=0.005)
    assert usd.ending_cash == pytest.approx(1993.65, abs=0.005)
    assert usd.ending_settled_cash == pytest.approx(1993.65, abs=0.005)
    assert by_currency["EUR"].ending_cash == 0.0
    assert by_currency["GBP"].ending_cash == 0.0


# ── AC5: fail-safe mutations ─────────────────────────────────────────────────

def _mutated_fixture(tmp_path: Path, old: str, new: str) -> Path:
    text = STATEMENT_2026_CSV_PATH.read_text(encoding="utf-8-sig")
    assert old in text, f"mutation target not found in fixture: {old!r}"
    mutated = tmp_path / "mutated.csv"
    mutated.write_text(text.replace(old, new, 1), encoding="utf-8-sig")
    return mutated


def test_failsafe_non_numeric_position_quantity(tmp_path: Path) -> None:
    path = _mutated_fixture(
        tmp_path,
        "Open Positions,Data,Summary,Stocks,USD,AMZN,10,",
        "Open Positions,Data,Summary,Stocks,USD,AMZN,not-a-number,",
    )
    snapshot = import_statement(path)
    assert len(snapshot.positions) == EXPECTED_POSITION_COUNT - 1
    assert "AMZN" not in {position.symbol for position in snapshot.positions}
    assert all(position.quantity != 0 for position in snapshot.positions)


def test_failsafe_malformed_dividend_date(tmp_path: Path) -> None:
    path = _mutated_fixture(
        tmp_path,
        "Dividends,Data,USD,2026-01-08,CRM",
        "Dividends,Data,USD,2026-99-08,CRM",
    )
    snapshot = import_statement(path)
    dividends = [entry for entry in snapshot.ledger_entries if entry.entry_type == "DIVIDEND"]
    assert len(dividends) == EXPECTED_LEDGER_COUNTS["DIVIDEND"] - 1
    assert all(entry.gross_amount for entry in dividends)


def test_failsafe_short_trade_row(tmp_path: Path) -> None:
    original = 'Trades,Data,Order,Stocks,EUR,ACOMO,"2026-04-07, 05:37:03",-30,27.3,26.65,819,-1.25,-721.87,95.88,19.5,C;IA'
    path = _mutated_fixture(tmp_path, original, "Trades,Data,Order,Stocks,EUR,ACOMO")
    snapshot = import_statement(path)
    counts = Counter(entry.entry_type for entry in snapshot.ledger_entries)
    assert counts["SELL"] == EXPECTED_LEDGER_COUNTS["SELL"] - 1
    assert counts["BUY"] == EXPECTED_LEDGER_COUNTS["BUY"]


def test_failsafe_missing_close_price_cell(tmp_path: Path) -> None:
    path = _mutated_fixture(
        tmp_path,
        "Open Positions,Data,Summary,Stocks,EUR,DEFS,500,1,5.59295003,2796.475015,5.635,2817.5,21.024985,",
        "Open Positions,Data,Summary,Stocks,EUR,DEFS,500,1,5.59295003,2796.475015,--,2817.5,21.024985,",
    )
    snapshot = import_statement(path)
    # The record degrades away — never a zero-filled close price.
    assert "DEFS" not in {position.symbol for position in snapshot.positions}
    assert len(snapshot.positions) == EXPECTED_POSITION_COUNT - 1
    assert all(position.close_price != 0 for position in snapshot.positions)


# ── AC6: BOM + quoting on the row reader ─────────────────────────────────────

def test_parse_number_handles_quoted_thousands_and_missing_sentinel() -> None:
    assert _parse_number("1,069.8600") == pytest.approx(1069.86)
    assert _parse_number("-1,266.9770624") == pytest.approx(-1266.9770624)
    with pytest.raises(ValueError):
        _parse_number("--")
    with pytest.raises(ValueError):
        _parse_number("")
    with pytest.raises(ValueError):
        _parse_number(None)


def test_read_records_handles_bom_quoting_and_header_restatement(tmp_path: Path) -> None:
    csv_path = tmp_path / "bom.csv"
    csv_path.write_bytes(
        "﻿".encode("utf-8")
        + (
            "Trades,Header,DataDiscriminator,Symbol,Quantity\n"
            'Trades,Data,Order,ACME,"1,457.77"\n'
            "Trades,Header,DataDiscriminator,Symbol,Proceeds\n"
            'Trades,Data,Order,OTHER,"2,000.00"\n'
            'Statement,Data,Period,"January 1, 2026 - June 30, 2026"\n'
        ).encode("utf-8")
    )
    records = _read_records(csv_path)
    # BOM must not leak into the first section name.
    assert records[0].section == "Trades"
    assert records[0].record == {"DataDiscriminator": "Order", "Symbol": "ACME", "Quantity": "1,457.77"}
    # The restated header remaps rows that follow it.
    assert records[1].record == {"DataDiscriminator": "Order", "Symbol": "OTHER", "Proceeds": "2,000.00"}
    # Quoted comma survives as one cell.
    assert records[2].cells == ["Period", "January 1, 2026 - June 30, 2026"]
