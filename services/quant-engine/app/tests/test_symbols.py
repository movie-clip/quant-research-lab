"""Regression tests for `app.core.symbols` (US-39.1, T-39.1.6).

No test module for `DEFAULT_SYMBOL_RULES` / `SymbolResolver` existed before
this story. Covers the new SBIO `SymbolResolutionRule` (T-39.1.2) — that it
resolves only to the exchange-suffixed candidate, never the bare wrong-fund
ticker — plus a general collision-freedom regression over the whole rule
table, since a duplicate canonical/alias key would silently shadow an
earlier rule (`SymbolResolver.__init__`'s `rule_index` build, last-write-wins).
"""
from __future__ import annotations

from app.core.symbols import (
    DEFAULT_SYMBOL_RESOLVER,
    DEFAULT_SYMBOL_RULES,
    canonicalize_symbol,
    resolve_symbol_candidates,
)


def test_no_duplicate_canonical_or_alias_keys_across_default_symbol_rules() -> None:
    """Regression guard for T-39.1.2: confirms the new SBIO rule (and every
    other rule) contributes a canonical/alias key set disjoint from every
    other rule's. A collision would silently shadow one rule's candidates
    with another's in `SymbolResolver.rule_index`, last rule in
    `DEFAULT_SYMBOL_RULES` order winning with no error raised."""
    seen: dict[str, str] = {}
    for rule in DEFAULT_SYMBOL_RULES:
        for key in rule.all_keys():
            normalized = key.strip().upper()
            assert normalized not in seen, (
                f"key {normalized!r} claimed by both {seen.get(normalized)!r} "
                f"and {rule.canonical_symbol!r}"
            )
            seen[normalized] = rule.canonical_symbol


def test_default_symbol_resolver_rule_index_has_no_collisions() -> None:
    """Same guard, exercised against the actual built `rule_index` (not just
    the raw tuple) — confirms the index has exactly as many entries as the
    sum of each rule's own key count, i.e. nothing was silently overwritten
    during `SymbolResolver.__init__`."""
    expected_key_count = sum(len(rule.all_keys()) for rule in DEFAULT_SYMBOL_RULES)
    assert len(DEFAULT_SYMBOL_RESOLVER.rule_index) == expected_key_count


# ── SBIO: deliberately no bare-ticker candidate (T-39.1.2, AC3/AC4) ─────────


def test_sbio_quote_candidates_resolve_only_to_the_exchange_suffixed_symbol() -> None:
    """SBIO.L is the statement's actual security; bare "SBIO" on FMP is a
    DIFFERENT, wrong fund (confirmed live) — the rule must never surface it
    as a quote candidate."""
    candidates = resolve_symbol_candidates("SBIO", kind="quote")

    assert candidates == ["SBIO.L"]
    assert "SBIO" not in candidates


def test_sbio_history_and_holdings_candidates_also_exclude_the_bare_ticker() -> None:
    assert resolve_symbol_candidates("SBIO", kind="history") == ["SBIO.L"]
    assert resolve_symbol_candidates("SBIO", kind="holdings") == ["SBIO.L"]


def test_sbio_has_no_dedicated_proxy_candidate() -> None:
    """The story deliberately omits a US-listed proxy for SBIO (unlike
    SEMI/CIBR/DFND) — none was requested and none is needed for the
    identity gate to fail closed. `SymbolResolver.resolve`'s own fallback
    (an empty `proxy_candidates` tuple falls back to the bare canonical
    symbol, same as every other rule with no dedicated proxy) still
    applies — this pins the absence of a *dedicated* proxy, not an empty
    candidate list."""
    assert resolve_symbol_candidates("SBIO", kind="proxy") == ["SBIO"]


def test_sbio_canonicalizes_to_itself() -> None:
    assert canonicalize_symbol("SBIO") == "SBIO"
    assert canonicalize_symbol("sbio.l") == "SBIO"
