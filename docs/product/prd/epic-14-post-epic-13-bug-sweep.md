# PRD: Epic 14 — Post-Epic-13 Bug Sweep

**Status:** Active
**Last updated:** 2026-06-01

---

## Problem

Running the product after Epic 13 shipped surfaced three independent
bugs that didn't justify their own epics individually but together
warrant a focused sweep before the next product epic:

1. **`overlayImportedSnapshot` symbol collision** — when two
   statements (e.g. IB + ESPP) both hold the same ticker, the
   "Add Statement" overlay flow REPLACES the existing position
   with the new one instead of summing the market values. Users
   silently lose dollars when adding statements that share any
   ticker with an existing import.

2. **DrawdownAnalyticsCard smart-default window absent** — the
   card defaults to a 1260-day window. If the FMP cache doesn't
   have that much history for the user's portfolio, the card
   shows EmptyState even though shorter windows (756d / 252d)
   may have plenty of data. User must manually click each window
   until something renders.

3. **Importer description weakness leading to "Other" sector
   mis-classification** — VTI (and other unknown US-listed ETFs)
   imported via Freedom24 land in "Other" because the parser
   uses the bare ticker as the description, and the registry's
   description-based ETF fallback can't detect anything from a
   raw ticker. Fixing the registry static map per-ticker (as
   done in the previous commit for VTI + 14 siblings) is a
   patch, not a fix: every NEW ticker any user holds will hit
   the same bug.

---

## Goal

- Sum market values + quantities when a symbol exists in both
  the existing portfolio and the newly-added statement (US-14.1).
- DrawdownAnalyticsCard falls back to the next-shorter window
  with data when its default window returns
  `trust='unavailable'` (US-14.2).
- Unknown-symbol imports automatically enrich
  `ImportedInstrument` with name + sector via the FMP company
  profile (US-14.3), so the static registry remains the
  fast-path but the slow-path covers any ticker FMP knows about.

---

## Non-goals

- No changes to methodology — every fix is a behaviour
  correction, not a new formula.
- No new Risk-tab cards, no new analytics modules.
- No expansion of the synthetic-history model (per-position
  entry-date semantics deliberately deferred — was discussed
  and explicitly out of scope per user direction).
- No new tab, no new route prefix.
- No retroactive fix to existing imported workspaces — the
  fixes apply to FUTURE imports only.
- No multi-currency handling (cross-cutting; separate epic).
- No new broker importers.

---

## Story list

| Story | Title | Scope |
|---|---|---|
| US-14.1 | Fix overlay symbol collision (sum, don't replace) | `apps/desktop/src/features/portfolio/portfolioSnapshot.ts` `overlayImportedSnapshot`; clone+test |
| US-14.2 | DrawdownAnalyticsCard smart-default window fallback | `apps/desktop/src/features/portfolio/DrawdownAnalyticsCard.tsx` — cycle 1260→756→252→Max on `trust='unavailable'` |
| US-14.3 | Freedom24 FMP company-profile enrichment for unknown symbols | `services/quant-engine/app/importers/freedom24.py` + new shared `enrich_imported_instrument` helper using `MarketDataService.get_company_profile` (or equivalent); falls through to current behaviour on FMP miss |

Stories may be built in any order but the recommended sequence
is 14.1 → 14.2 → 14.3 (biggest user impact first, polish
second, most-invasive last).

---

## Success signals

- **US-14.1**: importing IB + Add-Statement ESPP where both
  hold MSFT shows the combined MSFT market value (= IB amount +
  ESPP amount), not just the ESPP amount. New frontend vitest
  pinning the sum behaviour.
- **US-14.2**: a portfolio whose 1260d window has insufficient
  FMP history (synthetic, e.g. a position FMP only knows from
  Jan 2026 onward) renders the card with the longest window
  that DOES have data, not EmptyState. New frontend vitest with
  URL-routed mock returning unavailable→synthetic on second
  window attempt.
- **US-14.3**: importing a Freedom24 statement that contains a
  ticker not in INSTRUMENT_DEFINITIONS (e.g. a less-common
  Vanguard ETF) shows the FMP-enriched sector on the Exposure
  tab, not "Other". New backend pytest mocking FMP
  `get_company_profile` and asserting the enriched
  `ImportedInstrument` description / sector flow through to
  `attach_snapshot_metadata`.
- All previously Done tests stay green throughout.
- Epic-roadmap.md gets a slice log per story; Epic 14 flips
  Active → Completed when US-14.3 closes.

---

## Methodology / docs impact

None of the three stories changes any financial formula. The
methodology doc is not touched. New contract docs are not
needed (existing schemas unchanged). The Risk-fields contract
doc may get a one-line note in US-14.2's docs ticket if the
DrawdownAnalyticsCard's window-selection behaviour benefits
from explicit documentation.
