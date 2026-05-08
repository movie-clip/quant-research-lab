from __future__ import annotations

import tempfile

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.generic_ranking import (
    GENERIC_RANKING_ARTIFACT_ID_PREFIX,
    CompositeScoreTrace,
    EligibilityRecord,
    FactorConfig,
    GenericRankingResponse,
    GenericRankingRow,
    GenericRankingRunMetadata,
    ScoreConfig,
    ScoreConfigRef,
    UniverseSpec,
    UniverseSpecSnapshot,
)
from app.services.generic_ranking_artifact_service import (
    GenericRankingArtifactStore,
    GenericRankingIntegrityError,
    GenericRankingMissingFileError,
    build_stable_generic_ranking_artifact,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_score_config(factor_ids: list[str] | None = None) -> ScoreConfig:
    ids = factor_ids or ["momentum_6m", "realized_volatility_126d"]
    factors = []
    for fid in ids:
        family = "momentum" if "momentum" in fid else "volatility" if "volatility" in fid else "liquidity"
        direction = "lower_is_better" if "volatility" in fid or "drawdown" in fid else "higher_is_better"
        factors.append(
            FactorConfig(
                factor_id=fid,
                family=family,
                direction=direction,
                weight=1.0,
                raw_unit="pct",
            )
        )
    return ScoreConfig(
        score_config_id="test_config_v1",
        factors=factors,
    )


def _make_universe_spec(symbols: list[str] | None = None) -> UniverseSpec:
    return UniverseSpec(
        universe_id="test_universe",
        universe_kind="custom_list",
        explicit_symbols=symbols or ["AAPL", "MSFT", "NVDA"],
    )


def _make_response(symbols: list[str] | None = None) -> GenericRankingResponse:
    syms = symbols or ["AAPL", "MSFT"]
    score_config_ref = ScoreConfigRef(
        score_config_id="test_config_v1",
        score_config_version="v1",
        score_config_digest="abc123",
        factor_ids=["momentum_6m"],
        normalization="cross_sectional_zscore",
        winsorize_pct=0.05,
    )
    run_metadata = GenericRankingRunMetadata(
        ranking_id="generic_ranking_engine_v1",
        methodology_id="generic_ranking_methodology_v1",
        as_of_date="2026-01-31",
        ranking_basis_date="2026-01-31",
        price_basis="close",
        confidence="full",
        score_config_ref=score_config_ref,
        composite_score_trace=CompositeScoreTrace(
            normalization_method="cross_sectional_zscore",
            winsorize_pct=0.05,
            universe_size_at_normalization=len(syms),
            cross_sectional_mean={"momentum_6m": 0.05},
            cross_sectional_std={"momentum_6m": 0.02},
        ),
    )
    ranked = [
        GenericRankingRow(
            rank=i + 1,
            symbol=sym,
            composite_score=1.0 - i * 0.1,
            component_scores={},
            eligibility=EligibilityRecord(eligibility_status="eligible"),
        )
        for i, sym in enumerate(syms)
    ]
    return GenericRankingResponse(
        ranking_id="generic_ranking_engine_v1",
        methodology_id="generic_ranking_methodology_v1",
        title="Test",
        as_of_date="2026-01-31",
        benchmark_symbol="SPY",
        lookback_months=6,
        universe_spec_snapshot=UniverseSpecSnapshot(
            universe_id="test_universe",
            universe_kind="custom_list",
            spec_digest="deadbeef",
            evaluated_members=sorted(syms),
            evaluated_at="2026-01-31",
        ),
        run_metadata=run_metadata,
        ranked_universe=ranked,
        excluded_instruments=[],
        warnings=[],
    )


# ── Schema validation tests ────────────────────────────────────────────────────

def test_universe_spec_requires_explicit_symbols_for_custom_list() -> None:
    with pytest.raises(Exception) as exc_info:
        UniverseSpec(
            universe_id="test",
            universe_kind="custom_list",
            explicit_symbols=[],
        )
    assert "explicit_symbols" in str(exc_info.value).lower() or "requires" in str(exc_info.value).lower()


def test_universe_spec_requires_explicit_symbols_for_etf_peer_group() -> None:
    with pytest.raises(Exception):
        UniverseSpec(
            universe_id="test",
            universe_kind="etf_peer_group",
            explicit_symbols=[],
        )


def test_universe_spec_broad_equity_screen_does_not_require_explicit_symbols() -> None:
    spec = UniverseSpec(
        universe_id="broad_us",
        universe_kind="broad_equity_screen",
    )
    assert spec.universe_kind == "broad_equity_screen"
    assert spec.explicit_symbols == []


def test_universe_spec_custom_list_accepts_symbols() -> None:
    spec = UniverseSpec(
        universe_id="test",
        universe_kind="custom_list",
        explicit_symbols=["AAPL", "MSFT"],
    )
    assert set(spec.explicit_symbols) == {"AAPL", "MSFT"}


# ── ScoreConfig tests ──────────────────────────────────────────────────────────

def test_score_config_normalized_weights_sum_to_one() -> None:
    config = ScoreConfig(
        score_config_id="test",
        factors=[
            FactorConfig(factor_id="momentum_6m", family="momentum", direction="higher_is_better", weight=3.0),
            FactorConfig(factor_id="realized_volatility_126d", family="volatility", direction="lower_is_better", weight=1.0),
            FactorConfig(factor_id="liquidity_60d", family="liquidity", direction="higher_is_better", weight=2.0),
        ],
    )
    weights = config.normalized_weights()
    total = sum(weights.values())
    assert abs(total - 1.0) < 1e-9
    assert abs(weights["momentum_6m"] - 3.0 / 6.0) < 1e-9
    assert abs(weights["realized_volatility_126d"] - 1.0 / 6.0) < 1e-9


def test_score_config_rejects_zero_weight_total() -> None:
    with pytest.raises(Exception) as exc_info:
        ScoreConfig(
            score_config_id="test",
            factors=[
                FactorConfig(factor_id="momentum_6m", family="momentum", direction="higher_is_better", weight=0.0),
            ],
        )
    assert "weight" in str(exc_info.value).lower()


def test_score_config_equal_weights_normalize_correctly() -> None:
    config = ScoreConfig(
        score_config_id="test",
        factors=[
            FactorConfig(factor_id="momentum_6m", family="momentum", direction="higher_is_better", weight=1.0),
            FactorConfig(factor_id="momentum_3m", family="momentum", direction="higher_is_better", weight=1.0),
        ],
    )
    weights = config.normalized_weights()
    assert abs(weights["momentum_6m"] - 0.5) < 1e-9
    assert abs(weights["momentum_3m"] - 0.5) < 1e-9


# ── Artifact builder tests ─────────────────────────────────────────────────────

def test_build_stable_generic_ranking_artifact_produces_correct_prefix() -> None:
    response = _make_response()
    artifact = build_stable_generic_ranking_artifact(response)
    assert artifact.artifact_id.startswith(GENERIC_RANKING_ARTIFACT_ID_PREFIX)
    assert artifact.schema_version == "generic_ranking_artifact_v1"


def test_build_stable_generic_ranking_artifact_is_deterministic() -> None:
    response = _make_response()
    artifact1 = build_stable_generic_ranking_artifact(response)
    artifact2 = build_stable_generic_ranking_artifact(response)
    assert artifact1.artifact_id == artifact2.artifact_id


def test_build_stable_generic_ranking_artifact_different_content_produces_different_id() -> None:
    response_a = _make_response(["AAPL", "MSFT"])
    response_b = _make_response(["AAPL", "NVDA"])
    artifact_a = build_stable_generic_ranking_artifact(response_a)
    artifact_b = build_stable_generic_ranking_artifact(response_b)
    assert artifact_a.artifact_id != artifact_b.artifact_id


# ── Integrity validation tests ─────────────────────────────────────────────────

def test_artifact_integrity_fails_when_field_mutated() -> None:
    response = _make_response()
    artifact = build_stable_generic_ranking_artifact(response)

    # Mutate a field after construction
    mutated = artifact.model_copy(update={"as_of_date": "2099-12-31"})

    from app.services.generic_ranking_artifact_service import validate_generic_ranking_artifact
    with pytest.raises(GenericRankingIntegrityError):
        validate_generic_ranking_artifact(mutated)


def test_artifact_integrity_passes_for_valid_artifact() -> None:
    response = _make_response()
    artifact = build_stable_generic_ranking_artifact(response)
    from app.services.generic_ranking_artifact_service import validate_generic_ranking_artifact
    result = validate_generic_ranking_artifact(artifact)
    assert result.artifact_id == artifact.artifact_id


# ── Store persist / load tests ─────────────────────────────────────────────────

def test_artifact_store_persist_and_load_round_trip() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = GenericRankingArtifactStore(base_dir=tmp)
        response = _make_response()
        artifact = build_stable_generic_ranking_artifact(response)
        persisted = store.persist(artifact)
        loaded = store.load(persisted.artifact_id)
        assert loaded.artifact_id == persisted.artifact_id
        assert loaded.schema_version == "generic_ranking_artifact_v1"


def test_artifact_store_write_once_idempotent() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = GenericRankingArtifactStore(base_dir=tmp)
        response = _make_response()
        artifact = build_stable_generic_ranking_artifact(response)
        store.persist(artifact)
        # Persisting the same artifact again must not raise
        store.persist(artifact)


def test_artifact_store_missing_raises_correct_error() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = GenericRankingArtifactStore(base_dir=tmp)
        with pytest.raises(GenericRankingMissingFileError):
            store.load("generic_ranking_artifact_does_not_exist")


def test_artifact_store_list_recent_returns_newest_first() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        store = GenericRankingArtifactStore(base_dir=tmp)
        r1 = _make_response(["AAPL", "MSFT"])
        r2 = _make_response(["NVDA", "AMZN"])
        a1 = build_stable_generic_ranking_artifact(r1)
        a2 = build_stable_generic_ranking_artifact(r2)
        store.persist(a1)
        store.persist(a2)
        recent = store.list_recent(limit=10)
        assert len(recent) == 2
        # Most recently persisted appears first
        assert recent[0].artifact_id == a2.artifact_id


# ── Route integration tests ────────────────────────────────────────────────────

def test_run_generic_ranking_route_custom_list() -> None:
    client = TestClient(app)
    response = client.post(
        "/strategy-lab/ranking/run",
        json={
            "universe_spec": {
                "universe_id": "tech_test",
                "universe_kind": "custom_list",
                "explicit_symbols": ["AAPL", "MSFT", "NVDA"],
            },
            "score_config": {
                "score_config_id": "test_momentum_v1",
                "factors": [
                    {
                        "factor_id": "momentum_6m",
                        "family": "momentum",
                        "direction": "higher_is_better",
                        "weight": 0.6,
                        "raw_unit": "pct",
                    },
                    {
                        "factor_id": "realized_volatility_126d",
                        "family": "volatility",
                        "direction": "lower_is_better",
                        "weight": 0.4,
                        "raw_unit": "pct",
                    },
                ],
            },
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["schema_version"] == "generic_ranking_artifact_v1"
    assert payload["artifact_id"].startswith("generic_ranking_artifact_")
    assert payload["ranking_id"] == "generic_ranking_engine_v1"
    assert payload["methodology_id"] == "generic_ranking_methodology_v1"
    assert payload["benchmark_symbol"] == "SPY"
    assert payload["ranked_universe"]
    assert payload["ranked_universe"][0]["rank"] == 1
    assert "momentum_6m" in payload["ranked_universe"][0]["component_scores"]
    assert "realized_volatility_126d" in payload["ranked_universe"][0]["component_scores"]
    assert payload["universe_spec_snapshot"]["universe_id"] == "tech_test"
    assert payload["universe_spec_snapshot"]["universe_kind"] == "custom_list"
    assert payload["run_metadata"]["confidence"] in {"full", "partial", "degraded"}
    assert payload["run_metadata"]["score_config_ref"]["score_config_id"] == "test_momentum_v1"


def test_run_generic_ranking_route_returns_stable_artifact_id_on_repeated_calls() -> None:
    client = TestClient(app)
    body = {
        "universe_spec": {
            "universe_id": "stable_test",
            "universe_kind": "custom_list",
            "explicit_symbols": ["AAPL", "MSFT"],
        },
        "score_config": {
            "score_config_id": "stable_config_v1",
            "factors": [
                {
                    "factor_id": "momentum_6m",
                    "family": "momentum",
                    "direction": "higher_is_better",
                    "weight": 1.0,
                    "raw_unit": "pct",
                },
            ],
        },
        "benchmark_symbol": "SPY",
        "lookback_months": 6,
    }
    r1 = client.post("/strategy-lab/ranking/run", json=body)
    r2 = client.post("/strategy-lab/ranking/run", json=body)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["artifact_id"] == r2.json()["artifact_id"]


def test_run_generic_ranking_route_rejects_custom_list_without_symbols() -> None:
    client = TestClient(app)
    response = client.post(
        "/strategy-lab/ranking/run",
        json={
            "universe_spec": {
                "universe_id": "empty",
                "universe_kind": "custom_list",
                "explicit_symbols": [],
            },
            "score_config": {
                "score_config_id": "x",
                "factors": [
                    {
                        "factor_id": "momentum_6m",
                        "family": "momentum",
                        "direction": "higher_is_better",
                        "weight": 1.0,
                    },
                ],
            },
        },
    )
    assert response.status_code == 422  # Pydantic validation error


def test_run_generic_ranking_route_skips_unsupported_factor_ids() -> None:
    client = TestClient(app)
    response = client.post(
        "/strategy-lab/ranking/run",
        json={
            "universe_spec": {
                "universe_id": "tech_test",
                "universe_kind": "custom_list",
                "explicit_symbols": ["AAPL", "MSFT", "NVDA"],
            },
            "score_config": {
                "score_config_id": "mixed_config",
                "factors": [
                    {
                        "factor_id": "momentum_6m",
                        "family": "momentum",
                        "direction": "higher_is_better",
                        "weight": 1.0,
                        "raw_unit": "pct",
                    },
                    {
                        "factor_id": "unknown_factor_xyz",
                        "family": "quality",
                        "direction": "higher_is_better",
                        "weight": 0.5,
                        "raw_unit": "score",
                    },
                ],
            },
        },
    )
    assert response.status_code == 200
    payload = response.json()
    # The unsupported factor should appear in warnings
    warnings = payload.get("warnings", [])
    assert any("unknown_factor_xyz" in w for w in warnings)


def test_list_generic_ranking_recent_route() -> None:
    client = TestClient(app)
    # First create an artifact
    client.post(
        "/strategy-lab/ranking/run",
        json={
            "universe_spec": {
                "universe_id": "recent_test",
                "universe_kind": "custom_list",
                "explicit_symbols": ["AAPL", "MSFT"],
            },
            "score_config": {
                "score_config_id": "recent_config_v1",
                "factors": [
                    {
                        "factor_id": "momentum_6m",
                        "family": "momentum",
                        "direction": "higher_is_better",
                        "weight": 1.0,
                        "raw_unit": "pct",
                    },
                ],
            },
        },
    )
    response = client.get("/strategy-lab/ranking/artifacts/recent")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_generic_ranking_artifact_route() -> None:
    client = TestClient(app)
    create_resp = client.post(
        "/strategy-lab/ranking/run",
        json={
            "universe_spec": {
                "universe_id": "get_test",
                "universe_kind": "custom_list",
                "explicit_symbols": ["AAPL", "MSFT", "NVDA"],
            },
            "score_config": {
                "score_config_id": "get_config_v1",
                "factors": [
                    {
                        "factor_id": "momentum_6m",
                        "family": "momentum",
                        "direction": "higher_is_better",
                        "weight": 1.0,
                        "raw_unit": "pct",
                    },
                ],
            },
        },
    )
    assert create_resp.status_code == 200
    artifact_id = create_resp.json()["artifact_id"]

    get_resp = client.get(f"/strategy-lab/ranking/artifacts/{artifact_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["artifact_id"] == artifact_id


def test_get_generic_ranking_artifact_returns_404_for_unknown() -> None:
    client = TestClient(app)
    response = client.get("/strategy-lab/ranking/artifacts/generic_ranking_artifact_doesnotexist000")
    assert response.status_code == 404
