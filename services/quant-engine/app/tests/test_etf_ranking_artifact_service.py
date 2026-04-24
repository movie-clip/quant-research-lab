import json
from pathlib import Path

import pytest

from app.schemas.ranking import RankingEffectiveInputsBase, RankingRequestContextBase, RankingRunMetadataBase
from app.schemas.research import (
    EtfRankingComponentWeights,
    EtfRankingEffectiveInputs,
    EtfRankingRequestContext,
    EtfRankingResponse,
    EtfRankingRunMetadata,
    EtfRankingSourceStatus,
    EtfRankingWarnings,
)
from app.services.etf_ranking_artifact_service import (
    EtfRankingArtifactRecentIndexInvalidJsonError,
    EtfRankingArtifactRecentIndexNonObjectPayloadError,
    EtfRankingArtifactRecentIndexSchemaValidationError,
    EtfRankingArtifactStore,
    build_stable_etf_ranking_artifact,
    list_recent_etf_ranking_artifacts_strict,
)


def _build_response() -> EtfRankingResponse:
    request = EtfRankingRequestContext(
        universe=["XLK", "XLF"],
        benchmark_symbol="SPY",
        lookback_months=6,
        prefer_live_data=False,
        peer_group="Sector UCITS ETF",
        weights=EtfRankingComponentWeights(),
    )
    effective_inputs = EtfRankingEffectiveInputs(
        benchmark_symbol="SPY",
        lookback_months=6,
        price_basis="close",
        requested_universe=["XLK", "XLF"],
        evaluated_universe=["XLK", "XLF"],
        effective_peer_group="Sector UCITS ETF",
        effective_component_weights=EtfRankingComponentWeights().normalized(),
        excluded_symbols=[],
    )
    run_metadata = EtfRankingRunMetadata(
        ranking_id="etf_ranking_engine_v1",
        methodology_id="etf_ranking_methodology_v1",
        methodology="Test methodology",
        as_of_date="2026-01-31",
        ranking_basis_date="2026-01-31",
        price_basis="close",
        source_status=EtfRankingSourceStatus(
            price_history="sample",
            benchmark_history="sample",
            holdings_support="sample",
        ),
        confidence="high",
    )
    return EtfRankingResponse(
        ranking_id="etf_ranking_engine_v1",
        title="ETF Ranking Engine",
        as_of_date="2026-01-31",
        benchmark_symbol="SPY",
        universe=["XLK", "XLF"],
        lookback_months=6,
        price_basis="close",
        methodology="Test methodology",
        effective_peer_group="Sector UCITS ETF",
        effective_component_weights=EtfRankingComponentWeights().normalized(),
        source_status=run_metadata.source_status,
        warnings=EtfRankingWarnings(confidence="high", warnings=[]),
        request=request,
        effective_inputs=effective_inputs,
        run_metadata=run_metadata,
        ranked_universe=[],
        excluded_symbols=[],
    )


def test_etf_ranking_grouped_contract_uses_shared_ranking_bases() -> None:
    artifact = build_stable_etf_ranking_artifact(_build_response())

    assert isinstance(artifact.request, RankingRequestContextBase)
    assert isinstance(artifact.effective_inputs, RankingEffectiveInputsBase)
    assert isinstance(artifact.run_metadata, RankingRunMetadataBase)


def test_etf_ranking_grouped_contract_serializes_with_existing_payload_shape() -> None:
    artifact = build_stable_etf_ranking_artifact(_build_response())

    payload = artifact.model_dump(mode="json")

    assert payload["request"] == {
        "universe": ["XLK", "XLF"],
        "benchmark_symbol": "SPY",
        "lookback_months": 6,
        "prefer_live_data": False,
        "peer_group": "Sector UCITS ETF",
        "weights": {
            "momentum": 0.3,
            "benchmark_relative_strength": 0.2,
            "realized_volatility": 0.15,
            "downside_volatility": 0.1,
            "max_drawdown": 0.1,
            "liquidity": 0.1,
            "implementation_fit": 0.05,
        },
    }
    assert payload["effective_inputs"] == {
        "benchmark_symbol": "SPY",
        "lookback_months": 6,
        "price_basis": "close",
        "requested_universe": ["XLK", "XLF"],
        "evaluated_universe": ["XLK", "XLF"],
        "effective_peer_group": "Sector UCITS ETF",
        "effective_component_weights": {
            "momentum": 0.3,
            "benchmark_relative_strength": 0.2,
            "realized_volatility": 0.15,
            "downside_volatility": 0.1,
            "max_drawdown": 0.1,
            "liquidity": 0.1,
            "implementation_fit": 0.05,
        },
        "excluded_symbols": [],
    }
    assert payload["run_metadata"] == {
        "ranking_id": "etf_ranking_engine_v1",
        "methodology_id": "etf_ranking_methodology_v1",
        "methodology": "Test methodology",
        "as_of_date": "2026-01-31",
        "ranking_basis_date": "2026-01-31",
        "price_basis": "close",
        "source_status": {
            "price_history": "sample",
            "benchmark_history": "sample",
            "holdings_support": "sample",
        },
        "confidence": "high",
    }


def test_etf_ranking_request_context_requires_benchmark_symbol_and_lookback() -> None:
    with pytest.raises(ValueError):
        EtfRankingRequestContext(
            universe=["XLK", "XLF"],
            benchmark_symbol=None,
            lookback_months=6,
            prefer_live_data=False,
            peer_group="Sector UCITS ETF",
            weights=EtfRankingComponentWeights(),
        )

    with pytest.raises(ValueError):
        EtfRankingRequestContext(
            universe=["XLK", "XLF"],
            benchmark_symbol="SPY",
            lookback_months=0,
            prefer_live_data=False,
            peer_group="Sector UCITS ETF",
            weights=EtfRankingComponentWeights(),
        )

    with pytest.raises(ValueError):
        EtfRankingRequestContext(
            universe=["XLK", "XLF"],
            benchmark_symbol="SPY",
            lookback_months=None,
            prefer_live_data=False,
            peer_group="Sector UCITS ETF",
            weights=EtfRankingComponentWeights(),
        )


def test_etf_ranking_effective_inputs_require_close_price_basis_and_strict_fields() -> None:
    with pytest.raises(ValueError):
        EtfRankingEffectiveInputs(
            benchmark_symbol=None,
            lookback_months=6,
            price_basis="close",
            requested_universe=["XLK", "XLF"],
            evaluated_universe=["XLK", "XLF"],
            effective_peer_group="Sector UCITS ETF",
            effective_component_weights=EtfRankingComponentWeights().normalized(),
            excluded_symbols=[],
        )

    with pytest.raises(ValueError):
        EtfRankingEffectiveInputs(
            benchmark_symbol="SPY",
            lookback_months=None,
            price_basis="close",
            requested_universe=["XLK", "XLF"],
            evaluated_universe=["XLK", "XLF"],
            effective_peer_group="Sector UCITS ETF",
            effective_component_weights=EtfRankingComponentWeights().normalized(),
            excluded_symbols=[],
        )

    with pytest.raises(ValueError):
        EtfRankingEffectiveInputs(
            benchmark_symbol="SPY",
            lookback_months=6,
            price_basis="adjusted_close",
            requested_universe=["XLK", "XLF"],
            evaluated_universe=["XLK", "XLF"],
            effective_peer_group="Sector UCITS ETF",
            effective_component_weights=EtfRankingComponentWeights().normalized(),
            excluded_symbols=[],
        )

    with pytest.raises(ValueError):
        EtfRankingEffectiveInputs(
            benchmark_symbol="SPY",
            lookback_months=0,
            price_basis="close",
            requested_universe=["XLK", "XLF"],
            evaluated_universe=["XLK", "XLF"],
            effective_peer_group="Sector UCITS ETF",
            effective_component_weights=EtfRankingComponentWeights().normalized(),
            excluded_symbols=[],
        )


def test_etf_ranking_run_metadata_requires_close_price_basis() -> None:
    with pytest.raises(ValueError):
        EtfRankingRunMetadata(
            ranking_id="etf_ranking_engine_v1",
            methodology_id="etf_ranking_methodology_v1",
            methodology="Test methodology",
            as_of_date="2026-01-31",
            ranking_basis_date="2026-01-31",
            price_basis="adjusted_close",
            source_status=EtfRankingSourceStatus(
                price_history="sample",
                benchmark_history="sample",
                holdings_support="sample",
            ),
            confidence="high",
        )


def test_strict_recent_etf_listing_rejects_invalid_json_index_rows(tmp_path: Path) -> None:
    store = EtfRankingArtifactStore(base_dir=str(tmp_path))
    store.recent_index_path().write_text("not-json\n", encoding="utf-8")

    with pytest.raises(EtfRankingArtifactRecentIndexInvalidJsonError):
        list_recent_etf_ranking_artifacts_strict(limit=10, store=store)


def test_strict_recent_etf_listing_rejects_non_object_index_rows(tmp_path: Path) -> None:
    store = EtfRankingArtifactStore(base_dir=str(tmp_path))
    store.recent_index_path().write_text("[]\n", encoding="utf-8")

    with pytest.raises(EtfRankingArtifactRecentIndexNonObjectPayloadError):
        list_recent_etf_ranking_artifacts_strict(limit=10, store=store)


def test_strict_recent_etf_listing_rejects_schema_invalid_index_rows(tmp_path: Path) -> None:
    store = EtfRankingArtifactStore(base_dir=str(tmp_path))
    store.recent_index_path().write_text(
        json.dumps({"artifact_id": 123}, sort_keys=True, separators=(",", ":"), ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(EtfRankingArtifactRecentIndexSchemaValidationError):
        list_recent_etf_ranking_artifacts_strict(limit=10, store=store)


def test_etf_ranking_catalog_row_contract_rejects_kind_summary_mismatch() -> None:
    artifact = build_stable_etf_ranking_artifact(_build_response())

    with pytest.raises(ValueError, match="etf_ranking rows must populate only etf_summary"):
        from app.schemas.research import RankingArtifactCatalogReplacementSummary, RankingArtifactCatalogRow, RankingArtifactCatalogRowMetadata

        RankingArtifactCatalogRow(
            artifact_kind="etf_ranking",
            artifact_id=artifact.artifact_id,
            schema_version=artifact.schema_version,
            ranking_id=artifact.ranking_id,
            methodology_id=artifact.run_metadata.methodology_id,
            as_of_date=artifact.as_of_date,
            ranking_basis_date=artifact.run_metadata.ranking_basis_date,
            recent_order_primary_date=artifact.run_metadata.ranking_basis_date,
            recent_order_secondary_date=artifact.as_of_date,
            recent_order_artifact_id=artifact.artifact_id,
            metadata=RankingArtifactCatalogRowMetadata(
                metadata_provenance="persisted_artifact_body",
                matched_metadata_provenance="persisted_artifact_body",
                recency_same_day_provenance="etf_recent_index",
            ),
            etf_summary=None,
            replacement_summary=RankingArtifactCatalogReplacementSummary(
                basis_date="2026-01-31",
                status="ok",
                base_symbol="BASE",
                candidate_symbol="ETF1",
                peer_group="Sector UCITS ETF",
                eligible_count=1,
                excluded_count=0,
                confidence="high",
            ),
        )


def test_etf_ranking_catalog_row_metadata_rejects_recent_index_provenance_mismatch() -> None:
    from app.schemas.research import RankingArtifactCatalogRowMetadata

    with pytest.raises(
        ValueError,
        match="matched_metadata_provenance must remain persisted_etf_recent_index",
    ):
        RankingArtifactCatalogRowMetadata(
            metadata_provenance="persisted_etf_recent_index",
            matched_metadata_provenance="persisted_artifact_body",
            recency_same_day_provenance="etf_recent_index",
        )
