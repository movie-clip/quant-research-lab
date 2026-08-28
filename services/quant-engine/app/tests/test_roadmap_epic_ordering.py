"""`docs/product/epic-roadmap.md`'s per-epic section headings may not drift out
of the file's consistent order (US-41.3 AC4, T-41.3.4).

The roadmap's completed-epic slice log is a long run of self-contained per-epic
section blocks, each opening with a `## Completed Epic: Epic <N> — <title>`
heading, laid out in strictly descending epic-number order (Epic 40 down to
Epic 8). That order has now drifted twice — the 2026-08-27 health review caught
the Epic 23 / Epic 24 blocks transposed (Epic 23's heading precedes Epic 24's),
which is why AC4 exists. This module gives the ordering the same mechanical
re-drift guard that `test_route_inventory.py` (US-36.3) gives
`current-product-state.md`'s route list and
`test_architecture_doc_route_inventory.py` (US-41.2) gives
`system-architecture.md`'s router inventory — a deliberately narrow sibling
file, not folded into either of those (they guard route/router inventories; this
guards heading order in a different doc) and not into `test_docs_paths.py` (that
guards path claims, not ordering).

Scope is deliberately narrow: only the order and the non-vacuity of the
per-epic section headings. No other claim in `epic-roadmap.md` is checked here.

Red-before / green-after: against the roadmap as it stands before T-41.3.1's
Epic 23 / Epic 24 block swap lands, `test_epic_sections_are_in_descending_order`
FAILS naming that transposed pair; it goes green only once the swap restores the
descending run.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
EPIC_ROADMAP_DOC = REPO_ROOT / "docs" / "product" / "epic-roadmap.md"

# Matches every per-epic section heading. The completed-epic slice log uses
# `## Completed Epic: Epic <N> — <title>`; the `Completed Epic:` prefix is
# optional in the pattern so an active-epic heading in the shorter
# `## Epic <N> — <title>` form (none exist today — Epic 41's section is added at
# close-out, not in this story) is also swept in rather than silently escaping
# the order check. The non-vacuous count below protects against either form
# being reworded out of matching.
_HEADING_RE = re.compile(r"^##\s+(?:Completed Epic:\s+)?Epic\s+(\d+)\b")

# There are 33 per-epic headings today (Epic 40 down to Epic 8). A scan that
# resolves to far fewer means the heading form changed or the file moved.
_MIN_EXPECTED_HEADINGS = 20


def _epic_heading_sequence() -> list[tuple[int, str]]:
    """Every per-epic section heading, in file order, as (epic_number, line)."""
    text = EPIC_ROADMAP_DOC.read_text(encoding="utf-8")
    sequence: list[tuple[int, str]] = []
    for line in text.splitlines():
        match = _HEADING_RE.match(line)
        if match:
            sequence.append((int(match.group(1)), line.strip()))
    return sequence


def test_epic_sections_are_in_descending_order() -> None:
    """Per-epic section headings must run strictly descending down the file.

    On failure this names the specific out-of-order heading pair, matching the
    "name the offending entry" convention of `test_route_inventory.py` and
    `test_architecture_doc_route_inventory.py` rather than a bare
    `assert sequence == sorted(...)`.
    """
    sequence = _epic_heading_sequence()
    assert sequence, (
        "no per-epic section headings matched in docs/product/epic-roadmap.md — "
        "the ordering check is scanning nothing; see test_the_scan_is_not_vacuous"
    )

    for (prev_num, prev_line), (curr_num, curr_line) in zip(sequence, sequence[1:]):
        assert curr_num < prev_num, (
            f"epic-roadmap.md per-epic sections are out of order: "
            f'"{prev_line}" precedes "{curr_line}", but epic-number headings '
            f"must run strictly descending down the file. Epic {prev_num} should "
            f"be followed by a lower-numbered epic, not Epic {curr_num}. Swap the "
            f"two section blocks so the run stays monotonic (no heading text, PRD "
            f"link or slice-log row is reworded in the move)."
        )


def test_the_scan_is_not_vacuous() -> None:
    """A scan that silently matches nothing (or almost nothing) must fail.

    `test_epic_sections_are_in_descending_order` is of the form "no drift": a
    regex that stopped matching (heading form reworded, file moved/renamed)
    would make it pass while checking nothing. This pins that real content is
    actually being read and resolved.
    """
    assert EPIC_ROADMAP_DOC.exists(), (
        "docs/product/epic-roadmap.md moved — the ordering check above is "
        "checking nothing"
    )

    sequence = _epic_heading_sequence()
    numbers = [num for num, _ in sequence]

    assert len(sequence) >= _MIN_EXPECTED_HEADINGS, (
        f"only {len(sequence)} per-epic section heading(s) matched in "
        f"epic-roadmap.md (expected at least {_MIN_EXPECTED_HEADINGS}) — the "
        f"'## Completed Epic: Epic <N> — <title>' heading form was reworded, or "
        f"the file moved. The ordering check above is now scanning almost "
        f"nothing."
    )

    # A heading known to exist today, so resolution is proven to work in the
    # passing direction too, not just the absence of failures.
    assert 40 in numbers, (
        "Epic 40 — the most recently shipped epic — has no per-epic section "
        "heading matched in epic-roadmap.md; the heading regex has drifted from "
        "the doc's actual format"
    )
