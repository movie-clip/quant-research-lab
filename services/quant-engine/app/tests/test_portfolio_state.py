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

from app.core.constants import SYNTHETIC_COVERAGE_DE_MINIMIS_WEIGHT
from app.domain.ledger import snapshot_to_ledger
from app.engine.portfolio_state import PortfolioStateEngine, replay_symbol_universe
from app.schemas.imports import ImportedPortfolioSnapshot, ImportedStatementTotals
from app.scripts.export_dashboard_goldens import _docs_statement_path, _repo_root
from app.scripts.frozen_market_data import FrozenMarketData
from app.services.statement_importer import import_statements
from app.tests.fixtures import imported_snapshot, position


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


def _trade(entry_type: str, symbol: str, trade_date: str, quantity: float, price: float) -> dict:
    return {
        "entry_type": entry_type,
        "trade_date": trade_date,
        "symbol": symbol,
        "quantity": quantity,
        "price": price,
        "net_amount": (-1 if entry_type == "BUY" else 1) * quantity * price,
        "currency": "USD",
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

        assert len(current) == 20, "IB2026 statement pin: 20 current holdings"
        # 63 = 38 non-zero opening positions ∪ 16 symbols bought AND sold
        # entirely inside the window ∪ 9 opened during the window and still
        # held. All three populations are valued by the replay on some day.
        assert len(universe) == 63
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

        # Pre-fix drift was $35,534.21 (PRD F-2); it is now $1,097.18 — a 96.9%
        # collapse, confirming F-1 as the dominant term of the plug. The residual
        # is LQQ's statement-close anchor (see the day-one test) and is US-31.3's
        # to remove.
        pre_fix_drift = 35_534.21
        assert abs(drift) == pytest.approx(1_097.18, abs=1.0)
        assert abs(drift) < 0.05 * pre_fix_drift, (
            f"F-1 is NOT the dominant term in the F-2 cash plug (drift={drift:,.2f}) — "
            "re-scope the PRD causal chain before starting US-31.3"
        )


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

        assert by_symbol["SXRV"].market_value == pytest.approx(8_654.45, abs=1.0)
        assert by_symbol["SEMI"].market_value == pytest.approx(3_580.07, abs=1.0)
        assert by_symbol["LQQ"].market_value == pytest.approx(2_339.80, abs=1.0)
        # DEFS (DEFS.L quotes USD): unchanged, never double-converted.
        assert by_symbol["DEFS"].market_value == pytest.approx(
            next(p for p in snapshot.positions if p.symbol == "DEFS").quantity
            * max(price_histories["DEFS"], key=lambda r: r["date"])["price"],
            abs=1.0,
        )
        assert terminal.total_market_value == pytest.approx(61_238.53, abs=2.0)


class TestCashAnchorDisclosure:
    """US-31.3 (Epic 31 F-2): the opening cash anchor discloses its provenance
    and trust. `starting_nav - opening_positions_value` is only sound when both
    terms share an as-of date."""

    def test_cash_anchor_discloses_date_mismatch(self, ib2026_snapshot) -> None:
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

        engine, _states = _build(snapshot, ph, vd, fx_history=fx, symbol_fund_currencies=fund_ccy)
        anchor = engine.cash_anchor

        assert anchor is not None
        # starting_nav is as of the statement-period start; the positions are
        # valued at the replay window start - five trading days apart.
        assert anchor.basis == "statement_nav_date_mismatch"
        assert anchor.nav_as_of == "2026-01-01"
        assert anchor.window_start == "2026-01-08"
        assert anchor.residual == pytest.approx(-1_196.61, abs=2.0)
        assert anchor.trust == "degraded"

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
        assert raw_mixed == pytest.approx(-271.23, abs=1.0), "raw currency-mixed sum pin"

        rates = totals.fx_rates or {}

        def to_base(value, currency, day):
            if currency == "USD":
                return value
            return value * rates.get(currency + "USD", 1.0)

        engine = PortfolioStateEngine(
            snapshot=snapshot, base_currency="USD", fx_history={}, symbol_fund_currencies={}
        )
        implied = engine._statement_implied_opening_cash(to_base)

        # Converted flow is -2,459.29 -> implied opening cash 4,452.94.
        assert implied == pytest.approx(4_452.94, abs=2.0)
        # The wrong (raw) basis would have given 2,264.88 - explicitly rejected.
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

        assert states[-1].reconciliation_adjustment == pytest.approx(1_197.88, abs=2.0)
        assert all(s.reconciliation_adjustment is None for s in states[:-1])
        # ...and that day's return is therefore not publishable.
        assert states[-1].return_is_publishable is False
        assert all(s.return_is_publishable for s in states[:-1])

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
