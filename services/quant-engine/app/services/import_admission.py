from datetime import UTC, datetime
import math
from pathlib import Path

from app.schemas.import_bootstrap import (
    ImportAdmissionCheckV1,
    ImportAdmissionCheckValue,
    ImportAdmissionProvenanceV1,
    ImportAdmissionSummaryV1,
)
from app.schemas.imports import ImportedCashBalance, ImportedInstrument, ImportedPortfolioSnapshot, ImportedPosition


CURRENCY_TOLERANCE_ABSOLUTE = 0.01
TOLERANCE_POLICY = "absolute_currency_delta_lte_0.01_same_currency_only"


def _rounded(value: float | None) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), 2)


def _is_finite_number(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


def _non_finite_check(
    *,
    check_id: str,
    message: str,
    affected_fields: list[str],
    currency: str | None = None,
) -> ImportAdmissionCheckV1:
    return ImportAdmissionCheckV1(
        check_id=check_id,
        status="unavailable",
        severity="warning",
        trust_impact="degraded",
        message=message,
        affected_fields=affected_fields,
        currency=currency,
    )


def _cash_amount(balance: ImportedCashBalance) -> float:
    value = balance.ending_cash if balance.ending_cash is not None else balance.ending_settled_cash
    if value is None:
        raise ValueError("cash amount is missing")
    return float(value)


def _source_names(snapshot: ImportedPortfolioSnapshot) -> list[str]:
    names: list[str] = []
    for statement in snapshot.statements or [snapshot.statement]:
        source_path = statement.source_path
        if source_path:
            names.append(Path(source_path).name)
    return names


def _statement_ids(snapshot: ImportedPortfolioSnapshot) -> list[str]:
    ids: list[str] = []
    for statement in snapshot.statements or [snapshot.statement]:
        parts = [statement.importer]
        if statement.account_id:
            parts.append(statement.account_id)
        if statement.statement_period:
            parts.append(statement.statement_period)
        ids.append(":".join(parts))
    return ids


def _single_currency(currencies: set[str | None]) -> str | None:
    normalized = {currency for currency in currencies if currency}
    if len(normalized) == 1:
        return next(iter(normalized))
    return None


def _build_cash_check(snapshot: ImportedPortfolioSnapshot) -> ImportAdmissionCheckV1:
    totals = snapshot.statement_totals
    statement_currency = snapshot.statement.base_currency
    cash_currencies = {balance.currency for balance in snapshot.cash_balances}
    comparable_currency = _single_currency(cash_currencies | {statement_currency})

    if totals is None or totals.cash_total is None:
        return ImportAdmissionCheckV1(
            check_id="residual_cash_comparability",
            status="unavailable",
            severity="warning",
            trust_impact="degraded",
            message="Statement cash total is missing; residual cash comparability cannot be verified.",
            affected_fields=["statement_totals.cash_total", "cash_balances.ending_cash", "cash_balances.ending_settled_cash"],
            currency=comparable_currency,
        )

    if not _is_finite_number(totals.cash_total):
        return _non_finite_check(
            check_id="residual_cash_comparability",
            message="Statement cash total is non-finite; residual cash comparability cannot be verified.",
            affected_fields=["statement_totals.cash_total", "cash_balances.ending_cash", "cash_balances.ending_settled_cash"],
            currency=comparable_currency,
        )

    if comparable_currency is None:
        return ImportAdmissionCheckV1(
            check_id="residual_cash_comparability",
            status="unavailable",
            severity="warning",
            trust_impact="degraded",
            message="Cash balances are not comparable in a single statement currency.",
            affected_fields=["statement.base_currency", "cash_balances.currency", "statement_totals.cash_total"],
        )

    comparable_balances = [balance for balance in snapshot.cash_balances if balance.currency == comparable_currency]
    missing_cash_balances = [
        balance.currency
        for balance in comparable_balances
        if balance.ending_cash is None and balance.ending_settled_cash is None
    ]
    non_finite_cash_balances = [
        balance.currency
        for balance in comparable_balances
        if (balance.ending_cash is not None and not math.isfinite(balance.ending_cash))
        or (balance.ending_settled_cash is not None and not math.isfinite(balance.ending_settled_cash))
    ]
    if not comparable_balances or missing_cash_balances:
        return ImportAdmissionCheckV1(
            check_id="residual_cash_comparability",
            status="unavailable",
            severity="warning",
            trust_impact="degraded",
            message="Parsed cash amount evidence is missing; residual cash comparability cannot be verified.",
            affected_fields=["statement_totals.cash_total", "cash_balances.ending_cash", "cash_balances.ending_settled_cash"],
            comparison=ImportAdmissionCheckValue(label="statement_cash_total", value=_rounded(totals.cash_total)),
            currency=comparable_currency,
        )

    if non_finite_cash_balances:
        return _non_finite_check(
            check_id="residual_cash_comparability",
            message="Parsed cash amount evidence is non-finite; residual cash comparability cannot be verified.",
            affected_fields=["cash_balances.ending_cash", "cash_balances.ending_settled_cash", "statement_totals.cash_total"],
            currency=comparable_currency,
        )

    observed = sum(_cash_amount(balance) for balance in comparable_balances)
    comparison = totals.cash_total
    delta = observed - comparison
    if abs(delta) <= CURRENCY_TOLERANCE_ABSOLUTE:
        return ImportAdmissionCheckV1(
            check_id="residual_cash_comparability",
            status="pass",
            severity="info",
            trust_impact="none",
            message="Parsed residual cash matches statement cash total within tolerance.",
            affected_fields=["statement_totals.cash_total", "cash_balances.ending_cash", "cash_balances.ending_settled_cash"],
            observed=ImportAdmissionCheckValue(label="parsed_cash_balances", value=_rounded(observed)),
            comparison=ImportAdmissionCheckValue(label="statement_cash_total", value=_rounded(comparison)),
            delta=_rounded(delta),
            currency=comparable_currency,
        )

    return ImportAdmissionCheckV1(
        check_id="residual_cash_comparability",
        status="fail",
        severity="error",
        trust_impact="withheld",
        message="Parsed residual cash does not match statement cash total within tolerance.",
        affected_fields=["statement_totals.cash_total", "cash_balances.ending_cash", "cash_balances.ending_settled_cash"],
        observed=ImportAdmissionCheckValue(label="parsed_cash_balances", value=_rounded(observed)),
        comparison=ImportAdmissionCheckValue(label="statement_cash_total", value=_rounded(comparison)),
        delta=_rounded(delta),
        currency=comparable_currency,
    )


def _metadata_conflicts(position: ImportedPosition, instrument: ImportedInstrument) -> list[str]:
    conflicts: list[str] = []
    if instrument.currency and instrument.currency != position.currency:
        conflicts.append("currency")
    return conflicts


def _build_symbol_identity_check(snapshot: ImportedPortfolioSnapshot) -> ImportAdmissionCheckV1:
    instruments_by_symbol = {instrument.symbol: instrument for instrument in snapshot.instruments}
    missing_symbols: list[str] = []
    conflict_symbols: list[str] = []

    for position in snapshot.positions:
        instrument = instruments_by_symbol.get(position.symbol)
        if instrument is None or not instrument.symbol:
            missing_symbols.append(position.symbol)
            continue
        if _metadata_conflicts(position, instrument):
            conflict_symbols.append(position.symbol)

    if conflict_symbols:
        return ImportAdmissionCheckV1(
            check_id="symbol_security_identity_consistency",
            status="fail",
            severity="error",
            trust_impact="withheld",
            message=f"Imported instrument metadata conflicts with open positions for: {', '.join(conflict_symbols)}.",
            affected_fields=["positions.symbol", "positions.currency", "instruments.symbol", "instruments.currency"],
            observed=ImportAdmissionCheckValue(label="conflicting_symbols", value=", ".join(conflict_symbols)),
        )

    if missing_symbols:
        return ImportAdmissionCheckV1(
            check_id="symbol_security_identity_consistency",
            status="warn",
            severity="warning",
            trust_impact="degraded",
            message=f"Open positions lack imported instrument identity for: {', '.join(missing_symbols)}.",
            affected_fields=["positions.symbol", "instruments.symbol"],
            observed=ImportAdmissionCheckValue(label="missing_identity_symbols", value=", ".join(missing_symbols)),
        )

    return ImportAdmissionCheckV1(
        check_id="symbol_security_identity_consistency",
        status="pass",
        severity="info",
        trust_impact="none",
        message="Every open position has consistent imported instrument identity evidence.",
        affected_fields=["positions.symbol", "positions.currency", "instruments.symbol", "instruments.currency"],
    )


def _build_positions_market_value_check(snapshot: ImportedPortfolioSnapshot) -> ImportAdmissionCheckV1:
    totals = snapshot.statement_totals
    statement_currency = snapshot.statement.base_currency
    position_currencies = {position.currency for position in snapshot.positions}
    comparable_currency = _single_currency(position_currencies | {statement_currency})

    if totals is None or totals.stock_total is None:
        return ImportAdmissionCheckV1(
            check_id="parsed_position_market_value_comparability",
            status="unavailable",
            severity="warning",
            trust_impact="degraded",
            message="Statement stock total is missing; parsed position market value cannot be verified.",
            affected_fields=["statement_totals.stock_total", "positions.market_value"],
            currency=comparable_currency,
        )

    if not _is_finite_number(totals.stock_total):
        return _non_finite_check(
            check_id="parsed_position_market_value_comparability",
            message="Statement stock total is non-finite; parsed position market value cannot be verified.",
            affected_fields=["statement_totals.stock_total", "positions.market_value"],
            currency=comparable_currency,
        )

    if comparable_currency is None:
        return ImportAdmissionCheckV1(
            check_id="parsed_position_market_value_comparability",
            status="unavailable",
            severity="warning",
            trust_impact="degraded",
            message="Parsed position market value cannot be compared because positions and statement totals are not in one currency.",
            affected_fields=["statement.base_currency", "positions.currency", "statement_totals.stock_total"],
        )

    missing_market_value_symbols = [position.symbol for position in snapshot.positions if getattr(position, "market_value", None) is None]
    non_finite_market_value_symbols = [
        position.symbol
        for position in snapshot.positions
        if getattr(position, "market_value", None) is not None and not math.isfinite(position.market_value)
    ]
    if missing_market_value_symbols:
        return ImportAdmissionCheckV1(
            check_id="parsed_position_market_value_comparability",
            status="unavailable",
            severity="warning",
            trust_impact="degraded",
            message=f"Parsed position market value evidence is missing for: {', '.join(missing_market_value_symbols)}.",
            affected_fields=["positions.symbol", "positions.market_value", "statement_totals.stock_total"],
            observed=ImportAdmissionCheckValue(label="missing_market_value_symbols", value=", ".join(missing_market_value_symbols)),
            comparison=ImportAdmissionCheckValue(label="statement_stock_total", value=_rounded(totals.stock_total)),
            currency=comparable_currency,
        )

    if non_finite_market_value_symbols:
        return _non_finite_check(
            check_id="parsed_position_market_value_comparability",
            message=f"Parsed position market value evidence is non-finite for: {', '.join(non_finite_market_value_symbols)}.",
            affected_fields=["positions.symbol", "positions.market_value", "statement_totals.stock_total"],
            currency=comparable_currency,
        )

    observed = sum(position.market_value for position in snapshot.positions if position.currency == comparable_currency)
    comparison = totals.stock_total
    delta = observed - comparison
    if abs(delta) <= CURRENCY_TOLERANCE_ABSOLUTE:
        return ImportAdmissionCheckV1(
            check_id="parsed_position_market_value_comparability",
            status="pass",
            severity="info",
            trust_impact="none",
            message="Parsed position market values match statement stock total within tolerance.",
            affected_fields=["positions.market_value", "statement_totals.stock_total"],
            observed=ImportAdmissionCheckValue(label="parsed_position_market_value", value=_rounded(observed)),
            comparison=ImportAdmissionCheckValue(label="statement_stock_total", value=_rounded(comparison)),
            delta=_rounded(delta),
            currency=comparable_currency,
        )

    return ImportAdmissionCheckV1(
        check_id="parsed_position_market_value_comparability",
        status="fail",
        severity="error",
        trust_impact="withheld",
        message="Parsed position market values do not match statement stock total within tolerance.",
        affected_fields=["positions.market_value", "statement_totals.stock_total"],
        observed=ImportAdmissionCheckValue(label="parsed_position_market_value", value=_rounded(observed)),
        comparison=ImportAdmissionCheckValue(label="statement_stock_total", value=_rounded(comparison)),
        delta=_rounded(delta),
        currency=comparable_currency,
    )


def _build_nav_check(snapshot: ImportedPortfolioSnapshot) -> ImportAdmissionCheckV1:
    totals = snapshot.statement_totals
    statement_currency = snapshot.statement.base_currency
    position_currencies = {position.currency for position in snapshot.positions}
    cash_currencies = {balance.currency for balance in snapshot.cash_balances}
    comparable_currency = _single_currency(position_currencies | cash_currencies | {statement_currency})

    if totals is None or totals.ending_nav is None or totals.stock_total is None or totals.cash_total is None:
        return ImportAdmissionCheckV1(
            check_id="nav_market_value_comparability",
            status="unavailable",
            severity="warning",
            trust_impact="degraded",
            message="Statement ending NAV, stock total, and cash total are required for NAV comparability.",
            affected_fields=["statement_totals.ending_nav", "statement_totals.stock_total", "statement_totals.cash_total"],
            currency=comparable_currency,
        )

    if not _is_finite_number(totals.ending_nav) or not _is_finite_number(totals.stock_total) or not _is_finite_number(totals.cash_total):
        return _non_finite_check(
            check_id="nav_market_value_comparability",
            message="Statement NAV comparability inputs are non-finite; NAV comparability cannot be verified.",
            affected_fields=["statement_totals.ending_nav", "statement_totals.stock_total", "statement_totals.cash_total"],
            currency=comparable_currency,
        )

    if comparable_currency is None:
        return ImportAdmissionCheckV1(
            check_id="nav_market_value_comparability",
            status="unavailable",
            severity="warning",
            trust_impact="degraded",
            message="NAV cannot be compared because positions, cash, and statement totals are not in one currency.",
            affected_fields=["statement.base_currency", "positions.currency", "cash_balances.currency", "statement_totals.ending_nav"],
        )

    observed = totals.stock_total + totals.cash_total
    comparison = totals.ending_nav
    delta = observed - comparison
    if abs(delta) <= CURRENCY_TOLERANCE_ABSOLUTE:
        return ImportAdmissionCheckV1(
            check_id="nav_market_value_comparability",
            status="pass",
            severity="info",
            trust_impact="none",
            message="Statement ending NAV matches stock total plus cash total within tolerance.",
            affected_fields=["statement_totals.ending_nav", "statement_totals.stock_total", "statement_totals.cash_total"],
            observed=ImportAdmissionCheckValue(label="stock_total_plus_cash_total", value=_rounded(observed)),
            comparison=ImportAdmissionCheckValue(label="statement_ending_nav", value=_rounded(comparison)),
            delta=_rounded(delta),
            currency=comparable_currency,
        )

    return ImportAdmissionCheckV1(
        check_id="nav_market_value_comparability",
        status="fail",
        severity="error",
        trust_impact="withheld",
        message="Statement ending NAV does not match stock total plus cash total within tolerance.",
        affected_fields=["statement_totals.ending_nav", "statement_totals.stock_total", "statement_totals.cash_total"],
        observed=ImportAdmissionCheckValue(label="stock_total_plus_cash_total", value=_rounded(observed)),
        comparison=ImportAdmissionCheckValue(label="statement_ending_nav", value=_rounded(comparison)),
        delta=_rounded(delta),
        currency=comparable_currency,
    )


def build_import_admission_summary(snapshot: ImportedPortfolioSnapshot) -> ImportAdmissionSummaryV1:
    checks = [
        _build_cash_check(snapshot),
        _build_symbol_identity_check(snapshot),
        _build_positions_market_value_check(snapshot),
        _build_nav_check(snapshot),
    ]
    statuses = {check.status for check in checks}
    if "fail" in statuses:
        decision = "withheld"
        trust_level = "withheld"
    elif statuses <= {"pass"}:
        decision = "admitted"
        trust_level = "verified"
    else:
        decision = "degraded"
        trust_level = "degraded"

    return ImportAdmissionSummaryV1(
        decision=decision,
        trust_level=trust_level,
        checks=checks,
        provenance=ImportAdmissionProvenanceV1(
            importer=snapshot.statement.importer,
            statement_ids=_statement_ids(snapshot),
            source_names=_source_names(snapshot),
            generated_at=datetime.now(UTC),
            tolerance_policy=TOLERANCE_POLICY,
        ),
    )
