from datetime import datetime
from pathlib import Path

import json

import pytest

from app.schemas.optimizer import (
    OptimizerAlphaFundamentalSnapshot,
    OptimizerActiveGroupConstraint,
    OptimizerReturnBasisAttestation,
    OptimizerReturnBasisEvidenceBundle,
    OptimizerReturnBasisSectionTrust,
    OptimizerPreviewSnapshotReference,
    OptimizerPreviewBenchmarkInput,
    OptimizerPreviewPitAlphaInput,
    OptimizerPreviewRequest,
    OptimizationRequest,
    OptimizerBenchmarkRelativeConstraint,
    OptimizerHardConstraints,
    OptimizerPenalty,
    OptimizerPositionLimitConstraint,
    OptimizerTurnoverConstraint,
    OptimizerUniverseAsset,
    OptimizerWeight,
)
from app.schemas.imports import ImportedCashBalance, ImportedPortfolioSnapshot, ImportedPosition, ImportedStatement
from app.schemas.return_basis import ReturnBasisEvidence
from app.services.optimizer_alpha_fundamentals import load_alpha_pit_fundamentals_snapshot
from app.services.optimizer_alpha_service import build_alpha_quality_package
from app.services.optimizer_alpha_service import build_alpha_quality_package_from_pit_input
from app.services.optimizer_artifact_service import (
    InMemoryOptimizationArtifactStore,
    OptimizationArtifactPersistenceError,
    OptimizerHandoffStore,
    deserialize_optimization_artifact,
    load_optimizer_handoff_by_reference,
    load_raw_optimizer_handoff_by_reference,
    replay_optimization_result_from_artifact,
    serialize_optimization_artifact,
)
from app.services.optimizer_risk_service import build_optimizer_risk_package
from app.services.optimizer_preview_service import build_optimizer_preview
from app.services.optimizer_service import assemble_optimizer_request_with_trusted_pit_alpha, run_optimizer


PIT_FIXTURE_PATH = Path(__file__).with_name("alpha_quality_v1_pit_fixture.json")
ARTIFACT_FIXTURE_PATH = Path(__file__).with_name("optimizer_artifact_v1_acceptance.json")


def _base_request() -> OptimizationRequest:
    return OptimizationRequest(
        request_id="opt-1",
        as_of_timestamp="2024-04-15T09:30:00",
        effective_timestamp="2024-04-15T09:30:00",
        universe_id="optimizer_universe_large_cap_demo_v1",
        benchmark_id="benchmark_spy_demo_v1",
        current_portfolio_weights=[
            OptimizerWeight(symbol="AAA", weight=0.60),
            OptimizerWeight(symbol="BBB", weight=0.40),
        ],
        benchmark_weights=[
            OptimizerWeight(symbol="AAA", weight=0.50),
            OptimizerWeight(symbol="BBB", weight=0.30),
            OptimizerWeight(symbol="CCC", weight=0.20),
        ],
        universe=[
            OptimizerUniverseAsset(symbol="AAA", eligible=True),
            OptimizerUniverseAsset(symbol="BBB", eligible=True),
            OptimizerUniverseAsset(symbol="CCC", eligible=True),
        ],
        hard_constraints=OptimizerHardConstraints(
            benchmark_relative=OptimizerBenchmarkRelativeConstraint(max_abs_active_weight=0.10),
            position_limits=OptimizerPositionLimitConstraint(default_max_weight=0.60),
            turnover=OptimizerTurnoverConstraint(max_turnover=None),
        ),
    )


def _with_sector_taxonomy(request: OptimizationRequest) -> OptimizationRequest:
    request.universe[0].taxonomy_labels = {"sector": "Technology"}
    request.universe[1].taxonomy_labels = {"sector": "Financials"}
    request.universe[2].taxonomy_labels = {"sector": "Technology"}
    return request


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


def _risk_package():
    request = _base_request()
    return build_optimizer_risk_package(
        rebalance_date="2024-03-21",
        universe_symbols=[item.symbol for item in request.universe],
        benchmark_symbol="SPY",
        benchmark_weights=request.benchmark_weights,
        price_histories={
            "AAA": _price_history(100.0, [0.025, -0.015, 0.02, -0.01] * 20),
            "BBB": _price_history(100.0, [0.003, -0.002, 0.002, 0.001] * 20),
            "CCC": _price_history(100.0, [0.011, -0.009, 0.008, -0.004] * 20),
        },
    )


def _alpha_package(rebalance_date: str = "2024-04-15"):
    request = _base_request()
    return build_alpha_quality_package(
        rebalance_date=rebalance_date,
        universe_symbols=[item.symbol for item in request.universe],
        fundamental_snapshots=[
            OptimizerAlphaFundamentalSnapshot(
                symbol="AAA",
                statement_date="2023-12-31",
                period_type="annual",
                total_revenue=1000.0,
                cost_of_revenue=400.0,
                ebit=200.0,
                total_assets=800.0,
                operating_cash_flow=180.0,
                free_cash_flow=120.0,
                net_income=150.0,
                total_debt=160.0,
                cash_and_equivalents=60.0,
            ),
            OptimizerAlphaFundamentalSnapshot(
                symbol="BBB",
                statement_date="2023-12-31",
                period_type="annual",
                total_revenue=950.0,
                cost_of_revenue=500.0,
                ebit=150.0,
                total_assets=900.0,
                operating_cash_flow=110.0,
                free_cash_flow=80.0,
                net_income=120.0,
                total_debt=260.0,
                cash_and_equivalents=30.0,
            ),
            OptimizerAlphaFundamentalSnapshot(
                symbol="CCC",
                statement_date="2023-12-31",
                period_type="annual",
                total_revenue=700.0,
                cost_of_revenue=420.0,
                ebit=90.0,
                total_assets=850.0,
                operating_cash_flow=70.0,
                free_cash_flow=40.0,
                net_income=115.0,
                total_debt=320.0,
                cash_and_equivalents=20.0,
            ),
        ],
    )


def _pit_alpha_package(rebalance_date: str = "2024-04-15"):
    pit_input = load_alpha_pit_fundamentals_snapshot(PIT_FIXTURE_PATH)
    return build_alpha_quality_package_from_pit_input(
        rebalance_date=rebalance_date,
        pit_input=pit_input.model_copy(update={"decision_date": rebalance_date, "as_of_date": rebalance_date}),
    )


def _live_pit_request() -> OptimizationRequest:
    request = _base_request()
    request.current_portfolio_weights = [
        OptimizerWeight(symbol="AAPL", weight=0.60),
        OptimizerWeight(symbol="MSFT", weight=0.40),
    ]
    request.benchmark_weights = [
        OptimizerWeight(symbol="AAPL", weight=0.50),
        OptimizerWeight(symbol="MSFT", weight=0.30),
        OptimizerWeight(symbol="GOOG", weight=0.20),
    ]
    request.universe = [
        OptimizerUniverseAsset(symbol="AAPL", eligible=True),
        OptimizerUniverseAsset(symbol="MSFT", eligible=True),
        OptimizerUniverseAsset(symbol="GOOG", eligible=True),
    ]
    return request


def _imported_snapshot() -> ImportedPortfolioSnapshot:
    imported_at = datetime(2024, 4, 15, 9, 30, 0)
    statement = ImportedStatement(
        importer="interactive_brokers",
        imported_at=imported_at,
        source_path="IB2024.pdf",
        detected_format="statement_pdf",
        account_id="U1234567",
        base_currency="USD",
        statement_period="2024-04",
        page_count=4,
    )
    return ImportedPortfolioSnapshot(
        statement=statement,
        statements=[statement],
        statement_totals=None,
        instruments=[],
        cash_balances=[ImportedCashBalance(currency="USD", ending_cash=500.0)],
        positions=[
            ImportedPosition(
                as_of_date=imported_at.date(),
                symbol="AAA",
                quantity=10.0,
                cost_basis=60.0,
                close_price=6.0,
                market_value=60.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
            ImportedPosition(
                as_of_date=imported_at.date(),
                symbol="BBB",
                quantity=8.0,
                cost_basis=40.0,
                close_price=5.0,
                market_value=40.0,
                unrealized_pnl=0.0,
                currency="USD",
            ),
        ],
        ledger_entries=[],
    )


def _preview_request() -> OptimizerPreviewRequest:
    return OptimizerPreviewRequest(
        request_id="preview-1",
        universe_id="optimizer_universe_large_cap_demo_v1",
        snapshot=_imported_snapshot(),
        benchmark=OptimizerPreviewBenchmarkInput(
            benchmark_id="benchmark_spy_demo_v1",
            benchmark_version="2024-04-15",
            benchmark_symbol="SPY",
            source_name="test_benchmark_contract",
            as_of_timestamp="2024-04-15T09:30:00",
            weights=[
                OptimizerWeight(symbol="AAA", weight=0.50),
                OptimizerWeight(symbol="BBB", weight=0.30),
                OptimizerWeight(symbol="CCC", weight=0.20),
            ],
        ),
        universe=[
            OptimizerUniverseAsset(symbol="AAA", eligible=True),
            OptimizerUniverseAsset(symbol="BBB", eligible=True),
            OptimizerUniverseAsset(symbol="CCC", eligible=True),
        ],
        hard_constraints=OptimizerHardConstraints(
            benchmark_relative=OptimizerBenchmarkRelativeConstraint(max_abs_active_weight=0.10),
            position_limits=OptimizerPositionLimitConstraint(default_max_weight=0.60),
            turnover=OptimizerTurnoverConstraint(max_turnover=None),
        ),
    )


def test_run_optimizer_returns_deterministic_feasible_solution() -> None:
    request = _base_request()

    result = run_optimizer(request)

    assert result.feasibility.status == "feasible"
    assert result.proposed_weights == [
        OptimizerWeight(symbol="AAA", weight=0.5),
        OptimizerWeight(symbol="BBB", weight=0.3),
        OptimizerWeight(symbol="CCC", weight=0.2),
    ]
    assert result.active_weights[0].weight == 0.0
    assert result.active_weights[2].weight == 0.0
    assert result.ex_ante_diagnostics.turnover == 0.2
    assert result.ex_ante_diagnostics.active_share == 0.0
    assert result.run_metadata.deterministic_symbol_order == ["AAA", "BBB", "CCC"]
    assert result.replay.lower_bounds == [
        OptimizerWeight(symbol="AAA", weight=0.4),
        OptimizerWeight(symbol="BBB", weight=0.2),
        OptimizerWeight(symbol="CCC", weight=0.1),
    ]
    assert result.replay.upper_bounds == [
        OptimizerWeight(symbol="AAA", weight=0.6),
        OptimizerWeight(symbol="BBB", weight=0.4),
        OptimizerWeight(symbol="CCC", weight=0.3),
    ]
    assert any(item.constraint_id == "benchmark_relative_max_abs_active_weight" and item.status == "pass" for item in result.constraint_evaluations)
    assert any(item.constraint_id == "turnover_cap" and item.status == "not_applicable" for item in result.constraint_evaluations)
    assert result.artifact is not None
    assert result.artifact.schema_version == "optimizer_artifact_v1"
    assert result.artifact.universe_id == "optimizer_universe_large_cap_demo_v1"
    assert result.artifact.benchmark_id == "benchmark_spy_demo_v1"
    assert result.artifact.artifact_state.artifact_state == "complete"
    assert any(item.input_kind == "request" for item in result.artifact.input_fingerprints)
    assert any(item.attestation_type == "max_abs_active_weight" and item.status == "pass" for item in result.artifact.benchmark_relative_attestations)
    assert [item.model_dump() for item in result.artifact.trade_intents] == [
        {"symbol": "AAA", "action": "sell", "current_weight": 0.6, "proposed_weight": 0.5, "active_weight": 0.0, "trade_weight": -0.1},
        {"symbol": "BBB", "action": "sell", "current_weight": 0.4, "proposed_weight": 0.3, "active_weight": 0.0, "trade_weight": -0.1},
        {"symbol": "CCC", "action": "initiate", "current_weight": 0.0, "proposed_weight": 0.2, "active_weight": 0.0, "trade_weight": 0.2},
    ]


def test_run_optimizer_respects_turnover_cap_with_binding_diagnostics() -> None:
    request = _base_request()
    request.hard_constraints.turnover.max_turnover = 0.10

    result = run_optimizer(request)

    assert result.feasibility.status == "feasible"
    assert result.ex_ante_diagnostics.turnover == 0.1
    assert result.ex_ante_diagnostics.active_share == 0.1
    assert result.proposed_weights == [
        OptimizerWeight(symbol="AAA", weight=0.55),
        OptimizerWeight(symbol="BBB", weight=0.35),
        OptimizerWeight(symbol="CCC", weight=0.1),
    ]
    assert result.active_weights[0].weight == 0.05
    assert result.active_weights[1].weight == 0.05
    assert result.active_weights[2].weight == -0.1
    assert result.feasibility.binding_constraints == ["full_investment", "benchmark_relative_max_abs_active_weight", "turnover_cap"]
    assert any(item.constraint_id == "turnover_cap" and item.status == "binding" for item in result.constraint_evaluations)


def test_run_optimizer_returns_explicit_infeasibility_for_tight_turnover_cap() -> None:
    request = _base_request()
    request.hard_constraints.benchmark_relative.max_abs_active_weight = 0.02
    request.hard_constraints.turnover.max_turnover = 0.01

    result = run_optimizer(request)

    assert result.feasibility.status == "infeasible"
    assert result.proposed_weights == []
    assert result.feasibility.violated_constraints == ["turnover_cap"]
    assert result.feasibility.issues[0].code == "turnover_cap_too_tight"
    assert result.feasibility.issues[0].gap == 0.17
    assert result.feasibility.issues[0].symbols == ["AAA", "BBB", "CCC"]
    assert result.ex_ante_diagnostics.turnover is None
    assert result.artifact is not None
    assert result.artifact.artifact_state.artifact_state == "infeasible"
    assert result.artifact.failure_reasons[0].code == "turnover_cap_too_tight"


def test_run_optimizer_returns_explicit_infeasibility_for_ineligible_benchmark_name() -> None:
    request = _base_request()
    request.universe[2].eligible = False

    result = run_optimizer(request)

    assert result.feasibility.status == "infeasible"
    assert result.proposed_weights == []
    assert result.feasibility.issues[0].code == "symbol_bounds_infeasible"
    assert result.feasibility.issues[0].symbols == ["CCC"]
    assert result.feasibility.violated_constraints == ["benchmark_relative_max_abs_active_weight"]


def test_run_optimizer_supports_optional_stability_penalty_without_breaking_constraints() -> None:
    request = _base_request()
    request.penalties = [OptimizerPenalty(penalty_id="l2_distance_to_current", penalty_weight=1.0)]
    request.hard_constraints.turnover.max_turnover = 0.15

    result = run_optimizer(request)

    assert result.feasibility.status == "feasible"
    assert result.ex_ante_diagnostics.turnover == 0.1
    assert result.proposed_weights == [
        OptimizerWeight(symbol="AAA", weight=0.55),
        OptimizerWeight(symbol="BBB", weight=0.35),
        OptimizerWeight(symbol="CCC", weight=0.1),
    ]
    assert result.replay.target_weights == [
        OptimizerWeight(symbol="AAA", weight=0.55),
        OptimizerWeight(symbol="BBB", weight=0.35),
        OptimizerWeight(symbol="CCC", weight=0.1),
    ]


def test_run_optimizer_rejects_non_normalized_inputs() -> None:
    request = _base_request()
    request.current_portfolio_weights[0].weight = 0.70

    result = run_optimizer(request)

    assert result.feasibility.status == "rejected"
    assert result.proposed_weights == []
    assert result.feasibility.issues[0].code == "current_weights_must_sum_to_one"
    assert result.feasibility.violated_constraints == []


def test_run_optimizer_consumes_risk_package_and_enforces_active_risk_cap() -> None:
    request = _base_request()
    request.risk_package = _risk_package()
    request.hard_constraints.risk.max_active_risk = 0.02
    request.hard_constraints.turnover.max_turnover = 0.2
    request.penalties = [OptimizerPenalty(penalty_id="l2_distance_to_current", penalty_weight=20.0)]

    result = run_optimizer(request)

    assert result.feasibility.status == "feasible"
    assert result.run_metadata.risk_package_version == "optimizer_risk_package_v2"
    assert result.run_metadata.risk_package_representation == "structured_shrunk_covariance"
    assert result.run_metadata.risk_package_rebalance_date == "2024-03-21"
    assert result.run_metadata.risk_package_pairwise_coverage_ratio == 1.0
    assert result.run_metadata.risk_package_diagonal_fallback_count == 0
    assert result.replay.risk_package_id == request.risk_package.package_id
    assert result.ex_ante_diagnostics.active_risk is not None
    assert result.ex_ante_diagnostics.active_risk <= 0.020001
    assert result.ex_ante_diagnostics.risk_package_coverage_ratio == 1.0
    assert result.ex_ante_diagnostics.risk_package_representation == "structured_shrunk_covariance"
    assert result.ex_ante_diagnostics.risk_package_pairwise_coverage_ratio == 1.0
    assert result.ex_ante_diagnostics.risk_package_diagonal_fallback_count == 0
    assert any(item.constraint_id == "active_risk_cap" and item.status in {"binding", "pass"} for item in result.constraint_evaluations)
    assert result.proposed_weights != [
        OptimizerWeight(symbol="AAA", weight=0.5952381),
        OptimizerWeight(symbol="BBB", weight=0.3952381),
        OptimizerWeight(symbol="CCC", weight=0.00952381),
    ]


def test_run_optimizer_risk_v2_cleans_up_correlated_concentration_more_than_diagonal() -> None:
    request_v2 = _base_request()
    request_v2.current_portfolio_weights = [
        OptimizerWeight(symbol="AAA", weight=0.6),
        OptimizerWeight(symbol="BBB", weight=0.1),
        OptimizerWeight(symbol="CCC", weight=0.3),
    ]
    request_v2.penalties = [OptimizerPenalty(penalty_id="l2_distance_to_current", penalty_weight=30.0)]
    request_v2.hard_constraints.turnover.max_turnover = 0.4
    request_v2.hard_constraints.risk.max_active_risk = 0.015
    request_v2.risk_package = _risk_package()
    assert request_v2.risk_package is not None

    diagonal_request = request_v2.model_copy(deep=True)
    assert diagonal_request.risk_package is not None
    diagonal_request.risk_package.version = "optimizer_risk_package_v1"
    diagonal_request.risk_package.representation = "diagonal_covariance"
    diagonal_request.risk_package.covariance_matrix = [
        [row[index] if row_index == index else 0.0 for index, _ in enumerate(row)]
        for row_index, row in enumerate(diagonal_request.risk_package.covariance_matrix)
    ]
    diagonal_request.risk_package.package_id = f"legacy_{diagonal_request.risk_package.package_id}"

    result_v2 = run_optimizer(request_v2)
    result_diagonal = run_optimizer(diagonal_request)

    assert result_v2.feasibility.status == "feasible"
    assert result_diagonal.feasibility.status == "feasible"
    assert result_v2.proposed_weights[1].weight > result_diagonal.proposed_weights[1].weight
    assert result_v2.proposed_weights[2].weight < result_diagonal.proposed_weights[2].weight
    assert result_v2.ex_ante_diagnostics.weight_hhi is not None
    assert result_diagonal.ex_ante_diagnostics.weight_hhi is not None
    assert result_v2.ex_ante_diagnostics.weight_hhi < result_diagonal.ex_ante_diagnostics.weight_hhi
    assert result_v2.ex_ante_diagnostics.active_risk is not None
    assert result_v2.ex_ante_diagnostics.active_risk <= 0.015001
    assert max(abs(item.weight) for item in result_v2.active_weights) <= 0.100001
    assert abs(sum(item.weight for item in result_v2.proposed_weights) - 1.0) <= 1e-8


def test_run_optimizer_risk_v2_preserves_benchmark_relative_group_constraints() -> None:
    request = _with_sector_taxonomy(_base_request())
    request.current_portfolio_weights = [
        OptimizerWeight(symbol="AAA", weight=0.65),
        OptimizerWeight(symbol="BBB", weight=0.35),
    ]
    request.penalties = [OptimizerPenalty(penalty_id="l2_distance_to_current", penalty_weight=20.0)]
    request.hard_constraints.turnover.max_turnover = 0.25
    request.hard_constraints.risk.max_active_risk = 0.025
    request.hard_constraints.active_group_exposures = [
        OptimizerActiveGroupConstraint(taxonomy="sector", max_abs_active_exposure=0.02)
    ]
    request.risk_package = _risk_package()

    result = run_optimizer(request)

    assert result.feasibility.status == "feasible"
    assert any(item.constraint_id == "benchmark_relative_max_abs_active_weight" and item.status in {"binding", "pass"} for item in result.constraint_evaluations)
    assert any(item.constraint_id == "active_risk_cap" and item.status in {"binding", "pass"} for item in result.constraint_evaluations)
    technology_group = next(item for item in result.ex_ante_diagnostics.active_group_exposures if item.group_name == "Technology")
    assert abs(technology_group.active_weight) <= 0.020001
    assert max(abs(item.weight) for item in result.active_weights) <= 0.100001


def test_run_optimizer_rejects_risk_cap_request_without_risk_package() -> None:
    request = _base_request()
    request.hard_constraints.risk.max_active_risk = 0.02

    result = run_optimizer(request)

    assert result.feasibility.status == "rejected"
    assert result.feasibility.issues[0].code == "missing_risk_package"


def test_run_optimizer_rejects_invalid_risk_package_inputs() -> None:
    request = _base_request()
    request.hard_constraints.risk.max_active_risk = 0.02
    request.risk_package = _risk_package()
    request.risk_package.diagnostics.status = "invalid"
    request.risk_package.diagnostics.missing_symbols = ["CCC"]

    result = run_optimizer(request)

    assert result.feasibility.status == "rejected"
    assert result.feasibility.issues[0].code == "risk_package_inputs_invalid"
    assert result.feasibility.issues[0].symbols == ["CCC"]


def test_run_optimizer_consumes_alpha_package_as_modest_preference_only() -> None:
    request = _base_request()
    request.alpha_package = _alpha_package()

    result = run_optimizer(request)

    assert result.feasibility.status == "feasible"
    assert result.proposed_weights == [
        OptimizerWeight(symbol="AAA", weight=0.52),
        OptimizerWeight(symbol="BBB", weight=0.29711203),
        OptimizerWeight(symbol="CCC", weight=0.18288797),
    ]
    assert max(abs(item.weight) for item in result.active_weights) <= 0.100001
    assert any(item.constraint_id == "benchmark_relative_max_abs_active_weight" and item.status in {"binding", "pass"} for item in result.constraint_evaluations)
    assert result.run_metadata.alpha_package_id == request.alpha_package.package_id
    assert result.run_metadata.alpha_package_version == "alpha_quality_v1"
    assert result.run_metadata.alpha_package_rebalance_date == "2024-04-15"
    assert result.run_metadata.alpha_package_coverage_ratio == 1.0
    assert result.run_metadata.alpha_preference_l1_budget == 0.04
    assert result.ex_ante_diagnostics.alpha_package_version == "alpha_quality_v1"
    assert result.ex_ante_diagnostics.alpha_package_coverage_ratio == 1.0
    assert result.ex_ante_diagnostics.alpha_preference_applied is True
    assert result.ex_ante_diagnostics.alpha_preference_l1_budget == 0.04
    assert result.replay.alpha_package_id == request.alpha_package.package_id


def test_run_optimizer_allows_invalid_alpha_package_to_degrade_conservatively() -> None:
    request = _base_request()
    request.alpha_package = _alpha_package(rebalance_date="2025-08-01")

    result = run_optimizer(request)

    assert request.alpha_package is not None
    assert request.alpha_package.diagnostics.status == "invalid"
    assert result.feasibility.status == "feasible"
    assert result.run_metadata.alpha_package_version == "alpha_quality_v1"
    assert max(abs(item.weight) for item in result.active_weights) <= 0.100001
    assert result.artifact is not None
    assert result.artifact.artifact_state.artifact_state == "stale"
    assert "alpha_package" in result.artifact.artifact_state.stale_inputs


def test_run_optimizer_consumes_replayable_pit_alpha_package_without_lookahead() -> None:
    request = _base_request()
    request.alpha_package = _pit_alpha_package("2024-04-15")

    result = run_optimizer(request)

    assert request.alpha_package is not None
    assert request.alpha_package.diagnostics.status == "ok"
    assert request.alpha_package.metadata.input_descriptor.contract.contract_id == "alpha_quality_v1_pit_fundamentals_v1"
    assert request.alpha_package.metadata.input_descriptor.input_digest.startswith("pit_")
    assert request.alpha_package.diagnostics.selected_effective_date_by_symbol == {
        "AAA": "2024-03-28",
        "BBB": "2024-03-30",
        "CCC": "2024-03-29",
    }
    assert result.feasibility.status == "feasible"
    assert result.run_metadata.alpha_package_version == "alpha_quality_v1"
    assert result.run_metadata.alpha_package_coverage_ratio == 1.0
    assert result.ex_ante_diagnostics.alpha_preference_applied is True


def test_run_optimizer_pit_alpha_package_historical_as_of_blocks_unavailable_records() -> None:
    request = _base_request()
    request.alpha_package = _pit_alpha_package("2024-03-15")

    result = run_optimizer(request)

    assert request.alpha_package is not None
    assert request.alpha_package.diagnostics.status == "invalid"
    assert request.alpha_package.diagnostics.lag_blocked_symbols == ["CCC"]
    assert request.alpha_package.diagnostics.fallback_symbols == ["CCC"]
    assert result.feasibility.status == "feasible"
    assert result.run_metadata.alpha_package_version == "alpha_quality_v1"
    assert result.artifact is not None
    assert result.artifact.artifact_state.artifact_state == "degraded"
    assert "alpha_package" in result.artifact.artifact_state.degraded_inputs
    assert any(reason.startswith("alpha_package_lag_blocked:") for reason in result.artifact.artifact_state.reasons)


def test_assemble_optimizer_request_with_trusted_pit_alpha_happy_path(tmp_path: Path) -> None:
    from typing import Any, cast

    from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionService, AlphaQualityPitSnapshotStore
    from app.tests.test_optimizer_alpha_fundamentals import _build_client

    request = _live_pit_request()
    client = _build_client(["AAPL", "MSFT", "GOOG"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    ingestion_service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)

    assembled = assemble_optimizer_request_with_trusted_pit_alpha(
        request,
        ingestion_service=ingestion_service,
    )

    assert assembled.alpha_package is not None
    assert assembled.alpha_package.metadata.input_descriptor.source_name == "fmp_pit_ingestion_v1"
    assert assembled.alpha_package.metadata.input_descriptor.pit_provenance is not None
    assert assembled.alpha_package.metadata.input_descriptor.pit_provenance.model_dump() == {
        "trust_status": "trusted",
        "as_of_date": "2024-04-15",
        "decision_date": "2024-04-15",
        "snapshot_digest": assembled.alpha_package.metadata.input_descriptor.input_digest,
        "replay_digest": assembled.alpha_package.metadata.input_descriptor.input_digest,
    }
    assert all(row.selected_snapshot is not None for row in assembled.alpha_package.securities)


def test_assemble_optimizer_request_with_trusted_pit_alpha_blocks_untrusted_snapshot(tmp_path: Path) -> None:
    from typing import Any, cast

    import pytest

    from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionService, AlphaQualityPitSnapshotStore
    from app.tests.test_optimizer_alpha_fundamentals import _build_client

    request = _live_pit_request()
    client = _build_client(["AAPL", "MSFT", "GOOG"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    ingestion_service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)
    ingestion_service.ingest_for_universe(
        as_of_date="2024-04-15",
        decision_date="2024-04-15",
        universe_symbols=["AAPL", "MSFT", "GOOG"],
    )

    normalized_path = tmp_path / "2024-04-15" / "normalized" / "pit_fundamentals.json"
    payload = json.loads(normalized_path.read_text(encoding="utf-8"))
    payload["records"][0]["total_revenue"] = 9999.0
    normalized_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    from app.services.optimizer_alpha_fundamentals import AlphaQualityPitTrustError

    with pytest.raises(AlphaQualityPitTrustError) as exc_info:
        assemble_optimizer_request_with_trusted_pit_alpha(
            request,
            ingestion_service=ingestion_service,
        )

    assert "quarantined" in str(exc_info.value)


def test_assemble_optimizer_request_with_trusted_pit_alpha_fails_closed_on_missing_data(tmp_path: Path) -> None:
    from typing import Any, cast

    import pytest

    from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionService, AlphaQualityPitSnapshotStore
    from app.tests.test_optimizer_alpha_fundamentals import FakeFmpClient, _balance_sheet, _cash_flow, _income_statement, _profile

    request = _live_pit_request()
    client = FakeFmpClient()
    client.profiles["AAPL"] = [_profile("AAPL")]
    client.income_statements["AAPL"] = [_income_statement("AAPL")]
    client.balance_sheets["AAPL"] = [_balance_sheet("AAPL")]
    client.cash_flows["AAPL"] = [_cash_flow("AAPL")]
    client.profiles["MSFT"] = [_profile("MSFT")]
    client.income_statements["MSFT"] = [_income_statement("MSFT")]
    client.balance_sheets["MSFT"] = [_balance_sheet("MSFT")]
    client.cash_flows["MSFT"] = [_cash_flow("MSFT")]

    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    ingestion_service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)

    from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionError

    with pytest.raises(AlphaQualityPitIngestionError) as exc_info:
        assemble_optimizer_request_with_trusted_pit_alpha(
            request,
            ingestion_service=ingestion_service,
        )

    assert "failed closed" in str(exc_info.value)
    assert request.alpha_package is None


def test_assemble_optimizer_request_with_trusted_pit_alpha_is_replay_deterministic(tmp_path: Path) -> None:
    from typing import Any, cast

    from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionService, AlphaQualityPitSnapshotStore
    from app.tests.test_optimizer_alpha_fundamentals import _build_client

    request = _live_pit_request()
    client = _build_client(["AAPL", "MSFT", "GOOG"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    ingestion_service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)

    assembled_one = assemble_optimizer_request_with_trusted_pit_alpha(
        request,
        ingestion_service=ingestion_service,
    )
    assembled_two = assemble_optimizer_request_with_trusted_pit_alpha(
        request.model_copy(deep=True),
        ingestion_service=AlphaQualityPitIngestionService(client=cast(Any, _build_client(["AAPL", "MSFT", "GOOG"])), snapshot_store=snapshot_store),
    )

    assert assembled_one.alpha_package == assembled_two.alpha_package
    assert assembled_one.alpha_package is not None
    assert assembled_two.alpha_package is not None
    assert assembled_one.alpha_package.package_id == assembled_two.alpha_package.package_id
    assert assembled_one.alpha_package.metadata.input_descriptor.input_digest == assembled_two.alpha_package.metadata.input_descriptor.input_digest


def test_run_optimizer_enforces_active_sector_group_constraint_with_diagnostics() -> None:
    request = _with_sector_taxonomy(_base_request())
    request.hard_constraints.active_group_exposures = [
        OptimizerActiveGroupConstraint(taxonomy="sector", max_abs_active_exposure=0.0)
    ]
    request.penalties = [OptimizerPenalty(penalty_id="l2_distance_to_current", penalty_weight=5.0)]
    request.hard_constraints.turnover.max_turnover = 0.2

    result = run_optimizer(request)

    assert result.feasibility.status == "feasible"
    assert result.proposed_weights == [
        OptimizerWeight(symbol="AAA", weight=0.6),
        OptimizerWeight(symbol="BBB", weight=0.3),
        OptimizerWeight(symbol="CCC", weight=0.1),
    ]
    assert any(
        item.constraint_id == "active_group_exposure_sector:Technology" and item.status == "binding"
        for item in result.constraint_evaluations
    )
    assert [item.model_dump() for item in result.ex_ante_diagnostics.active_group_exposures] == [
        {
            "constraint_id": "active_group_exposure_sector:Financials",
            "taxonomy": "sector",
            "group_name": "Financials",
            "portfolio_weight": 0.3,
            "benchmark_weight": 0.3,
            "active_weight": 0.0,
            "max_abs_active_exposure": 0.0,
            "status": "binding",
        },
        {
            "constraint_id": "active_group_exposure_sector:Technology",
            "taxonomy": "sector",
            "group_name": "Technology",
            "portfolio_weight": 0.7,
            "benchmark_weight": 0.7,
            "active_weight": 0.0,
            "max_abs_active_exposure": 0.0,
            "status": "binding",
        },
    ]


def test_run_optimizer_returns_explicit_infeasibility_for_active_sector_constraint() -> None:
    request = _with_sector_taxonomy(_base_request())
    request.hard_constraints.active_group_exposures = [
        OptimizerActiveGroupConstraint(taxonomy="sector", max_abs_active_exposure=0.05)
    ]
    request.universe[2].eligible = False

    result = run_optimizer(request)

    assert result.feasibility.status == "infeasible"
    assert result.proposed_weights == []
    assert result.feasibility.issues[0].code == "symbol_bounds_infeasible"
    assert any(issue.code == "active_group_constraint_infeasible" for issue in result.feasibility.issues)
    assert "active_group_exposure_sector:Technology" in result.feasibility.violated_constraints


def test_run_optimizer_rejects_active_group_taxonomy_without_stable_labels() -> None:
    request = _base_request()
    request.hard_constraints.active_group_exposures = [
        OptimizerActiveGroupConstraint(taxonomy="sector", max_abs_active_exposure=0.05)
    ]

    result = run_optimizer(request)

    assert result.feasibility.status == "rejected"
    assert result.feasibility.issues[0].code == "missing_active_group_taxonomy_labels"
    assert result.feasibility.issues[0].symbols == ["AAA", "BBB", "CCC"]
    assert result.artifact is not None
    assert result.artifact.artifact_state.artifact_state == "rejected"


def test_optimizer_artifact_is_persistable_and_replayable() -> None:
    request = _base_request()
    result = run_optimizer(request)

    assert result.artifact is not None
    store = InMemoryOptimizationArtifactStore()
    artifact_id = store.save(result.artifact)
    loaded = store.load(artifact_id)

    assert loaded == result.artifact
    assert loaded is not None
    replayed = replay_optimization_result_from_artifact(loaded)
    assert replayed == result


def test_optimizer_artifact_acceptance_fixture_is_deterministic() -> None:
    request = _base_request()
    result_one = run_optimizer(request)
    result_two = run_optimizer(request.model_copy(deep=True))

    assert result_one.artifact is not None
    assert result_two.artifact is not None
    payload_one = serialize_optimization_artifact(result_one.artifact)
    payload_two = serialize_optimization_artifact(result_two.artifact)

    assert payload_one == payload_two
    assert deserialize_optimization_artifact(payload_one) == result_one.artifact
    assert json.loads(payload_one) == json.loads(ARTIFACT_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_build_optimizer_preview_returns_hypothetical_artifact_and_replay_handoff() -> None:
    request = _preview_request()

    response = build_optimizer_preview(request)

    assert response.workflow_id == "optimizer_preview_workflow_v1"
    assert response.optimizer_status == "feasible"
    assert response.truth_separation.model_dump() == {
        "current_holdings_truth": "imported_portfolio_snapshot",
        "optimized_output_truth": "hypothetical_optimizer_preview",
        "optimized_output_applied": False,
        "optimized_output_storage": "optimizer_artifact_only",
        "replay_role": "downstream_evaluation_only",
    }
    assert response.provenance.snapshot_reference.account_id == "U1234567"
    assert response.provenance.benchmark_trust_status == "trusted"
    assert response.provenance.return_basis_attestation.benchmark_symbol == "SPY"
    assert response.provenance.return_basis_attestation.section_trust.benchmark_relative_path in {"degraded_unverified_return_basis", "unavailable"}
    assert response.provenance.risk_input_status == "not_requested"
    assert response.provenance.alpha_input_status == "not_requested"
    assert response.persisted_handoff is not None
    assert response.optimizer_artifact.benchmark_id == "benchmark_spy_demo_v1"
    assert response.optimizer_artifact.proposed_weights == [
        OptimizerWeight(symbol="AAA", weight=0.5),
        OptimizerWeight(symbol="BBB", weight=0.3),
        OptimizerWeight(symbol="CCC", weight=0.2),
    ]
    assert response.replay_handoff is not None
    assert response.replay_handoff.status == "hypothetical_not_applied"
    assert response.replay_handoff.applied is False
    assert response.replay_handoff.source_artifact_id == response.optimizer_artifact.artifact_id
    assert response.replay_handoff.source_portfolio_snapshot_id == response.provenance.snapshot_reference.snapshot_id
    assert response.replay_handoff.benchmark_version == "2024-04-15"
    assert response.replay_handoff.benchmark_symbol == "SPY"
    assert response.replay_handoff.handoff_reference == response.persisted_handoff


def test_build_optimizer_preview_fails_closed_for_untrusted_benchmark() -> None:
    request = _preview_request()
    request.benchmark.trust_status = "untrusted"

    import pytest

    with pytest.raises(ValueError) as exc_info:
        build_optimizer_preview(request)

    assert "must be trusted" in str(exc_info.value)


def test_build_optimizer_preview_preserves_missing_risk_failure_without_replay_handoff() -> None:
    request = _preview_request()
    request.hard_constraints.risk.max_active_risk = 0.02

    response = build_optimizer_preview(request)

    assert response.optimizer_status == "rejected"
    assert response.provenance.risk_input_status == "required_but_missing"
    assert response.feasibility.issues[0].code == "missing_risk_package"
    assert response.replay_handoff is None


def test_build_optimizer_preview_attaches_trusted_pit_alpha_when_requested(tmp_path: Path) -> None:
    from typing import Any, cast

    from app.services.optimizer_alpha_fundamentals import AlphaQualityPitIngestionService, AlphaQualityPitSnapshotStore
    from app.tests.test_optimizer_alpha_fundamentals import _build_client

    request = _preview_request()
    request.snapshot.positions = [
        request.snapshot.positions[0].model_copy(update={"symbol": "AAPL", "market_value": 60.0}),
        request.snapshot.positions[1].model_copy(update={"symbol": "MSFT", "market_value": 40.0}),
    ]
    request.benchmark.weights = [
        OptimizerWeight(symbol="AAPL", weight=0.50),
        OptimizerWeight(symbol="MSFT", weight=0.30),
        OptimizerWeight(symbol="GOOG", weight=0.20),
    ]
    request.universe = [
        OptimizerUniverseAsset(symbol="AAPL", eligible=True),
        OptimizerUniverseAsset(symbol="MSFT", eligible=True),
        OptimizerUniverseAsset(symbol="GOOG", eligible=True),
    ]
    request.pit_alpha = OptimizerPreviewPitAlphaInput(as_of_date="2024-04-15")
    client = _build_client(["AAPL", "MSFT", "GOOG"])
    snapshot_store = AlphaQualityPitSnapshotStore(str(tmp_path))
    ingestion_service = AlphaQualityPitIngestionService(client=cast(Any, client), snapshot_store=snapshot_store)

    response = build_optimizer_preview(request, ingestion_service=ingestion_service)

    assert response.optimizer_status == "feasible"
    assert response.provenance.alpha_input_status == "trusted_pit_attached"
    assert response.optimizer_artifact.run_metadata.alpha_package_id is not None


def test_optimizer_preview_persists_immutable_explicit_handoff_reference(tmp_path: Path) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))

    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    loaded = load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)
    assert loaded.artifact == response.optimizer_artifact
    assert loaded.manifest.artifact_id == response.optimizer_artifact.artifact_id
    assert loaded.manifest.source_portfolio_snapshot.snapshot_id == response.provenance.snapshot_reference.snapshot_id
    assert loaded.manifest.benchmark.benchmark_id == "benchmark_spy_demo_v1"
    assert loaded.manifest.benchmark.benchmark_version == "2024-04-15"
    assert loaded.manifest.benchmark.benchmark_symbol == "SPY"
    assert loaded.manifest.return_basis_attestation == response.provenance.return_basis_attestation
    assert loaded.manifest.return_basis_attestation.factor_basis_path == loaded.manifest.return_basis_attestation.section_trust.factor_model_path
    assert loaded.manifest.hypothetical is True
    assert loaded.manifest.preview_only is True
    assert loaded.manifest.replay_consumption_mode == "explicit_reference_only"
    assert loaded.manifest.optimizer_output_target_weights == response.optimizer_artifact.proposed_weights
    assert Path(response.persisted_handoff.manifest_path).exists()
    assert Path(response.persisted_handoff.artifact_path).exists()


def test_optimizer_preview_persists_canonical_benchmark_symbol_at_handoff_boundary(tmp_path: Path) -> None:
    request = _preview_request()
    request.benchmark.benchmark_symbol = " spy "
    handoff_store = OptimizerHandoffStore(str(tmp_path))

    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    assert response.replay_handoff is not None
    assert response.replay_handoff.benchmark_symbol == "SPY"
    loaded = load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)
    assert loaded.manifest.benchmark.benchmark_symbol == "SPY"


@pytest.mark.parametrize("benchmark_symbol", [None, "", "   "])
def test_build_optimizer_preview_blocks_persisted_handoff_without_benchmark_symbol(
    tmp_path: Path,
    benchmark_symbol: str | None,
) -> None:
    request = _preview_request()
    request.benchmark.benchmark_symbol = benchmark_symbol
    handoff_store = OptimizerHandoffStore(str(tmp_path))

    with pytest.raises(OptimizationArtifactPersistenceError) as exc_info:
        build_optimizer_preview(request, handoff_store=handoff_store)

    assert "non-blank benchmark_symbol" in str(exc_info.value)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("benchmark_symbol", [None, "", "   "])
def test_optimizer_handoff_store_blocks_persisted_handoff_without_benchmark_symbol(
    tmp_path: Path,
    benchmark_symbol: str | None,
) -> None:
    request = _base_request()
    result = run_optimizer(request)

    assert result.artifact is not None
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    benchmark = _preview_request().benchmark.model_copy(update={"benchmark_symbol": benchmark_symbol})

    with pytest.raises(OptimizationArtifactPersistenceError) as exc_info:
        handoff_store.persist_handoff(
            artifact=result.artifact,
            snapshot_reference=_snapshot_reference_for_test(),
            benchmark=benchmark,
            return_basis_attestation=_return_basis_attestation_for_test(),
        )

    assert "non-blank" in str(exc_info.value)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("benchmark_symbol", [None, "", "   "])
def test_optimizer_handoff_load_rejects_corrupted_manifest_blank_benchmark_symbol(
    tmp_path: Path,
    benchmark_symbol: str | None,
) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    manifest_path = Path(response.persisted_handoff.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["benchmark"]["benchmark_symbol"] = benchmark_symbol
    manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(OptimizationArtifactPersistenceError) as exc_info:
        load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)

    assert "non-blank benchmark_symbol" in str(exc_info.value)


def test_optimizer_handoff_load_canonicalizes_padded_lowercase_manifest_benchmark_symbol(tmp_path: Path) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    manifest_path = Path(response.persisted_handoff.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["benchmark"]["benchmark_symbol"] = " spy "
    manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    loaded = load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)

    assert loaded.manifest.benchmark.benchmark_symbol == "SPY"


def test_optimizer_handoff_load_backfills_missing_factor_basis_path_from_section_trust(tmp_path: Path) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    manifest_path = Path(response.persisted_handoff.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    del payload["return_basis_attestation"]["factor_basis_path"]
    manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    loaded = load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)

    assert (
        loaded.manifest.return_basis_attestation.factor_basis_path
        == loaded.manifest.return_basis_attestation.section_trust.factor_model_path
    )


def test_optimizer_handoff_load_backfills_null_factor_basis_path_from_section_trust(tmp_path: Path) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    manifest_path = Path(response.persisted_handoff.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["return_basis_attestation"]["factor_basis_path"] = None
    manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    loaded = load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)

    assert (
        loaded.manifest.return_basis_attestation.factor_basis_path
        == loaded.manifest.return_basis_attestation.section_trust.factor_model_path
    )


def test_optimizer_handoff_load_normalizes_legacy_section_trust_to_loaded_factor_basis_path(tmp_path: Path) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    manifest_path = Path(response.persisted_handoff.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["return_basis_attestation"]["factor_basis_path"] = "degraded_unverified_return_basis"
    payload["return_basis_attestation"]["section_trust"]["factor_model_path"] = "verified_adjusted_close"
    payload["return_basis_attestation"]["section_trust"]["risk_contribution_path"] = "verified_adjusted_close"
    manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    raw_loaded = load_raw_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)
    loaded = load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)

    assert raw_loaded.manifest_payload["return_basis_attestation"]["factor_basis_path"] == "degraded_unverified_return_basis"
    assert raw_loaded.manifest_payload["return_basis_attestation"]["section_trust"] == {
        "benchmark_relative_path": "degraded_unverified_return_basis",
        "factor_model_path": "degraded_unverified_return_basis",
        "risk_contribution_path": "degraded_unverified_return_basis",
    }
    assert loaded.manifest.return_basis_attestation.factor_basis_path == "degraded_unverified_return_basis"
    assert loaded.manifest.return_basis_attestation.section_trust.model_dump() == {
        "benchmark_relative_path": "degraded_unverified_return_basis",
        "factor_model_path": "degraded_unverified_return_basis",
        "risk_contribution_path": "degraded_unverified_return_basis",
    }


def test_optimizer_handoff_store_rejects_incomplete_artifact_metadata(tmp_path: Path) -> None:
    request = _base_request()
    result = run_optimizer(request)

    assert result.artifact is not None
    invalid_artifact = result.artifact.model_copy(update={"input_fingerprints": result.artifact.input_fingerprints[:-1]})
    handoff_store = OptimizerHandoffStore(str(tmp_path))

    import pytest

    with pytest.raises(OptimizationArtifactPersistenceError) as exc_info:
        handoff_store.persist_handoff(
            artifact=invalid_artifact,
            snapshot_reference=_snapshot_reference_for_test(),
            benchmark=_preview_request().benchmark,
            return_basis_attestation=_return_basis_attestation_for_test(),
        )

    assert "missing required input provenance" in str(exc_info.value)


def test_optimizer_handoff_load_rejects_mismatched_return_basis_attestation_benchmark_symbol(tmp_path: Path) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    manifest_path = Path(response.persisted_handoff.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["return_basis_attestation"]["benchmark_symbol"] = "QQQ"
    manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(OptimizationArtifactPersistenceError) as exc_info:
        load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)

    assert "return_basis_attestation benchmark_symbol does not match manifest benchmark" in str(exc_info.value)


def test_optimizer_handoff_load_rejects_missing_return_basis_attestation_window(tmp_path: Path) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    manifest_path = Path(response.persisted_handoff.manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["return_basis_attestation"]["history_start_date"] = ""
    manifest_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")

    with pytest.raises(OptimizationArtifactPersistenceError) as exc_info:
        load_optimizer_handoff_by_reference(response.persisted_handoff, store=handoff_store)

    assert "requires persisted return_basis_attestation history window metadata" in str(exc_info.value)


def test_optimizer_handoff_store_rejects_ambiguous_manifest_reference(tmp_path: Path) -> None:
    request = _preview_request()
    handoff_store = OptimizerHandoffStore(str(tmp_path))
    response = build_optimizer_preview(request, handoff_store=handoff_store)

    assert response.persisted_handoff is not None
    bad_reference = response.persisted_handoff.model_copy(update={"handoff_id": "optimizer_handoff_wrong"})

    import pytest

    with pytest.raises(OptimizationArtifactPersistenceError) as exc_info:
        load_optimizer_handoff_by_reference(bad_reference, store=handoff_store)

    assert "manifest_path is not the canonical persisted path" in str(exc_info.value)


def _snapshot_reference_for_test():
    return OptimizerPreviewSnapshotReference(
        snapshot_id="portfolio_snapshot_test",
        account_id="U1234567",
        importer="interactive_brokers",
        imported_at="2024-04-15T09:30:00+00:00",
        statement_period="2024-04",
        source_files=["IB2024.pdf"],
    )


def _return_basis_attestation_for_test() -> OptimizerReturnBasisAttestation:
    unavailable = ReturnBasisEvidence(
        verification_status="unavailable",
        economic_basis="unavailable",
        construction_method="unknown",
        disqualifiers=["missing_history_rows"],
    )
    return OptimizerReturnBasisAttestation(
        benchmark_symbol="SPY",
        as_of_date="2024-04-15",
        history_start_date="2024-04-15",
        history_end_date="2024-04-15",
        factor_proxy_symbols=[],
        benchmark_return_basis_contract="unavailable",
        factor_return_basis_contract="unavailable",
        factor_basis_path="unavailable",
        section_trust=OptimizerReturnBasisSectionTrust(
            benchmark_relative_path="unavailable",
            factor_model_path="unavailable",
            risk_contribution_path="unavailable",
        ),
        evidence=OptimizerReturnBasisEvidenceBundle(
            benchmark_history=unavailable,
            factor_history=unavailable,
        ),
    )
