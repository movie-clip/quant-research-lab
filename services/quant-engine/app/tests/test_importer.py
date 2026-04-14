from pathlib import Path

from app.importers.espp import import_statement as import_espp_statement, preview_pdf_statement as preview_espp_statement
from app.importers.interactive_brokers import import_statement as import_interactive_brokers_statement
from app.importers.freedom24 import import_statement as import_freedom24_statement, preview_pdf_statement as preview_freedom24_statement
from app.importers.interactive_brokers import detect_statement_format, import_statement, preview_pdf_statement
from app.analytics.performance import build_daily_portfolio_states
from app.services.statement_importer import combine_imported_snapshots


DOCS_DIR = Path(r"C:\projects\investments\portfolio\docs")
STATEMENT_2025_PATH = DOCS_DIR / "2025.pdf"
if not STATEMENT_2025_PATH.exists():
    STATEMENT_2025_PATH = DOCS_DIR / "IB2025.pdf"
STATEMENT_2026_PATH = DOCS_DIR / "2026.pdf"
if not STATEMENT_2026_PATH.exists():
    STATEMENT_2026_PATH = DOCS_DIR / "IB2026.pdf"
FREEDOM24_2026_PATH = DOCS_DIR / "FF2026.pdf"
ESPP_PATH = DOCS_DIR / "ESPP.pdf"


def test_detect_statement_format_pdf() -> None:
    assert detect_statement_format(STATEMENT_2025_PATH) == "pdf"
    assert detect_statement_format(STATEMENT_2026_PATH) == "pdf"


def test_preview_espp_statement_extracts_core_metadata() -> None:
    preview = preview_espp_statement(ESPP_PATH)

    assert preview.account_id == "I09548809"
    assert preview.base_currency == "USD"
    assert preview.period == "January 1, 2025 - December 31, 2025"
    assert preview.page_count == 6


def test_import_espp_statement_returns_expected_snapshot() -> None:
    snapshot = import_espp_statement(ESPP_PATH)
    positions_by_symbol = {position.symbol: position for position in snapshot.positions}

    assert snapshot.statement.importer == "espp"
    assert snapshot.statement.account_id == "I09548809"
    assert snapshot.statement.base_currency == "USD"
    assert snapshot.statement.statement_period == "January 1, 2025 - December 31, 2025"
    assert snapshot.statement.page_count == 6
    assert len(snapshot.positions) == 1
    assert round(positions_by_symbol["MSFT"].quantity, 3) == 7.012
    assert round(positions_by_symbol["MSFT"].market_value, 2) == 3391.24
    assert round(positions_by_symbol["MSFT"].cost_basis, 2) == 3139.15
    assert len(snapshot.cash_balances) == 1
    assert round(snapshot.cash_balances[0].ending_cash or 0, 2) == 10.44
    assert snapshot.statement_totals is not None
    assert round(snapshot.statement_totals.ending_nav or 0, 2) == 3401.68
    assert snapshot.statement_totals.starting_nav is None
    assert round(snapshot.statement_totals.stock_total or 0, 2) == 3391.24
    assert round(snapshot.statement_totals.cash_total or 0, 2) == 10.44
    assert round(snapshot.statement_totals.withholding_tax_total or 0, 2) == 1.83
    assert round(snapshot.statement_totals.dividends_total or 0, 2) == 12.27
    assert round(snapshot.statement_totals.deposits_total or 0, 2) == 3139.15
    assert len(snapshot.ledger_entries) == 4
    assert any(entry.entry_type == "DEPOSIT" for entry in snapshot.ledger_entries)
    assert any(entry.entry_type == "BUY" and entry.symbol == "MSFT" for entry in snapshot.ledger_entries)


def test_combine_imported_snapshots_ignores_zero_starting_nav_placeholder() -> None:
    ib_path = DOCS_DIR / "U8516450_20260101_20260408.pdf"
    if not ib_path.exists():
        return

    ib_snapshot = import_interactive_brokers_statement(ib_path)
    espp_snapshot = import_espp_statement(ESPP_PATH)

    combined = combine_imported_snapshots([espp_snapshot, ib_snapshot])

    assert combined.statement_totals is not None
    assert ib_snapshot.statement_totals is not None
    assert round(combined.statement_totals.starting_nav or 0, 2) == round(ib_snapshot.statement_totals.starting_nav or 0, 2)


def test_preview_pdf_statement_extracts_core_metadata_for_2025() -> None:
    preview = preview_pdf_statement(STATEMENT_2025_PATH)

    assert preview.account_id == "U8516450"
    assert preview.base_currency == "USD"
    assert preview.period == "January 1, 2025 - December 31, 2025"
    assert preview.page_count == 25
    assert preview.sections.trades is True
    assert preview.sections.open_positions is True
    assert preview.sections.cash_report is True


def test_preview_pdf_statement_extracts_core_metadata_for_2026() -> None:
    preview = preview_pdf_statement(STATEMENT_2026_PATH)

    assert preview.account_id == "U8516450"
    assert preview.base_currency == "USD"
    assert preview.period == "January 1, 2026 - April 8, 2026"
    assert preview.page_count == 17
    assert preview.sections.trades is True
    assert preview.sections.open_positions is True
    assert preview.sections.cash_report is True


def test_import_statement_2025_returns_stable_snapshot() -> None:
    snapshot = import_statement(STATEMENT_2025_PATH)

    assert snapshot.statement.account_id == "U8516450"
    assert snapshot.statement.base_currency == "USD"
    assert snapshot.statement.statement_period == "January 1, 2025 - December 31, 2025"
    assert snapshot.statement.page_count == 25
    assert len(snapshot.positions) == 38
    assert {position.as_of_date.isoformat() for position in snapshot.positions} == {"2025-12-31"}
    assert len(snapshot.instruments) >= 60
    assert len(snapshot.cash_balances) == 2
    assert len(snapshot.ledger_entries) >= 100
    assert snapshot.statement_totals is not None
    assert round(snapshot.statement_totals.starting_nav or 0, 2) == 40821.72
    assert round(snapshot.statement_totals.ending_nav or 0, 2) == 52381.12


def test_import_statement_2026_uses_statement_end_date_and_keeps_expected_positions() -> None:
    snapshot = import_statement(STATEMENT_2026_PATH)
    positions_by_symbol = {position.symbol: position for position in snapshot.positions}
    instruments_by_symbol = {instrument.symbol: instrument for instrument in snapshot.instruments}

    assert snapshot.statement.account_id == "U8516450"
    assert snapshot.statement.base_currency == "USD"
    assert snapshot.statement.statement_period == "January 1, 2026 - April 13, 2026"
    assert snapshot.statement.page_count == 18
    assert len(snapshot.positions) == 22
    assert {position.as_of_date.isoformat() for position in snapshot.positions} == {"2026-04-13"}
    assert "ICOM" in positions_by_symbol
    assert positions_by_symbol["ICOM"].currency == "USD"
    assert "DFND" in positions_by_symbol
    assert positions_by_symbol["DFND"].currency == "GBP"
    assert instruments_by_symbol["DFND"].instrument_type == "ETF"
    assert instruments_by_symbol["IUFS"].instrument_type == "ETF"
    assert instruments_by_symbol["HOOD"].instrument_type == "COMMON"
    assert "SXRV" in positions_by_symbol
    assert positions_by_symbol["SXRV"].currency == "EUR"
    assert instruments_by_symbol["SXRV"].description == "ISHARES NASDAQ 100 USD ACC"
    assert instruments_by_symbol["SXRV"].isin == "IE00B53SZB19"
    assert instruments_by_symbol["SXRV"].listing_exchange == "IBIS2"
    assert instruments_by_symbol["SXRV"].instrument_type == "ETF"
    assert len(snapshot.cash_balances) >= 1
    assert len(snapshot.ledger_entries) >= 1


def test_combine_imported_snapshots_merges_sequential_ib_statements() -> None:
    snapshot_2025 = import_interactive_brokers_statement(STATEMENT_2025_PATH)
    snapshot_2026 = import_interactive_brokers_statement(STATEMENT_2026_PATH)

    combined = combine_imported_snapshots([snapshot_2025, snapshot_2026])

    assert combined.statement.account_id == 'U8516450'
    assert combined.statement.base_currency == 'USD'
    assert combined.statement.statement_period == '2025-01-01 - 2026-04-08'
    assert len(combined.statements) == 2
    assert [Path(statement.source_path).name for statement in combined.statements] == [STATEMENT_2025_PATH.name, STATEMENT_2026_PATH.name]
    assert {position.as_of_date.isoformat() for position in combined.positions} == {'2026-04-08'}
    assert len(combined.positions) == len(snapshot_2026.positions)
    assert len(combined.ledger_entries) >= len(snapshot_2025.ledger_entries) + len(snapshot_2026.ledger_entries) - 5
    assert combined.statement_totals is not None
    assert round(combined.statement_totals.starting_nav or 0, 2) == 40821.72
    assert round(combined.statement_totals.ending_nav or 0, 2) > 0
    snapshot_2025_totals = snapshot_2025.statement_totals or snapshot_2026.statement_totals
    assert round(combined.statement_totals.deposits_total or 0, 2) >= round((snapshot_2025_totals.deposits_total or 0) if snapshot_2025_totals else 0, 2)


def test_multi_year_combination_does_not_backfill_fake_pre_funding_positions() -> None:
    paths = [
        DOCS_DIR / "U8516450_2022_2022.pdf",
        DOCS_DIR / "U8516450_2023_2023.pdf",
        DOCS_DIR / "U8516450_2024_2024.pdf",
        DOCS_DIR / "U8516450_2025_2025.pdf",
        DOCS_DIR / "U8516450_20260101_20260408.pdf",
    ]
    snapshot = combine_imported_snapshots([import_interactive_brokers_statement(path) for path in paths])
    valuation_dates = ["2022-01-03", "2022-04-11", "2022-04-12", "2022-04-13"]

    states = build_daily_portfolio_states(snapshot=snapshot, price_histories={}, valuation_dates=valuation_dates, fx_history={})

    assert states[0].total_market_value == 0
    assert states[0].total_portfolio_value == 0
    assert states[1].total_market_value == 0
    assert states[1].total_portfolio_value == 0
    assert states[2].external_cash_flow > 0


def test_combine_imported_snapshots_allows_mixed_broker_same_currency_imports() -> None:
    ib_path = DOCS_DIR / "U8516450_20260101_20260408.pdf"
    if not ib_path.exists():
        return
    ib_snapshot = import_interactive_brokers_statement(ib_path)
    freedom_snapshot = import_freedom24_statement(FREEDOM24_2026_PATH)

    combined = combine_imported_snapshots([ib_snapshot, freedom_snapshot])

    assert combined.statement.importer == "multi_broker"
    assert combined.statement.base_currency == "USD"
    assert combined.statement.account_id == "185960 + U8516450"
    assert len(combined.statements) == 2
    assert len(combined.positions) == len(ib_snapshot.positions) + len(freedom_snapshot.positions)
    assert {position.symbol for position in combined.positions} >= {"VTI", "VUAA"}
    assert round(sum(position.market_value for position in combined.positions), 2) == round(sum(position.market_value for position in ib_snapshot.positions) + sum(position.market_value for position in freedom_snapshot.positions), 2)
    assert len([balance for balance in combined.cash_balances if balance.currency == "USD"]) == 1
    assert round(sum((balance.ending_cash or 0.0) for balance in combined.cash_balances), 2) == round(sum((balance.ending_cash or 0.0) for balance in ib_snapshot.cash_balances) + sum((balance.ending_cash or 0.0) for balance in freedom_snapshot.cash_balances), 2)
    assert len(combined.ledger_entries) >= len(ib_snapshot.ledger_entries) + len(freedom_snapshot.ledger_entries)


def test_preview_freedom24_statement_extracts_core_metadata() -> None:
    preview = preview_freedom24_statement(FREEDOM24_2026_PATH)

    assert preview.account_id == "185960"
    assert preview.base_currency == "USD"
    assert preview.period == "2025-12-31 - 2026-04-11"
    assert preview.page_count == 13


def test_import_freedom24_statement_returns_expected_snapshot() -> None:
    snapshot = import_freedom24_statement(FREEDOM24_2026_PATH)
    positions_by_symbol = {position.symbol: position for position in snapshot.positions}

    assert snapshot.statement.importer == "freedom24"
    assert snapshot.statement.account_id == "185960"
    assert snapshot.statement.base_currency == "USD"
    assert snapshot.statement.statement_period == "2025-12-31 - 2026-04-11"
    assert snapshot.statement.page_count == 13
    assert len(snapshot.positions) == 1
    assert positions_by_symbol["VTI"].quantity == 9
    assert round(positions_by_symbol["VTI"].close_price, 2) == 335.44
    assert round(positions_by_symbol["VTI"].market_value, 2) == 3018.96
    assert len(snapshot.cash_balances) >= 1
    assert snapshot.cash_balances[0].currency == "USD"
    assert round(snapshot.cash_balances[0].starting_cash or 0, 2) == 911.23
    assert round(snapshot.cash_balances[0].ending_cash or 0, 2) == 52.04
    assert snapshot.statement_totals is not None
    assert round(snapshot.statement_totals.starting_nav or 0, 2) == 2900.12
    assert round(snapshot.statement_totals.ending_nav or 0, 2) == 3071.00
    assert len(snapshot.ledger_entries) == 8
    assert {entry.trade_date.isoformat() for entry in snapshot.ledger_entries} == {"2025-12-01", "2026-03-31", "2026-04-01"}
    assert any(entry.entry_type == "DIVIDEND" and entry.trade_date.isoformat() == "2026-03-31" for entry in snapshot.ledger_entries)
    assert any(entry.entry_type == "WITHHOLDING_TAX" and entry.trade_date.isoformat() == "2026-04-01" for entry in snapshot.ledger_entries)


def test_import_statement_surfaces_parser_errors_for_supported_broker_pdf() -> None:
    try:
        import_statement(DOCS_DIR / "FF2026.pdf")
    except ValueError as exc:  # pragma: no cover - defensive branch for future regressions
        assert "Unsupported broker statement PDF" not in str(exc)
        raise
