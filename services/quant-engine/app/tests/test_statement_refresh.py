"""US-28.3: statement-refresh resilience — the swap-simulation meta-test.

Proves that replacing docs/IB2026.csv with a different export breaks ONLY the
documented failure surface — the pins in `statement_truths.py` (via
`diff_statement_truths`) plus the registry-coverage step for brand-new
symbols — and that every structural invariant keeps holding on the swapped
statement. Implemented as a meta-test on the truths module (the suite itself
is never broken).

The simulated refresh: one existing position's quantity changes (AMZN 10→12)
and one brand-new symbol (NEWX) appears as a position + instrument.
"""

from __future__ import annotations

from pathlib import Path

from app.importers.interactive_brokers_csv import import_statement
from app.instruments.registry import INSTRUMENT_DEFINITIONS, InstrumentRegistry
from app.tests._statement_fixtures import STATEMENT_2026_CSV_PATH
from app.tests.statement_truths import (
    IB_LEDGER_COUNTS,
    REFRESH_WORKFLOW_DOC,
    diff_statement_truths,
)

_NEW_SYMBOL = "NEWX"
_NEW_POSITION_ROW = f"Open Positions,Data,Summary,Stocks,USD,{_NEW_SYMBOL},5,1,10,50,12,60,10,\n"
_NEW_INSTRUMENT_ROW = (
    f"Financial Instrument Information,Data,Stocks,{_NEW_SYMBOL},NEWX HOLDINGS CORP,999999,"
    f"US0000000009,{_NEW_SYMBOL},NASDAQ,1,COMMON,\n"
)
_AMZN_ROW_PREFIX = "Open Positions,Data,Summary,Stocks,USD,AMZN,10,"
_INSTRUMENT_ANCHOR = "Financial Instrument Information,Data,Stocks,AAPL,"


def _swapped_statement(tmp_path: Path) -> Path:
    text = STATEMENT_2026_CSV_PATH.read_text(encoding="utf-8-sig")
    assert _AMZN_ROW_PREFIX in text and _INSTRUMENT_ANCHOR in text
    text = text.replace(_AMZN_ROW_PREFIX, "Open Positions,Data,Summary,Stocks,USD,AMZN,12,", 1)
    text = text.replace(_AMZN_ROW_PREFIX.rsplit("AMZN", 1)[0] + "ADBE,", _NEW_POSITION_ROW + _AMZN_ROW_PREFIX.rsplit("AMZN", 1)[0] + "ADBE,", 1)
    text = text.replace(_INSTRUMENT_ANCHOR, _NEW_INSTRUMENT_ROW + _INSTRUMENT_ANCHOR, 1)
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
    assert "position count" in labels            # 20 → 21 (NEWX added)
    assert "positions by currency" in labels     # USD 16 → 17
    assert "instrument count" in labels          # 65 → 66
    assert "pinned position AMZN.quantity" in labels  # 10 → 12
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
