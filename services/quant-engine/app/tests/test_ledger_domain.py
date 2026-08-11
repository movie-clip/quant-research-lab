"""US-24.5: the broker section-role registry in `domain/ledger.py`.

The domain used to classify a ledger entry by matching `source_section` against
hardcoded broker display strings drawn from IBKR statements. Any broker whose
vocabulary differed fell through to `cash_movement_classification == "unknown"`
silently — which was live on two of three supported brokers (F-1 Freedom24
"Transactions", F-2 ESPP "Employee Stock Purchase Summary").

The registry replaces the inline matching. These tests pin the two fixes, the
IBKR no-change guarantee, that `unknown` stays reachable for genuinely
unrecognised sections, and — the actual deliverable — that no importer can add
an unregistered section label without failing the suite.
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from app.domain.ledger import registered_section_labels, section_roles, snapshot_to_ledger
from app.tests.fixtures import imported_snapshot, position
from app.schemas.imports import ImportedPortfolioSnapshot


def _entry(entry_type: str, source_section: str, **overrides) -> dict:
    entry = {
        "entry_type": entry_type,
        "trade_date": "2026-03-02",
        "net_amount": -1000.0,
        "currency": "USD",
        "source_section": source_section,
    }
    if entry_type in {"BUY", "SELL"}:
        entry.update({"symbol": "AAA", "quantity": 10.0, "price": 100.0})
    entry.update(overrides)
    return entry


def _classify(entry_type: str, source_section: str) -> tuple[str, list[str]]:
    snapshot = ImportedPortfolioSnapshot.model_validate(
        imported_snapshot(
            positions=[position("AAA")],
            ledger_entries=[_entry(entry_type, source_section)],
            cash_balances=[],
        )
    )
    record = snapshot_to_ledger(snapshot)[0]
    return record.cash_movement_classification, record.broker_evidence


class TestSectionRoleRegistry:
    def test_f1_freedom24_transactions_trade_is_classified(self) -> None:
        """F-1: Freedom24 calls its trade section "Transactions"; every BUY and
        SELL on FF2026 classified as `unknown` before this registry."""
        classification, evidence = _classify("BUY", "Transactions")

        assert classification == "internal_trading_flow"
        assert "broker_trade_ledger_line" in evidence

    def test_f2_espp_payroll_deposit_is_an_external_capital_flow(self) -> None:
        """F-2, the more serious half: `external_capital_flow` is how the proof
        system recognises investor contributions, so an unclassified ESPP
        payroll deposit made the contribution invisible to it."""
        classification, evidence = _classify("DEPOSIT", "Employee Stock Purchase Summary")

        assert classification == "external_capital_flow"
        assert "broker_transfer_section_line" in evidence

    def test_f2_espp_purchase_is_an_internal_trading_flow(self) -> None:
        """The same ESPP section carries the BUY too — one label, two roles."""
        classification, evidence = _classify("BUY", "Employee Stock Purchase Summary")

        assert classification == "internal_trading_flow"
        assert "broker_trade_ledger_line" in evidence

    @pytest.mark.parametrize(
        ("entry_type", "source_section", "expected"),
        [
            ("BUY", "Trades", "internal_trading_flow"),
            ("SELL", "Trades", "internal_trading_flow"),
            ("DEPOSIT", "Deposits & Withdrawals", "external_capital_flow"),
            ("WITHDRAWAL", "Deposits & Withdrawals", "external_capital_flow"),
            ("DIVIDEND", "Dividends", "broker_explicit_dividend"),
            ("DIVIDEND", "Income Summary", "broker_explicit_dividend"),
            ("DIVIDEND", "Cash deposits/ withdrawals", "broker_explicit_dividend"),
            ("INTEREST", "Interest", "broker_explicit_interest"),
            ("FEE", "Fees", "broker_explicit_fee"),
            ("FEE", "Other Fees", "broker_explicit_fee"),
            ("FEE", "Commissions", "broker_explicit_fee"),
            ("WITHHOLDING_TAX", "Withholding Tax", "broker_explicit_tax"),
            ("WITHHOLDING_TAX", "Account Summary", "broker_explicit_tax"),
            ("WITHHOLDING_TAX", "Cash deposits/ withdrawals", "broker_explicit_tax"),
        ],
    )
    def test_every_pre_existing_pairing_is_unchanged(
        self, entry_type: str, source_section: str, expected: str
    ) -> None:
        """AC4 — the registry reproduces the inline vocabulary exactly. This is
        the guard against the refactor quietly re-classifying IBKR."""
        classification, _evidence = _classify(entry_type, source_section)
        assert classification == expected

    def test_an_unregistered_section_stays_unknown(self) -> None:
        """AC6 — `unknown` must remain reachable. Defaulting an unrecognised
        label to a role would fabricate provenance the statement never gave."""
        classification, evidence = _classify("BUY", "Some Broker Section We Have Never Seen")

        assert classification == "unknown"
        assert not any(item.startswith("broker_") for item in evidence)
        assert section_roles("Some Broker Section We Have Never Seen") == frozenset()

    def test_roles_resolve_exactly_and_do_not_guess(self) -> None:
        """Lookup is exact: no case-folding or fuzzy matching, because a near
        miss on a broker label is precisely the failure this registry exists to
        make visible rather than absorb."""
        assert "trade" in section_roles("Trades")
        assert section_roles("trades") == frozenset()
        assert section_roles("Trades ") == frozenset()
        # A wrong-role pairing gets no evidence even for a registered label.
        classification, _ = _classify("DIVIDEND", "Trades")
        assert classification == "unknown"


def _importer_section_literals() -> dict[str, set[str]]:
    """Every `source_section="..."` literal each importer module emits.

    Parsed from the AST rather than grepped so a renamed keyword or a moved
    call site cannot make this guard silently pass on nothing.
    """
    importers_dir = pathlib.Path(__file__).resolve().parents[1] / "importers"
    found: dict[str, set[str]] = {}
    for path in sorted(importers_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        labels: set[str] = set()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for keyword in node.keywords:
                if keyword.arg == "source_section" and isinstance(keyword.value, ast.Constant):
                    if isinstance(keyword.value.value, str):
                        labels.add(keyword.value.value)
        if labels:
            found[path.name] = labels
    return found


def test_every_importer_section_label_is_registered() -> None:
    """AC7 — the actual deliverable.

    A broker label the domain does not know degrades output silently in
    production. This turns that into a failing test: adding an importer with a
    new section vocabulary fails here until the label is given a role.

    (Literals only. A label built at runtime — the IBKR PDF path passes its
    section heading through a variable — is covered by the fixture-level
    zero-`unknown` assertions in `test_importer.py`.)
    """
    registered = registered_section_labels()
    by_module = _importer_section_literals()
    assert by_module, "AST scan found no source_section literals — the guard would pass vacuously"

    unregistered = {
        module: sorted(labels - registered)
        for module, labels in by_module.items()
        if labels - registered
    }
    assert unregistered == {}, (
        "These importer section labels have no role in the domain registry, so every entry "
        f"carrying them classifies as 'unknown': {unregistered}. Add them to _SECTION_ROLES in "
        "app/domain/ledger.py (see US-24.5)."
    )


# ── US-24.7: named financial tolerances ─────────────────────────────────────


def test_statement_reconciliation_tolerance_is_named_and_pinned() -> None:
    """US-24.7 AC4 — the pass/fail threshold for a reconciliation check was an
    inline `0.25` with no name and no rationale. Value pinned: changing it
    changes which statements reconcile."""
    from app.analytics.reconciliation import build_reconciliation_summary  # noqa: F401
    from app.core.constants import STATEMENT_RECONCILIATION_TOLERANCE

    assert STATEMENT_RECONCILIATION_TOLERANCE == 0.25


def test_proof_terminal_match_tolerance_is_distinct_from_the_replay_tolerance() -> None:
    """US-24.7 AC5 — two related checks use tolerances 100x apart, which is
    deliberate: the proof path compares its own recomputation against the
    statement (a cent of disagreement means the recomputation is wrong), while
    the replay tolerance absorbs genuine valuation residuals across a window.
    Pinned so the two cannot silently converge."""
    from app.core.constants import (
        PORTFOLIO_PROOF_TERMINAL_MATCH_TOLERANCE,
        REPLAY_RECONCILIATION_TOLERANCE,
    )
    from app.services.portfolio_proof import _terminal_totals_match

    assert PORTFOLIO_PROOF_TERMINAL_MATCH_TOLERANCE == 0.01
    assert PORTFOLIO_PROOF_TERMINAL_MATCH_TOLERANCE < REPLAY_RECONCILIATION_TOLERANCE

    # The proof helper uses the constant as its default.
    assert _terminal_totals_match(100.00, 100.005) is True
    assert _terminal_totals_match(100.00, 100.02) is False
