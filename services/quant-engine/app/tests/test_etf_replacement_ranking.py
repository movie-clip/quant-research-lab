from __future__ import annotations

from datetime import date, timedelta
from typing import cast

from fastapi.testclient import TestClient
import pytest
from pytest import MonkeyPatch

from app.api.main import app
from app.schemas.ranking import RankingEffectiveInputsBase, RankingRequestContextBase, RankingRunMetadataBase
from app.schemas.research import AssetClass, Instrument, IntentBoundEtfReplacementEffectiveInputs, IntentBoundEtfReplacementRankingRequest, IntentBoundEtfReplacementRankingRunMetadata, IntentBoundEtfReplacementRawFactors, IntentBoundEtfReplacementRequestContext, IntentBoundReplacementIntent, IntentBoundSeedContext
from app.services import replacement_ranking as replacement_ranking_module


def _build_request(*, seeded_symbols: list[str], candidate_symbol: str = "ETF1") -> IntentBoundEtfReplacementRankingRequest:
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


def _instrument(symbol: str, asset_class: AssetClass = "etf", category: str = "Sector UCITS ETF") -> Instrument:
    return Instrument(
        instrument_id=f"instrument-{symbol.lower()}",
        symbol=symbol,
        name=symbol,
        asset_class=asset_class,
        kind="spot",
        sector="Technology",
        category=category,
        exchange="TEST",
        currency="USD",
    )


def _history(days: int, *, start_price: float = 100.0, step: float = 1.0, volume: float = 1000.0, include_adjusted: bool = True) -> list[dict]:
    end = date(2025, 12, 31)
    start = end - timedelta(days=days - 1)
    rows: list[dict] = []
    for index in range(days):
        price = start_price + (index * step)
        row = {
            "date": (start + timedelta(days=index)).isoformat(),
            "close": round(price, 6),
            "volume": volume,
        }
        if include_adjusted:
            row["adjClose"] = round(price, 6)
        rows.append(row)
    return rows


def _assert_shared_route_ranking_payload(payload: dict) -> None:
    assert payload["ranking_id"] == "intent_bound_etf_replacement_ranking_v1"
    assert payload["methodology_id"] == "intent_bound_etf_replacement_ranking_methodology_v1"
    assert payload["request_hash"]
    assert payload["eligible_count"] == 2
    assert payload["excluded_count"] == 1
    assert [row["symbol"] for row in payload["ranked_candidates"]] == ["ETF1", "ETF2"]
    assert [row["symbol"] for row in payload["excluded_candidates"]] == ["BASE"]
    assert payload["request_context"]["universe"] == ["BASE", "ETF1", "ETF2"]
    assert payload["request_context"]["base_symbol"] == "BASE"
    assert payload["request_context"]["candidate_symbol"] == "ETF1"
    assert payload["submitted_request"]["replacement_intent"]["base_symbol"] == "BASE"
    assert payload["effective_inputs"]["requested_universe"] == ["BASE", "ETF1", "ETF2"]
    assert payload["effective_inputs"]["evaluated_universe"] == ["ETF1", "ETF2"]
    assert payload["request_context"]["benchmark_symbol"] == "SPY"
    assert payload["request_context"]["lookback_months"] == 6
    assert payload["effective_inputs"]["benchmark_symbol"] == "SPY"
    assert payload["effective_inputs"]["lookback_months"] == 6
    assert payload["effective_inputs"]["price_basis"] == "close"
    assert payload["run_metadata"]["methodology"]
    assert payload["run_metadata"]["as_of_date"] == payload["basis_date"]
    assert payload["run_metadata"]["ranking_basis_date"] == payload["basis_date"]
    assert payload["run_metadata"]["price_basis"] == "close"
    assert payload["run_metadata"]["confidence"] == "high"


class _FakeRegistry:
    def __init__(self, instruments: dict[str, Instrument]) -> None:
        self._instruments = instruments

    def get_instrument(self, symbol: str) -> Instrument | None:
        return self._instruments.get(symbol)


class _FakeMarketData:
    def __init__(self, histories: dict[str, list[dict]]) -> None:
        self._histories = histories

    def get_historical_prices_for_symbols(self, symbols, from_date, to_date):  # noqa: ANN001
        return {symbol: self._histories.get(symbol, []) for symbol in symbols}

    def get_last_fetch_meta(self, symbol: str):
        return {"resolved_symbol": symbol, "cached": True}


class _LiveMetaWithTailGapMarketData(_FakeMarketData):
    def get_last_fetch_meta(self, symbol: str):
        return {"resolved_symbol": symbol, "cached": False}


def test_request_hash_is_stable_for_seed_order(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.4)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    first = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(_build_request(seeded_symbols=["ETF2", "BASE", "ETF1"]))
    second = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(_build_request(seeded_symbols=["ETF1", "ETF2", "BASE"]))

    assert first.request_hash == second.request_hash
    assert first.normalized_request.seeded_symbols == ["BASE", "ETF1", "ETF2"]


def test_etf_only_and_base_symbol_exclusions_are_explicit(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "AAPL": _history(260, step=0.25)}
    instruments = {"BASE": _instrument("BASE"), "ETF1": _instrument("ETF1"), "AAPL": _instrument("AAPL", asset_class=cast(AssetClass, "equity"), category="Equity")}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(_build_request(seeded_symbols=["BASE", "AAPL", "ETF1"]))

    assert result.status == "ok"
    assert [row.symbol for row in result.ranked_candidates] == ["ETF1"]
    excluded = {row.symbol: row.exclusion_reason for row in result.excluded_candidates}
    assert excluded["BASE"] == "symbol matches the incumbent base symbol"
    assert excluded["AAPL"] == "instrument metadata marks AAPL as equity, not etf"


def test_seeded_candidates_only_enforcement_marks_context_mismatch_unavailable(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF2": _history(260, step=0.4)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))
    client = TestClient(app)
    response = client.post(
        "/ranking/etf-replacements",
        json=_build_request(seeded_symbols=["BASE", "ETF2"], candidate_symbol="ETF1").model_dump(mode="json"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["unavailable_reason"] == "replacement intent candidate symbol is not present in the seeded candidate set"


def test_legacy_replacement_ranking_post_route_preserves_non_artifact_contract(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.4)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    client = TestClient(app)
    response = client.post("/ranking/etf-replacements", json=_build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]).model_dump(mode="json"))

    assert response.status_code == 200
    payload = response.json()
    _assert_shared_route_ranking_payload(payload)
    assert payload["request"] == payload["request_context"]
    assert payload["request"]["universe"] == ["BASE", "ETF1", "ETF2"]
    assert "artifact_id" not in payload
    assert "schema_version" not in payload
    assert "lineage" not in payload


def test_strategy_lab_replacement_ranking_post_route_returns_artifact_contract(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.4)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    client = TestClient(app)
    response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]).model_dump(mode="json"),
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_shared_route_ranking_payload(payload)
    assert payload["schema_version"] == "intent_bound_etf_replacement_ranking_artifact_v1"
    assert payload["artifact_id"].startswith("intent_bound_etf_replacement_ranking_artifact_")
    assert payload["request"]["normalized_request"]["seeded_symbols"] == ["BASE", "ETF1", "ETF2"]
    assert payload["request"]["replacement_intent"]["base_symbol"] == "BASE"
    assert payload["request"]["seed_context"]["seeded_symbols"] == ["BASE", "ETF1", "ETF2"]
    assert payload["request"]["prefer_live_data"] is False


def test_legacy_and_artifact_post_routes_preserve_identical_ranking_outputs(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.4)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    client = TestClient(app)
    request_payload = _build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]).model_dump(mode="json")

    legacy_response = client.post("/ranking/etf-replacements", json=request_payload)
    artifact_response = client.post("/strategy-lab/etf-ranking/replacements", json=request_payload)

    assert legacy_response.status_code == 200
    assert artifact_response.status_code == 200

    legacy_payload = legacy_response.json()
    artifact_payload = artifact_response.json()

    for field in (
        "ranking_id",
        "methodology_id",
        "basis_date",
        "status",
        "request_context",
        "submitted_request",
        "normalized_request",
        "effective_inputs",
        "request_hash",
        "run_metadata",
        "eligible_count",
        "excluded_count",
        "ranked_candidates",
        "excluded_candidates",
        "warnings",
        "unavailable_reason",
    ):
        assert legacy_payload[field] == artifact_payload[field]


def test_missing_history_excludes_candidates_with_explicit_reasons(monkeypatch: MonkeyPatch) -> None:
    histories = {
        "BASE": _history(260),
        "ETF1": _history(260, step=0.5),
        "ETF2": _history(200, step=0.25),
        "ETF3": _history(260, step=0.2),
    }
    for row in histories["ETF3"][-60:]:
        row["volume"] = None
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(_build_request(seeded_symbols=["BASE", "ETF1", "ETF2", "ETF3"]))

    assert result.status == "ok"
    assert [row.symbol for row in result.ranked_candidates] == ["ETF1"]
    excluded = {row.symbol: row.exclusion_reason for row in result.excluded_candidates}
    assert excluded["ETF2"] == "candidate lacks required 252d adjusted-price history"
    assert excluded["ETF3"] == "candidate lacks required 60d close-volume history"


def test_score_breakdown_uses_locked_v1_formulas(monkeypatch: MonkeyPatch) -> None:
    history = _history(260, start_price=100.0, step=1.0, volume=1000.0)
    histories = {"BASE": history, "ETF1": history}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(_build_request(seeded_symbols=["BASE", "ETF1"]))
    row = result.ranked_candidates[0]

    one_month_ago = history[-21]["adjClose"]
    twelve_month_anchor = history[-252]["adjClose"]
    six_month_anchor = history[-126]["adjClose"]
    expected_momentum_12_1 = round((one_month_ago / twelve_month_anchor) - 1, 8)
    expected_momentum_6_1 = round((one_month_ago / six_month_anchor) - 1, 8)
    expected_blended = round((0.6 * expected_momentum_12_1) + (0.4 * expected_momentum_6_1), 8)

    assert row.raw_factors is not None
    assert row.raw_factors.momentum_12_1 == expected_momentum_12_1
    assert row.raw_factors.momentum_6_1 == expected_momentum_6_1
    assert row.raw_factors.momentum_blended == expected_blended
    assert row.normalized_scores is not None
    assert row.normalized_scores.momentum == 1.0
    assert row.normalized_scores.realized_volatility == 1.0
    assert row.normalized_scores.max_drawdown == 1.0
    assert row.normalized_scores.liquidity == 1.0
    assert row.composite_score == 1.0


def test_stable_ordering_uses_locked_tie_breaks(monkeypatch: MonkeyPatch) -> None:
    request = _build_request(seeded_symbols=["BASE", "AAA", "BBB", "CCC"], candidate_symbol="AAA")
    monkeypatch.setattr(replacement_ranking_module, "_percentile_rank", lambda *args, **kwargs: 0.5)
    candidates = [
        replacement_ranking_module._EligibleCandidate("AAA", IntentBoundEtfReplacementRawFactors(momentum_12_1=0.1, momentum_6_1=0.1, momentum_blended=0.1, realized_volatility_126d=0.2, max_drawdown_252d=0.15, liquidity_60d=8.0)),
        replacement_ranking_module._EligibleCandidate("BBB", IntentBoundEtfReplacementRawFactors(momentum_12_1=0.1, momentum_6_1=0.1, momentum_blended=0.1, realized_volatility_126d=0.2, max_drawdown_252d=0.10, liquidity_60d=7.0)),
        replacement_ranking_module._EligibleCandidate("CCC", IntentBoundEtfReplacementRawFactors(momentum_12_1=0.1, momentum_6_1=0.1, momentum_blended=0.1, realized_volatility_126d=0.2, max_drawdown_252d=0.10, liquidity_60d=6.0)),
    ]

    ranked = replacement_ranking_module._rank_candidates(candidates, request, "2025-12-31")

    assert [row.symbol for row in ranked] == ["BBB", "CCC", "AAA"]


def test_legacy_route_returns_ranked_and_excluded_candidates(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    client = TestClient(app)
    response = client.post("/ranking/etf-replacements", json=_build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]).model_dump(mode="json"))

    assert response.status_code == 200
    payload = response.json()
    _assert_shared_route_ranking_payload(payload)
    assert payload["request"] == payload["request_context"]
    assert payload["request"]["candidate_symbol"] == "ETF1"
    assert "artifact_id" not in payload
    assert "schema_version" not in payload
    assert "lineage" not in payload


def test_strategy_lab_route_returns_ranked_candidates_with_artifact_fields(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    client = TestClient(app)
    response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]).model_dump(mode="json"),
    )

    assert response.status_code == 200
    payload = response.json()
    _assert_shared_route_ranking_payload(payload)
    assert payload["schema_version"] == "intent_bound_etf_replacement_ranking_artifact_v1"
    assert payload["artifact_id"].startswith("intent_bound_etf_replacement_ranking_artifact_")
    assert payload["request"]["normalized_request"]["seeded_symbols"] == ["BASE", "ETF1", "ETF2"]
    assert payload["request"]["replacement_intent"]["base_symbol"] == "BASE"
    assert payload["request"]["replacement_intent"]["candidate_symbol"] == "ETF1"
    assert payload["lineage"] == {
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
    }


def test_legacy_route_persists_artifact_and_get_by_id_returns_artifact_payload(tmp_path, monkeypatch: MonkeyPatch) -> None:
    import app.services.replacement_ranking_artifact_service as artifact_service_module

    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    monkeypatch.setattr(
        artifact_service_module,
        "get_settings",
        lambda: type("Settings", (), {"replacement_ranking_artifact_dir": str(tmp_path)})(),
    )

    client = TestClient(app)
    post_response = client.post(
        "/ranking/etf-replacements",
        json=_build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]).model_dump(mode="json"),
    )

    assert post_response.status_code == 200
    post_payload = post_response.json()
    persisted_artifact = next(tmp_path.glob("*.json"))
    artifact_id = persisted_artifact.stem
    assert (tmp_path / f"{artifact_id}.json").exists()
    assert "artifact_id" not in post_payload
    assert "schema_version" not in post_payload

    get_response = client.get(f"/ranking/etf-replacements/artifacts/{artifact_id}")

    assert get_response.status_code == 200
    get_payload = get_response.json()
    assert get_payload["artifact_id"] == artifact_id
    assert get_payload["schema_version"] == "intent_bound_etf_replacement_ranking_artifact_v1"
    for field in (
        "ranking_id",
        "methodology_id",
        "basis_date",
        "status",
        "request_context",
        "submitted_request",
        "normalized_request",
        "effective_inputs",
        "request_hash",
        "run_metadata",
        "eligible_count",
        "excluded_count",
        "ranked_candidates",
        "excluded_candidates",
        "warnings",
        "unavailable_reason",
    ):
        assert get_payload[field] == post_payload[field]


def test_strategy_lab_replacement_route_persists_artifact_and_legacy_get_alias_returns_same_payload(tmp_path, monkeypatch: MonkeyPatch) -> None:
    import app.services.replacement_ranking_artifact_service as artifact_service_module

    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    monkeypatch.setattr(
        artifact_service_module,
        "get_settings",
        lambda: type("Settings", (), {"replacement_ranking_artifact_dir": str(tmp_path)})(),
    )

    client = TestClient(app)
    post_response = client.post(
        "/strategy-lab/etf-ranking/replacements",
        json=_build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]).model_dump(mode="json"),
    )

    assert post_response.status_code == 200
    post_payload = post_response.json()
    artifact_id = post_payload["artifact_id"]
    assert (tmp_path / f"{artifact_id}.json").exists()

    strategy_lab_get_response = client.get(f"/strategy-lab/etf-ranking/replacements/artifacts/{artifact_id}")
    legacy_get_response = client.get(f"/ranking/etf-replacements/artifacts/{artifact_id}")

    assert strategy_lab_get_response.status_code == 200
    assert legacy_get_response.status_code == 200
    assert strategy_lab_get_response.json() == post_payload
    assert legacy_get_response.json() == post_payload


def test_grouped_replacement_contract_uses_shared_ranking_bases(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(
        _build_request(seeded_symbols=["BASE", "ETF1", "ETF2"])
    )

    assert isinstance(result.request, RankingRequestContextBase)
    assert isinstance(result.effective_inputs, RankingEffectiveInputsBase)
    assert isinstance(result.run_metadata, RankingRunMetadataBase)
    assert result.request_context == result.request


def test_replacement_grouped_contract_requires_strict_fields_and_close_price_basis() -> None:
    with pytest.raises(ValueError):
        IntentBoundEtfReplacementRequestContext(
            universe=["BASE", "ETF1"],
            benchmark_symbol=None,
            lookback_months=6,
            prefer_live_data=False,
            base_symbol="BASE",
            candidate_symbol="ETF1",
            peer_group="Sector UCITS ETF",
            ranking_basis_date="2025-12-31",
            seed_ranking_id="etf_ranking_engine_v1",
            seed_methodology_id="etf_ranking_methodology_v1",
        )

    with pytest.raises(ValueError):
        IntentBoundEtfReplacementEffectiveInputs(
            benchmark_symbol="SPY",
            lookback_months=6,
            price_basis="adjusted_close",
            requested_universe=["BASE", "ETF1"],
            evaluated_universe=["ETF1"],
            base_symbol="BASE",
            candidate_symbol="ETF1",
            peer_group="Sector UCITS ETF",
            ranking_basis_date="2025-12-31",
        )

    with pytest.raises(ValueError):
        IntentBoundEtfReplacementRankingRunMetadata(
            ranking_id="intent_bound_etf_replacement_ranking_v1",
            methodology_id="intent_bound_etf_replacement_ranking_methodology_v1",
            methodology="Test methodology",
            as_of_date="2025-12-31",
            ranking_basis_date="2025-12-31",
            basis_date="2025-12-31",
            request_hash="abc",
            price_basis="adjusted_close",
            source_status="sample",
            confidence="low",
        )


def test_unavailable_response_maps_sample_source_status_to_low_confidence(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF2": _history(260, step=0.4)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(
        _build_request(seeded_symbols=["BASE", "ETF2"], candidate_symbol="ETF1")
    )

    assert result.status == "unavailable"
    assert result.submitted_request.replacement_intent.base_symbol == "BASE"
    assert result.normalized_request.seeded_symbols == ["BASE", "ETF2"]
    assert result.request.universe == ["BASE", "ETF2"]
    assert result.request.benchmark_symbol == "SPY"
    assert result.request.lookback_months == 6
    assert result.effective_inputs.requested_universe == ["BASE", "ETF2"]
    assert result.effective_inputs.evaluated_universe == []
    assert result.effective_inputs.benchmark_symbol == "SPY"
    assert result.effective_inputs.lookback_months == 6
    assert result.effective_inputs.price_basis == "close"
    assert result.run_metadata.source_status == "sample"
    assert result.run_metadata.confidence == "low"
    assert result.run_metadata.price_basis == "close"


def test_live_fetch_with_missing_adjusted_tail_never_claims_high_confidence(monkeypatch: MonkeyPatch) -> None:
    base_history = _history(260)
    candidate_history = _history(260, step=0.5)
    for row in candidate_history[-5:]:
        row.pop("adjClose", None)
    histories = {"BASE": base_history, "ETF1": candidate_history}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _LiveMetaWithTailGapMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(
        _build_request(seeded_symbols=["BASE", "ETF1"])
    )

    assert result.status == "unavailable"
    assert result.unavailable_reason == "no eligible seeded ETF candidates remain after exclusions"
    excluded = {row.symbol: row.exclusion_reason for row in result.excluded_candidates}
    assert excluded["ETF1"] == "candidate lacks required adjusted-price coverage through basis date"
    assert result.run_metadata.source_status == "live"
    assert result.run_metadata.confidence != "high"


def test_successful_run_with_adjusted_close_exclusion_downgrades_live_confidence(monkeypatch: MonkeyPatch) -> None:
    base_history = _history(260)
    eligible_history = _history(260, step=0.5)
    tail_gap_history = _history(260, step=0.25)
    for row in tail_gap_history[-5:]:
        row.pop("adjClose", None)
    histories = {"BASE": base_history, "ETF1": eligible_history, "ETF2": tail_gap_history}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _LiveMetaWithTailGapMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(
        _build_request(seeded_symbols=["BASE", "ETF1", "ETF2"])
    )

    assert result.status == "ok"
    assert [row.symbol for row in result.ranked_candidates] == ["ETF1"]
    excluded = {row.symbol: row.exclusion_reason for row in result.excluded_candidates}
    assert excluded["ETF2"] == "candidate lacks required adjusted-price coverage through basis date"
    assert result.run_metadata.source_status == "live"
    assert result.run_metadata.confidence == "medium"


def test_short_adjusted_history_keeps_252d_exclusion_reason(monkeypatch: MonkeyPatch) -> None:
    histories = {
        "BASE": _history(260),
        "ETF1": _history(260, step=0.5),
        "ETF2": _history(200, step=0.25),
    }
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(
        _build_request(seeded_symbols=["BASE", "ETF1", "ETF2"])
    )

    excluded = {row.symbol: row.exclusion_reason for row in result.excluded_candidates}
    assert excluded["ETF2"] == "candidate lacks required 252d adjusted-price history"


def test_seed_context_benchmark_and_lookback_mismatches_fail_closed(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    request = _build_request(seeded_symbols=["BASE", "ETF1"])
    request.seed_context.benchmark_symbol = "QQQ"

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(request)

    assert result.status == "unavailable"
    assert result.unavailable_reason == "replacement intent benchmark symbol does not match the seed context"

    request = _build_request(seeded_symbols=["BASE", "ETF1"])
    request.seed_context.lookback_months = 12

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(request)

    assert result.status == "unavailable"
    assert result.unavailable_reason == "replacement intent lookback months does not match the seed context"


def test_malformed_adjusted_history_fails_closed(monkeypatch: MonkeyPatch) -> None:
    malformed_history = _history(260, step=0.5)
    malformed_history[-1]["adjClose"] = 0.0
    histories = {"BASE": _history(260), "ETF1": malformed_history}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _LiveMetaWithTailGapMarketData(histories))

    result = replacement_ranking_module.build_intent_bound_etf_replacement_ranking(
        _build_request(seeded_symbols=["BASE", "ETF1"])
    )

    assert result.status == "unavailable"
    excluded = {row.symbol: row.exclusion_reason for row in result.excluded_candidates}
    assert excluded["ETF1"] == "candidate has malformed adjusted-price history"
    assert result.run_metadata.source_status == "live"
    assert result.run_metadata.confidence == "medium"
