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
from app.services.statement_importer import (
    import_statement as route_import_statement,
    import_statements,
)
from app.tests._statement_fixtures import STATEMENT_2025_PATH, STATEMENT_2026_CSV_PATH

# Statement-truth pins live in ONE module (US-28.3); tests reference them by
# name so a statement refresh updates a single file.
from app.tests.statement_truths import (
    IB_ACCOUNT_ID as EXPECTED_ACCOUNT,
    IB_INSTRUMENT_COUNT as EXPECTED_INSTRUMENT_COUNT,
    IB_LEDGER_COUNTS as EXPECTED_LEDGER_COUNTS,
    IB_PINNED_INSTRUMENTS,
    IB_PINNED_POSITIONS,
    IB_POSITION_COUNT as EXPECTED_POSITION_COUNT,
    IB_POSITIONS_BY_CURRENCY,
    IB_STATEMENT_PERIOD as EXPECTED_PERIOD,
    diff_statement_truths,
)


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
    # Totals are absolute values — the schema's established convention (shared
    # with the PDF path and assumed by build_reconciliation_summary); the
    # CSV's signs (withholding −17.47, other fees −1.05) live on the ledger
    # entries. The pinned values live in statement_truths, checked by
    # test_statement_matches_truths_module; here we pin only that every totals
    # field the statement carries actually landed (no silent None).
    totals = snapshot.statement_totals
    assert totals is not None
    for field in (
        "starting_nav", "ending_nav", "cash_total", "stock_total",
        "dividends_total", "withholding_tax_total", "interest_total",
        "other_fees_total", "commissions_total", "deposits_total",
        "time_weighted_return_pct",
    ):
        assert getattr(totals, field) is not None, field


def test_fx_rates_implied_from_open_positions_totals(snapshot) -> None:
    # Implied from the statement's own base-currency restatements of each
    # non-base Open Positions group total (values pinned in statement_truths).
    fx_rates = snapshot.statement_totals.fx_rates
    assert fx_rates["USDUSD"] == 1.0
    assert set(fx_rates) == {"USDUSD"} | {f"{c}USD" for c in IB_POSITIONS_BY_CURRENCY if c != "USD"}


def test_statement_matches_truths_module(snapshot) -> None:
    # THE statement-truth gate: every pin in statement_truths holds for the
    # committed docs/IB2026.csv. On a statement refresh, this is the test that
    # tells you exactly which pins to update.
    assert diff_statement_truths(snapshot) == []


# ── AC2: per-currency positions ───────────────────────────────────────────────

def test_positions_are_per_currency_and_complete(snapshot) -> None:
    assert len(snapshot.positions) == EXPECTED_POSITION_COUNT
    by_currency = Counter(position.currency for position in snapshot.positions)
    assert by_currency == IB_POSITIONS_BY_CURRENCY
    # Invariant: every position dates to the statement's own period end.
    period_end = EXPECTED_PERIOD.split(" - ")[1]
    for position in snapshot.positions:
        assert position.as_of_date.isoformat() == period_end


def test_pinned_per_currency_positions(snapshot) -> None:
    # One pinned position per statement currency; values single-sourced from
    # statement_truths (full-precision row fields).
    by_symbol = {position.symbol: position for position in snapshot.positions}
    assert {IB_PINNED_POSITIONS[s]["currency"] for s in IB_PINNED_POSITIONS} == set(IB_POSITIONS_BY_CURRENCY)
    for symbol, expected in IB_PINNED_POSITIONS.items():
        position = by_symbol[symbol]
        for field, value in expected.items():
            actual = getattr(position, field)
            if isinstance(value, (int, float)):
                assert actual == pytest.approx(value), f"{symbol}.{field}"
            else:
                assert actual == value, f"{symbol}.{field}"


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
    # Invariant: the CSV's Financial Instrument Information always carries a
    # Security ID — every instrument lands with an ISIN.
    assert all(instrument.isin for instrument in snapshot.instruments)

    # Pinned exemplars single-sourced from statement_truths.
    by_symbol = {instrument.symbol: instrument for instrument in snapshot.instruments}
    for symbol, expected in IB_PINNED_INSTRUMENTS.items():
        instrument = by_symbol[symbol]
        for field, value in expected.items():
            assert getattr(instrument, field) == value, f"{symbol}.{field}"


# ── cash balances ─────────────────────────────────────────────────────────────

def test_cash_balances_per_currency_without_base_summary_double_count(snapshot) -> None:
    by_currency = {balance.currency: balance for balance in snapshot.cash_balances}
    assert set(by_currency) == set(IB_POSITIONS_BY_CURRENCY)
    # Invariant: the base-currency (USD) cash balances equal the statement's
    # own totals — sourcing them from the snapshot proves the Base Currency
    # Summary pseudo-rows were not double counted.
    totals = snapshot.statement_totals
    usd = by_currency["USD"]
    assert usd.ending_cash == pytest.approx(totals.cash_total)
    assert usd.ending_settled_cash == pytest.approx(totals.cash_total)
    assert usd.starting_cash is not None and usd.starting_cash > 0


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


# ── US-28.2: statement_importer routing ──────────────────────────────────────

def test_statement_importer_routes_csv_to_ibkr_csv_importer() -> None:
    snapshot = route_import_statement(STATEMENT_2026_CSV_PATH)
    assert snapshot.statement.detected_format == "csv"
    assert snapshot.statement.importer == "interactive_brokers"
    assert snapshot.statement.account_id == EXPECTED_ACCOUNT


def test_statement_importer_rejects_non_ibkr_csv(tmp_path: Path) -> None:
    other = tmp_path / "other.csv"
    other.write_text("Statement,Header,Field Name,Field Value\nStatement,Data,BrokerName,Some Other Broker\n")
    with pytest.raises(ValueError, match="does not look like an Interactive Brokers"):
        route_import_statement(other)


def test_statement_importer_rejects_unsupported_suffix(tmp_path: Path) -> None:
    xml = tmp_path / "statement.xml"
    xml.write_text("<statement/>")
    with pytest.raises(ValueError, match="Only PDF or CSV broker statements"):
        route_import_statement(xml)


def test_combine_legacy_pdf_with_csv_terminal_statement() -> None:
    combined = import_statements([STATEMENT_2025_PATH, STATEMENT_2026_CSV_PATH])
    assert len(combined.statements) == 2
    assert {s.detected_format for s in combined.statements} == {"pdf", "csv"}
    # Same account: the CSV (later period) is the terminal snapshot, so the
    # combined positions are the CSV's per-currency Open Positions.
    assert combined.statement.account_id == EXPECTED_ACCOUNT
    assert combined.statement.detected_format == "csv"
    assert len(combined.positions) == EXPECTED_POSITION_COUNT
    assert combined.statement.statement_period is not None
    assert combined.statement.statement_period.endswith("2026-06-30")


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
