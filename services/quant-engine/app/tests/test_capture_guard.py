"""The golden capture must refuse to overwrite itself with a degraded run (US-35.3).

Epic 35 F-3, from a real incident on 2026-08-19: `capture_golden_market_data`
overwrote a 73-series capture with a 21-series one and printed "Wrote … (21
series)". The fixture is the foundation of a network-free suite, it is captured
rarely and by hand, and recovery meant `git checkout` of a file that had already
been written.

The guard is a pure function over two payloads, so every case here is a dict
rather than a live capture and the suite stays network-free.
"""
from __future__ import annotations

from app.scripts.capture_guard import assess_capture_regression


def _payload(series: dict[str, int]) -> dict:
    """A capture payload with `rows` rows for each symbol."""
    return {
        "series": [
            {
                "symbol": symbol,
                "from": "2026-01-01",
                "to": "2026-12-31",
                "rows": [{"date": f"2026-01-{i % 28 + 1:02d}", "price": 1.0} for i in range(count)],
            }
            for symbol, count in series.items()
        ],
        "fetch_meta": {},
    }


HEALTHY = _payload({"SPY": 148, "AAPL": 148, "VUAA": 149, "SXRV": 150})


def test_a_capture_with_fewer_series_is_refused() -> None:
    """US-35.3 AC1 — the headline symptom: 73 series became 21."""
    degraded = _payload({"SPY": 148, "AAPL": 148})

    reasons = assess_capture_regression(degraded, HEALTHY)

    assert reasons, "a capture that lost half its symbols must be refused"
    assert any("Series count fell from 4 to 2" in r for r in reasons)
    # AC3: it has to name what went missing, or the operator is diffing 2MB of JSON.
    assert any("VUAA" in r and "SXRV" in r for r in reasons)


def test_a_capture_with_materially_fewer_rows_is_refused() -> None:
    """US-35.3 AC1 — same symbols, gutted contents.

    9,288 -> 2,771 in the real incident. Series count alone would not catch a
    run where every symbol survived but returned almost nothing.
    """
    degraded = _payload({"SPY": 20, "AAPL": 20, "VUAA": 20, "SXRV": 20})

    reasons = assess_capture_regression(degraded, HEALTHY)

    assert any("Total rows fell from 595 to 80" in r for r in reasons), reasons
    assert any("%" in r for r in reasons), "AC3: state the share lost"


def test_a_present_but_empty_benchmark_is_refused() -> None:
    """US-35.3 AC2 — the exact shape of the real incident, and the sharpest case.

    SPY was PRESENT in the degraded payload, with zero rows. A naive "is the
    benchmark in the capture?" check passes that. Every dashboard figure is
    measured against SPY, so an empty one is worse than a missing one: the
    payload looks structurally complete.
    """
    degraded = _payload({"SPY": 0, "AAPL": 148, "VUAA": 149, "SXRV": 150})

    reasons = assess_capture_regression(degraded, HEALTHY)

    assert any("benchmark SPY has no rows" in r for r in reasons), reasons


def test_the_refusal_names_the_before_and_after_numbers() -> None:
    """US-35.3 AC3 — a refusal that does not say what changed just blocks work."""
    degraded = _payload({"SPY": 0, "AAPL": 10})

    reasons = assess_capture_regression(degraded, HEALTHY)
    joined = " ".join(reasons)

    assert "4" in joined and "2" in joined, "series before/after"
    assert "595" in joined, "row count before"
    assert "SPY" in joined, "the emptied benchmark"


def test_a_symbol_that_went_empty_is_reported_even_when_the_benchmark_is_fine() -> None:
    """US-35.3 AC3 — the same failure one level down.

    This is how the 52 symbols lost in the real incident would have surfaced if
    the benchmark had happened to survive.
    """
    degraded = _payload({"SPY": 148, "AAPL": 0, "VUAA": 0, "SXRV": 150})

    reasons = assess_capture_regression(degraded, HEALTHY)

    assert any("present but empty" in r and "AAPL" in r and "VUAA" in r for r in reasons), reasons


def test_a_first_capture_has_no_baseline_and_is_allowed() -> None:
    """US-35.3 AC5 — failing closed here would make the fixture uncreatable."""
    assert assess_capture_regression(HEALTHY, None) == []


def test_the_real_2026_08_19_refresh_shape_passes() -> None:
    """US-35.3 AC6 — the guard must not fire on ordinary drift.

    That refresh went 9,288 -> 9,302 rows at an unchanged 73 series, because the
    European listings gained a real terminal-day quote. A guard that blocked a
    healthy re-capture would be worse than none: it would train the operator to
    reach for the override.
    """
    committed = _payload({"SPY": 148, "AAPL": 148, "VUAA": 149, "SXRV": 150})
    refreshed = _payload({"SPY": 148, "AAPL": 148, "VUAA": 150, "SXRV": 151})

    assert assess_capture_regression(refreshed, committed) == []


def test_a_small_shrink_within_tolerance_is_allowed() -> None:
    """US-35.3 AC6 — a couple of rows moving is not a degraded capture."""
    committed = _payload({"SPY": 148, "AAPL": 148})
    slightly_smaller = _payload({"SPY": 147, "AAPL": 147})

    assert assess_capture_regression(slightly_smaller, committed) == []
