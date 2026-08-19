"""The cache CLI must be able to name every namespace it holds (US-35.2).

Epic 35 F-2. `manage_cache.py list` reported `history_yf`, `holdings`, `fx` and
`history`; `clear --namespace` accepted only `{quote, history, fx, fmp}`. So an
operator who had just poisoned the history cache could reason "clear history",
get a **partial** clear, and be told `Removed 172 cache file(s).` with no hint
that 51 entries were left standing.

That happened during US-34.9 and cost a second confused debugging round on top
of the first.

Note what is NOT broken: the namespace glob includes the `-` separator, so
`history-*.json` never matched `history_yf-abc.json`. The matching was always
exact. The defect was the hand-written `choices` list and the silence.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS = REPO_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import manage_cache  # noqa: E402
from app.core.cache import JsonFileCache  # noqa: E402


@pytest.fixture
def mixed_cache(tmp_path, monkeypatch):
    """A cache holding both provider histories, plus an unrelated namespace."""
    cache = JsonFileCache(tmp_path)
    cache.set(cache.build_key("history", "historical:SPY"), [{"date": "2026-01-02", "price": 1.0}])
    cache.set(cache.build_key("history", "historical:AAPL"), [{"date": "2026-01-02", "price": 2.0}])
    cache.set(cache.build_key("history_yf", "historical:VUAA.L"), [{"date": "2026-01-02", "price": 3.0}])
    cache.set(cache.build_key("holdings", "etf:SPY"), [{"asset": "AAPL"}])
    monkeypatch.setattr(manage_cache, "_cache", lambda: JsonFileCache(tmp_path))
    return cache


def test_the_cli_can_target_a_namespace_the_old_choice_list_omitted(mixed_cache, capsys) -> None:
    """US-35.2 AC1 — `history_yf` was unnameable; now it is not.

    `argparse` used to reject it outright with `invalid choice`, so the only way
    to clear the yfinance cache was to clear everything.
    """
    assert manage_cache.main(["clear", "--namespace", "history_yf"]) == 0

    remaining = mixed_cache.namespaces()
    assert "history_yf" not in remaining
    assert remaining.get("history") == 2, "the FMP history cache must be untouched"
    assert remaining.get("holdings") == 1


def test_the_accepted_namespaces_are_derived_not_hand_written(mixed_cache, capsys) -> None:
    """US-35.2 AC1 — the mechanism, not just today's instance.

    Nothing declares the namespace set: one exists because some caller passed
    that string to `build_key`. A literal `choices=[…]` is therefore guaranteed
    to drift, and had — `holdings`, `profile`, `fundamentals`, `screener` and
    `index_constituents` were all unnameable too.

    This uses a namespace no version of the old list contained, so it fails if
    anyone reintroduces a hand-maintained list.
    """
    assert manage_cache.main(["clear", "--namespace", "holdings"]) == 0
    assert "holdings" not in mixed_cache.namespaces()


def test_a_partial_clear_says_what_it_left_behind(mixed_cache, capsys) -> None:
    """US-35.2 AC3 — the silence is the bug, not the exactness.

    Clearing `history` correctly leaves `history_yf` alone. The failure was that
    it said so nowhere, so "I cleared the history cache" was true-but-misleading
    and only surfaced during the next debugging round.
    """
    assert manage_cache.main(["clear", "--namespace", "history"]) == 0

    out = capsys.readouterr().out
    assert "Removed 2 cache file(s)." in out
    assert "Still cached:" in out
    assert "history_yf" in out
    # The note has to say it was NOT cleared, not merely that it exists.
    assert "NOT cleared" in out
    assert mixed_cache.namespaces().get("history_yf") == 1


def test_an_unknown_namespace_is_rejected_rather_than_silently_doing_nothing(
    mixed_cache, capsys
) -> None:
    """US-35.2 AC6 — `Removed 0 cache file(s).` was indistinguishable from success.

    A typo ("histroy") used to look exactly like an already-empty namespace.
    """
    assert manage_cache.main(["clear", "--namespace", "histroy"]) == 1

    err = capsys.readouterr().err
    assert "No such namespace" in err
    assert "history" in err, "the message must list what IS present"
    assert sum(mixed_cache.namespaces().values()) == 4, "nothing may be removed on a typo"


def test_clearing_everything_still_works(mixed_cache, capsys) -> None:
    """US-35.2 AC5 — the escape hatch this story must not take away."""
    assert manage_cache.main(["clear"]) == 0
    assert mixed_cache.namespaces() == {}


def test_list_summarises_by_namespace(mixed_cache, capsys) -> None:
    """US-35.2 AC4 — choosing what to clear needs a summary, not 200 hashes."""
    assert manage_cache.main(["list"]) == 0

    out = capsys.readouterr().out
    assert "Namespaces:" in out
    assert "history_yf" in out
    assert "TOTAL" in out
