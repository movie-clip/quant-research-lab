from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.backtest_engine import (
    CandidateConstructionRuleInput,
    DraftPortfolioCashBalanceInput,
    DraftPortfolioImportedMetaInput,
    DraftPortfolioSnapshotInput,
    DraftPortfolioPositionInput,
    ReplacementIntentReplayInput,
    SingleReplacementCandidateConstructionRequest,
)
from app.services.candidate_construction import RULE_ID, RULE_ID_FIXED_SPLIT, build_single_replacement_candidate_construction, derive_fixed_split_50_50_substitution_construction, derive_same_weight_substitution_construction


def _draft_snapshot(*positions: tuple[str, float], include_cash: bool = False) -> DraftPortfolioSnapshotInput:
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
        cash_balances=[DraftPortfolioCashBalanceInput(currency="USD", amount=5000.0)] if include_cash else [],
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


def test_same_weight_substitution_construction_returns_review_only_output() -> None:
    response = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 600.0), ("IB01", 400.0), include_cash=True),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID),
        )
    )

    assert response.construction.kind == "single_replacement_construction"
    assert response.construction.status == "ok"
    assert response.construction.rule_id == RULE_ID
    assert [item.model_dump(mode="json") for item in response.inputs.baseline_weights] == [
        {"symbol": "VUAA", "target_weight": 0.6},
        {"symbol": "IB01", "target_weight": 0.4},
    ]
    assert [item.model_dump(mode="json") for item in response.outputs.candidate_weights] == [
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.6},
    ]
    assert response.inputs.incumbent_start_weight == 0.6
    assert response.inputs.candidate_added_weight == 0.6
    assert response.inputs.incumbent_remaining_weight == 0.0
    assert response.outputs.starting_turnover_pct == 0.6
    assert response.outputs.unchanged_positions_count == 1
    assert response.outputs.candidate_added_weight == 0.6
    assert response.outputs.incumbent_remaining_weight == 0.0
    assert response.derivation.construction_basis == "explicit_single_replacement_rule"
    assert response.truth_provenance.construction_truth_class == "candidate_construction_derived"
    assert response.warnings == [
        "Cash balances are excluded from the construction basis in this MVP.",
        "Replacement intent carries 1 prior review warning(s).",
    ]


def test_same_weight_substitution_derivation_matches_candidate_formation_semantics() -> None:
    result = derive_same_weight_substitution_construction(_draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)), _replacement_intent())

    assert [item.model_dump(mode="json") for item in result.baseline_weights] == [
        {"symbol": "VUAA", "target_weight": 0.6},
        {"symbol": "IB01", "target_weight": 0.4},
    ]
    assert [item.model_dump(mode="json") for item in result.candidate_weights] == [
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.6},
    ]


def test_fixed_split_50_50_substitution_returns_sum_preserving_candidate_output() -> None:
    response = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID_FIXED_SPLIT),
        )
    )

    assert response.construction.status == "ok"
    assert response.construction.rule_id == RULE_ID_FIXED_SPLIT
    assert [item.model_dump(mode="json") for item in response.outputs.candidate_weights] == [
        {"symbol": "VUAA", "target_weight": 0.3},
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.3},
    ]
    assert response.outputs.starting_turnover_pct == 0.3
    assert response.outputs.candidate_added_weight == 0.3
    assert response.outputs.incumbent_remaining_weight == 0.3
    assert abs(sum(item.target_weight for item in response.outputs.candidate_weights) - 1.0) < 0.000001


def test_fixed_split_50_50_derivation_matches_locked_rule() -> None:
    result = derive_fixed_split_50_50_substitution_construction(_draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)), _replacement_intent())

    assert [item.model_dump(mode="json") for item in result.candidate_weights] == [
        {"symbol": "VUAA", "target_weight": 0.3},
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.3},
    ]
    assert result.starting_turnover_pct == 0.3


def test_same_weight_substitution_rejects_missing_rule() -> None:
    response = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 1000.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=None,
        )
    )

    assert response.construction.status == "rejected"
    assert response.rejection_reason == "construction_rule is required"


def test_same_weight_substitution_rejects_unsupported_rule() -> None:
    response = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest.model_validate(
            {
                "snapshot": _draft_snapshot(("VUAA", 1000.0)).model_dump(mode="json"),
                "replacement_intent": _replacement_intent().model_dump(mode="json"),
                "construction_rule": {"rule_id": "unsupported_rule_v0"},
            }
        )
    )

    assert response.construction.status == "rejected"
    assert response.rejection_reason == "unsupported construction rule: unsupported_rule_v0"


def test_same_weight_substitution_rejects_candidate_already_held() -> None:
    response = build_single_replacement_candidate_construction(
        SingleReplacementCandidateConstructionRequest(
            snapshot=_draft_snapshot(("VUAA", 600.0), ("IUFS", 400.0)),
            replacement_intent=_replacement_intent(),
            construction_rule=CandidateConstructionRuleInput(rule_id=RULE_ID),
        )
    )

    assert response.construction.status == "rejected"
    assert response.rejection_reason == "replacement intent candidate is already held in draft snapshot: IUFS"


def test_candidate_construction_route_returns_explicit_rule_contract() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/candidate-construction/replacement-intent",
        json={
            "snapshot": _draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)).model_dump(mode="json"),
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "construction_rule": {"rule_id": RULE_ID},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["construction"] == {"kind": "single_replacement_construction", "status": "ok", "rule_id": RULE_ID}
    assert payload["proposal"]["source"] == "draft_replacement_intent"
    assert payload["truth_provenance"]["candidate_truth_class"] == "hypothetical_candidate_input_only"
    assert payload["rejection_reason"] is None


def test_candidate_construction_route_accepts_fixed_split_rule() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/candidate-construction/replacement-intent",
        json={
            "snapshot": _draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)).model_dump(mode="json"),
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
            "construction_rule": {"rule_id": RULE_ID_FIXED_SPLIT},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["construction"]["rule_id"] == RULE_ID_FIXED_SPLIT
    assert payload["outputs"]["candidate_added_weight"] == 0.3
    assert payload["outputs"]["incumbent_remaining_weight"] == 0.3
