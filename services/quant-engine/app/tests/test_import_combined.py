"""Combined-portfolio regression tests (US-46.1 merge, US-46.3 admission roll-up).

Pins the engine side of two import fixes:

- F3 / US-46.1: adding a statement from the SAME account replaces, never doubles;
  distinct accounts still sum; a combine that cannot be classified is refused
  (HTTP 400) and publishes nothing.
- F2 / US-46.3: a combined portfolio's admission label is the weakest of every
  input statement's own admission and the recompute on the combined snapshot
  (decision D-3), with each constituent's evidence kept alongside.

Expected values come from the statement truths (`statement_truths.py`), the
research brief (`02-quant.md` F2/F3) and worked synthetic examples - never
recomputed the way the engine does. The five committed-fixture pairs all agree
under recompute-only AND weakest-of-both, so they cannot tell the rules apart;
`test_offsetting_deltas_*` is the load-bearing test for the rule itself.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.schemas.import_bootstrap import ImportAdmissionSummaryV1
from app.schemas.imports import ImportedPortfolioSnapshot
from app.services.import_admission import build_combined_admission_summary, build_import_admission_summary
from app.services.import_engine import (
    build_combined_import_bootstrap,
    build_import_bootstrap,
    build_import_bootstrap_from_snapshot,
)
from app.services.statement_importer import combine_imported_snapshots, import_statements
from app.tests._statement_fixtures import ESPP_PATH, FREEDOM24_PATH, STATEMENT_2026_CSV_PATH as IB_PATH
from app.tests.fixtures import account_snapshot, position
from app.tests.statement_truths import (
    IB_ACCOUNT_ID,
    IB_PINNED_POSITIONS,
    IB_POSITION_COUNT,
    IB_RAW_MIXED_CURRENCY_SUM,
    IB_TOTALS_2DP,
)

ANALYZE_COMBINED = "/portfolios/import/analyze-combined"
ROLLUP_RULE = "weakest_of_constituents_and_combined_snapshot"

# Each committed statement's OWN admission (02-quant.md § F2: IB2026 and FF2026
# degrade on unavailable numeric checks; ESPP2026 passes everything).
SINGLE_LABELS = {
    "ib": ("degraded", "degraded"),
    "ff": ("degraded", "degraded"),
    "espp": ("admitted", "verified"),
}


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def _load(path) -> ImportedPortfolioSnapshot:
    return import_statements([str(path)])


@pytest.fixture(scope="module")
def ib() -> ImportedPortfolioSnapshot:
    return _load(IB_PATH)


@pytest.fixture(scope="module")
def ib_again() -> ImportedPortfolioSnapshot:
    """A second import of the same file - what re-adding the refreshed statement does."""
    return _load(IB_PATH)


@pytest.fixture(scope="module")
def espp() -> ImportedPortfolioSnapshot:
    return _load(ESPP_PATH)


@pytest.fixture(scope="module")
def ff() -> ImportedPortfolioSnapshot:
    return _load(FREEDOM24_PATH)


def _snap(**kwargs) -> ImportedPortfolioSnapshot:
    return ImportedPortfolioSnapshot.model_validate(account_snapshot(**kwargs))


def _json(snapshot: ImportedPortfolioSnapshot) -> dict:
    return snapshot.model_dump(mode="json")


def _post_combined(client: TestClient, snapshots, **extra):
    return client.post(ANALYZE_COMBINED, json={"snapshots": [_json(s) for s in snapshots], **extra})


def _by_key(snapshot: ImportedPortfolioSnapshot) -> dict[tuple[str, str], tuple[float, float]]:
    return {(p.symbol, p.currency): (p.quantity, p.market_value) for p in snapshot.positions}


def _cash(snapshot: ImportedPortfolioSnapshot) -> dict[str, float]:
    return {b.currency: round(b.ending_cash or 0.0, 2) for b in snapshot.cash_balances}


def _labels(summary: ImportAdmissionSummaryV1) -> list[tuple[str, str, str]]:
    assert summary.rollup is not None
    return [(c.origin, c.decision, c.trust_level) for c in summary.rollup.constituents]


# ── US-46.1: same account replaces, distinct accounts sum ───────────────────


def test_combine_of_a_statement_with_itself_is_idempotent_on_positions_and_cash(ib, ib_again) -> None:
    """AC 1-4: combine(S, S) = S for positions and cash (the invariant E3 states)."""
    combined = combine_imported_snapshots([ib, ib_again])

    assert _by_key(combined) == _by_key(ib)
    assert _cash(combined) == _cash(ib)
    assert len(combined.positions) == IB_POSITION_COUNT
    assert round(sum(p.market_value for p in combined.positions), 2) == IB_RAW_MIXED_CURRENCY_SUM
    assert (combined.statement.account_id) == IB_ACCOUNT_ID
    # the falsifier the desktop overlay failed: VUAA 160 / USD cash doubled
    vuaa = IB_PINNED_POSITIONS["VUAA"]
    assert _by_key(combined)[("VUAA", "USD")] == (vuaa["quantity"], vuaa["market_value"])


def test_flat_combine_of_ib_espp_ib_leaves_ib_unchanged(ib, ib_again, espp) -> None:
    """A distinct account in between does not make the second IB add up: flat combine
    of [IB, ESPP, IB] has exactly the IB holdings of [IB, ESPP]."""
    with_repeat = combine_imported_snapshots([ib, espp, ib_again])
    without_repeat = combine_imported_snapshots([ib, espp])

    assert _by_key(with_repeat) == _by_key(without_repeat)
    assert _cash(with_repeat) == _cash(without_repeat)
    ib_keys = set(_by_key(ib))
    assert {k: v for k, v in _by_key(with_repeat).items() if k in ib_keys} == _by_key(ib)
    assert len(with_repeat.positions) == IB_POSITION_COUNT + len(espp.positions)


def test_distinct_accounts_still_sum_a_shared_symbol_and_cash() -> None:
    """AC 5 (US-14.1 preserved): the same symbol held in two DIFFERENT accounts sums."""
    first = _snap(account_id="U1", positions=[position("AAA", 200.0, quantity=2.0)], cash=10.0)
    second = _snap(account_id="U2", positions=[position("AAA", 300.0, quantity=3.0)], cash=5.0)

    combined = combine_imported_snapshots([first, second])

    assert _by_key(combined) == {("AAA", "USD"): (5.0, 500.0)}
    assert _cash(combined) == {"USD": 15.0}


def test_same_account_later_statement_replaces_rather_than_sums() -> None:
    older = _snap(account_id="U1", positions=[position("AAA", 200.0, quantity=2.0)], cash=10.0, as_of_date="2026-02-28")
    newer = _snap(account_id="U1", positions=[position("AAA", 300.0, quantity=3.0)], cash=5.0, as_of_date="2026-03-31")

    combined = combine_imported_snapshots([older, newer])

    assert _by_key(combined) == {("AAA", "USD"): (3.0, 300.0)}
    assert _cash(combined) == {"USD": 5.0}


def test_chained_combine_of_a_combined_input_with_a_shared_account_is_refused(ib, ib_again, espp) -> None:
    """Design C5: (IB+ESPP) combined with IB again used to sum IB (VUAA 160). It now fails closed."""
    already_combined = combine_imported_snapshots([ib, espp])

    for ordering in ([already_combined, ib_again], [ib_again, already_combined]):
        with pytest.raises(ValueError, match="already-combined portfolio shares account"):
            combine_imported_snapshots(ordering)


def test_combined_input_with_no_shared_account_is_still_accepted(ib, espp, ff) -> None:
    """The chained-input guard is about a SHARED account, not about combined inputs as such."""
    already_combined = combine_imported_snapshots([ib, espp])

    combined = combine_imported_snapshots([already_combined, ff])

    assert len(combined.positions) == len(ib.positions) + len(espp.positions) + len(ff.positions)


def test_stored_snapshot_with_repeated_account_part_is_refused_even_alone(ib, espp) -> None:
    """A legacy chained merge leaves 'A + B + B' in account_id; its positions are not trustworthy."""
    combined = combine_imported_snapshots([ib, espp])
    doubled = combined.model_copy(
        update={"statement": combined.statement.model_copy(update={"account_id": f"{combined.statement.account_id} + {IB_ACCOUNT_ID}"})}
    )

    with pytest.raises(ValueError, match="repeats an account identifier"):
        combine_imported_snapshots([doubled])


def test_combine_refuses_a_missing_account_identity_and_a_base_currency_mismatch() -> None:
    known = _snap(account_id="U1", positions=[position("AAA", 200.0)])
    no_identity = _snap(account_id=None, positions=[position("BBB", 200.0)])
    euro = _snap(account_id="U2", positions=[position("CCC", 200.0, currency="EUR")], base_currency="EUR")

    with pytest.raises(ValueError, match="account"):
        combine_imported_snapshots([known, no_identity])
    with pytest.raises(ValueError, match="different base currencies"):
        combine_imported_snapshots([known, euro])


# ── analyze-combined route: the one merge source both surfaces consume ─────


def test_analyze_combined_ib_twice_matches_ib_alone_on_real_statement(client, ib, ib_again) -> None:
    """US-46.1 AC 1-4 on the route, real IB2026: 18 positions, raw MV, VUAA 80, USD cash 146.07."""
    response = _post_combined(client, [ib, ib_again])

    assert response.status_code == 200
    body = response.json()
    positions = body["snapshot"]["positions"]
    assert len(positions) == IB_POSITION_COUNT
    assert round(sum(p["market_value"] for p in positions), 2) == IB_RAW_MIXED_CURRENCY_SUM
    vuaa = next(p for p in positions if p["symbol"] == "VUAA")
    assert (vuaa["quantity"], vuaa["market_value"], vuaa["currency"]) == (
        IB_PINNED_POSITIONS["VUAA"]["quantity"],
        IB_PINNED_POSITIONS["VUAA"]["market_value"],
        "USD",
    )
    cash = {b["currency"]: round(b["ending_cash"], 2) for b in body["snapshot"]["cash_balances"]}
    assert cash["USD"] == IB_TOTALS_2DP["cash_total"]
    assert cash.get("EUR", 0) == 0 and cash.get("GBP", 0) == 0
    # base-currency value (statement rates) is the statement's own stock total
    assert round(body["overview"]["total_market_value"], 2) == IB_TOTALS_2DP["stock_total"]
    assert body["constituent_snapshots"] == []


def test_analyze_combined_carries_the_snapshot_the_merge_produced(client, ib, espp) -> None:
    """AC 6: Exposure and Dashboard consume one snapshot - the response echoes the flat combine."""
    response = _post_combined(client, [ib, espp])

    assert response.status_code == 200
    expected = combine_imported_snapshots([ib, espp])
    assert response.json()["snapshot"]["positions"] == _json(expected)["positions"]
    assert response.json()["snapshot"]["statement"]["account_id"] == expected.statement.account_id


def test_analyze_combined_chained_input_is_a_400_with_the_guard_message(client, ib, ib_again, espp) -> None:
    already_combined = combine_imported_snapshots([ib, espp])

    response = _post_combined(client, [already_combined, ib_again])

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Cannot combine: an already-combined portfolio shares account")


def test_analyze_combined_legacy_doubled_account_is_a_400_even_as_the_only_input(client, ib, espp) -> None:
    combined = combine_imported_snapshots([ib, espp])
    doubled = combined.model_copy(
        update={"statement": combined.statement.model_copy(update={"account_id": f"{combined.statement.account_id} + {IB_ACCOUNT_ID}"})}
    )

    response = _post_combined(client, [doubled])

    assert response.status_code == 400
    assert response.json()["detail"].startswith("Cannot combine: the saved combined statement")


def test_analyze_combined_stored_combined_snapshot_alone_analyses_without_a_rollup(client, ib, espp) -> None:
    combined = combine_imported_snapshots([ib, espp])

    response = _post_combined(client, [combined])

    assert response.status_code == 200
    assert response.json()["admission_summary"]["rollup"] is None


@pytest.mark.parametrize(
    "second, message",
    [
        (lambda: _snap(account_id=None, positions=[position("BBB", 200.0)]), "account"),
        (lambda: _snap(account_id="U2", positions=[position("CCC", 200.0, currency="EUR")], base_currency="EUR"), "different base currencies"),
    ],
    ids=["missing-account-identity", "base-currency-mismatch"],
)
def test_refused_combine_is_a_400_with_no_combined_admission_or_portfolio(client, second, message) -> None:
    """US-46.1 AC 7 / US-46.3 AC 11: a refused combine publishes nothing - just a detail string."""
    first = _snap(account_id="U1", positions=[position("AAA", 200.0)])

    response = _post_combined(client, [first, second()])

    assert response.status_code == 400
    body = response.json()
    assert set(body) == {"detail"}  # closed error body: no summary, no snapshot, no overview
    assert message in body["detail"]


def test_refused_combine_raises_before_any_admission_is_built() -> None:
    first = _snap(account_id="U1", positions=[position("AAA", 200.0)])
    no_identity = _snap(account_id=None, positions=[position("BBB", 200.0)])

    with pytest.raises(ValueError, match="account"):
        build_combined_import_bootstrap([first, no_identity], "SPY", {})


def test_analyze_combined_requires_at_least_one_snapshot(client) -> None:
    assert client.post(ANALYZE_COMBINED, json={"snapshots": []}).status_code == 422


# ── US-46.3: admission label of a combined portfolio ───────────────────────

PAIRS = [
    ("ib", "ib"),  # AC 3
    ("ib", "espp"),  # AC 1 - was admitted/verified (last file only)
    ("espp", "ib"),  # AC 4 - reverse order
    ("ib", "ff"),
    ("ff", "espp"),  # AC 2 - was admitted/verified (last file only)
]


@pytest.mark.parametrize("first, second", PAIRS, ids=[f"{a}+{b}" for a, b in PAIRS])
def test_fixture_pairs_are_degraded_and_keep_each_constituent_label(first, second, request) -> None:
    # a statement paired with itself is two separate imports of the same file
    inputs = [request.getfixturevalue(first), request.getfixturevalue("ib_again" if first == second else second)]
    combined = combine_imported_snapshots(inputs)

    summary = build_combined_admission_summary(inputs, combined)

    assert (summary.decision, summary.trust_level) == ("degraded", "degraded")
    assert _labels(summary) == [("statement", *SINGLE_LABELS[first]), ("statement", *SINGLE_LABELS[second])]
    assert summary.rollup is not None and summary.rollup.rule == ROLLUP_RULE


def test_last_file_only_label_is_gone_for_ib_plus_espp(ib, espp) -> None:
    """The F2 defect: the added file's own label (ESPP admitted/verified) is not the answer."""
    summary = build_combined_admission_summary([ib, espp], combine_imported_snapshots([ib, espp]))

    assert (summary.decision, summary.trust_level) != tuple(SINGLE_LABELS["espp"])


def test_single_statements_keep_their_own_label_and_have_no_rollup(ib, espp, ff) -> None:
    """AC 10 / design C3: a single input is the single-statement case, rollup None."""
    for name, snapshot in (("ib", ib), ("espp", espp), ("ff", ff)):
        summary = build_combined_admission_summary([snapshot], snapshot)

        assert (summary.decision, summary.trust_level) == SINGLE_LABELS[name]
        assert summary.rollup is None


def test_offsetting_deltas_across_two_accounts_cannot_lift_the_combined_label() -> None:
    """AC 6, the load-bearing test of US-46.3.

    Account U1 parses 200 of positions against a stated stock total of 190
    (delta +10); account U2 parses 300 against a stated 310 (delta -10). Each
    statement FAILS the position-value check on its own (withheld). Summed, the
    combined snapshot parses 500 against a stated 500 and PASSES every check.

    - recompute-only would label the portfolio admitted/verified: ABOVE both
      of its statements (the overstatement F2 audited).
    - the D-3 rule (weakest of all) must label it withheld.
    """
    first = _snap(account_id="U1", positions=[position("AAA", 200.0)], stock_total=190.0)
    second = _snap(account_id="U2", positions=[position("BBB", 300.0)], stock_total=310.0)
    combined = combine_imported_snapshots([first, second])

    # premises: each statement fails alone, the combined recompute passes
    assert build_import_admission_summary(first).decision == "withheld"
    assert build_import_admission_summary(second).decision == "withheld"
    recompute_only = build_import_admission_summary(combined)
    assert (recompute_only.decision, recompute_only.trust_level) == ("admitted", "verified")

    summary = build_combined_admission_summary([first, second], combined)

    assert (summary.decision, summary.trust_level) == ("withheld", "withheld")
    assert summary.rollup is not None
    # the roll-up still discloses what the recompute alone said
    assert (summary.rollup.combined_snapshot_decision, summary.rollup.combined_snapshot_trust_level) == ("admitted", "verified")
    assert _labels(summary) == [("statement", "withheld", "withheld"), ("statement", "withheld", "withheld")]


def test_offsetting_deltas_hold_through_the_route_and_in_either_order(client) -> None:
    first = _snap(account_id="U1", positions=[position("AAA", 200.0)], stock_total=190.0)
    second = _snap(account_id="U2", positions=[position("BBB", 300.0)], stock_total=310.0)

    for ordering in ([first, second], [second, first]):
        summary = _post_combined(client, ordering).json()["admission_summary"]

        assert (summary["decision"], summary["trust_level"]) == ("withheld", "withheld")
        assert summary["rollup"]["combined_snapshot_decision"] == "admitted"


def test_two_clean_statements_stay_admitted_verified_the_rollup_raises_no_rung() -> None:
    """AC 9 mirror: nothing the roll-up does lowers a clean pair, nothing raises a rung."""
    first = _snap(account_id="U1", positions=[position("AAA", 200.0)])
    second = _snap(account_id="U2", positions=[position("BBB", 300.0)])

    summary = build_combined_admission_summary([first, second], combine_imported_snapshots([first, second]))

    assert (summary.decision, summary.trust_level) == ("admitted", "verified")
    assert summary.rollup is not None


@pytest.mark.parametrize("order", ["weak-first", "weak-last"])
def test_superseded_statement_still_contributes_its_own_label(order) -> None:
    """AC 7: an earlier same-account statement is replaced in positions but not in the label."""
    earlier_weak = _snap(account_id="U1", positions=[position("AAA", 200.0)], with_totals=False, as_of_date="2026-02-28")
    later_clean = _snap(account_id="U1", positions=[position("AAA", 250.0)], as_of_date="2026-03-31")
    inputs = [earlier_weak, later_clean] if order == "weak-first" else [later_clean, earlier_weak]
    combined = combine_imported_snapshots(inputs)

    # premises: the later statement supersedes, and on its own the combined recompute is clean
    assert _by_key(combined) == {("AAA", "USD"): (10.0, 250.0)}
    assert build_import_admission_summary(combined).decision == "admitted"

    summary = build_combined_admission_summary(inputs, combined)

    assert (summary.decision, summary.trust_level) == ("degraded", "degraded")
    assert sorted(label[1:] for label in _labels(summary)) == [("admitted", "verified"), ("degraded", "degraded")]


def test_constituents_follow_input_order_and_keep_their_checks(ib, espp) -> None:
    """AC 8: each input's own label AND checks stay visible next to the combined label."""
    summary = build_combined_admission_summary([ib, espp], combine_imported_snapshots([ib, espp]))

    assert summary.rollup is not None
    first, second = summary.rollup.constituents
    assert first.checks and second.checks
    assert {c.check_id: c.status for c in first.checks} == {c.check_id: c.status for c in build_import_admission_summary(ib).checks}
    assert any(name.endswith(IB_PATH.name) for name in first.source_names)
    assert any(name.endswith(ESPP_PATH.name) for name in second.source_names)
    # top-level checks stay the combined snapshot's own, so existing consumers keep their meaning
    combined_checks = {c.check_id: c.status for c in build_import_admission_summary(combine_imported_snapshots([ib, espp])).checks}
    assert {c.check_id: c.status for c in summary.checks} == combined_checks


def test_carried_admission_from_a_saved_node_lowers_the_label(ib, espp) -> None:
    """D-11: persisted per-file admissions on the lineage enter the roll-up as 'carried' evidence."""
    carried_ib = build_import_admission_summary(ib)

    summary = build_combined_admission_summary([espp], espp, [carried_ib])

    assert (summary.decision, summary.trust_level) == ("degraded", "degraded")
    assert _labels(summary) == [("statement", "admitted", "verified"), ("carried", "degraded", "degraded")]
    carried = summary.rollup.constituents[1]
    assert carried.statement_ids == carried_ib.provenance.statement_ids
    assert carried.source_names == carried_ib.provenance.source_names


def test_withheld_and_unavailable_stay_distinct_rungs_in_the_rollup(espp) -> None:
    """Trust ladder verified > degraded > withheld > unavailable: decision and trust are
    ranked independently, and 'unavailable' is never collapsed into 'withheld'."""
    base = build_import_admission_summary(espp)
    unavailable_trust = base.model_copy(update={"decision": "degraded", "trust_level": "unavailable"})
    withheld_both = base.model_copy(update={"decision": "withheld", "trust_level": "withheld"})

    lowered = build_combined_admission_summary([espp], espp, [unavailable_trust])
    assert (lowered.decision, lowered.trust_level) == ("degraded", "unavailable")

    heaviest = build_combined_admission_summary([espp], espp, [unavailable_trust, withheld_both])
    assert (heaviest.decision, heaviest.trust_level) == ("withheld", "unavailable")


# ── path independence and the single-input contract ────────────────────────


def _identity(summary: ImportAdmissionSummaryV1) -> tuple:
    assert summary.rollup is not None
    return (
        summary.decision,
        summary.trust_level,
        [(c.origin, c.statement_ids, c.decision, c.trust_level) for c in summary.rollup.constituents],
    )


def test_multi_file_upload_and_analyze_combined_give_the_same_label_and_constituents(client, ib, espp) -> None:
    """AC 5: the same statements label identically whichever button built them."""
    by_paths = build_import_bootstrap([str(IB_PATH), str(ESPP_PATH)], "SPY", {})
    by_snapshots = build_combined_import_bootstrap([ib, espp], "SPY", {})
    via_route = _post_combined(client, [ib, espp]).json()
    via_paths_route = client.post(
        "/portfolios/import/interactive-brokers/analyze",
        json={"statement_paths": [str(IB_PATH), str(ESPP_PATH)], "benchmark_symbol": "SPY", "symbol_overrides": {}},
    ).json()

    expected = _identity(by_paths.admission_summary)
    assert _identity(by_snapshots.admission_summary) == expected
    assert _identity(ImportAdmissionSummaryV1.model_validate(via_route["admission_summary"])) == expected
    assert _identity(ImportAdmissionSummaryV1.model_validate(via_paths_route["admission_summary"])) == expected
    assert (by_paths.admission_summary.decision, by_paths.admission_summary.trust_level) == ("degraded", "degraded")


def test_multi_file_path_returns_constituents_but_analyze_combined_does_not(client, ib, espp) -> None:
    by_paths = build_import_bootstrap([str(IB_PATH), str(ESPP_PATH)], "SPY", {})
    single = build_import_bootstrap([str(IB_PATH)], "SPY", {})

    assert [s.statement.importer for s in by_paths.constituent_snapshots] == ["interactive_brokers", "espp"]
    assert single.constituent_snapshots == []
    assert _post_combined(client, [ib, espp]).json()["constituent_snapshots"] == []


def test_single_input_seam_equals_the_single_snapshot_bootstrap(ib) -> None:
    """Design: one input with no carried evidence is byte-for-byte today's bootstrap."""
    seam = build_combined_import_bootstrap([ib], "SPY", {}).model_dump(mode="json")
    direct = build_import_bootstrap_from_snapshot(ib, "SPY", {}).model_dump(mode="json")
    for payload in (seam, direct):
        payload["admission_summary"]["provenance"].pop("generated_at")

    assert seam == direct
    assert seam["admission_summary"]["rollup"] is None
    assert (seam["admission_summary"]["decision"], seam["admission_summary"]["trust_level"]) == SINGLE_LABELS["ib"]


def test_rollup_rule_name_is_the_published_contract_string(client, ib, espp) -> None:
    """Closed literal in the contract (import-admission-fields.md): pin it once."""
    rollup = _post_combined(client, [ib, espp]).json()["admission_summary"]["rollup"]

    assert rollup["rule"] == ROLLUP_RULE
    assert [c["origin"] for c in rollup["constituents"]] == ["statement", "statement"]


def test_carried_admissions_travel_through_the_route(client, espp, ib) -> None:
    carried = build_import_admission_summary(ib).model_dump(mode="json")

    body = _post_combined(client, [espp], carried_admissions=[carried]).json()["admission_summary"]

    assert (body["decision"], body["trust_level"]) == ("degraded", "degraded")
    assert [c["origin"] for c in body["rollup"]["constituents"]] == ["statement", "carried"]
