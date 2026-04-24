import math
from pathlib import Path
from types import SimpleNamespace
import json

from fastapi.testclient import TestClient
import pytest
from pytest import MonkeyPatch

from app.api.main import app
from app.schemas.research import BarRecord
from app.services.etf_ranking_artifact_service import load_etf_ranking_artifact
from app.services import strategy_lab as strategy_lab_module
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
