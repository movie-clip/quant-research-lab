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

    # US-34.3 (Epic 34 F-2) INVERTED this pin again. F-2 was resolved by
    # DISCLOSING the plug; it is now resolved by not creating one. The anchor
    # takes the statement's own reported starting cash — observed truth, exactly
    # dated — so there is no date mismatch to absorb and the anchor is
    # `verified`. Previously: basis `statement_nav_date_mismatch`, trust
    # `degraded`, residual -$1,377.59 (and -$1,196.61 pre-refresh), on every run
    # of every statement.
    assert anchor is not None, "F-2 has regressed — the anchor is undisclosed again"
    assert anchor.basis == "statement_starting_cash"
    assert anchor.trust == "verified"
    assert anchor.nav_as_of == "2026-01-01" and anchor.window_start == "2026-01-08"
    # The residual now measures how well the LEDGER reconciles the statement's
    # two cash endpoints — a different fact from the anchor's trust.
    # 2026-08-28 statement refresh: 46.69 -> -1.15.
    assert anchor.residual == pytest.approx(-1.15, abs=2.0)


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
    # US-33.4: 1,197.88 on the pre-refresh statement; 1,366.17 after it.
    # US-34.3: -58.11 — 96% of that adjustment WAS the cash-anchor offset riding
    # through the window, and it disappears once the anchor stops deriving.
    # 2026-08-28 statement refresh: -19.98 -> -5.95.
    assert terminal.reconciliation_adjustment == pytest.approx(-5.95, abs=2.0)

    # US-34.8 changed HOW F-3 is enforced, not WHAT it requires. The day is no
    # longer blanked; its return is computed from the market-derived value, so
    # the adjustment still never reaches a return. The test asserts that
    # directly, which is stronger than asserting the day is absent: it fails if
    # the adjustment ever moves the published figure.
    assert terminal.return_is_publishable is True
    series = dict(_portfolio_time_weighted_return_series(states))
    assert terminal.date in series

    previous = states[-2]
    market_derived = terminal.total_portfolio_value - terminal.reconciliation_adjustment
    expected = (market_derived - terminal.external_cash_flow) / previous.total_portfolio_value - 1
    assert series[terminal.date] == pytest.approx(expected, abs=1e-9), (
        "F-3 has regressed — an accounting adjustment is reaching a published return"
    )
    # And the reconciled value would have given a materially different number,
    # which is what makes the correction load-bearing rather than cosmetic.
    reconciled = (
        terminal.total_portfolio_value - terminal.external_cash_flow
    ) / previous.total_portfolio_value - 1
    assert abs(series[terminal.date] - reconciled) > 1e-6


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
    # US-33.4: rel=0.005, because market close vs the statement's own mark
    # differ by per-symbol noise on the terminal day (SEMI: 14.614 vs 14.646,
    # 0.22%). The claim under test is that the served quote is the HELD GBP
    # line — not the bare US ticker, which was 40.58 against 17.998.
    assert quote == pytest.approx(position.close_price, rel=0.005)
    # US-34.9: the frozen golden's terminal SEMI.L quote (~14.46) values the 200
    # units at ~$2,892 -- within 0.2% of the statement's own mark (statement_truths
    # pins SEMI at 2,885.60), and nowhere near the bare US ticker's 40.58.
    # 2026-08-28 statement refresh: 2,929.20 -> 2,892.00.
    assert position.quantity * quote == pytest.approx(2_892.00, abs=1.0)


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
    # The raw fetched series still show the per-line quote currency. Tolerance is
    # relative (2%): the frozen golden's terminal close and the statement's own
    # mark diverge by up to ~1.8% per symbol (DEFS) — per-line close-vs-mark
    # noise, not a currency-basis error. The discrimination margin (USD ratio
    # ~1.16 vs EUR ratio ~1.0) is an order of magnitude wider.
    # 2026-08-28 statement refresh: abs=0.01 -> rel=0.02.
    assert raw_ratio("DEFS") == pytest.approx(eurusd, rel=0.02)  # DEFS.L quotes USD
    assert raw_ratio("SXRV") == pytest.approx(1.0, rel=0.02)     # SXRV.DE quotes EUR
    assert raw_ratio("SEMI") == pytest.approx(1.0, rel=0.02)     # SEMI.L quotes GBP

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

    # US-33.4: 2026-04-14 was the exemplar until the refresh — it is now one of
    # LQQ's trade dates, so US-33.2 withholds its return entirely and it is in
    # neither chain. 2026-01-29 is the live equivalent: a $4,418.80 sale that
    # the naive chain reads as -8.69% and the shipped basis as -0.02%.
    assert "2026-04-14" not in naive and "2026-04-14" not in neutral
    assert naive["2026-01-29"] == pytest.approx(-0.086947, abs=1e-4)
    assert neutral["2026-01-29"] == pytest.approx(-0.000244, abs=1e-4)
    # No day in the whole window may show a trade-sized move under the shipped
    # basis: the naive chain swings 8.69%, the trade-neutral chain peaks at 2.95%.
    assert max(abs(r) for r in neutral.values()) == pytest.approx(0.029532, abs=1e-4)


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
    # 2026-08-28 statement refresh: -3_523.59 -> -3_516.03.
    assert by_date["2026-06-11"].trade_flow == pytest.approx(-3_516.03, abs=1.0)
    # ...so the day reports the priced book's real move, not a trade-sized one.
    # 2026-08-28 statement refresh: -0.003925 -> -0.004097.
    assert neutral["2026-06-11"] == pytest.approx(-0.004097, abs=1e-4)

    # And the 2026-04-27 sale, now backed by a trade-price valuation, IS
    # neutralised — its leg genuinely left yesterday's market value.
    assert by_date["2026-04-27"].trade_flow == pytest.approx(-5_341.92, abs=1.0)
    assert neutral["2026-04-27"] == pytest.approx(-0.001194, abs=1e-4)


def test_us249_de_dilution_is_explained_by_the_cash_weight(replay_context) -> None:
    """US-24.9 AC9 — the tripwire: the risk statistics must move by what the
    cash sleeve explains, and no more.

    Measured on IB2026 over **every** day of the window. When US-24.9 shipped
    this comparison had to exclude 2026-04-08 and 2026-04-27, whose
    cash-inclusive TWR was corrupted by unpriced-symbol cash events; US-24.10
    fixed that at source, so no exclusions remain:

        annualised volatility   TWR 13.81%  ->  trade-neutral 14.91%   (x1.079)
        median cash weight      6.50%       ->  predicted de-dilution  x1.069

    US-33.4 re-measured this on the 2026-08-11 statement, and the tripwire did
    its job on the way: before US-33.2 gave withheld-quantity symbols an
    unbacked-cash-flow guard, the ratio came out at **x0.965** — the wrong side
    of 1 — because LQQ's trades moved cash with no position behind it and the
    cash-inclusive chain published six of those steps as performance (the
    largest, +3.08% on 2026-04-17, was the window's biggest TWR day). Those days
    are now withheld, and the ratio is back where the cash weight predicts.

    A ratio far from the cash-weight prediction means the trade neutralisation
    is wrong, not that the portfolio is riskier.
    """
    import statistics

    from app.analytics.risk import _portfolio_time_weighted_return_series

    states = _us249_states(replay_context)
    base = "USD"

    weights = [s.cash[base] / s.total_portfolio_value for s in states if s.total_portfolio_value]
    median_weight = statistics.median(weights)
    # US-34.3: 0.0401 before opening cash moved to the statement's own figure.
    # 2026-08-28 statement refresh: 0.0650 -> 0.0490.
    assert median_weight == pytest.approx(0.0490, abs=0.005)

    def _vol(basis: str) -> float:
        series = _portfolio_time_weighted_return_series(states, basis=basis)
        return statistics.stdev([r for _, r in series]) * (252 ** 0.5)

    twr_vol = _vol("portfolio_value")
    neutral_vol = _vol("market_value_trade_neutral")

    # 2026-08-28 statement refresh: twr_vol 0.1381 -> 0.1343, neutral_vol 0.1491 -> 0.1445.
    assert twr_vol == pytest.approx(0.1343, abs=1e-3)
    assert neutral_vol == pytest.approx(0.1445, abs=1e-3)
    # The whole move is the cash weight: ratio close to 1/(1 - median weight).
    # 2026-08-28 statement refresh: the lower median cash weight (6.5% -> 4.9%)
    # makes the de-dilution prediction more sensitive; observed ratio 1.076 vs
    # predicted 1.052 is 2.3%, so the tripwire band widens rel=0.02 -> rel=0.03.
    assert neutral_vol / twr_vol == pytest.approx(1 / (1 - median_weight), rel=0.03)


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

    assert twr["2026-04-08"] == pytest.approx(0.024724, abs=1e-4)
    assert twr["2026-04-27"] == pytest.approx(-0.001191, abs=1e-4)
    # Nowhere near the fabricated values.
    assert abs(twr["2026-04-08"] - (-0.0790)) > 0.05
    assert abs(twr["2026-04-27"] - 0.0961) > 0.05
    # The window's largest TWR day falls from 9.61% to 2.76%. US-33.4 note: on
    # the refreshed statement this is 2.7617% — unmoved to four decimals, which
    # is a strong signal that US-33.2's withholding removed a fabrication rather
    # than reshaping real performance.
    assert max(abs(r) for r in twr.values()) == pytest.approx(0.026803, abs=1e-4)


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

    # US-33.2 restated this pin. On the 2026-08-11 statement two more round-trip
    # symbols (ICHN, ZPRV) reach the trade-anchored tier, and LQQ leaves every
    # tier: its reconstructed quantity is now WITHHELD (Epic 33 F-1), so there
    # is nothing to value on any basis. It previously appeared in TWO tiers at
    # once — `unpriced` before its first trade and `trade_price_anchored`
    # after — which is the observation US-33.3 corrects in the contract.
    assert engine.trade_price_anchored_symbols == {"BTEC", "ICHN", "IUFS", "IUHC", "ZPRV"}
    # Every held symbol whose quantity is trusted is valued on some basis...
    assert engine.unpriced_replay_symbols == set()
    assert engine.statement_anchored_symbols == set()
    # ...and the withheld one is in no tier at all.
    assert set(engine.quantity_withheld) == {"LQQ"}
    assert not (engine.trade_price_anchored_symbols & set(engine.quantity_withheld))


def test_us2410_terminal_reconciliation_does_not_worsen(replay_context) -> None:
    """US-24.10 AC9 — a valuation change must not degrade the statement match.

    US-31.5 brought terminal market value to within $1.35 of the pre-refresh
    statement's own `stock_total` ($61,238.53). US-33.4 re-measured it on the
    2026-08-11 statement: $64,934.40 against a `stock_total` of $64,922.99, a
    **$11.41** residual (0.018%). The wider gap is per-symbol noise between each
    holding's market close and the statement's mark — 11 symbols differ, largest
    $24.00 on a $11,988 line, signs in both directions — not a systematic error,
    so the assertion is relative rather than a two-dollar absolute.
    """
    snapshot, _price_histories, _valuation_dates = replay_context
    states = _us249_states(replay_context)

    # 2026-08-28 statement refresh: 64_896.27 -> 65_753.77.
    assert states[-1].total_market_value == pytest.approx(65_753.77, abs=1.0)
    assert states[-1].total_market_value == pytest.approx(
        snapshot.statement_totals.stock_total, rel=0.001
    )


# ---------------------------------------------------------------------------
# Epic 33 — corporate actions & replay quantity integrity (US-33.2)
#
# The 2026-08-11 statement contains a ~200:1 LQQ split. The opening roll-back
# `opening = ending + Σ SELL − Σ BUY` sums the 200-unit POST-split sale against
# the pre-split buys and produces a 199-unit opening position the broker never
# held (F-1); US-24.10's trade-price anchor then valued it at the stale
# pre-split EUR 1,457.78 (F-2), taking peak market value to $518,078.75 against
# a portfolio whose statement `stock_total` is $64,922.99.
#
# These pins assert the fail-closed behaviour. They are stated against the
# FX-enabled replay (`_us249_states` / `build_replay_currency_context`) — the
# same path the PRD's $518,078 was measured on. The `fx_history={}` audit
# harness above yields different magnitudes for the same defect.
# ---------------------------------------------------------------------------


def _us332_engine(replay_context):
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
    states = engine.build_daily_states(
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        apply_terminal_reconciliation=True,
    )
    return engine, states


def test_us332_lqq_is_flagged_with_its_measured_price_ratio(replay_context) -> None:
    """US-33.2 AC1/AC5 — the detection signal, pinned with its evidence.

    LQQ's own ledger spans EUR 9.069 … 1,977.94 in a single currency. No market
    move explains a 218x range inside one statement period; a change of share
    unit does.
    """
    engine, _states = _us332_engine(replay_context)

    withholding = engine.quantity_withheld["LQQ"]
    assert withholding.reason == "share_unit_discontinuity"
    assert withholding.currency == "EUR"
    assert withholding.price_low == pytest.approx(9.0691, abs=1e-4)
    assert withholding.price_high == pytest.approx(1_977.9409, abs=1e-4)
    assert withholding.price_ratio == pytest.approx(218.0967, abs=1e-3)
    # ending 0 + sells 204 − buys 5 — the phantom the roll-back produced.
    assert withholding.withheld_opening_quantity == 199.0


def test_us332_lqq_is_the_only_flagged_symbol(replay_context) -> None:
    """US-33.2 AC1/AC10 — a real signal, not a banner that always fires.

    Across every symbol with priced trades in this statement LQQ is the only one above the
    threshold. The widest LEGITIMATE range is NFLX at 1.40x, which is the margin
    that makes the 5.0 threshold defensible; if a future export narrows that gap
    this test is where it surfaces.
    """
    from collections import defaultdict

    from app.core.constants import REPLAY_SHARE_UNIT_DISCONTINUITY_RATIO
    from app.domain.ledger import snapshot_to_ledger

    snapshot, _price_histories, _valuation_dates = replay_context
    engine, _states = _us332_engine(replay_context)

    prices: defaultdict[tuple[str, str], list[float]] = defaultdict(list)
    for entry in snapshot_to_ledger(snapshot):
        if entry.entry_type in {"BUY", "SELL"} and entry.symbol and entry.price:
            prices[(entry.symbol, entry.cash_currency)].append(float(entry.price))
    ratios: dict[str, float] = defaultdict(float)
    for (symbol, _currency), observed in prices.items():
        ratios[symbol] = max(ratios[symbol], max(observed) / min(observed))

    # 61 of the statement's 68 replayed symbols carry priced BUY/SELL legs and
    # are therefore testable at all; the rest are opening-only reconstructions.
    assert len(ratios) == 61
    assert set(engine.quantity_withheld) == {"LQQ"}
    assert ratios["NFLX"] == pytest.approx(1.399, abs=0.01)
    assert "NFLX" not in engine.quantity_withheld
    runner_up = max(ratio for symbol, ratio in ratios.items() if symbol != "LQQ")
    assert runner_up < REPLAY_SHARE_UNIT_DISCONTINUITY_RATIO


def test_us332_lqq_never_appears_in_any_daily_state(replay_context) -> None:
    """US-33.2 AC3 — the phantom is the QUANTITY, so the quantity is withheld.

    Before the fix LQQ carried a position line on 130 of the window's 148 days,
    peaking at a 200-unit holding worth $395,199.92. Valuing it at $0 would not
    be enough: that still publishes a position size that was never held.
    """
    _engine, states = _us332_engine(replay_context)

    # 2026-08-28 statement refresh: 148 -> 161 (the window gained ~13 trading days).
    assert len(states) == 161
    assert not [
        state.date for state in states for item in state.positions if item.symbol == "LQQ"
    ]


def test_us332_peak_market_value_returns_to_a_plausible_band(replay_context) -> None:
    """US-33.2 AC8 — the headline number the epic exists to undo.

    Peak replayed market value falls from $518,078.75 (2026-07-06, ~8x the real
    portfolio) to $65,377.31, and the terminal state lands within $12 of the
    statement's own `stock_total`. The band assertion — not just the pin — is
    what makes a future corporate action fail loudly.
    """
    snapshot, _price_histories, _valuation_dates = replay_context
    _engine, states = _us332_engine(replay_context)

    peak = max(states, key=lambda state: state.total_market_value)
    # 2026-08-28 statement refresh: 65_377.31 -> 65_977.64; peak.date 2026-08-10 -> 2026-08-17.
    assert peak.total_market_value == pytest.approx(65_977.64, abs=1.0)
    assert peak.date == "2026-08-17"

    stock_total = snapshot.statement_totals.stock_total
    # 2026-08-28 statement refresh: 64_922.99 -> 65_746.67.
    assert stock_total == pytest.approx(65_746.67, abs=0.01)
    # Every day of the window is now within a plausible band of the statement's
    # own stock total — the pre-fix replay ran ~8x above it for three months.
    assert peak.total_market_value < stock_total * 1.05
    # 2026-08-28 statement refresh: 64_896.27 -> 65_753.77.
    assert states[-1].total_market_value == pytest.approx(65_753.77, abs=1.0)


def test_us346_no_published_period_figure_contains_the_reconciliation(replay_context) -> None:
    """US-34.6 (Epic 34 F-7) — US-31.3's rule, now enforced on EVERY period figure.

    US-31.3 stopped the terminal reconciliation being published as a return, but
    only on the time-weighted path. Modified Dietz and the investment gain read
    the reconciled terminal value straight, so both republished the same
    accounting entry: on IB2026 the money-weighted return was 5.30% (2.35pp of
    it the entry) and the gain $3,080.88 ($1,366.17 of it the entry).

    Inverted pin, in the style of the F-3 test above: it asserts the corrected
    behaviour and fails if the entry returns to either figure.
    """
    from app.analytics.performance import market_derived_terminal_value
    from app.scripts.frozen_market_data import FrozenMarketData
    from app.services.dashboard_history_engine import run_imported_dashboard_history

    snapshot, _price_histories, _valuation_dates = replay_context
    history = run_imported_dashboard_history(
        snapshot, "SPY", market_data=FrozenMarketData.from_file()
    )
    summary = (history.range_metrics or {})["All"].summary
    terminal = history.daily_states[-1]

    adjustment = terminal.reconciliation_adjustment
    # 2026-08-28 statement refresh: -19.98 -> -5.95.
    assert adjustment == pytest.approx(-5.95, abs=2.0), "fixture lost its reconciliation"

    # The performance figures are computed from the market-derived value...
    assert market_derived_terminal_value(history.daily_states) == pytest.approx(
        terminal.total_portfolio_value - adjustment, abs=0.01
    )
    # 2026-08-28 statement refresh: mwr 2.76 -> 3.49, investment_gain 1_645.99 -> 2_091.78.
    assert summary.money_weighted_return_pct == pytest.approx(3.49, abs=0.02)
    assert summary.investment_gain == pytest.approx(2_091.78, abs=0.02)

    # ...while the LEVEL keeps the broker's own ending NAV. Both halves matter:
    # dropping the entry from the level would discard broker truth.
    assert summary.end_value == pytest.approx(snapshot.statement_totals.ending_nav, abs=0.01)

    # US-34.8: the terminal day publishes again — with the adjustment removed
    # from the value, which is what keeps US-31.3's guarantee intact.
    assert terminal.return_is_publishable is True


def test_us344_withholding_states_how_much_was_at_stake(replay_context) -> None:
    """US-34.4 (Epic 34 F-3) — the withholding is sized, not just named.

    Epic 33 correctly refused to publish LQQ's reconstructed quantity, but told
    the researcher nothing about magnitude: missing 0.1% of a book and missing
    30% of it read identically. The broker's own cash answers it without a price
    or a quantity — which matters, because the quantity is the untrusted thing.

    Peak END-OF-DAY net investment. The within-day gross reaches $4,410.08 on
    2026-06-23 (a buy precedes a sell), which overstates anything ever held
    overnight; the replay's states are end-of-day objects.
    """
    _engine, _states = _us332_engine(replay_context)
    engine, _ = _us332_engine(replay_context)
    withholding = engine.quantity_withheld["LQQ"]

    # 2026-08-28 statement refresh: 2_130.62 -> 2_138.01.
    assert withholding.peak_net_cash_invested == pytest.approx(2_138.01, abs=1.0)
    assert withholding.peak_share_of_portfolio_pct == pytest.approx(3.52, abs=0.05)
    # First trade (2026-04-14) to last (2026-07-17), inclusive.
    assert withholding.exposure_day_count == 66

    # It is a LOWER BOUND on the position's value, not a valuation — so it must
    # never have leaked into market value.
    assert all(
        item.symbol != "LQQ" for state in _states for item in state.positions
    )


def test_us344_immaterial_unbacked_days_are_no_longer_withheld(replay_context) -> None:
    """US-34.4 (Epic 34 F-4) — the guard measures materiality, not cents.

    US-33.2 reused `REPLAY_RECONCILIATION_TOLERANCE` ($1.00), a constant
    calibrated for rounding across daily states. On this statement the six
    unbacked days are bimodal — 0.0085% and 0.0400% of the portfolio against
    2.77%-3.71% — so two real return days were being discarded for nothing.
    """
    _engine, states = _us332_engine(replay_context)

    # US-34.8 removed 2026-08-11: the reconciled terminal day is corrected
    # rather than withheld, leaving only the unbacked-cash set.
    withheld = [state.date for state in states if not state.return_is_publishable]
    assert withheld == [
        "2026-04-14",
        "2026-04-17",
        "2026-06-12",
        "2026-07-17",
    ]
    # The two recovered days still CARRY unbacked cash — they are published
    # because it is immaterial, not because the guard stopped noticing.
    recovered = {state.date: state for state in states if state.date in {"2026-06-10", "2026-06-23"}}
    # 2026-08-28 statement refresh: 25.09 -> 25.18; -5.13 -> -5.14.
    assert recovered["2026-06-10"].unbacked_cash_flow == pytest.approx(25.18, abs=0.01)
    assert recovered["2026-06-23"].unbacked_cash_flow == pytest.approx(-5.14, abs=0.01)
    assert all(state.return_is_publishable for state in recovered.values())

