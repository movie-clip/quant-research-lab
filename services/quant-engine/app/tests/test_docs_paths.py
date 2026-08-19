"""Agent-facing docs may not name backend paths that do not exist (US-32.1).

Epic 32 F-3/F-4. CLAUDE.md told every implementer to register routes in
`app/main.py` — a file this repository has never had — and the `write-story`
module table named three analytics modules that do not exist while omitting
eight that do.

**The table had been corrected twice before and drifted back both times.** The
`quant-research` skill carried a warning telling readers not to trust it and to
`ls` the directory first. A document that admits it cannot be trusted is a
document that should be checked mechanically, so these tests replace the
warning's job: a phantom path or a missing module fails the suite instead of
costing the next reader an hour.

This is the same move US-24.5 made for broker section labels and US-34.9 made
for the committed market-data capture — pin the class, not the instance.

Scope is deliberately narrow: `app/...` paths in CLAUDE.md and the skills. The
paths under `docs/finance/` and `docs/contracts/` were verified correct when the
story was written and are left for a follow-up rather than widened here.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "services" / "quant-engine"
ANALYTICS_DIR = BACKEND_ROOT / "app" / "analytics"

CLAUDE_MD = REPO_ROOT / "CLAUDE.md"
SKILL_FILES = sorted((REPO_ROOT / ".claude" / "skills").glob("*/SKILL.md"))

# `app/<something>/<file>.py` or `app/<file>.py`, as written in prose or a table.
# Backticks are stripped by the caller; the trailing `.py` keeps this to real
# module references rather than directory mentions like `app/analytics/`.
_APP_PATH = re.compile(r"\bapp/(?:[A-Za-z0-9_]+/)*[A-Za-z0-9_]+\.py\b")


# Table rows are prefixed with this before cue-matching, so `_claims` can tell a
# row from prose without re-parsing. It carries no cue text, so a row can never
# be read as a denial.
_TABLE_ROW_MARKER = "<!--table-row-->"

# Phrases that mark a path as one the doc is asserting does NOT exist — the
# `quant-research` skill, for instance, names the modules earlier versions of
# its table got wrong. Those are claims too, so they are checked in the opposite
# direction rather than exempted: a doc saying "app/foo.py does not exist" fails
# if it does. There is deliberately no way to opt a path out of being checked.
_ABSENCE_CUES = (
    "do not exist",
    "does not exist",
    "don't exist",
    "doesn't exist",
    "no separate",
    "there is no",
    "never had",
)


def _referenced_app_paths(text: str) -> set[str]:
    return set(_APP_PATH.findall(text))


def _negation_scopes(text: str) -> list[str]:
    """The chunks negation is judged within.

    Prose wraps, so a sentence saying a path is wrong often names it on the
    following line — those need paragraph scope. A markdown TABLE, though, is
    one unbroken block, so paragraph scope would let a single row saying "there
    is no `analytics/drift.py`" excuse every other row in the table.

    A table ROW is therefore always read as a POSITIVE claim, cue or not. Rows
    routinely say "…lives in the service, there is no `analytics/drift.py`"
    while also naming the module that really does exist, and one cue must not
    excuse the row's real path. Discussion of paths that were wrong belongs in
    prose, which is where the cues are honoured.
    """
    scopes: list[str] = []
    for block in text.split("\n\n"):
        lines = block.splitlines()
        if any(line.lstrip().startswith("|") for line in lines):
            scopes.extend(_TABLE_ROW_MARKER + line for line in lines)
        else:
            scopes.append(block)
    return scopes


def _claims(doc: Path) -> tuple[list[str], list[str]]:
    """(paths the doc claims exist, paths the doc claims do NOT exist)."""
    present_claims: set[str] = set()
    absent_claims: set[str] = set()
    for block in _negation_scopes(doc.read_text(encoding="utf-8")):
        is_table_row = block.startswith(_TABLE_ROW_MARKER)
        lowered = block.lower()
        negated = (not is_table_row) and any(cue in lowered for cue in _ABSENCE_CUES)
        target = absent_claims if negated else present_claims
        target.update(_referenced_app_paths(block))
    # A path claimed both ways in one document is ambiguous; treat the positive
    # claim as binding so the stricter check wins.
    absent_claims -= present_claims
    return sorted(present_claims), sorted(absent_claims)


def _wrong_claims(doc: Path) -> tuple[list[str], list[str]]:
    """(claimed present but missing, claimed absent but present)."""
    present_claims, absent_claims = _claims(doc)
    return (
        [p for p in present_claims if not (BACKEND_ROOT / p).exists()],
        [p for p in absent_claims if (BACKEND_ROOT / p).exists()],
    )


def _missing_paths(doc: Path) -> list[str]:
    return _wrong_claims(doc)[0]


def test_claude_md_names_only_backend_paths_that_exist() -> None:
    """US-32.1 AC1/AC5/AC6 — CLAUDE.md is injected into every agent's context.

    A wrong path here is read on every task in the repository, which is why this
    file is checked separately rather than folded into the skills sweep.
    """
    missing = _missing_paths(CLAUDE_MD)
    assert not missing, (
        f"CLAUDE.md names {len(missing)} backend path(s) that do not exist: "
        f"{', '.join(missing)}. Fix the document — do not add the file."
    )


@pytest.mark.parametrize("skill_file", SKILL_FILES, ids=lambda p: p.parent.name)
def test_skill_names_only_backend_paths_that_exist(skill_file: Path) -> None:
    """US-32.1 AC3/AC4/AC5/AC6 — one case per skill, so the failure names it.

    Parametrising rather than looping means a broken `write-story` does not hide
    behind a broken `quant-research`, and the failing skill is in the test id.
    """
    missing, wrongly_denied = _wrong_claims(skill_file)
    assert not missing, (
        f"{skill_file.parent.name}/SKILL.md names {len(missing)} backend path(s) "
        f"that do not exist: {', '.join(missing)}. Fix the document."
    )
    assert not wrongly_denied, (
        f"{skill_file.parent.name}/SKILL.md says {', '.join(wrongly_denied)} "
        "does not exist, but it does. Fix the document."
    )


def test_write_story_table_covers_every_analytics_module() -> None:
    """US-32.1 AC3 — the other half of the drift.

    Removing phantom rows only fixes today's error. The table was also missing
    eight real modules, which is how a story gets filed against the wrong module
    in the first place. This fails when a NEW analytics module is added without
    being described.
    """
    modules = {
        f"app/analytics/{path.name}"
        for path in ANALYTICS_DIR.glob("*.py")
        if path.name != "__init__.py"
    }
    assert modules, "no analytics modules found — the glob or the layout changed"

    documented = _referenced_app_paths(
        (REPO_ROOT / ".claude" / "skills" / "write-story" / "SKILL.md").read_text(encoding="utf-8")
    )
    undocumented = sorted(modules - documented)
    assert not undocumented, (
        f"write-story/SKILL.md does not describe {len(undocumented)} analytics "
        f"module(s): {', '.join(undocumented)}. Add a row saying what belongs there."
    )


def test_the_scan_is_not_vacuous() -> None:
    """US-32.1 AC7 — a scan that finds nothing must fail, not pass.

    Every assertion above is of the form "no missing paths". A regex that
    silently stopped matching, or a docs reorganisation that moved these files,
    would make all of them pass while checking nothing at all. This pins that
    the scan really is reading real content and resolving it against the tree.
    """
    assert CLAUDE_MD.exists(), "CLAUDE.md moved — the sweep above is checking nothing"
    assert SKILL_FILES, "no SKILL.md files found — the sweep above is checking nothing"

    found = _referenced_app_paths(CLAUDE_MD.read_text(encoding="utf-8"))
    assert found, "no app/... paths matched in CLAUDE.md — the regex is broken"
    # A path known to exist, so resolution is proven to work in the passing
    # direction too, not just the absence of failures.
    assert "app/api/main.py" in found, (
        "CLAUDE.md no longer references app/api/main.py — either the route "
        "instruction regressed, or this canary needs updating"
    )
    assert (BACKEND_ROOT / "app/api/main.py").exists()

    # And in the failing direction: a path that does not exist must be caught.
    assert not (BACKEND_ROOT / "app/main.py").exists(), (
        "app/main.py now exists — this test's premise (and CLAUDE.md's old "
        "instruction) needs revisiting"
    )

    # The negation branch must actually be exercised somewhere, or a doc could
    # smuggle a phantom path past the check by wording it as a denial.
    denials = {
        skill.parent.name: _claims(skill)[1]
        for skill in SKILL_FILES
        if _claims(skill)[1]
    }
    assert denials, (
        "no document asserts a path is absent — the negation branch is dead, so "
        "a phantom path could hide behind an absence cue unchecked"
    )
