"""US-43.3 — relocate the trust gate into app.services.trust_gate.

Two pins for the verbatim relocation:

- AC2: the one merged primitive, `has_any_symbol_price_history` — the two
  former engine copies were byte-identical, so the single surviving copy must
  behave exactly as both did (presence check over the history dict values).
- AC3: every relocated name is now imported by its consuming engine(s) by
  object identity from `app.services.trust_gate`, and every former private
  name (plus the `DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED`
  constant) is gone from the engine module namespace.

Structural template: `test_synthetic_history_coverage.py` (US-43.1 AC2 pin)
and `test_analytics.py` (US-43.2 identity block).
"""
from __future__ import annotations

from app.services import trust_gate


# ── AC2 — the one merged primitive ──────────────────────────────────────────


def test_has_any_symbol_price_history_is_a_presence_check_over_values() -> None:
    """AC2 — `has_any_symbol_price_history` merges two byte-identical engine
    copies of `return any(rows for rows in symbol_price_histories.values())`:
    empty dict and all-empty-lists are False; any non-empty row list is True."""
    assert trust_gate.has_any_symbol_price_history({}) is False
    assert trust_gate.has_any_symbol_price_history({"AAPL": []}) is False
    assert (
        trust_gate.has_any_symbol_price_history({"AAPL": [{"date": "2024-01-01"}]})
        is True
    )


# ── AC3 — the import-surface identity pin ───────────────────────────────────


def test_engines_bind_the_relocated_trust_gate_symbols_by_reference() -> None:
    """AC3 — the dashboard-history and diagnostics engines import every
    relocated helper from `app.services.trust_gate` by object identity (not a
    re-implementation), and the former private names — plus the runtime-flag
    constant — are gone from both engine module namespaces."""
    from app.services import dashboard_history_engine, diagnostics_engine

    dashboard_names = (
        "allow_dashboard_drawdown_outputs",
        "build_dashboard_investor_economics_partial_unlock",
        "build_dashboard_investor_economics_status",
        "build_dashboard_return_basis_contract",
        "build_dashboard_return_basis_evidence",
        "build_dashboard_section_trust",
        "classify_portfolio_return_basis",
        "has_any_symbol_price_history",
        "has_replay_outputs",
    )
    for name in dashboard_names:
        assert getattr(dashboard_history_engine, name) is getattr(trust_gate, name)

    diagnostics_names = (
        "allow_diagnostics_drawdown_outputs",
        "apply_diagnostics_drawdown_output_policy",
        "build_dashboard_investor_economics_partial_unlock",
        "build_diagnostics_drawdown_summary",
        "build_diagnostics_investor_economics_status",
        "build_diagnostics_section_trust",
        "has_any_symbol_price_history",
    )
    for name in diagnostics_names:
        assert getattr(diagnostics_engine, name) is getattr(trust_gate, name)

    dashboard_former_names = (
        "_build_dashboard_section_trust",
        "_classify_portfolio_return_basis",
        "_build_dashboard_return_basis_contract",
        "_build_dashboard_return_basis_evidence",
        "_allow_dashboard_drawdown_outputs",
        "_build_dashboard_investor_economics_status",
        "_build_dashboard_investor_economics_partial_unlock",
        "_has_any_symbol_price_history",
        "_has_replay_outputs",
        "DASHBOARD_EXACT_SLICE_EXCESS_RETURN_RUNTIME_ENABLED",
    )
    for name in dashboard_former_names:
        assert not hasattr(dashboard_history_engine, name)

    diagnostics_former_names = (
        "_resolve_section_trust",
        "_allow_diagnostics_drawdown_outputs",
        "_apply_diagnostics_drawdown_output_policy",
        "_build_diagnostics_drawdown_summary",
        "_build_diagnostics_investor_economics_status",
        "_has_any_symbol_price_history",
    )
    for name in diagnostics_former_names:
        assert not hasattr(diagnostics_engine, name)
