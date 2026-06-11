from datetime import UTC, date, datetime
import math

import pytest

from app.schemas.imports import (
    ImportedCashBalance,
    ImportedInstrument,
    ImportedPortfolioSnapshot,
    ImportedPosition,
    ImportedStatement,
    ImportedStatementTotals,
)
from app.schemas.import_bootstrap import ImportAdmissionReviewDispositionV1
from app.services.import_admission import build_import_admission_summary
from app.services.import_engine import build_import_bootstrap_from_snapshot


def _snapshot(
    *,
    statement_totals: ImportedStatementTotals | None = None,
    instruments: list[ImportedInstrument] | None = None,
    cash_balances: list[ImportedCashBalance] | None = None,
    positions: list[ImportedPosition] | None = None,
) -> ImportedPortfolioSnapshot:
    statement = ImportedStatement(
        importer="interactive_brokers",
        imported_at=datetime(2026, 4, 10, tzinfo=UTC),
        source_path="C:/docs/IB2025.pdf",
        detected_format="pdf",
        account_id="U8516450",
        base_currency="USD",
        statement_period="2025-01-01 - 2025-12-31",
        page_count=25,
    )
    return ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=statement_totals,
        instruments=instruments if instruments is not None else [ImportedInstrument(symbol="AAPL", currency="USD", isin="US0378331005")],
        cash_balances=cash_balances if cash_balances is not None else [ImportedCashBalance(currency="USD", ending_cash=100.0)],
        positions=positions if positions is not None else [
            ImportedPosition(
                as_of_date=date(2025, 12, 31),
                symbol="AAPL",
                quantity=2,
                cost_basis=150.0,
                close_price=100.0,
                market_value=200.0,
                unrealized_pnl=50.0,
                currency="USD",
            )
        ],
        ledger_entries=[],
    )


def test_import_admission_summary_clean_pass() -> None:
    snapshot = _snapshot(statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=300.0))

    summary = build_import_admission_summary(snapshot)

    assert summary.schema_version == "import_admission_summary_v1"
    assert summary.decision == "admitted"
    assert summary.trust_level == "verified"
    # Superset assertion: the admission check set is intentionally extensible
    # (checks were added in US-19.1). Pin that the known checks all pass; a new
    # check that fails would still be caught by the decision/trust_level
    # assertions above. Tolerate additive checks.
    assert {
        "residual_cash_comparability": "pass",
        "symbol_security_identity_consistency": "pass",
        "parsed_position_market_value_comparability": "pass",
        "nav_market_value_comparability": "pass",
        "instrument_description_registry_consistency": "pass",
    }.items() <= {check.check_id: check.status for check in summary.checks}.items()
    assert summary.provenance.tolerance_policy == "absolute_currency_delta_lte_0.01_same_currency_only"


def test_import_admission_summary_missing_totals_degrades_without_pass() -> None:
    summary = build_import_admission_summary(_snapshot(statement_totals=None))
    checks = {check.check_id: check for check in summary.checks}

    assert summary.decision == "degraded"
    assert summary.trust_level == "degraded"
    assert checks["residual_cash_comparability"].status == "unavailable"
    assert checks["parsed_position_market_value_comparability"].status == "unavailable"
    assert checks["nav_market_value_comparability"].status == "unavailable"
    assert checks["residual_cash_comparability"].trust_impact == "degraded"


def test_import_admission_summary_nav_mismatch_withholds() -> None:
    snapshot = _snapshot(statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=325.0))

    summary = build_import_admission_summary(snapshot)
    nav_check = next(check for check in summary.checks if check.check_id == "nav_market_value_comparability")

    assert summary.decision == "withheld"
    assert summary.trust_level == "withheld"
    assert nav_check.status == "fail"
    assert nav_check.delta == -25.0


def test_import_admission_summary_position_market_value_mismatch_withholds() -> None:
    snapshot = _snapshot(statement_totals=ImportedStatementTotals(stock_total=250.0, cash_total=100.0, ending_nav=350.0))

    summary = build_import_admission_summary(snapshot)
    position_check = next(check for check in summary.checks if check.check_id == "parsed_position_market_value_comparability")

    assert summary.decision == "withheld"
    assert summary.trust_level == "withheld"
    assert position_check.status == "fail"
    assert position_check.delta == -50.0


def test_import_admission_summary_missing_position_market_value_evidence_degrades() -> None:
    position_without_market_value = ImportedPosition.model_construct(
        as_of_date=date(2025, 12, 31),
        symbol="AAPL",
        quantity=2,
        cost_basis=150.0,
        close_price=100.0,
        market_value=None,
        unrealized_pnl=50.0,
        currency="USD",
    )
    snapshot = _snapshot(
        statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=300.0),
        positions=[position_without_market_value],
    )

    summary = build_import_admission_summary(snapshot)
    position_check = next(check for check in summary.checks if check.check_id == "parsed_position_market_value_comparability")

    assert summary.decision == "degraded"
    assert summary.trust_level == "degraded"
    assert position_check.status == "unavailable"
    assert position_check.trust_impact == "degraded"
    assert "AAPL" in position_check.message


def test_import_admission_summary_missing_cash_amount_evidence_degrades_without_zero_fill() -> None:
    snapshot = _snapshot(
        statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=300.0),
        cash_balances=[ImportedCashBalance(currency="USD")],
    )

    summary = build_import_admission_summary(snapshot)
    cash_check = next(check for check in summary.checks if check.check_id == "residual_cash_comparability")

    assert summary.decision == "degraded"
    assert summary.trust_level == "degraded"
    assert cash_check.status == "unavailable"
    assert cash_check.trust_impact == "degraded"
    assert cash_check.observed is None


def test_import_admission_summary_cash_mismatch_withholds() -> None:
    snapshot = _snapshot(
        statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=125.0, ending_nav=325.0),
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
    )

    summary = build_import_admission_summary(snapshot)
    cash_check = next(check for check in summary.checks if check.check_id == "residual_cash_comparability")

    assert summary.decision == "withheld"
    assert summary.trust_level == "withheld"
    assert cash_check.status == "fail"
    assert cash_check.delta == -25.0


def test_import_admission_summary_non_finite_cash_evidence_degrades_without_numeric_evidence() -> None:
    snapshot = _snapshot(
        statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=math.inf, ending_nav=300.0),
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=100.0)],
    )

    summary = build_import_admission_summary(snapshot)
    cash_check = next(check for check in summary.checks if check.check_id == "residual_cash_comparability")

    assert summary.decision == "degraded"
    assert summary.trust_level == "degraded"
    assert cash_check.status == "unavailable"
    assert cash_check.trust_impact == "degraded"
    assert cash_check.observed is None
    assert cash_check.comparison is None
    assert cash_check.delta is None


def test_import_admission_summary_non_finite_position_evidence_degrades_without_numeric_evidence() -> None:
    non_finite_position = ImportedPosition.model_construct(
        as_of_date=date(2025, 12, 31),
        symbol="AAPL",
        quantity=2,
        cost_basis=150.0,
        close_price=100.0,
        market_value=math.nan,
        unrealized_pnl=50.0,
        currency="USD",
    )
    snapshot = _snapshot(
        statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=300.0),
        positions=[non_finite_position],
    )

    summary = build_import_admission_summary(snapshot)
    position_check = next(check for check in summary.checks if check.check_id == "parsed_position_market_value_comparability")

    assert summary.decision == "degraded"
    assert summary.trust_level == "degraded"
    assert position_check.status == "unavailable"
    assert position_check.trust_impact == "degraded"
    assert position_check.observed is None
    assert position_check.comparison is None
    assert position_check.delta is None


def test_import_admission_summary_currency_conflict_withholds() -> None:
    snapshot = _snapshot(
        statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=300.0),
        instruments=[ImportedInstrument(symbol="AAPL", currency="EUR", isin="US0378331005")],
    )

    summary = build_import_admission_summary(snapshot)
    identity_check = next(check for check in summary.checks if check.check_id == "symbol_security_identity_consistency")

    assert summary.decision == "withheld"
    assert summary.trust_level == "withheld"
    assert identity_check.status == "fail"
    assert identity_check.trust_impact == "withheld"
    assert "AAPL" in identity_check.message


def test_import_admission_summary_missing_instrument_identity_degrades() -> None:
    snapshot = _snapshot(statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=300.0), instruments=[])

    summary = build_import_admission_summary(snapshot)
    identity_check = next(check for check in summary.checks if check.check_id == "symbol_security_identity_consistency")

    assert summary.decision == "degraded"
    assert summary.trust_level == "degraded"
    assert identity_check.status == "warn"
    assert identity_check.trust_impact == "degraded"
    assert "AAPL" in identity_check.message


def test_import_admission_does_not_rewrite_imported_values() -> None:
    snapshot = _snapshot(statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=325.0))
    before = snapshot.model_dump(mode="json")

    response = build_import_bootstrap_from_snapshot(snapshot, "SPY", {})

    assert snapshot.model_dump(mode="json") == before
    assert response.snapshot.model_dump(mode="json") == before
    assert response.admission_summary.decision == "withheld"


def test_import_admission_review_disposition_accepts_allowed_values() -> None:
    evidence_summary = {
        "status": "fail",
        "trust_impact": "withheld",
        "message": "Statement ending NAV differs from stock plus cash total.",
        "affected_fields": ["statement_totals.ending_nav"],
        "observed": {"label": "parsed_nav", "value": 300.0},
        "comparison": {"label": "statement_nav", "value": 325.0},
        "delta": -25.0,
        "currency": "USD",
    }

    for disposition in ["accepted_known_exception", "needs_source_correction", "deferred"]:
        review = ImportAdmissionReviewDispositionV1.model_validate({
            "check_id": "nav_market_value_comparability",
            "disposition": disposition,
            "rationale": "Reviewed against the broker statement notes.",
            "reviewed_at": datetime(2026, 4, 10, tzinfo=UTC),
            "reviewer_label": "local reviewer",
            "snapshot_fingerprint": "snapshot:abc",
            "admission_summary_fingerprint": "admission:def",
            "evidence_summary": evidence_summary,
        })

        assert review.schema_version == "import_admission_review_disposition_v1"
        assert review.disposition == disposition


def test_import_admission_review_disposition_requires_non_empty_rationale() -> None:
    try:
        ImportAdmissionReviewDispositionV1.model_validate({
            "check_id": "nav_market_value_comparability",
            "disposition": "deferred",
            "rationale": "   ",
            "reviewed_at": datetime(2026, 4, 10, tzinfo=UTC),
            "reviewer_label": "local reviewer",
            "snapshot_fingerprint": "snapshot:abc",
            "admission_summary_fingerprint": "admission:def",
            "evidence_summary": {
                "status": "unavailable",
                "trust_impact": "degraded",
                "message": "Evidence unavailable.",
            },
        })
    except ValueError as error:
        assert "rationale" in str(error)
    else:
        raise AssertionError("blank rationale should fail validation")


def test_import_admission_schema_rejects_non_finite_evidence_and_pass_review_status() -> None:
    with pytest.raises(ValueError):
        ImportAdmissionReviewDispositionV1.model_validate({
            "check_id": "nav_market_value_comparability",
            "disposition": "deferred",
            "rationale": "Reviewed against the broker statement notes.",
            "reviewed_at": datetime(2026, 4, 10, tzinfo=UTC),
            "reviewer_label": "local reviewer",
            "snapshot_fingerprint": "snapshot:abc",
            "admission_summary_fingerprint": "admission:def",
            "evidence_summary": {
                "status": "warn",
                "trust_impact": "degraded",
                "message": "Non-finite evidence should not validate.",
                "affected_fields": ["statement_totals.cash_total"],
                "observed": {"label": "parsed_cash", "value": math.nan},
                "delta": math.inf,
            },
        })

    with pytest.raises(ValueError):
        ImportAdmissionReviewDispositionV1.model_validate({
            "check_id": "nav_market_value_comparability",
            "disposition": "deferred",
            "rationale": "Pass evidence is not reviewable.",
            "reviewed_at": datetime(2026, 4, 10, tzinfo=UTC),
            "reviewer_label": "local reviewer",
            "snapshot_fingerprint": "snapshot:abc",
            "admission_summary_fingerprint": "admission:def",
            "evidence_summary": {
                "status": "pass",
                "trust_impact": "none",
                "message": "Pass evidence should not validate.",
                "affected_fields": [],
            },
        })


def test_admission_flags_instrument_description_mismatch() -> None:
    # VUAA is registry-known as "Vanguard S&P 500 UCITS ETF"; a disjoint
    # description (different fund) must flag (US-19.1).
    snapshot = _snapshot(instruments=[
        ImportedInstrument(symbol="VUAA", currency="USD", description="iShares Core MSCI World UCITS ETF"),
    ])
    summary = build_import_admission_summary(snapshot)
    check = next(c for c in summary.checks if c.check_id == "instrument_description_registry_consistency")

    assert check.status == "warn"
    assert check.severity == "warning"
    assert check.trust_impact == "degraded"
    assert "VUAA" in check.message


def test_admission_instrument_description_consistent_passes() -> None:
    snapshot = _snapshot(instruments=[
        ImportedInstrument(symbol="VUAA", currency="USD", description="VANGUARD S&P 500 UCITS ETF USD ACC"),
    ])
    summary = build_import_admission_summary(snapshot)
    check = next(c for c in summary.checks if c.check_id == "instrument_description_registry_consistency")

    assert check.status == "pass"
    assert check.trust_impact == "none"


def test_admission_includes_instrument_description_check() -> None:
    summary = build_import_admission_summary(
        _snapshot(statement_totals=ImportedStatementTotals(stock_total=200.0, cash_total=100.0, ending_nav=300.0))
    )
    assert any(c.check_id == "instrument_description_registry_consistency" for c in summary.checks)
