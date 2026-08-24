from collections import Counter, defaultdict

from app.analytics.currency import convert_to_base, snapshot_fx_context
from app.domain.ledger import snapshot_to_ledger
from app.instruments import InstrumentRegistry
from app.schemas.imports import ImportedPortfolioSnapshot
from app.schemas.reconciliation import PortfolioOverview
from app.services.market_data import MarketDataService

# Epic 37 / US-37.1 (AC9): sector bucket for an equity that no source (static
# registry, or identity-confirmed FMP) resolved a sector for. Distinct from,
# and never coerced into, get_sector()'s own "Other" literal.
UNCLASSIFIED_SECTOR_LABEL = "Unclassified"


def build_portfolio_overview(
    snapshot: ImportedPortfolioSnapshot, *, market_data: object | None = None
) -> PortfolioOverview:
    # `market_data` is an injection seam for the dashboard golden pipeline
    # (US-21.4/US-39.1.7): the generator passes a deterministic frozen provider
    # so goldens don't depend on the live FMP cache. Production callers leave
    # it None and get a live MarketDataService — mirrors
    # run_imported_dashboard_history's exact seam shape.
    ledger = snapshot_to_ledger(snapshot)
    instrument_registry = InstrumentRegistry()
    if market_data is None:
        market_data = MarketDataService()
    metadata = instrument_registry.attach_snapshot_metadata(snapshot, market_data=market_data)

    # US-30.5a (audit F-7): every total and weight below is summed in the BASE
    # currency. Raw-summing `position.market_value` mixed EUR/GBP/USD numerals
    # and understated the portfolio by 4.33% on the committed statement.
    base_currency, fx_rates = snapshot_fx_context(snapshot)

    def to_base(value: float, position) -> float:
        return convert_to_base(value, position.currency, base_currency, fx_rates)[0]

    # (position, base-currency market value) pairs — the single source for
    # every total, weight and ordering below.
    valued_positions = [(position, to_base(position.market_value, position)) for position in snapshot.positions]

    total_market_value = round(sum(value for _, value in valued_positions), 2)
    total_cost_basis = round(sum(to_base(p.cost_basis, p) for p in snapshot.positions), 2)
    total_unrealized_pnl = round(sum(to_base(p.unrealized_pnl, p) for p in snapshot.positions), 2)

    cash_by_currency = {
        balance.currency: round(balance.ending_cash or 0, 2)
        for balance in snapshot.cash_balances
    }

    top_positions = [
        {
            "symbol": position.symbol,
            "market_value": round(value, 2),
            "weight": round(value / total_market_value, 4) if total_market_value else 0,
            "unrealized_pnl": round(to_base(position.unrealized_pnl, position), 2),
        }
        for position, value in sorted(valued_positions, key=lambda item: item[1], reverse=True)[:10]
    ]

    sector_totals: defaultdict[str, float] = defaultdict(float)
    sector_position_breakdown: defaultdict[str, list[dict[str, float | str]]] = defaultdict(list)
    for position, value in valued_positions:
        instrument = metadata.get(position.symbol)
        if instrument is not None:
            sector = instrument.sector or UNCLASSIFIED_SECTOR_LABEL
        else:
            sector = instrument_registry.get_sector(position.symbol)  # unchanged, defensive-only
        sector_totals[sector] += value
        sector_position_breakdown[sector].append(
            {
                "symbol": position.symbol,
                "market_value": round(value, 2),
                "weight": round(value / total_market_value, 4) if total_market_value else 0,
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
