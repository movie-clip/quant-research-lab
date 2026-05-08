import json
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.main import app
from app.schemas.construction import (
    ConstructionArtifact,
    ConstructionCurrentPortfolioInput,
    ConstructionHardConstraints,
    ConstructionPolicyInput,
    ConstructionRunRequest,
)
from app.schemas.construction import (
    EtfRankingArtifactConstructionHandoff,
    IntentBoundEtfReplacementRankingArtifactConstructionHandoff,
)
from app.schemas.research import EtfRankingArtifact, IntentBoundEtfReplacementRankingArtifact
from app.services.construction_run_service import build_construction_run_request_from_ranking_artifact_handoff
from app.services.construction_artifact_service import (
    ConstructionArtifactIntegrityValidationError,
    ConstructionArtifactInvalidJsonError,
    ConstructionArtifactMissingFileError,
    ConstructionArtifactNonObjectPayloadError,
    ConstructionArtifactPersistenceError,
    ConstructionArtifactSchemaValidationError,
    ConstructionArtifactStore,
    _canonical_json,
    load_construction_artifact,
)
from app.services import construction_policy_catalog
from app.services.construction_run_service import build_construction_run
from app.services.construction_run_service import (
    build_construction_preflight_response_from_etf_ranking_artifact,
    build_construction_preflight_response_from_replacement_ranking_artifact,
)
from app.services.strategy_lab import build_etf_ranking_analysis
from app.services.etf_ranking_artifact_service import build_stable_etf_ranking_artifact
from app.services.replacement_ranking import build_intent_bound_etf_replacement_ranking
from app.services.replacement_ranking_artifact_service import build_stable_replacement_ranking_artifact


def _request(
    top_n: int = 2,
    max_position_weight: float = 0.6,
    policy_id: str = "top_n_equal_weight_v1",
    max_turnover_weight: float | None = None,
    min_position_weight: float | None = None,
    max_trade_intent_count: int | None = None,
    *,
    include_max_turnover_weight: bool = False,
    include_min_position_weight: bool = False,
    include_max_trade_intent_count: bool = False,
) -> ConstructionRunRequest:
    payload = {
        "request_id": "construction-1",
        "ranked_universe": {
            "artifact_id": "ranking_artifact_1",
            "ranking_id": "ranked_candidates_v1",
            "methodology_id": "ranked_candidates_methodology_v1",
            "as_of_date": "2026-04-23",
            "ranked_candidates": [
                {"symbol": "aaa", "rank": 1, "eligible": True, "score": 9.5},
                {"symbol": "bbb", "rank": 2, "eligible": True, "score": 8.1},
                {"symbol": "ccc", "rank": 3, "eligible": True, "score": 7.0},
                {"symbol": "ddd", "rank": 4, "eligible": False, "score": 6.5, "exclusion_reason": "liquidity_screen"},
            ],
        },
        "current_portfolio": {
            "artifact_id": "portfolio_snapshot_1",
            "as_of_timestamp": "2026-04-23T09:30:00",
            "weights": [
                {"symbol": "bbb", "weight": 0.4},
                {"symbol": "ccc", "weight": 0.35},
                {"symbol": "eee", "weight": 0.25},
            ],
        },
        "policy": {"policy_id": policy_id, "top_n": top_n},
        "hard_constraints": {
            "full_investment": True,
            "long_only": True,
            "eligible_ranked_universe_only": True,
            "max_position_weight": max_position_weight,
        },
    }
    if include_min_position_weight or min_position_weight is not None:
        payload["hard_constraints"]["min_position_weight"] = min_position_weight
    if include_max_turnover_weight or max_turnover_weight is not None:
        payload["hard_constraints"]["max_turnover_weight"] = max_turnover_weight
    if include_max_trade_intent_count or max_trade_intent_count is not None:
        payload["hard_constraints"]["max_trade_intent_count"] = max_trade_intent_count
    return ConstructionRunRequest.model_validate(payload)


def _persisted_etf_ranking_artifact_for_construction():
    ranking = build_etf_ranking_analysis(
        universe=["XLK", "XLF", "XLV"],
        benchmark_symbol="SPY",
        lookback_months=6,
    )
    return build_stable_etf_ranking_artifact(ranking)


def _persisted_replacement_ranking_artifact_for_construction() -> IntentBoundEtfReplacementRankingArtifact:
    from app.schemas.research import (
        IntentBoundEtfReplacementRankingRequest,
        IntentBoundReplacementIntent,
        IntentBoundSeedContext,
        Instrument,
    )
    from app.services import replacement_ranking as replacement_ranking_module

    class _FakeRegistry:
        def __init__(self, instruments):
            self._instruments = instruments

        def get_instrument(self, symbol: str):
            return self._instruments.get(symbol)

    class _FakeMarketData:
        def __init__(self, histories):
            self._histories = histories

        def get_historical_prices_for_symbols(self, symbols, from_date, to_date):  # noqa: ANN001
            return {symbol: self._histories.get(symbol, []) for symbol in symbols}

        def get_last_fetch_meta(self, symbol: str):
            return {"resolved_symbol": symbol, "cached": True}

    def _instrument(symbol: str) -> Instrument:
        return Instrument(
            instrument_id=f"instrument-{symbol.lower()}",
            symbol=symbol,
            name=symbol,
            asset_class="etf",
            kind="spot",
            sector="Technology",
            category="Sector UCITS ETF",
            exchange="TEST",
            currency="USD",
        )

    def _history(days: int, *, start_price: float = 100.0, step: float = 1.0, volume: float = 1000.0) -> list[dict]:
        from datetime import date, timedelta

        end = date(2025, 12, 31)
        start = end - timedelta(days=days - 1)
        rows: list[dict] = []
        for index in range(days):
            price = start_price + (index * step)
            rows.append(
                {
                    "date": (start + timedelta(days=index)).isoformat(),
                    "close": round(price, 6),
                    "volume": volume,
                    "adjClose": round(price, 6),
                }
            )
        return rows

    histories = {
        "BASE": _history(260),
        "ETF1": _history(260, step=0.5),
        "ETF2": _history(260, step=0.25),
    }
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    original_registry = replacement_ranking_module.InstrumentRegistry
    original_market_data = replacement_ranking_module.MarketDataService
    replacement_ranking_module.InstrumentRegistry = lambda: _FakeRegistry(instruments)
    replacement_ranking_module.MarketDataService = lambda: _FakeMarketData(histories)
    try:
        response = build_intent_bound_etf_replacement_ranking(
            IntentBoundEtfReplacementRankingRequest(
                replacement_intent=IntentBoundReplacementIntent(
                    draft_id="draft-1",
                    workspace_id="workspace-1",
                    base_node_id="node-1",
                    base_symbol="BASE",
                    candidate_symbol="ETF1",
                    seed_ranking_id="etf_ranking_engine_v1",
                    seed_methodology_id="etf_ranking_methodology_v1",
                    seed_ranking_basis_date="2025-12-31",
                    peer_group="Sector UCITS ETF",
                    benchmark_symbol="SPY",
                    lookback_months=6,
                ),
                seed_context=IntentBoundSeedContext(
                    ranking_id="etf_ranking_engine_v1",
                    methodology_id="etf_ranking_methodology_v1",
                    ranking_basis_date="2025-12-31",
                    peer_group="Sector UCITS ETF",
                    benchmark_symbol="SPY",
                    lookback_months=6,
                    seeded_symbols=["BASE", "ETF1", "ETF2"],
                ),
            )
        )
    finally:
        replacement_ranking_module.InstrumentRegistry = original_registry
        replacement_ranking_module.MarketDataService = original_market_data
    return build_stable_replacement_ranking_artifact(response)


def _handoff_supporting_inputs(
    artifact: EtfRankingArtifact,
) -> tuple[ConstructionCurrentPortfolioInput, ConstructionPolicyInput, ConstructionHardConstraints]:
    inline_request = _inline_request_from_etf_ranking_artifact(artifact)
    return inline_request.current_portfolio, inline_request.policy, inline_request.hard_constraints


def _inline_request_from_etf_ranking_artifact(artifact) -> ConstructionRunRequest:
    top_symbols = [row.symbol for row in artifact.ranked_universe[:2]]
    trailing_symbol = artifact.ranked_universe[2].symbol if len(artifact.ranked_universe) > 2 else top_symbols[-1]
    current_weights = [
        {"symbol": top_symbols[1], "weight": 0.4},
        {"symbol": trailing_symbol, "weight": 0.35},
        {"symbol": "GLD", "weight": 0.25},
    ]
    ranked_candidates = [
        {
            "symbol": row.symbol,
            "rank": row.rank,
            "eligible": True,
            "score": row.composite_score,
        }
        for row in artifact.ranked_universe
    ]
    return ConstructionRunRequest.model_validate(
        {
            "request_id": "construction-artifact-handoff-parity",
            "ranked_universe": {
                "artifact_id": artifact.artifact_id,
                "ranking_id": artifact.ranking_id,
                "methodology_id": artifact.run_metadata.methodology_id,
                "as_of_date": artifact.run_metadata.as_of_date,
                "ranked_candidates": ranked_candidates,
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": current_weights,
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        }
    )


def _inline_request_from_replacement_ranking_artifact(
    artifact: IntentBoundEtfReplacementRankingArtifact,
) -> ConstructionRunRequest:
    eligible_rows = sorted(
        [row for row in artifact.ranked_candidates if row.rank is not None],
        key=lambda row: (row.rank or 10**9, row.symbol),
    )
    top_symbols = [row.symbol for row in eligible_rows[:2]]
    trailing_symbol = eligible_rows[2].symbol if len(eligible_rows) > 2 else top_symbols[-1]
    current_weights = [
        {"symbol": top_symbols[1], "weight": 0.4},
        {"symbol": trailing_symbol, "weight": 0.35},
        {"symbol": "GLD", "weight": 0.25},
    ]
    ranked_candidates = [
        {
            "symbol": row.symbol,
            "rank": row.rank,
            "eligible": True,
            "score": row.composite_score,
        }
        for row in eligible_rows
    ] + [
        {
            "symbol": row.symbol,
            "rank": row.rank,
            "eligible": False,
            "score": row.composite_score,
            "exclusion_reason": row.exclusion_reason,
        }
        for row in artifact.excluded_candidates
        if row.rank is not None
    ]
    return ConstructionRunRequest.model_validate(
        {
            "request_id": "construction-artifact-handoff-parity-replacement",
            "ranked_universe": {
                "artifact_id": artifact.artifact_id,
                "ranking_id": artifact.ranking_id,
                "methodology_id": artifact.run_metadata.methodology_id,
                "as_of_date": artifact.run_metadata.as_of_date,
                "ranked_candidates": ranked_candidates,
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": current_weights,
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        }
    )


def _rewrite_artifact_with_rekeyed_payload(
    tmp_path: Path,
    artifact_id: str,
    payload_mutator,
) -> tuple[str, dict]:
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload_mutator(payload)
    payload_without_ids = {key: value for key, value in payload.items() if key not in {"artifact_id", "fingerprint"}}
    fingerprint = sha256(_canonical_json(payload_without_ids).encode("utf-8")).hexdigest()
    legacy_artifact_id = f"construction_artifact_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["artifact_id"] = legacy_artifact_id
    artifact_path.unlink()
    legacy_path = tmp_path / f"{legacy_artifact_id}.json"
    legacy_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    return legacy_artifact_id, payload


CONSTRUCTION_ARTIFACT_FIXTURE_DIR = Path(__file__).with_name("fixtures") / "construction_artifacts"


def _persist_construction_artifact_fixture(tmp_path: Path, fixture_name: str) -> tuple[str, dict]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    payload = json.loads((CONSTRUCTION_ARTIFACT_FIXTURE_DIR / fixture_name).read_text(encoding="utf-8"))
    artifact_path = tmp_path / f"{payload['artifact_id']}.json"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")
    return payload["artifact_id"], payload


def test_build_construction_run_returns_deterministic_equal_weight_artifact(tmp_path: Path) -> None:
    result = build_construction_run(_request(), artifact_store=ConstructionArtifactStore(str(tmp_path)))

    assert result.status == "feasible"
    assert result.policy.policy_id == "top_n_equal_weight_v1"
    assert result.normalized_inputs.policy_definition_id == "construction_policy_definition_top_n_equal_weight_v1"
    assert result.artifact_id.startswith("construction_artifact_")
    assert len(result.fingerprint) == 64
    assert [item.model_dump(mode="json") for item in result.selected_names] == [
        {"symbol": "AAA", "rank": 1, "score": 9.5},
        {"symbol": "BBB", "rank": 2, "score": 8.1},
    ]
    assert [item.model_dump(mode="json") for item in result.seed_weights] == [
        {"symbol": "AAA", "weight": 0.5},
        {"symbol": "BBB", "weight": 0.5},
    ]
    assert [item.model_dump(mode="json") for item in result.final_target_weights] == [
        {"symbol": "AAA", "weight": 0.5},
        {"symbol": "BBB", "weight": 0.5},
    ]
    assert [item.model_dump(mode="json") for item in result.trade_intents] == [
        {"symbol": "AAA", "action": "initiate", "current_weight": 0.0, "target_weight": 0.5, "delta_weight": 0.5},
        {"symbol": "BBB", "action": "buy", "current_weight": 0.4, "target_weight": 0.5, "delta_weight": 0.1},
        {"symbol": "CCC", "action": "exit", "current_weight": 0.35, "target_weight": 0.0, "delta_weight": -0.35},
        {"symbol": "EEE", "action": "exit", "current_weight": 0.25, "target_weight": 0.0, "delta_weight": -0.25},
    ]
    assert [item.model_dump(mode="json") for item in result.excluded_names] == [
        {"symbol": "CCC", "rank": 3, "eligible": True, "reason": "not selected by top_n_equal_weight_v1 cutoff"},
        {"symbol": "DDD", "rank": 4, "eligible": False, "reason": "liquidity_screen"},
    ]
    assert result.deterministic_ordering.model_dump(mode="json") == {
        "ranked_candidate_symbols": ["AAA", "BBB", "CCC", "DDD"],
        "selected_symbols": ["AAA", "BBB"],
        "trade_symbols": ["AAA", "BBB", "CCC", "EEE"],
    }
    assert result.selection_rule_trace.model_dump(mode="json") == {
        "rule_ids": ["eligible_only", "take_top_n"],
        "steps": [
            {
                "rule_id": "eligible_only",
                "rule_order": 1,
                "input_candidate_symbols": ["AAA", "BBB", "CCC", "DDD"],
                "output_candidate_symbols": ["AAA", "BBB", "CCC"],
            },
            {
                "rule_id": "take_top_n",
                "rule_order": 2,
                "input_candidate_symbols": ["AAA", "BBB", "CCC"],
                "output_candidate_symbols": ["AAA", "BBB"],
            },
        ],
    }
    assert result.turnover_diagnostics_status == "available"
    assert result.turnover_diagnostics_v1 is not None
    assert result.turnover_diagnostics_v1.model_dump(mode="json") == {
        "diagnostics_version": "construction_turnover_diagnostics_v1",
        "source": "persisted_construction_artifact",
        "diagnostic_truth": "artifact_backed_hypothetical_construction_diagnostics_only",
        "turnover_basis_method_version": "half_l1_weight_delta_union_v1",
        "reported_value_status": "computed",
        "reported_turnover_weight": 0.6,
        "inclusion_flags": {
            "uses_current_and_target_weight_union": True,
            "includes_initiations": True,
            "includes_exits": True,
            "includes_zero_delta_positions_in_trade_intent_context": True,
            "excludes_zero_delta_positions_from_reported_turnover_sum": True,
        },
        "trade_intent_context": {"source_field": "trade_intents", "intent_count": 4},
        "feasibility_context": {
            "artifact_status": "feasible",
            "failure_reasons_field": "failure_reasons",
            "turnover_failure_reason_present": False,
        },
        "constraint_context": {
            "constraint_id": "max_turnover_weight",
            "requested": False,
            "limit_weight": None,
            "evaluation_status": "not_evaluated",
        },
        "symbol_contributions": [
            {
                "symbol": "AAA",
                "action": "initiate",
                "current_weight": 0.0,
                "target_weight": 0.5,
                "delta_weight": 0.5,
                "absolute_delta_weight": 0.5,
                "turnover_contribution_weight": 0.25,
                "contribution_fraction_of_reported_turnover": 0.41666667,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "BBB",
                "action": "buy",
                "current_weight": 0.4,
                "target_weight": 0.5,
                "delta_weight": 0.1,
                "absolute_delta_weight": 0.1,
                "turnover_contribution_weight": 0.05,
                "contribution_fraction_of_reported_turnover": 0.08333333,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "CCC",
                "action": "exit",
                "current_weight": 0.35,
                "target_weight": 0.0,
                "delta_weight": -0.35,
                "absolute_delta_weight": 0.35,
                "turnover_contribution_weight": 0.175,
                "contribution_fraction_of_reported_turnover": 0.29166667,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "EEE",
                "action": "exit",
                "current_weight": 0.25,
                "target_weight": 0.0,
                "delta_weight": -0.25,
                "absolute_delta_weight": 0.25,
                "turnover_contribution_weight": 0.125,
                "contribution_fraction_of_reported_turnover": 0.20833333,
                "included_in_reported_turnover": True,
            },
        ],
    }
    assert result.weighting_trace_status == "available"
    assert result.weighting_trace_v1 is not None
    assert result.weighting_trace_v1.model_dump(mode="json") == {
        "trace_version": "weighting_trace_v1",
        "source": "persisted_construction_artifact",
        "diagnostic_truth": "artifact_backed_hypothetical_construction_diagnostics_only",
        "policy_id": "top_n_equal_weight_v1",
        "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
        "stages": [
            {
                "stage_id": "selected_order_to_raw_weight_numerator",
                "stage_order": 1,
                "input_metric_id": "selected_order",
                "output_metric_id": "raw_weight_numerator",
                "positions": [
                    {"symbol": "AAA", "rank": 1, "selected_order": 1, "input_value": 1.0, "output_value": 0.5},
                    {"symbol": "BBB", "rank": 2, "selected_order": 2, "input_value": 2.0, "output_value": 0.5},
                ],
            },
            {
                "stage_id": "raw_weight_numerator_to_seed_weight",
                "stage_order": 2,
                "input_metric_id": "raw_weight_numerator",
                "output_metric_id": "seed_weight",
                "positions": [
                    {"symbol": "AAA", "rank": 1, "selected_order": 1, "input_value": 0.5, "output_value": 0.5},
                    {"symbol": "BBB", "rank": 2, "selected_order": 2, "input_value": 0.5, "output_value": 0.5},
                ],
            },
            {
                "stage_id": "seed_weight_to_target_weight",
                "stage_order": 3,
                "input_metric_id": "seed_weight",
                "output_metric_id": "target_weight",
                "positions": [
                    {"symbol": "AAA", "rank": 1, "selected_order": 1, "input_value": 0.5, "output_value": 0.5},
                    {"symbol": "BBB", "rank": 2, "selected_order": 2, "input_value": 0.5, "output_value": 0.5},
                ],
            },
        ],
        "normalization": {
            "normalization_source": "raw_weight_numerator_to_seed_weight",
            "normalization_applied": True,
            "input_metric_id": "raw_weight_numerator",
            "output_metric_id": "seed_weight",
            "raw_value_sum": 1.0,
            "normalized_value_sum": 1.0,
            "rounding_scale": 8,
            "normalization_method": "fractional_sum_division_with_last_position_reconciliation",
            "residual_reconciliation_symbol": "BBB",
            "residual_reconciliation_delta": 0.0,
        },
        "artifact_binding": {
            "binding_status": "final_target_weights_persisted",
            "final_target_weights_present": True,
        },
    }
    assert [item.constraint_id for item in result.constraint_evaluations] == [
        "full_investment",
        "long_only",
        "eligible_ranked_universe_only",
        "max_position_weight",
        "min_position_weight",
        "max_turnover_weight",
        "max_trade_intent_count",
    ]
    assert next(item for item in result.constraint_evaluations if item.constraint_id == "full_investment").status == "binding"
    assert next(item for item in result.constraint_evaluations if item.constraint_id == "max_position_weight").status == "pass"
    assert next(item for item in result.constraint_evaluations if item.constraint_id == "min_position_weight").status == "not_evaluated"
    turnover_constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert turnover_constraint.status == "not_evaluated"
    assert turnover_constraint.limit_value is None
    trade_intent_count_constraint = next(
        item for item in result.constraint_evaluations if item.constraint_id == "max_trade_intent_count"
    )
    assert trade_intent_count_constraint.status == "not_evaluated"
    assert trade_intent_count_constraint.limit_value is None


def test_build_construction_run_returns_inverse_rank_weight_artifact(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.55, policy_id="top_n_inverse_rank_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    assert result.policy.policy_id == "top_n_inverse_rank_weight_v1"
    assert result.normalized_inputs.policy_definition_id == "construction_policy_definition_top_n_inverse_rank_weight_v1"
    assert result.artifact_id.startswith("construction_artifact_")
    assert len(result.fingerprint) == 64
    assert [item.model_dump(mode="json") for item in result.selected_names] == [
        {"symbol": "AAA", "rank": 1, "score": 9.5},
        {"symbol": "BBB", "rank": 2, "score": 8.1},
        {"symbol": "CCC", "rank": 3, "score": 7.0},
    ]
    assert [item.model_dump(mode="json") for item in result.seed_weights] == [
        {"symbol": "AAA", "weight": 0.54545455},
        {"symbol": "BBB", "weight": 0.27272727},
        {"symbol": "CCC", "weight": 0.18181818},
    ]
    assert [item.model_dump(mode="json") for item in result.final_target_weights] == [
        {"symbol": "AAA", "weight": 0.54545455},
        {"symbol": "BBB", "weight": 0.27272727},
        {"symbol": "CCC", "weight": 0.18181818},
    ]
    assert result.weighting_trace_status == "available"
    assert result.weighting_trace_v1 is not None
    assert result.weighting_trace_v1.normalization.model_dump(mode="json") == {
        "normalization_source": "raw_weight_numerator_to_seed_weight",
        "normalization_applied": True,
        "input_metric_id": "raw_weight_numerator",
        "output_metric_id": "seed_weight",
        "raw_value_sum": 1.8333333333333333,
        "normalized_value_sum": 1.0,
        "rounding_scale": 8,
        "normalization_method": "fractional_sum_division_with_last_position_reconciliation",
        "residual_reconciliation_symbol": "CCC",
        "residual_reconciliation_delta": 0.0,
    }
    assert [item.model_dump(mode="json") for item in result.excluded_names] == [
        {"symbol": "DDD", "rank": 4, "eligible": False, "reason": "liquidity_screen"},
    ]
    assert next(item for item in result.constraint_evaluations if item.constraint_id == "full_investment").status == "binding"
    max_position_constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_position_weight")
    assert max_position_constraint.status == "pass"
    assert max_position_constraint.actual_value == 0.54545455


def test_build_construction_run_returns_linear_rank_weight_artifact(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.51, policy_id="top_n_linear_rank_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    assert result.policy.policy_id == "top_n_linear_rank_weight_v1"
    assert result.normalized_inputs.policy_definition_id == "construction_policy_definition_top_n_linear_rank_weight_v1"
    assert [item.model_dump(mode="json") for item in result.selected_names] == [
        {"symbol": "AAA", "rank": 1, "score": 9.5},
        {"symbol": "BBB", "rank": 2, "score": 8.1},
        {"symbol": "CCC", "rank": 3, "score": 7.0},
    ]
    assert [item.model_dump(mode="json") for item in result.seed_weights] == [
        {"symbol": "AAA", "weight": 0.5},
        {"symbol": "BBB", "weight": 0.33333333},
        {"symbol": "CCC", "weight": 0.16666667},
    ]
    assert [item.model_dump(mode="json") for item in result.final_target_weights] == [
        {"symbol": "AAA", "weight": 0.5},
        {"symbol": "BBB", "weight": 0.33333333},
        {"symbol": "CCC", "weight": 0.16666667},
    ]
    assert result.weighting_trace_status == "available"
    assert result.weighting_trace_v1 is not None
    assert result.weighting_trace_v1.stages[0].model_dump(mode="json") == {
        "stage_id": "selected_order_to_raw_weight_numerator",
        "stage_order": 1,
        "input_metric_id": "selected_order",
        "output_metric_id": "raw_weight_numerator",
        "positions": [
            {"symbol": "AAA", "rank": 1, "selected_order": 1, "input_value": 1.0, "output_value": 3.0},
            {"symbol": "BBB", "rank": 2, "selected_order": 2, "input_value": 2.0, "output_value": 2.0},
            {"symbol": "CCC", "rank": 3, "selected_order": 3, "input_value": 3.0, "output_value": 1.0},
        ],
    }
    assert [item.model_dump(mode="json") for item in result.excluded_names] == [
        {"symbol": "DDD", "rank": 4, "eligible": False, "reason": "liquidity_screen"},
    ]


@pytest.mark.parametrize(
    ("policy_id", "top_n", "max_position_weight", "min_position_weight", "expected_min_weight"),
    [
        ("top_n_equal_weight_v1", 2, 0.6, 0.5, 0.5),
        ("top_n_inverse_rank_weight_v1", 3, 0.55, 0.18, 0.18181818),
        ("top_n_linear_rank_weight_v1", 3, 0.51, 0.16, 0.16666667),
    ],
)
def test_build_construction_run_marks_min_position_constraint_pass_when_policy_output_is_feasible(
    tmp_path: Path,
    policy_id: str,
    top_n: int,
    max_position_weight: float,
    min_position_weight: float,
    expected_min_weight: float,
) -> None:
    result = build_construction_run(
        _request(
            top_n=top_n,
            max_position_weight=max_position_weight,
            policy_id=policy_id,
            min_position_weight=min_position_weight,
        ),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    assert result.hard_constraints.min_position_weight == min_position_weight
    assert result.normalized_inputs.min_position_weight == min_position_weight
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "min_position_weight")
    assert constraint.status == ("binding" if expected_min_weight == min_position_weight else "pass")
    assert constraint.actual_value == expected_min_weight
    assert constraint.limit_value == min_position_weight


@pytest.mark.parametrize(
    ("policy_id", "top_n", "max_position_weight", "min_position_weight", "expected_reason", "expected_actual"),
    [
        ("top_n_equal_weight_v1", 2, 0.6, 0.51, "min_position_weight=0.51000000 is infeasible for selected_count=2 under full investment", 0.5),
        ("top_n_inverse_rank_weight_v1", 3, 0.55, 0.19, "policy output violates min_position_weight=0.19000000", 0.18181818),
        ("top_n_linear_rank_weight_v1", 3, 0.51, 0.17, "policy output violates min_position_weight=0.17000000", 0.16666667),
    ],
)
def test_build_construction_run_fails_closed_when_policy_output_breaks_min_position_constraint(
    tmp_path: Path,
    policy_id: str,
    top_n: int,
    max_position_weight: float,
    min_position_weight: float,
    expected_reason: str,
    expected_actual: float,
) -> None:
    result = build_construction_run(
        _request(
            top_n=top_n,
            max_position_weight=max_position_weight,
            policy_id=policy_id,
            min_position_weight=min_position_weight,
        ),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert expected_reason in result.failure_reasons
    assert result.final_target_weights == []
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "min_position_weight")
    assert constraint.status == "fail"
    assert constraint.actual_value == expected_actual
    assert constraint.limit_value == min_position_weight


def test_build_construction_run_marks_min_position_constraint_binding_at_boundary(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(min_position_weight=0.5),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "min_position_weight")
    assert constraint.status == "binding"
    assert constraint.actual_value == 0.5
    assert constraint.limit_value == 0.5


def test_build_construction_run_fails_closed_when_min_position_weight_exceeds_max_position_weight(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="min_position_weight must be less than or equal to max_position_weight"):
        _request(max_position_weight=0.49, min_position_weight=0.5)


@pytest.mark.parametrize(
    "invalid_value",
    [-1, 1.5, True, "4"],
    ids=["negative", "float", "bool", "string"],
)
def test_construction_run_request_rejects_invalid_max_trade_intent_count_values(invalid_value) -> None:
    with pytest.raises(ValidationError):
        _request(include_max_trade_intent_count=True, max_trade_intent_count=invalid_value)


def test_build_construction_run_fails_closed_when_min_position_weight_is_infeasible_for_selected_count(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.5, min_position_weight=0.34),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.failure_reasons == [
        "min_position_weight=0.34000000 is infeasible for selected_count=3 under full investment"
    ]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "min_position_weight")
    assert constraint.status == "fail"
    assert constraint.actual_value == 0.33333333
    assert constraint.limit_value == 0.34


def test_build_construction_run_marks_turnover_constraint_pass_when_under_cap(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(max_turnover_weight=0.61),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert constraint.status == "pass"
    assert constraint.actual_value == 0.6
    assert constraint.limit_value == 0.61
    assert result.turnover_diagnostics_v1 is not None
    assert result.turnover_diagnostics_v1.constraint_context.model_dump(mode="json") == {
        "constraint_id": "max_turnover_weight",
        "requested": True,
        "limit_weight": 0.61,
        "evaluation_status": "pass",
    }
    assert result.turnover_diagnostics_v1.reported_turnover_weight == 0.6


def test_build_construction_run_preserves_outputs_while_persisting_weighting_trace_v1(tmp_path: Path) -> None:
    baseline_outputs = {
        "status": "feasible",
        "selected_names": [
            {"symbol": "AAA", "rank": 1, "score": 9.5},
            {"symbol": "BBB", "rank": 2, "score": 8.1},
            {"symbol": "CCC", "rank": 3, "score": 7.0},
        ],
        "seed_weights": [
            {"symbol": "AAA", "weight": 0.54545455},
            {"symbol": "BBB", "weight": 0.27272727},
            {"symbol": "CCC", "weight": 0.18181818},
        ],
        "final_target_weights": [
            {"symbol": "AAA", "weight": 0.54545455},
            {"symbol": "BBB", "weight": 0.27272727},
            {"symbol": "CCC", "weight": 0.18181818},
        ],
        "failure_reasons": [],
    }

    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.55, policy_id="top_n_inverse_rank_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert {
        "status": result.status,
        "selected_names": [item.model_dump(mode="json") for item in result.selected_names],
        "seed_weights": [item.model_dump(mode="json") for item in result.seed_weights],
        "final_target_weights": [item.model_dump(mode="json") for item in result.final_target_weights],
        "failure_reasons": result.failure_reasons,
    } == baseline_outputs
    assert result.weighting_trace_status == "available"
    assert result.weighting_trace_v1 is not None


def test_build_construction_run_persists_infeasible_weighting_trace_without_changing_outputs(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.54, policy_id="top_n_inverse_rank_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.final_target_weights == []
    assert result.trade_intents == []
    assert result.failure_reasons == ["inverse-rank seed exceeds max_position_weight"]
    assert result.turnover_diagnostics_status == "available"
    assert result.turnover_diagnostics_v1 is not None
    assert result.turnover_diagnostics_v1.model_dump(mode="json") == {
        "diagnostics_version": "construction_turnover_diagnostics_v1",
        "source": "persisted_construction_artifact",
        "diagnostic_truth": "artifact_backed_hypothetical_construction_diagnostics_only",
        "turnover_basis_method_version": "half_l1_weight_delta_union_v1",
        "reported_value_status": "computed",
        "reported_turnover_weight": 0.54545455,
        "inclusion_flags": {
            "uses_current_and_target_weight_union": True,
            "includes_initiations": True,
            "includes_exits": True,
            "includes_zero_delta_positions_in_trade_intent_context": True,
            "excludes_zero_delta_positions_from_reported_turnover_sum": True,
        },
        "trade_intent_context": {"source_field": "trade_intents", "intent_count": 0},
        "feasibility_context": {
            "artifact_status": "infeasible",
            "failure_reasons_field": "failure_reasons",
            "turnover_failure_reason_present": False,
        },
        "constraint_context": {
            "constraint_id": "max_turnover_weight",
            "requested": False,
            "limit_weight": None,
            "evaluation_status": "not_evaluated",
        },
        "symbol_contributions": [
            {
                "symbol": "AAA",
                "action": "initiate",
                "current_weight": 0.0,
                "target_weight": 0.54545455,
                "delta_weight": 0.54545455,
                "absolute_delta_weight": 0.54545455,
                "turnover_contribution_weight": 0.27272727,
                "contribution_fraction_of_reported_turnover": 0.49999999,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "BBB",
                "action": "sell",
                "current_weight": 0.4,
                "target_weight": 0.27272727,
                "delta_weight": -0.12727273,
                "absolute_delta_weight": 0.12727273,
                "turnover_contribution_weight": 0.06363637,
                "contribution_fraction_of_reported_turnover": 0.11666668,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "CCC",
                "action": "sell",
                "current_weight": 0.35,
                "target_weight": 0.18181818,
                "delta_weight": -0.16818182,
                "absolute_delta_weight": 0.16818182,
                "turnover_contribution_weight": 0.08409091,
                "contribution_fraction_of_reported_turnover": 0.15416667,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "EEE",
                "action": "exit",
                "current_weight": 0.25,
                "target_weight": 0.0,
                "delta_weight": -0.25,
                "absolute_delta_weight": 0.25,
                "turnover_contribution_weight": 0.125,
                "contribution_fraction_of_reported_turnover": 0.22916666,
                "included_in_reported_turnover": True,
            },
        ],
    }
    assert result.weighting_trace_status == "available"
    assert result.weighting_trace_v1 is not None
    assert result.weighting_trace_v1.artifact_binding.model_dump(mode="json") == {
        "binding_status": "generated_target_weights_not_persisted_due_to_infeasible_artifact",
        "final_target_weights_present": False,
    }
    assert result.weighting_trace_v1.stages[2].model_dump(mode="json") == {
        "stage_id": "seed_weight_to_target_weight",
        "stage_order": 3,
        "input_metric_id": "seed_weight",
        "output_metric_id": "target_weight",
        "positions": [
            {"symbol": "AAA", "rank": 1, "selected_order": 1, "input_value": 0.54545455, "output_value": 0.54545455},
            {"symbol": "BBB", "rank": 2, "selected_order": 2, "input_value": 0.27272727, "output_value": 0.27272727},
            {"symbol": "CCC", "rank": 3, "selected_order": 3, "input_value": 0.18181818, "output_value": 0.18181818},
        ],
    }


def test_build_construction_run_marks_turnover_constraint_binding_when_at_cap(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(max_turnover_weight=0.6),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert constraint.status == "binding"
    assert constraint.actual_value == 0.6
    assert constraint.limit_value == 0.6
    assert result.turnover_diagnostics_v1 is not None
    assert result.turnover_diagnostics_v1.constraint_context.evaluation_status == "binding"


def test_build_construction_run_fails_closed_when_turnover_breaks_max_turnover_constraint(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(max_turnover_weight=0.59),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.final_target_weights == []
    assert result.trade_intents == []
    assert result.failure_reasons == ["target turnover exceeds max_turnover_weight"]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert constraint.status == "fail"
    assert constraint.actual_value == 0.6
    assert constraint.limit_value == 0.59
    assert result.turnover_diagnostics_v1 is not None
    assert result.turnover_diagnostics_v1.feasibility_context.turnover_failure_reason_present is True
    assert result.turnover_diagnostics_v1.constraint_context.model_dump(mode="json") == {
        "constraint_id": "max_turnover_weight",
        "requested": True,
        "limit_weight": 0.59,
        "evaluation_status": "fail",
    }


def test_build_construction_run_keeps_turnover_constraint_not_evaluated_when_cap_is_omitted(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert constraint.status == "not_evaluated"
    assert constraint.actual_value is None
    assert constraint.limit_value is None


def test_build_construction_run_keeps_trade_intent_count_constraint_not_evaluated_when_limit_is_omitted(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_trade_intent_count")
    assert constraint.status == "not_evaluated"
    assert constraint.actual_value is None
    assert constraint.limit_value is None


def test_build_construction_run_marks_trade_intent_count_constraint_pass_when_under_limit(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(max_trade_intent_count=5),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    assert len(result.trade_intents) == 4
    assert result.hard_constraints.max_trade_intent_count == 5
    assert result.normalized_inputs.max_trade_intent_count == 5
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_trade_intent_count")
    assert constraint.status == "pass"
    assert constraint.actual_value == 4.0
    assert constraint.limit_value == 5.0


def test_build_construction_run_marks_trade_intent_count_constraint_binding_at_limit(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(max_trade_intent_count=4),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_trade_intent_count")
    assert constraint.status == "binding"
    assert constraint.actual_value == 4.0
    assert constraint.limit_value == 4.0


def test_build_construction_run_fails_closed_when_trade_intent_count_breaks_limit(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(max_trade_intent_count=3),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.final_target_weights == []
    assert [item.model_dump(mode="json") for item in result.trade_intents] == [
        {"symbol": "AAA", "action": "initiate", "current_weight": 0.0, "target_weight": 0.5, "delta_weight": 0.5},
        {"symbol": "BBB", "action": "buy", "current_weight": 0.4, "target_weight": 0.5, "delta_weight": 0.1},
        {"symbol": "CCC", "action": "exit", "current_weight": 0.35, "target_weight": 0.0, "delta_weight": -0.35},
        {"symbol": "EEE", "action": "exit", "current_weight": 0.25, "target_weight": 0.0, "delta_weight": -0.25},
    ]
    assert result.failure_reasons == ["trade intent count exceeds max_trade_intent_count"]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_trade_intent_count")
    assert constraint.status == "fail"
    assert constraint.actual_value == 4.0
    assert constraint.limit_value == 3.0
    assert result.deterministic_ordering.trade_symbols == ["AAA", "BBB", "CCC", "EEE"]


def test_build_construction_run_keeps_trade_intent_count_not_evaluated_for_other_infeasible_requests(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_trade_intent_count=5, min_position_weight=0.4),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.trade_intents == []
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_trade_intent_count")
    assert constraint.status == "not_evaluated"
    assert constraint.actual_value is None
    assert constraint.limit_value == 5.0
    assert constraint.message == "target trade intents were not persisted because the request is infeasible"


def test_build_construction_run_treats_omitted_and_explicit_null_turnover_caps_as_canonical_equivalents(tmp_path: Path) -> None:
    omitted = build_construction_run(
        _request(),
        artifact_store=ConstructionArtifactStore(str(tmp_path / "omitted")),
    )
    explicit_null = build_construction_run(
        _request(include_max_turnover_weight=True),
        artifact_store=ConstructionArtifactStore(str(tmp_path / "null")),
    )

    assert omitted.artifact_id == explicit_null.artifact_id
    assert omitted.fingerprint == explicit_null.fingerprint
    omitted_constraint = next(item for item in omitted.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    explicit_null_constraint = next(item for item in explicit_null.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert omitted_constraint.status == explicit_null_constraint.status == "not_evaluated"
    assert omitted_constraint.limit_value is None
    assert explicit_null_constraint.limit_value is None


def test_build_construction_run_treats_zero_turnover_cap_as_binding_when_no_turnover_is_required(tmp_path: Path) -> None:
    result = build_construction_run(
        ConstructionRunRequest.model_validate(
            {
                "request_id": "construction-zero-turnover-binding",
                "ranked_universe": {
                    "artifact_id": "ranking_artifact_1",
                    "ranking_id": "ranked_candidates_v1",
                    "methodology_id": "ranked_candidates_methodology_v1",
                    "as_of_date": "2026-04-23",
                    "ranked_candidates": [
                        {"symbol": "AAA", "rank": 1, "eligible": True, "score": 9.5},
                        {"symbol": "BBB", "rank": 2, "eligible": True, "score": 8.1},
                    ],
                },
                "current_portfolio": {
                    "artifact_id": "portfolio_snapshot_1",
                    "as_of_timestamp": "2026-04-23T09:30:00",
                    "weights": [
                        {"symbol": "AAA", "weight": 0.5},
                        {"symbol": "BBB", "weight": 0.5},
                    ],
                },
                "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
                "hard_constraints": {
                    "full_investment": True,
                    "long_only": True,
                    "eligible_ranked_universe_only": True,
                    "max_position_weight": 0.6,
                    "max_turnover_weight": 0.0,
                },
            }
        ),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert constraint.status == "binding"
    assert constraint.actual_value == 0.0
    assert constraint.limit_value == 0.0


def test_turnover_symbol_contributions_sum_to_reported_turnover_within_tolerance(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.55, policy_id="top_n_inverse_rank_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.turnover_diagnostics_v1 is not None
    contributions = result.turnover_diagnostics_v1.symbol_contributions
    assert round(sum(item.turnover_contribution_weight for item in contributions), 8) == result.turnover_diagnostics_v1.reported_turnover_weight
    assert round(sum((item.contribution_fraction_of_reported_turnover or 0.0) for item in contributions), 8) == 1.0


def test_turnover_symbol_contributions_emit_zero_for_unchanged_positions_and_minimal_output_behavior(tmp_path: Path) -> None:
    result = build_construction_run(
        ConstructionRunRequest.model_validate(
            {
                "request_id": "construction-zero-turnover-symbol-diagnostics",
                "ranked_universe": {
                    "artifact_id": "ranking_artifact_1",
                    "ranking_id": "ranked_candidates_v1",
                    "methodology_id": "ranked_candidates_methodology_v1",
                    "as_of_date": "2026-04-23",
                    "ranked_candidates": [
                        {"symbol": "AAA", "rank": 1, "eligible": True, "score": 9.5},
                    ],
                },
                "current_portfolio": {
                    "artifact_id": "portfolio_snapshot_1",
                    "as_of_timestamp": "2026-04-23T09:30:00",
                    "weights": [
                        {"symbol": "AAA", "weight": 1.0},
                    ],
                },
                "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 1},
                "hard_constraints": {
                    "full_investment": True,
                    "long_only": True,
                    "eligible_ranked_universe_only": True,
                    "max_position_weight": 1.0,
                    "max_turnover_weight": 0.0,
                },
            }
        ),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.turnover_diagnostics_v1 is not None
    assert result.turnover_diagnostics_v1.reported_turnover_weight == 0.0
    assert [item.model_dump(mode="json") for item in result.turnover_diagnostics_v1.symbol_contributions] == [
        {
            "symbol": "AAA",
            "action": "hold",
            "current_weight": 1.0,
            "target_weight": 1.0,
            "delta_weight": 0.0,
            "absolute_delta_weight": 0.0,
            "turnover_contribution_weight": 0.0,
            "contribution_fraction_of_reported_turnover": None,
            "included_in_reported_turnover": False,
        }
    ]


def test_turnover_symbol_contributions_reconcile_buys_sells_entries_exits_and_sign_conventions(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.turnover_diagnostics_v1 is not None
    assert [item.model_dump(mode="json") for item in result.turnover_diagnostics_v1.symbol_contributions] == [
        {
            "symbol": "AAA",
            "action": "initiate",
            "current_weight": 0.0,
            "target_weight": 0.5,
            "delta_weight": 0.5,
            "absolute_delta_weight": 0.5,
            "turnover_contribution_weight": 0.25,
            "contribution_fraction_of_reported_turnover": 0.41666667,
            "included_in_reported_turnover": True,
        },
        {
            "symbol": "BBB",
            "action": "buy",
            "current_weight": 0.4,
            "target_weight": 0.5,
            "delta_weight": 0.1,
            "absolute_delta_weight": 0.1,
            "turnover_contribution_weight": 0.05,
            "contribution_fraction_of_reported_turnover": 0.08333333,
            "included_in_reported_turnover": True,
        },
        {
            "symbol": "CCC",
            "action": "exit",
            "current_weight": 0.35,
            "target_weight": 0.0,
            "delta_weight": -0.35,
            "absolute_delta_weight": 0.35,
            "turnover_contribution_weight": 0.175,
            "contribution_fraction_of_reported_turnover": 0.29166667,
            "included_in_reported_turnover": True,
        },
        {
            "symbol": "EEE",
            "action": "exit",
            "current_weight": 0.25,
            "target_weight": 0.0,
            "delta_weight": -0.25,
            "absolute_delta_weight": 0.25,
            "turnover_contribution_weight": 0.125,
            "contribution_fraction_of_reported_turnover": 0.20833333,
            "included_in_reported_turnover": True,
        },
    ]


def test_build_construction_run_treats_zero_turnover_cap_as_real_limit_not_missing(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(max_turnover_weight=0.0),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.failure_reasons == ["target turnover exceeds max_turnover_weight"]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert constraint.status == "fail"
    assert constraint.actual_value == 0.6
    assert constraint.limit_value == 0.0


def test_build_construction_run_computes_turnover_over_symbol_union(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=1, max_position_weight=1.0, max_turnover_weight=1.0),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    assert [item.model_dump(mode="json") for item in result.trade_intents] == [
        {"symbol": "AAA", "action": "initiate", "current_weight": 0.0, "target_weight": 1.0, "delta_weight": 1.0},
        {"symbol": "BBB", "action": "exit", "current_weight": 0.4, "target_weight": 0.0, "delta_weight": -0.4},
        {"symbol": "CCC", "action": "exit", "current_weight": 0.35, "target_weight": 0.0, "delta_weight": -0.35},
        {"symbol": "EEE", "action": "exit", "current_weight": 0.25, "target_weight": 0.0, "delta_weight": -0.25},
    ]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert constraint.status == "binding"
    assert constraint.actual_value == 1.0
    assert constraint.limit_value == 1.0


def test_build_construction_run_persists_feasible_artifact_by_artifact_id(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))

    result = build_construction_run(_request(), artifact_store=store)

    persisted = load_construction_artifact(result.artifact_id, store=store)
    assert persisted == result
    assert (tmp_path / f"{result.artifact_id}.json").exists()


@pytest.mark.parametrize(
    "trace_mutator",
    [
        lambda payload: payload.pop("selection_rule_trace"),
        lambda payload: payload.update({"selection_rule_trace": None}),
        lambda payload: payload.update({"selection_rule_trace": {}}),
    ],
    ids=["missing", "null", "empty_object"],
)
def test_construction_artifact_schema_rejects_missing_or_malformed_empty_selection_trace_outside_load_boundary(
    tmp_path: Path,
    trace_mutator,
) -> None:
    artifact = build_construction_run(_request(), artifact_store=ConstructionArtifactStore(str(tmp_path)))
    payload = artifact.model_dump(mode="json")
    trace_mutator(payload)

    with pytest.raises(ValidationError):
        ConstructionArtifact.model_validate(payload)


def test_construction_artifact_schema_accepts_explicit_empty_selection_trace_outside_load_boundary(
    tmp_path: Path,
) -> None:
    artifact = build_construction_run(_request(), artifact_store=ConstructionArtifactStore(str(tmp_path)))
    payload = artifact.model_dump(mode="json")
    payload["selection_rule_trace"] = {"rule_ids": [], "steps": []}

    validated = ConstructionArtifact.model_validate(payload)

    assert validated.selection_rule_trace.model_dump(mode="json") == {"rule_ids": [], "steps": []}


@pytest.mark.parametrize(
    "trace_mutator",
    [
        lambda payload: payload.pop("selection_rule_trace"),
        lambda payload: payload.update({"selection_rule_trace": None}),
        lambda payload: payload.update({"selection_rule_trace": {}}),
    ],
    ids=["missing", "null", "empty_object"],
)
def test_load_construction_artifact_normalizes_legacy_empty_selection_trace_variants(
    tmp_path: Path,
    trace_mutator,
) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    original_path = tmp_path / f"{result.artifact_id}.json"
    payload = json.loads(original_path.read_text(encoding="utf-8"))
    trace_mutator(payload)
    payload_without_ids = {key: value for key, value in payload.items() if key not in {"artifact_id", "fingerprint"}}
    if payload_without_ids.get("selection_rule_trace") in (None, {}, {"rule_ids": [], "steps": []}):
        payload_without_ids.pop("selection_rule_trace", None)
    fingerprint = sha256(
        json.dumps(payload_without_ids, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    legacy_artifact_id = f"construction_artifact_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["artifact_id"] = legacy_artifact_id
    original_path.unlink()
    legacy_path = tmp_path / f"{legacy_artifact_id}.json"
    legacy_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    loaded = load_construction_artifact(legacy_artifact_id, store=store)

    assert loaded.selection_rule_trace.model_dump(mode="json") == {"rule_ids": [], "steps": []}


@pytest.mark.parametrize(
    ("fixture_name", "expected_selection_rule_trace"),
    [
        ("construction_artifact_legacy_missing_selection_rule_trace.json", {"rule_ids": [], "steps": []}),
        ("construction_artifact_legacy_null_selection_rule_trace.json", {"rule_ids": [], "steps": []}),
        ("construction_artifact_legacy_empty_selection_rule_trace.json", {"rule_ids": [], "steps": []}),
        ("construction_artifact_legacy_missing_policy_definition_id.json", None),
        ("construction_artifact_legacy_missing_max_turnover_weight.json", None),
        ("construction_artifact_reference.json", None),
    ],
    ids=[
        "missing_selection_rule_trace",
        "null_selection_rule_trace",
        "empty_selection_rule_trace",
        "missing_policy_definition_id",
        "missing_max_turnover_weight",
        "explicit_null_max_turnover_weight",
    ],
)
def test_load_construction_artifact_fixture_matrix_preserves_legacy_behavior(
    tmp_path: Path,
    fixture_name: str,
    expected_selection_rule_trace: dict | None,
) -> None:
    reference_store = ConstructionArtifactStore(str(tmp_path / "reference"))
    reference_artifact_id, _ = _persist_construction_artifact_fixture(
        tmp_path / "reference",
        "construction_artifact_reference.json",
    )
    reference = load_construction_artifact(reference_artifact_id, store=reference_store)

    store = ConstructionArtifactStore(str(tmp_path / "fixture"))
    artifact_id, _ = _persist_construction_artifact_fixture(tmp_path / "fixture", fixture_name)
    loaded = load_construction_artifact(artifact_id, store=store)

    assert loaded.artifact_id == artifact_id
    assert loaded.status == reference.status
    assert loaded.policy == reference.policy
    assert loaded.selected_names == reference.selected_names
    assert loaded.excluded_names == reference.excluded_names
    assert loaded.seed_weights == reference.seed_weights
    assert loaded.final_target_weights == reference.final_target_weights
    assert loaded.trade_intents == reference.trade_intents
    assert loaded.failure_reasons == reference.failure_reasons
    assert loaded.deterministic_ordering == reference.deterministic_ordering
    assert loaded.normalized_inputs.current_portfolio_weights == reference.normalized_inputs.current_portfolio_weights
    assert loaded.normalized_inputs.policy_definition_id == reference.normalized_inputs.policy_definition_id
    assert loaded.hard_constraints.max_turnover_weight is None
    assert next(
        item.model_dump(mode="json")
        for item in loaded.constraint_evaluations
        if item.constraint_id == "max_turnover_weight"
    ) == next(
        item.model_dump(mode="json")
        for item in reference.constraint_evaluations
        if item.constraint_id == "max_turnover_weight"
    )
    assert loaded.selection_rule_trace.model_dump(mode="json") == (
        expected_selection_rule_trace
        or reference.selection_rule_trace.model_dump(mode="json")
    )


@pytest.mark.parametrize(
    "fixture_name",
    [
        "construction_artifact_malformed_partial_selection_trace_missing_rule_ids.json",
        "construction_artifact_malformed_partial_selection_trace_empty_rule_ids.json",
    ],
    ids=["missing_rule_ids", "empty_rule_ids"],
)
def test_load_construction_artifact_fixture_matrix_rejects_partial_malformed_selection_trace(
    tmp_path: Path,
    fixture_name: str,
) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    artifact_id, _ = _persist_construction_artifact_fixture(tmp_path, fixture_name)

    with pytest.raises(
        ConstructionArtifactSchemaValidationError,
        match="persisted construction artifact failed schema validation",
    ):
        load_construction_artifact(artifact_id, store=store)


@pytest.mark.parametrize(
    "selection_rule_trace",
    [
        {
            "steps": [
                {
                    "rule_id": "eligible_only",
                    "rule_order": 1,
                    "input_candidate_symbols": ["AAA", "BBB", "CCC", "DDD"],
                    "output_candidate_symbols": ["AAA", "BBB", "CCC"],
                }
            ]
        },
        {
            "rule_ids": [],
            "steps": [
                {
                    "rule_id": "eligible_only",
                    "rule_order": 1,
                    "input_candidate_symbols": ["AAA", "BBB", "CCC", "DDD"],
                    "output_candidate_symbols": ["AAA", "BBB", "CCC"],
                }
            ],
        },
    ],
    ids=["missing_rule_ids", "empty_rule_ids"],
)
def test_load_construction_artifact_rejects_partial_malformed_selection_trace(
    tmp_path: Path,
    selection_rule_trace: dict,
) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["selection_rule_trace"] = selection_rule_trace
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(
        ConstructionArtifactSchemaValidationError,
        match="persisted construction artifact failed schema validation",
    ):
        load_construction_artifact(result.artifact_id, store=store)


def test_build_construction_run_fails_closed_when_equal_weight_breaks_max_position_constraint(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=2, max_position_weight=0.49),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.final_target_weights == []
    assert result.trade_intents == []
    assert result.failure_reasons == ["equal-weight seed exceeds max_position_weight"]
    assert result.selection_rule_trace.rule_ids == ["eligible_only", "take_top_n"]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_position_weight")
    assert constraint.status == "fail"
    assert constraint.actual_value == 0.5
    assert constraint.limit_value == 0.49


def test_build_construction_run_fails_closed_when_inverse_rank_weight_breaks_max_position_constraint(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.54, policy_id="top_n_inverse_rank_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.final_target_weights == []
    assert result.trade_intents == []
    assert result.failure_reasons == ["inverse-rank seed exceeds max_position_weight"]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_position_weight")
    assert constraint.status == "fail"
    assert constraint.actual_value == 0.54545455
    assert constraint.limit_value == 0.54


def test_build_construction_run_fails_closed_when_linear_rank_weight_breaks_max_position_constraint(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.49, policy_id="top_n_linear_rank_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.final_target_weights == []
    assert result.trade_intents == []
    assert result.failure_reasons == ["linear-rank seed exceeds max_position_weight"]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_position_weight")
    assert constraint.status == "fail"
    assert constraint.actual_value == 0.5
    assert constraint.limit_value == 0.49


def test_build_construction_run_fails_closed_when_eligible_ranked_universe_is_too_small(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=4, max_position_weight=0.5),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.failure_reasons == ["eligible ranked universe has fewer names than requested top_n"]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "eligible_ranked_universe_only")
    assert constraint.status == "fail"


def test_build_construction_run_applies_selection_rules_in_order(tmp_path: Path) -> None:
    request = ConstructionRunRequest.model_validate(
        {
            "request_id": "construction-rule-ordering",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "aaa", "rank": 1, "eligible": False, "score": 9.9, "exclusion_reason": "screened_out"},
                    {"symbol": "bbb", "rank": 2, "eligible": True, "score": 9.5},
                    {"symbol": "ccc", "rank": 3, "eligible": True, "score": 9.1},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "bbb", "weight": 0.5},
                    {"symbol": "ccc", "weight": 0.5},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        }
    )

    result = build_construction_run(request, artifact_store=ConstructionArtifactStore(str(tmp_path)))

    assert result.status == "feasible"
    assert [item.symbol for item in result.selected_names] == ["BBB", "CCC"]
    assert [item.model_dump(mode="json") for item in result.excluded_names] == [
        {"symbol": "AAA", "rank": 1, "eligible": False, "reason": "screened_out"},
    ]
    assert result.selection_rule_trace.model_dump(mode="json") == {
        "rule_ids": ["eligible_only", "take_top_n"],
        "steps": [
            {
                "rule_id": "eligible_only",
                "rule_order": 1,
                "input_candidate_symbols": ["AAA", "BBB", "CCC"],
                "output_candidate_symbols": ["BBB", "CCC"],
            },
            {
                "rule_id": "take_top_n",
                "rule_order": 2,
                "input_candidate_symbols": ["BBB", "CCC"],
                "output_candidate_symbols": ["BBB", "CCC"],
            },
        ],
    }


def test_build_construction_run_matches_legacy_top_n_equal_weight_selection(tmp_path: Path) -> None:
    request = ConstructionRunRequest.model_validate(
        {
            "request_id": "construction-legacy-equivalence",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "ccc", "rank": 3, "eligible": True, "score": 7.0},
                    {"symbol": "bbb", "rank": 2, "eligible": True, "score": 8.1},
                    {"symbol": "aaa", "rank": 1, "eligible": True, "score": 9.5},
                    {"symbol": "bbb", "rank": 9, "eligible": False, "score": 0.1, "exclusion_reason": "duplicate_later"},
                    {"symbol": "ddd", "rank": 4, "eligible": False, "score": 6.5, "exclusion_reason": "liquidity_screen"},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [
                    {"symbol": "bbb", "weight": 0.4},
                    {"symbol": "ccc", "weight": 0.35},
                    {"symbol": "eee", "weight": 0.25},
                ],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 0.6,
            },
        }
    )

    result = build_construction_run(request, artifact_store=ConstructionArtifactStore(str(tmp_path)))
    normalized_ranked = result.normalized_inputs.ranked_candidates
    legacy_selected = [candidate for candidate in normalized_ranked if candidate.eligible][: request.policy.top_n]
    legacy_selected_symbols = [candidate.symbol for candidate in legacy_selected]
    legacy_excluded = [
        {
            "symbol": candidate.symbol,
            "rank": candidate.rank,
            "eligible": candidate.eligible,
            "reason": candidate.exclusion_reason or "not selected by top_n_equal_weight_v1 cutoff",
        }
        for candidate in normalized_ranked
        if candidate.symbol not in set(legacy_selected_symbols)
    ]

    assert result.status == "feasible"
    assert [item.symbol for item in result.selected_names] == legacy_selected_symbols
    assert [item.model_dump(mode="json") for item in result.excluded_names] == legacy_excluded
    assert [item.model_dump(mode="json") for item in result.final_target_weights] == [
        {"symbol": "AAA", "weight": 0.5},
        {"symbol": "BBB", "weight": 0.5},
    ]


def test_handoff_backed_construction_run_matches_inline_construction_outputs(tmp_path: Path) -> None:
    artifact = _persisted_etf_ranking_artifact_for_construction()
    inline_request = _inline_request_from_etf_ranking_artifact(artifact)
    handoff = EtfRankingArtifactConstructionHandoff(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
    )
    handoff_request = build_construction_run_request_from_ranking_artifact_handoff(
        request_id=inline_request.request_id,
        handoff=handoff,
        artifact=artifact,
        current_portfolio=inline_request.current_portfolio,
        policy=inline_request.policy,
        hard_constraints=inline_request.hard_constraints,
    )

    inline_result = build_construction_run(inline_request, artifact_store=ConstructionArtifactStore(str(tmp_path / "inline")))
    handoff_result = build_construction_run(handoff_request, artifact_store=ConstructionArtifactStore(str(tmp_path / "handoff")))

    assert [item.model_dump(mode="json") for item in handoff_result.selected_names] == [
        item.model_dump(mode="json") for item in inline_result.selected_names
    ]
    assert [item.model_dump(mode="json") for item in handoff_result.final_target_weights] == [
        item.model_dump(mode="json") for item in inline_result.final_target_weights
    ]
    assert [item.model_dump(mode="json") for item in handoff_result.constraint_evaluations] == [
        item.model_dump(mode="json") for item in inline_result.constraint_evaluations
    ]
    assert handoff_result.status == inline_result.status


def test_etf_construction_preflight_returns_ineligible_response_for_valid_but_empty_ranked_universe() -> None:
    artifact = _persisted_etf_ranking_artifact_for_construction().model_copy(update={"ranked_universe": []})

    response = build_construction_preflight_response_from_etf_ranking_artifact(artifact)

    assert response.artifact.artifact_kind == "etf_ranking"
    assert response.eligibility.model_dump(mode="json") == {
        "eligible": False,
        "reason": "persisted etf ranking artifact has no eligible ranked candidates for construction",
    }
    assert response.handoff is None


def test_replacement_construction_preflight_returns_ineligible_response_for_valid_but_empty_ranked_candidates() -> None:
    artifact = _persisted_replacement_ranking_artifact_for_construction().model_copy(
        update={"ranked_candidates": []}
    )

    response = build_construction_preflight_response_from_replacement_ranking_artifact(artifact)

    assert response.artifact.artifact_kind == "intent_bound_etf_replacement_ranking"
    assert response.eligibility.model_dump(mode="json") == {
        "eligible": False,
        "reason": "persisted replacement ranking artifact has no eligible ranked candidates for construction",
    }
    assert response.handoff is None


def test_handoff_backed_construction_run_persists_authoritative_ranking_provenance(tmp_path: Path) -> None:
    artifact = _persisted_etf_ranking_artifact_for_construction()
    inline_request = _inline_request_from_etf_ranking_artifact(artifact)
    handoff_request = build_construction_run_request_from_ranking_artifact_handoff(
        request_id=inline_request.request_id,
        handoff=EtfRankingArtifactConstructionHandoff(
            artifact_id=artifact.artifact_id,
            ranking_id=artifact.ranking_id,
            methodology_id=artifact.run_metadata.methodology_id,
            as_of_date=artifact.run_metadata.as_of_date,
        ),
        artifact=artifact,
        current_portfolio=inline_request.current_portfolio,
        policy=inline_request.policy,
        hard_constraints=inline_request.hard_constraints,
    )

    result = build_construction_run(handoff_request, artifact_store=ConstructionArtifactStore(str(tmp_path)))

    assert result.normalized_inputs.ranked_universe_artifact_kind == "etf_ranking"
    assert result.normalized_inputs.ranked_universe_artifact_id == artifact.artifact_id
    assert result.normalized_inputs.ranked_universe_artifact_schema_version == "etf_ranking_artifact_v1"
    assert result.normalized_inputs.ranking_id == artifact.ranking_id
    assert result.normalized_inputs.ranking_methodology_id == artifact.run_metadata.methodology_id
    assert result.normalized_inputs.ranking_as_of_date == artifact.run_metadata.as_of_date
    assert result.normalized_inputs.current_portfolio_artifact_id == inline_request.current_portfolio.artifact_id
    assert result.normalized_inputs.current_portfolio_as_of_timestamp == inline_request.current_portfolio.as_of_timestamp


def test_handoff_backed_construction_run_request_fails_closed_when_top_n_is_outside_launch_boundary() -> None:
    artifact = _persisted_etf_ranking_artifact_for_construction()
    current_portfolio, _, hard_constraints = _handoff_supporting_inputs(artifact)

    with pytest.raises(
        ValueError,
        match="ranking artifact handoff launch requires policy.top_n=2 for the shipped desktop boundary",
    ):
        build_construction_run_request_from_ranking_artifact_handoff(
            request_id="construction-handoff-invalid-top-n",
            handoff=EtfRankingArtifactConstructionHandoff(
                artifact_id=artifact.artifact_id,
                ranking_id=artifact.ranking_id,
                methodology_id=artifact.run_metadata.methodology_id,
                as_of_date=artifact.run_metadata.as_of_date,
            ),
            artifact=artifact,
            current_portfolio=current_portfolio,
            policy=ConstructionPolicyInput(policy_id="top_n_equal_weight_v1", top_n=3),
            hard_constraints=hard_constraints,
        )


def test_replacement_handoff_backed_construction_run_matches_inline_construction_outputs(tmp_path: Path) -> None:
    artifact = _persisted_replacement_ranking_artifact_for_construction()
    inline_request = _inline_request_from_replacement_ranking_artifact(artifact)
    handoff = IntentBoundEtfReplacementRankingArtifactConstructionHandoff(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
    )
    handoff_request = build_construction_run_request_from_ranking_artifact_handoff(
        request_id=inline_request.request_id,
        handoff=handoff,
        artifact=artifact,
        current_portfolio=inline_request.current_portfolio,
        policy=inline_request.policy,
        hard_constraints=inline_request.hard_constraints,
    )

    inline_result = build_construction_run(inline_request, artifact_store=ConstructionArtifactStore(str(tmp_path / "inline-replacement")))
    handoff_result = build_construction_run(handoff_request, artifact_store=ConstructionArtifactStore(str(tmp_path / "handoff-replacement")))

    assert [item.model_dump(mode="json") for item in handoff_result.selected_names] == [
        item.model_dump(mode="json") for item in inline_result.selected_names
    ]
    assert [item.model_dump(mode="json") for item in handoff_result.final_target_weights] == [
        item.model_dump(mode="json") for item in inline_result.final_target_weights
    ]
    assert [item.model_dump(mode="json") for item in handoff_result.constraint_evaluations] == [
        item.model_dump(mode="json") for item in inline_result.constraint_evaluations
    ]
    assert handoff_result.status == inline_result.status


def test_replacement_handoff_backed_construction_run_persists_authoritative_ranking_provenance(tmp_path: Path) -> None:
    artifact = _persisted_replacement_ranking_artifact_for_construction()
    inline_request = _inline_request_from_replacement_ranking_artifact(artifact)
    handoff_request = build_construction_run_request_from_ranking_artifact_handoff(
        request_id=inline_request.request_id,
        handoff=IntentBoundEtfReplacementRankingArtifactConstructionHandoff(
            artifact_id=artifact.artifact_id,
            ranking_id=artifact.ranking_id,
            methodology_id=artifact.run_metadata.methodology_id,
            as_of_date=artifact.run_metadata.as_of_date,
        ),
        artifact=artifact,
        current_portfolio=inline_request.current_portfolio,
        policy=inline_request.policy,
        hard_constraints=inline_request.hard_constraints,
    )

    result = build_construction_run(handoff_request, artifact_store=ConstructionArtifactStore(str(tmp_path)))

    assert result.normalized_inputs.ranked_universe_artifact_kind == "intent_bound_etf_replacement_ranking"
    assert result.normalized_inputs.ranked_universe_artifact_id == artifact.artifact_id
    assert result.normalized_inputs.ranked_universe_artifact_schema_version == "intent_bound_etf_replacement_ranking_artifact_v1"
    assert result.normalized_inputs.ranking_id == artifact.ranking_id
    assert result.normalized_inputs.ranking_methodology_id == artifact.run_metadata.methodology_id
    assert result.normalized_inputs.ranking_as_of_date == artifact.run_metadata.as_of_date
    assert result.normalized_inputs.current_portfolio_artifact_id == inline_request.current_portfolio.artifact_id
    assert result.normalized_inputs.current_portfolio_as_of_timestamp == inline_request.current_portfolio.as_of_timestamp


@pytest.mark.parametrize(
    ("field_name", "expected_detail"),
    [
        (
            "artifact_id",
            "ranking artifact handoff requests require current_portfolio.artifact_id",
        ),
        (
            "as_of_timestamp",
            "ranking artifact handoff requests require current_portfolio.as_of_timestamp",
        ),
    ],
)
def test_build_construction_run_request_from_ranking_artifact_handoff_requires_authoritative_current_portfolio_identity(
    field_name: str,
    expected_detail: str,
) -> None:
    artifact = _persisted_etf_ranking_artifact_for_construction()
    current_portfolio, policy, hard_constraints = _handoff_supporting_inputs(artifact)
    handoff = EtfRankingArtifactConstructionHandoff(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
    )
    invalid_current_portfolio = current_portfolio.model_copy(update={field_name: None})

    with pytest.raises(ValueError, match=expected_detail):
        build_construction_run_request_from_ranking_artifact_handoff(
            request_id="construction-handoff-missing-current-portfolio-lineage",
            handoff=handoff,
            artifact=artifact,
            current_portfolio=invalid_current_portfolio,
            policy=policy,
            hard_constraints=hard_constraints,
        )


@pytest.mark.parametrize(
    ("scenario", "artifact_mutator", "expected_detail"),
    [
        (
            "unsupported_persisted_schema_version",
            lambda artifact: artifact.model_copy(update={"schema_version": "intent_bound_etf_replacement_ranking_artifact_v0"}),
            "unsupported replacement ranking schema_version",
        ),
        (
            "persisted_artifact_identity_integrity_mismatch",
            lambda artifact: artifact.model_copy(update={"artifact_id": "intent_bound_etf_replacement_ranking_artifact_other"}),
            "ranking artifact handoff artifact_id does not match persisted artifact",
        ),
        (
            "persisted_construction_unusable_empty_ranked_candidates",
            lambda artifact: artifact.model_copy(update={"ranked_candidates": []}),
            "persisted replacement ranking artifact has no eligible ranked candidates for construction",
        ),
        (
            "persisted_construction_unusable_missing_rank",
            lambda artifact: artifact.model_copy(
                update={
                    "ranked_candidates": [
                        artifact.ranked_candidates[0].model_copy(update={"rank": None}),
                        *artifact.ranked_candidates[1:],
                    ]
                }
            ),
            "replacement ranking candidate rank is required for construction",
        ),
    ],
)
def test_build_construction_run_request_from_replacement_ranking_artifact_handoff_fails_closed_for_invalid_persisted_states(
    scenario: str,
    artifact_mutator,
    expected_detail: str,
) -> None:
    artifact = _persisted_replacement_ranking_artifact_for_construction()
    inline_request = _inline_request_from_replacement_ranking_artifact(artifact)
    handoff = IntentBoundEtfReplacementRankingArtifactConstructionHandoff(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
    )
    mutated_artifact = artifact_mutator(artifact)

    with pytest.raises(ValueError, match=expected_detail):
        build_construction_run_request_from_ranking_artifact_handoff(
            request_id=f"construction-replacement-handoff-fail-closed-{scenario}",
            handoff=handoff,
            artifact=mutated_artifact,
            current_portfolio=inline_request.current_portfolio,
            policy=inline_request.policy,
            hard_constraints=inline_request.hard_constraints,
        )


def test_build_construction_run_request_from_replacement_ranking_artifact_handoff_keeps_valid_persisted_state_unchanged() -> None:
    artifact = _persisted_replacement_ranking_artifact_for_construction()
    inline_request = _inline_request_from_replacement_ranking_artifact(artifact)
    handoff = IntentBoundEtfReplacementRankingArtifactConstructionHandoff(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
    )

    request = build_construction_run_request_from_ranking_artifact_handoff(
        request_id="construction-replacement-handoff-valid-state",
        handoff=handoff,
        artifact=artifact,
        current_portfolio=inline_request.current_portfolio,
        policy=inline_request.policy,
        hard_constraints=inline_request.hard_constraints,
    )

    assert request.ranking_artifact_handoff == handoff
    assert request.ranked_universe is not None
    assert request.ranked_universe.artifact_id == artifact.artifact_id
    assert request.ranked_universe.ranking_id == artifact.ranking_id
    assert request.ranked_universe.methodology_id == artifact.run_metadata.methodology_id
    assert request.ranked_universe.as_of_date == artifact.run_metadata.as_of_date
    assert [candidate.model_dump(mode="json") for candidate in request.ranked_universe.ranked_candidates] == [
        {
            "symbol": row.symbol,
            "rank": row.rank,
            "eligible": True,
            "score": row.composite_score,
            "exclusion_reason": row.exclusion_reason,
        }
        for row in artifact.ranked_candidates
    ]


@pytest.mark.parametrize(
    ("scenario", "artifact_mutator", "expected_detail"),
    [
        (
            "unsupported_persisted_schema_version",
            lambda artifact: artifact.model_copy(update={"schema_version": "etf_ranking_artifact_v0"}),
            "unsupported etf ranking schema_version",
        ),
        (
            "persisted_artifact_identity_integrity_mismatch",
            lambda artifact: artifact.model_copy(update={"artifact_id": "etf_ranking_artifact_other"}),
            "ranking artifact handoff artifact_id does not match persisted artifact",
        ),
        (
            "persisted_construction_unusable_empty_ranked_universe",
            lambda artifact: artifact.model_copy(update={"ranked_universe": []}),
            "persisted etf ranking artifact has no eligible ranked candidates for construction",
        ),
    ],
)
def test_build_construction_run_request_from_ranking_artifact_handoff_fails_closed_for_invalid_persisted_states(
    scenario: str,
    artifact_mutator,
    expected_detail: str,
) -> None:
    artifact = _persisted_etf_ranking_artifact_for_construction()
    current_portfolio, policy, hard_constraints = _handoff_supporting_inputs(artifact)
    handoff = EtfRankingArtifactConstructionHandoff(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
    )
    mutated_artifact = artifact_mutator(artifact)

    with pytest.raises(ValueError, match=expected_detail):
        build_construction_run_request_from_ranking_artifact_handoff(
            request_id=f"construction-handoff-fail-closed-{scenario}",
            handoff=handoff,
            artifact=mutated_artifact,
            current_portfolio=current_portfolio,
            policy=policy,
            hard_constraints=hard_constraints,
        )


def test_build_construction_run_request_from_ranking_artifact_handoff_keeps_valid_persisted_state_unchanged() -> None:
    artifact = _persisted_etf_ranking_artifact_for_construction()
    current_portfolio, policy, hard_constraints = _handoff_supporting_inputs(artifact)
    handoff = EtfRankingArtifactConstructionHandoff(
        artifact_id=artifact.artifact_id,
        ranking_id=artifact.ranking_id,
        methodology_id=artifact.run_metadata.methodology_id,
        as_of_date=artifact.run_metadata.as_of_date,
    )

    request = build_construction_run_request_from_ranking_artifact_handoff(
        request_id="construction-handoff-valid-state",
        handoff=handoff,
        artifact=artifact,
        current_portfolio=current_portfolio,
        policy=policy,
        hard_constraints=hard_constraints,
    )

    assert request.ranking_artifact_handoff == handoff
    assert request.ranked_universe is not None
    assert request.ranked_universe.artifact_id == artifact.artifact_id
    assert request.ranked_universe.ranking_id == artifact.ranking_id
    assert request.ranked_universe.methodology_id == artifact.run_metadata.methodology_id
    assert request.ranked_universe.as_of_date == artifact.run_metadata.as_of_date
    assert [candidate.model_dump(mode="json") for candidate in request.ranked_universe.ranked_candidates] == [
        {
            "symbol": row.symbol,
            "rank": row.rank,
            "eligible": True,
            "score": row.composite_score,
            "exclusion_reason": None,
        }
        for row in artifact.ranked_universe
    ]


def test_build_construction_run_keeps_equal_weight_policy_weights_unchanged_after_weighting_refactor(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.34, policy_id="top_n_equal_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    assert [item.model_dump(mode="json") for item in result.final_target_weights] == [
        {"symbol": "AAA", "weight": 0.33333333},
        {"symbol": "BBB", "weight": 0.33333333},
        {"symbol": "CCC", "weight": 0.33333334},
    ]
    assert next(item for item in result.constraint_evaluations if item.constraint_id == "max_position_weight").status == "pass"


def test_build_construction_run_uses_catalog_owned_selection_rule_order_and_cutoff_message(tmp_path: Path, monkeypatch) -> None:
    original_definition = construction_policy_catalog.get_construction_policy_definition("top_n_equal_weight_v1")
    assert original_definition is not None
    monkeypatch.setitem(
        construction_policy_catalog._POLICY_BY_ID,
        "top_n_equal_weight_v1",
        replace(
            original_definition,
            catalog_entry=original_definition.catalog_entry.model_copy(
                update={"selection_rule_ids": ["take_top_n", "eligible_only"]}
            ),
            cutoff_exclusion_reason="catalog-owned cutoff message",
        ),
    )
    request = ConstructionRunRequest.model_validate(
        {
            "request_id": "construction-catalog-owned-selection",
            "ranked_universe": {
                "artifact_id": "ranking_artifact_1",
                "ranking_id": "ranked_candidates_v1",
                "methodology_id": "ranked_candidates_methodology_v1",
                "as_of_date": "2026-04-23",
                "ranked_candidates": [
                    {"symbol": "aaa", "rank": 1, "eligible": False, "score": 9.9, "exclusion_reason": "screened_out"},
                    {"symbol": "bbb", "rank": 2, "eligible": True, "score": 9.5},
                    {"symbol": "ccc", "rank": 3, "eligible": True, "score": 9.1},
                ],
            },
            "current_portfolio": {
                "artifact_id": "portfolio_snapshot_1",
                "as_of_timestamp": "2026-04-23T09:30:00",
                "weights": [{"symbol": "bbb", "weight": 1.0}],
            },
            "policy": {"policy_id": "top_n_equal_weight_v1", "top_n": 2},
            "hard_constraints": {
                "full_investment": True,
                "long_only": True,
                "eligible_ranked_universe_only": True,
                "max_position_weight": 1.0,
            },
        }
    )

    result = build_construction_run(request, artifact_store=ConstructionArtifactStore(str(tmp_path)))

    assert result.status == "infeasible"
    assert [item.symbol for item in result.selected_names] == ["BBB"]
    assert result.selection_rule_trace.model_dump(mode="json") == {
        "rule_ids": ["take_top_n", "eligible_only"],
        "steps": [
            {
                "rule_id": "take_top_n",
                "rule_order": 1,
                "input_candidate_symbols": ["AAA", "BBB", "CCC"],
                "output_candidate_symbols": ["AAA", "BBB"],
            },
            {
                "rule_id": "eligible_only",
                "rule_order": 2,
                "input_candidate_symbols": ["AAA", "BBB"],
                "output_candidate_symbols": ["BBB"],
            },
        ],
    }
    assert [item.model_dump(mode="json") for item in result.excluded_names] == [
        {"symbol": "AAA", "rank": 1, "eligible": False, "reason": "screened_out"},
        {"symbol": "CCC", "rank": 3, "eligible": True, "reason": "catalog-owned cutoff message"},
    ]


def test_build_construction_run_uses_catalog_owned_weighting_and_failure_message(tmp_path: Path, monkeypatch) -> None:
    original_definition = construction_policy_catalog.get_construction_policy_definition("top_n_equal_weight_v1")
    assert original_definition is not None
    monkeypatch.setitem(
        construction_policy_catalog._POLICY_BY_ID,
        "top_n_equal_weight_v1",
        replace(
            original_definition,
            max_position_failure_reason="catalog-owned max position failure",
            raw_weight_numerator_builder=lambda selected_count: [Fraction(3, 1)] + [Fraction(1, 1)] * (selected_count - 1),
        ),
    )

    result = build_construction_run(
        _request(top_n=2, max_position_weight=0.7),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "infeasible"
    assert result.failure_reasons == ["catalog-owned max position failure"]
    constraint = next(item for item in result.constraint_evaluations if item.constraint_id == "max_position_weight")
    assert constraint.status == "fail"
    assert constraint.actual_value == 0.75
    assert constraint.limit_value == 0.7


def test_build_construction_run_persists_infeasible_artifact_when_output_is_valid(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))

    result = build_construction_run(_request(top_n=4, max_position_weight=0.5), artifact_store=store)

    persisted = load_construction_artifact(result.artifact_id, store=store)
    assert persisted.status == "infeasible"
    assert persisted == result


def test_build_construction_run_does_not_persist_malformed_request(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    request = _request()
    request.current_portfolio.weights[0] = request.current_portfolio.weights[0].model_copy(update={"weight": 0.9})

    with pytest.raises(ValueError, match="current_portfolio.weights must sum to 1.0"):
        build_construction_run(request, artifact_store=store)

    assert list(tmp_path.iterdir()) == []


def test_build_construction_run_fails_closed_without_persisting_when_catalog_policy_resolution_is_unavailable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    monkeypatch.delitem(construction_policy_catalog._POLICY_BY_ID, "top_n_equal_weight_v1")

    with pytest.raises(ValueError, match="unsupported construction policy: top_n_equal_weight_v1"):
        build_construction_run(_request(), artifact_store=store)

    assert list(tmp_path.iterdir()) == []


def test_build_construction_run_changes_canonical_fingerprint_when_policy_definition_provenance_changes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    baseline = build_construction_run(_request(), artifact_store=store)
    original_definition = construction_policy_catalog.get_construction_policy_definition("top_n_equal_weight_v1")
    assert original_definition is not None
    monkeypatch.setitem(
        construction_policy_catalog._POLICY_BY_ID,
        "top_n_equal_weight_v1",
        replace(
            original_definition,
            catalog_entry=original_definition.catalog_entry.model_copy(
                update={"policy_definition_id": "construction_policy_definition_top_n_inverse_rank_weight_v1"}
            ),
        ),
    )

    updated = build_construction_run(_request(), artifact_store=ConstructionArtifactStore(str(tmp_path / "alt")))

    assert baseline.final_target_weights == updated.final_target_weights
    assert baseline.fingerprint != updated.fingerprint
    assert baseline.artifact_id != updated.artifact_id


def test_list_construction_policies_fails_closed_when_canonical_launch_profile_has_multiple_defaults(monkeypatch) -> None:
    original_definition = construction_policy_catalog.get_construction_policy_definition("top_n_linear_rank_weight_v1")
    assert original_definition is not None
    monkeypatch.setitem(
        construction_policy_catalog._POLICY_BY_ID,
        "top_n_linear_rank_weight_v1",
        replace(
            original_definition,
            catalog_entry=original_definition.catalog_entry.model_copy(
                update={
                    "launch_profile": original_definition.catalog_entry.launch_profile.model_copy(
                        update={"policy_status": "default"}
                    )
                }
            ),
        ),
    )
    monkeypatch.setattr(
        construction_policy_catalog,
        "POLICY_CATALOG",
        tuple(construction_policy_catalog._POLICY_BY_ID[policy_id] for policy_id in [
            "top_n_equal_weight_v1",
            "top_n_inverse_rank_weight_v1",
            "top_n_linear_rank_weight_v1",
        ]),
    )

    with pytest.raises(
        ValueError,
        match="construction policy catalog must define exactly one default launch policy for ranking-artifact review handoff",
    ):
        construction_policy_catalog.list_construction_policies()


def test_list_construction_policies_fails_closed_when_launch_profile_metadata_disagrees_with_policy_identity(monkeypatch) -> None:
    original_definition = construction_policy_catalog.get_construction_policy_definition("top_n_linear_rank_weight_v1")
    assert original_definition is not None
    monkeypatch.setitem(
        construction_policy_catalog._POLICY_BY_ID,
        "top_n_linear_rank_weight_v1",
        replace(
            original_definition,
            catalog_entry=original_definition.catalog_entry.model_copy(update={"ranking_support": "selection_only"}),
        ),
    )
    monkeypatch.setattr(
        construction_policy_catalog,
        "POLICY_CATALOG",
        tuple(construction_policy_catalog._POLICY_BY_ID[policy_id] for policy_id in [
            "top_n_equal_weight_v1",
            "top_n_inverse_rank_weight_v1",
            "top_n_linear_rank_weight_v1",
        ]),
    )

    with pytest.raises(
        ValueError,
        match="construction policy top_n_linear_rank_weight_v1 launch profile metadata disagrees with ranking_support",
    ):
        construction_policy_catalog.list_construction_policies()


def test_load_construction_artifact_rejects_corrupted_payload(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "construction_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ConstructionArtifactIntegrityValidationError, match="artifact_id does not match canonical artifact content"):
        load_construction_artifact(result.artifact_id, store=store)


def test_load_construction_artifact_rejects_policy_definition_id_mismatch(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["normalized_inputs"]["policy_definition_id"] = "construction_policy_definition_top_n_inverse_rank_weight_v1"
    payload_without_ids = {key: value for key, value in payload.items() if key not in {"artifact_id", "fingerprint"}}
    fingerprint = sha256(
        json.dumps(payload_without_ids, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    artifact_id = f"construction_artifact_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["artifact_id"] = artifact_id
    artifact_path.unlink()
    artifact_path = tmp_path / f"{artifact_id}.json"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(
        ConstructionArtifactSchemaValidationError,
        match="persisted construction artifact failed schema validation",
    ):
        load_construction_artifact(artifact_id, store=store)


def test_load_construction_artifact_hydrates_missing_legacy_policy_definition_id(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    legacy_artifact_id, legacy_payload = _rewrite_artifact_with_rekeyed_payload(
        tmp_path,
        result.artifact_id,
        lambda payload: payload["normalized_inputs"].pop("policy_definition_id"),
    )

    loaded = load_construction_artifact(legacy_artifact_id, store=store)

    assert loaded.artifact_id == legacy_artifact_id
    assert loaded.fingerprint == legacy_payload["fingerprint"]
    assert loaded.normalized_inputs.policy_definition_id == "construction_policy_definition_top_n_equal_weight_v1"


def test_load_construction_artifact_hydrates_missing_legacy_weighting_trace_with_explicit_unavailable_status(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    legacy_artifact_id, legacy_payload = _rewrite_artifact_with_rekeyed_payload(
        tmp_path,
        result.artifact_id,
        lambda payload: (payload.pop("weighting_trace_status"), payload.pop("weighting_trace_v1")),
    )

    loaded = load_construction_artifact(legacy_artifact_id, store=store)

    assert loaded.artifact_id == legacy_artifact_id
    assert loaded.fingerprint == legacy_payload["fingerprint"]
    assert loaded.weighting_trace_status == "unavailable_legacy_artifact"
    assert loaded.weighting_trace_v1 is None


def test_load_construction_artifact_hydrates_missing_legacy_turnover_diagnostics_with_explicit_unavailable_status(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    legacy_artifact_id, legacy_payload = _rewrite_artifact_with_rekeyed_payload(
        tmp_path,
        result.artifact_id,
        lambda payload: (payload.pop("turnover_diagnostics_status"), payload.pop("turnover_diagnostics_v1")),
    )

    loaded = load_construction_artifact(legacy_artifact_id, store=store)

    assert loaded.artifact_id == legacy_artifact_id
    assert loaded.fingerprint == legacy_payload["fingerprint"]
    assert loaded.turnover_diagnostics_status == "unavailable_legacy_artifact"
    assert loaded.turnover_diagnostics_v1 is None


def test_load_construction_artifact_hydrates_missing_legacy_max_trade_intent_count_fields(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    legacy_artifact_id, legacy_payload = _rewrite_artifact_with_rekeyed_payload(
        tmp_path,
        result.artifact_id,
        lambda payload: (
            payload["hard_constraints"].pop("max_trade_intent_count", None),
            payload["normalized_inputs"].pop("max_trade_intent_count", None),
            payload.__setitem__(
                "constraint_evaluations",
                [
                    item
                    for item in payload["constraint_evaluations"]
                    if item["constraint_id"] != "max_trade_intent_count"
                ],
            ),
        ),
    )

    loaded = load_construction_artifact(legacy_artifact_id, store=store)

    assert loaded.artifact_id == legacy_artifact_id
    assert loaded.fingerprint == legacy_payload["fingerprint"]
    assert loaded.hard_constraints.max_trade_intent_count is None
    assert loaded.normalized_inputs.max_trade_intent_count is None
    constraint = next(item for item in loaded.constraint_evaluations if item.constraint_id == "max_trade_intent_count")
    assert constraint.model_dump(mode="json") == {
        "constraint_id": "max_trade_intent_count",
        "status": "not_evaluated",
        "actual_value": None,
        "limit_value": None,
        "message": "max_trade_intent_count was not requested",
    }


@pytest.mark.parametrize(
    "turnover_mutator",
    [
        lambda payload: payload["hard_constraints"].pop("max_turnover_weight", None),
        lambda payload: payload["hard_constraints"].__setitem__("max_turnover_weight", None),
    ],
    ids=["missing", "explicit_null"],
)
def test_load_construction_artifact_treats_missing_and_explicit_null_turnover_cap_as_canonical_equivalents(
    tmp_path: Path,
    turnover_mutator,
) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(
        _request(include_max_turnover_weight=True),
        artifact_store=store,
    )
    legacy_artifact_id, legacy_payload = _rewrite_artifact_with_rekeyed_payload(
        tmp_path,
        result.artifact_id,
        turnover_mutator,
    )

    loaded = load_construction_artifact(legacy_artifact_id, store=store)

    assert legacy_artifact_id == result.artifact_id
    assert loaded.artifact_id == result.artifact_id
    assert loaded.fingerprint == legacy_payload["fingerprint"] == result.fingerprint
    constraint = next(item for item in loaded.constraint_evaluations if item.constraint_id == "max_turnover_weight")
    assert constraint.status == "not_evaluated"
    assert constraint.limit_value is None


def test_load_construction_artifact_rejects_missing_legacy_policy_definition_id_when_policy_is_unresolvable(
    tmp_path: Path,
) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)

    def _make_unresolvable(payload: dict) -> None:
        payload["policy"]["policy_id"] = "unsupported_policy_v1"
        payload["normalized_inputs"]["policy_id"] = "unsupported_policy_v1"
        payload["normalized_inputs"].pop("policy_definition_id")

    legacy_artifact_id, _ = _rewrite_artifact_with_rekeyed_payload(tmp_path, result.artifact_id, _make_unresolvable)

    with pytest.raises(
        ConstructionArtifactIntegrityValidationError,
        match="construction artifact references unsupported construction policy",
    ):
        load_construction_artifact(legacy_artifact_id, store=store)


def test_load_construction_artifact_rejects_present_unsupported_policy_id(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)

    def _make_unresolvable(payload: dict) -> None:
        payload["policy"]["policy_id"] = "unsupported_policy_v1"
        payload["normalized_inputs"]["policy_id"] = "unsupported_policy_v1"
        payload["normalized_inputs"]["policy_definition_id"] = "construction_policy_definition_top_n_equal_weight_v1"

    artifact_id, _ = _rewrite_artifact_with_rekeyed_payload(tmp_path, result.artifact_id, _make_unresolvable)

    with pytest.raises(
        ConstructionArtifactSchemaValidationError,
        match="persisted construction artifact failed schema validation",
    ):
        load_construction_artifact(artifact_id, store=store)


@pytest.mark.parametrize(
    ("payload_mutator", "expected_error"),
    [
        (
            lambda payload: payload["turnover_diagnostics_v1"].__setitem__("diagnostics_version", "construction_turnover_diagnostics_v0"),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload.__setitem__("turnover_diagnostics_status", "available") or payload.__setitem__("turnover_diagnostics_v1", None),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload["turnover_diagnostics_v1"]["constraint_context"].__setitem__("evaluation_status", "pass"),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload["turnover_diagnostics_v1"]["constraint_context"].__setitem__("requested", True),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload["turnover_diagnostics_v1"]["trade_intent_context"].__setitem__("intent_count", 999),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: next(
                item for item in payload["constraint_evaluations"] if item["constraint_id"] == "max_trade_intent_count"
            ).update({"status": "pass", "actual_value": 999}),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload["turnover_diagnostics_v1"]["symbol_contributions"].__setitem__(0, {
                **payload["turnover_diagnostics_v1"]["symbol_contributions"][0],
                "turnover_contribution_weight": 0.12345678,
            }),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload["weighting_trace_v1"].__setitem__("trace_version", "weighting_trace_v0"),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload["weighting_trace_v1"].__setitem__("policy_id", "top_n_inverse_rank_weight_v1"),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload["weighting_trace_v1"]["stages"][1].__setitem__("positions", payload["weighting_trace_v1"]["stages"][1]["positions"][:-1]),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload.__setitem__("weighting_trace_status", "available") or payload.__setitem__("weighting_trace_v1", None),
            "persisted construction artifact failed schema validation",
        ),
        (
            lambda payload: payload["weighting_trace_v1"].__setitem__("policy_definition_id", "construction_policy_definition_top_n_inverse_rank_weight_v1"),
            "persisted construction artifact failed schema validation",
        ),
    ],
    ids=[
        "turnover_unsupported_version",
        "turnover_present_but_missing_body",
        "turnover_constraint_status_mismatch",
        "turnover_requested_mismatch",
        "turnover_trade_intent_count_mismatch",
        "trade_intent_constraint_mismatch",
        "turnover_symbol_contribution_mismatch",
        "unsupported_version",
        "policy_mismatch",
        "partial_stage_positions",
        "present_but_missing_trace_body",
        "policy_definition_mismatch",
    ],
)
def test_load_construction_artifact_fails_closed_for_invalid_diagnostic_states(
    tmp_path: Path,
    payload_mutator,
    expected_error: str,
) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload_mutator(payload)
    payload_without_ids = {key: value for key, value in payload.items() if key not in {"artifact_id", "fingerprint"}}
    fingerprint = sha256(_canonical_json(payload_without_ids).encode("utf-8")).hexdigest()
    artifact_id = f"construction_artifact_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["artifact_id"] = artifact_id
    artifact_path.unlink()
    (tmp_path / f"{artifact_id}.json").write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    with pytest.raises((ConstructionArtifactSchemaValidationError, ConstructionArtifactIntegrityValidationError), match=expected_error):
        load_construction_artifact(artifact_id, store=store)


def test_load_construction_artifact_raises_missing_file_error(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))

    with pytest.raises(ConstructionArtifactMissingFileError, match="missing persisted construction artifact file"):
        load_construction_artifact("construction_artifact_missing", store=store)


def test_load_construction_artifact_raises_invalid_json_error(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    artifact_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ConstructionArtifactInvalidJsonError, match="invalid persisted construction artifact json"):
        load_construction_artifact(result.artifact_id, store=store)


def test_load_construction_artifact_raises_non_object_payload_error(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    artifact_path.write_text("[]", encoding="utf-8")

    with pytest.raises(
        ConstructionArtifactNonObjectPayloadError,
        match="persisted construction artifact payload must be a json object",
    ):
        load_construction_artifact(result.artifact_id, store=store)


def test_load_construction_artifact_raises_schema_validation_error(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload.pop("status")
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(
        ConstructionArtifactSchemaValidationError,
        match="persisted construction artifact failed schema validation",
    ):
        load_construction_artifact(result.artifact_id, store=store)


def test_construction_artifact_store_enforces_write_once_semantics(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["failure_reasons"] = ["forged"]
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ConstructionArtifactPersistenceError, match="immutable construction artifact conflict"):
        store.persist(result)


def test_construction_route_returns_auditable_artifact_contract(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=type("Settings", (), {"construction_artifact_dir": str(tmp_path)})(),
    )
    client = TestClient(app)

    response = client.post("/construction/run", json=_request().model_dump(mode="json"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "construction_artifact_v1"
    assert payload["status"] == "feasible"
    assert payload["artifact_id"].startswith("construction_artifact_")
    assert payload["normalized_inputs"]["policy_id"] == "top_n_equal_weight_v1"
    assert payload["normalized_inputs"]["policy_definition_id"] == "construction_policy_definition_top_n_equal_weight_v1"
    assert payload["selected_names"][0] == {"symbol": "AAA", "rank": 1, "score": 9.5}
    assert payload["selection_rule_trace"] == {
        "rule_ids": ["eligible_only", "take_top_n"],
        "steps": [
            {
                "rule_id": "eligible_only",
                "rule_order": 1,
                "input_candidate_symbols": ["AAA", "BBB", "CCC", "DDD"],
                "output_candidate_symbols": ["AAA", "BBB", "CCC"],
            },
            {
                "rule_id": "take_top_n",
                "rule_order": 2,
                "input_candidate_symbols": ["AAA", "BBB", "CCC"],
                "output_candidate_symbols": ["AAA", "BBB"],
            },
        ],
    }
    assert payload["turnover_diagnostics_status"] == "available"
    assert payload["turnover_diagnostics_v1"] == {
        "diagnostics_version": "construction_turnover_diagnostics_v1",
        "source": "persisted_construction_artifact",
        "diagnostic_truth": "artifact_backed_hypothetical_construction_diagnostics_only",
        "turnover_basis_method_version": "half_l1_weight_delta_union_v1",
        "reported_value_status": "computed",
        "reported_turnover_weight": 0.6,
        "inclusion_flags": {
            "uses_current_and_target_weight_union": True,
            "includes_initiations": True,
            "includes_exits": True,
            "includes_zero_delta_positions_in_trade_intent_context": True,
            "excludes_zero_delta_positions_from_reported_turnover_sum": True,
        },
        "trade_intent_context": {"source_field": "trade_intents", "intent_count": 4},
        "feasibility_context": {
            "artifact_status": "feasible",
            "failure_reasons_field": "failure_reasons",
            "turnover_failure_reason_present": False,
        },
        "constraint_context": {
            "constraint_id": "max_turnover_weight",
            "requested": False,
            "limit_weight": None,
            "evaluation_status": "not_evaluated",
        },
        "symbol_contributions": [
            {
                "symbol": "AAA",
                "action": "initiate",
                "current_weight": 0.0,
                "target_weight": 0.5,
                "delta_weight": 0.5,
                "absolute_delta_weight": 0.5,
                "turnover_contribution_weight": 0.25,
                "contribution_fraction_of_reported_turnover": 0.41666667,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "BBB",
                "action": "buy",
                "current_weight": 0.4,
                "target_weight": 0.5,
                "delta_weight": 0.1,
                "absolute_delta_weight": 0.1,
                "turnover_contribution_weight": 0.05,
                "contribution_fraction_of_reported_turnover": 0.08333333,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "CCC",
                "action": "exit",
                "current_weight": 0.35,
                "target_weight": 0.0,
                "delta_weight": -0.35,
                "absolute_delta_weight": 0.35,
                "turnover_contribution_weight": 0.175,
                "contribution_fraction_of_reported_turnover": 0.29166667,
                "included_in_reported_turnover": True,
            },
            {
                "symbol": "EEE",
                "action": "exit",
                "current_weight": 0.25,
                "target_weight": 0.0,
                "delta_weight": -0.25,
                "absolute_delta_weight": 0.25,
                "turnover_contribution_weight": 0.125,
                "contribution_fraction_of_reported_turnover": 0.20833333,
                "included_in_reported_turnover": True,
            },
        ],
    }
    assert payload["weighting_trace_status"] == "available"
    assert payload["weighting_trace_v1"]["trace_version"] == "weighting_trace_v1"
    assert payload["weighting_trace_v1"]["source"] == "persisted_construction_artifact"
    assert payload["weighting_trace_v1"]["diagnostic_truth"] == "artifact_backed_hypothetical_construction_diagnostics_only"
    assert payload["weighting_trace_v1"]["policy_id"] == "top_n_equal_weight_v1"
    assert payload["weighting_trace_v1"]["policy_definition_id"] == "construction_policy_definition_top_n_equal_weight_v1"


def test_construction_route_returns_persisted_artifact_by_artifact_id(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=type("Settings", (), {"construction_artifact_dir": str(tmp_path)})(),
    )
    client = TestClient(app)

    run_response = client.post("/construction/run", json=_request().model_dump(mode="json"))

    assert run_response.status_code == 200
    artifact_id = run_response.json()["artifact_id"]
    get_response = client.get(f"/construction/artifacts/{artifact_id}")

    assert get_response.status_code == 200
    assert get_response.json() == run_response.json()


def test_construction_route_lists_exact_shipped_policy_catalog() -> None:
    client = TestClient(app)

    response = client.get("/construction/policies")

    assert response.status_code == 200
    assert response.json() == [
        {
            "policy_id": "top_n_equal_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_equal_weight_v1",
            "name": "Top N Equal Weight v1",
            "description": "Select eligible top-ranked names and assign equal target weights.",
            "family": "top_n_equal_weight",
            "constraints": "long_only_fully_invested_max_position_turnover",
            "inputs": "ranked_universe_and_current_portfolio",
            "determinism": "deterministic_rank_order",
            "ranking_support": "selection_only",
            "full_investment_constraint": "required",
            "long_only_constraint": "required",
            "eligible_ranked_universe_constraint": "required",
            "max_position_weight_constraint": "required",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
            "launch_top_n": 2,
            "selection_rule_ids": ["eligible_only", "take_top_n"],
            "launch_profile": {
                "profile_id": "ranking_artifact_review_handoff_v1",
                "profile_kind": "ranking_artifact_review_handoff",
                "policy_status": "default",
                "launch_top_n": 2,
            },
        },
        {
            "policy_id": "top_n_inverse_rank_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_inverse_rank_weight_v1",
            "name": "Top N Inverse Rank Weight v1",
            "description": "Select eligible top-ranked names and weight them by inverse selected-order rank.",
            "family": "top_n_rank_weighted",
            "constraints": "long_only_fully_invested_max_position_turnover",
            "inputs": "ranked_universe_and_current_portfolio",
            "determinism": "deterministic_rank_order",
            "ranking_support": "inverse_selected_order_weighting",
            "full_investment_constraint": "required",
            "long_only_constraint": "required",
            "eligible_ranked_universe_constraint": "required",
            "max_position_weight_constraint": "required",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
            "launch_top_n": 2,
            "selection_rule_ids": ["eligible_only", "take_top_n"],
            "launch_profile": {
                "profile_id": "ranking_artifact_review_handoff_v1",
                "profile_kind": "ranking_artifact_review_handoff",
                "policy_status": "excluded",
                "launch_top_n": 2,
            },
        },
        {
            "policy_id": "top_n_linear_rank_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_linear_rank_weight_v1",
            "name": "Top N Linear Rank Weight v1",
            "description": "Select eligible top-ranked names and weight them by selected-order linear rank numerators N..1.",
            "family": "top_n_rank_weighted",
            "constraints": "long_only_fully_invested_max_position_turnover",
            "inputs": "ranked_universe_and_current_portfolio",
            "determinism": "deterministic_rank_order",
            "ranking_support": "linear_selected_order_weighting",
            "full_investment_constraint": "required",
            "long_only_constraint": "required",
            "eligible_ranked_universe_constraint": "required",
            "max_position_weight_constraint": "required",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
            "launch_top_n": 2,
            "selection_rule_ids": ["eligible_only", "take_top_n"],
            "launch_profile": {
                "profile_id": "ranking_artifact_review_handoff_v1",
                "profile_kind": "ranking_artifact_review_handoff",
                "policy_status": "opt_in",
                "launch_top_n": 2,
            },
        },
    ]


def test_construction_route_filters_policy_catalog_by_authoritative_metadata() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={
            "family": "top_n_rank_weighted",
            "constraints": "long_only_fully_invested_max_position_turnover",
            "inputs": "ranked_universe_and_current_portfolio",
            "determinism": "deterministic_rank_order",
            "ranking_support": "inverse_selected_order_weighting",
            "full_investment_constraint": "required",
            "long_only_constraint": "required",
            "eligible_ranked_universe_constraint": "required",
            "max_position_weight_constraint": "required",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
        },
    )

    assert response.status_code == 200
    assert response.json() == [
        {
            "policy_id": "top_n_inverse_rank_weight_v1",
            "policy_definition_id": "construction_policy_definition_top_n_inverse_rank_weight_v1",
            "name": "Top N Inverse Rank Weight v1",
            "description": "Select eligible top-ranked names and weight them by inverse selected-order rank.",
            "family": "top_n_rank_weighted",
            "constraints": "long_only_fully_invested_max_position_turnover",
            "inputs": "ranked_universe_and_current_portfolio",
            "determinism": "deterministic_rank_order",
            "ranking_support": "inverse_selected_order_weighting",
            "full_investment_constraint": "required",
            "long_only_constraint": "required",
            "eligible_ranked_universe_constraint": "required",
            "max_position_weight_constraint": "required",
            "min_position_weight_constraint": "supported_optional",
            "max_turnover_weight_constraint": "supported_optional",
            "max_trade_intent_count_constraint": "supported_optional",
            "ranked_universe_input": "required",
            "current_portfolio_input": "required",
            "launch_top_n": 2,
            "selection_rule_ids": ["eligible_only", "take_top_n"],
            "launch_profile": {
                "profile_id": "ranking_artifact_review_handoff_v1",
                "profile_kind": "ranking_artifact_review_handoff",
                "policy_status": "excluded",
                "launch_top_n": 2,
            },
        }
    ]


def test_construction_route_returns_empty_catalog_when_metadata_filter_has_no_exact_match() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={
            "family": "top_n_equal_weight",
            "ranking_support": "linear_selected_order_weighting",
        },
    )

    assert response.status_code == 200
    assert response.json() == []


def test_construction_route_filters_policy_catalog_by_min_position_weight_capability() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"min_position_weight_constraint": "supported_optional"},
    )

    assert response.status_code == 200
    assert [item["policy_id"] for item in response.json()] == [
        "top_n_equal_weight_v1",
        "top_n_inverse_rank_weight_v1",
        "top_n_linear_rank_weight_v1",
    ]


def test_construction_route_filters_policy_catalog_by_trade_intent_count_capability() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"max_trade_intent_count_constraint": "supported_optional"},
    )

    assert response.status_code == 200
    assert [item["policy_id"] for item in response.json()] == [
        "top_n_equal_weight_v1",
        "top_n_inverse_rank_weight_v1",
        "top_n_linear_rank_weight_v1",
    ]


def test_construction_route_filters_policy_catalog_by_launch_top_n() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"launch_top_n": "2"},
    )

    assert response.status_code == 200
    assert [item["policy_id"] for item in response.json()] == [
        "top_n_equal_weight_v1",
        "top_n_inverse_rank_weight_v1",
        "top_n_linear_rank_weight_v1",
    ]


def test_construction_route_policy_catalog_exposes_canonical_launch_profile_statuses() -> None:
    client = TestClient(app)

    response = client.get("/construction/policies")

    assert response.status_code == 200
    payload = response.json()
    assert [
        (item["policy_id"], item["launch_profile"]["policy_status"])
        for item in payload
    ] == [
        ("top_n_equal_weight_v1", "default"),
        ("top_n_inverse_rank_weight_v1", "excluded"),
        ("top_n_linear_rank_weight_v1", "opt_in"),
    ]


def test_construction_route_rejects_invalid_launch_top_n_policy_catalog_filter_value() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"launch_top_n": "3"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'launch_top_n': '3'; supported values: 2"
    }


def test_construction_route_rejects_unsupported_policy_catalog_filter_key() -> None:
    client = TestClient(app)

    response = client.get("/construction/policies", params={"unsupported_filter": "x"})

    assert response.status_code == 422
    assert response.json() == {
        "detail": "unsupported construction policy filter key(s): unsupported_filter"
    }


def test_construction_route_rejects_mixed_supported_and_unsupported_policy_catalog_filter_keys() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"family": "top_n_rank_weighted", "unsupported_filter": "x"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "unsupported construction policy filter key(s): unsupported_filter"
    }


def test_construction_route_rejects_empty_supported_policy_catalog_filter_value() -> None:
    client = TestClient(app)

    response = client.get("/construction/policies?ranking_support=")

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'ranking_support': ''; supported values: inverse_selected_order_weighting, linear_selected_order_weighting, selection_only"
    }


def test_construction_route_rejects_malformed_supported_policy_catalog_filter_value() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"max_turnover_weight_constraint": "supported_optional "},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'max_turnover_weight_constraint': 'supported_optional '; supported values: supported_optional"
    }


def test_construction_route_rejects_invalid_min_position_weight_policy_catalog_filter_value() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies",
        params={"min_position_weight_constraint": "required"},
    )

    assert response.status_code == 422


def test_construction_route_rejects_repeated_policy_catalog_filter_when_any_raw_value_is_malformed() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies?family=bogus&family=top_n_equal_weight"
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "invalid construction policy filter value for 'family': 'bogus'; supported values: top_n_equal_weight, top_n_rank_weighted"
    }


def test_construction_route_rejects_repeated_policy_catalog_filter_when_all_raw_values_are_valid() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies?family=top_n_equal_weight&family=top_n_rank_weighted"
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "repeated construction policy filter key(s): family"
    }


def test_construction_route_rejects_repeated_policy_catalog_filter_when_repeated_values_are_identical() -> None:
    client = TestClient(app)

    response = client.get(
        "/construction/policies?ranking_support=selection_only&ranking_support=selection_only"
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "repeated construction policy filter key(s): ranking_support"
    }


def test_construction_route_returns_404_for_missing_artifact() -> None:
    client = TestClient(app)

    response = client.get("/construction/artifacts/construction_artifact_missing")

    assert response.status_code == 404
    assert "missing persisted construction artifact file" in response.json()["detail"]


def test_construction_route_fails_closed_on_corrupted_persisted_artifact(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=type("Settings", (), {"construction_artifact_dir": str(tmp_path)})(),
    )
    client = TestClient(app)

    run_response = client.post("/construction/run", json=_request().model_dump(mode="json"))
    assert run_response.status_code == 200
    artifact_id = run_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload.pop("status")
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.get(f"/construction/artifacts/{artifact_id}")

    assert response.status_code == 400
    assert "persisted construction artifact failed schema validation" in response.json()["detail"]


def test_construction_route_returns_400_for_invalid_json_artifact(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=type("Settings", (), {"construction_artifact_dir": str(tmp_path)})(),
    )
    client = TestClient(app)

    run_response = client.post("/construction/run", json=_request().model_dump(mode="json"))
    assert run_response.status_code == 200
    artifact_id = run_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    artifact_path.write_text("{not-json", encoding="utf-8")

    response = client.get(f"/construction/artifacts/{artifact_id}")

    assert response.status_code == 400
    assert "invalid persisted construction artifact json" in response.json()["detail"]


def test_construction_route_returns_400_for_non_object_artifact_payload(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=type("Settings", (), {"construction_artifact_dir": str(tmp_path)})(),
    )
    client = TestClient(app)

    run_response = client.post("/construction/run", json=_request().model_dump(mode="json"))
    assert run_response.status_code == 200
    artifact_id = run_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    artifact_path.write_text("[]", encoding="utf-8")

    response = client.get(f"/construction/artifacts/{artifact_id}")

    assert response.status_code == 400
    assert "persisted construction artifact payload must be a json object" in response.json()["detail"]


def test_construction_route_returns_400_for_integrity_validation_failure(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.construction_artifact_service.get_settings",
        return_value=type("Settings", (), {"construction_artifact_dir": str(tmp_path)})(),
    )
    client = TestClient(app)

    run_response = client.post("/construction/run", json=_request().model_dump(mode="json"))
    assert run_response.status_code == 200
    artifact_id = run_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "construction_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.get(f"/construction/artifacts/{artifact_id}")

    assert response.status_code == 400
    assert "construction artifact_id does not match canonical artifact content" in response.json()["detail"]


def test_construction_route_rejects_non_normalized_current_weights() -> None:
    client = TestClient(app)
    payload = _request().model_dump(mode="json")
    payload["current_portfolio"]["weights"][0]["weight"] = 0.9

    response = client.post("/construction/run", json=payload)

    assert response.status_code == 400
    assert response.json() == {"detail": "current_portfolio.weights must sum to 1.0"}
