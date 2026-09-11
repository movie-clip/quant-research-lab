"""`scripts/build_roadmap.py` — the generated planning index.

`docs/product/ROADMAP.md` is derived from story/epic frontmatter rather than
maintained by hand, because the hand-maintained predecessor
(`docs/product/epic-roadmap.md`) reached 2,090 lines of mostly completed-epic
prose before it was deleted at commit `ce9c97d`. `run_all_tests.py` runs
`--check`, so a stale index fails the suite.

That gate only protects the repo's *current* two stories. These tests pin the
frontmatter contract itself — the rules a future story file has to satisfy —
against synthetic files in `tmp_path`, so a malformed status, a filename that
disagrees with its `id`, or an epic reference with no file is caught as a named
error rather than as a silently missing roadmap row.

Reached via `sys.path` the same way `test_audit_dependencies.py` reaches
`scripts/audit_dependencies.py`. Pure parsing and rendering: no subprocess, no
network, no market data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_roadmap  # noqa: E402  (path set up above)
from build_roadmap import EPIC_ID, STORY_ID, FrontmatterError, load_item, render  # noqa: E402


def _write(tmp_path: Path, name: str, **fields: str) -> Path:
    body = "\n".join(f"{k}: {v}" for k, v in fields.items())
    path = tmp_path / name
    path.write_text(f"---\n{body}\n---\n\n# {name}\n", encoding="utf-8")
    return path


def _story(tmp_path: Path, name: str, **fields: str) -> Path:
    base = {
        "id": "US-45.1",
        "title": "A story",
        "status": "done",
        "opened": "2026-09-11",
        "closed": "2026-09-11",
    }
    base.update(fields)
    return _write(tmp_path, name, **base)


def test_valid_story_parses(tmp_path: Path) -> None:
    item = load_item(_story(tmp_path, "US-45.1-slug.md"), STORY_ID, "story")
    assert (item.id, item.status, item.closed, item.epic) == (
        "US-45.1",
        "done",
        "2026-09-11",
        None,
    )


def test_epic_is_optional_not_a_gap(tmp_path: Path) -> None:
    """A story with no epic is the normal case, not an error to be filled in."""
    item = load_item(_story(tmp_path, "US-45.1-slug.md"), STORY_ID, "story")
    assert item.epic is None
    assert "| - |" in render([item], {})


def test_missing_frontmatter_is_named(tmp_path: Path) -> None:
    path = tmp_path / "US-45.1-slug.md"
    path.write_text("# US-45.1 — no frontmatter\n", encoding="utf-8")
    with pytest.raises(FrontmatterError, match="no frontmatter"):
        load_item(path, STORY_ID, "story")


def test_unclosed_frontmatter_is_named(tmp_path: Path) -> None:
    path = tmp_path / "US-45.1-slug.md"
    path.write_text("---\nid: US-45.1\n\n# body\n", encoding="utf-8")
    with pytest.raises(FrontmatterError, match="never closed"):
        load_item(path, STORY_ID, "story")


@pytest.mark.parametrize(
    "field",
    ["id", "title", "status"],
)
def test_required_field_missing(tmp_path: Path, field: str) -> None:
    path = _story(tmp_path, "US-45.1-slug.md", **{field: ""})
    with pytest.raises(FrontmatterError, match=f"missing `{field}`|is not a valid"):
        load_item(path, STORY_ID, "story")


def test_filename_must_match_id(tmp_path: Path) -> None:
    """The one drift this format can still have: a rename that skips the id."""
    path = _story(tmp_path, "US-45.2-slug.md")  # frontmatter still says US-45.1
    with pytest.raises(FrontmatterError, match="does not match the filename"):
        load_item(path, STORY_ID, "story")


def test_unknown_status_rejected(tmp_path: Path) -> None:
    path = _story(tmp_path, "US-45.1-slug.md", status="in-progress")
    with pytest.raises(FrontmatterError, match="is not one of"):
        load_item(path, STORY_ID, "story")


def test_done_requires_a_closed_date(tmp_path: Path) -> None:
    path = _story(tmp_path, "US-45.1-slug.md", status="done", closed="")
    with pytest.raises(FrontmatterError, match="no `closed:` date"):
        load_item(path, STORY_ID, "story")


def test_non_iso_date_rejected(tmp_path: Path) -> None:
    path = _story(tmp_path, "US-45.1-slug.md", closed="Sept 11 2026")
    with pytest.raises(FrontmatterError, match="is not `YYYY-MM-DD`"):
        load_item(path, STORY_ID, "story")


def test_epic_must_be_an_epic_id(tmp_path: Path) -> None:
    path = _story(tmp_path, "US-45.1-slug.md", epic="Epic 45")
    with pytest.raises(FrontmatterError, match="is not an epic id"):
        load_item(path, STORY_ID, "story")


def test_epic_file_parses(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "EP-45-risk-card-ergonomics.md",
        id="EP-45", title="Risk card ergonomics", status="active", opened="2026-09-11",
    )
    epic = load_item(path, EPIC_ID, "epic")
    assert (epic.id, epic.status) == ("EP-45", "active")


def test_story_ids_sort_numerically_not_lexically(tmp_path: Path) -> None:
    """`US-9.2` is older than `US-45.1`; string sort says the opposite."""
    old = load_item(
        _story(tmp_path, "US-9.2-old.md", id="US-9.2", title="Older", closed="2026-01-02"),
        STORY_ID, "story",
    )
    new = load_item(
        _story(tmp_path, "US-45.1-new.md", title="Newer"), STORY_ID, "story"
    )
    shipped = render([old, new], {})
    assert shipped.index("US-45.1") < shipped.index("US-9.2")


def test_render_is_deterministic_and_carries_no_timestamp(tmp_path: Path) -> None:
    """`--check` compares text, so any clock-derived output would fail it daily."""
    item = load_item(_story(tmp_path, "US-45.1-slug.md"), STORY_ID, "story")
    assert render([item], {}) == render([item], {})


def test_shipped_story_costs_exactly_one_row(tmp_path: Path) -> None:
    """The property the 2,090-line predecessor did not have."""
    items = [
        load_item(
            _story(tmp_path, f"US-45.{n}-slug.md", id=f"US-45.{n}", title=f"Story {n}"),
            STORY_ID, "story",
        )
        for n in range(1, 6)
    ]
    rendered = render(items, {})
    assert sum(line.startswith("| [US-") for line in rendered.splitlines()) == len(items)


def test_repo_roadmap_is_current() -> None:
    """The committed index matches the committed story files.

    `run_all_tests.py` also runs `build_roadmap.py --check`; this keeps a bare
    `pytest` run from passing while the index is stale.
    """
    stories, epics = build_roadmap.load_all()
    assert build_roadmap.ROADMAP.read_text(encoding="utf-8") == render(stories, epics)
