from app.analytics.risk import selected_history_price_map
from app.schemas.reconciliation import BenchmarkComparison, BenchmarkPoint
from app.services.market_data import HistoryReturnBasisContract, classify_history_return_basis_contract

# US-34.5: bases on which a benchmark return may be PUBLISHED. `unavailable` has
# no data behind it; `unverified_adjusted_proxy` is a proxy the project has never
# admitted as a return basis. A price return is a real number — it is simply not
# a TOTAL return, which the basis label states.
_PUBLISHING_BENCHMARK_BASES: frozenset[str] = frozenset(
    {"verified_total_return", "price_return_only"}
)


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
    # US-34.5 (Epic 34 F-6/F-10): publish on whatever basis the data supports,
    # labelled. Requiring `verified_total_return` left 148 SPY closes drawn on
    # the chart with no number beside them — and that rung is unreachable against
    # the real provider anyway (F-9).
    #
    # A price return omits the benchmark's dividends, so it understates a
    # positive-yield benchmark and flatters any excess computed against it. The
    # bias is disclosed on the surface, not hidden.
    return_pct = (
        round(((end_price / start_price) - 1) * 100, 2)
        if allow_return_pct
        and start_price
        and resolved_return_basis_contract in _PUBLISHING_BENCHMARK_BASES
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
