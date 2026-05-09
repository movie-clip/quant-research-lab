"""Phase 2 tests for the generalized ranking platform.

Covers:
- index_constituent universe kind (S&P 500)
- Quality + value factor IDs
- Fundamental data loading
- Cross-kind catalog inclusion of generic_ranking
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.generic_ranking import (
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
    build_stable_generic_ranking_artifact,
)


# ── UniverseSpec: index_constituent ──────────────────────────────────────────


def test_universe_spec_index_constituent_requires_index_id() -> None:
    with pytest.raises(ValueError, match="index_id"):
        UniverseSpec(
            universe_id="sp500_universe",
            universe_kind="index_constituent",
        )


def test_universe_spec_index_constituent_accepts_sp500() -> None:
    spec = UniverseSpec(
        universe_id="sp500",
        universe_kind="index_constituent",
        index_id="sp500",
    )
    assert spec.index_id == "sp500"
    assert spec.universe_kind == "index_constituent"


# ── UniverseResolver: index_constituent ──────────────────────────────────────


def test_index_constituent_resolves_via_fmp_client() -> None:
    """UniverseResolver should call get_sp500_constituents and apply optional sector filters."""
    from app.services.universe_resolver import UniverseResolver

    class _FakeFmp:
        def get_sp500_constituents(self) -> list[dict]:
            return [
                {"symbol": "AAPL", "sector": "Information Technology"},
                {"symbol": "JPM", "sector": "Financials"},
                {"symbol": "XOM", "sector": "Energy"},
            ]

    spec = UniverseSpec(
        universe_id="sp500_filtered",
        universe_kind="index_constituent",
        index_id="sp500",
        sector_exclude=["Energy"],
    )
    resolver = UniverseResolver(fmp_client=_FakeFmp())
    snapshot = resolver.resolve(spec, as_of_date="2026-05-10")
    assert "AAPL" in snapshot.evaluated_members
    assert "JPM" in snapshot.evaluated_members
    assert "XOM" not in snapshot.evaluated_members


def test_index_constituent_returns_empty_when_fmp_client_missing() -> None:
    from app.services.universe_resolver import UniverseResolver

    spec = UniverseSpec(
        universe_id="sp500_no_client",
        universe_kind="index_constituent",
        index_id="sp500",
    )
    resolver = UniverseResolver(fmp_client=None)
    snapshot = resolver.resolve(spec, as_of_date="2026-05-10")
    assert snapshot.evaluated_members == []


# ── Quality + value factor support ───────────────────────────────────────────


def test_quality_and_value_factor_ids_supported() -> None:
    """Quality and value factor IDs must be in SUPPORTED_FACTOR_IDS."""
    from app.services.generic_ranking_service import (
        QUALITY_FACTOR_IDS,
        SUPPORTED_FACTOR_IDS,
        VALUE_FACTOR_IDS,
    )

    expected_quality = {
        "quality_profitability",
        "quality_cash_generation",
        "quality_accrual",
        "quality_leverage",
    }
    expected_value = {
        "value_earnings_yield",
        "value_book_to_market",
        "value_fcf_yield",
        "value_ev_ebitda_inverse",
    }
    assert expected_quality == QUALITY_FACTOR_IDS
    assert expected_value == VALUE_FACTOR_IDS
    assert expected_quality.issubset(SUPPORTED_FACTOR_IDS)
    assert expected_value.issubset(SUPPORTED_FACTOR_IDS)


def test_compute_fundamental_quality_profitability_primary_formula() -> None:
    """quality_profitability primary: (revenue - cogs) / total_assets."""
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    snap = _FundamentalSnapshot()
    snap.total_revenue = 100.0
    snap.cost_of_revenue = 60.0
    snap.total_assets = 200.0
    result = _compute_fundamental_raw_value("quality_profitability", snap)
    assert result == pytest.approx(0.20)


def test_compute_fundamental_quality_profitability_fallback_to_ebit() -> None:
    """quality_profitability fallback: EBIT / total_assets when revenue/cogs missing."""
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    snap = _FundamentalSnapshot()
    snap.ebit = 30.0
    snap.total_assets = 200.0
    result = _compute_fundamental_raw_value("quality_profitability", snap)
    assert result == pytest.approx(0.15)


def test_compute_fundamental_quality_accrual_sloan_ratio() -> None:
    """quality_accrual: (net_income - OCF) / total_assets — Sloan ratio."""
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    snap = _FundamentalSnapshot()
    snap.net_income = 20.0
    snap.operating_cash_flow = 25.0
    snap.total_assets = 100.0
    result = _compute_fundamental_raw_value("quality_accrual", snap)
    assert result == pytest.approx(-0.05)


def test_compute_fundamental_quality_leverage() -> None:
    """quality_leverage: (total_debt - cash) / total_assets — net leverage."""
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    snap = _FundamentalSnapshot()
    snap.total_debt = 50.0
    snap.cash_and_equivalents = 10.0
    snap.total_assets = 200.0
    result = _compute_fundamental_raw_value("quality_leverage", snap)
    assert result == pytest.approx(0.20)


def test_compute_fundamental_value_earnings_yield_greenblatt() -> None:
    """value_earnings_yield: EBIT / Enterprise Value (Greenblatt Magic Formula)."""
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    snap = _FundamentalSnapshot()
    snap.ebit = 100.0
    snap.enterprise_value = 1000.0
    result = _compute_fundamental_raw_value("value_earnings_yield", snap)
    assert result == pytest.approx(0.10)


def test_compute_fundamental_value_book_to_market() -> None:
    """value_book_to_market: 1 / P/B."""
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    snap = _FundamentalSnapshot()
    snap.price_to_book = 4.0
    result = _compute_fundamental_raw_value("value_book_to_market", snap)
    assert result == pytest.approx(0.25)


def test_compute_fundamental_value_fcf_yield_prefers_direct() -> None:
    """value_fcf_yield should prefer FMP fcf_yield field over inverted P/FCF."""
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    snap = _FundamentalSnapshot()
    snap.fcf_yield = 0.05
    snap.price_to_fcf = 30.0  # would give 0.0333... if used as fallback
    result = _compute_fundamental_raw_value("value_fcf_yield", snap)
    assert result == pytest.approx(0.05)


def test_compute_fundamental_value_ev_ebitda_inverse() -> None:
    """value_ev_ebitda_inverse: 1 / (EV/EBITDA)."""
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    snap = _FundamentalSnapshot()
    snap.ev_to_ebitda = 10.0
    result = _compute_fundamental_raw_value("value_ev_ebitda_inverse", snap)
    assert result == pytest.approx(0.10)


def test_compute_fundamental_returns_none_when_snapshot_missing() -> None:
    from app.services.generic_ranking_service import _compute_fundamental_raw_value

    assert _compute_fundamental_raw_value("quality_profitability", None) is None
    assert _compute_fundamental_raw_value("value_earnings_yield", None) is None


def test_compute_fundamental_returns_none_when_required_fields_missing() -> None:
    from app.services.generic_ranking_service import (
        _FundamentalSnapshot,
        _compute_fundamental_raw_value,
    )

    # Empty snapshot — no field is set
    snap = _FundamentalSnapshot()
    assert _compute_fundamental_raw_value("quality_profitability", snap) is None
    assert _compute_fundamental_raw_value("quality_accrual", snap) is None
    assert _compute_fundamental_raw_value("value_earnings_yield", snap) is None


# ── Service-level: warning when fundamentals requested without FMP client ───


def test_run_generic_ranking_warns_when_fundamentals_requested_without_fmp_client() -> None:
    """When quality/value factors are requested but no FMP client available, the service
    should emit a warning rather than raising."""
    client = TestClient(app)
    response = client.post(
        "/strategy-lab/ranking/run",
        json={
            "universe_spec": {
                "universe_id": "test_quality_no_fmp",
                "universe_kind": "custom_list",
                "explicit_symbols": ["AAPL", "MSFT"],
            },
            "score_config": {
                "score_config_id": "test_quality_v1",
                "factors": [
                    # Mix one price factor so symbols stay eligible (avoid all-fundamental excluded path)
                    {"factor_id": "momentum_6m",          "family": "momentum", "direction": "higher_is_better", "weight": 0.5, "raw_unit": "pct"},
                    {"factor_id": "quality_profitability", "family": "quality", "direction": "higher_is_better", "weight": 0.5, "raw_unit": "ratio"},
                ],
            },
        },
    )
    assert response.status_code == 200
    body = response.json()
    factor_ids = body["run_metadata"]["score_config_ref"]["factor_ids"]
    assert "quality_profitability" in factor_ids
    assert "momentum_6m" in factor_ids


# ── Catalog: generic_ranking included in cross-kind catalog ─────────────────


def _make_generic_ranking_response() -> GenericRankingResponse:
    return GenericRankingResponse(
        ranking_id="catalog_test_ranking",
        methodology_id="generic_ranking_methodology_v1",
        title="Catalog Test",
        as_of_date="2026-05-10",
        benchmark_symbol="SPY",
        lookback_months=6,
        universe_spec_snapshot=UniverseSpecSnapshot(
            universe_id="test_universe",
            universe_kind="custom_list",
            spec_digest="abc123",
            evaluated_members=["AAPL", "MSFT"],
            evaluated_at="2026-05-10",
        ),
        run_metadata=GenericRankingRunMetadata(
            ranking_id="catalog_test_ranking",
            methodology_id="generic_ranking_methodology_v1",
            as_of_date="2026-05-10",
            ranking_basis_date="2026-05-10",
            price_basis="close",
            confidence="full",
            score_config_ref=ScoreConfigRef(
                score_config_id="catalog_test_v1",
                score_config_version="v1",
                score_config_digest="def456",
                factor_ids=["momentum_6m"],
                normalization="cross_sectional_zscore",
                winsorize_pct=0.05,
            ),
            composite_score_trace=None,
        ),
        ranked_universe=[
            GenericRankingRow(
                rank=1,
                symbol="AAPL",
                composite_score=1.0,
                component_scores={},
                eligibility=EligibilityRecord(eligibility_status="eligible"),
            ),
        ],
        excluded_instruments=[],
        warnings=[],
    )


def test_catalog_includes_generic_ranking_artifacts(tmp_path) -> None:
    """The cross-kind ranking catalog must surface generic_ranking artifacts alongside ETF ones."""
    from app.services.ranking_artifact_catalog_service import RankingArtifactCatalogService

    store_dir = tmp_path / "generic-ranking-artifacts"
    store_dir.mkdir(parents=True, exist_ok=True)
    store = GenericRankingArtifactStore(base_dir=str(store_dir))

    response = _make_generic_ranking_response()
    artifact = build_stable_generic_ranking_artifact(response)
    store.persist(artifact)

    service = RankingArtifactCatalogService(generic_store=store)
    catalog = service.list_catalog()
    generic_items = [item for item in catalog.items if item.artifact_kind == "generic_ranking"]
    assert len(generic_items) >= 1
    assert generic_items[0].generic_summary is not None
    assert generic_items[0].generic_summary.universe_id == "test_universe"
    assert generic_items[0].generic_summary.universe_kind == "custom_list"
    assert generic_items[0].generic_summary.score_config_id == "catalog_test_v1"
    assert generic_items[0].generic_summary.evaluated_universe_size == 1


def test_catalog_filters_generic_ranking_by_artifact_kind(tmp_path) -> None:
    """Filtering catalog by artifact_kind='generic_ranking' should return only generic rows."""
    from app.schemas.research import RankingArtifactDiscoveryFilters
    from app.services.ranking_artifact_catalog_service import RankingArtifactCatalogService

    store_dir = tmp_path / "generic-ranking-artifacts"
    store_dir.mkdir(parents=True, exist_ok=True)
    store = GenericRankingArtifactStore(base_dir=str(store_dir))

    response = _make_generic_ranking_response()
    artifact = build_stable_generic_ranking_artifact(response)
    store.persist(artifact)

    service = RankingArtifactCatalogService(generic_store=store)
    filtered = service.list_catalog(filters=RankingArtifactDiscoveryFilters(artifact_kind="generic_ranking"))
    assert all(item.artifact_kind == "generic_ranking" for item in filtered.items)
    assert len(filtered.items) >= 1


def test_recent_includes_generic_ranking_artifacts(tmp_path) -> None:
    """The cross-kind recent endpoint should include generic_ranking artifacts."""
    from app.services.ranking_artifact_catalog_service import RankingArtifactCatalogService

    store_dir = tmp_path / "generic-ranking-artifacts"
    store_dir.mkdir(parents=True, exist_ok=True)
    store = GenericRankingArtifactStore(base_dir=str(store_dir))

    response = _make_generic_ranking_response()
    artifact = build_stable_generic_ranking_artifact(response)
    store.persist(artifact)

    service = RankingArtifactCatalogService(generic_store=store)
    recent = service.list_recent(limit=20)
    generic_items = [item for item in recent.items if item.artifact_kind == "generic_ranking"]
    assert len(generic_items) >= 1
