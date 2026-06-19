"""Tests for the factor return attribution engine.

Coverage:
  - build_factor_attribution() pure analytics function (no FMP calls)
  - /engines/attribution/run route structural test
  - Reconciliation identity, null propagation, unavailable state, no-alpha naming
"""
from __future__ import annotations

import datetime
import json

from fastapi.testclient import TestClient

from app.analytics.attribution import (
    ATTRIBUTION_METHODOLOGY_NOTE,
    build_factor_attribution,
)
from app.api.main import app
from app.schemas.attribution import FactorAttributionRequest
from app.schemas.reconciliation import DailyPortfolioState


# ── Synthetic data helpers ─────────────────────────────────────────────────────

def _make_daily_states(
    n: int,
    start_value: float = 10_000.0,
    daily_return: float = 0.001,
    start_date: datetime.date | None = None,
) -> list[DailyPortfolioState]:
    """Return n DailyPortfolioState objects with constant daily return.

    Consecutive states on calendar days (no weekday filtering); the analytics
    function is date-agnostic and only cares about intersection with factor dates.
    """
    if start_date is None:
        start_date = datetime.date(2024, 1, 2)
    states = []
    value = start_value
    for i in range(n):
        date = (start_date + datetime.timedelta(days=i)).isoformat()
        states.append(
            DailyPortfolioState(
                date=date,
                cash={"USD": value},
                positions=[],
                total_market_value=0.0,
                total_portfolio_value=round(value, 4),
                external_cash_flow=0.0,
            )
        )
        value *= 1.0 + daily_return
    return states


def _make_factor_rows(
    n: int,
    start_price: float = 100.0,
    daily_return: float = 0.0005,
    start_date: datetime.date | None = None,
) -> list[dict]:
    """Return n price-history rows for a single factor proxy.

    Starts one day before the daily_states so that the first daily_state date
    already has a factor return (needs price[d-1] and price[d]).
    """
    if start_date is None:
        start_date = datetime.date(2024, 1, 1)  # one day before default _make_daily_states start
    rows = []
    price = start_price
    for i in range(n):
        date = (start_date + datetime.timedelta(days=i)).isoformat()
        rows.append({"date": date, "price": round(price, 6)})
        price *= 1.0 + daily_return
    return rows


def _standard_histories(n_rows: int) -> dict[str, list[dict]]:
    """Factor histories for SPY (Market) and QQQ (Growth) only.

    Using only two factors keeps the test fast and deterministic.
    """
    return {
        "SPY": _make_factor_rows(n_rows, start_price=450.0, daily_return=0.0008),
        "QQQ": _make_factor_rows(n_rows, start_price=380.0, daily_return=0.001),
    }


# ── Analytics function tests ───────────────────────────────────────────────────

class TestBuildFactorAttributionReconciliation:
    """Reconciliation identity: Σ contributions + unexplained = r_p(t) on every date."""

    def test_reconciliation_holds_for_all_attributed_dates(self):
        # window=20, min_observations=20 → need ≥20 common dates.
        # 35 daily states → 34 portfolio return dates.
        # 36 factor rows (starting one day earlier) → 35 factor return dates.
        # common dates = 34 ∩ 35 = 34.  Non-null after index 19 = 15 dates.
        states = _make_daily_states(35, daily_return=0.001)
        histories = _standard_histories(36)
        result = build_factor_attribution(states, histories, window=20)

        assert result.attribution_status == "available"
        assert len(result.cumulative_series) > 0

        # Rebuild daily contributions from the cumulative series.
        prev_cumul: dict[str, float] = {}
        prev_unexplained = 0.0
        prev_portfolio = 0.0

        for i, entry in enumerate(result.cumulative_series):
            daily_portfolio = entry.cumul_portfolio_return - prev_portfolio
            daily_unexplained = entry.cumul_unexplained - prev_unexplained

            daily_sum = daily_unexplained
            for cp in entry.contributions:
                prev_cp = prev_cumul.get(cp.factor_key, 0.0)
                daily_sum += cp.cumul_contribution - prev_cp

            # Reconciliation: |Σ daily contrib + daily residual - r_p| < 1e-6
            assert abs(daily_sum - daily_portfolio) < 1e-6, (
                f"Reconciliation failed at entry {i} (date {entry.date}): "
                f"sum={daily_sum:.8f}, r_p={daily_portfolio:.8f}"
            )

            prev_cumul = {cp.factor_key: cp.cumul_contribution for cp in entry.contributions}
            prev_unexplained = entry.cumul_unexplained
            prev_portfolio = entry.cumul_portfolio_return


class TestBuildFactorAttributionWindows:
    """Different windows produce different numbers of non-null attributed dates."""

    def test_window_20_produces_fewer_entries_than_window_60(self):
        # Build enough history for both windows.
        # window=60, min_obs=75 → need ≥75 common dates.
        # Use 100 daily states → 99 portfolio return dates.
        # 101 factor rows → 100 factor return dates.
        # common = 99.  For w=60 non-null starts at index 74 → 25 entries.
        #             For w=20 non-null starts at index 24 → 75 entries.
        states = _make_daily_states(100, daily_return=0.001)
        histories = _standard_histories(101)

        result_20 = build_factor_attribution(states, histories, window=20)
        result_60 = build_factor_attribution(states, histories, window=60)

        assert result_20.attribution_status == "available"
        assert result_60.attribution_status == "available"
        assert len(result_20.cumulative_series) > len(result_60.cumulative_series)

    def test_window_parameter_is_reflected_in_response(self):
        states = _make_daily_states(100, daily_return=0.001)
        histories = _standard_histories(101)

        result = build_factor_attribution(states, histories, window=60)
        assert result.window == 60

    def test_window_252_requires_enough_history(self):
        # min_observations = window = 252. Only 30 common dates → unavailable.
        states = _make_daily_states(30, daily_return=0.001)
        histories = _standard_histories(31)
        result = build_factor_attribution(states, histories, window=252)
        assert result.attribution_status == "unavailable"
        assert result.cumulative_series == []


class TestBuildFactorAttributionUnavailable:
    """Unavailable state is emitted when history is insufficient."""

    def test_short_history_returns_unavailable(self):
        # Fewer than 20 common dates for window=20 → unavailable.
        states = _make_daily_states(10, daily_return=0.001)
        histories = _standard_histories(11)
        result = build_factor_attribution(states, histories, window=20)
        assert result.attribution_status == "unavailable"
        assert result.cumulative_series == []
        assert result.period_attribution == []
        assert result.total_portfolio_return_pct is None
        assert result.total_unexplained_pct is None

    def test_empty_daily_states_returns_unavailable(self):
        result = build_factor_attribution([], _standard_histories(20), window=20)
        assert result.attribution_status == "unavailable"

    def test_empty_factor_histories_returns_unavailable(self):
        states = _make_daily_states(40, daily_return=0.001)
        result = build_factor_attribution(states, {}, window=20)
        assert result.attribution_status == "unavailable"


class TestBuildFactorAttributionNoAlpha:
    """The residual must never be labelled 'alpha' in any field or serialized JSON."""

    def test_no_alpha_field_in_schema_or_json(self):
        states = _make_daily_states(40, daily_return=0.001)
        histories = _standard_histories(41)
        result = build_factor_attribution(states, histories, window=20)

        serialized = json.dumps(result.model_dump())
        assert "alpha" not in serialized.lower(), (
            "Found 'alpha' in serialized attribution response — "
            "the residual must be labelled 'unexplained' or 'idiosyncratic'."
        )

    def test_cumul_unexplained_field_exists(self):
        states = _make_daily_states(40, daily_return=0.001)
        histories = _standard_histories(41)
        result = build_factor_attribution(states, histories, window=20)
        assert result.attribution_status == "available"
        for entry in result.cumulative_series:
            assert hasattr(entry, "cumul_unexplained"), "cumul_unexplained field missing"


class TestBuildFactorAttributionPeriodTable:
    """Period attribution table has correct structure."""

    def test_period_table_has_rows_for_active_factors(self):
        states = _make_daily_states(40, daily_return=0.001)
        histories = _standard_histories(41)  # SPY + QQQ only
        result = build_factor_attribution(states, histories, window=20)
        assert result.attribution_status == "available"
        # Should have rows for market (SPY) and growth (QQQ) at minimum.
        assert len(result.period_attribution) >= 1

    def test_period_table_rows_have_required_fields(self):
        states = _make_daily_states(40, daily_return=0.001)
        histories = _standard_histories(41)
        result = build_factor_attribution(states, histories, window=20)
        for row in result.period_attribution:
            assert row.factor_key is not None
            assert row.factor_label is not None
            # avg_beta, factor_return_pct, contribution_pct can be None but must exist.
            assert hasattr(row, "avg_beta")
            assert hasattr(row, "factor_return_pct")
            assert hasattr(row, "contribution_pct")

    def test_total_portfolio_return_pct_is_not_none_when_available(self):
        states = _make_daily_states(40, daily_return=0.001)
        histories = _standard_histories(41)
        result = build_factor_attribution(states, histories, window=20)
        assert result.attribution_status == "available"
        assert result.total_portfolio_return_pct is not None
        assert result.total_unexplained_pct is not None

    def test_methodology_note_mentions_arithmetic(self):
        states = _make_daily_states(40, daily_return=0.001)
        histories = _standard_histories(41)
        result = build_factor_attribution(states, histories, window=20)
        assert "arithmetic" in result.methodology_note.lower()
        assert result.methodology_note == ATTRIBUTION_METHODOLOGY_NOTE


# ── Route / endpoint tests ─────────────────────────────────────────────────────

class TestAttributionRoute:
    """The /engines/attribution/run endpoint returns a valid JSON response."""

    def test_attribution_endpoint_exists_and_returns_200(self):
        client = TestClient(app)
        # Send a minimal valid ImportedPortfolioSnapshot with no positions.
        # The engine will return attribution_status="unavailable" (no market data
        # or no history), but the route must return HTTP 200 with valid JSON.
        payload = {
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2026-01-01T00:00:00",
                    "source_path": "/test/fixture.csv",
                    "detected_format": "ib_flex_2023",
                },
                "instruments": [],
                "cash_balances": [],
                "positions": [],
                "ledger_entries": [],
            },
            "window": 20,
            "benchmark_symbol": "SPY",
        }
        response = client.post("/engines/attribution/run", json=payload)
        assert response.status_code == 200

        body = response.json()
        assert "attribution_status" in body
        assert body["attribution_status"] in ("available", "unavailable")
        assert "window" in body
        assert body["window"] == 20
        assert "cumulative_series" in body
        assert "period_attribution" in body
        assert "methodology_note" in body
        assert "alpha" not in json.dumps(body).lower()

    def test_attribution_endpoint_unavailable_when_no_history(self):
        client = TestClient(app)
        payload = {
            "snapshot": {
                "statement": {
                    "importer": "interactive_brokers",
                    "imported_at": "2026-01-01T00:00:00",
                    "source_path": "/test/fixture.csv",
                    "detected_format": "ib_flex_2023",
                },
                "instruments": [],
                "cash_balances": [],
                "positions": [],
                "ledger_entries": [],
            },
            "window": 20,
        }
        response = client.post("/engines/attribution/run", json=payload)
        assert response.status_code == 200
        body = response.json()
        # No positions → engine returns unavailable immediately.
        assert body["attribution_status"] == "unavailable"
        assert body["cumulative_series"] == []
        assert body["period_attribution"] == []


# ── Engine lookback / display-span tests ────────────────────────────────────────

def _attr_price_rows(n_days: int = 520) -> list[dict]:
    """Synthetic daily prices ending today (non-constant returns)."""
    end = datetime.date.today()
    rows: list[dict] = []
    p = 100.0
    for i in range(n_days):
        d = end - datetime.timedelta(days=n_days - 1 - i)
        p = p * (1 + (0.001 if i % 2 else -0.0008) + 0.0002 * ((i % 5) - 2))
        rows.append({"date": d.isoformat(), "price": round(p, 4)})
    return rows


def _attr_snapshot_dict() -> dict:
    return {
        "statement": {
            "importer": "interactive_brokers",
            "imported_at": "2026-01-01T00:00:00",
            "source_path": "/test/fixture.csv",
            "detected_format": "ib_flex_2023",
        },
        "instruments": [],
        "cash_balances": [],
        "positions": [{
            "as_of_date": "2026-06-01", "symbol": "AAPL", "quantity": 10.0,
            "cost_basis": 800.0, "close_price": 100.0, "market_value": 1000.0,
            "unrealized_pnl": 200.0, "currency": "USD",
        }],
        "ledger_entries": [],
    }


class TestAttributionEngineLookback:
    """US-18.x fix: the cumulative series spans a fixed ~1y display window for
    every rolling window — it is no longer truncated to ~(1.6×window) days."""

    def test_20d_series_spans_full_display_range_not_just_window(self, mocker):
        from unittest.mock import MagicMock
        from app.services.attribution_engine import run_attribution_engine

        rows = _attr_price_rows(520)

        def _hist(sym, start, end, *a, **k):
            return [r for r in rows if start <= r["date"] <= end]

        mock = MagicMock()
        inst = mock.return_value
        inst.get_historical_prices.side_effect = _hist
        inst.get_historical_prices_for_symbols.side_effect = (
            lambda syms, a, b: {s: [r for r in rows if a <= r["date"] <= b] for s in syms}
        )
        mocker.patch("app.services.attribution_engine.MarketDataService", mock)

        resp = run_attribution_engine(FactorAttributionRequest.model_validate(
            {"snapshot": _attr_snapshot_dict(), "window": 20, "benchmark_symbol": "SPY"}
        ))

        assert resp.attribution_status == "available"
        # With the old window-scaled fetch (~62 calendar days) this would be ~40.
        # The fix fetches display(252)+window, so the 20d chart spans ~1 year.
        assert len(resp.cumulative_series) > 150


# ── Non-finite (NaN) guard regression (critical bug 2026-06-10) ─────────────────

def test_nonfinite_window_skipped_and_response_is_json_safe(monkeypatch):
    """A degenerate rolling window can make the OLS solve return a non-finite
    beta → NaN contributions that broke JSON serialization (500). The engine must
    skip such dates and never emit NaN."""
    import json
    import math as _math
    from app.analytics import attribution as attr_mod

    states = _make_daily_states(40, daily_return=0.001)
    histories = _standard_histories(41)

    real_fit = attr_mod._fit_factor_model
    calls = {"n": 0}

    def fake_fit(y_window, orth_window, ridge_lambda=1e-5):
        calls["n"] += 1
        coeffs, a, b = real_fit(y_window, orth_window, ridge_lambda=ridge_lambda)
        if calls["n"] == 1:
            coeffs = [float("nan")] * len(coeffs)  # simulate a degenerate window
        return coeffs, a, b

    monkeypatch.setattr(attr_mod, "_fit_factor_model", fake_fit)

    result = build_factor_attribution(states, histories, window=20)

    assert result.attribution_status == "available"
    # Replicates FastAPI's strict JSON render: raises if any NaN/inf is present.
    json.dumps(result.model_dump(), allow_nan=False)
    for entry in result.cumulative_series:
        assert _math.isfinite(entry.cumul_portfolio_return)
        assert _math.isfinite(entry.cumul_unexplained)
        for point in entry.contributions:
            assert _math.isfinite(point.cumul_contribution)
