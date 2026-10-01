"""Freedom24 ledger dating and single-charge commission (US-46.2, findings F1 + F7).

Importer-level regression tests. The dashboard-replay values that follow from
these dates (window 2026-03-31..2026-04-10, TWR 3.81%, ...) need the recaptured
frozen market data and are pinned by the golden-dependent lane, not here.

Expected values are the statement's own numbers (FF2026.pdf: three orders on
2026-04-07 with fees 2.56 / 2.12 / 2.08, ending cash 52.04), not engine output.
"""
from __future__ import annotations

import inspect
from datetime import date

import pytest

import app.importers.freedom24 as freedom24
from app.importers.freedom24 import _PAGE_TRANSACTIONS, _parse_cash_movements, _parse_transactions, import_statement
from app.tests._statement_fixtures import FREEDOM24_PATH

TRADE_DATE = "2026-04-07"
SETTLEMENT_DATE = "2026-04-08"
EXPECTED_FEES = {"SCHD": 2.56, "VTI": 2.12, "VWO": 2.08}
STATEMENT_START_MONTH_FABRICATION = "2025-12-01"


@pytest.fixture(scope="module")
def snapshot():
    return import_statement(FREEDOM24_PATH)


def _trades(snapshot):
    return [e for e in snapshot.ledger_entries if e.entry_type in {"BUY", "SELL"}]


# ── AC 1-2: dates are the statement's own ───────────────────────────────────


def test_trades_are_dated_by_trade_date_not_settlement(snapshot) -> None:
    assert {(e.symbol, e.entry_type, e.trade_date.isoformat()) for e in _trades(snapshot)} == {
        ("SCHD", "SELL", TRADE_DATE),
        ("VTI", "BUY", TRADE_DATE),
        ("VWO", "SELL", TRADE_DATE),
    }
    assert SETTLEMENT_DATE not in {e.trade_date.isoformat() for e in snapshot.ledger_entries}


def test_no_ledger_entry_carries_a_date_the_statement_does_not_state(snapshot) -> None:
    dates = {e.trade_date.isoformat() for e in snapshot.ledger_entries}

    assert dates == {"2026-03-31", "2026-04-01", TRADE_DATE}
    assert STATEMENT_START_MONTH_FABRICATION not in dates
    # every entry sits inside the statement period the header states
    start, end = snapshot.statement.statement_period.split(" - ")
    assert all(start <= d <= end for d in dates)


# ── AC 4-5: commission charged once ─────────────────────────────────────────


def test_each_commission_sits_on_its_trade_row_dated_to_the_trade(snapshot) -> None:
    fees = {e.symbol: e.fee for e in _trades(snapshot)}

    assert fees == pytest.approx(EXPECTED_FEES)
    for entry in _trades(snapshot):
        assert entry.trade_date.isoformat() == TRADE_DATE
        # commission is inside the trade's net amount exactly once: net = gross - fee
        assert entry.net_amount == pytest.approx(entry.gross_amount - entry.fee)


def test_no_period_fee_row_exists_so_total_commission_is_6_76_not_13_52(snapshot) -> None:
    assert [e for e in snapshot.ledger_entries if e.entry_type == "FEE"] == []
    charged = sum(e.fee or 0.0 for e in snapshot.ledger_entries)

    assert round(charged, 2) == 6.76


def test_ledger_cash_rolls_forward_to_the_statement_ending_cash(snapshot) -> None:
    """AC 5: 911.23 - 861.08 - 6.76 + 8.65 = 52.04 (it was 45.28 while the fee was charged twice)."""
    usd = next(b for b in snapshot.cash_balances if b.currency == "USD")
    rolled = usd.starting_cash + sum(e.net_amount for e in snapshot.ledger_entries if e.currency == "USD")

    assert round(rolled, 2) == 52.04
    assert round(usd.ending_cash, 2) == 52.04
    assert round(usd.starting_cash, 2) == 911.23


# ── AC 3: unparseable trade date drops the record - no substitute date ───────


def _record(ticker: str, direction: str, quantity: str, price: str, amount: str, fee: str, trade_cell: str, settlement: str = SETTLEMENT_DATE) -> list[str]:
    """One 12-line Transactions record: +3 direction, +4..+8 numbers, +9 trade date cell, +10 settlement, +11 order id."""
    return [ticker, "ISIN", "USD", direction, quantity, price, amount, "0.00", fee, trade_cell, settlement, "638027902/1"]


def _page(records: list[list[str]]) -> list[str]:
    pages = ["" for _ in range(_PAGE_TRANSACTIONS + 1)]
    pages[_PAGE_TRANSACTIONS] = "\n".join(["filler"] * 13 + [line for record in records for line in record])
    return pages


def test_synthetic_record_is_dated_by_its_trade_cell_and_ignores_settlement() -> None:
    entries = _parse_transactions(_page([_record("AAA.US", "Sell", "2", "10.00", "20.00", "1.00", "2026-04-07 16:35:44", "2026-04-09")]))

    assert [(e.symbol, e.trade_date, e.fee, e.net_amount) for e in entries] == [("AAA", date(2026, 4, 7), 1.0, 19.0)]


@pytest.mark.parametrize(
    "bad_cell",
    ["not-a-date", "", "07.04.2026 16:35:44", "2026-04-0", "2026-13-45 10:00:00"],
    ids=["text", "empty", "wrong-format", "truncated", "impossible-calendar-date"],
)
def test_record_with_an_unparseable_trade_date_is_dropped_and_the_rest_imports(bad_cell) -> None:
    good_before = _record("AAA.US", "Buy", "1", "10.00", "10.00", "1.00", "2026-03-31 09:30:00")
    bad = _record("BBB.US", "Sell", "1", "10.00", "10.00", "1.00", bad_cell)
    good_after = _record("CCC.US", "Sell", "1", "10.00", "10.00", "1.00", "2026-04-07 16:35:44")

    entries = _parse_transactions(_page([good_before, bad, good_after]))

    assert [(e.symbol, e.trade_date) for e in entries] == [("AAA", date(2026, 3, 31)), ("CCC", date(2026, 4, 7))]
    # no substitute date: nothing anywhere is dated from a constant or the settlement column
    assert not {date(2026, 1, 1), date(2025, 12, 1), date(2026, 4, 8)} & {e.trade_date for e in entries}


def test_a_page_of_only_bad_dates_yields_no_entries_rather_than_synthetic_ones() -> None:
    assert _parse_transactions(_page([_record("AAA.US", "Buy", "1", "10.00", "10.00", "1.00", "n/a")])) == []


# ── guard: the fallback date machinery does not come back ─────────────────────


def test_no_synthetic_date_or_period_commission_machinery_remains() -> None:
    for name in ("_statement_grouped_date", "GROUPED_ENTRY_DAY", "_parse_commissions"):
        assert not hasattr(freedom24, name), f"{name} re-introduces a fabricated ledger date or a second commission charge"
    for parser in (_parse_transactions, _parse_cash_movements):
        assert list(inspect.signature(parser).parameters) == ["page_texts"]
