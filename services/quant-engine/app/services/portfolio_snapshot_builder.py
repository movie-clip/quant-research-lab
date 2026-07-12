from datetime import datetime

from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement, ImportedStatementTotals, SnapshotAnalysisRequest
from app.schemas.portfolio_engine import PortfolioEngineRequest


def build_imported_snapshot_from_request(request: PortfolioEngineRequest | SnapshotAnalysisRequest) -> ImportedPortfolioSnapshot:
    imported_at = request.imported_at or datetime.utcnow()
    statement = ImportedStatement(
        importer=request.importer or 'interactive_brokers',
        imported_at=imported_at,
        source_path=', '.join(request.source_file_names) or 'snapshot',
        detected_format='snapshot',
        account_id='snapshot-workspace',
        base_currency=request.base_currency,
        statement_period=request.statement_period,
        page_count=None,
    )
    # US-30.5a (audit F-7): carry the request's statement-implied FX rates so
    # the analytics can sum weight denominators in the base currency. Only
    # materialised when rates are actually supplied — otherwise
    # `statement_totals` stays None and behaviour is byte-identical to before
    # (US-30.1's cash anchor guards on `starting_nav`, and the terminal
    # reconciliation guards on `ending_nav`/`cash_total`, all None here).
    fx_rates = dict(getattr(request, "fx_rates", {}) or {})
    statement_totals = ImportedStatementTotals(fx_rates=fx_rates) if fx_rates else None

    return ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=statement_totals,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency=item.currency, ending_cash=item.amount) for item in request.cash_balances],
        positions=[
            ImportedPosition(
                as_of_date=imported_at.date(),
                symbol=item.symbol,
                quantity=item.quantity or 0,
                cost_basis=item.market_value,
                close_price=item.market_value / item.quantity if item.quantity not in (None, 0) else item.market_value,
                market_value=item.market_value,
                unrealized_pnl=0,
                currency=item.currency or request.base_currency or 'USD',
            )
            for item in request.positions
        ],
        ledger_entries=[],
    )
