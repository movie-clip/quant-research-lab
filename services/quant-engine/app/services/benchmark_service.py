from app.schemas.reconciliation import BenchmarkComparison, BenchmarkPoint


def build_benchmark_comparison(symbol: str, rows: list[dict]) -> BenchmarkComparison | None:
    if not rows:
        return None

    ordered = sorted(rows, key=lambda row: row["date"])
    start_price = float(ordered[0]["price"])
    end_price = float(ordered[-1]["price"])
    return_pct = round(((end_price / start_price) - 1) * 100, 2) if start_price else None

    return BenchmarkComparison(
        symbol=symbol,
        start_price=start_price,
        end_price=end_price,
        return_pct=return_pct,
        points=[BenchmarkPoint(date=row["date"], price=float(row["price"])) for row in ordered],
    )
