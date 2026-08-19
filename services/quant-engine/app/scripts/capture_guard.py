"""Refuse to replace a good golden capture with a degraded one (US-35.3).

Epic 35 F-3. `capture_golden_market_data` used to write whatever it recorded and
print the count. On 2026-08-19 it overwrote a **73-series** capture with a
**21-series** one and reported success. The cause was upstream — a broken mapper
emptied SPY, the dashboard run degraded, and far fewer symbols were ever
requested — but the capture had no opinion about it, and the damage was caught
only because a human happened to compare the counts.

`golden_market_data.json` is the foundation of a deliberately network-free
suite: every engine test, every replay pin and `dashboardGoldens.ts` derive from
it. It is also captured rarely and by hand, which is exactly why it should be
loud — nobody runs it often enough to know what a healthy run looks like.

The comparison is against the **committed** fixture rather than a hardcoded
floor. A threshold like "at least 70 series" is another hand-maintained number
that drifts with the statement; the committed file is self-updating and is
already the definition of healthy.
"""
from __future__ import annotations

from typing import Any

# A re-capture legitimately moves by a few rows -- the 2026-08-19 refresh went
# 9,288 -> 9,302 as the European listings gained a terminal-day quote. The guard
# has to catch 9,288 -> 2,771 and ignore ordinary drift, so it is a share, not a
# count. 5% is far below the 70% collapse seen in the incident and far above any
# drift observed across the project's refreshes.
MATERIAL_ROW_LOSS_SHARE = 0.05


def _series_index(payload: dict[str, Any]) -> dict[str, int]:
    """Symbol -> total rows across every captured window."""
    totals: dict[str, int] = {}
    for entry in payload.get("series") or []:
        symbol = entry.get("symbol")
        if not symbol:
            continue
        totals[symbol] = totals.get(symbol, 0) + len(entry.get("rows") or [])
    return totals


def assess_capture_regression(
    new_payload: dict[str, Any],
    committed_payload: dict[str, Any] | None,
    *,
    benchmark_symbol: str = "SPY",
) -> list[str]:
    """Reasons the new capture must not replace the committed one.

    Empty list means acceptable. Each reason is a full sentence naming the
    before/after numbers, so the operator can tell a broken run from a
    legitimately smaller statement without diffing a 2 MB JSON file.
    """
    if committed_payload is None:
        # US-35.3 AC5: a first capture has no baseline. Failing closed here would
        # make the fixture impossible to create.
        return []

    reasons: list[str] = []
    new_series = _series_index(new_payload)
    old_series = _series_index(committed_payload)

    if len(new_series) < len(old_series):
        lost = sorted(set(old_series) - set(new_series))
        detail = f" Missing: {', '.join(lost)}." if lost else ""
        reasons.append(
            f"Series count fell from {len(old_series)} to {len(new_series)}.{detail}"
        )

    new_rows = sum(new_series.values())
    old_rows = sum(old_series.values())
    if old_rows and new_rows < old_rows * (1 - MATERIAL_ROW_LOSS_SHARE):
        share = (old_rows - new_rows) / old_rows * 100
        reasons.append(
            f"Total rows fell from {old_rows:,} to {new_rows:,} ({share:.1f}% lost)."
        )

    # US-35.3 AC2: the sharpest case, and the exact shape of the real incident.
    # SPY was PRESENT in the degraded payload with zero rows, so a naive
    # "is the benchmark there?" check would have passed it.
    if benchmark_symbol in old_series and old_series[benchmark_symbol] > 0:
        if new_series.get(benchmark_symbol, 0) == 0:
            reasons.append(
                f"The benchmark {benchmark_symbol} has no rows "
                f"(it had {old_series[benchmark_symbol]:,}). "
                "Every dashboard figure is measured against it."
            )

    # Any other symbol that went from "has data" to "has none" -- the same
    # failure one level down, and how the 52 lost symbols would have surfaced.
    emptied = sorted(
        symbol
        for symbol, count in old_series.items()
        if count > 0 and symbol in new_series and new_series[symbol] == 0
    )
    if emptied:
        reasons.append(
            f"{len(emptied)} symbol(s) are present but empty: {', '.join(emptied)}."
        )

    return reasons
