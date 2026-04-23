from pathlib import Path

from app.schemas.optimizer import (
    OptimizationIssue,
    OptimizerAlphaFundamentalSnapshot,
    OptimizerAlphaPitFundamentalRecord,
    OptimizerAlphaPitFundamentalsInput,
    OptimizerAlphaPitTrustReport,
)
from app.services.optimizer_alpha_fundamentals import load_alpha_pit_fundamentals_snapshot
from app.services.optimizer_alpha_service import (
    build_alpha_preference_vector,
    build_alpha_quality_package,
    build_alpha_quality_package_from_pit_input,
    validate_optimizer_alpha_package,
)


FIXTURE_PATH = Path(__file__).with_name("alpha_quality_v1_pit_fixture.json")


def _fundamental_snapshots() -> list[OptimizerAlphaFundamentalSnapshot]:
    return [
        OptimizerAlphaFundamentalSnapshot(
            source_dataset="legacy_fixture",
            source_record_id="aaa_2023fy",
            symbol="AAA",
            issuer_id="AAA",
            statement_date="2023-12-31",
            period_type="annual",
            availability_semantics="derived_reporting_lag",
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
            source_dataset="legacy_fixture",
            source_record_id="bbb_2023fy",
            symbol="BBB",
            issuer_id="BBB",
            statement_date="2023-12-31",
            period_type="annual",
            availability_semantics="derived_reporting_lag",
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
            source_dataset="legacy_fixture",
            source_record_id="ccc_2023fy",
            symbol="CCC",
            issuer_id="CCC",
            statement_date="2023-12-31",
            period_type="annual",
            availability_semantics="derived_reporting_lag",
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
    ]


def _pit_fixture() -> OptimizerAlphaPitFundamentalsInput:
    return load_alpha_pit_fundamentals_snapshot(FIXTURE_PATH)


def test_build_alpha_quality_package_is_deterministic() -> None:
    package_one = build_alpha_quality_package(
        rebalance_date="2024-04-15",
        universe_symbols=["CCC", "AAA", "BBB"],
        fundamental_snapshots=_fundamental_snapshots(),
        replay_id="legacy-determinism",
    )
    package_two = build_alpha_quality_package(
        rebalance_date="2024-04-15",
        universe_symbols=["BBB", "CCC", "AAA"],
        fundamental_snapshots=list(reversed(_fundamental_snapshots())),
        replay_id="legacy-determinism",
    )

    assert package_one == package_two
    assert package_one.package_id == package_two.package_id
    assert package_one.version == "alpha_quality_v1"
    assert package_one.ordered_symbols == ["AAA", "BBB", "CCC"]
    assert package_one.diagnostics.status == "ok"
    assert package_one.metadata.point_in_time_only is True
    assert package_one.metadata.fallback_behavior == "conservative_negative"
    assert package_one.metadata.input_descriptor.contract.contract_id == "alpha_quality_v1_pit_fundamentals_v1"


def test_build_alpha_quality_package_enforces_reporting_lag() -> None:
    package = build_alpha_quality_package(
        rebalance_date="2024-02-15",
        universe_symbols=["AAA"],
        fundamental_snapshots=[
            OptimizerAlphaFundamentalSnapshot(
                source_dataset="legacy_fixture",
                source_record_id="aaa_2024q1",
                symbol="AAA",
                issuer_id="AAA",
                statement_date="2024-01-31",
                period_type="quarterly",
                availability_semantics="derived_reporting_lag",
                total_revenue=100.0,
                cost_of_revenue=40.0,
                ebit=20.0,
                total_assets=100.0,
                operating_cash_flow=18.0,
                free_cash_flow=15.0,
                net_income=16.0,
                total_debt=20.0,
                cash_and_equivalents=5.0,
            )
        ],
    )

    assert package.diagnostics.status == "invalid"
    assert package.diagnostics.lag_blocked_symbols == ["AAA"]
    row = package.securities[0]
    assert row.selected_snapshot is None
    assert row.coverage_flags.lag_blocked is True
    assert row.coverage_flags.used_conservative_fallback is True
    assert all(item.normalized_score == -1.0 for item in row.sub_signals)


def test_build_alpha_quality_package_handles_missing_and_stale_data_conservatively() -> None:
    package = build_alpha_quality_package(
        rebalance_date="2025-08-01",
        universe_symbols=["AAA", "BBB"],
        fundamental_snapshots=[
            OptimizerAlphaFundamentalSnapshot(
                source_dataset="legacy_fixture",
                source_record_id="aaa_2023fy",
                symbol="AAA",
                issuer_id="AAA",
                statement_date="2023-12-31",
                period_type="annual",
                availability_semantics="derived_reporting_lag",
                total_revenue=1000.0,
                cost_of_revenue=400.0,
                total_assets=800.0,
                operating_cash_flow=180.0,
                net_income=150.0,
                total_debt=160.0,
                cash_and_equivalents=60.0,
            )
        ],
    )

    assert package.diagnostics.status == "invalid"
    assert package.diagnostics.missing_snapshot_symbols == ["BBB"]
    assert package.diagnostics.stale_symbols == ["AAA"]
    assert package.diagnostics.fallback_symbols == ["AAA", "BBB"]
    aaa_row = next(item for item in package.securities if item.symbol == "AAA")
    bbb_row = next(item for item in package.securities if item.symbol == "BBB")
    assert aaa_row.coverage_flags.stale_snapshot is True
    assert bbb_row.coverage_flags.missing_snapshot is True
    assert all(item.fallback_applied for item in aaa_row.sub_signals)
    assert all(item.fallback_applied for item in bbb_row.sub_signals)


def test_build_alpha_quality_package_exposes_stable_audit_shape() -> None:
    package = build_alpha_quality_package(
        rebalance_date="2024-04-15",
        universe_symbols=["AAA", "BBB", "CCC"],
        fundamental_snapshots=_fundamental_snapshots(),
        replay_id="stable-audit-shape",
    )

    assert package.metadata.component_weights == {
        "profitability": 0.35,
        "cash_generation": 0.3,
        "accrual_quality": 0.2,
        "leverage_discipline": 0.15,
    }
    row = package.securities[0]
    assert row.model_dump().keys() == {"symbol", "selected_snapshot", "effective_date", "coverage_flags", "sub_signals", "final_score"}
    assert [item.component_id for item in row.sub_signals] == [
        "profitability",
        "cash_generation",
        "accrual_quality",
        "leverage_discipline",
    ]
    assert package.diagnostics.selected_effective_date_by_symbol == {
        "AAA": "2024-03-30",
        "BBB": "2024-03-30",
        "CCC": "2024-03-30",
    }
    assert package.metadata.input_descriptor.input_record_count == 3
    assert package.metadata.input_descriptor.replay_id == "stable-audit-shape"


def test_build_alpha_preference_vector_is_zero_sum_and_modest() -> None:
    package = build_alpha_quality_package(
        rebalance_date="2024-04-15",
        universe_symbols=["AAA", "BBB", "CCC"],
        fundamental_snapshots=_fundamental_snapshots(),
    )

    vector, budget = build_alpha_preference_vector(
        ordered_symbols=package.ordered_symbols,
        benchmark_weights=[0.5, 0.3, 0.2],
        eligible_mask=[True, True, True],
        alpha_package=package,
        benchmark_active_limit=0.10,
    )

    assert budget == 0.04
    assert abs(sum(vector)) <= 1e-12
    assert round(sum(abs(value) for value in vector), 8) == 0.04
    assert vector[0] > 0.0
    assert vector[2] < 0.0


def test_build_alpha_quality_package_from_pit_input_is_replayable_and_deterministic() -> None:
    pit_input = _pit_fixture()

    package_one = build_alpha_quality_package_from_pit_input(
        rebalance_date="2024-04-15",
        pit_input=pit_input,
    )
    package_two = build_alpha_quality_package_from_pit_input(
        rebalance_date="2024-04-15",
        pit_input=OptimizerAlphaPitFundamentalsInput.model_validate(
            pit_input.model_dump(mode="json") | {"records": list(reversed(pit_input.records)), "universe_symbols": list(reversed(pit_input.universe_symbols))}
        ),
    )

    assert package_one == package_two
    assert package_one.package_id == package_two.package_id
    assert package_one.metadata.input_descriptor.source_name == "test_replay_snapshot"
    assert package_one.metadata.input_descriptor.replay_id == "alpha-quality-v1-2024-04-15-core3"
    assert package_one.metadata.input_descriptor.input_record_count == 5
    assert package_one.metadata.input_descriptor.input_digest.startswith("pit_")
    assert package_one.diagnostics.selected_effective_date_by_symbol == {
        "AAA": "2024-03-28",
        "BBB": "2024-03-30",
        "CCC": "2024-03-29",
    }
    assert package_one.diagnostics.coverage_ratio == 1.0
    assert package_one.diagnostics.complete_coverage_ratio == 1.0
    assert package_one.diagnostics.status == "ok"
    assert package_one.metadata.input_descriptor.pit_provenance is None


def test_build_alpha_quality_package_from_pit_input_preserves_trusted_pit_lineage() -> None:
    pit_input = _pit_fixture()
    baseline_package = build_alpha_quality_package_from_pit_input(
        rebalance_date="2024-04-15",
        pit_input=pit_input,
    )
    package = build_alpha_quality_package_from_pit_input(
        rebalance_date="2024-04-15",
        pit_input=pit_input,
        trust_report=OptimizerAlphaPitTrustReport(
            status="trusted",
            as_of_date="2024-04-15",
            decision_date="2024-04-15",
            source_name=pit_input.source_name,
            replay_id=pit_input.replay_id,
            requested_universe_symbols=["AAA", "BBB", "CCC"],
            snapshot_universe_symbols=["AAA", "BBB", "CCC"],
            raw_snapshot_symbols=["AAA", "BBB", "CCC"],
            normalized_record_count=5,
            raw_bundle_count=3,
            lineage_valid=True,
            replay_valid=True,
            approved_universe_valid=True,
            persisted_input_digest=baseline_package.metadata.input_descriptor.input_digest,
            replay_input_digest=baseline_package.metadata.input_descriptor.input_digest,
            issues=[],
        ),
    )

    assert package.metadata.input_descriptor.pit_provenance is not None
    assert package.metadata.input_descriptor.pit_provenance.model_dump() == {
        "trust_status": "trusted",
        "as_of_date": "2024-04-15",
        "decision_date": "2024-04-15",
        "snapshot_digest": package.metadata.input_descriptor.input_digest,
        "replay_digest": package.metadata.input_descriptor.input_digest,
    }


def test_build_alpha_quality_package_from_pit_input_respects_as_of_boundary_without_latest_fallback() -> None:
    pit_input = _pit_fixture()
    package = build_alpha_quality_package_from_pit_input(
        rebalance_date="2024-03-15",
        pit_input=pit_input.model_copy(update={"decision_date": "2024-03-15", "as_of_date": "2024-03-15"}),
    )

    aaa_row = next(item for item in package.securities if item.symbol == "AAA")
    bbb_row = next(item for item in package.securities if item.symbol == "BBB")
    ccc_row = next(item for item in package.securities if item.symbol == "CCC")

    assert aaa_row.selected_snapshot is not None
    assert aaa_row.selected_snapshot.source_record_id == "aaa_2023q3_pub"
    assert bbb_row.selected_snapshot is not None
    assert bbb_row.selected_snapshot.source_record_id == "bbb_2023q3_file"
    assert ccc_row.selected_snapshot is None
    assert package.diagnostics.lag_blocked_symbols == ["CCC"]
    assert package.diagnostics.missing_snapshot_symbols == ["CCC"]
    assert package.diagnostics.fallback_symbols == ["CCC"]
    assert package.diagnostics.status == "invalid"


def test_build_alpha_quality_package_from_pit_input_marks_component_missingness_without_imputation() -> None:
    pit_input = OptimizerAlphaPitFundamentalsInput(
        decision_date="2024-04-15",
        as_of_date="2024-04-15",
        source_name="component_missingness_fixture",
        replay_id="component-missingness",
        universe_symbols=["AAA", "BBB", "CCC"],
        records=[
            OptimizerAlphaPitFundamentalRecord(
                source_dataset="fixture_vendor",
                source_record_id="aaa",
                symbol="AAA",
                issuer_id="AAA",
                statement_date="2023-12-31",
                period_type="annual",
                availability_semantics="publication_date",
                publication_date="2024-03-20",
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
            OptimizerAlphaPitFundamentalRecord(
                source_dataset="fixture_vendor",
                source_record_id="bbb",
                symbol="BBB",
                issuer_id="BBB",
                statement_date="2023-12-31",
                period_type="annual",
                availability_semantics="publication_date",
                publication_date="2024-03-20",
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
            OptimizerAlphaPitFundamentalRecord(
                source_dataset="fixture_vendor",
                source_record_id="ccc_missing_cfo",
                symbol="CCC",
                issuer_id="CCC",
                statement_date="2023-12-31",
                period_type="annual",
                availability_semantics="publication_date",
                publication_date="2024-03-20",
                total_revenue=700.0,
                cost_of_revenue=420.0,
                ebit=90.0,
                total_assets=850.0,
                free_cash_flow=40.0,
                net_income=115.0,
                total_debt=320.0,
                cash_and_equivalents=20.0,
            ),
        ],
    )

    package = build_alpha_quality_package_from_pit_input(
        rebalance_date="2024-04-15",
        pit_input=pit_input,
    )

    ccc_row = next(item for item in package.securities if item.symbol == "CCC")
    cash_generation = next(item for item in ccc_row.sub_signals if item.component_id == "cash_generation")
    accrual_quality = next(item for item in ccc_row.sub_signals if item.component_id == "accrual_quality")

    assert cash_generation.available is True
    assert cash_generation.measure_id == "fcf_to_assets"
    assert accrual_quality.available is False
    assert accrual_quality.fallback_applied is True
    assert accrual_quality.missing_fields == ["net_income", "operating_cash_flow"] or accrual_quality.missing_fields == ["operating_cash_flow"]
    assert ccc_row.coverage_flags.used_conservative_fallback is True
    assert package.diagnostics.fallback_symbols == ["CCC"]
    assert package.diagnostics.complete_coverage_ratio == 0.66666667


def test_build_alpha_quality_package_from_pit_input_preserves_duplicate_restatement_records_for_gate_rejection() -> None:
    pit_input = OptimizerAlphaPitFundamentalsInput.model_validate(
        _pit_fixture().model_dump(mode="json")
        | {
            "records": _pit_fixture().model_dump(mode="json")["records"]
            + [
                _pit_fixture().model_dump(mode="json")["records"][1]
                | {
                    "source_record_id": "aaa_2023fy_avail_restated",
                    "total_revenue": 1001.0,
                }
            ]
        }
    )

    package = build_alpha_quality_package_from_pit_input(
        rebalance_date="2024-04-15",
        pit_input=pit_input,
    )

    aaa_row = next(item for item in package.securities if item.symbol == "AAA")
    assert aaa_row.selected_snapshot is not None
    assert aaa_row.selected_snapshot.source_record_id == "aaa_2023fy_avail_restated"
    assert package.metadata.input_descriptor.input_record_count == 6


def test_validate_optimizer_alpha_package_rejects_as_of_after_rebalance() -> None:
    package = build_alpha_quality_package(
        rebalance_date="2024-04-15",
        universe_symbols=["AAA", "BBB", "CCC"],
        fundamental_snapshots=_fundamental_snapshots(),
    )
    broken_package = package.model_copy(
        update={
            "metadata": package.metadata.model_copy(
                update={
                    "input_descriptor": package.metadata.input_descriptor.model_copy(update={"as_of_date": "2024-04-16"})
                }
            )
        }
    )

    issues = validate_optimizer_alpha_package(broken_package, expected_symbols=["AAA", "BBB", "CCC"])

    assert issues == [
        OptimizationIssue(
            code="alpha_package_as_of_after_rebalance",
            message="Alpha package as_of_date cannot be later than the rebalance date used for the optimizer decision.",
            actual_value="2024-04-16",
            required_value="2024-04-15",
        )
    ]
