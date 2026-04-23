from app.schemas.optimizer import OptimizerWeight
from app.services.optimizer_risk_service import (
    OptimizerRiskPackageConfig,
    build_optimizer_risk_package,
    compute_active_risk,
    max_covariance_asymmetry,
    min_covariance_eigenvalue,
    validate_optimizer_risk_package,
)


def _price_history(start_price: float, returns: list[float], start_date: str = "2024-01-01") -> list[dict]:
    year, month, day = (int(item) for item in start_date.split("-"))
    rows: list[dict] = []
    price = start_price
    rows.append({"date": f"{year:04d}-{month:02d}-{day:02d}", "adjusted_close": round(price, 6)})
    for value in returns:
        day += 1
        if day > 28:
            day = 1
            month += 1
            if month > 12:
                month = 1
                year += 1
        price *= 1.0 + value
        rows.append({"date": f"{year:04d}-{month:02d}-{day:02d}", "adjusted_close": round(price, 6)})
    return rows


def _benchmark_weights() -> list[OptimizerWeight]:
    return [
        OptimizerWeight(symbol="AAA", weight=0.5),
        OptimizerWeight(symbol="BBB", weight=0.3),
        OptimizerWeight(symbol="CCC", weight=0.2),
    ]


def _valid_histories() -> dict[str, list[dict]]:
    return {
        "AAA": _price_history(100.0, [0.02, -0.01, 0.015, -0.005] * 20),
        "BBB": _price_history(100.0, [0.004, -0.003, 0.002, 0.001] * 20),
        "CCC": _price_history(100.0, [0.012, -0.008, 0.01, -0.004] * 20),
    }


def test_build_optimizer_risk_package_is_deterministic_and_valid() -> None:
    package_one = build_optimizer_risk_package(
        rebalance_date="2024-03-21",
        universe_symbols=["CCC", "AAA", "BBB"],
        benchmark_symbol="SPY",
        benchmark_weights=_benchmark_weights(),
        price_histories=_valid_histories(),
    )
    package_two = build_optimizer_risk_package(
        rebalance_date="2024-03-21",
        universe_symbols=["BBB", "CCC", "AAA"],
        benchmark_symbol="SPY",
        benchmark_weights=_benchmark_weights(),
        price_histories=_valid_histories(),
    )

    assert package_one == package_two
    assert package_one.package_id == package_two.package_id
    assert package_one.ordered_symbols == ["AAA", "BBB", "CCC"]
    assert package_one.version == "optimizer_risk_package_v2"
    assert package_one.representation == "structured_shrunk_covariance"
    assert package_one.diagnostics.status == "ok"
    assert package_one.diagnostics.risk_model_version == "v2"
    assert package_one.diagnostics.coverage_ratio == 1.0
    assert package_one.diagnostics.pairwise_coverage_ratio == 1.0
    assert max_covariance_asymmetry(package_one.covariance_matrix) == 0.0
    assert min_covariance_eigenvalue(package_one.covariance_matrix) >= -1e-9
    assert package_one.diagnostics.covariance_psd is True
    assert all(package_one.covariance_matrix[index][index] >= 0.0 for index in range(len(package_one.ordered_symbols)))
    assert package_one.covariance_matrix[0][1] > 0.0
    assert validate_optimizer_risk_package(
        package_one,
        expected_symbols=["AAA", "BBB", "CCC"],
        benchmark_weights=_benchmark_weights(),
    ) == []


def test_build_optimizer_risk_package_fails_closed_on_missing_coverage() -> None:
    package = build_optimizer_risk_package(
        rebalance_date="2024-03-21",
        universe_symbols=["AAA", "BBB", "CCC"],
        benchmark_symbol="SPY",
        benchmark_weights=_benchmark_weights(),
        price_histories={"AAA": _valid_histories()["AAA"], "BBB": _valid_histories()["BBB"]},
    )

    assert package.diagnostics.status == "invalid"
    assert package.diagnostics.coverage_ratio == 0.66666667
    assert package.diagnostics.missing_symbols == ["CCC"]
    issues = validate_optimizer_risk_package(
        package,
        expected_symbols=["AAA", "BBB", "CCC"],
        benchmark_weights=_benchmark_weights(),
    )
    assert issues[0].code == "risk_package_inputs_invalid"
    assert issues[0].symbols == ["CCC"]


def test_build_optimizer_risk_package_fails_closed_on_stale_and_low_observation_inputs() -> None:
    package = build_optimizer_risk_package(
        rebalance_date="2024-03-21",
        universe_symbols=["AAA", "BBB", "CCC"],
        benchmark_symbol="SPY",
        benchmark_weights=_benchmark_weights(),
        price_histories={
            "AAA": _price_history(100.0, [0.01, -0.01] * 10, start_date="2024-01-01"),
            "BBB": _price_history(100.0, [0.01, -0.005, 0.004, 0.002] * 20),
            "CCC": _price_history(100.0, [0.02, -0.015, 0.01, -0.003] * 20),
        },
        config=OptimizerRiskPackageConfig(minimum_coverage_ratio=1.0, minimum_observations=60, stale_after_days=5),
    )

    assert package.diagnostics.status == "invalid"
    assert package.diagnostics.stale_symbols == ["AAA"]
    assert package.diagnostics.low_observation_symbols == ["AAA"]
    issues = validate_optimizer_risk_package(
        package,
        expected_symbols=["AAA", "BBB", "CCC"],
        benchmark_weights=_benchmark_weights(),
    )
    assert issues[0].code == "risk_package_inputs_invalid"
    assert issues[0].symbols == ["AAA"]


def test_validate_optimizer_risk_package_rejects_non_symmetric_covariance() -> None:
    package = build_optimizer_risk_package(
        rebalance_date="2024-03-21",
        universe_symbols=["AAA", "BBB", "CCC"],
        benchmark_symbol="SPY",
        benchmark_weights=_benchmark_weights(),
        price_histories=_valid_histories(),
    )
    package.covariance_matrix[0][1] = 0.01

    issues = validate_optimizer_risk_package(
        package,
        expected_symbols=["AAA", "BBB", "CCC"],
        benchmark_weights=_benchmark_weights(),
    )

    assert any(issue.code == "risk_package_not_symmetric" for issue in issues)


def test_risk_v2_reduces_false_diversification_relative_to_diagonal() -> None:
    package = build_optimizer_risk_package(
        rebalance_date="2024-03-21",
        universe_symbols=["AAA", "BBB", "CCC"],
        benchmark_symbol="SPY",
        benchmark_weights=_benchmark_weights(),
        price_histories=_valid_histories(),
    )

    weights = [0.54, 0.22, 0.24]
    benchmark = [0.5, 0.3, 0.2]
    diagonal_covariance = [
        [row[index] if row_index == index else 0.0 for index, _ in enumerate(row)]
        for row_index, row in enumerate(package.covariance_matrix)
    ]

    structured_risk = compute_active_risk(weights, benchmark, package.covariance_matrix)
    diagonal_risk = compute_active_risk(weights, benchmark, diagonal_covariance)

    assert structured_risk > diagonal_risk


def test_risk_v2_falls_back_symbol_by_symbol_when_pairwise_history_is_missing() -> None:
    package = build_optimizer_risk_package(
        rebalance_date="2024-03-21",
        universe_symbols=["AAA", "BBB", "CCC"],
        benchmark_symbol="SPY",
        benchmark_weights=_benchmark_weights(),
        price_histories={
            "AAA": _price_history(100.0, [0.02, -0.01, 0.015, -0.005] * 20),
            "BBB": _price_history(100.0, [0.018, -0.009, 0.012, -0.004] * 20, start_date="2024-01-15"),
            "CCC": _price_history(100.0, [0.011, -0.007, 0.009, -0.003] * 20),
        },
        config=OptimizerRiskPackageConfig(minimum_pairwise_observations=75),
    )

    assert package.diagnostics.status == "ok"
    assert package.diagnostics.pairwise_coverage_ratio == 0.33333333
    assert package.representation == "structured_shrunk_covariance"
    assert package.diagnostics.diagonal_fallback_symbols == ["BBB"]
