from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from hashlib import sha256
from math import sqrt
from typing import Literal

from app.analytics.risk import select_history_price_series
from app.schemas.optimizer import OptimizationIssue, OptimizerRiskPackage, OptimizerRiskBenchmarkAlignment, OptimizerRiskDiagnostics, OptimizerWeight


RISK_MODEL_VERSION = "v2"
RISK_PACKAGE_VERSION = "optimizer_risk_package_v2"
SUPPORTED_RISK_PACKAGE_VERSIONS = {"optimizer_risk_package_v1", "optimizer_risk_package_v2"}
RISK_REPRESENTATION: Literal["structured_shrunk_covariance"] = "structured_shrunk_covariance"
DIAGONAL_REPRESENTATION: Literal["diagonal_covariance"] = "diagonal_covariance"
RISK_ANNUALIZATION_FACTOR = 252
RISK_SYMMETRY_TOLERANCE = 1e-10
RISK_EIGENVALUE_TOLERANCE = 1e-9


@dataclass(frozen=True)
class OptimizerRiskPackageConfig:
    minimum_coverage_ratio: float = 1.0
    minimum_observations: int = 60
    stale_after_days: int = 5
    minimum_pairwise_observations: int = 40
    fallback_correlation: float = 0.35
    max_constant_correlation: float = 0.80


def build_optimizer_risk_package(
    *,
    rebalance_date: str,
    universe_symbols: list[str],
    benchmark_symbol: str,
    benchmark_weights: list[OptimizerWeight],
    price_histories: dict[str, list[dict]],
    config: OptimizerRiskPackageConfig | None = None,
) -> OptimizerRiskPackage:
    config = config or OptimizerRiskPackageConfig()
    ordered_symbols = sorted({symbol.upper() for symbol in universe_symbols})
    benchmark_map = {item.symbol.upper(): item.weight for item in benchmark_weights}
    rebalance_dt = date.fromisoformat(rebalance_date)

    observation_count_by_symbol: dict[str, int] = {}
    latest_data_by_symbol: dict[str, str | None] = {}
    missing_symbols: list[str] = []
    stale_symbols: list[str] = []
    low_observation_symbols: list[str] = []
    covered_symbols: list[str] = []
    annualized_variances: list[float] = []
    return_maps_by_symbol: dict[str, dict[str, float]] = {}

    for symbol in ordered_symbols:
        rows = [row for row in price_histories.get(symbol, []) if str(row.get("date") or "") <= rebalance_date]
        series = select_history_price_series(rows)
        returns = _series_to_returns(series.points)
        return_maps_by_symbol[symbol] = _series_to_return_map(series.points)
        observation_count_by_symbol[symbol] = len(returns)
        latest_date = series.points[-1][0] if series.points else None
        latest_data_by_symbol[symbol] = latest_date

        if latest_date is None:
            missing_symbols.append(symbol)
            annualized_variances.append(0.0)
            continue

        staleness_days = (rebalance_dt - date.fromisoformat(latest_date)).days
        if staleness_days > config.stale_after_days:
            stale_symbols.append(symbol)
        if len(returns) < config.minimum_observations:
            low_observation_symbols.append(symbol)

        if staleness_days <= config.stale_after_days and len(returns) >= config.minimum_observations:
            covered_symbols.append(symbol)

        annualized_variances.append(round(max(_sample_variance(returns) * RISK_ANNUALIZATION_FACTOR, 0.0), 12))

    benchmark_symbols_missing_from_package = sorted(symbol for symbol in benchmark_map if symbol not in ordered_symbols)
    covered_symbol_set = set(covered_symbols)
    benchmark_weight_coverage = sum(weight for symbol, weight in benchmark_map.items() if symbol in covered_symbol_set)
    coverage_ratio = (len(covered_symbols) / len(ordered_symbols)) if ordered_symbols else 0.0
    status = (
        "invalid"
        if missing_symbols
        or stale_symbols
        or low_observation_symbols
        or benchmark_symbols_missing_from_package
        or coverage_ratio + RISK_SYMMETRY_TOLERANCE < config.minimum_coverage_ratio
        or benchmark_weight_coverage + RISK_SYMMETRY_TOLERANCE < 1.0
        else "ok"
    )

    covariance_matrix, representation, pairwise_coverage_ratio, average_positive_correlation, diagonal_fallback_symbols = _build_structured_covariance(
        ordered_symbols=ordered_symbols,
        covered_symbols=covered_symbols,
        annualized_variances=annualized_variances,
        return_maps_by_symbol=return_maps_by_symbol,
        config=config,
    )
    covariance_min_eigenvalue = round(min_covariance_eigenvalue(covariance_matrix), 12)
    package_id = _build_package_id(
        rebalance_date=rebalance_date,
        benchmark_symbol=benchmark_symbol,
        ordered_symbols=ordered_symbols,
        representation=representation,
        covariance_matrix=covariance_matrix,
    )
    return OptimizerRiskPackage(
        package_id=package_id,
        version=RISK_PACKAGE_VERSION,
        rebalance_date=rebalance_date,
        benchmark_symbol=benchmark_symbol,
        representation=representation,
        annualization_factor=RISK_ANNUALIZATION_FACTOR,
        ordered_symbols=ordered_symbols,
        covariance_matrix=covariance_matrix,
        benchmark_alignment=OptimizerRiskBenchmarkAlignment(
            benchmark_symbol=benchmark_symbol,
            benchmark_weight_coverage=round(benchmark_weight_coverage, 8),
            aligned=not benchmark_symbols_missing_from_package,
            benchmark_symbols_missing_from_package=benchmark_symbols_missing_from_package,
        ),
        diagnostics=OptimizerRiskDiagnostics(
            status=status,
            risk_model_version=RISK_MODEL_VERSION,
            universe_symbol_count=len(ordered_symbols),
            covered_symbol_count=len(covered_symbols),
            coverage_ratio=round(coverage_ratio, 8),
            minimum_coverage_ratio=config.minimum_coverage_ratio,
            minimum_observations=config.minimum_observations,
            stale_after_days=config.stale_after_days,
            observation_count_by_symbol=observation_count_by_symbol,
            latest_data_by_symbol=latest_data_by_symbol,
            missing_symbols=missing_symbols,
            stale_symbols=stale_symbols,
            low_observation_symbols=low_observation_symbols,
            pairwise_coverage_ratio=round(pairwise_coverage_ratio, 8),
            average_positive_correlation=(round(average_positive_correlation, 8) if average_positive_correlation is not None else None),
            diagonal_fallback_symbols=diagonal_fallback_symbols,
            covariance_min_eigenvalue=covariance_min_eigenvalue,
            covariance_psd=covariance_min_eigenvalue >= -RISK_EIGENVALUE_TOLERANCE,
        ),
    )


def validate_optimizer_risk_package(
    risk_package: OptimizerRiskPackage,
    *,
    expected_symbols: list[str],
    benchmark_weights: list[OptimizerWeight],
) -> list[OptimizationIssue]:
    issues: list[OptimizationIssue] = []
    expected_order = sorted({symbol.upper() for symbol in expected_symbols})
    package_order = [symbol.upper() for symbol in risk_package.ordered_symbols]
    benchmark_map = {item.symbol.upper(): item.weight for item in benchmark_weights}

    if risk_package.version not in SUPPORTED_RISK_PACKAGE_VERSIONS:
        issues.append(
            OptimizationIssue(
                code="unsupported_risk_package_version",
                constraint_id="active_risk_cap",
                message="Optimizer risk package version is not supported by this optimizer baseline.",
                actual_value=risk_package.version,
                required_value=",".join(sorted(SUPPORTED_RISK_PACKAGE_VERSIONS)),
            )
        )

    if package_order != expected_order:
        issues.append(
            OptimizationIssue(
                code="risk_package_universe_misaligned",
                constraint_id="active_risk_cap",
                message="Optimizer risk package symbol order must match the normalized optimizer universe deterministically.",
                actual_value=",".join(package_order),
                required_value=",".join(expected_order),
            )
        )

    matrix = risk_package.covariance_matrix
    if len(matrix) != len(package_order) or any(len(row) != len(package_order) for row in matrix):
        issues.append(
            OptimizationIssue(
                code="risk_package_shape_invalid",
                constraint_id="active_risk_cap",
                message="Optimizer risk package covariance structure must be square and match the normalized universe size.",
                actual_value=len(matrix),
                required_value=len(package_order),
            )
        )
        return issues

    if risk_package.diagnostics.status != "ok":
        issues.append(
            OptimizationIssue(
                code="risk_package_inputs_invalid",
                constraint_id="active_risk_cap",
                message="Optimizer risk package failed closed due to stale, missing, or low-coverage risk inputs.",
                actual_value=risk_package.diagnostics.status,
                required_value="ok",
                symbols=sorted(
                    set(
                        risk_package.diagnostics.missing_symbols
                        + risk_package.diagnostics.stale_symbols
                        + risk_package.diagnostics.low_observation_symbols
                    )
                ),
            )
        )

    if risk_package.benchmark_alignment.benchmark_symbols_missing_from_package:
        issues.append(
            OptimizationIssue(
                code="risk_package_benchmark_misaligned",
                constraint_id="active_risk_cap",
                message="Benchmark-relative risk packaging must cover every benchmark constituent represented in the optimizer request.",
                actual_value=",".join(risk_package.benchmark_alignment.benchmark_symbols_missing_from_package),
                required_value="all_benchmark_symbols_in_package",
                symbols=risk_package.benchmark_alignment.benchmark_symbols_missing_from_package,
            )
        )

    expected_benchmark_symbols = sorted(benchmark_map)
    package_benchmark_symbols = sorted(symbol for symbol in package_order if symbol in benchmark_map)
    if package_benchmark_symbols != expected_benchmark_symbols:
        issues.append(
            OptimizationIssue(
                code="risk_package_benchmark_coverage_mismatch",
                constraint_id="active_risk_cap",
                message="Optimizer risk package must align to the full benchmark support used by the request.",
                actual_value=",".join(package_benchmark_symbols),
                required_value=",".join(expected_benchmark_symbols),
            )
        )

    if abs(risk_package.benchmark_alignment.benchmark_weight_coverage - 1.0) > 1e-8:
        issues.append(
            OptimizationIssue(
                code="risk_package_benchmark_weight_coverage_incomplete",
                constraint_id="active_risk_cap",
                message="Optimizer risk package must retain full benchmark weight coverage for hard benchmark-relative behavior.",
                actual_value=risk_package.benchmark_alignment.benchmark_weight_coverage,
                required_value=1.0,
                gap=round(1.0 - risk_package.benchmark_alignment.benchmark_weight_coverage, 8),
            )
        )

    symmetry_gap = max_covariance_asymmetry(matrix)
    if symmetry_gap > RISK_SYMMETRY_TOLERANCE:
        issues.append(
            OptimizationIssue(
                code="risk_package_not_symmetric",
                constraint_id="active_risk_cap",
                message="Optimizer risk covariance must be symmetric.",
                actual_value=round(symmetry_gap, 12),
                required_value=RISK_SYMMETRY_TOLERANCE,
                gap=round(symmetry_gap - RISK_SYMMETRY_TOLERANCE, 12),
            )
        )

    negative_diagonals = [package_order[index] for index, row in enumerate(matrix) if row[index] < -RISK_SYMMETRY_TOLERANCE]
    if negative_diagonals:
        issues.append(
            OptimizationIssue(
                code="risk_package_not_psd",
                constraint_id="active_risk_cap",
                message="Optimizer risk covariance must have non-negative variances.",
                actual_value="negative_diagonal",
                required_value="non_negative_diagonal",
                symbols=negative_diagonals,
            )
        )

    minimum_eigenvalue = min_covariance_eigenvalue(matrix)
    if minimum_eigenvalue < -RISK_EIGENVALUE_TOLERANCE:
        issues.append(
            OptimizationIssue(
                code="risk_package_not_psd",
                constraint_id="active_risk_cap",
                message="Optimizer risk covariance must remain positive semidefinite for stable active-risk control.",
                actual_value=round(minimum_eigenvalue, 12),
                required_value=0.0,
                gap=round(-minimum_eigenvalue, 12),
            )
        )

    return issues


def compute_active_risk(weights: list[float], benchmark_weights: list[float], covariance_matrix: list[list[float]]) -> float:
    active_weights = [weight - benchmark_weight for weight, benchmark_weight in zip(weights, benchmark_weights)]
    variance = 0.0
    for row_index, active_weight in enumerate(active_weights):
        row = covariance_matrix[row_index]
        variance += active_weight * sum(value * active_weights[column_index] for column_index, value in enumerate(row))
    return sqrt(max(variance, 0.0))


def project_to_active_risk_ball(
    vector: list[float],
    benchmark_weights: list[float],
    covariance_matrix: list[list[float]],
    max_active_risk: float,
) -> list[float]:
    if max_active_risk <= 0:
        return list(benchmark_weights)
    current_active_risk = compute_active_risk(vector, benchmark_weights, covariance_matrix)
    if current_active_risk <= max_active_risk + RISK_SYMMETRY_TOLERANCE:
        return list(vector)
    scale = max_active_risk / current_active_risk if current_active_risk > 0 else 0.0
    return [anchor + ((value - anchor) * scale) for value, anchor in zip(vector, benchmark_weights)]


def max_covariance_asymmetry(covariance_matrix: list[list[float]]) -> float:
    gap = 0.0
    for row_index, row in enumerate(covariance_matrix):
        for column_index, value in enumerate(row):
            gap = max(gap, abs(value - covariance_matrix[column_index][row_index]))
    return gap


def _build_diagonal_covariance(annualized_variances: list[float]) -> list[list[float]]:
    size = len(annualized_variances)
    return [
        [annualized_variances[row_index] if row_index == column_index else 0.0 for column_index in range(size)]
        for row_index in range(size)
    ]


def _build_structured_covariance(
    *,
    ordered_symbols: list[str],
    covered_symbols: list[str],
    annualized_variances: list[float],
    return_maps_by_symbol: dict[str, dict[str, float]],
    config: OptimizerRiskPackageConfig,
) -> tuple[list[list[float]], Literal["diagonal_covariance", "structured_shrunk_covariance"], float, float | None, list[str]]:
    covered_symbol_set = set(covered_symbols)
    valid_pair_counts = {symbol: 0 for symbol in ordered_symbols}
    correlations: list[float] = []
    total_possible_pairs = 0
    valid_pairs = 0

    for left_index, left_symbol in enumerate(ordered_symbols):
        if left_symbol not in covered_symbol_set or annualized_variances[left_index] <= 0:
            continue
        for right_index in range(left_index + 1, len(ordered_symbols)):
            right_symbol = ordered_symbols[right_index]
            if right_symbol not in covered_symbol_set or annualized_variances[right_index] <= 0:
                continue
            total_possible_pairs += 1
            correlation = _pairwise_correlation(
                return_maps_by_symbol.get(left_symbol, {}),
                return_maps_by_symbol.get(right_symbol, {}),
                minimum_observations=config.minimum_pairwise_observations,
            )
            if correlation is None:
                continue
            valid_pairs += 1
            valid_pair_counts[left_symbol] += 1
            valid_pair_counts[right_symbol] += 1
            correlations.append(correlation)

    pairwise_coverage_ratio = (valid_pairs / total_possible_pairs) if total_possible_pairs > 0 else 1.0
    positive_correlations = [value for value in correlations if value > 0]
    average_positive_correlation = (sum(positive_correlations) / len(positive_correlations)) if positive_correlations else None

    if valid_pairs == 0:
        return _build_diagonal_covariance(annualized_variances), DIAGONAL_REPRESENTATION, pairwise_coverage_ratio, average_positive_correlation, list(ordered_symbols)

    effective_correlation = min(
        max(config.fallback_correlation, average_positive_correlation or 0.0),
        config.max_constant_correlation,
    )
    diagonal_fallback_symbols = sorted(
        symbol
        for symbol in ordered_symbols
        if symbol not in covered_symbol_set or valid_pair_counts.get(symbol, 0) == 0
    )
    diagonal_fallback_set = set(diagonal_fallback_symbols)
    covariance_matrix = _build_constant_correlation_covariance(
        annualized_variances=annualized_variances,
        ordered_symbols=ordered_symbols,
        constant_correlation=effective_correlation,
        diagonal_fallback_symbols=diagonal_fallback_set,
    )
    representation = DIAGONAL_REPRESENTATION if len(diagonal_fallback_symbols) == len(ordered_symbols) else RISK_REPRESENTATION
    return covariance_matrix, representation, pairwise_coverage_ratio, average_positive_correlation, diagonal_fallback_symbols


def _build_constant_correlation_covariance(
    *,
    annualized_variances: list[float],
    ordered_symbols: list[str],
    constant_correlation: float,
    diagonal_fallback_symbols: set[str],
) -> list[list[float]]:
    size = len(annualized_variances)
    covariance_matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    for row_index in range(size):
        covariance_matrix[row_index][row_index] = annualized_variances[row_index]
        if annualized_variances[row_index] <= 0:
            continue
        if ordered_symbols[row_index] in diagonal_fallback_symbols:
            continue
        for column_index in range(row_index + 1, size):
            if annualized_variances[column_index] <= 0:
                continue
            if ordered_symbols[column_index] in diagonal_fallback_symbols:
                continue
            covariance_value = round(constant_correlation * sqrt(annualized_variances[row_index] * annualized_variances[column_index]), 12)
            covariance_matrix[row_index][column_index] = covariance_value
            covariance_matrix[column_index][row_index] = covariance_value
    return covariance_matrix


def _build_package_id(
    *,
    rebalance_date: str,
    benchmark_symbol: str,
    ordered_symbols: list[str],
    representation: str,
    covariance_matrix: list[list[float]],
) -> str:
    digest = sha256()
    digest.update(RISK_PACKAGE_VERSION.encode("ascii"))
    digest.update(rebalance_date.encode("ascii"))
    digest.update(benchmark_symbol.upper().encode("ascii"))
    digest.update(representation.encode("ascii"))
    for symbol in ordered_symbols:
        digest.update(symbol.encode("ascii"))
    for row in covariance_matrix:
        for value in row:
            digest.update(f"{value:.12f}".encode("ascii"))
    return f"orpv2_{digest.hexdigest()[:16]}"


def _sample_variance(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = sum(values) / len(values)
    return sum((value - mean_value) ** 2 for value in values) / (len(values) - 1)


def _series_to_returns(points: list[tuple[str, float]]) -> list[float]:
    ordered_points = sorted(points, key=lambda item: item[0])
    returns: list[float] = []
    for (_, previous_price), (_, current_price) in zip(ordered_points, ordered_points[1:]):
        if previous_price <= 0:
            continue
        returns.append((current_price / previous_price) - 1.0)
    return returns


def _series_to_return_map(points: list[tuple[str, float]]) -> dict[str, float]:
    ordered_points = sorted(points, key=lambda item: item[0])
    return_map: dict[str, float] = {}
    for (_, previous_price), (current_date, current_price) in zip(ordered_points, ordered_points[1:]):
        if previous_price <= 0:
            continue
        return_map[current_date] = (current_price / previous_price) - 1.0
    return return_map


def _pairwise_correlation(left: dict[str, float], right: dict[str, float], *, minimum_observations: int) -> float | None:
    overlap_dates = sorted(set(left) & set(right))
    if len(overlap_dates) < minimum_observations:
        return None
    left_values = [left[item] for item in overlap_dates]
    right_values = [right[item] for item in overlap_dates]
    return _sample_correlation(left_values, right_values)


def _sample_correlation(left: list[float], right: list[float]) -> float | None:
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    if left_variance <= 0 or right_variance <= 0:
        return None
    covariance = sum((left_value - left_mean) * (right_value - right_mean) for left_value, right_value in zip(left, right))
    correlation = covariance / sqrt(left_variance * right_variance)
    return max(min(correlation, 1.0), -1.0)


def min_covariance_eigenvalue(covariance_matrix: list[list[float]]) -> float:
    if not covariance_matrix:
        return 0.0
    matrix = [list(row) for row in covariance_matrix]
    size = len(matrix)
    for _ in range(100 * size * size):
        pivot_row = 0
        pivot_column = 1 if size > 1 else 0
        pivot_value = 0.0
        for row_index in range(size):
            for column_index in range(row_index + 1, size):
                candidate = abs(matrix[row_index][column_index])
                if candidate > pivot_value:
                    pivot_value = candidate
                    pivot_row = row_index
                    pivot_column = column_index
        if pivot_value <= 1e-12:
            break

        theta = 0.5 * (matrix[pivot_column][pivot_column] - matrix[pivot_row][pivot_row]) / matrix[pivot_row][pivot_column]
        tangent = _sign(theta) / (abs(theta) + sqrt((theta * theta) + 1.0)) if theta != 0 else 1.0
        cosine = 1.0 / sqrt((tangent * tangent) + 1.0)
        sine = tangent * cosine

        for index in range(size):
            if index in {pivot_row, pivot_column}:
                continue
            left_value = matrix[index][pivot_row]
            right_value = matrix[index][pivot_column]
            matrix[index][pivot_row] = (cosine * left_value) - (sine * right_value)
            matrix[pivot_row][index] = matrix[index][pivot_row]
            matrix[index][pivot_column] = (sine * left_value) + (cosine * right_value)
            matrix[pivot_column][index] = matrix[index][pivot_column]

        diagonal_left = matrix[pivot_row][pivot_row]
        diagonal_right = matrix[pivot_column][pivot_column]
        off_diagonal = matrix[pivot_row][pivot_column]
        matrix[pivot_row][pivot_row] = ((cosine * cosine) * diagonal_left) - (2.0 * sine * cosine * off_diagonal) + ((sine * sine) * diagonal_right)
        matrix[pivot_column][pivot_column] = ((sine * sine) * diagonal_left) + (2.0 * sine * cosine * off_diagonal) + ((cosine * cosine) * diagonal_right)
        matrix[pivot_row][pivot_column] = 0.0
        matrix[pivot_column][pivot_row] = 0.0

    return min(matrix[index][index] for index in range(size))


def _sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0
