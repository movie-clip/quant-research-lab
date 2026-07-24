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
from app.engine.portfolio_state import PortfolioStateEngine, replay_symbol_universe
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
    # US-31.2: mirrors what the ledger-replay callers now fetch. Before that
    # story this was `[p.symbol for p in snapshot.positions]` (current holdings
    # only) — which WAS F-1. Every pin below is therefore re-stated against
    # post-US-31.2 production behaviour; the pre-fix numbers are kept in the
    # comments so the PRD's evidence trail stays readable.
    price_histories = market_data.get_historical_prices_for_symbols(
        replay_symbol_universe(snapshot), start, end
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


def test_f1_opening_positions_are_priced(replay_context) -> None:
    """F-1 (Critical) — **RESOLVED by US-31.2**.

    Price history was fetched for the snapshot's *current* holdings while the
    replay reconstructs *opening* positions, so every since-sold symbol had no
    price rows and contributed $0 (27 of 38 unpriced on day one; opening market
    value $14,582.03 against an implied $50,116.24).

    The callers now fetch `replay_symbol_universe(snapshot)`. This pin is
    inverted accordingly — it fails if the narrow fetch ever comes back.
    """
    snapshot, price_histories, valuation_dates = replay_context
    states = _build_states(snapshot, price_histories, valuation_dates, reconcile=False)
    day_one = states[0]

    unpriced = [p.symbol for p in day_one.positions if p.market_value is None]

    assert unpriced == [], f"F-1 has regressed — opening positions unpriced: {unpriced}"
    # The replay still values more symbols than the snapshot holds today; that
    # is the reconstruction working, and is exactly why the wider fetch matters.
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

    # Still open, but US-31.2 shrank it by 96.9%: $35,534.21 → $1,097.18. The
    # residual is LQQ's statement-close anchor (a held symbol with no fetchable
    # history), NOT the since-sold gap F-1 described.
    assert abs(drift) == pytest.approx(1_097.18, abs=1.0), (
        f"F-2 drift moved (drift={drift:,.2f}) — re-check before US-31.3"
    )


def test_f3_terminal_reconciliation_is_published_as_a_return(replay_context) -> None:
    """PINS F-3 (High) — KNOWN WRONG.

    `_reconcile_terminal_state_to_statement_totals` corrects the whole
    accumulated drift on the final day, and the return series reads that
    accounting adjustment as performance.

    Expected AFTER the fix (US-31.3): the reconciliation is disclosed,
    distributed, or fails closed — never published as a single-day return. This
    test then flips to asserting the two series' final returns agree.

    **US-31.2 materially re-scoped this finding.** The adjustment was never an
    independent defect — it is the accumulated F-1/F-2 error snapping out on the
    last day. With opening positions priced, the fabricated terminal return fell
    from **−36.34% to −2.56%**, and its annualised-volatility inflation from
    **+79% (36.21% → 64.82%) to +1.1% (23.65% → 23.91%)**. US-31.3 remains
    necessary on principle — publishing ANY accounting adjustment as a return
    violates guardrail #3 — but its magnitude is now small, not Critical.
    """
    snapshot, price_histories, valuation_dates = replay_context

    def final_return(*, reconcile: bool) -> float:
        states = _build_states(snapshot, price_histories, valuation_dates, reconcile=reconcile)
        previous, last = states[-2], states[-1]
        return (last.total_portfolio_value - last.external_cash_flow) / previous.total_portfolio_value - 1

    with_reconciliation = final_return(reconcile=True)
    without_reconciliation = final_return(reconcile=False)

    # Still open: the final day's "return" is still driven by the correction,
    # not by market movement — only much smaller than the PRD recorded.
    assert with_reconciliation == pytest.approx(-0.0256, abs=0.002)
    assert without_reconciliation == pytest.approx(0.0087, abs=0.002)
    assert abs(with_reconciliation - without_reconciliation) > 0.01, (
        "F-3 appears fixed — update this pin and see US-31.3 "
        f"(with={with_reconciliation:.4f}, without={without_reconciliation:.4f})"
    )
    # The correction still flips a positive day negative — that is the defect.
    assert without_reconciliation > 0 > with_reconciliation


# ── F-4 / F-5 (recorded 2026-07-24, US-31.4 / US-31.5) ──────────────────────
#
# These pin KNOWN-WRONG behaviour found while re-measuring F-2/F-3 for US-31.3.
# Both are network-free: resolution candidates are pure, and the price series
# come from the frozen fixture.


def test_f5_bare_symbol_fallback_substitutes_a_different_security(replay_context) -> None:
    """PINS F-5 (High) — KNOWN WRONG.

    `SEMI` is the LSE UCITS line *iShares MSCI Global Semiconductors*
    (ISIN IE000I8KRLL9, GBP, statement close 17.998). `SEMI.L` is unavailable on
    the current FMP plan, so `resolve_symbol_candidates` falls through to the
    bare US-listed `SEMI` — a different security quoting 40.58 (2.2547×),
    overstating the holding by $2,506.93.

    Expected AFTER the fix (US-31.4): either the venue-qualified line resolves,
    or the symbol is reported as having NO history (and disclosed via
    `unpriced_replay_symbols`) — never silently valued from another security.
    """
    from app.core.symbols import resolve_symbol_candidates

    snapshot, price_histories, _valuation_dates = replay_context

    assert resolve_symbol_candidates("SEMI", None, kind="history") == ["SEMI.L", "SEMI"], (
        "F-5 pin: SEMI still carries an unguarded bare fallback (contrast CIBR, "
        "pinned to ['CIBR.L']) — see US-31.4"
    )

    position = next(p for p in snapshot.positions if p.symbol == "SEMI")
    rows = price_histories.get("SEMI") or []
    assert rows, "frozen fixture lost SEMI — re-capture"
    quote = max(rows, key=lambda row: row["date"])["price"]

    # Current behaviour: the served quote cannot be the held line in any currency.
    assert quote / position.close_price == pytest.approx(2.2547, abs=0.01), (
        "F-5 appears fixed or changed — update this pin and see US-31.4"
    )


def test_f4_provider_quote_currency_is_not_the_position_currency(replay_context) -> None:
    """PINS F-4 (High) — KNOWN WRONG.

    The replay carries every value unconverted (`fx_history={}`), and a blanket
    `position.currency` conversion is NOT the fix: the provider's quote currency
    varies per resolved line. DEFS is held in EUR but `DEFS.L` quotes USD (ratio
    ≈ EURUSD, so converting would double-count); SXRV is held in EUR and
    `SXRV.DE` quotes EUR (ratio 1.0, so conversion IS required).

    Expected AFTER the fix (US-31.5): a per-symbol quote currency is recorded and
    conversion is applied only where the quote currency differs from the base.
    """
    snapshot, price_histories, _valuation_dates = replay_context
    totals = snapshot.statement_totals
    assert totals is not None and totals.fx_rates

    def ratio(symbol: str) -> float:
        position = next(p for p in snapshot.positions if p.symbol == symbol)
        rows = price_histories.get(symbol) or []
        assert rows, f"frozen fixture lost {symbol} — re-capture"
        return max(rows, key=lambda row: row["date"])["price"] / position.close_price

    eurusd = totals.fx_rates["EURUSD"]

    # DEFS: EUR position, USD-quoted line — already in base, must NOT be converted.
    assert ratio("DEFS") == pytest.approx(eurusd, abs=0.01)
    # SXRV: EUR position, EUR-quoted line — must be converted.
    assert ratio("SXRV") == pytest.approx(1.0, abs=0.01)
    # The two cases are indistinguishable from the snapshot alone: same currency,
    # opposite required treatment. That is precisely the F-4 gap.
    assert (
        next(p for p in snapshot.positions if p.symbol == "DEFS").currency
        == next(p for p in snapshot.positions if p.symbol == "SXRV").currency
        == "EUR"
    )
