"""PostToolUse hook: after any Edit/Write under app/schemas/, remind the agent
that the Pydantic schema is the contract source of truth — the matching desktop
TS types and docs/contracts/<area>-fields.md must change in the same pass.

Exit code 2 on PostToolUse feeds stderr back to the agent without undoing the
edit (the tool already ran); exit 0 stays silent.
"""

from __future__ import annotations

import json
import sys


def main() -> None:
    try:
        payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    normalized = file_path.replace("\\", "/")
    if "/app/schemas/" not in normalized:
        sys.exit(0)

    print(
        f"CONTRACT REMINDER: you edited {normalized} — app/schemas/ is the "
        "contract source of truth. Update the mirroring desktop TS types "
        "(apps/desktop/src/) and the matching docs/contracts/<area>-fields.md "
        "in the same pass, per CLAUDE.md.",
        file=sys.stderr,
    )
    sys.exit(2)


if __name__ == "__main__":
    main()
