"""`docs/architecture/system-architecture.md`'s registered-router inventory may
not drift from the routers actually registered under `app/api/` (US-41.2 AC11,
AC12, T-41.2.3).

The architecture doc's "Current Implemented Backend Seams" section carried a
stale route/seam inventory naming route paths (`/backtests/*`, `/construction/*`,
`/optimizer/*`, `/ranking/*`, `/strategy-lab/*`) and service files that no
longer exist. The US-41.2 rewrite replaced it with a `### Registered routers`
block: a count-header sentence plus one contiguous bullet list, one bullet per
route module. This module gives that block the same mechanical drift guard that
`test_route_inventory.py` (US-36.3) gives `current-product-state.md`'s route
list — deliberately a narrow sibling, not folded into that file (its docstring
scopes it to "only the route-module bullet list" of one specific doc, and its
key differs: that doc lists `<module>.py`, this one lists bare `<module>`).

Scope is deliberately narrow: only the `### Registered routers` count-header and
bullet list. No other claim in `system-architecture.md` is checked here.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
BACKEND_ROOT = REPO_ROOT / "services" / "quant-engine"
ROUTES_DIR = BACKEND_ROOT / "app" / "api" / "routes"
SYSTEM_ARCH_DOC = REPO_ROOT / "docs" / "architecture" / "system-architecture.md"

# Matches the doc's own "The engine registers N routers" count-header, so the
# count is read directly from the doc rather than assumed.
_COUNT_HEADER_RE = re.compile(r"^The engine registers (\d+) routers?\b", re.MULTILINE)

# Matches each list-item line naming a router module, e.g.
# "- `dashboard_history` — POST /engines/dashboard-history/...". Anchored to a
# leading "- `" with a bare lowercase module stem as the first backticked
# token, so the "Grouped by role:" bullets ("- **Import** — ...") and the
# "### Service layer" bullets ("- Per-engine services: `x.py`, ...") that follow
# the list cannot be swept in even if the block boundary were to move.
_LIST_ITEM_RE = re.compile(r"^-\s+`([a-z0-9_]+)`", re.MULTILINE)


def _actual_route_modules() -> set[str]:
    return {
        path.stem
        for path in ROUTES_DIR.glob("*.py")
        if path.name != "__init__.py"
    }


def _doc_stated_count_and_modules() -> tuple[int, set[str]]:
    text = SYSTEM_ARCH_DOC.read_text(encoding="utf-8")
    count_match = _COUNT_HEADER_RE.search(text)
    assert count_match, (
        "system-architecture.md no longer has a 'The engine registers N "
        "routers' count-header in the expected shape — this test's regex needs "
        "updating to match the doc's new wording, not silently pass. (Against a "
        "pre-US-41.2 doc with no such header this assertion is the red-before "
        "state AC12 requires.)"
    )
    stated_count = int(count_match.group(1))

    # The bullet list immediately follows the header on the next line, with no
    # blank line between (mirrors current-product-state.md / test_route_inventory
    # .py). Take the block between the header and the first blank line so the
    # "Grouped by role:" / "### Service layer" bullets after that blank line
    # cannot leak in.
    list_block = text[count_match.end():]
    blank_line = list_block.find("\n\n")
    if blank_line != -1:
        list_block = list_block[:blank_line]
    stated_modules = set(_LIST_ITEM_RE.findall(list_block))
    return stated_count, stated_modules


def test_stated_count_matches_actual_router_count() -> None:
    """The integer in 'The engine registers N routers' must match the real
    directory and the real number of list items."""
    stated_count, stated_modules = _doc_stated_count_and_modules()
    actual_modules = _actual_route_modules()

    assert stated_count == len(actual_modules), (
        f"system-architecture.md says 'The engine registers {stated_count} "
        f"routers' but services/quant-engine/app/api/routes/ has "
        f"{len(actual_modules)} module(s) (excluding __init__.py): "
        f"{', '.join(sorted(actual_modules))}. Fix the doc's stated count."
    )
    assert stated_count == len(stated_modules), (
        f"system-architecture.md says 'The engine registers {stated_count} "
        f"routers' but its '### Registered routers' bullet list has "
        f"{len(stated_modules)} item(s): {', '.join(sorted(stated_modules))}. "
        "The count-header and the list must agree."
    )


def test_stated_module_list_matches_actual_route_modules() -> None:
    """Every module named in the bullet list must exist as a route module, and
    every registered route module must appear in the list.

    Failing this names the specific missing or extra module, matching
    `test_route_inventory.py`'s "name the offending file" convention rather than
    a bare pass/fail.
    """
    _, stated_modules = _doc_stated_count_and_modules()
    actual_modules = _actual_route_modules()

    undocumented = sorted(actual_modules - stated_modules)
    phantom = sorted(stated_modules - actual_modules)

    assert not undocumented, (
        f"system-architecture.md's '### Registered routers' list is missing "
        f"{len(undocumented)} module(s) that exist in "
        f"services/quant-engine/app/api/routes/: {', '.join(undocumented)}. "
        "Add a bullet row for each (module stem + one-line description) and "
        "bump the count-header."
    )
    assert not phantom, (
        f"system-architecture.md's '### Registered routers' list names "
        f"{len(phantom)} module(s) that do not exist in "
        f"services/quant-engine/app/api/routes/: {', '.join(phantom)}. "
        "Remove the stale row(s) and fix the count-header — do not create the "
        "file."
    )


def test_the_scan_is_not_vacuous() -> None:
    """A scan that silently matches nothing must fail, not pass.

    Every assertion above is of the form "no drift". A regex that stopped
    matching (doc reworded, section moved, directory renamed, blank line
    inserted into the list) would make both tests above pass while checking
    nothing. This pins that real content is actually being read and resolved
    against the real tree.
    """
    assert SYSTEM_ARCH_DOC.exists(), (
        "docs/architecture/system-architecture.md moved — the checks above are "
        "checking nothing"
    )
    assert ROUTES_DIR.exists(), (
        "services/quant-engine/app/api/routes/ moved — the checks above are "
        "checking nothing"
    )

    actual_modules = _actual_route_modules()
    assert actual_modules, (
        "no route modules found under app/api/routes/ — the glob or the layout "
        "changed"
    )
    # A module known to exist today, so resolution is proven to work in the
    # passing direction too, not just the absence of failures.
    assert "exposure" in actual_modules

    stated_count, stated_modules = _doc_stated_count_and_modules()
    assert stated_count > 0, (
        "parsed a stated router count of 0 — the count-header regex matched "
        "the wrong line"
    )
    assert stated_modules, (
        "no module stems parsed out of system-architecture.md's '### Registered "
        "routers' list — the list-item regex is broken or a blank line split "
        "the list"
    )
    assert "exposure" in stated_modules
