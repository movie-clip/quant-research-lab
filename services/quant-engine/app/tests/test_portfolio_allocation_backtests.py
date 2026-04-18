from datetime import datetime

from types import SimpleNamespace
from typing import Literal, cast

from app.schemas.backtest_engine import AllocationBacktestAssumptions, AllocationBacktestMetrics, AllocationBacktestPoint, AllocationBacktestResult, AllocationBacktestWeight, CandidateConstructionRuleInput, ConstructedCandidateReplayInput, DraftPortfolioImportedMetaInput, DraftPortfolioSnapshotInput, DraftPortfolioPositionInput, HypotheticalReplacementReplayRequest, PortfolioDiagnosticsComparisonRow, PortfolioDiagnosticsProvenance, PortfolioDiagnosticsSnapshot, PortfolioDiagnosticsTopCallout, PortfolioWeightInput, ReplacementIntentReplayInput, SingleReplacementCandidateConstructionRequest, SingleReplacementConstraintValidationState, SingleReplacementConstructionConstraintSetInput, SingleReplacementConstructionConstraintValidationRequest, SingleReplacementConstructionConstraintValidationResponse
from app.schemas.reconciliation import FactorRiskContributionItem, RiskConcentrationSnapshot, RiskContributionBreakdownPayload, SnapshotItem, StressScenarioResult, VolatilitySnapshot
from app.services.portfolio_backtest_engine import _build_backtest_diagnostics_inputs, _build_candidate_weights_from_replacement_intent, _build_diagnostics_comparison, _build_snapshot_baseline_weights, _build_synthetic_snapshot_from_weights, build_hypothetical_replacement_replay_preview
from app.services.candidate_constraints import CONSTRAINT_SET_ID, validate_single_replacement_candidate_construction_constraints
from app.services.candidate_construction import RULE_ID_FIXED_SPLIT, build_single_replacement_candidate_construction
from fastapi.testclient import TestClient

from app.api.main import app


def _history(*prices: float) -> list[dict]:
    dates = ["2024-01-02", "2024-01-31", "2024-02-01", "2024-06-03", "2024-12-31"]
    return [{"date": date, "price": price} for date, price in zip(dates[: len(prices)], prices, strict=False)]


def _draft_snapshot(*positions: tuple[str, float]) -> DraftPortfolioSnapshotInput:
    return DraftPortfolioSnapshotInput(
        base_currency="USD",
        imported_meta=DraftPortfolioImportedMetaInput(
            importer="interactive_brokers",
            statement_period="2025-01-01 - 2025-12-31",
            imported_at=datetime(2026, 4, 10),
            source_file_names=["IB2025.pdf"],
        ),
        positions=[
            DraftPortfolioPositionInput(symbol=symbol, market_value=market_value, quantity=1.0, currency="USD", source_type="etf")
            for symbol, market_value in positions
        ],
        cash_balances=[],
    )


def _replacement_intent(base_symbol: str = "VUAA", candidate_symbol: str = "IUFS") -> ReplacementIntentReplayInput:
    return ReplacementIntentReplayInput(
        kind="etf_replacement_intent",
        source="candidate_seed",
        created_at=datetime(2026, 4, 15, 0, 5, 0),
        draft_id="draft-1",
        workspace_id="workspace-1",
        base_node_id="node-1",
        base_symbol=base_symbol,
        candidate_symbol=candidate_symbol,
        seeded_from_draft_id="draft-1",
        seed_ranking_id="etf_ranking_engine_v1",
        seed_methodology_id="etf_ranking_methodology_v1",
        seed_ranking_basis_date="2026-04-15",
        peer_group="Sector UCITS ETF",
        benchmark_symbol="SPY",
        lookback_months=6,
        confidence="medium",
        holdings_support="mixed",
        warning_count=1,
    )


def _constructed_candidate_and_constraint_validation() -> tuple[ConstructedCandidateReplayInput, SingleReplacementConstructionConstraintValidationResponse]:
    constructed_candidate = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID_FIXED_SPLIT),
        )
    )
    constructed_candidate_input = ConstructedCandidateReplayInput.model_validate(constructed_candidate.model_dump(mode="json"))
    constraint_validation = validate_single_replacement_candidate_construction_constraints(
        SingleReplacementConstructionConstraintValidationRequest(
            constructed_candidate=constructed_candidate_input,
            constraint_set=SingleReplacementConstructionConstraintSetInput(constraint_set_id=CONSTRAINT_SET_ID),
        )
    )
    return constructed_candidate_input, constraint_validation


def _clone_constraint_validation(
    constraint_validation: SingleReplacementConstructionConstraintValidationResponse,
) -> SingleReplacementConstructionConstraintValidationResponse:
    return SingleReplacementConstructionConstraintValidationResponse.model_validate(constraint_validation.model_dump(mode="json"))


def test_build_synthetic_snapshot_from_weights_returns_explicit_imported_snapshot() -> None:
    result = AllocationBacktestResult(
        portfolio_name="Candidate",
        benchmark_symbol="SPY",
        start_date="2024-01-01",
        end_date="2024-12-31",
        observation_count=3,
        rebalance_frequency="monthly",
        commission_bps=0,
        slippage_bps=0,
        assumptions=AllocationBacktestAssumptions(
            price_basis="adjusted_close",
            execution_price_field="close",
            execution_lag_days=1,
            calendar_policy="intersection_common_dates",
            fractional_shares=True,
            long_only=True,
            leverage_allowed=False,
            tax_treatment="pre_tax",
            investor_base_currency="USD",
        ),
        status="ok",
        instrument_metadata=[],
        starting_weights=[AllocationBacktestWeight(symbol="SPY", target_weight=1.0)],
        ending_weights=[AllocationBacktestWeight(symbol="SPY", target_weight=1.0)],
        metrics=AllocationBacktestMetrics(),
        equity_curve=[AllocationBacktestPoint(date="2024-01-01", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=110000, cash=0)],
        rebalance_events=[],
        trades=[],
    )

    snapshot = _build_synthetic_snapshot_from_weights("Candidate", [PortfolioWeightInput(symbol="SPY", target_weight=1.0)], result)

    assert snapshot.statement.detected_format == "synthetic_backtest"
    assert snapshot.statement.importer == "multi_broker"
    assert snapshot.statement.source_path == "candidate-backtest"
    assert snapshot.statement.statement_period == "2024-01-01 - 2024-12-31"
    assert snapshot.positions[0].symbol == "SPY"
    assert snapshot.positions[0].market_value == 110000


def test_build_backtest_diagnostics_inputs_separates_replay_and_historical_inputs() -> None:
    result = AllocationBacktestResult(
        portfolio_name="Candidate",
        benchmark_symbol="SPY",
        start_date="2024-01-01",
        end_date="2024-12-31",
        observation_count=2,
        rebalance_frequency="monthly",
        commission_bps=0,
        slippage_bps=0,
        assumptions=AllocationBacktestAssumptions(
            price_basis="adjusted_close",
            execution_price_field="close",
            execution_lag_days=1,
            calendar_policy="intersection_common_dates",
            fractional_shares=True,
            long_only=True,
            leverage_allowed=False,
            tax_treatment="pre_tax",
            investor_base_currency="USD",
        ),
        status="ok",
        instrument_metadata=[],
        starting_weights=[AllocationBacktestWeight(symbol="SPY", target_weight=1.0)],
        ending_weights=[AllocationBacktestWeight(symbol="SPY", target_weight=1.0)],
        metrics=AllocationBacktestMetrics(),
        equity_curve=[AllocationBacktestPoint(date="2024-01-31", equity=100000, cash=0), AllocationBacktestPoint(date="2024-12-31", equity=110000, cash=0)],
        rebalance_events=[],
        trades=[],
    )
    histories = {
        "SPY": _history(100.0, 102.0, 108.0),
        "QQQ": _history(100.0, 104.0, 112.0),
        "IWD": _history(100.0, 101.0, 104.0),
        "IWM": _history(100.0, 99.0, 102.0),
        "XLF": _history(100.0, 103.0, 107.0),
        "XLV": _history(100.0, 101.0, 103.0),
        "XLE": _history(100.0, 97.0, 101.0),
        "XLI": _history(100.0, 102.0, 105.0),
        "IEF": _history(100.0, 100.4, 101.2),
        "TLT": _history(100.0, 99.5, 104.0),
        "LQD": _history(100.0, 100.8, 102.3),
        "GLD": _history(100.0, 101.0, 104.1),
    }

    diagnostics_inputs = _build_backtest_diagnostics_inputs(
        portfolio_name="Candidate",
        weights=[PortfolioWeightInput(symbol="SPY", target_weight=1.0)],
        result=result,
        benchmark_rows=histories["SPY"],
        histories=histories,
    )

    assert diagnostics_inputs.synthetic_snapshot.statement.detected_format == "synthetic_backtest"
    assert diagnostics_inputs.replay_daily_states[-1].total_portfolio_value == 110000
    assert diagnostics_inputs.benchmark_price_history[-1]["date"] == "2024-02-01"
    assert "QQQ" in diagnostics_inputs.factor_price_histories


def test_build_snapshot_baseline_weights_uses_draft_snapshot_market_values_without_extra_normalization() -> None:
    weights = _build_snapshot_baseline_weights(_draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)))

    assert weights == [
        PortfolioWeightInput(symbol="VUAA", target_weight=0.6),
        PortfolioWeightInput(symbol="IB01", target_weight=0.4),
    ]


def test_build_candidate_weights_from_replacement_intent_performs_exact_one_for_one_substitution() -> None:
    baseline = [
        PortfolioWeightInput(symbol="VUAA", target_weight=0.6),
        PortfolioWeightInput(symbol="IB01", target_weight=0.4),
    ]

    candidate = _build_candidate_weights_from_replacement_intent(baseline, "VUAA", "IUFS")

    assert candidate == [
        PortfolioWeightInput(symbol="IB01", target_weight=0.4),
        PortfolioWeightInput(symbol="IUFS", target_weight=0.6),
    ]
    assert sum(item.target_weight for item in candidate) == 1.0


def test_build_diagnostics_comparison_adds_explicit_top_callouts() -> None:
    baseline = PortfolioDiagnosticsSnapshot(
        provenance=PortfolioDiagnosticsProvenance(snapshot_basis="synthetic_replay_snapshot", historical_basis="market_data_history", note="n"),
        factor_snapshot=[SnapshotItem(key="market", label="Market", category="market", us_proxy="SPY", latest_loading=1.0, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="broad market"), SnapshotItem(key="value", label="Value", category="style", us_proxy="IWD", latest_loading=0.1, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="value")],
        volatility_snapshot=VolatilitySnapshot(realized_vol_252d=10.0, downside_vol_252d=6.0, tracking_error_252d=3.0, max_drawdown_pct=-4.0),
        risk_contribution=RiskContributionBreakdownPayload(methodology="m", window_days=60, observation_count=60, status="ok", factor_contributions=[FactorRiskContributionItem(key="market", label="Market", us_proxy="SPY", loading=1.0, factor_volatility=12.0, variance_contribution=0.01, risk_share=0.6)], factor_total_variance=0.01, specific_variance=0.005, total_variance=0.015, factor_risk_share_total=0.66, specific_risk_share=0.34, residual_volatility=5.0, position_contributions=[], concentration=RiskConcentrationSnapshot(top_1_factor_risk_share=0.6, top_3_factor_risk_share=0.6, top_1_position_risk_share=1.0, top_5_position_risk_share=1.0, factor_hhi=0.36, position_hhi=1.0)),
        stress_scenarios=[StressScenarioResult(name="Broad Market Selloff", estimated_return_pct=-8.5, description="x"), StressScenarioResult(name="Rates Shock", estimated_return_pct=-2.0, description="x")],
    )
    candidate = PortfolioDiagnosticsSnapshot(
        provenance=PortfolioDiagnosticsProvenance(snapshot_basis="synthetic_replay_snapshot", historical_basis="market_data_history", note="n"),
        factor_snapshot=[SnapshotItem(key="market", label="Market", category="market", us_proxy="SPY", latest_loading=0.8, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="broad market"), SnapshotItem(key="value", label="Value", category="style", us_proxy="IWD", latest_loading=0.4, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="value")],
        volatility_snapshot=VolatilitySnapshot(realized_vol_252d=9.0, downside_vol_252d=5.0, tracking_error_252d=4.0, max_drawdown_pct=-2.5),
        risk_contribution=RiskContributionBreakdownPayload(methodology="m", window_days=60, observation_count=60, status="ok", factor_contributions=[FactorRiskContributionItem(key="market", label="Market", us_proxy="SPY", loading=0.8, factor_volatility=11.0, variance_contribution=0.008, risk_share=0.3), FactorRiskContributionItem(key="value", label="Value", us_proxy="IWD", loading=0.4, factor_volatility=9.0, variance_contribution=0.007, risk_share=0.55)], factor_total_variance=0.015, specific_variance=0.004, total_variance=0.019, factor_risk_share_total=0.8, specific_risk_share=0.2, residual_volatility=4.5, position_contributions=[], concentration=RiskConcentrationSnapshot(top_1_factor_risk_share=0.55, top_3_factor_risk_share=0.55, top_1_position_risk_share=0.7, top_5_position_risk_share=1.0, factor_hhi=0.2, position_hhi=0.58)),
        stress_scenarios=[StressScenarioResult(name="Broad Market Selloff", estimated_return_pct=-6.0, description="x"), StressScenarioResult(name="Rates Shock", estimated_return_pct=-5.5, description="x")],
    )

    comparison = _build_diagnostics_comparison(baseline, candidate)

    assert comparison.top_factor_exposure_change is not None
    assert comparison.top_factor_exposure_change == PortfolioDiagnosticsTopCallout(key="value", label="Value", baseline_value=0.1, candidate_value=0.4, delta_value=0.3, selection_rule="largest_absolute_delta", rationale="Largest valid factor exposure delta in this group (candidate - baseline).")
    assert comparison.top_volatility_change is not None
    assert comparison.top_volatility_change.key == "max_drawdown"
    assert comparison.top_volatility_change.selection_rule == "fixed_priority"
    assert comparison.top_risk_contribution_change is not None
    assert comparison.top_risk_contribution_change.key == "market"
    assert comparison.top_concentration_change is not None
    assert comparison.top_concentration_change.key == "factor_hhi"
    assert comparison.top_stress_scenario_change is not None
    assert comparison.top_stress_scenario_change.key == "rates_shock"


def test_build_diagnostics_comparison_returns_null_top_callouts_when_groups_have_no_eligible_rows() -> None:
    empty = PortfolioDiagnosticsSnapshot(
        provenance=PortfolioDiagnosticsProvenance(snapshot_basis="synthetic_replay_snapshot", historical_basis="market_data_history", note="n"),
        factor_snapshot=[SnapshotItem(key="market", label="Market", category="market", us_proxy="SPY", latest_loading=None, target_exposure=None, primary_mapping=None, alternative_mappings=[], ucits_examples=[], mapping_quality="high", description="broad market")],
        volatility_snapshot=VolatilitySnapshot(realized_vol_252d=None, downside_vol_252d=None, tracking_error_252d=None, max_drawdown_pct=None),
        risk_contribution=None,
        stress_scenarios=[],
    )

    comparison = _build_diagnostics_comparison(empty, empty)

    assert comparison.top_factor_exposure_change is None
    assert comparison.top_volatility_change is None
    assert comparison.top_risk_contribution_change is None
    assert comparison.top_concentration_change is None
    assert comparison.top_stress_scenario_change is None


def test_portfolio_allocation_backtest_route_returns_reference_assumptions_and_metadata(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "VUAA", "target_weight": 0.6}, {"symbol": "TLT", "target_weight": 0.4}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "commission_bps": 2,
            "slippage_bps": 3,
            "price_basis": "adjusted_close",
            "execution_price_field": "close",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["reference_result"] is not None
    assert payload["candidate_result"]["assumptions"]["execution_lag_days"] == 1
    assert payload["candidate_result"]["assumptions"]["tax_treatment"] == "pre_tax"
    assert payload["candidate_result"]["instrument_metadata"][0]["symbol"] == "VUAA"
    assert payload["candidate_result"]["status"] in {"ok", "degraded"}
    assert payload["reference_diagnostics"] is not None
    assert payload["candidate_diagnostics"] is not None
    assert payload["candidate_diagnostics"]["provenance"]["snapshot_basis"] == "synthetic_replay_snapshot"
    assert payload["candidate_diagnostics"]["provenance"]["historical_basis"] == "market_data_history"
    assert payload["diagnostics_comparison"] is not None
    assert payload["diagnostics_comparison"]["factor_exposure_changes"]
    assert payload["diagnostics_comparison"]["volatility_changes"]


def test_portfolio_allocation_backtest_route_enforces_execution_lag() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 0,
        },
    )

    assert response.status_code == 400


def test_portfolio_allocation_backtest_route_rejects_invalid_weight_sum() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "weights": [{"symbol": "SPY", "target_weight": 0.7}, {"symbol": "TLT", "target_weight": 0.1}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400


def test_portfolio_allocation_backtest_route_rejects_negative_weights() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "weights": [{"symbol": "SPY", "target_weight": 1.1}, {"symbol": "TLT", "target_weight": -0.1}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400


def test_portfolio_allocation_backtest_falls_back_to_spy_history_for_vuaa(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "VUAA", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_result"]["starting_weights"][0]["symbol"] == "VUAA"


def test_portfolio_allocation_backtest_route_rejects_candidate_reference_with_insufficient_common_dates(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "AAA": [
            {"date": "2024-01-02", "price": 50.0},
            {"date": "2024-01-03", "price": 51.0},
        ],
        "BBB": [
            {"date": "2024-01-03", "price": 80.0},
            {"date": "2024-01-04", "price": 81.0},
        ],
        "QQQ": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
            {"date": "2024-01-04", "price": 102.0},
        ],
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "AAA", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "BBB", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Not enough common dates across candidate, reference, and benchmark"}


def test_portfolio_allocation_backtest_falls_back_to_gld_history_for_sgld(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "SGLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "SGLD", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_result"]["starting_weights"][0]["symbol"] == "SGLD"


def test_portfolio_allocation_backtest_falls_back_to_dbc_history_for_icom(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "ICOM": _history(20.0, 20.5, 20.8, 21.0, 21.2),
        "DBC": _history(20.0, 20.5, 20.8, 21.0, 21.2),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "ICOM", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_result"]["starting_weights"][0]["symbol"] == "ICOM"


def test_portfolio_allocation_backtest_falls_back_to_slv_history_for_isln(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "ISLN": _history(20.0, 20.4, 20.8, 21.0, 21.2),
        "SLV": _history(20.0, 20.4, 20.8, 21.0, 21.2),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
        "DBC": _history(20.0, 20.5, 20.8, 21.0, 21.2),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation",
        json={
            "portfolio_name": "Candidate",
            "weights": [{"symbol": "ISLN", "target_weight": 1.0}],
            "reference_weights": [{"symbol": "SPY", "target_weight": 1.0}],
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_result"]["starting_weights"][0]["symbol"] == "ISLN"


def test_hypothetical_replacement_preview_route_returns_proposal_derivation_and_wrapped_replay(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IUFS": _history(100.0, 103.0, 103.5, 105.0, 109.0),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {
                    "importer": "interactive_brokers",
                    "statement_period": "2025-01-01 - 2025-12-31",
                    "imported_at": "2026-04-10T00:00:00Z",
                    "source_file_names": ["IB2025.pdf"],
                },
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "commission_bps": 2,
            "slippage_bps": 3,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["proposal"] == {
        "source": "draft_replacement_intent",
        "incumbent_symbol": "VUAA",
        "candidate_symbol": "IUFS",
        "draft_id": "draft-1",
        "base_node_id": "node-1",
    }
    assert payload["derivation"] == {
        "baseline_basis": "draft_snapshot_positions_normalized",
        "candidate_construction_rule": "same_weight_substitution_v1",
    }
    assert payload["replay_provenance"] == {
        "candidate_input_source": "replacement_intent_preview",
        "construction_rule_id": "same_weight_substitution_v1",
        "upstream_ids": {
            "draft_id": "draft-1",
            "workspace_id": "workspace-1",
            "base_node_id": "node-1",
        },
        "seed_ranking_id": "etf_ranking_engine_v1",
        "seed_methodology_id": "etf_ranking_methodology_v1",
        "constraint_validation": {
            "supplied": False,
            "validation_status": None,
            "constraint_set_id": None,
        },
    }
    assert payload["baseline_weights"] == [
        {"symbol": "VUAA", "target_weight": 0.6},
        {"symbol": "IB01", "target_weight": 0.4},
    ]
    assert payload["candidate_weights"] == [
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.6},
    ]
    assert payload["replay"]["reference_result"] is not None
    assert payload["replay"]["candidate_result"]["portfolio_name"] == "Hypothetical Candidate"
    assert payload["replay"]["candidate_result"]["commission_bps"] == 2
    assert payload["replay"]["candidate_result"]["slippage_bps"] == 3
    assert payload["replay"]["candidate_diagnostics"]["provenance"]["snapshot_basis"] == "synthetic_replay_snapshot"
    assert payload["replay"]["diagnostics_comparison"]["top_factor_exposure_change"] is not None
    assert payload["replay"]["diagnostics_comparison"]["top_volatility_change"] is not None
    assert payload["replay"]["diagnostics_comparison"]["top_factor_exposure_change"]["selection_rule"] == "largest_absolute_delta"
    assert "candidate - baseline" in payload["replay"]["diagnostics_comparison"]["top_factor_exposure_change"]["rationale"]


def test_hypothetical_replacement_preview_route_rejects_missing_intent() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [{"symbol": "VUAA", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"}],
                "cash_balances": [],
            },
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement_intent is required"}


def test_hypothetical_replacement_preview_route_rejects_incumbent_not_found() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [{"symbol": "IB01", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"}],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement intent incumbent not found in draft snapshot: VUAA"}


def test_hypothetical_replacement_preview_route_rejects_zero_weight_incumbent() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [
                    {"symbol": "VUAA", "market_value": 0, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement intent incumbent not found in draft snapshot: VUAA"}


def test_hypothetical_replacement_preview_route_rejects_same_symbol_candidate() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [{"symbol": "VUAA", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"}],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent(candidate_symbol="VUAA").model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement intent candidate must differ from incumbent"}


def test_hypothetical_replacement_preview_route_rejects_candidate_already_held() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IUFS", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "replacement intent candidate is already held in draft snapshot: IUFS"}


def test_hypothetical_replacement_preview_route_rejects_candidate_with_missing_history(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "No historical prices found for symbol: IUFS"}


def test_hypothetical_replacement_preview_route_rejects_insufficient_common_dates(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "VUAA": [
            {"date": "2024-01-02", "price": 50.0},
            {"date": "2024-01-03", "price": 51.0},
        ],
        "IB01": [
            {"date": "2024-01-02", "price": 90.0},
            {"date": "2024-01-03", "price": 91.0},
        ],
        "IUFS": [
            {"date": "2024-01-03", "price": 80.0},
        ],
        "QQQ": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "IWD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "IWM": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "XLF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "XLV": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "XLE": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "XLI": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "IEF": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "TLT": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "LQD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
        "GLD": [
            {"date": "2024-01-02", "price": 100.0},
            {"date": "2024-01-03", "price": 101.0},
        ],
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Not enough common dates across portfolio symbols and benchmark"}


def test_overlay_aware_hypothetical_replacement_preview_route_returns_base_and_overlay_replays(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IUFS": _history(100.0, 103.0, 103.5, 105.0, 109.0),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-overlay-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {
                    "importer": "interactive_brokers",
                    "statement_period": "2025-01-01 - 2025-12-31",
                    "imported_at": "2026-04-10T00:00:00Z",
                    "source_file_names": ["IB2025.pdf"],
                },
                "positions": [
                    {"symbol": "VUAA", "market_value": 60000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                    {"symbol": "IB01", "market_value": 40000, "quantity": 1, "currency": "USD", "source_type": "etf"},
                ],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "overlay_state": {
                "overlay_id": "benchmark_trend_overlay_v1",
                "status": "risk_reduced",
                "as_of_month_end": "2024-12-31",
                "benchmark_symbol": "SPY",
                "signal_basis": "10_month_sma_month_end",
                "confirmation_count": 2,
                "rule_version": "v1",
            },
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "commission_bps": 2,
            "slippage_bps": 3,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["overlay_application"] == {
        "overlay_id": "benchmark_trend_overlay_v1",
        "overlay_status": "risk_reduced",
        "as_of_month_end": "2024-12-31",
        "benchmark_symbol": "SPY",
        "risky_weight_scale": 0.35,
        "cash_residual_weight": 0.65,
        "applied_to_candidate_only": True,
    }
    assert payload["derivation"] == {
        "baseline_basis": "draft_snapshot_positions_normalized",
        "candidate_construction_rule": "same_weight_substitution_v1",
    }
    assert payload["replay_provenance"] == {
        "candidate_input_source": "replacement_intent_preview",
        "construction_rule_id": "same_weight_substitution_v1",
        "upstream_ids": {
            "draft_id": "draft-1",
            "workspace_id": "workspace-1",
            "base_node_id": "node-1",
        },
        "seed_ranking_id": "etf_ranking_engine_v1",
        "seed_methodology_id": "etf_ranking_methodology_v1",
        "constraint_validation": {
            "supplied": False,
            "validation_status": None,
            "constraint_set_id": None,
        },
    }
    assert payload["candidate_weights_pre_overlay"] == [
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.6},
    ]
    assert payload["candidate_weights_post_overlay"] == [
        {"symbol": "IB01", "target_weight": 0.14},
        {"symbol": "IUFS", "target_weight": 0.21},
        {"symbol": "__CASH__", "target_weight": 0.65},
    ]
    assert payload["base_replay"]["candidate_result"]["portfolio_name"] == "Hypothetical Candidate"
    assert payload["overlay_replay"]["candidate_result"]["portfolio_name"] == "Hypothetical Candidate Overlay-Aware"
    assert payload["overlay_replay"]["candidate_result"]["starting_weights"][-1]["symbol"] == "__CASH__"


def test_overlay_aware_hypothetical_replacement_preview_route_rejects_unconfirmed_overlay() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-overlay-preview",
        json={
            "snapshot": {
                "base_currency": "USD",
                "imported_meta": {"importer": "interactive_brokers", "statement_period": "2025", "imported_at": "2026-04-10T00:00:00Z", "source_file_names": ["IB2025.pdf"]},
                "positions": [{"symbol": "VUAA", "market_value": 100000, "quantity": 1, "currency": "USD", "source_type": "etf"}],
                "cash_balances": [],
            },
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "overlay_state": {
                "overlay_id": "benchmark_trend_overlay_v1",
                "status": "unconfirmed",
                "as_of_month_end": "2024-12-31",
                "benchmark_symbol": "SPY",
                "signal_basis": "10_month_sma_month_end",
                "confirmation_count": 1,
                "rule_version": "v1",
            },
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "overlay_state status unconfirmed is not replayable"}


def test_hypothetical_replacement_preview_route_uses_constructed_candidate_rule_in_derivation_and_provenance(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IUFS": _history(100.0, 103.0, 103.5, 105.0, 109.0),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }
    constructed_candidate = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID_FIXED_SPLIT),
        )
    )

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": _draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)).model_dump(mode="json"),
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "constructed_candidate": constructed_candidate.model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["derivation"] == {
        "baseline_basis": "draft_snapshot_positions_normalized",
        "candidate_construction_rule": "fixed_split_50_50_substitution_v2",
    }
    assert payload["replay_provenance"] == {
        "candidate_input_source": "constructed_candidate_payload",
        "construction_rule_id": "fixed_split_50_50_substitution_v2",
        "upstream_ids": {
            "draft_id": "draft-1",
            "workspace_id": "workspace-1",
            "base_node_id": "node-1",
        },
        "seed_ranking_id": "etf_ranking_engine_v1",
        "seed_methodology_id": "etf_ranking_methodology_v1",
        "constraint_validation": {
            "supplied": False,
            "validation_status": None,
            "constraint_set_id": None,
        },
    }
    assert payload["candidate_weights"] == [
        {"symbol": "VUAA", "target_weight": 0.3},
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.3},
    ]


def test_hypothetical_replacement_preview_route_echoes_constraint_validation_lineage_without_enforcement(mocker) -> None:
    mock_service = mocker.patch("app.services.portfolio_backtest_engine.MarketDataService")
    service_instance = mock_service.return_value
    service_instance.get_historical_prices_for_symbols.return_value = {
        "SPY": _history(100.0, 102.0, 102.5, 103.0, 108.0),
        "VUAA": _history(100.0, 102.0, 102.2, 103.1, 107.5),
        "IUFS": _history(100.0, 103.0, 103.5, 105.0, 109.0),
        "IB01": _history(100.0, 101.0, 101.3, 102.0, 103.0),
        "QQQ": _history(100.0, 104.0, 104.5, 106.0, 112.0),
        "IWD": _history(100.0, 101.0, 101.3, 101.8, 104.5),
        "IWM": _history(100.0, 99.0, 98.7, 99.8, 102.0),
        "XLF": _history(100.0, 103.0, 103.2, 104.0, 107.0),
        "XLV": _history(100.0, 101.0, 101.4, 102.1, 103.5),
        "XLE": _history(100.0, 97.0, 97.2, 98.5, 101.0),
        "XLI": _history(100.0, 102.0, 102.4, 103.2, 105.2),
        "IEF": _history(100.0, 100.4, 100.5, 100.6, 101.2),
        "TLT": _history(100.0, 99.5, 99.0, 101.0, 104.0),
        "LQD": _history(100.0, 100.8, 100.9, 101.2, 102.3),
        "GLD": _history(100.0, 101.0, 101.4, 102.8, 104.1),
    }
    constructed_candidate = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID_FIXED_SPLIT),
        )
    )
    constructed_candidate_input = ConstructedCandidateReplayInput.model_validate(constructed_candidate.model_dump(mode="json"))
    constraint_validation = validate_single_replacement_candidate_construction_constraints(
        SingleReplacementConstructionConstraintValidationRequest(
            constructed_candidate=constructed_candidate_input,
            constraint_set=SingleReplacementConstructionConstraintSetInput(constraint_set_id=CONSTRAINT_SET_ID),
        )
    )
    constraint_validation.validation.status = "blocked"

    client = TestClient(app)
    response = client.post(
        "/backtests/portfolio-allocation/replacement-intent-preview",
        json={
            "snapshot": _draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)).model_dump(mode="json"),
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "constructed_candidate": constructed_candidate_input.model_dump(mode="json"),
            "constraint_validation": constraint_validation.model_dump(mode="json"),
            "benchmark_symbol": "SPY",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "initial_capital": 100000,
            "rebalance_frequency": "monthly",
            "execution_lag_days": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["replay_provenance"]["constraint_validation"] == {
        "supplied": True,
        "validation_status": "blocked",
        "constraint_set_id": "single_replacement_construction_constraints_v1",
    }


def test_hypothetical_replacement_preview_rejects_constraint_validation_without_constructed_candidate() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constraint_validation=constraint_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation requires constructed_candidate"


def test_hypothetical_replacement_preview_rejects_constraint_validation_proposal_incumbent_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.proposal.incumbent_symbol = "QQQ"

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation incumbent does not match constructed_candidate proposal"


def test_hypothetical_replacement_preview_rejects_constraint_validation_proposal_candidate_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.proposal.candidate_symbol = "IUIT"

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation candidate does not match constructed_candidate proposal"


def test_hypothetical_replacement_preview_rejects_constraint_validation_rule_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.construction.rule_id = "same_weight_substitution_v1"

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation rule_id does not match constructed_candidate"


def test_hypothetical_replacement_preview_rejects_constraint_validation_status_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.construction.status = "rejected"

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation construction status does not match constructed_candidate"


def test_hypothetical_replacement_preview_rejects_constraint_validation_constraint_set_mismatch() -> None:
    constructed_candidate_input, constraint_validation = _constructed_candidate_and_constraint_validation()
    mismatched_validation = _clone_constraint_validation(constraint_validation)
    mismatched_validation.validation = cast(
        SingleReplacementConstraintValidationState,
        SimpleNamespace(
        kind=mismatched_validation.validation.kind,
        status=mismatched_validation.validation.status,
        constraint_set_id="unsupported_constraint_set_v0",
        ),
    )

    try:
        build_hypothetical_replacement_replay_preview(
            HypotheticalReplacementReplayRequest(
                snapshot=_draft_snapshot(("VUAA", 60000.0), ("IB01", 40000.0)),
                replacement_intent=_replacement_intent(),
                constructed_candidate=constructed_candidate_input,
                constraint_validation=mismatched_validation,
                benchmark_symbol="SPY",
                start_date=datetime(2024, 1, 1).date(),
                end_date=datetime(2024, 12, 31).date(),
                initial_capital=100000,
                rebalance_frequency="monthly",
                execution_lag_days=1,
            )
        )
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert str(exc) == "constraint_validation constraint_set_id is unsupported: unsupported_constraint_set_v0"
