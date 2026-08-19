"""The committed capture's benchmark basis, asserted rather than assumed (US-34.9).

Epic 34 **F-9** was a rung whose tests passed for eighteen months while the
shipped data could never satisfy it. `_validate_verified_benchmark_slice`
required every row to carry `adjClose`; every test supplied hand-written rows
that did; and the real capture had none on any US symbol. Nothing connected the
two, so nothing failed.

US-34.9 fixed the endpoint. These tests fix the *blind spot*: they read the
committed `golden_market_data.json` and pin what it actually contains, next to
the basis the engine derives from it — so a change to either side has to come
through here rather than around it. They did exactly that job on the 2026-08-17
re-capture, failing deliberately and forcing this file, the US-34.5 basis pins,
the goldens and the methodology to be updated together.

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


def test_committed_spy_capture_is_fully_dividend_adjusted() -> None:
    """US-34.9 AC7 — the state of the shipped data, stated as a number.

    Before the 2026-08-17 re-capture this asserted the opposite: SPY carried
    **zero** adjusted closes, because the pinned endpoint returned none. That is
    the fact F-9 turned on, and it was asserted here precisely so the re-capture
    would have to come through this test rather than around it.

    It now pins the other side: complete coverage. Partial coverage is the
    dangerous middle state — it would splice two bases into one chain — so the
    assertion is completeness, not merely presence.
    """
    rows = _spy_rows()

    unadjusted = [row for row in rows if row.get("adjClose") is None]
    assert unadjusted == [], (
        f"{len(unadjusted)} of {len(rows)} SPY rows have no adjClose. A PARTIALLY "
        "adjusted benchmark cannot be published as a total return -- check the "
        "capture rather than relaxing this test."
    )
    assert len(rows) > 100, "the frozen SPY window shrank unexpectedly"


def test_the_capture_is_ordered_so_the_verified_slice_can_be_admitted() -> None:
    """US-34.9 — the SECOND structural disqualifier, which F-9 did not name.

    `_validate_verified_benchmark_slice` requires `ordered_dates ==
    sorted(ordered_dates)`. FMP returns rows newest-first, so vendor order alone
    kept the verified rung unreachable even after the endpoint was fixed — and it
    failed *silently*: the basis simply fell to `unverified_adjusted_proxy`,
    which publishes nothing at all. That is strictly worse than the
    `price_return_only` figure it replaced, and no test would have caught it.

    The client now normalises to ascending order; this pins that the committed
    capture really is ordered, per window.
    """
    payload = json.loads(GOLDEN_MARKET_DATA_PATH.read_text(encoding="utf-8"))
    windows = [entry for entry in payload["series"] if entry.get("symbol") == "SPY"]
    assert windows, "the frozen capture has no SPY series"

    for entry in windows:
        dates = [row["date"] for row in (entry.get("rows") or [])]
        assert dates == sorted(dates), f"SPY window {entry.get('from')}..{entry.get('to')} is not ascending"
        assert len(set(dates)) == len(dates), "duplicate dates in a SPY window"


def test_the_basis_the_engine_derives_matches_the_committed_capture() -> None:
    """US-34.9 AC7 — code and data are pinned to each other, not separately.

    Asserting the row contents alone would still allow the classifier to drift
    away from them. This asserts the derived basis in the same test, so the pair
    can never disagree silently the way F-9's validator and capture did.

    Note the ladder: complete `adjClose` gets a slice to `verified_adjusted_close`
    / `unverified_adjusted_proxy` on its own. Reaching `verified_total_return`
    additionally needs the allowlisted symbol, the direct single-vendor fetch and
    the pinned endpoint -- checked in `test_analytics.py`, not here.
    """
    rows = _spy_rows()

    assert detect_history_return_basis(rows) == "verified_adjusted_close"
    assert classify_history_return_basis_contract(rows) == "unverified_adjusted_proxy"


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

    assert with_adjusted, "no series carries adjClose"
    # The UCITS/LSE listings the fallback resolves carry it, as they always did.
    assert {"SXRV", "VUAA", "IUIT", "SGLD"} <= with_adjusted
    # SPY now carries it too -- from FMP's dividend-adjusted endpoint, which
    # US-34.9 added. This is the line that would have failed before that work.
    assert "SPY" in with_adjusted
    # But ONLY the benchmark: the ordinary US positions FMP serves still come
    # from the light endpoint and still carry none, because valuing holdings at
    # adjusted prices would put market values at odds with the broker.
    assert not with_adjusted & {"AAPL", "AMZN", "ASML", "CRM"}
