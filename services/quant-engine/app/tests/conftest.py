from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _isolate_generic_ranking_artifact_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate the generic_ranking artifact store to a per-test tmp directory.

    The cross-kind ranking catalog scans the generic_ranking artifact directory
    alongside ETF and replacement directories. ETF/replacement tests already
    isolate their own stores via mocker.patch on get_settings; without this
    fixture, generic_ranking artifacts persisted by previous test runs (or by
    the route tests in this run) would leak into ETF-focused tests through
    the catalog and break their assertions.

    This is autouse so every test gets isolation by default. Tests that need
    to inspect the real artifact directory can override the fixture.
    """
    isolated_dir = tmp_path / "generic-ranking-artifacts"
    isolated_dir.mkdir(parents=True, exist_ok=True)

    # Patch the settings used by the generic ranking artifact store.
    # Build a SimpleNamespace that mirrors the real settings shape; only
    # generic_ranking_artifacts_dir matters for the store.
    def _fake_settings() -> Any:
        return SimpleNamespace(generic_ranking_artifacts_dir=str(isolated_dir))

    monkeypatch.setattr(
        "app.services.generic_ranking_artifact_service.get_settings",
        _fake_settings,
    )
