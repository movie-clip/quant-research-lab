"""Tests for the Russell 1000 static-snapshot universe resolution path.

Russell 1000 has no FMP constituent endpoint; it is resolved from a versioned
JSON snapshot under data/universe/index_snapshots/. These tests cover:

- IndexId schema accepts russell1000
- Snapshot loader validates schema_version, index_id field, and constituent shape
- Resolver dispatches russell1000 to the snapshot loader and returns the bundled members
- Sector filters apply identically across sp500 and russell1000 paths
- Fail-closed behavior: missing snapshot returns empty list with explicit warning
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.generic_ranking import UniverseSpec
from app.services.universe_resolver import (
    IndexSnapshotError,
    UniverseResolver,
    _load_index_snapshot,
)


# ── Schema-level tests ──────────────────────────────────────────────────────


def test_universe_spec_accepts_russell1000_index_id() -> None:
    spec = UniverseSpec(
        universe_id="russell1000_quality",
        universe_kind="index_constituent",
        index_id="russell1000",
    )
    assert spec.index_id == "russell1000"


def test_universe_spec_rejects_unknown_index_id() -> None:
    with pytest.raises(ValueError):
        UniverseSpec(
            universe_id="russell5000",
            universe_kind="index_constituent",
            index_id="russell5000",  # type: ignore[arg-type]
        )


# ── Snapshot loader tests ───────────────────────────────────────────────────


def test_load_index_snapshot_loads_bundled_russell1000() -> None:
    constituents = _load_index_snapshot("russell1000")
    assert len(constituents) > 0
    # Sample bundle should contain well-known large caps
    symbols = {row["symbol"] for row in constituents}
    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "JPM" in symbols
    # Every constituent must have a non-empty symbol
    assert all(isinstance(row.get("symbol"), str) and row["symbol"].strip() for row in constituents)


def test_load_index_snapshot_fails_closed_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(IndexSnapshotError, match="missing"):
        _load_index_snapshot("nonexistent_index_xyz", snapshots_dir=tmp_path)


def test_load_index_snapshot_fails_closed_on_invalid_json(tmp_path: Path) -> None:
    bad = tmp_path / "russell1000.json"
    bad.write_text("not valid json {", encoding="utf-8")
    with pytest.raises(IndexSnapshotError, match="not valid JSON"):
        _load_index_snapshot("russell1000", snapshots_dir=tmp_path)


def test_load_index_snapshot_fails_closed_on_unsupported_schema_version(tmp_path: Path) -> None:
    bad = tmp_path / "russell1000.json"
    bad.write_text(
        json.dumps({
            "snapshot_schema_version": "made_up_v9",
            "index_id": "russell1000",
            "constituents": [{"symbol": "AAPL"}],
        }),
        encoding="utf-8",
    )
    with pytest.raises(IndexSnapshotError, match="unsupported snapshot_schema_version"):
        _load_index_snapshot("russell1000", snapshots_dir=tmp_path)


def test_load_index_snapshot_fails_closed_on_index_id_mismatch(tmp_path: Path) -> None:
    bad = tmp_path / "russell1000.json"
    bad.write_text(
        json.dumps({
            "snapshot_schema_version": "index_snapshot_v1",
            "index_id": "sp500",  # wrong: file is named russell1000.json
            "constituents": [{"symbol": "AAPL"}],
        }),
        encoding="utf-8",
    )
    with pytest.raises(IndexSnapshotError, match="index_id field"):
        _load_index_snapshot("russell1000", snapshots_dir=tmp_path)


def test_load_index_snapshot_fails_closed_on_malformed_constituent_row(tmp_path: Path) -> None:
    bad = tmp_path / "russell1000.json"
    bad.write_text(
        json.dumps({
            "snapshot_schema_version": "index_snapshot_v1",
            "index_id": "russell1000",
            "constituents": [{"symbol": "AAPL"}, {"name": "missing symbol field"}],
        }),
        encoding="utf-8",
    )
    with pytest.raises(IndexSnapshotError, match="malformed constituent row"):
        _load_index_snapshot("russell1000", snapshots_dir=tmp_path)


# ── Resolver dispatch tests ─────────────────────────────────────────────────


def test_resolver_dispatches_russell1000_to_static_snapshot() -> None:
    """russell1000 must resolve from the bundled snapshot WITHOUT touching FMP."""
    spec = UniverseSpec(
        universe_id="russell1000_full",
        universe_kind="index_constituent",
        index_id="russell1000",
    )
    # Pass fmp_client=None on purpose — russell1000 must NOT need FMP
    resolver = UniverseResolver(fmp_client=None)
    snapshot = resolver.resolve(spec, as_of_date="2026-05-11")
    # Should return real members from the bundled snapshot
    assert len(snapshot.evaluated_members) > 0
    assert "AAPL" in snapshot.evaluated_members
    assert "MSFT" in snapshot.evaluated_members
    # Members are sorted (resolver invariant)
    assert snapshot.evaluated_members == sorted(snapshot.evaluated_members)


def test_resolver_russell1000_applies_sector_filters() -> None:
    """Sector filters must apply to the russell1000 snapshot the same way they apply to sp500."""
    spec = UniverseSpec(
        universe_id="russell1000_tech_only",
        universe_kind="index_constituent",
        index_id="russell1000",
        sector_include=["Information Technology"],
    )
    resolver = UniverseResolver(fmp_client=None)
    snapshot = resolver.resolve(spec, as_of_date="2026-05-11")
    # Tech-only filter should keep tech names and drop financial / health-care names
    assert "AAPL" in snapshot.evaluated_members
    assert "MSFT" in snapshot.evaluated_members
    assert "JPM" not in snapshot.evaluated_members
    assert "JNJ" not in snapshot.evaluated_members


def test_resolver_russell1000_sector_exclude_filter() -> None:
    spec = UniverseSpec(
        universe_id="russell1000_no_energy",
        universe_kind="index_constituent",
        index_id="russell1000",
        sector_exclude=["Energy"],
    )
    resolver = UniverseResolver(fmp_client=None)
    snapshot = resolver.resolve(spec, as_of_date="2026-05-11")
    # XOM is the only Energy name in the bundled sample — must be excluded
    assert "XOM" not in snapshot.evaluated_members
    # Other sectors remain
    assert "AAPL" in snapshot.evaluated_members


def test_resolver_sp500_still_uses_fmp(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make sure the russell1000 dispatch did not break the existing sp500 path."""

    class _FakeFmp:
        def get_sp500_constituents(self) -> list[dict]:
            return [
                {"symbol": "AAPL", "sector": "Information Technology"},
                {"symbol": "JPM", "sector": "Financials"},
            ]

    spec = UniverseSpec(
        universe_id="sp500_full",
        universe_kind="index_constituent",
        index_id="sp500",
    )
    resolver = UniverseResolver(fmp_client=_FakeFmp())
    snapshot = resolver.resolve(spec, as_of_date="2026-05-11")
    assert sorted(snapshot.evaluated_members) == ["AAPL", "JPM"]


def test_resolver_russell1000_fail_closed_when_snapshot_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """When the bundled snapshot file is unavailable, russell1000 returns an empty list
    with a logged warning rather than raising — the resolver degrades gracefully and
    surface the trust state through evaluated_members=[]."""
    import app.services.universe_resolver as resolver_module

    # Point the snapshots dir to an empty tmp_path so the snapshot is "missing"
    monkeypatch.setattr(resolver_module, "_DEFAULT_INDEX_SNAPSHOTS_DIR", tmp_path)

    spec = UniverseSpec(
        universe_id="russell1000_full",
        universe_kind="index_constituent",
        index_id="russell1000",
    )
    resolver = UniverseResolver(fmp_client=None)
    snapshot = resolver.resolve(spec, as_of_date="2026-05-11")
    assert snapshot.evaluated_members == []
