# Epic 18 — Secondary Market-Data Provider (yfinance fallback)

**Status:** Active
**Created:** 2026-06-05

## Problem

The quant engine sources all price history from Financial Modeling Prep (FMP).
FMP's current plan covers US-listed equities/ETFs but returns **HTTP 402
(Payment Required)** for European exchange-listed symbols (`.L`, `.DE`, `.AS`,
`.MI`, `.PA`). For a portfolio of European **UCITS ETFs** (VUAA, SXRV, SGLD,
ICOM, VDST, IUIT, IAUP, …) this means *no price history at all* — those
holdings are silently excluded from every history-based analytic (correlation
matrix, factor model, drift, rolling risk). The data exists and is long-lived;
it is simply not served by this provider tier.

A proof-of-concept confirmed that **Yahoo Finance (via `yfinance`) returns full
adjusted-close history, for free, for the exact suffixed symbols the resolver
already produces** — 7 of the 10 excluded tickers resolve immediately; a few
niche defense ETFs need correct Yahoo symbols.

## Goal

- Add **yfinance as a secondary (fallback) market-data provider** behind the
  existing `MarketDataService` seam: FMP first, yfinance when FMP returns empty
  for a candidate. UCITS holdings stop being excluded across all analytics.
- Introduce an explicit **data provenance** dimension (`fmp` vs `yfinance`)
  that flows from the data layer into engine responses and is **surfaced
  visibly** in the UI — the researcher always knows which provider backed a
  holding (per the traceability guardrail).
- Reuse the existing symbol-resolution candidates, JSON cache, and return-basis
  classification. No change to the FMP path's behaviour.

## Non-goals

- **Not replacing FMP.** yfinance is fallback-only; FMP remains primary for
  everything it covers.
- **No new financial formula.** This is data-sourcing + provenance plumbing, not
  new analytics.
- **No live network in tests.** yfinance must be mocked exactly as FMP is.
- **No proxy substitution.** This epic fetches the *real* holding's history from
  a second provider — it is unrelated to the (still-disabled) US-proxy fallback.
- **No automatic correctness guarantee for ambiguous tickers.** Defense ETFs
  whose Yahoo symbol differs from the canonical (DFND, DEFS, IDFN) are handled
  by a dedicated symbol-mapping story, not guessed.

## Story list

| Story | Title | Scope |
|---|---|---|
| US-18.1 | yfinance fallback provider + data provenance | Backend — `YFinanceClient`; `MarketDataService` fallback + per-history provenance; reuse cache; offline test mocks; `requirements.txt`. Surface provenance on the Intra-Portfolio Correlation card (the surface where the gap appears) with a visible "via Yahoo Finance" secondary-source marker. Docs: system-architecture provider seam + trust/provenance note. |
| US-18.2 | Broaden provenance badges across analytics | Surface the provenance marker on the other history-based surfaces (factor model, drift, rolling risk, multi-benchmark) that now resolve UCITS holdings. |
| US-18.3 | Defense-ETF Yahoo symbol mapping | Research + add correct Yahoo symbols/resolution rules for DFND, DEFS, IDFN (and any other ambiguous UCITS tickers). |

Recommended build order: 18.1 → 18.2 → 18.3. US-18.1 is independently
valuable (it recovers 7/10 holdings end-to-end and establishes the provenance
mechanism).

## Success signals

- A portfolio of UCITS ETFs shows real holdings in the correlation matrix
  instead of a 10-row "excluded: insufficient history" caption.
- Every holding backed by Yahoo is visibly marked as such; no Yahoo-sourced
  value is presented as if it came from the primary provider.
- The FMP-only path (US holdings) is byte-for-byte unchanged.
- Tests run offline (both providers mocked); no network dependency introduced.
