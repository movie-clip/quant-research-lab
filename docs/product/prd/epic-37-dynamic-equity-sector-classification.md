# Epic 37 — Dynamic Equity Sector Classification

**Status:** Completed (created 2026-08-21)
**Created:** 2026-08-21
**Seeded by:** `docs/tech-debt-register.md`'s `instruments/registry.py:45-48,180-261`
row (tagged `epic-24`: "the keyword classifier is the fragile part"), acted on
via a dedicated research + story-drafting run
(`.agentic/runs/2026-08-21-dynamic-sector-classification/`). The originating
tech-debt row still explains *why* this fix exists; it does not determine epic
placement.

## Problem

`InstrumentRegistry.classify_imported_instrument`'s equity branch
(`services/quant-engine/app/instruments/registry.py:256-265`) unconditionally
returns `sector="Other"` for any equity not present in the static,
hand-curated `INSTRUMENT_DEFINITIONS` dict — no keyword inference, no
market-data lookup, nothing. Verified live against the bound statement
(`docs/IB2026.csv`): four real, currently-held equities (INTU, PANW, VICI,
SPCX) all land in `"Other"` today, though all four resolve cleanly via FMP's
company-profile endpoint with an ISIN that matches the statement's own
`Security ID` byte-for-byte. The Exposure tab's sector breakdown is therefore
an artifact of which ~90 tickers happen to be hand-curated, not a reflection
of what the researcher actually holds.

A bare-ticker provider lookup is not a safe substitute on its own — this
codebase has three prior recorded incidents of a bare-ticker FMP/Yahoo lookup
resolving to the wrong security (`app/core/symbols.py`'s `DFND`/`SEMI`/`CIBR`
comments) plus a fourth live reproduction (`DFNS`) found during this epic's
research pass. Any fix has to be identity-gated, reusing the evidence-gated
ISIN-comparison pattern this codebase already established for registry-known
holdings (US-19.1/US-19.2), not a second, divergent trust check.

**Why this is its own epic, not a reopened Epic 24.** The originating
tech-debt row was catalogued under Epic 24 ("Codebase Improvement"), but
Epic 24 is closed. The human decided this fix should not reopen that closed
epic — it ships under its own new, dedicated, single-story epic number
instead. Nothing about the fix's scope or grounding depends on which epic
number it is filed under.

## Goal

Ship US-37.1: any equity held outside the static registry gets a real,
identity-confirmed sector classification from market data when one is safely
resolvable, and an honest, distinctly-labeled "unclassified" disclosure when
it is not — never a silent `"Other"` standing in for absence.

## Non-goals

- **ETF look-through constituent classification** (`analytics/risk.py`'s
  `build_lookthrough_sector_exposure` / `_infer_sector_from_sources` and its
  duplicated hardcoded proxy-ticker list). A separate, already-catalogued
  tech-debt item (`docs/tech-debt-register.md`, `risk.py:1485-1499,1537-1549`);
  deliberately deferred, not this epic.
- **An audit-first / impact-quantification pass.** The research already
  grounded and live-verified the fix (see US-37.1's Context); this epic ships
  the direct correction, not a further investigation.
- **ETF-side FMP sector reliability.** FMP's `sector` field looks unreliable
  as an ETF-constituent proxy (both SPY and GRID return the fund sponsor's own
  `"Financial Services"` classification rather than a thematic one) — that is
  ETF-look-through territory, out of scope here.
- **Persisting the resolved classification as its own versioned record**, as
  opposed to widening the existing HTTP cache TTL. Left as an explicit
  "should, not a hard block" open decision for the design pass — see US-37.1's
  `## Open decisions`.
- **Any change to the trust ladder, a return formula, or another card's
  methodology.** This epic touches sector classification only.

## Story list

| Story | Title | Scope |
|---|---|---|
| [US-37.1](../stories/US-37.1-dynamic-equity-sector-classification.md) | Dynamic, identity-gated sector classification for equities outside the static registry | Full-stack (backend-weighted) — extends `InstrumentRegistry.classify_imported_instrument`'s equity branch with an identity-gated FMP resolution order (static → FMP+ISIN-confirmed → no classification), a sector-taxonomy normalization table, fail-safe FMP-failure handling, and the `analytics/overview.py` aggregation follow-through so an unclassified equity is disclosed by name rather than re-coerced to `"Other"`. Carries 4 open decisions (provenance-field naming, `sector` nullability wiring, ISIN-mismatch state shape, caching/persistence shape) that block ticketing until the design pass settles them. |

Single-story epic. No build-order constraints.

## Success signals

- The Exposure tab's sector breakdown reflects an equity's real, confirmed
  sector when one is safely resolvable, for holdings outside the static
  registry — not a blanket `"Other"`.
- An equity with no safely-resolvable sector is disclosed under a distinct,
  named unclassified state, with its weight still counted in the sector
  total — never dropped, never folded into `"Other"`.
- A statement/FMP ISIN mismatch never lets a wrong sector through — the
  identity gate fails closed to no classification, not a wrong classification.
- `python scripts/run_all_tests.py` stays green; any golden diff is limited to
  the legitimate reclassification of currently-`"Other"` equities.
