from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _isolate_artifact_stores(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isolate every persisted-artifact store to per-test tmp directories by default.

    The cross-kind ranking catalog scans the ETF, replacement, generic ranking, and
    optimizer-handoff artifact directories alongside one another. Without per-test
    isolation, artifacts created by tests that hit the FastAPI route layer (which
    instantiates the default stores against the real settings paths) leak into
    `data/artifacts/<kind>/` and cause cross-test pollution. They also cause cross-
    kind catalog tests to see artifacts from other kinds.

    This fixture monkeypatches `get_settings` in each artifact-store module to return
    a `SimpleNamespace` whose dir fields point at isolated `tmp_path_factory`-created
    directories. Explicit per-test `mocker.patch.object(...)` still overrides the
    fixture (monkeypatch and mocker are independent), so tests that need a specific
    path keep working unchanged.

    Uses `tmp_path_factory` (NOT the test's own `tmp_path`) so the test's tmp_path
    stays empty — several tests assert that fact (e.g., persistence-failure tests).
    """
    etf_dir = tmp_path_factory.mktemp("etf-ranking-artifacts")
    replacement_dir = tmp_path_factory.mktemp("etf-replacement-ranking-artifacts")
    generic_dir = tmp_path_factory.mktemp("generic-ranking-artifacts")
    optimizer_dir = tmp_path_factory.mktemp("optimizer-handoffs")

    def _fake_etf_settings() -> Any:
        return SimpleNamespace(etf_ranking_artifact_dir=str(etf_dir))

    def _fake_replacement_settings() -> Any:
        return SimpleNamespace(replacement_ranking_artifact_dir=str(replacement_dir))

    def _fake_generic_settings() -> Any:
        return SimpleNamespace(generic_ranking_artifacts_dir=str(generic_dir))

    def _fake_optimizer_settings() -> Any:
        return SimpleNamespace(optimizer_handoff_dir=str(optimizer_dir))

    monkeypatch.setattr(
        "app.services.etf_ranking_artifact_service.get_settings",
        _fake_etf_settings,
    )
    monkeypatch.setattr(
        "app.services.replacement_ranking_artifact_service.get_settings",
        _fake_replacement_settings,
    )
    monkeypatch.setattr(
        "app.services.generic_ranking_artifact_service.get_settings",
        _fake_generic_settings,
    )
    monkeypatch.setattr(
        "app.services.optimizer_artifact_service.get_settings",
        _fake_optimizer_settings,
    )
