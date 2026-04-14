from __future__ import annotations

from datetime import date
from pathlib import Path
import re
from typing import Sequence

from app.importers.espp import preview_pdf_statement as preview_espp_statement
from app.importers.espp import import_statement as import_espp_statement
from app.importers.freedom24 import preview_pdf_statement as preview_freedom24_statement
from app.importers.freedom24 import import_statement as import_freedom24_statement
from app.importers.interactive_brokers import preview_pdf_statement as preview_interactive_brokers_statement
from app.importers.interactive_brokers import import_statement as import_interactive_brokers_statement
from app.schemas.imports import ImportedCashBalance, ImportedInstrument, ImportedLedgerEntry, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement, ImportedStatementTotals


def import_statement(path: str | Path) -> ImportedPortfolioSnapshot:
    statement_path = Path(path)
    suffix = statement_path.suffix.lower()
    if suffix != ".pdf":
        raise ValueError("Only PDF broker statements are currently supported")
    last_error: ValueError | None = None

    try:
        preview_interactive_brokers_statement(statement_path)
        return import_interactive_brokers_statement(statement_path)
    except ValueError:
        pass

    try:
        preview_freedom24_statement(statement_path)
        return import_freedom24_statement(statement_path)
    except ValueError as freedom24_error:
        last_error = freedom24_error

    try:
        preview_espp_statement(statement_path)
        return import_espp_statement(statement_path)
    except ValueError as espp_error:
        last_error = espp_error

    error_message = str(last_error) if last_error is not None else ""
    if error_message:
        raise ValueError(error_message) from last_error
    raise ValueError("Unsupported broker statement PDF") from last_error


def import_statements(paths: Sequence[str | Path]) -> ImportedPortfolioSnapshot:
    if not paths:
        raise ValueError("At least one broker statement is required")

    snapshots = [import_statement(path) for path in paths]
    if len(snapshots) == 1:
        return snapshots[0]

    return combine_imported_snapshots(snapshots)


def combine_imported_snapshots(snapshots: list[ImportedPortfolioSnapshot]) -> ImportedPortfolioSnapshot:
    if not snapshots:
        raise ValueError("At least one imported snapshot is required")
    if len(snapshots) == 1:
        return snapshots[0]

    ordered = sorted(snapshots, key=_snapshot_sort_key)
    _validate_compatible_snapshots(ordered)

    statements = _collect_statements(ordered)
    latest_snapshot = ordered[-1]
    importers = {statement.importer for statement in statements}
    terminal_snapshots = _latest_snapshot_by_account(ordered)
    combined_statement = ImportedStatement(
        importer=latest_snapshot.statement.importer if len(importers) == 1 else "multi_broker",
        imported_at=max(statement.imported_at for statement in statements),
        source_path="; ".join(statement.source_path for statement in statements),
        detected_format=latest_snapshot.statement.detected_format,
        account_id=_build_combined_account_id(ordered),
        base_currency=latest_snapshot.statement.base_currency,
        statement_period=_build_combined_statement_period(ordered),
        page_count=sum(statement.page_count or 0 for statement in statements) or None,
    )

    return ImportedPortfolioSnapshot(
        statement=combined_statement,
        statements=statements,
        statement_totals=_merge_statement_totals(ordered, terminal_snapshots),
        instruments=_merge_instruments(ordered),
        cash_balances=_merge_terminal_cash_balances(terminal_snapshots),
        positions=_merge_terminal_positions(terminal_snapshots),
        ledger_entries=_merge_ledger_entries(ordered),
    )


def _snapshot_sort_key(snapshot: ImportedPortfolioSnapshot) -> tuple[date, date]:
    return (_snapshot_start_date(snapshot), _snapshot_end_date(snapshot))


def _snapshot_start_date(snapshot: ImportedPortfolioSnapshot) -> date:
    candidates = [entry.trade_date for entry in snapshot.ledger_entries if entry.trade_date is not None]
    candidates.extend(position.as_of_date for position in snapshot.positions)
    return min(candidates, default=date.min)


def _snapshot_end_date(snapshot: ImportedPortfolioSnapshot) -> date:
    candidates = [entry.trade_date for entry in snapshot.ledger_entries if entry.trade_date is not None]
    candidates.extend(position.as_of_date for position in snapshot.positions)
    return max(candidates, default=date.min)


def _collect_statements(snapshots: list[ImportedPortfolioSnapshot]) -> list[ImportedStatement]:
    statements: list[ImportedStatement] = []
    seen_paths: set[str] = set()
    for snapshot in snapshots:
        snapshot_statements = snapshot.statements or [snapshot.statement]
        for statement in snapshot_statements:
            if statement.source_path in seen_paths:
                continue
            statements.append(statement.model_copy(deep=True))
            seen_paths.add(statement.source_path)
    return statements


def _validate_compatible_snapshots(snapshots: list[ImportedPortfolioSnapshot]) -> None:
    base_currencies = {snapshot.statement.base_currency or "USD" for snapshot in snapshots}
    if len(base_currencies) != 1:
        raise ValueError("Cannot combine statements with different base currencies")


def _build_combined_statement_period(snapshots: list[ImportedPortfolioSnapshot]) -> str | None:
    dated_periods = [parsed for snapshot in snapshots if (parsed := _parse_statement_period(snapshot.statement.statement_period)) is not None]
    if dated_periods:
        start_date = min(period[0] for period in dated_periods)
        end_date = max(period[1] for period in dated_periods)
    else:
        start_date = min((_snapshot_start_date(snapshot) for snapshot in snapshots), default=date.min)
        end_date = max((_snapshot_end_date(snapshot) for snapshot in snapshots), default=date.min)

    if start_date == date.min or end_date == date.min:
        return None
    return f"{start_date.isoformat()} - {end_date.isoformat()}"


def _parse_statement_period(period: str | None) -> tuple[date, date] | None:
    if not period or " - " not in period:
        return None

    start_raw, end_raw = [part.strip() for part in period.split(" - ", 1)]
    start_date = _parse_period_date(start_raw)
    end_date = _parse_period_date(end_raw)
    if start_date is None or end_date is None:
        return None

    return start_date, end_date


def _parse_period_date(value: str) -> date | None:
    iso_match = re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)
    if iso_match:
        return date.fromisoformat(value)

    month_match = re.fullmatch(r"[A-Za-z]+\s+\d{1,2},\s+\d{4}", value)
    if month_match:
        from datetime import datetime

        return datetime.strptime(value, "%B %d, %Y").date()

    return None


def _merge_statement_totals(snapshots: list[ImportedPortfolioSnapshot], terminal_snapshots: list[ImportedPortfolioSnapshot]) -> ImportedStatementTotals | None:
    totals = [snapshot.statement_totals for snapshot in snapshots if snapshot.statement_totals is not None]
    if not totals:
        return None

    earliest = next(total for total in totals if total is not None)
    terminal_totals = [snapshot.statement_totals for snapshot in terminal_snapshots if snapshot.statement_totals is not None]
    latest = totals[-1]

    def sum_field(field_name: str) -> float | None:
        values = [getattr(total, field_name) for total in totals if getattr(total, field_name) is not None]
        if not values:
            return None
        return round(sum(values), 2)

    compounded_twr = None
    twr_values = [total.time_weighted_return_pct for total in totals]
    if twr_values and all(value is not None for value in twr_values):
        growth = 1.0
        for value in twr_values:
            growth *= 1 + ((value or 0.0) / 100)
        compounded_twr = round((growth - 1) * 100, 4)

    fx_rates: dict[str, float] = {}
    for total in totals:
        fx_rates.update(total.fx_rates)

    terminal_cash_total = round(
        sum((snapshot.statement_totals.cash_total or 0.0) for snapshot in terminal_snapshots if snapshot.statement_totals is not None),
        2,
    ) if terminal_totals else latest.cash_total
    terminal_stock_total = round(
        sum((snapshot.statement_totals.stock_total or 0.0) for snapshot in terminal_snapshots if snapshot.statement_totals is not None),
        2,
    ) if terminal_totals else latest.stock_total
    terminal_ending_nav = round(terminal_cash_total + terminal_stock_total, 2) if terminal_cash_total is not None and terminal_stock_total is not None else latest.ending_nav

    starting_nav_candidates = [total.starting_nav for total in totals if total.starting_nav is not None and total.starting_nav > 0]

    return ImportedStatementTotals(
        starting_nav=starting_nav_candidates[0] if starting_nav_candidates else None,
        ending_nav=terminal_ending_nav,
        cash_total=terminal_cash_total,
        stock_total=terminal_stock_total,
        dividends_total=sum_field("dividends_total"),
        withholding_tax_total=sum_field("withholding_tax_total"),
        interest_total=sum_field("interest_total"),
        other_fees_total=sum_field("other_fees_total"),
        commissions_total=sum_field("commissions_total"),
        deposits_total=sum_field("deposits_total"),
        time_weighted_return_pct=compounded_twr,
        fx_rates=fx_rates,
    )


def _build_combined_account_id(snapshots: list[ImportedPortfolioSnapshot]) -> str | None:
    account_ids = [snapshot.statement.account_id for snapshot in snapshots if snapshot.statement.account_id]
    unique_account_ids = list(dict.fromkeys(account_ids))
    if not unique_account_ids:
        return None
    if len(unique_account_ids) == 1:
        return unique_account_ids[0]
    return " + ".join(unique_account_ids)


def _latest_snapshot_by_account(snapshots: list[ImportedPortfolioSnapshot]) -> list[ImportedPortfolioSnapshot]:
    latest_by_account: dict[str, ImportedPortfolioSnapshot] = {}
    fallback_snapshots: list[ImportedPortfolioSnapshot] = []
    for snapshot in snapshots:
        account_id = snapshot.statement.account_id
        if not account_id:
            fallback_snapshots.append(snapshot)
            continue
        latest_by_account[account_id] = snapshot
    terminal = list(latest_by_account.values()) + fallback_snapshots
    return sorted(terminal, key=_snapshot_sort_key)


def _merge_terminal_positions(snapshots: list[ImportedPortfolioSnapshot]) -> list[ImportedPosition]:
    merged: dict[tuple[str, str, date], ImportedPosition] = {}
    for snapshot in snapshots:
        for position in snapshot.positions:
            key = (position.symbol, position.currency, position.as_of_date)
            existing = merged.get(key)
            if existing is None:
                merged[key] = ImportedPosition.model_validate(position.model_dump())
                continue
            total_quantity = existing.quantity + position.quantity
            total_cost_basis = round(existing.cost_basis + position.cost_basis, 2)
            total_market_value = round(existing.market_value + position.market_value, 2)
            total_unrealized_pnl = round(existing.unrealized_pnl + position.unrealized_pnl, 2)
            merged[key] = ImportedPosition(
                as_of_date=position.as_of_date,
                symbol=position.symbol,
                quantity=total_quantity,
                cost_basis=total_cost_basis,
                close_price=position.close_price,
                market_value=total_market_value,
                unrealized_pnl=total_unrealized_pnl,
                currency=position.currency,
            )
    positions = list(merged.values())
    return sorted(positions, key=lambda position: (position.symbol, position.currency, position.as_of_date))


def _merge_terminal_cash_balances(snapshots: list[ImportedPortfolioSnapshot]) -> list[ImportedCashBalance]:
    merged: dict[str, ImportedCashBalance] = {}
    for snapshot in snapshots:
        for balance in snapshot.cash_balances:
            existing = merged.get(balance.currency)
            if existing is None:
                merged[balance.currency] = ImportedCashBalance.model_validate(balance.model_dump())
                continue
            merged[balance.currency] = ImportedCashBalance(
                currency=balance.currency,
                starting_cash=round((existing.starting_cash or 0.0) + (balance.starting_cash or 0.0), 2),
                ending_cash=round((existing.ending_cash or 0.0) + (balance.ending_cash or 0.0), 2),
                ending_settled_cash=round((existing.ending_settled_cash or 0.0) + (balance.ending_settled_cash or 0.0), 2),
            )
    balances = list(merged.values())
    return sorted(balances, key=lambda balance: (balance.currency, balance.ending_cash or 0.0), reverse=False)


def _merge_instruments(snapshots: list[ImportedPortfolioSnapshot]) -> list[ImportedInstrument]:
    merged: dict[str, ImportedInstrument] = {}
    for snapshot in snapshots:
        for instrument in snapshot.instruments:
            existing = merged.get(instrument.symbol)
            if existing is None:
                merged[instrument.symbol] = instrument.model_copy(deep=True)
                continue

            merged[instrument.symbol] = ImportedInstrument(
                symbol=instrument.symbol,
                description=instrument.description or existing.description,
                isin=instrument.isin or existing.isin,
                listing_exchange=instrument.listing_exchange or existing.listing_exchange,
                instrument_type=instrument.instrument_type or existing.instrument_type,
                currency=instrument.currency or existing.currency,
            )

    return [merged[symbol] for symbol in sorted(merged)]


def _merge_ledger_entries(snapshots: list[ImportedPortfolioSnapshot]) -> list[ImportedLedgerEntry]:
    merged: list[ImportedLedgerEntry] = []
    seen_keys: set[tuple] = set()
    for snapshot in snapshots:
        for entry in snapshot.ledger_entries:
            key = (
                entry.entry_type,
                entry.trade_date,
                entry.symbol,
                entry.description,
                entry.quantity,
                entry.price,
                entry.gross_amount,
                entry.net_amount,
                entry.fee,
                entry.tax,
                entry.currency,
                entry.source_section,
                entry.source_line,
            )
            if key in seen_keys:
                continue
            merged.append(entry.model_copy(deep=True))
            seen_keys.add(key)

    return sorted(merged, key=lambda entry: (entry.trade_date, entry.symbol or "", entry.entry_type, entry.description or ""))
