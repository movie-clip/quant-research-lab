"""US-44.1 — Risk-tab annualized volatility publication gate.

Covers ``_build_risk_tab_annualized_volatility`` (the pure server-side
classifier) and the two integration paths that feed it: ``run_diagnostics_engine``
at / above and below the 60 paired-observation floor, and
``build_unavailable_diagnostics_result``.

The gate keys on ``risk_summary.observations`` (paired portfolio + benchmark
daily returns), classified before any value is selected, and never recomputes:
at ``N >= RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS`` it copies
``risk_summary.portfolio_volatility_pct`` straight through, byte-identical to the
Dashboard's ``volatility_summary.portfolio_volatility_pct`` in the same response.

Boundary cases reference ``RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS`` by name,
never a literal ``60``; the value itself is pinned once, in
``test_floor_constant_value_is_pinned``.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from app.core.constants import RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS
from app.schemas.diagnostics import DiagnosticsEngineRequest, RiskTabAnnualizedVolatility
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import (
    PortfolioCashBalanceSnapshot,
    PortfolioHistoryContext,
    PortfolioPositionSnapshot,
)
from app.schemas.reconciliation import PortfolioRiskSummary
from app.services.diagnostics_engine import (
    _build_risk_tab_annualized_volatility,
    build_unavailable_diagnostics_result,
    run_diagnostics_engine,
)
from app.tests.fixtures import imported_snapshot, position

FLOOR = RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS


def _risk_summary(
    *, observations: int, portfolio_volatility_pct: float | None
) -> PortfolioRiskSummary:
    """A minimal populated ``PortfolioRiskSummary`` — only ``observations`` and
    ``portfolio_volatility_pct`` matter to the classifier under test."""
    return PortfolioRiskSummary(
        benchmark_symbol="SPY",
        methodology="historical regression vs SPY daily returns",
        start_date="2025-01-02",
        end_date="2025-06-30",
        observations=observations,
        portfolio_beta=1.0,
        portfolio_correlation=0.8,
        r_squared=0.64,
        portfolio_volatility_pct=portfolio_volatility_pct,
        benchmark_volatility_pct=12.4,
    )


# ---------------------------------------------------------------------------
# The pure classifier — _build_risk_tab_annualized_volatility
# ---------------------------------------------------------------------------


def test_zero_observations_is_unavailable_with_null_value() -> None:
    result = _build_risk_tab_annualized_volatility(
        _risk_summary(observations=0, portfolio_volatility_pct=None)
    )

    assert result.trust == "unavailable"
    assert result.annualized_volatility_pct is None
    assert result.observations == 0
    assert result.minimum_observations == FLOOR


@pytest.mark.parametrize("n", [1, 2, 30, FLOOR - 2, FLOOR - 1])
def test_below_floor_is_withheld_and_never_exposes_a_value(n: int) -> None:
    # A real volatility value is present on the risk summary; the gate must
    # still drop it below the floor — withheld carries no number.
    result = _build_risk_tab_annualized_volatility(
        _risk_summary(observations=n, portfolio_volatility_pct=18.2)
    )

    assert result.trust == "withheld"
    assert result.annualized_volatility_pct is None
    assert result.observations == n
    assert result.minimum_observations == FLOOR


def test_n_equals_one_never_publishes_a_zero_on_this_field() -> None:
    # The reused ``_calculate_annualized_volatility`` path yields 0.0 at N == 1
    # (``len(values) < 2 -> 0.0``). This field classifies on the observation
    # count first, so N == 1 is withheld and the value stays null — never 0.0.
    result = _build_risk_tab_annualized_volatility(
        _risk_summary(observations=1, portfolio_volatility_pct=0.0)
    )

    assert result.trust == "withheld"
    assert result.annualized_volatility_pct is None
    assert result.annualized_volatility_pct != 0.0


@pytest.mark.parametrize("n", [FLOOR, FLOOR + 1, 252])
def test_at_or_above_floor_publishes_synthetic_number(n: int) -> None:
    result = _build_risk_tab_annualized_volatility(
        _risk_summary(observations=n, portfolio_volatility_pct=18.27)
    )

    assert result.trust == "synthetic"
    assert isinstance(result.annualized_volatility_pct, float)
    assert result.annualized_volatility_pct == 18.27
    assert result.observations == n
    assert result.minimum_observations == FLOOR


def test_published_value_is_byte_identical_to_risk_summary_scalar() -> None:
    # No recomputation: the published figure is the exact same float object's
    # value as ``risk_summary.portfolio_volatility_pct`` — assert to the bit,
    # not just to 2dp equality (guardrail 2 / AC 5).
    risk_summary = _risk_summary(
        observations=FLOOR + 5, portfolio_volatility_pct=13.336666666666667
    )
    result = _build_risk_tab_annualized_volatility(risk_summary)

    assert result.annualized_volatility_pct is not None
    assert (
        result.annualized_volatility_pct.hex()
        == risk_summary.portfolio_volatility_pct.hex()
    )


def test_zero_variance_series_at_floor_publishes_0_pct_not_withheld() -> None:
    # Human ruling for US-44.1: a constant return series at N >= floor (sample
    # stdev 0) publishes 0.00% — realized volatility is a well-defined
    # dispersion statistic at exactly zero, not an undefined ratio. There is NO
    # withheld branch for zero variance.
    result = _build_risk_tab_annualized_volatility(
        _risk_summary(observations=FLOOR, portfolio_volatility_pct=0.0)
    )

    assert result.trust == "synthetic"
    assert result.annualized_volatility_pct == 0.0


def test_withheld_serializes_distinct_from_unavailable() -> None:
    # Guardrail 4: the two below-floor rungs must not collapse. Both carry a
    # null value, so the ``trust`` string is the only thing that separates
    # them — assert it survives serialization on both paths.
    withheld = _build_risk_tab_annualized_volatility(
        _risk_summary(observations=10, portfolio_volatility_pct=18.2)
    )
    unavailable = _build_risk_tab_annualized_volatility(
        _risk_summary(observations=0, portfolio_volatility_pct=None)
    )

    assert withheld.model_dump()["trust"] == "withheld"
    assert unavailable.model_dump()["trust"] == "unavailable"
    assert withheld.model_dump()["trust"] != unavailable.model_dump()["trust"]
    # The withheld rung never leaks the word "unavailable" through JSON.
    assert "withheld" in withheld.model_dump_json()
    assert "unavailable" not in withheld.model_dump_json()


def test_floor_constant_value_is_pinned() -> None:
    # The one place the literal 60 is asserted (pack rule: pin a default in
    # exactly one dedicated test). Every other case reads the constant.
    assert RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS == 60


# ---------------------------------------------------------------------------
# Integration — build_unavailable_diagnostics_result
# ---------------------------------------------------------------------------


def test_build_unavailable_diagnostics_result_marks_risk_tab_volatility_unavailable() -> None:
    snapshot = ImportedPortfolioSnapshot.model_validate(
        imported_snapshot(positions=[position("AAPL", 1000.0)])
    )

    result = build_unavailable_diagnostics_result(snapshot, "SPY")

    assert result.risk_summary.observations == 0
    assert result.risk_tab_volatility.trust == "unavailable"
    assert result.risk_tab_volatility.annualized_volatility_pct is None
    assert (
        result.risk_tab_volatility.minimum_observations
        == RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS
    )


# ---------------------------------------------------------------------------
# Integration + cross-surface — run_diagnostics_engine
# ---------------------------------------------------------------------------


def _diagnostics_request(history_start: str, history_end: str) -> DiagnosticsEngineRequest:
    return DiagnosticsEngineRequest(
        benchmark_symbol="SPY",
        base_currency="USD",
        statement_period=f"{history_start} - {history_end}",
        imported_at=datetime.fromisoformat(f"{history_end}T00:00:00"),
        importer="interactive_brokers",
        source_file_names=["snapshot.json"],
        positions=[
            PortfolioPositionSnapshot(
                symbol="AAPL", market_value=1000.0, quantity=10.0, currency="USD"
            )
        ],
        cash_balances=[PortfolioCashBalanceSnapshot(currency="USD", amount=100.0)],
        history_context=PortfolioHistoryContext(
            benchmark_symbol="SPY",
            history_start_date=history_start,
            history_end_date=history_end,
        ),
    )


def test_run_diagnostics_engine_publishes_and_equals_dashboard_at_or_above_floor() -> None:
    # ~6 months of the conftest synthetic series -> well over 60 paired
    # observations. Cross-surface: the Risk-tab figure is the same scalar the
    # Dashboard shows (AC 4, AC 5).
    result = run_diagnostics_engine(_diagnostics_request("2025-01-02", "2025-06-30"))

    assert result.risk_summary.observations >= RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS

    rtv = result.risk_tab_volatility
    assert rtv.trust == "synthetic"
    assert isinstance(rtv.annualized_volatility_pct, float)
    assert rtv.annualized_volatility_pct == result.volatility_summary.portfolio_volatility_pct
    assert rtv.annualized_volatility_pct == result.risk_summary.portfolio_volatility_pct
    assert rtv.observations == result.risk_summary.observations
    assert rtv.minimum_observations == RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS


def test_run_diagnostics_engine_withholds_risk_tab_while_dashboard_stays_unfloored_below_floor() -> None:
    # ~3 weeks of history -> a handful of paired observations, safely inside the
    # 2 <= N < 60 divergence band. The Risk tab withholds (no number); the
    # Dashboard surface is unchanged and still publishes its unfloored estimate.
    result = run_diagnostics_engine(_diagnostics_request("2025-01-02", "2025-01-24"))

    n = result.risk_summary.observations
    assert 2 <= n < RISK_TAB_ANNUALIZED_VOL_MIN_OBSERVATIONS

    rtv = result.risk_tab_volatility
    assert rtv.trust == "withheld"
    assert rtv.annualized_volatility_pct is None
    assert rtv.observations == n

    # Regression: Dashboard surface unfloored / unchanged — a real number here.
    assert result.volatility_summary.portfolio_volatility_pct is not None
    assert result.risk_summary.portfolio_volatility_pct is not None


def test_risk_tab_volatility_is_a_required_field_on_the_result() -> None:
    # US-44.1 decision 9: the field is required (no default), so every
    # construction path classifies. A DiagnosticsResult built without it is a
    # validation error.
    result = run_diagnostics_engine(_diagnostics_request("2025-01-02", "2025-06-30"))
    assert isinstance(result.risk_tab_volatility, RiskTabAnnualizedVolatility)
    assert "risk_tab_volatility" in result.model_dump()
