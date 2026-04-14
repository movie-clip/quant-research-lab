from datetime import date, datetime

from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.portfolio_engine import PortfolioHistoryContext


def build_history_context(snapshot: ImportedPortfolioSnapshot, benchmark_symbol: str) -> PortfolioHistoryContext:
    start_date, end_date = derive_analysis_window(snapshot)
    return PortfolioHistoryContext(
        benchmark_symbol=benchmark_symbol,
        statement_period=snapshot.statement.statement_period,
        imported_at=snapshot.statement.imported_at,
        importer=snapshot.statement.importer,
        source_file_names=[statement.source_path for statement in snapshot.statements],
        history_start_date=start_date,
        history_end_date=end_date,
    )


def derive_analysis_window(snapshot: ImportedPortfolioSnapshot) -> tuple[str, str]:
    statement_window = derive_statement_window(snapshot)
    if statement_window is not None:
        return statement_window

    position_dates = [position.as_of_date.isoformat() for position in snapshot.positions]
    ledger_dates = [entry.trade_date.isoformat() for entry in snapshot.ledger_entries if entry.trade_date is not None]
    end_date = max(position_dates or ledger_dates or ["2025-12-31"])
    start_date = min(ledger_dates or position_dates or [end_date])
    return start_date, end_date


def derive_statement_window(snapshot: ImportedPortfolioSnapshot) -> tuple[str, str] | None:
    periods: list[tuple[date, date]] = []
    for statement in snapshot.statements or [snapshot.statement]:
        parsed = parse_statement_period(statement.statement_period)
        if parsed is not None:
            periods.append(parsed)

    if not periods:
        return None

    start_date = min(period[0] for period in periods)
    end_date = max(period[1] for period in periods)
    return start_date.isoformat(), end_date.isoformat()


def parse_statement_period(period: str | None) -> tuple[date, date] | None:
    if not period or " - " not in period:
        return None

    start_raw, end_raw = [part.strip() for part in period.split(" - ", 1)]
    start_date = parse_statement_period_date(start_raw)
    end_date = parse_statement_period_date(end_raw)
    if start_date is None or end_date is None:
        return None

    return start_date, end_date


def parse_statement_period_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass

    try:
        return datetime.strptime(value, "%B %d, %Y").date()
    except ValueError:
        return None
