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
    # ICOM = iShares Diversified Commodity Swap UCITS ETF (LSE, USD) → ICOM.L on Yahoo.
    SymbolResolutionRule(canonical_symbol="ICOM", quote_candidates=("ICOM.L", "ICOM"), history_candidates=("ICOM.L", "ICOM"), holdings_candidates=("ICOM.L", "ICOM"), proxy_candidates=("DBC",), aliases=("ICOM.L",)),
    SymbolResolutionRule(canonical_symbol="IUFS", quote_candidates=("IUFS",), history_candidates=("IUFS",), holdings_candidates=("IUFS",), proxy_candidates=("XLF",)),
    SymbolResolutionRule(canonical_symbol="IUHC", quote_candidates=("IUHC",), history_candidates=("IUHC",), holdings_candidates=("IUHC",), proxy_candidates=("XLV",)),
    SymbolResolutionRule(canonical_symbol="BTEC", quote_candidates=("BTEC",), history_candidates=("BTEC",), holdings_candidates=("BTEC",), proxy_candidates=("IBB",)),
    # DFND = iShares Global Aerospace & Defence UCITS ETF (LSE, GBP). The Yahoo
    # line is DFND.L (confirmed via yfinance longName + the user's broker
    # statement; see US-18.3 correction). Do NOT map to DFNS.L/DFEN.DE/DFNG.L —
    # those are VanEck Defense, a DIFFERENT fund. Proxies ITA/PPA (US A&D).
    SymbolResolutionRule(canonical_symbol="DFND", quote_candidates=("DFND.L", "DFND"), history_candidates=("DFND.L", "DFND"), holdings_candidates=("DFND.L", "DFND"), proxy_candidates=("ITA", "PPA"), aliases=("DFND.L",)),
    # VDST = Vanguard U.S. Treasury 0-1 Year Bond UCITS ETF (LSE, USD) → VDST.L on Yahoo.
    SymbolResolutionRule(canonical_symbol="VDST", quote_candidates=("VDST.L", "VDST"), history_candidates=("VDST.L", "VDST"), holdings_candidates=("VDST.L", "VDST"), proxy_candidates=("BIL", "VGSH"), aliases=("VDST.L",)),
    SymbolResolutionRule(canonical_symbol="ACOMO", quote_candidates=("ACOMO.AS", "ACOMO"), history_candidates=("ACOMO.AS", "ACOMO"), aliases=("ACOMO.AS",)),
    # UCITS ETFs without direct FMP coverage — exchange suffixes tried first; proxy is a US-listed equivalent
    # used as a fallback when allow_proxy_fallback=True is passed to MarketDataService.
    SymbolResolutionRule(canonical_symbol="IUIT", quote_candidates=("IUIT.L", "IUIT"), history_candidates=("IUIT.L", "IUIT"), holdings_candidates=("IUIT.L", "IUIT"), proxy_candidates=("XLK",), aliases=("IUIT.L",)),
    # SEMI = iShares MSCI Global Semiconductors UCITS ETF (LSE, GBP, ISIN
    # IE000I8KRLL9) → SEMI.L on Yahoo. Deliberately NO bare "SEMI" candidate:
    # on FMP that symbol is a DIFFERENT US-listed security (2026-06-30 quote
    # 40.58 vs the held line's 17.998 GBP, 2.25×; Epic 31 F-5). Same wrong-fund
    # trap as CIBR/DFND. The US line is reachable only as a labeled proxy; the
    # real fund comes from SEMI.L via the yfinance fallback. SOXX/SMH are the
    # deliberate US semiconductor proxies (allow_proxy_fallback=True).
    SymbolResolutionRule(canonical_symbol="SEMI", quote_candidates=("SEMI.L",), history_candidates=("SEMI.L",), holdings_candidates=("SEMI.L",), proxy_candidates=("SOXX", "SMH"), aliases=("SEMI.L",)),
    SymbolResolutionRule(canonical_symbol="SXRV", quote_candidates=("SXRV.DE", "SXRV"), history_candidates=("SXRV.DE", "SXRV"), holdings_candidates=("SXRV.DE", "SXRV"), proxy_candidates=("QQQ",), aliases=("SXRV.DE",)),
    SymbolResolutionRule(canonical_symbol="DEFS", quote_candidates=("DEFS.L", "DEFS"), history_candidates=("DEFS.L", "DEFS"), holdings_candidates=("DEFS.L", "DEFS"), proxy_candidates=("ITA", "PPA"), aliases=("DEFS.L",)),
    SymbolResolutionRule(canonical_symbol="IAUP", quote_candidates=("IAUP.L", "IAUP"), history_candidates=("IAUP.L", "IAUP"), holdings_candidates=("IAUP.L", "IAUP"), proxy_candidates=("GDX",), aliases=("IAUP.L",)),
    SymbolResolutionRule(canonical_symbol="IDFN", quote_candidates=("IDFN.L", "IDFN"), history_candidates=("IDFN.L", "IDFN"), holdings_candidates=("IDFN.L", "IDFN"), proxy_candidates=("ITA", "PPA"), aliases=("IDFN.L",)),
    # CIBR (statement 2026-06: First Trust Nasdaq Cybersecurity UCITS ETF,
    # LSE, ISIN IE00BF16M727) → CIBR.L on Yahoo. Deliberately NO bare "CIBR"
    # candidate: on FMP that symbol is the *US-listed sister fund* (a different
    # security — the DFND wrong-fund lesson). The US fund is available only as
    # the explicit, labeled proxy (allow_proxy_fallback=True).
    SymbolResolutionRule(canonical_symbol="CIBR", quote_candidates=("CIBR.L",), history_candidates=("CIBR.L",), holdings_candidates=("CIBR.L",), proxy_candidates=("CIBR",), aliases=("CIBR.L",)),
    # SBIO (statement: Invesco NASDAQ Biotech UCITS ETF, LSE, ISIN
    # IE00BQ70R696) -> SBIO.L on FMP/Yahoo. Deliberately NO bare "SBIO"
    # candidate: on FMP that symbol is a DIFFERENT US-listed security (ALPS
    # Medical Breakthroughs ETF, isin US00162Q5936 -- confirmed live,
    # 03-quant-research.md Live evidence log item 3). Same wrong-fund trap as
    # SEMI/CIBR/DFND. No US proxy is defined -- none was requested by this
    # story and none is needed for the identity gate to fail closed.
    SymbolResolutionRule(canonical_symbol="SBIO", quote_candidates=("SBIO.L",), history_candidates=("SBIO.L",), holdings_candidates=("SBIO.L",), aliases=("SBIO.L",)),
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
