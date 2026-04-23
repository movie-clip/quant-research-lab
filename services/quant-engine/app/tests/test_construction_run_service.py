import json
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.main import app
from app.schemas.construction import ConstructionArtifact, ConstructionRunRequest
from app.services.construction_artifact_service import (
    ConstructionArtifactIntegrityValidationError,
    ConstructionArtifactInvalidJsonError,
    ConstructionArtifactMissingFileError,
    ConstructionArtifactNonObjectPayloadError,
    ConstructionArtifactPersistenceError,
    ConstructionArtifactSchemaValidationError,
    ConstructionArtifactStore,
    load_construction_artifact,
)
from app.services.construction_run_service import build_construction_run


def _request(
    top_n: int = 2,
    max_position_weight: float = 0.6,
    policy_id: str = "top_n_equal_weight_v1",
) -> ConstructionRunRequest:
    return ConstructionRunRequest.model_validate(
        {
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
    )


def test_build_construction_run_returns_deterministic_equal_weight_artifact(tmp_path: Path) -> None:
    result = build_construction_run(_request(), artifact_store=ConstructionArtifactStore(str(tmp_path)))

    assert result.status == "feasible"
    assert result.policy.policy_id == "top_n_equal_weight_v1"
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
    assert [item.constraint_id for item in result.constraint_evaluations] == [
        "full_investment",
        "long_only",
        "eligible_ranked_universe_only",
        "max_position_weight",
    ]
    assert result.constraint_evaluations[0].status == "binding"
    assert result.constraint_evaluations[3].status == "pass"


def test_build_construction_run_returns_inverse_rank_weight_artifact(tmp_path: Path) -> None:
    result = build_construction_run(
        _request(top_n=3, max_position_weight=0.55, policy_id="top_n_inverse_rank_weight_v1"),
        artifact_store=ConstructionArtifactStore(str(tmp_path)),
    )

    assert result.status == "feasible"
    assert result.policy.policy_id == "top_n_inverse_rank_weight_v1"
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
    assert [item.model_dump(mode="json") for item in result.excluded_names] == [
        {"symbol": "DDD", "rank": 4, "eligible": False, "reason": "liquidity_screen"},
    ]
    assert result.constraint_evaluations[0].status == "binding"
    assert result.constraint_evaluations[3].status == "pass"
    assert result.constraint_evaluations[3].actual_value == 0.54545455


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


def test_load_construction_artifact_rejects_corrupted_payload(tmp_path: Path) -> None:
    store = ConstructionArtifactStore(str(tmp_path))
    result = build_construction_run(_request(), artifact_store=store)
    artifact_path = tmp_path / f"{result.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "construction_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ConstructionArtifactIntegrityValidationError, match="artifact_id does not match canonical artifact content"):
        load_construction_artifact(result.artifact_id, store=store)


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
