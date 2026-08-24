# Epic 39 — Direct-Held ETF Sector Classification

**Status:** Completed (created 2026-08-24)
**Created:** 2026-08-24
**Closed:** 2026-08-24
**Seeded by:** `docs/tech-debt-register.md:186`'s keyword-classifier clause
(tagged `epic-24`), surfaced via a fresh user request this run rather than a
health-review pass — the same lineage as Epic 37 (`registry.py`'s equity
branch, same row's other clause) and Epic 38 (the row's companion `risk.py`
look-through finding, `tech-debt-register.md:177`). This epic closes the
third and final code path off that lineage: `InstrumentRegistry
.classify_imported_instrument`'s **direct-held ETF branch**
(`registry.py:246-292`), the one sector-classification path neither Epic 37
(equity branch) nor Epic 38 (ETF look-through) touched.

## Problem

The direct-held ETF branch classified `sector` with a keyword-substring
matcher over the broker's free-text description (`"BIOTECH"`,
`"FINANCIAL"`, `"SEMIC"`, and about ten others). When none of its ~10
keywords hit, it silently defaulted `sector = "Broad Market"` — a claim
about the fund's *intent* (index-tracking, not sector-focused), asserted
with no evidence behind it.

**The user's stated symptom (SBIO showing as "Unclassified") was itself
wrong** — live-verified during this run's producer/research passes, SBIO
resolved to `sector = "Health Care"` today via the keyword matcher's
`"BIOTECH"` hit, not `"Unclassified"`. The underlying concern was real
regardless: the classification was a keyword guess with no identity
evidence behind it, structurally the same fragility Epic 37 fixed for
equities and Epic 38 fixed for look-through constituents.

**`get_company_profile`'s `sector` field is not the fix, confirmed live
against six ETFs** (SBIO, SPY, XLF, GRID, QQQ, ICLN): FMP's general profile
`sector` field returns the identical fund-sponsor/vehicle pair
(`"Financial Services"` / `"Asset Management"`) for every one — never a
thematic answer for any ETF. This extends the finding both Epic 37's and
Epic 38's PRDs already recorded as a non-goal.

**A dedicated FMP endpoint answers the theme correctly**, but only once
identity is confirmed — `/stable/etf/sector-weightings` returns each ETF's
real sector-weight breakdown, live-verified against eight tickers.
**The SBIO ticker-collision case, proven live, is the reason an identity
gate is not optional**: the bare ticker `"SBIO"` resolves on FMP to a
*different* security (`ALPS Medical Breakthroughs ETF`, ISIN
`US00162Q5936`, US-listed) than the statement's actual holding
(`Invesco NASDAQ Biotech UCITS ETF`, ISIN `IE00BQ70R696`, `SBIO.L`). Without
an identity gate, the sector-weightings endpoint would have returned a
plausible-looking "Healthcare 100%" result sourced from the *wrong*
security — the two funds happen to agree on theme by coincidence here,
nothing guarantees that in general.

## Goal

Identity-gated dynamic classification for the direct-held ETF branch,
static-curation-first, mirroring Epic 37's equity-branch shape:

1. Static registry lookup (unchanged) always wins.
2. Identity-gated dynamic lookup, opt-in (only when `market_data` is
   supplied): confirm a symbol candidate's FMP profile ISIN matches the
   statement's own ISIN, then read that candidate's
   `/stable/etf/sector-weightings` result; accept the top-weighted sector
   bucket as a single-sector classification only when its share of total
   weight clears `DOMINANCE_THRESHOLD = 55%` (human-resolved); map it
   through the existing sector-taxonomy table.
3. Anything that does not clear every step — no ISIN match, no ISIN
   evidence on either side, an empty/zero-weight response, a below-threshold
   top share, an unmapped sector bucket, a lookup exception — resolves to no
   classification, never a fallback guess, and specifically never
   `"Broad Market"`.

Delivered as a single story, **US-39.1**.

## Non-goals

- **The `category` field's dynamic tier.** This epic resolves `sector`
  only, via the existing `SECTOR_TAXONOMY_MAP` — the existing keyword-based
  `category` derivation (Sector/Thematic/Broad Market/Bond/Commodity ETF)
  is untouched.
- **The ETF-level `get_profile` sector field as a data source.** Confirmed
  unreliable for every ETF tested (fund-sponsor classification, not
  thematic) — a different, dedicated endpoint is used instead.
- **The ETF look-through path** (`analytics/risk.py`'s constituent
  classification) — already fixed by Epic 38 / US-38.1.
- **The futures-reference-data clause of `tech-debt-register.md:186`**
  (`tick_size`/`point_value`/`multiplier`) — a separate clause of the same
  row, already deemed acceptable and documented in the `fmp-data` skill.
- **Wiring yfinance's `funds_data.sector_weightings` as a production
  fallback path.** Used only as second-provider corroboration evidence for
  feasibility — yfinance exposes no ISIN and cannot itself pass the identity
  gate.
- **Persisting the resolved classification as its own versioned record.**
  Reuses the existing per-call caching pattern.

## Story snapshot

| Story | Title | Status |
|---|---|---|
| US-39.1 | Direct-held ETF sector classification stops relying on keyword-substring matching | Done |

Single-story epic. No build-order constraints.

## Slice log

| Date | Story | What shipped |
|---|---|---|
| 2026-08-24 | US-39.1 | `instruments/registry.py`'s ETF branch: every keyword-driven `sector = ...` assignment (the `"Broad Market"` default and all 9 elif branches) removed; `category` derivation left byte-identical. New module `instruments/etf_sector_resolution.py` (`resolve_etf_sector`, mirrors `equity_sector_resolution.py`'s shape) implements the identity gate → dominance-threshold (`DOMINANCE_THRESHOLD = 0.55`) → shared-taxonomy-map resolution order, reusing `instrument_identity.normalize_isin` and `equity_sector_resolution.SECTOR_TAXONOMY_MAP` (imported, not duplicated). New `FmpClient`/`MarketDataService.get_etf_sector_weightings(symbol)` reads `/stable/etf/sector-weightings`. New `ClassificationSource` literal `"fmp_etf_sector_weighting_confirmed"`, kept distinct from the equity tier's `"fmp_identity_confirmed"` to preserve provenance traceability. New `SymbolResolutionRule` for SBIO in `app/core/symbols.py` (`SBIO.L` only, deliberately no bare `"SBIO"` candidate) prevents the proven ticker-collision at the candidate-list level, before the identity gate is even reached. All 12 ACs SATISFIED per tech-lead INTEGRATION's ticket-by-ticket trace and the acceptance reviewer's independent AC-by-AC trace (own reading of code + tests, not the report descriptions); independently re-derived by quant-analyst AUDIT against real on-disk FMP cache data (no mocks) — resolved SBIO to `("Health Care", "fmp_etf_sector_weighting_confirmed")` via `SBIO.L`, matching the story's central claim byte-for-byte. 878 → 905 backend (+27: 17 new `test_etf_sector_resolution.py` resolver tests, 2 pre-existing pinned-defect tests rewritten to the new fail-closed semantics, 3 new registry wiring tests, 1 new aggregation test, 6 new tests in a new `test_symbols.py` module), 331 frontend unchanged; tsc + dead-code gate clean. Docs: `financial-methodology.md` gains "Direct-held ETF branch classification (US-39.1)"; `exposure-fields.md`'s enumeration prose lists the new `classification_source` literal; `tech-debt-register.md:186` narrowed — the keyword-classifier clause marked RESOLVED, the futures-reference-data clause left untouched; `current-product-state.md`'s Exposure-tab paragraph extended with the direct-held-ETF-branch mechanism. **Unplanned T-39.1.7** (see § Notes) fixed a pre-existing golden-export determinism defect the test lane's coverage first exposed. Both gates (quant-audit, integration) and the acceptance reviewer returned PASS — all 12 ACs verified SATISFIED, no GAP/DRIFTED. |

Final state (per 14-review.md's independently re-run verification): backend
905 passed, frontend 331 tests / 37 files passed, `tsc --noEmit` clean,
dead-code gate (ruff + vulture + knip) clean.

## Notes

**T-39.1.7 — unplanned golden-export determinism fix, pre-existing since
US-37.1, first exposed by this story.** `app/analytics/overview.py`'s
`build_portfolio_overview` always constructed a real, unmocked
`MarketDataService()` internally with no injection seam. The golden-export
script's bare-script path therefore resolved SBIO's sector from the live
on-disk FMP cache (`"Health Care"`), while pytest's in-process render ran
under an autouse mock (added for US-37.1) that always returns
`get_company_profile() -> None`, forcing `"Unclassified"` — two different
answers for the same committed golden file. Inert until this story's ETF
dynamic lookup became the first classification path in the golden statement
to actually diverge between the two render paths. Fixed by giving
`build_portfolio_overview` a keyword-only `market_data` parameter (defaults
to constructing `MarketDataService()` only when `None`, a strict superset of
prior behavior for every existing caller) and threading the export script's
own frozen/recording provider through it — both render paths now go through
the *same* object and fail closed identically. `dashboardGoldens.ts`
regenerated: SBIO moves from a stale, live-cache-derived
"Health Care"/"Consumer Discretionary" split into its own dedicated
"Unclassified" bucket, weight preserved (0.55%), no other symbol changed.
Judged methodologically sound and narrowly scoped by both gates
independently — the fix is guardrail 4 (trust semantics over fabrication)
working as intended, not a workaround.

**Two small, non-blocking carries from the review gates, not acted on this
pass:**

1. The committed golden fixture no longer exercises SBIO's *positive*
   dynamic-resolution path end-to-end — only the fail-closed path is
   covered by the golden diff, since `FrozenMarketData`/`RecordingMarketData`
   implement only the four price-history methods, not
   `get_company_profile`/`get_etf_sector_weightings`. Coverage for the
   positive path rests on the 17 unit tests (`FakeMarketData`, not the real
   client) and on quant-audit's own out-of-band recomputation against the
   real on-disk FMP cache. A future regression in the real field-name/
   candidate wiring (e.g. FMP renaming `weightPercentage`) would keep
   failing closed rather than being caught by the golden diff — safe, but
   silent. Recommended follow-up (unticketed): extend
   `FrozenMarketData`/`RecordingMarketData` with the two profile/weightings
   methods so a future `--capture` run can deterministically freeze a
   positive dynamic-resolution outcome too.
2. `RecordingMarketData`'s docstring is misleadingly worded (claims full
   delegation to the wrapped real service; only forwards the same four
   price-history methods `FrozenMarketData` does). Pre-existing, untouched
   by this epic — a documentation nit worth fixing whenever that file is
   next touched.

Neither carry blocks this epic's acceptance; both are recorded here per the
close-out order rather than filed as new tech-debt-register rows, since
they are narrow, already-diagnosed, non-blocking observations rather than
standing findings.
