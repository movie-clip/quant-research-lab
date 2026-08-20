"""`current-product-state.md`'s route-module inventory may not drift from the
actual routes directory (US-36.3 AC9, T-36.3.2b).

The doc's "N route modules:" bullet list under `## Backend` has already
drifted once — three modules (`cache.py` / Epic 20, `currency_risk.py` /
Epic 26, `provenance.py` / Epic 18) were added to
`services/quant-engine/app/api/routes/` across three separate epics, and none
of them updated the doc's stated count (12) or list. This is exactly the
"checked once, drifted back" pattern `test_docs_paths.py` (Epic 32) exists to
catch for other doc classes — this module gives the route-module inventory
the same mechanical guard, narrowly scoped rather than folded into that file
(see its own docstring: "left for a follow-up rather than widened here").

Scope is deliberately narrow: only the route-module bullet list. No other
claim in `current-product-state.md` is checked here.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "services" / "quant-engine"
ROUTES_DIR = BACKEND_ROOT / "app" / "api" / "routes"
CURRENT_PRODUCT_STATE = REPO_ROOT / "docs" / "product" / "current-product-state.md"

# Matches the doc's own "15 route modules:" bullet header, so a re-count is
# read directly from the doc rather than assumed.
_COUNT_HEADER_RE = re.compile(r"^(\d+)\s+route modules:\s*$", re.MULTILINE)

# Matches each list-item line naming a module, e.g. "- `exposure.py` — ...".
# Anchored to a leading `- \`` so prose mentioning `.py` elsewhere in the doc
# (there is none today, but the regex should not accidentally widen scope)
# is not swept in.
_LIST_ITEM_RE = re.compile(r"^-\s+`([A-Za-z0-9_]+\.py)`", re.MULTILINE)


def _actual_route_modules() -> set[str]:
    return {
        path.name
        for path in ROUTES_DIR.glob("*.py")
        if path.name != "__init__.py"
    }


def _doc_stated_count_and_modules() -> tuple[int, set[str]]:
    text = CURRENT_PRODUCT_STATE.read_text(encoding="utf-8")
    count_match = _COUNT_HEADER_RE.search(text)
    assert count_match, (
        "current-product-state.md no longer has a 'N route modules:' header in "
        "the expected '<int> route modules:' shape — this test's regex needs "
        "updating to match the doc's new wording, not silently pass"
    )
    stated_count = int(count_match.group(1))

    # The list immediately follows the header — take the block between the
    # header and the next blank line so a later, unrelated `.py` mention
    # (there is none today, but the boundary should be explicit) can't leak in.
    list_block = text[count_match.end():]
    blank_line = list_block.find("\n\n")
    if blank_line != -1:
        list_block = list_block[:blank_line]
    stated_modules = set(_LIST_ITEM_RE.findall(list_block))
    return stated_count, stated_modules


def test_stated_count_matches_actual_route_module_count() -> None:
    """The integer in 'N route modules:' must match the real directory."""
    stated_count, _ = _doc_stated_count_and_modules()
    actual_modules = _actual_route_modules()
    assert stated_count == len(actual_modules), (
        f"current-product-state.md says '{stated_count} route modules:' but "
        f"services/quant-engine/app/api/routes/ has {len(actual_modules)} "
        f"(excluding __init__.py): {', '.join(sorted(actual_modules))}. "
        "Fix the doc's stated count."
    )


def test_stated_module_list_matches_actual_route_modules() -> None:
    """Every module named in the bullet list must exist, and vice versa.

    Failing this names the specific missing or extra module, matching
    `test_docs_paths.py`'s own "name the offending file" convention rather
    than a bare pass/fail.
    """
    _, stated_modules = _doc_stated_count_and_modules()
    actual_modules = _actual_route_modules()

    undocumented = sorted(actual_modules - stated_modules)
    phantom = sorted(stated_modules - actual_modules)

    assert not undocumented, (
        f"current-product-state.md's route-module list is missing "
        f"{len(undocumented)} module(s) that exist in "
        f"services/quant-engine/app/api/routes/: {', '.join(undocumented)}. "
        "Add a bullet row for each (module name + one-line description)."
    )
    assert not phantom, (
        f"current-product-state.md's route-module list names "
        f"{len(phantom)} module(s) that do not exist in "
        f"services/quant-engine/app/api/routes/: {', '.join(phantom)}. "
        "Remove the stale row(s) — do not create the file."
    )


def test_the_scan_is_not_vacuous() -> None:
    """A scan that silently matches nothing must fail, not pass.

    Every assertion above is of the form "no drift". A regex that stopped
    matching (doc reworded, list moved, directory renamed) would make both
    tests above pass while checking nothing. This pins that real content is
    actually being read and resolved against the real tree.
    """
    assert CURRENT_PRODUCT_STATE.exists(), (
        "docs/product/current-product-state.md moved — the checks above are "
        "checking nothing"
    )
    assert ROUTES_DIR.exists(), (
        "services/quant-engine/app/api/routes/ moved — the checks above are "
        "checking nothing"
    )

    actual_modules = _actual_route_modules()
    assert actual_modules, (
        "no route modules found under app/api/routes/ — the glob or the "
        "layout changed"
    )
    # A module known to exist today, so resolution is proven to work in the
    # passing direction too, not just the absence of failures.
    assert "exposure.py" in actual_modules

    stated_count, stated_modules = _doc_stated_count_and_modules()
    assert stated_count > 0, (
        "parsed a stated route-module count of 0 — the header regex matched "
        "the wrong line"
    )
    assert stated_modules, (
        "no module names parsed out of current-product-state.md's route-module "
        "list — the list-item regex is broken"
    )
    assert "exposure.py" in stated_modules
