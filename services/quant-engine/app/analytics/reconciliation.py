from app.domain.ledger import snapshot_to_ledger
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import ReconciliationCheck, ReconciliationSummary
from app.core.constants import STATEMENT_RECONCILIATION_TOLERANCE


def _statement_stock_total_in_base(snapshot: ImportedPortfolioSnapshot) -> float | None:
    if snapshot.statement_totals is None or snapshot.statement_totals.stock_total is None:
        return None

    # Convert each currency through the statement's own fx_rates. EUR keeps its
    # legacy default of 1.0 when no rate exists (the PDF path's behavior); any
    # other non-USD currency without a rate stays excluded from the sum,
    # exactly as before US-28.1 — so PDF snapshots reconcile identically,
    # while the CSV path (which supplies implied per-currency rates from the
    # statement's own Open Positions totals) converts them all.
    fx_rates = snapshot.statement_totals.fx_rates
    total = 0.0
    for position in snapshot.positions:
        if position.currency == "USD":
            total += position.market_value
            continue
        rate = fx_rates.get(f"{position.currency}USD")
        if rate is None:
            if position.currency != "EUR":
                continue
            rate = 1.0
        total += position.market_value * rate
    return round(total, 2)


def _negative_withholding_total(snapshot: ImportedPortfolioSnapshot) -> float:
    ledger = snapshot_to_ledger(snapshot)
    running_total = 0.0

    for entry in sorted(
        [
            candidate
            for candidate in ledger
            if candidate.entry_type == "WITHHOLDING_TAX"
        ],
        key=lambda item: (item.date, item.symbol or "", item.gross_amount or 0),
    ):
        # Credit-interest withholding counts: IBKR's own Withholding Tax total
        # includes it on every statement that has such rows (2023–2026,
        # verified US-28.1) — the former "Credit Interest" exclusion made the
        # check fail against the statement's own number.
        amount = round(entry.gross_amount or 0, 2)

        if amount > 0:
            running_total -= amount
            continue

        running_total += abs(amount)

    return round(running_total, 2)


def build_reconciliation_summary(snapshot: ImportedPortfolioSnapshot) -> ReconciliationSummary:
    ledger = snapshot_to_ledger(snapshot)
    totals = snapshot.statement_totals
    checks: list[ReconciliationCheck] = []

    position_market_value = _statement_stock_total_in_base(snapshot)
    dividends_actual = round(sum((entry.gross_amount or 0) for entry in ledger if entry.entry_type == "DIVIDEND"), 2)
    taxes_actual = _negative_withholding_total(snapshot)
    fees_actual = round(-sum((entry.gross_amount or 0) for entry in ledger if entry.entry_type == "FEE"), 2)
    interest_actual = round(sum((entry.gross_amount or 0) for entry in ledger if entry.entry_type == "INTEREST"), 2)
    deposits_actual = round(sum((entry.gross_amount or 0) for entry in ledger if entry.entry_type == "DEPOSIT"), 2)
    usd_cash_ending = round(sum((balance.ending_cash or 0) for balance in snapshot.cash_balances if balance.currency == "USD"), 2)

    def add_check(name: str, expected: float | int | None, actual: float | int | None, detail: str) -> None:
        difference = None
        passed = False
        if expected is None or actual is None:
            passed = False
        else:
            difference = round(float(actual) - float(expected), 2)
            passed = abs(difference) <= STATEMENT_RECONCILIATION_TOLERANCE

        checks.append(
            ReconciliationCheck(
                name=name,
                expected=expected,
                actual=actual,
                difference=difference,
                passed=passed,
                detail=detail,
            )
        )

    add_check("open_positions_market_value", totals.stock_total if totals else None, position_market_value, "Compares statement stock total with parsed open positions market value.")
    add_check("dividends_total", totals.dividends_total if totals else None, dividends_actual, "Compares statement dividend total with parsed dividend ledger entries.")
    add_check("withholding_tax_total", totals.withholding_tax_total if totals else None, taxes_actual, "Uses only negative withholding tax cash flows for the annual total.")
    add_check("interest_total", totals.interest_total if totals else None, interest_actual, "Compares statement interest total with parsed interest entries.")
    add_check("other_fees_total", totals.other_fees_total if totals else None, fees_actual, "Compares statement other fees total with parsed fee entries.")
    add_check("deposits_total", totals.deposits_total if totals else None, deposits_actual, "Compares statement deposits total with parsed deposit entries.")
    add_check("ending_usd_cash", totals.cash_total if totals else None, usd_cash_ending, "Compares statement USD ending cash with parsed cash report balances.")

    return ReconciliationSummary(passed=all(check.passed for check in checks), checks=checks)
