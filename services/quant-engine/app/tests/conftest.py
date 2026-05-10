from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def _isolate_generic_ranking_artifact_store(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Isolate the generic_ranking artifact store to a per-test tmp directory.

    The cross-kind ranking catalog scans the generic_ranking artifact directory
    alongside ETF and replacement directories. ETF/replacement tests already
    isolate their own stores via mocker.patch on get_settings; without this
    fixture, generic_ranking artifacts persisted by previous test runs (or by
    the route tests in this run) would leak into ETF-focused tests through
    the catalog and break their assertions.

    Uses tmp_path_factory (not the test's tmp_path) so we don't pollute the
    test's own tmp_path with a generic-ranking-artifacts subdirectory — some
    tests assert that their tmp_path is empty after the operation.

    This is autouse so every test gets isolation by default.
    """
    isolated_dir = tmp_path_factory.mktemp("generic-ranking-artifacts")

    def _fake_settings() -> Any:
        return SimpleNamespace(generic_ranking_artifacts_dir=str(isolated_dir))

    monkeypatch.setattr(
        "app.services.generic_ranking_artifact_service.get_settings",
        _fake_settings,
    )
