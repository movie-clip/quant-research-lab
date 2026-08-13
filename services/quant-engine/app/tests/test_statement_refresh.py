"""US-28.3: statement-refresh resilience — the swap-simulation meta-test.

Proves that replacing docs/IB2026.csv with a different export breaks ONLY the
documented failure surface — the pins in `statement_truths.py` (via
`diff_statement_truths`) plus the registry-coverage step for brand-new
symbols — and that every structural invariant keeps holding on the swapped
statement. Implemented as a meta-test on the truths module (the suite itself
is never broken).

The simulated refresh: one existing position's quantity changes and one
brand-new symbol (NEWX) appears as a position + instrument.

US-33.4: the mutated symbol used to be hardcoded as AMZN, which the 2026-08-11
refresh sold in full — so the meta-test guarding the refresh surface was itself
a refresh casualty. Both anchors are now DERIVED from the statement under test.
"""

from __future__ import annotations

from pathlib import Path

from app.importers.interactive_brokers_csv import import_statement
from app.instruments.registry import INSTRUMENT_DEFINITIONS, InstrumentRegistry
from app.tests._statement_fixtures import STATEMENT_2026_CSV_PATH
from app.tests.statement_truths import (
    IB_LEDGER_COUNTS,
    IB_PINNED_POSITIONS,
    REFRESH_WORKFLOW_DOC,
    diff_statement_truths,
)

_NEW_SYMBOL = "NEWX"
_NEW_POSITION_ROW = f"Open Positions,Data,Summary,Stocks,USD,{_NEW_SYMBOL},5,1,10,50,12,60,10,\n"
_NEW_INSTRUMENT_ROW = (
    f"Financial Instrument Information,Data,Stocks,{_NEW_SYMBOL},NEWX HOLDINGS CORP,999999,"
    f"US0000000009,{_NEW_SYMBOL},NASDAQ,1,COMMON,\n"
)
_POSITION_ROW_PREFIX = "Open Positions,Data,Summary,Stocks,"
_INSTRUMENT_ROW_PREFIX = "Financial Instrument Information,Data,Stocks,"
_QUANTITY_FIELD = 6


def _pinned_position_row(text: str) -> str:
    """The Open Positions row of a symbol the truths module pins — derived.

    Mutating a PINNED position is what makes the diff assertion below specific
    (`pinned position X.quantity`), and deriving which one from the statement is
    what stops the next refresh invalidating this test by selling that symbol.
    """
    for line in text.splitlines():
        fields = line.split(",")
        if not line.startswith(_POSITION_ROW_PREFIX) or len(fields) <= _QUANTITY_FIELD:
            continue
        if fields[5] not in IB_PINNED_POSITIONS:
            continue
        try:
            float(fields[_QUANTITY_FIELD])
        except ValueError:
            continue
        return line
    raise AssertionError("no pinned Open Positions row found in the statement")


def _first_instrument_row(text: str) -> str:
    for line in text.splitlines():
        if line.startswith(_INSTRUMENT_ROW_PREFIX):
            return line
    raise AssertionError("no Financial Instrument Information row found")


def _swapped_statement(tmp_path: Path) -> Path:
    text = STATEMENT_2026_CSV_PATH.read_text(encoding="utf-8-sig")

    position_row = _pinned_position_row(text)
    fields = position_row.split(",")
    fields[_QUANTITY_FIELD] = str(float(fields[_QUANTITY_FIELD]) + 2)
    text = text.replace(position_row, _NEW_POSITION_ROW + ",".join(fields), 1)

    instrument_row = _first_instrument_row(text)
    text = text.replace(instrument_row, _NEW_INSTRUMENT_ROW + instrument_row, 1)

    swapped = tmp_path / "IB2026-refreshed.csv"
    swapped.write_text(text, encoding="utf-8-sig")
    return swapped


def test_swap_simulation_fails_only_the_documented_pin_surface(tmp_path: Path) -> None:
    snapshot = import_statement(_swapped_statement(tmp_path))

    # 1. Structural: the swapped statement still imports as a complete,
    #    well-formed snapshot — no structural test would crash on it.
    assert snapshot.statement.detected_format == "csv"
    assert snapshot.positions and snapshot.instruments and snapshot.ledger_entries
    for position in snapshot.positions:
        assert position.currency.isalpha() and len(position.currency) == 3

    # 2. The truths diff is exactly the documented failure surface: the pins
    #    touched by the mutation — nothing else.
    diffs = diff_statement_truths(snapshot)
    assert diffs, "a statement swap must surface truths-module diffs"
    labels = "\n".join(diffs)
    assert "position count" in labels            # NEWX added
    assert "positions by currency" in labels     # one more USD line
    assert "instrument count" in labels          # NEWX instrument added
    mutated_symbol = _pinned_position_row(
        STATEMENT_2026_CSV_PATH.read_text(encoding="utf-8-sig")
    ).split(",")[5]
    assert f"pinned position {mutated_symbol}.quantity" in labels
    # Untouched pin families produce NO diffs.
    assert "ledger entry-type counts" not in labels
    assert "totals." not in labels
    assert "fx_rates" not in labels
    assert "sector-example" not in labels

    # 3. Every diff line names the refresh workflow doc — the failure output
    #    is self-documenting.
    for line in diffs:
        assert REFRESH_WORKFLOW_DOC in line, line

    # 4. The ledger is untouched by the position swap (invariant families
    #    stay green): entry-type counts still match the truths pin.
    from collections import Counter

    assert dict(Counter(e.entry_type for e in snapshot.ledger_entries)) == IB_LEDGER_COUNTS

    # 5. Registry coverage is the one expected step outside the truths module:
    #    the brand-new symbol has no registry entry — adding one is the
    #    deliberate, reviewed step in the refresh workflow (fmp-data skill).
    registry = InstrumentRegistry()
    assert registry.normalize_symbol(_NEW_SYMBOL) not in INSTRUMENT_DEFINITIONS


def test_committed_statement_yields_zero_truths_diffs() -> None:
    # Behaviour-neutrality anchor for the meta-test: the real committed
    # statement produces an empty diff, so the swap test above measures the
    # mutation, not module drift.
    assert diff_statement_truths(import_statement(STATEMENT_2026_CSV_PATH)) == []
