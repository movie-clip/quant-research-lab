from app.analytics.risk import selected_history_price_map
from app.schemas.reconciliation import BenchmarkComparison, BenchmarkPoint
from app.services.market_data import HistoryReturnBasisContract, classify_history_return_basis_contract


def build_benchmark_comparison(
    symbol: str,
    rows: list[dict],
    *,
    return_basis_contract: HistoryReturnBasisContract | None = None,
    allow_return_pct: bool = True,
) -> BenchmarkComparison | None:
    if not rows:
        return None

    benchmark_by_date, _ = selected_history_price_map(rows)
    ordered = [{"date": date, "price": price} for date, price in sorted(benchmark_by_date.items())]
    if not ordered:
        return None
    start_price = float(ordered[0]["price"])
    end_price = float(ordered[-1]["price"])
    resolved_return_basis_contract = return_basis_contract or classify_history_return_basis_contract(rows)
    return_pct = (
        round(((end_price / start_price) - 1) * 100, 2)
        if allow_return_pct and start_price and resolved_return_basis_contract == "verified_total_return"
        else None
    )

    return BenchmarkComparison(
        symbol=symbol,
        start_price=start_price,
        end_price=end_price,
        return_pct=return_pct,
        return_basis_contract=resolved_return_basis_contract,
        points=[BenchmarkPoint(date=row["date"], price=float(row["price"])) for row in ordered],
    )
