# Epic 38 — Sector-Classification Follow-Through: ETF Look-Through & Diagnostic Integrity

**Status:** Completed (created 2026-08-24)
**Created:** 2026-08-24
**Closed:** 2026-08-24
**Seeded by:** a post-close recon pass over Epic 37 (`.agentic/runs/2026-08-21-epic38-followups-and-etf/01-scout.md`, `02-delivery-brief.md`), which surfaced four findings none of which were new discoveries — all four were already named, in writing, by Epic 37's own stories/PRD as explicitly out of scope or as a noticed-but-unscoped risk: (1) the ETF look-through sector-inference gap Epic 37's PRD explicitly deferred (its own non-goals: "ETF look-through constituent classification... a separate, already-catalogued tech-debt item... deliberately deferred, not this epic"); (2) a cache-flag bug pattern US-37.2 fixed for exactly one method (`get_company_profile`) and named, but did not investigate, for the remaining methods; (3) a duplicated cache-key formula US-37.2's own risk section flagged as "the clean fix belongs in fmp.py itself"; and (4) a flag to re-review the newly-shipped methodology section, which this run's producer verified accurate and closed with no ticket needed. The delivery brief's placement reasoning (§ Placement) is the same pattern Epic 37 itself used against Epic 24: Epic 37 was closed by the time these findings were folded in, so they ship under a new, dedicated epic number rather than reopening it.

## Problem

Epic 37 (US-37.1) fixed the fabrication-by-omission problem — a silent
`"Other"` standing in for an unresolved sector — for **direct equity
holdings** outside the static instrument registry. Two follow-through gaps
remained, both explicitly named at the time rather than discovered later:

1. **ETF look-through constituents still had the same problem.** When a
   look-through constituent's own symbol did not resolve through the static
   registry, `analytics/risk.py` fell back to one of three mechanisms — two
   hardcoded ETF-ticker-keyword → sector proxy lists
   (`_infer_sector_from_sources`, `_infer_sector_from_resolved_pair`), or an
   **ungated** live `market_data.get_company_profile(symbol)` call reading
   FMP's `sector` field directly with no identity check at all — with a
   final silent fallback to `"Other"` when even the guess failed. The
   Exposure tab's look-through sector breakdown, and the Risk tab's factor
   exposures (which read the same totals), were built on guesses dressed up
   as classifications.

2. **The cache-diagnostic `cached` flag lied for five of six call sites.**
   US-37.2 fixed this bug for exactly one `MarketDataService` method
   (`get_company_profile`); `last_fetch_meta`'s `cached` flag for
   `get_latest_quotes`, both branches of `get_historical_prices`,
   `get_direct_verified_benchmark_history`, `get_etf_holdings`, and
   `get_etf_holdings_for_date` still reported a hardcoded `True` regardless
   of whether the call was actually served from cache. Separately, the fix
   `get_company_profile` did get introduced a second problem: its pre-check
   helper re-derived its own copy of the cache-key formula rather than
   calling the one formula `fmp.py`'s `_get()` actually uses, so the two
   could silently drift apart.

## Goal

Ship both follow-through stories:

- **US-38.1** — ETF look-through sector exposure (`build_lookthrough_sector_exposure`
  and the ETF-overlap-pair card's `_build_shared_sector_overlap`) gets a
  real, identity-safe classification when one is resolvable (static registry,
  or a curated fund-category override), and a distinct, always-itemized
  "Unclassified" disclosure — never `"Other"`, never a keyword guess, never
  an ungated live market-data call — when it is not.
- **US-38.2** — every `MarketDataService` method that reports a `cached` flag
  reports the true per-call hit/miss state, the way `get_company_profile`
  already does since US-37.2, and the cache-key formula that answers "is
  this a hit" is expressed once (in `fmp.py`), not re-derived a second time.

## Non-goals

- **Re-deriving ETF-level sector classification from FMP directly.** FMP's
  `sector` field for an ETF ticker itself returns the fund sponsor's own
  classification, not a thematic category (both SPY and GRID return
  `"Financial Services"`) — out of scope for both this epic and Epic 37.
  This remains the one open, narrower remainder of the tech-debt register's
  F-B row.
- **A new dynamic, identity-gated FMP tier for look-through constituents**,
  analogous to US-37.1's tier 2. Structurally inapplicable: a look-through
  constituent carries no statement ISIN on any run, so the identity evidence
  such a tier would need does not exist for this input.
- **Any change to what gets cached, or for how long (TTL, persistence).**
  US-38.2 is a diagnostic-accuracy fix only, reporting what already happens.
- **Any change to the trust ladder, a return formula, or another card's
  methodology.** This epic touches sector classification and cache
  diagnostics only.

## Story snapshot

| Story | Title | Status |
|---|---|---|
| US-38.1 | ETF look-through sector exposure stops guessing and stops silently landing on "Other" | Done |
| US-38.2 | Market-data cache diagnostics report the truth, and the cache-key formula has one home | Done |

Two-story epic. Stories are structurally independent (disjoint files:
`analytics/risk.py` vs. `services/market_data.py` + `clients/fmp.py`;
disjoint concerns). No build-order constraints — both landed in this run.

## Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-08-24 | US-38.2 | `FmpClient` gains `build_cache_identifier` / `is_cached`; `_get` and `get_etf_holders` both now call the one formula instead of constructing it inline. `YFinanceClient` gets its own independent `_build_cache_identifier` / `is_cached` twin (different provider, deliberately not routed through `FmpClient`). `market_data.py`'s `_profile_will_be_served_from_cache` renamed to `_will_be_served_from_cache`, delegates to `FmpClient.is_cached`; `get_latest_quotes`, both branches of `get_historical_prices`, `get_direct_verified_benchmark_history` (AND of two underlying pre-checks), and `get_etf_holdings` all pre-check before fetch and report real hit/miss; `get_etf_holdings_for_date`'s non-history branch inherits the fix via delegation, no separate change needed. `get_company_profile`'s outcome unchanged (AC8 regression). 8 pre-existing tests that fully-mock `FmpClient` needed one prescribed line (`instance.is_cached.return_value = True`) each; all fixed. All 8 ACs satisfied per tech-lead INTEGRATION's ticket-by-ticket trace. 858 → (backend, before US-38.1 landed) with +test coverage: miss-then-hit pairs for all 5 methods, an AND-semantics test proving the two-underlying-call requirement, and a structural formula-agreement test (`test_get_and_is_cached_derive_the_cache_key_from_the_same_formula`) proving AC7 by construction, not just today's fixture output. |
| 2026-08-24 | US-38.1 | `analytics/risk.py`'s two hardcoded ETF-ticker-keyword → sector proxy functions (`_infer_sector_from_sources`, `_infer_sector_from_resolved_pair`) and the ungated live `get_company_profile` fallback inside `_build_shared_sector_overlap` are deleted, replaced by a static-registry-or-"Unclassified" rule (per-source-slice attribution preserved; a slice with no resolvable sector counts, at full weight, toward "Unclassified" — never redistributed, never dropped from the total). The curated fund-category override mechanism (Bond/Commodity/Sector/Thematic ETFs with their own `.sector`) is untouched. "Unclassified" is exempt from the existing `MIN_SECTOR_WEIGHT` (0.05%) display-suppression filter every other bucket keeps — always itemized, however small (human-resolved design decision). Eight ETF tickers the deleted proxy lists referenced but the registry didn't curate (`XLF`, `XLV`, `IBB`, `ITA`, `PPA`, `BIL`, `VGSH`, `DBC`) are now curated in `INSTRUMENT_DEFINITIONS`, shipped inside this story (human-resolved) rather than as a fast-follow, preserving factor-tilt fidelity (e.g. the Defense tilt) for value sourced through them. All 9 ACs satisfied per tech-lead INTEGRATION's trace and independently re-derived by quant-analyst AUDIT (own fixtures, not the shipped test file — matched the research brief's worked example: Technology $6,000/60%, Unclassified $4,000/40%). 20 new tests added to `test_analytics.py` (registry-hit, fund-category-override, unresolved-to-Unclassified, partial-resolution reconciliation, suppression-exemption asymmetry, all 8 companion tickers parametrized, a Defense-Tilt factor-exposure regression, `_build_shared_sector_overlap`'s three resolution paths via a no-network-call spy) plus a "no literal Other anywhere" regression in `test_exposure_engine.py`. 858 → 878 backend (+20), 331 frontend unchanged; tsc + dead-code gate clean; `dashboardGoldens.ts` untouched. Docs: `financial-methodology.md` gains "ETF look-through constituent classification (US-38.1)"; `exposure-fields.md`'s look-through-sector rows document the "Unclassified" bucket; `tech-debt-register.md:177` (F-B) corrected and marked RESOLVED, narrower ETF-side-FMP-reliability sub-finding left explicitly open. Both gates (quant-audit, integration) and the acceptance reviewer returned PASS — all 17 ACs across both stories verified SATISFIED, no GAP/DRIFTED. |

Final state (both stories combined, per 13-integration.md's independently
re-run verification): backend 878 passed, frontend 331 tests / 37 files
passed, `tsc --noEmit` clean, dead-code gate (ruff + vulture + knip) clean,
`dashboardGoldens.ts` byte-identical.
