"""Epic 31 / US-31.1 — reproduction pins for the imported ledger-replay defects.

These tests **document current, known-WRONG behaviour**. They are not
assertions that the engine is correct; they exist so that:

  1. the F-1..F-3 findings stay reproducible for whoever picks up the fixes, and
  2. a future fix has to flip them *deliberately* rather than surprising someone
     with an unexplained failure.

Each test names the finding it pins, the expected post-fix behaviour, and the
story that will change it (the US-27 "documented defect" convention).

All numbers come from the **frozen** `app/scripts/golden_market_data.json`
(deterministic, network-free), so these are not local FMP-cache artifacts.

See `docs/product/prd/epic-31-ledger-replay-correctness.md` F-1..F-3.
"""
from __future__ import annotations

import pytest

from app.domain.ledger import snapshot_to_ledger
from app.engine.portfolio_state import PortfolioStateEngine
from app.scripts.export_dashboard_goldens import _docs_statement_path, _repo_root
from app.scripts.frozen_market_data import FrozenMarketData
from app.services.statement_importer import import_statements


@pytest.fixture(scope="module")
def replay_context():
    """Imported IB2026 snapshot + frozen price history + valuation dates."""
    root = _repo_root()
    snapshot = import_statements(
        [str(_docs_statement_path(root, "IB2026.csv", "IB2026.pdf", "2026.pdf"))]
    )
    market_data = FrozenMarketData.from_file()

    history_dates = [e.trade_date.isoformat() for e in snapshot.ledger_entries if e.trade_date]
    history_dates += [p.as_of_date.isoformat() for p in snapshot.positions if p.as_of_date]
    start, end = min(history_dates), max(history_dates)

    benchmark_rows = market_data.get_historical_prices("SPY", start, end)
    valuation_dates = sorted({row["date"] for row in benchmark_rows})
    price_histories = market_data.get_historical_prices_for_symbols(
        [p.symbol for p in snapshot.positions], start, end
    )
    return snapshot, price_histories, valuation_dates


def _build_states(snapshot, price_histories, valuation_dates, *, reconcile: bool):
    engine = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=(snapshot.statement.base_currency or "USD"),
        fx_history={},
    )
    return engine.build_daily_states(
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        apply_terminal_reconciliation=reconcile,
    )


def test_f1_opening_positions_are_largely_unpriced(replay_context) -> None:
    """PINS F-1 (Critical) — KNOWN WRONG.

    Price history is fetched for the snapshot's *current* holdings, but the
    replay reconstructs *opening* positions by rolling back BUY/SELL, so every
    since-sold symbol has no price rows at all and contributes $0 to opening
    market value.

    Expected AFTER the fix (US-31.2): every reconstructed opening position is
    priced (or its absence is explicitly disclosed), and this test flips to
    asserting `unpriced == 0`.
    """
    snapshot, price_histories, valuation_dates = replay_context
    states = _build_states(snapshot, price_histories, valuation_dates, reconcile=False)
    day_one = states[0]

    unpriced = [p.symbol for p in day_one.positions if p.market_value is None]

    # Current behaviour: the majority of reconstructed opening positions are unpriced.
    assert unpriced, "F-1 appears fixed — update this pin and see US-31.2"
    assert len(unpriced) > len(day_one.positions) / 2, (
        f"F-1 pin: expected most opening positions unpriced, got "
        f"{len(unpriced)}/{len(day_one.positions)}"
    )
    # The snapshot holds far fewer symbols today than the replay reconstructs.
    assert len(day_one.positions) > len(snapshot.positions)


def test_f2_opening_cash_absorbs_the_valuation_error(replay_context) -> None:
    """PINS F-2 (Critical) — KNOWN WRONG.

    `base_cash = starting_nav - opening_positions_value` makes cash a plug: the
    F-1 undervaluation is absorbed into opening cash and rides every daily
    state, with no disclosure and no fail-closed.

    Expected AFTER the fix (US-31.3): opening cash reconciles to the
    statement-implied opening cash within a documented tolerance, or the
    degradation is surfaced with an explicit trust level.
    """
    snapshot, price_histories, valuation_dates = replay_context
    states = _build_states(snapshot, price_histories, valuation_dates, reconcile=False)

    totals = snapshot.statement_totals
    assert totals is not None and totals.cash_total is not None

    net_window_flow = sum(e.cash_effect or 0.0 for e in snapshot_to_ledger(snapshot))
    implied_opening_cash = totals.cash_total - net_window_flow
    engine_opening_cash = states[0].cash[snapshot.statement.base_currency or "USD"]

    drift = engine_opening_cash - implied_opening_cash

    # Current behaviour: a large, undisclosed drift.
    assert abs(drift) > 1_000.0, (
        f"F-2 appears fixed (drift={drift:,.2f}) — update this pin and see US-31.3"
    )


def test_f3_terminal_reconciliation_is_published_as_a_return(replay_context) -> None:
    """PINS F-3 (High) — KNOWN WRONG.

    `_reconcile_terminal_state_to_statement_totals` corrects the whole
    accumulated drift on the final day, and the return series reads that
    accounting adjustment as performance.

    Expected AFTER the fix (US-31.3): the reconciliation is disclosed,
    distributed, or fails closed — never published as a single-day return. This
    test then flips to asserting the two series' final returns agree.
    """
    snapshot, price_histories, valuation_dates = replay_context

    def final_return(*, reconcile: bool) -> float:
        states = _build_states(snapshot, price_histories, valuation_dates, reconcile=reconcile)
        previous, last = states[-2], states[-1]
        return (last.total_portfolio_value - last.external_cash_flow) / previous.total_portfolio_value - 1

    with_reconciliation = final_return(reconcile=True)
    without_reconciliation = final_return(reconcile=False)

    # Current behaviour: the adjustment dominates the final day's "return".
    assert abs(with_reconciliation - without_reconciliation) > 0.10, (
        "F-3 appears fixed — update this pin and see US-31.3 "
        f"(with={with_reconciliation:.4f}, without={without_reconciliation:.4f})"
    )
    # ...and it is a large negative move driven purely by the correction.
    assert with_reconciliation < -0.10
    assert abs(without_reconciliation) < 0.10
