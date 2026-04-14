from datetime import datetime

from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement, SnapshotAnalysisRequest
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
    return ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=None,
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
