from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

STATUS_FILE = ROOT / "opencode-status.md"
NEXT_TICKET_FILE = ROOT / "opencode-next-ticket.md"

STATUS_HEADINGS = [
    "## Current Task",
    "## Owner / Session Name",
    "## Branch",
    "## Status",
    "## Files Changed",
    "## What Was Completed",
    "## Remaining Work",
    "## Blockers / Risks",
    "## Validation Run",
    "## Recommended Next Step",
    "## Last Updated Timestamp",
]

NEXT_TICKET_HEADINGS = [
    "## Ticket Title",
    "## Objective",
    "## Scope",
    "## Relevant Files",
    "## Constraints",
    "## Acceptance Criteria",
    "## Validation Steps",
    "## Suggested Follow-up Tasks",
]


def _validate_file(path: Path, required_headings: list[str]) -> list[str]:
    errors: list[str] = []
    if not path.exists():
        return [f"missing file: {path.name}"]

    content = path.read_text(encoding="utf-8")
    for heading in required_headings:
        if heading not in content:
            errors.append(f"missing heading in {path.name}: {heading}")
    return errors


def validate() -> int:
    errors = []
    errors.extend(_validate_file(STATUS_FILE, STATUS_HEADINGS))
    errors.extend(_validate_file(NEXT_TICKET_FILE, NEXT_TICKET_HEADINGS))

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("Handoff files are present and contain required headings.")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 2 or argv[1] != "validate":
        print("Usage: python scripts/opencode_handoff.py validate")
        return 1
    return validate()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
