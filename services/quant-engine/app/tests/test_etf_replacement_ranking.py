from __future__ import annotations

from datetime import date, timedelta

from fastapi.testclient import TestClient
from pytest import MonkeyPatch

from app.api.main import app
from app.schemas.research import Instrument, IntentBoundEtfReplacementRankingRequest, IntentBoundEtfReplacementRawFactors, IntentBoundReplacementIntent, IntentBoundSeedContext
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
        ),
        seed_context=IntentBoundSeedContext(
            ranking_id="etf_ranking_engine_v1",
            methodology_id="etf_ranking_methodology_v1",
            ranking_basis_date="2025-12-31",
            peer_group="Sector UCITS ETF",
            seeded_symbols=seeded_symbols,
        ),
    )


def _instrument(symbol: str, asset_class: str = "etf", category: str = "Sector UCITS ETF") -> Instrument:
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
    start = date(2025, 1, 1)
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
    instruments = {"BASE": _instrument("BASE"), "ETF1": _instrument("ETF1"), "AAPL": _instrument("AAPL", asset_class="equity", category="Equity")}
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


def test_route_returns_ranked_and_excluded_candidates(monkeypatch: MonkeyPatch) -> None:
    histories = {"BASE": _history(260), "ETF1": _history(260, step=0.5), "ETF2": _history(260, step=0.25)}
    instruments = {symbol: _instrument(symbol) for symbol in histories}
    monkeypatch.setattr(replacement_ranking_module, "InstrumentRegistry", lambda: _FakeRegistry(instruments))
    monkeypatch.setattr(replacement_ranking_module, "MarketDataService", lambda: _FakeMarketData(histories))

    client = TestClient(app)
    response = client.post("/ranking/etf-replacements", json=_build_request(seeded_symbols=["BASE", "ETF1", "ETF2"]).model_dump(mode="json"))

    assert response.status_code == 200
    payload = response.json()
    assert payload["ranking_id"] == "intent_bound_etf_replacement_ranking_v1"
    assert payload["methodology_id"] == "intent_bound_etf_replacement_ranking_methodology_v1"
    assert payload["request_hash"]
    assert payload["eligible_count"] == 2
    assert payload["excluded_count"] == 1
