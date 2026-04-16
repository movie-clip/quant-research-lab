from datetime import datetime

from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.backtest_engine import DraftPortfolioImportedMetaInput, DraftPortfolioSnapshotInput, DraftPortfolioPositionInput, ReplacementIntentReplayInput, SingleReplacementCandidateFormationRequest
from app.services.candidate_formation import build_single_replacement_candidate_formation


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
        cash_balances=[{"currency": "USD", "amount": 5000.0}] if include_cash else [],
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


def test_single_replacement_candidate_formation_builds_explicit_review_object() -> None:
    response = build_single_replacement_candidate_formation(
        SingleReplacementCandidateFormationRequest(
            snapshot=_draft_snapshot(("VUAA", 600.0), ("IB01", 400.0), include_cash=True),
            replacement_intent=_replacement_intent(),
        )
    )

    assert response.formation.kind == "single_replacement_candidate_formation"
    assert response.formation.status == "ok"
    assert response.proposal.source == "draft_replacement_intent"
    assert response.proposal.incumbent_symbol == "VUAA"
    assert response.proposal.candidate_symbol == "IUFS"
    assert response.derivation.baseline_basis == "draft_snapshot_positions_normalized"
    assert response.derivation.candidate_construction_rule == "single_symbol_weight_substitution"
    assert response.truth_provenance.baseline_truth_class == "draft_snapshot_basis"
    assert response.truth_provenance.candidate_truth_class == "hypothetical_candidate_input_only"
    assert [item.model_dump(mode="json") for item in response.baseline_weights] == [
        {"symbol": "VUAA", "target_weight": 0.6},
        {"symbol": "IB01", "target_weight": 0.4},
    ]
    assert [item.model_dump(mode="json") for item in response.candidate_weights] == [
        {"symbol": "IB01", "target_weight": 0.4},
        {"symbol": "IUFS", "target_weight": 0.6},
    ]
    assert response.formation_summary.incumbent_start_weight == 0.6
    assert response.formation_summary.candidate_start_weight == 0.6
    assert response.formation_summary.starting_turnover_pct == 0.6
    assert response.formation_summary.unchanged_positions_count == 1
    assert response.warnings == [
        "Cash balances are excluded from the candidate-formation basis in this MVP.",
        "Replacement intent carries 1 prior review warning(s).",
    ]


def test_single_replacement_candidate_formation_rejects_missing_snapshot() -> None:
    response = build_single_replacement_candidate_formation(
        SingleReplacementCandidateFormationRequest(snapshot=None, replacement_intent=_replacement_intent())
    )

    assert response.formation.status == "rejected"
    assert response.rejection_reason == "snapshot is required"


def test_single_replacement_candidate_formation_rejects_missing_intent() -> None:
    response = build_single_replacement_candidate_formation(
        SingleReplacementCandidateFormationRequest(snapshot=_draft_snapshot(("VUAA", 1000.0)), replacement_intent=None)
    )

    assert response.formation.status == "rejected"
    assert response.rejection_reason == "replacement_intent is required"


def test_single_replacement_candidate_formation_rejects_incumbent_not_found() -> None:
    response = build_single_replacement_candidate_formation(
        SingleReplacementCandidateFormationRequest(
            snapshot=_draft_snapshot(("IB01", 1000.0)),
            replacement_intent=_replacement_intent(),
        )
    )

    assert response.formation.status == "rejected"
    assert response.rejection_reason == "replacement intent incumbent not found in draft snapshot: VUAA"


def test_single_replacement_candidate_formation_rejects_candidate_already_held() -> None:
    response = build_single_replacement_candidate_formation(
        SingleReplacementCandidateFormationRequest(
            snapshot=_draft_snapshot(("VUAA", 600.0), ("IUFS", 400.0)),
            replacement_intent=_replacement_intent(),
        )
    )

    assert response.formation.status == "rejected"
    assert response.rejection_reason == "replacement intent candidate is already held in draft snapshot: IUFS"


def test_single_replacement_candidate_formation_rejects_same_symbol_candidate() -> None:
    response = build_single_replacement_candidate_formation(
        SingleReplacementCandidateFormationRequest(
            snapshot=_draft_snapshot(("VUAA", 1000.0)),
            replacement_intent=_replacement_intent(candidate_symbol="VUAA"),
        )
    )

    assert response.formation.status == "rejected"
    assert response.rejection_reason == "replacement intent candidate must differ from incumbent"


def test_candidate_formation_route_returns_explicit_review_contract() -> None:
    client = TestClient(app)
    response = client.post(
        "/backtests/candidate-formation/replacement-intent",
        json={
            "snapshot": _draft_snapshot(("VUAA", 600.0), ("IB01", 400.0)).model_dump(mode="json"),
            "replacement_intent": _replacement_intent().model_dump(mode="json"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["formation"] == {"kind": "single_replacement_candidate_formation", "status": "ok"}
    assert payload["proposal"]["source"] == "draft_replacement_intent"
    assert payload["truth_provenance"]["formation_truth_class"] == "candidate_formation_derived"
    assert payload["rejection_reason"] is None
