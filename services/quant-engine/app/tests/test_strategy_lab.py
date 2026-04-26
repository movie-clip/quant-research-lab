import math
import os
from pathlib import Path
from types import SimpleNamespace
import json
from hashlib import sha256
from typing import cast

from fastapi.testclient import TestClient
import pytest
from pytest import MonkeyPatch

from app.api.main import app
from app.schemas.research import BarRecord
from app.schemas.research import CrossSectionalResearchArtifact
from app.schemas.research import RankingArtifactPreflightResponse
from app.services import strategy_lab as strategy_lab_module
from app.services import replacement_ranking as replacement_ranking_module
from app.services.cross_sectional_research_artifact_service import (
    build_stable_cross_sectional_research_artifact,
    load_cross_sectional_research_artifact,
)
from app.services.etf_ranking_artifact_service import load_etf_ranking_artifact
from app.services.strategy_lab import _blended_momentum, _median_dollar_volume, _normalize_fmp_holdings, _normalize_fmp_holdings_snapshot, _rows_to_monthly_bars, build_etf_ranking_analysis


def test_etf_ranking_route_returns_ranked_universe_and_component_scores() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_id"] == "etf_ranking_engine_v1"
    assert payload["schema_version"] == "etf_ranking_artifact_v1"
    assert payload["artifact_id"].startswith("etf_ranking_artifact_")
    assert payload["ranked_universe"]
    assert payload["ranked_universe"][0]["rank"] == 1
    assert payload["ranked_universe"][0]["component_scores"]["momentum"]["normalized_score"] is not None
    assert payload["ranked_universe"][0]["component_scores"]["momentum"]["label"] == "Blended momentum"
    assert payload["ranked_universe"][0]["component_scores"]["realized_volatility"]["direction"] == "lower_is_better"
    assert payload["ranked_universe"][0]["component_scores"]["liquidity"]["label"] == "Median dollar volume"
    assert payload["effective_component_weights"]["momentum"] > 0
    assert payload["effective_peer_group"] is None
    assert payload["source_status"]["price_history"] in {"sample", "live"}
    assert payload["warnings"]["confidence"] in {"high", "medium", "low"}
    assert payload["request"]["universe"] == ["XLK", "XLF", "XLV", "XLE", "XLI"]
    assert payload["request"]["benchmark_symbol"] == "SPY"
    assert payload["request"]["lookback_months"] == 6
    assert payload["effective_inputs"]["requested_universe"] == ["XLK", "XLF", "XLV", "XLE", "XLI"]
    assert payload["effective_inputs"]["evaluated_universe"] == [row["symbol"] for row in payload["ranked_universe"]]
    assert payload["effective_inputs"]["effective_component_weights"] == payload["effective_component_weights"]
    assert payload["run_metadata"]["ranking_id"] == payload["ranking_id"]
    assert payload["run_metadata"]["methodology_id"] == "etf_ranking_methodology_v1"
    assert payload["run_metadata"]["as_of_date"] == payload["as_of_date"]
    assert payload["run_metadata"]["ranking_basis_date"] == payload["as_of_date"]
    assert payload["run_metadata"]["price_basis"] == payload["price_basis"]
    assert payload["run_metadata"]["source_status"] == payload["source_status"]
    assert payload["run_metadata"]["confidence"] == payload["warnings"]["confidence"]


def test_etf_ranking_route_defaults_benchmark_symbol_and_lookback_months_when_omitted() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["benchmark_symbol"] == "SPY"
    assert payload["lookback_months"] == 3
    assert payload["request"]["benchmark_symbol"] == "SPY"
    assert payload["request"]["lookback_months"] == 3
    assert payload["effective_inputs"]["benchmark_symbol"] == "SPY"
    assert payload["effective_inputs"]["lookback_months"] == 3


def test_etf_ranking_post_persists_artifact_and_get_by_id_returns_same_payload(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    post_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert post_response.status_code == 200
    post_payload = post_response.json()
    artifact_id = post_payload["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    assert artifact_path.exists()

    get_response = client.get(f"/strategy-lab/etf-ranking/artifacts/{artifact_id}")

    assert get_response.status_code == 200
    assert get_response.json() == post_payload


def test_etf_ranking_artifact_id_is_stable_for_same_content(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    request_payload = {
        "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
        "benchmark_symbol": "SPY",
        "lookback_months": 6,
    }

    first = client.post("/strategy-lab/etf-ranking", json=request_payload)
    second = client.post("/strategy-lab/etf-ranking", json=request_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["artifact_id"] == second.json()["artifact_id"]
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_etf_ranking_artifact_id_changes_when_content_changes(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    second = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["artifact_id"] != second.json()["artifact_id"]


def test_load_etf_ranking_artifact_rejects_corrupted_payload(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "etf_ranking_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ValueError, match="etf ranking artifact_id does not match canonical artifact content"):
        load_etf_ranking_artifact(artifact_id)


def test_etf_ranking_get_by_id_returns_400_for_corrupted_persisted_payload(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    artifact_path.write_text("{not-json", encoding="utf-8")

    get_response = client.get(f"/strategy-lab/etf-ranking/artifacts/{artifact_id}")

    assert get_response.status_code == 400
    assert "invalid persisted etf ranking artifact json" in get_response.json()["detail"]


def test_recent_etf_ranking_artifacts_endpoint_returns_empty_state(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.get("/strategy-lab/etf-ranking/artifacts/recent")

    assert response.status_code == 200
    assert response.json() == []


def test_recent_etf_ranking_artifact_metadata_endpoint_returns_empty_state(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.get("/strategy-lab/etf-ranking/artifacts/recent/metadata")

    assert response.status_code == 200
    assert response.json() == {"available_effective_peer_groups": []}


def test_recent_etf_ranking_artifacts_endpoint_orders_newest_first(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    second = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLE", "XLI", "XLB"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200

    recent_response = client.get("/strategy-lab/etf-ranking/artifacts/recent")

    assert recent_response.status_code == 200
    recent = recent_response.json()
    assert [row["artifact_id"] for row in recent[:2]] == [
        second.json()["artifact_id"],
        first.json()["artifact_id"],
    ]
    assert recent[0]["ranking_id"] == second.json()["ranking_id"]
    assert recent[0]["methodology_id"] == second.json()["run_metadata"]["methodology_id"]
    assert recent[0]["as_of_date"] == second.json()["as_of_date"]
    assert recent[0]["ranking_basis_date"] == second.json()["run_metadata"]["ranking_basis_date"]
    assert recent[0]["benchmark_symbol"] == second.json()["benchmark_symbol"]
    assert recent[0]["lookback_months"] == second.json()["lookback_months"]
    assert recent[0]["universe_size"] == len(second.json()["universe"])
    assert recent[0]["evaluated_universe_size"] == len(second.json()["ranked_universe"])
    assert recent[0]["effective_peer_group"] == second.json()["effective_peer_group"]
    assert recent[0]["confidence"] == second.json()["warnings"]["confidence"]


def test_recent_etf_ranking_artifacts_endpoint_applies_limit(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    responses = [
        client.post(
            "/strategy-lab/etf-ranking",
            json={
                "universe": universe,
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
            },
        )
        for universe in (["XLK", "XLF", "XLV"], ["XLE", "XLI", "XLB"], ["XLP", "XLU", "XLY"])
    ]

    assert all(response.status_code == 200 for response in responses)

    recent_response = client.get("/strategy-lab/etf-ranking/artifacts/recent?limit=2")

    assert recent_response.status_code == 200
    recent = recent_response.json()
    assert len(recent) == 2
    assert [row["artifact_id"] for row in recent] == [
        responses[2].json()["artifact_id"],
        responses[1].json()["artifact_id"],
    ]


def test_recent_etf_ranking_artifacts_endpoint_deduplicates_repeated_identical_runs(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    request_payload = {
        "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
        "benchmark_symbol": "SPY",
        "lookback_months": 6,
    }

    first = client.post("/strategy-lab/etf-ranking", json=request_payload)
    second = client.post("/strategy-lab/etf-ranking", json=request_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["artifact_id"] == second.json()["artifact_id"]

    recent_response = client.get("/strategy-lab/etf-ranking/artifacts/recent")

    assert recent_response.status_code == 200
    recent = recent_response.json()
    assert len(recent) == 1
    assert recent[0]["artifact_id"] == first.json()["artifact_id"]


def test_recent_etf_ranking_artifacts_endpoint_uses_index_when_artifact_files_are_missing_or_corrupted(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    valid_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    missing_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLE", "XLI", "XLB"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    corrupted_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLP", "XLU", "XLY"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert valid_response.status_code == 200
    assert missing_response.status_code == 200
    assert corrupted_response.status_code == 200

    missing_path = tmp_path / f"{missing_response.json()['artifact_id']}.json"
    corrupted_path = tmp_path / f"{corrupted_response.json()['artifact_id']}.json"
    missing_path.unlink()
    corrupted_path.write_text("{not-json", encoding="utf-8")

    recent_response = client.get("/strategy-lab/etf-ranking/artifacts/recent")

    assert recent_response.status_code == 200
    assert recent_response.json() == [
        {
            "artifact_id": corrupted_response.json()["artifact_id"],
            "ranking_id": corrupted_response.json()["ranking_id"],
            "methodology_id": corrupted_response.json()["run_metadata"]["methodology_id"],
            "as_of_date": corrupted_response.json()["as_of_date"],
            "ranking_basis_date": corrupted_response.json()["run_metadata"]["ranking_basis_date"],
            "benchmark_symbol": corrupted_response.json()["benchmark_symbol"],
            "lookback_months": corrupted_response.json()["lookback_months"],
            "universe_size": len(corrupted_response.json()["universe"]),
            "evaluated_universe_size": len(corrupted_response.json()["ranked_universe"]),
            "effective_peer_group": corrupted_response.json()["effective_peer_group"],
            "confidence": corrupted_response.json()["warnings"]["confidence"],
        },
        {
            "artifact_id": missing_response.json()["artifact_id"],
            "ranking_id": missing_response.json()["ranking_id"],
            "methodology_id": missing_response.json()["run_metadata"]["methodology_id"],
            "as_of_date": missing_response.json()["as_of_date"],
            "ranking_basis_date": missing_response.json()["run_metadata"]["ranking_basis_date"],
            "benchmark_symbol": missing_response.json()["benchmark_symbol"],
            "lookback_months": missing_response.json()["lookback_months"],
            "universe_size": len(missing_response.json()["universe"]),
            "evaluated_universe_size": len(missing_response.json()["ranked_universe"]),
            "effective_peer_group": missing_response.json()["effective_peer_group"],
            "confidence": missing_response.json()["warnings"]["confidence"],
        },
        {
            "artifact_id": valid_response.json()["artifact_id"],
            "ranking_id": valid_response.json()["ranking_id"],
            "methodology_id": valid_response.json()["run_metadata"]["methodology_id"],
            "as_of_date": valid_response.json()["as_of_date"],
            "ranking_basis_date": valid_response.json()["run_metadata"]["ranking_basis_date"],
            "benchmark_symbol": valid_response.json()["benchmark_symbol"],
            "lookback_months": valid_response.json()["lookback_months"],
            "universe_size": len(valid_response.json()["universe"]),
            "evaluated_universe_size": len(valid_response.json()["ranked_universe"]),
            "effective_peer_group": valid_response.json()["effective_peer_group"],
            "confidence": valid_response.json()["warnings"]["confidence"],
        }
    ]


def test_recent_etf_ranking_artifacts_endpoint_skips_invalid_index_rows(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200

    index_path = tmp_path / "recent.jsonl"
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")
        handle.write("[]\n")
        handle.write(json.dumps({"artifact_id": 123}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        handle.write(json.dumps({"artifact_id": "etf_ranking_artifact_broken"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")

    recent_response = client.get("/strategy-lab/etf-ranking/artifacts/recent")

    assert recent_response.status_code == 200
    assert recent_response.json() == [
        {
            "artifact_id": response.json()["artifact_id"],
            "ranking_id": response.json()["ranking_id"],
            "methodology_id": response.json()["run_metadata"]["methodology_id"],
            "as_of_date": response.json()["as_of_date"],
            "ranking_basis_date": response.json()["run_metadata"]["ranking_basis_date"],
            "benchmark_symbol": response.json()["benchmark_symbol"],
            "lookback_months": response.json()["lookback_months"],
            "universe_size": len(response.json()["universe"]),
            "evaluated_universe_size": len(response.json()["ranked_universe"]),
            "effective_peer_group": response.json()["effective_peer_group"],
            "confidence": response.json()["warnings"]["confidence"],
        }
    ]


def test_recent_etf_ranking_artifacts_endpoint_limit_counts_unique_valid_rows_only(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    second = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLE", "XLI", "XLB"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    duplicate_second = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLE", "XLI", "XLB"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert duplicate_second.status_code == 200
    assert second.json()["artifact_id"] == duplicate_second.json()["artifact_id"]

    index_path = tmp_path / "recent.jsonl"
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"artifact_id": "broken-row"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")

    recent_response = client.get("/strategy-lab/etf-ranking/artifacts/recent?limit=2")

    assert recent_response.status_code == 200
    assert [row["artifact_id"] for row in recent_response.json()] == [
        second.json()["artifact_id"],
        first.json()["artifact_id"],
    ]


def test_recent_etf_ranking_artifacts_endpoint_filters_by_effective_peer_group(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    unfiltered = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    sector = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )
    bond = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Bond UCITS ETF",
        },
    )

    assert unfiltered.status_code == 200
    assert sector.status_code == 200
    assert bond.status_code == 200

    recent_response = client.get(
        "/strategy-lab/etf-ranking/artifacts/recent?effective_peer_group=Sector%20UCITS%20ETF"
    )

    assert recent_response.status_code == 200
    assert recent_response.json() == [
        {
            "artifact_id": sector.json()["artifact_id"],
            "ranking_id": sector.json()["ranking_id"],
            "methodology_id": sector.json()["run_metadata"]["methodology_id"],
            "as_of_date": sector.json()["as_of_date"],
            "ranking_basis_date": sector.json()["run_metadata"]["ranking_basis_date"],
            "benchmark_symbol": sector.json()["benchmark_symbol"],
            "lookback_months": sector.json()["lookback_months"],
            "universe_size": len(sector.json()["universe"]),
            "evaluated_universe_size": len(sector.json()["ranked_universe"]),
            "effective_peer_group": sector.json()["effective_peer_group"],
            "confidence": sector.json()["warnings"]["confidence"],
        }
    ]


def test_recent_etf_ranking_artifacts_endpoint_returns_empty_when_filter_has_no_matches(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200

    recent_response = client.get(
        "/strategy-lab/etf-ranking/artifacts/recent?effective_peer_group=Sector%20UCITS%20ETF"
    )

    assert recent_response.status_code == 200
    assert recent_response.json() == []


def test_recent_etf_ranking_artifact_metadata_endpoint_excludes_nulls_and_deduplicates_duplicate_rows(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    unfiltered = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    sector = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )
    duplicate_sector = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )
    bond = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Bond UCITS ETF",
        },
    )

    assert unfiltered.status_code == 200
    assert sector.status_code == 200
    assert duplicate_sector.status_code == 200
    assert bond.status_code == 200
    assert sector.json()["artifact_id"] == duplicate_sector.json()["artifact_id"]

    response = client.get("/strategy-lab/etf-ranking/artifacts/recent/metadata")

    assert response.status_code == 200
    assert response.json() == {
        "available_effective_peer_groups": [
            bond.json()["effective_peer_group"],
            sector.json()["effective_peer_group"],
        ]
    }


def test_recent_etf_ranking_artifact_metadata_endpoint_skips_invalid_index_rows(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )

    assert response.status_code == 200

    index_path = tmp_path / "recent.jsonl"
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write("not-json\n")
        handle.write("[]\n")
        handle.write(json.dumps({"artifact_id": 123}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")
        handle.write(json.dumps({"artifact_id": "etf_ranking_artifact_broken"}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n")

    metadata_response = client.get("/strategy-lab/etf-ranking/artifacts/recent/metadata")

    assert metadata_response.status_code == 200
    assert metadata_response.json() == {
        "available_effective_peer_groups": [response.json()["effective_peer_group"]]
    }


def test_recent_etf_ranking_artifact_metadata_endpoint_uses_index_when_artifact_files_are_missing_or_corrupted(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    missing_sector = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )
    corrupted_bond = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Bond UCITS ETF",
        },
    )

    assert missing_sector.status_code == 200
    assert corrupted_bond.status_code == 200

    missing_path = tmp_path / f"{missing_sector.json()['artifact_id']}.json"
    corrupted_path = tmp_path / f"{corrupted_bond.json()['artifact_id']}.json"
    missing_path.unlink()
    corrupted_path.write_text("{not-json", encoding="utf-8")

    metadata_response = client.get("/strategy-lab/etf-ranking/artifacts/recent/metadata")

    assert metadata_response.status_code == 200
    assert metadata_response.json() == {
        "available_effective_peer_groups": [
            corrupted_bond.json()["effective_peer_group"],
            missing_sector.json()["effective_peer_group"],
        ]
    }


def test_recent_etf_ranking_artifact_metadata_endpoint_aligns_with_recent_listing_filters(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    responses = [
        client.post(
            "/strategy-lab/etf-ranking",
            json={
                "universe": universe,
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
                "peer_group": peer_group,
            },
        )
        for universe, peer_group in (
            (["IUFS", "IUHC", "VDST"], "Sector UCITS ETF"),
            (["VDST"], "Bond UCITS ETF"),
            (["VUAA"], "Broad Market UCITS ETF"),
        )
    ]
    unfiltered = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert all(response.status_code == 200 for response in responses)
    assert unfiltered.status_code == 200

    metadata_response = client.get("/strategy-lab/etf-ranking/artifacts/recent/metadata")
    recent_response = client.get("/strategy-lab/etf-ranking/artifacts/recent")

    assert metadata_response.status_code == 200
    assert recent_response.status_code == 200

    expected_effective_peer_groups = []
    for row in recent_response.json():
        effective_peer_group = row["effective_peer_group"]
        if effective_peer_group is None or effective_peer_group in expected_effective_peer_groups:
            continue
        expected_effective_peer_groups.append(effective_peer_group)

    assert metadata_response.json() == {
        "available_effective_peer_groups": expected_effective_peer_groups
    }

    for effective_peer_group in expected_effective_peer_groups:
        filtered_response = client.get(
            f"/strategy-lab/etf-ranking/artifacts/recent?effective_peer_group={effective_peer_group.replace(' ', '%20')}"
        )
        assert filtered_response.status_code == 200
        assert filtered_response.json()
        assert all(row["effective_peer_group"] == effective_peer_group for row in filtered_response.json())


def test_recent_etf_ranking_artifacts_endpoint_applies_limit_after_effective_peer_group_filter(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    responses = [
        client.post(
            "/strategy-lab/etf-ranking",
            json={
                "universe": universe,
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
                "peer_group": "Sector UCITS ETF",
            },
        )
        for universe in (["IUFS", "IUHC"], ["BTEC", "IUHC"], ["IUFS", "BTEC"])
    ]
    unfiltered = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert all(response.status_code == 200 for response in responses)
    assert unfiltered.status_code == 200

    recent_response = client.get(
        "/strategy-lab/etf-ranking/artifacts/recent?effective_peer_group=Sector%20UCITS%20ETF&limit=2"
    )

    assert recent_response.status_code == 200
    assert [row["artifact_id"] for row in recent_response.json()] == [
        responses[2].json()["artifact_id"],
        responses[1].json()["artifact_id"],
    ]


def test_recent_etf_ranking_artifacts_endpoint_deduplicates_after_effective_peer_group_filter(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    request_payload = {
        "universe": ["IUFS", "IUHC", "VDST"],
        "benchmark_symbol": "SPY",
        "lookback_months": 6,
        "peer_group": "Sector UCITS ETF",
    }

    first = client.post("/strategy-lab/etf-ranking", json=request_payload)
    second = client.post("/strategy-lab/etf-ranking", json=request_payload)
    other = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Bond UCITS ETF",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert other.status_code == 200
    assert first.json()["artifact_id"] == second.json()["artifact_id"]

    recent_response = client.get(
        "/strategy-lab/etf-ranking/artifacts/recent?effective_peer_group=Sector%20UCITS%20ETF"
    )

    assert recent_response.status_code == 200
    assert recent_response.json() == [
        {
            "artifact_id": first.json()["artifact_id"],
            "ranking_id": first.json()["ranking_id"],
            "methodology_id": first.json()["run_metadata"]["methodology_id"],
            "as_of_date": first.json()["as_of_date"],
            "ranking_basis_date": first.json()["run_metadata"]["ranking_basis_date"],
            "benchmark_symbol": first.json()["benchmark_symbol"],
            "lookback_months": first.json()["lookback_months"],
            "universe_size": len(first.json()["universe"]),
            "evaluated_universe_size": len(first.json()["ranked_universe"]),
            "effective_peer_group": first.json()["effective_peer_group"],
            "confidence": first.json()["warnings"]["confidence"],
        }
    ]


def test_recent_etf_ranking_artifacts_endpoint_filter_uses_index_when_artifact_files_are_missing_or_corrupted(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(etf_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    valid_sector = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )
    missing_sector = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["BTEC", "IUFS"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )
    corrupted_bond = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Bond UCITS ETF",
        },
    )

    assert valid_sector.status_code == 200
    assert missing_sector.status_code == 200
    assert corrupted_bond.status_code == 200

    missing_path = tmp_path / f"{missing_sector.json()['artifact_id']}.json"
    corrupted_path = tmp_path / f"{corrupted_bond.json()['artifact_id']}.json"
    missing_path.unlink()
    corrupted_path.write_text("{not-json", encoding="utf-8")

    recent_response = client.get(
        "/strategy-lab/etf-ranking/artifacts/recent?effective_peer_group=Sector%20UCITS%20ETF"
    )

    assert recent_response.status_code == 200
    assert recent_response.json() == [
        {
            "artifact_id": missing_sector.json()["artifact_id"],
            "ranking_id": missing_sector.json()["ranking_id"],
            "methodology_id": missing_sector.json()["run_metadata"]["methodology_id"],
            "as_of_date": missing_sector.json()["as_of_date"],
            "ranking_basis_date": missing_sector.json()["run_metadata"]["ranking_basis_date"],
            "benchmark_symbol": missing_sector.json()["benchmark_symbol"],
            "lookback_months": missing_sector.json()["lookback_months"],
            "universe_size": len(missing_sector.json()["universe"]),
            "evaluated_universe_size": len(missing_sector.json()["ranked_universe"]),
            "effective_peer_group": missing_sector.json()["effective_peer_group"],
            "confidence": missing_sector.json()["warnings"]["confidence"],
        },
        {
            "artifact_id": valid_sector.json()["artifact_id"],
            "ranking_id": valid_sector.json()["ranking_id"],
            "methodology_id": valid_sector.json()["run_metadata"]["methodology_id"],
            "as_of_date": valid_sector.json()["as_of_date"],
            "ranking_basis_date": valid_sector.json()["run_metadata"]["ranking_basis_date"],
            "benchmark_symbol": valid_sector.json()["benchmark_symbol"],
            "lookback_months": valid_sector.json()["lookback_months"],
            "universe_size": len(valid_sector.json()["universe"]),
            "evaluated_universe_size": len(valid_sector.json()["ranked_universe"]),
            "effective_peer_group": valid_sector.json()["effective_peer_group"],
            "confidence": valid_sector.json()["warnings"]["confidence"],
        },
    ]


def test_etf_ranking_route_supports_custom_weights() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "weights": {
                "momentum": 0.0,
                "benchmark_relative_strength": 0.0,
                "realized_volatility": 1.0,
                "downside_volatility": 0.0,
                "max_drawdown": 0.0,
                "liquidity": 0.0,
                "implementation_fit": 0.0,
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_component_weights"]["realized_volatility"] == 1.0
    assert payload["effective_component_weights"]["momentum"] == 0.0
    assert payload["request"]["weights"]["realized_volatility"] == 1.0
    assert payload["effective_inputs"]["effective_component_weights"]["realized_volatility"] == 1.0


def test_etf_ranking_route_rejects_empty_universe() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": [],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 400


def test_etf_ranking_route_excludes_known_non_etf_symbols_with_explicit_reason() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["AAPL", "XLK", "XLF"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert all(row["symbol"] != "AAPL" for row in payload["ranked_universe"])
    excluded = next(item for item in payload["excluded_symbols"] if item["symbol"] == "AAPL")
    assert excluded["reason"] == "instrument metadata marks AAPL as equity, not etf"


def test_etf_ranking_route_filters_to_requested_peer_group() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_peer_group"] == "Sector UCITS ETF"
    assert payload["request"]["peer_group"] == "Sector UCITS ETF"
    assert payload["effective_inputs"]["effective_peer_group"] == "Sector UCITS ETF"
    assert {row["symbol"] for row in payload["ranked_universe"]} == {"IUFS", "IUHC"}
    excluded = next(item for item in payload["excluded_symbols"] if item["symbol"] == "VDST")
    assert excluded["reason"] == "instrument category Bond UCITS ETF does not match requested peer group Sector UCITS ETF"
    assert payload["effective_inputs"]["excluded_symbols"] == payload["excluded_symbols"]


def test_etf_ranking_route_reports_warnings_for_unknown_metadata_and_unclassified_peer_group_symbols(monkeypatch: MonkeyPatch) -> None:
    bars_by_symbol = {
        "MYSTERY": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-03-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-04-30", open=106, high=106, low=106, close=106, volume=1000),
            BarRecord(date="2025-05-31", open=108, high=108, low=108, close=108, volume=1000),
            BarRecord(date="2025-06-30", open=110, high=110, low=110, close=110, volume=1000),
            BarRecord(date="2025-07-31", open=112, high=112, low=112, close=112, volume=1000),
        ],
        "IUFS": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=1000),
            BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=1000),
            BarRecord(date="2025-05-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-06-30", open=105, high=105, low=105, close=105, volume=1000),
            BarRecord(date="2025-07-31", open=106, high=106, low=106, close=106, volume=1000),
        ],
        "SPY": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=1000),
            BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=1000),
            BarRecord(date="2025-05-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-06-30", open=105, high=105, low=105, close=105, volume=1000),
            BarRecord(date="2025-07-31", open=106, high=106, low=106, close=106, volume=1000),
        ],
    }

    def fake_load_base_data(symbols, benchmark, lookback_months, prefer_live_data, dataset_catalog):
        return strategy_lab_module._StrategyBaseData(
            bars_by_symbol={symbol: bars_by_symbol[symbol] for symbol in [*symbols, benchmark]},
            price_source_label="test-warnings",
            internals_mode="sample",
            price_history_status="sample",
        )

    monkeypatch.setattr(strategy_lab_module, "_load_base_data", fake_load_base_data)

    result = build_etf_ranking_analysis(universe=["MYSTERY", "IUFS"], benchmark_symbol="SPY", lookback_months=6, peer_group="Sector UCITS ETF")

    assert result.effective_peer_group == "Sector UCITS ETF"
    assert result.warnings.confidence == "medium"
    assert "MYSTERY" in result.warnings.unknown_metadata_symbols
    assert "MYSTERY" in result.warnings.peer_group_unclassified_symbols
    assert any("price history only" in warning for warning in result.warnings.warnings)
    assert result.request.peer_group == "Sector UCITS ETF"
    assert result.effective_inputs.evaluated_universe == [row.symbol for row in result.ranked_universe]
    assert result.run_metadata.methodology_id == "etf_ranking_methodology_v1"
    assert result.run_metadata.confidence == result.warnings.confidence


def test_etf_cross_sectional_momentum_route_returns_rankings_and_curve() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 3,
            "top_n": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["strategy_id"] == "book_etf_cross_sectional_momentum"
    assert payload["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["current_rankings"]
    assert payload["equity_curve"]
    assert payload["metrics"]["total_return_pct"] is None
    assert payload["metrics"]["benchmark_return_pct"] is None
    assert payload["metrics"]["excess_return_pct"] is None
    assert payload["metrics"]["annualized_return_pct"] is None
    assert payload["metrics"]["max_drawdown_pct"] is None
    assert payload["metrics"]["benchmark_max_drawdown_pct"] is None
    assert payload["metrics"]["win_rate_pct"] is None
    assert payload["metrics"]["average_volume_participation_ratio"] is not None
    assert payload["observations"][0]["rankings"]
    assert payload["observations"][0]["average_volume_ratio"] is not None
    assert payload["observations"][0]["strategy_return_pct"] is None
    assert payload["observations"][0]["benchmark_return_pct"] is None
    assert payload["equity_curve"][0]["strategy_equity"] is None
    assert payload["equity_curve"][0]["benchmark_equity"] is None
    assert payload["equity_curve"][0]["strategy_drawdown_pct"] is None
    assert payload["equity_curve"][0]["benchmark_drawdown_pct"] is None
    assert len(payload["latest_holdings"]) == 2
    assert payload["leader_internals"]
    assert payload["source_status"]["price_history"] in {"sample", "live"}
    assert payload["source_status"]["leader_internals"] in {"sample", "live-dated", "mixed"}
    assert payload["leader_internals"][0]["leader_symbol"] in {"XLK", "XLI", "XLV", "XLF", "XLE"}
    assert payload["leader_internals"][0]["constituents"][0]["weighted_contribution_pct"] is not None
    assert payload["leader_internals"][0]["snapshot_date"] is not None


def test_strategy_lab_replacement_artifact_get_returns_404_for_missing_file(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.get("/strategy-lab/etf-ranking/replacements/artifacts/intent_bound_etf_replacement_ranking_artifact_missing")

    assert response.status_code == 404
    assert "missing persisted replacement ranking artifact file" in response.json()["detail"]


def test_strategy_lab_replacement_post_keeps_artifact_envelope_additively(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["artifact_id"].startswith("intent_bound_etf_replacement_ranking_artifact_")
    assert payload["schema_version"] == "intent_bound_etf_replacement_ranking_artifact_v1"
    assert payload["lineage"]["candidate_symbol"] == "ETF1"


def test_generalized_ranking_artifact_catalog_lists_persisted_etf_and_replacement_artifacts(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    replacement_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )

    assert etf_response.status_code == 200
    assert replacement_response.status_code == 200

    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 200
    payload = response.json()
    assert payload["metadata"]["contract_version"] == "ranking_artifact_discovery_v1"
    assert payload["metadata"]["supported_artifact_kinds"] == [
        "etf_ranking",
        "intent_bound_etf_replacement_ranking",
    ]
    assert payload["metadata"]["artifact_kind_registry_version"] == "ranking_artifact_kind_registry_v1"
    assert payload["metadata"]["metadata_truth"] == "authoritative_persisted_metadata"
    assert payload["metadata"]["supported_metadata_provenance"] == [
        "persisted_artifact_body",
        "persisted_etf_recent_index",
    ]
    assert payload["metadata"]["supported_filters"] == [
        "artifact_kind",
        "schema_version",
        "metadata_truth",
        "metadata_provenance",
        "recency_same_day_provenance",
        "methodology_id",
        "benchmark_symbol",
        "effective_peer_group",
        "base_symbol",
        "candidate_symbol",
        "peer_group",
        "confidence",
        "status",
        "as_of_date",
        "ranking_basis_date",
        "basis_date",
    ]
    assert payload["metadata"]["artifact_kind_registry"] == [
        {
            "artifact_kind": "etf_ranking",
            "supported_schema_versions": ["etf_ranking_artifact_v1"],
            "supported_filters": [
                "artifact_kind",
                "schema_version",
                "metadata_truth",
                "metadata_provenance",
                "recency_same_day_provenance",
                "methodology_id",
                "confidence",
                "as_of_date",
                "ranking_basis_date",
                "benchmark_symbol",
                "effective_peer_group",
            ],
        },
        {
            "artifact_kind": "intent_bound_etf_replacement_ranking",
            "supported_schema_versions": ["intent_bound_etf_replacement_ranking_artifact_v1"],
            "supported_filters": [
                "artifact_kind",
                "schema_version",
                "metadata_truth",
                "metadata_provenance",
                "recency_same_day_provenance",
                "methodology_id",
                "confidence",
                "as_of_date",
                "ranking_basis_date",
                "base_symbol",
                "candidate_symbol",
                "peer_group",
                "status",
                "basis_date",
            ],
        },
    ]
    assert payload["metadata"]["applied_filters"] == {
        "artifact_kind": None,
        "schema_version": None,
        "metadata_truth": None,
        "metadata_provenance": None,
        "recency_same_day_provenance": None,
        "methodology_id": None,
        "benchmark_symbol": None,
        "effective_peer_group": None,
        "base_symbol": None,
        "candidate_symbol": None,
        "peer_group": None,
        "confidence": None,
        "status": None,
        "as_of_date": None,
        "ranking_basis_date": None,
        "basis_date": None,
    }
    assert {item["artifact_kind"] for item in payload["items"]} == {
        "etf_ranking",
        "intent_bound_etf_replacement_ranking",
    }
    replacement_row = next(item for item in payload["items"] if item["artifact_kind"] == "intent_bound_etf_replacement_ranking")
    etf_row = next(item for item in payload["items"] if item["artifact_kind"] == "etf_ranking")
    assert replacement_row["artifact_id"] == replacement_response.json()["artifact_id"]
    assert replacement_row["schema_version"] == "intent_bound_etf_replacement_ranking_artifact_v1"
    assert replacement_row["replacement_summary"] == {
        "basis_date": replacement_response.json()["basis_date"],
        "status": replacement_response.json()["status"],
        "base_symbol": replacement_response.json()["lineage"]["base_symbol"],
        "candidate_symbol": replacement_response.json()["lineage"]["candidate_symbol"],
        "peer_group": replacement_response.json()["lineage"]["peer_group"],
        "eligible_count": replacement_response.json()["eligible_count"],
        "excluded_count": replacement_response.json()["excluded_count"],
        "confidence": replacement_response.json()["run_metadata"]["confidence"],
    }
    assert replacement_row["etf_summary"] is None
    assert replacement_row["metadata"] == {
        "metadata_truth": "authoritative_persisted_metadata",
        "metadata_provenance": "persisted_artifact_body",
        "matched_metadata_provenance": "persisted_artifact_body",
        "recency_same_day_provenance": "artifact_id",
    }
    assert etf_row["artifact_id"] == etf_response.json()["artifact_id"]
    assert etf_row["schema_version"] == "etf_ranking_artifact_v1"
    assert etf_row["etf_summary"] == {
        "benchmark_symbol": etf_response.json()["benchmark_symbol"],
        "lookback_months": etf_response.json()["lookback_months"],
        "effective_peer_group": etf_response.json()["effective_peer_group"],
        "universe_size": len(etf_response.json()["universe"]),
        "evaluated_universe_size": len(etf_response.json()["ranked_universe"]),
        "confidence": etf_response.json()["warnings"]["confidence"],
    }
    assert etf_row["replacement_summary"] is None
    assert etf_row["metadata"] == {
        "metadata_truth": "authoritative_persisted_metadata",
        "metadata_provenance": "persisted_artifact_body",
        "matched_metadata_provenance": "persisted_artifact_body",
        "recency_same_day_provenance": "etf_recent_index",
    }


def test_generalized_ranking_artifact_catalog_preserves_same_day_etf_recent_index_order(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    first_etf = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    second_etf = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLE", "XLI", "XLB"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert first_etf.status_code == 200
    assert second_etf.status_code == 200

    index_path = tmp_path / "etf" / "recent.jsonl"
    index_lines = index_path.read_text(encoding="utf-8").splitlines()
    index_path.write_text("\n".join(reversed(index_lines)) + "\n", encoding="utf-8")

    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 200
    etf_rows = [item for item in response.json()["items"] if item["artifact_kind"] == "etf_ranking"]
    assert [item["artifact_id"] for item in etf_rows[:2]] == [
        first_etf.json()["artifact_id"],
        second_etf.json()["artifact_id"],
    ]


def test_generalized_ranking_artifact_catalog_returns_400_for_malformed_etf_recent_index_json(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    (tmp_path / "etf" / "recent.jsonl").write_text("not-json\n", encoding="utf-8")

    catalog_response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert catalog_response.status_code == 400
    assert "invalid persisted etf ranking recent index json" in catalog_response.json()["detail"]


def test_generalized_ranking_artifact_catalog_returns_400_for_non_object_etf_recent_index_row(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    (tmp_path / "etf" / "recent.jsonl").write_text("[]\n", encoding="utf-8")

    catalog_response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert catalog_response.status_code == 400
    assert "persisted etf ranking recent index payload must be a json object" in catalog_response.json()["detail"]


def test_generalized_ranking_artifact_catalog_returns_400_for_invalid_etf_recent_index_row_shape(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    (tmp_path / "etf" / "recent.jsonl").write_text(
        json.dumps({"artifact_id": 123}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    catalog_response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert catalog_response.status_code == 400
    assert "persisted etf ranking recent index row failed schema validation" in catalog_response.json()["detail"]


def test_generalized_recent_ranking_artifact_catalog_requires_etf_artifact_enrichment_file(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    replacement_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )

    assert etf_response.status_code == 200
    assert replacement_response.status_code == 200

    etf_artifact_path = tmp_path / "etf" / f"{etf_response.json()['artifact_id']}.json"
    etf_artifact_path.unlink()

    response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert response.status_code == 400
    assert "missing persisted etf ranking artifact file" in response.json()["detail"]


def test_generalized_recent_ranking_artifact_catalog_preserves_same_day_etf_recent_index_order(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    first_etf = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    second_etf = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLE", "XLI", "XLB"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    replacement_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )

    assert first_etf.status_code == 200
    assert second_etf.status_code == 200
    assert replacement_response.status_code == 200

    response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert response.status_code == 200
    etf_rows = [item for item in response.json()["items"] if item["artifact_kind"] == "etf_ranking"]
    assert [item["artifact_id"] for item in etf_rows[:2]] == [
        second_etf.json()["artifact_id"],
        first_etf.json()["artifact_id"],
    ]


def test_generalized_recent_ranking_artifact_catalog_filters_by_kind(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    replacement_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )

    assert etf_response.status_code == 200
    assert replacement_response.status_code == 200

    response = client.get(
        "/strategy-lab/ranking-artifacts/recent?artifact_kind=intent_bound_etf_replacement_ranking"
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["items"]) == 1
    assert payload["items"][0]["artifact_kind"] == "intent_bound_etf_replacement_ranking"
    assert payload["items"][0]["artifact_id"] == replacement_response.json()["artifact_id"]
    assert payload["metadata"]["applied_filters"]["artifact_kind"] == "intent_bound_etf_replacement_ranking"


def test_generalized_ranking_artifact_catalog_filters_by_etf_persisted_metadata(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    sector_etf = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )
    unfiltered_etf = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert sector_etf.status_code == 200
    assert unfiltered_etf.status_code == 200

    response = client.get(
        "/strategy-lab/ranking-artifacts/catalog"
        "?artifact_kind=etf_ranking"
        "&metadata_truth=authoritative_persisted_metadata"
        "&metadata_provenance=persisted_artifact_body"
        "&recency_same_day_provenance=etf_recent_index"
        "&benchmark_symbol=SPY"
        "&effective_peer_group=Sector%20UCITS%20ETF"
        "&confidence=medium"
        "&schema_version=etf_ranking_artifact_v1"
        "&methodology_id=etf_ranking_methodology_v1"
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["artifact_id"] for item in payload["items"]] == [sector_etf.json()["artifact_id"]]
    assert payload["metadata"]["applied_filters"] == {
        "artifact_kind": "etf_ranking",
        "schema_version": "etf_ranking_artifact_v1",
        "metadata_truth": "authoritative_persisted_metadata",
        "metadata_provenance": "persisted_artifact_body",
        "recency_same_day_provenance": "etf_recent_index",
        "methodology_id": "etf_ranking_methodology_v1",
        "benchmark_symbol": "SPY",
        "effective_peer_group": "Sector UCITS ETF",
        "base_symbol": None,
        "candidate_symbol": None,
        "peer_group": None,
        "confidence": "medium",
        "status": None,
        "as_of_date": None,
        "ranking_basis_date": None,
        "basis_date": None,
    }


def test_generalized_recent_ranking_artifact_catalog_filters_by_replacement_persisted_metadata(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    replacement_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )
    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )

    assert replacement_response.status_code == 200
    assert etf_response.status_code == 200

    response = client.get(
        "/strategy-lab/ranking-artifacts/recent"
        "?artifact_kind=intent_bound_etf_replacement_ranking"
        "&metadata_truth=authoritative_persisted_metadata"
        "&metadata_provenance=persisted_artifact_body"
        "&recency_same_day_provenance=artifact_id"
        "&schema_version=intent_bound_etf_replacement_ranking_artifact_v1"
        "&methodology_id=intent_bound_etf_replacement_ranking_methodology_v1"
        "&base_symbol=BASE"
        "&candidate_symbol=ETF1"
        "&peer_group=Sector%20UCITS%20ETF"
        f"&confidence={replacement_response.json()['run_metadata']['confidence']}"
        f"&status={replacement_response.json()['status']}"
        f"&basis_date={replacement_response.json()['basis_date']}"
        f"&ranking_basis_date={replacement_response.json()['run_metadata']['ranking_basis_date']}"
        f"&as_of_date={replacement_response.json()['run_metadata']['as_of_date']}"
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["artifact_id"] for item in payload["items"]] == [replacement_response.json()["artifact_id"]]
    assert payload["metadata"]["applied_filters"] == {
        "artifact_kind": "intent_bound_etf_replacement_ranking",
        "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
        "metadata_truth": "authoritative_persisted_metadata",
        "metadata_provenance": "persisted_artifact_body",
        "recency_same_day_provenance": "artifact_id",
        "methodology_id": "intent_bound_etf_replacement_ranking_methodology_v1",
        "benchmark_symbol": None,
        "effective_peer_group": None,
        "base_symbol": "BASE",
        "candidate_symbol": "ETF1",
        "peer_group": "Sector UCITS ETF",
        "confidence": replacement_response.json()["run_metadata"]["confidence"],
        "status": replacement_response.json()["status"],
        "as_of_date": replacement_response.json()["run_metadata"]["as_of_date"],
        "ranking_basis_date": replacement_response.json()["run_metadata"]["ranking_basis_date"],
        "basis_date": replacement_response.json()["basis_date"],
    }


def test_generalized_recent_ranking_artifact_catalog_filters_missing_etf_artifacts_by_index_metadata_first(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    matching_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )
    other_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Bond UCITS ETF",
        },
    )

    assert matching_response.status_code == 200
    assert other_response.status_code == 200

    (tmp_path / "etf" / f"{matching_response.json()['artifact_id']}.json").unlink()

    response = client.get(
        "/strategy-lab/ranking-artifacts/recent"
        "?artifact_kind=etf_ranking"
        "&metadata_provenance=persisted_etf_recent_index"
        "&effective_peer_group=Sector%20UCITS%20ETF"
    )

    assert response.status_code == 400
    assert "missing persisted etf ranking artifact file" in response.json()["detail"]


def test_generalized_recent_ranking_artifact_catalog_preserves_recent_index_match_provenance_on_enriched_etf_rows(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    etf_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["IUFS", "IUHC", "VDST"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "peer_group": "Sector UCITS ETF",
        },
    )

    assert etf_response.status_code == 200

    response = client.get(
        "/strategy-lab/ranking-artifacts/recent"
        "?artifact_kind=etf_ranking"
        "&metadata_provenance=persisted_etf_recent_index"
        "&effective_peer_group=Sector%20UCITS%20ETF"
    )

    assert response.status_code == 200
    payload = response.json()
    assert [item["artifact_id"] for item in payload["items"]] == [etf_response.json()["artifact_id"]]
    assert payload["metadata"]["applied_filters"] == {
        "artifact_kind": "etf_ranking",
        "schema_version": None,
        "metadata_truth": None,
        "metadata_provenance": "persisted_etf_recent_index",
        "recency_same_day_provenance": None,
        "methodology_id": None,
        "benchmark_symbol": None,
        "effective_peer_group": "Sector UCITS ETF",
        "base_symbol": None,
        "candidate_symbol": None,
        "peer_group": None,
        "confidence": None,
        "status": None,
        "as_of_date": None,
        "ranking_basis_date": None,
        "basis_date": None,
    }
    assert payload["items"][0]["metadata"] == {
        "metadata_truth": "authoritative_persisted_metadata",
        "metadata_provenance": "persisted_artifact_body",
        "matched_metadata_provenance": "persisted_etf_recent_index",
        "recency_same_day_provenance": "etf_recent_index",
    }


def test_generalized_recent_ranking_artifact_catalog_returns_400_for_malformed_etf_recent_index_json(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    index_path = tmp_path / "etf" / "recent.jsonl"
    index_path.write_text("not-json\n", encoding="utf-8")

    recent_response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert recent_response.status_code == 400
    assert "invalid persisted etf ranking recent index json" in recent_response.json()["detail"]


def test_generalized_recent_ranking_artifact_catalog_returns_400_for_non_object_etf_recent_index_row(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    index_path = tmp_path / "etf" / "recent.jsonl"
    index_path.write_text("[]\n", encoding="utf-8")

    recent_response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert recent_response.status_code == 400
    assert "persisted etf ranking recent index payload must be a json object" in recent_response.json()["detail"]


def test_generalized_recent_ranking_artifact_catalog_returns_400_for_unsupported_artifact_kind(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.get("/strategy-lab/ranking-artifacts/recent?artifact_kind=unknown_kind")

    assert response.status_code == 400
    assert response.json()["detail"] == "unsupported ranking artifact kind"


def test_generalized_ranking_artifact_catalog_returns_400_for_kind_specific_unsupported_filter(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.get(
        "/strategy-lab/ranking-artifacts/catalog?artifact_kind=etf_ranking&base_symbol=BASE"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "filter base_symbol is not supported for ranking artifact kind etf_ranking"


def test_generalized_ranking_artifact_catalog_returns_400_for_malformed_registry_filter_metadata(monkeypatch: MonkeyPatch) -> None:
    from app.services import ranking_artifact_catalog_service as catalog_service

    monkeypatch.setattr(
        catalog_service,
        "RANKING_ARTIFACT_KIND_REGISTRY",
        (
            catalog_service.RankingArtifactKindRegistryEntry(
                artifact_kind="etf_ranking",
                supported_schema_versions=("etf_ranking_artifact_v1",),
                supported_filters=cast(tuple, ("artifact_kind", "not_a_real_filter")),
            ),
        ),
    )

    client = TestClient(app)
    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "ranking artifact registry entry etf_ranking declares unsupported filter not_a_real_filter"
    )


def test_generalized_ranking_artifact_catalog_returns_400_for_registry_unknown_schema_version(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.services import ranking_artifact_catalog_service as catalog_service

    monkeypatch.setattr(
        catalog_service,
        "RANKING_ARTIFACT_KIND_REGISTRY",
        (
            catalog_service.RankingArtifactKindRegistryEntry(
                artifact_kind="etf_ranking",
                supported_schema_versions=("etf_ranking_artifact_v2",),
                supported_filters=("artifact_kind", "schema_version"),
            ),
        ),
    )

    client = TestClient(app)
    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "ranking artifact registry entry etf_ranking declares unsupported schema_version etf_ranking_artifact_v2"
    )


def test_generalized_ranking_artifact_catalog_returns_400_for_registry_misspelled_schema_version(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.services import ranking_artifact_catalog_service as catalog_service

    monkeypatch.setattr(
        catalog_service,
        "RANKING_ARTIFACT_KIND_REGISTRY",
        (
            catalog_service.RankingArtifactKindRegistryEntry(
                artifact_kind="etf_ranking",
                supported_schema_versions=("etf_rankng_artifact_v1",),
                supported_filters=("artifact_kind", "schema_version"),
            ),
        ),
    )

    client = TestClient(app)
    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "ranking artifact registry entry etf_ranking declares unsupported schema_version etf_rankng_artifact_v1"
    )


def test_generalized_ranking_artifact_catalog_returns_400_for_registry_duplicate_schema_version(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.services import ranking_artifact_catalog_service as catalog_service

    monkeypatch.setattr(
        catalog_service,
        "RANKING_ARTIFACT_KIND_REGISTRY",
        (
            catalog_service.RankingArtifactKindRegistryEntry(
                artifact_kind="etf_ranking",
                supported_schema_versions=("etf_ranking_artifact_v1", "etf_ranking_artifact_v1"),
                supported_filters=("artifact_kind", "schema_version"),
            ),
        ),
    )

    client = TestClient(app)
    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "ranking artifact registry entry etf_ranking declares duplicate schema_version etf_ranking_artifact_v1"
    )


def test_generalized_ranking_artifact_catalog_returns_400_for_registry_empty_schema_version_declaration(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.services import ranking_artifact_catalog_service as catalog_service

    monkeypatch.setattr(
        catalog_service,
        "RANKING_ARTIFACT_KIND_REGISTRY",
        (
            catalog_service.RankingArtifactKindRegistryEntry(
                artifact_kind="etf_ranking",
                supported_schema_versions=(),
                supported_filters=("artifact_kind", "schema_version"),
            ),
        ),
    )

    client = TestClient(app)
    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "ranking artifact registry entry etf_ranking must declare supported_schema_versions"
    )


def test_generalized_ranking_artifact_catalog_returns_400_for_registry_malformed_schema_version(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.services import ranking_artifact_catalog_service as catalog_service

    monkeypatch.setattr(
        catalog_service,
        "RANKING_ARTIFACT_KIND_REGISTRY",
        (
            catalog_service.RankingArtifactKindRegistryEntry(
                artifact_kind="etf_ranking",
                supported_schema_versions=(" etf_ranking_artifact_v1",),
                supported_filters=("artifact_kind", "schema_version"),
            ),
        ),
    )

    client = TestClient(app)
    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "ranking artifact registry entry etf_ranking declares malformed schema_version"
    )


def test_generalized_ranking_artifact_catalog_returns_400_for_registry_deprecated_schema_version(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.schemas import ranking as ranking_schema
    from app.services import ranking_artifact_catalog_service as catalog_service

    monkeypatch.setattr(
        ranking_schema,
        "DEPRECATED_RANKING_ARTIFACT_SCHEMA_VERSIONS_SET",
        frozenset({"etf_ranking_artifact_v1"}),
    )
    monkeypatch.setattr(
        catalog_service,
        "RANKING_ARTIFACT_KIND_REGISTRY",
        (
            catalog_service.RankingArtifactKindRegistryEntry(
                artifact_kind="etf_ranking",
                supported_schema_versions=("etf_ranking_artifact_v1",),
                supported_filters=("artifact_kind", "schema_version"),
            ),
        ),
    )

    client = TestClient(app)
    response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "ranking artifact registry entry etf_ranking declares deprecated schema_version etf_ranking_artifact_v1"
    )


def test_generalized_recent_ranking_artifact_catalog_returns_400_for_invalid_etf_recent_index_row_shape(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    index_path = tmp_path / "etf" / "recent.jsonl"
    index_path.write_text(
        json.dumps({"artifact_id": 123}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    recent_response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert recent_response.status_code == 400
    assert "persisted etf ranking recent index row failed schema validation" in recent_response.json()["detail"]


def test_generalized_ranking_artifact_catalog_returns_400_for_corrupted_etf_artifact_payload(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    artifact_path = tmp_path / "etf" / f"{response.json()['artifact_id']}.json"
    artifact_path.write_text("{not-json", encoding="utf-8")

    catalog_response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert catalog_response.status_code == 400
    assert "invalid persisted etf ranking artifact json" in catalog_response.json()["detail"]


def test_generalized_ranking_artifact_catalog_returns_400_for_unsupported_etf_schema_version(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    artifact_path = tmp_path / "etf" / f"{response.json()['artifact_id']}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["schema_version"] = "etf_ranking_artifact_v999"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    catalog_response = client.get("/strategy-lab/ranking-artifacts/catalog")

    assert catalog_response.status_code == 400
    assert "unsupported etf ranking schema_version" in catalog_response.json()["detail"]


def test_generalized_recent_ranking_artifact_catalog_returns_400_for_etf_artifact_integrity_contradiction(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    artifact_path = tmp_path / "etf" / f"{response.json()['artifact_id']}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "etf_ranking_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    recent_response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert recent_response.status_code == 400
    assert "etf ranking artifact_id does not match canonical artifact content" in recent_response.json()["detail"]


def test_generalized_recent_ranking_artifact_catalog_returns_400_for_etf_recent_index_identity_contradiction(
    tmp_path: Path,
    mocker,
) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert response.status_code == 200

    index_path = tmp_path / "etf" / "recent.jsonl"
    rows = index_path.read_text(encoding="utf-8").splitlines()
    payload = json.loads(rows[-1])
    payload["ranking_id"] = "contradictory_ranking_id"
    rows[-1] = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    index_path.write_text("\n".join(rows) + "\n", encoding="utf-8")

    recent_response = client.get("/strategy-lab/ranking-artifacts/recent")

    assert recent_response.status_code == 400
    assert "persisted etf recent index metadata contradicts persisted artifact metadata" in recent_response.json()["detail"]


def test_generalized_recent_ranking_artifact_catalog_returns_400_for_kind_schema_version_mismatch(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.get(
        "/strategy-lab/ranking-artifacts/recent"
        "?artifact_kind=etf_ranking"
        "&schema_version=intent_bound_etf_replacement_ranking_artifact_v1"
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "schema_version intent_bound_etf_replacement_ranking_artifact_v1 is not supported for ranking artifact kind etf_ranking"
    )


def test_generalized_recent_ranking_artifact_catalog_returns_400_for_unsupported_replacement_schema_version(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )
    assert response.status_code == 200

    artifact_path = tmp_path / "replacement" / f"{response.json()['artifact_id']}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["schema_version"] = "intent_bound_etf_replacement_ranking_artifact_v999"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    recent_response = client.get("/strategy-lab/ranking-artifacts/recent?artifact_kind=intent_bound_etf_replacement_ranking")

    assert recent_response.status_code == 400
    assert "unsupported replacement ranking schema_version" in recent_response.json()["detail"]


def test_generalized_ranking_artifact_preflight_and_open_happy_path_for_etf(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert artifact_response.status_code == 200

    artifact_payload = artifact_response.json()
    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_payload['artifact_id']}"
    )

    assert preflight_response.status_code == 200
    assert preflight_response.json() == {
        "contract_version": "ranking_artifact_preflight_v1",
        "artifact": {
            "artifact_kind": "etf_ranking",
            "artifact_id": artifact_payload["artifact_id"],
            "schema_version": "etf_ranking_artifact_v1",
            "ranking_id": artifact_payload["ranking_id"],
            "methodology_id": artifact_payload["run_metadata"]["methodology_id"],
            "as_of_date": artifact_payload["run_metadata"]["as_of_date"],
            "ranking_basis_date": artifact_payload["run_metadata"]["ranking_basis_date"],
        },
        "eligibility": {
            "review_truth_basis": "authoritative_persisted_ranking_artifact",
            "review_scope": "artifact_backed_review_only",
            "open_supported": True,
            "replay_eligible": True,
            "consumer_handoff_supported": False,
            "ineligibility_reason": None,
        },
        "open_handoff": {
            "handoff_kind": "ranking_artifact_open_handoff_v1",
            "artifact_kind": "etf_ranking",
            "artifact_id": artifact_payload["artifact_id"],
            "schema_version": "etf_ranking_artifact_v1",
        },
    }

    open_response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=preflight_response.json()["open_handoff"],
    )

    assert open_response.status_code == 200
    assert open_response.json() == {
        "contract_version": "ranking_artifact_open_v1",
        "open_handoff": preflight_response.json()["open_handoff"],
        "review_payload_kind": "etf_ranking_review_payload_v1",
        "review_payload": {
            "review_payload_kind": "etf_ranking_review_payload_v1",
            "review_truth_basis": "authoritative_persisted_ranking_artifact",
            "review_scope": "artifact_backed_review_only",
            "artifact_kind": "etf_ranking",
            "artifact_id": artifact_payload["artifact_id"],
            "schema_version": "etf_ranking_artifact_v1",
            "artifact": artifact_payload,
        },
    }


def test_generalized_ranking_artifact_preflight_and_open_happy_path_for_replacement(tmp_path: Path, mocker) -> None:
    _patch_replacement_ranking_dependencies(mocker)
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )
    assert artifact_response.status_code == 200

    artifact_payload = artifact_response.json()
    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_payload['artifact_id']}"
    )

    assert preflight_response.status_code == 200
    assert preflight_response.json()["artifact"] == {
        "artifact_kind": "intent_bound_etf_replacement_ranking",
        "artifact_id": artifact_payload["artifact_id"],
        "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
        "ranking_id": artifact_payload["ranking_id"],
        "methodology_id": artifact_payload["run_metadata"]["methodology_id"],
        "as_of_date": artifact_payload["run_metadata"]["as_of_date"],
        "ranking_basis_date": artifact_payload["run_metadata"]["ranking_basis_date"],
    }
    assert preflight_response.json()["open_handoff"] == {
        "handoff_kind": "ranking_artifact_open_handoff_v1",
        "artifact_kind": "intent_bound_etf_replacement_ranking",
        "artifact_id": artifact_payload["artifact_id"],
        "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
    }
    assert preflight_response.json()["eligibility"] == {
        "review_truth_basis": "authoritative_persisted_ranking_artifact",
        "review_scope": "artifact_backed_review_only",
        "open_supported": True,
        "replay_eligible": True,
        "consumer_handoff_supported": True,
        "ineligibility_reason": None,
    }

    open_response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=preflight_response.json()["open_handoff"],
    )

    assert open_response.status_code == 200
    assert open_response.json() == {
        "contract_version": "ranking_artifact_open_v1",
        "open_handoff": preflight_response.json()["open_handoff"],
        "review_payload_kind": "intent_bound_etf_replacement_ranking_review_payload_v1",
        "review_payload": {
            "review_payload_kind": "intent_bound_etf_replacement_ranking_review_payload_v1",
            "review_truth_basis": "authoritative_persisted_ranking_artifact",
            "review_scope": "artifact_backed_review_only",
            "artifact_kind": "intent_bound_etf_replacement_ranking",
            "artifact_id": artifact_payload["artifact_id"],
            "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
            "artifact": artifact_payload,
        },
        "consumer_handoff": {
            "contract_version": "intent_bound_etf_replacement_ranking_consumer_contract_v1",
            "handoff_kind": "intent_bound_etf_replacement_ranking_consumer_handoff_v1",
            "artifact_kind": "intent_bound_etf_replacement_ranking",
            "artifact_id": artifact_payload["artifact_id"],
            "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
            "ranking_id": artifact_payload["ranking_id"],
            "methodology_id": artifact_payload["methodology_id"],
            "basis_date": artifact_payload["basis_date"],
            "draft_id": artifact_payload["lineage"]["draft_id"],
            "workspace_id": artifact_payload["lineage"]["workspace_id"],
            "base_node_id": artifact_payload["lineage"]["base_node_id"],
            "base_symbol": artifact_payload["lineage"]["base_symbol"],
            "candidate_symbol": artifact_payload["lineage"]["candidate_symbol"],
            "seed_ranking_id": artifact_payload["lineage"]["seed_ranking_id"],
            "seed_methodology_id": artifact_payload["lineage"]["seed_methodology_id"],
            "seed_ranking_basis_date": artifact_payload["lineage"]["seed_ranking_basis_date"],
            "peer_group": artifact_payload["lineage"]["peer_group"],
            "benchmark_symbol": artifact_payload["lineage"]["benchmark_symbol"],
            "lookback_months": artifact_payload["lineage"]["lookback_months"],
            "eligible_count": artifact_payload["eligible_count"],
            "excluded_count": artifact_payload["excluded_count"],
            "selected_candidate": {
                "symbol": artifact_payload["lineage"]["candidate_symbol"],
                "rank": artifact_payload["ranked_candidates"][0]["rank"],
                "composite_score": artifact_payload["ranked_candidates"][0]["composite_score"],
                "basis_date": artifact_payload["ranked_candidates"][0]["basis_date"],
                "draft_id": artifact_payload["ranked_candidates"][0]["draft_id"],
                "base_node_id": artifact_payload["ranked_candidates"][0]["base_node_id"],
                "base_symbol": artifact_payload["ranked_candidates"][0]["base_symbol"],
                "seed_ranking_id": artifact_payload["ranked_candidates"][0]["seed_ranking_id"],
                "seed_methodology_id": artifact_payload["ranked_candidates"][0]["seed_methodology_id"],
            },
        },
    }


def test_generalized_ranking_artifact_open_rejects_missing_handoff_kind(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert artifact_response.status_code == 200

    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200

    handoff_payload = preflight_response.json()["open_handoff"]
    handoff_payload.pop("handoff_kind")

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=handoff_payload,
    )

    assert response.status_code == 422
    assert "open_handoff.handoff_kind is required" in response.text


def test_generalized_ranking_artifact_open_rejects_unsupported_handoff_kind(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert artifact_response.status_code == 200

    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200

    handoff_payload = preflight_response.json()["open_handoff"]
    handoff_payload["handoff_kind"] = "ranking_artifact_open_handoff_v0"

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=handoff_payload,
    )

    assert response.status_code == 422
    assert "unsupported open_handoff.handoff_kind: ranking_artifact_open_handoff_v0" in response.text


def test_generalized_ranking_artifact_open_rejects_mixed_handoff_and_loose_fields(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert artifact_response.status_code == 200

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json={
            "handoff_kind": "ranking_artifact_open_handoff_v1",
            "artifact_kind": "etf_ranking",
            "artifact_id": artifact_response.json()["artifact_id"],
            "schema_version": "etf_ranking_artifact_v1",
            "benchmark_symbol": "QQQ",
        },
    )

    assert response.status_code == 422


def test_generalized_ranking_artifact_open_rejects_handoff_artifact_kind_mismatch(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert artifact_response.status_code == 200

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json={
            "handoff_kind": "ranking_artifact_open_handoff_v1",
            "artifact_kind": "intent_bound_etf_replacement_ranking",
            "artifact_id": artifact_response.json()["artifact_id"],
            "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "ranking artifact handoff artifact_kind does not match artifact_id"


def test_generalized_ranking_artifact_open_rejects_handoff_schema_version_mismatch(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert artifact_response.status_code == 200

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json={
            "handoff_kind": "ranking_artifact_open_handoff_v1",
            "artifact_kind": "etf_ranking",
            "artifact_id": artifact_response.json()["artifact_id"],
            "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "schema_version intent_bound_etf_replacement_ranking_artifact_v1 is not supported for ranking artifact kind etf_ranking"
    )


def test_generalized_ranking_artifact_open_rejects_preflight_handoff_identity_mismatch(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking",
        json={
            "universe": ["XLK", "XLF", "XLV"],
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
    )
    assert artifact_response.status_code == 200

    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200

    handoff_payload = preflight_response.json()["open_handoff"]
    handoff_payload["artifact_id"] = "etf_ranking_artifact_other"

    response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=handoff_payload,
    )

    assert response.status_code == 404
    assert "missing persisted etf ranking artifact file" in response.json()["detail"]


def test_generalized_ranking_artifact_preflight_returns_404_for_missing_artifact(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/ranking-artifacts/preflight/etf_ranking_artifact_missing"
    )

    assert response.status_code == 404
    assert "missing persisted etf ranking artifact file" in response.json()["detail"]


def test_generalized_ranking_artifact_open_rejects_unreplayable_replacement_artifact(tmp_path: Path, mocker) -> None:
    _patch_replacement_ranking_dependencies(mocker)
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json={
            "replacement_intent": {
                "draft_id": "draft-1",
                "workspace_id": "workspace-1",
                "base_node_id": "node-1",
                "base_symbol": "BASE",
                "candidate_symbol": "ETF1",
                "seed_ranking_id": "etf_ranking_engine_v1",
                "seed_methodology_id": "etf_ranking_methodology_v1",
                "seed_ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
            },
            "seed_context": {
                "ranking_id": "etf_ranking_engine_v1",
                "methodology_id": "etf_ranking_methodology_v1",
                "ranking_basis_date": "2025-12-31",
                "peer_group": "Sector UCITS ETF",
                "benchmark_symbol": "SPY",
                "lookback_months": 6,
                "seeded_symbols": ["BASE", "ETF2"],
            },
        },
    )
    assert artifact_response.status_code == 200
    assert artifact_response.json()["status"] == "unavailable"

    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200
    assert preflight_response.json()["eligibility"] == {
        "review_truth_basis": "authoritative_persisted_ranking_artifact",
        "review_scope": "artifact_backed_review_only",
        "open_supported": False,
        "replay_eligible": False,
        "consumer_handoff_supported": False,
        "ineligibility_reason": "replacement ranking artifact is unreplayable",
    }

    open_response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=preflight_response.json()["open_handoff"],
    )

    assert open_response.status_code == 400
    assert open_response.json()["detail"] == "replacement ranking artifact is unreplayable"


def test_generalized_ranking_artifact_preflight_rejects_replacement_supported_without_consumer_handoff_support() -> None:
    with pytest.raises(
        ValueError,
        match="replacement ranking preflight must keep consumer_handoff_supported aligned with open_supported",
    ):
        RankingArtifactPreflightResponse.model_validate(
            {
                "contract_version": "ranking_artifact_preflight_v1",
                "artifact": {
                    "artifact_kind": "intent_bound_etf_replacement_ranking",
                    "artifact_id": "intent_bound_etf_replacement_ranking_artifact_test",
                    "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
                    "ranking_id": "intent_bound_etf_replacement_ranking_v1",
                    "methodology_id": "intent_bound_etf_replacement_ranking_methodology_v1",
                    "as_of_date": "2025-12-31",
                    "ranking_basis_date": "2025-12-31",
                },
                "eligibility": {
                    "review_truth_basis": "authoritative_persisted_ranking_artifact",
                    "review_scope": "artifact_backed_review_only",
                    "open_supported": True,
                    "replay_eligible": True,
                    "consumer_handoff_supported": False,
                    "ineligibility_reason": None,
                },
                "open_handoff": {
                    "handoff_kind": "ranking_artifact_open_handoff_v1",
                    "artifact_kind": "intent_bound_etf_replacement_ranking",
                    "artifact_id": "intent_bound_etf_replacement_ranking_artifact_test",
                    "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
                },
            }
        )


def test_generalized_ranking_artifact_open_rejects_replacement_consumer_identity_drift_fail_closed(tmp_path: Path, mocker) -> None:
    _patch_replacement_ranking_dependencies(mocker)
    mocker.patch(
        "app.services.etf_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(
            etf_ranking_artifact_dir=str(tmp_path / "etf"),
            replacement_ranking_artifact_dir=str(tmp_path / "replacement"),
        ),
    )
    client = TestClient(app)

    artifact_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )
    assert artifact_response.status_code == 200

    artifact_path = tmp_path / "replacement" / f"{artifact_response.json()['artifact_id']}.json"
    preflight_response = client.post(
        f"/strategy-lab/ranking-artifacts/preflight/{artifact_response.json()['artifact_id']}"
    )
    assert preflight_response.status_code == 200

    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["ranked_candidates"][0]["seed_methodology_id"] = "drifted_methodology"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    open_response = client.post(
        "/strategy-lab/ranking-artifacts/open",
        json=preflight_response.json()["open_handoff"],
    )

    assert open_response.status_code == 400
    assert open_response.json()["detail"] == "replacement ranking artifact_id does not match canonical artifact content"


def test_legacy_replacement_post_maps_persisted_artifact_back_to_legacy_shape(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/ranking/etf-replacements",
        json=_replacement_ranking_request_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_id"] == "intent_bound_etf_replacement_ranking_v1"
    assert payload["methodology_id"] == "intent_bound_etf_replacement_ranking_methodology_v1"
    assert "artifact_id" not in payload
    assert "schema_version" not in payload
    assert "lineage" not in payload
    assert payload["request_context"]["candidate_symbol"] == "ETF1"
    assert payload["request_hash"]
    persisted_artifacts = list(tmp_path.glob("*.json"))
    assert len(persisted_artifacts) == 1
    assert persisted_artifacts[0].stem.startswith("intent_bound_etf_replacement_ranking_artifact_")


def _replacement_ranking_request_payload() -> dict[str, object]:
    return {
        "replacement_intent": {
            "draft_id": "draft-1",
            "workspace_id": "workspace-1",
            "base_node_id": "node-1",
            "base_symbol": "BASE",
            "candidate_symbol": "ETF1",
            "seed_ranking_id": "etf_ranking_engine_v1",
            "seed_methodology_id": "etf_ranking_methodology_v1",
            "seed_ranking_basis_date": "2025-12-31",
            "peer_group": "Sector UCITS ETF",
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
        },
        "seed_context": {
            "ranking_id": "etf_ranking_engine_v1",
            "methodology_id": "etf_ranking_methodology_v1",
            "ranking_basis_date": "2025-12-31",
            "peer_group": "Sector UCITS ETF",
            "benchmark_symbol": "SPY",
            "lookback_months": 6,
            "seeded_symbols": ["BASE", "ETF1", "ETF2"],
        },
    }


def _cross_sectional_research_request_payload() -> dict[str, object]:
    return {
        "methodology_id": "alpha_quality_v1",
        "rebalance_date": "2024-04-15",
        "as_of_date": "2024-04-15",
        "holdout_start_date": "2024-01-01",
        "dataset_version": "alpha_quality_dataset_demo_v1",
        "universe_definition": "us_large_cap_demo_v1",
        "benchmark": {
            "benchmark_symbol": "SPY",
            "benchmark_name": "SPDR S&P 500 ETF Trust",
            "benchmark_kind": "etf_proxy",
        },
        "universe_symbols": ["AAA", "BBB", "CCC"],
        "source_name": "direct_snapshot_input",
        "fundamental_snapshots": [
            {
                "symbol": "AAA",
                "statement_date": "2023-12-31",
                "period_type": "annual",
                "total_revenue": 1000.0,
                "cost_of_revenue": 400.0,
                "ebit": 200.0,
                "total_assets": 800.0,
                "operating_cash_flow": 180.0,
                "free_cash_flow": 120.0,
                "net_income": 150.0,
                "total_debt": 160.0,
                "cash_and_equivalents": 60.0,
            },
            {
                "symbol": "BBB",
                "statement_date": "2023-12-31",
                "period_type": "annual",
                "total_revenue": 950.0,
                "cost_of_revenue": 500.0,
                "ebit": 150.0,
                "total_assets": 900.0,
                "operating_cash_flow": 110.0,
                "free_cash_flow": 80.0,
                "net_income": 120.0,
                "total_debt": 260.0,
                "cash_and_equivalents": 30.0,
            },
            {
                "symbol": "CCC",
                "statement_date": "2023-12-31",
                "period_type": "annual",
                "total_revenue": 700.0,
                "cost_of_revenue": 420.0,
                "ebit": 90.0,
                "total_assets": 850.0,
                "operating_cash_flow": 70.0,
                "free_cash_flow": 40.0,
                "net_income": 115.0,
                "total_debt": 320.0,
                "cash_and_equivalents": 20.0,
            },
        ],
        "top_ranked_count": 2,
    }


def _set_cross_sectional_artifact_persisted_at(path: Path, persisted_at: str) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["persisted_at"] = persisted_at
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")


def _set_cross_sectional_research_reload_response_identity(
    path: Path,
    *,
    artifact_id: str | None = None,
    artifact_kind: str | None = None,
    schema_version: str | None = None,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if artifact_id is not None:
        payload["artifact_id"] = artifact_id
    if artifact_kind is not None:
        payload["artifact_kind"] = artifact_kind
    if schema_version is not None:
        payload["schema_version"] = schema_version
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")


def _rekey_cross_sectional_research_artifact_payload(
    tmp_path: Path,
    artifact_id: str,
    payload_mutator,
) -> str:
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload_mutator(payload)
    artifact = CrossSectionalResearchArtifact.model_validate(payload)
    stable_artifact = build_stable_cross_sectional_research_artifact(artifact)
    artifact_path.unlink()
    stable_path = tmp_path / f"{stable_artifact.artifact_id}.json"
    stable_path.write_text(
        json.dumps(stable_artifact.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )
    return stable_artifact.artifact_id


def _rekey_legacy_cross_sectional_research_artifact_payload(
    tmp_path: Path,
    artifact_id: str,
    payload_mutator,
) -> str:
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload_mutator(payload)
    payload_without_ids = {
        key: value
        for key, value in payload.items()
        if key not in {"artifact_id", "fingerprint", "persisted_at"}
    }
    fingerprint = sha256(
        json.dumps(payload_without_ids, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    ).hexdigest()
    legacy_artifact_id = f"cross_sectional_research_artifact_{fingerprint[:16]}"
    payload["fingerprint"] = fingerprint
    payload["artifact_id"] = legacy_artifact_id
    artifact_path.unlink()
    legacy_path = tmp_path / f"{legacy_artifact_id}.json"
    legacy_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )
    return legacy_artifact_id


def test_strategy_lab_replacement_artifact_get_returns_400_for_invalid_json(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    post_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )
    assert post_response.status_code == 200
    artifact_id = post_response.json()["artifact_id"]
    (tmp_path / f"{artifact_id}.json").write_text("{not-json", encoding="utf-8")

    response = client.get(f"/strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}")

    assert response.status_code == 400
    assert "invalid persisted replacement ranking artifact json" in response.json()["detail"]


def test_strategy_lab_replacement_artifact_get_returns_400_for_non_object_payload(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    post_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )
    assert post_response.status_code == 200
    artifact_id = post_response.json()["artifact_id"]
    (tmp_path / f"{artifact_id}.json").write_text("[]", encoding="utf-8")

    response = client.get(f"/strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}")

    assert response.status_code == 400
    assert "payload must be a json object" in response.json()["detail"]


def test_strategy_lab_replacement_artifact_get_returns_400_for_schema_failure(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    post_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )
    assert post_response.status_code == 200
    artifact_id = post_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload.pop("status")
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.get(f"/strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}")

    assert response.status_code == 400
    assert "failed schema validation" in response.json()["detail"]


def test_strategy_lab_replacement_artifact_get_returns_400_for_integrity_failure(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.replacement_ranking_artifact_service.get_settings",
        return_value=SimpleNamespace(replacement_ranking_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    post_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_replacement_ranking_request_payload(),
    )
    assert post_response.status_code == 200
    artifact_id = post_response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "intent_bound_etf_replacement_ranking_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    response = client.get(f"/strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}")

    assert response.status_code == 400
    assert "replacement ranking artifact_id does not match canonical artifact content" in response.json()["detail"]


def test_cross_sectional_research_validate_does_not_persist_and_returns_compact_contract(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/validate",
        json=_cross_sectional_research_request_payload(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["valid"] is True
    assert payload["artifact_kind"] == "cross_sectional_research_run"
    assert payload["schema_version"] == "cross_sectional_research_artifact_v1"
    assert payload["would_persist_artifact_id"].startswith("cross_sectional_research_artifact_")
    assert len(payload["would_persist_fingerprint"]) == 64
    assert payload["normalized_request"]["methodology_id"] == "alpha_quality_v1"
    assert payload["methodology_metadata_v1"] == {
        "methodology_family_id": "cross_sectional_research_family_v1",
        "methodology_family_version": "v1",
        "active_methodology_id": "alpha_quality_v1",
        "active_methodology_version": "v1",
        "alpha_package_version": "alpha_quality_v1",
        "alpha_methodology_id": "alpha_quality_v1_methodology",
        "alpha_input_contract_id": "alpha_quality_v1_pit_fundamentals_v1",
        "score_basis": "optimizer_alpha_package.final_score",
        "benchmark_role": "descriptive_reference_only",
        "partition_rule": "effective_date_before_holdout_start_else_holdout",
        "output_shape": "compact_summary_only",
        "component_signal_ids": [
            "profitability",
            "cash_generation",
            "accrual_quality",
            "leverage_discipline",
        ],
    }
    assert payload["status_metadata_v1"] == {
        "artifact_status": "complete",
        "diagnostics_status": "ok",
        "coverage_status": "complete",
    }
    assert payload["provenance_metadata_v1"] == {
        "input_source_kind": "direct_snapshot_input",
        "replay_provenance_status": "absent",
        "benchmark_source_kind": "request_benchmark_reference",
        "alpha_source_kind": "optimizer_alpha_package",
    }
    assert payload["dataset_version"] == "alpha_quality_dataset_demo_v1"
    assert payload["universe_definition"] == "us_large_cap_demo_v1"
    assert payload["benchmark"]["benchmark_symbol"] == "SPY"
    assert payload["walk_forward_summary"]["split_label"] == "walk_forward"
    assert payload["holdout_summary"]["split_label"] == "holdout"
    assert payload["walk_forward_summary"]["provenance"]["alpha_package_version"] == "alpha_quality_v1"
    assert payload["provenance"]["alpha_input_contract_id"] == "alpha_quality_v1_pit_fundamentals_v1"
    assert list(tmp_path.glob("*.json")) == []


def test_cross_sectional_research_run_persists_and_reloads_same_artifact(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    post_response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )

    assert post_response.status_code == 200
    artifact_payload = post_response.json()
    artifact_id = artifact_payload["artifact_id"]
    assert (tmp_path / f"{artifact_id}.json").exists()

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")

    assert get_response.status_code == 200
    assert get_response.json() == {
        "contract_version": "cross_sectional_research_reload_v1",
        "requested_artifact_id": artifact_id,
        "artifact_id": artifact_id,
        "artifact_kind": artifact_payload["artifact_kind"],
        "schema_version": artifact_payload["schema_version"],
        "artifact": artifact_payload,
    }
    assert artifact_payload["persisted_at"].endswith("Z")
    assert artifact_payload["methodology_metadata_v1"]["active_methodology_id"] == artifact_payload["methodology_id"]
    assert artifact_payload["status_metadata_v1"]["diagnostics_status"] == artifact_payload["provenance"]["alpha_diagnostics_status"]
    assert artifact_payload["provenance_metadata_v1"]["alpha_source_kind"] == "optimizer_alpha_package"


def test_cross_sectional_research_get_returns_404_for_missing_artifact(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.get(
        "/strategy-lab/cross-sectional-research/artifacts/cross_sectional_research_artifact_missing"
    )

    assert response.status_code == 404
    assert "missing persisted cross-sectional research artifact file" in response.json()["detail"]


def test_cross_sectional_research_artifact_id_is_stable_for_same_content(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)
    request_payload = _cross_sectional_research_request_payload()

    first = client.post("/strategy-lab/cross-sectional-research/run", json=request_payload)
    second = client.post("/strategy-lab/cross-sectional-research/run", json=request_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["artifact_id"] == second.json()["artifact_id"]
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_cross_sectional_research_load_rejects_corrupted_integrity(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )

    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["fingerprint"] = "0" * 64
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ValueError, match="cross-sectional research fingerprint does not match canonical artifact content"):
        load_cross_sectional_research_artifact(artifact_id)


def test_cross_sectional_research_get_returns_400_for_invalid_json(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    (tmp_path / f"{artifact_id}.json").write_text("{not-json", encoding="utf-8")

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")

    assert get_response.status_code == 400
    assert "invalid persisted cross-sectional research artifact json" in get_response.json()["detail"]


def test_cross_sectional_research_catalog_and_recent_are_persisted_only(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    validate_response = client.post(
        "/strategy-lab/cross-sectional-research/validate",
        json=_cross_sectional_research_request_payload(),
    )
    assert validate_response.status_code == 200

    empty_catalog = client.get("/strategy-lab/cross-sectional-research/catalog")
    empty_recent = client.get("/strategy-lab/cross-sectional-research/recent")

    assert empty_catalog.status_code == 200
    assert empty_recent.status_code == 200
    assert empty_catalog.json()["items"] == []
    assert empty_recent.json()["items"] == []

    run_response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert run_response.status_code == 200

    catalog_response = client.get(
        "/strategy-lab/cross-sectional-research/catalog?artifact_kind=cross_sectional_research_run&methodology_id=alpha_quality_v1&dataset_version=alpha_quality_dataset_demo_v1&benchmark_symbol=SPY&artifact_status=complete&input_source_kind=direct_snapshot_input&score_basis=optimizer_alpha_package.final_score"
    )
    recent_response = client.get(
        "/strategy-lab/cross-sectional-research/recent?limit=1&schema_version=cross_sectional_research_artifact_v1"
    )

    assert catalog_response.status_code == 200
    assert recent_response.status_code == 200
    assert [item["artifact_id"] for item in catalog_response.json()["items"]] == [run_response.json()["artifact_id"]]
    assert [item["artifact_id"] for item in recent_response.json()["items"]] == [run_response.json()["artifact_id"]]
    assert catalog_response.json()["metadata"] == {
        "contract_version": "cross_sectional_research_discovery_v1",
        "metadata_truth": "authoritative_persisted_artifact_metadata",
        "recent_order_basis": "persisted_artifact.persisted_at_then_artifact_id",
        "supported_filters": [
            "artifact_kind",
            "schema_version",
            "methodology_id",
            "dataset_version",
            "universe_definition",
            "benchmark_symbol",
            "rebalance_date",
            "as_of_date",
            "holdout_start_date",
            "methodology_family_id",
            "methodology_family_version",
            "active_methodology_version",
            "alpha_package_version",
            "alpha_methodology_id",
            "alpha_input_contract_id",
            "score_basis",
            "benchmark_role",
            "partition_rule",
            "output_shape",
            "artifact_status",
            "diagnostics_status",
            "coverage_status",
            "input_source_kind",
            "replay_provenance_status",
            "benchmark_source_kind",
            "alpha_source_kind",
        ],
        "methodology_metadata_v1_semantics": "descriptive_only",
        "status_metadata_v1_semantics": "descriptive_only",
        "provenance_metadata_v1_semantics": "descriptive_only",
        "applied_filters": {
            "artifact_kind": "cross_sectional_research_run",
            "schema_version": None,
            "methodology_id": "alpha_quality_v1",
            "dataset_version": "alpha_quality_dataset_demo_v1",
            "universe_definition": None,
            "benchmark_symbol": "SPY",
            "rebalance_date": None,
            "as_of_date": None,
            "holdout_start_date": None,
            "methodology_family_id": None,
            "methodology_family_version": None,
            "active_methodology_version": None,
            "alpha_package_version": None,
            "alpha_methodology_id": None,
            "alpha_input_contract_id": None,
            "score_basis": "optimizer_alpha_package.final_score",
            "benchmark_role": None,
            "partition_rule": None,
            "output_shape": None,
            "artifact_status": "complete",
            "diagnostics_status": None,
            "coverage_status": None,
            "input_source_kind": "direct_snapshot_input",
            "replay_provenance_status": None,
            "benchmark_source_kind": None,
            "alpha_source_kind": None,
        },
    }
    assert catalog_response.json()["applied_filters"] == {
        "artifact_kind": "cross_sectional_research_run",
        "schema_version": None,
        "methodology_id": "alpha_quality_v1",
        "dataset_version": "alpha_quality_dataset_demo_v1",
        "universe_definition": None,
        "benchmark_symbol": "SPY",
        "rebalance_date": None,
        "as_of_date": None,
        "holdout_start_date": None,
        "methodology_family_id": None,
        "methodology_family_version": None,
        "active_methodology_version": None,
        "alpha_package_version": None,
        "alpha_methodology_id": None,
        "alpha_input_contract_id": None,
        "score_basis": "optimizer_alpha_package.final_score",
        "benchmark_role": None,
        "partition_rule": None,
        "output_shape": None,
        "artifact_status": "complete",
        "diagnostics_status": None,
        "coverage_status": None,
        "input_source_kind": "direct_snapshot_input",
        "replay_provenance_status": None,
        "benchmark_source_kind": None,
        "alpha_source_kind": None,
    }
    assert recent_response.json()["items"][0]["recent_order_persisted_at"] == run_response.json()["persisted_at"]
    assert recent_response.json()["items"][0]["recent_order_artifact_id"] == run_response.json()["artifact_id"]
    assert catalog_response.json()["items"][0]["methodology_metadata_v1"] == run_response.json()["methodology_metadata_v1"]
    assert catalog_response.json()["items"][0]["status_metadata_v1"] == run_response.json()["status_metadata_v1"]
    assert catalog_response.json()["items"][0]["provenance_metadata_v1"] == run_response.json()["provenance_metadata_v1"]
    assert recent_response.json()["items"][0]["methodology_metadata_v1"] == run_response.json()["methodology_metadata_v1"]
    assert recent_response.json()["items"][0]["status_metadata_v1"] == run_response.json()["status_metadata_v1"]
    assert recent_response.json()["items"][0]["provenance_metadata_v1"] == run_response.json()["provenance_metadata_v1"]


def test_cross_sectional_research_recent_orders_by_persisted_metadata_only_for_backfilled_artifacts(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    older_request = _cross_sectional_research_request_payload()
    newer_request = _cross_sectional_research_request_payload()
    older_request["rebalance_date"] = "2024-04-15"
    older_request["as_of_date"] = "2024-04-15"
    newer_request["rebalance_date"] = "2024-04-01"
    newer_request["as_of_date"] = "2024-04-01"

    older_response = client.post("/strategy-lab/cross-sectional-research/run", json=older_request)
    newer_response = client.post("/strategy-lab/cross-sectional-research/run", json=newer_request)

    assert older_response.status_code == 200
    assert newer_response.status_code == 200

    older_path = tmp_path / f"{older_response.json()['artifact_id']}.json"
    newer_path = tmp_path / f"{newer_response.json()['artifact_id']}.json"
    _set_cross_sectional_artifact_persisted_at(older_path, "2026-04-25T09:30:00Z")
    _set_cross_sectional_artifact_persisted_at(newer_path, "2026-04-24T09:30:00Z")
    os.utime(older_path, (1_700_000_000, 1_700_000_000))
    os.utime(newer_path, (1_900_000_000, 1_900_000_000))

    recent_response = client.get("/strategy-lab/cross-sectional-research/recent")

    assert recent_response.status_code == 200
    assert [item["artifact_id"] for item in recent_response.json()["items"][:2]] == [
        older_response.json()["artifact_id"],
        newer_response.json()["artifact_id"],
    ]


def test_cross_sectional_research_recent_uses_artifact_id_tiebreak_for_equal_persisted_timestamps(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    first_request = _cross_sectional_research_request_payload()
    second_request = _cross_sectional_research_request_payload()
    first_request["dataset_version"] = "alpha_quality_dataset_demo_v1"
    second_request["dataset_version"] = "alpha_quality_dataset_demo_v2"

    first_response = client.post("/strategy-lab/cross-sectional-research/run", json=first_request)
    second_response = client.post("/strategy-lab/cross-sectional-research/run", json=second_request)

    assert first_response.status_code == 200
    assert second_response.status_code == 200

    tied_timestamp = "2026-04-25T09:30:00Z"
    for artifact_id in [first_response.json()["artifact_id"], second_response.json()["artifact_id"]]:
        _set_cross_sectional_artifact_persisted_at(tmp_path / f"{artifact_id}.json", tied_timestamp)

    expected_order = sorted(
        [first_response.json()["artifact_id"], second_response.json()["artifact_id"]],
        reverse=True,
    )
    recent_response = client.get("/strategy-lab/cross-sectional-research/recent")

    assert recent_response.status_code == 200
    assert [item["artifact_id"] for item in recent_response.json()["items"][:2]] == expected_order
    assert all(item["recent_order_persisted_at"] == tied_timestamp for item in recent_response.json()["items"][:2])


@pytest.mark.parametrize(
    ("query", "expected_detail"),
    [
        ("rebalance_date=2024-4-15", "rebalance_date must be a canonical YYYY-MM-DD date"),
        ("as_of_date=2024-04-15T00:00:00", "as_of_date must be a canonical YYYY-MM-DD date"),
        ("holdout_start_date= 2024-01-01 ", "holdout_start_date must be a canonical YYYY-MM-DD date"),
    ],
)
def test_cross_sectional_research_discovery_filters_reject_malformed_dates(tmp_path: Path, mocker, query: str, expected_detail: str) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    catalog_response = client.get(f"/strategy-lab/cross-sectional-research/catalog?{query}")
    recent_response = client.get(f"/strategy-lab/cross-sectional-research/recent?{query}")

    assert catalog_response.status_code == 400
    assert catalog_response.json() == {"detail": expected_detail}
    assert recent_response.status_code == 400
    assert recent_response.json() == {"detail": expected_detail}


def test_cross_sectional_research_recent_returns_400_for_non_object_payload(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    (tmp_path / f"{artifact_id}.json").write_text("[]", encoding="utf-8")

    recent_response = client.get("/strategy-lab/cross-sectional-research/recent")

    assert recent_response.status_code == 400
    assert "payload must be a json object" in recent_response.json()["detail"]


def test_cross_sectional_research_load_fails_closed_on_non_canonical_methodology_metadata_v1(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["methodology_metadata_v1"]["benchmark_role"] = " descriptive_reference_only "
    artifact_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")

    assert get_response.status_code == 400
    assert (
        "benchmark_role must be the canonical value descriptive_reference_only"
        in get_response.json()["detail"]
    )


def test_cross_sectional_research_reload_fails_closed_on_response_identity_mismatch(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    _set_cross_sectional_research_reload_response_identity(
        artifact_path,
        artifact_id="cross_sectional_research_artifact_deadbeefdeadbeef",
    )

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")

    assert get_response.status_code == 400
    assert get_response.json() == {"detail": "cross-sectional research artifact_id does not match canonical artifact content"}


def test_cross_sectional_research_load_fails_closed_on_malformed_status_metadata_v1(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["status_metadata_v1"]["artifact_status"] = " complete "
    artifact_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")

    assert get_response.status_code == 400
    assert "Input should be 'complete', 'degraded', 'unknown' or 'unsupported'" in get_response.json()["detail"]


def test_cross_sectional_research_catalog_fails_closed_on_summary_provenance_mismatch(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["walk_forward_summary"]["provenance"]["benchmark_symbol"] = "QQQ"
    artifact_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    catalog_response = client.get("/strategy-lab/cross-sectional-research/catalog")

    assert catalog_response.status_code == 400
    assert (
        "walk_forward_summary.provenance.benchmark_symbol must match request.benchmark.benchmark_symbol"
        in catalog_response.json()["detail"]
    )


def test_cross_sectional_research_recent_fails_closed_on_summary_symbol_list_contradiction(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["holdout_summary"]["top_ranked_symbols"] = ["AAA", "AAA"]
    artifact_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    recent_response = client.get("/strategy-lab/cross-sectional-research/recent")

    assert recent_response.status_code == 400
    assert "top_ranked_symbols must not contain duplicates" in recent_response.json()["detail"]


def test_cross_sectional_research_reload_accepts_degraded_artifact_with_complete_coverage(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = _rekey_cross_sectional_research_artifact_payload(
        tmp_path,
        response.json()["artifact_id"],
        lambda payload: (
            payload["status_metadata_v1"].update(
                {
                    "artifact_status": "degraded",
                    "diagnostics_status": "invalid",
                }
            ),
            payload["provenance"].update({"alpha_diagnostics_status": "invalid"}),
        ),
    )

    reloaded = load_cross_sectional_research_artifact(artifact_id)
    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")
    catalog_response = client.get(
        "/strategy-lab/cross-sectional-research/catalog?artifact_status=degraded&coverage_status=complete"
    )
    recent_response = client.get(
        "/strategy-lab/cross-sectional-research/recent?artifact_status=degraded&coverage_status=complete"
    )

    assert reloaded.status_metadata_v1.artifact_status == "degraded"
    assert reloaded.status_metadata_v1.diagnostics_status == "invalid"
    assert reloaded.status_metadata_v1.coverage_status == "complete"
    assert get_response.status_code == 200
    assert get_response.json()["artifact"]["status_metadata_v1"] == {
        "artifact_status": "degraded",
        "diagnostics_status": "invalid",
        "coverage_status": "complete",
    }
    assert catalog_response.status_code == 200
    assert [item["artifact_id"] for item in catalog_response.json()["items"]] == [artifact_id]
    assert recent_response.status_code == 200
    assert [item["artifact_id"] for item in recent_response.json()["items"]] == [artifact_id]


def test_cross_sectional_research_reload_still_rejects_unsupported_status_combinations(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["status_metadata_v1"]["diagnostics_status"] = "invalid"
    payload["status_metadata_v1"]["artifact_status"] = "complete"
    artifact_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")

    assert get_response.status_code == 400
    assert "artifact_status must be degraded when diagnostics_status is invalid" in get_response.json()["detail"]


def test_cross_sectional_research_reload_hydrates_documented_legacy_missing_metadata_only(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    legacy_artifact_id = _rekey_legacy_cross_sectional_research_artifact_payload(
        tmp_path,
        response.json()["artifact_id"],
        lambda payload: (payload.pop("status_metadata_v1"), payload.pop("provenance_metadata_v1")),
    )

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{legacy_artifact_id}")
    catalog_response = client.get("/strategy-lab/cross-sectional-research/catalog")
    recent_response = client.get("/strategy-lab/cross-sectional-research/recent")

    assert get_response.status_code == 200
    assert get_response.json()["artifact_id"] == legacy_artifact_id
    assert get_response.json()["artifact"]["status_metadata_v1"] == {
        "artifact_status": "complete",
        "diagnostics_status": "ok",
        "coverage_status": "complete",
    }
    assert get_response.json()["artifact"]["provenance_metadata_v1"] == {
        "input_source_kind": "direct_snapshot_input",
        "replay_provenance_status": "absent",
        "benchmark_source_kind": "request_benchmark_reference",
        "alpha_source_kind": "optimizer_alpha_package",
    }
    assert catalog_response.status_code == 400
    assert "status_metadata_v1: Field required" in catalog_response.json()["detail"]
    assert recent_response.status_code == 400
    assert "status_metadata_v1: Field required" in recent_response.json()["detail"]


def test_cross_sectional_research_reload_rejects_inconsistent_present_provenance_metadata(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["provenance_metadata_v1"].update(
        {
            "input_source_kind": "replay_snapshot_input",
            "replay_provenance_status": "present",
        }
    )
    artifact_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")

    assert get_response.status_code == 400
    assert (
        "provenance_metadata_v1.input_source_kind must match persisted request source inputs"
        in get_response.json()["detail"]
    )


def test_cross_sectional_research_load_fails_closed_on_malformed_provenance_metadata_v1(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    request_payload = _cross_sectional_research_request_payload()
    request_payload["replay_id"] = "replay-123"
    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=request_payload,
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["provenance_metadata_v1"]["replay_provenance_status"] = " absent "
    artifact_path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True),
        encoding="utf-8",
    )

    get_response = client.get(f"/strategy-lab/cross-sectional-research/artifacts/{artifact_id}")

    assert get_response.status_code == 400
    assert "Input should be 'present', 'absent', 'unknown' or 'unsupported'" in get_response.json()["detail"]


def test_cross_sectional_research_recent_fails_closed_on_unsupported_kind(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    _set_cross_sectional_research_reload_response_identity(
        artifact_path,
        artifact_kind="unsupported_cross_sectional_research_run",
    )

    recent_response = client.get("/strategy-lab/cross-sectional-research/recent")

    assert recent_response.status_code == 400
    assert recent_response.json() == {"detail": "unsupported cross-sectional research artifact kind"}


def test_cross_sectional_research_catalog_fails_closed_on_unsupported_schema_version(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/cross-sectional-research/run",
        json=_cross_sectional_research_request_payload(),
    )
    assert response.status_code == 200
    artifact_id = response.json()["artifact_id"]
    artifact_path = tmp_path / f"{artifact_id}.json"
    _set_cross_sectional_research_reload_response_identity(
        artifact_path,
        schema_version="cross_sectional_research_artifact_v999",
    )

    catalog_response = client.get("/strategy-lab/cross-sectional-research/catalog")

    assert catalog_response.status_code == 400
    assert catalog_response.json() == {"detail": "unsupported cross-sectional research schema_version"}


@pytest.mark.parametrize(
    ("query", "expected_detail"),
    [
        ("dataset_version=%20%20%20", "discovery filters must not contain blank string values"),
        (
            "benchmark_symbol=%20spy%20",
            "benchmark_symbol must be canonical uppercase without surrounding whitespace",
        ),
    ],
)
def test_cross_sectional_research_discovery_filters_reject_non_canonical_strings(
    tmp_path: Path,
    mocker,
    query: str,
    expected_detail: str,
) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    catalog_response = client.get(f"/strategy-lab/cross-sectional-research/catalog?{query}")
    recent_response = client.get(f"/strategy-lab/cross-sectional-research/recent?{query}")

    assert catalog_response.status_code == 400
    assert catalog_response.json() == {"detail": expected_detail}
    assert recent_response.status_code == 400
    assert recent_response.json() == {"detail": expected_detail}


def test_cross_sectional_research_discovery_filters_support_backend_owned_metadata_fields(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    direct_request = _cross_sectional_research_request_payload()
    replay_request = _cross_sectional_research_request_payload()
    replay_request["dataset_version"] = "alpha_quality_dataset_demo_v2"
    replay_request["source_name"] = "research_replay_input"
    replay_request["replay_id"] = "replay-123"

    direct_response = client.post("/strategy-lab/cross-sectional-research/run", json=direct_request)
    replay_response = client.post("/strategy-lab/cross-sectional-research/run", json=replay_request)

    assert direct_response.status_code == 200
    assert replay_response.status_code == 200

    recent_response = client.get(
        "/strategy-lab/cross-sectional-research/recent?"
        "methodology_family_id=cross_sectional_research_family_v1&"
        "methodology_family_version=v1&"
        "active_methodology_version=v1&"
        "alpha_package_version=alpha_quality_v1&"
        "alpha_methodology_id=alpha_quality_v1_methodology&"
        "alpha_input_contract_id=alpha_quality_v1_pit_fundamentals_v1&"
        "score_basis=optimizer_alpha_package.final_score&"
        "benchmark_role=descriptive_reference_only&"
        "partition_rule=effective_date_before_holdout_start_else_holdout&"
        "output_shape=compact_summary_only&"
        "artifact_status=complete&"
        "diagnostics_status=ok&"
        "coverage_status=complete&"
        "input_source_kind=direct_snapshot_input&"
        "replay_provenance_status=absent&"
        "benchmark_source_kind=request_benchmark_reference&"
        "alpha_source_kind=optimizer_alpha_package"
    )
    replay_filtered_catalog = client.get(
        "/strategy-lab/cross-sectional-research/catalog?"
        "input_source_kind=replay_snapshot_input&"
        "replay_provenance_status=present&"
        "artifact_status=complete"
    )

    assert recent_response.status_code == 200
    assert replay_filtered_catalog.status_code == 200
    assert [item["artifact_id"] for item in recent_response.json()["items"]] == [direct_response.json()["artifact_id"]]
    assert [item["artifact_id"] for item in replay_filtered_catalog.json()["items"]] == [replay_response.json()["artifact_id"]]


@pytest.mark.parametrize(
    ("query", "expected_detail"),
    [
        (
            "score_basis= optimizer_alpha_package.final_score ",
            "score_basis must be the canonical value optimizer_alpha_package.final_score",
        ),
        (
            "partition_rule=wrong_rule",
            "partition_rule must be the canonical value effective_date_before_holdout_start_else_holdout",
        ),
    ],
)
def test_cross_sectional_research_discovery_filters_reject_unsupported_metadata_values(
    tmp_path: Path,
    mocker,
    query: str,
    expected_detail: str,
) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    catalog_response = client.get(f"/strategy-lab/cross-sectional-research/catalog?{query}")
    recent_response = client.get(f"/strategy-lab/cross-sectional-research/recent?{query}")

    assert catalog_response.status_code == 400
    assert catalog_response.json() == {"detail": expected_detail}
    assert recent_response.status_code == 400
    assert recent_response.json() == {"detail": expected_detail}


def test_cross_sectional_research_descriptive_metadata_filters_do_not_change_recent_ordering(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    direct_request = _cross_sectional_research_request_payload()
    replay_request = _cross_sectional_research_request_payload()
    replay_request["dataset_version"] = "alpha_quality_dataset_demo_v2"
    replay_request["source_name"] = "research_replay_input"
    replay_request["replay_id"] = "replay-123"

    direct_response = client.post("/strategy-lab/cross-sectional-research/run", json=direct_request)
    replay_response = client.post("/strategy-lab/cross-sectional-research/run", json=replay_request)

    assert direct_response.status_code == 200
    assert replay_response.status_code == 200

    direct_path = tmp_path / f"{direct_response.json()['artifact_id']}.json"
    replay_path = tmp_path / f"{replay_response.json()['artifact_id']}.json"
    _set_cross_sectional_artifact_persisted_at(direct_path, "2026-04-24T09:30:00Z")
    _set_cross_sectional_artifact_persisted_at(replay_path, "2026-04-25T09:30:00Z")

    unfiltered = client.get("/strategy-lab/cross-sectional-research/recent")
    filtered = client.get(
        "/strategy-lab/cross-sectional-research/recent?input_source_kind=replay_snapshot_input"
    )

    assert unfiltered.status_code == 200
    assert filtered.status_code == 200
    assert [item["artifact_id"] for item in unfiltered.json()["items"][:2]] == [
        replay_response.json()["artifact_id"],
        direct_response.json()["artifact_id"],
    ]
    assert [item["artifact_id"] for item in filtered.json()["items"]] == [replay_response.json()["artifact_id"]]
    assert filtered.json()["items"][0]["recent_order_persisted_at"] == "2026-04-25T09:30:00Z"


def test_cross_sectional_research_metadata_filters_return_empty_state_when_no_persisted_rows_match(tmp_path: Path, mocker) -> None:
    mocker.patch(
        "app.services.cross_sectional_research_artifact_service.get_settings",
        return_value=SimpleNamespace(cross_sectional_research_artifact_dir=str(tmp_path)),
    )
    client = TestClient(app)

    response = client.post("/strategy-lab/cross-sectional-research/run", json=_cross_sectional_research_request_payload())

    assert response.status_code == 200

    recent_response = client.get(
        "/strategy-lab/cross-sectional-research/recent?input_source_kind=replay_snapshot_input"
    )
    catalog_response = client.get(
        "/strategy-lab/cross-sectional-research/catalog?artifact_status=unsupported"
    )

    assert recent_response.status_code == 200
    assert catalog_response.status_code == 200
    assert recent_response.json()["items"] == []
    assert catalog_response.json()["items"] == []


def test_dashboard_exact_slice_policy_does_not_change_strategy_lab_payloads() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 3,
            "top_n": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["investor_economics_status"] == {
        "status": "withheld",
        "reason": "withheld_unverified_total_return_equivalence",
    }
    assert payload["metrics"]["benchmark_return_pct"] is None
    assert payload["metrics"]["excess_return_pct"] is None
    assert payload["metrics"]["max_drawdown_pct"] is None


def test_etf_cross_sectional_momentum_route_rejects_invalid_top_n() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK", "XLF"],
            "benchmark_symbol": "SPY",
            "lookback_months": 3,
            "top_n": 3,
        },
    )

    assert response.status_code == 400


def test_etf_cross_sectional_momentum_supports_long_quarter_lookbacks() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK", "XLF", "XLV", "XLE", "XLI"],
            "benchmark_symbol": "SPY",
            "lookback_months": 36,
            "top_n": 2,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["observations"]) >= 48


def test_etf_cross_sectional_momentum_uses_dated_leader_holdings_snapshots() -> None:
    client = TestClient(app)

    response = client.post(
        "/strategy-lab/etf-cross-sectional-momentum",
        json={
            "universe": ["XLK"],
            "benchmark_symbol": "SPY",
            "lookback_months": 12,
            "top_n": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    constituent_sets = [tuple(item["symbol"] for item in row["constituents"]) for row in payload["leader_internals"] if row["constituents"]]
    assert len(set(constituent_sets)) >= 2


def test_rows_to_monthly_bars_keeps_latest_row_per_month() -> None:
    bars = _rows_to_monthly_bars(
        [
            {"date": "2024-01-02", "price": 100.0, "volume": 1000},
            {"date": "2024-01-31", "price": 105.0, "volume": 1200},
            {"date": "2024-02-15", "price": 110.0, "volume": 1300},
        ]
    )

    assert [bar.date for bar in bars] == ["2024-01-31", "2024-02-15"]
    assert [bar.close for bar in bars] == [105.0, 110.0]


def test_normalize_fmp_holdings_converts_weight_percentages() -> None:
    rows = _normalize_fmp_holdings(
        [
            {"asset": "MSFT", "name": "Microsoft", "weightPercentage": 6.0},
            {"asset": "AAPL", "name": "Apple", "weightPercentage": 7.5},
        ]
    )

    assert [row["symbol"] for row in rows] == ["AAPL", "MSFT"]
    assert rows[0]["weight"] == 0.075


def test_normalize_fmp_holdings_snapshot_reads_snapshot_date() -> None:
    snapshot = _normalize_fmp_holdings_snapshot(
        [
            {"asset": "MSFT", "name": "Microsoft", "weightPercentage": 6.0, "updated": "2026-04-08 11:04:21"},
            {"asset": "AAPL", "name": "Apple", "weightPercentage": 7.5, "updated": "2026-04-08 11:04:21"},
        ]
    )

    assert snapshot is not None
    assert snapshot.snapshot_date == "2026-04-08"
    assert snapshot.holdings[0]["symbol"] == "AAPL"


def test_normalize_fmp_holdings_snapshot_returns_none_without_updated_timestamp() -> None:
    snapshot = _normalize_fmp_holdings_snapshot(
        [
            {"asset": "MSFT", "name": "Microsoft", "weightPercentage": 6.0},
        ]
    )

    assert snapshot is None


def test_blended_momentum_uses_12_1_and_6_1_style_formula_when_history_is_long_enough() -> None:
    closes = [100, 102, 104, 106, 108, 110, 112, 115, 118, 121, 124, 127, 130]
    bars = [BarRecord(date=f"2025-{index + 1:02d}-28", open=value, high=value, low=value, close=value, volume=1000) for index, value in enumerate(closes)]

    result = _blended_momentum(bars)

    expected_12_1 = (closes[-2] / closes[0]) - 1
    expected_6_1 = (closes[-2] / closes[-7]) - 1
    assert round(result, 8) == round((0.6 * expected_12_1) + (0.4 * expected_6_1), 8)


def test_blended_momentum_falls_back_conservatively_on_shorter_history() -> None:
    closes = [100, 103, 106, 109, 112, 115]
    bars = [BarRecord(date=f"2025-{index + 1:02d}-28", open=value, high=value, low=value, close=value, volume=1000) for index, value in enumerate(closes)]

    result = _blended_momentum(bars)

    assert round(result, 8) == round((closes[-1] / closes[0]) - 1, 8)


def test_median_dollar_volume_uses_logged_median() -> None:
    bars = [
        BarRecord(date="2025-01-31", open=10, high=10, low=10, close=10, volume=100),
        BarRecord(date="2025-02-28", open=10, high=10, low=10, close=10, volume=100),
        BarRecord(date="2025-03-31", open=10, high=10, low=10, close=10, volume=10000),
    ]

    result = _median_dollar_volume(bars)

    assert round(result, 8) == round(math.log(1001), 8)


def test_median_dollar_volume_returns_zero_when_volume_is_missing_or_zero() -> None:
    bars = [
        BarRecord(date="2025-01-31", open=10, high=10, low=10, close=10, volume=None),
        BarRecord(date="2025-02-28", open=10, high=10, low=10, close=10, volume=0),
    ]

    result = _median_dollar_volume(bars)

    assert result == 0.0


def test_etf_ranking_short_but_valid_aligned_history_uses_conservative_momentum_fallback(monkeypatch: MonkeyPatch) -> None:
    bars_by_symbol = {
        "AAA": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=103, high=103, low=103, close=103, volume=1000),
            BarRecord(date="2025-03-31", open=106, high=106, low=106, close=106, volume=1000),
            BarRecord(date="2025-04-30", open=109, high=109, low=109, close=109, volume=1000),
        ],
        "BBB": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=1000),
            BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=1000),
        ],
        "SPY": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-03-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-04-30", open=106, high=106, low=106, close=106, volume=1000),
        ],
    }

    def fake_load_base_data(symbols, benchmark, lookback_months, prefer_live_data, dataset_catalog):
        return strategy_lab_module._StrategyBaseData(
            bars_by_symbol={symbol: bars_by_symbol[symbol] for symbol in [*symbols, benchmark]},
            price_source_label="test-short-history",
            internals_mode="sample",
            price_history_status="sample",
        )

    monkeypatch.setattr(strategy_lab_module, "_load_base_data", fake_load_base_data)

    result = build_etf_ranking_analysis(universe=["AAA", "BBB"], benchmark_symbol="SPY", lookback_months=3)

    aaa = next(row for row in result.ranked_universe if row.symbol == "AAA")
    expected_momentum = ((109 / 100) - 1) * 100
    assert round(aaa.component_scores["momentum"].raw_value, 4) == round(expected_momentum, 4)


def test_etf_ranking_zero_volume_history_keeps_liquidity_raw_value_at_zero(monkeypatch: MonkeyPatch) -> None:
    zero_volume_bars = [
        BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=0),
        BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=0),
        BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=0),
        BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=0),
    ]
    bars_by_symbol = {
        "AAA": zero_volume_bars,
        "BBB": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-03-31", open=104, high=104, low=104, close=104, volume=1000),
            BarRecord(date="2025-04-30", open=106, high=106, low=106, close=106, volume=1000),
        ],
        "SPY": [
            BarRecord(date="2025-01-31", open=100, high=100, low=100, close=100, volume=1000),
            BarRecord(date="2025-02-28", open=101, high=101, low=101, close=101, volume=1000),
            BarRecord(date="2025-03-31", open=102, high=102, low=102, close=102, volume=1000),
            BarRecord(date="2025-04-30", open=103, high=103, low=103, close=103, volume=1000),
        ],
    }

    def fake_load_base_data(symbols, benchmark, lookback_months, prefer_live_data, dataset_catalog):
        return strategy_lab_module._StrategyBaseData(
            bars_by_symbol={symbol: bars_by_symbol[symbol] for symbol in [*symbols, benchmark]},
            price_source_label="test-zero-volume",
            internals_mode="sample",
            price_history_status="sample",
        )

    monkeypatch.setattr(strategy_lab_module, "_load_base_data", fake_load_base_data)

    result = build_etf_ranking_analysis(universe=["AAA", "BBB"], benchmark_symbol="SPY", lookback_months=3)

    aaa = next(row for row in result.ranked_universe if row.symbol == "AAA")
    assert aaa.component_scores["liquidity"].raw_value == 0.0
class _ReplacementFakeRegistry:
    def __init__(self, instruments):
        self._instruments = instruments

    def get_instrument(self, symbol: str):
        return self._instruments.get(symbol)


class _ReplacementFakeMarketData:
    def __init__(self, histories):
        self._histories = histories

    def get_historical_prices_for_symbols(self, symbols, from_date, to_date):  # noqa: ANN001
        return {symbol: self._histories.get(symbol, []) for symbol in symbols}

    def get_last_fetch_meta(self, symbol: str):
        return {"resolved_symbol": symbol, "cached": True}


def _replacement_instrument(symbol: str):
    from app.schemas.research import Instrument

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


def _replacement_history(days: int, *, start_price: float = 100.0, step: float = 1.0, volume: float = 1000.0) -> list[dict]:
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


def _patch_replacement_ranking_dependencies(mocker) -> None:
    histories = {
        "BASE": _replacement_history(260),
        "ETF1": _replacement_history(260, step=0.5),
        "ETF2": _replacement_history(260, step=0.25),
    }
    instruments = {symbol: _replacement_instrument(symbol) for symbol in histories}
    mocker.patch.object(replacement_ranking_module, "InstrumentRegistry", return_value=_ReplacementFakeRegistry(instruments))
    mocker.patch.object(replacement_ranking_module, "MarketDataService", return_value=_ReplacementFakeMarketData(histories))
