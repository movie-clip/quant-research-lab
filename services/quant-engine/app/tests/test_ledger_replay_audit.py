"""Epic 31 — regression pins for the imported ledger-replay findings F-1..F-5.

Originally authored by US-31.1 to pin **known-WRONG** behaviour so each defect
stayed reproducible for whoever picked up the fix. **All five findings are now
resolved** (US-31.2 → F-1, US-31.4 → F-5, US-31.5 → F-4, US-31.3 → F-2/F-3), so
every pin has been *inverted*: each one now asserts the corrected behaviour and
fails if the defect returns.

Each test keeps the finding's history in its docstring — including the numbers
as they moved while upstream fixes landed — because F-1..F-5 were one causal
chain and the magnitudes only make sense in that order.

All numbers come from the **frozen** `app/scripts/golden_market_data.json`
(deterministic, network-free), so these are not local FMP-cache artifacts.

See `docs/product/prd/epic-31-ledger-replay-correctness.md` F-1..F-5.
"""
from __future__ import annotations

import pytest

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


def test_f2_opening_cash_anchor_is_disclosed_not_silently_plugged(replay_context) -> None:
    """F-2 (Critical) — **RESOLVED by US-31.3** (disclosed, per the owner's
    fail-closed decision).

    `base_cash = starting_nav - opening_positions_value` still absorbs a
    residual, because the two terms are dated differently: `starting_nav` is as
    of the statement-period start (2026-01-01) while the positions are valued at
    the replay window start (2026-01-08). The replay cannot value the
    period-start date (no prices exist before the window), so the residual is an
    irreducible information gap — it is now MEASURED and DISCLOSED with an
    explicit trust level instead of riding silently at full confidence.
    """
    from app.analytics.performance import build_replay_currency_context

    snapshot, price_histories, valuation_dates = replay_context
    fund_currencies, fx_history = build_replay_currency_context(
        snapshot, replay_symbol_universe(snapshot), valuation_dates
    )
    engine = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=(snapshot.statement.base_currency or "USD"),
        fx_history=fx_history,
        symbol_fund_currencies=fund_currencies,
    )
    engine.build_daily_states(
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        apply_terminal_reconciliation=False,
    )
    anchor = engine.cash_anchor

    assert anchor is not None, "F-2 has regressed — the anchor is undisclosed again"
    assert anchor.trust == "degraded", "a date-mismatched anchor must never claim verified"
    assert anchor.basis == "statement_nav_date_mismatch"
    assert anchor.nav_as_of == "2026-01-01" and anchor.window_start == "2026-01-08"
    # The residual is the market move between those two dates.
    assert anchor.residual == pytest.approx(-1_196.61, abs=2.0)


def test_f3_terminal_reconciliation_is_never_published_as_a_return(replay_context) -> None:
    """F-3 (High) — **RESOLVED by US-31.3**.

    `_reconcile_terminal_state_to_statement_totals` still snaps the final state's
    value to the statement's ending NAV (that is correct — it IS the broker's
    number), but the correction is now RECORDED as
    `reconciliation_adjustment` and the affected day's return is WITHHELD
    instead of published as performance.

    History of the magnitude, since it moved as each upstream finding was fixed:
    US-31.1 recorded −36.34%; US-31.2 (F-1) took it to −2.56%; US-31.4 (F-5)
    flipped its sign to +2.77%; post-US-31.5 (F-4) it is +2.95% against an
    un-reconciled +1.00%. The sign-dependence is exactly why this story was
    ordered last — and why the fix is to withhold rather than to chase a
    "correct" value for a day whose value was overwritten.
    """
    from app.analytics.performance import build_replay_currency_context
    from app.analytics.risk import _portfolio_time_weighted_return_series

    snapshot, price_histories, valuation_dates = replay_context
    fund_currencies, fx_history = build_replay_currency_context(
        snapshot, replay_symbol_universe(snapshot), valuation_dates
    )
    engine = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=(snapshot.statement.base_currency or "USD"),
        fx_history=fx_history,
        symbol_fund_currencies=fund_currencies,
    )
    states = engine.build_daily_states(
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        apply_terminal_reconciliation=True,
    )

    terminal = states[-1]
    # The adjustment is recorded, not hidden...
    assert terminal.reconciliation_adjustment == pytest.approx(1_197.88, abs=2.0)
    # ...and the day it lands on publishes NO return.
    assert terminal.return_is_publishable is False
    series_dates = [d for d, _ in _portfolio_time_weighted_return_series(states)]
    assert terminal.date not in series_dates, (
        "F-3 has regressed — an accounting adjustment is being published as a return"
    )


# ── F-4 / F-5 (recorded 2026-07-24, US-31.4 / US-31.5) ──────────────────────
#
# These pin KNOWN-WRONG behaviour found while re-measuring F-2/F-3 for US-31.3.
# Both are network-free: resolution candidates are pure, and the price series
# come from the frozen fixture.


def test_f5_semi_resolves_to_held_line_not_bare_us_ticker(replay_context) -> None:
    """F-5 (High) — **RESOLVED by US-31.4**.

    `SEMI` is the LSE UCITS line *iShares MSCI Global Semiconductors*
    (ISIN IE000I8KRLL9, GBP, statement close 17.998). The rule used to carry a
    bare `SEMI` fallback; when `SEMI.L` was unavailable on FMP it fell through
    to the bare US-listed `SEMI` — a different security quoting 40.58 (2.2547×),
    overstating the holding by $2,506.93.

    The bare candidate is now removed (mirroring CIBR/DFND). `SEMI.L` resolves
    via the yfinance fallback to the held fund's GBP line, so the replayed
    terminal value is the correct-fund 150 × 17.998 = $2,699.70 (GBP,
    unconverted — the F-4 residual US-31.5 owns), never the wrong-fund
    $6,087.00. This pin is inverted: it fails if the bare fallback returns.
    """
    from app.core.symbols import resolve_symbol_candidates

    snapshot, price_histories, _valuation_dates = replay_context

    assert resolve_symbol_candidates("SEMI", None, kind="history") == ["SEMI.L"], (
        "F-5 has regressed — SEMI carries a bare fallback again (contrast CIBR)"
    )

    position = next(p for p in snapshot.positions if p.symbol == "SEMI")
    rows = price_histories.get("SEMI") or []
    assert rows, "frozen fixture lost SEMI — re-capture"
    quote = max(rows, key=lambda row: row["date"])["price"]

    # The served quote is now the held GBP line, matching the statement close.
    assert quote == pytest.approx(position.close_price, rel=0.001)
    assert position.quantity * quote == pytest.approx(2_699.70, abs=1.0)


def test_f4_resolved_by_fund_currency_conversion(replay_context) -> None:
    """F-4 (High) — **RESOLVED by US-31.5**.

    The replay used to carry every value unconverted (`fx_history={}`), and a
    blanket `position.currency` conversion would have been wrong: the provider's
    quote currency varies per resolved line. It now converts each holding by its
    FUND currency (registry) using the statement's implied rates, so:
      - DEFS (`DEFS.L` quotes USD): the fetched series is already in base and is
        NOT converted — the raw ratio ≈ EURUSD stands as the proof it was USD.
      - SXRV (`SXRV.DE` quotes EUR) and SEMI (`SEMI.L` quotes GBP): converted.
    The end-to-end reconciliation is pinned in
    `test_portfolio_state.py::test_ib2026_terminal_market_value_reconciles_to_statement`;
    here we pin the underlying per-line currency basis that makes it correct.
    """
    from app.analytics.performance import build_replay_currency_context
    from app.engine.portfolio_state import replay_symbol_universe

    snapshot, price_histories, valuation_dates = replay_context
    totals = snapshot.statement_totals
    assert totals is not None and totals.fx_rates

    def raw_ratio(symbol: str) -> float:
        position = next(p for p in snapshot.positions if p.symbol == symbol)
        rows = price_histories.get(symbol) or []
        assert rows, f"frozen fixture lost {symbol} — re-capture"
        return max(rows, key=lambda row: row["date"])["price"] / position.close_price

    eurusd = totals.fx_rates["EURUSD"]
    # The raw fetched series still show the per-line quote currency:
    assert raw_ratio("DEFS") == pytest.approx(eurusd, abs=0.01)  # DEFS.L quotes USD
    assert raw_ratio("SXRV") == pytest.approx(1.0, abs=0.01)     # SXRV.DE quotes EUR
    assert raw_ratio("SEMI") == pytest.approx(1.0, abs=0.01)     # SEMI.L quotes GBP

    # The fix reads the FUND currency (registry), which resolves the ambiguity:
    fund_currencies, _fx = build_replay_currency_context(
        snapshot, replay_symbol_universe(snapshot), valuation_dates
    )
    assert fund_currencies["DEFS"] == "USD"  # NOT the EUR listing → not converted
    assert fund_currencies["SXRV"] == "EUR"  # converted
    assert fund_currencies["SEMI"] == "GBP"  # converted


# ── US-24.9 (Epic 24): the trade-neutral market-value basis ─────────────────
#
# Not an Epic 31 finding, but pinned in this module because it measures the
# same IB2026 replay against the same frozen fixture, and the numbers only make
# sense next to the F-1..F-5 history above.


def _us249_states(replay_context):
    from app.analytics.performance import build_replay_currency_context

    snapshot, price_histories, valuation_dates = replay_context
    fund_currencies, fx_history = build_replay_currency_context(
        snapshot, replay_symbol_universe(snapshot), valuation_dates
    )
    engine = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=(snapshot.statement.base_currency or "USD"),
        fx_history=fx_history,
        symbol_fund_currencies=fund_currencies,
    )
    return engine.build_daily_states(
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        apply_terminal_reconciliation=True,
    )


def test_us249_trade_neutral_basis_publishes_no_trade_day_fabrication(replay_context) -> None:
    """US-24.9 AC4 — the guard the third basis exists for.

    2026-04-14 is the window's largest trade day ($6,916.09 of net buying into
    the priced book). The plain market-value chain reads that injection as
    performance — **+15.43%**, the F-1 fabrication class. The trade-neutral
    chain removes the leg and reports the day's actual move, **+2.37%**.

    (Figures restated by US-24.10, which gave BTEC/IUFS/IUHC a trade-price
    valuation; before that they were worth $0, which shifted every total they
    touched. The naive-vs-neutral gap — what this pin guards — is unchanged
    in character.)

    (US-30.5c cited 2026-06-19 for this class. That date is no longer a
    valuation date on the current statement window — it is a US market holiday,
    so the frozen SPY series has no row for it and the replay never values it.
    2026-04-14 is the live equivalent.)
    """
    from app.analytics.risk import _portfolio_time_weighted_return_series

    states = _us249_states(replay_context)
    naive = dict(_portfolio_time_weighted_return_series(states, basis="market_value"))
    neutral = dict(_portfolio_time_weighted_return_series(states, basis="market_value_trade_neutral"))

    assert naive["2026-04-14"] == pytest.approx(0.154319, abs=1e-4)
    assert neutral["2026-04-14"] == pytest.approx(0.023692, abs=1e-4)
    # No day in the whole window may show a trade-sized move under the shipped
    # basis: the naive chain peaks at 15.43%, the trade-neutral chain at 2.95%.
    assert max(abs(r) for r in neutral.values()) == pytest.approx(0.029539, abs=1e-4)


def test_us249_trade_leg_gate_excludes_legs_absent_from_market_value(replay_context) -> None:
    """US-24.9's fabrication guard, restated on IB2026 after US-24.10.

    `trade_flow` may only cancel a leg that actually crossed the market-value
    boundary. When US-24.9 shipped, IB2026 exercised this through **unpriced**
    symbols: selling IUFS + IUHC ($5,341.92) on 2026-04-27 moved no market value
    at all, and counting it fabricated **+9.43%** on a day the priced book moved
    +0.02%. US-24.10 then gave those symbols a trade-price valuation, so that
    case no longer arises here — but a second one does, and it is the live
    regression guard now:

    **2026-06-11 IITU is bought AND fully sold on the same day.** It is in no
    day's market value — not today's (quantity nets to zero before any close)
    and not yesterday's (it did not exist). Counting its $1,443.00 buy leg
    produced **−3.45%** against an expected **−0.36%**.
    """
    from app.analytics.risk import _portfolio_time_weighted_return_series

    states = _us249_states(replay_context)
    by_date = {state.date: state for state in states}
    neutral = dict(_portfolio_time_weighted_return_series(states, basis="market_value_trade_neutral"))

    # The same-day round trip contributes nothing to the neutralisation...
    assert by_date["2026-06-11"].trade_flow == pytest.approx(-3_524.27, abs=1.0)
    # ...so the day reports the priced book's real move, not a trade-sized one.
    assert neutral["2026-06-11"] == pytest.approx(-0.003427, abs=1e-4)

    # And the 2026-04-27 sale, now backed by a trade-price valuation, IS
    # neutralised — its leg genuinely left yesterday's market value.
    assert by_date["2026-04-27"].trade_flow == pytest.approx(-5_341.92, abs=1.0)
    assert neutral["2026-04-27"] == pytest.approx(-0.001189, abs=1e-4)


def test_us249_de_dilution_is_explained_by_the_cash_weight(replay_context) -> None:
    """US-24.9 AC9 — the tripwire: the risk statistics must move by what the
    cash sleeve explains, and no more.

    Measured on IB2026 over **every** day of the window. When US-24.9 shipped
    this comparison had to exclude 2026-04-08 and 2026-04-27, whose
    cash-inclusive TWR was corrupted by unpriced-symbol cash events; US-24.10
    fixed that at source, so no exclusions remain:

        annualised volatility   TWR 14.72%  ->  trade-neutral 15.71%   (x1.067)
        median cash weight      5.21%       ->  predicted de-dilution  x1.055

    A ratio far from the cash-weight prediction means the trade neutralisation
    is wrong, not that the portfolio is riskier.
    """
    import statistics

    from app.analytics.risk import _portfolio_time_weighted_return_series

    states = _us249_states(replay_context)
    base = "USD"

    weights = [s.cash[base] / s.total_portfolio_value for s in states if s.total_portfolio_value]
    median_weight = statistics.median(weights)
    assert median_weight == pytest.approx(0.052, abs=0.005)

    def _vol(basis: str) -> float:
        series = _portfolio_time_weighted_return_series(states, basis=basis)
        return statistics.stdev([r for _, r in series]) * (252 ** 0.5)

    twr_vol = _vol("portfolio_value")
    neutral_vol = _vol("market_value_trade_neutral")

    assert twr_vol == pytest.approx(0.1472, abs=1e-3)
    assert neutral_vol == pytest.approx(0.1571, abs=1e-3)
    # The whole move is the cash weight: ratio close to 1/(1 - median weight).
    assert neutral_vol / twr_vol == pytest.approx(1 / (1 - median_weight), rel=0.02)


# ── US-24.10: the trade-price valuation tier ───────────────────────────


def test_us2410_trade_price_anchor_removes_the_fabricated_twr_days(replay_context) -> None:
    """US-24.10 AC4 — the defect this story exists for.

    BTEC / IUFS / IUHC have no market history and no statement close (they are
    round trips, absent from the current snapshot), so they were valued at $0.
    Their trades still moved real cash, so `total_portfolio_value` stepped with
    no offsetting position and the INVESTOR-PERFORMANCE TWR published it:

        2026-04-08  −$5,092.82 of buying   ->  TWR  −7.90%
        2026-04-27  +$5,341.92 of selling  ->  TWR  +9.61%

    Valued at the broker's own execution price, both become ordinary days.
    """
    from app.analytics.risk import _portfolio_time_weighted_return_series

    states = _us249_states(replay_context)
    twr = dict(_portfolio_time_weighted_return_series(states, basis="portfolio_value"))

    assert twr["2026-04-08"] == pytest.approx(0.025412, abs=1e-4)
    assert twr["2026-04-27"] == pytest.approx(-0.001210, abs=1e-4)
    # Nowhere near the fabricated values.
    assert abs(twr["2026-04-08"] - (-0.0790)) > 0.05
    assert abs(twr["2026-04-27"] - 0.0961) > 0.05
    # The window's largest TWR day falls from 9.61% to 2.76%.
    assert max(abs(r) for r in twr.values()) == pytest.approx(0.027618, abs=1e-4)


def test_us2410_symbols_move_from_unpriced_into_the_trade_anchored_tier(replay_context) -> None:
    """US-24.10 AC5/AC6 — reclassification is real, and exclusive."""
    from app.analytics.performance import build_replay_currency_context

    snapshot, price_histories, valuation_dates = replay_context
    fund_currencies, fx_history = build_replay_currency_context(
        snapshot, replay_symbol_universe(snapshot), valuation_dates
    )
    engine = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=(snapshot.statement.base_currency or "USD"),
        fx_history=fx_history,
        symbol_fund_currencies=fund_currencies,
    )
    engine.build_daily_states(
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        apply_terminal_reconciliation=True,
    )

    assert engine.trade_price_anchored_symbols == {"BTEC", "IUFS", "IUHC"}
    # Every held symbol is now valued on some basis...
    assert engine.unpriced_replay_symbols == set()
    # ...and LQQ keeps its statement-close anchor (US-27.7 unchanged).
    assert engine.statement_anchored_symbols == {"LQQ"}
    assert not (engine.trade_price_anchored_symbols & engine.statement_anchored_symbols)


def test_us2410_terminal_reconciliation_does_not_worsen(replay_context) -> None:
    """US-24.10 AC9 — a valuation change must not degrade the statement match.

    US-31.5 brought terminal market value to within $1.35 of the statement's own
    `stock_total` ($61,238.53). All three newly-valued symbols are closed by
    period end, so the terminal state must be untouched.
    """
    states = _us249_states(replay_context)

    assert states[-1].total_market_value == pytest.approx(61_239.88, abs=1.0)
    assert abs(states[-1].total_market_value - 61_238.53) < 2.0
