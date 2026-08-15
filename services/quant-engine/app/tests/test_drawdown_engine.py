"""Engine + route tests for the standalone drawdown analytics engine.

Service-level tests hit the FMP cache via MarketDataService (same pattern
as test_stress_engine.py and test_drift_engine.py). Route tests use
TestClient with the canonical PortfolioEngineRequest-shaped payload.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.drawdown import DrawdownEngineRequest
from app.services.drawdown_engine import run_drawdown_engine


def _make_request(**kwargs) -> DrawdownEngineRequest:
    """Same canonical helper shape as test_stress_engine._make_request — the
    PortfolioEngineRequest schema accepts the flat positions/imported_at/
    benchmark_symbol shape."""
    defaults = {
        "benchmark_symbol": "SPY",
        "positions": [
            {"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"},
            {"symbol": "MSFT", "market_value": 8000.0, "quantity": 25.0, "currency": "USD"},
        ],
        "cash_balances": [],
        "base_currency": "USD",
    }
    defaults.update(kwargs)
    return DrawdownEngineRequest(**defaults)


# ── Service-level tests ───────────────────────────────────────────────────────


def test_run_drawdown_engine_returns_synthetic_for_real_portfolio() -> None:
    """Real AAPL + MSFT portfolio over default window (None = max). FMP cache
    provides multi-year history → underwater curve is non-empty, scalars
    are populated, drawdown is non-positive."""
    request = _make_request()
    result = run_drawdown_engine(request)

    assert result.trust == "synthetic"
    assert len(result.underwater_series) >= 20
    assert result.current_drawdown_pct is not None
    assert result.max_drawdown_pct is not None
    # Drawdown is by construction ≤ 0
    assert result.max_drawdown_pct <= 0
    # Sanity: current is at least as good as the worst (or equal)
    assert result.current_drawdown_pct >= result.max_drawdown_pct


def test_run_drawdown_engine_returns_unavailable_when_no_positions() -> None:
    """Empty positions → fail-closed: trust='unavailable', every list empty,
    every scalar None. No fabrication."""
    request = _make_request(positions=[])
    result = run_drawdown_engine(request)

    assert result.trust == "unavailable"
    assert result.underwater_series == []
    assert result.episodes == []
    assert result.current_drawdown_pct is None
    assert result.max_drawdown_pct is None


# ── Route-level tests ─────────────────────────────────────────────────────────


def test_post_drawdown_run_returns_200_with_valid_response_shape() -> None:
    client = TestClient(app)
    response = client.post(
        "/engines/drawdown/run",
        json={
            "benchmark_symbol": "SPY",
            "positions": [
                {"symbol": "AAPL", "market_value": 10000.0, "quantity": 50.0, "currency": "USD"},
            ],
            "cash_balances": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    expected_keys = {
        "window_trading_days",
        "underwater_series",
        "current_drawdown_pct",
        "max_drawdown_pct",
        "episodes",
        "trust",
    }
    assert expected_keys <= body.keys()
    assert body["trust"] in ("synthetic", "unavailable")
    assert isinstance(body["underwater_series"], list)
    assert isinstance(body["episodes"], list)


def test_post_drawdown_run_returns_422_on_malformed_payload() -> None:
    """Wrong type for window_trading_days fails Pydantic validation with 422."""
    client = TestClient(app)
    response = client.post(
        "/engines/drawdown/run",
        json={"window_trading_days": "not-an-int"},
    )
    assert response.status_code == 422


# ── US-15.1: per-position decomposition wire-up ──────────────────────────────


def test_run_drawdown_engine_populates_decomposition_for_episodes_when_positions_present() -> None:
    """Real AAPL + MSFT portfolio: every episode in the response should carry
    decomposition fields with trust other than 'unavailable' (when synthetic
    history is available). Reconciliation invariant is checked inside the
    engine (raises if violated) so we just assert the fields look populated."""
    request = _make_request()
    result = run_drawdown_engine(request)

    assert result.trust == "synthetic"
    # At least one episode populated (real history usually has multiple).
    assert len(result.episodes) >= 1
    for episode in result.episodes:
        assert episode.decomposition_trust in {"synthetic", "partial"}
        assert episode.top_contributors is not None
        assert len(episode.top_contributors) >= 1
        # Residual is always non-null when decomposition ran.
        assert episode.decomposition_residual_pct is not None


def test_run_drawdown_engine_skips_decomposition_when_no_positions() -> None:
    """Empty positions → engine returns trust='unavailable' with empty
    episodes list (no decomposition runs). Sanity: no exception."""
    request = _make_request(positions=[])
    result = run_drawdown_engine(request)
    assert result.trust == "unavailable"
    assert result.episodes == []


def test_synthetic_path_dividend_exposure_is_bounded_on_this_statement() -> None:
    """US-34.7 AC5 (Epic 34 F-12) — where the price-basis exposure IS real.

    The synthetic construction applies CURRENT holdings to historical prices
    with a flat cash balance and no ledger, so a dividend appears only as the
    ex-date price drop with no offsetting receipt. That makes this path a genuine
    PRICE drawdown, overstated by roughly the yield across the lookback — unlike
    the replay path, whose ledger carries the cash.

    On the committed statement the exposure is negligible because only one
    current holding paid a dividend in the window. The assertion is a BOUND, not
    a pin: a dividend-heavy portfolio must surface here rather than pass
    silently.
    """
    from app.domain.ledger import snapshot_to_ledger
    from app.scripts.export_dashboard_goldens import _docs_statement_path, _repo_root
    from app.services.statement_importer import import_statements

    snapshot = import_statements(
        [str(_docs_statement_path(_repo_root(), "IB2026.csv", "IB2026.pdf", "2026.pdf"))]
    )
    held = {position.symbol for position in snapshot.positions}
    ledger = snapshot_to_ledger(snapshot)

    # Only dividends on symbols STILL HELD reach the synthetic path, because it
    # values current holdings — a since-sold payer never enters it.
    exposed = {
        entry.symbol
        for entry in ledger
        if entry.entry_type == "DIVIDEND" and entry.symbol in held
    }
    assert exposed == {"PYPL"}

    exposure = sum(
        entry.cash_effect or 0.0
        for entry in ledger
        if entry.entry_type == "DIVIDEND" and entry.symbol in held
    )
    nav = snapshot.statement_totals.ending_nav
    assert exposure / nav < 0.0005, (
        f"the synthetic drawdown's dividend overstatement is {exposure / nav:.4%} "
        "of NAV — above the documented bound, so it can no longer be treated as "
        "negligible (see financial-methodology.md, Wealth Index and Drawdown)"
    )

