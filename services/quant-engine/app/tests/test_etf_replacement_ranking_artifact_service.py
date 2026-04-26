from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.research import IntentBoundEtfReplacementRankingArtifact
from app.schemas.research import RankingArtifactPreflightResponse
from app.services import replacement_ranking as replacement_ranking_module
from app.services.replacement_ranking import build_intent_bound_etf_replacement_ranking
from app.services.replacement_ranking_artifact_service import (
    ReplacementRankingArtifactMissingFileError,
    ReplacementRankingArtifactNonObjectPayloadError,
    ReplacementRankingArtifactSchemaValidationError,
    ReplacementRankingArtifactStore,
    build_replacement_ranking_consumer_handoff,
    build_stable_replacement_ranking_artifact,
    load_replacement_ranking_artifact,
)
from app.services.ranking_artifact_open_service import RankingArtifactOpenService, open_ranking_artifact, preflight_ranking_artifact


def _build_request(*, seeded_symbols: list[str], candidate_symbol: str = "ETF1"):
    from app.schemas.research import IntentBoundEtfReplacementRankingRequest, IntentBoundReplacementIntent, IntentBoundSeedContext

    return IntentBoundEtfReplacementRankingRequest(
        replacement_intent=IntentBoundReplacementIntent(
            draft_id="draft-1",
            workspace_id="workspace-1",
            base_node_id="node-1",
            base_symbol="BASE",
            candidate_symbol=candidate_symbol,
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
            seeded_symbols=seeded_symbols,
        ),
    )


def _instrument(symbol: str):
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


def _build_response(monkeypatch: pytest.MonkeyPatch):
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))
    return build_intent_bound_etf_replacement_ranking(_build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]))


def test_build_stable_replacement_ranking_artifact_includes_grouped_contract_and_lineage(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = build_stable_replacement_ranking_artifact(_build_response(monkeypatch))

    assert isinstance(artifact, IntentBoundEtfReplacementRankingArtifact)
    assert artifact.schema_version == "intent_bound_etf_replacement_ranking_artifact_v1"
    assert artifact.artifact_id.startswith("intent_bound_etf_replacement_ranking_artifact_")
    assert artifact.lineage.base_symbol == "BASE"
    assert artifact.lineage.candidate_symbol == "ETF1"
    assert artifact.lineage.workspace_id == "workspace-1"
    assert artifact.request_context.base_symbol == artifact.lineage.base_symbol
    assert artifact.request.normalized_request == artifact.normalized_request
    assert artifact.submitted_request.replacement_intent.base_symbol == "BASE"
    assert artifact.normalized_request.seeded_symbols == ["BASE", "ETF1", "ETF2"]


def test_replacement_ranking_artifact_id_is_stable_for_same_content(monkeypatch: pytest.MonkeyPatch) -> None:
    first = build_stable_replacement_ranking_artifact(_build_response(monkeypatch))
    second = build_stable_replacement_ranking_artifact(_build_response(monkeypatch))

    assert first.artifact_id == second.artifact_id


def test_load_replacement_ranking_artifact_rejects_corrupted_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ReplacementRankingArtifactStore(str(tmp_path))
    artifact = store.persist(build_stable_replacement_ranking_artifact(_build_response(monkeypatch)))
    artifact_path = tmp_path / f"{artifact.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["artifact_id"] = "intent_bound_etf_replacement_ranking_artifact_wrong"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ValueError, match="replacement ranking artifact_id does not match canonical artifact content"):
        load_replacement_ranking_artifact(artifact.artifact_id, store=store)


def test_load_replacement_ranking_artifact_rejects_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ReplacementRankingArtifactStore(str(tmp_path))
    artifact = store.persist(build_stable_replacement_ranking_artifact(_build_response(monkeypatch)))
    artifact_path = tmp_path / f"{artifact.artifact_id}.json"
    artifact_path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid persisted replacement ranking artifact json"):
        load_replacement_ranking_artifact(artifact.artifact_id, store=store)


def test_load_replacement_ranking_artifact_rejects_missing_file(tmp_path: Path) -> None:
    store = ReplacementRankingArtifactStore(str(tmp_path))

    with pytest.raises(ReplacementRankingArtifactMissingFileError, match="missing persisted replacement ranking artifact file"):
        load_replacement_ranking_artifact("intent_bound_etf_replacement_ranking_artifact_missing", store=store)


def test_load_replacement_ranking_artifact_rejects_non_object_payload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ReplacementRankingArtifactStore(str(tmp_path))
    artifact = store.persist(build_stable_replacement_ranking_artifact(_build_response(monkeypatch)))
    artifact_path = tmp_path / f"{artifact.artifact_id}.json"
    artifact_path.write_text("[]", encoding="utf-8")

    with pytest.raises(ReplacementRankingArtifactNonObjectPayloadError, match="payload must be a json object"):
        load_replacement_ranking_artifact(artifact.artifact_id, store=store)


def test_load_replacement_ranking_artifact_rejects_schema_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ReplacementRankingArtifactStore(str(tmp_path))
    artifact = store.persist(build_stable_replacement_ranking_artifact(_build_response(monkeypatch)))
    artifact_path = tmp_path / f"{artifact.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload.pop("status")
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ReplacementRankingArtifactSchemaValidationError, match="failed schema validation"):
        load_replacement_ranking_artifact(artifact.artifact_id, store=store)


def test_load_replacement_ranking_artifact_rejects_lineage_mismatch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = ReplacementRankingArtifactStore(str(tmp_path))
    artifact = store.persist(build_stable_replacement_ranking_artifact(_build_response(monkeypatch)))
    artifact_path = tmp_path / f"{artifact.artifact_id}.json"
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    payload["lineage"]["base_symbol"] = "OTHER"
    artifact_path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True), encoding="utf-8")

    with pytest.raises(ValueError, match="lineage.base_symbol must match request_context.base_symbol"):
        load_replacement_ranking_artifact(artifact.artifact_id, store=store)


def test_replacement_ranking_catalog_row_contract_rejects_kind_summary_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    artifact = build_stable_replacement_ranking_artifact(_build_response(monkeypatch))

    with pytest.raises(
        ValueError,
        match="intent_bound_etf_replacement_ranking rows must populate only replacement_summary",
    ):
        from app.schemas.research import RankingArtifactCatalogEtfSummary, RankingArtifactCatalogRow, RankingArtifactCatalogRowMetadata

        RankingArtifactCatalogRow(
            artifact_kind="intent_bound_etf_replacement_ranking",
            artifact_id=artifact.artifact_id,
            schema_version=artifact.schema_version,
            ranking_id=artifact.ranking_id,
            methodology_id=artifact.methodology_id,
            as_of_date=artifact.run_metadata.as_of_date,
            ranking_basis_date=artifact.run_metadata.ranking_basis_date,
            recent_order_primary_date=artifact.run_metadata.ranking_basis_date,
            recent_order_secondary_date=artifact.run_metadata.as_of_date,
            recent_order_artifact_id=artifact.artifact_id,
            metadata=RankingArtifactCatalogRowMetadata(
                metadata_provenance="persisted_artifact_body",
                matched_metadata_provenance="persisted_artifact_body",
                recency_same_day_provenance="artifact_id",
            ),
            etf_summary=RankingArtifactCatalogEtfSummary(
                benchmark_symbol="SPY",
                lookback_months=6,
                effective_peer_group="Sector UCITS ETF",
                universe_size=3,
                evaluated_universe_size=2,
                confidence="high",
            ),
            replacement_summary=None,
        )


def test_replacement_ranking_open_service_preflight_and_open_use_persisted_artifact_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ReplacementRankingArtifactStore(str(tmp_path))
    artifact = store.persist(build_stable_replacement_ranking_artifact(_build_response(monkeypatch)))
    service = RankingArtifactOpenService(replacement_store=store)

    preflight = preflight_ranking_artifact(artifact.artifact_id, service=service)

    assert preflight.artifact.model_dump(mode="json") == {
        "artifact_kind": "intent_bound_etf_replacement_ranking",
        "artifact_id": artifact.artifact_id,
        "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
        "ranking_id": artifact.ranking_id,
        "methodology_id": artifact.run_metadata.methodology_id,
        "as_of_date": artifact.run_metadata.as_of_date,
        "ranking_basis_date": artifact.run_metadata.ranking_basis_date,
    }
    assert preflight.open_handoff.model_dump(mode="json") == {
        "handoff_kind": "ranking_artifact_open_handoff_v1",
        "artifact_kind": "intent_bound_etf_replacement_ranking",
        "artifact_id": artifact.artifact_id,
        "schema_version": "intent_bound_etf_replacement_ranking_artifact_v1",
    }
    assert preflight.eligibility.model_dump(mode="json") == {
        "review_truth_basis": "authoritative_persisted_ranking_artifact",
        "review_scope": "artifact_backed_review_only",
        "open_supported": True,
        "replay_eligible": True,
        "consumer_handoff_supported": True,
        "ineligibility_reason": None,
    }

    opened = open_ranking_artifact(preflight.open_handoff, service=service)

    assert opened.review_payload_kind == "intent_bound_etf_replacement_ranking_review_payload_v1"
    assert opened.review_payload.review_truth_basis == "authoritative_persisted_ranking_artifact"
    assert opened.review_payload.review_scope == "artifact_backed_review_only"
    assert opened.review_payload.artifact.model_dump(mode="json") == artifact.model_dump(mode="json")
    assert opened.consumer_handoff.model_dump(mode="json") == build_replacement_ranking_consumer_handoff(
        artifact
    ).model_dump(mode="json")


def test_build_replacement_ranking_consumer_handoff_fails_closed_for_unavailable_artifact(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    histories = {"BASE": _history(260), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))
    artifact = build_stable_replacement_ranking_artifact(
        build_intent_bound_etf_replacement_ranking(_build_request(seeded_symbols=["BASE", "ETF2"], candidate_symbol="ETF1"))
    )

    with pytest.raises(ValueError, match="replacement ranking artifact is unreplayable"):
        build_replacement_ranking_consumer_handoff(artifact)


def test_replacement_ranking_open_service_preflight_marks_unreplayable_replacement_as_ineligible(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    histories = {"BASE": _history(260), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))
    store = ReplacementRankingArtifactStore(str(tmp_path))
    artifact = store.persist(
        build_stable_replacement_ranking_artifact(
            build_intent_bound_etf_replacement_ranking(
                _build_request(seeded_symbols=["BASE", "ETF2"], candidate_symbol="ETF1")
            )
        )
    )
    service = RankingArtifactOpenService(replacement_store=store)

    preflight = preflight_ranking_artifact(artifact.artifact_id, service=service)

    assert preflight.eligibility.model_dump(mode="json") == {
        "review_truth_basis": "authoritative_persisted_ranking_artifact",
        "review_scope": "artifact_backed_review_only",
        "open_supported": False,
        "replay_eligible": False,
        "consumer_handoff_supported": False,
        "ineligibility_reason": "replacement ranking artifact is unreplayable",
    }


def test_replacement_ranking_preflight_model_rejects_supported_without_consumer_handoff() -> None:
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


def test_build_replacement_ranking_consumer_handoff_rejects_candidate_lineage_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = build_stable_replacement_ranking_artifact(_build_response(monkeypatch))
    drifted_artifact = artifact.model_copy(
        update={
            "ranked_candidates": [
                artifact.ranked_candidates[0].model_copy(update={"seed_methodology_id": "other_methodology"}),
                *artifact.ranked_candidates[1:],
            ]
        }
    )

    with pytest.raises(
        ValueError,
        match="selected_candidate.seed_methodology_id must match seed_methodology_id",
    ):
        build_replacement_ranking_consumer_handoff(drifted_artifact)
