"""Tests for the ledger-replay state engine (Epic 31 / US-31.2).

Coverage:
  - `replay_symbol_universe`: the set of symbols the replay must price
    (current holdings ∪ every BUY/SELL symbol), and what it deliberately
    excludes (non-trade entry types).
  - Opening-position pricing on the real IB2026 statement (F-1 regression).
  - The de-minimis truncation trap: a since-sold symbol must never shorten the
    replay window by scoring the maximum default weight.
  - `unpriced_replay_symbols`: symbols held on a day but unvaluable are
    DISCLOSED, never silently contributing 0.

The IB2026 numbers come from the frozen `app/scripts/golden_market_data.json`
(deterministic, network-free), so they are not local FMP-cache artifacts.
"""
from __future__ import annotations

import pytest

from app.core.constants import (
    REPLAY_OPENING_CASH_RESIDUAL_SHARE,
    SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT,
)
from app.domain.ledger import snapshot_to_ledger
from app.engine.portfolio_state import PortfolioStateEngine, replay_symbol_universe
from app.schemas.imports import ImportedPortfolioSnapshot, ImportedStatementTotals
from app.schemas.reconciliation import DailyPortfolioState
from app.scripts.export_dashboard_goldens import _docs_statement_path, _repo_root
from app.scripts.frozen_market_data import FrozenMarketData
from app.services.statement_importer import import_statements
from app.tests.fixtures import imported_snapshot, position
from app.tests.statement_truths import IB_POSITION_COUNT, IB_REPLAY_UNIVERSE_SIZE


def _snapshot(
    *,
    positions: list[dict],
    ledger_entries: list[dict] | None = None,
    cash_balances: list[dict] | None = None,
) -> ImportedPortfolioSnapshot:
    return ImportedPortfolioSnapshot.model_validate(
        imported_snapshot(
            positions=positions,
            ledger_entries=ledger_entries or [],
            cash_balances=cash_balances or [],
        )
    )


def _trade(
    entry_type: str,
    symbol: str,
    trade_date: str,
    quantity: float,
    price: float,
    currency: str = "USD",
) -> dict:
    return {
        "entry_type": entry_type,
        "trade_date": trade_date,
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "net_amount": (-1 if entry_type == "BUY" else 1) * quantity * price,
        "currency": currency,
        "source_section": "Trades",
    }


def _rows(symbol: str, dates: list[str], price: float = 100.0) -> list[dict]:
    return [{"date": d, "price": price, "symbol": symbol} for d in dates]


def _build(
    snapshot,
    price_histories,
    valuation_dates,
    *,
    reconcile: bool = False,
    fx_history: dict | None = None,
    symbol_fund_currencies: dict | None = None,
):
    engine = PortfolioStateEngine(
        snapshot=snapshot,
        base_currency=(snapshot.statement.base_currency or "USD"),
        fx_history=fx_history or {},
        symbol_fund_currencies=symbol_fund_currencies or {},
    )
    states = engine.build_daily_states(
        price_histories=price_histories,
        valuation_dates=valuation_dates,
        apply_terminal_reconciliation=reconcile,
    )
    return engine, states


def _static_fx(dates: list[str], rates: dict[str, float]) -> dict[str, float]:
    """Static per-date fx_history keyed `{CCY}{BASE}:{date}` (the US-30.2 shape)."""
    return {f"{pair}:{d}": rate for d in dates for pair, rate in rates.items()}


@pytest.fixture(scope="module")
def ib2026_snapshot() -> ImportedPortfolioSnapshot:
    root = _repo_root()
    return import_statements(
        [str(_docs_statement_path(root, "IB2026.csv", "IB2026.pdf", "2026.pdf"))]
    )


@pytest.fixture(scope="module")
def ib2026_replay(ib2026_snapshot):
    """IB2026 replay driven by the FULL reconstructed universe (US-31.2)."""
    snapshot = ib2026_snapshot
    market_data = FrozenMarketData.from_file()

    history_dates = [e.trade_date.isoformat() for e in snapshot.ledger_entries if e.trade_date]
    history_dates += [p.as_of_date.isoformat() for p in snapshot.positions if p.as_of_date]
    start, end = min(history_dates), max(history_dates)

    benchmark_rows = market_data.get_historical_prices("SPY", start, end)
    valuation_dates = sorted({row["date"] for row in benchmark_rows})
    price_histories = market_data.get_historical_prices_for_symbols(
        replay_symbol_universe(snapshot), start, end
    )
    return _build(snapshot, price_histories, valuation_dates)


class TestReplaySymbolUniverse:
    def test_replay_symbol_universe_includes_since_sold_symbols(self, ib2026_snapshot) -> None:
        """The universe must cover positions the replay reconstructs, not just
        the ones still held today (Epic 31 F-1)."""
        snapshot = ib2026_snapshot
        universe = replay_symbol_universe(snapshot)
        current = {p.symbol for p in snapshot.positions}

        # US-33.4: both counts are statement truths and moved with the
        # 2026-08-11 refresh (20 -> 18 holdings, 63 -> 68 universe), so they are
        # read from the truths module rather than pinned here. The PROPERTY
        # under test is that the universe strictly exceeds current holdings —
        # opening positions since sold, and symbols round-tripped entirely
        # inside the window, are valued on some day and must be fetched.
        assert len(current) == IB_POSITION_COUNT
        assert len(universe) == IB_REPLAY_UNIVERSE_SIZE
        assert len(universe) > len(current)
        assert current <= set(universe)
        assert "NFLX" in universe and "NFLX" not in current

    def test_replay_symbol_universe_ignores_non_trade_entry_types(self) -> None:
        """Only BUY/SELL move quantities — a DIVIDEND naming a symbol we never
        held must not widen the fetch set."""
        snapshot = _snapshot(
            positions=[position("AAA")],
            ledger_entries=[
                {
                    "entry_type": "DIVIDEND",
                    "trade_date": "2025-03-03",
                    "symbol": "ZZZ",
                    "net_amount": 12.0,
                    "currency": "USD",
                    "source_section": "Dividends",
                },
                {
                    "entry_type": "FEE",
                    "trade_date": "2025-03-04",
                    "symbol": "YYY",
                    "net_amount": -1.0,
                    "currency": "USD",
                    "source_section": "Fees",
                },
            ],
        )
        assert replay_symbol_universe(snapshot) == ["AAA"]


class TestOpeningPositionCoverage:
    def test_opening_positions_all_priced_on_day_one(self, ib2026_replay) -> None:
        """F-1 regression: every reconstructed opening position is valued on day
        one. Pre-fix, 27 of 38 were unpriced and contributed $0."""
        _engine, states = ib2026_replay
        day_one = states[0]

        unpriced = sorted(p.symbol for p in day_one.positions if p.market_value is None)
        assert unpriced == [], f"opening positions still unpriced: {unpriced}"

        # Pre-fix day-one market value was $14,582.03 — 70.9% short of the
        # statement-implied $50,116.24 (PRD F-1). It is now $49,024.04, a 2.2%
        # residual attributable to LQQ: a held symbol with NO fetchable history,
        # so it keeps the US-27.7 statement-close anchor (valued flat at its
        # PERIOD-END price on day one). That anchor is broker-truth-adjacent and
        # disclosed via `statement_anchored_symbols`, not a US-31.2 defect.
        assert day_one.total_market_value == pytest.approx(49_024.04, abs=1.0)
        implied_shortfall = 50_116.24 - day_one.total_market_value
        assert implied_shortfall / 50_116.24 < 0.03

    def test_ib2026_replay_window_start_unchanged(self, ib2026_replay) -> None:
        """Expanding the fetch set must not move the replay window start."""
        _engine, states = ib2026_replay
        assert states[0].date == "2026-01-08"

    def test_opening_cash_anchor_records_us_31_3_baseline(self, ib2026_replay, ib2026_snapshot) -> None:
        """AC8 falsification check.

        F-1 was diagnosed as the dominant term in F-2's cash plug. With every
        opening position priced, the opening-cash drift must collapse. The
        residual pinned here is the BASELINE that US-31.3 (F-2/F-3) drives to
        zero — if this ever grows, F-1 has regressed.
        """
        _engine, states = ib2026_replay
        snapshot = ib2026_snapshot
        totals = snapshot.statement_totals
        assert totals is not None and totals.cash_total is not None

        net_window_flow = sum(e.cash_effect or 0.0 for e in snapshot_to_ledger(snapshot))
        implied_opening_cash = totals.cash_total - net_window_flow
        engine_opening_cash = states[0].cash[snapshot.statement.base_currency or "USD"]
        drift = engine_opening_cash - implied_opening_cash

        # US-34.3 SUPERSEDED this measurement. It compared the derived anchor
        # against a RAW currency-mixed implied figure — the basis US-31.3 AC3
        # documents as wrong — to show F-1 was the dominant term of the F-2 cash
        # plug (pre-fix $35,534.21 -> $1,097.18 -> $1,305.78). There is no plug
        # left to measure: the anchor no longer derives at all, it reads the
        # statement's own reported starting cash.
        #
        # The invariant worth keeping is the one that replaced it.
        assert states[0].cash[snapshot.statement.base_currency or "USD"] == pytest.approx(
            4_677.02, abs=1.0
        )
        assert engine_opening_cash > implied_opening_cash, (
            "day-one cash must reflect the statement's reported opening cash, "
            "not the raw currency-mixed implied figure"
        )
        assert drift == pytest.approx(2_620.74, abs=1.0)


class TestDeMinimisTruncationTrap:
    def test_since_sold_symbol_does_not_truncate_replay_window(self) -> None:
        """A since-sold symbol has no CURRENT weight, so it must be excluded
        from the truncation reference set rather than scoring the maximum
        `.get(symbol, 1.0)` default and shortening the window for everyone."""
        dates = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=10_000.0)],
            ledger_entries=[_trade("SELL", "BBB", "2025-01-02", 5.0, 50.0)],
        )
        price_histories = {
            "AAA": _rows("AAA", dates),
            # BBB only starts halfway through the window.
            "BBB": _rows("BBB", dates[3:], price=50.0),
        }

        _engine, states = _build(snapshot, price_histories, dates)

        assert [s.date for s in states] == dates, (
            "a since-sold symbol truncated the replay window"
        )

    def test_material_current_holding_still_truncates_the_window(self) -> None:
        """The US-27.7 rule itself is unchanged: a MATERIAL currently-held
        symbol whose coverage starts mid-window still truncates."""
        dates = ["2025-01-01", "2025-01-02", "2025-01-03", "2025-01-04", "2025-01-05"]
        snapshot = _snapshot(
            positions=[
                position("AAA", market_value=10_000.0),
                position("CCC", market_value=10_000.0),
            ],
        )
        assert 10_000.0 / 20_000.0 >= SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT
        price_histories = {
            "AAA": _rows("AAA", dates),
            "CCC": _rows("CCC", dates[2:]),
        }

        _engine, states = _build(snapshot, price_histories, dates)

        assert [s.date for s in states] == dates[2:]


class TestUnpricedSymbolDisclosure:
    def test_unpriced_opening_symbol_is_disclosed(self) -> None:
        """A since-sold symbol with no history AND no statement anchor cannot be
        valued — it contributes 0, so the gap must be disclosed (guardrail #3),
        never left silent."""
        dates = ["2025-01-01", "2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=10_000.0)],
            ledger_entries=[_trade("SELL", "BBB", "2025-01-03", 5.0, 50.0)],
        )
        price_histories = {"AAA": _rows("AAA", dates)}

        engine, states = _build(snapshot, price_histories, dates)

        assert "BBB" in engine.unpriced_replay_symbols
        assert "AAA" not in engine.unpriced_replay_symbols
        # BBB is held on day one (opening qty 5) but unvaluable, so day-one
        # market value reflects AAA alone — understated, and disclosed as such.
        bbb_day_one = next(p for p in states[0].positions if p.symbol == "BBB")
        assert bbb_day_one.market_value is None

    def test_fully_covered_replay_discloses_nothing(self) -> None:
        """The disclosure must stay empty when every held symbol is priced —
        an always-populated list would be noise, not a signal."""
        dates = ["2025-01-01", "2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=10_000.0)],
            ledger_entries=[_trade("SELL", "BBB", "2025-01-03", 5.0, 50.0)],
        )
        price_histories = {
            "AAA": _rows("AAA", dates),
            "BBB": _rows("BBB", dates, price=50.0),
        }

        engine, _states = _build(snapshot, price_histories, dates)

        assert engine.unpriced_replay_symbols == set()


class TestShareUnitDiscontinuity:
    """US-33.2 (Epic 33 F-1/F-2): the opening roll-back
    `opening = ending + Σ SELL − Σ BUY` is only valid while one share unit holds
    for the whole window. A split breaks the identity and fabricates a position
    size — on IB2026 a 199-unit LQQ opening the broker never held, which the
    US-24.10 trade-price anchor then valued at the stale pre-split price. The
    fabricated object is the QUANTITY, so the quantity is what is withheld.

    The synthetic ledger below reproduces the IB2026 LQQ shape in miniature:
    small pre-split buys around 1,500, then a 200-unit post-split sale at ~9.
    """

    DATES = ["2025-01-02", "2025-01-03", "2025-01-06"]

    def _split_snapshot(self):
        return _snapshot(
            positions=[position("AAA", market_value=10_000.0)],
            ledger_entries=[
                _trade("BUY", "SPLIT", "2025-01-02", 1.0, 1_457.78, currency="EUR"),
                _trade("BUY", "SPLIT", "2025-01-03", 1.0, 1_566.40, currency="EUR"),
                _trade("SELL", "SPLIT", "2025-01-06", 200.0, 9.07, currency="EUR"),
            ],
        )

    def test_share_unit_discontinuity_is_detected_with_its_evidence(self) -> None:
        """AC1/AC5 — the signal is the symbol's own price range, and the evidence
        is recorded so a researcher can judge the call rather than take it."""
        engine, _states = _build(
            self._split_snapshot(), {"AAA": _rows("AAA", self.DATES)}, self.DATES
        )

        withholding = engine.quantity_withheld["SPLIT"]
        assert withholding.reason == "share_unit_discontinuity"
        assert withholding.currency == "EUR"
        assert withholding.price_low == 9.07
        assert withholding.price_high == 1_566.40
        assert withholding.price_ratio == pytest.approx(172.70, abs=0.01)
        # ending 0 + sells 200 − buys 2: the phantom the roll-back produced.
        assert withholding.withheld_opening_quantity == 198.0

    def test_ordinary_price_movement_is_not_flagged(self) -> None:
        """AC10 — the detection must be a real signal. IB2026's widest LEGITIMATE
        within-symbol range is 1.40x (NFLX); a 1.4x ledger must value exactly as
        it does today, with nothing withheld."""
        dates = self.DATES
        snapshot = _snapshot(
            positions=[position("AAA", market_value=10_000.0)],
            ledger_entries=[
                _trade("BUY", "BBB", "2025-01-02", 4.0, 70.0),
                _trade("SELL", "BBB", "2025-01-06", 10.0, 98.0),
            ],
        )
        price_histories = {"AAA": _rows("AAA", dates), "BBB": _rows("BBB", dates, price=80.0)}

        engine, states = _build(snapshot, price_histories, dates)

        assert engine.quantity_withheld == {}
        # Opening 6 units (0 + 10 − 4), plus day one's own BUY of 4 — valued
        # exactly as it was before US-33.2.
        opening_bbb = next(p for p in states[0].positions if p.symbol == "BBB")
        assert opening_bbb.quantity == 10.0
        assert opening_bbb.market_value == 800.0

    def test_ratio_is_measured_within_a_currency_never_across(self) -> None:
        """AC2 — a symbol traded in two currencies must not be flagged by an FX
        difference it never experienced. 100 USD and 9 EUR is an 11x ratio
        across currencies and ~1x within each."""
        dates = self.DATES
        snapshot = _snapshot(
            positions=[position("AAA", market_value=10_000.0)],
            ledger_entries=[
                _trade("BUY", "BBB", "2025-01-02", 4.0, 100.0, currency="USD"),
                _trade("SELL", "BBB", "2025-01-06", 4.0, 9.0, currency="EUR"),
            ],
        )

        engine, _states = _build(snapshot, {"AAA": _rows("AAA", dates)}, dates)

        assert engine.quantity_withheld == {}

    def test_withheld_symbol_emits_no_position_and_no_market_value(self) -> None:
        """AC3 — withholding is of the QUANTITY: no line, no size, no value on
        any day. A $0 valuation would still publish a position size that was
        never held."""
        engine, states = _build(
            self._split_snapshot(), {"AAA": _rows("AAA", self.DATES)}, self.DATES
        )

        assert "SPLIT" in engine.quantity_withheld
        assert all(p.symbol != "SPLIT" for state in states for p in state.positions)
        # AAA alone carries market value on every day (10 units at 100) —
        # nothing phantom added, on no day.
        assert [state.total_market_value for state in states] == [1_000.0] * 3

    def test_trade_price_anchor_declines_a_withheld_symbol(self) -> None:
        """AC4 (Epic 33 F-2) — the anchor's own guard. Without it the pre-split
        1,457.78 is carried forward across the split and values the phantom."""
        snapshot = self._split_snapshot()
        engine, states = _build(snapshot, {"AAA": _rows("AAA", self.DATES)}, self.DATES)

        # The anchor would otherwise have had an observed price from day one
        # (the 2025-01-02 BUY) for every subsequent day.
        assert "SPLIT" not in engine.trade_price_anchored_symbols
        assert all(
            p.market_price is None for state in states for p in state.positions if p.symbol == "SPLIT"
        )

    def test_withheld_symbol_keeps_its_cash_but_fabricates_no_return(self) -> None:
        """AC7 — the cash is broker truth and unaffected by the unit ambiguity;
        the trade legs are excluded from `trade_flow` by the US-24.9 gate because
        the symbol is priced on no day, so no return is fabricated from them."""
        engine, states = _build(
            self._split_snapshot(), {"AAA": _rows("AAA", self.DATES)}, self.DATES
        )
        base = engine.base_currency

        # The 200-unit sale settles 1,814.00 into cash on the final day.
        assert states[-1].cash[base] - states[-2].cash[base] == pytest.approx(1_814.00, abs=0.01)
        assert [state.trade_flow for state in states] == [0.0, 0.0, 0.0]

    def test_withheld_symbol_trade_days_publish_no_return(self) -> None:
        """AC11 — the guard the cash preservation of AC7 makes necessary.

        `trade_flow` neutralisation only protects the cash-EXCLUDED chain. On the
        cash-inclusive basis the withheld symbol's cash still moves with no
        position behind it, so `total_portfolio_value` steps and the return chain
        would publish the step as performance — the US-24.9 fabrication class,
        re-opened by withholding. Found by the US-24.9 de-dilution tripwire while
        adopting the refreshed statement (US-33.4), where it had inflated the
        window's largest TWR day to +3.08%.
        """
        _engine, states = _build(
            self._split_snapshot(), {"AAA": _rows("AAA", self.DATES)}, self.DATES
        )
        by_date = {state.date: state for state in states}

        # Every SPLIT trade moves cash with nothing behind it — the two buys
        # and the 200-unit post-split sale.
        assert by_date["2025-01-02"].unbacked_cash_flow == pytest.approx(-1_457.78, abs=0.01)
        assert by_date["2025-01-03"].unbacked_cash_flow == pytest.approx(-1_566.40, abs=0.01)
        assert by_date["2025-01-06"].unbacked_cash_flow == pytest.approx(1_814.00, abs=0.01)
        assert not any(state.return_is_publishable for state in states)

    # -- US-34.4 (Epic 34 F-3/F-4): size the gap, and stop over-withholding ----

    def test_withholding_reports_what_the_broker_had_at_stake(self) -> None:
        """US-34.4 AC1/AC2 — how much, and for how long, from cash alone.

        The quantity is the untrusted thing, so the exposure cannot be measured
        as quantity x price. Running the broker's own net cash gives a LOWER
        BOUND: what was paid, not what it was worth.

        This fixture buys at 1,457.78 then 1,566.40 (running 3,024.18) before
        the post-split sale returns 1,814.00 — so the end-of-day peak is
        3,024.18 on day two.
        """
        engine, _states = _build(
            self._split_snapshot(), {"AAA": _rows("AAA", self.DATES)}, self.DATES
        )
        withholding = engine.quantity_withheld["SPLIT"]

        assert withholding.peak_net_cash_invested == pytest.approx(3_024.18, abs=0.01)
        # First trade to last, inclusive — the span the replay showed nothing for.
        assert withholding.exposure_day_count == 3
        # This fixture's SPLIT buys drive the portfolio value negative on the
        # peak day, so the share is not computable — and is reported as absent
        # rather than as a nonsense negative percentage.
        assert withholding.peak_share_of_portfolio_pct is None

    def test_withheld_exposure_converts_each_currency_before_accumulating(self) -> None:
        """US-34.4 AC2 — the US-31.3 currency-mixed trap, restated.

        A symbol traded in EUR must not have its cash summed as if it were base
        currency. At 1.20 the same ledger is worth 20% more.
        """
        snapshot = self._split_snapshot()
        dates = self.DATES
        engine, _states = _build(
            snapshot,
            {"AAA": _rows("AAA", dates)},
            dates,
            fx_history=_static_fx(dates, {"EURUSD": 1.20}),
        )

        withholding = engine.quantity_withheld["SPLIT"]
        assert withholding.peak_net_cash_invested == pytest.approx(3_024.18 * 1.20, abs=0.02)

    def test_immaterial_unbacked_cash_leaves_the_day_publishable(self) -> None:
        """US-34.4 AC5 — materiality is a share of the portfolio, not a dollar.

        US-33.2 reused the $1.00 rounding tolerance, so a flow worth 0.05% of
        the book cost a real return day. The same ledger against a portfolio 20x
        larger must keep its returns.
        """
        dates = self.DATES
        ledger = [
            _trade("BUY", "SPLIT", "2025-01-02", 1.0, 1_000.0),
            _trade("SELL", "SPLIT", "2025-01-06", 100.0, 10.0),
        ]

        big = _snapshot(positions=[position("AAA", market_value=20_000_000.0)], ledger_entries=ledger)
        engine_big, states_big = _build(
            big, {"AAA": _rows("AAA", dates, price=2_000_000.0)}, dates
        )
        small = _snapshot(positions=[position("AAA", market_value=100_000.0)], ledger_entries=ledger)
        engine_small, states_small = _build(
            small, {"AAA": _rows("AAA", dates, price=10_000.0)}, dates
        )

        # Same symbol withheld in both — only the materiality verdict differs.
        assert "SPLIT" in engine_big.quantity_withheld
        assert "SPLIT" in engine_small.quantity_withheld
        assert all(state.return_is_publishable for state in states_big)
        assert not all(state.return_is_publishable for state in states_small)

    def test_no_discontinuity_reports_no_exposure_and_no_unbacked_days(self) -> None:
        """US-34.4 AC9 — the measurement is a signal, not a permanent fixture."""
        dates = self.DATES
        snapshot = _snapshot(
            positions=[position("AAA", market_value=10_000.0)],
            ledger_entries=[_trade("BUY", "AAA", "2025-01-03", 4.0, 100.0)],
        )

        engine, states = _build(snapshot, {"AAA": _rows("AAA", dates)}, dates)

        assert engine.quantity_withheld == {}
        assert all(state.unbacked_cash_flow == 0.0 for state in states)
        assert all(state.return_is_publishable for state in states)

    def test_ordinary_trades_leave_the_return_publishable(self) -> None:
        """AC11 — the guard must fire only for withheld symbols.

        A day of ordinary trading has nothing unbacked, so its return is
        published exactly as before US-33.2.
        """
        dates = self.DATES
        snapshot = _snapshot(
            positions=[position("AAA", market_value=10_000.0)],
            ledger_entries=[_trade("BUY", "AAA", "2025-01-03", 4.0, 100.0)],
        )

        _engine, states = _build(snapshot, {"AAA": _rows("AAA", dates)}, dates)

        assert [state.unbacked_cash_flow for state in states] == [0.0, 0.0, 0.0]
        assert all(state.return_is_publishable for state in states)

    def test_withheld_symbol_is_in_no_valuation_tier(self) -> None:
        """AC6 — `withheld` is its own state. Collapsing it into `unpriced`
        would claim the quantity was trusted and only the price was missing,
        which is the opposite of the finding (guardrail #3)."""
        engine, _states = _build(
            self._split_snapshot(), {"AAA": _rows("AAA", self.DATES)}, self.DATES
        )

        assert "SPLIT" not in engine.unpriced_replay_symbols
        assert "SPLIT" not in engine.trade_price_anchored_symbols
        assert "SPLIT" not in engine.statement_anchored_symbols
        assert set(engine.quantity_withheld) == {"SPLIT"}


class TestFundCurrencyConversion:
    """US-31.5 (Epic 31 F-4): market values convert by the FUND currency (the
    resolved line's quote currency), not the broker listing currency; anchored
    values keep the position currency."""

    def test_market_value_converts_by_fund_currency_not_listing(self) -> None:
        # Two EUR-listed positions. AAA's fund currency is USD (like DEFS.L,
        # which quotes USD) → must NOT be converted. BBB's fund currency is EUR
        # (like SXRV.DE) → must be converted by EURUSD. The listing currency is
        # identical for both, so the engine must be reading the fund currency.
        dates = ["2025-01-01", "2025-01-02"]
        snapshot = _snapshot(
            positions=[
                position("AAA", market_value=1000.0, currency="EUR"),
                position("BBB", market_value=1000.0, currency="EUR"),
            ],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=10.0), "BBB": _rows("BBB", dates, price=10.0)}
        fx = _static_fx(dates, {"EURUSD": 1.20})

        _engine, states = _build(
            snapshot, price_histories, dates,
            fx_history=fx,
            symbol_fund_currencies={"AAA": "USD", "BBB": "EUR"},
        )
        by_symbol = {p.symbol: p for p in states[-1].positions}
        # AAA (fund USD): 10 qty × 10.0 = 100.0, no conversion.
        assert by_symbol["AAA"].market_value == pytest.approx(100.0)
        # BBB (fund EUR): 100.0 × 1.20 = 120.0.
        assert by_symbol["BBB"].market_value == pytest.approx(120.0)

    def test_statement_anchored_holding_converts_by_position_currency(self) -> None:
        # AAA has market data (fund USD). BBB has NO history → statement-anchored
        # at its close (2.0) in its POSITION currency EUR, converted by EURUSD,
        # NOT by any fund currency (the anchor is the statement close).
        dates = ["2025-01-01", "2025-01-02"]
        snapshot = _snapshot(
            positions=[
                position("AAA", market_value=1000.0, currency="USD", quantity=10.0),
                position("BBB", market_value=100.0, currency="EUR", quantity=50.0, close_price=2.0),
            ],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}  # BBB absent → anchored
        fx = _static_fx(dates, {"EURUSD": 1.30})

        engine, states = _build(
            snapshot, price_histories, dates,
            fx_history=fx,
            symbol_fund_currencies={"AAA": "USD"},  # BBB deliberately absent
        )
        by_symbol = {p.symbol: p for p in states[-1].positions}
        # BBB anchored at 2.0 EUR × 50 = 100 EUR × 1.30 = 130.0.
        assert by_symbol["BBB"].market_value == pytest.approx(130.0)
        assert "BBB" in engine.statement_anchored_symbols

    def test_no_fx_rates_carries_unconverted_and_discloses(self) -> None:
        # US-27.8 contract preserved: with an empty fx_history a non-base value
        # is carried raw and the currency recorded in the fallback set.
        dates = ["2025-01-01", "2025-01-02"]
        snapshot = _snapshot(positions=[position("BBB", market_value=1000.0, currency="EUR")])
        price_histories = {"BBB": _rows("BBB", dates, price=10.0)}

        engine, states = _build(
            snapshot, price_histories, dates,
            fx_history={},
            symbol_fund_currencies={"BBB": "EUR"},
        )
        assert states[-1].positions[0].market_value == pytest.approx(100.0)  # unconverted
        assert "EUR" in engine.fx_fallback_currencies

    def test_missing_fund_currency_falls_back_to_position_currency(self) -> None:
        # A symbol absent from the fund-currency map uses its position currency,
        # and converts by that — never a silent 1:1 base assumption.
        dates = ["2025-01-01", "2025-01-02"]
        snapshot = _snapshot(positions=[position("BBB", market_value=1000.0, currency="EUR")])
        price_histories = {"BBB": _rows("BBB", dates, price=10.0)}
        fx = _static_fx(dates, {"EURUSD": 1.10})

        _engine, states = _build(
            snapshot, price_histories, dates,
            fx_history=fx,
            symbol_fund_currencies={},  # BBB absent → position currency EUR
        )
        # 100 EUR × 1.10 = 110.0 (converted by position currency, not left raw).
        assert states[-1].positions[0].market_value == pytest.approx(110.0)


class TestIB2026FundCurrencyReconciliation:
    def test_ib2026_terminal_market_value_reconciles_to_statement(self, ib2026_snapshot) -> None:
        """US-31.5 AC1/AC2: with fund-currency conversion the replayed terminal
        total market value reconciles to the statement's own stock_total."""
        from app.instruments import InstrumentRegistry

        snapshot = ib2026_snapshot
        market_data = FrozenMarketData.from_file()
        history_dates = [e.trade_date.isoformat() for e in snapshot.ledger_entries if e.trade_date]
        history_dates += [p.as_of_date.isoformat() for p in snapshot.positions if p.as_of_date]
        start, end = min(history_dates), max(history_dates)
        valuation_dates = sorted({row["date"] for row in market_data.get_historical_prices("SPY", start, end)})
        price_histories = market_data.get_historical_prices_for_symbols(
            replay_symbol_universe(snapshot), start, end
        )

        registry = InstrumentRegistry()
        fund_currencies = {}
        for symbol in replay_symbol_universe(snapshot):
            inst = registry.get_instrument(symbol)
            if inst is not None and inst.currency:
                fund_currencies[symbol] = inst.currency
        fx = _static_fx(valuation_dates, {
            pair[:3] + pair[3:]: rate for pair, rate in (snapshot.statement_totals.fx_rates or {}).items()
        })

        _engine, states = _build(
            snapshot, price_histories, valuation_dates,
            fx_history=fx, symbol_fund_currencies=fund_currencies,
        )
        terminal = states[-1]
        by_symbol = {p.symbol: p for p in terminal.positions}

        # US-33.4 re-measured on the 2026-08-11 statement (was 8,654.45 /
        # 3,580.07). LQQ was a third pin here until US-33.2 withheld its
        # reconstructed quantity — a withheld symbol is in no state at all, so
        # the assertion is now that it is ABSENT rather than valued.
        assert by_symbol["SXRV"].market_value == pytest.approx(10_215.55, abs=1.0)
        assert by_symbol["SEMI"].market_value == pytest.approx(3_948.12, abs=1.0)
        assert "LQQ" not in by_symbol
        # DEFS (DEFS.L quotes USD): unchanged, never double-converted.
        assert by_symbol["DEFS"].market_value == pytest.approx(
            next(p for p in snapshot.positions if p.symbol == "DEFS").quantity
            * max(price_histories["DEFS"], key=lambda r: r["date"])["price"],
            abs=1.0,
        )
        assert terminal.total_market_value == pytest.approx(64_934.40, abs=2.0)


class TestCashAnchorDisclosure:
    """US-31.3 (Epic 31 F-2): the opening cash anchor discloses its provenance
    and trust. `starting_nav - opening_positions_value` is only sound when both
    terms share an as-of date."""

    def _ib2026_engine(self, snapshot):
        """The IB2026 replay, wired the way production wires it."""
        from app.analytics.performance import build_replay_currency_context

        market_data = FrozenMarketData.from_file()
        hd = [e.trade_date.isoformat() for e in snapshot.ledger_entries if e.trade_date]
        hd += [p.as_of_date.isoformat() for p in snapshot.positions if p.as_of_date]
        start, end = min(hd), max(hd)
        vd = sorted({r["date"] for r in market_data.get_historical_prices("SPY", start, end)})
        syms = replay_symbol_universe(snapshot)
        ph = market_data.get_historical_prices_for_symbols(syms, start, end)
        fund_ccy, fx = build_replay_currency_context(snapshot, syms, vd)
        return _build(snapshot, ph, vd, fx_history=fx, symbol_fund_currencies=fund_ccy)

    def test_cash_anchor_uses_the_statements_own_starting_cash(self, ib2026_snapshot) -> None:
        """US-34.3 (Epic 34 F-2) AC1/AC3 — the anchor can finally be verified.

        This test previously pinned `statement_nav_date_mismatch` / `degraded`
        with a -$1,377.59 residual, because the anchor was DERIVED as
        `starting_nav - opening_positions_value` from two differently-dated
        terms. Those dates coincide only if an account trades on the first day
        of its statement period, so the warning fired on every run of every
        statement — a disclosure carrying no information.

        The broker reports the figure directly, so the derivation is no longer
        needed and the anchor is observed truth.
        """
        engine, states = self._ib2026_engine(ib2026_snapshot)
        anchor = engine.cash_anchor

        assert anchor is not None
        assert anchor.basis == "statement_starting_cash"
        assert anchor.trust == "verified"
        # The dates are still reported - they are provenance, not a verdict.
        assert anchor.nav_as_of == "2026-01-01"
        assert anchor.window_start == "2026-01-08"
        # Day one opens on the statement's own cash (4,672.04) plus that day's
        # trades, rather than the derived 3,252.74.
        assert states[0].cash["USD"] == pytest.approx(4_677.02, abs=1.0)

    def test_cash_anchor_publishes_its_residual_alongside_verified_trust(
        self, ib2026_snapshot
    ) -> None:
        """US-34.3 AC4 — trust and residual are different facts.

        Trust follows the anchor's SOURCE: an observed figure is verified. The
        residual measures something else entirely — how well the ledger's flows
        reconcile the statement's own two cash endpoints — and is published
        rather than collapsed into the trust level.
        """
        engine, _states = self._ib2026_engine(ib2026_snapshot)
        anchor = engine.cash_anchor

        assert anchor.trust == "verified"
        assert anchor.residual == pytest.approx(46.69, abs=1.0)
        # 1.0% of opening cash - inside the documented share, hence verified.
        assert abs(anchor.residual) / 4_672.04 < REPLAY_OPENING_CASH_RESIDUAL_SHARE

    def test_cash_anchor_falls_back_to_the_derived_identity(self) -> None:
        """US-34.3 AC2 — a statement reporting no starting cash is unchanged.

        The derived `starting_nav - opening_positions_value` path and its two
        bases survive intact; only the precedence above them is new.
        """
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = ImportedPortfolioSnapshot.model_validate(
            imported_snapshot(
                positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
                # Reports an ENDING balance but no starting one.
                cash_balances=[{"currency": "USD", "ending_cash": 500.0}],
                statement_overrides={
                    "statement_period": "2024-12-01 - 2025-01-03",
                    "base_currency": "USD",
                },
            )
        )
        snapshot.statement_totals = ImportedStatementTotals(starting_nav=1500.0, cash_total=500.0)
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, _states = _build(snapshot, price_histories, dates)

        assert engine.cash_anchor.basis == "statement_nav_date_mismatch"
        assert engine.cash_anchor.trust == "degraded"

    def test_cash_anchor_uses_snapshot_balances_without_statement_totals(self) -> None:
        """US-34.3 AC2 — the request path is untouched.

        No `statement_totals` means nothing to derive from and nothing reported,
        so the snapshot's own balances remain the honest anchor (US-30.1).
        """
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            cash_balances=[{"currency": "USD", "ending_cash": 250.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, states = _build(snapshot, price_histories, dates)

        assert engine.cash_anchor.basis == "snapshot_cash_balances"
        assert engine.cash_anchor.trust == "verified"
        assert states[0].cash["USD"] == pytest.approx(250.0, abs=0.01)

    def test_cash_anchor_degrades_when_the_ledger_cannot_explain_the_statement(self) -> None:
        """US-34.3 AC5 — the disclosure is still a signal.

        Observed opening cash is not a licence to always claim verified. When
        the ledger's flows fail to reconcile the statement's two cash endpoints
        by more than the documented share, the anchor degrades and the card
        speaks again.
        """
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = ImportedPortfolioSnapshot.model_validate(
            imported_snapshot(
                positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
                # Reported opening cash 1,000; the statement's own ending cash of
                # 500 with no ledger flows implies an opening of 500 - a 100%
                # residual the ledger cannot account for.
                cash_balances=[{"currency": "USD", "starting_cash": 1000.0, "ending_cash": 500.0}],
                statement_overrides={
                    "statement_period": "2025-01-02 - 2025-01-03",
                    "base_currency": "USD",
                },
            )
        )
        snapshot.statement_totals = ImportedStatementTotals(starting_nav=1500.0, cash_total=500.0)
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, _states = _build(snapshot, price_histories, dates)

        assert engine.cash_anchor.basis == "statement_starting_cash"
        assert engine.cash_anchor.trust == "degraded"
        assert engine.cash_anchor.residual == pytest.approx(500.0, abs=1.0)

    def test_multi_currency_starting_cash_is_converted_never_summed_raw(self) -> None:
        """US-34.3 AC1/AC6 — the US-31.3 currency-mixed trap, restated.

        Summing 1,000 USD and 1,000 EUR as 2,000 would be meaningless. Each
        balance converts at the window start before it enters the anchor.
        """
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = ImportedPortfolioSnapshot.model_validate(
            imported_snapshot(
                positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
                cash_balances=[
                    {"currency": "USD", "starting_cash": 1000.0, "ending_cash": 1000.0},
                    {"currency": "EUR", "starting_cash": 1000.0, "ending_cash": 1000.0},
                ],
                statement_overrides={
                    "statement_period": "2025-01-02 - 2025-01-03",
                    "base_currency": "USD",
                },
            )
        )
        snapshot.statement_totals = ImportedStatementTotals(starting_nav=1500.0, cash_total=2000.0)
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, states = _build(
            snapshot, price_histories, dates, fx_history=_static_fx(dates, {"EURUSD": 1.20})
        )

        # 1,000 USD + (1,000 EUR x 1.20) = 2,200 - never the raw 2,000.
        assert states[0].cash["USD"] == pytest.approx(2_200.0, abs=0.01)
        assert engine.cash_anchor.basis == "statement_starting_cash"

    def test_cash_anchor_verified_when_dates_align(self) -> None:
        # Statement period starts the same day the replay window does, and the
        # cash reconciles - the anchor may claim `verified`.
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = ImportedPortfolioSnapshot.model_validate(
            imported_snapshot(
                positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
                statement_overrides={
                    "statement_period": "2025-01-02 - 2025-01-03",
                    "base_currency": "USD",
                },
            )
        )
        snapshot.statement_totals = ImportedStatementTotals(starting_nav=1500.0, cash_total=500.0)
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, _states = _build(snapshot, price_histories, dates)

        assert engine.cash_anchor is not None
        assert engine.cash_anchor.nav_as_of == "2025-01-02"
        assert engine.cash_anchor.window_start == "2025-01-02"
        assert engine.cash_anchor.residual == pytest.approx(0.0, abs=1.0)
        assert engine.cash_anchor.trust == "verified"

    def test_implied_opening_cash_uses_converted_flows(self, ib2026_snapshot) -> None:
        """AC3 trap guard: the implied opening cash must use FX-CONVERTED ledger
        flows. The raw per-currency sum is currency-mixed and gives a wrong
        figure - it must never be the basis."""
        snapshot = ib2026_snapshot
        totals = snapshot.statement_totals
        raw_mixed = sum(e.cash_effect or 0.0 for e in snapshot_to_ledger(snapshot))
        # US-33.4: -271.23 on the pre-refresh statement. The pin exists to prove
        # the raw sum is a DIFFERENT number from the converted one, not for its
        # own sake.
        assert raw_mixed == pytest.approx(-1_549.28, abs=1.0), "raw currency-mixed sum pin"

        rates = totals.fx_rates or {}

        def to_base(value, currency, day):
            if currency == "USD":
                return value
            return value * rates.get(currency + "USD", 1.0)

        engine = PortfolioStateEngine(
            snapshot=snapshot, base_currency="USD", fx_history={}, symbol_fund_currencies={}
        )
        implied = engine._statement_implied_opening_cash(to_base)

        # US-33.4: on the pre-refresh statement the converted flow was -2,459.29
        # -> implied opening cash 4,452.94. The 2026-08-11 statement gives
        # 4,625.35; the invariant is that it differs materially from the raw
        # basis below, which is what AC3 of US-31.3 guards.
        assert implied == pytest.approx(4_625.35, abs=2.0)
        # The wrong (raw) basis is explicitly rejected.
        wrong = totals.cash_total - raw_mixed
        assert abs(implied - wrong) > 100.0


class TestTerminalReconciliationAdjustment:
    def test_terminal_state_records_reconciliation_adjustment(self, ib2026_snapshot) -> None:
        from app.analytics.performance import build_replay_currency_context

        snapshot = ib2026_snapshot
        market_data = FrozenMarketData.from_file()
        hd = [e.trade_date.isoformat() for e in snapshot.ledger_entries if e.trade_date]
        hd += [p.as_of_date.isoformat() for p in snapshot.positions if p.as_of_date]
        start, end = min(hd), max(hd)
        vd = sorted({r["date"] for r in market_data.get_historical_prices("SPY", start, end)})
        syms = replay_symbol_universe(snapshot)
        ph = market_data.get_historical_prices_for_symbols(syms, start, end)
        fund_ccy, fx = build_replay_currency_context(snapshot, syms, vd)

        _engine, states = _build(
            snapshot, ph, vd, reconcile=True, fx_history=fx, symbol_fund_currencies=fund_ccy
        )

        # US-33.4: 1,197.88 on the pre-refresh statement.
        # US-34.3: 1,366.17 before the anchor moved to the statement's own
        # starting cash.
        assert states[-1].reconciliation_adjustment == pytest.approx(-58.11, abs=2.0)
        assert all(s.reconciliation_adjustment is None for s in states[:-1])
        # US-33.4: non-terminal days are publishable unless they carry a
        # withheld symbol's unbacked cash flow (US-33.2) — on IB2026 that is
        # LQQ's six trade dates, and nothing else.
        # US-34.4: 2026-06-10 ($25.09) and 2026-06-23 ($5.13) dropped out once
        # the unbacked-cash guard became a share of portfolio value rather than
        # the $1.00 rounding tolerance — they distort nothing measurable.
        unpublishable = [s.date for s in states if not s.return_is_publishable]
        assert unpublishable == [
            "2026-04-14",
            "2026-04-17",
            "2026-06-12",
            "2026-07-17",
        ]
        assert all(s.unbacked_cash_flow for s in states[:-1] if not s.return_is_publishable)
        # US-34.8: ...and that day's return IS publishable again — computed from
        # the market-derived value, so the adjustment never enters it.
        assert states[-1].return_is_publishable is True
        # No state is withheld for a RECONCILIATION reason except the terminal
        # one — the six above are the separate US-33.2 unbacked-cash case.
        assert not [
            s for s in states[:-1] if s.reconciliation_adjustment is not None
        ]

    def test_terminal_return_is_unmoved_by_the_size_of_the_adjustment(self) -> None:
        """US-34.8 AC2 — the guarantee, asserted directly.

        US-31.3 required that an accounting adjustment never be published as a
        return, and enforced it by blanking the day. US-34.8 enforces it by
        computing the day on the market-derived value instead, which is a
        stronger claim: the published return must be IDENTICAL whatever the
        adjustment is. This fails if the adjustment ever reaches the figure.
        """
        from app.analytics.performance import _time_weighted_daily_return

        previous = DailyPortfolioState(
            date="2025-01-02",
            cash={"USD": 0.0},
            positions=[],
            total_market_value=1000.0,
            total_portfolio_value=1000.0,
            external_cash_flow=0.0,
        )

        def _terminal(adjustment: float) -> DailyPortfolioState:
            # `total_portfolio_value` is the RECONCILED level, so a bigger
            # adjustment means the same market outcome snapped further.
            return DailyPortfolioState(
                date="2025-01-03",
                cash={"USD": 0.0},
                positions=[],
                total_market_value=1100.0,
                total_portfolio_value=1100.0 + adjustment,
                external_cash_flow=0.0,
                reconciliation_adjustment=adjustment,
            )

        baseline = _time_weighted_daily_return(previous, _terminal(0.0))
        assert baseline == pytest.approx(0.10)
        for adjustment in (500.0, -500.0, 5_000.0):
            state = _terminal(adjustment)
            assert state.return_is_publishable is True
            assert _time_weighted_daily_return(previous, state) == pytest.approx(baseline)

    def test_no_reconciliation_adjustment_when_states_reconcile(self) -> None:
        # Terminal value already equals the statement's ending NAV -> the
        # adjustment is sub-tolerance and the day's return stays publishable.
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = ImportedPortfolioSnapshot.model_validate(
            imported_snapshot(
                positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
                statement_overrides={
                    "statement_period": "2025-01-02 - 2025-01-03",
                    "base_currency": "USD",
                },
            )
        )
        snapshot.statement_totals = ImportedStatementTotals(
            starting_nav=1500.0, cash_total=500.0, ending_nav=1500.0
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        _engine, states = _build(snapshot, price_histories, dates, reconcile=True)

        assert abs(states[-1].reconciliation_adjustment or 0.0) <= 1.0
        assert states[-1].return_is_publishable is True

    def test_request_path_snapshot_has_no_reconciliation(self) -> None:
        # No statement_totals (the request path) -> nothing to reconcile, no
        # adjustment anywhere, and the anchor comes from real cash balances.
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            cash_balances=[{"currency": "USD", "ending_cash": 250.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, states = _build(snapshot, price_histories, dates, reconcile=True)

        assert all(s.reconciliation_adjustment is None for s in states)
        assert all(s.return_is_publishable for s in states)
        assert engine.cash_anchor is not None
        assert engine.cash_anchor.basis == "snapshot_cash_balances"
        assert states[0].cash["USD"] == pytest.approx(250.0)


class TestPerDayTradeFlow:
    """US-24.9: `DailyPortfolioState.trade_flow` — the net base-currency market
    value moved INTO the holdings by that day's BUY/SELL entries.

    Sign convention matters more than magnitude here: a sign error doubles the
    error the trade-neutral return chain is meant to cancel, so these tests
    assert the sign directly.
    """

    def test_buy_day_records_positive_trade_flow(self) -> None:
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            ledger_entries=[_trade("BUY", "AAA", "2025-01-03", quantity=4.0, price=100.0)],
            cash_balances=[{"currency": "USD", "ending_cash": 500.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        _engine, states = _build(snapshot, price_histories, dates)

        # A BUY's cash_effect is negative (cash leaves) while market value
        # arrives — the injection is its negation, so trade_flow is POSITIVE.
        assert states[0].trade_flow == pytest.approx(0.0)
        assert states[1].trade_flow == pytest.approx(400.0)
        # ...and it is not the (negative) cash movement itself.
        assert states[1].cash["USD"] < states[0].cash["USD"]

    def test_sell_day_records_negative_trade_flow(self) -> None:
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            ledger_entries=[_trade("SELL", "AAA", "2025-01-03", quantity=3.0, price=100.0)],
            cash_balances=[{"currency": "USD", "ending_cash": 500.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        _engine, states = _build(snapshot, price_histories, dates)

        assert states[1].trade_flow == pytest.approx(-300.0)

    def test_no_trade_day_records_exactly_zero(self) -> None:
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            cash_balances=[{"currency": "USD", "ending_cash": 500.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        _engine, states = _build(snapshot, price_histories, dates)

        assert [s.trade_flow for s in states] == [0.0, 0.0]

    def test_deposit_and_withdrawal_move_external_cash_flow_not_trade_flow(self) -> None:
        """The two flow concepts stay separate: investor money entering the
        account is NOT a transfer into the holdings sleeve."""
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            ledger_entries=[
                {
                    "entry_type": "DEPOSIT",
                    "trade_date": "2025-01-03",
                    "net_amount": 2500.0,
                    "currency": "USD",
                    "source_section": "Deposits & Withdrawals",
                },
                {
                    "entry_type": "WITHDRAWAL",
                    "trade_date": "2025-01-03",
                    "net_amount": -500.0,
                    "currency": "USD",
                    "source_section": "Deposits & Withdrawals",
                },
            ],
            cash_balances=[{"currency": "USD", "ending_cash": 500.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        _engine, states = _build(snapshot, price_histories, dates)

        assert states[1].external_cash_flow == pytest.approx(2000.0)
        assert states[1].trade_flow == pytest.approx(0.0)

    def test_multi_currency_trade_day_converts_each_entry_before_summing(self) -> None:
        """US-24.9 AC2 — the raw currency-mixed `cash_effect` sum is rejected.

        This is the US-31.3 measurement trap: adding a EUR amount to a USD
        amount produces a number in no currency at all.
        """
        dates = ["2025-01-02", "2025-01-03"]
        eur_buy = _trade("BUY", "EUE", "2025-01-03", quantity=10.0, price=100.0)
        eur_buy["currency"] = "EUR"
        snapshot = _snapshot(
            positions=[
                position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0),
                position("EUE", market_value=1100.0, quantity=10.0, close_price=100.0, currency="EUR"),
            ],
            ledger_entries=[
                _trade("BUY", "AAA", "2025-01-03", quantity=5.0, price=100.0),
                eur_buy,
            ],
            cash_balances=[{"currency": "USD", "ending_cash": 5000.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0), "EUE": _rows("EUE", dates, price=100.0)}

        _engine, states = _build(
            snapshot,
            price_histories,
            dates,
            fx_history=_static_fx(dates, {"EURUSD": 1.10}),
            symbol_fund_currencies={"EUE": "EUR"},
        )

        # Converted: 500 USD + (1000 EUR x 1.10) = 1,600.00
        assert states[1].trade_flow == pytest.approx(1600.0)
        # The raw, currency-mixed sum would have been 1,500 — explicitly rejected.
        assert states[1].trade_flow != pytest.approx(1500.0)

    def test_trade_in_an_unpriced_symbol_is_excluded_from_trade_flow(self) -> None:
        """US-24.9 — the fabrication guard found while measuring IB2026.

        A symbol with no price history and no statement anchor contributes 0 to
        `total_market_value`. Trading it therefore moves NO market value, so
        counting it in `trade_flow` would make the trade-neutral chain
        "neutralise" a leg that was never there — fabricating a return. On
        IB2026 2026-04-27 that was +9.43% on an otherwise flat day (selling the
        unpriced IUFS + IUHC for $5,341.92).
        """
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            ledger_entries=[
                _trade("BUY", "AAA", "2025-01-03", quantity=2.0, price=100.0),
                # GHOST is held and traded but never priced (no history, and no
                # current position to supply a statement close).
                _trade("SELL", "GHOST", "2025-01-03", quantity=50.0, price=20.0),
            ],
            cash_balances=[{"currency": "USD", "ending_cash": 500.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, states = _build(snapshot, price_histories, dates)

        # Only the priced AAA leg is neutralisable: +200, NOT +200 − 1,000.
        assert states[1].trade_flow == pytest.approx(200.0)
        # The GHOST sale still moves cash (it is real broker truth) and the
        # symbol is disclosed as unpriced rather than silently dropped.
        assert "GHOST" in engine.unpriced_replay_symbols


class TestTradePriceAnchor:
    """US-24.10: the third valuation tier — a symbol with no market history and
    no statement close price is valued at the broker's own execution price,
    carried FORWARD from that trade.

    Without it a round-trip position is worth $0 while held, so its BUY/SELL
    moves cash with no offsetting market value and the cash-inclusive TWR
    publishes the step as performance (IB2026: -7.90% / +9.61%).
    """

    def test_symbol_is_valued_at_its_buy_price_from_the_trade_day_onward(self) -> None:
        dates = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            # A genuine round trip: opening qty is 0, so the replay holds GHOST
            # only between the BUY and the SELL (the IB2026 BTEC/IUFS/IUHC shape).
            ledger_entries=[
                _trade("BUY", "GHOST", "2025-01-03", quantity=50.0, price=20.0),
                _trade("SELL", "GHOST", "2025-01-07", quantity=50.0, price=21.0),
            ],
            cash_balances=[{"currency": "USD", "ending_cash": 5000.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, states = _build(snapshot, price_histories, dates)

        def ghost(state):
            return next((p for p in state.positions if p.symbol == "GHOST"), None)

        assert ghost(states[0]) is None  # not held yet
        assert ghost(states[1]).market_value == pytest.approx(1000.0)  # 50 x 20.00
        assert ghost(states[2]).market_value == pytest.approx(1000.0)  # carried flat
        assert "GHOST" in engine.trade_price_anchored_symbols

    def test_a_later_trade_updates_the_carried_price(self) -> None:
        dates = ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            ledger_entries=[
                _trade("BUY", "GHOST", "2025-01-02", quantity=100.0, price=20.0),
                _trade("BUY", "GHOST", "2025-01-06", quantity=100.0, price=25.0),
                _trade("SELL", "GHOST", "2025-01-07", quantity=200.0, price=26.0),
            ],
            cash_balances=[{"currency": "USD", "ending_cash": 9000.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        _engine, states = _build(snapshot, price_histories, dates)

        def ghost_value(state):
            return next(p for p in state.positions if p.symbol == "GHOST").market_value

        assert ghost_value(states[0]) == pytest.approx(2_000.0)   # 100 x 20
        assert ghost_value(states[1]) == pytest.approx(2_000.0)   # carried
        assert ghost_value(states[2]) == pytest.approx(5_000.0)   # 200 x 25 (last trade wins)

    def test_anchor_never_back_fills_before_the_first_trade(self) -> None:
        """US-27.7 rule: reaching backwards would fabricate a price for a date
        the broker never produced one. A position held BEFORE its first observed
        trade stays unvalued and disclosed."""
        dates = ["2025-01-02", "2025-01-03"]
        # GHOST is held at the window open (ending 0 + sold 100 => opening 100)
        # and its only observed trade is the SELL on the second day.
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            ledger_entries=[_trade("SELL", "GHOST", "2025-01-03", quantity=100.0, price=20.0)],
            cash_balances=[{"currency": "USD", "ending_cash": 500.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, states = _build(snapshot, price_histories, dates)

        opening_ghost = next(p for p in states[0].positions if p.symbol == "GHOST")
        assert opening_ghost.market_price is None
        assert opening_ghost.market_value is None
        assert "GHOST" in engine.unpriced_replay_symbols

    def test_precedence_history_then_statement_close_then_trade_price(self) -> None:
        """AC3, pinned in both directions: the two existing tiers are unchanged
        and always outrank the new one."""
        dates = ["2025-01-02", "2025-01-03"]
        snapshot = _snapshot(
            # AAA has real history; HELD has none but IS a current position, so
            # it keeps the statement close anchor even though it was traded.
            positions=[
                position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0),
                position("HELD", market_value=500.0, quantity=10.0, close_price=50.0),
            ],
            ledger_entries=[_trade("BUY", "HELD", "2025-01-03", quantity=2.0, price=999.0)],
            cash_balances=[{"currency": "USD", "ending_cash": 5000.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, states = _build(snapshot, price_histories, dates)

        aaa = next(p for p in states[1].positions if p.symbol == "AAA")
        held = next(p for p in states[1].positions if p.symbol == "HELD")
        assert aaa.market_price == pytest.approx(100.0)          # history wins
        assert held.market_price == pytest.approx(50.0)          # statement close, NOT 999.0
        assert "HELD" in engine.statement_anchored_symbols
        assert "HELD" not in engine.trade_price_anchored_symbols

    def test_anchor_converts_from_the_trade_settle_currency(self) -> None:
        """AC7 — a trade price is quoted in the currency it executed in, not the
        fund currency the US-31.5 rule picks for market-priced holdings."""
        dates = ["2025-01-02", "2025-01-03"]
        dates = ["2025-01-02", "2025-01-03", "2025-01-06"]
        eur_buy = _trade("BUY", "GHOST", "2025-01-03", quantity=100.0, price=10.0)
        eur_buy["currency"] = "EUR"
        eur_sell = _trade("SELL", "GHOST", "2025-01-06", quantity=100.0, price=10.0)
        eur_sell["currency"] = "EUR"
        snapshot = _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            ledger_entries=[eur_buy, eur_sell],
            cash_balances=[{"currency": "USD", "ending_cash": 5000.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        _engine, converted = _build(
            snapshot, price_histories, dates, fx_history=_static_fx(dates, {"EURUSD": 1.10})
        )
        ghost = next(p for p in converted[1].positions if p.symbol == "GHOST")
        assert ghost.market_value == pytest.approx(1_100.0)  # 100 x 10 EUR x 1.10

        # No rate: carried unconverted and the degradation is recorded — never
        # a silent 1:1 conversion claim (US-27.8).
        engine_no_fx, unconverted = _build(snapshot, price_histories, dates)
        ghost_raw = next(p for p in unconverted[1].positions if p.symbol == "GHOST")
        assert ghost_raw.market_value == pytest.approx(1_000.0)
        assert "EUR" in engine_no_fx.fx_fallback_currencies

    def test_disclosure_tiers_do_not_overlap_within_a_single_day(self) -> None:
        """US-24.10 AC5/AC6, restated by US-33.3 (Epic 33 F-3).

        Each of these three symbols is valued on a single basis for its whole
        life in this window, so the three lists are disjoint here — but that is
        a property of THIS fixture, not a guarantee about symbols. The general
        rule is per (symbol, day); see
        `test_symbol_can_appear_in_two_disclosure_lists_across_days`, which is
        the counter-example the original claim lacked.

        The assertions below are unchanged: a symbol the anchor cannot value is
        NOT reclassified out of the unpriced disclosure.
        """
        dates = ["2025-01-02", "2025-01-03", "2025-01-06"]
        snapshot = _snapshot(
            positions=[
                position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0),
                position("HELD", market_value=500.0, quantity=10.0, close_price=50.0),
            ],
            ledger_entries=[
                _trade("BUY", "GHOST", "2025-01-03", quantity=10.0, price=20.0),
                _trade("SELL", "GHOST", "2025-01-06", quantity=10.0, price=21.0),
                # NOPRICE is sold out of an opening position, so every day it is
                # held falls BEFORE its only observed trade price.
                _trade("SELL", "NOPRICE", "2025-01-03", quantity=10.0, price=20.0),
            ],
            cash_balances=[{"currency": "USD", "ending_cash": 5000.0}],
        )
        price_histories = {"AAA": _rows("AAA", dates, price=100.0)}

        engine, _states = _build(snapshot, price_histories, dates)

        assert engine.trade_price_anchored_symbols == {"GHOST"}
        assert engine.statement_anchored_symbols == {"HELD"}
        assert engine.unpriced_replay_symbols == {"NOPRICE"}
        assert not (engine.trade_price_anchored_symbols & engine.statement_anchored_symbols)
        assert not (engine.trade_price_anchored_symbols & engine.unpriced_replay_symbols)

    # -- US-33.3 (Epic 33 F-3): the claim the contract used to make --------
    #
    # US-24.10's AC5, the contract doc and the methodology all said a symbol
    # appears in EXACTLY ONE of the three disclosure lists. That was an
    # overstatement: `price_for` picks a tier per (symbol, DAY), while the
    # disclosure sets are unions over the whole window. A holding that predates
    # its own first trade is legitimately unpriced then, and trade-anchored
    # after. On the 2026-08-11 statement LQQ was live proof — until US-33.2
    # withheld it, which is why this fixture now has to carry the proof.

    LATE_TRADE_DATES = ["2025-01-02", "2025-01-03", "2025-01-06"]

    def _late_first_trade_snapshot(self):
        """Opening 10 units (0 ending + 20 sold − 10 bought), first trade day 2."""
        return _snapshot(
            positions=[position("AAA", market_value=1000.0, quantity=10.0, close_price=100.0)],
            ledger_entries=[
                _trade("BUY", "LATE", "2025-01-03", quantity=10.0, price=20.0),
                _trade("SELL", "LATE", "2025-01-06", quantity=20.0, price=21.0),
            ],
            cash_balances=[{"currency": "USD", "ending_cash": 5000.0}],
        )

    def test_symbol_can_appear_in_two_disclosure_lists_across_days(self) -> None:
        """US-33.3 AC3 — the counter-example, asserted rather than asserted away.

        LATE is held from the window open but has no observed price until its
        day-2 BUY: unpriced on day one, trade-anchored from day two. Both lists
        name it, and both are telling the truth about different days.
        """
        dates = self.LATE_TRADE_DATES
        engine, states = _build(
            self._late_first_trade_snapshot(), {"AAA": _rows("AAA", dates, price=100.0)}, dates
        )

        assert "LATE" in engine.unpriced_replay_symbols
        assert "LATE" in engine.trade_price_anchored_symbols

        by_date = {
            state.date: next((p for p in state.positions if p.symbol == "LATE"), None)
            for state in states
        }
        # Day one: held (10 units), no price of any kind — never back-filled
        # from the later trade (the US-27.7 no-back-fill rule).
        assert by_date["2025-01-02"] is not None
        assert by_date["2025-01-02"].market_price is None
        # Day two onward: the broker's own execution price, carried forward.
        assert by_date["2025-01-03"].market_price == 20.0
        assert by_date["2025-01-03"].quantity == 20.0

    def test_each_symbol_day_is_valued_by_exactly_one_tier(self) -> None:
        """US-33.3 AC4 — the guarantee that IS made, pinned per symbol-day.

        Exclusivity is a property of a (symbol, day) valuation: a day's price
        comes from market history, or the statement close, or a carried trade
        price, or nowhere. A change that let two tiers value one symbol-day
        would fail here.
        """
        dates = self.LATE_TRADE_DATES
        snapshot = self._late_first_trade_snapshot()
        engine, states = _build(snapshot, {"AAA": _rows("AAA", dates, price=100.0)}, dates)

        market_history = {"AAA"}
        statement_close = {p.symbol for p in snapshot.positions if p.close_price is not None}
        for state in states:
            for item in state.positions:
                tiers = 0
                if item.symbol in market_history:
                    tiers += 1
                elif item.symbol in statement_close:
                    tiers += 1
                elif item.market_price is not None:
                    # Only a carried trade price can be left, and only at or
                    # after the symbol's first trade.
                    tiers += 1
                    assert state.date >= "2025-01-03"
                assert tiers <= 1, f"{item.symbol} on {state.date} was valued by {tiers} tiers"

        assert engine.statement_anchored_symbols == set()
