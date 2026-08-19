"""The committed capture's benchmark basis, asserted rather than assumed (US-34.9).

Epic 34 **F-9** was a rung whose tests passed for eighteen months while the
shipped data could never satisfy it. `_validate_verified_benchmark_slice`
required every row to carry `adjClose`; every test supplied hand-written rows
that did; and the real capture had none on any US symbol. Nothing connected the
two, so nothing failed.

US-34.9 fixes the endpoint. These tests fix the *blind spot*: they read the
committed `golden_market_data.json` and pin what it actually contains, next to
the basis the engine derives from it. If the data is re-captured and SPY starts
carrying `adjClose`, these fail — deliberately — and the fix is to update them
together with the goldens and the docs, which is exactly the review F-9 never
got.

They are also the reason the suite can stay network-free: the capture is the
only evidence available offline about what the provider really returns.
"""
from __future__ import annotations

import json

from app.scripts.frozen_market_data import GOLDEN_MARKET_DATA_PATH
from app.services.market_data import (
    classify_history_return_basis_contract,
    detect_history_return_basis,
)


def _spy_rows() -> list[dict]:
    """Every captured SPY row, across all windows.

    The capture holds several SPY series (the engines request different date
    ranges), so reading only the first would leave the rest unpinned — and a
    partial re-capture is exactly the state these tests exist to catch.
    """
    payload = json.loads(GOLDEN_MARKET_DATA_PATH.read_text(encoding="utf-8"))
    rows = [
        row
        for entry in payload["series"]
        if entry.get("symbol") == "SPY"
        for row in (entry.get("rows") or [])
    ]
    assert rows, "the frozen capture has no SPY series"
    return rows


def test_committed_spy_capture_carries_no_adjusted_close() -> None:
    """US-34.9 AC7 — the state of the shipped data, stated as a number.

    This is the fact F-9 turned on. It is asserted here so that "SPY has no
    adjClose" is a *tested* property of the repository rather than a claim in a
    findings document that silently rots.

    When the owner re-captures with an `FMP_API_KEY` against the
    dividend-adjusted endpoint, this test fails and must be rewritten to assert
    full coverage — that failure is the intended trigger for updating the
    goldens, the US-34.5 basis pins and the methodology together.
    """
    rows = _spy_rows()

    adjusted = [row for row in rows if row.get("adjClose") is not None]
    assert adjusted == [], (
        f"{len(adjusted)} of {len(rows)} SPY rows now carry adjClose — the capture "
        "has been refreshed against the dividend-adjusted endpoint. Update this "
        "test, the US-34.5 basis pins, dashboardGoldens.ts and the methodology's "
        "mixed-basis subsection together (US-34.9 T-34.9.6)."
    )


def test_the_basis_the_engine_derives_matches_the_committed_capture() -> None:
    """US-34.9 AC7 — code and data are pinned to each other, not separately.

    Asserting the row contents alone would still allow the classifier to drift
    away from them. This asserts the derived basis in the same test, so the pair
    can never disagree silently the way F-9's validator and capture did.
    """
    rows = _spy_rows()

    assert detect_history_return_basis(rows) == "unverified_close_only"
    assert classify_history_return_basis_contract(rows) == "price_return_only"


def test_adjusted_closes_do_reach_this_repo_but_only_from_the_fallback() -> None:
    """US-34.9 AC9 / F-13 — the claim the `fmp-data` skill got backwards.

    The skill told agents the `light` endpoint returns `adjClose` for *US-listed*
    equities and ETFs. The capture says the opposite: adjusted closes are present
    only for **non-US** listings, which are the symbols FMP cannot serve and the
    **yfinance** fallback supplies. Pinning it here means the corrected claim is
    checkable rather than merely rewritten.
    """
    payload = json.loads(GOLDEN_MARKET_DATA_PATH.read_text(encoding="utf-8"))
    with_adjusted = {
        entry["symbol"]
        for entry in payload["series"]
        if any(row.get("adjClose") is not None for row in (entry.get("rows") or []))
    }

    assert with_adjusted, "no series carries adjClose — the fallback path stopped supplying it"
    # The US names FMP serves directly carry none of it.
    assert not with_adjusted & {"SPY", "AAPL", "AMZN", "ASML", "CRM"}
    # The UCITS/LSE listings the fallback resolves carry all of it.
    assert {"SXRV", "VUAA", "IUIT", "SGLD"} <= with_adjusted
