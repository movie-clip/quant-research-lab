from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolResolutionRule:
    canonical_symbol: str
    quote_candidates: tuple[str, ...] = ()
    history_candidates: tuple[str, ...] = ()
    holdings_candidates: tuple[str, ...] = ()
    proxy_candidates: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()

    def all_keys(self) -> tuple[str, ...]:
        return (self.canonical_symbol, *self.aliases)


DEFAULT_SYMBOL_RULES: tuple[SymbolResolutionRule, ...] = (
    SymbolResolutionRule(canonical_symbol="ES", quote_candidates=("SPY",), history_candidates=("SPY",), proxy_candidates=("SPY",)),
    SymbolResolutionRule(canonical_symbol="NQ", quote_candidates=("QQQ",), history_candidates=("QQQ",), proxy_candidates=("QQQ",)),
    SymbolResolutionRule(canonical_symbol="CL", quote_candidates=("USO",), history_candidates=("USO",), proxy_candidates=("USO",)),
    SymbolResolutionRule(canonical_symbol="GC", quote_candidates=("GLD",), history_candidates=("GLD",), proxy_candidates=("GLD",)),
    SymbolResolutionRule(canonical_symbol="BRK B", quote_candidates=("BRK-B", "BRK.B"), history_candidates=("BRK-B", "BRK.B"), aliases=("BRK-B", "BRK.B")),
    SymbolResolutionRule(canonical_symbol="VUAA", quote_candidates=("VUAA.L", "VUAA"), history_candidates=("VUAA.L", "VUAA"), holdings_candidates=("VUAA.L", "VUAA"), proxy_candidates=("SPY",), aliases=("VUAA.L",)),
    SymbolResolutionRule(canonical_symbol="SGLD", quote_candidates=("SGLD.L", "SGLD"), history_candidates=("SGLD.L", "SGLD"), holdings_candidates=("SGLD.L", "SGLD"), proxy_candidates=("GLD",), aliases=("SGLD.L",)),
    SymbolResolutionRule(canonical_symbol="ISLN", quote_candidates=("ISLN.L", "ISLN"), history_candidates=("ISLN.L", "ISLN"), holdings_candidates=("ISLN.L", "ISLN"), proxy_candidates=("SLV",), aliases=("ISLN.L",)),
    SymbolResolutionRule(canonical_symbol="ICOM", quote_candidates=("ICOM",), history_candidates=("ICOM",), holdings_candidates=("ICOM",), proxy_candidates=("DBC",)),
    SymbolResolutionRule(canonical_symbol="IUFS", quote_candidates=("IUFS",), history_candidates=("IUFS",), holdings_candidates=("IUFS",), proxy_candidates=("XLF",)),
    SymbolResolutionRule(canonical_symbol="IUHC", quote_candidates=("IUHC",), history_candidates=("IUHC",), holdings_candidates=("IUHC",), proxy_candidates=("XLV",)),
    SymbolResolutionRule(canonical_symbol="BTEC", quote_candidates=("BTEC",), history_candidates=("BTEC",), holdings_candidates=("BTEC",), proxy_candidates=("IBB",)),
    SymbolResolutionRule(canonical_symbol="DFND", quote_candidates=("DFND",), history_candidates=("DFND",), holdings_candidates=("DFND",), proxy_candidates=("ITA", "PPA")),
    SymbolResolutionRule(canonical_symbol="VDST", quote_candidates=("VDST",), history_candidates=("VDST",), holdings_candidates=("VDST",), proxy_candidates=("BIL", "VGSH")),
    SymbolResolutionRule(canonical_symbol="ACOMO", quote_candidates=("ACOMO.AS", "ACOMO"), history_candidates=("ACOMO.AS", "ACOMO"), aliases=("ACOMO.AS",)),
)


class SymbolResolver:
    def __init__(self, rules: tuple[SymbolResolutionRule, ...] = DEFAULT_SYMBOL_RULES) -> None:
        self.rules = rules
        self.rule_index: dict[str, SymbolResolutionRule] = {}
        for rule in rules:
            for key in rule.all_keys():
                self.rule_index[self.normalize(key)] = rule

    def normalize(self, symbol: str) -> str:
        return symbol.strip().upper()

    def canonicalize(self, symbol: str) -> str:
        rule = self.rule_index.get(self.normalize(symbol))
        return rule.canonical_symbol if rule is not None else symbol.strip().upper()

    def _override_candidates(self, symbol: str, overrides: dict[str, list[str]] | None = None) -> tuple[str, ...] | None:
        if not overrides:
            return None
        normalized = self.normalize(symbol)
        for key, candidates in overrides.items():
            if self.normalize(key) == normalized:
                return tuple(dict.fromkeys(candidate.strip().upper() for candidate in candidates if candidate))
        return None

    def get_rule(self, symbol: str) -> SymbolResolutionRule | None:
        return self.rule_index.get(self.normalize(symbol))

    def resolve(self, symbol: str, kind: str, overrides: dict[str, list[str]] | None = None, *, include_proxy: bool = False) -> list[str]:
        override = self._override_candidates(symbol, overrides)
        if override is not None:
            return list(override)

        normalized = self.normalize(symbol)
        rule = self.get_rule(normalized)
        if rule is None:
            return [normalized]

        if kind == "quote":
            primary = rule.quote_candidates or (rule.canonical_symbol,)
        elif kind == "history":
            primary = rule.history_candidates or rule.quote_candidates or (rule.canonical_symbol,)
        elif kind == "holdings":
            primary = rule.holdings_candidates or rule.history_candidates or rule.quote_candidates or (rule.canonical_symbol,)
        elif kind == "proxy":
            primary = rule.proxy_candidates or ()
        else:
            primary = (rule.canonical_symbol,)

        candidates = list(primary)
        if include_proxy and kind in {"history", "holdings"}:
            candidates.extend(rule.proxy_candidates)
        if not candidates:
            candidates.append(rule.canonical_symbol)
        return list(dict.fromkeys(candidate for candidate in candidates if candidate))


DEFAULT_SYMBOL_RESOLVER = SymbolResolver()


def canonicalize_symbol(symbol: str) -> str:
    return DEFAULT_SYMBOL_RESOLVER.canonicalize(symbol)


def resolve_symbol_candidates(symbol: str, overrides: dict[str, list[str]] | None = None, *, kind: str = "quote", include_proxy: bool = False) -> list[str]:
    return DEFAULT_SYMBOL_RESOLVER.resolve(symbol, kind, overrides, include_proxy=include_proxy)


def resolve_proxy_candidates(symbol: str, overrides: dict[str, list[str]] | None = None) -> list[str]:
    return DEFAULT_SYMBOL_RESOLVER.resolve(symbol, "proxy", overrides)


def resolve_etf_holdings_candidates(symbol: str, overrides: dict[str, list[str]] | None = None) -> list[str]:
    return DEFAULT_SYMBOL_RESOLVER.resolve(symbol, "holdings", overrides, include_proxy=True)
