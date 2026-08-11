"""US-26.1: currency exposure by weight (snapshot analytics).

The two formula corrections this story made to the research brief are pinned
here: the denominator is base-currency converted (Correction 1 — the brief's
raw sum is the F-7 defect US-30.5a fixed as Critical), and the brief's
"unclassified" bucket is unreachable because `ImportedPosition.currency` is
schema-required (Correction 2 — the real fabrication is upstream, in the
request-path snapshot builder; recorded as its own finding).
"""
from __future__ import annotations

import pytest

from app.analytics.currency_exposure import build_currency_exposure
from app.schemas.imports import ImportedPortfolioSnapshot
from app.tests.fixtures import imported_snapshot, position


def _snapshot(
    positions: list[dict],
    *,
    base_currency: str | None = "USD",
    fx_rates: dict[str, float] | None = None,
) -> ImportedPortfolioSnapshot:
    payload = imported_snapshot(positions=positions, ledger_entries=[], cash_balances=[])
    payload["statement"]["base_currency"] = base_currency
    if fx_rates is not None:
        payload["statement_totals"] = {"fx_rates": fx_rates}
    return ImportedPortfolioSnapshot.model_validate(payload)


def _weight_of(exposure, currency: str) -> float:
    return next(item.weight for item in exposure.weights if item.currency == currency)


def test_weights_use_the_converted_denominator_and_sum_to_one() -> None:
    exposure = build_currency_exposure(
        _snapshot(
            [
                position("USA", market_value=750.0, currency="USD"),
                position("EUE", market_value=250.0, currency="EUR"),
            ],
            fx_rates={"EURUSD": 1.20},
        )
    )

    # EUR converts to 300; denominator is 750 + 300 = 1,050 (NOT the raw 1,000).
    assert exposure.total_base_market_value == pytest.approx(1_050.0)
    assert _weight_of(exposure, "USD") == pytest.approx(750 / 1050, abs=1e-6)
    assert _weight_of(exposure, "EUR") == pytest.approx(300 / 1050, abs=1e-6)
    assert sum(item.weight for item in exposure.weights) == pytest.approx(1.0, abs=1e-6)


def test_correction_1_a_raw_sum_implementation_would_fail_here() -> None:
    """Correction 1 pin. Constructed so the raw and converted answers differ
    materially: a raw sum would report EUR at 50%, the truth is 54.5%.

    This is the F-7 defect (US-30.5a, Critical) — reintroducing it on the card
    whose entire subject is currency would be the worst possible place for it.
    """
    exposure = build_currency_exposure(
        _snapshot(
            [
                position("USA", market_value=1000.0, currency="USD"),
                position("EUE", market_value=1000.0, currency="EUR"),
            ],
            fx_rates={"EURUSD": 1.20},
        )
    )

    assert _weight_of(exposure, "EUR") == pytest.approx(1200 / 2200, abs=1e-6)
    # The raw-sum answer, explicitly rejected.
    assert _weight_of(exposure, "EUR") != pytest.approx(0.50, abs=1e-3)


def test_a_currency_less_position_cannot_reach_this_analytic() -> None:
    """Correction 2 — the brief's "unclassified" bucket is unreachable.

    `ImportedPosition.currency` is `str = Field(min_length=3, max_length=3)`,
    so a snapshot carrying a currency-less position cannot be constructed at
    all. Building a bucket for it would be dead code with a UI state that can
    never render.

    This pin is what makes the omission safe: if the schema is ever relaxed to
    allow a missing currency, this test fails and whoever relaxed it has to
    decide what the card should show — rather than the card silently
    attributing that value to some currency.
    """
    import pydantic

    with pytest.raises(pydantic.ValidationError):
        _snapshot([position("UNK", market_value=100.0, currency=None)])
    with pytest.raises(pydantic.ValidationError):
        _snapshot([position("UNK", market_value=100.0, currency="")])


def test_null_base_currency_withholds_the_non_base_total() -> None:
    """AC4 — no baseline to compare against. 0.0 would read as 'no currency
    risk', which is a claim the data does not support."""
    exposure = build_currency_exposure(
        _snapshot(
            [
                position("USA", market_value=800.0, currency="USD"),
                position("EUE", market_value=200.0, currency="EUR"),
            ],
            base_currency=None,
        )
    )

    assert exposure.non_base_weight is None
    assert exposure.base_currency is None
    # Per-currency weights are still computable and still render.
    assert {item.currency for item in exposure.weights} == {"USD", "EUR"}


def test_base_currency_only_portfolio_is_one_row_at_zero_non_base() -> None:
    """AC8 — correct in the trivial case, not only the interesting one."""
    exposure = build_currency_exposure(
        _snapshot([position("USA", market_value=1000.0, currency="USD")])
    )

    assert [item.currency for item in exposure.weights] == ["USD"]
    assert exposure.weights[0].weight == pytest.approx(1.0)
    assert exposure.non_base_weight == pytest.approx(0.0)


def test_an_unconvertible_currency_is_counted_and_disclosed_not_dropped() -> None:
    """AC5 — with no rate the value is carried in its own currency (US-27.8),
    never converted 1:1 and never dropped from the denominator. Its weight is
    the least trustworthy number on this card, so the disclosure matters."""
    exposure = build_currency_exposure(
        _snapshot(
            [
                position("USA", market_value=900.0, currency="USD"),
                position("JPX", market_value=100.0, currency="JPY"),
            ]
        )
    )

    assert "JPY" in exposure.fx_disclosure.fallback_currencies
    # Counted at its raw value — present, not silently removed.
    assert _weight_of(exposure, "JPY") == pytest.approx(0.10, abs=1e-6)
    assert exposure.total_base_market_value == pytest.approx(1_000.0)


def test_an_empty_portfolio_yields_no_rows_and_no_division() -> None:
    exposure = build_currency_exposure(_snapshot([]))

    assert exposure.weights == []
    assert exposure.non_base_weight is None
    assert exposure.total_base_market_value == 0.0


def test_rows_are_sorted_by_weight_descending() -> None:
    exposure = build_currency_exposure(
        _snapshot(
            [
                position("GBX", market_value=100.0, currency="GBP"),
                position("USA", market_value=500.0, currency="USD"),
                position("EUE", market_value=300.0, currency="EUR"),
            ],
            fx_rates={"EURUSD": 1.0, "GBPUSD": 1.0},
        )
    )

    assert [item.currency for item in exposure.weights] == ["USD", "EUR", "GBP"]
