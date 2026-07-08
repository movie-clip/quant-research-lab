# Epic 26 — Currency Exposure & Risk

**Status:** Backlog (research brief only — not yet ticketed)
**Created:** 2026-07-04
**Validity re-check:** 2026-07-08 — premise re-verified against the current
codebase and **strengthened** by Epics 27/28: the display gap is unchanged
(no view aggregates `ImportedPosition.currency` anywhere), `get_fx_history`
still has zero callers (US-26.2 blocker intact), and two new inputs now exist
that this brief predates: (1) US-28.1's **statement-implied FX rates**
(`statement_totals.fx_rates` carries broker-truth EURUSD/GBPUSD derived from
the statement's own Open Positions totals — exactly the conversion basis a
base-currency-consistent exposure card wants, with no market-data call);
(2) US-27.8's `fx_fallback_currencies` disclosure on drift/dashboard-history
(the UI already admits FX blindness — this epic is its documented fix).
The `reconciliation.py` hardcode cited below was generalized by US-28.1;
the display gap it pointed at remains.

## Problem

The project holds no explicit view of how much of a portfolio is denominated
in a currency other than its base currency. `ImportedPosition.currency` and
`ImportedStatement.base_currency` are already captured on every import, but
nothing aggregates or displays them anywhere in the product. A researcher
holding UCITS ETFs traded in EUR/GBP (the project's documented UCITS support
implies this is a real scenario, not hypothetical) has currency risk they
cannot see on Dashboard, Exposure, or Risk. This gap was also flagged
indirectly by the tech-debt register: `reconciliation.py`'s hardcoded
`fx_rates.get("EURUSD", 1.0)` bakes in a single-currency-pair,
1.0-fallback assumption precisely because the project has never had to think
about multi-currency exposure as a first-class concept.

## Goal

- Give the researcher a **Currency Exposure** view on the Exposure tab: what
  fraction of the portfolio is in each currency, and how much is non-base.
- Do this with **zero new market-data dependency** — the MVP uses only
  already-imported `ImportedPosition.currency` fields (snapshot analytics,
  same trust class as sector exposure).
- Document (but explicitly do not build) the harder currency-*risk*
  question — how much historical return volatility came from FX moves — as
  a scoped-out stretch item with its own formula shape, so a future story
  doesn't have to re-derive the theory.

## Non-goals

- **No historical currency-risk decomposition in this epic's MVP story.**
  The local-return/FX-return/interaction-term decomposition
  (§Currency Risk Contribution in `financial-methodology.md`) is
  deliberately out of scope — it requires `MarketDataService.get_fx_history`
  to be verified as actually working (it has zero callers today) and a
  portfolio-level variance-decomposition design this brief does not resolve.
- **No hedging recommendation, no suggested currency overlay, no target
  currency-weight guidance** — this is a no-execution product; currency
  exposure is descriptive only, same as sector exposure today.
- **No change to `reconciliation.py`'s FX-rate handling.** That is a
  separate, already-catalogued tech-debt item (Epic 24 backlog); this epic
  does not depend on or fix it, though a future currency-risk story likely
  will want the same multi-pair FX-rate infrastructure.
- **No currency-hedged-share-class detection** (e.g. distinguishing a
  EUR-hedged US equity ETF from unhedged EUR exposure) — `risk.py` already
  has a `currency_hedged` concept for UCITS mapping-quality scoring; this
  epic's snapshot exposure view does not attempt to reuse or extend that,
  since hedged-share-class detection is a distinct, harder data problem.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-26.1 | Currency exposure by weight (snapshot) | Backend — new `app/analytics/<name>.py` pure function computing per-currency weight + non-base-currency weight from `ImportedPosition.currency`/`ImportedStatement.base_currency`; wired into the exposure engine/schema; a new Exposure-tab card (snapshot trust badge, `ui-polish` primitives) showing the weight breakdown + an "unclassified" residual for null-currency positions. |
| US-26.2 (stretch, not ready) | Currency risk contribution (historical) | Requires a follow-up research brief resolving the interaction-term and portfolio-variance-decomposition questions left open above, and empirical verification that `get_fx_history` actually returns usable FX history via FMP before any schema/engine work begins. |

## Success signals

- A researcher holding non-base-currency positions can answer "how much of
  my portfolio is not in USD?" from the Exposure tab without doing the math
  themselves.
- The new card never fabricates a currency for a position that doesn't have
  one — an "unclassified" bucket is visible instead.
- No new market-data call is added for US-26.1 (verifiable: the new
  analytics function takes only the already-imported snapshot as input).
