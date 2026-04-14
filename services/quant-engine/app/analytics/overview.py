from collections import Counter, defaultdict

from app.domain.ledger import snapshot_to_ledger
from app.instruments import InstrumentRegistry
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import PortfolioOverview


def build_portfolio_overview(snapshot: ImportedPortfolioSnapshot) -> PortfolioOverview:
    ledger = snapshot_to_ledger(snapshot)
    instrument_registry = InstrumentRegistry()
    metadata = instrument_registry.attach_snapshot_metadata(snapshot)
    total_market_value = round(sum(position.market_value for position in snapshot.positions), 2)
    total_cost_basis = round(sum(position.cost_basis for position in snapshot.positions), 2)
    total_unrealized_pnl = round(sum(position.unrealized_pnl for position in snapshot.positions), 2)

    cash_by_currency = {
        balance.currency: round(balance.ending_cash or 0, 2)
        for balance in snapshot.cash_balances
    }

    top_positions = [
        {
            "symbol": position.symbol,
            "market_value": round(position.market_value, 2),
            "weight": round(position.market_value / total_market_value, 4) if total_market_value else 0,
            "unrealized_pnl": round(position.unrealized_pnl, 2),
        }
        for position in sorted(snapshot.positions, key=lambda item: item.market_value, reverse=True)[:10]
    ]

    sector_totals: defaultdict[str, float] = defaultdict(float)
    sector_position_breakdown: defaultdict[str, list[dict[str, float | str]]] = defaultdict(list)
    for position in snapshot.positions:
        instrument = metadata.get(position.symbol)
        sector = instrument.sector if instrument and instrument.sector else instrument_registry.get_sector(position.symbol)
        sector_totals[sector] += position.market_value
        sector_position_breakdown[sector].append(
            {
                "symbol": position.symbol,
                "market_value": round(position.market_value, 2),
                "weight": round(position.market_value / total_market_value, 4) if total_market_value else 0,
            }
        )

    sector_allocation = [
        {
            "sector": sector,
            "market_value": round(market_value, 2),
            "weight": round(market_value / total_market_value, 4) if total_market_value else 0,
        }
        for sector, market_value in sorted(sector_totals.items(), key=lambda item: item[1], reverse=True)
    ]

    ledger_counts = dict(Counter(entry.entry_type for entry in ledger))
    realized_cash_flow: defaultdict[str, float] = defaultdict(float)
    for entry in ledger:
        realized_cash_flow[entry.cash_currency] += entry.cash_effect

    return PortfolioOverview(
        account_id=snapshot.statement.account_id,
        base_currency=snapshot.statement.base_currency,
        statement_period=snapshot.statement.statement_period,
        positions_count=len(snapshot.positions),
        instruments_count=len(snapshot.instruments),
        ledger_entries_count=len(ledger),
        total_market_value=total_market_value,
        total_cost_basis=total_cost_basis,
        total_unrealized_pnl=total_unrealized_pnl,
        cash_by_currency=cash_by_currency,
        top_positions=top_positions,
        sector_allocation=sector_allocation,
        sector_position_breakdown={
            sector: sorted(positions, key=lambda item: float(item["market_value"]), reverse=True)
            for sector, positions in sector_position_breakdown.items()
        },
        ledger_counts=ledger_counts,
        realized_cash_flow={currency: round(amount, 2) for currency, amount in realized_cash_flow.items()},
    )
