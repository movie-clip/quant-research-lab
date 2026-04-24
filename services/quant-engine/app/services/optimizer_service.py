from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import sqrt
from typing import cast

from app.instruments.registry import InstrumentRegistry
from app.schemas.optimizer import (
    OptimizationActiveGroupExposureDiagnostic,
    OptimizationConstraintEvaluation,
    OptimizationExAnteDiagnostics,
    OptimizationFeasibilityDiagnostics,
    OptimizationIssue,
    OptimizationReplayArtifact,
    OptimizationRequest,
    OptimizationResult,
    OptimizationRunMetadata,
    OptimizerActiveWeight,
    OptimizerGroupTaxonomy,
    OptimizerHardConstraints,
    OptimizerPenalty,
    OptimizerStatus,
    OptimizerUniverseAsset,
    OptimizerWeight,
)
from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionService, AlphaQualityPitTrustGate
from app.services.optimizer_alpha_service import (
    OptimizerAlphaPackageConfig,
    build_alpha_preference_vector,
    build_alpha_quality_package_from_live_pit_universe,
    validate_optimizer_alpha_package,
)
from app.services.optimizer_artifact_service import build_optimization_artifact
from app.services.optimizer_risk_service import compute_active_risk, project_to_active_risk_ball, validate_optimizer_risk_package


ENGINE_ID = "optimizer_service_v1"
METHODOLOGY_ID = "deterministic_constrained_optimizer_foundation_v4"
SOLVER_ID = "deterministic_projected_dykstra_v1"
TOLERANCE = 1e-8
BINDING_TOLERANCE = 1e-6
MAX_ITERATIONS = 4000
SUPPORTED_ACTIVE_GROUP_TAXONOMIES = {"sector"}


@dataclass(frozen=True)
class _ProblemAsset:
    symbol: str
    eligible: bool
    current_weight: float
    benchmark_weight: float
    target_weight: float
    lower_bound: float
    upper_bound: float
    concentration_cap: float
    taxonomy_labels: dict[str, str]


@dataclass(frozen=True)
class _ActiveGroupConstraint:
    taxonomy: OptimizerGroupTaxonomy
    group_name: str
    member_indices: tuple[int, ...]
    benchmark_weight: float
    max_abs_active_exposure: float
    member_symbols: tuple[str, ...]
    constraint_id: str

    @property
    def lower_bound(self) -> float:
        return self.benchmark_weight - self.max_abs_active_exposure

    @property
    def upper_bound(self) -> float:
        return self.benchmark_weight + self.max_abs_active_exposure


@dataclass(frozen=True)
class _NormalizedProblem:
    assets: tuple[_ProblemAsset, ...]
    objective_id: str
    turnover_cap: float | None
    active_risk_cap: float | None
    active_group_constraints: tuple[_ActiveGroupConstraint, ...]
    risk_package_id: str | None
    risk_package_version: str | None
    risk_package_representation: str | None
    risk_package_rebalance_date: str | None
    risk_package_coverage_ratio: float | None
    risk_package_pairwise_coverage_ratio: float | None
    risk_package_diagonal_fallback_count: int | None
    covariance_matrix: tuple[tuple[float, ...], ...] | None
    alpha_package_id: str | None
    alpha_package_version: str | None
    alpha_package_rebalance_date: str | None
    alpha_package_coverage_ratio: float | None
    alpha_preference_l1_budget: float | None


def run_optimizer(request: OptimizationRequest) -> OptimizationResult:
    uses_alpha_objective = request.objective.objective_id == "maximize_alpha_quality_v1"
    effective_request = request if uses_alpha_objective else request.model_copy(update={"alpha_package": None})
    validation_issues = _validate_request(effective_request)
    if validation_issues:
        return _build_terminal_result(
            effective_request,
            status="rejected",
            issues=validation_issues,
            proposed_weights=[],
            converged=False,
            iteration_count=0,
            constraint_residual=None,
        )

    if effective_request.risk_package is not None:
        risk_package_issues = validate_optimizer_risk_package(
            effective_request.risk_package,
            expected_symbols=[item.symbol for item in effective_request.universe] + [item.symbol for item in effective_request.current_portfolio_weights] + [item.symbol for item in effective_request.benchmark_weights],
            benchmark_weights=effective_request.benchmark_weights,
        )
        if risk_package_issues:
            return _build_terminal_result(
                effective_request,
                status="rejected",
                issues=risk_package_issues,
                proposed_weights=[],
                converged=False,
                iteration_count=0,
                constraint_residual=None,
            )

    if uses_alpha_objective and effective_request.alpha_package is not None:
        alpha_package_issues = validate_optimizer_alpha_package(
            effective_request.alpha_package,
            expected_symbols=[item.symbol for item in effective_request.universe] + [item.symbol for item in effective_request.current_portfolio_weights] + [item.symbol for item in effective_request.benchmark_weights],
        )
        if alpha_package_issues:
            return _build_terminal_result(
                effective_request,
                status="rejected",
                issues=alpha_package_issues,
                proposed_weights=[],
                converged=False,
                iteration_count=0,
                constraint_residual=None,
            )
        if effective_request.alpha_package.diagnostics.status != "ok":
            return _build_terminal_result(
                effective_request,
                status="rejected",
                issues=[
                    OptimizationIssue(
                        code="alpha_package_inputs_invalid",
                        message="alpha_quality_v1 objective requires an optimizer alpha package with complete, fresh, non-fallback coverage.",
                        actual_value=effective_request.alpha_package.diagnostics.status,
                        required_value="ok",
                        symbols=sorted(
                            set(
                                effective_request.alpha_package.diagnostics.missing_snapshot_symbols
                                + effective_request.alpha_package.diagnostics.stale_symbols
                                + effective_request.alpha_package.diagnostics.lag_blocked_symbols
                                + effective_request.alpha_package.diagnostics.fallback_symbols
                            )
                        ),
                    )
                ],
                proposed_weights=[],
                converged=False,
                iteration_count=0,
                constraint_residual=None,
            )
    problem = _normalize_problem(effective_request)
    feasibility_issues = _preflight_feasibility(problem, effective_request.hard_constraints)
    if feasibility_issues:
        return _build_terminal_result(
            effective_request,
            status="infeasible",
            issues=feasibility_issues,
            proposed_weights=[],
            converged=False,
            iteration_count=0,
            constraint_residual=None,
            problem=problem,
        )

    target = [asset.target_weight for asset in problem.assets]
    lower = [asset.lower_bound for asset in problem.assets]
    upper = [asset.upper_bound for asset in problem.assets]
    current = [asset.current_weight for asset in problem.assets]

    iterations = 1
    converged = True
    proposed, iterations, converged = _solve_problem(problem, target)

    evaluations = _build_constraint_evaluations(proposed, problem, effective_request.hard_constraints)
    violated = [item.constraint_id for item in evaluations if item.status == "violated"]
    residual = _constraint_residual(proposed, problem, effective_request.hard_constraints)
    if violated or not converged:
        issues = [
            OptimizationIssue(
                code="solver_failed_to_reach_feasible_point",
                constraint_id=violated[0] if violated else None,
                message="Deterministic solver did not return a point that satisfies every hard constraint within tolerance.",
                actual_value=round(residual, 10),
                required_value=round(TOLERANCE, 10),
                gap=round(max(residual - TOLERANCE, 0.0), 10),
                symbols=[],
            )
        ]
        return _build_terminal_result(
            effective_request,
            status="infeasible",
            issues=issues,
            proposed_weights=[],
            converged=converged,
            iteration_count=iterations,
            constraint_residual=residual,
            problem=problem,
        )

    return _build_terminal_result(
        effective_request,
        status="feasible",
        issues=[],
        proposed_weights=proposed,
        converged=converged,
        iteration_count=iterations,
        constraint_residual=residual,
        problem=problem,
        evaluations=evaluations,
    )


def assemble_optimizer_request_with_trusted_pit_alpha(
    request: OptimizationRequest,
    *,
    alpha_as_of_date: str | None = None,
    config: OptimizerAlphaPackageConfig | None = None,
    ingestion_service: AlphaQualityPitIngestionService | None = None,
    trust_gate: AlphaQualityPitTrustGate | None = None,
) -> OptimizationRequest:
    rebalance_date = datetime.fromisoformat(request.effective_timestamp).date().isoformat()
    as_of_date = alpha_as_of_date or datetime.fromisoformat(request.as_of_timestamp).date().isoformat()
    alpha_package = build_alpha_quality_package_from_live_pit_universe(
        rebalance_date=rebalance_date,
        as_of_date=as_of_date,
        universe_symbols=_optimizer_request_symbols(request),
        config=config,
        ingestion_service=ingestion_service,
        trust_gate=trust_gate,
    )
    return request.model_copy(update={"alpha_package": alpha_package})


def _validate_request(request: OptimizationRequest) -> list[OptimizationIssue]:
    issues: list[OptimizationIssue] = []
    registry = InstrumentRegistry()
    current_symbols = [item.symbol.upper() for item in request.current_portfolio_weights]
    benchmark_symbols = [item.symbol.upper() for item in request.benchmark_weights]
    universe_symbols = [item.symbol.upper() for item in request.universe]

    for scope, symbols in (
        ("current_portfolio_weights", current_symbols),
        ("benchmark_weights", benchmark_symbols),
        ("universe", universe_symbols),
    ):
        duplicates = _duplicates(symbols)
        if duplicates:
            issues.append(
                OptimizationIssue(
                    code="duplicate_symbols",
                    message=f"{scope} contains duplicate symbols and cannot be normalized deterministically.",
                    required_value="unique_symbols",
                    actual_value=",".join(duplicates),
                    symbols=duplicates,
                )
            )

    current_sum = sum(item.weight for item in request.current_portfolio_weights)
    benchmark_sum = sum(item.weight for item in request.benchmark_weights)
    if abs(current_sum - 1.0) > BINDING_TOLERANCE:
        issues.append(
            OptimizationIssue(
                code="current_weights_must_sum_to_one",
                message="Current portfolio weights must sum to 1.0 for turnover-constrained optimization.",
                actual_value=round(current_sum, 8),
                required_value=1.0,
                gap=round(abs(current_sum - 1.0), 8),
            )
        )
    if abs(benchmark_sum - 1.0) > BINDING_TOLERANCE:
        issues.append(
            OptimizationIssue(
                code="benchmark_weights_must_sum_to_one",
                message="Benchmark weights must sum to 1.0 because benchmark-relative behavior is enforced as a hard constraint.",
                actual_value=round(benchmark_sum, 8),
                required_value=1.0,
                gap=round(abs(benchmark_sum - 1.0), 8),
            )
        )

    if not request.universe:
        issues.append(
            OptimizationIssue(
                code="missing_universe",
                message="Universe input is required because the optimizer must not propose holdings outside the eligible universe.",
                required_value="non_empty_universe",
            )
        )

    if request.hard_constraints.benchmark_relative.max_abs_active_weight > 1.0:
        issues.append(
            OptimizationIssue(
                code="active_weight_limit_out_of_range",
                constraint_id="benchmark_relative_max_abs_active_weight",
                message="max_abs_active_weight must be in the closed interval [0, 1].",
                actual_value=request.hard_constraints.benchmark_relative.max_abs_active_weight,
                required_value=1.0,
            )
        )

    configured_taxonomies = [item.taxonomy for item in request.hard_constraints.active_group_exposures]
    duplicate_taxonomies = _duplicates(configured_taxonomies)
    if duplicate_taxonomies:
        issues.append(
            OptimizationIssue(
                code="duplicate_active_group_taxonomies",
                message="Each active group-exposure taxonomy can be configured at most once per optimizer request.",
                required_value="unique_taxonomies",
                actual_value=",".join(duplicate_taxonomies),
                symbols=duplicate_taxonomies,
            )
        )

    for group_constraint in request.hard_constraints.active_group_exposures:
        if group_constraint.taxonomy not in SUPPORTED_ACTIVE_GROUP_TAXONOMIES:
            issues.append(
                OptimizationIssue(
                    code="unsupported_active_group_taxonomy",
                    constraint_id=_taxonomy_constraint_id(group_constraint.taxonomy),
                    message="Requested active group-exposure taxonomy is not yet supported by the stable optimizer data contract.",
                    actual_value=group_constraint.taxonomy,
                    required_value=",".join(sorted(SUPPORTED_ACTIVE_GROUP_TAXONOMIES)),
                )
            )
            continue

        missing_symbols = sorted(
            symbol
            for symbol in sorted(set(current_symbols) | set(benchmark_symbols) | set(universe_symbols))
            if _resolve_request_taxonomy_label(symbol, request, group_constraint.taxonomy, registry) is None
        )
        if missing_symbols:
            issues.append(
                OptimizationIssue(
                    code="missing_active_group_taxonomy_labels",
                    constraint_id=_taxonomy_constraint_id(group_constraint.taxonomy),
                    message="Configured active group-exposure hard constraint requires stable taxonomy labels for every optimizer symbol.",
                    actual_value=",".join(missing_symbols),
                    required_value=group_constraint.taxonomy,
                    symbols=missing_symbols,
                )
            )

    for asset in request.universe:
        minimum = asset.min_weight
        maximum = asset.max_weight
        if minimum is not None and maximum is not None and minimum > maximum + TOLERANCE:
            issues.append(
                OptimizationIssue(
                    code="invalid_universe_bounds",
                    message="Universe asset min_weight cannot exceed max_weight.",
                    actual_value=minimum,
                    required_value=maximum,
                    gap=round(minimum - maximum, 8),
                    symbols=[asset.symbol.upper()],
                )
            )

    if request.hard_constraints.risk.max_active_risk is not None and request.risk_package is None:
        issues.append(
            OptimizationIssue(
                code="missing_risk_package",
                constraint_id="active_risk_cap",
                message="Active-risk control requires a deterministic optimizer risk package aligned to the optimizer universe and benchmark.",
                required_value="risk_package",
            )
        )

    if request.objective.objective_id == "maximize_alpha_quality_v1" and request.alpha_package is None:
        issues.append(
            OptimizationIssue(
                code="missing_alpha_package",
                message="alpha_quality_v1 objective requires a deterministic optimizer alpha package aligned to the optimizer universe.",
                required_value="alpha_package",
            )
        )

    supported_penalties = {"l2_distance_to_current"}
    unsupported_penalties = sorted({item.penalty_id for item in request.penalties if item.penalty_id not in supported_penalties})
    if unsupported_penalties:
        issues.append(
            OptimizationIssue(
                code="unsupported_penalty",
                message="Optimizer request includes a penalty that is not supported in sprint 1.",
                actual_value=",".join(unsupported_penalties),
                required_value="l2_distance_to_current",
            )
        )

    return issues


def _optimizer_request_symbols(request: OptimizationRequest) -> list[str]:
    return sorted(
        {
            item.symbol.upper()
            for item in request.universe + request.current_portfolio_weights + request.benchmark_weights
        }
    )


def _normalize_problem(request: OptimizationRequest) -> _NormalizedProblem:
    registry = InstrumentRegistry()
    current_map = _weight_map(request.current_portfolio_weights)
    benchmark_map = _weight_map(request.benchmark_weights)
    universe_map = {item.symbol.upper(): item for item in request.universe}
    all_symbols = sorted(set(current_map) | set(benchmark_map) | set(universe_map))
    active_limit = request.hard_constraints.benchmark_relative.max_abs_active_weight
    default_cap = request.hard_constraints.position_limits.default_max_weight
    turnover_cap = request.hard_constraints.turnover.max_turnover
    active_risk_cap = request.hard_constraints.risk.max_active_risk
    penalty_gamma = _stability_penalty_weight(request.penalties)
    alpha_package_id: str | None = None
    alpha_package_version: str | None = None
    alpha_package_rebalance_date: str | None = None
    alpha_package_coverage_ratio: float | None = None
    alpha_preference_l1_budget: float | None = None
    alpha_preference_map: dict[str, float] = {symbol: 0.0 for symbol in all_symbols}
    if request.objective.objective_id == "maximize_alpha_quality_v1" and request.alpha_package is not None:
        alpha_package_id = request.alpha_package.package_id
        alpha_package_version = request.alpha_package.version
        alpha_package_rebalance_date = request.alpha_package.rebalance_date
        alpha_package_coverage_ratio = request.alpha_package.diagnostics.coverage_ratio
        preference_vector, alpha_preference_l1_budget = build_alpha_preference_vector(
            ordered_symbols=all_symbols,
            benchmark_weights=[benchmark_map.get(symbol, 0.0) for symbol in all_symbols],
            eligible_mask=[(universe_map.get(symbol) or OptimizerUniverseAsset(symbol=symbol, eligible=False)).eligible for symbol in all_symbols],
            alpha_package=request.alpha_package,
            benchmark_active_limit=active_limit,
        )
        alpha_preference_map = {symbol: tilt for symbol, tilt in zip(all_symbols, preference_vector)}

    assets: list[_ProblemAsset] = []
    for symbol in all_symbols:
        universe_asset = universe_map.get(symbol) or OptimizerUniverseAsset(symbol=symbol, eligible=False, min_weight=0.0, max_weight=0.0, taxonomy_labels={})
        current_weight = current_map.get(symbol, 0.0)
        benchmark_weight = benchmark_map.get(symbol, 0.0)
        base_min = universe_asset.min_weight if universe_asset.min_weight is not None else 0.0
        concentration_cap = universe_asset.max_weight if universe_asset.max_weight is not None else 1.0
        if default_cap is not None:
            concentration_cap = min(concentration_cap, default_cap)
        if not universe_asset.eligible:
            concentration_cap = 0.0
        lower_bound = max(base_min, max(0.0, benchmark_weight - active_limit))
        upper_bound = min(concentration_cap, benchmark_weight + active_limit)
        base_target = ((benchmark_weight + (penalty_gamma * current_weight)) / (1.0 + penalty_gamma)) if penalty_gamma > 0 else benchmark_weight
        target_weight = base_target + alpha_preference_map.get(symbol, 0.0)
        taxonomy_labels = _resolve_taxonomy_labels(symbol, universe_asset, registry)
        assets.append(
            _ProblemAsset(
                symbol=symbol,
                eligible=universe_asset.eligible,
                current_weight=current_weight,
                benchmark_weight=benchmark_weight,
                target_weight=target_weight,
                lower_bound=lower_bound,
                upper_bound=upper_bound,
                concentration_cap=concentration_cap,
                taxonomy_labels=taxonomy_labels,
            )
        )

    active_group_constraints = _build_active_group_constraints(assets, request.hard_constraints)

    covariance_matrix: tuple[tuple[float, ...], ...] | None = None
    risk_package_id: str | None = None
    risk_package_version: str | None = None
    risk_package_representation: str | None = None
    risk_package_rebalance_date: str | None = None
    risk_package_coverage_ratio: float | None = None
    risk_package_pairwise_coverage_ratio: float | None = None
    risk_package_diagonal_fallback_count: int | None = None
    if request.risk_package is not None:
        risk_package_id = request.risk_package.package_id
        risk_package_version = request.risk_package.version
        risk_package_representation = request.risk_package.representation
        risk_package_rebalance_date = request.risk_package.rebalance_date
        risk_package_coverage_ratio = request.risk_package.diagnostics.coverage_ratio
        risk_package_pairwise_coverage_ratio = request.risk_package.diagnostics.pairwise_coverage_ratio
        risk_package_diagonal_fallback_count = len(request.risk_package.diagnostics.diagonal_fallback_symbols)
        covariance_matrix = tuple(tuple(value for value in row) for row in request.risk_package.covariance_matrix)

    return _NormalizedProblem(
        assets=tuple(assets),
        objective_id=request.objective.objective_id,
        turnover_cap=turnover_cap,
        active_risk_cap=active_risk_cap,
        active_group_constraints=active_group_constraints,
        risk_package_id=risk_package_id,
        risk_package_version=risk_package_version,
        risk_package_representation=risk_package_representation,
        risk_package_rebalance_date=risk_package_rebalance_date,
        risk_package_coverage_ratio=risk_package_coverage_ratio,
        risk_package_pairwise_coverage_ratio=risk_package_pairwise_coverage_ratio,
        risk_package_diagonal_fallback_count=risk_package_diagonal_fallback_count,
        covariance_matrix=covariance_matrix,
        alpha_package_id=alpha_package_id,
        alpha_package_version=alpha_package_version,
        alpha_package_rebalance_date=alpha_package_rebalance_date,
        alpha_package_coverage_ratio=alpha_package_coverage_ratio,
        alpha_preference_l1_budget=alpha_preference_l1_budget,
    )


def _preflight_feasibility(problem: _NormalizedProblem, constraints: OptimizerHardConstraints) -> list[OptimizationIssue]:
    issues: list[OptimizationIssue] = []
    lower_sum = sum(asset.lower_bound for asset in problem.assets)
    upper_sum = sum(asset.upper_bound for asset in problem.assets)

    for asset in problem.assets:
        if asset.lower_bound > asset.upper_bound + TOLERANCE:
            issues.append(
                OptimizationIssue(
                    code="symbol_bounds_infeasible",
                    constraint_id="benchmark_relative_max_abs_active_weight",
                    message="Combined eligibility, concentration, and benchmark-relative hard bounds leave no feasible weight for this symbol.",
                    actual_value=round(asset.lower_bound, 8),
                    required_value=round(asset.upper_bound, 8),
                    gap=round(asset.lower_bound - asset.upper_bound, 8),
                    symbols=[asset.symbol],
                )
            )

    if lower_sum > 1.0 + TOLERANCE:
        issues.append(
            OptimizationIssue(
                code="lower_bounds_exceed_full_investment",
                constraint_id="full_investment",
                message="Hard lower bounds require more than 100% capital, so the optimization problem is infeasible.",
                actual_value=round(lower_sum, 8),
                required_value=1.0,
                gap=round(lower_sum - 1.0, 8),
            )
        )
    if upper_sum < 1.0 - TOLERANCE:
        issues.append(
            OptimizationIssue(
                code="upper_bounds_below_full_investment",
                constraint_id="full_investment",
                message="Hard upper bounds leave less than 100% investable capacity, so full investment cannot be satisfied.",
                actual_value=round(upper_sum, 8),
                required_value=1.0,
                gap=round(1.0 - upper_sum, 8),
            )
        )

    if constraints.turnover.max_turnover is not None:
        min_turnover = _minimum_required_turnover(problem)
        if min_turnover > constraints.turnover.max_turnover + TOLERANCE:
            issues.append(
                OptimizationIssue(
                    code="turnover_cap_too_tight",
                    constraint_id="turnover_cap",
                    message="The turnover cap is below the minimum turnover required to satisfy the other hard constraints.",
                    actual_value=round(min_turnover, 8),
                    required_value=round(constraints.turnover.max_turnover, 8),
                    gap=round(min_turnover - constraints.turnover.max_turnover, 8),
                    symbols=[asset.symbol for asset in problem.assets if asset.current_weight > asset.upper_bound + TOLERANCE or asset.current_weight < asset.lower_bound - TOLERANCE],
                )
            )

    for group_constraint in problem.active_group_constraints:
        feasible_lower, feasible_upper = _group_feasible_interval(problem, group_constraint)
        required_lower = max(0.0, group_constraint.lower_bound)
        required_upper = min(1.0, group_constraint.upper_bound)
        if feasible_upper < required_lower - TOLERANCE or feasible_lower > required_upper + TOLERANCE:
            gap = max(required_lower - feasible_upper, feasible_lower - required_upper, 0.0)
            issues.append(
                OptimizationIssue(
                    code="active_group_constraint_infeasible",
                    constraint_id=group_constraint.constraint_id,
                    message="Active group-exposure hard bounds are infeasible given the symbol-level hard constraints and full-investment requirement.",
                    actual_value=f"[{round(feasible_lower, 8)}, {round(feasible_upper, 8)}]",
                    required_value=f"[{round(required_lower, 8)}, {round(required_upper, 8)}]",
                    gap=round(gap, 8),
                    symbols=list(group_constraint.member_symbols),
                )
            )

    return issues


def _solve_problem(problem: _NormalizedProblem, target: list[float]) -> tuple[list[float], int, bool]:
    if not target:
        return [], 0, True
    if problem.turnover_cap is None and problem.active_risk_cap is None and not problem.active_group_constraints:
        return _project_to_bounded_simplex(target, [asset.lower_bound for asset in problem.assets], [asset.upper_bound for asset in problem.assets]), 1, True
    if problem.turnover_cap is not None and problem.active_risk_cap is None and not problem.active_group_constraints:
        projected_target = _project_to_bounded_simplex(target, [asset.lower_bound for asset in problem.assets], [asset.upper_bound for asset in problem.assets])
        current = [asset.current_weight for asset in problem.assets]
        if _turnover(projected_target, current) <= problem.turnover_cap + BINDING_TOLERANCE:
            return projected_target, 1, True
        return _project_with_turnover_cap(problem, target)
    return _project_with_optional_risk_cap(problem, target)


def _project_with_turnover_cap(problem: _NormalizedProblem, target: list[float]) -> tuple[list[float], int, bool]:
    lower = [asset.lower_bound for asset in problem.assets]
    upper = [asset.upper_bound for asset in problem.assets]
    current = [asset.current_weight for asset in problem.assets]
    radius = 2.0 * (problem.turnover_cap or 0.0)
    x = list(target)
    p = [0.0] * len(target)
    q = [0.0] * len(target)

    for iteration in range(1, MAX_ITERATIONS + 1):
        y_input = [x_i + p_i for x_i, p_i in zip(x, p)]
        y = _project_to_bounded_simplex(y_input, lower, upper)
        p = [y_in - y_out for y_in, y_out in zip(y_input, y)]

        z_input = [y_i + q_i for y_i, q_i in zip(y, q)]
        x_next = _project_to_l1_ball(z_input, current, radius)
        q = [z_in - z_out for z_in, z_out in zip(z_input, x_next)]

        delta = max(abs(left - right) for left, right in zip(x_next, x)) if x else 0.0
        x = x_next
        residual = max(
            _bounded_simplex_distance(x, lower, upper),
            max(_turnover(x, current) - (problem.turnover_cap or 0.0), 0.0),
        )
        if delta <= TOLERANCE and residual <= BINDING_TOLERANCE:
            return x, iteration, True

    return x, MAX_ITERATIONS, False


def _project_with_optional_risk_cap(problem: _NormalizedProblem, target: list[float]) -> tuple[list[float], int, bool]:
    lower = [asset.lower_bound for asset in problem.assets]
    upper = [asset.upper_bound for asset in problem.assets]
    current = [asset.current_weight for asset in problem.assets]
    benchmark = [asset.benchmark_weight for asset in problem.assets]
    covariance_matrix = [list(row) for row in (problem.covariance_matrix or tuple())]
    x = list(target)
    p_simplex = [0.0] * len(target)
    p_turnover = [0.0] * len(target)
    p_groups = [[0.0] * len(target) for _ in problem.active_group_constraints]
    p_risk = [0.0] * len(target)

    for iteration in range(1, MAX_ITERATIONS + 1):
        simplex_input = [x_i + p_i for x_i, p_i in zip(x, p_simplex)]
        simplex_projected = _project_to_bounded_simplex(simplex_input, lower, upper)
        p_simplex = [left - right for left, right in zip(simplex_input, simplex_projected)]

        turnover_projected = simplex_projected
        if problem.turnover_cap is not None:
            turnover_input = [x_i + p_i for x_i, p_i in zip(simplex_projected, p_turnover)]
            turnover_projected = _project_to_l1_ball(turnover_input, current, 2.0 * problem.turnover_cap)
            p_turnover = [left - right for left, right in zip(turnover_input, turnover_projected)]

        group_projected = turnover_projected
        for index, group_constraint in enumerate(problem.active_group_constraints):
            group_input = [x_i + p_i for x_i, p_i in zip(group_projected, p_groups[index])]
            group_projected = _project_to_group_exposure_slab(group_input, group_constraint)
            p_groups[index] = [left - right for left, right in zip(group_input, group_projected)]

        risk_projected = group_projected
        if problem.active_risk_cap is not None and covariance_matrix:
            risk_input = [x_i + p_i for x_i, p_i in zip(group_projected, p_risk)]
            risk_projected = project_to_active_risk_ball(risk_input, benchmark, covariance_matrix, problem.active_risk_cap)
            p_risk = [left - right for left, right in zip(risk_input, risk_projected)]

        delta = max(abs(left - right) for left, right in zip(risk_projected, x)) if x else 0.0
        x = risk_projected
        residual = _problem_residual(x, problem)
        if delta <= TOLERANCE and residual <= BINDING_TOLERANCE:
            return x, iteration, True

    return x, MAX_ITERATIONS, False


def _build_terminal_result(
    request: OptimizationRequest,
    *,
    status: OptimizerStatus,
    issues: list[OptimizationIssue],
    proposed_weights: list[float],
    converged: bool,
    iteration_count: int,
    constraint_residual: float | None,
    problem: _NormalizedProblem | None = None,
    evaluations: list[OptimizationConstraintEvaluation] | None = None,
) -> OptimizationResult:
    normalized_problem = problem or _normalize_problem_for_replay(request)
    proposed_weight_rows: list[OptimizerWeight] = _weights_from_vector(proposed_weights, normalized_problem) if proposed_weights else []
    active_weight_rows: list[OptimizerActiveWeight] = _active_weights_from_vector(proposed_weights, normalized_problem) if proposed_weights else []
    evaluation_rows = evaluations or []
    binding_constraints = [item.constraint_id for item in evaluation_rows if item.status == "binding"]
    violated_constraints = [item.constraint_id for item in evaluation_rows if item.status == "violated"]
    if status != "feasible":
        violated_constraints = violated_constraints or sorted({item.constraint_id for item in issues if item.constraint_id is not None})

    summary = _diagnostic_summary(status, issues)
    base_result = OptimizationResult.model_construct(
        request_id=request.request_id,
        objective=request.objective,
        hard_constraints=request.hard_constraints,
        penalties=request.penalties,
        proposed_weights=proposed_weight_rows,
        active_weights=active_weight_rows,
        feasibility=OptimizationFeasibilityDiagnostics(
            status=cast(OptimizerStatus, status),
            summary=summary,
            issues=issues,
            binding_constraints=binding_constraints,
            violated_constraints=violated_constraints,
        ),
        constraint_evaluations=evaluation_rows,
        ex_ante_diagnostics=_build_ex_ante_diagnostics(proposed_weights, normalized_problem) if proposed_weights else OptimizationExAnteDiagnostics(
            eligible_names_count=sum(1 for asset in normalized_problem.assets if asset.eligible),
            benchmark_weight_coverage=round(sum(asset.benchmark_weight for asset in normalized_problem.assets if asset.eligible), 8),
            risk_package_coverage_ratio=normalized_problem.risk_package_coverage_ratio,
            risk_package_version=normalized_problem.risk_package_version,
            risk_package_representation=normalized_problem.risk_package_representation,
            risk_package_rebalance_date=normalized_problem.risk_package_rebalance_date,
            risk_package_pairwise_coverage_ratio=normalized_problem.risk_package_pairwise_coverage_ratio,
            risk_package_diagonal_fallback_count=normalized_problem.risk_package_diagonal_fallback_count,
            alpha_package_coverage_ratio=normalized_problem.alpha_package_coverage_ratio,
            alpha_package_version=normalized_problem.alpha_package_version,
            alpha_preference_applied=(normalized_problem.alpha_preference_l1_budget or 0.0) > 0.0,
            alpha_preference_l1_budget=normalized_problem.alpha_preference_l1_budget,
            active_group_exposures=[],
        ),
        run_metadata=OptimizationRunMetadata(
            engine_id=ENGINE_ID,
            methodology_id=METHODOLOGY_ID,
            solver_id=SOLVER_ID,
            risk_package_id=normalized_problem.risk_package_id,
            risk_package_version=normalized_problem.risk_package_version,
            risk_package_representation=normalized_problem.risk_package_representation,
            risk_package_rebalance_date=normalized_problem.risk_package_rebalance_date,
            risk_package_pairwise_coverage_ratio=normalized_problem.risk_package_pairwise_coverage_ratio,
            risk_package_diagonal_fallback_count=normalized_problem.risk_package_diagonal_fallback_count,
            alpha_package_id=normalized_problem.alpha_package_id,
            alpha_package_version=normalized_problem.alpha_package_version,
            alpha_package_rebalance_date=normalized_problem.alpha_package_rebalance_date,
            alpha_package_coverage_ratio=normalized_problem.alpha_package_coverage_ratio,
            alpha_preference_l1_budget=normalized_problem.alpha_preference_l1_budget,
            deterministic_symbol_order=[asset.symbol for asset in normalized_problem.assets],
            converged=converged,
            iteration_count=iteration_count,
            tolerance=TOLERANCE,
            max_iterations=MAX_ITERATIONS,
            constraint_residual=round(constraint_residual, 10) if constraint_residual is not None else None,
        ),
        replay=_build_replay_artifact(normalized_problem),
        artifact=None,
    )
    artifact = build_optimization_artifact(request, base_result)
    return base_result.model_copy(update={"artifact": artifact})


def _build_constraint_evaluations(
    proposed: list[float],
    problem: _NormalizedProblem,
    constraints: OptimizerHardConstraints,
) -> list[OptimizationConstraintEvaluation]:
    current = [asset.current_weight for asset in problem.assets]
    benchmark = [asset.benchmark_weight for asset in problem.assets]
    max_weight = max(proposed) if proposed else 0.0
    max_active = max(abs(weight - benchmark_weight) for weight, benchmark_weight in zip(proposed, benchmark)) if proposed else 0.0
    turnover = _turnover(proposed, current)
    zero_binding = [asset.symbol for asset, weight in zip(problem.assets, proposed) if abs(weight) <= BINDING_TOLERANCE]
    upper_binding = [asset.symbol for asset, weight in zip(problem.assets, proposed) if abs(weight - asset.upper_bound) <= BINDING_TOLERANCE]
    concentration_binding = [asset.symbol for asset, weight in zip(problem.assets, proposed) if abs(weight - asset.concentration_cap) <= BINDING_TOLERANCE]
    active_binding = [asset.symbol for asset, weight in zip(problem.assets, proposed) if abs(abs(weight - asset.benchmark_weight) - constraints.benchmark_relative.max_abs_active_weight) <= BINDING_TOLERANCE]
    ineligible_binding = [asset.symbol for asset, weight in zip(problem.assets, proposed) if (not asset.eligible) and abs(weight) <= BINDING_TOLERANCE]
    lower_violation = max((asset.lower_bound - weight) for asset, weight in zip(problem.assets, proposed))
    ineligible_weight = sum(weight for asset, weight in zip(problem.assets, proposed) if not asset.eligible)
    concentration_violation = max((weight - asset.concentration_cap) for asset, weight in zip(problem.assets, proposed))
    max_active_violation = max_active - constraints.benchmark_relative.max_abs_active_weight
    turnover_violation = turnover - constraints.turnover.max_turnover if constraints.turnover.max_turnover is not None else None
    active_risk = (
        compute_active_risk(proposed, benchmark, [list(row) for row in problem.covariance_matrix])
        if proposed and problem.active_risk_cap is not None and problem.covariance_matrix is not None
        else None
    )
    active_risk_violation = (active_risk - constraints.risk.max_active_risk) if active_risk is not None and constraints.risk.max_active_risk is not None else None
    group_evaluations = _build_active_group_constraint_evaluations(proposed, problem)

    return [
        OptimizationConstraintEvaluation(
            constraint_id="full_investment",
            status="binding" if abs(sum(proposed) - 1.0) <= BINDING_TOLERANCE else "violated",
            actual_value=round(sum(proposed), 8),
            limit_value=1.0,
            slack=round(1.0 - sum(proposed), 8),
            binding_symbols=[asset.symbol for asset in problem.assets],
            message="Portfolio remains fully invested.",
        ),
        OptimizationConstraintEvaluation(
            constraint_id="long_only",
            status="violated" if min(proposed) < -BINDING_TOLERANCE else ("binding" if zero_binding else "pass"),
            actual_value=round(min(proposed), 8) if proposed else None,
            limit_value=0.0,
            slack=round(max(0.0, min(proposed)), 8) if proposed else None,
            binding_symbols=zero_binding,
            message="All proposed weights are non-negative.",
        ),
        OptimizationConstraintEvaluation(
            constraint_id="eligible_universe_only",
            status="violated" if ineligible_weight > BINDING_TOLERANCE else ("binding" if ineligible_binding else "pass"),
            actual_value=round(ineligible_weight, 8),
            limit_value=0.0,
            slack=round(-ineligible_weight, 8),
            binding_symbols=ineligible_binding,
            message="No proposed holding sits outside the eligible universe.",
        ),
        OptimizationConstraintEvaluation(
            constraint_id="benchmark_relative_max_abs_active_weight",
            status="violated" if max_active_violation > BINDING_TOLERANCE else ("binding" if active_binding else "pass"),
            actual_value=round(max_active, 8),
            limit_value=constraints.benchmark_relative.max_abs_active_weight,
            slack=round(constraints.benchmark_relative.max_abs_active_weight - max_active, 8),
            binding_symbols=active_binding,
            message="Benchmark-relative active weights stay inside the hard active limit.",
        ),
        OptimizationConstraintEvaluation(
            constraint_id="concentration_max_weight",
            status="violated" if concentration_violation > BINDING_TOLERANCE else ("binding" if concentration_binding or upper_binding else "pass"),
            actual_value=round(max_weight, 8),
            limit_value=max((asset.concentration_cap for asset in problem.assets), default=None),
            slack=round(min((asset.concentration_cap - weight for asset, weight in zip(problem.assets, proposed)), default=0.0), 8),
            binding_symbols=sorted(set(concentration_binding + upper_binding)),
            message="Concentration caps are satisfied.",
        ),
        OptimizationConstraintEvaluation(
            constraint_id="turnover_cap",
            status=(
                "not_applicable"
                if constraints.turnover.max_turnover is None
                else "violated"
                if (turnover_violation or 0.0) > BINDING_TOLERANCE
                else "binding"
                if abs(turnover - constraints.turnover.max_turnover) <= BINDING_TOLERANCE
                else "pass"
            ),
            actual_value=round(turnover, 8),
            limit_value=constraints.turnover.max_turnover,
            slack=(round((constraints.turnover.max_turnover or 0.0) - turnover, 8) if constraints.turnover.max_turnover is not None else None),
            binding_symbols=[asset.symbol for asset, weight in zip(problem.assets, proposed) if abs(weight - asset.current_weight) > BINDING_TOLERANCE],
            message="Turnover stays inside the hard turnover cap.",
        ),
        OptimizationConstraintEvaluation(
            constraint_id="active_risk_cap",
            status=(
                "not_applicable"
                if constraints.risk.max_active_risk is None
                else "violated"
                if (active_risk_violation or 0.0) > BINDING_TOLERANCE
                else "binding"
                if active_risk is not None and abs(active_risk - constraints.risk.max_active_risk) <= BINDING_TOLERANCE
                else "pass"
            ),
            actual_value=round(active_risk, 8) if active_risk is not None else None,
            limit_value=constraints.risk.max_active_risk,
            slack=(round((constraints.risk.max_active_risk or 0.0) - active_risk, 8) if active_risk is not None and constraints.risk.max_active_risk is not None else None),
            binding_symbols=[asset.symbol for asset, weight in zip(problem.assets, proposed) if abs(weight - asset.benchmark_weight) > BINDING_TOLERANCE],
            message="Active risk stays inside the deterministic ex-ante hard cap.",
        ),
        *group_evaluations,
    ]


def _build_ex_ante_diagnostics(proposed: list[float], problem: _NormalizedProblem) -> OptimizationExAnteDiagnostics:
    benchmark = [asset.benchmark_weight for asset in problem.assets]
    current = [asset.current_weight for asset in problem.assets]
    active = [weight - benchmark_weight for weight, benchmark_weight in zip(proposed, benchmark)]
    active_share = 0.5 * sum(abs(item) for item in active)
    weight_hhi = sum(weight * weight for weight in proposed)
    active_risk = (
        compute_active_risk(proposed, benchmark, [list(row) for row in problem.covariance_matrix])
        if problem.covariance_matrix is not None
        else None
    )
    return OptimizationExAnteDiagnostics(
        active_share=round(active_share, 8),
        turnover=round(_turnover(proposed, current), 8),
        max_abs_active_weight=round(max((abs(item) for item in active), default=0.0), 8),
        active_risk=round(active_risk, 8) if active_risk is not None else None,
        weight_hhi=round(weight_hhi, 8),
        effective_holdings=round(1.0 / weight_hhi, 8) if weight_hhi > 0 else None,
        invested_names_count=sum(1 for weight in proposed if weight > BINDING_TOLERANCE),
        eligible_names_count=sum(1 for asset in problem.assets if asset.eligible),
        benchmark_weight_coverage=round(sum(asset.benchmark_weight for asset in problem.assets if asset.eligible), 8),
        risk_package_coverage_ratio=problem.risk_package_coverage_ratio,
        risk_package_version=problem.risk_package_version,
        risk_package_representation=problem.risk_package_representation,
        risk_package_rebalance_date=problem.risk_package_rebalance_date,
        risk_package_pairwise_coverage_ratio=problem.risk_package_pairwise_coverage_ratio,
        risk_package_diagonal_fallback_count=problem.risk_package_diagonal_fallback_count,
        alpha_package_coverage_ratio=problem.alpha_package_coverage_ratio,
        alpha_package_version=problem.alpha_package_version,
        alpha_preference_applied=(problem.alpha_preference_l1_budget or 0.0) > 0.0,
        alpha_preference_l1_budget=problem.alpha_preference_l1_budget,
        current_to_proposed_l2=round(_l2_distance(proposed, current), 8),
        benchmark_to_proposed_l2=round(_l2_distance(proposed, benchmark), 8),
        active_group_exposures=_build_active_group_diagnostics(proposed, problem),
    )


def _build_replay_artifact(problem: _NormalizedProblem) -> OptimizationReplayArtifact:
    return OptimizationReplayArtifact(
        ordered_symbols=[asset.symbol for asset in problem.assets],
        current_weights=[OptimizerWeight(symbol=asset.symbol, weight=round(asset.current_weight, 8)) for asset in problem.assets],
        benchmark_weights=[OptimizerWeight(symbol=asset.symbol, weight=round(asset.benchmark_weight, 8)) for asset in problem.assets],
        target_weights=[OptimizerWeight(symbol=asset.symbol, weight=round(asset.target_weight, 8)) for asset in problem.assets],
        lower_bounds=[OptimizerWeight(symbol=asset.symbol, weight=round(asset.lower_bound, 8)) for asset in problem.assets],
        upper_bounds=[OptimizerWeight(symbol=asset.symbol, weight=round(asset.upper_bound, 8)) for asset in problem.assets],
        turnover_cap=problem.turnover_cap,
        risk_package_id=problem.risk_package_id,
        alpha_package_id=problem.alpha_package_id,
    )


def _normalize_problem_for_replay(request: OptimizationRequest) -> _NormalizedProblem:
    try:
        return _normalize_problem(request)
    except Exception:
        return _NormalizedProblem(
            assets=tuple(),
            objective_id=request.objective.objective_id,
            turnover_cap=request.hard_constraints.turnover.max_turnover,
            active_risk_cap=request.hard_constraints.risk.max_active_risk,
            active_group_constraints=tuple(),
            risk_package_id=request.risk_package.package_id if request.risk_package is not None else None,
            risk_package_version=request.risk_package.version if request.risk_package is not None else None,
            risk_package_representation=request.risk_package.representation if request.risk_package is not None else None,
            risk_package_rebalance_date=request.risk_package.rebalance_date if request.risk_package is not None else None,
            risk_package_coverage_ratio=request.risk_package.diagnostics.coverage_ratio if request.risk_package is not None else None,
            risk_package_pairwise_coverage_ratio=request.risk_package.diagnostics.pairwise_coverage_ratio if request.risk_package is not None else None,
            risk_package_diagonal_fallback_count=len(request.risk_package.diagnostics.diagonal_fallback_symbols) if request.risk_package is not None else None,
            covariance_matrix=None,
            alpha_package_id=request.alpha_package.package_id if request.alpha_package is not None else None,
            alpha_package_version=request.alpha_package.version if request.alpha_package is not None else None,
            alpha_package_rebalance_date=request.alpha_package.rebalance_date if request.alpha_package is not None else None,
            alpha_package_coverage_ratio=request.alpha_package.diagnostics.coverage_ratio if request.alpha_package is not None else None,
            alpha_preference_l1_budget=None,
        )


def _weights_from_vector(vector: list[float], problem: _NormalizedProblem) -> list[OptimizerWeight]:
    return [OptimizerWeight(symbol=asset.symbol, weight=round(weight, 8)) for asset, weight in zip(problem.assets, vector)]


def _active_weights_from_vector(vector: list[float], problem: _NormalizedProblem) -> list[OptimizerActiveWeight]:
    return [OptimizerActiveWeight(symbol=asset.symbol, weight=round(weight - asset.benchmark_weight, 8)) for asset, weight in zip(problem.assets, vector)]


def _diagnostic_summary(status: str, issues: list[OptimizationIssue]) -> str:
    if status == "feasible":
        return "Deterministic constrained optimization completed successfully."
    if not issues:
        return "Optimization did not complete successfully."
    return issues[0].message


def _taxonomy_constraint_id(taxonomy: str) -> str:
    return f"active_group_exposure_{taxonomy}"


def _resolve_request_taxonomy_label(
    symbol: str,
    request: OptimizationRequest,
    taxonomy: OptimizerGroupTaxonomy,
    registry: InstrumentRegistry,
) -> str | None:
    universe_asset = next((item for item in request.universe if item.symbol.upper() == symbol.upper()), None)
    if universe_asset is not None and universe_asset.taxonomy_labels.get(taxonomy):
        return universe_asset.taxonomy_labels[taxonomy].strip()
    instrument = registry.get_instrument(symbol)
    if taxonomy == "sector" and instrument is not None and instrument.sector:
        return instrument.sector
    return None


def _resolve_taxonomy_labels(symbol: str, universe_asset: OptimizerUniverseAsset, registry: InstrumentRegistry) -> dict[str, str]:
    labels = {key: value.strip() for key, value in universe_asset.taxonomy_labels.items() if value and value.strip()}
    instrument = registry.get_instrument(symbol)
    if instrument is not None and instrument.sector:
        labels.setdefault("sector", instrument.sector)
    return labels


def _build_active_group_constraints(
    assets: list[_ProblemAsset],
    constraints: OptimizerHardConstraints,
) -> tuple[_ActiveGroupConstraint, ...]:
    active_group_constraints: list[_ActiveGroupConstraint] = []
    for configured_constraint in constraints.active_group_exposures:
        groups: dict[str, list[int]] = {}
        for index, asset in enumerate(assets):
            group_name = asset.taxonomy_labels.get(configured_constraint.taxonomy)
            if not group_name:
                continue
            groups.setdefault(group_name, []).append(index)

        for group_name in sorted(groups):
            member_indices = tuple(groups[group_name])
            benchmark_weight = sum(assets[index].benchmark_weight for index in member_indices)
            member_symbols = tuple(assets[index].symbol for index in member_indices)
            active_group_constraints.append(
                _ActiveGroupConstraint(
                    taxonomy=configured_constraint.taxonomy,
                    group_name=group_name,
                    member_indices=member_indices,
                    benchmark_weight=benchmark_weight,
                    max_abs_active_exposure=configured_constraint.max_abs_active_exposure,
                    member_symbols=member_symbols,
                    constraint_id=f"{_taxonomy_constraint_id(configured_constraint.taxonomy)}:{group_name}",
                )
            )
    return tuple(active_group_constraints)


def _group_weight(vector: list[float], member_indices: tuple[int, ...]) -> float:
    return sum(vector[index] for index in member_indices)


def _group_feasible_interval(problem: _NormalizedProblem, group_constraint: _ActiveGroupConstraint) -> tuple[float, float]:
    member_index_set = set(group_constraint.member_indices)
    group_lower = sum(problem.assets[index].lower_bound for index in group_constraint.member_indices)
    group_upper = sum(problem.assets[index].upper_bound for index in group_constraint.member_indices)
    non_group_lower = sum(asset.lower_bound for index, asset in enumerate(problem.assets) if index not in member_index_set)
    non_group_upper = sum(asset.upper_bound for index, asset in enumerate(problem.assets) if index not in member_index_set)
    feasible_lower = max(group_lower, 1.0 - non_group_upper)
    feasible_upper = min(group_upper, 1.0 - non_group_lower)
    return feasible_lower, feasible_upper


def _project_to_group_exposure_slab(vector: list[float], group_constraint: _ActiveGroupConstraint) -> list[float]:
    if not group_constraint.member_indices:
        return list(vector)
    current_group_weight = _group_weight(vector, group_constraint.member_indices)
    target_group_weight = current_group_weight
    lower_bound = max(0.0, group_constraint.lower_bound)
    upper_bound = min(1.0, group_constraint.upper_bound)
    if current_group_weight < lower_bound:
        target_group_weight = lower_bound
    elif current_group_weight > upper_bound:
        target_group_weight = upper_bound
    if abs(target_group_weight - current_group_weight) <= TOLERANCE:
        return list(vector)

    shift = (current_group_weight - target_group_weight) / len(group_constraint.member_indices)
    projected = list(vector)
    for index in group_constraint.member_indices:
        projected[index] -= shift
    return projected


def _build_active_group_constraint_evaluations(
    proposed: list[float],
    problem: _NormalizedProblem,
) -> list[OptimizationConstraintEvaluation]:
    evaluations: list[OptimizationConstraintEvaluation] = []
    for group_constraint in problem.active_group_constraints:
        group_weight = _group_weight(proposed, group_constraint.member_indices)
        active_weight = group_weight - group_constraint.benchmark_weight
        status = "violated" if abs(active_weight) - group_constraint.max_abs_active_exposure > BINDING_TOLERANCE else (
            "binding" if abs(abs(active_weight) - group_constraint.max_abs_active_exposure) <= BINDING_TOLERANCE else "pass"
        )
        evaluations.append(
            OptimizationConstraintEvaluation(
                constraint_id=group_constraint.constraint_id,
                status=status,
                actual_value=round(active_weight, 8),
                limit_value=group_constraint.max_abs_active_exposure,
                slack=round(group_constraint.max_abs_active_exposure - abs(active_weight), 8),
                binding_symbols=list(group_constraint.member_symbols),
                message=f"{group_constraint.taxonomy.title()} active exposure for {group_constraint.group_name} stays inside the hard benchmark-relative limit.",
            )
        )
    return evaluations


def _build_active_group_diagnostics(
    proposed: list[float],
    problem: _NormalizedProblem,
) -> list[OptimizationActiveGroupExposureDiagnostic]:
    diagnostics: list[OptimizationActiveGroupExposureDiagnostic] = []
    for group_constraint in problem.active_group_constraints:
        portfolio_weight = _group_weight(proposed, group_constraint.member_indices)
        active_weight = portfolio_weight - group_constraint.benchmark_weight
        status = "violated" if abs(active_weight) - group_constraint.max_abs_active_exposure > BINDING_TOLERANCE else (
            "binding" if abs(abs(active_weight) - group_constraint.max_abs_active_exposure) <= BINDING_TOLERANCE else "pass"
        )
        diagnostics.append(
            OptimizationActiveGroupExposureDiagnostic(
                constraint_id=group_constraint.constraint_id,
                taxonomy=group_constraint.taxonomy,
                group_name=group_constraint.group_name,
                portfolio_weight=round(portfolio_weight, 8),
                benchmark_weight=round(group_constraint.benchmark_weight, 8),
                active_weight=round(active_weight, 8),
                max_abs_active_exposure=group_constraint.max_abs_active_exposure,
                status=status,
            )
        )
    return diagnostics


def _problem_residual(proposed: list[float], problem: _NormalizedProblem) -> float:
    if not proposed:
        return 0.0
    lower = [asset.lower_bound for asset in problem.assets]
    upper = [asset.upper_bound for asset in problem.assets]
    current = [asset.current_weight for asset in problem.assets]
    benchmark = [asset.benchmark_weight for asset in problem.assets]
    residuals = [
        _bounded_simplex_distance(proposed, lower, upper),
    ]
    if problem.turnover_cap is not None:
        residuals.append(max(_turnover(proposed, current) - problem.turnover_cap, 0.0))
    residuals.extend(
        max(abs(_group_weight(proposed, group_constraint.member_indices) - group_constraint.benchmark_weight) - group_constraint.max_abs_active_exposure, 0.0)
        for group_constraint in problem.active_group_constraints
    )
    if problem.active_risk_cap is not None and problem.covariance_matrix is not None:
        residuals.append(
            max(
                compute_active_risk(proposed, benchmark, [list(row) for row in problem.covariance_matrix]) - problem.active_risk_cap,
                0.0,
            )
        )
    return max(residuals)


def _constraint_residual(proposed: list[float], problem: _NormalizedProblem, constraints: OptimizerHardConstraints) -> float:
    if not proposed:
        return 0.0
    lower = [asset.lower_bound for asset in problem.assets]
    upper = [asset.upper_bound for asset in problem.assets]
    benchmark = [asset.benchmark_weight for asset in problem.assets]
    current = [asset.current_weight for asset in problem.assets]
    residuals = [
        abs(sum(proposed) - 1.0),
        max(max(lower_i - weight, 0.0) for lower_i, weight in zip(lower, proposed)),
        max(max(weight - upper_i, 0.0) for upper_i, weight in zip(upper, proposed)),
        max(max(abs(weight - benchmark_weight) - constraints.benchmark_relative.max_abs_active_weight, 0.0) for weight, benchmark_weight in zip(proposed, benchmark)),
    ]
    if constraints.turnover.max_turnover is not None:
        residuals.append(max(_turnover(proposed, current) - constraints.turnover.max_turnover, 0.0))
    residuals.extend(
        max(abs(_group_weight(proposed, group_constraint.member_indices) - group_constraint.benchmark_weight) - group_constraint.max_abs_active_exposure, 0.0)
        for group_constraint in problem.active_group_constraints
    )
    if constraints.risk.max_active_risk is not None and problem.covariance_matrix is not None:
        residuals.append(
            max(
                compute_active_risk(proposed, benchmark, [list(row) for row in problem.covariance_matrix]) - constraints.risk.max_active_risk,
                0.0,
            )
        )
    return max(residuals)


def _bounded_simplex_distance(vector: list[float], lower: list[float], upper: list[float]) -> float:
    residuals = [abs(sum(vector) - 1.0)]
    residuals.extend(max(lower_i - value, 0.0) for lower_i, value in zip(lower, vector))
    residuals.extend(max(value - upper_i, 0.0) for upper_i, value in zip(upper, vector))
    return max(residuals)


def _minimum_required_turnover(problem: _NormalizedProblem) -> float:
    forced_buys = sum(max(asset.lower_bound - asset.current_weight, 0.0) for asset in problem.assets)
    forced_sells = sum(max(asset.current_weight - asset.upper_bound, 0.0) for asset in problem.assets)
    return max(forced_buys, forced_sells)


def _project_to_bounded_simplex(vector: list[float], lower: list[float], upper: list[float]) -> list[float]:
    if not vector:
        return []
    if abs(sum(lower) - 1.0) <= TOLERANCE:
        return list(lower)
    if abs(sum(upper) - 1.0) <= TOLERANCE:
        return list(upper)

    left = min(value - upper_bound for value, upper_bound in zip(vector, upper))
    right = max(value - lower_bound for value, lower_bound in zip(vector, lower))
    projected = list(lower)
    for _ in range(200):
        midpoint = (left + right) / 2.0
        projected = [min(upper_i, max(lower_i, value - midpoint)) for value, lower_i, upper_i in zip(vector, lower, upper)]
        if sum(projected) > 1.0:
            left = midpoint
        else:
            right = midpoint

    projected = [min(upper_i, max(lower_i, value - right)) for value, lower_i, upper_i in zip(vector, lower, upper)]
    return _repair_sum(projected, lower, upper)


def _project_to_l1_ball(vector: list[float], center: list[float], radius: float) -> list[float]:
    if radius <= 0:
        return list(center)
    shifted = [value - anchor for value, anchor in zip(vector, center)]
    norm = sum(abs(item) for item in shifted)
    if norm <= radius + TOLERANCE:
        return list(vector)

    magnitudes = sorted((abs(item) for item in shifted), reverse=True)
    cumulative = 0.0
    theta = 0.0
    for index, value in enumerate(magnitudes, start=1):
        cumulative += value
        candidate = (cumulative - radius) / index
        next_value = magnitudes[index] if index < len(magnitudes) else 0.0
        if value > candidate >= next_value:
            theta = candidate
            break

    projected = [
        anchor + _sign(delta) * max(abs(delta) - theta, 0.0)
        for anchor, delta in zip(center, shifted)
    ]
    return projected


def _repair_sum(vector: list[float], lower: list[float], upper: list[float]) -> list[float]:
    repaired = list(vector)
    residual = 1.0 - sum(repaired)
    if abs(residual) <= TOLERANCE:
        return repaired

    if residual > 0:
        for index in range(len(repaired)):
            room = upper[index] - repaired[index]
            if room <= 0:
                continue
            step = min(room, residual)
            repaired[index] += step
            residual -= step
            if residual <= TOLERANCE:
                break
    else:
        residual = -residual
        for index in range(len(repaired)):
            room = repaired[index] - lower[index]
            if room <= 0:
                continue
            step = min(room, residual)
            repaired[index] -= step
            residual -= step
            if residual <= TOLERANCE:
                break
    return repaired


def _duplicates(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    duplicates: list[str] = []
    for symbol in symbols:
        if symbol in seen and symbol not in duplicates:
            duplicates.append(symbol)
        seen.add(symbol)
    return sorted(duplicates)


def _weight_map(weights: list[OptimizerWeight]) -> dict[str, float]:
    return {item.symbol.upper(): item.weight for item in weights}


def _stability_penalty_weight(penalties: list[OptimizerPenalty]) -> float:
    return sum(item.penalty_weight for item in penalties if item.penalty_id == "l2_distance_to_current")




def _turnover(left: list[float], right: list[float]) -> float:
    return 0.5 * sum(abs(left_item - right_item) for left_item, right_item in zip(left, right))


def _l2_distance(left: list[float], right: list[float]) -> float:
    return sqrt(sum((left_item - right_item) ** 2 for left_item, right_item in zip(left, right)))


def _sign(value: float) -> float:
    if value > 0:
        return 1.0
    if value < 0:
        return -1.0
    return 0.0
