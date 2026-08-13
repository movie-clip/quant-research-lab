"""Single source of statement-truth pins for the CURRENT IB statement (US-28.3).

Statement truths are values specific to the current broker export
(`docs/IB2026.csv`, period 2026-01-01 - 2026-06-30): symbol lists, counts,
totals. They are legitimate pins, but they change on every statement refresh —
so they live HERE and only here. Structural invariants (schema shape,
reconciliation passes, sums that derive from the snapshot's own totals) must
NOT pin values from this module; they derive expectations from the imported
snapshot itself.

Refresh workflow (see docs/architecture/testing-architecture.md, "Statement
refresh workflow"): replace docs/IB2026.csv → run
`python scripts/refresh_statement.py` → update the pins below + add registry
entries for new symbols → commit the statement, goldens, fixture, and this
module together.

Audit note (US-28.3): `test_importer.py`'s IB2026.pdf pins are scoped to the
frozen legacy PDF fixture (the refresh flow replaces only the CSV since
US-28.2), so they are stable-fixture pins like FF2026/ESPP — not refresh
casualties — and intentionally stay in place.
"""

from __future__ import annotations

from app.schemas.imports import ImportedPortfolioSnapshot


REFRESH_WORKFLOW_DOC = "docs/architecture/testing-architecture.md#statement-refresh-workflow"

# ── Statement identity (period 2026-01-01 - 2026-08-11) ──────────────────────
IB_ACCOUNT_ID = "U8516450"  # stable across refreshes (same account)
IB_STATEMENT_PERIOD = "2026-01-01 - 2026-08-11"
IB_BASE_CURRENCY = "USD"

# ── Portfolio composition ─────────────────────────────────────────────────────
IB_POSITION_COUNT = 18
IB_POSITIONS_BY_CURRENCY = {"USD": 15, "EUR": 2, "GBP": 1}
IB_INSTRUMENT_COUNT = 70
# Symbols the ledger replay may need a price for: current holdings ∪ every
# BUY/SELL symbol (US-31.2). Re-homed here by US-33.4 — it moves on every
# refresh, so `test_portfolio_state.py` must not pin it inline.
IB_REPLAY_UNIVERSE_SIZE = 68

# One pinned position per statement currency (full row precision).
IB_PINNED_POSITIONS = {
    "DEFS": {"currency": "EUR", "quantity": 500, "cost_basis": 2796.475015, "close_price": 6.496, "market_value": 3248.0, "unrealized_pnl": 451.524985},
    "SEMI": {"currency": "GBP", "quantity": 200, "market_value": 2929.2, "unrealized_pnl": 166.2},
    # USD pin was AMZN until the 2026-08-11 refresh, which sold it in full
    # (it now appears in IB_ABSENT_SYMBOLS). VUAA is the replacement: a large,
    # long-held USD line, so the pin stays meaningful across refreshes.
    "VUAA": {"currency": "USD", "quantity": 80, "cost_basis": 10081.463136, "market_value": 11964.8},
}

# Two pinned instruments proving ISIN/exchange/type flow (AC4 of US-28.1).
IB_PINNED_INSTRUMENTS = {
    "AAPL": {"description": "APPLE INC", "isin": "US0378331005", "listing_exchange": "NASDAQ", "instrument_type": "COMMON"},
    "CIBR": {"isin": "IE00BF16M727", "listing_exchange": "LSEETF", "instrument_type": "ETF"},
}

# ── Ledger ────────────────────────────────────────────────────────────────────
IB_LEDGER_COUNTS = {
    "BUY": 92,
    "SELL": 77,
    "DIVIDEND": 25,
    "WITHHOLDING_TAX": 28,
    "INTEREST": 1,
    "FEE": 5,
    "DEPOSIT": 1,
}

# ── Statement totals (the statement's own Change in NAV / NAV numbers,
#    stored per the schema's absolute-value convention) ───────────────────────
IB_TOTALS_2DP = {
    "starting_nav": 52381.12,
    "ending_nav": 65429.98,
    "cash_total": 507.00,
    "stock_total": 64922.99,
    "dividends_total": 125.72,
    "withholding_tax_total": 17.93,
    "interest_total": 1.64,
    "other_fees_total": 1.05,
    "commissions_total": 215.16,
    "deposits_total": 9963.00,
}
IB_TWR_PCT = 4.765666  # Time Weighted Rate of Return, 6dp

# Statement-implied FX rates (base restatement of Open Positions totals).
IB_IMPLIED_FX_4DP = {"EURUSD": 1.1543, "GBPUSD": 1.3508}

# ── Base-currency weighting (US-30.5a / audit F-7) ───────────────────────────
# Re-homed here by US-33.4: `test_currency_conversion.py` and
# `test_exposure_engine.py` hardcoded these, so the 2026-08-11 refresh failed
# five structural tests that had no business pinning statement values. The
# refresh workflow doc is explicit — anything failing outside this module on a
# refresh is a test to fix, not a number to update.
#
# The raw mixed-currency sum is the PRE-FIX number (F-7 summed currency-mixed
# numerals). It is pinned because it is the arbiter test's counter-example: it
# must never equal the converted total.
IB_RAW_MIXED_CURRENCY_SUM = 62031.85
# Per-symbol weight (%) on the base-currency denominator, 2dp.
IB_BASE_WEIGHTS_PCT = {"SEMI": 6.09, "SXRV": 15.70, "VDST": 24.70, "VUAA": 18.43}
# Position-concentration HHI on those base weights, 6dp.
IB_POSITION_HHI_BASE = 0.138194

# ── Sector-classification examples (held / sold symbols) ─────────────────────
# Held symbols expected in build_portfolio_overview sector buckets.
IB_SECTOR_EXAMPLES = {
    "Defense": ("DEFS", "IDFN"),
    "Technology": ("CIBR", "SEMI", "SXRV"),
    "Broad Market": ("VUAA",),
    "Fixed Income": ("VDST",),
}
# Not held as open positions (sold during the period or earlier); they must
# never surface in a sector bucket.
IB_ABSENT_SYMBOLS = ("FICO", "DFND", "IUIT", "IUFS", "IUHC", "AMZN")

# Exposure-engine overlap vs the deterministic StubMarketDataService benchmark
# (MSFT/AAPL): neither is currently held, so both surface as the top overlap
# deltas. Changes if a refresh adds either symbol to the holdings.
IB_TOP_OVERWEIGHTS_VS_STUB_BENCHMARK = ["MSFT", "AAPL"]


def diff_statement_truths(snapshot: ImportedPortfolioSnapshot) -> list[str]:
    """Compare an imported IB snapshot against every pin in this module.

    Returns one human-readable line per mismatch, each naming the refresh
    workflow doc — this is the ONLY place statement-truth failures should
    originate on a statement refresh (plus the registry-coverage check in
    test_registry_isin_integrity.py).
    """
    from collections import Counter

    diffs: list[str] = []

    def check(label: str, expected: object, actual: object, *, ndigits: int | None = None) -> None:
        if ndigits is not None and isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
            expected = round(float(expected), ndigits)
            actual = round(float(actual), ndigits)
        if expected != actual:
            diffs.append(
                f"{label}: expected {expected!r}, statement has {actual!r} "
                f"— update app/tests/statement_truths.py per {REFRESH_WORKFLOW_DOC}"
            )

    check("account_id", IB_ACCOUNT_ID, snapshot.statement.account_id)
    check("statement_period", IB_STATEMENT_PERIOD, snapshot.statement.statement_period)
    check("base_currency", IB_BASE_CURRENCY, snapshot.statement.base_currency)
    check("position count", IB_POSITION_COUNT, len(snapshot.positions))
    check(
        "positions by currency",
        IB_POSITIONS_BY_CURRENCY,
        dict(Counter(position.currency for position in snapshot.positions)),
    )
    check("instrument count", IB_INSTRUMENT_COUNT, len(snapshot.instruments))
    check(
        "ledger entry-type counts",
        IB_LEDGER_COUNTS,
        dict(Counter(entry.entry_type for entry in snapshot.ledger_entries)),
    )

    positions_by_symbol = {position.symbol: position for position in snapshot.positions}
    for symbol, expected_fields in IB_PINNED_POSITIONS.items():
        position = positions_by_symbol.get(symbol)
        if position is None:
            diffs.append(
                f"pinned position {symbol}: absent from statement "
                f"— update app/tests/statement_truths.py per {REFRESH_WORKFLOW_DOC}"
            )
            continue
        for field, expected in expected_fields.items():
            check(f"pinned position {symbol}.{field}", expected, getattr(position, field), ndigits=6)

    instruments_by_symbol = {instrument.symbol: instrument for instrument in snapshot.instruments}
    for symbol, expected_fields in IB_PINNED_INSTRUMENTS.items():
        instrument = instruments_by_symbol.get(symbol)
        if instrument is None:
            diffs.append(
                f"pinned instrument {symbol}: absent from statement "
                f"— update app/tests/statement_truths.py per {REFRESH_WORKFLOW_DOC}"
            )
            continue
        for field, expected in expected_fields.items():
            check(f"pinned instrument {symbol}.{field}", expected, getattr(instrument, field))

    totals = snapshot.statement_totals
    if totals is None:
        diffs.append(f"statement_totals: missing — update app/tests/statement_truths.py per {REFRESH_WORKFLOW_DOC}")
    else:
        for field, expected in IB_TOTALS_2DP.items():
            check(f"totals.{field} (2dp)", expected, getattr(totals, field), ndigits=2)
        check("totals.time_weighted_return_pct (6dp)", IB_TWR_PCT, totals.time_weighted_return_pct, ndigits=6)
        for pair, expected_rate in IB_IMPLIED_FX_4DP.items():
            check(f"fx_rates.{pair} (4dp)", expected_rate, totals.fx_rates.get(pair), ndigits=4)

    held_symbols = set(positions_by_symbol)
    for symbol in IB_ABSENT_SYMBOLS:
        if symbol in held_symbols:
            diffs.append(
                f"absent-symbol pin {symbol}: now held "
                f"— update app/tests/statement_truths.py per {REFRESH_WORKFLOW_DOC}"
            )
    for sector, symbols in IB_SECTOR_EXAMPLES.items():
        for symbol in symbols:
            if symbol not in held_symbols:
                diffs.append(
                    f"sector-example pin {symbol} ({sector}): no longer held "
                    f"— update app/tests/statement_truths.py per {REFRESH_WORKFLOW_DOC}"
                )

    return diffs
